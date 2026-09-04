# Milestone 5 Analysis: Streamlit Visual Hub Integration & Server Coexistence (`app.py`)

## Executive Summary
This document defines the architectural blueprint and technical integration specifications for **Milestone 5: Streamlit Visual Staging Area & Hub Dashboard (`app.py`)** within the Sports Card Ecosystem Hub. 

The application serves as the unified operational command center, bridging **4 ingestion channels** (AI Vision, Checklist Scraper, Chrome Extension FastAPI Bridge, Manual Staging), the **Master 21-Variable SQLite Ingestion Layer**, the **Sales Copy Generation Engine**, and the **16-Column Card Ladder CSV Export Pipeline**.

```
                           +-------------------------------------------------------+
                           |           Streamlit Hub Dashboard (app.py)            |
                           |  [Tab 1: Staging]  [Tab 2: Vision]  [Tab 3: Scraper]  |
                           |  [Tab 4: Sales]    [Tab 5: Export]                    |
                           +---------------------------+---------------------------+
                                                       |
                     +---------------------------------+---------------------------------+
                     |                                 |                                 |
                     v                                 v                                 v
        +-------------------------+       +-------------------------+       +-------------------------+
        |  api.py (FastAPI Bridge)|       | vision_ingest / scraper |       | export.py / sales_gen   |
        |  Background Daemon      |       | Ingestion Pipelines     |       | Normalization & Export  |
        |  @st.cache_resource     |       | Mock / Live Gemini      |       | Card Ladder 16-Col CSV  |
        +------------+------------+       +------------+------------+       +------------+------------+
                     |                                 |                                 |
                     +---------------------------------+---------------------------------+
                                                       |
                                                       v
                                     +-----------------------------------+
                                     |    portfolio.db (SQLite3 WAL)     |
                                     |  - 21-Variable Strict Schema      |
                                     |  - busy_timeout = 5000ms          |
                                     |  - Non-blocking Reader/Writer     |
                                     +-----------------------------------+
```

---

## 1. Server Coexistence Architecture & SQLite Concurrency Model

### 1.1 The Dual-Server Paradigm (Streamlit + FastAPI Daemon)
The system requires simultaneous, non-interfering execution of:
1. **Streamlit Interactive UI (`app.py`)**: Runs on Streamlit's event loop (default port 8501), rendering reactive UI components on script reruns.
2. **FastAPI Ingestion Bridge (`api.py`)**: Listens on HTTP (default port 8002) to receive asynchronous `POST /api/v1/cards/capture` requests from Chrome Extensions or webhooks.

#### Lifecycle Management via `@st.cache_resource`
Because Streamlit executes `app.py` from top to bottom on every user action (button click, slider adjustment, filter change), the FastAPI daemon must be instantiated exactly once per server process and cached across script reruns:

```python
@st.cache_resource
def get_or_start_api_server(
    host: str = "127.0.0.1", 
    port: int = 8002, 
    db_path: str = DEFAULT_DB_PATH
) -> BackgroundServerThread:
    """
    Spawns and caches the FastAPI background listener daemon.
    Guarantees idempotency and prevents port re-binding errors across Streamlit reruns.
    """
    server_thread = start_api_server_thread(host=host, port=port, db_path=db_path)
    return server_thread
```

**Key Architectural Guarantees**:
- **Bypass Signal Handlers**: In `BackgroundServerThread.run()`, `self.server.install_signal_handlers = lambda: None` is explicitly set. This prevents Python `ValueError: signal only works in main thread of the main interpreter` when uvicorn is spawned inside a worker thread on Windows.
- **Port Conflict Protection**: `is_port_in_use(port, host)` validates socket availability prior to binding. If port 8002 is already occupied by a previously spawned daemon, a lightweight surrogate `BackgroundServerThread` is returned with `_is_ready.set()`.
- **Health Telemetry in UI**: Streamlit's sidebar queries `/api/v1/health` or `server_thread.is_alive()` to display live daemon status:
  - `🟢 API Bridge Active (Port 8002)`
  - `🔴 API Bridge Inactive`

### 1.2 Zero-Lock SQLite Concurrency under WAL Mode
Under standard rollback journal mode, SQLite locks the entire database file during writes, causing `sqlite3.OperationalError: database is locked` when Streamlit UI queries intersect with incoming API capture payloads.

The Hub resolves this through **WAL (Write-Ahead Logging)** mode configured in `database.py`:

```python
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA encoding = 'UTF-8';
```

#### Concurrency Interaction Matrix

| Operation 1 | Operation 2 | Concurrency Behavior | Lock Risk |
|---|---|---|---|
| Streamlit UI Reading Table (`get_all_cards`) | FastAPI Writing Card (`insert_card`) | WAL allows simultaneous readers and writer. Reader reads consistent snapshot; writer writes to `.wal` file. | **Zero Lock** (Independent) |
| Streamlit Updating Status (`update_card_status`) | FastAPI Writing Card (`insert_card`) | SQLite serializes the two writes. `busy_timeout = 5000` allows the second writer to wait up to 5.0s (write takes < 5ms). | **Zero Lock** (Handled by timeout) |
| Streamlit Exporting CSV (`fetch_records_for_export`) | Streamlit Inline Edit (`update_card`) | Export reads point-in-time snapshot while inline edit writes to WAL. | **Zero Lock** |
| Multiple Streamlit Tabs / Browser Sessions | Background Batch Ingestion | Readers execute concurrently across threads. | **Zero Lock** |

#### Connection Hygiene Rules for `app.py`:
1. **Never persist `sqlite3.Connection` in `st.session_state`**: SQLite connections are not thread-safe and must not be shared across Streamlit rerun cycles.
2. **Always use `with get_db_connection(db_path) as conn:`**: Guarantees automatic rollback on error, immediate commit on success, and guaranteed closure of the connection.
3. **No Long-Running Open Connections**: Database operations must execute and close within milliseconds before triggering external AI calls or file conversions.

---

## 2. Module-by-Module Integration Blueprints

### 2.1 Integration with `database.py` (CRUD, Metrics, Filtering, Query Synthesis, Tracking Notes)

#### A. Staging Grid & Dynamic Filtering
`app.py` directly binds to `database.get_all_cards` using Streamlit controls:
- **Status Filter**: `st.selectbox("Filter by AI Status", options=["ALL", "CLEARED", "REVIEW VARIATION", "NEEDS REVIEW"], index=0)`
- **Category Filter**: `st.selectbox("Filter by Category", options=["ALL"] + sorted(list(VALID_CATEGORIES)))`
- **Search Query**: `st.text_input("Search (Player, Set, Query, Notes)", "")`
- **Sort Ordering**: `st.selectbox("Sort Order", options=["id DESC", "id ASC", "player ASC", "estimated_value DESC", "date_purchased DESC"])`

```python
cards = get_all_cards(
    status_filter=selected_status if selected_status != "ALL" else None,
    category_filter=selected_category if selected_category != "ALL" else None,
    search_query=search_term if search_term.strip() else None,
    order_by=selected_order,
    limit=500,
    db_path=active_db_path,
)
```

#### B. Summary Metrics Banner & KPI Display
`app.py` queries `database.get_summary_stats(db_path)` and renders top-level KPI metric cards:
- **Total Staged Cards**: `stats["total_cards"]` (with progress indicator toward 500-card circuit breaker limit).
- **Total Investment Basis**: `f"${stats['total_investment']:,.2f}"`
- **Total Estimated Market Value**: `f"${stats['total_estimated_value']:,.2f}"`
- **Net Unrealized Spread / ROI**: `f"${stats['total_estimated_value'] - stats['total_investment']:+,.2f}"`
- **Review Attention Counter**: `stats['count_by_ai_status'].get('REVIEW VARIATION', 0) + stats['count_by_ai_status'].get('NEEDS REVIEW', 0)`

#### C. Manual Card Ingestion Form with Live 21-Variable Validation
A dedicated collapsible form allows single-card manual staging:
- Enforces 21 fields with automatic query synthesis:
  ```python
  synthesized_query = synthesize_query(
      year=form_year,
      set_name=form_set,
      player=form_player,
      variation=form_variation,
      condition=form_condition,
  )
  ```
- Cross-field guardrails:
  - If `Condition == "Raw"`, disable and clear `slab_serial_number`.
  - Validate model through `CardRecord(**payload)` prior to `database.insert_card()`.
  - If variation is non-empty, default status to `REVIEW VARIATION`.

#### D. Live Editing & Status Resolution
- **One-Click Clear**: Button to set `ai_status = "CLEARED"` via `database.update_card_status(card_id, "CLEARED", db_path)`.
- **Inline Editing**: Modal/Expander to update fields (Price, Variation, Condition, Notes, Player) via `database.update_card(card_id, updates, db_path)`.
- **Delete / Bulk Clear**:
  - Single card delete: `database.delete_card(card_id, db_path)`
  - Full staging wipe: `database.clear_staging_table(db_path)` protected with double-confirmation popover.

---

### 2.2 Integration with `vision_ingest.py` (AI Multimodal Ingestion & Offline Mock)

#### A. Multi-Image Ingestion Workflow
Streamlit provides `st.file_uploader(accept_multiple_files=True, type=["jpg", "jpeg", "png", "webp"])`.
- Supports single front images or multi-image batches.
- Handles image inputs either as in-memory bytes (`uploaded_file.getvalue()`) or saved temporary paths.

#### B. Execution Parameters & Configuration
- **Parent Image Tracking ID**: Input field (e.g. `8492` or auto-generated 4-digit timestamp).
- **Default Investment**: Cost basis to assign across the batch ($0.00 default).
- **Execution Mode**:
  - `Offline Mock Mode` (default if no `GEMINI_API_KEY` present; uses `MockVisionExtractor` with zero network calls and deterministic fixture matching).
  - `Live Gemini Multimodal API` (`gemini-2.5-flash` with structured Pydantic schema output).
- **API Key Override**: Optional UI input field if not exported in OS environment.

#### C. Ingestion Loop & Progress Tracking
```python
with st.status(f"Processing {len(uploaded_files)} card images...", expanded=True) as status_container:
    start_child_id = get_next_child_id(parent_image_id, db_path=active_db_path)
    inserted_ids = []
    
    for idx, file_obj in enumerate(uploaded_files, start=1):
        child_id = start_child_id + idx - 1
        # Extract structured schema
        extraction = extract_card_from_image(
            image_path=file_obj.getvalue(),
            mock=use_mock_mode,
            api_key=api_key,
            parent_image_id=parent_image_id,
            child_card_id=child_id,
        )
        # Convert & Insert
        card_id = ingest_vision_card(
            extraction=extraction,
            parent_image_id=parent_image_id,
            child_card_id=child_id,
            investment=batch_investment,
            db_path=active_db_path,
        )
        inserted_ids.append(card_id)
        st.write(f"✅ Extracted: **{extraction.player}** ({extraction.year} {extraction.set_name}) → Card ID #{card_id} [{extraction.notes}]")
        
    status_container.update(label=f"Successfully ingested {len(inserted_ids)} cards!", state="complete", expanded=False)
```

---

### 2.3 Integration with `scraper_ingest.py` (Streaming Checklist Parser & Parallel Generation)

#### A. Ingestion Source Modalities
1. **Remote URL**: `fetch_and_parse_checklist(url, fallback_fixture_path=...)`
2. **Raw HTML Paste / File Upload**: `parse_checklist_html(html_text, ...)`
3. **Built-in Static Fixture**: Loads `fixtures/beckett_sample.html` for 100% offline verification.

#### B. Metadata Inference & Custom Overrides
The built-in parser automatically executes `infer_metadata_from_text(header)` to infer:
- **Year** (e.g. `2024`)
- **Category** (e.g. `Basketball`)
- **Set Name** (e.g. `Panini Prizm`)
Streamlit pre-populates editable text inputs allowing the user to override or fine-tune inferred metadata before expansion.

#### C. Interactive Parallel Variation Matrix
1. `extract_parallels_from_html(parser)` scans the HTML for parallel listings (e.g. `Base`, `Silver Prizm`, `Gold Prizm /10`, `Refractor`, `Green Prizm`).
2. Streamlit renders an interactive multiselect:
   `selected_parallels = st.multiselect("Parallels to Generate", options=detected_parallels, default=["Base"])`
3. Allows custom parallel addition via text tag input.

#### D. Selective Ingestion & Circuit Breaker Protection
1. Renders the parsed checklist cards in an interactive checklist table with selectable rows.
2. User can select all or select specific cards (e.g., only rookie cards `[RC]`).
3. Total calculated records: `len(selected_cards) * len(selected_parallels)`
4. Circuit breaker validation:
   ```python
   current_count = get_card_count(active_db_path)
   if current_count + total_to_generate > 500:
       st.warning(f"⚠️ Batch size ({total_to_generate}) + current staging ({current_count}) exceeds 500-card limit. Adjust selection.")
   ```
5. On confirmation, executes `expand_parallels` and `ingest_scraper_cards(extractions, parent_id=parent_id, db_path=active_db_path)`.

---

### 2.4 Integration with `sales_generator.py` (Listing Generation & Clipboard Export)

#### A. Card Selection & On-Demand Context
- Select card from staged database via searchable selectbox or direct "Generate Listing" row action in Staging tab.
- Pre-fills current estimated market value as asking price.

#### B. Pricing & Condition Overrides
- **Target Asking Price**: Number input (defaults to `estimated_value` or `investment` or `$50.00`).
- **Additional Custom Notes**: Text area (e.g. "Includes magnetic one-touch case, local pickup in North Scottsdale").
- **Generator Mode**: Toggle between `Live Gemini 2.5 Flash Copywriter` and `Deterministic Mock Generator`.

#### C. Listing Copy Presentation & Clipboard Export
Displays the generated 6-section copy block:
1. **Title (<100 chars)**: Formatted as `[Year] [Set] [Player] [Variation] [Condition]`, stripped of forbidden spam buzzwords (`L@@K`, `FIRE`, `INVEST`, emojis).
2. **Asking Price & Payment Terms**: Formatted currency and supported payment options.
3. **Key Specifications**: Structured bullet points (Year, Brand, Card #, Player, Variation, Category, Condition, Slab Cert #).
4. **Condition & Authenticity**: Graded slab registry confirmation or raw card penny sleeve/top loader description.
5. **Shipping & Local Pickup Terms**: BMWT shipping guarantee, local safe meetup terms.
6. **Viral Discovery Hashtags**: Strictly 6 to 8 targeted hobby tags (`#SportsCards #TheHobby #BasketballCards...`).

#### Clipboard Integration:
- Rendered in a `st.code(listing_text, language="markdown")` block featuring native one-click clipboard copying.
- Accompanied by individual copyable widgets for Title, Price, and Hashtags for rapid multi-field pasting into Facebook Marketplace forms.

---

### 2.5 Integration with `export.py` (Card Ladder CSV Export & Download Triggers)

#### A. Export Configuration & Filtering
- **Status Filter**:
  - `CLEARED` (Default, recommended for pristine Card Ladder bulk sync)
  - `ALL` (Exports all records regardless of status)
  - `REVIEW VARIATION` / `NEEDS REVIEW` (For audit export)
- **Fuzzy Normalization Engine**: Checkbox (default `True`) to apply `normalize_player_name` and `normalize_set_name` against canonical catalogs across 22 categories.
- **Max Batch Limit**: 500 cards per CSV file.

#### B. Live 16-Column Export Preview
Before generating disk files, `app.py` converts staged records to a DataFrame via `cards_to_card_ladder_dataframe(rows, apply_normalization=True)`:
- Renders the exact 16 Card Ladder columns:
  `['Date Purchased', 'Quantity', 'Player', 'Year', 'Set', 'Variation', 'Number', 'Category', 'Condition', 'Investment', 'Estimated Value', 'Ladder ID', 'Notes', 'Date Sold', 'Sold Price', 'Image']`
- Proves zero-loss string preservation for leading zeroes in `Number` (e.g. `'001'`, `'04/102'`).
- Proves complete exclusion of 5 internal fields (`slab_serial_number`, `query`, `tags`, `back_image`, `ai_status`).

#### C. Single, Chunked, and ZIP Download Triggers
Executing `export_card_ladder_csv(db_path=active_db_path, output_path=output_path, status_filter=filter_val, max_batch_size=500)` returns `(total_rows, generated_files)`:
- **Single File Export (<= 500 cards)**:
  - Generates `CardLadder_Bulk_Upload.csv`.
  - Provides `st.download_button(label="📥 Download Card Ladder CSV", data=open(file_path, 'rb'), file_name="CardLadder_Bulk_Upload.csv", mime="text/csv")`.
- **Chunked File Export (> 500 cards)**:
  - Automatically splits into `CardLadder_Bulk_Upload_part1.csv`, `CardLadder_Bulk_Upload_part2.csv`, etc.
  - Renders individual download buttons for each chunk.
  - Packages all parts into an in-memory ZIP bundle via Python `zipfile` module for one-click bulk download:
    `st.download_button(label="📦 Download All Chunks (ZIP)", data=zip_buffer, file_name="CardLadder_Exports.zip", mime="application/zip")`.

#### D. Automated Forensic Validation
Runs `validate_card_ladder_csv(file_path)` on generated export and outputs an instant verification badge:
- `✅ Forensic Validation Passed: Exactly 16 columns, correct header order, leading zeros intact, zero internal fields leaked.`

---

## 3. UI Layout & State Architecture for `app.py`

### 3.1 Page Topology & Visual Hierarchy

```
+---------------------------------------------------------------------------------------------------+
| 🃏 SPORTS CARD ECOSYSTEM HUB                                        [🟢 API Bridge: 8002] [⚙️ DB] |
| Master 21-Variable Ingestion, Visual Staging & Card Ladder Export Engine                          |
+---------------------------------------------------------------------------------------------------+
|  [ 📊 Staged Cards: 42/500 ]  [ 💵 Investment: $1,450.00 ]  [ 📈 Est Value: $3,210.00 ]  [ +121.4% ] |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ Tab 1: 📊 Staging Area ]  [ Tab 2: 👁️ Vision ]  [ Tab 3: 🕷️ Scraper ]  [ Tab 4: 📢 Sales ]  [ Tab 5: 💾 Export ]
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | Search: [ Luka          ] | Status: [ ALL v ] | Category: [ Basketball v ] | Sort: [ ID DESC ] |  |
|  +---------------------------------------------------------------------------------------------+  |
|  | ID | Player       | Year | Set          | Var          | #   | Cond   | Value   | Status  | Actions| |
|  |----|--------------|------|--------------|--------------|-----|--------|---------|---------|--------| |
|  | 1  | Luka Dončić  | 2020 | Panini Prizm | Silver Prizm | 75  | PSA 10 | $350.00 | CLEARED | [Edit] | |
|  | 2  | Patrick M... | 2017 | Donruss      | The Rookies  | TR10| Raw    | $180.00 | REVIEW  | [Clear]| |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

### 3.2 Session State Schema (`st.session_state`)

```python
# Core State Variables
st.session_state.setdefault("db_path", DEFAULT_DB_PATH)
st.session_state.setdefault("selected_card_id_for_sales", None)
st.session_state.setdefault("last_export_files", [])
st.session_state.setdefault("active_tab_index", 0)
st.session_state.setdefault("mock_vision_enabled", False)
st.session_state.setdefault("mock_sales_enabled", False)
```

---

## 4. Edge Cases, Guardrails & Defensive Strategies

1. **Database Path Isolation in Multi-User / Testing Scenarios**:
   - `app.py` resolves `db_path` via environment variable `PORTFOLIO_DB_PATH` or sidebar override, ensuring automated test harnesses can point Streamlit at temporary in-memory/tempfile SQLite databases without contaminating `portfolio.db`.
2. **Circuit Breaker Enforcement**:
   - Every ingestion module checks `database.check_circuit_breaker(db_path)`. If staging >= 500, ingestion triggers display warning notices and enforce batch chunking.
3. **Diacritic & Character Encoding Safety**:
   - Full UTF-8 enforcement across SQLite (`PRAGMA encoding = 'UTF-8'`), FastAPI JSON serialization, and CSV export (`encoding='utf-8'`), ensuring accented names (`Luka Dončić`, `Ronald Acuña Jr.`) render with zero mojibake.
4. **Memory Management on Bulk File Uploads**:
   - Streamlit file upload byte streams are processed sequentially and garbage collected, preventing high memory consumption during large image batch uploads.

---

## 5. Verification & Testing Strategy

To verify the Milestone 5 implementation, the following test matrix will be executed:
- **Test 1: App Launch & Syntax Verification**: Verify `app.py` imports all modules without errors and initializes FastAPI background server.
- **Test 2: CRUD & Filter Verification**: Prove insertion, query filtering, status updates, and summary metrics calculation.
- **Test 3: AI Vision Staging Verification**: Process image batch in mock mode and verify sequential `[Parent]-[Child]` tracking notes in SQLite.
- **Test 4: Scraper Checklist Expansion**: Ingest static Beckett fixture, expand across 3 parallels, and verify resulting cards in staging.
- **Test 5: Sales Listing Generation**: Generate copy for staged card and verify 6-section structure, character limits, and hashtag count.
- **Test 6: Card Ladder 16-Column Export & Forensic Validation**: Export staged cards to CSV, verify chunking logic, and run `validate_card_ladder_csv`.
- **Test 7: Multi-Threaded Concurrency Test**: Concurrently execute Streamlit queries and FastAPI background captures to prove zero SQLite lock errors.
