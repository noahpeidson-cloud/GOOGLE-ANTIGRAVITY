# Milestone 4 Implementation Changes: Export Pipeline & Fuzzy Normalization

## Overview
Successfully implemented and verified Milestone 4 for the Sports Card Ecosystem Hub:
1. `sports_cards/ecosystem_hub/export.py`: Full Card Ladder 16-column export engine and fuzzy canonical normalization module.
2. `sports_cards/ecosystem_hub/tests/test_export.py`: Comprehensive test suite containing 48 deterministic unit and integration tests covering all export scenarios, normalization edge cases, leading-zero preservation, chunking boundaries, and round-trip fidelity.

---

## Detailed File Modifications

### 1. `sports_cards/ecosystem_hub/export.py` (New File)
- **Card Ladder 16-Column Constants**:
  - `CARD_LADDER_COLUMNS`: Exact 16-column canonical header list in fixed order (`Date Purchased`, `Quantity`, `Player`, `Year`, `Set`, `Variation`, `Number`, `Category`, `Condition`, `Investment`, `Estimated Value`, `Ladder ID`, `Notes`, `Date Sold`, `Sold Price`, `Image`).
  - `EXCLUDED_INTERNAL_FIELDS`: Explicit list of internal fields strictly omitted (`slab_serial_number`, `query`, `tags`, `back_image`, `ai_status`, `id`, `created_at`, `updated_at`).
  - `get_card_ladder_columns()` & `get_excluded_fields()`.
- **Fuzzy Normalization Engine**:
  - `CANONICAL_PLAYERS`: Canonical catalog covering all 22 ecosystem categories (Basketball, Baseball, Football, Hockey, Soccer, Tennis, Wrestling, Racing, Golf, Boxing, UFC/MMA, Pokemon, Magic, Metazoo, Yugioh, Fortnite, Dragonballz, Entertainment, Swimming, Softball, PopCulture, Flesh and Blood).
  - `CANONICAL_SETS`: Canonical set catalog covering major sports and TCG franchises across all categories.
  - `PLAYER_ALIASES` & `SET_ALIASES`: Fast-path alias lookup dictionaries.
  - `fold_string(s)`: Decomposes Unicode diacritics using `unicodedata.normalize('NFKD')`, strips dots/apostrophes and kanji parentheticals, lowercases and collapses whitespace for deterministic comparison.
  - `normalize_player_name(raw_name, category, canonical_dict, cutoff=0.75)`: Multi-tier matching (alias -> scoped exact folded -> scoped `difflib` -> global exact folded -> global `difflib` -> raw fallback).
  - `normalize_set_name(raw_set, year, category, canonical_dict, cutoff=0.75)`: Strips embedded year prefixes and executes multi-tier set matching.
- **Card Ladder Transformation & Export**:
  - `format_currency_value(val)`: Safe float formatting with 2 decimal precision.
  - `format_sold_price(val)`: Safe float formatting or empty string `""` for unsold cards.
  - `format_card_row_for_card_ladder(row, apply_normalization, ...)`: Formats single record, enforces leading-zero preservation on `card_number` string, strips internal 5 fields.
  - `cards_to_card_ladder_dataframe(cards, ...)` & `transform_records_to_card_ladder_df`: Constructs DataFrame with explicit string coercion on `Number`, `Year`, etc.
  - `generate_chunk_filepath(base_path, part_num, total_parts)`: Automatic `_part{i}.csv` naming scheme.
  - `export_dataframe_to_chunked_csvs(df, output_path, max_batch_size=500)` & `write_card_ladder_csv_chunks`: Writes CSVs partitioned at `max_batch_size` with `csv.QUOTE_MINIMAL` and `na_rep=""`.
  - `fetch_records_for_export(db_path, status_filter)`: Queries records matching status filter.
  - `export_card_ladder_csv(db_path, output_path, status_filter, max_batch_size, apply_normalization)`: Primary API entry point returning `(total_rows, generated_file_paths)`.
  - `validate_card_ladder_csv(csv_path)`: Forensic validation utility.

### 2. `sports_cards/ecosystem_hub/tests/test_export.py` (New File)
- Structured into 7 test classes:
  1. `TestFuzzyNormalizationEngine` (18 tests): Diacritics, exact matches, case-insensitivity, whitespace trimming, aliases, minor typos, cutoff rejection, category isolation, TCGs, custom canonical dicts, year stripping, empty inputs.
  2. `TestCardLadderCSVHeadersAndStructure` (4 tests): Exact 16 headers and sequence, internal fields exclusion, empty database export, validation utility.
  3. `TestLeadingZeroAndStringPreservation` (2 tests): Single and multi-zero preservation ('01', '007', '000', 'RC-05', '0', '0042', '01/25') across `csv.DictReader`, `pd.read_csv`, and raw text; blank number handling.
  4. `TestBatchRolloverAndChunking` (7 tests): Chunk path generator, <=500 single file, exact 500 boundary, 501 boundary (2 files), 1000 rows (2 files), 1250 rows (3 files), custom batch sizes.
  5. `TestStatusFiltering` (7 tests): Default `CLEARED`, `ALL`, `REVIEW VARIATION`, `NEEDS REVIEW`, case-insensitivity, zero match handling.
  6. `TestRoundTripSQLiteToCSVToPandas` (5 tests): Basic portfolio round-trip, variation preservation, financial precision, special characters/quotes/commas, all 22 categories.
  7. `TestExportEdgeCasesAndResilience` (5 tests): Non-existent directory creation, non-existent db error, normalization toggle on/off, WAL concurrent reads, 1000-card performance benchmark (<3.0s), helper aliases availability.

---

## Verification Summary
- Executed `py -m pytest sports_cards/ecosystem_hub/tests/test_export.py -v`: 48/48 passed in 9.21s.
- Executed full project test suite `py -m pytest sports_cards/ecosystem_hub/tests/ -v`: 637/637 passed in 33.36s with 0 errors and 0 regressions.
