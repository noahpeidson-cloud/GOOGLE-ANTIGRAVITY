"""Unit tests for SQLite telemetry database, failure lifelines seeding, and CRUD operations."""

import sqlite3
import pytest
from typing import List

from database import (
    get_anomalies_for_session,
    get_db_connection,
    get_historical_drift,
    get_historical_lifelines,
    get_session,
    get_textual_gradients_for_session,
    init_db,
    log_scan_session,
    seed_historical_lifelines,
)
from models import AnomalyRecord, DetectorType, Severity


def test_init_db_creates_tables(mock_db: str) -> None:
    """1. Test that init_db creates all 4 required schema tables."""
    conn = get_db_connection(mock_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row["name"] for row in cursor.fetchall()}
    conn.close()

    assert "scan_sessions" in tables, "Table 'scan_sessions' must exist"
    assert "anomalies" in tables, "Table 'anomalies' must exist"
    assert "historical_lifelines" in tables, "Table 'historical_lifelines' must exist"
    assert "textual_gradients" in tables, "Table 'textual_gradients' must exist"


def test_init_db_wal_mode_and_pragmas(mock_db: str) -> None:
    """2. Test that WAL journal mode, foreign keys, and busy_timeout are enabled."""
    conn = get_db_connection(mock_db)
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode;")
    journal_mode = cursor.fetchone()[0].lower()

    cursor.execute("PRAGMA foreign_keys;")
    foreign_keys = cursor.fetchone()[0]

    cursor.execute("PRAGMA busy_timeout;")
    busy_timeout = cursor.fetchone()[0]

    conn.close()

    assert journal_mode == "wal", f"Expected WAL mode, got {journal_mode}"
    assert foreign_keys == 1, "Foreign keys pragma must be enabled (1)"
    assert busy_timeout == 5000, f"Expected busy_timeout=5000, got {busy_timeout}"


def test_seed_historical_lifelines_idempotence(mock_db: str) -> None:
    """3. Test that seed_historical_lifelines can be called multiple times without duplicate records."""
    # Seed was already called in init_db via fixture
    lifelines_first = get_historical_lifelines(mock_db)
    assert len(lifelines_first) == 5, f"Expected 5 lifelines, found {len(lifelines_first)}"

    # Call seed multiple times
    seed_historical_lifelines(mock_db)
    seed_historical_lifelines(mock_db)

    lifelines_after = get_historical_lifelines(mock_db)
    assert len(lifelines_after) == 5, "Historical lifelines must remain exactly 5 due to idempotency"


def test_historical_lifelines_content(mock_db: str) -> None:
    """4. Test that all 5 August 23/24 failure lifelines exist with accurate codes, detectors, and root causes."""
    lifelines = get_historical_lifelines(mock_db)
    lifeline_dict = {lf["lifeline_code"]: lf for lf in lifelines}

    expected_codes = [
        "GHOST_DAEMONS_WINERROR_10048",
        "CONTEXT_ROT_PLANNING_ARTIFACTS",
        "ECOSYSTEM_POLLUTION_DISABLED_PLUGINS",
        "SECRET_ZERO_PLACEHOLDER_KEYS",
        "PROMPT_FATIGUE_MANIFEST_BLOAT",
    ]

    for code in expected_codes:
        assert code in lifeline_dict, f"Missing historical lifeline code: {code}"

    # Verify specific details
    ghost = lifeline_dict["GHOST_DAEMONS_WINERROR_10048"]
    assert ghost["detector_type"] == DetectorType.GHOST_DAEMONS.value
    assert ghost["severity"] == Severity.CRITICAL.value
    assert "10048" in ghost["title"]

    rot = lifeline_dict["CONTEXT_ROT_PLANNING_ARTIFACTS"]
    assert rot["detector_type"] == DetectorType.CONTEXT_ROT.value
    assert rot["severity"] == Severity.MEDIUM.value
    assert "24h" in rot["title"]

    poll = lifeline_dict["ECOSYSTEM_POLLUTION_DISABLED_PLUGINS"]
    assert poll["detector_type"] == DetectorType.ECOSYSTEM_POLLUTION.value
    assert poll["severity"] == Severity.HIGH.value

    sec = lifeline_dict["SECRET_ZERO_PLACEHOLDER_KEYS"]
    assert sec["detector_type"] == DetectorType.SECRET_ZERO.value
    assert sec["severity"] == Severity.CRITICAL.value

    fatigue = lifeline_dict["PROMPT_FATIGUE_MANIFEST_BLOAT"]
    assert fatigue["detector_type"] == DetectorType.PROMPT_FATIGUE.value
    assert fatigue["severity"] == Severity.MEDIUM.value


def test_log_scan_session_success(mock_db: str, sample_anomalies: List[AnomalyRecord]) -> None:
    """5. Test logging a complete scan session with anomalies and textual gradients."""
    session_id = "session-test-001"
    gradients = [
        "GRADIENT: Context rot clusters on .agents planning artifacts",
        "GRADIENT: Port collisions isolated to Next.js background daemons",
    ]

    log_scan_session(
        session_id=session_id,
        anomalies=sample_anomalies,
        gradients=gradients,
        duration_ms=45.2,
        db_path=mock_db,
        entropy_score=0.78,
        timestamp=1756001000,
    )

    session = get_session(session_id, mock_db)
    assert session is not None, "Session record must exist"
    assert session["session_id"] == session_id
    assert session["duration_ms"] == 45.2
    assert session["total_anomalies"] == 5
    assert session["entropy_score"] == 0.78
    assert session["timestamp"] == 1756001000


def test_get_session(mock_db: str) -> None:
    """6. Test get_session retrieves existing session and returns None for missing."""
    session_id = "session-test-002"
    log_scan_session(
        session_id=session_id,
        anomalies=[],
        gradients=[],
        duration_ms=12.0,
        db_path=mock_db,
        entropy_score=0.1,
    )

    found = get_session(session_id, mock_db)
    assert found is not None
    assert found["session_id"] == session_id
    assert found["total_anomalies"] == 0

    missing = get_session("nonexistent-session", mock_db)
    assert missing is None


def test_get_anomalies_for_session(mock_db: str, sample_anomalies: List[AnomalyRecord]) -> None:
    """7. Test get_anomalies_for_session deserializes JSON raw_details into AnomalyRecord objects."""
    session_id = "session-test-003"
    log_scan_session(
        session_id=session_id,
        anomalies=sample_anomalies,
        gradients=[],
        duration_ms=25.0,
        db_path=mock_db,
    )

    records = get_anomalies_for_session(session_id, mock_db)
    assert len(records) == 5

    # Check first record (Ghost Daemons)
    ghost_rec = records[0]
    assert isinstance(ghost_rec, AnomalyRecord)
    assert ghost_rec.detector_type == DetectorType.GHOST_DAEMONS
    assert ghost_rec.severity == Severity.CRITICAL
    assert ghost_rec.target_path == "127.0.0.1:3000"
    assert ghost_rec.raw_details["port"] == 3000
    assert ghost_rec.raw_details["errno"] == 10048


def test_get_textual_gradients_for_session(mock_db: str) -> None:
    """8. Test get_textual_gradients_for_session returns logged textual gradients."""
    session_id = "session-test-004"
    gradients = [
        "Rule refinement: exclude BRIEFING.md from rot scan",
        "Rule refinement: ignore closed ephemeral test sockets",
    ]

    log_scan_session(
        session_id=session_id,
        anomalies=[],
        gradients=gradients,
        duration_ms=30.0,
        db_path=mock_db,
    )

    retrieved = get_textual_gradients_for_session(session_id, mock_db)
    assert len(retrieved) == 2
    assert retrieved[0] == gradients[0]
    assert retrieved[1] == gradients[1]


def test_atomic_transaction_rollback(mock_db: str, sample_anomalies: List[AnomalyRecord]) -> None:
    """9. Test atomic rollback when an invalid anomaly or error occurs during session logging."""
    session_id = "session-rollback-test"

    # Inject an invalid item into anomalies to cause an exception mid-transaction
    bad_anomalies = [sample_anomalies[0], 12345]  # invalid type integer

    with pytest.raises(ValueError, match="Unsupported anomaly type"):
        log_scan_session(
            session_id=session_id,
            anomalies=bad_anomalies,  # type: ignore
            gradients=[],
            duration_ms=10.0,
            db_path=mock_db,
        )

    # Verify that NOTHING was committed to scan_sessions or anomalies
    session = get_session(session_id, mock_db)
    assert session is None, "Session must NOT be committed on transaction failure"

    anomalies = get_anomalies_for_session(session_id, mock_db)
    assert len(anomalies) == 0, "No anomalies should exist for aborted session"


def test_foreign_key_cascade(mock_db: str, sample_anomalies: List[AnomalyRecord]) -> None:
    """10. Test that deleting a scan session cascades to delete its anomalies and textual gradients."""
    session_id = "session-cascade-test"
    log_scan_session(
        session_id=session_id,
        anomalies=sample_anomalies[:2],
        gradients=["gradient 1", "gradient 2"],
        duration_ms=20.0,
        db_path=mock_db,
    )

    # Verify records exist before delete
    assert len(get_anomalies_for_session(session_id, mock_db)) == 2
    assert len(get_textual_gradients_for_session(session_id, mock_db)) == 2

    # Delete session
    conn = get_db_connection(mock_db)
    with conn:
        conn.execute("DELETE FROM scan_sessions WHERE session_id = ?;", (session_id,))
    conn.close()

    # Verify cascading deletion
    assert get_session(session_id, mock_db) is None
    assert len(get_anomalies_for_session(session_id, mock_db)) == 0
    assert len(get_textual_gradients_for_session(session_id, mock_db)) == 0


def test_get_historical_drift(mock_db: str, sample_anomalies: List[AnomalyRecord]) -> None:
    """11. Test get_historical_drift computes aggregate analytics across sessions."""
    # Log two sessions
    log_scan_session(
        session_id="session-drift-1",
        anomalies=sample_anomalies[:3],
        gradients=["gradient 1"],
        duration_ms=50.0,
        db_path=mock_db,
        entropy_score=0.4,
    )
    log_scan_session(
        session_id="session-drift-2",
        anomalies=sample_anomalies[3:],
        gradients=["gradient 2"],
        duration_ms=150.0,
        db_path=mock_db,
        entropy_score=0.8,
    )

    drift = get_historical_drift(mock_db)
    assert drift["total_sessions"] == 2
    assert drift["total_anomalies"] == 5
    assert drift["average_duration_ms"] == 100.0
    assert abs(drift["average_entropy_score"] - 0.6) < 1e-5
    assert drift["historical_lifelines_count"] == 5
    assert drift["drift_detected"] is True
    assert DetectorType.GHOST_DAEMONS.value in drift["detector_distribution"]
    assert Severity.CRITICAL.value in drift["severity_distribution"]


def test_concurrent_connections(mock_db: str) -> None:
    """12. Test concurrent read/write transactions operating under WAL mode without locking errors."""
    conn1 = get_db_connection(mock_db)
    conn2 = get_db_connection(mock_db)

    try:
        # Write via conn1
        with conn1:
            conn1.execute(
                "INSERT INTO scan_sessions (session_id, timestamp, duration_ms, total_anomalies, entropy_score) VALUES (?, ?, ?, ?, ?);",
                ("concurrent-sess-1", 1756002000, 10.0, 0, 0.0),
            )

        # Read via conn2 immediately
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT COUNT(*) AS count FROM scan_sessions WHERE session_id = 'concurrent-sess-1';")
        count = cursor2.fetchone()["count"]
        assert count == 1, "Concurrent read must immediately reflect committed WAL transaction"

        # Write via conn2
        with conn2:
            conn2.execute(
                "INSERT INTO scan_sessions (session_id, timestamp, duration_ms, total_anomalies, entropy_score) VALUES (?, ?, ?, ?, ?);",
                ("concurrent-sess-2", 1756002001, 15.0, 0, 0.0),
            )

        # Read via conn1
        cursor1 = conn1.cursor()
        cursor1.execute("SELECT COUNT(*) AS count FROM scan_sessions;")
        total_count = cursor1.fetchone()["count"]
        assert total_count >= 2, "Concurrent write from conn2 must be visible in conn1"
    finally:
        conn1.close()
        conn2.close()
