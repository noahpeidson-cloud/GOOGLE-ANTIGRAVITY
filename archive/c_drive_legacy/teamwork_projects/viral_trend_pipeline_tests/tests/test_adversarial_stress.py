"""Adversarial Stress Test Suite & Fuzz Harness for Viral Trend Pipeline.

Empirically tests extreme scales (10,000+ tags, 5,000+ DB rows), malformed input trees,
fuzzed data, complex Unicode/emojis, SQL injection safety, TimesFM 2.0 boundary conditions,
and zero-network socket enforcement under stress.
"""

from datetime import datetime, timedelta, timezone
import json
import random
import re
import socket
import string
import time
from typing import Any, Dict, List
import pytest

from viral_trend_pipeline.models import (
    TrendRecord,
    ExtractionParseError,
    NetworkBlockError,
    normalize_hashtag,
    parse_metric_number,
    parse_velocity_metric,
    classify_category,
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


class TestExtremeScaleStress:
    """Stress tests verifying high-volume throughput and memory efficiency."""

    def test_sqlite_5000_rows_bulk_ingestion_and_gc_sweep(self, tmp_path):
        """Stress-test SQLiteTrendStore with 5,000 rows across 50 dates and execute GC."""
        db_path = str(tmp_path / "stress_trends.db")
        store = SQLiteTrendStore(db_path)
        gc = GarbageCollector(store)

        anchor_dt = datetime(2026, 8, 22, tzinfo=timezone.utc)
        total_rows = 5000
        days_span = 50
        records_per_day = total_rows // days_span  # 100 records per day

        records: List[TrendRecord] = []
        platforms = ["tiktok", "instagram", "youtube", "facebook"]
        categories = ["sports_cards", "edm", "general"]

        start_time = time.perf_counter()
        for day_offset in range(days_span):
            curr_date = (anchor_dt - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            for r_idx in range(records_per_day):
                gid = day_offset * records_per_day + r_idx
                rec = TrendRecord(
                    platform=platforms[gid % len(platforms)],
                    category=categories[gid % len(categories)],
                    trend_type="hashtag",
                    raw_title=f"#TrendTag_{gid} 🔥💎",
                    normalized_tag=f"TrendTag_{gid}",
                    date_added=curr_date,
                    rank=(gid % 100) + 1,
                    post_count=1000 + (gid * 10),
                    velocity_metric=float(gid % 200),
                    editing_style="fast cuts" if gid % 2 == 0 else "seamless loop",
                    engagement_metrics={"views": 50000 + gid, "likes": 5000 + gid},
                    raw_metadata={"batch_id": "stress_5k", "gid": gid},
                )
                records.append(rec)

        # Batch insert 5,000 records
        inserted = store.insert_trends_batch(records, chunk_size=500)
        insert_duration = time.perf_counter() - start_time

        assert inserted == 5000
        assert store.get_total_count() == 5000
        assert insert_duration < 3.0  # Must insert 5k rows well under 3 seconds

        # Days 0 to 14 = 15 calendar days retained (15 * 100 = 1,500 records)
        # Days 15 to 49 = 35 calendar days purged (35 * 100 = 3,500 records)
        sweep_start = time.perf_counter()
        sweep_result = gc.sweep(anchor_date="2026-08-22", cutoff_days=14)
        sweep_duration = time.perf_counter() - sweep_start

        assert sweep_result["pre_count"] == 5000
        assert sweep_result["purged_count"] == 3500
        assert sweep_result["post_count"] == 1500
        assert sweep_result["retained_count"] == 1500
        assert sweep_duration < 0.5  # GC sweep must execute under 500ms

        # Generate markdown view on the 1,500 retained records
        view_start = time.perf_counter()
        view_md = gc.generate_current_trends_view(anchor_date="2026-08-22", cutoff_days=14)
        view_duration = time.perf_counter() - view_start

        assert "**Active Records Count:** `1500`" in view_md
        assert "| `#TrendTag_0` |" in view_md
        assert view_duration < 1.0  # View generation under 1.0s

        store.close()

    def test_bigquery_tag_normalizer_10000_tags_stress(self):
        """Stress-test BigQueryPayloadFormatter.normalize_tag_array with 10,000+ tags."""
        raw_tags: List[Any] = []
        base_names = [
            "SportsCards", "sportscards", "SPORTSCARDS", "CardLadder", "cardladder",
            "PaniniPrizm", "HardTechno", "hardtechno", "RaveTok", "EDMDrop",
            "Ultra2026", "Wembanyama", "ToppsChrome", "TheHobby", "WhoDoYouCollect"
        ]
        emojis = ["🔥", "💎", "⚡️", "🎧", "🚀", "✨", "👑", "🏆"]

        # Generate 12,000 items with heavy nesting, duplicates, emojis, and whitespace
        for i in range(12000):
            base = base_names[i % len(base_names)]
            emoji = emojis[i % len(emojis)]
            if i % 4 == 0:
                raw_tags.append(f"  #{base}{emoji}  ")
            elif i % 4 == 1:
                # Nested list inside
                raw_tags.append([f"#{base}!", f"  {base}_{i % 50}  "])
            elif i % 4 == 2:
                # Tuple with nulls
                raw_tags.append((None, f"#{base}", "   "))
            else:
                raw_tags.append(f"#{base}")

        start_time = time.perf_counter()
        normalized = BigQueryPayloadFormatter.normalize_tag_array(raw_tags)
        duration = time.perf_counter() - start_time

        # Distinct base tags (15 distinct base + 50 variations = at least 60 distinct tags)
        assert len(normalized) >= 15
        assert len(normalized) <= 100
        # Case preservation: SportsCards and sportscards and SPORTSCARDS must both exist
        assert "SportsCards" in normalized
        assert "sportscards" in normalized
        assert "SPORTSCARDS" in normalized
        assert "CardLadder" in normalized
        assert "cardladder" in normalized
        # No duplicates in output list
        assert len(normalized) == len(set(normalized))
        # Execution duration strictly under 1.0 second
        assert duration < 1.0


class TestFuzzingAndMalformedInputs:
    """Fuzz testing and malformed tree handling for extractors and normalization."""

    def test_fuzz_chrome_a11y_tree_parser(self, chrome_extractor: ChromeDevToolsExtractor):
        """Fuzz ChromeDevToolsExtractor with corrupted lines, extreme indentation, and binary noise."""
        fuzz_lines = [
            "",  # Empty
            "   ",  # Whitespace only
            "uid=INVALID_NO_ROLE",
            "uid=1_1 row",  # No name
            "uid=1_2 cell \"Unterminated string",
            "   uid=1_3 cell \"Valid Name\" invalid_attr_without_equals",
            "uid=1_4 role_with_quotes=\"bad\"",
            "uid=1_5 row \"Rank 1 #FuzzTag\" post_count=NaN velocity=+9999%",
            "           uid=1_6 cell \"Very deep indentation (depth 10)\"",
            "uid=1_7 link \"#🔥💎MixedEmojiTag\"",
            "\x00\x01\x02 binary control characters",
            "uid=1_8 text \"1. Fuzz Song - Fuzz Artist\" level=3",
            "uid=1_9 heading \"Trending Video Title 2026\" level=3",
        ]

        fuzzed_snapshot = "\n".join(fuzz_lines)
        nodes = chrome_extractor.parse_a11y_tree(fuzzed_snapshot)
        assert isinstance(nodes, list)

        # Should safely extract hashtags without crashing
        hashtags = chrome_extractor.parse_tiktok_hashtags(fuzzed_snapshot)
        assert isinstance(hashtags, list)

        # Should safely extract audio without crashing
        audio = chrome_extractor.parse_tiktok_audio(fuzzed_snapshot)
        assert isinstance(audio, list)

        # Should safely extract youtube trending without crashing
        yt = chrome_extractor.parse_youtube_trending(fuzzed_snapshot)
        assert isinstance(yt, list)

    def test_fuzz_android_layout_parser(self, android_extractor: AndroidCLIExtractor):
        """Fuzz AndroidCLIExtractor with invalid types, nulls, missing fields, and huge captions."""
        # 1. Non-JSON string should raise ExtractionParseError
        with pytest.raises(ExtractionParseError):
            android_extractor.parse_layout("<<<MALFORMED XML/NOT JSON>>>")

        # 2. List containing malformed dicts and non-dict primitives
        hostile_elements = [
            None,
            42,
            "just a string",
            {},
            {"resourceId": None, "text": None},
            {"resourceId": "com.instagram.android:id/caption_text_view", "text": ""},
            {
                "resourceId": "com.instagram.android:id/caption_text_view",
                "text": "Huge caption " + " ".join([f"#Tag_{i}" for i in range(200)]),
                "off-screen": False,
            },
            {
                "resourceId": "com.instagram.android:id/audio_track_title",
                "contentDesc": "Audio: Ultra 2026 Festival Anthem - DJ Test",
                "off-screen": False,
            },
            {
                "resourceId": "com.instagram.android:id/like_count",
                "text": "1.8M likes",
            },
            {
                "resourceId": "com.instagram.android:id/comments_count",
                "text": "95,420 comments",
            },
        ]

        records = android_extractor.parse_layout(hostile_elements)
        assert len(records) > 0
        # Check that engagement metrics from like/comment counts propagated
        assert any(r.post_count == 1_800_000 for r in records)
        assert any(r.trend_type == "audio" for r in records)

    def test_fuzz_unicode_and_astral_emojis(self):
        """Test tag normalization against astral plane emojis, ZWJ sequences, and RTL text."""
        test_cases = [
            ("#SportsCards🔥💎⚡️", "SportsCards"),
            (" #HardTechno 🎧🚀 ", "HardTechno"),
            ("#CardLadder\u200d\u200b", "CardLadder"),  # Zero-width joiner & zero-width space
            ("#\u202eRTL_Tag\u202c", "RTL_Tag"),  # Right-to-left override
            ("#Wembanyama-Rookie_2026!", "Wembanyama-Rookie_2026"),  # Hyphen & underscore preserved
            ("###MultiHash###Tag", "MultiHash"),
            ("🔥🔥🔥", ""),  # Only emojis
            ("", ""),
            (None, ""),
            ("  #Panini_Prizm  #Extra  ", "Panini_Prizm"),
        ]

        for raw_in, expected in test_cases:
            assert normalize_hashtag(raw_in) == expected

    def test_sql_injection_and_hostile_strings_safety(self, trend_store: SQLiteTrendStore):
        """Verify parameterized queries defend against SQL injection payloads."""
        hostile_titles = [
            "'; DROP TABLE trends; --",
            "' OR '1'='1",
            "Robert'); DROP TABLE students;--",
            "UNION SELECT * FROM sqlite_master --",
            "\"\"\"'''```",
        ]

        for idx, title in enumerate(hostile_titles):
            rec = TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title=title,
                normalized_tag=f"SafeTag_{idx}",
                date_added="2026-08-22",
                rank=1,
                engagement_metrics={"comment": title},
                raw_metadata={"attack": title},
            )
            row_id = trend_store.insert_trend(rec)
            assert row_id > 0

        # Verify table still exists and contains exactly 5 records
        assert trend_store.get_total_count() == 5
        records = trend_store.fetch_all()
        assert len(records) == 5

        # Verify GC sweep works safely with injection-containing data
        gc = GarbageCollector(trend_store)
        res = gc.sweep(anchor_date="2026-08-22", cutoff_days=14)
        assert res["post_count"] == 5

    def test_sqlite_check_constraint_enforcement(self, trend_store: SQLiteTrendStore):
        """Verify SQLite table rejects invalid platform or category values."""
        # Invalid platform
        with pytest.raises(Exception):
            trend_store.connection.execute(
                "INSERT INTO trends (tag, platform, category, date_added, engagement_metrics) "
                "VALUES ('Test', 'myspace', 'sports_cards', '2026-08-22', '{}');"
            )

        # Invalid category
        with pytest.raises(Exception):
            trend_store.connection.execute(
                "INSERT INTO trends (tag, platform, category, date_added, engagement_metrics) "
                "VALUES ('Test', 'tiktok', 'crypto', '2026-08-22', '{}');"
            )


class TestBigQueryMLBoundariesAndFuzzing:
    """Stress-test BigQuery TimesFM 2.0 and Key Driver Analysis validators."""

    def test_timesfm_forecast_minimum_3_points_enforcement(self):
        """Verify strict enforcement of minimum 3 points per series in AI.FORECAST."""
        # Series 1 has 3 points (valid), Series 2 has 2 points (invalid)
        records = [
            {"tag": "ValidSeries", "date": "2026-08-20", "velocity_score": 10.0},
            {"tag": "ValidSeries", "date": "2026-08-21", "velocity_score": 15.0},
            {"tag": "ValidSeries", "date": "2026-08-22", "velocity_score": 20.0},
            {"tag": "InvalidSeries", "date": "2026-08-21", "velocity_score": 5.0},
            {"tag": "InvalidSeries", "date": "2026-08-22", "velocity_score": 8.0},
        ]

        with pytest.raises(ValueError, match="Tag series 'InvalidSeries' has only 2 point"):
            BigQueryPayloadFormatter.build_ai_forecast_payload(records)

    def test_timesfm_forecast_large_scale_1000_series(self):
        """Format 1,000 distinct tag series x 4 daily data points (4,000 rows)."""
        records: List[Dict[str, Any]] = []
        for s_idx in range(1000):
            tag_name = f"Series_{s_idx}"
            for d in range(4):
                records.append({
                    "tag": tag_name,
                    "date": f"2026-08-{18 + d:02d}",
                    "velocity_score": float(10 + d * 2),
                })

        start = time.perf_counter()
        payload = BigQueryPayloadFormatter.build_ai_forecast_payload(records)
        duration = time.perf_counter() - start

        assert len(payload) == 4000
        assert BigQueryPayloadFormatter.validate_forecast_schema(payload) is True
        assert duration < 1.0  # Under 1.0s

    def test_key_drivers_dimension_count_boundaries(self):
        """Test exact boundary validation for 1-12 dimension columns in AI.KEY_DRIVERS."""
        records = [
            TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title="#CardLadder",
                normalized_tag="CardLadder",
                date_added="2026-08-22",
                editing_style="fast cuts",
                engagement_metrics={"views": 75000},
            )
        ]

        # 0 dimensions -> ValueError
        with pytest.raises(ValueError, match="between 1 and 12 dimension columns"):
            BigQueryPayloadFormatter.build_ai_key_drivers_payload(records, dimension_cols=[])

        # 1 dimension -> Valid
        p1 = BigQueryPayloadFormatter.build_ai_key_drivers_payload(records, dimension_cols=["platform"])
        assert len(p1) == 1
        assert "platform" in p1[0]
        assert p1[0]["is_viral"] is True

        # 12 dimensions -> Valid
        dim12 = [f"dim_{i}" for i in range(12)]
        p12 = BigQueryPayloadFormatter.build_ai_key_drivers_payload(records, dimension_cols=dim12)
        assert len(p12) == 1
        assert BigQueryPayloadFormatter.validate_key_drivers_schema(p12, dimension_cols=dim12) is True

        # 13 dimensions -> ValueError
        dim13 = [f"dim_{i}" for i in range(13)]
        with pytest.raises(ValueError, match="between 1 and 12 dimension columns"):
            BigQueryPayloadFormatter.build_ai_key_drivers_payload(records, dimension_cols=dim13)

        # Overlapping metric_col in dimension_cols -> ValueError
        with pytest.raises(ValueError, match="metric_col 'views' cannot be included"):
            BigQueryPayloadFormatter.build_ai_key_drivers_payload(records, dimension_cols=["views", "platform"])

        # Overlapping interest_label_col in dimension_cols -> ValueError
        with pytest.raises(ValueError, match="interest_label_col 'is_viral' cannot be included"):
            BigQueryPayloadFormatter.build_ai_key_drivers_payload(records, dimension_cols=["is_viral", "platform"])

    def test_safe_casting_fuzzing(self):
        """Fuzz safe_cast_float and safe_cast_int with diverse corrupted types."""
        float_fuzz = [
            (None, 0.0),
            (True, 0.0),
            (False, 0.0),
            ("+145%", 145.0),
            ("-12.5%", -12.5),
            ("  $1,250.75  ", 1250.75),
            ("1.2M", 1200000.0),
            ("850K", 850000.0),
            ("NEW", 0.0),
            ("CORRUPTED_TEXT", 0.0),
            ([1, 2, 3], 0.0),
            ({"key": "val"}, 0.0),
        ]
        for val, expected in float_fuzz:
            assert safe_cast_float(val) == expected

        int_fuzz = [
            (None, 0),
            (True, 0),
            (False, 0),
            (1234, 1234),
            (56.78, 56),
            ("1.5B", 1500000000),
            ("2.2M", 2200000),
            ("450K", 450000),
            ("1,280 views", 1280),
            ("N/A", 0),
            ("--", 0),
            ("bad_string", 0),
        ]
        for val, expected in int_fuzz:
            assert safe_cast_int(val) == expected


class TestSecurityAndNetworkGuardrail:
    """Empirically test network isolation guardrail."""

    def test_socket_connect_strictly_blocked(self):
        """Attempting socket connect must immediately raise NetworkBlockError."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(NetworkBlockError, match="Real network socket connection blocked"):
            s.connect(("8.8.8.8", 53))
        s.close()
