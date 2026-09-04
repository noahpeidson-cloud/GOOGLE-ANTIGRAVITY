# Implementation Plan: Ingest Watcher & 3-Tier Windows File Lock Detector

**Milestone:** Milestone 1 — Core Ingest & Locking  
**Agent:** `m1_explorer_2`  
**Date:** 2026-08-27  
**Status:** READY FOR IMPLEMENTATION  

---

## 1. Executive Summary & Problem Scope

In a high-throughput desktop video post-production brain, raw multi-gigabyte 4K/8K video media arrives in the `ingest/` folder via varied ingestion channels:
1. ADB Wi-Fi / USB file sync from mobile devices (e.g. Samsung S26 Ultra).
2. Network share (SMB / NFS) drops.
3. Web/Browser downloads or local background copy utilities.

### The "Half-Baked / In-Flight Copy" Hazard
When multi-gigabyte files are copied into `ingest/`:
- Windows filesystem events (`on_created`, `on_modified`) fire immediately when the file entry is created on disk, long before the payload transfer completes.
- If downstream consumers (FFprobe, OpenCV, Gemini ML grading, FFmpeg) attempt to read an in-flight file:
  - Windows raises `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`.
  - Incomplete MP4 container headers (e.g., missing or trailing `moov` atom) cause FFprobe/FFmpeg decoding failures.
  - Zero-byte file handles cause pipeline crashes.

### The Solution: 2-Part Ingest Subsystem
1. **`src/watcher/file_locker.py`**: A hardened 3-tier file lock detector:
   - **Tier 1**: Temporary extension and hidden file filter (`.tmp`, `.part`, `.crdownload`, `~$*`, etc.).
   - **Tier 2**: Native Win32 exclusive file handle test via `win32file.CreateFile(..., dwShareMode=0)` with graceful POSIX/mock fallback.
   - **Tier 3**: Configurable size stability debounce (default 1.0s) ensuring byte growth has fully ceased.
2. **`src/watcher/ingest_watcher.py`**: An asynchronous directory watcher leveraging `watchfiles` / `watchdog` with:
   - Background polling fallback (scanning for files dropped before start or bypassing OS notify).
   - Multi-event debouncing (coalescing burst OS notifications).
   - In-flight task tracking (preventing duplicate workers per file).
   - Seamless handoff to the pipeline orchestrator upon confirmed lock release.

---

## 2. Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INGEST DIRECTORY WATCHER                              │
│                                                                                 │
│  ┌───────────────────────────────┐     ┌─────────────────────────────────────┐  │
│  │   OS Event Engine             │     │   Background Polling Fallback       │  │
│  │  - watchfiles (Async Rust)    │     │  - Periodic scandir (every 5-10s)   │  │
│  │  - watchdog (Win32 Directory) │     │  - Recovers missed / pre-existing   │  │
│  └───────────────┬───────────────┘     └──────────────────┬──────────────────┘  │
│                  │                                        │                     │
│                  └───────────────────┬────────────────────┘                     │
│                                      ▼                                          │
│                    ┌───────────────────────────────────┐                        │
│                    │   Event Debounce & Deduplication  │                        │
│                    │   - Coalesces rapid burst events  │                        │
│                    │   - 1 in-flight worker per path   │                        │
│                    └─────────────────┬─────────────────┘                        │
└──────────────────────────────────────┼──────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    3-TIER FILE LOCK DETECTOR (file_locker.py)                   │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ Tier 1: Temporary Extension Filter                                        │  │
│  │ - Reject .tmp, .part, .crdownload, .downloading, hidden .*, ~$*           │  │
│  │ - Validate media extension against whitelist (.mp4, .mov, .mkv, etc.)     │  │
│  └─────────────────────────────────────┬─────────────────────────────────────┘  │
│                                        │ PASS                                   │
│                                        ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ Tier 2: Native Win32 Exclusive Handle Acquisition                         │  │
│  │ - Win32: win32file.CreateFile(dwShareMode=0, OPEN_EXISTING)               │  │
│  │ - Catch ERROR_SHARING_VIOLATION (32) / ERROR_LOCK_VIOLATION (33)          │  │
│  │ - Fallback: open(..., 'r+b') + os.rename self-lock check                  │  │
│  └─────────────────────────────────────┬─────────────────────────────────────┘  │
│                                        │ PASS                                   │
│                                        ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ Tier 3: Size Stability Debounce (1.0s interval)                           │  │
│  │ - Verify size(t0) > 0 (reject zero-byte stubs)                            │  │
│  │ - Verify size(t0) == size(t1) after debounce interval                     │  │
│  └─────────────────────────────────────┬─────────────────────────────────────┘  │
│                                        │ PASS                                   │
└────────────────────────────────────────┼────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       PIPELINE COORDINATOR HANDOFF                              │
│                                                                                 │
│  - Compute File Stats & Metadata (Size, SHA-256)                                │
│  - Transition Job State -> INGESTED                                             │
│  - Dispatch to Probe Engine (probe.py) & ML Grading Brain                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Specification: `src/watcher/file_locker.py`

### 3.1 Design Details

#### Tier 1: Temporary Extension & Whitelist Filter
- **Temporary Suffixes**:
  `{".tmp", ".part", ".crdownload", ".downloading", ".aria2", ".partial", ".uploading", ".incomplete", ".temp", ".swp", ".lock"}`
- **Temporary / Hidden Prefixes**:
  Files starting with `.` (e.g. `.DS_Store`), `~$` (Office/Windows temp), or `._` (AppleDouble).
- **Supported Video Formats**:
  `{".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".ts", ".flv", ".wmv"}` (case-insensitive).
- **Behavior**: If file has a temporary suffix/prefix or is not a supported media type, Tier 1 immediately rejects the check without attempting OS handle allocation.

#### Tier 2: Win32 Exclusive File Handle Acquisition
- **Native Implementation (`pywin32`)**:
  ```python
  handle = win32file.CreateFile(
      str(filepath),
      win32con.GENERIC_READ | win32con.GENERIC_WRITE,
      0,  # dwShareMode = 0 -> EXCLUSIVE access (prevents any other process from sharing read/write)
      None,
      win32con.OPEN_EXISTING,
      win32con.FILE_ATTRIBUTE_NORMAL,
      None
  )
  win32file.CloseHandle(handle)
  ```
- **Error Codes Handled**:
  - `32` (`ERROR_SHARING_VIOLATION`): File is open by writer/other process.
  - `33` (`ERROR_LOCK_VIOLATION`): Byte range lock collision.
  - `5` (`ERROR_ACCESS_DENIED`): File access denied (open in non-shareable mode).
- **Cross-Platform / Mock Fallback**:
  - If `pywin32` is not installed or on non-Windows/POSIX:
    1. Try `open(filepath, "r+b")`.
    2. On Windows: Try `os.rename(filepath, filepath)` which raises `WinError 32` if open by an external writer.
    3. On POSIX: Use `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` if available.

#### Tier 3: Size Stability Debounce
- **Behavior**:
  1. Record `size_0 = os.path.getsize(filepath)`.
  2. If `size_0 == 0`: Report locked (`tier_failed=3`, "Zero-byte file").
  3. Wait for `debounce_interval_sec` (default: 1.0s, configurable for fast unit tests to 0.05s).
  4. Record `size_1 = os.path.getsize(filepath)`.
  5. If `size_0 != size_1`: Report locked (`tier_failed=3`, f"Size unstable: {size_0} -> {size_1}").
  6. If `size_0 == size_1` and `size_0 > 0`: Pass Tier 3.

### 3.2 Data Models & Signatures for `file_locker.py`

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Set, Tuple, Union

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
        return not self.is_locked
```

### 3.3 Core Function Signatures in `file_locker.py`

```python
def is_temporary_file(path: Union[str, Path], temp_extensions: Optional[Set[str]] = None) -> bool:
    """Tier 1: Check if file has a temporary suffix or hidden prefix."""
    ...

def is_supported_media(path: Union[str, Path], media_extensions: Optional[Set[str]] = None) -> bool:
    """Check if file extension is an allowed video format."""
    ...

def test_exclusive_handle(path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """Tier 2: Acquire exclusive Win32 file handle (dwShareMode=0) or fallback."""
    ...

def test_size_stability(path: Union[str, Path], interval_sec: float = 1.0) -> Tuple[bool, int, Optional[str]]:
    """Tier 3 (Sync): Verify file size > 0 and unchanged across interval."""
    ...

async def test_size_stability_async(path: Union[str, Path], interval_sec: float = 1.0) -> Tuple[bool, int, Optional[str]]:
    """Tier 3 (Async): Verify file size > 0 and unchanged across interval using asyncio.sleep."""
    ...

def check_file_lock(
    path: Union[str, Path],
    debounce_interval_sec: float = 1.0,
    media_extensions: Optional[Set[str]] = None,
    temp_extensions: Optional[Set[str]] = None
) -> LockCheckResult:
    """Synchronously execute the full 3-tier lock detection sequence."""
    ...

async def check_file_lock_async(
    path: Union[str, Path],
    debounce_interval_sec: float = 1.0,
    media_extensions: Optional[Set[str]] = None,
    temp_extensions: Optional[Set[str]] = None
) -> LockCheckResult:
    """Asynchronously execute the full 3-tier lock detection sequence."""
    ...

async def wait_until_file_unlocked(
    path: Union[str, Path],
    timeout_sec: float = 60.0,
    poll_interval_sec: float = 1.0,
    debounce_interval_sec: float = 1.0,
    media_extensions: Optional[Set[str]] = None,
) -> LockCheckResult:
    """Repeatedly evaluate lock status with async sleep backoff until unlocked or timeout."""
    ...
```

---

## 4. Component Specification: `src/watcher/ingest_watcher.py`

### 4.1 Design Details

#### Dual Engine Architecture
1. **Primary Async Watcher (`watchfiles.awatch`)**:
   - High-performance, Rust-backed filesystem event monitor.
   - Non-blocking integration into FastAPI async event loop.
2. **Watchdog Fallback / Alternative (`watchdog.observers.Observer`)**:
   - Standard Win32 `ReadDirectoryChangesW` observer running in a dedicated OS thread.
   - Schedules async events onto the event loop via `loop.call_soon_threadsafe`.
3. **Background Polling Scanner (`PollingWatcherTask`)**:
   - Runs on a periodic timer (`polling_interval_sec`, default 5.0s).
   - Scans `ingest/` with `os.scandir` to detect files that were:
     - Dropped before the service started.
     - Written via network shares that do not reliably trigger OS notifications.
     - Renamed across directory boundaries.

#### Event Debounce & In-Flight Worker Management
- **Debounce Window (`debounce_delay_sec = 0.5`)**:
  - When an event (`Created`, `Modified`, `Renamed`) arrives for `path`, register it in `_pending_events[path] = timestamp`.
  - Sleep `debounce_delay_sec`. If newer events arrive for the same path, debounce window resets.
- **In-Flight Single Worker Guarantee**:
  - `_in_flight_evaluations: Dict[Path, asyncio.Task]` maps active evaluation tasks.
  - Ensures only **one** lock evaluation task runs per physical file at any given moment, preventing duplicate pipeline handoffs.
- **Processed Tracking & Deduplication**:
  - `_processed_files: Set[Path]` records files that have successfully been handed off to avoid re-triggering unless the file is replaced or modified with a new timestamp and hash.

#### Lock Evaluation Loop & Pipeline Handoff
1. Upon event trigger:
   - Check Tier 1 (ignore non-media and temp files).
   - Enter `wait_until_file_unlocked` loop.
2. On Success:
   - Compute basic file metrics: `file_size_bytes`, `mtime`.
   - Invoke registered callback: `await on_file_ready(filepath)`.
   - Mark file as processed.
3. On Timeout / Error:
   - Log error with failed tier and reason.
   - If DLQ / error callback provided, notify error handler.

### 4.2 Class Architecture for `ingest_watcher.py`

```python
import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Dict, Optional, Set, Union

class IngestWatcher:
    """
    Robust Ingestion Directory Watcher.
    Combines async filesystem event monitoring with 3-tier lock detection,
    event debouncing, background polling recovery, and pipeline handoff.
    """

    def __init__(
        self,
        watch_dir: Union[str, Path],
        on_file_ready: Callable[[Path], Awaitable[None]],
        on_error: Optional[Callable[[Path, str], Awaitable[None]]] = None,
        allowed_extensions: Optional[Set[str]] = None,
        temp_extensions: Optional[Set[str]] = None,
        debounce_delay_sec: float = 0.5,
        lock_timeout_sec: float = 120.0,
        lock_poll_interval_sec: float = 1.0,
        size_debounce_interval_sec: float = 1.0,
        enable_polling_fallback: bool = True,
        polling_fallback_interval_sec: float = 5.0,
        prefer_engine: str = "watchfiles",  # "watchfiles" or "watchdog"
    ): ...

    async def start(self) -> None:
        """Start the filesystem watcher and polling fallback tasks."""
        ...

    async def stop(self) -> None:
        """Gracefully stop watching, cancelling active evaluation tasks."""
        ...

    async def scan_once(self) -> int:
        """Manually trigger a scan of the ingest directory for new/unlocked files."""
        ...

    @property
    def is_running(self) -> bool:
        ...

    async def __aenter__(self) -> "IngestWatcher":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()
```

---

## 5. Implementation Blueprint

### 5.1 `src/watcher/file_locker.py`

```python
"""
3-Tier Windows File Lock Detector.
Module: src.watcher.file_locker
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import sys
import time
from typing import Optional, Set, Tuple, Union

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
    tier_failed: Optional[int]  # 1, 2, 3, or None
    reason: str
    file_size_bytes: int = 0
    checked_path: str = ""

    @property
    def is_ready(self) -> bool:
        return not self.is_locked


def is_temporary_file(
    path: Union[str, Path],
    temp_extensions: Optional[Set[str]] = None
) -> bool:
    """Tier 1: Checks if the path represents a temporary or partial file."""
    p = Path(path)
    filename = p.name.lower()
    suffix = p.suffix.lower()
    
    # Check temporary extensions
    active_temp = temp_extensions or DEFAULT_TEMP_EXTENSIONS
    if suffix in active_temp:
        return True
        
    # Check compound temporary suffixes (e.g. .mp4.tmp)
    for ext in active_temp:
        if filename.endswith(ext):
            return True
            
    # Check hidden and temporary prefix conventions
    if filename.startswith((".", "~$", "._")):
        return True
        
    return False


def is_supported_media(
    path: Union[str, Path],
    media_extensions: Optional[Set[str]] = None
) -> bool:
    """Validates if file extension is an allowed video media format."""
    p = Path(path)
    suffix = p.suffix.lower()
    active_media = media_extensions or DEFAULT_MEDIA_EXTENSIONS
    return suffix in active_media


def test_exclusive_handle(path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """
    Tier 2: Attempts to acquire an exclusive file handle to detect active writers.
    Uses native win32file.CreateFile on Windows with dwShareMode=0 (exclusive).
    Falls back to standard open/rename checks if pywin32 is unavailable.
    """
    p = Path(path)
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
            error_code, fn, msg = err.args
            return False, f"Win32 exclusive lock failed (code {error_code}): {msg}"
        except Exception as exc:
            return False, f"Win32 exclusive check unexpected error: {exc}"

    # Cross-Platform / Mock Fallback Path
    try:
        with open(p, "r+b") as f:
            pass
        if sys.platform == "win32":
            # On Windows without pywin32, os.rename to self fails with WinError 32 if open by another process
            os.rename(p, p)
        return True, None
    except (PermissionError, OSError) as err:
        return False, f"Fallback exclusive lock failed: {err}"


def test_size_stability(path: Union[str, Path], interval_sec: float = 1.0) -> Tuple[bool, int, Optional[str]]:
    """Tier 3 (Sync): Tests file size stability across an interval."""
    p = Path(path)
    if not p.exists():
        return False, 0, "File does not exist"
    try:
        size_0 = p.stat().st_size
    except OSError as err:
        return False, 0, f"Cannot stat file: {err}"

    if size_0 == 0:
        return False, 0, "File is zero bytes (empty/stub)"

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
    p = Path(path)
    if not p.exists():
        return False, 0, "File does not exist"
    try:
        size_0 = p.stat().st_size
    except OSError as err:
        return False, 0, f"Cannot stat file: {err}"

    if size_0 == 0:
        return False, 0, "File is zero bytes (empty/stub)"

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
    p = Path(path)
    str_path = str(p)

    if not p.exists():
        return LockCheckResult(is_locked=True, tier_failed=1, reason="File does not exist", checked_path=str_path)

    # Tier 1: Temporary & Media Filter
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
    p = Path(path)
    str_path = str(p)

    if not p.exists():
        return LockCheckResult(is_locked=True, tier_failed=1, reason="File does not exist", checked_path=str_path)

    # Tier 1
    if is_temporary_file(p, temp_extensions):
        return LockCheckResult(is_locked=True, tier_failed=1, reason="File has temporary or hidden extension", checked_path=str_path)
    if not is_supported_media(p, media_extensions):
        return LockCheckResult(is_locked=True, tier_failed=1, reason="File extension is not a supported media format", checked_path=str_path)

    # Tier 2
    handle_ok, handle_err = test_exclusive_handle(p)
    if not handle_ok:
        return LockCheckResult(is_locked=True, tier_failed=2, reason=handle_err or "Exclusive handle failed", checked_path=str_path)

    # Tier 3
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
    """Repeatedly checks lock status until unlocked or timeout is reached."""
    p = Path(path)
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

        # Backoff before next attempt
        await asyncio.sleep(poll_interval_sec)

    return LockCheckResult(
        is_locked=True,
        tier_failed=last_result.tier_failed or 2,
        reason=f"Lock wait timed out after {timeout_sec:.1f}s. Last reason: {last_result.reason}",
        file_size_bytes=last_result.file_size_bytes,
        checked_path=str(p),
    )
```

---

### 5.2 `src/watcher/ingest_watcher.py`

```python
"""
Ingestion Directory Watcher with Event Debounce, Polling Fallback, and Lock Handoff.
Module: src.watcher.ingest_watcher
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import time
from typing import Awaitable, Callable, Dict, Optional, Set, Union

from src.watcher.file_locker import (
    DEFAULT_MEDIA_EXTENSIONS,
    DEFAULT_TEMP_EXTENSIONS,
    is_supported_media,
    is_temporary_file,
    wait_until_file_unlocked,
)

logger = logging.getLogger(__name__)


class IngestWatcher:
    """
    Asynchronous filesystem watcher for the ingest directory.
    Monitors raw video drops, verifies 3-tier lock release, and invokes pipeline handoff.
    """

    def __init__(
        self,
        watch_dir: Union[str, Path],
        on_file_ready: Callable[[Path], Awaitable[None]],
        on_error: Optional[Callable[[Path, str], Awaitable[None]]] = None,
        allowed_extensions: Optional[Set[str]] = None,
        temp_extensions: Optional[Set[str]] = None,
        debounce_delay_sec: float = 0.5,
        lock_timeout_sec: float = 120.0,
        lock_poll_interval_sec: float = 1.0,
        size_debounce_interval_sec: float = 1.0,
        enable_polling_fallback: bool = True,
        polling_fallback_interval_sec: float = 5.0,
    ) -> None:
        self.watch_dir = Path(watch_dir).resolve()
        self.on_file_ready = on_file_ready
        self.on_error = on_error
        self.allowed_extensions = allowed_extensions or DEFAULT_MEDIA_EXTENSIONS
        self.temp_extensions = temp_extensions or DEFAULT_TEMP_EXTENSIONS
        self.debounce_delay_sec = debounce_delay_sec
        self.lock_timeout_sec = lock_timeout_sec
        self.lock_poll_interval_sec = lock_poll_interval_sec
        self.size_debounce_interval_sec = size_debounce_interval_sec
        self.enable_polling_fallback = enable_polling_fallback
        self.polling_fallback_interval_sec = polling_fallback_interval_sec

        self._running = False
        self._watcher_task: Optional[asyncio.Task] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._active_evaluations: Dict[Path, asyncio.Task] = {}
        self._processed_files: Set[Path] = set()
        self._pending_debounce: Dict[Path, float] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Starts the watcher and polling fallback background tasks."""
        if self._running:
            return

        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        logger.info(f"Starting IngestWatcher on: {self.watch_dir}")

        # Launch primary watcher task
        self._watcher_task = asyncio.create_task(self._run_watchfiles(), name="ingest_watchfiles")

        # Launch polling fallback if enabled
        if self.enable_polling_fallback:
            self._polling_task = asyncio.create_task(self._run_polling_fallback(), name="ingest_polling")

        # Execute an immediate initial scan
        await self.scan_once()

    async def stop(self) -> None:
        """Stops the watcher and gracefully cancels in-flight evaluation tasks."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping IngestWatcher...")

        if self._watcher_task and not self._watcher_task.done():
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass

        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

        # Cancel active evaluations
        for task in list(self._active_evaluations.values()):
            if not task.done():
                task.cancel()
        if self._active_evaluations:
            await asyncio.gather(*self._active_evaluations.values(), return_exceptions=True)
        self._active_evaluations.clear()

        logger.info("IngestWatcher stopped successfully.")

    async def scan_once(self) -> int:
        """Scans the watch directory for any pending media files."""
        if not self.watch_dir.exists():
            return 0

        detected_count = 0
        try:
            for entry in os.scandir(self.watch_dir):
                if entry.is_file():
                    p = Path(entry.path).resolve()
                    if self._should_consider_file(p):
                        self._trigger_file_evaluation(p)
                        detected_count += 1
        except Exception as exc:
            logger.error(f"Error during scan_once: {exc}", exc_info=True)

        return detected_count

    def _should_consider_file(self, path: Path) -> bool:
        """Determines if a file path is eligible for lock evaluation."""
        if path in self._processed_files or path in self._active_evaluations:
            return False
        if is_temporary_file(path, self.temp_extensions):
            return False
        if not is_supported_media(path, self.allowed_extensions):
            return False
        return True

    def _trigger_file_evaluation(self, path: Path) -> None:
        """Debounces and schedules a background evaluation task for a file."""
        if path in self._active_evaluations and not self._active_evaluations[path].done():
            return

        task = asyncio.create_task(
            self._evaluate_and_handoff(path),
            name=f"eval_lock_{path.name}"
        )
        self._active_evaluations[path] = task

        # Cleanup task reference on completion
        def _cleanup(t: asyncio.Task) -> None:
            self._active_evaluations.pop(path, None)

        task.add_done_callback(_cleanup)

    async def _evaluate_and_handoff(self, path: Path) -> None:
        """Wait for lock release and hand off to the pipeline callback."""
        # Debounce buffer
        await asyncio.sleep(self.debounce_delay_sec)

        if not path.exists():
            return

        logger.info(f"Evaluating 3-tier lock status for: {path.name}")
        lock_result = await wait_until_file_unlocked(
            path,
            timeout_sec=self.lock_timeout_sec,
            poll_interval_sec=self.lock_poll_interval_sec,
            debounce_interval_sec=self.size_debounce_interval_sec,
            media_extensions=self.allowed_extensions,
            temp_extensions=self.temp_extensions,
        )

        if lock_result.is_ready:
            logger.info(f"File unlocked and stable: {path.name} ({lock_result.file_size_bytes} bytes). Handing off to pipeline.")
            self._processed_files.add(path)
            try:
                await self.on_file_ready(path)
            except Exception as exc:
                logger.error(f"Error during on_file_ready callback for {path.name}: {exc}", exc_info=True)
                if self.on_error:
                    await self.on_error(path, str(exc))
        else:
            logger.warning(f"File failed lock release: {path.name}. Reason: {lock_result.reason}")
            if self.on_error:
                await self.on_error(path, lock_result.reason)

    async def _run_watchfiles(self) -> None:
        """Primary watcher loop using watchfiles."""
        try:
            import watchfiles
            async for changes in watchfiles.awatch(self.watch_dir, stop_event=None):
                if not self._running:
                    break
                for change_type, raw_path in changes:
                    p = Path(raw_path).resolve()
                    if self._should_consider_file(p):
                        self._trigger_file_evaluation(p)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning(f"watchfiles engine encountered error: {exc}. Relying on polling fallback.")

    async def _run_polling_fallback(self) -> None:
        """Periodic background polling loop to guarantee zero missed drops."""
        while self._running:
            try:
                await asyncio.sleep(self.polling_fallback_interval_sec)
                if self._running:
                    await self.scan_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Polling fallback error: {exc}", exc_info=True)

    async def __aenter__(self) -> "IngestWatcher":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()
```

---

## 6. Verification and Test Strategy (TDAD & Leash Protocol)

In accordance with Rule R2 (The Zero-Discretion Mandate / Leash Protocol), the following test suite will verify the implementation with deterministic assertions.

### 6.1 Unit Tests for `test_file_locker.py`

| Test ID | Test Scenario | Assertions |
|---|---|---|
| `test_tier1_temporary_extensions` | Feed `.tmp`, `.part`, `.crdownload`, `.aria2`, `.downloading`, `sample.mp4.tmp` | `is_temporary_file(path) == True`; `check_file_lock(path).tier_failed == 1` |
| `test_tier1_hidden_prefix_rejection` | Feed `~$clip.mp4`, `.hidden.mp4`, `._clip.mp4` | `is_temporary_file(path) == True` |
| `test_tier1_unsupported_media` | Feed `notes.txt`, `image.png`, `data.json` | `is_supported_media(path) == False`; `check_file_lock(path).tier_failed == 1` |
| `test_tier1_valid_media_extensions` | Feed `.mp4`, `.MOV`, `.MKV`, `.webm` | `is_supported_media(path) == True` |
| `test_tier2_exclusive_handle_held` | Open temporary file with exclusive lock in Python / mock `win32file.CreateFile` raising error 32 | `test_exclusive_handle(path)[0] == False`; `check_file_lock(path).tier_failed == 2` |
| `test_tier2_exclusive_handle_released` | Close the write handle on the file | `test_exclusive_handle(path)[0] == True` |
| `test_tier2_fallback_without_pywin32` | Patch `_PYWIN32_AVAILABLE = False` and test lock detection | Fallback mechanism detects locked/unlocked state accurately |
| `test_tier3_zero_byte_file` | Create empty 0-byte file `sample.mp4` | `check_file_lock(path).tier_failed == 3`; reason contains "zero bytes" |
| `test_tier3_size_growth_detection` | Append bytes to file during the debounce window | `check_file_lock(path, debounce_interval_sec=0.1).tier_failed == 3` |
| `test_tier3_size_stable_success` | Write 1024 bytes and let debounce window elapse without modification | `check_file_lock(path).is_ready == True`; `file_size_bytes == 1024` |
| `test_wait_until_unlocked_success` | Release file lock after 0.2s in background task | `await wait_until_file_unlocked(...)` returns `is_ready == True` |
| `test_wait_until_unlocked_timeout` | Hold file lock continuously past timeout | Returns `is_locked == True` with timeout reason |

### 6.2 Unit Tests for `test_ingest_watcher.py`

| Test ID | Test Scenario | Assertions |
|---|---|---|
| `test_watcher_lifecycle` | Start and stop `IngestWatcher` | `is_running == True` after start, `is_running == False` after stop; zero leaked background tasks |
| `test_watcher_detects_valid_file_drop` | Drop `clip.mp4` into ingest directory | Callback `on_file_ready` invoked with exact Path within 2.0s |
| `test_watcher_ignores_temporary_files` | Drop `clip.crdownload` | `on_file_ready` is NOT called |
| `test_watcher_handles_atomic_rename` | Drop `clip.tmp`, write data, rename to `clip.mp4` | `on_file_ready` is called for `clip.mp4` after rename |
| `test_watcher_event_debouncing` | Write to `clip.mp4` 5 times in 100ms | `on_file_ready` is invoked exactly ONCE |
| `test_polling_fallback_recovers_preexisting` | Place `preexisting.mp4` before starting watcher | `on_file_ready` is invoked during initial scan / polling |
| `test_watcher_error_callback_on_timeout` | Hold exclusive write lock for longer than `lock_timeout_sec` | `on_error` callback is invoked with failure reason |

---

## 7. Integration & Interface Alignment with M1 Modules

1. **`config/settings.py` (M1 Explorer 1)**:
   - Settings provides `settings.ingest_dir`, `settings.allowed_media_extensions`, `settings.lock_timeout_sec`.
   - `IngestWatcher` defaults can be loaded directly from `get_settings()`.
2. **`src/models/schemas.py` & `src/models/state_machine.py` (M1 Explorer 1)**:
   - When `on_file_ready` fires, orchestrator receives verified `file_path` and `file_size_bytes`.
   - Orchestrator creates `JobMetadata` in status `JobStatus.INGESTED`.
3. **`src/pipeline/orchestrator.py` & `job_manager.py` (M1 Explorer 3)**:
   - Orchestrator instantiates `IngestWatcher(watch_dir=settings.ingest_dir, on_file_ready=self.handle_ingested_file)`.
   - `handle_ingested_file` registers job in `JobManager` and triggers the probe/ML grading pipeline.

---
