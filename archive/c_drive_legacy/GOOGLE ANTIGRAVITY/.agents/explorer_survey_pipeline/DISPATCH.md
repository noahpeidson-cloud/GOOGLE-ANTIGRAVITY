## 2026-08-24T21:01:04Z

<USER_REQUEST>
You are Explorer 3 (Survey & Spark / Gemini / BigQuery Pipeline).
Your working directory is: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_survey_pipeline
The project root is: g:\My Drive\GOOGLE ANTIGRAVITY\media_pipeline
Authoritative user request file: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md

Mission:
Investigate and design the end-to-end processing and ML optimization pipeline:
1. Dataproc Serverless PySpark Architecture: PySpark batch job structure, GCS video ingestion, partitioning, distributed execution, resilience, and output formatting.
2. Gemini Video & Audio Multimodal Understanding (`gemini-omni-flash-api` / Google GenAI SDK `google-genai`): Video URI passing vs local streaming, prompt design for extracting viral parameters according to `VIRAL_FORMULA.md`, structured output extraction using Pydantic models.
3. BigQuery Integration & BigQuery ML Optimization Loop:
   - BigQuery schema design for video metadata, individual viral parameter scores, aggregate trending potential, and actual post-publish performance metrics.
   - BigQuery ML `CREATE OR REPLACE MODEL` SQL scripts (K-Means clustering for video typology and Boosted Tree / Linear Regression for virality score calibration).
   - Feedback loop design for retraining and feature importance extraction.
4. Design interface contracts, data models (Pydantic), and mock verification strategies for Spark and BigQuery ML.

Write your findings and comprehensive design to `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_survey_pipeline\handoff.md` and `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_survey_pipeline\analysis.md`.
Maintain progress.md in your working directory.
When finished, send a message back to parent reporting your findings and the location of your report.
</USER_REQUEST>
