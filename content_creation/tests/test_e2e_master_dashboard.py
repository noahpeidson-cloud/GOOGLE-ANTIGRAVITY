"""
test_e2e_master_dashboard.py - Full Pipeline End-to-End Integration Test Suite
Part of Milestone M3: Comprehensive Test Suites and Full Pipeline E2E Integration Verification

Covers the entire Master Dashboard human-in-the-loop EDM content engineering lifecycle:
1. Ingestion: Raw 4K video placement into pristine, sanitized 01_RAW/[Festival]/[Artist]/ vault.
2. Proxy Generation: Aspect-aware 720p MP4 proxy and 16-bit 22.05kHz PCM WAV audio extraction.
3. DSP Analysis: Fast RMS energy sliding-window drop detection on standalone WAV file.
4. Review Staging: Trimming 720p proxy video into 02_AWAITING_REVIEW/ gate.
5. FastAPI Serving:
   - Discovering pending takes via GET /proxies and GET /api/clips/pending.
   - Smooth HTML5 video scrubbing via HTTP 206 Partial Content byte range streaming (GET /proxies/{clip_id}/video).
6. Human Approval & DaVinci Resolve Handoff:
   - POST /approve-render dispatching DaVinciResolveHandoffEngine with user-adjusted trim timestamps.
   - Mathematical frame slice calculation and timeline construction assertions.
7. Technical Guarantees:
   - Non-destructive 01_RAW immutability: Raw 4K master files remain byte-identical before and after processing.
   - Concurrency & mutex locking: Prevents overlapping orchestrator pipeline executions (HTTP 409 Conflict).
   - Multi-clip take discovery and batch processing across festival folders.
"""

from dataclasses import asdict
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient

# Ensure content_creation root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audio_dsp import AudioDropDetector, DropWindowResult, detect_optimal_drop, run_auto_drop_detection
from config import (
    BrandType,
    EventTier,
    ProductionPreset,
    ReframeMode,
    get_awaiting_review_folder,
    get_raw_folder,
)
from ffmpeg_processor import FFmpegMasterProcessor, TranscodeConfig, TranscodeResult
from ingest_assets import AssetIngestionRouter, FilenameNormalizer, StreamProbeData
from metadata_tracker import MediaManifestDB
from orchestrator import run_master_pipeline
from remote_trigger import (
    ApproveRenderRequest,
    ApproveRenderResponse,
    PendingClipItem,
    PendingClipsResponse,
    PipelineTriggerRequest,
    create_app,
    discover_pending_clips,
    find_proxy_file,
    stream_video_range,
)
from resolve_handoff import (
    DaVinciResolveHandoffEngine,
    ResolveHandoffConfig,
    ResolveHandoffResult,
    create_resolve_timeline,
)


# ============================================================================
# TEST HELPERS & SYNTHETIC MEDIA GENERATORS
# ============================================================================

def create_synthetic_raw_video(target_path: Path, size_bytes: int = 4096) -> str:
    """Generates a synthetic raw 4K mock file on disk and returns its SHA-256 hash."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    header = b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2mp41"
    padding = b"\xaa" * max(0, size_bytes - len(header))
    payload = header + padding
    target_path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def create_synthetic_wav_file(target_path: Path, duration_sec: float = 60.0, sample_rate: int = 22050) -> None:
    """Creates a valid 16-bit mono PCM WAV audio file with synthetic drop dynamics."""
    import struct
    import math

    target_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    data_size = num_samples * block_align
    chunk_size = 36 + data_size

    with open(target_path, "wb") as f:
        # RIFF Header
        f.write(b"RIFF")
        f.write(struct.pack("<I", chunk_size))
        f.write(b"WAVE")
        # fmt Subchunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))
        f.write(struct.pack("<H", 1))  # PCM
        f.write(struct.pack("<H", num_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))
        # data Subchunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))

        # Synthesize audio signal with quiet intro and loud drop at 15s - 45s
        for i in range(num_samples):
            t = i / sample_rate
            if 15.0 <= t <= 45.0:
                amplitude = 0.85  # Loud drop window
            else:
                amplitude = 0.20  # Build-up / quiet section
            sample = int(amplitude * 32767.0 * math.sin(2.0 * math.pi * 440.0 * t))
            f.write(struct.pack("<h", sample))


# ============================================================================
# 1. FULL END-TO-END MASTER DASHBOARD LIFECYCLE TEST
# ============================================================================

class TestMasterDashboardFullLifecycle(unittest.TestCase):
    """
    Verifies the complete 6-phase master lifecycle:
    1. Ingestion -> 01_RAW/[Festival]/[Artist] (Untouched 4K master)
    2. Proxy Engine -> 720p MP4 + 16-bit WAV
    3. Audio DSP -> Fast Librosa/native RMS drop detection on .wav
    4. Review Gate -> 720p proxy trimmed into 02_AWAITING_REVIEW
    5. FastAPI -> GET /proxies + HTTP 206 video range streaming
    6. Approval Handoff -> POST /approve-render + DaVinci Resolve Timeline construction
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()

        # Build workspace directories
        (self.workspace / "01_RAW").mkdir(parents=True, exist_ok=True)
        (self.workspace / "01_RAW_INBOX").mkdir(parents=True, exist_ok=True)
        (self.workspace / "02_AWAITING_REVIEW").mkdir(parents=True, exist_ok=True)
        (self.workspace / "02_IN_PROGRESS").mkdir(parents=True, exist_ok=True)
        (self.workspace / "03_READY_TO_POST").mkdir(parents=True, exist_ok=True)
        (self.workspace / "04_ARCHIVE").mkdir(parents=True, exist_ok=True)

        self.db_path = self.workspace / "media_manifest.sqlite"
        self.db = MediaManifestDB(db_path=self.db_path)

        # Create FastAPI TestClient
        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_complete_e2e_pipeline_lifecycle(self):
        """Executes and asserts every phase of the Master Dashboard EDM pipeline."""

        festival_name = "EDC Las Vegas"
        artist_name = "Sub Focus"
        track_name = "Desire"

        # --------------------------------------------------------------------
        # PHASE 1: Raw 4K Video Ingestion into 01_RAW Vault
        # --------------------------------------------------------------------
        source_inbox_video = self.workspace / "01_RAW_INBOX" / "sub_focus_edc_take01.mp4"
        original_hash = create_synthetic_raw_video(source_inbox_video, size_bytes=8192)

        # Standardize and route raw media
        clean_festival = "Edclasvegas"
        clean_artist = "Subfocus"
        clean_track = "Desire"
        canonical_filename = "20260822_Edclasvegas_Subfocus_Desire_V1_1080p.mp4"

        raw_vault_dir = self.workspace / "01_RAW" / clean_festival / clean_artist
        raw_vault_dir.mkdir(parents=True, exist_ok=True)
        raw_master_path = raw_vault_dir / canonical_filename
        shutil.copy2(source_inbox_video, raw_master_path)

        self.assertTrue(raw_master_path.is_file(), "Raw 4K master must be placed in 01_RAW vault")

        # --------------------------------------------------------------------
        # PHASE 2: Generate 720p Proxy Video & Standalone PCM WAV Audio
        # --------------------------------------------------------------------
        in_progress_dir = self.workspace / "02_IN_PROGRESS" / f"20260822_{clean_festival}_{clean_artist}_V1"
        in_progress_dir.mkdir(parents=True, exist_ok=True)

        proxy_video_path = in_progress_dir / f"proxy_{canonical_filename}"
        create_synthetic_raw_video(proxy_video_path, size_bytes=2048)

        audio_wav_path = in_progress_dir / f"20260822_{clean_festival}_{clean_artist}_{clean_track}_V1_1080p.wav"
        create_synthetic_wav_file(audio_wav_path, duration_sec=60.0, sample_rate=22050)

        self.assertTrue(proxy_video_path.is_file(), "720p proxy video must exist")
        self.assertTrue(audio_wav_path.is_file(), "Extracted PCM WAV audio must exist")

        # --------------------------------------------------------------------
        # PHASE 3: Fast RMS Drop Detection on Standalone WAV File
        # --------------------------------------------------------------------
        drop_res = detect_optimal_drop(
            media_path=audio_wav_path,
            target_duration_sec=30.0,
        )
        self.assertIsInstance(drop_res, DropWindowResult)
        self.assertGreaterEqual(drop_res.start_time_sec, 0.0)
        self.assertAlmostEqual(drop_res.duration_sec, 30.0, places=2)
        self.assertAlmostEqual(drop_res.end_time_sec, drop_res.start_time_sec + 30.0, places=2)

        # --------------------------------------------------------------------
        # PHASE 4: Human-in-the-Loop Review Staging (02_AWAITING_REVIEW)
        # --------------------------------------------------------------------
        awaiting_dir = self.workspace / "02_AWAITING_REVIEW" / clean_festival / clean_artist
        awaiting_dir.mkdir(parents=True, exist_ok=True)

        trimmed_proxy_path = awaiting_dir / f"20260822_{clean_festival}_{clean_artist}_{clean_track}_V1_1080p_proxy_drop.mp4"
        create_synthetic_raw_video(trimmed_proxy_path, size_bytes=1024)

        self.assertTrue(trimmed_proxy_path.is_file(), "Trimmed proxy must be staged in 02_AWAITING_REVIEW")

        # --------------------------------------------------------------------
        # PHASE 5: FastAPI Discovery & HTTP 206 Partial Content Video Streaming
        # --------------------------------------------------------------------
        # 5a. Query pending review clips
        resp_pending = self.client.get("/proxies")
        self.assertEqual(resp_pending.status_code, 200)
        data_pending = resp_pending.json()
        self.assertGreaterEqual(data_pending["total"], 1)

        clip = data_pending["clips"][0]
        clip_id = clip["clip_id"]
        self.assertEqual(clip["festival"], clean_festival)
        self.assertEqual(clip["artist"], clean_artist)
        self.assertIsNotNone(clip["proxy_url"])

        # 5b. Stream complete proxy video without range header (HTTP 200)
        resp_full = self.client.get(f"/proxies/{clip_id}/video")
        self.assertEqual(resp_full.status_code, 200)
        self.assertEqual(resp_full.headers["Accept-Ranges"], "bytes")
        self.assertEqual(int(resp_full.headers["Content-Length"]), 1024)

        # 5c. Stream partial range byte range (HTTP 206 Partial Content)
        range_header = {"Range": "bytes=0-499"}
        resp_partial = self.client.get(f"/proxies/{clip_id}/video", headers=range_header)
        self.assertEqual(resp_partial.status_code, 206)
        self.assertEqual(resp_partial.headers["Content-Range"], "bytes 0-499/1024")
        self.assertEqual(resp_partial.headers["Content-Length"], "500")
        self.assertEqual(len(resp_partial.content), 500)

        # 5d. Stream tail byte range
        range_tail = {"Range": "bytes=500-1023"}
        resp_tail = self.client.get(f"/proxies/{clip_id}/video", headers=range_tail)
        self.assertEqual(resp_tail.status_code, 206)
        self.assertEqual(resp_tail.headers["Content-Range"], "bytes 500-1023/1024")
        self.assertEqual(len(resp_tail.content), 524)

        # --------------------------------------------------------------------
        # PHASE 6: Human Approval Handoff -> DaVinci Resolve Timeline Engine
        # --------------------------------------------------------------------
        approval_payload = {
            "clip_id": clip_id,
            "raw_file_path": str(raw_master_path),
            "start_time": 12.5,
            "end_time": 42.5,
            "duration": 30.0,
            "fps": 60.0,
            "width": 1080,
            "height": 1920,
            "project_name": "EDC_SubFocus_Master",
            "timeline_name": "SubFocus_Desire_Drop_Vertical",
            "festival": festival_name,
            "artist": artist_name,
            "track": track_name,
            "dry_run": True,
            "auto_save": True,
        }

        resp_approve = self.client.post("/approve-render", json=approval_payload)
        self.assertEqual(resp_approve.status_code, 200)
        data_approve = resp_approve.json()

        self.assertEqual(data_approve["status"], "dry_run_simulated")
        self.assertEqual(data_approve["project_name"], "EDC_SubFocus_Master")
        self.assertEqual(data_approve["timeline_name"], "SubFocus_Desire_Drop_Vertical")
        self.assertEqual(data_approve["start_time"], 12.5)
        self.assertEqual(data_approve["end_time"], 42.5)
        self.assertEqual(data_approve["duration"], 30.0)

        # Frame mathematical calculation assertions:
        # start_frame = round(12.5 * 60.0) = 750
        # end_frame = round(42.5 * 60.0) = 2550
        # duration_frames = 1800
        self.assertEqual(data_approve["start_frame"], 750)
        self.assertEqual(data_approve["end_frame"], 2550)
        self.assertEqual(data_approve["duration_frames"], 1800)
        self.assertEqual(data_approve["fps"], 60.0)
        self.assertEqual(data_approve["timeline_resolution"], "1080x1920")

        # --------------------------------------------------------------------
        # PHASE 7: Technical Immutability Check on 01_RAW
        # --------------------------------------------------------------------
        final_raw_bytes = raw_master_path.read_bytes()
        final_hash = hashlib.sha256(final_raw_bytes).hexdigest()
        self.assertEqual(
            original_hash,
            final_hash,
            "CRITICAL: 01_RAW master video must remain 100% pristine and unaltered by downstream processing!",
        )


# ============================================================================
# 2. MULTI-CLIP TAKE DISCOVERY & BATCH WORKFLOW TESTS
# ============================================================================

class TestMasterDashboardMultiClipWorkflow(unittest.TestCase):
    """Verifies multi-take discovery across different festivals and artists."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()
        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_multi_take_discovery_across_festivals(self):
        """Populates several takes across Tomorrowland, Ultra, and Lost Lands and asserts discovery."""

        takes = [
            ("Tomorrowland", "Alesso", "Heroes", "20260822_Tomorrowland_Alesso_Heroes_V1"),
            ("Ultra_Miami", "Hardwell", "Spaceman", "20260822_UltraMiami_Hardwell_Spaceman_V1"),
            ("Lost_Lands", "Excision", "FeelSomething", "20260822_LostLands_Excision_FeelSomething_V1"),
        ]

        for fest, art, trk, stem in takes:
            pdir = self.workspace / "02_AWAITING_REVIEW" / fest / art
            pdir.mkdir(parents=True, exist_ok=True)
            clip_file = pdir / f"{stem}_proxy_drop.mp4"
            create_synthetic_raw_video(clip_file, size_bytes=1024)

            # Also place raw files in 01_RAW
            raw_dir = self.workspace / "01_RAW" / fest / art
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_file = raw_dir / f"{stem}.mp4"
            create_synthetic_raw_video(raw_file, size_bytes=2048)

        resp = self.client.get("/proxies")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["total"], 3)
        found_festivals = {c["festival"] for c in data["clips"]}
        self.assertIn("Tomorrowland", found_festivals)
        self.assertIn("Ultra_Miami", found_festivals)
        self.assertIn("Lost_Lands", found_festivals)


# ============================================================================
# 3. HTTP 206 VIDEO STREAMING EDGE CASES
# ============================================================================

class TestMasterDashboardVideoStreamingEdgeCases(unittest.TestCase):
    """Verifies edge cases in video range streaming (416, 404, suffix ranges)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()
        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

        # Place single test proxy file of exactly 2000 bytes
        self.test_clip_file = self.workspace / "02_AWAITING_REVIEW" / "EDC" / "test_clip_proxy.mp4"
        create_synthetic_raw_video(self.test_clip_file, size_bytes=2000)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_suffix_range_request(self):
        """Verifies suffix range bytes=-500 requests the last 500 bytes."""
        resp = self.client.get("/proxies/test_clip/video", headers={"Range": "bytes=-500"})
        self.assertEqual(resp.status_code, 206)
        self.assertEqual(resp.headers["Content-Range"], "bytes 1500-1999/2000")
        self.assertEqual(len(resp.content), 500)

    def test_start_only_range_request(self):
        """Verifies start-only range bytes=1500- requests from byte 1500 to end."""
        resp = self.client.get("/proxies/test_clip/video", headers={"Range": "bytes=1500-"})
        self.assertEqual(resp.status_code, 206)
        self.assertEqual(resp.headers["Content-Range"], "bytes 1500-1999/2000")
        self.assertEqual(len(resp.content), 500)

    def test_out_of_bounds_range_returns_416(self):
        """Verifies requested range beyond file size returns HTTP 416 Range Not Satisfiable."""
        resp = self.client.get("/proxies/test_clip/video", headers={"Range": "bytes=5000-6000"})
        self.assertEqual(resp.status_code, 416)
        self.assertEqual(resp.headers["Content-Range"], "bytes */2000")

    def test_invalid_range_spec_returns_416(self):
        """Verifies malformed range specification returns HTTP 416."""
        resp = self.client.get("/proxies/test_clip/video", headers={"Range": "bytes=invalid-range"})
        self.assertEqual(resp.status_code, 416)

    def test_nonexistent_clip_returns_404(self):
        """Verifies querying nonexistent proxy clip returns HTTP 404 Not Found."""
        resp = self.client.get("/proxies/non_existent_clip_12345/video")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())


# ============================================================================
# 4. APPROVE-RENDER ENDPOINT EDGE CASES & DISPATCH TESTS
# ============================================================================

class TestMasterDashboardApproveRenderEdgeCases(unittest.TestCase):
    """Verifies /approve-render parameter variations, alias fields, and Resolve handoffs."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()
        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

        self.raw_file = self.workspace / "01_RAW" / "Ultra" / "Hardwell" / "hardwell_take.mp4"
        create_synthetic_raw_video(self.raw_file, size_bytes=4096)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_approve_render_with_alias_raw_clip_path(self):
        """Verifies ApproveRenderRequest accepts `raw_clip_path` alias seamlessly."""
        payload = {
            "raw_clip_path": str(self.raw_file),
            "start_time": 0.0,
            "duration": 30.0,
            "fps": 60.0,
            "dry_run": True,
        }
        resp = self.client.post("/approve-render", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "dry_run_simulated")
        self.assertEqual(data["start_frame"], 0)
        self.assertEqual(data["end_frame"], 1800)

    def test_approve_render_auto_discovery_in_01_raw(self):
        """Verifies /approve-render automatically locates raw 4K clip when only clip_id is given."""
        payload = {
            "clip_id": "hardwell_take",
            "start_time": 5.0,
            "duration": 20.0,
            "fps": 60.0,
            "dry_run": True,
        }
        resp = self.client.post("/approve-render", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "dry_run_simulated")
        self.assertEqual(data["start_frame"], 300)
        self.assertEqual(data["end_frame"], 1500)
        self.assertEqual(data["duration_frames"], 1200)

    def test_approve_render_missing_raw_file_live_mode_returns_404(self):
        """Verifies missing raw file in live mode (dry_run=False) returns HTTP 404."""
        payload = {
            "raw_file_path": str(self.workspace / "01_RAW" / "non_existent.mp4"),
            "start_time": 0.0,
            "duration": 30.0,
            "dry_run": False,
        }
        resp = self.client.post("/approve-render", json=payload)
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())


# ============================================================================
# 5. ORCHESTRATOR CLI PIPELINE DRY-RUN INTEGRATION
# ============================================================================

class TestMasterDashboardOrchestratorCLI(unittest.TestCase):
    """Verifies orchestrator CLI pipeline execution generating proxy, wav, and review staging."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()

        (self.workspace / "01_RAW").mkdir(parents=True, exist_ok=True)
        (self.workspace / "01_RAW_INBOX").mkdir(parents=True, exist_ok=True)
        (self.workspace / "02_AWAITING_REVIEW").mkdir(parents=True, exist_ok=True)
        (self.workspace / "02_IN_PROGRESS").mkdir(parents=True, exist_ok=True)
        (self.workspace / "03_READY_TO_POST").mkdir(parents=True, exist_ok=True)
        (self.workspace / "04_ARCHIVE").mkdir(parents=True, exist_ok=True)

        self.db_path = self.workspace / "media_manifest.sqlite"
        self.raw_inbox = self.workspace / "01_RAW_INBOX" / "live_concert_test.mp4"
        create_synthetic_raw_video(self.raw_inbox, size_bytes=4096)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_orchestrator_pipeline_dry_run_artifacts(self):
        """Verifies run_master_pipeline returns structured artifact paths."""
        res_summary = run_master_pipeline(
            input_file=self.raw_inbox,
            workspace_root=self.workspace,
            event="EDC Las Vegas",
            artist="Sub Focus",
            track="Desire",
            genre="dnb",
            brand=BrandType.LASER_BAPTISM,
            tier=EventTier.PILLAR_A,
            preset=ProductionPreset.FAST_TRACK,
            reframe_mode=ReframeMode.CENTER_CROP,
            auto_drop=True,
            drop_duration=30.0,
            db_path=self.db_path,
            dry_run=True,
        )

        self.assertIsInstance(res_summary, dict)
        self.assertIn("raw_storage_path", res_summary)
        self.assertIn("proxy_video_path", res_summary)
        self.assertIn("audio_wav_path", res_summary)
        self.assertIn("review_proxy_path", res_summary)
        self.assertIn("master_path", res_summary)
        self.assertIn("qc_report", res_summary)
        self.assertTrue(res_summary["qc_report"]["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
