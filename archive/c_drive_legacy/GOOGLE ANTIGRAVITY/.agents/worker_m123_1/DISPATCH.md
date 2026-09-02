# Dispatch Assignment - 2026-08-27T10:23:41Z

## Assigned Task
PostgreSQL migration for `quick_share_ai_loop`:
1. Requirements & Dependencies:
   - Ensure `psycopg2-binary`, `python-dotenv`, `pytest`, `watchdog`, `imageio-ffmpeg`, `google-genai` are specified in `requirements.txt`.
   - Install dependencies using `pip install -r requirements.txt`.
   - Provide `.env.example` with documented `PG_HOST`, `PG_PORT`, `PG_USER`, `PG_PASSWORD`, `PG_DB`, `PG_SSLMODE`.
2. PostgreSQL & Data Connect Schemas (R2):
   - Create `schema.sql`: Table `video_tags` replicating the SQLite table structure, but using `JSONB` for `viral_features` (array) and `technical` (object), with GIN indexing (`jsonb_path_ops`), `TIMESTAMPTZ`, and unique `filename`.
   - Create `schema.gql`: Firebase Data Connect GraphQL schema equivalent with `@table` and `jsonb` field bindings.
3. Database Sink Refactoring (R1, R3, R4):
   - Rewrite `database_sink.py` to connect to PostgreSQL via `psycopg2`.
   - Rule R26 Auth Guardrail: `get_db_config()` MUST fail fast (raise `ValueError` with clear actionable message) if `PG_HOST`, `PG_USER`, `PG_PASSWORD`, or `PG_DB` are missing or empty.
   - Connection Pooling (R4): Implement `ThreadedConnectionPool` singleton (`get_connection_pool()`, `close_pool()`).
   - Context Manager: Implement `get_db_connection()` context manager with pre-ping validation (`SELECT 1`), rollback on error, and guaranteed return (`pool.putconn()`) in a `finally` block to eliminate connection leaks.
   - `init_db()`: Executes DDL from `schema.sql` or table creation script idempotently.
   - `insert_video_analytics(filepath, tags_json)`: Parameterized upsert query using `ON CONFLICT (filename) DO UPDATE SET ...` wrapping `viral_features` and `technical` with `psycopg2.extras.Json`.
4. Test Suite Execution:
   - Create comprehensive unit/integration test suite `tests/test_database_sink.py` with Loud Assertions.
   - Verify config validation, pool checkout, leak prevention on exceptions, JSONB serialization, and 4K video tag payload insertion.
   - Run tests (`pytest -v`) and verify 100% pass.
5. Report:
   - Write handoff report at `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\worker_m123_1\handoff.md` with complete verification command outputs.
   - Send completion message to parent.
