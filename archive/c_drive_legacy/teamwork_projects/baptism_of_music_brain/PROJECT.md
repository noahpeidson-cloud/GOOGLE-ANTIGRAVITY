# Project: baptism_of_music_brain

## Architecture
`baptism_of_music_brain` is a local desktop Python/FastAPI machine learning video editing brain and desktop-class FFmpeg renderer. It intercepts raw 4K/8K video footage from an ingestion bridge (e.g., Samsung Galaxy devices or local file drops), analyzes visual and audio streams via an autonomous Gemini Omni ML feedback loop, synthesizes a structured Edit Decision List (EDL), exposes an interactive FastAPI REST/WebSocket control plane for real-time human overrides, renders the physical video edits with visually lossless fidelity (`libx264 -crf 17` / `hevc_nvenc`) via desktop FFmpeg, and atomically delivers the master video to a delivery directory with programmatic `ffprobe` verification.

```
┌─────────────────┐       ┌─────────────────┐       ┌────────────────────────────┐
│   Watchdog /    │       │   Win32 Lock    │       │       Video Metadata       │
│   Watchfiles    │ ────► │    Detector     │ ────► │       Probe Engine         │
│ (ingest/ watch) │       │ (Non-blocking)  │       │     (FFprobe / FFmpeg)     │
└─────────────────┘       └─────────────────┘       └─────────────┬──────────────┘
                                                                  │
                                                                  ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                          Gemini Omni ML Brain Loop                             │
│   - Video Rhythm & Beat Alignment      - Dynamic Viral Cut Decision Generator  │
│   - Color Balance & Aesthetic Grading  - Dual-Mode: Live GenAI + Offline Mock │
└────────────────────────────────────────┬───────────────────────────────────────┘
                                         │
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                     FastAPI REST & WebSocket Control Plane                     │
│   GET  /jobs,  GET /jobs/{id},  PUT /jobs/{id}/edl,  POST /jobs/{id}/approve   │
│   GET  /health,  GET /config,   POST /jobs/{id}/regrade,  GET /jobs/{id}/proxy │
└────────────────────────────────────────┬───────────────────────────────────────┘
                                         │ Approved EDL
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                 Desktop-Class Lossless FFmpeg Rendering Engine                 │
│   - Complex Filtergraph Assembler (Trims, Audio Fade, EQ/LUT Color Grade)      │
│   - Visually Lossless Encoding (libx264 -crf 17 / hevc_nvenc -qp 18)           │
│   - Real-time Subprocess Stderr Progress Parser                                │
└────────────────────────────────────────┬───────────────────────────────────────┘
                                         │ Render complete
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                       Atomic Delivery & Verification                           │
│   - Atomic Move: delivery/.tmp_<id>.mp4 -> delivery/<final_name>.mp4           │
│   - Mathematical Probe Assertion (Resolution, Bitrate >= Threshold, Codec)     │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Feature Inventory
Every feature identified during the Survey phase is mapped to an implementation or testing milestone:

| # | Feature | Description | Milestone | Source | Status |
|---|---------|-------------|-----------|--------|:------:|
| 1 | Configuration & Settings | Typed settings for directories, API keys, default encoding profile, port, host | M1 | Survey | DONE |
| 2 | Pydantic v2 Data Models | Schema definitions for `EditDecisionList`, `ClipSegment`, `ColorGrade`, `AudioConfig`, `VideoJob`, `JobStatus` | M1 | Survey | DONE |
| 3 | File System Watcher | Watchdog & async directory observer monitoring `ingest/` for new raw video drops | M1 | Survey | DONE |
| 4 | Win32 File Lock Detector | 3-tier lock detection (ext filter, Win32 exclusive handle test, 1.0s size debounce) for incomplete copies | M1 | Survey | DONE |
| 5 | Job State Repository | In-memory thread-safe state store & job lifecycle FSM manager | M1 | Survey | DONE |
| 6 | Media Metadata Prober | `ffprobe` wrapper extracting stream codec, duration, resolution, fps, bitrate, audio channels/rate | M1 | Survey | DONE |
| 7 | Gemini Omni ML Client | `google-genai` multimodal client analyzing video rhythm, cuts, color, and audio for EDL synthesis | M2 | Survey | DONE |
| 8 | Deterministic Mock ML Engine | Offline zero-dependency mock grading engine for repeatable tests and CI/E2E pipelines | M2 | Survey | DONE |
| 9 | FastAPI App & Lifespan | FastAPI application factory, background ingestion task management, CORS, error handling | M2 | Survey | DONE |
| 10 | REST API: Health & Config | `GET /api/v1/health`, `GET /api/v1/config` diagnostics and hardware encoder discovery | M2 | Survey | DONE |
| 11 | REST API: Job Management | `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `POST /api/v1/jobs/ingest/trigger` | M2 | Survey | DONE |
| 12 | REST API: EDL Query & Overrides | `GET /api/v1/jobs/{id}/edl`, `PUT /api/v1/jobs/{id}/edl` with validation of user overrides | M2 | Survey | DONE |
| 13 | REST API: Approval & Regrade | `POST /api/v1/jobs/{id}/approve`, `POST /api/v1/jobs/{id}/regrade` | M2 | Survey | DONE |
| 14 | HTTP Range Proxy Video Streaming | `GET /api/v1/jobs/{id}/proxy` with HTTP 206 Partial Content support for scrubbing | M2 | Survey | DONE |
| 15 | Visually Lossless Encoding Profiles | Profiles: `x264_crf17` (default), `x264_yuv444p`, `x265_crf16` (10-bit hvc1), `hevc_nvenc`, `prores_hq` | M3 | Survey | DONE |
| 16 | Filtergraph Assembler | Compiles trims (`trim`/`atrim` + `setpts`), color grading (`eq`), audio volume/fade, scale/pad, concat | M3 | Survey | DONE |
| 17 | Audio Loudness Normalization | Integrated EBU R128 (`loudnorm`) targeting -14 LUFS, -1.5 dBFS true peak | M3 | Survey | DONE |
| 18 | FFmpeg Subprocess Executor | Asynchronous process executor parsing real-time stderr progress (0-100%) without deadlock | M3 | Survey | DONE |
| 19 | Atomic Delivery Pipeline | Temp staging `.tmp_<id>.mp4`, probe check, and atomic move to `delivery/<filename>` | M3 | Survey | DONE |
| 20 | Procedural Test Media Generator | Synthetic 4K, 1080p, and vertical video clip generator via `ffmpeg -f lavfi` (testsrc2, noise, sine) | E2E-Track | Survey | DONE |
| 21 | Mathematical ffprobe Assertions | Programmatic validation of codec, bitrate thresholds, spatial resolution, and duration invariance | E2E-Track | Survey | DONE |
| 22 | Tier 1: Feature Coverage Tests | Unit & functional tests for each individual subsystem in isolation (>=5 per feature area) | E2E-Track | Survey | DONE |
| 23 | Tier 2: Boundary & Corner Tests | Edge cases: partial writes, invalid trim bounds, odd dimensions, corrupt files, zero audio | E2E-Track | Survey | DONE |
| 24 | Tier 3: Pairwise Combination Tests | Ingest+Override, Live/Mock+Render, 4K/1080p+Color+Loudnorm combinations | E2E-Track | Survey | DONE |
| 25 | Tier 4: Real-World Workload Tests | Full end-to-end integration: Ingest drop -> Detect -> ML -> Override -> Render -> Delivery -> Probe | E2E-Track | Survey | DONE |
| 26 | Tier 5: Adversarial Hardening | White-box stress tests, race conditions, memory leaks, high-bitrate load testing | Final-M | Survey | DONE |

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Test infra, procedural test media generator, Tier 1-4 opaque-box test suites, `TEST_READY.md` | none | DONE |
| 1 | Core Models, Ingest & Locking | Settings, Pydantic schemas, Prober, Win32 File Locking, Ingest Watchdog, Job State Store | none | DONE |
| 2 | ML Brain & FastAPI Control Plane | Gemini Omni client, Mock ML engine, FastAPI endpoints (health, jobs, EDL overrides, approval, proxy) | M1 | DONE |
| 3 | Lossless FFmpeg Renderer & Delivery | Visually lossless encoding profiles, filtergraph compiler, loudnorm, async process runner, atomic delivery | M1, M2 | DONE |
| Final | Final E2E Pass & Adversarial Hardening | Phase 1: 100% pass on Tiers 1-4 E2E tests; Phase 2: Tier 5 Adversarial Coverage Hardening | M1, M2, M3, E2E | DONE |

## Interface Contracts

### 1. `schemas.py` ↔ All Modules
- `EditDecisionList`: Contains `job_id`, `source_video_path`, `target_resolution` `(width, height)`, `target_fps`, `encoding_profile`, `segments: List[ClipSegment]`, `color_grade: ColorGradeSettings`, `audio_mastering: AudioMasteringSettings`, `manual_override_applied: bool`.
- `ClipSegment`: `clip_id: str`, `source_in_sec: float`, `source_out_sec: float`, `timeline_in_sec: float`, `speed_multiplier: float`, `volume_multiplier: float`, `label: Optional[str]`.
- `ColorGradeSettings`: `contrast: float` (0.0-3.0), `brightness: float` (-1.0 to 1.0), `saturation: float` (0.0-3.0), `gamma: float` (0.1-10.0).
- `AudioMasteringSettings`: `normalize_lufs: bool`, `target_lufs: float` (-14.0), `peak_limit_db: float` (-1.5), `gain_db: float`.
- `JobMetadata`: `job_id: str`, `source_filepath: str`, `status: JobStatus`, `progress_percent: float`, `active_edl: Optional[EditDecisionList]`, `delivery_filepath: Optional[str]`.

### 2. `watcher` ↔ `pipeline`
- `on_file_ingested(file_path: str) -> JobMetadata`: Called only after 3-tier lock validation succeeds. Registers job in repository with status `INGESTED` and initiates ML grading task.

### 3. `ml_brain` ↔ `pipeline`
- `grade_video(job: JobMetadata, probe_data: dict) -> EditDecisionList`: Analyzes video (via Gemini Omni or deterministic mock) and attaches generated EDL to `job.active_edl`, transitioning state to `AWAITING_OVERRIDE` or `EDL_READY`.

### 4. `api` ↔ `pipeline`
- `PUT /api/v1/jobs/{job_id}/edl`: Receives partial or full `EDLOverridePayload`, updates `job.active_edl`, sets `manual_override_applied=True`.
- `POST /api/v1/jobs/{job_id}/approve`: Validates current EDL and enqueues FFmpeg render task, transitioning state to `RENDERING`.

### 5. `renderer` ↔ `delivery`
- `render_edl(edl: EditDecisionList, progress_callback: Callable[[float], None]) -> str`: Compiles complex filtergraph, launches FFmpeg with visually lossless profile (`libx264 -crf 17`), writes to `delivery/.tmp_{job_id}.mp4`, validates with `ffprobe`, atomically renames to `delivery/{filename}`, and returns final delivery path.
