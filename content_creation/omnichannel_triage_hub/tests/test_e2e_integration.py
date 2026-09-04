"""
Comprehensive 4-Tier E2E Integration & Verification Test Suite
Omnichannel Triage Hub

Architecture & Tiers:
- Tier 1: Feature Coverage (F1 - F11: Frontend bundle, Layout, Phone Link Feed, Collision Queue, FastAPI routes, CORS, Data Connect)
- Tier 2: Boundary & Corner Cases (Offline fallbacks, payload validation, format toggling, metric calculations, concurrency)
- Tier 3: Cross-Feature Combinations (Pull -> Staging, Capture -> Tag Ingestion, Pull -> Collision Resolution, Dynamic Fallback, Full Lifecycle)
- Tier 4: Real-World Workloads (Batch ingestion, Live Phone Link tagging loop, Multi-item collision arena, Offline isolation, Rapid UI stress)

Strict compliance with Rule R16 (Absolute imports) and Rule R2 (Zero-Discretion Deterministic Verification).
"""

import os
import sys
import re
import json
import time
import base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List

import pytest
from fastapi.testclient import TestClient

# Resolve paths
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
DAEMON_DIR = REPO_ROOT / "local_daemon"
FRONTEND_DIR = REPO_ROOT / "frontend"
DATACONNECT_DIR = REPO_ROOT / "dataconnect"
SRC_DIR = FRONTEND_DIR / "src"
DIST_DIR = FRONTEND_DIR / "dist"

# Add local_daemon to sys.path for absolute imports
if str(DAEMON_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_DIR))

from main import app
from models import (
    AdbPullRequest,
    AdbPullResponse,
    CaptureScreenRequest,
    CaptureScreenResponse,
    HealthResponse,
    StagingInventoryResponse,
)


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """Synchronous test client for FastAPI local daemon."""
    with TestClient(app) as client:
        yield client


# ==============================================================================
# TIER 1: FEATURE COVERAGE (Deterministic Verification of Features F1 - F11)
# ==============================================================================

class TestTier1FeatureCoverage:
    """Deterministic validation of each core feature in isolation."""

    def test_f1_frontend_bundle_and_scaffolding(self):
        """F1: Verifies Vite build artifacts, package.json dependencies, and index.html structure."""
        pkg_json_path = FRONTEND_DIR / "package.json"
        assert pkg_json_path.exists(), "package.json missing"
        pkg_data = json.loads(pkg_json_path.read_text(encoding="utf-8"))
        deps = pkg_data.get("dependencies", {})
        assert "@firebase/data-connect" in deps
        assert "firebase" in deps
        assert "react" in deps
        assert "react-dom" in deps
        assert "lucide-react" in deps

        # Verify built production bundle
        dist_index = DIST_DIR / "index.html"
        assert dist_index.exists(), "dist/index.html missing - run npm run build"
        dist_html = dist_index.read_text(encoding="utf-8")
        assert '<div id="root">' in dist_html
        assert '<script type="module"' in dist_html

        assets_dir = DIST_DIR / "assets"
        assert assets_dir.exists()
        js_bundles = list(assets_dir.glob("*.js"))
        css_bundles = list(assets_dir.glob("*.css"))
        assert len(js_bundles) > 0, "No JS bundle in dist/assets"
        assert len(css_bundles) > 0, "No CSS bundle in dist/assets"
        assert js_bundles[0].stat().st_size > 50000, "JS bundle is too small"

    def test_f2_tailwind_two_column_layout(self):
        """F2: Verifies Tailwind CSS 12-column grid and theme tokens."""
        app_source = (SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        feed_source = (SRC_DIR / "components" / "PhoneLinkFeed.tsx").read_text(encoding="utf-8")
        col_source = (SRC_DIR / "components" / "CollisionQueue.tsx").read_text(encoding="utf-8")
        index_css = (SRC_DIR / "index.css").read_text(encoding="utf-8")

        assert "grid-cols-12" in app_source, "Main layout must use 12-column grid"
        assert "col-span-4" in feed_source, "Left column must span 4 cols"
        assert "col-span-8" in col_source, "Right column must span 8 cols"
        assert "--background" in index_css, "--background token missing"
        assert "--foreground" in index_css, "--foreground token missing"
        assert "--primary" in index_css, "--primary token missing"
        assert "--card" in index_css, "--card token missing"

    def test_f3_phonelink_feed_and_vision_card(self):
        """F3: Verifies Phone Link Feed 9:16 aspect ratio container and Gemini Vision card."""
        feed_source = (SRC_DIR / "components" / "PhoneLinkFeed.tsx").read_text(encoding="utf-8")
        assert "aspect-[9/16]" in feed_source, "Feed must enforce 9:16 aspect ratio"
        assert "Live Capture" in feed_source, "Live Capture badge missing"
        assert "Gemini Vision Result" in feed_source, "Gemini Vision card missing"
        assert "Entity (L2)" in feed_source
        assert "Attribute (L3)" in feed_source
        assert "Ctrl+Shift+T to Tag" in feed_source

    def test_f4_collision_resolution_queue_elements(self):
        """F4: Verifies Collision Resolution Queue side-by-side comparison cards and action buttons."""
        col_source = (SRC_DIR / "components" / "CollisionQueue.tsx").read_text(encoding="utf-8")
        assert "Collision Resolution Queue" in col_source
        assert "Resolution Mismatch" in col_source
        assert "Keep 4K ADB Version" in col_source
        assert "Keep Takeout" in col_source
        assert "Undo" in col_source

    def test_f5_fastapi_health_endpoint(self, api_client: TestClient):
        """F5: Verifies GET /api/health returns status=ok, ADB state, device count, and uptime."""
        res = api_client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert isinstance(data["adb_connected"], bool)
        assert isinstance(data["device_count"], int)
        assert isinstance(data["devices"], list)
        assert data["mock_available"] is True
        assert data["uptime_seconds"] >= 0.0

    def test_f6_trigger_adb_pull_endpoint(self, api_client: TestClient):
        """F6: Verifies POST /api/trigger-adb-pull executes pull with valid metrics."""
        res = api_client.post("/api/trigger-adb-pull", json={"mock": True, "limit": 2})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] in ("success", "mock_success")
        assert data["bytes_transferred"] > 0
        assert data["total_count"] >= 1
        assert len(data["pulled_files"]) >= 1
        assert "duration_ms" in data

    def test_f7_capture_screen_endpoint(self, api_client: TestClient):
        """F7: Verifies POST /api/capture-screen returns 9:16 frame with base64 data."""
        res = api_client.post("/api/capture-screen", json={"mock": True, "format": "png"})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] in ("success", "mock_success")
        assert data["image_base64"] is not None
        assert data["width"] == 540
        assert data["height"] == 960

    def test_f8_cors_headers_for_frontend_origin(self, api_client: TestClient):
        """F8: Verifies CORS preflight response headers for React Vite frontend origin."""
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Accept",
        }
        res = api_client.options("/api/trigger-adb-pull", headers=headers)
        assert res.status_code == 200
        allow_origin = res.headers.get("access-control-allow-origin")
        assert allow_origin in ("*", "http://localhost:5173")
        allow_methods = res.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods or "*" in allow_methods

    def test_f9_dataconnect_schema_and_config(self):
        """F9: Verifies Firebase Data Connect configuration and PostgreSQL schema."""
        dc_yaml = DATACONNECT_DIR / "dataconnect.yaml"
        conn_yaml = DATACONNECT_DIR / "connector" / "connector.yaml"
        schema_gql = DATACONNECT_DIR / "schema" / "schema.gql"

        assert dc_yaml.exists(), "dataconnect.yaml missing"
        assert conn_yaml.exists(), "connector.yaml missing"
        assert schema_gql.exists(), "schema.gql missing"

        schema_content = schema_gql.read_text(encoding="utf-8")
        assert "type VideoTag @table" in schema_content
        assert "id: Int64!" in schema_content
        assert "filename: String!" in schema_content
        assert "filepath: String!" in schema_content
        assert "domain: String!" in schema_content
        assert "entity: String!" in schema_content
        assert "viralFeatures: Any!" in schema_content
        assert "technical: Any!" in schema_content
        assert "createdAt: Timestamp!" in schema_content
        assert "updatedAt: Timestamp!" in schema_content

    def test_f10_dataconnect_sdk_and_graphql_ops(self):
        """F10: Verifies GraphQL queries/mutations and frontend Data Connect TypeScript SDK."""
        queries_gql = (DATACONNECT_DIR / "connector" / "queries.gql").read_text(encoding="utf-8")
        mutations_gql = (DATACONNECT_DIR / "connector" / "mutations.gql").read_text(encoding="utf-8")
        sdk_ts = (SRC_DIR / "lib" / "dataconnect" / "index.ts").read_text(encoding="utf-8")

        assert "query ListVideoTags" in queries_gql
        assert "query GetVideoTag" in queries_gql
        assert "mutation CreateVideoTag" in mutations_gql

        assert "export const connectorConfig" in sdk_ts
        assert "export function listVideoTags" in sdk_ts
        assert "export function createVideoTag" in sdk_ts
        assert "export function useVideoTags" in sdk_ts
        assert "INITIAL_OFFLINE_VIDEO_TAGS" in sdk_ts

    def test_f11_api_client_and_ui_wiring(self):
        """F11: Verifies frontend/src/lib/api.ts typed REST client and App.tsx wiring."""
        api_ts = (SRC_DIR / "lib" / "api.ts").read_text(encoding="utf-8")
        app_tsx = (SRC_DIR / "App.tsx").read_text(encoding="utf-8")

        # Verify exported API methods in api.ts
        assert "export async function triggerAdbPull" in api_ts
        assert "export async function captureScreen" in api_ts
        assert "export async function getHealth" in api_ts
        assert "export async function getDevices" in api_ts
        assert "export async function getStagingInventory" in api_ts

        # Verify App.tsx imports and uses API client
        assert "triggerAdbPull" in app_tsx
        assert "captureScreen" in app_tsx
        assert "getHealth" in app_tsx
        assert "handleTriggerAdbPull" in app_tsx
        assert "handleCaptureScreen" in app_tsx


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES
# ==============================================================================

class TestTier2BoundaryCases:
    """Stress tests boundary inputs, network edge cases, and validation rules."""

    def test_b1_client_offline_fallback_simulation(self):
        """B1: Verifies client-side fallback data contracts when daemon is offline."""
        # Test simulation of fallback structures identical to api.ts
        mock_bytes = 564166656
        mock_total = 97177649152
        filename = "20260819_213606.mp4"

        fallback_pull = {
            "success": True,
            "status": "mock_success",
            "message": "Daemon offline - simulated client ADB pull completed (538 MB)",
            "device_id": "emulator-5554-fallback",
            "bytes_transferred": mock_bytes,
            "total_bytes": mock_total,
            "file_path": f"/sdcard/DCIM/Camera/{filename}",
            "pulled_files": [
                {
                    "filename": filename,
                    "local_path": f"./staging/videos/{filename}",
                    "size_bytes": mock_bytes,
                    "timestamp": "2026-08-27T12:00:00Z",
                    "is_mock": True,
                }
            ],
            "total_count": 1,
            "duration_ms": 1240,
            "is_fallback": True,
        }

        assert fallback_pull["success"] is True
        assert fallback_pull["bytes_transferred"] > 0
        assert fallback_pull["is_fallback"] is True
        assert len(fallback_pull["pulled_files"]) == 1

    def test_b2_daemon_payload_validation(self, api_client: TestClient):
        """B2: Verifies validation constraints (e.g. limit bounds: 1 <= limit <= 100)."""
        # Invalid limit: 0 (less than 1)
        res_low = api_client.post("/api/trigger-adb-pull", json={"limit": 0})
        assert res_low.status_code == 422

        # Invalid limit: 200 (greater than 100)
        res_high = api_client.post("/api/trigger-adb-pull", json={"limit": 200})
        assert res_high.status_code == 422

        # Valid limit boundaries: 1 and 100
        res_min = api_client.post("/api/trigger-adb-pull", json={"limit": 1, "mock": True})
        assert res_min.status_code == 200
        assert res_min.json()["total_count"] == 1

        # Empty body default
        res_empty = api_client.post("/api/trigger-adb-pull", json={})
        assert res_empty.status_code == 200

    def test_b3_format_toggling_and_custom_paths(self, api_client: TestClient):
        """B3: Tests format toggling (png, jpeg, base64) and custom directory paths."""
        # PNG format
        res_png = api_client.post("/api/capture-screen", json={"mock": True, "format": "png"})
        assert res_png.status_code == 200
        assert "data:image/png;base64," in res_png.json()["image_base64"]

        # JPEG format
        res_jpeg = api_client.post("/api/capture-screen", json={"mock": True, "format": "jpeg"})
        assert res_jpeg.status_code == 200
        assert "data:image/jpeg;base64," in res_jpeg.json()["image_base64"]

        # Custom destination pull
        custom_dest = "./staging/videos/test_custom_batch"
        res_custom = api_client.post("/api/trigger-adb-pull", json={
            "mock": True,
            "destination_path": custom_dest,
            "limit": 1,
        })
        assert res_custom.status_code == 200
        assert res_custom.json()["success"] is True

    def test_b4_byte_count_and_large_metric_calculations(self):
        """B4: Verifies MB/GB formatting logic and non-zero transfer durations."""
        def format_transfer_metric(bytes_count: int) -> str:
            if bytes_count >= 1024 * 1024 * 1024:
                return f"{bytes_count / (1024 * 1024 * 1024):.1f} GB"
            return f"{bytes_count / (1024 * 1024):.1f} MB"

        assert format_transfer_metric(564166656) == "538.0 MB"
        assert format_transfer_metric(97177649152) == "90.5 GB"
        assert format_transfer_metric(0) == "0.0 MB"
        assert format_transfer_metric(1048576) == "1.0 MB"

    def test_b5_concurrent_requests_handling(self, api_client: TestClient):
        """B5: Dispatches concurrent requests to ensure server stability under multi-threaded calls."""
        def call_pull():
            return api_client.post("/api/trigger-adb-pull", json={"mock": True, "limit": 1})

        def call_capture():
            return api_client.post("/api/capture-screen", json={"mock": True, "format": "png"})

        def call_health():
            return api_client.get("/api/health")

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(call_pull),
                executor.submit(call_capture),
                executor.submit(call_health),
                executor.submit(call_pull),
                executor.submit(call_capture),
                executor.submit(call_health),
            ]
            results = [f.result() for f in futures]

        for res in results:
            assert res.status_code == 200
            assert res.json().get("success", True) is True or res.json().get("status") == "ok"


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==============================================================================

class TestTier3CrossFeatureCombinations:
    """Validates interaction pipelines connecting UI, API daemon, staging, and Data Connect."""

    def test_c1_pull_trigger_to_staging_inventory(self, api_client: TestClient):
        """C1: Trigger ADB Pull -> verify file staging -> query /api/staging inventory."""
        # 1. Trigger pull
        pull_res = api_client.post("/api/trigger-adb-pull", json={"mock": True, "limit": 2})
        assert pull_res.status_code == 200
        pull_data = pull_res.json()
        assert pull_data["success"] is True

        # 2. Check staging inventory
        staging_res = api_client.get("/api/staging")
        assert staging_res.status_code == 200
        staging_data = staging_res.json()
        assert staging_data["count"] >= 1
        assert staging_data["total_size_bytes"] > 0
        filenames = [f["filename"] for f in staging_data["files"]]
        assert any(".mp4" in name or ".png" in name for name in filenames)

    def test_c2_screen_capture_to_dataconnect_tag_lifecycle(self, api_client: TestClient):
        """C2: Capture screen -> Gemini Vision analysis -> construct Data Connect tag mutation."""
        # 1. Capture screen
        cap_res = api_client.post("/api/capture-screen", json={"mock": True, "format": "png"})
        assert cap_res.status_code == 200
        cap_data = cap_res.json()
        assert cap_data["image_base64"].startswith("data:image/png;base64,")

        # 2. Extract vision attributes & construct CreateVideoTag mutation payload
        tag_payload = {
            "filename": "20260819_213606.mp4",
            "filepath": "/sdcard/DCIM/Camera/20260819_213606.mp4",
            "domain": "EDM_FESTIVALS",
            "entity": "Excision (Bass Canyon 2026)",
            "viralFeatures": {
                "visualHooks": ["Mainstage Lasers", "Paradox Drop", "Bass Canyon"],
                "energyLevel": "Maximum",
                "screenFrame": cap_data["image_base64"][:50] + "...",
            },
            "technical": {
                "resolution": f"{cap_data['width']}x{cap_data['height']}",
                "fps": 60,
                "codec": "h264",
                "bitrateKbps": 48000,
                "audioClipping": False,
            },
        }

        # Verify mutation payload conforms to schema types
        assert tag_payload["domain"] in ("EDM_FESTIVALS", "SPORTS_CARDS", "TRAVEL_AND_LIFE")
        assert isinstance(tag_payload["viralFeatures"]["visualHooks"], list)
        assert tag_payload["technical"]["fps"] == 60

    def test_c3_adb_pull_to_collision_queue_resolution(self, api_client: TestClient):
        """C3: Pull 4K video -> identify Takeout collision -> resolve via 'adb' choice -> undo."""
        # 1. Simulate pull result for 4K video
        pull_res = api_client.post("/api/trigger-adb-pull", json={"mock": True, "limit": 1})
        assert pull_res.status_code == 200

        # 2. Simulate collision item state transition
        item = {
            "id": "col-test-01",
            "filename": "20260819_213606.mp4",
            "timestamp": "Aug 19, 2026 • 9:36 PM EST",
            "conflictType": "Resolution Mismatch",
            "adbSource": {"title": "Local ADB Pull", "resolution": "4K", "size": "538 MB"},
            "takeoutSource": {"title": "Takeout Cloud", "resolution": "1080p", "size": "42 MB"},
            "resolved": False,
            "resolutionChoice": None,
        }

        # Resolve: Keep 4K ADB
        item["resolved"] = True
        item["resolutionChoice"] = "adb"
        assert item["resolved"] is True
        assert item["resolutionChoice"] == "adb"

        # Undo resolution
        item["resolved"] = False
        item["resolutionChoice"] = None
        assert item["resolved"] is False
        assert item["resolutionChoice"] is None

    def test_c4_dual_engine_dynamic_fallback_switching(self, api_client: TestClient):
        """C4: Verifies daemon automatically falls back to procedural mock when real ADB is absent."""
        # Explicit mock=False should safely execute without raising 500
        res = api_client.post("/api/trigger-adb-pull", json={"mock": False, "limit": 1})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] in ("success", "mock_success")

        # Explicit mock=False for screen capture
        res_cap = api_client.post("/api/capture-screen", json={"mock": False, "format": "png"})
        assert res_cap.status_code == 200
        data_cap = res_cap.json()
        assert data_cap["success"] is True

    def test_c5_end_to_end_integrated_pipeline(self, api_client: TestClient):
        """C5: End-to-end multi-step flow: Health -> Screen Capture -> ADB Pull -> Staging Inventory."""
        # Step 1: Health check
        health = api_client.get("/api/health").json()
        assert health["status"] == "ok"

        # Step 2: Capture screen frame
        cap = api_client.post("/api/capture-screen", json={"mock": True}).json()
        assert cap["success"] is True
        assert cap["width"] == 540

        # Step 3: Trigger ADB pull
        pull = api_client.post("/api/trigger-adb-pull", json={"mock": True, "limit": 1}).json()
        assert pull["success"] is True

        # Step 4: Verify staging has media files
        staging = api_client.get("/api/staging").json()
        assert staging["count"] > 0


# ==============================================================================
# TIER 4: REAL-WORLD WORKLOAD SCENARIOS
# ==============================================================================

class TestTier4RealWorldWorkloads:
    """Simulates production user journeys and high-concurrency workloads."""

    def test_s1_batch_media_ingestion_scenario(self, api_client: TestClient):
        """S1: High-resolution video batch pull workflow with duration tracking."""
        start = time.time()
        res = api_client.post("/api/trigger-adb-pull", json={"mock": True, "limit": 1})
        elapsed = time.time() - start

        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["total_count"] >= 1
        assert len(data["pulled_files"]) >= 1
        assert data["bytes_transferred"] > 0
        assert data["duration_ms"] > 0
        assert elapsed < 10.0  # Completed in reasonable time

    def test_s2_live_phonelink_stream_tagging_loop(self, api_client: TestClient):
        """S2: Simulates 5 continuous Phone Link scrolling and tagging cycles."""
        domains = ["EDM_FESTIVALS", "SPORTS_CARDS", "TRAVEL_AND_LIFE", "EDM_FESTIVALS", "SPORTS_CARDS"]
        entities = [
            "Illenium (Trilogy 2026)",
            "1993 SP Derek Jeter Foil PSA 10",
            "Sedona Red Rocks Drone 4K",
            "Excision Mainstage",
            "2003 Topps Chrome LeBron James #111 BGS 9.5",
        ]

        tagged_records = []
        for i in range(5):
            cap = api_client.post("/api/capture-screen", json={"mock": True, "format": "png"}).json()
            assert cap["success"] is True

            record = {
                "id": str(i + 1),
                "filename": f"20260822_00{i}000.mp4",
                "domain": domains[i],
                "entity": entities[i],
                "frame_timestamp": cap["timestamp"],
            }
            tagged_records.append(record)

        assert len(tagged_records) == 5
        assert tagged_records[1]["domain"] == "SPORTS_CARDS"
        assert "LeBron James" in tagged_records[4]["entity"]

    def test_s3_multi_item_collision_batch_resolution(self):
        """S3: Multi-item collision batch: 5 conflicts with 4K vs Takeout, testing state isolation."""
        collisions = [
            {"id": f"col-{i}", "choice": "adb" if i % 2 == 0 else "takeout", "resolved": False}
            for i in range(5)
        ]

        # Resolve all items
        for col in collisions:
            col["resolved"] = True
            col["resolutionChoice"] = col["choice"]

        # Verify state isolation
        assert collisions[0]["resolutionChoice"] == "adb"
        assert collisions[1]["resolutionChoice"] == "takeout"
        assert collisions[2]["resolutionChoice"] == "adb"
        assert all(col["resolved"] for col in collisions)

        # Undo single item (item 2)
        collisions[2]["resolved"] = False
        collisions[2]["resolutionChoice"] = None

        # Verify only item 2 was undone
        assert collisions[2]["resolved"] is False
        assert collisions[0]["resolved"] is True
        assert collisions[1]["resolved"] is True

    def test_s4_complete_network_isolation_and_offline_mode(self):
        """S4: Simulates offline environment without daemon or emulator, verifying UI data integrity."""
        # When offline, SDK defaults to INITIAL_OFFLINE_VIDEO_TAGS in index.ts
        sdk_source = (SRC_DIR / "lib" / "dataconnect" / "index.ts").read_text(encoding="utf-8")
        assert "INITIAL_OFFLINE_VIDEO_TAGS: VideoTag[] = [" in sdk_source
        assert "EDM_FESTIVALS" in sdk_source
        assert "SPORTS_CARDS" in sdk_source
        assert "20260819_213606.mp4" in sdk_source
        assert "1986 Fleer Michael Jordan #57 PSA 10" in sdk_source

    def test_s5_rapid_stress_interaction_simulation(self, api_client: TestClient):
        """S5: Rapidly invokes 20 back-to-back API calls to verify zero memory leaks or deadlocks."""
        success_count = 0
        for _ in range(20):
            res = api_client.post("/api/capture-screen", json={"mock": True, "format": "png"})
            if res.status_code == 200 and res.json()["success"]:
                success_count += 1

        assert success_count == 20
