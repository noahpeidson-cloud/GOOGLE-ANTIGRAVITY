# Test Infrastructure & Opaque-Box Strategy: Media Ingestion & Viral Grading Pipeline

**Document ID:** `TEST-INFRA-MED-001`  
**Target Domain:** Track 2 — Content Creation & Media Engineering  
**Version:** 1.0.0-PROPOSAL  
**Project Root:** `media_pipeline/`  

---

## 1. Executive Summary & Strategy Overview

The **Media Ingestion & Viral Grading Pipeline** is an enterprise-grade automated system designed to ingest uncompressed 4K video from Android devices over Wi-Fi, stream raw assets bit-for-bit to Google Cloud Storage (GCS), score EDM short-form video virality using PySpark on Dataproc Serverless with Gemini Multimodal Video Understanding, and maintain an adaptive machine learning optimization loop in BigQuery ML.

This document establishes the **4-Tier Opaque-Box Testing Architecture** designed to rigorously validate all functional requirements, interface contracts, boundary conditions, cross-module interactions, and end-to-end workflows without coupling test assertions to internal implementation minutiae.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          4-TIER TEST ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Tier 1: Feature Tests]         - Exhaustive functional coverage           │
│                                  - ≥5 unit/functional test cases per feature│
│                                  - All 18 Features (90+ test cases)         │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Tier 2: Boundary Tests]        - Boundary Value Analysis (BVA)            │
│                                  - Corrupt files, hash mismatch, overflows  │
│                                  - Network dropouts, rate limits, DLQ       │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Tier 3: Pairwise Tests]        - Module boundary interactions             │
│                                  - ADB -> SQLite Manifest -> GCS Sync      │
│                                  - GCS -> PySpark -> Gemini -> BQML Loop    │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Tier 4: Application Workflows] - End-to-End full pipeline simulation      │
│                                  - Device-to-BQML weight recalibration      │
│                                  - Multi-asset batch processing & recovery  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Test Strategy & Methodologies

### 2.1 Opaque-Box Requirements Traceability
Tests are derived exclusively from the authoritative requirements specified in `ORIGINAL_REQUEST.md` and the interface contracts detailed in `PROJECT.md`. Tests interact solely with public APIs, standard schemas, CLI runners, and explicit input/output contracts.

### 2.2 Category-Partition Method
Each feature input space is partitioned into equivalence classes:
- **Valid Nominal Inputs**: Standard 4K/60fps MP4/JPG files, typical duration (15–45s), valid viral score ranges (0–100).
- **Valid Edge Inputs**: Exactly 59.0s duration, single-frame videos, 0.0 or 100.0 viral scores, boundary aspect ratios (9:16 vs 16:9).
- **Invalid Inputs**: Non-existent paths, negative file sizes, truncated payloads, corrupt bitstreams, malformed JSON schemas, invalid SQL DDL.

### 2.3 Boundary Value Analysis (BVA)
Systemic testing around operational thresholds:
- Video duration caps: 0.0s, 3.0s (hook boundary), 59.0s (YouTube Shorts policy limit), 60.0s (rejection boundary).
- Bitrate thresholds: 0 Mbps, 12.0 Mbps, 15.0 Mbps, 20.0 Mbps ceiling.
- Viral scores: Negative values (<0), zero (0.0), mid-range (50.0), maximum (100.0), overflow (>100.0).
- Concurrency & retry bounds: 0 retries, max backoff exhaustion, concurrent SQLite writer locks.

### 2.4 Deterministic Zero-Compression Verification
Every byte transferred must maintain cryptographic integrity:
$$\text{SHA-256}(\text{Source Byte Stream}) == \text{SHA-256}(\text{Local Part}) == \text{SHA-256}(\text{GCS Destination})$$
Any mismatch constitutes an immediate test failure.

---

## 3. Tier Architecture & Test Layout

### 3.1 Feature Inventory (18 Features)
| # | Feature Code | Feature Name | Target Test File | Target Cases |
|---|--------------|--------------|------------------|--------------|
| 1 | `F01` | EDM Viral Formula Specification | `tier1_feature_tests.py` | ≥ 5 |
| 2 | `F02` | Ingestion Comparative Analysis & Architecture | `tier1_feature_tests.py` | ≥ 5 |
| 3 | `F03` | Ingestion Manifest & State Management | `tier1_feature_tests.py` | ≥ 5 |
| 4 | `F04` | ADB Wi-Fi Connection & Device Discovery | `tier1_feature_tests.py` | ≥ 5 |
| 5 | `F05` | Zero-Compression Media Extraction | `tier1_feature_tests.py` | ≥ 5 |
| 6 | `F06` | GCS Streaming Uploader & Integrity Verifier | `tier1_feature_tests.py` | ≥ 5 |
| 7 | `F07` | Ingestion Deterministic Mock Test Harness | `tier1_feature_tests.py` | ≥ 5 |
| 8 | `F08` | Multimodal Pydantic Grading Schema | `tier1_feature_tests.py` | ≥ 5 |
| 9 | `F09` | Gemini Omni Multimodal Video Client | `tier1_feature_tests.py` | ≥ 5 |
| 10 | `F10` | PySpark Distributed Grading Job | `tier1_feature_tests.py` | ≥ 5 |
| 11 | `F11` | Local PySpark Deterministic Test Suite | `tier1_feature_tests.py` | ≥ 5 |
| 12 | `F12` | BigQuery Relational Feature Schema | `tier1_feature_tests.py` | ≥ 5 |
| 13 | `F13` | BigQuery Sink & Connector | `tier1_feature_tests.py` | ≥ 5 |
| 14 | `F14` | BigQuery ML Model Definitions | `tier1_feature_tests.py` | ≥ 5 |
| 15 | `F15` | Dynamic ML Recalibration Loop | `tier1_feature_tests.py` | ≥ 5 |
| 16 | `F16` | BigQuery ML Deterministic Test Suite | `tier1_feature_tests.py` | ≥ 5 |
| 17 | `F17` | Opaque-Box E2E Test Suite (Tiers 1-4) | `tier1_feature_tests.py` | ≥ 5 |
| 18 | `F18` | Final E2E Integration & Adversarial Hardening | `tier1_feature_tests.py` | ≥ 5 |

### 3.2 Tier 2: Boundary & Failure Mode Suite (`tier2_boundary_tests.py`)
Covers:
- **T2.1**: Corrupt payload & truncated file bitstream handling.
- **T2.2**: Hash mismatch detection & automatic cleanup.
- **T2.3**: Video duration boundary enforcement (0s, 59.0s, >60s).
- **T2.4**: Viral metric out-of-bound rejection (<0 or >100).
- **T2.5**: Network socket drops during ADB Wi-Fi stream & backoff reconnection.
- **T2.6**: Gemini API rate limiting (429 HTTP / QuotaExceeded) and Dead Letter Queue (DLQ) dumping.
- **T2.7**: SQLite manifest database lock contention and recovery.
- **T2.8**: BigQuery ML degenerate feature matrix (all-zero scores / collinearity).

### 3.3 Tier 3: Pairwise & Cross-Feature Interaction Suite (`tier3_pairwise_tests.py`)
Covers:
- **T3.1**: ADB Sync $\rightarrow$ SQLite Manifest state progression (`PENDING` $\rightarrow$ `HASHING` $\rightarrow$ `LOCAL_SAVED`).
- **T3.2**: Local File $\rightarrow$ GCS Streaming Uploader $\rightarrow$ SHA-256 Validation $\rightarrow$ Manifest Update (`GCS_VERIFIED`).
- **T3.3**: GCS Asset URI $\rightarrow$ PySpark Batch Job $\rightarrow$ Gemini Multimodal Grading $\rightarrow$ Structured Output.
- **T3.4**: PySpark Grading Engine $\rightarrow$ BigQuery Sink Schema Mapping $\rightarrow$ Record Ingestion.
- **T3.5**: BigQuery Historical Grades $\rightarrow$ BQML `CREATE MODEL` $\rightarrow$ `ML.WEIGHTS` Extraction $\rightarrow$ Parameter Recalibration.
- **T3.6**: Gemini Rate Limit Failure $\rightarrow$ DLQ Fallback $\rightarrow$ Partial Batch PySpark Completion $\rightarrow$ Alert Log.

### 3.4 Tier 4: Application End-to-End Workflow Suite (`tier4_application_tests.py`)
Covers:
- **T4.1**: Full Golden Path: Raw 4K Video on Android $\rightarrow$ Wireless Ingestion $\rightarrow$ GCS Staging $\rightarrow$ PySpark Grading $\rightarrow$ BigQuery Ingestion $\rightarrow$ BQML Weight Update.
- **T4.2**: Concurrent Multi-Asset Batch Workflow: Ingesting 10 diverse EDM clips simultaneously with distributed hashing, upload, grading, and composite EVPI calculation.
- **T4.3**: Disaster Recovery & Idempotency Workflow: Interrupted transfer resumed at exact byte offset, duplicate file submission skipped without re-upload, stale temporary files purged.
- **T4.4**: Adaptive Feedback Loop Cycle: Ingesting a sequence of videos, publishing mock view telemetry (VVSA, APV), training BQML Boosted Tree model, updating active parameter weights, and verifying that subsequent grading uses new weights.

---

## 4. Test Execution & Standalone Runner

### 4.1 Master Test Runner (`tests/run_e2e_tests.py`)
The suite is executable either via standard `pytest` or through the standalone Python test runner:
```bash
python tests/run_e2e_tests.py
```
Or with pytest:
```bash
pytest tests/ -v
```

### 4.2 Runner Semantics
- Formatted CLI summary table detailing tests run, passed, failed, skipped, and execution time per tier.
- Zero exit code (`exit 0`) if and only if all tests pass. Non-zero exit code (`exit 1`) on any test failure.
- Pure Python execution with zero external cloud dependencies using deterministic mock fixtures.

---

## 5. Coverage & Quality Assurance Thresholds

| Metric | Minimum Target | Description |
|--------|----------------|-------------|
| **Feature Coverage** | 100% (18/18 Features) | Every inventoried feature must have dedicated test cases |
| **Tier 1 Case Count** | ≥ 90 test cases | At least 5 distinct test cases per feature |
| **Tier 2 Case Count** | ≥ 10 test cases | Extreme values, corrupt data, timeouts, lockouts |
| **Tier 3 Case Count** | ≥ 6 test cases | Multi-component pairwise interfaces |
| **Tier 4 Case Count** | ≥ 4 test cases | Full lifecycle end-to-end workflows |
| **Total Test Count** | ≥ 110 test cases | Comprehensive coverage |
| **Test Pass Rate** | 100% | Zero failing or flaky tests |
| **Execution Determinism** | 100% | Offline executable with zero external network requirement |
