# Specification Mining Report: Pipeline Integration & Samsung S26 Ultra ADB Ingestion

**Document Identifier:** SPEC-MINER-01-PIPELINE-INTEGRATION  
**Target Directory:** `content_creation/` (Track 2: Media Engineering & Audio/Video Pipeline Automation)  
**Author:** Spec Miner 1  
**Date:** 2026-08-22  
**Status:** COMPLETE & GROUNDED  

---

## 1. Executive Summary & Architectural Overview

The Samsung S26 Ultra Concert Capture and Ingestion project introduces a critical hardware-to-local bridge to Noah Eidson's EDM Content Creation track. This document delivers the exhaustive specification mining results for **Requirement 3: Pipeline Integration**, probing:
1. `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` for exact insertion points, diagrams, and structural changes to incorporate **Phase 0: Hardware-to-Local ADB Ingestion** while strictly preserving all existing technical guardrails.
2. `config.py`, `ingest_assets.py`, `orchestrator.py`, `metadata_tracker.py`, and `ffmpeg_processor.py` for programmatic contracts, directory health partitioning, SQLite lifecycle schemas, and master CLI integration.
3. Test infrastructure in `content_creation/tests/` to specify deterministic unit tests using mocked ADB subprocess fixtures and blueprint integrity assertions.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Blueprint Structure | 6-Phase Lifecycle Architecture | Expansion of 5-Phase lifecycle to include Phase 0: Hardware-to-Local ADB Device Ingestion. | Raw device footage on Samsung Galaxy S26 Ultra (`/sdcard/DCIM/Camera/`). | Transferred raw 4K HDR files in `01_RAW_INBOX/{Event}/`. | If ADB disconnects, halts with retry/circuit breaker; falls back to manual drop. | `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` § 4.1 |
| 2 | Blueprint Topology | High-Level System Topology Update | Visual diagram linking S26 Ultra hardware -> `samsung_ingest.py` -> `01_RAW_INBOX` -> downstream AI Master Mind stack. | Device serial / USB connection. | ASCII Topology Graph in Blueprint § 1.5 & § 4.1. | N/A (Documentation specification). | `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` § 1.5 |
| 3 | Blueprint Mechanism | Mechanism 0 / Ingestion Expansion | Specification of `samsung_ingest.py` as an agent-executable mechanism in Section 3 alongside `ingest_watcher.py`. | CLI arguments (`--device`, `--recent`, `--event`, `--dest-dir`). | Ingestion results, transfer speed, staged file paths. | `ADBExecutionError`, `DeviceNotFoundError`, `TransferIntegrityError`. | `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` § 3 |
| 4 | Configuration | ADB Constants & Camera Defaults | Addition of Android camera paths, model identifiers (`SM-S948U`), buffer sizes, and ADB environment variables. | `DEFAULT_ANDROID_CAMERA_PATH`, `ADB_BINARY`. | Config dataclasses / constants in `config.py`. | Missing env falls back to system PATH and default `/sdcard/DCIM/Camera`. | `config.py` |
| 5 | ADB Bridge | Device Detection & Selection | Enumeration of connected devices via `adb devices -l`; auto-selection or explicit serial targeting. | Optional `--device <serial>`, custom `--adb-path`. | `ADBDeviceInfo` (serial, model, status, authorized). | Raises `NoDeviceConnectedError` or `DeviceUnauthorizedError`. | `samsung_ingest.py` specification |
| 6 | ADB Bridge | Remote Media Scanner & Filter | Headless inspection of remote Android camera directory with regex filtering and timestamp extraction. | Remote path, date filter (`--date`), count limit (`--recent N`). | List of `RemoteMediaAsset` records (filename, size, mtime, path). | Raises `RemoteDirectoryNotFoundError` if DCIM missing. | `samsung_ingest.py` specification |
| 7 | ADB Bridge | High-Speed Lossless Pull & Progress | Streaming file transfer via `adb pull -a` preserving creation timestamps and original 4K/8K HDR bitrates. | Source remote path, local destination folder. | Pulled local file, transfer rate (MB/s), duration. | Triggers 3-attempt circuit breaker on socket drop; cleans partial files. | `samsung_ingest.py` specification |
| 8 | Asset Integrity | Transfer Size & SHA-256 Verification | Compares remote file size against local byte count; computes SHA-256 checksum upon transfer completion. | Pulled local file, remote stat size. | Boolean match + calculated SHA-256 hex string. | Deletes corrupted pull; raises `ChecksumMismatchError`. | `ingest_assets.py` & `samsung_ingest.py` |
| 9 | Storage Health | 50-Item Ingestion Subfolder Partitioning | Integrates with `DirectoryHealthGuard` to guarantee raw inbox event partitions do not exceed 50 items. | Destination event directory, incoming asset list. | Healthy subfolder path (e.g. `01_RAW_INBOX/EDC2026_Batch02`). | Automatically branches to next partition when capacity reached. | `ingest_assets.py` § DirectoryHealthGuard |
| 10 | Deduplication | Ingestion History Ledger | Local persistent ledger tracking previously ingested remote filenames and SHA-256 hashes to prevent re-pulling. | Remote file inventory, local ledger file (`.adb_ingest_ledger.json`). | Filtered list of newly discovered assets. | Automatically skips existing files unless `--force` is specified. | `samsung_ingest.py` specification |
| 11 | Metadata Ledger | SQLite Asset Lifecycle Registration | Tracks origin metadata (`device_serial`, `remote_path`, `capture_time`) in `metadata_json` within `media_manifest.sqlite`. | Ingested asset details, device telemetry. | SQLite record in `asset_manifest` table. | ACID transaction guarantees consistency; rollbacks on error. | `metadata_tracker.py` § MediaManifestDB |
| 12 | Orchestration CLI | Master CLI Subcommand (`adb-ingest`) | Subcommand in `orchestrator.py` delegating to `samsung_ingest.py` for unified CLI administration. | `orchestrator.py adb-ingest [options]`. | Formatted CLI summary and exit code 0. | Non-zero exit code on transfer or device failure. | `orchestrator.py` § build_parser |
| 13 | Orchestration Pipeline | End-to-End Phone-to-Publish Pipeline | Optional `--from-device` flag in `orchestrator.py pipeline` executing Phone Pull -> Ingest -> Process -> QC -> Ready. | `orchestrator.py pipeline --input <device_clip> --from-device`. | Complete distribution package in `03_READY_TO_POST`. | Aborts pipeline early if device transfer fails. | `orchestrator.py` § run_master_pipeline |
| 14 | Downstream Transcode | 4K HDR10+ Mobius Tone-Mapping | Seamless downstream processing of S26 Ultra 10-bit HLG/PQ footage to BT.709 via FFmpeg `zscale` + `tonemap`. | 4K HDR S26 Ultra MP4 source. | 1080x1920 60fps CFR SDR master with laser highlight retention. | Preserves highlight details without crushing blacks or blowing out lasers. | `ffmpeg_processor.py` § FilterGraphBuilder |
| 15 | Downstream Audio | Concert Audio DSP Normalization | 80Hz festival high-pass filtering + two-pass EBU R128 loudnorm (-14.0 LUFS, <= -1.5 dBTP) for loud concert audio. | Raw stereo/multichannel audio stream. | Broadcast-grade normalized audio master. | Clamps true peak to <= -1.5 dBTP, eliminating festival bass distortion. | `ffmpeg_processor.py` & `config.py` |

---

## 3. Edge Cases & Remediation Matrix

| # | Feature | Input / Condition | Observed / Documented Behavior | Remediation & Agent Guardrail |
|---|---------|-------------------|--------------------------------|-------------------------------|
| 1 | ADB Device Connection | No Android device connected via USB or Wi-Fi (`adb devices` returns empty list). | `adb devices` returns only header `List of devices attached`. | Raise `NoDeviceConnectedError` with clear instruction: "Connect Samsung S26 Ultra via USB-C (USB 3.2 cable) and enable USB Debugging in Developer Options." |
| 2 | ADB Authorization | Device connected but unauthorized (`unauthorized` status in `adb devices`). | Device listed with `unauthorized` flag; commands like `adb shell` fail with permission denied. | Raise `DeviceUnauthorizedError`: "Unlock phone screen and tap 'Always allow from this computer' on the RSA fingerprint prompt." |
| 3 | Multiple Devices | Multiple Android devices/emulators connected simultaneously. | `adb pull` returns ambiguous target error (`error: more than one device/emulator`). | Implement smart filter: check `adb devices -l` for Samsung model string (`SM-S948*` / `SM-S938*`); if multiple matches, require `--device <serial>` flag. |
| 4 | Missing ADB Binary | `adb.exe` not found in PATH or standard Android SDK directories. | `shutil.which("adb")` returns `None`; subprocess raises `FileNotFoundError`. | Check `find_binary("adb", custom_path=args.adb_path, env_var="ADB_BINARY")` across common Windows SDK paths; print actionable installation guide (`winget install Google.PlatformTools`). |
| 5 | USB Disconnection Mid-Transfer | Cable disconnected or phone sleeps during multi-gigabyte 4K transfer. | `adb pull` subprocess terminates with non-zero exit code or `error: device not found`; partial file remains. | Implement 3-attempt retry loop. Always transfer to temporary `.part` file; delete `.part` on failure to prevent corrupted raw files entering inbox. |
| 6 | High-Capacity Inbox Folder | Ingesting 60+ raw concert clips into `01_RAW_INBOX/{Event}` in a single session. | Single folder exceeds 50 items, triggering Google Drive sync latency and IDE indexing lag. | Integrate `DirectoryHealthGuard.get_healthy_subfolder()` to auto-partition into `01_RAW_INBOX/{Event}_Batch01`, `Batch02`, etc. at 50 items. |
| 7 | Duplicate Ingestion | Running `samsung_ingest.py` multiple times on the same device after new takes are recorded. | Identical files re-pulled, wasting bandwidth and overwriting or creating duplicate versions. | Maintain `.adb_ingest_ledger.json` recording remote device file path, size, and modified timestamp. Automatically skip files present in ledger unless `--force` is set. |
| 8 | File Size Mismatch | Incomplete pull due to device storage read lock or premature termination. | Local file size != remote stat size. | Compare local `file.stat().st_size` with remote byte size returned from `adb shell stat -c %s`. If mismatch, delete local file and retry up to 3 times. |
| 9 | Non-Video Remote Files | Remote folder contains `.jpg`, `.dng`, `.heic` thumbnails or Samsung burst files. | Ingestion engine attempts to probe image files with video prober. | Enforce strict extension filtering on remote listing: only process `SUPPORTED_VIDEO_EXTENSIONS` (`.mp4`, `.mov`, `.mkv`, `.m4v`). |
| 10 | 8K Video Downscaling Overhead | User records 8K (4320x7680 or 7680x4320) video on S26 Ultra. | Heavy transcode compute latency and memory consumption during 9:16 re-framing. | Downstream `ffmpeg_processor.py` handles Lanczos downscale to 1080x1920 canvas with NVENC acceleration; Blueprint advises 4K 60fps capture in SOP. |
| 11 | Samsung Variable Frame Rate (VFR) | Phone records in dynamic VFR mode under extreme thermal conditions. | Progressive audio/video desync when processed by downstream lossy transcoders. | Downstream `ffmpeg_processor.py` enforces Constant Frame Rate (`-r 60` CFR with `-pix_fmt yuv420p`), mechanically repairing VFR drift. |
| 12 | Windows Path Length Limits | Deeply nested folders with long festival names (`01_RAW_INBOX/Tomorrowland_Belgium_2026_Weekend2_Mainstage_Batch01/...`). | Path length exceeds 260 chars on Windows if long paths not enabled in registry. | Use Python `pathlib.Path.resolve()` and enforce canonical sanitized token limits in `FilenameNormalizer`. |

---

## 4. Deep-Dive Specification Mining

### 4.1 `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` Insertion Points & Structural Mapping

To integrate Requirement 3 seamlessly, the Blueprint requires targeted structural enhancements across 5 specific sections while strictly retaining all existing parameters.

#### Exact Insertion Points:

1. **Table of Contents (Lines 22–67):**
   - Update Section 1.5 title: `1.5 System High-Level Topology & Flowchart Diagram (Including Phase 0 ADB Ingestion)`
   - Add Section 3.1: `3.1 Mechanism 0: Samsung S26 Ultra Hardware-to-Local ADB Ingestion Bridge (samsung_ingest.py)` (renumbering subsequent mechanisms to 3.2–3.5)
   - Update Section 4.1: `4.1 End-to-End 6-Phase Agent Orchestration Lifecycle (Phase 0 through Phase 5)`
   - Update Section 8.1: `8.1 Exhaustive Edge Cases & Concrete Remediation Matrix (Including ADB Hardware Faults)`

2. **Section 1.5 System High-Level Topology Diagram (Lines 177–208):**
   - Prepend the hardware capture stage:
     ```
     [Samsung Galaxy S26 Ultra] (Pro Video / 4K HDR10+ / ISO Locked)
               │ (USB 3.2 Gen 2 / Wi-Fi ADB Bridge)
               ▼
     [samsung_ingest.py] ──(Size Check & SHA-256 Ledger)──▶ [01_RAW_INBOX/{Event}/]
                                                                    │
                                                                    ▼
     [01_RAW_INBOX] ──▶ [ingest_assets.py] ──▶ [02_IN_PROGRESS/{project_id}/]
                              │
                              ▼
                      [audio_dsp.py] ──────────┐
                      - Librosa Drop Locator   │
                      - EBU R128 First-Pass    │
                      - High-Pass Filter Spec  │
                              │                │
                              ▼                ▼
                    [video_transcoder.py] ◀────┘
                    - 9:16 Center Crop & Re-frame
                    - Low-Light Spatio-Temporal Denoise
                    - HDR10+ to BT.709 Mobius Tone-Map
                    - Safe-Zone Kinetic Text Overlay
                    - Two-Pass Audio Loudnorm (-14 LUFS)
                    - Seamless 30ms Loop Crossfade
                              │
                              ▼
                     [qc_validator.py]
                    - ffprobe Stream Verification
                    - Duration <= 59.0s Guardrail
                    - Loudness: -14 LUFS / <= -1.5 dBTP
                    - Safe Zone Geometry Assertion
                              │
             ┌────────────────┴────────────────┐
             ▼ [PASS]                          ▼ [FAIL]
     [03_READY_TO_POST]               [02_IN_PROGRESS/Quarantine]
     - Signed qc_report.json          - Diagnostic Error Log
     - distribution_package.json      - Circuit Breaker Trigger
     ```

3. **Section 3 Concrete Technical Mechanisms (Lines 354–721):**
   - Insert **Mechanism 0: Direct Hardware-to-Local ADB Ingestion Bridge (`samsung_ingest.py`)**:
     - Class definitions: `SamsungADBIngestor`, `ADBDeviceManager`, `RemoteMediaAsset`, `ADBPullResult`.
     - JSON Schema for `adb_ingest_manifest.json`.
     - Production CLI invocation examples (`--device`, `--event`, `--recent`, `--auto-ingest`).

4. **Section 4.1 End-to-End Orchestration Lifecycle (Lines 725–760):**
   - Expand from 5 phases to **6 deterministic phases**:
     - **Phase 0: Hardware Capture & ADB Extraction**
       - S26 Ultra Pro Video capture according to `samsung_s26_concert_sop.md`.
       - Automatic ADB connection detection over USB 3.2 or secure local Wi-Fi pairing.
       - Scan `/sdcard/DCIM/Camera/` for uncompressed `.mp4` takes.
       - Lossless bit-for-bit pull directly into `01_RAW_INBOX/{Event}/` with 50-item partition protection.
       - Verification of transfer byte counts and SHA-256 ledger recording.
     - **Phase 1: Ingestion & Trigger** (Probing, canonical renaming, workspace staging).
     - **Phase 2: Deep Analysis & Classification** (Audio drop detection, brand routing).
     - **Phase 3: Automated Transcoding & Assembly** (9:16 re-framing, HDR tone-mapping, -14 LUFS loudnorm).
     - **Phase 4: Automated Verification & QC** (Duration <=59s, 1080x1920, 60fps CFR, -14 LUFS, <= -1.5 dBTP).
     - **Phase 5: Distribution Packaging & Metadata Staging** (SEO payloads, ghost-linking sync, 17-keyword moderation).

5. **Section 8.1 Troubleshooting & Edge Cases (Lines 987–1007):**
   - Append ADB-specific edge cases (device unauthorized, USB socket drop, storage full, non-video filtering, partition branching) to the existing 14 edge cases.

#### Retained Master Guardrails & Technical Boundaries:
- **Canvas Resolution:** $1080 \times 1920$ pixels (9:16 portrait orientation).
- **Framerate:** 60.0 fps Constant Frame Rate (CFR) strictly enforced.
- **Duration Guardrails:** Optimal 15.0–45.0s, Hard Ceiling $\le 59.00$s (Content ID safety).
- **Universal Safe Zones:**
  - YouTube Shorts: $900 \times 1270$ px ($X: 60-960, Y: 180-1450$).
  - TikTok: $920 \times 1310$ px ($X: 40-960, Y: 160-1470$).
  - Optimal text overlay anchor: $Y = 350$ px.
- **Audio Standards:**
  - Target Integrated Loudness: $-14.0\text{ LUFS} \pm 1.0\text{ LUFS}$.
  - True Peak: $\le -1.5\text{ dBTP}$ (hard ceiling $-1.0\text{ dBTP}$).
  - Loudness Range: $7.0\text{ LRA}$.
  - High-Pass Filter: $40\text{ Hz}$ (studio) / $80\text{ Hz}$ (festival).
  - Codec & Bitrate: AAC-LC at $320\text{ kbps}$, $48\text{ kHz}$ Stereo.
  - Seamless loop micro-fade: $30\text{ ms}$ linear crossfade.
- **Storage & Lifecycle:**
  - 4-Folder Hybrid Taxonomy: `01_RAW_INBOX`, `02_IN_PROGRESS`, `03_READY_TO_POST`, `04_ARCHIVE`.
  - Max 50 items per subfolder partition.
  - Canonical Naming: `YYYYMMDD_[Event]_[Artist]_[TrackName-or-ID]_V[#]_[Resolution].mp4`.
- **Platform Rules:** 17-Keyword Comment Spam Blocklist, TikTok 1–3% Ghost-Linking, YouTube Unlisted 30–60m Pre-Flight Hold.

---

### 4.2 Codebase Architecture & Schema Integration

#### 1. `config.py` Integration:
Add constants for Android device defaults:
```python
# Android ADB & Camera Hardware Settings
DEFAULT_ANDROID_CAMERA_PATH = "/sdcard/DCIM/Camera"
ALT_ANDROID_CAMERA_PATH = "/storage/emulated/0/DCIM/Camera"
SAMSUNG_MODEL_PREFIXES = ["SM-S948", "SM-S938", "SM-S928", "SM-S918"]  # Ultra series models
ADB_DEFAULT_TIMEOUT_SECONDS = 300
ADB_BUFFER_SIZE_BYTES = 1024 * 1024  # 1 MB chunk buffer
```

#### 2. `ingest_assets.py` Integration:
`samsung_ingest.py` interfaces cleanly with existing classes in `ingest_assets.py`:
- `DirectoryHealthGuard`: Invoked by `samsung_ingest.py` before pulling files to ensure destination directory in `01_RAW_INBOX` never exceeds 50 items:
  ```python
  health_guard = DirectoryHealthGuard(max_items=MAX_FOLDER_ITEMS)
  target_inbox = health_guard.get_healthy_subfolder(workspace_root / FOLDER_TIERS["INBOX"], event_slug)
  ```
- `calculate_sha256()`: Invoked on the local destination file immediately after `adb pull` to verify post-transfer integrity and generate cryptographic fingerprint.
- `find_binary("adb", custom_path=..., env_var="ADB_BINARY")`: Uses the identical discovery resolution hierarchy implemented in `ingest_assets.py`.

#### 3. `metadata_tracker.py` Integration:
`MediaManifestDB` tracks asset lifecycle from phone ingestion onward. The `metadata_json` field of `asset_manifest` seamlessly stores device provenance without schema migration:
```python
metadata_dict = {
    "ingestion_source": "samsung_adb",
    "device_serial": "RFCX10XYZAB",
    "device_model": "SM-S948U",
    "remote_camera_path": "/sdcard/DCIM/Camera/20260822_194512.mp4",
    "pull_timestamp": "2026-08-22T05:30:00Z",
    "pull_duration_sec": 4.2,
    "transfer_rate_mbps": 82.5,
    "sha256_verified": True
}
```

#### 4. `orchestrator.py` Integration:
- Add `adb-ingest` subcommand to `build_parser()`:
  ```python
  adb_p = subparsers.add_parser("adb-ingest", help="Pull raw 4K HDR footage directly from Samsung S26 Ultra via ADB.")
  adb_p.add_argument("--device", default=None, help="ADB device serial number.")
  adb_p.add_argument("--event", default="Concert", help="Event name for destination grouping.")
  adb_p.add_argument("--recent", type=int, default=None, help="Pull only the N most recent clips.")
  adb_p.add_argument("--date", default=None, help="Filter remote takes by date (YYYYMMDD).")
  adb_p.add_argument("--auto-ingest", action="store_true", help="Automatically trigger workspace staging after pull.")
  adb_p.add_argument("--dry-run", action="store_true", help="List device takes without pulling.")
  ```
- Add `--from-device` flag to `orchestrator.py pipeline` to enable seamless end-to-end execution from connected smartphone to ready-to-post export master.

#### 5. `ffmpeg_processor.py` Integration:
Ensures that raw high-bitrate 4K HDR10+ MP4 files captured by S26 Ultra Pro Video (often 100+ Mbps, 10-bit HLG or PQ color transfer `smpte2084`, BT.2020 primaries) are processed cleanly:
- `is_hdr` detected via `probe_media_file()`.
- Filtergraph automatically inserts `zscale=t=linear:npl=100,tonemap=mobius:desat=0.5,zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p` to map vibrant concert lasers into pristine SDR without highlight clipping.
- Spatio-temporal `hqdn3d` filtering smooths high-ISO sensor grain from low-light indoor rave stages.
- Two-pass EBU R128 loudnorm standardizes dynamic festival audio to $-14.0\text{ LUFS} \pm 1.0\text{ LUFS}$ and $\le -1.5\text{ dBTP}$.

---

### 4.3 `samsung_ingest.py` Complete Interface Specification

#### Class Interfaces & Data Structures:

```python
"""
samsung_ingest.py - Automated Samsung Galaxy S26 Ultra ADB Ingestion Bridge (Track 2)
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess

@dataclass
class ADBDeviceInfo:
    """Represents an attached Android device discovered via ADB."""
    serial: str
    state: str          # "device", "unauthorized", "offline"
    model: str          # e.g. "SM-S948U", "Galaxy S26 Ultra"
    product: str        # e.g. "dm3q"
    usb_port: str       # USB bus/port identifier
    is_authorized: bool

@dataclass
class RemoteMediaAsset:
    """Represents a media file discovered in device DCIM/Camera."""
    filename: str
    remote_path: str
    size_bytes: int
    modified_time: datetime
    extension: str

@dataclass
class ADBPullResult:
    """Outcome of an ADB file pull operation."""
    success: bool
    remote_asset: RemoteMediaAsset
    local_path: str
    size_bytes: int
    sha256_hash: str
    transfer_duration_sec: float
    transfer_rate_mbps: float
    error_message: Optional[str] = None

class SamsungADBIngestor:
    """
    Manages ADB connection, remote DCIM scanning, lossless USB 3.2 data transfer,
    file integrity verification, and 50-item inbox partitioning.
    """
    def __init__(
        self,
        workspace_root: Path,
        adb_path: Optional[str] = None,
        device_serial: Optional[str] = None,
        remote_camera_path: str = "/sdcard/DCIM/Camera"
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.adb_bin = self._resolve_adb_binary(adb_path)
        self.device_serial = device_serial
        self.remote_camera_path = remote_camera_path
        self.ledger_path = self.workspace_root / ".adb_ingest_ledger.json"

    def list_devices(self) -> List[ADBDeviceInfo]:
        """Executes 'adb devices -l' and parses connected Android hardware."""
        pass

    def select_device(self, preferred_serial: Optional[str] = None) -> ADBDeviceInfo:
        """Validates connection and returns active Samsung device."""
        pass

    def scan_remote_camera(
        self,
        date_filter: Optional[str] = None,
        recent_limit: Optional[int] = None,
        skip_previously_ingested: bool = True
    ) -> List[RemoteMediaAsset]:
        """Scans /sdcard/DCIM/Camera for .mp4/.mov files and extracts metadata."""
        pass

    def pull_asset(
        self,
        asset: RemoteMediaAsset,
        destination_dir: Path,
        verify_checksum: bool = True,
        max_retries: int = 3
    ) -> ADBPullResult:
        """Pulls asset via 'adb pull -a', verifies size and SHA-256, and records in ledger."""
        pass

    def ingest_batch(
        self,
        event_name: str = "Concert",
        date_filter: Optional[str] = None,
        recent_limit: Optional[int] = None,
        dry_run: bool = False,
        auto_stage: bool = False
    ) -> List[ADBPullResult]:
        """Executes full batch ingestion into 01_RAW_INBOX with 50-item partition guards."""
        pass
```

#### CLI Execution Commands:

1. **Scan & Dry-Run (Inspect pending concert takes on phone):**
   ```bash
   python content_creation/samsung_ingest.py --dry-run --recent 10
   ```

2. **Pull 5 Recent Clips from EDC Orlando into 01_RAW_INBOX:**
   ```bash
   python content_creation/samsung_ingest.py --event EDCOrlando --recent 5
   ```

3. **Pull All Takes from Specific Date with Automatic Staging:**
   ```bash
   python content_creation/samsung_ingest.py --event LostLands --date 20260822 --auto-ingest
   ```

4. **Master Orchestrator Integration:**
   ```bash
   python content_creation/orchestrator.py adb-ingest --event UltraMiami --recent 3
   ```

---

## 5. Acceptance Criteria & Test Suite Specification

### Test Plan: `content_creation/tests/test_samsung_ingest.py`

To ensure deterministic testing in any developer environment without requiring physical phone hardware or system ADB installation, the test suite must use mock subprocess fixtures:

| Test Case Method | Target Tested | Verification Logic |
| :--- | :--- | :--- |
| `test_adb_binary_discovery` | `find_binary("adb")` | Verifies custom path, env var, system path, and fallback discovery hierarchy. |
| `test_list_devices_parsing_single` | `SamsungADBIngestor.list_devices()` | Mocks `adb devices -l` output with single device; verifies model and authorization state. |
| `test_list_devices_parsing_unauthorized` | `SamsungADBIngestor.list_devices()` | Mocks unauthorized device; verifies `DeviceUnauthorizedError` is raised with clear help. |
| `test_list_devices_multiple_auto_select` | `SamsungADBIngestor.select_device()` | Mocks 2 devices (1 generic, 1 Samsung S26 Ultra); verifies auto-selection of Samsung model. |
| `test_remote_camera_scan_parsing` | `SamsungADBIngestor.scan_remote_camera()` | Mocks `adb shell ls -l` or `stat` output; verifies extraction of filenames, sizes, and timestamps. |
| `test_remote_camera_date_filtering` | `SamsungADBIngestor.scan_remote_camera()` | Verifies `--date 20260822` correctly filters out files from other dates. |
| `test_remote_camera_recent_limit` | `SamsungADBIngestor.scan_remote_camera()` | Verifies `--recent 5` extracts only the 5 most recent timestamps in descending order. |
| `test_pull_asset_success_with_sha256` | `SamsungADBIngestor.pull_asset()` | Mocks successful `adb pull`; verifies local file creation, size match, and SHA-256 calculation. |
| `test_pull_asset_size_mismatch_retry` | `SamsungADBIngestor.pull_asset()` | Mocks truncated transfer on attempt 1, success on attempt 2; verifies retry mechanism. |
| `test_pull_asset_exhausted_retries` | `SamsungADBIngestor.pull_asset()` | Mocks continuous transfer failure; verifies clean deletion of partial file and circuit breaker error. |
| `test_directory_health_50_item_guard` | `SamsungADBIngestor.ingest_batch()` | Verifies incoming pulls partition into `01_RAW_INBOX/Event_Batch01` and `Batch02` at 50 items. |
| `test_ledger_deduplication` | `SamsungADBIngestor.ledger` | Verifies files recorded in `.adb_ingest_ledger.json` are skipped on subsequent runs unless `--force`. |
| `test_cli_argument_parser` | `samsung_ingest.py main()` | Tests `--event`, `--recent`, `--date`, `--dry-run`, `--auto-ingest`, `--device` argument parsing. |

### Test Plan: Blueprint Integrity & Orchestrator Consistency

1. **`test_blueprint_consistency.py`**:
   - Asserts `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` exists and contains:
     - `Phase 0: Hardware-to-Local ADB Device Ingestion`
     - Reference to `samsung_ingest.py`
     - Reference to `samsung_s26_concert_sop.md`
     - Unchanged safe zone coordinates (YouTube $900 \times 1270$, TikTok $920 \times 1310$)
     - Unchanged audio loudness ($-14.0\text{ LUFS} \pm 1.0\text{ LUFS}$, $\le -1.5\text{ dBTP}$)
     - Hard duration ceiling $\le 59.00\text{s}$
     - 17-keyword comment spam filter string.
2. **`test_orchestrator_cli.py` Update**:
   - Asserts `orchestrator.py` recognizes `adb-ingest` subcommand and argument schema.

---

## 6. Implementation Roadmap & Hand-off Checklist

- [x] Survey existing codebase and Blueprint structure.
- [x] Determine exact insertion points and specifications for Phase 0 in V2 Blueprint.
- [x] Verify retention of all existing parameters (safe zones, audio loudness, export bitrates, 50-item partitions).
- [x] Document module-by-module integration points across `config.py`, `ingest_assets.py`, `orchestrator.py`, `metadata_tracker.py`, and `ffmpeg_processor.py`.
- [x] Specify comprehensive interface for `samsung_ingest.py` and mock-based test suite.
- [x] Deliver formal `report.md` and 5-component `handoff.md`.
