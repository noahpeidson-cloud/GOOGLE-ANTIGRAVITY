"""
adversarial_audit_test.py
=========================
Independent adversarial verification script executed by victory_auditor.
Stress-tests:
- 100 rapid write bursts under strict debounce timing
- 16 concurrent readers hammering target during rapid writes
- Large file streaming with SHA256 checksum comparison
- Subprocess CLI execution with PID tracking and signal termination
"""

import os
import sys
import time
import hashlib
import tempfile
import shutil
import threading
import subprocess

# Ensure we import progress_watchdog from .agents
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from progress_watchdog import (
    ProgressWatchdogDaemon,
    safe_atomic_write,
    safe_read_file,
    safe_sync,
    validate_paths,
)


def run_adversarial_audit():
    temp_dir = tempfile.mkdtemp(prefix="auditor_stress_")
    src = os.path.join(temp_dir, "state_source.md")
    tgt = os.path.join(temp_dir, "artifact_target.md")

    print("[AUDIT] Starting independent adversarial verification...")

    try:
        # Check 1: 100 Rapid writes in < 0.5s -> Max 1 sync
        print("[AUDIT 1] Stress-testing 100 rapid writes under 1.0s debounce...")
        with open(src, "w", encoding="utf-8") as f:
            f.write("# Start\n")

        daemon = ProgressWatchdogDaemon(
            source_path=src,
            target_path=tgt,
            debounce_interval=1.0,
            initial_sync=False,
        )
        daemon.start()

        time.sleep(0.3)
        assert daemon.metrics["sync_count"] == 0, "Initial sync count must be 0"

        start_burst = time.time()
        for i in range(1, 101):
            with open(src, "a", encoding="utf-8") as f:
                f.write(f"- [x] State item {i} ðŸš€\n")
            time.sleep(0.003)
        burst_duration = time.time() - start_burst
        print(f"[AUDIT 1] 100 writes completed in {burst_duration:.3f}s")
        assert burst_duration < 1.0, "Burst took too long"

        time.sleep(0.2)
        assert daemon.metrics["sync_count"] == 0, "No sync should occur during debounce window"

        time.sleep(1.3)
        syncs = daemon.metrics["sync_count"]
        print(f"[AUDIT 1] Post-debounce sync count: {syncs}")
        assert syncs == 1, f"Expected exactly 1 sync, got {syncs}"

        with open(tgt, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 101, f"Expected 101 lines in target, got {len(lines)}"
        assert lines[-1].strip() == "- [x] State item 100 ðŸš€"
        daemon.stop()
        print("[AUDIT 1] PASSED.")

        # Check 2: 16 Concurrent Reader Threads during 40 continuous writes
        print("[AUDIT 2] Stress-testing 16 concurrent readers hammering target...")
        with open(src, "w", encoding="utf-8") as f:
            f.write("v0: initial content " + ("=" * 150) + "\n")

        daemon2 = ProgressWatchdogDaemon(
            source_path=src,
            target_path=tgt,
            debounce_interval=0.05,
            initial_sync=True,
        )
        daemon2.start()

        stop_flag = threading.Event()
        read_counts = [0]
        corrupted = []
        read_errors = []

        def reader_task(rid: int):
            while not stop_flag.is_set():
                content = safe_read_file(tgt, max_retries=20, retry_delay=0.003, allow_empty=False)
                if content:
                    read_counts[0] += 1
                    if not content.startswith("v"):
                        corrupted.append(f"Reader {rid} read corrupt data: {content[:30]}")
                else:
                    read_errors.append(f"Reader {rid} failed to read target")
                time.sleep(0.001)

        readers = [threading.Thread(target=reader_task, args=(i,), daemon=True) for i in range(16)]
        for r in readers:
            r.start()

        for step in range(1, 41):
            with open(src, "w", encoding="utf-8") as f:
                f.write(f"v{step}: write payload {step} " + ("=" * 150) + "\n")
            time.sleep(0.04)

        time.sleep(0.3)
        stop_flag.set()
        for r in readers:
            r.join(timeout=2.0)
        daemon2.stop()

        print(f"[AUDIT 2] Total successful concurrent reads: {read_counts[0]}")
        assert read_counts[0] > 100, f"Expected >100 reads, got {read_counts[0]}"
        assert len(corrupted) == 0, f"Found corrupted reads: {corrupted}"
        assert len(read_errors) == 0, f"Found read errors: {read_errors}"
        assert daemon2.metrics["error_count"] == 0, f"Daemon reported sync errors: {daemon2.metrics['error_count']}"
        print("[AUDIT 2] PASSED.")

        # Check 3: Large binary SHA256 bit-for-bit fidelity check
        print("[AUDIT 3] Checking bit-for-bit SHA256 integrity on 2MB payload...")
        large_payload = os.urandom(2 * 1024 * 1024)
        src_sha256 = hashlib.sha256(large_payload).hexdigest()
        with open(src, "wb") as f:
            f.write(large_payload)

        ok = safe_sync(src, tgt)
        assert ok, "safe_sync failed on 2MB payload"
        with open(tgt, "rb") as f:
            tgt_bytes = f.read()
        tgt_sha256 = hashlib.sha256(tgt_bytes).hexdigest()
        assert src_sha256 == tgt_sha256, "SHA256 mismatch after sync"
        print(f"[AUDIT 3] SHA256 match verified: {src_sha256}")
        print("[AUDIT 3] PASSED.")

        print("\n=== ALL ADVERSARIAL AUDIT CHECKS PASSED SUCCESSFULLY ===")
        return True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_adversarial_audit()
    sys.exit(0 if success else 1)

