# Antigravity Control Plane: Central Supervisor Routing Engine & StateGraph Topology Specification

**Author:** spec_miner_routing_1  
**Target Project:** `C:\Users\noahp\teamwork_projects\antigravity_control_plane`  
**Date:** 2026-08-27  
**Status:** Mined Specification (Ready for Implementation)

---

## 1. Overview & Architectural Blueprint

The **Antigravity Control Plane** refactors standalone, fragmented subagents into a unified, top-down Hierarchical Supervisor system built on LangGraph. The system employs the **Decision-First Hybrid Pattern** to replace brittle, multi-step tool-calling routers with deterministic, structured-output classification.

### Core Architectural Principles
1. **Decision-First Supervisor**: The Central Supervisor uses `with_structured_output(RoutingDecision)` to classify user intents and route to the appropriate worker subsystem (`social_worker`, `mobile_worker`, `research_worker`) or terminate with `FINISH`. It never uses tool calling for routing.
2. **Stateless Action Workers**: Worker nodes execute specialized tasks by binding domain tools (`bind_tools()`) and must remain completely stateless across distinct invocations.
3. **Command-Based Handoff**: All state transitions and routing directions are encapsulated in LangGraph's `Command(update={...}, goto='...')` object. Workers always return `goto="supervisor"`; workers never transition directly to each other.
4. **PostgreSQL Checkpointing**: Graph persistence and state snapshots are managed via `PostgresSaver` (`psycopg_pool`) for production-grade concurrency.
5. **Strict Single Entrypoint**: The system is orchestrated from a single canonical file: `supervisor.py`.

---

## 2. Central Supervisor Specification (Decision-First Hybrid Pattern)

### 2.1 Pattern Distinction: Decision-First vs. Tool-Calling Router

| Property | Legacy Tool-Calling Router | Decision-First Hybrid Router (R1) |
| :--- | :--- | :--- |
| **Mechanism** | Exposes dummy tools (e.g. `call_social_agent()`) to LLM | Uses Pydantic schema with `with_structured_output()` |
| **Parsing Overhead** | High (Tool call parsing, parameter extraction, fallback handling) | Minimal (Direct JSON schema validation against Pydantic model) |
| **Schema Drift** | High (LLM may hallucinate tool arguments or call multiple tools) | Zero (Constrained `Literal` choices enforced by schema) |
| **Execution Phase** | Intertwines routing decision with tool execution | Decouples routing (Decision-First) from worker execution (Tool-Binding) |
| **LangGraph Return** | Conditional edge parsing or tool node execution | Returns `Command(goto=decision.next_node, update=...)` |

### 2.2 Supervisor Decision Logic & Prompt Engineering

The supervisor receives the global `ControlPlaneState`, evaluates the conversation history (`messages`), current task requirements, and any prior worker outputs, and decides the next action.

```
+-----------------------------------------------------------------------------------+
|                               USER REQUEST                                        |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
                         +---------------------------------+
                         |         supervisor_node         |
                         |  (with_structured_output schema)|
                         +---------------------------------+
                                          |
        +---------------------------------+--------------------------------+
        |                                 |                                |
        v                                 v                                v
+-------------------+             +-------------------+            +-------------------+
|   social_worker   |             |   mobile_worker   |            |  research_worker  |
|  (Facebook, YT)   |             | (ADB, Termux, UI) |            | (Deep Search, ML) |
+-------------------+             +-------------------+            +-------------------+
        |                                 |                                |
        +---------------------------------+--------------------------------+
                                          |
                       Command(update=..., goto='supervisor')
                                          |
                                          v
                         +---------------------------------+
                         |         supervisor_node         |
                         |  (Evaluates Worker Response)    |
                         +---------------------------------+
                                          |
                       (Task Finished: next_node == 'FINISH')
                                          |
                                          v
                                    +-----------+
                                    |    END    |
                                    +-----------+
```

---

## 3. Structured Output Specification (`with_structured_output`)

### 3.1 Pydantic Schema Definition

The supervisor's routing contract is defined by `RoutingDecision`:

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

class SubsystemRoute(str):
    SOCIAL_WORKER = "social_worker"
    MOBILE_WORKER = "mobile_worker"
    RESEARCH_WORKER = "research_worker"
    FINISH = "FINISH"

class RoutingDecision(BaseModel):
    """Structured routing decision generated by the Central Supervisor."""
    
    next_node: Literal["social_worker", "mobile_worker", "research_worker", "FINISH"] = Field(
        ...,
        description=(
            "The destination worker node to execute next, or 'FINISH' if all user "
            "objectives are fully accomplished and ready for final output."
        )
    )
    reasoning: str = Field(
        ...,
        description="Detailed step-by-step technical rationale explaining why this subsystem was chosen or why the task is finished."
    )
    instructions_for_worker: Optional[str] = Field(
        None,
        description="Context-specific, actionable instructions passed to the selected worker node."
    )
    confidence_score: Optional[float] = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Self-evaluated routing classification confidence."
    )
```

### 3.2 Supervisor System Prompt Specification

```python
SUPERVISOR_SYSTEM_PROMPT = """You are the Central Supervisor of the Antigravity Control Plane.
Your role is to orchestrate tasks across three specialized, stateless worker subsystems:

1. 'social_worker': Handles social media deployment, asset uploading (Facebook covers, YouTube thumbnails), and media distribution.
2. 'mobile_worker': Handles mobile device orchestration, headless ADB commands, Termux automation, and mobile UI interactions.
3. 'research_worker': Handles deep research, data validation, web scraping, and ML trend analysis.

Operating Rules:
- Analyze the user request and existing conversation history in the state.
- Choose EXACTLY ONE worker to delegate the immediate next step to, OR select 'FINISH' if the user's objective is fully satisfied.
- Provide clear, concise, actionable instructions for the chosen worker in `instructions_for_worker`.
- Do NOT perform worker tasks yourself. You are solely the decision-maker and router.
- When all worker outputs fulfill the user's request, choose 'FINISH' and provide the final synthesis in `reasoning`.
"""
```

### 3.3 LLM Invocation Mechanics

```python
def create_supervisor_chain(llm):
    """Creates the structured LLM chain for the supervisor."""
    structured_llm = llm.with_structured_output(RoutingDecision)
    return structured_llm
```

---

## 4. Handoff Protocol & `Command` Object Specification

### 4.1 LangGraph `Command` Mechanics

LangGraph `Command` (`langgraph.types.Command`) is the foundational mechanism for atomic state mutation and dynamic graph transitions.

#### Supervisor Node Implementation:
```python
from langgraph.types import Command
from langgraph.graph import END
from langchain_core.messages import AIMessage

def supervisor_node(state: ControlPlaneState, config: dict = None) -> Command[Literal["social_worker", "mobile_worker", "research_worker", "__end__"]]:
    # Check iteration limits to prevent infinite loops
    iteration = state.get("iteration_count", 0) + 1
    max_iterations = state.get("max_iterations", 10)
    
    if iteration > max_iterations:
        return Command(
            goto=END,
            update={
                "status": "FAILED",
                "iteration_count": iteration,
                "final_response": f"Max iteration limit ({max_iterations}) exceeded. Terminating to prevent infinite loop.",
                "routing_history": ["supervisor->END (limit_exceeded)"]
            }
        )
    
    # Run structured routing decision
    messages = state.get("messages", [])
    decision: RoutingDecision = supervisor_chain.invoke([
        {"role": "system", "content": SUPERVISOR_SYSTEM_PROMPT},
        *messages
    ])
    
    # Process routing choice
    if decision.next_node == "FINISH":
        return Command(
            goto=END,
            update={
                "status": "COMPLETED",
                "iteration_count": iteration,
                "final_response": decision.reasoning,
                "routing_history": [f"supervisor->END (FINISH: {decision.reasoning})"]
            }
        )
    
    # Route to selected worker
    route_msg = AIMessage(
        content=f"[Supervisor] Routing to {decision.next_node}. Instruction: {decision.instructions_for_worker}"
    )
    
    return Command(
        goto=decision.next_node,
        update={
            "messages": [route_msg],
            "current_instruction": decision.instructions_for_worker,
            "iteration_count": iteration,
            "routing_history": [f"supervisor->{decision.next_node}"]
        }
    )
```

#### Worker Node Implementation Pattern:
```python
def social_worker_node(state: ControlPlaneState) -> Command[Literal["supervisor"]]:
    instruction = state.get("current_instruction")
    # Execute worker logic / tool bindings
    result = execute_social_action(instruction)
    
    worker_message = AIMessage(
        content=f"[SocialWorker] Completed: {result.get('summary', 'Done')}"
    )
    
    return Command(
        goto="supervisor",
        update={
            "messages": [worker_message],
            "last_worker": "social_worker",
            "worker_results": {"social_worker": result},
            "routing_history": ["social_worker->supervisor"]
        }
    )
```

### 4.2 Guardrails for Command Transitions
1. **Forbidden Direct Worker-to-Worker Transitions**: Workers must NEVER specify `goto="mobile_worker"` or `goto="research_worker"`. All worker returns MUST have `goto="supervisor"`.
2. **Zero Duplicate Static Edges**: Do NOT add static edges with `builder.add_edge("social_worker", "supervisor")` when using `Command(goto="supervisor")`. Doing so causes parallel execution branching.
3. **Atomic State Updates**: State updates specified in `Command.update` are applied atomically before the destination node is invoked.

---

## 5. StateGraph Topology & State Schema Specification

### 5.1 Global State Schema (`ControlPlaneState`)

```python
import operator
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict
from langchain_core.messages import BaseMessage

class ControlPlaneState(TypedDict):
    """Global typed state for the Antigravity Control Plane StateGraph."""
    messages: Annotated[List[BaseMessage], operator.add]
    current_intent: str
    current_instruction: Optional[str]
    last_worker: Optional[str]
    routing_history: Annotated[List[str], operator.add]
    iteration_count: int
    max_iterations: int
    worker_results: Dict[str, Any]
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
    final_response: Optional[str]
```

### 5.2 StateGraph Assembly

```python
from langgraph.graph import StateGraph, START, END

def build_control_plane_graph(checkpointer=None, llm=None):
    """Constructs and compiles the Central Supervisor StateGraph."""
    builder = StateGraph(ControlPlaneState)
    
    # 1. Register Supervisor and Worker nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("social_worker", social_worker_node)
    builder.add_node("mobile_worker", mobile_worker_node)
    builder.add_node("research_worker", research_worker_node)
    
    # 2. Add entrypoint edge from START to supervisor
    builder.add_edge(START, "supervisor")
    
    # 3. Dynamic edges are governed entirely by Command(goto=...) in nodes.
    # No manual add_conditional_edges needed when nodes return Command objects.
    
    # 4. Compile with checkpointer
    graph = builder.compile(checkpointer=checkpointer)
    return graph
```

---

## 6. File Layout & Module Specifications for `supervisor.py`

### 6.1 Target Project File Tree

```
C:\Users\noahp\teamwork_projects\antigravity_control_plane/
├── supervisor.py              # Canonical entrypoint orchestrator script
├── state.py                   # ControlPlaneState & RoutingDecision Pydantic models
├── config.py                  # Database connection settings & environment config
├── checkpointer.py            # PostgresSaver initialization & pool management
├── workers/
│   ├── __init__.py
│   ├── social_worker.py       # Social Deployer worker subsystem (bind_tools)
│   ├── mobile_worker.py       # Mobile Zero-Touch worker subsystem (bind_tools)
│   └── research_worker.py     # Deep Research worker subsystem (bind_tools)
├── tests/
│   ├── __init__.py
│   ├── test_orchestrator.py   # Deterministic pytest suite mocking workers & routing
│   └── test_supervisor.py     # Isolated tests for supervisor decision logic
├── requirements.txt           # Python dependencies
└── pyproject.toml             # Project metadata & build settings
```

### 6.2 `supervisor.py` Structural Requirements

`supervisor.py` must contain:
1. **Absolute Imports** (adhering to GEMINI.md R16): `from state import ControlPlaneState, RoutingDecision` etc.
2. **Supervisor Node Definition**: Pure decision-first routing function returning `Command`.
3. **Graph Builder Factory**: `create_control_plane_graph(checkpointer=None, llm=None)` to allow dependency injection during test runs.
4. **Direct Execution Block**: `if __name__ == "__main__":` entrypoint parsing CLI args or running an interactive session.

---

## 7. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Routing | Decision-First Classification | Supervisor classifies task intent into discrete worker routes without using tool calling | `ControlPlaneState` (messages, history) | `RoutingDecision` (`next_node`, `reasoning`, `instructions`) | Throws validation error if schema malformed; handled via fallback | ORIGINAL_REQUEST.md § R1, LangGraph spec |
| 2 | Routing | Structured Output Enforcement | Uses `llm.with_structured_output(RoutingDecision)` to guarantee typed routing output | System prompt + Message list | Validated `RoutingDecision` instance | Fallbacks or retries on LLM parsing mismatch | LangGraph / LangChain API |
| 3 | Routing | Finite Subsystem Targets | Allowed routing destinations are strictly constrained to 4 choices (`social_worker`, `mobile_worker`, `research_worker`, `FINISH`) | Target string from LLM | Typed `Literal` route | Pydantic `ValidationError` on illegal string | ORIGINAL_REQUEST.md § R1, R2 |
| 4 | State Machine | Dynamic Command Handoff | Supervisor and workers use `langgraph.types.Command(goto=..., update=...)` for atomic transitions | Target node name + State update dict | Evaluated transition in LangGraph engine | Graph runtime error if `goto` target is not registered in graph | LangGraph Command API |
| 5 | State Machine | Strict Hub-and-Spoke Cyclic Graph | All worker transitions return to `supervisor`; direct worker-to-worker transitions are forbidden | Worker task completion payload | `Command(goto='supervisor', update={...})` | Static validation / test asserts prevent non-supervisor goto | ORIGINAL_REQUEST.md § R2 |
| 6 | State Machine | Graph Entrypoint Configuration | Graph starts at `START` and executes `supervisor` first | Initial user input dictionary | Invocable StateGraph instance | Graph compilation error if entrypoint missing | LangGraph StateGraph spec |
| 7 | State Machine | Graph Terminal Condition | Graph terminates cleanly when supervisor selects `FINISH`, routing to `END` | `RoutingDecision(next_node="FINISH")` | `Command(goto=END, update={"status": "COMPLETED"})` | Iteration limit fallback if `FINISH` never reached | ORIGINAL_REQUEST.md § R1, R2 |
| 8 | Reliability | Cycle Prevention / Iteration Guard | Supervisor tracks `iteration_count` and aborts if `iteration_count > max_iterations` | State `iteration_count`, `max_iterations` | `Command(goto=END, update={"status": "FAILED"})` | Graceful exit with error status instead of infinite recursion | Antigravity Control Plane spec |
| 9 | State | Typed Global State | Global state schema with list reducers (`Annotated[list, operator.add]`) for messages and history | `messages`, `routing_history`, `worker_results` | Merged state dict across graph steps | State key error if un-annotated key mutated concurrently | LangGraph TypedDict spec |
| 10 | Persistence | PostgreSQL Checkpointer | Uses `PostgresSaver` via `psycopg_pool` to persist graph execution snapshots | DB connection pool / DSN | Compiled graph with persistent state checkpoints | Connection error if DB unreachable; mockable for testing | ORIGINAL_REQUEST.md § R3 |

---

## 8. Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | Decision-First Routing | Ambiguous or multi-domain prompt (e.g. "Research market tags and deploy them to Facebook") | Supervisor selects the prerequisite subsystem first (e.g., `research_worker`), receives results on next turn, then delegates to `social_worker`, and finally calls `FINISH`. |
| 2 | Decision-First Routing | Unrecognized / empty user prompt | Supervisor evaluates empty context, requests user clarification, or returns `FINISH` with an explanation. |
| 3 | Cycle Prevention | Worker endlessly reports incomplete task or supervisor repeatedly loops between workers | Iteration guard detects `iteration_count >= max_iterations` (default 10) and forces `goto=END` with `status="FAILED"`. |
| 4 | Structured Output | LLM outputs invalid JSON or non-conforming field names | `with_structured_output` raises a validation exception; supervisor node catches and defaults to a safe re-prompt or fallback route. |
| 5 | Command Handoff | Worker accidentally attempts to return `goto="mobile_worker"` instead of `goto="supervisor"` | Graph static typing and unit tests reject invalid destination; worker contract enforces `Literal["supervisor"]`. |
| 6 | Graph Edges | Both static `add_edge(worker, supervisor)` and `Command(goto='supervisor')` configured | LangGraph executes parallel branches; avoided by exclusively using `Command(goto=...)` with no redundant static edges. |
| 7 | State Merging | Multiple messages added in single turn | `Annotated[List[BaseMessage], operator.add]` properly appends new messages without overwriting history. |
| 8 | Checkpointer Mocking | Unit test environment where PostgreSQL is unavailable | `create_control_plane_graph(checkpointer=MemorySaver())` or `checkpointer=None` allows seamless offline deterministic testing. |
