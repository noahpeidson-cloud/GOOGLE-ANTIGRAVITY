"""
Adversarial Stress and Robustness Challenge Test Suite for Milestone 2 (FastAPI Local Daemon Bridge).
Authored by Challenger 2 (Empirical Challenger).
Strict compliance with Rule R2 (Loud Assertions, Zero Discretion) and Rule R16 (Absolute Imports).
"""

import os
import io
import time
import base64
import subprocess
import threading
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from main import app, STAGING_DIR
from adb_service import AdbService
from media_generator import (
    generate_mock_frame,
    generate_mock_frame_base64,
    generate_mock_mp4,
    ensure_mock_video_asset,
    get_ffmpeg_path,
)
from models import (
    AdbPullRequest,
    AdbPullResponse,
    CaptureScreenRequest,
    CaptureScreenResponse,
    DeviceInfo,
    HealthResponse,
    StagingInventoryResponse,
)

ORIGINAL_SUBPROCESS_RUN = subprocess.run


# ==============================================================================
# Group 1: Media Generator Resilience & Edge Cases
# ==============================================================================

@pytest.mark.parametrize("width,height", [
    (400, 600),       # Minimum safe vertical dimension
    (540, 960),       # Standard 9:16 proxy
    (720, 1280),      # 720p HD 9:16
    (1080, 1920),     # Full HD 9:16
    (1440, 2560),     # 2K QHD 9:16
    (2160, 3840),     # 4K UHD 9:16
    (1920, 1080),     # Standard Landscape 16:9
    (400, 1920),      # Ultra-tall tower
    (500, 500),       # 1:1 Square
])
def test_media_generator_supported_resolutions(width, height):
    """Verifies that generate_mock_frame handles supported resolutions and aspect ratios."""
    frame_bytes = generate_mock_frame(width=width, height=height, img_format="PNG")
    assert frame_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    img = Image.open(io.BytesIO(frame_bytes))
    assert img.size == (width, height)
    assert img.format == "PNG"


@pytest.mark.parametrize("width,height", [
    (100, 100),       # Micro square
    (160, 90),        # Micro landscape thumbnail
    (90, 160),        # Micro portrait thumbnail
    (300, 300),       # Sub-400px height boundary
])
def test_media_generator_micro_resolution_boundary_behavior(width, height):
    """
    Exposes and documents boundary behavior for micro-resolutions (height < 400).
    In the current implementation, fixed header coordinates (y=48 vs top_safe=height*0.15)
    cause y1 < y0 when height < 400, raising ValueError in Pillow.
    """
    top_safe = int(height * 0.15)
    if top_safe - 12 < 48:
        with pytest.raises(ValueError, match="y1 must be greater than or equal to y0"):
            generate_mock_frame(width=width, height=height, img_format="PNG")
    else:
        frame_bytes = generate_mock_frame(width=width, height=height, img_format="PNG")
        assert len(frame_bytes) > 0


def test_media_generator_unicode_and_extreme_text_inputs():
    """Verifies HUD overlays handle unicode, emojis, long strings, and empty strings without crashing."""
    test_cases = [
        {"title": "", "domain": "", "entity": "", "ts": ""},
        {"title": "🎧 ULTRA 2026 🔥 EDM FESTIVAL 🚀", "domain": "✨ MUSIC ✨", "entity": "MARTIN GARRIX 🇳🇱", "ts": "2026-08-27 12:00:00 UTC"},
        {"title": "A" * 500, "domain": "B" * 300, "entity": "C" * 400, "ts": "D" * 200},
        {"title": "中文测试 / 日本語テスト / العربية", "domain": "DOMAIN_TEST", "entity": "ENTITY_TEST", "ts": None},
    ]

    for tc in test_cases:
        frame_bytes = generate_mock_frame(
            width=540,
            height=960,
            title=tc["title"],
            domain=tc["domain"],
            entity=tc["entity"],
            timestamp_str=tc["ts"],
            img_format="PNG",
        )
        assert frame_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        img = Image.open(io.BytesIO(frame_bytes))
        assert img.size == (540, 960)


@pytest.mark.parametrize("fmt,expected_header", [
    ("PNG", b"\x89PNG\r\n\x1a\n"),
    ("png", b"\x89PNG\r\n\x1a\n"),
    ("JPEG", b"\xff\xd8"),
    ("jpeg", b"\xff\xd8"),
    ("jpg", b"\xff\xd8"),
    ("JPG", b"\xff\xd8"),
    ("UNKNOWN_FALLBACK", b"\x89PNG\r\n\x1a\n"),  # Non-JPEG falls back to PNG
])
def test_media_generator_format_selection_and_fallback(fmt, expected_header):
    """Verifies that format selection and fallback correctly generate matching byte headers."""
    data = generate_mock_frame(width=540, height=960, img_format=fmt)
    assert data.startswith(expected_header)


def test_media_generator_base64_data_uri_and_raw_integrity():
    """Verifies generate_mock_frame_base64 produces valid data URIs and identical raw base64 payloads."""
    data_uri_png, raw_b64_png = generate_mock_frame_base64(width=540, height=960, img_format="png", as_data_uri=True)
    assert data_uri_png.startswith("data:image/png;base64,")
    assert data_uri_png.split(",", 1)[1] == raw_b64_png

    # Decode and check image integrity
    decoded = base64.b64decode(raw_b64_png)
    img = Image.open(io.BytesIO(decoded))
    assert img.size == (540, 960)
    assert img.format == "PNG"

    data_uri_jpg, raw_b64_jpg = generate_mock_frame_base64(width=540, height=960, img_format="jpeg", as_data_uri=True)
    assert data_uri_jpg.startswith("data:image/jpeg;base64,")
    assert data_uri_jpg.split(",", 1)[1] == raw_b64_jpg


@pytest.mark.parametrize("duration,fps", [
    (0.2, 15),
    (0.5, 30),
    (1.0, 60),
    (2.0, 24),
])
def test_media_generator_procedural_mp4_durations_and_fps(tmp_path, duration, fps):
    """Verifies genuine procedural MP4 generation across various durations and frame rates."""
    out_file = str(tmp_path / f"test_{duration}s_{fps}fps.mp4")
    res_path = generate_mock_mp4(out_file, duration_seconds=duration, width=320, height=480, fps=fps)
    assert os.path.exists(res_path)
    assert os.path.getsize(res_path) > 1000  # Valid MP4 header and frames


def test_media_generator_ensure_mock_video_corrupted_file_recovery(tmp_path):
    """Verifies that ensure_mock_video_asset regenerates 0-byte or corrupted video files."""
    dest_dir = str(tmp_path / "mock_cache")
    os.makedirs(dest_dir, exist_ok=True)
    corrupted_file = os.path.join(dest_dir, "corrupted_clip.mp4")

    # Create a 0-byte corrupted file
    with open(corrupted_file, "wb") as f:
        pass
    assert os.path.getsize(corrupted_file) == 0

    # ensure_mock_video_asset must detect 0-byte and regenerate
    recovered_path = ensure_mock_video_asset(dest_dir, filename="corrupted_clip.mp4")
    assert recovered_path == corrupted_file
    assert os.path.getsize(recovered_path) > 1000


def test_media_generator_invalid_output_path_error_handling(tmp_path):
    """Verifies that generate_mock_mp4 raises RuntimeError if FFmpeg fails or output path is invalid."""
    invalid_path = str(tmp_path / "invalid:folder*name?" / "clip.mp4")
    with pytest.raises((RuntimeError, OSError)):
        generate_mock_mp4(invalid_path, duration_seconds=1.0)


# ==============================================================================
# Group 2: AdbService Subprocess Error Handling & Timeout Resilience
# ==============================================================================

def test_adb_service_timeout_handling_devices_discovery():
    """Verifies that a subprocess timeout during device listing returns an empty list without crashing."""
    service = AdbService()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="adb devices -l", timeout=5)):
        devices = service.list_devices()
        assert devices == []


def test_adb_service_timeout_handling_version_check():
    """Verifies that a subprocess timeout during version check returns None without crashing."""
    service = AdbService()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="adb version", timeout=3)):
        version = service.get_adb_version()
        assert version is None


def test_adb_service_timeout_handling_screen_capture():
    """Verifies that a subprocess timeout during real screen capture falls back to mock capture."""
    service = AdbService()
    mock_devices = [DeviceInfo(serial="device-timeout-1", state="device")]

    with patch.object(service, "list_devices", return_value=mock_devices):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="adb screencap", timeout=10)):
            req = CaptureScreenRequest(mock=False, device_id="device-timeout-1")
            resp = service.capture_screen(req)

            assert resp.success is True
            assert resp.status == "mock_success"
            assert resp.image_base64 is not None
            assert resp.width == 540
            assert resp.height == 960


def test_adb_service_timeout_handling_adb_pull_ls(tmp_path):
    """Verifies that a subprocess timeout during device file listing falls back to mock pull."""
    service = AdbService()
    mock_devices = [DeviceInfo(serial="device-timeout-2", state="device")]

    def selective_mock_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and len(cmd) > 0 and "adb" in str(cmd[0]):
            raise subprocess.TimeoutExpired(cmd="adb shell ls", timeout=5)
        return ORIGINAL_SUBPROCESS_RUN(cmd, *args, **kwargs)

    with patch.object(service, "list_devices", return_value=mock_devices):
        with patch("subprocess.run", side_effect=selective_mock_run):
            req = AdbPullRequest(
                mock=False,
                device_id="device-timeout-2",
                destination_path=str(tmp_path / "timeout_ls_dest")
            )
            resp = service.trigger_pull(req)

            assert resp.success is True
            assert resp.status == "mock_success"
            assert resp.bytes_transferred == 564156416
            assert os.path.exists(resp.file_path)


def test_adb_service_timeout_handling_adb_pull_transfer(tmp_path):
    """Verifies that a subprocess timeout during actual adb pull falls back gracefully to mock pull."""
    service = AdbService()
    mock_devices = [DeviceInfo(serial="device-timeout-3", state="device")]

    def selective_mock_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and len(cmd) > 0 and "adb" in str(cmd[0]):
            if "shell" in cmd:
                mock_res = MagicMock()
                mock_res.returncode = 0
                mock_res.stdout = "/sdcard/DCIM/Camera/VID_2026.mp4\n"
                return mock_res
            elif "pull" in cmd:
                raise subprocess.TimeoutExpired(cmd="adb pull", timeout=30)
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = ""
            return mock_res
        return ORIGINAL_SUBPROCESS_RUN(cmd, *args, **kwargs)

    with patch.object(service, "list_devices", return_value=mock_devices):
        with patch("subprocess.run", side_effect=selective_mock_run):
            req = AdbPullRequest(
                mock=False,
                device_id="device-timeout-3",
                destination_path=str(tmp_path / "staging_timeout")
            )
            resp = service.trigger_pull(req)

            assert resp.success is True
            assert resp.status == "mock_success"
            assert os.path.exists(resp.file_path)


def test_adb_service_corrupted_screencap_binary_stream():
    """Verifies that non-PNG or corrupted stdout from real screencap falls back to mock capture."""
    service = AdbService()
    mock_devices = [DeviceInfo(serial="device-corrupted", state="device")]

    corrupted_outputs = [
        b"error: device unauthorized. Please check the confirmation dialog on your device.\n",
        b"\x00\x00\x00\x00\x00",
        b"GIF89a",  # Wrong format
        b"",        # Empty output
    ]

    for corrupt_bytes in corrupted_outputs:
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = corrupt_bytes

        with patch.object(service, "list_devices", return_value=mock_devices):
            with patch("subprocess.run", return_value=mock_res):
                req = CaptureScreenRequest(mock=False, device_id="device-corrupted")
                resp = service.capture_screen(req)

                assert resp.success is True
                assert resp.status == "mock_success"
                assert resp.image_base64.startswith("data:image/png;base64,")


def test_adb_service_device_state_filtering():
    """Verifies that only devices in state='device' are considered active and connected."""
    service = AdbService()
    mock_raw_output = (
        "List of devices attached\n"
        "serial_online          device product:pixel8 model:Pixel_8 device:shiba\n"
        "serial_unauth          unauthorized\n"
        "serial_offline         offline\n"
        "serial_recovery        recovery\n"
        "serial_noperm          no permissions (missing udev rules?)\n"
    )

    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = mock_raw_output

    with patch("subprocess.run", return_value=mock_res):
        devices = service.list_devices()
        assert len(devices) == 5

        # is_device_connected should only match serial_online
        is_conn, active_serial = service.is_device_connected()
        assert is_conn is True
        assert active_serial == "serial_online"

        # Explicit target query
        is_conn_online, _ = service.is_device_connected("serial_online")
        assert is_conn_online is True

        is_conn_unauth, _ = service.is_device_connected("serial_unauth")
        assert is_conn_unauth is False

        is_conn_offline, _ = service.is_device_connected("serial_offline")
        assert is_conn_offline is False


def test_adb_service_targeted_device_serial_selection():
    """Verifies that requesting a specific connected device selects that exact device."""
    service = AdbService()
    mock_raw_output = (
        "List of devices attached\n"
        "device_alpha          device product:phone_a model:Phone_A\n"
        "device_beta           device product:phone_b model:Phone_B\n"
    )

    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = mock_raw_output

    with patch("subprocess.run", return_value=mock_res):
        is_conn, serial = service.is_device_connected("device_beta")
        assert is_conn is True
        assert serial == "device_beta"

        is_conn_missing, serial_missing = service.is_device_connected("device_gamma_nonexistent")
        assert is_conn_missing is False
        assert serial_missing is None


def test_adb_service_subprocess_permission_denied_or_missing_binary():
    """Verifies that FileNotFoundError or PermissionError during subprocess calls is handled cleanly."""
    service = AdbService(adb_path="/nonexistent/path/to/adb")

    with patch("subprocess.run", side_effect=FileNotFoundError("No such file or directory: 'adb'")):
        devices = service.list_devices()
        assert devices == []

        version = service.get_adb_version()
        assert version is None

        req = CaptureScreenRequest(mock=False)
        resp = service.capture_screen(req)
        assert resp.success is True
        assert resp.status == "mock_success"


def test_adb_service_real_pull_with_no_files_found(tmp_path):
    """Verifies that when device ls returns no files, pull falls back to mock generation cleanly."""
    service = AdbService()
    mock_devices = [DeviceInfo(serial="device-empty", state="device")]

    def selective_mock_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and len(cmd) > 0 and "adb" in str(cmd[0]):
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = "ls: /sdcard/DCIM/Camera/*.mp4: No such file or directory\n"
            return mock_res
        return ORIGINAL_SUBPROCESS_RUN(cmd, *args, **kwargs)

    with patch.object(service, "list_devices", return_value=mock_devices):
        with patch("subprocess.run", side_effect=selective_mock_run):
            req = AdbPullRequest(
                mock=False,
                device_id="device-empty",
                destination_path=str(tmp_path / "pulled_empty")
            )
            resp = service.trigger_pull(req)

            assert resp.success is True
            assert resp.status == "mock_success"
            assert os.path.exists(resp.file_path)


# ==============================================================================
# Group 3: Staging Directory File Inventory & Cache Isolation
# ==============================================================================

def test_staging_inventory_empty_and_nonexistent_directory(tmp_path):
    """Verifies staging inventory returns 0 files when directory is empty or nonexistent."""
    empty_dir = str(tmp_path / "empty_staging")
    os.makedirs(empty_dir, exist_ok=True)

    with patch("main.STAGING_DIR", empty_dir):
        with TestClient(app) as test_client:
            res = test_client.get("/api/staging")
            assert res.status_code == 200
            data = res.json()
            assert data["count"] == 0
            assert data["total_size_bytes"] == 0
            assert data["files"] == []

    nonexistent_dir = str(tmp_path / "nonexistent_staging")
    with patch("main.STAGING_DIR", nonexistent_dir):
        with TestClient(app) as test_client:
            res = test_client.get("/api/staging")
            assert res.status_code == 200
            data = res.json()
            assert data["count"] == 0
            assert data["total_size_bytes"] == 0


def test_staging_inventory_nested_hierarchy_and_types(tmp_path):
    """Verifies recursive staging inventory across nested subdirectories and media type resolution."""
    staging_root = str(tmp_path / "staging_complex")
    vid_dir = os.path.join(staging_root, "videos")
    screen_dir = os.path.join(staging_root, "screenshots", "nested")
    other_dir = os.path.join(staging_root, "misc")

    os.makedirs(vid_dir, exist_ok=True)
    os.makedirs(screen_dir, exist_ok=True)
    os.makedirs(other_dir, exist_ok=True)

    # Create dummy files
    f1 = os.path.join(vid_dir, "clip1.mp4")
    with open(f1, "wb") as f:
        f.write(b"0" * 1024)

    f2 = os.path.join(screen_dir, "screen1.png")
    with open(f2, "wb") as f:
        f.write(b"0" * 2048)

    f3 = os.path.join(other_dir, "meta.json")
    with open(f3, "wb") as f:
        f.write(b"0" * 512)

    with patch("main.STAGING_DIR", staging_root):
        with TestClient(app) as test_client:
            res = test_client.get("/api/staging")
            assert res.status_code == 200
            data = res.json()

            assert data["count"] == 3
            assert data["total_size_bytes"] == 1024 + 2048 + 512

            files_by_name = {f["filename"]: f for f in data["files"]}
            assert "clip1.mp4" in files_by_name
            assert files_by_name["clip1.mp4"]["media_type"] == "video/mp4"
            assert files_by_name["clip1.mp4"]["size_bytes"] == 1024

            assert "screen1.png" in files_by_name
            assert files_by_name["screen1.png"]["media_type"] == "image/png"
            assert files_by_name["screen1.png"]["size_bytes"] == 2048

            assert "meta.json" in files_by_name
            assert files_by_name["meta.json"]["media_type"] == "application/octet-stream"


def test_staging_inventory_os_stat_error_resilience(tmp_path):
    """Verifies that an individual file failing os.stat does not crash the entire inventory endpoint."""
    staging_root = str(tmp_path / "staging_stat_error")
    os.makedirs(staging_root, exist_ok=True)

    f1 = os.path.join(staging_root, "good.mp4")
    with open(f1, "wb") as f:
        f.write(b"0" * 500)

    f2 = os.path.join(staging_root, "unreadable.mp4")
    with open(f2, "wb") as f:
        f.write(b"0" * 300)

    original_stat = os.stat

    def mock_stat(path, *args, **kwargs):
        if "unreadable.mp4" in str(path):
            raise OSError("Simulated permission / locked file error")
        return original_stat(path, *args, **kwargs)

    with patch("os.stat", side_effect=mock_stat):
        with patch("main.STAGING_DIR", staging_root):
            with TestClient(app) as test_client:
                res = test_client.get("/api/staging")
                assert res.status_code == 200
                data = res.json()
                assert data["count"] == 1
                assert data["files"][0]["filename"] == "good.mp4"


def test_staging_cache_isolation_across_custom_destinations(tmp_path):
    """Verifies that pull operations to custom destination directories remain completely isolated."""
    service = AdbService()
    dir_a = str(tmp_path / "staging_dir_a")
    dir_b = str(tmp_path / "staging_dir_b")

    req_a = AdbPullRequest(mock=True, destination_path=dir_a)
    resp_a = service.trigger_pull(req_a)

    req_b = AdbPullRequest(mock=True, destination_path=dir_b)
    resp_b = service.trigger_pull(req_b)

    assert resp_a.file_path != resp_b.file_path
    assert os.path.dirname(resp_a.file_path) == os.path.abspath(dir_a)
    assert os.path.dirname(resp_b.file_path) == os.path.abspath(dir_b)
    assert os.path.exists(resp_a.file_path)
    assert os.path.exists(resp_b.file_path)


def test_staging_video_asset_idempotency_and_no_unnecessary_regeneration(tmp_path):
    """Verifies that ensure_mock_video_asset does not re-encode if file already exists."""
    target_dir = str(tmp_path / "idempotent_test")
    p1 = ensure_mock_video_asset(target_dir, filename="idempotent.mp4")
    mtime1 = os.path.getmtime(p1)

    # Call 5 times in quick succession
    for _ in range(5):
        p2 = ensure_mock_video_asset(target_dir, filename="idempotent.mp4")
        assert p1 == p2
        assert os.path.getmtime(p2) == mtime1


# ==============================================================================
# Group 4: API Endpoint Robustness & Payload Fuzzing
# ==============================================================================

@pytest.mark.parametrize("limit_val,expected_status", [
    (1, 200),
    (50, 200),
    (100, 200),
    (0, 422),     # ge=1 violation
    (101, 422),   # le=100 violation
    (-1, 422),    # negative violation
])
def test_api_fuzzing_adb_pull_boundary_limits(client: TestClient, limit_val, expected_status):
    """Verifies Pydantic schema validation boundaries on limit parameter."""
    res = client.post("/api/trigger-adb-pull", json={"limit": limit_val, "mock": True})
    assert res.status_code == expected_status


def test_api_fuzzing_special_characters_in_paths(client: TestClient, tmp_path):
    """Verifies handling of special characters, spaces, and path formats in request payloads."""
    custom_dest = str(tmp_path / "My Special Folder (2026) #1" / "Sub Dir")
    payload = {
        "source_path": "/sdcard/DCIM/Camera/Special Folder 2026/*.mp4",
        "destination_path": custom_dest,
        "mock": True
    }
    res = client.post("/api/trigger-adb-pull", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert os.path.exists(data["file_path"])
    assert "My Special Folder (2026) #1" in data["file_path"]


def test_api_cors_preflight_and_wildcard_headers(client: TestClient):
    """Verifies CORS preflight OPTIONS requests across various client origins."""
    test_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://custom-client.local",
    ]

    for origin in test_origins:
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Authorization"
        }
        res = client.options("/api/trigger-adb-pull", headers=headers)
        assert res.status_code == 200
        assert "access-control-allow-origin" in res.headers
        assert "access-control-allow-methods" in res.headers


def test_api_concurrent_requests_stress(client: TestClient):
    """Verifies daemon stability under concurrent multi-threaded endpoint invocations."""
    results = []
    errors = []

    def worker(idx: int):
        try:
            if idx % 3 == 0:
                res = client.get("/api/health")
            elif idx % 3 == 1:
                res = client.post("/api/capture-screen", json={"mock": True})
            else:
                res = client.post("/api/trigger-adb-pull", json={"mock": True})

            results.append((idx, res.status_code))
        except Exception as e:
            errors.append((idx, str(e)))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Encountered errors in concurrent stress test: {errors}"
    assert len(results) == 20
    for idx, status_code in results:
        assert status_code == 200
