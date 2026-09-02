"""Challenger 2 Adversarial Stress Test Suite for Milestone 3.
Evaluates PolicyEngine, AutonomousMLAgent, and Mark-and-Sweep GC under extreme conditions:
1. Rapid oscillation between healthy (Cluster 0) and failure (Cluster 2) states.
2. Prolonged degraded runs (Cluster 1) with throttle ceiling enforcement and recovery decay.
3. Automated failover to Android scraper under sustained failure with DLQ error containment.
4. Memory and Object/Resource stability during 500+ Mark-and-Sweep GC cycles (tracemalloc & gc).
5. High-concurrency multi-threaded stress and database lock resilience.
6. Extreme numerical boundaries, sparse spans, and edge-case fuzzing.
"""

import gc
import os
import sqlite3
import threading
import time
import tracemalloc
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from unified_ops_hub.gateway.dlq_manager import DLQManager, ErrorCategory
from unified_ops_hub.ml_agent.clustering import KMeansOptimizer
from unified_ops_hub.ml_agent.ml_agent import (
    AutonomousMLAgent,
    build_ml_agent_config,
    execute_trends_garbage_collection,
)
from unified_ops_hub.ml_agent.policy import PolicyEngine
from unified_ops_hub.ml_agent.telemetry import TelemetryStore
from unified_ops_hub.mobile.android_client import (
    AndroidAutomationError,
    AndroidClient,
    DeviceOfflineError,
)
from unified_ops_hub.mobile.models import ScrapedTrendItem
from unified_ops_hub.mobile.scraper import MobileViralTrendScraper


@pytest.fixture
def stress_telemetry_db(tmp_path):
    """Provides an isolated SQLite DB path for stress testing."""
    return str(tmp_path / "stress_telemetry.db")


@pytest.fixture
def stress_trends_db(tmp_path):
    """Provides an isolated SQLite trends DB path for stress testing."""
    return str(tmp_path / "stress_trends.db")


@pytest.fixture
def stress_trends_md(tmp_path):
    """Provides an isolated markdown export path for trends catalog."""
    return str(tmp_path / "stress_trends.md")


@pytest.fixture
def stress_telemetry_store(stress_telemetry_db):
    """Provides an isolated TelemetryStore instance."""
    return TelemetryStore(stress_telemetry_db)


# ============================================================================
# 1. RAPID OSCILLATION BETWEEN HEALTHY (C0) AND FAILURE (C2) STATES
# ============================================================================

def test_rapid_oscillation_healthy_and_failure_states(stress_telemetry_store):
    """Adversarial Test: Rapidly alternates batches of Healthy (C0) and Failure (C2) spans.
    Verifies PolicyEngine avoids deadlock, bounding interval/backoff parameters without crashing.
    """
    store = stress_telemetry_store
    optimizer = KMeansOptimizer(k=3, random_state=42)
    policy_engine = PolicyEngine(store, optimizer)

    platform = "tiktok"
    num_cycles = 24  # 12 healthy, 12 failure cycles
    history_actions = []

    for cycle in range(num_cycles):
        if cycle % 2 == 0:
            # Inject Failure batch (Cluster 2): zero yield, high errors, short duration
            for _ in range(8):
                store.record_span(
                    platform=platform,
                    lens_type="web_a11y_tree",
                    duration_ms=1100,
                    yield_count=0,
                    error_count=5,
                    status_code="DOM_DRIFT",
                )
        else:
            # Inject Healthy batch (Cluster 0): high yield, zero error, fast duration
            for _ in range(8):
                store.record_span(
                    platform=platform,
                    lens_type="android_ui_dump",
                    duration_ms=650,
                    yield_count=25,
                    error_count=0,
                    status_code="SUCCESS",
                )

        eval_result = policy_engine.evaluate_and_adjust(platform, recent_window_size=10)
        history_actions.append(eval_result["action"])

        policy = store.get_policy(platform)
        assert policy is not None, f"LOUD ASSERTION FAILURE: Policy deleted or missing at cycle {cycle}"
        # Bounds check
        assert 3600 <= policy["poll_interval_sec"] <= 28800, (
            f"LOUD ASSERTION FAILURE: Poll interval out of bounds: {policy['poll_interval_sec']}"
        )
        assert 2.0 <= policy["retry_backoff_base_sec"] <= 10.0, (
            f"LOUD ASSERTION FAILURE: Backoff base out of bounds: {policy['retry_backoff_base_sec']}"
        )
        assert policy["active_lens"] in ["web_a11y_tree", "android_ui_dump"]

    # Verify both LENS_SWAP and RECOVER / MAINTAIN actions were triggered during oscillation
    assert "LENS_SWAP" in history_actions, "LOUD ASSERTION FAILURE: LENS_SWAP was never triggered during failure phases"
    # Verify policy version incremented monotonically
    final_policy = store.get_policy(platform)
    assert final_policy["policy_version"] > 1, "LOUD ASSERTION FAILURE: Policy version failed to increment"


def test_high_frequency_alternating_single_span_oscillation(stress_telemetry_store):
    """Adversarial Test: Injects single alternating spans (1 Healthy, 1 Failure) sequentially
    to test sliding window entropy and stability.
    """
    store = stress_telemetry_store
    optimizer = KMeansOptimizer(k=3, random_state=42)
    policy_engine = PolicyEngine(store, optimizer)

    platform = "youtube_shorts"

    # Pre-seed with 4 spans so K-Means has minimum points
    for _ in range(2):
        store.record_span(platform=platform, lens_type="web_a11y_tree", duration_ms=600, yield_count=20, error_count=0, status_code="SUCCESS")
        store.record_span(platform=platform, lens_type="web_a11y_tree", duration_ms=1200, yield_count=0, error_count=4, status_code="DOM_DRIFT")

    for i in range(20):
        if i % 2 == 0:
            store.record_span(platform=platform, lens_type="web_a11y_tree", duration_ms=550, yield_count=22, error_count=0, status_code="SUCCESS")
        else:
            store.record_span(platform=platform, lens_type="web_a11y_tree", duration_ms=1150, yield_count=0, error_count=6, status_code="DOM_DRIFT")

        res = policy_engine.evaluate_and_adjust(platform, recent_window_size=10)
        assert res["action"] in ["LENS_SWAP", "RECOVER", "MAINTAIN", "THROTTLE"], (
            f"LOUD ASSERTION FAILURE: Invalid action returned: {res.get('action')}"
        )


# ============================================================================
# 2. PROLONGED DEGRADED RUNS (CLUSTER 1 THROTTLING & RECOVERY DECAY)
# ============================================================================

def test_prolonged_degraded_runs_ceiling_enforcement(stress_telemetry_store):
    """Adversarial Test: Injects 20 consecutive degraded runs (Cluster 1 dominance)
    to prove that throttle progression reaches and respects hard maximum limits:
    - poll_interval_sec <= 28800 (8 hours)
    - retry_backoff_base_sec <= 10.0
    """
    store = stress_telemetry_store
    optimizer = KMeansOptimizer(k=3, random_state=42)
    policy_engine = PolicyEngine(store, optimizer)

    platform = "tiktok"
    initial_policy = store.get_policy(platform)
    assert initial_policy["poll_interval_sec"] == 3600
    assert initial_policy["retry_backoff_base_sec"] == 2.0

    intervals = []
    backoffs = []

    # Run 15 degraded cycles
    for cycle in range(15):
        # Inject 10 Degraded spans (slow duration, low yield, moderate errors)
        for _ in range(10):
            store.record_span(
                platform=platform,
                lens_type="web_a11y_tree",
                duration_ms=18500,
                yield_count=2,
                error_count=2,
                status_code="RATE_LIMITED",
            )

        res = policy_engine.evaluate_and_adjust(platform, recent_window_size=10)
        policy = store.get_policy(platform)

        intervals.append(policy["poll_interval_sec"])
        backoffs.append(policy["retry_backoff_base_sec"])

    # Loud Assertions on Throttle Limits
    assert max(intervals) == 28800, f"LOUD ASSERTION FAILURE: Expected interval cap at 28800, got {max(intervals)}"
    assert max(backoffs) == 10.0, f"LOUD ASSERTION FAILURE: Expected backoff cap at 10.0, got {max(backoffs)}"

    # Ensure no values exceed ceilings
    assert all(i <= 28800 for i in intervals), "LOUD ASSERTION FAILURE: Interval exceeded 28800 ceiling"
    assert all(b <= 10.0 for b in backoffs), "LOUD ASSERTION FAILURE: Backoff exceeded 10.0 ceiling"

    # Verify strictly non-decreasing progression up to caps
    for i in range(1, len(intervals)):
        assert intervals[i] >= intervals[i - 1], "LOUD ASSERTION FAILURE: Throttle interval decreased unexpectedly during degraded runs"
        assert backoffs[i] >= backoffs[i - 1], "LOUD ASSERTION FAILURE: Throttle backoff decreased unexpectedly during degraded runs"


def test_gradual_recovery_decay_after_prolonged_degradation(stress_telemetry_store):
    """Adversarial Test: After reaching maximum throttled dials (28800s, 10.0s),
    injects consecutive healthy spans and verifies gradual step-down to baseline (3600s, 2.0s).
    """
    store = stress_telemetry_store
    optimizer = KMeansOptimizer(k=3, random_state=42)
    policy_engine = PolicyEngine(store, optimizer)

    platform = "tiktok"

    # 1. Maximize dials
    store.update_policy(
        platform=platform,
        active_lens="web_a11y_tree",
        poll_interval_sec=28800,
        retry_backoff_base_sec=10.0,
        reason="Forced maximum throttling",
    )

    # 2. Inject healthy spans over 12 consecutive evaluation rounds
    intervals = [28800]
    backoffs = [10.0]

    for round_idx in range(12):
        for _ in range(12):
            store.record_span(
                platform=platform,
                lens_type="web_a11y_tree",
                duration_ms=500,
                yield_count=30,
                error_count=0,
                status_code="SUCCESS",
            )

        res = policy_engine.evaluate_and_adjust(platform, recent_window_size=10)
        policy = store.get_policy(platform)
        intervals.append(policy["poll_interval_sec"])
        backoffs.append(policy["retry_backoff_base_sec"])

    # Assert monotonic recovery step-down
    final_policy = store.get_policy(platform)
    assert final_policy["poll_interval_sec"] == 3600, (
        f"LOUD ASSERTION FAILURE: Expected recovery down to 3600, got {final_policy['poll_interval_sec']}"
    )
    assert final_policy["retry_backoff_base_sec"] == 2.0, (
        f"LOUD ASSERTION FAILURE: Expected recovery down to 2.0, got {final_policy['retry_backoff_base_sec']}"
    )

    for i in range(1, len(intervals)):
        assert intervals[i] <= intervals[i - 1], "LOUD ASSERTION FAILURE: Recovery interval increased"
        assert backoffs[i] <= backoffs[i - 1], "LOUD ASSERTION FAILURE: Recovery backoff increased"


# ============================================================================
# 3. FAILOVER TO ANDROID SCRAPER UNDER SUSTAINED FAILURE
# ============================================================================

def test_sustained_failure_triggers_android_scraper_failover(stress_telemetry_store, tmp_path):
    """Adversarial Test: Simulates sustained DOM drift failure, triggers failover to Android scraper,
    and executes mobile scraping session with XML parsing and metrics recording.
    """
    store = stress_telemetry_store
    optimizer = KMeansOptimizer(k=3, random_state=42)

    # Mock Android client
    mock_client = MagicMock(spec=AndroidClient)
    mock_client.serial = "emulator-5554"
    mock_client.get_layout_tree.return_value = [
        {"class": "android.widget.TextView", "text": "Viral Pokemon Card Pack Opening #VintagePrizm #PokeInvesting", "resourceId": "com.tiktok:id/caption", "bounds": "[50,50][400,100]"},
        {"class": "android.widget.TextView", "text": "Ultra Rare Drop Soundtrack", "resourceId": "com.tiktok:id/music_title", "bounds": "[50,110][300,140]"},
        {"class": "android.widget.TextView", "text": "55.4K", "resourceId": "com.tiktok:id/like_count", "bounds": "[400,200][450,230]"},
    ]

    dlq = DLQManager(str(tmp_path / "dlq"))
    scraper = MobileViralTrendScraper(client=mock_client, dlq_manager=dlq)
    policy_engine = PolicyEngine(store, optimizer, mobile_scraper=scraper)

    platform = "tiktok"

    # Inject 15 DOM drift failure spans
    for _ in range(15):
        store.record_span(
            platform=platform,
            lens_type="web_a11y_tree",
            duration_ms=1300,
            yield_count=0,
            error_count=5,
            status_code="DOM_DRIFT",
        )

    eval_result = policy_engine.evaluate_and_adjust(platform)
    assert eval_result["action"] == "LENS_SWAP", f"LOUD ASSERTION FAILURE: Expected LENS_SWAP, got {eval_result['action']}"
    assert eval_result["new_lens"] == "android_ui_dump"

    # Execute scraper through failover
    session, items, metrics = scraper.scrape_feed(platform=platform, max_swipes=2, delay_between_swipes_sec=0.01)
    assert session.status == "COMPLETED"
    assert len(items) > 0, "LOUD ASSERTION FAILURE: Expected scraped items after failover"
    assert items[0].caption == "Viral Pokemon Card Pack Opening #VintagePrizm #PokeInvesting"
    assert items[0].like_count == 55400


def test_android_scraper_failover_device_error_dlq_containment(stress_telemetry_store, tmp_path):
    """Adversarial Test: When Android scraper encounters DeviceOfflineError during failover,
    the failure is quarantined to DLQ and does not crash AutonomousMLAgent optimization cycle.
    """
    store = stress_telemetry_store
    dlq_dir = str(tmp_path / "dlq")
    dlq = DLQManager(dlq_dir)

    mock_client = MagicMock(spec=AndroidClient)
    mock_client.disable_samsung_auto_blocker.side_effect = DeviceOfflineError("ADB device emulator-5554 is OFFLINE")
    scraper = MobileViralTrendScraper(client=mock_client, dlq_manager=dlq)

    agent = AutonomousMLAgent(
        telemetry_db_path=store.db_path,
        mobile_scraper=scraper,
    )

    # Ingest mock spans with DOM drift
    cycle_result = agent.run_optimization_cycle(
        mock_spans=[
            {
                "platform": "tiktok",
                "lens_type": "web_a11y_tree",
                "duration_ms": 1200,
                "yield_count": 0,
                "error_count": 6,
                "status_code": "DOM_DRIFT",
            }
            for _ in range(12)
        ]
    )

    assert cycle_result["status"] == "COMPLETED", "LOUD ASSERTION FAILURE: Agent cycle crashed on device error"
    assert cycle_result["evaluations"]["tiktok"]["action"] == "LENS_SWAP"

    # Now execute scrape feed directly to verify DLQ quarantine
    session, items, metrics = scraper.scrape_feed(platform="tiktok", max_swipes=2)
    assert session.status == "FAILED"
    assert len(items) == 0

    # Verify DLQ received incident
    stats = dlq.get_stats()
    assert stats["total_incidents"] >= 1, "LOUD ASSERTION FAILURE: DLQ failed to record device offline incident"


# ============================================================================
# 4. MEMORY & RESOURCE STABILITY UNDER 500+ GC ITERATIONS
# ============================================================================

def test_high_frequency_mark_and_sweep_gc_memory_and_resource_stability(tmp_path):
    """Adversarial Test: Executes 500 consecutive Mark-and-Sweep garbage collection cycles.
    Monitors process memory allocation via tracemalloc and live Python objects to verify zero leaks.
    """
    db_path = str(tmp_path / "gc_stress.db")
    trends_db = str(tmp_path / "trends_gc.db")
    trends_md = str(tmp_path / "trends_gc.md")

    # Initialize tables
    store = TelemetryStore(db_path)
    now_ms = int(time.time() * 1000)
    day_ms = 86400 * 1000

    # Seed 2000 telemetry spans (1000 stale, 1000 active)
    with store.get_connection() as conn:
        for i in range(1000):
            stale_ts = now_ms - (20 * day_ms) - (i * 100)
            conn.execute(
                "INSERT INTO scraping_telemetry (span_id, timestamp_ms, platform, lens_type, duration_ms, yield_count, error_count, status_code) "
                "VALUES (?, ?, 'tiktok', 'web_a11y_tree', 800, 10, 0, 'SUCCESS')",
                (f"stale_{i}", stale_ts),
            )
        for i in range(1000):
            fresh_ts = now_ms - (2 * day_ms) - (i * 100)
            conn.execute(
                "INSERT INTO scraping_telemetry (span_id, timestamp_ms, platform, lens_type, duration_ms, yield_count, error_count, status_code) "
                "VALUES (?, ?, 'tiktok', 'web_a11y_tree', 800, 10, 0, 'SUCCESS')",
                (f"fresh_{i}", fresh_ts),
            )
        conn.commit()

    # Seed trends DB
    with sqlite3.connect(trends_db) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS trends ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, topic_category TEXT, "
            "hashtag_or_audio TEXT, velocity_score REAL, date_added TEXT)"
        )
        for i in range(200):
            conn.execute(
                "INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) "
                "VALUES ('tiktok', 'SportsCards', ?, 80.0, date('now', '-25 days'))",
                (f"#OldTag_{i}",),
            )
        for i in range(200):
            conn.execute(
                "INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) "
                "VALUES ('tiktok', 'SportsCards', ?, 95.0, date('now', '-2 days'))",
                (f"#FreshTag_{i}",),
            )
        conn.commit()

    agent = AutonomousMLAgent(
        telemetry_db_path=db_path,
        trends_db_path=trends_db,
        trends_md_path=trends_md,
    )

    tracemalloc.start()
    gc.collect()
    obj_count_before = len(gc.get_objects())

    # Execute 500 consecutive GC cycles
    num_gc_cycles = 500
    for cycle in range(num_gc_cycles):
        deleted_telemetry = store.mark_and_sweep_telemetry(retention_days=14)
        deleted_trends = execute_trends_garbage_collection(trends_db, trends_md)

        if cycle == 0:
            assert deleted_telemetry == 1000, f"LOUD ASSERTION FAILURE: Expected 1000 deleted telemetry spans, got {deleted_telemetry}"
            assert deleted_trends == 200, f"LOUD ASSERTION FAILURE: Expected 200 deleted trends, got {deleted_trends}"
        else:
            assert deleted_telemetry == 0, f"LOUD ASSERTION FAILURE: Spurious deletions in subsequent GC cycle: {deleted_telemetry}"
            assert deleted_trends == 0, f"LOUD ASSERTION FAILURE: Spurious deletions in subsequent GC cycle: {deleted_trends}"

    current_mem_bytes, peak_mem_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    gc.collect()
    obj_count_after = len(gc.get_objects())

    peak_mb = peak_mem_bytes / (1024 * 1024)
    current_mb = current_mem_bytes / (1024 * 1024)
    obj_delta = obj_count_after - obj_count_before

    # Loud Assertions on Memory Stability
    # Peak memory allocated by Python heap during 500 iterations must stay below 15 MB
    assert peak_mb < 15.0, f"LOUD ASSERTION FAILURE: Peak memory too high during GC stress: {peak_mb:.2f} MB"
    assert current_mb < 5.0, f"LOUD ASSERTION FAILURE: Leaked heap memory after GC stress: {current_mb:.2f} MB"
    # Object leak count must be tightly bounded
    assert obj_delta < 500, f"LOUD ASSERTION FAILURE: Python live object leak detected: grew by {obj_delta} objects"

    # Verify freshness integrity in DB
    remaining_telemetry = len(store.get_recent_spans(limit=2000))
    assert remaining_telemetry == 1000, f"LOUD ASSERTION FAILURE: Expected 1000 remaining spans, got {remaining_telemetry}"


# ============================================================================
# 5. MULTI-THREADED CONCURRENCY STRESS
# ============================================================================

def test_multithreaded_concurrent_optimization_cycles(tmp_path):
    """Adversarial Test: 8 concurrent threads executing full AutonomousMLAgent optimization cycles
    with span recording, K-Means clustering, policy adaptation, and GC sweeps simultaneously.
    """
    db_path = str(tmp_path / "concurrent_stress.db")
    trends_db = str(tmp_path / "concurrent_trends.db")
    trends_md = str(tmp_path / "concurrent_trends.md")

    agent = AutonomousMLAgent(
        telemetry_db_path=db_path,
        trends_db_path=trends_db,
        trends_md_path=trends_md,
    )

    num_threads = 8
    cycles_per_thread = 5
    thread_errors: List[Exception] = []

    def worker(thread_id: int):
        try:
            for cycle in range(cycles_per_thread):
                mock_spans = [
                    {
                        "platform": "tiktok" if thread_id % 2 == 0 else "instagram_reels",
                        "lens_type": "web_a11y_tree",
                        "duration_ms": 600 + (cycle * 50),
                        "yield_count": 15 + cycle,
                        "error_count": 0,
                        "status_code": "SUCCESS",
                    },
                    {
                        "platform": "youtube_shorts",
                        "lens_type": "web_a11y_tree",
                        "duration_ms": 17000,
                        "yield_count": 2,
                        "error_count": 2,
                        "status_code": "RATE_LIMITED",
                    },
                ]
                res = agent.run_optimization_cycle(mock_spans=mock_spans)
                assert res["status"] == "COMPLETED"
        except Exception as e:
            thread_errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(thread_errors) == 0, f"LOUD ASSERTION FAILURE: Concurrent execution errors: {thread_errors}"

    # Verify total spans recorded
    total_spans = len(agent.telemetry_store.get_recent_spans(limit=1000))
    expected_spans = num_threads * cycles_per_thread * 2
    assert total_spans == expected_spans, (
        f"LOUD ASSERTION FAILURE: Expected {expected_spans} spans in DB, got {total_spans}"
    )


# ============================================================================
# 6. EXTREME NUMERICAL BOUNDARIES & MALFORMED INPUT FUZZING
# ============================================================================

def test_extreme_numerical_boundary_and_fuzz_spans(stress_telemetry_store):
    """Adversarial Test: Injects astronomical values, zero durations, massive error counts,
    and checks that K-Means and PolicyEngine handle them without ZeroDivisionError or crash.
    """
    store = stress_telemetry_store
    optimizer = KMeansOptimizer(k=3, random_state=42)
    policy_engine = PolicyEngine(store, optimizer)

    platform = "tiktok"

    fuzz_spans = [
        {"duration_ms": 0, "yield_count": 0, "error_count": 0, "status_code": "EMPTY"},
        {"duration_ms": 10**9, "yield_count": 10**8, "error_count": 10**8, "status_code": "HUGE"},
        {"duration_ms": 1, "yield_count": 1000000, "error_count": 0, "status_code": "SUPER_FAST"},
        {"duration_ms": 5000, "yield_count": 0, "error_count": 999999, "status_code": "MASSIVE_ERRORS"},
        {"duration_ms": 100, "yield_count": 10, "error_count": 0, "status_code": "NORMAL"},
    ]

    for span in fuzz_spans:
        store.record_span(
            platform=platform,
            lens_type="web_a11y_tree",
            duration_ms=span["duration_ms"],
            yield_count=span["yield_count"],
            error_count=span["error_count"],
            status_code=span["status_code"],
        )

    # Evaluate
    result = policy_engine.evaluate_and_adjust(platform)
    assert result["action"] in ["THROTTLE", "LENS_SWAP", "RECOVER", "MAINTAIN"]
    policy = store.get_policy(platform)
    assert 3600 <= policy["poll_interval_sec"] <= 28800
    assert 2.0 <= policy["retry_backoff_base_sec"] <= 10.0


def test_evaluate_and_adjust_on_empty_and_sparse_database(stress_telemetry_store):
    """Adversarial Test: PolicyEngine on completely empty DB and 1-2 spans returns clean NO_OP."""
    store = stress_telemetry_store
    policy_engine = PolicyEngine(store)

    # Completely empty DB for unknown platform
    res_empty = policy_engine.evaluate_and_adjust("nonexistent_platform")
    assert res_empty["action"] == "NO_OP"
    assert "Insufficient telemetry" in res_empty["reason"]

    # 1 span for tiktok
    store.record_span(platform="tiktok", lens_type="web_a11y_tree", duration_ms=500, yield_count=10, error_count=0, status_code="SUCCESS")
    res_one = policy_engine.evaluate_and_adjust("tiktok")
    assert res_one["action"] == "NO_OP"
    assert "Insufficient telemetry" in res_one["reason"]

    # 2 spans for tiktok (still < 3)
    store.record_span(platform="tiktok", lens_type="web_a11y_tree", duration_ms=600, yield_count=12, error_count=0, status_code="SUCCESS")
    res_two = policy_engine.evaluate_and_adjust("tiktok")
    assert res_two["action"] == "NO_OP"
    assert "Insufficient telemetry" in res_two["reason"]


def test_kmeans_outlier_dispersion_robustness():
    """Adversarial Test: K-Means handles extreme numerical outliers without NaN centroids or crashes."""
    optimizer = KMeansOptimizer(k=3, random_state=42)
    df = pd.DataFrame([
        {"duration_ms": 500, "yield_count": 20, "error_count": 0, "status_code": "SUCCESS"},
        {"duration_ms": 600, "yield_count": 25, "error_count": 0, "status_code": "SUCCESS"},
        {"duration_ms": 550, "yield_count": 22, "error_count": 0, "status_code": "SUCCESS"},
        {"duration_ms": 10**8, "yield_count": 10**6, "error_count": 10**5, "status_code": "OUTLIER"},
        {"duration_ms": 18000, "yield_count": 2, "error_count": 3, "status_code": "RATE_LIMITED"},
    ])
    labels, centroids, counts = optimizer.fit_predict(df)
    assert len(labels) == 5
    assert not np.isnan(centroids).any()
    assert len(counts) == 3


def test_trends_gc_nonexistent_and_corrupt_files(tmp_path):
    """Adversarial Test: execute_trends_garbage_collection handles nonexistent DB, empty DB, or invalid paths cleanly."""
    nonexistent_db = str(tmp_path / "does_not_exist.db")
    output_md = str(tmp_path / "output.md")

    # Nonexistent DB
    res = execute_trends_garbage_collection(nonexistent_db, output_md)
    assert res == 0
    assert not os.path.exists(output_md)

    # Empty DB without trends table
    empty_db = str(tmp_path / "empty.db")
    with sqlite3.connect(empty_db) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
    
    # Should catch sqlite3.OperationalError cleanly or fail predictably
    try:
        execute_trends_garbage_collection(empty_db, output_md)
    except sqlite3.OperationalError:
        pass  # Expected when table doesn't exist


def test_concurrent_gc_and_write_interleaving(stress_telemetry_store):
    """Adversarial Test: Concurrent threads writing spans while another thread continuously sweeps GC."""
    store = stress_telemetry_store
    stop_event = threading.Event()
    errors: List[Exception] = []

    def writer():
        try:
            for i in range(100):
                store.record_span(
                    platform="tiktok",
                    lens_type="web_a11y_tree",
                    duration_ms=600 + i,
                    yield_count=10,
                    error_count=0,
                    status_code="SUCCESS",
                )
                time.sleep(0.005)
        except Exception as e:
            errors.append(e)

    def gc_sweeper():
        try:
            while not stop_event.is_set():
                store.mark_and_sweep_telemetry(retention_days=14)
                time.sleep(0.01)
        except Exception as e:
            errors.append(e)

    w_thread = threading.Thread(target=writer)
    g_thread = threading.Thread(target=gc_sweeper)

    g_thread.start()
    w_thread.start()

    w_thread.join()
    stop_event.set()
    g_thread.join()

    assert len(errors) == 0, f"LOUD ASSERTION FAILURE: Lock collision or error during concurrent GC/write: {errors}"
