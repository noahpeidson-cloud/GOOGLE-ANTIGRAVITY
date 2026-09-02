"""Pipeline coordinator bridging directory monitoring, media probing, ML grading, and render execution."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Union

from config.settings import AppSettings, get_settings
from src.models.schemas import ClipSegment, EditDecisionList, JobStatus, VideoJob
from src.pipeline.job_manager import JobEvent, JobEventType, JobManager
from src.renderer.ffmpeg_engine import FFmpegRenderer
from src.renderer.probe import async_probe_media, probe_media

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    End-to-end coordinator managing ingestion events, media probing,
    job lifecycle tracking, ML grading triggers, and render execution.
    """

    def __init__(
        self,
        settings: Optional[AppSettings] = None,
        job_manager: Optional[JobManager] = None,
        ml_provider: Optional[Any] = None,
        prober: Optional[Callable[[Union[str, Path]], Any]] = None,
        watcher: Optional[Any] = None,
        renderer: Optional[FFmpegRenderer] = None,
        auto_approve: bool = False,
        max_concurrent_jobs: int = 4,
    ) -> None:
        self.settings = settings or get_settings()
        self.job_manager = job_manager or JobManager()
        self.ml_provider = ml_provider
        self.prober = prober or async_probe_media
        self.watcher = watcher
        self.renderer = renderer or FFmpegRenderer(settings=self.settings)
        self.auto_approve = auto_approve
        self.semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self.active_tasks: Set[asyncio.Task] = set()
        self.is_running = False
        self._logger = logging.getLogger("baptism_of_music_brain.orchestrator")

    async def start(self) -> None:
        """Start directory watcher and initialize pipeline coordinator."""
        if self.is_running:
            return

        self._logger.info("Starting Pipeline Orchestrator...")
        self.settings.ensure_directories()

        if self.watcher:
            self.watcher.set_callback(self._on_file_detected_callback)
            await self.watcher.start()

        self.is_running = True
        self._logger.info("Pipeline Orchestrator is ACTIVE.")

    async def stop(self) -> None:
        """Gracefully shut down watcher and await pending pipeline tasks."""
        if not self.is_running:
            return

        self._logger.info("Stopping Pipeline Orchestrator...")
        self.is_running = False

        if self.watcher:
            await self.watcher.stop()

        if self.active_tasks:
            self._logger.info(f"Draining {len(self.active_tasks)} active tasks...")
            for task in list(self.active_tasks):
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self.active_tasks, return_exceptions=True)
            self.active_tasks.clear()

        self._logger.info("Pipeline Orchestrator shutdown complete.")

    def _on_file_detected_callback(self, file_path: Path) -> None:
        """Thread-safe entrypoint called by IngestWatcher when a file is stable & unlocked."""
        if not self.is_running:
            return

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self.handle_file_ingested(file_path))
            self.active_tasks.add(task)
            task.add_done_callback(self.active_tasks.discard)
        except RuntimeError:
            self._logger.error("No running event loop to schedule file ingestion task.")

    async def handle_file_ingested(self, file_path: Union[Path, str]) -> VideoJob:
        """
        Execute full ingestion pipeline for a video file:
        1. Register job in JobManager (DETECTED -> INGESTED)
        2. Probe media metadata via FFprobe
        3. Trigger ML grading loop (Gemini Omni / Mock)
        4. Transition to AWAITING_OVERRIDE (or APPROVED -> RENDERING if auto_approve=True)
        """
        path = Path(file_path).resolve()
        file_size = path.stat().st_size if path.exists() else 0

        # Step 1: Create Job Record
        job = self.job_manager.create_job(
            source_filepath=str(path),
            initial_status=JobStatus.DETECTED,
            file_size_bytes=file_size,
        )
        job_id = job.job_id

        async with self.semaphore:
            try:
                # Transition DETECTED -> INGESTING -> INGESTED
                self.job_manager.update_status(job_id, JobStatus.INGESTING)
                self.job_manager.update_status(job_id, JobStatus.INGESTED)

                # Step 2: Probe Media Metadata
                self.job_manager.update_status(job_id, JobStatus.PROBING)
                self._logger.info(f"Probing media metadata for job {job_id} ({path.name})...")
                probe_data = None
                if self.prober:
                    if asyncio.iscoroutinefunction(self.prober):
                        probe_data = await self.prober(path)
                    else:
                        probe_data = await asyncio.to_thread(self.prober, path)

                    if hasattr(probe_data, "model_dump"):
                        self.job_manager.update_probe_metadata(job_id, probe_data.model_dump())
                    elif isinstance(probe_data, dict):
                        self.job_manager.update_probe_metadata(job_id, probe_data)

                self.job_manager.update_status(job_id, JobStatus.PROBED)

                # Step 3: Trigger ML Grading Loop
                self.job_manager.update_status(job_id, JobStatus.ML_GRADING)
                self._logger.info(f"Triggering ML grading for job {job_id}...")

                edl = None
                if self.ml_provider:
                    if hasattr(self.ml_provider, "grade_video_async"):
                        edl = await self.ml_provider.grade_video_async(path, probe_data)
                    elif hasattr(self.ml_provider, "grade_video"):
                        edl = await asyncio.to_thread(self.ml_provider.grade_video, path, probe_data)
                    elif callable(self.ml_provider):
                        if asyncio.iscoroutinefunction(self.ml_provider):
                            edl = await self.ml_provider(path, probe_data)
                        else:
                            edl = await asyncio.to_thread(self.ml_provider, path, probe_data)

                if edl is not None:
                    self.job_manager.update_edl(job_id, edl, is_override=False)

                # Step 4: Approval / Override Handoff
                if self.auto_approve:
                    self._logger.info(f"Auto-approve enabled. Transitioning job {job_id} to APPROVED -> RENDERING...")
                    self.job_manager.update_status(job_id, JobStatus.APPROVED)
                    self.job_manager.update_status(job_id, JobStatus.RENDERING)
                    if self.renderer:
                        render_task = asyncio.create_task(self.render_job(job_id))
                        self.active_tasks.add(render_task)
                        render_task.add_done_callback(self.active_tasks.discard)
                else:
                    self._logger.info(f"Job {job_id} is now AWAITING_OVERRIDE.")
                    self.job_manager.update_status(job_id, JobStatus.AWAITING_OVERRIDE)

                return self.job_manager.get_job_or_raise(job_id)

            except Exception as exc:
                self._logger.exception(f"Pipeline error processing job {job_id}: {exc}")
                self.job_manager.update_status(job_id, JobStatus.FAILED, error_message=str(exc))
                return self.job_manager.get_job_or_raise(job_id)

    async def approve_job(self, job_id: str, trigger_render: bool = True) -> VideoJob:
        """
        Approve EDL and transition job from AWAITING_OVERRIDE / OVERRIDDEN / OVERRIDE_APPLIED
        to APPROVED -> RENDERING. Optionally schedules the render execution task.
        """
        job = self.job_manager.get_job_or_raise(job_id)
        if job.status not in (JobStatus.AWAITING_OVERRIDE, JobStatus.OVERRIDDEN, JobStatus.OVERRIDE_APPLIED):
            raise ValueError(f"Job {job_id} cannot be approved in state {job.status}.")

        self.job_manager.update_status(job_id, JobStatus.APPROVED)
        self.job_manager.update_status(job_id, JobStatus.RENDERING)

        if trigger_render and self.renderer:
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(self.render_job(job_id))
                self.active_tasks.add(task)
                task.add_done_callback(self.active_tasks.discard)
            except RuntimeError:
                pass

        return self.job_manager.get_job_or_raise(job_id)

    async def render_job(self, job_id: str) -> VideoJob:
        """
        Execute FFmpeg rendering for a job with real-time progress callbacks,
        update job state to DELIVERED, and record delivery file path.
        """
        job = self.job_manager.get_job_or_raise(job_id)
        edl = job.active_edl
        if not edl:
            # Construct baseline fallback EDL if missing
            edl = EditDecisionList(
                job_id=job_id,
                source_video_path=job.source_filepath,
                target_resolution=(1920, 1080),
                target_fps=30.0,
                encoding_profile=self.settings.default_profile,
                segments=[ClipSegment(clip_id="seg0", source_in_sec=0.0, source_out_sec=5.0)],
            )
            self.job_manager.update_edl(job_id, edl)

        if job.status != JobStatus.RENDERING:
            if job.status in (JobStatus.AWAITING_OVERRIDE, JobStatus.OVERRIDDEN, JobStatus.OVERRIDE_APPLIED):
                self.job_manager.update_status(job_id, JobStatus.APPROVED)
            if job.status == JobStatus.APPROVED:
                self.job_manager.update_status(job_id, JobStatus.RENDERING)

        def on_progress(percent: float) -> None:
            self.job_manager.update_progress(job_id, percent)

        try:
            self._logger.info(f"Rendering job {job_id} with profile {edl.encoding_profile}...")
            delivery_path = await self.renderer.async_render_edl(edl, progress_callback=on_progress)
            self.job_manager.set_delivery_path(job_id, delivery_path)
            self.job_manager.update_progress(job_id, 100.0)
            self.job_manager.update_status(job_id, JobStatus.DELIVERED)
            self._logger.info(f"Job {job_id} successfully rendered and delivered to {delivery_path}")
            return self.job_manager.get_job_or_raise(job_id)
        except Exception as exc:
            self._logger.exception(f"Render failed for job {job_id}: {exc}")
            self.job_manager.update_status(job_id, JobStatus.FAILED, error_message=str(exc))
            return self.job_manager.get_job_or_raise(job_id)

    async def override_edl(self, job_id: str, new_edl: EditDecisionList) -> VideoJob:
        """Apply user modifications to EDL and transition to OVERRIDE_APPLIED."""
        job = self.job_manager.get_job_or_raise(job_id)
        if job.status not in (JobStatus.AWAITING_OVERRIDE, JobStatus.OVERRIDDEN, JobStatus.OVERRIDE_APPLIED):
            raise ValueError(f"EDL overrides cannot be applied to job {job_id} in state {job.status}.")

        self.job_manager.update_edl(job_id, new_edl, is_override=True)
        self.job_manager.update_status(job_id, JobStatus.OVERRIDE_APPLIED)
        return self.job_manager.get_job_or_raise(job_id)

    async def regrade_job(self, job_id: str) -> VideoJob:
        """Trigger re-grading of a job by ML provider."""
        job = self.job_manager.get_job_or_raise(job_id)
        if job.status not in (JobStatus.AWAITING_OVERRIDE, JobStatus.OVERRIDDEN, JobStatus.OVERRIDE_APPLIED):
            raise ValueError(f"Cannot regrade job {job_id} in state {job.status}.")

        self.job_manager.update_status(job_id, JobStatus.ML_GRADING)
        path = Path(job.source_filepath)
        probe_data = job.probe_metadata

        edl = None
        if self.ml_provider:
            if hasattr(self.ml_provider, "grade_video_async"):
                edl = await self.ml_provider.grade_video_async(path, probe_data)
            elif hasattr(self.ml_provider, "grade_video"):
                edl = await asyncio.to_thread(self.ml_provider.grade_video, path, probe_data)

        if edl is not None:
            self.job_manager.update_edl(job_id, edl, is_override=False)

        self.job_manager.update_status(job_id, JobStatus.AWAITING_OVERRIDE)
        return self.job_manager.get_job_or_raise(job_id)
