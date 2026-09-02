# Adversarial Review Findings — `progress_watchdog.py`

## 1. Defects Identified & Root Cause Analysis

### Issue 1: High-Frequency Thread Explosion in Debounce Mechanism
- **Input**: Rapid event bursts (e.g. 1,000+ file modification events during streaming operations).
- **Expected**: Lightweight debouncing with zero OS thread churn and bounded memory.
- **Actual**: `ProgressWatchdogHandler.trigger()` instantiated and started a new `threading.Timer` (a full native OS thread) on every single event, thrashing OS thread creation and risking `RuntimeError: can't start new thread`.
- **Root Cause**: Spawning ephemeral timer threads on every filesystem event rather than maintaining a single persistent background worker thread with deadline synchronization.

### Issue 2: Windows Read-Only Target Replacement Failure (`[WinError 5] Access is denied`)
- **Input**: Target artifact file exists with read-only permissions (`stat.S_IREAD`).
- **Expected**: Target artifact updated atomically without permission errors.
- **Actual**: `safe_atomic_write` failed all 15 retry attempts with `[WinError 5] Access is denied` during `os.replace`.
- **Root Cause**: Windows NTFS denies rename/delete operations over files with the read-only attribute set unless write permissions are explicitly granted prior to replacement.

### Issue 3: Unhandled `UnicodeDecodeError` Crash Risk
- **Input**: Source file containing malformed, binary, or non-UTF-8 multibyte sequences.
- **Expected**: Safe reading with fallback replacement without throwing unhandled exceptions.
- **Actual**: `safe_read_file` only caught `(PermissionError, OSError)`. `UnicodeDecodeError` (subclass of `ValueError`) caused unhandled exceptions.
- **Root Cause**: Missing error handling and `errors="replace"` fallback during file decode.

### Issue 4: Missing Source/Target Identity Validation (Infinite Loop Risk)
- **Input**: Daemon invoked with `--source file.md --target file.md` (or case-insensitive path match on Windows).
- **Expected**: Immediate fast-fail rejection with `ValueError`.
- **Actual**: Daemon initialized without validation, leading to an infinite self-triggering feedback write loop upon the first modification.
- **Root Cause**: Lack of canonical path comparison (`os.path.normcase(os.path.abspath(...))`) during initialization.

### Issue 5: Missing Directory and Argument Bounds Validation
- **Input**: Directory passed as `--source` or non-positive `--debounce` (e.g. `<= 0`).
- **Expected**: Clear validation error and rejection.
- **Actual**: Silent misconfiguration or runtime directory read failure.
- **Root Cause**: Missing input validation checks in `ProgressWatchdogDaemon` and `parse_args`.

### Issue 6: Lack of Automatic Fallback for Unsupported Native Watchdog Observers
- **Input**: File monitoring on network drives, SMB shares, or virtual filesystem mounts where `ReadDirectoryChangesW` fails.
- **Expected**: Graceful automatic fallback to `PollingObserver`.
- **Actual**: Uncaught `OSError` crashed daemon initialization.
- **Root Cause**: Direct invocation of `Observer.start()` without fallback catch.

### Issue 7: Reader-Writer Lockstep Collisions in Extreme Concurrency
- **Input**: 8 concurrent continuous reader threads hammering target file during 25 rapid updates.
- **Expected**: 100% sync success with 0 errors.
- **Actual**: Periodic retry exhaustion due to deterministic retry timing resonance.
- **Root Cause**: Lack of randomized jitter backoff and low default retry limit (15 retries).

---

## 2. Remediations Implemented
1. **Persistent Worker Debounce Loop**: Replaced `threading.Timer` creation with a dedicated worker thread using `threading.Condition` and deadline calculation. Thread count stays constant (1 worker thread) regardless of event volume.
2. **Windows Read-Only Attribute Handling**: Added proactive `os.chmod(target_abs, stat.S_IWRITE | stat.S_IREAD)` before and during `os.replace` retry attempts.
3. **Robust UTF-8 Decoding**: Configured `errors="replace"` and expanded caught exceptions to `(PermissionError, OSError, UnicodeError)` in `safe_read_file`.
4. **Strict Canonical Path & Argument Validation**: Added `validate_paths()` checking source != target and preventing directory sources; enforced `debounce_interval > 0`.
5. **Automatic PollingObserver Fallback**: Wrapped native `Observer.start()` to seamlessly fallback to `PollingObserver` on network/virtual filesystem errors.
6. **Jittered Exponential Backoff**: Increased default retries to 35 and added randomized jitter (`0.003s` to `0.025s`) to eliminate reader/writer lockstep resonance.
7. **Serialized Sync Gate**: Added `_sync_lock` to serialize disk I/O operations and avoid race conditions between CLI flushes and debounced worker syncs.
