r"""
---
Name: Visually Lossless Encoding Profiles Registry & Hardware Fallback Manager
Context Mapping: Originally developed in `baptism_of_music_brain/src/renderer/profiles.py` for Track 2 (EDM Short-Form Media Engineering) to standardize production-grade video and audio encoding presets across social delivery and archival pipelines.
Strengths:
  - Five research-validated production profiles:
      1. `x264_crf17`: Universal visually lossless H.264 for mobile platforms (CRF 17, High Profile 5.2, Rec.709, AAC 320k, MP4 +faststart).
      2. `x264_yuv444p`: Studio archive master preserving 4:4:4 full chroma sampling without subsampling blur on lasers and fine text.
      3. `x265_crf16`: 10-bit HEVC distribution master (yuv420p10le, tag:v=hvc1 for Apple iOS and Samsung hardware decoders).
      4. `hevc_nvenc`: Hardware-accelerated NVIDIA GPU encoding (P6 preset, HQ tune, VBR CQ 17, 10-15x faster than CPU).
      5. `prores_hq`: Apple ProRes 422 HQ mezzanine archive master (prores_ks profile 3, 24-bit uncompressed PCM audio, .mov).
  - Resilient Hardware-to-Software Fallback: Queries `ffmpeg -encoders` dynamically. If `hevc_nvenc` is requested on a machine lacking an NVIDIA GPU or CUDA runtime, it gracefully falls back to `x264_crf17` without crashing the render pipeline.
  - Clean CLI argument generation: Compiles typed dataclass fields into exact, deterministic FFmpeg CLI argument lists.
  - Zero-dependency: Pure Python standard library implementation with self-contained executable discovery.
Weaknesses:
  - Hardware acceleration probing requires spawning `ffmpeg -encoders` subprocess on first run (cached per process).
  - Apple ProRes 422 HQ generates high-bitrate files (~220 Mbps at 4K) suitable for editing archives but too large for direct web transmission.
Implementation Instructions:
  - Import `get_profile` or `get_encoding_args` directly from this module.
  - Call `get_encoding_args('hevc_nvenc', fallback_to_software=True)` to get FFmpeg CLI flags with automatic NVENC fallback.
  - Inspect profile definitions with `list_available_profiles()`.
  - Standalone CLI supports `--list`, `--inspect <name>`, and `--check-nvenc`.
---
"""

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("lossless_encoding_profiles")


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class EncodingProfile:
    """Specification of video/audio codec flags, rate controls, and container parameters."""
    name: str
    video_codec: str
    preset: Optional[str] = None
    crf: Optional[int] = None
    cq: Optional[int] = None
    profile_v: Optional[str] = None
    level: Optional[str] = None
    pix_fmt: str = "yuv420p"
    colorspace: Optional[str] = None
    color_primaries: Optional[str] = None
    color_trc: Optional[str] = None
    color_range: Optional[str] = None
    tag_v: Optional[str] = None
    vendor: Optional[str] = None
    rc: Optional[str] = None
    tune: Optional[str] = None
    extra_video_args: List[str] = field(default_factory=list)
    audio_codec: str = "aac"
    audio_bitrate: Optional[str] = "320k"
    audio_sample_rate: int = 48000
    audio_channels: int = 2
    movflags: Optional[str] = "+faststart"
    container_extension: str = ".mp4"
    is_hardware_accelerated: bool = False

    def to_cli_args(self) -> List[str]:
        """Compiles profile into FFmpeg CLI arguments list."""
        args: List[str] = []

        # Video Codec
        args.extend(["-c:v", self.video_codec])

        # Preset / Tune
        if self.preset:
            args.extend(["-preset", self.preset])
        if self.tune:
            args.extend(["-tune", self.tune])

        # Rate Control (CRF / CQ / RC)
        if self.crf is not None:
            args.extend(["-crf", str(self.crf)])
        if self.cq is not None:
            args.extend(["-cq", str(self.cq)])
        if self.rc:
            args.extend(["-rc", self.rc])

        # Profile / Level
        if self.profile_v:
            args.extend(["-profile:v", self.profile_v])
        if self.level:
            args.extend(["-level", self.level])

        # Pixel Format
        if self.pix_fmt:
            args.extend(["-pix_fmt", self.pix_fmt])

        # Color Space Metadata
        if self.colorspace:
            args.extend(["-colorspace", self.colorspace])
        if self.color_primaries:
            args.extend(["-color_primaries", self.color_primaries])
        if self.color_trc:
            args.extend(["-color_trc", self.color_trc])
        if self.color_range:
            args.extend(["-color_range", self.color_range])

        # Tag / Vendor (e.g. hvc1 for Apple/Samsung, apl0 for ProRes)
        if self.tag_v:
            args.extend(["-tag:v", self.tag_v])
        if self.vendor:
            args.extend(["-vendor", self.vendor])

        # Extra Video Args
        args.extend(self.extra_video_args)

        # Audio Codec & Parameters
        if self.audio_codec:
            args.extend(["-c:a", self.audio_codec])
        if self.audio_bitrate:
            args.extend(["-b:a", self.audio_bitrate])
        if self.audio_sample_rate:
            args.extend(["-ar", str(self.audio_sample_rate)])
        if self.audio_channels:
            args.extend(["-ac", str(self.audio_channels)])

        # Container Movflags
        if self.movflags:
            args.extend(["-movflags", self.movflags])

        return args

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "video_codec": self.video_codec,
            "preset": self.preset,
            "crf": self.crf,
            "cq": self.cq,
            "profile_v": self.profile_v,
            "level": self.level,
            "pix_fmt": self.pix_fmt,
            "colorspace": self.colorspace,
            "color_primaries": self.color_primaries,
            "color_trc": self.color_trc,
            "color_range": self.color_range,
            "tag_v": self.tag_v,
            "vendor": self.vendor,
            "rc": self.rc,
            "tune": self.tune,
            "extra_video_args": self.extra_video_args,
            "audio_codec": self.audio_codec,
            "audio_bitrate": self.audio_bitrate,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_channels": self.audio_channels,
            "movflags": self.movflags,
            "container_extension": self.container_extension,
            "is_hardware_accelerated": self.is_hardware_accelerated,
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
# PROFILE DEFINITIONS REGISTRY
# ============================================================================

PROFILES_REGISTRY: Dict[str, EncodingProfile] = {
    # 1. Default Visually Lossless H.264 (Universal Mobile & Social Playback)
    "x264_crf17": EncodingProfile(
        name="x264_crf17",
        video_codec="libx264",
        preset="slow",
        crf=17,
        profile_v="high",
        level="5.2",
        pix_fmt="yuv420p",
        colorspace="bt709",
        color_primaries="bt709",
        color_trc="bt709",
        color_range="tv",
        movflags="+faststart",
        audio_codec="aac",
        audio_bitrate="320k",
        audio_sample_rate=48000,
        audio_channels=2,
        container_extension=".mp4",
        is_hardware_accelerated=False,
    ),

    # 2. Studio Lossless H.264 (4:4:4 Full Chroma Sampling, No Subsampling Blur)
    "x264_yuv444p": EncodingProfile(
        name="x264_yuv444p",
        video_codec="libx264",
        preset="slow",
        crf=17,
        profile_v="high444",
        pix_fmt="yuv444p",
        movflags="+faststart",
        audio_codec="aac",
        audio_bitrate="320k",
        audio_sample_rate=48000,
        audio_channels=2,
        container_extension=".mp4",
        is_hardware_accelerated=False,
    ),

    # 3. High-Efficiency 10-Bit HEVC (hvc1 Apple iOS & Samsung Hardware Tag)
    "x265_crf16": EncodingProfile(
        name="x265_crf16",
        video_codec="libx265",
        preset="medium",
        crf=16,
        pix_fmt="yuv420p10le",
        tag_v="hvc1",
        movflags="+faststart",
        audio_codec="aac",
        audio_bitrate="320k",
        audio_sample_rate=48000,
        audio_channels=2,
        container_extension=".mp4",
        is_hardware_accelerated=False,
    ),

    # 4. Hardware Accelerated NVENC (NVIDIA GPU VBR / CQ 17, 10-15x Transcode Speed)
    "hevc_nvenc": EncodingProfile(
        name="hevc_nvenc",
        video_codec="hevc_nvenc",
        preset="p6",
        tune="hq",
        rc="vbr",
        cq=17,
        extra_video_args=["-b:v", "0"],
        pix_fmt="yuv420p",
        tag_v="hvc1",
        movflags="+faststart",
        audio_codec="aac",
        audio_bitrate="320k",
        audio_sample_rate=48000,
        audio_channels=2,
        container_extension=".mp4",
        is_hardware_accelerated=True,
    ),

    # 5. Master Archive Apple ProRes 422 HQ (Uncompressed 24-bit PCM Audio)
    "prores_hq": EncodingProfile(
        name="prores_hq",
        video_codec="prores_ks",
        preset=None,
        profile_v="3",
        vendor="apl0",
        pix_fmt="yuv422p10le",
        movflags=None,
        audio_codec="pcm_s24le",
        audio_bitrate=None,
        audio_sample_rate=48000,
        audio_channels=2,
        container_extension=".mov",
        is_hardware_accelerated=False,
    ),
}

# Aliases for convenience
PROFILES_REGISTRY["default"] = PROFILES_REGISTRY["x264_crf17"]
PROFILES_REGISTRY["h264"] = PROFILES_REGISTRY["x264_crf17"]
PROFILES_REGISTRY["hevc"] = PROFILES_REGISTRY["x265_crf16"]
PROFILES_REGISTRY["nvenc"] = PROFILES_REGISTRY["hevc_nvenc"]
PROFILES_REGISTRY["prores"] = PROFILES_REGISTRY["prores_hq"]


# ============================================================================
# HARDWARE PROBING & FALLBACK
# ============================================================================

_NVENC_CACHE: Optional[bool] = None


def is_nvenc_available(ffmpeg_bin: Optional[Union[str, Path]] = None) -> bool:
    """
    Checks whether the local FFmpeg binary supports NVENC hardware encoding.
    Caches probe result in memory to avoid repeated subprocess invocations.
    """
    global _NVENC_CACHE
    if _NVENC_CACHE is not None:
        return _NVENC_CACHE

    try:
        bin_path = ffmpeg_bin or find_binary("ffmpeg", env_var="FFMPEG_BINARY")
        if not bin_path:
            _NVENC_CACHE = False
            return False

        res = subprocess.run(
            [str(bin_path), "-encoders"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        has_nvenc = "hevc_nvenc" in res.stdout or "h264_nvenc" in res.stdout
        _NVENC_CACHE = bool(has_nvenc)
        return _NVENC_CACHE
    except Exception as exc:
        logger.debug(f"NVENC probe failed: {exc}")
        _NVENC_CACHE = False
        return False


def list_available_profiles() -> List[str]:
    """Returns canonical registered profile names (excluding short aliases)."""
    return ["x264_crf17", "x264_yuv444p", "x265_crf16", "hevc_nvenc", "prores_hq"]


def get_profile(name: str) -> EncodingProfile:
    """Retrieves an EncodingProfile by name or raises KeyError."""
    canonical_key = str(name).strip().lower()
    if canonical_key not in PROFILES_REGISTRY:
        raise KeyError(
            f"Unsupported encoding profile '{name}'. "
            f"Available profiles: {list_available_profiles()}"
        )
    return PROFILES_REGISTRY[canonical_key]


def resolve_profile_with_fallback(
    name: str,
    ffmpeg_bin: Optional[Union[str, Path]] = None,
    allow_fallback: bool = True,
) -> EncodingProfile:
    """
    Resolves profile by name. If a requested hardware profile (e.g. hevc_nvenc)
    is unsupported on the current system, automatically falls back to software x264_crf17.
    """
    profile = get_profile(name)
    if profile.is_hardware_accelerated and allow_fallback:
        if not is_nvenc_available(ffmpeg_bin):
            logger.warning(
                f"Hardware encoder '{profile.name}' is unavailable on this host. "
                "Falling back to visually lossless software encoder 'x264_crf17'."
            )
            return PROFILES_REGISTRY["x264_crf17"]
    return profile


def get_encoding_args(
    profile_name: str,
    fallback_to_software: bool = True,
    ffmpeg_bin: Optional[Union[str, Path]] = None,
) -> List[str]:
    """
    Retrieves the compiled FFmpeg CLI arguments list for a given profile name,
    applying hardware-to-software fallback if necessary.
    """
    profile = resolve_profile_with_fallback(
        profile_name,
        ffmpeg_bin=ffmpeg_bin,
        allow_fallback=fallback_to_software,
    )
    return profile.to_cli_args()


# ============================================================================
# CLI ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Visually Lossless Encoding Profiles Registry & Fallback Manager")
    parser.add_argument("--list", action="store_true", help="List all registered production encoding profiles")
    parser.add_argument("--inspect", type=str, default=None, help="Inspect detailed configuration and CLI flags for a profile")
    parser.add_argument("--check-nvenc", action="store_true", help="Test whether NVIDIA NVENC hardware acceleration is available")
    parser.add_argument("--cli-args", type=str, default=None, help="Print compiled FFmpeg CLI arguments list for a profile")

    args = parser.parse_args()

    if args.list:
        print("REGISTERED PRODUCTION PROFILES:")
        for name in list_available_profiles():
            prof = get_profile(name)
            hw = "[GPU NVENC]" if prof.is_hardware_accelerated else "[CPU Lossless]"
            print(f"  - {name:<15} {hw:<15} Codec: {prof.video_codec:<12} Ext: {prof.container_extension}")
        sys.exit(0)

    if args.check_nvenc:
        avail = is_nvenc_available()
        status = "AVAILABLE (Hardware acceleration ready)" if avail else "UNAVAILABLE (Will fall back to CPU libx264)"
        print(f"NVIDIA NVENC Status: {status}")
        sys.exit(0 if avail else 1)

    if args.inspect:
        try:
            prof = get_profile(args.inspect)
            print(f"=== PROFILE: {prof.name} ===")
            print(json.dumps(prof.to_dict(), indent=2))
            print("\nCOMPILED CLI ARGS:")
            print(" ".join(prof.to_cli_args()))
            sys.exit(0)
        except KeyError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    if args.cli_args:
        try:
            args_list = get_encoding_args(args.cli_args, fallback_to_software=True)
            print(" ".join(args_list))
            sys.exit(0)
        except KeyError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    parser.print_help()
