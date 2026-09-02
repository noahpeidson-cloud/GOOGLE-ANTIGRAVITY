# Milestone 1 Implementation Report: Core Database & Data Models

## 1. Overview
Milestone 1 establishes the foundational data tier for the Sports Card Ecosystem Hub. It strictly enforces the 21-variable schema defined in `/sports_cards/GEMINI.md`, the 22 exact category enums, condition/slab serial validation, query auto-synthesis, parent-child ID format, WAL mode concurrency, and full SQLite CRUD operations.

## 2. Files Implemented

### 2.1 `sports_cards/ecosystem_hub/models.py`
- **Pydantic v2 Models**:
  - `CardRecord` (and aliases `CardModel`, `CardBase`, `CardCreate`): Master 21-variable ingestion model.
  - `CardExtractionSchema`: Output model for AI vision and checklist scraper modules.
  - `CardCaptureRequest`: Ingestion model for FastAPI Chrome Extension capture endpoint.
  - `CardUpdate`: Model for selective updates with field validation.
  - `CardBatchCreate`: Batch model enforcing the 500-card circuit breaker limit.
  - `SummaryStatsResponse`: Model for dashboard KPI aggregation.
- **Enums & Constants**:
  - `CardCategory`: 22 exact permitted categories (`Basketball`, `Baseball`, `Football`, `Hockey`, `Soccer`, `Tennis`, `Wrestling`, `Racing`, `Golf`, `Boxing`, `UFC/MMA`, `Pokemon`, `Magic`, `Metazoo`, `Yugioh`, `Fortnite`, `Dragonballz`, `Entertainment`, `Swimming`, `Softball`, `PopCulture`, `Flesh and Blood`).
  - `AIStatus`: Permitted statuses (`CLEARED`, `REVIEW VARIATION`, `NEEDS REVIEW`).
  - `CATEGORY_MAP`: Case-insensitive and alias mapping (`ufc` -> `UFC/MMA`, `pop culture` -> `PopCulture`, `dragon ball z` -> `Dragonballz`, `flesh & blood` -> `Flesh and Blood`).
- **Validation Rules**:
  - `player`, `set_name`: Strip whitespace, non-empty check, full Unicode & diacritic preservation.
  - `year`: 4-digit `YYYY` validation, handles multi-year strings like `2020-21` -> `2020`.
  - `date_purchased`: Normalizes ISO `YYYY-MM-DD` and unpadded `M/D/YYYY` to `MM/DD/YYYY`.
  - `card_number`: Typed strictly as `str`, preserves leading zeros (`007`, `04/102`, `RC-05`, `NNO`).
  - `condition`: `'Raw'` or graded without hyphens (`PSA 10`, `BGS 9.5`, `SGC 10`, `CGC 9.5`, `TAG 10`). Hyphens in graded condition (e.g. `PSA-10`) raise validation error.
  - `slab_serial_number`: Must be blank if `condition == 'Raw'`.
  - `query`: Auto-synthesized if omitted (`[Year] [Set] [Player] [Variation] [Condition]`). Negative exclusions (`-BGS -SGC`) are prohibited on `'Raw'` cards.
  - `ai_status`: Automatically set to `REVIEW VARIATION` if `variation` is present.
- **Helper Functions**:
  - `synthesize_query` / `calculate_query(year, set_name, player, variation="", condition="Raw") -> str`
  - `format_notes(parent_image_id, child_card_id) -> str` (`[Parent_Image_ID]-[Child_Card_ID]` e.g. `8492-105`)

### 2.2 `sports_cards/ecosystem_hub/database.py`
- **SQLite Configuration**:
  - `get_db_connection(db_path)` context manager.
  - Enables `PRAGMA journal_mode = WAL;`, `PRAGMA busy_timeout = 5000;`, `PRAGMA synchronous = NORMAL;`, `PRAGMA foreign_keys = ON;`, `PRAGMA encoding = 'UTF-8';`, and sets `conn.row_factory = sqlite3.Row`.
- **Schema DDL & Constraints (`init_db`)**:
  - `cards` table with 21 columns + `id`, `created_at`, `updated_at`.
  - `CHECK(quantity >= 1)`
  - `CHECK(length(trim(player)) > 0)`
  - `CHECK(length(year) = 4 AND year GLOB '[0-9][0-9][0-9][0-9]')`
  - `CHECK(length(trim(set_name)) > 0)`
  - `CHECK(category IN (...))` (22 exact categories)
  - `CHECK(investment >= 0.0)`
  - `CHECK(estimated_value >= 0.0)`
  - `CHECK(sold_price IS NULL OR sold_price >= 0.0)`
  - `CHECK(ai_status IN ('CLEARED', 'REVIEW VARIATION', 'NEEDS REVIEW'))`
  - `CONSTRAINT check_raw_no_slab CHECK((condition = 'Raw' AND (slab_serial_number = '' OR slab_serial_number IS NULL)) OR (condition != 'Raw'))`
  - `CONSTRAINT check_raw_no_negative_exclusions CHECK(NOT (condition = 'Raw' AND (query LIKE '%-BGS%' OR query LIKE '%-SGC%' OR query LIKE '%-PSA%' OR query LIKE '%-CGC%' OR query LIKE '%-CSG%' OR query LIKE '%-BVG%')))`
  - Indexes on `ai_status`, `category`, `player`, `(year, set_name)`, `notes`, `query`.
- **CRUD Methods & API Contracts**:
  - `insert_card(card_data, db_path=DEFAULT_DB_PATH) -> int`: Single card insert.
  - `insert_cards_batch(cards, db_path=DEFAULT_DB_PATH, chunk_size=500) -> list[int]`: Atomic batch insert with 500-chunk rollover.
  - `get_card_by_id(card_id, db_path=DEFAULT_DB_PATH) -> dict | None`: Single card retrieval.
  - `get_all_cards(status_filter=None, category_filter=None, search_query=None, limit=500, offset=0, order_by="id DESC", db_path=DEFAULT_DB_PATH, filters=None) -> list[dict]`: Filtered listing and pagination.
  - `update_card(card_id, updates, db_path=DEFAULT_DB_PATH) -> bool`: Updates card and re-synthesizes search query if relevant fields change.
  - `update_card_status(card_id, new_status, db_path=DEFAULT_DB_PATH) -> bool`: Fast inline status transition.
  - `delete_card(card_id, db_path=DEFAULT_DB_PATH) -> bool`: Card deletion.
  - `get_cards_for_export(status_filter="CLEARED", limit=500, db_path=DEFAULT_DB_PATH) -> list[dict]`: Export-ready query ordered by `id ASC`.
  - `get_summary_stats(db_path=DEFAULT_DB_PATH) -> dict`: Aggregated counts, investment, estimated value, category breakdown, and status breakdown.
  - `get_next_child_id(parent_image_id, db_path=DEFAULT_DB_PATH) -> int`: Relational incremental child ID counter.
  - `clear_staging_table(db_path=DEFAULT_DB_PATH) -> int`: Clears cards table.
  - `get_card_count(db_path, status_filter=None) -> int`: Card count.
  - `check_circuit_breaker(db_path, threshold=500) -> dict`: Returns `{"total_staged": count, "circuit_breaker_tripped": count >= threshold}`.
  - `capture_card_from_api(payload, db_path=DEFAULT_DB_PATH) -> dict`: Chrome Extension bridge ingest helper.

### 2.3 `sports_cards/ecosystem_hub/fixtures/mock_card_data.json`
- 12 comprehensive card fixtures spanning diverse sports (Basketball, Baseball, Football, Hockey, Soccer, Racing, Golf, UFC/MMA) and TCG categories (Pokemon, Magic, Yugioh).
- Covers Raw, PSA 10, BGS 9.5, SGC 10, CGC 9.5, TAG 10.
- Preserves leading zeros (`001`, `007`, `04/102`, `BCP-1`, `LOB-001`).
- Contains UTF-8 special characters (`Luka Dončić`, `Ronald Acuña Jr.`, `Shohei Ohtani (大谷 翔平)`).
- Formats notes as `8492-101`, `8492-102`, etc.

### 2.4 `sports_cards/ecosystem_hub/tests/test_database.py`
- 39 deterministic unit and integration tests across 5 tiers:
  - **Tier 1 (Pydantic Models)**: 15 tests verifying field validation, all 22 categories, case insensitivity, raw slab constraints, hyphen bans, leading zero preservation, multi-year normalization, date normalization, query auto-synthesis, variation auto-flagging, Unicode preservation, format_notes helper.
  - **Tier 2 (SQLite Constraints)**: 7 tests verifying table creation, WAL mode, raw slab check constraint, category check constraint, negative quantity/investment check, raw negative exclusion check, invalid status check.
  - **Tier 3 (Database CRUD)**: 10 tests verifying insert, get by id, flexible argument ordering, update with query re-synthesis, status update, delete, list with filters, export query, summary stats, get_next_child_id, clear staging table.
  - **Tier 4 (Batch & Concurrency)**: 6 tests verifying atomic batch insert, transaction rollback on invalid batch item, 500-chunk rollover, circuit breaker check, API capture payload parsing, and multi-threaded WAL reader/writer concurrency.
  - **Tier 5 (Mock Fixture Integration)**: 1 test loading `fixtures/mock_card_data.json` and verifying 100% batch insertion and field fidelity.

## 3. Verification Command and Output

```powershell
python -m pytest sports_cards/ecosystem_hub/tests/test_database.py -v
```

Execution Result:
```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
collected 39 items

sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_valid_raw_card_minimal PASSED [  2%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_valid_graded_card PASSED [  5%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_all_22_categories_valid PASSED [  7%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_category_case_insensitivity_and_aliases PASSED [ 10%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_invalid_category_raises_error PASSED [ 12%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_raw_card_with_slab_serial_rejected PASSED [ 15%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_graded_card_with_hyphen_rejected PASSED [ 17%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_leading_zero_card_number_preservation PASSED [ 20%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_multi_year_normalization PASSED [ 23%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_date_normalization PASSED [ 25%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_negative_exclusion_prohibited_on_raw PASSED [ 28%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_variation_auto_flags_ai_status PASSED [ 30%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_unicode_and_special_character_preservation PASSED [ 33%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_format_notes_formatting_and_validation PASSED [ 35%]
sports_cards/ecosystem_hub/tests/test_database.py::TestPydanticModels::test_calculate_query_variations PASSED [ 38%]
sports_cards/ecosystem_hub/tests/test_database.py::TestSQLiteConstraints::test_init_db_creates_tables_and_indexes PASSED [ 41%]
sports_cards/ecosystem_hub/tests/test_database.py::TestSQLiteConstraints::test_wal_journal_mode PASSED [ 43%]
sports_cards/ecosystem_hub/tests/test_database.py::TestSQLiteConstraints::test_db_rejects_raw_with_slab_serial PASSED [ 46%]
sports_cards/ecosystem_hub/tests/test_database.py::TestSQLiteConstraints::test_db_rejects_invalid_category PASSED [ 48%]
sports_cards/ecosystem_hub/tests/test_database.py::TestSQLiteConstraints::test_db_rejects_negative_quantity_or_investment PASSED [ 51%]
sports_cards/ecosystem_hub/tests/test_database.py::TestSQLiteConstraints::test_db_rejects_raw_negative_query_exclusions PASSED [ 53%]
sports_cards/ecosystem_hub/tests/test_database.py::TestSQLiteConstraints::test_db_rejects_invalid_ai_status PASSED [ 56%]
sports_cards/ecosystem_hub/tests/test_database.py::TestDatabaseCRUD::test_insert_and_get_card_by_id PASSED [ 58%]
sports_cards/ecosystem_hub/tests/test_database.py::TestDatabaseCRUD::test_flexible_argument_orders PASSED [ 61%]
sports_cards/ecosystem_hub/tests/test_database.py::TestDatabaseCRUD::test_update_card_and_query_resynthesis PASSED [ 64%]
sports_cards/ecosystem_hub/tests/test_database.py::TestDatabaseCRUD::test_update_card_status PASSED [ 66%]
sports_cards/ecosystem_hub/tests/test_database.py::TestDatabaseCRUD::test_delete_card PASSED [ 69%]
sports_cards/ecosystem_hub/tests/test_database.py::TestDatabaseCRUD::test_list_cards_and_filtering PASSED [ 71%]
sports_cards/ecosystem_hub/tests/test_database.py::TestDatabaseCRUD::test_get_cards_for_export PASSED [ 74%]
sports_cards/ecosystem_hub/tests/test_database.py::TestDatabaseCRUD::test_get_summary_stats PASSED [ 76%]
sports_cards/ecosystem_hub/tests/test_database.py::TestDatabaseCRUD::test_get_next_child_id PASSED [ 79%]
sports_cards/ecosystem_hub/tests/test_database.py::TestDatabaseCRUD::test_clear_staging_table PASSED [ 82%]
sports_cards/ecosystem_hub/tests/test_database.py::TestBatchAndConcurrency::test_insert_cards_batch_atomic_success PASSED [ 84%]
sports_cards/ecosystem_hub/tests/test_database.py::TestBatchAndConcurrency::test_insert_cards_batch_atomic_rollback_on_failure PASSED [ 87%]
sports_cards/ecosystem_hub/tests/test_database.py::TestBatchAndConcurrency::test_batch_insert_chunking_over_500 PASSED [ 89%]
sports_cards/ecosystem_hub/tests/test_database.py::TestBatchAndConcurrency::test_circuit_breaker_check PASSED [ 92%]
sports_cards/ecosystem_hub/tests/test_database.py::TestBatchAndConcurrency::test_api_capture_card PASSED [ 94%]
sports_cards/ecosystem_hub/tests/test_database.py::TestBatchAndConcurrency::test_sqlite_wal_multi_threaded_concurrency PASSED [ 97%]
sports_cards/ecosystem_hub/tests/test_database.py::TestMockFixtures::test_load_and_insert_mock_fixtures_json PASSED [100%]

============================= 39 passed in 1.80s ==============================
```
