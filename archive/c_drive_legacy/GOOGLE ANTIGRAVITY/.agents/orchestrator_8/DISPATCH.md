# Dispatch Log

## 2026-08-22T12:27:39Z
You are the Project Orchestrator for the Master Dashboard UI Overhaul.

# Project Task: Master Dashboard UI Overhaul
- **Authoritative Request File**: `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md` (specifically see section `## Follow-up — 2026-08-22T12:26:52Z`)
- **Project Working Directory**: `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation`
- **Orchestrator Working Directory**: `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\orchestrator_8`
- **File to Overhaul**: `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\index.html`

## Core Requirements
### R1. Desktop-Class CSS Grid Layout
Rewrite `index.html` to utilize a professional, dockable CSS Grid system containing:
- **Left Sidebar:** Project Navigation, Raw Asset Bins, and a Batch Render Queue.
- **Center Canvas (Top):** A massive 720p Proxy Viewer component. Must include toggleable HUD overlays for the **YouTube Shorts Safe Zone (900x1270 px)** and **TikTok Safe Zone (920x1310 px)**.
- **Center Canvas (Bottom):** Multi-track timeline with a visual audio waveform track and a draggable Electric Blue playhead.
- **Right Inspector:** Context-aware metadata panel (Festival, Artist, BPM, Drop Timestamps).

### R2. Color Palette & Aesthetics
Implement the strict slate dark mode hierarchy:
- Base Canvas: `#0B0F19`
- Elevated Panels: `#1A2234`
- Borders: `#2D3748`
- Text: `#E2E8F0`
- Active Accents: Electric Blue `#3B82F6` (for playhead, selected clips).

### R3. API Preservation & Functionality
Preserve existing JavaScript `fetch` API logic. The dashboard must continue to communicate with the FastAPI backend using these endpoints:
- `POST /trigger-pipeline`
- `POST /approve-render`
- `GET /proxies`
- `GET /status`
- `POST /cancel`
- `GET /health`
Wire all new UI components (timeline scrubber, render queue, metadata inputs, etc.) to these endpoints.

### R4. Omnichannel Guardrails (Alerts)
Embed platform-specific warning toasts/HUD elements:
- Warn the user (Amber alert) if the timeline trim selection exceeds **59.00 seconds** (YouTube Content ID limit).
- Show a "Ghost-Linking Audio" badge for TikTok exports.

## Execution Rules
- Rewrite the file completely. Do not leave placeholder comments in the JavaScript; ensure it remains fully functional and wired to the FastAPI backend.
- Deconstruct tasks, dispatch to specialists / implementers / reviewers, maintain `progress.md` and `BRIEFING.md` in your working directory.
- Verify changes with full test suite execution.
- When all requirements and tests are satisfied, report completion with your handoff report.
