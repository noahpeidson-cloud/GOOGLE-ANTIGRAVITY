## 2026-08-27T10:20:58Z

You are the Implementation Worker for Milestone 2 (Gemini Omni ML Grading Loop & FastAPI Control Plane) of the baptism_of_music_brain project.
Your working directory is C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m2_worker_1

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY FIRST STEPS:
1. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\ORIGINAL_REQUEST.md
2. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\PROJECT.md
3. Read Explorer 2 Survey Blueprint at C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\explorer_survey_2\survey_report.md

Your Exclusive Write Ownership:
- `src/ml_brain/__init__.py`, `src/ml_brain/base.py`, `src/ml_brain/mock_provider.py`, and `src/ml_brain/gemini_provider.py`
- `src/api/__init__.py`, `src/api/app.py`, and `src/api/routes.py`
- `tests/tier1_feature/test_ml_mock.py` and `tests/tier1_feature/test_api_endpoints.py`
- `tests/tier2_boundary/test_boundary_api.py`

Tasks:
1. Implement `src/ml_brain/base.py`:
   - Abstract `BaseMLProvider` with `grade_video(media_path: Path, probe_data: MediaProbeResult, user_prompt: Optional[str] = None) -> EditDecisionList` (sync and async).
2. Implement `src/ml_brain/mock_provider.py`:
   - `MockMLProvider`: Deterministic offline grading engine synthesizing valid `EditDecisionList` (cuts, trims, color grade, loudnorm audio, speed ramps) derived deterministically from media metadata / duration / hash.
3. Implement `src/ml_brain/gemini_provider.py`:
   - `GeminiOmniProvider`: Production multimodal client using `google-genai` SDK (`client.models.generate_content`) with structured JSON schema output and exponential backoff retry on 503 errors (per workspace rule R27), falling back to mock provider if API key is missing.
4. Implement `src/api/app.py`:
   - `create_app()` FastAPI app factory, lifespan manager (attaching `JobManager`, `PipelineOrchestrator`, `IngestWatcher`), CORS middleware, error handlers.
5. Implement `src/api/routes.py`:
   - REST Endpoints (supporting both `/api/v1/...` and root routes for client flexibility):
     - `GET /health` & `GET /api/v1/health` (diagnostics, FFmpeg availability, active jobs, disk free space).
     - `GET /config` & `GET /api/v1/config` (active directory paths, settings).
     - `GET /jobs` & `GET /api/v1/jobs` (list jobs with filtering & pagination).
     - `GET /jobs/{id}` & `GET /api/v1/jobs/{id}` (full job details & EDL).
     - `GET /jobs/{id}/edl` & `PUT /jobs/{id}/edl` (query / apply manual user overrides to EDL).
     - `POST /jobs/{id}/approve` & `POST /api/v1/jobs/{id}/approve` (approve EDL).
     - `POST /jobs/{id}/regrade` & `POST /api/v1/jobs/{id}/regrade` (re-grade with prompt).
     - `GET /jobs/{id}/proxy` & `GET /api/v1/jobs/{id}/proxy` (HTTP 206 Partial Content byte-range video streaming).
     - `POST /jobs/ingest/trigger` (manual file ingest trigger).
6. Implement and execute unit and integration tests:
   - `pytest -v tests/tier1_feature/test_ml_mock.py tests/tier1_feature/test_api_endpoints.py tests/tier2_boundary/test_boundary_api.py`
   - Run full test suite: `pytest -v tests/` and verify all Tier 1 and Tier 2 API/ML tests pass 100%.
7. Write a complete handoff report at `C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m2_worker_1\handoff.md` and notify parent.
