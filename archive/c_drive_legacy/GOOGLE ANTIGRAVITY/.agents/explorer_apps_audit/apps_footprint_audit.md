# Antigravity Application Ecosystem: Exhaustive Footprint & Architectural Audit

**Audit Date:** 2026-08-22  
**Auditor Archetype:** Teamwork Codebase Explorer  
**Scope Target:** `G:\My Drive\GOOGLE ANTIGRAVITY\apps`  
**Referenced Projects:** `agy_chrome_extension`, `agy_daemon`, `agy_mobile`, `auto_qa_builder`, `zero_friction_capture_extension`, and `apps/GEMINI.md`.

---

## 1. Executive Summary & Ecosystem Overview

The `apps/` directory within the Antigravity workspace serves as the client and transactional layer across multiple devices and user touchpoints (browser extensions, mobile/web interfaces, local daemon processes, autonomous QA builders, and local inbox servers). 

Currently, the ecosystem contains **5 distinct application sub-packages** and **1 architectural manifest**:

1. **`apps/agy_chrome_extension`**: A Manifest V3 Chrome Extension providing a side-panel chat UI, bi-directional WebSocket client targeting `ws://localhost:8002/ws`, DOM action executor (`click`, `type`, `scrape`), and proactive Card Ladder scraping.
2. **`apps/agy_daemon`**: A Python daemon utilizing the `firebase-admin` SDK connected to Google Cloud Firestore project `noahs-ai-bussin`. It actively watches a `commands` Firestore collection via real-time snapshot listeners to orchestrate pipelines (such as `trigger_edm_pipeline`) and stream subprocess logs.
3. **`apps/agy_mobile`**: A **Next.js 16.3.2 / React 19.2.8 / Tailwind CSS v4** progressive web application (PWA) configured with the client-side Firebase JS SDK. It provides a terminal-style AGY Command Center that pushes command documents into Firestore and subscribes to real-time logs. *(Note: While initially characterized as Flutter/Dart in legacy requests, it is implemented as a modern React/Next.js Web PWA)*.
4. **`apps/auto_qa_builder`**: An autonomous builder agent implemented via the `google.antigravity` SDK using `gemini-3.7-flash`, configured with the `chrome-devtools-mcp` server and `@hooks.post_tool_call` interceptors to mechanically enforce Web Accessibility (a11y) tree audits on generated UI code.
5. **`apps/zero_friction_capture_extension` & `inbox_server.py`**: A Manifest V3 Chrome Extension powered by Chrome's built-in on-device AI (`self.ai.languageModel` Prompt API / Gemini Nano) that extracts structured JSON (`type`, `title`, `summary`, `key_attributes`) directly in-browser and posts it to a local FastAPI + SQLite inbox service (`127.0.0.1:8080`).
6. **`apps/GEMINI.md`**: Directory-scoped architectural rule manifest defining clean architecture boundaries, UI tooling (Streamlit, React/Vite), data tiers (SQLite3, Pandas), and mandatory Core Web Vitals (LCP < 2.5s) / mobile layout validation gates.

---

## 2. Application Footprint Inventory Matrix

| Application Folder | Core Framework / Tech Stack | Primary Entrypoint | Transport / Protocols | Target Datastore / Backend | Status & Primary Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`agy_chrome_extension`** | Chrome MV3, Vanilla JS, HTML/CSS | `manifest.json`, `background.js` | WebSocket (`ws://localhost:8002/ws`), Chrome Messaging API | Local Daemon / Content DOM | Active Prototype (Contains JS syntax artifacts) |
| **`agy_daemon`** | Python 3.10+, `firebase-admin`, Firestore | `daemon.py` | Firestore Snapshot Listener (`commands_ref.on_snapshot`) | Cloud Firestore (`noahs-ai-bussin`) | Active Daemon (Missing local WS server port 8002) |
| **`agy_mobile`** | Next.js 16.3.2, React 19.2.8, Tailwind CSS 4, TS | `src/app/page.tsx` | HTTPS / Firestore Client SDK WebSocket | Cloud Firestore (`noahs-ai-bussin`) | Active Next.js Web/Mobile PWA |
| **`auto_qa_builder`** | Python, `google.antigravity`, `gemini-3.7-flash` | `builder_agent.py` | Antigravity Agent Protocol, MCP (`chrome-devtools-mcp`) | In-Memory / DevTools Tree | Active Autonomous QA Agent |
| **`zero_friction_capture_extension`** | Chrome MV3, Chrome Prompt API (Gemini Nano) | `service-worker.js`, `sidepanel.js` | Chrome Scripting API, Local REST HTTP POST (`:8080/ingest`) | Local FastAPI / SQLite (`inbox.db`) | Functional On-Device AI Extractor |
| **`inbox_server.py`** | FastAPI, Uvicorn, SQLite3, Pydantic | `inbox_server.py` | Local HTTP REST (`127.0.0.1:8080`) | SQLite (`apps/zero_friction_capture_extension/inbox.db`) | Functional Local Transactional Buffer |

---

## 3. Deep Architectural Audit: `apps/agy_chrome_extension`

### 3.1 Manifest & Permissions (`manifest.json`)
- **Manifest Version**: 3
- **Extension Name**: "Antigravity Universal Agent" (v1.0)
- **Permissions**: `sidePanel`, `tabs`, `activeTab`, `scripting`
- **Host Permissions**: `<all_urls>` (allows script injection and DOM reading on any domain)
- **Background Configuration**: Service worker registered at `background.js`
- **Side Panel**: Configured with `default_path: "sidepanel.html"`
- **Action**: Opens side panel on icon click (`setPanelBehavior({ openPanelOnActionClick: true })`)

### 3.2 Background Service Worker (`background.js`)
- **Connection Logic**: Instantiates WebSocket to `ws://localhost:8002/ws` on load (`connectWebSocket()`).
- **Resilience**: Implements auto-reconnect with a 5000ms delay (`setTimeout(connectWebSocket, 5000)` on `onclose`).
- **Inbound WebSocket Handling**:
  - Parses JSON incoming data.
  - If `data.type === 'EXECUTE_DOM_ACTION'`, queries active tab in current window and delegates execution via `chrome.tabs.sendMessage(tabs[0].id, data)`.
- **Outbound Message Routing**:
  - Listens for Chrome runtime messages (`chrome.runtime.onMessage`).
  - If `message.target === 'backend'` and WebSocket state is `WebSocket.OPEN`, serializes `message.payload` as JSON and transmits to `localhost:8002`.

### 3.3 Content Script & DOM Automation (`content.js`)
- **Action Router**: Listens for messages from `background.js` with `request.type === 'EXECUTE_DOM_ACTION'`:
  - **`click`**: Executes `document.querySelector(selector).click()`.
  - **`type`**: Assigns `element.value = value` and dispatches `input` and `change` bubbling events to simulate genuine user typing.
  - **`scrape`**: Extracts entire `document.body.innerText` and transmits `{ target: 'backend', payload: { type: 'DOM_DATA', url: window.location.href, content: data } }`.
- **Domain-Specific Automation**:
  - Detects `cardladder` domain (`if (window.location.hostname.includes('cardladder'))`).
  - Waits 3000ms, grabs `document.querySelector('table').innerText`, and sends `{ target: 'backend', payload: { type: 'CARD_LADDER_DATA', url, content } }`.
- **Defects / Syntax Issues in `content.js`**:
  - **Line 10**: `console.warn(Element not found: );` — Missing quotation marks/template literals. Causes a JavaScript syntax parse error when element is missing.

### 3.4 Sidepanel UI & User Interaction (`sidepanel.html`, `sidepanel.js`)
- **Interface Design**: Dark-slate aesthetic (`#0f172a` body, `#38bdf8` accent headers, `#1e293b` chat log).
- **Behavior**:
  - User submits text input -> Appends message to chat log.
  - Queries active tab URL.
  - Dispatches `{ target: 'backend', payload: { type: 'USER_CHAT', text, context_url } }`.
  - Dispatches `{ action: 'scrape' }` to active tab's content script to instantly capture fresh DOM context.
- **Defects / Syntax Issues in `sidepanel.js`**:
  - **Line 7**: `div.className = message ;` — Missing quotes/template string (should be ``div.className = `message ${sender.toLowerCase()}`;``).
  - **Line 8**: `div.innerHTML = <strong>:</strong> ;` — Malformed HTML string (should be ``div.innerHTML = `<strong>${sender}:</strong> ${text}`;``).

---

## 4. Deep Architectural Audit: `apps/agy_daemon`

### 4.1 Entrypoint & Initialization (`daemon.py`, `credentials.json`)
- **Service Identity**: Connected to GCP / Firebase project `noahs-ai-bussin`.
- **Credentials**: Hardcoded service account credentials loaded from `apps/agy_daemon/credentials.json` (`firebase-adminsdk-fbsvc@noahs-ai-bussin.iam.gserviceaccount.com`).
- **Initialization**: `firebase_admin.initialize_app(cred)` followed by `db = firestore.client()`.

### 4.2 Real-Time Command Listener
- **Collection**: Watches Cloud Firestore collection `commands` via real-time snapshot listener:
  ```python
  commands_ref = db.collection('commands')
  commands_watch = commands_ref.on_snapshot(handle_command)
  ```
- **State Machine**:
  - Filters for `change.type.name == 'ADDED'`.
  - Checks if `cmd_data.get('status') == 'pending'`.
  - Updates Firestore document status to `processing`.
  - If `action == "trigger_edm_pipeline"`, triggers pipeline and updates status to `completed`.

### 4.3 Subprocess Log Streaming (`stream_logs`)
- Reads stdout line-by-line in binary mode (`iter(process.stdout.readline, b'')`).
- Decodes UTF-8 and pushes structured telemetry into Firestore subcollection:
  ```python
  doc_ref.collection("logs").add({
      "timestamp": time.time(),
      "message": decoded_line
  })
  ```
- Upon process termination, updates `doc_ref.update({"status": "completed"})`.

### 4.4 Architectural Disconnects & Gaps
- **Missing WebSocket Server**: `agy_chrome_extension/background.js` actively attempts to connect to `ws://localhost:8002/ws`. However, `agy_daemon/daemon.py` only implements a Firestore listener; it does **not** launch an `asyncio` / `websockets` / FastAPI server on port 8002.
- **Missing Pipeline Execution Body**: The action `trigger_edm_pipeline` simply prints a string and immediately sets status to `completed` without invoking the actual content creation / ADB ingestion pipeline.

---

## 5. Deep Architectural Audit: `apps/agy_mobile`

### 5.1 Project Structure & Tech Stack
- **Architecture**: Next.js 16.3.2 (App Router), React 19.2.8, TypeScript 5, Tailwind CSS v4.
- **Nature**: Built as a responsive Web / PWA Command Center for mobile and desktop screens.
- **Routing**: Single page application (`src/app/page.tsx`, `src/app/layout.tsx`).

### 5.2 Client-Side Firebase Integration (`src/lib/firebase.ts`)
- **Project Configuration**:
  - Project ID: `noahs-ai-bussin`
  - App ID: `1:551414926862:web:84170e2d84d452d163f65f`
  - Storage Bucket: `noahs-ai-bussin.firebasestorage.app`
  - API Key: `AIzaSyAm2iQhnej19SBqoa3z9LojB-Wdm2qLTpU`
  - Auth Domain: `noahs-ai-bussin.firebaseapp.com`
- **Singleton Initialization**: `!getApps().length ? initializeApp(firebaseConfig) : getApp()`.

### 5.3 Command Dispatch & Telemetry UI (`src/app/page.tsx`)
- **State Management**: React hooks `useState` (logs, status) and `useEffect`.
- **Command Dispatcher**:
  ```typescript
  const triggerPipeline = async () => {
    setStatus('processing');
    await addDoc(collection(db, 'commands'), {
      action: 'trigger_edm_pipeline',
      status: 'pending',
      timestamp: Date.now()
    });
  };
  ```
- **Real-Time Log Ingestion**:
  - Subscribes to Firestore collection `logs` ordered by `timestamp` desc (limit 50).
  - Displays streaming terminal messages inside an elevated slate-styled console (`bg-gray-900 border-gray-700`).

### 5.4 Schema Inconsistency Between Mobile & Daemon
- **Inconsistency**:
  - `apps/agy_mobile/src/app/page.tsx` subscribes to the **root** collection: `collection(db, 'logs')`.
  - `apps/agy_daemon/daemon.py` writes logs to a **subcollection** under the specific command document: `doc_ref.collection("logs")`.
  - **Impact**: When the daemon streams execution output, `agy_mobile` will not receive or display the log entries unless the query is adjusted to collectionGroup or written to root `logs`.

---

## 6. Deep Architectural Audit: Additional Applications

### 6.1 `apps/auto_qa_builder` (`builder_agent.py`)
- **Purpose**: Autonomous Agent for building React/Vite interfaces with strict mechanical accessibility (a11y) verification.
- **SDK & Model**: `google.antigravity` SDK using `gemini-3.7-flash`.
- **MCP Integration**: Configures `chrome-devtools-mcp` via `npx -y chrome-devtools-mcp@latest`.
- **Enforcement Mechanism**: Uses `@hooks.post_tool_call` to intercept file generation / UI tool operations, invoking DevTools to take accessibility tree snapshots and enforce ARIA compliance, tap target sizes, and color contrast ratios.

### 6.2 `apps/zero_friction_capture_extension` & `inbox_server.py`
- **Purpose**: Zero-friction web data clipping directly into local structured storage.
- **Browser AI (On-Device)**: Uses Chrome's built-in Prompt API (`self.ai.languageModel.create()`, backed by Gemini Nano).
- **Data Pipeline**:
  1. `sidepanel.js` injects script to extract `document.body.innerText`.
  2. Passes text (truncated to 4000 chars) to Gemini Nano with prompt to format as strict JSON (`type`, `title`, `summary`, `key_attributes`).
  3. Displays extracted JSON in sidepanel `<textarea>`.
  4. User clicks "Save to Local Inbox" -> POSTs to `http://localhost:8080/ingest`.
- **Local Ingest Server (`inbox_server.py`)**:
  - FastAPI application running on `127.0.0.1:8080`.
  - SQLite database `apps/zero_friction_capture_extension/inbox.db`.
  - Schema: `inbox (id, source_url, timestamp, extracted_data_json, processed)`.
  - Implements CORS middleware allowing extension origins.

---

## 7. Cross-Application Integration & Data Flow Analysis

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               USER TOUCHPOINTS                                  │
│                                                                                 │
│   ┌───────────────────────────┐           ┌─────────────────────────────────┐   │
│   │ apps/agy_chrome_extension │           │ apps/zero_friction_capture_ext │   │
│   │  - Sidepanel Chat UI      │           │  - Chrome Prompt API (Nano)     │   │
│   │  - DOM Scraper (CardLad.) │           │  - JSON Structured Extraction   │   │
│   │  - DOM Action Injector    │           │                                 │   │
│   └─────────────┬─────────────┘           └────────────────┬────────────────┘   │
│                 │                                          │                    │
│     WebSocket   │ ws://localhost:8002                      │ HTTP POST          │
│     (DISCONNECT)│                                          │ :8080/ingest       │
│                 ▼                                          ▼                    │
│   ┌───────────────────────────┐           ┌─────────────────────────────────┐   │
│   │     [MISSING BRIDGE]      │           │    inbox_server.py (FastAPI)    │   │
│   │  (No WS Server on 8002)   │           │    - Local SQLite (inbox.db)    │   │
│   └───────────────────────────┘           └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │
┌─────────────────────────────────────┴───────────────────────────────────────────┐
│                           CLOUD & DAEMON CONTROL                                │
│                                                                                 │
│   ┌───────────────────────────┐           ┌─────────────────────────────────┐   │
│   │      apps/agy_mobile      │           │         apps/agy_daemon         │   │
│   │  (Next.js 16 / React 19)  │           │   (Python Firestore Listener)   │   │
│   │  - PWA Command Center     │           │   - Service Account Auth        │   │
│   │  - Push 'commands'        │           │   - Executes Pipeline Actions   │   │
│   │  - Listen 'logs' (Root)   │           │   - Streams logs (Subcollection)│   │
│   └─────────────┬─────────────┘           └────────────────┬────────────────┘   │
│                 │                                          │                    │
│                 │ Firestore JS SDK                         │ Firestore Admin SDK│
│                 ▼                                          ▼                    │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                   Google Cloud Firestore ('noahs-ai-bussin')            │   │
│   │                   - Collection: commands (pending / processing / done)  │   │
│   │                   - Collection: logs / command-subcollection logs       │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Key Ecosystem Strengths:
1. **Multi-Modal Ingestion**: Integrates DOM scraping, on-device AI summarization (Gemini Nano), and cloud-coordinated command triggering.
2. **Real-Time Reactive Architecture**: Firestore snapshot listeners allow zero-polling push updates between mobile clients and the daemon.
3. **Automated Quality Hooks**: `auto_qa_builder` pioneers automatic a11y testing during agentic code generation.

### Critical System Deficiencies & Architectural Debt:
1. **The Port 8002 Disconnect**: `agy_chrome_extension` requires a WebSocket server on `ws://localhost:8002/ws` to relay DOM events and chat messages to the local machine, but `agy_daemon` does not host this server.
2. **Firestore Log Path Mismatch**: `agy_daemon` writes logs to `commands/{cmd_id}/logs`, but `agy_mobile` reads from root `/logs`.
3. **JS Syntax Artifacts**: `content.js` and `sidepanel.js` contain unquoted/malformed string concatenation errors that prevent successful execution under strict evaluation.
4. **Hardcoded Service Account Keys**: `apps/agy_daemon/credentials.json` contains raw RSA private keys directly in the repo rather than referencing GCP Application Default Credentials (ADC) or Secret Manager.
5. **No Direct Spark / Big Lake / GCP Pipeline Egress**: The current data landing points are either local SQLite (`inbox.db`) or Firestore. There is no automated Cloud Pub/Sub, Cloud Storage, or Apache Spark ETL pipeline currently wired to ingest this data at scale.

---

## 8. Master Technical Recommendations for Orchestration

To unify these disparate applications into a cohesive, production-grade cloud ecosystem (as required for the Master Technical Specification):

1. **Unify the Local / Edge Daemons**:
   - Merge `inbox_server.py` and `agy_daemon` into a unified Antigravity Local Daemon that provides:
     - WebSocket Server (`ws://127.0.0.1:8002/ws`) for Chrome Extension bi-directional DOM control.
     - HTTP Ingestion Server (`http://127.0.0.1:8080/ingest`) for structured captures.
     - Firestore Command Dispatcher & Subprocess Runner.
2. **Synchronize Firestore Schema Contracts**:
   - Standardize command log telemetry to root `/commands/{commandId}/logs` and update `agy_mobile/src/app/page.tsx` to query the specific active command's log subcollection.
3. **Fix Extension Syntax & Adopt Chrome AI Standards**:
   - Correct template literals in `agy_chrome_extension/content.js` and `sidepanel.js`.
   - Upgrade DOM extraction to leverage the unified structured parser from `zero_friction_capture_extension`.
4. **Cloud Pipeline Egress (GCP & Apache Spark)**:
   - Implement an automated Cloud Function / Cloud Run trigger on Firestore `inbox` writes or direct GCS bucket uploads.
   - Stage raw JSON payloads into Cloud Storage (`gs://noahs-ai-bussin-raw/inbox/`).
   - Define Dataproc Serverless / Apache Spark batch jobs (via `gcp-spark` skill) to execute ETL transformations, deduplication, and schema validation before loading into BigQuery / BigLake Iceberg tables.
5. **Enforce Frontend Quality Gates**:
   - Institutionalize `auto_qa_builder`'s `chrome-devtools-mcp` audit rules into CI/CD pipelines, requiring all Next.js (`agy_mobile`) and Streamlit components to pass Lighthouse LCP < 2.5s and zero ARIA violations.
