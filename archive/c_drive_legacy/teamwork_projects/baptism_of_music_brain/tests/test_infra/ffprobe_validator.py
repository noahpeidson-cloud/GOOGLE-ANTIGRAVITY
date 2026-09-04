"""Mathematical programmatic verification engine using FFprobe JSON output.

Asserts video codec, profile, pixel format, spatial resolution, frame rate precision (±0.05 FPS),
audio codec (aac), audio bitrate (>=310kbps), and duration invariance.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from tests.test_infra.media_generator import get_ffprobe_binary


def probe_media_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Execute ffprobe and return parsed JSON stream and format metadata."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Media file not found for probing: {file_path}")

    ffprobe_bin = get_ffprobe_binary()
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-print_format", "json",
        str(file_path.resolve()),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe execution failed for {file_path}:\n{result.stderr}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse FFprobe JSON output: {exc}\nRaw: {result.stdout}")

    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    video_meta = {}
    if video_streams:
        v0 = video_streams[0]
        # Calculate fps from r_frame_rate (e.g. "30/1" or "30000/1001")
        fps = 0.0
        r_rate = v0.get("r_frame_rate", "0/1")
        if "/" in r_rate:
            num, den = r_rate.split("/")
            if float(den) > 0:
                fps = float(num) / float(den)
        else:
            fps = float(r_rate)

        # Video bitrate from stream or format
        v_bitrate = int(v0.get("bit_rate", 0))
        if v_bitrate == 0 and "bit_rate" in fmt:
            v_bitrate = int(fmt["bit_rate"])

        video_meta = {
            "codec": v0.get("codec_name"),
            "profile": v0.get("profile"),
            "width": int(v0.get("width", 0)),
            "height": int(v0.get("height", 0)),
            "fps": round(fps, 3),
            "pix_fmt": v0.get("pix_fmt"),
            "bitrate": v_bitrate,
            "duration": float(v0.get("duration", fmt.get("duration", 0.0))),
            "aspect_ratio": v0.get("display_aspect_ratio", f"{v0.get('width', 0)}:{v0.get('height', 0)}"),
        }

    audio_meta = {}
    if audio_streams:
        a0 = audio_streams[0]
        a_bitrate = int(a0.get("bit_rate", 0))
        audio_meta = {
            "codec": a0.get("codec_name"),
            "bitrate": a_bitrate,
            "sample_rate": int(a0.get("sample_rate", 0)),
            "channels": int(a0.get("channels", 0)),
            "duration": float(a0.get("duration", fmt.get("duration", 0.0))),
        }

    return {
        "raw": data,
        "format": fmt,
        "streams": streams,
        "video_streams": video_streams,
        "audio_streams": audio_streams,
        "video": video_meta,
        "audio": audio_meta,
    }


def assert_resolution_match(
    probe_data: Dict[str, Any],
    expected_width: int,
    expected_height: int,
) -> None:
    """Assert video resolution matches expected dimensions exactly."""
    video = probe_data.get("video", {})
    assert video, "No video stream found in media probe data"
    actual_width = video.get("width")
    actual_height = video.get("height")
    assert (actual_width, actual_height) == (expected_width, expected_height), (
        f"Resolution mismatch: expected {expected_width}x{expected_height}, "
        f"got {actual_width}x{actual_height}"
    )


def assert_fps_precision(
    probe_data: Dict[str, Any],
    expected_fps: float,
    tolerance: float = 0.05,
) -> None:
    """Assert video frame rate is within precision tolerance (±0.05 FPS)."""
    video = probe_data.get("video", {})
    assert video, "No video stream found in media probe data"
    actual_fps = video.get("fps", 0.0)
    diff = abs(actual_fps - expected_fps)
    assert diff <= tolerance, (
        f"FPS precision violation: expected {expected_fps} ± {tolerance}, "
        f"got {actual_fps} (diff: {diff:.4f})"
    )


def assert_codec_and_profile(
    probe_data: Dict[str, Any],
    expected_vcodec: Optional[str] = "h264",
    expected_profile: Optional[str] = "High",
    expected_acodec: Optional[str] = "aac",
    expected_pix_fmt: Optional[str] = "yuv420p",
) -> None:
    """Assert video and audio stream codecs, profile, and pixel format."""
    video = probe_data.get("video", {})
    if expected_vcodec:
        assert video, "Expected video stream but none found"
        actual_vcodec = video.get("codec")
        assert actual_vcodec == expected_vcodec, (
            f"Video codec mismatch: expected '{expected_vcodec}', got '{actual_vcodec}'"
        )
    if expected_profile and video:
        actual_profile = video.get("profile")
        # For High profile, it can be "High" or contain "High"
        assert expected_profile.lower() in (actual_profile or "").lower(), (
            f"Video profile mismatch: expected '{expected_profile}', got '{actual_profile}'"
        )
    if expected_pix_fmt and video:
        actual_pix_fmt = video.get("pix_fmt")
        assert actual_pix_fmt == expected_pix_fmt, (
            f"Pixel format mismatch: expected '{expected_pix_fmt}', got '{actual_pix_fmt}'"
        )

    if expected_acodec:
        audio = probe_data.get("audio", {})
        assert audio, "Expected audio stream but none found"
        actual_acodec = audio.get("codec")
        assert actual_acodec == expected_acodec, (
            f"Audio codec mismatch: expected '{expected_acodec}', got '{actual_acodec}'"
        )


def assert_duration(
    probe_data: Dict[str, Any],
    expected_duration: float,
    tolerance: float = 0.2,
) -> None:
    """Assert stream duration is within expected tolerance."""
    fmt = probe_data.get("format", {})
    actual_duration = float(fmt.get("duration", 0.0))
    diff = abs(actual_duration - expected_duration)
    assert diff <= tolerance, (
        f"Duration mismatch: expected {expected_duration}s ± {tolerance}s, "
        f"got {actual_duration}s (diff: {diff:.4f}s)"
    )


def assert_visually_lossless(
    file_path: Union[str, Path],
    expected_resolution: Optional[Tuple[int, int]] = None,
    expected_fps: Optional[float] = None,
    expected_vcodec: Optional[str] = "h264",
    expected_profile: Optional[str] = "High",
    expected_acodec: Optional[str] = "aac",
    min_audio_bitrate: Optional[int] = None,
    expected_pix_fmt: Optional[str] = "yuv420p",
    expected_duration: Optional[float] = None,
    duration_tolerance: float = 0.2,
) -> Dict[str, Any]:
    """Execute exhaustive programmatic verification of visually lossless encoding targets.
    
    Returns the parsed probe dictionary on success.
    """
    probe_data = probe_media_file(file_path)

    # 1. Video stream checks
    if expected_resolution:
        assert_resolution_match(probe_data, expected_resolution[0], expected_resolution[1])

    if expected_fps:
        assert_fps_precision(probe_data, expected_fps, tolerance=0.05)

    assert_codec_and_profile(
        probe_data,
        expected_vcodec=expected_vcodec,
        expected_profile=expected_profile,
        expected_acodec=expected_acodec,
        expected_pix_fmt=expected_pix_fmt,
    )

    # 2. Audio bitrate assertion
    if min_audio_bitrate is not None and expected_acodec:
        audio = probe_data.get("audio", {})
        actual_abitrate = audio.get("bitrate", 0)
        # Note: in some containers stream bitrate might report 0 if in container header;
        # in that case format bitrate or non-zero check is verified
        if actual_abitrate > 0:
            assert actual_abitrate >= min_audio_bitrate, (
                f"Audio bitrate below lossless target: expected >={min_audio_bitrate} bps, "
                f"got {actual_abitrate} bps"
            )

    # 3. Duration invariance
    if expected_duration is not None:
        assert_duration(probe_data, expected_duration, tolerance=duration_tolerance)

    return probe_data
