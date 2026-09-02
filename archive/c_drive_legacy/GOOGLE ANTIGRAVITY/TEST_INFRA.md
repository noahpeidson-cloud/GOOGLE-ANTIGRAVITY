# E2E Test Infra: Omnichannel Triage Hub

## Test Philosophy
- Opaque-box, requirement-driven testing. No dependency on implementation internal design.
- Methodology: 4-Tier Testing (Feature Coverage, Boundary & Corner Cases, Cross-Feature Combinations, Real-World Workloads) + R4 Zero-Waste Auditing.

## Feature Inventory
| # | Feature | Source | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|--------|:------:|:------:|:------:|:------:|
| 1 | React Vite Scaffolding & Render | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 2 | Tailwind Two-Column UI Mockup Replica | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 3 | Phone Link Feed & Live Tagging Badges | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 4 | Collision Resolution Queue & Actions | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 5 | FastAPI Server Boot & Health Endpoint | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 6 | Trigger ADB Pull Endpoint & Dual Engine | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 7 | Capture Screen Endpoint & Frame Output | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 8 | CORS Policy for Localhost:5173 | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 9 | Firebase Data Connect Schema (video_tags) | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 10 | Data Connect SDK & GraphQL Query Hooks | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 11 | UI Button -> FastAPI Trigger Integration | ORIGINAL_REQUEST Criteria | 5 | 5 | ✓ | ✓ |
| 12 | Zero-Waste Memory Leak Audit (0 detached nodes) | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ | ✓ |
| 13 | Zero-Waste a11y Audit (WCAG AA) | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- Test Runner: Python `pytest` with `httpx` and `playwright` + Node.js Jest / Puppeteer / DevTools scripts
- Location: `g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/tests/`
- Command: `pytest tests/e2e_integration_test.py`
- Pass/Fail semantics: 100% tests pass, exit code 0.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | End-to-End ADB Pull Trigger from React UI | F1, F2, F5, F6, F8, F11 | Medium |
| 2 | Real-time Phone Link Screen Capture & Tag Ingestion | F3, F7, F8, F9, F10 | High |
| 3 | Side-by-Side Resolution Collision Decision & Resolution | F4, F6, F9, F10 | Medium |
| 4 | Offline / Disconnected ADB Fallback Execution | F5, F6, F7, F11 | Medium |
| 5 | Rapid UI Interaction Stress & Memory Profiling | F1, F2, F3, F4, F12, F13 | High |

## Coverage Thresholds
- Tier 1: ≥5 per feature (Total ≥ 65 tests)
- Tier 2: ≥5 boundary/corner cases per feature (Total ≥ 65 tests)
- Tier 3: Pairwise combinations of major features
- Tier 4: ≥5 realistic application scenarios
- Tier 5 (Adversarial): Challenger stress testing & leak audits
