"""
Curated Memory Hub for Google Antigravity & AI Platform.
Implements the NVIDIA Labs Object-Oriented Agents (NOOA) durable memory standard:
- Agent-curated, inspectable SQLite store on D: drive
- Typed records with domain track, importance score, and relational graph
- Active reflection, superseding, and pruning to prevent context rot and recency bias
"""

import sqlite3
import uuid
import json
import os
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

DEFAULT_DB_PATH = Path(r"D:\AI_Platform\telemetry\vector_memory\vector_memory.db")

@dataclass
class MemoryRecord:
    id: str
    timestamp: str
    domain_track: str
    topic: str
    finding_summary: str
    evidence_source: str
    importance_score: int
    status: str = "active"  # active, superseded, deprecated
    relationship_type: Optional[str] = None  # supports, contradicts, replaces, derived-from
    related_id: Optional[str] = None
    metadata_json: str = "{}"

class CuratedMemoryHub:
    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = DEFAULT_DB_PATH

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curated_memory (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    domain_track TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    finding_summary TEXT NOT NULL,
                    evidence_source TEXT NOT NULL,
                    importance_score INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    relationship_type TEXT,
                    related_id TEXT,
                    metadata_json TEXT DEFAULT '{}'
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_track ON curated_memory(domain_track);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_topic ON curated_memory(topic);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_importance ON curated_memory(importance_score);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_status ON curated_memory(status);")

            # Kiro Crew & Amazon Quick inspired durable checkpointing table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    session_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    domain_track TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    checkpoint_hash TEXT NOT NULL,
                    token_budget_used INTEGER DEFAULT 0
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ckpt_session ON session_checkpoints(session_name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ckpt_track ON session_checkpoints(domain_track);")
            conn.commit()

    def record(
        self,
        topic: str,
        finding_summary: str,
        domain_track: str = "platform",
        importance_score: int = 5,
        evidence_source: str = "session",
        relationship_type: Optional[str] = None,
        related_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        rec_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(metadata or {})

        with self._get_connection() as conn:
            if relationship_type == "replaces" and related_id:
                conn.execute(
                    "UPDATE curated_memory SET status = 'superseded' WHERE id = ?",
                    (related_id,)
                )

            conn.execute("""
                INSERT INTO curated_memory (
                    id, timestamp, domain_track, topic, finding_summary,
                    evidence_source, importance_score, status, relationship_type,
                    related_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """, (
                rec_id, timestamp, domain_track, topic, finding_summary,
                evidence_source, importance_score, relationship_type,
                related_id, meta_str
            ))
            conn.commit()
        return rec_id

    def get_record(self, record_id: str) -> Optional[MemoryRecord]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM curated_memory WHERE id = ?", (record_id,)
            ).fetchone()
            if row:
                return MemoryRecord(**dict(row))
        return None

    def list_records(self, domain_track: Optional[str] = None, status: str = "active") -> List[MemoryRecord]:
        with self._get_connection() as conn:
            if domain_track:
                rows = conn.execute(
                    "SELECT * FROM curated_memory WHERE domain_track = ? AND status = ? ORDER BY importance_score DESC, timestamp DESC",
                    (domain_track, status)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM curated_memory WHERE status = ? ORDER BY importance_score DESC, timestamp DESC",
                    (status,)
                ).fetchall()
            return [MemoryRecord(**dict(r)) for r in rows]

    def query(self, topic: Optional[str] = None, domain_track: Optional[str] = None, min_importance: int = 1) -> List[MemoryRecord]:
        query_str = "SELECT * FROM curated_memory WHERE status = 'active' AND importance_score >= ?"
        params = [min_importance]

        if domain_track:
            query_str += " AND domain_track = ?"
            params.append(domain_track)

        if topic:
            query_str += " AND (topic LIKE ? OR finding_summary LIKE ?)"
            params.extend([f"%{topic}%", f"%{topic}%"])

        query_str += " ORDER BY importance_score DESC, timestamp DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query_str, params).fetchall()
            return [MemoryRecord(**dict(r)) for r in rows]

    def deprecate(self, record_id: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE curated_memory SET status = 'deprecated' WHERE id = ?", (record_id,))
            conn.commit()

    def get_dossier(self, domain_track: str) -> str:
        records = self.list_records(domain_track=domain_track, status="active")
        if not records:
            return f"No active curated memory for domain track: {domain_track}"

        lines = [f"# Curated Knowledge Dossier: {domain_track.upper()}", ""]
        for rec in records:
            lines.append(f"- **[{rec.topic}]** (Importance: {rec.importance_score}/10): {rec.finding_summary}")
            lines.append(f"  *Source: {rec.evidence_source} | Timestamp: {rec.timestamp}*")
        return "\n".join(lines)

    def save_checkpoint(
        self,
        session_name: str,
        domain_track: str,
        state_data: Dict[str, Any],
        token_budget_used: int = 0
    ) -> Dict[str, Any]:
        """
        Kiro Crew-style persistent session checkpointing.
        Saves structured agent state and computes a SHA-256 tamper-evident integrity hash.
        """
        ckpt_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        state_json = json.dumps(state_data, sort_keys=True)
        
        # SHA-256 integrity hash across session, track, state, and timestamp
        hasher = hashlib.sha256()
        hasher.update(f"{session_name}:{domain_track}:{timestamp}:{state_json}".encode("utf-8"))
        ckpt_hash = hasher.hexdigest()

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO session_checkpoints (
                    checkpoint_id, session_name, timestamp, domain_track,
                    state_json, checkpoint_hash, token_budget_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ckpt_id, session_name, timestamp, domain_track, state_json, ckpt_hash, token_budget_used))
            conn.commit()

        return {
            "checkpoint_id": ckpt_id,
            "session_name": session_name,
            "timestamp": timestamp,
            "domain_track": domain_track,
            "checkpoint_hash": ckpt_hash,
            "token_budget_used": token_budget_used
        }

    def get_latest_checkpoint(self, session_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent checkpoint for a given research/coding session."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM session_checkpoints 
                WHERE session_name = ? 
                ORDER BY timestamp DESC LIMIT 1
            """, (session_name,)).fetchone()
            if row:
                d = dict(row)
                d["state"] = json.loads(d["state_json"])
                return d
        return None

    def list_checkpoints(self, session_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all persistent session checkpoints."""
        with self._get_connection() as conn:
            if session_name:
                rows = conn.execute("""
                    SELECT checkpoint_id, session_name, timestamp, domain_track, checkpoint_hash, token_budget_used
                    FROM session_checkpoints
                    WHERE session_name = ?
                    ORDER BY timestamp DESC
                """, (session_name,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT checkpoint_id, session_name, timestamp, domain_track, checkpoint_hash, token_budget_used
                    FROM session_checkpoints
                    ORDER BY timestamp DESC
                """).fetchall()
            return [dict(r) for r in rows]

