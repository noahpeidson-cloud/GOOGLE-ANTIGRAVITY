## 2026-08-22T11:01:04Z

Investigate Requirement R2 (Proxy Generation & Storage Structure) and pipeline execution in `orchestrator.py` and `ffmpeg_processor.py`.
Specifically:
1. Examine `content_creation/orchestrator.py`, `content_creation/ffmpeg_processor.py`, `content_creation/config.py`, and `content_creation/metadata_tracker.py`:
   - Current directory structures (`01_RAW_INBOX`, `02_IN_PROGRESS`, `03_READY_TO_POST`, etc.).
   - How files are ingested, scanned, and routed.
   - How FFmpeg commands are currently constructed and executed in `ffmpeg_processor.py`.
2. Analyze the requirements for R2:
   - Moving / storing original 4K HDR files safely and untouched into `01_RAW/[Festival]/[Artist]` directory structure (sanitizing festival and artist names for filesystem safety).
   - Using FFmpeg to generate a lightweight 720p proxy video (`.mp4`, e.g. 720x1280 vertical or 1280x720 depending on aspect, fast preset, reasonable bitrate for editing/preview) and extracting a `.wav` file (PCM 16-bit, 44.1kHz or 22.05kHz for librosa analysis) for every 4K video.
   - Ensuring the original 4K HDR files remain pristine and untouched in `01_RAW/[Festival]/[Artist]`.
3. Check existing tests in `content_creation/tests/` (e.g. `test_ffmpeg_processor.py`, `test_ingest.py`, `test_orchestrator.py`, `test_e2e_pipeline.py`) to understand current conventions and assertions.

Deliverables:
Write your detailed findings in `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m6_survey_2\analysis.md` and a summary `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m6_survey_2\handoff.md`.
Update `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m6_survey_2\progress.md` with timestamps.
Send a message when complete.
