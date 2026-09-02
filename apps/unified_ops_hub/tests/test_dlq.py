"""Comprehensive Tests for Dead Letter Queue (DLQ) & Quarantine Architecture.
Following TDD / Loud Assertions Protocol (Requirement R4).
"""

import os
import json
import time
import shutil
import tempfile
import threading
from datetime import datetime, timezone, timedelta
import pytest

from unified_ops_hub.gateway.dlq_manager import (
    DLQManager,
    DLQIncident,
    ErrorCategory,
    IncidentStatus,
)


@pytest.fixture
def temp_dlq_env():
    """Provides an isolated temporary directory for DLQ SQLite and JSON persistence."""
    temp_dir = tempfile.mkdtemp(prefix="test_dlq_")
    db_path = os.path.join(temp_dir, "test_dlq.db")
    quarantine_dir = os.path.join(temp_dir, "quarantine")
    manager = DLQManager(db_path=db_path, quarantine_dir=quarantine_dir)
    yield {
        "dir": temp_dir,
        "db_path": db_path,
        "quarantine_dir": quarantine_dir,
        "manager": manager,
    }
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_dlq_initialization(temp_dlq_env):
    """Verifies that DLQManager initializes SQLite database tables and quarantine directory."""
    manager = temp_dlq_env["manager"]
    assert os.path.exists(temp_dlq_env["db_path"])
    assert os.path.exists(temp_dlq_env["quarantine_dir"])
    
    stats = manager.get_stats()
    assert stats["total_incidents"] == 0
    assert stats["quarantined_count"] == 0
    assert stats["resolved_count"] == 0


def test_record_failure_and_persistence(temp_dlq_env):
    """Verifies recording a failure persists both to SQLite and a standalone JSON audit artifact."""
    manager = temp_dlq_env["manager"]
    payload = {"card_id": "8492-01", "player": "Luka Doncic", "price": "invalid_number"}
    
    incident = manager.record_failure(
        source_service="sports_cards",
        error_category=ErrorCategory.CORRUPTED_PAYLOAD,
        error_message="Price cannot be parsed to float",
        payload=payload,
        traceback_str="ValueError: could not convert string to float: 'invalid_number'",
        max_retries=3,
    )
    
    assert incident.incident_id is not None
    assert incident.source_service == "sports_cards"
    assert incident.error_category == ErrorCategory.CORRUPTED_PAYLOAD
    assert incident.status == IncidentStatus.QUARANTINED
    assert incident.retry_count == 0
    assert incident.max_retries == 3
    assert incident.payload == payload
    assert incident.next_retry_at is not None

    # Verify retrieval from DB
    retrieved = manager.get_incident(incident.incident_id)
    assert retrieved is not None
    assert retrieved.incident_id == incident.incident_id
    assert retrieved.error_message == "Price cannot be parsed to float"

    # Verify JSON persistence on disk
    json_path = os.path.join(temp_dlq_env["quarantine_dir"], f"dlq_{incident.incident_id}.json")
    assert os.path.exists(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data["incident_id"] == incident.incident_id
    assert saved_data["payload"]["player"] == "Luka Doncic"


def test_incident_category_classification(temp_dlq_env):
    """Verifies error categories are properly typed and recognized."""
    manager = temp_dlq_env["manager"]
    categories = [
        ErrorCategory.CORRUPTED_PAYLOAD,
        ErrorCategory.ML_GRADING_FAILURE,
        ErrorCategory.SOCKET_COLLISION,
        ErrorCategory.API_RATE_LIMIT,
        ErrorCategory.TIMEOUT,
        ErrorCategory.UNHANDLED_EXCEPTION,
    ]
    
    for idx, cat in enumerate(categories):
        inc = manager.record_failure(
            source_service=f"service_{idx}",
            error_category=cat,
            error_message=f"Test error for {cat.value}",
            payload={"test_idx": idx},
        )
        assert inc.error_category == cat
        
    stats = manager.get_stats()
    assert stats["total_incidents"] == len(categories)
    for cat in categories:
        assert stats["categories"].get(cat.value, 0) == 1


def test_exponential_backoff_calculation(temp_dlq_env):
    """Verifies deterministic and jittered exponential backoff calculation."""
    manager = temp_dlq_env["manager"]
    
    # Check deterministic backoffs without jitter
    b0 = manager.calculate_backoff_seconds(retry_count=0, base_backoff=2.0, max_backoff=100.0, jitter=False)
    b1 = manager.calculate_backoff_seconds(retry_count=1, base_backoff=2.0, max_backoff=100.0, jitter=False)
    b2 = manager.calculate_backoff_seconds(retry_count=2, base_backoff=2.0, max_backoff=100.0, jitter=False)
    b3 = manager.calculate_backoff_seconds(retry_count=3, base_backoff=2.0, max_backoff=100.0, jitter=False)
    b10 = manager.calculate_backoff_seconds(retry_count=10, base_backoff=2.0, max_backoff=100.0, jitter=False)
    
    assert b0 == 2.0
    assert b1 == 4.0
    assert b2 == 8.0
    assert b3 == 16.0
    assert b10 == 100.0  # Capped at max_backoff


def test_thread_safe_concurrent_recording(temp_dlq_env):
    """Loud Assertion: Spawns 20 threads to write concurrently to DLQ without data loss or SQLite locks."""
    manager = temp_dlq_env["manager"]
    num_threads = 20
    errors = []
    
    def worker(worker_id):
        try:
            for i in range(5):
                manager.record_failure(
                    source_service=f"worker_{worker_id}",
                    error_category=ErrorCategory.ML_GRADING_FAILURE,
                    error_message=f"Failure from worker {worker_id} iter {i}",
                    payload={"worker": worker_id, "iter": i},
                )
        except Exception as exc:
            errors.append(exc)
            
    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    assert len(errors) == 0, f"Concurrent DLQ writes failed with errors: {errors}"
    stats = manager.get_stats()
    assert stats["total_incidents"] == num_threads * 5


def test_replay_incident_success(temp_dlq_env):
    """Verifies manual replay of a quarantined incident transitions state to RESOLVED."""
    manager = temp_dlq_env["manager"]
    incident = manager.record_failure(
        source_service="media_pipeline",
        error_category=ErrorCategory.API_RATE_LIMIT,
        error_message="429 Resource Exhausted",
        payload={"clip_id": "edm_drop_001.mp4", "resolution": "1080p"},
    )
    
    processed_payloads = []
    def mock_replay_handler(payload):
        processed_payloads.append(payload)
        return {"status": "SUCCESS", "grade": 88.5}
        
    result = manager.replay_incident(incident.incident_id, handler=mock_replay_handler)
    assert result["success"] is True
    assert len(processed_payloads) == 1
    assert processed_payloads[0]["clip_id"] == "edm_drop_001.mp4"
    
    updated = manager.get_incident(incident.incident_id)
    assert updated.status == IncidentStatus.RESOLVED
    assert updated.resolved_at is not None


def test_replay_incident_failure_and_exhaustion(temp_dlq_env):
    """Verifies that repeatedly failing replays increment retry_count and transition to EXHAUSTED upon max_retries."""
    manager = temp_dlq_env["manager"]
    incident = manager.record_failure(
        source_service="ml_grading",
        error_category=ErrorCategory.ML_GRADING_FAILURE,
        error_message="Gemini API 500 internal error",
        payload={"model": "gemini-1.5-pro", "tensor_id": 99},
        max_retries=2,
    )
    
    def failing_handler(payload):
        raise RuntimeError("Service still unavailable")
        
    # Attempt 1 -> Status RETRYING
    res1 = manager.replay_incident(incident.incident_id, handler=failing_handler)
    assert res1["success"] is False
    inc_after_1 = manager.get_incident(incident.incident_id)
    assert inc_after_1.retry_count == 1
    assert inc_after_1.status == IncidentStatus.RETRYING

    # Attempt 2 -> Max retries reached -> Status EXHAUSTED
    res2 = manager.replay_incident(incident.incident_id, handler=failing_handler)
    assert res2["success"] is False
    inc_after_2 = manager.get_incident(incident.incident_id)
    assert inc_after_2.retry_count == 2
    assert inc_after_2.status == IncidentStatus.EXHAUSTED


def test_process_eligible_retries(temp_dlq_env):
    """Verifies automated batch retry processing for incidents whose scheduled retry time has arrived."""
    manager = temp_dlq_env["manager"]
    now = datetime.now(timezone.utc)
    
    # 1. Incident due for retry (past timestamp)
    inc_due = manager.record_failure(
        source_service="sports_cards",
        error_category=ErrorCategory.API_RATE_LIMIT,
        error_message="Rate limited",
        payload={"item": 1},
    )
    # Manually set next_retry_at to past
    past_iso = (now - timedelta(minutes=5)).isoformat()
    manager.update_incident_schedule(inc_due.incident_id, next_retry_at=past_iso)

    # 2. Incident not due yet (future timestamp)
    inc_future = manager.record_failure(
        source_service="sports_cards",
        error_category=ErrorCategory.API_RATE_LIMIT,
        error_message="Rate limited",
        payload={"item": 2},
    )
    future_iso = (now + timedelta(hours=1)).isoformat()
    manager.update_incident_schedule(inc_future.incident_id, next_retry_at=future_iso)

    # Register service handler
    successful_runs = []
    def sports_handler(payload):
        successful_runs.append(payload)
        return True

    results = manager.process_retries(handlers={"sports_cards": sports_handler})
    assert len(results["processed"]) == 1
    assert results["processed"][0]["incident_id"] == inc_due.incident_id
    assert len(successful_runs) == 1


def test_quarantine_corrupt_file(temp_dlq_env):
    """Verifies file-level quarantine moves corrupt files and logs an audit incident."""
    manager = temp_dlq_env["manager"]
    
    # Create a dummy corrupt video file
    dummy_source = os.path.join(temp_dlq_env["dir"], "corrupt_take_01.mp4")
    with open(dummy_source, "wb") as f:
        f.write(b"CORRUPT_BYTES_DATA_NOT_VALID_CONTAINER")
        
    incident, quarantined_path = manager.quarantine_file(
        source_file_path=dummy_source,
        source_service="media_pipeline",
        reason="Invalid MP4 atom container / SHA256 mismatch",
    )
    
    assert not os.path.exists(dummy_source)
    assert os.path.exists(quarantined_path)
    assert "quarantine" in quarantined_path
    assert incident.error_category == ErrorCategory.CORRUPTED_PAYLOAD
    assert incident.payload["quarantined_path"] == quarantined_path


def test_dlq_stats_and_export(temp_dlq_env):
    """Verifies full report export containing forensic categorization."""
    manager = temp_dlq_env["manager"]
    manager.record_failure(
        source_service="ml",
        error_category=ErrorCategory.ML_GRADING_FAILURE,
        error_message="OOM in Spark partition",
        payload={"partition": 3},
    )
    
    report = manager.export_dlq_report()
    assert "generated_at" in report
    assert "stats" in report
    assert "incidents" in report
    assert len(report["incidents"]) == 1
    assert report["incidents"][0]["source_service"] == "ml"
