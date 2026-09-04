"""
ingestion_daemon.py - Autonomous Zero-Compression Ingestion Daemon.
Orchestrates ADB device polling, active recording guard, atomic .part downloads,
cryptographic SHA-256 verification, and streaming GCS uploads with process locking.
"""

import os
import sys
import time
import signal
import hashlib
import logging
from typing import Optional, List, Dict, Any, Tuple

from manifest_store import ManifestStore
from adb_connection_manager import AdbConnectionManager
from gcs_uploader import GCSUploader, GCSUploadError

logger = logging.getLogger("IngestionDaemon")


class CryptographicIntegrityError(Exception):
    """Raised when on-device SHA-256 does not match local downloaded SHA-256."""
    pass


class LockAcquisitionError(Exception):
    """Raised when another daemon process already holds the single-instance lock."""
    pass


class ProcessLock:
    """
    Cross-platform single-instance process lock using OS-level file locking.
    """

    def __init__(self, lock_path: str):
        self.lock_path = lock_path
        self.fd: Optional[int] = None

    def acquire(self):
        lock_dir = os.path.dirname(self.lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)

        try:
            self.fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR)
            os.lseek(self.fd, 0, os.SEEK_SET)

            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            pid_bytes = f"{os.getpid()}\n".encode("utf-8")
            os.write(self.fd, pid_bytes)
        except (IOError, OSError) as e:
            if self.fd is not None:
                try:
                    os.close(self.fd)
                except Exception:
                    pass
                self.fd = None
            raise LockAcquisitionError(f"Failed to acquire single-instance lock '{self.lock_path}': {e}") from e

    def release(self):
        if self.fd is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    try:
                        os.lseek(self.fd, 0, os.SEEK_SET)
                        msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(self.fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
                os.close(self.fd)
            except Exception as e:
                logger.debug(f"Error during lock file descriptor close: {e}")
            finally:
                self.fd = None

            try:
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
            except Exception as e:
                logger.debug(f"Error removing lock file: {e}")

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class IncrementalMediaScanner:
    """
    Scans remote Android directories for media files and detects actively recording files.
    """

    SUPPORTED_EXTENSIONS = (".mp4", ".mov", ".jpg", ".jpeg", ".dng", ".heic")

    def __init__(self, adb_manager: AdbConnectionManager, min_stability_seconds: float = 3.0):
        self.adb = adb_manager
        self.min_stability_seconds = min_stability_seconds
        # Maps remote_path -> (last_seen_size, last_growth_timestamp, is_first_observation)
        self._growth_tracker: Dict[str, Dict[str, Any]] = {}

    def scan_directory(self, remote_dir: str = "/sdcard/DCIM/Camera") -> List[Dict[str, Any]]:
        """
        Executes on-device stat command to discover media files with size and mtime.
        """
        ext_patterns = " ".join([f"{remote_dir}/*{ext}" for ext in self.SUPPORTED_EXTENSIONS])
        cmd = f"stat -c '%n|%s|%Y' {ext_patterns} 2>/dev/null"
        ret, stdout, stderr = self.adb.execute_shell(cmd)
        if ret != 0 and not stdout.strip():
            logger.debug(f"Remote scan returned {ret} for {remote_dir}: {stderr.strip()}")
            return []

        results: List[Dict[str, Any]] = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) == 3:
                path, size_str, mtime_str = parts
                try:
                    size = int(size_str)
                    mtime = int(mtime_str)
                    file_name = os.path.basename(path)
                    results.append({
                        "device_path": path,
                        "file_name": file_name,
                        "file_size": size,
                        "mtime": mtime,
                    })
                except ValueError:
                    continue
        return results

    def is_actively_recording(
        self,
        device_path: str,
        current_size: int,
        current_time: Optional[float] = None,
    ) -> bool:
        """
        2-Tick Delta Check: Detects if a video file is actively growing or unstable.
        Returns True if the file size has increased recently or is within the stability window.
        """
        now = current_time if current_time is not None else time.time()
        tracker = self._growth_tracker.get(device_path)

        if tracker is None:
            # First time observing this file
            self._growth_tracker[device_path] = {
                "last_size": current_size,
                "last_changed_time": now,
                "first_seen_time": now,
                "stable": False,
            }
            # Guard against pulling immediately on first tick if stability window > 0
            if self.min_stability_seconds > 0:
                return True
            return False

        last_size = tracker["last_size"]

        if current_size > last_size:
            # File is actively growing!
            tracker["last_size"] = current_size
            tracker["last_changed_time"] = now
            tracker["stable"] = False
            logger.info(f"File {device_path} is growing ({last_size} -> {current_size} bytes). Skipping pull.")
            return True
        elif current_size < last_size:
            # Anomalous shrinkage (e.g. file replaced/re-recorded)
            tracker["last_size"] = current_size
            tracker["last_changed_time"] = now
            tracker["stable"] = False
            return True
        else:
            # Size has not changed since last check
            time_since_last_change = now - tracker["last_changed_time"]
            if time_since_last_change < self.min_stability_seconds:
                logger.debug(f"File {device_path} size is unchanged but waiting for stability window ({time_since_last_change:.1f}s / {self.min_stability_seconds}s)")
                return True
            else:
                tracker["stable"] = True
                return False


class IngestionDaemon:
    """
    Autonomous Ingestion Daemon that connects to Android device over ADB Wi-Fi,
    scans DCIM directories, verifies bit-for-bit SHA-256 integrity, and uploads to GCS.
    """

    def __init__(
        self,
        adb_manager: AdbConnectionManager,
        manifest_store: ManifestStore,
        gcs_uploader: GCSUploader,
        staging_dir: str,
        gcs_bucket: str,
        remote_dirs: Optional[List[str]] = None,
        quarantine_dir: Optional[str] = None,
        lock_file_path: Optional[str] = None,
        min_stability_seconds: float = 3.0,
        max_retries: int = 3,
    ):
        self.adb = adb_manager
        self.manifest = manifest_store
        self.uploader = gcs_uploader
        self.staging_dir = staging_dir
        self.gcs_bucket = gcs_bucket
        self.remote_dirs = remote_dirs or ["/sdcard/DCIM/Camera", "/sdcard/DCIM/EDM_Drops"]
        self.quarantine_dir = quarantine_dir or os.path.join(staging_dir, "quarantine")
        self.lock_file_path = lock_file_path or os.path.join(staging_dir, ".ingestion_daemon.lock")
        self.scanner = IncrementalMediaScanner(self.adb, min_stability_seconds=min_stability_seconds)
        self.max_retries = max_retries
        self._running = False

        os.makedirs(self.staging_dir, exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)

    @staticmethod
    def compute_local_sha256(file_path: str, chunk_size: int = 65536) -> str:
        """
        Computes SHA-256 checksum of a local file using a streaming buffer.
        """
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha.update(chunk)
        return sha.hexdigest()

    def process_file(self, item: Dict[str, Any], current_time: Optional[float] = None) -> bool:
        """
        Executes atomic pull, integrity verification, and GCS upload for a single media item.
        """
        device_path = item["device_path"]
        file_name = item["file_name"]
        file_size = item["file_size"]
        mtime = item.get("mtime", 0)

        # Ensure manifest record exists
        self.manifest.register_discovered(
            device_ip=self.adb.device_ip,
            device_path=device_path,
            file_name=file_name,
            size=file_size,
            mtime=mtime,
        )

        # 1. Check Active Recording Guard
        if self.scanner.is_actively_recording(device_path, file_size, current_time=current_time):
            self.manifest.update_status(device_path, "RECORDING")
            return False

        part_path = os.path.join(self.staging_dir, f"{file_name}.part")
        final_local_path = os.path.join(self.staging_dir, file_name)

        # 2. Update status: DOWNLOADING
        self.manifest.update_status(device_path, "DOWNLOADING", local_staging_path=part_path)

        # 3. Obtain on-device SHA-256 checksum
        try:
            remote_sha256 = self.adb.get_remote_file_sha256(device_path)
            self.manifest.update_status(device_path, "DOWNLOADING", device_sha256=remote_sha256)
        except Exception as e:
            logger.error(f"Failed to query remote SHA-256 on {device_path}: {e}")
            self.manifest.increment_retry(device_path, str(e))
            self.manifest.update_status(device_path, "FAILED", last_error=str(e))
            return False

        # 4. Pull to atomic .part file
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except Exception:
                pass

        logger.info(f"Pulling {device_path} -> {part_path}...")
        try:
            # Added a hypothetical timeout arg if adb supports it, else we catch TimeoutError
            ret, stdout, stderr = self.adb.pull_file(device_path, part_path)
        except TimeoutError:
            err_msg = "ADB Protocol Timeout! Auto-quarantining corrupted part file."
            logger.error(err_msg)
            if os.path.exists(part_path):
                try:
                    q_path = os.path.join(self.quarantine_dir, f"timeout_{file_name}_{int(time.time())}.part")
                    os.rename(part_path, q_path)
                except Exception:
                    os.remove(part_path)
            self.manifest.mark_quarantined(device_path, err_msg)
            return False
            
        if ret != 0 or not os.path.exists(part_path):
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception:
                    pass
            err_msg = f"ADB pull failed (code {ret}): {stderr.strip()}"
            logger.error(err_msg)
            retries = self.manifest.increment_retry(device_path, err_msg)
            if retries >= self.max_retries:
                self.manifest.mark_failed(device_path, err_msg)
            else:
                self.manifest.update_status(device_path, "DISCOVERED", last_error=err_msg)
            return False

        # 5. Compute local SHA-256 and assert bit-for-bit integrity
        local_sha256 = self.compute_local_sha256(part_path)

        if local_sha256.lower() != remote_sha256.lower():
            # Cryptographic Corruption / Bit-Flip Detected!
            err_msg = f"Bit corruption detected! Remote SHA-256: {remote_sha256} != Local SHA-256: {local_sha256}"
            logger.error(err_msg)

            # Move corrupt part to quarantine for forensic audit
            quarantined_file = os.path.join(self.quarantine_dir, f"corrupt_{file_name}_{int(time.time())}.part")
            try:
                os.rename(part_path, quarantined_file)
            except Exception:
                if os.path.exists(part_path):
                    os.remove(part_path)

            self.manifest.mark_quarantined(device_path, err_msg)
            raise CryptographicIntegrityError(err_msg)

        # 6. Atomic promotion: .part -> final local path
        if os.path.exists(final_local_path):
            try:
                os.remove(final_local_path)
            except Exception:
                pass
        os.rename(part_path, final_local_path)

        self.manifest.update_status(
            device_path,
            "HASH_VERIFIED",
            local_staging_path=final_local_path,
            local_sha256=local_sha256,
        )
        logger.info(f"Verified bit-for-bit zero compression integrity for {file_name} (SHA-256: {local_sha256})")

        # 7. Resumable streaming upload to GCS
        destination_blob_name = f"raw_media/{file_name}"
        self.manifest.update_status(device_path, "UPLOADING", gcs_bucket=self.gcs_bucket, gcs_blob_name=destination_blob_name)

        try:
            upload_result = self.uploader.upload_media(
                bucket_name=self.gcs_bucket,
                local_path=final_local_path,
                destination_blob_name=destination_blob_name,
                sha256_hash=local_sha256,
                custom_metadata={"device_path": device_path},
                if_generation_match=0,
            )

            # 8. Confirm GCS Upload
            self.manifest.update_status(
                device_path,
                "GCS_CONFIRMED",
                gcs_bucket=self.gcs_bucket,
                gcs_blob_name=destination_blob_name,
                gcs_crc32c=upload_result.get("gcs_crc32c"),
                gcs_md5=upload_result.get("gcs_md5"),
            )
            logger.info(f"Confirmed in GCS: {upload_result.get('gcs_uri')}")
            return True

        except Exception as e:
            err_msg = f"GCS Upload failed: {e}"
            logger.error(err_msg)
            retries = self.manifest.increment_retry(device_path, err_msg)
            if retries >= self.max_retries:
                self.manifest.mark_failed(device_path, err_msg)
            else:
                self.manifest.update_status(device_path, "HASH_VERIFIED", last_error=err_msg)
            return False

    def run_cycle(self, current_time: Optional[float] = None) -> Dict[str, int]:
        """
        Executes one complete polling and processing cycle.
        """
        stats = {
            "scanned": 0,
            "new_registered": 0,
            "processed": 0,
            "skipped_recording": 0,
            "failed": 0,
        }

        # Verify or restore ADB connection and enforce Samsung bypass
        if not self.adb.ensure_connected():
            logger.info("ADB connection inactive. Attempting backoff reconnection...")
            if not self.adb.reconnect_with_backoff(max_attempts=3, base_delay=1.0):
                logger.warning("Could not establish ADB connection for this cycle.")
                return stats

        # Scan remote directories
        seen_paths = set()
        for remote_dir in self.remote_dirs:
            discovered_items = self.scanner.scan_directory(remote_dir)

            for item in discovered_items:
                path = item["device_path"]
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                stats["scanned"] += 1

                is_new = self.manifest.register_discovered(
                    device_ip=self.adb.device_ip,
                    device_path=item["device_path"],
                    file_name=item["file_name"],
                    size=item["file_size"],
                    mtime=item["mtime"],
                )
                if is_new:
                    stats["new_registered"] += 1

                # Check if eligible for processing
                record = self.manifest.get_record(item["device_path"])
                if record and record["status"] in ("DISCOVERED", "RECORDING", "DOWNLOADED"):
                    try:
                        success = self.process_file(item, current_time=current_time)
                        if success:
                            stats["processed"] += 1
                        else:
                            updated_rec = self.manifest.get_record(item["device_path"])
                            if updated_rec and updated_rec["status"] == "RECORDING":
                                stats["skipped_recording"] += 1
                            else:
                                stats["failed"] += 1
                    except CryptographicIntegrityError:
                        stats["failed"] += 1

        return stats

    def run(self, poll_interval: float = 5.0, max_cycles: Optional[int] = None):
        """
        Runs the daemon loop continuously under process lock protection.
        """
        lock = ProcessLock(self.lock_file_path)
        lock.acquire()
        self._running = True

        def handle_signal(sig, frame):
            logger.info(f"Received signal {sig}. Initiating graceful shutdown...")
            self._running = False

        try:
            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)
        except Exception:
            pass

        logger.info(f"IngestionDaemon started. Staging dir: {self.staging_dir}, GCS Bucket: {self.gcs_bucket}")
        cycles_run = 0

        try:
            while self._running:
                stats = self.run_cycle()
                logger.debug(f"Cycle completed: {stats}")
                cycles_run += 1
                if max_cycles is not None and cycles_run >= max_cycles:
                    break
                time.sleep(poll_interval)
        finally:
            self._running = False
            lock.release()
            logger.info("IngestionDaemon stopped and lock released.")
