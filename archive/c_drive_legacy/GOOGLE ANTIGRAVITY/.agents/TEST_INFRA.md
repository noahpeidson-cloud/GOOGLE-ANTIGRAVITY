# E2E Test Infra: Sports Card Ecosystem Hub

## Test Philosophy
- Opaque-box, requirement-driven testing based strictly on `ORIGINAL_REQUEST.md`.
- No internal mock dependence for public interfaces.
- Deterministic fixture data for scrapers, AI vision, and database records.

## Feature Inventory & Test Coverage Goals
| # | Feature | Requirement Source | Tier 1 (Feature) | Tier 2 (Boundary) | Tier 3 (Pairwise) | Tier 4 (Scenario) |
|---|---------|-------------------|:----------------:|:-----------------:|:-----------------:|:-----------------:|
| 1 | SQLite 21-Variable Schema | ORIGINAL_REQUEST §R1 | 5 tests | 5 tests | ✓ | ✓ |
| 2 | Streamlit Hub Dashboard | ORIGINAL_REQUEST §R1 | 5 tests | 5 tests | ✓ | ✓ |
| 3 | AI Vision Ingestion | ORIGINAL_REQUEST §R2 | 5 tests | 5 tests | ✓ | ✓ |
| 4 | Beckett/Cardboard Scraper | ORIGINAL_REQUEST §R2 | 5 tests | 5 tests | ✓ | ✓ |
| 5 | Chrome Extension API Bridge | ORIGINAL_REQUEST §R3 | 5 tests | 5 tests | ✓ | ✓ |
| 6 | Sales Listing Generator | ORIGINAL_REQUEST §R3 | 5 tests | 5 tests | ✓ | ✓ |
| 7 | Fuzzy Normalization & Export | ORIGINAL_REQUEST §R4 | 5 tests | 5 tests | ✓ | ✓ |

## Test Architecture
- Test Runner: `pytest` running `sports_cards/ecosystem_hub/tests/`
- Command: `pytest -v tests/`
- Expected: All tests pass with exit code 0.

## Tiered Test Suite Structure
- **Tier 1: Feature Coverage (≥5 per feature)**
  - Schema creation, field constraints, defaults, query synthesis.
  - Scraper table parsing with multiple rows.
  - Vision mock schema validation.
  - FastAPI `/api/v1/cards/capture` endpoint responses.
  - Facebook Marketplace copy formatting.
  - CSV export creation and 16-header matching.
- **Tier 2: Boundary & Corner Cases (≥5 per feature)**
  - Leading zeroes preservation on card numbers (`001`, `04`, `RC-05`).
  - Graded (`PSA 10`) vs Raw (`'Raw'`) condition validation; cert numbers on raw cards rejected.
  - Category validation against exact 22 enum members.
  - 500-card batch splitting / circuit breaker.
  - Empty checklists or malformed HTML graceful handling.
  - Special characters and punctuation in player names.
- **Tier 3: Cross-Feature Combinations**
  - Scraper $\rightarrow$ Database insertion $\rightarrow$ Normalization $\rightarrow$ CSV Export.
  - Chrome Extension API $\rightarrow$ Database insertion $\rightarrow$ Sales listing generation.
  - AI Vision $\rightarrow$ Flagging `REVIEW VARIATION` $\rightarrow$ Streamlit filter $\rightarrow$ Manual clearance $\rightarrow$ CSV export.
- **Tier 4: Real-World Scenarios**
  - Scenario 1: Bulk ingestion of a 100-card modern set with parallel variations.
  - Scenario 2: Vintage raw card ingestion with OCR mock and Card Ladder export.
  - Scenario 3: Graded PSA slab capture from Chrome Extension with Facebook Marketplace listing generation.
  - Scenario 4: Full lifecycle audit: Ingest $\rightarrow$ Stage $\rightarrow$ Review $\rightarrow$ Sales $\rightarrow$ Export $\rightarrow$ Verification.
- **Tier 5: Adversarial Hardening (Phase 2 of final milestone)**
  - Fuzzing card numbers, malformed inputs, SQL injection attempts, schema boundary violations.
