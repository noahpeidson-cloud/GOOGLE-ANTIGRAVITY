# Milestone M3 Architectural Analysis: Central Supervisor Orchestrator

**Target Project Directory:** `C:\Users\noahp\teamwork_projects\antigravity_control_plane`  
**Author:** explorer_m3_2  
**Date:** 2026-08-27  

---

## 1. Executive Summary & Problem Boundary

The Antigravity Control Plane consolidates fragmented, standalone agent scripts into a unified, top-down orchestrator utilizing the **Hierarchical Supervisor Pattern** in LangGraph.

Milestone M3 establishes the central orchestration engine in `supervisor.py`, which is the **canonical single entrypoint** for the entire control plane. 

### Core Responsibilities of M3:
1. **Hub-and-Spoke Topology**: StateGraph with an explicit entrypoint `START -> supervisor`, wiring three stateless worker subsystems (`social_worker`, `mobile_worker`, `research_worker`) and terminating at `END`.
2. **Inter-Worker Isolation**: Worker nodes have zero direct edges between each other. All transitions pass through the `supervisor` hub via atomic LangGraph `Command` objects.
3. **Decision-First Routing Engine**: The supervisor utilizes `llm.with_structured_output(RoutingDecision)` to classify intent without tool-calling overhead.
4. **Dynamic `Command` Transitions**: Handing off to worker nodes via `Command(goto="<worker_name>", update={...})` and to `END` (`"__end__"`) when `next_node == "FINISH"` or when termination conditions are met.
5. **Anti-Infinite-Loop Recursion Guard**: Monotonically tracking `iteration_count` on every supervisor cycle and forcing `goto=END` when `iteration_count >= max_iterations` with status `TERMINATED_LOOP_LIMIT` (or `FAILED`), preventing hanging or quota exhaustion.
6. **Canonical Single Entrypoint Factory**: `create_control_plane_graph(checkpointer=None, llm=None, max_iterations=10, ...)` compiling a ready-to-use `CompiledStateGraph` supporting synchronous/asynchronous invocation, streaming, and PostgreSQL/in-memory checkpointing.

---

## 2. Hub-and-Spoke StateGraph Topology & Node Registry

### 2.1 Graph Architecture

```
                      +-------------------+
                      |      START        |
                      +---------+---------+
                                |
                                v
                      +-------------------+
             +------->|    supervisor     |<-------+
             |        +---------+---------+        |
             |                  |                  |
      Command(goto=sup)         |           Command(goto=sup)
             |                  |                  |
             |        +---------+---------+        |
             |        | Dynamic Command   |        |
             |        | Routing:          |        |
             |        | - social_worker   |        |
             |        | - mobile_worker   |        |
             |        | - research_worker |        |
             |        | - FINISH -> END   |        |
             |        +----+----+----+----+        |
             |             |    |    |             |
             |             |    |    +-------+     |
             |             |    +-----+      |     |
             |             v          v      v     |
             |     +-------------+  +-------------+|
             +-----+social_worker|  |mobile_worker|+
             |     +-------------+  +-------------+
             |                            |
             |     +---------------+      |
             +-----+research_worker|<-----+
                   +---------------+
                           |
                     (Upon FINISH
                     or Loop Limit)
                           v
                      +---------+
                      |   END   |
                      +---------+
```

### 2.2 Node Definitions & Registered Names
The graph topology registers exactly four functional nodes plus LangGraph built-ins (`START`, `END`):

| Node Identifier | Subsystem / Role | Action Engine | Handoff Destination |
|---|---|---|---|
| `supervisor` | Central routing & lifecycle orchestrator | Decision-First `with_structured_output` | Dynamic (`social_worker`, `mobile_worker`, `research_worker`, or `END`) |
| `social_worker` | Facebook/YouTube campaign & ADB dispatch | `bind_tools` (`SOCIAL_TOOLS`) | `Command(update={...}, goto="supervisor")` |
| `mobile_worker` | 4-tier Android/Termux automation | `bind_tools` (`MOBILE_TOOLS`) | `Command(update={...}, goto="supervisor")` |
| `research_worker` | FTS5 workspace rules & deep research | `bind_tools` (`RESEARCH_TOOLS`) | `Command(update={...}, goto="supervisor")` |

### 2.3 Strict Inter-Worker Isolation
- In accordance with ORIGINAL_REQUEST §R2 and PROJECT.md §10, **worker nodes cannot talk to each other directly**.
- There are no static edges connecting `social_worker -> mobile_worker` or `mobile_worker -> research_worker`.
- Every worker handoff returns control and mutated state to `supervisor`. The supervisor evaluates the updated state, updates `iteration_count`, and decides the subsequent step.

---

## 3. Dynamic `Command` Return Semantics & Destination Mapping

### 3.1 LangGraph `Command` Mechanics
In LangGraph 0.2.70+ / 1.x, nodes control both state mutation and edge traversal by returning a `Command` object:
```python
from langgraph.types import Command
from langgraph.graph import END

# Routing to a worker node
Command(
    goto="social_worker",
    update={
        "iteration_count": new_iter,
        "status": "RUNNING",
        "next_worker": "social_worker",
        "execution_history": [history_entry],
    }
)

# Routing to termination (FINISH)
Command(
    goto=END,  # maps to "__end__"
    update={
        "iteration_count": new_iter,
        "status": "COMPLETED",
        "next_worker": None,
        "summary": summary_text,
        "execution_history": [history_entry],
    }
)
```

### 3.2 Destination Mapping & Handling for `FINISH -> END`
The Pydantic schema `RoutingDecision` uses `next_node: Literal["social_worker", "mobile_worker", "research_worker", "FINISH"]`.

**Crucial Implementation Caveat:**  
If a node returns `Command(goto="FINISH")`, LangGraph treats `"FINISH"` as an unregistered node name and logs `Task supervisor wrote to unknown channel branch:to:FINISH, ignoring it`.

Therefore, the supervisor MUST explicitly map `next_node` values:
```python
DESTINATION_MAP = {
    "social_worker": "social_worker",
    "mobile_worker": "mobile_worker",
    "research_worker": "research_worker",
    "FINISH": END,
    END: END,
    "__end__": END,
    None: END,
}
```
If `decision.next_node == "FINISH"` or `decision.next_node not in WORKER_NODES`:
- Map destination to `END`.
- Update state status to `"COMPLETED"` (or keep `"FAILED"` if prior error).
- Record completion entry in `execution_history`.

---

## 4. Anti-Infinite-Loop Recursion Guard Specification

### 4.1 Threat Model & Failure Scenarios
1. **Sycophantic / Non-Converging Worker Loops**: A worker repeatedly failing a step and returning back to supervisor without resolving, causing infinite back-and-forth cycles.
2. **Ambiguous LLM Routing Loops**: An LLM ping-ponging between two workers indefinitely.
3. **Rate Limit / API Hangs**: Degradation leading to endless retries.

### 4.2 Guard Mechanism & State Transitions
- **State Fields:** `iteration_count: int` (initialized to 0) and `max_iterations: int` (default 10).
- **Monotonic Increment:** Every execution of `supervisor_node` computes `new_iter = state.get("iteration_count", 0) + 1`.
- **Threshold Check:**
  ```python
  max_iter = state.get("max_iterations") or max_iterations
  if new_iter >= max_iter or state.get("iteration_count", 0) >= max_iter:
      guard_err = f"Recursion limit reached: iteration_count ({new_iter}) >= max_iterations ({max_iter})."
      guard_entry = create_history_entry(
          node="supervisor",
          action="recursion_guard_triggered",
          status="FAILED",
          error=guard_err,
          details={
              "iteration_count": new_iter,
              "max_iterations": max_iter,
              "reason": "loop_limit_exceeded",
          },
      )
      guard_msg = AIMessage(content=f"[Supervisor] Execution terminated by recursion guard: {guard_err}")
      return Command(
          goto=END,
          update={
              "iteration_count": new_iter,
              "status": "TERMINATED_LOOP_LIMIT",
              "execution_history": [guard_entry],
              "messages": [guard_msg],
              "next_worker": None,
              "summary": f"Execution halted by recursion guard after {new_iter} iterations.",
          },
      )
  ```
- **Validation Compliance:** `status="TERMINATED_LOOP_LIMIT"` is an approved literal in `AgentStateValidator.status` in `state.py`.
- **Zero-Discretion Guarantee:** Execution immediately forces `goto=END`. No further LLM calls or worker turns are allowed once threshold is hit.

---

## 5. Canonical Entrypoint Factory: `create_control_plane_graph`

### 5.1 Function Signature
```python
def create_control_plane_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    llm: Optional[BaseChatModel] = None,
    max_iterations: int = 10,
    worker_llm: Optional[BaseChatModel] = None,
    workers: Optional[Dict[str, Callable[[AgentState], Command]]] = None,
    system_prompt: Optional[str] = None,
    max_prune_messages: int = 20,
) -> CompiledStateGraph:
```

### 5.2 Factory Implementation Steps
1. **Initialize StateGraph**: `builder = StateGraph(AgentState)`
2. **Build Supervisor Node**:
   ```python
   supervisor_node = create_supervisor_node(
       llm=llm,
       max_iterations=max_iterations,
       system_prompt=system_prompt,
       max_prune_messages=max_prune_messages,
   )
   builder.add_node("supervisor", supervisor_node)
   ```
3. **Register Worker Nodes**:
   - If `workers` dictionary is passed (e.g. In custom or mocked test suites), add each node from `workers`.
   - If `workers` is `None`:
     - If `worker_llm` or `llm` is provided, instantiate worker nodes via `create_social_worker(llm=...)`, `create_mobile_worker(llm=...)`, `create_research_worker(llm=...)`.
     - Otherwise, use pre-instantiated default worker nodes (`social_worker`, `mobile_worker`, `research_worker` from `workers`).
     - Register `builder.add_node("social_worker", s_worker)`
     - Register `builder.add_node("mobile_worker", m_worker)`
     - Register `builder.add_node("research_worker", r_worker)`
4. **Wire Hub-and-Spoke Entrypoint**:
   ```python
   builder.add_edge(START, "supervisor")
   ```
5. **Compile Graph with Checkpointer**:
   ```python
   return builder.compile(checkpointer=checkpointer)
   ```

---

## 6. Complete Blueprint for `supervisor.py`

Below is the verified code design for `supervisor.py`:

```python
"""
Central Supervisor Orchestrator & Canonical StateGraph Entrypoint for Antigravity Control Plane.

Implements the Hierarchical Supervisor Pattern in LangGraph with Decision-First routing,
hub-and-spoke StateGraph topology, dynamic Command handoffs, and loop recursion guards.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from schemas import RoutingDecision
from state import (
    AgentState,
    create_history_entry,
    create_initial_state,
    prune_message_history,
)
from workers import (
    create_mobile_worker,
    create_research_worker,
    create_social_worker,
    mobile_worker,
    research_worker,
    social_worker,
)

logger = logging.getLogger(__name__)

SUPERVISOR_SYSTEM_PROMPT = """You are the Central Supervisor Orchestrator for the Antigravity Control Plane.
Your role is to analyze high-level user tasks and route execution to the appropriate stateless worker subsystem:

1. 'social_worker': Handles social media media deployments, Facebook cover/post automation via ADB, YouTube API uploads, social manifest validation, and telemetry logging.
2. 'mobile_worker': Handles 4-tier Android automation, ADB shell commands, Termux command injection, UIAutomator screen inspection/taps, Samsung AutoBlocker toggles, and Android app intents/permissions.
3. 'research_worker': Handles deep research workflows, workspace rules queries via SQLite FTS5, architectural design evaluations against project rules, and saving research reports.
4. 'FINISH': Select when the user's task has been completely satisfied, all requested actions are finished, or no further actions are required.

CRITICAL OPERATING RULES:
- You are a routing engine. Do NOT execute domain tools directly.
- Inspect the task intent, conversation history, and execution history.
- If a multi-step task requires multiple subsystems in sequence, route to the next pending subsystem.
- When all required steps are complete, select 'FINISH'.
"""


def score_domain_intent(text: str, executed_nodes: set) -> str:
    """
    Deterministic domain classifier scoring intent against domain keyword sets.
    """
    t = text.lower()
    scores = {
        "social_worker": sum(1 for k in ["facebook", "youtube", "social", "campaign", "manifest", "cover", "telemetry"] if k in t),
        "mobile_worker": sum(1 for k in ["termux", "adb", "mobile", "android", "uiautomator", "tap", "phone", "device", "permission", "samsung"] if k in t),
        "research_worker": sum(1 for k in ["research", "rule", "rules", "evaluate", "proposal", "trend", "query", "fts5", "sqlite"] if k in t),
    }
    available = {k: v for k, v in scores.items() if k not in executed_nodes and v > 0}
    if not available:
        return "FINISH"
    return max(available, key=available.get)


def fallback_classify_intent(
    task_intent: str,
    messages: Sequence[BaseMessage],
    history: Sequence[Dict[str, Any]],
) -> Tuple[str, str, str]:
    """
    Robust deterministic fallback router when no LLM is provided or structured output fails.
    """
    executed_nodes = {
        entry.get("node") or entry.get("worker")
        for entry in history
        if entry.get("status") == "SUCCESS"
    }

    # Check if a prior worker experienced fatal failure
    failed_entries = [
        e for e in history
        if e.get("status") == "FAILED" and (e.get("node") or e.get("worker")) != "supervisor"
    ]
    if failed_entries:
        err = failed_entries[-1].get("error", "Worker execution failure")
        return "FINISH", f"Halting workflow due to worker failure: {err}", ""

    combined_text = task_intent.lower()
    for m in messages:
        if hasattr(m, "content") and isinstance(m.content, str):
            combined_text += " " + m.content.lower()

    target = score_domain_intent(combined_text, executed_nodes)
    if target == "social_worker":
        return "social_worker", "Routing to Social Worker for media deployment", "Execute social deployment actions"
    elif target == "mobile_worker":
        return "mobile_worker", "Routing to Mobile Worker for Android/ADB automation", "Execute mobile commands"
    elif target == "research_worker":
        return "research_worker", "Routing to Research Worker for deep research/rules", "Execute research query"
    else:
        return "FINISH", "Workflow complete or no further worker action required", "Task satisfied"


def create_supervisor_node(
    llm: Optional[BaseChatModel] = None,
    max_iterations: int = 10,
    system_prompt: Optional[str] = None,
    max_prune_messages: int = 20,
) -> Callable[[AgentState], Command]:
    """
    Constructs the Supervisor node callable conforming to LangGraph node specifications.
    """
    resolved_prompt = system_prompt or SUPERVISOR_SYSTEM_PROMPT

    def supervisor_node(state: AgentState) -> Command:
        # 1. Monotonic Iteration Counter & Recursion Guard
        current_iter = state.get("iteration_count", 0)
        new_iter = current_iter + 1
        max_iter = state.get("max_iterations") or max_iterations

        if current_iter >= max_iter or new_iter > max_iter:
            guard_err = f"Recursion limit reached: iteration_count ({new_iter}) exceeds max_iterations ({max_iter})."
            logger.warning("[Supervisor] %s", guard_err)
            guard_entry = create_history_entry(
                node="supervisor",
                action="recursion_guard_triggered",
                status="FAILED",
                error=guard_err,
                details={"iteration_count": new_iter, "max_iterations": max_iter},
            )
            guard_msg = AIMessage(content=f"[Supervisor] Recursion guard triggered: {guard_err}")
            return Command(
                goto=END,
                update={
                    "iteration_count": new_iter,
                    "status": "TERMINATED_LOOP_LIMIT",
                    "execution_history": [guard_entry],
                    "messages": [guard_msg],
                    "next_worker": None,
                    "summary": f"Halted by recursion guard after {new_iter} iterations.",
                },
            )

        # 2. State Extraction
        task_intent = state.get("task_intent", "")
        raw_messages = list(state.get("messages", []))
        history = list(state.get("execution_history", []))
        summary = state.get("summary", "")

        # 3. Context Pruning
        pruned_messages: List[BaseMessage] = []
        if len(raw_messages) > max_prune_messages:
            pruned_messages = prune_message_history(raw_messages, max_messages=max_prune_messages)

        # 4. Decision-First Routing Engine
        next_node: str = "FINISH"
        reasoning: str = ""
        instructions: str = ""

        if llm is not None and hasattr(llm, "with_structured_output"):
            try:
                structured_llm = llm.with_structured_output(RoutingDecision)
                prompt_msgs: List[BaseMessage] = [SystemMessage(content=resolved_prompt)]
                if summary:
                    prompt_msgs.append(SystemMessage(content=f"Workflow Summary so far: {summary}"))
                if raw_messages:
                    prompt_msgs.extend(raw_messages)
                elif task_intent:
                    prompt_msgs.append(HumanMessage(content=task_intent))

                decision = structured_llm.invoke(prompt_msgs)
                if isinstance(decision, dict):
                    decision = RoutingDecision(**decision)
                next_node = decision.next_node
                reasoning = decision.reasoning
                instructions = decision.instructions
            except Exception as exc:
                logger.warning("[Supervisor] LLM structured output routing failed (%s); falling back to heuristic", exc)
                next_node, reasoning, instructions = fallback_classify_intent(task_intent, raw_messages, history)
        else:
            # Deterministic fallback router
            next_node, reasoning, instructions = fallback_classify_intent(task_intent, raw_messages, history)

        # 5. Compile Dynamic Command Handoff
        history_entry = create_history_entry(
            node="supervisor",
            action=f"route:{next_node}",
            status="SUCCESS",
            details={
                "target": next_node,
                "reasoning": reasoning,
                "instructions": instructions,
                "iteration_count": new_iter,
            },
        )

        new_msgs: List[BaseMessage] = list(pruned_messages)

        if next_node == "FINISH" or next_node == END or next_node == "__end__":
            summary_out = summary or f"Workflow completed successfully. Reason: {reasoning}"
            if instructions:
                new_msgs.append(AIMessage(content=f"[Supervisor Complete] {instructions}"))
            return Command(
                goto=END,
                update={
                    "iteration_count": new_iter,
                    "status": "COMPLETED" if state.get("status") != "FAILED" else "FAILED",
                    "next_worker": None,
                    "summary": summary_out,
                    "execution_history": [history_entry],
                    "messages": new_msgs,
                },
            )

        # Route to worker node
        if instructions:
            new_msgs.append(AIMessage(content=f"[Supervisor Directive -> {next_node}] {instructions}"))

        return Command(
            goto=next_node,
            update={
                "iteration_count": new_iter,
                "status": "RUNNING",
                "next_worker": next_node,
                "execution_history": [history_entry],
                "messages": new_msgs,
            },
        )

    supervisor_node.__name__ = "supervisor"
    return supervisor_node


def create_control_plane_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    llm: Optional[BaseChatModel] = None,
    max_iterations: int = 10,
    worker_llm: Optional[BaseChatModel] = None,
    workers: Optional[Dict[str, Callable[[AgentState], Command]]] = None,
    system_prompt: Optional[str] = None,
    max_prune_messages: int = 20,
) -> CompiledStateGraph:
    """
    Constructs and compiles the canonical Antigravity Control Plane StateGraph.

    Assembles a Hub-and-Spoke topology with START -> supervisor, delegating intents
    to stateless worker nodes (social_worker, mobile_worker, research_worker) via
    dynamic Command routing, and terminating cleanly at END.
    """
    builder = StateGraph(AgentState)

    # 1. Add Supervisor Node
    sup_node = create_supervisor_node(
        llm=llm,
        max_iterations=max_iterations,
        system_prompt=system_prompt,
        max_prune_messages=max_prune_messages,
    )
    builder.add_node("supervisor", sup_node)

    # 2. Add Worker Nodes
    if workers is not None:
        for w_name, w_fn in workers.items():
            builder.add_node(w_name, w_fn)
    else:
        target_worker_llm = worker_llm if worker_llm is not None else llm
        if target_worker_llm is not None:
            s_worker = create_social_worker(llm=target_worker_llm)
            m_worker = create_mobile_worker(llm=target_worker_llm)
            r_worker = create_research_worker(llm=target_worker_llm)
        else:
            s_worker = social_worker
            m_worker = mobile_worker
            r_worker = research_worker

        builder.add_node("social_worker", s_worker)
        builder.add_node("mobile_worker", m_worker)
        builder.add_node("research_worker", r_worker)

    # 3. Add Hub-and-Spoke Entrypoint
    builder.add_edge(START, "supervisor")

    # 4. Compile Graph
    return builder.compile(checkpointer=checkpointer)
```

---

## 7. Interaction with Database Checkpointing (`db.py`)

The StateGraph produced by `create_control_plane_graph` seamlessly supports all checkpointer types from `db.py`:
- `PostgresSaver` with synchronous `psycopg_pool.ConnectionPool`
- `AsyncPostgresSaver` with asynchronous `psycopg_pool.AsyncConnectionPool`
- `MemorySaver` (deterministic test fixture)
- `None` (uncheck-pointed graph for stateless execution)

When invoked with `config={"configurable": {"thread_id": "session_123"}}`:
- Every node execution checkpoint is persisted.
- State resumption across supervisor cycles is preserved.

---

## 8. Verification Strategy & Test Matrix (Milestone M4 Preview)

To verify the M3 implementation across all 5 test tiers:

| Tier | Focus | Test Scenarios | Verification Command |
|---|---|---|---|
| Tier 1 | Feature Isolation | Graph compilation, `START -> supervisor`, node presence, `RoutingDecision` parsing | `python -m pytest tests/test_supervisor.py` |
| Tier 2 | Boundary & Limits | Max iterations recursion guard (`max_iterations=1`, `max_iterations=10`), empty state, missing intent | `python -m pytest tests/test_supervisor.py -k "boundary"` |
| Tier 3 | Decision-First Engine | `MockStructuredModel` with `with_structured_output` for all 4 destinations | `python -m pytest tests/test_supervisor.py -k "structured"` |
| Tier 4 | Real-World Workflows | Social campaign, Termux automation, deep research, multi-turn sequence | `python -m pytest test_orchestrator.py` |
| Tier 5 | Adversarial Hardening | Corrupted state, invalid worker returns, LLM exceptions, PostgreSQL connection failure fallback | `python -m pytest tests/test_supervisor.py -k "adversarial"` |

---

## 9. Conclusion

The Hub-and-Spoke architecture using LangGraph dynamic `Command` routing achieves complete compliance with `ORIGINAL_REQUEST.md`, `PROJECT.md`, and `TEST_INFRA.md`. It eliminates brittle conditional edges, enforces inter-worker isolation, guarantees loop termination via monotonically increasing iteration tracking, and provides a clean single factory entrypoint `create_control_plane_graph`.
