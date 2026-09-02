## 2026-08-27T10:08:19Z
You are the Implementation Worker for Milestone 1 of the baptism_of_music_brain project.
Your working directory is C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_worker_1

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY FIRST STEPS:
1. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\ORIGINAL_REQUEST.md
2. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\PROJECT.md
3. Read the Explorer blueprints:
   - C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_explorer_1\plan.md
   - C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_explorer_2\plan.md
   - C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_explorer_3\plan.md

Your Exclusive Write Ownership:
- `requirements.txt` and `pytest.ini`
- `config/__init__.py` and `config/settings.py`
- `src/__init__.py`
- `src/models/__init__.py`, `src/models/schemas.py`, and `src/models/state_machine.py`
- `src/renderer/__init__.py` and `src/renderer/probe.py`
- `src/watcher/__init__.py`, `src/watcher/file_locker.py`, and `src/watcher/ingest_watcher.py`
- `src/pipeline/__init__.py`, `src/pipeline/job_manager.py`, and `src/pipeline/orchestrator.py`
- `tests/tier1_feature/test_models.py`, `tests/tier1_feature/test_file_locker.py`, `tests/tier1_feature/test_probe.py`, `tests/tier1_feature/test_job_manager.py`, and `tests/tier1_feature/test_orchestrator.py`

Tasks:
1. Create `requirements.txt` and `pytest.ini`.
2. Implement `config/settings.py` (AppSettings with directory helpers and FFmpeg path resolution).
3. Implement `src/models/schemas.py` and `src/models/state_machine.py` (Pydantic v2 models for EDL, ClipSegment, ColorGradeSettings, AudioMasteringSettings, VideoJob, JobMetadata, JobStatus enum & validation transitions).
4. Implement `src/renderer/probe.py` (FFprobe wrapper with fallback to imageio_ffmpeg / static_ffmpeg).
5. Implement `src/watcher/file_locker.py` (3-tier Windows lock detector with Win32 CreateFile dwShareMode=0, size debounce, and fallback).
6. Implement `src/watcher/ingest_watcher.py` (Async directory watcher with debouncing, polling fallback, and pipeline handoff).
7. Implement `src/pipeline/job_manager.py` (Thread-safe in-memory job repository with RLock, FSM transition validator, pagination/querying, and sync/async event bus).
8. Implement `src/pipeline/orchestrator.py` (Pipeline coordinator managing IngestWatcher -> probe -> job registration -> ML triggers).
9. Implement unit tests for all Milestone 1 components under `tests/tier1_feature/`.
10. Execute `pytest -v tests/tier1_feature/` and ensure all tests pass with 100% success.
11. Write a complete handoff report at `C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_worker_1\handoff.md` documenting implemented files, verification commands, and test outputs, then notify parent.
