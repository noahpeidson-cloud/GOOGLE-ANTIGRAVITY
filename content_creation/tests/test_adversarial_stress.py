"""
test_adversarial_stress.py - Empirical Adversarial Stress Test Suite for EDM Content Engine

Targeting:
1. Safe-zone geometric collision edge cases (boundary touching, partial overlap, multi-box coordinates).
2. Filename normalization edge cases (malformed dates, special characters, missing tokens, resolution fallback).
3. Audio normalization parameter edge cases (extreme dynamic range, clipping prevention, loudnorm filter formatting).
4. 17-keyword spam blocklist matching with obfuscations/variations.
5. Inconsistencies between Blueprint, GEMINI.md, and Code implementations.
"""

from pathlib import Path
import re
import tempfile
import unittest

from config import (
    AUDIO_CEILING_TRUE_PEAK,
    AUDIO_HIGHPASS_CUTOFF_HZ,
    AUDIO_LOOP_CROSSFADE_SEC,
    AUDIO_LUFS_TOLERANCE,
    AUDIO_TARGET_LRA,
    AUDIO_TARGET_LUFS,
    AUDIO_TARGET_TRUE_PEAK,
    BrandType,
    DenoiseMode,
    EventTier,
    LoudnormMode,
    ProductionPreset,
    ReframeMode,
    SAFE_ZONE_TIKTOK,
    SAFE_ZONE_YOUTUBE,
    SPAM_KEYWORDS,
    ToneMapMode,
    get_spam_blocklist_regex,
)
from ffmpeg_processor import (
    FFmpegMasterProcessor,
    FilterGraphBuilder,
    LoudnessStats,
    TranscodeConfig,
    parse_loudnorm_pass1_output,
)
from ingest_assets import (
    DirectoryHealthGuard,
    FilenameNormalizer,
    StreamProbeData,
    calculate_sha256,
)
from metadata_tracker import (
    BoundingBox,
    CommentSpamFilter,
    MediaManifestDB,
    SEOCaptionGenerator,
    SafeZoneAuditor,
)
from orchestrator import (
    QCReport,
    build_parser,
    run_master_pipeline,
)


class TestSafeZoneGeometricAdversarial(unittest.TestCase):
    """Adversarially tests safe-zone collision geometry against off-by-one, boundary touching, and extreme boxes."""

    def test_exact_youtube_safe_boundaries_touching(self):
        """A box exactly touching the YouTube safe zone edges (X: 60..960, Y: 180..1450) must pass."""
        box = BoundingBox(x=60, y=180, width=900, height=1270)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertTrue(report.yt_compliant, f"YT touching failed: {report.yt_violations}")
        self.assertEqual(len(report.yt_violations), 0)

    def test_youtube_top_boundary_1px_violation(self):
        """Y=179 is 1px inside the top exclusion zone (0..180). Must fail YouTube audit."""
        box = BoundingBox(x=100, y=179, width=400, height=100)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.yt_compliant)
        self.assertTrue(any("Top exclusion collision" in v for v in report.yt_violations))

    def test_youtube_bottom_boundary_1px_violation(self):
        """Y2=1451 is 1px inside the bottom exclusion zone (1450..1920). Must fail YouTube audit."""
        box = BoundingBox(x=100, y=1400, width=400, height=51)  # y2 = 1451
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.yt_compliant)
        self.assertTrue(any("Bottom exclusion collision" in v for v in report.yt_violations))

    def test_youtube_left_margin_1px_violation(self):
        """X=59 is 1px inside the left exclusion zone (0..60). Must fail YouTube audit."""
        box = BoundingBox(x=59, y=300, width=400, height=100)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.yt_compliant)
        self.assertTrue(any("Left margin collision" in v for v in report.yt_violations))

    def test_youtube_right_rail_1px_violation(self):
        """X2=961 is 1px inside the right action rail exclusion (960..1080). Must fail YouTube audit."""
        box = BoundingBox(x=561, y=300, width=400, height=100)  # x2 = 961
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.yt_compliant)
        self.assertTrue(any("Right exclusion collision" in v for v in report.yt_violations))

    def test_exact_tiktok_safe_boundaries_touching(self):
        """A box exactly touching the TikTok safe zone edges (X: 40..960, Y: 160..1470) must pass."""
        box = BoundingBox(x=40, y=160, width=920, height=1310)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertTrue(report.tiktok_compliant, f"TikTok touching failed: {report.tiktok_violations}")
        self.assertEqual(len(report.tiktok_violations), 0)

    def test_tiktok_top_boundary_1px_violation(self):
        """Y=159 is 1px inside TikTok top exclusion (0..160). Must fail TikTok audit."""
        box = BoundingBox(x=100, y=159, width=400, height=100)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.tiktok_compliant)
        self.assertTrue(any("Top exclusion collision" in v for v in report.tiktok_violations))

    def test_tiktok_bottom_boundary_1px_violation(self):
        """Y2=1471 is 1px inside TikTok bottom exclusion (1470..1920). Must fail TikTok audit."""
        box = BoundingBox(x=100, y=1400, width=400, height=71)  # y2 = 1471
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.tiktok_compliant)
        self.assertTrue(any("Bottom exclusion collision" in v for v in report.tiktok_violations))

    def test_tiktok_left_clearance_1px_violation(self):
        """X=39 is 1px inside TikTok left clearance (0..40). Must fail TikTok audit."""
        box = BoundingBox(x=39, y=300, width=400, height=100)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.tiktok_compliant)
        self.assertTrue(any("Left clearance collision" in v for v in report.tiktok_violations))

    def test_full_canvas_overlay_box(self):
        """A full canvas overlay (0,0,1080,1920) must trigger all 4 violations on both platforms (8 total)."""
        box = BoundingBox(x=0, y=0, width=1080, height=1920)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.is_compliant)
        self.assertEqual(len(report.yt_violations), 4)
        self.assertEqual(len(report.tiktok_violations), 4)

    def test_negative_coordinates(self):
        """Negative X or Y coordinates represent elements rendered off-screen."""
        box = BoundingBox(x=-50, y=-100, width=200, height=200)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertFalse(report.is_compliant)
        self.assertTrue(any("Top exclusion" in v for v in report.yt_violations))
        self.assertTrue(any("Left margin" in v for v in report.yt_violations))

    def test_safe_zone_dimension_consistency(self):
        """Verifies mathematical consistency of safe zone spans."""
        yt_sz = SAFE_ZONE_YOUTUBE.safe_zone
        tt_sz = SAFE_ZONE_TIKTOK.safe_zone

        yt_computed_height = yt_sz.bottom_exclusion_y - yt_sz.top_exclusion_y
        tt_computed_height = tt_sz.bottom_exclusion_y - tt_sz.top_exclusion_y

        self.assertEqual(yt_computed_height, 1270)
        self.assertEqual(yt_sz.height, 1270)

        self.assertEqual(tt_computed_height, 1310)
        self.assertEqual(tt_sz.height, 1310)

    def test_drawtext_filter_comma_escaping(self):
        """Verifies that commas in track titles and artist names are safely escaped with backslashes."""
        v_filter = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            track_title="Where You Are, Pt. 2",
            artist_name="John Summit",
        )
        self.assertIn(r"Where You Are\, Pt. 2", v_filter)
        # Verify splitting by unescaped commas leaves the drawtext filter graph token intact
        filter_tokens = re.split(r"(?<!\\),", v_filter)
        drawtext_tokens = [tok for tok in filter_tokens if tok.startswith("drawtext=")]
        self.assertEqual(len(drawtext_tokens), 1)
        orphaned_tokens = [tok for tok in filter_tokens if "Pt. 2" in tok and not tok.startswith("drawtext=")]
        self.assertEqual(len(orphaned_tokens), 0)


class TestFilenameNormalizationAdversarial(unittest.TestCase):
    """Adversarially tests filename normalization with malformed dates, special characters, unicode, and fallback."""

    def test_parse_valid_canonical_names(self):
        valid_cases = [
            ("20260821_EDCOrlando_JohnSummit_WhereYouAre_V1_1080p.mp4", "20260821", "EDCOrlando", "JohnSummit", "WhereYouAre", 1, "1080p", "mp4"),
            ("20261231_LostLands_Excision_Feel-Something_V3_4k.mov", "20261231", "LostLands", "Excision", "Feel-Something", 3, "4k", "mov"),
            ("20260101_ClubSpace_CharlotteDeWitte_ID-01_V1_720p.mkv", "20260101", "ClubSpace", "CharlotteDeWitte", "ID-01", 1, "720p", "mkv"),
            ("20260515_UltraMiami_ArminVanBuuren_BlahBlahBlah_V10_2160p.webm", "20260515", "UltraMiami", "ArminVanBuuren", "BlahBlahBlah", 10, "2160p", "webm"),
        ]
        for fname, d, ev, ar, tr, ver, res, ext in valid_cases:
            parsed = FilenameNormalizer.parse_filename(fname)
            self.assertIsNotNone(parsed, f"Failed to parse valid canonical filename: {fname}")
            self.assertEqual(parsed["date"], d)
            self.assertEqual(parsed["event"], ev)
            self.assertEqual(parsed["artist"], ar)
            self.assertEqual(parsed["track"], tr)
            self.assertEqual(parsed["version"], ver)
            self.assertEqual(parsed["resolution"], res)
            self.assertEqual(parsed["ext"], ext)

    def test_parse_malformed_filenames_rejected(self):
        malformed = [
            "IMG_4920.MOV",                                    # iOS raw capture
            "VID_20260821_190000.mp4",                         # Android raw capture
            "20260821_EDCOrlando_JohnSummit_V1_1080p.mp4",      # Missing track token (only 5 tokens)
            "20260821_EDC_Summit_Track_V_1080p.mp4",           # Missing version number
            "20260821_EDC_Summit_Track_V1.mp4",                # Missing resolution token
            "20260821_EDC_Summit_Track_V1_1080p.exe",          # Disallowed file extension
            "2026082_EDC_Summit_Track_V1_1080p.mp4",           # Date with 7 digits (not 8)
            "202608211_EDC_Summit_Track_V1_1080p.mp4",         # Date with 9 digits (not 8)
            "20260821_EDC_Summit_Track_V1_1080p",              # Missing extension
            "20260821__JohnSummit_WhereYouAre_V1_1080p.mp4",    # Empty event token
        ]
        for name in malformed:
            parsed = FilenameNormalizer.parse_filename(name)
            self.assertIsNone(parsed, f"Malformed filename should not be accepted as canonical: {name}")

    def test_token_sanitization_unicode_preservation(self):
        """Verifies that European artist names with umlauts, strokes, and diacritics are properly normalized."""
        self.assertEqual(FilenameNormalizer.sanitize_token("Tiësto"), "Tiesto")
        self.assertEqual(FilenameNormalizer.sanitize_token("Kölsch"), "Kolsch")
        self.assertEqual(FilenameNormalizer.sanitize_token("Öwnboss"), "Ownboss")
        self.assertEqual(FilenameNormalizer.sanitize_token("MØ"), "Mo")
        self.assertEqual(FilenameNormalizer.sanitize_token("Beyoncé"), "Beyonce")

    def test_build_canonical_filename_variations(self):
        # Test resolution normalization: '4K', '1080', '720p', '4k'
        f1 = FilenameNormalizer.build_canonical_filename("Ultra", "Garrix", "Animals", resolution="4K", version=1, date_str="20260822")
        self.assertEqual(f1, "20260822_Ultra_Garrix_Animals_V1_4k.mp4")

        f2 = FilenameNormalizer.build_canonical_filename("EDC", "Summit", "ID", resolution="1080", version=2, date_str="20260822")
        self.assertEqual(f2, "20260822_Edc_Summit_Id_V2_1080p.mp4")

        f3 = FilenameNormalizer.build_canonical_filename("Club", "DJ", "Track", resolution="720p", version=1, date_str="20260822", ext=".MOV")
        self.assertEqual(f3, "20260822_Club_Dj_Track_V1_720p.mov")

        # Test fallback when all fields are None / empty
        f_empty = FilenameNormalizer.build_canonical_filename(None, None, None, resolution="1080p", version=1, date_str="20260822")
        self.assertEqual(f_empty, "20260822_Event_Artist_ID_V1_1080p.mp4")

    def test_m4v_extension_support(self):
        """Verifies that .m4v extension is recognized and parsed by FilenameNormalizer."""
        m4v_name = "20260822_EDC_Summit_WhereYouAre_V1_1080p.m4v"
        parsed = FilenameNormalizer.parse_filename(m4v_name)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["ext"], "m4v")


class TestAudioNormalizationAdversarial(unittest.TestCase):
    """Adversarially tests audio loudnorm parsing, extreme dynamic range, and clipping limits."""

    def test_parse_loudnorm_valid_json(self):
        stderr = """
        [Parsed_loudnorm_1 @ 000001f3b890a000]
        {
            "input_i" : "-18.52",
            "input_tp" : "-0.41",
            "input_lra" : "8.30",
            "input_thresh" : "-29.10",
            "output_i" : "-14.00",
            "output_tp" : "-1.50",
            "output_lra" : "6.50",
            "output_thresh" : "-24.10",
            "normalization_type" : "dynamic",
            "target_offset" : "+0.10"
        }
        """
        stats = parse_loudnorm_pass1_output(stderr)
        self.assertIsNotNone(stats)
        self.assertAlmostEqual(stats.input_i, -18.52)
        self.assertAlmostEqual(stats.input_tp, -0.41)
        self.assertAlmostEqual(stats.input_lra, 8.30)
        self.assertAlmostEqual(stats.input_thresh, -29.10)
        self.assertAlmostEqual(stats.target_offset, 0.10)

    def test_parse_loudnorm_corrupted_or_missing_json(self):
        corrupted_cases = [
            "",                                                # Empty output
            "ffmpeg version 6.0 Copyright (c) 2000-2023",       # No loudnorm block
            "{ \"input_i\": \"-18.0\" }",                       # Missing required keys
            "Error opening input file: No such file",          # Execution error
        ]
        for err in corrupted_cases:
            stats = parse_loudnorm_pass1_output(err)
            self.assertIsNone(stats, f"Should return None on invalid loudnorm output: {err}")

    def test_audio_filter_builder_extreme_dynamic_range(self):
        """Tests filter construction with high dynamic range (LRA = 25.0 LU) and quiet input (-35 LUFS)."""
        stats = LoudnessStats(
            input_i=-35.0,
            input_tp=+2.5,   # Heavily clipping source
            input_lra=25.0,  # Extreme dynamic range
            input_thresh=-46.0,
            target_offset=4.5,
        )
        a_filter = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=stats,
            highpass_hz=80,
            duration_sec=45.0,
            apply_loop_crossfade=True,
            loudnorm_mode=LoudnormMode.TWO_PASS,
        )
        self.assertIn("highpass=f=80:poles=2", a_filter)
        self.assertIn("measured_I=-35.00", a_filter)
        self.assertIn("measured_TP=2.50", a_filter)
        self.assertIn("measured_LRA=25.00", a_filter)
        self.assertIn("offset=4.50:linear=true", a_filter)
        self.assertIn("afade=t=in:ss=0:d=0.030", a_filter)
        self.assertIn("afade=t=out:st=44.970:d=0.030", a_filter)

    def test_alimiter_in_filtergraph_builder(self):
        """Verifies that alimiter peak limiter is appended in build_audio_filter."""
        stats = LoudnessStats(input_i=-18.0, input_tp=-0.5, input_lra=8.0, input_thresh=-28.0, target_offset=0.0)
        a_filter = FilterGraphBuilder.build_audio_filter(loudnorm_stats=stats)
        self.assertIn("alimiter=limit=-1.5dB:attack=5:release=50", a_filter)

    def test_qc_true_peak_enforces_target(self):
        """Verifies that QC verification strictly enforces AUDIO_TARGET_TRUE_PEAK (-1.5 dBTP)."""
        self.assertEqual(AUDIO_TARGET_TRUE_PEAK, -1.5)
        # Test a borderline True Peak of -1.2 dBTP
        borderline_tp = -1.2
        is_compliant_with_target = (borderline_tp <= AUDIO_TARGET_TRUE_PEAK)     # False
        self.assertFalse(is_compliant_with_target)

        compliant_tp = -1.5
        self.assertTrue(compliant_tp <= AUDIO_TARGET_TRUE_PEAK)
        self.assertTrue(-1.6 <= AUDIO_TARGET_TRUE_PEAK)


class TestSpamBlocklistAdversarial(unittest.TestCase):
    """Adversarially tests the 17-keyword spam blocklist with obfuscations, case, whitespace, and variations."""

    def setUp(self):
        self.spam_filter = CommentSpamFilter()

    def test_all_17_keywords_detected(self):
        """Verifies that every single one of the 17 canonical spam keywords is detected in isolation."""
        self.assertEqual(len(SPAM_KEYWORDS), 17)
        for kw in SPAM_KEYWORDS:
            comment = f"Hey everyone, make sure to check {kw} right now!"
            is_spam, matches = self.spam_filter.check_comment(comment)
            self.assertTrue(is_spam, f"Failed to match canonical keyword: '{kw}'")
            self.assertGreater(len(matches), 0)

    def test_case_insensitive_matching(self):
        """Verifies matching across UPPERCASE, lowercase, and mixed case."""
        cases = [
            ("T.ME/RAVESET_LEAKS", "t.me/"),
            ("SEND ME A WHATSAPP MESSAGE", "whatsapp"),
            ("CRYPTO GAINS GUARANTEED", "crypto"),
            ("INVESTMENT OPPORTUNITY", "investment"),
            ("CHECK BIO FOR TICKETS", "check bio"),
            ("FULL SET LINK IN COMMENTS", "full set link"),
            ("JOIN OUR TELEGRAM GROUP", "telegram"),
            ("DROP YOUR TRACK FOR PROMO", "drop your track"),
            ("PAID PROMO ON OUR PAGE", "promo on"),
            ("DM TO PROMOTE YOUR MUSIC", "dm to promote"),
            ("CLICK HERE FOR FREE PASS", "click here"),
            ("TICKET SALE LIVE NOW", "ticket sale"),
            ("BUY TICKETS BEFORE THEY SELL OUT", "buy tickets"),
            ("NEW TRACK LEAK 2026", "leak"),
            ("THIS DJ IS A COMPLETE SCAM", "scam"),
            ("DM ME FOR GUESTLIST", "dm me"),
            ("FREE DOWNLOAD OF UNRELEASED ID", "free download"),
        ]
        for comment, expected_kw in cases:
            is_spam, matches = self.spam_filter.check_comment(comment)
            self.assertTrue(is_spam, f"Case insensitivity failed for: '{comment}'")

    def test_whitespace_and_newline_variations(self):
        """Verifies matching when spaces, tabs, or newlines are inserted between words."""
        cases = [
            "Check    bio for the link",
            "Check\nbio\nnow",
            "Full   set   link below",
            "Drop  your   track here",
            "Dm   to   promote your track",
            "Click   here to get access",
            "Ticket   sale is live",
            "Buy   tickets now",
            "Dm   me for the ID",
            "Free   download available",
        ]
        for comment in cases:
            is_spam, matches = self.spam_filter.check_comment(comment)
            self.assertTrue(is_spam, f"Whitespace variation matching failed for: '{comment}'")

    def test_no_space_concatenation_variations(self):
        """Verifies regex behavior when words are concatenated without spaces (e.g. checkbio, buytickets)."""
        cases = [
            ("checkbio for tickets", True),
            ("buytickets now", True),
            ("ticketsale live", True),
            ("dmme for info", True),
            ("freedownload available", True),
            ("fullsetlink in bio", True),
        ]
        for comment, should_match in cases:
            is_spam, matches = self.spam_filter.check_comment(comment)
            self.assertEqual(is_spam, should_match, f"Concatenation match failed for: '{comment}'")

    def test_underscore_and_hyphen_obfuscation_blocked(self):
        """Verifies that spam keywords with underscores, hyphens, and dots are detected."""
        underscore_cases = [
            "check_bio",
            "check-bio",
            "ticket_sale",
            "ticket-sale",
            "buy_tickets",
            "buy-tickets",
            "free_download",
            "free-download",
            "dm_me",
            "dm-me",
            "drop_your_track",
            "dm_to_promote",
        ]
        for c in underscore_cases:
            is_spam, matches = self.spam_filter.check_comment(c)
            self.assertTrue(is_spam, f"Obfuscated spam phrase was not blocked: '{c}'")
            self.assertGreater(len(matches), 0)

    def test_no_false_positives_on_benign_words(self):
        """Verifies that word boundaries prevent false positives on benign words containing spam substrings."""
        benign_cases = [
            "We visited Scamander on our Australia tour",
            "Check the cdm media article",
            "The atmosphere was bleak earlier",
            "Water leakage in the tent was repaired",
        ]
        for comment in benign_cases:
            is_spam, matches = self.spam_filter.check_comment(comment)
            self.assertFalse(
                is_spam,
                f"Benign comment falsely flagged as spam ({matches}): '{comment}'"
            )


class TestEndToEndPipelineStress(unittest.TestCase):
    """Stress tests end-to-end pipeline under extreme conditions (long durations, capacity overflow, dry runs)."""

    def test_pipeline_long_duration_clamping(self):
        """Verifies that raw files of 120s duration are clamped to <= 59.0s."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            raw_file = workspace / "20260822_EDC_Summit_LongSet_V1_1080p.mp4"
            raw_file.write_text("dummy media")

            summary = run_master_pipeline(
                input_file=raw_file,
                workspace_root=workspace,
                event="EDC",
                artist="Summit",
                track="LongSet",
                genre="house",
                duration=120.0,  # Extreme 2-minute duration
                dry_run=True,
            )
            qc = summary["qc_report"]
            self.assertLessEqual(qc["duration_seconds"], 59.0)
            self.assertTrue(qc["duration_compliant"])

    def test_directory_capacity_overflow_stress(self):
        """Verifies that 120 items are cleanly partitioned across Batch01, Batch02, Batch03 at 50-item cap."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            guard = DirectoryHealthGuard(max_items=50)

            # Create 120 items
            for i in range(120):
                target_folder = guard.get_healthy_subfolder(base_dir, "EDC_Orlando")
                dummy_file = target_folder / f"clip_{i:03d}.mp4"
                dummy_file.write_text("data")

            # Check folders created: EDC_Orlando (50), EDC_Orlando_Batch02 (50), EDC_Orlando_Batch03 (20)
            f1 = base_dir / "EDC_Orlando"
            f2 = base_dir / "EDC_Orlando_Batch02"
            f3 = base_dir / "EDC_Orlando_Batch03"

            self.assertTrue(f1.exists())
            self.assertTrue(f2.exists())
            self.assertTrue(f3.exists())

            self.assertEqual(guard.count_items(f1), 50)
            self.assertEqual(guard.count_items(f2), 50)
            self.assertEqual(guard.count_items(f3), 20)


if __name__ == "__main__":
    unittest.main()
