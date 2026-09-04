## 2026-08-24T21:09:27Z
You are teamwork_preview_worker assigned to Milestone 3 (PySpark & Gemini Omni Video Grading Engine).
Your working directory is: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\worker_m3_1
Authoritative user request: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md
Master project document: g:\My Drive\GOOGLE ANTIGRAVITY\media_pipeline\PROJECT.md
Authoritative viral formula: g:\My Drive\GOOGLE ANTIGRAVITY\media_pipeline\VIRAL_FORMULA.md
Explorer Survey 3 Analysis: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_3\analysis.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks:
1. Read ORIGINAL_REQUEST.md, PROJECT.md, VIRAL_FORMULA.md, and Explorer 3 analysis.md.
2. Implement the PySpark & Gemini Omni Video Grading Engine in `g:\My Drive\GOOGLE ANTIGRAVITY\media_pipeline\grading/`:
   - `viral_schema.py`: Pydantic V2 models (`EDMShortsViralMetrics`, `EDMViralGradingReport`, `TransientEvent`, sub-analyses) matching `VIRAL_FORMULA.md`.
   - `gemini_multimodal_client.py`: Robust client using `google-genai` SDK / `GenerateContentConfig(response_mime_type="application/json", response_schema=...)` with `tenacity` exponential backoff, rate limiting, and DLQ serialization.
   - `spark_grading_job.py`: PySpark batch pipeline designed for Dataproc Serverless, reading GCS video files/URIs, executing distributed inference via Gemini client, computing EVPI score and viral tier, and emitting structured DataFrames.
   - `test_spark_grading.py`: Deterministic local PySpark test suite processing mock video payloads, asserting that all 5 viral scores are correctly generated and Pydantic validation passes without crashing.
3. Execute the test suite: `python "g:\My Drive\GOOGLE ANTIGRAVITY\media_pipeline\grading\test_spark_grading.py"` and verify exit code 0.
4. Document all code paths and test run outputs in `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\worker_m3_1\handoff.md` and message parent when complete.
