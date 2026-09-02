"""
FastAPI Local Daemon Bridge for Omnichannel Triage Hub.
Exposes endpoints for ADB operations, procedural screen capture, and health monitoring.
Strict compliance with Rule R16 (Absolute imports only) and Rule R18/R21/R26.
"""

import os
import time
import json
import uuid
import sqlite3
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables if .env exists (Rule R26)
load_dotenv()

from models import (
    AdbPullRequest,
    AdbPullResponse,
    CaptureScreenRequest,
    CaptureScreenResponse,
    HealthResponse,
    DeviceInfo,
    DevicesResponse,
    StagingFile,
    StagingInventoryResponse,
)
from adb_service import adb_service

# Application Startup & State
START_TIME = time.time()
STAGING_DIR = os.getenv("STAGING_DIR", "./staging")

EVENT_BUS_DB_PATH = os.getenv(
    "EVENT_BUS_DB_PATH",
    os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "unified_ops_hub_dlq.db"
        )
    )
)


def init_event_bus_db(db_path: str = EVENT_BUS_DB_PATH) -> None:
    """Ensures event_bus_jobs table and indexes exist in SQLite WAL mode."""
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with sqlite3.connect(db_path, timeout=10.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS event_bus_jobs (
                job_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'QUEUED',
                payload_json TEXT NOT NULL,
                result_json TEXT,
                error_message TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_bus_status ON event_bus_jobs (status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_bus_task_type ON event_bus_jobs (task_type);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_bus_created ON event_bus_jobs (created_at);")
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes local daemon directories and verifies dependencies."""
    os.makedirs(os.path.join(STAGING_DIR, "videos"), exist_ok=True)
    os.makedirs(os.path.join(STAGING_DIR, "screenshots"), exist_ok=True)
    init_event_bus_db()
    yield


app = FastAPI(
    title="Omnichannel Triage Hub — Local Daemon Bridge",
    description="Local bridge connecting the React Triage UI to Android Debug Bridge and procedural media streams.",
    version="1.0.0",
    lifespan=lifespan,
)

# Rule R2 / CORS Middleware configuration for React Vite Frontend (localhost:5173)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/", tags=["Root"])
def read_root() -> Dict[str, Any]:
    """Root metadata and status."""
    return {
        "service": "Omnichannel Triage Hub Local Daemon",
        "version": "1.0.0",
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def get_health() -> HealthResponse:
    """
    Returns daemon health status, ADB connectivity, detected device count, and uptime.
    """
    devices = adb_service.list_devices()
    active_serials = [d.serial for d in devices if d.state == "device"]
    adb_ver = adb_service.get_adb_version()
    uptime = time.time() - START_TIME

    return HealthResponse(
        status="ok",
        adb_connected=len(active_serials) > 0,
        device_count=len(active_serials),
        devices=active_serials,
        adb_version=adb_ver,
        mock_available=True,
        uptime_seconds=round(uptime, 2),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/devices", response_model=DevicesResponse, tags=["ADB"])
def get_devices() -> DevicesResponse:
    """
    Lists all connected Android devices discovered via ADB.
    """
    devices = adb_service.list_devices()
    return DevicesResponse(devices=devices, count=len(devices))


@app.post("/api/trigger-adb-pull", response_model=AdbPullResponse, tags=["ADB"], status_code=status.HTTP_202_ACCEPTED)
def trigger_adb_pull(request: AdbPullRequest = AdbPullRequest()) -> AdbPullResponse:
    """
    Inserts an ADB pull operation into the Centralized SQLite Event Bus for background processing.
    """
    try:
        init_event_bus_db()
        job_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = request.model_dump()

        with sqlite3.connect(EVENT_BUS_DB_PATH, timeout=10.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute(
                """
                INSERT INTO event_bus_jobs (
                    job_id, task_type, status, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, "ADB_PULL", "QUEUED", json.dumps(payload), now_iso, now_iso)
            )
            conn.commit()

        return AdbPullResponse(
            success=True,
            status="in_progress",
            message=f"Job queued in SQLite Event Bus with ID: {job_id}",
            task_id=str(job_id),
            error=None
        )
    except Exception as e:
        return AdbPullResponse(
            success=False,
            status="error",
            message=f"Failed to queue ADB pull: {str(e)}",
            error=str(e),
        )


@app.get("/api/jobs/{job_id}", tags=["Jobs"])
def get_job_status(job_id: str):
    """
    Retrieves execution status and results of an enqueued event bus job.
    """
    init_event_bus_db()
    with sqlite3.connect(EVENT_BUS_DB_PATH, timeout=10.0) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM event_bus_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        job_data = dict(row)
        if job_data.get("payload_json"):
            try:
                job_data["payload"] = json.loads(job_data["payload_json"])
            except Exception:
                pass
        if job_data.get("result_json"):
            try:
                job_data["result"] = json.loads(job_data["result_json"])
            except Exception:
                pass
        return job_data


@app.get("/api/jobs", tags=["Jobs"])
def list_jobs(limit: int = 50, status_filter: Optional[str] = None):
    """
    Lists recent jobs in the event bus.
    """
    init_event_bus_db()
    with sqlite3.connect(EVENT_BUS_DB_PATH, timeout=10.0) as conn:
        conn.row_factory = sqlite3.Row
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM event_bus_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status_filter, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM event_bus_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/capture-screen", response_model=CaptureScreenResponse, tags=["ADB"])
def capture_screen(request: CaptureScreenRequest = CaptureScreenRequest()) -> CaptureScreenResponse:
    """
    Captures live screen from connected device or generates procedural 9:16 mock frame.
    """
    try:
        response = adb_service.capture_screen(request)
        return response
    except Exception as e:
        return CaptureScreenResponse(
            success=False,
            status="error",
            message=f"Screen capture failed: {str(e)}",
            error=str(e),
            width=540,
            height=960,
        )


@app.get("/api/staging", response_model=StagingInventoryResponse, tags=["Staging"])
def get_staging_inventory() -> StagingInventoryResponse:
    """
    Returns inventory of media files and screenshots currently in the staging directory.
    """
    staging_files: List[StagingFile] = []
    total_size = 0

    if os.path.exists(STAGING_DIR):
        for root, _, filenames in os.walk(STAGING_DIR):
            for fname in filenames:
                fpath = os.path.join(root, fname)
                try:
                    stat = os.stat(fpath)
                    mtime = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
                    ext = os.path.splitext(fname)[1].lower()
                    media_type = "video/mp4" if ext == ".mp4" else "image/png" if ext == ".png" else "application/octet-stream"

                    staging_files.append(StagingFile(
                        filename=fname,
                        path=os.path.abspath(fpath),
                        size_bytes=stat.st_size,
                        modified_at=mtime,
                        media_type=media_type,
                    ))
                    total_size += stat.st_size
                except OSError:
                    continue

    return StagingInventoryResponse(
        files=staging_files,
        total_size_bytes=total_size,
        count=len(staging_files),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
