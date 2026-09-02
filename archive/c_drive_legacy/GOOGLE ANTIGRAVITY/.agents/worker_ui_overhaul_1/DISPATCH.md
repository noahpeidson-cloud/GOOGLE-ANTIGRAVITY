## 2026-08-22T12:30:43Z
<USER_REQUEST>
You are the Primary Implementation Worker for the Master Dashboard UI Overhaul.

## Your Identity & Workspace
- Role: Primary Frontend & Full-Stack UI Implementation Worker
- Working Directory: G:\My Drive\GOOGLE ANTIGRAVITY\.agents\worker_ui_overhaul_1
- Parent Conversation ID: d17bc100-57eb-4aab-ae23-d164c44ded4e
- Code Ownership: `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\index.html` and `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\static\index.html`

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Context Files to Read Before Writing Code
1. `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md`
2. `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\orchestrator_8\PROJECT.md`
3. `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\orchestrator_8\TEST_INFRA.md`
4. `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_survey_1\survey_report.md`
5. `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_survey_2\survey_report.md`
6. `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_survey_3\survey_report.md`

## Implementation Task Requirements
Completely rewrite `content_creation/index.html` (and synchronize `content_creation/static/index.html`) with:

1. **Desktop-Class CSS Grid Layout**:
   - 3-column / 3-row layout (`grid-template-areas: "topbar topbar topbar" "sidebar workspace inspector" "footer footer footer"`)
   - Left Sidebar (320px): Project Navigation, Raw Asset Bins (dynamically loaded from `/proxies`), Batch Render Queue, Ingest CTA (`#trigger-btn`, `#btn-label`, `#btn-spinner`).
   - Center Workspace Top: 720p Proxy Viewer (9:16 aspect ratio) with toggleable HUD safe zone overlays (YouTube Shorts 900x1270 px, TikTok 920x1310 px, Dual, None), video player controls (`#play-pause-btn`, `#step-back-btn`, `#step-fwd-btn`, `#jump-drop-btn`), resolution badge (`#video-resolution-badge`), time display (`#video-time-display`), buffering HUD (`#buffering-status`), clip dropdown selector (`#clip-selector`).
   - Center Workspace Bottom: Multi-track timeline with Video track (V1), Audio Waveform track (A1) rendered via high-DPI HTML5 Canvas (`#waveform-canvas`), draggable Electric Blue playhead (`#timeline-playhead`), dual sub-frame trim handles (`#start-trim-handle`, `#end-trim-handle`), drop highlight region (`#drop-highlight-region`), timecode readouts (`#start-time-display`, `#end-time-display`, `#duration-display`), minimum 5.0s trim duration constraint.
   - Right Inspector (340px): Context-aware metadata panel (`#festival-input`, `#artist-input`, `#metadata-section`, BPM, Genre, Brand, Tier, Drop Timestamps), primary CTA "APPROVE & RENDER (DAVINCI)" (`#approve-render-btn`, `#approve-btn-label`).
   - Footer: Live daemon state (`#daemon-state`), telemetry display (`#active-job-id`, `#elapsed-time`, `#last-job-summary`, `#cancel-btn`, `#refresh-status-btn`).
   - Header: Live health status badges (`#health-badges`, `#badge-adb`, `#badge-ffmpeg`, `#badge-server`).
   - Toasts: Toast system (`#toast-container`, `#toast-card`, `#toast-icon`, `#toast-title`, `#toast-message`, `#toast-close`, `#status-toast`, `#status-display`).

2. **Slate Dark Mode Hierarchy**:
   - Base Canvas: `#0B0F19`
   - Elevated Panels: `#1A2234`
   - Borders: `#2D3748`
   - Text: `#E2E8F0`
   - Active Accents: Electric Blue `#3B82F6` (playhead, active clip highlights, primary buttons).
   - Retain OLED black compatibility (`--bg-oled-black: #000000`, `theme-color: #000000`).

3. **Omnichannel Guardrails**:
   - 59.00s YouTube Content ID warning toast / amber alert banner triggering when `duration > 59.00s` with a single-click auto-clamp action (`[Clamp to 59.00s]`).
   - TikTok Ghost-Linking Audio badge (`#ghost-link-badge`) and armed indicator.

4. **FastAPI Fetch API Preservation & Complete JavaScript Logic**:
   - Zero placeholder comments. Complete vanilla JavaScript `RemoteTriggerClient` class.
   - `fetch('/trigger-pipeline')`, `fetch('/approve-render')`, `fetch('/proxies')`, `fetch('/status')`, `fetch('/cancel')`, `fetch('/health')`, and HTTP 206 video byte-range streaming.
   - Real-time High-DPI canvas waveform drawing with active drop region illumination.
   - Pointer capture drag handling for playhead and trim handles.

5. **Static Sync & Test Suite Verification**:
   - Mirror `content_creation/index.html` to `content_creation/static/index.html`.
   - Run the automated test suites using `python -m unittest discover tests` from `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation`.
   - Ensure all tests pass with 0 errors / 0 failures.
   - Write your complete handoff report to `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\worker_ui_overhaul_1\handoff.md`.
   - Use `send_message` to notify the orchestrator (Conversation ID: d17bc100-57eb-4aab-ae23-d164c44ded4e).
</USER_REQUEST>
