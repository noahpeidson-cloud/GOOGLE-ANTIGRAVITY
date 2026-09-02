# Architectural Analysis: Database Architecture & Telemetry Engine (Milestone 1)

**Subagent ID:** `explorer_m1_2`  
**Working Directory:** `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m1_2`  
**Target File Paths:** `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\database.py`, `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_database.py`  
**Date:** 2026-08-25  

---

## 1. Executive Summary

Milestone 1 establishes the foundational data layer for the Antigravity Daily Health Scanner & ML Optimization Daemon. Per `ORIGINAL_REQUEST.md` (§R1, §R2) and `PROJECT.md`, the telemetry engine is responsible for:
1. Managing a lightweight, zero-dependency, local SQLite database (`health_telemetry.db`) configured with Write-Ahead Logging (`WAL`), strict foreign keys, and 5000ms busy timeouts.
2. Persisting structured scan sessions, detected anomalies, ProTeGi textual gradients, and historical baseline lifelines.
3. Automatically and idempotently seeding the exactly 5 August 23/24 failure lifelines on database initialization (`init_db()`).
4. Providing atomic transactional CRUD operations (`log_scan_session`, `get_session`, `get_anomalies_for_session`, `get_historical_drift`) that rollback completely upon any partial failure.
5. Providing a comprehensive, zero-shared-state unit test suite (`tests/test_database.py`) adhering to the Zero-Discretion Mandate (Rule R2) with Loud Assertions.

---

## 2. SQLite Schema Architecture & DDL

### 2.1 Database PRAGMAs
To prevent database lock collisions between background cron workers, CLI invocations, and test suites, the connection factory `get_db_connection(db_path)` must execute:
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

### 2.2 Table Definitions

#### 1. `scan_sessions`
Tracks overall metadata for each execution run of the daily scanner.
```sql
CREATE TABLE IF NOT EXISTS scan_sessions (
    session_id TEXT PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    duration_ms REAL NOT NULL DEFAULT 0.0,
    total_anomalies INTEGER NOT NULL DEFAULT 0,
    approved_count INTEGER NOT NULL DEFAULT 0,
    challenged_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    entropy_score REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. `anomalies`
Records individual anomalies detected during a scan session, complete with detector type, severity, JSON raw details, confidence, and red-team audit verdicts.
```sql
CREATE TABLE IF NOT EXISTS anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    detector_type TEXT NOT NULL CHECK(detector_type IN (
        'GHOST_DAEMONS', 'CONTEXT_ROT', 'ECOSYSTEM_POLLUTION', 'SECRET_ZERO', 'PROMPT_FATIGUE'
    )),
    target_path TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN (
        'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    )),
    description TEXT NOT NULL,
    raw_details TEXT NOT NULL DEFAULT '{}',
    is_historical INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 1.0,
    verdict TEXT CHECK(verdict IN ('APPROVED', 'CHALLENGED', 'REJECTED') OR verdict IS NULL),
    rationale TEXT,
    risk_assessment TEXT,
    recommended_action TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES scan_sessions(session_id) ON DELETE CASCADE
);
```

#### 3. `historical_lifelines`
Stores the permanent historical failure reference baselines from August 23/24 incidents.
```sql
CREATE TABLE IF NOT EXISTS historical_lifelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    incident_date TEXT NOT NULL,
    detector_type TEXT NOT NULL,
    description TEXT NOT NULL,
    failure_signature TEXT NOT NULL,
    mitigation_pattern TEXT NOT NULL,
    default_severity TEXT NOT NULL CHECK(default_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    raw_details TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 4. `textual_gradients`
Stores ProTeGi textual gradients and behavioral correction diffs emitted by the ML optimization loop.
```sql
CREATE TABLE IF NOT EXISTS textual_gradients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    detector_type TEXT NOT NULL,
    gradient_text TEXT NOT NULL,
    applied INTEGER NOT NULL DEFAULT 0,
    entropy_delta REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES scan_sessions(session_id) ON DELETE CASCADE
);
```

### 2.3 Indexes
```sql
CREATE INDEX IF NOT EXISTS idx_anomalies_session ON anomalies(session_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_detector ON anomalies(detector_type);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity);
CREATE INDEX IF NOT EXISTS idx_lifelines_key ON historical_lifelines(key);
CREATE INDEX IF NOT EXISTS idx_gradients_session ON textual_gradients(session_id);
```

---

## 3. The 5 August 23/24 Historical Failure Lifelines (Seeding Specification)

Per `ORIGINAL_REQUEST.md` §R2, the database must be idempotently auto-seeded on `init_db()` with exactly 5 failure callouts from the August 23/24 session:

| # | Key | Title | Incident Date | Detector Type | Default Severity | Failure Signature | Mitigation Pattern |
|---|-----|-------|---------------|---------------|------------------|-------------------|--------------------|
| 1 | `ghost_daemons` | Ghost Daemons Socket Collision | 2026-08-23 | `GHOST_DAEMONS` | `CRITICAL` | `WinError 10048: Only one usage of each socket address is normally permitted` | Audit background daemon tasks via socket probe on ports 3000, 8000, 8501; terminate orphaned listeners before bind |
| 2 | `context_rot` | Context Rot Planning Bloat | 2026-08-23 | `CONTEXT_ROT` | `HIGH` | `Stale planning files (*proposal*, *ideas*, *blueprint*) older than 24h (86400s)` | Page stale planning artifacts to .archive/ L2 storage; retain only active BRIEFING.md and task.md in primary context |
| 3 | `ecosystem_pollution` | Ecosystem Pollution Disabled Plugins | 2026-08-24 | `ECOSYSTEM_POLLUTION` | `MEDIUM` | `Directories matching *.disabled in plugins or cross-track domain leaks` | Prune or quarantine .disabled plugin folders from crawler index; enforce track isolation per GEMINI.md workspace manifest |
| 4 | `secret_zero` | Secret Zero Unresolved Placeholders | 2026-08-24 | `SECRET_ZERO` | `CRITICAL` | `Placeholder secrets (your_token_here, YOUR_API_KEY) in .env or configs` | Static scan of all .env and config files; halt immediately if placeholder secrets are detected without valid credentials |
| 5 | `prompt_fatigue` | Prompt Fatigue Manifest Bloat | 2026-08-24 | `PROMPT_FATIGUE` | `HIGH` | `GEMINI.md lines > 100 or excessive static procedural rules in system prompt` | Vectorize procedural rules into FTS5 / SQLite rule registry; dynamically retrieve top-k rules via BM25 matching |

### 3.1 Idempotency Logic
Seeding uses `INSERT INTO historical_lifelines ... ON CONFLICT(key) DO UPDATE SET ...` or `INSERT OR IGNORE`. This guarantees:
- Calling `init_db()` multiple times never duplicates rows.
- Exactly 5 rows exist in `historical_lifelines` under all circumstances.

---

## 4. Telemetry CRUD Interface & Transaction Safety

### 4.1 Interface Signatures
```python
def get_db_connection(db_path: str = "health_telemetry.db") -> sqlite3.Connection:
    """Creates a SQLite connection configured with WAL mode, foreign keys, and 5s timeout."""

def init_db(db_path: str = "health_telemetry.db") -> None:
    """Initializes tables, indexes, and idempotently seeds the 5 historical lifelines."""

def seed_historical_lifelines(db_path: str = "health_telemetry.db") -> None:
    """Idempotently inserts or updates the 5 August 23/24 historical lifelines."""

def log_scan_session(
    session_id: str,
    anomalies: List[Union[AnomalyRecord, Dict[str, Any]]],
    gradients: Optional[List[Union[str, Dict[str, Any]]]] = None,
    duration_ms: float = 0.0,
    total_anomalies: Optional[int] = None,
    approved_count: int = 0,
    challenged_count: int = 0,
    rejected_count: int = 0,
    entropy_score: float = 0.0,
    timestamp: Optional[int] = None,
    db_path: str = "health_telemetry.db"
) -> None:
    """Atomically logs a scan session, its anomalies, and textual gradients in a single transaction."""

def get_session(session_id: str, db_path: str = "health_telemetry.db") -> Optional[Dict[str, Any]]:
    """Retrieves metadata for a specific scan session."""

def get_anomalies_for_session(session_id: str, db_path: str = "health_telemetry.db") -> List[Dict[str, Any]]:
    """Retrieves all anomalies for a given session with JSON raw_details parsed."""

def get_textual_gradients_for_session(session_id: str, db_path: str = "health_telemetry.db") -> List[Dict[str, Any]]:
    """Retrieves all textual gradients for a given session."""

def get_historical_lifelines(db_path: str = "health_telemetry.db") -> List[Dict[str, Any]]:
    """Retrieves all 5 historical lifelines with JSON raw_details parsed."""

def get_historical_drift(db_path: str = "health_telemetry.db") -> Dict[str, Any]:
    """Aggregates telemetry across all sessions to compute drift metrics, detector frequencies, and severity counts."""
```

### 4.2 Atomic Transaction Safety & Rollback
`log_scan_session` wraps the insertion of `scan_sessions`, `anomalies`, and `textual_gradients` inside a Python `with conn:` context manager. If an exception is raised (e.g. invalid `detector_type` check constraint or malformed payload):
1. SQLite automatically rolls back the entire transaction.
2. No orphaned `scan_sessions` row or partial anomaly records remain in the database.
3. The error is propagated to the caller without silent suppression.

---

## 5. Loud Assertions Unit Test Suite (`tests/test_database.py`)

In accordance with Rule R2 (The Zero-Discretion Mandate):
- Tests must use Loud Assertions (zero shared state, explicit values, no silent catches).
- Each test runs against an isolated SQLite file in `tmp_path` or an in-memory database.
- 12 comprehensive unit tests cover:
  1. `test_init_db_creates_tables_and_indexes`: Confirms all 4 tables and 5 indexes exist.
  2. `test_init_db_seeds_exact_five_lifelines`: Confirms exactly 5 lifelines with expected keys.
  3. `test_seeding_idempotency`: Calling `init_db` multiple times maintains exactly 5 rows.
  4. `test_historical_lifelines_field_content`: Confirms signatures, severities, and JSON details for all 5 lifelines.
  5. `test_log_scan_session_atomic_commit`: Verifies session, anomalies, and gradients are persisted correctly.
  6. `test_log_scan_session_dataclass_and_dict_support`: Confirms both `AnomalyRecord` instances and dicts work seamlessly.
  7. `test_log_scan_session_atomic_rollback_on_error`: Inducing a constraint failure verifies 0 rows are created in any table.
  8. `test_foreign_key_enforcement`: Inserting anomaly with non-existent `session_id` raises `IntegrityError`.
  9. `test_check_constraint_detector_type`: Inserting invalid detector type raises `IntegrityError`.
  10. `test_check_constraint_severity`: Inserting invalid severity raises `IntegrityError`.
  11. `test_get_anomalies_for_session_json_deserialization`: Verifies `raw_details` is deserialized to Python dict.
  12. `test_get_historical_drift_aggregation`: Validates multi-session drift metrics, anomaly counts, and detector breakdowns.

---

## 6. Implementation Specifications for Worker Subagents

### 6.1 `database.py` Implementation Blueprint
```python
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Union

# Define exact 5 historical failure lifelines
HISTORICAL_LIFELINES_DATA = [
    {
        "key": "ghost_daemons",
        "title": "Ghost Daemons Socket Collision",
        "incident_date": "2026-08-23",
        "detector_type": "GHOST_DAEMONS",
        "description": "Unmonitored Next.js/Uvicorn background tasks causing socket collisions (WinError 10048)",
        "failure_signature": "WinError 10048: [WinError 10048] Only one usage of each socket address is normally permitted",
        "mitigation_pattern": "Audit background daemon tasks using socket probe on ports 3000, 8000, 8501; terminate orphaned listeners before bind",
        "default_severity": "CRITICAL",
        "raw_details": json.dumps({"ports": [3000, 8000, 8501], "error_code": "WinError 10048", "affected_runtimes": ["Next.js", "Uvicorn", "FastAPI"]})
    },
    {
        "key": "context_rot",
        "title": "Context Rot Planning Bloat",
        "incident_date": "2026-08-23",
        "detector_type": "CONTEXT_ROT",
        "description": "Planning artifacts older than 24 hours diluting the context window and consuming L1 cache",
        "failure_signature": "Stale planning files (*proposal*, *ideas*, *blueprint*) older than 86400s (24h)",
        "mitigation_pattern": "Page stale planning artifacts to .archive/ L2 storage; retain only active BRIEFING.md and task.md in primary context",
        "default_severity": "HIGH",
        "raw_details": json.dumps({"max_age_hours": 24, "target_patterns": ["*proposal*", "*ideas*", "*blueprint*"], "action": "archive"})
    },
    {
        "key": "ecosystem_pollution",
        "title": "Ecosystem Pollution Disabled Plugins",
        "incident_date": "2026-08-24",
        "detector_type": "ECOSYSTEM_POLLUTION",
        "description": "Unused .disabled plugin directories and cross-track files confusing the crawler and rule registry",
        "failure_signature": "Directories matching *.disabled in plugins or cross-track domain leakage",
        "mitigation_pattern": "Prune or quarantine .disabled plugin folders from crawler index; enforce track isolation per GEMINI.md workspace manifest",
        "default_severity": "MEDIUM",
        "raw_details": json.dumps({"plugin_suffix": ".disabled", "forbidden_cross_tracks": ["sports_cards in content_creation", "content_creation in apps"]})
    },
    {
        "key": "secret_zero",
        "title": "Secret Zero Unresolved Placeholders",
        "incident_date": "2026-08-24",
        "detector_type": "SECRET_ZERO",
        "description": "Unresolved placeholder tokens (your_token_here, YOUR_API_KEY) in .env files and OAuth credentials",
        "failure_signature": "your_token_here|YOUR_API_KEY|<API_KEY>|placeholder_in_.env",
        "mitigation_pattern": "Static scan of all .env and config files; halt immediately if placeholder secrets are detected without valid credentials",
        "default_severity": "CRITICAL",
        "raw_details": json.dumps({"placeholder_patterns": ["your_token_here", "YOUR_API_KEY", "INSERT_KEY_HERE", "TODO_TOKEN"], "target_files": [".env", ".env.local", "config.json"]})
    },
    {
        "key": "prompt_fatigue",
        "title": "Prompt Fatigue Manifest Bloat",
        "incident_date": "2026-08-24",
        "detector_type": "PROMPT_FATIGUE",
        "description": "Hardcoded procedural rules bloating GEMINI.md manifest beyond 100 lines and degrading LLM instruction adherence",
        "failure_signature": "GEMINI.md lines > 100 or excessive static rule tokens in system prompt",
        "mitigation_pattern": "Vectorize procedural rules into FTS5 / SQLite rule registry; dynamically retrieve top-k rules via BM25 matching",
        "default_severity": "HIGH",
        "raw_details": json.dumps({"max_manifest_lines": 100, "recommended_storage": "vectorized_rule_registry", "strategy": "BM25 dynamic retrieval"})
    }
]
```
