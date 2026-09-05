# Gemini Notebook MCP Extractor

A robust, enterprise-grade Python extraction utility for Google NotebookLM. Connects to the `gemini-notebook` Model Context Protocol (MCP) server over stdio (JSON-RPC) or directly via underlying Python service layers to extract all indexed research sources and synthesis notes into structured JSON/JSONL payloads.

## Architecture & Features

- **Dual-Transport Interface (`client.py`):**
  - `MCPStdioClient` (Default): Connects to `python -m notebooklm_tools.mcp.server` over stdio JSON-RPC.
  - `DirectClient`: In-process high-speed execution invoking `notebooklm_tools.services` directly.
- **Pydantic v2 Data Contracts (`schemas.py`):**
  - Fully typed schemas (`NotebookMetadata`, `ExtractedSource`, `ExtractedNote`, `ExtractionProvenance`, `NotebookExtractionPayload`).
  - Atomic, UTF-8 file writing supporting pretty `json` and streamable `jsonl`.
- **Concurrency & Rate-Limiting:**
  - Configurable `asyncio.Semaphore` (default: 4 concurrent workers) with pacing protection.
- **Guardrail Compliant:**
  - **R16:** Strictly absolute imports throughout.
  - **R18:** Dependency pre-flight check before execution.
  - **R38:** Fail-fast authentication verification and loud remediation advice.

## Prerequisites

1. **Python 3.10+** (Python 3.13 tested and verified)
2. **NotebookLM Authentication:**
   If you have not already authenticated, log in once via the NotebookLM CLI:
   ```bash
   nlm login
   ```
   This automates Google Chrome CDP authentication and saves session cookies to `~/.notebooklm-mcp-cli/profiles/default/cookies.json`.

## Installation

```bash
cd "d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor"
pip install -r requirements.txt
```

## Quick Start

### 1. Dry-Run Extraction (Verification Mode)
Fetches metadata, all notes, and a small subset (2 sources) to confirm connectivity:
```bash
python extractor.py --dry-run
```

### 2. Full Extraction via MCP Stdio (Default)
Extracts all 61 sources with full text and all notes:
```bash
python extractor.py --notebook-id 4b52cc67-9f81-4e85-a024-5f06756991ab -o extracted_notebook_data.json
```

### 3. High-Speed Direct Transport
Extracts directly in-process for maximum speed:
```bash
python extractor.py --transport direct -o extracted_notebook_data.json
```

### 4. JSON Lines Format Export
Export as line-delimited JSON for BigQuery, SQLite, or streaming ingestion:
```bash
python extractor.py --format jsonl -o extracted_notebook_data.jsonl
```

## CLI Options

| Flag | Type | Default | Description |
|---|---|---|---|
| `--notebook-id` | string | `4b52cc67-9f81-4e85-a024-5f06756991ab` | Notebook UUID |
| `-o`, `--output` | string | `extracted_notebook_data.json` | Destination file path |
| `--dry-run` | flag | `False` | Fast run extracting max 2 sources + notes |
| `--limit` | int | `None` | Restrict source extraction to N items |
| `--transport` | `mcp` \| `direct` | `mcp` | Transport protocol |
| `--concurrency` | int | `4` | Max concurrent source downloads |
| `--format` | `json` \| `jsonl` | `json` | Output serialization format |
| `--no-content` | flag | `False` | Skip full text extraction (metadata only) |
| `--fail-fast` | flag | `False` | Abort immediately on single source failure |
| `-v`, `--verbose` | flag | `False` | Enable debug logging |

## Running Tests

Run the test suite using `pytest`:
```bash
python -m pytest tests/ -v
```

## Troubleshooting

- **Authentication Error (`No active NotebookLM authentication tokens found`):**
  Run `nlm login` in your terminal to refresh expired cookies.
- **Windows Console Unicode Errors:**
  `extractor.py` automatically reconfigures stdout to UTF-8 on Windows. If running custom scripts, ensure `PYTHONIOENCODING=utf-8` is set.
