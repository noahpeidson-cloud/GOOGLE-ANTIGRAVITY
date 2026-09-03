---
name: antigravity-bridge-support
description: Comprehensive operational runbook and diagnostic procedures for managing the Antigravity Local Bridge (localhost:11435), MCP server (localhost:3033), sidecar ConnectRPC processes, and dual-IDE synchronization with VS Code.
license: Complete terms in LICENSE.txt
---

# Antigravity Bridge & IDE Support Skill

This skill provides deterministic diagnostic, operational, and remediation runbooks for the Antigravity local bridge architecture, language server sidecar, and dual-IDE workflows.

---

## 1. Architecture Overview

```
                      +-----------------------------+
                      |     Antigravity IDE         |
                      |  (Language Server Sidecar)  |
                      +--------------+--------------+
                                     |
                          Dynamic HTTPS ConnectRPC
                          + Dynamic CSRF Token
                                     |
                    +----------------v----------------+
                    |        ag-local-bridge          |
                    |     (VS Code Extension Host)    |
                    |       Listening on :11435       |
                    +----------------+----------------+
                                     |
                +--------------------+--------------------+
                |                                         |
    OpenAI-Compatible API                     Anthropic / Gemini APIs
  /v1/chat/completions (POST)                   /v1/messages (POST)
       /v1/models (GET)                     /v1beta/models/:id (POST)
                |                                         |
    +-----------v-----------+                 +-----------v-----------+
    |  VS Code Continue.dev |                 | External Tools / SDKs |
    |  (Tab Autocomplete &  |                 | (Python, Curl, Aider) |
    |      Inline Edits)    |                 |                       |
    +-----------------------+                 +-----------------------+
```

---

## 2. Diagnostic Runbooks

### Runbook A: Verify Bridge Health & Model Availability
Check if the local bridge is active and exposing models on port 11435:

```powershell
# Query available models
Invoke-RestMethod -Uri "http://127.0.0.1:11435/v1/models" -Method Get -TimeoutSec 3

# Verify Gemini 3.8 Flash is recognized
$models = (Invoke-RestMethod -Uri "http://127.0.0.1:11435/v1/models").data
$models | Where-Object { $_.id -like "*3.8*" -or $_.id -like "*sonnet*" } | Select-Object id, owned_by
```

### Runbook B: Diagnose Sidecar Discovery
Inspect CSRF token interception and sidecar ConnectRPC connection:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:11435/v1/debug" -Method Get -TimeoutSec 3 | ConvertTo-Json -Depth 4
```

- If `sidecar.error = "Not found"`, ensure Antigravity IDE or a language server instance (`language_server.exe`) is running.
- If `interceptedAuth.hasCsrf = false`, reload the VS Code window (`Developer: Reload Window`) to reinstall HTTP/H2 network interceptors.

### Runbook C: Resolving Socket Collisions (`WinError 10048` / `EADDRINUSE`)
If port 11435 is occupied:

1. Identify the process holding the port:
   ```powershell
   Get-NetTCPConnection -LocalPort 11435 -ErrorAction SilentlyContinue | Select-Object LocalPort, State, OwningProcess
   ```
2. The bridge has built-in auto-increment logic: if 11435 is occupied, it automatically scans ports 11436–11445.

### Runbook D: Verify MCP Dashboard & CDP Port
Check port 3033 (`antigravity-mcp-experimental`) and CDP port 9222:

```powershell
# Check listener status
Get-NetTCPConnection -LocalPort 3033, 9222 -ErrorAction SilentlyContinue | Select-Object LocalPort, State, OwningProcess

# Fetch active chat state from MCP bridge
Invoke-RestMethod -Uri "http://127.0.0.1:3033" -Method Get -TimeoutSec 3
```

---

## Natural Language Invocations
- *"Check the Antigravity local bridge status on port 11435"*
- *"Diagnose sidecar connection between VS Code and Antigravity"*
- *"Restart local bridge or fix socket collision on port 11435"*
- *"Verify MCP server connectivity on port 3033"*

