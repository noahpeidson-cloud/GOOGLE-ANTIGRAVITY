import os
import sys
import threading
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from media_pipeline.grading.gemini_multimodal_client import RateLimiter, DeadLetterQueue, GeminiMultimodalClient
from media_pipeline.grading.viral_schema import (
    compute_killswitches,
    calculate_evpi_from_scores,
    classify_viral_tier,
    ViralParameterScores,
    ModelParameterWeights,
    EDMViralGradingReport,
    HookAnalysis,
    DropPacingAnalysis,
    AudioAcousticAnalysis,
    CrowdDynamicsAnalysis,
    LightingProductionAnalysis,
    DEFAULT_WEIGHTS,
)
from media_pipeline.grading.spark_grading_job import grade_partition, get_spark_output_schema

print("=== STARTING ADVERSARIAL STRESS TEST SUITE ===")

# 1. Stress test RateLimiter with 10 concurrent threads
print("\n[1] Stress testing RateLimiter thread safety...")
rl = RateLimiter(max_qpm=600)  # 10 req/s -> 0.1s interval
start = time.time()
def worker():
    for _ in range(3):
        rl.acquire()
threads = [threading.Thread(target=worker) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()
elapsed = time.time() - start
print(f"  RateLimiter 15 acquisitions across 5 threads completed in {elapsed:.2f}s")
assert elapsed >= 1.0, f"RateLimiter should take at least 1.0s for 15 requests at 10 req/s, took {elapsed}"

# 2. Stress test DLQ concurrent recording
print("\n[2] Stress testing DLQ concurrent recording...")
dlq = DeadLetterQueue()
def dlq_worker(idx):
    for i in range(20):
        dlq.record_failure(f"vid_{idx}_{i}", f"gs://bucket/vid_{idx}_{i}.mp4", ValueError(f"err_{idx}_{i}"))
threads = [threading.Thread(target=dlq_worker, args=(t,)) for t in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()
records = dlq.get_records()
print(f"  DLQ total recorded: {len(records)} (expected 100)")
assert len(records) == 100, f"Expected 100 DLQ records, got {len(records)}"

# 3. Test grade_partition with mixed batch (valid, invalid URI, simulated errors)
print("\n[3] Testing grade_partition error isolation...")
mixed_records = [
    {"video_id": "v1_valid", "gcs_uri": "gs://b/v1.mp4", "duration_seconds": 30.0},
    {"video_id": "v2_bad_uri", "gcs_uri": "invalid_uri_no_gs", "duration_seconds": 20.0},
    {"video_id": "v3_horiz", "gcs_uri": "gs://b/v3.mp4", "duration_seconds": 10.0, "aspect_ratio": "16:9"},
    {"video_id": "v4_long", "gcs_uri": "gs://b/v4.mp4", "duration_seconds": 75.0},
]
results = list(grade_partition(iter(mixed_records), DEFAULT_WEIGHTS, mock_mode=True))
print(f"  Partition output count: {len(results)}")
for r in results:
    print(f"  Video: {r['video_id']} | Status: {r['status']} | Verdict: {r['trending_verdict']} | EVPI: {r['evpi_composite']}")
assert results[0]["status"] == "GRADED"
assert results[1]["status"] == "FAILED_DLQ"
assert "Invalid GCS URI format" in results[1]["error_message"]
assert results[2]["status"] == "GRADED"
assert results[3]["status"] == "GRADED"

# 4. Check killswitches on boundary durations
print("\n[4] Testing killswitch boundaries...")
k8 = compute_killswitches(False, "9:16", 8.0)
k799 = compute_killswitches(False, "9:16", 7.99)
k12 = compute_killswitches(False, "9:16", 12.0)
k38 = compute_killswitches(False, "9:16", 38.0)
k60 = compute_killswitches(False, "9:16", 60.0)
k601 = compute_killswitches(False, "9:16", 60.01)

print(f"  duration=8.0: {k8} (k_dur should be 0.85)")
assert k8[2] == 0.85
print(f"  duration=7.99: {k799} (k_dur should be 0.40)")
assert k799[2] == 0.40
print(f"  duration=12.0: {k12} (k_dur should be 1.0)")
assert k12[2] == 1.0
print(f"  duration=38.0: {k38} (k_dur should be 1.0)")
assert k38[2] == 1.0
print(f"  duration=60.0: {k60} (k_dur should be 0.85)")
assert k60[2] == 0.85
print(f"  duration=60.01: {k601} (k_dur should be 0.40)")
assert k601[2] == 0.40

# 5. Check EVPI formula clamping and tier classification
print("\n[5] Testing EVPI clamping and tier thresholds...")
assert calculate_evpi_from_scores(100, 100, 100, 100, 100) == 100.0
assert calculate_evpi_from_scores(0, 0, 0, 0, 0) == 0.0
assert classify_viral_tier(85.0) == "VIRAL_TIER_1"
assert classify_viral_tier(84.99) == "HIGH_POTENTIAL"
assert classify_viral_tier(70.0) == "HIGH_POTENTIAL"
assert classify_viral_tier(69.99) == "MODERATE"
assert classify_viral_tier(50.0) == "MODERATE"
assert classify_viral_tier(49.99) == "LOW_REACH"

print("\n=== ALL ADVERSARIAL STRESS CHECKS PASSED SUCCESSFULLY! ===")
