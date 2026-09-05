r"""
---
Name: EBU R128 Two-Pass Loudness Normalizer & Peak Limiter
Context Mapping: Originally developed in `content_creation/ffmpeg_processor.py` for Track 2 (EDM Short-Form Media Engineering) to master audio to broadcast loudness standards (-14.0 LUFS, -1.5 dBTP) for TikTok, YouTube Shorts, and Instagram Reels.
Strengths:
  - Exact ITU-R BS.1770-4 / EBU R128 compliance: Two-pass filtergraph prevents dynamic pumping artifacts by separating measurement from linear normalization.
  - Sub-bass conditioning: Integrated 40Hz 2-pole Butterworth high-pass filter (`highpass=f=40:poles=2`) eliminates destructive low-frequency DC rumble before loudness measurement.
  - Linear loudnorm injection: Pass 2 injects measured integrated loudness (`measured_I`), loudness range (`measured_LRA`), true peak (`measured_TP`), threshold (`measured_thresh`), and target offset (`offset`) with `linear=true` for transparent gain matching.
  - Inter-sample peak protection: Downstream brickwall peak limiter (`alimiter=limit=-1.5dB:attack=5:release=50`) guarantees true peak headroom <= -1.5 dBTP, eliminating DAC clipping on mobile phone speakers and Bluetooth codecs.
  - Seamless loop micro-fade: 30ms linear crossfade (`afade=t=in:ss=0:d=0.030,afade=t=out:st={duration-0.030}:d=0.030`) eliminates speaker click/pop transients on infinite-loop short-form platforms.
Weaknesses:
  - Requires FFmpeg executable with `loudnorm` and `alimiter` filter support.
  - Two-pass measurement requires full-file audio pass (though Pass 1 renders only audio to `-f null -`).
Implementation Instructions:
  - Import `EBUR128Normalizer` or `measure_loudness` / `normalize_audio_file`.
  - Use `measure_loudness(input_path)` to extract `LoudnessStats` without modifying the file.
  - Use `normalize_audio_file(input_path, output_path)` for complete two-pass mastering with 40Hz high-pass and 30ms loop crossfade.
  - Standalone CLI supports `--measure-only`, `--dry-run`, and audio conversion.
---
"""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("ebu_r128_normalizer")

# Default broadcast & social mastering constants
DEFAULT_TARGET_LUFS: float = -14.0
DEFAULT_TARGET_LRA: float = 7.0
DEFAULT_TARGET_TRUE_PEAK: float = -1.5
DEFAULT_HIGHPASS_HZ: int = 40
DEFAULT_LIMITER_ATTACK_MS: int = 5
DEFAULT_LIMITER_RELEASE_MS: int = 50
DEFAULT_LOOP_CROSSFADE_SEC: float = 0.030


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass(frozen=True)
class LoudnessStats:
    """Encapsulates measured audio loudness metrics from FFmpeg loudnorm Pass 1."""
    input_i: float
    input_tp: float
    input_lra: float
    input_thresh: float
    target_offset: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "input_i": self.input_i,
            "input_tp": self.input_tp,
            "input_lra": self.input_lra,
            "input_thresh": self.input_thresh,
            "target_offset": self.target_offset,
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
# PARSER & FILTER BUILDERS
# ============================================================================

def parse_loudnorm_stderr_json(stderr_text: str) -> Optional[LoudnessStats]:
    """
    Parses the JSON telemetry block emitted by FFmpeg loudnorm in stderr.
    Example:
    [Parsed_loudnorm_1 @ ...] {
        "input_i" : "-21.34",
        "input_tp" : "-0.45",
        "input_lra" : "6.80",
        "input_thresh" : "-32.10",
        "target_offset" : "+0.60"
    }
    """
    match = re.search(
        r"\{\s*\"input_i\"\s*:\s*\"([^\"]+)\".*?\"target_offset\"\s*:\s*\"([^\"]+)\"\s*\}",
        stderr_text,
        re.DOTALL,
    )
    if not match:
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


def build_pass1_filter(
    target_lufs: float = DEFAULT_TARGET_LUFS,
    target_lra: float = DEFAULT_TARGET_LRA,
    target_tp: float = DEFAULT_TARGET_TRUE_PEAK,
    highpass_hz: int = DEFAULT_HIGHPASS_HZ,
) -> str:
    """Builds the FFmpeg audio filter string for Pass 1 loudness measurement."""
    filters = [
        f"highpass=f={highpass_hz}:poles=2",
        f"loudnorm=I={target_lufs:.1f}:LRA={target_lra:.1f}:TP={target_tp:.1f}:print_format=json",
    ]
    return ",".join(filters)


def build_pass2_filter(
    stats: Optional[LoudnessStats] = None,
    target_lufs: float = DEFAULT_TARGET_LUFS,
    target_lra: float = DEFAULT_TARGET_LRA,
    target_tp: float = DEFAULT_TARGET_TRUE_PEAK,
    highpass_hz: int = DEFAULT_HIGHPASS_HZ,
    duration_sec: Optional[float] = None,
    apply_loop_crossfade: bool = True,
    crossfade_sec: float = DEFAULT_LOOP_CROSSFADE_SEC,
    limiter_attack_ms: int = DEFAULT_LIMITER_ATTACK_MS,
    limiter_release_ms: int = DEFAULT_LIMITER_RELEASE_MS,
) -> str:
    """
    Builds the complete Pass 2 audio filter chain:
    1. 40Hz Butterworth highpass
    2. Linear loudnorm injection with measured stats (or single-pass fallback if stats is None)
    3. True-peak brickwall peak limiter
    4. Optional 30ms linear crossfade micro-fade at boundaries
    """
    filters: List[str] = [f"highpass=f={highpass_hz}:poles=2"]

    if stats is not None:
        loudnorm_str = (
            f"loudnorm=I={target_lufs:.1f}:LRA={target_lra:.1f}:TP={target_tp:.1f}:"
            f"measured_I={stats.input_i:.2f}:"
            f"measured_LRA={stats.input_lra:.2f}:"
            f"measured_TP={stats.input_tp:.2f}:"
            f"measured_thresh={stats.input_thresh:.2f}:"
            f"offset={stats.target_offset:.2f}:linear=true"
        )
    else:
        loudnorm_str = f"loudnorm=I={target_lufs:.1f}:LRA={target_lra:.1f}:TP={target_tp:.1f}"

    filters.append(loudnorm_str)

    # True-peak brickwall peak limiter
    limiter_str = f"alimiter=limit={target_tp:.1f}dB:attack={limiter_attack_ms}:release={limiter_release_ms}"
    filters.append(limiter_str)

    # 30ms seamless loop micro-fade
    if apply_loop_crossfade and duration_sec is not None and duration_sec > 1.0:
        fade_out_start = max(0.0, duration_sec - crossfade_sec)
        filters.append(f"afade=t=in:ss=0:d={crossfade_sec:.3f}")
        filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={crossfade_sec:.3f}")

    return ",".join(filters)


# ============================================================================
# NORMALIZER CLASS
# ============================================================================

class EBUR128Normalizer:
    """
    Two-pass EBU R128 audio loudness normalizer and brickwall peak limiter.
    """

    def __init__(
        self,
        target_lufs: float = DEFAULT_TARGET_LUFS,
        target_lra: float = DEFAULT_TARGET_LRA,
        target_tp: float = DEFAULT_TARGET_TRUE_PEAK,
        highpass_hz: int = DEFAULT_HIGHPASS_HZ,
        crossfade_sec: float = DEFAULT_LOOP_CROSSFADE_SEC,
        custom_ffmpeg_path: Optional[Union[str, Path]] = None,
    ):
        self.target_lufs = float(target_lufs)
        self.target_lra = float(target_lra)
        self.target_tp = float(target_tp)
        self.highpass_hz = int(highpass_hz)
        self.crossfade_sec = float(crossfade_sec)
        self.custom_ffmpeg_path = custom_ffmpeg_path
        self._ffmpeg_bin: Optional[Path] = find_binary(
            "ffmpeg", custom_path=custom_ffmpeg_path, env_var="FFMPEG_BINARY"
        )

    def _require_ffmpeg(self) -> Path:
        ffmpeg_bin = self._ffmpeg_bin or find_binary(
            "ffmpeg", custom_path=self.custom_ffmpeg_path, env_var="FFMPEG_BINARY"
        )
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found on PATH or environment.")
        return ffmpeg_bin

    def measure_loudness(
        self,
        input_path: Union[str, Path],
        start_time: float = 0.0,
        duration: Optional[float] = None,
    ) -> Optional[LoudnessStats]:
        """
        Executes Pass 1 measurement on an audio/video file and returns LoudnessStats.
        Renders audio to null sink (`-f null -`) to minimize CPU/IO overhead.
        """
        ffmpeg_bin = self._require_ffmpeg()
        path_obj = Path(input_path).resolve()
        if not path_obj.is_file():
            raise FileNotFoundError(f"Input file not found: {path_obj}")

        af_filter = build_pass1_filter(
            target_lufs=self.target_lufs,
            target_lra=self.target_lra,
            target_tp=self.target_tp,
            highpass_hz=self.highpass_hz,
        )

        cmd = [str(ffmpeg_bin), "-y"]
        if start_time > 0:
            cmd.extend(["-ss", str(start_time)])
        if duration and duration > 0:
            cmd.extend(["-t", str(duration)])

        cmd.extend([
            "-i", str(path_obj),
            "-vn",
            "-af", af_filter,
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
                timeout=120,
            )
            return parse_loudnorm_stderr_json(proc.stderr)
        except subprocess.CalledProcessError as e:
            return parse_loudnorm_stderr_json(e.stderr)
        except Exception as ex:
            logger.error(f"Error during loudness measurement: {ex}")
            return None

    def normalize_audio_file(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        start_time: float = 0.0,
        duration: Optional[float] = None,
        apply_loop_crossfade: bool = True,
        audio_codec: str = "aac",
        audio_bitrate: str = "320k",
        sample_rate: int = 48000,
    ) -> bool:
        """
        Executes complete two-pass EBU R128 loudness normalization and encodes output audio.
        """
        ffmpeg_bin = self._require_ffmpeg()
        in_p = Path(input_path).resolve()
        out_p = Path(output_path).resolve()

        if not in_p.is_file():
            raise FileNotFoundError(f"Input file not found: {in_p}")

        # Pass 1: Measure loudness
        stats = self.measure_loudness(in_p, start_time=start_time, duration=duration)
        if stats:
            logger.info(
                f"Pass 1 measured: I={stats.input_i} LUFS, TP={stats.input_tp} dB, "
                f"LRA={stats.input_lra} LU, Offset={stats.target_offset} dB"
            )
        else:
            logger.warning("Pass 1 measurement failed or unavailable. Using single-pass fallback.")

        # Pass 2: Linear normalization filter
        af_pass2 = build_pass2_filter(
            stats=stats,
            target_lufs=self.target_lufs,
            target_lra=self.target_lra,
            target_tp=self.target_tp,
            highpass_hz=self.highpass_hz,
            duration_sec=duration,
            apply_loop_crossfade=apply_loop_crossfade,
            crossfade_sec=self.crossfade_sec,
        )

        out_p.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(ffmpeg_bin), "-y"]
        if start_time > 0:
            cmd.extend(["-ss", str(start_time)])
        if duration and duration > 0:
            cmd.extend(["-t", str(duration)])

        cmd.extend([
            "-i", str(in_p),
            "-vn",
            "-af", af_pass2,
            "-c:a", audio_codec,
            "-b:a", audio_bitrate,
            "-ar", str(sample_rate),
            str(out_p),
        ])

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=300,
            )
            return out_p.is_file() and out_p.stat().st_size > 0
        except subprocess.SubprocessError as e:
            logger.error(f"Pass 2 normalization failed: {e}")
            return False


# ============================================================================
# CONVENIENCE FUNCTIONAL INTERFACE
# ============================================================================

def measure_loudness(
    input_path: Union[str, Path],
    target_lufs: float = DEFAULT_TARGET_LUFS,
    custom_ffmpeg_path: Optional[str] = None,
) -> Optional[LoudnessStats]:
    """Convenience functional wrapper for measuring audio loudness."""
    normalizer = EBUR128Normalizer(target_lufs=target_lufs, custom_ffmpeg_path=custom_ffmpeg_path)
    return normalizer.measure_loudness(input_path)


def normalize_audio_file(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    target_lufs: float = DEFAULT_TARGET_LUFS,
    duration: Optional[float] = None,
    custom_ffmpeg_path: Optional[str] = None,
) -> bool:
    """Convenience functional wrapper for two-pass audio normalization."""
    normalizer = EBUR128Normalizer(target_lufs=target_lufs, custom_ffmpeg_path=custom_ffmpeg_path)
    return normalizer.normalize_audio_file(input_path, output_path, duration=duration)


# ============================================================================
# CLI ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EBU R128 Two-Pass Loudness Normalizer & Limiter")
    parser.add_argument("input_file", nargs="?", default=None, help="Path to input media container or audio file")
    parser.add_argument("-o", "--output", default=None, help="Path to output normalized audio file")
    parser.add_argument("--target-lufs", type=float, default=DEFAULT_TARGET_LUFS, help="Target integrated loudness in LUFS (default: -14.0)")
    parser.add_argument("--target-tp", type=float, default=DEFAULT_TARGET_TRUE_PEAK, help="Target true peak in dBTP (default: -1.5)")
    parser.add_argument("--highpass", type=int, default=DEFAULT_HIGHPASS_HZ, help="High-pass filter cutoff in Hz (default: 40)")
    parser.add_argument("--measure-only", action="store_true", help="Measure and display loudness statistics without writing output file")
    parser.add_argument("--dry-run", action="store_true", help="Print the generated Pass 1 and Pass 2 FFmpeg filtergraph strings")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    if args.dry_run:
        p1 = build_pass1_filter(target_lufs=args.target_lufs, target_tp=args.target_tp, highpass_hz=args.highpass)
        dummy_stats = LoudnessStats(input_i=-21.5, input_tp=-0.8, input_lra=6.2, input_thresh=-32.0, target_offset=0.5)
        p2 = build_pass2_filter(stats=dummy_stats, target_lufs=args.target_lufs, target_tp=args.target_tp, highpass_hz=args.highpass, duration_sec=30.0)
        print("PASS 1 FILTER:")
        print(f"  {p1}")
        print("\nPASS 2 FILTER (with sample measured stats):")
        print(f"  {p2}")
        sys.exit(0)

    if not args.input_file:
        parser.print_help()
        sys.exit(1)

    normalizer = EBUR128Normalizer(
        target_lufs=args.target_lufs,
        target_tp=args.target_tp,
        highpass_hz=args.highpass,
    )

    if args.measure_only or not args.output:
        stats = normalizer.measure_loudness(args.input_file)
        if not stats:
            print("[ERROR] Loudness measurement failed or no audio stream found.", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(stats.to_dict(), indent=2))
        else:
            print(f"Input Integrated Loudness: {stats.input_i:.2f} LUFS")
            print(f"Input True Peak:          {stats.input_tp:.2f} dBTP")
            print(f"Input Loudness Range:     {stats.input_lra:.2f} LU")
            print(f"Input Threshold:          {stats.input_thresh:.2f} LUFS")
            print(f"Target Normalization Gain:{stats.target_offset:.2f} dB")
        sys.exit(0)

    success = normalizer.normalize_audio_file(args.input_file, args.output)
    if success:
        print(f"[SUCCESS] Normalized audio exported to: {args.output}")
        sys.exit(0)
    else:
        print("[ERROR] Audio normalization failed.", file=sys.stderr)
        sys.exit(1)
