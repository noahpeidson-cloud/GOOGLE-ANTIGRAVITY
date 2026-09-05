"""
Empirical Stress Test Suite for Media Pipeline Archive Vault
Covers all extracted modules in `d:\\GOOGLE ANTIGRAVITY\\content_creation\\_archive_vault`:
- audio_dsp/edm_drop_detector.py
- audio_dsp/ebu_r128_normalizer.py
- video_transcoding/atempo_filter_compiler.py
- ingestion_hardware/canonical_filename_normalizer.py
- ingestion_hardware/win32_three_tier_file_locker.py
- viral_intelligence/evpi_viral_grading_model.py
- viral_intelligence/safe_zone_seo_auditor.py
- Frontend/Inventory frontmatter compliance across all vaulted modules.
"""

from __future__ import annotations

import asyncio
import compileall
import importlib.util
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any, Dict, List

import numpy as np
import pytest

VAULT_DIR = Path(r"d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault").resolve()

# Helper to dynamically import from vault subdirectories avoiding collisions with legacy root modules
def load_vault_module(relative_path: str, module_name: str):
    full_path = VAULT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(module_name, full_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {full_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load modules under unique names to prevent package collisions
edm_drop_mod = load_vault_module("audio_dsp/edm_drop_detector.py", "vault_edm_drop_detector")
ebu_r128_mod = load_vault_module("audio_dsp/ebu_r128_normalizer.py", "vault_ebu_r128_normalizer")
atempo_mod = load_vault_module("video_transcoding/atempo_filter_compiler.py", "vault_atempo_filter_compiler")
filename_mod = load_vault_module("ingestion_hardware/canonical_filename_normalizer.py", "vault_canonical_filename_normalizer")
file_locker_mod = load_vault_module("ingestion_hardware/win32_three_tier_file_locker.py", "vault_win32_three_tier_file_locker")
evpi_mod = load_vault_module("viral_intelligence/evpi_viral_grading_model.py", "vault_evpi_viral_grading_model")
safe_zone_mod = load_vault_module("viral_intelligence/safe_zone_seo_auditor.py", "vault_safe_zone_seo_auditor")
profiles_mod = load_vault_module("video_transcoding/lossless_encoding_profiles.py", "vault_lossless_encoding_profiles")
tonemap_mod = load_vault_module("video_transcoding/mobius_hdr_tonemapper.py", "vault_mobius_hdr_tonemapper")
content_id_mod = load_vault_module("viral_intelligence/youtube_content_id_guard.py", "vault_youtube_content_id_guard")
streamer_mod = load_vault_module("davinci_automation/http_range_video_streamer.py", "vault_http_range_video_streamer")
timeline_mod = load_vault_module("davinci_automation/resolve_timeline_builder.py", "vault_resolve_timeline_builder")
adb_mod = load_vault_module("ingestion_hardware/samsung_adb_ingestor.py", "vault_samsung_adb_ingestor")


# ============================================================================
# 1. SYNTAX COMPILATION TESTS
# ============================================================================

def test_compileall_archive_vault():
    """Validates that all Python files in _archive_vault compile without SyntaxError."""
    assert VAULT_DIR.is_dir(), f"Vault directory does not exist: {VAULT_DIR}"
    success = compileall.compile_dir(str(VAULT_DIR), force=True, quiet=1)
    assert success is True, "compileall failed on _archive_vault directory"


# ============================================================================
# 2. FRONTMATTER / DOCSTRING METADATA COMPLIANCE (R2 Acceptance Criteria)
# ============================================================================

def test_all_vault_artifacts_have_required_frontmatter():
    """
    R2 Acceptance Criteria: Every tool or concept in _archive_vault MUST have frontmatter
    or formatted docstring containing:
    - Name
    - Context Mapping (or context_mapping)
    - Strengths
    - Weaknesses
    - Implementation Instructions (or implementation_instructions)
    """
    python_files = list(VAULT_DIR.glob("**/*.py"))
    md_files = [f for f in VAULT_DIR.glob("**/*.md") if not f.name.startswith(".")]
    all_artifacts = python_files + md_files

    assert len(all_artifacts) >= 10, f"Expected at least 10 artifacts, found {len(all_artifacts)}"

    missing_fields = {}
    for art in all_artifacts:
        content = art.read_text(encoding="utf-8", errors="ignore").lower()
        missing = []
        if "name" not in content:
            missing.append("name")
        if "context mapping" not in content and "context_mapping" not in content:
            missing.append("context mapping")
        if "strengths" not in content:
            missing.append("strengths")
        if "weaknesses" not in content:
            missing.append("weaknesses")
        if "implementation instructions" not in content and "implementation_instructions" not in content:
            missing.append("implementation instructions")

        if missing:
            missing_fields[art.relative_to(VAULT_DIR).as_posix()] = missing

    assert not missing_fields, f"Artifacts missing mandatory frontmatter fields: {missing_fields}"


# ============================================================================
# 3. AUDIO DSP: EDM DROP DETECTOR TESTS
# ============================================================================

def test_edm_drop_detector_synthetic_localization():
    """Verifies that synthetic 90s EDM signal with drop at 30s is localized accurately."""
    AudioDropDetector = edm_drop_mod.AudioDropDetector
    generate_synthetic_edm_signal = edm_drop_mod.generate_synthetic_edm_signal

    detector = AudioDropDetector(target_duration_sec=30.0)
    sig = generate_synthetic_edm_signal(
        total_duration_sec=90.0, drop_start_sec=30.0, drop_duration_sec=30.0
    )
    result = detector.detect_optimal_drop(sig)

    assert result.duration_sec == 30.0
    assert abs(result.start_time_sec - 30.0) < 0.5, f"Drop localized at {result.start_time_sec}s, expected ~30.0s"
    assert result.max_rms_energy > 0.3
    assert result.is_manual_override is False


def test_edm_drop_detector_short_audio_fallback():
    """Verifies graceful fallback when audio buffer is shorter than target duration."""
    AudioDropDetector = edm_drop_mod.AudioDropDetector

    detector = AudioDropDetector(target_duration_sec=30.0, sample_rate=22050)
    short_sig = np.random.uniform(-0.1, 0.1, 22050 * 5).astype(np.float32)  # 5 seconds
    result = detector.detect_optimal_drop(short_sig)

    assert result.detection_method == "short_audio_fallback"
    assert result.start_time_sec == 0.0
    assert result.duration_sec == 5.0
    assert result.end_time_sec == 5.0


def test_edm_drop_detector_empty_audio_fallback():
    """Verifies graceful fallback on empty audio stream."""
    AudioDropDetector = edm_drop_mod.AudioDropDetector

    detector = AudioDropDetector(target_duration_sec=30.0)
    empty_sig = np.array([], dtype=np.float32)
    result = detector.detect_optimal_drop(empty_sig)

    assert result.detection_method == "no_audio_stream"
    assert result.start_time_sec == 0.0
    assert result.duration_sec == 30.0
    assert result.max_rms_energy == 0.0


def test_edm_drop_detector_silent_audio_fallback():
    """Verifies silent audio (RMS < 1e-4) returns silent_audio_fallback."""
    AudioDropDetector = edm_drop_mod.AudioDropDetector

    detector = AudioDropDetector(target_duration_sec=30.0)
    silent_sig = np.zeros(22050 * 45, dtype=np.float32)  # 45 seconds of pure silence
    result = detector.detect_optimal_drop(silent_sig)

    assert result.detection_method == "silent_audio_fallback"
    assert result.start_time_sec == 0.0
    assert result.duration_sec == 30.0
    assert result.max_rms_energy == 0.0


def test_edm_drop_detector_manual_override():
    """Verifies manual override immediately bypasses DSP math and returns exact values."""
    AudioDropDetector = edm_drop_mod.AudioDropDetector

    detector = AudioDropDetector(target_duration_sec=30.0)
    result = detector.detect_optimal_drop(
        media_path=np.zeros(10, dtype=np.float32),
        manual_start_time=14.5,
        manual_duration=22.0,
    )

    assert result.is_manual_override is True
    assert result.detection_method == "manual_cli_override"
    assert result.start_time_sec == 14.5
    assert result.duration_sec == 22.0
    assert result.end_time_sec == 36.5


def test_edm_drop_detector_numpy_strided_rms():
    """Verifies numpy strided RMS fallback calculates accurate RMS energy without librosa."""
    AudioDropDetector = edm_drop_mod.AudioDropDetector

    detector = AudioDropDetector(target_duration_sec=30.0, hop_length=512, frame_length=2048)
    # 440Hz sine wave with amplitude 0.5 -> theoretical RMS = 0.5 / sqrt(2) ≈ 0.3535
    t = np.linspace(0, 2.0, 22050 * 2, endpoint=False)
    sine = (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)

    rms, method = detector.calculate_rms_energy(sine)
    assert len(rms) > 0
    median_rms = float(np.median(rms[10:-10]))
    expected_rms = 0.5 / np.sqrt(2.0)
    assert abs(median_rms - expected_rms) < 0.02, f"Expected RMS ~{expected_rms}, got {median_rms}"


# ============================================================================
# 4. AUDIO DSP: EBU R128 NORMALIZER TESTS
# ============================================================================

def test_ebu_r128_filter_string_construction():
    """Verifies that Pass 1 and Pass 2 filter strings conform to exact FFmpeg syntax."""
    build_pass1_filter = ebu_r128_mod.build_pass1_filter
    build_pass2_filter = ebu_r128_mod.build_pass2_filter
    LoudnessStats = ebu_r128_mod.LoudnessStats

    # Pass 1
    p1 = build_pass1_filter(target_lufs=-14.0, target_lra=7.0, target_tp=-1.5, highpass_hz=40)
    assert "highpass=f=40:poles=2" in p1
    assert "loudnorm=I=-14.0:LRA=7.0:TP=-1.5:print_format=json" in p1

    # Pass 2 with stats
    stats = LoudnessStats(input_i=-22.4, input_tp=-0.3, input_lra=8.1, input_thresh=-33.0, target_offset=0.8)
    p2 = build_pass2_filter(
        stats=stats,
        target_lufs=-14.0,
        target_lra=7.0,
        target_tp=-1.5,
        highpass_hz=40,
        duration_sec=30.0,
        apply_loop_crossfade=True,
    )
    assert "highpass=f=40:poles=2" in p2
    assert "measured_I=-22.40" in p2
    assert "measured_TP=-0.30" in p2
    assert "measured_LRA=8.10" in p2
    assert "linear=true" in p2
    assert "alimiter=limit=-1.5dB:attack=5:release=50" in p2
    assert "afade=t=in:ss=0:d=0.030" in p2
    assert "afade=t=out:st=29.970:d=0.030" in p2


def test_ebu_r128_stderr_json_parser():
    """Verifies parsing of loudnorm JSON block in FFmpeg stderr."""
    parse_loudnorm_stderr_json = ebu_r128_mod.parse_loudnorm_stderr_json

    sample_stderr = """
    [Parsed_loudnorm_1 @ 0000021c3fa6c800] 
    {
        "input_i" : "-19.82",
        "input_tp" : "-0.45",
        "input_lra" : "6.70",
        "input_thresh" : "-30.12",
        "output_i" : "-14.05",
        "output_tp" : "-1.50",
        "output_lra" : "5.40",
        "output_thresh" : "-24.30",
        "normalization_type" : "dynamic",
        "target_offset" : "+0.05"
    }
    """
    stats = parse_loudnorm_stderr_json(sample_stderr)
    assert stats is not None
    assert stats.input_i == -19.82
    assert stats.input_tp == -0.45
    assert stats.input_lra == 6.70
    assert stats.input_thresh == -30.12
    assert stats.target_offset == 0.05

    assert parse_loudnorm_stderr_json("random ffmpeg output without json") is None


# ============================================================================
# 5. VIDEO TRANSCODING: ATEMPO FILTER COMPILER TESTS
# ============================================================================

def test_atempo_filter_decomposition_bounds():
    """
    Verifies that every atempo filter in the cascaded chain satisfies
    the strict FFmpeg requirement: 0.5 <= atempo <= 2.0.
    """
    build_atempo_chain = atempo_mod.build_atempo_chain

    speeds_to_test = [
        0.05, 0.1, 0.25, 0.33, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0,
        2.5, 3.0, 4.0, 5.0, 8.0, 10.0, 16.0, 32.0
    ]

    for s in speeds_to_test:
        chain = build_atempo_chain(s)
        if chain == "anull":
            assert math.isclose(s, 1.0, rel_tol=1e-5)
            continue

        filters = chain.split(",")
        product = 1.0
        for f in filters:
            assert f.startswith("atempo="), f"Invalid filter: {f}"
            val = float(f.split("=")[1])
            assert 0.5 <= val <= 2.0, f"Speed {s}: Filter {f} violated [0.5, 2.0] bounds"
            product *= val

        assert math.isclose(product, s, rel_tol=1e-3), f"Speed {s}: Chain product {product} != {s}"


def test_atempo_invalid_speed_rejection():
    """Verifies that non-positive speed multipliers raise ValueError."""
    build_atempo_chain = atempo_mod.build_atempo_chain

    with pytest.raises(ValueError):
        build_atempo_chain(0.0)

    with pytest.raises(ValueError):
        build_atempo_chain(-1.5)


def test_atempo_pts_synchronization():
    """Verifies that video PTS factor is exact reciprocal: pts_factor = 1 / speed."""
    compile_speed_filter = atempo_mod.compile_speed_filter

    for s in [0.25, 0.5, 2.0, 4.0]:
        comp = compile_speed_filter(s)
        assert math.isclose(comp.video_pts_factor, 1.0 / s, rel_tol=1e-5)
        assert f"{1.0/s:.4g}*(PTS-STARTPTS)" in comp.video_filter or f"{1.0/s:.1f}*(PTS-STARTPTS)" in comp.video_filter


def test_atempo_multi_segment_ramp():
    """Verifies compilation of multi-segment speed ramp with concatenation."""
    SpeedSegment = atempo_mod.SpeedSegment
    compile_multi_segment_speed_ramp = atempo_mod.compile_multi_segment_speed_ramp

    segments = [
        SpeedSegment(segment_id="s1", source_in_sec=0.0, source_out_sec=10.0, speed_multiplier=1.0),
        SpeedSegment(segment_id="s2", source_in_sec=10.0, source_out_sec=20.0, speed_multiplier=3.0),
        SpeedSegment(segment_id="s3", source_in_sec=20.0, source_out_sec=30.0, speed_multiplier=0.5),
    ]
    fg = compile_multi_segment_speed_ramp(segments)
    assert "[v0]" in fg and "[a0]" in fg
    assert "[v1]" in fg and "[a1]" in fg
    assert "[v2]" in fg and "[a2]" in fg
    assert "concat=n=3:v=1:a=1[vout][aout]" in fg


# ============================================================================
# 6. INGESTION HARDWARE: CANONICAL FILENAME NORMALIZER TESTS
# ============================================================================

def test_canonical_filename_token_sanitization():
    """Verifies Latin transliteration, NFKD diacritic removal, and ASCII cleanliness."""
    FilenameNormalizer = filename_mod.FilenameNormalizer

    assert FilenameNormalizer.sanitize_token("Møme & Kölsch") == "MomeKolsch"
    assert FilenameNormalizer.sanitize_token("Ørjan Nilsen") == "OrjanNilsen"
    assert FilenameNormalizer.sanitize_token("DJs From Mars (Live!)") == "DjsFromMarsLive"
    assert FilenameNormalizer.sanitize_token("Łukasz & Đorđe") == "LukaszDorde"
    assert FilenameNormalizer.sanitize_token("Subtronics // Griz") == "SubtronicsGriz"

    assert FilenameNormalizer.sanitize_token('bad<name>:test/file|?*') == "BadNameTestFile"
    assert FilenameNormalizer.sanitize_token(None, default="Fallback") == "Fallback"
    assert FilenameNormalizer.sanitize_token("", default="Fallback") == "Fallback"


def test_canonical_filename_build_and_parse():
    """Verifies round-trip build and regex parsing of canonical filenames."""
    FilenameNormalizer = filename_mod.FilenameNormalizer

    fname = FilenameNormalizer.build_canonical_filename(
        event="EDCLV",
        artist="Kölsch",
        track="Grey",
        resolution="4k",
        version=2,
        date_str="20260518",
        ext="mp4",
    )
    assert fname == "20260518_Edclv_Kolsch_Grey_V2_4k.mp4"

    parsed = FilenameNormalizer.parse_filename(fname)
    assert parsed is not None
    assert parsed["date"] == "20260518"
    assert parsed["event"] == "Edclv"
    assert parsed["artist"] == "Kolsch"
    assert parsed["track"] == "Grey"
    assert parsed["version"] == 2
    assert parsed["resolution"] == "4k"
    assert parsed["ext"] == "mp4"


def test_directory_health_guard_partitioning():
    """Verifies DirectoryHealthGuard caps folders at max_items and branches into _Batch02, etc."""
    DirectoryHealthGuard = filename_mod.DirectoryHealthGuard

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        guard = DirectoryHealthGuard(max_items=4)

        # Batch 1
        p1 = guard.get_healthy_subfolder(base, "Stage_A")
        assert p1.name == "Stage_A"
        for i in range(4):
            (p1 / f"file_{i}.mp4").touch()

        # Overflow -> Batch 02
        p2 = guard.get_healthy_subfolder(base, "Stage_A")
        assert p2.name == "Stage_A_Batch02"
        for i in range(4):
            (p2 / f"file_{i}.mp4").touch()

        # Overflow -> Batch 03
        p3 = guard.get_healthy_subfolder(base, "Stage_A")
        assert p3.name == "Stage_A_Batch03"


# ============================================================================
# 7. INGESTION HARDWARE: WIN32 3-TIER FILE LOCKER TESTS
# ============================================================================

def test_win32_file_locker_tier_1_temp_filter():
    """Verifies Tier 1 instantly rejects temporary/downloading/hidden extensions."""
    is_temporary_or_hidden = file_locker_mod.is_temporary_or_hidden
    check_file_lock = file_locker_mod.check_file_lock

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "take_01.mp4.part"
        p.write_bytes(b"temp_data")

        res = check_file_lock(p)
        assert res.is_locked is True
        assert res.tier_failed == 1
        assert res.is_ready is False

        p_hidden = Path(tmp) / ".~lock_file.mp4"
        p_hidden.write_bytes(b"temp_data")
        assert is_temporary_or_hidden(p_hidden) is True


def test_win32_file_locker_tier_2_active_writer():
    """Verifies Tier 2 detects active file handle locking when another process writes."""
    check_file_lock = file_locker_mod.check_file_lock

    with tempfile.TemporaryDirectory() as tmp:
        locked_file = Path(tmp) / "streaming_take.mp4"
        with open(locked_file, "wb") as f:
            f.write(b"ACTIVE_DATA_STREAM")
            f.flush()
            res = check_file_lock(locked_file, debounce_interval_sec=0.05)
            assert res.is_locked is True
            assert res.tier_failed in (2, 3)


def test_win32_file_locker_tier_3_zero_byte_stub():
    """Verifies Tier 3 rejects zero-byte stubs."""
    check_file_lock = file_locker_mod.check_file_lock

    with tempfile.TemporaryDirectory() as tmp:
        empty_file = Path(tmp) / "zero_byte.mp4"
        empty_file.touch()

        res = check_file_lock(empty_file, debounce_interval_sec=0.05)
        assert res.is_locked is True
        assert res.tier_failed == 3
        assert "zero bytes" in res.reason


def test_win32_file_locker_stable_file():
    """Verifies fully written, stable file passes all 3 tiers."""
    check_file_lock = file_locker_mod.check_file_lock

    with tempfile.TemporaryDirectory() as tmp:
        stable = Path(tmp) / "clean_take.mp4"
        stable.write_bytes(b"COMPLETED_DATA" * 500)

        res = check_file_lock(stable, debounce_interval_sec=0.1)
        assert res.is_locked is False
        assert res.tier_failed is None
        assert res.is_ready is True
        assert res.file_size_bytes == len(b"COMPLETED_DATA" * 500)


def test_win32_file_locker_async():
    """Verifies async check_file_lock_async execution."""
    check_file_lock_async = file_locker_mod.check_file_lock_async

    with tempfile.TemporaryDirectory() as tmp:
        stable = Path(tmp) / "clean_async.mp4"
        stable.write_bytes(b"ASYNC_BYTES" * 200)

        res = asyncio.run(check_file_lock_async(stable, debounce_interval_sec=0.1))
        assert res.is_ready is True


# ============================================================================
# 8. VIRAL INTELLIGENCE: EVPI VIRAL GRADING MODEL TESTS
# ============================================================================

def test_evpi_calculation_and_killswitches():
    """Verifies EVPI mathematical formula and non-linear killswitch dampeners."""
    calculate_evpi = evpi_mod.calculate_evpi
    compute_killswitches = evpi_mod.compute_killswitches
    classify_verdict = evpi_mod.classify_verdict
    TrendingVerdict = evpi_mod.TrendingVerdict

    # 1. Clean video in optimal duration envelope (24s)
    k_a, k_f, k_d = compute_killswitches(
        audio_clipping_detected=False, aspect_ratio="9:16", duration_seconds=24.0, safe_zone_violation=False
    )
    assert k_a == 1.0 and k_f == 1.0 and k_d == 1.0

    raw, comp = calculate_evpi(
        hook_score=90.0, retention_score=85.0, visual_score=80.0,
        coherence_score=85.0, pacing_score=80.0,
        k_audio=k_a, k_format=k_f, k_duration=k_d,
    )
    assert math.isclose(raw, 85.0, abs_tol=0.1)
    assert math.isclose(comp, 85.0, abs_tol=0.1)
    assert classify_verdict(comp) == TrendingVerdict.VIRAL_TIER_1

    # 2. Audio clipping killswitch: collapses score by 90%
    k_a_clip, _, _ = compute_killswitches(
        audio_clipping_detected=True, aspect_ratio="9:16", duration_seconds=24.0
    )
    assert k_a_clip == 0.10
    _, comp_clip = calculate_evpi(
        hook_score=90.0, retention_score=85.0, visual_score=80.0,
        coherence_score=85.0, pacing_score=80.0,
        k_audio=k_a_clip, k_format=1.0, k_duration=1.0,
    )
    assert math.isclose(comp_clip, 8.5, abs_tol=0.1)
    assert classify_verdict(comp_clip) == TrendingVerdict.LOW_REACH

    # 3. Safe zone violation killswitch: collapses score by 50%
    _, k_f_viol, _ = compute_killswitches(
        audio_clipping_detected=False, aspect_ratio="9:16", duration_seconds=24.0, safe_zone_violation=True
    )
    assert k_f_viol == 0.50


def test_evpi_pydantic_v2_model_validation():
    """Verifies ViralScoreReport Pydantic V2 schema validation and auto-calculation."""
    evaluate_video_metrics = evpi_mod.evaluate_video_metrics

    report = evaluate_video_metrics(
        video_id="edc_subtronics_take_01",
        duration_seconds=20.0,
        hook_score=88.0,
        retention_score=82.0,
        visual_score=79.0,
        coherence_score=84.0,
        pacing_score=76.0,
        aspect_ratio="9:16",
    )
    assert report.video_id == "edc_subtronics_take_01"
    assert report.trending_verdict in ("VIRAL_TIER_1", "HIGH_POTENTIAL")
    assert report.killswitch_multiplier == 1.0
    json_data = report.model_dump()
    assert "evpi_composite" in json_data
    assert "hook_metrics" in json_data


# ============================================================================
# 9. VIRAL INTELLIGENCE: SAFE ZONE & SEO AUDITOR TESTS
# ============================================================================

def test_safe_zone_geometric_collision():
    """Verifies accurate collision detection against YouTube Shorts and TikTok exclusion zones."""
    SafeZoneAuditor = safe_zone_mod.SafeZoneAuditor

    # Centered compliant box
    rep_ok = SafeZoneAuditor.audit_coordinates(x=100, y=350, width=500, height=100)
    assert rep_ok.is_compliant is True
    assert rep_ok.yt_compliant is True
    assert rep_ok.tiktok_compliant is True

    # Top hazard violation (Y < 180 on Shorts, Y < 160 on TikTok)
    rep_top = SafeZoneAuditor.audit_coordinates(x=100, y=50, width=500, height=100)
    assert rep_top.is_compliant is False
    assert rep_top.yt_compliant is False
    assert any("Top Collision" in v for v in rep_top.yt_violations)

    # Right rail collision (X2 > 960 px)
    rep_right = SafeZoneAuditor.audit_coordinates(x=900, y=500, width=150, height=100)
    assert rep_right.is_compliant is False
    assert rep_right.yt_compliant is False
    assert any("Right Rail Collision" in v for v in rep_right.yt_violations)


def test_safe_zone_seo_hashtag_clustering():
    """Verifies 5-7 hashtag clustering formula across various genres."""
    SEOPackager = safe_zone_mod.SEOPackager

    for g in ["house", "techno", "dubstep", "melodic", "dnb", "trance", "edm"]:
        tags = SEOPackager.generate_hashtag_cluster(
            artist="Subtronics", event="Lost Lands", genre=g, year=2026
        )
        assert 5 <= len(tags) <= 7, f"Genre {g}: Expected 5-7 tags, got {len(tags)}"
        assert "#EDM" in tags
        assert "#Subtronics" in tags


def test_safe_zone_17_keyword_spam_filter():
    """Verifies 17-keyword comment spam filter catches all target abuse vectors."""
    CommentSpamAuditor = safe_zone_mod.CommentSpamAuditor
    CANONICAL_17_SPAM_KEYWORDS = safe_zone_mod.CANONICAL_17_SPAM_KEYWORDS

    auditor = CommentSpamAuditor()

    for kw in CANONICAL_17_SPAM_KEYWORDS:
        test_comment = f"Hey great set, visit {kw} right now!"
        is_spam, matches = auditor.check_comment(test_comment)
        assert is_spam is True, f"Failed to detect spam keyword: '{kw}'"

    clean_comment = "This laser synchronization with the 60Hz drop was completely mindblowing! 🔥"
    is_spam, matches = auditor.check_comment(clean_comment)
    assert is_spam is False
    assert len(matches) == 0


# ============================================================================
# 10. ADDITIONAL VAULT MODULES TESTS
# ============================================================================

def test_lossless_encoding_profiles_registry():
    """Verifies lossless encoding profile registration and parameter extraction."""
    get_profile = profiles_mod.get_profile
    list_available_profiles = profiles_mod.list_available_profiles

    profiles = list_available_profiles()
    assert "x264_crf17" in profiles
    assert "hevc_nvenc" in profiles
    assert "prores_hq" in profiles

    p_x264 = get_profile("x264_crf17")
    assert p_x264.video_codec == "libx264"
    assert p_x264.crf == 17


def test_youtube_content_id_guard_dry_run():
    """Verifies YouTube Content ID guard dry-run pipeline."""
    YouTubeContentIDGuard = content_id_mod.YouTubeContentIDGuard

    guard = YouTubeContentIDGuard(dry_run=True)
    res = guard.publish_with_preflight_guard(
        video_path="test_clip.mp4",
        title="Test Shorts",
        description="Test description",
        auto_promote_if_clean=True,
    )
    assert res.verdict.value == "UNLISTED_CLEARED"
    assert res.final_privacy == "public"
    assert res.action_taken.value == "PROMOTED_TO_PUBLIC"
    assert res.is_quarantined is False


def test_samsung_adb_ingestor_mock():
    """Verifies Samsung ADB Ingestor with mock command executor."""
    SamsungAdbIngestor = adb_mod.SamsungAdbIngestor
    import hashlib
    import subprocess

    mock_data = b"MOCK_4K_VIDEO_STREAM"
    mock_hash = hashlib.sha256(mock_data).hexdigest().lower()

    def mock_cmd(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
        cmd_s = " ".join(cmd)
        if "connect" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="connected\n", stderr="")
        if "get-state" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="device\n", stderr="")
        if "rampart_auto_enabled_switch_enabled" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if "sha256sum" in cmd_s:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{mock_hash}  /remote.mp4\n", stderr="")
        if "pull" in cmd:
            dest = cmd[-1]
            with open(dest, "wb") as f:
                f.write(mock_data)
            return subprocess.CompletedProcess(cmd, 0, stdout="pulled\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as tmp:
        ingestor = SamsungAdbIngestor(
            device_ip="192.168.1.100",
            staging_dir=tmp,
            command_executor=mock_cmd,
        )
        assert ingestor.connect() is True
        rep = ingestor.pull_media_verified("/remote.mp4")
        assert rep.verified is True
        assert rep.local_sha256 == mock_hash


def test_http_range_video_streamer_range_parser():
    """Verifies RFC 7233 byte-range header parsing in http_range_video_streamer."""
    parse_byte_range = streamer_mod.parse_byte_range

    total_size = 5000
    assert parse_byte_range("bytes=0-999", total_size) == (0, 999)
    assert parse_byte_range("bytes=2000-", total_size) == (2000, 4999)
    assert parse_byte_range("bytes=-500", total_size) == (4500, 4999)


def test_resolve_timeline_builder_dry_run():
    """Verifies frame-accurate calculation and dry-run timeline assembly in resolve_timeline_builder."""
    ResolveTimelineBuilder = timeline_mod.ResolveTimelineBuilder
    SubclipSpec = timeline_mod.SubclipSpec

    builder = ResolveTimelineBuilder(dry_run=True, default_fps=60.0)
    subclips = [
        SubclipSpec(source_path="take_01.mp4", start_time_sec=5.0, end_time_sec=15.0, clip_type="A-Roll"),
        SubclipSpec(source_path="take_02.mp4", start_time_sec=10.0, end_time_sec=20.0, clip_type="B-Roll"),
    ]
    res = builder.build_subclip_timeline(
        project_name="EDM_Festival",
        timeline_base_name="Master_Cut",
        subclips=subclips,
    )
    assert res.success is True
    assert res.total_frames == 1200
    assert len(res.clip_details) == 2
