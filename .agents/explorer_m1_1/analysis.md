# Milestone M1 Analysis & Implementation Strategy
**Target Project:** `antigravity_control_plane`
**Milestone:** M1 — State Management & PostgreSQL Checkpointer Engine
**Author:** explorer_m1_1
**Date:** 2026-08-27

---

## Executive Summary
Milestone M1 establishes the foundational data structures, state reducers, context pruning mechanics, and PostgreSQL checkpoint persistence for the Antigravity Control Plane. The architecture adheres to the LangGraph Hierarchical Supervisor pattern, ensuring isolated, stateless workers communicate exclusively through a strongly-typed global state (`AgentState`) with atomic state updates, context overflow protection, and production concurrency checkpointers.

---

## 1. Dependency Analysis & `requirements.txt` Specification

### Required Packages & Versions
Based on the execution environment (Python 3.13) and LangGraph v1.2+ specifications:

1. **`langgraph>=0.2.0`**: Core framework for StateGraph compilation, node coordination, and `Command` transitions.
2. **`langchain-core>=0.3.0`**: Provides `BaseMessage`, `HumanMessage`, `AIMessage`, `ToolMessage`, `SystemMessage`, and `RemoveMessage`.
3. **`langgraph-checkpoint-postgres>=2.0.0`**: Official PostgreSQL checkpointer adapter (`PostgresSaver`) for LangGraph state persistence.
4. **`psycopg[binary]>=3.2.0`**: Modern PostgreSQL driver for Python with binary extensions for maximum throughput.
5. **`psycopg-pool>=3.2.0`**: Thread-safe connection pool manager (`ConnectionPool`) supporting async and sync connection reuse.
6. **`pydantic>=2.7.0`**: Structured data validation for intent schemas (`RoutingDecision`, tool parameters).
7. **`pytest>=8.0.0`**: Primary test runner for deterministic unit and E2E testing.
8. **`pytest-asyncio>=0.23.0`**: Async test support for checkpointer and LangGraph streams.
9. **`pytest-mock>=3.14.0`**: Fixture-based mocking for external APIs, pools, and workers.
10. **`python-dotenv>=1.0.0`**: Environment variable loading (`POSTGRES_URI`, `DATABASE_URL`).

### Proposed `requirements.txt`
```text
# Antigravity Control Plane Dependencies
# Milestone M1: State Management & PostgreSQL Checkpointer Engine

langgraph>=0.2.0
langchain-core>=0.3.0
langgraph-checkpoint-postgres>=2.0.0
psycopg[binary]>=3.2.0
psycopg-pool>=3.2.0
pydantic>=2.7.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-mock>=3.14.0
python-dotenv>=1.0.0
```

---

## 2. State Schema & Reducer Design (`state.py`)

### Schema Specification: `AgentState`
The `AgentState` TypedDict defines the global state passed between the Supervisor and Worker nodes.

```python
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
import operator

class AgentState(TypedDict):
    """
    Global state container for the Antigravity Control Plane StateGraph.
    
    Fields:
        messages: Sequence of chat and tool messages with LangGraph's add_messages reducer.
        next_worker: Destination worker node ('social_worker', 'mobile_worker', 'research_worker', or None/'FINISH').
        task_intent: High-level classification of user goal extracted by Supervisor.
        execution_history: Append-only audit trail tracking every node action, status, and payload.
        summary: Running textual summary of context/actions when pruning intermediate messages.
        iteration_count: Monotonically increasing counter incremented on each supervisor turn for loop safety.
        max_iterations: Safety threshold before recursion guard halts execution.
        status: Lifecycle state ('IDLE', 'RUNNING', 'COMPLETED', 'FAILED', 'TERMINATED_LOOP_LIMIT').
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_worker: Optional[str]
    task_intent: str
    execution_history: Annotated[List[Dict[str, Any]], operator.add]
    summary: str
    iteration_count: int
    max_iterations: int
    status: str
```

### Reducer Mechanics
1. **`messages: Annotated[Sequence[BaseMessage], add_messages]`**
   - Reducer: `langgraph.graph.message.add_messages`
   - Behavior: Automatically handles appending new messages (`HumanMessage`, `AIMessage`, `ToolMessage`), assigning unique UUIDs to messages without an ID, and pruning messages when receiving `RemoveMessage(id=...)`.
2. **`execution_history: Annotated[List[Dict[str, Any]], operator.add]`**
   - Reducer: `operator.add`
   - Behavior: Concatenates newly returned lists of history entries `[{"node": "...", "action": "...", "timestamp": "...", "status": "..."}]` onto the existing list, providing a complete non-destructive audit log.
3. **Overwrite Fields (`next_worker`, `task_intent`, `summary`, `iteration_count`, `max_iterations`, `status`)**
   - Behavior: Unannotated TypedDict fields follow LangGraph's default overwrite semantics, allowing individual nodes to update specific state properties without clobbering others.

### Context Pruning & Utility Helpers

#### A. Message History Pruning (`prune_message_history`)
To prevent LLM context window saturation during long-running multi-turn tool interactions, intermediate tool and chat messages must be pruned while retaining the initial user prompt and the recent context tail.

```python
def prune_message_history(
    messages: Sequence[BaseMessage],
    max_messages: int = 10,
    preserve_first_n: int = 1,
) -> List[RemoveMessage]:
    """
    Identifies intermediate messages to prune when total messages exceed max_messages.
    
    Preserves the first `preserve_first_n` messages (e.g., initial user prompt / system directive)
    and the most recent `(max_messages - preserve_first_n)` messages.
    
    Returns:
        List of RemoveMessage instances with IDs targeted for deletion by add_messages reducer.
    """
    if len(messages) <= max_messages:
        return []
    
    total = len(messages)
    keep_tail = max(0, max_messages - preserve_first_n)
    
    to_remove = (
        messages[preserve_first_n : total - keep_tail]
        if keep_tail > 0
        else messages[preserve_first_n:]
    )
    
    return [RemoveMessage(id=m.id) for m in to_remove if m.id]
```

#### B. Initial State Factory (`create_initial_state`)
```python
def create_initial_state(
    user_input: str,
    max_iterations: int = 10,
    task_intent: str = "",
    system_prompt: Optional[str] = None,
) -> AgentState:
    """
    Constructs a clean initial AgentState dictionary with standard defaults.
    """
    messages: List[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=user_input))
    
    return {
        "messages": messages,
        "next_worker": None,
        "task_intent": task_intent,
        "execution_history": [],
        "summary": "",
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "status": "IDLE",
    }
```

#### C. Audit History Factory (`create_history_entry`)
```python
import datetime

def create_history_entry(
    node: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    status: str = "SUCCESS",
) -> Dict[str, Any]:
    """
    Constructs a standardized ISO-timestamped audit history record.
    """
    return {
        "node": node,
        "action": action,
        "details": details or {},
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": status,
    }
```

---

## 3. PostgreSQL Checkpointer & Pool Architecture (`db.py`)

### Technical Rationale
The user requirement (§R3) explicitly mandates PostgreSQL checkpointing via `psycopg_pool` to ensure multi-session persistence, crash recovery, and thread safety across concurrent workers. For unit and integration testing where a physical PostgreSQL server may not be active, a seamless factory fallback to LangGraph's `MemorySaver` is provided.

### Checkpointer Factory Design
```python
import os
from typing import Optional, Union
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

def create_connection_pool(
    conn_string: str,
    min_size: int = 1,
    max_size: int = 10,
    timeout: float = 30.0,
    **kwargs
) -> ConnectionPool:
    """
    Initializes a thread-safe psycopg ConnectionPool with autocommit enabled.
    """
    connection_kwargs = kwargs.get("kwargs", {})
    if "autocommit" not in connection_kwargs:
        connection_kwargs["autocommit"] = True
    kwargs["kwargs"] = connection_kwargs

    return ConnectionPool(
        conninfo=conn_string,
        min_size=min_size,
        max_size=max_size,
        timeout=timeout,
        open=True,
        **kwargs
    )

def get_checkpointer(
    connection_string: Optional[str] = None,
    pool: Optional[ConnectionPool] = None,
    setup_tables: bool = False,
) -> Union[PostgresSaver, MemorySaver]:
    """
    Factory to obtain a LangGraph checkpointer.
    
    If connection_string or pool is provided, returns PostgresSaver.
    If none is provided (or in testing fallback), returns MemorySaver.
    """
    if pool is not None:
        saver = PostgresSaver(conn=pool)
        if setup_tables:
            saver.setup()
        return saver

    if connection_string is None:
        connection_string = os.getenv("POSTGRES_URI") or os.getenv("DATABASE_URL")

    if connection_string:
        conn_pool = create_connection_pool(connection_string)
        saver = PostgresSaver(conn=conn_pool)
        if setup_tables:
            saver.setup()
        return saver

    return MemorySaver()
```

---

## 4. Test Suite Strategy (`tests/test_state.py`)

### Test Matrix (Tiers 1–5 Compliance)

| Tier | Category | Test Cases | Objective |
|---|---|---|---|
| **Tier 1** | Schema & Feature Coverage | `test_agent_state_schema_types`<br>`test_create_initial_state_defaults`<br>`test_create_initial_state_with_system_prompt`<br>`test_create_history_entry_structure`<br>`test_add_messages_reducer_append` | Validate field types, factory defaults, and ISO UTC timestamp generation. |
| **Tier 2** | Boundary & Corner Cases | `test_prune_messages_under_limit`<br>`test_prune_messages_exact_limit`<br>`test_prune_messages_over_limit`<br>`test_prune_messages_zero_preserve`<br>`test_prune_messages_empty_list`<br>`test_prune_messages_without_ids` | Verify exact boundary slice logic and None-safe ID handling. |
| **Tier 3** | Reducer & LangGraph Graph Execution | `test_state_graph_reducer_integration`<br>`test_state_graph_message_pruning_in_node`<br>`test_execution_history_accumulation` | Execute mini StateGraphs to prove `operator.add` and `RemoveMessage` reducers behave identically to production. |
| **Tier 4** | Serialization & Concurrency | `test_state_json_serializability`<br>`test_status_enum_transitions` | Ensure state dictionaries serialize cleanly for PostgreSQL blob storage without circular references. |
| **Tier 5** | Adversarial Hardening | `test_malformed_history_entry_resilience`<br>`test_max_iterations_boundary_detection`<br>`test_negative_pruning_limits` | Verify extreme arguments (negative limits, empty payloads) do not cause unhandled exceptions. |

---

## 5. Verification & Downstream Integration

- **Downstream Consumers**:
  - `workers/base.py` & `workers/*.py` (M2): Will import `AgentState`, `create_history_entry`, and return `Command(update={...}, goto='supervisor')`.
  - `supervisor.py` (M3): Will import `AgentState`, `prune_message_history`, `create_initial_state`, and `get_checkpointer`.
  - `test_orchestrator.py` (M4): Will instantiate `AgentState` for all test scenarios.
