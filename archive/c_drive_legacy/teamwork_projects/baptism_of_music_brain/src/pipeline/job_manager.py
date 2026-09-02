"""Thread-safe in-memory job repository, querying engine, and pub/sub event bus."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
import logging
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Union
import uuid

from src.models.schemas import EditDecisionList, JobStatus, VideoJob
from src.models.state_machine import (
    InvalidStateTransitionError as FSMInvalidTransitionError,
    validate_transition,
)

logger = logging.getLogger(__name__)


class JobEventType(str, Enum):
    """Lifecycle event types emitted by JobManager."""
    CREATED = "job_created"
    STATUS_CHANGED = "status_changed"
    PROGRESS_UPDATED = "progress_updated"
    EDL_UPDATED = "edl_updated"
    PROBE_COMPLETED = "probe_completed"
    FAILED = "job_failed"
    DELIVERED = "job_delivered"
    DELETED = "job_deleted"
    ALL = "*"


class JobManagerError(ValueError):
    """Base exception for all JobManager operations."""
    pass


class JobNotFoundError(JobManagerError):
    """Raised when a requested job_id does not exist in the repository."""

    def __init__(self, job_id: str):
        super().__init__(f"Job with ID '{job_id}' not found in repository.")
        self.job_id = job_id


class InvalidStateTransitionError(JobManagerError):
    """Raised when an illegal status transition is requested."""

    def __init__(self, job_id: str, from_status: Any, to_status: Any):
        super().__init__(
            f"Invalid state transition for job '{job_id}': cannot transition from {from_status} to {to_status}."
        )
        self.job_id = job_id
        self.from_status = from_status
        self.to_status = to_status


class JobEvent:
    """Event payload emitted during job mutations."""

    def __init__(
        self,
        event_type: JobEventType,
        job_id: str,
        job: VideoJob,
        timestamp: Optional[datetime] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.event_type = event_type
        self.job_id = job_id
        self.job = job
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.details = details or {}


class JobManager:
    """
    Thread-safe in-memory repository for VideoJob instances with FSM validation,
    filtering, pagination, and synchronous/asynchronous pub/sub event subscriptions.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, VideoJob] = {}
        self._lock = threading.RLock()
        self._subscribers: Dict[JobEventType, Dict[str, Callable[[JobEvent], Any]]] = {
            event_type: {} for event_type in JobEventType
        }
        self._logger = logging.getLogger("baptism_of_music_brain.job_manager")

    def create_job(
        self,
        source_filepath: Union[str, Path],
        job_id: Optional[str] = None,
        initial_status: JobStatus = JobStatus.INGESTED,
        file_size_bytes: int = 0,
    ) -> VideoJob:
        """Create and register a new VideoJob in the repository."""
        with self._lock:
            jid = job_id or str(uuid.uuid4())
            str_path = str(Path(source_filepath).resolve())
            filename = Path(source_filepath).name

            job = VideoJob(
                job_id=jid,
                source_filepath=str_path,
                filename=filename,
                file_size_bytes=file_size_bytes,
                status=initial_status,
                progress_percent=0.0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self._jobs[jid] = job
            self._emit_event(JobEventType.CREATED, jid, job, {"initial_status": initial_status.value})
            return job

    def get_job(self, job_id: str) -> Optional[VideoJob]:
        """Retrieve a job by ID, or None if not found."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_job_or_raise(self, job_id: str) -> VideoJob:
        """Retrieve a job by ID or raise JobNotFoundError."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)
            return job

    def update_status(
        self,
        job_id: str,
        new_status: JobStatus,
        error_message: Optional[str] = None,
    ) -> VideoJob:
        """
        Transition job to new_status with FSM validation.
        Emits STATUS_CHANGED and conditionally FAILED / DELIVERED events.
        """
        with self._lock:
            job = self.get_job_or_raise(job_id)
            old_status = job.status

            if old_status != new_status:
                try:
                    validate_transition(old_status, new_status, job_id=job_id)
                except FSMInvalidTransitionError as exc:
                    raise InvalidStateTransitionError(job_id, old_status, new_status) from exc

                job.status = new_status
                job.updated_at = datetime.now(timezone.utc)
                if error_message is not None:
                    job.error_message = error_message

                details = {
                    "previous_status": old_status.value,
                    "new_status": new_status.value,
                    "error_message": error_message,
                }
                self._emit_event(JobEventType.STATUS_CHANGED, job_id, job, details)

                if new_status == JobStatus.FAILED:
                    self._emit_event(JobEventType.FAILED, job_id, job, details)
                elif new_status == JobStatus.DELIVERED:
                    self._emit_event(JobEventType.DELIVERED, job_id, job, details)

            return job

    def update_progress(self, job_id: str, progress_percent: float) -> VideoJob:
        """Update job progress percentage clamped between 0.0 and 100.0."""
        with self._lock:
            job = self.get_job_or_raise(job_id)
            clamped = max(0.0, min(100.0, float(progress_percent)))
            job.progress_percent = clamped
            job.updated_at = datetime.now(timezone.utc)
            self._emit_event(JobEventType.PROGRESS_UPDATED, job_id, job, {"progress_percent": clamped})
            return job

    def update_edl(self, job_id: str, edl: EditDecisionList, is_override: bool = False) -> VideoJob:
        """Attach or update active EDL for a job."""
        with self._lock:
            job = self.get_job_or_raise(job_id)
            job.active_edl = edl
            if is_override:
                edl.manual_override_applied = True
            job.updated_at = datetime.now(timezone.utc)
            self._emit_event(JobEventType.EDL_UPDATED, job_id, job, {"is_override": is_override})
            return job

    def update_probe_metadata(self, job_id: str, probe_metadata: Dict[str, Any]) -> VideoJob:
        """Attach media probe metadata dictionary to job."""
        with self._lock:
            job = self.get_job_or_raise(job_id)
            job.probe_metadata = probe_metadata
            job.updated_at = datetime.now(timezone.utc)
            self._emit_event(JobEventType.PROBE_COMPLETED, job_id, job, {})
            return job

    def set_delivery_path(self, job_id: str, delivery_filepath: Union[str, Path]) -> VideoJob:
        """Record the finalized delivery file path."""
        with self._lock:
            job = self.get_job_or_raise(job_id)
            job.delivery_filepath = str(Path(delivery_filepath).resolve())
            job.updated_at = datetime.now(timezone.utc)
            return job

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        active_only: bool = False,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> List[VideoJob]:
        """Query jobs with optional status filter, active filter, pagination, and sorting."""
        with self._lock:
            filtered = list(self._jobs.values())

            if status is not None:
                filtered = [j for j in filtered if j.status == status]
            elif active_only:
                terminal_states = {JobStatus.DELIVERED, JobStatus.FAILED, JobStatus.CANCELLED}
                filtered = [j for j in filtered if j.status not in terminal_states]

            def get_sort_key(j: VideoJob) -> Any:
                val = getattr(j, sort_by, None)
                if val is None:
                    return datetime.min.replace(tzinfo=timezone.utc)
                return val

            filtered.sort(key=get_sort_key, reverse=sort_desc)
            return filtered[offset : offset + limit]

    def count_jobs(self, status: Optional[JobStatus] = None) -> int:
        """Count total jobs or jobs matching a specific status."""
        with self._lock:
            if status is None:
                return len(self._jobs)
            return sum(1 for j in self._jobs.values() if j.status == status)

    def delete_job(self, job_id: str) -> bool:
        """Remove a job from the repository."""
        with self._lock:
            job = self._jobs.pop(job_id, None)
            if job is not None:
                self._emit_event(JobEventType.DELETED, job_id, job, {})
                return True
            return False

    def clear(self) -> None:
        """Reset repository state (for testing)."""
        with self._lock:
            self._jobs.clear()
            for subs in self._subscribers.values():
                subs.clear()

    def subscribe(
        self,
        event_type: JobEventType,
        callback: Callable[[JobEvent], Any],
    ) -> str:
        """Register a subscriber callback. Returns subscription ID."""
        with self._lock:
            sub_id = str(uuid.uuid4())
            self._subscribers[event_type][sub_id] = callback
            return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscriber by ID."""
        with self._lock:
            for subs in self._subscribers.values():
                if subscription_id in subs:
                    del subs[subscription_id]
                    return True
            return False

    def _emit_event(
        self,
        event_type: JobEventType,
        job_id: str,
        job: VideoJob,
        details: Dict[str, Any],
    ) -> None:
        """Dispatch event to registered synchronous and asynchronous subscribers."""
        event = JobEvent(event_type=event_type, job_id=job_id, job=job, details=details)

        # Collect callbacks for this specific event type and the ALL wildcard
        callbacks = list(self._subscribers[event_type].values())
        if event_type != JobEventType.ALL:
            callbacks.extend(self._subscribers[JobEventType.ALL].values())

        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(cb(event))
                    except RuntimeError:
                        asyncio.run(cb(event))
                else:
                    cb(event)
            except Exception as exc:
                self._logger.exception(f"Error in job event subscriber for {event_type}: {exc}")
