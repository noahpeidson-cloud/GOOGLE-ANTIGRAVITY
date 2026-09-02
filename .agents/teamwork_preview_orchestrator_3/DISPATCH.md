## 2026-08-29T12:52:02Z

User Request:
Weave the fragmented IDE components into a cohesive architecture by extracting the Firebase Data Connect database to a shared library and centralizing asynchronous event processing.

Requirements:
1. R1. Shared Database Extraction:
   Lift the `dataconnect/` schema out of `omnichannel_triage_hub` and move it to the workspace root as a shared package. This must allow both the React frontend and Python backend scripts across all tracks to seamlessly query the PostgreSQL `video_tags` schema.
2. R2. Centralized SQLite Event Bus (Non-Disruptive):
   Refactor the FastAPI local daemon to insert long-running jobs (like ADB pulls) into the `unified_ops_hub_dlq.db` SQLite queue.
   CRITICAL GUARDRAIL: Do NOT modify `daemon_orchestrator.py`, as another session is actively refactoring the Control Plane. Instead, create a strictly isolated `media_event_bus.py` consumer that polls the new queue.
3. R3. Universal ML Telemetry (Non-Disruptive):
   Extract the `@hooks.post_turn` telemetry function from `deployment_agent.py` into a new shared `base_agent.py` wrapper.
   CRITICAL GUARDRAIL: Create the wrapper but do NOT inject it into `mastermind_agent.py` or `.agents/context_engine/` files, as peer sessions are actively modifying them. Apply it only to the new `media_event_bus.py`.
4. R4. Cross-Session Safety:
   CRITICAL GUARDRAIL: You must absolutely avoid modifying any files in the `quick_share_ai_loop` directory (actively locked and being refactored by another session). Additionally, avoid interfering with the Control Plane orchestrator refactoring (`daemon_orchestrator.py` or LangGraph architectures) or any UI components related to `video_reviewer.html` (locked by the "ML Video Editing Styles" session).

Acceptance Criteria:
- The `dataconnect/` schema is moved to the workspace root and can be successfully queried.
- The React app's `api.ts` triggers background jobs via SQLite insertions.
- `media_event_bus.py` successfully polls `unified_ops_hub_dlq.db` without touching `daemon_orchestrator.py`.
- `base_agent.py` is created and successfully imported by `media_event_bus.py`, leaving peer agents untouched.
- Cross-Session Safety Confirmed: Verified that absolutely zero changes were made to `quick_share_ai_loop/`, `video_reviewer.html`, or existing Control Plane logic.
