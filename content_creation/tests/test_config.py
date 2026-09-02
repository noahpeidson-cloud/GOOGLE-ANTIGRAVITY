"""
test_config.py - Unit tests for centralized configuration and technical standards.
"""

import unittest
from config import (
    AUDIO_BITRATE_KBPS,
    AUDIO_CEILING_TRUE_PEAK,
    AUDIO_HIGHPASS_CUTOFF_HZ,
    AUDIO_LIMITER_ATTACK,
    AUDIO_LIMITER_LIMIT,
    AUDIO_LIMITER_RELEASE,
    AUDIO_LOOP_CROSSFADE_SEC,
    AUDIO_LUFS_TOLERANCE,
    AUDIO_SAMPLE_RATE,
    AUDIO_TARGET_LRA,
    AUDIO_TARGET_LUFS,
    AUDIO_TARGET_TRUE_PEAK,
    BrandType,
    EventTier,
    FOLDER_TIERS,
    GENRE_PROFILES,
    MAX_FOLDER_ITEMS,
    ProductionPreset,
    PROXY_AUDIO_CODEC,
    PROXY_AUDIO_SAMPLE_RATE,
    PROXY_PRESET,
    PROXY_VIDEO_BITRATE_KBPS,
    PROXY_VIDEO_CODEC,
    PROXY_VIDEO_HEIGHT,
    PROXY_VIDEO_SHORT_EDGE,
    ReframeMode,
    SAFE_ZONE_TIKTOK,
    SAFE_ZONE_YOUTUBE,
    SPAM_KEYWORDS,
    SUPPORTED_VIDEO_EXTENSIONS,
    ToneMapMode,
    VIDEO_CANVAS_HEIGHT,
    VIDEO_CANVAS_WIDTH,
    VIDEO_DURATION_MAX_SECONDS,
    VIDEO_TARGET_FPS,
    get_awaiting_review_folder,
    get_folder_tier,
    get_genre_profile,
    get_raw_folder,
    get_spam_blocklist_regex,
)


class TestConfigStandards(unittest.TestCase):
    """Verifies that all immutable constants match EDM Blueprint & GEMINI.md specs."""

    def test_canvas_dimensions(self):
        self.assertEqual(VIDEO_CANVAS_WIDTH, 1080)
        self.assertEqual(VIDEO_CANVAS_HEIGHT, 1920)
        self.assertEqual(VIDEO_TARGET_FPS, 60)
        self.assertEqual(VIDEO_DURATION_MAX_SECONDS, 59.0)
        self.assertIn(".m4v", SUPPORTED_VIDEO_EXTENSIONS)
        self.assertIn(".mp4", SUPPORTED_VIDEO_EXTENSIONS)

    def test_youtube_safe_zone_coordinates(self):
        sz = SAFE_ZONE_YOUTUBE.safe_zone
        self.assertEqual(sz.width, 900)
        self.assertEqual(sz.height, 1270)
        self.assertEqual(sz.top_exclusion_y, 180)
        self.assertEqual(sz.bottom_exclusion_y, 1450)
        self.assertEqual(sz.right_exclusion_x, 960)
        self.assertEqual(SAFE_ZONE_YOUTUBE.max_duration_seconds, 59.0)

    def test_tiktok_safe_zone_coordinates(self):
        sz = SAFE_ZONE_TIKTOK.safe_zone
        self.assertEqual(sz.width, 920)
        self.assertEqual(sz.height, 1310)
        self.assertEqual(sz.top_exclusion_y, 160)
        self.assertEqual(sz.bottom_exclusion_y, 1470)
        self.assertEqual(sz.right_exclusion_x, 960)
        self.assertEqual(sz.left_clearance_x, 40)

    def test_audio_standards(self):
        self.assertEqual(AUDIO_TARGET_LUFS, -14.0)
        self.assertEqual(AUDIO_LUFS_TOLERANCE, 1.0)
        self.assertEqual(AUDIO_TARGET_TRUE_PEAK, -1.5)
        self.assertEqual(AUDIO_CEILING_TRUE_PEAK, -1.0)
        self.assertEqual(AUDIO_TARGET_LRA, 7.0)
        self.assertEqual(AUDIO_HIGHPASS_CUTOFF_HZ, 40)
        self.assertEqual(AUDIO_SAMPLE_RATE, 48000)
        self.assertEqual(AUDIO_BITRATE_KBPS, 320)
        self.assertEqual(AUDIO_LOOP_CROSSFADE_SEC, 0.03)
        self.assertEqual(AUDIO_LIMITER_LIMIT, -1.5)
        self.assertEqual(AUDIO_LIMITER_ATTACK, 5.0)
        self.assertEqual(AUDIO_LIMITER_RELEASE, 50.0)

    def test_folder_tiers(self):
        self.assertEqual(FOLDER_TIERS["INBOX"], "01_RAW_INBOX")
        self.assertEqual(FOLDER_TIERS["RAW"], "01_RAW")
        self.assertEqual(FOLDER_TIERS["AWAITING_REVIEW"], "02_AWAITING_REVIEW")
        self.assertEqual(FOLDER_TIERS["IN_PROGRESS"], "02_IN_PROGRESS")
        self.assertEqual(FOLDER_TIERS["READY_TO_POST"], "03_READY_TO_POST")
        self.assertEqual(FOLDER_TIERS["ARCHIVE"], "04_ARCHIVE")
        self.assertEqual(MAX_FOLDER_ITEMS, 50)

    def test_proxy_standards(self):
        self.assertEqual(PROXY_VIDEO_HEIGHT, 720)
        self.assertEqual(PROXY_VIDEO_SHORT_EDGE, 720)
        self.assertEqual(PROXY_VIDEO_BITRATE_KBPS, 2500)
        self.assertEqual(PROXY_AUDIO_SAMPLE_RATE, 22050)
        self.assertEqual(PROXY_AUDIO_CODEC, "pcm_s16le")
        self.assertEqual(PROXY_PRESET, "fast")
        self.assertEqual(PROXY_VIDEO_CODEC, "libx264")

    def test_directory_resolution_helpers(self):
        from pathlib import Path
        dummy_ws = Path("/dummy/workspace")
        self.assertEqual(get_folder_tier("RAW"), "01_RAW")
        self.assertEqual(get_folder_tier("AWAITING_REVIEW"), "02_AWAITING_REVIEW")
        self.assertEqual(get_folder_tier("INBOX"), "01_RAW_INBOX")

        raw_path = get_raw_folder(dummy_ws, "UltraMiami", "MartinGarrix")
        self.assertEqual(raw_path, dummy_ws / "01_RAW" / "UltraMiami" / "MartinGarrix")

        review_path = get_awaiting_review_folder(dummy_ws, "Tomorrowland", "Alesso")
        self.assertEqual(review_path, dummy_ws / "02_AWAITING_REVIEW" / "Tomorrowland" / "Alesso")

    def test_genre_profiles(self):
        self.assertIn("dubstep", GENRE_PROFILES)
        self.assertIn("house", GENRE_PROFILES)
        self.assertIn("techno", GENRE_PROFILES)
        self.assertIn("trance", GENRE_PROFILES)
        self.assertIn("dnb", GENRE_PROFILES)

        dub = get_genre_profile("dubstep")
        self.assertEqual(dub.typical_bpm_range, (140, 150))
        self.assertTrue(any("Dubstep" in h for h in dub.recommended_hashtags))

        house = get_genre_profile("tech house")
        self.assertEqual(house.typical_bpm_range, (124, 130))

        unknown = get_genre_profile("unknown_genre")
        self.assertEqual(unknown.typical_bpm_range, (124, 130))  # Fallback to house

    def test_spam_blocklist_count_and_regex(self):
        self.assertEqual(len(SPAM_KEYWORDS), 17)
        regex = get_spam_blocklist_regex()
        for kw in SPAM_KEYWORDS:
            clean_kw = kw.replace("/", "").replace(".", "")
            sample_comment = f"Check this out: {kw} for discounts"
            self.assertTrue(
                bool(regex.search(sample_comment)),
                f"Regex failed to match keyword: {kw}",
            )


if __name__ == "__main__":
    unittest.main()
