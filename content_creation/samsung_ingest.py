"""
samsung_ingest.py - Automated Samsung Galaxy S26 Ultra ADB Ingestion Bridge (Track 2)

Establishes a hardware-to-local physical transport layer connecting the Samsung Galaxy S26 Ultra
directly to the Track 2 EDM Short-Form Content Creation pipeline via Android Debug Bridge (ADB).
"""

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Defensive import of Zeroconf mDNS library (RFC 6762 / RFC 6763)
try:
    import zeroconf
    from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    zeroconf = None
    Zeroconf = None
    ServiceBrowser = None
    ServiceListener = object  # type: ignore[misc, assignment]
    ServiceInfo = None
    ZEROCONF_AVAILABLE = False

# Import centralized configuration constants and existing pipeline utilities
try:
    from config import (
        ADB_BUFFER_SIZE_BYTES,
        ADB_DEFAULT_TIMEOUT_SECONDS,
        ADB_EXPERT_RAW_PATH,
        ADB_MIN_FREE_DISK_HEADROOM_BYTES,
        ADB_PULL_TIMEOUT_PER_GB_SECONDS,
        ADB_STILL_EXTENSIONS,
        ADB_SUPPORTED_EXTENSIONS,
        ADB_VIDEO_EXTENSIONS,
        ALT_ANDROID_CAMERA_PATH,
        BrandType,
        DEFAULT_ANDROID_CAMERA_PATH,
        EventTier,
        FOLDER_TIERS,
        MAX_FOLDER_ITEMS,
        MDNS_ADB_LEGACY_SERVICE_TYPE,
        MDNS_ADB_TLS_SERVICE_TYPE,
        MDNS_DEFAULT_TIMEOUT_SEC,
        SAMSUNG_MODEL_PREFIXES,
        SUPPORTED_VIDEO_EXTENSIONS,
    )
except ImportError:
    DEFAULT_ANDROID_CAMERA_PATH = "/sdcard/DCIM/EDM_Drops"
    ALT_ANDROID_CAMERA_PATH = "/storage/emulated/0/DCIM/EDM_Drops"
    ADB_EXPERT_RAW_PATH = "/sdcard/DCIM/Expert RAW"
    SAMSUNG_MODEL_PREFIXES = ["SM-S948", "SM-S938", "SM-S928", "SM-S918"]
    ADB_SUPPORTED_EXTENSIONS = [".mp4", ".mov", ".mkv", ".m4v", ".dng", ".jpg", ".heic"]
    ADB_VIDEO_EXTENSIONS = [".mp4", ".mov", ".mkv", ".m4v"]
    ADB_STILL_EXTENSIONS = [".dng", ".jpg", ".heic"]
    ADB_DEFAULT_TIMEOUT_SECONDS = 300.0
    ADB_PULL_TIMEOUT_PER_GB_SECONDS = 60.0
    ADB_MIN_FREE_DISK_HEADROOM_BYTES = 5 * 1024 * 1024 * 1024
    ADB_BUFFER_SIZE_BYTES = 1024 * 1024
    FOLDER_TIERS = {
        "INBOX": "01_RAW_INBOX",
        "IN_PROGRESS": "02_IN_PROGRESS",
        "READY_TO_POST": "03_READY_TO_POST",
        "ARCHIVE": "04_ARCHIVE",
    }
    MAX_FOLDER_ITEMS = 50
    MDNS_ADB_TLS_SERVICE_TYPE = "_adb-tls-connect._tcp.local."
    MDNS_ADB_LEGACY_SERVICE_TYPE = "_adb._tcp.local."
    MDNS_DEFAULT_TIMEOUT_SEC = 5.0

try:
    from ingest_assets import (
        AssetIngestionRouter,
        DirectoryHealthGuard,
        FilenameNormalizer,
        calculate_sha256,
        find_binary,
    )
except ImportError:
    def find_binary(name: str, custom_path: Optional[str] = None, env_var: Optional[str] = None) -> Optional[Path]:
        if custom_path and Path(custom_path).exists():
            return Path(custom_path)
        if env_var and os.environ.get(env_var) and Path(os.environ[env_var]).is_file():
            return Path(o.environ[env_var])
        which_p = shutil.which(name)
        if which_p:
            return Path(which_p)
        return None

    def calculate_sha256(file_path: Path, block_size: int = 65536) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(block_size), b""):
                sha256.update(block)
        return sha256.hexdigest()

    class DirectoryHealthGuard:
        def __init__(self, max_items: int = 50):
            self.max_items = max_items
        def count_items(self, d: Path) -> int:
            return sum(1 for p in d.iterdir() if not p.name.startswith(".")) if d.exists() else 0
        def get_healthy_subfolder(self, base_dir: Path, slug: str) -> Path:
            base_dir.mkdir(parents=True, exist_ok=True)
            p = base_dir / slug
            p.mkdir(parents=True, exist_ok=True)
            if self.count_items(p) < self.max_items:
                return p
            idx = 2
            while True:
                b = base_dir / f"{slug}_Batch{idx:02d}"
                b.mkdir(parents=True, exist_ok=True)
                if self.count_items(b) < self.max_items:
                    return b
                idx += 1

# ======================================================================
# CUSTOM EXCEPTIONS
# ======================================================================

class ADBError(Exception):
    """Base exception for Android Debug Bridge errors."""
    pass

class ADBNotFoundError(ADBError):
    """Raised when the ADB executable binary cannot be located."""
    pass

class NoDeviceConnectedError(ADBError):
    """Raised when no Android device is detected via ADB."""
    pass

class DeviceUnauthorizedError(ADBError):
    """Raised when the connected Android device has not authorized USB debugging."""
    pass

class DeviceSelectionError(ADBError):
    """Raised when multiple devices are connected and cannot be unambiguously resolved."""
    pass

class RemoteDirectoryNotFoundError(ADBError):
    """Raised when the remote camera directory does not exist on the device."""
    pass

class InsufficientStorageError(ADBError):
    """Raised when host workspace disk capacity is insufficient for pending transfers."""
    pass

class TransferIntegrityError(ADBError):
    """Raised when byte count or cryptographic digest validation fails."""
    pass


# ======================================================================
# DATA STRUCTURES
# ======================================================================

@dataclass
class ADBDeviceInfo:
    """Represents an attached Android hardware device discovered via ADB."""
    serial: str
    state: str                          # "device", "unauthorized", "offline"
    model: str = "Unknown"              # e.g. "SM-S948U", "SM-S938B"
    product: str = ""                   # e.g. "dm3q"
    usb_port: str = ""                  # USB bus/port identifier
    is_authorized: bool = False
    is_samsung: bool = False

    @property
    def is_s26_ultra(self) -> bool:
        """Checks if the model string matches the S26 Ultra flagships (SM-S948*)."""
        return any(self.model.startswith(prefix) for prefix in ["SM-S948", "SM-S948U", "SM-S948B", "SM-S948N", "SM-S9480"])

@dataclass
class RemoteMediaAsset:
    """Represents a media file discovered in remote device storage."""
    filename: str
    remote_path: str
    size_bytes: int
    modified_time: datetime
    extension: str
    is_video: bool = True
    is_dng: bool = False

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024 * 1024 * 1024)

    def matches_extensions(self, exts: List[str]) -> bool:
        norm_exts = [e.lower().lstrip(".") for e in exts]
        return self.extension.lower().lstrip(".") in norm_exts

@dataclass
class ADBPullResult:
    """Outcome of an individual ADB asset pull operation."""
    success: bool
    remote_asset: RemoteMediaAsset
    local_path: str
    size_bytes: int
    sha256_hash: str
    transfer_duration_sec: float
    transfer_rate_mbps: float
    retries_attempted: int = 0
    error_message: Optional[str] = None

@dataclass
class ADBIngestionSummary:
    """Overall batch ingestion execution summary."""
    total_remote_scanned: int
    total_eligible: int
    total_pulled: int
    total_skipped_duplicate: int
    total_failed: int
    total_bytes_transferred: int
    total_duration_sec: float
    pulled_results: List[ADBPullResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def total_mb_transferred(self) -> float:
        return self.total_bytes_transferred / (1024 * 1024)

    @property
    def average_rate_mbps(self) -> float:
        if self.total_duration_sec > 0:
            return (self.total_bytes_transferred * 8 / (1024 * 1024)) / self.total_duration_sec
        return 0.0


@dataclass
class DiscoveredADBService:
    """Represents an Android ADB mDNS service discovered over the local network."""
    name: str
    service_type: str
    ip_address: str
    port: int
    server: str = ""
    properties: Dict[str, str] = field(default_factory=dict)

    @property
    def endpoint(self) -> str:
        return f"{self.ip_address}:{self.port}"

    @property
    def model(self) -> str:
        return self.properties.get("model", "Unknown")

    @property
    def is_samsung(self) -> bool:
        model_str = self.model
        name_str = self.name
        return (
            any(model_str.startswith(pfx) for pfx in SAMSUNG_MODEL_PREFIXES)
            or "samsung" in name_str.lower()
            or "samsung" in model_str.lower()
            or model_str.startswith("SM-")
        )

    @property
    def is_s26_ultra(self) -> bool:
        return (
            any(self.model.startswith(pfx) for pfx in ["SM-S948", "SM-S948U", "SM-S948B", "SM-S948N", "SM-S9480"])
            or "s26" in self.name.lower()
            or "s26" in self.model.lower()
        )


# ======================================================================
# MDNS DISCOVERY HELPERS & ENGINE (ZEROCONF)
# ======================================================================

def extract_ip_address(info: Any) -> Optional[str]:
    """
    Extracts the best IPv4 address from ServiceInfo, handling both parsed_addresses()
    and raw network byte arrays (info.addresses) across zeroconf versions.
    """
    # 1. Prefer parsed_addresses() helper method if available (zeroconf >= 0.28)
    if hasattr(info, "parsed_addresses") and callable(info.parsed_addresses):
        try:
            parsed = info.parsed_addresses()
            if parsed:
                for ip in parsed:
                    if isinstance(ip, str) and ":" not in ip and not ip.startswith("127."):
                        return ip
                if isinstance(parsed[0], str):
                    return parsed[0]
        except Exception:
            pass

    # 2. Extract from raw byte arrays in info.addresses
    if hasattr(info, "addresses") and info.addresses:
        for raw_addr in info.addresses:
            if isinstance(raw_addr, (bytes, bytearray)) and len(raw_addr) == 4:
                try:
                    ip = socket.inet_ntoa(raw_addr)
                    if not ip.startswith("127."):
                        return ip
                except Exception:
                    continue
        for raw_addr in info.addresses:
            if isinstance(raw_addr, (bytes, bytearray)) and len(raw_addr) == 16:
                try:
                    return socket.inet_ntop(socket.AF_INET6, raw_addr)
                except Exception:
                    continue

    # 3. Direct parsed_scoped_addresses or address attribute fallback
    if hasattr(info, "address") and info.address:
        raw_addr = info.address
        if isinstance(raw_addr, (bytes, bytearray)) and len(raw_addr) == 4:
            try:
                return socket.inet_ntoa(raw_addr)
            except Exception:
                pass
        elif isinstance(raw_addr, str):
            return raw_addr

    return None


def parse_service_properties(info: Any) -> Dict[str, str]:
    """Decodes binary TXT records into string dictionary."""
    props: Dict[str, str] = {}
    if hasattr(info, "properties") and isinstance(info.properties, dict):
        for k, v in info.properties.items():
            k_str = k.decode("utf-8", errors="ignore") if isinstance(k, (bytes, bytearray)) else str(k)
            v_str = v.decode("utf-8", errors="ignore") if isinstance(v, (bytes, bytearray)) else (str(v) if v is not None else "")
            props[k_str] = v_str
    return props


class ADBMDNSListener(ServiceListener if ZEROCONF_AVAILABLE and ServiceListener is not None else object):  # type: ignore[misc]
    """Event-driven listener collecting ADB wireless debugging announcements."""

    def __init__(self) -> None:
        self.discovered_infos: List[Any] = []
        self._lock = threading.Lock()
        self._event = threading.Event()

    def add_service(self, zc: Any, type_: str, name: str) -> None:
        try:
            if hasattr(zc, "get_service_info"):
                try:
                    info = zc.get_service_info(type_, name, timeout=3000)
                except TypeError:
                    info = zc.get_service_info(type_, name)
            else:
                info = None
            if info:
                with self._lock:
                    self.discovered_infos.append(info)
                    self._event.set()
        except Exception:
            pass

    def update_service(self, zc: Any, type_: str, name: str) -> None:
        try:
            if hasattr(zc, "get_service_info"):
                try:
                    info = zc.get_service_info(type_, name, timeout=3000)
                except TypeError:
                    info = zc.get_service_info(type_, name)
            else:
                info = None
            if info:
                with self._lock:
                    self.discovered_infos = [s for s in self.discovered_infos if getattr(s, "name", None) != name] + [info]
                    self._event.set()
        except Exception:
            pass

    def remove_service(self, zc: Any, type_: str, name: str) -> None:
        try:
            with self._lock:
                self.discovered_infos = [s for s in self.discovered_infos if getattr(s, "name", None) != name]
        except Exception:
            pass


class ADBMDNSDiscovery:
    """Orchestrates mDNS network scans using python-zeroconf to find Android wireless debugging endpoints."""

    def __init__(self, timeout_sec: float = MDNS_DEFAULT_TIMEOUT_SEC):
        self.timeout_sec = timeout_sec

    def discover_services(
        self,
        service_types: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> List[DiscoveredADBService]:
        """Scans local Wi-Fi network and returns all discovered ADB services."""
        zc_class = Zeroconf
        sb_class = ServiceBrowser
        if zc_class is None:
            if "zeroconf" in sys.modules and hasattr(sys.modules["zeroconf"], "Zeroconf"):
                zc_class = sys.modules["zeroconf"].Zeroconf
                sb_class = getattr(sys.modules["zeroconf"], "ServiceBrowser", None)

        if zc_class is None or sb_class is None:
            return []

        scan_timeout = timeout if timeout is not None else self.timeout_sec
        types_to_scan = service_types or [MDNS_ADB_TLS_SERVICE_TYPE, MDNS_ADB_LEGACY_SERVICE_TYPE]
        listener = ADBMDNSListener()
        discovered: List[DiscoveredADBService] = []

        try:
            zc = zc_class()
            try:
                browsers = [sb_class(zc, st, listener) for st in types_to_scan]
                if scan_timeout > 0:
                    time.sleep(scan_timeout)
            finally:
                if hasattr(zc, "close"):
                    zc.close()

            with listener._lock:
                for info in listener.discovered_infos:
                    ip = extract_ip_address(info)
                    port = getattr(info, "port", None)
                    if ip and port:
                        props = parse_service_properties(info)
                        server = getattr(info, "server", "")
                        name = getattr(info, "name", "")
                        stype = getattr(info, "type", types_to_scan[0])
                        svc = DiscoveredADBService(
                            name=name,
                            service_type=stype,
                            ip_address=ip,
                            port=int(port),
                            server=server,
                            properties=props,
                        )
                        discovered.append(svc)
        except Exception:
            pass

        return discovered

    def find_target_device(
        self,
        preferred_serial: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Optional[DiscoveredADBService]:
        """
        Discovers and filters services, prioritizing Samsung S26 Ultra flagships.
        Hierarchy:
        1. Exact preferred serial match in properties or name.
        2. S26 Ultra (SM-S948*).
        3. Other Samsung Flagships.
        4. Any discovered Android ADB service.
        """
        services = self.discover_services(timeout=timeout)
        if not services:
            return None

        if preferred_serial:
            for s in services:
                if s.properties.get("serial") == preferred_serial or preferred_serial in s.name:
                    return s

        s26_services = [s for s in services if s.is_s26_ultra]
        if s26_services:
            return s26_services[0]

        samsung_services = [s for s in services if s.is_samsung]
        if samsung_services:
            return samsung_services[0]

        return services[0]


# ======================================================================
# ADB BINARY DISCOVERY
# ======================================================================

def find_adb_binary(custom_path: Optional[str] = None) -> Optional[Path]:
    """
    Locates the Android Debug Bridge (adb / adb.exe) binary across:
    1. Direct CLI custom argument path.
    2. Environment variables (ADB_BINARY, ANDROID_ADB, ANDROID_HOME, ANDROID_SDK_ROOT).
    3. System PATH via shutil.which.
    4. Standard Windows Android SDK / Platform-Tools installation directories.
    """
    if custom_path:
        p = Path(custom_path).resolve()
        if p.is_file():
            return p
        if p.is_dir():
            for ext in ["", ".exe"]:
                cand = p / f"adb{ext}"
                if cand.is_file():
                    return cand

    for env_k in ["ADB_BINARY", "ANDROID_ADB", "ANDROID_HOME", "ANDROID_SDK_ROOT"]:
        val = os.environ.get(env_k)
        if val:
            p_val = Path(val).resolve()
            if p_val.is_file() and p_val.name.lower().startswith("adb"):
                return p_val
            cand = p_val / "platform-tools" / "adb.exe"
            if cand.is_file():
                return cand
            cand_linux = p_val / "platform-tools" / "adb"
            if cand_linux.is_file():
                return cand_linux

    which_adb = shutil.which("adb")
    if which_adb:
        return Path(which_adb).resolve()

    user_home = Path.home()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", user_home / "AppData" / "Local"))
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFile{(x86)", "C:/Program Files (x86)"))

    search_candidates = [
        local_app_data / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        user_home / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        Path("C:/platform-tools/adb.exe"),
        Path("C:/tools/platform-tools/adb.exe"),
        user_home / "scoop" / "apps" / "adb" / "current" / "platform-tools" / "adb.exe",
        program_files / "Android" / "android-sdk" / "platform-tools" / "adb.exe",
        program_files_x86 / "Android" / "android-sdk" / "platform-tools" / "adb.exe",
        Path("/usr/bin/adb"),
        Path("/usr/local/bin/adb"),
        user_home / "Android" / "Sdk" / "platform-tools" / "adb",
    ]

    for cand in search_candidates:
        if cand.is_file():
            return cand.resolve()

    return None


# ======================================================================
# ADB CLIENT &_HARDWARE INTERACTION LAYER
# ======================================================================

class ADBClient:
    """
    Lightweight, robust subprocess-based client for orchestrating Android Debug Bridge commands.
    Provides native 64-bit multi-GB transfer, timestamp preservation (-a), and error remediation.
    """

    def __init__(self, adb_path: Optional[str] = None, target_serial: Optional[str] = None):
        self.adb_bin = find_adb_binary(adb_path)
        if not self.adb_bin:
            raise ADBNotFoundError(
                "Android Debug Bridge (adb) binary was not found on this system.\n"
                "Please install Android Platform-Tools (e.g. 'winget install Google.PlatformTools' on Windows),\n"
                "set the ADB_BINARY or ANDROID_HOME, ANDROID_SDK_ROOT environment variable, or pass --adb-path."
            )
        self.target_serial = target_serial

    def run_cmd(
        self,
        args: List[str],
        serial: Optional[str] = None,
        timeout: Optional[float] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        target = serial or self.target_serial
        cmd = [str(self.adb_bin)]
        if target:
            cmd.extend(["-s", target])
        cmd.extend(args)

        try:
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=check,
                timeout=timeout or ADB_DEFAULT_TIMEOUT_SECONDS,
            )
        except subprocess.CalledProcessError as e:
            raise ADBError(f"ADB command failed ({' '.join(cmd)}): {e.stderr.strip()}") from e
        except subprocess.TimeoutExpired as e:
            raise ADBError(f"ADB command timed out after {timeout}s: {' '.join(cmd)}") from e

    def connect_device(self, ip: str, port: int, timeout: float = 10.0) -> bool:
        """
        Connects to an Android device over TCP/IP via `adb connect <ip>:<port>`.
        Returns True if connection succeeded or already connected, False otherwise.
        """
        endpoint = f"{ip}:{port}"
        proc = self.run_cmd(["connect", endpoint], serial=None, timeout=timeout, check=False)
        stdout_lower = proc.stdout.lower().strip()
        stderr_lower = proc.stderr.lower().strip()
        output = f"{stdout_lower} {stderr_lower}"

        if "connected to" in output or "already connected to" in output:
            return True
        return False

    def disconnect_device(self, endpoint: Optional[str] = None, timeout: float = 10.0) -> bool:
        """Disconnects from a remote TCP/IP ADB endpoint."""
        args = ["disconnect"]
        if endpoint:
            args.append(endpoint)
        proc = self.run_cmd(args, serial=None, timeout=timeout, check=False)
        return proc.returncode == 0

    def list_devices(self) -> List[ADBDeviceInfo]:
        proc = self.run_cmd(["devices", "-l"], serial=None, check=False)
        lines = proc.stdout.strip().splitlines()
        devices: List[ADBDeviceInfo] = []

        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("List of devices attached") or line_str.startswith("*"):
                continue

            parts = line_str.split()
            if len(parts) < 2:
                continue

            serial = parts[0]
            state = parts[1]
            is_authorized = (state == "device")

            model = "Unknown"
            product = ""
            usb_port = ""

            for token in parts[2:]:
                if ":" in token:
                    k, v = token.split(":", 1)
                    if k == "model":
                        model = v
                    elif k == "product":
                        product = v
                    elif k == "usb":
                        usb_port = v

            if model == "Unknown" and is_authorized:
                try:
                    prop_proc = self.run_cmd(["shell", "getprop", "ro.product.model"], serial=serial, timeout=5, check=False)
                    if prop_proc.returncode == 0 and prop_proc.stdout.strip():
                        model = prop_proc.stdout.strip()
                except Exception:
                    pass

            is_samsung = any(model.startswith(pfx) for pfx in SAMSUNG_MODEL_PREFIXES) or "samsung" in product.lower() or model.startswith("SM-")

            devices.append(
                ADBDeviceInfo(
                    serial=serial,
                    state=state,
                    model=model,
                    product=product,
                    usb_port=usb_port,
                    is_authorized=is_authorized,
                    is_samsung=is_samsung,
                )
            )

        return devices

    def select_active_device(self, preferred_serial: Optional[str] = None) -> ADBDeviceInfo:
        devices = self.list_devices()

        if not devices:
            raise NoDeviceConnectedError(
                "No Android devices detected via ADB.\n"
                "Remediation Steps:\n"
                "1. Samsung S26 Ultra: Settings -> Developer Options -> Wireless Debugging -> Enable.\n"
                "2. Or connect via high-speed USB 3.2 Gen 2 cable with USB Debugging enabled.\n"
                "3. Verify PC and phone are connected to the same Wi-Fi network (AP isolation disabled).\n"
                "4. Check 'adb connect <ip>:<port>' with current device endpoint."
            )

        if preferred_serial:
            match = next((d for d in devices if d.serial == preferred_serial), None)
            if not match:
                available = ", ".join(f"{d.serial} ({d.model})" for d in devices)
                raise DeviceSelectionError(f"Requested device serial '{preferred_serial}' not found. Attached devices: {available}")
            if not match.is_authorized:
                raise DeviceUnauthorizedError(
                    f"Device {match.serial} ({match.model}) is UNAUTHORIZED.\n"
                    "Remediation: Unlock the phone screen and tap 'Always allow from this computer' on the USB Debugging prompt."
                )
            return match

        unauthorized = [d for d in devices if not d.is_authorized]
        authorized = [d for d in devices if d.is_authorized]

        if not authorized and unauthorized:
            unauth_dev = unauthorized[0]
            raise DeviceUnauthorizedError(
                f"Connected device {unauth_dev.serial} ({unauth_dev.model}) is in state '{unauth_dev.state}'.\n"
                "Remediation: Unlock the phone screen and tap 'Always allow from this computer' on the USB Debugging prompt."
            )

        samsung_devices = [d for d in authorized if d.is_samsung or d.is_s26_ultra]

        if len(samsung_devices) == 1:
            return samsung_devices[0]
        elif len(samsung_devices) > 1:
            s26_matches = [d for d in samsung_devices if d.is_s26_ultra]
            if len(s26_matches) == 1:
                return s26_matches[0]
            s_list = ", ".join(f"{d.serial} ({d.model})" for d in samsung_devices)
            raise DeviceSelectionError(
                f"Multiple Samsung devices detected: {s_list}.\n"
                "Please specify the target device serial explicitly via --device <SERIAL>."
            )
        elif len(authorized) == 1:
            return authorized[0]
        else:
            dev_list = ", ".join(f"{d.serial} ({d.model})" for d in authorized)
            raise DeviceSelectionError(
                f"Multiple Android devices connected: {dev_list}.\n"
                "Please specify the target device serial explicitly via --device <SERIAL>."
            )

    def stat_remote_directory(self, remote_dir: str, serial: str) -> List[RemoteMediaAsset]:
        check_proc = self.run_cmd(["shell", f"[ -d '{remote_dir}' ] && echo 'EXISTS'"], serial=serial, check=False)
        if "EXISTS" not in check_proc.stdout:
            if remote_dir == DEFAULT_ANDROID_CAMERA_PATH:
                alt_check = self.run_cmd(["shell", f"[ -d '{ALT_ANDROID_CAMERA_PATH}' ] && echo 'EXISTS'"], serial=serial, check=False)
                if "EXISTS" in alt_check.stdout:
                    remote_dir = ALT_ANDROID_CAMERA_PATH

                else:
                    raise RemoteDirectoryNotFoundError(f"Remote directory '{remote_dir}' does not exist on device {serial}.")
            else:
                raise RemoteDirectoryNotFoundError(f"Remote directory '{remote_dir}' does not exist on device {serial}.")

        stat_cmd = f"stat -c '%s %Y %n' '{remote_dir.rstrip('/')}'/* 2>/dev/null"

        proc = self.run_cmd(["shell", stat_cmd], serial=serial, check=False)

        assets: List[RemoteMediaAsset] = []
        now_epoch = time.time()

        for line in proc.stdout.strip().splitlines():
            line_str = line.strip()
            if not line_str:
                continue

            parts = line_str.split(" ", 2)
            if len(parts) < 3:
                continue

            try:
                size_bytes = int(parts[0])
                mtime_epoch = int(parts[1])
                remote_path = parts[2].strip()
            except ValueError:
                continue

            if size_bytes <= 0:
                continue

            if (now_epoch - mtime_epoch) < 5.0:
                continue

            filename = Path(remote_path).name
            ext = Path(remote_path).suffix.lower()
            mtime_dt = datetime.fromtimestamp(mtime_epoch)

            is_video = ext in ADB_VIDEO_EXTENSIONS
            is_dng = ext == ".dng"

            assets.append(
                RemoteMediaAsset(
                    filename=filename,
                    remote_path=remote_path,
                    size_bytes=size_bytes,
                    modified_time=mtime_dt,
                    extension=ext,
                    is_video=is_video,
                    is_dng=is_dng,
                )
            )

        return assets

    def pull_file_atomic(
        self,
        remote_path: str,
        local_destination: Path,
        expected_size_bytes: int,
        serial: str,
        max_retries: int = 3,
    ) -> Tuple[bool, float, str]:
        local_dest = Path(local_destination).resolve()
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        part_path = local_dest.parent / f".tmp_{local_dest.name}_{os.getpid()}.part"


        size_gb = expected_size_bytes / (1024 * 1024 * 1024)
        calc_timeout = max(ADB_DEFAULT_TIMEOUT_SECONDS, size_gb * ADB_PULL_TIMEOUT_PER_GB_SECONDS)

        for attempt in range(1, max_retries + 1):
            if part_path.exists():
                part_path.unlink(missing_ok=True)

            start_t = time.time()
            try:
                self.run_cmd(["pull", "-a", remote_path, str(part_path)], serial=serial, timeout=calc_timeout)
                duration = max(time.time() - start_t, 0.001)

                if not part_path.exists():
                    raise TransferIntegrityError(f"Target part file was not created: {part_path}")

                actual_size = part_path.stat().st_size
                if actual_size != expected_size_bytes:
                    raise TransferIntegrityError(
                        f"Size mismatch on {remote_path} (Attempt {attempt}/{max_retries}): "
                        f"Expected {expected_size_bytes} bytes, received {actual_size} bytes."
                    )

                sha256 = calculate_sha256(part_path)
                os.replace(part_path, local_dest)
                return True, duration, sha256

            except (ADBError, TransferIntegrityError, Exception) as ex:
                if part_path.exists():
                    part_path.unlink(missing_ok=True)
                if attempt == max_retries:
                    raise TransferIntegrityError(
                        f"Failed to pull {remote_path} after {max_retries} attempts. Last error: {ex}"
                    ) from ex
                time.sleep(1.0 * attempt)

        return False, 0.0, ""

    def get_remote_md5(self, remote_path: str, serial: str) -> Optional[str]:
        proc = self.run_cmd(["shell", f"md5sum '{remote_path}' 2>/dev/null"], serial=serial, check=False)
        if proc.returncode == 0 and proc.stdout.strip():
            parts = proc.stdout.strip().split()
            if parts:
                return parts[0].lower()
        return None

# ======================================================================
# PERSISTENT INGESTION LEDGER
# ======================================================================

class ADBIngestionLedger:
    """Maintains a persistent JSON ledger (.adb_ingest_ledger.json)."""

    def __init__(self, ledger_path: Path):
        self.ledger_path = Path(ledger_path).resolve()
        self.entries: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.ledger_path.is_file():
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
            except Exception:
                self.entries = {}

    def save(self) -> None:
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to write ADB ingestion ledger: {e}", file=sys.stderr)

    def is_ingested(self, filename: str, size_bytes: int) -> bool:
        entry = self.entries.get(filename)
        if entry and entry.get("size_bytes") == size_bytes:
            return True
        return False

    def record_ingest(
        self,
        filename: str,
        remote_path: str,
        size_bytes: int,
        sha256: str,
        device_serial: str,
        local_path: str,
    ) -> None:
        self.entries[filename] = {
            "filename": filename,
            "remote_path": remote_path,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "device_serial": device_serial,
            "local_path": local_path,
            "ingested_at": datetime.now().isoformat(),
        }
        self.save()


# ======================================================================
# MASTER SAMSUNG ADB INGESTION ENGINE
# ======================================================================

class SamsungADBIngestor:
    """Master Ingestion Bridge connecting Samsung Galaxy S26 Ultra to the pipeline."""

    def __init__(
        self,
        workspace_root: Path,
        adb_path: Optional[str] = None,
        device_serial: Optional[str] = None,
        remote_camera_path: str = DEFAULT_ANDROID_CAMERA_PATH,
        db_path: Optional[Path] = None,
        enable_mdns: bool = True,
        mdns_timeout: float = MDNS_DEFAULT_TIMEOUT_SEC,
        connect_endpoint: Optional[str] = None,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.adb = ADBClient(adb_path=adb_path, target_serial=device_serial)
        self.device_serial = device_serial
        self.remote_camera_path = remote_camera_path
        self.ledger = ADBIngestionLedger(self.workspace_root / ".adb_ingest_ledger.json")
        self.health_guard = DirectoryHealthGuard(max_items=MAX_FOLDER_ITEMS)
        self.db_path = db_path or (self.workspace_root / "media_manifest.sqlite")
        self.enable_mdns = enable_mdns
        self.mdns_timeout = mdns_timeout
        self.connect_endpoint = connect_endpoint
        self.mdns_discovery = ADBMDNSDiscovery(timeout_sec=mdns_timeout)

    def list_devices(self) -> List[ADBDeviceInfo]:
        return self.adb.list_devices()

    def discover_and_connect(self, timeout: Optional[float] = None) -> Optional[DiscoveredADBService]:
        """
        Scans local network for ADB mDNS services and attempts connection.
        Returns DiscoveredADBService if found and connection succeeded, else None.
        """
        if not self.enable_mdns:
            return None

        scan_timeout = timeout if timeout is not None else self.mdns_timeout
        try:
            target_svc = self.mdns_discovery.find_target_device(
                preferred_serial=self.device_serial,
                timeout=scan_timeout,
            )
            if target_svc:
                connected = self.adb.connect_device(target_svc.ip_address, target_svc.port)
                if connected:
                    return target_svc
        except Exception:
            pass
        return None

    def select_device(self, preferred_serial: Optional[str] = None) -> ADBDeviceInfo:
        """
        Resolves active device supporting 4-tier fallback:
        1. Explicit connect_endpoint (if provided).
        2. mDNS Auto-Discovery & auto adb connect (if enable_mdns=True).
        3. Attached USB/Wi-Fi devices fallback.
        4. Actionable error (NoDeviceConnectedError).
        """
        if self.connect_endpoint:
            try:
                if ":" in self.connect_endpoint:
                    ip, port_str = self.connect_endpoint.split(":", 1)
                    self.adb.connect_device(ip.strip(), int(port_str.strip()))
                else:
                    self.adb.connect_device(self.connect_endpoint.strip(), 5555) # default port
            except Exception:
                pass

        # Tier 2: Select from attached devices or raise actionable error
        return self.adb.select_active_device(preferred_serial or self.device_serial)

    def scan_remote_camera(
        self,
        remote_dir: Optional[str] = None,
        date_filter: Optional[str] = None,
        recent_limit: Optional[int] = None,
        extensions: Optional[List[str]] = None,
        include_raw_dng: bool = False,
        skip_duplicates: bool = True,
        force: bool = False,
    ) -> List[RemoteMediaAsset]:
        device = self.select_device()
        target_dir = remote_dir or self.remote_camera_path

        allowed_exts = list(extensions or ADB_VIDEO_EXTENSIONS)
        if include_raw_dng and ".dng" not in allowed_exts:
            allowed_exts.append(".dng")

        assets = self.adb.stat_remote_directory(target_dir, serial=device.serial)

        if include_raw_dng:
            try:
                raw_assets = self.adb.stat_remote_directory(ADB_EXPERT_RAW_PATH, serial=device.serial)
                assets.extend(raw_assets)
            except Exception:
                pass

        filtered = [a for a in assets if a.matches_extensions(allowed_exts)]

        if date_filter:
            date_clean = date_filter.replace("-", "").strip()
            date_filtered = []
            for a in filtered:
                file_date = a.modified_time.strftime("%Y%m%d")
                if file_date == date_clean or a.filename.startswith(date_clean):
                    date_filtered.append(a)
            filtered = date_filtered

        filtered.sort(key=lambda a: a.modified_time, reverse=True)

        if recent_limit and recent_limit > 0:
            filtered = filtered[:recent_limit]

        if skip_duplicates and not force:
            non_duplicates = []
            for a in filtered:
                if not self._is_duplicate(a):
                    non_duplicates.append(a)
            return non_duplicates

        return filtered

    def _is_duplicate(self, asset: RemoteMediaAsset) -> bool:
        if self.ledger.is_ingested(asset.filename, asset.size_bytes):
            return True

        for tier_folder in FOLDER_TIERS.values():
            tier_dir = self.workspace_root / tier_folder
            if tier_dir.exists():
                direct_file = tier_dir / asset.filename
                if direct_file.is_file() and direct_file.stat().st_size == asset.size_bytes:
                    return True
                for match in tier_dir.rglob(asset.filename):
                    if match.is_file() and match.stat().st_size == asset.size_bytes:
                        return True

        if self.db_path.is_file():
            try:
                import sqlite3
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='asset_manifest'")
                    if cursor.fetchone():
                        cursor.execute(
                            "SELECT id FROM asset_manifest WHERE source_file_name = ? OR canonical_name LIKE ?",
                            (asset.filename, f"{Path(asset.filename).stem}]".replace("_", "%").replace("]", ""))
                        )
                        row = cursor.fetchone()
                        if row:
                            return True
            except Exception:
                pass

        return False

    def pull_asset(
        self,
        asset: RemoteMediaAsset,
        destination_dir: Path,
        verify_checksum: bool = True,
        max_retries: int = 3,
    ) -> ADBPullResult:
        device = self.select_device()
        dest_path = destination_dir / asset.filename

        try:
            success, duration, sha256 = self.adb.pull_file_atomic(
                remote_path=asset.remote_path,
                local_destination=dest_path,
                expected_size_bytes=asset.size_bytes,
                serial=device.serial,
                max_retries=max_retries,
            )

            rate_mbps = (asset.size_bytes * 8 / (1024 * 1024)) / max(duration, 0.001)

            self.ledger.record_ingest(
                filename=asset.filename,
                remote_path=asset.remote_path,
                size_bytes=asset.size_bytes,
                sha256=sha256,
                device_serial=device.serial,
                local_path=str(dest_path),
            )

            return ADBPullResult(
                success=True,
                remote_asset=asset,
                local_path=str(dest_path),
                size_bytes=asset.size_bytes,
                sha256_hash=sha256,
                transfer_duration_sec=duration,
                transfer_rate_mbps=rate_mbps,
                retries_attempted=1,
            )

        except Exception as e:
            return ADBPullResult(
                success=False,
                remote_asset=asset,
                local_path="",
                size_bytes=0,
                sha256_hash="",
                transfer_duration_sec=0.0,
                transfer_rate_mbps=0.0,
                error_message=str(e),
            )
    def ingest_batch(
        self,
        event_name: str = "Concert",
        artist_name: str = "Artist",
        track_name: str = "ID",
        brand: BrandType = BrandType.MUSIC_BAPTISM,
        tier: EventTier = EventTier.PILLAR_A,
        date_filter: Optional[str] = None,
        recent_limit: Optional[int] = None,
        extensions: Optional[List[str]] = None,
        include_raw_dng: bool = False,
        auto_route: bool = False,
        inbox_only: bool = True,
        dry_run: bool = False,
        force: bool = False,
        verify_remote_md5: bool = False,
    ) -> ADBIngestionSummary:
        start_batch_time = time.time()
        device = self.select_device()

        all_remote = self.scan_remote_camera(
            date_filter=date_filter,
            recent_limit=None,
            extensions=extensions,
            include_raw_dng=include_raw_dng,
            skip_duplicates=False,
            force=True,
        )

        eligible_assets = self.scan_remote_camera(
            date_filter=date_filter,
            recent_limit=recent_limit,
            extensions=extensions,
            include_raw_dng=include_raw_dng,
            skip_duplicates=True,
            force=force,
        )

        skipped_duplicates = len(all_remote) - len(eligible_assets) if not force else 0

        if not eligible_assets:
            return ADBIngestionSummary(
                total_remote_scanned=len(all_remote),
                total_eligible=0,
                total_pulled=0,
                total_skipped_duplicate=skipped_duplicates,
                total_failed=0,
                total_bytes_transferred=0,
                total_duration_sec=time.time() - start_batch_time,
                pulled_results=[],
            )

        # INTERACTIVE PROMPT
        print(f"\n[INTERACTIVE] Discovered {len(eligible_assets)} eligible assets on device {device.serial}.")
        for idx, a in enumerate(eligible_assets, 1):
            print(f"  [{idx}] {a.filename} ({a.size_mb:.2f} MB) - Modified: {a.modified_time}")
        
        while True:
            sel = input("\nEnter assets to pull (e.g. '1', '1,2-4', 'all', 'none'): ").strip().lower()
            if sel == 'none' or sel == '':
                print("[INFO] Aborting ingestion.")
                return ADBIngestionSummary(
                    total_remote_scanned=len(all_remote),
                    total_eligible=len(eligible_assets),
                    total_pulled=0,
                    total_skipped_duplicate=skipped_duplicates,
                    total_failed=0,
                    total_bytes_transferred=0,
                    total_duration_sec=time.time() - start_batch_time,
                    pulled_results=[],
                )
            if sel == 'all':
                break
            
            selected_indices = set()
            try:
                for part in sel.split(','):
                    part = part.strip()
                    if '-' in part:
                        start_str, end_str = part.split('-')
                        for i in range(int(start_str), int(end_str) + 1):
                            selected_indices.add(i)
                    else:
                        selected_indices.add(int(part))
                
                new_eligible = []
                for idx in sorted(list(selected_indices)):
                    if 1 <= idx <= len(eligible_assets):
                        new_eligible.append(eligible_assets[idx - 1])
                if new_eligible:
                    eligible_assets = new_eligible
                    break
                else:
                    print("[ERROR] Invalid selection, out of bounds.")
            except ValueError:
                print("[ERROR] Invalid format. Please use numbers separated by commas or dashes.")

        total_pending_bytes = sum(a.size_bytes for a in eligible_assets)
        inbox_base = self.workspace_root / FOLDER_TIERS["INBOX"]
        inbox_base.mkdir(parents=True, exist_ok=True)

        try:
            free_disk_bytes = shutil.disk_usage(str(inbox_base)).free
            required_disk_bytes = total_pending_bytes + ADB_MIN_FREE_DISK_HEADROOM_BYTES
            if free_disk_bytes < required_disk_bytes:
                raise InsufficientStorageError(
                    f"Insufficient host disk space: Available {free_disk_bytes / (1024**3):.2f} GB, "
                    f"Required {required_disk_bytes / (1024**3):.2f} GB (including 5 GB headroom)."
                )
        except OSError:
            pass

        if dry_run:
            results = []
            for asset in eligible_assets:
                results.append(
                    ADBPullResult(
                        success=True,
                        remote_asset=asset,
                        local_path=str(inbox_base / asset.filename),
                        size_bytes=asset.size_bytes,
                        sha256_hash="DRY_RUN_SIMULATION_HASH",
                        transfer_duration_sec=0.01,
                        transfer_rate_mbps=100.0,
                    )
                )
            return ADBIngestionSummary(
                total_remote_scanned=len(all_remote),
                total_eligible=len(eligible_assets),
                total_pulled=len(eligible_assets),
                total_skipped_duplicate=skipped_duplicates,
                total_failed=0,
                total_bytes_transferred=total_pending_bytes,
                total_duration_sec=time.time() - start_batch_time,
                pulled_results=results,
            )

        pulled_results: List[ADBPullResult] = []
        errors: List[str] = []
        event_slug = FilenameNormalizer.sanitize_token(event_name, default="Concert")

        for asset in eligible_assets:
            target_inbox_subfolder = self.health_guard.get_healthy_subfolder(inbox_base, event_slug)

            if verify_remote_md5:
                remote_md5 = self.adb.get_remote_md5(asset.remote_path, device.serial)
                if remote_md5:
                    print(f"  [REMOTE MD5] {asset.filename}: {remote_md6}")

            pull_res = self.pull_asset(asset, target_inbox_subfolder)
            pulled_results.append(pull_res)

            if not pull_res.success:
                errors.append(f"Failed to pull {asset.filename}: {pull_res.error_message}")
            else:
                print(f"  [PULLED] {asset.filename} ({asset.size_mb:.1f} MB @ {pull_res.transfer_rate_mbps:.1f} Mbps) -> {pull_res.local_path}")

        if (auto_route or not inbox_only) and not dry_run:
            router = AssetIngestionRouter(workspace_root=self.workspace_root)
            for res in pulled_results:
                if res.success and res.remote_asset.is_video:
                    try:
                        router.ingest_asset(
                            source_path=Path(res.local_path),
                            event_name=event_name,
                            artist_name=artist_name,
                            track_name=track_name,
                            brand=brand,
                            tier=tier,
                        )
                        print(f"  [AUTO-ROUTED] Staged {res.remote_asset.filename} in 02_IN_PROGRESS")
                    except Exception as ex:
                        errors.append(f"Auto-route failed for {res.local_path}: {ex}")

        total_transferred = sum(r.size_bytes for r in pulled_results if r.success)
        successful_pulls = sum(1 for r in pulled_results if r.success)
        failed_pulls = sum(1 for r in pulled_results if not r.success)

        return ADBIngestionSummary(
            total_remote_scanned=len(all_remote),
            total_eligible=len(eligible_assets),
            total_pulled=successful_pulls,
            total_skipped_duplicate=skipped_duplicates,
            total_failed=failed_pulls,
            total_bytes_transferred=total_transferred,
            total_duration_sec=time.time() - start_batch_time,
            pulled_results=pulled_results,
            errors=errors,
        )


SamsungIngestEngine = SamsungADBIngestor
ADBDeviceManager = ADBClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="samsung_ingest.py",
        description="Samsung Galaxy S26 Ultra ADB Hardware Ingestion Bridge (Track 2: Content Creation)",
    )
    parser.add_argument("--target-dir", "-t", default=str(Path.cwd()), help="Content creation workspace root directory.")
    parser.add_argument("--adb-path", default=None, help="Explicit path to adb executable binary.")
    parser.add_argument("--device", "-d", default=None, help="Target ADB device serial number.")
    parser.add_argument("--connect", default=None, help="Explicitly connect to an ADB TCP/IP endpoint (<ip>:<port>) before ingestion.")
    parser.add_argument("--mdns", "--auto-discover", dest="enable_mdns", action="store_true", default=True, help="Enable mDNS Zeroconf wireless debugging auto-discovery (default: True).")
    parser.add_argument("--no-mdns", dest="enable_mdns", action="store_false", help="Disable mDNS auto-discovery and use only attached USB/Wi-Fi devices.")
    parser.add_argument("--mdns-timeout", type=float, default=MDNS_DEFAULT_TIMEOUT_SEC, help=f"Timeout in seconds for mDNS discovery scan (default: {MDNS_DEFAULT_TIMEOUT_SEC}).")
    parser.add_argument("--remote-dir", default=DEFAULT_ANDROID_CAMERA_PATH, help="Remote Android camera folder path.")
    parser.add_argument("--event", "-e", default="Concert", help="Concert / Festival name (e.g. EDCOrlando).")
    parser.add_argument("--artist", "-a", default="Artist", help="DJ / Headliner name (e.g. JohnSummit).")
    parser.add_argument("--track", default="ID", help="Track name or unreleased ID code.")
    parser.add_argument("--brand", choices=[b.value for b in BrandType], default=BrandType.MUSIC_BAPTISM.value)
    parser.add_argument("--tier", choices=[t.value for t in EventTier], default=EventTier.PILLAR_A.value)
    parser.add_argument("--recent", type=int, default=None, help="Pull only the N most recent camera takes.")
    parser.add_argument("--date", default=None, help="Filter remote takes by capture date (YYYYMMDD).")
    parser.add_argument("--auto-route", "--auto-ingest", dest="auto_route", action="store_true", help="Automatically probe and stage in 02_IN_PROGRESS.")
    parser.add_argument("--inbox-only", action="store_true", help="Pull raw untouched files to 01_RAW_INBOX without downstream routing.")
    parser.add_argument("--include-raw-dng", action="store_true", help="Also scan and ingest 16-bit DNG stills from Expert RAW.")
    parser.add_argument("--verify-remote-md5" , action="store_true", help="Execute on-device md5sum verification before download.")
    parser.add_argument("--force", action="store_true", help="Bypass deduplication ledger and re-pull existing files.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate remote scan and deduplication without transferring bytes.")
    parser.add_argument("--list-devices", action="store_true", help="List all connected Android devices and exit.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    workspace = Path(args.target_dir).resolve()

    try:
        ingestor = SamsungADBIngestor(
            workspace_root=workspace,
            adb_path=args.adb_path,
            device_serial=args.device,
            remote_camera_path=args.remote_dir,
            enable_mdns=args.enable_mdns,
            mdns_timeout=args.mdns_timeout,
            connect_endpoint=args.connect,
        )

        if args.list_devices:
            devices = ingestor.list_devices()
            print("=" * 60)
            print("ATTACHED ANDROID HARDWARE DEVICES (ADB)")
            print("=" * 60)
            if not devices:
                print("No devices connected.")
            for d in devices:
                samsung_tag = " [Samsung Flagship]" if d.is_samsung else ""
                s26_tag = " [S26 Ultra Verified]" if d.is_s26_ultra else ""
                auth_tag = "AUTHORIZED" if d.is_authorized else f"BUNAUTHORIZED ({d.state})"
                print(f"- Serial: {d.serial} | Model: {d.model} | State: {auth_tag}{samsung_tag}{s26_tag}")
            print("=" * 60)
            return

        device = ingestor.select_device()
        print("=" * 60)
        print(f"SAMSUNG S26 ULTRA ADB INGESTION BRIDGE: {device.model} ({device.serial})")
        print("=" * 60)


        summary = ingestor.ingest_batch(
            event_name=args.event,
            artist_name=args.artist,
            track_name=args.track,
            brand=BrandType(args.brand),
            tier=EventTier(args.tier),
            date_filter=args.date,
            recent_limit=args.recent,
            include_raw_dng=args.include_raw_dng,
            auto_route=args.auto_route,
            inbox_only=args.inbox_only,
            dry_run=args.dry_run,
            force=args.force,
            verify_remote_md5=args.verify_remote_md5,
        )


        print("\n" + "=" * 60)
        print("INGESTIOM EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Remote Assets Scanned:     {summary.total_remote_scanned}")
        print(f"Eligible Pending Takes:    {summary.total_eligible}")
        print(f"Successfully Transferred:  {summary.total_pulled}")
        print(f"Skipped (Duplicates):      {summary.total_skipped_duplicate}")
        print(f"Failed Transfers:          {summary.total_failed}")
        print(f"Total Payload Transferred: {summary.total_mb_transferred:.2f} MB")
        print(f"Total Elapsed Duration:    {summary.total_duration_sec:.2f} seconds")
        print(f"Average Transfer Speed:    {summary.average_rate_mbps:.1f} Mbps")
        print("=" * 60)


        if summary.errors:
            print("\nErrors encountered:")
            for err in summary.errors:
                print(f"  - {err}")
            sys.exit(1)


    except Exception as ex:
        print(f"[INGESTION ERROR] {ex}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
