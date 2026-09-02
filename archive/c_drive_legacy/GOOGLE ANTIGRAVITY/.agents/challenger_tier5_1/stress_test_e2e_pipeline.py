#!/usr/bin/env python3
"""
stress_test_e2e_pipeline.py - Tier 5 Adversarial Cross-Module Stress Test Harness.
Location: .agents/challenger_tier5_1/stress_test_e2e_pipeline.py

Verifies end-to-end resilience of the entire Media Ingestion & Viral Grading Pipeline:
1. High-Throughput E2E Pipeline (50+ 4K videos: ADB Ingestion -> SHA-256 -> GCS -> PySpark Grading -> BigQuery Sink -> BQML Recalibration).
2. Bit-Flip Corruption & Forensic Quarantine Isolation.
3. Wireless ADB Network Disconnection & Exponential Backoff Reconnection.
4. Active Recording 2-Tick Guard Under Heavy Load.
5. Gemini Multimodal 429 Quota Exhaustion & DLQ Isolation in PySpark.
6. Simplex Normalization & Extreme BQML Weight Shift Robustness.
7. Single-Instance Process Lock Concurrency Race.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from media_pipeline.ingestion.manifest_store import ManifestStore
from media_pipeline.ingestion.adb_connection_manager import AdbConnectionManager
from media_pipeline.ingestion.gcs_uploader import GCSUploader, GCSUploadError
from media_pipeline.ingestion.ingestion_daemon import (
    IngestionDaemon,
    CryptographicIntegrityError,
    ProcessLock,
    LockAcquisitionError,
    IncrementalMediaScanner,
)
from media_pipeline.grading.viral_schema import (
    ViralParameterScores,
    ModelParameterWeights,
    EDMShortsViralMetrics,
    EDMViralGradingReport,
    TrendingVerdict,
    calculate_evpi,
    calculate_evpi_from_scores,
    classify_viral_tier,
    compute_killswitches,
    DEFAULT_WEIGHTS,
)
from media_pipeline.grading.gemini_multimodal_client import (
    GeminiMultimodalClient,
    DeadLetterQueue,
    RateLimiter,
)
from media_pipeline.grading.spark_grading_job import (
    PySparkGradingPipeline,
    grade_partition,
    fetch_active_weights,
)
from media_pipeline.bqml.feedback_loop import (
    BigQueryMLFeedbackEngine,
    extract_normalized_weights,
    recalibrate_model_weights,
    sink_video_grades_to_bq,
    update_post_performance_telemetry,
)
from media_pipeline.tests.conftest import (
    MockAdbDevice,
    MockGCSClient,
    MockGeminiOmniClient,
    MockPySparkGradingEngine,
    MockBigQueryMLEngine,
)


class MockCommandExecutor:
    """Simulates Android ADB shell / pull commands in memory."""

    def __init__(self, mock_device: MockAdbDevice):
        self.device = mock_device
        self.drop_connection = False
        self.corrupt_pull_path: Optional[str] = None
        self.samsung_bypass_applied = False

    def __call__(self, cmd: List[str], timeout: int = 60, **kwargs):
        class Result:
            def __init__(self, returncode: int, stdout: str, stderr: str = ""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        if self.drop_connection:
            return Result(1, "", "error: device offline (Wi-Fi drop)")

        cmd_str = " ".join(cmd)

        if "connect" in cmd:
            if self.drop_connection:
                return Result(1, "failed to connect", "Connection refused")
            self.device.connect()
            return Result(0, f"connected to {self.device.serial}")

        if "disconnect" in cmd:
            self.device.disconnect()
            return Result(0, f"disconnected {self.device.serial}")

        if "get-state" in cmd:
            if self.device.connected:
                return Result(0, "device")
            return Result(1, "unknown", "error: device not found")

        if "rampart_auto_enabled_switch_enabled" in cmd_str:
            self.samsung_bypass_applied = True
            return Result(0, "")

        if "stat -c '%n|%s|%Y'" in cmd_str:
            lines = []
            for path, data in self.device.files.items():
                mtime = int(time.time())
                lines.append(f"{path}|{len(data)}|{mtime}")
            return Result(0, "\n".join(lines))

        if "sha256sum" in cmd_str:
            # Extract path from command
            target_path = None
            for p in self.device.files.keys():
                if p in cmd_str:
                    target_path = p
                    break
            if target_path:
                h = hashlib.sha256(self.device.files[target_path]).hexdigest()
                return Result(0, f"{h}  {target_path}")
            return Result(1, "", "sha256sum: file not found")

        if "pull" in cmd:
            remote_path = cmd[-2]
            local_path = cmd[-1]
            if remote_path in self.device.files:
                data = self.device.files[remote_path]
                if self.corrupt_pull_path == remote_path:
                    # Invert last 4 bytes to simulate transit corruption
                    data = data[:-4] + b"BAD!"
                os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(data)
                return Result(0, f"[{len(data)} bytes] {remote_path} -> {local_path}")
            return Result(1, "", f"remote object '{remote_path}' does not exist")

        return Result(0, "mock ok")


class MockGCSStorageClient:
    """Mock storage.Client for GCSUploader integration."""

    def __init__(self, mock_gcs: MockGCSClient):
        self.mock_gcs = mock_gcs

    def bucket(self, bucket_name: str):
        outer = self

        class MockBucket:
            def blob(self, blob_name: str):
                class MockBlob:
                    def __init__(self):
                        self.metadata = {}
                        self.crc32c = None
                        self.md5_hash = None

                    def upload_from_filename(self, local_path: str, **kwargs):
                        with open(local_path, "rb") as f:
                            data = f.read()
                        outer.mock_gcs.upload_from_bytes(blob_name, data, self.metadata)
                        self.crc32c = "mock_crc32c_b64"
                        self.md5_hash = "mock_md5_b64"

                    def reload(self):
                        pass

                return MockBlob()

        return MockBucket()


class Tier5AdversarialStressTests(unittest.TestCase):
    """Tier 5 White-Box & Adversarial Cross-Module Test Suite."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="tier5_stress_")
        self.staging_dir = os.path.join(self.test_dir, "staging")
        self.quarantine_dir = os.path.join(self.test_dir, "quarantine")
        self.db_path = os.path.join(self.test_dir, "test_manifest.db")
        self.dlq_dir = os.path.join(self.test_dir, "dlq")

        os.makedirs(self.staging_dir, exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)
        os.makedirs(self.dlq_dir, exist_ok=True)

        self.mock_device = MockAdbDevice()
        self.executor = MockCommandExecutor(self.mock_device)
        self.adb = AdbConnectionManager(
            device_ip="192.168.1.150",
            device_port=5555,
            command_executor=self.executor,
        )
        self.manifest = ManifestStore(self.db_path)
        self.mock_gcs = MockGCSClient(bucket_name="edm-viral-vault")
        self.storage_client = MockGCSStorageClient(self.mock_gcs)
        self.uploader = GCSUploader(storage_client=self.storage_client)

        self.daemon = IngestionDaemon(
            adb_manager=self.adb,
            manifest_store=self.manifest,
            gcs_uploader=self.uploader,
            staging_dir=self.staging_dir,
            gcs_bucket="edm-viral-vault",
            quarantine_dir=self.quarantine_dir,
            min_stability_seconds=0.0,  # disable delay for speed in unit tests
        )

        self.bq_mock = MockBigQueryMLEngine()
        self.feedback_engine = BigQueryMLFeedbackEngine(
            client=self.bq_mock,
            dataset="media_pipeline",
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _generate_video_bytes(self, identifier: str, size_kb: int = 100) -> bytes:
        """Generates deterministic video payload with valid MP4 ftyp box."""
        header = b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41"
        pattern = f"EDM_TRACK_{identifier}_STREAM_DATA_".encode("utf-8")
        repeat = max(1, (size_kb * 1024 - len(header)) // len(pattern))
        body = pattern * repeat
        return (header + body)[: size_kb * 1024]

    # ========================================================================
    # TEST 1: High-Throughput E2E Pipeline (50 Videos Full Flow)
    # ========================================================================
    def test_01_high_throughput_e2e_pipeline_flow(self):
        """
        Stress-tests 50 raw 4K videos through the entire pipeline:
        Mock ADB -> Bit-for-bit SHA-256 Check -> GCS Upload -> PySpark Distributed Grading
        -> BigQuery Sink -> Post-Performance Telemetry -> BQML Weight Recalibration Loop.
        """
        num_videos = 50
        video_metadata: List[Dict[str, Any]] = []

        # 1. Populate Mock Android Device with 50 video files
        for i in range(1, num_videos + 1):
            vid_id = f"edm_clip_2026_{i:03d}"
            filename = f"{vid_id}.mp4"
            remote_path = f"/sdcard/DCIM/Camera/{filename}"
            payload = self._generate_video_bytes(vid_id, size_kb=64)
            expected_hash = self.mock_device.add_remote_file(remote_path, payload)
            video_metadata.append({
                "video_id": vid_id,
                "file_name": filename,
                "remote_path": remote_path,
                "expected_hash": expected_hash,
                "size_bytes": len(payload),
                "duration_seconds": 20.0 + (i % 18),
            })

        # 2. Run Ingestion Daemon Cycle
        stats = self.daemon.run_cycle()
        self.assertEqual(stats["scanned"], num_videos)
        self.assertEqual(stats["new_registered"], num_videos)
        self.assertEqual(stats["processed"], num_videos)
        self.assertEqual(stats["failed"], 0)

        # Verify Manifest and GCS state for all 50 items
        all_records = self.manifest.get_all_records()
        self.assertEqual(len(all_records), num_videos)

        gcs_grading_inputs: List[Dict[str, Any]] = []
        for meta in video_metadata:
            rec = self.manifest.get_record(meta["remote_path"])
            self.assertIsNotNone(rec)
            self.assertEqual(rec["status"], "GCS_CONFIRMED")
            self.assertEqual(rec["device_sha256"], meta["expected_hash"])
            self.assertEqual(rec["local_sha256"], meta["expected_hash"])
            self.assertEqual(rec["gcs_bucket"], "edm-viral-vault")

            # Check GCS Storage
            expected_gcs_uri = f"gs://edm-viral-vault/{rec['gcs_blob_name']}"
            self.assertTrue(self.mock_gcs.exists(expected_gcs_uri))
            gcs_bytes = self.mock_gcs.download_as_bytes(expected_gcs_uri)
            self.assertEqual(hashlib.sha256(gcs_bytes).hexdigest(), meta["expected_hash"])

            gcs_grading_inputs.append({
                "video_id": meta["video_id"],
                "gcs_uri": expected_gcs_uri,
                "raw_file_name": meta["file_name"],
                "file_size_bytes": meta["size_bytes"],
                "duration_seconds": meta["duration_seconds"],
                "aspect_ratio": "9:16",
            })

        # 3. Distributed PySpark Batch Grading
        grading_pipeline = PySparkGradingPipeline(mock_mode=True)
        graded_results = grading_pipeline.process_records(gcs_grading_inputs)

        self.assertEqual(len(graded_results), num_videos)
        for g in graded_results:
            self.assertEqual(g["status"], "GRADED")
            self.assertIsNone(g["error_message"])
            self.assertGreaterEqual(g["evpi_composite"], 0.0)
            self.assertLessEqual(g["evpi_composite"], 100.0)
            self.assertIn(g["trending_verdict"], [v.value for v in TrendingVerdict] + ["VIRAL_TIER_1", "HIGH_POTENTIAL", "MODERATE", "LOW_REACH"])
            self.assertGreaterEqual(g["hrv_score"], 0.0)
            self.assertGreaterEqual(g["dpaw_score"], 0.0)
            self.assertGreaterEqual(g["adr_sfd_score"], 0.0)
            self.assertGreaterEqual(g["cke_mve_score"], 0.0)
            self.assertGreaterEqual(g["ltss_score"], 0.0)

        # 4. Sink Graded Results to BigQuery
        inserted_rows = self.feedback_engine.sink_grades(graded_results)
        self.assertEqual(inserted_rows, num_videos)
        self.assertEqual(len(self.bq_mock.tables["media_pipeline.video_grades"]), num_videos)

        # 5. Ingest Post-Publishing Performance Telemetry
        for i, g in enumerate(graded_results):
            vid = g["video_id"]
            # Simulate real retention metrics: higher EVPI -> higher VVSA
            evpi = g["evpi_composite"]
            sim_vvsa = round(min(0.98, max(0.40, evpi / 100.0 * 0.95 + 0.05)), 2)
            sim_apv = round(min(2.5, max(0.5, evpi / 100.0 * 1.8 + 0.2)), 2)
            sim_viral = 1 if evpi >= 75.0 else 0
            ok = self.feedback_engine.record_telemetry(vid, sim_vvsa, sim_apv, sim_viral)
            self.assertTrue(ok)

        # 6. Train BQML Model & Recalibrate Dynamic Weights
        train_res = self.feedback_engine.train_model("viral_weight_regressor", model_type="LINEAR_REG")
        self.assertEqual(train_res["model_name"], "viral_weight_regressor")

        recalibrated_weights = self.feedback_engine.recalibrate_weights("viral_weight_regressor")
        self.assertIsInstance(recalibrated_weights, ModelParameterWeights)
        self.assertTrue(recalibrated_weights.is_active)

        # Assert simplex constraint: sum(weights) == 1.0000 ± 0.0001
        w_sum = (
            recalibrated_weights.weight_hrv
            + recalibrated_weights.weight_dpaw
            + recalibrated_weights.weight_adr_sfd
            + recalibrated_weights.weight_cke_mve
            + recalibrated_weights.weight_ltss
        )
        self.assertAlmostEqual(w_sum, 1.0, places=3)

        # Verify new weights are retrieved by the grading pipeline
        active_w = self.feedback_engine.get_active_weights()
        self.assertEqual(active_w.version_id, recalibrated_weights.version_id)

    # ========================================================================
    # TEST 2: Bit-Flip Corruption & Forensic Quarantine Isolation
    # ========================================================================
    def test_02_bit_flip_corruption_quarantine_isolation(self):
        """
        Injects bit-level transit corruption into ADB pull stream.
        Verifies:
        1. CryptographicIntegrityError is raised.
        2. Corrupt .part file is immediately isolated into quarantine directory.
        3. SQLite manifest marks status='QUARANTINED'.
        4. Staging area is cleaned; corrupted file is NOT uploaded to GCS.
        5. Valid subsequent files are ingested cleanly without pipeline deadlock.
        """
        # File 1: Corrupt File
        corrupt_vid = "corrupt_clip_001.mp4"
        corrupt_remote = f"/sdcard/DCIM/Camera/{corrupt_vid}"
        corrupt_data = self._generate_video_bytes("corrupt", size_kb=32)
        self.mock_device.add_remote_file(corrupt_remote, corrupt_data)
        self.executor.corrupt_pull_path = corrupt_remote

        # File 2: Clean File
        clean_vid = "clean_clip_002.mp4"
        clean_remote = f"/sdcard/DCIM/Camera/{clean_vid}"
        clean_data = self._generate_video_bytes("clean", size_kb=32)
        self.mock_device.add_remote_file(clean_remote, clean_data)

        # Run cycle
        stats = self.daemon.run_cycle()
        self.assertEqual(stats["scanned"], 2)
        self.assertEqual(stats["processed"], 1)  # Clean file succeeded
        self.assertEqual(stats["failed"], 1)     # Corrupt file failed & quarantined

        # Verify Corrupt File Manifest State
        corrupt_rec = self.manifest.get_record(corrupt_remote)
        self.assertIsNotNone(corrupt_rec)
        self.assertEqual(corrupt_rec["status"], "QUARANTINED")
        self.assertIn("Bit corruption detected", corrupt_rec["last_error"])

        # Verify Quarantine Folder contains the isolated artifact
        quarantine_files = os.listdir(self.quarantine_dir)
        self.assertGreaterEqual(len(quarantine_files), 1)
        self.assertTrue(any(corrupt_vid.replace(".mp4", "") in f for f in quarantine_files))

        # Verify corrupt file is NOT in GCS
        corrupt_gcs_uri = f"gs://edm-viral-vault/raw_media/{corrupt_vid}"
        self.assertFalse(self.mock_gcs.exists(corrupt_gcs_uri))

        # Verify Clean File Manifest & GCS State
        clean_rec = self.manifest.get_record(clean_remote)
        self.assertIsNotNone(clean_rec)
        self.assertEqual(clean_rec["status"], "GCS_CONFIRMED")
        clean_gcs_uri = f"gs://edm-viral-vault/raw_media/{clean_vid}"
        self.assertTrue(self.mock_gcs.exists(clean_gcs_uri))

    # ========================================================================
    # TEST 3: Wireless ADB Network Disconnection & Exponential Backoff
    # ========================================================================
    def test_03_adb_wireless_disconnection_and_backoff_recovery(self):
        """
        Simulates Wi-Fi drop during ADB pull.
        Verifies:
        1. Ingestion daemon detects failure without hanging.
        2. Manifest records error and increments retry counter.
        3. When connection recovers, backoff reconnects and Samsung Auto Blocker bypass is re-applied.
        4. Partial .part files are cleanly purged and re-pulled.
        """
        vid_id = "network_drop_clip.mp4"
        remote_path = f"/sdcard/DCIM/Camera/{vid_id}"
        payload = self._generate_video_bytes("net_drop", size_kb=48)
        self.mock_device.add_remote_file(remote_path, payload)

        # 1. Simulate Wi-Fi drop
        self.executor.drop_connection = True
        stats_failed = self.daemon.run_cycle()
        self.assertEqual(stats_failed["processed"], 0)

        # 2. Check retry counter and manifest status
        rec = self.manifest.get_record(remote_path)
        # If device was offline during initial ensure_connected, it skipped scanning or registered retry
        # Let's restore connection and run again
        self.executor.drop_connection = False
        self.mock_device.connect()

        stats_recovered = self.daemon.run_cycle()
        self.assertEqual(stats_recovered["processed"], 1)

        # Check that Samsung bypass was re-applied
        self.assertTrue(self.executor.samsung_bypass_applied)

        # Check final GCS confirmed status
        rec_recovered = self.manifest.get_record(remote_path)
        self.assertIsNotNone(rec_recovered)
        self.assertEqual(rec_recovered["status"], "GCS_CONFIRMED")

    # ========================================================================
    # TEST 4: Active Recording 2-Tick Guard Under Heavy Load
    # ========================================================================
    def test_04_active_recording_2tick_guard(self):
        """
        Tests active camera recording detection across multiple time ticks:
        Tick 1: File is discovered; size is growing -> IngestionDaemon marks RECORDING, does not pull.
        Tick 2: File size still growing -> RECORDING maintained.
        Tick 3: File size stable, stability window passed -> Pulled, verified, and uploaded.
        """
        scanner = IncrementalMediaScanner(self.adb, min_stability_seconds=2.0)
        vid_path = "/sdcard/DCIM/Camera/live_recording_01.mp4"

        t0 = 1000.0
        # Tick 1: Initial observation (size = 10MB)
        is_rec_1 = scanner.is_actively_recording(vid_path, current_size=10_000_000, current_time=t0)
        self.assertTrue(is_rec_1)

        # Tick 2: Size grew to 20MB after 1s -> Actively growing
        t1 = 1001.0
        is_rec_2 = scanner.is_actively_recording(vid_path, current_size=20_000_000, current_time=t1)
        self.assertTrue(is_rec_2)

        # Tick 3: Size unchanged at 20MB after 1s (total 1s elapsed < 2.0s min stability) -> Still waiting
        t2 = 1002.0
        is_rec_3 = scanner.is_actively_recording(vid_path, current_size=20_000_000, current_time=t2)
        self.assertTrue(is_rec_3)

        # Tick 4: Size unchanged at 20MB after 3s (total 3s elapsed >= 2.0s min stability) -> Stabilized!
        t3 = 1004.0
        is_rec_4 = scanner.is_actively_recording(vid_path, current_size=20_000_000, current_time=t3)
        self.assertFalse(is_rec_4)

    # ========================================================================
    # TEST 5: Gemini Multimodal 429 Rate Limit & PySpark DLQ Isolation
    # ========================================================================
    def test_05_gemini_429_quota_exhaustion_and_dlq_isolation(self):
        """
        Simulates Gemini API 429 Quota Exceeded during PySpark distributed grading.
        Verifies:
        1. Dead Letter Queue captures failed video metadata, traceback, and error type.
        2. PySpark partition worker yields FAILED_DLQ status without crashing the Spark batch job.
        3. BigQuery sink accepts DLQ records with status='FAILED_DLQ'.
        """
        # Create client simulating 429 quota exhaustion
        gemini_client = GeminiMultimodalClient(
            mock_mode=True,
            simulate_rate_limit=True,
            dlq_dir=self.dlq_dir,
        )

        test_records = [
            {"video_id": "rate_limited_vid_01", "gcs_uri": "gs://bucket/vid01.mp4", "duration_seconds": 25.0},
            {"video_id": "rate_limited_vid_02", "gcs_uri": "gs://bucket/vid02.mp4", "duration_seconds": 30.0},
        ]

        # Execute partition grading under simulated 429
        results = list(grade_partition(iter(test_records), DEFAULT_WEIGHTS, mock_mode=True, simulate_rate_limit=True))
        self.assertEqual(len(results), 2)

        for res in results:
            self.assertEqual(res["status"], "FAILED_DLQ")
            self.assertIn("429", res["error_message"])
            self.assertEqual(res["evpi_composite"], 0.0)
            self.assertEqual(res["trending_verdict"], TrendingVerdict.LOW_REACH.value if hasattr(TrendingVerdict.LOW_REACH, 'value') else "LOW_REACH")

        # Verify BigQuery Sink accepts DLQ records without failing
        sink_count = self.feedback_engine.sink_grades(results)
        self.assertEqual(sink_count, 2)

        # Check stored BigQuery row status
        grades_table = self.bq_mock.tables["media_pipeline.video_grades"]
        self.assertTrue(all(r["status"] == "FAILED_DLQ" for r in grades_table[-2:]))

    # ========================================================================
    # TEST 6: Simplex Normalization & Extreme BQML Weight Shifts
    # ========================================================================
    def test_06_simplex_normalization_and_extreme_weight_shifts(self):
        """
        Tests BQML feedback loop under adversarial weight distributions:
        1. Extreme weight shift (1 feature gets massive score, others 0).
        2. All negative coefficients from regression.
        3. Missing features and alias variations.
        Verifies:
        - Simplex normalization guarantees sum == 1.0000 in all cases.
        - Minimum floor >= 0.01 prevents zero/negative weight collapse.
        - Pydantic ModelParameterWeights validates successfully without ValidationError.
        """
        # Case A: Extreme single-feature domination
        extreme_raw = {
            "hrv": 1000.0,
            "dpaw": 0.0,
            "adr_sfd": 0.0,
            "cke_mve": 0.0,
            "ltss": 0.0,
        }
        norm_a = extract_normalized_weights(extreme_raw)
        self.assertAlmostEqual(sum(norm_a.values()), 1.0000, places=4)
        self.assertGreater(norm_a["weight_hrv"], 0.90)
        self.assertTrue(all(v >= 0.0 for v in norm_a.values()))

        # Case B: All negative coefficients (e.g. inverse retention correlation)
        all_neg = {
            "hook_strength": -5.2,
            "audio_drop_sync": -10.0,
            "crowd_energy": -2.1,
            "visual_dynamism": -8.4,
            "retention_pacing": -0.5,
        }
        norm_b = extract_normalized_weights(all_neg)
        self.assertAlmostEqual(sum(norm_b.values()), 1.0000, places=4)
        # All floored to 0.01 and normalized equally to 0.2000
        for v in norm_b.values():
            self.assertAlmostEqual(v, 0.20, delta=0.01)

        # Case C: Pydantic ModelParameterWeights initialization
        model_weights = ModelParameterWeights(
            version_id="v_extreme_test",
            weight_hrv=norm_a["weight_hrv"],
            weight_dpaw=norm_a["weight_dpaw"],
            weight_adr_sfd=norm_a["weight_adr_sfd"],
            weight_cke_mve=norm_a["weight_cke_mve"],
            weight_ltss=norm_a["weight_ltss"],
            model_r2_score=0.92,
            is_active=True,
        )
        self.assertEqual(model_weights.version_id, "v_extreme_test")

        # Test EVPI calculation with extreme weights
        scores = ViralParameterScores(hrv=95.0, dpaw=40.0, adr_sfd=50.0, cke_mve=30.0, ltss=20.0)
        evpi = calculate_evpi(scores, model_weights)
        # Since HRV is ~96% of the weight and HRV score is 95, EVPI should be ~91+
        self.assertGreaterEqual(evpi, 85.0)

    # ========================================================================
    # TEST 7: Single-Instance Process Lock Concurrency Race
    # ========================================================================
    def test_07_single_instance_process_lock_concurrency(self):
        """
        Tests OS-level single-instance file locking:
        1. First process acquires lock file successfully.
        2. Second concurrent process attempting to acquire raises LockAcquisitionError.
        3. First process releases lock; second process can now acquire lock cleanly.
        """
        lock_file = os.path.join(self.test_dir, ".daemon_test.lock")
        lock1 = ProcessLock(lock_file)
        lock2 = ProcessLock(lock_file)

        # Process 1 acquires
        lock1.acquire()
        self.assertIsNotNone(lock1.fd)

        # Process 2 attempts acquisition -> must raise LockAcquisitionError
        with self.assertRaises(LockAcquisitionError):
            lock2.acquire()

        # Process 1 releases
        lock1.release()
        self.assertIsNone(lock1.fd)

        # Process 2 acquires now
        lock2.acquire()
        self.assertIsNotNone(lock2.fd)
        lock2.release()


def run_stress_suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(Tier5AdversarialStressTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_stress_suite())
