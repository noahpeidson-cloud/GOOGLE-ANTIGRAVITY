# Adversarial Review Findings (Iteration 3)

## Summary
The SWE Light Adversarial Reviewer audited the watchdog daemon implementation (`progress_watchdog.py`) and test suite (`test_progress_watchdog.py`), discovering 6 distinct failure modes and edge case vulnerabilities across directory path handling, logger reconfiguration, unhandled filesystem exceptions, and cross-volume path matching.

---

## Defects Discovered & Resolved

### 1. Unhandled `OSError` / `FileNotFoundError` in `safe_sync` and `safe_atomic_write` on Inaccessible Drives
- **Input**: Passing a target path located on an unmounted/inaccessible drive (e.g. `Z:\invalid_volume\task.md`).
- **Expected**: `safe_sync` and `safe_atomic_write` catch the filesystem error, log a structured error, and safely return `False`.
- **Actual**: Threw unhandled `FileNotFoundError: [WinError 3] The system cannot find the path specified: 'Z:\\'` directly to the caller.
- **Root Cause**: `os.makedirs(target_dir, exist_ok=True)` was placed prior to the enclosing `try...except` block in both functions.
- **Fix**: Wrapped directory creation within the main `try...except` block with dedicated `OSError` error handling.

### 2. Logger Reconfiguration Silently Drops `FileHandler` and Level Updates
- **Input**: Calling `setup_logger(..., log_file='watchdog.log')` after `setup_logger()` or after logger handlers were initialized.
- **Expected**: Attach `FileHandler` to write logs to `watchdog.log` and update the logger level.
- **Actual**: `FileHandler` was never attached; log file output was silently dropped.
- **Root Cause**: `setup_logger` wrapped all handler creation inside `if not logger.handlers:`, which blocked subsequent `FileHandler` attachments on pre-existing loggers.
- **Fix**: Replaced monolithic guard with granular checks (`has_stream_handler` and `has_this_file_handler`) and explicit `logger.setLevel()`.

### 3. Trailing Slash and Uncreated Directory Target Bypass
- **Input**: Starting daemon with `--target ./nonexistent_dir/` (trailing slash).
- **Expected**: Fast-fail rejection with `ValueError` identifying that target is explicitly specified as a directory.
- **Actual**: `validate_paths` checked `os.path.isdir()`, which returned `False` because the directory did not yet exist on disk, causing `safe_sync` to create a regular file named `nonexistent_dir`.
- **Root Cause**: `validate_paths` lacked checks for trailing directory separators (`/` and `\\`) on source and target paths.
- **Fix**: Added explicit trailing slash detection and root drive volume validation.

### 4. Negative / Zero `max_wait` Unchecked in CLI Parser
- **Input**: Running `progress_watchdog.py` with `--max-wait -1.0` or `--max-wait 0`.
- **Expected**: CLI parser rejection.
- **Actual**: Parser accepted negative values.
- **Root Cause**: `parse_args` only checked `args.debounce <= 0`.
- **Fix**: Added validation rejecting `args.max_wait <= 0`.

### 5. Incomplete Path Normalization in `ProgressWatchdogHandler`
- **Input**: Passing short 8.3 paths (e.g. `C:\Users\NOAH~1\...`), relative paths, or symlinks to `ProgressWatchdogHandler`.
- **Expected**: Event matching succeeds regardless of whether watchdog delivers abspath, realpath, or relative path.
- **Actual**: `_matches_source` compared `os.path.realpath(event_path)` against `os.path.abspath(source_path)` without realpath normalization in handler `__init__`.
- **Root Cause**: Asymmetric normalization between initialization and event dispatch.
- **Fix**: Stored both realpath and abspath normalized forms and checked both in `_matches_source`.

### 6. Missing Transient Retry on Opening Destination Temporary File
- **Input**: Windows Defender or indexing service transiently locking new file creation in destination folder.
- **Expected**: Retried creation with jittered backoff.
- **Actual**: Immediate hard failure on attempt 0.
- **Root Cause**: `open(tmp_path, "wb")` was executed without a retry loop.
- **Fix**: Added jittered retry loop around temporary file creation in `safe_sync`.
