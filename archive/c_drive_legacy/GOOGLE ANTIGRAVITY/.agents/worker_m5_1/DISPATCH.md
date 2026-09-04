## 2026-08-23T22:04:05Z

You are a teamwork_preview_worker subagent.
Working Directory: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\worker_m5_1
Project Code Directory: g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub
Authoritative Request: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md
Project Blueprint: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\PROJECT.md
Parent Orchestrator Conv ID: 0c586af6-e90b-4330-8029-7be97c7c607c

Explorer Analysis Reports:
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m5_1\analysis.md`
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m5_2\analysis.md`
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m5_3\analysis.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Milestone 5 Scope & Assigned Files:
You exclusively own and will create/verify the following files in `sports_cards/ecosystem_hub/`:
1. `app.py`:
   - `st.set_page_config(page_title="Sports Card Ecosystem Hub", layout="wide", page_icon="🃏")`.
   - Top KPI Metrics Bar: Total Cards, Total Investment ($), Total Estimated Value ($), Pending AI Reviews (`REVIEW VARIATION` + `NEEDS REVIEW`), Cleared Cards.
   - Tab 1: 📊 Portfolio Staging Area
     - Filter by Category (22 enums), AI Status, Year, and live text Search Query.
     - Interactive DataFrame with card details.
     - Expanders for card inspection, single card edit/update form (with automatic query calculation), status badge toggle, and card deletion.
     - Manual card entry form.
   - Tab 2: 📸 AI Vision Ingestion
     - File Uploader for Card Front and Back photos.
     - Gemini visual analysis preview using `vision_ingest.py` (`extract_card_from_image` with offline mock fallback).
     - Form to review and commit extracted card to SQLite `portfolio.db`.
   - Tab 3: 📋 Checklist Scraper
     - Beckett / Cardboard Connection URL or raw HTML paste box.
     - Category, Set, Year selection.
     - Parallel variation checkboxes (Base, Silver Prizm, Red /99, Gold /10, etc.).
     - "Parse & Bulk Ingest Checklist" button with progress reporting and batch count.
   - Tab 4: 🏷️ Sales Copy Generator
     - Card selector from database.
     - Asking price input.
     - "Generate SEO Facebook Marketplace Listing" button invoking `sales_generator.py`.
     - Structured listing copy display with one-click copy button.
   - Tab 5: 📤 Card Ladder CSV Export
     - Status filter selection (`CLEARED`, `ALL`, specific statuses).
     - Fuzzy normalization toggle.
     - "Export to Card Ladder CSV" button invoking `export.py`.
     - Download buttons for generated CSV(s) / ZIP, and a live preview of the 16 columns showing leading zero preservation on card numbers.
   - Tab 6: 🌐 API Bridge & System Health
     - Background FastAPI server runner cached via `@st.cache_resource` calling `start_api_server_thread`.
     - Live port 8002 status indicator, health metrics, and Chrome Extension payload ingestion documentation.
2. `tests/test_streamlit_app.py`:
   - Comprehensive headless test suite leveraging `streamlit.testing.v1.AppTest` and direct module test fixtures covering all 6 tabs, KPI rendering, data mutations, and export downloads without syntax or runtime exceptions.
