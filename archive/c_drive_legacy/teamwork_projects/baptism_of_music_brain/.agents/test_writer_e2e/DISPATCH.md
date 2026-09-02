## 2026-08-27T10:06:03Z
You are the E2E Testing Track Specialist for the baptism_of_music_brain project.
Your working directory is C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\test_writer_e2e

MANDATORY FIRST STEPS:
1. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\ORIGINAL_REQUEST.md
2. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\PROJECT.md
3. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\TEST_INFRA.md

Task:
Design and implement the complete opaque-box E2E test suite according to the 4-tier methodology:
1. Create `tests/test_infra/media_generator.py`:
   - Procedural generator using FFmpeg `lavfi` (testsrc2, smptebars, noise, sine tones) for 4K UHD (3840x2160), 1080p, 9:16 vertical (1080x1920), and high-entropy noise patterns.
2. Create `tests/test_infra/ffprobe_validator.py`:
   - Mathematical assertion engine running `ffprobe -show_format -show_streams -print_format json` to programmatically verify video codec (e.g. h264, hevc), profile (High), pixel format (yuv420p), resolution match, frame rate precision (±0.05 FPS), audio codec (aac), audio bitrate (>=310kbps), and duration invariance.
3. Create `tests/conftest.py` with reusable fixtures (temp directories, procedural test media fixtures, mock clients).
4. Create test suites:
   - `tests/tier1_feature/`: Unit and isolated functional test cases for models, locking, prober, ml mock, api endpoints, and filtergraph.
   - `tests/tier2_boundary/`: Boundary and corner tests for in-flight locks, invalid trims, odd dimensions, silent audio, corrupt files.
   - `tests/tier3_pairwise/`: Pairwise combination tests for ingest+override, mock+render, 4K/1080p+color+loudnorm.
   - `tests/tier4_workload/`: Full end-to-end workload tests matching Acceptance Criteria 1 & 2 (`test_e2e_encoding_verification.py`, `test_e2e_pipeline_execution.py`).
5. Execute test discovery via `pytest --collect-only` to ensure 100% clean test syntax.
6. Publish `C:\Users\noahp\teamwork_projects\baptism_of_music_brain\TEST_READY.md` summarizing the test suite tiers and runner commands.
7. Write your handoff report at `C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\test_writer_e2e\handoff.md` and notify the parent orchestrator via send_message.
