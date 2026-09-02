# Project: Quick Share AI Loop PostgreSQL Migration

## Architecture
- **Language/Runtime**: Python 3.13 (`quick_share_ai_loop/.venv`)
- **Database**: Google Cloud SQL PostgreSQL / Firebase Data Connect (SQL Connect)
- **Database Driver**: `psycopg2-binary` with `psycopg2.pool.ThreadedConnectionPool`
- **Configuration & Auth**: `python-dotenv` with strict fail-fast validation (Rule R26)
- **Schema**: Native PostgreSQL with `JSONB` arrays (`viral_features`) and objects (`technical`), indexed via GIN (`jsonb_path_ops`).

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
|                                        |  - ThreadedConnectionPool             |  |
|                                        |  - Safe Context Manager Checkout      |  |
|                                        |  - Fail-Fast .env Guardrail (R26)     |  |
|                                        |  - Pre-Ping Connection Recovery       |  |
|                                        +---------------------------------------+  |
|                                                           |                       |
+-----------------------------------------------------------|-----------------------+
                                                            v
                        +-------------------------------------------------------+
                        | Google Cloud SQL PostgreSQL / Firebase Data Connect   |
                        | Table: video_tags                                     |
                        | Columns: id, filename, filepath, domain, entity,      |
                        |          viral_features (JSONB), technical (JSONB),   |
                        |          created_at, updated_at                       |
                        +-------------------------------------------------------+
```

## Feature Inventory
| # | Feature | Description | Milestone | Source | Status |
|---|---------|-------------|-----------|--------|:------:|
| 1 | Dependency & Environment Pre-Flight | Install `psycopg2-binary`, `python-dotenv`, `pytest` and setup `requirements.txt` | M1 | Survey | **DONE** |
| 2 | Rule R26 Auth Guardrail | Fail-fast config validation in `get_db_config()` for `PG_HOST`, `PG_USER`, `PG_PASSWORD`, `PG_DB` | M1 | Survey / Rule R26 | **DONE** |
| 3 | PostgreSQL DDL Schema (`schema.sql`) | DDL table definition with `JSONB` for `viral_features` & `technical`, GIN indices | M2 | Survey / R2 | **DONE** |
| 4 | Firebase Data Connect Schema (`schema.gql`) | GraphQL schema with `@table`, `@col(dataType: "jsonb")` directives | M2 | Survey / R2 | **DONE** |
| 5 | Threaded Connection Pool Management | `ThreadedConnectionPool` singleton lifecycle (`get_connection_pool()`, `close_pool()`) | M3 | Survey / R1, R4 | **DONE** |
| 6 | Safe Context Manager (`get_db_connection()`) | Micro-checkout with automatic commit/rollback and guarantee of `putconn()` return | M3 | Survey / R1, R4 | **DONE** |
| 7 | Pre-Ping & Stale Socket Recovery | Health check (`SELECT 1`) to discard dead connections on idle drop before use | M3 | Survey / R4 | **DONE** |
| 8 | Parameterized JSONB Upsert (`insert_video_analytics`) | Native PostgreSQL `ON CONFLICT (filename) DO UPDATE` with `psycopg2.extras.Json` | M3 | Survey / R1, R2 | **DONE** |
| 9 | Database Initialization (`init_db`) | Idempotent table & index initialization executing DDL schema | M3 | Survey / R1 | **DONE** |
| 10 | E2E Testing Suite (Tiers 1-4) | Deterministic mock test suite with Loud Assertions (`test_database_sink.py`) | M4 | Survey / Acceptance Criteria | **DONE** |
| 11 | Red Team Audit & Adversarial Hardening (Tier 5) | Red Team verification of connection leaks, pool starvation, and exception safety | M5 | Survey / R4 | **DONE** |
| 12 | Forensic Integrity & Final Acceptance Audit | Independent auditor verification against hardcoding and cheating | M6 | Survey / Audit Protocol | **DONE** |

## Milestones
| # | Name | Scope | Dependencies | Status | Key Outputs |
|---|------|-------|-------------|--------|-------------|
| M1 | Secret Management & Pre-Flight | `requirements.txt`, `.env.example`, `get_db_config()` fail-fast validation | None | **DONE** | `requirements.txt`, `.env.example`, `get_db_config()` |
| M2 | Schema Definitions | `schema.sql` & `schema.gql` with JSONB types and GIN indices | None | **DONE** | `schema.sql`, `schema.gql` |
| M3 | Database Sink Refactoring | `database_sink.py` with `ThreadedConnectionPool`, context manager, pre-ping recovery, upsert | M1, M2 | **DONE** | `database_sink.py` |
| M4 | E2E Testing Suite | `test_database_sink.py` covering Tiers 1-4 (4K video payloads, JSONB arrays, auth guardrail) | M3 | **DONE** | `tests/test_database_sink.py` (34 tests) |
| M5 | Red Team Audit & Hardening | Adversarial tests for connection leaks, thread starvation, exception rollback | M4 | **DONE** | `tests/test_adversarial_pool.py`, `tests/test_adversarial_payloads.py` (61 tests) |
| M6 | Forensic Integrity & Final Certification | `teamwork_preview_auditor` verification and 100% test pass confirmation | M5 | **DONE** | Full suite (95 tests passed in 1.15s), CLEAN forensic audit |

## Interface Contracts

### `database_sink.py` Public Interface
```python
def get_db_config() -> dict[str, Any]:
    """
    Validates and returns PostgreSQL connection configuration from .env.
    Raises ValueError with descriptive message if PG_HOST, PG_USER, PG_PASSWORD, or PG_DB is missing.
    """
    ...

def get_connection_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """
    Returns thread-safe singleton ThreadedConnectionPool (minconn=1, maxconn=10).
    """
    ...

@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Yields connection from pool with pre-ping validation.
    Guarantees rollback on exception and putconn() in finally block.
    """
    ...

def init_db() -> None:
    """
    Executes schema DDL to create video_tags table and indexes if not existing.
    """
    ...

def insert_video_analytics(filepath: str, tags_json: Union[str, dict]) -> None:
    """
    Inserts or updates video metadata into PostgreSQL video_tags table.
    Wraps viral_features (list) and technical (dict) with psycopg2.extras.Json.
    """
    ...

def close_pool() -> None:
    """
    Closes all connections in the connection pool cleanly.
    """
    ...
```

## Code Layout
```
quick_share_ai_loop/
├── .env                          # Local environment variables (PG_*, GEMINI_API_KEY)
├── .env.example                  # Documented template of required environment variables
├── requirements.txt              # Production and test Python dependencies
├── schema.sql                    # PostgreSQL DDL with JSONB & GIN indexes
├── schema.gql                    # Firebase Data Connect GraphQL schema
├── database_sink.py              # PostgreSQL database sink implementation
├── gemini_tagger.py              # Multimodal AI tagger
├── quick_share_hijack.py         # Watchdog daemon
├── TEST_INFRA.md                 # E2E Test Suite Specification
├── TEST_READY.md                 # E2E Test Readiness & Coverage Signoff
├── PROJECT.md                    # Authoritative project architecture & status
└── tests/
    ├── conftest.py               # Shared test fixtures and psycopg2 mock harnesses
    ├── test_database_sink.py     # Deterministic unit and integration tests (34 tests)
    ├── test_adversarial_pool.py  # Concurrency and connection leak stress tests (23 tests)
    └── test_adversarial_payloads.py # JSONB boundaries and payload stress tests (38 tests)
```
