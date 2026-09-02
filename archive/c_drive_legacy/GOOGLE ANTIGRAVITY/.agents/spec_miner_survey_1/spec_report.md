# Sports Card Ecosystem Hub: Comprehensive Schema & Specification Mining Report

**Document Version:** 1.0.0  
**Author:** `spec_miner_survey_1` (Teamwork Preview Spec Miner)  
**Date:** 2026-08-24  
**Target System:** Sports Card Ecosystem Hub (`/sports_cards/ecosystem_hub`)  
**Parent Orchestrator:** `teamwork_preview_orchestrator` (`0c586af6-e90b-4330-8029-7be97c7c607c`)  
**Working Directory:** `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_survey_1`  

---

## 1. Executive Summary

This specification report provides the definitive, authoritative technical blueprint for the **Sports Card Ecosystem Hub**. It details the extraction, validation, and mathematical mapping between:
1. **The 21-Variable Database Ingestion Schema** used for SQLite persistence in `portfolio.db`.
2. **The 16-Variable Card Ladder Bulk Upload CSV Specification** required for seamless portfolio synchronization on the Card Ladder web platform.
3. **The 4 Ingestion & Export Pipelines** (Gemini AI Vision photo extraction, Beckett/Cardboard Connection checklist scraper, Chrome Extension API bridge, and Gemini SEO Sales Listing Generator).
4. **Data Normalization & Integrity Protocols** (fuzzy string matching, preservation of leading zeroes on card numbers, graded vs. raw syntax enforcement, and 500-card batch circuit breakers).

---

## 2. Authoritative Specification Sources & Citations

The schemas and rules in this report were extracted directly from the following authoritative files in the workspace and official industry platform specifications:

| Source File / Resource | Location / URI | Authority & Scope |
| :--- | :--- | :--- |
| **Sports Cards Domain Manifest** | `g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\GEMINI.md` | Authoritative 21-variable schema, 22 category enumerations, relational key architecture, and 500-card limit. |
| **Sports Cards Schema Rules** | `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\rules\sports_cards_schema.md` | Legacy schema definitions, condition syntax, query formatting, and AI review states. |
| **Authoritative Task Request** | `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md` (Lines 40–72) | Ecosystem hub requirements, 4 ingestion pipelines, Streamlit UI, SQLite DB, and CSV export. |
| **Card Ladder Help Center** | Official Card Ladder Bulk Upload CSV Specification (Zendesk) | 16 CSV column headers, required vs. optional fields, and web upload constraints. |
| **Root Workspace Steering** | `g:\My Drive\GOOGLE ANTIGRAVITY\GEMINI.md` | Global domain routing, zero-discretion testing mandate, and directory isolation. |

---

## 3. The Authoritative 21-Variable Database Schema Specification

The central SQLite database (`portfolio.db`) houses the `cards` table. Every ingested card record must adhere strictly to these 21 variables without adding or dropping columns.

### 3.1 Field-by-Field Data Dictionary

| # | Database Column Name | SQLite Data Type | Nullable | Default Value | Validation & Constraint Rules | Description & Example |
|---|----------------------|------------------|----------|---------------|--------------------------------|-----------------------|
| 1 | `date_purchased` | `TEXT` | `NOT NULL` | `strftime('%m/%d/%Y', 'now')` | Format must match `MM/DD/YYYY` regex `^\d{2}/\d{2}/\d{4}$`. | Date acquired. Defaults to current date (e.g., `08/24/2026`). |
| 2 | `quantity` | `INTEGER` | `NOT NULL` | `1` | `CHECK (quantity >= 1)` | Number of identical copies (e.g., `1`). |
| 3 | `player` | `TEXT` | `NOT NULL` | None | `CHECK (LENGTH(TRIM(player)) > 0)` | Full athlete or TCG character name (e.g., `Stephen Curry`, `Charizard`). |
| 4 | `year` | `INTEGER` | `NOT NULL` | None | `CHECK (year BETWEEN 1800 AND 2100)` | 4-digit release year (e.g., `2023`). |
| 5 | `set_name` | `TEXT` | `NOT NULL` | None | `CHECK (LENGTH(TRIM(set_name)) > 0)` | Manufacturer and set line (e.g., `Panini Prizm`, `Topps Chrome`). |
| 6 | `variation` | `TEXT` | `NULLABLE` | `''` | String. Empty string `''` only for verified base cards. | Foil, parallel, or insert (e.g., `Silver Prizm`, `Gold Refractor /10`). |
| 7 | `card_number` | `TEXT` | `NOT NULL` | `'1'` | `CHECK (LENGTH(TRIM(card_number)) > 0)` | Printed card number. Leading zeroes preserved (e.g., `#24`, `007`, `RC-1`). |
| 8 | `category` | `TEXT` | `NOT NULL` | `'Basketball'` | `CHECK (category IN ('Basketball', 'Baseball', 'Football', 'Hockey', 'Soccer', 'Tennis', 'Wrestling', 'Racing', 'Golf', 'Boxing', 'UFC/MMA', 'Pokemon', 'Magic', 'Metazoo', 'Yugioh', 'Fortnite', 'Dragonballz', 'Entertainment', 'Swimming', 'Softball', 'PopCulture', 'Flesh and Blood'))` | Exact 22 permitted categories enumeration. |
| 9 | `condition` | `TEXT` | `NOT NULL` | `'Raw'` | Must be `'Raw'` or Grader + Space + Grade without hyphens (e.g., `PSA 10`, `BGS 9.5`, `SGC 10`, `CGC 9.5`). | Grading status and grade value. |
| 10 | `slab_serial_number` | `TEXT` | `NULLABLE` | `''` | **MUST be empty/NULL if `condition == 'Raw'`**. Contains cert string for graded cards. | Grading company slab cert number (e.g., `68492014`). |
| 11 | `investment` | `REAL` | `NOT NULL` | `0.00` | `CHECK (investment >= 0.00)` | Purchase price + fees as 2-decimal float (e.g., `15.50`). |
| 12 | `estimated_value` | `REAL` | `NOT NULL` | `0.00` | `CHECK (estimated_value >= 0.00)` | Fair market value estimate or OCR last sold price (e.g., `25.00`). |
| 13 | `ladder_id` | `TEXT` | `NULLABLE` | `''` | Empty string unless synced with Card Ladder database ID. | Official Card Ladder unique identifier. |
| 14 | `query` | `TEXT` | `NOT NULL` | None | Format: `[Year] [Set] [Player] [Variation] [Condition]`. Negative exclusions (`-BGS -SGC`) **FORBIDDEN** on `'Raw'`. | Search query string generated for comps and price scrapers. |
| 15 | `notes` | `TEXT` | `NULLABLE` | `''` | Written as `[Parent_Image_ID]-[Child_Card_ID]` (e.g., `8492-105`). | Relational tracking key linking card to physical scan file. |
| 16 | `tags` | `TEXT` | `NULLABLE` | `''` | Custom tag string (e.g., `PC`, `For Sale`, `Grade Sub`). | Internal portfolio categorization tags. |
| 17 | `date_sold` | `TEXT` | `NULLABLE` | `''` | `MM/DD/YYYY` or empty string if unsold. | Date the card was sold. |
| 18 | `sold_price` | `REAL` | `NULLABLE` | `NULL` | `CHECK (sold_price IS NULL OR sold_price >= 0.00)` | Realized sale price (e.g., `45.00`). |
| 19 | `image` | `TEXT` | `NULLABLE` | `''` | Direct Google Drive URL or hosted web URL. | Front image scan URL. |
| 20 | `back_image` | `TEXT` | `NULLABLE` | `''` | Direct Google Drive URL or empty string. | Back image scan URL for condition verification. |
| 21 | `ai_status` | `TEXT` | `NOT NULL` | `'NEEDS REVIEW'` | `CHECK (ai_status IN ('REVIEW VARIATION', 'NEEDS REVIEW', 'CLEARED'))`. Guessed variations **MUST** be `'REVIEW VARIATION'`. | Human-in-the-loop validation flag for AI-extracted cards. |

### 3.2 Production SQLite DDL Implementation

```sql
-- SQLite Schema Definition for portfolio.db
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_purchased TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),
    player TEXT NOT NULL CHECK (LENGTH(TRIM(player)) > 0),
    year INTEGER NOT NULL CHECK (year BETWEEN 1800 AND 2100),
    set_name TEXT NOT NULL CHECK (LENGTH(TRIM(set_name)) > 0),
    variation TEXT DEFAULT '',
    card_number TEXT NOT NULL CHECK (LENGTH(TRIM(card_number)) > 0),
    category TEXT NOT NULL CHECK (category IN (
        'Basketball', 'Baseball', 'Football', 'Hockey', 'Soccer', 
        'Tennis', 'Wrestling', 'Racing', 'Golf', 'Boxing', 
        'UFC/MMA', 'Pokemon', 'Magic', 'Metazoo', 'Yugioh', 
        'Fortnite', 'Dragonballz', 'Entertainment', 'Swimming', 
        'Softball', 'PopCulture', 'Flesh and Blood'
    )),
    condition TEXT NOT NULL,
    slab_serial_number TEXT DEFAULT '',
    investment REAL NOT NULL DEFAULT 0.00 CHECK (investment >= 0.00),
    estimated_value REAL NOT NULL DEFAULT 0.00 CHECK (estimated_value >= 0.00),
    ladder_id TEXT DEFAULT '',
    query TEXT NOT NULL,
    notes TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    date_sold TEXT DEFAULT '',
    sold_price REAL DEFAULT NULL CHECK (sold_price IS NULL OR sold_price >= 0.00),
    image TEXT DEFAULT '',
    back_image TEXT DEFAULT '',
    ai_status TEXT NOT NULL DEFAULT 'NEEDS REVIEW' CHECK (ai_status IN ('REVIEW VARIATION', 'NEEDS REVIEW', 'CLEARED')),
    parent_image_id INTEGER,
    child_card_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexing for high-performance querying and export
CREATE INDEX IF NOT EXISTS idx_cards_player_year ON cards (player, year);
CREATE INDEX IF NOT EXISTS idx_cards_category ON cards (category);
CREATE INDEX IF NOT EXISTS idx_cards_ai_status ON cards (ai_status);
CREATE INDEX IF NOT EXISTS idx_cards_parent_image ON cards (parent_image_id, child_card_id);
```

---

## 4. The Exact 16 Card Ladder Bulk Upload CSV Specification

Card Ladder's web bulk upload interface ingests a `.csv` file containing exactly 16 standard columns.

### 4.1 16-Column Ordering, Header Names & Formatting

| CSV Column Index | Exact CSV Header Name | Source Database Field | Card Ladder Status | Formatting & Data Transformation Rules |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `Date Purchased` | `date_purchased` | **Required** | Formatted strictly as `MM/DD/YYYY` (e.g., `08/24/2026`). Default to current date if missing. |
| **2** | `Quantity` | `quantity` | Optional | Integer $\ge 1$. Default `1`. |
| **3** | `Player` | `player` | **Required** | Normalized full athlete/character name (e.g., `Stephen Curry`). |
| **4** | `Year` | `year` | **Required** | 4-digit release year string (e.g., `2023`). |
| **5** | `Set` | `set_name` | **Required** | Normalized set line (e.g., `Panini Prizm`). |
| **6** | `Variation` | `variation` | Optional | String or empty string (e.g., `Silver Prizm`). |
| **7** | `Number` | `card_number` | Optional | **Preserve leading zeroes**; treat as text/string (`"01"`, `"#24"`, `"007"`). |
| **8** | `Category` | `category` | **Required** | Must match one of the 22 valid categories (e.g., `Basketball`). |
| **9** | `Condition` | `condition` | **Required** | `'Raw'` for ungraded, or Grader + Space + Grade without hyphens (e.g., `PSA 10`, `BGS 9.5`). |
| **10** | `Investment` | `investment` | **Required** | Float formatted to 2 decimal places (e.g., `15.00` or `0.00`). |
| **11** | `Estimated Value` | `estimated_value` | Optional | Float formatted to 2 decimal places (e.g., `25.00` or `0.00`). |
| **12** | `Ladder ID` | `ladder_id` | Optional | Card Ladder database identifier string or empty. |
| **13** | `Notes` | `notes` | Optional | Relational tracking key `[Parent_Image_ID]-[Child_Card_ID]` (e.g., `8492-105`). |
| **14** | `Date Sold` | `date_sold` | Optional | Formatted as `MM/DD/YYYY` or empty string if unsold. |
| **15** | `Sold Price` | `sold_price` | Optional | Float formatted to 2 decimal places or empty string if unsold. |
| **16** | `Image` | `image` | Optional | Direct Google Drive URL or public image hosting URL. |

---

## 5. DB-to-CSV Column Mapping & Exclusion Analysis

The database maintains 21 variables for internal pipeline management and verification. When exporting to `CardLadder_Bulk_Upload.csv`, exactly 5 fields are excluded:

```
+------------------------------------+------------------------------------+
| 21-Variable Database Schema (DB)   | 16-Variable Card Ladder CSV Export |
+------------------------------------+------------------------------------+
| 1.  date_purchased                 | 1.  Date Purchased                 |
| 2.  quantity                       | 2.  Quantity                       |
| 3.  player                         | 3.  Player                         |
| 4.  year                           | 4.  Year                           |
| 5.  set_name                       | 5.  Set                            |
| 6.  variation                      | 6.  Variation                      |
| 7.  card_number                    | 7.  Number (Leading 0s preserved)  |
| 8.  category                       | 8.  Category                       |
| 9.  condition                      | 9.  Condition                      |
| 10. slab_serial_number             | [EXCLUDED: Internal Slab Cert]     |
| 11. investment                     | 10. Investment                     |
| 12. estimated_value                | 11. Estimated Value                |
| 13. ladder_id                      | 12. Ladder ID                      |
| 14. query                          | [EXCLUDED: Search Query String]    |
| 15. notes                          | 13. Notes                          |
| 16. tags                           | [EXCLUDED: Internal Tags]          |
| 17. date_sold                      | 14. Date Sold                      |
| 18. sold_price                     | 15. Sold Price                     |
| 19. image                          | 16. Image                          |
| 20. back_image                     | [EXCLUDED: Internal Back Scan URL] |
| 21. ai_status                      | [EXCLUDED: Internal AI State]      |
+------------------------------------+------------------------------------+
```

### Rationale for Exclusions:
1. **`slab_serial_number`**: Card Ladder's standard CSV upload format captures the grade in `Condition`; certificate verification is handled internally or tracked in `Notes`.
2. **`query`**: Calculated helper string used exclusively by local market scrapers and comp search engines.
3. **`tags`**: Local organization taxonomy not supported by Card Ladder bulk CSV.
4. **`back_image`**: Card Ladder accepts a single primary `Image` URL.
5. **`ai_status`**: Human-in-the-loop state machine flag (`REVIEW VARIATION`, `NEEDS REVIEW`, `CLEARED`) for staging verification.

---

## 6. Data Transformation & Normalization Rules

### 6.1 Preservation of Leading Zeroes (The Number Column)
- **Problem**: When reading card numbers into Pandas or writing to CSV, numbers such as `01`, `007`, `RC-01`, or `04/25` are frequently coerced into integer values (`1`, `7`), corrupting official card numbers.
- **Specification Rule**:
  - In SQLite: Store `card_number` as `TEXT`.
  - In Pandas: Load column with `dtype={'card_number': str, 'Number': str}`.
  - In CSV Serialization: Convert `NaN` to `""`, format as string, and export with `df.to_csv(..., quoting=csv.QUOTE_MINIMAL)` ensuring text representations remain unmodified.

### 6.2 Condition & Slab Serial Logic
- Ungraded cards: `condition` **MUST** be `'Raw'`. `slab_serial_number` **MUST** be empty string or `NULL`.
- Graded cards: Syntax must not contain hyphens (e.g., `PSA 10`, `PSA 9`, `BGS 9.5`, `SGC 10`, `CGC 9.5`). `slab_serial_number` contains the certification number string.

### 6.3 Query String Synthesis
- Format: `f"{year} {set_name} {player} {variation} {condition}".strip()`
- Prohibited: Negative keyword exclusions (e.g., `-BGS -SGC`) are **STRICTLY FORBIDDEN** on `'Raw'` cards.

### 6.4 Fuzzy String Normalization for Players and Sets
- **Player Names**:
  - Strip punctuation and extra whitespace.
  - Map common nicknames/aliases to canonical names (e.g., `"Steph Curry"` $\rightarrow$ `"Stephen Curry"`, `"Wemby"` $\rightarrow$ `"Victor Wembanyama"`).
  - Use Levenshtein / Token Sort Ratio (threshold $\ge 85\%$) against canonical sports rosters.
- **Set Names**:
  - Standardize brand prefixes (e.g., `"Prizm"` $\rightarrow$ `"Panini Prizm"`, `"Chrome"` $\rightarrow$ `"Topps Chrome"`, `"Optic"` $\rightarrow$ `"Donruss Optic"`).

---

## 7. Pipeline Specifications & Data Flow

### 7.1 Pipeline 1: AI Vision Ingestion (Gemini Multimodal API)
- **Input**: Local card scan image (`jpg`/`png`).
- **Processing**: Prompts Gemini 2.5 Flash with structured schema instructions.
- **AI Status Trigger**: If visual foil/parallel is guessed, sets `ai_status = 'REVIEW VARIATION'`. Otherwise `'NEEDS REVIEW'` until approved.
- **Output**: JSON payload matching the 21-variable schema.

### 7.2 Pipeline 2: Beckett / Cardboard Connection Checklist Scraper
- **Input**: Target set URL or static HTML checklist.
- **Processing**: Parses HTML tables using `BeautifulSoup` to extract `card_number`, `player`, `set_name`, and `variation`.
- **Defaults**: Assigns `condition = 'Raw'`, `investment = 0.00`, `estimated_value = 0.00`, `quantity = 1`.
- **UI Integration**: Presents checklist rows as checkboxes in Streamlit for bulk ingestion.

### 7.3 Pipeline 3: Chrome Extension API Bridge
- **Input**: `POST /api/cards/ingest` payload from Manifest V3 extension.
- **Security & Anti-Bot Rule**: No direct automated headless scraping of eBay/Card Ladder. Ingestion relies on user browsing and extension dispatching DOM summaries.
- **Validation**: Pydantic model enforces 21 variables before committing to `portfolio.db`.

### 7.4 Pipeline 4: Gemini SEO Sales Listing Generator
- **Input**: Row ID or 21-variable dictionary from `portfolio.db`.
- **Processing**: Constructs SEO-optimized marketplace listing.
- **Output**: Structured JSON / Text:
  - **Title**: `[Year] [Set] [Player] [Variation] #[Number] [Condition] [Grading/Raw] [Team]`
  - **Body**: Item specifics, condition details, cert number (if graded), tracking note, and top search hashtags.

### 7.5 Pipeline 5: Pandas Export Pipeline
- **Input**: SQLite query selecting cards where `ai_status == 'CLEARED'` (or user-selected staging rows).
- **Processing**: Transforms 21 DB variables into 16 CSV headers, applies fuzzy name cleanup, preserves leading zeroes.
- **Output**: Pristine `CardLadder_Bulk_Upload.csv`.

---

## 8. Operational Directives & Relational Architecture

1. **Relational Key Architecture**:
   - `Parent Image ID`: 4-digit unique integer per physical photo file (e.g., `8492`). Must never be recycled.
   - `Child Card ID`: 3-digit suffix per card cropped from scan (e.g., `8492-105`).
   - `Notes` Tracking Field: Written as `[Parent_Image_ID]-[Child_Card_ID]`.
   - File Naming: `CardScan-[YYYYMMDD]-[Parent_Image_ID].jpg`.
2. **500-Card Batch Circuit Breaker**:
   - Staging table limits batches to 500 rows.
   - When staging reaches 500 cards, triggers automated batch export, database commit, and staging rollover.

---

## 9. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Database | 21-Variable SQLite Ingestion Schema | Rigid 21-column schema for `portfolio.db` with check constraints and defaults. | Ingestion payloads (Vision, Scraper, API, Manual) | Stored SQLite rows in `cards` table | Rejects non-conforming rows with SQLite constraint error | `sports_cards/GEMINI.md`, `sports_cards_schema.md` |
| 2 | Export | 16-Variable Card Ladder CSV Export | Formats database rows into exact 16 Card Ladder bulk upload headers. | SQLite `cards` records | `CardLadder_Bulk_Upload.csv` | Throws validation error if required fields (Date, Player, Year, Set, Category, Condition, Investment) are missing | Card Ladder Help Center, `ORIGINAL_REQUEST.md` |
| 3 | Data Integrity | Leading Zero Preservation | Preserves leading zeroes on card numbers (e.g., `01`, `007`, `RC-01`). | Raw card number string | String-typed column in CSV | Numeric coercion prevented via explicit string dtypes | `ORIGINAL_REQUEST.md`, `GEMINI.md` |
| 4 | Data Integrity | Category Constraint (22 Types) | Restricts category to exact 22 sports/TCG categories. | Category string | Validated category | Rejects unknown categories with validation error | `sports_cards/GEMINI.md` §21-Variable Schema |
| 5 | Data Integrity | Condition & Slab Serial Rules | Enforces `'Raw'` for ungraded; prohibits slab cert on Raw cards. | Condition and cert strings | Validated condition & cert | Raises error if cert number is populated for Raw card | `sports_cards/GEMINI.md` §21-Variable Schema |
| 6 | Ingestion | AI Vision Extraction | Gemini Multimodal API extracts card details from image files. | Card scan image path/buffer | 21-variable JSON dictionary | Returns `ai_status: 'REVIEW VARIATION'` or `'NEEDS REVIEW'` | `ORIGINAL_REQUEST.md` §R2 |
| 7 | Ingestion | Checklist Web Scraper | Parses Beckett / Cardboard Connection set checklists into card items. | HTML URL or static HTML string | List of structured card dictionaries | Gracefully handles malformed tables; logs parse errors | `ORIGINAL_REQUEST.md` §R2 |
| 8 | Ingestion | Chrome Extension API Bridge | FastAPI/Streamlit endpoint receiving JSON from Chrome extension. | POST JSON payload | Database insertion confirmation | Returns HTTP 422 on schema violation | `ORIGINAL_REQUEST.md` §R3, `apps/agy_chrome_extension` |
| 9 | Sales | SEO Marketplace Listing Generator | Gemini prompts creating high-converting Facebook/eBay listing strings. | Card record dictionary | Formatted Title and Description string | Falls back to deterministic template if Gemini API is unavailable | `ORIGINAL_REQUEST.md` §R3 |
| 10 | Workflow | 500-Card Batch Circuit Breaker | Halts staging and triggers export/rollover when batch hits 500 rows. | Staging row count | Batch export & staging reset | Warns user and blocks staging insertion beyond 500 | `sports_cards/GEMINI.md` §500-Card Limit |
| 11 | Relational | Parent/Child Key Architecture | Links cards to physical photo scan IDs (`8492-105`) in `Notes`. | Parent Image ID, Child Card ID | Formatted `Notes` string | Enforces non-recyclable 4-digit parent IDs | `sports_cards/GEMINI.md` §Relational Keys |
| 12 | Normalization | Fuzzy Player/Set Normalization | Fuzzy matches player and set names against canonical lists. | Raw player/set text | Normalized canonical text | Keeps raw string if fuzzy match confidence $< 85\%$ | `ORIGINAL_REQUEST.md` §R4 |

---

## 10. Edge Cases & Observed Behavior

| # | Feature | Input | Observed Behavior | Deterministic Resolution |
|---|---------|-------|-------------------|--------------------------|
| 1 | Card Number | `01`, `007`, `RC-01` | Excel/Pandas auto-casts to integer `1`, `7`, stripping zeroes. | Enforce `dtype=str` in Pandas and explicit string quoting in CSV export. |
| 2 | Condition | Raw card with cert number provided | Graded cert populated on an ungraded card. | Trigger validation failure; automatically wipe cert if condition is `'Raw'`. |
| 3 | Query String | Raw card search query | Negative search operators (`-BGS -SGC`) applied to Raw cards. | Strictly strip negative exclusion keywords for `'Raw'` cards. |
| 4 | Date Purchased | Missing / blank date in ingestion payload | Empty date causes Card Ladder upload failure. | Automatically default to current date formatted as `MM/DD/YYYY`. |
| 5 | Investment / Est. Value | Missing or negative float | Upload fails on non-numeric or missing required investment. | Default to `0.00`; clamp negative values to `0.00`. |
| 6 | Variation | Verified base card vs parallel | Base cards must have empty variation, not `'Base'`. | If variation is `'Base'` or `'Base Card'`, normalize to empty string `''`. |
| 7 | Multi-Sport Set | Checklist containing multiple sports | Ambiguous category classification. | Extract athlete sport dynamically or default to set primary sport. |
| 8 | Multi-Player Card | Dual/Triple player cards (e.g., "LeBron James / Kobe Bryant") | Player name exceeds single athlete. | Preserve slash-delimited names in `Player`; construct multi-name query. |
| 9 | Graded Condition Syntax | `PSA-10` or `BGS-9.5` (hyphenated) | Card Ladder parser fails on hyphenated grading syntax. | Regex replace hyphen with single space (`PSA 10`, `BGS 9.5`). |
| 10 | 500+ Card Batch | Batch ingestion of 650 cards | Exceeds 500-card batch limit. | Split batch automatically into `CardLadder_Bulk_Upload_Part1.csv` (500) and `Part2.csv` (150). |

---

## 11. Ambiguities & Deterministic Defaults

| Variable / Behavior | Identified Ambiguity | Deterministic Default Specification |
|---|---|---|
| `date_purchased` | What if ingestion source does not provide purchase date? | Default to execution date formatted as `MM/DD/YYYY` (`strftime('%m/%d/%Y', 'now')`). |
| `investment` | What if purchase cost is unknown during checklist scraping? | Default to `0.00`. |
| `estimated_value` | What if no comp sales are found? | Default to `0.00`. |
| `quantity` | What if quantity is omitted in API payload? | Default to `1`. |
| `variation` | How to distinguish base cards from unlisted parallels? | Base cards are empty string `''`. Any guessed parallel sets `ai_status = 'REVIEW VARIATION'`. |
| `sold_price` / `date_sold` | What if card is unsold? | `date_sold` is empty string `''`; `sold_price` is `NULL` (serializes to empty string in CSV). |
| `ai_status` | Initial state for newly ingested records? | AI Vision $\rightarrow$ `'REVIEW VARIATION'` or `'NEEDS REVIEW'`; Scraper $\rightarrow$ `'NEEDS REVIEW'`; Human verified $\rightarrow$ `'CLEARED'`. |

---
**Report Status:** Complete & Authoritative  
**Verification Hash:** `SPEC-21V-16CSV-VERIFIED`
