"""Renderer package for media probing, filtergraph compilation, profiles, and FFmpeg execution."""

from src.renderer.ffmpeg_engine import (
    FFmpegError,
    FFmpegExecutionError,
    FFmpegNotFoundError,
    FFmpegRenderer,
    RenderVerificationError,
)
from src.renderer.filtergraph import (
    FiltergraphCompilationResult,
    build_filtergraph,
    compile_filtergraph,
)
from src.renderer.probe import (
    CorruptMediaError,
    FFprobeError,
    FFprobeExecutionError,
    FFprobeNotFoundError,
    MediaFileNotFoundError,
    async_probe_media,
    probe_media,
)
from src.renderer.profiles import (
    PROFILES_REGISTRY,
    EncodingProfile,
    get_encoding_args,
    get_profile,
    is_nvenc_available,
    list_available_profiles,
    resolve_profile_with_fallback,
)

__all__ = [
    # Probe
    "FFprobeError",
    "FFprobeNotFoundError",
    "MediaFileNotFoundError",
    "CorruptMediaError",
    "FFprobeExecutionError",
    "probe_media",
    "async_probe_media",
    # Profiles
    "EncodingProfile",
    "PROFILES_REGISTRY",
    "get_profile",
    "get_encoding_args",
    "list_available_profiles",
    "is_nvenc_available",
    "resolve_profile_with_fallback",
    # Filtergraph
    "build_filtergraph",
    "compile_filtergraph",
    "FiltergraphCompilationResult",
    # Engine
    "FFmpegError",
    "FFmpegNotFoundError",
    "FFmpegExecutionError",
    "RenderVerificationError",
    "FFmpegRenderer",
]
