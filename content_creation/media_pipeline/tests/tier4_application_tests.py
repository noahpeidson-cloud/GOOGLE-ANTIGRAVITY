"""
tier4_application_tests.py - Tier 4: Real-World End-to-End Workflow Scenarios.
Executes complete full-system simulations of the Media Ingestion & Viral Grading Pipeline:
Device -> Wireless Ingestion -> Cloud Storage -> PySpark Grading -> BigQuery Sink -> BQML Training -> Dynamic Feedback Loop.
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
# TIER 4: APPLICATION WORKFLOW TESTS
# ============================================================================

def test_t4_full_golden_path_pipeline_lifecycle(
    mock_manifest: MockSQLiteManifestStore,
    tmp_path: Path,
):
    """
    T4.1: Golden Path End-to-End Pipeline Execution.
    Stages:
    1. Android 4K video recording on mobile device.
    2. Wireless extraction over ADB with zero compression.
    3. SHA-256 verification and atomic staging in local storage.
    4. Resumable streaming upload to Google Cloud Storage.
    5. Dataproc PySpark batch job with Gemini Multimodal Video AI grading.
    6. Relational sink to BigQuery video_grades table.
    7. Post-publishing telemetry simulation (Viewed vs Swiped Away, Average Percentage Viewed).
    8. BQML Boosted Tree model training and ML.WEIGHTS extraction.
    9. Parameter weight recalibration and feedback into the active scoring pipeline.
    """
    # 1. Setup Mock System Components
    adb = MockAdbDevice(serial="192.168.1.150:5555")
    gcs = MockGCSClient(bucket_name="edm-media-vault")
    gemini = MockGeminiOmniClient()
    spark = MockPySparkGradingEngine(gemini_client=gemini, gcs_client=gcs)
    bqml = MockBigQueryMLEngine()

    # 2. Device Media Preparation
    raw_video_data = b"\x00\x00\x00\x1cftypisom" + b"_RAW_4K_60FPS_CONCERT_DATA_" * 10000
    remote_path = "/sdcard/DCIM/Camera/20260824_Tomorrowland_Excision_Drop.mp4"
    device_hash = adb.add_remote_file(remote_path, raw_video_data)

    # 3. Discovery & Manifest Recording
    media_list = adb.list_camera_media()
    assert len(media_list) == 1
    file_info = media_list[0]
    
    mock_manifest.record_pending(remote_path, file_info["name"], file_info["size"], device_hash)
    assert mock_manifest.get_record(remote_path)["status"] == "PENDING"

    # 4. Zero-Compression Ingestion & Atomic Local Staging
    mock_manifest.update_status(remote_path, ManifestStatus.HASHING)
    pulled_stream = adb.pull_file_stream(remote_path)
    local_hash = hashlib.sha256(pulled_stream).hexdigest()
    assert local_hash == device_hash  # Zero Bit-Loss Guarantee

    local_staged_file = tmp_path / "20260824_Tomorrowland_Excision_Drop.mp4"
    with open(local_staged_file, "wb") as f:
        f.write(pulled_stream)

    mock_manifest.update_status(remote_path, ManifestStatus.LOCAL_SAVED, local_sha256=local_hash)
    assert mock_manifest.get_record(remote_path)["status"] == "LOCAL_SAVED"

    # 5. Streaming GCS Upload with Custom Metadata
    mock_manifest.update_status(remote_path, ManifestStatus.UPLOADING)
    blob_name = f"raw/{Path(remote_path).name}"
    gcs_uri = gcs.upload_from_file(
        blob_name,
        str(local_staged_file),
        metadata={"sha256": local_hash, "device_serial": adb.serial},
    )
    assert gcs.exists(gcs_uri)
    mock_manifest.update_status(remote_path, ManifestStatus.GCS_VERIFIED, gcs_uri=gcs_uri)

    # 6. PySpark Batch Video Grading with Gemini Omni
    spark_batch = [{"video_id": "tomorrowland_excision_01", "gcs_uri": gcs_uri, "duration_seconds": 38.0}]
    graded_metrics = spark.execute_batch_job(spark_batch)
    assert len(graded_metrics) == 1
    metric = graded_metrics[0]
    assert metric.video_id == "tomorrowland_excision_01"
    assert metric.scores.hrv > 0.0
    assert 0.0 <= metric.evpi_composite <= 100.0

    # 7. BigQuery Relational Sink
    sink_count = bqml.sink_video_grades(graded_metrics)
    assert sink_count == 1
    assert len(bqml.tables["media_pipeline.video_grades"]) == 1

    # 8. Post-Publishing Performance Telemetry
    bqml.update_post_telemetry(
        video_id="tomorrowland_excision_01",
        vvsa_rate=0.88,
        apv=1.24,
        viral_status=1,
    )

    # 9. BigQuery ML Model Training & Weight Recalibration
    train_res = bqml.execute_create_model(
        model_name="edm_viral_boosted_tree_v1",
        model_type="BOOSTED_TREE_REGRESSOR",
        query_sql="SELECT hrv_score, dpaw_score, adr_sfd_score, cke_mve_score, ltss_score, actual_vvsa_rate FROM `media_pipeline.video_grades`",
    )
    assert train_res["training_row_count"] == 1

    new_active_weights = bqml.extract_ml_weights("edm_viral_boosted_tree_v1")
    assert new_active_weights.is_active is True
    assert bqml.get_active_weights().version_id == new_active_weights.version_id

    # 10. Update Manifest status to GRADED
    mock_manifest.update_status(remote_path, ManifestStatus.GRADED)
    final_record = mock_manifest.get_record(remote_path)
    assert final_record["status"] == "GRADED"


def test_t4_multi_asset_concurrent_batch_workflow(tmp_path: Path):
    """
    T4.2: Concurrent Multi-Asset Batch Workflow.
    Ingests 8 concert clips from various festivals, executes parallel hashing,
    streaming GCS uploads, distributed PySpark grading, and BigQuery analytics aggregation.
    """
    adb = MockAdbDevice()
    gcs = MockGCSClient()
    gemini = MockGeminiOmniClient()
    spark = MockPySparkGradingEngine(gemini_client=gemini, gcs_client=gcs)
    bqml = MockBigQueryMLEngine()

    manifest_db = str(tmp_path / "batch_manifest.db")
    manifest = MockSQLiteManifestStore(manifest_db)

    festivals = [
        ("EDCLasVegas_Illenium", 25.0),
        ("UltraMiami_Hardwell", 40.0),
        ("Tomorrowland_Armin", 30.0),
        ("ElectricForest_Odesza", 35.0),
        ("LostLands_Excision", 22.0),
        ("Coachella_Raye", 45.0),
        ("Creamfields_Tiesto", 30.0),
        ("Defqon1_Headhunterz", 28.0),
    ]

    spark_inputs = []

    for name, dur in festivals:
        remote_file = f"/sdcard/DCIM/Camera/{name}.mp4"
        raw_bytes = f"RAW_DATA_FOR_{name}".encode() * 5000
        dev_hash = adb.add_remote_file(remote_file, raw_bytes)

        # Ingestion & Manifest
        manifest.record_pending(remote_file, f"{name}.mp4", len(raw_bytes), dev_hash)
        pulled = adb.pull_file_stream(remote_file)
        manifest.update_status(remote_file, ManifestStatus.LOCAL_SAVED, local_sha256=dev_hash)

        # GCS Upload
        uri = gcs.upload_from_bytes(f"raw/{name}.mp4", pulled, metadata={"sha256": dev_hash})
        manifest.update_status(remote_file, ManifestStatus.GCS_VERIFIED, gcs_uri=uri)

        spark_inputs.append({"video_id": name, "gcs_uri": uri, "duration_seconds": dur})

    # Distributed Batch Grading
    graded_results = spark.execute_batch_job(spark_inputs)
    assert len(graded_results) == 8

    # BigQuery Sink
    bqml.sink_video_grades(graded_results)
    assert len(bqml.tables["media_pipeline.video_grades"]) == 8

    # Verify Verdict Distribution
    verdicts = [r.trending_verdict for r in graded_results]
    assert len(verdicts) == 8
    assert all(isinstance(v, TrendingVerdict) for v in verdicts)

    manifest.close()


def test_t4_disaster_recovery_interrupted_transfer_and_idempotency(tmp_path: Path):
    """
    T4.3: Disaster Recovery, Resumption, and Idempotency.
    Simulates network drop during ADB stream, recovery on reconnect, and verifies
    that duplicate ingestion does not create duplicate entries or corrupt GCS state.
    """
    adb = MockAdbDevice()
    gcs = MockGCSClient()
    manifest_file = str(tmp_path / "recovery_manifest.db")
    manifest = MockSQLiteManifestStore(manifest_file)

    remote_path = "/sdcard/DCIM/Camera/resilient_clip.mp4"
    data = b"RESILIENT_STREAM_BYTES" * 8000
    h = adb.add_remote_file(remote_path, data)

    # 1. Record pending
    manifest.record_pending(remote_path, "resilient_clip.mp4", len(data), h)

    # 2. Simulate socket drop during transfer
    adb.disconnect()
    with pytest.raises(ConnectionError):
        adb.pull_file_stream(remote_path)

    # 3. Reconnect and complete transfer
    adb.connect()
    pulled_data = adb.pull_file_stream(remote_path)
    assert hashlib.sha256(pulled_data).hexdigest() == h

    manifest.update_status(remote_path, ManifestStatus.LOCAL_SAVED, local_sha256=h)
    uri = gcs.upload_from_bytes("raw/resilient_clip.mp4", pulled_data)
    manifest.update_status(remote_path, ManifestStatus.GCS_VERIFIED, gcs_uri=uri)

    # 4. Idempotency Check: Second ingestion attempt for the same file
    manifest.record_pending(remote_path, "resilient_clip.mp4", len(data), h)
    records = manifest.list_records()
    # Unique constraint ensures exactly 1 record exists for remote_path
    matching = [r for r in records if r["file_path"] == remote_path]
    assert len(matching) == 1

    manifest.close()


def test_t4_continuous_learning_multi_generation_recalibration():
    """
    T4.4: Continuous Learning Multi-Generation Recalibration Loop.
    Validates adaptive model retraining across two generations of video ingestion
    and verifies active weight progression and history tracking.
    """
    gcs = MockGCSClient()
    gemini = MockGeminiOmniClient()
    spark = MockPySparkGradingEngine(gemini_client=gemini, gcs_client=gcs)
    bqml = MockBigQueryMLEngine()

    # --- Generation 1 ---
    gen1_inputs = []
    for i in range(4):
        u = gcs.upload_from_bytes(f"raw/gen1_{i}.mp4", f"GEN1_DATA_{i}".encode() * 1000)
        gen1_inputs.append({"video_id": f"gen1_{i}", "gcs_uri": u, "duration_seconds": 30.0})

    # Grade with initial baseline
    baseline_w = bqml.get_active_weights()
    m_gen1 = spark.execute_batch_job(gen1_inputs, weights=baseline_w)
    bqml.sink_video_grades(m_gen1)

    # Add Gen 1 telemetry & train
    for m in m_gen1:
        bqml.update_post_telemetry(m.video_id, vvsa_rate=0.80, apv=1.10, viral_status=1)

    bqml.execute_create_model("model_gen1", "BOOSTED_TREE_REGRESSOR", "SELECT *")
    weights_gen1 = bqml.extract_ml_weights("model_gen1")

    assert bqml.get_active_weights().version_id == weights_gen1.version_id

    # --- Generation 2 ---
    gen2_inputs = []
    for i in range(4):
        u = gcs.upload_from_bytes(f"raw/gen2_{i}.mp4", f"GEN2_DATA_{i}".encode() * 1000)
        gen2_inputs.append({"video_id": f"gen2_{i}", "gcs_uri": u, "duration_seconds": 30.0})

    # Grade with Gen 1 learned weights
    m_gen2 = spark.execute_batch_job(gen2_inputs, weights=weights_gen1)
    bqml.sink_video_grades(m_gen2)

    for m in m_gen2:
        bqml.update_post_telemetry(m.video_id, vvsa_rate=0.92, apv=1.40, viral_status=1)

    bqml.execute_create_model("model_gen2", "BOOSTED_TREE_REGRESSOR", "SELECT *")
    weights_gen2 = bqml.extract_ml_weights("model_gen2")

    assert bqml.get_active_weights().version_id == weights_gen2.version_id
    assert weights_gen2.version_id != weights_gen1.version_id

    # Verify weight history table contains 3 versions (baseline + gen1 + gen2)
    history = bqml.tables["media_pipeline.model_parameter_weights"]
    assert len(history) == 3
    active_rows = [r for r in history if r["is_active"]]
    assert len(active_rows) == 1
    assert active_rows[0]["version_id"] == weights_gen2.version_id


def test_t4_high_volume_quota_exhaustion_recovery_lifecycle():
    """
    T4.5: High-Volume Rate Limit & Quota Exhaustion Recovery.
    Simulates pipeline behavior under Gemini API 429 quota exhaustion,
    verifies Dead Letter Queue recording, and confirms recovery when rate limit lifts.
    """
    gcs = MockGCSClient()
    gemini = MockGeminiOmniClient(simulate_rate_limit=True)
    spark = MockPySparkGradingEngine(gemini_client=gemini, gcs_client=gcs)
    bqml = MockBigQueryMLEngine()

    u = gcs.upload_from_bytes("raw/quota_clip.mp4", b"QUOTA_TEST_PAYLOAD")

    # Ingestion during quota exhaustion -> fails to DLQ
    with pytest.raises(RuntimeError):
        spark.execute_batch_job([{"video_id": "quota_vid", "gcs_uri": u}])

    assert len(gemini.dlq_records) == 1
    assert gemini.dlq_records[0]["video_id"] == "quota_vid"

    # Quota recovered
    gemini.simulate_rate_limit = False
    recovery_results = spark.execute_batch_job([{"video_id": "quota_vid", "gcs_uri": u}])
    assert len(recovery_results) == 1

    # Sunk to BigQuery successfully
    bqml.sink_video_grades(recovery_results)
    assert len(bqml.tables["media_pipeline.video_grades"]) == 1
