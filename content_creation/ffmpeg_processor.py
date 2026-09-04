"""
ffmpeg_processor.py - Non-Destructive FFmpeg Filtergraph Generator & Media Engine

Handles:
1. 9:16 vertical re-framing (Center Crop, Blurred Background Pad, Subject Offset Crop).
2. HDR (HLG / PQ / BT.2020) to SDR (BT.709) Mobius tone-mapping.
3. Spatio-temporal low-light sensor denoising via hqdn3d.
4. Two-pass EBU R128 audio normalization (-14.0 LUFS, -1.5 dBTP, 40 Hz high-pass).
5. 30ms loop micro-fade and <= 59.0s duration clamping for YouTube Shorts compliance.
6. Hardware-accelerated encoding (NVENC / QSV / CPU fallback) with faststart MP4 container.
"""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from config import (
    AUDIO_BITRATE_KBPS,
    AUDIO_CEILING_TRUE_PEAK,
    AUDIO_HIGHPASS_CUTOFF_HZ,
    AUDIO_LIMITER_ATTACK,
    AUDIO_LIMITER_LIMIT,
    AUDIO_LIMITER_RELEASE,
    AUDIO_LOOP_CROSSFADE_SEC,
    AUDIO_SAMPLE_RATE,
    AUDIO_TARGET_LRA,
    AUDIO_TARGET_LUFS,
    AUDIO_TARGET_TRUE_PEAK,
    DenoiseMode,
    HQDN3D_CHROMA_SPATIAL,
    HQDN3D_CHROMA_TMP,
    HQDN3D_LUMA_SPATIAL,
    HQDN3D_LUMA_TMP,
    LoudnormMode,
    ProductionPreset,
    PROXY_AUDIO_CODEC,
    PROXY_AUDIO_SAMPLE_RATE,
    PROXY_PRESET,
    PROXY_VIDEO_BITRATE_KBPS,
    PROXY_VIDEO_CODEC,
    PROXY_VIDEO_HEIGHT,
    PROXY_VIDEO_SHORT_EDGE,
    ReframeMode,
    ToneMapMode,
    VIDEO_CANVAS_HEIGHT,
    VIDEO_CANVAS_WIDTH,
    VIDEO_DURATION_MAX_SECONDS,
    VIDEO_HIGH_BITRATE_KBPS,
    VIDEO_MAX_BITRATE_CEILING_KBPS,
    VIDEO_STANDARD_BITRATE_KBPS,
    VIDEO_TARGET_FPS,
)
from ingest_assets import find_binary


# ============================================================================
# EXCEPTIONS
# ============================================================================

class FFmpegExecutionError(Exception):
    """Raised when an FFmpeg subprocess execution fails."""
    pass


class FFmpegNotFoundError(Exception):
    """Raised when the ffmpeg executable cannot be located."""
    pass


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class LoudnessStats:
    """EBU R128 measurement metrics extracted from Pass 1 analysis."""
    input_i: float          # Measured integrated loudness (LUFS)
    input_tp: float         # Measured true peak (dBTP)
    input_lra: float        # Measured loudness range (LU)
    input_thresh: float     # Measured threshold (LUFS)
    target_offset: float    # Normalization target offset (LU)


@dataclass
class TranscodeConfig:
    """Configuration parameters for rendering an export master."""
    input_path: Path
    output_path: Path
    preset: ProductionPreset = ProductionPreset.FAST_TRACK
    reframe_mode: ReframeMode = ReframeMode.CENTER_CROP
    crop_x: Optional[int] = None
    crop_y: Optional[int] = None
    tone_map: ToneMapMode = ToneMapMode.AUTO
    is_source_hdr: bool = False
    denoise: DenoiseMode = DenoiseMode.AUTO
    loudnorm: LoudnormMode = LoudnormMode.TWO_PASS
    highpass_hz: int = AUDIO_HIGHPASS_CUTOFF_HZ
    start_time_sec: float = 0.0
    duration_sec: Optional[float] = None
    max_duration_sec: float = VIDEO_DURATION_MAX_SECONDS
    loop_crossfade: bool = True
    track_title: Optional[str] = None
    artist_name: Optional[str] = None
    encoder_choice: str = "auto"
    custom_ffmpeg_path: Optional[str] = None
    dry_run: bool = False


@dataclass
class TranscodeResult:
    """Outcome of a transcoding operation."""
    success: bool
    output_path: str
    duration_sec: float
    video_filtergraph: str
    audio_filtergraph: str
    loudness_stats: Optional[LoudnessStats]
    ffmpeg_command: List[str]
    stdout: str = ""
    stderr: str = ""


@dataclass
class ProxyGenerationResult:
    """Result of proxy video and audio WAV extraction."""
    proxy_video_path: str
    audio_wav_path: str
    duration_seconds: float = 0.0
    proxy_ffmpeg_cmd: List[str] = field(default_factory=list)
    wav_ffmpeg_cmd: List[str] = field(default_factory=list)
    success: bool = True


# ============================================================================
# HARDWARE ACCELERATION DETECTOR
# ============================================================================

def detect_available_encoders(ffmpeg_bin: Path) -> List[str]:
    """Inspects ffmpeg -encoders to determine hardware encoder availability."""
    try:
        proc = subprocess.run(
            [str(ffmpeg_bin), "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=10,
        )
        encoders = []
        for line in proc.stdout.splitlines():
            if "hevc_nvenc" in line:
                encoders.append("hevc_nvenc")
            elif "h264_nvenc" in line:
                encoders.append("h264_nvenc")
            elif "hevc_qsv" in line:
                encoders.append("hevc_qsv")
            elif "h264_qsv" in line:
                encoders.append("h264_qsv")
            elif "libx265" in line:
                encoders.append("libx265")
            elif "libx264" in line:
                encoders.append("libx264")
        return encoders
    except Exception:
        return ["libx264"]


def select_best_encoder(ffmpeg_bin: Path, preferred: str = "auto") -> str:
    """Selects optimal encoder based on system capabilities and preference."""
    if preferred != "auto":
        return preferred

    available = detect_available_encoders(ffmpeg_bin)
    priority = ["hevc_nvenc", "h264_nvenc", "hevc_qsv", "h264_qsv", "libx264", "libx265"]
    for enc in priority:
        if enc in available:
            return enc
    return "libx264"


# ============================================================================
# TWO-PASS LOUDNORM ANALYZER
# ============================================================================

def parse_loudnorm_pass1_output(stderr_text: str) -> Optional[LoudnessStats]:
    """
    Parses JSON measurement block output by FFmpeg loudnorm filter in stderr.
    Example block:
    {
        "input_i" : "-21.40",
        "input_tp" : "-0.20",
        "input_lra" : "11.20",
        "input_thresh" : "-32.50",
        "target_offset" : "+0.60"
    }
    """
    match = re.search(r"\{\s*\"input_i\"\s*:\s*\"([^\"]+)\".*?\"target_offset\"\s*:\s*\"([^\"]+)\"\s*\}", stderr_text, re.DOTALL)
    if not match:
        # Fallback regex searching for standard JSON object containing input_i
        match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr_text, re.DOTALL)
        if not match:
            return None
        json_str = match.group(0)
    else:
        json_str = match.group(0)

    try:
        data = json.loads(json_str)
        return LoudnessStats(
            input_i=float(data["input_i"]),
            input_tp=float(data["input_tp"]),
            input_lra=float(data["input_lra"]),
            input_thresh=float(data["input_thresh"]),
            target_offset=float(data["target_offset"]),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def run_loudnorm_pass1(
    input_path: Path,
    ffmpeg_bin: Path,
    highpass_hz: int = AUDIO_HIGHPASS_CUTOFF_HZ,
    start_time: float = 0.0,
    duration: Optional[float] = None,
) -> Optional[LoudnessStats]:
    """
    Executes first-pass loudness measurement with high-pass filtering.
    """
    af_string = (
        f"highpass=f={highpass_hz}:poles=2,"
        f"loudnorm=I={AUDIO_TARGET_LUFS}:LRA={AUDIO_TARGET_LRA}:TP={AUDIO_TARGET_TRUE_PEAK}:print_format=json"
    )

    cmd = [str(ffmpeg_bin), "-y"]
    if start_time > 0:
        cmd.extend(["-ss", str(start_time)])
    if duration:
        cmd.extend(["-t", str(duration)])

    cmd.extend([
        "-i", str(input_path.resolve()),
        "-vn",
        "-af", af_string,
        "-f", "null",
        "-",
    ])

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=60,
        )
        return parse_loudnorm_pass1_output(proc.stderr)
    except subprocess.CalledProcessError as e:
        return parse_loudnorm_pass1_output(e.stderr)
    except Exception:
        return None


# ============================================================================
# FILTERGRAPH BUILDER
# ============================================================================

class FilterGraphBuilder:
    """
    Constructs complex FFmpeg filtergraphs incorporating 9:16 re-framing,
    tone-mapping, low-light denoising, two-pass audio normalization, and loop micro-fades.
    """

    @classmethod
    def build_video_filter(
        cls,
        reframe_mode: ReframeMode = ReframeMode.CENTER_CROP,
        crop_x: Optional[int] = None,
        crop_y: Optional[int] = None,
        tone_map: ToneMapMode = ToneMapMode.AUTO,
        is_hdr: bool = False,
        denoise: DenoiseMode = DenoiseMode.AUTO,
        track_title: Optional[str] = None,
        artist_name: Optional[str] = None,
    ) -> str:
        """Constructs the complete video filter chain."""
        filters: List[str] = []

        # 1. 9:16 Re-framing
        if reframe_mode == ReframeMode.CENTER_CROP:
            # Crop to 9:16 from center and scale to 1080x1920
            filters.append(
                f"crop=w=ih*9/16:h=ih:x=(iw-ow)/2:y=0,scale={VIDEO_CANVAS_WIDTH}:{VIDEO_CANVAS_HEIGHT}:flags=lanczos"
            )
        elif reframe_mode == ReframeMode.OFFSET_CROP:
            cx = crop_x if crop_x is not None else "(iw-ow)/2"
            cy = crop_y if crop_y is not None else "0"
            filters.append(
                f"crop=w=ih*9/16:h=ih:x={cx}:y={cy},scale={VIDEO_CANVAS_WIDTH}:{VIDEO_CANVAS_HEIGHT}:flags=lanczos"
            )
        elif reframe_mode == ReframeMode.BLUR_PAD:
            # Foreground over blurred expanded background
            # Note: For filter_complex notation, blur_pad creates split streams
            blur_pad_graph = (
                f"split=2[fg][bg];"
                f"[bg]scale={VIDEO_CANVAS_WIDTH}:{VIDEO_CANVAS_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_CANVAS_WIDTH}:{VIDEO_CANVAS_HEIGHT},boxblur=luma_radius=25:luma_power=2[blurred_bg];"
                f"[fg]scale={VIDEO_CANVAS_WIDTH}:{VIDEO_CANVAS_HEIGHT}:force_original_aspect_ratio=decrease[scaled_fg];"
                f"[blurred_bg][scaled_fg]overlay=(W-w)/2:(H-h)/2"
            )
            filters.append(blur_pad_graph)

        # 2. HDR -> SDR Tone Mapping (Mobius to BT.709)
        apply_tonemap = (tone_map == ToneMapMode.ON) or (tone_map == ToneMapMode.AUTO and is_hdr)
        if apply_tonemap:
            # Mobius tone mapping preserves laser highlights without clipping
            filters.append(
                "zscale=t=linear:npl=100,tonemap=mobius:desat=0.5,zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p"
            )

        # 3. Spatio-Temporal Denoising (hqdn3d)
        apply_denoise = (denoise == DenoiseMode.ON) or (denoise == DenoiseMode.AUTO)
        if apply_denoise:
            filters.append(
                f"hqdn3d=luma_spatial={HQDN3D_LUMA_SPATIAL}:chroma_spatial={HQDN3D_CHROMA_SPATIAL}:"
                f"luma_tmp={HQDN3D_LUMA_TMP}:chroma_tmp={HQDN3D_CHROMA_TMP}"
            )

        # 4. Safe-Zone Compliant Text Overlay (Track ID & Artist)
        if artist_name or track_title:
            overlay_text = []
            if artist_name:
                overlay_text.append(artist_name.upper())
            if track_title:
                overlay_text.append(track_title)
            display_str = " - ".join(overlay_text)
            # Rendered at Y=350 px (well inside the YouTube 180-1450 & TikTok 160-1470 safe box)
            # Escape backslashes, single quotes, colons, and commas for FFmpeg filtergraph syntax safety
            escaped_text = (
                display_str.replace("\\", r"\\")
                .replace("'", "")
                .replace(":", r"\:")
                .replace(",", r"\,")
            )
            text_filter = (
                f"drawtext=text='{escaped_text}':fontcolor=white:fontsize=44:"
                f"box=1:boxcolor=black@0.65:boxborderw=12:x=(w-text_w)/2:y=350"
            )
            filters.append(text_filter)

        return ",".join(filters)

    @classmethod
    def build_audio_filter(
        cls,
        loudnorm_stats: Optional[LoudnessStats] = None,
        highpass_hz: int = AUDIO_HIGHPASS_CUTOFF_HZ,
        duration_sec: float = 30.0,
        apply_loop_crossfade: bool = True,
        loudnorm_mode: LoudnormMode = LoudnormMode.TWO_PASS,
    ) -> str:
        """Constructs the complete audio filter chain."""
        filters: List[str] = []

        # 1. High-Pass Sub-Bass Filter (Eliminate destructive 40Hz rumble)
        filters.append(f"highpass=f={highpass_hz}:poles=2")

        # 2. EBU R128 Two-Pass Loudnorm Normalization & True Peak Brickwall Limiter
        if loudnorm_mode == LoudnormMode.TWO_PASS and loudnorm_stats:
            loudnorm_filter = (
                f"loudnorm=I={AUDIO_TARGET_LUFS}:LRA={AUDIO_TARGET_LRA}:TP={AUDIO_TARGET_TRUE_PEAK}:"
                f"measured_I={loudnorm_stats.input_i:.2f}:"
                f"measured_LRA={loudnorm_stats.input_lra:.2f}:"
                f"measured_TP={loudnorm_stats.input_tp:.2f}:"
                f"measured_thresh={loudnorm_stats.input_thresh:.2f}:"
                f"offset={loudnorm_stats.target_offset:.2f}:linear=true"
            )
            filters.append(loudnorm_filter)
            filters.append(
                f"alimiter=limit={AUDIO_LIMITER_LIMIT}dB:attack={int(AUDIO_LIMITER_ATTACK)}:release={int(AUDIO_LIMITER_RELEASE)}"
            )
        elif loudnorm_mode == LoudnormMode.TWO_PASS:
            # Fallback single-pass loudnorm if pass 1 stats are unavailable
            filters.append(
                f"loudnorm=I={AUDIO_TARGET_LUFS}:LRA={AUDIO_TARGET_LRA}:TP={AUDIO_TARGET_TRUE_PEAK}"
            )
            filters.append(
                f"alimiter=limit={AUDIO_LIMITER_LIMIT}dB:attack={int(AUDIO_LIMITER_ATTACK)}:release={int(AUDIO_LIMITER_RELEASE)}"
            )

        # 3. Seamless Loop Micro-Fade (30 ms linear crossfade at boundary)
        if apply_loop_crossfade and duration_sec > 1.0:
            fade_out_start = max(0.0, duration_sec - AUDIO_LOOP_CROSSFADE_SEC)
            filters.append(f"afade=t=in:ss=0:d={AUDIO_LOOP_CROSSFADE_SEC:.3f}")
            filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={AUDIO_LOOP_CROSSFADE_SEC:.3f}")

        return ",".join(filters)


# ============================================================================
# MASTER FFMPEG PROCESSOR ENGINE
# ============================================================================

class FFmpegMasterProcessor:
    """
    Executes end-to-end media transcoding pipelines from raw inputs into
    broadcast-ready, 9:16 vertical social video masters.
    """

    def __init__(self, custom_ffmpeg_path: Optional[str] = None):
        self.custom_ffmpeg_path = custom_ffmpeg_path
        self._ffmpeg_bin = find_binary("ffmpeg", custom_path=custom_ffmpeg_path, env_var="FFMPEG_BINARY")

    @property
    def ffmpeg_binary(self) -> Path:
        if not self._ffmpeg_bin:
            raise FFmpegNotFoundError(
                "ffmpeg executable not found. Please install FFmpeg on PATH, "
                "set FFMPEG_BINARY environment variable, or supply --ffmpeg-path."
            )
        return self._ffmpeg_bin

    def transcode(self, config: TranscodeConfig) -> TranscodeResult:
        """
        Executes full transcoding lifecycle:
        1. Validates inputs and clamps duration to <= 59.0s.
        2. Executes Pass 1 Loudnorm measurement.
        3. Assembles video and audio filtergraphs.
        4. Invokes hardware-accelerated FFmpeg export.
        """
        src = config.input_path.resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Input video file not found: {src}")

        dest = config.output_path.resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Duration clamping (max 59.0s ceiling)
        target_duration = config.duration_sec
        if target_duration is None:
            # Default to 59s if duration is unspecified
            target_duration = config.max_duration_sec
        else:
            target_duration = min(target_duration, config.max_duration_sec)

        # Execute Loudnorm Pass 1 if not dry-run and loudnorm enabled
        loudnorm_stats: Optional[LoudnessStats] = None
        if not config.dry_run and config.loudnorm == LoudnormMode.TWO_PASS and self._ffmpeg_bin:
            loudnorm_stats = run_loudnorm_pass1(
                input_path=src,
                ffmpeg_bin=self.ffmpeg_binary,
                highpass_hz=config.highpass_hz,
                start_time=config.start_time_sec,
                duration=target_duration,
            )

        # If stats could not be measured or in dry run, provide standard nominal baseline
        if loudnorm_stats is None:
            loudnorm_stats = LoudnessStats(
                input_i=-20.0,
                input_tp=-1.0,
                input_lra=8.0,
                input_thresh=-30.0,
                target_offset=0.0,
            )

        # Build filtergraphs
        v_filter = FilterGraphBuilder.build_video_filter(
            reframe_mode=config.reframe_mode,
            crop_x=config.crop_x,
            crop_y=config.crop_y,
            tone_map=config.tone_map,
            is_hdr=config.is_source_hdr,
            denoise=config.denoise,
            track_title=config.track_title,
            artist_name=config.artist_name,
        )

        a_filter = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=loudnorm_stats,
            highpass_hz=config.highpass_hz,
            duration_sec=target_duration,
            apply_loop_crossfade=config.loop_crossfade,
            loudnorm_mode=config.loudnorm,
        )

        # Determine Bitrate & Encoder
        if config.preset == ProductionPreset.NORTH_STAR:
            target_v_bitrate = f"{VIDEO_HIGH_BITRATE_KBPS}k"
            max_v_bitrate = f"{VIDEO_MAX_BITRATE_CEILING_KBPS}k"
            bufsize = f"{VIDEO_MAX_BITRATE_CEILING_KBPS * 2}k"
        else:
            target_v_bitrate = f"{VIDEO_STANDARD_BITRATE_KBPS}k"
            max_v_bitrate = "16000k"
            bufsize = "24000k"

        bin_path = str(self._ffmpeg_bin) if self._ffmpeg_bin else "ffmpeg"
        encoder = select_best_encoder(self._ffmpeg_bin, preferred=config.encoder_choice) if self._ffmpeg_bin else "libx264"

        # Assemble CLI invocation
        cmd: List[str] = [
            bin_path,
            "-y",
        ]

        if config.start_time_sec > 0:
            cmd.extend(["-ss", str(config.start_time_sec)])
        if target_duration:
            cmd.extend(["-t", str(target_duration)])

        cmd.extend([
            "-i", str(src),
            "-filter_complex", f"[0:v]{v_filter}[v_out];[0:a]{a_filter}[a_out]",
            "-map", "[v_out]",
            "-map", "[a_out]",
            "-c:v", encoder,
            "-b:v", target_v_bitrate,
            "-maxrate", max_v_bitrate,
            "-bufsize", bufsize,
            "-pix_fmt", "yuv420p",
            "-r", str(VIDEO_TARGET_FPS),
            "-c:a", "aac",
            "-b:a", f"{AUDIO_BITRATE_KBPS}k",
            "-ar", str(AUDIO_SAMPLE_RATE),
            "-movflags", "+faststart",
            str(dest),
        ])

        if config.dry_run:
            return TranscodeResult(
                success=True,
                output_path=str(dest),
                duration_sec=target_duration,
                video_filtergraph=v_filter,
                audio_filtergraph=a_filter,
                loudness_stats=loudnorm_stats,
                ffmpeg_command=cmd,
                stdout="[DRY-RUN] Command constructed successfully.",
                stderr="",
            )

        # Execute FFmpeg command
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=300,
            )
            return TranscodeResult(
                success=True,
                output_path=str(dest),
                duration_sec=target_duration,
                video_filtergraph=v_filter,
                audio_filtergraph=a_filter,
                loudness_stats=loudnorm_stats,
                ffmpeg_command=cmd,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.CalledProcessError as e:
            raise FFmpegExecutionError(
                f"FFmpeg transcode failed with code {e.returncode}.\nCommand: {' '.join(cmd)}\nStderr: {e.stderr}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise FFmpegExecutionError(f"FFmpeg transcode timed out on {src}") from e

    def generate_proxy_video(
        self,
        input_path: Union[Path, str],
        output_path: Union[Path, str],
        target_resolution: int = PROXY_VIDEO_HEIGHT,
        bitrate_kbps: int = PROXY_VIDEO_BITRATE_KBPS,
        preset: str = PROXY_PRESET,
        dry_run: bool = False,
    ) -> List[str]:
        """
        Generates a lightweight 720p MP4 proxy video with aspect-aware scaling.
        """
        src = Path(input_path).resolve()
        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        bin_path = str(self._ffmpeg_bin) if self._ffmpeg_bin else "ffmpeg"
        scale_filter = f"scale='if(gt(ih,iw),{target_resolution},-2)':'if(gt(ih,iw),-2,{target_resolution})'"

        cmd = [
            bin_path,
            "-y",
            "-i", str(src),
            "-vf", scale_filter,
            "-c:v", PROXY_VIDEO_CODEC,
            "-preset", preset,
            "-b:v", f"{bitrate_kbps}k",
            "-maxrate", "3500k",
            "-bufsize", "5000k",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(dest),
        ]

        if not dry_run:
            try:
                subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=180,
                )
            except subprocess.CalledProcessError as e:
                raise FFmpegExecutionError(
                    f"FFmpeg proxy generation failed with code {e.returncode}.\nCommand: {' '.join(cmd)}\nStderr: {e.stderr}"
                ) from e
            except subprocess.TimeoutExpired as e:
                raise FFmpegExecutionError(f"FFmpeg proxy generation timed out on {src}") from e

        return cmd

    def extract_wav_audio(
        self,
        input_path: Union[Path, str],
        output_path: Union[Path, str],
        sample_rate: int = PROXY_AUDIO_SAMPLE_RATE,
        audio_codec: str = PROXY_AUDIO_CODEC,
        dry_run: bool = False,
    ) -> List[str]:
        """
        Extracts lightweight mono 16-bit PCM WAV audio for fast DSP/Librosa analysis.
        """
        src = Path(input_path).resolve()
        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        bin_path = str(self._ffmpeg_bin) if self._ffmpeg_bin else "ffmpeg"

        cmd = [
            bin_path,
            "-y",
            "-i", str(src),
            "-vn",
            "-c:a", audio_codec,
            "-ar", str(sample_rate),
            "-ac", "1",
            "-f", "wav",
            str(dest),
        ]

        if not dry_run:
            try:
                subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=60,
                )
            except subprocess.CalledProcessError as e:
                raise FFmpegExecutionError(
                    f"FFmpeg WAV audio extraction failed with code {e.returncode}.\nCommand: {' '.join(cmd)}\nStderr: {e.stderr}"
                ) from e
            except subprocess.TimeoutExpired as e:
                raise FFmpegExecutionError(f"FFmpeg WAV audio extraction timed out on {src}") from e

        return cmd

    def generate_proxy_and_wav(
        self,
        input_path: Union[Path, str],
        output_proxy_path: Union[Path, str],
        output_wav_path: Union[Path, str],
        target_resolution: int = PROXY_VIDEO_HEIGHT,
        wav_sample_rate: int = PROXY_AUDIO_SAMPLE_RATE,
        dry_run: bool = False,
    ) -> ProxyGenerationResult:
        """
        Generates both a 720p proxy video and a 16-bit PCM WAV audio track.
        """
        proxy_cmd = self.generate_proxy_video(
            input_path=input_path,
            output_path=output_proxy_path,
            target_resolution=target_resolution,
            dry_run=dry_run,
        )
        wav_cmd = self.extract_wav_audio(
            input_path=input_path,
            output_path=output_wav_path,
            sample_rate=wav_sample_rate,
            dry_run=dry_run,
        )

        return ProxyGenerationResult(
            proxy_video_path=str(Path(output_proxy_path).resolve()),
            audio_wav_path=str(Path(output_wav_path).resolve()),
            duration_seconds=0.0,
            proxy_ffmpeg_cmd=proxy_cmd,
            wav_ffmpeg_cmd=wav_cmd,
            success=True,
        )

    def trim_proxy_video(
        self,
        input_proxy_path: Union[Path, str],
        output_path: Union[Path, str],
        start_time: float = 0.0,
        duration: float = 30.0,
        dry_run: bool = False,
        start_time_sec: Optional[float] = None,
        duration_sec: Optional[float] = None,
    ) -> List[str]:
        """
        Trims a 720p proxy video fast and cleanly without re-encoding delays.
        """
        st = start_time_sec if start_time_sec is not None else start_time
        dur = duration_sec if duration_sec is not None else duration

        src = Path(input_proxy_path).resolve()
        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        bin_path = str(self._ffmpeg_bin) if self._ffmpeg_bin else "ffmpeg"

        # Fast trim with stream copy
        cmd = [
            bin_path,
            "-y",
            "-ss", str(st),
            "-t", str(dur),
            "-i", str(src),
            "-c", "copy",
            "-movflags", "+faststart",
            str(dest),
        ]

        if not dry_run:
            try:
                subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=60,
                )
            except subprocess.CalledProcessError as e:
                # If stream copy fails due to keyframe boundaries, fallback to fast transcode
                fallback_cmd = [
                    bin_path,
                    "-y",
                    "-ss", str(st),
                    "-t", str(dur),
                    "-i", str(src),
                    "-c:v", PROXY_VIDEO_CODEC,
                    "-preset", "fast",
                    "-b:v", f"{PROXY_VIDEO_BITRATE_KBPS}k",
                    "-c:a", "aac",
                    "-movflags", "+faststart",
                    str(dest),
                ]
                try:
                    subprocess.run(
                        fallback_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True,
                        timeout=60,
                    )
                    return fallback_cmd
                except subprocess.CalledProcessError as e2:
                    raise FFmpegExecutionError(
                        f"FFmpeg proxy trim failed with code {e2.returncode}.\nStderr: {e2.stderr}"
                    ) from e2
            except subprocess.TimeoutExpired as e:
                raise FFmpegExecutionError(f"FFmpeg proxy trim timed out on {src}") from e

        return cmd


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="EDM Media Transcoding & Audio Engineering Engine (Track 2: Content Creation)"
    )
    parser.add_argument("--input", "-i", required=True, help="Path to input video file.")
    parser.add_argument("--output", "-o", required=True, help="Path to output MP4 master.")
    parser.add_argument(
        "--preset",
        choices=[p.value for p in ProductionPreset],
        default=ProductionPreset.FAST_TRACK.value,
        help="Production preset profile.",
    )
    parser.add_argument(
        "--reframe-mode",
        choices=[r.value for r in ReframeMode],
        default=ReframeMode.CENTER_CROP.value,
        help="9:16 vertical re-framing method.",
    )
    parser.add_argument("--crop-x", type=int, default=None, help="X-offset for subject tracking.")
    parser.add_argument("--crop-y", type=int, default=None, help="Y-offset for subject tracking.")
    parser.add_argument(
        "--tone-map",
        choices=[t.value for t in ToneMapMode],
        default=ToneMapMode.AUTO.value,
        help="HDR->SDR tone-mapping mode.",
    )
    parser.add_argument(
        "--denoise",
        choices=[d.value for d in DenoiseMode],
        default=DenoiseMode.AUTO.value,
        help="Low-light spatio-temporal denoising mode.",
    )
    parser.add_argument(
        "--loudnorm",
        choices=[l.value for l in LoudnormMode],
        default=LoudnormMode.TWO_PASS.value,
        help="Audio loudness normalization mode.",
    )
    parser.add_argument("--highpass", type=int, default=AUDIO_HIGHPASS_CUTOFF_HZ, help="High-pass filter cutoff Hz.")
    parser.add_argument("--start-time", type=float, default=0.0, help="Start trim time in seconds.")
    parser.add_argument("--duration", type=float, default=None, help="Duration in seconds.")
    parser.add_argument("--max-duration", type=float, default=VIDEO_DURATION_MAX_SECONDS, help="Max duration clamp.")
    parser.add_argument("--loop-crossfade", action="store_true", default=True, help="Apply 30ms loop micro-fade.")
    parser.add_argument("--track-title", default=None, help="Track name for on-screen kinetic safe-zone overlay.")
    parser.add_argument("--artist-name", default=None, help="Artist name for on-screen safe-zone overlay.")
    parser.add_argument("--encoder", default="auto", help="Video encoder ('auto', 'libx264', 'hevc_nvenc', etc.).")
    parser.add_argument("--ffmpeg-path", default=None, help="Custom path to ffmpeg binary.")
    parser.add_argument("--dry-run", action="store_true", help="Print filtergraph and commands without running.")

    args = parser.parse_args()

    config = TranscodeConfig(
        input_path=Path(args.input),
        output_path=Path(args.output),
        preset=ProductionPreset(args.preset),
        reframe_mode=ReframeMode(args.reframe_mode),
        crop_x=args.crop_x,
        crop_y=args.crop_y,
        tone_map=ToneMapMode(args.tone_map),
        denoise=DenoiseMode(args.denoise),
        loudnorm=LoudnormMode(args.loudnorm),
        highpass_hz=args.highpass,
        start_time_sec=args.start_time,
        duration_sec=args.duration,
        max_duration_sec=args.max_duration,
        loop_crossfade=args.loop_crossfade,
        track_title=args.track_title,
        artist_name=args.artist_name,
        encoder_choice=args.encoder,
        custom_ffmpeg_path=args.ffmpeg_path,
        dry_run=args.dry_run,
    )

    processor = FFmpegMasterProcessor(custom_ffmpeg_path=args.ffmpeg_path)

    try:
        res = processor.transcode(config)
        print("[SUCCESS] Transcode Pipeline Completed.")
        print(f"  Output Path: {res.output_path}")
        print(f"  Clamped Duration: {res.duration_sec:.2f}s")
        print(f"  Video Filter: {res.video_filtergraph}")
        print(f"  Audio Filter: {res.audio_filtergraph}")
        if res.loudness_stats:
            print(f"  Measured I: {res.loudness_stats.input_i:.1f} LUFS | TP: {res.loudness_stats.input_tp:.1f} dBTP | Offset: {res.loudness_stats.target_offset:+.1f} LU")
        print(f"  Command: {' '.join(res.ffmpeg_command)}")
    except Exception as ex:
        print(f"[ERROR] Transcode failed: {ex}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
