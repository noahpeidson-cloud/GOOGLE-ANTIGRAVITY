# Handoff Report — Ingestion Architecture Deep Research & Daemon Design (R2)

**Author:** teamwork_preview_explorer_survey_2  
**Target:** `g:/My Drive/GOOGLE ANTIGRAVITY/media_pipeline`  
**Date:** 2026-08-24T21:05:30Z  
**Status:** Hard Handoff (Task Complete)  

---

## 1. Observation

1. **User Objective & Requirement Definition:**
   - Evaluated `ORIGINAL_REQUEST.md` (lines 93–98, 110–112):
     > "R2. Ingestion Architecture (Deep Research & Implementation): Conduct a deep research phase evaluating two ingestion paths: 1. Google Photos Automation... 2. Android ADB Wi-Fi Sync... Based on this research, implement the superior ingestion daemon that guarantees zero compression and seamlessly routes the raw .mp4/.jpg files to Google Cloud Storage."
     > "Ingestion Verification: A test script running a mock ADB transfer correctly hashes a local dummy file, uploads it to a local/mock GCS bucket, and proves the hashes match exactly (Zero Quality Loss)."

2. **Existing Workspace Skills & Protocols:**
   - Inspected `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\edm-master-mind-pipeline\SKILL.md` (lines 18–25):
     > "1. Ingestion (Zero-Touch): Execute `adb pull` exclusively targeting `/sdcard/DCIM/EDM_Drops`. Do not download files that already exist in the local manifest. 2. Proxy Generation (FFmpeg)... Move 4K raw files to 01_RAW/."
   - Inspected `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\zero-touch-mobile-provisioning\SKILL.md` (lines 76–80):
     > "1. The Samsung Auto Blocker Timeout: On Samsung One UI 6.0+, Auto Blocker will secretly turn itself back on and kill ADB connections after a timeout. Before deploying prolonged ADB sessions, you MUST kill the auto-enablement timer: `adb shell settings put global rampart_auto_enabled_switch_enabled 0`"

3. **Google Photos API Technical Constraints:**
   - Google Photos REST API `baseUrl=dv` endpoint forces cloud video downsampling / re-encoding for web streaming rather than serving raw 10-bit HDR HEVC bitstreams.
   - Google Photos 2025 Picker API policy restricts headless background sweeping (`photoslibrary.readonly` scope deprecated in favor of user-interactive picking modals), violating Rule R10.2 (No-UI Mandate).
   - Sensor gyro metadata, ISOBMFF metadata atoms, and embedded color spaces (BT.2020) are stripped or decoupled into sidecars by Google Photos ingestion.

4. **Android ADB Wi-Fi Extraction Mechanics:**
   - `adb sync` suffers from FUSE timestamp virtualization issues on modern Android 11+ `/sdcard` mounts.
   - `adb pull` with `.part` atomic staging, on-device `sha256sum`, and local streaming `hashlib.sha256()` allows deterministic, bit-for-bit, zero-compression raw container extraction over local Wi-Fi (500–1200 Mbps).

---

## 2. Logic Chain

1. **Step 1 (Observation 1 & 3):** The project goal requires feeding pristine, uncompressed 4K HDR videos into the Gemini Omni Video grading engine (R3). Because Google Photos API enforces video transcoding on download and strips sensor gyro metadata, using Google Photos introduces irreversible quality and metadata degradation.
2. **Step 2 (Observation 2 & 3):** The workspace mandates the Zero-Touch No-UI Protocol (Rule R10.2). Because Google's updated Photos API requires interactive user UI selection via the Photos Picker, Google Photos cannot run as an autonomous background daemon.
3. **Step 3 (Observation 2 & 4):** Android ADB Wi-Fi Sync provides direct block/file access to `/sdcard/DCIM/Camera`. Neutralizing Samsung Auto Blocker via `adb shell settings put global rampart_auto_enabled_switch_enabled 0` permits persistent wireless connections.
4. **Step 4 (Observation 4):** Comparing `adb sync` vs `adb pull`, `adb sync` fails deterministically on Android 11+ FUSE `/sdcard` storage due to mtime mismatches. `adb pull` combined with staged `.part` files and pre/post-transfer SHA-256 cryptographic verification guarantees bit-for-bit integrity and atomic recovery from wireless drops.
5. **Step 5 (Architecture Synthesis):** Pairing the `AdbConnectionManager` (mDNS auto-connect + backoff), `IncrementalMediaScanner` (with 2-interval recording stability check), `IntegrityVerifier` (`sha256sum` device-to-host assertion), SQLite state manifest, and `GCSStreamingUploader` (resumable chunked upload with CRC32c/MD5 validation) produces a complete, resilient, zero-compression ingestion pipeline.
6. **Step 6 (Testability):** Creating `MockAdbDevice` and `MockGCSClient` allows 100% deterministic, offline TDAD verification with loud assertions.

---

## 3. Caveats

1. **Android Wireless Debugging Dynamic Port Changes:** On Android 11+, if the mobile device reboots or reconnects to Wi-Fi, the Wireless Debugging port can change dynamically. The daemon architecture incorporates Zeroconf/mDNS discovery (`_adb-tls-connect._tcp`) to detect dynamic ports, but static IP fallback assumes a fixed router DHCP lease or static port 5555.
2. **Network Bandwidth Saturation:** Pushing multiple 5–15GB 4K video files concurrently over Wi-Fi and WAN uplink may saturate bandwidth. The daemon defaults to sequential, single-file pipelining (`pull` -> `verify` -> `upload`) to ensure stability.
3. **Storage Quota on Local Host Staging:** The local staging directory requires sufficient disk buffer (at least 2x the largest expected raw video file, ~30GB recommended).

---

## 4. Conclusion

- **Decision:** Android ADB Wi-Fi Sync is conclusively selected; Google Photos Automation is rejected.
- **Deliverable:** The complete architectural specification, state machines, SQLite schema, and test harness blueprints are documented in `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_2\analysis.md`.
- **Actionable Path for SWE / Implementer:**
  1. Build `manifest_store.py`, `adb_connection_manager.py`, `gcs_uploader.py`, and `ingestion_daemon.py` under `g:/My Drive/GOOGLE ANTIGRAVITY/media_pipeline/ingestion/`.
  2. Implement the offline test suite `test_ingestion_daemon.py` covering the 5 loud assertion scenarios.

---

## 5. Verification Method

Downstream agents and reviewers can independently verify this survey and specification using:

1. **Inspect Architectural Specification:**
   ```powershell
   Get-Content -Path "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_2\analysis.md"
   ```

2. **Verify SQLite Schema & Manifest Structure:**
   Check Section 5.4 of `analysis.md` for complete table schema including all required integrity hashes (`device_sha256`, `local_sha256`, `gcs_crc32c`, `gcs_md5`).

3. **Verify Offline Test Harness Design:**
   Verify Section 6 of `analysis.md` for the 5 deterministic test scenarios (`test_e2e_zero_compression_happy_path`, `test_wifi_drop_recovery_with_backoff`, `test_bit_flip_corruption_detection`, `test_active_recording_guard`, `test_daemon_single_instance_lock`).