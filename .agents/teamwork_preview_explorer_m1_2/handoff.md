# Handoff Report: Evaluation of Legacy Orchestrators & Dashboards
**Agent**: `teamwork_preview_explorer_m1_2`  
**Working Directory**: `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_2`  
**Handoff Type**: Hard (Task Complete)  
**Date**: 2026-09-04  

---

## 1. Observation

Direct observations from read-only examination of the 7 target files and companion implementations:

### A. Orchestrators
1. **`polyglot_orchestrator.py`**:
   - Lines 11-12 & 52-64: Uses `google.antigravity` SDK (`Agent`, `LocalAgentConfig`, `types`). Sets root router model to `gemini-3.7-flash` with `retry_config=types.RetryConfig.benchmark()`.
   - Lines 29-46: Defines two subagents: `editor_agent` using `model="anthropic/claude-5-sonnet-20260220"` with `RUN_COMMAND` capability, and `publisher_agent` using `model="gemini-3.7-flash"`.
   - Lines 74-82: Writes output to relative path `"draft_state.json"` with `"status": "AWAITING_HUMAN_COMMIT"` for human review.
   - Lines 86-93: Catches exceptions, opens relative SQLite connection `"media_manifest.sqlite"`, and executes `UPDATE assets SET status = 'QUARANTINED' WHERE asset_id = ?`, swallowing error traces.

2. **`orchestrator.py`**:
   - Lines 105-232: Defines dataclass `QCReport` and function `verify_media_file()`. Executes `ffmpeg -i <file> -vn -af ebur128=peak=true -f null -` and uses regular expressions to parse loudness from stderr:
     `re.search(r"Integrated loudness:\s+I:\s+([-\d\.]+)\s+LUFS", proc.stderr)` and `re.search(r"Peak:\s+True:\s+([-\d\.]+)\s+dBFS", proc.stderr)`. Asserts integrated loudness in `[-15.0, -13.0]` LUFS and true peak `<= -1.5` dBTP. Enforces duration `<= 59.1s` and resolution `1080x1920`.
   - Lines 238-303: `run_auto_drop_detection` runs Librosa/RMS analysis exclusively on extracted uncompressed `.wav` files, bypassing demuxing and parsing 4K video files.
   - Lines 309-468 & 470-658: Two-phase architecture (`run_ingestion_phase` and `run_render_phase`) separated by an `AssetStatus.AWAITING_REVIEW` database and filesystem staging gate.
   - Lines 1-1198: Monolithic 1,198-line script importing 8 local modules (`config`, `ffmpeg_processor`, `ingest_assets`, `metadata_tracker`, `audio_dsp`, `youtube_publisher`, `samsung_ingest`).

3. **`remote_trigger.py`**:
   - Lines 851-935: `stream_video_range()` implements HTTP 206 Partial Content range streaming, parsing `bytes=start-end`, generating 64KB chunks (`iter_file_chunk`), and returning `StreamingResponse` with `Content-Range: bytes {start}-{end}/{file_size}` and `Accept-Ranges: bytes`.
   - Lines 432-672: `PipelineJobManager` maintains an `asyncio.Lock()` mutex. If a job is active, `trigger()` returns HTTP 409 Conflict with active job telemetry. Spawns `asyncio.create_subprocess_exec` executing `orchestrator.py pipeline`, streaming `stdout` and `stderr` into an in-memory `deque(maxlen=2000)` ring buffer.
   - Lines 633-671: `cancel_active_job()` terminates active process via `proc.terminate()`, awaits up to 3.0s, falls back to `proc.kill()`, and updates state to `CANCELLED`.
   - Lines 677-809: `discover_pending_clips()` recursively crawls the filesystem (`rglob("*")`) across 4 folders on every request to find proxies and raw clips, rather than querying `media_manifest.sqlite`.

### B. Dashboards
4. **`index.html`**:
   - Lines 1-2494: Massive 2,494-line single-file monolith containing 1,200 lines of CSS, 400 lines of HTML, and 900 lines of JavaScript.
   - Lines 1422-1456: Contains SVG Safe-Zone masks for YouTube Shorts (`900x1270 px` with `880x340` bottom hazard and `100x380` right hazard) and TikTok (`920x1310 px` with `890x380` bottom hazard and `90x520` right hazard).
   - Lines 826-895 & 1926-1994: Custom scrubber with pointer-capture drag handles (`start-trim-handle`, `end-trim-handle`), draggable region, and keyboard shortcuts (Space, Arrow keys, D).
   - Lines 1585-1590 & 2323-2334: If duration `> 59.00s`, turns duration display amber, unhides warning banner, and activates a "Clamp to 59.00s" button.
   - Lines 1658-1670: `generatePeakData()` generates synthetic sine/random numbers instead of reading true audio peak data.

5. **`dashboard_v2.html` & `static/dashboard.js`**:
   - `dashboard_v2.html` (81 lines) delegates logic to `static/dashboard.js` (318 lines).
   - `static/dashboard.js:1`: Hardcodes `const API_BASE = "http://127.0.0.1:9067";` (conflicting with port 8000 and port 9051).
   - Lines 283-313: `pollDraftState()` periodically polls `/api/draft_state`. When `"AWAITING_HUMAN_COMMIT"` is detected, displays `draftConcept` and `draftSummary`. Clicking `#btnCommitRender` sends `POST /api/commit_render` to execute the DaVinci Resolve render.

6. **`council_ui.html`**:
   - Lines 275-296: Models 5 personas: Hook Architect (🪝, `#ff3366`), Kinetic Editor (⚡, `#00f0ff`), Vibe Curator (🔮, `#bf00ff`), Retention Hacker (⏱️, `#00ff66`), Sound Seeder (🔥, `#ffaa00`).
   - Line 322: Hardcodes endpoint `http://127.0.0.1:9051/api/council_think`.
   - Lines 346-373: Defines rich animated `renderCouncil(dialogue, syntheticPrompt)` function.
   - Lines 332-336: Button click handler bypasses `renderCouncil()` entirely:
     `document.getElementById('dialogueLog').innerHTML = '<div style="color:white; white-space:pre-wrap;">' + data.response + '</div>'`
     leaving `renderCouncil` as dead code because `dashboard_backend.py:277` was altered to return a plain text string from `polyglot_orchestrator.py`.

7. **`review_dashboard.html`**:
   - Lines 241-310: Duplicate `<style>` block and lines 311-367 duplicate HTML markup inside the document.
   - Lines 531-568: Triage actions send `POST /api/assets/approve/{asset_id}` with `clip_type: "A-Roll"` or `"B-Roll"`, categorizing takes by performance sync vs atmosphere/lasers.

---

## 2. Logic Chain

1. **Premise**: Ingestion and processing of high-bitrate 4K mobile video (from modern flagships like the Samsung S26 Ultra) is compute-heavy, memory-intensive, and prone to timeout or failure if not isolated.
   - **Observation Reference**: `orchestrator.py:238-303` extracts `.wav` first; `orchestrator.py:309-468` generates a 720p proxy before touching 4K masters.
   - **Inference**: Separating lightweight proxies and audio extraction from master 4K rendering is essential to prevent desktop freezing and pipeline stalls.

2. **Premise**: AI agent video editing must be deterministic and verifiable without allowing agents to "self-certify" subjective success (violating R2: Zero-Discretion Mandate).
   - **Observation Reference**: `orchestrator.py:105-232` executes programmatic FFmpeg EBU R128 loudness verification and duration checks, raising a loud exception if measurements deviate from broadcast standards.
   - **Inference**: The `verify_media_file` function is a trustless, objective QC gate that belongs in the permanent core tool library.

3. **Premise**: Autonomous agents must not incur massive GPU/rendering costs without human confirmation.
   - **Observation Reference**: `polyglot_orchestrator.py:75-82` dumps proposals to `draft_state.json`, while `dashboard_v2.html:66-71` and `dashboard.js:283-313` poll this draft and require a physical "Commit & Render" click.
   - **Inference**: This Human-in-the-Loop review state machine is an essential architectural pattern for media pipelines.

4. **Premise**: The existing implementations suffer from architectural drift and fragmentation.
   - **Observation Reference**: `council_ui.html` calls port 9051, `dashboard.js` calls port 9067, `remote_trigger.py` binds port 8000; `council_ui.html` has dead animation code because `dashboard_backend.py` broke the `{ dialogue: [...], synthetic_prompt: ... }` schema contract.
   - **Inference**: The legacy codebase cannot be repaired by incremental in-place patching. The valuable logic must be surgically extracted into clean standalone modules with explicit Pydantic schemas, and the bloated legacy files archived.

---

## 3. Caveats

- **No Live Subprocess Execution**: In accordance with the Explorer role and the ZERO-MODIFICATION GUARANTEE, no video transcode commands or live API server processes were executed during this inspection. Observations were gathered through static AST and code analysis.
- **DaVinci Resolve Environment Dependency**: DaVinci Resolve scripting logic (`resolve_handoff.py`) requires DaVinci Resolve Studio running with external scripting enabled. It was not tested against live Resolve instances.
- **Port Conflict Origin**: It is assumed that ports 9051, 9067, and 8000 were spun up across different historical development sessions to avoid `WinError 10048` (address in use) socket collisions.

---

## 4. Conclusion

The legacy orchestrators and dashboards contain 8 high-value, research-validated components that must be preserved:
1. `EBU_R128_Loudness_QC_Verifier` (`orchestrator.py:105-232`)
2. `Decoupled_WAV_Audio_Drop_Detector` (`orchestrator.py:238-303`)
3. `Platform_SafeZone_SVG_Overlay_Specs` (`index.html:1422-1456`)
4. `Council_of_the_Drop_Arbitration_Engine` (`council_ui.html:276-296`, `test_pipeline.py:21-52`)
5. `FastAPI_HTTP206_Range_Streamer` (`remote_trigger.py:851-935`)
6. `Single_Job_Async_Subprocess_Supervisor` (`remote_trigger.py:432-672`)
7. `Polyglot_Draft_Review_State_Machine` (`polyglot_orchestrator.py:75-82`, `dashboard_v2.html:66-71`)
8. `Dual_Tier_Footage_Triage_Classifier` (`review_dashboard.html:531-568`)

All 8 concepts are fully detailed with context mapping, strengths, weaknesses, and implementation instructions in `analysis.md`. The surrounding legacy files (`index.html`, `orchestrator.py`, `remote_trigger.py`, `council_ui.html`, `review_dashboard.html`) should be retired to `_archive_vault` once extracted.

---

## 5. Verification Method

To independently verify these findings:
1. **Inspect Target Files & Lines**:
   - View `d:\GOOGLE ANTIGRAVITY\content_creation\orchestrator.py` lines 105-232 to verify `QCReport` and `verify_media_file` EBU R128 regex logic.
   - View `d:\GOOGLE ANTIGRAVITY\content_creation\remote_trigger.py` lines 851-935 to verify the HTTP 206 Partial Content byte-range streamer.
   - View `d:\GOOGLE ANTIGRAVITY\content_creation\index.html` lines 1422-1456 to verify YouTube Shorts (900x1270) and TikTok (920x1310) SVG safe-zone coordinates.
   - View `d:\GOOGLE ANTIGRAVITY\content_creation\council_ui.html` lines 322, 332-336, and 346-373 to verify the disconnected `renderCouncil` animation and hardcoded port 9051.
   - View `d:\GOOGLE ANTIGRAVITY\content_creation\tests\test_pipeline.py` lines 21-52 to verify the 5-persona council test contract.
2. **Execute Existing Test Suite**:
   ```powershell
   pytest "d:\GOOGLE ANTIGRAVITY\content_creation\tests\test_pipeline.py" -v
   ```
   *Condition for Invalidation*: If `test_council_think_personas` passes against the current live `dashboard_backend.py`, our finding of contract desynchronization is invalidated. (Static code analysis confirmed that line 277 in `dashboard_backend.py` returns `{"status": "success", "response": draft_state.get("ai_summary")}` rather than `{"dialogue": [...]}`).
