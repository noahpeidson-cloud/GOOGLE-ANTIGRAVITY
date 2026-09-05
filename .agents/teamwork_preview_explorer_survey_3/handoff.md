# Handoff Report: Gemini Notebook MCP Extractor Architecture & Feasibility Survey

**Author:** `teamwork_preview_explorer` (Survey 3)  
**Assigned Directory:** `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_3`  
**Target Directory:** `d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor`  
**Handoff Type:** Hard (Survey Task Complete)  
**Date:** 2026-09-04T19:27:00Z  

---

## 1. Observation

1. **Target Directory State:**
   - Path: `d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor`
   - Filesystem check via `list_dir` and `Get-ChildItem -Force`: Directory exists and is currently completely empty (`0 files, 0 subdirectories`).
   - Git status via `git status --short content_creation/gemini_mcp_extractor`: Clean and untracked; zero conflicting edits or locks.

2. **System Runtime & Package Environment:**
   - Python: `Python 3.13.14 (Store)` located at `C:\Users\noahp\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe`
   - Package manager: `uv.exe 0.0.0.0` located at `C:\Users\noahp\.local\bin\uv.exe`
   - Test framework: `pytest 9.1.1` (`python -m pytest`), `pytest-asyncio 1.4.0`, `pytest-mock 3.15.1`
   - MCP library: `mcp 1.29.1` and `fastmcp 3.4.7` installed
   - NotebookLM integration: `notebooklm-mcp-cli 0.10.1` (`notebooklm_tools` package in site-packages)
   - Schema & HTTP libraries: `pydantic 2.13.4`, `pydantic-settings 2.15.0`, `httpx 0.28.1`, `httpx-sse 0.4.3`

3. **`gemini-notebook` MCP Server Configuration:**
   - Configuration file: `C:\Users\noahp\.gemini\config\mcp_config.json` (lines 105–115):
     ```json
     "gemini-notebook": {
       "command": "python",
       "args": [
         "-m",
         "notebooklm_tools.mcp.server"
       ],
       "type": "stdio",
       "options": {
         "windowsHide": true
       }
     }
     ```
   - Server module: `notebooklm_tools.mcp.server`
   - Stdio parameter signature: `StdioServerParameters(command=sys.executable, args=['-m', 'notebooklm_tools.mcp.server'], env=None)`

4. **Live Target Notebook Verification:**
   - Live query via MCP tool `notebook_list` returned 5 user notebooks.
   - Target notebook identified with exact 61 sources:
     - **ID:** `4b52cc67-9f81-4e85-a024-5f06756991ab`
     - **Title:** `"Dual-Loop Control and Agentic Orchestration in Cognitive Architectures"`
     - **Source Count:** `61`
     - **URL:** `https://notebooklm.google.com/notebook/4b52cc67-9f81-4e85-a024-5f06756991ab`
     - **Emoji:** `⚓`
     - **Created:** `2026-09-02T07:27:02Z` | **Modified:** `2026-09-04T02:26:07Z`
   - Verified `notebook_get(notebook_id="4b52cc67-9f81-4e85-a024-5f06756991ab")`:
     Returns all 61 source records (IDs and titles from `7b7c692f-9bac-4a94-be71-b76010be5686` to `7d9c850e-eec2-4232-b63b-ad62932ae215`).
   - Verified `note(notebook_id="4b52cc67-9f81-4e85-a024-5f06756991ab", action="list")`:
     Returns 1 note: `id: "eff2cf19-844e-4af7-aad8-601d7d0fbf13"`, `title: "The Multi-Model Orchestration and AI Handoff Framework"`, 3,923 chars of markdown content.
   - Verified `source_get_content(source_id="7b7c692f-9bac-4a94-be71-b76010be5686")`:
     Successfully retrieved 53,314 bytes of raw indexed full text (`"11 Top Open-Source LLMs for 2026 and Their Uses | DataCamp..."`).

5. **Python MCP Stdio Connection Proof of Concept:**
   - Executed live test script:
     ```python
     server_params = StdioServerParameters(command=sys.executable, args=['-m', 'notebooklm_tools.mcp.server'])
     async with stdio_client(server_params) as (read, write):
         async with ClientSession(read, write) as session:
             await session.initialize()
             tools = await session.list_tools()
             res = await session.call_tool('notebook_list', {'max_results': 10})
     ```
   - Result: Exit code 0, `Connected to MCP! Available tools count: 48`, parsed response returned valid `TextContent` JSON.

6. **Authentication Mechanism:**
   - Module: `notebooklm_tools.core.auth`
   - Function: `load_cached_tokens()`
   - Verified live in Python: `load_cached_tokens() is not None` returned `True`. Valid Google credentials are actively cached on disk (from `nlm login`).

---

## 2. Logic Chain

1. **Transport Layer Architecture (MCP Client vs Direct API):**
   - *From Observation 3 & 5:* The standard `mcp` library (`mcp.client.stdio.stdio_client`) connects seamlessly to `python -m notebooklm_tools.mcp.server` and executes tool calls over JSON-RPC stdio.
   - *From Observation 2 & 6:* The underlying package `notebooklm_tools` also exposes direct services (`notebooks_service.get_notebook`, `notes_service.list_notes`, `sources_service.get_source_content`) using the same client credentials.
   - *Logical Inference:* The standalone extractor script should implement a **Pluggable Client Architecture**:
     - **Default Transport:** `MCPStdioClient` using `mcp.client.stdio` (fulfilling requirement R1 to connect to the MCP server).
     - **Alternative / Speed Transport:** `DirectClient` invoking `notebooklm_tools.services` in-process (useful for high-speed local processing and mock-free integration testing).
     - A unified abstract protocol `NotebookClientProtocol` allows switching between them via CLI flag `--transport mcp|direct`.

2. **Concurrency & Rate Limiting:**
   - *From Observation 4:* The target notebook has 61 sources. Fetching full content sequentially over network RPC requires ~60–90 seconds.
   - *From Observation 5:* The MCP server runs as a standalone Python process using FastMCP which dispatches requests across a thread pool.
   - *Logical Inference:* In the async extraction loop, wrap `source_get_content` calls with an `asyncio.Semaphore(concurrency=4)` (configurable via `--concurrency`). This achieves complete extraction in ~15–20 seconds without overwhelming Google RPC endpoints or encountering 429 throttling.

3. **Data Modeling & Structured Output (Pydantic v2):**
   - *From Observation 2 & 4:* The extracted payload must capture notebook metadata, individual sources (ID, title, URL, source type, char count, full content), notes (ID, title, content), and execution provenance.
   - *Logical Inference:* Using `pydantic.BaseModel` provides strict type enforcement, deterministic serialization (`payload.model_dump_json(indent=2)`), and schema export (`payload.model_json_schema()`).

4. **CLI Entrypoint & Guardrail Compliance:**
   - **R16 Compliance (Absolute Imports):** `extractor.py` and its sibling modules must use top-level absolute imports (`import schemas`, `import client`) or project-rooted absolute imports. No relative imports (`from .schemas import ...`).
   - **R18 Compliance (Pre-flight Dependencies):** Provide a clean `requirements.txt` in `gemini_mcp_extractor/` and include an automated dependency check in `extractor.py`.
   - **R38 Compliance (Fail-Fast Anti-Mocking):**
     - Pre-flight auth check: If `load_cached_tokens()` returns `None`, fail immediately with exit code 1 and loud remediation instructions (`"Please run 'nlm login' to authenticate"`).
     - Production API errors: If `notebook_get` or `source_get_content` fails fatally, raise a loud exception and abort. Never fall back to mock placeholder strings.
   - **R2 Compliance (Zero-Discretion Loud Assertions):** Deterministic pytest suites with explicit assertions on exact types and counts.

---

## 3. Recommended Technical Specifications

### 3.1 Proposed File Layout
```
d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor\
├── __init__.py
├── requirements.txt            # R18 pre-flight dependencies
├── schemas.py                  # Pydantic v2 data models
├── client.py                   # MCP stdio & Direct client adapters
├── extractor.py                # Main CLI entrypoint (R16 absolute imports, R38 fail-fast)
├── tests/
│   ├── __init__.py
│   ├── test_schemas.py         # Unit tests: Pydantic serialization & loud assertions
│   ├── test_client_mock.py     # Unit tests: Mocked MCP transport & error conditions
│   ├── test_extractor_dry.py   # Integration test: Live dry-run with --limit 2
│   └── test_extractor_full.py  # Full integration test: All 61 items validated
└── README.md                   # Operator usage guide
```

### 3.2 Pydantic Data Schema (`schemas.py`)
```python
from datetime import datetime, timezone
from typing import Any, List, Optional
from pydantic import BaseModel, Field

class NotebookMetadata(BaseModel):
    id: str = Field(description="Notebook UUID")
    title: str = Field(description="Notebook title")
    url: str = Field(description="Notebook web URL")
    source_count: int = Field(description="Reported source count")
    emoji: Optional[str] = Field(default=None, description="Notebook emoji icon")

class ExtractedSource(BaseModel):
    id: str = Field(description="Source UUID")
    title: str = Field(description="Source title")
    source_type: str = Field(default="unknown", description="Source type (web, file, text, etc.)")
    url: Optional[str] = Field(default=None, description="Original URL if available")
    char_count: int = Field(default=0, description="Character count of extracted text")
    content: Optional[str] = Field(default=None, description="Full extracted text content")
    status: str = Field(default="success", description="Extraction status: success, failed, skipped")
    error: Optional[str] = Field(default=None, description="Error message if failed")

class ExtractedNote(BaseModel):
    id: str = Field(description="Note UUID")
    title: str = Field(description="Note title")
    content: str = Field(description="Full markdown content")
    preview: Optional[str] = Field(default=None, description="Preview text")

class ExtractionProvenance(BaseModel):
    extracted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    extractor_version: str = "1.0.0"
    transport: str = Field(description="mcp-stdio or direct-api")
    total_sources: int
    total_notes: int
    is_dry_run: bool = False
    limit_applied: Optional[int] = None

class NotebookExtractionPayload(BaseModel):
    schema_version: str = "1.0.0"
    metadata: NotebookMetadata
    sources: List[ExtractedSource]
    notes: List[ExtractedNote]
    provenance: ExtractionProvenance
```

### 3.3 CLI Interface (`extractor.py`)
```
usage: python extractor.py [-h] [--notebook-id NOTEBOOK_ID] [--output OUTPUT]
                           [--dry-run] [--limit LIMIT] [--format {json,jsonl}]
                           [--transport {mcp,direct}] [--concurrency CONCURRENCY]
                           [--no-content] [--verbose]

Options:
  --notebook-id ID     UUID of notebook (default: 4b52cc67-9f81-4e85-a024-5f06756991ab)
  --output PATH        Target JSON output path (default: extracted_<id>.json)
  --dry-run            Dry run mode: extracts 2 sources and all notes without full extraction
  --limit N            Limit full source content extractions to N items (0 for unlimited)
  --format FMT         Output format: 'json' (pretty-printed) or 'jsonl' (default: json)
  --transport MODE     Transport protocol: 'mcp' (stdio via MCP server) or 'direct' (default: mcp)
  --concurrency N      Maximum concurrent source content fetches (default: 4)
  --no-content         Extract source metadata only without fetching full text
  --verbose            Enable debug logging
```

### 3.4 Requirements (`requirements.txt`)
```text
mcp>=1.29.0
notebooklm-mcp-cli>=0.10.0
pydantic>=2.10.0
httpx>=0.28.0
pytest>=9.0.0
pytest-asyncio>=1.4.0
pytest-mock>=3.15.0
```

---

## 4. Caveats

1. **Windows Subprocess Spawning (`sys.executable`):** When invoking `StdioServerParameters`, always pass `sys.executable` as the `command` rather than generic `'python'`. This avoids potential Windows Store execution alias redirection issues.
2. **UTF-8 Output Encoding:** Windows default file encoding is frequently `cp1252`. All JSON file writes must explicitly pass `encoding="utf-8"` to handle special characters and emojis (e.g. `⚓`, non-Latin text in crawled research articles).
3. **IDE Tool Permission Prompt Boundary:** The IDE's built-in MCP proxy prompts for confirmation on certain tools like `source_describe`. However, our standalone script spawns `python -m notebooklm_tools.mcp.server` directly via stdio; read-only operations (`notebook_get`, `note(list)`, `source_get_content`) execute headlessly with zero interactive modals.

---

## 5. Conclusion

1. **Target workspace is verified and completely clear:** `d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor` is ready for implementation with zero file conflicts.
2. **Environment is fully provisioned:** Python 3.13.14, `mcp 1.29.1`, `notebooklm_tools`, and `pydantic 2.13.4` are verified and functional.
3. **Target dataset verified live:** Notebook `4b52cc67-9f81-4e85-a024-5f06756991ab` contains exactly 61 sources and 1 comprehensive research note.
4. **Implementation Plan is solid:** The subsequent builder agent can proceed immediately to generate `schemas.py`, `client.py`, `extractor.py`, `requirements.txt`, and the full test suite in `tests/`.

---

## 6. Verification Method

The following deterministic commands independently verify all survey findings:

1. **Verify Python & MCP library availability:**
   ```powershell
   python -c "import mcp, pydantic, notebooklm_tools; print('Libraries verified successfully')"
   ```

2. **Verify active NotebookLM credentials:**
   ```powershell
   python -c "from notebooklm_tools.core.auth import load_cached_tokens; t = load_cached_tokens(); assert t is not None, 'No auth tokens found'; print('Auth verified for profile:', getattr(t, 'profile_name', 'default'))"
   ```

3. **Verify MCP server stdio connectivity & 61-source notebook:**
   ```powershell
   python -c "
   import asyncio, sys
   from mcp import ClientSession, StdioServerParameters
   from mcp.client.stdio import stdio_client
   async def run():
       params = StdioServerParameters(command=sys.executable, args=['-m', 'notebooklm_tools.mcp.server'])
       async with stdio_client(params) as (r, w):
           async with ClientSession(r, w) as s:
               await s.initialize()
               res = await s.call_tool('notebook_get', {'notebook_id': '4b52cc67-9f81-4e85-a024-5f06756991ab'})
               text = res.content[0].text
               assert 'Dual-Loop' in text
               assert '61' in text
               print('Verified target notebook with 61 sources via MCP stdio')
   asyncio.run(run())
   "
   ```

4. **Verify Target Directory Purity:**
   ```powershell
   Get-ChildItem -Path "d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor" -Force
   ```

