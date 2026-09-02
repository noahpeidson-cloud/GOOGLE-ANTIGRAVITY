"""
Adversarial Empirical Challenge Test Suite for Milestone 4 (E2E Integration & Verification)
Omnichannel Triage Hub

Challenger 1 Adversarial Coverage:
1. Rapid concurrent ADB trigger requests (in-memory Base64 capture, UI-throttled pulling, file I/O contention analysis).
2. CORS headers under multiple origins (localhost:5173, 127.0.0.1:5173, localhost:3000, 127.0.0.1:3000, preflight OPTIONS, header permutations).
3. Base64 screenshot format conversions (PNG, JPEG, byte header verification, dimensions, raw vs data-URI).
4. Boundary injection and security fuzzing (command injection fuzzing, traversal attempts, Pydantic validation boundaries).
5. Staging inventory and file system resilience under rapid writes and missing folders.

Strict compliance with Rule R16 (Absolute imports) and Rule R2 (Zero-Discretion Deterministic Verification).
"""

import os
import sys
import io
import time
import base64
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

import pytest
from PIL import Image
from fastapi.testclient import TestClient

# Resolve paths
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
DAEMON_DIR = REPO_ROOT / "local_daemon"
FRONTEND_DIR = REPO_ROOT / "frontend"
DATACONNECT_DIR = REPO_ROOT / "dataconnect"
STAGING_DIR = REPO_ROOT / "staging"

# Add local_daemon to sys.path
if str(DAEMON_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_DIR))

from main import app
from models import (
    AdbPullRequest,
    AdbPullResponse,
    CaptureScreenRequest,
    CaptureScreenResponse,
    HealthResponse,
    StagingInventoryResponse,
)
from adb_service import adb_service


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """Synchronous test client for FastAPI local daemon."""
    with TestClient(app) as client:
        yield client


# ==============================================================================
# SECTION 1: RAPID CONCURRENT ADB TRIGGER REQUESTS & STRESS HARNESS
# ==============================================================================

class TestConcurrentAdbTriggerStress:
    """Stress tests rapid concurrent requests against the FastAPI local daemon."""

    def test_rapid_concurrent_inmemory_screen_captures(self, api_client: TestClient):
        """Dispatches 20 concurrent in-memory Base64 screen captures (with save_dir=None)."""
        def make_capture(req_id: int):
            fmt = "png" if req_id % 2 == 0 else "jpeg"
            res = api_client.post(
                "/api/capture-screen",
                json={"mock": True, "format": fmt, "save_dir": None, "save_to_file": False},
            )
            return res.status_code, res.json(), fmt

        concurrency = 20
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(make_capture, i) for i in range(concurrency)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == concurrency
        for status_code, data, fmt in results:
            assert status_code == 200
            assert data["success"] is True
            assert data["width"] == 540
            assert data["height"] == 960
            expected_prefix = f"data:image/{'jpeg' if fmt == 'jpeg' else 'png'};base64,"
            assert data["image_base64"].startswith(expected_prefix)

    def test_concurrent_screen_captures_default_no_disk_writes(self, api_client: TestClient):
        """Dispatches 20 concurrent screen captures with default parameters (save_to_file=False)."""
        def make_capture(req_id: int):
            res = api_client.post("/api/capture-screen", json={"mock": True, "format": "png"})
            return res.status_code, res.json()

        concurrency = 20
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(make_capture, i) for i in range(concurrency)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == concurrency
        for status_code, data in results:
            assert status_code == 200
            assert data["success"] is True
            assert data["file_path"] is None

    def test_concurrent_screen_captures_with_file_writes(self, api_client: TestClient):
        """Dispatches 20 concurrent screen captures with save_to_file=True (verifies nanosecond/uuid unique files)."""
        def make_capture(req_id: int):
            res = api_client.post(
                "/api/capture-screen",
                json={"mock": True, "format": "png", "save_to_file": True, "save_dir": "./staging/screenshots"}
            )
            return res.status_code, res.json()

        concurrency = 20
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(make_capture, i) for i in range(concurrency)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == concurrency
        saved_paths = set()
        for status_code, data in results:
            assert status_code == 200
            assert data["success"] is True
            assert data["file_path"] is not None
            assert os.path.exists(data["file_path"])
            saved_paths.add(data["file_path"])

        # Every concurrent request must produce a unique file path
        assert len(saved_paths) == concurrency

    def test_rapid_concurrent_pull_requests_cached(self, api_client: TestClient):
        """Dispatches 20 concurrent POST /api/trigger-adb-pull requests against cached asset."""
        # Ensure base asset is generated first
        api_client.post("/api/trigger-adb-pull", json={"mock": True, "limit": 1})

        def make_pull(req_id: int):
            res = api_client.post(
                "/api/trigger-adb-pull",
                json={"mock": True, "limit": 1},
            )
            return res.status_code, res.json()

        concurrency = 20
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(make_pull, i) for i in range(concurrency)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == concurrency
        for status_code, data in results:
            assert status_code == 200, f"Expected 200, got {status_code}: {data}"
            assert data["success"] is True
            assert data["status"] in ("success", "mock_success")
            assert data["bytes_transferred"] > 0
            assert len(data["pulled_files"]) == 1
            assert os.path.exists(data["pulled_files"][0]["local_path"])

    def test_mixed_workload_high_concurrency_stress(self, api_client: TestClient):
        """Dispatches 30 concurrent heterogeneous requests across all endpoints simultaneously."""
        def dispatch_action(idx: int):
            action_type = idx % 5
            if action_type == 0:
                res = api_client.get("/api/health")
            elif action_type == 1:
                res = api_client.get("/api/devices")
            elif action_type == 2:
                res = api_client.get("/api/staging")
            elif action_type == 3:
                res = api_client.post("/api/trigger-adb-pull", json={"mock": True, "limit": 1})
            else:
                res = api_client.post("/api/capture-screen", json={"mock": True, "format": "png", "save_dir": None})
            return res.status_code, res.json()

        concurrency = 30
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(dispatch_action, i) for i in range(concurrency)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == concurrency
        for status_code, data in results:
            assert status_code == 200


# ==============================================================================
# SECTION 2: CORS HEADERS UNDER MULTIPLE ORIGINS
# ==============================================================================

class TestCorsMultiOriginVerification:
    """Verifies CORS headers for multiple origins, preflight OPTIONS, and header permutations."""

    @pytest.mark.parametrize("origin", [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ])
    def test_cors_allowed_origins_preflight(self, api_client: TestClient, origin: str):
        """Tests preflight OPTIONS for each specified origin in the allowed origins list."""
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Accept,Authorization,X-Requested-With",
        }
        res = api_client.options("/api/trigger-adb-pull", headers=headers)
        assert res.status_code == 200
        allow_origin = res.headers.get("access-control-allow-origin")
        assert allow_origin in (origin, "*")
        allow_methods = res.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods or "*" in allow_methods
        allow_headers = res.headers.get("access-control-allow-headers", "")
        assert "content-type" in allow_headers.lower() or "*" in allow_headers

    @pytest.mark.parametrize("origin", [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])
    def test_cors_actual_request_headers(self, api_client: TestClient, origin: str):
        """Verifies CORS response headers on actual GET and POST requests."""
        # GET /api/health with Origin header
        res_get = api_client.get("/api/health", headers={"Origin": origin})
        assert res_get.status_code == 200
        assert res_get.headers.get("access-control-allow-origin") in (origin, "*")

        # POST /api/trigger-adb-pull with Origin header
        res_post = api_client.post(
            "/api/trigger-adb-pull",
            json={"mock": True, "limit": 1},
            headers={"Origin": origin, "Content-Type": "application/json"},
        )
        assert res_post.status_code == 200
        assert res_post.headers.get("access-control-allow-origin") in (origin, "*")

    def test_cors_wildcard_fallback_behavior(self, api_client: TestClient):
        """Tests CORS response for non-standard origin when wildcard is permitted."""
        headers = {
            "Origin": "http://custom-test-client.local:8080",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        res = api_client.options("/api/capture-screen", headers=headers)
        assert res.status_code == 200
        allow_origin = res.headers.get("access-control-allow-origin")
        assert allow_origin is not None


# ==============================================================================
# SECTION 3: BASE64 SCREENSHOT FORMAT CONVERSIONS & PAYLOAD INTEGRITY
# ==============================================================================

class TestBase64ScreenshotIntegrity:
    """Verifies binary and Base64 image encoding, decoding, dimensions, and format conversions."""

    def test_png_screenshot_byte_decoding(self, api_client: TestClient):
        """Verifies PNG capture format generates valid PNG byte header and decodes in PIL."""
        res = api_client.post("/api/capture-screen", json={"mock": True, "format": "png", "save_dir": None})
        assert res.status_code == 200
        data = res.json()

        assert data["success"] is True
        assert data["image_base64"].startswith("data:image/png;base64,")
        assert data["raw_base64"] is not None

        # Decode raw base64 string
        raw_bytes = base64.b64decode(data["raw_base64"])
        # PNG signature: 89 50 4E 47 0D 0A 1A 0A
        assert raw_bytes.startswith(b"\x89PNG\r\n\x1a\n")

        # Open in PIL to verify image stream integrity and dimensions
        img = Image.open(io.BytesIO(raw_bytes))
        assert img.format == "PNG"
        assert img.size == (540, 960)
        assert data["width"] == 540
        assert data["height"] == 960

    def test_jpeg_screenshot_byte_decoding(self, api_client: TestClient):
        """Verifies JPEG capture format generates valid JPEG SOI marker and decodes in PIL."""
        res = api_client.post("/api/capture-screen", json={"mock": True, "format": "jpeg", "save_dir": None})
        assert res.status_code == 200
        data = res.json()

        assert data["success"] is True
        assert data["image_base64"].startswith("data:image/jpeg;base64,")
        assert data["raw_base64"] is not None

        # Decode raw base64 string
        raw_bytes = base64.b64decode(data["raw_base64"])
        # JPEG SOI marker: FF D8 FF
        assert raw_bytes.startswith(b"\xff\xd8\xff")

        # Open in PIL
        img = Image.open(io.BytesIO(raw_bytes))
        assert img.format == "JPEG"
        assert img.size == (540, 960)
        assert data["width"] == 540
        assert data["height"] == 960

    def test_data_uri_and_raw_base64_coherence(self, api_client: TestClient):
        """Verifies data: URI prefix strictly wraps the exact raw_base64 string."""
        res = api_client.post("/api/capture-screen", json={"mock": True, "format": "png", "save_dir": None})
        data = res.json()

        data_uri = data["image_base64"]
        raw_b64 = data["raw_base64"]
        prefix, encoded_part = data_uri.split(",", 1)

        assert prefix == "data:image/png;base64"
        assert encoded_part == raw_b64

    def test_unsupported_format_graceful_handling(self, api_client: TestClient):
        """Verifies non-standard formats (e.g. webp, bmp) default safely to PNG."""
        res = api_client.post("/api/capture-screen", json={"mock": True, "format": "bmp", "save_dir": None})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["image_base64"].startswith("data:image/png;base64,")


# ==============================================================================
# SECTION 4: SECURITY FUZZING & ADVERSARIAL PAYLOADS
# ==============================================================================

class TestAdversarialFuzzingAndSecurity:
    """Fuzzes endpoints with command injection attempts, path traversal, and extreme inputs."""

    def test_command_injection_mitigation_in_device_id(self, api_client: TestClient):
        """Tests that shell injection payloads in device_id do not execute or crash daemon."""
        injection_payloads = [
            "; calc.exe",
            "& dir",
            "| whoami",
            "`id`",
            "$(echo test)",
            "emulator-5554; rm -rf /",
        ]
        for payload in injection_payloads:
            res = api_client.post("/api/trigger-adb-pull", json={"device_id": payload, "mock": False})
            assert res.status_code == 200
            data = res.json()
            # Should safely handle via mock fallback or safe error
            assert data["success"] is True or data["status"] == "error"

    def test_path_traversal_mitigation_in_destination_path(self, api_client: TestClient):
        """Tests that relative directory paths with traversal are normalized without crashing."""
        traversal_dest = "./staging/videos/../../staging/videos/safe_test"
        res = api_client.post("/api/trigger-adb-pull", json={
            "mock": True,
            "destination_path": traversal_dest,
            "limit": 1
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert os.path.exists(data["pulled_files"][0]["local_path"])

    def test_empty_json_body_defaults_safely(self, api_client: TestClient):
        """Tests empty JSON objects default safely across all POST routes."""
        res_pull = api_client.post("/api/trigger-adb-pull", json={})
        assert res_pull.status_code == 200
        assert res_pull.json()["success"] is True

        res_cap = api_client.post("/api/capture-screen", json={})
        assert res_cap.status_code == 200
        assert res_cap.json()["success"] is True

    def test_pydantic_schema_validation_on_invalid_types(self, api_client: TestClient):
        """Verifies Pydantic strict type validation on non-boolean or invalid limit values."""
        # Non-boolean mock field
        res_null_mock = api_client.post("/api/trigger-adb-pull", json={"mock": "not-a-bool"})
        assert res_null_mock.status_code == 422

        # Invalid limit < 1
        res_zero_limit = api_client.post("/api/trigger-adb-pull", json={"limit": 0})
        assert res_zero_limit.status_code == 422

        # Invalid limit > 100
        res_high_limit = api_client.post("/api/trigger-adb-pull", json={"limit": 101})
        assert res_high_limit.status_code == 422


# ==============================================================================
# SECTION 5: STAGING INVENTORY & FILE RESILIENCE
# ==============================================================================

class TestStagingInventoryResilience:
    """Tests /api/staging behavior under varied file system states."""

    def test_staging_inventory_returns_accurate_metadata(self, api_client: TestClient):
        """Verifies staging endpoint lists existing media files with correct sizes and types."""
        # Ensure at least one mock video exists
        api_client.post("/api/trigger-adb-pull", json={"mock": True, "limit": 1})

        res = api_client.get("/api/staging")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] >= 1
        assert data["total_size_bytes"] > 0
        for f in data["files"]:
            assert "filename" in f
            assert "path" in f
            assert "size_bytes" in f
            assert "modified_at" in f
            assert f["media_type"] in ("video/mp4", "image/png", "application/octet-stream")
