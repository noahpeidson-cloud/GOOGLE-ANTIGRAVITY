"""
manifest_store.py - SQLite state tracker for Zero-Compression Ingestion Daemon.
Tracks full lifecycle: DISCOVERED -> RECORDING -> DOWNLOADING -> DOWNLOADED -> HASH_VERIFIED -> UPLOADING -> GCS_CONFIRMED (or FAILED / QUARANTINED).
"""

import sqlite3
import datetime
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Generator

logger = logging.getLogger("ManifestStore")


class ManifestStore:
    """
    SQLite transactional manifest store for tracking device media files,
    cryptographic checksums, staging paths, GCS blobs, and sync statuses.
    """

    VALID_STATUSES = {
        "DISCOVERED",
        "RECORDING",
        "DOWNLOADING",
        "DOWNLOADED",
        "HASH_VERIFIED",
        "UPLOADING",
        "GCS_CONFIRMED",
        "FAILED",
        "QUARANTINED",
    }

    def __init__(self, db_path: str = "ingestion_manifest.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_manifest (
                file_id TEXT PRIMARY KEY,
                device_ip TEXT NOT NULL,
                device_path TEXT NOT NULL UNIQUE,
                file_name TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                device_mtime INTEGER NOT NULL,
                device_sha256 TEXT,
                local_staging_path TEXT,
                local_sha256 TEXT,
                gcs_bucket TEXT,
                gcs_blob_name TEXT,
                gcs_crc32c TEXT,
                gcs_md5 TEXT,
                status TEXT NOT NULL CHECK(status IN (
                    'DISCOVERED', 
                    'RECORDING', 
                    'DOWNLOADING', 
                    'DOWNLOADED', 
                    'HASH_VERIFIED', 
                    'UPLOADING', 
                    'GCS_CONFIRMED', 
                    'FAILED',
                    'QUARANTINED'
                )),
                retry_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_manifest_status ON ingestion_manifest(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_manifest_device_path ON ingestion_manifest(device_path);")

    def register_discovered(
        self,
        device_ip: str,
        device_path: str,
        file_name: str,
        size: int,
        mtime: int,
        status: str = "DISCOVERED",
    ) -> bool:
        """
        Registers a newly discovered media file on the remote device.
        Returns True if newly inserted, False if already present.
        """
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO ingestion_manifest (
                        file_id, device_ip, device_path, file_name, file_size_bytes, 
                        device_mtime, status, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (device_path, device_ip, device_path, file_name, size, mtime, status, now_iso),
                )
                return True
            except sqlite3.IntegrityError:
                # Update size and mtime if currently in RECORDING or DISCOVERED state
                conn.execute(
                    """
                    UPDATE ingestion_manifest 
                    SET file_size_bytes = ?, device_mtime = ?, status = ?, updated_at = ?
                    WHERE device_path = ? AND status IN ('DISCOVERED', 'RECORDING')
                    """,
                    (size, mtime, status, now_iso, device_path),
                )
                return False

    def update_status(self, device_path: str, status: str, **kwargs) -> bool:
        """
        Updates the sync status and optional columns (e.g. device_sha256, local_sha256, gcs_blob_name).
        """
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        set_clauses = ["status = ?", "updated_at = ?"]
        params: List[Any] = [status, now_iso]

        allowed_fields = {
            "file_id",
            "device_ip",
            "file_name",
            "file_size_bytes",
            "device_mtime",
            "device_sha256",
            "local_staging_path",
            "local_sha256",
            "gcs_bucket",
            "gcs_blob_name",
            "gcs_crc32c",
            "gcs_md5",
            "retry_count",
            "last_error",
        }

        for k, v in kwargs.items():
            if k in allowed_fields:
                set_clauses.append(f"{k} = ?")
                params.append(v)

        params.append(device_path)

        with self._get_conn() as conn:
            cur = conn.execute(
                f"UPDATE ingestion_manifest SET {', '.join(set_clauses)} WHERE device_path = ?",
                params,
            )
            return cur.rowcount > 0

    def increment_retry(self, device_path: str, error_msg: Optional[str] = None) -> int:
        """
        Increments the retry counter and updates the last error message.
        Returns the new retry count.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE ingestion_manifest 
                SET retry_count = retry_count + 1, last_error = ?, updated_at = ?
                WHERE device_path = ?
                """,
                (error_msg, now_iso, device_path),
            )
            cur = conn.execute(
                "SELECT retry_count FROM ingestion_manifest WHERE device_path = ?",
                (device_path,),
            )
            row = cur.fetchone()
            return row["retry_count"] if row else 0

    def mark_quarantined(self, device_path: str, error_msg: str) -> bool:
        """
        Marks a file as QUARANTINED due to cryptographic hash corruption.
        """
        return self.update_status(device_path, "QUARANTINED", last_error=error_msg)

    def mark_failed(self, device_path: str, error_msg: str) -> bool:
        """
        Marks a file as FAILED after exceeding max retries or unrecoverable error.
        """
        return self.update_status(device_path, "FAILED", last_error=error_msg)

    def get_record(self, device_path: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single manifest record by device_path.
        """
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT * FROM ingestion_manifest WHERE device_path = ?",
                (device_path,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_record_by_file_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single manifest record by file_id.
        """
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT * FROM ingestion_manifest WHERE file_id = ?",
                (file_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_all_records(self) -> List[Dict[str, Any]]:
        """
        Retrieves all records in the manifest.
        """
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM ingestion_manifest ORDER BY created_at ASC")
            return [dict(r) for r in cur.fetchall()]

    def get_pending_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves records eligible for processing.
        """
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM ingestion_manifest 
                WHERE status IN ('DISCOVERED', 'DOWNLOADED', 'HASH_VERIFIED') 
                ORDER BY device_mtime ASC LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
