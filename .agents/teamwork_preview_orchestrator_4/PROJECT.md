# Project: Gemini Notebook MCP Extractor

## Architecture
- Target Directory: `d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor`
- Transport Layer: Dual-mode client interface (`client.py`) supporting:
  1. `MCPStdioClient`: Spawns `sys.executable -m notebooklm_tools.mcp.server` via `mcp.client.stdio.stdio_client` and calls `notebook_get`, `source_get_content`, and `note`.
  2. `DirectClient`: Directly calls `notebooklm_tools.services` in-process using cached auth tokens.
- Data Layer: Pydantic v2 data models (`schemas.py`) ensuring strict validation, type safety, and clean JSON serialization.
- CLI Entrypoint: `extractor.py` using absolute imports (R16), pre-flight dependencies check (R18), fail-fast validation (R38), and flexible options (`--notebook-id`, `--output`, `--dry-run`, `--limit`, `--format`, `--concurrency`).
- Target Dataset: Notebook `4b52cc67-9f81-4e85-a024-5f06756991ab` ("Dual-Loop Control and Agentic Orchestration in Cognitive Architectures"), containing 61 sources and 1 research note.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Dependencies Pre-flight | `requirements.txt` specifying exact versions for `mcp`, `notebooklm-mcp-cli`, `pydantic`, `httpx`, `pytest` | M1 | Survey 3 / R18 |
| 2 | Pydantic v2 Data Schemas | Structured data models for NotebookMetadata, ExtractedSource, ExtractedNote, Provenance, and NotebookExtractionPayload | M1 | Survey 3 / R2 |
| 3 | MCP Stdio Client Adapter | Async context manager connecting to MCP server via stdio JSON-RPC | M1 | Survey 1 & 3 / R1 |
| 4 | Direct Service Client Adapter | In-process high-speed fallback client using `notebooklm_tools.services` | M1 | Survey 1 & 3 / R1 |
| 5 | Authentication & Fail-Fast | Fail-fast verification of cached auth tokens with remediation message | M1 | Survey 1 & 3 / R38 |
| 6 | Bulk Source Extraction Pipeline | Concurrency-controlled extraction of all 61 sources with full text and error isolation | M1 | Survey 2 & 3 / R1 |
| 7 | Note Extraction Pipeline | Extraction of all notes with titles, content, and previews | M1 | Survey 2 & 3 / R1 |
| 8 | Structured JSON Output Writer | UTF-8 formatted JSON/JSONL serialization with indentation and atomic file write | M1 | Survey 2 & 3 / R2 |
| 9 | CLI Command Interface | CLI entrypoint with `--notebook-id`, `--output`, `--dry-run`, `--limit`, `--format`, `--transport`, `--concurrency` | M1 | Survey 3 / R3 |
| 10 | Deterministic Unit & Mock Tests | Pytest test suite with loud assertions (R2) covering schemas, mock transport, and edge cases | M2 | Survey 3 / R2 |
| 11 | Live Dry-Run Validation | Test verifying extraction of subset of items (`--dry-run` / `--limit 2`) without full payload | M2 | Acceptance Criteria |
| 12 | Live 61-Item E2E Verification | End-to-end extraction and JSON verification of all 61 sources and notes | M2 | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Extractor Engine Implementation | Implement `requirements.txt`, `schemas.py`, `client.py`, `extractor.py`, `README.md` | none | IN_PROGRESS |
| M2 | Test Suite & E2E Verification | Implement unit tests, dry-run integration test, and full 61-source E2E verification | M1 | PLANNED |

## Interface Contracts
### `schemas.py` Data Contracts
- `NotebookMetadata`: `id: str`, `title: str`, `url: str`, `source_count: int`, `emoji: Optional[str]`
- `ExtractedSource`: `id: str`, `title: str`, `source_type: str`, `url: Optional[str]`, `char_count: int`, `content: Optional[str]`, `status: str`, `error: Optional[str]`
- `ExtractedNote`: `id: str`, `title: str`, `content: str`, `preview: Optional[str]`
- `ExtractionProvenance`: `extracted_at: str`, `extractor_version: str`, `transport: str`, `total_sources: int`, `total_notes: int`, `is_dry_run: bool`, `limit_applied: Optional[int]`
- `NotebookExtractionPayload`: `schema_version: str`, `metadata: NotebookMetadata`, `sources: List[ExtractedSource]`, `notes: List[ExtractedNote]`, `provenance: ExtractionProvenance`

### `client.py` Protocol Contract
- `NotebookClientProtocol`:
  - `async def connect() -> None`
  - `async def disconnect() -> None`
  - `async def get_notebook(notebook_id: str) -> Dict[str, Any]`
  - `async def get_notes(notebook_id: str) -> List[Dict[str, Any]]`
  - `async def get_source_content(source_id: str) -> Dict[str, Any]`

## Code Layout
```
d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor\
├── __init__.py
├── requirements.txt
├── schemas.py
├── client.py
├── extractor.py
├── README.md
├── tests/
│   ├── __init__.py
│   ├── test_schemas.py
│   ├── test_client_mock.py
│   ├── test_extractor_dry.py
│   └── test_extractor_full.py
└── extracted_notebook_data.json
```
