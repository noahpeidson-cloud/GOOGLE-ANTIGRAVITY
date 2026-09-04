# Project: Master Dashboard UI Overhaul

## Architecture
The Master Dashboard (`content_creation/index.html` and `static/index.html`) has been successfully rewritten as a desktop-class, dockable CSS Grid workspace for EDM short-form video engineering. It connects via REST and HTTP 206 byte-range streaming to the FastAPI backend (`remote_trigger.py`), orchestrator CLI (`orchestrator.py`), and DaVinci Resolve Studio handoff engine (`resolve_handoff.py`).

### Visual Layout & Zones
- **Top Bar**: System brand, live health telemetry badges (`badge-adb`, `badge-ffmpeg`, `badge-server`), sync indicator.
- **Left Sidebar (320px)**: Project navigation, raw asset bins (discovered takes from `/proxies`), batch render queue.
- **Center Canvas (Top, 1fr)**: 720p Proxy Video Viewer (9:16 aspect ratio) with toggleable HUD overlays for YouTube Shorts Safe Zone (900x1270 px) and TikTok Safe Zone (920x1310 px).
- **Center Canvas (Bottom, ~280px)**: Multi-track timeline with video lane (V1), high-DPI HTML5 canvas audio waveform lane (A1), draggable Electric Blue playhead (`#3B82F6`), dual sub-frame trim handles, and high-precision timecodes.
- **Right Inspector (340px)**: Context-aware metadata panel (Festival, Artist, Track, BPM, Genre, Brand, Tier, Drop Timestamps), primary CTA "APPROVE & RENDER (DAVINCI)", and pipeline trigger controls.
- **Footer Status**: Daemon state machine, active job telemetry, elapsed time, playhead position, zoom.

## Feature Inventory
| # | Feature | Description | Milestone | Source | Status |
|---|---------|-------------|-----------|--------|--------|
| 1 | Desktop-Class CSS Grid Layout | 3-zone, 3-column dockable grid layout with collapsible sidebars | M1 | User R1 / Survey | DONE |
| 2 | Slate Dark Mode Color Palette | Strict hierarchy: Base `#0B0F19`, Elevated `#1A2234`, Borders `#2D3748`, Text `#E2E8F0`, Accents `#3B82F6` | M1 | User R2 / Survey | DONE |
| 3 | 720p Proxy Viewer Component | 9:16 vertical video player with resolution badge, buffering HUD, transport controls | M2 | User R1 / Survey | DONE |
| 4 | HUD Safe Zone Overlays | Pixel-accurate toggleable overlays for YouTube Shorts (900x1270 px) and TikTok (920x1310 px) | M2 | User R1 / Survey | DONE |
| 5 | Multi-Track Timeline Scrubber | V1 video track, draggable Electric Blue playhead (`#3B82F6`), dual trim handles, timecode readouts | M3 | User R1 / Survey | DONE |
| 6 | High-DPI Audio Waveform Engine | HTML5 Canvas rendering RMS audio peaks with active drop zone illumination | M3 | User R1 / Survey | DONE |
| 7 | Context-Aware Metadata Panel | Festival, Artist, Track, BPM, Genre, Brand, Tier, Drop Timestamps, DaVinci CTA | M4 | User R1 / Survey | DONE |
| 8 | FastAPI Fetch API Wiring | Complete wiring to `/trigger-pipeline`, `/approve-render`, `/proxies`, `/status`, `/cancel`, `/health` | M4 | User R3 / Survey | DONE |
| 9 | 59.00s Content ID Amber Alert | Reactive warning toast/banner when trim duration > 59.00s with auto-clamp action | M5 | User R4 / Survey | DONE |
| 10| TikTok Ghost-Linking Audio Badge | Visual badge and armed indicator for TikTok audio metadata preservation | M5 | User R4 / Survey | DONE |
| 11| Static Asset Synchronization | Exact sync between `content_creation/index.html` and `content_creation/static/index.html` | M6 | Survey / Tests | DONE |
| 12| 100% Test Suite Compliance | All 34 unittest modules, DOM assertions, and Lighthouse standards passing | M6 | Survey / Tests | DONE |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Grid Layout & Dark Theme | CSS Grid structure, Slate Dark tokens, dockable containers | Survey | DONE |
| M2 | Proxy Viewer & HUD Safe Zones | 720p 9:16 player, SVG safe area masks (YT Shorts 900x1270, TikTok 920x1310) | M1 | DONE |
| M3 | Multi-Track Timeline & Waveform | High-DPI canvas waveform, Electric Blue playhead, dual trim handles | M1, M2 | DONE |
| M4 | API Integration & Metadata Panel | Context inspector, FastAPI fetch endpoints, DaVinci Resolve handoff | M1, M2, M3 | DONE |
| M5 | Omnichannel Guardrails | 59.00s Content ID Amber alert, TikTok Ghost-Linking badge | M3, M4 | DONE |
| M6 | Sync & Full Test Verification | Dual-file sync, full test suite pass (672 tests), forensic audit | M1-M5 | DONE |

## Interface Contracts
### Frontend ↔ FastAPI Backend (`remote_trigger.py`)
- `POST /trigger-pipeline`: JSON body `PipelineTriggerRequest`, response `202 Accepted` / `409 Conflict`.
- `POST /approve-render`: JSON body `ApproveRenderRequest` (`clip_id`, `raw_file_path`, `start_time`, `end_time`, `duration`, `fps`), response `200 OK`.
- `GET /proxies`: response `200 OK` (`clips` array of `PendingClipItem`).
- `GET /proxies/{clip_id}/video`: HTTP 206 Byte Range streaming.
- `GET /status`: response `200 OK` (`state`, `is_running`, `active_job`, `recent_jobs`).
- `POST /cancel`: response `200 OK` (`terminated: true`).
- `GET /health`: response `200 OK` (`adb_available`, `ffmpeg_available`, `ffprobe_available`).

## Code Layout
- `content_creation/index.html` — Master root dashboard source file (SHA-256: `2038D1399ECE7E75AAFE942C48BA309B454CF804C238F997F724A1769B49D574`).
- `content_creation/static/index.html` — Synchronized PWA static distribution file (Exact byte match).
- `content_creation/remote_trigger.py` — FastAPI server and endpoints.
- `content_creation/tests/` — Automated test suite (34 modules, 672 passing tests).
