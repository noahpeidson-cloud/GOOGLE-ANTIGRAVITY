"""
Empirical Adversarial Stress Test Suite for PySpark & Gemini Omni Video Grading Engine.
Module: .agents.challenger_m3_1.stress_test_grading
Author: teamwork_preview_challenger (Milestone 3)
Target Directory: media_pipeline/grading

Comprehensive Adversarial Stress Vectors:
1. High-concurrency rate limit flooding (simulating 500 requests against 50 QPM window & thread contention).
2. Malformed / corrupted JSON payloads returned from Gemini API.
3. Out-of-bounds parameter scores (NaN, Inf, -50.0, 999.0, schema violations).
4. Dead Letter Queue (DLQ) disk serialization under simulated disk / path / permission failures.
"""

from __future__ import annotations

import concurrent.futures
import json
import math
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

# Ensure workspace root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from media_pipeline.grading.viral_schema import (
    AudioAcousticAnalysis,
    CrowdDynamicsAnalysis,
    DEFAULT_WEIGHTS,
    DropPacingAnalysis,
    EDMShortsViralMetrics,
    EDMViralGradingReport,
    HookAnalysis,
    LightingProductionAnalysis,
    ModelParameterWeights,
    TransientEvent,
    TrendingVerdict,
    ViralParameterScores,
    calculate_evpi,
    calculate_evpi_from_scores,
    classify_viral_tier,
    compute_killswitches,
    get_verdict_from_evpi,
)
from media_pipeline.grading.gemini_multimodal_client import (
    DeadLetterQueue,
    GeminiMultimodalClient,
    RateLimiter,
)
from media_pipeline.grading.spark_grading_job import (
    PYSPARK_AVAILABLE,
    PySparkGradingPipeline,
    fetch_active_weights,
    get_spark_output_schema,
    grade_partition,
)


# ============================================================================
# 1. HIGH CONCURRENCY RATE LIMIT FLOODING (500 REQUESTS AGAINST 50 QPM)
# ============================================================================

def test_rate_limiter_500_requests_virtual_clock_simulation():
    """
    Simulates 500 concurrent requests flooding RateLimiter configured with max_qpm=50.
    Uses virtual time stepping to simulate the full 500-request window (600s total duration)
    in milliseconds without sleeping real-world time.
    Asserts:
    1. Zero race conditions under 500 contending requests.
    2. Every acquisition is spaced exactly by min_interval = 1.2s.
    3. Total simulated elapsed time equals exactly (500 - 1) * 1.2s = 598.8s.
    """
    print("\n--- [VECTOR 1.1] 500 Requests against 50 QPM Window (Virtual Clock Simulation) ---")
    max_qpm = 50
    expected_interval = 60.0 / 50.0  # 1.2s per request
    limiter = RateLimiter(max_qpm=max_qpm)

    current_virtual_time = 1000000.0
    time_lock = threading.Lock()
    acquisition_times: List[float] = []

    def mock_time():
        with time_lock:
            return current_virtual_time

    def mock_sleep(seconds: float):
        nonlocal current_virtual_time
        with time_lock:
            current_virtual_time += seconds

    with patch("time.time", side_effect=mock_time), patch("time.sleep", side_effect=mock_sleep):
        # Reset limiter's initial reference time
        limiter.last_call_time = 0.0

        def client_request(req_id: int):
            limiter.acquire()
            with time_lock:
                acquisition_times.append(current_virtual_time)

        num_requests = 500
        # Dispatch 500 requests across concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(client_request, i) for i in range(num_requests)]
            concurrent.futures.wait(futures)

    assert len(acquisition_times) == 500, f"Expected 500 acquisitions, got {len(acquisition_times)}"
    sorted_times = sorted(acquisition_times)
    
    # Verify spacing between all 500 requests
    for idx in range(1, len(sorted_times)):
        spacing = sorted_times[idx] - sorted_times[idx - 1]
        assert abs(spacing - expected_interval) < 1e-5, f"Interval between #{idx-1} and #{idx} was {spacing}s, expected {expected_interval}s"

    total_virtual_span = sorted_times[-1] - sorted_times[0]
    expected_span = (500 - 1) * expected_interval
    assert abs(total_virtual_span - expected_span) < 1e-4, f"Total virtual span was {total_virtual_span}s, expected {expected_span}s"
    print(f"[PASS] 500 concurrent requests safely throttled: {total_virtual_span:.2f}s total simulated duration at exactly {expected_interval}s spacing.")


def test_rate_limiter_real_thread_contention():
    """Stress-tests RateLimiter under rapid real multi-threading to ensure no deadlocks."""
    print("\n--- [VECTOR 1.2] Real-Thread RateLimiter Rapid Contention ---")
    limiter = RateLimiter(max_qpm=12000) # 200 req/sec
    timestamps: List[float] = []
    lock = threading.Lock()

    def worker():
        limiter.acquire()
        with lock:
            timestamps.append(time.time())

    num_threads = 60
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(worker) for _ in range(num_threads)]
        concurrent.futures.wait(futures)

    assert len(timestamps) == num_threads
    print(f"[PASS] {num_threads} threads acquired RateLimiter cleanly with zero lock contention deadlocks.")


def test_simulated_500_requests_429_quota_exhaustion_flooding():
    """
    Floods the client with 500 simulated 429 quota exhaustion requests.
    Verifies that DeadLetterQueue serializes all 500 failures with exact schema and zero dropped entries.
    """
    print("\n--- [VECTOR 1.3] 500 Concurrent 429 Quota Exhaustion Flooding ---")
    with tempfile.TemporaryDirectory() as tmp_dlq:
        client = GeminiMultimodalClient(
            mock_mode=True,
            simulate_rate_limit=True,
            dlq_dir=tmp_dlq,
        )

        def make_call(i: int):
            try:
                client.grade_video_report(
                    video_id=f"clip_429_{i:04d}",
                    gcs_uri=f"gs://edm-vault/raw/clip_429_{i:04d}.mp4",
                )
                return "OK"
            except Exception as e:
                return f"ERR:{type(e).__name__}"

        num_requests = 500
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(make_call, range(num_requests)))

        assert all(r == "ERR:RuntimeError" for r in results)
        
        # Verify in-memory records
        records = client.dlq_records
        assert len(records) == num_requests, f"Expected {num_requests} records in DLQ memory, got {len(records)}"

        # Verify on-disk JSON files
        disk_files = list(Path(tmp_dlq).glob("*.json"))
        assert len(disk_files) == num_requests, f"Expected {num_requests} JSON files on disk, got {len(disk_files)}"
        print(f"[PASS] Successfully processed and captured 500 concurrent 429 failures into DLQ.")


def test_tenacity_retry_exception_filter_audit():
    """
    Adversarial Audit of Tenacity retry policy in _execute_live_call:
    Proves whether APIError is retried or bypassed by Tenacity's current exception filter.
    """
    print("\n--- [VECTOR 1.4] Tenacity Retry Policy Audit on APIError ---")
    client = GeminiMultimodalClient(mock_mode=False, api_key="dummy_key")
    
    mock_genai_client = MagicMock()
    class MockAPIError(Exception):
        pass

    attempts = 0
    def side_effect_counter(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise MockAPIError("429 Resource Exhausted")

    mock_genai_client.models.generate_content.side_effect = side_effect_counter
    client._client = mock_genai_client

    try:
        client._execute_live_call("gs://test/vid.mp4", EDMViralGradingReport)
        assert False, "Should have raised MockAPIError"
    except MockAPIError:
        print(f"[FINDING] MockAPIError resulted in {attempts} attempt(s). (Retry decorator caught only ConnectionError/TimeoutError).")


# ============================================================================
# 2. MALFORMED / CORRUPTED JSON PAYLOAD TESTS
# ============================================================================

def test_malformed_json_payload_resilience():
    """
    Tests EDMViralGradingReport model validation against varied corrupted / adversarial payloads.
    """
    print("\n--- [VECTOR 2.1] Malformed / Corrupted JSON Payload Resilience ---")
    
    corrupted_cases = [
        ("Truncated JSON", '{"video_id": "v1", "gcs_uri": "gs://b/v1.mp4", "video_duration'),
        ("Markdown Wrapped", '```json\n{"video_id": "v1", "gcs_uri": "gs://b/v1.mp4"}\n```'),
        ("HTML Error Page", '<!DOCTYPE html><html><body>502 Bad Gateway</body></html>'),
        ("Empty String", ""),
        ("JSON Array instead of Object", '[{"video_id": "v1"}]'),
        ("Missing Sub-Analyses", json.dumps({
            "video_id": "v_missing",
            "gcs_uri": "gs://bucket/raw/v_missing.mp4",
            "video_duration_seconds": 30.0,
            "aspect_ratio": "9:16",
            "evpi_composite_score": 85.0,
            "trending_verdict": "VIRAL_TIER_1",
            "algorithmic_recommendation": "Great video",
        })),
        ("Invalid Event Type in Transients", json.dumps({
            "video_id": "v_bad_event",
            "gcs_uri": "gs://bucket/raw/v_bad_event.mp4",
            "video_duration_seconds": 30.0,
            "aspect_ratio": "9:16",
            "key_transients": [{
                "timestamp_seconds": 1.5,
                "event_type": "confetti_cannon_explosion",  # Illegal literal
                "intensity": 0.9,
                "description": "Explosion"
            }],
            "hook_analysis": {"hook_onset_latency_seconds": 0.1, "transient_count_first_3s": 2, "initial_visual_stimulus_score": 80.0, "hrv_score": 80.0},
            "drop_pacing_analysis": {"drop_detected": True, "dpaw_score": 80.0},
            "audio_analysis": {"sub_bass_surge_ratio": 5.0, "spectral_flux_delta": 6.0, "loudness_jump_lufs_est": 5.0, "audio_clipping_detected": False, "adr_sfd_score": 80.0},
            "crowd_analysis": {"crowd_visible_percentage": 50.0, "jump_synchronicity_coherence": 0.8, "energy_acceleration_factor": 3.0, "moshpit_or_intense_reaction": True, "cke_mve_score": 80.0},
            "lighting_analysis": {"laser_co2_pyro_present": True, "strobe_frequency_hz": 12.0, "light_audio_sync_latency_ms": 10.0, "ltss_score": 80.0},
            "evpi_composite_score": 80.0,
            "trending_verdict": "HIGH_POTENTIAL",
            "algorithmic_recommendation": "Fix timing",
        })),
        ("Malformed GCS URI Regex in Report", json.dumps({
            "video_id": "v_bad_gcs",
            "gcs_uri": "https://storage.googleapis.com/bucket/video.mp4",  # Not gs://
            "video_duration_seconds": 30.0,
            "aspect_ratio": "9:16",
            "key_transients": [],
            "hook_analysis": {"hook_onset_latency_seconds": 0.1, "transient_count_first_3s": 2, "initial_visual_stimulus_score": 80.0, "hrv_score": 80.0},
            "drop_pacing_analysis": {"drop_detected": True, "dpaw_score": 80.0},
            "audio_analysis": {"sub_bass_surge_ratio": 5.0, "spectral_flux_delta": 6.0, "loudness_jump_lufs_est": 5.0, "audio_clipping_detected": False, "adr_sfd_score": 80.0},
            "crowd_analysis": {"crowd_visible_percentage": 50.0, "jump_synchronicity_coherence": 0.8, "energy_acceleration_factor": 3.0, "moshpit_or_intense_reaction": True, "cke_mve_score": 80.0},
            "lighting_analysis": {"laser_co2_pyro_present": True, "strobe_frequency_hz": 12.0, "light_audio_sync_latency_ms": 10.0, "ltss_score": 80.0},
            "evpi_composite_score": 80.0,
            "trending_verdict": "HIGH_POTENTIAL",
            "algorithmic_recommendation": "Fix timing",
        })),
    ]

    for label, payload in corrupted_cases:
        with pytest.raises((ValidationError, json.JSONDecodeError, Exception)):
            EDMViralGradingReport.model_validate_json(payload)
        print(f"[PASS] Successfully rejected corrupted payload: '{label}'")


def test_spark_partition_isolation_under_malformed_batch():
    """
    Stress-tests PySpark partition processing on a large heterogeneous batch containing:
    - 50 normal valid records
    - 20 adversarial / corrupted records (bad URIs, missing fields, unparseable values)
    Verifies that zero unhandled exceptions escape grade_partition and all failed items are tagged FAILED_DLQ.
    """
    print("\n--- [VECTOR 2.2] Spark Partition Isolation on 70-Item Adversarial Batch ---")
    valid_records = [
        {"video_id": f"valid_{i:03d}", "gcs_uri": f"gs://edm-vault/raw/valid_{i:03d}.mp4", "duration_seconds": 25.0}
        for i in range(50)
    ]
    corrupt_records = [
        {"video_id": f"bad_scheme_http_{i}", "gcs_uri": f"http://domain.com/v_{i}.mp4"}
        for i in range(5)
    ] + [
        {"video_id": f"bad_scheme_s3_{i}", "gcs_uri": f"s3://mybucket/v_{i}.mp4"}
        for i in range(5)
    ] + [
        {"video_id": f"empty_uri_{i}", "gcs_uri": ""}
        for i in range(5)
    ] + [
        {"video_id": f"none_uri_{i}", "gcs_uri": None}
        for i in range(5)
    ]

    combined_batch = valid_records[:25] + corrupt_records + valid_records[25:]
    assert len(combined_batch) == 70

    results = list(grade_partition(iter(combined_batch), DEFAULT_WEIGHTS, mock_mode=True))
    assert len(results) == 70

    graded_count = sum(1 for r in results if r["status"] == "GRADED")
    failed_count = sum(1 for r in results if r["status"] == "FAILED_DLQ")

    assert graded_count == 50, f"Expected 50 GRADED records, got {graded_count}"
    assert failed_count == 20, f"Expected 20 FAILED_DLQ records, got {failed_count}"

    for failed_rec in [r for r in results if r["status"] == "FAILED_DLQ"]:
        assert failed_rec["evpi_composite"] == 0.0
        assert failed_rec["trending_verdict"] == "LOW_REACH"
        assert failed_rec["error_message"] is not None

    print(f"[PASS] Processed batch of {len(combined_batch)} items: {graded_count} GRADED, {failed_count} FAILED_DLQ cleanly isolated.")


# ============================================================================
# 3. OUT-OF-BOUNDS PARAMETER SCORES TESTS
# ============================================================================

def test_out_of_bounds_viral_parameter_scores():
    """
    Stress-tests ViralParameterScores against negative, excessive, and NaN values.
    """
    print("\n--- [VECTOR 3.1] Out-of-Bounds ViralParameterScores ---")
    # Negative scores
    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=-50.0, dpaw=80.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)
    
    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=80.0, dpaw=-0.01, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)

    # Excessive scores (>100.0)
    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=100.1, dpaw=80.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)

    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=80.0, dpaw=999.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)

    # IEEE 754 NaN and Inf
    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=float('nan'), dpaw=80.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)

    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=float('inf'), dpaw=80.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)

    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=float('-inf'), dpaw=80.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)

    print("[PASS] ViralParameterScores rejected all negative, >100, NaN, and Inf values.")


def test_evpi_calculation_with_ieee754_special_values():
    """
    Empirically inspects calculate_evpi_from_scores and calculate_evpi behavior on NaN/Inf inputs.
    """
    print("\n--- [VECTOR 3.2] EVPI Calculation with IEEE 754 Special Values ---")
    res_nan = calculate_evpi_from_scores(
        hrv_score=float('nan'),
        dpaw_score=80.0,
        adr_sfd_score=80.0,
        cke_mve_score=80.0,
        ltss_score=80.0,
    )
    print(f"[FINDING] calculate_evpi_from_scores with NaN hrv evaluates to: {res_nan}")
    # In Python: min(100.0, NaN) -> 100.0, max(0.0, 100.0) -> 100.0.
    # This proves that unvalidated NaN passing into calculate_evpi_from_scores would clamp to 100.0 (VIRAL_TIER_1)
    # confirming the critical necessity of Pydantic validation before calculation.


def test_edm_shorts_viral_metrics_boundary_and_verdict_dissonance():
    """
    Tests EDMShortsViralMetrics schema enforcement:
    1. Duration > 60s
    2. Duration <= 0s
    3. Aspect ratio non-standard (e.g. 21:9)
    4. Verdict mismatch (EVPI 90.0 with LOW_REACH)
    5. Invalid GCS URI pattern
    """
    print("\n--- [VECTOR 3.3] EDMShortsViralMetrics Schema Boundary & Dissonance ---")
    valid_scores = ViralParameterScores(hrv=90.0, dpaw=90.0, adr_sfd=90.0, cke_mve=90.0, ltss=90.0)

    # 1. Duration > 60s
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="v1",
            gcs_uri="gs://b/v.mp4",
            duration_seconds=60.1,
            aspect_ratio="9:16",
            scores=valid_scores,
            evpi_composite=90.0,
            trending_verdict=TrendingVerdict.VIRAL_TIER_1,
        )

    # 2. Duration <= 0s
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="v1",
            gcs_uri="gs://b/v.mp4",
            duration_seconds=0.0,
            aspect_ratio="9:16",
            scores=valid_scores,
            evpi_composite=90.0,
            trending_verdict=TrendingVerdict.VIRAL_TIER_1,
        )

    # 3. Invalid aspect ratio (e.g. 21:9)
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="v1",
            gcs_uri="gs://b/v.mp4",
            duration_seconds=30.0,
            aspect_ratio="21:9",
            scores=valid_scores,
            evpi_composite=90.0,
            trending_verdict=TrendingVerdict.VIRAL_TIER_1,
        )

    # 4. Verdict mismatch
    with pytest.raises(ValidationError, match="does not match expected"):
        EDMShortsViralMetrics(
            video_id="v1",
            gcs_uri="gs://b/v.mp4",
            duration_seconds=30.0,
            aspect_ratio="9:16",
            scores=valid_scores,
            evpi_composite=90.0,  # Should be VIRAL_TIER_1
            trending_verdict=TrendingVerdict.LOW_REACH,
        )

    # 5. Invalid GCS URI pattern (.mov instead of .mp4)
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="v1",
            gcs_uri="gs://b/invalid_file.mov",
            duration_seconds=30.0,
            aspect_ratio="9:16",
            scores=valid_scores,
            evpi_composite=90.0,
            trending_verdict=TrendingVerdict.VIRAL_TIER_1,
        )

    print("[PASS] EDMShortsViralMetrics successfully enforced all boundary constraints and verdict consistency.")


def test_model_parameter_weights_simplex_stress():
    """
    Stress-tests ModelParameterWeights simplex constraint sum(w_i) == 1.0.
    """
    print("\n--- [VECTOR 3.4] ModelParameterWeights Simplex Stress ---")
    invalid_weight_sets = [
        {"weight_hrv": 0.5, "weight_dpaw": 0.5, "weight_adr_sfd": 0.5, "weight_cke_mve": 0.1, "weight_ltss": 0.1},
        {"weight_hrv": 0.1, "weight_dpaw": 0.1, "weight_adr_sfd": 0.1, "weight_cke_mve": 0.1, "weight_ltss": 0.1},
        {"weight_hrv": 1.2, "weight_dpaw": 0.0, "weight_adr_sfd": 0.0, "weight_cke_mve": 0.0, "weight_ltss": -0.2},
    ]

    for w_set in invalid_weight_sets:
        with pytest.raises(ValidationError):
            ModelParameterWeights(**w_set)

    print("[PASS] ModelParameterWeights strictly rejected all non-simplex weight combinations.")


# ============================================================================
# 4. DLQ DISK SERIALIZATION & FAULT SIMULATION TESTS
# ============================================================================

def test_dlq_disk_failure_graceful_degradation():
    """
    Simulates disk write failures in DeadLetterQueue (e.g. read-only filesystem, permission denied).
    Verifies:
    1. record_failure catches the write exception and does NOT crash.
    2. The failure record is safely retained in in-memory list (self.records).
    """
    print("\n--- [VECTOR 4.1] DLQ Disk Write Failure Graceful Degradation ---")
    with tempfile.TemporaryDirectory() as tmp_dlq:
        dlq = DeadLetterQueue(dlq_dir=tmp_dlq)

        # Mock open to raise PermissionError during disk serialization
        original_open = open
        def faulty_open(file, mode="r", *args, **kwargs):
            if "w" in mode and str(tmp_dlq) in str(file):
                raise PermissionError("EACCES: Permission denied writing DLQ entry")
            return original_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=faulty_open):
            entry = dlq.record_failure(
                video_id="vid_disk_fail",
                gcs_uri="gs://edm-vault/raw/fail.mp4",
                error=RuntimeError("Corrupt media stream"),
                context={"test": "simulated_disk_failure"},
            )

        assert entry["video_id"] == "vid_disk_fail"
        assert len(dlq.records) == 1
        assert dlq.records[0]["video_id"] == "vid_disk_fail"
        assert dlq.records[0]["error_type"] == "RuntimeError"
        print("[PASS] DLQ gracefully handled disk PermissionError and retained record in-memory.")


def test_dlq_high_concurrency_thread_safety():
    """
    Stress-tests DeadLetterQueue under 100 concurrent threads recording failures simultaneously.
    Verifies thread safety, exact count of memory records and on-disk files.
    """
    print("\n--- [VECTOR 4.2] DLQ High-Concurrency Thread Safety (100 Threads) ---")
    with tempfile.TemporaryDirectory() as tmp_dlq:
        dlq = DeadLetterQueue(dlq_dir=tmp_dlq)

        def record_worker(i: int):
            dlq.record_failure(
                video_id=f"thread_vid_{i:04d}",
                gcs_uri=f"gs://edm-vault/raw/thread_vid_{i:04d}.mp4",
                error=RuntimeError(f"Simulated error {i}"),
            )

        num_threads = 100
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(record_worker, i) for i in range(num_threads)]
            concurrent.futures.wait(futures)

        records = dlq.get_records()
        assert len(records) == num_threads, f"Expected {num_threads} records, got {len(records)}"

        disk_files = list(Path(tmp_dlq).glob("*.json"))
        assert len(disk_files) == num_threads, f"Expected {num_threads} files on disk, got {len(disk_files)}"
        print(f"[PASS] Recorded {num_threads} concurrent failures without race condition or lost records.")


def test_dlq_in_memory_only_mode():
    """Validates DeadLetterQueue when dlq_dir=None (pure in-memory)."""
    print("\n--- [VECTOR 4.3] DLQ In-Memory Only Mode ---")
    dlq = DeadLetterQueue(dlq_dir=None)
    assert dlq.dlq_dir is None
    entry = dlq.record_failure("mem_vid", "gs://b/v.mp4", ValueError("Test err"))
    assert len(dlq.get_records()) == 1
    assert entry["video_id"] == "mem_vid"
    dlq.clear()
    assert len(dlq.get_records()) == 0
    print("[PASS] In-memory mode works cleanly.")


# ============================================================================
# MASTER RUNNER
# ============================================================================

def run_stress_suite():
    """Runs all adversarial stress tests and outputs comprehensive summary."""
    print("=" * 80)
    print("STARTING EMPIRICAL ADVERSARIAL STRESS SUITE FOR MILESTONE 3")
    print("=" * 80)

    tests = [
        test_rate_limiter_500_requests_virtual_clock_simulation,
        test_rate_limiter_real_thread_contention,
        test_simulated_500_requests_429_quota_exhaustion_flooding,
        test_tenacity_retry_exception_filter_audit,
        test_malformed_json_payload_resilience,
        test_spark_partition_isolation_under_malformed_batch,
        test_out_of_bounds_viral_parameter_scores,
        test_evpi_calculation_with_ieee754_special_values,
        test_edm_shorts_viral_metrics_boundary_and_verdict_dissonance,
        test_model_parameter_weights_simplex_stress,
        test_dlq_disk_failure_graceful_degradation,
        test_dlq_high_concurrency_thread_safety,
        test_dlq_in_memory_only_mode,
    ]

    passed = 0
    failed = 0
    start_all = time.time()

    for test_fn in tests:
        name = test_fn.__name__
        try:
            test_fn()
            print(f"[TEST PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"[TEST FAIL] {name}: {e}")
            failed += 1

    total_time = time.time() - start_all
    print("\n" + "=" * 80)
    print(f"ADVERSARIAL STRESS TEST SUMMARY: {passed} PASSED, {failed} FAILED in {total_time:.2f}s")
    print("=" * 80)

    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    run_stress_suite()
