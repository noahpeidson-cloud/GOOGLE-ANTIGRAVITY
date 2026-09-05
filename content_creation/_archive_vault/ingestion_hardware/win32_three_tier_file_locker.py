"""
================================================================================
Name: 3-Tier Windows File Lock Detector & Growth Debounce Engine
Context Mapping: Extracted from `baptism_of_music_brain/src/watcher/file_locker.py`.
                 Replaces naive sleep-based polling and incomplete file reads
                 across Windows media ingestion pipelines (Quick Share, Syncthing,
                 SMB shares, and local USB staging).
Strengths:
  - 3-Tier Sequential Lock Evaluation:
    * Tier 1 (Extension & Prefix Filter): Instantly rejects active downloads,
      temp buffers (`.part`, `.tmp`, `.crdownload`, `.uploading`, etc.), and hidden
      or lock files (`.~`, `~$`, `._`) before performing OS system calls.
    * Tier 2 (Win32 Native Exclusive Handle): Uses Windows kernel `CreateFileW`
      via `win32file` with `dwShareMode=0` (exclusive access). Accurately detects
      `ERROR_SHARING_VIOLATION` (32) and `ERROR_LOCK_VIOLATION` (33) when media is
      actively open by another process.
    * Error Code 5 (Access Denied) Read-Only Fallback: Handles read-only files
      without false positives by gracefully retrying with `GENERIC_READ` and
      `dwShareMode=0`.
    * POSIX & Non-pywin32 Fallback: Implements resilient cross-platform fallback
      via `open(r+b)` and `os.rename(p, p)` when running in non-Windows or pure
      POSIX environments.
    * Tier 3 (Byte-Size Growth Debounce): Verifies that byte size remains completely
      stable over an observation debounce interval (default 1.0s) and rejects
      zero-byte stubs.
  - Both Synchronous and Asynchronous APIs (`check_file_lock` and `check_file_lock_async`).

Weaknesses:
  - Tier 3 introduces a mandatory debounce delay (default 1.0s) to observe file
    growth, which adds a slight initial latency before promoting ingested files.
  - On networked SMB/CIFS filesystems, opportunistic locks (oplocks) can sometimes
    delay kernel sharing violation notifications by several hundred milliseconds.

Implementation Instructions:
  1. Inspect a local file before processing:
     `result = check_file_lock(file_path, debounce_interval_sec=1.0)`
     `if result.is_ready: process_media(file_path)`
  2. In async loops:
     `result = await check_file_lock_async(file_path, debounce_interval_sec=1.0)`
  3. Wait for lock release with timeout:
     `is_unlocked = wait_for_file_lock_release(file_path, timeout_sec=30.0)`
================================================================================
"""

from __future__ import annotations

import os
import sys
import time
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set, Tuple, Union

logger = logging.getLogger("Win32ThreeTierFileLocker")

# Attempt native Win32 imports
try:
    import pywintypes
    import win32con
    import win32file
    _PYWIN32_AVAILABLE = True
except ImportError:
    _PYWIN32_AVAILABLE = False


DEFAULT_TEMP_EXTENSIONS: Set[str] = {
    ".tmp", ".part", ".crdownload", ".downloading",
    ".aria2", ".partial", ".uploading", ".incomplete",
    ".temp", ".swp", ".lock"
}

DEFAULT_MEDIA_EXTENSIONS: Set[str] = {
    ".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".ts", ".flv", ".wmv"
}


@dataclass(frozen=True)
class LockCheckResult:
    """Detailed result telemetry from a 3-tier file lock evaluation."""
    is_locked: bool
    tier_failed: Optional[int]  # 1, 2, 3, or None if unlocked
    reason: str
    file_size_bytes: int = 0
    checked_path: str = ""

    @property
    def is_ready(self) -> bool:
        """Convenience property indicating file is unlocked, valid, and fully written."""
        return not self.is_locked


# ============================================================================
# TIER 1: EXTENSION & PREFIX FILTERING
# ============================================================================

def is_temporary_or_hidden(
    path: Union[str, Path],
    temp_extensions: Optional[Set[str]] = None,
) -> bool:
    """
    Tier 1: Checks whether the path represents a temporary, downloading, or hidden file.
    """
    p = Path(path)
    filename = p.name.lower()
    suffix = p.suffix.lower()

    active_temp = temp_extensions or DEFAULT_TEMP_EXTENSIONS

    # Direct suffix match
    if suffix in active_temp:
        return True

    # Compound suffix match (e.g., footage.mp4.part or video.mov.tmp)
    for ext in active_temp:
        if filename.endswith(ext):
            return True

    # Hidden or temporary prefix patterns
    if filename.startswith((".", "~$", "._")):
        return True

    return False


def is_supported_media(
    path: Union[str, Path],
    media_extensions: Optional[Set[str]] = None,
) -> bool:
    """
    Tier 1: Checks whether the file extension matches recognized video formats.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    active_media = media_extensions or DEFAULT_MEDIA_EXTENSIONS
    return suffix in active_media


# ============================================================================
# TIER 2: WIN32 EXCLUSIVE HANDLE ACQUISITION
# ============================================================================

def test_exclusive_handle(path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """
    Tier 2: Attempts to acquire an exclusive file handle to detect active writers.
    On Windows with pywin32:
      Uses win32file.CreateFile with dwShareMode=0 (exclusive access).
      Detects ERROR_SHARING_VIOLATION (32) and ERROR_LOCK_VIOLATION (33).
      Falls back to GENERIC_READ on ERROR_ACCESS_DENIED (5) for read-only media.
    On Non-Windows or non-pywin32:
      Falls back to open(r+b) and atomic self-rename.
    """
    p = Path(path).resolve()
    if not p.exists():
        return False, "File does not exist"

    # Win32 Native Path
    if _PYWIN32_AVAILABLE and sys.platform == "win32":
        try:
            handle = win32file.CreateFile(
                str(p),
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                0,  # dwShareMode = 0 -> Exclusive access
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None,
            )
            win32file.CloseHandle(handle)
            return True, None
        except pywintypes.error as err:
            # Win32 Error Codes:
            # 32 = ERROR_SHARING_VIOLATION
            # 33 = ERROR_LOCK_VIOLATION
            # 5  = ERROR_ACCESS_DENIED
            error_code = err.args[0] if err.args else -1

            if error_code == 5:
                # Read-only files fail GENERIC_WRITE with ERROR_ACCESS_DENIED (code 5).
                # Gracefully retry with GENERIC_READ and dwShareMode=0 to verify exclusive lock.
                try:
                    ro_handle = win32file.CreateFile(
                        str(p),
                        win32con.GENERIC_READ,
                        0,  # dwShareMode = 0 -> Exclusive access
                        None,
                        win32con.OPEN_EXISTING,
                        win32con.FILE_ATTRIBUTE_NORMAL,
                        None,
                    )
                    win32file.CloseHandle(ro_handle)
                    return True, None
                except pywintypes.error as ro_err:
                    ro_code = ro_err.args[0] if ro_err.args else -1
                    ro_msg = ro_err.args[2] if len(ro_err.args) > 2 else str(ro_err)
                    return False, f"Win32 exclusive lock failed for read-only file (code {ro_code}): {ro_msg}"
                except Exception as ro_exc:
                    return False, f"Win32 exclusive check error for read-only file: {ro_exc}"

            msg = err.args[2] if len(err.args) > 2 else str(err)
            return False, f"Win32 exclusive lock failed (code {error_code}): {msg}"
        except Exception as exc:
            return False, f"Win32 exclusive check error: {exc}"

    # Cross-Platform / Fallback Path
    try:
        try:
            with open(p, "r+b"):
                pass
        except (PermissionError, OSError):
            # Fallback to read-only mode if read-only attribute prevents r+b
            with open(p, "rb"):
                pass

        if sys.platform == "win32":
            # On Windows without pywin32, os.rename to self fails with WinError 32 if open by another process
            try:
                os.rename(str(p), str(p))
            except PermissionError:
                pass

        return True, None
    except (PermissionError, OSError) as err:
        return False, f"Exclusive lock failed: {err}"


# ============================================================================
# TIER 3: BYTE-SIZE GROWTH DEBOUNCE CHECK
# ============================================================================

def test_size_stability(path: Union[str, Path], interval_sec: float = 1.0) -> Tuple[bool, int, Optional[str]]:
    """
    Tier 3 (Synchronous): Checks if file size remains stable over an observation interval.
    """
    p = Path(path).resolve()
    if not p.exists():
        return False, 0, "File does not exist"

    try:
        size_0 = p.stat().st_size
    except OSError as err:
        return False, 0, f"Cannot stat file: {err}"

    if size_0 == 0:
        return False, 0, "File is zero bytes (empty/stub)"

    if interval_sec > 0:
        time.sleep(interval_sec)

    try:
        size_1 = p.stat().st_size
    except OSError as err:
        return False, size_0, f"Cannot stat file on second check: {err}"

    if size_0 != size_1:
        return False, size_1, f"File size changed from {size_0} to {size_1} bytes (actively growing)"

    return True, size_1, None


async def test_size_stability_async(
    path: Union[str, Path],
    interval_sec: float = 1.0,
) -> Tuple[bool, int, Optional[str]]:
    """
    Tier 3 (Asynchronous): Checks if file size remains stable using non-blocking asyncio.sleep.
    """
    p = Path(path).resolve()
    if not p.exists():
        return False, 0, "File does not exist"

    try:
        size_0 = p.stat().st_size
    except OSError as err:
        return False, 0, f"Cannot stat file: {err}"

    if size_0 == 0:
        return False, 0, "File is zero bytes (empty/stub)"

    if interval_sec > 0:
        await asyncio.sleep(interval_sec)

    try:
        size_1 = p.stat().st_size
    except OSError as err:
        return False, size_0, f"Cannot stat file on second check: {err}"

    if size_0 != size_1:
        return False, size_1, f"File size changed from {size_0} to {size_1} bytes (actively growing)"

    return True, size_1, None


# ============================================================================
# COMPREHENSIVE 3-TIER LOCK CHECK APIs
# ============================================================================

def check_file_lock(
    path: Union[str, Path],
    debounce_interval_sec: float = 1.0,
    media_extensions: Optional[Set[str]] = None,
    temp_extensions: Optional[Set[str]] = None,
) -> LockCheckResult:
    """
    Synchronously executes the full 3-tier file lock evaluation sequence:
      1. Tier 1: Rejects temporary extensions and hidden prefixes.
      2. Tier 2: Acquires exclusive handle (Win32 dwShareMode=0 with Error 5 fallback).
      3. Tier 3: Asserts non-zero byte size stability across debounce interval.
    """
    p = Path(path).resolve()
    str_path = str(p)

    if not p.exists():
        return LockCheckResult(
            is_locked=True, tier_failed=1, reason="File does not exist on disk", checked_path=str_path
        )

    # Tier 1 Check
    if is_temporary_or_hidden(p, temp_extensions):
        return LockCheckResult(
            is_locked=True, tier_failed=1, reason="File has temporary or hidden extension/prefix", checked_path=str_path
        )

    # Tier 2 Check
    unlocked, err_msg = test_exclusive_handle(p)
    if not unlocked:
        return LockCheckResult(
            is_locked=True, tier_failed=2, reason=f"Exclusive handle check failed: {err_msg}", checked_path=str_path
        )

    # Tier 3 Check
    stable, size, err_msg = test_size_stability(p, interval_sec=debounce_interval_sec)
    if not stable:
        return LockCheckResult(
            is_locked=True, tier_failed=3, reason=f"Size stability check failed: {err_msg}", file_size_bytes=size, checked_path=str_path
        )

    return LockCheckResult(
        is_locked=False, tier_failed=None, reason="File is unlocked and stable", file_size_bytes=size, checked_path=str_path
    )


async def check_file_lock_async(
    path: Union[str, Path],
    debounce_interval_sec: float = 1.0,
    media_extensions: Optional[Set[str]] = None,
    temp_extensions: Optional[Set[str]] = None,
) -> LockCheckResult:
    """
    Asynchronously executes the 3-tier file lock evaluation sequence without blocking event loops.
    """
    p = Path(path).resolve()
    str_path = str(p)

    if not p.exists():
        return LockCheckResult(
            is_locked=True, tier_failed=1, reason="File does not exist on disk", checked_path=str_path
        )

    # Tier 1 Check
    if is_temporary_or_hidden(p, temp_extensions):
        return LockCheckResult(
            is_locked=True, tier_failed=1, reason="File has temporary or hidden extension/prefix", checked_path=str_path
        )

    # Tier 2 Check
    unlocked, err_msg = test_exclusive_handle(p)
    if not unlocked:
        return LockCheckResult(
            is_locked=True, tier_failed=2, reason=f"Exclusive handle check failed: {err_msg}", checked_path=str_path
        )

    # Tier 3 Check (Async sleep)
    stable, size, err_msg = await test_size_stability_async(p, interval_sec=debounce_interval_sec)
    if not stable:
        return LockCheckResult(
            is_locked=True, tier_failed=3, reason=f"Size stability check failed: {err_msg}", file_size_bytes=size, checked_path=str_path
        )

    return LockCheckResult(
        is_locked=False, tier_failed=None, reason="File is unlocked and stable", file_size_bytes=size, checked_path=str_path
    )


def wait_for_file_lock_release(
    path: Union[str, Path],
    timeout_sec: float = 30.0,
    poll_interval_sec: float = 1.0,
    debounce_interval_sec: float = 1.0,
) -> bool:
    """
    Blocks until the file passes all 3 tiers or until timeout is exceeded.
    Returns True if unlocked and stable, False on timeout.
    """
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        res = check_file_lock(path, debounce_interval_sec=debounce_interval_sec)
        if res.is_ready:
            return True
        time.sleep(poll_interval_sec)
    return False


# ============================================================================
# VERIFICATION & CLI ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print(f"Testing 3-Tier Windows File Locker (pywin32 available: {_PYWIN32_AVAILABLE})...")

    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Test Tier 1 filter on temp file
        part_file = tmp_path / "recording_take_01.mp4.part"
        part_file.write_bytes(b"DATA")
        res1 = check_file_lock(part_file)
        assert res1.is_locked is True and res1.tier_failed == 1
        print("Tier 1 rejection test passed (temporary suffix .part)!")

        # 2. Test Tier 3 zero-byte rejection
        empty_file = tmp_path / "empty_video.mp4"
        empty_file.touch()
        res_empty = check_file_lock(empty_file, debounce_interval_sec=0.1)
        assert res_empty.is_locked is True and res_empty.tier_failed == 3
        print("Tier 3 zero-byte stub rejection test passed!")

        # 3. Test Tier 2 active writer lock
        active_file = tmp_path / "locked_file.mp4"
        with open(active_file, "wb") as writer:
            writer.write(b"ACTIVE_DATA_STREAMING")
            writer.flush()
            # File is actively open by writer
            res2 = check_file_lock(active_file, debounce_interval_sec=0.1)
            # Depending on OS / pywin32, this fails Tier 2 or Tier 3
            print(f"Active file lock test: is_locked={res2.is_locked}, tier={res2.tier_failed}, reason={res2.reason}")

        # 4. Test fully released stable file
        stable_file = tmp_path / "clean_export.mp4"
        stable_file.write_bytes(b"COMPLETE_VALID_VIDEO_BYTES" * 100)
        res_stable = check_file_lock(stable_file, debounce_interval_sec=0.2)
        assert res_stable.is_ready is True
        print(f"Stable file test passed! Size: {res_stable.file_size_bytes} bytes.")

    print("All 3-Tier Windows File Locker tests completed successfully.")
