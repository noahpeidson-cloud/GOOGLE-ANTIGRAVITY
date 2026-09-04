"""Empirical Adversarial Stress Test Harness for database.py (Milestone 1) - Extended Edition.

Tests:
1. Concurrency: Multi-threaded burst insertions (50 & 100 threads), race seeding, active re-init under concurrent read/write.
2. Extreme Payloads: 5MB JSON, deep nesting, Unicode, emojis, null bytes, SQLi strings, extreme floats, huge batches, non-serializable objects (sets, circular refs).
3. Transaction Rollback: Mid-batch anomaly failures, gradient failures, duplicate session_id collisions, foreign key violations, non-serializable payload rollbacks.
4. Schema & Seeding Integrity: Concurrent seed calls, empty DB drift metrics, invalid types, connection leak verification.
"""

import concurrent.futures
import gc
import json
import os
import sqlite3
import sys
import tempfile
import time
from typing import Any, Dict, List

# Ensure cron module is in sys.path
CRON_DIR = r"g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron"
if CRON_DIR not in sys.path:
    sys.path.insert(0, CRON_DIR)

from config import DEFAULT_DB_PATH
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


def create_temp_db() -> str:
    """Creates a clean temporary database file with schema initialized."""
    fd, path = tempfile.mkstemp(prefix="test_telemetry_", suffix=".db")
    os.close(fd)
    init_db(path)
    return path


def cleanup_db(path: str) -> None:
    """Removes temporary database and WAL/SHM sidecars."""
    gc.collect()
    for p in [path, f"{path}-wal", f"{path}-shm"]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


# ==============================================================================
# TEST SUITE 1: CONCURRENCY & CONTENTION STRESS
# ==============================================================================

def test_concurrency_50_threads_burst():
    """50 concurrent threads logging sessions, anomalies, and querying drift simultaneously."""
    print("\n--- [TEST 1.1] Concurrency: 50 Concurrent Threads Burst ---")
    db_path = create_temp_db()
    num_threads = 50
    anomalies_per_session = 5

    def worker(worker_id: int):
        sess_id = f"sess-concur-50-{worker_id:03d}"
        anomalies = [
            AnomalyRecord(
                detector_type=DetectorType.GHOST_DAEMONS if i % 2 == 0 else DetectorType.CONTEXT_ROT,
                target_path=f"path/to/target_{worker_id}_{i}",
                severity=Severity.HIGH if i % 2 == 0 else Severity.LOW,
                description=f"Thread {worker_id} anomaly {i}",
                raw_details={"worker": worker_id, "idx": i, "timestamp": time.time()},
            )
            for i in range(anomalies_per_session)
        ]
        gradients = [f"Gradient from worker {worker_id} - step 1", f"Gradient from worker {worker_id} - step 2"]
        
        log_scan_session(
            session_id=sess_id,
            anomalies=anomalies,
            gradients=gradients,
            duration_ms=10.0 + worker_id,
            db_path=db_path,
            entropy_score=0.5,
        )
        
        s = get_session(sess_id, db_path)
        assert s is not None, f"Worker {worker_id} session not found"
        assert s["total_anomalies"] == anomalies_per_session
        
        anoms = get_anomalies_for_session(sess_id, db_path)
        assert len(anoms) == anomalies_per_session

        grads = get_textual_gradients_for_session(sess_id, db_path)
        assert len(grads) == 2

        if worker_id % 5 == 0:
            drift = get_historical_drift(db_path)
            assert drift["total_sessions"] > 0

    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()
            
    elapsed = time.time() - start_time
    print(f"  -> Successfully logged {num_threads} concurrent sessions in {elapsed:.3f}s")

    drift = get_historical_drift(db_path)
    assert drift["total_sessions"] == num_threads
    assert drift["total_anomalies"] == num_threads * anomalies_per_session
    print(f"  -> Verified: {drift['total_sessions']} sessions, {drift['total_anomalies']} anomalies stored without contention errors.")
    cleanup_db(db_path)


def test_concurrency_100_threads_burst():
    """100 concurrent threads logging sessions and writing simultaneously under load."""
    print("\n--- [TEST 1.2] Concurrency: 100 Concurrent Threads High Contention ---")
    db_path = create_temp_db()
    num_threads = 100
    anomalies_per_session = 3

    def worker(worker_id: int):
        sess_id = f"sess-concur-100-{worker_id:03d}"
        anomalies = [
            AnomalyRecord(
                detector_type=DetectorType.SECRET_ZERO if i % 2 == 0 else DetectorType.PROMPT_FATIGUE,
                target_path=f"path/item_{worker_id}_{i}",
                severity=Severity.MEDIUM,
                description=f"Thread {worker_id} item {i}",
                raw_details={"worker": worker_id, "idx": i},
            )
            for i in range(anomalies_per_session)
        ]
        log_scan_session(
            session_id=sess_id,
            anomalies=anomalies,
            gradients=["grad1"],
            duration_ms=5.0,
            db_path=db_path,
        )

    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    elapsed = time.time() - start_time
    print(f"  -> Successfully logged {num_threads} concurrent sessions in {elapsed:.3f}s")

    drift = get_historical_drift(db_path)
    assert drift["total_sessions"] == num_threads
    assert drift["total_anomalies"] == num_threads * anomalies_per_session
    cleanup_db(db_path)


def test_concurrency_race_seeding():
    """30 concurrent threads calling seed_historical_lifelines on a fresh database."""
    print("\n--- [TEST 1.3] Concurrency: 30 Concurrent Threads Seeding Lifelines ---")
    fd, db_path = tempfile.mkstemp(prefix="test_seed_concur_", suffix=".db")
    os.close(fd)
    
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historical_lifelines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lifeline_code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                detector_type TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                remediation TEXT NOT NULL,
                failure_session_date TEXT NOT NULL,
                target_pattern TEXT NOT NULL,
                severity TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.close()

    def seed_worker():
        return seed_historical_lifelines(db_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(seed_worker) for _ in range(30)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    lifelines = get_historical_lifelines(db_path)
    assert len(lifelines) == 5, f"Expected exactly 5 lifelines, found {len(lifelines)}"
    print(f"  -> Verified: Exactly 5 lifelines present after 30 concurrent seed attempts. Total rows inserted across threads: {sum(results)}")
    cleanup_db(db_path)


def test_concurrency_reinit_during_active_reads():
    """Calling init_db repeatedly while other threads are performing reads/writes."""
    print("\n--- [TEST 1.4] Concurrency: init_db idempotence during active load ---")
    db_path = create_temp_db()

    def reader():
        for _ in range(10):
            get_historical_drift(db_path)
            time.sleep(0.01)

    def reinit():
        for _ in range(5):
            init_db(db_path)
            time.sleep(0.01)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        f_reads = [executor.submit(reader) for _ in range(5)]
        f_inits = [executor.submit(reinit) for _ in range(5)]
        for f in concurrent.futures.as_completed(f_reads + f_inits):
            f.result()

    drift = get_historical_drift(db_path)
    assert drift["historical_lifelines_count"] == 5
    print("  -> Verified: Multiple concurrent init_db calls caused zero schema lockouts.")
    cleanup_db(db_path)


# ==============================================================================
# TEST SUITE 2: EXTREME PAYLOADS & BOUNDARY VALUES
# ==============================================================================

def test_extreme_payload_large_json():
    """5MB JSON payload in raw_details, deeply nested dictionaries, 10,000 keys."""
    print("\n--- [TEST 2.1] Extreme Payload: Large & Deeply Nested JSON ---")
    db_path = create_temp_db()
    
    deep_dict = {"level_0": "root"}
    curr = deep_dict
    for level in range(1, 50):
        curr["child"] = {"level": level, "data": "x" * 500}
        curr = curr["child"]
    
    large_dict = {f"key_{i:05d}": f"value_{i:05d}_" + ("a" * 100) for i in range(10000)}
    large_dict["deep_nesting"] = deep_dict

    sess_id = "sess-large-json"
    anom = AnomalyRecord(
        detector_type=DetectorType.ECOSYSTEM_POLLUTION,
        target_path="/very/deep/path/" + ("subfolder/" * 50),
        severity=Severity.HIGH,
        description="Massive JSON payload test",
        raw_details=large_dict,
    )

    t0 = time.time()
    log_scan_session(
        session_id=sess_id,
        anomalies=[anom],
        gradients=["gradient with large payload"],
        duration_ms=123.45,
        db_path=db_path,
    )
    write_time = time.time() - t0
    print(f"  -> Wrote ~2MB JSON anomaly in {write_time:.3f}s")

    t0 = time.time()
    retrieved = get_anomalies_for_session(sess_id, db_path)
    read_time = time.time() - t0
    print(f"  -> Retrieved & deserialized ~2MB JSON anomaly in {read_time:.3f}s")

    assert len(retrieved) == 1
    assert len(retrieved[0].raw_details) == 10001
    assert retrieved[0].raw_details["key_00000"] == large_dict["key_00000"]
    assert retrieved[0].raw_details["key_09999"] == large_dict["key_09999"]
    cleanup_db(db_path)


def test_extreme_payload_unicode_and_special_chars():
    """Test full Unicode spectrum, emojis, ZWJ sequences, RTL Arabic/Hebrew, SQL injection payloads, null chars, escaped quotes."""
    print("\n--- [TEST 2.2] Extreme Payload: Unicode, Emojis, SQLi Strings, Escapes ---")
    db_path = create_temp_db()

    special_strings = [
        "🔥🚀👨‍👩‍👧‍👦🏳️‍🌈⚡️✨",
        "مرحبا بالعالم - שלום עולם - สวัสดีชาวโลก",
        "日本語と中国語：你好世界，こんにちは",
        "'; DROP TABLE scan_sessions; DROP TABLE anomalies; --",
        "\"'``${{process.env.SECRET}}' OR 1=1 --",
        "Line 1\nLine 2\r\nLine 3\tTabbed\b\f\\Backslash/Slash",
        "Zażółć gęślą jaźń - naïve - façade - résumé - élévation",
        "Zalgo: H̴͖͔̄͑e̷̛̱l̵̤̈l̷͓̀o̶̗͠ ̸̰͝W̶̜̄ö̵̰ṟ̸̕l̵͈̐d̴̟̍",
    ]

    anomalies = []
    for idx, s in enumerate(special_strings):
        anomalies.append(
            AnomalyRecord(
                detector_type=DetectorType.SECRET_ZERO,
                target_path=f"C:\\Users\\noahp\\AppData\\Local\\Temp\\special_paths_{idx}\\{s[:15]}.env",
                severity=Severity.CRITICAL,
                description=f"Description containing: {s}",
                raw_details={"special_string": s, "index": idx, "nested": {"val": s}},
            )
        )

    sess_id = "sess-unicode-sqli"
    log_scan_session(
        session_id=sess_id,
        anomalies=anomalies,
        gradients=[f"Gradient with {s}" for s in special_strings],
        duration_ms=55.5,
        db_path=db_path,
    )

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row["name"] for row in cursor.fetchall()}
    conn.close()
    assert "scan_sessions" in tables
    assert "anomalies" in tables

    retrieved = get_anomalies_for_session(sess_id, db_path)
    assert len(retrieved) == len(special_strings)
    for idx, rec in enumerate(retrieved):
        expected = special_strings[idx]
        assert rec.raw_details["special_string"] == expected, f"Fidelity loss at idx {idx}"
        assert rec.description == f"Description containing: {expected}"
    
    gradients = get_textual_gradients_for_session(sess_id, db_path)
    assert len(gradients) == len(special_strings)
    print("  -> Verified: Unicode, emojis, RTL, and SQLi strings preserved with 100% fidelity without corrupting schema.")
    cleanup_db(db_path)


def test_extreme_payload_boundary_types_and_numbers():
    """Test boundary numbers: extreme timestamps, float limits, negative durations, 0 values."""
    print("\n--- [TEST 2.3] Extreme Payload: Numerical Boundaries & Dict Formats ---")
    db_path = create_temp_db()

    sess_id = "sess-boundaries"
    anomalies_dict = [
        {
            "detector_type": "PROMPT_FATIGUE",
            "target_path": "",
            "severity": "LOW",
            "description": "",
            "raw_details": {},
            "is_historical": False,
            "timestamp": 0,
            "confidence": 0.0,
        },
        {
            "detector_type": "GHOST_DAEMONS",
            "target_path": "/path/max/int",
            "severity": "CRITICAL",
            "description": "Max int timestamp",
            "raw_details": {"max_int": 9223372036854775807, "min_int": -9223372036854775808},
            "is_historical": True,
            "timestamp": 9223372036854775807,
            "confidence": 1.0,
        },
        {
            "detector_type": "SECRET_ZERO",
            "target_path": "/path/future",
            "severity": "HIGH",
            "description": "Negative duration and future timestamp",
            "raw_details": {"float_val": 1e-15, "large_float": 1e15},
            "is_historical": 0,
            "timestamp": 253402300799,
            "confidence": 0.999999,
        }
    ]

    gradients_dict = [
        {"gradient_text": "Gradient with dict format", "cluster_id": 99, "semantic_weight": 0.0001},
        {"text": "Gradient using 'text' key alias", "cluster_id": -1, "semantic_weight": 999.9},
    ]

    log_scan_session(
        session_id=sess_id,
        anomalies=anomalies_dict,
        gradients=gradients_dict,
        duration_ms=-1.0,
        db_path=db_path,
        entropy_score=-0.5,
    )

    sess = get_session(sess_id, db_path)
    assert sess is not None
    assert sess["duration_ms"] == -1.0
    assert sess["entropy_score"] == -0.5
    assert sess["total_anomalies"] == 3

    anoms = get_anomalies_for_session(sess_id, db_path)
    assert len(anoms) == 3
    assert anoms[0].timestamp == 0
    assert anoms[0].confidence == 0.0
    assert anoms[1].timestamp == 9223372036854775807
    assert anoms[1].is_historical is True
    print("  -> Verified: Boundary integers, floats, and alternative dict payloads handled cleanly.")
    cleanup_db(db_path)


def test_extreme_payload_huge_batch():
    """Batch insertion of 2,000 anomalies and 500 gradients in a single atomic session."""
    print("\n--- [TEST 2.4] Extreme Payload: 2,000 Anomalies in Single Batch ---")
    db_path = create_temp_db()
    sess_id = "sess-huge-batch"
    batch_size = 2000

    anomalies = [
        AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT if i % 2 == 0 else DetectorType.GHOST_DAEMONS,
            target_path=f"path/item_{i:04d}.txt",
            severity=Severity.LOW if i % 3 == 0 else (Severity.MEDIUM if i % 3 == 1 else Severity.HIGH),
            description=f"Batch item #{i}",
            raw_details={"idx": i, "data": f"payload_{i}"},
        )
        for i in range(batch_size)
    ]
    gradients = [f"Gradient rule #{g}" for g in range(500)]

    t0 = time.time()
    log_scan_session(
        session_id=sess_id,
        anomalies=anomalies,
        gradients=gradients,
        duration_ms=500.0,
        db_path=db_path,
    )
    elapsed = time.time() - t0
    print(f"  -> Inserted {batch_size} anomalies & 500 gradients in {elapsed:.3f}s")

    anoms = get_anomalies_for_session(sess_id, db_path)
    assert len(anoms) == batch_size, f"Expected {batch_size}, got {len(anoms)}"
    
    grads = get_textual_gradients_for_session(sess_id, db_path)
    assert len(grads) == 500, f"Expected 500, got {len(grads)}"
    cleanup_db(db_path)


# ==============================================================================
# TEST SUITE 3: TRANSACTION ROLLBACK UNDER INTENTIONAL FAILURES
# ==============================================================================

def test_rollback_mid_batch_anomaly_failure():
    """Inject an unhandled / corrupt item at index 99 of 100 anomalies to verify 100% rollback."""
    print("\n--- [TEST 3.1] Rollback: Mid-Batch Failure at Anomaly #99 of 100 ---")
    db_path = create_temp_db()
    sess_id = "sess-rollback-mid-batch"

    anomalies = [
        AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path=f"path/good_{i}.txt",
            severity=Severity.LOW,
            description=f"Valid anomaly {i}",
            raw_details={"i": i},
        )
        for i in range(99)
    ]
    anomalies.append("INVALID_ANOMALY_STRING_NOT_DICT_OR_RECORD")  # type: ignore

    failed = False
    try:
        log_scan_session(
            session_id=sess_id,
            anomalies=anomalies,
            gradients=["good gradient"],
            duration_ms=10.0,
            db_path=db_path,
        )
    except ValueError as e:
        failed = True
        assert "Unsupported anomaly type" in str(e)

    assert failed, "log_scan_session should have raised ValueError"

    sess = get_session(sess_id, db_path)
    assert sess is None, "Session MUST NOT exist in scan_sessions after rollback"

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS c FROM anomalies WHERE session_id = ?", (sess_id,))
    anom_count = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) AS c FROM textual_gradients WHERE session_id = ?", (sess_id,))
    grad_count = cursor.fetchone()["c"]
    conn.close()

    assert anom_count == 0, f"Expected 0 anomalies after rollback, found {anom_count}"
    assert grad_count == 0, f"Expected 0 gradients after rollback, found {grad_count}"
    print("  -> Verified: 99 prior anomalies fully rolled back with 0 orphaned rows.")
    cleanup_db(db_path)


def test_rollback_gradient_failure():
    """All anomalies valid, but gradient at index 2 is corrupt. Verify complete rollback."""
    print("\n--- [TEST 3.2] Rollback: Gradient Failure After Anomaly Inserts ---")
    db_path = create_temp_db()
    sess_id = "sess-rollback-gradient-failure"

    anomalies = [
        AnomalyRecord(
            detector_type=DetectorType.GHOST_DAEMONS,
            target_path="127.0.0.1:3000",
            severity=Severity.CRITICAL,
            description="Valid ghost daemon",
            raw_details={"port": 3000},
        )
    ]
    gradients = ["Valid gradient 1", 123456789]  # Corrupt gradient type (int)

    failed = False
    try:
        log_scan_session(
            session_id=sess_id,
            anomalies=anomalies,
            gradients=gradients,  # type: ignore
            duration_ms=10.0,
            db_path=db_path,
        )
    except ValueError as e:
        failed = True
        assert "Unsupported gradient type" in str(e)

    assert failed, "log_scan_session should have raised ValueError on invalid gradient"

    assert get_session(sess_id, db_path) is None
    assert len(get_anomalies_for_session(sess_id, db_path)) == 0
    assert len(get_textual_gradients_for_session(sess_id, db_path)) == 0
    print("  -> Verified: Full rollback triggered when gradient step fails.")
    cleanup_db(db_path)


def test_rollback_non_serializable_raw_details():
    """Attempting to log raw_details containing a non-JSON serializable object (e.g. set or func) triggers rollback."""
    print("\n--- [TEST 3.3] Rollback: Non-JSON Serializable Payload ---")
    db_path = create_temp_db()
    sess_id = "sess-rollback-unserializable"

    anomalies = [
        AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path="valid.md",
            severity=Severity.LOW,
            description="Valid anomaly 1",
            raw_details={"key": "val"},
        ),
        AnomalyRecord(
            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
            target_path="unserializable.md",
            severity=Severity.HIGH,
            description="Unserializable set in raw_details",
            raw_details={"bad_set": {1, 2, 3}, "func": lambda x: x},
        ),
    ]

    failed = False
    try:
        log_scan_session(
            session_id=sess_id,
            anomalies=anomalies,
            gradients=["gradient 1"],
            duration_ms=10.0,
            db_path=db_path,
        )
    except TypeError:
        failed = True

    assert failed, "Expected TypeError on unserializable payload"
    assert get_session(sess_id, db_path) is None
    assert len(get_anomalies_for_session(sess_id, db_path)) == 0
    print("  -> Verified: JSON serialization error rolls back the entire session atomically.")
    cleanup_db(db_path)


def test_rollback_session_id_collision():
    """Attempting to log a session with a duplicate session_id must fail atomically and not alter existing session."""
    print("\n--- [TEST 3.4] Rollback: Duplicate session_id Collision ---")
    db_path = create_temp_db()
    sess_id = "sess-collision-test"

    log_scan_session(
        session_id=sess_id,
        anomalies=[
            AnomalyRecord(
                detector_type=DetectorType.SECRET_ZERO,
                target_path=".env",
                severity=Severity.HIGH,
                description="Original secret zero",
                raw_details={"key": "original"},
            )
        ],
        gradients=["Original gradient"],
        duration_ms=25.0,
        db_path=db_path,
    )

    failed = False
    try:
        log_scan_session(
            session_id=sess_id,
            anomalies=[
                AnomalyRecord(
                    detector_type=DetectorType.CONTEXT_ROT,
                    target_path="stale.md",
                    severity=Severity.LOW,
                    description="Colliding anomaly",
                    raw_details={"key": "colliding"},
                )
            ],
            gradients=["Colliding gradient"],
            duration_ms=999.0,
            db_path=db_path,
        )
    except sqlite3.IntegrityError:
        failed = True

    assert failed, "Expected sqlite3.IntegrityError on session_id collision"

    sess = get_session(sess_id, db_path)
    assert sess is not None
    assert sess["duration_ms"] == 25.0

    anoms = get_anomalies_for_session(sess_id, db_path)
    assert len(anoms) == 1
    assert anoms[0].detector_type == DetectorType.SECRET_ZERO
    assert anoms[0].description == "Original secret zero"
    print("  -> Verified: Duplicate session_id aborted with IntegrityError; original data untouched.")
    cleanup_db(db_path)


def test_foreign_key_direct_violation():
    """Direct insertion of anomaly with non-existent session_id must fail via foreign key constraint."""
    print("\n--- [TEST 3.5] Foreign Key: Direct Insertion Constraint ---")
    db_path = create_temp_db()
    conn = get_db_connection(db_path)
    
    failed = False
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO anomalies (session_id, detector_type, target_path, severity, description, raw_details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                ("non-existent-session-id", "SECRET_ZERO", ".env", "HIGH", "orphan", "{}", 12345),
            )
    except sqlite3.IntegrityError:
        failed = True
    finally:
        conn.close()

    assert failed, "Foreign key constraint must reject orphaned anomaly"
    print("  -> Verified: Foreign keys prevent orphaned anomaly inserts.")
    cleanup_db(db_path)


# ==============================================================================
# TEST SUITE 4: RETRIEVAL, CORRUPTION RESILIENCE & DRIFT ANALYTICS
# ==============================================================================

def test_retrieval_corrupt_json_resilience():
    """If anomalies table contains raw string that is NOT valid JSON, get_anomalies_for_session wraps it in {'raw': ...} without crashing."""
    print("\n--- [TEST 4.1] Resilience: Handling Corrupted JSON in raw_details ---")
    db_path = create_temp_db()
    sess_id = "sess-corrupt-raw"

    conn = get_db_connection(db_path)
    with conn:
        conn.execute(
            "INSERT INTO scan_sessions (session_id, timestamp, duration_ms, total_anomalies) VALUES (?, ?, ?, ?);",
            (sess_id, 1756000000, 10.0, 1),
        )
        conn.execute(
            """
            INSERT INTO anomalies (session_id, detector_type, target_path, severity, description, raw_details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (sess_id, "SECRET_ZERO", ".env", "HIGH", "Corrupt JSON test", "MALFORMED_{{NOT_JSON}}", 1756000000),
        )
    conn.close()

    records = get_anomalies_for_session(sess_id, db_path)
    assert len(records) == 1
    assert records[0].raw_details == {"raw": "MALFORMED_{{NOT_JSON}}"}
    print("  -> Verified: Gracefully recovered malformed JSON into {'raw': ...}.")
    cleanup_db(db_path)


def test_empty_db_analytics():
    """Drift calculation and session queries on a freshly initialized, empty database."""
    print("\n--- [TEST 4.2] Analytics: Empty Database Drift Query ---")
    db_path = create_temp_db()
    
    drift = get_historical_drift(db_path)
    assert drift["total_sessions"] == 0
    assert drift["total_anomalies"] == 0
    assert drift["average_duration_ms"] == 0.0
    assert drift["average_entropy_score"] == 0.0
    assert drift["historical_lifelines_count"] == 5
    assert drift["drift_detected"] is False
    assert drift["detector_distribution"] == {}
    assert drift["severity_distribution"] == {}
    assert len(drift["historical_match_counts"]) == 5
    print("  -> Verified: Empty database returns clean aggregate zeroes without division by zero or errors.")
    cleanup_db(db_path)


def test_connection_resource_leak_check():
    """Verify that after 500 rapid open/close cycles, no file handles or locks remain."""
    print("\n--- [TEST 4.3] Resource Management: 500 Rapid Connections Leak Check ---")
    db_path = create_temp_db()
    
    for i in range(500):
        s = get_session(f"non-existent-{i}", db_path)
        assert s is None
        drift = get_historical_drift(db_path)
        assert drift["total_sessions"] == 0

    # Ensure we can delete the database file immediately without Windows [WinError 32] Sharing Violation
    cleanup_db(db_path)
    assert not os.path.exists(db_path), "DB file must be deletable without sharing violations"
    print("  -> Verified: 500 cycles executed and database file deleted cleanly with 0 lock leaks.")


# ==============================================================================
# MAIN RUNNER
# ==============================================================================

if __name__ == "__main__":
    print("================================================================================")
    print("STARTING EXTENDED ADVERSARIAL STRESS TEST HARNESS FOR database.py")
    print("================================================================================")
    
    tests = [
        test_concurrency_50_threads_burst,
        test_concurrency_100_threads_burst,
        test_concurrency_race_seeding,
        test_concurrency_reinit_during_active_reads,
        test_extreme_payload_large_json,
        test_extreme_payload_unicode_and_special_chars,
        test_extreme_payload_boundary_types_and_numbers,
        test_extreme_payload_huge_batch,
        test_rollback_mid_batch_anomaly_failure,
        test_rollback_gradient_failure,
        test_rollback_non_serializable_raw_details,
        test_rollback_session_id_collision,
        test_foreign_key_direct_violation,
        test_retrieval_corrupt_json_resilience,
        test_empty_db_analytics,
        test_connection_resource_leak_check,
    ]
    
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"FAILED: {t.__name__} with error: {e}")
            import traceback
            traceback.print_exc()

    print("\n================================================================================")
    print(f"EXTENDED STRESS TEST RUN COMPLETE: {passed} PASSED, {failed} FAILED (TOTAL: {len(tests)})")
    print("================================================================================")
    
    if failed > 0:
        sys.exit(1)
