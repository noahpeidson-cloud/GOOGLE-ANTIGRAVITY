"""Media Catalog Manager for Unified Ops Hub.
Provides SQLite WAL-mode storage, foreign-key cascading, auto-updating triggers,
and thread-safe CRUD operations for Albums and Media Assets.
"""

import os
import json
import uuid
import sqlite3
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger("unified_ops_hub.media_catalog")


def _utc_now_iso() -> str:
    """Returns current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_proxy_url(proxy_path: Optional[str]) -> Optional[str]:
    """Normalizes a local or relative proxy path to a web-accessible /proxies/ URL."""
    if not proxy_path:
        return None
    normalized = proxy_path.replace("\\", "/")
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized
    if normalized.startswith("/proxies/"):
        return normalized
    if "proxies/" in normalized:
        parts = normalized.split("proxies/", 1)
        return f"/proxies/{parts[1].lstrip('/')}"
    return f"/proxies/{os.path.basename(normalized)}"


class MediaCatalogManager:
    """Thread-safe SQLite-backed manager for Albums and Media Catalog."""

    def __init__(self, db_path: str = "media_catalog.db", proxies_dir: Optional[str] = None) -> None:
        self.db_path = str(Path(db_path).resolve())
        self.proxies_dir = proxies_dir or str(Path(os.getcwd()) / "proxies")
        self._lock = threading.RLock()
        
        # Ensure parent directory exists
        db_parent = Path(self.db_path).parent
        db_parent.mkdir(parents=True, exist_ok=True)
        
        self.create_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection with WAL mode and foreign keys enabled."""
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def create_schema(self) -> None:
        """Creates tables, indexes, and triggers if they do not exist."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    # 1. Albums table
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS albums (
                            id TEXT PRIMARY KEY,
                            title TEXT NOT NULL,
                            description TEXT DEFAULT '',
                            cover_media_id TEXT,
                            media_count INTEGER NOT NULL DEFAULT 0,
                            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                        );
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_albums_created_at ON albums(created_at DESC);")

                    # 2. Media table
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS media (
                            id TEXT PRIMARY KEY,
                            album_id TEXT NOT NULL,
                            filename TEXT NOT NULL,
                            proxy_path TEXT NOT NULL,
                            raw_path TEXT,
                            duration REAL NOT NULL DEFAULT 0.0,
                            resolution TEXT NOT NULL DEFAULT '1080p',
                            file_size_bytes INTEGER NOT NULL DEFAULT 0,
                            upload_status TEXT NOT NULL DEFAULT 'LOCAL_READY' 
                                CHECK(upload_status IN ('LOCAL_READY', 'LOCAL', 'UPLOADING', 'UPLOADED', 'GCS_SYNCED', 'FAILED')),
                            grading_status TEXT NOT NULL DEFAULT 'UNGRADED' 
                                CHECK(grading_status IN ('UNGRADED', 'QUEUED', 'GRADING', 'GRADED', 'FAILED')),
                            grading_score REAL,
                            grading_verdict TEXT,
                            grading_details TEXT,
                            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                            FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE
                        );
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_album_id ON media(album_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_upload_status ON media(upload_status);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_grading_status ON media(grading_status);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_created_at ON media(created_at DESC);")

                    # 3. Triggers for atomic media count and cover thumbnail maintenance
                    conn.execute("""
                        CREATE TRIGGER IF NOT EXISTS trg_media_insert_count
                        AFTER INSERT ON media
                        BEGIN
                            UPDATE albums
                            SET media_count = media_count + 1,
                                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
                                cover_media_id = COALESCE(cover_media_id, NEW.id)
                            WHERE id = NEW.album_id;
                        END;
                    """)

                    conn.execute("""
                        CREATE TRIGGER IF NOT EXISTS trg_media_delete_count
                        AFTER DELETE ON media
                        BEGIN
                            UPDATE albums
                            SET media_count = MAX(0, media_count - 1),
                                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
                                cover_media_id = CASE
                                    WHEN cover_media_id = OLD.id THEN (SELECT id FROM media WHERE album_id = OLD.album_id AND id != OLD.id LIMIT 1)
                                    ELSE cover_media_id
                                END
                            WHERE id = OLD.album_id;
                        END;
                    """)
                logger.info("MediaCatalogManager database schema verified at %s", self.db_path)
            finally:
                conn.close()

    def create_album(
        self,
        title: str,
        description: Optional[str] = "",
        album_id: Optional[str] = None,
        cover_media_id: Optional[str] = None,
    ) -> str:
        """Creates a new album record and returns its ID."""
        aid = album_id or f"alb_{uuid.uuid4().hex[:8]}"
        now = _utc_now_iso()
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO albums (id, title, description, cover_media_id, media_count, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 0, ?, ?)
                        """,
                        (aid, title, description or "", cover_media_id, now, now),
                    )
                return aid
            finally:
                conn.close()

    def add_media_item(
        self,
        album_id: str,
        filename: str,
        proxy_path: str,
        raw_path: Optional[str] = None,
        duration: float = 0.0,
        resolution: str = "1080p",
        file_size_bytes: int = 0,
        upload_status: str = "LOCAL_READY",
        grading_status: str = "UNGRADED",
        grading_score: Optional[float] = None,
        grading_verdict: Optional[str] = None,
        grading_details: Optional[Union[str, Dict[str, Any]]] = None,
        media_id: Optional[str] = None,
    ) -> str:
        """Inserts a media item linked to an album and returns the media ID."""
        mid = media_id or f"med_{uuid.uuid4().hex[:8]}"
        now = _utc_now_iso()
        
        details_str: Optional[str] = None
        if isinstance(grading_details, dict):
            details_str = json.dumps(grading_details)
        elif isinstance(grading_details, str):
            details_str = grading_details

        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO media (
                            id, album_id, filename, proxy_path, raw_path, duration,
                            resolution, file_size_bytes, upload_status, grading_status,
                            grading_score, grading_verdict, grading_details, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            mid,
                            album_id,
                            filename,
                            proxy_path,
                            raw_path,
                            float(duration),
                            resolution,
                            int(file_size_bytes),
                            upload_status,
                            grading_status,
                            float(grading_score) if grading_score is not None else None,
                            grading_verdict,
                            details_str,
                            now,
                            now,
                        ),
                    )
                return mid
            finally:
                conn.close()

    def add_media(self, *args, **kwargs) -> str:
        """Alias for add_media_item."""
        return self.add_media_item(*args, **kwargs)

    def batch_add_media(self, album_id: str, media_items: List[Dict[str, Any]]) -> List[str]:
        """Atomically inserts multiple media records for an album."""
        created_ids: List[str] = []
        now = _utc_now_iso()
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    for item in media_items:
                        mid = item.get("id") or item.get("media_id") or f"med_{uuid.uuid4().hex[:8]}"
                        details = item.get("grading_details")
                        details_str = json.dumps(details) if isinstance(details, dict) else details

                        conn.execute(
                            """
                            INSERT INTO media (
                                id, album_id, filename, proxy_path, raw_path, duration,
                                resolution, file_size_bytes, upload_status, grading_status,
                                grading_score, grading_verdict, grading_details, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                mid,
                                album_id,
                                item["filename"],
                                item["proxy_path"],
                                item.get("raw_path"),
                                float(item.get("duration", 0.0)),
                                item.get("resolution", "1080p"),
                                int(item.get("file_size_bytes", 0)),
                                item.get("upload_status", "LOCAL_READY"),
                                item.get("grading_status", "UNGRADED"),
                                float(item["grading_score"]) if item.get("grading_score") is not None else None,
                                item.get("grading_verdict"),
                                details_str,
                                now,
                                now,
                            ),
                        )
                        created_ids.append(mid)
                return created_ids
            finally:
                conn.close()

    def get_albums(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieves list of albums with calculated media counts and cover proxy URLs."""
        with self._lock:
            conn = self._get_connection()
            try:
                query = """
                    SELECT 
                        a.id,
                        a.title,
                        a.description,
                        a.cover_media_id,
                        a.media_count,
                        a.created_at,
                        a.updated_at,
                        m.proxy_path AS cover_proxy_path
                    FROM albums a
                    LEFT JOIN media m ON a.cover_media_id = m.id
                    ORDER BY a.created_at DESC
                    LIMIT ? OFFSET ?
                """
                cursor = conn.execute(query, (limit, offset))
                rows = cursor.fetchall()
                albums = []
                for row in rows:
                    item = dict(row)
                    item["cover_proxy_url"] = _format_proxy_url(item.get("cover_proxy_path"))
                    albums.append(item)
                return albums
            finally:
                conn.close()

    def get_album(self, album_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single album by ID with cover proxy URL."""
        with self._lock:
            conn = self._get_connection()
            try:
                query = """
                    SELECT 
                        a.id,
                        a.title,
                        a.description,
                        a.cover_media_id,
                        a.media_count,
                        a.created_at,
                        a.updated_at,
                        m.proxy_path AS cover_proxy_path
                    FROM albums a
                    LEFT JOIN media m ON a.cover_media_id = m.id
                    WHERE a.id = ?
                """
                row = conn.execute(query, (album_id,)).fetchone()
                if not row:
                    return None
                album = dict(row)
                album["cover_proxy_url"] = _format_proxy_url(album.get("cover_proxy_path"))
                return album
            finally:
                conn.close()

    def get_album_media(
        self,
        album_id: str,
        limit: int = 200,
        offset: int = 0,
        grading_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves all media items belonging to an album."""
        with self._lock:
            conn = self._get_connection()
            try:
                if grading_status:
                    query = """
                        SELECT * FROM media 
                        WHERE album_id = ? AND grading_status = ?
                        ORDER BY created_at ASC
                        LIMIT ? OFFSET ?
                    """
                    cursor = conn.execute(query, (album_id, grading_status, limit, offset))
                else:
                    query = """
                        SELECT * FROM media 
                        WHERE album_id = ?
                        ORDER BY created_at ASC
                        LIMIT ? OFFSET ?
                    """
                    cursor = conn.execute(query, (album_id, limit, offset))
                
                rows = cursor.fetchall()
                media_list = []
                for row in rows:
                    item = dict(row)
                    item["proxy_url"] = _format_proxy_url(item.get("proxy_path"))
                    if item.get("grading_details"):
                        try:
                            item["grading_details"] = json.loads(item["grading_details"])
                        except Exception:
                            pass
                    media_list.append(item)
                return media_list
            finally:
                conn.close()

    def get_media(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single media record by ID."""
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute("SELECT * FROM media WHERE id = ?", (media_id,)).fetchone()
                if not row:
                    return None
                item = dict(row)
                item["proxy_url"] = _format_proxy_url(item.get("proxy_path"))
                if item.get("grading_details"):
                    try:
                        item["grading_details"] = json.loads(item["grading_details"])
                    except Exception:
                        pass
                return item
            finally:
                conn.close()

    def get_media_by_id(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Alias for get_media."""
        return self.get_media(media_id)

    def get_full_catalog(self) -> List[Dict[str, Any]]:
        """Retrieves the complete catalog of albums with nested media items via relational join."""
        with self._lock:
            conn = self._get_connection()
            try:
                albums_query = "SELECT * FROM albums ORDER BY created_at DESC"
                album_rows = conn.execute(albums_query).fetchall()
                
                catalog = []
                for a_row in album_rows:
                    album = dict(a_row)
                    media_query = "SELECT * FROM media WHERE album_id = ? ORDER BY created_at ASC"
                    media_rows = conn.execute(media_query, (album["id"],)).fetchall()
                    
                    media_items = []
                    for m_row in media_rows:
                        m_dict = dict(m_row)
                        m_dict["proxy_url"] = _format_proxy_url(m_dict.get("proxy_path"))
                        if m_dict.get("grading_details"):
                            try:
                                m_dict["grading_details"] = json.loads(m_dict["grading_details"])
                            except Exception:
                                pass
                        media_items.append(m_dict)
                    
                    album["media"] = media_items
                    album["cover_proxy_url"] = None
                    if album.get("cover_media_id"):
                        cover = next((m for m in media_items if m["id"] == album["cover_media_id"]), None)
                        if cover:
                            album["cover_proxy_url"] = cover.get("proxy_url")
                    if not album["cover_proxy_url"] and media_items:
                        album["cover_proxy_url"] = media_items[0].get("proxy_url")
                    
                    catalog.append(album)
                return catalog
            finally:
                conn.close()

    def update_grading_status(
        self,
        media_ids: Union[List[str], str],
        status: str,
        scores: Optional[Dict[str, float]] = None,
        grading_score: Optional[float] = None,
        grading_details: Optional[Union[str, Dict[str, Any]]] = None,
        grading_verdict: Optional[str] = None,
    ) -> None:
        """Updates grading status, score, verdict, and details for one or more media records."""
        ids = [media_ids] if isinstance(media_ids, str) else list(media_ids)
        if not ids:
            return

        now = _utc_now_iso()
        details_str: Optional[str] = None
        if isinstance(grading_details, dict):
            details_str = json.dumps(grading_details)
        elif isinstance(grading_details, str):
            details_str = grading_details

        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    for mid in ids:
                        # Individual score override from scores dict if provided
                        score_val = scores.get(mid) if scores and mid in scores else grading_score
                        
                        updates = ["grading_status = ?", "updated_at = ?"]
                        params: List[Any] = [status, now]

                        if score_val is not None:
                            updates.append("grading_score = ?")
                            params.append(float(score_val))

                        if grading_verdict is not None:
                            updates.append("grading_verdict = ?")
                            params.append(grading_verdict)

                        if details_str is not None:
                            updates.append("grading_details = ?")
                            params.append(details_str)

                        params.append(mid)
                        query = f"UPDATE media SET {', '.join(updates)} WHERE id = ?"
                        conn.execute(query, params)
            finally:
                conn.close()

    def update_media_upload_status(
        self,
        media_id: str,
        upload_status: str,
        raw_path: Optional[str] = None,
    ) -> bool:
        """Updates upload status and optional raw storage path."""
        now = _utc_now_iso()
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    if raw_path is not None:
                        cursor = conn.execute(
                            "UPDATE media SET upload_status = ?, raw_path = ?, updated_at = ? WHERE id = ?",
                            (upload_status, raw_path, now, media_id),
                        )
                    else:
                        cursor = conn.execute(
                            "UPDATE media SET upload_status = ?, updated_at = ? WHERE id = ?",
                            (upload_status, now, media_id),
                        )
                    return cursor.rowcount > 0
            finally:
                conn.close()

    def delete_album(self, album_id: str) -> bool:
        """Deletes an album and cascade-deletes all associated media items."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))
                    return cursor.rowcount > 0
            finally:
                conn.close()

    def delete_media(self, media_id: str) -> bool:
        """Deletes a single media item and decrements the album media_count via trigger."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.execute("DELETE FROM media WHERE id = ?", (media_id,))
                    return cursor.rowcount > 0
            finally:
                conn.close()

    def seed_sample_catalog(self) -> None:
        """Seeds initial mock albums and media if database is empty."""
        with self._lock:
            albums = self.get_albums()
            if albums:
                return

            alb1 = self.create_album(
                title="Ultra Miami 2026 Mainstage",
                description="4K 60FPS multi-cam raw captures from Mainstage Day 1",
                album_id="album_ultra_2026",
            )
            self.batch_add_media(
                alb1,
                [
                    {
                        "id": "med_ultra_01",
                        "filename": "clip_ultra_drop_4k_01.mp4",
                        "proxy_path": "proxies/clip_ultra_drop_4k_01_proxy.mp4",
                        "raw_path": "G:/My Drive/GOOGLE ANTIGRAVITY/unified_ops_hub/clip_ultra_drop_4k_01.mp4",
                        "duration": 30.0,
                        "resolution": "3840x2160",
                        "file_size_bytes": 317320,
                        "upload_status": "GCS_SYNCED",
                        "grading_status": "GRADED",
                        "grading_score": 88.74,
                        "grading_verdict": "VIRAL_READY",
                        "grading_details": {
                            "HRV": 92.4,
                            "DPAW": 88.0,
                            "ADR_SFD": 85.2,
                            "CKE_MVE": 90.1,
                            "LTSS": 86.5,
                            "recommendation": "Viral Ready. Recommend 9:16 vertical crop centered around 15.0s audio peak.",
                        },
                    },
                    {
                        "id": "med_ultra_02",
                        "filename": "clip_ultra_drop_4k_02.mp4",
                        "proxy_path": "proxies/audio_source_proxy.mp4",
                        "raw_path": "G:/My Drive/GOOGLE ANTIGRAVITY/unified_ops_hub/clip_ultra_drop_4k_02.mp4",
                        "duration": 25.0,
                        "resolution": "3840x2160",
                        "file_size_bytes": 284000,
                        "upload_status": "LOCAL_READY",
                        "grading_status": "UNGRADED",
                    },
                    {
                        "id": "med_ultra_03",
                        "filename": "clip_ultra_drop_4k_03.mp4",
                        "proxy_path": "proxies/raw_1080p_proxy.mp4",
                        "raw_path": "G:/My Drive/GOOGLE ANTIGRAVITY/unified_ops_hub/clip_ultra_drop_4k_03.mp4",
                        "duration": 20.0,
                        "resolution": "3840x2160",
                        "file_size_bytes": 245000,
                        "upload_status": "LOCAL_READY",
                        "grading_status": "UNGRADED",
                    },
                ],
            )
