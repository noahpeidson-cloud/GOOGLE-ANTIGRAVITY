# Comprehensive Codebase Survey: `quick_share_ai_loop` PostgreSQL Migration

**Date**: 2026-08-27  
**Author**: Explorer Survey Agent (`explorer_survey_1`)  
**Target Repository**: `g:/My Drive/GOOGLE ANTIGRAVITY/quick_share_ai_loop`  
**Working Directory**: `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_survey_1`  

---

## 1. Executive Summary

The `quick_share_ai_loop` is an automated, real-time media ingestion and tagging pipeline. It intercepts incoming video files (e.g. 4K/60fps concert footage, sports card rips, travel clips) transferred via Google Quick Share (`C:\Users\noahp\Downloads\Quick Share`), generates 720p FFmpeg proxies, extracts a structured 4-layer taxonomy via Gemini 3.6 Flash (`gemini-3.6-flash`), stores video metadata in a local SQLite database (`media_analytics.db`), and transfers the original raw media to Google Drive (`photos_triage_project/Raw_Ingest`) with SHA-256 checksum verification.

The objective of this survey is to provide complete architectural, schema, payload, and invocation specifications to guide the migration of the database layer (`database_sink.py`) from local SQLite to a remote **Google Cloud SQL PostgreSQL / Firebase Data Connect** instance using `psycopg2`.

---

## 2. Repository & File System Inventory

Path: `g:/My Drive/GOOGLE ANTIGRAVITY/quick_share_ai_loop`

```
quick_share_ai_loop/
├── .env                  (69 bytes: GEMINI_API_KEY)
├── .venv/                (Python 3.13.14 virtual environment)
├── database_sink.py      (1,587 bytes: SQLite database sink implementation)
├── gemini_tagger.py      (3,845 bytes: FFmpeg proxy generator & Gemini Flash tagger)
├── media_analytics.db    (16,384 bytes: Live SQLite database containing historical records)
├── quick_share_hijack.py (4,390 bytes: Watchdog daemon, file locking, sha256 copier)
└── __pycache__/          (Precompiled bytecode: database_sink, gemini_tagger)
```

---

## 3. Detailed Component-by-Component Code Analysis

### 3.1 `database_sink.py`
- **Current Responsibilities**:
  - Defines the database schema for video tags.
  - Exposes `init_db()` to create the `video_tags` SQLite table if not present.
  - Exposes `insert_video_analytics(filepath, tags_json)` to sink parsed AI tagging results into SQLite.
- **Key Code Segments**:
  - SQLite Table Creation (`database_sink.py:15-25`):
    ```python
    cursor.execute('''
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
    ''')
    ```
  - Upsert Logic (`database_sink.py:38-47`):
    ```python
    cursor.execute('''
    INSERT OR REPLACE INTO video_tags (filename, filepath, domain, entity, viral_features, technical)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        filename,
        filepath,
        tags.get('domain', 'Unknown'),
        tags.get('entity', 'Unknown'),
        json.dumps(tags.get('viral_features', [])),
        json.dumps(tags.get('technical', {}))
    ))
    ```
- **Observed Deficiencies & Migration Requirements**:
  1. Uses SQLite-specific `INSERT OR REPLACE INTO` which must be converted to PostgreSQL standard `INSERT INTO ... ON CONFLICT (filename) DO UPDATE SET ...`.
  2. Serializes `viral_features` and `technical` as flat strings (`json.dumps()`) stored in SQLite `TEXT` columns. In PostgreSQL, these must be migrated to native `JSONB` data types.
  3. Lacks connection pooling: each call invokes `sqlite3.connect(DB_PATH)`. For remote Cloud SQL Postgres, opening fresh TCP/TLS sockets per video causes high latency and potential socket starvation.
  4. Lacks `.env` fail-fast validation for PostgreSQL connection parameters (`PG_HOST`, `PG_USER`, `PG_PASSWORD`, `PG_DB`, `PG_PORT`).

---

### 3.2 `gemini_tagger.py`
- **Responsibilities**:
  - **FFmpeg Proxy Generation (`generate_proxy`)**: Converts heavy 4K/60fps media into a lightweight 720p 30fps 1Mbps proxy (`temp_proxy/<stem>_proxy.mp4`) via `imageio_ffmpeg`.
  - **Gemini Multimodal Upload & Polling (`tag_video`)**: Uploads the proxy to Google AI Files API, polls state until `ACTIVE`.
  - **AI Inference Prompt**: Prompts `gemini-3.6-flash` with a 4-layer taxonomy:
    ```
    Analyze this video and output a JSON object adhering to this 4-layer taxonomy:
    1. domain: The high-level category (e.g., 'EDM', 'Sports Cards', 'Travel').
    2. entity: The specific subject (e.g., 'Excision', 'Zeds Dead').
    3. viral_features: Array of strings detailing trending hooks (e.g., ['Heavy_Lasers', 'Bass_Drop_0:15', 'Crowd_Pan']).
    4. technical: Object with quality metrics (e.g., {'lighting': 'dark', 'audio_clipping': true}).
    
    Return ONLY raw JSON.
    ```
  - **Exponential Backoff (`gemini_tagger.py:65-98`)**: Robust 503 retry wrapper with base delay 5s and 5 retries (adheres to Rule R27).
  - **Resource Cleanup**: Deletes uploaded file on Gemini server and deletes local proxy file (`gemini_tagger.py:99-102`).
  - **Return Type**: Python `dict` parsed via `json.loads(response_text)`.

---

### 3.3 `quick_share_hijack.py`
- **Responsibilities**:
  - Long-running watchdog daemon (`watchdog.observers.Observer`) monitoring `C:\Users\noahp\Downloads\Quick Share`.
  - Filters for `.mp4`, `.mov`, `.webm`.
  - File lock stabilization: `wait_for_file_to_finish(filepath, timeout=300)` checks file size stability for 3 seconds and verifies OS write lock release.
  - Orchestration pipeline on new file:
    1. Calls `tag_video(str(filepath))` -> returns `tags_json` dict.
    2. Calls `insert_video_analytics(str(filepath), tags_json)`.
    3. Calculates SHA-256 hash on C: drive file.
    4. Copies file to `G:/My Drive/GOOGLE ANTIGRAVITY/photos_triage_project/Raw_Ingest` using `shutil.copy2`.
    5. Calculates SHA-256 hash on G: drive destination.
    6. Deletes local file on C: drive only if hashes match identically.
- **Invocation & Dependency on `database_sink.py`**:
  - `from database_sink import insert_video_analytics` (`quick_share_hijack.py:9`)
  - Invocation line 61: `insert_video_analytics(str(filepath), tags_json)`
  - Note: `filepath` passed to `insert_video_analytics` is the original C: drive path (e.g., `C:\Users\noahp\Downloads\Quick Share\20260819_212636.mp4`), and `filename` is extracted as `Path(filepath).name`.

---

## 4. Current Database Schema & Live SQLite Data Inspection

### 4.1 SQLite Table Definition (`media_analytics.db`)

| Column Name | SQLite Type | Nullable | Default | Constraints | Description |
|---|---|---|---|---|---|
| `id` | `INTEGER` | No | Auto-inc | `PRIMARY KEY AUTOINCREMENT` | Internal synthetic ID |
| `filename` | `TEXT` | Yes | None | `UNIQUE` | Base name of the video file |
| `filepath` | `TEXT` | Yes | None | None | File path on disk at ingestion |
| `domain` | `TEXT` | Yes | None | None | Domain taxonomy (e.g., `EDM`, `Sports Cards`, `Travel`) |
| `entity` | `TEXT` | Yes | None | None | Specific subject (e.g., `EDM Concert`, `Excision`) |
| `viral_features` | `TEXT` | Yes | None | None | Stringified JSON array of viral hooks |
| `technical` | `TEXT` | Yes | None | None | Stringified JSON object of technical metrics |
| `created_at` | `TIMESTAMP` | Yes | `CURRENT_TIMESTAMP` | None | Row creation timestamp (UTC) |

### 4.2 Live Row 1 Inspection from `media_analytics.db`

Direct query output (`SELECT * FROM video_tags`):
- `id`: `1`
- `filename`: `'20260819_212636.mp4'`
- `filepath`: `'C:\\Users\\noahp\\Downloads\\Quick Share\\20260819_212636.mp4'`
- `domain`: `'EDM'`
- `entity`: `'EDM Concert'`
- `viral_features`: `'["Heavy_Lasers", "Laser_Show", "Crowd_Pan", "Stage_Lighting", "Synchronized_Lights"]'`
- `technical`: `'{"lighting": "dynamic_lasers", "audio_clipping": false, "orientation": "vertical", "camera_stability": "handheld"}'`
- `created_at`: `'2026-08-27 10:13:27'`

---

## 5. Target PostgreSQL & Firebase Data Connect Architecture

### 5.1 Proposed PostgreSQL Schema (`schema.sql`)

```sql
-- schema.sql: PostgreSQL / Firebase Data Connect Schema for Video Analytics

CREATE TABLE IF NOT EXISTS video_tags (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL UNIQUE,
    filepath TEXT NOT NULL,
    domain VARCHAR(100) NOT NULL DEFAULT 'Unknown',
    entity VARCHAR(255) NOT NULL DEFAULT 'Unknown',
    viral_features JSONB NOT NULL DEFAULT '[]'::jsonb,
    technical JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indices for performance and JSON containment queries
CREATE INDEX IF NOT EXISTS idx_video_tags_filename ON video_tags(filename);
CREATE INDEX IF NOT EXISTS idx_video_tags_domain ON video_tags(domain);
CREATE INDEX IF NOT EXISTS idx_video_tags_viral_features ON video_tags USING GIN(viral_features);
CREATE INDEX IF NOT EXISTS idx_video_tags_technical ON video_tags USING GIN(technical);
```

### 5.2 JSONB Query Capabilities Enabled by Postgres
Migrating from SQLite `TEXT` to Postgres `JSONB` unlocks native array and key-value indexing:
1. **Array Containment**: `SELECT * FROM video_tags WHERE viral_features @> '["Heavy_Lasers"]';`
2. **JSON Key Extraction**: `SELECT filename, technical->>'lighting' AS lighting FROM video_tags WHERE (technical->>'audio_clipping')::boolean = false;`
3. **Array Length Queries**: `SELECT filename, jsonb_array_length(viral_features) FROM video_tags;`

---

## 6. Target DML Upsert & Driver Logic (`psycopg2`)

### 6.1 Parameterized Upsert Query
```python
UPSERT_VIDEO_TAGS_QUERY = """
INSERT INTO video_tags (filename, filepath, domain, entity, viral_features, technical, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
ON CONFLICT (filename) 
DO UPDATE SET
    filepath = EXCLUDED.filepath,
    domain = EXCLUDED.domain,
    entity = EXCLUDED.entity,
    viral_features = EXCLUDED.viral_features,
    technical = EXCLUDED.technical,
    updated_at = CURRENT_TIMESTAMP;
"""
```

### 6.2 Serialization via `psycopg2.extras.Json`
In `psycopg2`, native Python dicts and lists should be passed using `psycopg2.extras.Json`:
```python
from psycopg2.extras import Json

viral_features = tags.get('viral_features', [])
technical = tags.get('technical', {})

params = (
    filename,
    filepath,
    tags.get('domain', 'Unknown'),
    tags.get('entity', 'Unknown'),
    Json(viral_features if isinstance(viral_features, list) else []),
    Json(technical if isinstance(technical, dict) else {})
)
```

---

## 7. Configuration & Secret Management Guardrails (Rule R26)

### 7.1 Environment Variables Required in `.env`
To adhere to Rule R26 (The Background Daemon Auth Guardrail), `database_sink.py` must explicitly load `.env` via `python-dotenv` and fail fast if any Postgres connection variables are absent:

| Variable | Description | Default / Example | Required |
|---|---|---|---|
| `PG_HOST` | Hostname or Cloud SQL proxy IP | `localhost` / `127.0.0.1` | **YES** |
| `PG_PORT` | PostgreSQL port | `5432` | Optional (default 5432) |
| `PG_DB` | Database name | `media_analytics` / `postgres` | **YES** |
| `PG_USER` | Database username | `postgres` | **YES** |
| `PG_PASSWORD` | Database password | `******` | **YES** |
| `PG_SSLMODE` | SSL Mode for Cloud SQL | `prefer` / `require` / `disable` | Optional (default `prefer`) |

### 7.2 Fail-Fast Enforcement Pattern
```python
def validate_pg_config():
    missing = [var for var in ("PG_HOST", "PG_USER", "PG_PASSWORD", "PG_DB") if not os.getenv(var)]
    if missing:
        raise ValueError(f"CRITICAL: Missing required PostgreSQL environment variables: {', '.join(missing)}")
```

---

## 8. Connection Pooling & Daemon Lifecycle (Rule R4 Audit)

### 8.1 The Daemon Connection Problem
`quick_share_hijack.py` runs continuously as a background process. If `database_sink.py` opens a new connection on every file event and relies on garbage collection, connection leaks or socket timeouts against Cloud SQL will occur. Conversely, maintaining a single raw connection will break when Cloud SQL drops idle TCP connections after inactivity.

### 8.2 Recommended Solution: `psycopg2.pool.ThreadedConnectionPool` with Context Manager
1. Implement a thread-safe connection pool singleton (`ThreadedConnectionPool(minconn=1, maxconn=5, ...)`).
2. Provide a context manager (`get_db_connection()`) that borrows a connection from the pool, tests/refreshes if closed, yields it, commits or rolls back, and returns it to the pool in a `finally` block.
3. Graceful shutdown handler to close all pool connections on SIGINT/SIGTERM.

---

## 9. Dependency Matrix & Packaging Requirements

### Current Python Environment
- Python Version: `3.13.14`
- Installed: `watchdog (6.0.0)`, `google-genai (2.20.0)`, `imageio-ffmpeg (0.6.0)`, `python-dotenv (1.2.3)`, `requests (2.34.2)`, `pydantic (2.13.4)`

### Missing Required Package
- `psycopg2-binary` (or `psycopg2`) is **NOT** currently installed in the workspace `.venv`.
- Action: Install `psycopg2-binary` and add to a new `requirements.txt`.

---

## 10. Summary Checklist for Implementation Specialists

- [ ] **Dependency Setup**: Create `requirements.txt` containing `psycopg2-binary`, `python-dotenv`, `google-genai`, `imageio-ffmpeg`, `watchdog` and run `pip install -r requirements.txt`.
- [ ] **PostgreSQL DDL (`schema.sql`)**: Create `schema.sql` with table `video_tags` using `JSONB` for `viral_features` and `technical`, GIN indices, and `TIMESTAMPTZ`.
- [ ] **`database_sink.py` Refactoring**:
  - Replace SQLite imports with `psycopg2`, `psycopg2.extras.Json`, and `psycopg2.pool.ThreadedConnectionPool`.
  - Load `.env` and fail fast on missing `PG_*` credentials.
  - Implement `init_db()` executing `schema.sql` (or table creation DDL).
  - Implement `insert_video_analytics(filepath, tags_json)` using PostgreSQL `JSONB` upsert.
- [ ] **Verification Harness (`test_database_sink.py`)**:
  - Test connection validation (fail fast without env).
  - Test mock insertion with 4K video tag payload containing arrays and dicts.
  - Verify JSONB array and object querying.
