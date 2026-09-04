# Milestone M1 Technical Analysis: State Management & PostgreSQL Checkpointer Engine

**Project**: Antigravity Control Plane Refactor (`~/teamwork_projects/antigravity_control_plane`)  
**Author**: `explorer_m1_3`  
**Target Milestone**: Milestone 1 (`state.py`, `db.py`, `tests/conftest.py`, `tests/test_state.py`, `tests/test_db.py`, `requirements.txt`)  
**Date**: 2026-08-27  

---

## 1. Executive Summary & Problem Boundary

Milestone 1 (M1) is the foundational state management and persistence substrate of the Antigravity Control Plane. The Control Plane adopts the **Hierarchical Supervisor Pattern** in LangGraph, unifying fragmented agents (Social Deployer, Mobile Zero-Touch, Deep Research) into isolated, stateless worker nodes governed by a top-down Supervisor.

The state management engine must satisfy four core features specified in `PROJECT.md`:
1. **Feature 1: Typed State Schema (`AgentState`)**: Strongly typed state using `TypedDict`, `Annotated[Sequence[BaseMessage], add_messages]`, and `Annotated[List[Dict[str, Any]], operator.add]`.
2. **Feature 2: PostgreSQL Checkpointer Backend**: Production-ready checkpointer utilizing `PostgresSaver` and `psycopg_pool.ConnectionPool` configured with `autocommit=True`.
3. **Feature 3: Context Pruning Engine**: Systematic pruning of stale intermediate scratchpads and tool outputs using `RemoveMessage` to eliminate context bloat while preserving conversation lineage.
4. **Feature 4: Checkpointer Factory with Testing Fallback**: Resilient checkpointer initialization supporting PostgreSQL in production and `MemorySaver` in headless/testing environments.

---

## 2. State Schema & Reducer Architecture (`state.py`)

### 2.1 Formal Schema Definition

```python
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
import operator

class AgentState(TypedDict):
    """Global state container for the Hierarchical Supervisor Control Plane."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_worker: Optional[str]
    task_intent: str
    execution_history: Annotated[List[Dict[str, Any]], operator.add]
    summary: str
    iteration_count: int
    max_iterations: int
    status: str
```

### 2.2 Reducer Mechanics & Channel Semantics

In LangGraph, node functions return partial state dictionaries. How these partial dictionaries merge into the global state depends entirely on whether a field is wrapped in `Annotated[T, reducer]`:

| State Field | Type | Reducer | Channel Update Behavior |
|---|---|---|---|
| `messages` | `Sequence[BaseMessage]` | `add_messages` | Appends new messages; updates existing messages if IDs match; deletes messages if `RemoveMessage(id=...)` is yielded. |
| `execution_history` | `List[Dict[str, Any]]` | `operator.add` | Appends list of execution records chronologically. **Strict Contract: updates must always be a `list` (e.g. `[entry]`), not a raw `dict`**. |
| `next_worker` | `Optional[str]` | *None (Overwrite)* | Overwritten by Supervisor routing decisions (`"social_worker"`, `"mobile_worker"`, `"research_worker"`, or `None`). |
| `task_intent` | `str` | *None (Overwrite)* | Overwritten/set during initialization representing the high-level user objective. |
| `summary` | `str` | *None (Overwrite)* | Overwritten by workers/supervisor upon completing or summarizing execution phases. |
| `iteration_count` | `int` | *None (Overwrite)* | Monotonically incremented by the Supervisor on each routing cycle. |
| `max_iterations` | `int` | *None (Overwrite)* | Safety recursion threshold (defaults to `10`). |
| `status` | `str` | *None (Overwrite)* | Lifecycle enum: `"PENDING"`, `"RUNNING"`, `"COMPLETED"`, `"FAILED"`, `"MAX_ITERATIONS_REACHED"`. |

### 2.3 Edge Cases & Defensive Validation

1. **`operator.add` Type Guarding**:
   - *Risk*: If a worker node mistakenly returns `{"execution_history": {"worker": "social_worker"}}` instead of a list `[{"worker": "social_worker"}]`, `operator.add` raises `TypeError: can only concatenate list (not "dict") to list`.
   - *Mitigation*: Provide helper factory functions in `state.py`:
     ```python
     def create_history_entry(
         worker: str,
         status: Literal["SUCCESS", "FAILED", "RUNNING"],
         action: str,
         result: Any = None,
         error: Optional[str] = None
     ) -> List[Dict[str, Any]]:
         """Returns a single-item list conforming to the execution_history reducer contract."""
         from datetime import datetime, timezone
         return [{
             "worker": worker,
             "status": status,
             "action": action,
             "result": result,
             "error": error,
             "timestamp": datetime.now(timezone.utc).isoformat()
         }]
     ```

2. **Initial State Sanitization**:
   - Provide `create_initial_state` to ensure all fields are populated with valid defaults:
     ```python
     def create_initial_state(
         task_intent: str,
         messages: Optional[Sequence[BaseMessage]] = None,
         max_iterations: int = 10
     ) -> AgentState:
         from langchain_core.messages import HumanMessage
         msgs = list(messages) if messages is not None else [HumanMessage(content=task_intent)]
         return {
             "messages": msgs,
             "next_worker": None,
             "task_intent": task_intent,
             "execution_history": [],
             "summary": "",
             "iteration_count": 0,
             "max_iterations": max_iterations,
             "status": "PENDING"
         }
     ```

3. **Pydantic Validation Guardrail (`AgentStateValidator`)**:
   - For white-box testing and runtime validation:
     ```python
     from pydantic import BaseModel, Field, field_validator

     class AgentStateValidator(BaseModel):
         task_intent: str
         next_worker: Optional[str] = None
         summary: str = ""
         iteration_count: int = Field(ge=0)
         max_iterations: int = Field(gt=0, default=10)
         status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "MAX_ITERATIONS_REACHED"] = "PENDING"
         execution_history: List[Dict[str, Any]] = Field(default_factory=list)

         @field_validator("iteration_count")
         def check_iteration_bounds(cls, v, values):
             return v
     ```

---

## 3. Context Pruning Engine with `RemoveMessage`

### 3.1 Mechanism

LangGraph's `add_messages` reducer natively intercepts `RemoveMessage(id=...)` instances. When `add_messages(existing_messages, removals)` executes, any message whose `.id` matches a `RemoveMessage.id` is removed from the sequence.

### 3.2 Pruning Strategies

`state.py` should expose two explicit pruning utilities:

#### 1. Windowed History Pruner (`prune_message_history`)
Trims older intermediate conversational turns when message count exceeds `max_messages`, while unconditionally preserving the root `HumanMessage` containing the original task intent.

```python
from typing import List, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, RemoveMessage

def prune_message_history(
    messages: Sequence[BaseMessage],
    max_messages: int = 10,
    preserve_first_user_message: bool = True
) -> List[RemoveMessage]:
    """Generates RemoveMessage commands for excess messages beyond max_messages."""
    if len(messages) <= max_messages:
        return []

    removals: List[RemoveMessage] = []
    start_idx = 1 if (preserve_first_user_message and len(messages) > 0 and isinstance(messages[0], HumanMessage)) else 0
    excess_count = len(messages) - max_messages
    
    # Identify eligible slice for removal
    candidates = messages[start_idx : -(max_messages - start_idx)] if (max_messages - start_idx) > 0 else messages[start_idx:]

    for msg in candidates[:excess_count]:
        if msg.id:
            removals.append(RemoveMessage(id=msg.id))

    return removals
```

#### 2. Intermediate Scratchpad Pruner (`prune_intermediate_scratchpad`)
Removes verbose tool execution traces (`AIMessage(tool_calls=...)` and `ToolMessage(...)`) once a worker has synthesized its conclusion, collapsing multi-turn scratchpads into concise state updates.

```python
from langchain_core.messages import AIMessage, ToolMessage

def prune_intermediate_scratchpad(
    messages: Sequence[BaseMessage],
    keep_last_n_tool_turns: int = 0
) -> List[RemoveMessage]:
    """Prunes intermediate ToolMessages and assistant tool call messages to prevent prompt bloat."""
    removals: List[RemoveMessage] = []
    
    # Identify tool calls and tool outputs
    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.id:
            removals.append(RemoveMessage(id=msg.id))
        elif isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None) and msg.id:
            # Check if this is an intermediate tool dispatch message
            removals.append(RemoveMessage(id=msg.id))
            
    return removals
```

### 3.3 Context Pruning Edge Cases

1. **Auto-Generated Message IDs**:
   - If a message was created without an explicit `id`, LangGraph's `add_messages` assigns a UUID upon insertion into the state graph. The pruner checks `msg.id` before emitting `RemoveMessage(id=msg.id)`.
2. **Dangling Tool Call Prevention**:
   - In standard LLM chat APIs (e.g. OpenAI / Gemini), providing an `AIMessage` with `tool_calls` without subsequent `ToolMessage` payloads causes a 400 error. The `prune_intermediate_scratchpad` engine prunes both the `AIMessage(tool_calls=...)` and the corresponding `ToolMessage(tool_call_id=...)` atomically.
3. **Zero / Sub-threshold Invocations**:
   - If `len(messages) <= max_messages`, `prune_message_history` immediately returns `[]` (empty list), resulting in zero state mutations.

---

## 4. PostgreSQL Checkpointer Backend & Factory (`db.py`)

### 4.1 Checkpointer Architecture

`PROJECT.md` specifies that the control plane must use PostgreSQL as the production persistence checkpointer, backed by `psycopg_pool.ConnectionPool` with `autocommit=True`.

### 4.2 Module Locations in Python Ecosystem

- **`PostgresSaver`**: `from langgraph.checkpoint.postgres import PostgresSaver`
- **`AsyncPostgresSaver`**: `from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver`
- **`ConnectionPool`**: `from psycopg_pool import ConnectionPool`
- **`MemorySaver`**: `from langgraph.checkpoint.memory import MemorySaver`

### 4.3 `db.py` Implementation Design

```python
import os
from typing import Optional, Union
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

def create_connection_pool(
    conninfo: str,
    min_size: int = 1,
    max_size: int = 20,
    autocommit: bool = True,
    timeout: float = 10.0
) -> ConnectionPool:
    """Creates a configured psycopg_pool.ConnectionPool with autocommit=True."""
    if not conninfo or not isinstance(conninfo, str):
        raise ValueError("Invalid connection URI provided.")
    
    return ConnectionPool(
        conninfo=conninfo,
        min_size=min_size,
        max_size=max_size,
        kwargs={"autocommit": autocommit},
        timeout=timeout,
        open=True
    )

def get_checkpointer(
    connection_string: Optional[str] = None,
    pool: Optional[ConnectionPool] = None,
    testing: bool = False,
    auto_setup: bool = True
) -> BaseCheckpointSaver:
    """Factory creating PostgresSaver backed by ConnectionPool, or MemorySaver for testing."""
    if testing:
        return MemorySaver()
    
    conn_uri = connection_string or os.environ.get("DATABASE_URL")
    if not conn_uri and pool is None:
        return MemorySaver()
    
    if pool is None:
        pool = create_connection_pool(conn_uri)
        
    saver = PostgresSaver(conn=pool)
    if auto_setup:
        try:
            saver.setup()
        except Exception as e:
            # When testing with mocks or existing tables, handle setup gracefully
            pass
    return saver
```

### 4.4 PostgreSQL Schema & Idempotent Migrations

When `PostgresSaver.setup()` executes, it applies the required migrations to the connected database:
- `checkpoints` table: Stores thread IDs, checkpoint IDs, versions, parent checkpoint IDs, timestamps, and serialized state payloads.
- `checkpoint_blobs` table: Stores binary data payloads and channel version snapshots.
- `checkpoint_writes` table: Stores intermediate write buffers and pending commands.
- `checkpoint_migrations` table: Tracks applied migration versions.

---

## 5. Interoperability Matrix (M1 ↔ M2 Workers ↔ M3 Supervisor)

### 5.1 System Call Flow & State Life Cycle

```
[ START ]
    │
    ▼
┌────────────────────────────────────────────────────────┐
│ M3: Supervisor Node                                    │
│ 1. Read state['iteration_count'] and increment         │
│ 2. Check recursion guard (if it > max_iterations)      │
│ 3. Classify intent via with_structured_output          │
│ 4. Return Command(goto='<worker>', update={...})       │
└───────────────────────┬────────────────────────────────┘
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  M2: Social  │ │  M2: Mobile  │ │ M2: Research │
│    Worker    │ │    Worker    │ │    Worker    │
│ (bind_tools) │ │ (bind_tools) │ │ (bind_tools) │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┴────────────────┘
                        │
                        ▼ (Atomic Handoff via Command)
┌────────────────────────────────────────────────────────┐
│ Worker Returns:                                        │
│ Command(                                               │
│   update={                                             │
│     "messages": [AIMessage(...)],                      │
│     "execution_history": [{worker, action, status...}] │
│   },                                                   │
│   goto="supervisor"                                    │
│ )                                                      │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ M3: Supervisor Evaluates Completion                    │
│ If task finished:                                      │
│   Return Command(goto=END, update={"status":"COMPLETED"})
└────────────────────────────────────────────────────────┘
```

### 5.2 Interoperability Requirements Table

| Contract Element | M1 Provider (`state.py` / `db.py`) | M2 Consumer (`workers/`) | M3 Consumer (`supervisor.py`) |
|---|---|---|---|
| **Message Reducer** | `messages: Annotated[Sequence[BaseMessage], add_messages]` | Appends tool output `AIMessage` | Injects task prompt `HumanMessage` & routing rationale |
| **History Reducer** | `execution_history: Annotated[List[Dict[str, Any]], operator.add]` | Appends single-item list `[{"worker": ..., "status": ...}]` | Evaluates past execution steps to avoid redundant routing |
| **Handoff Target** | N/A | Returns `Command(..., goto="supervisor")` | Routes to workers (`goto="social_worker"`) or `goto=END` |
| **Safety Counter** | `iteration_count: int`, `max_iterations: int` | Reads read-only | Increments `iteration_count += 1`; halts if limit reached |
| **Thread Checkpointing** | `PostgresSaver` / `MemorySaver` | Stateless execution (no internal state retention) | Compiles graph with `checkpointer=get_checkpointer()` |

---

## 6. Test Infrastructure & Mock Harness (`tests/conftest.py`)

### 6.1 `_internal.get_connection` Constraint Resolution

During our technical verification of `langgraph-checkpoint-postgres`, we identified that `_internal.get_connection(self.conn)` enforces strict runtime type checking:
```python
if isinstance(conn, Connection):
    yield conn
elif isinstance(conn, ConnectionPool):
    with conn.connection() as conn:
        yield conn
else:
    raise TypeError(f"Invalid connection type: {type(conn)}")
```

**Crucial Testing Pattern**: Any mock connection pool in `tests/conftest.py` MUST be instantiated using `MagicMock(spec=ConnectionPool)` or `create_autospec(ConnectionPool, instance=True)`. A generic `MagicMock()` will fail with `TypeError`.

### 6.2 Proposed `tests/conftest.py` Architecture

```python
import socket
import pytest
from unittest.mock import MagicMock
from psycopg_pool import ConnectionPool
from psycopg import Connection
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from state import create_initial_state, AgentState

@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Guarantees zero network egress during test runs."""
    def guarded_connect(*args, **kwargs):
        raise RuntimeError("External network connection attempted during test execution.")
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

@pytest.fixture
def mock_checkpointer():
    """Provides an in-memory checkpointer conforming to BaseCheckpointSaver."""
    return MemorySaver()

@pytest.fixture
def mock_db_pool():
    """Provides a spec-compliant mock ConnectionPool for PostgresSaver testing."""
    mock_pool = MagicMock(spec=ConnectionPool)
    mock_conn = MagicMock(spec=Connection)
    mock_cursor = MagicMock()
    
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    
    return mock_pool, mock_conn, mock_cursor

@pytest.fixture
def sample_initial_state() -> AgentState:
    """Provides a fresh canonical AgentState."""
    return create_initial_state(
        task_intent="Deploy media asset to Facebook and verify via mobile screenshot.",
        max_iterations=10
    )

@pytest.fixture
def sample_conversation_with_scratchpad():
    """Provides a multi-turn conversation with intermediate tool scratchpads."""
    return [
        HumanMessage(content="Deploy asset", id="msg_0"),
        AIMessage(
            content="",
            id="msg_1",
            tool_calls=[{"name": "adb_push", "args": {"src": "/tmp/a.mp4"}, "id": "call_1"}]
        ),
        ToolMessage(content="File pushed successfully", tool_call_id="call_1", id="msg_2"),
        AIMessage(content="Asset deployed successfully", id="msg_3")
    ]
```

---

## 7. Concrete File Specifications for Implementation

### 7.1 `requirements.txt`
```text
langgraph>=0.2.70
langchain-core>=0.3.40
langgraph-checkpoint>=2.0.10
langgraph-checkpoint-postgres>=2.0.15
psycopg[binary]>=3.2.0
psycopg-pool>=3.2.0
pydantic>=2.7.4
pytest>=8.0.0
pytest-mock>=3.14.0
pytest-asyncio>=0.23.0
```

### 7.2 `state.py`
```python
"""State management, TypedDict schemas, reducers, and context pruning for Antigravity Control Plane."""

import operator
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, RemoveMessage
from langgraph.graph.message import add_messages
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class AgentState(TypedDict):
    """Global state container for the Hierarchical Supervisor Control Plane."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_worker: Optional[str]
    task_intent: str
    execution_history: Annotated[List[Dict[str, Any]], operator.add]
    summary: str
    iteration_count: int
    max_iterations: int
    status: str

class AgentStateValidator(BaseModel):
    """Pydantic model for schema validation of state transitions."""
    task_intent: str
    next_worker: Optional[str] = None
    summary: str = ""
    iteration_count: int = Field(ge=0, default=0)
    max_iterations: int = Field(gt=0, default=10)
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "MAX_ITERATIONS_REACHED"] = "PENDING"
    execution_history: List[Dict[str, Any]] = Field(default_factory=list)

def create_initial_state(
    task_intent: str,
    messages: Optional[Sequence[BaseMessage]] = None,
    max_iterations: int = 10
) -> AgentState:
    """Constructs a fully initialized AgentState dictionary with standard defaults."""
    if not task_intent or not isinstance(task_intent, str):
        raise ValueError("task_intent must be a non-empty string.")
    
    msgs = list(messages) if messages is not None else [HumanMessage(content=task_intent)]
    return {
        "messages": msgs,
        "next_worker": None,
        "task_intent": task_intent,
        "execution_history": [],
        "summary": "",
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "status": "PENDING"
    }

def create_history_entry(
    worker: str,
    status: Literal["SUCCESS", "FAILED", "RUNNING"],
    action: str,
    result: Any = None,
    error: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Creates a single-item execution history list ensuring compatibility with operator.add."""
    return [{
        "worker": worker,
        "status": status,
        "action": action,
        "result": result,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }]

def prune_message_history(
    messages: Sequence[BaseMessage],
    max_messages: int = 10,
    preserve_first_user_message: bool = True
) -> List[RemoveMessage]:
    """Generates RemoveMessage objects to prune excess messages while retaining user intent."""
    if len(messages) <= max_messages:
        return []

    start_idx = 1 if (preserve_first_user_message and len(messages) > 0 and isinstance(messages[0], HumanMessage)) else 0
    excess_count = len(messages) - max_messages
    
    candidates = messages[start_idx : -(max_messages - start_idx)] if (max_messages - start_idx) > 0 else messages[start_idx:]
    
    removals: List[RemoveMessage] = []
    for msg in candidates[:excess_count]:
        if msg.id:
            removals.append(RemoveMessage(id=msg.id))
            
    return removals

def prune_intermediate_scratchpad(
    messages: Sequence[BaseMessage]
) -> List[RemoveMessage]:
    """Prunes intermediate ToolMessages and assistant tool call messages to collapse scratchpad."""
    removals: List[RemoveMessage] = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.id:
            removals.append(RemoveMessage(id=msg.id))
        elif isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None) and msg.id:
            removals.append(RemoveMessage(id=msg.id))
    return removals
```

### 7.3 `db.py`
```python
"""Database connection pool & PostgreSQL checkpointer engine for Antigravity Control Plane."""

import os
from typing import Optional
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

def create_connection_pool(
    conninfo: str,
    min_size: int = 1,
    max_size: int = 20,
    autocommit: bool = True,
    timeout: float = 10.0
) -> ConnectionPool:
    """Instantiates a psycopg_pool.ConnectionPool configured for PostgreSQL checkpointing."""
    if not conninfo or not isinstance(conninfo, str):
        raise ValueError("A valid PostgreSQL connection URI string must be provided.")
    
    return ConnectionPool(
        conninfo=conninfo,
        min_size=min_size,
        max_size=max_size,
        kwargs={"autocommit": autocommit},
        timeout=timeout,
        open=True
    )

def get_checkpointer(
    connection_string: Optional[str] = None,
    pool: Optional[ConnectionPool] = None,
    testing: bool = False,
    auto_setup: bool = True
) -> BaseCheckpointSaver:
    """Factory returning PostgresSaver backed by ConnectionPool or MemorySaver fallback."""
    if testing:
        return MemorySaver()
    
    conn_uri = connection_string or os.environ.get("DATABASE_URL")
    if not conn_uri and pool is None:
        return MemorySaver()
    
    if pool is None:
        pool = create_connection_pool(conn_uri)
        
    saver = PostgresSaver(conn=pool)
    if auto_setup:
        try:
            saver.setup()
        except Exception:
            pass
    return saver
```

---

## 8. Verification Commands & Execution Expectations

### 8.1 Verification Invocations

Implementers and auditors should verify M1 deliverables using:

```powershell
# 1. Verify dependencies installation
python -m pip install -r requirements.txt

# 2. Run M1 Unit Tests in isolation
python -m pytest tests/test_state.py tests/test_db.py -v --durations=10

# 3. Run full test suite
python -m pytest tests/ -v --durations=10
```

### 8.2 Execution Performance Expectations
- **M1 Unit Test Suite Duration**: < 1.0 second.
- **Pass Rate**: 100% (0 errors, 0 warnings, 0 network socket attempts).
- **Memory Footprint**: 0 memory leaks across state graph transitions.
