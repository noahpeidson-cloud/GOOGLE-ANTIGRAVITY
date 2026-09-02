"""SQLite Telemetry Manager for Antigravity ML Agent.
Provides thread-safe WAL-mode persistence for scraping spans, dynamic execution policies,
and ProTeGi textual gradient logs.
"""

import json
import logging
import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger("unified_ops_hub.ml_agent.telemetry")


class TelemetryStore:
    """Thread-safe SQLite telemetry store with WAL mode concurrency for ML agent optimization."""

    def __init__(self, db_path: str) -> None:
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection with WAL mode and busy timeout."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def _init_db(self) -> None:
        """Initializes database schema and seeds baseline execution policies."""
        with self.get_connection() as conn:
            # 1. Master Scraping Telemetry Spans
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scraping_telemetry (
                    span_id TEXT PRIMARY KEY,
                    timestamp_ms INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    lens_type TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL CHECK(duration_ms >= 0),
                    yield_count INTEGER NOT NULL CHECK(yield_count >= 0),
                    error_count INTEGER NOT NULL CHECK(error_count >= 0),
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    status_code TEXT NOT NULL,
                    cluster_label INTEGER DEFAULT -1,
                    metadata_json TEXT DEFAULT '{}'
                )
                """
            )

            # Indexes
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_telemetry_platform_ts 
                ON scraping_telemetry(platform, timestamp_ms DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_telemetry_cluster 
                ON scraping_telemetry(cluster_label)
                """
            )

            # 2. Dynamic Execution Policies
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_policies (
                    platform TEXT PRIMARY KEY,
                    active_lens TEXT NOT NULL,
                    poll_interval_sec INTEGER NOT NULL CHECK(poll_interval_sec >= 60),
                    retry_backoff_base_sec REAL NOT NULL CHECK(retry_backoff_base_sec >= 1.0),
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    batch_size INTEGER NOT NULL DEFAULT 10,
                    last_adjusted_at INTEGER NOT NULL,
                    adjustment_reason TEXT NOT NULL,
                    policy_version INTEGER NOT NULL DEFAULT 1
                )
                """
            )

            # 3. ProTeGi Textual Gradient Logs
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS protegi_gradient_log (
                    gradient_id TEXT PRIMARY KEY,
                    timestamp_ms INTEGER NOT NULL,
                    target_skill_path TEXT NOT NULL,
                    divergence_entropy REAL NOT NULL,
                    critique_text TEXT NOT NULL,
                    gradient_diff TEXT NOT NULL,
                    applied_status TEXT NOT NULL CHECK(applied_status IN ('PROPOSED', 'AUDITED', 'APPLIED', 'REJECTED'))
                )
                """
            )

            # Seed Baseline Policies
            now_ms = int(time.time() * 1000)
            baseline_policies = [
                ("tiktok", "web_a11y_tree", 3600, 2.0, 3, 10, now_ms, "Initial baseline seed", 1),
                ("youtube_shorts", "web_a11y_tree", 7200, 2.0, 3, 10, now_ms, "Initial baseline seed", 1),
                ("instagram_reels", "android_ui_dump", 3600, 2.5, 3, 10, now_ms, "Initial baseline seed", 1),
                ("facebook_reels", "android_ui_dump", 14400, 2.0, 2, 5, now_ms, "Initial baseline seed", 1),
            ]

            conn.executemany(
                """
                INSERT OR IGNORE INTO execution_policies 
                (platform, active_lens, poll_interval_sec, retry_backoff_base_sec, max_retries, batch_size, last_adjusted_at, adjustment_reason, policy_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                baseline_policies,
            )
            conn.commit()

    def record_span(
        self,
        platform: str,
        lens_type: str,
        duration_ms: int,
        yield_count: int,
        error_count: int,
        status_code: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        span_id: Optional[str] = None,
        timestamp_ms: Optional[int] = None,
    ) -> str:
        """Records an execution span into SQLite with WAL safety."""
        actual_span_id = span_id or str(uuid.uuid4())
        actual_ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
        meta_json = json.dumps(metadata or {})

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO scraping_telemetry 
                (span_id, timestamp_ms, platform, lens_type, duration_ms, yield_count, error_count, input_tokens, output_tokens, status_code, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actual_span_id,
                    actual_ts,
                    platform,
                    lens_type,
                    int(duration_ms),
                    int(yield_count),
                    int(error_count),
                    int(input_tokens),
                    int(output_tokens),
                    status_code,
                    meta_json,
                ),
            )
            conn.commit()

        return actual_span_id

    def get_recent_spans(self, platform: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
        """Queries the most recent spans as a Pandas DataFrame."""
        query = "SELECT * FROM scraping_telemetry"
        params: List[Any] = []
        if platform:
            query += " WHERE platform = ?"
            params.append(platform)
        query += " ORDER BY timestamp_ms DESC LIMIT ?"
        params.append(limit)

        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        return df

    def update_cluster_labels(self, span_cluster_map: Dict[str, int]) -> None:
        """Updates cluster_label for the given span IDs."""
        if not span_cluster_map:
            return

        with self.get_connection() as conn:
            conn.executemany(
                "UPDATE scraping_telemetry SET cluster_label = ? WHERE span_id = ?",
                [(int(cluster), span_id) for span_id, cluster in span_cluster_map.items()],
            )
            conn.commit()

    def get_policy(self, platform: str) -> Optional[Dict[str, Any]]:
        """Fetches the execution policy for a given platform."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM execution_policies WHERE platform = ?", (platform,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_policies(self) -> Dict[str, Dict[str, Any]]:
        """Fetches all platform execution policies."""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM execution_policies").fetchall()
            return {row["platform"]: dict(row) for row in rows}

    def update_policy(
        self,
        platform: str,
        active_lens: str,
        poll_interval_sec: int,
        retry_backoff_base_sec: float,
        reason: str,
        batch_size: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        """Updates execution policy dials for a platform."""
        now_ms = int(time.time() * 1000)
        current = self.get_policy(platform)

        new_batch_size = batch_size if batch_size is not None else (current["batch_size"] if current else 10)
        new_max_retries = max_retries if max_retries is not None else (current["max_retries"] if current else 3)

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO execution_policies 
                (platform, active_lens, poll_interval_sec, retry_backoff_base_sec, max_retries, batch_size, last_adjusted_at, adjustment_reason, policy_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(platform) DO UPDATE SET
                    active_lens = excluded.active_lens,
                    poll_interval_sec = excluded.poll_interval_sec,
                    retry_backoff_base_sec = excluded.retry_backoff_base_sec,
                    max_retries = excluded.max_retries,
                    batch_size = excluded.batch_size,
                    last_adjusted_at = excluded.last_adjusted_at,
                    adjustment_reason = excluded.adjustment_reason,
                    policy_version = execution_policies.policy_version + 1
                """,
                (
                    platform,
                    active_lens,
                    int(poll_interval_sec),
                    float(retry_backoff_base_sec),
                    int(new_max_retries),
                    int(new_batch_size),
                    now_ms,
                    reason,
                ),
            )
            conn.commit()

    def log_protegi_gradient(
        self,
        target_skill_path: str,
        divergence_entropy: float,
        critique_text: str,
        gradient_diff: str,
        applied_status: str = "PROPOSED",
    ) -> str:
        """Logs a ProTeGi textual gradient alignment entry."""
        gradient_id = str(uuid.uuid4())
        now_ms = int(time.time() * 1000)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO protegi_gradient_log 
                (gradient_id, timestamp_ms, target_skill_path, divergence_entropy, critique_text, gradient_diff, applied_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (gradient_id, now_ms, target_skill_path, float(divergence_entropy), critique_text, gradient_diff, applied_status),
            )
            conn.commit()
        return gradient_id

    def mark_and_sweep_telemetry(self, retention_days: int = 14) -> int:
        """Purges telemetry spans older than retention_days to prevent database and context rot."""
        cutoff_ms = int(time.time() * 1000) - (retention_days * 86400 * 1000)
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM scraping_telemetry WHERE timestamp_ms < ?", (cutoff_ms,)
            )
            deleted_count = cursor.rowcount
            conn.commit()
        return deleted_count
