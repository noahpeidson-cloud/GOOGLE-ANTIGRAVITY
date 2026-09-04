# Comprehensive Survey Report: Requirement R1 (Modern PWA Web Dashboard)

- **Date**: 2026-08-22
- **Track**: Track 2 (`/content_creation`)
- **Investigator**: Explorer Agent (`explorer_survey_pwa`)
- **Status**: Completed Survey & Gap Analysis
- **Authoritative Specification**: `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md`

---

## 1. Executive Summary

Requirement **R1 (Modern PWA Web Dashboard)** mandates a sleek, dark-mode Progressive Web App (PWA) served by the FastAPI server that:
1. Adheres to modern web standards (View Transitions, Glassmorphism, mobile responsiveness).
2. Displays 720p proxies with a timeline scrubber allowing the user to manually adjust AI-detected trim points.
3. Captures metadata (Festival, Artist) before triggering the pipeline.
4. Meets Lighthouse PWA compliance and provides supporting endpoints.

### High-Level Verdict: **Partially Satisfied (~35% Complete)**

| Dimension | Current Status | Completeness |
|---|---|---|
| **FastAPI PWA Server & Base Routing** | Operational (`GET /`, `GET /manifest.json`, `GET /health`, `POST /trigger-pipeline`) | 90% |
| **Dark-Mode OLED Theme & Glassmorphism** | Implemented (`#000000` background, neon accents, `backdrop-filter: blur(12px)`) | 90% |
| **Metadata Capture (Festival, Artist)** | Fully implemented (`#festival-input`, `#artist-input`, backend validation, DB persistence) | 100% |
| **View Transitions API** | **Missing** (Zero `document.startViewTransition()` or CSS view transitions) | 0% |
| **720p Proxy Video Player** | **Missing** (No `<video>` tag or proxy streaming support in UI) | 0% |
| **Interactive Timeline Scrubber (AI Trim)** | **Missing** (No multi-handle range control, no visual drop window) | 0% |
| **"Approve & Render" / DaVinci Trigger** | **Missing** (Only has blind "TRIGGER EDM PIPELINE" button) | 0% |
| **Lighthouse PWA Compliance** | Partial (Has manifest & meta tags; lacks Service Worker `sw.js` & icon links) | 40% |
| **Proxy & Review API Endpoints** | **Missing** (`GET /proxies`, `GET /proxies/{id}/video`, `POST /analyze-drop`, `POST /approve-render`) | 0% |

---

## 2. Evidence-Based Investigation by Criterion

### 2.1 Criterion 1: Sleek, Dark-Mode PWA Served by FastAPI

#### Observations:
- **FastAPI Mount & Routing (`remote_trigger.py:601-639`)**:
  - `create_app()` mounts `/static` via `StaticFiles(directory=str(static_dir))`.
  - `GET /` serves `static/index.html` with fallback to `workspace_root / "index.html"`.
  - `GET /manifest.json` serves `static/manifest.json` with media type `application/manifest+json`.
- **Styling (`static/index.html:14-39`)**:
  - Sets root CSS variables: `--bg-oled-black: #000000`, `--bg-surface-dark: #08080c`, `--bg-surface-elevated: #121218`, `--bg-card-glass: rgba(18, 18, 24, 0.85)`.
  - Neon accent palette: `--neon-cyan: #00ffcc`, `--neon-pink: #ff007f`, `--neon-purple: #7928ca`, `--neon-green: #00ff88`, `--neon-amber: #ffaa00`.
  - SafeArea insets: `env(safe-area-inset-top, 20px)`, `env(safe-area-inset-bottom, 20px)`.
- **Manifest (`static/manifest.json:1-24`)**:
  - Configures `display: "standalone"`, `orientation: "portrait"`, `background_color: "#000000"`, `theme_color: "#000000"`.
  - Declares icons: `192x192` (`/static/icon-192.png`) and `512x512` (`/static/icon-512.png`).

#### Verified Test Baseline:
- `python -m unittest tests/test_remote_trigger.py tests/test_adversarial_pwa_dom.py` executed 72 tests with 100% pass rate (`OK`).

#### Deficiencies / Gaps:
- **No Service Worker**: `static/index.html` does not register a service worker (`navigator.serviceWorker.register('/sw.js')`). Lighthouse requires an active service worker with a fetch handler to pass the PWA Installable audit.
- **Missing Head Icons**: `<head>` lacks `<link rel="icon" type="image/png" href="/static/icon-192.png">` and `<link rel="apple-touch-icon" href="/static/icon-192.png">`.

---

### 2.2 Criterion 2: Modern Web Standards (View Transitions, Glassmorphism, Mobile Responsiveness)

#### Observations:
- **Glassmorphism (`static/index.html:144-155, 316-327, 432-447`)**:
  - Implemented on `.metadata-card`, `.status-card`, and `.toast-card`.
  - Uses `background: var(--bg-card-glass)`, `backdrop-filter: blur(12px)`, `-webkit-backdrop-filter: blur(12px)`, `border: 1px solid var(--border-glass)`, and `box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5)`.
- **Mobile Touch Responsiveness (`static/index.html:41-63, 178-191`)**:
  - `touch-action: manipulation` eliminates 300ms tap delay.
  - `-webkit-tap-highlight-color: transparent` prevents intrusive tap overlays.
  - Inputs specify `font-size: 16px` to prevent iOS viewport auto-zoom.
  - Dual-pulse haptic vibration (`navigator.vibrate([100, 100, 100])`) provides tactile feedback on HTTP 202, while warning pattern `[500, 200, 500]` handles HTTP 409 and network errors.

#### Deficiencies / Gaps:
- **Zero View Transitions API Implementation**:
  - Neither `document.startViewTransition()` nor `@view-transition` CSS rules exist anywhere in `static/index.html`.
  - Modern Web Guidance standard (`modern-web-guidance retrieve "same-document-transitions"`) specifies that SPA view changes (e.g. switching between Ingest / Proxy Scrubber / Export Telemetry) must be wrapped in `document.startViewTransition()` with progressive enhancement fallbacks and `@media (prefers-reduced-motion: reduce)`.

---

### 2.3 Criterion 3: Display of 720p Proxies with Timeline Scrubber & AI Trim Points

#### Observations:
- **Existing Backend Capabilities**:
  - `ffmpeg_processor.py` (lines 600-712) already implements `FFmpegMasterProcessor.generate_proxy_video()`, `extract_wav_audio()`, and `generate_proxy_and_wav()`.
  - `ffmpeg_processor.py` (lines 713-790) implements `trim_proxy_video()` with fast stream-copy slicing.
  - `audio_dsp.py` (lines 66-70) implements `AudioDropDetector` and `detect_optimal_drop()`, computing optimal RMS energy windows.
  - `config.py` (lines 243-251) standardizes proxy specs: `PROXY_VIDEO_HEIGHT = 720`, `PROXY_VIDEO_BITRATE_KBPS = 2500`, `PROXY_AUDIO_SAMPLE_RATE = 22050`, `PROXY_AUDIO_CODEC = "pcm_s16le"`.

#### Deficiencies / Gaps:
1. **Frontend (`static/index.html`)**:
   - **No `<video>` Player Element**: The UI cannot render 720p `.mp4` proxies.
   - **No Interactive Timeline Scrubber**: Lacks dual-range sliders for `start_time` and `duration`/`end_time`.
   - **No Visual AI Drop Highlight**: Lacks a visual track overlay displaying where the AI-detected 30s RMS drop window is located on the full clip.
   - **No Manual Adjustment Handles**: User cannot drag the start or end handles to fine-tune the drop boundaries.
   - **No "Approve & Render" Button**: UI only features a single massive "TRIGGER EDM PIPELINE" button that assumes immediate end-to-end processing rather than human-in-the-loop review.
2. **Backend (`remote_trigger.py`)**:
   - **No Proxy Catalog Endpoint**: No `GET /proxies` or `GET /assets` to list available raw takes, proxy files, and durations.
   - **No Video Streaming Endpoint**: No endpoint to stream 720p proxy files with HTTP 206 Partial Content (Range requests) for seeking.
   - **No Drop Detection Preflight Endpoint**: No `POST /analyze-drop` endpoint to run RMS detection on a specific clip and return coordinates prior to transcoding.
   - **No DaVinci Resolve Handoff Endpoint**: No `POST /approve-render` or `POST /resolve-handoff` endpoint to pass approved timestamps to DaVinci Resolve script (R3).

---

### 2.4 Criterion 4: Capture of Metadata (Festival, Artist) Before Pipeline Trigger

#### Observations:
- **Frontend (`static/index.html:518-550, 680-698`)**:
  - Input elements `<input id="festival-input" name="festival">` and `<input id="artist-input" name="artist">`.
  - JavaScript client extracts values with fallback defaults (`"Concert"`, `"Artist"`) and submits them in `POST /trigger-pipeline`.
- **Backend Schema (`remote_trigger.py:74-114`)**:
  - `PipelineTriggerRequest` validates `festival`, `event`, `artist`, with `@property resolved_event` and `@property resolved_artist`.
- **Orchestration Execution (`remote_trigger.py:225-290`, `orchestrator.py:275-307`)**:
  - `build_orchestrator_command()` converts metadata into `--event <Festival>` and `--artist <Artist>` CLI arguments.
  - `orchestrator.py` uses metadata for directory partitioning, canonical naming (`AssetIngestionRouter`), and SQLite lifecycle tracking (`MediaManifestDB.upsert_asset()`).

#### Verdict: **100% Satisfied and Tested**.

---

### 2.5 Criterion 5: Lighthouse Compliance & API Endpoints

#### Observations:
- Current endpoints in `remote_trigger.py`:
  - `GET /`: Serves PWA HTML shell (HTTP 200).
  - `GET /manifest.json`: Serves Web App Manifest (HTTP 200).
  - `GET /health`: Returns system readiness (ADB, FFmpeg, FFprobe, Disk space) (HTTP 200/503).
  - `POST /trigger-pipeline`: Async dispatch with mutex concurrency lock (HTTP 202 / 409).
  - `GET /status` & `GET /status/{job_id}`: Returns daemon & job telemetry.
  - `GET /logs`: Ring-buffered log stream.
  - `POST /cancel`: Active job cancellation (HTTP 200/400).

#### Deficiencies / Gaps:
- **Missing Service Worker**: Must create and serve `static/sw.js` with offline caching logic.
- **Missing Video Streaming Endpoint**: Must support HTTP 206 range requests for 720p proxy video scrubbing.
- **Missing Proxy Review Endpoints**: Must provide API routes for proxy file listings and drop point approvals.

---

## 3. Recommended Architecture & Implementation Blueprint

To fully satisfy Requirement R1 while seamlessly integrating with R2 (FFmpeg Proxy Engine) and R3 (DaVinci Resolve Python Handoff), the following design is recommended:

```
+-----------------------------------------------------------------------------------+
|                           PWA Master Web Dashboard                                |
|                                                                                   |
|  [Header: Brand Neon Logo + ADB / FFmpeg / Resolve Health Badges]                 |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | STEP 1: Ingest & Metadata Form (Glassmorphism Card)                         |  |
|  | - Festival / Event: [ EDC Las Vegas 2026 ]                                  |  |
|  | - Artist / DJ:       [ Subtronics        ]                                  |  |
|  | - Pull Source:       (o) Samsung S26 ADB   ( ) Local Inbox File             |  |
|  | [ Button: INGEST & GENERATE PROXIES (POST /trigger-ingest) ]                |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | STEP 2: 720p Proxy Player & Interactive Timeline Scrubber                   |  |
|  |                                                                             |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |  | [ Video Player Canvas (720p MP4 Proxy Stream) - 9:16 or 16:9 ]         |  |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |                                                                             |  |
|  |  Timeline Scrubber:                                                         |  |
|  |  00:00 [====|==================[==== AI DROP (30s) ====]========|========] 02:30 |
|  |             ^ Start Trim (00:45)                         ^ End Trim (01:15)  |  |
|  |                                                                             |  |
|  |  Adjustments: Start Time: [ 45.0s ]   Duration: [ 30.0s ]   Auto-Drop: [v]   |  |
|  |                                                                             |  |
|  |  [ Button: APPROVE & SEND TO DAVINCI RESOLVE (POST /approve-render) ]       |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | STEP 3: Live Telemetry & DaVinci Pipeline Status HUD                        |  |
|  | - Active Job: job_20260822_111304 | State: RESOLVE_TIMELINE_CREATED        |  |
|  | - Raw 4K Preserved: 01_RAW/EDCLV2026_Subtronics_RAW.mp4                      |  |
|  | - Target Timeline: Subtronics_Drop_01 (Slices: 45.00s -> 75.00s)           |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### 3.1 Frontend Components to Add (`static/index.html` & `static/sw.js`)

1. **Proxy Video Player Component**:
   - Semantic `<video id="proxy-video-player" playsinline preload="metadata">`.
   - Custom playback controls (Play/Pause, Frame Step Back/Forward, Current Time / Duration counter).
2. **Dual-Handle Timeline Scrubber Component**:
   - Visual container with:
     - Background clip timeline track (0 to clip duration).
     - Colored AI Drop Window highlight bar (calculated from RMS energy peak).
     - Interactive drag handles: Start Handle (`#trim-handle-start`) and End Handle (`#trim-handle-end`).
     - Real-time time synchronization between video playback playhead and timeline position.
     - Accessible ARIA attributes (`role="slider"`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax`).
3. **View Transitions Integration**:
   - Implement navigation transitions with `document.startViewTransition()`:
     ```javascript
     function switchView(targetViewId) {
       if (!document.startViewTransition) {
         updateViewDOM(targetViewId);
         return;
       }
       document.startViewTransition(() => updateViewDOM(targetViewId));
     }
     ```
   - Add `@media (prefers-reduced-motion: reduce)` rules for accessibility.
4. **Service Worker (`static/sw.js`)**:
   - Standard Cache-First strategy for static assets (`index.html`, `manifest.json`, `icon-*.png`).
   - Network-First strategy for API endpoints (`/status`, `/health`, `/proxies`).
   - Register in `static/index.html` on `window.load`.

### 3.2 Backend Endpoints to Add (`remote_trigger.py`)

1. **`GET /proxies`**:
   - Returns JSON list of available proxy assets from `02_IN_PROGRESS/` and `01_RAW/` with metadata (`project_id`, `filename`, `duration`, `proxy_url`, `ai_drop_window`).
2. **`GET /proxies/{project_id}/video`**:
   - Returns `FileResponse` with `Accept-Ranges: bytes` supporting HTTP 206 Partial Content for smooth browser video seeking.
3. **`POST /analyze-drop`**:
   - Accepts `{ project_id: "...", input_file: "..." }`.
   - Executes `AudioDropDetector.detect_optimal_drop()` on the extracted `.wav` and returns `{ start_time_sec, duration_sec, end_time_sec, max_rms_energy }`.
4. **`POST /approve-render` (or `/resolve-handoff`)**:
   - Accepts `{ project_id: "...", start_time: 45.0, duration: 30.0, festival: "EDC", artist: "Subtronics", timeline_name: "..." }`.
   - Spawns the DaVinci Resolve handoff script (Requirement R3) using the untouched 4K raw footage from `01_RAW/`.

---

## 4. Summary & Verification Method

- **Full Verification Suite**:
  Run existing and future PWA test suites:
  ```powershell
  python -m unittest tests/test_remote_trigger.py tests/test_adversarial_pwa_dom.py
  ```
- **Lighthouse Verification**:
  Once the Service Worker and icon tags are installed, audit via Chrome DevTools or Lighthouse CLI.
