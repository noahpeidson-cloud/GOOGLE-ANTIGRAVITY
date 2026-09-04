"""Tier 1 Feature Tests: PipelineOrchestrator coordination and workflow execution."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict
import pytest

from config.settings import AppSettings
from src.models.schemas import (
    ClipSegment,
    ColorGradeSettings,
    EditDecisionList,
    JobStatus,
    MediaProbeResult,
    VideoStreamMetadata,
)
from src.pipeline.job_manager import JobManager
from src.pipeline.orchestrator import PipelineOrchestrator


class MockMLProvider:
    """Mock ML Brain provider for deterministic pipeline testing."""

    async def grade_video_async(self, file_path: Path, probe_data: Any) -> EditDecisionList:
        return EditDecisionList(
            job_id="mock_job",
            source_video_path=str(file_path),
            target_resolution=(1920, 1080),
            target_fps=30.0,
            segments=[
                ClipSegment(clip_id="seg1", source_in_sec=0.0, source_out_sec=2.0, label="intro_drop"),
            ],
            color_grade=ColorGradeSettings(contrast=1.1, saturation=1.2),
        )


@pytest.mark.tier1
class TestPipelineOrchestratorWorkflows:
    """Unit tests for PipelineOrchestrator workflows and lifecycle."""

    @pytest.mark.asyncio
    async def test_standard_ingest_to_awaiting_override(
        self,
        tmp_path: Path,
        procedural_1080p_clip: Path,
    ) -> None:
        settings = AppSettings(
            ingest_dir=tmp_path / "ingest",
            delivery_dir=tmp_path / "delivery",
            temp_dir=tmp_path / "tmp",
        )
        jm = JobManager()
        ml = MockMLProvider()

        orchestrator = PipelineOrchestrator(
            settings=settings,
            job_manager=jm,
            ml_provider=ml,
            auto_approve=False,
        )
        await orchestrator.start()

        job = await orchestrator.handle_file_ingested(procedural_1080p_clip)

        assert job.status == JobStatus.AWAITING_OVERRIDE
        assert job.probe_metadata is not None
        assert job.active_edl is not None
        assert job.active_edl.segment_count == 1
        assert job.active_edl.manual_override_applied is False

        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_auto_approve_transitions_to_rendering(
        self,
        tmp_path: Path,
        procedural_1080p_clip: Path,
    ) -> None:
        settings = AppSettings(
            ingest_dir=tmp_path / "ingest",
            delivery_dir=tmp_path / "delivery",
            temp_dir=tmp_path / "tmp",
        )
        jm = JobManager()
        ml = MockMLProvider()

        orchestrator = PipelineOrchestrator(
            settings=settings,
            job_manager=jm,
            ml_provider=ml,
            auto_approve=True,
        )
        await orchestrator.start()

        job = await orchestrator.handle_file_ingested(procedural_1080p_clip)

        assert job.status == JobStatus.RENDERING
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_probe_failure_transitions_to_failed(
        self,
        tmp_path: Path,
        corrupt_media_file: Path,
    ) -> None:
        settings = AppSettings(
            ingest_dir=tmp_path / "ingest",
            delivery_dir=tmp_path / "delivery",
            temp_dir=tmp_path / "tmp",
        )
        jm = JobManager()

        orchestrator = PipelineOrchestrator(
            settings=settings,
            job_manager=jm,
            auto_approve=False,
        )
        await orchestrator.start()

        job = await orchestrator.handle_file_ingested(corrupt_media_file)

        assert job.status == JobStatus.FAILED
        assert job.error_message is not None
        assert "probe" in job.error_message.lower() or "failed" in job.error_message.lower() or "corrupt" in job.error_message.lower()

        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_user_edl_override_and_approval(
        self,
        tmp_path: Path,
        procedural_1080p_clip: Path,
    ) -> None:
        settings = AppSettings(
            ingest_dir=tmp_path / "ingest",
            delivery_dir=tmp_path / "delivery",
            temp_dir=tmp_path / "tmp",
        )
        jm = JobManager()
        ml = MockMLProvider()

        orchestrator = PipelineOrchestrator(
            settings=settings,
            job_manager=jm,
            ml_provider=ml,
            auto_approve=False,
        )
        await orchestrator.start()

        job = await orchestrator.handle_file_ingested(procedural_1080p_clip)
        assert job.status == JobStatus.AWAITING_OVERRIDE

        # Editor applies override
        custom_edl = EditDecisionList(
            job_id=job.job_id,
            source_video_path=str(procedural_1080p_clip),
            target_resolution=(1080, 1920),
            segments=[
                ClipSegment(clip_id="custom1", source_in_sec=0.5, source_out_sec=1.8),
            ],
            color_grade=ColorGradeSettings(contrast=1.3),
        )

        job = await orchestrator.override_edl(job.job_id, custom_edl)
        assert job.status == JobStatus.OVERRIDE_APPLIED
        assert job.active_edl.manual_override_applied is True
        assert job.active_edl.target_resolution == (1080, 1920)

        # Editor approves job for rendering
        job = await orchestrator.approve_job(job.job_id)
        assert job.status == JobStatus.RENDERING

        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_regrade_workflow(
        self,
        tmp_path: Path,
        procedural_1080p_clip: Path,
    ) -> None:
        settings = AppSettings(
            ingest_dir=tmp_path / "ingest",
            delivery_dir=tmp_path / "delivery",
            temp_dir=tmp_path / "tmp",
        )
        jm = JobManager()
        ml = MockMLProvider()

        orchestrator = PipelineOrchestrator(
            settings=settings,
            job_manager=jm,
            ml_provider=ml,
            auto_approve=False,
        )
        await orchestrator.start()

        job = await orchestrator.handle_file_ingested(procedural_1080p_clip)
        assert job.status == JobStatus.AWAITING_OVERRIDE

        job = await orchestrator.regrade_job(job.job_id)
        assert job.status == JobStatus.AWAITING_OVERRIDE

        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_watcher_integration_with_file_drop(
        self,
        tmp_path: Path,
    ) -> None:
        from src.watcher.ingest_watcher import IngestWatcher
        from tests.test_infra.media_generator import generate_1080p_video

        ingest_dir = tmp_path / "ingest_watch"
        ingest_dir.mkdir(parents=True, exist_ok=True)

        settings = AppSettings(
            ingest_dir=ingest_dir,
            delivery_dir=tmp_path / "delivery",
            temp_dir=tmp_path / "tmp",
        )
        jm = JobManager()
        ml = MockMLProvider()

        watcher = IngestWatcher(
            watch_dir=ingest_dir,
            debounce_delay_sec=0.05,
            lock_poll_interval_sec=0.05,
            size_debounce_interval_sec=0.05,
        )

        orchestrator = PipelineOrchestrator(
            settings=settings,
            job_manager=jm,
            ml_provider=ml,
            watcher=watcher,
            auto_approve=False,
        )
        await orchestrator.start()

        # Drop a synthetic media file
        target_video = ingest_dir / "dropped_clip.mp4"
        generate_1080p_video(target_video, duration_sec=1.0)

        # Trigger manual scan_once to guarantee fast detection in unit test
        await watcher.scan_once()

        # Wait for processing
        for _ in range(30):
            await asyncio.sleep(0.1)
            jobs = jm.list_jobs()
            if jobs and jobs[0].status == JobStatus.AWAITING_OVERRIDE:
                break

        jobs = jm.list_jobs()
        assert len(jobs) >= 1
        assert jobs[0].status == JobStatus.AWAITING_OVERRIDE
        assert jobs[0].filename == "dropped_clip.mp4"

        await orchestrator.stop()
