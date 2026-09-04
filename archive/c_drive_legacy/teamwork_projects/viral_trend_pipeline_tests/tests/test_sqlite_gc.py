"""Integration test suite for SQLite Storage and Mark-and-Sweep Garbage Collection (Milestone M2 / R2)."""

from datetime import datetime, timedelta
import os
import sqlite3
import time
import pytest

from viral_trend_pipeline.models import TrendRecord
from viral_trend_pipeline.storage.database import SQLiteTrendStore
from viral_trend_pipeline.storage.garbage_collector import GarbageCollector


class TestSQLiteSchemaAndDDL:
    """Validate SQLite DDL schema creation, constraints, and basic CRUD operations."""

    def test_schema_initialization_tables_and_indexes(self, trend_store: SQLiteTrendStore):
        """Verify that table 'trends' and expected B-tree indexes are created."""
        cursor = trend_store.connection.cursor()
        
        # Check trends table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trends';")
        assert cursor.fetchone() is not None

        # Check indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = {row[0] for row in cursor.fetchall()}
        assert "idx_trends_date_added" in indexes
        assert "idx_trends_platform_cat" in indexes
        assert "idx_trends_tag" in indexes

    def test_platform_check_constraint(self, trend_store: SQLiteTrendStore):
        """Verify CHECK constraint rejects unsupported platform values."""
        invalid_record = TrendRecord(
            platform="twitter",  # Invalid platform
            category="sports_cards",
            trend_type="hashtag",
            raw_title="#SportsCards",
            normalized_tag="SportsCards",
            date_added="2026-08-22",
        )
        with pytest.raises(sqlite3.IntegrityError):
            trend_store.insert_trend(invalid_record)

    def test_category_check_constraint(self, trend_store: SQLiteTrendStore):
        """Verify CHECK constraint rejects unsupported category values."""
        invalid_record = TrendRecord(
            platform="tiktok",
            category="crypto_nfts",  # Invalid category
            trend_type="hashtag",
            raw_title="#Crypto",
            normalized_tag="Crypto",
            date_added="2026-08-22",
        )
        with pytest.raises(sqlite3.IntegrityError):
            trend_store.insert_trend(invalid_record)

    def test_single_trend_insertion_and_fetch(self, trend_store: SQLiteTrendStore):
        """Verify single record insertion, auto-increment ID, and round-trip retrieval."""
        record = TrendRecord(
            platform="tiktok",
            category="sports_cards",
            trend_type="hashtag",
            raw_title="#PaniniPrizm rookie rip",
            normalized_tag="PaniniPrizm",
            date_added="2026-08-22",
            rank=1,
            post_count=45000,
            velocity_metric=125.5,
            editing_style="fast cuts",
            engagement_metrics={"views": 500000, "likes": 35000, "shares": 5000},
            raw_metadata={"source": "test_fixture"},
        )
        row_id = trend_store.insert_trend(record)
        assert row_id == 1
        assert trend_store.get_total_count() == 1

        records = trend_store.fetch_all()
        assert len(records) == 1
        fetched = records[0]
        assert fetched.normalized_tag == "PaniniPrizm"
        assert fetched.platform == "tiktok"
        assert fetched.category == "sports_cards"
        assert fetched.date_added == "2026-08-22"
        assert fetched.velocity_metric == 125.5
        assert fetched.editing_style == "fast cuts"
        assert fetched.engagement_metrics["views"] == 500000

    def test_batch_insertion_across_chunk_boundary(self, trend_store: SQLiteTrendStore):
        """Verify chunked batch insertion for > 500 records."""
        records = []
        for i in range(600):
            records.append(
                TrendRecord(
                    platform="tiktok" if i % 2 == 0 else "instagram",
                    category="sports_cards" if i % 2 == 0 else "edm",
                    trend_type="hashtag",
                    raw_title=f"#Tag_{i}",
                    normalized_tag=f"Tag_{i}",
                    date_added="2026-08-22",
                    rank=(i % 10) + 1,
                    post_count=1000 + i,
                    velocity_metric=float(i),
                )
            )

        inserted_count = trend_store.insert_trends_batch(records, chunk_size=250)
        assert inserted_count == 600
        assert trend_store.get_total_count() == 600

    def test_file_backed_persistence(self, temp_trend_store: SQLiteTrendStore):
        """Verify that on-disk SQLite store persists data across connections."""
        record = TrendRecord(
            platform="youtube",
            category="edm",
            trend_type="video_title",
            raw_title="Ultra 2026 Live Set",
            normalized_tag="Ultra2026",
            date_added="2026-08-22",
            rank=1,
            velocity_metric=99.0,
        )
        temp_trend_store.insert_trend(record)
        db_path = temp_trend_store.db_path
        temp_trend_store.close()

        # Reopen same database file
        reopened_store = SQLiteTrendStore(db_path)
        try:
            assert reopened_store.get_total_count() == 1
            fetched = reopened_store.fetch_all()[0]
            assert fetched.normalized_tag == "Ultra2026"
            assert fetched.platform == "youtube"
        finally:
            reopened_store.close()


class Test30DaySeedingAndMarkSweep:
    """Validate the 30-day data seeding and 14-day mark-and-sweep garbage collection mechanics (R2)."""

    def test_30_day_seeding_and_exact_sweep_counts(self, trend_store: SQLiteTrendStore):
        """Seed 30 days (60 rows) with anchor 2026-08-22 and verify exact pre/post/purged counts."""
        anchor_date = "2026-08-22"
        # Seed 30 days * 2 records = 60 records
        seeded_records = trend_store.seed_30_day_trends(
            anchor_date=anchor_date,
            records_per_day=2,
            total_days=30,
        )
        assert len(seeded_records) == 60
        assert trend_store.get_total_count() == 60

        gc = GarbageCollector(trend_store)
        result = gc.sweep(anchor_date=anchor_date, cutoff_days=14)

        # Mathematical verification:
        # Window: [2026-08-08, 2026-08-22] -> 15 calendar days retained (offsets 0..14) -> 30 rows
        # Expired: [2026-07-24, 2026-08-07] -> 15 calendar days purged (offsets 15..29) -> 30 rows
        assert result["pre_count"] == 60
        assert result["purged_count"] == 30
        assert result["post_count"] == 30
        assert result["retained_count"] == 30
        assert trend_store.get_total_count() == 30

        # Verify retained date bounds in SQLite
        cursor = trend_store.connection.cursor()
        cursor.execute("SELECT MIN(date_added), MAX(date_added) FROM trends;")
        min_date, max_date = cursor.fetchone()
        assert min_date == "2026-08-08"
        assert max_date == "2026-08-22"

        # Verify no records strictly older than 2026-08-08 remain
        cursor.execute("SELECT COUNT(*) FROM trends WHERE date_added < '2026-08-08';")
        assert cursor.fetchone()[0] == 0

    def test_retained_records_window_query(self, trend_store: SQLiteTrendStore):
        """Verify get_records_in_window returns only active records sorted chronologically."""
        anchor_date = "2026-08-22"
        trend_store.seed_30_day_trends(anchor_date=anchor_date, records_per_day=2, total_days=30)
        gc = GarbageCollector(trend_store)
        gc.sweep(anchor_date=anchor_date, cutoff_days=14)

        window_records = trend_store.get_records_in_window(anchor_date=anchor_date, window_days=14)
        assert len(window_records) == 30

        # Check descending order of date_added
        dates = [r.date_added for r in window_records]
        assert dates == sorted(dates, reverse=True)
        assert all("2026-08-08" <= d <= "2026-08-22" for d in dates)


class TestBoundaryValueAnalysis:
    """Verify exact 14-day mathematical boundaries for mark-and-sweep deletion."""

    def test_bva_day_minus_13_is_retained(self, trend_store: SQLiteTrendStore):
        """Date = anchor - 13 days (2026-08-09) must be retained."""
        anchor = "2026-08-22"
        trend_store.insert_trend(
            TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title="#Day13",
                normalized_tag="Day13",
                date_added="2026-08-09",
            )
        )
        gc = GarbageCollector(trend_store)
        result = gc.sweep(anchor_date=anchor, cutoff_days=14)
        assert result["purged_count"] == 0
        assert result["retained_count"] == 1
        assert trend_store.get_total_count() == 1

    def test_bva_day_minus_14_is_retained(self, trend_store: SQLiteTrendStore):
        """Date = anchor - 14 days (2026-08-08) is the boundary and must be retained."""
        anchor = "2026-08-22"
        trend_store.insert_trend(
            TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title="#Day14Boundary",
                normalized_tag="Day14Boundary",
                date_added="2026-08-08",
            )
        )
        gc = GarbageCollector(trend_store)
        result = gc.sweep(anchor_date=anchor, cutoff_days=14)
        assert result["purged_count"] == 0
        assert result["retained_count"] == 1
        assert trend_store.get_total_count() == 1

    def test_bva_day_minus_15_is_purged(self, trend_store: SQLiteTrendStore):
        """Date = anchor - 15 days (2026-08-07) is expired and must be purged."""
        anchor = "2026-08-22"
        trend_store.insert_trend(
            TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title="#Day15Expired",
                normalized_tag="Day15Expired",
                date_added="2026-08-07",
            )
        )
        gc = GarbageCollector(trend_store)
        result = gc.sweep(anchor_date=anchor, cutoff_days=14)
        assert result["purged_count"] == 1
        assert result["retained_count"] == 0
        assert trend_store.get_total_count() == 0

    def test_bva_triple_point_boundary_simultaneous(self, trend_store: SQLiteTrendStore):
        """Insert records at T-13, T-14, and T-15 simultaneously; assert T-13 & T-14 retained, T-15 purged."""
        anchor = "2026-08-22"
        records = [
            TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title="#Day13",
                normalized_tag="Day13",
                date_added="2026-08-09",
            ),
            TrendRecord(
                platform="instagram",
                category="sports_cards",
                trend_type="hashtag",
                raw_title="#Day14",
                normalized_tag="Day14",
                date_added="2026-08-08",
            ),
            TrendRecord(
                platform="youtube",
                category="edm",
                trend_type="hashtag",
                raw_title="#Day15",
                normalized_tag="Day15",
                date_added="2026-08-07",
            ),
        ]
        trend_store.insert_trends_batch(records)
        assert trend_store.get_total_count() == 3

        gc = GarbageCollector(trend_store)
        result = gc.sweep(anchor_date=anchor, cutoff_days=14)
        assert result["pre_count"] == 3
        assert result["purged_count"] == 1
        assert result["retained_count"] == 2

        remaining_tags = {r.normalized_tag for r in trend_store.fetch_all()}
        assert "Day13" in remaining_tags
        assert "Day14" in remaining_tags
        assert "Day15" not in remaining_tags

    def test_bva_custom_cutoff_window(self, trend_store: SQLiteTrendStore):
        """Verify that cutoff_days parameter is customizable (e.g. 7-day window)."""
        anchor = "2026-08-22"
        # T-7 (2026-08-15) retained, T-8 (2026-08-14) purged
        trend_store.insert_trend(
            TrendRecord(
                platform="tiktok",
                category="edm",
                trend_type="hashtag",
                raw_title="#Day7",
                normalized_tag="Day7",
                date_added="2026-08-15",
            )
        )
        trend_store.insert_trend(
            TrendRecord(
                platform="tiktok",
                category="edm",
                trend_type="hashtag",
                raw_title="#Day8",
                normalized_tag="Day8",
                date_added="2026-08-14",
            )
        )
        gc = GarbageCollector(trend_store)
        result = gc.sweep(anchor_date=anchor, cutoff_days=7)
        assert result["pre_count"] == 2
        assert result["purged_count"] == 1
        assert result["retained_count"] == 1

        remaining = trend_store.fetch_all()
        assert len(remaining) == 1
        assert remaining[0].normalized_tag == "Day7"


class TestGCEdgeCases:
    """Validate edge cases: empty tables, all-expired, all-fresh, and sweep idempotency."""

    def test_edge_case_empty_db_sweep(self, trend_store: SQLiteTrendStore):
        """Mark-and-sweep on empty database completes without error and reports 0 counts."""
        assert trend_store.get_total_count() == 0
        gc = GarbageCollector(trend_store)
        result = gc.sweep(anchor_date="2026-08-22", cutoff_days=14)

        assert result["pre_count"] == 0
        assert result["purged_count"] == 0
        assert result["post_count"] == 0
        assert result["retained_count"] == 0
        assert trend_store.get_total_count() == 0

    def test_edge_case_all_expired_db(self, trend_store: SQLiteTrendStore):
        """Database with 50 rows all older than 20 days purges all 50 rows."""
        records = [
            TrendRecord(
                platform="facebook",
                category="edm",
                trend_type="hashtag",
                raw_title=f"#Old_{i}",
                normalized_tag=f"Old_{i}",
                date_added="2026-07-01",
            )
            for i in range(50)
        ]
        trend_store.insert_trends_batch(records)
        assert trend_store.get_total_count() == 50

        gc = GarbageCollector(trend_store)
        result = gc.sweep(anchor_date="2026-08-22", cutoff_days=14)

        assert result["pre_count"] == 50
        assert result["purged_count"] == 50
        assert result["post_count"] == 0
        assert result["retained_count"] == 0
        assert trend_store.get_total_count() == 0

    def test_edge_case_all_fresh_db(self, trend_store: SQLiteTrendStore):
        """Database with 50 rows all dated within the last 3 days purges 0 rows."""
        records = [
            TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title=f"#Fresh_{i}",
                normalized_tag=f"Fresh_{i}",
                date_added="2026-08-21",
            )
            for i in range(50)
        ]
        trend_store.insert_trends_batch(records)
        assert trend_store.get_total_count() == 50

        gc = GarbageCollector(trend_store)
        result = gc.sweep(anchor_date="2026-08-22", cutoff_days=14)

        assert result["pre_count"] == 50
        assert result["purged_count"] == 0
        assert result["post_count"] == 50
        assert result["retained_count"] == 50
        assert trend_store.get_total_count() == 50

    def test_edge_case_sweep_idempotency(self, trend_store: SQLiteTrendStore):
        """Running mark-and-sweep consecutively on the same anchor date purges 0 rows on the second pass."""
        trend_store.seed_30_day_trends(anchor_date="2026-08-22", records_per_day=2, total_days=30)
        gc = GarbageCollector(trend_store)

        # First sweep
        res1 = gc.sweep(anchor_date="2026-08-22", cutoff_days=14)
        assert res1["purged_count"] == 30
        assert res1["post_count"] == 30

        # Second sweep immediately after
        res2 = gc.sweep(anchor_date="2026-08-22", cutoff_days=14)
        assert res2["pre_count"] == 30
        assert res2["purged_count"] == 0
        assert res2["post_count"] == 30
        assert res2["retained_count"] == 30

    def test_edge_case_null_and_empty_metadata(self, trend_store: SQLiteTrendStore):
        """Ensure records with empty metrics or metadata dictionaries deserialize gracefully."""
        record = TrendRecord(
            platform="youtube",
            category="general",
            trend_type="hashtag",
            raw_title="#Minimal",
            normalized_tag="Minimal",
            date_added="2026-08-22",
            engagement_metrics={},
            raw_metadata={},
        )
        trend_store.insert_trend(record)
        fetched = trend_store.fetch_all()[0]
        assert fetched.engagement_metrics == {}
        assert fetched.raw_metadata == {}


class TestMarkdownViewGeneration:
    """Validate markdown view generation and report formatting (R2 View)."""

    def test_markdown_view_generation_structure(self, trend_store: SQLiteTrendStore):
        """Verify generated markdown contains title, metadata, platform groupings, and table columns."""
        trend_store.seed_30_day_trends(anchor_date="2026-08-22", records_per_day=2, total_days=30)
        gc = GarbageCollector(trend_store)
        gc.sweep(anchor_date="2026-08-22", cutoff_days=14)

        md_view = gc.generate_current_trends_view(anchor_date="2026-08-22", cutoff_days=14)

        # Verify header structure
        assert "# Active Viral Trends (Rolling 14-Day Window)" in md_view
        assert "**Anchor Date:** `2026-08-22`" in md_view
        assert "**Window Range:** `2026-08-08` to `2026-08-22` (14 days)" in md_view
        assert "**Active Records Count:** `30`" in md_view

        # Verify platform headers
        assert "## Platform: Tiktok | Category: `sports_cards`" in md_view or "## Platform: Tiktok | Category: `edm`" in md_view
        assert "| Tag | Date Added | Velocity | Rank | Post Count | Editing Style | Views |" in md_view

        # Verify table row formatting with tags
        assert "| `#" in md_view
        assert "2026-08-" in md_view

    def test_markdown_view_file_output(self, trend_store: SQLiteTrendStore, tmp_path):
        """Verify generate_current_trends_view writes file to output_path."""
        trend_store.seed_30_day_trends(anchor_date="2026-08-22", records_per_day=2, total_days=30)
        gc = GarbageCollector(trend_store)
        gc.sweep(anchor_date="2026-08-22", cutoff_days=14)

        out_file = str(tmp_path / "current_trends.md")
        md_view = gc.generate_current_trends_view(
            anchor_date="2026-08-22",
            cutoff_days=14,
            output_path=out_file,
        )

        assert os.path.exists(out_file)
        with open(out_file, "r", encoding="utf-8") as f:
            saved_content = f.read()

        assert saved_content == md_view
        assert "# Active Viral Trends" in saved_content

    def test_markdown_view_empty_db(self, trend_store: SQLiteTrendStore):
        """Verify markdown view on empty database returns friendly empty message."""
        gc = GarbageCollector(trend_store)
        md_view = gc.generate_current_trends_view(anchor_date="2026-08-22", cutoff_days=14)

        assert "# Active Viral Trends" in md_view
        assert "**Active Records Count:** `0`" in md_view
        assert "_No active trends found in current window._" in md_view


class TestStorageUtilityAndContextManager:
    """Validate helper methods, context manager, and default anchor handling."""

    def test_sweep_with_default_anchor_none(self, trend_store: SQLiteTrendStore):
        """Verify sweep works when anchor_date is None (defaults to current date)."""
        trend_store.insert_trend(
            TrendRecord(
                platform="tiktok",
                category="edm",
                trend_type="hashtag",
                raw_title="#Techno",
                normalized_tag="Techno",
                date_added="2020-01-01",  # Definitely expired relative to today
            )
        )
        gc = GarbageCollector(trend_store)
        res = gc.sweep()  # default anchor_date=None
        assert res["pre_count"] == 1
        assert res["purged_count"] == 1
        assert res["post_count"] == 0

    def test_generate_view_with_default_anchor_none(self, trend_store: SQLiteTrendStore):
        """Verify markdown view generation with default anchor date."""
        gc = GarbageCollector(trend_store)
        view = gc.generate_current_trends_view()
        assert "# Active Viral Trends" in view

    def test_filtered_window_queries(self, trend_store: SQLiteTrendStore):
        """Verify get_records_in_window filtering by platform and category."""
        anchor = "2026-08-22"
        trend_store.insert_trend(
            TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title="#Card1",
                normalized_tag="Card1",
                date_added="2026-08-22",
            )
        )
        trend_store.insert_trend(
            TrendRecord(
                platform="instagram",
                category="edm",
                trend_type="hashtag",
                raw_title="#EDM1",
                normalized_tag="EDM1",
                date_added="2026-08-22",
            )
        )

        tt_records = trend_store.get_records_in_window(anchor_date=anchor, platform="tiktok")
        assert len(tt_records) == 1
        assert tt_records[0].platform == "tiktok"

        edm_records = trend_store.get_records_in_window(anchor_date=anchor, category="edm")
        assert len(edm_records) == 1
        assert edm_records[0].category == "edm"

    def test_context_manager_usage(self, tmp_path):
        """Verify SQLiteTrendStore can be used as a context manager."""
        db_file = str(tmp_path / "ctx_test.db")
        with SQLiteTrendStore(db_file) as store:
            store.insert_trend(
                TrendRecord(
                    platform="youtube",
                    category="general",
                    trend_type="hashtag",
                    raw_title="#Ctx",
                    normalized_tag="Ctx",
                    date_added="2026-08-22",
                )
            )
            assert store.get_total_count() == 1

    def test_dictionary_record_insertion(self, trend_store: SQLiteTrendStore):
        """Verify inserting raw dictionary records directly."""
        dict_record = {
            "platform": "facebook",
            "category": "sports_cards",
            "trend_type": "hashtag",
            "raw_title": "#DictTag",
            "tag": "DictTag",
            "date_added": "2026-08-22",
            "rank": 5,
            "post_count": 2000,
            "velocity_metric": 88.0,
            "editing_style": "slow zoom",
            "engagement_metrics": {"views": 100000},
            "raw_metadata": {"meta_key": "meta_val"},
        }
        row_id = trend_store.insert_trend(dict_record)
        assert row_id == 1
        fetched = trend_store.fetch_all()[0]
        assert fetched.normalized_tag == "DictTag"
        assert fetched.platform == "facebook"
        assert fetched.engagement_metrics["views"] == 100000


class TestPerformanceAndExecutionBenchmark:
    """Benchmark execution time to guarantee fast test feedback."""

    def test_1000_row_insertion_sweep_and_view_sub_500ms(self, trend_store: SQLiteTrendStore):
        """Verify inserting 1000 rows, sweeping, and generating markdown runs under 500ms."""
        start_time = time.perf_counter()

        # Seed 1000 rows across 50 days
        records = []
        anchor_dt = datetime(2026, 8, 22)
        for day in range(50):
            d_str = (anchor_dt - timedelta(days=day)).strftime("%Y-%m-%d")
            for r in range(20):
                records.append(
                    TrendRecord(
                        platform="tiktok" if r % 2 == 0 else "instagram",
                        category="sports_cards" if r % 2 == 0 else "edm",
                        trend_type="hashtag",
                        raw_title=f"#BenchmarkTag_{day}_{r}",
                        normalized_tag=f"BenchmarkTag_{day}_{r}",
                        date_added=d_str,
                        rank=(r % 10) + 1,
                        post_count=5000 + day * 100,
                        velocity_metric=75.5,
                        editing_style="fast cuts",
                        engagement_metrics={"views": 250000, "likes": 15000},
                    )
                )

        trend_store.insert_trends_batch(records, chunk_size=500)
        assert trend_store.get_total_count() == 1000

        gc = GarbageCollector(trend_store)
        res = gc.sweep(anchor_date="2026-08-22", cutoff_days=14)
        assert res["purged_count"] > 0

        md_view = gc.generate_current_trends_view(anchor_date="2026-08-22", cutoff_days=14)
        assert len(md_view) > 100

        elapsed = time.perf_counter() - start_time
        assert elapsed < 0.5, f"Expected < 0.5s execution, took {elapsed:.4f}s"

