"""
Integration and functional API tests for FastAPI Local Daemon Bridge.
Strict compliance with Rule R2 (Loud Assertions, Zero-Discretion).
"""

import os
import base64
import pytest
from fastapi.testclient import TestClient
from PIL import Image
import io


def test_read_root(client: TestClient):
    """Verifies root endpoint returns online status."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "version" in data
    assert "service" in data


def test_get_health(client: TestClient):
    """Verifies /api/health returns valid schema and status."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert isinstance(data["adb_connected"], bool)
    assert isinstance(data["device_count"], int)
    assert isinstance(data["devices"], list)
    assert data["mock_available"] is True
    assert "uptime_seconds" in data
    assert "timestamp" in data


def test_trigger_adb_pull_default(client: TestClient):
    """Verifies /api/trigger-adb-pull executes with default options."""
    res = client.post("/api/trigger-adb-pull", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] in ["success", "mock_success"]
    assert data["bytes_transferred"] > 0
    assert data["total_bytes"] > 0
    assert data["file_path"] is not None
    assert os.path.exists(data["file_path"]), f"File does not exist: {data['file_path']}"


def test_trigger_adb_pull_explicit_mock(client: TestClient):
    """Verifies /api/trigger-adb-pull with mock=True produces expected simulation metrics."""
    payload = {
        "mock": True,
        "destination_path": "./staging/videos",
        "limit": 5
    }
    res = client.post("/api/trigger-adb-pull", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "mock_success"
    # Verify exact metric specifications (538 MB simulated clip, 90.5 GB total storage)
    assert data["bytes_transferred"] == 564156416
    assert data["total_bytes"] == 97173897216
    assert len(data["pulled_files"]) == 1
    assert data["pulled_files"][0]["is_mock"] is True
    assert os.path.exists(data["file_path"])


def test_capture_screen_default_png(client: TestClient):
    """Verifies /api/capture-screen returns a valid 9:16 Base64 PNG image."""
    res = client.post("/api/capture-screen", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] in ["success", "mock_success"]
    assert data["image_base64"].startswith("data:image/png;base64,")
    assert data["width"] == 540
    assert data["height"] == 960

    # Verify base64 is genuine decodable PNG image
    raw_b64 = data["image_base64"].split(",", 1)[1]
    img_bytes = base64.b64decode(raw_b64)
    img = Image.open(io.BytesIO(img_bytes))
    assert img.size == (540, 960)
    assert img.format == "PNG"


def test_capture_screen_jpeg_format(client: TestClient):
    """Verifies /api/capture-screen with format='jpeg' returns a valid JPEG."""
    res = client.post("/api/capture-screen", json={"format": "jpeg", "mock": True})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["image_base64"].startswith("data:image/jpeg;base64,")

    raw_b64 = data["image_base64"].split(",", 1)[1]
    img_bytes = base64.b64decode(raw_b64)
    img = Image.open(io.BytesIO(img_bytes))
    assert img.size == (540, 960)
    assert img.format == "JPEG"


def test_capture_screen_save_to_file(client: TestClient):
    """Verifies /api/capture-screen with save_to_file=True writes image to disk."""
    payload = {
        "format": "png",
        "mock": True,
        "save_to_file": True,
        "save_dir": "./staging/screenshots"
    }
    res = client.post("/api/capture-screen", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["file_path"] is not None
    assert os.path.exists(data["file_path"])
    assert os.path.getsize(data["file_path"]) > 0


def test_cors_preflight_options(client: TestClient):
    """Verifies CORS preflight headers for React Vite frontend (localhost:5173)."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type"
    }
    res = client.options("/api/trigger-adb-pull", headers=headers)
    assert res.status_code == 200
    assert "access-control-allow-origin" in res.headers
    assert res.headers["access-control-allow-origin"] in ["http://localhost:5173", "*"]


def test_get_devices(client: TestClient):
    """Verifies /api/devices returns a list."""
    res = client.get("/api/devices")
    assert res.status_code == 200
    data = res.json()
    assert "devices" in data
    assert "count" in data
    assert isinstance(data["devices"], list)


def test_get_staging_inventory(client: TestClient):
    """Verifies /api/staging returns staged files."""
    res = client.get("/api/staging")
    assert res.status_code == 200
    data = res.json()
    assert "files" in data
    assert "total_size_bytes" in data
    assert "count" in data


def test_invalid_payload_validation_error(client: TestClient):
    """Verifies invalid types trigger 422 Unprocessable Entity."""
    res = client.post("/api/trigger-adb-pull", json={"limit": "not_an_int"})
    assert res.status_code == 422


def test_404_not_found(client: TestClient):
    """Verifies non-existent endpoints return 404."""
    res = client.get("/api/invalid-endpoint-xyz")
    assert res.status_code == 404
