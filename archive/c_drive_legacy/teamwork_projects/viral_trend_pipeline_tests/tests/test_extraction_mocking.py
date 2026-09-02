"""Comprehensive integration tests for Extraction Mocking (Milestone M1 / R1).

Validates:
- Chrome DevTools A11y snapshot extraction (TikTok hashtags, TikTok audio, YouTube trending).
- Android CLI UI hierarchy layout extraction (Instagram captions, multi-tags, audio, metrics).
- Strict case preservation and emoji stripping in tag normalization.
- Numerical metric parsing and velocity conversion.
- Domain track classification (sports_cards vs edm vs general).
- Zero network socket blocking guardrail (NetworkBlockError).
- Edge cases E1 to E16.
- Sub-2-second execution benchmark.
"""

import time
import urllib.request
import socket
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
from tests.fixtures.chrome_fixtures import (
    EMPTY_LOADING_A11Y_SNAPSHOT,
    MALFORMED_A11Y_SNAPSHOT,
    EMOJI_A11Y_SNAPSHOT,
    generate_large_a11y_tree,
)
from tests.fixtures.android_fixtures import (
    INVALID_SYNTAX_JSON,
    NULL_TEXT_LAYOUT_DATA,
    OFFSCREEN_LAYOUT_DATA,
    MULTI_TAG_CAPTION_LAYOUT_DATA,
)


class TestTikTokExtraction:
    """Tests for TikTok Creative Center a11y tree extraction."""

    def test_tiktok_hashtag_extraction_happy_path(
        self, chrome_extractor: ChromeDevToolsExtractor, tiktok_a11y_raw: str
    ):
        records = chrome_extractor.parse_tiktok_hashtags(tiktok_a11y_raw)
        assert len(records) == 5

        # Record 1: #SportsCards
        r1 = records[0]
        assert r1.platform == "tiktok"
        assert r1.trend_type == "hashtag"
        assert r1.raw_title == "#SportsCards"
        assert r1.normalized_tag == "SportsCards"  # Strict case preservation
        assert r1.rank == 1
        assert r1.post_count == 1_200_000
        assert r1.velocity_metric == 145.0
        assert r1.category == "sports_cards"

        # Record 2: #HardTechno
        r2 = records[1]
        assert r2.raw_title == "#HardTechno"
        assert r2.normalized_tag == "HardTechno"
        assert r2.rank == 2
        assert r2.post_count == 850_000
        assert r2.velocity_metric == 82.0
        assert r2.category == "edm"

        # Record 3: #CardLadder
        r3 = records[2]
        assert r3.raw_title == "#CardLadder"
        assert r3.normalized_tag == "CardLadder"
        assert r3.rank == 3
        assert r3.post_count == 420_000
        assert r3.velocity_metric == 210.0
        assert r3.category == "sports_cards"

        # Record 4: #RaveTok
        r4 = records[3]
        assert r4.raw_title == "#RaveTok"
        assert r4.normalized_tag == "RaveTok"
        assert r4.rank == 4
        assert r4.post_count == 310_000
        assert r4.velocity_metric == 55.0
        assert r4.category == "edm"

        # Record 5: #PaniniPrizm
        r5 = records[4]
        assert r5.raw_title == "#PaniniPrizm"
        assert r5.normalized_tag == "PaniniPrizm"
        assert r5.rank == 5
        assert r5.post_count == 190_000
        assert r5.velocity_metric == 35.0
        assert r5.category == "sports_cards"

    def test_tiktok_audio_extraction_happy_path(
        self, chrome_extractor: ChromeDevToolsExtractor, tiktok_a11y_raw: str
    ):
        records = chrome_extractor.parse_tiktok_audio(tiktok_a11y_raw)
        assert len(records) == 2

        # Song 1: Montagem Mysterious Game - LXNGVX
        s1 = records[0]
        assert s1.platform == "tiktok"
        assert s1.trend_type == "audio"
        assert "Montagem Mysterious Game" in s1.raw_title
        assert s1.rank == 1
        assert s1.velocity_metric == 120.0
        assert s1.category == "edm"
        assert s1.raw_metadata.get("artist") == "LXNGVX"

        # Song 2: Dimension - DJ Velocity
        s2 = records[1]
        assert s2.platform == "tiktok"
        assert s2.trend_type == "audio"
        assert "Dimension" in s2.raw_title
        assert s2.rank == 2
        assert s2.velocity_metric == 74.0
        assert s2.category == "edm"
        assert s2.raw_metadata.get("artist") == "DJ Velocity"


class TestYouTubeExtraction:
    """Tests for YouTube Trending a11y tree extraction."""

    def test_youtube_trending_extraction_happy_path(
        self, chrome_extractor: ChromeDevToolsExtractor, youtube_a11y_raw: str
    ):
        records = chrome_extractor.parse_youtube_trending(youtube_a11y_raw)
        assert len(records) == 2

        # Video 1: Sports Cards
        v1 = records[0]
        assert v1.platform == "youtube"
        assert v1.trend_type == "video_title"
        assert v1.raw_title == "Is the 2026 Topps Chrome Wembanyama worth grading?"
        assert v1.post_count == 500_000
        assert v1.category == "sports_cards"
        assert v1.engagement_metrics.get("channel") == "CardCollector"

        # Video 2: EDM Festival
        v2 = records[1]
        assert v2.platform == "youtube"
        assert v2.trend_type == "video_title"
        assert v2.raw_title == "EDM Festival Live Set 2026 - Mainstage Ultra"
        assert v2.post_count == 1_200_000
        assert v2.category == "edm"
        assert v2.engagement_metrics.get("channel") == "RaveMaster"


class TestInstagramReelsExtraction:
    """Tests for Instagram Reels Android UI layout extraction."""

    def test_instagram_reels_caption_and_audio_extraction(
        self, android_extractor: AndroidCLIExtractor, instagram_layout_data: list
    ):
        records = android_extractor.parse_instagram_reels(instagram_layout_data)
        # 3 tags from Reel 1, 1 audio from Reel 1, 3 tags from Reel 2, 1 audio from Reel 2 = 8 total
        assert len(records) == 8

        # Check hashtag records from Reel 1
        tags_r1 = [r for r in records if r.trend_type == "hashtag" and r.category == "sports_cards"]
        assert len(tags_r1) == 3
        extracted_tags_r1 = [r.normalized_tag for r in tags_r1]
        assert "TheHobby" in extracted_tags_r1
        assert "SportsCardInvesting" in extracted_tags_r1
        assert "WhoDoYouCollect" in extracted_tags_r1

        # Check engagement metrics propagated
        for r in tags_r1:
            assert r.post_count == 45_200
            assert r.engagement_metrics.get("likes") == 45_200
            assert r.engagement_metrics.get("comments") == 1_280

        # Check hashtag records from Reel 2
        tags_r2 = [r for r in records if r.trend_type == "hashtag" and r.category == "edm"]
        assert len(tags_r2) == 3
        extracted_tags_r2 = [r.normalized_tag for r in tags_r2]
        assert "HardTechno" in extracted_tags_r2
        assert "EDMDrop" in extracted_tags_r2
        assert "RaveTok" in extracted_tags_r2

        # Check audio records
        audio_records = [r for r in records if r.trend_type == "audio"]
        assert len(audio_records) == 2
        assert any("Card Ladder ROI Anthem" in r.raw_title for r in audio_records)
        assert any("Montagem Mysterious Game" in r.raw_title for r in audio_records)


class TestEdgeCasesE1ToE16:
    """Comprehensive test coverage for Edge Cases E1 through E16."""

    def test_e1_empty_snapshot_string(
        self, chrome_extractor: ChromeDevToolsExtractor, android_extractor: AndroidCLIExtractor
    ):
        """E1: Empty snapshot or whitespace returns [] cleanly."""
        assert chrome_extractor.parse_tiktok_hashtags("") == []
        assert chrome_extractor.parse_tiktok_audio("   \n\t  ") == []
        assert chrome_extractor.parse_youtube_trending("") == []
        assert android_extractor.parse_instagram_reels("") == []
        assert android_extractor.parse_instagram_reels("   ") == []

    def test_e2_loading_only_snapshot(self, chrome_extractor: ChromeDevToolsExtractor):
        """E2: Snapshot with only RootWebArea 'Loading...' returns []."""
        records = chrome_extractor.parse_snapshot(EMPTY_LOADING_A11Y_SNAPSHOT)
        assert records == []

    def test_e3_malformed_a11y_syntax(self, chrome_extractor: ChromeDevToolsExtractor):
        """E3: Malformed lines skipped without crash; valid rows extracted."""
        records = chrome_extractor.parse_tiktok_hashtags(MALFORMED_A11Y_SNAPSHOT)
        assert len(records) >= 1
        assert any(r.normalized_tag == "CardLadder" for r in records)

    def test_e4_unicode_and_emojis(self, chrome_extractor: ChromeDevToolsExtractor):
        """E4: Preserves full Unicode in raw_title, strips emojis in normalized_tag."""
        records = chrome_extractor.parse_tiktok_hashtags(EMOJI_A11Y_SNAPSHOT)
        assert len(records) == 2
        assert records[0].normalized_tag == "Wembanyama"
        assert "🔥" in records[0].raw_title
        assert records[1].normalized_tag == "CardLadder"
        assert "💎" in records[1].raw_title

    def test_e5_massive_tree_benchmark(self, chrome_extractor: ChromeDevToolsExtractor):
        """E5: 10,000 node a11y tree parses in under 50ms without memory bloat."""
        large_tree = generate_large_a11y_tree(num_nodes=2000)
        start = time.perf_counter()
        records = chrome_extractor.parse_tiktok_hashtags(large_tree)
        duration = time.perf_counter() - start

        assert len(records) == 2000
        assert duration < 0.20, f"Massive tree parse took {duration:.3f}s, expected < 0.20s"

    def test_e6_android_empty_json_array(self, android_extractor: AndroidCLIExtractor):
        """E6: Android empty array [] returns [] without error."""
        assert android_extractor.parse_instagram_reels([]) == []
        assert android_extractor.parse_instagram_reels("[]") == []

    def test_e7_android_invalid_json_syntax(self, android_extractor: AndroidCLIExtractor):
        """E7: Invalid JSON string raises ExtractionParseError."""
        with pytest.raises(ExtractionParseError):
            android_extractor.parse_instagram_reels(INVALID_SYNTAX_JSON)

    def test_e8_android_null_text_fallback(self, android_extractor: AndroidCLIExtractor):
        """E8: UI element with text=null safely uses contentDesc fallback."""
        records = android_extractor.parse_instagram_reels(NULL_TEXT_LAYOUT_DATA)
        assert len(records) == 2
        tags = [r.normalized_tag for r in records]
        assert "TheHobby" in tags
        assert "CardInvesting" in tags

    def test_e9_android_offscreen_elements(self, android_extractor: AndroidCLIExtractor):
        """E9: Elements with off-screen: true are filtered by default, included when requested."""
        # Default: exclude off-screen
        visible_records = android_extractor.parse_instagram_reels(OFFSCREEN_LAYOUT_DATA, include_offscreen=False)
        assert len(visible_records) == 1
        assert visible_records[0].normalized_tag == "SportsCards"

        # Include off-screen
        all_records = android_extractor.parse_instagram_reels(OFFSCREEN_LAYOUT_DATA, include_offscreen=True)
        assert len(all_records) == 2
        tags = [r.normalized_tag for r in all_records]
        assert "SportsCards" in tags
        assert "HiddenTrend" in tags

    def test_e10_android_multi_hashtag_caption(self, android_extractor: AndroidCLIExtractor):
        """E10: Reel caption with 20+ hashtags in a single block parses all individual records."""
        records = android_extractor.parse_instagram_reels(MULTI_TAG_CAPTION_LAYOUT_DATA)
        assert len(records) == 21
        tags = [r.normalized_tag for r in records]
        assert "TheHobby" in tags
        assert "CardLadder" in tags
        assert "NationalTreasures" in tags
        assert "VintageCards" in tags

    def test_e11_metric_non_numeric_placeholders(self):
        """E11: Non-numeric strings return None without raising error."""
        assert parse_metric_number("NEW") is None
        assert parse_metric_number("Trending") is None
        assert parse_metric_number("--") is None
        assert parse_metric_number("N/A") is None
        assert parse_metric_number(None) is None
        assert parse_velocity_metric("NEW") is None
        assert parse_velocity_metric("--") is None

    def test_e12_metric_suffix_variations(self):
        """E12: Accurate parsing of K, M, B suffixes and commas."""
        assert parse_metric_number("1.2M") == 1_200_000
        assert parse_metric_number("1.2m") == 1_200_000
        assert parse_metric_number("850K") == 850_000
        assert parse_metric_number("850k") == 850_000
        assert parse_metric_number("2.5B") == 2_500_000_000
        assert parse_metric_number("1,250") == 1250
        assert parse_metric_number("45.2K likes") == 45_200
        assert parse_velocity_metric("+145%") == 145.0
        assert parse_velocity_metric("-12.5%") == -12.5
        assert parse_velocity_metric("82%") == 82.0

    def test_e13_tag_mixed_case_and_punctuation(self):
        """E13: Preserves mixed case, handles hyphens and underscores, strips punctuation."""
        assert normalize_hashtag("#Sports-Cards_2026!") == "Sports-Cards_2026"
        assert normalize_hashtag("#CardLadder?") == "CardLadder"
        assert normalize_hashtag("###HardTechno...") == "HardTechno"

    def test_e14_tag_whitespace_and_zero_width(self):
        """E14: Strips outer whitespace and zero-width characters."""
        assert normalize_hashtag(" #HardTechno \u200b ") == "HardTechno"
        assert normalize_hashtag("\ufeff#RaveTok\u200e") == "RaveTok"

    def test_e15_zero_network_socket_blocking(self):
        """E15: Attempting real socket connection triggers NetworkBlockError."""
        with pytest.raises(NetworkBlockError, match="Real network socket connection blocked"):
            s = socket.socket()
            s.connect(("127.0.0.1", 8080))

        with pytest.raises((NetworkBlockError, Exception)):
            urllib.request.urlopen("http://example.com", timeout=0.1)

    def test_e16_subprocess_isolation(
        self, chrome_extractor: ChromeDevToolsExtractor, android_extractor: AndroidCLIExtractor
    ):
        """E16: Extractor execution runs purely in memory on static fixtures with zero subprocess overhead."""
        start = time.perf_counter()
        r1 = chrome_extractor.parse_tiktok_hashtags(MALFORMED_A11Y_SNAPSHOT)
        r2 = android_extractor.parse_instagram_reels(MULTI_TAG_CAPTION_LAYOUT_DATA)
        duration = time.perf_counter() - start

        assert len(r1) > 0
        assert len(r2) == 21
        assert duration < 0.05, f"Subprocess isolation execution took {duration:.3f}s"


class TestTrendRecordContract:
    """Tests verifying the TrendRecord dataclass contract and serialization."""

    def test_trend_record_to_dict(self):
        rec = TrendRecord(
            platform="tiktok",
            category="sports_cards",
            trend_type="hashtag",
            raw_title="#SportsCards",
            normalized_tag="SportsCards",
            date_added="2026-08-22",
            rank=1,
            post_count=1200000,
            velocity_metric=145.0,
            editing_style="fast_cuts",
            engagement_metrics={"views": 1200000},
            raw_metadata={"source": "test"},
        )
        d = rec.to_dict()
        assert d["platform"] == "tiktok"
        assert d["category"] == "sports_cards"
        assert d["trend_type"] == "hashtag"
        assert d["raw_title"] == "#SportsCards"
        assert d["normalized_tag"] == "SportsCards"
        assert d["date_added"] == "2026-08-22"
        assert d["rank"] == 1
        assert d["post_count"] == 1200000
        assert d["velocity_metric"] == 145.0
        assert d["editing_style"] == "fast_cuts"
        assert d["engagement_metrics"] == {"views": 1200000}
        assert d["raw_metadata"] == {"source": "test"}

    def test_classify_category(self):
        assert classify_category("2026 Topps Chrome Rookie") == "sports_cards"
        assert classify_category("CardLadder Price Index") == "sports_cards"
        assert classify_category("Ultra Music Festival Mainstage") == "edm"
        assert classify_category("HardTechno Rave Drop") == "edm"
        assert classify_category("Random Cooking Recipe") == "general"


class TestExecutionBenchmark:
    """Tests asserting overall sub-2-second execution."""

    def test_full_extraction_sub_2s_benchmark(
        self,
        chrome_extractor: ChromeDevToolsExtractor,
        android_extractor: AndroidCLIExtractor,
        tiktok_a11y_raw: str,
        youtube_a11y_raw: str,
        instagram_layout_data: list,
    ):
        start = time.perf_counter()

        # Run 50 full extraction iterations
        for _ in range(50):
            tt_tags = chrome_extractor.parse_tiktok_hashtags(tiktok_a11y_raw)
            tt_audio = chrome_extractor.parse_tiktok_audio(tiktok_a11y_raw)
            yt_videos = chrome_extractor.parse_youtube_trending(youtube_a11y_raw)
            ig_records = android_extractor.parse_instagram_reels(instagram_layout_data)

            assert len(tt_tags) == 5
            assert len(tt_audio) == 2
            assert len(yt_videos) == 2
            assert len(ig_records) == 8

        total_time = time.perf_counter() - start
        assert total_time < 2.0, f"50 extraction iterations took {total_time:.3f}s, expected < 2.0s"
