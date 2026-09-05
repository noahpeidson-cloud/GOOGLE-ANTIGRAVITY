# E2E Test Infra: Gemini Notebook MCP Extractor

## Test Philosophy
- Opaque-box, requirement-driven, and unit test coverage.
- Zero-Discretion Mandate (R2): Deterministic loud assertions, no subjective passes.
- Methodology: Unit testing with mock MCP payloads + Live dry-run subset extraction + Full 61-source end-to-end extraction.

## Feature Inventory & Test Mapping
| # | Feature | Source | Tier 1 (Unit) | Tier 2 (Boundary) | Tier 3 (Integration) | Tier 4 (E2E) |
|---|---------|--------|:-------------:|:-----------------:|:--------------------:|:------------:|
| 1 | Dependencies Pre-flight | R18 | ✓ | ✓ | - | - |
| 2 | Pydantic Schemas | R2 | ✓ | ✓ | - | - |
| 3 | MCP Stdio Client | R1 | ✓ | ✓ | ✓ | - |
| 4 | Direct Service Client | R1 | ✓ | ✓ | ✓ | - |
| 5 | Auth & Fail-Fast | R38 | ✓ | ✓ | ✓ | - |
| 6 | Bulk Source Extraction | R1 | - | ✓ | ✓ | ✓ |
| 7 | Note Extraction | R1 | - | ✓ | ✓ | ✓ |
| 8 | Structured JSON Output | R2 | ✓ | ✓ | ✓ | ✓ |
| 9 | CLI Flags & Dry-Run | R3 | ✓ | ✓ | ✓ | - |
| 10 | 61-Item Extraction Completeness | Acceptance Criteria | - | - | - | ✓ |

## Test Architecture
- Test runner: `pytest`
- Test suite directory: `d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor\tests\`
- Tests:
  1. `test_schemas.py`: Verifies Pydantic v2 models, serialization, required fields, and validation errors with loud assertions.
  2. `test_client_mock.py`: Verifies `MCPStdioClient` and `DirectClient` behavior with mocked responses, error isolation, and network failure modes.
  3. `test_extractor_dry.py`: Runs `extractor.py --dry-run` or `--limit 2` against live notebook or mocks to verify CLI parsing, partial extraction, and valid JSON output.
  4. `test_extractor_full.py`: Runs full extraction against notebook `4b52cc67-9f81-4e85-a024-5f06756991ab`, verifies resulting JSON file exists, contains exactly 61 sources with non-empty content and 1 note, and parses against `NotebookExtractionPayload`.

## Coverage Thresholds
- All unit tests pass with exit code 0.
- All acceptance criteria verified live.
- Zero integrity violations.
