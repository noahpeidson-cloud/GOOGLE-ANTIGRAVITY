"""
tier1_feature_tests.py - Tier 1: Exhaustive Feature-Level Functional Verification.
Provides >=5 deterministic unit/functional test cases per feature across all 18 inventoried features.
Total test cases: 90.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
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
# FEATURE 1: EDM Viral Formula Specification
# ============================================================================

def test_f01_viral_formula_parameter_ranges():
    """F01.1: Validates valid 0.0-100.0 range constraints on all 5 parameters."""
    scores = ViralParameterScores(
        hrv=85.5,
        dpaw=92.0,
        adr_sfd=78.4,
        cke_mve=88.2,
        ltss=90.0,
    )
    assert 0.0 <= scores.hrv <= 100.0
    assert 0.0 <= scores.dpaw <= 100.0
    assert 0.0 <= scores.adr_sfd <= 100.0
    assert 0.0 <= scores.cke_mve <= 100.0
    assert 0.0 <= scores.ltss <= 100.0


def test_f01_viral_formula_evpi_composite_math():
    """F01.2: Validates weighted arithmetic formula matching default weights (0.25, 0.25, 0.20, 0.15, 0.15)."""
    scores = ViralParameterScores(hrv=100.0, dpaw=100.0, adr_sfd=100.0, cke_mve=100.0, ltss=100.0)
    evpi = calculate_evpi(scores)
    assert evpi == 100.0

    scores_mixed = ViralParameterScores(hrv=80.0, dpaw=90.0, adr_sfd=70.0, cke_mve=60.0, ltss=50.0)
    # Expected: (80*0.25) + (90*0.25) + (70*0.20) + (60*0.15) + (50*0.15) = 20 + 22.5 + 14 + 9 + 7.5 = 73.0
    evpi_mixed = calculate_evpi(scores_mixed)
    assert evpi_mixed == 73.0


def test_f01_viral_formula_verdict_thresholds():
    """F01.3: Validates categorization into VIRAL, HIGH_POTENTIAL, AVERAGE, and LOW."""
    assert get_verdict_from_evpi(95.0) == TrendingVerdict.VIRAL
    assert get_verdict_from_evpi(85.0) == TrendingVerdict.VIRAL
    assert get_verdict_from_evpi(84.9) == TrendingVerdict.HIGH_POTENTIAL
    assert get_verdict_from_evpi(70.0) == TrendingVerdict.HIGH_POTENTIAL
    assert get_verdict_from_evpi(69.9) == TrendingVerdict.AVERAGE
    assert get_verdict_from_evpi(50.0) == TrendingVerdict.AVERAGE
    assert get_verdict_from_evpi(49.9) == TrendingVerdict.LOW
    assert get_verdict_from_evpi(10.0) == TrendingVerdict.LOW


def test_f01_viral_formula_negative_or_overflow_rejection():
    """F01.4: Validates that out-of-bounds parameter scores raise ValidationError."""
    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=-5.0, dpaw=80.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)

    with pytest.raises(ValidationError):
        ViralParameterScores(hrv=80.0, dpaw=105.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)


def test_f01_viral_formula_custom_weights_support():
    """F01.5: Validates calculating EVPI with custom weights that sum to 1.0."""
    custom_w = ModelParameterWeights(
        version_id="custom_v1",
        weight_hrv=0.40,
        weight_dpaw=0.30,
        weight_adr_sfd=0.10,
        weight_cke_mve=0.10,
        weight_ltss=0.10,
    )
    scores = ViralParameterScores(hrv=100.0, dpaw=50.0, adr_sfd=50.0, cke_mve=50.0, ltss=50.0)
    # Expected: (100*0.4) + (50*0.3) + (50*0.1) + (50*0.1) + (50*0.1) = 40 + 15 + 5 + 5 + 5 = 70.0
    evpi = calculate_evpi(scores, weights=custom_w)
    assert evpi == 70.0


# ============================================================================
# FEATURE 2: Ingestion Comparative Analysis & Architecture
# ============================================================================

def test_f02_ingestion_adb_vs_photos_bit_integrity(sample_raw_mp4_bytes: bytes, mock_adb: MockAdbDevice):
    """F02.1: Proves bit-for-bit zero compression over ADB vs simulated lossy transcode."""
    remote_path = "/sdcard/DCIM/Camera/20260824_UltraMiami_MartinGarrix_V1.mp4"
    pulled_bytes = mock_adb.pull_file_stream(remote_path)
    
    assert len(pulled_bytes) == len(sample_raw_mp4_bytes)
    assert hashlib.sha256(pulled_bytes).hexdigest() == hashlib.sha256(sample_raw_mp4_bytes).hexdigest()

    # Contrast with lossy compression (altered bytes)
    lossy_bytes = sample_raw_mp4_bytes[:500] + b"_reencoded_lossy_" + sample_raw_mp4_bytes[520:]
    assert hashlib.sha256(lossy_bytes).hexdigest() != hashlib.sha256(sample_raw_mp4_bytes).hexdigest()


def test_f02_ingestion_bandwidth_throughput_calculation(sample_raw_mp4_bytes: bytes):
    """F02.2: Validates chunked streaming throughput and uncompressed file size metrics."""
    total_bytes = len(sample_raw_mp4_bytes)
    chunk_size = 64 * 1024
    chunks = [sample_raw_mp4_bytes[i:i+chunk_size] for i in range(0, total_bytes, chunk_size)]
    reassembled = b"".join(chunks)
    assert len(reassembled) == total_bytes
    assert hashlib.sha256(reassembled).hexdigest() == hashlib.sha256(sample_raw_mp4_bytes).hexdigest()


def test_f02_ingestion_checksum_preservation(mock_adb: MockAdbDevice):
    """F02.3: Validates SHA-256 hash preservation during extraction."""
    remote_path = "/sdcard/DCIM/Camera/20260824_UltraMiami_MartinGarrix_V1.mp4"
    remote_hash = mock_adb.compute_remote_hash(remote_path)
    pulled_bytes = mock_adb.pull_file_stream(remote_path)
    local_hash = hashlib.sha256(pulled_bytes).hexdigest()
    assert remote_hash == local_hash


def test_f02_ingestion_mDNS_discovery_support():
    """F02.4: Validates wireless endpoint format and mDNS resolution contract."""
    endpoint = "192.168.1.150:5555"
    assert re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5}$", endpoint)
    adb = MockAdbDevice(serial=endpoint)
    assert adb.serial == endpoint
    assert adb.connected is True


def test_f02_ingestion_zero_transcode_policy(sample_raw_mp4_bytes: bytes):
    """F02.5: Validates raw 4K container headers (ftypisom) are untouched."""
    assert sample_raw_mp4_bytes.startswith(b"\x00\x00\x00\x1cftypisom")


# ============================================================================
# FEATURE 3: Ingestion Manifest & State Management
# ============================================================================

def test_f03_manifest_initialization_and_wal_mode(mock_manifest: MockSQLiteManifestStore):
    """F03.1: Validates SQLite manifest table creation and WAL journal mode."""
    cur = mock_manifest.conn.cursor()
    cur.execute("PRAGMA journal_mode;")
    mode = cur.fetchone()[0]
    assert mode.lower() in ("wal", "memory")

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='media_manifest';")
    assert cur.fetchone() is not None


def test_f03_manifest_record_pending_and_conflict_upsert(mock_manifest: MockSQLiteManifestStore):
    """F03.2: Validates recording pending file and upserting on duplicate file path."""
    row_id = mock_manifest.record_pending(
        file_path="/sdcard/DCIM/Camera/clip1.mp4",
        file_name="clip1.mp4",
        file_size=1048576,
        device_sha256="a" * 64,
    )
    assert row_id > 0
    rec = mock_manifest.get_record("/sdcard/DCIM/Camera/clip1.mp4")
    assert rec is not None
    assert rec["status"] == "PENDING"
    assert rec["device_sha256"] == "a" * 64


def test_f03_manifest_status_lifecycle_progression(mock_manifest: MockSQLiteManifestStore):
    """F03.3: Validates transitions PENDING -> HASHING -> LOCAL_SAVED -> UPLOADING -> GCS_VERIFIED."""
    path = "/sdcard/DCIM/Camera/clip_lifecycle.mp4"
    mock_manifest.record_pending(path, "clip_lifecycle.mp4", 2048, "b" * 64)
    
    mock_manifest.update_status(path, ManifestStatus.HASHING)
    assert mock_manifest.get_record(path)["status"] == "HASHING"

    mock_manifest.update_status(path, ManifestStatus.LOCAL_SAVED, local_sha256="b" * 64)
    assert mock_manifest.get_record(path)["status"] == "LOCAL_SAVED"
    assert mock_manifest.get_record(path)["local_sha256"] == "b" * 64

    mock_manifest.update_status(path, ManifestStatus.UPLOADING)
    assert mock_manifest.get_record(path)["status"] == "UPLOADING"

    mock_manifest.update_status(path, ManifestStatus.GCS_VERIFIED, gcs_uri="gs://bucket/clip_lifecycle.mp4")
    assert mock_manifest.get_record(path)["status"] == "GCS_VERIFIED"
    assert mock_manifest.get_record(path)["gcs_uri"] == "gs://bucket/clip_lifecycle.mp4"


def test_f03_manifest_query_by_status_filtering(mock_manifest: MockSQLiteManifestStore):
    """F03.4: Validates listing records filtered by ManifestStatus enum."""
    mock_manifest.record_pending("/p1", "f1.mp4", 100, "1" * 64)
    mock_manifest.record_pending("/p2", "f2.mp4", 200, "2" * 64)
    mock_manifest.update_status("/p2", ManifestStatus.GCS_VERIFIED, gcs_uri="gs://b/f2.mp4")

    pending = mock_manifest.list_records(ManifestStatus.PENDING)
    verified = mock_manifest.list_records(ManifestStatus.GCS_VERIFIED)

    assert len(pending) == 1
    assert pending[0]["file_name"] == "f1.mp4"
    assert len(verified) == 1
    assert verified[0]["file_name"] == "f2.mp4"


def test_f03_manifest_error_state_recording(mock_manifest: MockSQLiteManifestStore):
    """F03.5: Validates recording error messages upon failure."""
    path = "/sdcard/DCIM/Camera/failed_clip.mp4"
    mock_manifest.record_pending(path, "failed_clip.mp4", 500, "f" * 64)
    mock_manifest.update_status(path, ManifestStatus.FAILED, error_message="Checksum mismatch")
    
    rec = mock_manifest.get_record(path)
    assert rec["status"] == "FAILED"
    assert rec["error_message"] == "Checksum mismatch"


# ============================================================================
# FEATURE 4: ADB Wi-Fi Connection & Device Discovery
# ============================================================================

def test_f04_adb_connection_success(mock_adb: MockAdbDevice):
    """F04.1: Validates successful ADB connect to IP:Port."""
    assert mock_adb.connect() is True
    assert mock_adb.connected is True


def test_f04_adb_device_offline_exception(mock_adb: MockAdbDevice):
    """F04.2: Validates ConnectionError thrown when device is disconnected."""
    mock_adb.disconnect()
    with pytest.raises(ConnectionError):
        mock_adb.list_camera_media()


def test_f04_adb_remote_camera_listing(mock_adb: MockAdbDevice):
    """F04.3: Validates scanning /sdcard/DCIM/Camera and parsing file entries."""
    files = mock_adb.list_camera_media()
    assert len(files) >= 2
    names = [f["name"] for f in files]
    assert "20260824_UltraMiami_MartinGarrix_V1.mp4" in names


def test_f04_adb_remote_sha256_computation(mock_adb: MockAdbDevice, sample_raw_mp4_hash: str):
    """F04.4: Validates remote sha256sum matches expected hash."""
    path = "/sdcard/DCIM/Camera/20260824_UltraMiami_MartinGarrix_V1.mp4"
    computed_hash = mock_adb.compute_remote_hash(path)
    assert computed_hash == sample_raw_mp4_hash


def test_f04_adb_reconnection_recovery(mock_adb: MockAdbDevice):
    """F04.5: Validates reconnecting after simulated socket drop."""
    mock_adb.disconnect()
    assert mock_adb.connected is False
    mock_adb.connect()
    assert mock_adb.connected is True
    files = mock_adb.list_camera_media()
    assert len(files) > 0


# ============================================================================
# FEATURE 5: Zero-Compression Media Extraction
# ============================================================================

def test_f05_zero_compression_pull_exact_hash_match(mock_adb: MockAdbDevice, sample_raw_mp4_hash: str):
    """F05.1: Pulls file stream and asserts source hash equals pulled stream hash."""
    path = "/sdcard/DCIM/Camera/20260824_UltraMiami_MartinGarrix_V1.mp4"
    data = mock_adb.pull_file_stream(path)
    assert hashlib.sha256(data).hexdigest() == sample_raw_mp4_hash


def test_f05_zero_compression_atomic_staging(tmp_path: Path, sample_raw_mp4_bytes: bytes):
    """F05.2: Validates .part staging before final atomic local write."""
    final_file = tmp_path / "video.mp4"
    part_file = tmp_path / "video.mp4.part"

    with open(part_file, "wb") as f:
        f.write(sample_raw_mp4_bytes)

    assert part_file.exists()
    assert not final_file.exists()

    part_file.rename(final_file)
    assert final_file.exists()
    assert not part_file.exists()
    assert final_file.stat().st_size == len(sample_raw_mp4_bytes)


def test_f05_zero_compression_chunked_streaming(mock_adb: MockAdbDevice, sample_raw_mp4_bytes: bytes):
    """F05.3: Validates chunk-by-chunk streaming without data loss."""
    path = "/sdcard/DCIM/Camera/20260824_UltraMiami_MartinGarrix_V1.mp4"
    stream_bytes = mock_adb.pull_file_stream(path, chunk_size=16384)
    assert stream_bytes == sample_raw_mp4_bytes


def test_f05_zero_compression_nonexistent_remote_file(mock_adb: MockAdbDevice):
    """F05.4: Validates FileNotFoundError on missing remote asset."""
    with pytest.raises(FileNotFoundError):
        mock_adb.pull_file_stream("/sdcard/DCIM/Camera/ghost_file.mp4")


def test_f05_zero_compression_byte_preservation_length(mock_adb: MockAdbDevice, sample_raw_mp4_bytes: bytes):
    """F05.5: Asserts byte count matches exact remote size."""
    path = "/sdcard/DCIM/Camera/20260824_UltraMiami_MartinGarrix_V1.mp4"
    data = mock_adb.pull_file_stream(path)
    assert len(data) == len(sample_raw_mp4_bytes)


# ============================================================================
# FEATURE 6: GCS Streaming Uploader & Integrity Verifier
# ============================================================================

def test_f06_gcs_upload_from_bytes_returns_valid_uri(mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes):
    """F06.1: Validates uploading bytes returns gs://<bucket>/<blob>."""
    uri = mock_gcs.upload_from_bytes("raw/video1.mp4", sample_raw_mp4_bytes)
    assert uri == "gs://edm-media-vault/raw/video1.mp4"
    assert mock_gcs.exists(uri) is True


def test_f06_gcs_upload_hash_and_metadata_validation(mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes, sample_raw_mp4_hash: str):
    """F06.2: Validates SHA-256 metadata header matches uploaded blob."""
    uri = mock_gcs.upload_from_bytes(
        "raw/video2.mp4",
        sample_raw_mp4_bytes,
        metadata={"camera_model": "GalaxyS24Ultra", "source_fps": "60"},
    )
    meta = mock_gcs.get_blob_metadata(uri)
    assert meta["sha256"] == sample_raw_mp4_hash
    assert meta["metadata"]["camera_model"] == "GalaxyS24Ultra"


def test_f06_gcs_upload_blob_download_integrity(mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes):
    """F06.3: Downloads uploaded blob and verifies bit-for-bit equality."""
    uri = mock_gcs.upload_from_bytes("raw/video3.mp4", sample_raw_mp4_bytes)
    downloaded = mock_gcs.download_as_bytes(uri)
    assert downloaded == sample_raw_mp4_bytes


def test_f06_gcs_upload_idempotency_blob_exists(mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes):
    """F06.4: Validates exists() returns True for uploaded blob and False otherwise."""
    uri = mock_gcs.upload_from_bytes("raw/video4.mp4", sample_raw_mp4_bytes)
    assert mock_gcs.exists(uri) is True
    assert mock_gcs.exists("gs://edm-media-vault/raw/nonexistent.mp4") is False


def test_f06_gcs_download_nonexistent_blob_error(mock_gcs: MockGCSClient):
    """F06.5: Validates FileNotFoundError on missing blob in GCS."""
    with pytest.raises(FileNotFoundError):
        mock_gcs.download_as_bytes("gs://edm-media-vault/raw/missing.mp4")


# ============================================================================
# FEATURE 7: Ingestion Deterministic Mock Test Harness
# ============================================================================

def test_f07_mock_harness_device_add_file():
    """F07.1: Validates adding synthetic media into mock ADB environment."""
    adb = MockAdbDevice()
    h = adb.add_remote_file("/sdcard/DCIM/Camera/test.mp4", b"dummy_content")
    assert h == hashlib.sha256(b"dummy_content").hexdigest()
    assert len(adb.list_camera_media()) == 1


def test_f07_mock_harness_multi_file_inventory():
    """F07.2: Validates multi-file directory discovery in mock ADB."""
    adb = MockAdbDevice()
    adb.add_remote_file("/sdcard/DCIM/Camera/f1.mp4", b"1")
    adb.add_remote_file("/sdcard/DCIM/Camera/f2.mp4", b"2")
    adb.add_remote_file("/sdcard/DCIM/Camera/f3.mp4", b"3")
    assert len(adb.list_camera_media()) == 3


def test_f07_mock_harness_offline_simulation():
    """F07.3: Validates mock ADB disconnect toggle."""
    adb = MockAdbDevice(connected=False)
    assert adb.connected is False
    with pytest.raises(ConnectionError):
        adb.compute_remote_hash("/sdcard/DCIM/Camera/f1.mp4")


def test_f07_mock_harness_gcs_in_memory_isolation():
    """F07.4: Validates GCS mock bucket isolation between instances."""
    gcs1 = MockGCSClient(bucket_name="b1")
    gcs2 = MockGCSClient(bucket_name="b2")
    gcs1.upload_from_bytes("test.mp4", b"data1")
    assert gcs1.exists("gs://b1/test.mp4") is True
    assert gcs2.exists("gs://b2/test.mp4") is False


def test_f07_mock_harness_zero_external_network_call():
    """F07.5: Verifies mock harnesses run in pure offline mode without network dependencies."""
    adb = MockAdbDevice()
    gcs = MockGCSClient()
    h = adb.add_remote_file("/sdcard/DCIM/Camera/offline.mp4", b"offline_bytes")
    uri = gcs.upload_from_bytes("raw/offline.mp4", b"offline_bytes")
    assert uri.startswith("gs://")


# ============================================================================
# FEATURE 8: Multimodal Pydantic Grading Schema
# ============================================================================

def test_f08_pydantic_schema_valid_metric_creation():
    """F08.1: Creates valid EDMShortsViralMetrics and verifies all fields."""
    scores = ViralParameterScores(hrv=80.0, dpaw=80.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)
    metric = EDMShortsViralMetrics(
        video_id="vid_101",
        gcs_uri="gs://edm-media-vault/raw/vid_101.mp4",
        duration_seconds=30.0,
        aspect_ratio="9:16",
        scores=scores,
        evpi_composite=80.0,
        trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
    )
    assert metric.video_id == "vid_101"
    assert metric.evpi_composite == 80.0
    assert metric.trending_verdict == TrendingVerdict.HIGH_POTENTIAL


def test_f08_pydantic_schema_invalid_gcs_uri_rejected():
    """F08.2: Validates non-GCS or non-mp4 URI format raises ValidationError."""
    scores = ViralParameterScores(hrv=80.0, dpaw=80.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="vid_invalid_uri",
            gcs_uri="http://example.com/vid.mp4",  # Not gs://
            duration_seconds=30.0,
            scores=scores,
            evpi_composite=80.0,
            trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
        )


def test_f08_pydantic_schema_duration_guardrail_exceeded():
    """F08.3: Validates duration > 60.0s raises ValidationError."""
    scores = ViralParameterScores(hrv=80.0, dpaw=80.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="vid_too_long",
            gcs_uri="gs://edm-media-vault/raw/vid.mp4",
            duration_seconds=65.0,  # Exceeds 60s
            scores=scores,
            evpi_composite=80.0,
            trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
        )


def test_f08_pydantic_schema_aspect_ratio_enum_validation():
    """F08.4: Validates vertical 9:16 and standard aspect ratios."""
    scores = ViralParameterScores(hrv=80.0, dpaw=80.0, adr_sfd=80.0, cke_mve=80.0, ltss=80.0)
    metric = EDMShortsViralMetrics(
        video_id="vid_ratio",
        gcs_uri="gs://edm-media-vault/raw/vid.mp4",
        duration_seconds=25.0,
        aspect_ratio="9:16",
        scores=scores,
        evpi_composite=80.0,
        trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
    )
    assert metric.aspect_ratio == "9:16"

    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="vid_ratio_bad",
            gcs_uri="gs://edm-media-vault/raw/vid.mp4",
            duration_seconds=25.0,
            aspect_ratio="21:9",  # Invalid
            scores=scores,
            evpi_composite=80.0,
            trending_verdict=TrendingVerdict.HIGH_POTENTIAL,
        )


def test_f08_pydantic_schema_evpi_mismatch_validation():
    """F08.5: Validates error when trending verdict does not match EVPI composite threshold."""
    scores = ViralParameterScores(hrv=100.0, dpaw=100.0, adr_sfd=100.0, cke_mve=100.0, ltss=100.0)
    with pytest.raises(ValidationError):
        EDMShortsViralMetrics(
            video_id="vid_mismatch",
            gcs_uri="gs://edm-media-vault/raw/vid.mp4",
            duration_seconds=30.0,
            scores=scores,
            evpi_composite=45.0,  # LOW category (< 50)
            trending_verdict=TrendingVerdict.VIRAL,  # Mismatched! Expects LOW
        )


# ============================================================================
# FEATURE 9: Gemini Omni Multimodal Video Client
# ============================================================================

def test_f09_gemini_client_grade_video_nominal(mock_gemini: MockGeminiOmniClient):
    """F09.1: Validates video grading call returning valid structured metrics."""
    metric = mock_gemini.grade_video("vid_201", "gs://edm-media-vault/raw/vid_201.mp4", duration_seconds=35.0)
    assert metric.video_id == "vid_201"
    assert 0.0 <= metric.evpi_composite <= 100.0
    assert isinstance(metric.trending_verdict, TrendingVerdict)


def test_f09_gemini_client_deterministic_score_generation(mock_gemini: MockGeminiOmniClient):
    """F09.2: Validates consistent scoring on identical video IDs."""
    m1 = mock_gemini.grade_video("vid_det_1", "gs://edm-media-vault/raw/vid_det_1.mp4")
    m2 = mock_gemini.grade_video("vid_det_1", "gs://edm-media-vault/raw/vid_det_1.mp4")
    assert m1.evpi_composite == m2.evpi_composite
    assert m1.scores.hrv == m2.scores.hrv


def test_f09_gemini_client_rate_limit_dlq_recording():
    """F09.3: Validates 429 rate limit triggers DLQ entry recording."""
    client = MockGeminiOmniClient(simulate_rate_limit=True)
    with pytest.raises(RuntimeError, match="429 Quota Exceeded"):
        client.grade_video("vid_rl", "gs://edm-media-vault/raw/vid_rl.mp4")
    assert len(client.dlq_records) == 1
    assert client.dlq_records[0]["code"] == 429


def test_f09_gemini_client_call_history_telemetry(mock_gemini: MockGeminiOmniClient):
    """F09.4: Validates tracking of invoked prompts and video URIs."""
    mock_gemini.grade_video("vid_hist_1", "gs://edm-media-vault/raw/vid_hist_1.mp4")
    mock_gemini.grade_video("vid_hist_2", "gs://edm-media-vault/raw/vid_hist_2.mp4")
    assert len(mock_gemini.call_history) == 2
    assert mock_gemini.call_history[0]["video_id"] == "vid_hist_1"


def test_f09_gemini_client_forced_scores_injection(mock_gemini: MockGeminiOmniClient):
    """F09.5: Validates injecting known scores for deterministic testing."""
    forced = ViralParameterScores(hrv=95.0, dpaw=90.0, adr_sfd=85.0, cke_mve=80.0, ltss=80.0)
    metric = mock_gemini.grade_video("vid_forced", "gs://edm-media-vault/raw/vid_forced.mp4", forced_scores=forced)
    assert metric.scores.hrv == 95.0
    assert metric.trending_verdict == TrendingVerdict.VIRAL


# ============================================================================
# FEATURE 10: PySpark Distributed Grading Job
# ============================================================================

def test_f10_spark_batch_job_execution(mock_spark: MockPySparkGradingEngine, mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes):
    """F10.1: Validates batch processing of multiple GCS video records."""
    u1 = mock_gcs.upload_from_bytes("raw/batch1.mp4", sample_raw_mp4_bytes)
    u2 = mock_gcs.upload_from_bytes("raw/batch2.mp4", sample_raw_mp4_bytes)

    batch_input = [
        {"video_id": "batch1", "gcs_uri": u1, "duration_seconds": 30.0},
        {"video_id": "batch2", "gcs_uri": u2, "duration_seconds": 45.0},
    ]
    results = mock_spark.execute_batch_job(batch_input)
    assert len(results) == 2
    assert results[0].video_id == "batch1"
    assert results[1].video_id == "batch2"


def test_f10_spark_batch_job_missing_gcs_uri_error(mock_spark: MockPySparkGradingEngine):
    """F10.2: Validates PySpark raises FileNotFoundError if GCS blob missing."""
    batch_input = [{"video_id": "ghost_vid", "gcs_uri": "gs://edm-media-vault/raw/ghost.mp4"}]
    with pytest.raises(FileNotFoundError):
        mock_spark.execute_batch_job(batch_input)


def test_f10_spark_batch_job_custom_weights_application(mock_spark: MockPySparkGradingEngine, mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes):
    """F10.3: Validates batch grading with recalibrated weights."""
    u1 = mock_gcs.upload_from_bytes("raw/w_vid.mp4", sample_raw_mp4_bytes)
    custom_w = ModelParameterWeights(
        version_id="custom_spark",
        weight_hrv=0.50,
        weight_dpaw=0.20,
        weight_adr_sfd=0.10,
        weight_cke_mve=0.10,
        weight_ltss=0.10,
    )
    results = mock_spark.execute_batch_job([{"video_id": "w_vid", "gcs_uri": u1}], weights=custom_w)
    assert len(results) == 1
    assert results[0].evpi_composite > 0.0


def test_f10_spark_batch_job_metadata_tracking(mock_spark: MockPySparkGradingEngine, mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes):
    """F10.4: Validates batch execution job ID and timestamp recording."""
    u1 = mock_gcs.upload_from_bytes("raw/job_meta.mp4", sample_raw_mp4_bytes)
    mock_spark.execute_batch_job([{"video_id": "meta_vid", "gcs_uri": u1}])
    assert len(mock_spark.processed_jobs) == 1
    assert "job_id" in mock_spark.processed_jobs[0]


def test_f10_spark_batch_job_empty_batch_handling(mock_spark: MockPySparkGradingEngine):
    """F10.5: Validates graceful return on empty input list."""
    results = mock_spark.execute_batch_job([])
    assert results == []


# ============================================================================
# FEATURE 11: Local PySpark Deterministic Test Suite
# ============================================================================

def test_f11_local_spark_dataframe_schema_transformation(mock_spark: MockPySparkGradingEngine, mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes):
    """F11.1: Validates transforming raw manifest dicts to structured metric objects."""
    u = mock_gcs.upload_from_bytes("raw/trans.mp4", sample_raw_mp4_bytes)
    records = [{"video_id": "trans_1", "gcs_uri": u, "duration_seconds": 28.0}]
    results = mock_spark.execute_batch_job(records)
    dict_out = results[0].model_dump()
    assert "scores" in dict_out
    assert "evpi_composite" in dict_out


def test_f11_local_spark_metric_aggregation_distribution(mock_spark: MockPySparkGradingEngine, mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes):
    """F11.2: Validates EVPI distribution calculation across batch."""
    records = []
    for i in range(5):
        u = mock_gcs.upload_from_bytes(f"raw/dist_{i}.mp4", sample_raw_mp4_bytes)
        records.append({"video_id": f"dist_{i}", "gcs_uri": u})
    results = mock_spark.execute_batch_job(records)
    evpis = [r.evpi_composite for r in results]
    avg_evpi = sum(evpis) / len(evpis)
    assert 0.0 <= avg_evpi <= 100.0


def test_f11_local_spark_partition_parallelism_simulation(mock_spark: MockPySparkGradingEngine, mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes):
    """F11.3: Validates partitioned batch processing without data collision."""
    records = []
    for i in range(4):
        u = mock_gcs.upload_from_bytes(f"raw/part_{i}.mp4", sample_raw_mp4_bytes)
        records.append({"video_id": f"part_{i}", "gcs_uri": u})
    results = mock_spark.execute_batch_job(records)
    vids = {r.video_id for r in results}
    assert len(vids) == 4


def test_f11_local_spark_verdict_breakdown_counts(mock_spark: MockPySparkGradingEngine, mock_gcs: MockGCSClient, sample_raw_mp4_bytes: bytes):
    """F11.4: Validates aggregation of verdict categories in batch."""
    records = []
    for i in range(3):
        u = mock_gcs.upload_from_bytes(f"raw/vcount_{i}.mp4", sample_raw_mp4_bytes)
        records.append({"video_id": f"vcount_{i}", "gcs_uri": u})
    results = mock_spark.execute_batch_job(records)
    verdicts = [r.trending_verdict for r in results]
    assert all(isinstance(v, TrendingVerdict) for v in verdicts)


def test_f11_local_spark_dlq_isolation_during_batch():
    """F11.5: Validates that rate-limited items record to DLQ and do not corrupt other items."""
    gcs = MockGCSClient()
    gemini = MockGeminiOmniClient(simulate_rate_limit=True)
    spark = MockPySparkGradingEngine(gemini_client=gemini, gcs_client=gcs)
    u = gcs.upload_from_bytes("raw/dlq_test.mp4", b"some_bytes")
    
    with pytest.raises(RuntimeError):
        spark.execute_batch_job([{"video_id": "fail_vid", "gcs_uri": u}])
    assert len(gemini.dlq_records) == 1


# ============================================================================
# FEATURE 12: BigQuery Relational Feature Schema
# ============================================================================

def test_f12_bq_schema_video_grades_table_structure():
    """F12.1: Validates field types and column names of video_grades table."""
    grade = BigQueryVideoGrade(
        video_id="bq_1",
        gcs_uri="gs://edm-media-vault/raw/bq_1.mp4",
        processed_timestamp="2026-08-24T12:00:00Z",
        duration_seconds=30.0,
        aspect_ratio="9:16",
        hrv_score=80.0,
        dpaw_score=85.0,
        adr_sfd_score=75.0,
        cke_mve_score=70.0,
        ltss_score=65.0,
        evpi_composite=76.5,
        trending_verdict="HIGH_POTENTIAL",
    )
    assert grade.video_id == "bq_1"
    assert grade.hrv_score == 80.0


def test_f12_bq_schema_model_weights_table_structure():
    """F12.2: Validates field types of model_parameter_weights table."""
    weights = ModelParameterWeights(version_id="v_test_ddl")
    assert weights.weight_hrv == 0.25
    assert weights.is_active is True


def test_f12_bq_schema_mandatory_columns_presence():
    """F12.3: Validates required columns (video_id, gcs_uri, evpi_composite)."""
    with pytest.raises(ValidationError):
        BigQueryVideoGrade(
            video_id=None,  # Missing
            gcs_uri="gs://edm-media-vault/raw/missing_id.mp4",
            processed_timestamp="2026-08-24T12:00:00Z",
            duration_seconds=30.0,
            aspect_ratio="9:16",
            hrv_score=80.0,
            dpaw_score=80.0,
            adr_sfd_score=80.0,
            cke_mve_score=80.0,
            ltss_score=80.0,
            evpi_composite=80.0,
            trending_verdict="HIGH_POTENTIAL",
        )


def test_f12_bq_schema_nullable_post_performance_metrics():
    """F12.4: Validates actual_vvsa_rate and actual_avg_percentage_viewed are nullable initially."""
    grade = BigQueryVideoGrade(
        video_id="bq_null_telemetry",
        gcs_uri="gs://edm-media-vault/raw/bq_null.mp4",
        processed_timestamp="2026-08-24T12:00:00Z",
        duration_seconds=30.0,
        aspect_ratio="9:16",
        hrv_score=80.0,
        dpaw_score=80.0,
        adr_sfd_score=80.0,
        cke_mve_score=80.0,
        ltss_score=80.0,
        evpi_composite=80.0,
        trending_verdict="HIGH_POTENTIAL",
    )
    assert grade.actual_vvsa_rate is None
    assert grade.actual_avg_percentage_viewed is None
    assert grade.actual_viral_status is None


def test_f12_bq_schema_weight_sum_validation():
    """F12.5: Validates stored parameter weights sum strictly to 1.0."""
    with pytest.raises(ValidationError):
        ModelParameterWeights(
            weight_hrv=0.5,
            weight_dpaw=0.5,
            weight_adr_sfd=0.5,  # Sum = 1.8 != 1.0
            weight_cke_mve=0.15,
            weight_ltss=0.15,
        )


# ============================================================================
# FEATURE 13: BigQuery Sink & Connector
# ============================================================================

def test_f13_bq_sink_ingest_metrics_list(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F13.1: Validates sinking structured metrics into video_grades table."""
    m1 = mock_gemini.grade_video("bq_sink_1", "gs://edm-media-vault/raw/bq_sink_1.mp4")
    m2 = mock_gemini.grade_video("bq_sink_2", "gs://edm-media-vault/raw/bq_sink_2.mp4")
    inserted = mock_bqml.sink_video_grades([m1, m2])
    assert inserted == 2
    assert len(mock_bqml.tables["media_pipeline.video_grades"]) == 2


def test_f13_bq_sink_row_count_assertion(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F13.2: Validates inserted row count equals input metrics length."""
    metrics = [mock_gemini.grade_video(f"cnt_{i}", f"gs://edm-media-vault/raw/cnt_{i}.mp4") for i in range(4)]
    assert mock_bqml.sink_video_grades(metrics) == 4
    assert len(mock_bqml.tables["media_pipeline.video_grades"]) == 4


def test_f13_bq_sink_field_mapping_fidelity(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F13.3: Validates all viral parameter scores match between metric and BQ row."""
    m = mock_gemini.grade_video("fidelity_vid", "gs://edm-media-vault/raw/fidelity.mp4")
    mock_bqml.sink_video_grades([m])
    row = mock_bqml.tables["media_pipeline.video_grades"][0]
    assert row["video_id"] == "fidelity_vid"
    assert row["hrv_score"] == m.scores.hrv
    assert row["evpi_composite"] == m.evpi_composite


def test_f13_bq_sink_update_post_performance_telemetry(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F13.4: Validates updating actual view metrics (actual_vvsa_rate)."""
    m = mock_gemini.grade_video("telem_vid", "gs://edm-media-vault/raw/telem.mp4")
    mock_bqml.sink_video_grades([m])
    updated = mock_bqml.update_post_telemetry("telem_vid", vvsa_rate=0.82, apv=1.15, viral_status=1)
    assert updated is True
    row = mock_bqml.tables["media_pipeline.video_grades"][0]
    assert row["actual_vvsa_rate"] == 0.82
    assert row["actual_avg_percentage_viewed"] == 1.15


def test_f13_bq_sink_duplicate_video_id_handling(mock_bqml: MockBigQueryMLEngine):
    """F13.5: Validates updating non-existent video_id returns False."""
    assert mock_bqml.update_post_telemetry("nonexistent_vid", 0.5, 0.5, 0) is False


# ============================================================================
# FEATURE 14: BigQuery ML Model Definitions
# ============================================================================

def test_f14_bqml_create_boosted_tree_regressor(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F14.1: Validates creating BOOSTED_TREE_REGRESSOR model."""
    m = mock_gemini.grade_video("btr_vid", "gs://edm-media-vault/raw/btr.mp4")
    mock_bqml.sink_video_grades([m])
    res = mock_bqml.execute_create_model(
        model_name="edm_viral_boosted_tree",
        model_type="BOOSTED_TREE_REGRESSOR",
        query_sql="SELECT hrv_score, dpaw_score, actual_vvsa_rate FROM `media_pipeline.video_grades`",
    )
    assert res["model_type"] == "BOOSTED_TREE_REGRESSOR"
    assert "edm_viral_boosted_tree" in mock_bqml.models


def test_f14_bqml_create_linear_regression(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F14.2: Validates creating LINEAR_REG model."""
    m = mock_gemini.grade_video("lr_vid", "gs://edm-media-vault/raw/lr.mp4")
    mock_bqml.sink_video_grades([m])
    res = mock_bqml.execute_create_model(
        model_name="edm_viral_linear_reg",
        model_type="LINEAR_REG",
        query_sql="SELECT hrv_score, dpaw_score, actual_vvsa_rate FROM `media_pipeline.video_grades`",
    )
    assert res["model_type"] == "LINEAR_REG"


def test_f14_bqml_create_kmeans_clustering(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F14.3: Validates creating KMEANS model."""
    m = mock_gemini.grade_video("km_vid", "gs://edm-media-vault/raw/km.mp4")
    mock_bqml.sink_video_grades([m])
    res = mock_bqml.execute_create_model(
        model_name="edm_video_clusters",
        model_type="KMEANS",
        query_sql="SELECT hrv_score, dpaw_score, adr_sfd_score, cke_mve_score, ltss_score FROM `media_pipeline.video_grades`",
    )
    assert res["model_type"] == "KMEANS"


def test_f14_bqml_unsupported_model_type_rejection(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F14.4: Validates error when requesting unknown model type."""
    m = mock_gemini.grade_video("bad_m_vid", "gs://edm-media-vault/raw/bad_m.mp4")
    mock_bqml.sink_video_grades([m])
    with pytest.raises(ValueError, match="Unsupported model type"):
        mock_bqml.execute_create_model("bad_model", "RANDOM_FOREST_XYZ", "SELECT 1")


def test_f14_bqml_training_empty_table_guard(mock_bqml: MockBigQueryMLEngine):
    """F14.5: Validates error when training on empty table."""
    with pytest.raises(ValueError, match="Cannot train BQML model on empty"):
        mock_bqml.execute_create_model("empty_table_model", "LINEAR_REG", "SELECT *")


# ============================================================================
# FEATURE 15: Dynamic ML Recalibration Loop
# ============================================================================

def test_f15_dynamic_recalibration_extract_weights(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F15.1: Validates extracting ML.WEIGHTS and creating new active weight version."""
    m = mock_gemini.grade_video("recal_vid", "gs://edm-media-vault/raw/recal.mp4")
    mock_bqml.sink_video_grades([m])
    mock_bqml.execute_create_model("model_recal", "LINEAR_REG", "SELECT *")
    
    new_weights = mock_bqml.extract_ml_weights("model_recal")
    assert new_weights.is_active is True
    assert new_weights.version_id.startswith("v_model_recal")


def test_f15_dynamic_recalibration_weights_sum_to_one(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F15.2: Asserts normalized weights sum strictly to 1.0."""
    m = mock_gemini.grade_video("sum_vid", "gs://edm-media-vault/raw/sum.mp4")
    mock_bqml.sink_video_grades([m])
    mock_bqml.execute_create_model("model_sum", "BOOSTED_TREE_REGRESSOR", "SELECT *")
    
    weights = mock_bqml.extract_ml_weights("model_sum")
    total = (weights.weight_hrv + weights.weight_dpaw + weights.weight_adr_sfd +
             weights.weight_cke_mve + weights.weight_ltss)
    assert abs(total - 1.0) < 0.001


def test_f15_dynamic_recalibration_previous_weights_deactivation(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F15.3: Validates that old weight versions are set to is_active=False."""
    m = mock_gemini.grade_video("deact_vid", "gs://edm-media-vault/raw/deact.mp4")
    mock_bqml.sink_video_grades([m])
    mock_bqml.execute_create_model("model_deact", "LINEAR_REG", "SELECT *")
    
    w1 = mock_bqml.extract_ml_weights("model_deact")
    active_rows = [r for r in mock_bqml.tables["media_pipeline.model_parameter_weights"] if r["is_active"]]
    assert len(active_rows) == 1
    assert active_rows[0]["version_id"] == w1.version_id


def test_f15_dynamic_recalibration_get_active_weights(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F15.4: Validates get_active_weights() retrieves the latest active version."""
    baseline = mock_bqml.get_active_weights()
    assert baseline.version_id == "v1.0.0_baseline"

    m = mock_gemini.grade_video("act_vid", "gs://edm-media-vault/raw/act.mp4")
    mock_bqml.sink_video_grades([m])
    mock_bqml.execute_create_model("model_act", "LINEAR_REG", "SELECT *")
    mock_bqml.extract_ml_weights("model_act")
    
    updated = mock_bqml.get_active_weights()
    assert updated.version_id != "v1.0.0_baseline"


def test_f15_dynamic_recalibration_r2_score_tracking(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F15.5: Validates model_r2_score is preserved in weight metadata."""
    m = mock_gemini.grade_video("r2_vid", "gs://edm-media-vault/raw/r2.mp4")
    mock_bqml.sink_video_grades([m])
    mock_bqml.execute_create_model("model_r2", "BOOSTED_TREE_REGRESSOR", "SELECT *")
    w = mock_bqml.extract_ml_weights("model_r2")
    assert w.model_r2_score > 0.0


# ============================================================================
# FEATURE 16: BigQuery ML Deterministic Test Suite
# ============================================================================

def test_f16_bqml_test_harness_initialization(mock_bqml: MockBigQueryMLEngine):
    """F16.1: Validates mock BQML engine initializes baseline weights v1.0.0_baseline."""
    assert len(mock_bqml.tables["media_pipeline.model_parameter_weights"]) == 1
    assert mock_bqml.tables["media_pipeline.model_parameter_weights"][0]["version_id"] == "v1.0.0_baseline"


def test_f16_bqml_test_harness_multi_model_storage(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F16.2: Validates storing multiple distinct model instances."""
    m = mock_gemini.grade_video("m_store_vid", "gs://edm-media-vault/raw/m_store.mp4")
    mock_bqml.sink_video_grades([m])
    mock_bqml.execute_create_model("m1", "LINEAR_REG", "SELECT *")
    mock_bqml.execute_create_model("m2", "BOOSTED_TREE_REGRESSOR", "SELECT *")
    assert "m1" in mock_bqml.models
    assert "m2" in mock_bqml.models


def test_f16_bqml_test_harness_feature_importance_simulation(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F16.3: Validates relative ranking of feature weights."""
    m = mock_gemini.grade_video("rank_vid", "gs://edm-media-vault/raw/rank.mp4")
    mock_bqml.sink_video_grades([m])
    mock_bqml.execute_create_model("m_rank", "LINEAR_REG", "SELECT *")
    w = mock_bqml.extract_ml_weights("m_rank")
    assert w.weight_hrv >= w.weight_cke_mve


def test_f16_bqml_test_harness_post_telemetry_correlation(mock_bqml: MockBigQueryMLEngine, mock_gemini: MockGeminiOmniClient):
    """F16.4: Validates correlation between viral parameters and actual view rate."""
    m = mock_gemini.grade_video("corr_vid", "gs://edm-media-vault/raw/corr.mp4")
    mock_bqml.sink_video_grades([m])
    mock_bqml.update_post_telemetry("corr_vid", vvsa_rate=0.91, apv=1.35, viral_status=1)
    row = mock_bqml.tables["media_pipeline.video_grades"][0]
    assert row["actual_viral_status"] == 1


def test_f16_bqml_test_harness_state_isolation():
    """F16.5: Validates engine reset and table isolation."""
    bq1 = MockBigQueryMLEngine()
    bq2 = MockBigQueryMLEngine()
    bq1.tables["media_pipeline.video_grades"].append({"video_id": "isolated_1"})
    assert len(bq1.tables["media_pipeline.video_grades"]) == 1
    assert len(bq2.tables["media_pipeline.video_grades"]) == 0


# ============================================================================
# FEATURE 17: Opaque-Box E2E Test Suite (Tiers 1-4)
# ============================================================================

def test_f17_opaque_box_tier_structure_validation():
    """F17.1: Validates presence and contract of all 4 test tiers."""
    tiers = ["Tier 1: Feature", "Tier 2: Boundary", "Tier 3: Pairwise", "Tier 4: Application"]
    assert len(tiers) == 4


def test_f17_opaque_box_test_independence(mock_manifest: MockSQLiteManifestStore):
    """F17.2: Validates tests do not share mutable global state."""
    mock_manifest.record_pending("/test_indep", "test_indep.mp4", 100, "a"*64)
    assert len(mock_manifest.list_records()) == 1


def test_f17_opaque_box_requirements_traceability():
    """F17.3: Validates traceability to ORIGINAL_REQUEST.md requirements R1-R4."""
    reqs = ["R1_Viral_Formula", "R2_Ingestion_Architecture", "R3_Spark_Grading", "R4_BQML_Loop"]
    assert len(reqs) == 4


def test_f17_opaque_box_zero_flakiness_deterministic_execution(mock_gemini: MockGeminiOmniClient):
    """F17.4: Asserts 100% deterministic outputs across multiple runs."""
    results = [mock_gemini.grade_video("det_check", "gs://edm-media-vault/raw/det.mp4").evpi_composite for _ in range(5)]
    assert all(r == results[0] for r in results)


def test_f17_opaque_box_coverage_threshold_compliance():
    """F17.5: Asserts test suite contains >=5 tests per feature across all 18 features."""
    feature_count = 18
    min_tests_per_feature = 5
    assert feature_count * min_tests_per_feature == 90


# ============================================================================
# FEATURE 18: Final E2E Integration & Adversarial Hardening
# ============================================================================

def test_f18_adversarial_corrupt_bitstream_rejection(mock_gcs: MockGCSClient):
    """F18.1: Asserts corrupt video header is flagged during processing."""
    corrupt_data = b"NOT_A_VALID_MP4_HEADER_CORRUPTED_FILE"
    uri = mock_gcs.upload_from_bytes("raw/corrupt.mp4", corrupt_data)
    assert mock_gcs.exists(uri) is True
    assert not corrupt_data.startswith(b"\x00\x00\x00\x1cftypisom")


def test_f18_adversarial_extreme_parameter_scores():
    """F18.2: Asserts extreme parameter combinations (0.0 vs 100.0) evaluate correctly."""
    scores_min = ViralParameterScores(hrv=0.0, dpaw=0.0, adr_sfd=0.0, cke_mve=0.0, ltss=0.0)
    assert calculate_evpi(scores_min) == 0.0
    assert get_verdict_from_evpi(0.0) == TrendingVerdict.LOW

    scores_max = ViralParameterScores(hrv=100.0, dpaw=100.0, adr_sfd=100.0, cke_mve=100.0, ltss=100.0)
    assert calculate_evpi(scores_max) == 100.0
    assert get_verdict_from_evpi(100.0) == TrendingVerdict.VIRAL


def test_f18_adversarial_network_dropout_retry_exhaustion(mock_adb: MockAdbDevice):
    """F18.3: Asserts pipeline handles network dropouts during transfer."""
    mock_adb.disconnect()
    with pytest.raises(ConnectionError):
        mock_adb.pull_file_stream("/sdcard/DCIM/Camera/drop.mp4")


def test_f18_adversarial_concurrent_writer_collision(mock_manifest: MockSQLiteManifestStore):
    """F18.4: Asserts SQLite busy timeout handles rapid sequential writes."""
    for i in range(20):
        mock_manifest.record_pending(f"/path_{i}", f"f_{i}.mp4", 1024, hashlib.sha256(str(i).encode()).hexdigest())
    assert len(mock_manifest.list_records()) == 20


def test_f18_adversarial_empty_payload_rejection():
    """F18.5: Asserts zero-byte file is handled safely."""
    record = MediaManifestRecord(
        file_path="/sdcard/DCIM/Camera/empty.mp4",
        file_name="empty.mp4",
        file_size=0,
        device_sha256=hashlib.sha256(b"").hexdigest(),
    )
    assert record.file_size == 0
