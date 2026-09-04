# DISPATCH

## 2026-08-24T03:44:04Z
You are the Project Orchestrator (teamwork_preview_orchestrator).

Your working directory is:
g:\My Drive\GOOGLE ANTIGRAVITY\.agents\orchestrator_12

The project root / code working directory is:
g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub

Authoritative user request file:
g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md

Task summary:
Build a robust, omnichannel "Sports Card Ecosystem" local web application using Streamlit and SQLite. The system acts as a central hub that accepts ingestion from 4 distinct pipelines (AI Vision photo analysis, Beckett bulk checklists, a Chrome extension bridge, and a sales listing generator), formatting all data into a strict 21-variable schema for Card Ladder CSV export.

Requirements:
1. R1. The Central Hub (Streamlit + SQLite): Streamlit dashboard as visual staging area connected to SQLite database (portfolio.db) strictly enforcing the 21-variable Card Ladder schema defined in workspace rules.
2. R2. The Ingestion Pipelines (AI Vision & Scraper): Process local card images using Gemini Multimodal API to extract details. Separate web scraper module (BeautifulSoup/requests) to parse set checklists from Beckett or Cardboard Connection for bulk checkbox ingestion.
3. R3. API Bridge & Sales Generator: Local FastAPI endpoint (or Streamlit equivalent) to receive POST payloads from a Chrome Extension. Sales module reading a row from DB using Gemini to generate SEO-optimized Facebook Marketplace listing.
4. R4. Export Pipeline: Pandas-driven export reading SQLite DB, performing fuzzy string normalization on player/set names, and exporting pristine CardLadder_Bulk_Upload.csv with no leading zeros dropped.

Acceptance Criteria:
- Central Hub: Running `streamlit run app.py` launches UI on localhost without errors. Python test script inserts mock 21-variable row into `portfolio.db` and retrieves it.
- Ingestion: Test script pointing scraper at static HTML checklist returns structured list of at least 3 cards. AI Vision module mock test takes image path and returns JSON matching 21-variable schema.
- Export: Export function generates .csv from DB. Generated CSV contains exactly the 16 headers required by Card Ladder, preserving leading zeros.
