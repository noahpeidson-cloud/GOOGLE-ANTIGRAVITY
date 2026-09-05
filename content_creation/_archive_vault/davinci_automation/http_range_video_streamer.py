"""
================================================================================
Name: FastAPI HTTP 206 Byte-Range Video Streamer & Subprocess Supervisor
Context Mapping: Extracted from `content_creation/remote_trigger.py` and
                 `content_creation/dashboard_backend.py`. Solves mobile and
                 web video scrubber buffering issues and prevents multi-GB
                 memory exhaustion while providing a robust single-job mutex
                 supervisor for heavy DaVinci / FFmpeg render jobs.
Strengths:
  - Production-grade HTTP 206 Partial Content byte-range streaming engine:
    * Implements RFC 7233 byte-range specifications (exact start-end, open-ended
      ranges, and suffix ranges).
    * Streams in optimized 64KB (65,536 bytes) chunks via Python generators,
      enabling instant HTML5 video seeking without loading entire 4K files into RAM.
    * Sets explicit `Accept-Ranges: bytes`, `Content-Range`, and `Content-Length`
      headers, returning HTTP 416 Range Not Satisfiable when bounds are invalid.
  - Single-Job Async Subprocess Supervisor:
    * Uses an `asyncio.Lock()` mutex to serialize compute-heavy rendering tasks.
    * Returns HTTP 409 Conflict with detailed active job telemetry when a job is
      already running, preventing GPU/VRAM thrashing and filesystem race conditions.
    * Streams non-blocking stdout and stderr concurrently into an in-memory ring
      buffer (`collections.deque(maxlen=2000)`), avoiding Windows pipe deadlocks.
    * Two-stage graceful cancellation protocol: sends SIGTERM (`proc.terminate()`),
      awaits up to 3.0 seconds, and falls back to SIGKILL (`proc.kill()`).

Weaknesses:
  - Byte-range streaming requires direct local filesystem access (POSIX / Windows
    paths); cloud object stores (e.g. GCS / S3) require signed URLs or custom
    cloud streaming wrappers.
  - The in-memory ring buffer does not survive application restarts; long-term
    audit trails should mirror log records to an external SQLite or PostgreSQL DB.

Implementation Instructions:
  1. Mount the router into your FastAPI application or run as a standalone service:
     `app.include_router(router)` or `python http_range_video_streamer.py`.
  2. For video streaming: `GET /stream/{video_name}` with standard HTTP `Range` headers.
  3. For job supervision:
     - `POST /jobs/trigger` with a shell command or render task.
     - `GET /jobs/active` to poll current job status.
     - `GET /jobs/logs` to read tail logs from the ring buffer.
     - `POST /jobs/cancel` to gracefully terminate an active job.
================================================================================
"""

from __future__ import annotations

import os
import sys
import uuid
import time
import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Deque, Dict, Generator, List, Optional, Tuple, Union

try:
    from fastapi import FastAPI, APIRouter, Header, HTTPException, Query, Response, status
    from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Minimal mock definitions for offline compilation and type safety
    class BaseModel:  # type: ignore[no-redef]
        def model_dump(self) -> Dict[str, Any]:
            return self.__dict__
    def Field(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        return None
    class HTTPException(Exception):  # type: ignore[no-redef]
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

logger = logging.getLogger("HttpRangeVideoStreamer")


# ============================================================================
# DATA MODELS & ENUMS
# ============================================================================

class JobState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    job_id: str


@dataclass
class JobRecord:
    job_id: str
    command: List[str]
    params: Dict[str, Any]
    state: JobState = JobState.IDLE
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    error_summary: Optional[str] = None

    @property
    def elapsed_seconds(self) -> float:
        if not self.started_at:
            return 0.0
        end_time = self.completed_at or datetime.now(timezone.utc)
        return max(0.0, (end_time - self.started_at).total_seconds())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "command": self.command,
            "params": self.params,
            "state": self.state.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "exit_code": self.exit_code,
            "error_summary": self.error_summary,
        }


# ============================================================================
# HTTP 206 BYTE-RANGE STREAMING LOGIC
# ============================================================================

CHUNK_SIZE: int = 64 * 1024  # 64 KB chunk size for smooth scrubbing


def parse_byte_range(range_header: str, file_size: int) -> Tuple[int, int]:
    """
    Parses standard HTTP Range header (e.g., 'bytes=0-1048575', 'bytes=1000-', 'bytes=-500').
    Returns (start_byte, end_byte) inclusive.
    Raises ValueError if range is invalid or not satisfiable.
    """
    if not range_header.startswith("bytes="):
        raise ValueError("Invalid range unit; expected 'bytes='")

    range_val = range_header[6:].strip()
    if not range_val:
        raise ValueError("Empty range value")

    parts = range_val.split("-")
    if len(parts) != 2:
        raise ValueError(f"Malformed range header: {range_header}")

    start_str, end_str = parts[0].strip(), parts[1].strip()

    if start_str and end_str:
        start = int(start_str)
        end = int(end_str)
    elif start_str and not end_str:
        start = int(start_str)
        end = file_size - 1
    elif not start_str and end_str:
        suffix_len = int(end_str)
        if suffix_len <= 0:
            raise ValueError("Suffix length must be positive")
        start = max(0, file_size - suffix_len)
        end = file_size - 1
    else:
        raise ValueError("Both start and end cannot be empty")

    if start < 0 or start >= file_size or end < start:
        raise ValueError(f"Range [{start}-{end}] not satisfiable for file size {file_size}")

    end = min(end, file_size - 1)
    return start, end


def iter_file_chunks(
    file_path: Union[str, Path],
    offset: int,
    length: int,
    chunk_size: int = CHUNK_SIZE,
) -> Generator[bytes, None, None]:
    """
    Synchronous byte generator yielding fixed-size chunks for streaming responses.
    """
    with open(file_path, "rb") as f:
        f.seek(offset)
        remaining = length
        while remaining > 0:
            read_size = min(remaining, chunk_size)
            data = f.read(read_size)
            if not data:
                break
            remaining -= len(data)
            yield data


def build_range_response(
    file_path: Union[str, Path],
    range_header: Optional[str] = None,
    media_type: str = "video/mp4",
) -> Any:
    """
    Generates a production HTTP 206 Partial Content StreamingResponse or HTTP 200 FileResponse.
    Handles invalid ranges with RFC-compliant HTTP 416 responses.
    """
    p = Path(file_path).resolve()
    if not p.is_file():
        if FASTAPI_AVAILABLE:
            raise HTTPException(status_code=404, detail=f"Media file '{p.name}' not found")
        raise FileNotFoundError(f"Media file '{p.name}' not found")

    file_size = p.stat().st_size

    # Full content response when no Range header is requested
    if not range_header or not range_header.strip().startswith("bytes="):
        if FASTAPI_AVAILABLE:
            return FileResponse(
                str(p),
                media_type=media_type,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(file_size),
                },
            )
        return {
            "status_code": 200,
            "headers": {"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
        }

    # Byte-range parsing
    try:
        start, end = parse_byte_range(range_header, file_size)
    except (ValueError, IndexError):
        headers_416 = {"Content-Range": f"bytes */{file_size}"}
        if FASTAPI_AVAILABLE:
            return Response(status_code=416, headers=headers_416)
        return {"status_code": 416, "headers": headers_416}

    content_length = (end - start) + 1
    response_headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": media_type,
    }

    if FASTAPI_AVAILABLE:
        return StreamingResponse(
            iter_file_chunks(p, start, content_length, chunk_size=CHUNK_SIZE),
            status_code=206,
            headers=response_headers,
            media_type=media_type,
        )

    return {
        "status_code": 206,
        "headers": response_headers,
        "generator": iter_file_chunks(p, start, content_length, chunk_size=CHUNK_SIZE),
    }


# ============================================================================
# SINGLE-JOB ASYNC SUBPROCESS SUPERVISOR
# ============================================================================

class SubprocessJobSupervisor:
    """
    Asynchronous supervisor managing compute-intensive subprocess execution.
    Features:
      - `asyncio.Lock()` mutex preventing concurrent execution conflicts.
      - Ring-buffered stdout/stderr streaming (`collections.deque`).
      - Two-stage cancellation (SIGTERM -> 3.0s -> SIGKILL).
      - Thread-safe job state query and history tracking.
    """

    def __init__(
        self,
        workspace_dir: Optional[Union[str, Path]] = None,
        max_logs: int = 2000,
        max_history: int = 50,
    ):
        self.workspace_dir = Path(workspace_dir or os.getcwd()).resolve()
        self.max_logs = max_logs
        self.max_history = max_history

        self._lock = asyncio.Lock()
        self._active_job: Optional[JobRecord] = None
        self._active_process: Optional[asyncio.subprocess.Process] = None
        self._active_task: Optional[asyncio.Task] = None
        self._log_buffer: Deque[LogEntry] = deque(maxlen=max_logs)
        self._job_history: List[JobRecord] = []
        self._total_jobs_run: int = 0

    @property
    def is_running(self) -> bool:
        return self._active_job is not None and self._active_job.state == JobState.RUNNING

    @property
    def active_job(self) -> Optional[JobRecord]:
        return self._active_job if self.is_running else None

    def get_logs(self, tail: Optional[int] = None, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
        entries = list(self._log_buffer)
        if job_id:
            entries = [e for e in entries if e.job_id == job_id]
        if tail is not None and tail > 0:
            entries = entries[-tail:]
        return [
            {"timestamp": e.timestamp, "level": e.level, "message": e.message, "job_id": e.job_id}
            for e in entries
        ]

    def _append_log(self, job_id: str, message: str, level: str = "INFO") -> None:
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            message=message,
            job_id=job_id,
        )
        self._log_buffer.append(entry)
        if level == "ERROR":
            logger.error("[%s] %s", job_id, message)
        else:
            logger.info("[%s] %s", job_id, message)

    async def trigger_job(
        self,
        command: List[str],
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Dict[str, Any], int]:
        """
        Attempts to acquire the mutex and spawn the requested subprocess.
        Returns (success, response_dict, http_status_code).
        If another job is running, returns (False, conflict_dict, 409).
        """
        async with self._lock:
            if self.is_running and self._active_job is not None:
                conflict_data = {
                    "status": "conflict",
                    "error": "A pipeline or render job is already running",
                    "active_job": self._active_job.to_dict(),
                }
                return False, conflict_data, 409

            self._total_jobs_run += 1
            now_utc = datetime.now(timezone.utc)
            job_id = f"job_{now_utc.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

            job = JobRecord(
                job_id=job_id,
                command=command,
                params=params or {},
                state=JobState.RUNNING,
                started_at=now_utc,
            )
            self._active_job = job

            self._append_log(job_id, f"Job accepted. Spawning command: {' '.join(command)}")

            # Launch async background runner task
            self._active_task = asyncio.create_task(self._execute_subprocess(job))

            accepted_data = {
                "status": "accepted",
                "job_id": job_id,
                "command": command,
                "started_at": now_utc.isoformat(),
            }
            return True, accepted_data, 202

    async def _execute_subprocess(self, job: JobRecord) -> None:
        """
        Internal worker coroutine executing the command and draining stdout/stderr.
        """
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            proc = await asyncio.create_subprocess_exec(
                *job.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_dir),
                env=env,
            )
            self._active_process = proc

            async def drain_stream(stream: Optional[asyncio.StreamReader], prefix: str, level: str) -> None:
                if stream is None:
                    return
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                    self._append_log(job.job_id, f"{prefix}{text}", level=level)

            # Ingest stdout and stderr concurrently without pipe deadlock
            await asyncio.gather(
                drain_stream(proc.stdout, prefix="", level="INFO"),
                drain_stream(proc.stderr, prefix="[STDERR] ", level="ERROR"),
            )

            exit_code = await proc.wait()
            job.exit_code = exit_code
            job.completed_at = datetime.now(timezone.utc)

            if exit_code == 0:
                job.state = JobState.COMPLETED
                self._append_log(
                    job.job_id,
                    f"Job completed successfully (exit code 0) in {job.elapsed_seconds:.2f}s"
                )
            else:
                job.state = JobState.FAILED
                job.error_summary = f"Subprocess exited with code {exit_code}"
                self._append_log(
                    job.job_id,
                    f"Job failed with non-zero exit code {exit_code} in {job.elapsed_seconds:.2f}s",
                    level="ERROR"
                )

        except asyncio.CancelledError:
            job.state = JobState.CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            job.error_summary = "Job execution was cancelled"
            self._append_log(job.job_id, "Job was cancelled via task cancellation", level="WARNING")
        except Exception as ex:
            job.state = JobState.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_summary = str(ex)
            self._append_log(job.job_id, f"Unexpected error during job execution: {ex}", level="ERROR")
        finally:
            self._active_process = None
            if self._active_job == job:
                self._active_job = None
            self._job_history.insert(0, job)
            if len(self._job_history) > self.max_history:
                self._job_history.pop()

    async def cancel_job(self) -> Tuple[bool, str, Optional[str]]:
        """
        Gracefully cancels the active running job:
        1. Sends SIGTERM via proc.terminate().
        2. Awaits up to 3.0s for graceful shutdown.
        3. Falls back to SIGKILL via proc.kill().
        """
        async with self._lock:
            if not self.is_running or self._active_job is None:
                return False, "No active job currently running", None

            job = self._active_job
            job_id = job.job_id
            proc = self._active_process

            try:
                if proc is not None:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=3.0)
                    except asyncio.TimeoutError:
                        self._append_log(job_id, "Process did not terminate within 3.0s; issuing SIGKILL", level="WARNING")
                        proc.kill()
                        await proc.wait()
                    job.exit_code = proc.returncode

                if self._active_task and not self._active_task.done():
                    self._active_task.cancel()

                job.state = JobState.CANCELLED
                job.completed_at = datetime.now(timezone.utc)
                job.error_summary = "Terminated via user cancellation request"

                self._append_log(job_id, "Job terminated and cleaned up successfully", level="WARNING")

                self._active_job = None
                self._active_process = None
                self._job_history.insert(0, job)
                if len(self._job_history) > self.max_history:
                    self._job_history.pop()

                return True, f"Job {job_id} cancelled successfully", job_id
            except Exception as ex:
                logger.exception("Failed to cancel job %s: %s", job_id, ex)
                return False, f"Failed to cancel job {job_id}: {ex}", job_id


# ============================================================================
# FASTAPI ROUTER & APP FACTORY
# ============================================================================

def create_streaming_and_supervisor_router(
    video_storage_dir: Union[str, Path],
    supervisor: SubprocessJobSupervisor,
) -> Any:
    """
    Creates a FastAPI APIRouter bundling HTTP 206 video streaming and
    subprocess job management endpoints.
    """
    if not FASTAPI_AVAILABLE:
        logger.warning("FastAPI is not installed; returning empty router stub.")
        return None

    router = APIRouter(prefix="/api/media", tags=["Media Streaming & Jobs"])
    video_dir = Path(video_storage_dir).resolve()

    class TriggerRequest(BaseModel):
        command: List[str] = Field(..., description="Executable command line array")
        params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Job metadata parameters")

    @router.get("/stream/{filename}")
    async def stream_video_endpoint(
        filename: str,
        range: Optional[str] = Header(None, alias="Range"),
    ) -> Response:
        """
        Streams video file with HTTP 206 Partial Content byte-range support.
        """
        target_file = (video_dir / filename).resolve()
        # Security check: ensure target remains inside video_dir
        if not str(target_file).startswith(str(video_dir)):
            raise HTTPException(status_code=403, detail="Access denied: invalid path traversal")

        return build_range_response(target_file, range_header=range)

    @router.post("/jobs/trigger", status_code=status.HTTP_202_ACCEPTED)
    async def trigger_job_endpoint(payload: TriggerRequest) -> Any:
        """
        Launches a single-job background task. Returns 409 if a job is already running.
        """
        success, response_data, status_code = await supervisor.trigger_job(
            command=payload.command,
            params=payload.params,
        )
        return JSONResponse(status_code=status_code, content=response_data)

    @router.get("/jobs/active")
    async def get_active_job_endpoint() -> Dict[str, Any]:
        """
        Returns status of the currently active job, if any.
        """
        active = supervisor.active_job
        return {
            "is_running": supervisor.is_running,
            "active_job": active.to_dict() if active else None,
        }

    @router.get("/jobs/logs")
    async def get_logs_endpoint(
        tail: int = Query(default=100, ge=1, le=2000),
        job_id: Optional[str] = Query(default=None),
    ) -> Dict[str, Any]:
        """
        Retrieves logs from the supervisor's ring buffer.
        """
        logs = supervisor.get_logs(tail=tail, job_id=job_id)
        return {"total_returned": len(logs), "logs": logs}

    @router.post("/jobs/cancel")
    async def cancel_job_endpoint() -> Dict[str, Any]:
        """
        Gracefully terminates the active running job.
        """
        success, message, job_id = await supervisor.cancel_job()
        if not success:
            raise HTTPException(status_code=400, detail=message)
        return {"status": "cancelled", "message": message, "job_id": job_id}

    return router


# ============================================================================
# VERIFICATION & CLI ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("Testing HTTP 206 Video Streamer and Subprocess Supervisor...")

    # 1. Test range parsing logic
    test_size = 1000
    start, end = parse_byte_range("bytes=0-499", test_size)
    assert start == 0 and end == 499, f"Expected (0, 499), got ({start}, {end})"

    start, end = parse_byte_range("bytes=500-", test_size)
    assert start == 500 and end == 999, f"Expected (500, 999), got ({start}, {end})"

    start, end = parse_byte_range("bytes=-200", test_size)
    assert start == 800 and end == 999, f"Expected (800, 999), got ({start}, {end})"

    print("Byte-range parsing test passed!")

    # 2. Test SubprocessJobSupervisor in asyncio loop
    async def run_supervisor_test():
        supervisor = SubprocessJobSupervisor()
        # Trigger echo test job
        success, data, code = await supervisor.trigger_job(
            command=[sys.executable, "-c", "import time; print('Job Started'); time.sleep(0.5); print('Job Finished')"],
            params={"type": "test_job"},
        )
        assert success is True and code == 202
        print(f"Triggered test job: {data['job_id']}")

        # Attempt concurrent trigger (must return 409 Conflict)
        c_success, c_data, c_code = await supervisor.trigger_job(
            command=[sys.executable, "-c", "print('Collision!')"],
        )
        assert c_success is False and c_code == 409
        print(f"Verified 409 Conflict rejection: {c_data['error']}")

        # Await completion
        await asyncio.sleep(1.0)
        logs = supervisor.get_logs(tail=10)
        assert any("Job Finished" in l["message"] for l in logs)
        print("Supervisor execution and log buffer test passed!")

    asyncio.run(run_supervisor_test())
    print("All self-tests passed successfully.")
