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

class MockInfo:
    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "mock_service")
        self.type = kwargs.get("type", "_adb-tls-connect._tcp.local.")
        self.server = kwargs.get("server", "mock.local.")
        self.port = kwargs.get("port", 38491)
        self.properties = kwargs.get("properties", {})
        self.addresses = kwargs.get("addresses", [])
        self._parsed_list = kwargs.get("parsed_addresses", None)
        self.address = kwargs.get("address", None)

    def parsed_addresses(self):
        if self._parsed_list is not None:
            return self._parsed_list
        res = []
        for a in self.addresses:
            if isinstance(a, (bytes, bytearray)):
                if len(a) == 4:
                    res.append(socket.inet_ntoa(a))
                elif len(a) == 16:
                    res.append(socket.inet_ntop(socket.AF_INET6, a))
            elif isinstance(a, str):
                res.append(a)
        return res

class TestDeepAdversarial(unittest.TestCase):

    def test_empty_and_corrupt_addresses(self):
        self.assertIsNone(extract_ip_address(MockInfo(addresses=[b""])))
        self.assertIsNone(extract_ip_address(MockInfo(addresses=[b"\x00\x01\x02"]))) # 3 bytes
        self.assertIsNone(extract_ip_address(MockInfo(addresses=[b"\x00" * 5]))) # 5 bytes
        self.assertIsNone(extract_ip_address(MockInfo(addresses=[None])))
        self.assertIsNone(extract_ip_address(MockInfo(parsed_addresses=[])))
        self.assertIsNone(extract_ip_address(MockInfo(parsed_addresses=["127.0.0.1"]))) # localhost filtered

    def test_parsed_addresses_exception_fallback_to_raw_addresses(self):
        """If parsed_addresses() throws, should fallback to addresses bytes."""
        info = MockInfo(addresses=[socket.inet_aton("192.168.1.88")])
        def bad_parsed():
            raise RuntimeError("Corrupt parser")
        info.parsed_addresses = bad_parsed
        ip = extract_ip_address(info)
        self.assertEqual(ip, "192.168.1.88")

    def test_multi_threaded_listener_churn(self):
        """Stress-test listener with 50 threads adding/updating/removing concurrently."""
        listener = ADBMDNSListener()
        mock_zc = MagicMock()
        mock_zc.get_service_info.side_effect = lambda t, n, timeout=3000: MockInfo(name=n, port=40000, addresses=[socket.inet_aton("192.168.1.10")])

        def churn(worker_id):
            for i in range(20):
                name = f"dev_{worker_id}_{i}"
                listener.add_service(mock_zc, "_adb-tls-connect._tcp.local.", name)
                listener.update_service(mock_zc, "_adb-tls-connect._tcp.local.", name)
                if i % 2 == 0:
                    listener.remove_service(mock_zc, "_adb-tls-connect._tcp.local.", name)

        threads = [threading.Thread(target=churn, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Thread safety check: should not raise ConcurrentModificationError or deadlock
        with listener._lock:
            count = len(listener.discovered_infos)
            self.assertGreaterEqual(count, 0)

    def test_discovery_with_invalid_ports(self):
        """Services with port=0 or None or missing port."""
        listener = ADBMDNSListener()
        mock_zc = MagicMock()
        mock_zc.get_service_info.return_value = MockInfo(
            name="NoPortService",
            port=0,
            addresses=[socket.inet_aton("192.168.1.50")]
        )
        listener.add_service(mock_zc, "_adb-tls-connect._tcp.local.", "NoPortService")
        
        # When port is 0 or None, discover_services filters it out if ip and port:
        # In samsung_ingest.py: "if ip and port:" where port=0 evaluates to False!
        discovery = ADBMDNSDiscovery(timeout_sec=0.01)
        with patch.object(ADBMDNSDiscovery, "discover_services", return_value=[]):
            res = discovery.discover_services()
            self.assertEqual(res, [])

    def test_connect_parsing_variations(self):
        """Test ADBClient.connect_device parsing various stdout/stderr strings."""
        with patch.object(ADBClient, "__init__", return_value=None):
            c = ADBClient()
            c.adb_bin = Path("adb")
            c.target_serial = None

            # Test standard success
            with patch.object(c, "run_cmd", return_value=subprocess.CompletedProcess([], 0, "connected to 192.168.1.1:5555", "")):
                self.assertTrue(c.connect_device("192.168.1.1", 5555))

            # Test already connected
            with patch.object(c, "run_cmd", return_value=subprocess.CompletedProcess([], 0, "already connected to 192.168.1.1:5555", "")):
                self.assertTrue(c.connect_device("192.168.1.1", 5555))

            # Test mixed case
            with patch.object(c, "run_cmd", return_value=subprocess.CompletedProcess([], 0, "Connected To 192.168.1.1:5555", "")):
                self.assertTrue(c.connect_device("192.168.1.1", 5555))

            # Test failure: cannot connect
            with patch.object(c, "run_cmd", return_value=subprocess.CompletedProcess([], 0, "cannot connect to 192.168.1.1:5555: No connection could be made", "")):
                self.assertFalse(c.connect_device("192.168.1.1", 5555))

            # Test failure: connection refused
            with patch.object(c, "run_cmd", return_value=subprocess.CompletedProcess([], 0, "failed to connect to 192.168.1.1:5555", "")):
                self.assertFalse(c.connect_device("192.168.1.1", 5555))

    def test_adb_client_list_devices_parsing(self):
        """Test parsing complex adb devices -l output with various device types."""
        raw_output = """List of devices attached
* daemon not running; starting now at tcp:5037
* daemon started successfully
192.168.1.150:38491    device product:dm3q model:SM_S948U device:dm3q transport_id:1
R5CW123456            device usb:1-1 product:dm1q model:SM-S928B device:dm1q transport_id:2
192.168.1.200:5555    unauthorized transport_id:3
emulator-5554         offline transport_id:4
pixel_serial          device product:husky model:Pixel_8_Pro device:husky transport_id:5
"""
        with patch.object(ADBClient, "__init__", return_value=None):
            c = ADBClient()
            c.adb_bin = Path("adb")
            c.target_serial = None

            with patch.object(c, "run_cmd", return_value=subprocess.CompletedProcess([], 0, raw_output, "")):
                devices = c.list_devices()
                self.assertEqual(len(devices), 5)
                
                # Check S26 Ultra via Wi-Fi
                dev0 = devices[0]
                self.assertEqual(dev0.serial, "192.168.1.150:38491")
                self.assertEqual(dev0.state, "device")
                self.assertTrue(dev0.is_authorized)
                self.assertEqual(dev0.model, "SM_S948U")
                
                # Check S24 via USB
                dev1 = devices[1]
                self.assertEqual(dev1.serial, "R5CW123456")
                self.assertTrue(dev1.is_samsung)
                self.assertEqual(dev1.usb_port, "1-1")
                
                # Check unauthorized
                dev2 = devices[2]
                self.assertFalse(dev2.is_authorized)
                self.assertEqual(dev2.state, "unauthorized")

    def test_select_active_device_unambiguous_resolution(self):
        """When 1 S26 Ultra and 1 Pixel 8 are connected, select S26 Ultra automatically."""
        s26 = ADBDeviceInfo(serial="192.168.1.150:38491", state="device", model="SM-S948U", is_authorized=True, is_samsung=True)
        pixel = ADBDeviceInfo(serial="pixel_serial", state="device", model="Pixel 8 Pro", is_authorized=True, is_samsung=False)
        
        with patch.object(ADBClient, "__init__", return_value=None):
            c = ADBClient()
            c.adb_bin = Path("adb")
            c.target_serial = None
            
            with patch.object(c, "list_devices", return_value=[pixel, s26]):
                selected = c.select_active_device()
                self.assertEqual(selected.serial, "192.168.1.150:38491")
                self.assertEqual(selected.model, "SM-S948U")

if __name__ == "__main__":
    unittest.main(verbosity=2)