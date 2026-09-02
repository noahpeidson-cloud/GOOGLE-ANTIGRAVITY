# E2E Test Infra: Master Dashboard UI Overhaul

## Test Philosophy
- Opaque-box, requirement-driven, and backward-compatible.
- Verified against existing test suites and DOM assertion tests.

## Feature Inventory & Test Mapping
| # | Feature | Test Module | Verification Method |
|---|---------|-------------|---------------------|
| 1 | Desktop-Class CSS Grid Layout | `test_lighthouse_and_standards.py`, `test_pwa_dom_and_scrubber.py` | DOM element checks, CSS grid classes |
| 2 | Slate Dark Mode Palette | `test_lighthouse_and_standards.py` | CSS variable presence & contrast |
| 3 | 720p Proxy Viewer Component | `test_pwa_dom_and_scrubber.py`, `test_e2e_master_dashboard.py` | `#proxy-video`, playback controls |
| 4 | HUD Safe Zone Overlays (YT Shorts & TikTok) | Custom DOM verification / Challenger tests | SVG safe zone bounds, 900x1270, 920x1310 |
| 5 | Multi-Track Timeline & Waveform | `test_pwa_dom_and_scrubber.py` | `#timeline-scrubber`, canvas waveform, playhead |
| 6 | Context-Aware Metadata Panel | `test_adversarial_pwa_dom.py` | `#festival-input`, `#artist-input`, `#metadata-section` |
| 7 | FastAPI Fetch API Wiring | `test_remote_trigger_endpoints.py`, `test_remote_trigger.py` | Endpoints, payloads, status polling, approvals |
| 8 | 59.00s Content ID Amber Alert | Custom DOM verification / Challenger tests | Scrubber drag duration > 59.00s toast trigger |
| 9 | TikTok Ghost-Linking Audio Badge | Custom DOM verification / Challenger tests | Badge element presence and armed state |
| 10| Dual-File Synchronization | `test_pwa_dom_and_scrubber.py` | Exact string / hash match of index.html and static/index.html |

## Execution Commands
- Full Test Suite: `python -m unittest discover tests` (run from `content_creation`)
- Specific Target: `python -m unittest tests/test_remote_trigger_endpoints.py tests/test_remote_trigger.py tests/test_pwa_dom_and_scrubber.py tests/test_lighthouse_and_standards.py tests/test_adversarial_pwa_dom.py tests/test_e2e_master_dashboard.py`
