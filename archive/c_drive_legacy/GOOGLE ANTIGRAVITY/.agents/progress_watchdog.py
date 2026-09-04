"""
progress_watchdog.py - Real-Time Artifact Mirror Daemon
======================================================
Production-grade background daemon that synchronizes an internal agent state
file (e.g. progress.md) to a frontend Artifact file (e.g. task.md) in real-time.

Features:
- Debounced File Synchronization: monitors source file events and mirrors contents to target.
- High-Frequency Stream Protection: strict 1.0-second debounce mechanism (configurable)
  backed by a single persistent worker thread (zero thread-explosion under event storms).
- Safe Concurrency & Windows Resilience: atomic file writes via temporary files and os.replace
  with retry backoff and Windows read-only attribute handling.
- Automatic Fallback: gracefully falls back to PollingObserver if native OS observer fails.
- Strict Validation: rejects identical source/target paths, directories as source, and <=0 debounce.
- Signal Handling: clean shutdown on SIGINT/SIGTERM/SIGBREAK with final flush guarantee.
"""

import argparse
import logging
import os
import signal
import stat
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Dict, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver


def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    name: str = "progress_watchdog",
) -> logging.Logger:
    """Configures and returns a structured logger."""
    logger = logging.getLogger(name)
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )
    if not has_stream_handler:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        log_file_abs = os.path.abspath(log_file)
        has_this_file_handler = any(
            isinstance(h, logging.FileHandler)
            and getattr(h, "baseFilename", None) == log_file_abs
            for h in logger.handlers
        )
        if not has_this_file_handler:
            log_dir = os.path.dirname(log_file_abs)
            if log_dir:
                try:
                    os.makedirs(log_dir, exist_ok=True)
                except OSError:
                    pass
            try:
                file_handler = logging.FileHandler(log_file_abs, encoding="utf-8")
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except OSError as e:
                logger.warning(f"Could not initialize FileHandler for '{log_file_abs}': {e}")

    return logger


def is_pid_alive(pid: int) -> bool:
    """Checks if a process with the given PID is currently running."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            # On Windows, os.kill(pid, 0) checks process existence in Python 3.8+
            os.kill(pid, 0)
            return True
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ProcessLookupError):
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        return True


def validate_paths(source_path: str, target_path: str) -> None:
    """Validates source and target paths to prevent destructive recursive write loops."""
    if not source_path or not isinstance(source_path, str) or not source_path.strip():
        raise ValueError("Source path must be a non-empty string.")
    if not target_path or not isinstance(target_path, str) or not target_path.strip():
        raise ValueError("Target path must be a non-empty string.")

    # Check for explicit trailing directory separators
    if target_path.rstrip().endswith(("/", "\\")):
        raise ValueError(
            f"Target path '{target_path}' ends with a directory separator. "
            "progress_watchdog requires target to be a file path, not a directory."
        )
    if source_path.rstrip().endswith(("/", "\\")):
        raise ValueError(
            f"Source path '{source_path}' ends with a directory separator. "
            "progress_watchdog only monitors individual files."
        )

    src_abs = os.path.realpath(os.path.abspath(source_path.strip()))
    tgt_abs = os.path.realpath(os.path.abspath(target_path.strip()))

    if os.path.normcase(src_abs) == os.path.normcase(tgt_abs):
        raise ValueError(
            f"Source path and target path point to the exact same file ('{src_abs}'). "
            "Mirroring a file onto itself causes an infinite recursive write feedback loop."
        )

    if os.path.exists(src_abs) and os.path.isdir(src_abs):
        raise ValueError(
            f"Source path '{src_abs}' is a directory. progress_watchdog only monitors individual files."
        )

    if os.path.exists(tgt_abs) and os.path.isdir(tgt_abs):
        raise ValueError(
            f"Target path '{tgt_abs}' is a directory. progress_watchdog requires target to be a file path."
        )

    # Check root volume paths where basename is empty
    if not os.path.basename(src_abs.rstrip("/\\")):
        raise ValueError(
            f"Source path '{src_abs}' is a drive root or directory. progress_watchdog only monitors individual files."
        )
    if not os.path.basename(tgt_abs.rstrip("/\\")):
        raise ValueError(
            f"Target path '{tgt_abs}' is a drive root or directory. progress_watchdog requires target to be a file path."
        )


import random


def safe_read_file(
    file_path: str,
    max_retries: int = 30,
    retry_delay: float = 0.01,
    allow_empty: bool = True,
) -> Optional[str]:
    """Safely reads a file with jittered retry backoff to handle transient locks, non-UTF8 bytes, mid-write truncations, and atomic replace races on Windows."""
    for attempt in range(max_retries):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                if (
                    not allow_empty
                    and len(content) == 0
                    and attempt < max_retries - 1
                ):
                    sleep_time = (retry_delay * (1.15**attempt)) + random.uniform(0.002, 0.015)
                    time.sleep(sleep_time)
                    continue
                return content
        except FileNotFoundError:
            # Allow up to 4 retries for transient atomic replace windows by external editors
            if attempt < 4 and attempt < max_retries - 1:
                time.sleep(0.005 + random.uniform(0.001, 0.005))
                continue
            return None
        except (PermissionError, OSError, UnicodeError) as e:
            if attempt == max_retries - 1:
                logging.getLogger("progress_watchdog").warning(
                    f"Failed to read file '{file_path}' after {max_retries} attempts: {e}"
                )
                return None
            sleep_time = (retry_delay * (1.15**attempt)) + random.uniform(0.002, 0.015)
            time.sleep(sleep_time)
    return None


def safe_atomic_write(
    target_path: str,
    content: Any,
    max_retries: int = 30,
    retry_delay: float = 0.01,
) -> bool:
    """Safely writes content (str or bytes) to target_path atomically using a temporary file in the
    same directory and os.replace, with jittered retry backoff and Windows read-only attribute handling.
    """
    try:
        target_abs = os.path.abspath(target_path)
        target_dir = os.path.dirname(target_abs)
        if target_dir:
            try:
                os.makedirs(target_dir, exist_ok=True)
            except OSError as e:
                logging.getLogger("progress_watchdog").error(
                    f"Could not create target directory '{target_dir}': {e}"
                )
                return False

        target_name = os.path.basename(target_abs)
        if not target_name:
            logging.getLogger("progress_watchdog").error(
                f"Target path '{target_abs}' has no filename."
            )
            return False

        tmp_name = f".{target_name}.tmp_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}"
        tmp_path = os.path.join(target_dir, tmp_name)
    except Exception as e:
        logging.getLogger("progress_watchdog").error(
            f"Failed to prepare atomic write path for '{target_path}': {e}"
        )
        return False

    tmp_created = False
    try:
        is_binary = isinstance(content, (bytes, bytearray))
        mode = "wb" if is_binary else "w"
        encoding = None if is_binary else "utf-8"

        for attempt in range(max_retries):
            try:
                with open(tmp_path, mode, encoding=encoding) as f:
                    f.write(content)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        pass
                tmp_created = True
                break
            except (PermissionError, OSError) as e:
                if attempt == max_retries - 1:
                    logging.getLogger("progress_watchdog").error(
                        f"Failed to write temporary file '{tmp_path}' after {max_retries} attempts: {e}"
                    )
                    return False
                sleep_time = (retry_delay * (1.15**attempt)) + random.uniform(0.003, 0.02)
                time.sleep(sleep_time)

        if not tmp_created:
            return False

        for attempt in range(max_retries):
            try:
                if os.path.exists(target_abs):
                    try:
                        os.chmod(target_abs, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        pass
                os.replace(tmp_path, target_abs)
                return True
            except (PermissionError, OSError) as e:
                if os.path.exists(target_abs):
                    try:
                        os.chmod(target_abs, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        pass
                if attempt == max_retries - 1:
                    logging.getLogger("progress_watchdog").error(
                        f"Failed to atomically replace target file '{target_abs}' after {max_retries} attempts: {e}"
                    )
                    return False
                sleep_time = (retry_delay * (1.15**attempt)) + random.uniform(0.003, 0.02)
                time.sleep(sleep_time)
        return False
    except Exception as e:
        logging.getLogger("progress_watchdog").error(
            f"Unexpected error in safe_atomic_write to '{target_abs}': {e}"
        )
        return False
    finally:
        if os.path.exists(tmp_path):
            try:
                os.chmod(tmp_path, stat.S_IWRITE)
            except OSError:
                pass
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def safe_sync(
    source_path: str,
    target_path: str,
    max_retries: int = 35,
    retry_delay: float = 0.015,
    chunk_size: int = 64 * 1024,
) -> bool:
    """Synchronizes source_path to target_path atomically using chunked streaming.
    Preserves exact bit-for-bit fidelity while maintaining O(1) constant memory usage (<1MB).
    """
    try:
        source_abs = os.path.abspath(source_path)
        target_abs = os.path.abspath(target_path)
        target_dir = os.path.dirname(target_abs)
        if target_dir:
            try:
                os.makedirs(target_dir, exist_ok=True)
            except OSError as e:
                logging.getLogger("progress_watchdog").error(
                    f"Could not create target directory '{target_dir}': {e}"
                )
                return False

        target_name = os.path.basename(target_abs)
        if not target_name:
            logging.getLogger("progress_watchdog").error(
                f"Target path '{target_abs}' has no filename."
            )
            return False

        tmp_name = f".{target_name}.tmp_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}"
        tmp_path = os.path.join(target_dir, tmp_name)
    except Exception as e:
        logging.getLogger("progress_watchdog").error(
            f"Failed to prepare sync paths for '{source_path}' -> '{target_path}': {e}"
        )
        return False

    # Step 1: Open source with jittered retries for transient locks / mid-rename races
    src_file = None
    for attempt in range(max_retries):
        try:
            src_file = open(source_abs, "rb")
            break
        except FileNotFoundError:
            if attempt < 4 and attempt < max_retries - 1:
                time.sleep(0.005 + random.uniform(0.001, 0.005))
                continue
            return False
        except (PermissionError, OSError) as e:
            if attempt == max_retries - 1:
                logging.getLogger("progress_watchdog").warning(
                    f"Failed to open source file '{source_abs}' after {max_retries} attempts: {e}"
                )
                return False
            sleep_time = (retry_delay * (1.15**attempt)) + random.uniform(0.002, 0.015)
            time.sleep(sleep_time)

    if src_file is None:
        return False

    # Step 2: Stream source to temporary file in target directory with retried open
    tmp_written = False
    try:
        with src_file:
            dst_file = None
            for attempt in range(max_retries):
                try:
                    dst_file = open(tmp_path, "wb")
                    break
                except (PermissionError, OSError) as e:
                    if attempt == max_retries - 1:
                        logging.getLogger("progress_watchdog").error(
                            f"Failed to open temporary destination '{tmp_path}': {e}"
                        )
                        return False
                    sleep_time = (retry_delay * (1.15**attempt)) + random.uniform(0.003, 0.02)
                    time.sleep(sleep_time)

            if dst_file is None:
                return False

            with dst_file:
                while True:
                    chunk = src_file.read(chunk_size)
                    if not chunk:
                        break
                    dst_file.write(chunk)
                dst_file.flush()
                try:
                    os.fsync(dst_file.fileno())
                except OSError:
                    pass
            tmp_written = True

        if not tmp_written:
            return False

        # Step 3: Perform atomic replacement with retry backoff and Windows read-only handling
        for attempt in range(max_retries):
            try:
                if os.path.exists(target_abs):
                    try:
                        os.chmod(target_abs, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        pass
                os.replace(tmp_path, target_abs)
                return True
            except (PermissionError, OSError) as e:
                if os.path.exists(target_abs):
                    try:
                        os.chmod(target_abs, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        pass
                if attempt == max_retries - 1:
                    logging.getLogger("progress_watchdog").error(
                        f"Failed to atomically replace target file '{target_abs}' after {max_retries} attempts: {e}"
                    )
                    return False
                sleep_time = (retry_delay * (1.15**attempt)) + random.uniform(0.003, 0.02)
                time.sleep(sleep_time)
        return False
    except Exception as e:
        logging.getLogger("progress_watchdog").error(
            f"Unexpected error in safe_sync '{source_abs}' -> '{target_abs}': {e}"
        )
        return False
    finally:
        if os.path.exists(tmp_path):
            try:
                os.chmod(tmp_path, stat.S_IWRITE)
            except OSError:
                pass
            try:
                os.remove(tmp_path)
            except OSError:
                pass


class ProgressWatchdogHandler(FileSystemEventHandler):
    """Event handler that debounces file modification events and mirrors source to target
    using a dedicated background worker thread to prevent thread churn.
    """

    def __init__(
        self,
        source_path: str,
        target_path: str,
        debounce_interval: float = 1.0,
        max_wait: Optional[float] = None,
        callback: Optional[Callable[[bool, int], None]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__()
        validate_paths(source_path, target_path)

        self.source_path = os.path.realpath(os.path.abspath(source_path))
        self.target_path = os.path.realpath(os.path.abspath(target_path))
        self.normalized_source = os.path.normcase(self.source_path)
        self.normalized_source_abs = os.path.normcase(os.path.abspath(source_path))

        debounce_val = float(debounce_interval)
        if debounce_val <= 0:
            raise ValueError(f"debounce_interval must be positive, got {debounce_val}")
        self.debounce_interval = debounce_val

        self.max_wait = (
            float(max_wait) if max_wait is not None and max_wait > 0 else None
        )
        self.callback = callback
        self.logger = logger or logging.getLogger("progress_watchdog")

        self._lock = threading.RLock()
        self._sync_lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

        self._deadline: Optional[float] = None
        self._first_event_time: Optional[float] = None
        self._pending_sync: bool = False
        self._stopped: bool = False

        self.sync_count: int = 0
        self.event_count: int = 0
        self.error_count: int = 0
        self.last_sync_time: Optional[float] = None

        # Start single persistent debounce worker thread
        self._worker_thread = threading.Thread(
            target=self._debounce_worker,
            daemon=True,
            name="WatchdogDebounceWorker",
        )
        self._worker_thread.start()

    def _matches_source(self, event_path: str) -> bool:
        if not event_path:
            return False
        abs_p = os.path.abspath(event_path)
        norm_abs = os.path.normcase(abs_p)
        if norm_abs == self.normalized_source or norm_abs == self.normalized_source_abs:
            return True
        norm_real = os.path.normcase(os.path.realpath(abs_p))
        return norm_real == self.normalized_source or norm_real == self.normalized_source_abs

    def _is_relevant_event(self, event: FileSystemEvent) -> bool:
        if event.is_directory:
            return False
        if self._matches_source(event.src_path):
            return True
        if hasattr(event, "dest_path") and event.dest_path:
            if self._matches_source(event.dest_path):
                return True
        return False

    def on_modified(self, event: FileSystemEvent) -> None:
        if self._is_relevant_event(event):
            self.logger.debug(f"on_modified detected on {event.src_path}")
            self.trigger()

    def on_created(self, event: FileSystemEvent) -> None:
        if self._is_relevant_event(event):
            self.logger.debug(f"on_created detected on {event.src_path}")
            self.trigger()

    def on_moved(self, event: FileSystemEvent) -> None:
        if self._is_relevant_event(event):
            self.logger.debug(
                f"on_moved detected on {event.src_path} -> {getattr(event, 'dest_path', '')}"
            )
            self.trigger()

    def trigger(self) -> None:
        """Trigger debounced sync scheduling."""
        now = time.time()
        with self._cond:
            self.event_count += 1
            self._pending_sync = True

            if self._first_event_time is None:
                self._first_event_time = now

            # Check if max_wait exceeded to prevent starvation during continuous write streams
            if self.max_wait and (now - self._first_event_time >= self.max_wait):
                self._deadline = now
            else:
                self._deadline = now + self.debounce_interval

            self._cond.notify_all()

    def _debounce_worker(self) -> None:
        """Dedicated background loop that sleeps until deadline and executes sync."""
        while True:
            should_sync = False
            with self._cond:
                while not self._stopped and not self._pending_sync:
                    self._cond.wait()

                if self._stopped:
                    # Final flush on shutdown if pending, executed outside condition lock
                    if self._pending_sync:
                        self._pending_sync = False
                        self._first_event_time = None
                        self._deadline = None
                        should_sync = True
                    break

                now = time.time()
                if self._deadline is not None and now < self._deadline:
                    timeout = self._deadline - now
                    self._cond.wait(timeout=timeout)
                    continue

                self._pending_sync = False
                self._first_event_time = None
                self._deadline = None
                should_sync = True

            # Execute sync outside condition lock to prevent holding lock during I/O
            if should_sync:
                self._do_sync()

        # If shutdown required final flush, execute outside the condition lock
        if should_sync:
            self._do_sync()

    def _do_sync(self) -> bool:
        """Performs synchronized I/O and updates counters."""
        with self._sync_lock:
            self.logger.info(
                f"Debounce resolved: syncing '{self.source_path}' -> '{self.target_path}'"
            )
            success = safe_sync(self.source_path, self.target_path)
            with self._lock:
                if success:
                    self.sync_count += 1
                    self.last_sync_time = time.time()
                    self.logger.info(
                        f"Sync successful (total sync count: {self.sync_count})"
                    )
                else:
                    self.error_count += 1
                    self.logger.warning(
                        f"Sync failed (total error count: {self.error_count})"
                    )

            if self.callback:
                try:
                    self.callback(success, self.sync_count)
                except Exception as e:
                    self.logger.warning(f"Error in watchdog callback: {e}")

            return success

    def _execute_sync_locked(self) -> bool:
        """Internal helper for immediate execution."""
        return self._do_sync()

    def flush(self) -> bool:
        """Immediately flushes any pending debounced sync synchronously."""
        with self._cond:
            if not self._pending_sync:
                return True
            self._pending_sync = False
            self._first_event_time = None
            self._deadline = None
        return self._do_sync()

    def sync_immediate(self) -> bool:
        """Forces an immediate sync regardless of pending state."""
        with self._cond:
            self._pending_sync = False
            self._first_event_time = None
            self._deadline = None
        return self._do_sync()

    def stop(self) -> None:
        """Stops the debounce worker loop cleanly."""
        with self._cond:
            self._stopped = True
            self._cond.notify_all()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)


import atexit


class ProgressWatchdogDaemon:
    """Daemon manager that configures and runs watchdog observer and debounced sync."""

    def __init__(
        self,
        source_path: str,
        target_path: str,
        debounce_interval: float = 1.0,
        initial_sync: bool = True,
        max_wait: Optional[float] = None,
        use_polling: bool = False,
        pid_file: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        callback: Optional[Callable[[bool, int], None]] = None,
    ):
        validate_paths(source_path, target_path)

        self.source_path = os.path.realpath(os.path.abspath(source_path))
        self.target_path = os.path.realpath(os.path.abspath(target_path))
        self.debounce_interval = float(debounce_interval)
        if self.debounce_interval <= 0:
            raise ValueError(f"debounce_interval must be positive, got {self.debounce_interval}")

        self.initial_sync = initial_sync
        self.max_wait = max_wait
        self.use_polling = use_polling
        self.pid_file = os.path.abspath(pid_file) if pid_file else None
        self.logger = logger or logging.getLogger("progress_watchdog")

        self.handler = ProgressWatchdogHandler(
            source_path=self.source_path,
            target_path=self.target_path,
            debounce_interval=self.debounce_interval,
            max_wait=self.max_wait,
            callback=callback,
            logger=self.logger,
        )
        self.observer: Optional[Observer] = None
        self._running = threading.Event()
        self._atexit_registered = False

    @property
    def metrics(self) -> Dict[str, Any]:
        """Returns current operational metrics."""
        with self.handler._lock:
            return {
                "sync_count": self.handler.sync_count,
                "event_count": self.handler.event_count,
                "error_count": self.handler.error_count,
                "last_sync_time": self.handler.last_sync_time,
                "is_running": self._running.is_set(),
                "pending_sync": self.handler._pending_sync,
            }

    def start(self) -> None:
        """Starts the observer and optionally performs initial sync."""
        if self._running.is_set():
            return

        if self.pid_file:
            try:
                if os.path.exists(self.pid_file):
                    try:
                        with open(self.pid_file, "r", encoding="utf-8") as pf:
                            old_pid = int(pf.read().strip())
                        if is_pid_alive(old_pid):
                            self.logger.warning(
                                f"PID file '{self.pid_file}' exists and process {old_pid} is active."
                            )
                        else:
                            self.logger.info(
                                f"Removing stale PID file '{self.pid_file}' from dead process {old_pid}."
                            )
                            os.remove(self.pid_file)
                    except (ValueError, OSError):
                        pass

                os.makedirs(os.path.dirname(self.pid_file), exist_ok=True)
                with open(self.pid_file, "w", encoding="utf-8") as f:
                    f.write(str(os.getpid()))
            except Exception as e:
                self.logger.warning(
                    f"Could not write PID file '{self.pid_file}': {e}"
                )

        if not self._atexit_registered:
            atexit.register(self.stop)
            self._atexit_registered = True

        source_dir = os.path.dirname(self.source_path) or "."
        try:
            os.makedirs(source_dir, exist_ok=True)
        except OSError as e:
            self.logger.warning(f"Could not create source directory '{source_dir}': {e}")

        if self.initial_sync and os.path.exists(self.source_path):
            self.logger.info(
                f"Performing initial sync: '{self.source_path}' -> '{self.target_path}'"
            )
            self.handler.sync_immediate()

        if self.use_polling:
            self.observer = PollingObserver()
            self.observer.schedule(self.handler, source_dir, recursive=False)
            self.observer.start()
            self._running.set()
            self.logger.info(
                f"ProgressWatchdog started with PollingObserver: monitoring '{self.source_path}' -> '{self.target_path}' (debounce={self.debounce_interval}s)"
            )
            return

        # Attempt native Observer with automatic fallback to PollingObserver
        try:
            self.observer = Observer()
            self.observer.schedule(self.handler, source_dir, recursive=False)
            self.observer.start()
            self._running.set()
            self.logger.info(
                f"ProgressWatchdog started with native Observer: monitoring '{self.source_path}' -> '{self.target_path}' (debounce={self.debounce_interval}s)"
            )
        except (OSError, RuntimeError, Exception) as e:
            self.logger.warning(
                f"Native Observer failed to start ({e}). Falling back to PollingObserver."
            )
            self.observer = PollingObserver()
            self.observer.schedule(self.handler, source_dir, recursive=False)
            self.observer.start()
            self._running.set()
            self.logger.info(
                f"ProgressWatchdog started with PollingObserver fallback: monitoring '{self.source_path}' -> '{self.target_path}' (debounce={self.debounce_interval}s)"
            )

    def stop(self) -> None:
        """Stops the observer and flushes any pending sync."""
        if not self._running.is_set():
            return
        self.logger.info("Stopping ProgressWatchdog...")
        self._running.clear()
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=5.0)
            except Exception as e:
                self.logger.warning(f"Error stopping observer: {e}")

        # Stop handler worker and flush any pending sync
        self.handler.flush()
        self.handler.stop()

        if self.pid_file and os.path.exists(self.pid_file):
            try:
                os.remove(self.pid_file)
            except OSError:
                pass

        try:
            atexit.unregister(self.stop)
        except Exception:
            pass

        self.logger.info("ProgressWatchdog stopped cleanly.")

    def join(self) -> None:
        """Blocks until the observer stops."""
        if self.observer:
            self.observer.join()

    def sync_now(self) -> bool:
        """Forces an immediate synchronization."""
        return self.handler.sync_immediate()

    def run_forever(self) -> None:
        """Starts the daemon, registers OS signal handlers, and keeps the process resident."""
        self.start()

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}. Initiating shutdown...")
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            if hasattr(signal, "SIGBREAK"):
                signal.signal(signal.SIGBREAK, signal_handler)
        except (ValueError, AttributeError):
            # Not in main thread or signal unsupported
            pass

        try:
            while self._running.is_set():
                time.sleep(0.5)
        except (KeyboardInterrupt, SystemExit):
            self.stop()


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Real-time debounced file synchronization daemon for Antigravity state mirror."
    )
    parser.add_argument(
        "--source",
        "-s",
        required=True,
        help="Path to source state file (e.g. progress.md).",
    )
    parser.add_argument(
        "--target",
        "-t",
        required=True,
        help="Path to target Artifact file (e.g. task.md).",
    )
    parser.add_argument(
        "--debounce",
        "-d",
        type=float,
        default=1.0,
        help="Debounce duration in seconds (default: 1.0).",
    )
    parser.add_argument(
        "--no-initial-sync",
        action="store_true",
        default=False,
        help="Disable automatic initial synchronization at startup.",
    )
    parser.add_argument(
        "--max-wait",
        "-m",
        type=float,
        default=None,
        help="Maximum wait time in seconds before forcing a sync during continuous write streams.",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        default=False,
        help="Use polling-based observer instead of native OS filesystem events.",
    )
    parser.add_argument(
        "--pid-file",
        type=str,
        default=None,
        help="Path to write PID file for process management.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO).",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        default=False,
        help="Perform a single synchronization pass and exit immediately.",
    )

    args = parser.parse_args(argv)
    if args.debounce <= 0:
        parser.error(f"--debounce must be a positive number, got {args.debounce}")
    if args.max_wait is not None and args.max_wait <= 0:
        parser.error(f"--max-wait must be a positive number, got {args.max_wait}")
    return args


def main():
    args = parse_args()
    logger = setup_logger(log_level=args.log_level, log_file=args.log_file)

    try:
        validate_paths(args.source, args.target)
    except ValueError as e:
        logger.error(f"Path validation error: {e}")
        sys.exit(2)

    if args.run_once:
        logger.info(
            f"Running one-shot sync: '{args.source}' -> '{args.target}'"
        )
        success = safe_sync(args.source, args.target)
        if success:
            logger.info("One-shot sync succeeded.")
            sys.exit(0)
        else:
            logger.error("One-shot sync failed.")
            sys.exit(1)

    daemon = ProgressWatchdogDaemon(
        source_path=args.source,
        target_path=args.target,
        debounce_interval=args.debounce,
        initial_sync=not args.no_initial_sync,
        max_wait=args.max_wait,
        use_polling=args.poll,
        pid_file=args.pid_file,
        logger=logger,
    )

    daemon.run_forever()


if __name__ == "__main__":
    main()
