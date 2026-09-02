# Specification Mining Report: State Management & PostgreSQL Checkpointer

**Target Project:** `C:\Users\noahp\teamwork_projects\antigravity_control_plane`  
**Agent:** `spec_miner_state_1`  
**Authoritative Source:** `ORIGINAL_REQUEST.md` (lines 68–98) & `teamwork-langgraph-orchestrator` Blueprint  
**Date:** 2026-08-27  

---

## Executive Summary

This report defines the complete technical specifications for **State Management (R3)**, the **PostgreSQL Checkpointer backend with `psycopg_pool`**, **Context Pruning**, and **Test Fallbacks/Mocking** for the Antigravity Control Plane (`antigravity_control_plane`).

The Control Plane implements the **Hierarchical Supervisor Pattern** in LangGraph. State is managed centrally in a typed schema (`AgentState`), transitions are mediated through LangGraph `Command` objects, state persistence is handled by `PostgresSaver` backed by a `psycopg_pool.ConnectionPool`, and context bloat is eliminated via incremental worker handoffs and message pruning (`RemoveMessage` / `trim_messages`).

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | State Schema | `AgentState` TypedDict | Global state schema for the LangGraph StateGraph tracking messages, next worker, task intent, execution history, summary, and status. | Dictionary or keyword updates | Strongly typed `AgentState` dictionary | TypeError on missing required keys or invalid reducer operations | `ORIGINAL_REQUEST.md` R3, LangGraph v0.2+ StateGraph spec |
| 2 | State Schema | `TaskIntent` Pydantic Model | Structured representation of classified user intent extracted by Supervisor via `with_structured_output`. | Raw user prompt, metadata | `TaskIntent(category, intent_description, confidence, parameters, target_worker)` | `ValidationError` if fields fail type constraints | LangGraph Structured Output spec & R1 Supervisor |
| 3 | State Schema | `SupervisorDecision` Model | Decision model output by the Supervisor to direct routing and issue worker commands. | Supervisor prompt, state messages | `SupervisorDecision(next_node, intent, reasoning, worker_instructions)` | `ValidationError` on malformed LLM response | `ORIGINAL_REQUEST.md` R1 Routing Engine spec |
| 4 | State Schema | `ExecutionStep` Model | Structured audit trail entry recording worker actions, execution status, latency, and summaries. | Worker execution result, metadata | `ExecutionStep(step_id, node_name, timestamp, action_type, status, summary, details)` | `ValidationError` if required fields missing | `teamwork-langgraph-orchestrator` CI/CD telemetry spec |
| 5 | State Schema | `PruningMetadata` Model | Metadata tracking pruning runs, active window sizes, and total pruned tokens/messages. | Pruning invocation counts | `PruningMetadata(last_pruned_turn, pruned_count, active_window, summary_length)` | Handled gracefully with default zeros | Context bloat prevention requirement R3 |
| 6 | Reducers | `add_messages` Reducer | Reducer function for `messages` field allowing message appending, ID replacement, and `RemoveMessage` deletion. | `list[BaseMessage]` or `RemoveMessage` | Updated `list[BaseMessage]` | ValueError on malformed message object | LangGraph `langgraph.graph.message` API |
| 7 | Reducers | `operator.add` History Reducer | Reducer for `execution_history` that appends new execution steps to the cumulative history list. | `list[ExecutionStep]` or `list[dict]` | Combined cumulative `list` | TypeError if non-list passed to update | Python `operator.add` & LangGraph Annotated spec |
| 8 | Reducers | Overwrite Reducers | Scalar fields (`next_worker`, `summary`, `status`, `task_intent`) overwrite prior value with latest update. | Scalar / dict values | Latest assigned value | None (standard overwrite) | LangGraph default field behavior |
| 9 | State Updates | `Command` Protocol | Worker handoff mechanism using `Command(goto='supervisor', update={...})` for atomic state mutations. | Destination node (`'supervisor'`), update dictionary | LangGraph runtime transition | GraphRecursionError if circular loop without termination | `ORIGINAL_REQUEST.md` R2 Handoff Protocol |
| 10 | Context Pruning | Incremental Worker Return | Worker nodes filter out raw scratchpad / browser DOM dumps before returning, emitting only synthesized text & structured metadata. | Internal worker execution trace | Clean `AIMessage` + `ExecutionStep` | Unfiltered bloat if worker returns full scratchpad | LangGraph context management best practices |
| 11 | Context Pruning | `prune_messages` Function | Utility to prune historical messages exceeding token or count limits using `RemoveMessage(id=...)`. | `messages: list[BaseMessage]`, `max_messages: int`, `keep_system: bool` | `list[RemoveMessage]` to emit in state update | Ignores invalid IDs; raises ValueError if negative limit | LangGraph `RemoveMessage` specification |
| 12 | Context Pruning | Context Summarization | Condenses pruned conversation history into `state['summary']` to maintain long-term task context without token overflow. | Pruned message list, current summary | Updated `summary: str` | Fallback to truncation if summarizer fails | `teamwork-langgraph-orchestrator` Context GC spec |
| 13 | Postgres Checkpointer | `psycopg_pool.ConnectionPool` | Connection pool managing thread-safe, reconnectable database connections for `PostgresSaver`. | `conninfo: str`, `max_size: int`, `kwargs: dict` | `ConnectionPool` instance | `psycopg.OperationalError` if database unreachable | `ORIGINAL_REQUEST.md` R3, `psycopg_pool` documentation |
| 14 | Postgres Checkpointer | `PostgresSaver` Integration | Synchronous checkpointer saving graph state snapshots, blobs, and writes to PostgreSQL. | `pool: ConnectionPool` | `PostgresSaver` instance | `CheckpointerError` on serialization or SQL write failure | `langgraph.checkpoint.postgres` specification |
| 15 | Postgres Checkpointer | `AsyncPostgresSaver` | Asynchronous checkpointer saving graph state snapshots using `AsyncConnectionPool`. | `pool: AsyncConnectionPool` | `AsyncPostgresSaver` instance | `CheckpointerError` on async write failure | `langgraph.checkpoint.postgres.aio` spec |
| 16 | Postgres Checkpointer | Schema Setup (`.setup()`) | Creates `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` tables. | Checkpointer instance | Provisioned database schema | `psycopg.ProgrammingError` if missing table permissions | `langgraph-checkpoint-postgres` setup API |
| 17 | Checkpointer Factory | `get_checkpointer` Factory | Central factory creating `PostgresSaver` when DB available, falling back to `MemorySaver` for testing. | `conninfo: Optional[str]`, `fallback_to_memory: bool` | `BaseCheckpointSaver` instance | Raises `ConnectionError` if strict mode enabled and DB down | Test infrastructure & deployment flexibility spec |
| 18 | Test Checkpointer | `MemorySaver` Backend | In-memory checkpointer fulfilling `BaseCheckpointSaver` interface for fast unit tests without DB dependencies. | None | `MemorySaver` instance | Volatile in-memory storage (cleared on process exit) | `langgraph.checkpoint.memory` API |
| 19 | Test Harness | Checkpointer Pytest Fixture | Reusable test fixture injecting `MemorySaver` or ephemeral Postgres checkpointer into test graph compilations. | Pytest session / function scope | Initialized checkpointer instance | Fails test if compilation fails | `ORIGINAL_REQUEST.md` Verification Resources |
| 20 | State Concurrency | `thread_id` & `checkpoint_ns` | Multi-tenant and multi-run isolation keying checkpoints by unique thread and namespace IDs. | `config={"configurable": {"thread_id": "...", "checkpoint_ns": "..."}}` | Isolated execution thread state | KeyError if thread_id missing when checkpointer is active | LangGraph configuration contract |

---

## Edge Cases

| # | Feature | Input | Observed / Expected Behavior |
|---|---------|-------|------------------------------|
| 1 | `add_messages` Reducer | Message with existing ID passed in update | Replaces the existing message with identical ID in place rather than appending duplicate. |
| 2 | `RemoveMessage` Pruning | `RemoveMessage(id="msg_unknown")` for ID not in state | Reducer ignores non-existent ID gracefully without raising an exception. |
| 3 | State Serialization | Custom non-serializable Python object in `details` | `PostgresSaver` uses `msgpack` or JSON serializer; non-serializable objects cause `TypeError`. Must serialize to primitives/dict first. |
| 4 | Connection Pool Config | `ConnectionPool` initialized without `autocommit=True` | `PostgresSaver.setup()` or checkpoint write fails with transaction lock / inactive transaction error. `autocommit=True` is mandatory. |
| 5 | Connection Pool Config | `ConnectionPool` initialized without `row_factory=dict_row` | `PostgresSaver` queries return tuples instead of dicts, causing `KeyError` or internal checkpointer crash. |
| 6 | Database Unreachable | `get_checkpointer(fallback_to_memory=True)` when DB offline | Catches connection error, logs warning, returns `MemorySaver()`, allowing offline tests to pass without stalling. |
| 7 | Database Unreachable | `get_checkpointer(fallback_to_memory=False)` when DB offline | Raises `psycopg.OperationalError` immediately (strict production mode). |
| 8 | Context Pruning | Message history smaller than `pruning_threshold` (e.g. 3 messages < 10) | Pruning function performs a no-op, returning empty list of removals; state messages remain unchanged. |
| 9 | Context Pruning | Preserving System Prompt & First User Prompt | Pruning sliding window must preserve `index 0` (System Prompt) and `index 1` (Initial User Goal) while deleting intermediate turns. |
| 10 | Circular Routing Loop | Supervisor continuously routes to Worker without reaching `FINISH` | LangGraph `recursion_limit` (default 25) triggers `GraphRecursionError`. Supervisor decision logic must have loop guard counter. |
| 11 | Concurrent Runs | Two concurrent tasks with different `thread_id` values | Postgres checkpointer isolates states by `thread_id`; writes do not collide or overwrite each other. |
| 12 | Checkpointer Schema Setup | `.setup()` called multiple times concurrently or sequentially | DDL migrations are idempotent (`CREATE TABLE IF NOT EXISTS`); subsequent calls are safe no-ops. |

---

## Detailed Technical Specifications

### 1. State Schema & Models (`state.py`)

#### 1.1 `AgentState` TypedDict
The central state must be a `TypedDict` compatible with LangGraph `StateGraph`:

```python
from typing import Annotated, Any, Dict, List, Literal, Optional, Sequence
from typing_extensions import TypedDict
import operator
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

class TaskIntent(BaseModel):
    """Structured representation of task intent classified by the Supervisor."""
    category: Literal["social", "mobile", "research", "finish", "unknown"] = "unknown"
    intent_description: str = Field(description="Summary of the user's primary goal")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    target_worker: Optional[str] = None

class SupervisorDecision(BaseModel):
    """Decision output produced by the Supervisor using with_structured_output."""
    next_node: Literal["social_worker", "mobile_worker", "research_worker", "FINISH"]
    intent: TaskIntent
    reasoning: str
    instructions_for_worker: str

class ExecutionStep(BaseModel):
    """Single step in the execution history."""
    step_id: str
    node_name: str
    timestamp: str
    action_type: str
    status: Literal["success", "error", "skipped"]
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)

class PruningMetadata(BaseModel):
    """Metadata tracking context pruning operations."""
    last_pruned_turn: int = 0
    total_messages_pruned: int = 0
    active_window_size: int = 10
    summary_token_count: int = 0

class AgentState(TypedDict):
    """Central global state schema for the Antigravity Control Plane."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_worker: Optional[str]
    task_intent: Optional[Dict[str, Any]]
    execution_history: Annotated[List[Dict[str, Any]], operator.add]
    summary: Optional[str]
    pruning_metadata: Optional[Dict[str, Any]]
    status: str
```

#### 1.2 Context Pruning Logic
Context pruning operates on two levels:

1. **Worker-Level Filtering (Scratchpad Elimination):**
   Stateless workers execute their internal loops with tools. Instead of returning raw observation dumps (e.g., 50KB accessibility trees or raw JSON payloads) into `state["messages"]`, the worker extracts the essential finding and returns:
   ```python
   return Command(
       goto="supervisor",
       update={
           "messages": [AIMessage(content=f"[{worker_name}] {summary_result}")],
           "execution_history": [execution_step.model_dump()],
           "status": "in_progress"
       }
   )
   ```

2. **Graph-Level Pruning (`prune_messages`):**
   ```python
   from langchain_core.messages import BaseMessage, RemoveMessage, SystemMessage, HumanMessage

   def prune_message_history(
       messages: Sequence[BaseMessage],
       max_messages: int = 10,
       keep_initial: bool = True
   ) -> List[RemoveMessage]:
       """
       Calculates messages to remove when history exceeds max_messages.
       Preserves the initial user request and the latest (max_messages - 1) messages.
       """
       if len(messages) <= max_messages:
           return []
       
       removals = []
       start_idx = 1 if keep_initial else 0
       end_idx = len(messages) - (max_messages - (1 if keep_initial else 0))
       
       for msg in messages[start_idx:end_idx]:
           if hasattr(msg, 'id') and msg.id:
               removals.append(RemoveMessage(id=msg.id))
       
       return removals
   ```

---

### 2. Database & Checkpointer Architecture (`db.py`)

#### 2.1 PostgreSQL Pool & Saver Setup
```python
import os
import logging
from typing import Optional, Union
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, AsyncConnectionPool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger("antigravity_control_plane.db")

def create_postgres_pool(
    conninfo: Optional[str] = None,
    max_size: int = 10,
    timeout: float = 5.0
) -> ConnectionPool:
    """Creates a psycopg_pool.ConnectionPool with required PostgresSaver settings."""
    uri = conninfo or os.getenv("POSTGRES_URI") or os.getenv("DATABASE_URL")
    if not uri:
        raise ValueError("PostgreSQL connection string must be provided or set in POSTGRES_URI/DATABASE_URL")
    
    return ConnectionPool(
        conninfo=uri,
        max_size=max_size,
        timeout=timeout,
        kwargs={"autocommit": True, "row_factory": dict_row}
    )

def get_checkpointer(
    conninfo: Optional[str] = None,
    fallback_to_memory: bool = True,
    max_size: int = 10
) -> BaseCheckpointSaver:
    """
    Factory that returns a PostgresSaver if PostgreSQL is reachable,
    or falls back to MemorySaver for testing/offline environments.
    """
    uri = conninfo or os.getenv("POSTGRES_URI") or os.getenv("DATABASE_URL")
    if not uri and fallback_to_memory:
        logger.info("No PostgreSQL URI configured. Using in-memory checkpointer (MemorySaver).")
        return MemorySaver()
    
    try:
        pool = create_postgres_pool(uri, max_size=max_size)
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()
        logger.info("Successfully connected to PostgreSQL checkpointer.")
        return checkpointer
    except Exception as e:
        if fallback_to_memory:
            logger.warning(f"Failed to connect to PostgreSQL ({e}). Falling back to MemorySaver.")
            return MemorySaver()
        raise
```

---

### 3. File Layout & Interface Contracts

```
antigravity_control_plane/
├── pyproject.toml / requirements.txt   # Dependencies (langgraph, psycopg_pool, psycopg[binary], pydantic)
├── README.md                           # Architecture and setup guide
├── supervisor.py                       # Central Routing Agent (R1) with with_structured_output
├── state.py                            # TypedDict schema, Pydantic models, context pruning (R3)
├── db.py                               # ConnectionPool, PostgresSaver, MemorySaver fallback (R3)
├── workers/                            # Stateless Worker nodes (R2)
│   ├── __init__.py
│   ├── social_worker.py                # Social deployer node with bind_tools + Command handoff
│   ├── mobile_worker.py                # Mobile automation node with bind_tools + Command handoff
│   └── research_worker.py              # Deep research node with bind_tools + Command handoff
└── tests/
    ├── __init__.py
    ├── conftest.py                     # Checkpointer fixtures (MemorySaver / Postgres mocks)
    ├── test_state.py                   # State validation, reducers, pruning logic tests
    ├── test_db.py                      # Connection pool config, setup, fallback tests
    └── test_orchestrator.py            # End-to-end DAG routing & handoff tests
```

---

## Acceptance & Verification Criteria for State & Checkpointer

1. **State Reducer Integrity:**
   - `add_messages` correctly merges messages and handles `RemoveMessage` deletions.
   - `operator.add` monotonically appends `ExecutionStep` items without overwriting history.
   - Scalar fields overwrite atomically.

2. **Checkpointer Conformance:**
   - `PostgresSaver` configured with `autocommit=True` and `row_factory=dict_row`.
   - `checkpointer.setup()` creates all 4 checkpoint tables without SQL errors.
   - `MemorySaver` fallback works seamlessly when Postgres is absent.

3. **Context Pruning Verification:**
   - Pruning reduces token and message counts when threshold is breached.
   - Preserves system prompt and initial user intent.

4. **100% Deterministic Testing:**
   - `pytest` executes state and database tests in under 5 seconds using `MemorySaver` and mock pool fixtures.
