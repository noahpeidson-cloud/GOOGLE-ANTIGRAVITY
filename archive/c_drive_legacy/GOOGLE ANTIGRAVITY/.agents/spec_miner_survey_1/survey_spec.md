# Comprehensive Specification Report: Quick Share AI Loop PostgreSQL Migration

## Executive Summary
This document provides the authoritative, exhaustive technical specification for migrating the **Quick Share AI Loop** database layer from local SQLite (`media_analytics.db`) to **Google Cloud SQL PostgreSQL** and **Firebase Data Connect (SQL Connect)**.

The migration encompasses:
1. **R1**: Database sink refactoring (`database_sink.py`) with thread-safe connection pooling (`psycopg2.pool.ThreadedConnectionPool`), connection lifecycle management, and upsert handling.
2. **R2**: PostgreSQL DDL (`schema.sql`) and Firebase Data Connect GraphQL schema (`schema.gql`) utilizing native `JSONB` for `viral_features` and `technical` metadata.
3. **R3**: Fail-fast secret management and environment variable validation adhering to **Workspace Rule R26** (The Background Daemon Auth Guardrail).
4. **R4**: Connection leak prevention, concurrency safety, and idle socket recovery for long-running watchdog daemons.
5. **Data Contracts & Migration**: End-to-end schema mapping, 4-layer taxonomy contract, backfill tooling, and test verification suite.

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Database Sink | `get_db_config()` | Validates and returns PostgreSQL connection configuration from environment variables. | Environment variables (`PG_HOST`, `PG_PORT`, `PG_USER`, `PG_PASSWORD`, `PG_DB`, `PG_SSLMODE`, etc.) | `dict` containing validated DB parameters | Raises `ValueError` or `KeyError` with actionable message if required env vars are missing/invalid | `database_sink.py`, `GEMINI.md` Rule R26 |
| 2 | Database Sink | `get_connection_pool()` | Thread-safe singleton connection pool using `psycopg2.pool.ThreadedConnectionPool`. | Config dictionary from `get_db_config()` | Initialized `ThreadedConnectionPool` instance | Raises `psycopg2.OperationalError` if connection to PostgreSQL host fails | `database_sink.py`, watchdog threading architecture |
| 3 | Database Sink | `get_db_connection()` (Context Manager) | Safe connection checkout and checkin wrapper ensuring connections are returned to the pool even on failure. | `ThreadedConnectionPool` | Yields active `psycopg2.extensions.connection` | Catches exceptions, rolls back active transaction, returns connection to pool, re-raises exception | Architecture Red Team Audit, `database_sink.py` |
| 4 | Database Sink | `init_db()` | Initializes PostgreSQL table `video_tags` and GIN/B-tree indexes if they do not exist. | Active connection from pool | `None` (table & indexes created) | Raises `psycopg2.DatabaseError` on DDL syntax or permission failure | `database_sink.py:init_db` |
| 5 | Database Sink | `insert_video_analytics()` | Inserts or updates video tagging metadata in PostgreSQL `video_tags` table using `JSONB` fields. | `filepath` (str), `tags_json` (str or dict) | `None` (row inserted or updated) | Raises `psycopg2.Error` or `ValueError` on malformed payload or DB failure; automatically rolls back | `database_sink.py:insert_video_analytics` |
| 6 | Database Sink | `close_pool()` | Gracefully closes all connections in the pool upon daemon shutdown. | None | `None` (all pool sockets closed) | Logs warning if closing already-closed pool | `quick_share_hijack.py`, `atexit` lifecycle |
| 7 | Schema | PostgreSQL DDL (`schema.sql`) | Production SQL schema definition for `video_tags` table with `JSONB` columns and GIN indexes. | SQL script executed via `psql` or `init_db()` | Relational table and indexes created in Cloud SQL | Fails on PostgreSQL syntax or type mismatch | `ORIGINAL_REQUEST.md`, SQLite schema probe |
| 8 | Schema | Firebase Data Connect Schema (`schema.gql`) | GraphQL schema definition with `@table`, `@col`, and `@default` directives for Firebase SQL Connect. | `schema.gql` file | Compiled Firebase Data Connect schema | Fails during `firebase dataconnect:compile` if syntax or types invalid | `firebase-data-connect` SKILL.md |
| 9 | Schema | Firebase Data Connect Config (`dataconnect.yaml`) | Service configuration mapping Data Connect to Cloud SQL PostgreSQL instance. | `dataconnect.yaml` configuration | Service definition for deployment | Fails on invalid service ID or instance ID | `firebase-data-connect` SKILL.md |
| 10 | Schema | Firebase Data Connect Connector (`connector.yaml`, `mutations.gql`, `queries.gql`) | Type-safe SDK generation, GraphQL queries, and mutations for `video_tags`. | GraphQL operation documents | Generated TypeScript / Kotlin / Swift SDKs | Fails during compilation if operations violate schema types | `firebase-data-connect` SKILL.md |
| 11 | Auth & Secrets | Fail-Fast Env Validation (Rule R26) | Enforces presence of `.env` and all DB credentials at startup before daemon starts event loop. | Local `.env` file | Boolean success or immediate process termination | Exits process with code 1 and loud descriptive error; prevents silent failures | `GEMINI.md` Rule R26 |
| 12 | Concurrency & Anti-Leak | Lazy Connection Checkout | Connection is held ONLY during the microsecond SQL query execution, not during FFmpeg or Gemini API calls. | Event lifecycle | Minimized connection hold time (<10ms) | Prevents Cloud SQL connection pool exhaustion during long AI inference turns | Architecture Red Team Audit |
| 13 | Concurrency & Anti-Leak | Idle Socket & TCP Keepalive Recovery | Detects stale or severed Cloud SQL connections and refreshes the connection pool. | `conn.closed` check / `SELECT 1` ping | Valid active connection | Automatically drops bad connection (`putconn(close=True)`) and creates fresh socket | Cloud SQL Proxy & TCP timeout specs |
| 14 | Migration Tooling | `migrate_sqlite_to_postgres.py` | Standalone backfill script reading all records from `media_analytics.db` and sinking into PostgreSQL. | SQLite DB file, PostgreSQL connection | Count of migrated rows, verification status | Reports mismatched rows and rolls back batch on fatal error | Workspace SQLite schema inspection |
| 15 | Testing & TDAD | Mock PostgreSQL Test Suite (`test_database_sink.py`) | Deterministic unit and integration tests using `unittest.mock` and/or live test DB for loud assertions. | Mock connection & cursor / test DB | Test pass/fail status | Loud assertion failure on unhandled leak or schema mismatch | `GEMINI.md` Rule R2 (TDAD & Loud Assertions) |

---

## Edge Cases

| # | Feature | Input / Condition | Observed / Required Behavior |
|---|---------|-------------------|------------------------------|
| 1 | `get_db_config()` | `PG_PORT` provided as string with whitespace (e.g., `" 5432 "`) or missing. | Strip whitespace, cast to integer; default to `5432` if empty. If non-numeric string (e.g. `"abc"`), raise `ValueError`. |
| 2 | `get_db_config()` | Missing `PG_PASSWORD` or `PG_HOST` in `.env`. | Raise `ValueError("CRITICAL: Missing required environment variable 'PG_HOST' / 'PG_PASSWORD' in .env. Adhering to Rule R26, halting execution.")`. |
| 3 | `insert_video_analytics()` | `tags_json` passed as Python `dict` instead of JSON string. | Accept directly without double serialization. Pass `viral_features` list and `technical` dict to `psycopg2.extras.Json`. |
| 4 | `insert_video_analytics()` | `tags_json` passed as malformed JSON string (e.g., `"{bad_json"`). | Catch `json.JSONDecodeError`, raise descriptive `ValueError` or fallback gracefully to default taxonomy, preventing unhandled crash of the watchdog daemon. |
| 5 | `insert_video_analytics()` | `viral_features` missing or `None` in `tags_json`. | Default to empty Python list `[]` (inserted as `[]`::jsonb in PostgreSQL). |
| 6 | `insert_video_analytics()` | `technical` missing or `None` in `tags_json`. | Default to empty Python dict `{}` (inserted as `{}`::jsonb in PostgreSQL). |
| 7 | `insert_video_analytics()` | Duplicate `filename` inserted (e.g., re-running tagger on same video). | PostgreSQL executes `ON CONFLICT (filename) DO UPDATE SET filepath = EXCLUDED.filepath, domain = EXCLUDED.domain, entity = EXCLUDED.entity, viral_features = EXCLUDED.viral_features, technical = EXCLUDED.technical, created_at = CURRENT_TIMESTAMP`. No duplicate key error. |
| 8 | `insert_video_analytics()` | `filepath` contains backslashes on Windows (e.g., `C:\Users\noahp\...`). | Correctly escape and store verbatim text without mangling escape sequences. |
| 9 | `get_db_connection()` | Cloud SQL drops connection due to 15-minute idle timeout while watchdog waits for a file. | When connection is checked out, perform `conn.poll()` or lightweight ping (`SELECT 1`). If `OperationalError` or connection is closed, discard connection with `pool.putconn(conn, close=True)`, establish new connection, and continue. |
| 10 | `get_connection_pool()` | Multiple concurrent threads trigger file ingest in `quick_share_hijack.py`. | `ThreadedConnectionPool` manages thread-safe checkout with mutex lock. If pool limit reached (`maxconn`), request blocks up to timeout or raises pool exhaustion error. |
| 11 | `close_pool()` | Daemon terminated via `Ctrl+C` (KeyboardInterrupt) or `SIGTERM`. | `atexit` handler and `try...finally` block in `quick_share_hijack.py` invoke `database_sink.close_pool()`, cleanly closing all open pool sockets. |
| 12 | `migrate_sqlite_to_postgres.py` | SQLite row contains legacy stringified JSON: `'["Laser_Show"]'`. | Parse with `json.loads()`, wrap in `psycopg2.extras.Json`, and insert into PostgreSQL `JSONB` column. |

---

## Detailed Technical Specifications

### 1. Architectural Overview & Context

```
+-----------------------------------------------------------------------------------+
|                           Quick Share AI Loop Daemon                              |
|                                                                                   |
|  +---------------------------+        +----------------------------------------+  |
|  |  quick_share_hijack.py    | -----> |  gemini_tagger.py (Gemini 3.6 Flash)   |  |
|  |  (Watchdog Observer)      |        |  (FFmpeg Proxy + Multimodal Inference) |  |
|  +---------------------------+        +----------------------------------------+  |
|                |                                          |                       |
|                |                                          v                       |
|                |                       +---------------------------------------+  |
|                +---------------------> |  database_sink.py                     |  |
|                                        |  (psycopg2.pool.ThreadedConnectionPool|  |
|                                        +---------------------------------------+  |
|                                                           |                       |
+-----------------------------------------------------------|-----------------------+
                                                            v
                        +-------------------------------------------------------+
                        | Google Cloud SQL PostgreSQL / Firebase Data Connect   |
                        | Table: video_tags                                     |
                        | Columns: id, filename, filepath, domain, entity,      |
                        |          viral_features (JSONB), technical (JSONB),   |
                        |          created_at (TIMESTAMPTZ)                     |
                        +-------------------------------------------------------+
```

---

### 2. Requirement R1: `database_sink.py` Specification

#### 2.1 Dependencies
- `psycopg2-binary` >= 2.9.9
- `python-dotenv` >= 1.0.0

#### 2.2 Environment Variables Specification
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PG_HOST` | **YES** | None | Hostname or IP of PostgreSQL / Cloud SQL Proxy (e.g., `127.0.0.1`, `localhost`). |
| `PG_PORT` | NO | `5432` | Port for PostgreSQL instance. |
| `PG_USER` | **YES** | None | Database username (e.g., `postgres`). |
| `PG_PASSWORD` | **YES** | None | Database user password. |
| `PG_DB` | **YES** | None | Database name (e.g., `media_analytics` or `quick_share_ai`). |
| `PG_SSLMODE` | NO | `prefer` | SSL Mode (`disable`, `allow`, `prefer`, `require`, `verify-ca`, `verify-full`). |
| `PG_MIN_CONN` | NO | `1` | Minimum connections in pool. |
| `PG_MAX_CONN` | NO | `10` | Maximum connections in pool. |
| `PG_CONNECT_TIMEOUT` | NO | `10` | Connection timeout in seconds. |

#### 2.3 Interface Signatures & Contracts

```python
"""
database_sink.py - PostgreSQL Data Sink for Quick Share AI Loop
"""
import os
import json
import logging
from pathlib import Path
from typing import Union, Dict, Any, Optional
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool, extras

logger = logging.getLogger(__name__)

# Global singleton connection pool
_CONNECTION_POOL: Optional[pool.ThreadedConnectionPool] = None

def get_db_config() -> Dict[str, Any]:
    """
    Loads and validates PostgreSQL configuration from .env adhering to Rule R26.
    Fails fast if mandatory keys are missing.
    """
    ...

def get_connection_pool() -> pool.ThreadedConnectionPool:
    """
    Initializes or returns the thread-safe singleton connection pool.
    """
    ...

@contextmanager
def get_db_connection():
    """
    Context manager for checking out and returning connections to the pool.
    Guarantees connection return on error and rolls back uncommitted transactions.
    """
    ...

def init_db() -> None:
    """
    Initializes the PostgreSQL database schema (creates video_tags table and indexes).
    """
    ...

def insert_video_analytics(filepath: str, tags_json: Union[str, Dict[str, Any]]) -> None:
    """
    Inserts or updates video metadata into PostgreSQL video_tags using JSONB serialization.
    """
    ...

def close_pool() -> None:
    """
    Closes all active connections in the connection pool during daemon shutdown.
    """
    ...
```

#### 2.4 SQL Upsert Query Contract
```sql
INSERT INTO video_tags (
    filename,
    filepath,
    domain,
    entity,
    viral_features,
    technical,
    created_at
) VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    CURRENT_TIMESTAMP
)
ON CONFLICT (filename) DO UPDATE SET
    filepath = EXCLUDED.filepath,
    domain = EXCLUDED.domain,
    entity = EXCLUDED.entity,
    viral_features = EXCLUDED.viral_features,
    technical = EXCLUDED.technical,
    created_at = CURRENT_TIMESTAMP;
```

---

### 3. Requirement R2: Database Schemas

#### 3.1 PostgreSQL DDL (`schema.sql`)
```sql
-- =============================================================================
-- Quick Share AI Loop PostgreSQL Schema
-- Target: Google Cloud SQL for PostgreSQL / Local PostgreSQL 14+
-- =============================================================================

CREATE TABLE IF NOT EXISTS video_tags (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(512) NOT NULL UNIQUE,
    filepath TEXT NOT NULL,
    domain VARCHAR(100) NOT NULL DEFAULT 'Unknown',
    entity VARCHAR(255) NOT NULL DEFAULT 'Unknown',
    viral_features JSONB NOT NULL DEFAULT '[]'::jsonb,
    technical JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Comments for schema documentation
COMMENT ON TABLE video_tags IS 'Video tagging metadata generated by Gemini 3.6 Flash multimodal inference.';
COMMENT ON COLUMN video_tags.filename IS 'Unique filename of the video.';
COMMENT ON COLUMN video_tags.filepath IS 'Original or ingested absolute path of the video.';
COMMENT ON COLUMN video_tags.domain IS 'High-level category taxonomy (e.g., EDM, Sports Cards, Travel).';
COMMENT ON COLUMN video_tags.entity IS 'Specific subject entity (e.g., Excision, Victor Wembanyama).';
COMMENT ON COLUMN video_tags.viral_features IS 'JSONB array of strings detailing viral hooks (e.g., ["Heavy_Lasers", "Bass_Drop_0:15"]).';
COMMENT ON COLUMN video_tags.technical IS 'JSONB object containing video quality and capture metrics.';
COMMENT ON COLUMN video_tags.created_at IS 'UTC timestamp of record creation or update.';

-- Performance & Query Indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_video_tags_filename ON video_tags (filename);
CREATE INDEX IF NOT EXISTS idx_video_tags_domain ON video_tags (domain);
CREATE INDEX IF NOT EXISTS idx_video_tags_entity ON video_tags (entity);
CREATE INDEX IF NOT EXISTS idx_video_tags_viral_features_gin ON video_tags USING gin (viral_features);
CREATE INDEX IF NOT EXISTS idx_video_tags_technical_gin ON video_tags USING gin (technical);
CREATE INDEX IF NOT EXISTS idx_video_tags_created_at ON video_tags (created_at DESC);
```

#### 3.2 Firebase Data Connect Schema (`dataconnect/schema/schema.gql`)
```graphql
# =============================================================================
# Firebase SQL Connect GraphQL Schema
# Service: quick-share-analytics
# =============================================================================

type VideoTag @table(name: "video_tags", key: "id", singular: "videoTag", plural: "videoTags") {
  id: UUID! @default(expr: "uuidV4()")
  filename: String! @unique
  filepath: String!
  domain: String! @default(value: "Unknown")
  entity: String! @default(value: "Unknown")
  viralFeatures: Any! @col(name: "viral_features", dataType: "jsonb") @default(value: [])
  technical: Any! @col(name: "technical", dataType: "jsonb") @default(value: {})
  createdAt: Timestamp! @col(name: "created_at") @default(expr: "request.time")
}
```

#### 3.3 Firebase Data Connect Service Configuration (`dataconnect/dataconnect.yaml`)
```yaml
specVersion: "v1alpha"
serviceId: "quick-share-analytics"
location: "us-central1"
schema:
  source: "./schema"
  datasource:
    postgresql:
      database: "media_analytics"
      cloudSql:
        instanceId: "quick-share-postgres-instance"
connectorDirs: ["./connector"]
```

#### 3.4 Firebase Data Connect Connector Configuration (`dataconnect/connector/connector.yaml`)
```yaml
connectorId: "video-analytics-connector"
generate:
  javascriptSdk:
    outputDir: "../dashboard/src/lib/dataconnect"
    package: "@quickshare/dataconnect"
```

#### 3.5 Firebase Data Connect Operations (`dataconnect/connector/mutations.gql` & `queries.gql`)
```graphql
# dataconnect/connector/mutations.gql
mutation UpsertVideoTag(
  $filename: String!
  $filepath: String!
  $domain: String!
  $entity: String!
  $viralFeatures: Any!
  $technical: Any!
) @auth(level: NO_ACCESS) {
  videoTag_upsert(
    data: {
      filename: $filename
      filepath: $filepath
      domain: $domain
      entity: $entity
      viralFeatures: $viralFeatures
      technical: $technical
    }
  )
}

# dataconnect/connector/queries.gql
query ListVideoTagsByDomain($domain: String!, $limit: Int = 50) @auth(level: PUBLIC) {
  videoTags(
    where: { domain: { eq: $domain } }
    limit: $limit
    orderBy: [{ createdAt: DESC }]
  ) {
    id
    filename
    filepath
    domain
    entity
    viralFeatures
    technical
    createdAt
  }
}

query GetVideoTagByFilename($filename: String!) @auth(level: PUBLIC) {
  videoTags(where: { filename: { eq: $filename } }) {
    id
    filename
    filepath
    domain
    entity
    viralFeatures
    technical
    createdAt
  }
}
```

---

### 4. Requirement R3: Secret Management & Rule R26 Guardrail Specification

#### 4.1 Workspace Rule R26 Compliance
- **Rule Statement**: When spawning long-running Python background scripts or daemons that require external service access, agents must not assume the script inherits IDE proxy auth or global environment variables.
- **Fail-Fast Protocol**:
  1. The `.env` file MUST exist in the project working directory (`quick_share_ai_loop/.env`).
  2. `load_dotenv()` MUST be called explicitly at top of file before accessing `os.environ`.
  3. The `get_db_config()` function checks for all required keys:
     - `PG_HOST`
     - `PG_USER`
     - `PG_PASSWORD`
     - `PG_DB`
  4. If any key is missing or is an empty string, the process immediately raises a fatal `ValueError` with clear remediation instructions:
     ```python
     missing = [k for k in ['PG_HOST', 'PG_USER', 'PG_PASSWORD', 'PG_DB'] if not os.getenv(k)]
     if missing:
         raise ValueError(
             f"FATAL: Missing required PostgreSQL environment variables in .env: {missing}. "
             f"Adhering to Workspace Rule R26 (The Background Daemon Auth Guardrail), "
             f"the pipeline is halted immediately to prevent silent data loss."
         )
     ```
  5. Password sanitization: Error logs and status outputs MUST sanitize `PG_PASSWORD` (e.g. `postgresql://user:***@host:port/dbname`).

#### 4.2 `.env` Template Specification (`quick_share_ai_loop/.env.example`)
```env
# Gemini API Key for Multimodal Inference
GEMINI_API_KEY=your_gemini_api_key_here

# PostgreSQL / Google Cloud SQL Connection Parameters
PG_HOST=127.0.0.1
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=your_secure_password_here
PG_DB=media_analytics
PG_SSLMODE=prefer
PG_MIN_CONN=1
PG_MAX_CONN=10
PG_CONNECT_TIMEOUT=10
```

---

### 5. Requirement R4: Architecture Red Team Audit & Anti-Leak Patterns

#### 5.1 Red Team Flaw Analysis

| # | Vulnerability / Flaw | Mechanism | Red Team Severity | Required Mitigation |
|---|----------------------|-----------|-------------------|---------------------|
| 1 | **Connection Hoarding during AI Inference** | If a connection is checked out when `on_created` fires in `quick_share_hijack.py`, the connection sits idle during FFmpeg proxy generation (5-30s) and Gemini API call (10-60s). If 5 files drop at once, 5 connections are locked, exhausting Cloud SQL pool slots. | **CRITICAL** | **Micro-Checkout Pattern**: Do not check out a DB connection during file wait, FFmpeg, or Gemini inference. Acquire the connection strictly inside `insert_video_analytics()`, perform the query, and release it immediately in `<10ms`. |
| 2 | **Thread Race Conditions in Watchdog** | `watchdog.observers.Observer` dispatches file events across internal thread pool. A standard `psycopg2.pool.SimpleConnectionPool` is not thread-safe and crashes under concurrent calls. | **HIGH** | Use `psycopg2.pool.ThreadedConnectionPool` with explicit thread safety. |
| 3 | **Cloud SQL Idle Socket Termination (Ghost Connections)** | Cloud SQL / TCP proxies terminate idle TCP connections after 10-15 minutes of inactivity. When `quick_share_hijack` is idle waiting for the next video, the pool's cached connections become stale. Executing a query causes `psycopg2.OperationalError: server closed the connection unexpectedly`. | **HIGH** | **Connection Liveness Verification**: In `get_db_connection()`, check `conn.closed` or execute a lightweight ping (`SELECT 1`). If dead, discard with `pool.putconn(conn, close=True)` and acquire/create a fresh connection. |
| 4 | **Connection Leaks on Unhandled Exceptions** | If `insert_video_analytics` encounters an exception (e.g., JSON decode error or DB timeout) without a `try...finally` block, the connection is never returned to the pool (`pool.putconn()`), causing cumulative pool exhaustion. | **HIGH** | Mandatory `try...finally` inside the `get_db_connection()` context manager to guarantee `pool.putconn(conn)` execution. |
| 5 | **Zombie Connections on Daemon Termination** | When daemon is stopped via `Ctrl+C` or task kill, open connections remain dangling on Cloud SQL server until backend timeout. | **MEDIUM** | Register `atexit.register(close_pool)` and signal handlers (`SIGINT`, `SIGTERM`) to invoke `close_pool()`. |

---

### 6. Data Contract & Taxonomy Specification

#### 6.1 The 4-Layer Taxonomy Contract
The payload produced by `gemini_tagger.py` and ingested by `database_sink.py` adheres to this exact contract:

```json
{
  "domain": "EDM",
  "entity": "Excision",
  "viral_features": [
    "Heavy_Lasers",
    "Bass_Drop_0:15",
    "Crowd_Pan",
    "Stage_Lighting",
    "Synchronized_Lights"
  ],
  "technical": {
    "lighting": "dynamic_lasers",
    "audio_clipping": false,
    "orientation": "vertical",
    "camera_stability": "handheld"
  }
}
```

#### 6.2 Data Field Specifications

| Field Name | SQLite Type | PostgreSQL Type | GraphQL Type | Nullable | Default | Description / Example |
|------------|-------------|-----------------|--------------|----------|---------|-----------------------|
| `id` | `INTEGER` | `SERIAL` (or `BIGSERIAL`) | `UUID!` / `Int!` | No | Auto-generated | Primary identifier. |
| `filename` | `TEXT` | `VARCHAR(512)` | `String!` | No | None | Unique filename (e.g. `20260819_212636.mp4`). |
| `filepath` | `TEXT` | `TEXT` | `String!` | No | None | Absolute path to media on host or G: Drive. |
| `domain` | `TEXT` | `VARCHAR(100)` | `String!` | No | `'Unknown'` | High-level category (`'EDM'`, `'Sports Cards'`, `'Travel'`). |
| `entity` | `TEXT` | `VARCHAR(255)` | `String!` | No | `'Unknown'` | Subject entity (`'Excision'`, `'Victor Wembanyama'`). |
| `viral_features` | `TEXT` (JSON) | `JSONB` | `Any!` (or `[String!]!`) | No | `'[]'::jsonb` | Array of trending hooks / key timestamps. |
| `technical` | `TEXT` (JSON) | `JSONB` | `Any!` | No | `'{}'::jsonb` | JSON object of camera, audio, and lighting metrics. |
| `created_at` | `TIMESTAMP` | `TIMESTAMPTZ` | `Timestamp!` | No | `CURRENT_TIMESTAMP` / `request.time` | UTC timestamp of record creation/update. |

---

### 7. SQLite to PostgreSQL Migration & Backfill Strategy

To seamlessly transition historical analytics from `media_analytics.db` without data loss, a migration script `migrate_sqlite_to_postgres.py` is specified:

```python
"""
migrate_sqlite_to_postgres.py - Migration & Backfill Utility
Transfers historical rows from media_analytics.db to Cloud SQL PostgreSQL.
"""
import sqlite3
import json
import logging
from pathlib import Path
from database_sink import get_db_connection, init_db, get_db_config
import psycopg2.extras

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

SQLITE_PATH = Path("g:/My Drive/GOOGLE ANTIGRAVITY/quick_share_ai_loop/media_analytics.db")

def migrate_data():
    if not SQLITE_PATH.exists():
        logger.warning(f"SQLite DB not found at {SQLITE_PATH}. Nothing to migrate.")
        return

    # Ensure PostgreSQL schema is initialized
    init_db()

    # Read SQLite data
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute("SELECT filename, filepath, domain, entity, viral_features, technical, created_at FROM video_tags")
    rows = sqlite_cur.fetchall()
    sqlite_conn.close()

    logger.info(f"Found {len(rows)} records in SQLite database.")
    if not rows:
        return

    migrated_count = 0
    with get_db_connection() as pg_conn:
        with pg_conn.cursor() as pg_cur:
            for row in rows:
                filename, filepath, domain, entity, viral_raw, tech_raw, created_at = row
                
                # Parse legacy stringified JSON
                viral_features = json.loads(viral_raw) if isinstance(viral_raw, str) else viral_raw or []
                technical = json.loads(tech_raw) if isinstance(tech_raw, str) else tech_raw or {}

                pg_cur.execute("""
                INSERT INTO video_tags (
                    filename, filepath, domain, entity, viral_features, technical, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (filename) DO UPDATE SET
                    filepath = EXCLUDED.filepath,
                    domain = EXCLUDED.domain,
                    entity = EXCLUDED.entity,
                    viral_features = EXCLUDED.viral_features,
                    technical = EXCLUDED.technical,
                    created_at = EXCLUDED.created_at;
                """, (
                    filename,
                    filepath,
                    domain or 'Unknown',
                    entity or 'Unknown',
                    psycopg2.extras.Json(viral_features),
                    psycopg2.extras.Json(technical),
                    created_at
                ))
                migrated_count += 1
            pg_conn.commit()

    logger.info(f"✅ Successfully migrated {migrated_count} records to PostgreSQL.")

if __name__ == "__main__":
    migrate_data()
```

---

### 8. Verification & Test Suite Matrix (TDAD Protocol)

In accordance with **Workspace Rule R2** (The Zero-Discretion Mandate / Leash Protocol), the implementation will be certified using deterministic, standalone automated tests:

1. **Unit & Integration Test Suite (`tests/test_database_sink.py`)**:
   - `test_env_validation_missing_keys()`: Proves that missing `PG_HOST` / `PG_PASSWORD` raises loud `ValueError` and prevents database execution.
   - `test_env_validation_valid()`: Proves valid `.env` parsing, port int conversion, and default fallback.
   - `test_connection_pool_lifecycle()`: Proves singleton pool instantiation, `ThreadedConnectionPool` type, and clean shutdown.
   - `test_micro_checkout_context_manager()`: Proves connections are returned to the pool after query completion and on query failure.
   - `test_insert_video_analytics_jsonb()`: Proves insertion of 4-layer taxonomy payload with `viral_features` list and `technical` dict as native `JSONB`.
   - `test_upsert_on_conflict()`: Proves subsequent insert with same `filename` updates record without duplicate key error.
2. **End-to-End Watchdog Integration Test (`tests/test_quick_share_integration.py`)**:
   - Proves `quick_share_hijack.py` successfully calls `database_sink.insert_video_analytics()` and releases all database connections.

---
Report Compiled by **Specification Miner 1** on 2026-08-27.
