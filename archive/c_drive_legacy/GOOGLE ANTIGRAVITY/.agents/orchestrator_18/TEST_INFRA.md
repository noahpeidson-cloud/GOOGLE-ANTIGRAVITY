# TEST INFRASTRUCTURE SPECIFICATION
# Unified Ops Hub — Media Gallery & Catalog System (E2E Test Architecture)

## 1. Test Philosophy & Execution Protocol
- **Opaque-Box & Requirement-Driven**: Tests validate external interface contracts (`MediaCatalogManager` Python API and FastAPI Gateway REST endpoints) strictly against requirements in `ORIGINAL_REQUEST.md` and `PROJECT.md`.
- **Zero-Discretion Mandate (Rule R2)**: Zero hardcoded or self-certifying assumptions. Every assertion is a "Loud Assertion" with deterministic, unyielding verification of return values, schema constraints, record counts, and HTTP status codes.
- **Sandboxed Isolation**: Each test runs in an isolated `tmp_path` temporary SQLite database with `PRAGMA foreign_keys = ON;` and `PRAGMA journal_mode = WAL;` to prevent side effects or data contamination across test runs.
- **Python Execution Standard (Rules R16 / R18)**: All test executions use `python -m pytest` with absolute imports.

---

## 2. Test Execution Commands & Environment

### Python Backend Test Harness
- **Runtime**: Python 3.13.14 (win32)
- **Framework**: `pytest 9.1.1`, `fastapi.testclient.TestClient`, `sqlite3`
- **Execution Command**:
  ```powershell
  python -m pytest tests/test_e2e_gallery_suite.py -v
  ```

---

## 3. Comprehensive 4-Tier Test Matrix

| Tier | Category | Minimum Target | Target File | Scope |
|------|----------|:--------------:|-------------|-------|
| **Tier 1** | Feature Coverage | ≥5 tests | `tests/test_e2e_gallery_suite.py` | Schema creation, album creation, media insertion, relational join retrieval, batch grading dispatch. |
| **Tier 2** | Boundary & Corner Cases | ≥5 tests | `tests/test_e2e_gallery_suite.py` | Empty albums, non-existent album/media IDs, special characters/Unicode/G: drive paths, zero-selection batch grade rejection, large catalog queries (50+ items). |
| **Tier 3** | Cross-Feature Combinations | ≥3 tests | `tests/test_e2e_gallery_suite.py` | Ingestion -> Catalog DB -> API retrieval; Cascade deletion of Album removing all child Media; Batch grading status updates reflected across catalog queries. |
| **Tier 4** | Real-World Application Scenarios | ≥2 tests | `tests/test_e2e_gallery_suite.py` | Multi-album concurrent workflow with simultaneous querying and status updates under SQLite WAL mode; Full end-to-end lifecycle from ingestion to grading and cleanup. |

---

## 4. Test Case Catalog & Expected Output Derivation

### Tier 1: Feature Coverage
1. **`test_t1_schema_creation_and_tables`**:
   - *Target*: `MediaCatalogManager.create_schema()` / `sqlite_master` table metadata.
   - *Verification*: Connects to newly created database, executes schema setup, queries `sqlite_master` to assert `albums` table, `media` table, indexes (`idx_media_album_id`, `idx_media_grading_status`, `idx_media_upload_status`, `idx_albums_event_date`), and foreign key definitions.
   - *Expected Source*: `PROJECT.md` Section 1 & `analysis.md` Section 3.1 schema DDL.
2. **`test_t1_album_creation_and_attributes`**:
   - *Target*: `MediaCatalogManager.create_album()` and `GET /api/v1/media/albums`.
   - *Verification*: Inserts an album with title, description, event_date, source_device. Asserts returned album ID, created timestamp, default `total_media_count=0`, and `status='INGESTED'`.
   - *Expected Source*: `PROJECT.md` Interface Contracts.
3. **`test_t1_media_insertion_with_gdrive_paths`**:
   - *Target*: `MediaCatalogManager.add_media_item()` and schema constraints.
   - *Verification*: Inserts media records linked to an album with raw paths (`G:\My Drive\...`), proxy paths (`/proxies/...` or `G:\..._proxy.mp4`), resolution, duration, fps, and file size. Asserts media ID generation and default status values (`PENDING`, `UNGRADED`).
   - *Expected Source*: `ORIGINAL_REQUEST.md` Acceptance Criteria 1.
4. **`test_t1_relational_join_query_by_album`**:
   - *Target*: `MediaCatalogManager.get_album_media(album_id)` / `GET /api/v1/media/albums/{album_id}/media`.
   - *Verification*: Inserts 1 album and 3 media entries, executes relational join query. Asserts exactly 3 media records returned, all matching the album ID, with accurate attributes and ordering.
   - *Expected Source*: `ORIGINAL_REQUEST.md` Acceptance Criteria 1.
5. **`test_t1_batch_grading_dispatch`**:
   - *Target*: `MediaCatalogManager.update_grading_status()` / `POST /api/v1/ml/grade/batch` (or `/api/v1/media/grade/batch`).
   - *Verification*: Dispatches a batch grading request with an array of media IDs `["med_001", "med_002"]`. Asserts response returns `status="QUEUED"`, valid `job_id`, and `queued_count=2`.
   - *Expected Source*: `PROJECT.md` REST Endpoints Contract.

### Tier 2: Boundary Value Analysis & Edge Cases
6. **`test_t2_empty_album_handling`**:
   - *Target*: `MediaCatalogManager.get_album_media()` for an album with 0 media items.
   - *Verification*: Creates album with no media. Queries album media and full catalog. Asserts returns empty list `[]` without raising exceptions; album `total_media_count` equals `0`.
   - *Expected Source*: Boundary Value Analysis / Empty State Robustness.
7. **`test_t2_nonexistent_ids_queries_and_updates`**:
   - *Target*: Querying/updating non-existent `album_id` or `media_id`.
   - *Verification*: Queries `get_album_media("nonexistent_alb_999")` -> returns `[]` or 404; updates grading status on nonexistent media IDs -> returns `0` modified items or isolates safely without crashing.
   - *Expected Source*: Robustness against orphaned references.
8. **`test_t2_special_characters_and_unicode_paths`**:
   - *Target*: Filenames and paths containing spaces, brackets, hashes, single quotes, and Unicode/emojis (e.g., `G:\My Drive\GOOGLE ANTIGRAVITY\raw\Clip #1 [Ultra] 100% (4K) — 🎵 'Mainstage'.mp4`).
   - *Verification*: Inserts and retrieves records with complex strings. Asserts exact character preservation and proper SQL parameterization without syntax errors.
   - *Expected Source*: Global Steering Directives & Adversarial Integrity.
9. **`test_t2_zero_selection_batch_grading_rejection`**:
   - *Target*: `POST /api/v1/ml/grade/batch` with `{"media_ids": []}` or empty input.
   - *Verification*: Dispatches empty array payload. Asserts gateway returns HTTP 422 Unprocessable Content (or 400 Bad Request), preventing empty background ML job dispatch.
   - *Expected Source*: `analysis.md` Section 5 (T2.5).
10. **`test_t2_large_catalog_query_scalability`**:
    - *Target*: Querying an album containing 50+ media items.
    - *Verification*: Inserts 60 media records across multiple albums. Queries `get_album_media()` and `get_full_catalog()`. Asserts all 60 items are retrieved intact with correct pagination/sorting and execution time under 100ms.
    - *Expected Source*: Scalability & Stress Analysis.

### Tier 3: Cross-Feature Combinations
11. **`test_t3_ingest_to_catalog_db_to_api_retrieval`**:
    - *Target*: Ingestion pipeline -> `MediaCatalogManager` -> FastAPI REST API `/api/v1/media/albums`.
    - *Verification*: Simulates ingestion daemon creating an album and adding 3 media items. Queries via FastAPI `TestClient`. Asserts JSON structure matches TypeScript dashboard models with nested media items and accurate count aggregations.
    - *Expected Source*: `PROJECT.md` Feature 1, 2, 3 Integration.
12. **`test_t3_foreign_key_cascade_album_deletion`**:
    - *Target*: SQLite `PRAGMA foreign_keys = ON;` and `ON DELETE CASCADE`.
    - *Verification*: Creates album with 4 media items. Deletes album record via `delete_album(album_id)` or SQL `DELETE FROM albums`. Queries `media` table directly. Asserts all 4 child media records are automatically deleted by SQLite foreign key cascade with 0 orphaned rows remaining.
    - *Expected Source*: `PROJECT.md` Section Database Layer.
13. **`test_t3_batch_grading_status_propagation`**:
    - *Target*: Batch grading dispatch -> status update in SQLite -> catalog queries reflect updated status.
    - *Verification*: Media items initially in `UNGRADED` / `PENDING` state. Dispatches batch grade -> updates status to `QUEUED` -> completes grading with EVPI score `89.5` and verdict `VIRAL_READY`. Asserts full catalog query and album query immediately return updated status and EVPI metrics.
    - *Expected Source*: `PROJECT.md` Feature 9, 10, 11 Integration.

### Tier 4: Real-World Workload & Concurrency
14. **`test_t4_sqlite_wal_concurrent_reads_and_writes`**:
    - *Target*: SQLite WAL mode under concurrent multithreaded load.
    - *Verification*: Spawns 4 concurrent writer threads continuously adding media items and updating grading statuses, while 6 reader threads continuously query `get_full_catalog()` and `get_album_media()`. Asserts 0 `sqlite3.OperationalError: database is locked` exceptions and 100% data consistency.
    - *Expected Source*: `analysis.md` Section 5 (T4.1).
15. **`test_t4_full_lifecycle_e2e_workflow`**:
    - *Target*: Complete end-to-end media catalog lifecycle.
    - *Verification*:
      1. Create Album `Ultra Miami 2026 Raw Drops`.
      2. Ingest 5 raw clips with G: drive paths and proxy references.
      3. Verify album listing returns 5 items with `total_media_count=5`.
      4. Select 2 clips and trigger batch ML grading.
      5. Update grading results with EVPI score calculations (e.g. 91.2 EVPI, `VIRAL_READY`).
      6. Query catalog and verify 2 clips are `GRADED` while 3 remain `UNGRADED`.
      7. Trigger cascade deletion of album and verify complete database cleanup.
    - *Expected Source*: End-to-End Mission Objective.

---

## 5. Pass/Fail Gates & Quality Standards
- **Gate 1 (Zero Discretion)**: No hardcoded mocks bypassing SQL logic. All assertions verify live database state or API contract schemas.
- **Gate 2 (Isolation)**: Every test case provisions an independent temporary database file via `tmp_path`.
- **Gate 3 (Resiliency)**: All database connections enforce `PRAGMA foreign_keys = ON;`, `PRAGMA journal_mode = WAL;`, and `PRAGMA busy_timeout = 5000;`.
