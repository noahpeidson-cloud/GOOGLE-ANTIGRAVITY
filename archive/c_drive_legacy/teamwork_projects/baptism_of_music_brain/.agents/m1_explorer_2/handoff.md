# Handoff Report: Ingest Watcher & 3-Tier Windows File Lock Detector (Milestone 1)

**Agent:** `m1_explorer_2` (Explorer 2 — Milestone 1)  
**Parent:** `c878e1aa-1a39-4b58-ae7a-edef54099979`  
**Date:** 2026-08-27T10:08:00Z  
**Handoff Type:** Hard (Milestone 1 Investigation & Plan Complete)  

---

## 1. Observation

1. **Environment & Dependency Verification**:
   - Executed terminal probe: `python -c "import win32file, win32con, pywintypes; import watchdog; import watchfiles"`
   - Output:
     ```
     win32file OK
     watchdog OK
     watchfiles OK
     ```
     Confirms native `pywin32` (`win32file`), `watchdog` (`6.0.0`), and `watchfiles` (`1.2.0`) are active in Python 3.13.14 on Windows 11.

2. **Empirical Win32 Exclusive Handle Locking Behavior**:
   - Evaluated `win32file.CreateFile` against an active in-flight open file handle with `dwShareMode=0`:
     - Verbatim error returned:
       ```
       (32, 'CreateFile', 'The process cannot access the file because it is being used by another process.')
       ```
     - Verbatim success returned when handle was closed:
       ```
       Success acquiring exclusive handle when closed
       ```
   - Evaluated fallback `os.rename(filepath, filepath)` on an open file in Windows without `pywin32`:
     - Verbatim error returned:
       ```
       [WinError 32] The process cannot access the file because it is being used by another process: '...\\tmp...' -> '...\\tmp...'
       ```

3. **Empirical Watchdog and Watchfiles Event Behavior**:
   - `watchdog.observers.Observer` fires `on_created` and `on_modified` synchronously.
   - `watchfiles.awatch` yielded `(Change.added, '...\\test2.mp4')` asynchronously within the Python event loop without thread blocking.

4. **Interface Requirements**:
   - `PROJECT.md` lines 50–51 & 120–123 specify:
     - `src/watcher/file_locker.py`: 3-tier lock detection (ext filter, Win32 exclusive handle test, 1.0s size debounce) for incomplete copies.
     - `src/watcher/ingest_watcher.py`: Ingest directory watcher (Watchdog + async polling fallback).
   - `ORIGINAL_REQUEST.md` lines 17, 31 specify monitoring local `ingest` directory and asserting integration file drop detection.

---

## 2. Logic Chain

1. **From Observation 1 & 2 to Tier 2 Exclusive Lock Design**:
   - Because Windows multi-gigabyte copies hold open write handles that trigger OS error code 32 (`ERROR_SHARING_VIOLATION`), testing `win32file.CreateFile(..., dwShareMode=0, ...)` directly provides an instantaneous, non-blocking check for active copy operations.
   - For platforms or mock test environments without `pywin32`, standard `open(..., 'r+b')` combined with `os.rename(path, path)` provides an exact behavioral surrogate on Windows.

2. **From Observation 2 & 4 to Tier 1 & Tier 3 Design**:
   - Certain downloaders and copy tools write to `.tmp`, `.part`, or `.crdownload` extensions before atomic renaming; Tier 1 extension filtering immediately eliminates premature processing of staging files.
   - Burst-write copy protocols (e.g. chunked transfers) may temporarily release file handles between byte flushes; Tier 3 size stability debounce (measuring `size(t0)` vs `size(t1)` over a 1.0s interval) guarantees that the file has reached a steady state before triggering downstream FFprobe or ML analysis.

3. **From Observation 3 & 4 to IngestWatcher Architecture**:
   - File copies can trigger multiple rapid OS events (`on_created`, multiple `on_modified`); an event debounce buffer (`debounce_delay_sec = 0.5`) coalesces these bursts.
   - Tracking active evaluation tasks (`_active_evaluations: Dict[Path, asyncio.Task]`) guarantees that only one evaluation worker executes per physical file, preventing duplicate pipeline handoffs.
   - Background polling fallback (`_run_polling_fallback` every 5.0s) ensures files placed before watcher startup or transferred via notification-bypassing mechanisms (e.g. certain network shares) are reliably detected.

---

## 3. Caveats

1. **Network File Systems (SMB/NFS)**: On remote network shares, Win32 file locks may have slight caching delays depending on client-side SMB leasing. Tier 3 (1.0s size stability debounce) provides the secondary safety net if SMB share locks report transient availability.
2. **Read-Only Investigation Boundary**: This report and plan provide complete architectural specifications and implementation code; source code files in `src/watcher/` have not been created yet to maintain strict explorer read-only protocol.

---

## 4. Conclusion

The design for `src/watcher/file_locker.py` and `src/watcher/ingest_watcher.py` is fully specified, verified against the local Windows runtime, and ready for implementation.

Key deliverables formulated:
- **`src/watcher/file_locker.py`**:
  - `is_temporary_file()`: Tier 1 temporary extension and hidden file filter.
  - `is_supported_media()`: Whitelist filter for video containers (`.mp4`, `.mov`, `.mkv`, etc.).
  - `test_exclusive_handle()`: Tier 2 native Win32 `win32file.CreateFile(dwShareMode=0)` with cross-platform fallback.
  - `test_size_stability()` & `test_size_stability_async()`: Tier 3 size growth debounce.
  - `check_file_lock()` & `check_file_lock_async()`: Full 3-tier evaluator returning `LockCheckResult`.
  - `wait_until_file_unlocked()`: Async polling backoff helper.
- **`src/watcher/ingest_watcher.py`**:
  - `IngestWatcher`: Async directory observer combining `watchfiles.awatch` with background polling fallback (`scan_once()`), event debouncing, single-worker-per-file concurrency tracking, and asynchronous handoff to `on_file_ready(path)`.
- **`plan.md`**: Complete architectural blueprint, complete code templates, and 19-point unit test matrix.

---

## 5. Verification Method

To verify this plan and test its upcoming implementation:

1. **Inspect Plan Artifacts**:
   - `view_file` on `C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_explorer_2\plan.md`
2. **Execute Independent Unit Tests** (once implemented in Milestone 1):
   - `pytest tests/tier1_feature/test_file_locker.py -v`
   - `pytest tests/tier1_feature/test_ingest_watcher.py -v`
3. **Invalidation Conditions**:
   - If `test_exclusive_handle` returns `True` while a writer holds an exclusive write handle.
   - If `IngestWatcher` triggers duplicate callbacks for a single multi-gigabyte file copy.
