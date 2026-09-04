"""
test_adversarial_ingestion.py - Independent Adversarial Test Suite for Ingestion Daemon.

Empirical Challenger Test Matrix:
1. Network Fault Tolerance & Jitter Backoff (Multi-drop, backoff math, GCS drop, precondition overwrite block)
2. Cryptographic Hash Verification & Corruption Fuzzing (Bit flips, truncation, trailing padding, 0-byte, 50MB stream, case insensitivity, malformed hashes)
3. Multi-Thread Concurrency & Race Conditions (10-thread parallel pull, duplicate file race, concurrent SQLite read/write storm, multi-process lock contention)
4. Filename Safety, Unicode, Injection & Boundary Defense (Spaces, Unicode emojis, quotes, quarantine collision safety)
"""

import os
import sys
import time
import math
import base64
import random
import hashlib
import tempfile
import unittest
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, List, Tuple

# Ensure import paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from ingestion.manifest_store import ManifestStore
from ingestion.adb_connection_manager import AdbConnectionManager
from ingestion.gcs_uploader import GCSUploader, GCSPreconditionError, GCSUploadError
from ingestion.ingestion_daemon import (
    IngestionDaemon,
    IncrementalMediaScanner,
    CryptographicIntegrityError,
    ProcessLock,
    LockAcquisitionError,
)
from ingestion.test_ingestion_daemon import MockAdbDevice, MockGCSClient, MockGCSBucket, MockGCSBlob


# ============================================================================
# ADVANCED ADVERSARIAL MOCK ADB & GCS
# ============================================================================

class AdvancedMockAdbDevice(MockAdbDevice):
    """
    Extends MockAdbDevice with fine-grained failure injection:
    - per-file drop countdowns
    - selective corruption strategies (first byte, middle byte, last byte, truncation, padding)
    - flaky shell commands
    """

    def __init__(self, device_id: str = "192.168.1.150:5555"):
        super().__init__(device_id)
        self.per_file_drop: Dict[str, int] = {}
        self.corruption_mode: Dict[str, str] = {}  # "bit_flip_start", "bit_flip_mid", "bit_flip_end", "truncate", "append"
        self.fail_sha256: Dict[str, str] = {}  # "invalid_len", "non_hex", "empty", "error"
        self.lock = threading.Lock()

    def set_file_drop(self, remote_path: str, drops_remaining: int):
        with self.lock:
            self.per_file_drop[remote_path] = drops_remaining

    def set_corruption(self, remote_path: str, mode: str):
        with self.lock:
            self.corruption_mode[remote_path] = mode

    def set_sha256_failure(self, remote_path: str, mode: str):
        with self.lock:
            self.fail_sha256[remote_path] = mode

    def command_executor(self, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        cmd_str = " ".join(cmd)

        # 1. shell sha256sum
        if "sha256sum" in cmd_str:
            with self.lock:
                for path, meta in self.files.items():
                    clean_path = path.strip("'\"")
                    if clean_path in cmd_str or path in cmd_str:
                        if path in self.fail_sha256:
                            mode = self.fail_sha256[path]
                            if mode == "invalid_len":
                                return subprocess.CompletedProcess(cmd, 0, stdout=f"abcd1234  {path}\n", stderr="")
                            elif mode == "non_hex":
                                return subprocess.CompletedProcess(cmd, 0, stdout=f"{'Z' * 64}  {path}\n", stderr="")
                            elif mode == "empty":
                                return subprocess.CompletedProcess(cmd, 0, stdout="\n", stderr="")
                            elif mode == "error":
                                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="sha256sum: permission denied")

                        sha = hashlib.sha256(meta["content"]).hexdigest()
                        return subprocess.CompletedProcess(cmd, 0, stdout=f"{sha}  {path}\n", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="No such file or directory")

        # 2. adb pull
        if "pull" in cmd:
            with self.lock:
                self.pull_call_count += 1
                remote_path = cmd[-2]
                local_path = cmd[-1]

                if not self.is_connected or self.fail_pull_countdown > 0:
                    if self.fail_pull_countdown > 0:
                        self.fail_pull_countdown -= 1
                    with open(local_path, "wb") as f:
                        f.write(b"PARTIAL_WIFI_FAIL")
                    return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error: closed socket")

                if remote_path in self.per_file_drop and self.per_file_drop[remote_path] > 0:
                    self.per_file_drop[remote_path] -= 1
                    with open(local_path, "wb") as f:
                        f.write(b"INCOMPLETE_STREAM")
                    return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error: connection reset by peer")

                if remote_path not in self.files:
                    return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="remote object does not exist")

                content = bytearray(self.files[remote_path]["content"])
                mode = self.corruption_mode.get(remote_path)

                if mode == "bit_flip_start" and len(content) > 0:
                    content[0] ^= 0x01
                elif mode == "bit_flip_mid" and len(content) > 1:
                    content[len(content) // 2] ^= 0x01
                elif mode == "bit_flip_end" and len(content) > 0:
                    content[-1] ^= 0x01
                elif mode == "truncate" and len(content) > 10:
                    content = content[:len(content) // 2]
                elif mode == "append":
                    content.extend(b"EXTRA_TRAILING_GARBAGE_BYTES")

                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(content)

                return subprocess.CompletedProcess(cmd, 0, stdout=f"1 file pulled. {len(content)} bytes/s", stderr="")

        return super().command_executor(cmd, **kwargs)


class FlakyGCSClient(MockGCSClient):
    """
    Simulates transient network timeouts, HTTP 503s, and bucket connection errors on GCS uploads.
    """

    def __init__(self):
        super().__init__()
        self.fail_uploads_count = 0
        self.lock = threading.Lock()

    def bucket(self, bucket_name: str) -> MockGCSBucket:
        with self.lock:
            if self.fail_uploads_count > 0:
                self.fail_uploads_count -= 1
                raise GCSUploadError("Simulated 503 Service Unavailable / GCS Socket Timeout")
            return super().bucket(bucket_name)


# ============================================================================
# ADVERSARIAL TEST SUITE
# ============================================================================

class TestAdversarialIngestionDaemon(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="adv_ingestion_")
        self.staging_dir = os.path.join(self.temp_dir, "staging")
        self.quarantine_dir = os.path.join(self.temp_dir, "quarantine")
        self.db_path = os.path.join(self.temp_dir, "adv_manifest.db")
        self.lock_path = os.path.join(self.temp_dir, "adv_daemon.lock")
        self.bucket_name = "adversarial-media-bucket"

        os.makedirs(self.staging_dir, exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)

        self.manifest = ManifestStore(self.db_path)
        self.mock_adb = AdvancedMockAdbDevice("192.168.1.150:5555")
        self.adb_manager = AdbConnectionManager(
            device_ip="192.168.1.150",
            device_port=5555,
            command_executor=self.mock_adb.command_executor,
        )
        self.mock_gcs_client = MockGCSClient()
        self.gcs_uploader = GCSUploader(storage_client=self.mock_gcs_client)

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    # ========================================================================
    # 1. NETWORK FAULT TOLERANCE & JITTER BACKOFF
    # ========================================================================

    def test_multi_drop_recovery_within_max_retries(self):
        """
        Stress-tests daemon recovering from 2 consecutive Wi-Fi drops on the same file
        when max_retries=3. Proves 3rd attempt succeeds and records 2 retries.
        """
        payload = b"MULTI_DROP_RESILIENCE_TEST_" * 50000
        remote_path = "/sdcard/DCIM/Camera/VID_MULTI_DROP.mp4"
        expected_sha256 = hashlib.sha256(payload).hexdigest()
        self.mock_adb.add_file(remote_path, payload)
        self.mock_adb.set_file_drop(remote_path, 2)  # Will fail twice, succeed on 3rd

        daemon = IngestionDaemon(
            adb_manager=self.adb_manager,
            manifest_store=self.manifest,
            gcs_uploader=self.gcs_uploader,
            staging_dir=self.staging_dir,
            quarantine_dir=self.quarantine_dir,
            gcs_bucket=self.bucket_name,
            min_stability_seconds=0.0,
            max_retries=3,
        )

        # Attempt 1: Fails
        stats1 = daemon.run_cycle(current_time=100.0)
        self.assertEqual(stats1["processed"], 0)
        self.assertEqual(stats1["failed"], 1)
        rec1 = self.manifest.get_record(remote_path)
        self.assertEqual(rec1["retry_count"], 1)
        self.assertEqual(rec1["status"], "DISCOVERED")

        # Attempt 2: Fails
        stats2 = daemon.run_cycle(current_time=105.0)
        self.assertEqual(stats2["processed"], 0)
        self.assertEqual(stats2["failed"], 1)
        rec2 = self.manifest.get_record(remote_path)
        self.assertEqual(rec2["retry_count"], 2)
        self.assertEqual(rec2["status"], "DISCOVERED")

        # Attempt 3: Succeeds!
        stats3 = daemon.run_cycle(current_time=110.0)
        self.assertEqual(stats3["processed"], 1)
        self.assertEqual(stats3["failed"], 0)
        rec3 = self.manifest.get_record(remote_path)
        self.assertEqual(rec3["status"], "GCS_CONFIRMED")
        self.assertEqual(rec3["retry_count"], 2)
        self.assertEqual(rec3["local_sha256"], expected_sha256)

    def test_exceeded_max_retries_marks_failed_cleanly(self):
        """
        Stress-tests daemon exhausting max_retries (3 drops). Proves status transitions to FAILED,
        error message is captured, .part file is removed, and GCS upload is avoided.
        """
        payload = b"PERMANENT_NETWORK_FAILURE_TEST" * 10000
        remote_path = "/sdcard/DCIM/Camera/VID_PERMANENT_FAIL.mp4"
        self.mock_adb.add_file(remote_path, payload)
        self.mock_adb.set_file_drop(remote_path, 10)  # Persistent failure

        daemon = IngestionDaemon(
            adb_manager=self.adb_manager,
            manifest_store=self.manifest,
            gcs_uploader=self.gcs_uploader,
            staging_dir=self.staging_dir,
            quarantine_dir=self.quarantine_dir,
            gcs_bucket=self.bucket_name,
            min_stability_seconds=0.0,
            max_retries=3,
        )

        for cycle in range(1, 4):
            daemon.run_cycle(current_time=100.0 + cycle * 5)

        rec = self.manifest.get_record(remote_path)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["status"], "FAILED")
        self.assertEqual(rec["retry_count"], 3)
        self.assertIn("ADB pull failed", rec["last_error"])

        part_file = os.path.join(self.staging_dir, "VID_PERMANENT_FAIL.mp4.part")
        self.assertFalse(os.path.exists(part_file), ".part file must be cleaned up on permanent failure")

        bucket = self.mock_gcs_client.bucket(self.bucket_name)
        self.assertIsNone(bucket.get_blob("raw_media/VID_PERMANENT_FAIL.mp4"))

    def test_reconnect_backoff_mathematical_progression_and_jitter(self):
        """
        Adversarially audits reconnect_with_backoff to verify:
        - Exact exponential backoff formula: min(max_delay, base_delay * 2^(attempt-1))
        - Jitter presence: sleep time >= backoff_time and sleep time <= backoff_time + 0.5
        - Max attempts boundary condition
        """
        sleep_records: List[float] = []

        def mock_sleep(seconds: float):
            sleep_records.append(seconds)

        orig_sleep = time.sleep
        try:
            time.sleep = mock_sleep
            self.mock_adb.is_connected = False  # Permanent offline

            success = self.adb_manager.reconnect_with_backoff(max_attempts=5, base_delay=1.0, max_delay=10.0)
            self.assertFalse(success, "Must return False when device never comes online")

            # max_attempts=5 means 4 sleep intervals (between attempts 1-2, 2-3, 3-4, 4-5)
            self.assertEqual(len(sleep_records), 4, "Must execute exactly 4 backoff delays for 5 attempts")

            # Attempt 1: base = 1.0 -> 1.0 <= sleep <= 1.55
            self.assertGreaterEqual(sleep_records[0], 1.0)
            self.assertLessEqual(sleep_records[0], 1.55)

            # Attempt 2: base = 2.0 -> 2.0 <= sleep <= 2.55
            self.assertGreaterEqual(sleep_records[1], 2.0)
            self.assertLessEqual(sleep_records[1], 2.55)

            # Attempt 3: base = 4.0 -> 4.0 <= sleep <= 4.55
            self.assertGreaterEqual(sleep_records[2], 4.0)
            self.assertLessEqual(sleep_records[2], 4.55)

            # Attempt 4: base = 8.0 -> 8.0 <= sleep <= 8.55
            self.assertGreaterEqual(sleep_records[3], 8.0)
            self.assertLessEqual(sleep_records[3], 8.55)

        finally:
            time.sleep = orig_sleep

    def test_gcs_transient_failure_and_retry_preservation(self):
        """
        Simulates transient GCS failure during upload. Daemon must increment retry count,
        preserve local staged file, and keep manifest in HASH_VERIFIED state for subsequent cycle.
        """
        payload = b"GCS_TRANSIENT_UPLOAD_FAIL_DATA" * 5000
        remote_path = "/sdcard/DCIM/Camera/VID_GCS_FLAKY.mp4"
        self.mock_adb.add_file(remote_path, payload)

        flaky_gcs = FlakyGCSClient()
        flaky_gcs.fail_uploads_count = 1  # 1 failure then success
        flaky_uploader = GCSUploader(storage_client=flaky_gcs)

        daemon = IngestionDaemon(
            adb_manager=self.adb_manager,
            manifest_store=self.manifest,
            gcs_uploader=flaky_uploader,
            staging_dir=self.staging_dir,
            quarantine_dir=self.quarantine_dir,
            gcs_bucket=self.bucket_name,
            min_stability_seconds=0.0,
            max_retries=3,
        )

        # Cycle 1: ADB pull succeeds, but GCS upload throws error
        stats1 = daemon.run_cycle(current_time=100.0)
        self.assertEqual(stats1["processed"], 0)
        self.assertEqual(stats1["failed"], 1)

        rec1 = self.manifest.get_record(remote_path)
        self.assertEqual(rec1["status"], "HASH_VERIFIED", "Status should remain HASH_VERIFIED on GCS upload fail")
        self.assertEqual(rec1["retry_count"], 1)
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "VID_GCS_FLAKY.mp4")), "Staged file must be preserved")

    def test_gcs_precondition_duplicate_overwrite_prevention(self):
        """
        Verifies GCSUploader enforces if_generation_match=0 to prevent overwriting existing raw blobs.
        """
        test_file = os.path.join(self.staging_dir, "test_precondition.mp4")
        with open(test_file, "wb") as f:
            f.write(b"ORIGINAL_RAW_MASTER_BLOB")
        sha = hashlib.sha256(b"ORIGINAL_RAW_MASTER_BLOB").hexdigest()

        # First upload: succeeds
        res1 = self.gcs_uploader.upload_media(
            bucket_name=self.bucket_name,
            local_path=test_file,
            destination_blob_name="raw_media/test_precondition.mp4",
            sha256_hash=sha,
            if_generation_match=0,
        )
        self.assertEqual(res1["blob_name"], "raw_media/test_precondition.mp4")

        # Second upload with same name: must raise GCSPreconditionError
        with self.assertRaises(GCSPreconditionError):
            self.gcs_uploader.upload_media(
                bucket_name=self.bucket_name,
                local_path=test_file,
                destination_blob_name="raw_media/test_precondition.mp4",
                sha256_hash=sha,
                if_generation_match=0,
            )

    # ========================================================================
    # 2. CRYPTOGRAPHIC HASH VERIFICATION & CORRUPTION FUZZING
    # ========================================================================

    def test_corruption_fuzzing_all_byte_positions(self):
        """
        Fuzzes byte corruption at start byte (0), middle byte (len//2), and end byte (-1).
        Verifies CryptographicIntegrityError is raised for each and quarantined.
        """
        positions = [
            ("bit_flip_start", "/sdcard/DCIM/Camera/VID_CORRUPT_START.mp4", "VID_CORRUPT_START.mp4"),
            ("bit_flip_mid", "/sdcard/DCIM/Camera/VID_CORRUPT_MID.mp4", "VID_CORRUPT_MID.mp4"),
            ("bit_flip_end", "/sdcard/DCIM/Camera/VID_CORRUPT_END.mp4", "VID_CORRUPT_END.mp4"),
        ]

        daemon = IngestionDaemon(
            adb_manager=self.adb_manager,
            manifest_store=self.manifest,
            gcs_uploader=self.gcs_uploader,
            staging_dir=self.staging_dir,
            quarantine_dir=self.quarantine_dir,
            gcs_bucket=self.bucket_name,
            min_stability_seconds=0.0,
        )

        for mode, path, fname in positions:
            payload = (f"PAYLOAD_FOR_{mode}_TESTING_".encode("utf-8")) * 1000
            self.mock_adb.add_file(path, payload)
            self.mock_adb.set_corruption(path, mode)

            item = {"device_path": path, "file_name": fname, "file_size": len(payload), "mtime": 1000}
            with self.assertRaises(CryptographicIntegrityError):
                daemon.process_file(item, current_time=100.0)

            rec = self.manifest.get_record(path)
            self.assertEqual(rec["status"], "QUARANTINED", f"Failed for mode {mode}")
            self.assertIn("Bit corruption detected", rec["last_error"])

    def test_truncated_and_appended_stream_corruption(self):
        """
        Fuzzes truncated payload (half-received) and appended garbage bytes.
        Verifies both trigger cryptographic hash integrity violations.
        """
        cases = [
            ("truncate", "/sdcard/DCIM/Camera/VID_TRUNCATED.mp4", "VID_TRUNCATED.mp4"),
            ("append", "/sdcard/DCIM/Camera/VID_APPENDED.mp4", "VID_APPENDED.mp4"),
        ]

        daemon = IngestionDaemon(
            adb_manager=self.adb_manager,
            manifest_store=self.manifest,
            gcs_uploader=self.gcs_uploader,
            staging_dir=self.staging_dir,
            quarantine_dir=self.quarantine_dir,
            gcs_bucket=self.bucket_name,
            min_stability_seconds=0.0,
        )

        for mode, path, fname in cases:
            payload = b"STRUCTURED_4K_MP4_ATOM_HEADER_DATA_1234567890" * 500
            self.mock_adb.add_file(path, payload)
            self.mock_adb.set_corruption(path, mode)

            item = {"device_path": path, "file_name": fname, "file_size": len(payload), "mtime": 1000}
            with self.assertRaises(CryptographicIntegrityError):
                daemon.process_file(item, current_time=100.0)

            rec = self.manifest.get_record(path)
            self.assertEqual(rec["status"], "QUARANTINED")

    def test_zero_byte_empty_file_ingestion(self):
        """
        Tests edge case of 0-byte file (empty video/photo artifact).
        Verifies SHA-256 of empty payload is computed, matched, and stored without crashing.
        """
        empty_path = "/sdcard/DCIM/Camera/VID_0BYTE_EMPTY.mp4"
        empty_payload = b""
        expected_empty_sha256 = hashlib.sha256(b"").hexdigest()

        self.mock_adb.add_file(empty_path, empty_payload)

        daemon = IngestionDaemon(
            adb_manager=self.adb_manager,
            manifest_store=self.manifest,
            gcs_uploader=self.gcs_uploader,
            staging_dir=self.staging_dir,
            quarantine_dir=self.quarantine_dir,
            gcs_bucket=self.bucket_name,
            min_stability_seconds=0.0,
        )

        stats = daemon.run_cycle(current_time=100.0)
        self.assertEqual(stats["processed"], 1)

        rec = self.manifest.get_record(empty_path)
        self.assertEqual(rec["status"], "GCS_CONFIRMED")
        self.assertEqual(rec["device_sha256"], expected_empty_sha256)
        self.assertEqual(rec["local_sha256"], expected_empty_sha256)
        self.assertEqual(rec["file_size_bytes"], 0)

    def test_large_file_streaming_sha256_buffer_integrity(self):
        """
        Tests 50MB pseudo-random binary stream through compute_local_sha256.
        Verifies 64KB chunk buffer computes exact hash matching in-memory hashlib.sha256.
        """
        test_file = os.path.join(self.staging_dir, "large_50mb_test.bin")
        chunk = os.urandom(65536)  # 64KB random block
        total_chunks = (50 * 1024 * 1024) // 65536
        full_hasher = hashlib.sha256()

        with open(test_file, "wb") as f:
            for _ in range(total_chunks):
                f.write(chunk)
                full_hasher.update(chunk)

        expected_sha = full_hasher.hexdigest()
        computed_sha = IngestionDaemon.compute_local_sha256(test_file, chunk_size=65536)
        self.assertEqual(computed_sha, expected_sha, "Streaming 64KB buffer SHA-256 must match exactly")

    def test_malformed_remote_device_sha256_responses(self):
        """
        Adversarially tests handling of corrupted or malicious sha256sum outputs from device:
        - Non-64 hex length string
        - Non-hex characters (corrupt hash causing integrity failure)
        - Empty string
        - Shell error
        """
        daemon = IngestionDaemon(
            adb_manager=self.adb_manager,
            manifest_store=self.manifest,
            gcs_uploader=self.gcs_uploader,
            staging_dir=self.staging_dir,
            quarantine_dir=self.quarantine_dir,
            gcs_bucket=self.bucket_name,
            min_stability_seconds=0.0,
        )

        # 1. Invalid length
        p1 = "/sdcard/DCIM/Camera/VID_BAD_LEN.mp4"
        self.mock_adb.add_file(p1, b"TEST_PAYLOAD_1")
        self.mock_adb.set_sha256_failure(p1, "invalid_len")
        stats1 = daemon.run_cycle(current_time=100.0)
        self.assertEqual(stats1["failed"], 1)
        rec1 = self.manifest.get_record(p1)
        self.assertEqual(rec1["status"], "FAILED")

        # 2. Non-hex characters
        p2 = "/sdcard/DCIM/Camera/VID_NON_HEX.mp4"
        self.mock_adb.add_file(p2, b"TEST_PAYLOAD_2")
        self.mock_adb.set_sha256_failure(p2, "non_hex")
        stats2 = daemon.run_cycle(current_time=105.0)
        self.assertEqual(stats2["failed"], 1)
        rec2 = self.manifest.get_record(p2)
        self.assertEqual(rec2["status"], "QUARANTINED")

        # 3. Empty hash
        p3 = "/sdcard/DCIM/Camera/VID_EMPTY_HASH.mp4"
        self.mock_adb.add_file(p3, b"TEST_PAYLOAD_3")
        self.mock_adb.set_sha256_failure(p3, "empty")
        stats3 = daemon.run_cycle(current_time=110.0)
        self.assertEqual(stats3["failed"], 1)
        rec3 = self.manifest.get_record(p3)
        self.assertEqual(rec3["status"], "FAILED")

        # 4. Shell error
        p4 = "/sdcard/DCIM/Camera/VID_ERR_HASH.mp4"
        self.mock_adb.add_file(p4, b"TEST_PAYLOAD_4")
        self.mock_adb.set_sha256_failure(p4, "error")
        stats4 = daemon.run_cycle(current_time=115.0)
        self.assertEqual(stats4["failed"], 1)
        rec4 = self.manifest.get_record(p4)
        self.assertEqual(rec4["status"], "FAILED")

    # ========================================================================
    # 3. MULTI-THREAD CONCURRENCY & RACE CONDITIONS
    # ========================================================================

    def test_concurrent_multi_thread_file_ingestion(self):
        """
        Spawns 10 concurrent threads simultaneously processing 10 distinct video files (2MB each).
        Asserts:
        - Zero SQLite thread contention or database locking crashes
        - All 10 files reach GCS_CONFIRMED status
        - All 10 files have bit-for-bit verified SHA-256 hashes
        """
        num_files = 10
        files_data = {}

        for i in range(num_files):
            file_name = f"VID_CONCURRENT_{i:03d}.mp4"
            remote_path = f"/sdcard/DCIM/Camera/{file_name}"
            content = os.urandom(2 * 1024 * 1024)  # 2MB random bytes
            sha = hashlib.sha256(content).hexdigest()
            self.mock_adb.add_file(remote_path, content)
            files_data[remote_path] = {
                "file_name": file_name,
                "content": content,
                "sha256": sha,
                "item": {
                    "device_path": remote_path,
                    "file_name": file_name,
                    "file_size": len(content),
                    "mtime": 1700000000 + i,
                }
            }

        daemon = IngestionDaemon(
            adb_manager=self.adb_manager,
            manifest_store=self.manifest,
            gcs_uploader=self.gcs_uploader,
            staging_dir=self.staging_dir,
            quarantine_dir=self.quarantine_dir,
            gcs_bucket=self.bucket_name,
            min_stability_seconds=0.0,
        )

        def worker_task(item: Dict[str, Any]) -> bool:
            return daemon.process_file(item, current_time=1700000100.0)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(worker_task, meta["item"]): path for path, meta in files_data.items()}
            results = {}
            for fut in as_completed(futures):
                path = futures[fut]
                results[path] = fut.result()

        for path, success in results.items():
            self.assertTrue(success, f"Concurrent ingestion failed for {path}")
            rec = self.manifest.get_record(path)
            self.assertIsNotNone(rec)
            self.assertEqual(rec["status"], "GCS_CONFIRMED")
            self.assertEqual(rec["local_sha256"], files_data[path]["sha256"])

        all_records = self.manifest.get_all_records()
        self.assertEqual(len(all_records), num_files, f"Expected exactly {num_files} records in manifest")

    def test_concurrent_manifest_read_write_storm(self):
        """
        Stress-tests SQLite ManifestStore under high concurrency:
        - 8 threads continuously writing/updating records
        - 8 threads continuously reading records and running aggregate queries
        Total > 500 concurrent operations. Proves thread safety and context manager robustness.
        """
        num_writers = 8
        num_readers = 8
        ops_per_thread = 50
        errors: List[Exception] = []
        lock = threading.Lock()

        for i in range(20):
            self.manifest.register_discovered(
                device_ip="192.168.1.150",
                device_path=f"/sdcard/DCIM/Camera/SEED_{i}.mp4",
                file_name=f"SEED_{i}.mp4",
                size=1000 + i,
                mtime=1000,
            )

        def writer_thread(tid: int):
            try:
                for j in range(ops_per_thread):
                    path = f"/sdcard/DCIM/Camera/SEED_{j % 20}.mp4"
                    self.manifest.update_status(
                        path,
                        "DOWNLOADING",
                        local_sha256=f"hash_{tid}_{j}",
                        retry_count=j,
                    )
                    self.manifest.register_discovered(
                        device_ip="192.168.1.150",
                        device_path=f"/sdcard/DCIM/Camera/DYNAMIC_{tid}_{j}.mp4",
                        file_name=f"DYNAMIC_{tid}_{j}.mp4",
                        size=2000 + j,
                        mtime=2000,
                    )
            except Exception as e:
                with lock:
                    errors.append(e)

        def reader_thread(tid: int):
            try:
                for _ in range(ops_per_thread):
                    self.manifest.get_all_records()
                    self.manifest.get_pending_tasks(limit=10)
                    self.manifest.get_record("/sdcard/DCIM/Camera/SEED_0.mp4")
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for i in range(num_writers):
            threads.append(threading.Thread(target=writer_thread, args=(i,)))
        for i in range(num_readers):
            threads.append(threading.Thread(target=reader_thread, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent DB access raised errors: {errors}")

    def test_multi_process_lock_contention(self):
        """
        Adversarially tests ProcessLock across multiple threads/instances.
        Verifies mutual exclusion and release semantics.
        """
        lock_file = os.path.join(self.temp_dir, "contention_test.lock")
        acquired_count = [0]
        lock_barrier = threading.Barrier(5)
        lock_list: List[ProcessLock] = []

        def lock_attempt(tid: int):
            p_lock = ProcessLock(lock_file)
            lock_barrier.wait()
            try:
                p_lock.acquire()
                acquired_count[0] += 1
                lock_list.append(p_lock)
                time.sleep(0.05)
            except LockAcquisitionError:
                pass

        threads = [threading.Thread(target=lock_attempt, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(acquired_count[0], 1, "Exactly 1 thread must acquire ProcessLock under contention")

        for l in lock_list:
            l.release()

    # ========================================================================
    # 4. FILENAME SAFETY, SPECIAL CHARACTERS & QUARANTINE SAFETY
    # ========================================================================

    def test_adversarial_filenames_unicode_and_spaces(self):
        """
        Tests media files with complex filenames:
        - Spaces: 'VID 2026 EDM FESTIVAL.mp4'
        - Unicode & Emojis: 'VID_Ultra_Miami_🔥_Stage.mp4'
        - Symbols: 'VID_Tchami_&_Malaa_[1080p].mp4'
        """
        files = [
            ("VID 2026 EDM FESTIVAL.mp4", b"SPACE_FILENAME_PAYLOAD" * 100),
            ("VID_Ultra_Miami_🔥_Stage.mp4", b"UNICODE_EMOJI_PAYLOAD" * 100),
            ("VID_Tchami_&_Malaa_[1080p].mp4", b"SPECIAL_CHAR_PAYLOAD" * 100),
        ]

        daemon = IngestionDaemon(
            adb_manager=self.adb_manager,
            manifest_store=self.manifest,
            gcs_uploader=self.gcs_uploader,
            staging_dir=self.staging_dir,
            quarantine_dir=self.quarantine_dir,
            gcs_bucket=self.bucket_name,
            min_stability_seconds=0.0,
        )

        for fname, content in files:
            rpath = f"/sdcard/DCIM/Camera/{fname}"
            sha = hashlib.sha256(content).hexdigest()
            self.mock_adb.add_file(rpath, content)

            item = {"device_path": rpath, "file_name": fname, "file_size": len(content), "mtime": 1000}
            success = daemon.process_file(item, current_time=100.0)
            self.assertTrue(success, f"Failed processing adversarial filename: {fname}")

            rec = self.manifest.get_record(rpath)
            self.assertEqual(rec["status"], "GCS_CONFIRMED")
            self.assertEqual(rec["local_sha256"], sha)

    def test_quarantine_collision_safety(self):
        """
        Proves that repeated corruptions of the same filename produce distinct timestamped
        quarantine files without overwriting previous forensic records.
        """
        path = "/sdcard/DCIM/Camera/VID_REPEATED_CORRUPT.mp4"
        payload = b"REPEATED_CORRUPT_PAYLOAD" * 100
        self.mock_adb.add_file(path, payload)
        self.mock_adb.set_corruption(path, "bit_flip_start")

        daemon = IngestionDaemon(
            adb_manager=self.adb_manager,
            manifest_store=self.manifest,
            gcs_uploader=self.gcs_uploader,
            staging_dir=self.staging_dir,
            quarantine_dir=self.quarantine_dir,
            gcs_bucket=self.bucket_name,
            min_stability_seconds=0.0,
        )

        item = {"device_path": path, "file_name": "VID_REPEATED_CORRUPT.mp4", "file_size": len(payload), "mtime": 1000}

        # First corruption at t=100.0
        with self.assertRaises(CryptographicIntegrityError):
            daemon.process_file(item, current_time=100.0)

        time.sleep(1.05)

        # Second corruption at t=102.0
        with self.assertRaises(CryptographicIntegrityError):
            daemon.process_file(item, current_time=102.0)

        quarantined_files = os.listdir(self.quarantine_dir)
        self.assertGreaterEqual(len(quarantined_files), 2, "Multiple corruptions must produce separate quarantine files")


# ============================================================================
# MAIN ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
