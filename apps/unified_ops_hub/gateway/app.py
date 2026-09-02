"""Unified Ops Hub Gateway & FastAPI Resiliency Application.
Integrates domain routers (/api/v1/health, /api/v1/sports, /api/v1/media, /api/v1/ml, /api/v1/dlq),
circuit breakers, dynamic port allocation, and automatic DLQ exception isolation.
"""

import os
import uuid
import time
import asyncio
import traceback
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, Request, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from unified_ops_hub.gateway.port_manager import PortManager
from unified_ops_hub.gateway.dlq_manager import (
    DLQManager,
    ErrorCategory,
    IncidentStatus,
)
from unified_ops_hub.gateway.renderer import (
    FFmpegRenderer,
    RenderRequest,
    RenderResponse,
)
from unified_ops_hub.gateway.media_catalog import MediaCatalogManager

logger = logging.getLogger("unified_ops_hub.gateway")


# ============================================================================
# Pydantic Request / Response Models
# ============================================================================

class SportsCardCaptureRequest(BaseModel):
    player: str = Field(..., min_length=1)
    year: str = "2024"
    set_name: str = "Standard"
    card_number: str = "1"
    category: str = "Basketball"
    condition: str = "Raw"
    investment: float = 0.0
    estimated_value: float = 0.0
    notes: Optional[str] = None


class VideoTriggerRequest(BaseModel):
    clip_name: str
    mode: str = "vertical_reframes"
    priority: str = "NORMAL"


class VideoGradeRequest(BaseModel):
    video_id: str
    scores: Dict[str, float]
    aspect_ratio: str = "9:16"


class MLFeedbackRequest(BaseModel):
    video_id: str
    actual_views: int = 0
    actual_shares: int = 0


class CrashSimulationRequest(BaseModel):
    error_type: str = "RuntimeException"
    trigger: bool = True


class GradeSelectedRequest(BaseModel):
    media_ids: List[str]


# ============================================================================
# In-Memory Domain State Stores (for Unified Hub integration)
# ============================================================================

class GatewayState:
    """Manages in-memory state for gateway domain routers."""
    def __init__(self) -> None:
        self.start_time = time.time()
        self.cards_staging: List[Dict[str, Any]] = []
        self.media_jobs: Dict[str, Dict[str, Any]] = {}
        self.model_weights = {
            "HRV": 0.25,
            "DPAW": 0.25,
            "ADR_SFD": 0.20,
            "CKE_MVE": 0.15,
            "LTSS": 0.15,
        }
        self.feedback_records: List[Dict[str, Any]] = []
        self.active_platform: str = "tiktok"
        self.active_lens: str = "android_ui_dump"
        self.poll_interval_sec: int = 3600
        self.retry_backoff_base_sec: float = 2.0
        self.clusters: Dict[str, int] = {
            "c0_healthy": 78,
            "c1_throttled": 15,
            "c2_failover": 7,
        }
        self.entropy: float = 0.042
        self.trending_sounds: List[Dict[str, Any]] = [
            {
                "id": "SND_001",
                "sound_title": "Ultra Miami 2026 Mainstage ID",
                "creator": "Martin Garrix",
                "hashtag": "#Ultra2026",
                "likes": 1420000,
                "velocity": 98.4,
                "lens": "android_ui_dump",
            },
            {
                "id": "SND_002",
                "sound_title": "Hardwell Rebel ID Drop",
                "creator": "Hardwell",
                "hashtag": "#BigRoomNeverDies",
                "likes": 890000,
                "velocity": 91.2,
                "lens": "android_ui_dump",
            },
            {
                "id": "SND_003",
                "sound_title": "Subtronics Heavy Bass Flip",
                "creator": "Subtronics",
                "hashtag": "#EDMDrop",
                "likes": 640000,
                "velocity": 87.6,
                "lens": "android_ui_dump",
            },
        ]


# ============================================================================
# Domain Routers
# ============================================================================

def create_health_router(app_state: GatewayState) -> APIRouter:
    router = APIRouter(prefix="/api/v1/health", tags=["Health"])

    @router.get("")
    async def get_health(request: Request):
        port_mgr: PortManager = request.app.state.port_manager
        dlq_mgr: DLQManager = request.app.state.dlq_manager
        
        uptime = round(time.time() - app_state.start_time, 2)
        port_status = port_mgr.get_port_status()
        dlq_stats = dlq_mgr.get_stats()

        return {
            "status": "HEALTHY",
            "version": "1.0.0",
            "uptime_seconds": uptime,
            "ports": port_status,
            "dlq_stats": dlq_stats,
            "services": {
                "sports_cards": "READY",
                "media_pipeline": "READY",
                "ml_grading": "READY",
                "dlq_gateway": "ACTIVE",
            },
        }

    @router.get("/ports")
    async def get_ports(request: Request):
        port_mgr: PortManager = request.app.state.port_manager
        return port_mgr.get_port_status()

    return router


def create_sports_router(app_state: GatewayState) -> APIRouter:
    router = APIRouter(prefix="/api/v1/sports", tags=["Sports Cards"])

    @router.get("/health")
    async def sports_health():
        return {"status": "READY", "staged_count": len(app_state.cards_staging)}

    @router.post("/capture")
    async def capture_card(card: SportsCardCaptureRequest):
        card_id = f"CARD_{uuid.uuid4().hex[:8]}"
        card_record = {
            "id": card_id,
            "player": card.player,
            "year": card.year,
            "set_name": card.set_name,
            "card_number": card.card_number,
            "category": card.category,
            "condition": card.condition,
            "investment": card.investment,
            "estimated_value": card.estimated_value,
            "ai_status": "CLEARED",
            "captured_at": time.time(),
        }
        app_state.cards_staging.append(card_record)
        return card_record

    @router.get("/staging")
    async def get_staging():
        return {
            "total": len(app_state.cards_staging),
            "cards": app_state.cards_staging,
        }

    @router.get("/stats")
    async def get_stats():
        total_inv = sum(c.get("investment", 0.0) for c in app_state.cards_staging)
        total_val = sum(c.get("estimated_value", 0.0) for c in app_state.cards_staging)
        return {
            "total_cards": len(app_state.cards_staging),
            "total_investment": total_inv,
            "total_estimated_value": total_val,
        }

    return router


def create_media_router(app_state: GatewayState) -> APIRouter:
    router = APIRouter(prefix="/api/v1/media", tags=["Media Pipeline"])

    @router.get("/health")
    async def media_health():
        return {"status": "READY", "active_jobs": len(app_state.media_jobs)}

    @router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
    async def trigger_pipeline(req: VideoTriggerRequest):
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job_data = {
            "job_id": job_id,
            "clip_name": req.clip_name,
            "mode": req.mode,
            "status": "QUEUED",
            "progress": 0.0,
            "created_at": time.time(),
        }
        app_state.media_jobs[job_id] = job_data
        return job_data

    @router.get("/status/{job_id}")
    async def get_job_status(job_id: str):
        if job_id not in app_state.media_jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
        return app_state.media_jobs[job_id]

    @router.get("/proxies")
    async def get_proxies():
        return {
            "proxies": [
                {"clip_id": "proxy_drop_01.mp4", "resolution": "720p", "fps": 60},
                {"clip_id": "proxy_drop_02.mp4", "resolution": "720p", "fps": 60},
            ]
        }

    @router.post("/render", response_model=RenderResponse, status_code=status.HTTP_200_OK)
    async def render_media_endpoint(
        req: RenderRequest,
        background_tasks: BackgroundTasks,
        request: Request,
    ):
        """Headless FFmpeg video rendering endpoint supporting synchronous and async background jobs."""
        if req.in_point >= req.out_point:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"in_point ({req.in_point}) must be strictly less than out_point ({req.out_point})"
            )

        # Resolve or initialize renderer
        renderer: Optional[FFmpegRenderer] = getattr(request.app.state, "renderer", None)
        if renderer is None:
            renderer = FFmpegRenderer()
            request.app.state.renderer = renderer

        # Validate source file existence
        try:
            resolved_source = renderer._resolve_source_path(req.source_file)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source video file not found: {req.source_file}"
            )

        if req.sync:
            try:
                result = await asyncio.to_thread(renderer.render_sync, req)
                app_state.media_jobs[result.job_id] = result.model_dump()
                return result
            except Exception as exc:
                dlq_mgr: DLQManager = request.app.state.dlq_manager
                dlq_mgr.record_failure(
                    source_service="media_renderer",
                    error_category=ErrorCategory.UNHANDLED_EXCEPTION,
                    error_message=f"Sync render failed: {str(exc)}",
                    payload=req.model_dump(),
                    traceback_str=traceback.format_exc(),
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Render execution failed: {str(exc)}"
                )
        else:
            job_id = f"render_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            duration = round(req.out_point - req.in_point, 3)
            initial_job = RenderResponse(
                status="QUEUED",
                job_id=job_id,
                render_id=job_id,
                source_file=str(resolved_source),
                in_point=req.in_point,
                out_point=req.out_point,
                duration=duration,
                crop_ratio=req.crop_ratio,
                text_overlay=req.text_overlay,
                message="Render job queued for background execution",
                created_at=time.time(),
            )
            app_state.media_jobs[job_id] = initial_job.model_dump()
            background_tasks.add_task(
                renderer.execute_background_render, req, job_id, app_state
            )
            return initial_job

    @router.get("/renders")
    async def list_renders():
        """Returns catalog of rendered video files available on disk."""
        renders_dir = Path(os.getcwd()) / "renders"
        if not renders_dir.exists():
            return {"total": 0, "renders": []}

        files = []
        for p in renders_dir.glob("*.mp4"):
            stat = p.stat()
            files.append({
                "filename": p.name,
                "file_path": str(p),
                "url": f"/renders/{p.name}",
                "size_bytes": stat.st_size,
                "mtime": stat.st_mtime,
            })
        return {
            "total": len(files),
            "renders": sorted(files, key=lambda x: x["mtime"], reverse=True),
        }

    @router.get("/catalog")
    async def get_catalog(request: Request):
        return request.app.state.media_catalog.get_full_catalog()

    @router.post("/catalog/grade")
    async def trigger_grade_selected(req: GradeSelectedRequest, request: Request):
        catalog: MediaCatalogManager = request.app.state.media_catalog
        for mid in req.media_ids:
            catalog.update_grading_status(mid, "QUEUED")
        return {"status": "QUEUED", "media_ids": req.media_ids}

    return router


def create_ml_router(app_state: GatewayState) -> APIRouter:
    router = APIRouter(prefix="/api/v1/ml", tags=["ML Grading"])

    @router.get("/health")
    async def ml_health():
        return {"status": "READY", "weights": app_state.model_weights}

    @router.post("/grade")
    async def grade_video(req: VideoGradeRequest):
        scores = req.scores
        hrv = scores.get("HRV", 50.0)
        dpaw = scores.get("DPAW", 50.0)
        adr_sfd = scores.get("ADR_SFD", 50.0)
        cke_mve = scores.get("CKE_MVE", 50.0)
        ltss = scores.get("LTSS", 50.0)

        w = app_state.model_weights
        composite = (
            hrv * w["HRV"]
            + dpaw * w["DPAW"]
            + adr_sfd * w["ADR_SFD"]
            + cke_mve * w["CKE_MVE"]
            + ltss * w["LTSS"]
        )

        # Killswitch 1: Low HRV hook retention (<40) caps EVPI at 49.9
        if hrv < 40.0:
            composite = min(composite, 49.9)

        # Killswitch 2: 16:9 Aspect Ratio penalty (50% reduction for Shorts/Reels)
        if req.aspect_ratio == "16:9":
            composite *= 0.5

        composite = round(composite, 2)

        # Verdict classification
        if composite >= 85.0:
            verdict = "VIRAL_READY"
        elif composite >= 70.0:
            verdict = "HIGH_POTENTIAL"
        elif composite >= 50.0:
            verdict = "MODERATE_REACH"
        else:
            verdict = "LOW_REACH"

        return {
            "video_id": req.video_id,
            "evpi": composite,
            "verdict": verdict,
            "scores": scores,
            "aspect_ratio": req.aspect_ratio,
        }

    @router.get("/weights")
    async def get_weights():
        return {"weights": app_state.model_weights}

    @router.post("/feedback")
    async def ingest_feedback(feedback: MLFeedbackRequest):
        app_state.feedback_records.append(feedback.model_dump())
        return {"status": "INGESTED", "records_count": len(app_state.feedback_records)}

    return router


def create_dlq_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/dlq", tags=["Dead Letter Queue"])

    @router.get("/incidents")
    async def list_incidents(
        request: Request,
        status: Optional[str] = None,
        category: Optional[str] = None,
        source_service: Optional[str] = None,
        limit: int = 100,
    ):
        dlq_mgr: DLQManager = request.app.state.dlq_manager
        incidents = dlq_mgr.list_incidents(
            status=IncidentStatus(status) if status else None,
            category=ErrorCategory(category) if category else None,
            source_service=source_service,
            limit=limit,
        )
        return {"incidents": [inc.to_dict() for inc in incidents], "count": len(incidents)}

    @router.get("/incidents/{incident_id}")
    async def get_incident(request: Request, incident_id: str):
        dlq_mgr: DLQManager = request.app.state.dlq_manager
        incident = dlq_mgr.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")
        return incident.to_dict()

    @router.post("/retry/{incident_id}")
    async def retry_incident(request: Request, incident_id: str):
        dlq_mgr: DLQManager = request.app.state.dlq_manager
        result = dlq_mgr.replay_incident(incident_id)
        return result

    @router.get("/stats")
    async def get_stats(request: Request):
        dlq_mgr: DLQManager = request.app.state.dlq_manager
        return dlq_mgr.get_stats()

    @router.post("/purge")
    async def purge_resolved(request: Request):
        dlq_mgr: DLQManager = request.app.state.dlq_manager
        deleted = dlq_mgr.purge_resolved()
        return {"deleted_count": deleted}

    return router


def create_agent_router(app_state: GatewayState) -> APIRouter:
    router = APIRouter(prefix="/api/v1/agent", tags=["Agent Telemetry"])

    @router.get("/telemetry")
    async def get_telemetry():
        return {
            "platform": app_state.active_platform,
            "active_lens": app_state.active_lens,
            "poll_interval_sec": app_state.poll_interval_sec,
            "retry_backoff_base_sec": app_state.retry_backoff_base_sec,
            "clusters": app_state.clusters,
            "entropy": app_state.entropy,
            "trending_sounds": app_state.trending_sounds,
        }

    return router


def create_viral_router(app_state: GatewayState) -> APIRouter:
    router = APIRouter(prefix="/api/v1/viral", tags=["Viral Pipeline"])

    @router.post("/failover")
    async def trigger_failover(req: Optional[Dict[str, Any]] = None):
        new_lens = "web_a11y_tree" if app_state.active_lens == "android_ui_dump" else "android_ui_dump"
        app_state.active_lens = new_lens
        return {
            "success": True,
            "active_lens": new_lens,
            "reason": f"Swapped lens to {new_lens} per operational feedback.",
        }

    return router


# ============================================================================
# Application Factory with Lifespan & Global Resiliency Exception Handlers
# ============================================================================

def create_app(
    port_manager: Optional[PortManager] = None,
    dlq_manager: Optional[DLQManager] = None,
) -> FastAPI:
    """Factory creating a production-configured FastAPI gateway instance."""
    
    app_state = GatewayState()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: configure port manager & DLQ
        if not hasattr(app.state, "port_manager") or app.state.port_manager is None:
            app.state.port_manager = port_manager or PortManager()
        if not hasattr(app.state, "dlq_manager") or app.state.dlq_manager is None:
            app.state.dlq_manager = dlq_manager or DLQManager()
        if not hasattr(app.state, "media_catalog") or app.state.media_catalog is None:
            app.state.media_catalog = MediaCatalogManager()
            app.state.media_catalog.seed_sample_catalog()

        # Clean stale lock files
        app.state.port_manager.cleanup_stale_locks(max_age_seconds=60)
        logger.info("Unified Ops Hub Gateway initialized successfully.")
        yield
        # Shutdown cleanup
        logger.info("Unified Ops Hub Gateway shutting down.")

    app = FastAPI(
        title="Unified Ops Hub Gateway",
        description="Unified Resilient Microservices Gateway & Dead Letter Queue Architecture",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Attach managers directly
    app.state.port_manager = port_manager or PortManager()
    app.state.dlq_manager = dlq_manager or DLQManager()
    app.state.gateway_state = app_state

    # Cross-Origin Resource Sharing (CORS) Middleware for Dashboard Frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static Media File Serving
    renders_dir = Path(os.getcwd()) / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/renders", StaticFiles(directory=str(renders_dir)), name="renders")

    proxies_dir = Path(os.getcwd()) / "proxies"
    proxies_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/proxies", StaticFiles(directory=str(proxies_dir)), name="proxies")

    # Mount domain routers
    app.include_router(create_health_router(app_state))
    app.include_router(create_sports_router(app_state))
    app.include_router(create_media_router(app_state))
    app.include_router(create_ml_router(app_state))
    app.include_router(create_agent_router(app_state))
    app.include_router(create_viral_router(app_state))
    app.include_router(create_dlq_router())

    # Crash simulation endpoint
    @app.post("/api/v1/simulate-crash")
    async def simulate_crash(req: CrashSimulationRequest):
        if req.trigger:
            if req.error_type == "DivisionByZero":
                _ = 1 / 0
            elif req.error_type == "MLGradingCrash":
                raise RuntimeError("Simulated PySpark partition crash in Gemini Omni grading job.")
            else:
                raise RuntimeError(f"Simulated crash of type: {req.error_type}")
        return {"status": "NO_CRASH_TRIGGERED"}

    # Resiliency Exception Handlers: Protects Daemon from Dying
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        dlq_mgr: DLQManager = request.app.state.dlq_manager
        
        # Read raw request body if available
        body = None
        try:
            body = await request.json()
        except Exception:
            body = {"raw_body_error": "Could not parse JSON"}

        incident = dlq_mgr.record_failure(
            source_service="gateway_validation",
            error_category=ErrorCategory.CORRUPTED_PAYLOAD,
            error_message=f"Schema validation error on {request.url.path}: {str(exc)}",
            payload={"path": str(request.url.path), "payload": body, "errors": exc.errors()},
            traceback_str=str(exc),
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": "CORRUPTED_PAYLOAD",
                "message": "Request payload failed schema validation and was quarantined in DLQ.",
                "incident_id": incident.incident_id,
                "status": IncidentStatus.QUARANTINED.value,
                "detail": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        dlq_mgr: DLQManager = request.app.state.dlq_manager
        
        tb = traceback.format_exc()
        category = ErrorCategory.UNHANDLED_EXCEPTION
        exc_str = f"{exc.__class__.__name__}: {str(exc)}"
        if "MLGrading" in exc_str or "Spark" in exc_str:
            category = ErrorCategory.ML_GRADING_FAILURE
        elif "Socket" in exc_str or "10048" in exc_str:
            category = ErrorCategory.SOCKET_COLLISION

        incident = dlq_mgr.record_failure(
            source_service="gateway_global",
            error_category=category,
            error_message=f"Unhandled exception [{exc.__class__.__name__}] on {request.url.path}: {str(exc)}",
            payload={"path": str(request.url.path), "method": request.method, "exception_type": exc.__class__.__name__},
            traceback_str=tb,
        )

        logger.error("Global Resiliency Handler caught exception on %s: %s (DLQ ID: %s)", request.url.path, exc, incident.incident_id)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unhandled server exception occurred. The payload has been safely isolated in the DLQ.",
                "incident_id": incident.incident_id,
                "category": category.value,
                "status": IncidentStatus.QUARANTINED.value,
            },
        )

    return app


# Default module-level application
app = create_app()
