# Handoff Report: Viral Trend Pipeline Specification & Test Architecture (R2 & R3)

**Author:** Spec Miner Subagent (`spec_miner_pipeline_1`)  
**Parent Orchestrator:** `7d41a357-3c5b-4f20-a1e5-11948f7130eb`  
**Working Directory:** `C:\Users\noahp\OneDrive\Desktop\Antigravity\.agents\spec_miner_pipeline_1`  
**Date:** 2026-08-22T23:55:00Z  
**Integrity Mode:** Benchmark  

---

## 1. Observation

Direct observations extracted verbatim from authoritative specification documents:

1. **`ORIGINAL_REQUEST.md` (lines 10, 20-25, 29-32):**
   - *"This project establishes a comprehensive Python integration test suite to validate the 'Viral Trend Pipeline' (which uses SQLite, BigQuery ML, and headless Chrome/Android extraction)..."*
   - *"R2. SQLite Mark-and-Sweep Validation: Implement a test that seeds a local `trends.db` with data spanning 30 days. Verify that the garbage collection logic successfully purges rows older than 14 days while retaining the active rolling window."*
   - *"R3. BigQuery Payload Formatting: Write tests to verify that the unnested, normalized tag arrays match the exact JSON schema expected by BigQuery's `AI.FORECAST` and `AI.KEY_DRIVERS` functions (e.g., ensuring case preservation, deduplication, and proper data types)."*
   - *"Acceptance Criteria: Running `pytest` executes all tests without hanging; The SQLite test confirms exact row counts before and after the sweep; The mock extractors yield deterministic JSON structures without attempting real network requests; The test suite completes in under 10 seconds."*

2. **`g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\viral-trend-pipeline\SKILL.md` (lines 8-21, 24-48):**
   - Section 1: *"The Mark-and-Sweep: A scheduled weekly cron job (`/schedule`) runs the pipeline. It inserts new trends and executes a hard `DELETE FROM trends WHERE date_added < date('now', '-14 days')`."*
   - Section 1: *"The View: It then generates a single, clean `current_trends.md` artifact that only contains the active rolling 14-day window."*
   - Section 3: *"Data Autocleaning: We apply the `data-autocleaning` protocol: extracting JSON arrays of tags, using `SAFE_CAST`, normalizing strings (preserving case, stripping emojis where necessary), and deduplicating."*
   - Section 3: *"AI/ML: We utilize BigQuery's `AI.FORECAST` to predict the trajectory of a hashtag's momentum, and `AI.KEY_DRIVERS` to determine which editing styles (e.g., 'stutter edit' vs 'slow zoom') drive the highest engagement."*
   - Section 4: Platforms: TikTok (tags: `#SportsCards`, `#PaniniPrizm`, `#CardLadder`, `#HardTechno`, `#RaveTok`), Instagram Reels (`#TheHobby`, `#WhoDoYouCollect`), YouTube Shorts, Facebook Reels.

3. **`bigquery_ai_ml/references/ai_forecast.md` (lines 8-85):**
   - Syntax: `AI.FORECAST(TABLE, data_col => '...', timestamp_col => '...' [, id_cols => [...], horizon => ..., confidence_level => ..., output_historical_time_series => ...])`
   - Constraints: TimesFM 2.0 foundation model, minimum 3 historical data points per series, `horizon` default 10 (range [1, 10000]), `confidence_level` default 0.95 (range (0, 1)), `context_window` [64, 2048].
   - Output fields: `id_cols`, `forecast_timestamp` / `time_series_timestamp`, `forecast_value` / `time_series_data`, `time_series_type`, `prediction_interval_lower_bound`, `prediction_interval_upper_bound`, `confidence_level`, `ai_forecast_status`.

4. **`bigquery_ai_ml/references/ai_key_drivers.md` (lines 8-51):**
   - Syntax: `AI.KEY_DRIVERS(TABLE, metric_col => '...', dimension_cols => [...], interest_label_col => '...' [, min_apriori_support => ..., top_k => ..., enable_pruning => ...])`
   - Constraints: `dimension_cols` is `ARRAY<STRING>` with 1-12 columns (cannot be `metric_col` or `interest_label_col`), `metric_col` numeric (INT64, FLOAT64, NUMERIC), `interest_label_col` BOOL (`TRUE` for interest group, `FALSE` for reference group), `min_apriori_support` [0, 1] (default 0.1), `top_k` [1, 1M] mutually exclusive with `min_apriori_support`.
   - Output fields: `drivers` (ARRAY<STRING>), `metric_interest` (NUMERIC), `metric_reference` (NUMERIC), `difference` (NUMERIC), `relative_difference` (NUMERIC), `unexpected_difference` (NUMERIC), `relative_unexpected_difference` (NUMERIC), `contribution` (NUMERIC), `apriori_support` (NUMERIC).

5. **`data_autocleaning/SKILL.md` (lines 153-185):**
   - Array & String rules: Case preservation is mandatory ("Make sure to PRESERVE CASE. DO NOT perform case conversions (e.g., LOWER(), UPPER()) unless explicitly required").
   - Trimming: Trim whitespace on string fields.
   - Array NULL filtering: BigQuery arrays cannot contain `NULL`s (`ARRAY_FILTER(array_column, e -> e IS NOT NULL)`).
   - Deduplication: `ARRAY(SELECT DISTINCT x FROM UNNEST(array_column))` for case-sensitive deduplication.

---

## 2. Logic Chain

1. **Schema Design Deduction**:
   - The pipeline processes multi-platform extraction data across 4 platforms (`tiktok`, `instagram`, `youtube`, `facebook`) and 2 domain categories (`sports_cards`, `edm`).
   - SQLite table `trends` must store the normalized tag, platform, category, date_added, structured metrics (views, shares, watch time, velocity), editing style (for key driver analysis), and raw metadata.
   - Primary key must be integer autoincrement for robust row tracking.
   - B-tree indexing on `date_added` guarantees O(log N) deletion performance during the weekly cron sweep. Composite index on `(platform, category)` optimizes downstream view generation.

2. **Garbage Collection Math & Boundary Deduction**:
   - The query specifies `DELETE FROM trends WHERE date_added < date('now', '-14 days')`.
   - In ISO-8601 date math, if today is T0, then `date('now', '-14 days')` evaluates to T0 - 14 days.
   - Rows strictly older than T0 - 14 days (i.e. dates from T0 - 29 down to T0 - 15) satisfy `date_added < T0 - 14` -> exactly 15 calendar days are purged.
   - Rows from T0 - 14 up to T0 (today) satisfy `date_added >= T0 - 14` -> exactly 15 calendar days are retained (the active 14-day rolling window including today).
   - When seeding 30 days with K rows per day:
     - Total seeded rows: 30 * K.
     - Expected purged rows: 15 * K.
     - Expected retained rows: 15 * K.
   - For test reproducibility without relying on live system clock, GC function must support an optional reference anchor date parameter `anchor_date` (defaulting to `datetime.date.today()` / `date('now')`).

3. **BigQuery Payload Transformation Deduction**:
   - Extraction inputs yield nested tag lists per post (e.g. `["#SportsCards", " #PaniniPrizm ", "#SportsCards", "#CardLadder"]`).
   - Autocleaning normalizer must:
     1. Unnest array items into discrete elements.
     2. Trim leading/trailing whitespace (`#PaniniPrizm`).
     3. Case-sensitive deduplication (`#SportsCards` appears once).
     4. Preserve exact casing (never lowercase `#SportsCards` to `#sportscards`).
     5. Filter out empty strings or nulls.
   - For `AI.FORECAST`: Format records as time-series observations grouped by `tag` (or `[platform, tag]`), requiring `date` (TIMESTAMP/DATE) and `velocity_score` / `volume` (FLOAT64/INT64), ensuring >= 3 data points per series.
   - For `AI.KEY_DRIVERS`: Format records with dimension features (`editing_style`, `platform`, `category`), boolean interest indicator (`is_viral`), and numeric metric (`views` / `engagement_score`).

---

## 3. Detailed Technical Specifications

### 3.1 SQLite Database Specification (`trends.db`)

#### 3.1.1 DDL Schema
```sql
CREATE TABLE IF NOT EXISTS trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('tiktok', 'instagram', 'youtube', 'facebook')),
    category TEXT NOT NULL CHECK (category IN ('sports_cards', 'edm')),
    date_added TEXT NOT NULL, -- Format: YYYY-MM-DD
    engagement_metrics TEXT NOT NULL, -- JSON-encoded dictionary
    editing_style TEXT, -- e.g. 'stutter edit', 'slow zoom', 'fast cuts', 'seamless loop'
    raw_metadata TEXT, -- JSON-encoded extractor metadata
    created_at TEXT DEFAULT (datetime('now', 'utc'))
);

CREATE INDEX IF NOT EXISTS idx_trends_date_added ON trends(date_added);
CREATE INDEX IF NOT EXISTS idx_trends_platform_cat ON trends(platform, category);
CREATE INDEX IF NOT EXISTS idx_trends_tag ON trends(tag);
```

#### 3.1.2 JSON Field Structure
1. `engagement_metrics`:
```json
{
    "views": 250000,
    "likes": 18500,
    "shares": 4200,
    "comments": 610,
    "watch_time_avg_sec": 14.8,
    "velocity_score": 92.4,
    "loop_rate": 1.15
}
```

2. `raw_metadata`:
```json
{
    "extractor": "chrome_devtools_accessibility_tree",
    "audio_title": "Original Sound - Techno Bunker",
    "node_id": "ax_node_49182",
    "bounding_box": {"x": 120, "y": 450, "width": 840, "height": 120}
}
```

---

### 3.2 Mark-and-Sweep Garbage Collection Specification (R2)

#### 3.2.1 Core SQL Statements
- **Sweep Deletion:**
```sql
DELETE FROM trends WHERE date_added < date(:anchor_date, '-14 days');
```
*(In live cron execution, `:anchor_date` is `'now'`)*

- **Pre/Post Count Assertions:**
```sql
SELECT COUNT(*) FROM trends;
```

- **Window Consistency Check:**
```sql
SELECT MIN(date_added), MAX(date_added) FROM trends;
```

#### 3.2.2 30-Day Seeding Model
- Given Anchor Date T0 = `2026-08-22`:
  - Day Offsets: i in {0, 1, 2, ..., 29} where Date = T0 - i days.
  - Days 0 to 14: Active rolling window (T0 down to T0 - 14 days) -> 15 dates.
  - Days 15 to 29: Expired window (T0 - 15 days down to T0 - 29 days) -> 15 dates.
  - Seeding 2 records per day -> 60 initial records.
  - After Sweep: Exactly 30 records deleted, exactly 30 records retained.
  - Retained date range: [T0 - 14 days, T0].

#### 3.2.3 View Generation Specification (`current_trends.md`)
- Generates markdown artifact summarizing the active 14-day window grouped by platform and category with calculated 14-day velocity and top tags.

---

## 3.3 BigQuery ML Payload Schemas & Transformation Rules (R3)

### 3.3.1 Transformation Pipeline
1. **Raw Extracted Payload**:
```json
{
    "platform": "tiktok",
    "category": "sports_cards",
    "date": "2026-08-22",
    "raw_tags": ["#SportsCards", " #PaniniPrizm ", "#SportsCards", "#CardLadder", "  "],
    "views": "150000",
    "velocity_score": "88.5",
    "editing_style": "fast cuts"
}
```

2. **Normalized Tag Array Rules**:
  - Whitespace stripping: `tag.strip()` -> `"#PaniniPrizm"`
  - Null/Empty filter: remove `""` or `None`.
  - Case preservation: Keep `#SportsCards` as `#SportsCards` (DO NOT lowercase).
  - Case-sensitive deduplication: `["#SportsCards", "#PaniniPrizm", "#CardLadder"]`.
  - Type casting: `SAFE_CAST(views AS INT64)`, `SAFE_CAST(velocity_score AS FLOAT64)`.

### 3.3.2 `AI.FORECAST` Payload Specification
- **Input Table/JSON Schema**:
```json
[
    {
        "tag": "#SportsCards",
        "date": "2026-08-20T00:00:00Z",
        "velocity_score": 75.2
    },
    {
        "tag": "#SportsCards",
        "date": "2026-08-21T00:00:00Z",
        "velocity_score": 82.0
    },
    {
        "tag": "#SportsCards",
        "date": "2026-08-22T00:00:00Z",
        "velocity_score": 89.4
    }
]
```
- **Constraints**:
  - Minimum 3 historical data points per time-series ID (`tag`).
  - Timestamp ordering: monotonically non-decreasing.
  - Required parameters for invocation: `data_col => 'velocity_score'`, `timestamp_col => 'date'`, `id_cols => ['tag']`, `horizon => 7`, `confidence_level => 0.95`.

### 3.3.3 `AI.KEY_DRIVERS` Payload Specification
- **Input Table/JSON Schema**:
```json
[
    {
        "editing_style": "stutter edit",
        "platform": "tiktok",
        "category": "edm",
        "is_viral": true,
        "views": 450000
    },
    {
        "editing_style": "slow zoom",
        "platform": "tiktok",
        "category": "edm",
        "is_viral": false,
        "views": 25000
    }
]
```
- **Constraints**:
  - `metric_col`: `'views'` (INT64/FLOAT64)
  - `interest_label_col`: `'is_viral'` (BOOL: `TRUE` for interest group, `FALSE` for reference group)
  - `dimension_cols`: `['editing_style', 'platform', 'category']` (1-12 columns)
  - `min_apriori_support`: `0.05`

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | SQLite Ingestion | `insert_trend` | Ingests parsed trend record with JSON metrics and raw metadata | Trend dataclass / dict | Row ID (int) | Raises `sqlite3.IntegrityError` on invalid platform/category enum | `SKILL.md` §1, DDL spec |
| 2 | SQLite GC | `mark_and_sweep` | Purges trends strictly older than 14 days from anchor date | `trends.db` connection, optional `anchor_date` | `SweepResult(purged_count, retained_count)` | Rolls back transaction on error | `ORIGINAL_REQUEST.md` R2, `SKILL.md` §1 |
| 3 | SQLite View | `generate_current_trends_view` | Compiles active 14-day rolling window into clean markdown view | SQLite DB connection | Markdown string (`current_trends.md`) | Empty markdown table if 0 rows | `SKILL.md` §1 |
| 4 | Tag Normalization | `normalize_tag_array` | Cleans, trims, deduplicates, and preserves case of tag lists | Raw list/array of string tags | Clean, deduplicated, case-preserved list of strings | Drops empty/None strings, handles empty list gracefully | `ORIGINAL_REQUEST.md` R3, `data-autocleaning` |
| 5 | BigQuery Payload | `build_ai_forecast_payload` | Transforms unnested trend series into valid BigQuery `AI.FORECAST` payload | List of trend records | List of dicts matching `AI.FORECAST` schema | Raises `ValueError` if series has <3 historical points | `bigquery_ai_ml/ai_forecast.md` |
| 6 | BigQuery Payload | `build_ai_key_drivers_payload` | Transforms trend records into valid BigQuery `AI.KEY_DRIVERS` TVF input table payload | List of trend records, threshold config | List of dicts with dimensions, boolean interest label, and numeric metric | Raises `ValueError` if dimension columns empty or >12 | `bigquery_ai_ml/ai_key_drivers.md` |
| 7 | Multi-platform Support | Platform Enumeration | Enforces strict platform validation across TikTok, IG, YouTube, Facebook | Platform string | Validated enum | Rejects invalid platforms (e.g. 'twitter') | `SKILL.md` §2, §4 |
| 8 | Category Track Isolation | Category Enumeration | Enforces strict category validation across sports_cards and edm | Category string | Validated enum | Rejects invalid categories | `GEMINI.md` R1, `SKILL.md` §4 |

---

## Edge Cases

| # | Feature | Input | Observed / Expected Behavior |
|---|---------|-------|---------------------------|
| 1 | Mark-and-Sweep Boundary | Date added exactly equal to `date('now', '-14 days')` | Retained in active window (condition `<` does not match). |
| 2 | Mark-and-Sweep Boundary | Date added equal to `date('now', '-15 days')` | Purged from DB (`'YYYY-MM-DD' < date('now', '-14 days')` is TRUE). |
| 3 | Empty DB Sweep | Run mark-and-sweep on empty `trends.db` | Purged: 0, Retained: 0, exit status 0 without error. |
| 4 | All-Expired DB | 50 rows all dated 20 days ago | Purged: 50, Retained: 0. |
| 5 | All-Fresh DB | 50 rows all dated today | Purged: 0, Retained: 50. |
| 6 | Tag Array with Case Variations | `["#SportsCards", "#sportscards", "#SPORTSCARDS"]` | All 3 preserved as distinct tags (case preservation without forced lowercasing). |
| 7 | Tag Array with Exact Duplicates & Whitespace | `["#HardTechno", " #HardTechno ", "#HardTechno"]` | Deduplicated to single `"#HardTechno"`. |
| 8 | Tag Array with Nulls/Empty | `["#EDM", "", None, "  ", "#RaveTok"]` | Sanitized to `["#EDM", "#RaveTok"]`. |
| 9 | AI.FORECAST History Constraint | Series with only 2 historical dates | Flagged as insufficient data points (minimum 3 required by TimesFM 2.0). |
| 10 | AI.KEY_DRIVERS Dimensions | 0 dimension columns or 13 dimension columns | Error raised (BigQuery ML requires 1-12 dimension columns). |
| 11 | Malformed Engagement JSON | JSON string missing closing bracket or invalid types | `SAFE_CAST` fallback or schema validation error before insertion. |
| 12 | 500-Row Batch Boundary | Ingestion batch exceeding 500 records | Trigger chunked commit / circuit breaker before memory exhaustion. |

---

## 4. Comprehensive Test Cases (Tier 1-4)

### Tier 1: Category-Partition Tests (Equivalence Partitioning)
- **TC-T1-01 (Platform Partitioning)**: Test insertion, normalization, and payload generation across all 4 valid platforms (`tiktok`, `instagram`, `youtube`, `facebook`).
- **TC-T1-02 (Category Partitioning)**: Test isolation and schema compliance for `sports_cards` and `edm` categories.
- **TC-T1-03 (Date Window Partitioning)**: Verify 3 partitions: Future dates (rejected/clamped), Active window [0 to -14 days] (retained), Expired window [<-14 days] (purged).
- **TC-T1-04 (Viral Threshold Partitioning)**: Test `is_viral` boolean assignment for `AI.KEY_DRIVERS` across low (<50k views), medium (50k-100k), and viral (>100k) partitions.

### Tier 2: Boundary Value Analysis (BVA)
- **TC-T2-01 (GC Exact 14-Day Boundary)**:
  - Day -13: Retained
  - Day -14: Retained (boundary)
  - Day -15: Purged (boundary)
- **TC-T2-02 (Row Count Boundaries)**:
  - 0 rows (empty table GC)
  - 1 row in expired window (purges to 0)
  - 1 row in active window (retains 1)
  - 500 rows (batch staging limit)
- **TC-T2-03 (Tag List Length Boundaries)**:
  - Empty tag list `[]`
  - 1 tag `["#SportsCards"]`
  - Maximum tags (e.g. 15 tags for IG Reels)
- **TC-T2-04 (AI.FORECAST Time Points)**:
  - 1 point: Invalid (rejected)
  - 2 points: Invalid (rejected)
  - 3 points: Valid (minimum boundary accepted)
  - 30 points: Valid (full 30-day forecast horizon)

### Tier 3: Pairwise Combinatorial Tests
- Matrix: `Platform` (4) x `Category` (2) x `Editing Style` (4: fast cuts, stutter edit, slow zoom, seamless loop) x `Engagement Level` (3: low, med, high).
- Covers all 2-way interactions to ensure no combination generates unparseable JSON or invalid BigQuery payloads.

### Tier 4: Real-World Workloads & Stress Testing
- **TC-T4-01 (Full 30-Day Multi-Platform Ingestion & Sweep)**:
  - Seed 60 records across 4 platforms and 2 categories over 30 days.
  - Execute sweep with reference date.
  - Assert exact pre-count = 60, post-count = 30.
  - Assert `current_trends.md` generation.
- **TC-T4-02 (Sequential Sweeps / Idempotency)**:
  - Run sweep twice consecutively on same anchor date -> second sweep purges 0 rows, retains 30 rows.
- **TC-T4-03 (End-to-End BigQuery Export)**:
  - Feed retained 30 records into BigQuery normalizer.
  - Generate and validate `AI.FORECAST` payload against JSON schema.
  - Generate and validate `AI.KEY_DRIVERS` payload against JSON schema.
- **TC-T4-04 (Execution Performance Benchmark)**:
  - Run full suite of 25+ unit and integration tests under `pytest`.
  - Assert total test suite execution runtime < 2.0 seconds (well within the < 10.0 second acceptance criteria).

---

## 5. Caveats

- **No live Google Cloud or BigQuery connection:** All BigQuery ML tests must validate against deterministic schema models, type validators, and mock response structures without performing live cloud API calls.
- **SQLite date functions:** SQLite `date('now')` utilizes UTC system time. In tests, the GC function MUST accept an optional `anchor_date` parameter to guarantee 100% deterministic test execution across different timezones and execution dates.
- **No external heavy packages:** The implementation must rely strictly on standard library (`sqlite3`, `datetime`, `json`, `dataclasses`, `typing`) and `pytest` + `pandas` if required, respecting workspace tooling boundaries.

---

## 6. Conclusion

The specification mining for the Viral Trend Pipeline integration test suite (R2 and R3) is complete and fully grounded in authoritative sources:
1. SQLite schema and 14-day rolling window mark-and-sweep mechanics are unambiguously specified with exact mathematical boundaries.
2. BigQuery ML payload formatting for `AI.FORECAST` and `AI.KEY_DRIVERS` is comprehensively defined, including array unnesting, case-preserving deduplication, null filtering, and type casting rules.
3. A 4-tier test architecture is established to guarantee exhaustive test coverage, rapid test execution (<10s), and total test reproducibility.

---

## 7. Verification Method

To verify these specifications:
1. Inspect `handoff.md` and verify all DDL, SQL queries, and JSON payloads.
2. Run unit and integration tests using `pytest` once implemented:
   ```bash
   pytest -v tests/test_sqlite_gc.py tests/test_bigquery_payloads.py
   ```
3. Verify test execution finishes in < 10 seconds with 100% passing tests and zero network calls.
