"""Integration test suite for BigQuery ML Payload Formatting (Milestone M3 / R3).

Validates tag array unnesting, whitespace/emoji stripping, case-preserving deduplication,
BigQuery TimesFM 2.0 (AI.FORECAST) time-series constraints (>=3 points),
BigQuery Key Drivers (AI.KEY_DRIVERS) TVF dimension schemas (1-12 cols), and edge cases.
"""

from datetime import datetime, timedelta
import time
from typing import Any, Dict, List
import pytest

from viral_trend_pipeline.models import TrendRecord
from viral_trend_pipeline.exporters.bigquery_payload import (
    BigQueryPayloadFormatter,
    safe_cast_float,
    safe_cast_int,
    format_iso_timestamp,
)


class TestTagArrayNormalization:
    """Validate tag array unnesting, whitespace stripping, emoji stripping, case preservation, and deduplication."""

    def test_basic_tag_normalization_and_whitespace(self):
        """Verify trimming outer whitespace, tabs, and leading hashes."""
        raw = ["#SportsCards", "  #PaniniPrizm  ", "\t#CardLadder\n", "#TheHobby"]
        result = BigQueryPayloadFormatter.normalize_tag_array(raw)
        assert result == ["SportsCards", "PaniniPrizm", "CardLadder", "TheHobby"]

    def test_emoji_and_special_symbol_stripping(self):
        """Verify emojis and decorative symbols are stripped while preserving tag alphanumeric core."""
        raw = ["#CardLadder🔥", "#HardTechno⚡️", "#EDM🎧🎉", "#SportsCards🏆", "#RaveTok✨"]
        result = BigQueryPayloadFormatter.normalize_tag_array(raw)
        assert result == ["CardLadder", "HardTechno", "EDM", "SportsCards", "RaveTok"]

    def test_strict_case_preservation_distinct_tags(self):
        """Verify that case differences are strictly preserved and treated as distinct entities."""
        raw = ["#SportsCards", "#sportscards", "#SPORTSCARDS", "#sportsCards"]
        result = BigQueryPayloadFormatter.normalize_tag_array(raw)
        # All 4 variations have distinct casing and must all be preserved in order
        assert result == ["SportsCards", "sportscards", "SPORTSCARDS", "sportsCards"]

    def test_case_sensitive_deduplication(self):
        """Verify exact case-sensitive deduplication where identical strings are deduplicated."""
        raw = [
            "#SportsCards",
            " #SportsCards ",
            "#sportscards",
            "#CardLadder🔥",
            "#CardLadder",
            "#SportsCards",
        ]
        result = BigQueryPayloadFormatter.normalize_tag_array(raw)
        assert result == ["SportsCards", "sportscards", "CardLadder"]

    def test_nested_arrays_and_iterables(self):
        """Verify recursive unnesting of nested lists, tuples, and sets."""
        raw = [
            "#Tag1",
            ["#Tag2", ["#Tag3", "#Tag4"]],
            ("#Tag5", "#Tag6"),
            {"#Tag7"},
        ]
        result = BigQueryPayloadFormatter.normalize_tag_array(raw)
        assert "Tag1" in result
        assert "Tag2" in result
        assert "Tag3" in result
        assert "Tag4" in result
        assert "Tag5" in result
        assert "Tag6" in result
        assert "Tag7" in result
        assert len(result) == 7

    def test_null_empty_and_zero_width_filtering(self):
        """Verify None, empty strings, whitespace-only, and zero-width spaces are filtered out."""
        raw = [
            "#SportsCards",
            "",
            None,
            "   ",
            "\u200b\ufeff",
            "#",
            "###",
            "#EDM",
        ]
        result = BigQueryPayloadFormatter.normalize_tag_array(raw)
        assert result == ["SportsCards", "EDM"]

    def test_hyphen_and_underscore_preservation(self):
        """Verify internal hyphens and underscores are preserved in tags."""
        raw = ["#Topps-Chrome_2026", "#Sports-Cards_Investing", "#Hard_Techno-2026!"]
        result = BigQueryPayloadFormatter.normalize_tag_array(raw)
        assert result == ["Topps-Chrome_2026", "Sports-Cards_Investing", "Hard_Techno-2026"]

    def test_alias_normalize_tags_matches(self):
        """Verify that normalize_tags alias behaves identically to normalize_tag_array."""
        raw = ["#SportsCards", "#CardLadder"]
        assert BigQueryPayloadFormatter.normalize_tags(raw) == BigQueryPayloadFormatter.normalize_tag_array(raw)


class TestAIForecastPayloadFormatting:
    """Validate BigQuery TimesFM 2.0 AI.FORECAST time-series payload generation and constraints."""

    def test_forecast_minimum_3_points_happy_path(self):
        """Format 3 historical data points for a single tag series (minimum boundary)."""
        records = [
            TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title="#SportsCards",
                normalized_tag="SportsCards",
                date_added="2026-08-20",
                velocity_metric=75.2,
            ),
            TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title="#SportsCards",
                normalized_tag="SportsCards",
                date_added="2026-08-21",
                velocity_metric=82.0,
            ),
            TrendRecord(
                platform="tiktok",
                category="sports_cards",
                trend_type="hashtag",
                raw_title="#SportsCards",
                normalized_tag="SportsCards",
                date_added="2026-08-22",
                velocity_metric=89.4,
            ),
        ]
        payload = BigQueryPayloadFormatter.build_ai_forecast_payload(records)

        assert len(payload) == 3
        assert payload[0]["tag"] == "SportsCards"
        assert payload[0]["date"] == "2026-08-20T00:00:00Z"
        assert payload[0]["velocity_score"] == 75.2

        assert payload[1]["date"] == "2026-08-21T00:00:00Z"
        assert payload[1]["velocity_score"] == 82.0

        assert payload[2]["date"] == "2026-08-22T00:00:00Z"
        assert payload[2]["velocity_score"] == 89.4

        assert BigQueryPayloadFormatter.validate_forecast_schema(payload) is True

    def test_forecast_raises_value_error_if_under_3_points(self):
        """TimesFM 2.0 requires minimum 3 points; verify ValueError is raised for 1 or 2 points."""
        # 1 point
        records_1 = [
            TrendRecord(
                platform="tiktok",
                category="edm",
                trend_type="hashtag",
                raw_title="#HardTechno",
                normalized_tag="HardTechno",
                date_added="2026-08-22",
                velocity_metric=90.0,
            )
        ]
        with pytest.raises(ValueError, match="minimum of 3 historical data points"):
            BigQueryPayloadFormatter.build_ai_forecast_payload(records_1)

        # 2 points
        records_2 = [
            TrendRecord(
                platform="tiktok",
                category="edm",
                trend_type="hashtag",
                raw_title="#HardTechno",
                normalized_tag="HardTechno",
                date_added="2026-08-21",
                velocity_metric=85.0,
            ),
            TrendRecord(
                platform="tiktok",
                category="edm",
                trend_type="hashtag",
                raw_title="#HardTechno",
                normalized_tag="HardTechno",
                date_added="2026-08-22",
                velocity_metric=90.0,
            ),
        ]
        with pytest.raises(ValueError, match="minimum of 3 historical data points"):
            BigQueryPayloadFormatter.build_ai_forecast_payload(records_2)

    def test_forecast_multi_series_grouping_and_chronological_ordering(self):
        """Format multiple tag series (unordered) and verify correct grouping and ascending date sort."""
        records = [
            # Tag B out of order
            {"tag": "TagB", "date": "2026-08-22", "velocity_score": 90.0},
            {"tag": "TagA", "date": "2026-08-21", "velocity_score": 50.0},
            {"tag": "TagB", "date": "2026-08-20", "velocity_score": 70.0},
            {"tag": "TagA", "date": "2026-08-20", "velocity_score": 40.0},
            {"tag": "TagB", "date": "2026-08-21", "velocity_score": 80.0},
            {"tag": "TagA", "date": "2026-08-22", "velocity_score": 60.0},
        ]
        payload = BigQueryPayloadFormatter.build_ai_forecast_payload(records)
        assert len(payload) == 6

        # TagA items
        tag_a = [p for p in payload if p["tag"] == "TagA"]
        assert [p["date"] for p in tag_a] == [
            "2026-08-20T00:00:00Z",
            "2026-08-21T00:00:00Z",
            "2026-08-22T00:00:00Z",
        ]
        assert [p["velocity_score"] for p in tag_a] == [40.0, 50.0, 60.0]

        # TagB items
        tag_b = [p for p in payload if p["tag"] == "TagB"]
        assert [p["date"] for p in tag_b] == [
            "2026-08-20T00:00:00Z",
            "2026-08-21T00:00:00Z",
            "2026-08-22T00:00:00Z",
        ]
        assert [p["velocity_score"] for p in tag_b] == [70.0, 80.0, 90.0]

    def test_forecast_custom_metric_field(self):
        """Verify building forecast payload with custom metric field (e.g. 'views')."""
        records = [
            {"tag": "CardLadder", "date": "2026-08-20", "views": 10000},
            {"tag": "CardLadder", "date": "2026-08-21", "views": 15000},
            {"tag": "CardLadder", "date": "2026-08-22", "views": 25000},
        ]
        payload = BigQueryPayloadFormatter.build_ai_forecast_payload(records, metric_field="views")
        assert len(payload) == 3
        assert payload[0]["views"] == 10000.0
        assert BigQueryPayloadFormatter.validate_forecast_schema(payload, metric_field="views") is True


class TestAIKeyDriversPayloadFormatting:
    """Validate BigQuery AI.KEY_DRIVERS TVF input table payload generation and constraints."""

    def test_key_drivers_happy_path_and_is_viral_calculation(self):
        """Verify dimension extraction, numeric views parsing, and boolean is_viral assignment at threshold."""
        records = [
            TrendRecord(
                platform="tiktok",
                category="edm",
                trend_type="hashtag",
                raw_title="#StutterEdit",
                normalized_tag="StutterEdit",
                date_added="2026-08-22",
                editing_style="stutter edit",
                engagement_metrics={"views": 450000},
            ),
            TrendRecord(
                platform="tiktok",
                category="edm",
                trend_type="hashtag",
                raw_title="#SlowZoom",
                normalized_tag="SlowZoom",
                date_added="2026-08-22",
                editing_style="slow zoom",
                engagement_metrics={"views": 25000},
            ),
        ]
        payload = BigQueryPayloadFormatter.build_ai_key_drivers_payload(
            records,
            viral_threshold=50000,
        )

        assert len(payload) == 2
        # First row >= 50,000 views -> is_viral is True
        assert payload[0]["editing_style"] == "stutter edit"
        assert payload[0]["platform"] == "tiktok"
        assert payload[0]["category"] == "edm"
        assert payload[0]["is_viral"] is True
        assert payload[0]["views"] == 450000

        # Second row < 50,000 views -> is_viral is False
        assert payload[1]["editing_style"] == "slow zoom"
        assert payload[1]["platform"] == "tiktok"
        assert payload[1]["category"] == "edm"
        assert payload[1]["is_viral"] is False
        assert payload[1]["views"] == 25000

        assert BigQueryPayloadFormatter.validate_key_drivers_schema(payload) is True

    def test_key_drivers_threshold_boundary_values(self):
        """Verify is_viral boolean flag at exact threshold boundary."""
        records = [
            {"editing_style": "cut", "platform": "tiktok", "category": "sports_cards", "views": 49999},
            {"editing_style": "cut", "platform": "tiktok", "category": "sports_cards", "views": 50000},
            {"editing_style": "cut", "platform": "tiktok", "category": "sports_cards", "views": 50001},
        ]
        payload = BigQueryPayloadFormatter.build_ai_key_drivers_payload(records, viral_threshold=50000)

        assert payload[0]["is_viral"] is False  # 49999 < 50000
        assert payload[1]["is_viral"] is True   # 50000 == 50000 (boundary included)
        assert payload[2]["is_viral"] is True   # 50001 > 50000

    def test_key_drivers_dimension_count_boundaries(self):
        """Verify validation of 1 to 12 dimension columns (BigQuery ML constraint)."""
        sample_record = [
            {"dim1": "val1", "views": 100000}
        ]

        # 1 dimension column (minimum valid)
        p1 = BigQueryPayloadFormatter.build_ai_key_drivers_payload(
            sample_record,
            dimension_cols=["dim1"],
        )
        assert len(p1) == 1
        assert "dim1" in p1[0]
        assert BigQueryPayloadFormatter.validate_key_drivers_schema(p1, dimension_cols=["dim1"]) is True

        # 12 dimension columns (maximum valid)
        cols_12 = [f"dim_{i}" for i in range(1, 13)]
        sample_12 = [{**{c: f"v_{c}" for c in cols_12}, "views": 75000}]
        p12 = BigQueryPayloadFormatter.build_ai_key_drivers_payload(
            sample_12,
            dimension_cols=cols_12,
        )
        assert len(p12) == 1
        assert BigQueryPayloadFormatter.validate_key_drivers_schema(p12, dimension_cols=cols_12) is True

        # 0 dimension columns -> ValueError
        with pytest.raises(ValueError, match="requires between 1 and 12 dimension columns"):
            BigQueryPayloadFormatter.build_ai_key_drivers_payload(sample_record, dimension_cols=[])

        # 13 dimension columns -> ValueError
        cols_13 = [f"dim_{i}" for i in range(1, 14)]
        with pytest.raises(ValueError, match="requires between 1 and 12 dimension columns"):
            BigQueryPayloadFormatter.build_ai_key_drivers_payload(sample_record, dimension_cols=cols_13)

    def test_key_drivers_metric_and_label_overlap_rejection(self):
        """Verify error is raised if metric_col or interest_label_col is mistakenly in dimension_cols."""
        records = [{"editing_style": "cut", "platform": "tiktok", "views": 10000}]
        with pytest.raises(ValueError, match="metric_col 'views' cannot be included"):
            BigQueryPayloadFormatter.build_ai_key_drivers_payload(
                records,
                dimension_cols=["editing_style", "views"],
            )

        with pytest.raises(ValueError, match="interest_label_col 'is_viral' cannot be included"):
            BigQueryPayloadFormatter.build_ai_key_drivers_payload(
                records,
                dimension_cols=["editing_style", "is_viral"],
            )


class TestSafeCastingAndEdgeCases:
    """Validate safe casting helpers, corrupted data fallback, multi-platform exporting, and schema validators."""

    def test_safe_cast_float_variations(self):
        """Verify safe_cast_float handles various string patterns, percentages, commas, and corrupt values."""
        assert safe_cast_float(42.5) == 42.5
        assert safe_cast_float(100) == 100.0
        assert safe_cast_float("+125.5%") == 125.5
        assert safe_cast_float("-14.2%") == -14.2
        assert safe_cast_float("1,250.75") == 1250.75
        assert safe_cast_float("$450.00") == 450.00
        assert safe_cast_float("1.2M") == 1200000.0
        assert safe_cast_float("850K") == 850000.0
        assert safe_cast_float(None, default=0.0) == 0.0
        assert safe_cast_float(True, default=0.0) == 0.0  # Booleans should not be cast to 1.0
        assert safe_cast_float("INVALID_DATA", default=-1.0) == -1.0

    def test_safe_cast_int_variations(self):
        """Verify safe_cast_int handles numbers, strings with suffixes (K, M, B), and corrupt inputs."""
        assert safe_cast_int(50000) == 50000
        assert safe_cast_int(42.8) == 42
        assert safe_cast_int("250,000") == 250000
        assert safe_cast_int("1.5M") == 1500000
        assert safe_cast_int("2.5B") == 2500000000
        assert safe_cast_int("750K") == 750000
        assert safe_cast_int(None, default=0) == 0
        assert safe_cast_int(False, default=0) == 0
        assert safe_cast_int("CORRUPTED_STRING", default=0) == 0

    def test_format_iso_timestamp_variations(self):
        """Verify timestamp normalization across dates, datetimes, and strings."""
        assert format_iso_timestamp("2026-08-22") == "2026-08-22T00:00:00Z"
        assert format_iso_timestamp("2026-08-22T14:30:00Z") == "2026-08-22T14:30:00Z"
        dt = datetime(2026, 8, 22, 18, 0, 0)
        assert format_iso_timestamp(dt) == "2026-08-22T18:00:00Z"

    def test_empty_lists_payload_handling(self):
        """Verify empty input lists produce empty output payloads and validate as True."""
        assert BigQueryPayloadFormatter.build_ai_forecast_payload([]) == []
        assert BigQueryPayloadFormatter.build_ai_key_drivers_payload([]) == []
        assert BigQueryPayloadFormatter.validate_forecast_schema([]) is True
        assert BigQueryPayloadFormatter.validate_key_drivers_schema([]) is True

    def test_schema_validators_reject_invalid_payloads(self):
        """Verify schema validators detect missing keys, invalid types, or invalid series."""
        # Forecast missing 'tag'
        assert BigQueryPayloadFormatter.validate_forecast_schema([
            {"date": "2026-08-20T00:00:00Z", "velocity_score": 10.0}
        ]) is False

        # Forecast invalid boolean metric
        assert BigQueryPayloadFormatter.validate_forecast_schema([
            {"tag": "T", "date": "2026-08-20T00:00:00Z", "velocity_score": True}
        ]) is False

        # Forecast insufficient historical points (<3)
        assert BigQueryPayloadFormatter.validate_forecast_schema([
            {"tag": "T", "date": "2026-08-20T00:00:00Z", "velocity_score": 10.0},
            {"tag": "T", "date": "2026-08-21T00:00:00Z", "velocity_score": 20.0},
        ]) is False

        # Key drivers missing dimension
        assert BigQueryPayloadFormatter.validate_key_drivers_schema([
            {"editing_style": "cut", "is_viral": True, "views": 10000}
        ], dimension_cols=["editing_style", "platform"]) is False

        # Key drivers invalid boolean label type
        assert BigQueryPayloadFormatter.validate_key_drivers_schema([
            {"editing_style": "cut", "platform": "tiktok", "category": "edm", "is_viral": "YES", "views": 10000}
        ]) is False

    def test_multi_platform_and_multi_category_export(self):
        """Verify building payloads containing records across all 4 platforms and 2 categories."""
        platforms = ["tiktok", "instagram", "youtube", "facebook"]
        categories = ["sports_cards", "edm"]
        records: List[TrendRecord] = []

        for p in platforms:
            for c in categories:
                records.append(
                    TrendRecord(
                        platform=p,
                        category=c,
                        trend_type="hashtag",
                        raw_title=f"#{p}_{c}",
                        normalized_tag=f"{p}_{c}",
                        date_added="2026-08-22",
                        editing_style="fast cuts",
                        engagement_metrics={"views": 75000, "velocity_score": 88.0},
                    )
                )

        # Key drivers payload
        kd_payload = BigQueryPayloadFormatter.build_ai_key_drivers_payload(records, viral_threshold=50000)
        assert len(kd_payload) == 8
        assert all(row["is_viral"] is True for row in kd_payload)
        assert BigQueryPayloadFormatter.validate_key_drivers_schema(kd_payload) is True


class TestHighVolumeAndPerformanceBenchmark:
    """Benchmark high-volume tag normalization and payload generation."""

    def test_high_volume_10k_tag_normalization_sub_200ms(self):
        """Normalize 10,000 raw tags with duplicates, emojis, and whitespace under 200ms."""
        base_tags = [
            "#SportsCards", " #SportsCards ", "#sportscards", "#CardLadder🔥",
            "#TheHobby", "  #PaniniPrizm  ", "#HardTechno⚡️", "#RaveTok✨",
            "#EDMDrop", "#WhoDoYouCollect",
        ]
        large_tag_list = base_tags * 1000  # 10,000 tags
        assert len(large_tag_list) == 10000

        start_time = time.perf_counter()
        normalized = BigQueryPayloadFormatter.normalize_tag_array(large_tag_list)
        elapsed = time.perf_counter() - start_time

        # Deduplication yields exactly the unique case-preserved tags
        assert len(normalized) == 9
        assert "SportsCards" in normalized
        assert "sportscards" in normalized
        assert "CardLadder" in normalized
        assert elapsed < 0.2, f"Expected < 0.2s, took {elapsed:.4f}s"

    def test_1000_record_forecast_and_key_drivers_formatting_sub_200ms(self):
        """Format 1,000 records for TimesFM 2.0 forecast and Key Drivers under 200ms."""
        records: List[TrendRecord] = []
        anchor_dt = datetime(2026, 8, 22)

        # 50 tags * 20 days = 1,000 records (20 points per tag series > 3 min requirement)
        for tag_idx in range(50):
            tag_name = f"TrendTag_{tag_idx}"
            for day in range(20):
                d_str = (anchor_dt - timedelta(days=day)).strftime("%Y-%m-%d")
                records.append(
                    TrendRecord(
                        platform="tiktok" if tag_idx % 2 == 0 else "instagram",
                        category="sports_cards" if tag_idx % 2 == 0 else "edm",
                        trend_type="hashtag",
                        raw_title=f"#{tag_name}",
                        normalized_tag=tag_name,
                        date_added=d_str,
                        velocity_metric=float(50 + (day * 2)),
                        editing_style="stutter edit" if day % 2 == 0 else "slow zoom",
                        engagement_metrics={"views": 30000 + (day * 2000)},
                    )
                )

        assert len(records) == 1000

        start_time = time.perf_counter()
        forecast_payload = BigQueryPayloadFormatter.build_ai_forecast_payload(records)
        kd_payload = BigQueryPayloadFormatter.build_ai_key_drivers_payload(records, viral_threshold=50000)
        elapsed = time.perf_counter() - start_time

        assert len(forecast_payload) == 1000
        assert len(kd_payload) == 1000
        assert BigQueryPayloadFormatter.validate_forecast_schema(forecast_payload) is True
        assert BigQueryPayloadFormatter.validate_key_drivers_schema(kd_payload) is True
        assert elapsed < 0.2, f"Expected < 0.2s, took {elapsed:.4f}s"
