# Plan — Media Ingestion & Viral Grading Pipeline

## Objective
Build an enterprise-grade Media Ingestion & Viral Grading Pipeline that securely pulls uncompressed 4K videos from an Android device to Google Cloud, evaluates their trending potential using Gemini Video understanding, and stores the analytics in BigQuery for a continuous Machine Learning feedback loop.

## Phases & Milestones

### Phase 0: Survey & Deep Research (3 Explorers in Parallel)
- **Explorer 1 (Viral Research)**: Scrape and analyze web data on YouTube Shorts algorithms, EDM video pacing, drop timing, crowd energy metrics, lighting transitions, retention hooks. Formulate the mathematical/heuristic parameters for `VIRAL_FORMULA.md`.
- **Explorer 2 (Ingestion Architecture Research)**: In-depth architectural trade-off analysis of Google Photos API/automation vs. Android ADB Wi-Fi Sync (`adb pull` vs `adb sync`, zero-compression guarantees, retry strategies, Wi-Fi drop tolerance, SHA-256 integrity validation, GCS direct streaming/upload).
- **Explorer 3 (Spark, Gemini Omni & BigQuery ML Pipeline Research)**: Dataproc Serverless PySpark architecture, `gemini-omni-flash-api` / Google GenAI SDK integration, Pydantic schema validation, BigQuery connector sink, and BigQuery ML `CREATE MODEL` clustering (K-Means) / regression syntax and schema definitions.

### Milestone 1: Viral Formula Definition (R1)
- Output `VIRAL_FORMULA.md` to project root (`g:\My Drive\GOOGLE ANTIGRAVITY\media_pipeline\VIRAL_FORMULA.md`).
- Minimum 5 distinct, measurable parameters for grading short-form EDM videos (e.g., Hook Retention Index, Beat Drop Alignment & Audio Dynamics, Visual Lighting & Color Velocity, Crowd Movement / Energy Density, Pacing & Camera Movement).
- Verification: Formal schema validation and parameter measurement rubrics.

### Milestone 2: Ingestion Daemon & GCS Uploader (R2)
- Zero-compression Android ADB Wi-Fi sync daemon (`ingestion_daemon.py`).
- Fault-tolerant file sync with retry, resumption, SHA-256 checksum calculation before and after GCS transfer.
- Verification: Deterministic test suite with mock ADB transfer, proving exact SHA-256 hash match on uncompressed files.

### Milestone 3: GCP Spark & Gemini Omni Video Grading (R3)
- PySpark batch job for Dataproc Serverless (`spark_grading_job.py`).
- Gemini Omni Video/Audio multimodal grading pipeline with prompt engineering tuned to `VIRAL_FORMULA.md`.
- Strict Pydantic output schemas (`GradingResult`, `ViralScoreBreakdown`).
- Verification: Local PySpark test suite processing mock video payload returning valid structured Pydantic/JSON scores.

### Milestone 4: BigQuery ML Optimization Loop (R4)
- BigQuery sink module writing Spark structured outputs to BigQuery dataset/table.
- BigQuery ML SQL generation (`CREATE OR REPLACE MODEL ... OPTIONS(model_type='kmeans' / 'boosted_tree_regressor')`).
- Optimization loop script training and scoring models on video features vs virality.
- Verification: Mock BigQuery Python test verifying table creation and SQL syntax validation.

### Milestone 5: E2E Testing, Adversarial Hardening & Forensic Audit
- Tier 1-4 comprehensive test suite.
- Adversarial test writer / challenger verification (edge cases, corrupt headers, corrupted audio, partial syncs, zero-byte chunks).
- Forensic Integrity Audit (`teamwork_preview_auditor`).
