"""
adversarial_test_suite.py - Comprehensive Empirical Adversarial Challenge Suite for Milestone 1
Track 2: Samsung S26 Ultra ADB mDNS Auto-Discovery & Ingestion Bridge

Empirically challenges:
1. Malformed mDNS service properties & binary TXT record decoding.
2. IPv4 / IPv6 network address resolution & edge cases.
3. Timeout handling when no mDNS services broadcast on local Wi-Fi.
4. 4-Tier Ingestion fallback hierarchy (Explicit connect -> mDNS -> USB/Wi-Fi attached -> NoDeviceConnectedError).
5. ADB TCP/IP connection parsing ("connected to", "already connected to", "connection refused", "cannot connect", timeouts).
6. S26 Ultra flagship model matching (SM-S948*) & multi-device prioritization hierarchy.
7. mDNS Listener service lifecycle events (add, update, remove, exception handling).
8. Resilience when zeroconf is uninstalled or dynamically unavailable.
9. Malformed CLI arguments, malformed endpoint strings, and socket timeout exceptions.
"""

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure content_creation module path is accessible
CODEBASE_ROOT = Path("G:/My Drive/GOOGLE ANTIGRAVITY/content_creation").resolve()
sys.path.insert(0, str(CODEBASE_ROOT))

from config import (
    MDNS_ADB_LEGACY_SERVICE_TYPE,
    MDNS_ADB_TLS_SERVICE_TYPE,
    MDNS_DEFAULT_TIMEOUT_SEC,
    SAMSUNG_MODEL_PREFIXES,
)
import samsung_ingest
from samsung_ingest import (
    ADBClient,
    ADBDeviceInfo,
    ADBError,
    ADBMDNSDiscovery,
    ADBMDNSListener,
    DiscoveredADBService,
    NoDeviceConnectedError,
    build_parser,
    extract_ip_address,
    parse_service_properties,
    SamsungADBIngestor,
)


class TestAdversarialMdnsPropertyDecoding(unittest.TestCase):
    """Stress-tests mDNS TXT record property parsing with adversarial inputs."""

    def test_non_utf8_binary_properties(self):
        """Tests decoding raw binary bytes with invalid UTF-8 sequences."""
        mock_info = MagicMock()
        mock_info.properties = {
            b"model": b"SM-S948U\xff\xfe\x80",
            b"serial": b"R5CX10ABCD\x00\x01\x02",
            b"corrupt_key_\x80\xff": b"valid_value",
            b"null_bytes": b"val\x00\x00test",
        }
        props = parse_service_properties(mock_info)
        self.assertIn("model", props)
        self.assertIn("serial", props)
        self.assertTrue(props["model"].startswith("SM-S948U"))
        self.assertTrue(props["serial"].startswith("R5CX10ABCD"))

    def test_mixed_types_and_none_in_properties(self):
        """Tests handling of None, integer, and non-bytes values in properties."""
        mock_info = MagicMock()
        mock_info.properties = {
            "str_key": "str_value",
            "none_val": None,
            "int_val": 12345,
            100: b"int_key_val",
            b"empty_val": b"",
        }
        props = parse_service_properties(mock_info)
        self.assertEqual(props["str_key"], "str_value")
        self.assertEqual(props["none_val"], "")
        self.assertEqual(props["int_val"], "12345")
        self.assertEqual(props["100"], "int_key_val")
        self.assertEqual(props["empty_val"], "")

    def test_non_dict_properties(self):
        """Tests handling when info.properties is None, string, list, or missing."""
        for invalid_props in [None, "invalid_string", [1, 2, 3], 42, object()]:
            mock_info = MagicMock()
            mock_info.properties = invalid_props
            props = parse_service_properties(mock_info)
            self.assertEqual(props, {})

        mock_empty = object()
        props = parse_service_properties(mock_empty)
        self.assertEqual(props, {})


class TestAdversarialIPAddressExtraction(unittest.TestCase):
    """Stress-tests IPv4/IPv6 address parsing across different Zeroconf version formats."""

    def test_parsed_addresses_ipv4_priority_over_ipv6_and_loopback(self):
        """Verifies parsed_addresses() filters out loopback and prioritizes LAN IPv4."""
        mock_info = MagicMock()
        mock_info.parsed_addresses.return_value = [
            "127.0.0.1",
            "::1",
            "fe80::1ff:fe00:3a60",
            "192.168.1.155",
            "10.0.0.22",
        ]
        ip = extract_ip_address(mock_info)
        self.assertEqual(ip, "192.168.1.155")

    def test_parsed_addresses_ipv6_only(self):
        """Verifies parsed_addresses() returns first valid IPv6 when no IPv4 is present."""
        mock_info = MagicMock()
        mock_info.parsed_addresses.return_value = ["fe80::20c:29ff:fe4f:8e9b", "2001:db8::1"]
        ip = extract_ip_address(mock_info)
        self.assertEqual(ip, "fe80::20c:29ff:fe4f:8e9b")

    def test_raw_4byte_ipv4_bytes(self):
        """Verifies raw network byte array decoding for standard IPv4."""
        mock_info = MagicMock(spec=["addresses"])
        mock_info.addresses = [socket.inet_aton("192.168.50.88")]
        ip = extract_ip_address(mock_info)
        self.assertEqual(ip, "192.168.50.88")

    def test_raw_byte_array_loopback_skipping(self):
        """Verifies raw byte decoding skips 127.0.0.1 loopback in favor of routable IP."""
        mock_info = MagicMock(spec=["addresses"])
        mock_info.addresses = [
            socket.inet_aton("127.0.0.1"),
            socket.inet_aton("172.16.0.45"),
        ]
        ip = extract_ip_address(mock_info)
        self.assertEqual(ip, "172.16.0.45")

    def test_raw_16byte_ipv6_bytes(self):
        """Verifies raw 16-byte network byte array decoding for IPv6."""
        mock_info = MagicMock(spec=["addresses"])
        mock_info.addresses = [socket.inet_pton(socket.AF_INET6, "2001:db8::8a2e:370:7334")]
        ip = extract_ip_address(mock_info)
        self.assertEqual(ip, "2001:db8::8a2e:370:7334")

    def test_corrupted_address_bytes(self):
        """Verifies robustness against corrupt byte lengths (0, 3, 5, 15, 17 bytes)."""
        mock_info = MagicMock(spec=["addresses"])
        mock_info.addresses = [b"", b"\x01\x02\x03", b"\x01" * 5, b"\x02" * 15, b"\x03" * 17]
        ip = extract_ip_address(mock_info)
        self.assertIsNone(ip)

    def test_legacy_address_attribute(self):
        """Verifies fallback to legacy info.address single attribute."""
        mock_info_bytes = MagicMock(spec=["address"])
        mock_info_bytes.address = socket.inet_aton("192.168.10.99")
        self.assertEqual(extract_ip_address(mock_info_bytes), "192.168.10.99")

        mock_info_str = MagicMock(spec=["address"])
        mock_info_str.address = "192.168.10.100"
        self.assertEqual(extract_ip_address(mock_info_str), "192.168.10.100")

    def test_exception_in_parsed_addresses_falls_back(self):
        """Verifies that an exception in parsed_addresses() gracefully falls back to raw bytes."""
        mock_info = MagicMock()
        mock_info.parsed_addresses.side_effect = RuntimeError("Socket buffer read error")
        mock_info.addresses = [socket.inet_aton("10.10.10.10")]
        ip = extract_ip_address(mock_info)
        self.assertEqual(ip, "10.10.10.10")

    def test_empty_or_none_info_returns_none(self):
        """Verifies None or empty info returns None without raising errors."""
        self.assertIsNone(extract_ip_address(None))
        self.assertIsNone(extract_ip_address(object()))


class TestAdversarialMdnsDiscoveryTimeout(unittest.TestCase):
    """Stress-tests mDNS discovery timeouts and lifecycle when no services respond."""

    def test_discovery_timeout_no_services(self):
        """Verifies discovery finishes within requested timeout and returns empty list."""
        discovery = ADBMDNSDiscovery(timeout_sec=0.1)
        start_t = time.time()
        services = discovery.discover_services(timeout=0.1)
        elapsed = time.time() - start_t

        self.assertIsInstance(services, list)
        self.assertLess(elapsed, 1.5)

    def test_find_target_device_returns_none_on_timeout(self):
        """Verifies find_target_device() safely returns None when no devices are discovered."""
        discovery = ADBMDNSDiscovery(timeout_sec=0.05)
        target = discovery.find_target_device(timeout=0.05)
        self.assertIsNone(target)

    @patch("samsung_ingest.Zeroconf")
    def test_zeroconf_instantiation_exception_resilience(self, mock_zc):
        """Verifies resilience if Zeroconf() raises OSError (e.g. UDP 5353 bind conflict)."""
        mock_zc.side_effect = OSError("Address already in use on UDP port 5353")
        discovery = ADBMDNSDiscovery(timeout_sec=0.1)
        services = discovery.discover_services()
        self.assertEqual(services, [])

    def test_zeroconf_uninstalled_fallback(self):
        """Verifies graceful fallback when zeroconf classes are None."""
        with patch.object(samsung_ingest, "Zeroconf", None):
            with patch.object(samsung_ingest, "ServiceBrowser", None):
                discovery = ADBMDNSDiscovery()
                services = discovery.discover_services()
                self.assertEqual(services, [])


class TestAdversarialADBConnectParsing(unittest.TestCase):
    """Stress-tests adb connect output parsing across real ADB response variants."""

    def setUp(self):
        self.temp_bin = tempfile.NamedTemporaryFile(suffix=".exe", delete=False)
        self.temp_bin.write(b"mock binary")
        self.temp_bin.close()
        self.client = ADBClient(adb_path=self.temp_bin.name)

    def tearDown(self):
        if os.path.exists(self.temp_bin.name):
            os.unlink(self.temp_bin.name)

    @patch("subprocess.run")
    def test_connect_success_strings(self, mock_run):
        """Verifies successful connection parsing on standard success outputs."""
        success_outputs = [
            "connected to 192.168.1.100:38491\n",
            "Connected to 192.168.1.100:38491\n",
            "already connected to 192.168.1.100:38491\n",
            "Already connected to 192.168.1.100:38491\n",
            "* daemon started successfully *\nconnected to 192.168.1.100:38491\n",
        ]
        for out in success_outputs:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=out, stderr="")
            res = self.client.connect_device("192.168.1.100", 38491)
            self.assertTrue(res, f"Failed on output: {out}")

    @patch("subprocess.run")
    def test_connect_failure_strings(self, mock_run):
        """Verifies failed connection parsing on error / refusal strings."""
        failure_outputs = [
            ("cannot connect to 192.168.1.100:38491: No connection could be made because the target machine actively refused it. (10061)", ""),
            ("failed to connect to '192.168.1.100:38491': Connection refused", ""),
            ("unable to connect to 192.168.1.100:38491: Connection timed out", ""),
            ("cannot connect to 192.168.1.100:38491: No route to host", ""),
            ("", "error: could not connect to 192.168.1.100:38491"),
            ("device offline", ""),
        ]
        for stdout_val, stderr_val in failure_outputs:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout=stdout_val, stderr=stderr_val)
            res = self.client.connect_device("192.168.1.100", 38491)
            self.assertFalse(res, f"Expected False on: stdout='{stdout_val}', stderr='{stderr_val}'")

    @patch("subprocess.run")
    def test_disconnect_device_execution(self, mock_run):
        """Verifies adb disconnect execution."""
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="disconnected 192.168.1.100:38491\n", stderr="")
        res = self.client.disconnect_device("192.168.1.100:38491")
        self.assertTrue(res)


class TestAdversarialS26ModelFilteringAndPrioritization(unittest.TestCase):
    """Stress-tests S26 Ultra model regex matching and multi-device priority hierarchy."""

    def test_s26_ultra_model_variants(self):
        """Verifies all Samsung S26 Ultra regional variants match is_s26_ultra."""
        s26_variants = [
            "SM-S948U",   # US Carrier
            "SM-S948U1",  # US Unlocked
            "SM-S948B",   # Global
            "SM-S948N",   # Korea
            "SM-S9480",   # China / Hong Kong
            "SM-S948W",   # Canada
            "SM-S948",    # Base Series
        ]
        for model in s26_variants:
            dev_info = ADBDeviceInfo(serial="R5CXTEST", state="device", model=model, is_authorized=True, is_samsung=True)
            self.assertTrue(dev_info.is_s26_ultra, f"Model {model} failed is_s26_ultra on ADBDeviceInfo")

            svc = DiscoveredADBService(
                name=f"adb-{model}-service._adb-tls-connect._tcp.local.",
                service_type="_adb-tls-connect._tcp.local.",
                ip_address="192.168.1.100",
                port=38491,
                properties={"model": model},
            )
            self.assertTrue(svc.is_s26_ultra, f"Model {model} failed is_s26_ultra on DiscoveredADBService")
            self.assertTrue(svc.is_samsung)

    def test_non_s26_models_filtering(self):
        """Verifies older Samsung flagships and competitor models do NOT match is_s26_ultra."""
        older_samsungs = ["SM-S938U", "SM-S928U", "SM-S918U", "SM-G998U", "SM-A546U"]
        for model in older_samsungs:
            dev_info = ADBDeviceInfo(serial="R5CXTEST", state="device", model=model, is_authorized=True, is_samsung=True)
            self.assertFalse(dev_info.is_s26_ultra, f"Model {model} falsely identified as S26 Ultra")
            self.assertTrue(dev_info.is_samsung)

        competitors = ["Pixel 9 Pro", "Pixel 8", "OnePlus 12", "Xiaomi 14", "iPhone16,2"]
        for model in competitors:
            dev_info = ADBDeviceInfo(serial="12345", state="device", model=model, is_authorized=True, is_samsung=False)
            self.assertFalse(dev_info.is_s26_ultra)
            self.assertFalse(dev_info.is_samsung)

    def test_mdns_target_device_prioritization_hierarchy(self):
        """
        Tests strict prioritization hierarchy:
        1. Preferred Serial Match -> 2. S26 Ultra -> 3. Older Samsung -> 4. Any Android
        """
        discovery = ADBMDNSDiscovery()

        s26_svc = DiscoveredADBService("s26", "_adb-tls-connect._tcp.local.", "192.168.1.101", 38491, properties={"model": "SM-S948U", "serial": "SERIAL_S26"})
        s25_svc = DiscoveredADBService("s25", "_adb-tls-connect._tcp.local.", "192.168.1.102", 38492, properties={"model": "SM-S938U", "serial": "SERIAL_S25"})
        pixel_svc = DiscoveredADBService("pixel", "_adb-tls-connect._tcp.local.", "192.168.1.103", 38493, properties={"model": "Pixel 9 Pro", "serial": "SERIAL_PIXEL"})

        # Case A: S26 + S25 + Pixel present -> chooses S26
        with patch.object(discovery, "discover_services", return_value=[pixel_svc, s25_svc, s26_svc]):
            chosen = discovery.find_target_device()
            self.assertEqual(chosen.properties["model"], "SM-S948U")

        # Case B: Preferred serial specified -> overrides S26
        with patch.object(discovery, "discover_services", return_value=[pixel_svc, s25_svc, s26_svc]):
            chosen = discovery.find_target_device(preferred_serial="SERIAL_PIXEL")
            self.assertEqual(chosen.properties["model"], "Pixel 9 Pro")

        # Case C: Only S25 + Pixel present -> chooses S25
        with patch.object(discovery, "discover_services", return_value=[pixel_svc, s25_svc]):
            chosen = discovery.find_target_device()
            self.assertEqual(chosen.properties["model"], "SM-S938U")

        # Case D: Only Pixel present -> chooses Pixel
        with patch.object(discovery, "discover_services", return_value=[pixel_svc]):
            chosen = discovery.find_target_device()
            self.assertEqual(chosen.properties["model"], "Pixel 9 Pro")


class TestAdversarialFourTierFallbackHierarchy(unittest.TestCase):
    """Stress-tests the 4-tier hardware fallback hierarchy in SamsungADBIngestor."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace = Path(self.test_dir)
        self.adb_bin = self.workspace / "adb.exe"
        self.adb_bin.write_bytes(b"mock adb binary")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)

    @patch.object(ADBClient, "connect_device")
    @patch.object(ADBClient, "list_devices")
    def test_tier_1_explicit_connect_endpoint(self, mock_list, mock_connect):
        """Tier 1: Explicit --connect <ip>:<port> triggers connection before device selection."""
        mock_connect.return_value = True
        mock_list.return_value = [
            ADBDeviceInfo(serial="192.168.1.50:5555", state="device", model="SM-S948U", is_authorized=True, is_samsung=True)
        ]

        ingestor = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            connect_endpoint="192.168.1.50:5555",
            enable_mdns=False,
        )

        selected = ingestor.select_device()
        mock_connect.assert_called_once_with("192.168.1.50", 5555)
        self.assertEqual(selected.serial, "192.168.1.50:5555")

    @patch.object(ADBMDNSDiscovery, "find_target_device")
    @patch.object(ADBClient, "connect_device")
    @patch.object(ADBClient, "list_devices")
    def test_tier_2_mdns_auto_discovery_and_connect(self, mock_list, mock_connect, mock_find):
        """Tier 2: mDNS auto-discovers S26 Ultra and executes adb connect."""
        mock_find.return_value = DiscoveredADBService("s26", "_adb-tls-connect._tcp.local.", "192.168.1.77", 41234, properties={"model": "SM-S948U"})
        mock_connect.return_value = True
        mock_list.return_value = [
            ADBDeviceInfo(serial="192.168.1.77:41234", state="device", model="SM-S948U", is_authorized=True, is_samsung=True)
        ]

        ingestor = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            enable_mdns=True,
            mdns_timeout=0.1,
        )

        selected = ingestor.select_device()
        mock_find.assert_called_once()
        mock_connect.assert_called_once_with("192.168.1.77", 41234)
        self.assertEqual(selected.serial, "192.168.1.77:41234")

    @patch.object(ADBMDNSDiscovery, "find_target_device")
    @patch.object(ADBClient, "connect_device")
    @patch.object(ADBClient, "list_devices")
    def test_tier_2_connect_exception_resilience(self, mock_list, mock_connect, mock_find):
        """Tier 2: Even if connect_device raises ADBError/Timeout, safely falls through to Tier 3."""
        mock_find.return_value = DiscoveredADBService("s26", "_adb-tls-connect._tcp.local.", "192.168.1.77", 41234, properties={"model": "SM-S948U"})
        mock_connect.side_effect = ADBError("Connection timeout during ADB connect")
        mock_list.return_value = [
            ADBDeviceInfo(serial="ATTACHED_USB", state="device", model="SM-S948U", is_authorized=True, is_samsung=True)
        ]

        ingestor = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            enable_mdns=True,
            mdns_timeout=0.05,
        )

        selected = ingestor.select_device()
        self.assertEqual(selected.serial, "ATTACHED_USB")

    @patch.object(ADBMDNSDiscovery, "find_target_device")
    @patch.object(ADBClient, "list_devices")
    def test_tier_3_fallback_to_attached_usb_device_on_mdns_timeout(self, mock_list, mock_find):
        """Tier 3: When mDNS times out (None), falls back to attached USB device."""
        mock_find.return_value = None  # mDNS timeout / no device broadcast
        mock_list.return_value = [
            ADBDeviceInfo(serial="USB_R5CX10ABCDE", state="device", model="SM-S948U", usb_port="1-2", is_authorized=True, is_samsung=True)
        ]

        ingestor = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            enable_mdns=True,
            mdns_timeout=0.05,
        )

        selected = ingestor.select_device()
        self.assertEqual(selected.serial, "USB_R5CX10ABCDE")
        self.assertTrue(selected.is_s26_ultra)

    @patch.object(ADBMDNSDiscovery, "find_target_device")
    @patch.object(ADBClient, "list_devices")
    def test_tier_4_actionable_no_device_connected_error(self, mock_list, mock_find):
        """Tier 4: When mDNS and USB both fail, raises NoDeviceConnectedError with actionable guide."""
        mock_find.return_value = None
        mock_list.return_value = []

        ingestor = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            enable_mdns=True,
            mdns_timeout=0.05,
        )

        with self.assertRaises(NoDeviceConnectedError) as ctx:
            ingestor.select_device()

        err_msg = str(ctx.exception)
        self.assertIn("No Android devices detected via ADB", err_msg)
        self.assertIn("Wireless Debugging", err_msg)
        self.assertIn("USB Debugging", err_msg)

    @patch.object(ADBMDNSDiscovery, "find_target_device")
    @patch.object(ADBClient, "list_devices")
    def test_no_mdns_flag_bypasses_mdns(self, mock_list, mock_find):
        """Verifies --no-mdns (enable_mdns=False) completely skips mDNS discovery."""
        mock_list.return_value = [
            ADBDeviceInfo(serial="USB_SERIAL_DIRECT", state="device", model="SM-S948B", is_authorized=True, is_samsung=True)
        ]

        ingestor = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            enable_mdns=False,
        )

        selected = ingestor.select_device()
        mock_find.assert_not_called()
        self.assertEqual(selected.serial, "USB_SERIAL_DIRECT")

    @patch.object(ADBClient, "connect_device")
    @patch.object(ADBClient, "list_devices")
    def test_malformed_connect_endpoint_resilience(self, mock_list, mock_connect):
        """Verifies malformed --connect string (e.g. invalid port string) does not crash."""
        mock_list.return_value = [
            ADBDeviceInfo(serial="FALLBACK_USB", state="device", model="SM-S948U", is_authorized=True, is_samsung=True)
        ]

        ingestor = SamsungADBIngestor(
            workspace_root=self.workspace,
            adb_path=str(self.adb_bin),
            connect_endpoint="192.168.1.100:invalid_port_int",
            enable_mdns=False,
        )

        selected = ingestor.select_device()
        self.assertEqual(selected.serial, "FALLBACK_USB")


class TestAdversarialMdnsListenerLifecycle(unittest.TestCase):
    """Stress-tests ADBMDNSListener event handling and thread synchronization."""

    def test_listener_add_update_remove_cycle(self):
        """Tests add_service, update_service, and remove_service operations under thread lock."""
        listener = ADBMDNSListener()

        mock_zc = MagicMock()
        mock_info_v1 = MagicMock()
        mock_info_v1.name = "device1._adb-tls-connect._tcp.local."
        mock_info_v1.port = 38491
        mock_zc.get_service_info.return_value = mock_info_v1

        listener.add_service(mock_zc, "_adb-tls-connect._tcp.local.", "device1._adb-tls-connect._tcp.local.")
        self.assertEqual(len(listener.discovered_infos), 1)

        # Update service
        mock_info_v2 = MagicMock()
        mock_info_v2.name = "device1._adb-tls-connect._tcp.local."
        mock_info_v2.port = 45000
        mock_zc.get_service_info.return_value = mock_info_v2

        listener.update_service(mock_zc, "_adb-tls-connect._tcp.local.", "device1._adb-tls-connect._tcp.local.")
        self.assertEqual(len(listener.discovered_infos), 1)
        self.assertEqual(listener.discovered_infos[0].port, 45000)

        # Remove service
        listener.remove_service(mock_zc, "_adb-tls-connect._tcp.local.", "device1._adb-tls-connect._tcp.local.")
        self.assertEqual(len(listener.discovered_infos), 0)

    def test_listener_get_service_info_exception_handling(self):
        """Verifies listener does not crash if get_service_info raises an exception."""
        listener = ADBMDNSListener()
        mock_zc = MagicMock()
        mock_zc.get_service_info.side_effect = RuntimeError("DNS socket timeout")

        # Must not raise
        listener.add_service(mock_zc, "_adb-tls-connect._tcp.local.", "broken_svc")
        self.assertEqual(len(listener.discovered_infos), 0)


class TestAdversarialCLIParserBindings(unittest.TestCase):
    """Stress-tests CLI parser with all combination of flags."""

    def test_cli_mdns_flags(self):
        parser = build_parser()

        # Default
        args = parser.parse_args([])
        self.assertTrue(args.enable_mdns)
        self.assertEqual(args.mdns_timeout, MDNS_DEFAULT_TIMEOUT_SEC)
        self.assertIsNone(args.connect)

        # Explicit --no-mdns
        args_no_mdns = parser.parse_args(["--no-mdns"])
        self.assertFalse(args_no_mdns.enable_mdns)

        # Explicit --auto-discover
        args_auto = parser.parse_args(["--auto-discover", "--mdns-timeout", "12.5"])
        self.assertTrue(args_auto.enable_mdns)
        self.assertEqual(args_auto.mdns_timeout, 12.5)

        # Explicit --connect
        args_conn = parser.parse_args(["--connect", "192.168.1.200:5555"])
        self.assertEqual(args_conn.connect, "192.168.1.200:5555")


if __name__ == "__main__":
    unittest.main()
