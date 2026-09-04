"""SQLite Telemetry Database for Health Scanner & ML Optimization Daemon."""

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Union

from config import BUSY_TIMEOUT_MS, DEFAULT_DB_PATH
from models import AnomalyRecord, DetectorType, Severity


HISTORICAL_LIFELINES_DATA = [
    {
        "lifeline_code": "GHOST_DAEMONS_WINERROR_10048",
        "title": "Ghost Daemons (WinError 10048 / socket collision on ports 3000/8000/8501)",
        "detector_type": DetectorType.GHOST_DAEMONS.value,
        "root_cause": "Unmonitored Next.js/Uvicorn tasks binding ports 3000/8000/8501 without lifecycle management causing WinError 10048",
        "remediation": "Audit active port bindings on 3000, 8000, 8501 before launching server instances",
        "failure_session_date": "2026-08-23",
        "target_pattern": "ports:[3000, 8000, 8501]",
        "severity": Severity.CRITICAL.value,
    },
    {
        "lifeline_code": "CONTEXT_ROT_PLANNING_ARTIFACTS",
        "title": "Context Rot (>24h planning artifacts diluting context)",
        "detector_type": DetectorType.CONTEXT_ROT.value,
        "root_cause": "Planning artifacts older than 24 hours diluting the context window",
        "remediation": "Archive stale planning artifacts into BRIEFING.md / BRIEFING_ARCHIVE.md",
        "failure_session_date": "2026-08-23",
        "target_pattern": "artifacts_age_hours > 24.0",
        "severity": Severity.MEDIUM.value,
    },
    {
        "lifeline_code": "ECOSYSTEM_POLLUTION_DISABLED_PLUGINS",
        "title": "Ecosystem Pollution (.disabled plugins / cross-track leaks)",
        "detector_type": DetectorType.ECOSYSTEM_POLLUTION.value,
        "root_cause": "Unused .disabled plugin directories and cross-track leaks confusing crawler",
        "remediation": "Isolate track domains and quarantine disabled plugin configurations",
        "failure_session_date": "2026-08-24",
        "target_pattern": ".disabled directories & cross-track references",
        "severity": Severity.HIGH.value,
    },
    {
        "lifeline_code": "SECRET_ZERO_PLACEHOLDER_KEYS",
        "title": "Secret Zero (your_token_here in .env)",
        "detector_type": DetectorType.SECRET_ZERO.value,
        "root_cause": "Unresolved placeholder tokens (your_token_here) in .env files",
        "remediation": "Replace placeholder API keys with valid tokens or remove dummy keys from environment",
        "failure_session_date": "2026-08-24",
        "target_pattern": "your_token_here / YOUR_API_KEY_HERE",
        "severity": Severity.CRITICAL.value,
    },
    {
        "lifeline_code": "PROMPT_FATIGUE_MANIFEST_BLOAT",
        "title": "Prompt Fatigue (GEMINI.md > 100 lines)",
        "detector_type": DetectorType.PROMPT_FATIGUE.value,
        "root_cause": "Hardcoded procedural rules bloating the GEMINI.md manifest",
        "remediation": "Prune procedural rule text from GEMINI.md and distill into specialized skills",
        "failure_session_date": "2026-08-24",
        "target_pattern": "GEMINI.md line_count > 100",
        "severity": Severity.MEDIUM.value,
    },
]


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Creates a configured SQLite connection with WAL mode, busy_timeout, and foreign keys."""
    conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_MS / 1000.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS};")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.close()
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes SQLite telemetry tables and auto-seeds historical failure lifelines."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    session_id TEXT PRIMARY KEY,
                    timestamp INTEGER NOT NULL,
                    duration_ms REAL NOT NULL,
                    total_anomalies INTEGER NOT NULL,
                    entropy_score REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS anomalies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    detector_type TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    raw_details TEXT NOT NULL,
                    is_historical INTEGER DEFAULT 0,
                    timestamp INTEGER NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    FOREIGN KEY (session_id) REFERENCES scan_sessions(session_id) ON DELETE CASCADE
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS historical_lifelines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lifeline_code TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    detector_type TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    remediation TEXT NOT NULL,
                    failure_session_date TEXT NOT NULL,
                    target_pattern TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS textual_gradients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    gradient_text TEXT NOT NULL,
                    cluster_id INTEGER DEFAULT 0,
                    semantic_weight REAL DEFAULT 1.0,
                    timestamp INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES scan_sessions(session_id) ON DELETE CASCADE
                );
                """
            )
        # Auto-seed the 5 historical failure lifelines
        seed_historical_lifelines(db_path)
    finally:
        conn.close()


def seed_historical_lifelines(db_path: str = DEFAULT_DB_PATH) -> int:
    """Seeds the 5 August 23/24 historical failure lifelines. Idempotent."""
    conn = get_db_connection(db_path)
    inserted_count = 0
    try:
        with conn:
            cursor = conn.cursor()
            for lifeline in HISTORICAL_LIFELINES_DATA:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO historical_lifelines (
                        lifeline_code,
                        title,
                        detector_type,
                        root_cause,
                        remediation,
                        failure_session_date,
                        target_pattern,
                        severity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        lifeline["lifeline_code"],
                        lifeline["title"],
                        lifeline["detector_type"],
                        lifeline["root_cause"],
                        lifeline["remediation"],
                        lifeline["failure_session_date"],
                        lifeline["target_pattern"],
                        lifeline["severity"],
                    ),
                )
                if cursor.rowcount > 0:
                    inserted_count += cursor.rowcount
        return inserted_count
    finally:
        conn.close()


def log_scan_session(
    session_id: str,
    anomalies: List[Union[AnomalyRecord, Dict[str, Any]]],
    gradients: List[Union[str, Dict[str, Any]]],
    duration_ms: float,
    db_path: str = DEFAULT_DB_PATH,
    entropy_score: float = 0.0,
    timestamp: Optional[int] = None,
) -> None:
    """Atomically logs a scan session, its anomalies, and generated textual gradients."""
    ts = timestamp if timestamp is not None else int(time.time())
    conn = get_db_connection(db_path)
    try:
        # Atomic transaction
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scan_sessions (
                    session_id,
                    timestamp,
                    duration_ms,
                    total_anomalies,
                    entropy_score
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (session_id, ts, float(duration_ms), len(anomalies), float(entropy_score)),
            )

            for anomaly in anomalies:
                if isinstance(anomaly, AnomalyRecord):
                    det_type = anomaly.detector_type.value if isinstance(anomaly.detector_type, DetectorType) else str(anomaly.detector_type)
                    target_path = anomaly.target_path
                    sev = anomaly.severity.value if isinstance(anomaly.severity, Severity) else str(anomaly.severity)
                    desc = anomaly.description
                    raw_details = json.dumps(anomaly.raw_details)
                    is_hist = 1 if anomaly.is_historical else 0
                    anom_ts = anomaly.timestamp if anomaly.timestamp > 0 else ts
                    conf = anomaly.confidence
                elif isinstance(anomaly, dict):
                    det_type = str(anomaly.get("detector_type", ""))
                    target_path = str(anomaly.get("target_path", ""))
                    sev = str(anomaly.get("severity", ""))
                    desc = str(anomaly.get("description", ""))
                    raw_details = json.dumps(anomaly.get("raw_details", {}))
                    is_hist = 1 if anomaly.get("is_historical", False) else 0
                    anom_ts = int(anomaly.get("timestamp", ts))
                    conf = float(anomaly.get("confidence", 1.0))
                else:
                    raise ValueError(f"Unsupported anomaly type: {type(anomaly)}")

                cursor.execute(
                    """
                    INSERT INTO anomalies (
                        session_id,
                        detector_type,
                        target_path,
                        severity,
                        description,
                        raw_details,
                        is_historical,
                        timestamp,
                        confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (session_id, det_type, target_path, sev, desc, raw_details, is_hist, anom_ts, conf),
                )

            for grad in gradients:
                if isinstance(grad, str):
                    grad_text = grad
                    cluster_id = 0
                    weight = 1.0
                elif isinstance(grad, dict):
                    grad_text = str(grad.get("gradient_text", grad.get("text", "")))
                    cluster_id = int(grad.get("cluster_id", 0))
                    weight = float(grad.get("semantic_weight", 1.0))
                else:
                    raise ValueError(f"Unsupported gradient type: {type(grad)}")

                cursor.execute(
                    """
                    INSERT INTO textual_gradients (
                        session_id,
                        gradient_text,
                        cluster_id,
                        semantic_weight,
                        timestamp
                    ) VALUES (?, ?, ?, ?, ?);
                    """,
                    (session_id, grad_text, cluster_id, weight, ts),
                )
    finally:
        conn.close()


def get_session(session_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves session metadata by session_id."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT session_id, timestamp, duration_ms, total_anomalies, entropy_score, created_at
            FROM scan_sessions
            WHERE session_id = ?;
            """,
            (session_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        conn.close()


def get_anomalies_for_session(session_id: str, db_path: str = DEFAULT_DB_PATH) -> List[AnomalyRecord]:
    """Retrieves all anomaly records for a given session, deserializing raw_details."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT detector_type, target_path, severity, description, raw_details, is_historical, timestamp, confidence
            FROM anomalies
            WHERE session_id = ?
            ORDER BY id ASC;
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        records: List[AnomalyRecord] = []
        for r in rows:
            raw_details_dict = {}
            if r["raw_details"]:
                try:
                    raw_details_dict = json.loads(r["raw_details"])
                except json.JSONDecodeError:
                    raw_details_dict = {"raw": r["raw_details"]}
            records.append(
                AnomalyRecord(
                    detector_type=DetectorType(r["detector_type"]),
                    target_path=r["target_path"],
                    severity=Severity(r["severity"]),
                    description=r["description"],
                    raw_details=raw_details_dict,
                    is_historical=bool(r["is_historical"]),
                    timestamp=int(r["timestamp"]),
                    confidence=float(r["confidence"]),
                )
            )
        return records
    finally:
        conn.close()


def get_textual_gradients_for_session(session_id: str, db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """Retrieves all textual gradients logged for a given session."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT gradient_text
            FROM textual_gradients
            WHERE session_id = ?
            ORDER BY id ASC;
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        return [r["gradient_text"] for r in rows]
    finally:
        conn.close()


def get_historical_lifelines(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves all seeded historical failure lifelines."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, lifeline_code, title, detector_type, root_cause, remediation, failure_session_date, target_pattern, severity, created_at
            FROM historical_lifelines
            ORDER BY id ASC;
            """
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_historical_drift(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Calculates drift statistics across all logged sessions against historical failure lifelines."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()

        # Session metrics
        cursor.execute("SELECT COUNT(*) AS total_sessions, AVG(duration_ms) AS avg_duration, AVG(entropy_score) AS avg_entropy FROM scan_sessions;")
        sess_row = cursor.fetchone()
        total_sessions = sess_row["total_sessions"] if sess_row else 0
        avg_duration = float(sess_row["avg_duration"] or 0.0)
        avg_entropy = float(sess_row["avg_entropy"] or 0.0)

        # Anomaly metrics
        cursor.execute("SELECT COUNT(*) AS total_anomalies FROM anomalies;")
        anom_row = cursor.fetchone()
        total_anomalies = anom_row["total_anomalies"] if anom_row else 0

        # Frequency by detector type
        cursor.execute("SELECT detector_type, COUNT(*) AS count FROM anomalies GROUP BY detector_type;")
        detector_dist = {r["detector_type"]: r["count"] for r in cursor.fetchall()}

        # Frequency by severity
        cursor.execute("SELECT severity, COUNT(*) AS count FROM anomalies GROUP BY severity;")
        severity_dist = {r["severity"]: r["count"] for r in cursor.fetchall()}

        # Historical lifelines comparison
        cursor.execute("SELECT lifeline_code, detector_type, severity FROM historical_lifelines;")
        lifelines = [dict(r) for r in cursor.fetchall()]

        lifelines_match_counts = {}
        for lf in lifelines:
            det = lf["detector_type"]
            lifelines_match_counts[lf["lifeline_code"]] = detector_dist.get(det, 0)

        return {
            "total_sessions": total_sessions,
            "total_anomalies": total_anomalies,
            "detector_distribution": detector_dist,
            "severity_distribution": severity_dist,
            "average_duration_ms": avg_duration,
            "average_entropy_score": avg_entropy,
            "historical_lifelines_count": len(lifelines),
            "historical_match_counts": lifelines_match_counts,
            "drift_detected": total_anomalies > 0,
        }
    finally:
        conn.close()
