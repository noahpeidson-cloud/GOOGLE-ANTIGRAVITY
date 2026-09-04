"""
Adversarial Challenge Test Suite for Milestone 2 (FastAPI Local Daemon Bridge).
Rigorous empirical stress-testing for ADB pull, screen capture, CORS, health, staging inventory,
boundary conditions, input validation, base64 decoding, concurrency, and error handling.
Strict compliance with Rule R2 (Loud Assertions, Zero-Discretion).
"""

import os
import io
import time
import base64
import shutil
import pytest
import concurrent.futures
from typing import List
from PIL import Image
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import app
from models import (
    AdbPullRequest,
    AdbPullResponse,
    CaptureScreenRequest,
    CaptureScreenResponse,
    HealthResponse,
    DevicesResponse,
    StagingInventoryResponse,
)
from adb_service import AdbService
from media_generator import generate_mock_frame, generate_mock_mp4


@pytest.fixture
def client():
    """Provides a clean TestClient for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


# ============================================================================
# Category 1: POST /api/trigger-adb-pull Adversarial & Edge Case Tests
# ============================================================================

def test_trigger_adb_pull_boundary_limits_low(client: TestClient):
    """Challenge: limit < 1 must be rejected with 422 Unprocessable Entity."""
    res_zero = client.post("/api/trigger-adb-pull", json={"limit": 0})
    assert res_zero.status_code == 422, f"Expected 422 for limit=0, got {res_zero.status_code}"

    res_neg = client.post("/api/trigger-adb-pull", json={"limit": -5})
    assert res_neg.status_code == 422, f"Expected 422 for limit=-5, got {res_neg.status_code}"


def test_trigger_adb_pull_boundary_limits_high(client: TestClient):
    """Challenge: limit > 100 must be rejected with 422 Unprocessable Entity."""
    res_high = client.post("/api/trigger-adb-pull", json={"limit": 101})
    assert res_high.status_code == 422, f"Expected 422 for limit=101, got {res_high.status_code}"

    res_huge = client.post("/api/trigger-adb-pull", json={"limit": 99999})
    assert res_huge.status_code == 422, f"Expected 422 for limit=99999, got {res_huge.status_code}"


def test_trigger_adb_pull_valid_boundary_limits(client: TestClient, tmp_path):
    """Challenge: limit=1 and limit=100 must succeed."""
    dest_dir = str(tmp_path / "boundary_test")
    res_min = client.post("/api/trigger-adb-pull", json={"limit": 1, "mock": True, "destination_path": dest_dir})
    assert res_min.status_code == 200
    assert res_min.json()["success"] is True

    res_max = client.post("/api/trigger-adb-pull", json={"limit": 100, "mock": True, "destination_path": dest_dir})
    assert res_max.status_code == 200
    assert res_max.json()["success"] is True


def test_trigger_adb_pull_field_aliasing_and_precedence(client: TestClient, tmp_path):
    """
    Challenge: verify field alias resolution and precedence:
    - source_path vs device_path
    - destination_path vs local_dest
    """
    dest_explicit = str(tmp_path / "dest_explicit")
    dest_alias = str(tmp_path / "dest_alias")

    # 1. Using alias device_path and local_dest
    res_alias = client.post("/api/trigger-adb-pull", json={
        "device_path": "/sdcard/Movies/Test",
        "local_dest": dest_alias,
        "mock": True
    })
    assert res_alias.status_code == 200
    data_alias = res_alias.json()
    assert data_alias["success"] is True
    assert os.path.exists(dest_alias)

    # 2. Both specified: destination_path must take precedence
    res_both = client.post("/api/trigger-adb-pull", json={
        "source_path": "/sdcard/DCIM/Primary",
        "device_path": "/sdcard/DCIM/Secondary",
        "destination_path": dest_explicit,
        "local_dest": dest_alias,
        "mock": True
    })
    assert res_both.status_code == 200
    data_both = res_both.json()
    assert data_both["success"] is True
    assert os.path.exists(dest_explicit)
    assert data_both["file_path"].startswith(os.path.abspath(dest_explicit))


def test_trigger_adb_pull_deeply_nested_destination(client: TestClient, tmp_path):
    """Challenge: auto-creation of deeply nested destination directories without crashing."""
    deep_path = str(tmp_path / "a" / "b" / "c" / "d" / "e" / "videos")
    res = client.post("/api/trigger-adb-pull", json={
        "destination_path": deep_path,
        "mock": True
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert os.path.exists(deep_path)
    assert os.path.exists(data["file_path"])


def test_trigger_adb_pull_nonexistent_device_serial(client: TestClient, tmp_path):
    """Challenge: target nonexistent device_id with mock=False falls back cleanly to mock without 500."""
    res = client.post("/api/trigger-adb-pull", json={
        "device_id": "ghost_serial_99999",
        "mock": False,
        "destination_path": str(tmp_path / "ghost_pull")
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] in ["mock_success", "success"]
    assert data["file_path"] is not None
    assert os.path.exists(data["file_path"])


def test_trigger_adb_pull_extra_fields_ignored(client: TestClient):
    """Challenge: unknown/extra fields in JSON payload must not trigger 500 error."""
    payload = {
        "mock": True,
        "unexpected_extra_field_123": "injected_value",
        "malicious_sql_drop": "DROP TABLE video_tags;"
    }
    res = client.post("/api/trigger-adb-pull", json=payload)
    assert res.status_code == 200
    assert res.json()["success"] is True


# ============================================================================
# Category 2: POST /api/capture-screen Adversarial & Image Integrity Tests
# ============================================================================

def test_capture_screen_base64_exact_decoding_png(client: TestClient):
    """
    Challenge: Base64 payload must decode into an authentic, uncorrupted PNG image
    matching exact 540x960 9:16 aspect ratio with valid color channels.
    """
    res = client.post("/api/capture-screen", json={"format": "png", "mock": True})
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert data["status"] == "mock_success"
    assert data["width"] == 540
    assert data["height"] == 960

    # Data URI format verification
    assert data["image_base64"] is not None
    assert data["image_base64"].startswith("data:image/png;base64,")

    # Raw base64 consistency check
    raw_b64 = data["raw_base64"]
    assert raw_b64 is not None
    expected_from_uri = data["image_base64"].split(",", 1)[1]
    assert raw_b64 == expected_from_uri

    # Decode and inspect image metadata
    img_bytes = base64.b64decode(raw_b64)
    assert img_bytes.startswith(b"\x89PNG\r\n\x1a\n"), "Missing PNG magic bytes"

    img = Image.open(io.BytesIO(img_bytes))
    assert img.format == "PNG"
    assert img.size == (540, 960)
    assert img.mode in ["RGB", "RGBA"]

    # Verify aspect ratio is exactly 9:16 (540/960 = 0.5625)
    aspect_ratio = img.width / img.height
    assert abs(aspect_ratio - (9 / 16)) < 1e-4


def test_capture_screen_base64_exact_decoding_jpeg(client: TestClient):
    """
    Challenge: JPEG format output must be valid JPEG with correct MIME type and decodability.
    """
    res = client.post("/api/capture-screen", json={"format": "jpeg", "mock": True})
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert data["image_base64"].startswith("data:image/jpeg;base64,")

    raw_b64 = data["raw_base64"]
    img_bytes = base64.b64decode(raw_b64)
    assert img_bytes.startswith(b"\xff\xd8"), "Missing JPEG SOI magic bytes"

    img = Image.open(io.BytesIO(img_bytes))
    assert img.format == "JPEG"
    assert img.size == (540, 960)


def test_capture_screen_case_insensitive_format_handling(client: TestClient):
    """Challenge: uppercase and mixed case format strings (PNG, JPEG, Jpg, pNg) must work."""
    for fmt_str in ["PNG", "JPEG", "Jpg", "pNg", "JPG"]:
        res = client.post("/api/capture-screen", json={"format": fmt_str, "mock": True})
        assert res.status_code == 200, f"Failed for format={fmt_str}"
        data = res.json()
        assert data["success"] is True
        assert data["width"] == 540
        assert data["height"] == 960


def test_capture_screen_unsupported_format_graceful_fallback(client: TestClient):
    """Challenge: unsupported formats (e.g. 'webp', 'bmp', 'invalid_xyz') must fallback gracefully without 500."""
    res = client.post("/api/capture-screen", json={"format": "invalid_format_xyz", "mock": True})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["image_base64"] is not None


def test_capture_screen_save_to_custom_directory(client: TestClient, tmp_path):
    """Challenge: verify physical file writing to custom directory when save_to_file=True."""
    custom_dir = str(tmp_path / "custom_screenshots")
    res = client.post("/api/capture-screen", json={
        "format": "png",
        "mock": True,
        "save_to_file": True,
        "save_dir": custom_dir
    })
    assert res.status_code == 200
    data = res.json()
    assert data["file_path"] is not None
    assert os.path.exists(data["file_path"])
    assert os.path.getsize(data["file_path"]) > 0

    # Ensure written file is authentic PNG
    with open(data["file_path"], "rb") as f:
        file_bytes = f.read()
    assert file_bytes.startswith(b"\x89PNG")


def test_capture_screen_no_save_when_false(client: TestClient):
    """Challenge: when save_to_file=False and save_dir is default, file_path may be None or empty."""
    res = client.post("/api/capture-screen", json={"mock": True, "save_to_file": False, "save_dir": None})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True


# ============================================================================
# Category 3: Health & Device Monitoring Adversarial Tests
# ============================================================================

def test_health_endpoint_contract_and_uptime_monotonicity(client: TestClient):
    """
    Challenge: /api/health must satisfy exact schema requirements and uptime must increase.
    """
    res1 = client.get("/api/health")
    assert res1.status_code == 200
    data1 = res1.json()

    # Validate against HealthResponse model
    health1 = HealthResponse(**data1)
    assert health1.status == "ok"
    assert health1.mock_available is True
    assert isinstance(health1.devices, list)
    assert isinstance(health1.device_count, int)
    assert health1.device_count == len(health1.devices)

    time.sleep(0.05)

    res2 = client.get("/api/health")
    assert res2.status_code == 200
    data2 = res2.json()
    health2 = HealthResponse(**data2)

    # Uptime should be strictly >= previous call
    assert health2.uptime_seconds >= health1.uptime_seconds


def test_devices_endpoint_contract(client: TestClient):
    """Challenge: /api/devices must return DevicesResponse schema."""
    res = client.get("/api/devices")
    assert res.status_code == 200
    data = res.json()
    devices_resp = DevicesResponse(**data)
    assert devices_resp.count == len(devices_resp.devices)
    assert isinstance(devices_resp.devices, list)


# ============================================================================
# Category 4: CORS Preflight & Security Headers Adversarial Tests
# ============================================================================

@pytest.mark.parametrize("origin", [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
])
def test_cors_preflight_for_supported_origins(client: TestClient, origin: str):
    """Challenge: CORS preflight must permit all configured frontend origins."""
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type, Authorization, X-Requested-With",
    }
    res = client.options("/api/trigger-adb-pull", headers=headers)
    assert res.status_code == 200
    assert "access-control-allow-origin" in res.headers
    allowed_origin = res.headers["access-control-allow-origin"]
    assert allowed_origin in [origin, "*"]


def test_cors_actual_request_headers(client: TestClient):
    """Challenge: Actual GET and POST requests from localhost:5173 include CORS headers."""
    headers = {"Origin": "http://localhost:5173"}

    res_get = client.get("/api/health", headers=headers)
    assert res_get.status_code == 200
    assert "access-control-allow-origin" in res_get.headers
    assert res_get.headers["access-control-allow-origin"] in ["http://localhost:5173", "*"]

    res_post = client.post("/api/capture-screen", json={"mock": True}, headers=headers)
    assert res_post.status_code == 200
    assert "access-control-allow-origin" in res_post.headers


# ============================================================================
# Category 5: Concurrency & Stress Tests
# ============================================================================

def test_concurrent_api_requests(client: TestClient, tmp_path):
    """
    Challenge: Execute 20 concurrent requests across health, capture, and pull endpoints.
    Verifies no race conditions, socket leaks, or unhandled file lock collisions.
    """
    dest_dir = str(tmp_path / "concurrent_dest")

    def make_request(req_id: int):
        if req_id % 3 == 0:
            return client.get("/api/health")
        elif req_id % 3 == 1:
            return client.post("/api/capture-screen", json={"mock": True, "format": "png"})
        else:
            return client.post("/api/trigger-adb-pull", json={"mock": True, "destination_path": dest_dir})

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(make_request, i) for i in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 20
    for r in results:
        assert r.status_code == 200, f"Request failed with status {r.status_code}: {r.text}"


# ============================================================================
# Category 6: Staging Inventory Verification
# ============================================================================

def test_staging_inventory_accuracy(client: TestClient, tmp_path):
    """
    Challenge: /api/staging must accurately report files, sizes, and media types.
    """
    # Trigger a pull to create a video
    video_dest = "./staging/videos"
    client.post("/api/trigger-adb-pull", json={"mock": True, "destination_path": video_dest})

    # Trigger a capture to create a screenshot
    screenshot_dest = "./staging/screenshots"
    client.post("/api/capture-screen", json={
        "mock": True,
        "format": "png",
        "save_to_file": True,
        "save_dir": screenshot_dest
    })

    res = client.get("/api/staging")
    assert res.status_code == 200
    data = res.json()
    inventory = StagingInventoryResponse(**data)

    assert inventory.count >= 2
    assert inventory.total_size_bytes > 0
    assert len(inventory.files) == inventory.count

    # Verify media types
    media_types = [f.media_type for f in inventory.files]
    assert "video/mp4" in media_types or any("mp4" in f.filename for f in inventory.files)
