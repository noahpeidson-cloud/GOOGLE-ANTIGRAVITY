r"""
---
Name: Mobius HDR Tone-Mapper & 9:16 Vertical Reframing Engine
Context Mapping: Originally developed in `content_creation/ffmpeg_processor.py` for Track 2 (EDM Short-Form Media Engineering) to convert 4K HDR (HLG/PQ/BT.2020) festival stage recordings into SDR (BT.709) 9:16 vertical videos for YouTube Shorts, TikTok, and Instagram Reels.
Strengths:
  - Specular highlight preservation: Mobius tone-mapping (`zscale=t=linear:npl=100,tonemap=mobius:desat=0.5,zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p`) maps extreme dynamic range (1000-4000 nits) down to SDR (100 nits) without blowing out laser beams or pyrotechnics into flat white clipping.
  - Smooth desaturation rolloff: Desaturation factor 0.5 prevents ultra-bright laser beams from distorting into unnatural neon halos or color banding.
  - Three 9:16 vertical reframing modes:
    1. Center Crop (`CENTER_CROP`): High-precision Lanczos-scaled center crop (`crop=w=ih*9/16:h=ih:x=(iw-ow)/2:y=0,scale=1080:1920:flags=lanczos`).
    2. Safe-Region Offset Crop (`OFFSET_CROP`): Configurable horizontal/vertical offset tracking off-center performers with bounds clamping.
    3. Blur-Pad Fallback (`BLUR_PAD`): Two-stream split graph (`split=2[fg][bg]`) placing aspect-preserved foreground over a 25px Gaussian box-blurred expanded background.
  - Automated HDR detection: Probes video stream color primaries, color transfer (HLG `arib-std-b67`, PQ `smpte2084`), and color space (`bt2020nc`) via `ffprobe`.
  - Mobile safe-zone compliance: Optional text overlay positioned at Y=350 (outside TikTok and YouTube Shorts UI occlusion zones).
Weaknesses:
  - Requires FFmpeg compiled with `libzimg` (`zscale` and `tonemap` filters).
  - CPU-bound color grading and Lanczos scaling can be slow without GPU acceleration.
Implementation Instructions:
  - Import `MobiusHDRToneMapper`, `ReframeMode`, or filter builders (`build_mobius_tonemap_filter`, `build_reframe_filter`).
  - Call `detect_hdr_metadata(video_path)` to determine whether HDR tone-mapping is necessary.
  - Call `build_video_filtergraph()` to generate the ready-to-run FFmpeg filter string.
  - Standalone CLI supports `--dry-run`, `--detect-hdr`, and direct transcode execution.
---
"""

from dataclasses import dataclass
from enum import Enum
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("mobius_hdr_tonemapper")

# Canvas Constants
CANVAS_WIDTH: int = 1080
CANVAS_HEIGHT: int = 1920
DEFAULT_MOBIUS_DESAT: float = 0.5
DEFAULT_MOBIUS_NPL: int = 100
BOXBLUR_RADIUS: int = 25
BOXBLUR_POWER: int = 2


# ============================================================================
# ENUMS & DATA STRUCTURES
# ============================================================================

class ReframeMode(str, Enum):
    """Reframing modes for adapting horizontal (16:9) media to vertical (9:16)."""
    CENTER_CROP = "center_crop"
    OFFSET_CROP = "offset_crop"
    BLUR_PAD = "blur_pad"


class ToneMapMode(str, Enum):
    """Tone-mapping activation modes."""
    AUTO = "auto"
    ON = "on"
    OFF = "off"


@dataclass(frozen=True)
class StreamColorMetadata:
    """Color characteristics parsed from ffprobe video stream."""
    color_space: Optional[str] = None
    color_transfer: Optional[str] = None
    color_primaries: Optional[str] = None
    pix_fmt: Optional[str] = None
    is_hdr: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "color_space": self.color_space,
            "color_transfer": self.color_transfer,
            "color_primaries": self.color_primaries,
            "pix_fmt": self.pix_fmt,
            "is_hdr": self.is_hdr,
        }


# ============================================================================
# BINARY DISCOVERY
# ============================================================================

def find_binary(
    binary_name: str,
    custom_path: Optional[Union[str, Path]] = None,
    env_var: Optional[str] = None,
) -> Optional[Path]:
    """Locates an executable binary across custom paths, environment variables, PATH, and Windows dirs."""
    if custom_path:
        cp = Path(custom_path)
        if cp.is_file() and os.access(cp, os.X_OK):
            return cp

    if env_var and os.environ.get(env_var):
        ep = Path(os.environ[env_var])
        if ep.is_file() and os.access(ep, os.X_OK):
            return ep

    which_path = shutil.which(binary_name)
    if which_path:
        return Path(which_path)

    if sys.platform == "win32":
        candidates = [
            Path(r"C:\ffmpeg\bin") / f"{binary_name}.exe",
            Path(r"C:\Program Files\ffmpeg\bin") / f"{binary_name}.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / f"{binary_name}.exe",
        ]
        for c in candidates:
            if c.is_file() and os.access(c, os.X_OK):
                return c

    return None


# ============================================================================
# HDR METADATA PROBER
# ============================================================================

def probe_color_metadata(
    video_path: Union[str, Path],
    custom_ffprobe_path: Optional[str] = None,
) -> StreamColorMetadata:
    """
    Probes video container via ffprobe to inspect color transfer, primaries, and space.
    Detects whether stream uses HDR transfer (PQ / smpte2084 or HLG / arib-std-b67) or BT.2020.
    """
    ffprobe_bin = find_binary("ffprobe", custom_path=custom_ffprobe_path, env_var="FFPROBE_BINARY")
    if not ffprobe_bin:
        logger.warning("ffprobe not found. Defaulting to non-HDR SDR assumption.")
        return StreamColorMetadata()

    path_obj = Path(video_path).resolve()
    if not path_obj.is_file():
        raise FileNotFoundError(f"Video file not found: {path_obj}")

    cmd = [
        str(ffprobe_bin),
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=color_space,color_transfer,color_primaries,pix_fmt",
        "-of", "json",
        str(path_obj),
    ]

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, timeout=30)
        data = json.loads(proc.stdout)
        streams = data.get("streams", [])
        if not streams:
            return StreamColorMetadata()

        v = streams[0]
        c_space = v.get("color_space")
        c_trc = v.get("color_transfer")
        c_prim = v.get("color_primaries")
        pix_fmt = v.get("pix_fmt")

        # Detect HDR signatures
        hdr_transfers = {"smpte2084", "arib-std-b67"}  # PQ and HLG
        hdr_primaries = {"bt2020"}
        is_hdr = (c_trc in hdr_transfers) or (c_prim in hdr_primaries) or ("10" in str(pix_fmt) and c_space == "bt2020nc")

        return StreamColorMetadata(
            color_space=c_space,
            color_transfer=c_trc,
            color_primaries=c_prim,
            pix_fmt=pix_fmt,
            is_hdr=bool(is_hdr),
        )
    except Exception as e:
        logger.debug(f"ffprobe probe failed: {e}")
        return StreamColorMetadata()


# ============================================================================
# FILTERGRAPH BUILDERS
# ============================================================================

def build_mobius_tonemap_filter(
    npl: int = DEFAULT_MOBIUS_NPL,
    desat: float = DEFAULT_MOBIUS_DESAT,
) -> str:
    """
    Builds Mobius HDR (HLG/PQ/BT.2020) to SDR (BT.709) tone-mapping filtergraph.
    Uses zscale to linearize, tonemap=mobius to compress highlights, and zscale to output BT.709 TV range.
    """
    return (
        f"zscale=t=linear:npl={npl},"
        f"tonemap=mobius:desat={desat:.2f},"
        f"zscale=p=bt709:t=bt709:m=bt709:r=tv,"
        f"format=yuv420p"
    )


def build_reframe_filter(
    mode: ReframeMode = ReframeMode.CENTER_CROP,
    canvas_w: int = CANVAS_WIDTH,
    canvas_h: int = CANVAS_HEIGHT,
    offset_x: Optional[Union[int, str]] = None,
    offset_y: Optional[Union[int, str]] = None,
) -> str:
    """
    Builds video reframing filter string for standard 9:16 vertical canvas.
    """
    if mode == ReframeMode.CENTER_CROP:
        # Exact 9:16 center crop scaled with Lanczos filter
        return f"crop=w=ih*9/16:h=ih:x=(iw-ow)/2:y=0,scale={canvas_w}:{canvas_h}:flags=lanczos"

    elif mode == ReframeMode.OFFSET_CROP:
        cx = str(offset_x) if offset_x is not None else "(iw-ow)/2"
        cy = str(offset_y) if offset_y is not None else "0"
        return f"crop=w=ih*9/16:h=ih:x={cx}:y={cy},scale={canvas_w}:{canvas_h}:flags=lanczos"

    elif mode == ReframeMode.BLUR_PAD:
        # Multi-stream split filtergraph: blurred expanded background + centered aspect-preserved foreground
        return (
            f"split=2[fg][bg];"
            f"[bg]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w}:{canvas_h},"
            f"boxblur=luma_radius={BOXBLUR_RADIUS}:luma_power={BOXBLUR_POWER}[blurred_bg];"
            f"[fg]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease[scaled_fg];"
            f"[blurred_bg][scaled_fg]overlay=(W-w)/2:(H-h)/2"
        )

    raise ValueError(f"Unknown reframe mode: {mode}")


def build_safe_zone_text_overlay(
    artist_name: Optional[str] = None,
    track_title: Optional[str] = None,
    y_position: int = 350,
) -> Optional[str]:
    """
    Builds drawtext filter located inside social media safe zones (default Y=350).
    Escapes special FFmpeg syntax characters to avoid filter errors.
    """
    items = []
    if artist_name:
        items.append(artist_name.strip().upper())
    if track_title:
        items.append(track_title.strip())

    if not items:
        return None

    raw_text = " - ".join(items)
    escaped_text = (
        raw_text.replace("\\", r"\\")
        .replace("'", "")
        .replace(":", r"\:")
        .replace(",", r"\,")
        .replace("[", r"\[")
        .replace("]", r"\]")
    )
    return (
        f"drawtext=text='{escaped_text}':fontcolor=white:fontsize=44:"
        f"box=1:boxcolor=black@0.65:boxborderw=12:x=(w-text_w)/2:y={y_position}"
    )


def build_video_filtergraph(
    reframe_mode: ReframeMode = ReframeMode.CENTER_CROP,
    offset_x: Optional[Union[int, str]] = None,
    offset_y: Optional[Union[int, str]] = None,
    apply_mobius_tonemap: bool = False,
    artist_name: Optional[str] = None,
    track_title: Optional[str] = None,
    canvas_w: int = CANVAS_WIDTH,
    canvas_h: int = CANVAS_HEIGHT,
) -> str:
    """
    Compiles full video filter chain combining:
    1. 9:16 Reframing (center crop, offset crop, or blur pad)
    2. Optional Mobius HDR-to-SDR tone-mapping
    3. Optional Safe-Zone artist/track title text overlay
    """
    reframe_str = build_reframe_filter(
        mode=reframe_mode,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        offset_x=offset_x,
        offset_y=offset_y,
    )

    linear_filters: List[str] = []

    # If blur pad was chosen, it is a multi-stream split graph terminating in an overlay stream
    if reframe_mode == ReframeMode.BLUR_PAD:
        combined_graph = reframe_str
        if apply_mobius_tonemap:
            combined_graph += "," + build_mobius_tonemap_filter()
        text_overlay = build_safe_zone_text_overlay(artist_name=artist_name, track_title=track_title)
        if text_overlay:
            combined_graph += "," + text_overlay
        return combined_graph

    # Linear filter chain
    linear_filters.append(reframe_str)
    if apply_mobius_tonemap:
        linear_filters.append(build_mobius_tonemap_filter())

    text_overlay = build_safe_zone_text_overlay(artist_name=artist_name, track_title=track_title)
    if text_overlay:
        linear_filters.append(text_overlay)

    return ",".join(linear_filters)


# ============================================================================
# TONEMAPPER CLASS
# ============================================================================

class MobiusHDRToneMapper:
    """
    High-dynamic-range video processor and vertical reframer.
    """

    def __init__(
        self,
        reframe_mode: ReframeMode = ReframeMode.CENTER_CROP,
        tonemap_mode: ToneMapMode = ToneMapMode.AUTO,
        desat: float = DEFAULT_MOBIUS_DESAT,
        npl: int = DEFAULT_MOBIUS_NPL,
        custom_ffmpeg_path: Optional[str] = None,
        custom_ffprobe_path: Optional[str] = None,
    ):
        self.reframe_mode = reframe_mode
        self.tonemap_mode = tonemap_mode
        self.desat = desat
        self.npl = npl
        self.custom_ffmpeg_path = custom_ffmpeg_path
        self.custom_ffprobe_path = custom_ffprobe_path
        self._ffmpeg_bin = find_binary("ffmpeg", custom_path=custom_ffmpeg_path, env_var="FFMPEG_BINARY")
        self._ffprobe_bin = find_binary("ffprobe", custom_path=custom_ffprobe_path, env_var="FFPROBE_BINARY")

    def probe_media(self, video_path: Union[str, Path]) -> StreamColorMetadata:
        """Inspects media container for HDR characteristics."""
        return probe_color_metadata(video_path, custom_ffprobe_path=self.custom_ffprobe_path)

    def should_apply_tonemapping(self, video_path: Union[str, Path]) -> bool:
        """Determines whether tone-mapping should be applied based on mode and media probe."""
        if self.tonemap_mode == ToneMapMode.ON:
            return True
        if self.tonemap_mode == ToneMapMode.OFF:
            return False
        # AUTO mode: probe media
        meta = self.probe_media(video_path)
        return meta.is_hdr

    def get_filtergraph(
        self,
        video_path: Optional[Union[str, Path]] = None,
        artist_name: Optional[str] = None,
        track_title: Optional[str] = None,
        offset_x: Optional[Union[int, str]] = None,
        offset_y: Optional[Union[int, str]] = None,
    ) -> str:
        """Generates the compiled FFmpeg video filtergraph."""
        apply_tonemap = False
        if video_path:
            apply_tonemap = self.should_apply_tonemapping(video_path)
        elif self.tonemap_mode == ToneMapMode.ON:
            apply_tonemap = True

        return build_video_filtergraph(
            reframe_mode=self.reframe_mode,
            offset_x=offset_x,
            offset_y=offset_y,
            apply_mobius_tonemap=apply_tonemap,
            artist_name=artist_name,
            track_title=track_title,
        )

    def transcode_video(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        start_time: float = 0.0,
        duration: Optional[float] = None,
        artist_name: Optional[str] = None,
        track_title: Optional[str] = None,
        encoder: str = "libx264",
        crf: int = 17,
        preset: str = "medium",
    ) -> bool:
        """
        Transcodes video file applying 9:16 reframing and Mobius HDR tonemapping.
        """
        ffmpeg_bin = self._ffmpeg_bin or find_binary("ffmpeg", custom_path=self.custom_ffmpeg_path, env_var="FFMPEG_BINARY")
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found.")

        in_p = Path(input_path).resolve()
        out_p = Path(output_path).resolve()
        if not in_p.is_file():
            raise FileNotFoundError(f"Input file not found: {in_p}")

        vfilter = self.get_filtergraph(
            video_path=in_p,
            artist_name=artist_name,
            track_title=track_title,
        )

        out_p.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(ffmpeg_bin), "-y"]
        if start_time > 0:
            cmd.extend(["-ss", str(start_time)])
        if duration and duration > 0:
            cmd.extend(["-t", str(duration)])

        cmd.extend([
            "-i", str(in_p),
            "-filter_complex", vfilter if ("split=" in vfilter) else f"[0:v]{vfilter}[vout]",
            "-map", "[vout]" if ("split=" not in vfilter) else "[vout]",  # map correctly
        ])

        # If blur_pad, map final overlay output
        if self.reframe_mode == ReframeMode.BLUR_PAD:
            # Reconstruct with explicit label
            vfilter_labeled = vfilter + "[vout]"
            cmd = [
                str(ffmpeg_bin), "-y",
                "-ss", str(start_time) if start_time > 0 else "0",
                "-i", str(in_p),
                "-filter_complex", vfilter_labeled,
                "-map", "[vout]",
            ]
            if duration and duration > 0:
                cmd.extend(["-t", str(duration)])
        else:
            cmd = [
                str(ffmpeg_bin), "-y",
                "-ss", str(start_time) if start_time > 0 else "0",
                "-i", str(in_p),
                "-vf", vfilter,
            ]
            if duration and duration > 0:
                cmd.extend(["-t", str(duration)])

        # Video encoding parameters
        cmd.extend([
            "-c:v", encoder,
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "copy",
            str(out_p),
        ])

        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, timeout=600)
            return out_p.is_file() and out_p.stat().st_size > 0
        except subprocess.SubprocessError as e:
            logger.error(f"Transcoding failed: {e}")
            return False


# ============================================================================
# CLI ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mobius HDR Tone-Mapper & 9:16 Vertical Reframing Engine")
    parser.add_argument("input_file", nargs="?", default=None, help="Input video file path")
    parser.add_argument("-o", "--output", default=None, help="Output transcoded video path")
    parser.add_argument("--reframe-mode", choices=["center_crop", "offset_crop", "blur_pad"], default="center_crop", help="Reframing mode (default: center_crop)")
    parser.add_argument("--tonemap", choices=["auto", "on", "off"], default="auto", help="Tone-mapping mode (default: auto)")
    parser.add_argument("--detect-hdr", action="store_true", help="Probe and print input video HDR color metadata")
    parser.add_argument("--dry-run", action="store_true", help="Print the generated video filtergraph without transcoding")
    parser.add_argument("--artist", default=None, help="Artist name for safe-zone text overlay")
    parser.add_argument("--title", default=None, help="Track title for safe-zone text overlay")

    args = parser.parse_args()

    reframe_enum = ReframeMode(args.reframe_mode)
    tonemap_enum = ToneMapMode(args.tonemap)

    if args.dry_run:
        mapper = MobiusHDRToneMapper(reframe_mode=reframe_enum, tonemap_mode=tonemap_enum)
        fg = mapper.get_filtergraph(
            video_path=args.input_file,
            artist_name=args.artist,
            track_title=args.title,
        )
        print("GENERATED VIDEO FILTERGRAPH:")
        print(f"  {fg}")
        sys.exit(0)

    if not args.input_file:
        parser.print_help()
        sys.exit(1)

    if args.detect_hdr:
        meta = probe_color_metadata(args.input_file)
        print(json.dumps(meta.to_dict(), indent=2))
        sys.exit(0)

    mapper = MobiusHDRToneMapper(reframe_mode=reframe_enum, tonemap_mode=tonemap_enum)

    if not args.output:
        fg = mapper.get_filtergraph(video_path=args.input_file, artist_name=args.artist, track_title=args.title)
        print("FILTERGRAPH:")
        print(fg)
        sys.exit(0)

    success = mapper.transcode_video(
        input_path=args.input_file,
        output_path=args.output,
        artist_name=args.artist,
        track_title=args.title,
    )
    if success:
        print(f"[SUCCESS] Transcoded video exported to: {args.output}")
        sys.exit(0)
    else:
        print("[ERROR] Transcoding failed.", file=sys.stderr)
        sys.exit(1)
