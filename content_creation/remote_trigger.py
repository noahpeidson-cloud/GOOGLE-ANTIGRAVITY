"""
remote_trigger.py - FastAPI Zero-Touch Remote Trigger Server for EDM Content Creation
Part of Track 2: Content Creation & Media Engineering Pipeline

Exposes RESTful endpoints for mobile Tasker widgets, webhooks, and automation bridges:
- POST /trigger-pipeline: Asynchronously launches orchestrator pipeline (from-device, auto-drop).
- GET /status: Returns state of running/recent jobs and telemetry.
- GET /status/{job_id}: Returns telemetry for a specific job ID.
- GET /health: Verifies system health, disk space, ADB, FFmpeg, and FFprobe readiness.
- GET /logs: Fetches ring-buffered log lines with optional filtering.
- POST /cancel: Gracefully terminates active subprocess.
"""

import argparse
import asyncio
from collections import deque
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Any, Deque, Dict, List, Optional, Tuple, Union
import uuid

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
import uvicorn

# Track 2 configuration and utility helpers import
try:
    from config import BrandType, EventTier, ReframeMode
except ImportError:
    BrandType = None
    EventTier = None
    ReframeMode = None

try:
    from resolve_handoff import (
        create_resolve_timeline,
        DaVinciResolveHandoffEngine,
        ResolveHandoffConfig,
        ResolveHandoffResult,
        ResolveScriptError,
    )
except ImportError:
    create_resolve_timeline = None
    DaVinciResolveHandoffEngine = None
    ResolveHandoffConfig = None
    ResolveHandoffResult = None
    ResolveScriptError = Exception

try:
    from ingest_assets import find_binary
except ImportError:
    def find_binary(name: str, custom_path: Optional[str] = None, env_var: Optional[str] = None) -> Optional[Path]:
        which_p = shutil.which(name)
        return Path(which_p).resolve() if which_p else None

try:
    from samsung_ingest import find_adb_binary
except ImportError:
    find_adb_binary = None

# Configure logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [remote_trigger] %(message)s")
logger = logging.getLogger("remote_trigger")


# ============================================================================
# PYDANTIC V2 SCHEMAS & MODELS
# ============================================================================

class JobState(str, Enum):
    """Execution state machine for pipeline jobs."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineTriggerRequest(BaseModel):
    """Payload schema for triggering the automated pipeline."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    festival: Optional[str] = Field(default=None, description="Festival or event name")
    event: Optional[str] = Field(default="Concert", description="Event or festival name")
    artist: Optional[str] = Field(default="Artist", description="DJ or artist name")
    track: str = Field(default="ID", description="Track title or ID")
    genre: str = Field(default="house", description="EDM subgenre for pacing")
    brand: str = Field(default="music_baptism", description="Brand umbrella (laser_baptism / music_baptism)")
    tier: str = Field(default="pillar_a_stadium_arena", description="Event tier pillar")
    from_device: bool = Field(default=True, description="Pull take from Samsung S26 Ultra via ADB")
    device_serial: Optional[str] = Field(default=None, description="Explicit ADB device serial")
    input_file: Optional[str] = Field(default=None, description="Explicit local input video file")
    auto_drop: bool = Field(default=True, description="Enable Librosa 30s RMS drop detection")
    drop_duration: float = Field(default=30.0, ge=5.0, le=59.0, description="Drop window duration in seconds")
    start_time: Optional[float] = Field(default=None, ge=0.0, description="Manual start time override")
    duration: Optional[float] = Field(default=None, ge=5.0, le=59.0, description="Manual duration override")
    reframe_mode: str = Field(default="center_crop", description="Reframe mode (center_crop / blur_pad / offset_crop)")
    publish_youtube: bool = Field(default=False, description="Trigger YouTube Data API v3 upload")
    auto_promote: bool = Field(default=False, description="Auto-promote from unlisted to public")
    poll_timeout: Optional[float] = Field(default=300.0, ge=10.0, description="Content ID polling timeout in seconds")
    client_secrets: Optional[str] = Field(default=None, description="Path to client_secret.json")
    token_path: Optional[str] = Field(default=None, description="Path to token.json")
    dry_run: bool = Field(default=False, description="Simulate without executing file I/O or ffmpeg")

    @property
    def resolved_event(self) -> str:
        """Resolves festival/event name with fallbacks."""
        if self.festival and self.festival.strip():
            return self.festival.strip()
        if self.event and self.event.strip():
            return self.event.strip()
        return "Concert"

    @property
    def resolved_artist(self) -> str:
        """Resolves artist name with fallbacks."""
        return self.artist.strip() if (self.artist and self.artist.strip()) else "Artist"


class TriggerResponse(BaseModel):
    """Successful trigger response (<50ms HTTP 202 Accepted)."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    status: str = Field(default="accepted", description="Status string ('accepted')")
    job_id: str = Field(description="Unique job execution identifier")
    message: str = Field(default="Pipeline job accepted and launched in background")
    command: List[str] = Field(description="Command line arguments executed")
    started_at: str = Field(description="ISO timestamp when job was accepted")
    created_at: Optional[str] = Field(default=None, description="Alias for started_at")


class ConflictResponse(BaseModel):
    """Response returned when a job is already in progress (HTTP 409 Conflict)."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    status: str = Field(default="conflict", description="Status string ('conflict')")
    error: str = Field(default="Pipeline execution is already in progress")
    current_job_id: Optional[str] = Field(default=None, description="Active job ID")
    started_at: Optional[str] = Field(default=None, description="Active job start time")
    elapsed_seconds: Optional[float] = Field(default=None, description="Elapsed seconds for active job")


class JobTelemetry(BaseModel):
    """Detailed telemetry for a single pipeline job."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    job_id: str = Field(description="Unique job execution identifier")
    state: JobState = Field(description="Current job execution state")
    command: List[str] = Field(description="Command line arguments")
    started_at: Optional[str] = Field(default=None, description="Start timestamp")
    completed_at: Optional[str] = Field(default=None, description="Completion timestamp")
    elapsed_seconds: float = Field(default=0.0, description="Elapsed run duration in seconds")
    exit_code: Optional[int] = Field(default=None, description="Process exit code")
    error_summary: Optional[str] = Field(default=None, description="Summary of any execution errors")
    params: Dict[str, Any] = Field(default_factory=dict, description="Original request parameters")


class StatusResponse(BaseModel):
    """Overall daemon and job status summary."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    state: JobState = Field(default=JobState.IDLE, description="Current daemon state")
    is_running: bool = Field(default=False, description="True if a pipeline job is currently executing")
    current_job_id: Optional[str] = Field(default=None, description="Active job ID if running")
    total_jobs_run: int = Field(default=0, description="Total number of jobs executed")
    active_job: Optional[JobTelemetry] = Field(default=None, description="Telemetry for active job")
    last_job: Optional[JobTelemetry] = Field(default=None, description="Telemetry for most recent job")
    recent_jobs: List[JobTelemetry] = Field(default_factory=list, description="List of recent job telemetry records")


class LogEntry(BaseModel):
    """Structured log record."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    timestamp: str = Field(description="ISO timestamp")
    level: str = Field(default="INFO", description="Log level (INFO, WARNING, ERROR, DEBUG)")
    message: str = Field(description="Log line content")
    job_id: Optional[str] = Field(default=None, description="Associated job ID if applicable")


class LogsResponse(BaseModel):
    """Log buffer retrieval response."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    job_id: Optional[str] = Field(default=None, description="Target job ID filter")
    total_lines: int = Field(description="Total log lines returned")
    logs: List[str] = Field(default_factory=list, description="Formatted log strings")
    entries: List[LogEntry] = Field(default_factory=list, description="Structured log records")


class HealthResponse(BaseModel):
    """System health check and dependency readiness report."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    status: str = Field(description="Overall health status ('healthy', 'degraded', 'unhealthy')")
    service: str = Field(default="content_creation.remote_trigger", description="Service identifier")
    version: str = Field(default="1.0.0", description="Service version")
    is_pipeline_running: bool = Field(description="Whether a pipeline job is currently running")
    adb_available: bool = Field(description="Whether adb binary is discovered")
    ffmpeg_available: bool = Field(description="Whether ffmpeg binary is discovered")
    ffprobe_available: bool = Field(description="Whether ffprobe binary is discovered")
    free_disk_space_bytes: Optional[int] = Field(default=None, description="Free disk space in bytes")
    free_disk_space_gb: Optional[float] = Field(default=None, description="Free disk space in gigabytes")
    workspace_root: str = Field(description="Resolved workspace directory path")
    timestamp: str = Field(description="Current ISO timestamp")


class CancelResponse(BaseModel):
    """Response returned upon cancelling an active job."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    status: str = Field(default="cancelled", description="Cancellation status")
    job_id: str = Field(description="ID of the cancelled job")
    message: str = Field(description="Status message")
    terminated: bool = Field(default=True, description="Whether process termination was signaled")


class PendingClipItem(BaseModel):
    """Individual take / proxy clip item ready for browser review."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    clip_id: str = Field(description="Unique clip or take identifier")
    canonical_filename: str = Field(description="Standardized filename")
    raw_path: str = Field(description="Relative or absolute path to pristine 4K raw video")
    proxy_path: Optional[str] = Field(default=None, description="Path to 720p proxy video")
    proxy_url: Optional[str] = Field(default=None, description="Stream URL for 720p proxy")
    wav_path: Optional[str] = Field(default=None, description="Path to extracted PCM WAV audio")
    wav_url: Optional[str] = Field(default=None, description="URL to access WAV audio")
    duration_seconds: float = Field(default=30.0, description="Total clip duration in seconds")
    detected_drop_start: float = Field(default=0.0, description="AI detected drop start timestamp in seconds")
    detected_drop_duration: float = Field(default=30.0, description="AI detected drop duration in seconds")
    detected_drop_end: float = Field(default=30.0, description="AI detected drop end timestamp in seconds")
    festival: str = Field(default="Concert", description="Festival or event name")
    artist: str = Field(default="Artist", description="Artist or DJ name")
    track: str = Field(default="ID", description="Track title or ID")
    tier: Optional[str] = Field(default="pillar_a_stadium_arena", description="Event tier")
    brand: Optional[str] = Field(default="music_baptism", description="Brand umbrella")
    status: str = Field(default="awaiting_review", description="Review status")
    created_at: Optional[str] = Field(default=None, description="Creation ISO timestamp")


class PendingClipsResponse(BaseModel):
    """List of pending takes / proxies awaiting human review."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    total: int = Field(description="Total count of pending clips found")
    clips: List[PendingClipItem] = Field(default_factory=list, description="List of pending clip records")


class ApproveRenderRequest(BaseModel):
    """Payload schema for approving trim bounds and triggering DaVinci Resolve handoff."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    clip_id: Optional[str] = Field(default=None, description="Clip ID being approved")
    raw_file_path: Optional[str] = Field(default=None, description="Path to untouched 4K raw video")
    raw_clip_path: Optional[str] = Field(default=None, description="Alias for raw_file_path")
    start_time: float = Field(default=0.0, ge=0.0, description="Approved start trim timestamp in seconds")
    end_time: Optional[float] = Field(default=None, ge=0.0, description="Approved end trim timestamp in seconds")
    duration: Optional[float] = Field(default=30.0, ge=1.0, le=120.0, description="Approved clip duration in seconds")
    fps: float = Field(default=60.0, ge=1.0, le=240.0, description="Timeline framerate")
    width: int = Field(default=1080, description="Timeline width in pixels")
    height: int = Field(default=1920, description="Timeline height in pixels")
    project_name: Optional[str] = Field(default=None, description="Target DaVinci Resolve project name")
    timeline_name: Optional[str] = Field(default=None, description="Target DaVinci Resolve timeline name")
    festival: Optional[str] = Field(default="Concert", description="Festival metadata")
    artist: Optional[str] = Field(default="Artist", description="Artist metadata")
    track: Optional[str] = Field(default="ID", description="Track metadata")
    brand: Optional[str] = Field(default="music_baptism", description="Brand umbrella")
    tier: Optional[str] = Field(default="pillar_a_stadium_arena", description="Event tier")
    dry_run: bool = Field(default=False, description="Simulate without executing Resolve handoff")
    auto_save: bool = Field(default=True, description="Auto-save Resolve project")

    @property
    def resolved_raw_path(self) -> Optional[str]:
        return self.raw_file_path or self.raw_clip_path


class ApproveRenderResponse(BaseModel):
    """Telemetry response for DaVinci Resolve handoff dispatch."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    status: str = Field(description="Execution status ('accepted', 'success', 'resolve_unavailable', etc.)")
    job_id: str = Field(description="Unique job execution identifier")
    message: str = Field(description="User-facing status message")
    project_name: str = Field(description="Target DaVinci Resolve project name")
    timeline_name: str = Field(description="Target DaVinci Resolve timeline name")
    start_time: float = Field(description="Approved start time in seconds")
    end_time: float = Field(description="Approved end time in seconds")
    duration: float = Field(description="Approved duration in seconds")
    start_frame: Optional[int] = Field(default=None, description="Calculated start frame index")
    end_frame: Optional[int] = Field(default=None, description="Calculated end frame index")
    duration_frames: Optional[int] = Field(default=None, description="Calculated duration in frames")
    fps: float = Field(default=60.0, description="Framerate")
    timeline_resolution: str = Field(default="1080x1920", description="Timeline resolution")
    raw_file_path: Optional[str] = Field(default=None, description="Resolved raw 4K file path")
    telemetry: Dict[str, Any] = Field(default_factory=dict, description="Execution telemetry")


# Schema backward-compatibility aliases
PipelineTriggerResponse = TriggerResponse
PipelineConflictResponse = ConflictResponse
JobDetail = JobTelemetry
JobStatusResponse = StatusResponse
CancelJobResponse = CancelResponse
ResolveHandoffRequest = ApproveRenderRequest
ResolveHandoffResponse = ApproveRenderResponse


# ============================================================================
# COMMAND BUILDER LOGIC
# ============================================================================

def build_orchestrator_command(
    request: PipelineTriggerRequest,
    workspace_root: Path,
    python_bin: str = sys.executable,
) -> List[str]:
    """Constructs the canonical CLI invocation list for orchestrator.py pipeline."""
    orchestrator_script = workspace_root / "orchestrator.py"

    resolved_event = request.resolved_event if hasattr(request, "resolved_event") else (request.festival or request.event or "Concert")
    resolved_artist = request.resolved_artist if hasattr(request, "resolved_artist") else (request.artist or "Artist")

    cmd: List[str] = [
        python_bin,
        str(orchestrator_script),
        "--target-dir",
        str(workspace_root),
        "pipeline",
        "--event",
        str(resolved_event),
        "--artist",
        str(resolved_artist),
        "--track",
        str(request.track),
        "--genre",
        str(request.genre),
        "--brand",
        str(request.brand),
        "--tier",
        str(request.tier),
        "--reframe-mode",
        str(request.reframe_mode),
        "--drop-duration",
        str(request.drop_duration),
    ]

    if request.from_device:
        cmd.append("--from-device")
        if request.device_serial:
            cmd.extend(["--device", str(request.device_serial)])
    elif request.input_file:
        cmd.extend(["--input", str(request.input_file)])

    if request.auto_drop:
        cmd.append("--auto-drop")

    if request.start_time is not None:
        cmd.extend(["--start-time", str(request.start_time)])

    if request.duration is not None:
        cmd.extend(["--duration", str(request.duration)])

    if request.publish_youtube:
        cmd.append("--publish-youtube")
        if request.auto_promote:
            cmd.append("--auto-promote")
        if request.poll_timeout is not None:
            cmd.extend(["--poll-timeout", str(request.poll_timeout)])
        if request.client_secrets is not None:
            cmd.extend(["--client-secrets", str(request.client_secrets)])
        if request.token_path is not None:
            cmd.extend(["--token-path", str(request.token_path)])

    if request.dry_run:
        cmd.append("--dry-run")

    return cmd


# ============================================================================
# PIPELINE JOB MANAGER & ASYNC PROCESS HANDLER
# ============================================================================

class JobRecord:
    """Internal tracker for an executing or historical pipeline job."""

    def __init__(self, job_id: str, command: List[str], params: Dict[str, Any]):
        self.job_id = job_id
        self.command = command
        self.params = params
        self.state = JobState.IDLE
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.exit_code: Optional[int] = None
        self.error_summary: Optional[str] = None

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.now(timezone.utc)
        return round((end - self.started_at).total_seconds(), 2)

    def to_telemetry(self) -> JobTelemetry:
        return JobTelemetry(
            job_id=self.job_id,
            state=self.state,
            command=self.command,
            started_at=self.started_at.isoformat() if self.started_at else None,
            completed_at=self.completed_at.isoformat() if self.completed_at else None,
            elapsed_seconds=self.elapsed_seconds,
            exit_code=self.exit_code,
            error_summary=self.error_summary,
            params=self.params,
        )

    to_detail = to_telemetry


class PipelineJobManager:
    """Manages lifecycle, single-run concurrency locking, logs, and execution for pipeline jobs."""

    def __init__(self, workspace_root: Path, max_history: int = 50, max_logs: int = 2000):
        self.workspace_root = workspace_root.resolve()
        self.max_history = max_history
        self.max_logs = max_logs
        self._lock = asyncio.Lock()
        self._active_job: Optional[JobRecord] = None
        self._active_process: Optional[asyncio.subprocess.Process] = None
        self._active_task: Optional[asyncio.Task] = None
        self._job_history: List[JobRecord] = []
        self._log_buffer: Deque[LogEntry] = deque(maxlen=max_logs)
        self._total_jobs_count: int = 0

    @property
    def is_running(self) -> bool:
        return self._active_job is not None and self._active_job.state == JobState.RUNNING

    @property
    def current_job_id(self) -> Optional[str]:
        return self._active_job.job_id if self.is_running and self._active_job else None

    @property
    def total_jobs_run(self) -> int:
        return self._total_jobs_count

    def get_active_job(self) -> Optional[JobRecord]:
        return self._active_job if self.is_running else None

    def get_last_job(self) -> Optional[JobRecord]:
        if self._active_job:
            return self._active_job
        if self._job_history:
            return self._job_history[0]
        return None

    def find_job(self, job_id: str) -> Optional[JobRecord]:
        if self._active_job and self._active_job.job_id == job_id:
            return self._active_job
        for j in self._job_history:
            if j.job_id == job_id:
                return j
        return None

    def _add_log(self, entry: LogEntry) -> None:
        self._log_buffer.append(entry)

    def get_logs(self, tail: Optional[int] = None, job_id: Optional[str] = None) -> List[LogEntry]:
        entries = list(self._log_buffer)
        if job_id:
            entries = [e for e in entries if e.job_id == job_id]
        if tail is not None and tail > 0:
            return entries[-tail:]
        return entries

    async def trigger(self, request: PipelineTriggerRequest) -> Tuple[bool, Union[TriggerResponse, ConflictResponse]]:
        """Attempts to acquire the single-job mutex and spawn background execution."""
        async with self._lock:
            if self.is_running and self._active_job is not None:
                active = self._active_job
                return False, ConflictResponse(
                    status="conflict",
                    error="Pipeline execution is already in progress",
                    current_job_id=active.job_id,
                    started_at=active.started_at.isoformat() if active.started_at else "",
                    elapsed_seconds=active.elapsed_seconds,
                )

            self._total_jobs_count += 1
            now_utc = datetime.now(timezone.utc)
            job_id = f"job_{now_utc.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            cmd = build_orchestrator_command(request, self.workspace_root)
            job = JobRecord(job_id=job_id, command=cmd, params=request.model_dump())
            job.state = JobState.RUNNING
            job.started_at = now_utc
            self._active_job = job

            started_iso = now_utc.isoformat()
            self._add_log(LogEntry(
                timestamp=started_iso,
                level="INFO",
                message=f"[SYSTEM] Job {job_id} accepted. Command: {' '.join(cmd)}",
                job_id=job_id,
            ))

            # Spawn background execution task
            self._active_task = asyncio.create_task(self._run_subprocess(job))

            return True, TriggerResponse(
                status="accepted",
                job_id=job_id,
                message="Pipeline job accepted and launched in background",
                command=cmd,
                started_at=started_iso,
                created_at=started_iso,
            )

    async def _run_subprocess(self, job: JobRecord) -> None:
        """Executes the orchestrator subprocess asynchronously and streams stdout/stderr."""
        try:
            logger.info("Executing orchestrator command for job %s: %s", job.job_id, " ".join(job.command))
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            proc = await asyncio.create_subprocess_exec(
                *job.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_root),
                env=env,
            )
            self._active_process = proc

            async def read_stream(stream: Optional[asyncio.StreamReader], prefix: str = "", level: str = "INFO"):
                if stream is None:
                    return
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                    formatted = f"{prefix}{text}" if prefix else text
                    entry = LogEntry(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        level=level,
                        message=formatted,
                        job_id=job.job_id,
                    )
                    self._add_log(entry)
                    if level == "ERROR":
                        logger.warning("[%s] %s", job.job_id, formatted)
                    else:
                        logger.debug("[%s] %s", job.job_id, formatted)

            # Ingest stdout and stderr concurrently without blocking the event loop
            await asyncio.gather(
                read_stream(proc.stdout, prefix="", level="INFO"),
                read_stream(proc.stderr, prefix="[STDERR] ", level="ERROR"),
            )

            exit_code = await proc.wait()
            job.exit_code = exit_code
            job.completed_at = datetime.now(timezone.utc)

            if exit_code == 0:
                job.state = JobState.COMPLETED
                logger.info("Job %s completed successfully in %.2fs", job.job_id, job.elapsed_seconds)
                self._add_log(LogEntry(
                    timestamp=job.completed_at.isoformat(),
                    level="INFO",
                    message=f"[SYSTEM] Job {job.job_id} completed successfully (exit 0) in {job.elapsed_seconds:.2f}s",
                    job_id=job.job_id,
                ))
            else:
                job.state = JobState.FAILED
                job.error_summary = f"Subprocess exited with non-zero exit code: {exit_code}"
                logger.error("Job %s failed with exit code %d in %.2fs", job.job_id, exit_code, job.elapsed_seconds)
                self._add_log(LogEntry(
                    timestamp=job.completed_at.isoformat(),
                    level="ERROR",
                    message=f"[SYSTEM] Job {job.job_id} failed with exit code {exit_code} in {job.elapsed_seconds:.2f}s",
                    job_id=job.job_id,
                ))

        except asyncio.CancelledError:
            job.state = JobState.CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            job.error_summary = "Job execution cancelled by user request"
            logger.warning("Job %s was cancelled", job.job_id)
            self._add_log(LogEntry(
                timestamp=job.completed_at.isoformat(),
                level="WARNING",
                message=f"[SYSTEM] Job {job.job_id} cancelled via asyncio task cancellation",
                job_id=job.job_id,
            ))
        except Exception as ex:
            job.state = JobState.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_summary = str(ex)
            logger.exception("Unexpected error executing job %s: %s", job.job_id, ex)
            self._add_log(LogEntry(
                timestamp=job.completed_at.isoformat(),
                level="ERROR",
                message=f"[SYSTEM] Unexpected error executing job {job.job_id}: {ex}",
                job_id=job.job_id,
            ))
        finally:
            self._active_process = None
            if self._active_job == job:
                self._active_job = None
            self._job_history.insert(0, job)
            if len(self._job_history) > self.max_history:
                self._job_history.pop()

    async def cancel_active_job(self) -> Tuple[bool, str, Optional[str]]:
        """Gracefully terminates the active running subprocess and transitions state."""
        async with self._lock:
            if not self.is_running or self._active_job is None:
                return False, "No active pipeline job currently running", None

            proc = self._active_process
            job = self._active_job
            job_id = job.job_id

            try:
                if proc is not None:
                    proc.terminate()
                    # Allow up to 3.0s for graceful shutdown before force-kill
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=3.0)
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()
                    job.exit_code = proc.returncode

                if self._active_task and not self._active_task.done():
                    self._active_task.cancel()

                job.state = JobState.CANCELLED
                job.completed_at = datetime.now(timezone.utc)
                job.error_summary = "Process terminated via /cancel request"

                self._add_log(LogEntry(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    level="WARNING",
                    message=f"[SYSTEM] Job {job_id} cancelled and terminated via /cancel",
                    job_id=job_id,
                ))

                self._active_job = None
                self._active_process = None
                self._job_history.insert(0, job)
                if len(self._job_history) > self.max_history:
                    self._job_history.pop()

                return True, f"Successfully terminated job {job_id}", job_id
            except Exception as ex:
                return False, f"Failed to terminate process: {ex}", job_id


# ============================================================================
# PROXY MEDIA DISCOVERY & HTTP 206 RANGE STREAMING HELPERS
# ============================================================================

def discover_pending_clips(workspace_root: Path) -> List[PendingClipItem]:
    """
    Discovers pending takes and 720p proxies across workspace directories.
    Extracts festival, artist, raw path, proxy path, wav path, and AI drop timestamps.
    """
    clips_map: Dict[str, PendingClipItem] = {}
    video_exts = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}

    scan_dirs = [
        ("02_AWAITING_REVIEW", "awaiting_review"),
        ("02_IN_PROGRESS", "in_progress"),
        ("01_RAW", "raw_stored"),
        ("01_RAW_INBOX", "inbox"),
    ]

    for dir_name, state_label in scan_dirs:
        target_dir = workspace_root / dir_name
        if not target_dir.is_dir():
            continue

        for file_path in target_dir.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in video_exts:
                continue

            stem = file_path.stem
            clean_stem = re.sub(r"(_proxy_drop|_proxy|_4k|_1080p|_720p)$", "", stem, flags=re.IGNORECASE)
            clip_id = clean_stem or stem

            # Extract festival / artist / track from path hierarchy or tokens
            try:
                rel_parts = file_path.relative_to(target_dir).parts
            except ValueError:
                rel_parts = ()

            festival = "Concert"
            artist = "Artist"
            track = "ID"

            if len(rel_parts) >= 3:
                festival = rel_parts[0]
                artist = rel_parts[1]
            elif len(rel_parts) == 2:
                festival = rel_parts[0]
            else:
                tokens = clean_stem.split("_")
                if len(tokens) >= 3:
                    festival = tokens[1]
                    artist = tokens[2]
                    if len(tokens) >= 4:
                        track = tokens[3]

            # Locate matching raw file in 01_RAW
            raw_path = None
            raw_dir = workspace_root / "01_RAW"
            if raw_dir.is_dir():
                for candidate in raw_dir.rglob("*"):
                    if candidate.is_file() and candidate.suffix.lower() in video_exts:
                        if candidate.stem.startswith(clean_stem) and "_proxy" not in candidate.stem.lower():
                            try:
                                raw_path = str(candidate.relative_to(workspace_root))
                            except ValueError:
                                raw_path = str(candidate)
                            break

            if not raw_path:
                try:
                    raw_path = str(file_path.relative_to(workspace_root))
                except ValueError:
                    raw_path = str(file_path)

            # Locate matching proxy file
            proxy_path = None
            if "_proxy" in file_path.stem.lower():
                try:
                    proxy_path = str(file_path.relative_to(workspace_root))
                except ValueError:
                    proxy_path = str(file_path)
            else:
                for pdir in [workspace_root / "02_AWAITING_REVIEW", workspace_root / "01_RAW", workspace_root / "02_IN_PROGRESS"]:
                    if pdir.is_dir():
                        for pcan in pdir.rglob(f"{clean_stem}*proxy*.mp4"):
                            if pcan.is_file():
                                try:
                                    proxy_path = str(pcan.relative_to(workspace_root))
                                except ValueError:
                                    proxy_path = str(pcan)
                                break
                    if proxy_path:
                        break

            # Locate matching wav audio
            wav_path = None
            for wdir in [workspace_root / "01_RAW", workspace_root / "02_AWAITING_REVIEW", workspace_root / "02_IN_PROGRESS"]:
                if wdir.is_dir():
                    for wcan in wdir.rglob(f"{clean_stem}*.wav"):
                        if wcan.is_file():
                            try:
                                wav_path = str(wcan.relative_to(workspace_root))
                            except ValueError:
                                wav_path = str(wcan)
                            break
                if wav_path:
                    break

            proxy_url = f"/proxies/{clip_id}/video" if (proxy_path or raw_path) else None
            wav_url = f"/proxies/{clip_id}/audio" if wav_path else None

            duration = 30.0
            drop_start = 0.0
            drop_dur = 30.0

            if clip_id not in clips_map or (proxy_path and not clips_map[clip_id].proxy_path):
                clips_map[clip_id] = PendingClipItem(
                    clip_id=clip_id,
                    canonical_filename=file_path.name,
                    raw_path=raw_path or str(file_path),
                    proxy_path=proxy_path,
                    proxy_url=proxy_url,
                    wav_path=wav_path,
                    wav_url=wav_url,
                    duration_seconds=duration,
                    detected_drop_start=drop_start,
                    detected_drop_duration=drop_dur,
                    detected_drop_end=drop_start + drop_dur,
                    festival=festival,
                    artist=artist,
                    track=track,
                    status=state_label,
                    created_at=datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc).isoformat(),
                )

    return list(clips_map.values())


def find_proxy_file(workspace_root: Path, clip_id: str) -> Optional[Path]:
    """Resolves clip_id to an existing proxy or video file path."""
    direct = Path(clip_id)
    if direct.is_file():
        return direct
    direct_rel = workspace_root / clip_id
    if direct_rel.is_file():
        return direct_rel

    video_exts = [".mp4", ".mov", ".mkv", ".m4v", ".webm"]
    search_dirs = [
        workspace_root / "02_AWAITING_REVIEW",
        workspace_root / "01_RAW",
        workspace_root / "02_IN_PROGRESS",
        workspace_root / "01_RAW_INBOX",
        workspace_root / "static",
        workspace_root,
    ]

    for sdir in search_dirs:
        if not sdir.is_dir():
            continue
        for ext in video_exts:
            cands = [
                sdir / f"{clip_id}{ext}",
                sdir / f"{clip_id}_proxy{ext}",
                sdir / f"{clip_id}_proxy_drop{ext}",
            ]
            for cand in cands:
                if cand.is_file():
                    return cand

        for f in sdir.rglob("*"):
            if f.is_file() and f.suffix.lower() in video_exts:
                if clip_id in f.stem:
                    return f

    return None


def stream_video_range(file_path: Path, range_header: Optional[str] = None) -> Response:
    """
    Implements HTTP 206 Partial Content byte-range streaming for video files.
    Allows smooth HTML5 video scrubbing and seeking in mobile browsers.
    """
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video file '{file_path.name}' not found",
        )

    file_size = file_path.stat().st_size
    content_type = "video/mp4"

    if not range_header or not range_header.strip().startswith("bytes="):
        return FileResponse(
            str(file_path),
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            },
        )

    range_spec = range_header.replace("bytes=", "").strip()
    parts = range_spec.split("-")
    start_str = parts[0].strip() if len(parts) > 0 else ""
    end_str = parts[1].strip() if len(parts) > 1 else ""

    status_416 = 416
    try:
        if start_str and end_str:
            start = int(start_str)
            end = int(end_str)
        elif start_str:
            start = int(start_str)
            end = file_size - 1
        elif end_str:
            suffix_len = int(end_str)
            start = max(0, file_size - suffix_len)
            end = file_size - 1
        else:
            start = 0
            end = file_size - 1
    except ValueError:
        return Response(
            status_code=status_416,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    if start < 0 or start >= file_size or end < start:
        return Response(
            status_code=status_416,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    end = min(end, file_size - 1)
    chunk_length = (end - start) + 1

    def iter_file_chunk(path: Path, offset: int, length: int, chunk_size: int = 64 * 1024):
        with open(path, "rb") as f:
            f.seek(offset)
            remaining = length
            while remaining > 0:
                read_size = min(remaining, chunk_size)
                data = f.read(read_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_length),
        "Content-Type": content_type,
    }

    return StreamingResponse(
        iter_file_chunk(file_path, start, chunk_length),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        headers=headers,
        media_type=content_type,
    )


# ============================================================================
# FASTAPI APPLICATION FACTORY
# ============================================================================

def create_app(workspace_root: Optional[Path] = None) -> FastAPI:
    """Instantiates and configures the FastAPI Zero-Touch Remote Trigger application."""
    root = (workspace_root or Path(__file__).resolve().parent).resolve()
    manager = PipelineJobManager(workspace_root=root)

    app = FastAPI(
        title="Content Creation Remote Trigger API",
        description="FastAPI Zero-Touch Automation Bridge for EDM Short-Form Media Engineering Pipeline",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.job_manager = manager

    # Mount /static directory for PWA assets if it exists
    static_dir = root / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get(
        "/",
        response_class=HTMLResponse,
        summary="Mobile PWA Dashboard",
        description="Serves the mobile-first Progressive Web App interface for triggering EDM pipelines.",
        include_in_schema=False,
    )
    async def get_index():
        index_path = manager.workspace_root / "static" / "index.html"
        if not index_path.exists():
            index_path = manager.workspace_root / "index.html"
        if not index_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"index.html not found in {manager.workspace_root / 'static'} or {manager.workspace_root}",
            )
        return FileResponse(str(index_path), media_type="text/html")

    @app.get(
        "/manifest.json",
        summary="PWA Web App Manifest",
        description="Serves the PWA Web App Manifest for mobile home screen installation.",
        include_in_schema=False,
    )
    async def get_manifest():
        manifest_path = manager.workspace_root / "static" / "manifest.json"
        if not manifest_path.exists():
            manifest_path = manager.workspace_root / "manifest.json"
        if not manifest_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"manifest.json not found in {manager.workspace_root / 'static'} or {manager.workspace_root}",
            )
        return FileResponse(str(manifest_path), media_type="application/manifest+json")

    @app.post(
        "/trigger-pipeline",
        response_model=TriggerResponse,
        status_code=status.HTTP_202_ACCEPTED,
        summary="Trigger Automated Pipeline",
        description="Asynchronously initiates orchestrator pipeline execution and returns HTTP 202 Accepted in <50ms.",
        responses={
            status.HTTP_202_ACCEPTED: {"model": TriggerResponse, "description": "Job accepted and started in background"},
            status.HTTP_409_CONFLICT: {"model": ConflictResponse, "description": "Another job is already in progress"},
        },
    )
    async def trigger_pipeline(request: Optional[PipelineTriggerRequest] = None):
        req = request or PipelineTriggerRequest()
        success, res = await manager.trigger(req)
        if not success:
            return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=res.model_dump())
        return res

    @app.get(
        "/status",
        response_model=StatusResponse,
        summary="Get Overall Daemon Status",
        description="Returns current daemon state, is_running indicator, current job ID, total jobs run, and active/last job telemetry.",
    )
    async def get_status():
        active = manager.get_active_job()
        last = manager.get_last_job()
        return StatusResponse(
            state=active.state if active and manager.is_running else JobState.IDLE,
            is_running=manager.is_running,
            current_job_id=manager.current_job_id,
            total_jobs_run=manager.total_jobs_run,
            active_job=active.to_telemetry() if active and manager.is_running else None,
            last_job=last.to_telemetry() if last else None,
            recent_jobs=[j.to_telemetry() for j in manager._job_history],
        )

    @app.get(
        "/status/{job_id}",
        response_model=JobTelemetry,
        summary="Get Specific Job Status",
        description="Returns full telemetry for a specific job ID or HTTP 404 if not found.",
        responses={
            status.HTTP_200_OK: {"model": JobTelemetry, "description": "Job telemetry found"},
            status.HTTP_404_NOT_FOUND: {"description": "Job ID not found in active or historical records"},
        },
    )
    async def get_job_status(job_id: str):
        job = manager.find_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job ID '{job_id}' not found")
        return job.to_telemetry()

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="System Health & Readiness Check",
        description="Probes system readiness, disk space headroom, and availability of adb, ffmpeg, and ffprobe binaries.",
        responses={
            status.HTTP_200_OK: {"model": HealthResponse, "description": "System is healthy or degraded"},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse, "description": "Critical dependencies missing"},
        },
    )
    async def health_check(response: Response):
        adb_ok = bool(find_adb_binary()) if find_adb_binary else bool(find_binary("adb"))
        ffmpeg_ok = bool(find_binary("ffmpeg"))
        ffprobe_ok = bool(find_binary("ffprobe"))

        free_bytes = None
        free_gb = None
        try:
            usage = shutil.disk_usage(manager.workspace_root)
            free_bytes = usage.free
            free_gb = round(free_bytes / (1024 ** 3), 2)
        except Exception:
            pass

        is_critical_ok = ffmpeg_ok and ffprobe_ok
        if is_critical_ok and adb_ok:
            health_status = "healthy"
        elif is_critical_ok:
            health_status = "degraded"
        else:
            health_status = "unhealthy"

        health_data = HealthResponse(
            status=health_status,
            service="content_creation.remote_trigger",
            version="1.0.0",
            is_pipeline_running=manager.is_running,
            adb_available=adb_ok,
            ffmpeg_available=ffmpeg_ok,
            ffprobe_available=ffprobe_ok,
            free_disk_space_bytes=free_bytes,
            free_disk_space_gb=free_gb,
            workspace_root=str(manager.workspace_root),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if not is_critical_ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return health_data

    @app.get(
        "/logs",
        response_model=LogsResponse,
        summary="Get System & Job Logs",
        description="Retrieves buffered log lines from the in-memory ring buffer with optional tail length and job ID filters.",
    )
    async def get_logs(tail: Optional[int] = 100, job_id: Optional[str] = None):
        entries = manager.get_logs(tail=tail, job_id=job_id)
        raw_logs = [f"[{e.timestamp}] [{e.level}] {e.message}" for e in entries]
        return LogsResponse(
            job_id=job_id,
            total_lines=len(raw_logs),
            logs=raw_logs,
            entries=entries,
        )

    @app.post(
        "/cancel",
        response_model=CancelResponse,
        summary="Cancel Active Pipeline Job",
        description="Gracefully terminates the currently running pipeline subprocess or returns HTTP 400 if no job is active.",
        responses={
            status.HTTP_200_OK: {"model": CancelResponse, "description": "Active job successfully cancelled"},
            status.HTTP_400_BAD_REQUEST: {"description": "No active job is currently running"},
        },
    )
    async def cancel_job():
        success, msg, job_id = await manager.cancel_active_job()
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        return CancelResponse(
            status="cancelled",
            job_id=job_id or "unknown",
            message=msg,
            terminated=True,
        )

    @app.get(
        "/api/clips/pending",
        response_model=PendingClipsResponse,
        summary="Get Pending Review Clips",
        description="Discovers pending takes and 720p proxies in 01_RAW, 02_AWAITING_REVIEW, or 02_IN_PROGRESS.",
    )
    @app.get(
        "/proxies",
        response_model=PendingClipsResponse,
        include_in_schema=False,
    )
    @app.get(
        "/api/proxies",
        response_model=PendingClipsResponse,
        include_in_schema=False,
    )
    async def get_pending_clips():
        clips = discover_pending_clips(manager.workspace_root)
        return PendingClipsResponse(total=len(clips), clips=clips)

    @app.get(
        "/proxies/{clip_id}/video",
        summary="Stream 720p Proxy Video with HTTP 206 Byte Range",
        description="Streams the requested 720p proxy video using HTTP 206 Partial Content byte ranges for smooth scrubbing.",
        responses={
            status.HTTP_200_OK: {"description": "Complete video file returned"},
            status.HTTP_206_PARTIAL_CONTENT: {"description": "Partial byte range stream for HTML5 video player"},
            status.HTTP_404_NOT_FOUND: {"description": "Proxy video file not found"},
            416: {"description": "Requested range out of bounds"},
        },
    )
    @app.get(
        "/api/proxy/{clip_id}/video",
        include_in_schema=False,
    )
    @app.get(
        "/api/proxies/{clip_id}/video",
        include_in_schema=False,
    )
    async def get_proxy_video(clip_id: str, request: Request):
        video_path = find_proxy_file(manager.workspace_root, clip_id)
        if not video_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proxy video for clip '{clip_id}' not found",
            )
        range_header = request.headers.get("range")
        return stream_video_range(video_path, range_header)

    @app.post(
        "/approve-render",
        response_model=ApproveRenderResponse,
        status_code=status.HTTP_200_OK,
        summary="Approve Trim Points & Trigger DaVinci Resolve Handoff",
        description="Receives user-approved trim timestamps and launches DaVinci Resolve timeline construction.",
        responses={
            status.HTTP_200_OK: {"model": ApproveRenderResponse, "description": "Handoff executed successfully"},
            status.HTTP_404_NOT_FOUND: {"description": "Raw media file not found on disk"},
            422: {"description": "Invalid payload format"},
        },
    )
    @app.post(
        "/api/resolve/handoff",
        response_model=ApproveRenderResponse,
        include_in_schema=False,
    )
    @app.post(
        "/api/approve-render",
        response_model=ApproveRenderResponse,
        include_in_schema=False,
    )
    async def approve_render(request: ApproveRenderRequest):
        raw_path_str = request.resolved_raw_path
        raw_file = None

        if raw_path_str:
            p = Path(raw_path_str)
            if p.is_file():
                raw_file = p
            elif (manager.workspace_root / raw_path_str).is_file():
                raw_file = manager.workspace_root / raw_path_str
            elif not request.dry_run:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Raw 4K video file not found at path '{raw_path_str}'",
                )

        if not raw_file and request.clip_id:
            raw_file = find_proxy_file(manager.workspace_root, request.clip_id)

        if not raw_file and not raw_path_str:
            raw_dir = manager.workspace_root / "01_RAW"
            if raw_dir.is_dir():
                for f in raw_dir.rglob("*.mp4"):
                    if f.is_file() and "_proxy" not in f.stem.lower():
                        raw_file = f
                        break

        if not raw_file and not request.dry_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Raw 4K video file could not be located for clip '{request.clip_id or raw_path_str}'",
            )

        target_raw_path = str(raw_file) if raw_file else (raw_path_str or "01_RAW/simulated_raw.mp4")

        fest = request.festival or "Concert"
        art = request.artist or "Artist"
        trk = request.track or "ID"

        clean_fest = re.sub(r"[^\w\-]", "", fest.replace(" ", "_"))
        clean_art = re.sub(r"[^\w\-]", "", art.replace(" ", "_"))
        clean_trk = re.sub(r"[^\w\-]", "", trk.replace(" ", "_"))

        proj_name = request.project_name or f"{clean_fest}_{clean_art}_Master"
        tl_name = request.timeline_name or f"{clean_art}_{clean_trk}_Drop_Vertical"

        dur = request.duration if request.duration is not None else ((request.end_time - request.start_time) if request.end_time else 30.0)
        end_time = request.end_time if request.end_time is not None else (request.start_time + dur)

        job_id = f"job_resolve_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        manager._add_log(LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level="INFO",
            message=f"[RESOLVE HANDOFF] Dispatching Resolve timeline '{tl_name}' in project '{proj_name}' (Slices: {request.start_time:.2f}s..{end_time:.2f}s)",
            job_id=job_id,
        ))

        if create_resolve_timeline:
            result_dict = create_resolve_timeline(
                raw_file_path=target_raw_path,
                start_time=request.start_time,
                end_time=end_time,
                duration=dur,
                project_name=proj_name,
                timeline_name=tl_name,
                fps=request.fps,
                width=request.width,
                height=request.height,
                festival=fest,
                artist=art,
                track=trk,
                auto_save=request.auto_save,
                dry_run=request.dry_run,
            )
        else:
            start_frame = int(round(request.start_time * request.fps))
            end_frame = int(round(end_time * request.fps))
            result_dict = {
                "success": True,
                "status": "fallback_simulated",
                "project_name": proj_name,
                "timeline_name": tl_name,
                "raw_file_path": target_raw_path,
                "start_time": request.start_time,
                "end_time": end_time,
                "duration": dur,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "duration_frames": end_frame - start_frame,
                "fps": request.fps,
                "width": request.width,
                "height": request.height,
                "timeline_resolution": f"{request.width}x{request.height}",
                "telemetry": {},
            }

        status_str = result_dict.get("status", "accepted")
        msg = f"DaVinci Resolve handoff completed with status '{status_str}'"
        if result_dict.get("error_message"):
            msg = f"DaVinci Resolve handoff reported: {result_dict.get('error_message')}"

        manager._add_log(LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level="INFO" if result_dict.get("success") else "WARNING",
            message=f"[RESOLVE HANDOFF] Result: {status_str} - {msg}",
            job_id=job_id,
        ))

        return ApproveRenderResponse(
            status=status_str,
            job_id=job_id,
            message=msg,
            project_name=result_dict.get("project_name", proj_name),
            timeline_name=result_dict.get("timeline_name", tl_name),
            start_time=result_dict.get("start_time", request.start_time),
            end_time=result_dict.get("end_time", end_time),
            duration=result_dict.get("duration", dur),
            start_frame=result_dict.get("start_frame"),
            end_frame=result_dict.get("end_frame"),
            duration_frames=result_dict.get("duration_frames"),
            fps=result_dict.get("fps", request.fps),
            timeline_resolution=result_dict.get("timeline_resolution", f"{request.width}x{request.height}"),
            raw_file_path=result_dict.get("raw_file_path", target_raw_path),
            telemetry=result_dict.get("telemetry", {}),
        )

    return app


# Default application instance for uvicorn ASGI loading
app = create_app()


# ============================================================================
# CLI RUNNER & CONFIGURATION DISPATCHER
# ============================================================================

def main():
    """CLI entrypoint for running the FastAPI Remote Trigger server via uvicorn."""
    parser = argparse.ArgumentParser(description="FastAPI Zero-Touch Remote Trigger Server for EDM Content Creation")
    parser.add_argument(
        "--host",
        default=os.environ.get("REMOTE_TRIGGER_HOST", "0.0.0.0"),
        help="Host IP to bind (default: 0.0.0.0 or REMOTE_TRIGGER_HOST env var)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("REMOTE_TRIGGER_PORT", 8000)),
        help="Port to bind (default: 8000 or REMOTE_TRIGGER_PORT env var)",
    )
    parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parent),
        help="Content creation workspace directory",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    args = parser.parse_args()

    server_app = create_app(workspace_root=Path(args.workspace))
    logger.info("Starting Remote Trigger server on %s:%d (Workspace: %s)", args.host, args.port, args.workspace)
    uvicorn.run(server_app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
