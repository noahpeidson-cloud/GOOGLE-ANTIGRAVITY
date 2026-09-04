# Project: Omnichannel Triage Hub

## Architecture
The Omnichannel Triage Hub is a decoupled desktop/web application suite designed for live media ingestion, device screen capture, collision resolution, and metadata indexing.

```
+-------------------------------------------------------------------------------+
|                             React Vite Frontend                               |
|                            (http://localhost:5173)                            |
|  +-------------------------------------+-----------------------------------+  |
|  |     Left Column (Phone Link Feed)   |  Right Column (Collision Queue)   |  |
|  |  - 9:16 Video Feed (Placeholder/Liv)|  - Side-by-side comparison cards  |  |
|  |  - Gemini Vision analysis badges    |  - Auto-trash / Keep 4K actions   |  |
|  |  - "Trigger ADB Pull" Action Button |  - Video Tags GraphQL Browser     |  |
|  +-------------------------------------+-----------------------------------+  |
|         │ (Fetch / REST)                                   │ (GraphQL)        |
+─────────┼──────────────────────────────────────────────────┼──────────────────+
          ▼                                                  ▼
+─────────────────────────────────+        +────────────────────────────────────+
|      Python FastAPI Bridge      |        |     Firebase Data Connect SDK      |
|     (http://localhost:8000)     |        |      (@firebase/data-connect)      |
|  - POST /api/trigger-adb-pull   |        |  - Query: ListVideoTags            |
|  - POST /api/capture-screen     |        |  - Mutation: CreateVideoTag        |
|  - GET /api/health              |        |  - Schema: video_tags (PostgreSQL) |
|  - Auto-detect Real/Mock ADB    |        +────────────────────────────────────+
|  - Procedural Media Generator   |
+─────────────────────────────────+
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | React Vite App Scaffolding | Initialize React + Vite in `frontend/` with TypeScript / modern tooling | M1 | R1 |
| 2 | Tailwind CSS & Theme Tokens | Configure Tailwind with dark-mode theme variables matching `triage_ui_mockup.html` | M1 | R1 |
| 3 | Two-Column Grid Layout | Implement 12-column grid (`col-span-4` left, `col-span-8` right) with fixed height & custom scrollbars | M1 | R1 |
| 4 | Header & Live Status Badges | ADB connection badge (pull progress) and Windows Phone Link badge with live pulse indicator | M1 | R1 |
| 5 | Phone Link Live Feed Component | 9:16 aspect video container, live capture indicator, hotkey badge (`Ctrl+Shift+T`), and entity tagging card | M1 | R1 |
| 6 | Collision Queue Component | Comparison card header with warning badge, 4K ADB vs 1080p Takeout side-by-side stats, and resolution button | M1 | R1 |
| 7 | Mock Media Asset Generation | Procedural 9:16 placeholder video/image assets via `imageio_ffmpeg` (Rule R21) | M1 | R1 / R21 |
| 8 | FastAPI Bridge Project Setup | Initialize FastAPI project in `local_daemon/` with Uvicorn, Pydantic, and absolute imports | M2 | R2 |
| 9 | CORS Middleware Configuration | Enable CORS on FastAPI for `http://localhost:5173` with all standard HTTP methods & headers | M2 | R2 |
| 10 | Trigger ADB Pull Endpoint | `POST /api/trigger-adb-pull` accepting path/dest options with real ADB command execution or realistic mock fallback | M2 | R2 |
| 11 | Screen Capture Endpoint | `POST /api/capture-screen` executing `adb exec-out screencap` or generating mock capture frame | M2 | R2 |
| 12 | Health & Status Endpoint | `GET /api/health` returning bridge status, ADB device connectivity status, and version | M2 | R2 |
| 13 | Firebase Data Connect Configuration | `dataconnect.yaml`, `connector.yaml`, and schema definition in `dataconnect/` | M3 | R3 |
| 14 | PostgreSQL `video_tags` Schema | GQL table schema for `video_tags` with id, filename, filepath, domain, entity, viral_features, technical | M3 | R3 |
| 15 | GraphQL Queries & SDK Generation | Define queries/mutations and configure `@firebase/data-connect` client SDK generation | M3 | R3 |
| 16 | React Firebase Client Initialization | Configure Firebase app init and Data Connect connector client in React frontend with emulator fallback | M3 | R3 |
| 17 | React UI Bridge Action Integration | Wire mock "Trigger ADB Pull" and "Capture Screen" buttons in React UI to FastAPI endpoints | M4 | R1 / R2 |
| 18 | E2E Integration Test Suite | Full suite testing API connectivity, CORS requests, schema queries, and UI components (Tiers 1-4) | M4 | All |
| 19 | Zero-Waste Memory Leak Audit | Profile and test frontend for 0 detached DOM nodes and clean component teardown | M5 | R4 |
| 20 | Zero-Waste Accessibility (a11y) Audit | Audit semantic HTML, WCAG AA contrast (>=4.5:1), tap targets (>=48px), and keyboard focus states | M5 | R4 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | React Vite UI Foundation | Frontend scaffold, Tailwind setup, two-column layout, components, and media placeholders | none | DONE |
| M2 | FastAPI Local Daemon Bridge | FastAPI project, CORS middleware, `/api/trigger-adb-pull`, `/api/capture-screen`, health check | none | DONE |
| M3 | Firebase Data Connect Integration | Schema definition, GQL queries, SDK generation configuration, React client initialization | M1 | DONE |
| M4 | E2E Integration & Verification | Wire UI actions to FastAPI, execute 4-tier E2E tests, verify CORS and live flows | M1, M2, M3 | DONE |
| M5 | Zero-Waste Frontend Audit (R4) | Memory leak audit (0 detached DOM nodes) and accessibility audit (WCAG AA) | M4 | DONE |

## Interface Contracts

### Frontend ↔ FastAPI Local Daemon
- Base URL: `http://localhost:8000`
- Headers: `Content-Type: application/json`
- Endpoints:
  - `POST /api/trigger-adb-pull`
    - Request: `{"device_id": string | null, "source_path": string | null, "destination_path": string | null, "mock": boolean}`
    - Response: `{"success": boolean, "status": string, "bytes_transferred": number, "total_bytes": number, "file_path": string, "duration_ms": number}`
  - `POST /api/capture-screen`
    - Request: `{"device_id": string | null, "format": "png" | "jpeg"}`
    - Response: `{"success": boolean, "image_base64": string, "width": number, "height": number, "timestamp": string}`
  - `GET /api/health`
    - Response: `{"status": "ok", "adb_connected": boolean, "device_count": number, "devices": string[]}`

### Frontend ↔ Firebase Data Connect
- Connector: `omnichannel-connector`
- Types:
  ```graphql
  type VideoTag {
    id: Int64!
    filename: String!
    filepath: String!
    domain: String!
    entity: String!
    viralFeatures: Any!
    technical: Any!
    createdAt: Timestamp!
    updatedAt: Timestamp!
  }
  ```
- Operations:
  - `query ListVideoTags`: returns `[VideoTag!]!`
  - `mutation CreateVideoTag(data: VideoTagInput!)`: returns `VideoTag!`

## Code Layout
- `g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/`
  - `frontend/`
    - `package.json`
    - `vite.config.ts`
    - `tailwind.config.js`
    - `postcss.config.js`
    - `index.html`
    - `src/`
      - `main.tsx`
      - `App.tsx`
      - `index.css`
      - `components/`
        - `Header.tsx`
        - `PhoneLinkFeed.tsx`
        - `CollisionQueue.tsx`
        - `VideoTagList.tsx`
      - `lib/`
        - `api.ts`
        - `firebase.ts`
        - `dataconnect/`
      - `public/`
        - `placeholder.mp4`
        - `placeholder.png`
  - `local_daemon/`
    - `requirements.txt`
    - `main.py`
    - `adb_service.py`
    - `media_generator.py`
    - `models.py`
    - `tests/`
      - `test_api.py`
      - `test_adb.py`
  - `dataconnect/`
    - `dataconnect.yaml`
    - `schema/`
      - `schema.gql`
    - `connector/`
      - `connector.yaml`
      - `queries.gql`
      - `mutations.gql`
  - `tests/`
    - `e2e_integration_test.py`
    - `a11y_memory_audit.js`
