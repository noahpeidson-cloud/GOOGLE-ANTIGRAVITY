"""Procedural test media generator using FFmpeg lavfi filters.

Generates zero-dependency synthetic test video assets for 4K UHD, 1080p,
9:16 vertical video, SMPTE color bars, high-entropy noise patterns,
and multi-frequency audio tones.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def get_ffmpeg_binary() -> str:
    """Resolve the path to the FFmpeg executable across environments."""
    # 1. Check static_ffmpeg
    try:
        import static_ffmpeg
        ffmpeg_path, _ = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path
    except Exception:
        pass

    # 2. Check imageio_ffmpeg
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path
    except Exception:
        pass

    # 3. Check system PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg and os.path.exists(system_ffmpeg):
        return system_ffmpeg

    # 4. Check common Windows install paths
    win_candidates = [
        r"C:\Program Files\Logitech\LogiTune\resources\ffmpeg\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\CapCut\Apps\9.3.0.3970\ffmpeg.exe"),
    ]
    for candidate in win_candidates:
        if os.path.exists(candidate):
            return candidate

    raise RuntimeError("FFmpeg executable not found in static_ffmpeg, imageio_ffmpeg, or PATH.")


def get_ffprobe_binary() -> str:
    """Resolve the path to the FFprobe executable across environments."""
    # 1. Check static_ffmpeg
    try:
        import static_ffmpeg
        _, ffprobe_path = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        if os.path.exists(ffprobe_path):
            return ffprobe_path
    except Exception:
        pass

    # 2. Check system PATH
    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe and os.path.exists(system_ffprobe):
        return system_ffprobe

    # 3. Look in same directory as get_ffmpeg_binary()
    try:
        ffmpeg_bin = get_ffmpeg_binary()
        sibling = os.path.join(os.path.dirname(ffmpeg_bin), "ffprobe.exe")
        if os.path.exists(sibling):
            return sibling
        sibling_nix = os.path.join(os.path.dirname(ffmpeg_bin), "ffprobe")
        if os.path.exists(sibling_nix):
            return sibling_nix
    except Exception:
        pass

    raise RuntimeError("FFprobe executable not found in static_ffmpeg or PATH.")


def generate_procedural_video(
    output_path: str | Path,
    duration_sec: float = 2.0,
    resolution: Tuple[int, int] = (1920, 1080),
    fps: float = 30.0,
    pattern: str = "testsrc2",
    with_audio: bool = True,
    audio_freq: float = 440.0,
    audio_sample_rate: int = 48000,
    audio_bitrate: str = "320k",
    pix_fmt: str = "yuv420p",
    video_codec: str = "libx264",
    crf: int = 17,
) -> Path:
    """Generate a synthetic video using FFmpeg lavfi filter sources.
    
    Args:
        output_path: Target path for the output MP4 container.
        duration_sec: Length of video in seconds.
        resolution: (width, height) tuple.
        fps: Target frame rate.
        pattern: Video generator filter ('testsrc2', 'smptebars', 'smptehdbars', 'noise').
        with_audio: If True, synthesizes a synchronized sine wave audio stream.
        audio_freq: Sine tone frequency in Hz.
        audio_sample_rate: Audio sampling rate in Hz.
        audio_bitrate: Audio encoder bitrate.
        pix_fmt: Pixel format (e.g., 'yuv420p', 'yuv444p').
        video_codec: Encoder name (e.g., 'libx264', 'libx265').
        crf: Constant Rate Factor (17 = visually lossless).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = get_ffmpeg_binary()

    width, height = resolution
    cmd = [ffmpeg_bin, "-y"]

    if pattern == "noise":
        video_filter = f"nullsrc=size={width}x{height}:rate={fps},noise=alls=80:allf=t+u"
    elif pattern in ("smptebars", "smptehdbars"):
        video_filter = f"{pattern}=size={width}x{height}:rate={fps}"
    elif pattern == "color":
        video_filter = f"color=c=blue:size={width}x{height}:rate={fps}"
    else:
        video_filter = f"testsrc2=size={width}x{height}:rate={fps}"

    cmd.extend(["-f", "lavfi", "-i", video_filter])

    if with_audio:
        audio_filter = f"sine=frequency={audio_freq}:sample_rate={audio_sample_rate}"
        cmd.extend(["-f", "lavfi", "-i", audio_filter])

    cmd.extend([
        "-t", str(duration_sec),
        "-c:v", video_codec,
        "-crf", str(crf),
        "-preset", "veryfast",
        "-pix_fmt", pix_fmt,
    ])
    if video_codec == "libx264":
        if pix_fmt == "yuv444p":
            cmd.extend(["-profile:v", "high444"])
        else:
            cmd.extend(["-profile:v", "high"])

    if with_audio:
        cmd.extend([
            "-c:a", "aac",
            "-ac", "2",
            "-b:a", audio_bitrate,
            "-ar", str(audio_sample_rate),
        ])
    else:
        cmd.append("-an")

    cmd.append(str(output_path.resolve()))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg generation failed (code {result.returncode}):\n{result.stderr}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Generated file does not exist or is 0 bytes: {output_path}")

    return output_path


def generate_4k_uhd_video(output_path: str | Path, duration_sec: float = 2.0, fps: float = 60.0) -> Path:
    """Generate 4K UHD (3840x2160) synthetic benchmark clip."""
    return generate_procedural_video(
        output_path=output_path,
        duration_sec=duration_sec,
        resolution=(3840, 2160),
        fps=fps,
        pattern="testsrc2",
        with_audio=True,
        audio_freq=440.0,
    )


def generate_1080p_video(output_path: str | Path, duration_sec: float = 2.0, fps: float = 30.0) -> Path:
    """Generate 1080p Full HD (1920x1080) synthetic benchmark clip."""
    return generate_procedural_video(
        output_path=output_path,
        duration_sec=duration_sec,
        resolution=(1920, 1080),
        fps=fps,
        pattern="testsrc2",
        with_audio=True,
        audio_freq=440.0,
    )


def generate_vertical_video(output_path: str | Path, duration_sec: float = 2.0, fps: float = 30.0) -> Path:
    """Generate 9:16 vertical (1080x1920) social clip."""
    return generate_procedural_video(
        output_path=output_path,
        duration_sec=duration_sec,
        resolution=(1080, 1920),
        fps=fps,
        pattern="testsrc2",
        with_audio=True,
        audio_freq=520.0,
    )


def generate_noise_video(output_path: str | Path, duration_sec: float = 1.5) -> Path:
    """Generate high-entropy video clip to test encoder bitrate ceilings."""
    return generate_procedural_video(
        output_path=output_path,
        duration_sec=duration_sec,
        resolution=(1280, 720),
        fps=30.0,
        pattern="noise",
        with_audio=True,
        audio_freq=880.0,
    )


def generate_smpte_bars_video(output_path: str | Path, duration_sec: float = 2.0) -> Path:
    """Generate standard SMPTE color bars for color calibration testing."""
    return generate_procedural_video(
        output_path=output_path,
        duration_sec=duration_sec,
        resolution=(1920, 1080),
        fps=30.0,
        pattern="smptebars",
        with_audio=True,
        audio_freq=1000.0,
    )


def generate_silent_video(output_path: str | Path, duration_sec: float = 2.0) -> Path:
    """Generate video without audio stream (boundary condition)."""
    return generate_procedural_video(
        output_path=output_path,
        duration_sec=duration_sec,
        resolution=(1920, 1080),
        fps=30.0,
        pattern="testsrc2",
        with_audio=False,
    )


def generate_odd_dimension_video(output_path: str | Path, duration_sec: float = 1.0) -> Path:
    """Generate non-standard/odd dimension video (e.g. 1921x1081) for boundary testing."""
    return generate_procedural_video(
        output_path=output_path,
        duration_sec=duration_sec,
        resolution=(1921, 1081),
        fps=30.0,
        pattern="color",
        with_audio=True,
        pix_fmt="yuv444p",
    )


def generate_corrupt_video(output_path: str | Path) -> Path:
    """Create a corrupted/truncated media file for error-handling verification."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Write invalid MP4 header with random garbage
    with open(output_path, "wb") as f:
        f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42\xde\xad\xbe\xef" + os.urandom(2048))
    return output_path
