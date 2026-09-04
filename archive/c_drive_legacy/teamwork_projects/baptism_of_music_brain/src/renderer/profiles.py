"""Visually lossless video and audio encoding profiles for FFmpeg rendering engine."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional, Union

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class EncodingProfile:
    """Specification of video/audio codec flags, rates, and container parameters."""
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
        """Compile profile into FFmpeg CLI arguments list."""
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

        # Color Metadata
        if self.colorspace:
            args.extend(["-colorspace", self.colorspace])
        if self.color_primaries:
            args.extend(["-color_primaries", self.color_primaries])
        if self.color_trc:
            args.extend(["-color_trc", self.color_trc])
        if self.color_range:
            args.extend(["-color_range", self.color_range])

        # Tags & Vendors (e.g. hvc1 for Apple/Samsung, apl0 for ProRes)
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


# ============================================================================
# Profile Definitions Registry
# ============================================================================

PROFILES_REGISTRY: Dict[str, EncodingProfile] = {
    # 1. Default Visually Lossless H.264 (Universal Playback)
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
    ),

    # 2. Studio Lossless H.264 (4:4:4 Chroma Sampling)
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
    ),

    # 3. High-Efficiency 10-Bit HEVC (hvc1 Apple & Samsung Hardware Tag)
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
    ),

    # 4. Hardware Accelerated NVENC (GPU VBR / CQ 17)
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
        is_hardware_accelerated=True,
        container_extension=".mp4",
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
    ),
}

# Aliases for convenience
PROFILES_REGISTRY["default"] = PROFILES_REGISTRY["x264_crf17"]
PROFILES_REGISTRY["h264"] = PROFILES_REGISTRY["x264_crf17"]
PROFILES_REGISTRY["hevc"] = PROFILES_REGISTRY["x265_crf16"]
PROFILES_REGISTRY["nvenc"] = PROFILES_REGISTRY["hevc_nvenc"]
PROFILES_REGISTRY["prores"] = PROFILES_REGISTRY["prores_hq"]


# ============================================================================
# Discovery and Argument Helpers
# ============================================================================

def list_available_profiles() -> List[str]:
    """List all registered encoding profile names (excluding short aliases)."""
    return ["x264_crf17", "x264_yuv444p", "x265_crf16", "hevc_nvenc", "prores_hq"]


def get_profile(name: str) -> EncodingProfile:
    """Retrieve an EncodingProfile by name or raise KeyError."""
    canonical_key = str(name).strip().lower()
    if canonical_key not in PROFILES_REGISTRY:
        raise KeyError(
            f"Unsupported encoding profile '{name}'. "
            f"Available profiles: {list_available_profiles()}"
        )
    return PROFILES_REGISTRY[canonical_key]


def is_nvenc_available(ffmpeg_bin: Optional[str] = None) -> bool:
    """Check whether FFmpeg binary supports NVENC hardware encoding on this system."""
    try:
        bin_path = ffmpeg_bin or get_settings().resolve_ffmpeg_bin()
        res = subprocess.run(
            [bin_path, "-encoders"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return "hevc_nvenc" in res.stdout or "h264_nvenc" in res.stdout
    except Exception as exc:
        logger.debug(f"NVENC hardware acceleration probe failed: {exc}")
        return False


def resolve_profile_with_fallback(
    name: str,
    ffmpeg_bin: Optional[str] = None,
    allow_fallback: bool = True,
) -> EncodingProfile:
    """
    Resolve profile by name, falling back to software encoding (x265_crf16 or x264_crf17)
    if a requested hardware encoder (e.g. hevc_nvenc) is unavailable.
    """
    profile = get_profile(name)
    if profile.is_hardware_accelerated and allow_fallback:
        if not is_nvenc_available(ffmpeg_bin):
            logger.warning(
                f"Hardware encoder '{profile.name}' is unavailable. "
                "Falling back to visually lossless software encoder 'x264_crf17'."
            )
            return PROFILES_REGISTRY["x264_crf17"]
    return profile


def get_encoding_args(
    profile_name: str,
    fallback_to_software: bool = True,
    ffmpeg_bin: Optional[str] = None,
) -> List[str]:
    """
    Retrieve the compiled FFmpeg CLI argument list for a given profile name.
    Raises KeyError or ValueError if the profile name is invalid.
    """
    canonical_key = str(profile_name).strip().lower()
    if canonical_key not in PROFILES_REGISTRY:
        raise KeyError(
            f"Invalid encoding profile '{profile_name}'. "
            f"Supported profiles: {list_available_profiles()}"
        )

    profile = resolve_profile_with_fallback(
        canonical_key,
        ffmpeg_bin=ffmpeg_bin,
        allow_fallback=fallback_to_software,
    )
    return profile.to_cli_args()
