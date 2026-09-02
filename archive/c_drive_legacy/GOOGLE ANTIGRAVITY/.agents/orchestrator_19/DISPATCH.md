# DISPATCH Log

## 2026-08-27T10:19:59Z
You are the Project Orchestrator (teamwork_preview_orchestrator).

Your working directory is:
G:\My Drive\GOOGLE ANTIGRAVITY\.agents\orchestrator_19

The authoritative user request file is:
G:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md

The target project working directory is:
g:/My Drive/GOOGLE ANTIGRAVITY/quick_share_ai_loop

Task Overview:
Migrate the local Quick Share AI pipeline's database from SQLite to a production Google Cloud SQL PostgreSQL database using Firebase Data Connect.

Requirements:
1. R1. Database Refactoring (database_sink.py)
   Rewrite the `database_sink.py` script to connect to a remote PostgreSQL database via `psycopg2`. It must authenticate using environment variables loaded from the `.env` file (e.g., `PG_HOST`, `PG_USER`, `PG_PASSWORD`, `PG_DB`).
2. R2. PostgreSQL Schema Definition
   Create a `schema.sql` (or Firebase Data Connect `schema.gql` equivalent) that replicates the existing SQLite `video_tags` table, but uses proper Postgres data types (e.g., `JSONB` for the `viral_features` and `technical` arrays instead of stringified JSON).
3. R3. Secret Management & Guardrails
   Adhere to the workspace rule R26 (The Background Daemon Auth Guardrail). The Python script must fail fast if the PostgreSQL environment variables are missing, preventing silent data loss.
4. R4. The Red Team Audit (architecture-red-team)
   Before finalizing the implementation, the LangGraph Red Team node must audit the connection pool strategy in `database_sink.py` to ensure it does not leak connections to the Cloud SQL instance during long-running daemon operations.

Acceptance Criteria:
- [ ] A mock test script successfully connects to a local/mock Postgres instance and inserts a tagged 4K video payload.
- [ ] The `viral_features` column correctly accepts array payloads as `JSONB`.
- [ ] The `database_sink.py` uses proper connection pooling or context managers that automatically close connections upon success or failure.
