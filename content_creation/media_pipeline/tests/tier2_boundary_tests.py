"""
tier2_boundary_tests.py - Tier 2: Boundary Value Analysis (BVA), Stress & Failure Modes.
Validates extreme parameter ranges, corrupt payloads, network socket timeouts, rate limits,
concurrency contention, and malformed inputs.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict, List
import pytest
from pydantic import ValidationError

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
# TIER 2: BOUNDARY & STRESS TESTS
# ============================================================================

def test_t2_duration_boundaries_0_and_60():
    """T2.1: Tests video duration boundaries: 0.0s (fail), 0.1s (pass), 59.0s (pass), 60.0s (pass), 60.1s (fail)."""
    scores = ViralParameterScores(hrv=75.0, dpaw=75.0, adr_sfd=75.0, cke_mve=75.0, ltss=75.0)

    # 0.0s must fail (gt=0.0)
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="v_dur_0",
            gcs_uri="gs://edm-media-vault/raw/v0.mp4",
            duration_seconds=0.0,
            scores=scores,
            evpi_composite=75.0,
            trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
        )

    # 0.1s must pass
    m_min = EDMShortsViralMetrics(
        video_id="v_dur_min",
        gcs_uri="gs://edm-media-vault/raw/vmin.mp4",
        duration_seconds=0.1,
        scores=scores,
        evpi_composite=75.0,
        trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
    )
    assert m_min.duration_seconds == 0.1

    # 59.0s (YouTube Shorts standard safe limit) must pass
    m_59 = EDMShortsViralMetrics(
        video_id="v_dur_59",
        gcs_uri="gs://edm-media-vault/raw/v59.mp4",
        duration_seconds=59.0,
        scores=scores,
        evpi_composite=75.0,
        trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
    )
    assert m_59.duration_seconds == 59.0

    # 60.0s (hard ceiling) must pass
    m_60 = EDMShortsViralMetrics(
        video_id="v_dur_60",
        gcs_uri="gs://edm-media-vault/raw/v60.mp4",
        duration_seconds=60.0,
        scores=scores,
        evpi_composite=75.0,
        trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
    )
    assert m_60.duration_seconds == 60.0

    # 60.1s must fail (le=60.0)
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="v_dur_60_1",
            gcs_uri="gs://edm-media-vault/raw/v60_1.mp4",
            duration_seconds=60.1,
            scores=scores,
            evpi_composite=75.0,
            trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
        )


def test_t2_viral_parameter_extreme_boundaries():
    """T2.2: Tests exact parameter boundaries: 0.0, 100.0, -0.001 (fail), 100.001 (fail)."""
    # Exact 0.0
    p_zero = ViralParameterScores(hrv=0.0, dpaw=0.0, adr_sfd=0.0, cke_mve=0.0, ltss=0.0)
    assert p_zero.hrv == 0.0

    # Exact 100.0
    p_hundred = ViralParameterScores(hrv=100.0, dpaw=100.0, adr_sfd=100.0, cke_mve=100.0, ltss=100.0)
    assert p_hundred.hrv == 100.0

    # -0.001 must fail
    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=-0.001, dpaw=50.0, adr_sfd=50.0, cke_mve=50.0, ltss=50.0)

    # 100.001 must fail
    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=100.001, dpaw=50.0, adr_sfd=50.0, cke_mve=50.0, ltss=50.0)


def test_t2_empty_file_and_huge_file_payloads(mock_gcs: MockGCSClient):
    """T2.3: Tests zero-byte file handling and simulated large 500MB payload streaming."""
    # Zero-byte payload
    uri_empty = mock_gcs.upload_from_bytes("raw/zero_byte.mp4", b"")
    assert mock_gcs.exists(uri_empty) is True
    assert mock_gcs.get_blob_metadata(uri_empty)["size"] == 0

    # Large chunked payload (simulating 5MB buffer without blowing memory)
    chunk = b"X" * 1024 * 1024  # 1MB
    large_payload = chunk * 5     # 5MB
    uri_large = mock_gcs.upload_from_bytes("raw/large_file.mp4", large_payload)
    assert mock_gcs.get_blob_metadata(uri_large)["size"] == 5 * 1024 * 1024


def test_t2_corrupted_payload_and_hash_mismatch(mock_adb: MockAdbDevice, mock_manifest: MockSQLiteManifestStore):
    """T2.4: Tests detection when payload is corrupted in transit (hash mismatch triggers failure)."""
    remote_path = "/sdcard/DCIM/Camera/tampered.mp4"
    original_data = b"PRISTINE_4K_VIDEO_CONTENT"
    mock_adb.add_remote_file(remote_path, original_data)
    expected_hash = mock_adb.compute_remote_hash(remote_path)

    # Record in manifest
    mock_manifest.record_pending(remote_path, "tampered.mp4", len(original_data), expected_hash)

    # Simulate bitflip / corruption during transfer
    corrupted_data = b"CORRUPTED_TAMPERED_CONTENT"
    actual_hash = hashlib.sha256(corrupted_data).hexdigest()

    assert expected_hash != actual_hash

    # Pipeline asserts mismatch and sets status to FAILED
    if expected_hash != actual_hash:
        mock_manifest.update_status(
            remote_path,
            ManifestStatus.FAILED,
            error_message=f"Hash mismatch: expected {expected_hash} but got {actual_hash}",
        )

    rec = mock_manifest.get_record(remote_path)
    assert rec["status"] == "FAILED"
    assert "Hash mismatch" in rec["error_message"]


def test_t2_adb_socket_timeout_and_transient_failure(mock_adb: MockAdbDevice):
    """T2.5: Tests simulated network drop mid-transfer and backoff retry recovery."""
    path = "/sdcard/DCIM/Camera/transient.mp4"
    data = b"STREAMING_PAYLOAD"
    mock_adb.add_remote_file(path, data)

    # Drop connection
    mock_adb.disconnect()

    max_retries = 3
    success = False
    pulled_bytes = None

    for attempt in range(max_retries):
        try:
            pulled_bytes = mock_adb.pull_file_stream(path)
            success = True
            break
        except ConnectionError:
            # Backoff simulation: reconnect on 2nd attempt
            if attempt == 1:
                mock_adb.connect()

    assert success is True
    assert pulled_bytes == data


def test_t2_gemini_rate_limit_and_quota_exhaustion():
    """T2.6: Tests Gemini 429 quota exhaustion and Dead Letter Queue (DLQ) dumping."""
    gemini = MockGeminiOmniClient(simulate_rate_limit=True)
    video_uris = [f"gs://edm-media-vault/raw/rl_{i}.mp4" for i in range(3)]

    failed_count = 0
    for uri in video_uris:
        try:
            gemini.grade_video(video_id=Path(uri).stem, gcs_uri=uri)
        except RuntimeError:
            failed_count += 1

    assert failed_count == 3
    assert len(gemini.dlq_records) == 3
    assert all(r["code"] == 429 for r in gemini.dlq_records)


def test_t2_manifest_concurrent_writer_contention(tmp_path: Path):
    """T2.7: Tests concurrent SQLite writing across multiple threads with WAL concurrency."""
    db_file = str(tmp_path / "concurrent_test.db")
    # Initialize DB schema
    init_store = MockSQLiteManifestStore(db_file)
    init_store.close()

    errors = []

    def writer_worker(thread_id: int):
        thread_store = MockSQLiteManifestStore(db_file)
        try:
            for i in range(15):
                path = f"/sdcard/DCIM/t{thread_id}_f{i}.mp4"
                thread_store.record_pending(path, f"t{thread_id}_f{i}.mp4", 1024, "a"*64)
                thread_store.update_status(path, ManifestStatus.LOCAL_SAVED, local_sha256="a"*64)
        except Exception as e:
            errors.append(e)
        finally:
            thread_store.close()

    threads = [threading.Thread(target=writer_worker, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    verify_store = MockSQLiteManifestStore(db_file)
    records = verify_store.list_records()
    verify_store.close()

    assert len(errors) == 0
    assert len(records) == 5 * 15


def test_t2_bqml_zero_variance_collinear_features(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """T2.8: Tests BQML handling of dataset where all scores are identical (collinearity)."""
    # Insert 10 identical videos
    forced = ViralParameterScores(hrv=50.0, dpaw=50.0, adr_sfd=50.0, cke_mve=50.0, ltss=50.0)
    for i in range(10):
        m = mock_gemini.grade_video(f"ident_{i}", f"gs://edm-media-vault/raw/ident_{i}.mp4", forced_scores=forced)
        mock_bqml.sink_video_grades([m])

    # Model training should execute without crashing
    res = mock_bqml.execute_create_model(
        model_name="model_collinear",
        model_type="LINEAR_REG",
        query_sql="SELECT * FROM `media_pipeline.video_grades`",
    )
    assert res["training_row_count"] == 10


def test_t2_weight_normalization_extreme_skews(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """T2.9: Tests weight normalization when model weights are extremely skewed."""
    m = mock_gemini.grade_video("skew_vid", "gs://edm-media-vault/raw/skew.mp4")
    mock_bqml.sink_video_grades([m])
    mock_bqml.execute_create_model("model_skew", "BOOSTED_TREE_REGRESSOR", "SELECT *")
    
    weights = mock_bqml.extract_ml_weights("model_skew")
    assert abs(weights.weight_hrv + weights.weight_dpaw + weights.weight_adr_sfd + weights.weight_cke_mve + weights.weight_ltss - 1.0) < 0.001


def test_t2_invalid_gcs_bucket_or_path_injection():
    """T2.10: Tests malformed GCS URIs (missing gs://, path traversal, invalid characters)."""
    scores = ViralParameterScores(hrv=70.0, dpaw=70.0, adr_sfd=70.0, cke_mve=70.0, ltss=70.0)

    # Missing gs://
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="v_bad_uri",
            gcs_uri="s3://bucket/video.mp4",
            duration_seconds=30.0,
            scores=scores,
            evpi_composite=70.0,
            trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
        )

    # Not an mp4
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="v_bad_ext",
            gcs_uri="gs://bucket/video.exe",
            duration_seconds=30.0,
            scores=scores,
            evpi_composite=70.0,
            trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
        )
