"""FastAPI application factory, lifespan management, CORS middleware, and global exception handlers."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import AppSettings, get_settings
from src.api.routes import router as api_router
from src.pipeline.job_manager import (
    InvalidStateTransitionError,
    JobManager,
    JobNotFoundError,
)
from src.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


def create_app(
    settings: Optional[AppSettings] = None,
    job_manager: Optional[JobManager] = None,
    orchestrator: Optional[PipelineOrchestrator] = None,
    start_background_orchestrator: bool = False,
) -> FastAPI:
    """
    Factory creating configured FastAPI instance with lifespan event management,
    CORS middleware, error handlers, and mounted REST routers.
    """
    app_settings = settings or get_settings()
    app_job_manager = job_manager or JobManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Lifespan context manager initializing background orchestrators and directories."""
        logger.info(f"Initializing {app_settings.app_name} (v{app_settings.app_version})...")
        app_settings.ensure_directories()

        # Attach singletons to app state
        app.state.settings = app_settings
        app.state.job_manager = app_job_manager

        if orchestrator is not None:
            app.state.orchestrator = orchestrator
        else:
            # Create default orchestrator attached to this job manager
            from src.ml_brain.mock_provider import MockMLProvider
            app.state.orchestrator = PipelineOrchestrator(
                settings=app_settings,
                job_manager=app_job_manager,
                ml_provider=MockMLProvider(),
            )

        if start_background_orchestrator and app.state.orchestrator:
            await app.state.orchestrator.start()

        yield

        # Shutdown cleanup
        logger.info(f"Shutting down {app_settings.app_name}...")
        if app.state.orchestrator and app.state.orchestrator.is_running:
            await app.state.orchestrator.stop()

    app = FastAPI(
        title="baptism_of_music_brain",
        description="Local desktop ML Video Editing Brain & FFmpeg Renderer Control Plane",
        version=app_settings.app_version,
        lifespan=lifespan,
    )

    # Attach initial state objects directly before startup
    app.state.settings = app_settings
    app.state.job_manager = app_job_manager
    if orchestrator is not None:
        app.state.orchestrator = orchestrator
    else:
        from src.ml_brain.mock_provider import MockMLProvider
        app.state.orchestrator = PipelineOrchestrator(
            settings=app_settings,
            job_manager=app_job_manager,
            ml_provider=MockMLProvider(),
        )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Exception Handlers
    @app.exception_handler(JobNotFoundError)
    async def job_not_found_handler(request: Request, exc: JobNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "JobNotFound", "detail": str(exc), "job_id": exc.job_id},
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_transition_handler(request: Request, exc: InvalidStateTransitionError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "InvalidStateTransition", "detail": str(exc), "job_id": exc.job_id},
        )

    # 3. Mount Routers at /api/v1 prefix and root /
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(api_router, prefix="")

    return app
