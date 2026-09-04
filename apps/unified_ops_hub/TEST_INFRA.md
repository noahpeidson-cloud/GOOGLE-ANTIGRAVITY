# E2E Test Infra: Unified Ops Hub Media Studio

## Test Philosophy
- Opaque-box, requirement-driven testing with zero reliance on subjective agent assertions.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Combinations + Real-World End-to-End Scenarios.

## Feature Inventory
| # | Feature | Source (Requirement) | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Cross-Feature) | Tier 4 (Real-World) |
|---|---------|----------------------|:-----------------:|:-----------------:|:---------------------:|:-------------------:|
| 1 | 720p Proxy Downscaling | ORIGINAL_REQUEST §1 | 5 tests | 5 tests | ✓ | ✓ |
| 2 | Audio Peak DSP & 3 Cuts | ORIGINAL_REQUEST §1 | 5 tests | 5 tests | ✓ | ✓ |
| 3 | Headless FFmpeg Renderer | ORIGINAL_REQUEST §2 | 5 tests | 5 tests | ✓ | ✓ |
| 4 | FastAPI Render API Endpoint | ORIGINAL_REQUEST §2 | 5 tests | 5 tests | ✓ | ✓ |
| 5 | Media Studio Frontend Component | ORIGINAL_REQUEST §3 | 5 tests | 5 tests | ✓ | ✓ |
| 6 | Dashboard Navigation Integration | ORIGINAL_REQUEST §3 | 5 tests | 5 tests | ✓ | ✓ |

## Test Architecture
- **Backend Test Runner**: `pytest` (`python -m pytest tests/test_media_editor.py tests/test_ffmpeg_renderer.py -v`)
- **Frontend Test Runner**: `vitest` (`npm test` in `dashboard/`)
- **Test Case Format**: Deterministic synthetic video/audio generators, FastAPI TestClient requests, Vitest DOM testing.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Ingest raw 4K clip -> Auto-generate 720p proxy -> Detect audio peak -> Load in Media Studio -> Apply text overlay -> Render 9:16 vertical MP4 | F1, F2, F3, F4, F5, F6 | High |
| 2 | Ingest clip with zero audio (silent) -> Fallback to default in-point -> Switch to Cinematic cut (16:9) -> Render 16:9 widescreen MP4 | F1, F2, F3, F4, F5 | Medium |
| 3 | Ingest short 3-second clip -> Boundary duration clamping -> Trim to [1.0s, 2.5s] -> Render with escaped special characters overlay | F1, F3, F4, F5 | High |

## Coverage Thresholds
- Tier 1: ≥5 per feature (Total ≥ 30)
- Tier 2: ≥5 per feature boundary (Total ≥ 30)
- Tier 3: Pairwise combinations across aspect ratios, audio levels, durations, overlays
- Tier 4: Realistic E2E pipeline workflows
