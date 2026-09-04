"""
Procedural Media Generator for Omnichannel Triage Hub.
Strict compliance with Rule R16 (Absolute imports) and Rule R21 (Procedural Media Generation).
Uses Pillow for high-fidelity 9:16 mock frames and imageio-ffmpeg for procedural MP4 clips.
"""

import os
import io
import base64
import subprocess
from datetime import datetime, timezone
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg


def get_ffmpeg_path() -> str:
    """Returns verified path to FFmpeg binary via imageio_ffmpeg."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def generate_mock_frame(
    width: int = 540,
    height: int = 960,
    img_format: str = "PNG",
    title: str = "Omnichannel Triage Hub",
    domain: str = "EDM",
    entity: str = "Ultra Miami 2026",
    timestamp_str: Optional[str] = None
) -> bytes:
    """
    Generates a procedural 9:16 screen capture frame with HUD overlays,
    safe-zone guidelines, and live metadata.
    """
    if timestamp_str is None:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Base canvas: Dark slate gradient simulation
    img = Image.new("RGB", (width, height), color=(15, 23, 42))  # Slate 900
    draw = ImageDraw.Draw(img)

    # Gradient/Accent bands
    for y in range(0, height, 4):
        alpha = int(255 * (1.0 - (y / height) * 0.3))
        # Draw soft background grid / scanlines
        if y % 32 == 0:
            draw.line([(0, y), (width, y)], fill=(30, 41, 59), width=1)

    # Safe-zone Framing Guidelines (9:16 Shorts / Reels Safe Area)
    margin_x = int(width * 0.08)
    top_safe = int(height * 0.15)
    bottom_safe = int(height * 0.82)

    draw.rectangle(
        [margin_x, top_safe, width - margin_x, bottom_safe],
        outline=(59, 130, 246),  # Blue 500
        width=2
    )

    # Viewfinder Corner Reticles
    corner_len = 24
    # Top-Left
    draw.line([(margin_x, top_safe), (margin_x + corner_len, top_safe)], fill=(96, 165, 250), width=3)
    draw.line([(margin_x, top_safe), (margin_x, top_safe + corner_len)], fill=(96, 165, 250), width=3)
    # Top-Right
    draw.line([(width - margin_x, top_safe), (width - margin_x - corner_len, top_safe)], fill=(96, 165, 250), width=3)
    draw.line([(width - margin_x, top_safe), (width - margin_x, top_safe + corner_len)], fill=(96, 165, 250), width=3)
    # Bottom-Left
    draw.line([(margin_x, bottom_safe), (margin_x + corner_len, bottom_safe)], fill=(96, 165, 250), width=3)
    draw.line([(margin_x, bottom_safe), (margin_x, bottom_safe - corner_len)], fill=(96, 165, 250), width=3)
    # Bottom-Right
    draw.line([(width - margin_x, bottom_safe), (width - margin_x - corner_len, bottom_safe)], fill=(96, 165, 250), width=3)
    draw.line([(width - margin_x, bottom_safe), (width - margin_x, bottom_safe - corner_len)], fill=(96, 165, 250), width=3)

    # Phone Status Bar Simulation (Top)
    draw.rectangle([0, 0, width, 36], fill=(10, 15, 30))
    draw.text((16, 10), "12:00", fill=(226, 232, 240))
    draw.text((width - 90, 10), "5G  100%", fill=(34, 197, 94))  # Green 500

    # Header Card
    draw.rectangle([margin_x, 48, width - margin_x, top_safe - 12], fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((margin_x + 12, 54), title.upper(), fill=(248, 250, 252))
    draw.text((margin_x + 12, 72), "LIVE PHONE LINK • 4K HDR RECORDER", fill=(148, 163, 184))

    # Center Visual Mock Scene (DJ Stage / Arena Lights simulation)
    center_y = int((top_safe + bottom_safe) / 2)
    draw.ellipse(
        [int(width * 0.25), center_y - 60, int(width * 0.75), center_y + 60],
        fill=(139, 92, 246),  # Purple 500
        outline=(236, 72, 153)  # Pink 500
    )
    draw.text((int(width * 0.35), center_y - 10), "⚡ 4K PROXY", fill=(255, 255, 255))

    # AI Tag Badges Overlay (Lower half inside safe area)
    badge_y = bottom_safe - 90
    draw.rectangle([margin_x + 10, badge_y, width - margin_x - 10, bottom_safe - 10], fill=(15, 23, 42, 220), outline=(71, 85, 105))
    draw.text((margin_x + 20, badge_y + 8), f"DOMAIN: {domain}", fill=(56, 189, 248))
    draw.text((margin_x + 20, badge_y + 26), f"ENTITY: {entity}", fill=(244, 114, 182))
    draw.text((margin_x + 20, badge_y + 44), f"STATUS: ACTIVE 4K ADB STREAM", fill=(74, 222, 128))
    draw.text((margin_x + 20, badge_y + 62), f"CAPTURED: {timestamp_str}", fill=(148, 163, 184))

    # Save to in-memory bytes
    buf = io.BytesIO()
    fmt = "JPEG" if img_format.upper() in ["JPEG", "JPG"] else "PNG"
    img.save(buf, format=fmt, quality=90 if fmt == "JPEG" else None)
    return buf.getvalue()


def generate_mock_frame_base64(
    width: int = 540,
    height: int = 960,
    img_format: str = "png",
    as_data_uri: bool = True
) -> Tuple[str, str]:
    """
    Generates a procedural mock frame and returns (data_uri, raw_base64).
    """
    raw_bytes = generate_mock_frame(width=width, height=height, img_format=img_format)
    encoded = base64.b64encode(raw_bytes).decode("utf-8")
    mime = "image/jpeg" if img_format.lower() in ["jpeg", "jpg"] else "image/png"
    data_uri = f"data:{mime};base64,{encoded}"
    if as_data_uri:
        return data_uri, encoded
    return encoded, encoded


def generate_mock_mp4(
    output_path: str,
    duration_seconds: float = 2.0,
    width: int = 540,
    height: int = 960,
    fps: int = 30
) -> str:
    """
    Generates a genuine procedural MP4 clip using imageio_ffmpeg and FFmpeg testsrc.
    Zero ghost files — guaranteed to be a playable H.264 video.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    ffmpeg_exe = get_ffmpeg_path()

    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration_seconds}:size={width}x{height}:rate={fps}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg procedural video generation failed: {result.stderr}")

    return os.path.abspath(output_path)


def ensure_mock_video_asset(dest_dir: str, filename: str = "mock_adb_4k_clip.mp4") -> str:
    """
    Ensures a valid procedural MP4 video asset exists in the destination directory.
    """
    os.makedirs(dest_dir, exist_ok=True)
    target_path = os.path.join(dest_dir, filename)
    if not os.path.exists(target_path) or os.path.getsize(target_path) == 0:
        generate_mock_mp4(target_path, duration_seconds=2.0)
    return target_path
