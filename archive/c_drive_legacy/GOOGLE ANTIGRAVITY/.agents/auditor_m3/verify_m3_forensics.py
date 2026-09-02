"""Independent Forensic Integrity Verification Script for Milestone 3: Antigravity ML Agent.
Tests:
1. Genuine Lloyd's Algorithm Iteration, K-Means++ Initialization, and Euclidean Distance Math
2. Non-Deterministic / Dynamic Response to Arbitrary Data (No Hardcoding)
3. Authentic SQLite WAL Concurrency & Pragma Enforcement
4. True Mark-and-Sweep Garbage Collection & Date Arithmetic
5. Dynamic Policy State Machine Transitions & Persistence
6. Prohibited Pattern & Facade Detection across all source files
"""

import os
import sys
import time
import uuid
import tempfile
import sqlite3
import threading

sys.path.insert(0, os.path.abspath("g:/My Drive/GOOGLE ANTIGRAVITY"))

import numpy as np
import pandas as pd

from unified_ops_hub.ml_agent.clustering import KMeansOptimizer
from unified_ops_hub.ml_agent.telemetry import TelemetryStore
from unified_ops_hub.ml_agent.policy import PolicyEngine
from unified_ops_hub.ml_agent.ml_agent import (
    AutonomousMLAgent,
    build_ml_agent_config,
    execute_trends_garbage_collection,
)

def log_check(name: str, passed: bool, details: str = ""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {name}")
    if details:
        print(f"       Details: {details}")
    if not passed:
        raise AssertionError(f"Check failed: {name} - {details}")


def test_kmeans_lloyds_algorithm_authenticity():
    print("\n--- 1. Testing Lloyd's Algorithm & Euclidean Distance Authenticity ---")
    
    # Generate 3 well-separated synthetic clusters in 3D
    np.random.seed(12345)
    c1 = np.random.randn(30, 3) * 0.1 + np.array([500.0, 30.0, 0.0])   # Healthy: short duration, high yield, 0 errors
    c2 = np.random.randn(30, 3) * 0.1 + np.array([18000.0, 2.0, 3.0]) # Degraded: long duration, low yield, some errors
    c3 = np.random.randn(30, 3) * 0.1 + np.array([2000.0, 0.0, 8.0])  # Failure: med duration, 0 yield, high errors
    
    all_data = np.vstack([c1, c2, c3])
    df = pd.DataFrame(all_data, columns=["duration_ms", "yield_count", "error_count"])
    
    optimizer = KMeansOptimizer(k=3, random_state=42, max_iter=20)
    labels, centroids, counts = optimizer.fit_predict(df)
    
    # Verify shape and contents
    log_check("Cluster labels length matches input", len(labels) == 90, f"Got {len(labels)}")
    log_check("Centroids shape is (3, 3)", centroids.shape == (3, 3), f"Shape: {centroids.shape}")
    log_check("Each cluster has exactly 30 samples", counts[0] == 30 and counts[1] == 30 and counts[2] == 30, f"Counts: {counts}")
    
    # Verify semantic ordering: Cluster 0 must correspond to c1 (Healthy), Cluster 1 to c2 (Degraded), Cluster 2 to c3 (Failure)
    first_30 = labels[:30]
    mid_30 = labels[30:60]
    last_30 = labels[60:90]
    
    log_check("Semantic ordering maps c1 to Cluster 0 (Healthy)", np.all(first_30 == 0), f"Labels: {set(first_30)}")
    log_check("Semantic ordering maps c2 to Cluster 1 (Degraded)", np.all(mid_30 == 1), f"Labels: {set(mid_30)}")
    log_check("Semantic ordering maps c3 to Cluster 2 (Failure)", np.all(last_30 == 2), f"Labels: {set(last_30)}")
    
    # Test with randomized perturbed data to prove NO hardcoding
    for seed in [101, 202, 303]:
        np.random.seed(seed)
        p1 = np.random.randn(20, 3) * 0.2 + np.array([400.0, 40.0, 0.0])
        p2 = np.random.randn(25, 3) * 0.2 + np.array([22000.0, 1.0, 4.0])
        p3 = np.random.randn(15, 3) * 0.2 + np.array([3000.0, 0.0, 10.0])
        p_df = pd.DataFrame(np.vstack([p1, p2, p3]), columns=["duration_ms", "yield_count", "error_count"])
        
        p_opt = KMeansOptimizer(k=3, random_state=seed, max_iter=25)
        p_labels, p_centroids, p_counts = p_opt.fit_predict(p_df)
        
        log_check(f"Dynamic clustering with seed {seed}", p_counts[0] == 20 and p_counts[1] == 25 and p_counts[2] == 15,
                  f"Counts: {p_counts}, Centroids:\n{p_centroids}")


def test_kmeans_boundary_cases():
    print("\n--- 2. Testing K-Means Boundary Conditions ---")
    opt = KMeansOptimizer(k=3, random_state=42)
    
    # 1. Empty DataFrame
    empty_df = pd.DataFrame(columns=["duration_ms", "yield_count", "error_count"])
    labels, centroids, counts = opt.fit_predict(empty_df)
    log_check("Empty DataFrame returns empty arrays without crash", len(labels) == 0 and counts == {})
    
    # 2. Single row (N = 1 < K)
    single_df = pd.DataFrame([{"duration_ms": 500, "yield_count": 20, "error_count": 0}])
    labels, centroids, counts = opt.fit_predict(single_df)
    log_check("Single row handled via cold-start fallback", len(labels) == 1 and labels[0] == 0)
    
    # 3. Two rows (N = 2 < K) with failure
    two_df = pd.DataFrame([
        {"duration_ms": 500, "yield_count": 20, "error_count": 0},
        {"duration_ms": 5000, "yield_count": 0, "error_count": 4}
    ])
    labels, centroids, counts = opt.fit_predict(two_df)
    log_check("Two rows handled via cold-start fallback", len(labels) == 2 and labels[0] == 0 and labels[1] == 2)
    
    # 4. Zero variance (all points identical)
    identical_df = pd.DataFrame([
        {"duration_ms": 1000, "yield_count": 10, "error_count": 0} for _ in range(20)
    ])
    labels, centroids, counts = opt.fit_predict(identical_df)
    log_check("Identical points handled without NaN or division by zero", len(labels) == 20 and not np.isnan(centroids).any())


def test_sqlite_wal_and_concurrency(tmp_path):
    print("\n--- 3. Testing SQLite WAL Concurrency & Storage Integrity ---")
    db_path = os.path.join(tmp_path, "telemetry_test.db")
    store = TelemetryStore(db_path)
    
    # Verify WAL mode on file
    with store.get_connection() as conn:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        sync = conn.execute("PRAGMA synchronous;").fetchone()[0]
        busy = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        log_check("PRAGMA journal_mode is WAL", mode.lower() == "wal", f"Got: {mode}")
        log_check("PRAGMA synchronous is NORMAL (1)", sync == 1, f"Got: {sync}")
        log_check("PRAGMA busy_timeout is 5000ms", busy == 5000, f"Got: {busy}")
    
    # Multi-threaded stress test: 12 threads writing simultaneously
    num_threads = 12
    writes_per_thread = 25
    errors = []
    
    def writer(t_id):
        try:
            for w in range(writes_per_thread):
                store.record_span(
                    platform=f"platform_{t_id % 3}",
                    lens_type="web_a11y_tree",
                    duration_ms=500 + w * 20,
                    yield_count=w + 1,
                    error_count=0 if w % 5 != 0 else 1,
                    status_code="SUCCESS" if w % 5 != 0 else "ERROR",
                )
        except Exception as e:
            errors.append(e)
            
    threads = [threading.Thread(target=writer, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    log_check("Zero database lock collisions under concurrent writes", len(errors) == 0, f"Errors: {errors}")
    spans = store.get_recent_spans(limit=1000)
    expected_total = num_threads * writes_per_thread
    log_check(f"All {expected_total} spans persisted accurately", len(spans) == expected_total, f"Found {len(spans)}")


def test_mark_and_sweep_gc_authenticity(tmp_path):
    print("\n--- 4. Testing Authentic Mark-and-Sweep Garbage Collection ---")
    db_path = os.path.join(tmp_path, "telemetry_gc.db")
    store = TelemetryStore(db_path)
    
    now_ms = int(time.time() * 1000)
    day_ms = 86400 * 1000
    
    # Insert specific time-distributed spans
    timestamps = [
        ("span_30d_old", now_ms - (30 * day_ms)), # Stale -> delete
        ("span_15d_old", now_ms - (15 * day_ms)), # Stale -> delete
        ("span_14d_1s_old", now_ms - (14 * day_ms + 1000)), # Stale -> delete
        ("span_13d_old", now_ms - (13 * day_ms)), # Active -> keep
        ("span_5d_old", now_ms - (5 * day_ms)),   # Active -> keep
        ("span_now", now_ms),                      # Active -> keep
    ]
    
    for s_id, ts in timestamps:
        store.record_span(
            platform="tiktok",
            lens_type="web_a11y_tree",
            duration_ms=1000,
            yield_count=10,
            error_count=0,
            status_code="SUCCESS",
            span_id=s_id,
            timestamp_ms=ts,
        )
    
    spans_before = store.get_recent_spans(limit=50)
    log_check("6 spans successfully seeded for GC test", len(spans_before) == 6)
    
    deleted_count = store.mark_and_sweep_telemetry(retention_days=14)
    log_check("mark_and_sweep_telemetry deletes exactly the 3 stale records (>14 days)", deleted_count == 3, f"Deleted: {deleted_count}")
    
    spans_after = store.get_recent_spans(limit=50)
    remaining_ids = set(spans_after["span_id"].tolist())
    expected_remaining = {"span_13d_old", "span_5d_old", "span_now"}
    log_check("Remaining spans exactly match the active 14-day window", remaining_ids == expected_remaining, f"Remaining: {remaining_ids}")

    # Test Trends DB Garbage Collection & Markdown Generation
    trends_db = os.path.join(tmp_path, "trends_test.db")
    trends_md = os.path.join(tmp_path, "current_trends_test.md")
    
    with sqlite3.connect(trends_db) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                topic_category TEXT NOT NULL,
                hashtag_or_audio TEXT NOT NULL,
                velocity_score REAL NOT NULL,
                date_added TEXT NOT NULL
            )
            """
        )
        conn.execute("INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) VALUES ('tiktok', 'Sports', '#StaleTag', 50.0, date('now', '-20 days'))")
        conn.execute("INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) VALUES ('youtube_shorts', 'EDM', '#ActiveTag', 95.0, date('now', '-2 days'))")
        conn.commit()
        
    trends_deleted = execute_trends_garbage_collection(trends_db, trends_md)
    log_check("execute_trends_garbage_collection deletes exactly 1 stale item", trends_deleted == 1, f"Deleted: {trends_deleted}")
    log_check("Markdown catalog artifact generated", os.path.exists(trends_md))
    
    with open(trends_md, "r", encoding="utf-8") as f:
        md_text = f.read()
    log_check("Markdown includes active tag", "#ActiveTag" in md_text)
    log_check("Markdown excludes purged stale tag", "#StaleTag" not in md_text)


def test_dynamic_policy_state_machine(tmp_path):
    print("\n--- 5. Testing Policy Engine Dynamic State Machine ---")
    db_path = os.path.join(tmp_path, "telemetry_policy.db")
    store = TelemetryStore(db_path)
    engine = PolicyEngine(store)
    
    # 1. Inject Cluster 1 degradation (Rate limiting)
    for _ in range(10):
        store.record_span("tiktok", "web_a11y_tree", duration_ms=18000, yield_count=2, error_count=2, status_code="RATE_LIMITED")
    r1 = engine.evaluate_and_adjust("tiktok")
    log_check("Degradation triggers THROTTLE action", r1["action"] == "THROTTLE", f"Action: {r1['action']}")
    
    # 2. Inject Cluster 2 DOM Drift (Zero yield, heavy error)
    for _ in range(10):
        store.record_span("tiktok", "web_a11y_tree", duration_ms=1200, yield_count=0, error_count=8, status_code="DOM_DRIFT")
    r2 = engine.evaluate_and_adjust("tiktok")
    log_check("Critical DOM Drift triggers LENS_SWAP action to android_ui_dump", r2["action"] == "LENS_SWAP" and r2["new_lens"] == "android_ui_dump", f"Result: {r2}")
    
    # 3. Inject Cluster 0 Recovery (High yield, fast, zero error)
    for _ in range(15):
        store.record_span("tiktok", "android_ui_dump", duration_ms=600, yield_count=30, error_count=0, status_code="SUCCESS")
    r3 = engine.evaluate_and_adjust("tiktok")
    log_check("Healthy performance triggers RECOVER action", r3["action"] == "RECOVER", f"Result: {r3}")


def test_source_code_forensics():
    print("\n--- 6. Scanning Source Code for Prohibited Patterns ---")
    ml_agent_dir = os.path.abspath("g:/My Drive/GOOGLE ANTIGRAVITY/unified_ops_hub/ml_agent")
    tests_file = os.path.abspath("g:/My Drive/GOOGLE ANTIGRAVITY/unified_ops_hub/tests/test_ml_agent.py")
    
    files_to_scan = [
        os.path.join(ml_agent_dir, "__init__.py"),
        os.path.join(ml_agent_dir, "clustering.py"),
        os.path.join(ml_agent_dir, "policy.py"),
        os.path.join(ml_agent_dir, "telemetry.py"),
        os.path.join(ml_agent_dir, "ml_agent.py"),
        tests_file,
    ]
    
    prohibited_keywords = [
        "return [0, 0, 0]",
        "return [1, 1, 1]",
        "return [2, 2, 2]",
        "pytest.skip(",
        "unittest.skip(",
        "# type: ignore",
        "mock.return_value = 'CLEAN'",
        "pass  # fake",
    ]
    
    for fpath in files_to_scan:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        for kw in prohibited_keywords:
            if kw in content:
                log_check(f"Prohibited pattern '{kw}' found in {os.path.basename(fpath)}", False)
        log_check(f"Clean static audit: {os.path.basename(fpath)}", True)


def main():
    print("=" * 70)
    print("STARTING FORENSIC INTEGRITY AUDIT: MILESTONE 3 (ML AGENT)")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        test_kmeans_lloyds_algorithm_authenticity()
        test_kmeans_boundary_cases()
        test_sqlite_wal_and_concurrency(tmp_dir)
        test_mark_and_sweep_gc_authenticity(tmp_dir)
        test_dynamic_policy_state_machine(tmp_dir)
        test_source_code_forensics()
        
    print("\n" + "=" * 70)
    print("ALL FORENSIC INTEGRITY CHECKS PASSED: VERDICT = CLEAN")
    print("=" * 70)

if __name__ == "__main__":
    main()
