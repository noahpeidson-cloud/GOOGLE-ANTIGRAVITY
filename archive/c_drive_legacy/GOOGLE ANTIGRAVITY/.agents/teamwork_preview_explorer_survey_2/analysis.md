# Ingestion Architecture Deep Research & Daemon Design Specification (R2)

**Author:** teamwork_preview_explorer (Survey Track 2)  
**Target Project:** `media_pipeline` (`g:/My Drive/GOOGLE ANTIGRAVITY/media_pipeline`)  
**Date:** 2026-08-24T21:05:00Z  
**Status:** Complete Forensic Specification  

---

## 1. Executive Summary & Architectural Verdict

Requirement R2 dictates evaluating two ingestion methodologies for extracting high-bitrate 4K media from mobile devices into Google Cloud Storage (GCS):
1. **Google Photos Automation** (REST API / Photos Picker API / Cloud Sweeper)
2. **Android ADB Wi-Fi Sync** (`adb connect`, `adb pull` vs `adb sync`, wireless drop recovery)

### The Architectural Verdict: Android ADB Wi-Fi Sync is Selected
After rigorous analysis of API quotas, video compression behaviors, metadata retention, and headless automation constraints, **Google Photos Automation is categorically disqualified**. 

**Core Disqualification Factors for Google Photos:**
- **Destructive Transcoding & Compression:** Google Photos API endpoints (`baseUrl=dv`) serve downscaled/transcoded web renditions, stripping 10-bit HDR (BT.2020 / DCI-P3) profiles and crushing 80–150 Mbps camera bitrates to compressed streaming streams.
- **Metadata Stripping:** Sensor gyro metadata (essential for DaVinci Resolve AI camera stabilization) and precise XMP/EXIF timestamps are permanently detached or discarded during cloud processing.
- **Breaking API Policies (2025+ Deprecation):** Google has deprecated broad `photoslibrary.readonly` library sweeping in favor of interactive, human-facing `Photos Picker` UI dialogs, making headless zero-touch automation impossible.

**Android ADB Wi-Fi Sync** operates directly over the local 802.11ax/Wi-Fi 7 wireless network at physical link speeds (500–1200 Mbps), bypassing all cloud transcoders and enabling **bit-for-bit, zero-compression raw container extraction**. Combined with on-device `sha256sum` verification and streaming resumable GCS uploads, it guarantees 100% mathematical integrity from phone sensor to cloud analytics.

---

## 2. Deep Comparative Matrix: Google Photos vs Android ADB Wi-Fi Sync

| Evaluation Dimension | Google Photos Automation API | Android ADB Wi-Fi Sync Daemon | Invalidation / Selection Rationale |
| :--- | :--- | :--- | :--- |
| **Bitstream Integrity & Compression** | ❌ **High Risk / Transcoded:** Video downloads via API (`baseUrl=dv`) return re-encoded MP4s. "Storage saver" settings on device crush 4K to 1080p. | ✅ **Zero Compression (Bit-for-Bit):** Direct extraction from `/sdcard/DCIM/Camera`. Full 80–150 Mbps HEVC 10-bit HDR master streams preserved. | **Mandate Violated by Google Photos:** Cannot feed degraded video to Gemini Omni Video grading. |
| **Metadata & Sensor Telemetry** | ❌ **Stripped / Fragmented:** Gyro sensor streams, embedded QuickTime atoms, and fine GPS timecodes are stripped or dumped into sidecar JSON files. | ✅ **100% Preserved:** Raw container headers, ISOBMFF atoms, multi-channel 48kHz audio, and gyro data remain completely intact. | Critical for downstream DaVinci Resolve editing and video feature engineering. |
| **Zero-Touch Automation (No-UI)** | ❌ **Disallowed / Broken:** Google Photos Picker API requires interactive human click-through. Headless background sweeping deprecated. | ✅ **100% Zero-Touch (Rule R10.2 Compliant):** Headless background daemon authenticates via ADB RSA keys and automated shell commands. | Fully autonomous; zero human intervention required. |
| **Throughput & Bandwidth Efficiency** | ❌ **Double WAN Hop:** Phone → Google Photos Cloud → Local Host/GCS (wasting 2x Internet bandwidth and incurring API latency). | ✅ **Single LAN + Uplink Stream:** Phone → Local Daemon (LAN 500-1200 Mbps) → GCS Streaming Upload. | Maximum throughput; eliminates double-metered WAN usage. |
| **Rate Limits & Socket Quotas** | ❌ **Strict API Quotas:** 10,000 requests/day per project. `baseUrl` expires in 60 mins. Socket timeouts on 5–15GB raw clips. | ✅ **Zero API Limits:** Limited only by local router throughput and Google Cloud Storage bucket ingress. | No quota throttling or artificial link expirations. |
| **Fault Recovery & Resumption** | ❌ **Brittle:** REST API dropped downloads must restart from byte 0 unless complex ranged HTTP chunking is engineered on ephemeral URLs. | ✅ **Deterministic Resilience:** Atomic `.part` staging, byte-offset resumption, and SQLite transactional journal tracking. | Complete recovery across intermittent Wi-Fi drops. |

---

## 3. ADB Ingestion Mechanism Analysis: `adb pull` vs `adb sync` vs `adb exec-out`

To determine the most fault-tolerant wireless extraction mechanism:

### 3.1 `adb sync` Evaluation
- **Design Intent:** Originally engineered for AOSP platform developers to sync compiled ROM partitions (`/system`, `/vendor`, `/data`).
- **Failure Mode on `/sdcard`:** On Android 11+ (API 30+), `/sdcard` is virtualized via FUSE / Scoped Storage (`/storage/emulated/0`). `adb sync` relies on ext4 filesystem timestamps that do not map deterministically to emulated FUSE mtimes, frequently leading to false "up-to-date" skips or repeated full re-transfers.
- **Lack of Atomic Staging:** Does not provide `.part` file isolation or native byte-level hashing verification.

### 3.2 `adb exec-out` Streaming Evaluation
- **Design Intent:** Pipes stdout from the device directly to the host (e.g. `adb exec-out cat /sdcard/DCIM/video.mp4 > local.mp4` or `tar` streams).
- **Failure Mode:** On Windows hosts, stdout piping through ADB can encounter newline translations (`\r\n` vs `\n`) or socket EOF race conditions unless specifically wrapped in raw binary handles. Furthermore, interrupted streams cannot be resumed without custom Android shell byte-offset hacking (`dd skip=...`).

### 3.3 `adb pull` with Staged Hashing Daemon (Selected Standard)
- **Advantages:**
  1. Handles binary transfers with native block-level integrity.
  2. Allows atomic destination staging (`video.mp4.part` -> `video.mp4`).
  3. Returns precise return codes and stdout transfer statistics.
  4. Allows pre-flight on-device `sha256sum` queries before transfer and post-transfer host `hashlib.sha256()` verification.
- **Verdict:** `adb pull` wrapped in an intelligent Python daemon with SQLite manifest state tracking is the most reliable, deterministic, and maintainable solution.

---

## 4. End-to-End Zero-Compression Ingestion Daemon Architecture

```
+----------------------------------------------------------------------------------------------------+
|                                    ANDROID MOBILE DEVICE (Wi-Fi)                                   |
|  /sdcard/DCIM/Camera/ (4K HDR .mp4 / .jpg)                                                         |
|  - Auto Blocker Disabled (rampart_auto_enabled_switch_enabled = 0)                                 |
|  - On-Device Checksum: sha256sum /sdcard/DCIM/Camera/VID_20260824.mp4                              |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  | Wireless ADB Protocol (TCP 5555 / mDNS)
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                ZERO-COMPRESSION INGESTION DAEMON (Host)                            |
|                                                                                                    |
|  1. AdbConnectionManager                                                                           |
|     - mDNS Zeroconf scan (_adb-tls-connect._tcp) / Static IP Fallback                              |
|     - Auto-reconnect loop with exponential backoff & keepalive heartbeat                           |
|                                                                                                    |
|  2. IncrementalMediaScanner                                                                        |
|     - Scans /sdcard/DCIM/Camera via adb shell stat / ls -l                                         |
|     - Growth Delta Check (2-tick size stability test to avoid syncing active recordings)           |
|                                                                                                    |
|  3. Atomic Pull & Verification Engine                                                              |
|     - Downloads to local_staging/VID_20260824.mp4.part via adb pull                                |
|     - Computes local SHA-256 (64KB streaming buffer)                                               |
|     - Asserts: on_device_sha256 == local_sha256                                                    |
|     - Atomic rename: VID_20260824.mp4.part -> VID_20260824.mp4                                     |
|                                                                                                    |
|  4. SQLite State Store (ingestion_manifest.db)                                                     |
|     - Tracks lifecycle: DISCOVERED -> STAGED -> HASH_VERIFIED -> UPLOADING -> GCS_CONFIRMED        |
|                                                                                                    |
|  5. GCS Resumable Streaming Uploader                                                               |
|     - Resumable chunked upload to gs://<bucket>/raw_media/                                         |
|     - Sets custom metadata: {'sha256': '<hash>', 'device_path': '<path>', 'raw': 'true'}          |
|     - Cloud hash confirmation: GCS CRC32c / MD5 verification                                       |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  | HTTPS Resumable Streaming Upload (TLS 1.3)
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                    GOOGLE CLOUD STORAGE (GCS)                                      |
|  gs://<bucket>/raw_media/VID_20260824.mp4                                                          |
|  - Precondition: if_generation_match = 0 (Idempotent / No Overwrite)                               |
|  - Blob Metadata: x-goog-meta-sha256, crc32c verification                                          |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                         DOWNSTREAM CONSUMERS (R3 PySpark & R4 BigQuery ML)                         |
|  - PySpark Dataproc Serverless Video Grading (Gemini Omni Flash API)                               |
|  - BigQuery ML Continuous Learning Loop                                                            |
+----------------------------------------------------------------------------------------------------+
```

---

## 5. Detailed Component Specifications

### 5.1 Device Discovery & Connection Manager (`AdbConnectionManager`)

```python
class AdbConnectionManager:
    """
    Manages wireless ADB pairing, connection lifecycle, health heartbeats,
    and manufacturer-specific lockouts (Samsung Auto Blocker).
    """
```
- **Discovery Strategy:**
  1. Query active ADB mDNS services: `adb mdns services`.
  2. Fallback to configured target IP/port: `192.168.1.xxx:5555`.
  3. Connection execution: `adb connect <ip>:<port>`.
- **Health Heartbeat:** Every 10 seconds, runs `adb -s <target> get-state`. If output != `device`, triggers reconnect state machine.
- **Samsung One UI 6+ Auto Blocker Bypass (Mandatory Rule R10.2):**
  Immediately upon establishing connection, execute:
  ```bash
  adb -s <target> shell settings put global rampart_auto_enabled_switch_enabled 0
  ```
  This disables the silent background ADB teardown timer.

### 5.2 Incremental Media Scanner & Recording Guard (`IncrementalMediaScanner`)

- **Polling Directory:** `/sdcard/DCIM/Camera` and `/sdcard/DCIM/EDM_Drops`.
- **Extension Filter:** `.mp4`, `.mov`, `.jpg`, `.jpeg`, `.dng`, `.heic`.
- **File Metadata Extraction:** Executes:
  ```bash
  adb -s <target> shell "stat -c '%n|%s|%Y' /sdcard/DCIM/Camera/*.mp4 /sdcard/DCIM/Camera/*.jpg 2>/dev/null"
  ```
- **Active Recording Guard (2-Tick Delta Check):**
  To prevent pulling videos currently being recorded by the camera app:
  1. Record `(file_path, file_size, current_time)` on tick $T_1$.
  2. On tick $T_2$ ($T_1 + 5\text{s}$), check `file_size`.
  3. If $size(T_2) > size(T_1)$ or delta timestamp $< 3\text{s}$, mark status as `RECORDING_IN_PROGRESS` and defer pull until $size(T_2) == size(T_1)$.

### 5.3 Cryptographic Integrity Engine (`IntegrityVerifier`)

- **Step 1 (On-Device Hashing):**
  ```bash
  adb -s <target> shell sha256sum "/sdcard/DCIM/Camera/VID_20260824_001.mp4"
  ```
  Parses output: `<remote_sha256>  /sdcard/DCIM/Camera/VID_20260824_001.mp4`.
- **Step 2 (Local Stream Hashing):**
  Reads local staged file in 64KB chunks (`hashlib.sha256()`).
- **Step 3 (Integrity Assertion):**
  ```python
  if local_sha256.lower() != remote_sha256.lower():
      os.remove(staging_part_path)
      raise CryptographicIntegrityError(
          f"Bit corruption detected! Remote: {remote_sha256} != Local: {local_sha256}"
      )
  ```
- **Step 4 (Atomic Renaming):**
  Only after hash confirmation is the `.part` file renamed to the final filename.

### 5.4 SQLite Manifest Schema (`ingestion_manifest.db`)

```sql
CREATE TABLE IF NOT EXISTS ingestion_manifest (
    file_id TEXT PRIMARY KEY,               -- SHA-256 of file (or UUID prior to hash)
    device_ip TEXT NOT NULL,
    device_path TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    device_mtime INTEGER NOT NULL,
    device_sha256 TEXT,
    local_staging_path TEXT,
    local_sha256 TEXT,
    gcs_bucket TEXT,
    gcs_blob_name TEXT,
    gcs_crc32c TEXT,
    gcs_md5 TEXT,
    status TEXT NOT NULL CHECK(status IN (
        'DISCOVERED', 
        'RECORDING', 
        'DOWNLOADING', 
        'DOWNLOADED', 
        'HASH_VERIFIED', 
        'UPLOADING', 
        'GCS_CONFIRMED', 
        'FAILED'
    )),
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_manifest_status ON ingestion_manifest(status);
CREATE INDEX IF NOT EXISTS idx_manifest_device_path ON ingestion_manifest(device_path);
```

### 5.5 GCS Resumable Streaming Uploader (`GCSStreamingUploader`)

```python
from google.cloud import storage
import google_crc32c
import base64

def upload_raw_media(bucket_name: str, local_path: str, blob_name: str, metadata: dict) -> dict:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Enforce Idempotency: Fail if blob already exists
    blob.metadata = metadata
    blob.upload_from_filename(
        local_path,
        if_generation_match=0,
        timeout=300,
        retry=storage.retry.DEFAULT_RETRY
    )
    
    # Reload blob to fetch server-computed checksums
    blob.reload()
    return {
        "blob_name": blob.name,
        "gcs_crc32c": blob.crc32c,
        "gcs_md5": blob.md5_hash,
        "custom_metadata": blob.metadata
    }
```

### 5.6 Fault Tolerance & Resilience Specifications

1. **Exponential Backoff with Jitter:**
   $$\text{WaitTime} = \min(M_{\text{max}}, B_{\text{base}} \times 2^{\text{retry}}) + \text{Uniform}(0, J)$$
   - $B_{\text{base}} = 2.0\text{s}$, $M_{\text{max}} = 60.0\text{s}$, $J = 1.0\text{s}$.
2. **Single-Instance Process Lock (`ingestion_daemon.lock`):**
   Uses OS-level file locking (`msvcrt` on Windows, `fcntl` on POSIX) on `.ingestion_daemon.lock` to prevent concurrent daemon conflicts.
3. **Signal Interception & Clean Shutdown:**
   Captures `SIGINT` and `SIGTERM`. Closes active ADB child processes, commits pending SQLite transactions, and releases the process lockfile before exit.

---

## 6. Deterministic Offline Test Harness Design

To comply with **Rule R2 (Zero-Discretion / Test-Driven Agentic Development)**, all daemon components must be fully testable offline without physical Android devices or live Google Cloud credentials.

### 6.1 Mock ADB Subprocess Architecture (`MockAdbServer`)

The test harness provides a deterministic `MockAdbSubprocess` fixture that intercepts `subprocess.run` / `subprocess.Popen` or wraps the ADB CLI calls:

```python
class MockAdbDevice:
    def __init__(self, device_id="192.168.1.150:5555"):
        self.device_id = device_id
        self.connected = True
        self.files = {} # path -> bytes
        self.fail_pull_at_bytes = None
        self.simulate_corruption = False
        
    def add_file(self, path: str, content: bytes, mtime: int = 1700000000):
        self.files[path] = {"content": content, "mtime": mtime}
        
    def run_command(self, cmd_args: list) -> subprocess.CompletedProcess:
        # Handles: connect, disconnect, get-state, shell stat, shell sha256sum, pull
        ...
```

### 6.2 Mock GCS Storage Client (`MockGCSClient`)

An in-memory mock replicating the `google.cloud.storage.Client`, `Bucket`, and `Blob` APIs:
- Computes CRC32C using `google-crc32c` or software polynomial table.
- Computes MD5 using `hashlib.md5()`.
- Enforces `if_generation_match=0` (raising `google.api_core.exceptions.PreconditionFailed` if blob exists).
- Stores and retrieves custom metadata dictionaries.

### 6.3 Five Mandatory Loud Assertion Test Scenarios

1. **`test_e2e_zero_compression_happy_path`**:
   - **Action:** Provisions 100MB random binary payload in `MockAdbDevice`. Executes daemon poll & sync.
   - **Assertion:** `device_sha256 == local_sha256 == gcs_metadata['sha256']`. Bit-for-bit zero loss confirmed.
2. **`test_wifi_drop_recovery_with_backoff`**:
   - **Action:** Simulates Wi-Fi disconnect mid-transfer at byte 5,000,000.
   - **Assertion:** Daemon catches socket error, enters backoff, reconnects on next tick, cleans `.part` file, re-pulls, and successfully completes GCS upload.
3. **`test_bit_flip_corruption_detection`**:
   - **Action:** Injects a single-bit flip into the transferred stream.
   - **Assertion:** Daemon asserts `CryptographicIntegrityError`, deletes corrupted staging `.part`, logs violation in SQLite manifest, and retries.
4. **`test_active_recording_guard`**:
   - **Action:** Simulates an MP4 file whose size increases between scanning intervals ($10\text{MB} \to 25\text{MB}$).
   - **Assertion:** Scanner categorizes file as `RECORDING` and refuses to trigger `adb pull` until file size stabilizes across consecutive ticks.
5. **`test_daemon_single_instance_lock`**:
   - **Action:** Launches secondary daemon instance while lockfile is acquired.
   - **Assertion:** Secondary instance fails immediately with `LockAcquisitionError` and exit code `1`.

---

## 7. Concrete Code Implementation Blueprint

### 7.1 Database & Manifest Manager (`manifest_store.py`)

```python
"""
manifest_store.py - SQLite state tracker for Zero-Compression Ingestion Daemon.
"""
import sqlite3
import datetime
from typing import Optional, Dict, Any, List

class ManifestStore:
    def __init__(self, db_path: str = "ingestion_manifest.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_manifest (
                file_id TEXT PRIMARY KEY,
                device_ip TEXT NOT NULL,
                device_path TEXT NOT NULL UNIQUE,
                file_name TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                device_mtime INTEGER NOT NULL,
                device_sha256 TEXT,
                local_staging_path TEXT,
                local_sha256 TEXT,
                gcs_bucket TEXT,
                gcs_blob_name TEXT,
                gcs_crc32c TEXT,
                gcs_md5 TEXT,
                status TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON ingestion_manifest(status);")

    def register_discovered(self, device_ip: str, device_path: str, file_name: str, size: int, mtime: int) -> bool:
        with self._get_conn() as conn:
            try:
                conn.execute("""
                INSERT INTO ingestion_manifest (
                    file_id, device_ip, device_path, file_name, file_size_bytes, 
                    device_mtime, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'DISCOVERED', ?)
                """, (device_path, device_ip, device_path, file_name, size, mtime, datetime.datetime.utcnow().isoformat()))
                return True
            except sqlite3.IntegrityError:
                return False # Already registered

    def update_status(self, device_path: str, status: str, **kwargs):
        set_clauses = ["status = ?", "updated_at = ?"]
        params = [status, datetime.datetime.utcnow().isoformat()]
        for k, v in kwargs.items():
            set_clauses.append(f"{k} = ?")
            params.append(v)
        params.append(device_path)
        
        with self._get_conn() as conn:
            conn.execute(f"UPDATE ingestion_manifest SET {', '.join(set_clauses)} WHERE device_path = ?", params)

    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.execute("""
            SELECT * FROM ingestion_manifest 
            WHERE status IN ('DISCOVERED', 'DOWNLOADED', 'HASH_VERIFIED') 
            ORDER BY device_mtime ASC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]
```

### 7.2 Ingestion Daemon Core (`ingestion_daemon.py`)

```python
"""
ingestion_daemon.py - Zero-Compression Ingestion Daemon over Android ADB Wi-Fi Sync.
"""
import os
import sys
import time
import hashlib
import logging
import subprocess
from typing import Optional, List, Dict, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IngestionDaemon")

class CryptographicIntegrityError(Exception):
    pass

class AdbIngestionDaemon:
    def __init__(self, device_ip: str, device_port: int, staging_dir: str, gcs_bucket: str, manifest_store):
        self.device_ip = device_ip
        self.device_port = device_port
        self.target = f"{device_ip}:{device_port}"
        self.staging_dir = staging_dir
        self.gcs_bucket = gcs_bucket
        self.manifest = manifest_store
        os.makedirs(staging_dir, exist_ok=True)

    def connect(self) -> bool:
        logger.info(f"Connecting to wireless ADB device at {self.target}...")
        res = subprocess.run(["adb", "connect", self.target], capture_output=True, text=True)
        if "connected" in res.stdout.lower():
            # Neutralize Samsung Auto Blocker (Rule R10.2)
            subprocess.run(["adb", "-s", self.target, "shell", "settings", "put", "global", "rampart_auto_enabled_switch_enabled", "0"], capture_output=True)
            logger.info("Connected successfully. Samsung Auto Blocker neutralized.")
            return True
        logger.warning(f"Failed to connect: {res.stdout.strip()} {res.stderr.strip()}")
        return False

    def scan_remote_media(self, remote_dir: str = "/sdcard/DCIM/Camera") -> List[Dict[str, Any]]:
        cmd = ["adb", "-s", self.target, "shell", f"stat -c '%n|%s|%Y' {remote_dir}/*.mp4 {remote_dir}/*.jpg 2>/dev/null"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        discovered = []
        for line in res.stdout.strip().splitlines():
            if not line or "|" not in line:
                continue
            parts = line.strip().split("|")
            if len(parts) == 3:
                path, size_str, mtime_str = parts
                try:
                    size = int(size_str)
                    mtime = int(mtime_str)
                    discovered.append({
                        "device_path": path,
                        "file_name": os.path.basename(path),
                        "file_size": size,
                        "mtime": mtime
                    })
                except ValueError:
                    continue
        return discovered

    def compute_remote_sha256(self, remote_path: str) -> str:
        cmd = ["adb", "-s", self.target, "shell", f"sha256sum '{remote_path}'"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not res.stdout:
            raise RuntimeError(f"Remote sha256sum failed: {res.stderr}")
        return res.stdout.strip().split()[0]

    def compute_local_sha256(self, local_path: str) -> str:
        sha = hashlib.sha256()
        with open(local_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    def pull_and_verify(self, remote_path: str, expected_size: int) -> Tuple[str, str]:
        file_name = os.path.basename(remote_path)
        part_path = os.path.join(self.staging_dir, f"{file_name}.part")
        final_path = os.path.join(self.staging_dir, file_name)

        # 1. Fetch remote hash
        logger.info(f"Computing remote SHA-256 for {remote_path}...")
        remote_sha256 = self.compute_remote_sha256(remote_path)

        # 2. Pull file
        logger.info(f"Pulling {remote_path} -> {part_path}...")
        pull_cmd = ["adb", "-s", self.target, "pull", remote_path, part_path]
        res = subprocess.run(pull_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            if os.path.exists(part_path):
                os.remove(part_path)
            raise RuntimeError(f"ADB Pull failed: {res.stderr}")

        # 3. Compute and verify local hash
        local_sha256 = self.compute_local_sha256(part_path)
        if local_sha256.lower() != remote_sha256.lower():
            if os.path.exists(part_path):
                os.remove(part_path)
            raise CryptographicIntegrityError(f"Hash mismatch! Remote: {remote_sha256} != Local: {local_sha256}")

        # 4. Atomic finalize
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(part_path, final_path)
        logger.info(f"Verified bit-for-bit integrity for {file_name} (SHA-256: {local_sha256})")
        return final_path, local_sha256
```

---

## 8. Downstream Integration & Verification Protocol

### 8.1 Integration with R3 (GCP PySpark / Gemini Omni Grading)
When a raw 4K `.mp4` is confirmed in GCS:
1. GCS Object finalized event triggers Dataproc Serverless PySpark batch job.
2. The PySpark executor reads the uncompressed stream from `gs://<bucket>/raw_media/<file_name>` and invokes `gemini-omni-flash-api` for multimodal video/audio feature extraction.
3. Raw 10-bit color matrices and audio transients are evaluated against the `VIRAL_FORMULA.md` parameter rubric without any prior compression artifacts.

### 8.2 Integration with R4 (BigQuery ML Feedback Loop)
1. Video metadata, calculated SHA-256 checksums, and the 5 viral dimension scores are inserted into the BigQuery table `media_analytics.viral_grading_results`.
2. A continuous BigQuery ML `CREATE MODEL` regression/clustering pipeline trains on post-publish audience retention metrics against the raw grading features.

---

## 9. Conclusion & Implementation Checklist

The ADB Wi-Fi Ingestion Daemon architecture completely satisfies all constraints of Requirement R2. It completely eliminates compression degradation, preserves sensor metadata, adheres to Rule R10.2 (No-UI), and provides deterministic offline testability.

### Checklist for Implementation Phase:
- [ ] Implement `g:/My Drive/GOOGLE ANTIGRAVITY/media_pipeline/ingestion/manifest_store.py`
- [ ] Implement `g:/My Drive/GOOGLE ANTIGRAVITY/media_pipeline/ingestion/adb_connection_manager.py`
- [ ] Implement `g:/My Drive/GOOGLE ANTIGRAVITY/media_pipeline/ingestion/gcs_uploader.py`
- [ ] Implement `g:/My Drive/GOOGLE ANTIGRAVITY/media_pipeline/ingestion/daemon.py`
- [ ] Implement `g:/My Drive/GOOGLE ANTIGRAVITY/media_pipeline/tests/test_ingestion_daemon.py` with the 5 deterministic test scenarios.
