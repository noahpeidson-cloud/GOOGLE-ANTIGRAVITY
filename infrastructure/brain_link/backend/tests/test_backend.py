import os
import io
import json
import pytest
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient

# Ensure test uses a clean temporary upload directory
TEST_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "test_uploads")
os.environ["UPLOAD_DIR"] = TEST_UPLOAD_DIR
os.environ["AUTH_TOKEN"] = "test-secret-token-12345"
os.environ["SERVER_PORT"] = "8000"

# Import application under test
import config
from main import app
from qr_generator import get_local_ip, generate_qr_image_bytes, get_pairing_payload, print_pairing_cli
from gemini_tagger import process_video_async


def setup_function():
    os.makedirs(TEST_UPLOAD_DIR, exist_ok=True)
    config.UPLOAD_DIR = TEST_UPLOAD_DIR
    config.AUTH_TOKEN = "test-secret-token-12345"


def teardown_function():
    if os.path.exists(TEST_UPLOAD_DIR):
        for f in os.listdir(TEST_UPLOAD_DIR):
            try:
                os.remove(os.path.join(TEST_UPLOAD_DIR, f))
            except Exception:
                pass
        try:
            os.rmdir(TEST_UPLOAD_DIR)
        except Exception:
            pass


def test_pairing_info_endpoint():
    """Assert pairing info endpoint returns server ip, port, and auth token."""
    client = TestClient(app)
    response = client.get("/api/pair-info")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "server_ip" in data, "Missing server_ip in pair-info response"
    assert "port" in data, "Missing port in pair-info response"
    assert "auth_token" in data, "Missing auth_token in pair-info response"
    assert data["auth_token"] == "test-secret-token-12345", "Auth token does not match config"


def test_qr_code_endpoint():
    """Assert QR code generation endpoint returns a valid PNG image."""
    client = TestClient(app)
    response = client.get("/api/qr")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.headers["content-type"] == "image/png", f"Expected image/png, got {response.headers.get('content-type')}"
    assert len(response.content) > 0, "QR code image content is empty"
    # PNG signature check
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n", "Content does not have valid PNG header"


def test_upload_missing_auth_header_rejected():
    """Assert upload without auth token returns 401 Unauthorized."""
    client = TestClient(app)
    video_bytes = b"0" * 1024
    response = client.post(
        "/api/upload",
        files={"file": ("video.mp4", io.BytesIO(video_bytes), "video/mp4")},
    )
    assert response.status_code == 401, f"Expected 401 for missing auth, got {response.status_code}"


def test_upload_invalid_auth_header_rejected():
    """Assert upload with invalid auth token returns 401 Unauthorized."""
    client = TestClient(app)
    video_bytes = b"0" * 1024
    response = client.post(
        "/api/upload",
        headers={"Authorization": "Bearer wrong-token"},
        files={"file": ("video.mp4", io.BytesIO(video_bytes), "video/mp4")},
    )
    assert response.status_code == 401, f"Expected 401 for invalid auth, got {response.status_code}"


def test_upload_with_x_auth_token_header(monkeypatch):
    """Assert upload with X-Auth-Token header is accepted."""
    client = TestClient(app)
    monkeypatch.setattr("main.process_video_async", lambda path: {"status": "success"})

    dummy_payload = b"test video stream"
    response = client.post(
        "/api/upload",
        headers={"X-Auth-Token": "test-secret-token-12345"},
        files={"file": ("x_auth_video.mp4", io.BytesIO(dummy_payload), "video/mp4")},
    )
    assert response.status_code == 200, f"Expected 200 with X-Auth-Token, got {response.status_code}"


def test_upload_valid_auth_streaming_write_and_immediate_200(monkeypatch):
    """Assert valid upload writes file to disk, returns 200 immediately, and dispatches background task."""
    client = TestClient(app)
    dispatched_tasks = []

    def mock_process_video_async(file_path: str):
        dispatched_tasks.append(file_path)
        return {"status": "success", "tags": ["sports", "highlight"]}

    # Monkeypatch the background worker
    monkeypatch.setattr("main.process_video_async", mock_process_video_async)

    dummy_video_payload = b"\x00\x00\x00\x18ftypmp42" + b"A" * (1024 * 100)  # 100KB test video payload
    filename = "test_sample_4k.mp4"

    response = client.post(
        "/api/upload",
        headers={"Authorization": "Bearer test-secret-token-12345"},
        files={"file": (filename, io.BytesIO(dummy_video_payload), "video/mp4")},
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data.get("status") == "success", "Response status is not success"
    assert "saved_path" in data, "Response missing saved_path"
    assert os.path.exists(data["saved_path"]), f"Uploaded file was not written to disk: {data['saved_path']}"
    assert os.path.getsize(data["saved_path"]) == len(dummy_video_payload), "File size on disk mismatch"
    assert len(dispatched_tasks) == 1, "Background tagging task was not dispatched"
    assert dispatched_tasks[0] == data["saved_path"], "Dispatched task path mismatch"


def test_gemini_tagger_fallback_on_missing_file():
    """Assert tagger gracefully handles non-existent file path without raising uncaught exception."""
    result = process_video_async("non_existent_file_path_1234.mp4")
    assert result.get("status") == "error", "Expected error status for missing file"


def test_gemini_tagger_success_flow(tmp_path, monkeypatch):
    """Assert tagger uploads file to Gemini client, parses response, and saves sidecar JSON."""
    test_video = tmp_path / "mock_vid.mp4"
    test_video.write_bytes(b"dummy mp4 data")

    mock_client = MagicMock()
    mock_file = MagicMock()
    mock_file.name = "files/test12345"
    mock_file.state = "ACTIVE"
    mock_client.files.upload.return_value = mock_file

    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "title": "4K Test Video",
        "summary": "High resolution test footage",
        "tags": ["4k", "cinematic", "drone"],
        "detected_objects": ["car", "tree"],
        "key_moments": [{"timestamp": "00:01", "description": "Drone ascends"}]
    })
    mock_client.models.generate_content.return_value = mock_response

    monkeypatch.setattr("gemini_tagger.genai.Client", lambda **kwargs: mock_client)

    result = process_video_async(str(test_video))
    assert result["status"] == "success"
    assert "metadata" in result
    assert result["metadata"]["title"] == "4K Test Video"
    assert "4k" in result["metadata"]["tags"]

    # Verify sidecar JSON file exists on disk
    sidecar_path = test_video.with_suffix(".mp4.tags.json")
    assert sidecar_path.exists(), "Companion metadata file not created"
    saved_json = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert saved_json["metadata"]["title"] == "4K Test Video"
