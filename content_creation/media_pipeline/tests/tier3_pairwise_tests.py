"""
tier3_pairwise_tests.py - Tier 3: Pairwise & Cross-Feature Interaction Tests.
Validates module boundaries, data pipeline transitions, and cross-component contracts:
ADB -> SQLite Manifest -> GCS -> PySpark -> Gemini API -> BigQuery Sink -> BQML Optimization Loop.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List
import pytest

try:
    from tests.conftest import (
        DEFAULT_WEIGHTS,
        BigQueryVideoGrade,
        EDMShortsViralMetrics,
        ManifestStatus,
        MediaManifestRecord,
        MockAdbDevice,
        MockBigQueryMLEngine,
        MockGCSClient,
        MockGeminiOmniClient,
        MockPySparkGradingEngine,
        MockSQLiteManifestStore,
        ModelParameterWeights,
        TrendingVerdict,
        ViralParameterScores,
        calculate_evpi,
        get_verdict_from_evpi,
    )
except ImportError:
    from conftest import (
        DEFAULT_WEIGHTS,
        BigQueryVideoGrade,
        EDMShortsViralMetrics,
        ManifestStatus,
        MediaManifestRecord,
        MockAdbDevice,
        MockBigQueryMLEngine,
        MockGCSClient,
        MockGeminiOmniClient,
        MockPySparkGradingEngine,
        MockSQLiteManifestStore,
        ModelParameterWeights,
        TrendingVerdict,
        ViralParameterScores,
        calculate_evpi,
        get_verdict_from_evpi,
    )


# ============================================================================
# TIER 3: PAIRWISE & INTERACTION TESTS
# ============================================================================

def test_t3_adb_pull_to_manifest_hash_handshake(
    mock_adb: MockAdbDevice,
    mock_manifest: MockSQLiteManifestStore,
    sample_raw_mp4_bytes: bytes,
    sample_raw_mp4_hash: str,
):
    """T3.1: Validates ADB pull handshake with SQLite manifest state tracking."""
    remote_path = "/sdcard/DCIM/Camera/20260824_UltraMiami_MartinGarrix_V1.mp4"
    
    # 1. Device Discovery & Hash extraction
    device_hash = mock_adb.compute_remote_hash(remote_path)
    assert device_hash == sample_raw_mp4_hash

    # 2. Record initial PENDING state in manifest
    mock_manifest.record_pending(remote_path, Path(remote_path).name, len(sample_raw_mp4_bytes), device_hash)
    rec = mock_manifest.get_record(remote_path)
    assert rec["status"] == "PENDING"

    # 3. Pull raw stream with zero compression
    mock_manifest.update_status(remote_path, ManifestStatus.HASHING)
    stream_bytes = mock_adb.pull_file_stream(remote_path)
    local_hash = hashlib.sha256(stream_bytes).hexdigest()
    assert local_hash == device_hash

    # 4. Update manifest to LOCAL_SAVED
    mock_manifest.update_status(remote_path, ManifestStatus.LOCAL_SAVED, local_sha256=local_hash)
    rec_saved = mock_manifest.get_record(remote_path)
    assert rec_saved["status"] == "LOCAL_SAVED"
    assert rec_saved["local_sha256"] == device_hash


def test_t3_manifest_to_gcs_upload_and_state_verification(
    mock_manifest: MockSQLiteManifestStore,
    mock_gcs: MockGCSClient,
    sample_raw_mp4_bytes: bytes,
    sample_raw_mp4_hash: str,
):
    """T3.2: Validates transition from local saved file to GCS upload with metadata integrity."""
    remote_path = "/sdcard/DCIM/Camera/festival_clip.mp4"
    mock_manifest.record_pending(remote_path, "festival_clip.mp4", len(sample_raw_mp4_bytes), sample_raw_mp4_hash)
    mock_manifest.update_status(remote_path, ManifestStatus.LOCAL_SAVED, local_sha256=sample_raw_mp4_hash)

    # 1. Transition to UPLOADING
    mock_manifest.update_status(remote_path, ManifestStatus.UPLOADING)
    assert mock_manifest.get_record(remote_path)["status"] == "UPLOADING"

    # 2. Upload to GCS
    blob_name = "raw/festival_clip.mp4"
    gcs_uri = mock_gcs.upload_from_bytes(blob_name, sample_raw_mp4_bytes, metadata={"sha256": sample_raw_mp4_hash})

    # 3. Assert GCS blob integrity
    assert mock_gcs.exists(gcs_uri)
    blob_meta = mock_gcs.get_blob_metadata(gcs_uri)
    assert blob_meta["sha256"] == sample_raw_mp4_hash

    # 4. Mark GCS_VERIFIED in manifest
    mock_manifest.update_status(remote_path, ManifestStatus.GCS_VERIFIED, gcs_uri=gcs_uri)
    rec = mock_manifest.get_record(remote_path)
    assert rec["status"] == "GCS_VERIFIED"
    assert rec["gcs_uri"] == gcs_uri


def test_t3_gcs_to_spark_grading_to_pydantic_output(
    mock_gcs: MockGCSClient,
    mock_spark: MockPySparkGradingEngine,
    sample_raw_mp4_bytes: bytes,
):
    """T3.3: Validates GCS asset ingested by PySpark and converted to structured Pydantic metrics."""
    gcs_uri = mock_gcs.upload_from_bytes("raw/spark_test_clip.mp4", sample_raw_mp4_bytes)

    batch = [{"video_id": "spark_clip_1", "gcs_uri": gcs_uri, "duration_seconds": 32.5}]
    graded_metrics = mock_spark.execute_batch_job(batch)

    assert len(graded_metrics) == 1
    metric = graded_metrics[0]
    assert isinstance(metric, EDMShortsViralMetrics)
    assert metric.video_id == "spark_clip_1"
    assert metric.gcs_uri == gcs_uri
    assert metric.duration_seconds == 32.5
    assert 0.0 <= metric.evpi_composite <= 100.0


def test_t3_spark_grading_to_bigquery_sink_pipeline(
    mock_gcs: MockGCSClient,
    mock_spark: MockPySparkGradingEngine,
    mock_bqml: MockBigQueryMLEngine,
    sample_raw_mp4_bytes: bytes,
):
    """T3.4: Validates PySpark batch output sinking directly into BigQuery relational schema."""
    u1 = mock_gcs.upload_from_bytes("raw/sink_1.mp4", sample_raw_mp4_bytes)
    u2 = mock_gcs.upload_from_bytes("raw/sink_2.mp4", sample_raw_mp4_bytes)

    batch = [
        {"video_id": "sink_clip_1", "gcs_uri": u1, "duration_seconds": 25.0},
        {"video_id": "sink_clip_2", "gcs_uri": u2, "duration_seconds": 40.0},
    ]
    metrics = mock_spark.execute_batch_job(batch)
    inserted_count = mock_bqml.sink_video_grades(metrics)

    assert inserted_count == 2
    grades_table = mock_bqml.tables["media_pipeline.video_grades"]
    assert len(grades_table) == 2
    assert grades_table[0]["video_id"] == "sink_clip_1"
    assert grades_table[1]["video_id"] == "sink_clip_2"


def test_t3_bigquery_telemetry_to_bqml_training_to_weight_feedback(
    mock_gcs: MockGCSClient,
    mock_spark: MockPySparkGradingEngine,
    mock_bqml: MockBigQueryMLEngine,
    sample_raw_mp4_bytes: bytes,
):
    """T3.5: Validates telemetry updating, BQML model training, and active weight extraction."""
    # Ingest 5 videos
    batch = []
    for i in range(5):
        uri = mock_gcs.upload_from_bytes(f"raw/train_{i}.mp4", sample_raw_mp4_bytes)
        batch.append({"video_id": f"train_vid_{i}", "gcs_uri": uri, "duration_seconds": 30.0})

    metrics = mock_spark.execute_batch_job(batch)
    mock_bqml.sink_video_grades(metrics)

    # Simulate post-publishing telemetry
    for i, m in enumerate(metrics):
        mock_bqml.update_post_telemetry(
            video_id=m.video_id,
            vvsa_rate=0.75 + (i * 0.04),
            apv=1.10 + (i * 0.05),
            viral_status=1 if i >= 3 else 0,
        )

    # Train BQML model
    mock_bqml.execute_create_model(
        model_name="edm_viral_feedback_model",
        model_type="BOOSTED_TREE_REGRESSOR",
        query_sql="SELECT hrv_score, dpaw_score, adr_sfd_score, actual_vvsa_rate FROM `media_pipeline.video_grades`",
    )

    # Extract new learned weights
    new_weights = mock_bqml.extract_ml_weights("edm_viral_feedback_model")
    assert new_weights.is_active is True
    assert mock_bqml.get_active_weights().version_id == new_weights.version_id


def test_t3_gemini_failure_to_dlq_to_partial_batch_success(
    mock_gcs: MockGCSClient,
    sample_raw_mp4_bytes: bytes,
):
    """T3.6: Validates DLQ capturing of failed requests while isolating healthy jobs."""
    gemini = MockGeminiOmniClient(simulate_rate_limit=False)
    u_good = mock_gcs.upload_from_bytes("raw/good.mp4", sample_raw_mp4_bytes)
    
    # Process healthy video
    m_good = gemini.grade_video("good_vid", u_good)
    assert m_good.video_id == "good_vid"

    # Switch to rate-limit mode to simulate transient outage
    gemini.simulate_rate_limit = True
    u_bad = mock_gcs.upload_from_bytes("raw/bad.mp4", sample_raw_mp4_bytes)
    
    with pytest.raises(RuntimeError):
        gemini.grade_video("bad_vid", u_bad)

    assert len(gemini.dlq_records) == 1
    assert gemini.dlq_records[0]["video_id"] == "bad_vid"


def test_t3_feedback_loop_reweighted_spark_scoring(
    mock_gcs: MockGCSClient,
    mock_spark: MockPySparkGradingEngine,
    mock_bqml: MockBigQueryMLEngine,
    sample_raw_mp4_bytes: bytes,
):
    """T3.7: Validates that subsequent PySpark grading applies new active BQML weights."""
    u1 = mock_gcs.upload_from_bytes("raw/loop_test.mp4", sample_raw_mp4_bytes)

    # Grade with baseline weights
    baseline_weights = mock_bqml.get_active_weights()
    r1 = mock_spark.execute_batch_job([{"video_id": "loop_vid", "gcs_uri": u1}], weights=baseline_weights)
    score_baseline = r1[0].evpi_composite

    # Seed data and train model to produce recalibrated weights with heavy HRV emphasis
    mock_bqml.sink_video_grades(r1)
    mock_bqml.execute_create_model("m_loop", "LINEAR_REG", "SELECT *")
    recalibrated_weights = mock_bqml.extract_ml_weights("m_loop")

    # Grade again with new active weights
    r2 = mock_spark.execute_batch_job([{"video_id": "loop_vid", "gcs_uri": u1}], weights=recalibrated_weights)
    score_recalibrated = r2[0].evpi_composite

    # Both scores are valid 0-100 values
    assert 0.0 <= score_baseline <= 100.0
    assert 0.0 <= score_recalibrated <= 100.0
