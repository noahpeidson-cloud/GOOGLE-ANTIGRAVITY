"""
test_challenger_1_m4_empirical.py - Empirical Adversarial Verification Suite for Milestone 4
Author: Challenger 1 (teamwork_preview_challenger)
Target Scope: Milestone 4 (Wireless Samsung Ingestion & Zero-Touch Remote Trigger)

Verifies acceptance criteria:
1. Zeroconf import and dynamic IP resolution in samsung_ingest.py (RFC 6762 / 6763 mDNS auto-discovery).
2. FastAPI application non-blocking async execution in remote_trigger.py (asyncio subprocess, mutex locking, telemetry, health, logs, cancel).
3. Tasker XML matching HTTP Request action parameters in tasker_profile.md.
4. End-to-end integration and adversarial boundary conditions across all Milestone 4 deliverables.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import xml.etree.ElementTree as ET

from fastapi import status
from fastapi.testclient import TestClient

MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import config
from remote_trigger import (
    CancelResponse,
    ConflictResponse,
    HealthResponse,
    JobRecord,
    JobState,
    JobTelemetry,
    LogEntry,
    LogsResponse,
    PipelineJobManager,
    PipelineTriggerRequest,
    StatusResponse,
    TriggerResponse,
    build_orchestrator_command,
    create_app,
)
from samsung_ingest import (
    ADBClient,
    ADBDeviceInfo,
    ADBError,
    ADBMDNSDiscovery,
    ADBMDNSListener,
    ADBNotFoundError,
    DiscoveredADBService,
    NoDeviceConnectedError,
    SamsungADBIngestor,
    build_parser,
    extract_ip_address,
    parse_service_properties,
)


class TestZeroconfMDNSDynamicResolution(unittest.TestCase):
    """Empirical adversarial stress testing for Zeroconf mDNS dynamic resolution in samsung_ingest.py."""

    def test_zeroconf_constants_in_config(self):
        """Verifies required mDNS constants are defined in config.py."""
        self.assertEqual(config.MDNS_ADB_TLS_SERVICE_TYPE, "_adb-tls-connect._tcp.local.")
        self.assertEqual(config.MDNS_ADB_LEGACY_SERVICE_TYPE, "_adb._tcp.local.")
        self.assertGreater(config.MDNS_DEFAULT_TIMEOUT_SEC, 0)
        self.assertIn("SM-S948", config.SAMSUNG_MODEL_PREFIXES)

    def test_extract_ip_address_various_formats(self):
        """Tests extract_ip_address against parsed_addresses, packed bytes, IPv6, and edge cases."""
        # 1. Mock info with parsed_addresses() method returning IPv4
        mock_info_1 = MagicMock()
        mock_info_1.parsed_addresses.return_value = ["192.168.1.185"]
        self.assertEqual(extract_ip_address(mock_info_1), "192.168.1.185")

        # 2. Mock info with parsed_addresses() returning loopback first, then valid IP
        mock_info_2 = MagicMock()
        mock_info_2.parsed_addresses.return_value = ["127.0.0.1", "10.0.0.50"]
        self.assertEqual(extract_ip_address(mock_info_2), "10.0.0.50")

        # 3. Mock info with raw 4-byte packed IPv4 address in info.addresses
        mock_info_3 = MagicMock(spec=["addresses"])
        mock_info_3.addresses = [socket.inet_aton("192.168.1.200")]
        self.assertEqual(extract_ip_address(mock_info_3), "192.168.1.200")

        # 4. Mock info with raw 16-byte packed IPv6 address in info.addresses
        mock_info_4 = MagicMock(spec=["addresses"])
        mock_info_4.addresses = [socket.inet_pton(socket.AF_INET6, "fe80::1")]
        self.assertEqual(extract_ip_address(mock_info_4), "fe80::1")

        # 5. Mock info with legacy info.address packed bytes attribute
        mock_info_5 = MagicMock(spec=["address"])
        mock_info_5.address = socket.inet_aton("192.168.1.210")
        self.assertEqual(extract_ip_address(mock_info_5), "192.168.1.210")

        # 6. Mock info with legacy info.address string attribute
        mock_info_6 = MagicMock(spec=["address"])
        mock_info_6.address = "192.168.1.220"
        self.assertEqual(extract_ip_address(mock_info_6), "192.168.1.220")

        # 7. Mock info with empty addresses / None
        mock_info_7 = MagicMock(spec=[])
        self.assertIsNone(extract_ip_address(mock_info_7))

    def test_parse_service_properties_decoding(self):
        """Tests binary TXT record decoding into string dictionaries."""
        mock_info = MagicMock()
        mock_info.properties = {
            b"model": b"SM-S948U",
            b"serial": b"R5CX10ABCDE",
            b"version": b"Android 16",
            b"flag": None,
        }
        props = parse_service_properties(mock_info)
        self.assertEqual(props["model"], "SM-S948U")
        self.assertEqual(props["serial"], "R5CX10ABCDE")
        self.assertEqual(props["version"], "Android 16")
        self.assertEqual(props["flag"], "")

    def test_discovered_adb_service_model_and_flags(self):
        """Tests DiscoveredADBService model classification and flagship detection."""
        s26_svc = DiscoveredADBService(
            name="adb-SM-S948U-001._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            ip_address="192.168.1.111",
            port=38472,
            properties={"model": "SM-S948U", "serial": "R5CX10S26U"},
        )
        self.assertEqual(s26_svc.endpoint, "192.168.1.111:38472")
        self.assertEqual(s26_svc.model, "SM-S948U")
        self.assertTrue(s26_svc.is_samsung)
        self.assertTrue(s26_svc.is_s26_ultra)

        s24_svc = DiscoveredADBService(
            name="adb-SM-S928B-002._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            ip_address="192.168.1.112",
            port=38473,
            properties={"model": "SM-S928B", "serial": "R5CX10S24U"},
        )
        self.assertTrue(s24_svc.is_samsung)
        self.assertFalse(s24_svc.is_s26_ultra)

        pixel_svc = DiscoveredADBService(
            name="adb-Pixel9-003._adb._tcp.local.",
            service_type="_adb._tcp.local.",
            ip_address="192.168.1.113",
            port=5555,
            properties={"model": "Pixel 9 Pro"},
        )
        self.assertFalse(pixel_svc.is_samsung)
        self.assertFalse(pixel_svc.is_s26_ultra)

    @patch("samsung_ingest.ADBMDNSDiscovery.discover_services")
    def test_find_target_device_priority_hierarchy(self, mock_discover):
        """Stress-tests multi-device priority hierarchy in ADBMDNSDiscovery."""
        discovery = ADBMDNSDiscovery(timeout_sec=1.0)

        s26 = DiscoveredADBService("s26._adb-tls-connect._tcp.local.", "_adb-tls-connect._tcp.local.", "192.168.1.10", 4001, properties={"model": "SM-S948U"})
        s24 = DiscoveredADBService("s24._adb-tls-connect._tcp.local.", "_adb-tls-connect._tcp.local.", "192.168.1.11", 4002, properties={"model": "SM-S928B"})
        pixel = DiscoveredADBService("pixel._adb._tcp.local.", "_adb._tcp.local.", "192.168.1.12", 5555, properties={"model": "Pixel 9 Pro"})

        # Case 1: Multiple devices -> prioritizes S26 Ultra
        mock_discover.return_value = [pixel, s24, s26]
        target = discovery.find_target_device()
        self.assertIsNotNone(target)
        self.assertEqual(target.endpoint, "192.168.1.10:4001")

        # Case 2: Exact serial request
        target_serial = discovery.find_target_device(preferred_serial="s24")
        self.assertIsNotNone(target_serial)
        self.assertEqual(target_serial.endpoint, "192.168.1.11:4002")

        # Case 3: No S26 Ultra -> prioritizes Samsung over generic Android
        mock_discover.return_value = [pixel, s24]
        target_samsung = discovery.find_target_device()
        self.assertIsNotNone(target_samsung)
        self.assertEqual(target_samsung.endpoint, "192.168.1.11:4002")

        # Case 4: Only generic Android
        mock_discover.return_value = [pixel]
        target_pixel = discovery.find_target_device()
        self.assertIsNotNone(target_pixel)
        self.assertEqual(target_pixel.endpoint, "192.168.1.12:5555")

        # Case 5: Empty scan -> returns None
        mock_discover.return_value = []
        self.assertIsNone(discovery.find_target_device())

    @patch("samsung_ingest.find_adb_binary")
    @patch("samsung_ingest.ADBClient.run_cmd")
    def test_samsung_ingestor_4_tier_fallback(self, mock_run_cmd, mock_find_adb):
        """Tests SamsungADBIngestor device resolution across all 4 fallback tiers."""
        temp_dir = tempfile.mkdtemp()
        try:
            mock_find_adb.return_value = Path("/usr/bin/adb")
            ingestor = SamsungADBIngestor(workspace_root=Path(temp_dir), enable_mdns=True)

            # Tier 1: Explicit connect_endpoint
            ingestor.connect_endpoint = "192.168.1.99:41234"
            mock_run_cmd.side_effect = [
                subprocess.CompletedProcess(args=[], returncode=0, stdout="connected to 192.168.1.99:41234\n", stderr=""),
                subprocess.CompletedProcess(args=[], returncode=0, stdout="List of devices attached\n192.168.1.99:41234 device model:SM-S948U\n", stderr=""),
            ]
            dev = ingestor.select_device()
            self.assertEqual(dev.serial, "192.168.1.99:41234")

            # Tier 2: mDNS Auto-Discovery
            ingestor.connect_endpoint = None
            with patch.object(ingestor.mdns_discovery, "find_target_device") as mock_find_target:
                mock_find_target.return_value = DiscoveredADBService("s26", "_adb-tls-connect._tcp.local.", "192.168.1.88", 43210, properties={"model": "SM-S948U"})
                mock_run_cmd.side_effect = [
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="connected to 192.168.1.88:43210\n", stderr=""),
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="List of devices attached\n192.168.1.88:43210 device model:SM-S948U\n", stderr=""),
                ]
                dev2 = ingestor.select_device()
                self.assertEqual(dev2.serial, "192.168.1.88:43210")

            # Tier 3: Fallback to attached USB device
            with patch.object(ingestor.mdns_discovery, "find_target_device", return_value=None):
                mock_run_cmd.side_effect = [
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="List of devices attached\nR5CX10USB device model:SM-S948U\n", stderr=""),
                ]
                dev3 = ingestor.select_device()
                self.assertEqual(dev3.serial, "R5CX10USB")

            # Tier 4: Actionable NoDeviceConnectedError
            with patch.object(ingestor.mdns_discovery, "find_target_device", return_value=None):
                mock_run_cmd.side_effect = [
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="List of devices attached\n\n", stderr=""),
                ]
                with self.assertRaises(NoDeviceConnectedError) as ctx:
                    ingestor.select_device()
                self.assertIn("No Android devices detected", str(ctx.exception))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_cli_parser_mdns_flags(self):
        """Verifies CLI parser supports --mdns, --auto-discover, --no-mdns, and --connect."""
        parser = build_parser()

        # Default: enable_mdns = True
        args_def = parser.parse_args([])
        self.assertTrue(args_def.enable_mdns)
        self.assertEqual(args_def.mdns_timeout, config.MDNS_DEFAULT_TIMEOUT_SEC)

        # --auto-discover flag alias
        args_ad = parser.parse_args(["--auto-discover", "--mdns-timeout", "8.5"])
        self.assertTrue(args_ad.enable_mdns)
        self.assertEqual(args_ad.mdns_timeout, 8.5)

        # --no-mdns flag
        args_no = parser.parse_args(["--no-mdns", "--connect", "192.168.1.55:5555"])
        self.assertFalse(args_no.enable_mdns)
        self.assertEqual(args_no.connect, "192.168.1.55:5555")


class TestFastAPIRemoteTriggerNonBlockingAsync(unittest.TestCase):
    """Empirical verification of FastAPI remote_trigger.py non-blocking async execution."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir).resolve()
        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("asyncio.create_subprocess_exec")
    def test_non_blocking_response_time_under_50ms(self, mock_exec):
        """Asserts POST /trigger-pipeline responds immediately (<50ms) with HTTP 202."""
        # Configure mock subprocess to simulate long-running background process
        fake_process = MagicMock()
        fake_process.stdout.readline = AsyncMock(side_effect=[b"Processing take 1\n", b""])
        fake_process.stderr.readline = AsyncMock(side_effect=[b""])
        fake_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = fake_process

        start_time = time.perf_counter()
        response = self.client.post(
            "/trigger-pipeline",
            json={
                "event": "EDC2026",
                "artist": "JohnSummit",
                "track": "WhereYouAre",
                "from_device": True,
                "auto_drop": True,
                "dry_run": True,
            },
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()
        self.assertEqual(data["status"], "accepted")
        self.assertTrue(data["job_id"].startswith("job_"))
        self.assertIn("orchestrator.py", " ".join(data["command"]))
        self.assertLess(elapsed_ms, 50.0, f"Trigger endpoint response took {elapsed_ms:.2f}ms, exceeding 50ms requirement")

    def test_mutex_concurrency_locking_returns_409(self):
        """Asserts second concurrent request returns HTTP 409 Conflict when a job is active."""
        manager: PipelineJobManager = self.app.state.job_manager
        active_job = JobRecord("job_active_lock_test", ["cmd"], {})
        active_job.state = JobState.RUNNING
        active_job.started_at = datetime.now(timezone.utc)
        manager._active_job = active_job

        response = self.client.post("/trigger-pipeline", json={"event": "SecondJob"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        data = response.json()
        self.assertEqual(data["status"], "conflict")
        self.assertEqual(data["current_job_id"], "job_active_lock_test")
        self.assertIn("already in progress", data["error"])

    def test_pydantic_validation_bounds(self):
        """Verifies Pydantic v2 rejects out-of-bound parameters with HTTP 422."""
        # drop_duration < 5.0
        res1 = self.client.post("/trigger-pipeline", json={"drop_duration": 4.0})
        self.assertEqual(res1.status_code, 422)

        # drop_duration > 59.0
        res2 = self.client.post("/trigger-pipeline", json={"drop_duration": 65.0})
        self.assertEqual(res2.status_code, 422)

        # duration > 59.0
        res3 = self.client.post("/trigger-pipeline", json={"duration": 70.0})
        self.assertEqual(res3.status_code, 422)

        # start_time < 0
        res4 = self.client.post("/trigger-pipeline", json={"start_time": -1.0})
        self.assertEqual(res4.status_code, 422)

    @patch("remote_trigger.find_binary")
    @patch("remote_trigger.find_adb_binary")
    def test_health_endpoint_states(self, mock_find_adb, mock_find_bin):
        """Verifies GET /health endpoint correctly evaluates healthy, degraded, and unhealthy states."""
        # 1. Healthy
        mock_find_adb.return_value = Path("/usr/bin/adb")
        mock_find_bin.side_effect = lambda name: Path(f"/usr/bin/{name}")
        res_h = self.client.get("/health")
        self.assertEqual(res_h.status_code, status.HTTP_200_OK)
        self.assertEqual(res_h.json()["status"], "healthy")

        # 2. Degraded (missing ADB)
        mock_find_adb.return_value = None
        mock_find_bin.side_effect = lambda name: None if name == "adb" else Path(f"/usr/bin/{name}")
        res_d = self.client.get("/health")
        self.assertEqual(res_d.status_code, status.HTTP_200_OK)
        self.assertEqual(res_d.json()["status"], "degraded")

        # 3. Unhealthy 503 (missing FFmpeg)
        mock_find_bin.side_effect = lambda name: None if name == "ffmpeg" else Path(f"/usr/bin/{name}")
        res_u = self.client.get("/health")
        self.assertEqual(res_u.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(res_u.json()["status"], "unhealthy")

    def test_cancel_active_job_vs_idle(self):
        """Tests POST /cancel when idle (400) vs when running (200)."""
        # Idle -> 400
        res_idle = self.client.post("/cancel")
        self.assertEqual(res_idle.status_code, status.HTTP_400_BAD_REQUEST)

        # Running -> 200
        manager: PipelineJobManager = self.app.state.job_manager
        active_job = JobRecord("job_to_cancel", ["proc"], {})
        active_job.state = JobState.RUNNING
        active_job.started_at = datetime.now(timezone.utc)
        manager._active_job = active_job

        mock_proc = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = AsyncMock(return_value=-15)
        mock_proc.returncode = -15
        manager._active_process = mock_proc

        res_cancel = self.client.post("/cancel")
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(res_cancel.json()["status"], "cancelled")
        self.assertEqual(res_cancel.json()["job_id"], "job_to_cancel")


class TestTaskerProfileParityAndXMLValidity(unittest.TestCase):
    """Empirical verification of Tasker XML and schema contract in tasker_profile.md."""

    def setUp(self):
        self.doc_path = MODULE_DIR / "tasker_profile.md"
        self.assertTrue(self.doc_path.is_file(), f"tasker_profile.md not found at {self.doc_path}")
        self.content = self.doc_path.read_text(encoding="utf-8")

    def test_tasker_xml_parses_and_has_required_actions(self):
        """Verifies XML blocks parse with ElementTree and contain the complete action sequence."""
        xml_blocks = re.findall(r"```xml\s*(<TaskerData[\s\S]*?</TaskerData>)\s*```", self.content)
        self.assertGreaterEqual(len(xml_blocks), 2, "tasker_profile.md must contain at least 2 Tasker XML blocks")

        task_xml = ET.fromstring(xml_blocks[0])
        self.assertEqual(task_xml.tag, "TaskerData")
        self.assertEqual(task_xml.attrib.get("tv"), "6.3.13")

        task = task_xml.find("Task")
        self.assertIsNotNone(task)
        self.assertEqual(task.find("nme").text, "Trigger_EDM_Pipeline")

        actions = task.findall("Action")
        self.assertEqual(len(actions), 11)

        # Action 2: HTTP Request Action Code 339
        act2 = actions[2]
        self.assertEqual(act2.find("code").text, "339")
        self.assertEqual(act2.find("Int[@sr='arg0']").attrib.get("val"), "1")  # Method 1 = POST
        self.assertEqual(act2.find("Str[@sr='arg1']").text, "http://%EDM_SERVER_IP:%EDM_SERVER_PORT/trigger-pipeline")

        headers = act2.find("Str[@sr='arg2']").text
        self.assertIn("Content-Type:application/json", headers)

        body = json.loads(act2.find("Str[@sr='arg4']").text)
        self.assertTrue(body.get("from_device"))
        self.assertTrue(body.get("auto_drop"))

        # Pydantic schema validation of Tasker payload
        req = PipelineTriggerRequest(**body)
        self.assertTrue(req.from_device)
        self.assertTrue(req.auto_drop)

        # Action 3: If %http_response_code eq 202
        act3 = actions[3]
        self.assertEqual(act3.find("code").text, "37")
        self.assertEqual(act3.find("ConditionList/Condition/lhs").text, "%http_response_code")
        self.assertEqual(act3.find("ConditionList/Condition/rhs").text, "202")

        # Action 4: Success haptic vibration pattern (0,100,100,100)
        act4 = actions[4]
        self.assertEqual(act4.find("code").text, "130")
        self.assertEqual(act4.find("Str[@sr='arg0']").text, "0,100,100,100")

        # Action 8: Error haptic vibration pattern (0,500,200,500)
        act8 = actions[8]
        self.assertEqual(act8.find("code").text, "130")
        self.assertEqual(act8.find("Str[@sr='arg0']").text, "0,500,200,500")


if __name__ == "__main__":
    unittest.main()
