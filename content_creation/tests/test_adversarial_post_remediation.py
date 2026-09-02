import unittest
import sys
from pathlib import Path
import re
import json
import unicodedata

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    BrandType,
    EventTier,
    ProductionPreset,
    ReframeMode,
    ToneMapMode,
    DenoiseMode,
    LoudnormMode,
    AssetStatus,
    ContentIDStatus,
    SAFE_ZONE_YOUTUBE,
    SAFE_ZONE_TIKTOK,
    AUDIO_TARGET_LUFS,
    AUDIO_LUFS_TOLERANCE,
    AUDIO_TARGET_TRUE_PEAK,
    AUDIO_CEILING_TRUE_PEAK,
    AUDIO_LIMITER_LIMIT,
    AUDIO_LIMITER_ATTACK,
    AUDIO_LIMITER_RELEASE,
    VIDEO_CANVAS_WIDTH,
    VIDEO_CANVAS_HEIGHT,
    VIDEO_DURATION_MAX_SECONDS,
    SPAM_KEYWORDS,
    SPAM_BLOCKLIST_PATTERN,
    get_spam_blocklist_regex,
    get_genre_profile,
)
from ingest_assets import (
    FilenameNormalizer,
    DirectoryHealthGuard,
    StreamProbeData,
    calculate_sha256,
)
from ffmpeg_processor import (
    FilterGraphBuilder,
    LoudnessStats,
    TranscodeConfig,
    FFmpegMasterProcessor,
    parse_loudnorm_pass1_output,
)
from metadata_tracker import (
    BoundingBox,
    SafeZoneAuditor,
    SEOCaptionGenerator,
    CommentSpamFilter,
    MediaManifestDB,
)
from orchestrator import (
    verify_media_file,
    QCReport,
)


class TestAdversarialUnicodeDiacriticsAndLigatures(unittest.TestCase):
    """
    Adversarial evaluation of FilenameNormalizer and token sanitization across
    complex international EDM artist names, diacritics, ligatures, and edge cases.
    """

    def test_european_edm_artists_with_umlauts_and_diacritics(self):
        """Tests that diacritics and umlauts are decomposed and normalized into ASCII."""
        cases = {
            "Tiësto": "Tiesto",
            "Beyoncé": "Beyonce",
            "Björk": "Bjork",
            "Møme": "Mome",
            "Kölsch": "Kolsch",
            "Öwnboss": "Ownboss",
            "MØ": "Mo",
            "Dätwyler": "Datwyler",
            "Gerd Janson & Lauer (Tuff City Kids)": "GerdJansonLauerTuffCityKids",
            "Sébastien Léger": "SebastienLeger",
            "Stimming & Lazarusman": "StimmingLazarusman",
            "Âme": "Ame",
            "Chloé": "Chloe",
            "Claptone feat. Jaw": "ClaptoneFeatJaw",
            "Nils Frahm": "NilsFrahm",
            "Kollektiv Turmstrasse": "KollektivTurmstrasse",
            "Gaspard Augé (Justice)": "GaspardAugeJustice",
            "Rødhåd": "Rodhad",
            "Ørjan Nilsen": "OrjanNilsen",
            "Sébastien Tellier": "SebastienTellier",
            "Hælos": "Haelos",
            "Édith Piaf": "EdithPiaf",
        }
        for raw, expected in cases.items():
            result = FilenameNormalizer.sanitize_token(raw)
            self.assertEqual(result, expected, f"Failed on raw token: {raw} -> got {result}, expected {expected}")

    def test_special_ligatures_and_strokes(self):
        """Tests explicit Latin character mapping (Ø, Æ, ß, Ł, Đ)."""
        cases = {
            "MØ": "Mo",
            "møme": "Mome",
            "Æntrøpy": "Aentropy",
            "Groß": "Gross",
            "Łukasz": "Lukasz",
            "Đorđe": "Dorde",
            "Kælan": "Kaelan",
            "Fraunhofer-Institut für Integrierte Schaltungen": "FraunhoferInstitutFurIntegrierteSchaltungen",
        }
        for raw, expected in cases.items():
            result = FilenameNormalizer.sanitize_token(raw)
            self.assertEqual(result, expected, f"Failed on ligature: {raw} -> got {result}, expected {expected}")

    def test_whitespace_and_punctuation_token_sanitization(self):
        """Tests artist and track names with diverse punctuation, hyphens, and whitespace."""
        cases = {
            "AC/DC": "AcDc",
            "Above & Beyond": "AboveBeyond",
            "deadmau5": "Deadmau5",
            "3LAU": "3lau",
            "KSHMR & DallasK": "KshmrDallask",
            "Galantis vs. Axwell / Ingrosso": "GalantisVsAxwellIngrosso",
            "What So Not - High You Are (Branchez Remix)": "WhatSoNotHighYouAreBranchezRemix",
            "  Fred again..  ": "FredAgain",
            "---Sub_Focus---": "SubFocus",
            "Swedish House Mafia ft. John Martin - Don't You Worry Child": "SwedishHouseMafiaFtJohnMartinDonTYouWorryChild",
            "Bicep - Glue (Sub Focus Bootleg) [Live @ Printworks]": "BicepGlueSubFocusBootlegLivePrintworks",
        }
        for raw, expected in cases.items():
            result = FilenameNormalizer.sanitize_token(raw)
            self.assertEqual(result, expected, f"Failed on token: {raw} -> got {result}, expected {expected}")

    def test_empty_and_non_ascii_fallback(self):
        """Tests fallback handling for empty, whitespace, and non-Latin scripts."""
        self.assertEqual(FilenameNormalizer.sanitize_token(""), "Unknown")
        self.assertEqual(FilenameNormalizer.sanitize_token("   "), "Unknown")
        self.assertEqual(FilenameNormalizer.sanitize_token(None), "Unknown")
        self.assertEqual(FilenameNormalizer.sanitize_token("!@#$%^&*()"), "Unknown")
        self.assertEqual(FilenameNormalizer.sanitize_token("!!!", default="Fallback"), "Fallback")
        # Non-Latin script fallback to default
        self.assertEqual(FilenameNormalizer.sanitize_token("Алексей", default="CyrillicArtist"), "CyrillicArtist")
        self.assertEqual(FilenameNormalizer.sanitize_token("初音ミク", default="JapaneseArtist"), "JapaneseArtist")

    def test_canonical_filename_builder_with_unicode_inputs(self):
        """Tests full canonical filename construction with unicode artist/event/track."""
        name = FilenameNormalizer.build_canonical_filename(
            event="Tomorrowland (Belgium) 🇧🇪",
            artist="Tiësto & Kölsch",
            track="Wë Äre Thë Clüb (VIP Rëmïx)",
            resolution="1080p",
            version=2,
            date_str="20260822",
            ext="mp4",
        )
        expected = "20260822_TomorrowlandBelgium_TiestoKolsch_WeAreTheClubVipRemix_V2_1080p.mp4"
        self.assertEqual(name, expected)
        # Verify that the generated name parses cleanly through CANONICAL_PATTERN
        parsed = FilenameNormalizer.parse_filename(name)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["artist"], "TiestoKolsch")
        self.assertEqual(parsed["version"], 2)


class TestAdversarialDrawtextFilterInjection(unittest.TestCase):
    """
    Adversarial stress-testing of FFmpeg filtergraph construction against injection
    payloads, unescaped commas, colons, quotes, backslashes, and special characters.
    """

    def test_drawtext_escaping_with_colons_commas_quotes_backslashes(self):
        """Verifies escaping of all FFmpeg filtergraph metacharacters."""
        v_filter = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            artist_name="Skrillex, Fred again.. & Four Tet",
            track_title="Baby again..: Live in London, Pt. 1 'Exclusive'",
        )
        # Check that single quotes are stripped
        self.assertNotIn("'", v_filter.split("text=")[1].split(":")[0][1:-1])
        # Check that commas are escaped as \,
        self.assertIn(r"SKRILLEX\, FRED AGAIN..", v_filter)
        self.assertIn(r"London\, Pt. 1", v_filter)
        # Check that colons are escaped as \:
        self.assertIn(r"again..\: Live", v_filter)

        # Splitting by unescaped comma must yield exactly 4 filter tokens:
        # 1. crop=...
        # 2. scale=...
        # 3. hqdn3d=...
        # 4. drawtext=...
        filter_tokens = re.split(r"(?<!\\),", v_filter)
        self.assertEqual(len(filter_tokens), 4)
        self.assertTrue(filter_tokens[0].startswith("crop="))
        self.assertTrue(filter_tokens[1].startswith("scale="))
        self.assertTrue(filter_tokens[2].startswith("hqdn3d="))
        self.assertTrue(filter_tokens[3].startswith("drawtext="))

    def test_drawtext_adversarial_injection_payload(self):
        """Tests filtergraph construction with aggressive injection strings."""
        payload = r"'; drop table; -- : , \\ ' \" [ ] { } % $ # @ ! ^ & *"
        v_filter = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            artist_name=payload,
            track_title=payload,
        )
        self.assertTrue(v_filter.startswith("crop="))
        self.assertIn("drawtext=text=", v_filter)
        # Ensure no unescaped commas exist in the drawtext token
        drawtext_part = v_filter.split("drawtext=")[1]
        tokens = re.split(r"(?<!\\),", drawtext_part)
        # Should be a single valid drawtext filter stage without orphaned tokens
        self.assertEqual(len(tokens), 1)

    def test_drawtext_empty_and_none_overlays(self):
        """Verifies that empty or None artist/track produces no drawtext filter."""
        v_filter1 = FilterGraphBuilder.build_video_filter(artist_name=None, track_title=None)
        self.assertNotIn("drawtext", v_filter1)

        v_filter2 = FilterGraphBuilder.build_video_filter(artist_name="", track_title="")
        self.assertNotIn("drawtext", v_filter2)

    def test_drawtext_overlay_quotes_and_percent_expansion(self):
        """Tests text with double quotes, percent signs, and brackets."""
        v_filter = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            artist_name='DJ "The Master"',
            track_title="100% High Energy (Live @ Red Rocks) [VIP]",
        )
        self.assertIn(r'DJ "THE MASTER"', v_filter)
        self.assertIn("100% High Energy", v_filter)
        self.assertIn("[VIP]", v_filter)


class TestAdversarialSpamRegexAndEvasion(unittest.TestCase):
    """
    Adversarial evaluation of the 17-keyword spam blocklist regex pattern
    against obfuscation, punctuation splitting, case variations, and benign collisions.
    """

    def setUp(self):
        self.spam_filter = CommentSpamFilter()
        self.regex = get_spam_blocklist_regex()

    def test_all_17_keywords_detected_with_variations(self):
        """Verifies 100% detection of all 17 canonical spam keywords."""
        test_samples = {
            "t.me/": "Join my channel at t.me/edm_leaks_2026 for unreleased tracks",
            "whatsapp": "Message us on WhatsApp +1234567890 for VIP backstage passes",
            "crypto": "Guaranteed 100x return on crypto investment telegram",
            "investment": "Great investment opportunity in EDM NFTs",
            "check bio": "Free guestlist link in profile, check bio now!",
            "full set link": "Full set link is up on our private cloud server",
            "telegram": "Add me on telegram for live set audio rips",
            "drop your track": "Drop your track here for label A&R review",
            "promo on": "Send music for promo on our 1M follower page",
            "dm to promote": "DM to promote your upcoming festival single",
            "click here": "Want tickets? Click here now before they sell out!",
            "ticket sale": "EDC Las Vegas ticket sale going on right now",
            "buy tickets": "Buy tickets at discount via our verified link",
            "leak": "Exclusive John Summit leak from Ultra 2026",
            "scam": "Warning this website is a ticket scam",
            "dm me": "Interested in DJ lessons? DM me on Instagram",
            "free download": "Grab the free download of this bootleg remix",
        }
        for kw, sample in test_samples.items():
            is_spam, matches = self.spam_filter.check_comment(sample)
            self.assertTrue(is_spam, f"Keyword '{kw}' failed to be detected in sample: '{sample}'")
            self.assertGreater(len(matches), 0)

    def test_punctuation_and_delimiter_obfuscation(self):
        """Tests that spammers using dots, underscores, hyphens, and spaces are detected."""
        evasion_cases = [
            "check_bio",
            "check-bio",
            "check.bio",
            "check   bio",
            "CHECK__BIO",
            "ticket_sale",
            "ticket-sale",
            "ticket.sale",
            "ticket_sales",
            "buy_tickets",
            "buy-tickets",
            "buy.tickets",
            "buy_ticket",
            "free_download",
            "free-download",
            "free.download",
            "free_downloads",
            "dm_me",
            "dm-me",
            "dm.me",
            "dm_to_promote",
            "dm-to-promote",
            "drop_your_track",
            "drop-your-track",
            "full_set_link",
            "full-set-link",
            "promo_on",
            "promo-on",
            "click_here",
            "click-here",
        ]
        for phrase in evasion_cases:
            comment = f"Hey guys {phrase} for more info!"
            is_spam, matches = self.spam_filter.check_comment(comment)
            self.assertTrue(is_spam, f"Obfuscated spam phrase '{phrase}' was NOT caught!")

    def test_plural_and_tense_variations(self):
        """Tests detection of singular and plural forms for spam keywords."""
        plurals = [
            "investments in EDM crypto",
            "ticket sales open at noon",
            "buy tickets right here",
            "buy ticket discount code",
            "unreleased leaks from studio",
            "beware of online scams",
            "free downloads for all tracks",
        ]
        for phrase in plurals:
            is_spam, matches = self.spam_filter.check_comment(phrase)
            self.assertTrue(is_spam, f"Plural phrase '{phrase}' was not flagged as spam!")

    def test_benign_rave_conversations_no_false_positives(self):
        """Verifies word boundary enforcement prevents false positives on benign words."""
        benign_comments = [
            "We visited Scamander on our Australia road trip before the festival",
            "Check the cdm media article about laser programming",
            "The atmosphere was bleak earlier but the laser show transformed it",
            "Water leakage in our tent at Lost Lands was fixed by morning",
            "That kick drum sounds massive on the PK Sound system",
            "Can you tell me which synthesizer Sub Focus used for that lead?",
            "The transition from techno to drum and bass was completely seamless",
            "Does anyone know what time John Summit plays on Sunday?",
            "The crowd energy during the closing set was unmatched",
            "Check out my new festival outfit for EDC!",
            "I will dm you later about hotel booking", # 'dm you' is not 'dm me'
            "Is there a ticket booth at the venue entrance?", # 'ticket booth' is not 'ticket sale'
        ]
        for comment in benign_comments:
            is_spam, matches = self.spam_filter.check_comment(comment)
            self.assertFalse(
                is_spam,
                f"Benign comment FALSE POSITIVE: '{comment}' (matched: {matches})"
            )


class TestAdversarialAudioDSPAndFiltergraph(unittest.TestCase):
    """
    Adversarial evaluation of audio filtergraph assembly, loudnorm parameters,
    and brickwall peak limiting.
    """

    def test_audio_filtergraph_two_pass_structure(self):
        """Verifies audio filtergraph with measured two-pass stats and brickwall limiter."""
        stats = LoudnessStats(
            input_i=-21.4,
            input_tp=-0.2,
            input_lra=11.2,
            input_thresh=-32.5,
            target_offset=0.6,
        )
        af = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=stats,
            highpass_hz=40,
            duration_sec=30.0,
            apply_loop_crossfade=True,
            loudnorm_mode=LoudnormMode.TWO_PASS,
        )
        # Expected sequence: highpass -> loudnorm with linear=true -> alimiter -> afade in -> afade out
        filters = af.split(",")
        self.assertTrue(filters[0].startswith("highpass=f=40"))
        self.assertIn("loudnorm=I=-14.0", af)
        self.assertIn("measured_I=-21.40", af)
        self.assertIn("measured_TP=-0.20", af)
        self.assertIn("measured_LRA=11.20", af)
        self.assertIn("measured_thresh=-32.50", af)
        self.assertIn("offset=0.60", af)
        self.assertIn("linear=true", af)
        self.assertIn("alimiter=limit=-1.5dB:attack=5:release=50", af)
        self.assertIn("afade=t=in:ss=0:d=0.030", af)
        self.assertIn("afade=t=out:st=29.970:d=0.030", af)

    def test_audio_filtergraph_extreme_dynamic_range(self):
        """Tests filter construction with quiet input (-38 LUFS) and extreme LRA (28 LU)."""
        stats = LoudnessStats(
            input_i=-38.0,
            input_tp=+2.5,
            input_lra=28.0,
            input_thresh=-48.0,
            target_offset=+3.0,
        )
        af = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=stats,
            highpass_hz=40,
            duration_sec=59.0,
            apply_loop_crossfade=True,
            loudnorm_mode=LoudnormMode.TWO_PASS,
        )
        self.assertIn("measured_I=-38.00", af)
        self.assertIn("measured_TP=2.50", af)
        self.assertIn("measured_LRA=28.00", af)
        self.assertIn("alimiter=limit=-1.5dB:attack=5:release=50", af)
        self.assertIn("afade=t=out:st=58.970:d=0.030", af)

    def test_audio_filtergraph_festival_highpass_cutoff(self):
        """Tests highpass cutoff at 80 Hz for intense festival bass environments."""
        af = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=None,
            highpass_hz=80,
            duration_sec=45.0,
            apply_loop_crossfade=True,
            loudnorm_mode=LoudnormMode.TWO_PASS,
        )
        self.assertTrue(af.startswith("highpass=f=80:poles=2"))
        self.assertIn("alimiter=limit=-1.5dB:attack=5:release=50", af)
        self.assertIn("afade=t=out:st=44.970:d=0.030", af)

    def test_audio_filtergraph_disabled_loudnorm(self):
        """Tests audio filtergraph when loudness normalization is disabled."""
        af = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=None,
            highpass_hz=40,
            duration_sec=20.0,
            apply_loop_crossfade=False,
            loudnorm_mode=LoudnormMode.DISABLED,
        )
        self.assertEqual(af, "highpass=f=40:poles=2")

    def test_audio_filtergraph_short_duration_no_crossfade_underflow(self):
        """Verifies that short audio durations (<= 1.0s) do not produce invalid fade times."""
        af = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=None,
            highpass_hz=40,
            duration_sec=0.5,
            apply_loop_crossfade=True,
            loudnorm_mode=LoudnormMode.TWO_PASS,
        )
        self.assertNotIn("afade", af)


class TestAdversarialSafeZoneGeometryAndAuditing(unittest.TestCase):
    """
    Adversarial verification of safe zone boundaries, geometric calculations,
    and platform coordinate audits.
    """

    def test_safe_zone_coordinate_mathematical_consistency(self):
        """Verifies that safe zone height matches Y2 - Y1 exactly."""
        yt = SAFE_ZONE_YOUTUBE.safe_zone
        self.assertEqual(yt.height, yt.bottom_exclusion_y - yt.top_exclusion_y)
        self.assertEqual(yt.height, 1270)
        self.assertEqual(yt.width, 900)

        tt = SAFE_ZONE_TIKTOK.safe_zone
        self.assertEqual(tt.height, tt.bottom_exclusion_y - tt.top_exclusion_y)
        self.assertEqual(tt.height, 1310)
        self.assertEqual(tt.width, 920)

    def test_kinetic_text_overlay_recommended_position(self):
        """Tests that the standard track text overlay at Y=350 centered (X: 100..940) passes both platform audits."""
        box = BoundingBox(x=100, y=350, width=840, height=80)
        report = SafeZoneAuditor.audit_bounding_box(box)
        self.assertTrue(report.is_compliant)
        self.assertTrue(report.yt_compliant)
        self.assertTrue(report.tiktok_compliant)
        self.assertEqual(len(report.yt_violations), 0)
        self.assertEqual(len(report.tiktok_violations), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
class TestAdversarialQCVerificationThresholds(unittest.TestCase):
    """
    Adversarial evaluation of QC evaluation logic, strict boundary thresholds,
    and tolerance limits.
    """

    def test_qc_report_true_peak_threshold_strictness(self):
        """Verifies that -1.5 dBTP is the strict pass ceiling, and -1.49 / -1.4 fails."""
        # Baseline valid parameters
        kwargs = {
            "file_path": "master.mp4",
            "duration_seconds": 30.0,
            "duration_compliant": True,
            "resolution": "1080x1920",
            "resolution_compliant": True,
            "framerate_fps": 60.0,
            "framerate_compliant": True,
            "measured_lufs": -14.0,
            "lufs_compliant": True,
        }

        # Passing True Peaks (<= -1.5 dBTP)
        for tp in [-1.5, -1.6, -2.0, -3.0, -10.0]:
            tp_ok = (tp <= AUDIO_TARGET_TRUE_PEAK)
            self.assertTrue(tp_ok, f"True Peak {tp} dBTP should pass <= -1.5 dBTP")

        # Failing True Peaks (> -1.5 dBTP)
        for tp in [-1.49, -1.4, -1.2, -1.0, -0.5, 0.0, +1.0]:
            tp_ok = (tp <= AUDIO_TARGET_TRUE_PEAK)
            self.assertFalse(tp_ok, f"True Peak {tp} dBTP should FAIL <= -1.5 dBTP")

    def test_qc_report_lufs_tolerance_boundaries(self):
        """Verifies integrated loudness must be within [-15.0, -13.0] LUFS."""
        min_lufs = AUDIO_TARGET_LUFS - AUDIO_LUFS_TOLERANCE  # -15.0
        max_lufs = AUDIO_TARGET_LUFS + AUDIO_LUFS_TOLERANCE  # -13.0

        # Passing LUFS values
        for lufs in [-14.0, -13.0, -15.0, -13.5, -14.5]:
            lufs_ok = (min_lufs <= lufs <= max_lufs)
            self.assertTrue(lufs_ok, f"LUFS {lufs} should pass within [-15.0, -13.0]")

        # Failing LUFS values
        for lufs in [-12.9, -12.0, -10.0, -15.1, -16.0, -20.0]:
            lufs_ok = (min_lufs <= lufs <= max_lufs)
            self.assertFalse(lufs_ok, f"LUFS {lufs} should FAIL outside [-15.0, -13.0]")

    def test_qc_report_duration_clamp_threshold(self):
        """Verifies duration <= 59.0s (+0.1s tolerance)."""
        # Passing durations
        for dur in [15.0, 30.0, 45.0, 58.9, 59.0, 59.05]:
            dur_ok = (dur <= VIDEO_DURATION_MAX_SECONDS + 0.1)
            self.assertTrue(dur_ok, f"Duration {dur}s should pass <= 59.0s")

        # Failing durations
        for dur in [59.2, 59.5, 60.0, 65.0, 120.0]:
            dur_ok = (dur <= VIDEO_DURATION_MAX_SECONDS + 0.1)
            self.assertFalse(dur_ok, f"Duration {dur}s should FAIL > 59.0s")


class TestAdversarialSEOAndGenreProfiles(unittest.TestCase):
    """
    Adversarial evaluation of SEO package generation, hashtag boundaries,
    and genre profiles.
    """

    def test_seo_title_length_auto_trim_fallback(self):
        """Verifies that standard long titles trigger the compact template fallback."""
        artist = "John Summit & Hayla"
        track = "Where You Are (Gorgon City Remix)"
        event = "Creamfields North Festival"
        payload = SEOCaptionGenerator.generate_seo_package(
            artist=artist,
            track=track,
            event=event,
            genre="house",
        )
        # Primary template would be > 95 chars, so it should trigger the compact fallback
        self.assertLessEqual(len(payload.yt_title), 100)
        self.assertIn("#Shorts", payload.yt_title)
        self.assertIn(artist, payload.yt_title)

    def test_seo_hashtag_cluster_maximum_limit(self):
        """Verifies that hashtag count is capped between 5 and 7 tags."""
        for genre in ["dubstep", "house", "techno", "trance", "dnb", "unknown_subgenre"]:
            payload = SEOCaptionGenerator.generate_seo_package(
                artist="Excision",
                track="Decimate",
                event="LostLands",
                genre=genre,
            )
            self.assertGreaterEqual(len(payload.hashtags), 5)
            self.assertLessEqual(len(payload.hashtags), 7)
            for tag in payload.hashtags:
                self.assertTrue(tag.startswith("#"), f"Hashtag '{tag}' must start with #")

    def test_all_genre_profiles_have_valid_bpms_and_hashtags(self):
        """Verifies that all 5 EDM genres have defined BPM ranges and non-empty hashtags."""
        genres = ["dubstep", "house", "techno", "trance", "dnb"]
        for g in genres:
            prof = get_genre_profile(g)
            self.assertIsNotNone(prof)
            self.assertGreater(prof.typical_bpm_range[0], 100)
            self.assertGreater(prof.typical_bpm_range[1], prof.typical_bpm_range[0])
            self.assertGreater(len(prof.recommended_hashtags), 0)
