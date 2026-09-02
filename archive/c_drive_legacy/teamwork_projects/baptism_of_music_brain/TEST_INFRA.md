# E2E Test Infra: baptism_of_music_brain

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation internals.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial + Real-World Workload Testing.
- Zero external media dependencies: All test media is procedurally generated using FFmpeg `lavfi` (testsrc2, smptebars, noise, sine).
- Mathematical verification: Output videos must programmatically satisfy visually lossless parameters via `ffprobe` (CRF 17 target bitrate, resolution preservation, aspect ratio, frame rate, audio loudness normalization to -14 LUFS).

## Feature Inventory
| # | Feature | Source (Requirement) | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|----------------------|:------:|:------:|:------:|:------:|
| 1 | Configuration & Settings | ORIGINAL_REQUEST § R1 | 5 | 5 | ✓ | ✓ |
| 2 | Pydantic v2 Data Models & Schema | ORIGINAL_REQUEST § R1 | 5 | 5 | ✓ | ✓ |
| 3 | Ingest Watcher & Win32 Locking | ORIGINAL_REQUEST § R1, § AC2 | 5 | 5 | ✓ | ✓ |
| 4 | Job State Management | ORIGINAL_REQUEST § R1 | 5 | 5 | ✓ | ✓ |
| 5 | Media Metadata Prober | ORIGINAL_REQUEST § R1, § AC1 | 5 | 5 | ✓ | ✓ |
| 6 | Gemini Omni ML Grading & Mock Engine | ORIGINAL_REQUEST § R1, § AC2 | 5 | 5 | ✓ | ✓ |
| 7 | FastAPI Control Plane & Overrides API | ORIGINAL_REQUEST § R1, § AC2 | 5 | 5 | ✓ | ✓ |
| 8 | Lossless FFmpeg Rendering Engine | ORIGINAL_REQUEST § R2, § AC1 | 5 | 5 | ✓ | ✓ |
| 9 | Filtergraph & Audio Mastering | ORIGINAL_REQUEST § R2, § AC1 | 5 | 5 | ✓ | ✓ |
| 10 | Atomic Delivery Pipeline | ORIGINAL_REQUEST § R3, § AC2 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- Test Runner: `pytest`
- Invocation: `pytest -v tests/`
- Procedural Media Generator: `tests/test_infra/media_generator.py`
- Programmatic FFprobe Verifier: `tests/test_infra/ffprobe_validator.py`
- Test Directory Layout:
  - `tests/tier1_feature/`: Isolated feature coverage unit tests (≥5 per feature)
  - `tests/tier2_boundary/`: Boundary and corner cases (in-flight locks, invalid trims, odd dimensions, silent audio)
  - `tests/tier3_pairwise/`: Pairwise cross-feature combinations
  - `tests/tier4_workload/`: Full end-to-end user journeys matching Acceptance Criteria 1 & 2
  - `tests/tier5_adversarial/`: Adversarial coverage hardening (white-box stress testing)

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Acceptance Criteria 1: Programmatic Encoding Verification | FFmpeg render, Lossless profile (`x264_crf17`), ffprobe codec/bitrate/resolution assertions | Medium |
| 2 | Acceptance Criteria 2: End-to-End File Pipeline Execution | Ingest drop -> Detection -> Mock ML decision -> Manual Override API -> FFmpeg render -> Delivery drop | High |
| 3 | Mobile 4K Landscape Ingestion with Social Portrait Reframing | 3840x2160 Ingest, ML 9:16 crop/pad EDL, color grade, loudnorm audio, delivery | High |
| 4 | Multi-Clip High-Impact EDM Highlight Reel Assembly | 3 segments with speed ramp (0.5x slow-mo), flash transition, bass boost, delivery | High |
| 5 | Incomplete ADB Copy Ingest with Win32 Lock Retry & Recovery | In-flight `.tmp` write lock simulation, lock release, pipeline recovery, delivery | High |

## Coverage Thresholds
- Tier 1: ≥5 per feature area (≥50 total)
- Tier 2: ≥5 per feature area (≥50 total)
- Tier 3: ≥10 pairwise interaction tests
- Tier 4: ≥5 realistic end-to-end application scenarios
- Total Target: ≥115 test cases
