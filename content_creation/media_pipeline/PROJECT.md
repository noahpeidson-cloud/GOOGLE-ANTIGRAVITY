# Project: Media Ingestion & Viral Grading Pipeline

## Architecture
An enterprise-grade, zero-touch media engineering and machine learning pipeline that autonomously pulls uncompressed 4K video footage from Android mobile devices over local Wi-Fi, computes SHA-256 cryptographic hashes for bit-for-bit integrity, streams raw media to Google Cloud Storage (GCS), executes distributed video and audio analysis via PySpark (Dataproc Serverless) and Gemini Omni/Video Multimodal API against a 5-parameter EDM Viral Formula, and sinks structured grading metrics into BigQuery where BigQuery ML continuously trains and updates parameter weights based on post-publishing performance telemetry.

```
[Android Device (DCIM/Camera)]
        │
        ▼ (ADB Wi-Fi Sync, zero compression, sha256 checksum)
[Ingestion Daemon (ingestion/)] ───► [SQLite Manifest (`manifest.db`)]
        │
        ▼ (Streaming upload with SHA-256/CRC32c verification)
[Google Cloud Storage (gs://...)]
        │
        ▼ (Dataproc Serverless PySpark Batch Job)
[PySpark Grading Engine (grading/)] ◄───► [Gemini Omni Multimodal API]
        │                                 (Pydantic schema: 5 viral parameters)
        ▼ (BigQuery Sink Connector)
[BigQuery: `media_pipeline.video_grades`]
        │
        ▼ (CREATE OR REPLACE MODEL: BOOSTED_TREE, LINEAR_REG, KMEANS)
[BigQuery ML Optimization Loop (bqml/)]
        │
        ▼ (ML.WEIGHTS & ML.FEATURE_IMPORTANCE recalibration)
[Active Parameter Weights (`model_parameter_weights`)] ───► (Feeds back into PySpark Engine)
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | EDM Viral Formula Specification | 5 distinct, mathematically measurable parameters (HRV, DPAW, ADR-SFD, CKE-MVE, LTSS), Pydantic schemas, 0-100 scaling, and EVPI composite weighting | M1 | Survey / R1 |
| 2 | Ingestion Comparative Analysis & Architecture | Comprehensive architectural evaluation proving ADB Wi-Fi sync superiority over Google Photos API | M1 | Survey / R2 |
| 3 | Ingestion Manifest & State Management | Local SQLite manifest database tracking file transfer states, device hashes, local hashes, and GCS metadata | M2 | Survey / R2 |
| 4 | ADB Wi-Fi Connection & Device Discovery | Device manager handling mDNS discovery, wireless connect, Samsung Auto Blocker bypass, and backoff reconnection | M2 | Survey / R2 |
| 5 | Zero-Compression Media Extraction | Daemon pulling raw 4K `.mp4`/`.jpg` files via atomic `.part` staging and device-to-host `sha256sum` verification | M2 | Survey / R2 |
| 6 | GCS Streaming Uploader & Integrity Verifier | Resumable chunked upload to GCS with custom metadata and end-to-end SHA-256 hash match assertion | M2 | Survey / R2 |
| 7 | Ingestion Deterministic Mock Test Harness | Mock ADB device and Mock GCS client verifying zero-compression transfer and hash matching without hardware | M2 | Survey / R2 |
| 8 | Multimodal Pydantic Grading Schema | Strict Pydantic models (`EDMShortsViralMetrics` / `EDMViralGradingReport`) enforcing structured JSON output from Gemini API | M3 | Survey / R3 |
| 9 | Gemini Omni Multimodal Video Client | Resilient video grading client using Google GenAI SDK with retry logic, rate limit handling, and DLQ | M3 | Survey / R3 |
| 10 | PySpark Distributed Grading Job | Dataproc Serverless PySpark batch pipeline processing GCS video URIs, evaluating viral parameters, and calculating EVPI | M3 | Survey / R3 |
| 11 | Local PySpark Deterministic Test Suite | Offline PySpark test validating distributed grading logic and Pydantic object generation | M3 | Survey / R3 |
| 12 | BigQuery Relational Feature Schema | DDL for `video_grading_records`, `post_performance_metrics`, and `model_parameter_weights` | M4 | Survey / R4 |
| 13 | BigQuery Sink & Connector | PySpark BigQuery sink writing graded records to BigQuery tables | M4 | Survey / R4 |
| 14 | BigQuery ML Model Definitions | `CREATE OR REPLACE MODEL` SQL scripts for `BOOSTED_TREE_REGRESSOR`, `LINEAR_REG`, and `KMEANS` | M4 | Survey / R4 |
| 15 | Dynamic ML Recalibration Loop | Python module executing ML.WEIGHTS extraction and parameter weight normalization to close the feedback loop | M4 | Survey / R4 |
| 16 | BigQuery ML Deterministic Test Suite | Mock BigQuery test harness validating schema DDLs, SQL queries, and weight recalibration | M4 | Survey / R4 |
| 17 | Opaque-Box E2E Test Suite (Tiers 1-4) | Comprehensive requirement-driven test suite covering all features with Category-Partition, BVA, and Pairwise testing | E2E Track | Requirements |
| 18 | Final E2E Integration & Adversarial Hardening (Tier 5) | Full system integration test pass and adversarial edge-case stress verification | M5 | Requirements |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Requirement-driven test harness, test runner, and test cases across Tiers 1-4 (`TEST_READY.md`) | none | DONE |
| 1 | Research & Viral Formula Artifact | Generate authoritative `VIRAL_FORMULA.md` with >=5 distinct parameters, mathematical formulas, Pydantic schemas, and BQML DDLs | none | DONE |
| 2 | Zero-Compression Ingestion Daemon | Build ADB Wi-Fi sync daemon, SQLite manifest store, GCS uploader with SHA-256 verification, and mock test harness | none | DONE |
| 3 | PySpark & Gemini Omni Grading Engine | Build Dataproc Serverless PySpark grading job, Pydantic schema, Gemini API client, DLQ, and local test suite | M1 | DONE |
| 4 | BigQuery ML Optimization Loop | Build BigQuery schemas, BQML SQL scripts, PySpark BQ sink, feedback weight recalibration engine, and test suite | M1, M3 | DONE |
| 5 | Full Pipeline Integration & E2E Verification | Integrate all modules, execute 100% E2E test suite (Tiers 1-4), followed by Tier 5 adversarial hardening | M1, M2, M3, M4, E2E | DONE |

## Interface Contracts

### Ingestion Daemon ↔ Cloud Storage / Manifest
- Ingestion daemon produces:
  - Local raw video file: `data/raw/<video_id>.mp4`
  - GCS URI: `gs://<bucket>/raw/<video_id>.mp4`
  - Metadata: `{"video_id": str, "sha256": str, "file_size_bytes": int, "gcs_uri": str, "ingested_at": str}`
  - SQLite Manifest: Table `ingestion_manifest` with columns `(file_id, device_ip, device_path, file_name, file_size_bytes, device_mtime, device_sha256, local_staging_path, local_sha256, gcs_bucket, gcs_blob_name, gcs_crc32c, gcs_md5, status, retry_count, last_error, created_at, updated_at)`

### Cloud Storage ↔ PySpark Grading Engine
- Input to PySpark Job: DataFrame of GCS URIs / Manifest records.
- PySpark Job Output: Structured DataFrame containing `video_id`, `gcs_uri`, `hrv_score` (float), `dpaw_score` (float), `adr_sfd_score` (float), `cke_mve_score` (float), `ltss_score` (float), `evpi_composite` (float), `trending_verdict` (str), `grading_metadata` (json string).

### PySpark Grading Engine ↔ BigQuery Sink & ML Loop
- Table: `media_pipeline.video_grades`
- Table: `media_pipeline.model_parameter_weights`

## Code Layout
```
media_pipeline/
├── VIRAL_FORMULA.md                     # Authoritative EDM short-form viral grading matrix & formula
├── PROJECT.md                           # Master architecture & milestone tracking
├── TEST_INFRA.md                        # E2E test infrastructure specification
├── TEST_READY.md                        # Published when E2E test suite is complete
├── ingestion/                           # Milestone 2: Zero-compression Ingestion Daemon
│   ├── __init__.py
│   ├── manifest_store.py                # SQLite state management & hash storage
│   ├── adb_connection_manager.py        # Wireless ADB device discovery & connect
│   ├── gcs_uploader.py                  # Streaming GCS uploader with SHA-256 check
│   ├── ingestion_daemon.py              # Main daemon coordinating pull -> hash -> upload
│   └── test_ingestion_daemon.py         # Deterministic mock ADB/GCS test suite
├── grading/                             # Milestone 3: Dataproc PySpark & Gemini Omni Grading Engine
│   ├── __init__.py
│   ├── viral_schema.py                  # Strict Pydantic models for viral parameters
│   ├── gemini_multimodal_client.py      # Resilient Gemini API client with backoff & DLQ
│   ├── spark_grading_job.py             # Dataproc Serverless PySpark batch job
│   └── test_spark_grading.py            # Local PySpark deterministic test suite
├── bqml/                                # Milestone 4: BigQuery ML Optimization Loop
│   ├── __init__.py
│   ├── schema.sql                       # BigQuery table DDLs
│   ├── models.sql                       # BQML CREATE MODEL (Boosted Tree, Linear Reg, KMeans)
│   ├── feedback_loop.py                 # Weight extraction & recalibration engine
│   └── test_bqml_loop.py                # Deterministic BigQuery ML validation test suite
└── tests/                               # E2E Testing Track: Opaque-box 4-tier test suite
    ├── __init__.py
    ├── conftest.py
    ├── run_e2e_tests.py                 # Test runner
    ├── tier1_feature_tests.py           # Tier 1: ≥5 tests per feature
    ├── tier2_boundary_tests.py          # Tier 2: Boundary and corner cases
    ├── tier3_pairwise_tests.py          # Tier 3: Cross-feature combinations
    └── tier4_application_tests.py       # Tier 4: Real-world end-to-end workloads
```
