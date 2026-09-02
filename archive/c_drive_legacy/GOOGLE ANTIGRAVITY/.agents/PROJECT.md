# Project: Sports Card Ecosystem Hub

## Architecture
- **Root Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub`
- **Core Technology Stack**:
  - Python 3.13 (Windows)
  - Database: SQLite3 (`portfolio.db`) with WAL mode
  - Dashboard: Streamlit (`app.py`)
  - Ingestion API Bridge: FastAPI (`api.py`) + Uvicorn
  - Data Processing & Export: Pandas (`export.py`), `difflib` for fuzzy normalization
  - AI Vision & Copy: `google-genai` SDK (`vision_ingest.py`, `sales_generator.py`) + Mock fallbacks
  - Web Scraping: Built-in `html.parser` / `requests` parser (`scraper_ingest.py`)
- **Data Flow**:
  1. Ingestion Sources (AI Vision, Checklist Scraper, Chrome Extension POST API, Manual Entry)
  2. Master 21-Variable SQLite Ingestion Layer (`portfolio.db`)
  3. Visual Staging, Validation & Filtering in Streamlit Dashboard (`app.py`)
  4. Sales Copy Generation (`sales_generator.py`) for Facebook Marketplace
  5. Fuzzy Normalization & Pristine 16-Column Card Ladder CSV Export (`export.py`)

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | 21-Variable SQLite Schema | Enforces 21 fields, 22 category check constraints, types, defaults, and query synthesis in portfolio.db | M1 | ORIGINAL_REQUEST §R1 & survey |
| 2 | Core Database CRUD & Tracking | Python database interface with insert, query, update, delete, batching, and `[Parent]-[Child]` ID tracking | M1 | survey |
| 3 | AI Vision Ingestion | Gemini Multimodal API photo analysis with Pydantic `CardExtractionSchema` and offline mock fallback | M2 | ORIGINAL_REQUEST §R2 |
| 4 | Beckett/Cardboard Scraper | Checklist table/list parser extracting card numbers, players, teams, parallels with static HTML testing | M2 | ORIGINAL_REQUEST §R2 |
| 5 | Chrome Extension API Bridge | FastAPI endpoint `POST /api/v1/cards/capture` validating 21 variables and persisting to `portfolio.db` | M3 | ORIGINAL_REQUEST §R3 |
| 6 | Sales Listing Generator | Gemini-powered SEO Facebook Marketplace listing generator with titles, bullets, terms, hashtags, and mock fallback | M3 | ORIGINAL_REQUEST §R3 |
| 7 | Fuzzy String Normalization | `difflib`-based normalization of player and set names against canonical checklists | M4 | ORIGINAL_REQUEST §R4 |
| 8 | Card Ladder 16-Column CSV Export | Pandas export producing exactly 16 Card Ladder headers, preserving leading zeros, 500-card batch limit | M4 | ORIGINAL_REQUEST §R4 |
| 9 | Streamlit Central Hub UI | Staging dashboard with card grid, status filters, ingestion controls, listing generator, and export trigger | M5 | ORIGINAL_REQUEST §R1 |
| 10 | Unified Hub Runner / Daemon | Background FastAPI server + Streamlit integration for concurrent local operation | M5 | survey |
| 11 | Comprehensive E2E Verification | 100% test pass on Tiers 1-4 and adversarial coverage hardening (Tier 5) | M6 | ORIGINAL_REQUEST Acceptance |

## Code Layout
```
sports_cards/ecosystem_hub/
├── app.py                   # Streamlit central dashboard UI
├── database.py              # SQLite database manager, DDL, CRUD, WAL setup
├── models.py                # Pydantic schemas (21-variable ingestion, Card Ladder export, API models)
├── vision_ingest.py         # Gemini Multimodal AI vision extractor + offline mock
├── scraper_ingest.py        # Beckett / Cardboard Connection checklist parser + static HTML ingest
├── api.py                   # FastAPI application for Chrome Extension bridge
├── sales_generator.py       # Facebook Marketplace SEO listing copy generator
├── export.py                # Fuzzy string normalizer + Card Ladder 16-variable CSV exporter
├── fixtures/                # Static HTML checklists, sample JSON, mock images
│   ├── beckett_sample.html
│   └── mock_card_data.json
└── tests/                   # Deterministic test suite (Tiers 1-5)
    ├── test_database.py
    ├── test_ingest_vision.py
    ├── test_ingest_scraper.py
    ├── test_api_bridge.py
    ├── test_sales_generator.py
    ├── test_export.py
    └── test_e2e_hub.py
```

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Core Database & Models | `database.py`, `models.py`, 21-variable schema in `portfolio.db`, CRUD tests | none | DONE |
| 2 | Ingestion Pipelines | `vision_ingest.py`, `scraper_ingest.py`, static HTML fixtures, offline tests | M1 | DONE |
| 3 | API Bridge & Sales Generator | `api.py` (FastAPI `/api/v1/cards/capture`), `sales_generator.py`, mock tests | M1 | DONE |
| 4 | Export Pipeline | `export.py`, fuzzy normalizer, 16-column Card Ladder CSV builder, zero-preservation tests | M1 | DONE |
| 5 | Streamlit Visual Hub | `app.py`, staging tables, filters, interactive ingestion & export triggers | M1, M2, M3, M4 | DONE |
| 6 | E2E Testing & Hardening | Full opaque-box E2E test suite (Tiers 1-4) & adversarial hardening (Tier 5) | M1, M2, M3, M4, M5 | DONE |

## Interface Contracts

### 1. Database Model (`models.py` & `database.py`)
- Master Record:
  - `date_purchased`: str (`MM/DD/YYYY`)
  - `quantity`: int (`>= 1`, default 1)
  - `player`: str (NOT NULL)
  - `year`: str (4 digits `YYYY`)
  - `set_name`: str (NOT NULL)
  - `variation`: str (default `''`)
  - `card_number`: str (default `''`, preserves leading zeroes)
  - `category`: str (one of 22 exact values)
  - `condition`: str (`'Raw'` or `'PSA 10'`, `'BGS 9.5'`, etc.)
  - `slab_serial_number`: str (default `''`, must be blank if Raw)
  - `investment`: float (default `0.00`)
  - `estimated_value`: float (default `0.00`)
  - `ladder_id`: str (default `''`)
  - `query`: str (`[Year] [Set] [Player] [Variation] [Condition]`)
  - `notes`: str (`[Parent_Image_ID]-[Child_Card_ID]`)
  - `tags`: str (default `''`)
  - `date_sold`: str (default `''`)
  - `sold_price`: float (nullable)
  - `image`: str (default `''`)
  - `back_image`: str (default `''`)
  - `ai_status`: str (`'CLEARED'`, `'REVIEW VARIATION'`, `'NEEDS REVIEW'`)

### 2. Ingestion Contracts
- **Vision**: `extract_card_from_image(image_path: str, mock: bool = False) -> CardExtractionSchema`
- **Scraper**: `parse_checklist_html(html_content: str, set_name: str, year: str, category: str) -> list[CardExtractionSchema]`

### 3. API Bridge Contract
- `POST /api/v1/cards/capture`: Accepts JSON matching `CardCaptureRequest`, inserts into `portfolio.db`, returns `{"status": "success", "card_id": int, "query": str}`.

### 4. Sales Generator Contract
- `generate_marketplace_listing(card: dict, asking_price: float, mock: bool = False) -> str`: Returns structured copy with Title (<100 chars), Price, Specs bullets, Slab verification, Terms, and 6-8 hashtags.

### 5. Export Contract
- `export_card_ladder_csv(db_path: str, output_csv_path: str, status_filter: str = 'CLEARED') -> tuple[int, list[str]]`: Returns `(row_count, generated_files)`. Output CSV contains exactly 16 columns in specified order, preserving leading zeroes in `Number`.
