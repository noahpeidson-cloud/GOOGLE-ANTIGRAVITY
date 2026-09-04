# Unified Ops Hub

A high-performance operational cockpit and headless telemetry bus unifying real-time system metrics, automated knowledge ingestion pipelines (**Ingest Daemon**), and semantic retrieval stores (**Vector Hub**).

---

## Architecture Overview

```
                          ┌───────────────────────────┐
                          │   React 19 + Tailwind     │
                          │   Vite SPA (Port 5173)    │
                          └─────────────┬─────────────┘
                                        │
                         HTTP & WS Proxy │ (/api, /ws)
                                        ▼
                          ┌───────────────────────────┐
                          │   FastAPI Headless Bus    │
                          │   backend/app.py (8000)   │
                          └──────┬─────────────┬──────┘
                                 │             │
                    ┌────────────┴──┐       ┌──┴──────────────┐
                    ▼               ▼       ▼                 ▼
          [GET / & /status]     [WS /ws]  [Ingest Daemon]  [Vector Hub]
          {"status":"online"}   Event Bus  Queue & Heartbeat 1536-dim Search
```

- **Headless Backend (`backend/app.py`)**:
  - FastAPI asynchronous server with lifespan telemetry background task.
  - Endpoints `GET /` and `GET /status` returning `{"status": "online"}`.
  - WebSocket Event Bus (`/ws`, `/ws/telemetry`) broadcasting periodic telemetry updates (CPU, RAM, daemon states, vector search latency) and enabling full-duplex client event broadcasting.
  - Decoupled REST API endpoints for Vector Hub semantic search (`/api/vector-hub/search`), Ingest Daemon telemetry (`/api/ingest/status`), and custom event dispatching (`/api/events`).
- **Frontend SPA (`frontend/`)**:
  - React 19, TypeScript, Tailwind CSS, and Vite.
  - Real-time telemetry bar (CPU load bar, RAM usage, vector store size, query latency, index health).
  - **Vector Hub Panel**: Semantic search interface with cosine similarity score badges, query suggestions, and clipboard actions.
  - **Ingest Daemon Panel**: Live queue depth, document throughput counters, heartbeat tracking, and manual ingestion triggers via WebSocket.
  - **Telemetry Stream Panel**: Monospace live frame monitor for the multiplexed event bus with filtering.
  - WCAG 2.1 AA accessible focus indicators, responsive design, and React Error Boundaries.

---

## Prerequisites

- **Python 3.10+** (tested on Python 3.13)
- **Node.js 18+** & **npm 9+** (tested on Node.js v26.7)

---

## Local Launch Instructions

### 1. Launch the Backend Server

From the `apps/unified_ops_hub` directory:

```bash
# Optional: create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix:
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run the FastAPI server
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

Verify backend health:
```bash
curl http://127.0.0.1:8000/
# Returns: {"status": "online"}

curl http://127.0.0.1:8000/status
# Returns: {"status": "online"}
```

---

### 2. Launch the Frontend Application

In a separate terminal, navigate to the `frontend/` folder:

```bash
cd apps/unified_ops_hub/frontend

# Install frontend dependencies
npm install

# Start the Vite development server
npm run dev
```

The Vite dev server will start at:
👉 **`http://localhost:5173`**

The Vite configuration automatically proxies:
- `/api/*` to `http://127.0.0.1:8000/api/*`
- `/ws` to `ws://127.0.0.1:8000/ws`

---

## API & WebSocket Reference

### HTTP Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Root health check, returns `{"status": "online"}` |
| `GET` | `/status` | Status endpoint, returns `{"status": "online"}` |
| `GET` | `/health` | Alternate health endpoint |
| `GET` | `/api/telemetry` | Current system & daemon telemetry snapshot |
| `GET` | `/api/vector-hub/search?q={query}&limit=6` | Semantic vector search placeholder results |
| `GET` | `/api/ingest/status` | Ingest Daemon operational state & metrics |
| `POST` | `/api/events` | Publish arbitrary JSON event to the WebSocket bus |

### WebSocket Protocol (`/ws`)

Connect via `ws://127.0.0.1:8000/ws`:
- On connection, receives initial state `{ "event": "connected", "data": { ... } }`.
- Periodically receives `{ "event": "telemetry_update", "data": { ... } }` every 2 seconds.
- Client can send ping: `{ "action": "ping" }` -> returns `{ "event": "pong" }`.
- Client can trigger ingest sync: `{ "action": "trigger_sync" }` -> broadcasts update across all clients.
- Client can broadcast custom message: `{ "action": "broadcast", "event": "...", "data": { ... } }`.
