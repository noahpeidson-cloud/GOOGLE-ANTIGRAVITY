# Unified Ops Hub: Comprehensive Codebase & Architectural Survey Report

**Author**: Explorer Subagent (`explorer_survey_codebase`)  
**Workspace**: `g:\My Drive\GOOGLE ANTIGRAVITY`  
**Target Hub Path**: `g:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub`  
**Date**: 2026-08-26 (UTC)  
**Parent Agent**: `0ed1cf9f-fb22-4a88-aa7e-30539e35df1b`

---

## 1. Executive Summary & Scope

A comprehensive architectural and code-level investigation of `g:\My Drive\GOOGLE ANTIGRAVITY` was performed to survey all existing Python backend daemons, servers, background workers, ports, routes, data flows, failure handling strategies, and test suites.

The Antigravity workspace hosts multiple autonomous, production-grade subsystems spanning:
1. **Sports Card Ecosystem Hub (`sports_cards/ecosystem_hub`)**: 21-variable schema ingestion, Chrome Extension bridge, HTML checklist scraper, Gemini vision extraction, SQLite WAL database, Facebook Marketplace listing generator, and Card Ladder 16-variable CSV exporter.
2. **Track 2 EDM Content Creation Pipeline (`content_creation/`)**: FastAPI remote trigger server, Tasker mobile integration, ADB zero-compression video pull, Librosa 30s RMS drop detector, FFmpeg proxy generation, DaVinci Resolve Python API timeline constructor, and YouTube Data API v3 publisher.
3. **Distributed Media Ingestion & PySpark Grading Pipeline (`media_pipeline/`)**: Incremental media scanner with 2-tick active recording guard, SHA-256 bit-for-bit cryptographic validation, GCS streaming uploader, Dataproc/local PySpark multimodal grading job with Gemini API client, Dead Letter Queue (DLQ) serialization, and BigQuery ML dynamic feedback loop.
4. **Autonomous Cron & System Health Scanner (`.agents/cron/`)**: Daily AST safety analyzer, ghost daemon/socket collision detector, context rot detector, ecosystem pollution detector, secret zero detector, prompt fatigue scanner, and localized NumPy/Pandas K-Means ProTeGi textual gradient optimizer.
5. **Comms, Logistics & MCP Integrations (Root Utilities & `apps/`)**: `sync_drive_to_sqlite.py` (Drive API delta syncer), `workspace_mcp.py` (Gmail & Calendar MCP server), `mastermind_agent.py` (Google Antigravity SDK ultra agent), `watchdog.py` (task mirroring), and `ops_hub.py` (Streamlit SOP viewer).

The proposed **Unified Ops Hub (`g:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub`)** will serve as the single, centralized operational brain—unifying routing, background daemon lifecycle management, port virtualization, real-time telemetry, and DLQ remediation across all tracks.

---

## 2. Inventory of Daemons, Frameworks, Ports & Routes

### 2.1 Port Allocation & Collision Matrix

| Subsystem / Daemon | Framework | Default Port | Config / Override | Target File & Line | Collision Risk & Notes |
|---|---|---|---|---|---|
| **Sports Cards API Bridge** | FastAPI / Uvicorn | `8002` (in `api.py`) / `8000` (in `boot_hub.py`) | `PORT` / CLI args | `sports_cards/ecosystem_hub/api.py:671,709` `sports_cards/ecosystem_hub/boot_hub.py:11` | **CRITICAL COLLISION**: `boot_hub.py` boots on `8000`, conflicting directly with `content_creation/remote_trigger.py` (port `8000`). |
| **EDM Remote Trigger Server** | FastAPI / Uvicorn | `8000` | `REMOTE_TRIGGER_PORT` env var | `content_creation/remote_trigger.py:1365` | **CRITICAL COLLISION**: Clashes with `sports_cards/boot_hub.py` on `8000`. |
| **Sports Cards Staging Hub** | Streamlit | `8501` | `--server.port` | `sports_cards/ecosystem_hub/boot_hub.py:20` | **HIGH COLLISION**: Clashes with `ops_hub.py` (port `8501`). |
| **Antigravity Operations Hub (SOPs)** | Streamlit | `8501` | `--server.port` | `ops_hub.py:1` | **HIGH COLLISION**: Clashes with Sports Card Streamlit on `8501`. |
| **YouTube Publisher OAuth** | Google OAuth Local Server | `8080` | `port=8080` | `content_creation/youtube_publisher.py:75` | **COLLISION**: Clashes with legacy Chrome extension target / `inbox_server.py`. |
| **Legacy Ingestion Inbox** | FastAPI / Uvicorn | `8080` | hardcoded `8080` | `archive/inbox_server.py:64` | Targeted by `apps/zero_friction_capture_extension/sidepanel/sidepanel.js:90`. |
| **Next.js Mobile App** | Next.js / Node | `3000` | `PORT=3000` | `apps/agy_mobile/package.json` | Standard Next.js dev server. |
| **Android ADB Wi-Fi Daemon** | TCP Socket | `5555` | `device_ip:5555` | `media_pipeline/ingestion/adb_connection_manager.py:48` | Standard ADB Wi-Fi port. |

---

### 2.2 Complete Endpoint & Route Catalog

#### A. Sports Cards Ecosystem API (`sports_cards/ecosystem_hub/api.py`)
- `GET /health` & `GET /api/v1/health`: Returns SQLite connectivity, total cards, portfolio stats, circuit breaker status.
- `POST /api/v1/cards/capture`: Ingests single card payload from Chrome Extension with 21-variable schema validation, query synthesis, and tracking notes resolution.
- `POST /api/v1/cards/batch`: Atomic transaction batch ingestion (up to 500 records).
- `GET /api/v1/cards`: Query staged cards with filters (`status_filter`, `category_filter`, `search_query`, `limit`, `offset`, `order_by`).
- `GET /api/v1/cards/{card_id}`: Single card retrieval.
- `PATCH /api/v1/cards/{card_id}`: Partial update with automatic query re-synthesis.
- `DELETE /api/v1/cards/{card_id}`: Hard delete card from staging.
- `POST /api/v1/cards/{card_id}/status`: Updates AI review status (`CLEARED`, `REVIEW VARIATION`, `NEEDS REVIEW`).
- `POST /api/v1/cards/{card_id}/listing`: Generates SEO-optimized Facebook Marketplace listing copy.
- `POST /api/v1/sales/generate`: On-demand listing generator from inline card data or card ID.
- `GET /api/v1/stats`: Aggregated summary statistics (investment, estimated value, card counts).
- `GET /api/v1/circuit-breaker`: Capacity monitoring (limit: 500 items).
- `POST /api/v1/cards/staging/clear`: Truncates card staging table.

#### B. Content Creation Remote Trigger & PWA Server (`content_creation/remote_trigger.py`)
- `GET /`: Serves static PWA Web App and review dashboard.
- `GET /manifest.json`: Serves Web App Manifest for mobile installation.
- `POST /trigger-pipeline`: Asynchronously initiates video processing pipeline (returns HTTP 202 Accepted in <50ms with `job_id`, or HTTP 409 Conflict if busy).
- `GET /status` & `GET /status/{job_id}`: Real-time telemetry, stage progression, and job state (`idle`, `running`, `completed`, `failed`, `cancelled`).
- `GET /health`: Diagnostic probe for disk space, ADB, FFmpeg, and FFprobe readiness.
- `GET /logs`: In-memory ring buffer log reader with filtering.
- `POST /cancel`: Graceful subprocess termination.
- `GET /api/clips/pending`: Discovers video takes awaiting review in `02_AWAITING_REVIEW/`.
- `GET /proxies` & `GET /api/proxies`: Lists available low-resolution 720p H.264 video proxies.
- `GET /proxies/{clip_id}/video` & `GET /api/proxy/{clip_id}/video`: Range-request streaming video endpoint for mobile scrubbers.
- `POST /approve-render` & `POST /api/approve-render`: Triggers DaVinci Resolve handoff and YouTube publishing flow.
- `POST /api/resolve/handoff`: Direct API bridge for DaVinci Resolve Python scripting engine.

---

### 2.3 Background Daemons & Polling Workers

1. **Android Ingestion Daemon (`media_pipeline/ingestion/ingestion_daemon.py`)**:
   - Background loop polling `/sdcard/DCIM/Camera` and `/sdcard/DCIM/EDM_Drops`.
   - Single-instance process lock via `ProcessLock` (`.ingestion_daemon.lock` using `msvcrt` on Windows).
   - SQLite Manifest (`ingestion_manifest.db`).
   - Downloads to `.part` files, verifies on-device vs. local SHA-256, promotes atomically to GCS bucket (`gs://<bucket>/raw_media/`).

2. **PySpark Batch Video Grading Job (`media_pipeline/grading/spark_grading_job.py`)**:
   - Discovers un-graded media in GCS or SQLite manifest.
   - Fetches active dynamic regression weights from BigQuery `media_pipeline.model_parameter_weights`.
   - Distributed partition mapping with Gemini Omni multimodal video client.
   - Dead Letter Queue serialization (`dlq_<video_id>_<timestamp>.json`) for bad codecs or rate limits.
   - Sinks structured scores to BigQuery `media_pipeline.video_grades`.

3. **BigQuery ML Feedback Loop (`media_pipeline/bqml/feedback_loop.py`)**:
   - Evaluates social engagement data against video scores.
   - Runs `CREATE OR REPLACE MODEL` (Linear Regression / Boosted Tree).
   - Extracts coefficients via `ML.WEIGHTS`, normalizes sum to 1.0000, and updates active parameter weights.

4. **Google Drive Metadata Sync Daemon (`sync_drive_to_sqlite.py`)**:
   - Polls Google Drive API v3 every 300s using change tokens.
   - Backfills and updates metadata to `apps/inbox.db` (`drive_metadata` table).

5. **Real-Time Transparency Watchdog (`watchdog.py`)**:
   - 1.0s debounced file watcher mirroring active subagent `progress.md` to user `task.md`.

6. **Daily Antigravity Health Scanner Daemon (`.agents/cron/scanner_daemon.py`)**:
   - Scans socket collisions (ports 3000, 8000, 8501), context rot, ecosystem leaks, placeholder secrets, and token fatigue.
   - Logs sessions and anomalies to `health_telemetry.db`.

---

## 3. Deep Dive: Sports Card Ecosystem Hub Architecture

```
[Chrome Extension (Prompt API)]  --> [POST /api/v1/cards/capture] --\
[HTML Checklist Scraper]         --> [parse_checklist_html()]     ----> [portfolio.db (SQLite WAL)]
[Gemini Vision Extractor]        --> [extract_card_from_image()] --/          |
                                                                               v
[Card Ladder 16-Col CSV Exporter] <------- [Streamlit Hub (app.py)] <--- [get_all_cards()]
[Marketplace Listing Generator]   <------- [sales_generator.py]
```

### 3.1 Data Schema & Integrity Controls
- **21-Variable Canonical Schema**:
  `id`, `date_purchased`, `quantity`, `player`, `year`, `set_name`, `variation`, `card_number`, `category`, `condition`, `slab_serial_number`, `investment`, `estimated_value`, `ladder_id`, `query`, `notes`, `tags`, `date_sold`, `sold_price`, `image`, `back_image`, `ai_status`, `created_at`, `updated_at`.
- **Enforced Constraints & Trigger Logic**:
  - `condition`: Must be `'Raw'` or graded (e.g. `'PSA 10'`, `'BGS 9.5'`, `'SGC 10'`).
  - `slab_serial_number`: STRICTLY FORBIDDEN on `Raw` cards. Triggers check constraint `NOT(condition = 'Raw' AND slab_serial_number != '')`.
  - `category`: Must match one of 22 valid categories (e.g. `Basketball`, `Football`, `Baseball`, `Pokemon`, `Soccer`).
  - `notes`: Strict parent/child tracking format `[Parent_Image_ID]-[Child_Card_ID]` (e.g., `8492-01`).
  - `query`: Synthesized search string with negative exclusions for raw cards (`-PSA -BGS -SGC -CGC -CSG -TAG`).
  - `ai_status`: State machine: `CLEARED`, `REVIEW VARIATION`, `NEEDS REVIEW`. Auto-flags if variation or parallel detected.
- **Database Engine (`sports_cards/ecosystem_hub/database.py`)**:
  - SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`).
  - Busy timeout: `PRAGMA busy_timeout = 5000;`.
  - Batch chunking: Max 500 records per transaction with atomic rollback.

### 3.2 Export & Monetization Pipeline
- **Card Ladder CSV Export (`export.py`)**:
  - Produces standard 16-variable CSV matching Card Ladder bulk upload format.
  - Strips internal fields (`ai_status`, `created_at`, `updated_at`, `id`).
  - Splits output into multi-part files if exceeding 500 rows per batch.
- **Sales Copy Generator (`sales_generator.py`)**:
  - Dynamic SEO title formatting: `[Year] [Set] [Player] #[Number] [Variation] [Condition]`.
  - High-converting Facebook Marketplace / eBay description builder with pricing logic, condition notes, and hashtags.

---

## 4. Deep Dive: Media Ingestion & Video Pipeline Architecture

```
[Samsung S26 Ultra (ADB Wi-Fi:5555)] 
        |
        v  (2-Tick Stability Check)
[Ingestion Daemon] ---> [.part download] ---> [SHA-256 Verify] ---> [Promote & Upload] ---> [GCS (gs://raw_media/)]
        |                                                                                         |
        v                                                                                         v
[ingestion_manifest.db]                                                                [PySpark Grading Job]
                                                                                                  |
                                                                                    (Gemini Omni Video Client)
                                                                                                  |
                                                                                 /----------------+----------------\
                                                                                v                                  v
                                                                   [BigQuery (video_grades)]             [DLQ Error Files (.json)]
                                                                                |
                                                                                v
                                                                   [BQML Feedback Loop] ---> [model_parameter_weights]
```

### 4.1 Zero-Compression Android Ingestion (`media_pipeline/ingestion/`)
- **ADB Connection Manager (`adb_connection_manager.py`)**: Manages TCP Wi-Fi ADB connections (`adb connect <ip>:5555`), battery level checks, storage checks, and on-device shell commands.
- **Active Recording Guard (`IncrementalMediaScanner`)**:
  - Implements 2-tick delta check (`is_actively_recording`). If file size grew between ticks or elapsed time < 3.0s, skips pull to prevent reading partial frames.
- **Bit-for-Bit Cryptographic Integrity**:
  - Runs remote `sha256sum <file>` on Android.
  - Pulls file to `.part` extension.
  - Computes streaming local SHA-256 buffer.
  - Compares checksums:
    - Match: Atomically renames `.part` -> `.mp4`, updates SQLite manifest to `HASH_VERIFIED`.
    - Mismatch: Quarantines corrupt file to `quarantine/corrupt_<name>_<time>.part`, marks manifest `QUARANTINED`, raises `CryptographicIntegrityError`.

### 4.2 PySpark Multimodal Video Grading (`media_pipeline/grading/`)
- **5 Viral Parameter Scores (0.0 to 100.0)**:
  1. `HRV` (Hook Retention Velocity / First 3-sec visual dynamism) - Default Weight: `0.25`
  2. `DPAW` (Drop Pacing & Audio Waveform / Bass drop synchronization) - Default Weight: `0.25`
  3. `ADR_SFD` (Audio Dynamic Range & Spectral Flux Density / Crowd cheer & bass clarity) - Default Weight: `0.20`
  4. `CKE_MVE` (Crowd Kinetic Energy & Motion Vector Entropy) - Default Weight: `0.15`
  5. `LTSS` (Lighting & Production Sync / Laser & strobe alignment) - Default Weight: `0.15`
- **EVPI Composite Score & Killswitches**:
  $$\text{EVPI} = \sum (\text{Score}_i \times \text{Weight}_i)$$
  - *Killswitch 1*: If `HRV < 40.0`, maximum EVPI is capped at `49.9` (`LOW_REACH`).
  - *Killswitch 2*: If aspect ratio is horizontal (`16:9`), score is penalized by 50% for Shorts/Reels algorithms.
- **Verdict Classification**:
  - `VIRAL_READY`: $\text{EVPI} \ge 85.0$
  - `HIGH_POTENTIAL`: $70.0 \le \text{EVPI} < 85.0$
  - `MODERATE_REACH`: $50.0 \le \text{EVPI} < 70.0$
  - `LOW_REACH`: $\text{EVPI} < 50.0$

### 4.3 Track 2 EDM Video Engineering (`content_creation/`)
- **FFmpeg Engine (`ffmpeg_processor.py`)**:
  - Automatic hardware acceleration detection (NVIDIA NVENC `h264_nvenc`, `hevc_nvenc` with fallback to CPU `libx264`).
  - 720p proxy generation for low-latency web scrubbers.
  - Smart vertical reframing: `center_crop`, `blur_pad`, `offset_crop`.
- **Audio DSP (`audio_dsp.py`)**:
  - Librosa onset and RMS energy peak detection for 30s drop window extraction.
- **DaVinci Resolve Handoff (`resolve_handoff.py`)**:
  - Injects clips directly into DaVinci Resolve Studio timeline via `DaVinciResolveScript` Python API.
- **YouTube Publisher (`youtube_publisher.py`)**:
  - Uploads to YouTube Shorts via YouTube Data API v3 with automated tags and unlisted-to-public promotion.

---

## 5. System Failure Modes, Port Collisions & DLQ Handling

### 5.1 Port Collisions & Ghost Daemons
1. **Port 8000 Collision**:
   - `sports_cards/ecosystem_hub/boot_hub.py` executes `uvicorn api:app --port 8000`.
   - `content_creation/remote_trigger.py` defaults to `port=8000`.
   - *Failure*: If both are launched, the second process crashes with `OSError: [WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted`.
2. **Port 8501 Collision**:
   - `sports_cards/ecosystem_hub/boot_hub.py` launches Streamlit on `8501`.
   - `ops_hub.py` launches Streamlit without port specification (defaults to `8501`).
   - *Failure*: Streamlit will either silently re-bind to `8502` (breaking hardcoded bookmarks) or collide.
3. **Port 8080 Collision**:
   - `apps/zero_friction_capture_extension` posts to `http://localhost:8080/ingest`.
   - `content_creation/youtube_publisher.py` starts OAuth redirect listener on `8080`.
   - *Failure*: OAuth authorization fails if port 8080 is occupied by a legacy inbox server.
4. **Ghost Process / Lock File Stagnation**:
   - `media_pipeline/ingestion/ingestion_daemon.py` uses `.ingestion_daemon.lock`. If a background daemon is terminated via `SIGKILL` or task cancellation without executing `__exit__`, the lock descriptor is released by Windows kernel, but the file may remain on disk.

### 5.2 Gemini API Failure & DLQ Isolation
1. **Rate Limiting (429 / 503)**:
   - Handled via `RateLimiter` (token bucket QPM) and `tenacity.retry` with exponential backoff and jitter (`wait_random_exponential(min=2, max=60)`).
2. **Dead Letter Queue (DLQ) Implementation**:
   - When a video file has an unsupported codec, corrupted container, or exhausted API retries:
     - `DeadLetterQueue.record_failure()` writes `dlq_<video_id>_<timestamp>.json` containing `video_id`, `gcs_uri`, `error_type`, `error_message`, `traceback`, and timestamp.
     - PySpark partition emits a record with `status: "FAILED_DLQ"`, preventing distributed job failure.
     - Corrupted files are safely quarantined in `staging/quarantine/`.

---

## 6. Test Infrastructure & Quality Assurance Landscape

The workspace features a mature, highly disciplined test suite comprising **74 test files and >1,000 unit, integration, and adversarial test cases**.

### 6.1 Test Suite Breakdown

| Module / Track | Test Files | Total Test Cases | Key Focus Areas |
|---|---|---|---|
| **`sports_cards/ecosystem_hub/tests`** | 21 files | 420+ tests | 21-variable schema constraints, SQLite WAL multi-threaded concurrency, Card Ladder CSV export formatting, checklist scraping, vision extraction, sales generation, circuit breaker, fuzzer & adversarial chaos tests. |
| **`content_creation/tests`** | 28 files | 480+ tests | FFmpeg hardware acceleration, Librosa drop detection, DaVinci Resolve handoff engine, remote trigger REST API, PWA DOM & Service Worker lifecycle, Tasker profiles, YouTube OAuth publishing. |
| **`media_pipeline/tests` & submodules** | 12 files | 180+ tests | Tier 1-4 opaque-box tests, ADB Wi-Fi connection manager, 2-tick active recording guard, SHA-256 bit-for-bit integrity, PySpark grading job, Gemini client retry & DLQ, BigQuery ML feedback loop. |
| **`tests/` (Root)** | 3 files | 27 tests | Workspace stress harness and adversarial cross-module tests. |
| **`.agents/cron/tests`** | 8 files | 140+ tests | AST safety guardrails (0 destructive calls), SQLite telemetry CRUD, 5 anomaly detectors, NumPy/Pandas K-Means clustering ($K=3$), ProTeGi textual gradients, Architecture Red-Team audit. |

### 6.2 Test Execution Command
All tests execute via:
```powershell
python -m pytest <path_to_test_file_or_directory>
```
Supported pytest plugins: `anyio`, `asyncio`, `mock`.

### 6.3 Test Infrastructure Gaps to Address in `unified_ops_hub`
1. **Cross-Module Gateway Tests**: No existing test suite tests the simultaneous mounting of Sports Cards, Media Ingestion, and Health routes under a single unified FastAPI gateway.
2. **Unified Port Collision Prevention Tests**: Need automated tests ensuring all submodules boot on designated virtualized or distinct port bindings.
3. **Unified DLQ Inspector & Retry Tests**: Need automated tests for discovering, inspecting, and retrying failed DLQ items across both media grading and sports card ingestion.

---

## 7. Architectural Blueprint for `unified_ops_hub`

### 7.1 Proposed System Architecture

```
g:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\
├── app.py                      # Unified FastAPI Gateway & Application Entrypoint
├── config.py                   # Central Port, Path & Environment Configuration
├── supervisor.py               # Background Process & Daemon Manager
├── database.py                 # SQLite Schema for Unified Ops State & Telemetry
├── models.py                   # Unified Pydantic Schemas & Data Models
├── routers/
│   ├── __init__.py
│   ├── sports_cards.py         # Mounted Router for Sports Card Ecosystem
│   ├── media.py                # Mounted Router for EDM Remote Trigger & Proxies
│   ├── ingestion.py            # Mounted Router for Android ADB Wi-Fi Ingestion
│   ├── grading.py              # Mounted Router for PySpark Grading & DLQ
│   ├── health.py               # Mounted Router for System Telemetry & Socket Scans
│   └── ops.py                  # Mounted Router for SOPs, Drive Sync & Comms
├── dlq/
│   ├── __init__.py
│   ├── manager.py              # Unified DLQ Aggregator & Quarantine Controller
│   └── schemas.py              # DLQ Incident & Forensic Audit Schemas
├── static/                     # Unified PWA Frontend Assets
│   ├── index.html              # Centralized Control Panel Dashboard
│   ├── app.js                  # Real-time WebSocket / SSE Telemetry Client
│   └── styles.css              # Dark-mode Operations HUD Theme
└── tests/
    ├── __init__.py
    ├── conftest.py             # Shared Test Fixtures & Mock Clients
    ├── test_unified_gateway.py # E2E Router Mounting & Dispatch Tests
    ├── test_supervisor.py      # Daemon Lifecycle & Process Lock Tests
    ├── test_dlq_manager.py     # DLQ Quarantine & Retry Tests
    └── test_port_isolation.py  # Socket & Collision Prevention Tests
```

### 7.2 Core Design Principles for `unified_ops_hub`

1. **Unified Gateway on Single Port (`8000` or `8080`)**:
   - Instead of running 4 separate web servers on colliding ports (8000, 8002, 8501, 8080), `unified_ops_hub/app.py` boots a single, high-performance FastAPI application.
   - Domain routers are mounted under explicit namespaces:
     - `/api/v1/sports/*`
     - `/api/v1/media/*`
     - `/api/v1/ingestion/*`
     - `/api/v1/grading/*`
     - `/api/v1/health/*`
     - `/api/v1/ops/*`
2. **Centralized Daemon Supervisor (`supervisor.py`)**:
   - Supervises background threads and sub-processes (ADB Ingestion Daemon, Drive Sync Daemon, Watchdog, Cron Scanner).
   - Provides REST endpoints to start, stop, restart, and monitor health status for each daemon.
   - Cleans up stale file locks (`.lock`) on startup.
3. **Unified DLQ & Incident Center (`dlq/manager.py`)**:
   - Centralizes error recording across all tracks:
     - Media grading failures (`FAILED_DLQ`)
     - Corrupt media downloads (`QUARANTINED`)
     - Chrome extension extraction syntax errors (`NEEDS REVIEW`)
   - Exposes `GET /api/v1/dlq/incidents` and `POST /api/v1/dlq/retry/{incident_id}`.
4. **Real-Time Operational Dashboard**:
   - Replaces fragmented Streamlit pages with a sleek, unified web interface (FastAPI static mount or Streamlit hub) displaying:
     - ADB device connection status and live pull speed.
     - Pending video proxy review and DaVinci Resolve handoff button.
     - Sports card staging counter and 1-click Card Ladder export.
     - Active socket listeners and system health metrics.

---

## 8. Actionable Implementation Roadmap

| Milestone | Scope | Deliverables | Verification Method |
|---|---|---|---|
| **Phase 1: Config, Models & Port Virtualization** | Create `config.py`, `models.py`, port registry | Non-overlapping port configuration, unified schemas | Unit tests verifying configuration loading and schema validation |
| **Phase 2: Unified Gateway & Router Integration** | Build `app.py`, `routers/` | Mount Sports Cards, Media, Ingestion, Grading, Health routers | FastAPI `TestClient` route dispatch tests |
| **Phase 3: Daemon Supervisor & Process Management** | Build `supervisor.py` | Subprocess lifecycle manager, socket probing, lock cleanup | Process start/stop/status tests, WinError 10048 prevention tests |
| **Phase 4: Unified DLQ & Quarantine Manager** | Build `dlq/` package | DLQ aggregator, forensic JSON logger, retry dispatcher | Mock failure injection and retry verification tests |
| **Phase 5: Unified Control Panel UI** | Build frontend in `static/` or Streamlit hub | Real-time status cards, staging table, DLQ table, SOP viewer | End-to-end browser / endpoint verification |
| **Phase 6: Opaque-Box E2E Testing & Hardening** | Build `tests/` suite | 4-tier E2E tests + adversarial stress harness | `python -m pytest unified_ops_hub/tests` 100% pass |

---
*Report successfully generated and verified by Teamwork Explorer.*
