# Milestone 6 Changes: Full Opaque-Box E2E Acceptance Test Suite

## Overview
Implemented `sports_cards/ecosystem_hub/tests/test_e2e_acceptance.py` providing complete, deterministic, opaque-box E2E acceptance verification for all requirements in `ORIGINAL_REQUEST.md` (Tiers 1-5).

## Created Files
- `sports_cards/ecosystem_hub/tests/test_e2e_acceptance.py`: Comprehensive test suite containing 21 test methods across 5 test classes.

## Coverage Summary

### Tier 1: Central Hub Acceptance
- `test_app_py_compiles_cleanly`: Programmatic validation of `app.py` via `ast.parse` and `py_compile.compile`.
- `test_app_py_initializes_without_errors`: Headless initialization and layout validation via Streamlit `AppTest`.
- `test_insert_and_retrieve_21_variable_mock_row`: Inserts a full 21-variable mock row into SQLite and verifies exact field, type, and default retrieval.
- `test_all_22_exact_category_constraints`: Validates insertion across all 22 exact categories and verifies DB CHECK constraint rejection on invalid categories.
- `test_query_synthesis_and_sanitization`: Verifies formula `[Year] [Set] [Player] [Variation] [Condition]` and negative exclusion blocking (`-PSA`, `-BGS`, etc.) on Raw cards.
- `test_raw_card_no_slab_serial_constraint`: Verifies DB CHECK constraint and Pydantic validation forbidding slab cert numbers on Raw cards.

### Tier 2: Ingestion Acceptance
- `test_scraper_beckett_sample_fixture_parsing`: Points `scraper_ingest.py` at `fixtures/beckett_sample.html`, validating extraction of >=3 cards (Wembanyama, Dončić, Curry, Henderson, Miller) with card numbers (`01`, `007`, `75`), player names, and teams.
- `test_scraper_to_database_sequential_notes`: Ingests scraped cards into database with parent ID `8492` and verifies sequential tracking notes (`8492-101`, `8492-102`, etc.).
- `test_ai_vision_mock_extraction_schema_conformity`: Calls `extract_card_from_image(mock=True)` and verifies schema conformity against `CardExtractionSchema` and 21-variable schema.
- `test_ai_vision_variation_review_status_flagging`: Tests automatic status transition to `REVIEW VARIATION` when variations/parallels are detected.
- `test_ai_vision_batch_ingestion_to_database`: Validates batch extraction and database ingestion for mock image paths.

### Tier 3: API Bridge & Sales Listing Acceptance
- `test_chrome_extension_post_capture_persists_to_db`: Submits `POST /api/v1/cards/capture` payload and verifies database persistence, synthesized query, and tracking notes.
- `test_chrome_extension_auto_child_id_increment`: Tests automatic child ID incrementing on consecutive API captures (`8492-101`, `8492-102`, `8492-103`).
- `test_sales_listing_generator_facebook_marketplace_specs`: Validates complete Facebook Marketplace copy generation:
  - Title < 100 characters, SEO formatted, sanitized of forbidden buzzwords (`INVESTMENT`, `FIRE`, `L@@K`, etc.) and emojis.
  - Formatted price with payment terms.
  - Key specifications bullets.
  - Condition and authenticity notes.
  - Shipping and local pickup terms.
  - Exactly 6 to 8 targeted hashtags.
- `test_sales_listing_via_api_endpoints`: Verifies `/api/v1/cards/{id}/listing` and `/api/v1/sales/generate` FastAPI endpoints.

### Tier 4: Export Pipeline Acceptance
- `test_export_card_ladder_csv_generation_and_headers`: Validates export to `CardLadder_Bulk_Upload.csv` with exactly 16 canonical headers in exact sequence.
- `test_exclusion_of_internal_variables`: Validates that internal database variables (`slab_serial_number`, `query`, `tags`, `back_image`, `ai_status`, `id`) are strictly excluded from the CSV.
- `test_leading_zero_preservation_raw_bytes_and_pandas`: Proves leading zero preservation (`01`, `007`, `000`, `04/102`) via raw byte inspection and pandas `read_csv(dtype=str)`.
- `test_500_card_batch_chunking`: Tests exporting 505 cards with `max_batch_size=500`, verifying split into `_part1.csv` (500 rows) and `_part2.csv` (5 rows), each with exact 16 headers.
- `test_fuzzy_normalization_in_export`: Tests normalization of player names (e.g. `'Luka Doncic'` -> `'Luka Dončić'`, `'Steph Curry'` -> `'Stephen Curry'`) and sets (e.g. `'prizm'` -> `'Panini Prizm'`, `'topps chrome bb'` -> `'Topps Chrome'`).

### Tier 5: Full Omnichannel Lifecycle Scenario
- `test_full_omnichannel_e2e_pipeline`: Exercises the entire pipeline lifecycle end-to-end: Scraper HTML ingest + AI Vision ingest + Chrome Extension API ingest -> SQLite staging -> AI status clearance -> Sales listing generation -> 16-column Card Ladder CSV export -> Forensic CSV validation.

## Test Results
- `python -m pytest sports_cards/ecosystem_hub/tests/test_e2e_acceptance.py -v`: 21 passed in 5.58s.
- `python -m pytest sports_cards/ecosystem_hub/tests/`: 915 passed in 146.06s (100% pass rate, 0 failures).
