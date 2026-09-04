# Technical Analysis: Social Deployer Worker Subsystem (`workers/social.py`)

**Author:** `explorer_m2_1`  
**Date:** 2026-08-27  
**Target File:** `workers/social.py`, `workers/base.py`, `schemas.py`, `tests/test_workers.py`  
**Status:** Complete Architectural Specification  

---

## 1. Executive Summary

The Social Deployer worker subsystem (`workers/social.py`) is an isolated, stateless execution node within the Antigravity Control Plane StateGraph. In accordance with the Hierarchical Supervisor pattern (PROJECT.md Milestone 2), the Social Deployer:
1. Binds 4 deterministic domain tools (`@tool`): `deploy_to_facebook_via_adb`, `deploy_to_youtube_api`, `validate_social_manifest`, and `log_social_telemetry`.
2. Executes actions through the LangChain Action Engine (`llm.bind_tools(...)`).
3. Appends structured audit records to `execution_history` via `create_history_entry(...)`.
4. Returns atomic state transitions and transfers control exclusively to the central supervisor via `Command(update={...}, goto='supervisor')`.
5. Strictly prevents inter-worker lateral execution (workers cannot communicate with peer workers directly).

---

## 2. Tool Architecture & Specifications (`@tool`)

All tools are decorated with `@tool` from `langchain_core.tools`, providing automatic JSON schema generation, type hints, and rich docstrings for model grounding.

### 2.1 `deploy_to_facebook_via_adb`
- **Purpose:** Anti-ban Facebook media dispatch. Bypasses headless browser detection by pushing the local image to an Android emulator (`/sdcard/Pictures/`) and broadcasting the `android.intent.action.SEND` intent to `com.facebook.katana`.
- **Signature:**
  ```python
  @tool
  def deploy_to_facebook_via_adb(
      image_path: str,
      post_text: str,
      device_id: Optional[str] = None,
      package_name: str = "com.facebook.katana",
      timeout_seconds: int = 30,
  ) -> Dict[str, Any]:
      """
      Deploys an image asset with accompanying post text to Facebook on an Android device via ADB.
      
      Executes device wake, file push to /sdcard/Pictures/, and broadcasts the android.intent.action.SEND
      intent targeting the Facebook app to initiate posting.
      
      Args:
          image_path: Absolute or relative local path to the image file to upload.
          post_text: Caption or copy text accompanying the post.
          device_id: Optional specific ADB device serial/identifier (for multi-device environments).
          package_name: Target package name (defaults to 'com.facebook.katana').
          timeout_seconds: Subprocess execution timeout in seconds (default 30).
          
      Returns:
          Dictionary with execution status ('SUCCESS' or 'FAILED'), remote path, post copy, or error details.
      """
  ```
- **Execution Logic:**
  1. **Pre-flight Validation:** Checks if `image_path` exists on disk. If missing, returns `{"status": "FAILED", "platform": "facebook", "error": f"Image file not found: {image_path}"}` without spawning subprocesses.
  2. **Device Wakeup:** Runs `adb [-s <device_id>] shell input keyevent KEYCODE_WAKEUP`.
  3. **File Push:** Derives `remote_path = f"/sdcard/Pictures/{os.path.basename(image_path)}"`. Runs `adb [-s <device_id>] push <image_path> <remote_path>`. Checks return code.
  4. **Intent Broadcast:** Runs `adb [-s <device_id>] shell am start -a android.intent.action.SEND -t image/jpeg --eu android.intent.extra.STREAM file://<remote_path> --es android.intent.extra.TEXT "<post_text>" <package_name>`.
  5. **Exception Handling:** Catches `FileNotFoundError` (ADB missing on PATH), `subprocess.TimeoutExpired`, and `subprocess.SubprocessError`, returning clean error payloads.

### 2.2 `deploy_to_youtube_api`
- **Purpose:** Updates video thumbnail and metadata via YouTube Data API v3 (with offline/mockable fallback for test environments).
- **Signature:**
  ```python
  @tool
  def deploy_to_youtube_api(
      image_path: str,
      video_id: str,
      title: Optional[str] = None,
      description: Optional[str] = None,
  ) -> Dict[str, Any]:
      """
      Uploads a custom video thumbnail and optionally updates metadata via YouTube Data API.
      
      Args:
          image_path: Local path to the thumbnail image (JPEG/PNG).
          video_id: The target YouTube video ID (e.g., 'dQw4w9WgXcQ').
          title: Optional updated video title.
          description: Optional updated video description.
          
      Returns:
          Dictionary with status ('SUCCESS' or 'FAILED'), video_id, thumbnail path, and confirmation message.
      """
  ```
- **Execution Logic:**
  1. **Validation:** Checks that `video_id` is non-empty and `image_path` exists on the local filesystem.
  2. **API Invocation:** In production, interacts with Google API Client. In test/mock mode, validates parameters and returns verified confirmation payload.
  3. **Quota/Error Handling:** Follows R27 (Zero-Friction Fallback Mandate) — traps 429/503 quota errors and returns structured diagnostic error objects without blocking.

### 2.3 `validate_social_manifest`
- **Purpose:** Validates social campaign deployment manifests (`social_manifest.json` or inline dict payloads), verifying platform configs, feed paths, and asset integrity.
- **Signature:**
  ```python
  @tool
  def validate_social_manifest(
      manifest_path: Optional[str] = None,
      manifest_content: Optional[str] = None,
      check_files_exist: bool = False,
  ) -> Dict[str, Any]:
      """
      Validates a social deployment manifest file or inline JSON payload.
      
      Checks for required campaign metadata, supported platforms (facebook, youtube, etc.),
      and optionally verifies that staged asset files exist on disk.
      
      Args:
          manifest_path: Path to the JSON manifest file on disk.
          manifest_content: Raw JSON string or serialized manifest structure.
          check_files_exist: If True, physically verifies that asset file paths exist on disk.
          
      Returns:
          Dictionary with validation status (valid: bool), campaign name, detected platforms,
          assets list, missing assets list, and validation errors.
      """
  ```
- **Execution Logic:**
  1. Parses JSON from file or string.
  2. Verifies `campaign` identifier.
  3. Detects platform blocks: `platforms.facebook_page` / `platforms.facebook`, `platforms.youtube`, or `deployments` array.
  4. If `check_files_exist=True`, tests `os.path.exists()` on every asset path and collects missing files into `missing_assets`.
  5. Returns structured schema: `{"valid": bool, "campaign": str, "platforms_detected": list[str], "assets_count": int, "missing_assets": list[str], "errors": list[str]}`.

### 2.4 `log_social_telemetry`
- **Purpose:** Logs deployment telemetry to SQLite database (`booth_telemetry.db`), feeding the `agent-ml-optimization-loop`.
- **Signature:**
  ```python
  @tool
  def log_social_telemetry(
      campaign: str,
      platform: str,
      status: str,
      details: Optional[str] = None,
      db_path: Optional[str] = None,
  ) -> Dict[str, Any]:
      """
      Records deployment telemetry and status into the local SQLite telemetry database.
      
      Args:
          campaign: Name or ID of the campaign (e.g. 'Music Baptism Vol 1').
          platform: Social platform ('facebook', 'youtube', 'general').
          status: Deployment status ('SUCCESS', 'FAILED', 'EVALUATE', 'PENDING').
          details: Optional JSON string or message detailing the outcome.
          db_path: Optional path to the SQLite database (defaults to booth_telemetry.db).
          
      Returns:
          Dictionary confirming the logged record ID, timestamp, and target database path.
      """
  ```
- **Execution Logic:**
  1. Resolves `db_path` from argument -> `os.getenv("BOOTH_TELEMETRY_DB_PATH")` -> `"booth_telemetry.db"`.
  2. Ensures parent directory exists (`os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)`).
  3. Executes DDL: `CREATE TABLE IF NOT EXISTS deployment_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, campaign TEXT NOT NULL, platform TEXT NOT NULL, status TEXT NOT NULL, details TEXT)`.
  4. Inserts parameterized row with UTC ISO timestamp.
  5. Returns `{"status": "SUCCESS", "log_id": cursor.lastrowid, "timestamp": timestamp, "campaign": campaign, "platform": platform, "telemetry_status": status, "db_path": db_path}`.

---

## 3. Action Engine Integration (`llm.bind_tools`)

Worker execution uses the LangChain `bind_tools()` protocol:
1. Tools collection:
   ```python
   SOCIAL_TOOLS = [
       deploy_to_facebook_via_adb,
       deploy_to_youtube_api,
       validate_social_manifest,
       log_social_telemetry,
   ]
   ```
2. Dynamic binding:
   ```python
   llm_with_tools = llm.bind_tools(SOCIAL_TOOLS)
   ```
3. Worker System Instructions (`SOCIAL_WORKER_SYSTEM_PROMPT`):
   Grounds the model in executing discrete deployment tasks without hallucinating direct supervisor decisions or peer worker delegations.

---

## 4. Node Execution & Handoff Protocol (`Command`)

### 4.1 Node Signature & Execution Flow
```python
def social_worker(
    state: AgentState,
    llm: Optional[BaseChatModel] = None,
    tools: Optional[Sequence[BaseTool]] = None,
) -> Command:
```

### 4.2 Step-by-Step Node Lifecycle
1. **Context Extraction:** Extracts `messages = state.get("messages", [])` and `task_intent = state.get("task_intent", "")`.
2. **Tool Execution Loop:**
   - Invocations of `llm_with_tools.invoke(...)`.
   - If `response.tool_calls` is populated:
     - For each tool call, looks up tool in `tool_map`.
     - Executes `tool.invoke(tc["args"])`.
     - Creates `ToolMessage(content=json_serialized_result, tool_call_id=tc["id"])`.
     - Creates `create_history_entry(node="social_worker", action=f"tool_call:{tc['name']}", details={"args": tc["args"], "result": result}, status="SUCCESS"|"FAILED")`.
   - If no tool calls (direct response):
     - Creates `create_history_entry(node="social_worker", action="social_response", details={"content": response.content}, status="SUCCESS")`.
3. **Atomic State Update & Command Handoff:**
   ```python
   return Command(
       update={
           "messages": new_messages,
           "execution_history": history_entries,
           "status": "RUNNING",
           "next_worker": None,
       },
       goto="supervisor",
   )
   ```

---

## 5. Architectural Blueprint for `workers/` Module

```
workers/
├── __init__.py               # Exports social_worker, SOCIAL_TOOLS, tool callables
├── base.py                   # Worker execution harness & tool dispatch utilities
└── social.py                 # Social Deployer worker node & 4 domain tools
```

### 5.1 `workers/base.py` Specification
Contains reusable worker engine logic:
- `execute_worker_turn(state, llm, tools, worker_name, system_prompt) -> Command`: Standardized execution loop handling tool calls, error trapping, history recording, and Command return.
- `execute_tool_calls(tool_map, tool_calls) -> Tuple[List[ToolMessage], List[Dict[str, Any]], bool]`: Isolated tool invoker preventing node crashes when single tools fail.

### 5.2 `workers/social.py` Specification
Implements:
- `@tool` definitions for the 4 social tools.
- `SOCIAL_TOOLS = [...]`.
- `social_worker(state, ...)` node function.
- `create_social_worker(llm, tools)` factory function for custom dependency injection in tests and production.

---

## 6. Unit Testing Strategy (`tests/test_workers.py`)

The test suite in `tests/test_workers.py` will validate 100% of the Social Worker specification across 5 test tiers:

| Tier | Category | Test Cases |
|------|----------|------------|
| Tier 1 | Tool Unit Tests | `test_validate_social_manifest_valid`, `test_validate_social_manifest_missing_file`, `test_deploy_to_facebook_via_adb_success`, `test_deploy_to_youtube_api_success`, `test_log_social_telemetry_success` |
| Tier 2 | Tool Error & Boundary Handling | `test_deploy_to_facebook_missing_image`, `test_deploy_to_facebook_adb_not_found`, `test_deploy_to_facebook_timeout`, `test_deploy_to_youtube_missing_image`, `test_deploy_to_youtube_empty_video_id`, `test_log_social_telemetry_db_creation` |
| Tier 3 | Action Engine & `bind_tools` | `test_social_worker_tool_binding`, `test_social_worker_executes_single_tool_call`, `test_social_worker_executes_multi_tool_calls`, `test_social_worker_handles_unknown_tool_call`, `test_social_worker_handles_tool_exception` |
| Tier 4 | StateGraph & Command Handoff | `test_social_worker_returns_command_goto_supervisor`, `test_social_worker_updates_state_and_history`, `test_social_worker_in_stategraph_lifecycle` |
| Tier 5 | Inter-Worker Isolation & Adversarial | `test_inter_worker_isolation_no_direct_edges`, `test_social_worker_malformed_state_recovery` |

---

## 7. Implementation Recommendations for Builders

1. **Subprocess Mocking in ADB Tool:** Ensure `deploy_to_facebook_via_adb` cleanly uses `subprocess.run` with `text=True` and `capture_output=True`, checking `check=False` to handle non-zero return codes gracefully.
2. **SQLite Directory Safety in Telemetry Tool:** Always resolve `os.path.abspath(db_path)` and call `os.makedirs(os.path.dirname(...), exist_ok=True)` before `sqlite3.connect()`.
3. **Pydantic Tool Parameter Parsing:** Keep tool argument types explicit (`str`, `Optional[str] = None`, `bool = False`) so LangChain's `@tool` introspects JSON schemas perfectly.
4. **Command Reducer Alignment:** Ensure the worker updates `messages` and `execution_history` with lists (e.g. `[entry]`), matching `add_messages` and `operator.add` reducers in `AgentState`.
