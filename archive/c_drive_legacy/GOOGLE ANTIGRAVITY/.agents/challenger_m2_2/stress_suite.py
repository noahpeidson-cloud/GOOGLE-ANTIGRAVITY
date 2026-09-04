"""Comprehensive Empirical Adversarial Stress Suite for HealthScanner Orchestrator."""

import hashlib
import json
import logging
import os
import random
import shutil
import stat
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, List

cron_path = r"g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron"
tests_path = r"g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests"
for p in [cron_path, tests_path]:
    if p not in sys.path:
        sys.path.insert(0, p)

from conftest import FileSystemSnapshot
from detectors.base import BaseDetector
from models import AnomalyRecord, DetectorType, Severity
from scanner import HealthScanner

logging.basicConfig(level=logging.CRITICAL)

print("=== STARTING ADVANCED EMPIRICAL ADVERSARIAL STRESS HARNESS ===")

passed_tests = 0
total_tests = 0


def test_assert(name: str, condition: bool, msg: str = "") -> None:
    global passed_tests, total_tests
    total_tests += 1
    if condition:
        passed_tests += 1
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name}: {msg}")
        raise AssertionError(f"{name} failed: {msg}")


# =============================================================
# SUITE 1: EXCEPTION & CORRUPTION ISOLATION
# =============================================================
print("\n[SUITE 1] Advanced Exception & Return Corruption Isolation")


class CrashingDetector(BaseDetector):
    def __init__(self, exc_to_raise: Exception, name: str = "CrashingDetector") -> None:
        self.exc_to_raise = exc_to_raise
        self.name = name

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        raise self.exc_to_raise


class CorruptReturnDetector(BaseDetector):
    def __init__(self, corrupt_value: Any) -> None:
        self.corrupt_value = corrupt_value

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        return self.corrupt_value


class GoodDetector(BaseDetector):
    def __init__(self, name: str, count: int = 1) -> None:
        self.name = name
        self.count = count

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        return [
            AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path=f"{self.name}_path_{i}.md",
                severity=Severity.LOW,
                description=f"Test anomaly {i} from {self.name}",
                raw_details={"index": i},
            )
            for i in range(self.count)
        ]


# 1.1 100% Crashing Detectors (all 5 crash)
c_detectors = [
    CrashingDetector(RuntimeError("Fatal socket collision"), "DetRuntime"),
    CrashingDetector(ValueError("Invalid integer threshold"), "DetValue"),
    CrashingDetector(KeyError("Missing config key"), "DetKey"),
    CrashingDetector(PermissionError("Access denied"), "DetPerm"),
    CrashingDetector(MemoryError("OOM simulation"), "DetMem"),
]
scanner_all_fail = HealthScanner(detectors=c_detectors)
anomalies_all_fail = scanner_all_fail.scan_workspace("/tmp/dummy")
test_assert("1.1 100% detector crash returns empty list []", anomalies_all_fail == [], f"Got {anomalies_all_fail}")
test_assert("1.1 100% detector crash records non-negative duration", scanner_all_fail.get_last_duration_ms() >= 0.0)

# 1.2 Interleaved Crash/Good Detectors
interleaved_detectors = []
for i in range(10):
    if i % 2 == 0:
        interleaved_detectors.append(CrashingDetector(RuntimeError(f"Crash at {i}"), f"Crash_{i}"))
    else:
        interleaved_detectors.append(GoodDetector(f"Good_{i}", count=2))

scanner_interleaved = HealthScanner(detectors=interleaved_detectors)
anomalies_interleaved = scanner_interleaved.scan_workspace("/tmp/dummy")
test_assert(
    "1.2 Interleaved crash/good detectors returns exactly 10 records",
    len(anomalies_interleaved) == 10,
    f"Got {len(anomalies_interleaved)}",
)
expected_paths = [f"Good_{i}_path_{j}.md" for i in range(1, 10, 2) for j in range(2)]
actual_paths = [a.target_path for a in anomalies_interleaved]
test_assert("1.2 Anomaly sequence perfectly preserved from surviving detectors", actual_paths == expected_paths, f"Actual: {actual_paths}")

# 1.3 Corrupt Return Value Isolation (int, float, invalid object)
scanner_corrupt = HealthScanner(
    detectors=[
        CorruptReturnDetector(12345),  # Non-iterable int causes TypeError in extend(), isolated
        CorruptReturnDetector(object()),  # Non-iterable object causes TypeError in extend(), isolated
        GoodDetector("SurvivingCorrupt", count=2),
    ]
)
anomalies_corrupt = scanner_corrupt.scan_workspace("/tmp/dummy")
test_assert("1.3 Non-iterable corrupt return values caught & isolated", len(anomalies_corrupt) == 2 and anomalies_corrupt[0].target_path == "SurvivingCorrupt_path_0.md")

# 1.4 Deep Recursion & Custom Exceptions
def recursive_blowup(depth: int) -> None:
    if depth > 0:
        recursive_blowup(depth + 1)
    raise RecursionError("Maximum recursion depth exceeded")


class RecursionBlowupDetector(BaseDetector):
    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        recursive_blowup(1)
        return []


scanner_recursion = HealthScanner(detectors=[RecursionBlowupDetector(), GoodDetector("AfterRecursion", count=1)])
anomalies_rec = scanner_recursion.scan_workspace("/tmp/dummy")
test_assert("1.4 RecursionError isolated and subsequent detectors execute", len(anomalies_rec) == 1)

# =============================================================
# SUITE 2: DURATION MEASUREMENT & STATISTICAL AGGREGATION
# =============================================================
print("\n[SUITE 2] Duration Measurement & Statistical Aggregation")


class DelayedDetector(BaseDetector):
    def __init__(self, delay_s: float) -> None:
        self.delay_s = delay_s

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        time.sleep(self.delay_s)
        return []


# 2.1 Controlled Latency Accuracy
delays = [0.010, 0.020, 0.030]
scanner_delay = HealthScanner(detectors=[DelayedDetector(d) for d in delays])
t0 = time.perf_counter()
scanner_delay.scan_workspace("/tmp/dummy")
t_ext_ms = (time.perf_counter() - t0) * 1000.0
t_int_ms = scanner_delay.get_last_duration_ms()

test_assert(
    "2.1 Internal duration aligns with external high-res timer (< 15ms delta)",
    abs(t_ext_ms - t_int_ms) < 15.0,
    f"Ext: {t_ext_ms:.2f}ms, Int: {t_int_ms:.2f}ms",
)
test_assert("2.1 Injected ~60ms delay measured accurately", 50.0 <= t_int_ms <= 85.0, f"Measured: {t_int_ms:.2f}ms")

# 2.2 Re-entrancy & Isolation
scanner_reset = HealthScanner(detectors=[DelayedDetector(0.040)])
scanner_reset.scan_workspace("/tmp/dummy")
first_duration = scanner_reset.get_last_duration_ms()

scanner_reset.detectors = [DelayedDetector(0.005)]
scanner_reset.scan_workspace("/tmp/dummy")
second_duration = scanner_reset.get_last_duration_ms()

test_assert(
    "2.2 Duration resets per invocation (no stale accumulator)",
    second_duration < first_duration and second_duration < 25.0,
    f"First: {first_duration:.2f}ms, Second: {second_duration:.2f}ms",
)

# 2.3 Statistical distribution over N=50 randomized runs
durations = []
for _ in range(50):
    sleep_time = random.uniform(0.002, 0.008)
    s = HealthScanner(detectors=[DelayedDetector(sleep_time)])
    s.scan_workspace("/tmp/dummy")
    durations.append(s.get_last_duration_ms())

mean_d = statistics.mean(durations)
median_d = statistics.median(durations)
stdev_d = statistics.stdev(durations)
min_d = min(durations)
max_d = max(durations)

print(f"  [METRICS] N=50 Runs: Mean={mean_d:.2f}ms, Median={median_d:.2f}ms, StDev={stdev_d:.2f}ms, Min={min_d:.2f}ms, Max={max_d:.2f}ms")
test_assert("2.3 Duration distribution bound min >= 1.5ms, max <= 35ms", min_d >= 1.5 and max_d <= 35.0)
test_assert("2.3 Distribution mean matches expected uniform distribution (2-12ms)", 2.0 <= mean_d <= 12.0)

# 2.4 High-volume throughput (100,000 anomaly records stress test)
class HeavyVolumeDetector(BaseDetector):
    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        return [
            AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path=f"file_{i}.md",
                severity=Severity.LOW,
                description="Heavy volume record",
                raw_details={"i": i},
            )
            for i in range(50000)
        ]


scanner_heavy = HealthScanner(detectors=[HeavyVolumeDetector(), HeavyVolumeDetector()])
t_heavy_start = time.perf_counter()
heavy_records = scanner_heavy.scan_workspace("/tmp/dummy")
heavy_duration_ms = (time.perf_counter() - t_heavy_start) * 1000.0

test_assert("2.4 Aggregates 100,000 anomaly records without failure", len(heavy_records) == 100000)
test_assert("2.4 100,000 records processed rapidly (< 500ms)", heavy_duration_ms < 500.0, f"Duration: {heavy_duration_ms:.2f}ms")

# =============================================================
# SUITE 3: CRYPTOGRAPHIC SHA-256 READ-ONLY IMMUTABILITY
# =============================================================
print("\n[SUITE 3] Cryptographic SHA-256 Read-Only Non-Destructive Invariance")

# 3.1 Complex multi-artifact mock workspace
with tempfile.TemporaryDirectory() as temp_dir:
    ws = Path(temp_dir) / "test_workspace"
    ws.mkdir()

    # Stale files
    old_time = time.time() - (48 * 3600)
    for name in ["plan_v1.md", "scratchpad.md", "notes.md"]:
        f = ws / name
        f.write_text(f"# Stale plan {name}", encoding="utf-8")
        os.utime(str(f), (old_time, old_time))

    # Fresh files
    f_fresh = ws / "active_task.md"
    f_fresh.write_text("# Active plan", encoding="utf-8")

    # Whitelisted manifests
    f_gemini = ws / "GEMINI.md"
    f_gemini.write_text("# Steering Manifest\n" + "\n".join([f"Rule {i}" for i in range(120)]), encoding="utf-8")
    f_proj = ws / "PROJECT.md"
    f_proj.write_text("# Project Architecture", encoding="utf-8")

    # Secret zero files
    f_env = ws / ".env"
    f_env.write_text("API_KEY=your_token_here\nPORT=3000\n", encoding="utf-8")
    f_cfg = ws / "config.json"
    f_cfg.write_text('{"key": "YOUR_API_KEY_HERE"}', encoding="utf-8")

    # Disabled plugins
    plugins_dir = ws / ".gemini" / "config" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "gcp_spark.disabled").mkdir()
    (plugins_dir / "gcp_spark.disabled" / "SKILL.md").write_text("# Spark", encoding="utf-8")

    # Domain tracks
    sports = ws / "sports_cards"
    sports.mkdir()
    (sports / "video_leak.mp4").write_bytes(b"fake_mp4_bytes_12345")
    content = ws / "content_creation"
    content.mkdir()
    (content / "card_ladder_export.csv").write_text("card,price\n1,100", encoding="utf-8")

    # Take Snapshot
    snapshot = FileSystemSnapshot(str(ws))
    initial_file_count = len(snapshot.initial_hashes)
    print(f"  [SNAPSHOT] Tracked {initial_file_count} files across directory hierarchy")

    # Execute production HealthScanner 10 consecutive times
    real_scanner = HealthScanner()
    for run_idx in range(10):
        findings = real_scanner.scan_workspace(str(ws))
        test_assert(f"3.1 Run {run_idx+1}/10 detected anomalies", len(findings) >= 5, f"Got {len(findings)}")
        snapshot.assert_untouched()

    test_assert("3.1 10 Consecutive Full Scans: 100% Cryptographic SHA-256 Invariance Verified", True)

# 3.2 Live Workspace SHA-256 Invariance Test (Scanning the actual .agents/cron tree)
print("  [SNAPSHOT] Computing initial SHA-256 snapshot of live .agents/cron directory...")
live_cron_snapshot = FileSystemSnapshot(cron_path)
live_file_count = len(live_cron_snapshot.initial_hashes)
print(f"  [SNAPSHOT] Tracked {live_file_count} live files in .agents/cron")

live_scanner = HealthScanner()
live_anomalies = live_scanner.scan_workspace(cron_path)
print(f"  [LIVE SCAN] Scan completed in {live_scanner.get_last_duration_ms():.2f}ms, findings: {len(live_anomalies)}")

live_cron_snapshot.assert_untouched()
test_assert("3.2 Live .agents/cron filesystem 100% untouched & cryptographically invariant after scan", True)

# =============================================================
# SUITE 4: CONCURRENCY, THREAD SAFETY & BOUNDARY CONDITIONS
# =============================================================
print("\n[SUITE 4] Concurrency & Boundary Conditions")

# 4.1 Multi-threaded concurrent execution (20 worker threads)
shared_scanner = HealthScanner()
thread_errors = []
thread_results = []


def thread_worker(tid: int) -> None:
    try:
        res = shared_scanner.scan_workspace(str(cron_path))
        thread_results.append(len(res))
    except Exception as e:
        thread_errors.append((tid, e))


threads = [threading.Thread(target=thread_worker, args=(i,)) for i in range(20)]
for t in threads:
    t.start()
for t in threads:
    t.join()

test_assert("4.1 20-Thread concurrent execution zero exceptions", len(thread_errors) == 0, f"Errors: {thread_errors}")
test_assert("4.1 All 20 threads completed successfully", len(thread_results) == 20)

# 4.2 Empty detector list
empty_scanner = HealthScanner(detectors=[])
empty_res = empty_scanner.scan_workspace("/tmp/dummy")
test_assert("4.2 Empty detector list returns empty anomalies", empty_res == [])
test_assert("4.2 Empty detector list records duration", empty_scanner.get_last_duration_ms() >= 0.0)

# 4.3 Non-existent workspace path
res_nonexistent = real_scanner.scan_workspace("/path/that/does/not/exist_12345")
test_assert("4.3 Non-existent path handled gracefully without throwing", isinstance(res_nonexistent, list))

print(f"\n======================================================")
print(f"ALL EMPIRICAL CHALLENGE SUITES PASSED: {passed_tests}/{total_tests} tests")
print(f"======================================================")
