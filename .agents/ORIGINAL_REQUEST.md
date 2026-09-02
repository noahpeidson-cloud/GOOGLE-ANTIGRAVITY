# Original User Request

## Initial Request — 2026-08-22T23:51:55Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Requested team: Small, focused team for end-to-end Python integration tests

This project establishes a comprehensive Python integration test suite to validate the "Viral Trend Pipeline" (which uses SQLite, BigQuery ML, and headless Chrome/Android extraction). The tests should mock the extraction layer and verify data ingestion, garbage collection, and BigQuery payload generation.

Working directory: ~/teamwork_projects/viral_trend_pipeline_tests
Integrity mode: benchmark

## Requirements

### R1. Extraction Mocking
Write robust mock fixtures for both the Chrome DevTools extraction (yielding mock TikTok/YouTube tags) and Android CLI extraction (yielding mock Instagram UI trees).

### R2. SQLite Mark-and-Sweep Validation
Implement a test that seeds a local `trends.db` with data spanning 30 days. Verify that the garbage collection logic successfully purges rows older than 14 days while retaining the active rolling window.

### R3. BigQuery Payload Formatting
Write tests to verify that the unnested, normalized tag arrays match the exact JSON schema expected by BigQuery's `AI.FORECAST` and `AI.KEY_DRIVERS` functions (e.g., ensuring case preservation, deduplication, and proper data types).

## Acceptance Criteria

### Test Execution
- [ ] Running `pytest` executes all tests without hanging.
- [ ] The SQLite test confirms exact row counts before and after the sweep.
- [ ] The mock extractors yield deterministic JSON structures without attempting real network requests.
- [ ] The test suite completes in under 10 seconds.

## Follow-up — 2026-08-25T05:39:31Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Small, focused team

This project is Phase 1 of the Omnichannel architecture migration. You will refactor the existing `agy_chrome_extension` into a pure headless Manifest V3 background worker that acts strictly as a message passer, removing all brittle DOM scraping logic. The actual extraction will now be handled externally via the Chrome DevTools MCP Accessibility Tree (`a11y-debugging`).

Working directory: ~/teamwork_projects/agy_chrome_extension_headless
Integrity mode: development

## Requirements

### R1. Manifest V3 Headless Compliance
Convert the extension to use a Manifest V3 Service Worker. Remove any popup UIs, content scripts that perform DOM scraping, and `eval()` calls. The extension must operate silently in the background.

### R2. Secure Message Passing Interface
Implement a secure `chrome.runtime.onMessageExternal` or Native Messaging listener. The extension's only job is to receive capture triggers from the local Python agent and pass them along, or proxy responses. It must NOT execute the actual data extraction (which is now handled by the Python MCP agent reading the Accessibility Tree).

## Acceptance Criteria

### Security & Compliance
- [ ] `manifest.json` specifies `"manifest_version": 3`.
- [ ] No `content_scripts` are used for DOM traversal or scraping.
- [ ] The `background.js` service worker loads without throwing CSP (Content Security Policy) errors.

### Message Routing
- [ ] A test script (`test_messaging.py`) successfully sends a ping to the extension's background worker and receives a deterministic acknowledgement payload without triggering any UI.

---
*Next: when approved → delegate via invoke_subagent (see Delegation Protocol)*

## Follow-up — 2026-08-27T21:17:56Z

[Project description: An Antigravity workspace refactor to build a top-down, unified "Well-Oiled Machine". We will implement the Hierarchical Supervisor Pattern (mirroring LangGraph/MetaGPT industry standards) to consolidate all standalone agents into a single Control Plane.]

Working directory: `~/teamwork_projects/antigravity_control_plane`

## Requirements

### R1. The Top-Down Supervisor (Control Plane)
Build a central routing agent (The Supervisor) that holds the global state. Instead of the user tracking 15 different skills, the Supervisor receives the high-level intent and mathematically routes it to the correct subsystem.
- **Routing Engine:** Use a Decision-First Hybrid pattern. The Supervisor MUST use `with_structured_output` to classify intent and select the destination. It must NOT use tool calling for routing.

### R2. Stateless Worker Subsystems
Convert the fragmented, overlapping agents (Social Deployer, Mobile Zero-Touch, Deep Research) into isolated, stateless worker nodes that only execute when called by the Supervisor.
- **Action Engine:** Worker nodes MUST use `bind_tools()` to execute actions.
- **Handoff Protocol:** Worker nodes MUST return control to the Supervisor using the LangGraph `Command` object (`Command(update={state}, goto='supervisor')`) to ensure atomic state updates and transitions. Do not use legacy conditional edges for handoffs.

### R3. Context Pruning & State Management
Implement typed state management between nodes to prevent context bloat.
- **Checkpointer:** You MUST use PostgreSQL (via `psycopg_pool`) as the state management backend to ensure production concurrency, rather than SQLite.

## Verification Resources
You must write a deterministic test suite (`test_orchestrator.py`) using `pytest` that programmatically verifies the Supervisor logic. It must mock the worker nodes and assert that the routing state machine correctly delegates intents (e.g., "Deploy this to Facebook" -> Social Worker, "Click the button in Termux" -> Mobile Worker).

## Acceptance Criteria

### Architectural Integrity
- [ ] The workspace contains exactly ONE entrypoint orchestrator script (`supervisor.py`).
- [ ] Worker agents cannot talk to each other directly; they return their output to the global state.
- [ ] `pytest test_orchestrator.py` passes with 100% success, proving the DAG routing works without infinite loops.

## Follow-up — 2026-08-29T12:51:11Z

<USER_REQUEST>
# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: [none — teamwork routes from the description]

Project description: Weave the fragmented IDE components into a cohesive architecture by extracting the Firebase Data Connect database to a shared library and centralizing asynchronous event processing.

Working directory: G:\My Drive\GOOGLE ANTIGRAVITY

## Requirements

### R1. Shared Database Extraction
Lift the `dataconnect/` schema out of `omnichannel_triage_hub` and move it to the workspace root as a shared package. This must allow both the React frontend and Python backend scripts across all tracks to seamlessly query the PostgreSQL `video_tags` schema.

### R2. Centralized SQLite Event Bus (Non-Disruptive)
Refactor the FastAPI local daemon to insert long-running jobs (like ADB pulls) into the `unified_ops_hub_dlq.db` SQLite queue. **CRITICAL GUARDRAIL:** Do NOT modify `daemon_orchestrator.py`, as another session is actively refactoring the Control Plane. Instead, create a strictly isolated `media_event_bus.py` consumer that polls the new queue.

### R3. Universal ML Telemetry (Non-Disruptive)
Extract the `@hooks.post_turn` telemetry function from `deployment_agent.py` into a new shared `base_agent.py` wrapper. **CRITICAL GUARDRAIL:** Create the wrapper but do NOT inject it into `mastermind_agent.py` or `.agents/context_engine/` files, as peer sessions are actively modifying them. Apply it only to the new `media_event_bus.py`.

### R4. Cross-Session Safety
**CRITICAL GUARDRAIL:** The teamwork orchestrator must absolutely avoid modifying any files in the `quick_share_ai_loop` directory (which is actively locked and being refactored by the "Music Baptism Image Concepts" session). Additionally, avoid interfering with the Control Plane orchestrator refactoring (`daemon_orchestrator.py` or LangGraph architectures) or any UI components related to `video_reviewer.html` (locked by the "ML Video Editing Styles" session).

## Acceptance Criteria

### Execution & Integration
- [ ] The `dataconnect/` schema is moved to the workspace root and can be successfully queried.
- [ ] The React app's `api.ts` triggers background jobs via SQLite insertions.
- [ ] `media_event_bus.py` successfully polls `unified_ops_hub_dlq.db` without touching `daemon_orchestrator.py`.
- [ ] `base_agent.py` is created and successfully imported by `media_event_bus.py`, leaving peer agents untouched.
- [ ] **Cross-Session Safety Confirmed:** Verified that absolutely zero changes were made to `quick_share_ai_loop/`, `video_reviewer.html`, or existing Control Plane logic.

---
*Next: when approved → delegate via invoke_subagent (see Delegation Protocol)*
</USER_REQUEST>
