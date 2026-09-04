"""Tier 1 Feature Tests: Job State Management and Lifecycle FSM."""

from __future__ import annotations

import pytest

try:
    from src.models.schemas import JobMetadata, JobStatus
    from src.pipeline.job_manager import JobManager, InvalidStateTransitionError
except ImportError:
    JobMetadata = None
    JobStatus = None
    JobManager = None
    InvalidStateTransitionError = Exception


def _check_jm():
    if JobManager is None:
        pytest.skip("src.pipeline.job_manager not yet implemented")


@pytest.fixture
def manager():
    _check_jm()
    return JobManager()


@pytest.mark.tier1
def test_job_repository_create_and_retrieve(manager):
    """Verify creating a job stores it and permits retrieval by ID."""
    job = manager.create_job(source_filepath="ingest/raw_clip.mp4")
    assert job.job_id is not None
    assert job.status in (JobStatus.DETECTED, JobStatus.INGESTED)

    retrieved = manager.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.job_id == job.job_id


@pytest.mark.tier1
def test_job_lifecycle_state_transitions(manager):
    """Verify valid state progression through the FSM to DELIVERED."""
    job = manager.create_job(source_filepath="ingest/raw_clip.mp4", initial_status=JobStatus.DETECTED)
    
    manager.update_status(job.job_id, JobStatus.INGESTED)
    assert manager.get_job(job.job_id).status == JobStatus.INGESTED

    manager.update_status(job.job_id, JobStatus.PROBING)
    assert manager.get_job(job.job_id).status == JobStatus.PROBING

    manager.update_status(job.job_id, JobStatus.PROBED)
    assert manager.get_job(job.job_id).status == JobStatus.PROBED

    manager.update_status(job.job_id, JobStatus.GRADING)
    assert manager.get_job(job.job_id).status == JobStatus.GRADING

    manager.update_status(job.job_id, JobStatus.AWAITING_OVERRIDE)
    assert manager.get_job(job.job_id).status == JobStatus.AWAITING_OVERRIDE

    manager.update_status(job.job_id, JobStatus.APPROVED)
    assert manager.get_job(job.job_id).status == JobStatus.APPROVED

    manager.update_status(job.job_id, JobStatus.RENDERING)
    assert manager.get_job(job.job_id).status == JobStatus.RENDERING

    manager.update_status(job.job_id, JobStatus.DELIVERED)
    assert manager.get_job(job.job_id).status == JobStatus.DELIVERED


@pytest.mark.tier1
def test_invalid_state_transition_handling(manager):
    """Verify invalid state transitions raise InvalidStateTransitionError."""
    job = manager.create_job(source_filepath="ingest/raw_clip.mp4", initial_status=JobStatus.DETECTED)
    with pytest.raises(InvalidStateTransitionError):
        manager.update_status(job.job_id, JobStatus.DELIVERED)


@pytest.mark.tier1
def test_job_progress_tracking(manager):
    """Verify job progress percentage updates accurately."""
    job = manager.create_job(source_filepath="ingest/raw_clip.mp4")
    manager.update_progress(job.job_id, 45.5)
    updated = manager.get_job(job.job_id)
    assert updated.progress_percent == 45.5


@pytest.mark.tier1
def test_job_repository_list_all(manager):
    """Verify listing jobs returns all registered jobs."""
    j1 = manager.create_job(source_filepath="ingest/clip1.mp4")
    j2 = manager.create_job(source_filepath="ingest/clip2.mp4")
    all_jobs = manager.list_jobs()
    ids = [j.job_id for j in all_jobs]
    assert j1.job_id in ids
    assert j2.job_id in ids


@pytest.mark.tier1
def test_job_repository_thread_safety(manager):
    """Verify concurrent job creations and updates maintain state integrity."""
    import concurrent.futures

    def create_and_update(i: int):
        j = manager.create_job(source_filepath=f"ingest/clip_{i}.mp4")
        manager.update_progress(j.job_id, float(i))
        return j.job_id

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create_and_update, range(20)))

    assert len(results) == 20
    assert len(manager.list_jobs()) >= 20


@pytest.mark.tier1
def test_job_repository_get_nonexistent(manager):
    """Verify get_job with non-existent ID returns None."""
    assert manager.get_job("non_existent_id_xyz") is None
