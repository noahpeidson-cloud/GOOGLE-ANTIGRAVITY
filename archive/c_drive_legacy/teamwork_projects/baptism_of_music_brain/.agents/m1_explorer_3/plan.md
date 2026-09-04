# Milestone 1 Technical Implementation Plan: Job Manager, Orchestrator & Unit Test Plan
**Project:** `baptism_of_music_brain`  
**Explorer:** `m1_explorer_3`  
**Working Directory:** `C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_explorer_3`  
**Date:** 2026-08-27  

---

## 1. Executive Summary

Milestone 1 establishes the foundational infrastructure of the `baptism_of_music_brain` video editing platform. This plan details the architectural design, API specifications, concurrency controls, and implementation blueprints for:
1. **`src/pipeline/job_manager.py`**: Thread-safe in-memory job repository, querying engine, state machine transition validator, and asynchronous pub/sub event bus.
2. **`src/pipeline/orchestrator.py`**: End-to-end pipeline coordinator bridging the Windows file watcher (`ingest_watcher.py` & `file_locker.py`), media prober (`probe.py`), job repository (`job_manager.py`), and ML brain grading loop (`ml_brain/`).
3. **Milestone 1 Unit Test Plan**: Comprehensive test specifications spanning configuration, schemas, state machine, Win32 file locking, ingestion watching, media probing, job management, and pipeline orchestration.

---

## 2. Component Design: `src/pipeline/job_manager.py`

### 2.1 Core Architectural Principles
- **Thread Safety**: File watcher events originate in OS background threads (`watchdog`), whereas FastAPI route handlers and ML tasks execute on asynchronous event loops (`asyncio`) or thread pools. The job repository uses an internal `threading.RLock()` to guarantee atomic state mutations and query consistency without blocking event loops.
- **Strict State Machine Enforcement**: Status updates are checked against `src.models.state_machine.validate_transition`. Illegal transitions raise `InvalidStateTransitionError`.
- **Pub/Sub Event Bus**: Decouples job lifecycle mutations from external observers (e.g., WebSocket event broadcasters, logging systems, orchestrator worker queues). Supports both synchronous callbacks and asynchronous coroutine subscribers.

### 2.2 Data Structures & Exception Hierarchy

```python
from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Awaitable, Union, Set
from datetime import datetime, timezone
import uuid
import threading
import asyncio
import logging

class JobEventType(str, Enum):
    CREATED = "job_created"
    STATUS_CHANGED = "status_changed"
    PROGRESS_UPDATED = "progress_updated"
    EDL_UPDATED = "edl_updated"
    PROBE_COMPLETED = "probe_completed"
    FAILED = "job_failed"
    DELIVERED = "job_delivered"
    DELETED = "job_deleted"
    ALL = "*"

class JobManagerError(Exception):
    """Base exception for all job manager errors."""
    pass

class JobNotFoundError(JobManagerError):
    """Raised when a queried job_id does not exist."""
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
    """Event payload emitted on job lifecycle mutations."""
    def __init__(
        self,
        event_type: JobEventType,
        job_id: str,
        job: Any,  # VideoJob
        timestamp: Optional[datetime] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.event_type = event_type
        self.job_id = job_id
        self.job = job
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.details = details or {}
```

### 2.3 `JobManager` Class Specification

```python
class JobManager:
    """
    Thread-safe, in-memory repository for VideoJob instances with status FSM validation,
    rich querying/sorting capabilities, and an asynchronous event subscription bus.
    """

    def __init__(self):
        self._jobs: Dict[str, VideoJob] = {}
        self._lock = threading.RLock()
        self._subscribers: Dict[JobEventType, Dict[str, Callable[[JobEvent], Any]]] = {
            event_type: {} for event_type in JobEventType
        }
        self._logger = logging.getLogger("baptism_of_music_brain.job_manager")

    # --- Creation & Retrieval ---
    def create_job(
        self,
        source_filepath: str,
        job_id: Optional[str] = None,
        initial_status: JobStatus = JobStatus.DETECTED,
        file_size_bytes: int = 0
    ) -> VideoJob:
        """Create and store a new VideoJob."""
        with self._lock:
            jid = job_id or str(uuid.uuid4())
            filename = Path(source_filepath).name
            
            job = VideoJob(
                job_id=jid,
                source_filepath=str(source_filepath),
                filename=filename,
                file_size_bytes=file_size_bytes,
                status=initial_status,
                progress_percent=0.0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            self._jobs[jid] = job
            self._emit_event(JobEventType.CREATED, jid, job, {"initial_status": initial_status})
            return job

    def get_job(self, job_id: str) -> Optional[VideoJob]:
        """Retrieve a job by ID, returning None if not found."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_job_or_raise(self, job_id: str) -> VideoJob:
        """Retrieve a job by ID or raise JobNotFoundError."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)
            return job

    # --- Lifecycle & State Mutations ---
    def update_status(
        self,
        job_id: str,
        new_status: JobStatus,
        error_message: Optional[str] = None
    ) -> VideoJob:
        """
        Transition job to new_status with FSM validation.
        Emits STATUS_CHANGED and conditionally FAILED or DELIVERED events.
        """
        with self._lock:
            job = self.get_job_or_raise(job_id)
            old_status = job.status
            
            if old_status != new_status:
                if not validate_transition(old_status, new_status):
                    raise InvalidStateTransitionError(job_id, old_status, new_status)
                
                job.status = new_status
                job.updated_at = datetime.now(timezone.utc)
                if error_message is not None:
                    job.error_message = error_message
                
                details = {"previous_status": old_status, "new_status": new_status, "error_message": error_message}
                self._emit_event(JobEventType.STATUS_CHANGED, job_id, job, details)
                
                if new_status == JobStatus.FAILED:
                    self._emit_event(JobEventType.FAILED, job_id, job, details)
                elif new_status == JobStatus.DELIVERED:
                    self._emit_event(JobEventType.DELIVERED, job_id, job, details)

            return job

    def update_progress(self, job_id: str, progress_percent: float) -> VideoJob:
        """Update job progress percentage (0.0 - 100.0)."""
        with self._lock:
            job = self.get_job_or_raise(job_id)
            clamped_progress = max(0.0, min(100.0, float(progress_percent)))
            job.progress_percent = clamped_progress
            job.updated_at = datetime.now(timezone.utc)
            self._emit_event(JobEventType.PROGRESS_UPDATED, job_id, job, {"progress_percent": clamped_progress})
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
        """Attach media probe metadata to job."""
        with self._lock:
            job = self.get_job_or_raise(job_id)
            job.probe_metadata = probe_metadata
            job.updated_at = datetime.now(timezone.utc)
            self._emit_event(JobEventType.PROBE_COMPLETED, job_id, job, {})
            return job

    def set_delivery_path(self, job_id: str, delivery_filepath: str) -> VideoJob:
        """Record the finalized master delivery file path."""
        with self._lock:
            job = self.get_job_or_raise(job_id)
            job.delivery_filepath = str(delivery_filepath)
            job.updated_at = datetime.now(timezone.utc)
            return job

    # --- Querying & Pagination ---
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        active_only: bool = False,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_desc: bool = True
    ) -> List[VideoJob]:
        """Query jobs with filtering, pagination, and sorting."""
        with self._lock:
            filtered = list(self._jobs.values())
            
            if status is not None:
                filtered = [j for j in filtered if j.status == status]
            elif active_only:
                terminal_states = {JobStatus.DELIVERED, JobStatus.FAILED, JobStatus.CANCELLED}
                filtered = [j for j in filtered if j.status not in terminal_states]

            # Sorting
            def get_sort_key(j: VideoJob):
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
        """Reset repository state (primarily used in testing)."""
        with self._lock:
            self._jobs.clear()
            for subscribers in self._subscribers.values():
                subscribers.clear()

    # --- Pub/Sub Event Subscription ---
    def subscribe(
        self,
        event_type: JobEventType,
        callback: Callable[[JobEvent], Any]
    ) -> str:
        """Register a subscriber callback. Returns a subscription handle ID."""
        with self._lock:
            sub_id = str(uuid.uuid4())
            self._subscribers[event_type][sub_id] = callback
            return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscriber by handle ID."""
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
        details: Dict[str, Any]
    ) -> None:
        """Dispatch event to registered synchronous and asynchronous subscribers."""
        event = JobEvent(event_type=event_type, job_id=job_id, job=job, details=details)
        
        # Gather target callbacks (specific event + wildcard ALL)
        callbacks = list(self._subscribers[event_type].values())
        if event_type != JobEventType.ALL:
            callbacks.extend(self._subscribers[JobEventType.ALL].values())

        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    # If running inside an event loop, schedule coroutine task
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(cb(event))
                    except RuntimeError:
                        # Fallback if called outside event loop
                        asyncio.run(cb(event))
                else:
                    cb(event)
            except Exception as e:
                self._logger.exception(f"Error in job event subscriber for {event_type}: {e}")
```

---

## 3. Component Design: `src/pipeline/orchestrator.py`

### 3.1 Orchestration Workflow & Architecture
The `PipelineOrchestrator` is the central coordinator of the system. It connects:
1. **`IngestWatcher`**: Listens for file drops in `ingest_dir`, manages 3-tier Win32 lock detection, and emits `on_file_ready`.
2. **`probe_media`**: Asynchronously extracts stream formats, duration, video dimensions, frame rate, and audio parameters.
3. **`JobManager`**: Registers jobs, transitions FSM states, updates metadata, and attaches synthesized EDLs.
4. **`MLBrain` Provider**: Dispatches media analysis to Gemini Omni (or Mock provider) to produce an `EditDecisionList`.
5. **FastAPI & Render Control Plane**: Transitions to `AWAITING_OVERRIDE` (for editor inspection) or `RENDERING` (if `auto_approve=True`).

```
┌─────────────────┐       ┌─────────────────┐       ┌────────────────────────────┐
│   Watchdog /    │       │   Win32 Lock    │       │       Video Metadata       │
│   Watchfiles    │ ────► │    Detector     │ ────► │       Probe Engine         │
│ (ingest/ watch) │       │ (Non-blocking)  │       │     (FFprobe / FFmpeg)     │
└─────────────────┘       └─────────────────┘       └─────────────┬──────────────┘
                                                                  │
                                                                  ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                          Gemini Omni ML Brain Loop                             │
│   - Video Rhythm & Beat Alignment      - Dynamic Viral Cut Decision Generator  │
│   - Color Balance & Aesthetic Grading  - Dual-Mode: Live GenAI + Offline Mock │
└────────────────────────────────────────┬───────────────────────────────────────┘
                                         │
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                     FastAPI REST & WebSocket Control Plane                     │
│   GET  /jobs,  GET /jobs/{id},  PUT /jobs/{id}/edl,  POST /jobs/{id}/approve   │
└────────────────────────────────────────┬───────────────────────────────────────┘
                                         │ Approved EDL
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                 Desktop-Class Lossless FFmpeg Rendering Engine                 │
│   - Complex Filtergraph Assembler (Trims, Audio Fade, EQ/LUT Color Grade)      │
│   - Visually Lossless Encoding (libx264 -crf 17 / hevc_nvenc -qp 18)           │
└────────────────────────────────────────┬───────────────────────────────────────┘
```

### 3.2 `PipelineOrchestrator` Class Specification

```python
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Set
import asyncio
import logging

from config.settings import AppSettings
from src.models.schemas import VideoJob, EditDecisionList, JobStatus
from src.pipeline.job_manager import JobManager, JobEventType, JobEvent

class PipelineOrchestrator:
    """
    End-to-end coordinator managing ingestion events, media probing,
    job lifecycle tracking, ML grading triggers, and render execution.
    """

    def __init__(
        self,
        settings: AppSettings,
        job_manager: Optional[JobManager] = None,
        ml_provider: Optional[Any] = None,
        prober: Optional[Callable[[Path], Any]] = None,
        watcher: Optional[Any] = None,
        auto_approve: bool = False,
        max_concurrent_jobs: int = 4
    ):
        self.settings = settings
        self.job_manager = job_manager or JobManager()
        self.ml_provider = ml_provider
        self.prober = prober
        self.watcher = watcher
        self.auto_approve = auto_approve
        self.semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self.active_tasks: Set[asyncio.Task] = set()
        self.is_running = False
        self._logger = logging.getLogger("baptism_of_music_brain.orchestrator")

    async def start(self) -> None:
        """Start directory watcher and background pipeline workers."""
        if self.is_running:
            return

        self._logger.info("Starting Pipeline Orchestrator...")
        self.settings.ensure_directories()
        
        # Wire IngestWatcher callback if watcher is provided
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

        # Cancel and drain active tasks with timeout
        if self.active_tasks:
            self._logger.info(f"Draining {len(self.active_tasks)} active tasks...")
            for task in list(self.active_tasks):
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

    async def handle_file_ingested(self, file_path: Path | str) -> VideoJob:
        """
        Execute full M1 ingestion pipeline for a video file:
        1. Register job in JobManager (DETECTED -> INGESTED)
        2. Probe media metadata via FFprobe
        3. Trigger ML grading loop (Gemini Omni / Mock)
        4. Transition to AWAITING_OVERRIDE (or RENDERING if auto_approve=True)
        """
        path = Path(file_path).resolve()
        file_size = path.stat().st_size if path.exists() else 0
        
        # Step 1: Create Job Record
        job = self.job_manager.create_job(
            source_filepath=str(path),
            initial_status=JobStatus.DETECTED,
            file_size_bytes=file_size
        )
        job_id = job.job_id

        async with self.semaphore:
            try:
                # Transition DETECTED -> INGESTING -> INGESTED
                self.job_manager.update_status(job_id, JobStatus.INGESTING)
                self.job_manager.update_status(job_id, JobStatus.INGESTED)

                # Step 2: Probe Media Metadata
                self._logger.info(f"Probing media metadata for job {job_id} ({path.name})...")
                probe_data = None
                if self.prober:
                    if asyncio.iscoroutinefunction(self.prober):
                        probe_data = await self.prober(path)
                    else:
                        probe_data = await asyncio.to_thread(self.prober, path)
                    
                    self.job_manager.update_probe_metadata(job_id, probe_data.model_dump() if hasattr(probe_data, "model_dump") else probe_data)
                
                # Step 3: Trigger ML Grading Loop
                self.job_manager.update_status(job_id, JobStatus.ML_GRADING)
                self._logger.info(f"Triggering ML grading for job {job_id}...")
                
                edl = None
                if self.ml_provider:
                    if hasattr(self.ml_provider, "grade_video_async"):
                        edl = await self.ml_provider.grade_video_async(path, probe_data)
                    elif hasattr(self.ml_provider, "grade_video"):
                        edl = await asyncio.to_thread(self.ml_provider.grade_video, path, probe_data)
                
                if edl is not None:
                    self.job_manager.update_edl(job_id, edl, is_override=False)

                # Step 4: Approval / Override Handoff
                if self.auto_approve:
                    self._logger.info(f"Auto-approve enabled. Enqueuing render for job {job_id}...")
                    self.job_manager.update_status(job_id, JobStatus.RENDERING)
                    # Trigger render handler in M3
                else:
                    self._logger.info(f"Job {job_id} is now AWAITING_OVERRIDE.")
                    self.job_manager.update_status(job_id, JobStatus.AWAITING_OVERRIDE)

                return self.job_manager.get_job_or_raise(job_id)

            except Exception as exc:
                self._logger.exception(f"Pipeline error processing job {job_id}: {exc}")
                self.job_manager.update_status(job_id, JobStatus.FAILED, error_message=str(exc))
                return self.job_manager.get_job_or_raise(job_id)

    async def approve_job(self, job_id: str) -> VideoJob:
        """Approve EDL and transition job from AWAITING_OVERRIDE / OVERRIDE_APPLIED to RENDERING."""
        job = self.job_manager.get_job_or_raise(job_id)
        if job.status not in (JobStatus.AWAITING_OVERRIDE, JobStatus.OVERRIDE_APPLIED):
            raise ValueError(f"Job {job_id} cannot be approved in state {job.status}.")

        self.job_manager.update_status(job_id, JobStatus.RENDERING)
        # Handoff to FFmpeg rendering engine
        return self.job_manager.get_job_or_raise(job_id)

    async def override_edl(self, job_id: str, new_edl: EditDecisionList) -> VideoJob:
        """Apply user modifications to EDL and transition to OVERRIDE_APPLIED."""
        job = self.job_manager.get_job_or_raise(job_id)
        if job.status not in (JobStatus.AWAITING_OVERRIDE, JobStatus.OVERRIDE_APPLIED):
            raise ValueError(f"EDL overrides cannot be applied to job {job_id} in state {job.status}.")

        self.job_manager.update_edl(job_id, new_edl, is_override=True)
        self.job_manager.update_status(job_id, JobStatus.OVERRIDE_APPLIED)
        return self.job_manager.get_job_or_raise(job_id)
```

---

## 4. Comprehensive Milestone 1 Unit Test Plan

The Milestone 1 test plan guarantees strict zero-discretion verification across all 7 core subsystem areas:

### 4.1 Test Module Matrix

| Test Module | Target Components | Key Assertions & Scenarios |
|---|---|---|
| `tests/unit/test_settings.py` | `config/settings.py` | 1. Default directory paths, port (8000), host (127.0.0.1)<br>2. Environment variable overrides via prefix (`BAPTISM_`)<br>3. `ensure_directories()` creates `ingest`, `delivery`, `temp` paths. |
| `tests/unit/test_models.py` | `src/models/schemas.py`, `src/models/state_machine.py` | 1. `ClipSegment` boundary constraints (`start < end`, volume in [0, 5])<br>2. `ColorGradeSettings` clamping bounds (brightness, contrast, saturation, gamma)<br>3. `AudioMasteringSettings` default LUFS (-14.0) and true peak (-1.5 dBFS)<br>4. `EditDecisionList` validation and JSON serialization round-trip<br>5. `validate_transition()` accepts legal FSM paths and rejects illegal jumps (e.g. `DELIVERED -> ML_GRADING`). |
| `tests/unit/test_probe.py` | `src/renderer/probe.py` | 1. Probing synthetic video returns duration, dimensions, fps, codec, pix_fmt, audio channels/rate.<br>2. Graceful error handling and descriptive exceptions for non-existent or corrupt files.<br>3. Fallback binary discovery via `imageio-ffmpeg` when `ffprobe` is not on PATH. |
| `tests/unit/test_file_locker.py` | `src/watcher/file_locker.py` | 1. Tier 1: Temporary extension filter rejects `.tmp`, `.part`, `.crdownload`.<br>2. Tier 2: Win32 exclusive handle test returns `is_locked=True` when file is opened for writing.<br>3. Tier 3: Size debounce verifies file size stability over 1.0s interval.<br>4. Non-Windows / fallback mode operates cleanly using standard library `open()`. |
| `tests/unit/test_ingest_watcher.py` | `src/watcher/ingest_watcher.py` | 1. Watchdog observer detects newly created `.mp4` file in `ingest_dir`.<br>2. Non-video and temporary files are filtered out without invoking callback.<br>3. Debounced trigger fires only once per unique video file.<br>4. Clean startup and shutdown without orphaned background threads. |
| `tests/unit/test_job_manager.py` | `src/pipeline/job_manager.py` | 1. Job creation, retrieval by ID, and `JobNotFoundError` raising.<br>2. FSM status transitions and rejection of invalid transitions.<br>3. Progress percentage updates clamped between 0.0 and 100.0.<br>4. EDL updates and override flag tracking.<br>5. Synchronous and asynchronous pub/sub event subscriptions.<br>6. Thread-safety: 50 concurrent worker threads creating and updating jobs simultaneously without race conditions or state corruption.<br>7. Query filtering by status, active-only, pagination (`limit`/`offset`), and sorting. |
| `tests/unit/test_orchestrator.py` | `src/pipeline/orchestrator.py` | 1. End-to-end M1 workflow: file ready -> probe media -> register job -> trigger ML grading -> attach EDL -> transition to `AWAITING_OVERRIDE`.<br>2. Auto-approve configuration transitions directly to `RENDERING`.<br>3. Probe failure transitions job to `FAILED` with error message.<br>4. ML grading failure triggers fallback or transitions to `FAILED`.<br>5. Manual EDL override transitions to `OVERRIDE_APPLIED`.<br>6. Concurrency semaphore limits simultaneous job processing.<br>7. Graceful start and stop drains pending background tasks. |

---

## 5. Step-by-Step Implementation Sequence for Worker

1. **Step 1: Implement `src/pipeline/job_manager.py`**:
   - Define custom exceptions (`JobManagerError`, `JobNotFoundError`, `InvalidStateTransitionError`).
   - Implement `JobEventType` and `JobEvent` data structures.
   - Implement `JobManager` with `threading.RLock`, CRUD operations, FSM transition checking, querying/pagination, and sync/async event dispatch.
2. **Step 2: Implement `src/pipeline/orchestrator.py`**:
   - Implement `PipelineOrchestrator` coordinating `AppSettings`, `JobManager`, `IngestWatcher`, prober, and ML grading engine.
   - Implement `handle_file_ingested` with bounded concurrency (`asyncio.Semaphore`) and comprehensive error isolation.
   - Implement `approve_job`, `override_edl`, and `regrade_job` workflow methods.
   - Implement async `start()` and `stop()` lifecycle handlers.
3. **Step 3: Implement Milestone 1 Unit Tests in `tests/`**:
   - `tests/tier1_feature/test_job_manager.py`
   - `tests/tier1_feature/test_orchestrator.py`
   - Unit tests for settings, schemas, state machine, prober, file locker, and ingest watcher.
4. **Step 4: Execute & Verify**:
   - Run `pytest -v tests/` and assert 100% test pass.
