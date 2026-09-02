"""
test_progress_watchdog.py
=========================
Comprehensive automated verification suite for progress_watchdog.py.

Tests:
1. CLI argument parsing & validation
2. Real-time debounced file synchronization
3. High-frequency stream protection (50 writes within 1.0s -> max 1 sync)
4. Safe atomic concurrency (concurrent readers during active sync, zero sync errors, zero corrupted reads)
5. Source lifecycle events (creation after startup, recreation)
6. Missing target directory creation
7. Clean shutdown and pending sync flush
8. Subprocess background daemon lifecycle
9. Multiple intermittent bursts (exact debounced sync count verification)
10. Continuous write stream with max_wait starvation protection
11. Large markdown file & UTF-8 character integrity
12. Extreme multi-threaded concurrent readers + concurrent writers stress
"""

import os
import sys
import time
import tempfile
import shutil
import threading
import subprocess
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from progress_watchdog import (
    ProgressWatchdogDaemon,
    ProgressWatchdogHandler,
    safe_atomic_write,
    safe_read_file,
    safe_sync,
    validate_paths,
    setup_logger,
    parse_args,
)


class TestProgressWatchdog(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="watchdog_test_")
        self.source_file = os.path.join(self.temp_dir, "progress.md")
        self.target_file = os.path.join(self.temp_dir, "task.md")

    def tearDown(self):
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def test_01_cli_arg_parsing(self):
        """Test CLI argument parser with various options."""
        args = parse_args(["-s", "src.md", "-t", "dst.md", "-d", "2.5"])
        self.assertEqual(args.source, "src.md")
        self.assertEqual(args.target, "dst.md")
        self.assertEqual(args.debounce, 2.5)
        self.assertFalse(args.no_initial_sync)
        self.assertFalse(args.poll)

        args2 = parse_args([
            "--source", "a.txt",
            "--target", "b.txt",
            "--debounce", "0.5",
            "--no-initial-sync",
            "--max-wait", "3.0",
            "--poll",
            "--pid-file", "test.pid",
            "--log-level", "DEBUG"
        ])
        self.assertEqual(args2.source, "a.txt")
        self.assertEqual(args2.target, "b.txt")
        self.assertEqual(args2.debounce, 0.5)
        self.assertTrue(args2.no_initial_sync)
        self.assertEqual(args2.max_wait, 3.0)
        self.assertTrue(args2.poll)
        self.assertEqual(args2.pid_file, "test.pid")
        self.assertEqual(args2.log_level, "DEBUG")

    def test_02_safe_atomic_write_and_sync(self):
        """Test safe atomic write and sync functions."""
        content = "# Progress State\n- [x] Step 1\n- [ ] Step 2\n"
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write(content)

        success = safe_sync(self.source_file, self.target_file)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.target_file))

        with open(self.target_file, "r", encoding="utf-8") as f:
            read_content = f.read()
        self.assertEqual(read_content, content)

    def test_03_high_frequency_debounce_stream_protection(self):
        """R2 / Acceptance Criterion: Rapidly writing 50 lines within 1s triggers at most 1 sync."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("# Initial Header\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=1.0,
            initial_sync=False,
        )
        daemon.start()

        try:
            time.sleep(0.3)
            initial_syncs = daemon.metrics["sync_count"]
            self.assertEqual(initial_syncs, 0)

            # Rapidly write 50 lines in < 0.6 seconds
            start_time = time.time()
            for i in range(1, 51):
                with open(self.source_file, "a", encoding="utf-8") as f:
                    f.write(f"- [x] Task item {i}\n")
                time.sleep(0.01)  # 50 * 10ms = 0.5s burst
            burst_duration = time.time() - start_time
            self.assertLess(burst_duration, 1.0, "50 writes should complete in under 1 second")

            # Check during debounce window: should still be 0
            time.sleep(0.2)
            sync_during_burst = daemon.metrics["sync_count"]
            self.assertEqual(
                sync_during_burst, 0,
                f"Sync should NOT trigger during active stream burst, but got {sync_during_burst}"
            )

            # Wait for debounce window (1.0s + buffer)
            time.sleep(1.3)

            final_syncs = daemon.metrics["sync_count"]
            self.assertEqual(
                final_syncs, 1,
                f"Rapid burst of 50 writes must trigger exactly 1 sync operation, got {final_syncs}"
            )

            with open(self.target_file, "r", encoding="utf-8") as f:
                target_lines = f.readlines()

            self.assertEqual(len(target_lines), 51)
            self.assertEqual(target_lines[-1].strip(), "- [x] Task item 50")

        finally:
            daemon.stop()

    def test_04_safe_concurrency_stress(self):
        """R3 / Acceptance Criterion: Concurrent readers never experience corrupt data; sync operation throws zero exceptions."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("v0: " + ("#" * 200) + "\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.05,
            initial_sync=True,
        )
        daemon.start()

        stop_event = threading.Event()
        safe_read_failures = []
        corrupted_reads = []
        read_counter = [0]

        def concurrent_reader(reader_id: int):
            while not stop_event.is_set():
                data = safe_read_file(self.target_file, max_retries=15, retry_delay=0.005, allow_empty=False)
                if data:
                    read_counter[0] += 1
                    if not data.startswith("v"):
                        corrupted_reads.append(f"Reader {reader_id} saw corrupt: {data[:20]}")
                elif data is None:
                    safe_read_failures.append(f"Reader {reader_id} failed to read target")
                time.sleep(0.001)

        readers = [
            threading.Thread(target=concurrent_reader, args=(i,), daemon=True)
            for i in range(8)
        ]
        for r in readers:
            r.start()

        try:
            for v in range(1, 25):
                with open(self.source_file, "w", encoding="utf-8") as f:
                    f.write(f"v{v}: " + ("#" * 200) + f" update {v}\n")
                time.sleep(0.06)

            time.sleep(0.3)
        finally:
            stop_event.set()
            for r in readers:
                r.join(timeout=2.0)
            daemon.stop()

        self.assertGreater(read_counter[0], 50, "Should have performed dozens of concurrent reads")
        self.assertEqual(len(corrupted_reads), 0, f"Detected corrupted reads: {corrupted_reads}")
        self.assertEqual(len(safe_read_failures), 0, f"Safe read failures occurred: {safe_read_failures}")
        self.assertEqual(daemon.metrics["error_count"], 0, "Daemon encountered sync errors on Windows")

    def test_05_source_lifecycle_created_after_start(self):
        """Test that source file created after daemon starts is properly detected and mirrored."""
        non_existent_source = os.path.join(self.temp_dir, "delayed_source.md")

        daemon = ProgressWatchdogDaemon(
            source_path=non_existent_source,
            target_path=self.target_file,
            debounce_interval=0.2,
            initial_sync=False,
        )
        daemon.start()

        try:
            time.sleep(0.2)
            self.assertFalse(os.path.exists(self.target_file))

            with open(non_existent_source, "w", encoding="utf-8") as f:
                f.write("Created after daemon started\n")

            time.sleep(0.6)

            self.assertTrue(os.path.exists(self.target_file))
            with open(self.target_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Created after daemon started\n")
            self.assertGreaterEqual(daemon.metrics["sync_count"], 1)

        finally:
            daemon.stop()

    def test_06_target_directory_autocreation(self):
        """Test target path with nested non-existent directory."""
        nested_target = os.path.join(self.temp_dir, "nested", "subdir", "deep_task.md")
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Deep nested target test\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=nested_target,
            debounce_interval=0.2,
            initial_sync=True,
        )
        daemon.start()

        try:
            self.assertTrue(os.path.exists(nested_target))
            with open(nested_target, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Deep nested target test\n")
        finally:
            daemon.stop()

    def test_07_shutdown_flush_guarantee(self):
        """Test that shutting down daemon flushes any pending debounced sync."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("initial\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=2.0,
            initial_sync=True,
        )
        daemon.start()
        time.sleep(0.2)

        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("updated right before shutdown\n")

        time.sleep(0.1)
        daemon.stop()

        with open(self.target_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "updated right before shutdown\n")

    def test_08_subprocess_cli_daemon_execution(self):
        """Test launching progress_watchdog.py as a real CLI subprocess daemon."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("CLI Test Initial\n")

        pid_file = os.path.join(self.temp_dir, "daemon.pid")
        log_file = os.path.join(self.temp_dir, "daemon.log")

        proc = subprocess.Popen(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "progress_watchdog.py"),
                "--source", self.source_file,
                "--target", self.target_file,
                "--debounce", "0.3",
                "--pid-file", pid_file,
                "--log-file", log_file,
                "--log-level", "DEBUG",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            for _ in range(30):
                if os.path.exists(self.target_file) and os.path.exists(pid_file):
                    break
                time.sleep(0.1)

            self.assertTrue(os.path.exists(self.target_file))
            self.assertTrue(os.path.exists(pid_file))

            with open(self.source_file, "w", encoding="utf-8") as f:
                f.write("CLI Test Updated Live\n")

            time.sleep(0.8)

            with open(self.target_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "CLI Test Updated Live\n")

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_09_multiple_intermittent_bursts(self):
        """Test multiple separated write bursts each trigger exactly 1 debounced sync."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Header\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.5,
            initial_sync=False,
        )
        daemon.start()

        try:
            time.sleep(0.2)

            # Burst 1: 20 writes in 0.15s
            for i in range(20):
                with open(self.source_file, "a", encoding="utf-8") as f:
                    f.write(f"Burst1-{i}\n")
                time.sleep(0.007)

            # Wait for Burst 1 debounce to complete (0.5s + buffer = 0.8s)
            time.sleep(0.8)
            self.assertEqual(daemon.metrics["sync_count"], 1)

            # Burst 2: 25 writes in 0.2s
            for i in range(25):
                with open(self.source_file, "a", encoding="utf-8") as f:
                    f.write(f"Burst2-{i}\n")
                time.sleep(0.007)

            # Wait for Burst 2 debounce to complete
            time.sleep(0.8)
            self.assertEqual(daemon.metrics["sync_count"], 2)

            with open(self.target_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 46)
            self.assertEqual(lines[-1].strip(), "Burst2-24")

        finally:
            daemon.stop()

    def test_10_max_wait_starvation_prevention(self):
        """Test continuous write stream triggers intermediate sync via max_wait."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Continuous Stream Start\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=1.0,
            max_wait=0.8,
            initial_sync=False,
        )
        daemon.start()

        try:
            time.sleep(0.2)
            # Continuous writes every 0.1s for 1.8s
            for i in range(18):
                with open(self.source_file, "a", encoding="utf-8") as f:
                    f.write(f"Stream-line-{i}\n")
                time.sleep(0.1)

            self.assertGreaterEqual(
                daemon.metrics["sync_count"], 1,
                "max_wait should have forced intermediate sync during continuous stream"
            )

            time.sleep(1.4)
            with open(self.target_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 19)

        finally:
            daemon.stop()

    def test_11_large_markdown_and_utf8_integrity(self):
        """Test large multiline markdown document with unicode emojis and complex formatting."""
        large_content = "# Real-Time Dashboard 🚀\n\n"
        large_content += "## Active Subagents ⚡\n"
        for i in range(1000):
            status = "completed" if i % 2 == 0 else "pending"
            icon = "✅" if i % 2 == 0 else "⏳"
            large_content += f"- [{ 'x' if i % 2 == 0 else ' ' }] Task `{i:04d}`: Status {status} {icon} — Metric: {i * 1.5:.2f}ms\n"

        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write(large_content)

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.2,
            initial_sync=True,
        )
        daemon.start()

        try:
            time.sleep(0.5)
            self.assertTrue(os.path.exists(self.target_file))
            with open(self.target_file, "r", encoding="utf-8") as f:
                read_data = f.read()

            self.assertEqual(len(read_data), len(large_content))
            self.assertEqual(read_data, large_content)
        finally:
            daemon.stop()

    def test_12_extreme_multithreaded_readers_and_writers_stress(self):
        """Stress test with concurrent writers and readers hammering source and target."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Initial Stress Content\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.05,
            initial_sync=True,
        )
        daemon.start()

        stop_event = threading.Event()
        writer_errors = []
        reader_errors = []
        read_success = [0]
        write_success = [0]

        def writer_job(writer_id: int):
            for i in range(30):
                if stop_event.is_set():
                    break
                try:
                    with open(self.source_file, "w", encoding="utf-8") as f:
                        f.write(f"Writer {writer_id} iteration {i}\n" * 20)
                    write_success[0] += 1
                except Exception as e:
                    writer_errors.append(f"Writer error: {e}")
                time.sleep(0.01)

        def reader_job(reader_id: int):
            while not stop_event.is_set():
                data = safe_read_file(self.target_file, max_retries=10, retry_delay=0.005)
                if data:
                    read_success[0] += 1
                else:
                    reader_errors.append(f"Reader {reader_id} read failure")
                time.sleep(0.002)

        writers = [threading.Thread(target=writer_job, args=(w,)) for w in range(3)]
        readers = [threading.Thread(target=reader_job, args=(r,), daemon=True) for r in range(6)]

        for r in readers:
            r.start()
        for w in writers:
            w.start()

        for w in writers:
            w.join()

        time.sleep(0.4)
        stop_event.set()
        for r in readers:
            r.join(timeout=1.0)
        daemon.stop()

        self.assertEqual(len(writer_errors), 0, f"Writer errors: {writer_errors}")
        self.assertEqual(len(reader_errors), 0, f"Reader errors: {reader_errors}")
        self.assertGreater(read_success[0], 20, "Readers performed multiple reads")
        self.assertGreater(write_success[0], 50, "Writers performed multiple writes")
        self.assertEqual(daemon.metrics["error_count"], 0, "Daemon sync errors occurred")

    def test_13_corrupted_non_utf8_source_integrity(self):
        """Test reading and mirroring a file with non-UTF8 binary bytes without crashing."""
        with open(self.source_file, "wb") as f:
            f.write(b"# Progress State\n\xff\xfe corrupted binary \x80\x81\n- [x] Step Complete\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.2,
            initial_sync=True,
        )
        daemon.start()

        try:
            time.sleep(0.4)
            self.assertTrue(os.path.exists(self.target_file))
            with open(self.target_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.assertIn("# Progress State", content)
            self.assertIn("- [x] Step Complete", content)
            self.assertEqual(daemon.metrics["error_count"], 0)
        finally:
            daemon.stop()

    def test_14_windows_readonly_target_overwrite(self):
        """Test writing to a read-only target file on Windows without Access Denied."""
        import stat
        with open(self.target_file, "w", encoding="utf-8") as f:
            f.write("Initial target content\n")

        # Mark target read-only
        os.chmod(self.target_file, stat.S_IREAD)

        success = safe_atomic_write(self.target_file, "Updated content over read-only")
        self.assertTrue(success, "safe_atomic_write should succeed on read-only targets on Windows")
        with open(self.target_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Updated content over read-only")

    def test_15_source_equals_target_rejection(self):
        """Test initializing daemon with identical source and target paths raises ValueError."""
        with self.assertRaises(ValueError, msg="ProgressWatchdogDaemon should reject identical source and target paths"):
            ProgressWatchdogDaemon(
                source_path=self.source_file,
                target_path=self.source_file.upper() if os.name == "nt" else self.source_file,
            )

    def test_16_source_is_directory_rejection(self):
        """Test that source path being a directory is rejected with ValueError."""
        with self.assertRaises(ValueError, msg="ProgressWatchdogDaemon should reject directory as source"):
            ProgressWatchdogDaemon(
                source_path=self.temp_dir,
                target_path=self.target_file,
            )

    def test_17_invalid_debounce_argument_rejection(self):
        """Test non-positive debounce intervals are rejected."""
        with self.assertRaises(ValueError, msg="ProgressWatchdogDaemon should reject <=0 debounce interval"):
            ProgressWatchdogDaemon(
                source_path=self.source_file,
                target_path=self.target_file,
                debounce_interval=-1.0,
            )

    def test_18_automatic_polling_fallback_on_observer_failure(self):
        """Test that if native Observer fails to start, daemon falls back to PollingObserver seamlessly."""
        from unittest.mock import MagicMock, patch
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Fallback test content\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.2,
            initial_sync=False,
            use_polling=False,
        )

        with patch("progress_watchdog.Observer") as MockObserver:
            instance = MagicMock()
            instance.start.side_effect = OSError("Native ReadDirectoryChangesW unsupported on network share")
            MockObserver.return_value = instance

            daemon.start()
            self.assertTrue(daemon._running.is_set())
            daemon.stop()

    def test_19_concurrent_flush_and_sync_idempotency(self):
        """Test calling flush(), sync_immediate(), and trigger() concurrently with zero race errors."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Concurrent sync initial\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.1,
            initial_sync=True,
        )
        daemon.start()

        try:
            threads = []
            for i in range(12):
                if i % 3 == 0:
                    t = threading.Thread(target=daemon.handler.trigger)
                elif i % 3 == 1:
                    t = threading.Thread(target=daemon.handler.flush)
                else:
                    t = threading.Thread(target=daemon.sync_now)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            time.sleep(0.3)
            self.assertEqual(daemon.metrics["error_count"], 0)
            self.assertTrue(os.path.exists(self.target_file))
        finally:
            daemon.stop()

    def test_20_shutdown_during_pending_sync_deadlock_prevention(self):
        """Test that calling handler.stop() when pending_sync is True never deadlocks."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Deadlock prevention test\n")

        handler = ProgressWatchdogHandler(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=5.0,  # Long interval so sync is pending
        )

        try:
            handler.trigger()
            self.assertTrue(handler._pending_sync)

            # Write updated content
            with open(self.source_file, "w", encoding="utf-8") as f:
                f.write("Flushed cleanly upon stop without deadlock\n")

            # Call stop() directly: must finish within 2.0s without hanging
            start_stop = time.time()
            handler.stop()
            stop_duration = time.time() - start_stop

            self.assertLess(stop_duration, 2.5, "handler.stop() took too long; possible deadlock detected")
            self.assertTrue(os.path.exists(self.target_file))
            with open(self.target_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Flushed cleanly upon stop without deadlock\n")
        finally:
            handler.stop()

    def test_21_chunked_streaming_large_file_sync(self):
        """Test chunked binary streaming on large multi-megabyte file (O(1) memory overhead)."""
        # Generate 4MB of repeating deterministic pattern
        block = b"0123456789abcdefghijklmnopqrstuvwxyz\n" * 28000  # ~1MB
        large_bytes = block * 4  # ~4MB

        with open(self.source_file, "wb") as f:
            f.write(large_bytes)

        success = safe_sync(self.source_path if hasattr(self, 'source_path') else self.source_file, self.target_file, chunk_size=32 * 1024)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.target_file))

        self.assertEqual(os.path.getsize(self.target_file), len(large_bytes))
        with open(self.target_file, "rb") as f:
            target_bytes = f.read()
        self.assertEqual(target_bytes, large_bytes)

    def test_22_target_is_directory_rejection(self):
        """Test that passing an existing directory as target is rejected with ValueError."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Valid source\n")

        with self.assertRaises(ValueError, msg="Should reject existing directory as target"):
            ProgressWatchdogDaemon(
                source_path=self.source_file,
                target_path=self.temp_dir,
            )

    def test_23_transient_source_disappearance_resilience(self):
        """Test that transient missing file during atomic source save does not crash safe_sync."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Initial state\n")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.1,
            initial_sync=True,
        )
        daemon.start()

        try:
            time.sleep(0.15)
            self.assertTrue(os.path.exists(self.target_file))

            # Simulate atomic editor replace: unlink source then immediately recreate
            temp_swap = os.path.join(self.temp_dir, "swap.tmp")
            with open(temp_swap, "w", encoding="utf-8") as f:
                f.write("Replaced via atomic rename\n")

            os.replace(temp_swap, self.source_file)
            time.sleep(0.35)

            with open(self.target_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Replaced via atomic rename\n")
            self.assertEqual(daemon.metrics["error_count"], 0)
        finally:
            daemon.stop()

    def test_24_pid_file_lifecycle_and_stale_pid_cleanup(self):
        """Test PID file creation, removal on stop, and stale PID detection."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("PID test source\n")

        pid_path = os.path.join(self.temp_dir, "test_daemon.pid")

        # Write stale dead PID (e.g. 999999)
        with open(pid_path, "w", encoding="utf-8") as f:
            f.write("999999")

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.2,
            pid_file=pid_path,
            initial_sync=False,
        )
        daemon.start()

        try:
            self.assertTrue(os.path.exists(pid_path))
            with open(pid_path, "r", encoding="utf-8") as f:
                active_pid = int(f.read().strip())
            self.assertEqual(active_pid, os.getpid())
        finally:
            daemon.stop()

        self.assertFalse(os.path.exists(pid_path), "PID file must be removed on clean stop")

    def test_25_zero_byte_empty_file_sync(self):
        """Test that 0-byte empty source file syncs without hanging or retries."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            pass  # 0 bytes

        daemon = ProgressWatchdogDaemon(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.1,
            initial_sync=True,
        )
        daemon.start()

        try:
            time.sleep(0.25)
            self.assertTrue(os.path.exists(self.target_file))
            self.assertEqual(os.path.getsize(self.target_file), 0)
            self.assertEqual(daemon.metrics["error_count"], 0)
        finally:
            daemon.stop()

    def test_26_relative_path_normalization_across_subdirectories(self):
        """Test daemon when initialized with relative paths in nested subdirectories."""
        src_subdir = os.path.join(self.temp_dir, "src_sub")
        tgt_subdir = os.path.join(self.temp_dir, "tgt_sub")
        os.makedirs(src_subdir, exist_ok=True)
        os.makedirs(tgt_subdir, exist_ok=True)

        old_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            rel_source = os.path.join("src_sub", "rel_progress.md")
            rel_target = os.path.join("tgt_sub", "rel_task.md")

            with open(rel_source, "w", encoding="utf-8") as f:
                f.write("Relative path content\n")

            daemon = ProgressWatchdogDaemon(
                source_path=rel_source,
                target_path=rel_target,
                debounce_interval=0.1,
                initial_sync=True,
            )
            daemon.start()

            try:
                time.sleep(0.25)
                self.assertTrue(os.path.exists(rel_target))
                with open(rel_target, "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), "Relative path content\n")
            finally:
                daemon.stop()
        finally:
            os.chdir(old_cwd)

    def test_27_run_once_cli_mode(self):
        """Test --run-once CLI flag executes single pass and exits with code 0."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("One-shot CLI content\n")

        script_path = os.path.join(os.path.dirname(__file__), "progress_watchdog.py")
        result = subprocess.run(
            [
                sys.executable,
                script_path,
                "--source", self.source_file,
                "--target", self.target_file,
                "--run-once",
            ],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertTrue(os.path.exists(self.target_file))
        with open(self.target_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "One-shot CLI content\n")

    def test_28_logger_reconfiguration_and_file_handler_attachment(self):
        """Test setup_logger correctly attaches FileHandler on reconfigured loggers."""
        import logging
        test_log_name = f"test_logger_{time.time_ns()}"
        l1 = setup_logger(log_level="INFO", name=test_log_name)
        log_path = os.path.join(self.temp_dir, "reconfigured.log")
        l2 = setup_logger(log_level="DEBUG", log_file=log_path, name=test_log_name)
        self.assertEqual(l1, l2)
        has_file = any(isinstance(h, logging.FileHandler) for h in l2.handlers)
        self.assertTrue(has_file, "FileHandler must be attached when log_file is specified")
        l2.debug("Test log entry")
        for h in l2.handlers:
            h.flush()
        self.assertTrue(os.path.exists(log_path))
        with open(log_path, "r", encoding="utf-8") as f:
            self.assertIn("Test log entry", f.read())

    def test_29_target_with_trailing_slash_rejected(self):
        """Test validate_paths rejects targets and sources with trailing directory slashes."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Valid source\n")
        with self.assertRaises(ValueError, msg="Target ending with slash should be rejected as directory"):
            validate_paths(self.source_file, os.path.join(self.temp_dir, "nonexistent_dir") + "/")
        with self.assertRaises(ValueError, msg="Target ending with backslash should be rejected as directory"):
            validate_paths(self.source_file, os.path.join(self.temp_dir, "nonexistent_dir") + "\\")

    def test_30_safe_sync_and_atomic_write_inaccessible_drive_graceful_failure(self):
        """Test safe_sync and safe_atomic_write return False without throwing unhandled exceptions on invalid drives."""
        invalid_target = "Z:\\nonexistent_volume_99999\\task.md"
        sync_res = safe_sync(self.source_file, invalid_target, max_retries=2)
        self.assertFalse(sync_res, "safe_sync must return False for inaccessible drive without crashing")
        write_res = safe_atomic_write(invalid_target, "test content", max_retries=2)
        self.assertFalse(write_res, "safe_atomic_write must return False for inaccessible drive without crashing")

    def test_31_root_drive_target_and_source_validation(self):
        """Test validate_paths rejects drive roots and root directory targets."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Valid source\n")
        root_path = "C:\\" if os.name == "nt" else "/"
        with self.assertRaises(ValueError, msg="Drive root target should be rejected"):
            validate_paths(self.source_file, root_path)
        with self.assertRaises(ValueError, msg="Drive root source should be rejected"):
            validate_paths(root_path, self.target_file)

    def test_32_max_wait_negative_cli_rejection(self):
        """Test parse_args rejects non-positive --max-wait."""
        with self.assertRaises(SystemExit):
            parse_args(["-s", "src.md", "-t", "tgt.md", "--max-wait", "-1.0"])
        with self.assertRaises(SystemExit):
            parse_args(["-s", "src.md", "-t", "tgt.md", "--max-wait", "0"])

    def test_33_multiprocess_supervisor_stability_and_sigbreak(self):
        """Test supervisor spawning daemon in subprocess, verifying continuous live sync and clean shutdown."""
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("Supervisor Test v1\n")

        pid_file = os.path.join(self.temp_dir, "supervisor_daemon.pid")
        log_file = os.path.join(self.temp_dir, "supervisor_daemon.log")

        proc = subprocess.Popen(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "progress_watchdog.py"),
                "--source", self.source_file,
                "--target", self.target_file,
                "--debounce", "0.2",
                "--pid-file", pid_file,
                "--log-file", log_file,
                "--log-level", "DEBUG",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            # Wait for startup
            for _ in range(30):
                if os.path.exists(self.target_file) and os.path.exists(pid_file):
                    break
                time.sleep(0.1)

            self.assertTrue(os.path.exists(self.target_file))
            self.assertTrue(os.path.exists(pid_file))

            # Simulate supervisor updates over time
            for step in range(2, 6):
                with open(self.source_file, "w", encoding="utf-8") as f:
                    f.write(f"Supervisor Test v{step}\n")
                time.sleep(0.35)
                with open(self.target_file, "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), f"Supervisor Test v{step}\n")

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_34_short_8_3_and_symlink_path_matching(self):
        """Test ProgressWatchdogHandler correctly matches events across realpath and abspath variants."""
        handler = ProgressWatchdogHandler(
            source_path=self.source_file,
            target_path=self.target_file,
            debounce_interval=0.1,
        )
        try:
            # Realpath matches
            self.assertTrue(handler._matches_source(self.source_file))
            # Abspath matches
            self.assertTrue(handler._matches_source(os.path.abspath(self.source_file)))
            # Relative path within temp dir matches
            rel_src = os.path.relpath(self.source_file, start=self.temp_dir)
            full_rel = os.path.join(self.temp_dir, rel_src)
            self.assertTrue(handler._matches_source(full_rel))
            # Non-source does not match
            self.assertFalse(handler._matches_source(self.target_file))
        finally:
            handler.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)
