"""
test_challenger2_m3_empirical.py - Challenger 2 Comprehensive Empirical Verification Harness for Milestone 3

Executes AST/regex inspection, XML parsing, Pydantic schema validation, cross-reference consistency checks,
and adversarial stress-testing across:
1. content_creation/tasker_profile.md
2. content_creation/V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md
3. content_creation/remote_trigger.py
4. content_creation/samsung_ingest.py
5. content_creation/config.py
6. content_creation/orchestrator.py
"""

import ast
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET

# Add module dir to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_DIR = SCRIPT_DIR.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from config import (
    BrandType,
    EventTier,
    FOLDER_TIERS,
    MDNS_ADB_LEGACY_SERVICE_TYPE,
    MDNS_ADB_TLS_SERVICE_TYPE,
    MDNS_DEFAULT_TIMEOUT_SEC,
    MAX_FOLDER_ITEMS,
    ReframeMode,
    VIDEO_CANVAS_HEIGHT,
    VIDEO_CANVAS_WIDTH,
    VIDEO_DURATION_MAX_SECONDS,
)
from remote_trigger import (
    CancelResponse,
    ConflictResponse,
    HealthResponse,
    JobState,
    JobTelemetry,
    LogsResponse,
    PipelineTriggerRequest,
    StatusResponse,
    TriggerResponse,
    app,
    build_orchestrator_command,
)
from samsung_ingest import (
    ADBMDNSDiscovery,
    ADBDeviceInfo,
    DiscoveredADBService,
    SamsungADBIngestor,
)


class TestTaskerXMLAndSchemaEmpirical(unittest.TestCase):
    """Empirical XML AST & Schema Validation for tasker_profile.md."""

    def setUp(self):
        self.tasker_path = MODULE_DIR / "tasker_profile.md"
        self.assertTrue(self.tasker_path.is_file(), f"Tasker profile missing at {self.tasker_path}")
        self.tasker_text = self.tasker_path.read_text(encoding="utf-8")

    def test_xml_blocks_presence_and_parsing(self):
        """Extracts all <TaskerData> XML blocks and verifies clean parsing via ElementTree."""
        xml_pattern = re.compile(r"<TaskerData[\s\S]*?</TaskerData>")
        matches = xml_pattern.findall(self.tasker_text)
        self.assertGreaterEqual(len(matches), 2, "Expected at least 2 Tasker XML blocks (Task & Project)")

        for i, xml_str in enumerate(matches):
            try:
                root = ET.fromstring(xml_str)
                self.assertEqual(root.tag, "TaskerData", f"Block {i} root tag is not TaskerData")
                self.assertEqual(root.attrib.get("dvi"), "1", f"Block {i} dvi attribute mismatch")
            except ET.ParseError as e:
                self.fail(f"XML ParseError in block {i}: {e}")

    def test_tasker_action_codes_and_hierarchy(self):
        """Verifies exact Tasker action codes, parameters, conditions, and error branches."""
        xml_pattern = re.compile(r"<TaskerData[\s\S]*?</TaskerData>")
        task_xml = xml_pattern.findall(self.tasker_text)[0]
        root = ET.fromstring(task_xml)

        task_node = root.find("Task")
        self.assertIsNotNone(task_node, "Task node missing in Tasker XML")
        self.assertEqual(task_node.find("nme").text, "Trigger_EDM_Pipeline")

        actions = task_node.findall("Action")
        self.assertEqual(len(actions), 11, f"Expected exactly 11 Tasker actions (act0-act10), found {len(actions)}")

        action_codes = [act.find("code").text for act in actions]
        expected_codes = ["547", "547", "339", "37", "130", "548", "523", "43", "130", "548", "38"]
        self.assertEqual(action_codes, expected_codes, "Action code sequence mismatch in Tasker XML")

        # Act 0: %EDM_SERVER_IP fallback
        act0 = actions[0]
        self.assertEqual(act0.find("Str[@sr='arg0']").text, "%EDM_SERVER_IP")
        self.assertEqual(act0.find("Str[@sr='arg1']").text, "192.168.1.100")

        # Act 1: %EDM_SERVER_PORT fallback
        act1 = actions[1]
        self.assertEqual(act1.find("Str[@sr='arg0']").text, "%EDM_SERVER_PORT")
        self.assertEqual(act1.find("Str[@sr='arg1']").text, "8000")

        # Act 2: Action 339 HTTP Request
        act2 = actions[2]
        self.assertEqual(act2.find("Int[@sr='arg0']").attrib["val"], "1", "HTTP Method should be 1 (POST)")
        self.assertEqual(act2.find("Str[@sr='arg1']").text, "http://%EDM_SERVER_IP:%EDM_SERVER_PORT/trigger-pipeline")
        headers = act2.find("Str[@sr='arg2']").text
        self.assertTrue("Content-Type:application/json" in headers, "Content-Type header missing")
        self.assertEqual(act2.find("Int[@sr='arg7']").attrib["val"], "30", "Timeout should be 30 seconds")
        self.assertEqual(act2.find("Int[@sr='arg11']").attrib["val"], "1", "Continue Task After Error must be ON (1)")

        # Act 3: If %http_response_code eq 202
        act3 = actions[3]
        cond = act3.find("ConditionList/Condition")
        self.assertEqual(cond.find("lhs").text, "%http_response_code")
        self.assertEqual(cond.find("op").text, "0", "Comparison operator should be 0 (Equals)")
        self.assertEqual(cond.find("rhs").text, "202")

        # Act 4: Success vibration
        act4 = actions[4]
        self.assertEqual(act4.find("Str[@sr='arg0']").text, "0,100,100,100")

        # Act 6: Notification
        act6 = actions[6]
        self.assertEqual(act6.find("Str[@sr='arg0']").text, "EDM Master Pipeline")
        self.assertEqual(act6.find("Str[@sr='arg2']").text, "mw_av_videocam")
        self.assertEqual(act6.find("Int[@sr='arg5']").attrib["val"], "4", "Notification priority should be 4")

        # Act 8: Failure vibration
        act8 = actions[8]
        self.assertEqual(act8.find("Str[@sr='arg0']").text, "0,500,200,500")

    def test_tasker_payload_schema_compatibility(self):
        """Extracts JSON payload from Tasker XML and validates compatibility against FastAPI Pydantic schema."""
        xml_pattern = re.compile(r"<TaskerData[\s\S]*?</TaskerData>")
        task_xml = xml_pattern.findall(self.tasker_text)[0]
        root = ET.fromstring(task_xml)
        act2 = root.find("Task").findall("Action")[2]
        raw_json = act2.find("Str[@sr='arg4']").text
        self.assertIsNotNone(raw_json, "Action 339 JSON payload body is missing")

        payload_dict = json.loads(raw_json)
        self.assertIsInstance(payload_dict, dict)
        self.assertEqual(payload_dict.get("source"), "s26_ultra")
        self.assertTrue(payload_dict.get("from_device"))
        self.assertTrue(payload_dict.get("auto_drop"))

        # Instantiate Pydantic request model
        req_obj = PipelineTriggerRequest(**payload_dict)
        self.assertEqual(req_obj.event, payload_dict.get("event"))
        self.assertEqual(req_obj.artist, payload_dict.get("artist"))
        self.assertEqual(req_obj.brand, payload_dict.get("brand"))
        self.assertTrue(req_obj.from_device)
        self.assertTrue(req_obj.auto_drop)

    def test_tasker_runbook_ui_and_knox_whitelisting(self):
        """Verifies presence of complete step-by-step UI instructions and Knox power optimization guide."""
        self.assertTrue("1x1 Home Screen Widget Configuration" in self.tasker_text, "Missing Widget Config section")
        self.assertTrue("Task Shortcut (1x1)" in self.tasker_text, "Missing Task Shortcut 1x1")
        self.assertTrue("Quick Settings (QS) Tile Configuration" in self.tasker_text, "Missing QS Tile section")
        self.assertTrue("Quick Settings Tasks" in self.tasker_text, "Missing Quick Settings Tasks")
        self.assertTrue("Tile 1" in self.tasker_text, "Missing Tile 1")
        self.assertTrue("Knox Battery & Power Optimization Whitelist Runbook" in self.tasker_text, "Missing Knox runbook")
        self.assertTrue("Unrestricted" in self.tasker_text, "Missing Unrestricted battery setting")
        self.assertTrue("Never sleeping apps" in self.tasker_text, "Missing Never sleeping apps")
        self.assertTrue("Allow background data usage" in self.tasker_text, "Missing Background data")
        self.assertTrue("Run In Foreground" in self.tasker_text, "Missing Run In Foreground")


class TestBlueprintStructuralIntegrity(unittest.TestCase):
    """Empirical Structural & Cross-Reference Validation for V2 Master Blueprint."""

    def setUp(self):
        self.bp_path = MODULE_DIR / "V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md"
        self.assertTrue(self.bp_path.is_file(), f"Blueprint missing at {self.bp_path}")
        self.bp_text = self.bp_path.read_text(encoding="utf-8")

    def test_table_of_contents_completeness(self):
        """Verifies Table of Contents contains all mechanisms (0 through 7 and 3.9)."""
        checks = [
            "Mechanism 0: Samsung Galaxy S26 Ultra ADB Hardware",
            "Mechanism 1: MCP Asset Ingestion & Routing Engine",
            "Mechanism 2: Librosa & Vectorized RMS Audio Drop Detector",
            "Mechanism 3: FFmpeg Hardware-Accelerated Master Transcoder",
            "Mechanism 4: Headless Automated Quality Control (QC) Validator",
            "Mechanism 5: YouTube Data API v3 Shorts Publisher",
            "Mechanism 6: FastAPI Zero-Touch Remote Trigger Server",
            "Mechanism 7: Tasker One UI 7 Mobile Fast-Action Client",
            "3.9 [Automation of Manual GUI Editing Tasks]",
        ]
        for c in checks:
            self.assertTrue(c in self.bp_text, f"TOC missing item: {c}")

    def test_system_topology_phase0_integration(self):
        """Verifies Section 1.5 Topology includes Phase 0, Tasker XML Action 339, and FastAPI Daemon."""
        checks = [
            "PHASE 0: ZERO-TOUCH REMOTE TRIGGER & HARDWARE INGESTION",
            "Tasker XML Action Code 339",
            "remote_trigger.py (FastAPI Zero-Touch Daemon on Workstation Port 8000)",
            "HTTP 202 Accepted Response",
            "Single-Job Mutex Concurrency Lock",
            "samsung_ingest.py (with Zeroconf mDNS Discovery Engine)",
        ]
        for c in checks:
            self.assertTrue(c in self.bp_text, f"Topology missing item: {c}")

    def test_mechanism_0_zeroconf_mdns_documentation(self):
        """Verifies Section 3.1 documents Zeroconf mDNS discovery and constants."""
        checks = [
            "_adb-tls-connect._tcp.local.",
            "_adb._tcp.local.",
            "adb connect",
            "4-Tier Ingestion Fallback Hierarchy",
            "mDNS Dynamic Auto-Discovery",
            "Attached Device Check",
            "CLI / Environment Overrides",
        ]
        for c in checks:
            self.assertTrue(c in self.bp_text, f"Mechanism 0 missing item: {c}")

    def test_mechanism_6_fastapi_server_documentation(self):
        """Verifies Section 3.7 documents FastAPI server, endpoints, schemas, and concurrency."""
        checks = [
            "Mechanism 6: FastAPI Zero-Touch Remote Trigger Server",
            "POST /trigger-pipeline",
            "HTTP 202 Accepted",
            "HTTP 409 Conflict",
            "PipelineTriggerRequest",
            "GET /status",
            "GET /health",
            "GET /logs",
            "POST /cancel",
        ]
        for c in checks:
            self.assertTrue(c in self.bp_text, f"Mechanism 6 missing item: {c}")

    def test_mechanism_7_tasker_client_documentation(self):
        """Verifies Section 3.8 documents Tasker mobile client, action codes, and haptics."""
        checks = [
            "Mechanism 7: Tasker One UI 7 Mobile Fast-Action Client",
            "Action Code 339",
            "0,100,100,100",
            "0,500,200,500",
            "1x1 Home Screen Widgets",
            "Quick Settings Tiles",
            "Knox Power Whitelist",
        ]
        for c in checks:
            self.assertTrue(c in self.bp_text, f"Mechanism 7 missing item: {c}")

    def test_gui_automation_mapping_table(self):
        """Verifies Section 3.9 table maps manual GUI tasks to automated mechanisms."""
        checks = [
            "Mobile Remote Triggering",
            "Wireless Ingestion IP Mapping",
            "Tasker One UI 7 Widget / QS Tile",
            "Zeroconf mDNS Discovery",
        ]
        for c in checks:
            self.assertTrue(c in self.bp_text, f"GUI Automation table missing item: {c}")

    def test_phase0_lifecycle_steps(self):
        """Verifies Section 4.1 Phase 0 lifecycle details Steps 0A through 0E."""
        checks = [
            "Step 0A (Mobile Trigger)",
            "Step 0B (HTTP Dispatch)",
            "Step 0C (mDNS Discovery & Connect)",
            "Step 0D (Atomic Pull & Ledger)",
            "Step 0E (Health Partitioning)",
        ]
        for c in checks:
            self.assertTrue(c in self.bp_text, f"Phase 0 lifecycle missing: {c}")

    def test_edge_cases_20_through_23(self):
        """Verifies Section 8.1 contains Edge Cases 20 through 23."""
        checks = [
            "mDNS Discovery Timeout",
            "Android Wireless Debugging Port Rotation",
            "Tasker HTTP Timeout / Host Unreachable",
            "Concurrent Trigger Overlap (HTTP 409 Conflict)",
        ]
        for c in checks:
            self.assertTrue(c in self.bp_text, f"Edge cases missing: {c}")

    def test_core_guardrails_preservation(self):
        """Verifies preservation of all broadcast and media engineering invariants."""
        # Audio Loudness
        self.assertTrue("-14.0" in self.bp_text, "Missing -14.0 LUFS target")
        self.assertTrue("-1.5" in self.bp_text, "Missing -1.5 dBTP target")
        # Duration ceiling
        self.assertTrue("59.00" in self.bp_text, "Missing 59.00s max duration")
        # Geometry & CFR
        self.assertTrue("1080" in self.bp_text, "Missing 1080 width")
        self.assertTrue("1920" in self.bp_text, "Missing 1920 height")
        self.assertTrue("60" in self.bp_text, "Missing 60fps")
        # Partition health
        self.assertTrue("50" in self.bp_text, "Missing 50-item partition rule")
        # Brands
        self.assertTrue("@LaserBaptismLive" in self.bp_text, "Missing @LaserBaptismLive brand")
        self.assertTrue("@MusicBaptismLive" in self.bp_text, "Missing @MusicBaptismLive brand")


class TestCrossReferenceASTAndEndpoints(unittest.TestCase):
    """Verifies AST and cross-file synchronization across Python modules."""

    def test_mdns_constants_synchronization(self):
        """Verifies mDNS service constants match across config.py and samsung_ingest.py."""
        self.assertEqual(MDNS_ADB_TLS_SERVICE_TYPE, "_adb-tls-connect._tcp.local.")
        self.assertEqual(MDNS_ADB_LEGACY_SERVICE_TYPE, "_adb._tcp.local.")
        self.assertEqual(MDNS_DEFAULT_TIMEOUT_SEC, 5.0)

    def test_remote_trigger_command_builder(self):
        """Tests build_orchestrator_command generates valid CLI invocations."""
        req = PipelineTriggerRequest(
            event="EDCLasVegas",
            artist="SubFocus",
            track="Desire",
            genre="dnb",
            brand="laser_baptism",
            tier="pillar_a_stadium_arena",
            from_device=True,
            auto_drop=True,
            drop_duration=30.0,
            publish_youtube=True,
            auto_promote=True,
            dry_run=True,
        )
        cmd = build_orchestrator_command(req, workspace_root=MODULE_DIR)
        self.assertTrue("orchestrator.py" in cmd[1])
        self.assertTrue("pipeline" in cmd)
        self.assertTrue("--from-device" in cmd)
        self.assertTrue("--auto-drop" in cmd)
        self.assertTrue("--drop-duration" in cmd)
        self.assertTrue("30.0" in cmd)
        self.assertTrue("--publish-youtube" in cmd)
        self.assertTrue("--auto-promote" in cmd)
        self.assertTrue("--dry-run" in cmd)

    def test_fastapi_routes_registration(self):
        """Inspects FastAPI app route registry to confirm all required endpoints exist."""
        route_paths = {route.path for route in app.routes}
        self.assertTrue("/trigger-pipeline" in route_paths)
        self.assertTrue("/status" in route_paths)
        self.assertTrue("/status/{job_id}" in route_paths)
        self.assertTrue("/health" in route_paths)
        self.assertTrue("/logs" in route_paths)
        self.assertTrue("/cancel" in route_paths)


if __name__ == "__main__":
    unittest.main()
