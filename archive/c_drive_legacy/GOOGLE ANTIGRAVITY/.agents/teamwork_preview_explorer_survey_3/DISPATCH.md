## 2026-08-25T04:03:49Z
You are teamwork_preview_explorer investigating R3 (GCP Spark & Gemini Omni Video Grading) and R4 (BigQuery ML Optimization Loop).
Your working directory is: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_3
Authoritative user request: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md

Task:
1. Read g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md.
2. Architect the PySpark Video Grading Engine (R3):
   - Design for Dataproc Serverless (PySpark batch job processing GCS video URIs)
   - Multimodal Gemini Video API integration (`gemini-omni-flash-api` / google-genai SDK) with structured Pydantic response schema (extracting the 5 viral parameters and composite Trending Potential score)
   - Audio and video chunking / temporal sampling logic
   - Resilience against API rate limits and token windows
   - Deterministic local PySpark testing harness using local SparkSession and mock Gemini payload.
3. Architect the BigQuery ML Optimization Loop (R4):
   - BigQuery schema definition for video grading records and metadata
   - PySpark BigQuery connector / sink logic
   - BigQuery ML SQL scripts (`CREATE OR REPLACE MODEL ... OPTIONS(model_type='kmeans' / 'boosted_tree_regressor' / 'linear_reg')`)
   - ML feedback loop: retraining model as post-performance metrics (views, likes, retention) are ingested to update parameter weights
   - Deterministic mock BigQuery validation script to verify schema generation and SQL compilation without syntax errors.
4. Document full technical designs in `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_3\analysis.md` and handoff at `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_3\handoff.md`.
5. Send a message to your parent with your summary and completion status.
