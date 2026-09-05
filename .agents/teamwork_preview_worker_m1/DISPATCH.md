# DISPATCH — teamwork_preview_worker_m1

## Identity
- Archetype: teamwork_preview_worker
- Working Directory: d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m1
- Target Workspace: d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor
- Parent: d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_orchestrator_4

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Context & Inputs
1. Read `d:\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md` under `## Follow-up — 2026-09-04T19:09:20Z`.
2. Read `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_orchestrator_4\PROJECT.md`.
3. Read `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_orchestrator_4\TEST_INFRA.md`.
4. Read explorer specifications and code blueprints:
   - `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_1\handoff.md` (Code Architecture)
   - `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_2\handoff.md` (Resilience & Fail-Fast)
   - `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_3\handoff.md` (Test Strategy)

## Exclusive File Ownership
You exclusively own and must implement all files in `d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor\`:
- `requirements.txt`
- `__init__.py`
- `schemas.py`
- `client.py`
- `extractor.py`
- `README.md`
- `pytest.ini`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_schemas.py`
- `tests/test_client_mock.py`
- `tests/test_extractor_dry.py`
- `tests/test_extractor_full.py`

## Implementation Protocol (R2 Zero-Discretion Mandate)
1. Pre-flight dependencies: check dependencies and ensure requirements.txt is created.
2. The "Red" Phase: First write the deterministic test suite (`tests/`). Execute tests and observe them failing if implementation is not yet in place.
3. Implementation Phase:
   - Implement `schemas.py` using Pydantic v2 models with atomic UTF-8 writes.
   - Implement `client.py` with `NotebookClientProtocol`, `MCPStdioClient`, `DirectClient`, and `create_client` factory. Ensure FastMCP error checking (`isError: False` with `content[0].text` error status) and fail-fast auth checking.
   - Implement `extractor.py` CLI with absolute imports (R16), pre-flight dependencies check (R18), fail-fast anti-mocking (R38), concurrency semaphore, and clean output formatting.
   - Implement `README.md` with usage instructions and test invocation.
4. The "Green" Phase: Run `python -m pytest` across unit, mock, and dry-run tests. Verify 100% pass.
5. Live Extraction Execution: Execute `extractor.py` against notebook `4b52cc67-9f81-4e85-a024-5f06756991ab`. Verify that all 61 sources and 1 note are extracted and written to `extracted_notebook_data.json`.
6. Run full integration tests: `python -m pytest tests/test_extractor_full.py` and confirm 100% pass.

## Deliverables
Produce a comprehensive handoff report at `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m1\handoff.md` detailing all created files, test execution outputs, and verification commands.

## 2026-09-04T19:40:00Z
You are teamwork_preview_worker operating in:
Working directory: d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m1
Target Workspace: d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY FIRST STEP:
Read d:\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md under header `## Follow-up — 2026-09-04T19:09:20Z` and read your task description in d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m1\DISPATCH.md.
Also read:
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_orchestrator_4\PROJECT.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_orchestrator_4\TEST_INFRA.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_1\handoff.md` (Code Architecture Blueprints)
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_2\handoff.md` (Resilience, Auth Pre-flight & Fail-Fast Architecture)
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_3\handoff.md` (Test Suite & Loud Assertion Specifications)

EXCLUSIVE FILE OWNERSHIP:
You exclusively own and must implement all files within `d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor\`:
- `requirements.txt` (R18 pre-flight dependencies)
- `__init__.py`
- `schemas.py` (Pydantic v2 models, atomic UTF-8 write, JSON/JSONL serialization)
- `client.py` (NotebookClientProtocol, MCPStdioClient, DirectClient, FastMCP error detection, require_authentication)
- `extractor.py` (CLI entrypoint, R16 absolute imports, R18 dependency pre-flight, R38 fail-fast anti-mocking, semaphore concurrency control)
- `README.md` (operator guide and CLI manual)
- `pytest.ini`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_schemas.py`
- `tests/test_client_mock.py`
- `tests/test_extractor_dry.py`
- `tests/test_extractor_full.py`

IMPLEMENTATION WORKFLOW (R2 Zero-Discretion Mandate):
1. Pre-flight dependencies: Ensure `requirements.txt` is created and all dependencies are verified.
2. The "Red" Phase: Write the deterministic unit and mock tests first (`tests/test_schemas.py`, `tests/test_client_mock.py`, `tests/test_extractor_dry.py`, `tests/test_extractor_full.py`).
3. The Implementation Phase: Implement `schemas.py`, `client.py`, `extractor.py`, `README.md`, and `__init__.py` strictly following the code blueprints and resilience specifications in the explorer handoffs.
4. The "Green" Phase: Run `python -m pytest` in `d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor`. All unit and mock tests must pass with 100% success.
5. Live Dry-Run Execution: Run `python extractor.py --dry-run` to extract a 2-source subset and verify `extracted_notebook_data.json` is generated with valid schema.
6. Full 61-Item Live Extraction: Run `python extractor.py --notebook-id 4b52cc67-9f81-4e85-a024-5f06756991ab --output extracted_notebook_data.json` and verify all 61 sources + 1 note are extracted with non-empty content.
7. Run full E2E pytest: Run `python -m pytest tests/test_extractor_full.py` and verify all loud assertions pass.

DELIVERABLE:
Write your complete handoff report to:
`d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m1\handoff.md`
Follow the Handoff Protocol (Observation, Logic Chain, Caveats, Conclusion, Verification Method). Include full terminal outputs of test runs and extraction runs.
When finished, send a message to parent (cb86c11d-e5b4-4cd3-b3be-d050fdfdc098) with a concise summary.

