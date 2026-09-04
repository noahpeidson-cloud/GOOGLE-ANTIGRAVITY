# Milestone 5 Architecture & UI Specification: Streamlit Visual Staging Area & Hub Dashboard (`app.py`)

## Executive Summary
This document provides the complete architectural blueprint and component specification for Milestone 5: **Streamlit Visual Staging Area & Hub Dashboard** (`app.py`).

The Streamlit Hub serves as the central control plane and visual staging area for the Sports Card Ecosystem. It bridges the entire multi-pipeline ingestion architecture (AI Vision photo analysis, Beckett/Cardboard Connection checklist scraping, Chrome Extension FastAPI bridge, and Manual Staging) into the master 21-variable SQLite database (`portfolio.db`), and provides 1-click monetization (SEO Facebook Marketplace listings) and pristine 16-variable Card Ladder CSV exports.

---

## 1. System Integration Map

The dashboard integrates directly with the completed modules built in Milestones 1 through 4:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Streamlit Visual Hub (app.py)                       │
│  - Top KPI Metrics Bar                                                      │
│  - 6 Specialized Operational Tabs                                           │
└──────┬────────────┬─────────────┬─────────────┬─────────────┬───────────────┘
       │            │             │             │             │
┌──────▼─────┐┌─────▼──────┐┌─────▼──────┐┌─────▼──────┐┌─────▼──────┐┌────────▼─────┐
│ database.py││vision_     ││scraper_    ││sales_      ││export.py   ││api.py         │
│            ││ingest.py   ││ingest.py   ││generator.py││            ││               │
│ - CRUD     ││- Gemini    ││- HTML      ││- Gemini SEO││- 16-Col    ││- FastAPI      │
│ - Filtering││  Vision    ││  Parser    ││  Copy      ││  Card Ladder│- Port 8002    │
│ - Stats    ││- Mock      ││- Parallel  ││- Mock Gen  ││- Fuzzy Norm││- Background   │
│ - Circuit  ││  Extractor ││  Expansion ││- Structured││- Zero-Pres ││  Server       │
│   Breaker  ││- Ingest    ││- Batch     ││  FB Copy   ││- Part      ││  Thread       │
│ - WAL Mode ││  Bridge    ││  Ingest    ││            ││  Chunking  ││               │
└────────────┘└────────────┘└────────────┘└────────────┘└────────────┘└──────────────┘
```

### Module Interface Contracts
| Target Module | Exported Functions Used in `app.py` | UI Purpose |
|---|---|---|
| `database.py` | `init_db()`, `get_summary_stats()`, `get_all_cards()`, `get_card_by_id()`, `update_card()`, `update_card_status()`, `delete_card()`, `insert_card()`, `insert_cards_batch()`, `clear_staging_table()`, `check_circuit_breaker()`, `get_next_child_id()` | Primary persistence, KPI aggregation, live table filtering, card edit/delete, batch inserts |
| `models.py` | `CardRecord`, `CardUpdate`, `CardCategory`, `VALID_CATEGORIES`, `AIStatus`, `synthesize_query`, `format_notes` | Strict Pydantic validation, enum lookups, query synthesis, parent-child ID formatting |
| `vision_ingest.py` | `extract_card_from_image()`, `MockVisionExtractor()`, `ingest_vision_card()`, `extraction_to_card_record()` | Multi-modal card photo analysis, instant preview extraction, database commit |
| `scraper_ingest.py` | `fetch_and_parse_checklist()`, `parse_checklist_html()`, `ingest_scraper_cards()`, `expand_parallels()` | Remote URL or raw HTML checklist parsing, parallel set generation, multi-card staging |
| `sales_generator.py` | `generate_marketplace_listing()`, `build_structured_listing()`, `MockSalesGenerator` | 1-click SEO FB Marketplace copy generator, structured spec formatting, hashtag generator |
| `export.py` | `export_card_ladder_csv()`, `validate_card_ladder_csv()`, `cards_to_card_ladder_dataframe()`, `CARD_LADDER_COLUMNS` | 16-column Card Ladder CSV generation, fuzzy player/set normalization, forensic validation, download button feeds |
| `api.py` | `is_port_in_use()`, `start_api_server_thread()`, `BackgroundServerThread`, `DEFAULT_DB_PATH` | API health check, daemon background server start/stop on port 8002 |

---

## 2. Streamlit Session State Architecture

To prevent Streamlit execution reruns from losing user inputs, staged data, or active background threads, the session state architecture is structured with explicit keys:

```python
SESSION_STATE_DEFAULTS = {
    # System & Database
    "db_path": os.environ.get("PORTFOLIO_DB_PATH", "portfolio.db"),
    "api_server_running": False,
    "api_server_thread": None,
    
    # Portfolio Staging (Tab 1)
    "selected_card_id": None,
    "staging_filter_category": "ALL",
    "staging_filter_status": "ALL",
    "staging_filter_year": "",
    "staging_search_query": "",
    "staging_page_offset": 0,
    
    # AI Vision Ingestion (Tab 2)
    "vision_extraction_result": None,     # Holds CardExtractionSchema
    "vision_front_bytes": None,
    "vision_back_bytes": None,
    "vision_parent_id": "8492",
    "vision_cost_basis": 0.0,
    "vision_mock_mode": True if not os.environ.get("GEMINI_API_KEY") else False,
    
    # Checklist Scraper (Tab 3)
    "scraper_raw_cards": [],             # Holds list of CardExtractionSchema
    "scraper_selected_indices": set(),
    "scraper_source_type": "URL",        # "URL" or "RAW_HTML"
    "scraper_target_set": "",
    "scraper_target_year": "",
    "scraper_target_category": "Basketball",
    "scraper_parallels_input": "Base",
    
    # Sales Copy Generator (Tab 4)
    "sales_selected_card_id": None,
    "sales_asking_price": 0.0,
    "sales_custom_notes": "",
    "sales_generated_text": "",
    "sales_structured_data": None,
    "sales_mock_mode": True if not os.environ.get("GEMINI_API_KEY") else False,
    
    # Card Ladder Export (Tab 5)
    "export_status_filter": "CLEARED",
    "export_apply_normalization": True,
    "export_row_count": 0,
    "export_file_paths": [],
    "export_validation_result": None,
}
```

---

## 3. UI Layout & Component Hierarchy

### Page Configuration & Theme
```python
st.set_page_config(
    page_title="Sports Card Ecosystem Hub",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

### Layout Structure
```
[Header: 🃏 Sports Card Ecosystem Hub | Port 8002 Status Badge | Theme/Settings]
─────────────────────────────────────────────────────────────────────────────
[Top KPI Metrics Bar (5 Metrics)]
  [Total Cards]  [Total Investment]  [Estimated Value]  [Pending AI Reviews]  [Cleared Cards]
─────────────────────────────────────────────────────────────────────────────
[Navigation: 6 Tabs]
  Tab 1: 📊 Portfolio Staging Area
  Tab 2: 📸 AI Vision Ingestion
  Tab 3: 📋 Checklist Scraper
  Tab 4: 🏷️ Sales Copy Generator
  Tab 5: 📤 Card Ladder CSV Export
  Tab 6: 🌐 API Bridge & System Health
```

---

## 4. Deep-Dive Tab Specifications

### 4.1 Top KPI Metrics Bar
Located above the tab bar, rendering five live metrics queried from `get_summary_stats(db_path)`:
1. **Total Cards**: Count of all records in `cards` table. Displays a warning badge `⚠️ Circuit Breaker Reached (500)` if `>= 500`.
2. **Total Investment**: `$XX,XXX.XX` (sum of `investment`).
3. **Total Estimated Value**: `$XX,XXX.XX` (sum of `estimated_value`). Shows delta: `+$X,XXX.XX (ROI: +XX.X%)`.
4. **Pending AI Reviews**: Count of cards with `ai_status IN ('REVIEW VARIATION', 'NEEDS REVIEW')`.
5. **Cleared Cards**: Count of cards with `ai_status = 'CLEARED'`.

### 4.2 Tab 1: 📊 Portfolio Staging Area
The master staging grid allows collectors to review, inspect, edit, and curate records before export:
- **Filters Row (`st.columns(4)`)**:
  - `Category`: Selectbox (`ALL` + 22 permitted categories: `Basketball`, `Baseball`, `Football`, etc.).
  - `AI Status`: Selectbox (`ALL`, `CLEARED`, `REVIEW VARIATION`, `NEEDS REVIEW`).
  - `Year`: Text input (filters exact 4-digit year or substring).
  - `Search`: Text input (fuzzy free-text search across `player`, `set_name`, `query`, and `notes`).
- **Interactive Staging Table**:
  - Rendered via `st.dataframe` with selection support:
    `st.dataframe(df, use_container_width=True, selection_mode="single-row", on_select="rerun")`
  - Columns displayed: `id`, `ai_status`, `player`, `year`, `set_name`, `variation`, `card_number`, `category`, `condition`, `investment`, `estimated_value`, `notes`, `query`.
- **Card Details & Edit Expander**:
  - Appears when a row is selected or via a card ID dropdown.
  - **Quick Status Bar**: Three 1-click status change buttons:
    - `[✅ Mark CLEARED]` -> Calls `update_card_status(card_id, "CLEARED")`
    - `[⚠️ Flag REVIEW VARIATION]` -> Calls `update_card_status(card_id, "REVIEW VARIATION")`
    - `[❌ Flag NEEDS REVIEW]` -> Calls `update_card_status(card_id, "NEEDS REVIEW")`
  - **Edit Form (`st.form("edit_card_form")`)**:
    - Two-column grid with pre-populated values for all 21 fields.
    - Automatic validation on submission: re-calculates `query` string dynamically if player, year, set, variation, or condition change.
    - `[💾 Save Changes]` button -> Calls `update_card(card_id, updates)` -> `st.toast("Card updated successfully!", icon="✅")` -> `st.rerun()`.
  - **Delete Card & Actions**:
    - `[🗑️ Delete Card]` button with confirmation -> Calls `delete_card(card_id)` -> `st.toast("Card deleted", icon="🗑️")` -> `st.rerun()`.
    - `[✨ Generate Sales Copy]` button -> Switches active view/context to Tab 4 with this card pre-selected.
  - **Staging Table Maintenance**:
    - `[⚠️ Clear Entire Staging Table]` button with modal/confirmation checkbox -> Calls `clear_staging_table(db_path)`.

### 4.3 Tab 2: 📸 AI Vision Ingestion
Zero-friction photo analysis leveraging Google Gemini 2.5 Flash Multimodal API with deterministic offline mock fallback:
- **Image Upload Controls**:
  - `Front Card Photo`: `st.file_uploader("Front Card Image", type=["jpg", "jpeg", "png", "webp"])`
  - `Back Card Photo (Optional)`: `st.file_uploader("Back Card Image", type=["jpg", "jpeg", "png", "webp"])`
- **Ingestion Parameters**:
  - `Parent Image ID`: Text input (e.g. `8492` - automatically generates `8492-101`, `8492-102` tracking notes).
  - `Cost Basis / Investment ($)`: Number input (default `0.00`).
  - `Purchase Date`: Date input (defaults to today `MM/DD/YYYY`).
  - `Mode Toggle`: Checkbox `"Offline Mock Mode"` (auto-selected if `GEMINI_API_KEY` is not present in environment).
- **Extraction Trigger**:
  - `[🔍 Extract Card Info with Gemini]` button:
    - Reads uploaded file bytes.
    - Calls `extract_card_from_image(front_bytes, back_bytes, mock=mock_mode, parent_image_id=parent_id)`.
    - Saves extraction schema into `st.session_state.vision_extraction_result`.
- **Extraction Preview & Review Form**:
  - Displays side-by-side: Image thumbnail & Structured Extraction Grid.
  - Form with pre-populated extracted values (Player, Year, Set, Variation, Number, Category, Condition, Slab Serial, Estimated Value, AI Status).
  - `[💾 Commit Card to Staging DB]` button:
    - Validates 21-variable schema via `ingest_vision_card()`.
    - Automatically updates tracking notes using `get_next_child_id()`.
    - `st.toast("Card successfully ingested to staging database!", icon="🃏")`.
    - Resets upload state and refreshes staging table.

### 4.4 Tab 3: 📋 Checklist Scraper
Bulk checklist extraction from Beckett or Cardboard Connection to stage complete set breakdowns in seconds:
- **Input Source Selection**:
  - Radio button: `🌐 Beckett / Cardboard Connection URL` vs `📝 Raw HTML Paste`
- **Metadata Fields (Auto-Inferred if Left Blank)**:
  - `Set Name` (e.g., `Panini Prizm`)
  - `Year` (e.g., `2024`)
  - `Category` (e.g., `Basketball`)
  - `Parallels List`: Text input / multiselect (e.g., `Base, Silver Prizm, Red White Blue Prizm, Hyper Prizm, Gold Prizm /10`).
- **Parsing Trigger**:
  - `[📥 Parse Checklist]` button:
    - If URL selected: Calls `fetch_and_parse_checklist(url, set_name, year, category, parallels)`.
    - If HTML pasted: Calls `parse_checklist_html(html, set_name, year, category, parallels)`.
    - Stores parsed list of `CardExtractionSchema` objects in `st.session_state.scraper_raw_cards`.
- **Interactive Checklist Staging Table**:
  - Displays parsed cards with columns: `Card #`, `Player`, `Team / Notes`, `Variation`, `AI Status`, `Category`.
  - Checkbox selection or batch select-all / deselect-all controls.
  - Displays count: `"Selected X of Y cards"`.
- **Bulk Ingest Controls**:
  - `Default Cost / Investment per card ($)` (e.g. `0.50` for retail pack breaks).
  - `Date Purchased` (defaults to today).
  - `Parent Batch ID` (e.g. `9001` for box break).
  - `[⚡ Bulk Ingest (N) Cards to Database]` button:
    - Checks 500-card circuit breaker.
    - Calls `ingest_scraper_cards(selected_cards, parent_id=parent_id, investment=inv, date_purchased=date)`.
    - `st.toast(f"Successfully staged {len(inserted)} cards!", icon="🚀")`.
    - Clears scraper staging buffer and refreshes KPI bar.

### 4.5 Tab 4: 🏷️ Sales Copy Generator
High-conversion, SEO-optimized Facebook Marketplace and social listing copy generator:
- **Target Card Selection**:
  - Radio button: `🗄️ Select from Staging Database` vs `✍️ Manual Card Input`
  - If database selected: Searchable card selectbox displaying `[ID] [Year] [Set] [Player] [Variation] [Condition]`.
- **Listing Parameters**:
  - `Asking Price ($)`: Defaults to card's `estimated_value` or `investment`.
  - `Custom Condition Notes`: Text area (e.g., "Includes magnetic one-touch case. Local pickup in Scottsdale, AZ.").
  - `Generator Mode`: Checkbox `"Offline Deterministic SEO Mock"` vs `"Live Gemini 2.5 Flash"`.
- **Generation Trigger**:
  - `[✨ Generate Facebook Marketplace Listing]` button:
    - Calls `generate_marketplace_listing(card, asking_price=price, custom_notes=notes, mock=mock_mode)`.
    - Calls `build_structured_listing(card, asking_price=price, custom_notes=notes, card_id=id, is_mock=mock_mode)`.
    - Saves output into session state.
- **Visual Listing Preview & Copy Box**:
  - **Structured Spec Cards**:
    - **SEO Title**: Displayed with character count pill badge (e.g. `84 / 99 chars` - green if `< 100`, red if `>= 100`).
    - **Asking Price**: Formatted `$XXX.XX`.
    - **Specs Grid**: Year, Brand/Set, Card #, Player, Variation, Category, Condition, Slab Cert #.
    - **Condition & Buyer Assurance**: Formatted paragraphs.
    - **Hashtags**: Badge pills for 6-8 viral tags (`#SportsCards #TheHobby #PaniniPrizm ...`).
  - **Copy-Paste Ready Text Block**:
    - `st.text_area("Full Copy Block", value=raw_text, height=280)`
    - `st.code(raw_text, language="markdown")` for 1-click clipboard copying.

### 4.6 Tab 5: 📤 Card Ladder CSV Export
Generates Card Ladder CSV uploads with fuzzy player/set normalization and leading-zero preservation:
- **Export Filters & Settings**:
  - `AI Status Filter`: Selectbox (`CLEARED` [recommended default], `ALL`, `REVIEW VARIATION`, `NEEDS REVIEW`).
  - `Fuzzy Normalization`: Checkbox `"Apply Canonical Player/Set Normalization"` (default Checked).
  - `Output Filename`: Text input (default `CardLadder_Bulk_Upload.csv`).
  - `Batch Size Limit`: Display badge `500 Cards / Part` (Card Ladder ingestion threshold).
- **Export Trigger**:
  - `[🚀 Export to Card Ladder CSV]` button:
    - Calls `export_card_ladder_csv(db_path, output_path, status_filter=filter, apply_normalization=norm)`.
    - Calls `validate_card_ladder_csv(path)` to forensically audit the output.
    - Saves result in session state.
- **Forensic Validation & Download Station**:
  - **Audit Status Box**:
    - `✅ 16 Exact Columns Verified: Date Purchased, Quantity, Player, Year, Set, Variation, Number, Category, Condition, Investment, Estimated Value, Ladder ID, Notes, Date Sold, Sold Price, Image`
    - `✅ Excluded 5 Internal Fields (Slab Serial #, Query, Tags, Back Image, AI Status)`
    - `✅ Leading Zeroes Preserved on Card Number`
    - `✅ Total Records Exported: N`
  - **Download Buttons**:
    - If 1 file generated: `st.download_button("📥 Download CardLadder_Bulk_Upload.csv", data=file_bytes, file_name="CardLadder_Bulk_Upload.csv", mime="text/csv")`.
    - If multiple chunked files: Multiple download buttons (`Part 1`, `Part 2`, etc.).
  - **CSV Preview Table**: Displays first 10 rows of the pristine 16-column export.

### 4.7 Tab 6: 🌐 API Bridge & System Health
System health diagnostics, database maintenance, and FastAPI background server management:
- **FastAPI Chrome Extension Bridge Daemon**:
  - Status indicator: `🟢 Online (Listening on http://127.0.0.1:8002)` or `🔴 Offline`.
  - Control buttons:
    - `[▶️ Start Background API Bridge]` -> Starts `BackgroundServerThread` on port 8002.
    - `[⏹️ Stop API Server]` -> Gracefully stops uvicorn server.
  - Interactive Documentation Link: `http://127.0.0.1:8002/docs`.
  - Quick Integration Guide: Sample `curl` command for Chrome Extension `POST /api/v1/cards/capture`.
- **Database & Storage Diagnostics**:
  - Database Path: `portfolio.db` (file size in KB, permissions).
  - SQLite Configuration: `WAL Mode = Active`, `Busy Timeout = 5000ms`, `Synchronous = NORMAL`.
  - Staging Capacity Gauge: Progress bar showing current card count vs 500-card circuit breaker (`N / 500 staged`).
- **Portfolio Analytics & Category Breakdown**:
  - Category count distribution chart (Plotly bar / pie chart or table).
  - AI Review Status distribution (Cleared vs Review Variation vs Needs Review).

---

## 5. Session State Keys & Event Handling Summary

| Event / Action | Trigger Component | Session State Updated | Side Effect |
|---|---|---|---|
| Filter Table | Selectbox / Text Inputs | `staging_filter_*`, `staging_search_query` | Re-queries `get_all_cards()` on next render |
| Select Card | DataFrame row click | `selected_card_id` | Populates Details & Edit expander |
| Update Card | `[💾 Save Changes]` in Tab 1 | `selected_card_id` | Calls `update_card()`, triggers `st.toast()`, `st.rerun()` |
| Delete Card | `[🗑️ Delete Card]` in Tab 1 | `selected_card_id` = None | Calls `delete_card()`, triggers `st.toast()`, `st.rerun()` |
| Extract Photo | `[🔍 Extract Card Info]` in Tab 2 | `vision_extraction_result` | Calls `extract_card_from_image()`, renders review form |
| Commit Vision Card | `[💾 Commit Card]` in Tab 2 | `vision_extraction_result` = None | Calls `ingest_vision_card()`, clears preview, `st.toast()` |
| Parse Checklist | `[📥 Parse Checklist]` in Tab 3 | `scraper_raw_cards` | Calls `parse_checklist_html()`, populates staging table |
| Bulk Ingest Scraper | `[⚡ Bulk Ingest]` in Tab 3 | `scraper_raw_cards` = [] | Calls `ingest_scraper_cards()`, `st.toast()`, refreshes table |
| Generate Sales Copy | `[✨ Generate Listing]` in Tab 4 | `sales_generated_text`, `sales_structured_data` | Calls `generate_marketplace_listing()`, renders copy box |
| Export CSV | `[🚀 Export CSV]` in Tab 5 | `export_file_paths`, `export_row_count` | Calls `export_card_ladder_csv()`, triggers download buttons |
| Toggle API Server | `[▶️ Start]` / `[⏹️ Stop]` in Tab 6 | `api_server_running`, `api_server_thread` | Launches / terminates daemon thread on port 8002 |

---

## 6. Implementation Architecture for `app.py`

To ensure maintainability and testability, `app.py` is organized into modular render functions:

```python
"""
app.py - Streamlit Visual Staging Area & Central Hub for Sports Card Ecosystem.
"""

import os
import streamlit as st
import pandas as pd
from database import ...
from models import ...
from vision_ingest import ...
from scraper_ingest import ...
from sales_generator import ...
from export import ...
from api import ...

def init_session_state():
    """Initializes default keys in st.session_state."""
    ...

def render_custom_css():
    """Injects modern minimalist zinc typography and metric card styles."""
    ...

def render_header():
    """Renders application header and port status badge."""
    ...

def render_kpi_bar(stats: dict):
    """Renders 5 top KPI metrics."""
    ...

def render_tab_staging(db_path: str):
    """Tab 1: Portfolio Staging Area."""
    ...

def render_tab_vision(db_path: str):
    """Tab 2: AI Vision Ingestion."""
    ...

def render_tab_scraper(db_path: str):
    """Tab 3: Checklist Scraper."""
    ...

def render_tab_sales(db_path: str):
    """Tab 4: Sales Copy Generator."""
    ...

def render_tab_export(db_path: str):
    """Tab 5: Card Ladder CSV Export."""
    ...

def render_tab_health(db_path: str):
    """Tab 6: API Bridge & System Health."""
    ...

def main():
    """Application main entry point."""
    st.set_page_config(...)
    init_session_state()
    render_custom_css()
    
    # Auto-initialize DB schema
    db_path = st.session_state.db_path
    init_db(db_path)
    
    render_header()
    stats = get_summary_stats(db_path)
    render_kpi_bar(stats)
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Portfolio Staging",
        "📸 AI Vision Ingest",
        "📋 Checklist Scraper",
        "🏷️ Sales Copy Generator",
        "📤 Card Ladder Export",
        "🌐 API Bridge & Health"
    ])
    
    with tab1: render_tab_staging(db_path)
    with tab2: render_tab_vision(db_path)
    with tab3: render_tab_scraper(db_path)
    with tab4: render_tab_sales(db_path)
    with tab5: render_tab_export(db_path)
    with tab6: render_tab_health(db_path)

if __name__ == "__main__":
    main()
```

---

## 7. Verification & Testing Strategy for Implementer

When the implementer builds `app.py` and tests it:
1. **Deterministic Syntax & Import Verification**:
   - `python -m py_compile app.py` must pass with 0 syntax errors.
2. **Streamlit Headless / CLI Test**:
   - `streamlit run app.py --server.headless true --server.port 8501` can be tested or verified via programmatic test harness.
3. **Module Interoperability Test**:
   - Programmatic integration test `tests/test_streamlit_hub.py` asserting that all functions called by `app.py` exist in their respective modules and return valid schema objects without exceptions.
4. **End-to-End Functional Walkthrough**:
   - Ingest card via Mock Vision -> Staged in DB -> Displayed in Tab 1 -> Edit card -> Generate FB sales copy -> Export to Card Ladder CSV -> Verify 16 columns.
