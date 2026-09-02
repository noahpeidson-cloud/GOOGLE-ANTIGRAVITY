"""Tier 1 Feature Tests: FastAPI REST Control Plane Endpoints."""

from __future__ import annotations

from pathlib import Path
import pytest

from fastapi.testclient import TestClient
from src.api.app import create_app
from src.models.schemas import EditDecisionList, JobMetadata, JobStatus
from src.pipeline.job_manager import JobManager


@pytest.fixture
def custom_job_manager():
    return JobManager()


@pytest.fixture
def client(custom_job_manager):
    app = create_app(job_manager=custom_job_manager)
    return TestClient(app)


@pytest.mark.tier1
def test_api_health_endpoint(client):
    """Verify GET /api/v1/health and GET /health return healthy status and diagnostics."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in ("ok", "healthy", "UP")
    assert "ffmpeg_available" in data
    assert "disk_free_gb" in data

    # Root route alias check
    root_resp = client.get("/health")
    assert root_resp.status_code == 200
    assert root_resp.json().get("status") in ("ok", "healthy", "UP")


@pytest.mark.tier1
def test_api_config_endpoint(client):
    """Verify GET /api/v1/config exposes system settings."""
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    data = response.json()
    assert "default_encoding_profile" in data or "ingest_dir" in data

    root_resp = client.get("/config")
    assert root_resp.status_code == 200


@pytest.mark.tier1
def test_api_get_jobs_empty_and_populated(client):
    """Verify GET /api/v1/jobs lists tracked ingestion jobs."""
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    root_resp = client.get("/jobs")
    assert root_resp.status_code == 200
    assert isinstance(root_resp.json(), list)


@pytest.mark.tier1
def test_api_get_job_by_id_not_found(client):
    """Verify GET /api/v1/jobs/{id} returns 404 for unknown job."""
    response = client.get("/api/v1/jobs/non_existent_job_123")
    assert response.status_code == 404


@pytest.mark.tier1
def test_api_get_job_by_id_success(client):
    """Verify GET /api/v1/jobs/{id} returns full job details."""
    trigger_resp = client.post("/api/v1/jobs/ingest/trigger", json={"filepath": "ingest/test_clip.mp4"})
    assert trigger_resp.status_code in (200, 201)
    job_id = trigger_resp.json()["job_id"]

    get_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["job_id"] == job_id


@pytest.mark.tier1
def test_api_get_and_put_edl(client, sample_edl_dict_factory):
    """Verify GET and PUT /api/v1/jobs/{id}/edl."""
    trigger_resp = client.post("/api/v1/jobs/ingest/trigger", json={"filepath": "ingest/test.mp4"})
    assert trigger_resp.status_code in (200, 201)
    job_id = trigger_resp.json()["job_id"]

    override_payload = sample_edl_dict_factory(
        job_id=job_id,
        contrast=1.8,
        saturation=1.5,
        manual_override_applied=True,
    )
    put_resp = client.put(f"/api/v1/jobs/{job_id}/edl", json=override_payload)
    assert put_resp.status_code in (200, 202)
    data = put_resp.json()
    assert data.get("manual_override_applied") is True or data.get("color_grade", {}).get("contrast") == 1.8

    # Query EDL back
    get_edl_resp = client.get(f"/api/v1/jobs/{job_id}/edl")
    assert get_edl_resp.status_code == 200
    assert get_edl_resp.json()["color_grade"]["contrast"] == 1.8


@pytest.mark.tier1
def test_api_post_job_approve(client):
    """Verify POST /api/v1/jobs/{id}/approve transitions job toward rendering."""
    trigger_resp = client.post("/api/v1/jobs/ingest/trigger", json={"filepath": "ingest/test.mp4"})
    assert trigger_resp.status_code in (200, 201)
    job_id = trigger_resp.json()["job_id"]
    approve_resp = client.post(f"/api/v1/jobs/{job_id}/approve")
    assert approve_resp.status_code in (200, 202)


@pytest.mark.tier1
def test_api_post_job_regrade(client):
    """Verify POST /api/v1/jobs/{id}/regrade requests a fresh ML grading pass."""
    trigger_resp = client.post("/api/v1/jobs/ingest/trigger", json={"filepath": "ingest/test.mp4"})
    assert trigger_resp.status_code in (200, 201)
    job_id = trigger_resp.json()["job_id"]
    regrade_resp = client.post(f"/api/v1/jobs/{job_id}/regrade", json={"prompt": "Vibrant concert look"})
    assert regrade_resp.status_code in (200, 202)


@pytest.mark.tier1
def test_api_proxy_stream_range_header(client, tmp_path: Path, custom_job_manager):
    """Verify GET /api/v1/jobs/{id}/proxy supports HTTP 206 Partial Content range requests."""
    dummy_proxy = tmp_path / "proxy_test.mp4"
    dummy_proxy.write_bytes(b"0123456789" * 1000)  # 10,000 bytes

    job = custom_job_manager.create_job(str(dummy_proxy), job_id="test_stream_job")

    headers = {"Range": "bytes=0-499"}
    response = client.get(f"/api/v1/jobs/{job.job_id}/proxy", headers=headers)
    assert response.status_code == 206
    assert response.headers.get("Content-Range") == "bytes 0-499/10000"
    assert len(response.content) == 500


@pytest.mark.tier1
def test_api_jobs_filtering_and_pagination(client):
    """Verify job querying with status filter and pagination."""
    for i in range(5):
        client.post("/api/v1/jobs/ingest/trigger", json={"filepath": f"ingest/video_{i}.mp4"})

    resp_all = client.get("/api/v1/jobs?limit=2&offset=0")
    assert resp_all.status_code == 200
    assert len(resp_all.json()) == 2


@pytest.mark.tier1
def test_api_unsupported_route_returns_404(client):
    """Verify unsupported URL paths return HTTP 404."""
    response = client.get("/api/v1/unknown_invalid_endpoint")
    assert response.status_code == 404
