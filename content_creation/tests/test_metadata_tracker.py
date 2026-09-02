"""
test_metadata_tracker.py - Unit tests for SEO generation, Safe-Zone geometry, spam filter, and SQLite DB.
"""

from pathlib import Path
import tempfile
import unittest

from config import AssetStatus, BrandType, EventTier
from metadata_tracker import (
    BoundingBox,
    CommentSpamFilter,
    MediaManifestDB,
    SEOCaptionGenerator,
    SafeZoneAuditor,
)


class TestMetadataTracker(unittest.TestCase):
    """Tests SEO packaging, safe zone collision math, comment moderation, and SQLite CRUD."""

    def test_seo_caption_and_hashtag_formula(self):
        seo = SEOCaptionGenerator.generate_seo_package(
            artist="John Summit",
            track="Where You Are",
            event="EDC Orlando",
            genre="house",
            year=2026,
            brand=BrandType.LASER_BAPTISM,
            tier=EventTier.PILLAR_A,
        )
        self.assertIn("John Summit", seo.yt_title)
        self.assertIn("Where You Are", seo.yt_title)
        self.assertIn("#Shorts", seo.yt_title)
        self.assertLessEqual(len(seo.yt_title), 100)

        # Hashtag Cluster verification (5 to 7 tags)
        self.assertGreaterEqual(len(seo.hashtags), 5)
        self.assertLessEqual(len(seo.hashtags), 7)
        self.assertIn("#EDM", seo.hashtags)
        self.assertIn("#Festival", seo.hashtags)
        self.assertIn("#JohnSummit", seo.hashtags)
        self.assertIn("#EDCOrlando2026", seo.hashtags)

        # Engagement Hooks verification
        self.assertIn("track_id_bounty", seo.first_hour_comments)
        self.assertIn("binary_rating", seo.first_hour_comments)
        self.assertIn("artist_tag", seo.first_hour_comments)

    def test_safe_zone_geometry_pass(self):
        # Positioned inside universal safe area (X: 60-960, Y: 180-1450)
        box = BoundingBox(x=100, y=350, width=500, height=80)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertTrue(report.is_compliant)
        self.assertTrue(report.yt_compliant)
        self.assertTrue(report.tiktok_compliant)
        self.assertEqual(len(report.yt_violations), 0)
        self.assertEqual(len(report.tiktok_violations), 0)

    def test_safe_zone_geometry_top_collision(self):
        # Y=100 is in YouTube (Y:0-180) and TikTok (Y:0-160) top exclusion
        box = BoundingBox(x=100, y=100, width=500, height=80)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.is_compliant)
        self.assertFalse(report.yt_compliant)
        self.assertFalse(report.tiktok_compliant)
        self.assertTrue(any("Top exclusion collision" in v for v in report.yt_violations))

    def test_safe_zone_geometry_bottom_collision(self):
        # Y=1600 is in YouTube (Y:1450-1920) and TikTok (Y:1470-1920) bottom exclusion
        box = BoundingBox(x=100, y=1600, width=500, height=80)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.is_compliant)
        self.assertTrue(any("Bottom exclusion collision" in v for v in report.yt_violations))
        self.assertTrue(any("Bottom exclusion collision" in v for v in report.tiktok_violations))

    def test_safe_zone_geometry_right_rail_collision(self):
        # X2 = 1000px is in right action rail (X: 960-1080)
        box = BoundingBox(x=700, y=500, width=300, height=80)  # x2 = 1000
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.is_compliant)
        self.assertTrue(any("Right" in v for v in report.yt_violations))
        self.assertTrue(any("Right" in v for v in report.tiktok_violations))

    def test_comment_spam_filter(self):
        spam_filter = CommentSpamFilter()

        # Spam comment
        spam_1 = "Get tickets cheap on t.me/edcorlando2026"
        is_spam, matches = spam_filter.check_comment(spam_1)
        self.assertTrue(is_spam)
        self.assertIn("t.me/", matches)

        # Another spam comment
        spam_2 = "DM to promote your music! WhatsApp +1234567"
        is_spam, matches = spam_filter.check_comment(spam_2)
        self.assertTrue(is_spam)
        self.assertTrue(any("whatsapp" in m or "dm to promote" in m for m in matches))

        # Legitimate rave comment
        legit_comment = "What an insane laser drop! Who was on the decks?"
        is_spam, matches = spam_filter.check_comment(legit_comment)
        self.assertFalse(is_spam)
        self.assertEqual(len(matches), 0)

    def test_sqlite_manifest_db_crud(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "test_manifest.sqlite"
            db = MediaManifestDB(db_path=db_file)

            # Insert / Upsert
            db.upsert_asset(
                asset_id="20260822_EDC_Summit_V1",
                source_file_name="raw_clip.mp4",
                canonical_name="20260822_EDC_Summit_WhereYouAre_V1_1080p.mp4",
                brand=BrandType.LASER_BAPTISM.value,
                tier=EventTier.PILLAR_A.value,
                event_name="EDC",
                artist_name="John Summit",
                track_name="Where You Are",
                genre="house",
                duration_seconds=35.0,
                is_hdr=True,
                measured_lufs=-14.1,
                measured_true_peak=-1.5,
                current_status=AssetStatus.IN_PROGRESS,
            )

            # Retrieve
            asset = db.get_asset("20260822_EDC_Summit_V1")
            self.assertIsNotNone(asset)
            self.assertEqual(asset["canonical_name"], "20260822_EDC_Summit_WhereYouAre_V1_1080p.mp4")
            self.assertEqual(asset["current_status"], "IN_PROGRESS")
            self.assertEqual(asset["is_hdr"], 1)
            self.assertAlmostEqual(asset["measured_lufs"], -14.1)

            # Update status
            updated = db.update_status("20260822_EDC_Summit_V1", AssetStatus.READY_TO_POST)
            self.assertTrue(updated)

            # Verify list
            ready_assets = db.list_assets(status=AssetStatus.READY_TO_POST)
            self.assertEqual(len(ready_assets), 1)
            self.assertEqual(ready_assets[0]["asset_id"], "20260822_EDC_Summit_V1")


if __name__ == "__main__":
    unittest.main()
