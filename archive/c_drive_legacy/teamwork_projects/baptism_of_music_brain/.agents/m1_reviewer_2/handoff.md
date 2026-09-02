# Milestone 1 Review & Adversarial Challenge Report — Reviewer 2

## Review Summary

- **Verdict**: **REQUEST_CHANGES**
- **Overall Risk Assessment**: **MEDIUM**
- **Integrity Assessment**: **PASS** (Zero integrity violations; genuine implementations with no hardcoded test facades or fabricated results).

---

## 1. Observation

### Codebase & Test Observations

1. **Test Execution (`pytest -v tests/tier1_feature/test_file_locker.py tests/tier1_feature/test_job_manager.py tests/tier2_boundary/test_boundary_locking.py`)**:
   - `tests/tier1_feature/test_file_locker.py`: 11 / 11 PASSED.
   - `tests/tier1_feature/test_job_manager.py`: 13 / 13 PASSED.
   - `tests/tier2_boundary/test_boundary_locking.py`: **8 / 8 SKIPPED** with message:
     `tests\tier2_boundary\test_boundary_locking.py:20: src.watcher.file_locker not yet implemented`
   - Total across targeted files: 24 passed, 8 skipped in 0.91s.

2. **Missing Interface Functions in `src/watcher/file_locker.py`**:
   - `tests/tier2_boundary/test_boundary_locking.py` lines 11–15:
     ```python
     try:
         from src.watcher.file_locker import is_file_locked, wait_until_unlocked
     except ImportError:
         is_file_locked = None
         wait_until_unlocked = None
     ```
   - In `src/watcher/file_locker.py`, the exposed functions are named `check_file_lock`, `check_file_lock_async`, and `wait_until_file_unlocked`.
   - The top-level convenience functions `is_file_locked(path, debounce_sec=0.0) -> bool` and `wait_until_unlocked(path, timeout_sec=30.0, debounce_sec=1.0) -> bool` are missing.

3. **Exclusive Handle Implementation in `src/watcher/file_locker.py` (lines 104–135)**:
   - On Windows native path:
     ```python
     handle = win32file.CreateFile(
         str(p),
         win32con.GENERIC_READ | win32con.GENERIC_WRITE,
         0,  # dwShareMode = 0 -> Exclusive access
         None,
         win32con.OPEN_EXISTING,
         win32con.FILE_ATTRIBUTE_NORMAL,
         None,
     )
     ```
   - On fallback path:
     ```python
     with open(p, "r+b"):
         pass
     ```
   - Both implementations require write permissions (`GENERIC_WRITE` / `"r+b"`). When examining a file with read-only file attributes (or permissions `0o444`), `CreateFile` / `open` fails with `ERROR_ACCESS_DENIED` (code 5) or `PermissionError`, causing unlocked read-only files to be reported as locked.

4. **Thread Safety in `src/pipeline/job_manager.py`**:
   - `JobManager` initializes `self._lock = threading.RLock()` and wraps all internal mutations and queries (`create_job`, `get_job`, `update_status`, `update_progress`, `update_edl`, `update_probe_metadata`, `set_delivery_path`, `list_jobs`, `count_jobs`, `delete_job`, `subscribe`, `unsubscribe`) in `with self._lock:` blocks.
   - Tested under high multi-threaded contention (30 threads x 20 iterations = 600 concurrent jobs), passing without race conditions or memory corruption.

5. **Event Dispatching in `src/pipeline/job_manager.py` (lines 282–308)**:
   - `_emit_event` calls subscriber callbacks while holding `self._lock`.
   - Asynchronous callbacks are scheduled safely onto the running event loop via `loop.create_task(cb(event))` without blocking the lock.

6. **Debouncing and Polling in `src/watcher/ingest_watcher.py`**:
   - `IngestWatcher` uses `_active_evaluations: Dict[Path, asyncio.Task]` to debounce duplicate file system notifications.
   - Dual-mode architecture utilizes `watchfiles.awatch` with an asynchronous background polling fallback (`_run_polling_fallback`).
   - Clean task cancellation and resource reclamation in `stop()`.

---

## 2. Logic Chain

1. **Step 1: Test Suite Verification**:
   - Running `pytest` on the three target test modules revealed 24 passing tests and 8 skipped tests.
   - Tracing the skip condition in `test_boundary_locking.py` confirmed that the boundary test suite could not import `is_file_locked` and `wait_until_unlocked`.

2. **Step 2: Win32 Exclusive Handle Analysis**:
   - The purpose of `test_exclusive_handle` in video ingestion is to verify that another process (e.g. file copy, browser download, FTP bridge) is not actively writing to the source media.
   - Setting `dwShareMode=0` requests exclusive sharing mode (blocking or detecting other open handles).
   - However, specifying `GENERIC_WRITE` in the desired access flags demands write permissions to the file system entity.
   - In production video pipelines, raw footage from cameras, SD cards, or network shares is often marked read-only.
   - When a read-only file is tested, `CreateFile` fails with `ERROR_ACCESS_DENIED` (error code 5), which is currently caught and returned as `is_locked=True` (`Win32 exclusive lock failed (code 5): Access is denied`).
   - Consequently, read-only footage can never pass lock validation and will stall ingestion.

3. **Step 3: Concurrency & Thread Safety Evaluation**:
   - `JobManager` utilizes `threading.RLock`, ensuring recursive safety when status updates trigger internal queries or state lookups.
   - `IngestWatcher` properly separates async event listening (`watchfiles`) from task debouncing (`_active_evaluations`), preventing unhandled coroutine pileups.
   - `file_locker.py` properly closes Win32 handles via `win32file.CloseHandle(handle)` immediately after acquisition in the success path, preventing handle leaks.

---

## 3. Findings

### [Major] Finding 1: Missing Convenience Functions in `src/watcher/file_locker.py`
- **What**: `is_file_locked` and `wait_until_unlocked` are not defined or exported.
- **Where**: `src/watcher/file_locker.py` and `src/watcher/__init__.py`.
- **Why**: `tests/tier2_boundary/test_boundary_locking.py` requires `is_file_locked(path, debounce_sec=0.0) -> bool` and `wait_until_unlocked(path, timeout_sec=30.0, debounce_sec=1.0) -> bool`. Because these functions are missing, all 8 boundary tests are skipped.
- **Suggestion**:
  Add synchronous helper functions in `src/watcher/file_locker.py` and export in `src/watcher/__init__.py`:
  ```python
  def is_file_locked(path: Union[str, Path], debounce_sec: float = 0.0) -> bool:
      """Convenience helper returning True if file is locked or unready, False if unlocked."""
      result = check_file_lock(path, debounce_interval_sec=debounce_sec)
      return result.is_locked

  def wait_until_unlocked(
      path: Union[str, Path],
      timeout_sec: float = 30.0,
      debounce_sec: float = 1.0,
      poll_interval_sec: float = 0.25,
  ) -> bool:
      """Synchronous polling helper returning True when unlocked, False on timeout."""
      if timeout_sec <= 0:
          return not is_file_locked(path, debounce_sec=0.0)
      start = time.monotonic()
      while (time.monotonic() - start) < timeout_sec:
          if not is_file_locked(path, debounce_sec=debounce_sec):
              return True
          time.sleep(poll_interval_sec)
      return False
  ```

### [Major] Finding 2: `test_exclusive_handle` Rejects Read-Only Footage with Access Denied
- **What**: `CreateFile` requests `GENERIC_WRITE` and fallback uses `open(p, "r+b")`, which fails on read-only files.
- **Where**: `src/watcher/file_locker.py`, lines 108 and 127.
- **Why**: Read-only media files cannot be opened with write access, causing `CreateFile` to fail with error code 5 (`ERROR_ACCESS_DENIED`) and treating valid, unlocked read-only clips as locked.
- **Suggestion**:
  In `test_exclusive_handle`:
  - Request `win32con.GENERIC_READ` with `dwShareMode = 0` (exclusive access mode).
  - In fallback, use `open(p, "rb")` (with `os.rename(p, p)` on Windows to verify exclusive sharing).

### [Minor] Finding 3: Unbounded `_processed_files` Set in `IngestWatcher`
- **What**: `self._processed_files` grows unbounded in memory.
- **Where**: `src/watcher/ingest_watcher.py`, line 58.
- **Why**: In long-running processes, retaining all processed paths forever consumes memory and prevents reprocessing if a file of the same name is removed and re-dropped later.
- **Suggestion**: Use an LRU cache or bounded collection, or check `st_mtime` to permit re-ingestion of modified/replaced files.

### [Minor] Finding 4: Pub/Sub Callbacks Executed Inside Lock
- **What**: `_emit_event` invokes synchronous subscriber callbacks while holding `self._lock`.
- **Where**: `src/pipeline/job_manager.py`, lines 296–308.
- **Why**: While `RLock` prevents re-entrancy deadlocks on the same thread, a synchronous callback that blocks or waits on another thread acquiring `JobManager._lock` could cause thread contention.
- **Suggestion**: Collect the subscriber callback list under lock, and invoke synchronous callbacks after releasing the lock if callbacks perform heavy external work.

---

## 4. Caveats

1. **Milestone Scope**: Milestone 2 endpoints (`src/api/app.py`, `src/ml_brain/mock_provider.py`) and Milestone 3 rendering components (`src/renderer/filtergraph.py`, `src/renderer/profiles.py`) are skipped in test runs as intended for Milestone 1.
2. **Review-Only Constraint**: In accordance with the Reviewer role constraints, no source code was directly modified by this agent.

---

## 5. Conclusion

**Verdict: REQUEST_CHANGES**

The architectural foundation for Milestone 1 is well-structured, thread-safe, and free of integrity shortcuts. However, two Major items require remediation by the implementation worker:
1. Export the expected convenience functions `is_file_locked` and `wait_until_unlocked` in `src/watcher/file_locker.py` so that Tier 2 boundary locking tests can execute.
2. Adjust `test_exclusive_handle` to open handles with `GENERIC_READ` (`dwShareMode=0`) so that read-only media footage is correctly identified as unlocked.

---

## 6. Verification Method

To independently verify the resolution of these findings:
1. Ensure `is_file_locked` and `wait_until_unlocked` are implemented and exported in `src/watcher/file_locker.py` and `src/watcher/__init__.py`.
2. Run the targeted test suite:
   ```powershell
   python -m pytest -v tests/tier1_feature/test_file_locker.py tests/tier1_feature/test_job_manager.py tests/tier2_boundary/test_boundary_locking.py
   ```
3. Assert that all 32 tests (including all 8 tests in `test_boundary_locking.py`) pass with **0 skipped** and **0 failures**.
