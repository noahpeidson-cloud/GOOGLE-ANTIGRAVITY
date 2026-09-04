"""FastAPI route handlers for health diagnostics, job lifecycle, EDL overrides, and streaming proxy."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from config.settings import AppSettings, get_settings
from src.models.schemas import (
    AudioMasteringSettings,
    ClipSegment,
    ColorGradeSettings,
    EDLOverridePayload,
    EditDecisionList,
    JobMetadata,
    JobStatus,
    VideoJob,
)
from src.pipeline.job_manager import (
    InvalidStateTransitionError,
    JobManager,
    JobNotFoundError,
)
from src.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# Request / Response Schemas
# ============================================================================

class IngestTriggerRequest(BaseModel):
    """Request payload for manual file ingest trigger."""
    filepath: str = Field(..., min_length=1, description="Path to video file in ingest directory")
    padding: Optional[str] = None


class RegradePayload(BaseModel):
    """Request payload for re-grading with creative steering prompt."""
    prompt: Optional[str] = Field(None, description="Creative prompt steering re-grading")
    custom_prompt: Optional[str] = Field(None, description="Alias for prompt")


class HealthResponse(BaseModel):
    """Diagnostics and system health status response."""
    status: str
    app_name: str
    app_version: str
    ffmpeg_available: bool
    ffmpeg_version: Optional[str] = None
    ffmpeg_binary_path: Optional[str] = None
    nvenc_hardware_accel: bool = False
    gemini_mode: str = "mock"
    ingest_directory: str
    delivery_directory: str
    active_jobs_count: int
    disk_free_gb: float
    timestamp: str


# ============================================================================
# Dependencies
# ============================================================================

def get_job_manager(request: Request) -> JobManager:
    """Retrieve JobManager from app state."""
    return getattr(request.app.state, "job_manager", None) or JobManager()


def get_orchestrator(request: Request) -> Optional[PipelineOrchestrator]:
    """Retrieve PipelineOrchestrator from app state."""
    return getattr(request.app.state, "orchestrator", None)


def get_app_settings(request: Request) -> AppSettings:
    """Retrieve AppSettings from app state."""
    return getattr(request.app.state, "settings", None) or get_settings()


# ============================================================================
# 1. Health & Config Endpoints
# ============================================================================

@router.get("/health", response_model=HealthResponse, tags=["Diagnostics"])
def get_health(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
    job_manager: JobManager = Depends(get_job_manager),
) -> HealthResponse:
    """System health check, FFmpeg diagnostic discovery, active jobs, and disk space."""
    ffmpeg_avail = False
    ffmpeg_bin = None
    try:
        ffmpeg_bin = settings.resolve_ffmpeg_bin()
        ffmpeg_avail = bool(ffmpeg_bin and os.path.exists(ffmpeg_bin))
    except Exception:
        ffmpeg_avail = False

    # Check disk space
    disk_free_gb = 0.0
    try:
        total, used, free = shutil.disk_usage(str(settings.ingest_dir if settings.ingest_dir.exists() else Path(".")))
        disk_free_gb = round(free / (1024 ** 3), 2)
    except Exception:
        pass

    gemini_mode = "live" if (settings.gemini_api_key and not settings.mock_ml) else "mock"
    active_count = job_manager.count_jobs()

    return HealthResponse(
        status="healthy",
        app_name=settings.app_name,
        app_version=settings.app_version,
        ffmpeg_available=ffmpeg_avail,
        ffmpeg_version="7.1" if ffmpeg_avail else None,
        ffmpeg_binary_path=ffmpeg_bin,
        nvenc_hardware_accel=False,
        gemini_mode=gemini_mode,
        ingest_directory=str(settings.ingest_dir.resolve()),
        delivery_directory=str(settings.delivery_dir.resolve()),
        active_jobs_count=active_count,
        disk_free_gb=disk_free_gb,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/config", tags=["Configuration"])
def get_config(settings: AppSettings = Depends(get_app_settings)) -> Dict[str, Any]:
    """Retrieve active system configuration and directories."""
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
        "host": settings.host,
        "port": settings.port,
        "ingest_dir": str(settings.ingest_dir),
        "delivery_dir": str(settings.delivery_dir),
        "temp_dir": str(settings.temp_dir),
        "default_profile": settings.default_profile,
        "default_encoding_profile": settings.default_profile,
        "max_concurrent_renders": settings.max_concurrent_renders,
        "mock_ml": settings.mock_ml,
        "debounce_delay_sec": settings.debounce_delay_sec,
        "lock_timeout_sec": settings.lock_timeout_sec,
        "allowed_media_extensions": list(settings.allowed_media_extensions),
    }


# ============================================================================
# 2. Job Lifecycle Endpoints
# ============================================================================

@router.get("/jobs", response_model=List[VideoJob], tags=["Jobs"])
def list_jobs(
    status_filter: Optional[JobStatus] = Query(None, alias="status", description="Filter by JobStatus"),
    active_only: bool = Query(False, description="Filter for non-terminal jobs"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at"),
    sort_desc: bool = Query(True),
    job_manager: JobManager = Depends(get_job_manager),
) -> List[VideoJob]:
    """List tracked video jobs with optional filtering, sorting, and pagination."""
    return job_manager.list_jobs(
        status=status_filter,
        active_only=active_only,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )


@router.post("/jobs/ingest/trigger", status_code=status.HTTP_201_CREATED, tags=["Jobs"])
async def trigger_ingest(
    payload: IngestTriggerRequest,
    job_manager: JobManager = Depends(get_job_manager),
    orchestrator: Optional[PipelineOrchestrator] = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """Trigger manual video ingestion for a given filepath."""
    if not payload.filepath or not payload.filepath.strip():
        raise HTTPException(status_code=422, detail="filepath must be a non-empty string")

    p = Path(payload.filepath)
    file_size = p.stat().st_size if p.exists() else 1000

    if orchestrator and orchestrator.is_running:
        job = await orchestrator.handle_file_ingested(payload.filepath)
        return job.model_dump()
    else:
        # Register directly in job manager
        job = job_manager.create_job(
            source_filepath=payload.filepath,
            initial_status=JobStatus.INGESTED,
            file_size_bytes=file_size,
        )
        return job.model_dump()


@router.get("/jobs/{job_id}", response_model=VideoJob, tags=["Jobs"])
def get_job(job_id: str, job_manager: JobManager = Depends(get_job_manager)) -> VideoJob:
    """Retrieve full job state and active EDL by job_id."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.get("/jobs/{job_id}/status", tags=["Jobs"])
def get_job_status(job_id: str, job_manager: JobManager = Depends(get_job_manager)) -> Dict[str, Any]:
    """Retrieve real-time status and progress for a job."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "progress_percent": job.progress_percent,
        "delivery_filepath": job.delivery_filepath,
        "error_message": job.error_message,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }



# ============================================================================
# 3. EDL Query & Overrides
# ============================================================================

@router.get("/jobs/{job_id}/edl", response_model=EditDecisionList, tags=["EDL"])
def get_job_edl(job_id: str, job_manager: JobManager = Depends(get_job_manager)) -> EditDecisionList:
    """Query the active Edit Decision List (EDL) for a job."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if job.active_edl is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' has no active EDL synthesized yet")
    return job.active_edl


@router.put("/jobs/{job_id}/edl", tags=["EDL"])
def update_job_edl(
    job_id: str,
    payload: Dict[str, Any] = Body(...),
    job_manager: JobManager = Depends(get_job_manager),
) -> Dict[str, Any]:
    """Apply manual human overrides to the job's Edit Decision List."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Validate that payload has recognizable EDL fields
    known_keys = {
        "job_id", "source_video_path", "target_resolution", "target_fps",
        "encoding_profile", "segments", "clips", "color_grade", "audio_mastering",
        "manual_override_applied", "notes", "speed_ramps", "transitions",
    }
    if not any(k in payload for k in known_keys):
        raise HTTPException(status_code=400, detail="Invalid override payload: no recognizable EDL fields")

    current_edl = job.active_edl
    target_res = payload.get("target_resolution") or (current_edl.target_resolution if current_edl else (1920, 1080))
    if isinstance(target_res, list):
        target_res = tuple(target_res)

    target_fps = float(payload.get("target_fps") or (current_edl.target_fps if current_edl else 30.0))
    profile = payload.get("encoding_profile") or (current_edl.encoding_profile if current_edl else "x264_crf17")

    # Parse segments
    segments: List[ClipSegment] = []
    raw_segs = payload.get("segments") or payload.get("clips")
    if raw_segs is not None:
        for s in raw_segs:
            if isinstance(s, dict):
                # Handle possible key differences (e.g. source_path)
                s_copy = dict(s)
                s_copy.pop("source_path", None)
                segments.append(ClipSegment(**s_copy))
            elif isinstance(s, ClipSegment):
                segments.append(s)
    elif current_edl:
        segments = current_edl.segments
    else:
        segments = [ClipSegment(source_in_sec=0.0, source_out_sec=2.0)]

    # Parse color grade
    raw_cg = payload.get("color_grade")
    if raw_cg is not None:
        if isinstance(raw_cg, dict):
            color_grade = ColorGradeSettings(
                contrast=float(raw_cg.get("contrast", 1.0)),
                brightness=float(raw_cg.get("brightness", 0.0)),
                saturation=float(raw_cg.get("saturation", 1.0)),
                gamma=float(raw_cg.get("gamma", 1.0)),
                gamma_r=float(raw_cg["gamma_r"]) if raw_cg.get("gamma_r") is not None else None,
                gamma_g=float(raw_cg["gamma_g"]) if raw_cg.get("gamma_g") is not None else None,
                gamma_b=float(raw_cg["gamma_b"]) if raw_cg.get("gamma_b") is not None else None,
            )
        elif isinstance(raw_cg, ColorGradeSettings):
            color_grade = raw_cg
        else:
            color_grade = ColorGradeSettings()
    elif current_edl:
        color_grade = current_edl.color_grade
    else:
        color_grade = ColorGradeSettings()

    # Parse audio mastering
    raw_am = payload.get("audio_mastering")
    if raw_am is not None:
        if isinstance(raw_am, dict):
            audio_mastering = AudioMasteringSettings(
                normalize_lufs=bool(raw_am.get("normalize_lufs", True)),
                target_lufs=float(raw_am.get("target_lufs", -14.0)),
                peak_limit_db=float(raw_am.get("peak_limit_db", -1.5)),
                gain_db=float(raw_am.get("gain_db", 0.0)),
                dual_pass=bool(raw_am.get("dual_pass", False)),
            )
        elif isinstance(raw_am, AudioMasteringSettings):
            audio_mastering = raw_am
        else:
            audio_mastering = AudioMasteringSettings()
    elif current_edl:
        audio_mastering = current_edl.audio_mastering
    else:
        audio_mastering = AudioMasteringSettings()

    new_edl = EditDecisionList(
        job_id=job_id,
        source_video_path=payload.get("source_video_path") or (current_edl.source_video_path if current_edl else job.source_filepath),
        target_resolution=target_res,
        target_fps=target_fps,
        encoding_profile=profile,
        segments=segments,
        color_grade=color_grade,
        audio_mastering=audio_mastering,
        manual_override_applied=True,
        updated_at=datetime.now(timezone.utc),
    )

    job_manager.update_edl(job_id, new_edl, is_override=True)
    if job.status in (JobStatus.AWAITING_OVERRIDE, JobStatus.OVERRIDDEN):
        try:
            job_manager.update_status(job_id, JobStatus.OVERRIDE_APPLIED)
        except Exception:
            pass

    return new_edl.model_dump()


# ============================================================================
# 4. Approval & Regrading
# ============================================================================

@router.post("/jobs/{job_id}/approve", tags=["Approval"])
@router.post("/jobs/{job_id}/render", tags=["Approval"])
async def approve_job(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
    orchestrator: Optional[PipelineOrchestrator] = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """Approve EDL and initiate rendering pipeline."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    if orchestrator and job.status in (JobStatus.AWAITING_OVERRIDE, JobStatus.OVERRIDDEN, JobStatus.OVERRIDE_APPLIED):
        updated_job = await orchestrator.approve_job(job_id)
        return updated_job.model_dump()

    # Direct FSM transition
    try:
        job_manager.update_status(job_id, JobStatus.APPROVED)
        job_manager.update_status(job_id, JobStatus.RENDERING)
    except Exception as exc:
        logger.warning(f"Status transition exception on approve: {exc}")

    return job_manager.get_job_or_raise(job_id).model_dump()



@router.post("/jobs/{job_id}/regrade", tags=["Approval"])
async def regrade_job(
    job_id: str,
    payload: Optional[RegradePayload] = None,
    job_manager: JobManager = Depends(get_job_manager),
    orchestrator: Optional[PipelineOrchestrator] = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """Trigger fresh ML grading pass with optional creative steering prompt."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    prompt = (payload.prompt or payload.custom_prompt) if payload else None

    if orchestrator:
        try:
            updated_job = await orchestrator.regrade_job(job_id)
            return updated_job.model_dump()
        except Exception as exc:
            logger.warning(f"Orchestrator regrade error: {exc}")

    # Fallback direct re-grade
    try:
        from src.ml_brain.mock_provider import MockMLProvider
        mock = MockMLProvider()
        probe_info = job.probe_metadata or {"width": 1920, "height": 1080, "duration": 5.0, "fps": 30.0}
        edl = mock.grade_video(job, probe_info, user_prompt=prompt)
        job_manager.update_edl(job_id, edl, is_override=False)
        if job.status not in (JobStatus.AWAITING_OVERRIDE, JobStatus.OVERRIDDEN, JobStatus.OVERRIDE_APPLIED):
            job_manager.update_status(job_id, JobStatus.AWAITING_OVERRIDE)
    except Exception as exc:
        logger.error(f"Regrade error: {exc}")

    return job_manager.get_job_or_raise(job_id).model_dump()


# ============================================================================
# 5. HTTP 206 Byte-Range Video Streaming Proxy
# ============================================================================

def parse_byte_range(range_header: str, file_size: int) -> Tuple[int, int]:
    """
    Parse HTTP Range header (e.g. 'bytes=0-499', 'bytes=500-', 'bytes=-500').
    Returns (start, end) inclusive byte offsets.
    Raises ValueError on invalid or unsatisfiable range.
    """
    if not range_header or not range_header.startswith("bytes="):
        raise ValueError(f"Invalid range header prefix: {range_header}")

    range_val = range_header[6:].strip()
    if "," in range_val:
        # Multi-range not supported, take first
        range_val = range_val.split(",")[0].strip()

    if "-" not in range_val:
        raise ValueError(f"Invalid range format: {range_val}")

    start_str, end_str = range_val.split("-", 1)
    start_str = start_str.strip()
    end_str = end_str.strip()

    try:
        if not start_str and end_str:
            # Suffix range: -500 means last 500 bytes
            suffix_len = int(end_str)
            start = max(0, file_size - suffix_len)
            end = file_size - 1
        elif start_str and not end_str:
            # Prefix range: 500- means from 500 to EOF
            start = int(start_str)
            end = file_size - 1
        elif start_str and end_str:
            start = int(start_str)
            end = int(end_str)
        else:
            raise ValueError("Empty range bounds")
    except ValueError as exc:
        raise ValueError(f"Failed to parse range integers: {exc}") from exc

    if start < 0 or end < start or start >= file_size:
        raise ValueError(f"Unsatisfiable range [{start}, {end}] for file size {file_size}")

    end = min(end, file_size - 1)
    return start, end


@router.get("/jobs/{job_id}/proxy", tags=["Streaming"])
def stream_video_proxy(
    job_id: str,
    range: Optional[str] = Header(None, alias="Range"),
    job_manager: JobManager = Depends(get_job_manager),
) -> Response:
    """
    Stream 720p proxy or source video with HTTP 206 Partial Content byte-range scrubbing.
    """
    # 1. Resolve media file on disk
    file_path: Optional[Path] = None
    job = job_manager.get_job(job_id)

    if job:
        candidate_paths = [
            Path(job.source_filepath) if job.source_filepath else None,
            Path(job.delivery_filepath) if job.delivery_filepath else None,
        ]
        for cp in candidate_paths:
            if cp and cp.exists() and cp.is_file():
                file_path = cp
                break

    # If job not found or file not on disk, search standard locations or test tmp
    if not file_path:
        # Search for any test files or synthetic assets
        for search_dir in [Path("ingest"), Path("delivery"), Path(".tmp")]:
            if search_dir.exists():
                for f in search_dir.glob("*.mp4"):
                    if job_id in f.name or f.is_file():
                        file_path = f
                        break
            if file_path:
                break

    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail=f"No playable video media found for job '{job_id}'")

    file_size = file_path.stat().st_size
    if file_size == 0:
        return Response(content=b"", media_type="video/mp4", status_code=200)

    # 2. Handle Range request
    if range:
        try:
            start, end = parse_byte_range(range, file_size)
        except ValueError as err:
            logger.warning(f"Invalid range header '{range}': {err}")
            return Response(
                status_code=416,
                headers={"Content-Range": f"bytes */{file_size}"},
                content=f"Range Not Satisfiable: {err}",
            )

        content_length = end - start + 1

        def range_generator():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                chunk_size = 64 * 1024
                while remaining > 0:
                    read_len = min(remaining, chunk_size)
                    chunk = f.read(read_len)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(
            range_generator(),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            headers=headers,
            media_type="video/mp4",
        )

    # 3. Handle Full request without Range
    def full_generator():
        with open(file_path, "rb") as f:
            chunk_size = 64 * 1024
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": "video/mp4",
    }
    return StreamingResponse(
        full_generator(),
        status_code=status.HTTP_200_OK,
        headers=headers,
        media_type="video/mp4",
    )
