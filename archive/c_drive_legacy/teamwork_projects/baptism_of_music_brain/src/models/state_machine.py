"""Deterministic Finite State Machine (FSM) validator for VideoJob lifecycle transitions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional, Set

from src.models.schemas import JobStatus, VideoJob


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal status transition is requested."""

    def __init__(self, current_status: JobStatus, target_status: JobStatus, job_id: Optional[str] = None):
        self.current_status = current_status
        self.target_status = target_status
        self.job_id = job_id
        msg = f"Invalid state transition: cannot transition from {current_status.value} to {target_status.value}"
        if job_id:
            msg += f" (job_id: {job_id})"
        super().__init__(msg)


# State transition mapping table
ALLOWED_TRANSITIONS: Dict[JobStatus, Set[JobStatus]] = {
    JobStatus.PENDING: {
        JobStatus.DETECTED,
        JobStatus.INGESTING,
        JobStatus.INGESTED,
        JobStatus.PROBING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.DETECTED: {
        JobStatus.INGESTING,
        JobStatus.INGESTED,
        JobStatus.PROBING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.INGESTING: {
        JobStatus.INGESTED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.INGESTED: {
        JobStatus.PROBING,
        JobStatus.PROBED,
        JobStatus.ANALYZING,
        JobStatus.GRADING,
        JobStatus.ML_GRADING,
        JobStatus.AWAITING_OVERRIDE,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.PROBING: {
        JobStatus.PROBED,
        JobStatus.ANALYZING,
        JobStatus.GRADING,
        JobStatus.ML_GRADING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.PROBED: {
        JobStatus.ANALYZING,
        JobStatus.GRADING,
        JobStatus.ML_GRADING,
        JobStatus.AWAITING_OVERRIDE,
        JobStatus.APPROVED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.ANALYZING: {
        JobStatus.AWAITING_OVERRIDE,
        JobStatus.OVERRIDDEN,
        JobStatus.OVERRIDE_APPLIED,
        JobStatus.APPROVED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.GRADING: {
        JobStatus.AWAITING_OVERRIDE,
        JobStatus.OVERRIDDEN,
        JobStatus.OVERRIDE_APPLIED,
        JobStatus.APPROVED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.ML_GRADING: {
        JobStatus.AWAITING_OVERRIDE,
        JobStatus.OVERRIDDEN,
        JobStatus.OVERRIDE_APPLIED,
        JobStatus.APPROVED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.AWAITING_OVERRIDE: {
        JobStatus.OVERRIDDEN,
        JobStatus.OVERRIDE_APPLIED,
        JobStatus.APPROVED,
        JobStatus.ANALYZING,
        JobStatus.GRADING,
        JobStatus.ML_GRADING,
        JobStatus.CANCELLED,
        JobStatus.FAILED,
    },
    JobStatus.OVERRIDDEN: {
        JobStatus.APPROVED,
        JobStatus.AWAITING_OVERRIDE,
        JobStatus.OVERRIDDEN,
        JobStatus.OVERRIDE_APPLIED,
        JobStatus.ANALYZING,
        JobStatus.GRADING,
        JobStatus.ML_GRADING,
        JobStatus.CANCELLED,
        JobStatus.FAILED,
    },
    JobStatus.OVERRIDE_APPLIED: {
        JobStatus.APPROVED,
        JobStatus.AWAITING_OVERRIDE,
        JobStatus.OVERRIDDEN,
        JobStatus.OVERRIDE_APPLIED,
        JobStatus.ANALYZING,
        JobStatus.GRADING,
        JobStatus.ML_GRADING,
        JobStatus.CANCELLED,
        JobStatus.FAILED,
    },
    JobStatus.APPROVED: {
        JobStatus.RENDERING,
        JobStatus.CANCELLED,
        JobStatus.FAILED,
    },
    JobStatus.RENDERING: {
        JobStatus.DELIVERING,
        JobStatus.DELIVERED,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.DELIVERING: {
        JobStatus.DELIVERED,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.DELIVERED: set(),  # Terminal state
    JobStatus.COMPLETED: set(),  # Terminal state
    JobStatus.FAILED: {
        JobStatus.PENDING,
        JobStatus.DETECTED,
        JobStatus.INGESTED,
        JobStatus.PROBING,
    },  # Allows retry
    JobStatus.CANCELLED: {
        JobStatus.PENDING,
        JobStatus.DETECTED,
    },
}


def can_transition(current: JobStatus, target: JobStatus) -> bool:
    """Return True if transitioning from current to target is allowed by the FSM."""
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, set())


def validate_transition(current: JobStatus, target: JobStatus, job_id: Optional[str] = None) -> bool:
    """
    Validate status transition.
    Returns True if valid, raises InvalidStateTransitionError if invalid.
    """
    if not can_transition(current, target):
        raise InvalidStateTransitionError(current_status=current, target_status=target, job_id=job_id)
    return True


def transition_job(job: VideoJob, target: JobStatus, error_message: Optional[str] = None) -> VideoJob:
    """
    Transition a VideoJob to a new status with validation.
    Mutates job status, updated_at timestamp, and optionally error_message.
    """
    validate_transition(job.status, target, job_id=job.job_id)
    job.status = target
    job.updated_at = datetime.now(timezone.utc)
    if error_message is not None:
        job.error_message = error_message
    return job
