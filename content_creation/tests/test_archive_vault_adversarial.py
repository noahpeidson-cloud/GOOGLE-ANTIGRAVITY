"""
Adversarial Stress Test Harness & Boundary Condition Probing
Target: `d:\\GOOGLE ANTIGRAVITY\\content_creation\\_archive_vault`
Empirical Challenger Verification
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, List

import numpy as np
import pytest

VAULT_DIR = Path(r"d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault").resolve()

def load_vault_module(relative_path: str, module_name: str):
    full_path = VAULT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(module_name, full_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod

adv_edm_drop = load_vault_module("audio_dsp/edm_drop_detector.py", "adv_edm_drop")
adv_ebu_normalizer = load_vault_module("audio_dsp/ebu_r128_normalizer.py", "adv_ebu_normalizer")
adv_atempo = load_vault_module("video_transcoding/atempo_filter_compiler.py", "adv_atempo")
adv_filename = load_vault_module("ingestion_hardware/canonical_filename_normalizer.py", "adv_filename")
adv_file_locker = load_vault_module("ingestion_hardware/win32_three_tier_file_locker.py", "adv_file_locker")
adv_evpi = load_vault_module("viral_intelligence/evpi_viral_grading_model.py", "adv_evpi")
adv_safe_zone = load_vault_module("viral_intelligence/safe_zone_seo_auditor.py", "adv_safe_zone")


# ============================================================================
# 1. ADVERSARIAL AUDIO DSP TESTS
# ============================================================================

def test_adversarial_drop_detector_nonexistent_file():
    """Assault: Passing non-existent path must raise FileNotFoundError."""
    detector = adv_edm_drop.AudioDropDetector()
    with pytest.raises(FileNotFoundError):
        detector.extract_audio_buffer("Z:\\ghost_drive\\nonexistent_take_000.mp4")


def test_adversarial_drop_detector_negative_or_extreme_manual_bounds():
    """Assault: Passing negative manual start time or excessive duration."""
    detector = adv_edm_drop.AudioDropDetector(target_duration_sec=30.0)
    # Manual duration > 59.0s should be clamped to 59.0s (VIDEO_DURATION_MAX_SECONDS)
    res = detector.detect_optimal_drop(
        np.zeros(100, dtype=np.float32),
        manual_start_time=-5.0,
        manual_duration=120.0,
    )
    assert res.is_manual_override is True
    assert res.start_time_sec == -5.0
    assert res.duration_sec == 59.0  # Clamped to maximum short-form boundary


def test_adversarial_drop_detector_nan_inf_resilience():
    """Assault: Audio signal containing NaNs and Infs."""
    detector = adv_edm_drop.AudioDropDetector(target_duration_sec=10.0)
    dirty_signal = np.ones(22050 * 20, dtype=np.float32)
    dirty_signal[100:200] = np.nan
    dirty_signal[300:400] = np.inf

    # calculate_rms_energy on dirty signal
    rms, _ = detector.calculate_rms_energy(dirty_signal)
    assert len(rms) > 0


# ============================================================================
# 2. ADVERSARIAL ATEMPO COMPILER TESTS
# ============================================================================

def test_adversarial_atempo_extreme_slowmo():
    """Assault: Extreme slow-motion (0.01x) decomposition."""
    chain = adv_atempo.build_atempo_chain(0.01)
    filters = chain.split(",")
    # 0.01 requires 0.5^7 = 0.0078125 or 0.5^6 = 0.015625
    assert len(filters) >= 6
    product = 1.0
    for f in filters:
        val = float(f.split("=")[1])
        assert 0.5 <= val <= 2.0
        product *= val
    assert math.isclose(product, 0.01, rel_tol=1e-3)


def test_adversarial_atempo_extreme_timelapse():
    """Assault: Extreme fast-motion (128.0x) decomposition."""
    chain = adv_atempo.build_atempo_chain(128.0)
    filters = chain.split(",")
    # 2.0^7 = 128.0 -> exactly 7 filters of atempo=2.0
    assert len(filters) == 7
    for f in filters:
        assert f == "atempo=2.0"


def test_adversarial_atempo_empty_segments_rejection():
    """Assault: Passing empty segment list to multi_segment compiler."""
    with pytest.raises(ValueError):
        adv_atempo.compile_multi_segment_speed_ramp([])


# ============================================================================
# 3. ADVERSARIAL FILENAME & DIRECTORY TESTS
# ============================================================================

def test_adversarial_filename_emoji_and_symbol_bomb():
    """Assault: Unicode emoji and pure symbol inputs."""
    Normalizer = adv_filename.FilenameNormalizer

    # Emoji bomb
    clean = Normalizer.sanitize_token("🛸 Subtronics 🔥 (VIP Edit) 🤯")
    assert clean == "SubtronicsVipEdit"

    # Pure symbol bomb -> fallback
    clean_sym = Normalizer.sanitize_token("??? /// < > : |", default="FallbackToken")
    assert clean_sym == "FallbackToken"

    # Extreme whitespace and control chars
    clean_ctrl = Normalizer.sanitize_token("\t\n  John \r\n Summit  \x00")
    assert clean_ctrl == "JohnSummit"


def test_adversarial_directory_partition_cascade():
    """Assault: Forcing DirectoryHealthGuard to branch through 10 batch folders."""
    DirectoryHealthGuard = adv_filename.DirectoryHealthGuard

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        guard = DirectoryHealthGuard(max_items=2)

        # Fill 10 successive batches
        folders = []
        for b in range(10):
            folder = guard.get_healthy_subfolder(base, "Overflow_Test")
            folders.append(folder.name)
            (folder / "file_1.mp4").touch()
            (folder / "file_2.mp4").touch()

        assert folders[0] == "Overflow_Test"
        assert folders[1] == "Overflow_Test_Batch02"
        assert folders[9] == "Overflow_Test_Batch10"


# ============================================================================
# 4. ADVERSARIAL WIN32 FILE LOCKER TESTS
# ============================================================================

def test_adversarial_file_locker_nonexistent_and_timeout():
    """Assault: Locking tests against missing file and timeout handling."""
    # Missing file
    res = adv_file_locker.check_file_lock("Z:\\nonexistent\\missing.mp4")
    assert res.is_locked is True
    assert res.tier_failed == 1
    assert "does not exist" in res.reason

    # Timeout check
    unlocked = adv_file_locker.wait_for_file_lock_release(
        "Z:\\nonexistent\\missing.mp4", timeout_sec=0.1, poll_interval_sec=0.05
    )
    assert unlocked is False


# ============================================================================
# 5. ADVERSARIAL EVPI VIRAL GRADING TESTS
# ============================================================================

def test_adversarial_evpi_boundary_zero_and_hundred():
    """Assault: All zeros and all hundred boundary tests."""
    calc = adv_evpi.calculate_evpi

    # All zeros
    raw_0, comp_0 = calc(0.0, 0.0, 0.0, 0.0, 0.0)
    assert raw_0 == 0.0 and comp_0 == 0.0
    assert adv_evpi.classify_verdict(comp_0) == adv_evpi.TrendingVerdict.LOW_REACH

    # All 100s
    raw_100, comp_100 = calc(100.0, 100.0, 100.0, 100.0, 100.0)
    assert raw_100 == 100.0 and comp_100 == 100.0
    assert adv_evpi.classify_verdict(comp_100) == adv_evpi.TrendingVerdict.VIRAL_TIER_1


def test_adversarial_evpi_duration_killswitch_extremes():
    """Assault: Duration extremes (<8s and >60s)."""
    compute = adv_evpi.compute_killswitches

    # 4-second video
    _, _, k_d_short = compute(False, "9:16", duration_seconds=4.0)
    assert k_d_short == 0.40

    # 120-second video
    _, _, k_d_long = compute(False, "9:16", duration_seconds=120.0)
    assert k_d_long == 0.40

    # Optimal 25-second video
    _, _, k_d_opt = compute(False, "9:16", duration_seconds=25.0)
    assert k_d_opt == 1.00


def test_adversarial_evpi_unusual_aspect_ratios():
    """Assault: Non-standard aspect ratios like 16:9, 21:9, 4:3."""
    compute = adv_evpi.compute_killswitches

    _, k_f_wide, _ = compute(False, "16:9", 25.0)
    assert k_f_wide == 0.50

    _, k_f_square, _ = compute(False, "1:1", 25.0)
    assert k_f_square == 0.85

    _, k_f_weird, _ = compute(False, "32:9", 25.0)
    assert k_f_weird == 0.50


# ============================================================================
# 6. ADVERSARIAL SAFE ZONE & SPAM TESTS
# ============================================================================

def test_adversarial_safe_zone_huge_box_and_negative_coords():
    """Assault: Overlay box spanning beyond canvas and negative coordinates."""
    Auditor = adv_safe_zone.SafeZoneAuditor

    # Giant overlay covering entire canvas
    rep_huge = Auditor.audit_coordinates(x=0, y=0, width=1080, height=1920)
    assert rep_huge.is_compliant is False
    assert len(rep_huge.yt_violations) == 4  # Top, bottom, left, right all fail
    assert len(rep_huge.tiktok_violations) == 4

    # Negative coordinates
    rep_neg = Auditor.audit_coordinates(x=-100, y=-50, width=200, height=100)
    assert rep_neg.is_compliant is False


def test_adversarial_spam_filter_casing_and_separators():
    """Assault: Spam evasions with casing, spaces, underscores, and dots."""
    auditor = adv_safe_zone.CommentSpamAuditor()

    # Uppercase
    assert auditor.check_comment("JOIN MY TELEGRAM GROUP")[0] is True
    # Punctuation / separators: check.bio, check_bio, check-bio
    assert auditor.check_comment("free tickets check.bio now")[0] is True
    assert auditor.check_comment("free download click_here")[0] is True
    assert auditor.check_comment("buy_tickets online fast")[0] is True
    assert auditor.check_comment("dm_to_promote on insta")[0] is True
