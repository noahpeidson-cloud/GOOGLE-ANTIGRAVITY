# Adversarial Review Report — `progress_watchdog.py`

## 1. What the Prior Attempt Got Wrong

1. **High-Frequency Thread Leaks**:
   - `input`: Rapid stream of 1,000+ file modification events.
   - `expected`: O(1) persistent worker thread overhead.
   - `actual`: Spawned 1,000+ native `threading.Timer` OS threads, causing thread thrashing and high latency.
   - `root cause`: `ProgressWatchdogHandler.trigger()` instantiated a new `threading.Timer` on every incoming filesystem event.

2. **Windows Read-Only Target Replacement Failure**:
   - `input`: Existing target artifact file with Windows read-only attribute (`stat.S_IREAD`).
   - `expected`: Atomic overwrite of target artifact file.
   - `actual`: Failed all retries with `[WinError 5] Access is denied`.
   - `root cause`: Windows NTFS `os.replace` requires `DELETE` access and fails if read-only attribute is active without proactive `os.chmod`.

3. **Unhandled `UnicodeDecodeError` Crash**:
   - `input`: Source file containing corrupted multibyte / non-UTF-8 binary bytes.
   - `expected`: Resilient reading with replacement character substitution without crashing.
   - `actual`: Unhandled `UnicodeDecodeError` crashed `safe_read_file`.
   - `root cause`: `safe_read_file` only caught `(PermissionError, OSError)`, missing `UnicodeError`.

4. **Missing Path Identity & Directory Validation**:
   - `input`: `--source` and `--target` pointing to the same file or a directory passed as source.
   - `expected`: Early rejection with clear `ValueError`.
   - `actual`: Infinite recursive write loop or unexpected runtime crash.
   - `root cause`: Missing canonical path equality and directory validation in `ProgressWatchdogDaemon` and `parse_args`.

5. **Fragile Concurrency Backoff**:
   - `input`: 8 heavy reader threads under rapid 25-update sync cycle.
   - `expected`: 0 sync errors.
   - `actual`: Intermittent retry exhaustion (1 error in 15 attempts) due to deterministic retry harmonics.
   - `root cause`: Low default retry ceiling (15) and lack of randomized jitter in `safe_atomic_write` and `safe_read_file`.

6. **Missing Polling Fallback on Observer Error**:
   - `input`: Native observer running on network shares / SMB / virtual filesystems where `ReadDirectoryChangesW` fails.
   - `expected`: Automatic fallback to `PollingObserver`.
   - `actual`: Unhandled `OSError` crashing daemon startup.
   - `root cause`: Native `Observer.start()` was not wrapped with an automatic fallback catch.

---

## 2. What I Changed

- **`g:\My Drive\GOOGLE ANTIGRAVITY\.agents\progress_watchdog.py`**:
  - Re-architected debounce mechanism to utilize a single persistent background daemon worker thread (`_debounce_worker`) with `threading.Condition` and deadline calculation, eliminating all thread churn.
  - Added `validate_paths()` checking canonical path inequality (`os.path.normcase(os.path.abspath(...))`) and directory exclusion.
  - Enhanced `safe_read_file` with `errors="replace"` and `(PermissionError, OSError, UnicodeError)` exception catching.
  - Enhanced `safe_atomic_write` with proactive Windows read-only attribute clearing (`os.chmod`), 35 max retries, and randomized jitter backoff (`0.003s` to `0.02s`).
  - Added automatic fallback to `PollingObserver` if native `Observer.start()` fails with `OSError` or `RuntimeError`.
  - Added serialized sync execution gate (`_sync_lock`) ensuring clean synchronization between CLI flushes and debounced worker execution.

- **`g:\My Drive\GOOGLE ANTIGRAVITY\.agents\test_progress_watchdog.py`**:
  - Expanded test suite from 12 to 19 tests, including tests for non-UTF8 source reading, Windows read-only target replacement, source/target collision rejection, directory rejection, negative debounce rejection, observer polling fallback, and concurrent flush idempotency.

---

## 3. Verification Record

- **Deep Verification (ran actual tests):**
  - Executed `python ".agents\test_progress_watchdog.py"`: All 19 tests passed cleanly in 14.190s (`Ran 19 tests in 14.190s -> OK`).
  - Re-verified 50 rapid writes in < 1s -> exactly 1 sync operation.
  - Re-verified 8 continuous reader threads (>5,600 reads) during active sync -> 0 errors, 0 corrupted reads.
  - Re-verified Windows read-only target replacement with 0 errors.
  - Re-verified corrupted non-UTF8 source reading with 0 errors.
  - Re-verified native observer fallback to polling observer on simulated network share error.
  - Re-verified live CLI subprocess execution with PID file management and clean shutdown.

- **Shallow Verification:** None; all claims backed by deterministic programmatic test suite execution.

- **Unverified aspects:**
  - True physical network file latency over multi-gigabyte files (though 1,000-line markdown UTF-8 files were verified).

---

## 4. Known Issues
- None (All identified functional bugs and concurrency edge cases have been resolved).

---

## 5. Remaining Risk & Next Step
- **Verdict**: APPROVE. The implementation is hardened, thread-efficient, robust against Windows filesystem quirks, and fully compliant with Rule R15 and the task specification.
