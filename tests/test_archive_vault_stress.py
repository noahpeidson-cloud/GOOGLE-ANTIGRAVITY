"""
Adversarial Stress Test Suite for Archive Vault Tools
Tests boundary conditions, extreme inputs, killswitches, and safety invariants.
"""

import math
import os
from pathlib import Path
import re
import sys
import tempfile
import pytest
from pydantic import ValidationError

# Ensure archive vault modules are importable
VAULT_ROOT = Path(r"d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault")
sys.path.insert(0, str(VAULT_ROOT))
sys.path.insert(0, str(VAULT_ROOT / "video_transcoding"))
sys.path.insert(0, str(VAULT_ROOT / "ingestion_hardware"))
sys.path.insert(0, str(VAULT_ROOT / "viral_intelligence"))

import atempo_filter_compiler
from atempo_filter_compiler import (
    build_atempo_chain,
    compile_speed_filter,
    compile_multi_segment_speed_ramp,
    SpeedSegment,
    SpeedFilterResult,
    format_float,
)

import canonical_filename_normalizer
from canonical_filename_normalizer import (
    FilenameNormalizer,
    DirectoryHealthGuard,
)

import evpi_viral_grading_model
from evpi_viral_grading_model import (
    compute_killswitches,
    calculate_evpi,
    classify_verdict,
    evaluate_video_metrics,
    ViralScoreReport,
    TrendingVerdict,
    HookMetrics,
    RetentionMetrics,
)

import safe_zone_seo_auditor
from safe_zone_seo_auditor import (
    SafeZoneAuditor,
    OverlayBoundingBox,
    SEOPackager,
    CommentSpamAuditor,
    CANONICAL_17_SPAM_KEYWORDS,
    YOUTUBE_SHORTS_SAFE_ZONE,
    TIKTOK_SAFE_ZONE,
)


# ============================================================================
# 1. ATEMPO FILTER COMPILER STRESS TESTS
# ============================================================================

class TestAtempoFilterCompilerStress:
    """Adversarial stress testing of atempo filter decomposition and PTS calculation."""

    def test_identity_speed_1_0x(self):
        """Speed 1.0x must yield passthrough 'anull' and identity setpts."""
        chain = build_atempo_chain(1.0)
        assert chain == "anull", f"Expected 'anull', got '{chain}'"

        res = compile_speed_filter(1.0)
        assert res.is_passthrough is True
        assert res.atempo_chain == "anull"
        assert res.video_pts_factor == 1.0
        assert "setpts=PTS-STARTPTS" in res.video_filter

    def test_extreme_fast_speed_8_0x(self):
        """Speed 8.0x must decompose into three 2.0x filters (2.0 * 2.0 * 2.0 = 8.0)."""
        chain = build_atempo_chain(8.0)
        expected = "atempo=2.0,atempo=2.0,atempo=2.0"
        assert chain == expected, f"Expected '{expected}', got '{chain}'"

        # Verify individual filter bounds [0.5, 2.0]
        filters = [float(f.split("=")[1]) for f in chain.split(",")]
        for f_val in filters:
            assert 0.5 <= f_val <= 2.0, f"Filter {f_val} violates [0.5, 2.0]"
        prod = math.prod(filters)
        assert math.isclose(prod, 8.0, rel_tol=1e-3), f"Cumulative product {prod} != 8.0"

        res = compile_speed_filter(8.0)
        assert math.isclose(res.video_pts_factor, 0.125, rel_tol=1e-4)

    def test_extreme_slow_speed_0_1x(self):
        """Speed 0.1x must decompose into chained 0.5x with compliant remainder (0.5^3 * 0.8 = 0.1)."""
        chain = build_atempo_chain(0.1)
        expected = "atempo=0.5,atempo=0.5,atempo=0.5,atempo=0.8"
        assert chain == expected, f"Expected '{expected}', got '{chain}'"

        filters = [float(f.split("=")[1]) for f in chain.split(",")]
        for f_val in filters:
            assert 0.5 <= f_val <= 2.0, f"Filter {f_val} violates [0.5, 2.0]"
        prod = math.prod(filters)
        assert math.isclose(prod, 0.1, rel_tol=1e-3), f"Cumulative product {prod} != 0.1"

        res = compile_speed_filter(0.1)
        assert math.isclose(res.video_pts_factor, 10.0, rel_tol=1e-4)

    @pytest.mark.parametrize("speed", [0.05, 0.125, 0.25, 0.333, 0.5, 0.75, 1.5, 2.0, 3.5, 4.0, 5.0, 10.0, 16.0])
    def test_arbitrary_speeds_bounds_and_product(self, speed):
        """Every speed must decompose to filters strictly within [0.5, 2.0] and product = speed."""
        chain = build_atempo_chain(speed)
        if chain == "anull":
            assert math.isclose(speed, 1.0, rel_tol=1e-4)
            return

        filters = [float(f.split("=")[1]) for f in chain.split(",")]
        for f_val in filters:
            assert 0.5 <= f_val <= 2.0, f"Filter {f_val} out of bounds for speed {speed}"
        prod = math.prod(filters)
        assert math.isclose(prod, speed, rel_tol=1e-3), f"Product {prod} != {speed}"

    def test_invalid_speeds_raise_value_error(self):
        """Zero or negative speeds must raise ValueError."""
        with pytest.raises(ValueError):
            build_atempo_chain(0.0)

        with pytest.raises(ValueError):
            build_atempo_chain(-1.5)

        with pytest.raises(ValueError):
            compile_speed_filter(0.0)

        with pytest.raises(ValueError):
            compile_speed_filter(-5.0)

    def test_multi_segment_empty_list_raises(self):
        """compile_multi_segment_speed_ramp with empty segments must raise ValueError."""
        with pytest.raises(ValueError):
            compile_multi_segment_speed_ramp([])

    def test_multi_segment_speed_ramp_syntax(self):
        """Multi-segment compilation produces valid concat filtergraph syntax."""
        segments = [
            SpeedSegment(segment_id="s1", source_in_sec=0.0, source_out_sec=5.0, speed_multiplier=1.0),
            SpeedSegment(segment_id="s2", source_in_sec=5.0, source_out_sec=10.0, speed_multiplier=4.0),
        ]
        fg = compile_multi_segment_speed_ramp(segments)
        assert "[v0]" in fg
        assert "[a0]" in fg
        assert "[v1]" in fg
        assert "[a1]" in fg
        assert "concat=n=2:v=1:a=1" in fg

    def test_single_segment_speed_ramp_no_concat(self):
        """Single segment ramp should not use concat filter, but aliases null and anull."""
        segments = [
            SpeedSegment(segment_id="single", source_in_sec=0.0, source_out_sec=10.0, speed_multiplier=2.0)
        ]
        fg = compile_multi_segment_speed_ramp(segments)
        assert "concat=" not in fg
        assert "[v0]null[vout]" in fg
        assert "[a0]anull[aout]" in fg

    @pytest.mark.parametrize("extreme_speed", [0.001, 0.01, 32.0, 64.0, 128.0])
    def test_extreme_speeds_chain_and_reconstruction(self, extreme_speed):
        """Verify decomposition under extreme fast/slow speeds without recursion depth error."""
        chain = build_atempo_chain(extreme_speed)
        filters = [float(f.split("=")[1]) for f in chain.split(",")]
        for f in filters:
            assert 0.5 <= f <= 2.0
        prod = math.prod(filters)
        assert math.isclose(prod, extreme_speed, rel_tol=1e-2)

    @pytest.mark.parametrize("irrational_speed", [1/3, 1/7, math.pi, math.e, math.sqrt(2)])
    def test_non_integer_irrational_speeds(self, irrational_speed):
        """Verify irrational/periodic decimal speeds compile without numeric breakdown."""
        chain = build_atempo_chain(irrational_speed)
        filters = [float(f.split("=")[1]) for f in chain.split(",")]
        for f in filters:
            assert 0.5 <= f <= 2.0
        prod = math.prod(filters)
        assert math.isclose(prod, irrational_speed, rel_tol=1e-2)


# ============================================================================
# 2. CANONICAL FILENAME NORMALIZER STRESS TESTS
# ============================================================================

class TestCanonicalFilenameNormalizerStress:
    """Adversarial stress testing of filename sanitization, character maps, and capacity guarding."""

    def test_emoji_sanitization(self):
        """Emojis must be stripped completely without crashing or corrupting ascii output."""
        token = "Subtronics 🔥🚀🎉 Bass"
        cleaned = FilenameNormalizer.sanitize_token(token)
        assert cleaned == "SubtronicsBass", f"Expected 'SubtronicsBass', got '{cleaned}'"

    def test_pure_emoji_falls_back_to_default(self):
        """String of pure emojis must fallback safely to default."""
        cleaned = FilenameNormalizer.sanitize_token("🔥🔥🔥", default="Fallback")
        assert cleaned == "Fallback"

    def test_european_latin_char_transliterations(self):
        """European DJ special characters must transliterate properly."""
        # Ø, ø, Æ, æ, ß, Ł, ł, Đ, đ, Þ, þ, Œ, œ, Å, å
        test_cases = [
            ("Møme", "Mome"),
            ("Kölsch", "Kolsch"),
            ("Æon", "Aeon"),
            ("Strauß", "Strauss"),
            ("Łukasz", "Lukasz"),
            ("Đorđe", "Dorde"),
            ("Þórr", "Thorr"),
            ("Ålesund", "Alesund"),
        ]
        for raw, expected in test_cases:
            res = FilenameNormalizer.sanitize_token(raw)
            assert res == expected, f"Failed for '{raw}': expected '{expected}', got '{res}'"

    def test_illegal_windows_filesystem_characters(self):
        """Illegal Windows filesystem characters (< > : \" / \\ | ? *) must be stripped."""
        raw = 'Track <1> : "VIP" / Remix \\ Edit | Live ? Star*'
        cleaned = FilenameNormalizer.sanitize_token(raw)
        # Check no illegal characters remain
        assert not re.search(r'[<>:"/\\|?*]', cleaned)
        assert cleaned == "Track1VipRemixEditLiveStar"

    def test_extreme_length_token(self):
        """Tokens of extreme lengths (10,000 chars) must not cause catastrophic backtracking or crash."""
        massive_input = ("SuperLongArtistName" * 500) + "!"
        cleaned = FilenameNormalizer.sanitize_token(massive_input)
        assert cleaned.startswith("Superlongartistname")
        assert len(cleaned) == len("SuperLongArtistName") * 500

    def test_parse_filename_valid_and_invalid(self):
        """Canonical parser correctly identifies valid syntax and rejects invalid syntax."""
        valid = "20260904_EDCLV_Subtronics_GrizCollab-VIP_V1_4k.mp4"
        parsed = FilenameNormalizer.parse_filename(valid)
        assert parsed is not None
        assert parsed["date"] == "20260904"
        assert parsed["event"] == "EDCLV"
        assert parsed["artist"] == "Subtronics"
        assert parsed["track"] == "GrizCollab-VIP"
        assert parsed["resolution"] == "4k"

        # Invalid formats
        assert FilenameNormalizer.parse_filename("random_file.mp4") is None
        assert FilenameNormalizer.parse_filename("20260904_EDCLV.mp4") is None
        assert FilenameNormalizer.parse_filename("") is None

    def test_directory_health_guard_overflow_partitioning(self):
        """DirectoryHealthGuard must partition into _Batch02, _Batch03 when threshold reached."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "01_RAW"
            guard = DirectoryHealthGuard(max_items=2)

            # Primary folder
            f1 = guard.get_healthy_subfolder(base_dir, "Clips")
            assert f1.name == "Clips"
            (f1 / "file1.mp4").touch()
            (f1 / "file2.mp4").touch()

            # Overflow to Batch02
            f2 = guard.get_healthy_subfolder(base_dir, "Clips")
            assert f2.name == "Clips_Batch02"
            (f2 / "file3.mp4").touch()
            (f2 / "file4.mp4").touch()

            # Overflow to Batch03
            f3 = guard.get_healthy_subfolder(base_dir, "Clips")
            assert f3.name == "Clips_Batch03"

    def test_path_traversal_sanitization(self):
        """Path traversal patterns must be neutralized into plain alphanumeric tokens."""
        dangerous = "../../etc/passwd"
        cleaned = FilenameNormalizer.sanitize_token(dangerous)
        assert "/" not in cleaned and ".." not in cleaned
        assert cleaned == "EtcPasswd"

        win_dangerous = "..\\..\\Windows\\System32"
        cleaned_win = FilenameNormalizer.sanitize_token(win_dangerous)
        assert "\\" not in cleaned_win and ".." not in cleaned_win
        assert cleaned_win == "WindowsSystem32"

    def test_whitespace_and_newlines_sanitization(self):
        """Tabs, carriage returns, and newlines must be stripped/collapsed."""
        messy = "\t\r\n  Subtronics  \t\n  Live   \r\n"
        cleaned = FilenameNormalizer.sanitize_token(messy)
        assert cleaned == "SubtronicsLive"

    def test_build_canonical_filename_defaults_and_resolutions(self):
        """Missing tokens fallback to defaults, resolution formatted with 'p' if needed."""
        fname = FilenameNormalizer.build_canonical_filename(
            event=None,
            artist=None,
            track=None,
            resolution="1080",
            version=2,
            date_str="20260904",
        )
        assert fname == "20260904_Event_Artist_ID_V2_1080p.mp4"

        # 4k preservation
        fname_4k = FilenameNormalizer.build_canonical_filename(
            event="EDC",
            artist="SVDDENDEATH",
            track="Voyd",
            resolution="4k",
            date_str="20260904",
        )
        assert fname_4k == "20260904_Edc_Svddendeath_Voyd_V1_4k.mp4"


# ============================================================================
# 3. EVPI VIRAL GRADING MODEL STRESS TESTS
# ============================================================================

class TestEVPIViralGradingModelStress:
    """Adversarial stress testing of EVPI mathematical formulation and killswitches."""

    def test_audio_clipping_killswitch_collapse(self):
        """Severe audio clipping must impose 0.10 multiplier, collapsing high scores into LOW_REACH."""
        # 100 on all metrics
        report = evaluate_video_metrics(
            video_id="clip_01",
            duration_seconds=25.0,
            hook_score=100.0,
            retention_score=100.0,
            visual_score=100.0,
            coherence_score=100.0,
            pacing_score=100.0,
            audio_clipping_detected=True,
        )
        assert report.evpi_raw == 100.0
        # Multiplier = 0.10 * 1.0 * 1.0 = 0.10
        assert math.isclose(report.killswitch_multiplier, 0.10, abs_tol=1e-2)
        assert math.isclose(report.evpi_composite, 10.0, abs_tol=0.5)
        assert report.trending_verdict == TrendingVerdict.LOW_REACH.value

    def test_duration_boundary_penalties(self):
        """Duration killswitches must strictly penalize out-of-envelope videos."""
        # Optimal [12s, 38s] -> 1.0
        _, _, k_opt = compute_killswitches(False, "9:16", 20.0)
        assert k_opt == 1.00

        # Boundary checks
        _, _, k_opt_min = compute_killswitches(False, "9:16", 12.0)
        assert k_opt_min == 1.00
        _, _, k_opt_max = compute_killswitches(False, "9:16", 38.0)
        assert k_opt_max == 1.00

        # Acceptable [8s, 12s) or (38s, 60s] -> 0.85
        _, _, k_acc_low = compute_killswitches(False, "9:16", 10.0)
        assert k_acc_low == 0.85
        _, _, k_acc_high = compute_killswitches(False, "9:16", 45.0)
        assert k_acc_high == 0.85

        # Defective < 8s or > 60s -> 0.40
        _, _, k_short = compute_killswitches(False, "9:16", 5.0)
        assert k_short == 0.40
        _, _, k_long = compute_killswitches(False, "9:16", 75.0)
        assert k_long == 0.40

    def test_safe_zone_violation_and_aspect_ratios(self):
        """Safe zone collision imposes 0.50 multiplier."""
        _, k_sz, _ = compute_killswitches(False, "9:16", 20.0, safe_zone_violation=True)
        assert k_sz == 0.50

        # Aspect ratios without safe zone violation
        _, k_916, _ = compute_killswitches(False, "9:16", 20.0, safe_zone_violation=False)
        assert k_916 == 1.00
        _, k_11, _ = compute_killswitches(False, "1:1", 20.0, safe_zone_violation=False)
        assert k_11 == 0.85
        _, k_169, _ = compute_killswitches(False, "16:9", 20.0, safe_zone_violation=False)
        assert k_169 == 0.50

    def test_compound_triple_killswitch_collapse(self):
        """Simultaneous audio clipping, safe zone violation, and bad duration collapses score to 0.02x."""
        k_a, k_f, k_d = compute_killswitches(
            audio_clipping_detected=True,      # 0.10
            aspect_ratio="9:16",
            duration_seconds=5.0,              # 0.40
            safe_zone_violation=True,          # 0.50
        )
        total_mult = k_a * k_f * k_d
        assert math.isclose(total_mult, 0.02, abs_tol=1e-4)

        raw, comp = calculate_evpi(100, 100, 100, 100, 100, k_audio=k_a, k_format=k_f, k_duration=k_d)
        assert raw == 100.0
        assert comp == 2.0

    def test_pydantic_schema_validation_bounds(self):
        """Pydantic must reject out-of-bound scores (<0 or >100) and invalid durations."""
        with pytest.raises(ValidationError):
            evaluate_video_metrics(
                video_id="err",
                duration_seconds=20.0,
                hook_score=150.0,  # Invalid > 100
                retention_score=80.0,
                visual_score=80.0,
                coherence_score=80.0,
                pacing_score=80.0,
            )

        with pytest.raises(ValidationError):
            evaluate_video_metrics(
                video_id="err",
                duration_seconds=0.5,  # Invalid < 1.0s
                hook_score=80.0,
                retention_score=80.0,
                visual_score=80.0,
                coherence_score=80.0,
                pacing_score=80.0,
            )

    @pytest.mark.parametrize(
        "duration, expected_k",
        [
            (7.99, 0.40),
            (8.00, 0.85),
            (11.99, 0.85),
            (12.00, 1.00),
            (38.00, 1.00),
            (38.01, 0.85),
            (60.00, 0.85),
            (60.01, 0.40),
        ],
    )
    def test_exact_duration_threshold_transitions(self, duration, expected_k):
        """Micro-step duration values verify sharp step-function killswitch boundaries."""
        _, _, k_d = compute_killswitches(False, "9:16", duration)
        assert math.isclose(k_d, expected_k, abs_tol=1e-4), f"Duration {duration}s expected k_d={expected_k}, got {k_d}"

    def test_zero_scores_and_minimal_evpi(self):
        """All zero sub-scores produce 0.0 EVPI and LOW_REACH verdict."""
        report = evaluate_video_metrics(
            video_id="zero_clip",
            duration_seconds=15.0,
            hook_score=0.0,
            retention_score=0.0,
            visual_score=0.0,
            coherence_score=0.0,
            pacing_score=0.0,
        )
        assert report.evpi_raw == 0.0
        assert report.evpi_composite == 0.0
        assert report.trending_verdict == TrendingVerdict.LOW_REACH.value

    def test_custom_weights_auto_normalization(self):
        """Custom non-unitary weights (e.g. all 10.0, sum=50.0) must be automatically normalized."""
        weights = {
            "weight_hook": 10.0,
            "weight_retention": 10.0,
            "weight_visual": 10.0,
            "weight_coherence": 10.0,
            "weight_pacing": 10.0,
        }
        # Equal scores 80.0 across all components
        raw, comp = calculate_evpi(80.0, 80.0, 80.0, 80.0, 80.0, weights=weights)
        assert math.isclose(raw, 80.0, abs_tol=1e-2)
        assert math.isclose(comp, 80.0, abs_tol=1e-2)


# ============================================================================
# 4. SAFE ZONE & SEO AUDITOR STRESS TESTS
# ============================================================================

class TestSafeZoneSEOAuditorStress:
    """Adversarial stress testing of safe zone boundary collisions, SEO packaging, and spam filter."""

    def test_safe_zone_exact_boundaries(self):
        """Overlay exactly inside boundary passes; 1-px protrusion triggers collision."""
        # YouTube Shorts safe area: X: 60-960, Y: 180-1450
        # Exact fit
        exact_box = OverlayBoundingBox(x=60, y=180, width=900, height=1270)
        report = SafeZoneAuditor.audit_bounding_box(exact_box)
        assert report.yt_compliant is True
        assert report.tiktok_compliant is True
        assert report.is_compliant is True

        # Off-by-one top violation (Y=179 for YT)
        top_protrusion = OverlayBoundingBox(x=60, y=179, width=900, height=1270)
        rep_top = SafeZoneAuditor.audit_bounding_box(top_protrusion)
        assert rep_top.yt_compliant is False
        assert any("Top Collision" in v for v in rep_top.yt_violations)

        # Off-by-one right rail violation (X2=961)
        right_protrusion = OverlayBoundingBox(x=60, y=180, width=901, height=1270)
        rep_right = SafeZoneAuditor.audit_bounding_box(right_protrusion)
        assert rep_right.yt_compliant is False
        assert rep_right.tiktok_compliant is False
        assert any("Right Rail Collision" in v for v in rep_right.yt_violations)

        # Off-by-one bottom violation (Y2=1451 for YT)
        bot_protrusion = OverlayBoundingBox(x=60, y=180, width=900, height=1271)
        rep_bot = SafeZoneAuditor.audit_bounding_box(bot_protrusion)
        assert rep_bot.yt_compliant is False
        # Note: TikTok safe_y_max is 1470, so TikTok remains compliant
        assert rep_bot.tiktok_compliant is True

    def test_extreme_hazard_coordinates(self):
        """Negative coordinates, zero dimensions, and massive canvas-exceeding coordinates."""
        # Negative coords
        rep_neg = SafeZoneAuditor.audit_coordinates(-50, -100, 200, 200)
        assert rep_neg.is_compliant is False
        assert len(rep_neg.yt_violations) >= 2

        # Massive screen coverage (1080x1920)
        rep_full = SafeZoneAuditor.audit_coordinates(0, 0, 1080, 1920)
        assert rep_full.is_compliant is False
        assert len(rep_full.yt_violations) == 4  # top, bottom, left, right

    def test_seo_hashtag_cluster_bounds(self):
        """Hashtag cluster must strictly contain between 5 and 7 hashtags."""
        tags = SEOPackager.generate_hashtag_cluster(
            artist="John Summit",
            event="EDC Las Vegas",
            genre="house",
            year=2026,
        )
        assert 5 <= len(tags) <= 7, f"Expected 5-7 tags, got {len(tags)}: {tags}"
        assert "#EDM" in tags
        assert "#JohnSummit" in tags
        assert "#EDCLasVegas2026" in tags

    def test_seo_special_character_artist_and_genre(self):
        """Special characters in artist names must be sanitized into valid hashtags."""
        tags = SEOPackager.generate_hashtag_cluster(
            artist="Kölsch & Møme!",
            event="Tomorrowland",
            genre="melodic",
            year=2026,
        )
        assert 5 <= len(tags) <= 7
        # Verify no illegal characters in hashtags
        for t in tags:
            assert t.startswith("#")
            assert not re.search(r"[\s&!]", t), f"Hashtag '{t}' contains invalid characters"

    def test_canonical_17_spam_keyword_filtering(self):
        """All 17 canonical spam keywords must be positively caught and blocked."""
        auditor = CommentSpamAuditor()
        for kw in CANONICAL_17_SPAM_KEYWORDS:
            comment = f"Hey great video bro {kw} for more info"
            is_spam, matches = auditor.check_comment(comment)
            assert is_spam is True, f"Failed to detect spam keyword: '{kw}' in '{comment}'"
            assert len(matches) > 0

    def test_comment_spam_evasion_and_false_positive_control(self):
        """Evasion patterns caught; benign concert comments must pass cleanly."""
        auditor = CommentSpamAuditor()

        # Evasion punctuation (check.bio, check_bio, check-bio)
        assert auditor.check_comment("Check.bio for exclusive tickets")[0] is True
        assert auditor.check_comment("Check-bio right now")[0] is True
        assert auditor.check_comment("Check_bio on profile")[0] is True

        # Benign EDM comments should NOT be flagged
        clean_comments = [
            "This set was absolutely unreal! Who played after him?",
            "That bass drop melted my face off at 2am",
            "Track ID at 0:15 please? Such clean lasers!",
            "John Summit always delivers pure fire on the main stage",
        ]
        for c in clean_comments:
            is_spam, matches = auditor.check_comment(c)
            assert is_spam is False, f"False positive on clean comment '{c}': matched {matches}"

    def test_word_boundary_false_positive_immunity(self):
        """Words containing spam substrings (cryptography, telegrams, biome) must NOT trigger spam detection."""
        auditor = CommentSpamAuditor()
        safe_words = [
            "We studied modern cryptography in computer science class",
            "Old telegrams from the 1920s were delivered by courier",
            "The desert biome of Las Vegas gets chilly at night",
        ]
        for s in safe_words:
            is_spam, matches = auditor.check_comment(s)
            assert is_spam is False, f"False positive on safe word phrase '{s}': matched {matches}"

    def test_platform_boundary_discrepancy_tiktok_vs_youtube(self):
        """Overlay in TikTok safe area (X=50, Y=170) but outside YouTube safe area (X>=60, Y>=180)."""
        # Box: X=50, Y=170, W=800, H=1000
        box = OverlayBoundingBox(x=50, y=170, width=800, height=1000)
        report = SafeZoneAuditor.audit_bounding_box(box)
        # TikTok: safe_x_min=40, safe_y_min=160 -> X=50 and Y=170 are COMPLIANT
        assert report.tiktok_compliant is True
        # YouTube Shorts: safe_x_min=60, safe_y_min=180 -> X=50 and Y=170 are VIOLATIONS
        assert report.yt_compliant is False
        assert report.is_compliant is False
        assert any("Left Clearance" in v for v in report.yt_violations)
        assert any("Top Collision" in v for v in report.yt_violations)
