## 2026-08-24T05:23:46Z

You are a teamwork_preview_test_writer subagent.
Working Directory: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\test_writer_m6_1
Project Code Directory: g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub
Authoritative Request: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md
Project Blueprint: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\PROJECT.md
Test Blueprint: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\TEST_INFRA.md
Parent Orchestrator Conv ID: 0c586af6-e90b-4330-8029-7be97c7c607c

Milestone: Milestone 6 - Full Opaque-Box E2E Acceptance Test Suite (Tiers 1-4)
Scope & Assigned File:
You exclusively own and will create:
`sports_cards/ecosystem_hub/tests/test_e2e_acceptance.py`

Task:
Implement a comprehensive, deterministic, opaque-box E2E test suite strictly testing all acceptance criteria from `ORIGINAL_REQUEST.md`:
1. **Tier 1 - Central Hub Acceptance**:
   - Programmatic verification that `app.py` compiles and initializes without errors.
   - Test inserting a mock 21-variable row into `portfolio.db` and retrieving it, verifying all 21 fields, 22 category check constraints, types, defaults, and query synthesis.
2. **Tier 2 - Ingestion Acceptance**:
   - Scraper Acceptance: Pointing `scraper_ingest.py` at static HTML checklist fixture (`fixtures/beckett_sample.html`) returns a structured list of at least 3 cards with card numbers, player names, and team/notes.
   - AI Vision Acceptance: Calling `vision_ingest.py` with mock image path returns a dictionary/schema matching the 21-variable schema.
3. **Tier 3 - API Bridge & Sales Listing Acceptance**:
   - Chrome Extension POST payload capture via `api.py` endpoint `/api/v1/cards/capture` successfully persists to DB with sequential tracking notes.
   - Sales listing generator produces complete Facebook Marketplace listing with title < 100 chars, price, bullet specs, condition disclaimer, and 6-8 hashtags.
4. **Tier 4 - Export Pipeline Acceptance**:
   - Export function generates `CardLadder_Bulk_Upload.csv` from database.
   - Generated CSV contains exactly the 16 headers required by Card Ladder in the exact specified order.
   - Preserves leading zeros on card numbers (e.g. `'01'`, `'007'`, `'000'`) verified via raw byte inspection and pandas `read_csv(dtype=str)`.
   - 500-card batch chunking verified.

Execution:
- Run `pytest sports_cards/ecosystem_hub/tests/test_e2e_acceptance.py -v`.
- Run full repo suite `pytest sports_cards/ecosystem_hub/tests/ -v`.
- Verify all pass with 0 failures.

Deliverable:
Write report to `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\test_writer_m6_1\changes.md` and `handoff.md`.
Use `send_message` when done.
