"""Port Manager & Dynamic Socket Collision Resolver.
Provides automatic port collision detection, lock-file cleanup, and sequential fallback allocation.
"""

import os
import sys
import time
import socket
import logging
import tempfile
import threading
from typing import Optional, List, Dict, Any

logger = logging.getLogger("unified_ops_hub.port_manager")


class PortManager:
    """Manages port allocation, collision detection, and lock files for resilient daemon startup."""

    def __init__(self, lock_dir: Optional[str] = None, host: str = "127.0.0.1") -> None:
        self.host = host
        if lock_dir:
            self.lock_dir = os.path.abspath(lock_dir)
        else:
            self.lock_dir = os.path.join(tempfile.gettempdir(), "unified_ops_hub_locks")
        os.makedirs(self.lock_dir, exist_ok=True)
        self._held_locks: Dict[int, str] = {}
        self._lock = threading.Lock()

    def is_port_in_use(self, port: int, host: Optional[str] = None) -> bool:
        """Determines if a TCP port is actively occupied or listening."""
        target_host = host or self.host
        
        # Test 1: Active connection check
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            result = s.connect_ex((target_host, port))
            if result == 0:
                return True

        # Test 2: Exclusive bind check
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Do not set SO_REUSEADDR on Windows to ensure strict exclusivity
                s.bind((target_host, port))
                return False
        except (OSError, socket.error):
            return True

    def find_available_port(
        self,
        preferred_port: int = 8000,
        max_attempts: int = 50,
        host: Optional[str] = None,
    ) -> int:
        """Finds the first available port starting at preferred_port and falling back sequentially."""
        target_host = host or self.host
        for offset in range(max_attempts):
            candidate = preferred_port + offset
            if not self.is_port_in_use(candidate, target_host) and not self.is_port_locked(candidate):
                logger.info("Allocated port %d (preferred %d, offset +%d)", candidate, preferred_port, offset)
                return candidate

        raise RuntimeError(
            f"Unable to find available port starting from {preferred_port} after {max_attempts} attempts."
        )

    def _lock_file_path(self, port: int) -> str:
        return os.path.join(self.lock_dir, f"port_{port}.lock")

    def is_port_locked(self, port: int) -> bool:
        """Checks if a lock file exists for the given port."""
        path = self._lock_file_path(port)
        if not os.path.exists(path):
            return False
        
        # Check if process holding lock is still alive
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content.isdigit():
                pid = int(content)
                if not self._is_pid_alive(pid):
                    # Stale lock from dead process
                    try:
                        os.remove(path)
                        return False
                    except OSError:
                        pass
        except Exception:
            pass
        return True

    def acquire_port_lock(self, port: int) -> Optional[str]:
        """Atomically acquires an OS-level lock file for the given port."""
        with self._lock:
            path = self._lock_file_path(port)
            pid = os.getpid()
            
            try:
                # Atomic file creation
                flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
                fd = os.open(path, flags)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(str(pid))
                self._held_locks[port] = path
                logger.debug("Acquired lock file for port %d: %s", port, path)
                return path
            except FileExistsError:
                # Lock file exists; verify if it's stale
                if not self.is_port_locked(port):
                    # Stale lock was removed in check, retry acquisition
                    try:
                        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        with os.fdopen(fd, "w", encoding="utf-8") as f:
                            f.write(str(pid))
                        self._held_locks[port] = path
                        return path
                    except OSError:
                        return None
                logger.warning("Port %d is already locked by another process.", port)
                return None
            except OSError as exc:
                logger.error("Failed to acquire lock for port %d: %s", port, exc)
                return None

    def release_port_lock(self, port: int) -> bool:
        """Releases the lock file held by this instance for the given port."""
        with self._lock:
            path = self._held_locks.pop(port, None) or self._lock_file_path(port)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.debug("Released lock file for port %d: %s", port, path)
                    return True
                except OSError as exc:
                    logger.warning("Could not remove lock file %s: %s", path, exc)
                    return False
            return True

    def cleanup_stale_locks(self, max_age_seconds: int = 60) -> List[str]:
        """Cleans up lock files older than max_age_seconds or belonging to dead PIDs."""
        cleaned = []
        now = time.time()
        
        if not os.path.exists(self.lock_dir):
            return cleaned

        for filename in os.listdir(self.lock_dir):
            if filename.startswith("port_") and filename.endswith(".lock"):
                full_path = os.path.join(self.lock_dir, filename)
                try:
                    stat = os.stat(full_path)
                    age = now - stat.st_mtime
                    is_stale = age > max_age_seconds

                    if not is_stale:
                        with open(full_path, "r", encoding="utf-8") as f:
                            content = f.read().strip()
                        if content.isdigit():
                            pid = int(content)
                            if not self._is_pid_alive(pid):
                                is_stale = True

                    if is_stale:
                        os.remove(full_path)
                        cleaned.append(full_path)
                        logger.info("Cleaned stale lock file: %s (age=%.1fs)", full_path, age)
                except OSError as exc:
                    logger.warning("Error inspecting/cleaning lock %s: %s", full_path, exc)

        return cleaned

    def get_port_status(self, ports: Optional[List[int]] = None) -> Dict[str, Any]:
        """Returns availability and lock status for standard or provided ports."""
        target_ports = ports or [8000, 8002, 8501, 8080, 3000, 5555]
        status_map = {}
        
        for port in target_ports:
            in_use = self.is_port_in_use(port)
            locked = self.is_port_locked(port)
            status_map[str(port)] = {
                "port": port,
                "in_use": in_use,
                "locked": locked,
                "available": not in_use and not locked,
            }
            
        return status_map

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """Cross-platform check to see if a process ID is still alive."""
        if pid <= 0:
            return False
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
            if not handle:
                return False
            kernel32.CloseHandle(handle)
            return True
        else:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False
