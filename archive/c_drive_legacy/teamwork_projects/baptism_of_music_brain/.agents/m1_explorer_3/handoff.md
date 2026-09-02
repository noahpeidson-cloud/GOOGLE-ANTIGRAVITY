# Milestone 1 Handoff Report: Job Manager, Orchestrator & Unit Test Plan
**Project:** `baptism_of_music_brain`  
**Agent:** `m1_explorer_3`  
**Working Directory:** `C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_explorer_3`  
**Date:** 2026-08-27  

---

## 1. Observation

1. **Environment Verification**:
   - Tool command `python -c "import pydantic, watchdog, win32file, imageio_ffmpeg; print('Python imports OK')"` exited with code 0. Output: `Python imports OK`.
   - Python runtime: `3.13.14` (64-bit Windows).
   - Core libraries installed and verified: `fastapi 0.141.1`, `pydantic 2.13.4`, `watchdog 6.0.0`, `pywin32 312`, `imageio-ffmpeg 0.6.0`, `pytest 9.1.1`, `pytest-asyncio 1.4.0`.

2. **Project Specification Contracts**:
   - `ORIGINAL_REQUEST.md` (Lines 16-24): Defines R1 (FastAPI + Gemini Omni monitoring ingest, generating EDL, exposing override interface), R2 (Desktop FFmpeg lossless rendering), R3 (Delivery pipeline).
   - `PROJECT.md` (Lines 48-53): Maps Milestone 1 components: Settings, Pydantic schemas, Prober, Win32 File Locking, Ingest Watchdog, Job State Store (`src/pipeline/job_manager.py`, `src/pipeline/orchestrator.py`).
   - `PROJECT.md` (Lines 94-98): Defines interface contract `watcher ↔ pipeline` (`on_file_ingested`) and `ml_brain ↔ pipeline` (`grade_video(job, probe_data)`).

3. **Multi-Agent Milestone Decomposition**:
   - `m1_explorer_1`: Settings (`config/settings.py`), Data models (`src/models/schemas.py`, `src/models/state_machine.py`), Media prober (`src/renderer/probe.py`).
   - `m1_explorer_2`: Win32 file locking (`src/watcher/file_locker.py`), Ingest watcher (`src/watcher/ingest_watcher.py`).
   - `m1_explorer_3` (This agent): In-memory job repository (`src/pipeline/job_manager.py`), Pipeline orchestrator (`src/pipeline/orchestrator.py`), and comprehensive Milestone 1 unit test plan.

---

## 2. Logic Chain

1. **Concurrency & Thread Safety**:
   - *Premise (Observation 1 & 2)*: Ingestion events are emitted by `watchdog` from native OS threads, while the FastAPI server and ML triggers run on an `asyncio` event loop.
   - *Deduction*: An un-synchronized repository would suffer from race conditions, dictionary corruption, or stale reads.
   - *Design Choice*: `JobManager` wraps internal state in `threading.RLock()` for atomic CRUD operations and provides an event bus capable of dispatching to both sync callables and async coroutines safely via `asyncio.get_running_loop().create_task()`.

2. **State Machine Integrity**:
   - *Premise (Observation 2)*: `PROJECT.md` dictates strict job lifecycles (`DETECTED -> INGESTING -> INGESTED -> ML_GRADING -> AWAITING_OVERRIDE / OVERRIDE_APPLIED -> RENDERING -> DELIVERED / FAILED`).
   - *Deduction*: Arbitrary state jumps (such as bypassing lock validation or jumping from `DELIVERED` back to `ML_GRADING`) would violate pipeline invariant guarantees.
   - *Design Choice*: `JobManager.update_status()` checks every transition against `src.models.state_machine.validate_transition()` and raises `InvalidStateTransitionError` on illegal mutations.

3. **Orchestrator Resilience & Bounded Concurrency**:
   - *Premise (Observation 2)*: High-bitrate 4K media analysis and FFmpeg rendering can consume significant system resources (CPU/GPU/RAM).
   - *Deduction*: Dropping 10+ raw video files simultaneously without concurrency control would exhaust memory and trigger out-of-memory or timeout errors.
   - *Design Choice*: `PipelineOrchestrator` implements an `asyncio.Semaphore(max_concurrent_jobs=4)` and isolates per-job exceptions so a corrupted video file transitions only that specific job to `JobStatus.FAILED` without interrupting the watcher or stalling other in-flight jobs.

4. **Zero-Discretion Verification**:
   - *Premise (Observation 1 & 2)*: Rule R2 strictly forbids self-certification without automated test suites.
   - *Deduction*: Every component in Milestone 1 must be covered by deterministic unit and functional tests in `tests/tier1_feature/` and `tests/unit/`.
   - *Design Choice*: Formulated a complete 7-module test matrix with exact assertions for settings, models, probe engine, file locker, directory watcher, job repository, and orchestrator.

---

## 3. Caveats

1. **FFmpeg Binary Path Resolution**:
   - If standalone `ffmpeg`/`ffprobe` binaries are not in system PATH on some environments, the system depends on `imageio-ffmpeg`'s bundled executable or explicit path configuration in `config/settings.py`.
2. **Gemini Omni Live vs Mock Provider**:
   - Live Gemini Omni grading requires a valid `GEMINI_API_KEY`. For Milestone 1 testing and offline execution, the orchestrator defaults to or seamlessly accepts the deterministic `MockMLGradingProvider`.
3. **Storage of In-Memory Jobs**:
   - Jobs are stored in memory (`JobManager._jobs`). For multi-worker production deployments in future milestones, a lightweight persistence layer (e.g. SQLite) can wrap the same interface if crash-recovery across restarts is needed.

---

## 4. Conclusion

1. The architectural design and complete implementation blueprints for `src/pipeline/job_manager.py` and `src/pipeline/orchestrator.py` are fully defined in `plan.md`.
2. All interface contracts with settings, schemas, state machine, file locker, ingest watcher, and ML brain are aligned with `PROJECT.md`.
3. A comprehensive, deterministic Milestone 1 Unit Test Plan is prepared to drive Test-Driven Agentic Development (TDAD) during worker implementation.

---

## 5. Verification Method

To independently verify the implementation once executed by the Worker:

1. **Unit & Feature Test Execution**:
   ```powershell
   pytest -v tests/tier1_feature/test_job_manager.py
   pytest -v tests/tier1_feature/test_orchestrator.py
   pytest -v tests/unit/
   ```
2. **Thread Safety Verification**:
   - Assert `test_job_manager_concurrent_threads` spawns 50 threads performing 1000 concurrent creates/updates with 0 lost updates or race conditions.
3. **FSM Enforcement Verification**:
   - Assert `test_job_manager_invalid_transition_raises` verifies that attempting invalid transitions (e.g. `DELIVERED -> ML_GRADING`) raises `InvalidStateTransitionError`.
4. **Orchestrator Pipeline Verification**:
   - Assert `test_orchestrator_end_to_end_flow` runs a synthetic video through ingest detection, probing, ML grading, and EDL attachment to `AWAITING_OVERRIDE`.

**Invalidation Conditions**:
- Any uncaught `PermissionError` or deadlocks during multi-threaded repository updates.
- Ingestion pipeline crashing upon corrupted media instead of cleanly marking the job as `FAILED`.
- Any non-zero exit code during `pytest` test runs.
