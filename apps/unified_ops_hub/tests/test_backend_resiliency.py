"""Comprehensive Tests for Backend Resiliency, Port Manager, FastAPI Gateway, and Programmatic Crash Testing.
Following TDD / Loud Assertions Protocol (Requirement R4).
"""

import os
import socket
import tempfile
import shutil
import time
import pytest
from fastapi.testclient import TestClient

from unified_ops_hub.gateway.port_manager import PortManager
from unified_ops_hub.gateway.dlq_manager import DLQManager, ErrorCategory, IncidentStatus
from unified_ops_hub.gateway.app import create_app
from unified_ops_hub.gateway.crash_tester import CrashTester


@pytest.fixture
def test_env():
    """Provides isolated temp dirs for DLQ, lock files, and a test FastAPI TestClient."""
    temp_dir = tempfile.mkdtemp(prefix="test_resiliency_")
    db_path = os.path.join(temp_dir, "test_gateway_dlq.db")
    quarantine_dir = os.path.join(temp_dir, "quarantine")
    lock_dir = os.path.join(temp_dir, "locks")
    
    port_mgr = PortManager(lock_dir=lock_dir)
    dlq_mgr = DLQManager(db_path=db_path, quarantine_dir=quarantine_dir)
    
    app = create_app(port_manager=port_mgr, dlq_manager=dlq_mgr)
    client = TestClient(app, raise_server_exceptions=False)
    
    yield {
        "dir": temp_dir,
        "lock_dir": lock_dir,
        "db_path": db_path,
        "quarantine_dir": quarantine_dir,
        "port_manager": port_mgr,
        "dlq_manager": dlq_mgr,
        "app": app,
        "client": client,
    }
    shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# 1. Port Manager & Socket Collision Tests
# ============================================================================

def test_port_manager_detect_free_and_in_use_ports(test_env):
    """Verifies PortManager accurately detects open vs occupied ports."""
    pm = test_env["port_manager"]
    
    # 1. Find a dynamic port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    
    try:
        # Port should be detected as in use
        assert pm.is_port_in_use(port) is True
    finally:
        sock.close()
        
    # Give OS a moment to release socket
    time.sleep(0.05)
    # Port should now be detected as free
    assert pm.is_port_in_use(port) is False


def test_port_manager_fallback_allocation(test_env):
    """Verifies PortManager allocates fallback sequential ports when preferred port is occupied."""
    pm = test_env["port_manager"]
    
    # Bind preferred port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    occupied_port = sock.getsockname()[1]
    
    try:
        # Requesting occupied_port with fallback should return occupied_port + 1 (or next available)
        allocated_port = pm.find_available_port(preferred_port=occupied_port, max_attempts=10)
        assert allocated_port is not None
        assert allocated_port != occupied_port
        assert allocated_port > occupied_port
        assert pm.is_port_in_use(allocated_port) is False
    finally:
        sock.close()


def test_port_manager_lockfile_lifecycle_and_stale_cleanup(test_env):
    """Verifies file-lock acquisition, conflict prevention, and stale lock eviction."""
    pm = test_env["port_manager"]
    lock_dir = test_env["lock_dir"]
    target_port = 8099
    
    # Acquire lock for target_port
    lock_file = pm.acquire_port_lock(target_port)
    assert lock_file is not None
    assert os.path.exists(lock_file)
    
    # Attempting to acquire again in another instance should fail
    pm2 = PortManager(lock_dir=lock_dir)
    assert pm2.acquire_port_lock(target_port) is None
    
    # Release lock
    pm.release_port_lock(target_port)
    assert not os.path.exists(lock_file)
    
    # Simulate a stale abandoned lock file older than max_age
    stale_file = os.path.join(lock_dir, "port_8098.lock")
    with open(stale_file, "w") as f:
        f.write("99999")  # Non-existent PID
    # Set mtime back by 2 hours
    old_time = time.time() - 7200
    os.utime(stale_file, (old_time, old_time))
    
    cleaned = pm.cleanup_stale_locks(max_age_seconds=60)
    assert len(cleaned) == 1
    assert not os.path.exists(stale_file)


# ============================================================================
# 2. FastAPI Gateway Routes & Domain Integration Tests
# ============================================================================

def test_gateway_health_route(test_env):
    """Verifies /api/v1/health returns comprehensive operational metrics."""
    client = test_env["client"]
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert "version" in data
    assert "uptime_seconds" in data
    assert "ports" in data
    assert "dlq_stats" in data
    assert data["dlq_stats"]["total_incidents"] == 0


def test_sports_cards_domain_routes(test_env):
    """Verifies /api/v1/sports routes (capture, staging, stats)."""
    client = test_env["client"]
    
    # Health probe
    resp = client.get("/api/v1/sports/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "READY"

    # Capture card payload
    card_data = {
        "player": "Victor Wembanyama",
        "year": "2023",
        "set_name": "Prizm",
        "card_number": "136",
        "category": "Basketball",
        "condition": "Raw",
        "investment": 150.0,
        "estimated_value": 220.0,
    }
    resp = client.post("/api/v1/sports/capture", json=card_data)
    assert resp.status_code == 200
    saved = resp.json()
    assert saved["id"] is not None
    assert saved["player"] == "Victor Wembanyama"
    assert saved["ai_status"] == "CLEARED"

    # Query staging
    resp = client.get("/api/v1/sports/staging")
    assert resp.status_code == 200
    staged = resp.json()
    assert len(staged["cards"]) == 1
    assert staged["total"] == 1

    # Query stats
    resp = client.get("/api/v1/sports/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_investment"] == 150.0
    assert stats["total_estimated_value"] == 220.0


def test_media_domain_routes(test_env):
    """Verifies /api/v1/media routes (pipeline trigger, job status, proxies)."""
    client = test_env["client"]
    
    # Health probe
    resp = client.get("/api/v1/media/health")
    assert resp.status_code == 200

    # Trigger video pipeline
    trigger_payload = {"clip_name": "edc_drop_stage1.mp4", "mode": "vertical_reframes"}
    resp = client.post("/api/v1/media/trigger", json=trigger_payload)
    assert resp.status_code == 202
    job_info = resp.json()
    assert "job_id" in job_info
    job_id = job_info["job_id"]

    # Poll status
    resp = client.get(f"/api/v1/media/status/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] in ["QUEUED", "RUNNING", "COMPLETED"]

    # Query proxies
    resp = client.get("/api/v1/media/proxies")
    assert resp.status_code == 200
    assert isinstance(resp.json()["proxies"], list)


def test_ml_domain_routes(test_env):
    """Verifies /api/v1/ml routes (video grading, dynamic weights, telemetry)."""
    client = test_env["client"]
    
    # Grade video request
    grade_req = {
        "video_id": "vid_9981",
        "scores": {
            "HRV": 88.0,
            "DPAW": 92.0,
            "ADR_SFD": 85.0,
            "CKE_MVE": 78.0,
            "LTSS": 80.0,
        },
        "aspect_ratio": "9:16",
    }
    resp = client.post("/api/v1/ml/grade", json=grade_req)
    assert resp.status_code == 200
    grade_res = resp.json()
    assert grade_res["evpi"] >= 80.0
    assert grade_res["verdict"] in ["VIRAL_READY", "HIGH_POTENTIAL"]

    # Query active weights
    resp = client.get("/api/v1/ml/weights")
    assert resp.status_code == 200
    weights = resp.json()["weights"]
    assert sum(weights.values()) == pytest.approx(1.0, 0.001)

    # Ingest feedback loop
    feedback_req = {"video_id": "vid_9981", "actual_views": 150000, "actual_shares": 8500}
    resp = client.post("/api/v1/ml/feedback", json=feedback_req)
    assert resp.status_code == 200
    assert resp.json()["status"] == "INGESTED"


def test_dlq_gateway_endpoints(test_env):
    """Verifies /api/v1/dlq REST interface for inspecting, retrying, and managing quarantined incidents."""
    client = test_env["client"]
    dlq_mgr = test_env["dlq_manager"]
    
    # Seed an incident
    incident = dlq_mgr.record_failure(
        source_service="media_pipeline",
        error_category=ErrorCategory.ML_GRADING_FAILURE,
        error_message="Gemini API Quota Exceeded",
        payload={"clip": "take3.mov"},
    )
    
    # List incidents
    resp = client.get("/api/v1/dlq/incidents")
    assert resp.status_code == 200
    incidents = resp.json()["incidents"]
    assert len(incidents) == 1
    assert incidents[0]["incident_id"] == incident.incident_id

    # Get single incident
    resp = client.get(f"/api/v1/dlq/incidents/{incident.incident_id}")
    assert resp.status_code == 200
    assert resp.json()["incident_id"] == incident.incident_id

    # Trigger replay via endpoint
    resp = client.post(f"/api/v1/dlq/retry/{incident.incident_id}")
    assert resp.status_code == 200
    assert "success" in resp.json()

    # DLQ stats endpoint
    resp = client.get("/api/v1/dlq/stats")
    assert resp.status_code == 200
    assert resp.json()["total_incidents"] == 1


# ============================================================================
# 3. Resiliency Middleware & Auto-DLQ Exception Routing
# ============================================================================

def test_unhandled_exception_caught_and_quarantined(test_env):
    """Loud Assertion: An unexpected exception during request processing does NOT crash the server;
    instead it captures the incident into DLQ and returns a structured 500 error with incident_id.
    """
    client = test_env["client"]
    dlq_mgr = test_env["dlq_manager"]
    
    # Call endpoint configured to raise an unexpected runtime error
    resp = client.post("/api/v1/simulate-crash", json={"error_type": "DivisionByZero", "trigger": True})
    assert resp.status_code == 500
    body = resp.json()
    assert "incident_id" in body
    incident_id = body["incident_id"]
    
    # Verify incident was automatically captured in DLQ
    incident = dlq_mgr.get_incident(incident_id)
    assert incident is not None
    assert incident.error_category in [ErrorCategory.UNHANDLED_EXCEPTION, ErrorCategory.ML_GRADING_FAILURE]
    assert "ZeroDivision" in incident.error_message or "division by zero" in incident.error_message.lower()

    # Ensure subsequent health checks still succeed (daemon remains alive)
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "HEALTHY"


# ============================================================================
# 4. Programmatic Crash Tester Suite Integration
# ============================================================================

def test_programmatic_crash_tester_suite(test_env):
    """Executes the CrashTester programmatic verification suite simulating:
    1. Socket collision
    2. Malformed / Corrupted Payload quarantine
    3. Simulated ML grading crash
    4. Daemon alive under rapid chaos load
    """
    crash_tester = CrashTester(
        app=test_env["app"],
        client=test_env["client"],
        port_manager=test_env["port_manager"],
        dlq_manager=test_env["dlq_manager"],
    )
    
    report = crash_tester.run_all_tests()
    assert report["all_passed"] is True
    assert report["summary"]["total_tests"] >= 4
    assert report["summary"]["failed_tests"] == 0
    assert len(report["results"]) >= 4
    
    for test_result in report["results"]:
        assert test_result["passed"] is True, f"Crash test {test_result['name']} failed: {test_result['error']}"
