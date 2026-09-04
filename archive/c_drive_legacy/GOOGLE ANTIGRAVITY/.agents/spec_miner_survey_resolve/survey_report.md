# DaVinci Resolve Python Handoff & Acceptance Criteria Specification Report
**Project Track**: Track 2 — Content Creation & Media Engineering Pipeline (`/content_creation`)  
**Requirement Focus**: Requirement R3 (DaVinci Resolve Python Handoff) & Acceptance Criteria Verification  
**Author**: Specification Miner Agent  
**Date**: 2026-08-22  
**Status**: Comprehensive Specification & Gap Analysis Finalized  

---

## 1. Executive Summary & Scope

This specification document provides the authoritative blueprint and gap analysis for **Requirement R3 (DaVinci Resolve Python Handoff)** and its associated **Acceptance Criteria** for the **Master Dashboard EDM Content Creation Pipeline**.

The Master Dashboard is designed as an autonomous, zero-touch media engineering pipeline that bridges mobile hardware capture (Samsung Galaxy S26 Ultra via ADB) with professional post-production (DaVinci Resolve Studio) and multi-platform distribution (YouTube Shorts, TikTok). When mobile footage is ingested and proxies are generated, the user interacts with a sleek, dark-mode PWA dashboard to review 720p proxies, adjust AI-detected trim points on a timeline scrubber, enter festival/artist metadata, and click **"Approve & Render"**. This action triggers an automated Python script leveraging the **DaVinci Resolve Studio Python API** (`DaVinciResolveScript`) to instantiate Resolve, configure a 9:16 vertical 60fps timeline, import pristine 4K raw footage from the `01_RAW` vault, and place precisely sliced media clips on the edit track.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | DaVinci API | Environment & Module Discovery | Dynamically discovers Blackmagic `DaVinciResolveScript` / `fusionscript` DLL and module paths on Windows. | Environment vars (`RESOLVE_SCRIPT_API`, `RESOLVE_SCRIPT_LIB`), default `%PROGRAMDATA%` and `%PROGRAMFILES%` paths | Loaded `DaVinciResolveScript` module object | Raises `ResolveModuleNotFoundError` with actionable configuration guidance | Blackmagic Design Developer Documentation & Windows Registry conventions |
| 2 | DaVinci API | Resolve Application Instantiation | Obtains running DaVinci Resolve Studio application instance via `dvr_script.scriptapp("Resolve")`. | Application identifier (`"Resolve"`) | Live `Resolve` object handle | Raises `ResolveNotRunningError` if Resolve Studio is closed or scripting is disabled | Blackmagic Resolve Scripting API Specification |
| 3 | DaVinci API | Project & Settings Management | Creates or loads a dedicated project and applies 9:16 vertical 1080x1920 (or 4K 2160x3840) 60fps project settings. | `project_name`, resolution dimensions (`1080x1920`), target framerate (`60.0`) | Active `Project` instance | Returns error if ProjectManager cannot create or switch project | Resolve API `ProjectManager` / `Project` interface |
| 4 | DaVinci API | Media Pool 4K Raw Ingestion | Locates untouched 4K raw master in `01_RAW/[Festival]/[Artist]/` vault and imports it into the Media Pool root bin. | List of absolute file paths `[str(raw_4k_path)]` | List of `MediaPoolItem` objects | Raises `MediaImportError` if file is missing, corrupt, or rejected by MediaStorage | Resolve API `MediaStorage.AddItemListToMediaPool` / `MediaPool.ImportMedia` |
| 5 | DaVinci API | Timeline Construction & Precise Slicing | Creates a vertical timeline and appends subclips sliced at exact millisecond/frame in/out timestamps. | `timeline_name`, `clip_item`, `start_time_sec`, `end_time_sec` / `duration_sec`, `fps` | Created `Timeline` object with populated video/audio tracks | Raises `TimelineCreationError` if frame bounds exceed clip length or timeline creation fails | Resolve API `MediaPool.CreateEmptyTimeline` & `AppendToTimeline` |
| 6 | PWA / Backend | Approve & Render REST Endpoint | FastAPI endpoint (`POST /approve-render` or `POST /api/resolve/handoff`) accepting clip ID, metadata, and trim timestamps. | JSON payload: `{project_id, raw_clip_path, festival, artist, track, start_time, duration, end_time, fps}` | HTTP 202/200 JSON `{status: "accepted", job_id, project_name, timeline_name}` | HTTP 400 (validation error), HTTP 404 (clip missing), HTTP 409 (pipeline busy), HTTP 500 (Resolve failure) | `ORIGINAL_REQUEST.md` R3 & `edm-master-mind-pipeline` SKILL |
| 7 | PWA / Backend | Pending Takes / Review API | Endpoint (`GET /api/clips/pending`) listing ingested takes awaiting user review with proxy URLs and AI drop timestamps. | None or filter query parameters | List of pending clip records with metadata, 720p proxy path, WAV path, detected drop window | HTTP 500 on database / filesystem read failure | Master Dashboard PWA UX Requirements |
| 8 | PWA / Frontend | 720p Proxy Scrubber Player | Web video player with interactive dual-handle timeline scrubber, AI drop marker overlay, and timecode display. | 720p MP4 stream, duration, detected drop bounds | User-adjusted `start_time` and `duration` / `end_time` | Fallback to default start=0.0, duration=30.0 if user does not adjust | `ORIGINAL_REQUEST.md` R1 & PWA UI Guidelines |
| 9 | PWA / Frontend | Approve & Render CTA Flow | Glassmorphic CTA button triggering handoff request with smooth View Transition and haptic vibration feedback. | Button tap / click event | Async fetch to `/approve-render`, loading spinner, toast notification | Displays error toast and vibrating alert on network / server failure | Modern Web Guidance & `index.html` PWA architecture |
| 10 | Testing Harness | DaVinci Mock / Headless Test Harness | Complete mock object hierarchy allowing full unit and integration testing of `resolve_handoff.py` in headless CI/CD without GPU or Resolve Studio. | Synthetic file paths and timestamp configurations | Mock invocation call logs and assertion reports | Asserts exact mathematical frame conversion and method call sequences | Teamwork Benchmark Integrity & Verification Standards |
| 11 | Testing Harness | Live Resolve Studio Prober | Integration test validating execution against a live, running DaVinci Resolve Studio instance on Windows. | Live Resolve Studio process | Verifiable timeline created in Resolve UI with active clips | Skips gracefully or reports actionable error if Resolve is not running | Acceptance Criteria Programmatic Verification |
| 12 | Testing Harness | Automated Lighthouse PWA Audit | Automated headless audit validating PWA performance, accessibility, best practices, SEO, and modern web standards. | PWA URL (`http://localhost:8000/`) | Lighthouse JSON audit score (all categories >= 90) | Fails build if any category falls below benchmark threshold | Acceptance Criteria Programmatic Verification |

---

## 3. Edge Cases & Boundary Conditions

| # | Feature | Input Condition | Observed / Documented Behavior |
|---|---------|-----------------|--------------------------------|
| 1 | Resolve Script Discovery | Windows environment where `RESOLVE_SCRIPT_API` and `PYTHONPATH` are unset. | Module fallback searches `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules` and `C:\Program Files\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules` and dynamically appends to `sys.path`. |
| 2 | Resolve Script Discovery | Non-Studio (Free) DaVinci Resolve or Resolve not installed. | External Python scripting is disabled in Free Resolve; script detects `dvr_script.scriptapp("Resolve")` returning `None` and raises explicit error explaining DaVinci Resolve Studio requirement and "External scripting using" setting. |
| 3 | Project Creation | Project with identical name already exists in Resolve Project Manager. | Script checks `project_manager.LoadProject(project_name)`. If existing, loads project or creates versioned project name (`[ProjectName]_V2`) or clears existing timeline to prevent collision. |
| 4 | Clip Ingestion | Raw 4K file in `01_RAW` has variable frame rate (VFR) or unusual framerate (e.g. 59.94 vs 60.00 fps). | Stream probe extracts exact fractional framerate (`59.940` or `60.000`), configures project timeline to match, and calculates frame indices as `int(round(time_sec * fps))` avoiding drift. |
| 5 | Clip Slicing | `start_time` + `duration` exceeds total video file duration. | Script clamps `end_time = min(start_time + duration, total_file_duration)` and calculates `end_frame = int(round(end_time * fps)) - 1`. |
| 6 | Clip Slicing | User sets sub-second slice (e.g. start=12.450s, end=42.450s). | Subclip dictionary computes exact integer frames: `startFrame = int(round(12.450 * 60)) = 747`, `endFrame = int(round(42.450 * 60)) = 2547`. |
| 7 | Timeline Resolution | Source clip is 16:9 landscape 4K (3840x2160) or 9:16 portrait (2160x3840). | Project timeline is configured for 9:16 portrait (1080x1920 or 2160x3840). Resolve's "Scale full frame with crop" or Smart Reframe is configured on timeline/clip items. |
| 8 | Media Storage Import | Windows path contains spaces or backslashes (`G:\My Drive\GOOGLE ANTIGRAVITY\...`). | Paths are normalized using `os.path.abspath` / `Path.resolve()` with proper string formatting before passing to `AddItemListToMediaPool`. |
| 9 | PWA Scrubber | Network disconnects while user is scrubbing proxy video. | HTML5 video element buffers local 720p proxy; offline indicator shows toast; UI prevents "Approve & Render" until connection restores. |
| 10 | Approve & Render Trigger | Two simultaneous "Approve & Render" requests dispatched in parallel. | Backend single-job mutex locks execution, returning HTTP 409 Conflict with active job telemetry for the second request. |

---

## 4. Current Codebase Audit & Gap Analysis

### 4.1. Audit of Existing Files in `content_creation/`

| Existing Module | Current Functionality | R3 & Acceptance Criteria Gap |
|-----------------|-----------------------|------------------------------|
| `remote_trigger.py` | FastAPI daemon providing `/trigger-pipeline`, `/status`, `/health`, `/logs`, `/cancel`. | ❌ Missing `/approve-render` or `/api/resolve/handoff` endpoint.<br>❌ Missing `/api/clips/pending` review endpoint.<br>❌ Missing proxy video/audio static route. |
| `static/index.html` | PWA trigger interface with giant button, metadata inputs (Festival, Artist), and status card. | ❌ Missing HTML5 video player for 720p proxy preview.<br>❌ Missing interactive timeline scrubber with start/end trim handles.<br>❌ Missing AI drop point visualization overlay.<br>❌ Missing "Approve & Render" CTA button wired to Resolve handoff. |
| `ffmpeg_processor.py` | Transcoder, HDR tone-mapping, 2-pass loudnorm, `generate_proxy_and_wav()`, `trim_proxy_video()`. | ⚠️ Has proxy generation primitives, but lacks direct binding to Resolve handoff pipeline. |
| `ingest_assets.py` | Ingestion router, canonical naming, 4-tier directory health, `store_raw_asset()` into `01_RAW`. | ✅ Correctly deposits pristine 4K raw masters into `01_RAW/[Festival]/[Artist]/`. |
| `orchestrator.py` | Master CLI facade (`ingest`, `process`, `inspect`, `generate-seo`, `audit-safezone`, `verify`, `adb-ingest`, `publish`, `pipeline`). | ❌ Missing `resolve-handoff` subcommand and programmatic workflow dispatch. |
| `resolve_handoff.py` | **DOES NOT EXIST** | ❌ Entire DaVinci Resolve Studio Python API module is absent from repository. |
| `tests/` | Unit tests for config, ffmpeg, metadata, remote trigger, samsung ingest, audio DSP, youtube publisher. | ❌ Missing `test_resolve_handoff_mock.py` (headless CI/CD mock test).<br>❌ Missing `test_resolve_handoff_live.py` (live Studio test).<br>❌ Missing automated Lighthouse audit script / test. |

---

## 5. Detailed Technical Specifications

### 5.1. DaVinci Resolve Python Handoff Module (`resolve_handoff.py`)

#### 5.1.1. Architecture & Windows Scripting Discovery Protocol
DaVinci Resolve Studio exposes its scripting API via Python 3 through `fusionscript.dll` and `DaVinciResolveScript.py`. On Windows 10/11, these modules are typically located in:
- `%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules`
- `%PROGRAMFILES%\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules`

The module must implement a resilient discovery helper:
```python
def get_resolve_instance() -> Any:
    """
    Discovers DaVinciResolveScript module and connects to active DaVinci Resolve Studio instance.
    Raises ResolveModuleNotFoundError or ResolveNotRunningError if unavailable.
    """
    try:
        import DaVinciResolveScript as dvr_script
    except ImportError:
        # Search Windows standard paths
        search_paths = [
            os.path.expandvars(r"%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules"),
            os.path.expandvars(r"%PROGRAMFILES%\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules"),
            r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules",
        ]
        for p in search_paths:
            if os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)
        try:
            import DaVinciResolveScript as dvr_script
        except ImportError as err:
            raise ResolveModuleNotFoundError(
                "DaVinciResolveScript module could not be loaded. Ensure DaVinci Resolve Studio is installed "
                "and RESOLVE_SCRIPT_API is configured."
            ) from err

    resolve = dvr_script.scriptapp("Resolve")
    if resolve is None:
        raise ResolveNotRunningError(
            "DaVinci Resolve Studio is not running or external scripting is disabled. "
            "Please launch DaVinci Resolve Studio and verify 'Preferences -> System -> General -> External scripting using -> Local' is enabled."
        )
    return resolve
```

#### 5.1.2. Resolve Studio Handoff Class Model
```python
@dataclass
class ResolveHandoffConfig:
    """Configuration parameters for DaVinci Resolve timeline construction."""
    raw_clip_path: Path
    project_name: str
    timeline_name: str
    start_time_sec: float = 0.0
    duration_sec: Optional[float] = 30.0
    end_time_sec: Optional[float] = None
    timeline_width: int = 1080
    timeline_height: int = 1920
    timeline_fps: float = 60.0
    festival_name: str = "Concert"
    artist_name: str = "Artist"
    track_name: str = "ID"
    auto_save: bool = True
    dry_run: bool = False

@dataclass
class ResolveHandoffResult:
    """Telemetry report produced upon timeline construction."""
    success: bool
    project_name: str
    timeline_name: str
    raw_clip_path: str
    start_frame: int
    end_frame: int
    duration_frames: int
    duration_seconds: float
    timeline_resolution: str
    framerate: float
    error_message: Optional[str] = None
```

#### 5.1.3. Step-by-Step API Execution Flow
1. **Initialize Application**: Obtain `resolve = get_resolve_instance()`.
2. **Project Manager**: Access `pm = resolve.GetProjectManager()`.
3. **Create or Load Project**:
   - `project = pm.LoadProject(config.project_name)`
   - If not found: `project = pm.CreateProject(config.project_name)`
4. **Configure Project Settings**:
   - `project.SetSetting("timelineResolutionWidth", str(config.timeline_width))`
   - `project.SetSetting("timelineResolutionHeight", str(config.timeline_height))`
   - `project.SetSetting("timelineFrameRate", str(config.timeline_fps))`
   - `project.SetSetting("useCustomTimelineSettings", "1")`
5. **Access Media Pool & Storage**:
   - `media_pool = project.GetMediaPool()`
   - `media_storage = resolve.GetMediaStorage()`
6. **Import Raw 4K Clip**:
   - `raw_path_str = str(config.raw_clip_path.resolve())`
   - `imported_items = media_storage.AddItemListToMediaPool([raw_path_str])` or `media_pool.ImportMedia([raw_path_str])`
   - Obtain `clip_item = imported_items[0]`
7. **Calculate Frame Indices**:
   - `fps = config.timeline_fps`
   - `start_frame = int(round(config.start_time_sec * fps))`
   - `dur_sec = config.duration_sec if config.duration_sec else ((config.end_time_sec - config.start_time_sec) if config.end_time_sec else 30.0)`
   - `end_frame = start_frame + int(round(dur_sec * fps))`
8. **Create Timeline & Insert Subclip**:
   - `timeline = media_pool.CreateEmptyTimeline(config.timeline_name)`
   - Subclip structure:
     ```python
     clip_info = {
         "mediaPoolItem": clip_item,
         "startFrame": start_frame,
         "endFrame": end_frame,
         "recordFrame": 0
     }
     media_pool.AppendToTimeline([clip_info])
     ```
9. **Set Current Timeline & Save**:
   - `project.SetCurrentTimeline(timeline)`
   - If `config.auto_save`: `pm.SaveProject()`
10. **Return Result**: Return `ResolveHandoffResult` with exact metadata.

---

### 5.2. FastAPI Backend & PWA Endpoint Expansion

The FastAPI application in `remote_trigger.py` must be augmented with dedicated endpoints for the Review & Resolve workflow:

#### Endpoint 1: `GET /api/clips/pending`
- **Purpose**: Lists takes in `01_RAW_INBOX` or `01_RAW` with generated 720p proxies and detected drop points ready for browser review.
- **Response Schema**:
  ```json
  [
    {
      "clip_id": "20260822_Edclasvegas_Subfocus_V1",
      "canonical_filename": "20260822_Edclasvegas_Subfocus_Desire_V1_4k.mp4",
      "raw_path": "01_RAW/Edclasvegas/Subfocus/20260822_Edclasvegas_Subfocus_Desire_V1_4k.mp4",
      "proxy_url": "/api/proxy/20260822_Edclasvegas_Subfocus_Desire_V1_720p.mp4",
      "wav_url": "/api/proxy/20260822_Edclasvegas_Subfocus_Desire_V1.wav",
      "duration_seconds": 124.5,
      "detected_drop_start": 34.2,
      "detected_drop_duration": 30.0,
      "festival": "EDC Las Vegas",
      "artist": "Sub Focus",
      "track": "Desire"
    }
  ]
  ```

#### Endpoint 2: `POST /approve-render` (or `/api/resolve/handoff`)
- **Purpose**: Accepts user-approved trim bounds and metadata, asynchronously launching `resolve_handoff.py`.
- **Request Schema**:
  ```json
  {
    "clip_id": "20260822_Edclasvegas_Subfocus_V1",
    "raw_clip_path": "01_RAW/Edclasvegas/Subfocus/20260822_Edclasvegas_Subfocus_Desire_V1_4k.mp4",
    "festival": "EDC Las Vegas",
    "artist": "Sub Focus",
    "track": "Desire",
    "start_time": 34.2,
    "duration": 30.0,
    "end_time": 64.2,
    "brand": "laser_baptism",
    "tier": "pillar_a_stadium_arena"
  }
  ```
- **Response**: HTTP 202 Accepted with `{status: "accepted", job_id: "resolve_...", message: "DaVinci Resolve handoff launched"}`.

---

### 5.3. PWA Web UI (`static/index.html`) Component Specification

To fulfill Requirement R1 and R3, the PWA Web UI requires:
1. **Modern View Transitions & Glassmorphism Design**:
   - `document.startViewTransition()` for smooth panel animations.
   - OLED black background (`#000000`) with glass cards (`backdrop-filter: blur(16px)`), neon cyan (`#00ffcc`) and pink (`#ff007f`) accents.
2. **720p Proxy Video Player**:
   - `<video id="proxy-player" playsinline muted controls="false">` displaying 720p lightweight preview.
3. **Interactive Timeline Scrubber & Trim Sliders**:
   - Dual-handle range scrubber allowing drag-adjustment of `start_time` (0.0 to clip duration) and `duration` (15.0 to 59.0s).
   - Visual waveform/drop marker highlighting the AI-detected RMS drop window.
   - Timecode readout displays: `IN: 00:34.20 | OUT: 01:04.20 | DUR: 30.00s`.
4. **Metadata Inputs**:
   - Inputs for `FESTIVAL`, `ARTIST`, `TRACK`, `GENRE`.
5. **Approve & Render Button**:
   - High-contrast glowing CTA button: `<button id="btn-approve-render">APPROVE & RENDER TO RESOLVE</button>`.
   - Dispatches payload to `/approve-render`, shows loading spinner, provides dual-pulse haptic vibration, and presents live status.

---

## 6. Acceptance Criteria Verification Strategy

### 6.1. Acceptance Criterion 1: DaVinci Resolve Python Script Testing
- **Verification Target**: The Python script must instantiate `DaVinciResolveScript`, create a project/timeline, import 4K raw footage, and slice clips at exact timestamps.
- **Headless / Mock Test Suite (`tests/test_resolve_handoff_mock.py`)**:
  - Implements complete mock objects (`MockResolve`, `MockProjectManager`, `MockProject`, `MockMediaPool`, `MockMediaStorage`, `MockTimeline`, `MockMediaPoolItem`).
  - Asserts that:
    1. `scriptapp("Resolve")` is invoked.
    2. `CreateProject` or `LoadProject` sets `timelineResolutionWidth=1080`, `timelineResolutionHeight=1920`, `timelineFrameRate=60`.
    3. `AddItemListToMediaPool` receives exact 4K raw file path from `01_RAW`.
    4. `AppendToTimeline` receives correct dictionary `{"mediaPoolItem": item, "startFrame": 2052, "endFrame": 3852, "recordFrame": 0}` matching browser timestamps.
    5. Mathematical calculations (`round(time * fps)`) are verified to 100% precision.
  - Executable in CI/CD without physical GPU, dongle, or running Resolve instance.
- **Live Studio Verification Script (`tests/test_resolve_handoff_live.py`)**:
  - Probes live environment for running DaVinci Resolve Studio. If detected, creates a temporary test project and verifies timeline creation directly in the Resolve DOM.

### 6.2. Acceptance Criterion 2: Lighthouse Verification
- **Verification Target**: Web UI PWA passes Lighthouse tests for responsiveness and modern web standards.
- **Audit Targets**:
  - Performance: >= 90
  - Accessibility: >= 90
  - Best Practices: >= 90
  - SEO: >= 90
  - PWA Checklist: Valid `manifest.json`, theme-color, viewport meta tag, responsive layout across mobile viewports (360px, 390px, 412px, 768px), Glassmorphism styling, and View Transitions API integration.
- **Automated Verification Harness (`tests/test_pwa_lighthouse.py`)**:
  - Uses Lighthouse CLI / Chrome DevTools MCP or Python `playwright` / `selenium` / `requests_html` to execute headless audit and assert score thresholds.

### 6.3. Acceptance Criterion 3: FFmpeg Proxy & H.265 Transcoding
- **Verification Target**: FFmpeg generates playable 720p proxy and WAV file without crashing on H.265 HDR inputs, preserving 4K originals in `01_RAW`.
- **Automated Verification**:
  - Synthesize 4K 10-bit H.265 sample clip with audio.
  - Execute `generate_proxy_and_wav()`.
  - Validate proxy video stream via ffprobe (720p resolution, H.264 video codec, faststart).
  - Validate audio stream via ffprobe (16-bit PCM WAV, mono, 22.05kHz / 48kHz).
  - Verify 4K source file in `01_RAW` is untouched and bit-identical via SHA-256 hash.

### 6.4. Acceptance Criterion 4: Full Pipeline Integration
- **Verification Target**: End-to-end integration test (`tests/test_e2e_resolve_pipeline.py`) exercising:
  - ADB Ingest / Raw Staging -> 720p Proxy + WAV Generation -> Web UI Scrubber Payload -> Approve & Render Endpoint -> DaVinci Resolve Timeline Creation -> SQLite Manifest Update.

---

## 7. Actionable Implementation Runbook for Downstream Engineering

1. **Implement `content_creation/resolve_handoff.py`**:
   - Build `DaVinciResolveHandoffEngine` with dynamic Windows path discovery, project creation, 9:16 vertical settings, 4K clip import from `01_RAW`, and exact frame-sliced timeline construction.
2. **Update `content_creation/remote_trigger.py`**:
   - Add `POST /approve-render` (or `/api/resolve/handoff`) and `GET /api/clips/pending` endpoints.
   - Mount proxy media file streaming.
3. **Upgrade `content_creation/static/index.html`**:
   - Embed 720p proxy video player, interactive dual-handle scrubber, drop marker visualization, and "Approve & Render" CTA with View Transitions.
4. **Implement Test Suite**:
   - Add `tests/test_resolve_handoff_mock.py` (100% headless mock coverage).
   - Add `tests/test_resolve_handoff_live.py` (live Studio probe).
   - Add `tests/test_pwa_lighthouse_standards.py` (DOM & PWA standards verification).
   - Add `tests/test_e2e_resolve_pipeline.py` (complete pipeline integration).

---
