# Test Infrastructure Specification: Milestone 3 EDM Content Strategy Architecture

## Executive Summary
This document establishes the comprehensive test architecture, verification methodology, and quality assurance framework for Milestone 3 of the EDM Short-Form Content Strategy engine (`content_creation/`).

The test infrastructure enforces a strict **4-Tier Verification Methodology** ensuring deterministic, opaque-box validation of all automated media processing, audio DSP drop detection, and YouTube Data API v3 publishing systems without requiring external network access or GPU hardware.

---

## 1. Architectural Test Topology (4-Tier Framework)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TIER 4: REAL-WORLD SCENARIOS                          │
│  - Full Festival Set E2E (ADB Ingest -> Drop -> Transcode -> SEO -> Publish) │
│  - Copyright Strike Quarantine & Content ID Retention Simulation            │
├─────────────────────────────────────────────────────────────────────────────┤
│                    TIER 3: CROSS-FEATURE COMBINATIONS                       │
│  - Drop Detection + FFmpeg Transcoding + YouTube Publisher                  │
│  - Manual Timestamp Override + YouTube Dry-Run Pipeline                     │
│  - Samsung S26 ADB Ingest + Librosa Audio Windowing                         │
│  - Corrupted Stream -> Graceful Fallback -> SQLite Manifest Sync            │
├─────────────────────────────────────────────────────────────────────────────┤
│                    TIER 2: BOUNDARY & CORNER CASES                          │
│  - Zero/Silent Audio (All Zeros)        - Dirac Delta & +6dBFS Clamping     │
│  - 0s / Negative Manual Overrides       - 100-Char Title Truncation Ceiling │
│  - Unicode/Diacritics/Emoji SEO Strings - YouTube API 500s & Timeouts       │
├─────────────────────────────────────────────────────────────────────────────┤
│                    TIER 1: FEATURE COVERAGE (≥5 / REQ)                       │
│  - R1: Librosa RMS Engine (Argmax, Fallback, Demux, Override, Duration)     │
│  - R2: YouTube Data API (Unlisted Insert, Content ID Poll, Promote, DryRun) │
│  - R3: Master CLI (CLI Flags, Subcommands, Chaining, DB Manifest Lifecycle) │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Mocking Strategy & Deterministic Test Harnesses

To guarantee 100% test reproducibility, execution speed (<5s total runtime), and independence from external cloud services or physical hardware:

### 2.1 Mock Audio DSP & Librosa Harness (`MockLibrosaHarness`)
- **Purpose**: Simulates audio waveforms (sine waves, white noise, Dirac impulses, silent buffers) and generates predictable RMS energy contours.
- **Mechanisms**:
  - Intercepts `librosa.feature.rms` or executes the pure NumPy vectorized fallback.
  - Simulates peak energy concentrated in known time windows (e.g. 45.0s - 75.0s in a 120s track).
  - Emulates `librosa.load` and in-memory FFmpeg raw PCM demuxing (`-f s16le`).

### 2.2 Mock FFmpeg Transcoder Harness (`MockFFmpegHarness`)
- **Purpose**: Simulates video/audio transcoding, EBU R128 loudnorm measurement output, and file generation without requiring GPU acceleration.
- **Mechanisms**:
  - Intercepts `subprocess.run` calls to `ffmpeg` and `ffprobe`.
  - Injects valid JSON stderr for EBU R128 Pass 1 (`input_i`, `input_tp`, `input_lra`, `input_thresh`).
  - Synthesizes target output MP4 container files and validates filtergraph argument syntax (crop, tonemap, loudnorm, drawtext, afade).

### 2.3 Mock YouTube Data API v3 Harness (`MockYouTubeAPIHarness`)
- **Purpose**: Simulates Google API Client discovery, `videos.insert`, `videos.list`, and `videos.update` operations.
- **Mechanisms**:
  - Emulates OAuth2 token credentials and API client building.
  - Returns structured mock responses for upload status (`uploaded`, `processing`, `processed`).
  - Injects Content ID audit states (`UNLISTED_CLEARED`, `CLAIMED`, `BLOCKED`, `REJECTED`).
  - Simulates API network timeouts and exponential backoff retry cycles.

### 2.4 Mock Samsung ADB Bridge Harness (`MockADBHarness`)
- **Purpose**: Simulates Android Debug Bridge device discovery and camera asset pulling.
- **Mechanisms**:
  - Emulates `adb devices -l` output for Samsung S26 Ultra flagship hardware.
  - Emulates `adb pull` transferring raw 4K 60fps MP4 takes into `01_RAW_INBOX`.

---

## 3. Tier 1: Feature Coverage Specifications

### Requirement 1: Librosa Drop Detection Engine (`audio_dsp.py`)
| Test ID | Test Name | Target Behavior | Expected Result |
|---|---|---|---|
| `T1.R1.01` | `test_rms_energy_contour_argmax` | 120s synthetic track with peak at 45s–75s | Returns `start_time_sec=45.0`, `duration_sec=30.0`, `end_time_sec=75.0` |
| `T1.R1.02` | `test_numpy_fallback_drop_detection` | Drop detection when `librosa` is unavailable | Executes vectorized numpy RMS, returns identical argmax window |
| `T1.R1.03` | `test_audio_buffer_demuxing` | Extracting raw PCM stream from MP4 container | Yields 1D float32 numpy array normalized to `[-1.0, 1.0]` |
| `T1.R1.04` | `test_cli_manual_override_precedence` | Passing `--start-time 15.0 --duration 20.0` | Bypasses RMS analysis; returns `start_time_sec=15.0`, `duration_sec=20.0`, `is_manual_override=True` |
| `T1.R1.05` | `test_custom_drop_duration_window` | Requesting 45.0s drop window instead of 30.0s | Computes 45.0s sliding window argmax correctly |
| `T1.R1.06` | `test_short_audio_clamping` | Audio track shorter than target duration (e.g. 18.5s) | Clamps window to audio length (18.5s) without index errors |

### Requirement 2: YouTube Data API Auditing Loop (`youtube_publisher.py`)
| Test ID | Test Name | Target Behavior | Expected Result |
|---|---|---|---|
| `T2.R2.01` | `test_upload_unlisted_video` | Uploading 1080x1920 MP4 with metadata | Calls `videos.insert` with `privacyStatus='unlisted'`, category `10`, `madeForKids=False`; returns `video_id` |
| `T2.R2.02` | `test_content_id_clean_and_promote` | Polling clean video with no copyright claims | Polls `videos.list`, detects `processingStatus='succeeded'`, calls `videos.update` with `privacyStatus='public'` |
| `T2.R2.03` | `test_content_id_blocked_retains_unlisted` | Video triggers Content ID block (`rejectionReason='copyright'`) | Halts promotion; video remains `privacyStatus='unlisted'`; sets `is_blocked=True`, `content_id_status='BLOCKED'` |
| `T2.R2.04` | `test_polling_timeout_handling` | Processing remains in `processing` state beyond timeout | Terminates polling gracefully; returns `processing_status='timeout'`; avoids infinite loops |
| `T2.R2.05` | `test_dry_run_mode_publishing` | Invoking publisher with `dry_run=True` | Simulates full workflow, returns valid `YouTubePublishResult` with mock ID and URL; zero API calls |
| `T2.R2.06` | `test_auth_credential_hierarchy` | Resolving credentials from token file vs env vars | Correctly selects active token source according to precedence hierarchy |

### Requirement 3: Master Orchestrator CLI & Chaining (`orchestrator.py`)
| Test ID | Test Name | Target Behavior | Expected Result |
|---|---|---|---|
| `T3.R3.01` | `test_master_cli_argument_parsing` | CLI flags `--auto-drop`, `--drop-duration`, `--publish-youtube` | Correctly parses all new flags into namespace |
| `T3.R3.02` | `test_publish_youtube_subcommand` | Invoking standalone `publish-youtube` CLI subcommand | Dispatches directly to `YouTubePublisher` with provided video path and metadata |
| `T3.R3.03` | `test_pipeline_chaining_auto_drop` | Running `pipeline` with `--auto-drop` | Invokes `AudioDropDetector`, passes optimal timestamps to `FFmpegMasterProcessor` |
| `T3.R3.04` | `test_pipeline_chaining_manual_override` | Running `pipeline` with `--start-time 10.0 --duration 25.0` | Bypasses `AudioDropDetector` and uses explicit 10s–35s window |
| `T3.R3.05` | `test_pipeline_chaining_publish_youtube` | Running `pipeline` with `--publish-youtube` | Chained execution publishes rendered master to YouTube and updates SQLite manifest to `POSTED` |

---

## 4. Tier 2: Boundary & Corner Cases

| Test ID | Boundary Condition | Edge Scenario | Verification Method |
|---|---|---|---|
| `T2.BC.01` | **Silent Audio Buffer** | Input audio is completely zeroed (all samples = 0.0) | Drop detector returns `start_time_sec=0.0`, `max_rms_energy=0.0` without divide-by-zero or NaN |
| `T2.BC.02` | **Extreme Energy Spikes** | Audio contains +6.0 dBFS clipping or Dirac impulses | Vectorized RMS handles values gracefully without floating-point overflow |
| `T2.BC.03` | **Invalid Timestamp Overrides** | Negative start time (`-5.0s`) or start time exceeding file duration (`200.0s` on 60s file) | Input validator clamps start time to `[0.0, max_duration]` |
| `T2.BC.04` | **100-Char Title Boundary** | Generated YouTube Shorts title is 150+ characters | SEOCaptionGenerator truncates title to strictly <100 chars without breaking words |
| `T2.BC.05` | **Unicode & Emoji SEO** | Artist names with diacritics (`Tiësto`, `Kölsch`) and emojis (`🔥`, `⚡`) | Full unicode preservation in JSON sidecar and YouTube API payloads |
| `T2.BC.06` | **YouTube API 500 & Network Errors** | Transient HTTP 500/503 errors during polling loop | Publisher executes retry loop with exponential backoff before reporting failure |

---

## 5. Tier 3: Cross-Feature Combinations

| Test ID | Cross-Feature Combination | Description |
|---|---|---|
| `T3.XC.01` | **Drop Detection + Transcoding + YouTube Publish** | Raw asset is analyzed for RMS peak $\to$ FFmpeg trims and renders 9:16 vertical MP4 $\to$ YouTube publisher uploads unlisted, audits Content ID, and promotes to public. |
| `T3.XC.02` | **Manual Override + YouTube Dry-Run** | User provides explicit `--start-time 32.5 --duration 28.0` $\to$ FFmpeg transcode uses exact timestamps $\to$ YouTube publisher runs dry-run, recording simulated publish URL in SQLite. |
| `T3.XC.03` | **ADB Ingest + Auto Drop Detection** | Samsung S26 Ultra camera take is pulled via ADB bridge $\to$ Audio stream is probed and analyzed by `AudioDropDetector` $\to$ Staged in `02_IN_PROGRESS` with drop metadata. |
| `T3.XC.04` | **Corrupted Audio Stream + Graceful Degradation** | Video file has missing/corrupt audio track $\to$ Drop detector logs warning and falls back to `start_time_sec=0.0` $\to$ Transcoding proceeds with silent audio track. |

---

## 6. Tier 4: Real-World Scenarios

### Scenario 1: Complete Autonomous Festival Set Reel Production (`T4.RW.01`)
- **Input**: 3-minute raw 4K 60fps concert take (`20260822_UltraMiami_Garrix_Animals_Raw.mp4`).
- **Pipeline Execution**:
  1. Asset probed & routed: Resolution 3840x2160, 60fps, HDR10+.
  2. `AudioDropDetector` analyzes 180s track, identifies massive energy peak at `85.0s - 115.0s`.
  3. `FFmpegMasterProcessor` executes 2-pass transcoding:
     - 9:16 center crop & 1080x1920 downscale
     - Mobius HDR->SDR tone-mapping
     - 2-pass EBU R128 loudness normalization (-14.0 LUFS, -1.5 dBTP)
     - 30ms linear loop crossfade
  4. `SafeZoneAuditor` confirms visual overlays respect 900x1160 safe zone.
  5. `SEOCaptionGenerator` synthesizes title, caption, and 5-7 hashtags.
  6. `YouTubePublisher` uploads unlisted, polls Content ID, detects clean status, and promotes to public.
  7. `MediaManifestDB` logs complete record with status `POSTED` and `UNLISTED_CLEARED`.

### Scenario 2: Copyright Blocked Track Quarantine SOP (`T4.RW.02`)
- **Input**: Unreleased festival bootleg with high copyright risk.
- **Pipeline Execution**:
  1. Video rendered and uploaded as "Unlisted".
  2. Polling loop receives Content ID block (`rejectionReason='copyright'`).
  3. Publisher prevents promotion to public, keeping video "Unlisted".
  4. System updates SQLite manifest to `current_status='READY_TO_POST'`, `youtube_content_id_status='BLOCKED'`.
  5. Alert is emitted with remediation recommendations.

---

## 7. Test Execution Runbook

To execute the full E2E test suite in PowerShell:

```powershell
# Navigate to content_creation directory
cd "G:\My Drive\GOOGLE ANTIGRAVITY\content_creation"

# Run full E2E test suite
python -m unittest tests.test_e2e_pipeline -v

# Run entire test suite across all modules
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 8. Quality Assurance & Forensic Integrity Matrix

| Criterion | Specification | Enforced By |
|---|---|---|
| **Zero Facade Testing** | All tests must assert genuine state transformations, return types, and file outputs. | Opaque-box assertions |
| **Deterministic Execution** | Zero flaky tests; all random seeds and timestamps mocked/pinned. | Mock harnesses |
| **Domain Rule Isolation** | Strictly zero sports card schemas, Card Ladder ETL, or grading attributes. | `content_creation/GEMINI.md` |
| **Duration Limit Compliance** | Every rendered short-form video must strictly obey $\le 59.0\text{s}$. | `QCReport.duration_compliant` |
| **Audio Loudness Standards** | Target $-14.0\text{ LUFS} \pm 1.0\text{ LUFS}$, True Peak $\le -1.5\text{ dBTP}$. | EBU R128 QC verification |
