# Analysis Report: Milestone M3 — Central Supervisor Orchestrator

## Executive Summary
Milestone M3 establishes the **Central Supervisor Orchestrator** for the Antigravity Control Plane. Building upon the foundational State & PostgreSQL Checkpointer (M1) and Stateless Worker Subsystems (M2), M3 delivers a unified, top-down Control Plane implementing the Hierarchical Supervisor Pattern in LangGraph.

The core architectural requirement is the **Decision-First Hybrid Pattern**: the Supervisor classifies user intent and selects target worker destinations strictly via typed structured output (`llm.with_structured_output(RoutingDecision)`), completely eliminating tool-calling overhead, brittle intermediate scratchpads, and routing latency. Dynamic graph transitions are handled atomically via LangGraph `Command(goto=..., update=...)` objects without legacy conditional edges.

---

## 1. Architectural Blueprint & Graph Topology

### 1.1 Hierarchical Hub-and-Spoke Topology
The Control Plane is structured as a centralized Hub-and-Spoke StateGraph:
- **Entrypoint**: `START -> supervisor`
- **Supervisor Node**: Evaluates global state (`task_intent`, `messages`, `execution_history`, `iteration_count`), invokes the Decision-First structured output model, and emits an atomic `Command(goto=target_worker, update=...)` or `Command(goto=END, update=...)`.
- **Worker Nodes (`social_worker`, `mobile_worker`, `research_worker`)**: Execute domain-specific actions via `bind_tools()`, append audit entries to `execution_history`, and return control atomically via `Command(goto="supervisor", update=...)`.
- **Isolation Invariant**: Zero direct edges between workers. All data flow is mediated through the Supervisor and global `AgentState`.

```
                  +---------------+
                  |     START     |
                  +-------+-------+
                          |
                          v
               +--------------------+
               |     supervisor     |<-------------------+
               | (Decision-First)   |                    |
               +---+------+------+--+                    |
                   |      |      |                       |
        +----------+      |      +----------+            |
        |                 |                 |            | Command(goto='supervisor')
        v                 v                 v            |
+---------------+ +---------------+ +-----------------+  |
| social_worker | | mobile_worker | | research_worker | -+
+-------+-------+ +-------+-------+ +--------+--------+
        |                 |                  |
        +-----------------+------------------+
                          |
                   (All Worker Nodes)
                          |
                          v (when next_node == "FINISH" or loop guard triggered)
                   +-------------+
                   |     END     |
                   +-------------+
```

---

## 2. Component Design & Implementation Details

### 2.1 `schemas.py`: Structured Output Decision Model
The Pydantic schema `RoutingDecision` defines the contract for LLM structured output.

```python
from __future__ import annotations
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict

class RoutingDecision(BaseModel):
    """
    Structured output schema for the Central Supervisor Orchestrator routing decisions.
    Enforces Decision-First routing without tool calling.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    next_node: Literal["social_worker", "mobile_worker", "research_worker", "FINISH"] = Field(
        ...,
        description="The target worker node destination or FINISH if the task has been fully completed."
    )
    reasoning: str = Field(
        ...,
        description="Detailed, step-by-step logical justification for the selected routing decision."
    )
    instructions: str = Field(
        ...,
        description="Clear, actionable instructions for the target worker node, or the final executive summary if FINISH."
    )

    @field_validator("reasoning", "instructions")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info) -> str:
        if not value or not value.strip():
            raise ValueError(f"Field '{info.field_name}' must not be empty or whitespace only.")
        return value.strip()
```

#### Additional Supporting Schemas in `schemas.py`
1. `ControlPlaneConfig`: Validates runtime configuration (e.g. `thread_id: str`, `max_iterations: int`, `checkpointer_type: Literal["memory", "postgres"]`, `verbose: bool`).
2. `WorkflowStatus`: Typed literal enum (`"IDLE"`, `"PENDING"`, `"RUNNING"`, `"COMPLETED"`, `"FAILED"`, `"TERMINATED_LOOP_LIMIT"`).
3. `SupervisorDecisionLog`: Encapsulates audit metadata for routing history.

---

### 2.2 Decision-First Routing Engine (`supervisor_node`)

#### Protocol Specifications
1. **Zero Tool Calling**: The Supervisor does NOT bind tools. It binds the Pydantic schema using `llm.with_structured_output(RoutingDecision)`.
2. **Context Compilation**: Every turn, the supervisor compiles:
   - System instruction (`SUPERVISOR_SYSTEM_PROMPT`)
   - Preserved user prompts and conversation history (`state["messages"]`)
   - Execution audit history summary (`state["execution_history"]`)
   - Iteration status (`state["iteration_count"]` / `state["max_iterations"]`)
3. **Loop Recursion Guard**:
   - Monotonically increments `iteration_count = state.get("iteration_count", 0) + 1`.
   - If `iteration_count >= state.get("max_iterations", 10)`:
     - Halts execution immediately.
     - Logs `action="loop_guard_termination"`, `status="TERMINATED_LOOP_LIMIT"`.
     - Returns `Command(goto=END, update={"iteration_count": iteration_count, "status": "TERMINATED_LOOP_LIMIT", ...})`.
4. **Handoff Handling**:
   - If `decision.next_node in ["social_worker", "mobile_worker", "research_worker"]`:
     - Updates `next_worker = decision.next_node`
     - Appends `AIMessage` containing reasoning and worker instructions
     - Appends history audit entry `action=f"route_to_{decision.next_node}"`
     - Returns `Command(goto=decision.next_node, update={...})`
   - If `decision.next_node == "FINISH"`:
     - Updates `next_worker = None`, `status = "COMPLETED"`
     - Appends final `AIMessage` with executive summary
     - Returns `Command(goto=END, update={...})`

---

### 2.3 System Prompt Design (`prompts.py`)

The Supervisor system prompt establishes strict operational boundaries, domain mappings, and delegation rules:

```python
SUPERVISOR_SYSTEM_PROMPT = """You are the Central Supervisor Orchestrator for the Antigravity Control Plane.
Your role is to act as the primary intelligence hub: analyzing high-level user intents, delegating subtasks to specialized, stateless worker subsystems, maintaining the global execution state, and synthesizing final completion.

### Architecture & Operating Protocol
1. Decision-First Hybrid Architecture:
   - You MUST classify intent and make routing decisions directly using structured output (RoutingDecision).
   - You do NOT call tools yourself. You delegate all physical executions to worker nodes.
   - Every turn, you evaluate the user's intent, the accumulated messages, and the execution history to decide the next step.

2. Available Worker Subsystems:
   - `social_worker`:
     - Scope: Anti-ban social media distribution, Facebook media dispatch via ADB intent (`com.facebook.katana`), YouTube video thumbnail uploads and metadata updates via YouTube Data API, social deployment manifest validation, and SQLite telemetry logging (`booth_telemetry.db`).
     - Trigger when: Tasks involve Facebook posts, YouTube uploads/thumbnails, social campaign manifests, or social telemetry logs.
   - `mobile_worker`:
     - Scope: Zero-Touch 4-tier Android automation hierarchy (Tier 1: direct Dalvik/binary/shell execution; Tier 2: Android intent broadcasts/activity starts; Tier 3: UI Automator XML DOM parsing & center bounds coordinate tapping; Tier 4: sandboxed Termux execution via keystroke injection & monkey), pre-flight ADB connectivity checks (`verify_device_connected`), Samsung AutoBlocker timeout prevention, and runtime permission grants.
     - Trigger when: Tasks involve Android device interaction, Termux scripting, UI element tapping, shell commands on mobile, or ADB device verification.
   - `research_worker`:
     - Scope: Deep data-driven technical research, SQLite FTS5 BM25 workspace rules queries (`sentinel_rules.db`), objective architectural design proposal evaluation against workspace rules (Rules R1-R36), and on-disk markdown report persistence.
     - Trigger when: Tasks involve architectural validation, rules lookups, compliance auditing, system design evaluation, or detailed benchmarking research.
   - `FINISH`:
     - Scope: Signifies that all required steps have been successfully executed and verified, or that the request can be completely answered without further worker delegations.

3. Delegation Rules & Multi-Step Orchestration:
   - Break down complex multi-domain requests into sequential worker delegations.
   - Route to one worker at a time. Provide specific, unambiguous, step-by-step instructions in the `instructions` field.
   - When a worker returns control with its execution summary and history, evaluate whether additional worker actions are needed.
   - If a previous step failed, evaluate whether to retry with adjusted instructions, route to a diagnostic worker, or terminate with an explanation.
   - Once all objectives are met, emit `next_node: "FINISH"` with a comprehensive executive summary in `instructions`.

4. Output Schema Constraints:
   - You must strictly output a valid `RoutingDecision` object with:
     - `next_node`: exactly one of "social_worker", "mobile_worker", "research_worker", or "FINISH".
     - `reasoning`: clear step-by-step logical justification for this decision.
     - `instructions`: concrete instructions for the target worker, or final executive synthesis if finishing.
"""
```

---

### 2.4 StateGraph Assembly & Single Entrypoint (`supervisor.py`)

The StateGraph assembly in `supervisor.py` provides:
1. `create_supervisor_node(llm, system_prompt, fallback_router)`: Factory for the Decision-First supervisor node.
2. `deterministic_fallback_router(state)`: Zero-network keyword & history router for offline testing and fallback recovery.
3. `create_control_plane_graph(llm, worker_llm, checkpointer, max_iterations, connection_string, testing)`: Compiles the full StateGraph with checkpointer integration.
4. `run_control_plane(...)` & `async_run_control_plane(...)`: High-level sync and async execution entrypoints.
5. CLI execution entrypoint with `load_dotenv()` (Rule R26).

```python
def create_control_plane_graph(
    llm: Optional[BaseChatModel] = None,
    worker_llm: Optional[BaseChatModel] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
    max_iterations: int = 10,
    connection_string: Optional[str] = None,
    testing: bool = False,
) -> CompiledStateGraph:
    """
    Constructs and compiles the unified Antigravity Control Plane StateGraph.
    """
    builder = StateGraph(AgentState)

    # 1. Register Supervisor and Worker nodes
    supervisor_node = create_supervisor_node(llm=llm)
    social_node = create_social_worker(llm=worker_llm)
    mobile_node = create_mobile_worker(llm=worker_llm)
    research_node = create_research_worker(llm=worker_llm)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("social_worker", social_node)
    builder.add_node("mobile_worker", mobile_node)
    builder.add_node("research_worker", research_node)

    # 2. Add entry edge
    builder.add_edge(START, "supervisor")

    # 3. Resolve checkpointer backend
    resolved_checkpointer = checkpointer
    if resolved_checkpointer is None:
        resolved_checkpointer = get_checkpointer(
            connection_string=connection_string,
            testing=testing,
        )

    # 4. Compile graph
    return builder.compile(checkpointer=resolved_checkpointer)
```

---

## 3. Fallback Routing & Adversarial Hardening

### 3.1 Deterministic Fallback Router
To guarantee 100% test reliability and zero-stall offline execution, a deterministic fallback router inspects the `task_intent`, recent messages, and `execution_history`:
- **Facebook / YouTube / Social keywords** (and `social_worker` not yet executed in current pass) -> `social_worker`
- **ADB / Android / Termux / Tap / Intent keywords** (and `mobile_worker` not yet executed in current pass) -> `mobile_worker`
- **Research / Rules / Benchmarks / Evaluate keywords** (and `research_worker` not yet executed in current pass) -> `research_worker`
- When all required workers have executed or no further keywords match -> `FINISH`

### 3.2 Error Trapping & Tiered Cascade
In compliance with Rule R27 (Zero-Friction Fallback), if the LLM raises a 429 quota error or a Pydantic `ValidationError`:
1. The supervisor catches the exception.
2. Invokes the fallback router or secondary model if configured.
3. If unrecoverable, returns `Command(goto=END, update={"status": "FAILED", "execution_history": [...]})` instead of crashing the state machine.

---

## 4. Verification & Testing Matrix (Milestone M4 Preview)

| Tier | Category | Test Cases | Objective |
|---|---|---|---|
| **Tier 1** | Schema & Unit | 5+ cases in `test_schemas.py` | Validate `RoutingDecision` fields, Literal constraint, non-empty validators, whitespace stripping |
| **Tier 2** | Boundary & Recursion | 5+ cases in `test_orchestrator.py` | Validate `max_iterations` recursion guard, empty state handling, missing fields recovery |
| **Tier 3** | Pairwise Sequence | 5+ cases in `test_orchestrator.py` | Verify multi-worker sequences: supervisor -> research -> mobile -> social -> finish |
| **Tier 4** | Real-World Workflows | 5 application scenarios | Social deployment, Termux automation, architectural proposal evaluation, multi-turn orchestration, loop exhaustion |
| **Tier 5** | Adversarial Hardening | 5+ stress cases | Malformed LLM outputs, simulated 429 exceptions, concurrent checkpointer multi-threading |

---

## 5. Artifact Summary
The M3 implementation will create:
1. `schemas.py`: Pydantic `RoutingDecision`, `ControlPlaneConfig`, `WorkflowStatus`.
2. `prompts.py`: `SUPERVISOR_SYSTEM_PROMPT` containing domain mappings and Decision-First instructions.
3. `supervisor.py`: Canonical entrypoint, `create_supervisor_node`, `create_control_plane_graph`, `run_control_plane`, and CLI runner.
4. `tests/test_schemas.py` / `test_orchestrator.py`: Deterministic test suite verifying StateGraph compilation, Decision-First routing, and recursion guard.
