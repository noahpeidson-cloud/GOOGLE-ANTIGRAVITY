"""
adb_connection_manager.py - Wireless ADB Device Lifecycle & Discovery Manager.
Handles mDNS service discovery, connection handshakes, Samsung Auto Blocker bypass
(rampart_auto_enabled_switch_enabled 0), health heartbeats, and exponential backoff reconnection.
"""

import os
import re
import time
import random
import logging
import subprocess
from typing import Optional, List, Dict, Tuple, Callable

logger = logging.getLogger("AdbConnectionManager")


class AdbConnectionManager:
    """
    Manages wireless Android Debug Bridge (ADB) lifecycle over Wi-Fi.
    Enforces Rule R10.2 zero-touch compliance and hardware lockout mitigation.
    """

    def __init__(
        self,
        device_ip: str = "192.168.1.150",
        device_port: int = 5555,
        adb_binary: str = "adb",
        command_executor: Optional[Callable[..., subprocess.CompletedProcess]] = None,
    ):
        self.device_ip = device_ip
        self.device_port = device_port
        self.adb_binary = adb_binary
        self.target = f"{device_ip}:{device_port}"
        self.executor = command_executor or self._default_executor
        self._connected = False

    def _default_executor(self, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("text", True)
        return subprocess.run(cmd, **kwargs)

    def discover_mdns_services(self) -> List[Dict[str, str]]:
        """
        Scans local subnet for ADB wireless pairing and connection services via mDNS.
        """
        cmd = [self.adb_binary, "mdns", "services"]
        try:
            res = self.executor(cmd, timeout=10)
            services = []
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line or "List of discoverable" in line:
                    continue
                parts = re.split(r"\s+", line)
                if len(parts) >= 3:
                    services.append({
                        "service_name": parts[0],
                        "service_type": parts[1],
                        "address": parts[2],
                    })
            return services
        except Exception as e:
            logger.warning(f"mDNS discovery query failed: {e}")
            return []

    def connect(self, timeout_seconds: int = 15) -> bool:
        """
        Establishes wireless ADB TCP connection and applies Samsung Auto Blocker bypass.
        """
        logger.info(f"Connecting to wireless ADB device at {self.target}...")
        cmd = [self.adb_binary, "connect", self.target]
        try:
            res = self.executor(cmd, timeout=timeout_seconds)
            stdout_lower = res.stdout.lower()
            if "connected" in stdout_lower or "already connected" in stdout_lower:
                self._connected = True
                self._apply_samsung_auto_blocker_bypass()
                logger.info(f"Successfully connected to {self.target}")
                return True
            else:
                self._connected = False
                logger.warning(f"ADB Connect failed output: {res.stdout.strip()} {res.stderr.strip()}")
                return False
        except Exception as e:
            self._connected = False
            logger.error(f"Exception during ADB connect: {e}")
            return False

    def _apply_samsung_auto_blocker_bypass(self) -> bool:
        """
        Mitigates Samsung One UI 6+ Auto Blocker lockout timer (Rule R10.2).
        Sets rampart_auto_enabled_switch_enabled to 0.
        """
        cmd = [
            self.adb_binary,
            "-s",
            self.target,
            "shell",
            "settings",
            "put",
            "global",
            "rampart_auto_enabled_switch_enabled",
            "0",
        ]
        try:
            res = self.executor(cmd, timeout=10)
            if res.returncode == 0:
                logger.info("Samsung Auto Blocker bypass successfully applied.")
                return True
            else:
                logger.warning(f"Auto Blocker bypass returned code {res.returncode}: {res.stderr.strip()}")
                return False
        except Exception as e:
            logger.warning(f"Could not apply Auto Blocker bypass: {e}")
            return False

    def is_connected(self) -> bool:
        """
        Queries target device state via ADB heartbeat.
        """
        cmd = [self.adb_binary, "-s", self.target, "get-state"]
        try:
            res = self.executor(cmd, timeout=10)
            is_device = res.returncode == 0 and res.stdout.strip() == "device"
            self._connected = is_device
            return is_device
        except Exception:
            self._connected = False
            return False

    def ensure_connected(self) -> bool:
        """
        Ensures device is connected and Samsung Auto Blocker bypass is applied.
        """
        if not self._connected or not self.is_connected():
            return self.connect()
        # Ensure bypass is maintained
        self._apply_samsung_auto_blocker_bypass()
        return True

    def disconnect(self) -> bool:
        """
        Disconnects the wireless ADB session.
        """
        cmd = [self.adb_binary, "disconnect", self.target]
        try:
            res = self.executor(cmd, timeout=10)
            self._connected = False
            return res.returncode == 0
        except Exception as e:
            logger.warning(f"Error disconnecting ADB: {e}")
            self._connected = False
            return False

    def reconnect_with_backoff(
        self,
        max_attempts: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ) -> bool:
        """
        Attempts reconnection with exponential backoff and jitter upon network drops.
        """
        logger.info(f"Initiating backoff reconnection for {self.target} (max {max_attempts} attempts)...")
        for attempt in range(1, max_attempts + 1):
            if self.connect():
                logger.info(f"Reconnected successfully on attempt {attempt}.")
                return True

            if attempt < max_attempts:
                backoff_time = min(max_delay, base_delay * (2 ** (attempt - 1)))
                jitter = random.uniform(0.0, 0.5)
                total_wait = backoff_time + jitter
                logger.warning(f"Connection attempt {attempt} failed. Retrying in {total_wait:.2f}s...")
                time.sleep(total_wait)

        logger.error(f"Failed to reconnect to {self.target} after {max_attempts} attempts.")
        return False

    def execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Executes a shell command on the connected Android device.
        """
        cmd = [self.adb_binary, "-s", self.target, "shell", command]
        res = self.executor(cmd, timeout=timeout)
        return res.returncode, res.stdout, res.stderr

    def pull_file(self, remote_path: str, local_path: str, timeout: int = 300) -> Tuple[int, str, str]:
        """
        Pulls a remote file from the Android filesystem to local storage.
        """
        cmd = [self.adb_binary, "-s", self.target, "pull", remote_path, local_path]
        res = self.executor(cmd, timeout=timeout)
        return res.returncode, res.stdout, res.stderr

    def get_remote_file_sha256(self, remote_path: str, timeout: int = 60) -> str:
        """
        Computes SHA-256 hash on-device using Android native sha256sum binary.
        """
        ret, stdout, stderr = self.execute_shell(f"sha256sum '{remote_path}'", timeout=timeout)
        if ret != 0 or not stdout.strip():
            raise RuntimeError(f"Failed to calculate remote SHA-256 on {remote_path}: {stderr.strip()}")
        parts = stdout.strip().split()
        if not parts:
            raise RuntimeError(f"Empty sha256sum response from device: {stdout}")
        remote_hash = parts[0].strip()
        if len(remote_hash) != 64:
            raise RuntimeError(f"Invalid SHA-256 hash length ({len(remote_hash)}): {remote_hash}")
        return remote_hash
