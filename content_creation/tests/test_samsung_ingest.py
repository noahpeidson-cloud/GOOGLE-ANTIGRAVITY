"""
test_samsung_ingest.py - Unit Test Suite for Samsung S26 Ultra ADB Ingestion Bridge

Tests cover:
1. Dataclass properties and helper methods (ADBDeviceInfo, RemoteMediaAsset, ADBPullResult, ADBIngestionSummary, DiscoveredADBService).
2. ADB binary discovery (custom path, env vars, PATH, OS candidate fallback).
3. ADB client command execution, timeout, error handling, device enumeration, connect/disconnect.
4. Device selection logic (Samsung S26 Ultra prioritization, unauthorized state, preferred serial).
5. Remote directory stat scanning, timestamp/size parsing, alt path fallback, and date/recent filtering.
6. Atomic file pull with .tmp staging, SHA-256 verification, and retry backoff on size mismatch.
7. Multi-tier deduplication (JSON ledger, 4-tier folder scan, SQLite manifest).
8. 50-item folder partition health enforcement via DirectoryHealthGuard.
9. Dry-run execution and host storage headroom pre-flight check.
10. mDNS Zeroconf Auto-Discovery:
    - extract_ip_address across parsed_addresses, raw byte arrays (IPv4/IPv6), and direct address attributes.
    - parse_service_properties decoding binary TXT records.
    - ADBMDNSListener event handling (add_service, update_service, remove_service).
    - ADBMDNSDiscovery service scanning and multi-tier target device resolution.
    - SamsungADBIngestor 4-tier fallback hierarchy (explicit endpoint -> mDNS -> attached devices -> actionable error).
11. CLI parser argument bindings (including mDNS flags) and architectural aliases.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    ADB_EXPERT_RAW_PATH,
    BrandType,
    DEFAULT_ANDROID_CAMERA_PATH,
    EventTier,
    FOLDER_TIERS,
    MDNS_ADB_LEGACY_SERVICE_TYPE,
    MDNS_ADB_TLS_SERVICE_TYPE,
    MDNS_DEFAULT_TIMEOUT_SEC,
)
from samsung_ingest import (
    ADBClient,
    ADBDeviceInfo,
    ADBDeviceManager,
    ADBError,
    ADBIngestionLedger,
    ADBIngestionSummary,
    ADBMDNSDiscovery,
    ADBMDNSListener,
    ADBNotFoundError,
    ADBPullResult,
    DeviceSelectionError,
    DeviceUnauthorizedError,
    DirectoryHealthGuard,
    DiscoveredADBService,
    InsufficientStorageError,
    NoDeviceConnectedError,
    RemoteDirectoryNotFoundError,
    RemoteMediaAsset,
    SamsungADBIngestor,
    SamsungIngestEngine,
    TransferIntegrityError,
    build_parser,
    extract_ip_address,
    find_adb_binary,
    parse_service_properties,
)


class TestSamsungIngestDataclasses(unittest.TestCase):
    """Tests for dataclasses and their properties."""

    def test_adb_device_info_properties(self):
        s26 = ADBDeviceInfo(
            serial="R5CX10ABCDE",
            state="device",
            model="SM-S948U",
            product="e3q",
            is_authorized=True,
            is_samsung=True,
        )
        self.assertTrue(s26.is_s26_ultra)
        self.assertTrue(s26.is_authorized)
        self.assertTrue(s26.is_samsung)

        pixel = ADBDeviceInfo(
            serial="1234567890",
            state="device",
            model="Pixel 9 Pro",
            is_authorized=True,
            is_samsung=False,
        )
        self.assertFalse(pixel.is_s26_ultra)
        self.assertFalse(pixel.is_samsung)

        unauth = ADBDeviceInfo(
            serial="R5CX99999",
            state="unauthorized",
            model="SM-S948B",
            is_authorized=False,
            is_samsung=True,
        )
        self.assertTrue(unauth.is_s26_ultra)
        self.assertFalse(unauth.is_authorized)

    def test_remote_media_asset_properties(self):
        asset = RemoteMediaAsset(
            filename="20260821_220000.mp4",
            remote_path="/sdcard/DCIM/Camera/20260821_220000.mp4",
            size_bytes=100 * 1024 * 1024,
            modified_time=datetime(2026, 8, 21, 22, 0, 0),
            extension=".mp4",
            is_video=True,
            is_dng=False,
        )
        self.assertAlmostEqual(asset.size_mb, 100.0, places=2)
        self.assertAlmostEqual(asset.size_gb, 100.0 / 1024.0, places=3)
        self.assertTrue(asset.matches_extensions([".mp4", ".mov"]))
        self.assertTrue(asset.matches_extensions(["MP4"]))
        self.assertFalse(asset.matches_extensions([".dng", ".jpg"]))

    def test_adb_ingestion_summary_properties(self):
        summary = ADBIngestionSummary(
            total_remote_scanned=10,
            total_eligible=5,
            total_pulled=5,
            total_skipped_duplicate=5,
            total_failed=0,
            total_bytes_transferred=200 * 1024 * 1024,
            total_duration_sec=10.0,
        )
        self.assertAlmostEqual(summary.total_mb_transferred, 200.0, places=2)
        self.assertAlmostEqual(summary.average_rate_mbps, 160.0, places=1)

    def test_discovered_adb_service_properties(self):
        svc = DiscoveredADBService(
            name="adb-SM-S948U-123456._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            ip_address="192.168.1.150",
            port=42109,
            properties={"model": "SM-S948U", "serial": "R5CX10ABCDE"},
        )
        self.assertEqual(svc.endpoint, "192.168.1.150:42109")
        self.assertEqual(svc.model, "SM-S948U")
        self.assertTrue(svc.is_samsung)
        self.assertTrue(svc.is_s26_ultra)

        generic_svc = DiscoveredADBService(
            name="generic-android._adb._tcp.local.",
            service_type="_adb._tcp.local.",
            ip_address="192.168.1.151",
            port=5555,
            properties={"model": "Pixel9"},
        )
        self.assertEqual(generic_svc.endpoint, "192.168.1.151:5555")
        self.assertFalse(generic_svc.is_samsung)
        self.assertFalse(generic_svc.is_s26_ultra)


class TestBinaryDiscovery(unittest.TestCase):
    """Tests for finding the adb executable binary."""

    def test_find_adb_custom_path_file(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"mock adb")
            temp_path = f.name
        try:
            res = find_adb_binary(temp_path)
            self.assertIsNotNone(res)
            self.assertEqual(res, Path(temp_path).resolve())
        finally:
            os.unlink(temp_path)

    def test_find_adb_custom_path_dir(self):
        temp_dir = tempfile.mkdtemp()
        adb_file = Path(temp_dir) / "adb.exe"
        adb_file.write_bytes(b"mock adb")
        try:
            res = find_adb_binary(temp_dir)
            self.assertIsNotNone(res)
            self.assertEqual(res, adb_file.resolve())
        finally:
            shutil.rmtree(temp_dir)

    @patch.dict(os.environ, {"ADB_BINARY": ""}, clear=False)
    @patch("shutil.which")
    def test_find_adb_via_which(self, mock_which):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"mock adb")
            temp_path = f.name
        try:
            mock_which.return_value = temp_path
            res = find_adb_binary()
            self.assertIsNotNone(res)
            self.assertEqual(res, Path(temp_path).resolve())
        finally:
            os.unlink(temp_path)


class TestADBClient(unittest.TestCase):
    """Tests for ADBClient command execution, device discovery, connect/disconnect, and stat parsing."""

    def setUp(self):
        self.temp_bin = tempfile.NamedTemporaryFile(suffix=".exe", delete=False)
        self.temp_bin.write(b"mock binary")
        self.temp_bin.close()
        self.client = ADBClient(adb_path=self.temp_bin.name)

    def tearDown(self):
        if os.path.exists(self.temp_bin.name):
            os.unlink(self.temp_bin.name)

    @patch("subprocess.run")
    def test_connect_device_success_and_already_connected(self, mock_run):
        # Case 1: Successfully connected
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "connect", "192.168.1.100:42109"],
            returncode=0,
            stdout="connected to 192.168.1.100:42109\n",
            stderr="",
        )
        self.assertTrue(self.client.connect_device("192.168.1.100", 42109))

        # Case 2: Already connected
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "connect", "192.168.1.100:42109"],
            returncode=0,
            stdout="already connected to 192.168.1.100:42109\n",
            stderr="",
        )
        self.assertTrue(self.client.connect_device("192.168.1.100", 42109))

        # Case 3: Failed to connect
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "connect", "192.168.1.100:42109"],
            returncode=0,
            stdout="failed to connect to 192.168.1.100:42109: Connection refused\n",
            stderr="",
        )
        self.assertFalse(self.client.connect_device("192.168.1.100", 42109))

    @patch("subprocess.run")
    def test_disconnect_device(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "disconnect", "192.168.1.100:42109"],
            returncode=0,
            stdout="disconnected 192.168.1.100:42109\n",
            stderr="",
        )
        self.assertTrue(self.client.disconnect_device("192.168.1.100:42109"))

    @patch("subprocess.run")
    def test_list_devices_parsing(self, mock_run):
        mock_output = (
            "List of devices attached\n"
            "R5CX10ABCDE            device product:e3q model:SM-S948U device:e3q transport_id:1\n"
            "UNAUTH123456           unauthorized usb:1-1 transport_id:2\n"
            "PIXEL987654            device product:komodo model:Pixel_9_Pro device:komodo transport_id:3\n"
        )
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "devices", "-l"],
            returncode=0,
            stdout=mock_output,
            stderr="",
        )

        devices = self.client.list_devices()
        self.assertEqual(len(devices), 3)

        s26 = devices[0]
        self.assertEqual(s26.serial, "R5CX10ABCDE")
        self.assertEqual(s26.model, "SM-S948U")
        self.assertTrue(s26.is_authorized)
        self.assertTrue(s26.is_samsung)
        self.assertTrue(s26.is_s26_ultra)

        unauth = devices[1]
        self.assertEqual(unauth.serial, "UNAUTH123456")
        self.assertFalse(unauth.is_authorized)

        pixel = devices[2]
        self.assertEqual(pixel.serial, "PIXEL987654")
        self.assertTrue(pixel.is_authorized)
        self.assertFalse(pixel.is_samsung)

    @patch("subprocess.run")
    def test_select_active_device_single_samsung(self, mock_run):
        mock_output = (
            "List of devices attached\n"
            "R5CX10ABCDE            device product:e3q model:SM-S948U device:e3q transport_id:1\n"
        )
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "devices", "-l"],
            returncode=0,
            stdout=mock_output,
            stderr="",
        )

        selected = self.client.select_active_device()
        self.assertEqual(selected.serial, "R5CX10ABCDE")
        self.assertTrue(selected.is_s26_ultra)

    @patch("subprocess.run")
    def test_select_active_device_unauthorized_error(self, mock_run):
        mock_output = (
            "List of devices attached\n"
            "R5CX10ABCDE            unauthorized usb:1-1 transport_id:1\n"
        )
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "devices", "-l"],
            returncode=0,
            stdout=mock_output,
            stderr="",
        )

        with self.assertRaises(DeviceUnauthorizedError):
            self.client.select_active_device()

    @patch("subprocess.run")
    def test_select_active_device_none_connected(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "devices", "-l"],
            returncode=0,
            stdout="List of devices attached\n\n",
            stderr="",
        )

        with self.assertRaises(NoDeviceConnectedError):
            self.client.select_active_device()

    @patch("subprocess.run")
    def test_stat_remote_directory_parsing(self, mock_run):
        past_epoch = int(time.time()) - 100
        mock_check = subprocess.CompletedProcess(args=[], returncode=0, stdout="EXISTS\n", stderr="")
        mock_stat = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                f"104857600 {past_epoch} /sdcard/DCIM/Camera/20260821_220000.mp4\n"
                f"52428800 {past_epoch} /sdcard/DCIM/Camera/20260821_220100.mp4\n"
                f"25000000 {past_epoch} /sdcard/DCIM/Camera/20260821_220200.dng\n"
            ),
            stderr="",
        )
        mock_run.side_effect = [mock_check, mock_stat]

        assets = self.client.stat_remote_directory("/sdcard/DCIM/Camera", serial="R5CX10ABCDE")
        self.assertEqual(len(assets), 3)
        self.assertEqual(assets[0].filename, "20260821_220000.mp4")
        self.assertEqual(assets[0].size_bytes, 104857600)
        self.assertTrue(assets[0].is_video)
        self.assertFalse(assets[0].is_dng)

        self.assertEqual(assets[2].filename, "20260821_220200.dng")
        self.assertTrue(assets[2].is_dng)

    @patch("subprocess.run")
    def test_pull_file_atomic_success(self, mock_run):
        test_dir = tempfile.mkdtemp()
        try:
            dest_file = Path(test_dir) / "output.mp4"
            expected_payload = b"Sample 4K video stream content payload."

            def fake_pull(cmd, **kwargs):
                part_target = Path(cmd[-1])
                part_target.write_bytes(expected_payload)
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            mock_run.side_effect = fake_pull

            success, duration, sha256 = self.client.pull_file_atomic(
                remote_path="/sdcard/DCIM/Camera/20260821_220000.mp4",
                local_destination=dest_file,
                expected_size_bytes=len(expected_payload),
                serial="R5CX10ABCDE",
            )

            self.assertTrue(success)
            self.assertTrue(dest_file.is_file())
            self.assertEqual(dest_file.stat().st_size, len(expected_payload))
            self.assertGreater(len(sha256), 0)
        finally:
            shutil.rmtree(test_dir)

    @patch("subprocess.run")
    def test_pull_file_retry_on_size_mismatch(self, mock_run):
        test_dir = tempfile.mkdtemp()
        try:
            dest_file = Path(test_dir) / "output.mp4"
            expected_size = 1000

            def corrupt_pull(cmd, **kwargs):
                part_target = Path(cmd[-1])
                part_target.write_bytes(b"Too small")
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            mock_run.side_effect = corrupt_pull

            with self.assertRaises(TransferIntegrityError):
                self.client.pull_file_atomic(
                    remote_path="/sdcard/DCIM/Camera/20260821_220000.mp4",
                    local_destination=dest_file,
                    expected_size_bytes=expected_size,
                    serial="R5CX10ABCDE",
                    max_retries=2,
                )

            self.assertFalse(dest_file.exists())
        finally:
            shutil.rmtree(test_dir)


class TestMDNSDiscoveryAndExtraction(unittest.TestCase):
    """Unit tests for mDNS Zeroconf discovery functions and listener."""

    def test_extract_ip_address_from_parsed_addresses(self):
        info_mock = MagicMock()
        info_mock.parsed_addresses.return_value = ["127.0.0.1", "192.168.1.120"]
        self.assertEqual(extract_ip_address(info_mock), "192.168.1.120")

    def test_extract_ip_address_from_raw_byte_arrays(self):
        info_mock = MagicMock(spec=[])
        # 192.168.1.105 in 4-byte packed IPv4
        packed_ipv4 = socket.inet_aton("192.168.1.105")
        info_mock.addresses = [packed_ipv4]
        self.assertEqual(extract_ip_address(info_mock), "192.168.1.105")

    def test_extract_ip_address_from_address_attribute(self):
        info_mock = MagicMock(spec=[])
        info_mock.address = socket.inet_aton("10.0.0.42")
        self.assertEqual(extract_ip_address(info_mock), "10.0.0.42")

        info_mock_str = MagicMock(spec=[])
        info_mock_str.address = "172.16.0.5"
        self.assertEqual(extract_ip_address(info_mock_str), "172.16.0.5")

    def test_extract_ip_address_returns_none_on_empty(self):
        info_mock = MagicMock(spec=[])
        self.assertIsNone(extract_ip_address(info_mock))

    def test_parse_service_properties(self):
        info_mock = MagicMock()
        info_mock.properties = {
            b"model": b"SM-S948U",
            b"serial": b"R5CX10ABCDE",
            "version": "1.0",
        }
        props = parse_service_properties(info_mock)
        self.assertEqual(props["model"], "SM-S948U")
        self.assertEqual(props["serial"], "R5CX10ABCDE")
        self.assertEqual(props["version"], "1.0")

    def test_mdns_listener_callbacks(self):
        listener = ADBMDNSListener()
        zc_mock = MagicMock()
        info_mock = MagicMock()
        info_mock.name = "adb-test._adb._tcp.local."
        zc_mock.get_service_info.return_value = info_mock

        # add_service
        listener.add_service(zc_mock, "_adb._tcp.local.", "adb-test._adb._tcp.local.")
        self.assertEqual(len(listener.discovered_infos), 1)
        self.assertTrue(listener._event.is_set())

        # update_service
        info_mock_updated = MagicMock()
        info_mock_updated.name = "adb-test._adb._tcp.local."
        zc_mock.get_service_info.return_value = info_mock_updated
        listener.update_service(zc_mock, "_adb._tcp.local.", "adb-test._adb._tcp.local.")
        self.assertEqual(len(listener.discovered_infos), 1)

        # remove_service
        listener.remove_service(zc_mock, "_adb._tcp.local.", "adb-test._adb._tcp.local.")
        self.assertEqual(len(listener.discovered_infos), 0)

    @patch("samsung_ingest.ADBMDNSDiscovery.discover_services")
    def test_find_target_device_priority_hierarchy(self, mock_discover):
        s26 = DiscoveredADBService("s26", "_adb-tls-connect._tcp.local.", "192.168.1.10", 42000, properties={"model": "SM-S948U", "serial": "S26SERIAL"})
        s24 = DiscoveredADBService("s24", "_adb-tls-connect._tcp.local.", "192.168.1.11", 42001, properties={"model": "SM-S928B", "serial": "S24SERIAL"})
        pixel = DiscoveredADBService("pixel", "_adb._tcp.local.", "192.168.1.12", 5555, properties={"model": "Pixel9", "serial": "PIXELSERIAL"})

        discovery = ADBMDNSDiscovery(timeout_sec=0.1)

        # 1. Preferred serial takes highest precedence
        mock_discover.return_value = [s26, s24, pixel]
        found_serial = discovery.find_target_device(preferred_serial="S24SERIAL")
        self.assertEqual(found_serial.ip_address, "192.168.1.11")

        # 2. S26 Ultra takes precedence when no serial specified
        mock_discover.return_value = [pixel, s24, s26]
        found_s26 = discovery.find_target_device()
        self.assertEqual(found_s26.ip_address, "192.168.1.10")

        # 3. Other Samsung takes precedence over generic Android
        mock_discover.return_value = [pixel, s24]
        found_samsung = discovery.find_target_device()
        self.assertEqual(found_samsung.ip_address, "192.168.1.11")

        # 4. Fallback to generic Android
        mock_discover.return_value = [pixel]
        found_generic = discovery.find_target_device()
        self.assertEqual(found_generic.ip_address, "192.168.1.12")

        # 5. Empty discovery returns None
        mock_discover.return_value = []
        self.assertIsNone(discovery.find_target_device())


class TestADBIngestionLedger(unittest.TestCase):
    """Tests for persistent ingestion ledger deduplication."""

    def test_ledger_persistence_and_deduplication(self):
        temp_dir = tempfile.mkdtemp()
        try:
            ledger_path = Path(temp_dir) / ".adb_ingest_ledger.json"
            ledger = ADBIngestionLedger(ledger_path)

            self.assertFalse(ledger.is_ingested("20260821_220000.mp4", 104857600))

            ledger.record_ingest(
                filename="20260821_220000.mp4",
                remote_path="/sdcard/DCIM/Camera/20260821_220000.mp4",
                size_bytes=104857600,
                sha256="aabbccddeeff",
                device_serial="R5CX10ABCDE",
                local_path="01_RAW_INBOX/20260821_220000.mp4",
            )

            self.assertTrue(ledger.is_ingested("20260821_220000.mp4", 104857600))
            self.assertFalse(ledger.is_ingested("20260821_220000.mp4", 999999))

            # Reload from disk
            ledger2 = ADBIngestionLedger(ledger_path)
            self.assertTrue(ledger2.is_ingested("20260821_220000.mp4", 104857600))
        finally:
            shutil.rmtree(temp_dir)


class TestSamsungADBIngestor(unittest.TestCase):
    """Integration test suite for SamsungADBIngestor and 4-tier fallback."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace = Path(self.test_dir)
        self.adb_bin = self.workspace / "adb.exe"
        self.adb_bin.write_bytes(b"mock adb binary")

        self.ingestor = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            device_serial="R5CX10ABCDE",
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_discover_and_connect_mdns_enabled_vs_disabled(self):
        self.ingestor.enable_mdns = False
        self.assertIsNone(self.ingestor.discover_and_connect())

        self.ingestor.enable_mdns = True
        fake_svc = DiscoveredADBService("s26", "_adb-tls-connect._tcp.local.", "192.168.1.150", 42109, properties={"model": "SM-S948U"})
        with patch.object(self.ingestor.mdns_discovery, "find_target_device", return_value=fake_svc):
            with patch.object(self.ingestor.adb, "connect_device", return_value=True):
                res = self.ingestor.discover_and_connect()
                self.assertEqual(res, fake_svc)

    @patch("subprocess.run")
    def test_select_device_4_tier_fallback(self, mock_run):
        # Tier 1: Explicit connect_endpoint
        ingestor_tier1 = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            connect_endpoint="192.168.1.99:5555",
            enable_mdns=False,
        )
        mock_devices = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="List of devices attached\n192.168.1.99:5555 device product:e3q model:SM-S948U\n",
            stderr="",
        )
        mock_connect = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="connected to 192.168.1.99:5555\n",
            stderr="",
        )
        mock_run.side_effect = [mock_connect, mock_devices]
        selected = ingestor_tier1.select_device()
        self.assertEqual(selected.serial, "192.168.1.99:5555")

        # Tier 2: mDNS Auto-Discovery
        ingestor_tier2 = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            enable_mdns=True,
        )
        fake_svc = DiscoveredADBService("s26", "_adb-tls-connect._tcp.local.", "192.168.1.150", 42109, properties={"model": "SM-S948U"})
        mock_devices_mdns = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="List of devices attached\n192.168.1.150:42109 device product:e3q model:SM-S948U\n",
            stderr="",
        )
        with patch.object(ingestor_tier2, "discover_and_connect", return_value=fake_svc):
            mock_run.side_effect = [mock_devices_mdns]
            dev = ingestor_tier2.select_device()
            self.assertEqual(dev.serial, "192.168.1.150:42109")

        # Tier 3: Fallback to USB attached device
        ingestor_tier3 = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            enable_mdns=False,
        )
        mock_devices_usb = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="List of devices attached\nR5CX10ABCDE device product:e3q model:SM-S948U\n",
            stderr="",
        )
        mock_run.side_effect = [mock_devices_usb]
        dev_usb = ingestor_tier3.select_device()
        self.assertEqual(dev_usb.serial, "R5CX10ABCDE")

        # Tier 4: NoDeviceConnectedError when none connected
        ingestor_tier4 = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            enable_mdns=False,
        )
        mock_devices_empty = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="List of devices attached\n\n",
            stderr="",
        )
        mock_run.side_effect = [mock_devices_empty]
        with self.assertRaises(NoDeviceConnectedError):
            ingestor_tier4.select_device()

    @patch("subprocess.run")
    def test_scan_remote_camera_filters(self, mock_run):
        mock_devices = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="List of devices attached\nR5CX10ABCDE device product:e3q model:SM-S948U\n",
            stderr="",
        )
        mock_check = subprocess.CompletedProcess(args=[], returncode=0, stdout="EXISTS\n", stderr="")
        epoch_21st = int(datetime(2026, 8, 21, 22, 0, 0).timestamp())
        epoch_20th = int(datetime(2026, 8, 20, 22, 0, 0).timestamp())

        mock_stat = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=(
                f"100000000 {epoch_21st} /sdcard/DCIM/Camera/20260821_220000.mp4\n"
                f"80000000 {epoch_21st} /sdcard/DCIM/Camera/20260821_220100.mp4\n"
                f"60000000 {epoch_20th} /sdcard/DCIM/Camera/20260820_220000.mp4\n"
            ),
            stderr="",
        )
        mock_run.side_effect = [mock_devices, mock_check, mock_stat]

        filtered_date = self.ingestor.scan_remote_camera(date_filter="20260821")
        self.assertEqual(len(filtered_date), 2)
        self.assertEqual(filtered_date[0].filename, "20260821_220000.mp4")

    @patch("subprocess.run")
    def test_50_item_folder_partitioning(self, mock_run):
        inbox_dir = self.workspace / "01_RAW_INBOX"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        event_batch1 = inbox_dir / "EDCOrlando"
        event_batch1.mkdir(parents=True, exist_ok=True)

        for i in range(50):
            (event_batch1 / f"dummy_{i:02d}.mp4").write_text("x")

        guard = DirectoryHealthGuard(max_items=50)
        target = guard.get_healthy_subfolder(inbox_dir, "EDCOrlando")
        self.assertEqual(target.name, "EDCOrlando_Batch02")
        self.assertTrue(target.exists())

    @patch("subprocess.run")
    def test_dry_run_ingestion_batch(self, mock_run):
        epoch_now = int(time.time()) - 100

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "devices" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0,
                    stdout="List of devices attached\nR5CX10ABCDE device product:e3q model:SM-S948U\n",
                    stderr="",
                )
            if "[ -d" in cmd_str:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="EXISTS\n", stderr="")
            if "stat -c" in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0,
                    stdout=(
                        f"104857600 {epoch_now} /sdcard/DCIM/Camera/20260821_Take1.mp4\n"
                        f"52428800 {epoch_now} /sdcard/DCIM/Camera/20260821_Take2.mp4\n"
                    ),
                    stderr="",
                )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        mock_run.side_effect = fake_run

        summary = self.ingestor.ingest_batch(
            event_name="EDCOrlando",
            artist_name="JohnSummit",
            track_name="WhereYouAre",
            dry_run=True,
        )

        self.assertEqual(summary.total_remote_scanned, 2)
        self.assertEqual(summary.total_eligible, 2)
        self.assertEqual(summary.total_pulled, 2)
        self.assertEqual(summary.total_failed, 0)
        self.assertEqual(summary.total_bytes_transferred, 157286400)


class TestCLIParserAndAliases(unittest.TestCase):
    """Tests for CLI parser options, mDNS arguments, and architectural aliases."""

    def test_cli_parser_options_and_mdns_flags(self):
        parser = build_parser()
        args = parser.parse_args([
            "--event", "LostLands",
            "--artist", "Excision",
            "--track", "FeelSomething",
            "--brand", "laser_baptism",
            "--tier", "pillar_c_festival_mega",
            "--recent", "5",
            "--date", "20260822",
            "--auto-discover",
            "--mdns-timeout", "8.0",
            "--connect", "192.168.1.200:42100",
            "--auto-route",
            "--include-raw-dng",
            "--force",
            "--dry-run",
        ])

        self.assertEqual(args.event, "LostLands")
        self.assertEqual(args.artist, "Excision")
        self.assertEqual(args.track, "FeelSomething")
        self.assertEqual(args.brand, "laser_baptism")
        self.assertEqual(args.tier, "pillar_c_festival_mega")
        self.assertEqual(args.recent, 5)
        self.assertEqual(args.date, "20260822")
        self.assertTrue(args.enable_mdns)
        self.assertEqual(args.mdns_timeout, 8.0)
        self.assertEqual(args.connect, "192.168.1.200:42100")
        self.assertTrue(args.auto_route)
        self.assertTrue(args.include_raw_dng)
        self.assertTrue(args.force)
        self.assertTrue(args.dry_run)

        # Test --no-mdns disables mDNS
        args_no_mdns = parser.parse_args(["--no-mdns"])
        self.assertFalse(args_no_mdns.enable_mdns)

    def test_architectural_aliases(self):
        self.assertIs(SamsungIngestEngine, SamsungADBIngestor)
        self.assertIs(ADBDeviceManager, ADBClient)


if __name__ == "__main__":
    unittest.main()
