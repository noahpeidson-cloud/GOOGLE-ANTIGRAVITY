"""
conftest.py - Master Fixtures, Mock Drivers, and Data Models for E2E Test Suite.
Provides standalone, zero-external-dependency mock harnesses for ADB Wi-Fi Sync,
SQLite Manifest, Cloud Storage (GCS), Gemini Multimodal Video API, Dataproc PySpark,
and BigQuery ML Optimization Loop.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pytest
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# ============================================================================
# 1. ENUMS & CONSTANTS
# ============================================================================

class ManifestStatus(str, Enum):
    PENDING = "PENDING"
    HASHING = "HASHING"
    LOCAL_SAVED = "LOCAL_SAVED"
    UPLOADING = "UPLOADING"
    GCS_VERIFIED = "GCS_VERIFIED"
    GRADED = "GRADED"
    FAILED = "FAILED"


class TrendingVerdict(str, Enum):
    VIRAL = "VIRAL"                    # EVPI >= 85.0
    HIGH_POTENTIAL = "HIGH_POTENTIAL"  # 70.0 <= EVPI < 85.0
    AVERAGE = "AVERAGE"                # 50.0 <= EVPI < 70.0
    LOW = "LOW"                        # EVPI < 50.0


# Default weights defined in VIRAL_FORMULA specification
DEFAULT_WEIGHTS = {
    "weight_hrv": 0.25,
    "weight_dpaw": 0.25,
    "weight_adr_sfd": 0.20,
    "weight_cke_mve": 0.15,
    "weight_ltss": 0.15,
}


# ============================================================================
# 2. PYDANTIC SCHEMAS & DATA MODELS
# ============================================================================

class ViralParameterScores(BaseModel):
    """5 Core EDM Short-Form Viral Parameters (0.0 to 100.0)."""
    model_config = ConfigDict(validate_assignment=True)

    hrv: float = Field(..., ge=0.0, le=100.0, description="Hook Retention Velocity (0-3s energy curve)")
    dpaw: float = Field(..., ge=0.0, le=100.0, description="Drop Payoff Audio Waveform (RMS & spectral punch)")
    adr_sfd: float = Field(..., ge=0.0, le=100.0, description="Audio Drop Rate & Spectral Flux Density")
    cke_mve: float = Field(..., ge=0.0, le=100.0, description="Crowd Kinetic Energy & Motion Vector Entropy")
    ltss: float = Field(..., ge=0.0, le=100.0, description="Lighting Transition & Strobe Synchronization")


class ModelParameterWeights(BaseModel):
    """Dynamic parameter weights learned via BQML loop. Must sum to 1.0 ± 0.001."""
    model_config = ConfigDict(validate_assignment=True)

    version_id: str = "v1.0.0"
    weight_hrv: float = Field(0.25, ge=0.0, le=1.0)
    weight_dpaw: float = Field(0.25, ge=0.0, le=1.0)
    weight_adr_sfd: float = Field(0.20, ge=0.0, le=1.0)
    weight_cke_mve: float = Field(0.15, ge=0.0, le=1.0)
    weight_ltss: float = Field(0.15, ge=0.0, le=1.0)
    trained_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model_r2_score: float = Field(0.85, ge=0.0, le=1.0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_sum_to_one(self) -> ModelParameterWeights:
        total = self.weight_hrv + self.weight_dpaw + self.weight_adr_sfd + self.weight_cke_mve + self.weight_ltss
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Parameter weights must sum to 1.0 (got {total:.4f})")
        return self


def calculate_evpi(scores: ViralParameterScores, weights: Optional[ModelParameterWeights] = None) -> float:
    """Calculates composite Expected Viral Potential Index (EVPI)."""
    w = weights or ModelParameterWeights()
    evpi = (
        scores.hrv * w.weight_hrv +
        scores.dpaw * w.weight_dpaw +
        scores.adr_sfd * w.weight_adr_sfd +
        scores.cke_mve * w.weight_cke_mve +
        scores.ltss * w.weight_ltss
    )
    return round(float(evpi), 2)


def get_verdict_from_evpi(evpi: float) -> TrendingVerdict:
    """Classifies EVPI score into categorical verdict."""
    if evpi >= 85.0:
        return TrendingVerdict.VIRAL
    elif evpi >= 70.0:
        return TrendingVerdict.HIGH_POTENTIAL
    elif evpi >= 50.0:
        return TrendingVerdict.AVERAGE
    else:
        return TrendingVerdict.LOW


class EDMShortsViralMetrics(BaseModel):
    """Pydantic model representing structured video grading result."""
    model_config = ConfigDict(validate_assignment=True)

    video_id: str = Field(..., min_length=1)
    gcs_uri: str = Field(..., pattern=r"^gs://[a-zA-Z0-9_\.\-]+/.+\.mp4$")
    duration_seconds: float = Field(..., gt=0.0, le=60.0)
    aspect_ratio: str = Field("9:16", pattern=r"^(9:16|16:9|1:1|4:5)$")
    scores: ViralParameterScores
    evpi_composite: float = Field(..., ge=0.0, le=100.0)
    trending_verdict: TrendingVerdict
    graded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="after")
    def validate_evpi_and_verdict(self) -> EDMShortsViralMetrics:
        expected_verdict = get_verdict_from_evpi(self.evpi_composite)
        if self.trending_verdict != expected_verdict:
            raise ValueError(f"Verdict {self.trending_verdict} does not match expected {expected_verdict} for EVPI {self.evpi_composite}")
        return self


class MediaManifestRecord(BaseModel):
    """SQLite manifest entry representation."""
    model_config = ConfigDict(validate_assignment=True)

    file_path: str
    file_name: str
    file_size: int = Field(..., ge=0)
    device_sha256: str = Field(..., min_length=64, max_length=64)
    local_sha256: Optional[str] = None
    gcs_uri: Optional[str] = None
    status: ManifestStatus = ManifestStatus.PENDING
    uploaded_at: Optional[str] = None
    error_message: Optional[str] = None


class BigQueryVideoGrade(BaseModel):
    """BigQuery video_grades table row representation."""
    video_id: str
    gcs_uri: str
    processed_timestamp: str
    duration_seconds: float
    aspect_ratio: str
    hrv_score: float
    dpaw_score: float
    adr_sfd_score: float
    cke_mve_score: float
    ltss_score: float
    evpi_composite: float
    trending_verdict: str
    actual_vvsa_rate: Optional[float] = None
    actual_avg_percentage_viewed: Optional[float] = None
    actual_viral_status: Optional[int] = None


# ============================================================================
# 3. MOCK HARNESSES & STANDALONE DRIVERS
# ============================================================================

class MockAdbDevice:
    """Emulates an Android device connected over local Wi-Fi ADB."""

    def __init__(self, serial: str = "192.168.1.150:5555", connected: bool = True):
        self.serial = serial
        self.connected = connected
        self.paired = True
        self.files: Dict[str, bytes] = {}
        self.disconnect_rate = 0.0
        self.call_count = 0

    def add_remote_file(self, remote_path: str, data: bytes) -> str:
        """Adds a remote file in /sdcard/DCIM/Camera and returns its SHA-256."""
        self.files[remote_path] = data
        return hashlib.sha256(data).hexdigest()

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def list_camera_media(self) -> List[Dict[str, Any]]:
        """Emulates `adb shell ls -l /sdcard/DCIM/Camera`."""
        if not self.connected:
            raise ConnectionError(f"Device {self.serial} is offline.")
        results = []
        for path, data in self.files.items():
            name = Path(path).name
            results.append({
                "path": path,
                "name": name,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
        return results

    def compute_remote_hash(self, remote_path: str) -> str:
        """Emulates `adb shell sha256sum <path>`."""
        if not self.connected:
            raise ConnectionError(f"Device {self.serial} is offline.")
        if remote_path not in self.files:
            raise FileNotFoundError(f"Remote file {remote_path} not found.")
        return hashlib.sha256(self.files[remote_path]).hexdigest()

    def pull_file_stream(self, remote_path: str, chunk_size: int = 1024 * 1024) -> bytes:
        """Pulls raw bytes with zero compression."""
        self.call_count += 1
        if not self.connected:
            raise ConnectionError("Socket closed during ADB transfer.")
        if remote_path not in self.files:
            raise FileNotFoundError(f"Remote file {remote_path} does not exist.")
        return self.files[remote_path]


class MockSQLiteManifestStore:
    """SQLite-backed manifest database store with WAL concurrency."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, timeout=10.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA busy_timeout = 5000;")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS media_manifest (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                device_sha256 TEXT NOT NULL,
                local_sha256 TEXT,
                gcs_uri TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                uploaded_at TEXT,
                error_message TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_manifest_status ON media_manifest(status);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_manifest_device_hash ON media_manifest(device_sha256);")
        self.conn.commit()

    def record_pending(self, file_path: str, file_name: str, file_size: int, device_sha256: str) -> int:
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO media_manifest (file_path, file_name, file_size, device_sha256, status)
            VALUES (?, ?, ?, ?, 'PENDING')
            ON CONFLICT(file_path) DO UPDATE SET
                file_size=excluded.file_size,
                device_sha256=excluded.device_sha256,
                updated_at=CURRENT_TIMESTAMP;
        """, (file_path, file_name, file_size, device_sha256))
        self.conn.commit()
        return cur.lastrowid

    def update_status(self, file_path: str, status: ManifestStatus, **kwargs) -> bool:
        fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params: List[Any] = [status.value]
        for k, v in kwargs.items():
            fields.append(f"{k} = ?")
            params.append(v)
        params.append(file_path)
        cur = self.conn.cursor()
        cur.execute(f"UPDATE media_manifest SET {', '.join(fields)} WHERE file_path = ?;", params)
        self.conn.commit()
        return cur.rowcount > 0

    def get_record(self, file_path: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM media_manifest WHERE file_path = ?;", (file_path,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_records(self, status: Optional[ManifestStatus] = None) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        if status:
            cur.execute("SELECT * FROM media_manifest WHERE status = ? ORDER BY id ASC;", (status.value,))
        else:
            cur.execute("SELECT * FROM media_manifest ORDER BY id ASC;")
        return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()


class MockGCSClient:
    """Emulates Google Cloud Storage bucket operations."""

    def __init__(self, bucket_name: str = "edm-media-vault"):
        self.bucket_name = bucket_name
        self.storage: Dict[str, Dict[str, Any]] = {}

    def upload_from_bytes(self, destination_blob_name: str, data: bytes, metadata: Optional[Dict[str, str]] = None) -> str:
        sha256_hash = hashlib.sha256(data).hexdigest()
        gcs_uri = f"gs://{self.bucket_name}/{destination_blob_name}"
        self.storage[gcs_uri] = {
            "data": data,
            "size": len(data),
            "sha256": sha256_hash,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return gcs_uri

    def upload_from_file(self, destination_blob_name: str, file_path: str, metadata: Optional[Dict[str, str]] = None) -> str:
        with open(file_path, "rb") as f:
            data = f.read()
        return self.upload_from_bytes(destination_blob_name, data, metadata)

    def download_as_bytes(self, gcs_uri: str) -> bytes:
        if gcs_uri not in self.storage:
            raise FileNotFoundError(f"Blob {gcs_uri} not found in GCS.")
        return self.storage[gcs_uri]["data"]

    def get_blob_metadata(self, gcs_uri: str) -> Dict[str, Any]:
        if gcs_uri not in self.storage:
            raise FileNotFoundError(f"Blob {gcs_uri} not found in GCS.")
        return self.storage[gcs_uri]

    def exists(self, gcs_uri: str) -> bool:
        return gcs_uri in self.storage


class MockGeminiOmniClient:
    """Emulates Gemini Multimodal Video Understanding API with DLQ & retry simulation."""

    def __init__(self, failure_rate: float = 0.0, simulate_rate_limit: bool = False):
        self.failure_rate = failure_rate
        self.simulate_rate_limit = simulate_rate_limit
        self.dlq_records: List[Dict[str, Any]] = []
        self.call_history: List[Dict[str, Any]] = []

    def grade_video(self, video_id: str, gcs_uri: str, duration_seconds: float = 30.0, forced_scores: Optional[ViralParameterScores] = None) -> EDMShortsViralMetrics:
        self.call_history.append({"video_id": video_id, "gcs_uri": gcs_uri, "timestamp": datetime.now(timezone.utc).isoformat()})
        
        if self.simulate_rate_limit:
            err = {"error": "RESOURCE_EXHAUSTED", "code": 429, "video_id": video_id, "gcs_uri": gcs_uri}
            self.dlq_records.append(err)
            raise RuntimeError(f"Gemini API 429 Quota Exceeded for {gcs_uri}")

        if forced_scores:
            scores = forced_scores
        else:
            # Deterministic pseudo-scores derived from video_id hash
            h = int(hashlib.md5(video_id.encode()).hexdigest()[:8], 16)
            hrv = round(60.0 + (h % 35), 1)
            dpaw = round(65.0 + ((h >> 2) % 30), 1)
            adr_sfd = round(70.0 + ((h >> 4) % 25), 1)
            cke_mve = round(55.0 + ((h >> 6) % 40), 1)
            ltss = round(60.0 + ((h >> 8) % 35), 1)
            scores = ViralParameterScores(
                hrv=hrv,
                dpaw=dpaw,
                adr_sfd=adr_sfd,
                cke_mve=cke_mve,
                ltss=ltss,
            )

        evpi = calculate_evpi(scores)
        verdict = get_verdict_from_evpi(evpi)

        return EDMShortsViralMetrics(
            video_id=video_id,
            gcs_uri=gcs_uri,
            duration_seconds=duration_seconds,
            aspect_ratio="9:16",
            scores=scores,
            evpi_composite=evpi,
            trending_verdict=verdict,
        )


class MockPySparkGradingEngine:
    """Emulates Dataproc Serverless PySpark batch video grading job."""

    def __init__(self, gemini_client: MockGeminiOmniClient, gcs_client: MockGCSClient):
        self.gemini = gemini_client
        self.gcs = gcs_client
        self.processed_jobs: List[Dict[str, Any]] = []

    def execute_batch_job(self, video_records: List[Dict[str, Any]], weights: Optional[ModelParameterWeights] = None) -> List[EDMShortsViralMetrics]:
        results: List[EDMShortsViralMetrics] = []
        for rec in video_records:
            vid = rec["video_id"]
            uri = rec["gcs_uri"]
            duration = rec.get("duration_seconds", 30.0)
            
            # Verify asset exists in GCS
            if not self.gcs.exists(uri):
                raise FileNotFoundError(f"GCS URI {uri} not found during PySpark partition processing.")
            
            metric = self.gemini.grade_video(video_id=vid, gcs_uri=uri, duration_seconds=duration)
            if weights:
                recalc_evpi = calculate_evpi(metric.scores, weights)
                metric.evpi_composite = recalc_evpi
                metric.trending_verdict = get_verdict_from_evpi(recalc_evpi)
            results.append(metric)

        self.processed_jobs.append({
            "job_id": f"spark-job-{int(time.time()*1000)}",
            "batch_size": len(video_records),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        return results


class MockBigQueryMLEngine:
    """Emulates BigQuery table storage and BQML CREATE MODEL / ML.WEIGHTS execution."""

    def __init__(self):
        self.tables: Dict[str, List[Dict[str, Any]]] = {
            "media_pipeline.video_grades": [],
            "media_pipeline.model_parameter_weights": [],
        }
        self.models: Dict[str, Dict[str, Any]] = {}
        self._init_default_weights()

    def _init_default_weights(self) -> None:
        default_w = ModelParameterWeights(version_id="v1.0.0_baseline")
        self.tables["media_pipeline.model_parameter_weights"].append(default_w.model_dump())

    def sink_video_grades(self, metrics: List[Union[EDMShortsViralMetrics, Dict[str, Any]]]) -> int:
        count = 0
        for m in metrics:
            if isinstance(m, dict):
                self.tables["media_pipeline.video_grades"].append(dict(m))
                count += 1
                continue
            row = BigQueryVideoGrade(
                video_id=m.video_id,
                gcs_uri=m.gcs_uri,
                processed_timestamp=m.graded_at,
                duration_seconds=m.duration_seconds,
                aspect_ratio=m.aspect_ratio,
                hrv_score=m.scores.hrv,
                dpaw_score=m.scores.dpaw,
                adr_sfd_score=m.scores.adr_sfd,
                cke_mve_score=m.scores.cke_mve,
                ltss_score=m.scores.ltss,
                evpi_composite=m.evpi_composite,
                trending_verdict=m.trending_verdict.value if hasattr(m.trending_verdict, "value") else str(m.trending_verdict),
            ).model_dump()
            self.tables["media_pipeline.video_grades"].append(row)
            count += 1
        return count

    def update_post_telemetry(
        self,
        video_id: str,
        vvsa_rate: float,
        apv: float,
        viral_status: int,
        share_count: Optional[int] = None,
        completion_rate: Optional[float] = None,
    ) -> bool:
        for row in self.tables["media_pipeline.video_grades"]:
            if row["video_id"] == video_id:
                row["actual_vvsa_rate"] = vvsa_rate
                row["actual_avg_percentage_viewed"] = apv
                row["actual_viral_status"] = viral_status
                if share_count is not None:
                    row["actual_share_count"] = share_count
                if completion_rate is not None:
                    row["actual_completion_rate"] = completion_rate
                return True
        return False

    def execute_create_model(self, model_name: str, model_type: str, query_sql: str) -> Dict[str, Any]:
        """Simulates BQML CREATE OR REPLACE MODEL."""
        supported_types = {"BOOSTED_TREE_REGRESSOR", "LINEAR_REG", "KMEANS"}
        if model_type.upper() not in supported_types:
            raise ValueError(f"Unsupported model type {model_type}. Supported: {supported_types}")

        # Ensure we have data
        grades = self.tables["media_pipeline.video_grades"]
        if not grades:
            raise ValueError("Cannot train BQML model on empty video_grades table.")

        model_info = {
            "model_name": model_name,
            "model_type": model_type.upper(),
            "query_sql": query_sql,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "training_row_count": len(grades),
            "r2_score": 0.88,
        }
        self.models[model_name] = model_info
        return model_info

    def extract_ml_weights(self, model_name: str) -> ModelParameterWeights:
        """Simulates ML.WEIGHTS or ML.FEATURE_IMPORTANCE extraction and weight normalization."""
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} does not exist.")

        # Simulate dynamic feature weights based on learned regression coefficients
        # e.g., HRV and DPAW get higher weights if VVSA is correlated
        raw_weights = {
            "weight_hrv": 0.30,
            "weight_dpaw": 0.28,
            "weight_adr_sfd": 0.18,
            "weight_cke_mve": 0.12,
            "weight_ltss": 0.12,
        }
        # Normalization
        tot = sum(raw_weights.values())
        norm = {k: round(v / tot, 4) for k, v in raw_weights.items()}
        # Minor adjustment for floating point precision to exactly 1.0
        norm["weight_hrv"] = round(1.0 - sum(v for k, v in norm.items() if k != "weight_hrv"), 4)

        new_weights = ModelParameterWeights(
            version_id=f"v_{model_name}_{int(time.time())}",
            weight_hrv=norm["weight_hrv"],
            weight_dpaw=norm["weight_dpaw"],
            weight_adr_sfd=norm["weight_adr_sfd"],
            weight_cke_mve=norm["weight_cke_mve"],
            weight_ltss=norm["weight_ltss"],
            model_r2_score=self.models[model_name]["r2_score"],
            is_active=True,
        )

        # Deactivate previous weights and append new active weight row
        for row in self.tables["media_pipeline.model_parameter_weights"]:
            row["is_active"] = False
        self.tables["media_pipeline.model_parameter_weights"].append(new_weights.model_dump())
        return new_weights

    def get_active_weights(self) -> ModelParameterWeights:
        for row in reversed(self.tables["media_pipeline.model_parameter_weights"]):
            if row.get("is_active", True):
                return ModelParameterWeights(**row)
        return ModelParameterWeights()


# ============================================================================
# 4. PYTEST FIXTURES
# ============================================================================

@pytest.fixture
def sample_raw_mp4_bytes() -> bytes:
    """Generates a deterministic 1MB test binary video stream."""
    header = b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41"
    body = b"EDM_4K_60FPS_RAW_PAYLOAD_TEST_DATA_" * 30000
    return header + body


@pytest.fixture
def sample_raw_mp4_hash(sample_raw_mp4_bytes: bytes) -> str:
    """Returns expected SHA-256 hex digest for sample_raw_mp4_bytes."""
    return hashlib.sha256(sample_raw_mp4_bytes).hexdigest()


@pytest.fixture
def mock_adb(sample_raw_mp4_bytes: bytes) -> MockAdbDevice:
    """Provides a configured Mock ADB Device with sample 4K video files."""
    adb = MockAdbDevice()
    adb.add_remote_file("/sdcard/DCIM/Camera/20260824_UltraMiami_MartinGarrix_V1.mp4", sample_raw_mp4_bytes)
    adb.add_remote_file("/sdcard/DCIM/Camera/20260824_EDCLasVegas_Subtronics_V2.mp4", sample_raw_mp4_bytes + b"_extra_frame")
    return adb


@pytest.fixture
def mock_manifest(tmp_path: Path) -> MockSQLiteManifestStore:
    """Provides an isolated SQLite manifest store."""
    db_file = str(tmp_path / "test_media_manifest.db")
    store = MockSQLiteManifestStore(db_file)
    yield store
    store.close()


@pytest.fixture
def mock_gcs() -> MockGCSClient:
    """Provides a Mock Google Cloud Storage client."""
    return MockGCSClient(bucket_name="edm-media-vault")


@pytest.fixture
def mock_gemini() -> MockGeminiOmniClient:
    """Provides a Mock Gemini Multimodal Video client."""
    return MockGeminiOmniClient()


@pytest.fixture
def mock_spark(mock_gemini: MockGeminiOmniClient, mock_gcs: MockGCSClient) -> MockPySparkGradingEngine:
    """Provides a Mock PySpark Dataproc Serverless batch grading engine."""
    return MockPySparkGradingEngine(gemini_client=mock_gemini, gcs_client=mock_gcs)


@pytest.fixture
def mock_bqml() -> MockBigQueryMLEngine:
    """Provides a Mock BigQuery ML Engine with storage and weight extraction."""
    return MockBigQueryMLEngine()
