import argparse
from datetime import datetime
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

WORKSPACE_DIR = Path("G:/My Drive/GOOGLE ANTIGRAVITY/content_creation").resolve()
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

import config
import samsung_ingest
from samsung_ingest import (
    ADBClient,
    ADBDeviceInfo,
    ADBError,
    ADBMDNSDiscovery,
    ADBMDNSListener,
    ADBNotFoundError,
    DeviceSelectionError,
    DeviceUnauthorizedError,
    DiscoveredADBService,
    NoDeviceConnectedError,
    SamsungADBIngestor,
    build_parser,
    extract_ip_address,
    parse_service_properties,
)

class MockServiceInfo:
    def __init__(
        self,
        name="Samsung S26 Ultra._adb-tls-connect._tcp.local.",
        service_type="_adb-tls-connect._tcp.local.",
        server="samsung-s26.local.",
        port=38491,
        properties=None,
        addresses=None,
        parsed_addresses_list=None,
        address=None,
    ):
        self.name = name
        self.type = service_type
        self.server = server
        self.port = port
        self.properties = properties or {}
        self.addresses = addresses or []
        self._parsed_addresses_list = parsed_addresses_list
        self.address = address

    def parsed_addresses(self):
        if self._parsed_addresses_list is not None:
            return self._parsed_addresses_list
        if self.addresses:
            result = []
            for a in self.addresses:
                if len(a) == 4:
                    result.append(socket.inet_ntoa(a))
                elif len(a) == 16:
                    result.append(socket.inet_ntop(socket.AF_INET6, a))
            return result
        return []

class TestScenario1ZeroconfMissingFallback(unittest.TestCase):
    def test_discovery_when_zeroconf_is_none(self):
        with patch("samsung_ingest.Zeroconf", None), patch("samsung_ingest.ServiceBrowser", None):
            discovery = ADBMDNSDiscovery(timeout_sec=0.1)
            results = discovery.discover_services()
            self.assertEqual(results, [])
            target = discovery.find_target_device()
            self.assertIsNone(target)

    def test_ingestor_discover_and_connect_when_zeroconf_missing(self):
        with patch("samsung_ingest.Zeroconf", None), patch("samsung_ingest.ServiceBrowser", None):
            with patch.object(ADBClient, "__init__", return_value=None):
                ingestor = SamsungADBIngestor(workspace_root=Path("."), enable_mdns=True, mdns_timeout=0.1)
                result = ingestor.discover_and_connect()
                self.assertIsNone(result)

    def test_select_device_fallback_when_zeroconf_missing_and_usb_attached(self):
        mock_dev = ADBDeviceInfo(
            serial="R5CX123456",
            state="device",
            model="SM-S948U",
            is_authorized=True,
            is_samsung=True,
        )
        with patch("samsung_ingest.Zeroconf", None), patch("samsung_ingest.ServiceBrowser", None):
            with patch.object(ADBClient, "__init__", return_value=None):
                with patch.object(ADBClient, "list_devices", return_value=[mock_dev]):
                    ingestor = SamsungADBIngestor(workspace_root=Path("."), enable_mdns=True, mdns_timeout=0.1)
                    chosen = ingestor.select_device()
                    self.assertEqual(chosen.serial, "R5CX123456")
                    self.assertEqual(chosen.model, "SM-S948U")

    def test_select_device_raises_no_device_error_when_zeroconf_missing_and_no_attached_devs(self):
        with patch("samsung_ingest.Zeroconf", None), patch("samsung_ingest.ServiceBrowser", None):
            with patch.object(ADBClient, "__init__", return_value=None):
                with patch.object(ADBClient, "list_devices", return_value=[]):
                    ingestor = SamsungADBIngestor(workspace_root=Path("."), enable_mdns=True, mdns_timeout=0.1)
                    with self.assertRaises(NoDeviceConnectedError) as ctx:
                        ingestor.select_device()
                    self.assertIn("No Android devices detected via ADB", str(ctx.exception))
                    self.assertIn("Wireless Debugging", str(ctx.exception))

class TestScenario2SimultaneousMultiDeviceDiscovery(unittest.TestCase):
    def setUp(self):
        self.s26_ultra = DiscoveredADBService(
            name="Samsung Galaxy S26 Ultra._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            ip_address="192.168.1.150",
            port=38491,
            server="s26ultra.local.",
            properties={"model": "SM-S948U", "serial": "R5CX948001"},
        )
        self.s24_ultra = DiscoveredADBService(
            name="Samsung Galaxy S24 Ultra._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            ip_address="192.168.1.151",
            port=38492,
            server="s24ultra.local.",
            properties={"model": "SM-S928U", "serial": "R5CX928001"},
        )
        self.pixel_8 = DiscoveredADBService(
            name="Google Pixel 8 Pro._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            ip_address="192.168.1.160",
            port=41234,
            server="pixel8pro.local.",
            properties={"model": "Pixel 8 Pro", "serial": "38291FDJ"},
        )
        self.xiaomi_13 = DiscoveredADBService(
            name="Xiaomi 13 Ultra._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            ip_address="192.168.1.170",
            port=45000,
            server="xiaomi13.local.",
            properties={"model": "2201123G", "serial": "XM987654"},
        )

    def test_s26_ultra_properties(self):
        self.assertTrue(self.s26_ultra.is_s26_ultra)
        self.assertTrue(self.s26_ultra.is_samsung)
        self.assertEqual(self.s26_ultra.endpoint, "192.168.1.150:38491")
        self.assertFalse(self.s24_ultra.is_s26_ultra)
        self.assertTrue(self.s24_ultra.is_samsung)
        self.assertFalse(self.pixel_8.is_s26_ultra)
        self.assertFalse(self.pixel_8.is_samsung)

    def test_find_target_prioritizes_s26_ultra_over_all_devices(self):
        discovery = ADBMDNSDiscovery()
        with patch.object(discovery, "discover_services", return_value=[self.pixel_8, self.xiaomi_13, self.s24_ultra, self.s26_ultra]):
            target = discovery.find_target_device()
            self.assertIsNotNone(target)
            self.assertEqual(target.properties.get("model"), "SM-S948U")
            self.assertEqual(target.ip_address, "192.168.1.150")
            self.assertEqual(target.port, 38491)

    def test_find_target_prioritizes_samsung_when_no_s26_ultra(self):
        discovery = ADBMDNSDiscovery()
        with patch.object(discovery, "discover_services", return_value=[self.pixel_8, self.xiaomi_13, self.s24_ultra]):
            target = discovery.find_target_device()
            self.assertIsNotNone(target)
            self.assertEqual(target.properties.get("model"), "SM-S928U")
            self.assertEqual(target.ip_address, "192.168.1.151")

    def test_find_target_falls_back_to_any_device_when_no_samsung(self):
        discovery = ADBMDNSDiscovery()
        with patch.object(discovery, "discover_services", return_value=[self.pixel_8, self.xiaomi_13]):
            target = discovery.find_target_device()
            self.assertIsNotNone(target)
            self.assertEqual(target.ip_address, "192.168.1.160")

    def test_find_target_respects_preferred_serial(self):
        discovery = ADBMDNSDiscovery()
        with patch.object(discovery, "discover_services", return_value=[self.s26_ultra, self.s24_ultra, self.pixel_8]):
            target = discovery.find_target_device(preferred_serial="R5CX928001")
            self.assertIsNotNone(target)
            self.assertEqual(target.properties.get("serial"), "R5CX928001")

            target_pixel = discovery.find_target_device(preferred_serial="38291FDJ")
            self.assertIsNotNone(target_pixel)
            self.assertEqual(target_pixel.properties.get("model"), "Pixel 8 Pro")

    def test_s26_ultra_name_heuristic(self):
        svc_by_name = DiscoveredADBService(
            name="Galaxy-S26-Ultra._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            ip_address="192.168.1.99",
            port=39999,
            properties={},
        )
        self.assertTrue(svc_by_name.is_s26_ultra)
        self.assertTrue(svc_by_name.is_samsung)

class TestScenario3DynamicPortAndIPExtraction(unittest.TestCase):
    def test_extract_ip_from_parsed_addresses(self):
        info = MockServiceInfo(parsed_addresses_list=["192.168.1.200", "::1"])
        ip = extract_ip_address(info)
        self.assertEqual(ip, "192.168.1.200")

    def test_extract_ip_skips_localhost_and_ipv6_when_ipv4_present(self):
        info = MockServiceInfo(parsed_addresses_list=["127.0.0.1", "2001:db8::1", "10.0.0.42"])
        ip = extract_ip_address(info)
        self.assertEqual(ip, "10.0.0.42")

    def test_extract_ip_from_raw_byte_addresses(self):
        raw_ip = socket.inet_aton("192.168.1.77")
        info = MockServiceInfo(addresses=[raw_ip])
        ip = extract_ip_address(info)
        self.assertEqual(ip, "192.168.1.77")

    def test_extract_ip_from_ipv6_raw_bytes_fallback(self):
        raw_ipv6 = socket.inet_pton(socket.AF_INET6, "fe80::1")
        info = MockServiceInfo(addresses=[raw_ipv6])
        ip = extract_ip_address(info)
        self.assertEqual(ip, "fe80::1")

    def test_extract_ip_from_legacy_address_attribute(self):
        raw_ip = socket.inet_aton("172.16.0.5")
        info_bytes = MockServiceInfo(address=raw_ip)
        self.assertEqual(extract_ip_address(info_bytes), "172.16.0.5")

        info_str = MockServiceInfo(address="172.16.0.6")
        self.assertEqual(extract_ip_address(info_str), "172.16.0.6")

    def test_extract_ip_returns_none_on_invalid_addresses(self):
        self.assertIsNone(extract_ip_address(MockServiceInfo(addresses=[])))
        self.assertIsNone(extract_ip_address(MockServiceInfo(addresses=[b"bad", b"123"])))
        self.assertIsNone(extract_ip_address(None))

    def test_ports_standard_vs_ephemeral_tls(self):
        test_ports = [5555, 30001, 37419, 42195, 50000, 65535]
        for p in test_ports:
            svc = DiscoveredADBService(
                name="test",
                service_type="_adb-tls-connect._tcp.local.",
                ip_address="192.168.1.50",
                port=p,
            )
            self.assertEqual(svc.port, p)
            self.assertEqual(svc.endpoint, f"192.168.1.50:{p}")

    def test_listener_and_discovery_with_ephemeral_port(self):
        raw_ip = socket.inet_aton("192.168.1.105")
        info = MockServiceInfo(
            name="Samsung S26 Ultra Wireless Debugging._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            port=43892,
            addresses=[raw_ip],
            properties={b"model": b"SM-S948U", b"serial": b"R5CX948TEST"},
        )
        listener = ADBMDNSListener()
        mock_zc = MagicMock()
        mock_zc.get_service_info.return_value = info

        listener.add_service(mock_zc, "_adb-tls-connect._tcp.local.", info.name)

        self.assertEqual(len(listener.discovered_infos), 1)
        extracted_ip = extract_ip_address(listener.discovered_infos[0])
        extracted_props = parse_service_properties(listener.discovered_infos[0])
        self.assertEqual(extracted_ip, "192.168.1.105")
        self.assertEqual(listener.discovered_infos[0].port, 43892)
        self.assertEqual(extracted_props.get("model"), "SM-S948U")

class TestScenario4CLIArgumentParsing(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()

    def test_default_cli_arguments(self):
        args = self.parser.parse_args([])
        self.assertTrue(args.enable_mdns)
        self.assertEqual(args.mdns_timeout, 5.0)
        self.assertIsNone(args.connect)

    def test_explicit_mdns_flags(self):
        args1 = self.parser.parse_args(["--mdns"])
        self.assertTrue(args1.enable_mdns)

        args2 = self.parser.parse_args(["--auto-discover"])
        self.assertTrue(args2.enable_mdns)

    def test_no_mdns_flag(self):
        args = self.parser.parse_args(["--no-mdns"])
        self.assertFalse(args.enable_mdns)

    def test_mdns_timeout_flag(self):
        args = self.parser.parse_args(["--mdns-timeout", "12.5"])
        self.assertEqual(args.mdns_timeout, 12.5)

    def test_connect_flag(self):
        args = self.parser.parse_args(["--connect", "192.168.1.100:39481"])
        self.assertEqual(args.connect, "192.168.1.100:39481")

    def test_combined_cli_flags(self):
        args = self.parser.parse_args([
            "--no-mdns",
            "--connect", "10.0.0.50:5555",
            "--device", "10.0.0.50:5555",
            "--recent", "5",
            "--inbox-only",
        ])
        self.assertFalse(args.enable_mdns)
        self.assertEqual(args.connect, "10.0.0.50:5555")
        self.assertEqual(args.device, "10.0.0.50:5555")
        self.assertEqual(args.recent, 5)
        self.assertTrue(args.inbox_only)

class TestScenario5AdversarialEdgeCasesAndErrorHandling(unittest.TestCase):
    def test_parse_service_properties_with_corrupt_non_utf8_bytes(self):
        info = MockServiceInfo()
        info.properties = {
            b"model": b"SM-S948U\xff\xfe",
            b"serial": b"R5CX123",
            b"invalid_key_\x80\x81": b"test_val",
            123: 456,
            b"none_val": None,
        }
        props = parse_service_properties(info)
        self.assertIn("SM-S948U", props["model"])
        self.assertEqual(props["serial"], "R5CX123")
        self.assertEqual(props["123"], "456")
        self.assertEqual(props["none_val"], "")

    def test_listener_exception_resilience(self):
        listener = ADBMDNSListener()
        failing_zc = MagicMock()
        failing_zc.get_service_info.side_effect = RuntimeError("Socket error")
        listener.add_service(failing_zc, "_adb-tls-connect._tcp.local.", "device1")
        listener.update_service(failing_zc, "_adb-tls-connect._tcp.local.", "device1")
        listener.remove_service(failing_zc, "_adb-tls-connect._tcp.local.", "device1")
        self.assertEqual(len(listener.discovered_infos), 0)

    def test_4_tier_fallback_tier1_explicit_connect(self):
        with patch.object(ADBClient, "__init__", return_value=None):
            with patch.object(ADBClient, "connect_device", return_value=True) as mock_connect:
                mock_dev = ADBDeviceInfo(serial="192.168.1.99:38192", state="device", model="SM-S948U", is_authorized=True, is_samsung=True)
                with patch.object(ADBClient, "select_active_device", return_value=mock_dev):
                    ingestor = SamsungADBIngestor(
                        workspace_root=Path("."),
                        enable_mdns=False,
                        connect_endpoint="192.168.1.99:38192",
                    )
                    selected = ingestor.select_device()
                    mock_connect.assert_called_once_with("192.168.1.99", 38192)
                    self.assertEqual(selected.serial, "192.168.1.99:38192")

    def test_4_tier_fallback_tier2_mdns_auto_discovery(self):
        s26_svc = DiscoveredADBService(
            name="Samsung S26 Ultra._adb-tls-connect._tcp.local.",
            service_type="_adb-tls-connect._tcp.local.",
            ip_address="192.168.1.222",
            port=39182,
            properties={"model": "SM-S948U"},
        )
        mock_dev = ADBDeviceInfo(serial="192.168.1.222:39182", state="device", model="SM-S948U", is_authorized=True, is_samsung=True)

        with patch.object(ADBClient, "__init__", return_value=None):
            with patch.object(ADBMDNSDiscovery, "find_target_device", return_value=s26_svc):
                with patch.object(ADBClient, "connect_device", return_value=True) as mock_connect:
                    with patch.object(ADBClient, "select_active_device", return_value=mock_dev):
                        ingestor = SamsungADBIngestor(
                            workspace_root=Path("."),
                            enable_mdns=True,
                            mdns_timeout=1.0,
                        )
                        selected = ingestor.select_device()
                        mock_connect.assert_called_once_with("192.168.1.222", 39182)
                        self.assertEqual(selected.serial, "192.168.1.222:39182")

    def test_adb_client_connect_device_output_parsing(self):
        with patch.object(ADBClient, "__init__", return_value=None):
            client = ADBClient()
            client.adb_bin = Path("adb")
            client.target_serial = None

            with patch.object(client, "run_cmd", return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="connected to 192.168.1.100:38491\n", stderr="")):
                self.assertTrue(client.connect_device("192.168.1.100", 38491))

            with patch.object(client, "run_cmd", return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="already connected to 192.168.1.100:38491\n", stderr="")):
                self.assertTrue(client.connect_device("192.168.1.100", 38491))

            with patch.object(client, "run_cmd", return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="cannot connect to 192.168.1.100:38491\n", stderr="failed")):
                self.assertFalse(client.connect_device("192.168.1.100", 38491))

if __name__ == "__main__":
    unittest.main(verbosity=2)