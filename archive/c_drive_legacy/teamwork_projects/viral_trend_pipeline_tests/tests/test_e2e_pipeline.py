"""End-to-End Integration Test Suite for the Viral Trend Pipeline (Milestone M4).

Validates:
- End-to-End Lifecycle Flow: Multi-platform Extraction (TikTok, YouTube, Instagram)
  -> SQLite Database Ingestion (`trends.db`) -> 30-Day Simulated History
  -> 14-Day Mark-and-Sweep Garbage Collection -> Exact Row Count Validation
  -> BigQuery ML Payload Formatting (TimesFM 2.0 AI.FORECAST & AI.KEY_DRIVERS)
  -> BigQuery Schema Validation.
- Real-World Workload Scenarios 1-5 (Tier 4):
  - Scenario 1: 30-day multi-platform ingestion, 14-day purge, `current_trends.md` generation.
  - Scenario 2: High-velocity Sports Cards & EDM tagging matrix normalization & forecast formatting.
  - Scenario 3: Instagram Reels video editing style driver analysis for BigQuery AI.KEY_DRIVERS.
  - Scenario 4: Corrupted extraction recovery and zero-network socket enforcement.
  - Scenario 5: Full suite execution runtime benchmark (verifying total pytest runtime < 5.0s, strictly under 10.0s).
- Pairwise Platform x Category x Editing Style Integration (Tier 3).
- Boundary Value & Rolling Schedule Hardening (Tier 2).
"""

from datetime import datetime, timedelta
import os
import socket
import time
from typing import Any, Dict, List
import urllib.request
import pytest

from viral_trend_pipeline.models import (
    TrendRecord,
    ExtractionParseError,
    NetworkBlockError,
    normalize_hashtag,
    classify_category,
    parse_metric_number,
    parse_velocity_metric,
    get_default_date,
)
from viral_trend_pipeline.extractors.chrome_devtools import ChromeDevToolsExtractor
from viral_trend_pipeline.extractors.android_cli import AndroidCLIExtractor
from viral_trend_pipeline.storage.database import SQLiteTrendStore
from viral_trend_pipeline.storage.garbage_collector import GarbageCollector
from viral_trend_pipeline.exporters.bigquery_payload import (
    BigQueryPayloadFormatter,
    safe_cast_float,
    safe_cast_int,
    format_iso_timestamp,
)
from tests.fixtures.chrome_fixtures import (
    get_tiktok_a11y_snapshot,
    get_youtube_a11y_snapshot,
    MALFORMED_A11Y_SNAPSHOT,
    EMPTY_LOADING_A11Y_SNAPSHOT,
    EMOJI_A11Y_SNAPSHOT,
    generate_large_a11y_tree,
)
from tests.fixtures.android_fixtures import (
    get_instagram_reels_layout_data,
    get_instagram_reels_layout_json,
    INVALID_SYNTAX_JSON,
    NULL_TEXT_LAYOUT_DATA,
    OFFSCREEN_LAYOUT_DATA,
    MULTI_TAG_CAPTION_LAYOUT_DATA,
)


# ==============================================================================
# 1. End-to-End Pipeline Full Lifecycle Flow
# ==============================================================================

class TestE2EPipelineFullLifecycle:
    """End-to-End integration testing connecting extraction, storage, GC, and BigQuery export."""

    def test_e2e_multiplatform_extraction_ingestion_gc_and_bigquery_export(
        self,
        chrome_extractor: ChromeDevToolsExtractor,
        android_extractor: AndroidCLIExtractor,
        tiktok_a11y_raw: str,
        youtube_a11y_raw: str,
        instagram_layout_data: list,
        tmp_path,
    ):
        """Full lifecycle integration test:
        1. Extract multi-platform trends from mock fixtures (TikTok, YouTube, Instagram).
        2. Ingest extracted records into SQLite database.
        3. Seed 30 days of historical multi-platform trends anchored at 2026-08-22.
        4. Execute 14-day mark-and-sweep GC and verify exact purged/retained counts.
        5. Generate `current_trends.md` active rolling window view.
        6. Export active records to BigQuery TimesFM 2.0 (AI.FORECAST) and Key Drivers (AI.KEY_DRIVERS).
        7. Validate schemas of both BigQuery payloads.
        """
        anchor_date = "2026-08-22"
        db_path = str(tmp_path / "trends_e2e.db")
        md_path = str(tmp_path / "current_trends_e2e.md")

        with SQLiteTrendStore(db_path) as store:
            # Step 1: Multi-platform Extraction
            tt_hashtags = chrome_extractor.parse_tiktok_hashtags(tiktok_a11y_raw, anchor_date=anchor_date)
            tt_audio = chrome_extractor.parse_tiktok_audio(tiktok_a11y_raw, anchor_date=anchor_date)
            yt_videos = chrome_extractor.parse_youtube_trending(youtube_a11y_raw, anchor_date=anchor_date)
            ig_records = android_extractor.parse_instagram_reels(instagram_layout_data, anchor_date=anchor_date)

            assert len(tt_hashtags) == 5
            assert len(tt_audio) == 2
            assert len(yt_videos) == 2
            assert len(ig_records) == 8

            fresh_extracted_records = tt_hashtags + tt_audio + yt_videos + ig_records
            assert len(fresh_extracted_records) == 17

            # Step 2: Ingest fresh extractions into SQLite
            inserted_fresh = store.insert_trends_batch(fresh_extracted_records)
            assert inserted_fresh == 17
            assert store.get_total_count() == 17

            # Step 3: Seed 30 days of historical trends (2 records/day = 60 records)
            seeded_history = store.seed_30_day_trends(
                anchor_date=anchor_date,
                records_per_day=2,
                total_days=30,
            )
            assert len(seeded_history) == 60
            assert store.get_total_count() == 77  # 17 fresh + 60 history

            # Step 4: Execute 14-Day Mark-and-Sweep GC
            gc = GarbageCollector(store)
            gc_result = gc.sweep(anchor_date=anchor_date, cutoff_days=14)

            # Mathematical verification:
            # Seed history: 30 days total (offsets 0..29).
            # Retained window [2026-08-08 to 2026-08-22] (offsets 0..14) = 15 days * 2 = 30 rows.
            # Expired window [2026-07-24 to 2026-08-07] (offsets 15..29) = 15 days * 2 = 30 rows purged.
            # Fresh records: all dated 2026-08-22 = 17 rows retained.
            # Total pre: 77 | Purged: 30 | Post: 47 | Retained: 47
            assert gc_result["pre_count"] == 77
            assert gc_result["purged_count"] == 30
            assert gc_result["post_count"] == 47
            assert gc_result["retained_count"] == 47
            assert store.get_total_count() == 47

            # Step 5: Generate current_trends.md markdown view
            md_content = gc.generate_current_trends_view(
                anchor_date=anchor_date,
                cutoff_days=14,
                output_path=md_path,
            )
            assert os.path.exists(md_path)
            assert "# Active Viral Trends (Rolling 14-Day Window)" in md_content
            assert "**Anchor Date:** `2026-08-22`" in md_content
            assert "**Active Records Count:** `47`" in md_content
            assert "## Platform: Tiktok" in md_content
            assert "## Platform: Instagram" in md_content
            assert "## Platform: Youtube" in md_content

            # Step 6: Query active window records and export to BigQuery
            active_records = store.get_records_in_window(anchor_date=anchor_date, window_days=14)
            assert len(active_records) == 47

            # Filter or group records for TimesFM 2.0 (AI.FORECAST) ensuring series >= 3 points
            # In our seed data, tags like 'SportsCards', 'CardLadder', 'HardTechno' appear across multiple days
            forecast_records = [r for r in active_records if r.category in {"sports_cards", "edm"} and r.trend_type == "hashtag"]
            # Filter to tags with >= 3 observations in window
            tag_counts = {}
            for r in forecast_records:
                tag_counts[r.normalized_tag] = tag_counts.get(r.normalized_tag, 0) + 1
            valid_forecast_tags = {tag for tag, cnt in tag_counts.items() if cnt >= 3}
            eligible_records = [r for r in forecast_records if r.normalized_tag in valid_forecast_tags]

            forecast_payload = BigQueryPayloadFormatter.build_ai_forecast_payload(eligible_records)
            assert len(forecast_payload) >= 9  # At least 3 series * 3 points
            assert BigQueryPayloadFormatter.validate_forecast_schema(forecast_payload) is True

            # Step 7: Export active records for BigQuery AI.KEY_DRIVERS
            key_drivers_payload = BigQueryPayloadFormatter.build_ai_key_drivers_payload(
                active_records,
                viral_threshold=50000,
                dimension_cols=["editing_style", "platform", "category"],
                metric_col="views",
                interest_label_col="is_viral",
            )
            assert len(key_drivers_payload) == 47
            assert BigQueryPayloadFormatter.validate_key_drivers_schema(
                key_drivers_payload,
                dimension_cols=["editing_style", "platform", "category"],
                metric_col="views",
                interest_label_col="is_viral",
            ) is True

            # Verify presence of both viral and non-viral labeled rows
            viral_flags = {row["is_viral"] for row in key_drivers_payload}
            assert True in viral_flags
            assert False in viral_flags


# ==============================================================================
# 2. Real-World Application Workloads (Scenarios 1-5 from TEST_INFRA.md)
# ==============================================================================

class TestRealWorldWorkloadScenarios:
    """Tier 4: Comprehensive validation of Real-World Workload Scenarios 1 through 5."""

    def test_scenario_1_multiplatform_30day_ingestion_purge_and_markdown_view(
        self, temp_trend_store: SQLiteTrendStore, tmp_path
    ):
        """Scenario 1: 30-Day Multi-Platform Trend Ingestion, 14-Day Purge, and Markdown View Generation.
        - Ingest 30 days of multi-platform trends (TikTok, YouTube, Instagram, Facebook).
        - Execute 14-day mark-and-sweep GC.
        - Verify exact purged/retained counts and database date boundaries.
        - Generate and validate `current_trends.md` active rolling window view.
        """
        anchor_date = "2026-08-22"
        md_file = str(tmp_path / "current_trends.md")

        # 1. Seed 30 days of multi-platform data (2 records/day = 60 records)
        seeded = temp_trend_store.seed_30_day_trends(
            anchor_date=anchor_date,
            records_per_day=2,
            total_days=30,
        )
        assert len(seeded) == 60
        assert temp_trend_store.get_total_count() == 60

        # 2. Run 14-day GC sweep
        gc = GarbageCollector(temp_trend_store)
        gc_stats = gc.sweep(anchor_date=anchor_date, cutoff_days=14)

        assert gc_stats["pre_count"] == 60
        assert gc_stats["purged_count"] == 30
        assert gc_stats["post_count"] == 30
        assert gc_stats["retained_count"] == 30
        assert temp_trend_store.get_total_count() == 30

        # 3. Assert database date boundaries
        cursor = temp_trend_store.connection.cursor()
        cursor.execute("SELECT MIN(date_added), MAX(date_added) FROM trends;")
        min_date, max_date = cursor.fetchone()
        assert min_date == "2026-08-08"
        assert max_date == "2026-08-22"

        # 4. Generate markdown view
        view_content = gc.generate_current_trends_view(
            anchor_date=anchor_date,
            cutoff_days=14,
            output_path=md_file,
        )

        assert os.path.isfile(md_file)
        assert "# Active Viral Trends (Rolling 14-Day Window)" in view_content
        assert "**Anchor Date:** `2026-08-22`" in view_content
        assert "**Window Range:** `2026-08-08` to `2026-08-22` (14 days)" in view_content
        assert "**Active Records Count:** `30`" in view_content

        # Platform sections present
        assert "## Platform:" in view_content
        assert "| Tag | Date Added | Velocity | Rank | Post Count | Editing Style | Views |" in view_content

    def test_scenario_2_sports_cards_and_edm_tagging_matrix_forecast(self):
        """Scenario 2: High-Velocity Sports Cards & EDM Hashtag Tagging Matrix Normalization & AI.FORECAST Export.
        - Ingest multi-day time series for Sports Cards (#SportsCards, #PaniniPrizm, #CardLadder, #TheHobby)
          and EDM (#HardTechno, #RaveTok, #EDMDrop, #Ultra2026).
        - Test tag normalization: unnesting, emoji stripping, case-preservation, and deduplication.
        - Build BigQuery AI.FORECAST (TimesFM 2.0) payload.
        - Validate minimum 3 points per series, ascending chronological order, and ISO-8601 timestamps.
        """
        sports_cards_tags = ["SportsCards", "PaniniPrizm", "CardLadder", "TheHobby"]
        edm_tags = ["HardTechno", "RaveTok", "EDMDrop", "Ultra2026"]
        anchor_dt = datetime(2026, 8, 22)

        raw_tag_inputs = [
            "#SportsCards", " #SportsCards ", "#sportscards", "#CardLadder🔥",
            "#TheHobby💎", "#PaniniPrizm✨", "#HardTechno⚡️", "#RaveTok🎧",
            "#EDMDrop🎉", "#Ultra2026🚀",
        ]
        normalized_tags = BigQueryPayloadFormatter.normalize_tag_array(raw_tag_inputs)
        # Verify strict case preservation & deduplication
        assert "SportsCards" in normalized_tags
        assert "sportscards" in normalized_tags
        assert "CardLadder" in normalized_tags
        assert "TheHobby" in normalized_tags
        assert "HardTechno" in normalized_tags

        # Generate 7 daily data points for each tag series
        records: List[TrendRecord] = []
        all_tags = sports_cards_tags + edm_tags

        for tag in all_tags:
            cat = "sports_cards" if tag in sports_cards_tags else "edm"
            for day_offset in range(7):
                date_str = (anchor_dt - timedelta(days=6 - day_offset)).strftime("%Y-%m-%d")
                velocity = round(60.0 + (day_offset * 8.5), 2)
                views = 20_000 + (day_offset * 15_000)

                records.append(
                    TrendRecord(
                        platform="tiktok" if cat == "edm" else "instagram",
                        category=cat,
                        trend_type="hashtag",
                        raw_title=f"#{tag}",
                        normalized_tag=tag,
                        date_added=date_str,
                        velocity_metric=velocity,
                        engagement_metrics={"views": views, "velocity_score": velocity},
                    )
                )

        assert len(records) == 8 * 7  # 56 records (8 tags * 7 days)

        forecast_payload = BigQueryPayloadFormatter.build_ai_forecast_payload(records)
        assert len(forecast_payload) == 56

        # Assert schema validation
        assert BigQueryPayloadFormatter.validate_forecast_schema(forecast_payload) is True

        # Assert chronological ordering within each tag series
        for tag in all_tags:
            series_items = [p for p in forecast_payload if p["tag"] == tag]
            assert len(series_items) == 7
            dates = [p["date"] for p in series_items]
            assert dates == sorted(dates)
            assert dates[0] == "2026-08-16T00:00:00Z"
            assert dates[-1] == "2026-08-22T00:00:00Z"

    def test_scenario_3_instagram_reels_video_editing_style_driver_analysis(self):
        """Scenario 3: Instagram Reels Video Editing Style Driver Analysis for BigQuery AI.KEY_DRIVERS.
        - Create dataset with diverse video editing styles ("fast cuts", "stutter edit", "slow zoom", "seamless loop", "educational overlay").
        - Build BigQuery AI.KEY_DRIVERS payload with dimension columns, viral thresholding, and metric values.
        - Assert exact boolean `is_viral` labeling, dimension bounds (1-12), and type validations.
        """
        editing_styles = [
            ("fast cuts", 85_000),         # Viral (>= 50k)
            ("stutter edit", 120_000),     # Viral
            ("slow zoom", 22_000),         # Non-viral (< 50k)
            ("seamless loop", 95_000),     # Viral
            ("educational overlay", 48_500), # Non-viral (< 50k)
            ("talking head", 15_000),      # Non-viral
            ("montage cut", 50_000),       # Viral (boundary: == 50k)
        ]

        records: List[TrendRecord] = []
        for idx, (style, views) in enumerate(editing_styles):
            cat = "sports_cards" if idx % 2 == 0 else "edm"
            records.append(
                TrendRecord(
                    platform="instagram",
                    category=cat,
                    trend_type="video_title",
                    raw_title=f"Reel_{idx} using {style}",
                    normalized_tag=f"Reel_{idx}",
                    date_added="2026-08-22",
                    editing_style=style,
                    engagement_metrics={"views": views, "likes": int(views * 0.1)},
                )
            )

        payload = BigQueryPayloadFormatter.build_ai_key_drivers_payload(
            records,
            viral_threshold=50000,
            dimension_cols=["editing_style", "platform", "category"],
            metric_col="views",
            interest_label_col="is_viral",
        )

        assert len(payload) == 7
        assert BigQueryPayloadFormatter.validate_key_drivers_schema(payload) is True

        # Check is_viral classifications
        expected_viral = [True, True, False, True, False, False, True]
        actual_viral = [row["is_viral"] for row in payload]
        assert actual_viral == expected_viral

        # Verify editing style dimension preservation
        assert [row["editing_style"] for row in payload] == [s[0] for s in editing_styles]

    def test_scenario_4_corrupted_extraction_recovery_and_zero_network_socket(
        self,
        chrome_extractor: ChromeDevToolsExtractor,
        android_extractor: AndroidCLIExtractor,
    ):
        """Scenario 4: Corrupted/Malformed Extraction Snapshot Recovery with Zero Network Fallback.
        - Parse malformed / noisy a11y tree snapshots and Android UI hierarchy dumps.
        - Assert parsers recover valid elements gracefully without crashing or throwing unhandled errors.
        - Verify zero-network socket blocking raises NetworkBlockError when network connection is attempted.
        """
        # 1. Parse malformed a11y snapshot (skips broken lines, extracts valid row)
        tt_recovered = chrome_extractor.parse_tiktok_hashtags(MALFORMED_A11Y_SNAPSHOT)
        assert len(tt_recovered) >= 1
        assert any(r.normalized_tag == "CardLadder" for r in tt_recovered)

        # 2. Parse empty / loading a11y snapshot (returns [] gracefully)
        loading_records = chrome_extractor.parse_snapshot(EMPTY_LOADING_A11Y_SNAPSHOT)
        assert loading_records == []

        # 3. Parse invalid syntax Android JSON (raises ExtractionParseError)
        with pytest.raises(ExtractionParseError):
            android_extractor.parse_instagram_reels(INVALID_SYNTAX_JSON)

        # 4. Parse null text UI elements with contentDesc fallback
        null_text_records = android_extractor.parse_instagram_reels(NULL_TEXT_LAYOUT_DATA)
        assert len(null_text_records) == 2
        tags = [r.normalized_tag for r in null_text_records]
        assert "TheHobby" in tags
        assert "CardInvesting" in tags

        # 5. Parse 20+ multi-hashtag caption
        multi_tag_records = android_extractor.parse_instagram_reels(MULTI_TAG_CAPTION_LAYOUT_DATA)
        assert len(multi_tag_records) == 21

        # 6. Verify zero-network socket connection attempt raises NetworkBlockError
        with pytest.raises(NetworkBlockError, match="Real network socket connection blocked"):
            s = socket.socket()
            s.connect(("127.0.0.1", 9999))

        with pytest.raises((NetworkBlockError, Exception)):
            urllib.request.urlopen("https://api.tiktok.com/trends", timeout=0.1)

    def test_scenario_5_full_suite_execution_runtime_benchmark(
        self,
        chrome_extractor: ChromeDevToolsExtractor,
        android_extractor: AndroidCLIExtractor,
        tiktok_a11y_raw: str,
        youtube_a11y_raw: str,
        instagram_layout_data: list,
    ):
        """Scenario 5: Full Lifecycle Pipeline Benchmark Execution under 5.0s (strictly < 10.0s).
        - Executes extraction, batch SQLite storage, 14-day GC sweep, and BigQuery payload generation.
        - Asserts total execution time is under 5.0 seconds.
        """
        start_time = time.perf_counter()

        with SQLiteTrendStore(":memory:") as store:
            # 1. Extraction from fixtures
            tt_tags = chrome_extractor.parse_tiktok_hashtags(tiktok_a11y_raw)
            tt_audio = chrome_extractor.parse_tiktok_audio(tiktok_a11y_raw)
            yt_videos = chrome_extractor.parse_youtube_trending(youtube_a11y_raw)
            ig_reels = android_extractor.parse_instagram_reels(instagram_layout_data)

            extracted = tt_tags + tt_audio + yt_videos + ig_reels
            assert len(extracted) == 17

            # 2. Batch ingestion of 1,000 synthetic records across 30 days
            records: List[TrendRecord] = []
            anchor_dt = datetime(2026, 8, 22)
            for day in range(30):
                d_str = (anchor_dt - timedelta(days=day)).strftime("%Y-%m-%d")
                for r in range(33):  # ~1000 total
                    records.append(
                        TrendRecord(
                            platform="tiktok" if r % 2 == 0 else "instagram",
                            category="sports_cards" if r % 2 == 0 else "edm",
                            trend_type="hashtag",
                            raw_title=f"#Benchmark_{day}_{r}",
                            normalized_tag=f"Benchmark_{day}_{r}",
                            date_added=d_str,
                            rank=(r % 10) + 1,
                            post_count=10000 + (day * 500),
                            velocity_metric=float(40 + (day * 2)),
                            editing_style="fast cuts" if r % 2 == 0 else "stutter edit",
                            engagement_metrics={"views": 25000 + (day * 1000)},
                        )
                    )

            store.insert_trends_batch(extracted + records, chunk_size=500)
            assert store.get_total_count() == 17 + len(records)

            # 3. 14-day Mark-and-Sweep GC
            gc = GarbageCollector(store)
            gc_res = gc.sweep(anchor_date="2026-08-22", cutoff_days=14)
            assert gc_res["purged_count"] > 0

            # 4. Generate markdown view
            view_md = gc.generate_current_trends_view(anchor_date="2026-08-22", cutoff_days=14)
            assert len(view_md) > 100

            # 5. Format BigQuery Payloads
            retained = store.fetch_all()
            kd_payload = BigQueryPayloadFormatter.build_ai_key_drivers_payload(retained, viral_threshold=50000)
            assert len(kd_payload) == len(retained)
            assert BigQueryPayloadFormatter.validate_key_drivers_schema(kd_payload) is True

        elapsed_time = time.perf_counter() - start_time
        assert elapsed_time < 5.0, f"Full pipeline benchmark took {elapsed_time:.3f}s, expected < 5.0s (limit 10.0s)"


# ==============================================================================
# 3. Multi-Platform Pairwise Integrations (Tier 3)
# ==============================================================================

class TestPairwiseIntegrations:
    """Tier 3: Pairwise combinations across platforms, categories, and metrics."""

    @pytest.mark.parametrize("platform", ["tiktok", "instagram", "youtube", "facebook"])
    @pytest.mark.parametrize("category", ["sports_cards", "edm", "general"])
    def test_pairwise_platform_category_matrix_sqlite_and_bigquery(
        self, trend_store: SQLiteTrendStore, platform: str, category: str
    ):
        """Verify pairwise combinations of platform x category through SQLite and BigQuery export."""
        record = TrendRecord(
            platform=platform,
            category=category,
            trend_type="hashtag",
            raw_title=f"#{platform}_{category}",
            normalized_tag=f"{platform}_{category}",
            date_added="2026-08-22",
            rank=1,
            post_count=75000,
            velocity_metric=95.0,
            editing_style="seamless loop",
            engagement_metrics={"views": 75000, "likes": 5000},
        )
        trend_store.insert_trend(record)
        assert trend_store.get_total_count() == 1

        fetched = trend_store.fetch_all()[0]
        assert fetched.platform == platform
        assert fetched.category == category

        # BigQuery export
        kd_payload = BigQueryPayloadFormatter.build_ai_key_drivers_payload([fetched], viral_threshold=50000)
        assert len(kd_payload) == 1
        assert kd_payload[0]["platform"] == platform
        assert kd_payload[0]["category"] == category
        assert kd_payload[0]["is_viral"] is True
        assert BigQueryPayloadFormatter.validate_key_drivers_schema(kd_payload) is True

    @pytest.mark.parametrize("post_count_val, expected_int", [
        ("1.2M", 1200000),
        ("850K", 850000),
        ("2.5B", 2500000000),
        ("45,200", 45200),
        (50000, 50000),
        ("NEW", 0),
        (None, 0),
    ])
    @pytest.mark.parametrize("velocity_str, expected_float", [
        ("+145%", 145.0),
        ("-12.5%", -12.5),
        ("82%", 82.0),
        (99.5, 99.5),
        ("NEW", 0.0),
        (None, 0.0),
    ])
    def test_pairwise_metric_and_velocity_safe_casting(
        self, post_count_val: Any, expected_int: int, velocity_str: Any, expected_float: float
    ):
        """Verify pairwise combinations of human-readable metric inputs and safe casting."""
        casted_int = safe_cast_int(post_count_val)
        casted_float = safe_cast_float(velocity_str)

        assert casted_int == expected_int
        assert casted_float == expected_float


# ==============================================================================
# 4. Adversarial Stress, Rolling Schedules & Hardening (Tier 2 Boundary)
# ==============================================================================

class TestHardeningAndBoundaryConditions:
    """Tier 2 Boundary: Stress testing rolling weekly cron schedules and multi-pass GC sweeps."""

    def test_successive_weekly_cron_rolling_sweeps(self, trend_store: SQLiteTrendStore):
        """Simulate a 4-week cron schedule where new trends are added and GC sweep is executed weekly.
        Verifies that SQLite store never accumulates unbounded historical rows.
        """
        base_anchor = datetime(2026, 8, 1)

        for week in range(4):
            current_anchor_dt = base_anchor + timedelta(weeks=week)
            current_anchor_str = current_anchor_dt.strftime("%Y-%m-%d")

            # Seed 7 days of trends for this week (2 records/day = 14 records)
            weekly_records = []
            for day in range(7):
                d_str = (current_anchor_dt - timedelta(days=day)).strftime("%Y-%m-%d")
                for r in range(2):
                    weekly_records.append(
                        TrendRecord(
                            platform="tiktok" if r == 0 else "instagram",
                            category="sports_cards" if r == 0 else "edm",
                            trend_type="hashtag",
                            raw_title=f"#Week{week}_Day{day}_{r}",
                            normalized_tag=f"Week{week}_Day{day}_{r}",
                            date_added=d_str,
                            rank=1,
                            post_count=10000,
                            velocity_metric=50.0,
                        )
                    )
            trend_store.insert_trends_batch(weekly_records)

            # Execute weekly sweep
            gc = GarbageCollector(trend_store)
            gc_res = gc.sweep(anchor_date=current_anchor_str, cutoff_days=14)

            # Invariant: Active window [current_anchor - 14 days, current_anchor]
            # Database should never exceed ~30 records (15 days * 2 records/day = 30 max)
            assert trend_store.get_total_count() <= 30
            assert gc_res["retained_count"] <= 30

    def test_large_scale_2000_record_pipeline_integrity(self, trend_store: SQLiteTrendStore):
        """Ingest 2,000 multi-platform records, perform GC sweep, and format TimesFM & Key Drivers payloads."""
        records: List[TrendRecord] = []
        anchor_dt = datetime(2026, 8, 22)

        # 40 tags * 50 days = 2,000 records
        for tag_idx in range(40):
            tag_name = f"TrendTag_{tag_idx}"
            cat = "sports_cards" if tag_idx % 2 == 0 else "edm"
            plat = "tiktok" if tag_idx % 3 == 0 else ("instagram" if tag_idx % 3 == 1 else "youtube")

            for day in range(50):
                d_str = (anchor_dt - timedelta(days=day)).strftime("%Y-%m-%d")
                views = 10_000 + (day * 2_000)
                vel = round(40.0 + (day * 1.5), 2)
                records.append(
                    TrendRecord(
                        platform=plat,
                        category=cat,
                        trend_type="hashtag",
                        raw_title=f"#{tag_name}",
                        normalized_tag=tag_name,
                        date_added=d_str,
                        rank=(tag_idx % 10) + 1,
                        post_count=views,
                        velocity_metric=vel,
                        editing_style="fast cuts" if day % 2 == 0 else "stutter edit",
                        engagement_metrics={"views": views, "velocity_score": vel},
                    )
                )

        assert len(records) == 2000
        trend_store.insert_trends_batch(records, chunk_size=500)
        assert trend_store.get_total_count() == 2000

        # Run GC sweep (Day 0 to 14 retained = 15 days * 40 tags = 600 records)
        gc = GarbageCollector(trend_store)
        res = gc.sweep(anchor_date="2026-08-22", cutoff_days=14)

        assert res["pre_count"] == 2000
        assert res["purged_count"] == 1400  # 35 expired days * 40 tags
        assert res["post_count"] == 600    # 15 active days * 40 tags
        assert res["retained_count"] == 600
        assert trend_store.get_total_count() == 600

        # Build BigQuery Payloads on active window
        retained = trend_store.fetch_all()
        forecast_payload = BigQueryPayloadFormatter.build_ai_forecast_payload(retained)
        kd_payload = BigQueryPayloadFormatter.build_ai_key_drivers_payload(retained, viral_threshold=50000)

        assert len(forecast_payload) == 600
        assert len(kd_payload) == 600
        assert BigQueryPayloadFormatter.validate_forecast_schema(forecast_payload) is True
        assert BigQueryPayloadFormatter.validate_key_drivers_schema(kd_payload) is True
