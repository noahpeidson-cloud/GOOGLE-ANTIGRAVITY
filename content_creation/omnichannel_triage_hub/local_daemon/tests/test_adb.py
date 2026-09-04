"""
Unit tests for AdbService and procedural media generation.
Strict compliance with Rule R2 (Deterministic testing with loud assertions).
"""

import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from adb_service import AdbService
from media_generator import (
    generate_mock_frame,
    generate_mock_frame_base64,
    generate_mock_mp4,
    ensure_mock_video_asset,
    get_ffmpeg_path,
)
from models import AdbPullRequest, CaptureScreenRequest


def test_ffmpeg_binary_exists():
    """Verifies that the FFmpeg binary is located and executable."""
    ffmpeg_exe = get_ffmpeg_path()
    assert os.path.exists(ffmpeg_exe), f"FFmpeg executable not found at: {ffmpeg_exe}"
    res = subprocess.run([ffmpeg_exe, "-version"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "ffmpeg version" in res.stdout


def test_procedural_mock_frame_generation():
    """Verifies that generate_mock_frame produces valid PNG and JPEG bytes."""
    png_bytes = generate_mock_frame(width=540, height=960, img_format="PNG")
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    jpeg_bytes = generate_mock_frame(width=540, height=960, img_format="JPEG")
    assert jpeg_bytes.startswith(b"\xff\xd8")


def test_procedural_mp4_generation(tmp_path):
    """Verifies genuine procedural MP4 generation via imageio_ffmpeg."""
    test_mp4 = str(tmp_path / "test_clip.mp4")
    out_path = generate_mock_mp4(test_mp4, duration_seconds=1.0, width=320, height=480, fps=24)
    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 0


def test_ensure_mock_video_asset(tmp_path):
    """Verifies ensure_mock_video_asset creates and reuses video files."""
    dest_dir = str(tmp_path / "videos")
    path1 = ensure_mock_video_asset(dest_dir, "clip1.mp4")
    assert os.path.exists(path1)
    mtime1 = os.path.getmtime(path1)

    # Calling again should reuse without error
    path2 = ensure_mock_video_asset(dest_dir, "clip1.mp4")
    assert path1 == path2
    assert os.path.getmtime(path2) == mtime1


def test_adb_service_mock_capture_screen():
    """Verifies AdbService.capture_screen fallback mode."""
    service = AdbService()
    req = CaptureScreenRequest(mock=True, format="png")
    resp = service.capture_screen(req)

    assert resp.success is True
    assert resp.status == "mock_success"
    assert resp.width == 540
    assert resp.height == 960
    assert resp.image_base64 is not None
    assert resp.image_base64.startswith("data:image/png;base64,")


def test_adb_service_mock_trigger_pull(tmp_path):
    """Verifies AdbService.trigger_pull in mock fallback mode."""
    service = AdbService()
    req = AdbPullRequest(
        mock=True,
        destination_path=str(tmp_path / "pulled_videos")
    )
    resp = service.trigger_pull(req)

    assert resp.success is True
    assert resp.status == "mock_success"
    assert resp.bytes_transferred == 564156416
    assert resp.total_bytes == 97173897216
    assert resp.file_path is not None
    assert os.path.exists(resp.file_path)
    assert len(resp.pulled_files) == 1
    assert resp.pulled_files[0].is_mock is True


def test_adb_service_with_simulated_real_device(tmp_path):
    """Verifies real ADB execution path when a physical device is present."""
    service = AdbService()

    mock_devices_output = (
        "List of devices attached\n"
        "emulator-5554          device product:sdk_gphone64_x86_64 model:sdk_gphone64_x86_64 device:emu64x\n"
    )

    # Generate a small valid PNG to return from screencap
    valid_png = generate_mock_frame(width=1080, height=1920, img_format="PNG")

    def mock_subprocess_run(cmd, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.returncode = 0

        if "devices" in cmd:
            mock_res.stdout = mock_devices_output
        elif "screencap" in cmd:
            mock_res.stdout = valid_png
        elif "version" in cmd:
            mock_res.stdout = "Android Debug Bridge version 1.0.41\n"
        else:
            mock_res.stdout = ""
        return mock_res

    with patch("subprocess.run", side_effect=mock_subprocess_run):
        # 1. Test device discovery
        devices = service.list_devices()
        assert len(devices) == 1
        assert devices[0].serial == "emulator-5554"
        assert devices[0].model == "sdk_gphone64_x86_64"

        # 2. Test real screen capture
        cap_req = CaptureScreenRequest(mock=False, save_to_file=True, save_dir=str(tmp_path / "screens"))
        cap_resp = service.capture_screen(cap_req)

        assert cap_resp.success is True
        assert cap_resp.status == "success"
        assert cap_resp.device_id == "emulator-5554"
        assert cap_resp.width == 1080
        assert cap_resp.height == 1920
        assert cap_resp.file_path is not None
        assert os.path.exists(cap_resp.file_path)


def test_adb_service_graceful_error_handling():
    """Verifies that subprocess failures fall back gracefully to mock mode."""
    service = AdbService(adb_path="non_existent_adb_binary_xyz")

    # Devices listing should return empty list without raising
    devices = service.list_devices()
    assert devices == []

    # Capture screen should fall back to mock
    req = CaptureScreenRequest(mock=False)
    resp = service.capture_screen(req)
    assert resp.success is True
    assert resp.status == "mock_success"
