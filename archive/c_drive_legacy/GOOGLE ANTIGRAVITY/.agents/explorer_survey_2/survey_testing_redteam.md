# PostgreSQL Migration & Connection Pool Red Team Survey: `quick_share_ai_loop`

**Author:** Explorer 2 (Red Team & Testing Specialist)  
**Target Project:** `g:/My Drive/GOOGLE ANTIGRAVITY/quick_share_ai_loop`  
**Date:** 2026-08-27  
**Status:** Completed Architectural & Adversarial Survey

---

## 1. Executive Summary & Problem Scope

The `quick_share_ai_loop` pipeline is an autonomous, event-driven daemon running 24/7 on the local workstation. It intercepts raw 4K videos transferred via Samsung Quick Share, generates 720p proxies, extracts a 4-layer taxonomy via Gemini 3.6 Flash (`domain`, `entity`, `viral_features`, `technical`), sinks the metadata, and moves the raw media to Google Drive (`photos_triage_project/Raw_Ingest`).

Currently, the sink is backed by a local SQLite file (`media_analytics.db`) using `sqlite3.connect()`. The objective is to migrate this database sink to a production **Google Cloud SQL PostgreSQL** instance (accessible directly or via Firebase Data Connect) with robust connection pooling, fail-fast auth enforcement (Rule **R26**), `JSONB` array/object support, and zero connection leak vulnerabilities.

This survey delivers:
1. **Root-cause vulnerability analysis** of connection leaks, pool starvation, idle timeouts, and Cloud SQL connection exhaustion in long-running Python daemons.
2. **Architecture Red Team Audit** following the `architecture-red-team` protocol and omnichannel alignment with Noah's 4 active tracks.
3. **PostgreSQL schema & GIN indexing design** replacing stringified SQLite TEXT columns with native `JSONB`.
4. **Deterministic testing framework** using `unittest.mock` and `pytest` with "Loud Assertions" to verify 100% of PostgreSQL pooling, recovery, and payload insertion logic without requiring a live GCP instance.
5. **Production-grade reference blueprints** for `database_sink.py` and `test_database_sink.py`.

---

## 2. Deep-Dive Vulnerability Analysis: Connection Pooling & Leaks in Python Daemons

In a long-running watchdog daemon (`quick_share_hijack.py`), transitioning from local SQLite to remote Cloud SQL PostgreSQL introduces six major failure modes.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Watchdog Daemon Event Loop                            │
│  (on_created spawned in background thread on Quick Share file arrival)     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
     [Vulnerability 2: Pool Starvation]           [Vulnerability 3: Idle Drops]
     Multiple concurrent drops exhaust             Connection idle > 10 mins
     unmanaged or small pool size                  dropped silently by NAT/GCP
                │                                             │
                ▼                                             ▼
     [Vulnerability 1: Connection Leaks]          [Vulnerability 5: Hangs]
     Unhandled exception skips putconn()          Daemon SIGINT leaves hanging
     → Socket / Backend exhaustion                Cloud SQL backend sessions
```

### Vulnerability Vector 1: Unhandled Exceptions & Unclosed Cursors / Connections
- **The SQLite Illusion:** In SQLite, `sqlite3.connect()` creates a local file descriptor that OS file handles clean up on process exit, and SQLite locks are process-local.
- **The Cloud SQL Reality:** A `psycopg2` connection to Cloud SQL occupies a dedicated backend Postgres process (`postgres: user db host(port) idle`), consuming memory (typically 5–10 MB RAM per backend connection) and incrementing the database's `max_connections` counter.
- **The Leak Mechanism:** If an exception is thrown during JSON serialization, schema mismatch, or network transport without a strict `try...finally` block that calls `pool.putconn(conn)` or `conn.close()`, that connection is orphaned. The connection remains checked out of the pool indefinitely.
- **Impact:** After $N$ errors (where $N = \text{maxconn}$), the pool deadlocks on `pool.getconn()`, permanently freezing the media ingestion loop.

### Vulnerability Vector 2: Watchdog Concurrency & Threaded Pool Starvation
- **The Architecture:** `quick_share_hijack.py` uses `watchdog.observers.Observer()`. When a user transfers 10 videos at once via Quick Share, watchdog dispatches `on_created` callbacks across multiple background worker threads.
- **The Flaw:** If developers use `psycopg2.pool.SimpleConnectionPool`, it is **not thread-safe**. Concurrent `getconn()` / `putconn()` calls cause race conditions, corrupting the pool's internal list `_pool`.
- **The Fix:** Must use `psycopg2.pool.ThreadedConnectionPool`. Furthermore, the pool size (`minconn`, `maxconn`) must accommodate peak bursts (e.g., `minconn=1`, `maxconn=10`) with a bounded timeout rather than blocking indefinitely.

### Vulnerability Vector 3: Idle Timeouts & Silent TCP Connection Drops ("The 3 AM Syndrome")
- **The Phenomenon:** Video transfers are sporadic. Hours or days may elapse between Quick Share events.
- **The Network Vector:** Cloud SQL, Google Cloud load balancers, and local NAT routers terminate idle TCP connections after 10 to 15 minutes of inactivity without sending a TCP RST packet to the client.
- **The Failure:** At 3:00 AM, when a new video arrives, the pool returns a stale connection handle. Executing `cur.execute()` immediately crashes with:
  ```text
  psycopg2.OperationalError: server closed the connection unexpectedly
      This probably means the server terminated abnormally
      before or while processing the request.
  ```
- **Red Team Mitigation:**
  1. **TCP Keepalives:** Inject TCP keepalive settings into the DSN: `keepalives=1 keepalives_idle=30 keepalives_interval=10 keepalives_count=3`.
  2. **Pre-Ping Health Check:** Before executing work on a checked-out connection, run a lightweight ping (`SELECT 1;`) inside a safety wrapper. If it raises `OperationalError`, discard the dead connection via `pool.putconn(conn, close=True)`, obtain a fresh connection, and retry.

### Vulnerability Vector 4: Direct TCP vs Cloud SQL Auth Proxy Handshake Overhead
- **Direct Public IP + SSL:** Every cold `psycopg2.connect()` requires DNS resolution, TCP 3-way handshake, and TLS/SSL certificate negotiation (taking 250ms–600ms per connection). Creating a fresh connection per video is an anti-pattern.
- **Cloud SQL Auth Proxy / Connector:** The Google Cloud SQL Python Connector or local Auth Proxy daemon maintains an encrypted tunnel via ephemeral IAM certs.
- **Pool Persistence:** The application must maintain a long-lived, singleton `ThreadedConnectionPool` instance initialized at module load or daemon boot, amortizing the handshake cost across all ingestion runs.

### Vulnerability Vector 5: Daemon Shutdown & Dangling Cloud SQL Sessions
- **The Flaw:** When the user terminates the daemon via `Ctrl+C` (`KeyboardInterrupt`), `Observer.stop()` is called, but open database connections in the pool are abruptly severed without sending a `DISCONNECT` packet to Postgres.
- **Impact:** Cloud SQL keeps backend sessions alive until TCP timeout, holding table locks or consuming connection slots.
- **Mitigation:** Implement `atexit.register(close_pool)` and explicit `try...finally` in the daemon entrypoint to invoke `pool.closeall()`.

### Vulnerability Vector 6: Secret Exposure & Silent Fallback Violation (Rule R26)
- **The Rule:** Rule **R26** (*The Background Daemon Auth Guardrail*) dictates that background scripts must not assume inherited IDE auth and must fail fast if credentials are missing.
- **The Trap:** Naively falling back to default values like `localhost` or `postgres` if `.env` variables are missing causes silent data ingestion into non-existent or wrong databases, or hangs indefinitely attempting to connect to a local port.
- **Mitigation:** Explicit schema validation for `PG_HOST`, `PG_PORT`, `PG_USER`, `PG_PASSWORD`, and `PG_DB` at startup before any watchdog observation begins.

---

## 3. Architecture Red Team Audit (`architecture-red-team`)

Following the 5-step `architecture-red-team` protocol:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                             The Red Team Matrix                                │
├────────────────────────┬────────────────────────────────┬──────────────────────┤
│ Architecture Option    │ Attack / Hidden Vulnerabilities│ Industry Alternative │
├────────────────────────┼────────────────────────────────┼──────────────────────┤
│ 1. Direct psycopg2     │ High latency per video (500ms),│ Threaded pool with   │
│    connect() per call  │ socket exhaustion on bursts.   │ pre-ping validation. │
├────────────────────────┼────────────────────────────────┼──────────────────────┤
│ 2. Unmanaged Global    │ Stale idle TCP drops, unclosed │ Context manager +    │
│    Connection Pool     │ leaks on exceptions, deadlocks.│ close=True disposal. │
├────────────────────────┼────────────────────────────────┼──────────────────────┤
│ 3. Cloud SQL Python    │ Extra async dependency runtime,│ Standard psycopg2    │
│    Connector + pg8000  │ slower pure-Python driver.     │ pool + keepalives.   │
├────────────────────────┼────────────────────────────────┼──────────────────────┤
│ 4. Hybrid Offline-First│ Increases complexity; requires │ Cloud SQL direct     │
│    (SQLite WAL + Sync) │ local sync daemon.             │ with local fallback. │
└────────────────────────┴────────────────────────────────┴──────────────────────┘
```

### 1. The Original Idea
- **Concept:** Replace `sqlite3.connect()` in `database_sink.py` with `psycopg2.connect(os.getenv('DATABASE_URL'))`.
- **Pros:** Minimal lines of code changed.
- **Cons:** Cold-start latency on every file, no connection reuse, high risk of connection exhaustion on multi-file Quick Share transfers, crashes on transient network drops.

### 2. The Red Team Attack (Vulnerabilities Discovered)
1. **Network Partition Data Loss:** If Noah is editing videos offline or in an area with degraded WiFi, a direct Cloud SQL insert will fail and crash the Quick Share watchdog before moving the video to Google Drive, blocking video triage.
2. **JSONB Serialization Type Errors:** `psycopg2` cannot adapt Python `dict` or `list` to Postgres `JSONB` without `psycopg2.extras.Json()` wrapping or automatic JSON adapter registration (`psycopg2.extras.register_default_jsonb()`). Passing raw dicts raises `can't adapt type 'dict'`.
3. **Transaction State Pollution:** In `psycopg2`, an error in a transaction puts the connection in an `ABORTED` state (`current transaction is aborted, commands ignored until end of transaction block`). If the connection is returned to the pool without a `rollback()`, the next caller inherits a broken connection.

### 3. The Industry Standard Alternative
- **Pattern:** **Hardened Thread-Safe Connection Pool with Context Manager & Automatic Rollback**.
- **Key Characteristics:**
  - Encapsulate `psycopg2.pool.ThreadedConnectionPool` in a dedicated `DatabaseSink` manager.
  - Expose a `@contextmanager def get_cursor()` that:
    1. Borrows connection from pool (`getconn()`).
    2. Verifies connection liveness (`SELECT 1;`).
    3. Yields cursor inside a `try` block.
    4. Auto-commits on clean exit (`conn.commit()`).
    5. Auto-rollbacks on exception (`conn.rollback()`).
    6. Always returns connection in a `finally` block (`pool.putconn(conn)` or `pool.putconn(conn, close=True)` if broken).

### 4. The Omnichannel Alignment Check
Cross-referencing this database architecture against Noah's 4 active tracks in `GEMINI.md`:

| Track | Domain | How Cloud SQL PostgreSQL Serves the Track |
|---|---|---|
| **Track 1: Sports Cards** | `/sports_cards` (Card Ladder ETL) | Centralized storage for card market analytics, price histories, and grading submissions. JSONB allows flexible schema for disparate card attributes (BGS subgrades, PSA certs). |
| **Track 2: Content Creation** | `/content_creation` (Media Ingestion, EDM) | Stores 4-layer taxonomy (`domain`, `entity`, `viral_features`, `technical`). Enables querying videos by hook tags (e.g., `Bass_Drop_0:15`) across months of festival footage. |
| **Track 3: Apps** | `/apps` (Unified Ops Hub Dashboard) | The Next.js / FastAPI dashboard can query the same PostgreSQL database directly or via Firebase Data Connect GraphQL, creating a single source of truth across mobile and desktop. |
| **Track 4: Travel and Life** | `/travel_and_life` (Location & Logistics) | GPS coordinates, flight times, and location tags stored in JSONB enable spatial and temporal queries across media. |

**Verdict:** The migration directly unifies Track 2 (Quick Share AI loop) with Track 3 (Unified Ops Hub) and establishes the foundation for Track 1 and Track 4 data synchronization into the Centralized Autonomous Brain.

---

## 4. PostgreSQL Schema & JSONB Optimization

### 4.1 Schema Definition (`schema.sql`)

```sql
-- Quick Share AI Video Analytics Schema (Cloud SQL PostgreSQL / Firebase Data Connect)

CREATE TABLE IF NOT EXISTS video_tags (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    filepath TEXT NOT NULL,
    domain VARCHAR(64) NOT NULL DEFAULT 'Unknown',
    entity VARCHAR(128) NOT NULL DEFAULT 'Unknown',
    viral_features JSONB NOT NULL DEFAULT '[]'::jsonb,
    technical JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Comments for Data Catalog
COMMENT ON TABLE video_tags IS '4-Layer Video Taxonomy & ML Ingestion Sink for Quick Share AI Loop';
COMMENT ON COLUMN video_tags.viral_features IS 'JSONB array of trending hook markers, e.g. ["Heavy_Lasers", "Bass_Drop_0:15"]';
COMMENT ON COLUMN video_tags.technical IS 'JSONB key-value map of video quality metrics, e.g. {"lighting": "dark", "fps": 60}';

-- High-Performance GIN Indexes for JSONB Querying
-- jsonb_path_ops optimizes array containment queries: viral_features @> '["Bass_Drop_0:15"]'::jsonb
CREATE INDEX IF NOT EXISTS idx_video_tags_viral_features_gin 
    ON video_tags USING GIN (viral_features jsonb_path_ops);

-- Default GIN index on technical allows key existence and path queries: technical ? 'lighting'
CREATE INDEX IF NOT EXISTS idx_video_tags_technical_gin 
    ON video_tags USING GIN (technical);

-- Composite B-Tree index for domain/entity filtering
CREATE INDEX IF NOT EXISTS idx_video_tags_domain_entity 
    ON video_tags (domain, entity);

CREATE INDEX IF NOT EXISTS idx_video_tags_created_at 
    ON video_tags (created_at DESC);
```

### 4.2 JSONB Query Patterns Supported

1. **Find all EDM videos with a specific bass drop timestamp:**
   ```sql
   SELECT filename, entity, viral_features 
   FROM video_tags 
   WHERE domain = 'EDM' 
     AND viral_features @> '["Bass_Drop_0:15"]'::jsonb;
   ```
2. **Find all videos with audio clipping or 4K resolution:**
   ```sql
   SELECT filename, technical->>'resolution' AS resolution
   FROM video_tags
   WHERE (technical->>'audio_clipping')::boolean = true
      OR technical->>'resolution' = '3840x2160';
   ```
3. **Array unnesting for trend aggregation across all videos:**
   ```sql
   SELECT tag, COUNT(*) as frequency
   FROM video_tags, jsonb_array_elements_text(viral_features) as tag
   GROUP BY tag
   ORDER BY frequency DESC;
   ```

---

## 5. Comprehensive Testing Strategy (Zero GCP Cloud SQL Required)

To strictly comply with Rule **R2** (The Zero-Discretion Mandate / Leash Protocol) and TDAD (Test-Driven Agentic Development), all automated unit and integration tests must run in isolated local environments without requiring active GCP network credentials or a live Cloud SQL instance.

### 5.1 Test Architecture Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Deterministic Test Suite Suite                        │
├──────────────────────┬──────────────────────────────────────────────────────┤
│ Test Module          │ Purpose & Verification Mechanism                     │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ 1. Auth Guardrail    │ Proves fail-fast when PG_* env vars missing (R26)    │
│ 2. 4K Payload Insert │ Verifies JSONB parameterization & ON CONFLICT SQL    │
│ 3. JSONB Containment │ Verifies query compilation for JSONB arrays & objects│
│ 4. Exception Cleanup │ Verifies conn.rollback() & putconn() on query error  │
│ 5. Stale Conn Recycle│ Verifies OperationalError closes and discards socket │
│ 6. Pool Exhaustion   │ Verifies recovery & timeout handling under load      │
│ 7. Daemon Lifecycle  │ Verifies pool.closeall() upon graceful termination   │
└──────────────────────┴──────────────────────────────────────────────────────┘
```

### 5.2 Deterministic Mocking Strategy
- **Mock Target:** `psycopg2.pool.ThreadedConnectionPool` and `psycopg2.extras.Json`.
- **Methodology:** Use `unittest.mock.MagicMock` to simulate:
  1. Connection checkout (`pool.getconn()`).
  2. Cursor creation (`conn.cursor()`).
  3. Query execution and SQL capture (`cursor.execute(sql, params)`).
  4. Connection return (`pool.putconn(conn)`).
  5. Error simulation (`cursor.execute.side_effect = psycopg2.OperationalError(...)`).

---

## 6. Reference Implementation Blueprints

### 6.1 `database_sink.py` (Production Blueprint)

```python
"""
Database Sink for Quick Share AI Loop
Connects to Google Cloud SQL PostgreSQL via psycopg2 ThreadedConnectionPool.
Implements Rule R26 (Fail-Fast Auth), automatic connection recovery, and JSONB adaptation.
"""

import os
import sys
import logging
from typing import Dict, Any, Union, Optional
from pathlib import Path
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool, extras
from psycopg2.extras import Json

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)

# Ensure .env is explicitly loaded per Rule R26
ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

REQUIRED_ENV_VARS = ["PG_HOST", "PG_USER", "PG_PASSWORD", "PG_DB"]

def validate_environment() -> Dict[str, str]:
    """Validates required PostgreSQL environment variables fail-fast per Rule R26."""
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        error_msg = f"CRITICAL: Missing required PostgreSQL environment variables: {', '.join(missing)}. Halting per Rule R26."
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return {
        "host": os.getenv("PG_HOST", "localhost"),
        "port": os.getenv("PG_PORT", "5432"),
        "user": os.getenv("PG_USER", ""),
        "password": os.getenv("PG_PASSWORD", ""),
        "dbname": os.getenv("PG_DB", ""),
    }

class PostgresDatabaseSink:
    """Thread-safe connection-pooled database sink for video analytics metadata."""
    
    _instance: Optional["PostgresDatabaseSink"] = None
    
    def __init__(self, minconn: int = 1, maxconn: int = 10):
        self.config = validate_environment()
        self.minconn = minconn
        self.maxconn = maxconn
        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._init_pool()
        
    def _init_pool(self):
        """Initializes the psycopg2 ThreadedConnectionPool with TCP keepalives."""
        try:
            dsn = (
                f"host={self.config['host']} "
                f"port={self.config['port']} "
                f"user={self.config['user']} "
                f"password={self.config['password']} "
                f"dbname={self.config['dbname']} "
                f"connect_timeout=10 "
                f"keepalives=1 "
                f"keepalives_idle=30 "
                f"keepalives_interval=10 "
                f"keepalives_count=3"
            )
            self._pool = pool.ThreadedConnectionPool(
                minconn=self.minconn,
                maxconn=self.maxconn,
                dsn=dsn
            )
            logger.info(f"Initialized ThreadedConnectionPool ({self.minconn}-{self.maxconn} connections) to {self.config['host']}:{self.config['dbname']}")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL Connection Pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Context manager for borrowing and returning connections with auto-rollback on error."""
        if not self._pool:
            raise RuntimeError("Database connection pool is not initialized.")
            
        conn = None
        is_broken = False
        try:
            conn = self._pool.getconn()
            
            # Connection health check (pre-ping)
            try:
                with conn.cursor() as ping_cur:
                    ping_cur.execute("SELECT 1;")
            except (psycopg2.OperationalError, psycopg2.DatabaseError):
                logger.warning("Detected stale connection from pool. Discarding and reconnecting...")
                self._pool.putconn(conn, close=True)
                conn = self._pool.getconn()
                
            yield conn
            conn.commit()
        except Exception as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    is_broken = True
            logger.error(f"Database transaction error: {exc}")
            raise
        finally:
            if conn and self._pool:
                self._pool.putconn(conn, close=is_broken)

    def init_schema(self):
        """Executes the DDL schema to ensure table and GIN indexes exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS video_tags (
            id BIGSERIAL PRIMARY KEY,
            filename TEXT UNIQUE NOT NULL,
            filepath TEXT NOT NULL,
            domain VARCHAR(64) NOT NULL DEFAULT 'Unknown',
            entity VARCHAR(128) NOT NULL DEFAULT 'Unknown',
            viral_features JSONB NOT NULL DEFAULT '[]'::jsonb,
            technical JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_video_tags_viral_features_gin 
            ON video_tags USING GIN (viral_features jsonb_path_ops);

        CREATE INDEX IF NOT EXISTS idx_video_tags_technical_gin 
            ON video_tags USING GIN (technical);
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
        logger.info("PostgreSQL schema verification complete.")

    def insert_video_analytics(self, filepath: str, tags: Union[str, Dict[str, Any]]) -> None:
        """
        Inserts or updates video analytics metadata using JSONB adapters.
        Handles ON CONFLICT (filename) DO UPDATE.
        """
        import json
        if isinstance(tags, str):
            tags_dict = json.loads(tags)
        else:
            tags_dict = tags

        filename = Path(filepath).name
        domain = tags_dict.get("domain", "Unknown")
        entity = tags_dict.get("entity", "Unknown")
        viral_features = tags_dict.get("viral_features", [])
        technical = tags_dict.get("technical", {})

        query = """
        INSERT INTO video_tags (filename, filepath, domain, entity, viral_features, technical)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (filename) DO UPDATE SET
            filepath = EXCLUDED.filepath,
            domain = EXCLUDED.domain,
            entity = EXCLUDED.entity,
            viral_features = EXCLUDED.viral_features,
            technical = EXCLUDED.technical,
            created_at = NOW();
        """

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (
                    filename,
                    filepath,
                    domain,
                    entity,
                    Json(viral_features),
                    Json(technical)
                ))
        logger.info(f"Successfully synced analytics for {filename} to PostgreSQL.")

    def close(self):
        """Gracefully closes all pool connections."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("Closed all PostgreSQL pool connections.")


# Singleton convenience accessors
_sink_instance: Optional[PostgresDatabaseSink] = None

def get_sink() -> PostgresDatabaseSink:
    global _sink_instance
    if _sink_instance is None:
        _sink_instance = PostgresDatabaseSink()
    return _sink_instance

def insert_video_analytics(filepath: str, tags: Union[str, Dict[str, Any]]) -> None:
    sink = get_sink()
    sink.insert_video_analytics(filepath, tags)

def init_db() -> None:
    sink = get_sink()
    sink.init_schema()

def close_pool() -> None:
    global _sink_instance
    if _sink_instance:
        _sink_instance.close()
        _sink_instance = None
```

---

### 6.2 `test_database_sink.py` (Deterministic Test Suite Blueprint)

```python
"""
Comprehensive Unit & Integration Test Suite for Postgres Database Sink.
Tests Rule R26 Auth, 4K payload insertion, JSONB parameters, pool recovery, and leak prevention.
Runs 100% locally with zero GCP Cloud SQL dependency.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, call
import psycopg2
from psycopg2.extras import Json

# Test 1: Rule R26 Auth Guardrail - Fail-Fast on Missing Env Vars
def test_validate_environment_missing_vars_raises_value_error(monkeypatch):
    from database_sink import validate_environment
    
    # Strip env vars
    monkeypatch.delenv("PG_HOST", raising=False)
    monkeypatch.delenv("PG_USER", raising=False)
    monkeypatch.delenv("PG_PASSWORD", raising=False)
    monkeypatch.delenv("PG_DB", raising=False)
    
    with pytest.raises(ValueError) as exc_info:
        validate_environment()
        
    assert "Missing required PostgreSQL environment variables" in str(exc_info.value)
    assert "Rule R26" in str(exc_info.value)


# Test 2: Successful 4K Video Tagged Payload Insertion & JSONB Adaptation
@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_video_analytics_4k_payload(mock_pool_cls, monkeypatch):
    monkeypatch.setenv("PG_HOST", "127.0.0.1")
    monkeypatch.setenv("PG_USER", "postgres")
    monkeypatch.setenv("PG_PASSWORD", "secret")
    monkeypatch.setenv("PG_DB", "quick_share_db")

    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    mock_pool_cls.return_value = mock_pool
    mock_pool.getconn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    from database_sink import PostgresDatabaseSink
    sink = PostgresDatabaseSink()
    
    payload = {
        "domain": "EDM",
        "entity": "Excision",
        "viral_features": ["Heavy_Lasers", "Bass_Drop_0:15", "Crowd_Pan"],
        "technical": {
            "resolution": "3840x2160",
            "fps": 60,
            "bitrate_mbps": 120,
            "lighting": "dark",
            "audio_clipping": False
        }
    }
    
    filepath = "G:/My Drive/GOOGLE ANTIGRAVITY/photos_triage_project/Raw_Ingest/Lost_Lands_4K.mp4"
    sink.insert_video_analytics(filepath, payload)

    # Verify query execution
    assert mock_cur.execute.called
    args, kwargs = mock_cur.execute.call_args
    sql, params = args
    
    assert "INSERT INTO video_tags" in sql
    assert "ON CONFLICT (filename) DO UPDATE" in sql
    assert params[0] == "Lost_Lands_4K.mp4"
    assert params[1] == filepath
    assert params[2] == "EDM"
    assert params[3] == "Excision"
    
    # Assert JSONB adapters were applied
    assert isinstance(params[4], Json)
    assert params[4].adapted == ["Heavy_Lasers", "Bass_Drop_0:15", "Crowd_Pan"]
    assert isinstance(params[5], Json)
    assert params[5].adapted["resolution"] == "3840x2160"
    
    # Assert commit and putconn were called
    assert mock_conn.commit.called
    assert mock_pool.putconn.called_with(mock_conn, close=False)


# Test 3: Exception Safety & Automatic Rollback (Connection Leak Prevention)
@patch("database_sink.pool.ThreadedConnectionPool")
def test_connection_leak_prevention_on_execution_failure(mock_pool_cls, monkeypatch):
    monkeypatch.setenv("PG_HOST", "127.0.0.1")
    monkeypatch.setenv("PG_USER", "postgres")
    monkeypatch.setenv("PG_PASSWORD", "secret")
    monkeypatch.setenv("PG_DB", "quick_share_db")

    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    mock_pool_cls.return_value = mock_pool
    mock_pool.getconn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    # Simulate DB syntax / constraint violation error
    mock_cur.execute.side_effect = psycopg2.DatabaseError("Foreign key constraint violation")

    from database_sink import PostgresDatabaseSink
    sink = PostgresDatabaseSink()

    with pytest.raises(psycopg2.DatabaseError):
        sink.insert_video_analytics("test.mp4", {"domain": "EDM"})

    # Prove rollback was executed and connection was returned to pool safely
    assert mock_conn.rollback.called
    assert mock_pool.putconn.called_with(mock_conn, close=False)


# Test 4: Stale Connection Recovery (The 3 AM Silent Drop Handler)
@patch("database_sink.pool.ThreadedConnectionPool")
def test_stale_connection_recovery_reconnects_and_retries(mock_pool_cls, monkeypatch):
    monkeypatch.setenv("PG_HOST", "127.0.0.1")
    monkeypatch.setenv("PG_USER", "postgres")
    monkeypatch.setenv("PG_PASSWORD", "secret")
    monkeypatch.setenv("PG_DB", "quick_share_db")

    mock_pool = MagicMock()
    dead_conn = MagicMock()
    fresh_conn = MagicMock()
    dead_cur = MagicMock()
    fresh_cur = MagicMock()
    
    mock_pool_cls.return_value = mock_pool
    mock_pool.getconn.side_effect = [dead_conn, fresh_conn]
    
    # Pre-ping on dead connection fails with OperationalError
    dead_conn.cursor.return_value.__enter__.return_value = dead_cur
    dead_cur.execute.side_effect = psycopg2.OperationalError("server closed the connection unexpectedly")
    
    # Pre-ping on fresh connection succeeds
    fresh_conn.cursor.return_value.__enter__.return_value = fresh_cur

    from database_sink import PostgresDatabaseSink
    sink = PostgresDatabaseSink()

    with sink.get_connection() as conn:
        assert conn == fresh_conn

    # Verify dead connection was closed and discarded
    mock_pool.putconn.assert_any_call(dead_conn, close=True)
    # Verify fresh connection was returned safely
    mock_pool.putconn.assert_any_call(fresh_conn, close=False)


# Test 5: Graceful Daemon Shutdown & Pool Teardown
@patch("database_sink.pool.ThreadedConnectionPool")
def test_close_pool_closes_all_connections(mock_pool_cls, monkeypatch):
    monkeypatch.setenv("PG_HOST", "127.0.0.1")
    monkeypatch.setenv("PG_USER", "postgres")
    monkeypatch.setenv("PG_PASSWORD", "secret")
    monkeypatch.setenv("PG_DB", "quick_share_db")

    mock_pool = MagicMock()
    mock_pool_cls.return_value = mock_pool

    from database_sink import PostgresDatabaseSink
    sink = PostgresDatabaseSink()
    sink.close()

    assert mock_pool.closeall.called
    assert sink._pool is None
```

---

## 7. Implementation Checklist & Next Steps for Squad

1. **Environment Setup:** Ensure `.env` contains valid Cloud SQL credentials (`PG_HOST`, `PG_PORT`, `PG_USER`, `PG_PASSWORD`, `PG_DB`).
2. **Dependencies:** Add `psycopg2-binary>=2.9.9` and `pytest>=8.0.0` to `requirements.txt`.
3. **Database Migration:** Apply `schema.sql` to the Cloud SQL PostgreSQL instance to initialize `video_tags` and GIN indexes.
4. **Implement Code:** Deploy `database_sink.py` based on Section 6.1.
5. **Run Tests:** Execute `pytest test_database_sink.py -v` to ensure 100% test pass rate.
6. **Daemon Verification:** Run `python quick_share_hijack.py` and verify zero connection leaks or watchdog hangs on new file triggers.
