---
name: unified-ops-hub
description: Operational runbook and diagnostic procedures for managing the Unified Ops Hub cockpit (FastAPI port 8000, Vite React port 5173, WebSocket telemetry bus).
---

# Unified Ops Hub Operational Runbook

## Overview
The Unified Ops Hub (`apps/unified_ops_hub`) is a real-time operational cockpit and telemetry event bus connecting system performance metrics, the Ingest Daemon, and the Curated Memory / Vector Hub.

## Architecture & Ports
- **Backend**: FastAPI asynchronous server on `http://127.0.0.1:8000`
- **Frontend**: Vite + React 19 + TypeScript on `http://localhost:5173`
- **WebSocket Event Bus**: `ws://127.0.0.1:8000/ws` (proxied by Vite from `/ws`)
- **API Proxy**: `/api/*` proxied by Vite to `http://127.0.0.1:8000/api/*`

## Launch Runbooks

### 1. Launch Backend Server
```powershell
# From workspace root:
cd apps/unified_ops_hub
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Launch Frontend Application
```powershell
# From workspace root:
cd apps/unified_ops_hub/frontend
npm run dev
```

### 3. Verify Health & Telemetry
```powershell
# Verify root health check
Invoke-RestMethod -Uri "http://127.0.0.1:8000/status" -Method Get

# Verify telemetry snapshot
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/telemetry" -Method Get
```

## Storage & Boundary Governance
- The backend MUST strictly import shared utilities using absolute imports: `from infrastructure.workspace_context import WORKSPACE_ROOT`.
- All persistent event logs and DLQ databases MUST reside on `D:`.

## Natural Language Invocations
- *"Start the Unified Ops Hub backend and frontend"*
- *"Check the status of the Unified Ops Hub telemetry bus"*
- *"Diagnose the WebSocket connection between the Ops Hub frontend and FastAPI"*
