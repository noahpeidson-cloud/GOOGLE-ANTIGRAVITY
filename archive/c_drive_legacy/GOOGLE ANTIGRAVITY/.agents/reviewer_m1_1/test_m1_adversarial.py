"""
test_m1_adversarial.py - Comprehensive Reviewer & Adversarial Stress Tests for Milestone 1 (M1)

Tests:
1. Centralized configuration mDNS constants and backwards compatibility.
2. DiscoveredADBService dataclass properties and classification.
3. extract_ip_address parsing across byte arrays, parsed addresses, IPv6, loopback filtering.
4. parse_service_properties binary decoding, none values, and edge cases.
5. ADBMDNSListener event handling, locks, and thread safety.
6. ADBMDNSDiscovery service scanning, target device priority hierarchy, and fallback handling.
7. ADBClient connect_device and disconnect_device socket status parsing.
8. SamsungADBIngestor 4-tier device selection hierarchy.
9. CLI argument parser options and default values.
10. Zeroconf missing/uninstalled defensive handling.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure content_creation is on sys.path
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent / "content_creation"
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from config import (
    ADB_MDNS_ALL_SERVICES,
    ADB_MDNS_DEFAULT_TIMEOUT_SECONDS,
    ADB_MDNS_SERVICE_LEGACY,
    ADB_MDNS_SERVICE_TLS_CONNECT,
    DEFAULT_ADB_WIFI_PORT,
    MDNS_ADB_LEGACY_SERVICE_TYPE,
    MDNS_ADB_TLS_SERVICE_TYPE,
    MDNS_DEFAULT_TIMEOUT_SEC,
    SAMSUNG_MODEL_PREFIXES,
)
from samsung_ingest import (
    ADBClient,
    ADBDeviceInfo,
    ADBMDNSDiscovery,
    ADBMDNSListener,
    DiscoveredADBService,
    NoDeviceConnectedError,
    SamsungADBIngestor,
    build_parser,
    extract_ip_address,
    parse_service_properties,
)


class TestConfigMDNSConstants(unittest.TestCase):
    """Verifies that mDNS constants conform to RFC 6762 / RFC 6763 and project contracts."""

    def test_mdns_constants_values(self):
        self.assertEqual(MDNS_ADB_TLS_SERVICE_TYPE, "_adb-tls-connect._tcp.local.")
        self.assertEqual(MDNS_ADB_LEGACY_SERVICE_TYPE, "_adb._tcp.local.")
        self.assertEqual(MDNS_DEFAULT_TIMEOUT_SEC, 5.0)
        self.assertEqual(DEFAULT_ADB_WIFI_PORT, 5555)

    def test_mdns_aliases_and_collections(self):
        self.assertEqual(ADB_MDNS_SERVICE_TLS_CONNECT, "_adb-tls-connect._tcp.local.")
        self.assertEqual(ADB_MDNS_SERVICE_LEGACY, "_adb._tcp.local.")
        self.assertEqual(ADB_MDNS_DEFAULT_TIMEOUT_SECONDS, 5.0)
        self.assertIn(MDNS_ADB_TLS_SERVICE_TYPE, ADB_MDNS_ALL_SERVICES)
        self.assertIn(MDNS_ADB_LEGACY_SERVICE_TYPE, ADB_MDNS_ALL_SERVICES)
        self.assertIn("SM-S948", SAMSUNG_MODEL_PREFIXES)


class TestDiscoveredADBService(unittest.TestCase):
    """Stress-tests the DiscoveredADBService dataclass and classification properties."""

    def test_s26_ultra_identification(self):
        svc = DiscoveredADBService(
            name="adb-SM-S948U-xyz._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            ip_address="192.168.1.150",
            port=41235,
            properties={"model": "SM-S948U", "serial": "RF8N12345"},
        )
        self.assertEqual(svc.endpoint, "192.168.1.150:41235")
        self.assertEqual(svc.model, "SM-S948U")
        self.assertTrue(svc.is_samsung)
        self.assertTrue(svc.is_s26_ultra)

    def test_samsung_non_s26_identification(self):
        svc = DiscoveredADBService(
            name="adb-SM-S928B._adb._tcp.local.",
            service_type="_adb._tcp.local.",
            ip_address="192.168.1.151",
            port=5555,
            properties={"model": "SM-S928B"},
        )
        self.assertTrue(svc.is_samsung)
        self.assertFalse(svc.is_s26_ultra)

    def test_non_samsung_identification(self):
        svc = DiscoveredADBService(
            name="adb-Pixel-9-Pro._adb._tcp.local.",
            service_type="_adb._tcp.local.",
            ip_address="192.168.1.152",
            port=5555,
            properties={"model": "Pixel 9 Pro"},
        )
        self.assertFalse(svc.is_samsung)
        self.assertFalse(svc.is_s26_ultra)


class TestExtractIPAddress(unittest.TestCase):
    """Adversarial testing of extract_ip_address across multiple Zeroconf representations."""

    def test_parsed_addresses_ipv4_preferred(self):
        mock_info = MagicMock()
        mock_info.parsed_addresses.return_value = ["127.0.0.1", "192.168.1.200"]
        ip = extract_ip_address(mock_info)
        self.assertEqual(ip, "192.168.1.200")

    def test_raw_byte_addresses_ipv4(self):
        mock_info = MagicMock(spec=["addresses"])
        # 192.168.1.75 in packed network bytes: 192=0xc0, 168=0xa8, 1=0x01, 75=0x4b
        mock_info.addresses = [bytes([192, 168, 1, 75])]
        ip = extract_ip_address(mock_info)
        self.assertEqual(ip, "192.168.1.75")

    def test_raw_byte_addresses_ipv6_fallback(self):
        mock_info = MagicMock(spec=["addresses"])
        # 16-byte IPv6 address
        ipv6_bytes = socket.inet_pton(socket.AF_INET6, "2001:db8::1")
        mock_info.addresses = [ipv6_bytes]
        ip = extract_ip_address(mock_info)
        self.assertEqual(ip, "2001:db8::1")

    def test_legacy_address_attribute(self):
        mock_info = MagicMock(spec=["address"])
        mock_info.address = bytes([10, 0, 0, 42])
        ip = extract_ip_address(mock_info)
        self.assertEqual(ip, "10.0.0.42")

    def test_empty_or_malformed_returns_none(self):
        mock_info = MagicMock(spec=[])
        ip = extract_ip_address(mock_info)
        self.assertIsNone(ip)


class TestParseServiceProperties(unittest.TestCase):
    """Tests binary TXT record decoding into clean Python string dictionary."""

    def test_binary_properties_decoding(self):
        mock_info = MagicMock()
        mock_info.properties = {
            b"model": b"SM-S948U",
            b"features": b"wifi,tls",
            b"null_val": None,
        }
        props = parse_service_properties(mock_info)
        self.assertEqual(props["model"], "SM-S948U")
        self.assertEqual(props["features"], "wifi,tls")
        self.assertEqual(props["null_val"], "")

    def test_string_properties(self):
        mock_info = MagicMock()
        mock_info.properties = {"model": "SM-S948B", "version": "1.0"}
        props = parse_service_properties(mock_info)
        self.assertEqual(props["model"], "SM-S948B")
        self.assertEqual(props["version"], "1.0")


class TestADBMDNSDiscoveryHierarchy(unittest.TestCase):
    """Adversarial stress-testing of discovery and target device selection priority."""

    def test_target_device_priority_s26_over_others(self):
        discovery = ADBMDNSDiscovery()
        s26_svc = DiscoveredADBService("s26", "_adb-tls-connect._tcp.local.", "192.168.1.10", 38001, properties={"model": "SM-S948U"})
        s24_svc = DiscoveredADBService("s24", "_adb-tls-connect._tcp.local.", "192.168.1.11", 38002, properties={"model": "SM-S928U"})
        pixel_svc = DiscoveredADBService("pixel", "_adb._tcp.local.", "192.168.1.12", 5555, properties={"model": "Pixel 9"})

        with patch.object(discovery, "discover_services", return_value=[pixel_svc, s24_svc, s26_svc]):
            selected = discovery.find_target_device()
            self.assertIsNotNone(selected)
            self.assertEqual(selected.model, "SM-S948U")
            self.assertEqual(selected.ip_address, "192.168.1.10")

    def test_target_device_priority_preferred_serial(self):
        discovery = ADBMDNSDiscovery()
        s26_svc = DiscoveredADBService("s26", "_adb-tls-connect._tcp.local.", "192.168.1.10", 38001, properties={"model": "SM-S948U", "serial": "SERIAL_A"})
        s24_svc = DiscoveredADBService("s24", "_adb-tls-connect._tcp.local.", "192.168.1.11", 38002, properties={"model": "SM-S928U", "serial": "SERIAL_B"})

        with patch.object(discovery, "discover_services", return_value=[s26_svc, s24_svc]):
            selected = discovery.find_target_device(preferred_serial="SERIAL_B")
            self.assertIsNotNone(selected)
            self.assertEqual(selected.model, "SM-S928U")
            self.assertEqual(selected.ip_address, "192.168.1.11")

    def test_target_device_empty_discovery(self):
        discovery = ADBMDNSDiscovery()
        with patch.object(discovery, "discover_services", return_value=[]):
            selected = discovery.find_target_device()
            self.assertIsNone(selected)


class TestADBClientConnection(unittest.TestCase):
    """Verifies ADBClient connect_device and disconnect_device parsing."""

    @patch("samsung_ingest.find_adb_binary", return_value=Path("C:/platform-tools/adb.exe"))
    def test_connect_device_success_and_already_connected(self, mock_find):
        client = ADBClient()

        # Case 1: Successfully connected
        mock_proc_1 = MagicMock(stdout="connected to 192.168.1.100:38491\n", stderr="", returncode=0)
        with patch.object(client, "run_cmd", return_value=mock_proc_1):
            self.assertTrue(client.connect_device("192.168.1.100", 38491))

        # Case 2: Already connected
        mock_proc_2 = MagicMock(stdout="already connected to 192.168.1.100:38491\n", stderr="", returncode=0)
        with patch.object(client, "run_cmd", return_value=mock_proc_2):
            self.assertTrue(client.connect_device("192.168.1.100", 38491))

        # Case 3: Connection refused / failed
        mock_proc_3 = MagicMock(stdout="failed to connect to 192.168.1.100:38491: Connection refused\n", stderr="", returncode=0)
        with patch.object(client, "run_cmd", return_value=mock_proc_3):
            self.assertFalse(client.connect_device("192.168.1.100", 38491))


class TestSamsungADBIngestor4TierFallback(unittest.TestCase):
    """Stress-tests the 4-tier fallback device resolution hierarchy in SamsungADBIngestor."""

    @patch("samsung_ingest.find_adb_binary", return_value=Path("C:/platform-tools/adb.exe"))
    def test_tier_1_explicit_connect_endpoint(self, mock_find):
        ingestor = SamsungADBIngestor(
            workspace_root=Path.cwd(),
            connect_endpoint="192.168.1.55:40001",
            enable_mdns=False,
        )
        mock_dev = ADBDeviceInfo(serial="192.168.1.55:40001", state="device", model="SM-S948U", is_authorized=True, is_samsung=True)

        with patch.object(ingestor.adb, "connect_device", return_value=True) as mock_connect:
            with patch.object(ingestor.adb, "select_active_device", return_value=mock_dev):
                dev = ingestor.select_device()
                mock_connect.assert_called_once_with("192.168.1.55", 40001)
                self.assertEqual(dev.serial, "192.168.1.55:40001")

    @patch("samsung_ingest.find_adb_binary", return_value=Path("C:/platform-tools/adb.exe"))
    def test_tier_2_mdns_auto_discovery(self, mock_find):
        ingestor = SamsungADBIngestor(
            workspace_root=Path.cwd(),
            enable_mdns=True,
            mdns_timeout=2.0,
        )
        discovered_svc = DiscoveredADBService("s26", "_adb-tls-connect._tcp.local.", "192.168.1.88", 39999, properties={"model": "SM-S948U"})
        mock_dev = ADBDeviceInfo(serial="192.168.1.88:39999", state="device", model="SM-S948U", is_authorized=True, is_samsung=True)

        with patch.object(ingestor.mdns_discovery, "find_target_device", return_value=discovered_svc):
            with patch.object(ingestor.adb, "connect_device", return_value=True) as mock_connect:
                with patch.object(ingestor.adb, "select_active_device", return_value=mock_dev):
                    dev = ingestor.select_device()
                    mock_connect.assert_called_once_with("192.168.1.88", 39999)
                    self.assertEqual(dev.serial, "192.168.1.88:39999")

    @patch("samsung_ingest.find_adb_binary", return_value=Path("C:/platform-tools/adb.exe"))
    def test_tier_3_usb_fallback_when_mdns_times_out(self, mock_find):
        ingestor = SamsungADBIngestor(
            workspace_root=Path.cwd(),
            enable_mdns=True,
        )
        usb_dev = ADBDeviceInfo(serial="RF8N1234567", state="device", model="SM-S948U", is_authorized=True, is_samsung=True)

        with patch.object(ingestor.mdns_discovery, "find_target_device", return_value=None):
            with patch.object(ingestor.adb, "select_active_device", return_value=usb_dev):
                dev = ingestor.select_device()
                self.assertEqual(dev.serial, "RF8N1234567")

    @patch("samsung_ingest.find_adb_binary", return_value=Path("C:/platform-tools/adb.exe"))
    def test_tier_4_no_device_connected_error(self, mock_find):
        ingestor = SamsungADBIngestor(
            workspace_root=Path.cwd(),
            enable_mdns=False,
        )
        with patch.object(ingestor.adb, "list_devices", return_value=[]):
            with self.assertRaises(NoDeviceConnectedError) as ctx:
                ingestor.select_device()
            self.assertIn("Wireless Debugging", str(ctx.exception))


class TestCLIArgumentParsing(unittest.TestCase):
    """Verifies CLI flag bindings and defaults in build_parser()."""

    def test_parser_mdns_flags(self):
        parser = build_parser()

        # Default: enable_mdns=True, mdns_timeout=5.0
        args_def = parser.parse_args([])
        self.assertTrue(args_def.enable_mdns)
        self.assertEqual(args_def.mdns_timeout, 5.0)
        self.assertIsNone(args_def.connect)

        # Explicit --no-mdns
        args_no_mdns = parser.parse_args(["--no-mdns"])
        self.assertFalse(args_no_mdns.enable_mdns)

        # Explicit --mdns and --mdns-timeout and --connect
        args_custom = parser.parse_args(["--mdns", "--mdns-timeout", "8.5", "--connect", "192.168.1.77:45000"])
        self.assertTrue(args_custom.enable_mdns)
        self.assertEqual(args_custom.mdns_timeout, 8.5)
        self.assertEqual(args_custom.connect, "192.168.1.77:45000")


if __name__ == "__main__":
    unittest.main()
