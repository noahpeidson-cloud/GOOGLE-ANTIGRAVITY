"""3-Tier Windows File Lock Detector.

Tier 1: Temporary & Hidden Extension / Suffix Filter.
Tier 2: Native Win32 Exclusive Handle Acquisition (dwShareMode=0) / Fallback.
Tier 3: File Size Stability Debounce (byte growth check).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import sys
import time
from typing import Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

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
    """Detailed result of a 3-tier file lock evaluation."""
    is_locked: bool
    tier_failed: Optional[int]  # 1, 2, 3, or None if unlocked
    reason: str
    file_size_bytes: int = 0
    checked_path: str = ""

    @property
    def is_ready(self) -> bool:
        """Convenience property indicating file is unlocked and stable."""
        return not self.is_locked


def is_temporary_file(
    path: Union[str, Path],
    temp_extensions: Optional[Set[str]] = None
) -> bool:
    """Tier 1: Checks if the path represents a temporary, downloading, or hidden file."""
    p = Path(path)
    filename = p.name.lower()
    suffix = p.suffix.lower()

    active_temp = temp_extensions or DEFAULT_TEMP_EXTENSIONS
    if suffix in active_temp:
        return True

    # Check compound suffixes (e.g. sample.mp4.tmp)
    for ext in active_temp:
        if filename.endswith(ext):
            return True

    # Check hidden or temporary prefix patterns
    if filename.startswith((".", "~$", "._")):
        return True

    return False


def is_supported_media(
    path: Union[str, Path],
    media_extensions: Optional[Set[str]] = None
) -> bool:
    """Tier 1: Validates if file extension is an allowed video media format."""
    p = Path(path)
    suffix = p.suffix.lower()
    active_media = media_extensions or DEFAULT_MEDIA_EXTENSIONS
    return suffix in active_media


def test_exclusive_handle(path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """
    Tier 2: Attempts to acquire an exclusive file handle to detect active writers.
    Uses native win32file.CreateFile on Windows with dwShareMode=0 (exclusive).
    Falls back to standard open/rename checks if pywin32 is unavailable.
    Handles read-only files by falling back to GENERIC_READ with dwShareMode=0.
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
            # Win32 Error Codes: 32 = ERROR_SHARING_VIOLATION, 33 = ERROR_LOCK_VIOLATION, 5 = ACCESS_DENIED
            error_code = err.args[0] if err.args else -1
            if error_code == 5:
                # Read-only files fail GENERIC_WRITE with ERROR_ACCESS_DENIED (code 5).
                # Retry with GENERIC_READ and dwShareMode=0 to verify exclusive handle on read-only media.
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
                os.rename(p, p)
            except PermissionError:
                # Read-only attribute on Windows can raise PermissionError on rename; open(rb) already succeeded
                pass
        return True, None
    except (PermissionError, OSError) as err:
        return False, f"Exclusive lock failed: {err}"


def test_size_stability(path: Union[str, Path], interval_sec: float = 1.0) -> Tuple[bool, int, Optional[str]]:
    """Tier 3 (Sync): Tests file size stability across an interval."""
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
        return False, size_1, f"File size changed from {size_0} to {size_1} bytes"

    return True, size_1, None


async def test_size_stability_async(path: Union[str, Path], interval_sec: float = 1.0) -> Tuple[bool, int, Optional[str]]:
    """Tier 3 (Async): Tests file size stability across an interval using asyncio.sleep."""
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
        return False, size_1, f"File size changed from {size_0} to {size_1} bytes"

    return True, size_1, None


def check_file_lock(
    path: Union[str, Path],
    debounce_interval_sec: float = 1.0,
    media_extensions: Optional[Set[str]] = None,
    temp_extensions: Optional[Set[str]] = None,
) -> LockCheckResult:
    """Synchronously executes the full 3-tier lock detection sequence."""
    p = Path(path).resolve()
    str_path = str(p)

    if not p.exists():
        return LockCheckResult(is_locked=True, tier_failed=1, reason="File does not exist", checked_path=str_path)

    # Tier 1: Temporary & Media Extension Filter
    if is_temporary_file(p, temp_extensions):
        return LockCheckResult(is_locked=True, tier_failed=1, reason="File has temporary or hidden extension", checked_path=str_path)
    if not is_supported_media(p, media_extensions):
        return LockCheckResult(is_locked=True, tier_failed=1, reason="File extension is not a supported media format", checked_path=str_path)

    # Tier 2: Exclusive Handle Test
    handle_ok, handle_err = test_exclusive_handle(p)
    if not handle_ok:
        return LockCheckResult(is_locked=True, tier_failed=2, reason=handle_err or "Exclusive handle failed", checked_path=str_path)

    # Tier 3: Size Stability Check
    size_ok, final_size, size_err = test_size_stability(p, interval_sec=debounce_interval_sec)
    if not size_ok:
        return LockCheckResult(is_locked=True, tier_failed=3, reason=size_err or "Size unstable", file_size_bytes=final_size, checked_path=str_path)

    return LockCheckResult(is_locked=False, tier_failed=None, reason="File is unlocked, stable, and ready", file_size_bytes=final_size, checked_path=str_path)


async def check_file_lock_async(
    path: Union[str, Path],
    debounce_interval_sec: float = 1.0,
    media_extensions: Optional[Set[str]] = None,
    temp_extensions: Optional[Set[str]] = None,
) -> LockCheckResult:
    """Asynchronously executes the full 3-tier lock detection sequence."""
    p = Path(path).resolve()
    str_path = str(p)

    if not p.exists():
        return LockCheckResult(is_locked=True, tier_failed=1, reason="File does not exist", checked_path=str_path)

    # Tier 1: Temporary & Media Extension Filter
    if is_temporary_file(p, temp_extensions):
        return LockCheckResult(is_locked=True, tier_failed=1, reason="File has temporary or hidden extension", checked_path=str_path)
    if not is_supported_media(p, media_extensions):
        return LockCheckResult(is_locked=True, tier_failed=1, reason="File extension is not a supported media format", checked_path=str_path)

    # Tier 2: Exclusive Handle Test
    handle_ok, handle_err = test_exclusive_handle(p)
    if not handle_ok:
        return LockCheckResult(is_locked=True, tier_failed=2, reason=handle_err or "Exclusive handle failed", checked_path=str_path)

    # Tier 3: Size Stability Check
    size_ok, final_size, size_err = await test_size_stability_async(p, interval_sec=debounce_interval_sec)
    if not size_ok:
        return LockCheckResult(is_locked=True, tier_failed=3, reason=size_err or "Size unstable", file_size_bytes=final_size, checked_path=str_path)

    return LockCheckResult(is_locked=False, tier_failed=None, reason="File is unlocked, stable, and ready", file_size_bytes=final_size, checked_path=str_path)


async def wait_until_file_unlocked(
    path: Union[str, Path],
    timeout_sec: float = 60.0,
    poll_interval_sec: float = 1.0,
    debounce_interval_sec: float = 1.0,
    media_extensions: Optional[Set[str]] = None,
    temp_extensions: Optional[Set[str]] = None,
) -> LockCheckResult:
    """Repeatedly evaluates lock status with async sleep backoff until unlocked or timeout."""
    p = Path(path).resolve()
    start_time = time.monotonic()

    last_result = LockCheckResult(is_locked=True, tier_failed=1, reason="Initialization", checked_path=str(p))

    while (time.monotonic() - start_time) < timeout_sec:
        last_result = await check_file_lock_async(
            p,
            debounce_interval_sec=debounce_interval_sec,
            media_extensions=media_extensions,
            temp_extensions=temp_extensions,
        )
        if last_result.is_ready:
            return last_result

        # Backoff before next check
        await asyncio.sleep(poll_interval_sec)

    return LockCheckResult(
        is_locked=True,
        tier_failed=last_result.tier_failed or 2,
        reason=f"Lock wait timed out after {timeout_sec:.1f}s. Last reason: {last_result.reason}",
        file_size_bytes=last_result.file_size_bytes,
        checked_path=str(p),
    )


def is_file_locked(
    path: Union[str, Path],
    debounce_interval_sec: float = 0.0,
    debounce_sec: Optional[float] = None,
) -> bool:
    """Convenience boolean helper checking if a file is locked or unready.

    Evaluates check_file_lock(path, debounce_interval_sec) and returns result.is_locked.
    """
    effective_debounce = debounce_sec if debounce_sec is not None else debounce_interval_sec
    p = Path(path).resolve()
    if not p.exists():
        return True
    res = check_file_lock(p, debounce_interval_sec=effective_debounce)
    return res.is_locked


def wait_until_unlocked(
    path: Union[str, Path],
    timeout_sec: float = 60.0,
    poll_interval_sec: float = 0.1,
    debounce_interval_sec: float = 1.0,
    debounce_sec: Optional[float] = None,
) -> bool:
    """Convenience synchronous helper waiting until a file is unlocked and stable.

    Returns True if file becomes ready within timeout_sec, False otherwise.
    """
    effective_debounce = debounce_sec if debounce_sec is not None else debounce_interval_sec
    p = Path(path).resolve()

    if timeout_sec <= 0.0:
        if not p.exists():
            return False
        res = check_file_lock(p, debounce_interval_sec=effective_debounce)
        return res.is_ready

    start_time = time.monotonic()
    # Fast initial check
    if p.exists():
        res = check_file_lock(p, debounce_interval_sec=effective_debounce)
        if res.is_ready:
            return True

    while (time.monotonic() - start_time) < timeout_sec:
        time.sleep(poll_interval_sec)
        if not p.exists():
            continue
        res = check_file_lock(p, debounce_interval_sec=effective_debounce)
        if res.is_ready:
            return True

    return False
