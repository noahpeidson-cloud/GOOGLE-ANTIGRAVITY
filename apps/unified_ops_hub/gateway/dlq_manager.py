"""Dead Letter Queue (DLQ) & Quarantine Architecture.
Thread-safe incident persistence (SQLite WAL + JSON audit artifacts),
exponential backoff scheduling, and automated/manual replay capabilities.
"""

import os
import json
import uuid
import time
import random
import shutil
import sqlite3
import logging
import threading
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Callable, Tuple

logger = logging.getLogger("unified_ops_hub.dlq")


class ErrorCategory(str, Enum):
    """Categorized root causes for Dead Letter Queue incidents."""
    CORRUPTED_PAYLOAD = "CORRUPTED_PAYLOAD"
    ML_GRADING_FAILURE = "ML_GRADING_FAILURE"
    SOCKET_COLLISION = "SOCKET_COLLISION"
    API_RATE_LIMIT = "API_RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    UNHANDLED_EXCEPTION = "UNHANDLED_EXCEPTION"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    CIRCUIT_BREAKER_TRIPPED = "CIRCUIT_BREAKER_TRIPPED"


class IncidentStatus(str, Enum):
    """Lifecycle states for a quarantined incident."""
    QUARANTINED = "QUARANTINED"
    RETRYING = "RETRYING"
    RESOLVED = "RESOLVED"
    EXHAUSTED = "EXHAUSTED"
    DISCARDED = "DISCARDED"


@dataclass
class DLQIncident:
    """Represents an isolated failure incident inside the Dead Letter Queue."""
    incident_id: str
    timestamp: str
    source_service: str
    error_category: ErrorCategory
    error_message: str
    payload: Dict[str, Any]
    traceback_str: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[str] = None
    status: IncidentStatus = IncidentStatus.QUARANTINED
    resolved_at: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the incident to a standard JSON-compatible dictionary."""
        data = asdict(self)
        data["error_category"] = self.error_category.value if isinstance(self.error_category, ErrorCategory) else self.error_category
        data["status"] = self.status.value if isinstance(self.status, IncidentStatus) else self.status
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DLQIncident":
        """Reconstitutes an incident from dictionary data."""
        return cls(
            incident_id=data["incident_id"],
            timestamp=data["timestamp"],
            source_service=data["source_service"],
            error_category=ErrorCategory(data["error_category"]),
            error_message=data["error_message"],
            payload=data.get("payload", {}),
            traceback_str=data.get("traceback_str"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            next_retry_at=data.get("next_retry_at"),
            status=IncidentStatus(data.get("status", IncidentStatus.QUARANTINED.value)),
            resolved_at=data.get("resolved_at"),
            history=data.get("history", []),
        )


class DLQManager:
    """Thread-safe Dead Letter Queue & Quarantine Manager."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        quarantine_dir: Optional[str] = None,
    ) -> None:
        self.db_path = db_path or os.path.join(os.getcwd(), "unified_ops_hub_dlq.db")
        self.quarantine_dir = quarantine_dir or os.path.join(os.getcwd(), "quarantine")
        
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)
        
        self._lock = threading.RLock()
        self._init_sqlite()

    def _get_connection(self) -> sqlite3.Connection:
        """Establishes an isolated SQLite connection configured with WAL and busy timeouts."""
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_sqlite(self) -> None:
        """Initializes the SQLite schema for DLQ incident logging."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dlq_incidents (
                        incident_id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        source_service TEXT NOT NULL,
                        error_category TEXT NOT NULL,
                        error_message TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        traceback_str TEXT,
                        retry_count INTEGER NOT NULL DEFAULT 0,
                        max_retries INTEGER NOT NULL DEFAULT 3,
                        next_retry_at TEXT,
                        status TEXT NOT NULL,
                        resolved_at TEXT,
                        history_json TEXT
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_dlq_status ON dlq_incidents (status);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_dlq_service ON dlq_incidents (source_service);"
                )
                conn.commit()

    @staticmethod
    def calculate_backoff_seconds(
        retry_count: int,
        base_backoff: float = 2.0,
        max_backoff: float = 300.0,
        jitter: bool = True,
    ) -> float:
        """Calculates exponential backoff delay with optional uniform jitter."""
        backoff = base_backoff * (2 ** retry_count)
        backoff = min(backoff, max_backoff)
        if jitter:
            backoff = backoff * random.uniform(0.8, 1.2)
        return round(backoff, 3)

    def record_failure(
        self,
        source_service: str,
        error_category: ErrorCategory,
        error_message: str,
        payload: Dict[str, Any],
        traceback_str: Optional[str] = None,
        max_retries: int = 3,
        base_backoff: float = 2.0,
    ) -> DLQIncident:
        """Records a failure into the DLQ, saves JSON audit artifact, and schedules initial retry."""
        now = datetime.now(timezone.utc)
        incident_id = str(uuid.uuid4())
        
        backoff_sec = self.calculate_backoff_seconds(0, base_backoff=base_backoff, jitter=False)
        next_retry_time = (now + timedelta(seconds=backoff_sec)).isoformat()
        
        history_entry = {
            "timestamp": now.isoformat(),
            "event": "RECORDED",
            "message": error_message,
        }
        
        incident = DLQIncident(
            incident_id=incident_id,
            timestamp=now.isoformat(),
            source_service=source_service,
            error_category=error_category,
            error_message=error_message,
            payload=payload,
            traceback_str=traceback_str,
            retry_count=0,
            max_retries=max_retries,
            next_retry_at=next_retry_time,
            status=IncidentStatus.QUARANTINED,
            resolved_at=None,
            history=[history_entry],
        )

        with self._lock:
            # 1. Write to SQLite
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO dlq_incidents (
                        incident_id, timestamp, source_service, error_category,
                        error_message, payload_json, traceback_str, retry_count,
                        max_retries, next_retry_at, status, resolved_at, history_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        incident.incident_id,
                        incident.timestamp,
                        incident.source_service,
                        incident.error_category.value,
                        incident.error_message,
                        json.dumps(incident.payload),
                        incident.traceback_str,
                        incident.retry_count,
                        incident.max_retries,
                        incident.next_retry_at,
                        incident.status.value,
                        incident.resolved_at,
                        json.dumps(incident.history),
                    ),
                )
                conn.commit()

            # 2. Write to JSON Audit Artifact
            self._write_json_artifact(incident)

        logger.warning(
            "DLQ Captured incident %s from [%s] Category=%s Msg=%s",
            incident_id,
            source_service,
            error_category.value,
            error_message,
        )
        return incident

    def _write_json_artifact(self, incident: DLQIncident) -> str:
        """Persists the incident as a JSON file in the quarantine directory."""
        path = os.path.join(self.quarantine_dir, f"dlq_{incident.incident_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(incident.to_dict(), f, indent=2)
            return path
        except Exception as exc:
            logger.error("Failed to write DLQ JSON artifact %s: %s", path, exc)
            return path

    def get_incident(self, incident_id: str) -> Optional[DLQIncident]:
        """Retrieves a single incident by ID."""
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM dlq_incidents WHERE incident_id = ?",
                    (incident_id,),
                ).fetchone()
                if not row:
                    return None
                return self._row_to_incident(row)

    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        category: Optional[ErrorCategory] = None,
        source_service: Optional[str] = None,
        limit: int = 100,
    ) -> List[DLQIncident]:
        """Lists incidents with optional filtering."""
        query = "SELECT * FROM dlq_incidents WHERE 1=1"
        params: List[Any] = []
        
        if status:
            query += " AND status = ?"
            params.append(status.value if isinstance(status, IncidentStatus) else status)
        if category:
            query += " AND error_category = ?"
            params.append(category.value if isinstance(category, ErrorCategory) else category)
        if source_service:
            query += " AND source_service = ?"
            params.append(source_service)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute(query, params).fetchall()
                return [self._row_to_incident(r) for r in rows]

    def update_incident_schedule(
        self,
        incident_id: str,
        next_retry_at: Optional[str] = None,
        status: Optional[IncidentStatus] = None,
    ) -> bool:
        """Manually updates the retry timestamp or status for an incident."""
        with self._lock:
            incident = self.get_incident(incident_id)
            if not incident:
                return False

            if next_retry_at is not None:
                incident.next_retry_at = next_retry_at
            if status is not None:
                incident.status = status

            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE dlq_incidents SET next_retry_at = ?, status = ? WHERE incident_id = ?",
                    (
                        incident.next_retry_at,
                        incident.status.value,
                        incident_id,
                    ),
                )
                conn.commit()

            self._write_json_artifact(incident)
            return True

    def replay_incident(
        self,
        incident_id: str,
        handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> Dict[str, Any]:
        """Replays an incident payload through a handler function or marks it resolved."""
        with self._lock:
            incident = self.get_incident(incident_id)
            if not incident:
                return {"success": False, "error": f"Incident {incident_id} not found."}

            now = datetime.now(timezone.utc)
            incident.retry_count += 1
            
            try:
                if handler:
                    result = handler(incident.payload)
                else:
                    result = {"replayed_manually": True}

                incident.status = IncidentStatus.RESOLVED
                incident.resolved_at = now.isoformat()
                incident.history.append({
                    "timestamp": now.isoformat(),
                    "event": "REPLAY_SUCCESS",
                    "retry_count": incident.retry_count,
                    "result": str(result),
                })
                self._save_incident(incident)
                return {"success": True, "incident_id": incident_id, "result": result}

            except Exception as exc:
                is_exhausted = incident.retry_count >= incident.max_retries
                incident.status = IncidentStatus.EXHAUSTED if is_exhausted else IncidentStatus.RETRYING
                
                backoff_sec = self.calculate_backoff_seconds(incident.retry_count)
                incident.next_retry_at = (now + timedelta(seconds=backoff_sec)).isoformat()
                incident.history.append({
                    "timestamp": now.isoformat(),
                    "event": "REPLAY_FAILED",
                    "retry_count": incident.retry_count,
                    "error": str(exc),
                })
                self._save_incident(incident)
                return {
                    "success": False,
                    "incident_id": incident_id,
                    "retry_count": incident.retry_count,
                    "status": incident.status.value,
                    "error": str(exc),
                }

    def process_retries(
        self,
        handlers: Optional[Dict[str, Callable[[Dict[str, Any]], Any]]] = None,
    ) -> Dict[str, Any]:
        """Scans for incidents eligible for automatic retry and runs them through service handlers."""
        now_iso = datetime.now(timezone.utc).isoformat()
        processed = []
        handlers_map = handlers or {}

        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM dlq_incidents
                    WHERE status IN ('QUARANTINED', 'RETRYING')
                      AND next_retry_at IS NOT NULL
                      AND next_retry_at <= ?
                    ORDER BY next_retry_at ASC
                    """,
                    (now_iso,),
                ).fetchall()
                
            incidents = [self._row_to_incident(r) for r in rows]

            for inc in incidents:
                handler = handlers_map.get(inc.source_service)
                if handler:
                    res = self.replay_incident(inc.incident_id, handler=handler)
                    processed.append(res)

        return {"processed_count": len(processed), "processed": processed}

    def quarantine_file(
        self,
        source_file_path: str,
        source_service: str,
        reason: str,
    ) -> Tuple[DLQIncident, str]:
        """Moves a corrupt or unprocessable file to the quarantine directory and records a DLQ incident."""
        with self._lock:
            if not os.path.exists(source_file_path):
                raise FileNotFoundError(f"Source file {source_file_path} does not exist.")

            filename = os.path.basename(source_file_path)
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            quarantined_filename = f"quarantined_{timestamp_str}_{filename}"
            quarantined_path = os.path.join(self.quarantine_dir, quarantined_filename)
            
            shutil.move(source_file_path, quarantined_path)

            incident = self.record_failure(
                source_service=source_service,
                error_category=ErrorCategory.CORRUPTED_PAYLOAD,
                error_message=reason,
                payload={
                    "original_path": source_file_path,
                    "quarantined_path": quarantined_path,
                    "file_size": os.path.getsize(quarantined_path),
                },
            )
            return incident, quarantined_path

    def get_stats(self) -> Dict[str, Any]:
        """Calculates aggregated metrics across all incidents."""
        with self._lock:
            with self._get_connection() as conn:
                total = conn.execute("SELECT COUNT(*) FROM dlq_incidents").fetchone()[0]
                quarantined = conn.execute(
                    "SELECT COUNT(*) FROM dlq_incidents WHERE status = 'QUARANTINED'"
                ).fetchone()[0]
                retrying = conn.execute(
                    "SELECT COUNT(*) FROM dlq_incidents WHERE status = 'RETRYING'"
                ).fetchone()[0]
                resolved = conn.execute(
                    "SELECT COUNT(*) FROM dlq_incidents WHERE status = 'RESOLVED'"
                ).fetchone()[0]
                exhausted = conn.execute(
                    "SELECT COUNT(*) FROM dlq_incidents WHERE status = 'EXHAUSTED'"
                ).fetchone()[0]

                # Category breakdown
                cat_rows = conn.execute(
                    "SELECT error_category, COUNT(*) FROM dlq_incidents GROUP BY error_category"
                ).fetchall()
                categories = {row[0]: row[1] for row in cat_rows}

                # Service breakdown
                svc_rows = conn.execute(
                    "SELECT source_service, COUNT(*) FROM dlq_incidents GROUP BY source_service"
                ).fetchall()
                services = {row[0]: row[1] for row in svc_rows}

        return {
            "total_incidents": total,
            "quarantined_count": quarantined,
            "retrying_count": retrying,
            "resolved_count": resolved,
            "exhausted_count": exhausted,
            "categories": categories,
            "services": services,
        }

    def export_dlq_report(self) -> Dict[str, Any]:
        """Exports a full forensic audit report."""
        incidents = self.list_incidents(limit=500)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stats": self.get_stats(),
            "incidents": [inc.to_dict() for inc in incidents],
        }

    def purge_resolved(self, older_than_seconds: Optional[int] = None) -> int:
        """Purges resolved incidents older than the specified threshold."""
        with self._lock:
            with self._get_connection() as conn:
                if older_than_seconds is not None:
                    cutoff = (
                        datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
                    ).isoformat()
                    cur = conn.execute(
                        "DELETE FROM dlq_incidents WHERE status = 'RESOLVED' AND resolved_at < ?",
                        (cutoff,),
                    )
                else:
                    cur = conn.execute("DELETE FROM dlq_incidents WHERE status = 'RESOLVED'")
                deleted_count = cur.rowcount
                conn.commit()
            return deleted_count

    def _save_incident(self, incident: DLQIncident) -> None:
        """Updates an existing incident in SQLite and rewrites the JSON audit artifact."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE dlq_incidents SET
                    retry_count = ?,
                    status = ?,
                    next_retry_at = ?,
                    resolved_at = ?,
                    history_json = ?
                WHERE incident_id = ?
                """,
                (
                    incident.retry_count,
                    incident.status.value,
                    incident.next_retry_at,
                    incident.resolved_at,
                    json.dumps(incident.history),
                    incident.incident_id,
                ),
            )
            conn.commit()
        self._write_json_artifact(incident)

    @staticmethod
    def _row_to_incident(row: sqlite3.Row) -> DLQIncident:
        """Transforms a SQLite row into a DLQIncident dataclass."""
        return DLQIncident(
            incident_id=row["incident_id"],
            timestamp=row["timestamp"],
            source_service=row["source_service"],
            error_category=ErrorCategory(row["error_category"]),
            error_message=row["error_message"],
            payload=json.loads(row["payload_json"]),
            traceback_str=row["traceback_str"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            next_retry_at=row["next_retry_at"],
            status=IncidentStatus(row["status"]),
            resolved_at=row["resolved_at"],
            history=json.loads(row["history_json"]) if row["history_json"] else [],
        )
