"""Tier 1 Feature Tests: Thread-safe in-memory JobManager repository and event bus."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import pytest

from src.models.schemas import (
    ClipSegment,
    EditDecisionList,
    JobStatus,
    VideoJob,
)
from src.pipeline.job_manager import (
    InvalidStateTransitionError,
    JobEvent,
    JobEventType,
    JobManager,
    JobNotFoundError,
)


@pytest.mark.tier1
class TestJobManagerCRUD:
    """Unit tests for JobManager creation, retrieval, and deletion."""

    def test_create_and_get_job(self) -> None:
        jm = JobManager()
        job = jm.create_job("ingest/sample_raw.mp4", file_size_bytes=5000)

        assert job.job_id is not None
        assert job.filename == "sample_raw.mp4"
        assert job.file_size_bytes == 5000
        assert job.status in (JobStatus.INGESTED, JobStatus.DETECTED)

        fetched = jm.get_job(job.job_id)
        assert fetched is not None
        assert fetched.job_id == job.job_id

        # Explicit initial_status
        job_detected = jm.create_job("ingest/clip2.mp4", initial_status=JobStatus.DETECTED)
        assert job_detected.status == JobStatus.DETECTED

    def test_get_job_or_raise_not_found(self) -> None:
        jm = JobManager()
        with pytest.raises(JobNotFoundError) as excinfo:
            jm.get_job_or_raise("nonexistent_id_999")
        assert "nonexistent_id_999" in str(excinfo.value)

    def test_delete_and_clear_jobs(self) -> None:
        jm = JobManager()
        j1 = jm.create_job("clip1.mp4")
        j2 = jm.create_job("clip2.mp4")

        assert jm.count_jobs() == 2
        assert jm.delete_job(j1.job_id) is True
        assert jm.delete_job(j1.job_id) is False
        assert jm.count_jobs() == 1

        jm.clear()
        assert jm.count_jobs() == 0


@pytest.mark.tier1
class TestJobManagerMutations:
    """Unit tests for status, progress, EDL, and metadata mutations."""

    def test_status_transition_fsm_validation(self) -> None:
        jm = JobManager()
        job = jm.create_job("ingest/video.mp4", initial_status=JobStatus.DETECTED)

        # Valid transitions
        job = jm.update_status(job.job_id, JobStatus.INGESTING)
        assert job.status == JobStatus.INGESTING

        job = jm.update_status(job.job_id, JobStatus.INGESTED)
        assert job.status == JobStatus.INGESTED

        # Invalid transition
        with pytest.raises(InvalidStateTransitionError):
            jm.update_status(job.job_id, JobStatus.DELIVERED)

    def test_progress_clamping(self) -> None:
        jm = JobManager()
        job = jm.create_job("video.mp4")

        jm.update_progress(job.job_id, 45.5)
        assert jm.get_job(job.job_id).progress_percent == 45.5

        jm.update_progress(job.job_id, -10.0)
        assert jm.get_job(job.job_id).progress_percent == 0.0

        jm.update_progress(job.job_id, 150.0)
        assert jm.get_job(job.job_id).progress_percent == 100.0

    def test_update_edl_and_override_flag(self) -> None:
        jm = JobManager()
        job = jm.create_job("video.mp4")

        edl = EditDecisionList(
            job_id=job.job_id,
            source_video_path="video.mp4",
            segments=[ClipSegment(source_in_sec=0.0, source_out_sec=2.0)],
        )

        jm.update_edl(job.job_id, edl, is_override=False)
        assert jm.get_job(job.job_id).active_edl.manual_override_applied is False

        jm.update_edl(job.job_id, edl, is_override=True)
        assert jm.get_job(job.job_id).active_edl.manual_override_applied is True

    def test_update_probe_metadata_and_delivery_path(self) -> None:
        jm = JobManager()
        job = jm.create_job("video.mp4")

        meta = {"width": 1920, "height": 1080, "fps": 30.0}
        jm.update_probe_metadata(job.job_id, meta)
        assert jm.get_job(job.job_id).probe_metadata == meta

        jm.set_delivery_path(job.job_id, "delivery/final.mp4")
        assert "final.mp4" in jm.get_job(job.job_id).delivery_filepath


@pytest.mark.tier1
class TestJobManagerQuerying:
    """Unit tests for querying, filtering, sorting, and pagination."""

    def test_list_and_count_jobs_by_status(self) -> None:
        jm = JobManager()
        j1 = jm.create_job("v1.mp4", initial_status=JobStatus.DETECTED)
        j2 = jm.create_job("v2.mp4", initial_status=JobStatus.INGESTED)
        j3 = jm.create_job("v3.mp4", initial_status=JobStatus.INGESTED)

        assert jm.count_jobs() == 3
        assert jm.count_jobs(JobStatus.INGESTED) == 2
        assert jm.count_jobs(JobStatus.DETECTED) == 1

        ingested_jobs = jm.list_jobs(status=JobStatus.INGESTED)
        assert len(ingested_jobs) == 2
        assert all(j.status == JobStatus.INGESTED for j in ingested_jobs)

    def test_active_only_filter(self) -> None:
        jm = JobManager()
        j1 = jm.create_job("v1.mp4", initial_status=JobStatus.DETECTED)
        j2 = jm.create_job("v2.mp4", initial_status=JobStatus.DELIVERED)
        j3 = jm.create_job("v3.mp4", initial_status=JobStatus.FAILED)

        active = jm.list_jobs(active_only=True)
        assert len(active) == 1
        assert active[0].job_id == j1.job_id

    def test_pagination(self) -> None:
        jm = JobManager()
        for i in range(10):
            jm.create_job(f"video_{i}.mp4")

        page1 = jm.list_jobs(limit=4, offset=0)
        page2 = jm.list_jobs(limit=4, offset=4)
        page3 = jm.list_jobs(limit=4, offset=8)

        assert len(page1) == 4
        assert len(page2) == 4
        assert len(page3) == 2


@pytest.mark.tier1
class TestJobManagerPubSub:
    """Unit tests for synchronous and asynchronous pub/sub event subscriptions."""

    def test_sync_event_subscription(self) -> None:
        jm = JobManager()
        events_received: list[JobEvent] = []

        def on_event(event: JobEvent) -> None:
            events_received.append(event)

        sub_id = jm.subscribe(JobEventType.CREATED, on_event)

        j = jm.create_job("video.mp4")
        assert len(events_received) == 1
        assert events_received[0].event_type == JobEventType.CREATED
        assert events_received[0].job_id == j.job_id

        # Unsubscribe
        assert jm.unsubscribe(sub_id) is True
        jm.create_job("video2.mp4")
        assert len(events_received) == 1

    @pytest.mark.asyncio
    async def test_async_event_subscription(self) -> None:
        jm = JobManager()
        async_events: list[JobEvent] = []

        async def on_async_event(event: JobEvent) -> None:
            async_events.append(event)

        jm.subscribe(JobEventType.ALL, on_async_event)

        j = jm.create_job("video_async.mp4")
        # Give event loop a tick to process background tasks
        await asyncio.sleep(0.05)

        assert len(async_events) >= 1
        assert any(e.job_id == j.job_id for e in async_events)


@pytest.mark.tier1
class TestJobManagerConcurrency:
    """Unit test for thread-safety under heavy concurrent multi-threaded workload."""

    def test_concurrent_job_creation_and_mutations(self) -> None:
        jm = JobManager()
        num_workers = 30
        iterations_per_worker = 20
        created_ids: list[str] = []
        lock = threading.Lock()

        def worker_task(worker_idx: int) -> None:
            for i in range(iterations_per_worker):
                job = jm.create_job(f"clip_{worker_idx}_{i}.mp4")
                with lock:
                    created_ids.append(job.job_id)

                jm.update_progress(job.job_id, (i / iterations_per_worker) * 100.0)

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker_task, idx) for idx in range(num_workers)]
            for f in futures:
                f.result()

        total_expected = num_workers * iterations_per_worker
        assert jm.count_jobs() == total_expected
        assert len(created_ids) == total_expected
