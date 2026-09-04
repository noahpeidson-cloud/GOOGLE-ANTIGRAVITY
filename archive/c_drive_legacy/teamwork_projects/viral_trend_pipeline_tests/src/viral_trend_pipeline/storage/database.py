"""SQLite storage layer and database operations for Viral Trend Pipeline."""

from datetime import datetime, timezone, timedelta
import json
import sqlite3
from typing import Optional, Dict, Any, List, Union

from viral_trend_pipeline.models import TrendRecord, get_default_date


class SQLiteTrendStore:
    """SQLite-backed storage engine for extracted viral trend records."""

    DDL_SCHEMA = """
    CREATE TABLE IF NOT EXISTS trends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag TEXT NOT NULL,
        platform TEXT NOT NULL CHECK (platform IN ('tiktok', 'instagram', 'youtube', 'facebook')),
        category TEXT NOT NULL CHECK (category IN ('sports_cards', 'edm', 'general')),
        trend_type TEXT DEFAULT 'hashtag',
        raw_title TEXT,
        date_added TEXT NOT NULL,
        rank INTEGER,
        post_count INTEGER,
        velocity_metric REAL,
        editing_style TEXT,
        engagement_metrics TEXT NOT NULL,
        raw_metadata TEXT,
        created_at TEXT DEFAULT (datetime('now', 'utc'))
    );

    CREATE INDEX IF NOT EXISTS idx_trends_date_added ON trends(date_added);
    CREATE INDEX IF NOT EXISTS idx_trends_platform_cat ON trends(platform, category);
    CREATE INDEX IF NOT EXISTS idx_trends_tag ON trends(tag);
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize the store with given database path (defaults to in-memory)."""
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Create connection and configure sqlite settings."""
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._connection:
            self._connection.execute("PRAGMA foreign_keys = ON;")
        self.initialize_schema()

    @property
    def connection(self) -> sqlite3.Connection:
        """Return active sqlite3 connection."""
        if self._connection is None:
            self._initialize_connection()
        return self._connection

    def initialize_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self.connection:
            self.connection.executescript(self.DDL_SCHEMA)

    def _normalize_record_dict(self, record: Union[TrendRecord, Dict[str, Any]]) -> Dict[str, Any]:
        """Convert TrendRecord or dictionary into standardized database row dict."""
        if isinstance(record, TrendRecord):
            rec_dict = record.to_dict()
        else:
            rec_dict = dict(record)

        tag = rec_dict.get("normalized_tag") or rec_dict.get("tag") or rec_dict.get("raw_title") or ""
        platform = rec_dict.get("platform")
        category = rec_dict.get("category", "general")
        trend_type = rec_dict.get("trend_type", "hashtag")
        raw_title = rec_dict.get("raw_title", tag)
        date_added = rec_dict.get("date_added") or get_default_date()
        rank = rec_dict.get("rank")
        post_count = rec_dict.get("post_count")
        velocity_metric = rec_dict.get("velocity_metric")
        editing_style = rec_dict.get("editing_style")

        eng_metrics = rec_dict.get("engagement_metrics") or {}
        if not isinstance(eng_metrics, str):
            eng_metrics_str = json.dumps(eng_metrics)
        else:
            eng_metrics_str = eng_metrics

        raw_meta = rec_dict.get("raw_metadata") or {}
        if not isinstance(raw_meta, str):
            raw_meta_str = json.dumps(raw_meta)
        else:
            raw_meta_str = raw_meta

        return {
            "tag": tag,
            "platform": platform,
            "category": category,
            "trend_type": trend_type,
            "raw_title": raw_title,
            "date_added": date_added,
            "rank": rank,
            "post_count": post_count,
            "velocity_metric": velocity_metric,
            "editing_style": editing_style,
            "engagement_metrics": eng_metrics_str,
            "raw_metadata": raw_meta_str,
        }

    def _row_to_record(self, row: sqlite3.Row) -> TrendRecord:
        """Convert a sqlite3.Row to a TrendRecord."""
        eng_raw = row["engagement_metrics"]
        try:
            eng_metrics = json.loads(eng_raw) if eng_raw else {}
        except Exception:
            eng_metrics = {}

        meta_raw = row["raw_metadata"]
        try:
            raw_meta = json.loads(meta_raw) if meta_raw else {}
        except Exception:
            raw_meta = {}

        return TrendRecord(
            platform=row["platform"],
            category=row["category"],
            trend_type=row["trend_type"] if "trend_type" in row.keys() else "hashtag",
            raw_title=row["raw_title"] if ("raw_title" in row.keys() and row["raw_title"]) else row["tag"],
            normalized_tag=row["tag"],
            date_added=row["date_added"],
            rank=row["rank"],
            post_count=row["post_count"],
            velocity_metric=row["velocity_metric"],
            editing_style=row["editing_style"],
            engagement_metrics=eng_metrics,
            raw_metadata=raw_meta,
        )

    def insert_trend(self, record: Union[TrendRecord, Dict[str, Any]]) -> int:
        """Insert a single trend record. Returns the new row id."""
        data = self._normalize_record_dict(record)
        query = """
        INSERT INTO trends (
            tag, platform, category, trend_type, raw_title, date_added,
            rank, post_count, velocity_metric, editing_style,
            engagement_metrics, raw_metadata
        ) VALUES (
            :tag, :platform, :category, :trend_type, :raw_title, :date_added,
            :rank, :post_count, :velocity_metric, :editing_style,
            :engagement_metrics, :raw_metadata
        );
        """
        with self.connection:
            cursor = self.connection.execute(query, data)
            return cursor.lastrowid

    def insert_trends_batch(self, records: List[Union[TrendRecord, Dict[str, Any]]], chunk_size: int = 500) -> int:
        """Insert multiple trend records in chunked transactions. Returns total inserted count."""
        if not records:
            return 0

        query = """
        INSERT INTO trends (
            tag, platform, category, trend_type, raw_title, date_added,
            rank, post_count, velocity_metric, editing_style,
            engagement_metrics, raw_metadata
        ) VALUES (
            :tag, :platform, :category, :trend_type, :raw_title, :date_added,
            :rank, :post_count, :velocity_metric, :editing_style,
            :engagement_metrics, :raw_metadata
        );
        """
        total_inserted = 0
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i + chunk_size]
            data_chunk = [self._normalize_record_dict(r) for r in chunk]
            with self.connection:
                self.connection.executemany(query, data_chunk)
            total_inserted += len(data_chunk)

        return total_inserted

    def get_total_count(self) -> int:
        """Return total row count in the trends table."""
        cursor = self.connection.execute("SELECT COUNT(*) FROM trends;")
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_records_in_window(
        self,
        anchor_date: Optional[str] = None,
        window_days: int = 14,
        platform: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[TrendRecord]:
        """Fetch records within the rolling window [anchor_date - window_days, anchor_date]."""
        anchor = get_default_date(anchor_date)
        query = """
        SELECT * FROM trends
        WHERE date_added >= date(?, '-' || ? || ' days')
          AND date_added <= date(?)
        """
        params: List[Any] = [anchor, window_days, anchor]

        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY date_added DESC, id DESC;"
        cursor = self.connection.execute(query, params)
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def fetch_all(self) -> List[TrendRecord]:
        """Fetch all records in the trends table."""
        cursor = self.connection.execute("SELECT * FROM trends ORDER BY date_added DESC, id DESC;")
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def seed_30_day_trends(
        self,
        anchor_date: Optional[str] = "2026-08-22",
        records_per_day: int = 2,
        total_days: int = 30,
    ) -> List[TrendRecord]:
        """Helper to seed deterministic multi-day trend records for test validation.
        Days 0 to 14 (15 calendar days): Active rolling window.
        Days 15 to 29 (15 calendar days): Expired window.
        """
        anchor_dt = datetime.strptime(get_default_date(anchor_date), "%Y-%m-%d")
        records: List[TrendRecord] = []

        platforms = ["tiktok", "instagram", "youtube", "facebook"]
        categories = ["sports_cards", "edm"]
        editing_styles = ["fast cuts", "stutter edit", "slow zoom", "seamless loop"]

        sports_card_tags = ["SportsCards", "CardLadder", "PaniniPrizm", "TheHobby", "Wembanyama"]
        edm_tags = ["HardTechno", "RaveTok", "EDMDrop", "Ultra2026", "TechnoBunker"]

        for day_offset in range(total_days):
            current_date = (anchor_dt - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            for r_idx in range(records_per_day):
                global_idx = day_offset * records_per_day + r_idx
                platform = platforms[global_idx % len(platforms)]
                category = categories[global_idx % len(categories)]
                editing_style = editing_styles[global_idx % len(editing_styles)]

                if category == "sports_cards":
                    tag = sports_card_tags[global_idx % len(sports_card_tags)]
                    raw_title = f"#{tag} rookie investment spike"
                else:
                    tag = edm_tags[global_idx % len(edm_tags)]
                    raw_title = f"#{tag} live set anthem"

                views = 50_000 + (30 - day_offset) * 5_000 + r_idx * 1_200
                velocity = round(50.0 + (30 - day_offset) * 1.5 + r_idx * 0.5, 2)
                rank = (global_idx % 10) + 1
                post_count = 1_000 + (30 - day_offset) * 100

                rec = TrendRecord(
                    platform=platform,
                    category=category,
                    trend_type="hashtag",
                    raw_title=raw_title,
                    normalized_tag=tag,
                    date_added=current_date,
                    rank=rank,
                    post_count=post_count,
                    velocity_metric=velocity,
                    editing_style=editing_style,
                    engagement_metrics={
                        "views": views,
                        "likes": int(views * 0.1),
                        "shares": int(views * 0.02),
                        "velocity_score": velocity,
                    },
                    raw_metadata={
                        "seed_day_offset": day_offset,
                        "seed_index": global_idx,
                    },
                )
                records.append(rec)

        self.insert_trends_batch(records)
        return records

    def close(self) -> None:
        """Close SQLite database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "SQLiteTrendStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
