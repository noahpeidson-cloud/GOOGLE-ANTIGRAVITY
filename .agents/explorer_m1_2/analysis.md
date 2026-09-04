# Milestone M1 Analysis: State Management & PostgreSQL Checkpointer Engine

**Author**: `explorer_m1_2`  
**Working Directory**: `C:\Users\noahp\OneDrive\Desktop\Antigravity\.agents\explorer_m1_2`  
**Target Project**: `C:\Users\noahp\teamwork_projects\antigravity_control_plane`  
**Timestamp**: 2026-08-27T21:23:30Z  

---

## 1. Executive Summary

Milestone M1 establishes the state management and persistence foundation for the Antigravity Control Plane. The central requirement (per `ORIGINAL_REQUEST.md` §R3 and `PROJECT.md` Feature 2 & 4) is a production-grade, concurrency-safe checkpointer backend using PostgreSQL via `psycopg_pool` and LangGraph's `PostgresSaver` / `AsyncPostgresSaver`, alongside an automatic in-memory fallback (`MemorySaver`) for zero-flakiness deterministic unit and integration testing.

This analysis provides the complete architectural blueprint and implementation specification for:
1. **`db.py`**: Checkpointer factories (`get_checkpointer()`, `get_async_checkpointer()`) and connection pool managers (`create_connection_pool()`, `create_async_connection_pool()`).
2. **Integration Contracts**: Exact wiring of `psycopg_pool.ConnectionPool` / `psycopg_pool.AsyncConnectionPool` with `kwargs={"autocommit": True, "row_factory": dict_row}` to `PostgresSaver` / `AsyncPostgresSaver`.
3. **`tests/test_db.py`**: A 5-tier deterministic unit test suite verifying factory behavior, environment fallbacks, connection pool configurations, schema migrations (`setup()`), and StateGraph checkpoint persistence.

---

## 2. Technical Findings & Architectural Nuances

### 2.1 Package & API Specifications
- **LangGraph Checkpoint Postgres**: `langgraph-checkpoint-postgres` (v3.1.2) provides:
  - `langgraph.checkpoint.postgres.PostgresSaver` (synchronous)
  - `langgraph.checkpoint.postgres.aio.AsyncPostgresSaver` (asynchronous)
- **Psycopg 3 & Pool**: `psycopg` (v3.3.4) and `psycopg-pool` (v3.3.1) provide:
  - `psycopg_pool.ConnectionPool` (synchronous connection pool)
  - `psycopg_pool.AsyncConnectionPool` (asynchronous connection pool)
  - `psycopg.rows.dict_row` (dictionary row factory)
- **Memory Checkpointer**: `langgraph.checkpoint.memory.MemorySaver` provides:
  - High-performance in-memory state checkpointing supporting both synchronous (`invoke`, `get_state`) and asynchronous (`ainvoke`, `aget_state`) LangGraph executions.

### 2.2 Key Operational Discoveries

1. **Mandatory Pool Kwargs**:
   - `PostgresSaver` and `AsyncPostgresSaver` require transactions to be committed automatically per statement or managed without explicit external commit locks, and return dictionary records for column lookups (`row["v"]` in migration checks).
   - Therefore, the connection pool MUST be initialized with:
     ```python
     kwargs = {"autocommit": True, "row_factory": dict_row}
     ```
   - Failing to provide `row_factory=dict_row` causes migrations (`setup()`) and checkpoint lookups to fail with `TypeError: tuple indices must be integers`.
   - Failing to provide `autocommit=True` can cause connection stalls or transaction deadlocks when multiple graph nodes access checkpointer tables concurrently.

2. **AsyncPostgresSaver Event Loop Requirement**:
   - In `langgraph.checkpoint.postgres.aio.AsyncPostgresSaver.__init__`, the constructor executes:
     ```python
     self.loop = asyncio.get_running_loop()
     ```
   - Attempting to instantiate `AsyncPostgresSaver` in synchronous top-level code outside of a running asyncio loop raises `RuntimeError: no running event loop`.
   - **Resolution**: `get_async_checkpointer` should be defined as an asynchronous factory (`async def get_async_checkpointer(...)`) or provide an async setup path. When used in async applications (FastAPI, asyncio workers, or async tests), it guarantees an active running loop.

3. **Pipeline Mode vs Connection Pool**:
   - `PostgresSaver.__init__` explicitly forbids passing both a `ConnectionPool` and a `Pipeline` object (`if isinstance(conn, ConnectionPool) and pipe is not None: raise ValueError(...)`).
   - The connection pool manager handles pooling and concurrency, while pipeline mode is reserved for single dedicated connections.

4. **Zero-Flakiness Testing Strategy**:
   - Real PostgreSQL servers should never be required for running unit tests (`pytest`).
   - Testing tests two distinct scenarios:
     a. **Factory Fallback & In-Memory Mode**: When connection string is `None`, `""`, `"memory"`, or `":memory:"`, the factories return `MemorySaver()`.
     b. **PostgreSQL Mocking**: Using `unittest.mock.MagicMock(spec=ConnectionPool)` and `AsyncMock(spec=AsyncConnectionPool)` to test pool creation, kwargs assignment, `PostgresSaver.setup()` migrations, and cursor operations without network egress.

---

## 3. Proposed Implementation Blueprint: `db.py`

Below is the complete, production-grade proposed source code for `C:\Users\noahp\teamwork_projects\antigravity_control_plane\db.py`.

```python
"""Database connection pooling and LangGraph checkpointer factories.

Provides synchronous and asynchronous checkpointer engines backed by PostgreSQL
via psycopg_pool.ConnectionPool / AsyncConnectionPool, with automated fallback to
in-memory storage (MemorySaver) for lightweight local execution and testing.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional, Union

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)

# Default Pool Configuration
DEFAULT_MIN_POOL_SIZE: int = 1
DEFAULT_MAX_POOL_SIZE: int = 20
DEFAULT_POOL_TIMEOUT: float = 30.0
DEFAULT_MAX_IDLE: float = 600.0
DEFAULT_KWARGS: Dict[str, Any] = {"autocommit": True, "row_factory": dict_row}

IN_MEMORY_SENTINELS = {"", "memory", ":memory:", "none", "local"}


def create_connection_pool(
    conninfo: str,
    *,
    min_size: int = DEFAULT_MIN_POOL_SIZE,
    max_size: Optional[int] = DEFAULT_MAX_POOL_SIZE,
    open: bool = True,
    timeout: float = DEFAULT_POOL_TIMEOUT,
    max_idle: float = DEFAULT_MAX_IDLE,
    kwargs: Optional[Dict[str, Any]] = None,
    **pool_options: Any,
) -> ConnectionPool:
    """Create and configure a psycopg_pool.ConnectionPool with autocommit and dict_row.

    Args:
        conninfo: PostgreSQL connection URI (e.g. postgresql://user:pass@host:5432/db).
        min_size: Minimum number of connections in the pool.
        max_size: Maximum number of connections in the pool.
        open: Whether to immediately open the pool connections.
        timeout: Maximum seconds to wait for a connection from the pool.
        max_idle: Maximum seconds a connection can remain idle before being recycled.
        kwargs: Additional connection parameters (merged with autocommit & dict_row).
        **pool_options: Extra arguments passed to ConnectionPool.

    Returns:
        Configured ConnectionPool instance.
    """
    final_kwargs = dict(DEFAULT_KWARGS)
    if kwargs:
        final_kwargs.update(kwargs)

    logger.debug(
        "Initializing ConnectionPool (min_size=%s, max_size=%s, open=%s)",
        min_size,
        max_size,
        open,
    )
    return ConnectionPool(
        conninfo=conninfo,
        min_size=min_size,
        max_size=max_size,
        open=open,
        timeout=timeout,
        max_idle=max_idle,
        kwargs=final_kwargs,
        **pool_options,
    )


def create_async_connection_pool(
    conninfo: str,
    *,
    min_size: int = DEFAULT_MIN_POOL_SIZE,
    max_size: Optional[int] = DEFAULT_MAX_POOL_SIZE,
    open: bool = True,
    timeout: float = DEFAULT_POOL_TIMEOUT,
    max_idle: float = DEFAULT_MAX_IDLE,
    kwargs: Optional[Dict[str, Any]] = None,
    **pool_options: Any,
) -> AsyncConnectionPool:
    """Create and configure a psycopg_pool.AsyncConnectionPool with autocommit and dict_row.

    Args:
        conninfo: PostgreSQL connection URI.
        min_size: Minimum number of connections in the pool.
        max_size: Maximum number of connections in the pool.
        open: Whether to immediately open the pool connections.
        timeout: Maximum seconds to wait for a connection from the pool.
        max_idle: Maximum seconds a connection can remain idle before being recycled.
        kwargs: Additional connection parameters (merged with autocommit & dict_row).
        **pool_options: Extra arguments passed to AsyncConnectionPool.

    Returns:
        Configured AsyncConnectionPool instance.
    """
    final_kwargs = dict(DEFAULT_KWARGS)
    if kwargs:
        final_kwargs.update(kwargs)

    logger.debug(
        "Initializing AsyncConnectionPool (min_size=%s, max_size=%s, open=%s)",
        min_size,
        max_size,
        open,
    )
    return AsyncConnectionPool(
        conninfo=conninfo,
        min_size=min_size,
        max_size=max_size,
        open=open,
        timeout=timeout,
        max_idle=max_idle,
        kwargs=final_kwargs,
        **pool_options,
    )


def get_checkpointer(
    connection_string: Optional[str] = None,
    *,
    pool: Optional[ConnectionPool] = None,
    auto_setup: bool = False,
    min_size: int = DEFAULT_MIN_POOL_SIZE,
    max_size: Optional[int] = DEFAULT_MAX_POOL_SIZE,
    open: bool = True,
    **pool_kwargs: Any,
) -> BaseCheckpointSaver:
    """Factory creating a synchronous LangGraph checkpointer.

    If an existing pool is provided, it is wrapped in a PostgresSaver.
    If a connection_string is provided (or resolved from DATABASE_URL / POSTGRES_URI),
    a new ConnectionPool is created and wrapped in a PostgresSaver.
    If no connection string is available or an in-memory sentinel is given,
    returns a MemorySaver instance.

    Args:
        connection_string: PostgreSQL URI string, 'memory', or None.
        pool: Pre-existing ConnectionPool instance (bypasses pool creation).
        auto_setup: If True and using PostgresSaver, calls checkpointer.setup() to run migrations.
        min_size: Minimum connection pool size.
        max_size: Maximum connection pool size.
        open: Whether to open the pool immediately.
        **pool_kwargs: Additional parameters passed to create_connection_pool.

    Returns:
        BaseCheckpointSaver (PostgresSaver or MemorySaver).
    """
    if pool is not None:
        saver = PostgresSaver(conn=pool)
        if auto_setup:
            saver.setup()
        return saver

    conn_str = connection_string
    if conn_str is None:
        conn_str = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URI")

    if not conn_str or conn_str.strip().lower() in IN_MEMORY_SENTINELS:
        logger.info("Using MemorySaver checkpointer fallback.")
        return MemorySaver()

    pool_instance = create_connection_pool(
        conninfo=conn_str,
        min_size=min_size,
        max_size=max_size,
        open=open,
        **pool_kwargs,
    )
    saver = PostgresSaver(conn=pool_instance)
    if auto_setup:
        saver.setup()
    return saver


async def get_async_checkpointer(
    connection_string: Optional[str] = None,
    *,
    pool: Optional[AsyncConnectionPool] = None,
    auto_setup: bool = False,
    min_size: int = DEFAULT_MIN_POOL_SIZE,
    max_size: Optional[int] = DEFAULT_MAX_POOL_SIZE,
    open: bool = True,
    **pool_kwargs: Any,
) -> BaseCheckpointSaver:
    """Factory creating an asynchronous LangGraph checkpointer.

    Must be called inside an active asyncio event loop.
    If an existing async pool is provided, it is wrapped in an AsyncPostgresSaver.
    If a connection_string is provided (or resolved from DATABASE_URL / POSTGRES_URI),
    a new AsyncConnectionPool is created and wrapped in an AsyncPostgresSaver.
    If no connection string is available or an in-memory sentinel is given,
    returns a MemorySaver instance.

    Args:
        connection_string: PostgreSQL URI string, 'memory', or None.
        pool: Pre-existing AsyncConnectionPool instance.
        auto_setup: If True and using AsyncPostgresSaver, awaits checkpointer.setup().
        min_size: Minimum async pool size.
        max_size: Maximum async pool size.
        open: Whether to open the pool immediately.
        **pool_kwargs: Additional parameters passed to create_async_connection_pool.

    Returns:
        BaseCheckpointSaver (AsyncPostgresSaver or MemorySaver).
    """
    if pool is not None:
        saver = AsyncPostgresSaver(conn=pool)
        if auto_setup:
            await saver.setup()
        return saver

    conn_str = connection_string
    if conn_str is None:
        conn_str = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URI")

    if not conn_str or conn_str.strip().lower() in IN_MEMORY_SENTINELS:
        logger.info("Using MemorySaver checkpointer fallback for async execution.")
        return MemorySaver()

    pool_instance = create_async_connection_pool(
        conninfo=conn_str,
        min_size=min_size,
        max_size=max_size,
        open=open,
        **pool_kwargs,
    )
    saver = AsyncPostgresSaver(conn=pool_instance)
    if auto_setup:
        await saver.setup()
    return saver


def close_connection_pool(pool: Union[ConnectionPool, Any]) -> None:
    """Safely closes a synchronous connection pool."""
    if isinstance(pool, ConnectionPool) and not pool.closed:
        pool.close()


async def close_async_connection_pool(pool: Union[AsyncConnectionPool, Any]) -> None:
    """Safely closes an asynchronous connection pool."""
    if isinstance(pool, AsyncConnectionPool) and not pool.closed:
        await pool.close()
```

---

## 4. Comprehensive Unit Test Design: `tests/test_db.py`

Below is the design for `tests/test_db.py` covering all 5 testing tiers.

### 4.1 Test Tier Distribution

| Tier | Focus | Test Cases |
|---|---|---|
| **Tier 1: Feature Coverage** | Happy path factory instantiation, kwargs validation, pool classes | 8 test functions |
| **Tier 2: Boundary & Corner Cases** | Sentinel strings, environment precedence, pool limits, auto_setup handling | 7 test functions |
| **Tier 3: Cross-Feature Integration** | LangGraph StateGraph persistence, thread isolation, version increments | 4 test functions |
| **Tier 4: Mock PostgreSQL Lifecycle** | Mocked PostgresSaver & AsyncPostgresSaver put/get tuple workflows | 4 test functions |
| **Tier 5: Adversarial Hardening** | Pipeline conflicts, invalid connection types, database error propagation | 3 test functions |
| **Total** | | **26 Test Cases** |

### 4.2 Proposed Test Code Blueprint (`tests/test_db.py`)

```python
"""Unit and integration tests for database connection pooling and checkpointer factories."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Generator, TypedDict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from db import (
    DEFAULT_KWARGS,
    DEFAULT_MAX_POOL_SIZE,
    DEFAULT_MIN_POOL_SIZE,
    close_async_connection_pool,
    close_connection_pool,
    create_async_connection_pool,
    create_connection_pool,
    get_async_checkpointer,
    get_checkpointer,
)

SAMPLE_PG_URI = "postgresql://testuser:testpass@localhost:5432/antigravity_test"


# ============================================================================
# Tier 1: Feature Coverage (Happy Path Isolation)
# ============================================================================

def test_get_checkpointer_default_memory_fallback():
    """Verify that get_checkpointer() with no arguments returns a MemorySaver instance."""
    checkpointer = get_checkpointer()
    assert isinstance(checkpointer, MemorySaver)
    assert isinstance(checkpointer, BaseCheckpointSaver)


def test_get_checkpointer_explicit_memory_string():
    """Verify explicit memory strings return MemorySaver."""
    for sentinel in ["memory", ":memory:", "MEMORY", " none "]:
        saver = get_checkpointer(sentinel)
        assert isinstance(saver, MemorySaver)


def test_get_checkpointer_postgres_creation():
    """Verify get_checkpointer with postgres URI creates PostgresSaver backed by ConnectionPool."""
    saver = get_checkpointer(SAMPLE_PG_URI, open=False)
    assert isinstance(saver, PostgresSaver)
    assert isinstance(saver.conn, ConnectionPool)
    assert saver.conn.conninfo == SAMPLE_PG_URI


def test_connection_pool_kwargs_autocommit_dict_row():
    """Verify ConnectionPool kwargs explicitly enforce autocommit=True and row_factory=dict_row."""
    pool = create_connection_pool(SAMPLE_PG_URI, open=False)
    assert pool.kwargs["autocommit"] is True
    assert pool.kwargs["row_factory"] is dict_row


@pytest.mark.asyncio
async def test_get_async_checkpointer_default_memory_fallback():
    """Verify get_async_checkpointer() with no arguments returns MemorySaver."""
    saver = await get_async_checkpointer()
    assert isinstance(saver, MemorySaver)


@pytest.mark.asyncio
async def test_get_async_checkpointer_postgres_creation():
    """Verify get_async_checkpointer creates AsyncPostgresSaver backed by AsyncConnectionPool."""
    saver = await get_async_checkpointer(SAMPLE_PG_URI, open=False)
    assert isinstance(saver, AsyncPostgresSaver)
    assert isinstance(saver.conn, AsyncConnectionPool)
    assert saver.conn.conninfo == SAMPLE_PG_URI


def test_get_checkpointer_with_preexisting_pool():
    """Verify passing an existing ConnectionPool directly to get_checkpointer wraps it."""
    mock_pool = MagicMock(spec=ConnectionPool)
    saver = get_checkpointer(pool=mock_pool)
    assert isinstance(saver, PostgresSaver)
    assert saver.conn is mock_pool


@pytest.mark.asyncio
async def test_get_async_checkpointer_with_preexisting_pool():
    """Verify passing an existing AsyncConnectionPool directly wraps it."""
    mock_apool = MagicMock(spec=AsyncConnectionPool)
    saver = await get_async_checkpointer(pool=mock_apool)
    assert isinstance(saver, AsyncPostgresSaver)
    assert saver.conn is mock_apool


# ============================================================================
# Tier 2: Boundary & Corner Cases
# ============================================================================

def test_empty_and_whitespace_connection_strings():
    """Verify empty or whitespace-only connection strings fallback to MemorySaver."""
    for empty_val in ["", "   ", None]:
        saver = get_checkpointer(empty_val)
        assert isinstance(saver, MemorySaver)


def test_env_var_fallback(monkeypatch):
    """Verify checkpointer resolves DATABASE_URL from environment when not explicitly passed."""
    monkeypatch.setenv("DATABASE_URL", SAMPLE_PG_URI)
    saver = get_checkpointer(open=False)
    assert isinstance(saver, PostgresSaver)
    assert saver.conn.conninfo == SAMPLE_PG_URI


def test_postgres_uri_env_fallback(monkeypatch):
    """Verify checkpointer resolves POSTGRES_URI from environment when DATABASE_URL is unset."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_URI", SAMPLE_PG_URI)
    saver = get_checkpointer(open=False)
    assert isinstance(saver, PostgresSaver)


def test_explicit_argument_precedence_over_env(monkeypatch):
    """Verify explicit argument takes precedence over environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://env_host:5432/envdb")
    saver = get_checkpointer(SAMPLE_PG_URI, open=False)
    assert saver.conn.conninfo == SAMPLE_PG_URI


def test_pool_size_and_timeout_boundaries():
    """Verify custom pool boundary parameters are correctly passed to ConnectionPool."""
    pool = create_connection_pool(
        SAMPLE_PG_URI,
        min_size=5,
        max_size=50,
        timeout=15.5,
        max_idle=300.0,
        open=False,
    )
    assert pool.min_size == 5
    assert pool.max_size == 50
    assert pool.timeout == 15.5
    assert pool.max_idle == 300.0


def test_auto_setup_sync_checkpointer():
    """Verify auto_setup=True invokes saver.setup() on PostgresSaver."""
    mock_pool = MagicMock(spec=ConnectionPool)
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = {"v": -1}

    saver = get_checkpointer(pool=mock_pool, auto_setup=True)
    assert isinstance(saver, PostgresSaver)
    assert mock_cur.execute.called


@pytest.mark.asyncio
async def test_auto_setup_async_checkpointer():
    """Verify auto_setup=True awaits saver.setup() on AsyncPostgresSaver."""
    mock_apool = MagicMock(spec=AsyncConnectionPool)
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute = AsyncMock()
    mock_cur.fetchone = AsyncMock(return_value={"v": -1})
    mock_conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_apool.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_apool.connection.return_value.__aexit__ = AsyncMock(return_value=None)

    saver = await get_async_checkpointer(pool=mock_apool, auto_setup=True)
    assert isinstance(saver, AsyncPostgresSaver)
    assert mock_cur.execute.called


# ============================================================================
# Tier 3: Cross-Feature Combinations (LangGraph StateGraph Execution)
# ============================================================================

class TestState(TypedDict):
    value: str
    count: int


def test_sync_stategraph_checkpointing_with_memory_saver():
    """Verify MemorySaver preserves and increments state across synchronous graph invocations."""
    builder = StateGraph(TestState)
    builder.add_node("step", lambda s: {"value": s["value"] + "->step", "count": s["count"] + 1})
    builder.add_edge(START, "step")
    builder.add_edge("step", END)

    saver = get_checkpointer()
    graph = builder.compile(checkpointer=saver)

    config = {"configurable": {"thread_id": "thread-1"}}
    res1 = graph.invoke({"value": "init", "count": 0}, config=config)
    assert res1 == {"value": "init->step", "count": 1}

    state1 = graph.get_state(config)
    assert state1.values["count"] == 1

    res2 = graph.invoke({"value": "init2", "count": 10}, config=config)
    state2 = graph.get_state(config)
    assert state2.values["count"] == 11


@pytest.mark.asyncio
async def test_async_stategraph_checkpointing_with_memory_saver():
    """Verify MemorySaver preserves and restores state across asynchronous ainvoke calls."""
    builder = StateGraph(TestState)
    builder.add_node("async_step", lambda s: {"value": s["value"] + "->async", "count": s["count"] + 1})
    builder.add_edge(START, "async_step")
    builder.add_edge("async_step", END)

    saver = await get_async_checkpointer()
    graph = builder.compile(checkpointer=saver)

    config = {"configurable": {"thread_id": "async-thread-1"}}
    res = await graph.ainvoke({"value": "start", "count": 5}, config=config)
    assert res == {"value": "start->async", "count": 6}

    state = await graph.aget_state(config)
    assert state.values["value"] == "start->async"
    assert state.values["count"] == 6


def test_thread_isolation_in_checkpointer():
    """Verify distinct thread IDs have isolated state timelines."""
    builder = StateGraph(TestState)
    builder.add_node("step", lambda s: {"value": s["value"], "count": s["count"]})
    builder.add_edge(START, "step")
    builder.add_edge("step", END)

    saver = get_checkpointer()
    graph = builder.compile(checkpointer=saver)

    config_a = {"configurable": {"thread_id": "thread-A"}}
    config_b = {"configurable": {"thread_id": "thread-B"}}

    graph.invoke({"value": "Thread A State", "count": 100}, config=config_a)
    graph.invoke({"value": "Thread B State", "count": 200}, config=config_b)

    assert graph.get_state(config_a).values["value"] == "Thread A State"
    assert graph.get_state(config_b).values["value"] == "Thread B State"


def test_checkpoint_tuple_retrieval_and_history():
    """Verify checkpointer get_tuple retrieves exact tuple and history specs."""
    saver = get_checkpointer()
    config = {"configurable": {"thread_id": "history-thread"}}

    checkpoint = {
        "v": 1,
        "ts": "2026-08-27T00:00:00Z",
        "id": "cp-1",
        "channel_values": {"x": 42},
        "channel_versions": {"x": 1},
        "versions_seen": {},
        "pending_sends": [],
    }
    metadata = {"source": "input", "step": 1, "writes": {}}

    saver.put(config, checkpoint, metadata, {})
    tuple_result = saver.get_tuple(config)

    assert tuple_result is not None
    assert tuple_result.checkpoint["channel_values"]["x"] == 42
    assert tuple_result.metadata["step"] == 1


# ============================================================================
# Tier 4: Mocked PostgreSQL Real-World Workloads
# ============================================================================

def test_mocked_postgres_saver_put():
    """Verify PostgresSaver writes to mocked connection pool cursor."""
    mock_pool = MagicMock(spec=ConnectionPool)
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    saver = PostgresSaver(conn=mock_pool)
    config = {"configurable": {"thread_id": "mock-pg-thread", "checkpoint_ns": ""}}
    checkpoint = {
        "v": 1,
        "ts": "2026-08-27T00:00:00Z",
        "id": "cp-mock",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
        "pending_sends": [],
    }
    saver.put(config, checkpoint, {}, {})
    assert mock_cur.execute.called


@pytest.mark.asyncio
async def test_mocked_async_postgres_saver_aput():
    """Verify AsyncPostgresSaver writes to mocked async pool cursor."""
    mock_apool = MagicMock(spec=AsyncConnectionPool)
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute = AsyncMock()
    mock_conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_apool.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_apool.connection.return_value.__aexit__ = AsyncMock(return_value=None)

    saver = AsyncPostgresSaver(conn=mock_apool)
    config = {"configurable": {"thread_id": "mock-apg-thread", "checkpoint_ns": ""}}
    checkpoint = {
        "v": 1,
        "ts": "2026-08-27T00:00:00Z",
        "id": "cp-mock-async",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
        "pending_sends": [],
    }
    await saver.aput(config, checkpoint, {}, {})
    assert mock_cur.execute.called


def test_close_connection_pool_safe():
    """Verify close_connection_pool closes pool and ignores non-pools."""
    mock_pool = MagicMock(spec=ConnectionPool)
    mock_pool.closed = False
    close_connection_pool(mock_pool)
    mock_pool.close.assert_called_once()

    # Safe with None or MemorySaver
    close_connection_pool(None)
    close_connection_pool(MemorySaver())


@pytest.mark.asyncio
async def test_close_async_connection_pool_safe():
    """Verify close_async_connection_pool awaits close on async pools."""
    mock_apool = MagicMock(spec=AsyncConnectionPool)
    mock_apool.closed = False
    mock_apool.close = AsyncMock()
    await close_async_connection_pool(mock_apool)
    mock_apool.close.assert_awaited_once()

    # Safe with None or MemorySaver
    await close_async_connection_pool(None)
    await close_async_connection_pool(MemorySaver())


# ============================================================================
# Tier 5: Adversarial Hardening & Failure Recovery
# ============================================================================

def test_pipeline_with_connection_pool_rejection():
    """Verify passing pipeline to PostgresSaver with ConnectionPool raises ValueError."""
    mock_pool = MagicMock(spec=ConnectionPool)
    mock_pipe = MagicMock()
    with pytest.raises(ValueError, match="Pipeline should be used only with a single Connection"):
        PostgresSaver(conn=mock_pool, pipe=mock_pipe)


def test_invalid_connection_type_raises_type_error():
    """Verify get_connection raises TypeError when passed an unsupported object type."""
    from langgraph.checkpoint.postgres._internal import get_connection
    with pytest.raises(TypeError, match="Invalid connection type"):
        with get_connection("invalid_conn_string"):
            pass


def test_database_error_on_setup_propagates():
    """Verify database exceptions during setup() propagate cleanly."""
    mock_pool = MagicMock(spec=ConnectionPool)
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute.side_effect = RuntimeError("Database migration connection failure")
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    saver = PostgresSaver(conn=mock_pool)
    with pytest.raises(RuntimeError, match="Database migration connection failure"):
        saver.setup()
```

---

## 5. Downstream Integration with Milestones M2, M3, and M4

1. **Milestone M3 (`supervisor.py`) Integration**:
   - `supervisor.py` will expose `create_control_plane_graph(checkpointer: Optional[BaseCheckpointSaver] = None)`:
     ```python
     from db import get_checkpointer

     def create_control_plane_graph(checkpointer=None):
         if checkpointer is None:
             checkpointer = get_checkpointer()
         builder = StateGraph(AgentState)
         # ... worker and supervisor nodes ...
         return builder.compile(checkpointer=checkpointer)
     ```
   - In production, setting `DATABASE_URL=postgresql://...` automatically attaches `PostgresSaver`.
   - In automated test runs (`pytest test_orchestrator.py`), omitting `DATABASE_URL` uses `MemorySaver()`, satisfying the sub-10 second execution and zero-network mandate.

2. **Milestone M4 (`test_orchestrator.py` & `conftest.py`)**:
   - Fixture in `conftest.py`:
     ```python
     @pytest.fixture
     def checkpointer():
         return get_checkpointer("memory")
     ```

---

## 6. Verification Plan & Commands

To independently verify the checkpointer module and test suite:
1. Run the test suite with verbose output and timing:
   ```powershell
   python -m pytest tests/test_db.py -v --durations=10
   ```
2. Verify that 100% of the 26 unit tests pass in under 2 seconds with 0 network egress.
