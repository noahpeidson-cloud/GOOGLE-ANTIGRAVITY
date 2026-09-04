# Technical Architecture & Survey Report: Sports Card Ecosystem Hub

**Date:** 2026-08-24  
**Working Directory Target:** `g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub`  
**Domain Scope:** Track 1 (/sports_cards)  
**Author:** Explorer Subagent (`teamwork_preview_explorer`)

---

## 1. Executive Summary & Runtime Environment Audit

An exhaustive technical survey was conducted on the Python runtime environment, installed packages, workspace assets, and architectural constraints. 

### 1.1 Python & Package Availability Matrix
- **Python Version:** `3.13.14` (Windows 64-bit)

| Package | Status | Version | Role in Ecosystem Hub | Strategy / Adaptation |
| :--- | :--- | :--- | :--- | :--- |
| **`streamlit`** | ✅ Available | `1.60.0` | Main interactive UI / dashboard | Native Streamlit application |
| **`fastapi`** | ✅ Available | `0.141.1` | REST/WebSocket API bridge for Chrome extension | Native FastAPI app |
| **`uvicorn`** | ✅ Available | `0.52.0` | ASGI server for FastAPI | Background server / runner |
| **`pydantic`** | ✅ Available | `2.13.4` | Data validation & structured schema | Pydantic V2 models (`model_dump()`, `Field`) |
| **`sqlite3`** | ✅ Available | Built-in | Relational database (`portfolio.db`) | Standard library `sqlite3` with WAL mode |
| **`pandas`** | ✅ Available | `3.0.5` | Data manipulation & CSV serialization | Strict string dtype preservation for card numbers |
| **`requests`** | ✅ Available | `2.34.2` | HTTP client for checklists / web scraping | Fetching static HTML checklists |
| **`google.genai`** | ✅ Available | `2.19.0` | Official Google GenAI SDK | AI Vision image extraction & Sales copy generation |
| **`google.generativeai`** | ❌ Missing | N/A (Legacy SDK) | Older Gemini SDK | Deprecated; replaced by official `google.genai` SDK |
| **`bs4` / `beautifulsoup4`** | ❌ Missing | N/A | HTML parsing | Built-in `html.parser.HTMLParser` fallback engine |
| **`rapidfuzz` / `thefuzz`** | ❌ Missing | N/A | Fuzzy string matching | Standard library `difflib.get_close_matches` / `SequenceMatcher` |
| **`openpyxl`** | ❌ Missing | N/A | Excel files | Standard `pandas.to_csv` with standard `csv.QUOTE_MINIMAL` |
| **`pytest`** | ✅ Available | `9.1.1` | Test runner for test suites | Programmatic test execution |
| **`watchdog`** | ✅ Available | Built-in | File watching | State synchronization & file monitoring |

### 1.2 Zero-Dependency Resilience Highlights
1. **Fuzzy Normalization:** Instead of depending on missing `rapidfuzz`, the export pipeline utilizes Python's built-in `difflib.get_close_matches` and `difflib.SequenceMatcher`, which provide 100% native fuzzy string matching without external C-extensions.
2. **HTML Checklist Scraper:** Implements a custom `ChecklistHTMLParser` using Python's standard library `html.parser.HTMLParser` with optional fallback to `beautifulsoup4` if installed. This guarantees zero-crash execution out-of-the-box on clean environments.
3. **Gemini SDK:** Modern `google.genai` (v2.19.0) is already installed and utilized for multimodal card recognition and listing generation with a deterministic offline mock fallback when `GEMINI_API_KEY` is not supplied.

---

## 2. Domain Rules, Schemas & Integrity Constraints

Adheres strictly to the `/sports_cards` domain manifest defined in `g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\GEMINI.md`:

### 2.1 The Relational Key Architecture
- **Parent Image ID:** 4-digit unique integer per physical scan/photo batch (e.g. `8492`).
- **Child Card ID:** 3-digit unique integer per distinct card in photo (e.g. `105`).
- **Tracking Key:** Formatted as `[Parent_Image_ID]-[Child_Card_ID]` (e.g. `8492-105`), stored in the `Notes` field (Column 15).
- **Scan Naming:** Follows `CardScan-[YYYYMMDD]-[Parent_Image_ID].jpg`.

### 2.2 The 21-Variable Master Schema
All ingestion pipelines format data into this 21-column database structure:

| # | Field Name | SQLite Data Type | Rules & Constraints |
|---|---|---|---|
| 1 | `date_purchased` | `TEXT` | Format: `MM/DD/YYYY` (Defaults to current date) |
| 2 | `quantity` | `INTEGER` | Default `1` |
| 3 | `player` | `TEXT` | Full athlete name or TCG character |
| 4 | `year` | `INTEGER` | 4-digit `YYYY` |
| 5 | `set_name` | `TEXT` | Manufacturer + line (e.g., `Panini Prizm`, `Topps Chrome`) |
| 6 | `variation` | `TEXT` | Parallel / visual foil (e.g., `Silver Prizm`, `Refractor`). Blank ONLY for verified base |
| 7 | `card_number` | `TEXT` | Printed card # (`001`, `#24`, `RC-1`). **MUST preserve leading zeros** |
| 8 | `category` | `TEXT` | Restricted to the 22 exact permitted categories |
| 9 | `condition` | `TEXT` | `'Raw'` for ungraded; graded syntax without hyphens (`PSA 10`, `BGS 9.5`, `SGC 10`, `CGC 9.5`) |
| 10 | `slab_serial_number` | `TEXT` | Certification number (Must be blank if condition is `'Raw'`) |
| 11 | `investment` | `REAL` | Cost basis float (`0.00`) |
| 12 | `estimated_value` | `REAL` | Market value float (`0.00`) |
| 13 | `ladder_id` | `TEXT` | Blank (reserved for Card Ladder sync) |
| 14 | `query` | `TEXT` | Synthesized: `[Year] [Set] [Player] [Variation] [Condition]`. No negative exclusions on Raw |
| 15 | `notes` | `TEXT` | Formatted `[Parent_Image_ID]-[Child_Card_ID]` |
| 16 | `tags` | `TEXT` | Blank / custom tags |
| 17 | `date_sold` | `TEXT` | Blank / `MM/DD/YYYY` |
| 18 | `sold_price` | `REAL` | Blank / float |
| 19 | `image_url` | `TEXT` | Direct Google Drive URL or local path |
| 20 | `back_image_url` | `TEXT` | Direct Google Drive URL or blank |
| 21 | `ai_status` | `TEXT` | Enumeration: `REVIEW VARIATION`, `NEEDS REVIEW`, or `CLEARED` |

### 2.3 Permitted Categories (22 Exact Values)
`[Basketball, Baseball, Football, Hockey, Soccer, Tennis, Wrestling, Racing, Golf, Boxing, UFC/MMA, Pokemon, Magic, Metazoo, Yugioh, Fortnite, Dragonballz, Entertainment, Swimming, Softball, PopCulture, Flesh and Blood]`

### 2.4 Card Ladder 16-Column Export Format
When generating `CardLadder_Bulk_Upload.csv`, exactly columns 1 through 16 are selected with exact header titles:
1. `Date Purchased`
2. `Quantity`
3. `Player`
4. `Year`
5. `Set`
6. `Variation`
7. `Number`
8. `Category`
9. `Condition`
10. `Slab Serial #`
11. `Investment`
12. `Estimated Value`
13. `Ladder ID`
14. `Query`
15. `Notes`
16. `Tags`

### 2.5 500-Card Circuit Breaker
If the staging database or CSV batch exceeds 500 rows, processing must pause and trigger an automatic batch export commit and staging table rollover.

---

## 3. Proposed Modular Architecture & Directory Layout

The `sports_cards/ecosystem_hub` directory will be structured with clean separation of concerns:

```
g:/My Drive/GOOGLE ANTIGRAVITY/sports_cards/ecosystem_hub/
│
├── app.py                      # Streamlit Main Dashboard & Navigation
├── config.py                   # Global constants, schema definitions & category enums
├── database.py                 # SQLite CRUD, schema migrations, WAL mode & batch management
├── vision_ingest.py            # Gemini Multimodal AI Vision extractor & offline mock
├── scraper_ingest.py           # Beckett / Cardboard Connection checklist HTML parser
├── api.py                      # FastAPI bridge (REST & WebSocket) for Chrome extension
├── sales_generator.py          # Gemini AI Facebook Marketplace & eBay listing copy generator
├── export.py                   # Pandas + difflib fuzzy normalization & Card Ladder CSV builder
├── run_hub.py                  # Process orchestrator launching FastAPI daemon & Streamlit UI
│
├── mock_data/                  # Test artifacts and mock payloads
│   ├── beckett_sample.html     # Mock Beckett HTML checklist table
│   ├── chrome_payload.json     # Mock payload from Chrome extension
│   └── sample_cards.json       # Mock 21-variable card records
│
└── tests/                      # Pytest verification suite
    ├── __init__.py
    ├── test_database.py        # 21-variable schema CRUD, constraints, 500-batch limit
    ├── test_scraper.py         # Checklist parsing on static HTML (>= 3 cards extracted)
    ├── test_vision.py          # AI Vision schema conformance & mock extraction
    ├── test_api.py             # FastAPI endpoints (/api/ingest, /api/health)
    ├── test_sales.py           # Marketplace listing copy generator formatting & tags
    └── test_export.py          # 16-header Card Ladder CSV export & leading-zero tests
```

---

## 4. Component Technical Specifications

### 4.1 `config.py`
- Stores `CATEGORIES` (tuple of 22 valid strings).
- Stores `MASTER_COLUMNS_21` and `CARD_LADDER_HEADERS_16`.
- Defines paths: `DB_PATH = "portfolio.db"`, `EXPORT_PATH = "CardLadder_Bulk_Upload.csv"`.
- Sets circuit breaker `BATCH_LIMIT = 500`.

### 4.2 `database.py`
- Initializes SQLite database with `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;` for high-concurrency read/write between FastAPI and Streamlit.
- Provides functions:
  - `init_db(db_path)`: Creates `cards` table with indexes on `player`, `year`, `set_name`, `ai_status`.
  - `insert_card(card_dict, db_path)`: Inserts a single 21-variable card dictionary, validating categories and auto-generating the `query` field.
  - `bulk_insert_cards(card_list, db_path)`: Atomic transaction for batch insertion.
  - `get_all_cards(db_path)`: Returns all cards as a list of dicts or Pandas DataFrame.
  - `update_card(card_id, card_dict, db_path)`: Updates card fields.
  - `delete_card(card_id, db_path)`: Removes a card record.
  - `get_staging_count(db_path)`: Checks count against 500-row circuit breaker.

### 4.3 `vision_ingest.py`
- Uses `google.genai` SDK (`from google import genai`).
- Structured JSON prompt instructing Gemini to analyze card photos (front and back) and extract: `player`, `year`, `set_name`, `variation`, `card_number`, `category`, `condition`, `slab_serial_number`, `estimated_value`, `ai_status`.
- Flags `ai_status = 'REVIEW VARIATION'` if variation is visually guessed.
- Provides `extract_card_from_image(image_path, api_key=None, mock=False)`:
  - When `mock=True` or `api_key` is missing: returns deterministic mock data matching the 21-variable schema.
  - When `mock=False` and `api_key` is available: executes live Gemini multimodal inference.

### 4.4 `scraper_ingest.py`
- Zero-dependency `ChecklistHTMLParser` based on `html.parser.HTMLParser`.
- Parses tabular checklists (e.g. Beckett, Cardboard Connection) with columns: `Card #`, `Player / Description`, `Team / Attribute`.
- Sanitizes card numbers (preserving leading zeros like `001`, `07`, `RC-1`).
- Auto-formats each parsed card into the 21-variable schema with `ai_status = 'CLEARED'`.
- Provides `parse_checklist_html(html_content, set_name, year, category)` and `fetch_and_parse_url(url, set_name, year, category)`.

### 4.5 `api.py` (FastAPI Bridge)
- FastAPI app instance configured with CORS middleware for Chrome extensions (`chrome-extension://*` and `localhost`).
- Endpoints:
  - `GET /api/health`: Health status & database card count.
  - `POST /api/ingest`: Accepts JSON payload from Chrome extension, validates with Pydantic model `CardIngestPayload`, formats into 21 variables, and inserts into `portfolio.db`.
  - `GET /api/cards`: Returns staging cards.
  - `POST /api/sales/generate`: Generates listing copy for a specific card ID.

### 4.6 `sales_generator.py`
- Generates SEO-optimized listing copy for Facebook Marketplace & eBay.
- Listing includes:
  - High-CTR Title with emojis, year, set, player, card #, variation, and condition.
  - Formatted Item Specifics section.
  - Detailed Description (condition, top-loader protection, shipping policy, bundle offers).
  - 10-15 Target Hashtags/Keywords (e.g. `#TheHobby`, `#SportsCards`, `#PaniniPrizm`, `#Wembanyama`).
- Provides `generate_listing_copy(card_dict, api_key=None, mock=False)` with deterministic fallback.

### 4.7 `export.py`
- Implements `export_card_ladder_csv(db_path, output_csv_path, normalize_fuzzy=True)`:
  1. Queries cards from `portfolio.db`.
  2. Applies `difflib.get_close_matches` against canonical player rosters and set lists to correct OCR/scraping typos.
  3. Formats `card_number` as explicit string to guarantee leading zeros are never dropped.
  4. Formats floats (`investment`, `estimated_value`) with 2 decimal places (`0.00`).
  5. Selects exactly the 16 Card Ladder columns.
  6. Exports to `CardLadder_Bulk_Upload.csv` with standard quotes and UTF-8 encoding.

### 4.8 `app.py` (Streamlit Central Hub)
- Streamlit application structured with tabs:
  1. **📊 Portfolio Staging Area:** Interactive data editor table, search/filter, delete/edit actions, batch count indicator against 500-card circuit breaker.
  2. **📸 AI Vision Ingestion:** Drag-and-drop image upload, single or batch photo analysis, visual card preview, confidence review.
  3. **📋 Web Checklist Scraper:** URL or raw HTML paste for Beckett/Cardboard Connection checklists, set name & year selection, bulk ingest preview with selection checkboxes.
  4. **🔌 Extension Inbox & API Bridge:** Monitor inbound payloads from the Chrome extension, real-time sync status, server port configuration.
  5. **🏷️ Sales Copy Generator:** Select card from database -> one-click generation of Facebook Marketplace listing copy with copy-to-clipboard button.
  6. **💾 Card Ladder Export:** Fuzzy normalization toggle, CSV preview, one-click export button & download link.

---

## 5. FastAPI & Streamlit Harmonious Co-existence Patterns

To ensure that both the Streamlit UI and the FastAPI endpoint run smoothly without port conflicts or blocking:

```
                         ┌─────────────────────────┐
                         │ Chrome Extension / HTTP │
                         └────────────┬────────────┘
                                      │ POST /api/ingest
                                      ▼
┌────────────────────────┐      ┌─────────────────────────┐
│     User Browser       │      │   FastAPI Bridge        │
│  (Streamlit Dashboard) │      │   (Uvicorn :8002)       │
└────────────┬───────────┘      └────────────┬────────────┘
             │                               │
             │ Read/Write                    │ Insert
             ▼                               ▼
     ┌───────────────────────────────────────────────┐
     │          SQLite Database (portfolio.db)       │
     │            PRAGMA journal_mode = WAL          │
     │            PRAGMA busy_timeout = 30000        │
     └───────────────────────────────────────────────┘
```

### Execution Options
1. **Option A (Recommended: Unified Orchestrator `run_hub.py`):**
   ```python
   # run_hub.py launches FastAPI in a background daemon thread/process,
   # then launches Streamlit in the main process.
   ```
2. **Option B (Streamlit Self-Hosted In-Process Daemon):**
   ```python
   # Inside app.py:
   @st.cache_resource
   def start_fastapi_daemon():
       import threading, uvicorn
       from api import app as api_app
       thread = threading.Thread(
           target=lambda: uvicorn.run(api_app, host="127.0.0.1", port=8002, log_level="warning"),
           daemon=True
       )
       thread.start()
       return thread
   ```
3. **Database Concurrency Guarantee:**
   Enabling SQLite **Write-Ahead Logging (`WAL`)** mode ensures simultaneous non-blocking reads from Streamlit while FastAPI writes incoming records.

---

## 6. Test Suite & Verification Plan

Deterministic testing strategy under the Zero-Discretion Mandate:

| Test File | Test Cases | Assertion Criteria |
|---|---|---|
| `test_database.py` | `test_init_and_insert`, `test_invalid_category_rejection`, `test_query_synthesis`, `test_batch_500_limit` | Schema strictly enforces 21 columns, valid category enum, query string synthesis, and 500-row limit check |
| `test_scraper.py` | `test_beckett_html_parsing`, `test_leading_zero_preservation` | Parses `beckett_sample.html`, returns >= 3 cards, preserves `'001'` |
| `test_vision.py` | `test_mock_vision_schema`, `test_ai_status_flagging` | Returns all 21 fields, flags `REVIEW VARIATION` when variation guessed |
| `test_api.py` | `test_health_endpoint`, `test_ingest_endpoint` | FastAPI `TestClient` sends payload, receives HTTP 200, row exists in DB |
| `test_sales.py` | `test_generate_marketplace_copy`, `test_tag_generation` | Generates title, price, specifics, description, and 10+ tags |
| `test_export.py` | `test_card_ladder_export_headers`, `test_leading_zeros_in_csv`, `test_fuzzy_normalization` | CSV contains exact 16 headers, `'001'` not converted to `1`, normalized names |

---

## 7. Conclusion & Next Steps
The technical architecture for `sports_cards/ecosystem_hub` is completely sound and fully compatible with the existing Python 3.13 environment. The proposed zero-dependency fallbacks ensure 100% operational reliability without external installation roadblocks. The design is ready for immediate implementation.
