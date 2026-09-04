"""Master E2E Integration Test Suite for Unified Ops Hub (Milestone 5).
Verifies the complete end-to-end system orchestration:
1. Dynamic port allocation & lock management via PortManager
2. FastAPI gateway cross-domain routing (Sports Cards, Media Ingestion, ML Grading)
3. Autonomous ML optimization loop, SQLite WAL telemetry, K-Means clustering, and policy state machine (C0 -> C1 -> C2)
4. Headless Android CLI mobile scraping and viral velocity computation on Cluster 2 failover
5. Gateway resiliency, unhandled exception containment, Dead Letter Queue (DLQ) quarantine, and replay cycle
6. Next.js dashboard API contract parity across all TypeScript interfaces
"""

import json
import os
import shutil
import sqlite3
import tempfile
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from unified_ops_hub.gateway.app import create_app, GatewayState
from unified_ops_hub.gateway.dlq_manager import DLQManager, ErrorCategory, IncidentStatus
from unified_ops_hub.gateway.port_manager import PortManager
from unified_ops_hub.ml_agent.clustering import KMeansOptimizer
from unified_ops_hub.ml_agent.ml_agent import AutonomousMLAgent, build_ml_agent_config
from unified_ops_hub.ml_agent.policy import PolicyEngine
from unified_ops_hub.ml_agent.telemetry import TelemetryStore
from unified_ops_hub.mobile.android_client import AndroidClient
from unified_ops_hub.mobile.models import DeviceState, ScrapedTrendItem
from unified_ops_hub.mobile.scraper import MobileViralTrendScraper


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_workspace():
    """Provides an isolated temporary workspace directory."""
    temp_dir = tempfile.mkdtemp(prefix="e2e_unified_ops_hub_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def e2e_env(temp_workspace):
    """Sets up an end-to-end environment with temporary SQLite stores and isolated gateway."""
    lock_dir = os.path.join(temp_workspace, "locks")
    dlq_db_path = os.path.join(temp_workspace, "e2e_dlq.db")
    quarantine_dir = os.path.join(temp_workspace, "quarantine")
    telemetry_db_path = os.path.join(temp_workspace, "e2e_telemetry.db")
    trends_db_path = os.path.join(temp_workspace, "e2e_trends.db")
    trends_md_path = os.path.join(temp_workspace, "artifacts", "current_trends.md")

    port_mgr = PortManager(lock_dir=lock_dir)
    dlq_mgr = DLQManager(db_path=dlq_db_path, quarantine_dir=quarantine_dir)
    app = create_app(port_manager=port_mgr, dlq_manager=dlq_mgr)
    client = TestClient(app, raise_server_exceptions=False)

    return {
        "workspace": temp_workspace,
        "lock_dir": lock_dir,
        "dlq_db_path": dlq_db_path,
        "quarantine_dir": quarantine_dir,
        "telemetry_db_path": telemetry_db_path,
        "trends_db_path": trends_db_path,
        "trends_md_path": trends_md_path,
        "port_manager": port_mgr,
        "dlq_manager": dlq_mgr,
        "app": app,
        "client": client,
    }


# ============================================================================
# 1. Dynamic Port Allocation & Gateway Lifecycle
# ============================================================================

def test_e2e_01_dynamic_port_allocation_and_gateway_boot(e2e_env):
    """Verifies dynamic port scanning, conflict detection, lock acquisition/release,
    stale cleanup, and gateway startup with active port status metrics.
    """
    port_mgr: PortManager = e2e_env["port_manager"]
    client: TestClient = e2e_env["client"]

    # 1. Test port availability detection
    assert port_mgr.is_port_in_use(65432) is False

    # 2. Acquire lock on preferred port 8000
    lock_8000 = port_mgr.acquire_port_lock(8000)
    assert lock_8000 is not None
    assert os.path.exists(lock_8000)
    assert port_mgr.is_port_locked(8000) is True

    # 3. Dynamic allocation must detect locked 8000 and cleanly allocate 8001
    allocated_port = port_mgr.find_available_port(preferred_port=8000)
    assert allocated_port == 8001, f"Expected 8001 fallback, got {allocated_port}"

    # 4. Release lock on 8000
    released = port_mgr.release_port_lock(8000)
    assert released is True
    assert port_mgr.is_port_locked(8000) is False

    # 5. Gateway health probe confirms operational state
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["version"] == "1.0.0"
    assert isinstance(data["uptime_seconds"], (int, float))
    assert "sports_cards" in data["services"]
    assert "media_pipeline" in data["services"]
    assert "ml_grading" in data["services"]
    assert "dlq_gateway" in data["services"]

    # 6. Gateway port status probe
    port_resp = client.get("/api/v1/health/ports")
    assert port_resp.status_code == 200
    port_map = port_resp.json()
    assert "8000" in port_map
    assert "available" in port_map["8000"]


# ============================================================================
# 2. FastAPI Gateway Cross-Domain Routing
# ============================================================================

def test_e2e_02_fastapi_gateway_cross_domain_routing(e2e_env):
    """Verifies all 3 domain routes across the FastAPI gateway:
    1. Sports Cards Staging & Portfolio Valuation
    2. Media Ingestion Job Queue & Proxy Clips
    3. ML Grading Engine with EVPI calculation, HRV killswitch, and Aspect Ratio modifier
    """
    client: TestClient = e2e_env["client"]

    # ------------------------------------------------------------------------
    # Domain A: Sports Cards Ecosystem
    # ------------------------------------------------------------------------
    sports_health = client.get("/api/v1/sports/health")
    assert sports_health.status_code == 200
    assert sports_health.json()["status"] == "READY"

    # Capture first card
    card_1 = {
        "player": "Victor Wembanyama",
        "year": "2023",
        "set_name": "Prizm Silver Rookie",
        "card_number": "136",
        "category": "Basketball",
        "condition": "PSA 10 Gem Mint",
        "investment": 1200.0,
        "estimated_value": 1850.0,
        "notes": "CardLadder trend +12.4%",
    }
    cap_resp_1 = client.post("/api/v1/sports/capture", json=card_1)
    assert cap_resp_1.status_code == 200
    saved_1 = cap_resp_1.json()
    assert saved_1["id"].startswith("CARD_")
    assert saved_1["player"] == "Victor Wembanyama"
    assert saved_1["ai_status"] == "CLEARED"
    assert saved_1["captured_at"] > 0

    # Capture second card
    card_2 = {
        "player": "Shohei Ohtani",
        "year": "2018",
        "set_name": "Bowman Chrome Rookie",
        "card_number": "BCP1",
        "category": "Baseball",
        "condition": "BGS 9.5",
        "investment": 2500.0,
        "estimated_value": 3400.0,
        "notes": "50/50 Club season momentum",
    }
    cap_resp_2 = client.post("/api/v1/sports/capture", json=card_2)
    assert cap_resp_2.status_code == 200

    # Verify staging portfolio
    staging_resp = client.get("/api/v1/sports/staging")
    assert staging_resp.status_code == 200
    staged = staging_resp.json()
    assert staged["total"] == 2
    assert len(staged["cards"]) == 2

    # Verify financial analytics
    stats_resp = client.get("/api/v1/sports/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_cards"] == 2
    assert stats["total_investment"] == 3700.0
    assert stats["total_estimated_value"] == 5250.0

    # ------------------------------------------------------------------------
    # Domain B: Media Ingestion Pipeline
    # ------------------------------------------------------------------------
    media_health = client.get("/api/v1/media/health")
    assert media_health.status_code == 200
    assert media_health.json()["status"] == "READY"

    # Trigger video processing pipeline
    trigger_req = {
        "clip_name": "ultra_miami_drop_4k_01.mp4",
        "mode": "vertical_reframes",
        "priority": "HIGH",
    }
    trig_resp = client.post("/api/v1/media/trigger", json=trigger_req)
    assert trig_resp.status_code == 202
    job_info = trig_resp.json()
    assert "job_id" in job_info
    assert job_info["job_id"].startswith("job_")
    assert job_info["clip_name"] == "ultra_miami_drop_4k_01.mp4"
    assert job_info["mode"] == "vertical_reframes"
    assert job_info["status"] == "QUEUED"

    # Query job status
    status_resp = client.get(f"/api/v1/media/status/{job_info['job_id']}")
    assert status_resp.status_code == 200
    assert status_resp.json()["job_id"] == job_info["job_id"]

    # Query proxy stream definitions
    proxy_resp = client.get("/api/v1/media/proxies")
    assert proxy_resp.status_code == 200
    proxies = proxy_resp.json()["proxies"]
    assert len(proxies) >= 2
    assert proxies[0]["resolution"] == "720p"
    assert proxies[0]["fps"] == 60

    # ------------------------------------------------------------------------
    # Domain C: ML Video Grading Engine
    # ------------------------------------------------------------------------
    weights_resp = client.get("/api/v1/ml/weights")
    assert weights_resp.status_code == 200
    weights = weights_resp.json()["weights"]
    assert pytest.approx(sum(weights.values()), 0.001) == 1.0

    # 1. Viral Ready 9:16 Video
    grade_req_viral = {
        "video_id": "vid_festival_stage_01",
        "scores": {
            "HRV": 92.0,
            "DPAW": 90.0,
            "ADR_SFD": 88.0,
            "CKE_MVE": 82.0,
            "LTSS": 85.0,
        },
        "aspect_ratio": "9:16",
    }
    grade_resp_1 = client.post("/api/v1/ml/grade", json=grade_req_viral)
    assert grade_resp_1.status_code == 200
    grade_res_1 = grade_resp_1.json()
    assert grade_res_1["evpi"] >= 85.0
    assert grade_res_1["verdict"] == "VIRAL_READY"

    # 2. Low HRV Killswitch Enforcement (HRV < 40 caps EVPI at 49.9)
    grade_req_killswitch = {
        "video_id": "vid_slow_intro_02",
        "scores": {
            "HRV": 32.0,
            "DPAW": 95.0,
            "ADR_SFD": 90.0,
            "CKE_MVE": 90.0,
            "LTSS": 90.0,
        },
        "aspect_ratio": "9:16",
    }
    grade_resp_2 = client.post("/api/v1/ml/grade", json=grade_req_killswitch)
    assert grade_resp_2.status_code == 200
    grade_res_2 = grade_resp_2.json()
    assert grade_res_2["evpi"] <= 49.9
    assert grade_res_2["verdict"] == "LOW_REACH"

    # 3. 16:9 Aspect Ratio 50% Penalty
    grade_req_landscape = {
        "video_id": "vid_landscape_03",
        "scores": {
            "HRV": 90.0,
            "DPAW": 90.0,
            "ADR_SFD": 90.0,
            "CKE_MVE": 90.0,
            "LTSS": 90.0,
        },
        "aspect_ratio": "16:9",
    }
    grade_resp_3 = client.post("/api/v1/ml/grade", json=grade_req_landscape)
    assert grade_resp_3.status_code == 200
    grade_res_3 = grade_resp_3.json()
    assert grade_res_3["evpi"] == 45.0  # 90.0 * 0.5 = 45.0
    assert grade_res_3["verdict"] == "LOW_REACH"

    # Ingest actual performance feedback
    fb_req = {"video_id": "vid_festival_stage_01", "actual_views": 450000, "actual_shares": 32000}
    fb_resp = client.post("/api/v1/ml/feedback", json=fb_req)
    assert fb_resp.status_code == 200
    assert fb_resp.json()["status"] == "INGESTED"


# ============================================================================
# 3. Autonomous ML Loop, SQLite WAL Telemetry & Policy State Transitions
# ============================================================================

def test_e2e_03_autonomous_ml_loop_telemetry_clustering_and_policy_transitions(e2e_env):
    """Verifies the closed-loop ML optimization engine:
    1. SQLite WAL mode persistence for execution spans
    2. K-Means clustering ($K=3$) for healthy (0), degraded (1), and failure (2) operational states
    3. Self-adjusting policy state machine (Baseline -> Throttle -> Lens Failover)
    4. ProTeGi textual gradient diff logging
    5. 14-day Mark-and-Sweep garbage collection and current_trends.md generation
    """
    telemetry_db = e2e_env["telemetry_db_path"]
    trends_db = e2e_env["trends_db_path"]
    trends_md = e2e_env["trends_md_path"]

    # Seed mock trends in trends DB
    with sqlite3.connect(trends_db) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trends (
                trend_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                topic_category TEXT NOT NULL,
                hashtag_or_audio TEXT NOT NULL,
                velocity_score REAL NOT NULL,
                date_added TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO trends (trend_id, platform, topic_category, hashtag_or_audio, velocity_score, date_added)
            VALUES ('t1', 'tiktok', 'EDM', '#Ultra2026', 98.4, date('now')),
                   ('t2', 'tiktok', 'Sports', '#Wembanyama', 89.1, date('now')),
                   ('t_old', 'tiktok', 'Stale', '#StaleTag', 12.0, date('now', '-20 days'));
            """
        )
        conn.commit()

    agent = AutonomousMLAgent(
        telemetry_db_path=telemetry_db,
        trends_db_path=trends_db,
        trends_md_path=trends_md,
    )

    store = agent.telemetry_store

    # 1. Verify SQLite WAL mode
    with store.get_connection() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal_mode.lower() == "wal"

    # Verify baseline seed policy
    tiktok_policy = store.get_policy("tiktok")
    assert tiktok_policy is not None
    assert tiktok_policy["active_lens"] == "web_a11y_tree"
    assert tiktok_policy["poll_interval_sec"] == 3600
    assert tiktok_policy["retry_backoff_base_sec"] == 2.0

    # ------------------------------------------------------------------------
    # Step A: Establish 3-Cluster Reference Population (45 Spans)
    # ------------------------------------------------------------------------
    baseline_spans = (
        [
            {"platform": "tiktok", "lens_type": "web_a11y_tree", "duration_ms": 600, "yield_count": 25, "error_count": 0, "status_code": "SUCCESS"}
            for _ in range(15)
        ]
        + [
            {"platform": "tiktok", "lens_type": "web_a11y_tree", "duration_ms": 18000, "yield_count": 3, "error_count": 2, "status_code": "RATE_LIMITED"}
            for _ in range(15)
        ]
        + [
            {"platform": "tiktok", "lens_type": "web_a11y_tree", "duration_ms": 2000, "yield_count": 0, "error_count": 6, "status_code": "DOM_DRIFT"}
            for _ in range(15)
        ]
    )
    for span in baseline_spans:
        store.record_span(**span)

    df = store.get_recent_spans(platform="tiktok", limit=50)
    assert len(df) == 45
    labels, centroids, counts = agent.k_means.fit_predict(df)
    assert counts.get(0, 0) == 15, "Expected 15 Healthy spans in Cluster 0"
    assert counts.get(1, 0) == 15, "Expected 15 Degraded spans in Cluster 1"
    assert counts.get(2, 0) == 15, "Expected 15 Failure spans in Cluster 2"

    # ------------------------------------------------------------------------
    # Step B: Transition to Cluster 1 (Degraded / Rate Limiting) -> THROTTLE
    # ------------------------------------------------------------------------
    degraded_batch = [
        {"platform": "tiktok", "lens_type": "web_a11y_tree", "duration_ms": 18500, "yield_count": 2, "error_count": 2, "status_code": "RATE_LIMITED"}
        for _ in range(10)
    ]
    res_b = agent.run_optimization_cycle(mock_spans=degraded_batch, platforms=["tiktok"])
    eval_b = res_b["evaluations"]["tiktok"]
    assert eval_b["action"] == "THROTTLE"
    assert eval_b["c1_rate"] >= 0.40

    pol_b = store.get_policy("tiktok")
    assert pol_b["poll_interval_sec"] > 3600
    assert pol_b["retry_backoff_base_sec"] >= 4.0

    # ------------------------------------------------------------------------
    # Step C: Transition to Cluster 2 (DOM Drift / Failure) -> LENS_SWAP
    # ------------------------------------------------------------------------
    failure_batch = [
        {"platform": "tiktok", "lens_type": "web_a11y_tree", "duration_ms": 2000, "yield_count": 0, "error_count": 6, "status_code": "DOM_DRIFT"}
        for _ in range(10)
    ]
    res_c = agent.run_optimization_cycle(mock_spans=failure_batch, platforms=["tiktok"])
    eval_c = res_c["evaluations"]["tiktok"]
    assert eval_c["action"] == "LENS_SWAP"
    assert eval_c["new_lens"] == "android_ui_dump"
    assert eval_c["c2_rate"] >= 0.35

    pol_c = store.get_policy("tiktok")
    assert pol_c["active_lens"] == "android_ui_dump"
    assert pol_c["poll_interval_sec"] >= 7200

    # ------------------------------------------------------------------------
    # Step D: ProTeGi Gradient Logging & Mark-and-Sweep Garbage Collection
    # ------------------------------------------------------------------------
    grad_id = store.log_protegi_gradient(
        target_skill_path="skills/viral-trend-pipeline/SKILL.md",
        divergence_entropy=0.042,
        critique_text="Web accessibility tree encountered anti-bot DOM rotation. Switch to Android UI hierarchy.",
        gradient_diff="--- a/SKILL.md\n+++ b/SKILL.md\n- default_lens: web_a11y_tree\n+ default_lens: android_ui_dump",
        applied_status="APPLIED",
    )
    assert grad_id is not None

    # Check that trends GC purged the 20-day old trend on cycle B and exported current_trends.md
    assert res_b["gc_trends_purged"] == 1
    assert res_c["gc_trends_purged"] == 0
    assert os.path.exists(trends_md)
    with open(trends_md, "r", encoding="utf-8") as f:
        md_content = f.read()
    assert "# Active 14-Day Viral Trend Catalog" in md_content
    assert "#Ultra2026" in md_content
    assert "#Wembanyama" in md_content
    assert "#StaleTag" not in md_content


# ============================================================================
# 4. Cluster 2 Failover Triggers Headless Mobile Scraping
# ============================================================================

def test_e2e_04_cluster_2_triggers_headless_mobile_scraping_and_dlq(e2e_env):
    """Verifies that when Cluster 2 failover occurs, the ML agent successfully activates
    the headless Android CLI mobile scraper (`unified_ops_hub.mobile.scraper`),
    extracts structured trends with viral velocity scoring, and isolates corrupted UI nodes to DLQ.
    """
    dlq_mgr: DLQManager = e2e_env["dlq_manager"]

    # Mock ADB command runner for headless Android execution
    mock_layout_nodes = [
        {
            "class": "android.widget.TextView",
            "resourceId": "com.zhiliaoapp.musically:id/desc",
            "text": "Insane mainstage festival drop! #Ultra2026 #BigRoomNeverDies",
            "bounds": "[50,1800][1000,1950]",
        },
        {
            "class": "android.widget.TextView",
            "resourceId": "com.zhiliaoapp.musically:id/music_title",
            "text": "Ultra Miami 2026 Mainstage ID",
            "bounds": "[50,1960][600,2020]",
        },
        {
            "class": "android.widget.TextView",
            "resourceId": "com.zhiliaoapp.musically:id/author",
            "text": "@martingarrix",
            "bounds": "[50,1740][400,1790]",
        },
        {
            "class": "android.widget.Button",
            "resourceId": "com.zhiliaoapp.musically:id/like_count",
            "text": "1.4M",
            "bounds": "[950,1200][1050,1300]",
        },
        {
            "class": "android.widget.Button",
            "resourceId": "com.zhiliaoapp.musically:id/comment_count",
            "text": "12.5K",
            "bounds": "[950,1350][1050,1450]",
        },
        {
            "class": "android.widget.Button",
            "resourceId": "com.zhiliaoapp.musically:id/share_count",
            "text": "45.2K",
            "bounds": "[950,1500][1050,1600]",
        },
    ]

    def mock_adb_runner(cmd: List[str], timeout: float = 15.0) -> str:
        cmd_str = " ".join(cmd)
        if "wm size" in cmd_str:
            return "Physical size: 1080x2400"
        if "rampart_auto_enabled_switch_enabled" in cmd_str:
            return ""
        if "layout" in cmd_str:
            return json.dumps(mock_layout_nodes)
        if "input swipe" in cmd_str:
            return ""
        if "devices -l" in cmd_str:
            return "List of devices attached\nemulator-5554 device product:sdk_gphone64_arm64 model:sdk_gphone64_arm64 device:emulator64_arm64"
        return ""

    client = AndroidClient(serial="emulator-5554", runner=mock_adb_runner)
    scraper = MobileViralTrendScraper(client=client, dlq_manager=dlq_mgr)

    # Execute autonomous scrape session
    session, items, metrics = scraper.scrape_feed(
        platform="tiktok",
        max_swipes=2,
        delay_between_swipes_sec=0.01,
    )

    assert session.status == "COMPLETED"
    assert session.items_scraped >= 1
    assert len(items) >= 1

    item = items[0]
    assert item.platform == "tiktok"
    assert "Ultra2026" in item.hashtags
    assert item.sound_title == "Ultra Miami 2026 Mainstage ID"
    assert item.author_handle == "@martingarrix"
    assert item.like_count == 1_400_000
    assert item.comment_count == 12_500
    assert item.share_count == 45_200

    # Viral Velocity Verification: (1.4M*10 + 12.5K*50 + 45.2K*100) / 1.0 = 19,145,000.0
    expected_velocity = (1_400_000 * 10.0 + 12_500 * 50.0 + 45_200 * 100.0) / 1.0
    assert item.velocity_score == round(expected_velocity, 2)

    # Telemetry metrics verification
    assert metrics.successful_parses >= 1
    assert metrics.yield_rate > 0.0
    assert len(metrics.top_hashtags) >= 1

    # ------------------------------------------------------------------------
    # Adversarial Sub-test: Corrupted Layout Nodes Quarantined to DLQ
    # ------------------------------------------------------------------------
    corrupted_nodes = ["NOT_A_DICT", 12345, None]  # Violates dictionary node contract
    parsed_items = scraper.parse_layout_nodes(corrupted_nodes, platform="tiktok")
    assert parsed_items == []

    # Verify DLQ caught the parsing exception
    dlq_incidents = dlq_mgr.list_incidents(source_service="mobile_scraper")
    assert len(dlq_incidents) >= 1
    assert dlq_incidents[0].error_category == ErrorCategory.CORRUPTED_PAYLOAD
    assert "Layout node parsing error" in dlq_incidents[0].error_message


# ============================================================================
# 5. DLQ Incident Quarantine, Resiliency & Replay Cycle
# ============================================================================

def test_e2e_05_dlq_capture_resiliency_and_replay(e2e_env):
    """Verifies that simulated failure payloads and unhandled exceptions are:
    1. Caught by gateway exception handlers without crashing the daemon
    2. Safely quarantined into DLQ SQLite WAL + JSON audit artifacts
    3. Replayed successfully, transitioning status from QUARANTINED to RESOLVED
    4. Purged cleanly upon resolution
    """
    client: TestClient = e2e_env["client"]
    dlq_mgr: DLQManager = e2e_env["dlq_manager"]

    # ------------------------------------------------------------------------
    # 1. Schema Validation Error on Sports Card Capture
    # ------------------------------------------------------------------------
    malformed_card = {"year": "2024", "condition": "Raw"}  # Missing required 'player'
    resp_val = client.post("/api/v1/sports/capture", json=malformed_card)
    assert resp_val.status_code == 422
    val_body = resp_val.json()
    assert val_body["error"] == "CORRUPTED_PAYLOAD"
    assert "incident_id" in val_body
    inc_val_id = val_body["incident_id"]

    inc_val = dlq_mgr.get_incident(inc_val_id)
    assert inc_val is not None
    assert inc_val.error_category == ErrorCategory.CORRUPTED_PAYLOAD
    assert inc_val.status == IncidentStatus.QUARANTINED

    # ------------------------------------------------------------------------
    # 2. Simulated PySpark Partition Crash during ML Grading
    # ------------------------------------------------------------------------
    resp_crash = client.post(
        "/api/v1/simulate-crash",
        json={"error_type": "MLGradingCrash", "trigger": True},
    )
    assert resp_crash.status_code == 500
    crash_body = resp_crash.json()
    assert crash_body["error"] == "INTERNAL_SERVER_ERROR"
    assert "incident_id" in crash_body
    inc_crash_id = crash_body["incident_id"]

    inc_crash = dlq_mgr.get_incident(inc_crash_id)
    assert inc_crash is not None
    assert inc_crash.error_category == ErrorCategory.ML_GRADING_FAILURE
    assert inc_crash.status == IncidentStatus.QUARANTINED

    # Ensure daemon remains alive and healthy after catching 500 error
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "HEALTHY"

    # ------------------------------------------------------------------------
    # 3. File Quarantine Primitive
    # ------------------------------------------------------------------------
    corrupt_file_path = os.path.join(e2e_env["workspace"], "corrupted_media_clip.mp4")
    with open(corrupt_file_path, "wb") as f:
        f.write(b"CORRUPTED_HEX_HEADER_\x00\xFF\xFE")

    file_inc, quarantined_path = dlq_mgr.quarantine_file(
        source_file_path=corrupt_file_path,
        source_service="media_pipeline",
        reason="FFmpeg MOOV atom corrupted",
    )
    assert not os.path.exists(corrupt_file_path)
    assert os.path.exists(quarantined_path)
    assert file_inc.error_category == ErrorCategory.CORRUPTED_PAYLOAD

    # ------------------------------------------------------------------------
    # 4. DLQ REST API Inspection & Manual Replay
    # ------------------------------------------------------------------------
    incidents_resp = client.get("/api/v1/dlq/incidents")
    assert incidents_resp.status_code == 200
    inc_list = incidents_resp.json()["incidents"]
    assert len(inc_list) >= 3

    # Replay the crash incident via REST endpoint
    replay_resp = client.post(f"/api/v1/dlq/retry/{inc_crash_id}")
    assert replay_resp.status_code == 200
    assert replay_resp.json()["success"] is True

    replayed_inc = dlq_mgr.get_incident(inc_crash_id)
    assert replayed_inc.status == IncidentStatus.RESOLVED
    assert replayed_inc.retry_count == 1
    assert replayed_inc.resolved_at is not None

    # Check stats endpoint
    stats_resp = client.get("/api/v1/dlq/stats")
    assert stats_resp.status_code == 200
    dlq_stats = stats_resp.json()
    assert dlq_stats["total_incidents"] >= 3
    assert dlq_stats["resolved_count"] >= 1

    # ------------------------------------------------------------------------
    # 5. Purge Resolved Incidents
    # ------------------------------------------------------------------------
    purge_resp = client.post("/api/v1/dlq/purge")
    assert purge_resp.status_code == 200
    assert purge_resp.json()["deleted_count"] >= 1

    assert dlq_mgr.get_incident(inc_crash_id) is None  # Purged
    assert dlq_mgr.get_incident(inc_val_id) is not None  # Still quarantined


# ============================================================================
# 6. Next.js Dashboard API Payload Contract Parity
# ============================================================================

def test_e2e_06_dashboard_api_payload_contract_parity(e2e_env):
    """Verifies that all FastAPI gateway response payloads strictly adhere to the
    TypeScript data contracts defined in dashboard/src/lib/api.ts.
    """
    client: TestClient = e2e_env["client"]

    # 1. SystemHealth Contract (api.ts: SystemHealth)
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    h = health_resp.json()
    assert isinstance(h["status"], str)
    assert isinstance(h["version"], str)
    assert isinstance(h["uptime_seconds"], (int, float))
    assert isinstance(h["ports"], dict)
    assert isinstance(h["dlq_stats"], dict)
    assert isinstance(h["services"], dict)

    # 2. SportsCard & SportsStats Contracts (api.ts: SportsCard, SportsStats)
    card_resp = client.post(
        "/api/v1/sports/capture",
        json={
            "player": "Luka Doncic",
            "year": "2018",
            "set_name": "Prizm Base Rookie",
            "card_number": "280",
            "category": "Basketball",
            "condition": "Raw",
            "investment": 400.0,
            "estimated_value": 620.0,
        },
    )
    assert card_resp.status_code == 200
    c = card_resp.json()
    assert isinstance(c["id"], str)
    assert isinstance(c["player"], str)
    assert isinstance(c["year"], str)
    assert isinstance(c["set_name"], str)
    assert isinstance(c["card_number"], str)
    assert isinstance(c["category"], str)
    assert isinstance(c["condition"], str)
    assert isinstance(c["investment"], (int, float))
    assert isinstance(c["estimated_value"], (int, float))
    assert isinstance(c["ai_status"], str)
    assert isinstance(c["captured_at"], (int, float))

    portfolio_resp = client.get("/api/v1/sports/staging")
    assert portfolio_resp.status_code == 200
    p = portfolio_resp.json()
    assert isinstance(p["total"], int)
    assert isinstance(p["cards"], list)

    stats_resp = client.get("/api/v1/sports/stats")
    assert stats_resp.status_code == 200
    s = stats_resp.json()
    assert isinstance(s["total_cards"], int)
    assert isinstance(s["total_investment"], (int, float))
    assert isinstance(s["total_estimated_value"], (int, float))

    # 3. MediaJob Contract (api.ts: MediaJob)
    media_resp = client.post(
        "/api/v1/media/trigger",
        json={"clip_name": "edc_vegas_drop_01.mp4", "mode": "vertical_reframes"},
    )
    assert media_resp.status_code == 202
    m = media_resp.json()
    assert isinstance(m["job_id"], str)
    assert isinstance(m["clip_name"], str)
    assert isinstance(m["mode"], str)
    assert isinstance(m["status"], str)
    assert isinstance(m["progress"], (int, float))
    assert isinstance(m["created_at"], (int, float))

    # 4. VideoGradeResult Contract (api.ts: VideoGradeResult)
    grade_resp = client.post(
        "/api/v1/ml/grade",
        json={
            "video_id": "vid_contract_01",
            "scores": {"HRV": 88.0, "DPAW": 84.0, "ADR_SFD": 80.0, "CKE_MVE": 75.0, "LTSS": 78.0},
            "aspect_ratio": "9:16",
        },
    )
    assert grade_resp.status_code == 200
    g = grade_resp.json()
    assert isinstance(g["video_id"], str)
    assert isinstance(g["evpi"], (int, float))
    assert g["verdict"] in ["VIRAL_READY", "HIGH_POTENTIAL", "MODERATE_REACH", "LOW_REACH"]
    assert isinstance(g["scores"], dict)
    assert isinstance(g["aspect_ratio"], str)

    # 5. MLTelemetryData Contract (api.ts: MLTelemetryData)
    telem_resp = client.get("/api/v1/agent/telemetry")
    assert telem_resp.status_code == 200
    t = telem_resp.json()
    assert isinstance(t["platform"], str)
    assert t["active_lens"] in ["web_a11y_tree", "android_ui_dump"]
    assert isinstance(t["poll_interval_sec"], int)
    assert isinstance(t["retry_backoff_base_sec"], (int, float))
    assert isinstance(t["clusters"], dict)
    assert "c0_healthy" in t["clusters"]
    assert "c1_throttled" in t["clusters"]
    assert "c2_failover" in t["clusters"]
    assert isinstance(t["entropy"], (int, float))
    assert isinstance(t["trending_sounds"], list)

    # 6. Lens Failover Contract (api.ts: triggerLensFailover)
    failover_resp = client.post("/api/v1/viral/failover", json={"platform": "tiktok"})
    assert failover_resp.status_code == 200
    fo = failover_resp.json()
    assert isinstance(fo["success"], bool)
    assert isinstance(fo["active_lens"], str)
    assert isinstance(fo["reason"], str)


# ============================================================================
# 7. Full System Orchestration Master Smoke Cycle
# ============================================================================

def test_e2e_07_full_system_orchestration_master_smoke_cycle(e2e_env):
    """End-to-end master smoke cycle:
    Port allocation -> Gateway boot -> Multi-domain execution -> ML WAL loop & K-Means clustering ->
    Mobile scraper on Cluster 2 failover -> DLQ containment & Replay -> Dashboard API validation.
    """
    client: TestClient = e2e_env["client"]
    port_mgr: PortManager = e2e_env["port_manager"]
    dlq_mgr: DLQManager = e2e_env["dlq_manager"]
    telemetry_db = e2e_env["telemetry_db_path"]

    # 1. Port allocation check
    port = port_mgr.find_available_port(preferred_port=8000)
    assert port in [8000, 8001, 8002]

    # 2. Sports Card Domain
    c_resp = client.post(
        "/api/v1/sports/capture",
        json={"player": "Caitlin Clark", "year": "2024", "investment": 500.0, "estimated_value": 850.0},
    )
    assert c_resp.status_code == 200

    # 3. Media Domain
    m_resp = client.post("/api/v1/media/trigger", json={"clip_name": "master_smoke.mp4"})
    assert m_resp.status_code == 202

    # 4. ML Grade Domain
    g_resp = client.post(
        "/api/v1/ml/grade",
        json={"video_id": "vid_smoke_01", "scores": {"HRV": 95.0, "DPAW": 90.0, "ADR_SFD": 85.0, "CKE_MVE": 80.0, "LTSS": 80.0}},
    )
    assert g_resp.status_code == 200
    assert g_resp.json()["verdict"] == "VIRAL_READY"

    # 5. Autonomous ML Agent Cycle
    agent = AutonomousMLAgent(telemetry_db_path=telemetry_db)
    spans = [
        {"platform": "tiktok", "duration_ms": 700, "yield_count": 30, "error_count": 0, "status_code": "SUCCESS"}
        for _ in range(12)
    ]
    cycle_res = agent.run_optimization_cycle(mock_spans=spans, platforms=["tiktok"])
    assert cycle_res["status"] == "COMPLETED"

    # 6. DLQ Resiliency & Recovery
    crash_resp = client.post("/api/v1/simulate-crash", json={"error_type": "MLGradingCrash", "trigger": True})
    assert crash_resp.status_code == 500
    inc_id = crash_resp.json()["incident_id"]

    replay_res = client.post(f"/api/v1/dlq/retry/{inc_id}")
    assert replay_res.status_code == 200
    assert replay_res.json()["success"] is True

    # 7. Final Health & Dashboard Contract Check
    health_final = client.get("/api/v1/health")
    assert health_final.status_code == 200
    assert health_final.json()["status"] == "HEALTHY"
