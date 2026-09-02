# Master Execution Plan: Mobile PWA Zero-Touch Remote Trigger

## Objective
Pivot Zero-Touch Remote Trigger from Tasker-dependent workflow to a mobile-first Progressive Web App (PWA) hosted directly by `content_creation/remote_trigger.py` (FastAPI).

## Requirements Breakdown
- **R1. Serve Web UI**: Modify `content_creation/remote_trigger.py` to serve static HTML at root `GET /` (e.g., via `HTMLResponse` or `FileResponse` / `StaticFiles` or inline/template serving `index.html` from a static/templates folder or dedicated location).
- **R2. Mobile-First Dashboard (PWA)**: Create `index.html` with dark theme, responsive mobile layout, single massive "TRIGGER EDM PIPELINE" button, and standard PWA meta tags (`viewport`, `apple-mobile-web-app-capable`, `theme-color`, `mobile-web-app-capable`, web app manifest linkage if applicable).
- **R3. Web API Integration (Haptics & Fetch)**:
  - `fetch('POST /trigger-pipeline')` when button is tapped.
  - Haptics: `navigator.vibrate([100, 100, 100])` for success (HTTP 202).
  - Haptics: `navigator.vibrate([500, 200, 500])` for conflict/error (HTTP 409 or network error).
  - Visual feedback: Toast/status message indicating job ID, accepted state, busy state, or connection error.

## Workflow Phases
1. **Phase 0: Survey & Spec Mining** (Spawn 3 Explorers / Spec Miners in parallel).
2. **Phase 1: Project Scope & Architecture Update** (Merge survey reports, update `PROJECT.md` & `TEST_INFRA.md`).
3. **Phase 2: Milestone Execution**:
   - Milestone A: PWA Frontend UI (`index.html`) with CSS/JS, meta tags, haptic vibration API integration, visual toast notifications, and mobile ergonomics.
   - Milestone B: FastAPI Backend Integration (`remote_trigger.py`) to mount and serve `index.html` at `GET /`, maintaining all existing `/trigger-pipeline`, `/status`, `/health`, `/logs` endpoints without regression.
   - Milestone C: Dual Track E2E Testing Suite (Unit, integration, and opaque-box test suites in `tests/test_remote_trigger.py` & `tests/test_pwa_frontend.py`).
4. **Phase 3: Rigorous Verification & Gate**:
   - Reviewers (2)
   - Challengers (2)
   - Forensic Auditor (1)
5. **Phase 4: Handoff & Final Reporting**.
