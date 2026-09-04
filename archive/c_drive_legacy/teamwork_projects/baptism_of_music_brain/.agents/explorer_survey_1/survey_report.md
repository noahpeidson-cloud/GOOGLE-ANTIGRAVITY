# Architectural & Technical Survey Report
**Project:** `baptism_of_music_brain` — Local Desktop ML Video Editing Brain & FFmpeg Renderer  
**Explorer Agent:** `explorer_survey_1`  
**Date:** 2026-08-27  
**Status:** Completed  

---

## 1. Executive Summary & Mission Overview

The `baptism_of_music_brain` system is a high-performance, local desktop Python/FastAPI service engineered to automate high-fidelity video post-production. It intercepts raw 4K video footage from an ingestion bridge (e.g., ADB Wi-Fi sync from Samsung Galaxy devices or local capture), executes an automated multimodal ML grading loop (powered by Gemini Omni) to generate an intelligent Edit Decision List (EDL), exposes an interactive FastAPI REST/WebSocket control plane for real-time human overrides, and invokes desktop-class FFmpeg to execute visually lossless rendering before atomically pushing the finalized media to a delivery directory.

### Key Objectives
1. **Zero-Friction Ingestion Monitoring**: Detect incoming high-bitrate video files with robust Windows file lock handling during copy operations.
2. **Autonomous ML Grading with Gemini Omni**: Analyze visual rhythm, cuts, color palette, and audio dynamics to synthesize a structured EDL.
3. **Interactive Control Plane**: Provide a FastAPI REST/WebSocket API allowing human editors to inspect, override, or approve EDLs.
4. **Visually Lossless FFmpeg Rendering**: Execute complex filtergraphs with visually lossless encoding (e.g., `libx264 -crf 17` / `hevc_nvenc -qp 18`) without uncompressed storage bloat.
5. **Atomic Delivery & Programmatic Verification**: Export completed videos to `delivery/` and verify stream codec, bitrate, resolution, and container integrity via automated probing.

---

## 2. Environment & Dependency Inventory

A thorough audit of the local Windows development environment (`C:\Users\noahp\teamwork_projects\baptism_of_music_brain`) was conducted:

| Subsystem / Package | Detected Version | Status / Capability | Purpose in Pipeline |
|---|---|---|---|
| **Python Runtime** | `3.13.14` (64-bit) | Available | Primary runtime environment |
| **FastAPI** | `0.141.1` | Installed | Asynchronous REST and WebSocket control plane |
| **Uvicorn** | `0.52.0` | Installed | ASGI web server |
| **Pydantic** | `2.13.4` | Installed | Type-safe data models & EDL schema validation |
| **PyWin32** | `312` | Installed | Win32 native API (`win32file`) for Windows file lock detection |
| **Watchdog** | `6.0.0` | Installed | Native OS file system directory watcher |
| **Watchfiles** | `1.2.0` | Installed | Rust-backed async directory watcher for FastAPI lifespan |
| **Google GenAI SDK** | `2.19.0` | Installed | Gemini Omni API client (`google-genai`) |
| **ImageIO-FFmpeg** | `0.6.0` | Installed | Bundles FFmpeg v7.1 (Gyan static build) with full encoder suite |
| **FFmpeg Binary** | `7.1-essentials_build` | Available via ImageIO / Winget | `libx264`, `libx265`, `hevc_nvenc`, `h264_nvenc`, `prores` |
| **Pytest Suite** | `pytest 9.1.1`, `pytest-asyncio 1.4.0` | Installed | Unit, integration, and E2E verification test harness |
| **HTTPX** | `0.28.1` | Installed | Async HTTP client for test suite and API communication |
| **Pandas / NumPy** | `pandas 3.0.5`, `numpy 2.5.1` | Installed | Telemetry, scoring calculations, and metadata analysis |
| **Google ADC** | Present at `%APPDATA%/gcloud/` | Configured | Google Cloud Application Default Credentials |

---

## 3. Ingestion Watcher & Windows File Lock Mechanism

### 3.1 The "Half-Baked / In-Flight Copy" Challenge
When multi-gigabyte 4K video files are transferred into the `ingest/` folder (via ADB sync, network share, USB, or local file copy), Windows file system notifications (`on_created`, `on_modified`) fire immediately upon file handle creation. If the pipeline attempts to probe, analyze, or render the file while the write operation is ongoing:
- A `PermissionError: [Errno 13] Permission denied` is raised if opened exclusively.
- Partial container headers or truncated frames cause FFmpeg/FFprobe decoding panics.
- ML inference receives corrupted or zero-length buffers.

### 3.2 Robust 3-Tier Lock Detection Algorithm
To guarantee 100% reliability on Windows, the ingestion engine implements a 3-tier lock verification algorithm:

```
[File Detected in ingest/]
           │
           ▼
Tier 1: Extension Filter
Is file .tmp, .part, .crdownload, or hidden?
     ├── YES ──► Ignore / Wait for Rename
     └── NO  ──► Proceed to Tier 2
           │
           ▼
Tier 2: Win32 Exclusive Handle Acquisition (Win32 API)
Attempt: win32file.CreateFile(
    filepath,
    GENERIC_READ | GENERIC_WRITE,
    dwShareMode=0 (Exclusive),
    OPEN_EXISTING
)
     ├── FAILED (ERROR_SHARING_VIOLATION) ──► Backoff (500ms) & Retry
     └── SUCCESS ──► Release Handle immediately ──► Proceed to Tier 3
           │
           ▼
Tier 3: Size Stability Debounce
Sample os.path.getsize(filepath) at t0 and t1 (interval: 1.0s).
Are size(t0) == size(t1) AND size > 0?
     ├── NO  ──► Reset Debounce Timer & Retry
     └── YES ──► Transition State: INGESTED -> ML_GRADING
```

### 3.3 File Lifecycle Finite State Machine (FSM)

Each video progresses through a deterministic lifecycle:

```
┌──────────────┐     File Arrives      ┌───────────────┐
│   DETECTED   │ ────────────────────► │   INGESTING   │ (Lock held by writer)
└──────────────┘                       └───────┬───────┘
                                               │ Lock released & Size stable
                                               ▼
┌──────────────┐     ML Loop Triggered ┌───────────────┐
│  ML_GRADING  │ ◄──────────────────── │   INGESTED    │ (Valid container verified)
└──────┬───────┘                       └───────────────┘
       │ EDL generated
       ▼
┌──────────────────┐  Manual Override  ┌──────────────────┐
│ AWAITING_OVERRIDE│ ────────────────► │  OVERRIDE_APPLIED│
└──────┬───────────┘                   └─────────┬────────┘
       │ Approved / Auto-timeout                 │
       └───────────────────┬─────────────────────┘
                           ▼
                   ┌───────────────┐
                   │   RENDERING   │ (FFmpeg process active)
                   └───────┬───────┘
                           │ FFmpeg exit code 0 + Probe OK
                           ▼
                   ┌───────────────┐
                   │   DELIVERED   │ (Atomically moved to delivery/)
                   └───────────────┘
```

---

## 4. End-to-End Architectural Blueprint

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               BAPTISM OF MUSIC BRAIN                                   │
│                                                                                        │
│   ┌─────────────────┐       ┌─────────────────┐       ┌────────────────────────────┐   │
│   │   Watchdog /    │       │   Win32 Lock    │       │       Video Metadata       │   │
│   │   Watchfiles    │ ────► │    Detector     │ ────► │       Probe Engine         │   │
│   │ (ingest/ watch) │       │ (Non-blocking)  │       │     (FFprobe / FFmpeg)     │   │
│   └─────────────────┘       └─────────────────┘       └─────────────┬──────────────┘   │
│                                                                     │                  │
│                                                                     ▼                  │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                          Gemini Omni ML Brain Loop                             │   │
│   │   - Video Rhythm & Beat Alignment      - Dynamic Viral Cut Decision Generator  │   │
│   │   - Color Balance & Aesthetic Grading  - Dual-Mode: Live GenAI + Offline Mock │   │
│   └────────────────────────────────────────┬───────────────────────────────────────┘   │
│                                            │                                           │
│                                            ▼                                           │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                     FastAPI REST & WebSocket Control Plane                     │   │
│   │   GET  /jobs,  GET /jobs/{id},  POST /jobs/{id}/override,  POST /jobs/{id}/approve│   │
│   │   GET  /health,  GET /config,  WS /jobs/{id}/events (Live Stderr & Progress)   │   │
│   └────────────────────────────────────────┬───────────────────────────────────────┘   │
│                                            │ Approved EDL                              │
│                                            ▼                                           │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                 Desktop-Class Lossless FFmpeg Rendering Engine                 │   │
│   │   - Complex Filtergraph Assembler (Trims, Audio Fade, EQ/LUT Color Grade)      │   │
│   │   - Visually Lossless Encoding (libx264 -crf 17 / hevc_nvenc -qp 18)           │   │
│   │   - Real-time Subprocess Stderr Progress Parser                                │   │
│   └────────────────────────────────────────┬───────────────────────────────────────┘   │
│                                            │ Render complete                           │
│                                            ▼                                           │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                       Atomic Delivery & Verification                           │   │
│   │   - Atomic Rename: delivery/.tmp_<id>.mp4 -> delivery/<final_name>.mp4         │   │
│   │   - Mathematical Probe Assertion (Resolution, Bitrate >= Threshold, Codec)     │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Detailed Subsystem Specifications

### 5.1 Core Data Models (Pydantic v2 Schema)

```python
class JobStatus(str, Enum):
    DETECTED = "DETECTED"
    INGESTING = "INGESTING"
    INGESTED = "INGESTED"
    ML_GRADING = "ML_GRADING"
    AWAITING_OVERRIDE = "AWAITING_OVERRIDE"
    OVERRIDE_APPLIED = "OVERRIDE_APPLIED"
    RENDERING = "RENDERING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"

class TrimSegment(BaseModel):
    start_time: float = Field(ge=0.0, description="Start time in seconds")
    end_time: float = Field(gt=0.0, description="End time in seconds")
    label: Optional[str] = None

class ColorGrade(BaseModel):
    brightness: float = Field(default=0.0, ge=-1.0, le=1.0)
    contrast: float = Field(default=1.0, ge=0.1, le=3.0)
    saturation: float = Field(default=1.0, ge=0.0, le=3.0)
    gamma: float = Field(default=1.0, ge=0.1, le=10.0)

class AudioConfig(BaseModel):
    volume_multiplier: float = Field(default=1.0, ge=0.0, le=5.0)
    strip_audio: bool = False
    fade_in_sec: float = 0.0
    fade_out_sec: float = 0.0

class EncodingProfile(str, Enum):
    CPU_X264_CRF17 = "CPU_X264_CRF17"       # libx264, crf=17, preset=slow, yuv420p
    CPU_HEVC_CRF18 = "CPU_HEVC_CRF18"       # libx265, crf=18, preset=medium
    GPU_NVENC_HEVC = "GPU_NVENC_HEVC"       # hevc_nvenc, qp=18, preset=p7
    GPU_NVENC_H264 = "GPU_NVENC_H264"       # h264_nvenc, cq=17, preset=p7

class EditDecisionList(BaseModel):
    edl_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    video_id: str
    version: int = 1
    source: Literal["AI_GENERATED", "USER_OVERRIDDEN", "FALLBACK_DEFAULT"] = "AI_GENERATED"
    segments: List[TrimSegment]
    color: ColorGrade = Field(default_factory=ColorGrade)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    profile: EncodingProfile = EncodingProfile.CPU_X264_CRF17
    target_resolution: Optional[Tuple[int, int]] = None
    ai_reasoning: Optional[str] = None

class VideoJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    input_file_path: str
    file_name: str
    file_size_bytes: int
    status: JobStatus = JobStatus.DETECTED
    progress_percent: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    edl: Optional[EditDecisionList] = None
    output_file_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

---

### 5.2 Gemini Omni ML Brain & Grading Loop
1. **Multimodal Analysis Engine**:
   - Evaluates video tempo, visual transitions, facial cues, scene dynamic range, and soundtrack energy.
   - Synthesizes intelligent trim recommendations (e.g. cutting 30s raw clip down to high-energy 10s viral highlight).
   - Generates subtle, cinematic color grading (`eq` parameters) and audio adjustments.
2. **Dual-Mode Engine Architecture**:
   - **Production Engine (`GeminiOmniProvider`)**: Uses `google-genai` interactions client to upload preview frames / proxies, prompts the Gemini Omni model with structured JSON schemas, and parses candidate EDLs.
   - **Deterministic Mock Engine (`MockMLGradingProvider`)**: Provides offline, deterministic EDL synthesis based on mathematical rules (e.g. 10% intro trim, 15% outro trim, slight saturation boost). Guarantees test suite execution without API keys, network latencies, or token costs.

---

### 5.3 FastAPI Control Plane & Overrides API
The FastAPI application provides a full management layer:

| HTTP Method | Route | Description |
|---|---|---|
| `GET` | `/health` | System health check, FFmpeg executable detection, hardware encoder status |
| `GET` | `/config` | Active pipeline configuration (`ingest_dir`, `delivery_dir`, `default_profile`) |
| `GET` | `/jobs` | List all tracked video jobs with status and progress |
| `GET` | `/jobs/{job_id}` | Retrieve specific job, probe metadata, and current EDL |
| `POST` | `/jobs/{job_id}/override` | Submit user modifications to EDL (trims, color, audio, profile) and trigger render |
| `POST` | `/jobs/{job_id}/approve` | Approve AI-generated EDL without changes to commence rendering |
| `POST` | `/jobs/ingest/trigger` | Manually trigger ingestion of a specific file path |
| `WS` | `/ws/jobs/{job_id}` | WebSocket endpoint streaming live progress and FFmpeg render stats |

---

### 5.4 High-Fidelity Desktop FFmpeg Rendering Engine
1. **Command Generation & Filtergraph Architecture**:
   - Translates trim segments into `-ss` and `-to` parameters or `trim`/`atrim` filtergraphs with `concat`.
   - Injects video color filters: `-vf eq=contrast={c}:brightness={b}:saturation={s}:gamma={g}`.
   - Injects audio filters: `-af volume={vol},afade=t=in:d={fade_in},afade=t=out:st={fade_out_st}:d={fade_out}`.
2. **Visually Lossless Encoding Configuration**:
   - **Target CRF**: `libx264 -crf 17 -preset slow -pix_fmt yuv420p -c:a aac -b:a 320k`.
   - **Lossless Metric**: `CRF 17` is universally recognized in digital video engineering as visually indistinguishable from uncompressed master files, while keeping file sizes reasonable for mobile gallery sync.
3. **Hardware Encoder Auto-Detection**:
   - Inspects `ffmpeg -encoders` at startup.
   - If NVIDIA GPU (`hevc_nvenc` or `h264_nvenc`) is detected and selected in profile, utilizes hardware acceleration; otherwise falls back gracefully to `libx264`.
4. **Real-time Stderr Progress Parsing**:
   - Reads lines matching `frame=\s*(\d+)\s+fps=\s*([\d\.]+)\s+time=(\d{2}:\d{2}:\d{2}\.\d{2})`.
   - Computes progress percentage relative to target EDL duration and updates `JobState.progress_percent`.

---

### 5.5 Atomic Delivery Pipeline & Verification Engine
1. **Atomic Write Protocol**:
   - FFmpeg outputs directly to a temporary staging file: `delivery/.tmp_{job_id}_{filename}`.
   - Upon exit code 0, performs verification probe.
   - If verification passes, performs atomic `os.replace` to `delivery/{filename}`.
2. **Programmatic Encoding Verification**:
   - Probes final delivery file using FFprobe/FFmpeg.
   - Mathematical assertions:
     - Output duration matches sum of EDL trim segment durations (within tolerance ±0.1s).
     - Video codec matches target profile (e.g. `h264`).
     - Bitrate is >= minimum visually lossless threshold.
     - Zero decoding errors / non-corrupt container.

---

## 6. Proposed Project Directory Structure

```
baptism_of_music_brain/
├── config/
│   ├── __init__.py
│   └── settings.py              # Environment settings, directory paths, default profiles
├── src/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py           # Pydantic models (EDL, VideoJob, ColorGrade, AudioConfig)
│   │   └── state_machine.py     # Job status lifecycle and state transition logic
│   ├── watcher/
│   │   ├── __init__.py
│   │   ├── file_locker.py       # Win32 exclusive lock & debounce detector
│   │   └── ingest_watcher.py    # Directory observer (Watchdog / Watchfiles async worker)
│   ├── ml_brain/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract ML grading provider interface
│   │   ├── mock_provider.py     # Offline deterministic mock provider for testing
│   │   └── gemini_provider.py   # Live Gemini Omni provider via google-genai
│   ├── renderer/
│   │   ├── __init__.py
│   │   ├── probe.py             # FFmpeg/FFprobe media stream analyzer & metadata parser
│   │   ├── filtergraph.py       # EDL to FFmpeg command/filtergraph generator
│   │   └── ffmpeg_engine.py     # Subprocess execution, stderr progress parsing, fallback
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── job_manager.py       # In-memory / SQLite job repository and state coordinator
│   │   └── orchestrator.py      # End-to-end pipeline coordinator
│   └── api/
│       ├── __init__.py
│       ├── app.py               # FastAPI application factory and lifespan manager
│       └── routes.py            # REST endpoints and WebSocket handlers
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Fixtures (temp folders, mock videos, test client)
│   ├── unit/
│   │   ├── test_file_locker.py  # Tests for Win32 locking and debounce
│   │   ├── test_filtergraph.py  # Tests for EDL to FFmpeg command construction
│   │   ├── test_ml_brain.py     # Tests for mock ML provider and EDL output
│   │   └── test_probe.py        # Tests for media metadata probing
│   ├── integration/
│   │   ├── test_api_routes.py   # FastAPI endpoint tests (override, approve, get status)
│   │   └── test_renderer.py     # FFmpeg rendering execution and visually lossless encoding
│   └── e2e/
│       ├── test_encoding_verification.py  # Programmatic ffprobe codec/bitrate/resolution check
│       └── test_end_to_end_pipeline.py    # Ingest -> ML -> Override -> Render -> Delivery E2E
├── ingest/                      # Ingest directory (gitignored)
├── delivery/                    # Delivery directory (gitignored)
├── pytest.ini                   # Pytest configuration with async markers
├── requirements.txt             # Python dependencies
├── README.md                    # System documentation and operational runbook
└── ORIGINAL_REQUEST.md          # User prompt and acceptance criteria
```

---

## 7. Risk Analysis & Mitigation Strategies

| Potential Risk | Root Cause | Architectural Mitigation |
|---|---|---|
| **Partial File Corruption on Ingest** | Watcher fires before 4K copy completes over Wi-Fi / ADB | Mandatory 3-tier lock verification (Win32 exclusive lock test + 1.0s size debounce) before ingestion state transition. |
| **System FFmpeg / FFprobe PATH Absence** | Machine does not have global `ffmpeg` in Windows PATH | Auto-detect `imageio_ffmpeg.get_ffmpeg_exe()` as built-in fallback; support setting explicit binary path via configuration. |
| **FFmpeg Subprocess Hanging on Corrupt Input** | Malformed input video stream causes indefinite blocking | Implement execution timeout (e.g. 120s), asynchronous non-blocking process reading, and graceful termination. |
| **Race Conditions in Downstream Consumers** | External bridge reads delivery file while FFmpeg is writing | Atomic write protocol: render to `delivery/.tmp_{id}.mp4` first, probe verify, then atomically rename to destination. |
| **API Rate Limits / Outages in Live ML Brain** | Gemini API network latency or token quota exhaustion | Implement graceful fallback to deterministic default EDL rules; provide clear status flag (`source: FALLBACK_DEFAULT`) in EDL. |

---

## 8. Summary of Findings & Next Steps

1. **Environment Readiness**: The Windows environment is fully equipped with Python 3.13.14, FastAPI, Watchdog, PyWin32, Google GenAI SDK, and an FFmpeg v7.1 binary with visually lossless encoders (`libx264`, `libx265`, `hevc_nvenc`).
2. **Deterministic Architecture**: The proposed design cleanly separates concerns across data models, file locking, ML decision loops, REST control planes, FFmpeg filtergraph generation, and atomic delivery verification.
3. **Execution Plan**: Proceed with Orchestrator Milestone decomposition:
   - **Milestone 1**: Core Data Models, Configuration, Ingestion Directory Watcher & Win32 File Locking.
   - **Milestone 2**: Gemini Omni ML Grading Loop & FastAPI Overrides API.
   - **Milestone 3**: Desktop FFmpeg Visually Lossless Rendering Engine & Delivery Pipeline.
   - **Milestone 4**: Automated E2E Verification Suite (FFprobe Assertions & Full Ingest-to-Delivery Pipeline).
