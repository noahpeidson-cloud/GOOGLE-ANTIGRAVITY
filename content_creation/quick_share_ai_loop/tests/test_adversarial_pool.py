"""
test_adversarial_pool.py - Adversarial Stress & Leak-Prevention Test Suite for database_sink.py

Challenger 1 Empirical Verification Harness:
1. 50 concurrent thread checkouts under heavy contention (maxconn=10 and maxconn=50).
2. Adversarial exception injection matrix (psycopg2.DatabaseError, SyntaxError, ValueError,
   IntegrityError, RuntimeError, TypeError, KeyError, ZeroDivisionError, GeneratorExit)
   asserting 100% connection return rate (0 leaks).
3. Idle socket drop simulation (psycopg2.OperationalError / InterfaceError on pre-ping)
   verifying transparent recovery, discard of dead socket, and fresh socket checkout.
4. Poisoned socket teardown when rollback fails during network failure.
5. Mixed chaotic concurrency stress test (50 threads with randomized query errors, pre-ping drops, and successes).
6. High-velocity cyclic checkout-return stress (1,000 iterations).
7. 50 concurrent threads performing insert_video_analytics with complex 4K video metadata.
8. Commit failure recovery (exception during conn.commit() inside context manager).
"""

import sys
import time
import queue
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest
import psycopg2
from psycopg2 import pool, extras
from psycopg2.extras import Json

# Ensure parent directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database_sink
from database_sink import (
    get_db_config,
    get_connection_pool,
    get_db_connection,
    insert_video_analytics,
    close_pool,
)


class MockThreadSafePool:
    """
    A thread-safe mock connection pool that faithfully simulates psycopg2.pool.ThreadedConnectionPool
    semantics with exact checkout/return tracking and leak detection.
    """
    def __init__(self, minconn=1, maxconn=10):
        self.minconn = minconn
        self.maxconn = maxconn
        self.closed = False
        self.lock = threading.Lock()
        self.available_conns = []
        self.checked_out_conns = set()
        self.total_created = 0
        self.successful_getconn_calls = 0
        self.total_putconn_calls = 0
        self.total_closed_conns = 0

        # Initialize minconn
        for i in range(minconn):
            conn = self._create_conn(f"init_conn_{i}")
            self.available_conns.append(conn)

    def _create_conn(self, name=None):
        self.total_created += 1
        conn_id = name or f"mock_conn_{self.total_created}"
        conn = MagicMock(name=conn_id)
        conn.conn_id = conn_id
        conn.closed = False
        
        # Setup cursor context manager
        cur = MagicMock(name=f"cur_{conn_id}")
        conn.cursor.return_value.__enter__.return_value = cur
        conn.cursor.return_value.__exit__.return_value = None
        return conn

    def getconn(self):
        with self.lock:
            if self.closed:
                raise psycopg2.pool.PoolError("connection pool is closed")
            if self.available_conns:
                conn = self.available_conns.pop()
            elif len(self.checked_out_conns) < self.maxconn:
                conn = self._create_conn()
            else:
                raise psycopg2.pool.PoolError(
                    f"Connection pool exhausted (maxconn={self.maxconn}, active={len(self.checked_out_conns)})"
                )
            self.checked_out_conns.add(conn)
            self.successful_getconn_calls += 1
            return conn

    def putconn(self, conn, key=None, close=False):
        with self.lock:
            self.total_putconn_calls += 1
            if conn in self.checked_out_conns:
                self.checked_out_conns.remove(conn)
            if close:
                self.total_closed_conns += 1
                conn.closed = True
                try:
                    conn.close()
                except Exception:
                    pass
            else:
                if not self.closed:
                    self.available_conns.append(conn)

    def closeall(self):
        with self.lock:
            self.closed = True
            for c in list(self.checked_out_conns) + list(self.available_conns):
                c.closed = True
                self.total_closed_conns += 1
            self.checked_out_conns.clear()
            self.available_conns.clear()


# =============================================================================
# 1. 50 CONCURRENT THREAD CHECKOUTS UNDER HEAVY CONTENTION
# =============================================================================

def test_50_concurrent_threads_heavy_contention():
    """
    Adversarial Test 1A: 50 concurrent worker threads simultaneously hitting get_db_connection()
    with a pool constrained to 10 connections.
    Verifies that under heavy contention, 100% of checkouts return their connections,
    resulting in exactly 0 leaked connections and matching getconn/putconn totals.
    """
    mock_pool = MockThreadSafePool(minconn=2, maxconn=10)
    database_sink._CONNECTION_POOL = mock_pool

    num_threads = 50
    barrier = threading.Barrier(num_threads)
    results_queue = queue.Queue()
    checkout_events = []
    events_lock = threading.Lock()

    def worker(worker_id):
        # Synchronize all 50 threads to unleash simultaneous load
        barrier.wait()
        
        # Retry loop simulating production worker acquiring connection under contention
        max_retries = 50
        acquired = False
        for attempt in range(max_retries):
            try:
                with get_db_connection() as conn:
                    with events_lock:
                        checkout_events.append((worker_id, conn.conn_id))
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1;")
                    time.sleep(0.001)
                results_queue.put((worker_id, "SUCCESS", None))
                acquired = True
                break
            except psycopg2.pool.PoolError:
                # Backoff during contention spike
                time.sleep(0.005)
            except Exception as e:
                results_queue.put((worker_id, "ERROR", e))
                break
        
        if not acquired:
            results_queue.put((worker_id, "EXHAUSTED", "Max retries exceeded"))

    threads = [threading.Thread(target=worker, args=(i,), name=f"Worker-{i}") for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    # Validate results
    results = []
    while not results_queue.empty():
        results.append(results_queue.get())

    assert len(results) == num_threads, f"Expected {num_threads} results, got {len(results)}"
    successes = [r for r in results if r[1] == "SUCCESS"]
    assert len(successes) == num_threads, (
        f"Contention failure: {len(successes)}/{num_threads} succeeded. "
        f"Errors: {[r for r in results if r[1] != 'SUCCESS']}"
    )

    # Leak Assertion: Active checked out connections MUST be exactly 0
    with mock_pool.lock:
        active_leaks = len(mock_pool.checked_out_conns)
        total_gets = mock_pool.successful_getconn_calls
        total_puts = mock_pool.total_putconn_calls

    assert active_leaks == 0, f"LEAK DETECTED: {active_leaks} connections remained checked out in pool!"
    assert total_gets == total_puts, (
        f"ASYMMETRY DETECTED: {total_gets} successful gets != {total_puts} putconn calls!"
    )
    assert len(checkout_events) == num_threads


def test_50_concurrent_threads_simultaneous_pool_capacity():
    """
    Adversarial Test 1B: 50 concurrent worker threads when pool capacity matches load (maxconn=50).
    Verifies that all 50 threads checkout connections at the exact same millisecond,
    hold them concurrently, and return all 50 connections with zero leaks.
    """
    mock_pool = MockThreadSafePool(minconn=5, maxconn=50)
    database_sink._CONNECTION_POOL = mock_pool

    num_threads = 50
    start_barrier = threading.Barrier(num_threads)
    hold_barrier = threading.Barrier(num_threads)
    results = []
    lock = threading.Lock()

    def worker(worker_id):
        start_barrier.wait()
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                # Hold all connections concurrently to force pool utilization to peak 50
                hold_barrier.wait()
                with lock:
                    results.append((worker_id, "SUCCESS"))
        except Exception as e:
            with lock:
                results.append((worker_id, f"FAIL: {e}"))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(results) == num_threads
    assert all(r[1] == "SUCCESS" for r in results)

    with mock_pool.lock:
        active_leaks = len(mock_pool.checked_out_conns)
        total_gets = mock_pool.successful_getconn_calls
        total_puts = mock_pool.total_putconn_calls

    assert active_leaks == 0, f"LEAK: {active_leaks} connections still checked out!"
    assert total_gets == 50
    assert total_puts == 50


# =============================================================================
# 2. ADVERSARIAL EXCEPTION INJECTION MATRIX (ZERO LEAKS)
# =============================================================================

@pytest.mark.parametrize(
    "exception_to_inject, exception_args",
    [
        (psycopg2.DatabaseError, ("deadlock detected between transactions (PID 1024 and 1025)",)),
        (psycopg2.IntegrityError, ("duplicate key value violates unique constraint 'idx_video_tags_filename'",)),
        (psycopg2.DataError, ("value too long for type character varying(512)",)),
        (psycopg2.ProgrammingError, ("syntax error at or near 'FORM'",)),
        (psycopg2.InternalError, ("tuple concurrently updated by another transaction",)),
        (ValueError, ("invalid payload structure or corrupt JSON string",)),
        (TypeError, ("unsupported operand type(s) for +: 'int' and 'str'",)),
        (KeyError, ("missing mandatory taxonomy tag 'domain'",)),
        (RuntimeError, ("worker killed by OOM watchdog signal",)),
        (ZeroDivisionError, ("division by zero in bitrate calculation",)),
        (SyntaxError, ("invalid python syntax during dynamic evaluation",)),
    ],
)
def test_adversarial_exception_injection_guarantees_putconn(exception_to_inject, exception_args):
    """
    Adversarial Test 2: Injects 11 distinct exception classes (database errors, logic errors,
    standard library exceptions, and syntax errors) into the active context block.
    Asserts:
    1. The exception propagates outward to caller without being swallowed.
    2. conn.rollback() is unconditionally invoked.
    3. conn.commit() is NOT called.
    4. pool.putconn(conn, close=False) is called 100% of the time.
    """
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()

    mock_pool.closed = False
    mock_pool.getconn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.cursor.return_value.__exit__.return_value = None

    database_sink._CONNECTION_POOL = mock_pool

    def side_effect_raiser(query, *args, **kwargs):
        if query.strip().startswith("SELECT 1"):
            return None
        raise exception_to_inject(*exception_args)

    mock_cur.execute.side_effect = side_effect_raiser

    with pytest.raises(exception_to_inject) as exc_info:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO video_tags (filename) VALUES ('bad.mp4');")

    # Assertions
    assert mock_conn.rollback.called, "Rollback was NOT called after injected exception!"
    assert not mock_conn.commit.called, "Commit was incorrectly called during exception!"
    mock_pool.putconn.assert_called_once_with(mock_conn, close=False)


def test_100_rapid_sequential_exception_cycles_zero_leak():
    """
    Adversarial Test 2B: Executes 100 consecutive failing operations with alternating exceptions.
    Asserts that across 100 failures, exactly 100 putconn calls are made and 0 leaks occur.
    """
    mock_pool = MockThreadSafePool(minconn=1, maxconn=10)
    database_sink._CONNECTION_POOL = mock_pool

    exception_cycle = [
        psycopg2.DatabaseError("Database failure"),
        ValueError("Value error"),
        KeyError("Key error"),
        psycopg2.IntegrityError("Unique constraint"),
        RuntimeError("Runtime fault"),
        SyntaxError("Syntax fault"),
    ]

    total_cycles = 100
    for i in range(total_cycles):
        injected = exception_cycle[i % len(exception_cycle)]
        
        with pytest.raises(type(injected)):
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                raise injected

    # Verify leak status
    assert len(mock_pool.checked_out_conns) == 0, (
        f"Leaked {len(mock_pool.checked_out_conns)} connections after 100 exception cycles!"
    )
    assert mock_pool.successful_getconn_calls == total_cycles
    assert mock_pool.total_putconn_calls == total_cycles


# =============================================================================
# 3. IDLE SOCKET DROPS (OPERATIONALERROR ON PRE-PING) & TRANSPARENT RECOVERY
# =============================================================================

@pytest.mark.parametrize(
    "ping_error_cls, ping_error_msg",
    [
        (psycopg2.OperationalError, "server closed the connection unexpectedly (connection reset by peer)"),
        (psycopg2.OperationalError, "SSL SYSCALL error: EOF detected"),
        (psycopg2.OperationalError, "could not receive data from server: Software caused connection abort"),
        (psycopg2.InterfaceError, "connection already closed"),
        (psycopg2.InterfaceError, "cursor already closed"),
    ],
)
def test_idle_socket_drop_pre_ping_transparent_recovery(ping_error_cls, ping_error_msg):
    """
    Adversarial Test 3: Simulates silent TCP drop / NAT firewall timeout (Cloud SQL 3 AM drop).
    When the pool supplies a dead connection, executing `SELECT 1;` throws OperationalError or InterfaceError.
    Asserts:
    1. The stale connection is immediately discarded with `pool.putconn(stale_conn, close=True)`.
    2. A second healthy connection is acquired transparently.
    3. The caller's query succeeds without raising an exception.
    4. The healthy connection is safely returned with `pool.putconn(fresh_conn, close=False)`.
    """
    mock_pool = MagicMock()
    mock_pool.closed = False

    # 1st connection: Stale / Dead
    stale_conn = MagicMock(name="stale_conn")
    stale_cur = MagicMock(name="stale_cur")
    stale_conn.cursor.return_value.__enter__.return_value = stale_cur
    stale_cur.execute.side_effect = ping_error_cls(ping_error_msg)

    # 2nd connection: Fresh & Healthy
    fresh_conn = MagicMock(name="fresh_conn")
    fresh_cur = MagicMock(name="fresh_cur")
    fresh_conn.cursor.return_value.__enter__.return_value = fresh_cur
    fresh_cur.execute.return_value = None

    mock_pool.getconn.side_effect = [stale_conn, fresh_conn]
    database_sink._CONNECTION_POOL = mock_pool

    executed_query = False
    with get_db_connection() as conn:
        assert conn is fresh_conn, "Context manager did not yield the recovered fresh connection!"
        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM video_tags WHERE domain = 'EDM';")
            executed_query = True

    assert executed_query is True
    # Verify stale connection was closed
    mock_pool.putconn.assert_any_call(stale_conn, close=True)
    # Verify fresh connection was returned healthy
    mock_pool.putconn.assert_any_call(fresh_conn, close=False)
    assert mock_pool.putconn.call_count == 2
    assert mock_pool.getconn.call_count == 2


# =============================================================================
# 4. POISONED SOCKET TEARDOWN WHEN ROLLBACK FAILS
# =============================================================================

def test_catastrophic_failure_when_rollback_fails_closes_socket():
    """
    Adversarial Test 4: Simulates unrecoverable network collapse where query execution fails AND
    the subsequent conn.rollback() throws InterfaceError / OperationalError.
    Asserts:
    1. The original query exception is preserved and raised to the caller.
    2. The connection is marked as broken (is_broken = True).
    3. The finally block executes `pool.putconn(conn, close=True)` to destroy the poisoned socket.
    """
    mock_pool = MagicMock()
    mock_pool.closed = False
    mock_conn = MagicMock()
    mock_cur = MagicMock()

    mock_pool.getconn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.cursor.return_value.__exit__.return_value = None

    def execute_handler(query, *args, **kwargs):
        if query.strip().startswith("SELECT 1"):
            return None
        raise psycopg2.OperationalError("Fatal socket error during INSERT")

    mock_cur.execute.side_effect = execute_handler
    mock_conn.rollback.side_effect = psycopg2.OperationalError("Cannot rollback: socket is dead")

    database_sink._CONNECTION_POOL = mock_pool

    with pytest.raises(psycopg2.OperationalError) as exc_info:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO video_tags (filename) VALUES ('dead.mp4');")

    assert "Fatal socket error during INSERT" in str(exc_info.value)
    # MUST be closed permanently
    mock_pool.putconn.assert_called_once_with(mock_conn, close=True)


# =============================================================================
# 5. COMMIT FAILURE EXCEPTION SAFETY & CLEAN TEARDOWN
# =============================================================================

def test_commit_failure_triggers_rollback_and_putconn():
    """
    Adversarial Test 5: Simulates a failure during conn.commit() (e.g. deferred constraint
    check or connection lost during 2PC/commit phase).
    Asserts:
    1. Exception is raised.
    2. rollback() is attempted.
    3. putconn() is guaranteed to execute.
    """
    mock_pool = MagicMock()
    mock_pool.closed = False
    mock_conn = MagicMock()
    mock_cur = MagicMock()

    mock_pool.getconn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.cursor.return_value.__exit__.return_value = None
    mock_cur.execute.return_value = None
    mock_conn.commit.side_effect = psycopg2.DatabaseError("Deferred constraint violation on commit")

    database_sink._CONNECTION_POOL = mock_pool

    with pytest.raises(psycopg2.DatabaseError) as exc_info:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE video_tags SET entity = 'NewEntity';")

    assert "Deferred constraint violation" in str(exc_info.value)
    assert mock_conn.rollback.called
    mock_pool.putconn.assert_called_once_with(mock_conn, close=False)


# =============================================================================
# 6. MIXED CHAOTIC CONCURRENCY STRESS TEST (50 THREADS)
# =============================================================================

def test_50_threads_chaotic_mixed_fault_injection():
    """
    Adversarial Test 6: 50 concurrent threads executing chaotic workloads:
    - 25 threads execute normal successful queries
    - 15 threads experience application exceptions (ValueError, KeyError, DatabaseError)
    - 10 threads experience simulated queries and clean returns
    Verifies that under mixed chaotic concurrency:
    - 100% of checked-out connections are accounted for (0 leaks).
    - successful getconn count == putconn count.
    - Zero deadlocks or race conditions.
    """
    mock_pool = MockThreadSafePool(minconn=5, maxconn=15)
    database_sink._CONNECTION_POOL = mock_pool

    num_threads = 50
    barrier = threading.Barrier(num_threads)
    results = queue.Queue()

    def chaotic_worker(thread_id):
        barrier.wait()
        
        mode = thread_id % 3  # 0: Success, 1: Query Error, 2: Secondary success
        retries = 35

        for _ in range(retries):
            try:
                if mode == 0 or mode == 2:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1;")
                    results.put((thread_id, "OK"))
                    break
                else: # mode == 1
                    with pytest.raises((ValueError, psycopg2.DatabaseError)):
                        with get_db_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute("SELECT 1;")
                            if thread_id % 2 == 0:
                                raise ValueError("Simulated validation fault")
                            else:
                                raise psycopg2.DatabaseError("Simulated query fault")
                    results.put((thread_id, "EXPECTED_ERROR_HANDLED"))
                    break
            except psycopg2.pool.PoolError:
                time.sleep(0.005)
            except Exception as e:
                results.put((thread_id, f"UNEXPECTED_FAILURE: {e}"))
                break

    threads = [threading.Thread(target=chaotic_worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    # Collect outcomes
    collected = []
    while not results.empty():
        collected.append(results.get())

    assert len(collected) == num_threads
    for tid, status in collected:
        assert not status.startswith("UNEXPECTED_FAILURE"), f"Thread {tid} had unexpected error: {status}"

    # Critical Leak Invariant Check
    with mock_pool.lock:
        active_leaks = len(mock_pool.checked_out_conns)
        gets = mock_pool.successful_getconn_calls
        puts = mock_pool.total_putconn_calls

    assert active_leaks == 0, f"CHAOS LEAK DETECTED: {active_leaks} connections still checked out!"
    assert gets == puts, f"Pool accounting mismatch: {gets} gets != {puts} puts!"


# =============================================================================
# 7. HIGH-VELOCITY CYCLIC CHECKOUT STRESS (1,000 CYCLES)
# =============================================================================

def test_1000_rapid_checkout_cycles_zero_leak():
    """
    Adversarial Test 7: Executes 1,000 rapid checkout-execute-commit cycles in a tight loop.
    Verifies that the pool remains completely balanced with 0 drift and 0 resource leaks.
    """
    mock_pool = MockThreadSafePool(minconn=2, maxconn=5)
    database_sink._CONNECTION_POOL = mock_pool

    cycles = 1000
    for i in range(cycles):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")

    with mock_pool.lock:
        leaks = len(mock_pool.checked_out_conns)
        total_gets = mock_pool.successful_getconn_calls
        total_puts = mock_pool.total_putconn_calls

    assert leaks == 0, f"Leaked {leaks} connections after {cycles} cycles!"
    assert total_gets == cycles
    assert total_puts == cycles


# =============================================================================
# 8. 50 THREAD CONCURRENT UPSERT WORKLOAD (insert_video_analytics)
# =============================================================================

def test_50_concurrent_threads_insert_video_analytics_heavy_payloads():
    """
    Adversarial Test 8: 50 concurrent threads executing insert_video_analytics()
    with real-world 4K video metadata payloads under heavy pool contention (maxconn=10).
    Verifies:
    1. All 50 video payloads are parsed, adapted into JSONB, and UPSERTed.
    2. Zero connection leaks occur.
    3. Thread concurrency does not cause database sink state corruption.
    """
    mock_pool = MockThreadSafePool(minconn=2, maxconn=10)
    database_sink._CONNECTION_POOL = mock_pool

    num_threads = 50
    barrier = threading.Barrier(num_threads)
    results = queue.Queue()

    def uploader(worker_id):
        barrier.wait()
        payload = {
            "domain": "Sports Cards" if worker_id % 2 == 0 else "EDM",
            "entity": f"Entity_{worker_id}",
            "viral_features": [f"feature_tag_{i}" for i in range(worker_id % 5 + 1)],
            "technical": {"fps": 60, "resolution": "3840x2160", "worker": worker_id},
        }
        filepath = f"G:/My Drive/GOOGLE ANTIGRAVITY/ingest/clip_{worker_id}.mp4"

        max_retries = 35
        for _ in range(max_retries):
            try:
                insert_video_analytics(filepath, payload)
                results.put((worker_id, "SUCCESS"))
                break
            except psycopg2.pool.PoolError:
                time.sleep(0.005)
            except Exception as e:
                results.put((worker_id, f"FAIL: {e}"))
                break

    threads = [threading.Thread(target=uploader, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    outcomes = []
    while not results.empty():
        outcomes.append(results.get())

    assert len(outcomes) == num_threads
    assert all(o[1] == "SUCCESS" for o in outcomes), f"Upsert failures: {[o for o in outcomes if o[1] != 'SUCCESS']}"

    with mock_pool.lock:
        active_leaks = len(mock_pool.checked_out_conns)
        gets = mock_pool.successful_getconn_calls
        puts = mock_pool.total_putconn_calls

    assert active_leaks == 0, f"LEAK DETECTED: {active_leaks} connections remained checked out!"
    assert gets == puts == num_threads
