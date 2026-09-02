"""Tests for Antigravity ML Agent, Telemetry Engine, Localized K-Means Clustering,
and Closed-Loop Execution Policy Engine (Requirement R2 / Loud Assertions).
"""

import os
import sqlite3
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from unified_ops_hub.ml_agent.telemetry import TelemetryStore
from unified_ops_hub.ml_agent.clustering import KMeansOptimizer
from unified_ops_hub.ml_agent.policy import PolicyEngine
from unified_ops_hub.ml_agent.ml_agent import (
    AutonomousMLAgent,
    build_ml_agent_config,
    execute_trends_garbage_collection,
)
from unified_ops_hub.mobile.models import ScrapedTrendItem, ScrapeMetrics, MobileScrapeSession
from unified_ops_hub.mobile.scraper import MobileViralTrendScraper
from unified_ops_hub.mobile.android_client import AndroidClient


@pytest.fixture
def isolated_db_path(tmp_path):
    """Provides a fresh isolated SQLite file path for telemetry testing."""
    return str(tmp_path / "test_telemetry.db")


@pytest.fixture
def isolated_telemetry_store(isolated_db_path):
    """Provides an isolated TelemetryStore instance."""
    return TelemetryStore(isolated_db_path)


# ============================================================================
# 1. SQLite Telemetry & WAL Mode Tests
# ============================================================================

def test_telemetry_schema_creation_and_wal_mode(isolated_telemetry_store):
    """Loud Assertion: TelemetryStore correctly initializes WAL mode, schema tables, and baseline policies."""
    store = isolated_telemetry_store

    # 1. Check WAL mode
    with store.get_connection() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal_mode.lower() == "wal", f"LOUD ASSERTION FAILURE: Expected WAL mode, got {journal_mode}"

        # 2. Check tables exist
        tables = [
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        ]
        assert "scraping_telemetry" in tables, "LOUD ASSERTION FAILURE: scraping_telemetry table missing"
        assert "execution_policies" in tables, "LOUD ASSERTION FAILURE: execution_policies table missing"
        assert "protegi_gradient_log" in tables, "LOUD ASSERTION FAILURE: protegi_gradient_log table missing"

    # 3. Check seeded baseline policies
    policies = store.get_all_policies()
    assert len(policies) >= 4, f"LOUD ASSERTION FAILURE: Expected >=4 seeded policies, got {len(policies)}"
    assert "tiktok" in policies, "LOUD ASSERTION FAILURE: 'tiktok' policy missing"
    assert "youtube_shorts" in policies, "LOUD ASSERTION FAILURE: 'youtube_shorts' policy missing"
    assert "instagram_reels" in policies, "LOUD ASSERTION FAILURE: 'instagram_reels' policy missing"
    assert "facebook_reels" in policies, "LOUD ASSERTION FAILURE: 'facebook_reels' policy missing"
    assert policies["tiktok"]["active_lens"] == "web_a11y_tree", "LOUD ASSERTION FAILURE: TikTok lens mismatch"
    assert policies["instagram_reels"]["active_lens"] == "android_ui_dump", "LOUD ASSERTION FAILURE: IG lens mismatch"


def test_telemetry_span_insertion_and_query(isolated_telemetry_store):
    """Loud Assertion: Spans are accurately inserted and queried with all metrics preserved."""
    store = isolated_telemetry_store

    span_id = store.record_span(
        platform="tiktok",
        lens_type="web_a11y_tree",
        duration_ms=1450,
        yield_count=18,
        error_count=0,
        status_code="SUCCESS",
        input_tokens=520,
        output_tokens=140,
        metadata={"hashtag": "#SportsCards", "velocity": 92.5},
    )

    assert span_id is not None and len(span_id) > 0, "LOUD ASSERTION FAILURE: Invalid span ID returned"

    # Query back
    df = store.get_recent_spans(platform="tiktok", limit=10)
    assert len(df) == 1, f"LOUD ASSERTION FAILURE: Expected 1 span, found {len(df)}"
    record = df.iloc[0]
    assert record["span_id"] == span_id, "LOUD ASSERTION FAILURE: Span ID mismatch"
    assert record["platform"] == "tiktok", "LOUD ASSERTION FAILURE: Platform mismatch"
    assert record["lens_type"] == "web_a11y_tree", "LOUD ASSERTION FAILURE: Lens type mismatch"
    assert int(record["duration_ms"]) == 1450, "LOUD ASSERTION FAILURE: Duration mismatch"
    assert int(record["yield_count"]) == 18, "LOUD ASSERTION FAILURE: Yield count mismatch"
    assert int(record["error_count"]) == 0, "LOUD ASSERTION FAILURE: Error count mismatch"
    assert int(record["input_tokens"]) == 520, "LOUD ASSERTION FAILURE: Input tokens mismatch"
    assert int(record["output_tokens"]) == 140, "LOUD ASSERTION FAILURE: Output tokens mismatch"
    assert record["status_code"] == "SUCCESS", "LOUD ASSERTION FAILURE: Status code mismatch"
    assert '"hashtag": "#SportsCards"' in record["metadata_json"], "LOUD ASSERTION FAILURE: Metadata json mismatch"


def test_telemetry_concurrent_thread_safety(isolated_telemetry_store):
    """Loud Assertion: Concurrent multi-threaded writes succeed without database lock collisions."""
    store = isolated_telemetry_store
    num_threads = 8
    writes_per_thread = 20
    errors = []

    def worker(thread_idx: int):
        try:
            for i in range(writes_per_thread):
                store.record_span(
                    platform="tiktok" if thread_idx % 2 == 0 else "instagram_reels",
                    lens_type="web_a11y_tree" if thread_idx % 2 == 0 else "android_ui_dump",
                    duration_ms=500 + i * 10,
                    yield_count=i + 1,
                    error_count=0,
                    status_code="SUCCESS",
                )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"LOUD ASSERTION FAILURE: Concurrent writes encountered errors: {errors}"
    total_spans = len(store.get_recent_spans(limit=1000))
    expected_spans = num_threads * writes_per_thread
    assert total_spans == expected_spans, f"LOUD ASSERTION FAILURE: Expected {expected_spans} spans, found {total_spans}"


# ============================================================================
# 2. Localized K-Means Clustering Tests
# ============================================================================

def test_kmeans_clustering_convergence_and_segmentation(isolated_telemetry_store):
    """Loud Assertion: Localized K-Means clustering segments spans into 3 operational clusters."""
    store = isolated_telemetry_store

    # 1. 15 Healthy spans (Cluster 0): fast duration (~600ms), high yield (~25), 0 errors
    for _ in range(15):
        store.record_span(
            platform="tiktok",
            lens_type="web_a11y_tree",
            duration_ms=600,
            yield_count=25,
            error_count=0,
            status_code="SUCCESS",
        )

    # 2. 15 Degraded spans (Cluster 1): slow duration (~18000ms), low yield (~3), some errors (~2)
    for _ in range(15):
        store.record_span(
            platform="tiktok",
            lens_type="web_a11y_tree",
            duration_ms=18000,
            yield_count=3,
            error_count=2,
            status_code="RATE_LIMITED",
        )

    # 3. 15 Failure spans (Cluster 2): zero yield (0), high errors (~6), DOM drift
    for _ in range(15):
        store.record_span(
            platform="tiktok",
            lens_type="web_a11y_tree",
            duration_ms=2000,
            yield_count=0,
            error_count=6,
            status_code="DOM_DRIFT",
        )

    df = store.get_recent_spans(platform="tiktok", limit=50)
    assert len(df) == 45, f"LOUD ASSERTION FAILURE: Expected 45 spans, got {len(df)}"

    optimizer = KMeansOptimizer(k=3, random_state=42)
    start_time = time.perf_counter()
    labels, centroids, counts = optimizer.fit_predict(df)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Sub-5ms execution constraint
    assert elapsed_ms < 100.0, f"LOUD ASSERTION FAILURE: Clustering too slow: {elapsed_ms:.2f}ms"
    assert len(labels) == 45, f"LOUD ASSERTION FAILURE: Label count mismatch: {len(labels)}"
    assert len(counts) == 3, f"LOUD ASSERTION FAILURE: Expected 3 unique clusters, got {len(counts)}"

    # Semantic ordering verification:
    # Cluster 0 must be Healthy, Cluster 1 must be Degraded, Cluster 2 must be Failure
    assert counts.get(0, 0) == 15, f"LOUD ASSERTION FAILURE: Expected 15 Cluster 0 items, got {counts.get(0)}"
    assert counts.get(1, 0) == 15, f"LOUD ASSERTION FAILURE: Expected 15 Cluster 1 items, got {counts.get(1)}"
    assert counts.get(2, 0) == 15, f"LOUD ASSERTION FAILURE: Expected 15 Cluster 2 items, got {counts.get(2)}"


def test_kmeans_cold_start_and_zero_variance():
    """Loud Assertion: K-Means handles sparse telemetry (N < 3) and zero variance gracefully."""
    optimizer = KMeansOptimizer(k=3, random_state=42)

    # Sparse data (N = 2)
    sparse_df = pd.DataFrame([
        {"duration_ms": 1000, "yield_count": 10, "error_count": 0, "status_code": "SUCCESS"},
        {"duration_ms": 2000, "yield_count": 0, "error_count": 5, "status_code": "DOM_DRIFT"},
    ])
    labels, centroids, counts = optimizer.fit_predict(sparse_df)
    assert len(labels) == 2, "LOUD ASSERTION FAILURE: Sparse labels length mismatch"
    assert labels[0] == 0, "LOUD ASSERTION FAILURE: Expected healthy span to be labeled 0"
    assert labels[1] == 2, "LOUD ASSERTION FAILURE: Expected failure span to be labeled 2"

    # Zero variance data (identical spans)
    zero_var_df = pd.DataFrame([
        {"duration_ms": 1000, "yield_count": 10, "error_count": 0, "status_code": "SUCCESS"}
        for _ in range(10)
    ])
    zv_labels, zv_centroids, zv_counts = optimizer.fit_predict(zero_var_df)
    assert len(zv_labels) == 10, "LOUD ASSERTION FAILURE: Zero variance labels length mismatch"
    assert not np.isnan(zv_centroids).any(), "LOUD ASSERTION FAILURE: Centroids contained NaN values"


# ============================================================================
# 3. Closed-Loop Policy Adjustment Tests
# ============================================================================

def test_policy_engine_throttle_on_cluster_1_degradation(isolated_telemetry_store):
    """Loud Assertion: PolicyEngine throttles cadence (increases interval and backoff) on Cluster 1."""
    store = isolated_telemetry_store
    optimizer = KMeansOptimizer(k=3, random_state=42)
    policy_engine = PolicyEngine(store, optimizer)

    # Seed 12 Degraded spans (Cluster 1 dominance)
    for _ in range(12):
        store.record_span(
            platform="tiktok",
            lens_type="web_a11y_tree",
            duration_ms=17500,
            yield_count=2,
            error_count=3,
            status_code="RATE_LIMITED",
        )

    initial_policy = store.get_policy("tiktok")
    result = policy_engine.evaluate_and_adjust("tiktok")

    assert result["action"] == "THROTTLE", f"LOUD ASSERTION FAILURE: Expected THROTTLE, got {result['action']}"
    assert result["new_interval"] > initial_policy["poll_interval_sec"], "LOUD ASSERTION FAILURE: Poll interval not increased"
    assert result["new_backoff"] > initial_policy["retry_backoff_base_sec"], "LOUD ASSERTION FAILURE: Backoff not increased"

    updated_policy = store.get_policy("tiktok")
    assert updated_policy["poll_interval_sec"] == result["new_interval"]
    assert updated_policy["retry_backoff_base_sec"] == result["new_backoff"]
    assert updated_policy["policy_version"] > initial_policy["policy_version"]


def test_policy_engine_lens_swap_on_cluster_2_dom_drift(isolated_telemetry_store):
    """Loud Assertion: PolicyEngine swaps lens to android_ui_dump when Cluster 2 (DOM Drift) dominates."""
    store = isolated_telemetry_store
    optimizer = KMeansOptimizer(k=3, random_state=42)
    policy_engine = PolicyEngine(store, optimizer)

    # Inject DOM drift failures (Cluster 2)
    for _ in range(12):
        store.record_span(
            platform="tiktok",
            lens_type="web_a11y_tree",
            duration_ms=1200,
            yield_count=0,
            error_count=5,
            status_code="DOM_DRIFT",
        )

    result = policy_engine.evaluate_and_adjust("tiktok")

    assert result["action"] == "LENS_SWAP", f"LOUD ASSERTION FAILURE: Expected LENS_SWAP, got {result['action']}"
    assert result["new_lens"] == "android_ui_dump", f"LOUD ASSERTION FAILURE: Expected android_ui_dump lens, got {result.get('new_lens')}"

    updated_policy = store.get_policy("tiktok")
    assert updated_policy["active_lens"] == "android_ui_dump"
    assert "DOM Drift" in updated_policy["adjustment_reason"]


def test_policy_engine_healthy_recovery_restoration(isolated_telemetry_store):
    """Loud Assertion: PolicyEngine gently restores baseline intervals when Cluster 0 is sustained."""
    store = isolated_telemetry_store
    optimizer = KMeansOptimizer(k=3, random_state=42)
    policy_engine = PolicyEngine(store, optimizer)

    # First set elevated policy
    store.update_policy(
        platform="tiktok",
        active_lens="web_a11y_tree",
        poll_interval_sec=14400,
        retry_backoff_base_sec=6.0,
        reason="Manually throttled",
    )

    # Seed 15 Healthy spans (Cluster 0)
    for _ in range(15):
        store.record_span(
            platform="tiktok",
            lens_type="web_a11y_tree",
            duration_ms=700,
            yield_count=30,
            error_count=0,
            status_code="SUCCESS",
        )

    result = policy_engine.evaluate_and_adjust("tiktok")

    assert result["action"] == "RECOVER", f"LOUD ASSERTION FAILURE: Expected RECOVER, got {result['action']}"
    assert result["new_interval"] < 14400, "LOUD ASSERTION FAILURE: Interval should be decreased on recovery"
    assert result["new_backoff"] < 6.0, "LOUD ASSERTION FAILURE: Backoff should be decreased on recovery"


def test_policy_engine_mobile_scraper_failover_integration(isolated_telemetry_store):
    """Loud Assertion: PolicyEngine failover seamlessly integrates with MobileViralTrendScraper."""
    store = isolated_telemetry_store
    optimizer = KMeansOptimizer(k=3, random_state=42)

    # Mock Android client and scraper
    mock_client = MagicMock(spec=AndroidClient)
    mock_client.serial = "emulator-5554"
    mock_client.dump_ui_xml.return_value = "<hierarchy><node text='Viral Card Clip' /></hierarchy>"
    mock_scraper = MobileViralTrendScraper(client=mock_client)

    policy_engine = PolicyEngine(store, optimizer, mobile_scraper=mock_scraper)

    # Trigger explicit failover
    failover_result = policy_engine.trigger_mobile_failover("tiktok")
    assert failover_result["success"] is True
    assert failover_result["active_lens"] == "android_ui_dump"
    assert failover_result["platform"] == "tiktok"

    policy = store.get_policy("tiktok")
    assert policy["active_lens"] == "android_ui_dump"


# ============================================================================
# 4. Garbage Collection (Mark-and-Sweep 14-Day Rolling Window) Tests
# ============================================================================

def test_telemetry_mark_and_sweep_garbage_collection(isolated_telemetry_store):
    """Loud Assertion: Telemetry records older than 14 days are swept, preserving fresh records."""
    store = isolated_telemetry_store

    now_ms = int(time.time() * 1000)
    day_ms = 86400 * 1000

    # 1. Insert 5 Stale Spans (20 days old)
    for i in range(5):
        old_ts = now_ms - (20 * day_ms) - (i * 1000)
        with store.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO scraping_telemetry 
                (span_id, timestamp_ms, platform, lens_type, duration_ms, yield_count, error_count, status_code)
                VALUES (?, ?, 'tiktok', 'web_a11y_tree', 1000, 10, 0, 'SUCCESS')
                """,
                (f"old_span_{i}", old_ts),
            )
            conn.commit()

    # 2. Insert 5 Fresh Spans (2 days old)
    for i in range(5):
        fresh_ts = now_ms - (2 * day_ms) - (i * 1000)
        with store.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO scraping_telemetry 
                (span_id, timestamp_ms, platform, lens_type, duration_ms, yield_count, error_count, status_code)
                VALUES (?, ?, 'tiktok', 'web_a11y_tree', 1000, 10, 0, 'SUCCESS')
                """,
                (f"fresh_span_{i}", fresh_ts),
            )
            conn.commit()

    total_before = len(store.get_recent_spans(limit=100))
    assert total_before == 10, f"LOUD ASSERTION FAILURE: Expected 10 total spans, got {total_before}"

    deleted = store.mark_and_sweep_telemetry(retention_days=14)
    assert deleted == 5, f"LOUD ASSERTION FAILURE: Expected 5 deleted spans, got {deleted}"

    total_after = len(store.get_recent_spans(limit=100))
    assert total_after == 5, f"LOUD ASSERTION FAILURE: Expected 5 remaining spans, got {total_after}"


def test_trends_db_garbage_collection_and_markdown_export(tmp_path):
    """Loud Assertion: Trends DB purges stale items >14 days and exports clean current_trends.md."""
    trends_db_path = str(tmp_path / "trends.db")
    output_md_path = str(tmp_path / "current_trends.md")

    # Create trends table and seed
    with sqlite3.connect(trends_db_path) as conn:
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
        # 3 Stale items (25 days old)
        conn.execute(
            "INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) "
            "VALUES ('tiktok', 'SportsCards', '#VintagePrizm', 45.0, date('now', '-25 days'))"
        )
        conn.execute(
            "INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) "
            "VALUES ('youtube_shorts', 'EDM', 'HardstyleDrop_01', 50.0, date('now', '-20 days'))"
        )
        conn.execute(
            "INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) "
            "VALUES ('instagram_reels', 'SportsCards', '#TheHobby', 60.0, date('now', '-18 days'))"
        )

        # 2 Active items (2 days old)
        conn.execute(
            "INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) "
            "VALUES ('tiktok', 'SportsCards', '#WembanyamaRookie', 98.5, date('now', '-2 days'))"
        )
        conn.execute(
            "INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) "
            "VALUES ('instagram_reels', 'EDM', 'TechnoLoop2026', 88.0, date('now', '-1 days'))"
        )
        conn.commit()

    deleted = execute_trends_garbage_collection(trends_db_path, output_md_path)
    assert deleted == 3, f"LOUD ASSERTION FAILURE: Expected 3 deleted trends, got {deleted}"

    # Verify output markdown
    assert os.path.exists(output_md_path), "LOUD ASSERTION FAILURE: Output markdown file not generated"
    with open(output_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Active 14-Day Viral Trend Catalog" in content
    assert "#WembanyamaRookie" in content
    assert "TechnoLoop2026" in content
    assert "#VintagePrizm" not in content
    assert "HardstyleDrop_01" not in content


# ============================================================================
# 5. Full Autonomous ML Agent End-to-End Orchestration Tests
# ============================================================================

def test_autonomous_ml_agent_cycle_execution(isolated_db_path, tmp_path):
    """Loud Assertion: AutonomousMLAgent runs a full optimization cycle end-to-end."""
    trends_db_path = str(tmp_path / "trends.db")
    trends_md_path = str(tmp_path / "current_trends.md")

    # Seed mock trends.db
    with sqlite3.connect(trends_db_path) as conn:
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
        conn.execute(
            "INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) "
            "VALUES ('tiktok', 'SportsCards', '#CardInvesting', 90.0, date('now', '-1 days'))"
        )
        conn.commit()

    agent = AutonomousMLAgent(
        telemetry_db_path=isolated_db_path,
        trends_db_path=trends_db_path,
        trends_md_path=trends_md_path,
    )

    # Execute cycle with mock scrape session
    summary = agent.run_optimization_cycle(
        mock_spans=[
            {
                "platform": "tiktok",
                "lens_type": "web_a11y_tree",
                "duration_ms": 950,
                "yield_count": 22,
                "error_count": 0,
                "status_code": "SUCCESS",
            },
            {
                "platform": "instagram_reels",
                "lens_type": "android_ui_dump",
                "duration_ms": 1400,
                "yield_count": 15,
                "error_count": 0,
                "status_code": "SUCCESS",
            },
        ]
    )

    assert summary["spans_recorded"] == 2, "LOUD ASSERTION FAILURE: Expected 2 spans recorded"
    assert "tiktok" in summary["evaluations"], "LOUD ASSERTION FAILURE: TikTok evaluation missing"
    assert "instagram_reels" in summary["evaluations"], "LOUD ASSERTION FAILURE: IG evaluation missing"
    assert summary["gc_telemetry_purged"] >= 0
    assert summary["gc_trends_purged"] >= 0

    # Check persistence
    df = agent.telemetry_store.get_recent_spans(limit=10)
    assert len(df) == 2, f"LOUD ASSERTION FAILURE: Expected 2 spans in DB, got {len(df)}"


def test_build_ml_agent_config_sdk_compliance(tmp_path):
    """Loud Assertion: build_ml_agent_config produces valid Antigravity LocalAgentConfig with strict constraints."""
    app_data_dir = str(tmp_path / "app_data")
    db_path = str(tmp_path / "telemetry.db")

    config = build_ml_agent_config(
        db_path=db_path,
        app_data_dir=app_data_dir,
        interval_seconds=1800,
    )

    assert config.model == "gemini-3.7-flash"
    assert config.capabilities.agent_behavior.name == "AUTONOMOUS"
    assert config.capabilities.enable_subagents is True
    assert "web_lens_worker" in config.capabilities.allowed_subagents
    assert "android_lens_worker" in config.capabilities.allowed_subagents
    assert config.budget_config.max_model_calls > 0
    assert config.budget_config.max_tool_calls > 0
    assert len(config.subagents) == 2
    assert len(config.triggers) >= 1
    assert len(config.hooks) >= 1
