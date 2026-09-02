"""
Targeted Concurrency Diagnostics for TelemetryStore.
Explores concurrency limits, busy_timeout behaviors, and connection lifecycle on Windows.
"""

import os
import sqlite3
import sys
import tempfile
import threading
import time

WORKSPACE_ROOT = r"G:\My Drive\GOOGLE ANTIGRAVITY"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from unified_ops_hub.ml_agent.telemetry import TelemetryStore

def test_concurrency_matrix():
    print("Testing concurrency matrix...")
    thread_counts = [8, 16, 24, 32, 40, 48, 50]
    writes_per_thread = 40

    for num_threads in thread_counts:
        temp_db = tempfile.mktemp(suffix=".db")
        store = TelemetryStore(temp_db)
        errors = []

        def worker(tid: int):
            try:
                for i in range(writes_per_thread):
                    store.record_span(
                        platform="tiktok",
                        lens_type="web_a11y_tree",
                        duration_ms=1000,
                        yield_count=10,
                        error_count=0,
                        status_code="SUCCESS",
                        metadata={"t": tid, "i": i},
                    )
            except Exception as e:
                errors.append((tid, e))

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - t0

        total_records = len(store.get_recent_spans(limit=10000))
        expected = num_threads * writes_per_thread
        print(f"Threads: {num_threads:2d} | Total Writes: {expected:4d} | Elapsed: {elapsed:5.2f}s | Success: {total_records:4d}/{expected:4d} | Errors: {len(errors)}")

        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass

if __name__ == "__main__":
    test_concurrency_matrix()
