# Antigravity Control Plane: Stateless Worker Subsystems & Test Suite Specification

## 1. Executive Summary

This document establishes the authoritative specification for **Stateless Worker Subsystems (R2)**, the **Action Engine (`bind_tools`)**, the **Handoff Protocol (`Command`)**, and the **Deterministic Test Suite (`test_orchestrator.py`)** within the `antigravity_control_plane` architecture.

The `antigravity_control_plane` unifies fragmented Antigravity skills into a clean, hierarchical LangGraph architecture. The Central Supervisor coordinates three specialized, isolated, stateless worker subsystems:
1. **Social Deployer Worker** (`workers/social_deployer.py`): Media asset deployment across Facebook (ADB Anti-Ban intent) and YouTube (Data API).
2. **Mobile Worker** (`workers/mobile_worker.py`): 4-tier Android automation engine (Dalvik binaries, Android Intents, UI Automator XML layout parsing, and Termux keystroke injection).
3. **Research Worker** (`workers/research_worker.py`): Deep research and data-driven validation against workspace constraints (`GEMINI.md`) using Google GenAI / Gemini Interactions API.

All worker nodes are strictly stateless, use `bind_tools()` to invoke discrete functions, and return control atomically to the Supervisor via `Command(update={...}, goto='supervisor')`. Worker-to-worker direct communication is strictly forbidden.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Social Worker | `deploy_to_facebook_via_adb` | Deploys media to Facebook by waking device, pushing asset to `/sdcard/Pictures/`, and broadcasting `android.intent.action.SEND` to `com.facebook.katana`. | `image_path: str`, `post_text: str` | `{"status": "SUCCESS", "platform": "facebook", "path": str}` | Raises `FileNotFoundError` if asset missing; returns `{"status": "FAILED", "error": str}` if ADB offline. | `social-deployment-agent/SKILL.md`, `deployment_agent.py` |
| 2 | Social Worker | `deploy_to_youtube_api` | Updates video thumbnail / uploads media via YouTube Data API v3 using authenticated credentials. | `image_path: str`, `video_id: str`, `title: str`, `description: str` | `{"status": "SUCCESS", "platform": "youtube", "video_id": str}` | Raises `ValueError` if `video_id` missing; returns `{"status": "FAILED", "error": "AUTH_EXPIRED"}` if credentials invalid. | `social-deployment-agent/SKILL.md`, `deployment_agent.py` |
| 3 | Social Worker | `validate_social_manifest` | Validates JSON schema of `social_manifest.json` ensuring required targets, asset paths, and text payloads are defined. | `manifest_path: str` | `{"valid": bool, "campaign": str, "targets": list[dict]}` | Returns `{"valid": False, "errors": list[str]}` on schema violation. | `social-deployment-agent/SKILL.md` |
| 4 | Social Worker | `log_social_telemetry` | Records deployment outcome and error traces into SQLite telemetry database (`booth_telemetry.db`) satisfying ML optimization requirements. | `status: str`, `details: str`, `db_path: str` | `{"logged": True, "row_id": int}` | Catches SQLite errors, logs warning, returns `{"logged": False, "error": str}`. | `deployment_agent.py`, `agent-ml-optimization-loop` |
| 5 | Mobile Worker | `verify_device_connected` | Preflight check validating ADB daemon connectivity and device authorization status before operations. | None | `{"connected": bool, "devices": list[str]}` | Returns `{"connected": False, "error": "NO_DEVICE"}` if no authorized device attached. | `autonomous-mobile-agent-blueprint/SKILL.md` |
| 6 | Mobile Worker | `execute_adb_shell` | Tier 1 Dalvik / binary execution and general shell command runner via `adb shell`. | `command: str`, `timeout_seconds: int = 30` | `{"stdout": str, "stderr": str, "exit_code": int}` | Returns non-zero exit code and stderr on failure; catches `TimeoutExpired`. | `zero-touch-automation-registry/SKILL.md` |
| 7 | Mobile Worker | `send_android_intent` | Tier 2 Android Intent dispatcher (`am start` / `am broadcast`) to trigger app actions without UI interaction. | `action: str`, `package: str = None`, `extras: dict = None`, `is_broadcast: bool = False` | `{"success": bool, "output": str}` | Captures Intent delivery failure from ADB stderr. | `zero-touch-automation-registry/SKILL.md` |
| 8 | Mobile Worker | `uiautomator_tap_element` | Tier 3 UI Automator engine: dumps `window_dump.xml`, parses target element bounds `[x1,y1][x2,y2]`, calculates center `(x, y)`, and executes `input tap`. | `target_text: str = None`, `resource_id: str = None`, `content_desc: str = None` | `{"tapped": bool, "coordinates": [int, int], "bounds": str}` | Returns `{"tapped": False, "error": "ELEMENT_NOT_FOUND"}` if XML search yields no matching node. | `zero-touch-automation-registry/SKILL.md` |
| 9 | Mobile Worker | `inject_termux_command` | Tier 4 Keystroke injection engine: pushes payload to `/sdcard/`, brings `com.termux` to foreground via `monkey`, and injects input text with space `%s` escaping. | `command: str`, `push_payload_path: str = None` | `{"injected": bool, "command": str}` | Returns `{"injected": False, "error": str}` if monkey launch fails or ADB is offline. | `zero-touch-automation-registry/SKILL.md` |
| 10 | Mobile Worker | `disable_samsung_autoblocker` | Proactively disables Samsung One UI Auto Blocker timeout switch to maintain persistent ADB communication. | None | `{"disabled": bool}` | Returns `{"disabled": False, "error": str}` if settings command rejected. | `zero-touch-automation-registry/SKILL.md` |
| 11 | Mobile Worker | `grant_app_permission` | Grants requested Android runtime permissions via `pm grant` bypassing user dialogs. | `package_name: str`, `permission: str` | `{"granted": bool}` | Returns `{"granted": False, "error": str}` if package or permission invalid. | `zero-touch-automation-registry/SKILL.md` |
| 12 | Research Worker | `execute_deep_research` | Spawns Gemini Deep Research interaction (`deep-research-max-preview-04-2026` or web-grounded research) to analyze technical designs and benchmarks. | `topic: str`, `output_path: str`, `context_filter: str = ""` | `{"status": "COMPLETED", "output_file": str, "verdict": str}` | Catches 429/503 quota errors and triggers R27 model cascade; writes error summary to output file on fatal failure. | `data-driven-validation/SKILL.md`, `validate_design.py` |
| 13 | Research Worker | `query_workspace_rules` | Loads and extracts specific constraints from `GEMINI.md` / workspace manifest for compliance checking. | `rule_keyword: str` | `{"rules_matched": list[str]}` | Returns empty list if no rules match keyword. | `validate_design.py`, `GEMINI.md` |
| 14 | Research Worker | `evaluate_design_proposal` | Synthesizes research findings into structured output: Verdict (VALIDATE / ENHANCE / REJECT), Evidence, Citations. | `proposal: str`, `research_data: str` | `{"verdict": str, "evidence": list[str], "enhancements": list[str]}` | Returns fallback verdict `EVALUATE` if response parsing fails. | `data-driven-validation/SKILL.md` |
| 15 | Action Engine | `bind_tools` Integration | Binds domain-specific tool definitions to worker LLM instances so tool calling schemas are passed deterministically to the model. | `tools: list[Callable]` | Bound model instance `Runnable` | Raises `ValueError` if tool callable lacks type annotations or docstring. | LangGraph / LangChain Core Specification |
| 16 | Handoff Protocol | `Command` Object Return | Returns atomic state delta and explicit destination `goto="supervisor"` from worker node to Central Supervisor. | `update: dict`, `goto: str = "supervisor"` | `Command` object | Prevents legacy conditional edge races; enforces single control plane routing. | LangGraph v0.2+ Specification |
| 17 | Test Suite | Deterministic Mock Harness | Mocks LLM structured outputs, tool execution subshells, API calls, and checkpointers for fast, zero-network test runs. | `pytest` test runner | Test results (all pass in < 5s) | Deterministic assertion failures when state transitions or tool calls mismatch. | `ORIGINAL_REQUEST.md`, `test_orchestrator.py` |
| 18 | Test Suite | DAG Loop Protection Test | Injects cyclic and failing worker state updates into graph execution and asserts termination within `recursion_limit`. | `GraphConfig(recursion_limit=10)` | Graph stops cleanly without infinite loop | Raises `GraphRecursionError` if recursion limit breached without clean termination. | `ORIGINAL_REQUEST.md`, `test_orchestrator.py` |

---

## 3. Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | `deploy_to_facebook_via_adb` | Image path containing spaces (e.g. `staged_assets/Track 01 Cover.jpg`) | Remote path quoting in ADB push and URI formatting (`file:///sdcard/Pictures/...`) must properly encode spaces to prevent ADB CLI argument fragmentation. |
| 2 | `deploy_to_facebook_via_adb` | Device screen is locked/asleep | Worker must issue `input keyevent KEYCODE_WAKEUP` and `input keyevent 82` (unlock/menu) before launching intent; otherwise intent starts behind lockscreen. |
| 3 | `deploy_to_youtube_api` | Expired OAuth token (`token.json`) | Function catches `google.auth.exceptions.RefreshError`, returns structured `{"status": "FAILED", "error": "TOKEN_EXPIRED", "retryable": False}` to state so Supervisor can flag auth requirement. |
| 4 | `uiautomator_tap_element` | Target text exists in multiple nodes in XML hierarchy (e.g. parent container and child label) | XML parser selects the innermost clickable node or exact matching leaf node, extracts bounds `[x1,y1][x2,y2]`, and calculates arithmetic midpoint `((x1+x2)//2, (y1+y2)//2)`. |
| 5 | `uiautomator_tap_element` | Element is off-screen (requires scroll) | XML dump does not contain element; function returns `{"tapped": False, "error": "NOT_VISIBLE"}`, allowing worker to issue swipe gesture and retry. |
| 6 | `inject_termux_command` | Command contains symbols (`$`, `&`, `"`, `'`, spaces) | String parser transforms spaces to `%s`, `$` to `%24`, and escapes shell characters before passing to `adb shell input text` to avoid command truncation. |
| 7 | `execute_deep_research` | Gemini API returns 429 Quota Exhausted | R27 Zero-Friction Fallback cascade immediately switches model: `gemini-3.7-flash` -> `gemini-3.6-flash` -> `gemini-3.5-flash-lite` -> `gemini-2.5-pro` without sleep stalls. |
| 8 | `execute_deep_research` | Output directory does not exist | Function automatically creates parent directory using `os.makedirs(os.path.dirname(output_path), exist_ok=True)` before file write. |
| 9 | `execute_adb_shell` | Command hangs indefinitely (e.g. blocking process) | `subprocess.run` enforces `timeout=30`, catches `subprocess.TimeoutExpired`, terminates process, and returns `{"exit_code": -1, "stderr": "Command timed out after 30s"}`. |
| 10 | Handoff `Command` | Worker encounters fatal error during execution | Worker constructs `Command(update={"messages": [AIMessage(content=f"Error: {err}")], "task_status": "FAILED", "error_details": str(err)}, goto="supervisor")`. Supervisor inspects `task_status` and routes to error resolution or final exit. |
| 11 | Handoff `Command` | Worker attempts to hand off to another worker (e.g. `goto='mobile_worker'`) | Strict contract violation: worker nodes must only specify `goto='supervisor'`. Test suite asserts that all worker nodes strictly route to `'supervisor'`. |
| 12 | State Pruning | Large tool outputs (e.g. 50KB UI XML dump or 100KB research text) | State schema trims raw tool payloads in graph state history, storing full data in discrete artifact files and keeping only summarized structured dicts in `state["worker_results"]`. |

---

## 4. Subsystem Architectural Specifications

### 4.1 Subsystem 1: Social Deployer Worker (`workers/social_deployer.py`)

#### Purpose
Automates social distribution workflows without triggering platform bot detection. Uses physical Android ADB Intent dispatching for Facebook and Google API Client libraries for YouTube.

#### Bound Tools
1. **`deploy_to_facebook_via_adb(image_path: str, post_text: str) -> dict`**:
   - Wakes Android device via `adb shell input keyevent KEYCODE_WAKEUP`.
   - Pushes file to `/sdcard/Pictures/<filename>` via `adb push`.
   - Dispatches `android.intent.action.SEND` targeting `com.facebook.katana` with `android.intent.extra.STREAM` and `android.intent.extra.TEXT`.
   - Returns execution dict.
2. **`deploy_to_youtube_api(image_path: str, video_id: str, title: str = "", description: str = "") -> dict`**:
   - Authenticates via `token.json` / Google API credentials.
   - Executes thumbnail set / video metadata update.
   - Returns execution dict.
3. **`validate_social_manifest(manifest_path: str) -> dict`**:
   - Parses manifest JSON, verifying `campaign`, `targets`, `assets`, and `captions`.
4. **`log_social_telemetry(status: str, details: str, db_path: str = None) -> dict`**:
   - Appends entry into SQLite `booth_telemetry.db` (`deployment_logs` table).

#### Node Execution Logic
```python
def social_deployer_node(state: State) -> Command[Literal["supervisor"]]:
    """
    Stateless Social Deployer Worker Node.
    Binds tools, invokes LLM / tool dispatcher, and hands off to Supervisor.
    """
    # 1. Bind tools to worker model
    tools = [deploy_to_facebook_via_adb, deploy_to_youtube_api, validate_social_manifest, log_social_telemetry]
    worker_llm = llm.bind_tools(tools)
    
    # 2. Invoke LLM with current task messages
    response = worker_llm.invoke(state["messages"])
    
    # 3. Execute tool calls if requested
    tool_messages = []
    results = {}
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in response.tool_calls:
            tool_fn = {t.__name__: t for t in tools}.get(tool_call["name"])
            if tool_fn:
                tool_output = tool_fn(**tool_call["args"])
                tool_messages.append(ToolMessage(
                    content=json.dumps(tool_output),
                    tool_call_id=tool_call["id"]
                ))
                results[tool_call["name"]] = tool_output
                
    # 4. Atomic Handoff back to Supervisor
    return Command(
        update={
            "messages": [response] + tool_messages,
            "worker_results": results,
            "active_worker": None,
            "last_step": "social_deployer"
        },
        goto="supervisor"
    )
```

---

### 4.2 Subsystem 2: Mobile Worker (`workers/mobile_worker.py`)

#### Purpose
Executes headless Android device orchestration, bypassing UI prompts through a 4-tier automation hierarchy.

#### 4-Tier Automation Hierarchy
- **Tier 1 (Dalvik / Binary Execution)**: Executes native binaries and `app_process` scripts over ADB (`execute_adb_shell`).
- **Tier 2 (Android Intents)**: Dispatches explicit/implicit Intents (`am start`, `am broadcast`) via `send_android_intent`.
- **Tier 3 (UI Automator DOM Parsing)**: Dumps XML hierarchy (`uiautomator dump`), parses element bounds, and calculates center tap coordinates (`uiautomator_tap_element`).
- **Tier 4 (Keystroke Injection & Termux Sandbox Bypass)**: Launches target sandbox via `monkey -p <pkg> 1`, injects formatted input commands via `input text` and `keyevent 66` (`inject_termux_command`).

#### Bound Tools
1. **`verify_device_connected() -> dict`**: Runs `adb devices`, verifies >= 1 device in `'device'` state.
2. **`execute_adb_shell(command: str, timeout_seconds: int = 30) -> dict`**: Runs `adb shell <command>` with strict timeout.
3. **`send_android_intent(action: str, package: str = None, extras: dict = None, is_broadcast: bool = False) -> dict`**: Runs `adb shell am start` or `am broadcast`.
4. **`uiautomator_tap_element(target_text: str = None, resource_id: str = None, content_desc: str = None) -> dict`**: Dumps XML, parses `bounds="[x1,y1][x2,y2]"`, computes `((x1+x2)//2, (y1+y2)//2)`, issues `adb shell input tap <x> <y>`.
5. **`inject_termux_command(command: str, push_payload_path: str = None) -> dict`**: Pushes payload to `/sdcard/`, activates Termux, types formatted command.
6. **`disable_samsung_autoblocker() -> dict`**: Sets `rampart_auto_enabled_switch_enabled` to `0`.
7. **`grant_app_permission(package_name: str, permission: str) -> dict`**: Runs `adb shell pm grant <package> <permission>`.

#### Node Execution Logic
```python
def mobile_worker_node(state: State) -> Command[Literal["supervisor"]]:
    """
    Stateless Mobile Automation Worker Node.
    """
    tools = [
        verify_device_connected, execute_adb_shell, send_android_intent,
        uiautomator_tap_element, inject_termux_command, disable_samsung_autoblocker, grant_app_permission
    ]
    worker_llm = llm.bind_tools(tools)
    response = worker_llm.invoke(state["messages"])
    
    tool_messages = []
    results = {}
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in response.tool_calls:
            tool_fn = {t.__name__: t for t in tools}.get(tool_call["name"])
            if tool_fn:
                tool_output = tool_fn(**tool_call["args"])
                tool_messages.append(ToolMessage(
                    content=json.dumps(tool_output),
                    tool_call_id=tool_call["id"]
                ))
                results[tool_call["name"]] = tool_output

    return Command(
        update={
            "messages": [response] + tool_messages,
            "worker_results": results,
            "active_worker": None,
            "last_step": "mobile_worker"
        },
        goto="supervisor"
    )
```

---

### 4.3 Subsystem 3: Research Worker (`workers/research_worker.py`)

#### Purpose
Executes deep research and data-driven architectural validation against workspace constraints (`GEMINI.md`) using Google GenAI APIs.

#### Bound Tools
1. **`execute_deep_research(topic: str, output_path: str, context_filter: str = "") -> dict`**:
   - Dispatches Gemini Interactions API research task (`deep-research-max-preview-04-2026`).
   - Injects `GEMINI.md` workspace boundary rules.
   - Polls for completion and saves markdown output to `output_path`.
   - Returns structured status dict with verdict.
2. **`query_workspace_rules(rule_keyword: str) -> list[str]`**:
   - Parses `GEMINI.md` to extract active rules (e.g. R2, R16, R22, R27) relevant to query.
3. **`save_research_report(content: str, destination_path: str) -> str`**:
   - Saves formatted markdown report to disk.
4. **`evaluate_design_proposal(proposal: str, criteria: list[str]) -> dict`**:
   - Performs structured evaluation returning verdict: `VALIDATE`, `ENHANCE`, or `REJECT`.

#### Node Execution Logic
```python
def research_worker_node(state: State) -> Command[Literal["supervisor"]]:
    """
    Stateless Deep Research & Validation Worker Node.
    """
    tools = [execute_deep_research, query_workspace_rules, save_research_report, evaluate_design_proposal]
    worker_llm = llm.bind_tools(tools)
    response = worker_llm.invoke(state["messages"])
    
    tool_messages = []
    results = {}
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in response.tool_calls:
            tool_fn = {t.__name__: t for t in tools}.get(tool_call["name"])
            if tool_fn:
                tool_output = tool_fn(**tool_call["args"])
                tool_messages.append(ToolMessage(
                    content=json.dumps(tool_output),
                    tool_call_id=tool_call["id"]
                ))
                results[tool_call["name"]] = tool_output

    return Command(
        update={
            "messages": [response] + tool_messages,
            "worker_results": results,
            "active_worker": None,
            "last_step": "research_worker"
        },
        goto="supervisor"
    )
```

---

## 5. Action Engine Specification (`bind_tools()`)

### Principles of Stateless Worker Execution
1. **Tool Definition Isolation**: Every tool is a pure, independently testable Python function with full type hints (`pydantic` / Python typing) and clear docstrings.
2. **Deterministic Schema Binding**: When `llm.bind_tools(tools)` is called, LangChain/LangGraph converts the Python callables into standard JSON Schema function definitions passed to the model endpoint.
3. **Zero In-Memory Drift**: Worker functions do NOT store mutable instance state on classes. State flows entirely in and out through the `State` dict.
4. **Execution Isolation**: When a tool raises an exception, the worker catches it, converts it to a structured error dictionary, and emits a `ToolMessage` rather than crashing the orchestrator process.

---

## 6. Handoff Protocol Specification (`Command(update={...}, goto='supervisor')`)

### LangGraph `Command` Semantics
- **Atomic State Mutation**: The `update` dictionary modifies the graph state keys in the exact transaction as the node transition.
- **Explicit Destination**: `goto="supervisor"` specifies that control MUST return directly to the Central Supervisor node.
- **Elimination of Conditional Edges**: Legacy LangGraph setups required `workflow.add_conditional_edges("worker", router_fn, {"supervisor": "supervisor"})`. With `Command`, the worker's return value handles both state update and routing natively, simplifying the DAG topology.
- **Worker Isolation Enforcement**: Worker nodes cannot route to peer workers (`goto="mobile_worker"` from `social_worker` is invalid). All transitions route through `supervisor`.

---

## 7. Deterministic Test Suite Specification (`test_orchestrator.py`)

### Test Suite Architecture
The test suite `test_orchestrator.py` validates the complete control plane deterministically without making live network requests, touching ADB hardware, or calling external APIs.

```
tests/
├── test_orchestrator.py        # Master DAG routing & integration tests
├── test_social_worker.py       # Unit tests for social deployment tools
├── test_mobile_worker.py       # Unit tests for mobile 4-tier automation tools
├── test_research_worker.py     # Unit tests for research & validation tools
└── conftest.py                 # Pytest fixtures, mock state, mock checkpointer, mock LLMs
```

### Key Test Categories in `test_orchestrator.py`

#### 1. Supervisor Routing State Machine Tests
- **Test Intent -> Social Worker**:
  - Input message: `"Deploy the album cover image to Facebook and YouTube"`
  - Assert: Supervisor routes to `social_worker`.
- **Test Intent -> Mobile Worker**:
  - Input message: `"Click the install button in Termux over ADB"`
  - Assert: Supervisor routes to `mobile_worker`.
- **Test Intent -> Research Worker**:
  - Input message: `"Perform deep research to validate migrating our state to PostgreSQL"`
  - Assert: Supervisor routes to `research_worker`.
- **Test Termination (`FINISH` -> `END`)**:
  - Input message with completed worker results:
  - Assert: Supervisor detects task completion and routes to `END`.

#### 2. Worker Handoff & State Update Tests
- **Verify `Command` Structure**:
  - Assert worker return value is an instance of `Command`.
  - Assert `command.goto == "supervisor"`.
  - Assert `command.update` contains updated `messages` and `worker_results`.
- **Verify Worker Isolation**:
  - Assert no worker node defines an edge or `goto` targeting another worker node.

#### 3. Infinite Loop & Recursion Protection Tests
- **Finite Iteration Guarantee**:
  - Graph is compiled with `checkpointer` and run with `{"recursion_limit": 15}`.
  - Multi-step tasks complete in <= 6 steps (Supervisor -> Worker 1 -> Supervisor -> Worker 2 -> Supervisor -> END).
  - Failing worker returns `FAILED` status, causing Supervisor to transition to `END` or error state rather than re-invoking the failing worker indefinitely.

#### 4. Mocking Strategy
- **Mock LLM**: Use `unittest.mock.MagicMock` or LangChain's `FakeListChatModel` / `FakeMessagesListChatModel` to return deterministic `AIMessage` with structured output for Supervisor and `tool_calls` for Workers.
- **Mock ADB & Subprocess**: Mock `subprocess.run` to return canned stdout/stderr for `adb devices`, `adb shell uiautomator dump`, `adb push`, and `adb shell am start`.
- **Mock Google GenAI**: Mock `genai.Client().interactions.create()` and `.get()` to return pre-canned markdown validation reports without API keys.
- **Mock Checkpointer**: Use `MemorySaver()` or mocked connection pool for unit testing graph routing.

---

## 8. Expected File Layout

```
C:\Users\noahp\teamwork_projects\antigravity_control_plane\
├── pyproject.toml              # Project dependencies and pytest configuration
├── requirements.txt            # Dependency manifest (langgraph, langchain-core, pydantic, psycopg_pool, pytest)
├── README.md                   # Control Plane documentation
├── supervisor.py               # Central Supervisor orchestrator (entrypoint)
├── state.py                    # State schema (TypedDict, Pydantic models, context pruning)
├── db.py                       # PostgreSQL checkpointer setup (psycopg_pool / PostgresSaver)
├── workers/
│   ├── __init__.py
│   ├── social_deployer.py      # Stateless Social Deployer Worker
│   ├── mobile_worker.py        # Stateless Mobile Automation Worker (4-tier engine)
│   └── research_worker.py      # Stateless Deep Research & Validation Worker
└── tests/
    ├── __init__.py
    ├── conftest.py             # Shared fixtures and mock harness
    ├── test_orchestrator.py    # Master DAG routing & loop protection tests
    ├── test_social_worker.py   # Unit tests for social deployer
    ├── test_mobile_worker.py   # Unit tests for mobile worker
    └── test_research_worker.py # Unit tests for research worker
```

---

## 9. Conclusion & Implementation Readiness

The specifications for R2 Stateless Worker Subsystems, the Action Engine (`bind_tools`), the Handoff Protocol (`Command`), and the deterministic test suite (`test_orchestrator.py`) are fully mapped and grounded in existing codebase standards and LangGraph best practices. The project is ready for formal synthesis into `PROJECT.md` and subsequent milestone execution.
