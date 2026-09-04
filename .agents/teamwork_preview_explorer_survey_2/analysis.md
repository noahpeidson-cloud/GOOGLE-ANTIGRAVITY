# Investigation & Architecture Analysis: Requirement R2 (Centralized SQLite Event Bus)

**Explorer**: Explorer 2  
**Date**: 2026-08-29  
**Target Architecture**: Centralized SQLite Event Bus (`unified_ops_hub_dlq.db`) & Isolated Consumer (`media_event_bus.py`)  
**Status**: Completed Investigation & Architecture Specification  

---

## 1. Executive Summary

This report delivers a comprehensive investigation into Requirement R2 (Centralized SQLite Event Bus) and Requirement R3 (Universal ML Telemetry) for the Antigravity IDE Component Unification project.

### Core Objectives Examined:
1. **FastAPI Local Daemon**: Analyzed existing implementations in `omnichannel_triage_hub/local_daemon/main.py`, `local_daemon/main.py`, and `unified_ops_hub/gateway/app.py`.
2. **React API Client**: Analyzed `omnichannel_triage_hub/frontend/src/lib/api.ts` and `unified_ops_hub/dashboard/src/lib/api.ts`, detailing how UI components dispatch operations and handle graceful offline fallback.
3. **Database & Queue Architecture**: Inspected `unified_ops_hub_dlq.db` (552 KB), detailing existing `dlq_incidents` table schema, WAL configuration, and specified the unified `event_bus_jobs` schema.
4. **Control Plane Guardrail**: Inspected `daemon_orchestrator.py` (68 lines), establishing the strict boundary to ensure zero modifications are made to `daemon_orchestrator.py`.
5. **Isolated Consumer Design**: Designed `media_event_bus.py`, a robust polling daemon that processes asynchronous background jobs (ADB pulls, media workflow, screen captures) using SQLite transactions and routes failures to DLQ.
6. **Cross-Session Safety Matrix**: Verified strict zero-touch isolation for `quick_share_ai_loop/`, `video_reviewer.html`, `daemon_orchestrator.py`, and `mastermind_agent.py`.

---

## 2. FastAPI Local Daemon Architecture & Endpoints Analysis

### 2.1 Omnichannel Triage Hub Daemon (`omnichannel_triage_hub/local_daemon/main.py`)
- **Framework & Port**: FastAPI on `http://127.0.0.1:8000` (or `localhost:8000`).
- **Middleware**: CORS enabled for `http://localhost:5173`, `http://localhost:3000`, and `*`.
- **Existing Endpoints**:
  | Route | Method | Request Model | Response Model | Description & Current Behavior |
  |---|---|---|---|---|
  | `/` | `GET` | None | Dict | Returns service metadata, version `1.0.0`, status `online`. |
  | `/api/health` | `GET` | None | `HealthResponse` | Checks ADB connectivity (`adb version`, active devices count), daemon uptime. |
  | `/api/devices` | `GET` | None | `DevicesResponse` | Executes `adb devices -l` to return connected Android serials. |
  | `/api/trigger-adb-pull` | `POST` | `AdbPullRequest` | `AdbPullResponse` | Currently contains an experimental psycopg connection attempting to insert into PostgreSQL `event_queue` (lines 114-150), which fails if Postgres is offline or unconfigured. |
  | `/api/capture-screen` | `POST` | `CaptureScreenRequest` | `CaptureScreenResponse` | Captures screen via `adb exec-out screencap -p` or falls back to procedural 9:16 PIL image. |
  | `/api/staging` | `GET` | None | `StagingInventoryResponse` | Lists media files in `./staging` directory. |

### 2.2 Root Local Daemon (`local_daemon/main.py`)
- Title: "Antigravity Control Plane - Celery Edition"
- Route: `POST /api/jobs/media` accepting `JobPayload(task_type, target_file, parameters)`
- Legacy state: Offloaded to Celery/Redis (`process_media_worker.delay`). Celery and Redis create external broker dependencies that are fragile on local dev environments without Docker/Redis server running.

### 2.3 Unified Ops Hub Gateway (`unified_ops_hub/gateway/app.py`)
- Contains full domain routers (`/api/v1/health`, `/api/v1/sports`, `/api/v1/media`, `/api/v1/ml`, `/api/v1/dlq`, `/api/v1/agent`, `/api/v1/viral`).
- Integrated with `DLQManager` and `PortManager`.
- Exposes `POST /api/v1/dlq/incidents`, `/api/v1/dlq/retry/{incident_id}`, `/api/v1/simulate-crash`.

---

## 3. Frontend API Client & Calling Flow (`api.ts`)

### 3.1 Omnichannel Triage Hub (`omnichannel_triage_hub/frontend/src/lib/api.ts`)
- **Base URL Resolution**: Defaults to `http://localhost:8000` or `import.meta.env.VITE_DAEMON_API_URL`.
- **Key Functions**:
  - `triggerAdbPull(options: AdbPullOptions)`:
    - Sends `POST /api/trigger-adb-pull` with payload:
      ```json
      {
        "device_id": null,
        "source_path": "/sdcard/DCIM/Camera",
        "destination_path": "./staging/videos",
        "file_pattern": "*.mp4",
        "limit": 10,
        "mock": false,
        "run_in_background": false
      }
      ```
    - Timeout: 4000ms via `fetchWithTimeout`.
    - Fallback: On network error or timeout, simulates successful pull of `20260819_213606.mp4` (538 MB clip) and returns `is_fallback: true`.
  - `captureScreen(options: CaptureScreenOptions)`:
    - Sends `POST /api/capture-screen`.
    - Fallback: Returns procedural SVG poster frame (`FALLBACK_POSTER_FRAME`).
  - `getHealth()`, `getDevices()`, `getStagingInventory()`.

### 3.2 Unified Ops Hub Dashboard (`unified_ops_hub/dashboard/src/lib/api.ts`)
- `renderMediaVideo(payload: RenderRequest)`: Calls `POST http://127.0.0.1:8000/api/jobs/media` with `task_type: 'TASK_MEDIA_WORKFLOW'`.
- Interacts with `/api/v1/dlq/*` to list and retry dead-letter queue incidents.

---

## 4. SQLite Event Bus & DLQ Schema Analysis (`unified_ops_hub_dlq.db`)

### 4.1 Database Location & Properties
- Primary Location: `G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub_dlq.db`
- Current File Size: 552,960 bytes
- SQLite Pragma Configuration:
  - `PRAGMA journal_mode=WAL;`
  - `PRAGMA busy_timeout=5000;`
  - `PRAGMA synchronous=NORMAL;`

### 4.2 Existing Schema: `dlq_incidents`
```sql
CREATE TABLE dlq_incidents (
    incident_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    source_service TEXT NOT NULL,
    error_category TEXT NOT NULL,
    error_message TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    traceback_str TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    next_retry_at TEXT,
    status TEXT NOT NULL,
    resolved_at TEXT,
    history_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_dlq_status ON dlq_incidents (status);
CREATE INDEX IF NOT EXISTS idx_dlq_service ON dlq_incidents (source_service);
```
- Current Row Count: 154 quarantined/resolved incidents.
- Managed by `unified_ops_hub.gateway.dlq_manager.DLQManager`.

### 4.3 Proposed Event Bus Table Schema: `event_bus_jobs`
To support non-disruptive, multi-process event queueing without colliding with `dlq_incidents`, we introduce `event_bus_jobs` into `unified_ops_hub_dlq.db`:
```sql
CREATE TABLE IF NOT EXISTS event_bus_jobs (
    job_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,          -- e.g. 'ADB_PULL', 'MEDIA_WORKFLOW', 'SCREEN_CAPTURE', 'VIDEO_TRIM'
    payload_json TEXT NOT NULL,       -- JSON serialized task arguments
    status TEXT NOT NULL DEFAULT 'QUEUED', -- 'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED'
    result_json TEXT,                 -- JSON output upon success
    error_message TEXT,               -- Error message if failed
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    created_at TEXT NOT NULL,         -- ISO-8601 UTC
    updated_at TEXT NOT NULL,         -- ISO-8601 UTC
    completed_at TEXT                 -- ISO-8601 UTC
);

CREATE INDEX IF NOT EXISTS idx_event_bus_status ON event_bus_jobs (status);
CREATE INDEX IF NOT EXISTS idx_event_bus_task_type ON event_bus_jobs (task_type);
CREATE INDEX IF NOT EXISTS idx_event_bus_created ON event_bus_jobs (created_at);
```

---

## 5. Control Plane Guardrail & `daemon_orchestrator.py` Deep Dive

### 5.1 Inspection of `daemon_orchestrator.py`
```python
# G:\My Drive\GOOGLE ANTIGRAVITY\daemon_orchestrator.py
import os, sys, time, sqlite3
sys.path.append(os.path.join(os.path.dirname(__file__), "media_pipeline", "design_arm"))
from batch_processor import process_media_edit

DB_FILE = r"g:\My Drive\GOOGLE ANTIGRAVITY\content_creation\editing_booth\booth_telemetry.db"
STATE_FILE = r"g:\My Drive\GOOGLE ANTIGRAVITY\daemon_state.txt"

def get_last_processed_id(): ...
def set_last_processed_id(last_id): ...
def run_headless_daemon():
    # Polls SELECT id, filename, tags, notes, in_point, out_point, bounding_box FROM edits WHERE id > ?
    # Calls process_media_edit(...)
    # Updates daemon_state.txt
```

### 5.2 Strict Cross-Session Boundary
- `daemon_orchestrator.py` is actively maintained and being refactored by the Control Plane engineering session.
- **Rule**: Absolutely ZERO modifications to `daemon_orchestrator.py`, `daemon_state.txt`, or `content_creation\editing_booth\booth_telemetry.db` schemas.
- `media_event_bus.py` will run as a completely independent daemon process interacting exclusively with `unified_ops_hub_dlq.db`.

---

## 6. Architecture & Implementation Plan for `media_event_bus.py`

### 6.1 Daemon Process Lifecycle
1. **Startup**:
   - Initializes connection to `unified_ops_hub_dlq.db` with WAL mode and busy timeout (5.0s).
   - Ensures `event_bus_jobs` and `dlq_incidents` tables exist.
   - Attaches `DLQManager` instance for error quarantine.
   - Imports telemetry hook from `base_agent.py`.
2. **Worker Polling Loop**:
   - Atomic job acquisition:
     ```python
     with sqlite_conn:
         cursor.execute("""
             SELECT job_id, task_type, payload_json, retry_count, max_retries 
             FROM event_bus_jobs 
             WHERE status = 'QUEUED' 
             ORDER BY created_at ASC 
             LIMIT 1
         """)
         row = cursor.fetchone()
         if row:
             cursor.execute(
                 "UPDATE event_bus_jobs SET status = 'PROCESSING', updated_at = ? WHERE job_id = ?",
                 (datetime.now(timezone.utc).isoformat(), row["job_id"])
             )
     ```
3. **Task Handlers**:
   - `ADB_PULL` / `adb_pull`: Executes `AdbService().trigger_pull(AdbPullRequest(**payload))`.
   - `SCREEN_CAPTURE` / `capture_screen`: Executes `AdbService().capture_screen(CaptureScreenRequest(**payload))`.
   - `MEDIA_WORKFLOW` / `TASK_MEDIA_WORKFLOW`: Executes headless media pipeline processing and FFmpeg proxy rendering.
4. **Completion & Telemetry**:
   - On success: Updates `event_bus_jobs` status to `COMPLETED`, saves `result_json`, sets `completed_at`.
   - Fires `@hooks.post_turn` telemetry via `base_agent.py` to record operational telemetry.
5. **Failure & DLQ Isolation**:
   - If an unhandled exception occurs:
     - Updates `event_bus_jobs` status to `FAILED`.
     - Logs incident into `dlq_incidents` via `DLQManager.record_failure()`.
     - Writes JSON audit artifact in `quarantine/dlq_<incident_id>.json`.
6. **Graceful Shutdown**:
   - Handles `SIGINT` (Ctrl+C) and `SIGTERM`, completing active in-flight job before exiting cleanly.

---

## 7. Refactoring Plan for FastAPI Local Daemon

### 7.1 Fix in `omnichannel_triage_hub/local_daemon/main.py`
- Replace broken `psycopg` PostgreSQL insert with SQLite event bus insertion:
  ```python
  import sqlite3
  import json
  import uuid
  from datetime import datetime, timezone

  DB_PATH = os.getenv("EVENT_BUS_DB_PATH", os.path.abspath(r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub_dlq.db"))

  @app.post("/api/trigger-adb-pull", response_model=AdbPullResponse, tags=["ADB"], status_code=status.HTTP_202_ACCEPTED)
  def trigger_adb_pull(request: AdbPullRequest = AdbPullRequest()) -> AdbPullResponse:
      try:
          job_id = str(uuid.uuid4())
          now_iso = datetime.now(timezone.utc).isoformat()
          payload = request.model_dump()
          
          # Insert into centralized SQLite event bus
          with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
              conn.execute("PRAGMA journal_mode=WAL;")
              conn.execute(
                  """
                  INSERT INTO event_bus_jobs (
                      job_id, task_type, payload_json, status, created_at, updated_at
                  ) VALUES (?, ?, ?, ?, ?, ?)
                  """,
                  (job_id, "ADB_PULL", json.dumps(payload), "QUEUED", now_iso, now_iso)
              )
              conn.commit()

          return AdbPullResponse(
              success=True,
              status="in_progress",
              message=f"Job queued in Centralized SQLite Event Bus with ID: {job_id}",
              task_id=job_id,
              error=None
          )
      except Exception as e:
          return AdbPullResponse(
              success=False,
              status="error",
              message=f"Failed to queue ADB pull: {str(e)}",
              error=str(e),
          )
  ```
- Add job status polling endpoint:
  ```python
  @app.get("/api/jobs/{job_id}", tags=["Jobs"])
  def get_job_status(job_id: str):
      with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
          conn.row_factory = sqlite3.Row
          row = conn.execute("SELECT * FROM event_bus_jobs WHERE job_id = ?", (job_id,)).fetchone()
          if not row:
              raise HTTPException(status_code=404, detail="Job not found")
          return dict(row)
  ```

---

## 8. Cross-Session Safety Matrix

| Component / Path | Status / Owner | Guardrail Action |
|---|---|---|
| `quick_share_ai_loop/` | Music Baptism Image Concepts Session | **LOCKED (0 Modifications)** — Read-only verification only. |
| `video_reviewer.html` | ML Video Editing Styles Session | **LOCKED (0 Modifications)** — No UI or file changes. |
| `daemon_orchestrator.py` | Control Plane Orchestrator Session | **LOCKED (0 Modifications)** — `media_event_bus.py` is strictly isolated. |
| `mastermind_agent.py` | Active Core Agent Session | **LOCKED (0 Modifications)** — Do not inject telemetry hook. |
| `.agents/context_engine/` | Active Context Engine Session | **LOCKED (0 Modifications)** — Do not modify. |
| `unified_ops_hub_dlq.db` | Shared DLQ & Event Bus | Extended with `event_bus_jobs` table; `dlq_incidents` table preserved. |
| `base_agent.py` | Teamwork Unification (New) | Created to house shared `@hooks.post_turn` telemetry extracted from `deployment_agent.py`. |
| `media_event_bus.py` | Teamwork Unification (New) | Created as the standalone consumer for SQLite event bus. |

---

## 9. Verification & Test Plan

1. **Schema Verification**:
   - Programmatically verify `unified_ops_hub_dlq.db` contains both `dlq_incidents` and `event_bus_jobs` tables with indexes.
2. **API Endpoint Verification**:
   - `POST /api/trigger-adb-pull` inserts a job row with `status = 'QUEUED'`.
   - `GET /api/jobs/{job_id}` returns job status and metadata.
3. **Consumer Polling Verification**:
   - Run `media_event_bus.py` against a queued job.
   - Verify job transitions `QUEUED` -> `PROCESSING` -> `COMPLETED`.
   - Verify output `result_json` contains `pulled_files` and byte counts.
4. **Crash & DLQ Verification**:
   - Submit a malformed job or simulated failure.
   - Verify `media_event_bus.py` catches the error, sets job status `FAILED`, and inserts incident into `dlq_incidents`.
5. **Guardrail Audit**:
   - Verify `git status` / file diffs confirm 0 modified files in `quick_share_ai_loop/`, 0 modifications to `video_reviewer.html`, and 0 modifications to `daemon_orchestrator.py`.
