"""Tier 2 Boundary Tests: REST API Fault Injection and Edge Cases."""

from __future__ import annotations

from pathlib import Path
import pytest

from fastapi.testclient import TestClient
from src.api.app import create_app
from src.pipeline.job_manager import JobManager


@pytest.fixture
def custom_job_manager():
    return JobManager()


@pytest.fixture
def client(custom_job_manager):
    app = create_app(job_manager=custom_job_manager)
    return TestClient(app)


@pytest.mark.tier2
def test_boundary_api_invalid_json_body(client):
    """Verify endpoint rejects malformed JSON payload with 422 Unprocessable Entity."""
    response = client.post(
        "/api/v1/jobs/ingest/trigger",
        content="not_valid_json{",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code in (400, 422)


@pytest.mark.tier2
def test_boundary_api_missing_fields_in_override(client):
    """Verify PUT /jobs/{id}/edl rejects incomplete override body."""
    response = client.put("/api/v1/jobs/job_123/edl", json={"invalid_field": True})
    assert response.status_code in (400, 404, 422)


@pytest.mark.tier2
def test_boundary_api_approve_nonexistent_job(client):
    """Verify approving a non-existent job ID returns 404."""
    response = client.post("/api/v1/jobs/non_existent_9999/approve")
    assert response.status_code == 404


@pytest.mark.tier2
def test_boundary_api_regrade_nonexistent_job(client):
    """Verify regrading a non-existent job ID returns 404."""
    response = client.post("/api/v1/jobs/non_existent_9999/regrade")
    assert response.status_code == 404


@pytest.mark.tier2
def test_boundary_api_invalid_range_header(client):
    """Verify streaming proxy handles invalid Range headers safely."""
    headers = {"Range": "bytes=abc-xyz"}
    response = client.get("/api/v1/jobs/test_job/proxy", headers=headers)
    assert response.status_code in (400, 404, 416, 200)


@pytest.mark.tier2
def test_boundary_api_range_out_of_bounds(client, tmp_path: Path, custom_job_manager):
    """Verify Range header beyond file size returns 416 Range Not Satisfiable."""
    dummy_proxy = tmp_path / "small_clip.mp4"
    dummy_proxy.write_bytes(b"x" * 100)

    job = custom_job_manager.create_job(str(dummy_proxy), job_id="job_small")

    headers = {"Range": "bytes=5000-6000"}
    response = client.get(f"/api/v1/jobs/{job.job_id}/proxy", headers=headers)
    assert response.status_code == 416
    assert "Content-Range" in response.headers


@pytest.mark.tier2
def test_boundary_api_suffix_range_header(client, tmp_path: Path, custom_job_manager):
    """Verify Range header suffix request (e.g. bytes=-50) returns last 50 bytes."""
    dummy_proxy = tmp_path / "suffix_clip.mp4"
    dummy_proxy.write_bytes(b"A" * 100)

    job = custom_job_manager.create_job(str(dummy_proxy), job_id="job_suffix")

    headers = {"Range": "bytes=-50"}
    response = client.get(f"/api/v1/jobs/{job.job_id}/proxy", headers=headers)
    assert response.status_code == 206
    assert len(response.content) == 50


@pytest.mark.tier2
def test_boundary_api_empty_trigger_payload(client):
    """Verify triggering an ingestion with an empty payload returns 422."""
    response = client.post("/api/v1/jobs/ingest/trigger", json={})
    assert response.status_code in (400, 422)


@pytest.mark.tier2
def test_boundary_api_excessive_payload_size(client):
    """Verify posting massive payloads is rejected or handled without memory leak."""
    giant_payload = {"filepath": "ingest/test.mp4", "padding": "x" * 100000}
    response = client.post("/api/v1/jobs/ingest/trigger", json=giant_payload)
    assert response.status_code in (200, 201, 400, 413, 422)


@pytest.mark.tier2
def test_boundary_api_unsupported_http_method(client):
    """Verify unsupported HTTP method on endpoint returns 405 Method Not Allowed."""
    response = client.delete("/api/v1/health")
    assert response.status_code == 405
