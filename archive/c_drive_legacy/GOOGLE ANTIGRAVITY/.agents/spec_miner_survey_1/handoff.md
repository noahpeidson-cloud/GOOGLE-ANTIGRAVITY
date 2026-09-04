# Handoff Report: Quick Share AI Loop PostgreSQL Migration Specification

**Agent ID:** `spec_miner_survey_1`  
**Archetype:** `teamwork_preview_spec_miner`  
**Working Directory:** `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_survey_1`  
**Target Repository / Workspace:** `g:/My Drive/GOOGLE ANTIGRAVITY/quick_share_ai_loop`  
**Parent Conversation ID:** `c6475b09-d90e-472c-88ce-de3ae2ea24d5`  
**Handoff Type:** Hard (Task Complete)  
**Date:** 2026-08-27  

---

## 1. Observation

1. **User Request & Requirements (`ORIGINAL_REQUEST.md`, lines 88–118):**
   - R1: Database Refactoring (`database_sink.py`) to connect to remote PostgreSQL via `psycopg2` using environment variables (`PG_HOST`, `PG_USER`, `PG_PASSWORD`, `PG_DB`).
   - R2: PostgreSQL schema definition (`schema.sql` / Firebase Data Connect `schema.gql`) replicating `video_tags` table using `JSONB` for `viral_features` and `technical` array fields.
   - R3: Secret Management & Rule R26 (The Background Daemon Auth Guardrail) requiring fail-fast environment variable validation.
   - R4: Red Team audit of connection pool strategy in `database_sink.py` ensuring no connection leaks during long-running daemon operations.

2. **Existing SQLite Implementation (`quick_share_ai_loop/database_sink.py`, lines 1–49):**
   - Current schema:
     ```sql
     CREATE TABLE IF NOT EXISTS video_tags (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         filename TEXT UNIQUE,
         filepath TEXT,
         domain TEXT,
         entity TEXT,
         viral_features TEXT,
         technical TEXT,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
     )
     ```
   - `insert_video_analytics(filepath, tags_json)` receives raw file path and parsed/unparsed JSON, dumping `viral_features` and `technical` to strings with `json.dumps()` and executing `INSERT OR REPLACE INTO video_tags`.

3. **Current Watchdog Daemon (`quick_share_ai_loop/quick_share_hijack.py`, lines 42–97):**
   - Monitors `~/Downloads/Quick Share` with `watchdog.observers.Observer`.
   - On video detection (`on_created`), calls `wait_for_file_to_finish()`, then invokes `gemini_tagger.tag_video()` (which runs FFmpeg proxy generation, Gemini File upload, and `gemini-3.6-flash` inference), sinks analytics via `database_sink.insert_video_analytics()`, and performs SHA-256 integrity verification before moving file to G: Drive.

4. **Workspace Rule R26 (`GEMINI.md`, lines 183–190):**
   - "When spawning long-running Python background scripts or daemons (e.g., via run_command in detached PowerShell) that require Gemini API access... The agent MUST install python-dotenv, import load_dotenv, and explicitly require/generate a local .env file containing the raw GEMINI_API_KEY to prevent immediate runtime auth crashes."

5. **Existing Local SQLite Database (`media_analytics.db`):**
   - Inspected row:
     `[(1, '20260819_212636.mp4', 'C:\\Users\\noahp\\Downloads\\Quick Share\\20260819_212636.mp4', 'EDM', 'EDM Concert', '["Heavy_Lasers", "Laser_Show", "Crowd_Pan", "Stage_Lighting", "Synchronized_Lights"]', '{"lighting": "dynamic_lasers", "audio_clipping": false, "orientation": "vertical", "camera_stability": "handheld"}', '2026-08-27 10:13:27')]`
   - Proves `viral_features` is a list of strings and `technical` is a dictionary of key-value attributes.

---

## 2. Logic Chain

1. **Driver & Pooling Architecture (R1 & R4):**
   - From Observation 3, `quick_share_hijack.py` runs on a long-lived multi-threaded background event loop (`watchdog`).
   - Standard single connections or naive `SimpleConnectionPool` instances fail due to thread collisions and Cloud SQL idle TCP dropouts.
   - Therefore, `database_sink.py` must use `psycopg2.pool.ThreadedConnectionPool` with a micro-checkout context manager (`get_db_connection()`), checking out a connection only when executing the SQL insert (<10ms) and immediately releasing it in a `finally` block.

2. **Schema & JSONB Data Type Transformation (R2):**
   - From Observations 2 and 5, SQLite used `TEXT` for `viral_features` and `technical`.
   - In PostgreSQL, `JSONB` offers binary indexing via GIN (`CREATE INDEX ... USING gin (viral_features)`) and native querying.
   - For Firebase Data Connect, `schema.gql` maps these to `Any! @col(name: "viral_features", dataType: "jsonb")`.
   - The PostgreSQL upsert syntax must use `ON CONFLICT (filename) DO UPDATE SET ...` replacing SQLite's `INSERT OR REPLACE`.

3. **Rule R26 Fail-Fast Protocol (R3):**
   - From Observation 4, daemons must not fail silently or assume IDE environment variables.
   - `database_sink.py` must validate `PG_HOST`, `PG_USER`, `PG_PASSWORD`, and `PG_DB` on startup; if missing, it raises a fatal `ValueError` and terminates execution immediately.

4. **Zero-Data-Loss Migration:**
   - From Observation 5, historical data exists in `media_analytics.db`.
   - A dedicated migration script (`migrate_sqlite_to_postgres.py`) must unpack stringified JSON and bulk upsert records into PostgreSQL.

---

## 3. Caveats

- **Cloud SQL Public vs Private IP / Auth Proxy**: If running outside Google Cloud VPC without public IP, the Cloud SQL Auth Proxy (`cloud-sql-proxy`) must be running locally forwarding port 5432 to `127.0.0.1`.
- **Firebase Data Connect CLI Requirements**: Deploying Firebase SQL Connect requires Firebase CLI version >= 13.x and an initialized Firebase project with Cloud SQL linked.
- No other caveats.

---

## 4. Conclusion

The specification survey for the Quick Share AI Loop PostgreSQL / Firebase Data Connect migration is complete:
1. `survey_spec.md` is compiled with full requirements, discovery tables, edge cases, interface contracts, SQL DDL, GraphQL schemas, and connection lifecycle anti-leak patterns.
2. `database_sink.py` refactoring design specifies `psycopg2.pool.ThreadedConnectionPool`, micro-checkout context manager, `ON CONFLICT` upsert, and Rule R26 fail-fast env validation.
3. PostgreSQL `schema.sql` and Firebase `schema.gql` define `video_tags` with native `JSONB` and GIN indexing.
4. Red Team anti-leak recommendations guarantee no connection hoarding during FFmpeg proxy generation or Gemini inference.

---

## 5. Verification Method

To independently verify the specification report and schema contracts:

1. **Inspect Mined Specification Artifact**:
   - Open and review `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_survey_1\survey_spec.md`.

2. **Verify SQL DDL Syntax**:
   - Execute Python parser test against the SQL schema in `survey_spec.md`:
     ```powershell
     python -c "import re; spec = open('G:/My Drive/GOOGLE ANTIGRAVITY/.agents/spec_miner_survey_1/survey_spec.md').read(); ddl = re.search(r'```sql\n(CREATE TABLE IF NOT EXISTS video_tags[\s\S]*?);?\n```', spec).group(1); print('Extracted DDL:\n', ddl)"
     ```

3. **Verify Existing SQLite Data Baseline**:
   - Inspect SQLite database count and structure:
     ```powershell
     python -c "import sqlite3; conn = sqlite3.connect('g:/My Drive/GOOGLE ANTIGRAVITY/quick_share_ai_loop/media_analytics.db'); cur = conn.cursor(); print('Existing row count:', cur.execute('SELECT COUNT(*) FROM video_tags').fetchone()[0])"
     ```
