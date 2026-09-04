# Omnichannel Triage Hub — Specification Mining & Architecture Survey

## Executive Summary
This document provides the authoritative Phase 0 specification mining and environment survey for the **Omnichannel Triage Hub** project. The application integrates a modern React Vite frontend, a local Python FastAPI hardware/daemon bridge for ADB automation, and Firebase Data Connect (PostgreSQL) for structured video tagging and metadata querying, fully audited under the **R4 Zero-Waste Frontend Audit** mandate (0 detached DOM nodes and 100% semantic a11y compliance).

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | R1: Frontend | Two-Column Layout | Responsive two-column dashboard layout containing device/triage controls on the left and video tags query/grid on the right. | Viewport dimensions, responsive breakpoints | Rendered two-column UI container (`<main>`, `<section>`, `<aside>`) | Degrades gracefully on smaller screens into stacked flex column. | ORIGINAL_REQUEST §R1 |
| 2 | R1: Frontend | Trigger ADB Action | Interactive UI action button in left column that sends an asynchronous POST request to the local FastAPI bridge. | Click event, device target parameters | Network request to `http://localhost:8000/api/trigger-adb-pull`, UI status badge update | Displays error alert / notification on network failure or daemon offline status. | ORIGINAL_REQUEST §R1, §Acceptance |
| 3 | R1: Frontend | Capture Screen Action | Interactive UI button to initiate immediate device screen capture via the daemon bridge. | Click event | Network request to `http://localhost:8000/api/capture-screen`, preview image rendered in UI | Displays error banner if ADB device is disconnected or permission denied. | ORIGINAL_REQUEST §R1, §R2 |
| 4 | R1: Frontend | Triage Live Log & Status Panel | Real-time console/status log displaying daemon connection state, ADB execution events, and operation timestamps. | Event streams, HTTP response payloads | Visual log stream with colored badges (Idle, Running, Success, Error) | Displays fallback "Bridge Disconnected" warning when health check fails. | ORIGINAL_REQUEST §R1, §R2 |
| 5 | R1: Frontend | Tailwind CSS Design System | Modern Tailwind CSS utility styling featuring dark mode, accessible focus rings, and high contrast. | CSS class definitions, theme config | Styled UI with 48x48px tap targets and WCAG AA contrast ratios | Falls back to default browser styles if Tailwind fails to build. | ORIGINAL_REQUEST §R1, GEMINI.md R4 |
| 6 | R2: FastAPI Bridge | ADB Media Pull Endpoint | REST endpoint `POST /api/trigger-adb-pull` triggering `adb pull` to ingest media from connected Android devices. | JSON body: `{ "device_id"?: str, "source_path"?: str, "dest_dir"?: str, "mock"?: bool }` | JSON response: `{ "status": "success", "message": str, "pulled_files": list[str], "timestamp": str }` | Returns HTTP 500 / 503 with structured `{ "status": "error", "detail": str }` if ADB binary fails or device is absent. | ORIGINAL_REQUEST §R2 |
| 7 | R2: FastAPI Bridge | Device Screen Capture Endpoint | REST endpoint `POST /api/capture-screen` capturing device screenshot via `adb exec-out screencap -p`. | JSON body: `{ "device_id"?: str, "mock"?: bool }` | JSON response: `{ "status": "success", "image_base64": str, "saved_path"?: str, "timestamp": str }` | Returns HTTP 500 with error details if screenshot capture fails. | ORIGINAL_REQUEST §R2 |
| 8 | R2: FastAPI Bridge | Daemon Health & Status Check | REST endpoint `GET /api/status` or `GET /health` reporting daemon uptime, ADB connectivity, and environment status. | None | JSON response: `{ "status": "ok", "adb_connected": bool, "adb_version": str, "uptime": float }` | Returns `{ "status": "degraded", "adb_connected": false }` if ADB is unavailable. | ORIGINAL_REQUEST §Acceptance |
| 9 | R2: FastAPI Bridge | CORS Middleware Handler | Starlette/FastAPI `CORSMiddleware` configured to allow requests from `http://localhost:5173`. | HTTP Preflight `OPTIONS` & Request headers | Permissive CORS headers (`Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`) | Returns standard CORS error if disallowed origin connects. | ORIGINAL_REQUEST §Acceptance |
| 10 | R3: Firebase Data Connect | Video Tags Table Definition | GraphQL schema defining the `VideoTag` entity mapped to the `video_tags` PostgreSQL table. | GraphQL schema (`schema.gql`) | PostgreSQL DDL & Data Connect metadata schema | Compilation error via `firebase-tools dataconnect:compile` if syntax or types are invalid. | ORIGINAL_REQUEST §R3, `quick_share_ai_loop/schema.gql` |
| 11 | R3: Firebase Data Connect | Video Tags Query Operation | GraphQL query `ListVideoTags` fetching video tag records with filtering by domain/entity and ordering by `createdAt`. | Query parameters: `{ domain?: string, limit?: number }` | GraphQL response: `{ videoTags: [{ id, filename, domain, entity, viralFeatures, technical, createdAt }] }` | Returns GraphQL error list if query syntax or parameters fail validation. | ORIGINAL_REQUEST §R3 |
| 12 | R3: Firebase Data Connect | Video Tag Mutation Operations | GraphQL mutations (`CreateVideoTag`, `UpdateVideoTag`, `DeleteVideoTag`) for managing triage records. | GraphQL mutation inputs (`VideoTag_InsertInput`, etc.) | GraphQL response with mutated entity ID and status | Returns GraphQL validation errors if unique constraints (e.g. `filename`) are violated. | ORIGINAL_REQUEST §R3, `firebase_data_connect_basics` |
| 13 | R3: Firebase Data Connect | Generated Web SDK Binding | Generated TypeScript/JavaScript SDK (`@firebase/data-connect` or local SDK) providing type-safe query/mutation functions. | Configuration in `connector.yaml` | Type-safe bindings (`executeQuery`, `listVideoTagsRef`, custom React hooks) | Build-time TypeScript errors if SDK generation is out of sync with schema. | ORIGINAL_REQUEST §R3, `reference/sdk_web.md` |
| 14 | R3: Firebase Data Connect | Emulator / Mock Client Adapter | Client-side connection adapter supporting `connectDataConnectEmulator` or offline fallback mock data provider. | Environment config (`VITE_USE_EMULATOR`, `VITE_MOCK_DATA`) | Mock/emulator data streams for local offline development & testing | Fallback to in-memory fixtures when database connection is unreachable. | ORIGINAL_REQUEST §R3 |
| 15 | R4: Frontend Audit | Zero Detached DOM Nodes | Heap snapshot verification that component mounting, unmounting, and list mutations leave 0 detached DOM elements. | 10x repeated tab toggle / list refresh actions | Chrome DevTools `.heapsnapshot` diff showing 0 detached DOM node leaks | Failing test / audit flag if detached HTML elements or event listeners persist. | GEMINI.md R4, `memory-leak-debugging` |
| 16 | R4: Frontend Audit | Semantic HTML Landmarks | HTML5 structure strictly adhering to `<header>`, `<main>`, `<section>`, `<aside>`, `<footer>`, `<h1>`-`<h3>`. | Component JSX markup | Verified Accessibility Tree hierarchy | Axe-core / Lighthouse audit failure if landmarks or heading hierarchy are missing. | GEMINI.md R4, `a11y-debugging` |
| 17 | R4: Frontend Audit | Accessible Form Controls & Buttons | All buttons, inputs, and interactive components feature explicit `aria-label`, `<label for>`, and role definitions. | UI interactive elements | 100% accessible names in Accessibility Tree | Audit failure on orphaned form inputs or nameless icon buttons. | GEMINI.md R4, `a11y-debugging` |
| 18 | R4: Frontend Audit | Keyboard Navigation & Focus Ring | Full keyboard navigability (Tab / Shift+Tab / Enter / Space) with visible high-contrast focus rings (`focus:ring-2`). | Keyboard events | Observable visual focus ring on active element | Audit failure if interactive elements are skipped or focus trap occurs. | GEMINI.md R4, `a11y-debugging` |
| 19 | R4: Frontend Audit | Tap Target & Contrast Compliance | Minimum 48x48px touch/click bounding boxes and WCAG AA color contrast ratio (>= 4.5:1 text, >= 3:1 UI). | Bounding box metrics, CSS computed styles | Verified dimensions and contrast calculation scores | Audit failure if tap targets are < 48px or contrast is < 4.5:1. | GEMINI.md R4, `a11y-debugging` |

---

## Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | FastAPI ADB Pull | No Android device connected via USB/WiFi | `adb` returns `error: no devices/emulators found`. FastAPI daemon catches exception, logs event, and returns HTTP 200 with mock fallback in dev mode or HTTP 503 in strict mode with clear detail. |
| 2 | FastAPI Screen Capture | Device screen locked or asleep | Screen capture executes but produces black image or requires wake command; daemon returns base64 image with warning metadata. |
| 3 | FastAPI Port Collision | Port 8000 already occupied by another service | Uvicorn fails to bind to port 8000; daemon startup script provides port-selection fallback or error message instructing port clearance. |
| 4 | React CORS Preflight | Browser issues `OPTIONS /api/trigger-adb-pull` | FastAPI `CORSMiddleware` intercepts request and returns `200 OK` with `Access-Control-Allow-Origin: http://localhost:5173` and allowed headers. |
| 5 | Firebase Data Connect | Network disconnected / Emulator down | React frontend query handler catches connection error, avoids unhandled promise rejection, and displays an accessible "Offline / Using Cached Data" banner. |
| 6 | Video Tags Table | Duplicate `filename` inserted | PostgreSQL unique constraint on `filename` triggers constraint violation; Data Connect mutation returns structured GraphQL error. |
| 7 | React Component Lifecycle | 10x Rapid Click on "Trigger ADB" | Debounced button handler disables click during flight, preventing duplicate concurrent subprocesses and detached event listener leaks. |
| 8 | Large Video Tags Dataset | 1,000+ records returned from PostgreSQL | Component renders items efficiently with pagination or virtualization to prevent DOM node bloat and heap memory exhaustion. |
| 9 | High Contrast & Dark Mode | Dark background (`bg-gray-900`) with muted text | Text styling uses `text-gray-100` (contrast ratio > 12:1) and badges use high-contrast color pairings satisfying WCAG AA (>= 4.5:1). |
| 10 | Keyboard Focus Management | Modal open / Toast alert appearance | Focus is smoothly shifted to the modal/toast container or dismiss button and restored to triggering element upon closure without keyboard trapping. |

---

## Detailed Requirements Breakdown

### Requirement 1: React Vite Foundation
- **Location**: `g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/frontend`
- **Build & Dev Tooling**:
  - Vite 6+ / 5+ with `@vitejs/plugin-react`
  - TypeScript (`tsconfig.json`) or modern ES6+
  - Tailwind CSS (`tailwindcss`, `postcss`, `autoprefixer`)
  - Lucide React (`lucide-react`) for accessible iconography
- **Layout Architecture**:
  - Two-column responsive dashboard (`grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-screen bg-gray-950 text-gray-100 p-6`).
  - **Left Column (`col-span-12 lg:col-span-4`)**:
    - **Header & Device Status**: Device connection badge (Online / Offline / Mock Mode), ADB daemon health ping.
    - **Hardware Control Panel**:
      - "Trigger ADB Pull" primary button with spinner and status badge.
      - "Capture Screen" secondary button with instant thumbnail preview.
    - **Live Triage Log Console**: Scrollable terminal-style output log displaying timestamped events (`[INFO]`, `[ADB]`, `[DATA]`).
  - **Right Column (`col-span-12 lg:col-span-8`)**:
    - **Video Tags Explorer Header**: Search input by entity/filename, Domain filter dropdown (EDM, Sports Cards, Travel, All).
    - **Data Connect Query Grid / Table**:
      - Table listing: `ID`, `Thumbnail / Filename`, `Domain`, `Entity`, `Viral Features (Badges)`, `Created At`.
      - Interactive tag chips (`#Heavy_Lasers`, `#Bass_Drop`).
      - "Refresh Data" button triggering GraphQL re-fetch.
      - Empty state and Loading skeleton states with proper ARIA `aria-busy` and `aria-live` regions.
- **Acceptance Criteria**:
  - Running `npm run dev` in `frontend` boots dev server on `http://localhost:5173`.
  - UI displays full two-column layout matching design specifications.

---

### Requirement 2: Python FastAPI Bridge
- **Location**: `g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/local_daemon`
- **Technology Stack**:
  - Python 3.13.14
  - Framework: `fastapi >= 0.115.0`, `uvicorn >= 0.32.0`, `pydantic >= 2.10.0`
  - Environment: `python-dotenv` for local `.env` loading (GEMINI.md R26).
  - Absolute imports throughout all modules (GEMINI.md R16).
  - Explicit `requirements.txt` pre-flight dependency specification (GEMINI.md R18).
- **Core Endpoints**:
  1. `POST /api/trigger-adb-pull`:
     - **Request Schema** (`AdbPullRequest`):
       ```json
       {
         "device_id": "optional_device_serial",
         "source_path": "/sdcard/DCIM/Camera",
         "dest_dir": "g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/downloads",
         "mock": false
       }
       ```
     - **Response Schema** (`AdbPullResponse`):
       ```json
       {
         "status": "success",
         "message": "Pulled 3 media items successfully",
         "pulled_files": ["VID_20260827_01.mp4", "VID_20260827_02.mp4"],
         "timestamp": "2026-08-27T11:15:00Z"
       }
       ```
  2. `POST /api/capture-screen`:
     - **Request Schema** (`ScreenCaptureRequest`):
       ```json
       {
         "device_id": "optional_device_serial",
         "mock": false
       }
       ```
     - **Response Schema** (`ScreenCaptureResponse`):
       ```json
       {
         "status": "success",
         "image_base64": "data:image/png;base64,iVBORw0KGgo...",
         "timestamp": "2026-08-27T11:15:00Z"
       }
       ```
  3. `GET /api/status` or `GET /health`:
     - **Response Schema** (`DaemonStatusResponse`):
       ```json
       {
         "status": "online",
         "adb_available": true,
         "adb_version": "1.0.41",
         "connected_devices": ["emulator-5554"]
       }
       ```
- **CORS Configuration**:
  ```python
  from fastapi.middleware.cors import CORSMiddleware

  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Acceptance Criteria**:
  - Running `uvicorn main:app --reload` (or `python -m uvicorn main:app --host 0.0.0.0 --port 8000`) launches FastAPI bridge on `http://localhost:8000`.
  - React button click hits `http://localhost:8000/api/trigger-adb-pull` without CORS errors and receives status 200.

---

### Requirement 3: Firebase Data Connect Integration
- **Location**: `omnichannel_triage_hub/dataconnect/` and `frontend/src/lib/dataconnect/`
- **Database Schema (`schema/schema.gql`)**:
  ```graphql
  type VideoTag @table(name: "video_tags", key: "id", singular: "videoTag", plural: "videoTags") {
    id: Int64! @default(expr: "autoIncrement()")
    filename: String! @unique
    filepath: String!
    domain: String! @default(value: "Unknown")
    entity: String! @default(value: "Unknown")
    viralFeatures: Any! @col(name: "viral_features", dataType: "jsonb") @default(value: [])
    technical: Any! @col(name: "technical", dataType: "jsonb") @default(value: {})
    createdAt: Timestamp! @col(name: "created_at") @default(expr: "request.time")
    updatedAt: Timestamp! @col(name: "updated_at") @default(expr: "request.time")
  }
  ```
- **Operations (`connector/queries.gql` & `connector/mutations.gql`)**:
  - `ListVideoTags`:
    ```graphql
    query ListVideoTags($domain: String) @auth(level: PUBLIC) {
      videoTags(where: { domain: { eq: $domain } }, orderBy: [{ createdAt: DESC }]) {
        id
        filename
        filepath
        domain
        entity
        viralFeatures
        technical
        createdAt
      }
    }
    ```
  - `CreateVideoTag`:
    ```graphql
    mutation CreateVideoTag($data: VideoTag_InsertInput!) @auth(level: PUBLIC) {
      videoTag_insert(data: $data)
    }
    ```
- **Generated SDK Configuration (`connector/connector.yaml`)**:
  ```yaml
  connectorId: triage-connector
  generate:
    javascriptSdk:
      outputDir: "../frontend/src/lib/dataconnect"
      package: "@triage/dataconnect"
  ```
- **Client Integration Pattern (`frontend/src/lib/firebase.ts` & `dataconnect.ts`)**:
  - Initialize Firebase App with project config.
  - Export typed functions `fetchVideoTags()`, `addVideoTag()`.
  - Automatic fallback to mock provider when emulator / cloud backend is unavailable.
- **Acceptance Criteria**:
  - Firebase Data Connect schema compiles with `npx -y firebase-tools@latest dataconnect:compile`.
  - Frontend queries `video_tags` GraphQL schema and renders records in the UI table/grid.

---

### Requirement 4: The Zero-Waste Frontend Audit (`R4`)
- **Mandatory Policy**: GEMINI.md R4 & ORIGINAL_REQUEST §R4.
- **Memory Leak & Detached DOM Node Audit**:
  - **Tooling**: Chrome DevTools MCP (`take_memory_snapshot`), `node compare_snapshots.js`.
  - **Procedure**:
    1. Capture `baseline.heapsnapshot` at initial page load.
    2. Execute 10 consecutive action cycles (e.g. click "Trigger ADB", toggle filter tabs, expand/collapse details).
    3. Revert page to baseline state.
    4. Capture `target.heapsnapshot`.
    5. Run `node compare_snapshots.js baseline.heapsnapshot target.heapsnapshot`.
  - **Standard**: **0 Detached DOM Nodes** (`Detached HTMLDivElement`, `Detached HTMLButtonElement`, etc. delta must equal 0).
  - **Remediation Rules**:
    - Always clean up `useEffect` event listeners, intervals (`clearInterval`), and abort controllers (`AbortController.abort()`).
    - Avoid global array mutations or detached DOM caching.
- **Accessibility (a11y) & Semantic Audit**:
  - **Tooling**: Chrome DevTools MCP (`take_snapshot`), Lighthouse accessibility audit, `a11y-snippets.md`.
  - **Checklist**:
    1. **Semantic Hierarchy**: Single `<h1>` main heading, logical `<h2>` section headings, `<main>`, `<nav>`, `<aside>`, `<section>` landmark elements.
    2. **Accessible Names**: All buttons have non-empty accessible names (text content or `aria-label`).
    3. **Form Association**: Zero orphaned `<input>` / `<select>` elements (`label[for]` or `aria-label` present on 100%).
    4. **Tap Target Sizing**: Minimum 48x48px bounding box on all interactive controls (`min-w-[48px] min-h-[48px]`).
    5. **Color Contrast**: WCAG AA ratio >= 4.5:1 for standard text (e.g. `text-white` on `bg-gray-900`, `text-blue-400` on `bg-gray-950`).
    6. **Keyboard Navigation**: Full Tab navigation cycle, visible focus rings (`focus:ring-2 focus:ring-blue-500 focus:outline-none`).
    7. **Console Health**: 0 console warnings, 0 runtime errors, 0 preserved a11y issues.

---

## Workspace & Environmental Survey

| Environment Aspect | Discovered State | Verification Command | Implications / Action Required |
|-------------------|------------------|----------------------|--------------------------------|
| **Node.js** | `v26.7.0` | `node -v` | Modern Node 26 runtime available. Fully supports ES Modules, Vite 6, Next.js, and modern JS toolchains. |
| **NPM** | `11.19.0` | `npm -v` | Modern npm package manager. Primary tool for dependency management. |
| **PNPM** | Not installed on system PATH | `pnpm -v` (CommandNotFound) | Use standard `npm` / `npx` commands for all frontend operations. |
| **Python** | `3.13.14` (Windows x64) | `python --version` | Python 3.13 available in PATH with full `asyncio`, `typing`, and `dataclasses` support. |
| **PIP** | `26.1.2` | `pip --version` | Up-to-date pip installer. |
| **Installed Python Packages** | `fastapi (0.141.1)`, `uvicorn (0.52.0)`, `pydantic (2.13.4)`, `pytest (9.1.1)`, `pytest-asyncio (1.4.0)`, `httpx (0.28.1)`, `playwright (1.62.0)` | `python -m pip list` | Core FastAPI, Uvicorn, testing, and async HTTP libraries are pre-installed. |
| **ADB (Android Debug Bridge)** | `1.0.41` (Version 37.0.1-15733141) | `adb --version` | Located at `C:\Users\noahp\AppData\Local\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe`. Ready for ADB subprocess execution. |
| **Firebase CLI** | `15.28.1` | `npx -y firebase-tools@latest --version` | Latest Firebase CLI available via `npx`. Full support for `dataconnect:compile`, `dataconnect:sdk:generate`, and emulators. |
| **Chrome DevTools MCP** | Active in runtime environment | Native MCP tools registered | Full support for `take_memory_snapshot`, `take_snapshot`, `click`, `navigate_page`, `evaluate_script` for R4 audit. |
| **Audit Scripts & References** | Available in config plugin directories | `compare_snapshots.js`, `a11y-snippets.md` | Authoritative auditing scripts available for heap snapshot comparison and WCAG evaluation. |

---

## Four-Tier Verification & Testing Methodology

```
┌─────────────────────────────────────────────────────────────┐
│  Tier 4: R4 Zero-Waste Audit & Adversarial Hardening        │
│  - 0 Detached DOM Nodes via Heap Snapshot Comparison        │
│  - 100% WCAG AA Semantic a11y, 48px Tap Targets, Contrast   │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  Tier 3: Full-Stack E2E & Local Daemon Integration          │
│  - React Frontend (Port 5173) ↔ FastAPI Bridge (Port 8000)   │
│  - Real HTTP / CORS Preflight / JSON Response Cycle         │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  Tier 2: Component & Route Integration Tests                │
│  - FastAPI Routes via httpx.AsyncClient / TestClient        │
│  - React Component DOM tests (RTL / Vitest)                 │
│  - Data Connect Schema Compilation (firebase-tools)         │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  Tier 1: Static Analysis, Types & Pure Unit Tests           │
│  - Pydantic Schema Validation & Python Unit Tests (pytest)  │
│  - TypeScript Compilation (tsc --noEmit) & ESLint           │
│  - Pure Model & Utility Function Assertions                 │
└─────────────────────────────────────────────────────────────┘
```

### Tier 1: Static Analysis & Unit Tests
- **Backend Unit Tests (`pytest tests/test_unit.py`)**:
  - Verify `AdbPullRequest`, `AdbPullResponse`, `ScreenCaptureRequest`, `ScreenCaptureResponse`, `DaemonStatusResponse` Pydantic models with valid and invalid payloads.
  - Test ADB command string builder / executor mock isolation.
- **Frontend Type & Lint Check (`npx tsc --noEmit` & Vitest)**:
  - Validate TypeScript types for API payloads and Data Connect schemas.
  - Unit test isolated UI helper functions (date formatters, tag parsers, status badge formatters).
- **Data Connect Schema Syntax Check**:
  - Run `npx -y firebase-tools@latest dataconnect:compile` to statically validate `schema.gql`, `queries.gql`, `mutations.gql`.

### Tier 2: Integration & Contract Tests
- **FastAPI Endpoint Integration Tests (`pytest tests/test_api_integration.py`)**:
  - Execute `POST /api/trigger-adb-pull` with `TestClient` / `httpx.AsyncClient` verifying status 200 and schema validity.
  - Execute `POST /api/capture-screen` verifying base64 image generation.
  - Test error status codes (e.g. 500/503 on mock failure) and error message structures.
- **React Component Integration Tests (Vitest + React Testing Library)**:
  - Render `TwoColumnDashboard`, `DeviceControlPanel`, `VideoTagsViewer`.
  - Simulate user click on "Trigger ADB" and assert API loading state, successful response rendering, and log append.
  - Verify domain filtering updates visible tag items.

### Tier 3: System & Full-Stack Daemon E2E Tests
- **Live Local Bridge E2E (`pytest tests/test_e2e_bridge.py` or Playwright)**:
  - Boot FastAPI daemon on `localhost:8000` via subprocess or test fixture.
  - Boot Vite dev server on `localhost:5173`.
  - Trigger live fetch from `localhost:5173` to `http://localhost:8000/api/trigger-adb-pull`.
  - Assert zero CORS errors, response status 200, and DOM badge update to "Success".

### Tier 4: Zero-Waste Audit & Adversarial Hardening (R4 Audit)
- **Memory Leak & Detached DOM Audit**:
  - Launch application in browser via DevTools / Playwright.
  - Take baseline heap snapshot (`baseline.heapsnapshot`).
  - Execute 10 repeated click & tab switch interaction cycles.
  - Take target heap snapshot (`target.heapsnapshot`).
  - Run `node compare_snapshots.js baseline.heapsnapshot target.heapsnapshot`.
  - **Pass Criterion**: Top growing objects diff contains **0 Detached DOM Elements**.
- **Semantic a11y & WCAG AA Audit**:
  - Execute `a11y-snippets.md` scripts via DevTools or automated runner:
    - **Find Orphaned Form Inputs**: Expect `[]` (empty list).
    - **Measure Tap Target Size**: Expect `width >= 48` and `height >= 48` for all buttons.
    - **Check Color Contrast**: Expect `contrastRatio >= 4.50` for all text elements.
    - **Global Page Checks**: Verify `lang="en"`, non-empty `<title>`, valid `<meta name="viewport">`.
  - Verify keyboard focus cycle: Tab through all interactive elements without focus trap and with visible focus rings.

---

## Traceability Matrix & Acceptance Criteria Mapping

| Acceptance Criterion (from ORIGINAL_REQUEST.md) | Mined Feature & Requirement | Required Implementation Deliverable | Verification Tier & Method |
|---|---|---|---|
| Running `npm run dev` in the frontend directory loads the two-column dashboard on `localhost:5173`. | R1: Feature #1 (Two-Column Layout), Feature #5 (Tailwind CSS) | `frontend/src/App.tsx`, `frontend/vite.config.ts`, `frontend/src/index.css` | Tier 3: HTTP GET `http://localhost:5173` returns 200 and loads HTML containing layout components. |
| Running `uvicorn main:app --reload` launches the Python bridge on `localhost:8000`. | R2: Feature #6 (ADB Pull), Feature #7 (Screen Capture), Feature #8 (Health Check) | `local_daemon/main.py`, `local_daemon/api/routes.py`, `local_daemon/requirements.txt` | Tier 2/3: HTTP GET `http://localhost:8000/health` returns status `online`. |
| Clicking a mock "Trigger ADB" button in the React UI successfully hits the FastAPI endpoint without CORS errors. | R1: Feature #2 (Trigger Action), R2: Feature #9 (CORS Middleware) | `frontend/src/components/DeviceControlPanel.tsx`, `local_daemon/main.py` CORSMiddleware | Tier 3: Live button click sends POST request to `http://localhost:8000/api/trigger-adb-pull` and receives 200 OK. |
| Firebase Data Connect queries `video_tags` PostgreSQL table using GraphQL. | R3: Feature #10 (Schema), Feature #11 (Queries), Feature #13 (Generated SDK) | `dataconnect/schema/schema.gql`, `dataconnect/connector/queries.gql`, `frontend/src/lib/dataconnect/` | Tier 1/2: `dataconnect:compile` succeeds and React component renders queried `video_tags` data. |
| Red Team executes memory leak and accessibility audit to ensure 0 detached DOM nodes and passes semantic a11y checks. | R4: Feature #15 (Zero Detached DOM), Features #16-19 (Semantic a11y) | Clean React component lifecycles, full ARIA labelling, 48px tap targets, WCAG AA contrast | Tier 4: `compare_snapshots.js` confirms 0 detached nodes; a11y snippets confirm 100% compliance. |
