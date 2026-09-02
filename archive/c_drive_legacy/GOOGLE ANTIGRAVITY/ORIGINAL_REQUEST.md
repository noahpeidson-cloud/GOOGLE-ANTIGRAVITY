# Original User Request

## 2026-08-23T13:52:37Z

This is a single self-contained feature; keep it small and focused.

Architect and implement a production-grade Python background daemon (`progress_watchdog.py`) that synchronizes an internal agent state file to a frontend Artifact file in real-time. This solves the "black box" transparency issue by allowing the Antigravity UI to auto-refresh as background agents complete their tasks.

Working directory: G:\My Drive\GOOGLE ANTIGRAVITY
Integrity mode: development

## Requirements

### R1. Debounced File Synchronization
Build a Python script utilizing the `watchdog` library. It must take two CLI arguments: `--source` (the internal agent file, e.g., `progress.md`) and `--target` (the UI artifact, e.g., `task.md`). The script must monitor the source file for modification events (`on_modified`) and immediately mirror its contents to the target file.

### R2. High-Frequency Stream Protection
LLMs write text at extreme frequencies (token-by-token streaming). You MUST implement a strict 1.0-second `debounce` mechanism within the event handler to prevent the script from queueing hundreds of write operations per second, which would crash the frontend UI. 

### R3. Safe Concurrency
Implement safe, atomic file writes (e.g., writing to a temporary file and renaming it, or using appropriate file locking) to ensure the UI never reads a partially written or corrupted artifact during the sync.

## Acceptance Criteria

### Execution & Stability
- [ ] The script successfully launches and remains resident in the background.
- [ ] A programmatic test script proves that rapidly writing 50 lines to the source file within 1 second only triggers a maximum of 1 sync operation to the target file (debouncing verified).
- [ ] The sync operation does not throw `PermissionError` or locking exceptions on Windows when concurrent reads occur.

## 2026-08-24T03:43:21Z

<USER_REQUEST>
# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: [none — teamwork routes from the description]

Build a robust, omnichannel "Sports Card Ecosystem" local web application using Streamlit and SQLite. The system acts as a central hub that accepts ingestion from 4 distinct pipelines (AI Vision photo analysis, Beckett bulk checklists, a Chrome extension bridge, and a sales listing generator), formatting all data into a strict 21-variable schema for Card Ladder CSV export.

Working directory: `g:/My Drive/GOOGLE ANTIGRAVITY/sports_cards/ecosystem_hub`
Integrity mode: development

## Requirements

### R1. The Central Hub (Streamlit + SQLite)
Build a Streamlit dashboard that serves as the visual staging area. It must connect to a SQLite database (`portfolio.db`) that strictly enforces the 21-variable Card Ladder schema defined in the workspace rules.

### R2. The Ingestion Pipelines (AI Vision & Scraper)
Implement a module to process local card images using the Gemini Multimodal API to extract card details. Implement a separate web scraper module (using BeautifulSoup/requests) to parse set checklists from Beckett or Cardboard Connection to allow bulk checkbox ingestion.

### R3. API Bridge & Sales Generator
Implement a local FastAPI endpoint (or Streamlit equivalent) to receive `POST` payloads from a Chrome Extension. Implement a Sales module that reads a row from the database and uses Gemini to generate an SEO-optimized Facebook Marketplace listing string.

### R4. Export Pipeline
Implement a Pandas-driven export function that reads the SQLite database, performs fuzzy string normalization on player/set names, and exports a pristine `CardLadder_Bulk_Upload.csv` with no leading zeros dropped.

## Acceptance Criteria

### Central Hub Verification
- [ ] Running `streamlit run app.py` launches the UI on localhost without errors.
- [ ] A Python test script successfully inserts a mock 21-variable row into `portfolio.db` and retrieves it.

### Ingestion Verification
- [ ] A test script pointing the scraper at a static HTML checklist returns a structured list of at least 3 cards.
- [ ] The AI Vision module contains a mock test function that takes an image path and returns a JSON object matching the 21-variable schema.

### Export Verification
- [ ] The export function successfully generates a `.csv` file from the database.
- [ ] The generated CSV contains exactly the 16 headers required by Card Ladder, and preserves leading zeros.
</USER_REQUEST>

## 2026-08-25T03:59:57Z

<USER_REQUEST>
# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: [none — teamwork routes from the description]

Build an enterprise-grade Media Ingestion & Viral Grading Pipeline that securely pulls uncompressed 4K videos from an Android device to Google Cloud, evaluates their trending potential using Gemini Video understanding, and stores the analytics in BigQuery for a continuous Machine Learning feedback loop. 

Working directory: `g:/My Drive/GOOGLE ANTIGRAVITY/media_pipeline`
Integrity mode: development

## Requirements

### R1. Deep Research Phase (Viral Formula)
Before writing the grading logic, the team must spawn a research subagent to scrape and analyze the web for YouTube Shorts algorithms and EDM viral parameters (e.g., audio drop timing, crowd energy, lighting transitions). Output this formula to a `VIRAL_FORMULA.md` artifact.

### R2. Ingestion Architecture (Deep Research & Implementation)
Conduct a deep research phase evaluating two ingestion paths: 
1. **Google Photos Automation**: Are there existing tools/APIs that can scan a Google Photos library, filter for high-quality videos based on trending parameters, and export them without compression?
2. **Android ADB Wi-Fi Sync**: What is the most fault-tolerant method for wireless raw file extraction (`adb sync` vs `adb pull`, handling drops).
Based on this research, implement the superior ingestion daemon that guarantees zero compression and seamlessly routes the raw `.mp4`/`.jpg` files to Google Cloud Storage.

### R3. GCP Spark & Gemini Omni Video Grading
Implement a PySpark job (designed for Dataproc Serverless) that processes the raw videos in GCS. It must utilize the `gemini-omni-flash-api` to analyze the video/audio and grade it against the `VIRAL_FORMULA` parameters, generating a final "Trending Potential" score.

### R4. BigQuery ML Optimization Loop
Implement the BigQuery integration to sink the Spark grading results into a table. Include the BigQuery ML (`CREATE MODEL`) SQL scripts to train a clustering or regression model on the data, creating an automated loop that learns which video traits actually correlate with virality over time.

## Acceptance Criteria

### Research Verification
- [ ] `VIRAL_FORMULA.md` is generated and contains at least 5 distinct, measurable parameters for grading short-form EDM videos.

### Ingestion Verification
- [ ] A test script running a mock ADB transfer correctly hashes a local dummy file, uploads it to a local/mock GCS bucket, and proves the hashes match exactly (Zero Quality Loss).

### Grading Engine Verification
- [ ] A local PySpark test runs without crashing, processes a mock video payload, and outputs a structured Pydantic/JSON object containing the 5 viral scores.

### BigQuery ML Verification
- [ ] A Python script successfully executes against a mock BigQuery dataset, creates the table schema, and successfully compiles the `CREATE MODEL` SQL statement without syntax errors.

---
*Expecting this to run as a full project team — say so if you want it broken up.*
*Next: when approved → delegate via invoke_subagent (see Delegation Protocol)*
</USER_REQUEST>

## 2026-08-25T05:15:00Z

<USER_REQUEST>
# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Full Engineering Team

Build a daily background daemon using the Google Antigravity SDK that executes a non-destructive system health scan, stores the findings in a local SQLite optimization loop to continuously improve its own accuracy, and utilizes an internal red-team to audit proposed optimizations before requesting human-in-the-loop (HITL) approval.

Working directory: G:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron
Integrity mode: development

## Requirements

### R1. ML Optimization & SQLite Telemetry Loop
Implement the `agent-ml-optimization-loop` pattern using local SQLite as the backend. The script must log all detected anomalies into the database. It must apply a basic ML clustering algorithm (e.g., K-Means via scikit-learn or pandas) to identify recurring patterns over time, generating "textual gradients" to refine what the agent considers "bloat" vs. "active work."

### R2. Historical Session Seeding
The SQLite database must be programmatically seeded on initialization with the exact failure lifelines from the August 23/24 session:
1. **Ghost Daemons:** Unmonitored Next.js/Uvicorn tasks causing socket collisions (`WinError 10048`).
2. **Context Rot:** Planning artifacts older than 24 hours diluting the context window.
3. **Ecosystem Pollution:** Unused `.disabled` plugin directories confusing the crawler.
4. **Secret Zero:** Unresolved placeholder tokens (`your_token_here`) in `.env` files.
5. **Prompt Fatigue:** Hardcoded procedural rules bloating the `GEMINI.md` manifest.

### R3. Strict Data Loss Prevention (HITL)
Adhere strictly to the `accidental-data-loss-prevention` skill. The execution must be 100% read-only and analytical. It must compile a proposed optimization report and halt. It is strictly forbidden from executing structural deletions or killing tasks autonomously.

### R4. Internal Red-Team Scrutiny
Before presenting the final report to the user, the script must invoke a secondary `architecture-red-team` subagent to rigorously challenge the ML's proposed optimizations, ensuring it is not hallucinating false positives (e.g., flagging active config files as dead code).

## Acceptance Criteria

### Execution & Safety
- [ ] The core Python script executes end-to-end and exits with code 0 against a mock environment.
- [ ] A static code check verifies that destructive commands (`os.remove`, `shutil.rmtree`, `taskkill`) are entirely absent from the script's automated execution path.
- [ ] The SQLite telemetry database is successfully initialized and seeded with the 5 historical session callouts.
- [ ] The script successfully outputs a daily `.md` report containing the red-team's audit of the ML's findings.
</USER_REQUEST>

## 2026-08-26T01:46:06Z

<USER_REQUEST>
# Teamwork Project Prompt

Build an enterprise-grade "Improved Workflow" unified system that includes: (1) A custom Antigravity SDK Agent with ML optimization loops to automate the Android/Viral Trend pipelines, (2) a centralized modern web dashboard to unify all tools, and (3) a massive refactor of existing pipelines to add advanced troubleshooting and error recovery.

Working directory: `g:/My Drive/GOOGLE ANTIGRAVITY/unified_ops_hub`
Integrity mode: development

**USER DIRECTIVE:** "Please do this in strategic passes so we aren't over utilized and work your way through it correctly." (Execute the requirements sequentially rather than trying to build the entire monolith concurrently).

## Requirements

### R1. Unified Next.js Command Center
Build a Next.js (React) application serving as the master visual dashboard for both the Sports Card Ecosystem and the Media Ingestion pipelines. It must follow `modern-web-guidance` best practices for layout and performance.

### R2. Antigravity ML Agent (Autonomy Loop)
Using the `google-antigravity-sdk`, build an autonomous orchestrator script (`ml_agent.py`) that monitors the `viral-trend-pipeline`. It must implement `agent-ml-optimization-loop` principles (SQLite telemetry, K-Means clustering) to dynamically analyze scraping performance and self-adjust its execution policy.

### R3. Android CLI Automation Integration
The ML Agent must utilize the `android-cli` tools to fully automate headless mobile scraping for viral trends, bypassing the brittleness of standard web DOM scraping.

### R4. Pipeline Refactor & Resiliency
Refactor the existing Python backend daemons to implement deep `troubleshooting` logic. The system must include automatic port-collision resolution, Dead Letter Queues (DLQ) for failed ML grades, and robust fallback states if an external API fails.

## Acceptance Criteria

*(Enforcing Rule R2: The Zero-Discretion Mandate)*

### Programmatic Verification (Loud Assertions)
- [ ] The team MUST write a deterministic test suite (e.g., PyTest for the agent/backend, Jest/Cypress for Next.js) before writing implementation code.
- [ ] Running `npm run test` on the Next.js app must pass all component rendering and state integration tests.
- [ ] Running `pytest test_ml_agent.py` must successfully execute a mock ML optimization loop, inserting a telemetry record into SQLite and reading it back.
- [ ] Running a programmatic crash-test script against the refactored backend must successfully catch the simulated failure and route the payload to the Dead Letter Queue without crashing the daemon.
</USER_REQUEST>

## 2026-08-26T05:01:44Z

<USER_REQUEST>
# Build the Media Studio Module

Working directory: `g:/My Drive/GOOGLE ANTIGRAVITY/unified_ops_hub`
Integrity mode: development

We are building a Human-in-the-loop "Media Studio" into the existing unified ops hub. The user must be able to view 3 AI-generated cuts, use advanced Instagram-style editing tools in the browser, and render the final video headlessly via FFmpeg.

## Requirements

### R1. AI Proxy & Cut Generator (Backend)
Modify `ml_agent/ml_agent.py` (or create a new module `ml_agent/editor.py`) to process ingested videos.
1. Use `subprocess` and `ffmpeg` to generate a 720p proxy (`.mp4`) of the original video.
2. Generate a JSON metadata payload defining 3 cuts:
   - `hype_drop`: Trimmed to the loudest audio peak, cropped to 9:16.
   - `cinematic`: Full length, 16:9.
   - `raw_pov`: Full length, original aspect ratio.

### R2. Headless FFmpeg Renderer (Backend)
Create `gateway/renderer.py` and hook it into `gateway/app.py`.
- Expose a `POST /api/v1/media/render` endpoint.
- It must accept a JSON payload containing: `source_file`, `in_point`, `out_point`, `crop_ratio` (9:16 or 16:9), and an optional `text_overlay`.
- It must compile and execute the corresponding `ffmpeg` command against the 4K raw file to produce the final render in a `renders/` directory.

### R3. Media Studio Web Editor (Frontend)
Build `MediaStudio.tsx` inside `dashboard/src/components/`.
- Must load the 720p proxy in an HTML5 video player.
- Must have 3 buttons to toggle between the base cuts (Hype, Cinematic, Raw).
- Must have a dual-handle trim slider.
- Must have a "Render & Publish" button that sends the final coordinates to the `/api/v1/media/render` endpoint.

## Acceptance Criteria
- [ ] Backend: A test script `test_ffmpeg_renderer.py` successfully sends a mock edit payload and FFmpeg generates an actual (or mock) `.mp4` file.
- [ ] Frontend: `npm run test` passes for the new `MediaStudio` component.
</USER_REQUEST>

## 2026-08-26T06:47:46Z

<USER_REQUEST>
# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: A full agent team (parallel execution)

Build a Google Photos-style Media Gallery section for the Unified Ops Hub dashboard. The gallery must ingest and display albums of raw media pulled by the ingestion pipeline, allowing the user to visually browse, select, and trigger specific albums for Gemini Omni ML grading.

Working directory: `G:/My Drive/GOOGLE ANTIGRAVITY/unified_ops_hub`
Integrity mode: development

## Requirements

### R1. SQLite Catalog Database
Initialize a local SQLite database (`media_catalog.db`) with schemas for `Albums` and `Media`. It must track local proxy paths on the G: Drive, upload status, and grading results.

### R2. Media Gallery UI (Next.js)
Build a responsive, Google Photos-style gallery view that queries the SQLite database to organize and display local proxy videos into Albums. It must support zero-latency scrubbing of local files.

### R3. Grading Trigger Mechanism
Provide a UI mechanism (checkboxes/selection state) allowing the user to select an album or specific videos, and a "Grade Selected" button that dispatches a POST request to trigger the Spark/Gemini ML grading pipeline.

## Acceptance Criteria

### Backend Database Verification
- [ ] A Python test script successfully creates the `media_catalog.db` schema, inserts a mock Album containing 3 mock Media entries (with local G: drive paths), and retrieves them via a `SELECT` join.

### UI Rendering & Trigger Verification
- [ ] A programmatic test (e.g., using `testing-library/react` or a mock DOM render) verifies that the Gallery component successfully maps over a list of mock Media objects and renders corresponding HTML `<video>` elements.
- [ ] A programmatic test confirms that clicking the "Grade Selected" button successfully fires a mock API POST request containing the selected Media IDs.

---
*Expecting this to run as a full project team — say so if you want it broken up.*
</USER_REQUEST>

## 2026-08-27T10:18:49Z

<USER_REQUEST>
# Teamwork Project Prompt

> Status: Launched
> Requested team: Firebase & Postgres Data Engineering Squad

Migrate the local Quick Share AI pipeline's database from SQLite to a production Google Cloud SQL PostgreSQL database using Firebase Data Connect. 

Working directory: `g:/My Drive/GOOGLE ANTIGRAVITY/quick_share_ai_loop`

## Requirements

### R1. Database Refactoring (`database_sink.py`)
Rewrite the `database_sink.py` script to connect to a remote PostgreSQL database via `psycopg2`. It must authenticate using environment variables loaded from the `.env` file (e.g., `PG_HOST`, `PG_USER`, `PG_PASSWORD`, `PG_DB`).

### R2. PostgreSQL Schema Definition
Create a `schema.sql` (or Firebase Data Connect `schema.gql` equivalent) that replicates the existing SQLite `video_tags` table, but uses proper Postgres data types (e.g., `JSONB` for the `viral_features` and `technical` arrays instead of stringified JSON).

### R3. Secret Management & Guardrails
Adhere to the workspace rule **R26** (The Background Daemon Auth Guardrail). The Python script must fail fast if the PostgreSQL environment variables are missing, preventing silent data loss.

### R4. The Red Team Audit (`architecture-red-team`)
Before finalizing the implementation, the LangGraph Red Team node must audit the connection pool strategy in `database_sink.py` to ensure it does not leak connections to the Cloud SQL instance during long-running daemon operations.

## Acceptance Criteria
- [ ] A mock test script successfully connects to a local/mock Postgres instance and inserts a tagged 4K video payload.
</USER_REQUEST>

## 2026-08-27T11:10:51Z

<USER_REQUEST>
# Teamwork Project Prompt

> Status: Launched
> Requested team: Full-Stack React & Python Squad

Build the foundation of the "Omnichannel Triage Hub" web application based on the `triage_ui_mockup.html` design. 

Working directory: `g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub`

## Architectural Decisions (For Sustainability & Effectiveness)
Based on your request for maximum long-term sustainability:
1. **Frontend:** React (Vite) + Tailwind CSS. This perfectly matches the HTML mockup and is the industry standard for maintainability. 
2. **Local Bridge:** A Python FastAPI server. It isolates the messy OS-level code (ADB pulls, hotkey listeners) into clean REST endpoints. React is entirely decoupled from the OS.
3. **Database Access:** The React frontend will use the **Firebase Data Connect React SDK**. This provides auto-generated, strictly-typed GraphQL hooks directly to our new PostgreSQL database, bypassing the need to write endless Python REST endpoints just to fetch data.

## Requirements

### R1. The React Vite Foundation
Initialize a React Vite frontend in `g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/frontend`. Configure Tailwind CSS. Replicate the two-column layout from `triage_ui_mockup.html` using React components.

### R2. The Python FastAPI Bridge
Initialize a FastAPI project in `g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/local_daemon`. It must expose a `POST /api/trigger-adb-pull` endpoint and a `POST /api/capture-screen` endpoint.

### R3. Firebase Data Connect Integration
Configure the React frontend to initialize Firebase. Generate the Firebase Data Connect SDK (`@firebase/data-connect`) so the frontend can query the `video_tags` PostgreSQL table directly using GraphQL.

### R4. The Zero-Waste Frontend Audit (`R4`)
Before final delivery, the Red Team must execute a memory leak and accessibility audit to ensure the frontend has 0 detached DOM nodes and passes semantic a11y checks.

## Acceptance Criteria
- [ ] Running `npm run dev` in the frontend directory loads the two-column dashboard on `localhost:5173`.
- [ ] Running `uvicorn main:app --reload` launches the Python bridge on `localhost:8000`.
- [ ] Clicking a mock "Trigger ADB" button in the React UI successfully hits the FastAPI endpoint without CORS errors.
</USER_REQUEST>

