# Project: Master Technical Specification (V1_OMNICHANNEL_ARCHITECTURE_SPEC.md)

## Architecture
The Antigravity Omnichannel Architecture integrates multi-client edge capture layers (Chrome Extension Manifest V3, Next.js 16/React 19 Mobile Command Center, Local Desktop Daemon, and Edge Prompt API Capture) with an enterprise Google Cloud Platform backend. 

### High-Level Data Flow
1. **Client Edge Capture Layer**:
   - `agy_chrome_extension`: Manifest V3 extension capturing structured DOM events, text selections, and tabular data from target portals.
   - `agy_mobile`: Next.js 16 / React 19 Mobile PWA command center dispatching telemetry and pipeline triggers.
   - `agy_daemon`: Local FastAPI/Python daemon bridging desktop hardware, ADB ingestion, and Firestore commands.
   - `zero_friction_capture_extension`: On-device Gemini Nano (Chrome Prompt API) parsing.
2. **Ingestion & Edge Security Layer**:
   - Cloud Armor WAF & DDoS mitigation.
   - Cloud Run Ingestion Gateway with OAuth2/OIDC PKCE token validation.
   - Binary Protobuf serialization (`DomScrapePayload.proto`) with Cloud DLP PII sanitization.
3. **Messaging & Staging Buffers**:
   - Google Cloud Pub/Sub with deterministic ordering keys (`user_id#session_id`) and 5-attempt Dead Letter Queue (DLQ).
   - CMEK-encrypted Google Cloud Storage (GCS) staging buckets with temporal partitioning (`gs://agy-raw-lake-prod/raw_dom/YYYY/MM/DD/HH/`).
4. **Distributed Processing Tier (Apache Spark on Dataproc Serverless)**:
   - Spark Structured Streaming (10s micro-batch, RocksDB state management, write-ahead logs on GCS, 10-minute watermarking).
   - PySpark Batch ETL with vectorized Arrow/Pandas UDFs for DOM cleaning, entity resolution, and Vertex AI vector embeddings.
   - Apache Iceberg Lakehouse (Medallion: Bronze raw -> Silver cleaned -> Gold analytics) using BigLake REST Catalog and BigQuery zero-copy query federation.
5. **Orchestration & Governance**:
   - Cloud Composer (Apache Airflow 2.10+) DAGs automating hourly micro-batch reconciliation, compaction (`rewrite_data_files`), and data quality validation.
6. **Frontend, Accessibility & Performance Gates**:
   - Modern Web Guidelines: Component architecture, View Transitions, Container Queries, Popover API, offline PWA caching.
   - WCAG 2.1 Level AA & Section 508 accessibility standards (unskipped headings, ARIA live regions, focus trapping, min 48x48px tap targets, 4.5:1 color contrast).
   - Core Web Vitals budgets (LCP < 2.5s, INP < 200ms, CLS < 0.1).
   - Mandatory CI/CD testing gates (axe-core, Lighthouse CI, Pa11y, Playwright synthetic performance & a11y tests).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Ecosystem Audit & Synthesis | Comprehensive architectural audit of `agy_chrome_extension`, `agy_daemon`, `agy_mobile`, `auto_qa_builder`, and `zero_friction_capture_extension` | M1 | Survey (Explorer 1) |
| 2 | Chrome-to-GCP Transfer Protocol | Exact secure protocol specification for DOM payload capture, OAuth2/OIDC auth, Cloud Armor, and Cloud Run ingestion | M2 | Survey (Explorer 2) |
| 3 | Apache Spark Data Processing | Distributed processing design on Dataproc Serverless, Spark Structured Streaming, PySpark batch ETL, and BigLake Iceberg Lakehouse | M2 | Survey (Explorer 2) |
| 4 | Modern Web & Architecture Guidelines | Modern UI patterns, PWA service workers, resilient error boundaries, optimistic state management | M3 | Survey (Explorer 3) |
| 5 | Accessibility (a11y) Standards | WCAG 2.1 AA & Section 508 compliance, semantic HTML, ARIA rules, keyboard navigation, focus management, 48x48px touch targets | M3 | Survey (Explorer 3) |
| 6 | LCP & Web Performance Budgets | Sub-2.5s LCP engineering, resource prioritization (`fetchpriority="high"`, preconnect), image optimization, INP < 200ms, CLS < 0.1 | M3 | Survey (Explorer 3) |
| 7 | Mandatory Automated Testing Gates | CI/CD automated gates using axe-core, Pa11y, Lighthouse CI, and Playwright synthetic performance/a11y test suites | M3 | Survey (Explorer 3) |
| 8 | Master Specification Document | Complete authoring of `V1_OMNICHANNEL_ARCHITECTURE_SPEC.md` written to `apps/V1_OMNICHANNEL_ARCHITECTURE_SPEC.md` | M4 | Implementation Worker |
| 9 | Multi-Agent Verification | Rigorous review (2 Reviewers), empirical challenge (2 Challengers), and forensic integrity audit (1 Auditor) | M5 | Verification Agents |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Survey: Ecosystem Audit | Full audit of apps footprints | none | DONE |
| 2 | Survey: GCP & Spark Architecture | Cloud ingestion, Pub/Sub, Spark streaming/batch, Iceberg | none | DONE |
| 3 | Survey: Web, a11y & Performance | Modern web, WCAG 2.1 AA, LCP budgets, CI/CD gates | none | DONE |
| 4 | Master Specification Authoring | Write `apps/V1_OMNICHANNEL_ARCHITECTURE_SPEC.md` | M1, M2, M3 | IN_PROGRESS |
| 5 | Multi-Agent Verification | Reviewers, Challengers, and Forensic Auditor | M4 | PLANNED |
| 6 | Gate Evaluation & Delivery | Gate check, synthesis, and report to Sentinel | M5 | PLANNED |

## Interface Contracts & Data Schemas
### Chrome Extension ↔ GCP Ingestion Gateway
- Protocol: HTTPS POST / WSS over TLS 1.3
- Auth Header: `Authorization: Bearer <OIDC_JWT_TOKEN>`
- Content-Type: `application/x-protobuf` or `application/json`
- Ingestion Endpoint: `POST https://ingest.antigravity.internal/v1/telemetry/dom`
- Schema: `DomScrapePayload.proto` (fields: `event_id`, `client_id`, `user_id`, `session_id`, `timestamp_epoch_ms`, `source_url`, `page_title`, `dom_action`, `extracted_elements`, `raw_html_chunk`, `metadata`)

### Cloud Run Ingest ↔ Cloud Pub/Sub
- Topic: `projects/noahs-ai-bussin/topics/agy-dom-events-raw`
- Ordering Key: `${user_id}#${session_id}`
- DLQ Topic: `projects/noahs-ai-bussin/topics/agy-dom-events-dlq`

### Dataproc Spark ↔ BigLake Iceberg Lakehouse
- REST Catalog URI: `https://biglake.googleapis.com/iceberg/v1/restcatalog`
- Warehouse: `gs://agy-lakehouse-prod/warehouse`
- Tables: `bronze_dom_events`, `silver_dom_entities`, `gold_content_intelligence`

## Code Layout
- Target Specification: `G:\My Drive\GOOGLE ANTIGRAVITY\apps\V1_OMNICHANNEL_ARCHITECTURE_SPEC.md`
- Project Definition: `G:\My Drive\GOOGLE ANTIGRAVITY\apps\PROJECT.md`
- Orchestrator Metadata: `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\orchestrator_9\`
