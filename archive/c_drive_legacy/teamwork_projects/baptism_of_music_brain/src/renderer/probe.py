"""Media metadata extraction and stream parsing using FFprobe."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional, Union

from config.settings import get_settings
from src.models.schemas import (
    AudioStreamMetadata,
    MediaProbeResult,
    VideoStreamMetadata,
)

logger = logging.getLogger(__name__)


class FFprobeError(Exception):
    """Base exception for FFprobe extraction errors."""
    pass


class FFprobeNotFoundError(FFprobeError):
    """Raised when FFprobe binary cannot be discovered."""
    pass


class MediaFileNotFoundError(FFprobeError):
    """Raised when the target media file does not exist on disk."""
    pass


class CorruptMediaError(FFprobeError):
    """Raised when the target media file cannot be decoded or is corrupt."""
    pass


class FFprobeExecutionError(FFprobeError):
    """Raised when FFprobe subprocess exits with a non-zero code or times out."""
    pass


def parse_fractional_rate(rate_str: Optional[str], default: float = 30.0) -> float:
    """Parse FFprobe fractional frame rate strings (e.g. '30000/1001', '30/1', '29.97')."""
    if not rate_str or rate_str in ("0/0", "N/A", "0"):
        return default

    rate_str = str(rate_str).strip()
    if "/" in rate_str:
        try:
            num, den = rate_str.split("/", 1)
            f_den = float(den)
            if f_den > 0:
                return float(num) / f_den
        except (ValueError, ZeroDivisionError):
            return default

    try:
        val = float(rate_str)
        return val if val > 0 else default
    except ValueError:
        return default


def _resolve_ffprobe_binary(explicit_bin: Optional[str] = None) -> str:
    """Resolve FFprobe executable path from explicit param or settings."""
    if explicit_bin:
        if os.path.exists(explicit_bin):
            return str(Path(explicit_bin).resolve())
        raise FFprobeNotFoundError(f"Specified ffprobe binary does not exist on disk: {explicit_bin}")

    try:
        settings = get_settings()
        return settings.resolve_ffprobe_bin()
    except Exception as exc:
        raise FFprobeNotFoundError(f"Failed to locate ffprobe binary: {exc}") from exc


def _parse_ffprobe_json(data: Dict[str, Any], file_path: Path) -> MediaProbeResult:
    """Construct MediaProbeResult schema from parsed FFprobe JSON data."""
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video_streams: list[VideoStreamMetadata] = []
    audio_streams: list[AudioStreamMetadata] = []

    for idx, s in enumerate(streams):
        codec_type = s.get("codec_type")
        if codec_type == "video":
            # Determine FPS from avg_frame_rate, r_frame_rate, or fallback
            fps = parse_fractional_rate(s.get("avg_frame_rate"))
            if fps == 30.0 and s.get("r_frame_rate"):
                fps = parse_fractional_rate(s.get("r_frame_rate"))

            # Video bitrate from stream or fallback to format
            v_bitrate = None
            if s.get("bit_rate"):
                try:
                    v_bitrate = int(s["bit_rate"])
                except (ValueError, TypeError):
                    pass

            v_meta = VideoStreamMetadata(
                index=int(s.get("index", idx)),
                codec_name=s.get("codec_name", "unknown"),
                codec_long_name=s.get("codec_long_name"),
                profile=s.get("profile"),
                width=int(s.get("width", 0)),
                height=int(s.get("height", 0)),
                aspect_ratio=s.get("display_aspect_ratio"),
                fps=round(fps, 3),
                pixel_format=s.get("pix_fmt", "unknown"),
                bitrate=v_bitrate,
                duration_sec=float(s.get("duration", fmt.get("duration", 0.0))) if s.get("duration") or fmt.get("duration") else None,
                nb_frames=int(s["nb_frames"]) if s.get("nb_frames") and str(s["nb_frames"]).isdigit() else None,
                color_space=s.get("color_space"),
                color_transfer=s.get("color_transfer"),
                color_primaries=s.get("color_primaries"),
            )
            video_streams.append(v_meta)

        elif codec_type == "audio":
            a_bitrate = None
            if s.get("bit_rate"):
                try:
                    a_bitrate = int(s["bit_rate"])
                except (ValueError, TypeError):
                    pass

            a_meta = AudioStreamMetadata(
                index=int(s.get("index", idx)),
                codec_name=s.get("codec_name", "unknown"),
                codec_long_name=s.get("codec_long_name"),
                sample_rate=int(s.get("sample_rate", 48000)),
                channels=int(s.get("channels", 2)),
                channel_layout=s.get("channel_layout"),
                bitrate=a_bitrate,
                duration_sec=float(s.get("duration", fmt.get("duration", 0.0))) if s.get("duration") or fmt.get("duration") else None,
            )
            audio_streams.append(a_meta)

    # Format-level metadata
    duration_sec = 0.0
    if fmt.get("duration"):
        try:
            duration_sec = float(fmt["duration"])
        except (ValueError, TypeError):
            pass

    size_bytes = 0
    if fmt.get("size"):
        try:
            size_bytes = int(fmt["size"])
        except (ValueError, TypeError):
            pass
    elif file_path.exists():
        size_bytes = file_path.stat().st_size

    fmt_bitrate = None
    if fmt.get("bit_rate"):
        try:
            fmt_bitrate = int(fmt["bit_rate"])
        except (ValueError, TypeError):
            pass

    return MediaProbeResult(
        filepath=str(file_path.resolve()),
        format_name=fmt.get("format_name", "unknown"),
        format_long_name=fmt.get("format_long_name"),
        duration_sec=duration_sec,
        size_bytes=size_bytes,
        bitrate=fmt_bitrate,
        video_streams=video_streams,
        audio_streams=audio_streams,
        raw_json=data,
    )


def probe_media(
    file_path: Union[str, Path],
    ffprobe_bin: Optional[str] = None,
    timeout_sec: float = 15.0,
) -> MediaProbeResult:
    """Synchronously execute FFprobe against a media file and parse stream metadata."""
    p = Path(file_path).resolve()
    if not p.exists():
        raise MediaFileNotFoundError(f"Target media file does not exist: {p}")

    if p.stat().st_size == 0:
        raise CorruptMediaError(f"Target media file is 0 bytes (empty): {p}")

    bin_path = _resolve_ffprobe_binary(ffprobe_bin)

    cmd = [
        bin_path,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-show_error",
        "-print_format", "json",
        str(p),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as err:
        raise FFprobeExecutionError(f"FFprobe execution timed out after {timeout_sec}s for {p}") from err
    except Exception as exc:
        raise FFprobeExecutionError(f"Failed to execute FFprobe process: {exc}") from exc

    if result.returncode != 0:
        err_msg = result.stderr.strip() or f"Process exited with code {result.returncode}"
        raise CorruptMediaError(f"FFprobe failed to decode {p.name}: {err_msg}")

    try:
        parsed_data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CorruptMediaError(f"Failed to parse FFprobe JSON output for {p.name}: {exc}") from exc

    if "error" in parsed_data:
        raise CorruptMediaError(f"FFprobe reported container error: {parsed_data['error']}")

    return _parse_ffprobe_json(parsed_data, p)


async def async_probe_media(
    file_path: Union[str, Path],
    ffprobe_bin: Optional[str] = None,
    timeout_sec: float = 15.0,
) -> MediaProbeResult:
    """Asynchronously execute FFprobe against a media file in a thread pool."""
    return await asyncio.to_thread(probe_media, file_path, ffprobe_bin, timeout_sec)
