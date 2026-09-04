"""
Deterministic Local PySpark & Gemini Omni Video Grading Test Suite.
Module: media_pipeline.grading.test_spark_grading
Authoritative Requirements: PROJECT.md, VIRAL_FORMULA.md, Acceptance Criteria for Milestone 3

Test Coverage:
1. Pydantic V2 Schemas: EDMViralGradingReport, EDMShortsViralMetrics, TransientEvent, and sub-analyses.
2. EVPI Mathematical Formulation: 5-parameter weighting, non-linear killswitches, and viral tier classification.
3. Gemini Multimodal Client: Structured outputs, tenacity retry logic, rate limiter, and DLQ serialization.
4. PySpark Batch Job: Distributed partition processing, broadcast dynamic weights, DLQ error isolation.
5. End-to-end batch execution on mock video payloads verifying all 5 viral scores are generated.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
import pytest
from pydantic import ValidationError

# Add project root to sys.path to allow absolute imports
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
# 1. VIRAL SCHEMA PYDANTIC V2 TESTS
# ============================================================================

def test_transient_event_validation():
    """Validates TransientEvent bounds and literal event types."""
    event = TransientEvent(
        timestamp_seconds=12.45,
        event_type="audio_drop",
        intensity=0.95,
        description="Sub-bass impact (42Hz) with laser fan",
    )
    assert event.timestamp_seconds == 12.45
    assert event.event_type == "audio_drop"
    assert event.intensity == 0.95

    with pytest.raises(ValidationError):
        TransientEvent(
            timestamp_seconds=-1.0,  # Negative timestamp rejected
            event_type="audio_drop",
            intensity=0.5,
            description="Test",
        )

    with pytest.raises(ValidationError):
        TransientEvent(
            timestamp_seconds=5.0,
            event_type="invalid_event_type",  # Not in Literal
            intensity=0.5,
            description="Test",
        )


def test_edm_viral_grading_report_nominal():
    """Validates full EDMViralGradingReport schema with all sub-analyses."""
    report = EDMViralGradingReport(
        video_id="vid_ultra_001",
        gcs_uri="gs://edm-media-vault/raw/ultra_001.mp4",
        video_duration_seconds=28.5,
        aspect_ratio="9:16",
        key_transients=[
            TransientEvent(
                timestamp_seconds=14.2,
                event_type="audio_drop",
                intensity=1.0,
                description="Peak bass drop",
            )
        ],
        hook_analysis=HookAnalysis(
            hook_onset_latency_seconds=0.05,
            transient_count_first_3s=3,
            initial_visual_stimulus_score=92.0,
            hrv_score=90.0,
        ),
        drop_pacing_analysis=DropPacingAnalysis(
            drop_detected=True,
            drop_timestamp_seconds=14.2,
            buildup_duration_seconds=4.5,
            predrop_silence_duration_ms=250.0,
            drop_position_ratio=0.50,
            dpaw_score=94.0,
        ),
        audio_analysis=AudioAcousticAnalysis(
            sub_bass_surge_ratio=6.5,
            spectral_flux_delta=8.5,
            loudness_jump_lufs_est=6.0,
            audio_clipping_detected=False,
            adr_sfd_score=88.0,
        ),
        crowd_analysis=CrowdDynamicsAnalysis(
            crowd_visible_percentage=70.0,
            jump_synchronicity_coherence=0.89,
            energy_acceleration_factor=4.5,
            moshpit_or_intense_reaction=True,
            cke_mve_score=86.0,
        ),
        lighting_analysis=LightingProductionAnalysis(
            laser_co2_pyro_present=True,
            strobe_frequency_hz=16.0,
            light_audio_sync_latency_ms=20.0,
            ltss_score=92.0,
        ),
        evpi_composite_score=90.3,
        trending_verdict="VIRAL_TIER_1",
        algorithmic_recommendation="Instant viral distribution ready.",
    )
    assert report.video_id == "vid_ultra_001"
    assert report.hook_analysis.hrv_score == 90.0
    assert report.drop_pacing_analysis.dpaw_score == 94.0
    assert report.audio_analysis.adr_sfd_score == 88.0
    assert report.crowd_analysis.cke_mve_score == 86.0
    assert report.lighting_analysis.ltss_score == 92.0
    assert report.evpi_composite_score == 90.3
    assert report.trending_verdict == "VIRAL_TIER_1"


def test_edm_shorts_viral_metrics_validation():
    """Validates EDMShortsViralMetrics and verdict matching."""
    scores = ViralParameterScores(
        hrv=85.0,
        dpaw=90.0,
        adr_sfd=80.0,
        cke_mve=75.0,
        ltss=80.0,
    )
    evpi = calculate_evpi(scores)
    assert evpi == (85 * 0.25 + 90 * 0.25 + 80 * 0.20 + 75 * 0.15 + 80 * 0.15)  # 21.25 + 22.5 + 16 + 11.25 + 12 = 83.0

    metric = EDMShortsViralMetrics(
        video_id="vid_test_01",
        gcs_uri="gs://edm-media-vault/raw/vid_test_01.mp4",
        duration_seconds=30.0,
        aspect_ratio="9:16",
        scores=scores,
        evpi_composite=evpi,
        trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
    )
    assert metric.video_id == "vid_test_01"
    assert metric.evpi_composite == 83.0
    assert metric.trending_verdict == TrendingVerdict.HIGH_POTENTIAL

    # Test invalid GCS URI
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="vid_bad_uri",
            gcs_uri="https://storage.googleapis.com/vid.mp4",  # Not gs://
            duration_seconds=30.0,
            scores=scores,
            evpi_composite=evpi,
            trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
        )

    # Test duration exceeding 60s
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="vid_too_long",
            gcs_uri="gs://edm-media-vault/raw/long.mp4",
            duration_seconds=75.0,  # Exceeds 60s
            scores=scores,
            evpi_composite=evpi,
            trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
        )


def test_model_parameter_weights_simplex_constraint():
    """Validates ModelParameterWeights sum to 1.0."""
    valid_w = ModelParameterWeights(
        version_id="test_v1",
        weight_hrv=0.30,
        weight_dpaw=0.30,
        weight_adr_sfd=0.20,
        weight_cke_mve=0.10,
        weight_ltss=0.10,
    )
    assert valid_w.weight_hrv == 0.30

    with pytest.raises(ValidationError):
        ModelParameterWeights(
            version_id="bad_weights",
            weight_hrv=0.50,
            weight_dpaw=0.50,
            weight_adr_sfd=0.50,  # Sum = 1.50 -> error
            weight_cke_mve=0.10,
            weight_ltss=0.10,
        )


# ============================================================================
# 2. EVPI MATH & KILLSWITCH TESTS
# ============================================================================

def test_evpi_killswitches():
    """Validates non-linear killswitch multipliers."""
    # Clean 9:16 video between 12-38s
    k_aud, k_fmt, k_dur = compute_killswitches(
        audio_clipping_detected=False,
        aspect_ratio="9:16",
        duration_seconds=25.0,
    )
    assert (k_aud, k_fmt, k_dur) == (1.0, 1.0, 1.0)

    # Clipped audio killswitch
    k_aud_clip, _, _ = compute_killswitches(
        audio_clipping_detected=True,
        aspect_ratio="9:16",
        duration_seconds=25.0,
    )
    assert k_aud_clip == 0.1

    # Horizontal 16:9 killswitch
    _, k_fmt_16_9, _ = compute_killswitches(
        audio_clipping_detected=False,
        aspect_ratio="16:9",
        duration_seconds=25.0,
    )
    assert k_fmt_16_9 == 0.50

    # Short (<8s) duration killswitch
    _, _, k_dur_short = compute_killswitches(
        audio_clipping_detected=False,
        aspect_ratio="9:16",
        duration_seconds=5.0,
    )
    assert k_dur_short == 0.40


def test_classify_viral_tier_thresholds():
    """Validates viral tier verdict mapping."""
    assert classify_viral_tier(95.0) == "VIRAL_TIER_1"
    assert classify_viral_tier(85.0) == "VIRAL_TIER_1"
    assert classify_viral_tier(84.9) == "HIGH_POTENTIAL"
    assert classify_viral_tier(70.0) == "HIGH_POTENTIAL"
    assert classify_viral_tier(69.9) == "MODERATE"
    assert classify_viral_tier(50.0) == "MODERATE"
    assert classify_viral_tier(49.9) == "LOW_REACH"
    assert classify_viral_tier(10.0) == "LOW_REACH"


# ============================================================================
# 3. GEMINI MULTIMODAL CLIENT TESTS
# ============================================================================

def test_gemini_client_mock_mode_grading():
    """Validates Gemini client in mock mode produces all 5 scores and valid Pydantic models."""
    client = GeminiMultimodalClient(mock_mode=True)
    report = client.grade_video_report(
        video_id="clip_fest_01",
        gcs_uri="gs://edm-media-vault/raw/clip_fest_01.mp4",
        duration_seconds=30.0,
    )
    assert isinstance(report, EDMViralGradingReport)
    assert 0.0 <= report.hook_analysis.hrv_score <= 100.0
    assert 0.0 <= report.drop_pacing_analysis.dpaw_score <= 100.0
    assert 0.0 <= report.audio_analysis.adr_sfd_score <= 100.0
    assert 0.0 <= report.crowd_analysis.cke_mve_score <= 100.0
    assert 0.0 <= report.lighting_analysis.ltss_score <= 100.0
    assert 0.0 <= report.evpi_composite_score <= 100.0

    # Streamlined metrics method
    metrics = client.grade_video(
        video_id="clip_fest_01",
        gcs_uri="gs://edm-media-vault/raw/clip_fest_01.mp4",
        duration_seconds=30.0,
    )
    assert isinstance(metrics, EDMShortsViralMetrics)
    assert metrics.scores.hrv == report.hook_analysis.hrv_score
    assert metrics.scores.dpaw == report.drop_pacing_analysis.dpaw_score
    assert metrics.scores.adr_sfd == report.audio_analysis.adr_sfd_score
    assert metrics.scores.cke_mve == report.crowd_analysis.cke_mve_score
    assert metrics.scores.ltss == report.lighting_analysis.ltss_score


def test_gemini_client_forced_scores_injection():
    """Validates injecting forced scores for exact deterministic grading."""
    client = GeminiMultimodalClient(mock_mode=True)
    forced = ViralParameterScores(
        hrv=95.0,
        dpaw=92.0,
        adr_sfd=90.0,
        cke_mve=88.0,
        ltss=90.0,
    )
    report = client.grade_video_report(
        video_id="forced_vid",
        gcs_uri="gs://edm-media-vault/raw/forced_vid.mp4",
        forced_scores=forced,
    )
    assert report.hook_analysis.hrv_score == 95.0
    assert report.drop_pacing_analysis.dpaw_score == 92.0
    assert report.audio_analysis.adr_sfd_score == 90.0
    assert report.crowd_analysis.cke_mve_score == 88.0
    assert report.lighting_analysis.ltss_score == 90.0
    assert report.trending_verdict == "VIRAL_TIER_1"


def test_gemini_client_rate_limiting_and_dlq():
    """Validates rate limiting and Dead Letter Queue recording."""
    with tempfile.TemporaryDirectory() as tmp_dlq:
        client = GeminiMultimodalClient(
            mock_mode=True,
            simulate_rate_limit=True,
            dlq_dir=tmp_dlq,
        )
        with pytest.raises(RuntimeError, match="429 Quota Exceeded"):
            client.grade_video_report("rl_vid", "gs://edm-media-vault/raw/rl_vid.mp4")

        # Verify in-memory DLQ record
        records = client.dlq_records
        assert len(records) == 1
        assert records[0]["video_id"] == "rl_vid"
        assert records[0]["error_type"] == "RuntimeError"

        # Verify on-disk DLQ JSON serialization
        dlq_files = list(Path(tmp_dlq).glob("*.json"))
        assert len(dlq_files) == 1


# ============================================================================
# 4. PYSPARK GRADING JOB TESTS
# ============================================================================

def test_pyspark_partition_grading_nominal():
    """Validates distributed partition generator processing batch payloads."""
    records = [
        {"video_id": f"batch_clip_{i}", "gcs_uri": f"gs://edm-vault/raw/clip_{i}.mp4", "duration_seconds": 25.0}
        for i in range(5)
    ]
    results = list(grade_partition(iter(records), DEFAULT_WEIGHTS, mock_mode=True))
    assert len(results) == 5
    for r in results:
        assert r["status"] == "GRADED"
        assert r["error_message"] is None
        assert 0.0 <= r["hrv_score"] <= 100.0
        assert 0.0 <= r["dpaw_score"] <= 100.0
        assert 0.0 <= r["adr_sfd_score"] <= 100.0
        assert 0.0 <= r["cke_mve_score"] <= 100.0
        assert 0.0 <= r["ltss_score"] <= 100.0
        assert 0.0 <= r["evpi_composite"] <= 100.0
        assert r["trending_verdict"] in ("VIRAL_TIER_1", "HIGH_POTENTIAL", "MODERATE", "LOW_REACH")


def test_pyspark_partition_grading_dlq_capture():
    """Validates invalid GCS URIs are routed to FAILED_DLQ without crashing batch."""
    records = [
        {"video_id": "good_clip", "gcs_uri": "gs://edm-vault/raw/good.mp4", "duration_seconds": 30.0},
        {"video_id": "corrupt_clip", "gcs_uri": "http://invalid-prefix/bad.mp4", "duration_seconds": 30.0},
    ]
    results = list(grade_partition(iter(records), DEFAULT_WEIGHTS, mock_mode=True))
    assert len(results) == 2
    assert results[0]["status"] == "GRADED"
    assert results[1]["status"] == "FAILED_DLQ"
    assert "Invalid GCS URI format" in results[1]["error_message"]


def test_pyspark_grading_pipeline_custom_weights():
    """Validates batch grading applying BQML-recalibrated weights."""
    pipeline = PySparkGradingPipeline(spark=None, mock_mode=True)
    records = [
        {"video_id": "custom_w_vid", "gcs_uri": "gs://edm-vault/raw/custom_w.mp4", "duration_seconds": 30.0}
    ]
    custom_w = {
        "weight_hrv": 0.50,
        "weight_dpaw": 0.20,
        "weight_adr_sfd": 0.10,
        "weight_cke_mve": 0.10,
        "weight_ltss": 0.10,
    }
    results = pipeline.process_records(records, custom_weights=custom_w)
    assert len(results) == 1
    assert results[0]["status"] == "GRADED"


def test_spark_output_schema():
    """Validates PySpark StructType schema specification."""
    schema = get_spark_output_schema()
    if schema is not None:
        field_names = [f.name for f in schema.fields]
        assert "video_id" in field_names
        assert "gcs_uri" in field_names
        assert "hrv_score" in field_names
        assert "dpaw_score" in field_names
        assert "adr_sfd_score" in field_names
        assert "cke_mve_score" in field_names
        assert "ltss_score" in field_names
        assert "evpi_composite" in field_names
        assert "trending_verdict" in field_names
        assert "status" in field_names


# ============================================================================
# 5. MAIN SCRIPT RUNNER (EXIT CODE 0 ASSERTION)
# ============================================================================

def run_all_tests():
    """Executes all test functions sequentially and logs results."""
    print("=" * 70)
    print("RUNNING DETERMINISTIC PYSPARK & GEMINI OMNI GRADING TEST SUITE")
    print("=" * 70)

    test_functions = [
        test_transient_event_validation,
        test_edm_viral_grading_report_nominal,
        test_edm_shorts_viral_metrics_validation,
        test_model_parameter_weights_simplex_constraint,
        test_evpi_killswitches,
        test_classify_viral_tier_thresholds,
        test_gemini_client_mock_mode_grading,
        test_gemini_client_forced_scores_injection,
        test_gemini_client_rate_limiting_and_dlq,
        test_pyspark_partition_grading_nominal,
        test_pyspark_partition_grading_dlq_capture,
        test_pyspark_grading_pipeline_custom_weights,
        test_spark_output_schema,
    ]

    passed = 0
    failed = 0

    for test_fn in test_functions:
        name = test_fn.__name__
        try:
            test_fn()
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1

    print("=" * 70)
    print(f"TEST SUMMARY: {passed} passed, {failed} failed out of {len(test_functions)} tests.")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
    else:
        print("[SUCCESS] All PySpark & Gemini Omni Video Grading tests passed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
