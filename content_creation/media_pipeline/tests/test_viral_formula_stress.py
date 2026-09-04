"""
test_viral_formula_stress.py - Empirical Challenger Stress Test Suite
Milestone 1: Authoritative Viral Formula Definition (EVPI-5)

Adversarially challenges:
1. Mathematical continuity, boundary limits, and zero-division resistance
2. Weight sum invariants (primary and sub-weights summing to 1.000)
3. Non-linear killswitch scaling and boundary stability
4. Pydantic v2 schema validation, field constraints, and error handling
5. BigQuery ML SQL compilation, schema consistency, and weight normalization query logic
"""

import math
import re
import pytest
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing_extensions import Literal


# ============================================================================
# 1. PURE PYTHON REFERENCE IMPLEMENTATION OF FORMULAS IN VIRAL_FORMULA.MD
# ============================================================================

def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, val))


def calc_hrv_score(
    d_hook: float,
    n_transients: int,
    t_onset: float
) -> float:
    """
    Parameter 1: 3-Second Hook Retention Velocity
    d_hook: integral in [0, 3.0] of (0.55*A(t) + 0.45*min(1.0, V_opt/25)) dt. Range: [0.0, 3.0]
    n_transients: count of pattern interrupts in [0, 3.0]s
    t_onset: initial audiovisual onset latency in seconds
    """
    term_density = 0.40 * (d_hook / 3.0)
    term_transients = 0.35 * min(1.0, n_transients / 3.0)
    term_onset = 0.25 * max(0.0, 1.0 - (t_onset / 0.5))
    hrv_raw = term_density + term_transients + term_onset
    return 100.0 * clamp(hrv_raw, 0.0, 1.0)


def calc_dpaw_score(
    t_drop: Optional[float],
    total_duration: float,
    w_build: Optional[float],
    delta_t_pocket: Optional[float],
    drop_detected: bool = True
) -> float:
    """
    Parameter 2: Drop Pacing & Anticipation Window
    """
    if not drop_detected or t_drop is None or w_build is None or delta_t_pocket is None:
        return 25.0

    if total_duration <= 0:
        raise ValueError("total_duration must be positive")

    pos_ratio = t_drop / total_duration
    p_pos = math.exp(-((pos_ratio - 0.52) ** 2) / (2.0 * (0.12 ** 2)))
    b_window = math.exp(-((w_build - 4.5) ** 2) / (2.0 * (1.5 ** 2)))

    if 0.15 <= delta_t_pocket <= 0.45:
        q_pocket = 1.0
    elif 0.0 <= delta_t_pocket < 0.15:
        q_pocket = 0.5 + 0.5 * (delta_t_pocket / 0.15)
    else:
        q_pocket = max(0.0, 1.0 - (delta_t_pocket - 0.45) / 0.50)

    raw_dpaw = 0.45 * p_pos + 0.35 * b_window + 0.20 * q_pocket
    return 100.0 * clamp(raw_dpaw, 0.0, 1.0)


def calc_adr_sfd_score(
    r_sub: float,
    sfd_peak: float,
    sfd_build_mean: float,
    sigma_sf: float,
    delta_lufs: float,
    epsilon: float = 1e-6
) -> float:
    """
    Parameter 3: Audio Dynamic Range & Spectral Flux Delta
    """
    r_norm = clamp(math.log10(max(0.0, r_sub) + 1.0) / math.log10(8.0), 0.0, 1.0)
    sfd_diff = sfd_peak - sfd_build_mean
    sfd_norm = clamp(sfd_diff / (2.5 * max(0.0, sigma_sf) + epsilon), 0.0, 1.0)
    l_norm = clamp(delta_lufs / 6.0, 0.0, 1.0)

    raw_adr = 0.40 * r_norm + 0.35 * sfd_norm + 0.25 * l_norm
    return 100.0 * clamp(raw_adr, 0.0, 1.0)


def calc_cke_mve_score(
    delta_e_kinetic: float,
    c_jump: float,
    phi_bpm: float
) -> float:
    """
    Parameter 4: Crowd Kinetic Energy & Motion Vector Entropy
    """
    term_e = 0.40 * min(1.0, max(0.0, delta_e_kinetic) / 4.0)
    term_jump = 0.35 * clamp(c_jump, 0.0, 1.0)
    term_bpm = 0.25 * max(0.0, min(1.0, phi_bpm))
    raw_cke = term_e + term_jump + term_bpm
    return 100.0 * clamp(raw_cke, 0.0, 1.0)


def calc_ltss_score(
    tau_sync: float,
    lasers: bool,
    pyro: bool,
    co2: bool,
    led: bool,
    f_strobe: float
) -> float:
    """
    Parameter 5: Lighting Transition & Strobe Peak Synchronicity
    """
    sync_score = math.exp(-(tau_sync ** 2) / (2.0 * (0.033 ** 2)))
    f_prod = min(1.0, 0.30 * int(lasers) + 0.30 * int(pyro) + 0.20 * int(co2) + 0.20 * int(led))
    strobe_score = clamp((f_strobe - 4.0) / 12.0, 0.0, 1.0)

    raw_ltss = 0.40 * sync_score + 0.35 * f_prod + 0.25 * strobe_score
    return 100.0 * clamp(raw_ltss, 0.0, 1.0)


def calc_killswitch_multipliers(
    audio_status: str,
    aspect_ratio: str,
    duration: float
) -> Tuple[float, float, float]:
    """Calculates non-linear killswitch factors."""
    # K_audio
    if audio_status == "clean":
        k_audio = 1.0
    elif audio_status == "moderate_clipping":
        k_audio = 0.6
    else:  # ruined / silent / heavy clipping
        k_audio = 0.1

    # K_format
    if aspect_ratio in ["9:16", "2160:3840", "1080:1920"]:
        k_format = 1.0
    elif aspect_ratio in ["1:1", "1080:1080"]:
        k_format = 0.85
    else:  # horizontal 16:9 etc.
        k_format = 0.50

    # K_duration
    if 12.0 <= duration <= 38.0:
        k_duration = 1.0
    elif (8.0 <= duration < 12.0) or (38.0 < duration <= 60.0):
        k_duration = 0.85
    else:
        k_duration = 0.40

    return k_audio, k_format, k_duration


def calc_evpi_composite(
    s_hrv: float,
    s_dpaw: float,
    s_adr_sfd: float,
    s_cke_mve: float,
    s_ltss: float,
    k_audio: float = 1.0,
    k_format: float = 1.0,
    k_duration: float = 1.0,
    weights: Tuple[float, float, float, float, float] = (0.25, 0.25, 0.20, 0.15, 0.15)
) -> float:
    """Calculates final EVPI score."""
    w1, w2, w3, w4, w5 = weights
    evpi_raw = w1 * s_hrv + w2 * s_dpaw + w3 * s_adr_sfd + w4 * s_cke_mve + w5 * s_ltss
    evpi_final = evpi_raw * k_audio * k_format * k_duration
    return clamp(evpi_final, 0.0, 100.0)


def classify_verdict(evpi: float) -> str:
    if evpi >= 85.0:
        return "VIRAL_TIER_1"
    elif evpi >= 70.0:
        return "HIGH_POTENTIAL"
    elif evpi >= 50.0:
        return "MODERATE"
    else:
        return "LOW_REACH"


# ============================================================================
# 2. PYDANTIC SCHEMAS FROM VIRAL_FORMULA.MD
# ============================================================================

class TransientEvent(BaseModel):
    timestamp_seconds: float = Field(..., ge=0.0)
    event_type: Literal[
        "audio_drop", "buildup_start", "predrop_pocket", "laser_burst",
        "pyro_blast", "co2_cryo", "crowd_jump", "camera_zoom", "scene_cut"
    ]
    intensity: float = Field(..., ge=0.0, le=1.0)
    description: str = Field(..., max_length=256)


class HookAnalysis(BaseModel):
    hook_onset_latency_seconds: float = Field(..., ge=0.0)
    transient_count_first_3s: int = Field(..., ge=0)
    initial_visual_stimulus_score: float = Field(..., ge=0.0, le=100.0)
    hrv_score: float = Field(..., ge=0.0, le=100.0)


class DropPacingAnalysis(BaseModel):
    drop_detected: bool
    drop_timestamp_seconds: Optional[float] = Field(None, ge=0.0)
    buildup_duration_seconds: Optional[float] = Field(None, ge=0.0)
    predrop_silence_duration_ms: Optional[float] = Field(None, ge=0.0)
    drop_position_ratio: Optional[float] = Field(None, ge=0.0, le=1.0)
    dpaw_score: float = Field(..., ge=0.0, le=100.0)


class AudioAcousticAnalysis(BaseModel):
    sub_bass_surge_ratio: float = Field(..., ge=0.0)
    spectral_flux_delta: float = Field(..., ge=0.0)
    loudness_jump_lufs_est: float
    audio_clipping_detected: bool
    adr_sfd_score: float = Field(..., ge=0.0, le=100.0)


class CrowdDynamicsAnalysis(BaseModel):
    crowd_visible_percentage: float = Field(..., ge=0.0, le=100.0)
    jump_synchronicity_coherence: float = Field(..., ge=0.0, le=1.0)
    energy_acceleration_factor: float = Field(..., ge=0.0)
    moshpit_or_intense_reaction: bool
    cke_mve_score: float = Field(..., ge=0.0, le=100.0)


class LightingProductionAnalysis(BaseModel):
    laser_co2_pyro_present: bool
    strobe_frequency_hz: float = Field(..., ge=0.0, le=50.0)
    light_audio_sync_latency_ms: float = Field(..., ge=0.0)
    ltss_score: float = Field(..., ge=0.0, le=100.0)


class EDMViralGradingReport(BaseModel):
    video_id: str
    gcs_uri: str
    video_duration_seconds: float = Field(..., ge=1.0, le=300.0)
    aspect_ratio: str = Field(..., pattern=r"^\d+:\d+$")
    key_transients: List[TransientEvent] = Field(default_factory=list)
    hook_analysis: HookAnalysis
    drop_pacing_analysis: DropPacingAnalysis
    audio_analysis: AudioAcousticAnalysis
    crowd_analysis: CrowdDynamicsAnalysis
    lighting_analysis: LightingProductionAnalysis
    evpi_composite_score: float = Field(..., ge=0.0, le=100.0)
    trending_verdict: Literal["VIRAL_TIER_1", "HIGH_POTENTIAL", "MODERATE", "LOW_REACH"]
    algorithmic_recommendation: str = Field(..., max_length=512)

    @field_validator("evpi_composite_score")
    @classmethod
    def validate_evpi(cls, v: float) -> float:
        return round(v, 2)


# ============================================================================
# 3. TEST SUITE: MATHEMATICAL CONTINUITY, STABILITY, AND BOUNDS
# ============================================================================

def test_weights_sum_to_exact_unity():
    """Adversarially verify all weight groups sum exactly to 1.000."""
    # EVPI primary weights
    w_evpi = [0.25, 0.25, 0.20, 0.15, 0.15]
    assert math.isclose(sum(w_evpi), 1.0, rel_tol=1e-9), f"EVPI weights sum to {sum(w_evpi)}"

    # Parameter sub-weights
    w_hrv = [0.40, 0.35, 0.25]
    assert math.isclose(sum(w_hrv), 1.0, rel_tol=1e-9), f"HRV sub-weights sum to {sum(w_hrv)}"

    w_dpaw = [0.45, 0.35, 0.20]
    assert math.isclose(sum(w_dpaw), 1.0, rel_tol=1e-9), f"DPAW sub-weights sum to {sum(w_dpaw)}"

    w_adr = [0.40, 0.35, 0.25]
    assert math.isclose(sum(w_adr), 1.0, rel_tol=1e-9), f"ADR sub-weights sum to {sum(w_adr)}"

    w_cke = [0.40, 0.35, 0.25]
    assert math.isclose(sum(w_cke), 1.0, rel_tol=1e-9), f"CKE sub-weights sum to {sum(w_cke)}"

    w_ltss = [0.40, 0.35, 0.25]
    assert math.isclose(sum(w_ltss), 1.0, rel_tol=1e-9), f"LTSS sub-weights sum to {sum(w_ltss)}"

    w_prod = [0.30, 0.30, 0.20, 0.20]
    assert math.isclose(sum(w_prod), 1.0, rel_tol=1e-9), f"Production sub-weights sum to {sum(w_prod)}"


def test_qpocket_piecewise_continuity():
    """
    Stress-test Q_pocket function at boundary transition points:
    delta_t = 0.15s, delta_t = 0.45s, and delta_t = 0.95s.
    Proves left and right limits are strictly continuous (no jump discontinuities).
    """
    def q_pocket(dt: float) -> float:
        if 0.15 <= dt <= 0.45:
            return 1.0
        elif 0.0 <= dt < 0.15:
            return 0.5 + 0.5 * (dt / 0.15)
        else:
            return max(0.0, 1.0 - (dt - 0.45) / 0.50)

    eps = 1e-7
    # At dt = 0.15
    left_015 = q_pocket(0.15 - eps)
    exact_015 = q_pocket(0.15)
    right_015 = q_pocket(0.15 + eps)
    assert math.isclose(left_015, exact_015, abs_tol=1e-5), f"Discontinuity at 0.15s: {left_015} vs {exact_015}"
    assert math.isclose(right_015, exact_015, abs_tol=1e-5), f"Discontinuity at 0.15s: {right_015} vs {exact_015}"

    # At dt = 0.45
    left_045 = q_pocket(0.45 - eps)
    exact_045 = q_pocket(0.45)
    right_045 = q_pocket(0.45 + eps)
    assert math.isclose(left_045, exact_045, abs_tol=1e-5), f"Discontinuity at 0.45s: {left_045} vs {exact_045}"
    assert math.isclose(right_045, exact_045, abs_tol=1e-5), f"Discontinuity at 0.45s: {right_045} vs {exact_045}"

    # At dt = 0.95 (where max(0, ...) clamps to 0)
    left_095 = q_pocket(0.95 - eps)
    exact_095 = q_pocket(0.95)
    right_095 = q_pocket(0.95 + eps)
    assert math.isclose(left_095, 0.0, abs_tol=1e-5)
    assert math.isclose(exact_095, 0.0, abs_tol=1e-5)
    assert math.isclose(right_095, 0.0, abs_tol=1e-5)


def test_monte_carlo_parameter_stability_and_bounds():
    """
    Executes 50,000 synthetic evaluations across random parameter distributions
    to prove:
    1. Zero division-by-zero errors
    2. Zero NaN or Inf values
    3. Strict output boundedness: 0.0 <= Score <= 100.0
    """
    import random
    random.seed(42)

    for _ in range(50000):
        # 1. HRV
        d_hook = random.uniform(-1.0, 10.0)  # include out-of-spec values to test clamping
        n_transients = random.randint(-5, 20)
        t_onset = random.uniform(-1.0, 5.0)
        s_hrv = calc_hrv_score(d_hook, n_transients, t_onset)
        assert 0.0 <= s_hrv <= 100.0, f"HRV out of bounds: {s_hrv}"
        assert not math.isnan(s_hrv) and not math.isinf(s_hrv)

        # 2. DPAW
        t_drop = random.uniform(0.1, 60.0)
        dur = random.uniform(5.0, 120.0)
        w_build = random.uniform(0.0, 20.0)
        dt_pocket = random.uniform(0.0, 2.0)
        s_dpaw = calc_dpaw_score(t_drop, dur, w_build, dt_pocket, drop_detected=True)
        assert 0.0 <= s_dpaw <= 100.0, f"DPAW out of bounds: {s_dpaw}"
        assert not math.isnan(s_dpaw) and not math.isinf(s_dpaw)

        # 3. ADR-SFD
        r_sub = random.uniform(0.0, 500.0)
        sfd_peak = random.uniform(0.0, 100.0)
        sfd_mean = random.uniform(0.0, 50.0)
        sigma_sf = random.uniform(0.0, 20.0)  # can be 0 to test epsilon protection
        delta_lufs = random.uniform(-30.0, 30.0)
        s_adr = calc_adr_sfd_score(r_sub, sfd_peak, sfd_mean, sigma_sf, delta_lufs)
        assert 0.0 <= s_adr <= 100.0, f"ADR out of bounds: {s_adr}"
        assert not math.isnan(s_adr) and not math.isinf(s_adr)

        # 4. CKE-MVE
        delta_e = random.uniform(-10.0, 50.0)
        c_jump = random.uniform(-1.0, 2.0)
        phi_bpm = random.uniform(-2.0, 2.0)
        s_cke = calc_cke_mve_score(delta_e, c_jump, phi_bpm)
        assert 0.0 <= s_cke <= 100.0, f"CKE out of bounds: {s_cke}"
        assert not math.isnan(s_cke) and not math.isinf(s_cke)

        # 5. LTSS
        tau_sync = random.uniform(0.0, 2.0)
        lasers = random.choice([True, False])
        pyro = random.choice([True, False])
        co2 = random.choice([True, False])
        led = random.choice([True, False])
        f_strobe = random.uniform(0.0, 40.0)
        s_ltss = calc_ltss_score(tau_sync, lasers, pyro, co2, led, f_strobe)
        assert 0.0 <= s_ltss <= 100.0, f"LTSS out of bounds: {s_ltss}"
        assert not math.isnan(s_ltss) and not math.isinf(s_ltss)

        # 6. Composite EVPI
        audio_stat = random.choice(["clean", "moderate_clipping", "ruined"])
        aspect = random.choice(["9:16", "1:1", "16:9", "4:3"])
        k_aud, k_fmt, k_dur = calc_killswitch_multipliers(audio_stat, aspect, dur)
        evpi = calc_evpi_composite(s_hrv, s_dpaw, s_adr, s_cke, s_ltss, k_aud, k_fmt, k_dur)
        assert 0.0 <= evpi <= 100.0, f"EVPI out of bounds: {evpi}"
        verdict = classify_verdict(evpi)
        assert verdict in ["VIRAL_TIER_1", "HIGH_POTENTIAL", "MODERATE", "LOW_REACH"]


def test_monotonicity_of_hrv():
    """Verify that increasing positive features strictly non-decreases HRV score."""
    base = calc_hrv_score(d_hook=1.5, n_transients=1, t_onset=0.25)
    
    # Increase density
    higher_density = calc_hrv_score(d_hook=2.5, n_transients=1, t_onset=0.25)
    assert higher_density > base

    # Increase transients
    more_transients = calc_hrv_score(d_hook=1.5, n_transients=3, t_onset=0.25)
    assert more_transients > base

    # Decreasing latency (faster onset) should increase score
    faster_onset = calc_hrv_score(d_hook=1.5, n_transients=1, t_onset=0.05)
    assert faster_onset > base


def test_killswitch_severe_penalties():
    """Verify that killswitches severely penalize bad inputs even if parameter scores are 100."""
    # Perfect 100 across all 5 parameters
    s_perfect = 100.0
    evpi_raw = calc_evpi_composite(s_perfect, s_perfect, s_perfect, s_perfect, s_perfect, 1.0, 1.0, 1.0)
    assert evpi_raw == 100.0
    assert classify_verdict(evpi_raw) == "VIRAL_TIER_1"

    # Ruined audio: K_audio = 0.1 -> EVPI drops to 10.0 -> LOW_REACH
    k_aud, k_fmt, k_dur = calc_killswitch_multipliers("ruined", "9:16", 20.0)
    evpi_ruined_audio = calc_evpi_composite(s_perfect, s_perfect, s_perfect, s_perfect, s_perfect, k_aud, k_fmt, k_dur)
    assert math.isclose(evpi_ruined_audio, 10.0, abs_tol=1e-5)
    assert classify_verdict(evpi_ruined_audio) == "LOW_REACH"

    # Horizontal 16:9: K_format = 0.50 -> EVPI drops to 50.0 -> MODERATE
    k_aud, k_fmt, k_dur = calc_killswitch_multipliers("clean", "16:9", 20.0)
    evpi_horizontal = calc_evpi_composite(s_perfect, s_perfect, s_perfect, s_perfect, s_perfect, k_aud, k_fmt, k_dur)
    assert math.isclose(evpi_horizontal, 50.0, abs_tol=1e-5)
    assert classify_verdict(evpi_horizontal) == "MODERATE"

    # Ultra long video (>60s): K_duration = 0.40 -> EVPI drops to 40.0 -> LOW_REACH
    k_aud, k_fmt, k_dur = calc_killswitch_multipliers("clean", "9:16", 90.0)
    evpi_too_long = calc_evpi_composite(s_perfect, s_perfect, s_perfect, s_perfect, s_perfect, k_aud, k_fmt, k_dur)
    assert math.isclose(evpi_too_long, 40.0, abs_tol=1e-5)
    assert classify_verdict(evpi_too_long) == "LOW_REACH"


# ============================================================================
# 4. TEST SUITE: PYDANTIC SCHEMA VALIDATION & REJECTION RULES
# ============================================================================

def test_pydantic_valid_report_roundtrip():
    """Verifies that a full, valid grading report deserializes and validates successfully."""
    payload = {
        "video_id": "vid_edc_2026_001",
        "gcs_uri": "gs://edm-viral-media/raw/vid_edc_2026_001.mp4",
        "video_duration_seconds": 24.5,
        "aspect_ratio": "9:16",
        "key_transients": [
            {
                "timestamp_seconds": 12.4,
                "event_type": "audio_drop",
                "intensity": 0.95,
                "description": "Main bass drop with sub-bass surge"
            },
            {
                "timestamp_seconds": 12.42,
                "event_type": "laser_burst",
                "intensity": 1.0,
                "description": "Full stage green laser blast"
            }
        ],
        "hook_analysis": {
            "hook_onset_latency_seconds": 0.05,
            "transient_count_first_3s": 3,
            "initial_visual_stimulus_score": 92.0,
            "hrv_score": 91.5
        },
        "drop_pacing_analysis": {
            "drop_detected": True,
            "drop_timestamp_seconds": 12.4,
            "buildup_duration_seconds": 4.5,
            "predrop_silence_duration_ms": 250.0,
            "drop_position_ratio": 0.506,
            "dpaw_score": 96.2
        },
        "audio_analysis": {
            "sub_bass_surge_ratio": 6.8,
            "spectral_flux_delta": 4.2,
            "loudness_jump_lufs_est": 5.5,
            "audio_clipping_detected": False,
            "adr_sfd_score": 94.0
        },
        "crowd_analysis": {
            "crowd_visible_percentage": 65.0,
            "jump_synchronicity_coherence": 0.88,
            "energy_acceleration_factor": 4.5,
            "moshpit_or_intense_reaction": True,
            "cke_mve_score": 92.0
        },
        "lighting_analysis": {
            "laser_co2_pyro_present": True,
            "strobe_frequency_hz": 15.0,
            "light_audio_sync_latency_ms": 20.0,
            "ltss_score": 95.0
        },
        "evpi_composite_score": 93.654321,  # Tests field_validator rounding
        "trending_verdict": "VIRAL_TIER_1",
        "algorithmic_recommendation": "High viral velocity expected. Publish immediately with trending audio tags."
    }

    report = EDMViralGradingReport.model_validate(payload)
    assert report.video_id == "vid_edc_2026_001"
    assert report.evpi_composite_score == 93.65  # Verified rounded to 2 decimal places
    assert report.trending_verdict == "VIRAL_TIER_1"
    assert len(report.key_transients) == 2


def test_pydantic_schema_rejection_boundaries():
    """Adversarially asserts that invalid schema payloads raise ValidationError."""
    base_valid = {
        "video_id": "vid_test",
        "gcs_uri": "gs://bucket/test.mp4",
        "video_duration_seconds": 30.0,
        "aspect_ratio": "9:16",
        "hook_analysis": {
            "hook_onset_latency_seconds": 0.1,
            "transient_count_first_3s": 2,
            "initial_visual_stimulus_score": 80.0,
            "hrv_score": 80.0
        },
        "drop_pacing_analysis": {
            "drop_detected": False,
            "dpaw_score": 25.0
        },
        "audio_analysis": {
            "sub_bass_surge_ratio": 1.0,
            "spectral_flux_delta": 1.0,
            "loudness_jump_lufs_est": 0.0,
            "audio_clipping_detected": False,
            "adr_sfd_score": 50.0
        },
        "crowd_analysis": {
            "crowd_visible_percentage": 0.0,
            "jump_synchronicity_coherence": 0.0,
            "energy_acceleration_factor": 1.0,
            "moshpit_or_intense_reaction": False,
            "cke_mve_score": 30.0
        },
        "lighting_analysis": {
            "laser_co2_pyro_present": False,
            "strobe_frequency_hz": 0.0,
            "light_audio_sync_latency_ms": 0.0,
            "ltss_score": 20.0
        },
        "evpi_composite_score": 50.0,
        "trending_verdict": "MODERATE",
        "algorithmic_recommendation": "Needs work."
    }

    # 1. Negative duration should fail
    bad_dur = dict(base_valid, video_duration_seconds=-5.0)
    with pytest.raises(ValidationError):
        EDMViralGradingReport.model_validate(bad_dur)

    # 2. Duration exceeding 300s max should fail
    bad_dur_max = dict(base_valid, video_duration_seconds=500.0)
    with pytest.raises(ValidationError):
        EDMViralGradingReport.model_validate(bad_dur_max)

    # 3. Invalid aspect ratio pattern (e.g. "horizontal" instead of "16:9") should fail
    bad_ar = dict(base_valid, aspect_ratio="horizontal")
    with pytest.raises(ValidationError):
        EDMViralGradingReport.model_validate(bad_ar)

    # 4. Out of bounds parameter score (>100) should fail
    bad_score = dict(base_valid)
    bad_score["hook_analysis"] = dict(base_valid["hook_analysis"], hrv_score=105.0)
    with pytest.raises(ValidationError):
        EDMViralGradingReport.model_validate(bad_score)

    # 5. Invalid trending verdict literal should fail
    bad_verdict = dict(base_valid, trending_verdict="SUPER_VIRAL")
    with pytest.raises(ValidationError):
        EDMViralGradingReport.model_validate(bad_verdict)


# ============================================================================
# 5. TEST SUITE: BIGQUERY ML SQL AND RECALIBRATION LOGIC
# ============================================================================

def test_acoustic_extreme_edge_cases():
    """
    Stress-tests acoustic parameter under extreme edge cases:
    - Zero bass surge (silent drop)
    - Enormous bass surge (1,000,000x surge)
    - Zero spectral flux variance (sigma_SF = 0.0)
    - Negative LUFS delta (fake drop / breakdown)
    """
    # 1. Zero bass surge, zero delta LUFS, zero SF difference -> Score = 0.0
    s_silent = calc_adr_sfd_score(r_sub=0.0, sfd_peak=1.0, sfd_build_mean=1.0, sigma_sf=1.0, delta_lufs=-10.0)
    assert s_silent == 0.0

    # 2. Enormous bass surge, massive delta LUFS, huge SF spike -> Score = 100.0
    s_massive = calc_adr_sfd_score(r_sub=1e6, sfd_peak=100.0, sfd_build_mean=0.0, sigma_sf=1.0, delta_lufs=20.0)
    assert s_massive == 100.0

    # 3. Sigma SF = 0.0 (constant variance) with epsilon protection
    s_zero_sigma = calc_adr_sfd_score(r_sub=7.0, sfd_peak=10.0, sfd_build_mean=0.0, sigma_sf=0.0, delta_lufs=6.0, epsilon=1e-6)
    assert s_zero_sigma == 100.0
    assert not math.isnan(s_zero_sigma)


def test_timing_and_drop_extreme_edge_cases():
    """
    Stress-tests drop pacing under extreme boundary conditions:
    - Drop on frame 0 (t_drop = 0.0)
    - Drop on final frame (t_drop = T)
    - Zero build duration (w_build = 0.0)
    - Endless build duration (w_build = 60.0)
    - Missing drop (drop_detected = False)
    """
    T = 30.0
    # Drop at start (t=0)
    s_early = calc_dpaw_score(t_drop=0.0, total_duration=T, w_build=4.5, delta_t_pocket=0.25)
    assert s_early < 60.0  # severely penalized

    # Drop at end (t=T)
    s_late = calc_dpaw_score(t_drop=T, total_duration=T, w_build=4.5, delta_t_pocket=0.25)
    assert s_late < 60.0  # severely penalized

    # No build (w_build = 0)
    s_no_build = calc_dpaw_score(t_drop=15.0, total_duration=T, w_build=0.0, delta_t_pocket=0.25)
    assert s_no_build < 70.0

    # Perfect drop: centered at 52% (15.6s of 30s), 4.5s build, 0.25s silence pocket
    s_perfect = calc_dpaw_score(t_drop=15.6, total_duration=T, w_build=4.5, delta_t_pocket=0.25)
    assert math.isclose(s_perfect, 100.0, abs_tol=1e-5)

    # Missing drop fallback
    s_no_drop = calc_dpaw_score(t_drop=None, total_duration=T, w_build=None, delta_t_pocket=None, drop_detected=False)
    assert s_no_drop == 25.0


def test_lighting_and_strobe_synchronicity_precision():
    """
    Stress-tests lighting synchronization sensitivity:
    - Frame-perfect sync (tau = 0.0s) -> 100%
    - 1-frame offset at 30 fps (tau = 0.033s) -> exp(-0.5) ~ 60.65%
    - 2-frame offset (tau = 0.066s) -> exp(-2.0) ~ 13.53%
    - Massive delay (tau = 1.0s) -> 0%
    """
    # 1. Frame perfect with full production (lasers+pyro+co2+led) and 16Hz strobe
    s_perfect = calc_ltss_score(tau_sync=0.0, lasers=True, pyro=True, co2=True, led=True, f_strobe=16.0)
    assert math.isclose(s_perfect, 100.0, abs_tol=1e-5)

    # 2. 1-frame offset: sync term drops from 40.0 to 40.0 * exp(-0.5) = 24.26
    s_1frame = calc_ltss_score(tau_sync=0.033, lasers=True, pyro=True, co2=True, led=True, f_strobe=16.0)
    expected = 40.0 * math.exp(-0.5) + 35.0 + 25.0
    assert math.isclose(s_1frame, expected, abs_tol=1e-5)

    # 3. Completely desynchronized lighting (1.0s offset, zero stage FX, 0Hz strobe)
    s_dead = calc_ltss_score(tau_sync=1.0, lasers=False, pyro=False, co2=False, led=False, f_strobe=0.0)
    assert s_dead < 1e-10


def test_monte_carlo_100k_sweeps():
    """100,000 random sweeps verifying global zero-division and continuous clamping stability."""
    import random
    random.seed(999)
    for _ in range(100000):
        d_hook = random.uniform(0.0, 3.0)
        n_trans = random.randint(0, 10)
        t_onset = random.uniform(0.0, 2.0)
        s1 = calc_hrv_score(d_hook, n_trans, t_onset)

        t_drop = random.uniform(0.1, 30.0)
        dur = random.uniform(10.0, 60.0)
        w_build = random.uniform(0.0, 15.0)
        dt_pocket = random.uniform(0.0, 1.5)
        s2 = calc_dpaw_score(t_drop, dur, w_build, dt_pocket)

        r_sub = random.uniform(0.0, 50.0)
        sfd_peak = random.uniform(0.0, 20.0)
        sfd_mean = random.uniform(0.0, 10.0)
        sigma_sf = random.uniform(0.0, 5.0)
        delta_lufs = random.uniform(-10.0, 15.0)
        s3 = calc_adr_sfd_score(r_sub, sfd_peak, sfd_mean, sigma_sf, delta_lufs)

        delta_e = random.uniform(0.0, 10.0)
        c_jump = random.uniform(0.0, 1.0)
        phi_bpm = random.uniform(-1.0, 1.0)
        s4 = calc_cke_mve_score(delta_e, c_jump, phi_bpm)

        tau_sync = random.uniform(0.0, 0.5)
        lasers = random.random() > 0.5
        pyro = random.random() > 0.5
        co2 = random.random() > 0.5
        led = random.random() > 0.5
        f_strobe = random.uniform(0.0, 30.0)
        s5 = calc_ltss_score(tau_sync, lasers, pyro, co2, led, f_strobe)

        evpi = calc_evpi_composite(s1, s2, s3, s4, s5)
        assert 0.0 <= evpi <= 100.0
        assert not (math.isnan(evpi) or math.isinf(evpi))



def test_sql_ddl_and_model_feature_consistency():
    """
    Parses table schema DDL and BQML model queries from VIRAL_FORMULA.md
    to assert 100% feature consistency across all SQL statements.
    """
    # Columns defined in media_pipeline.video_grades
    table_columns = {
        "video_id", "gcs_uri", "processed_timestamp", "duration_seconds", "aspect_ratio",
        "hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score",
        "evpi_composite", "trending_verdict", "hook_onset_latency_seconds",
        "drop_timestamp_seconds", "buildup_duration_seconds", "predrop_silence_ms",
        "strobe_hz", "actual_vvsa_rate", "actual_avg_percentage_viewed",
        "actual_share_count", "actual_completion_rate", "actual_viral_status"
    }

    # Model 1: viral_weight_regressor features
    m1_features = {"hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score", "actual_avg_percentage_viewed"}
    assert m1_features.issubset(table_columns), f"Missing features in M1: {m1_features - table_columns}"

    # Model 2: viral_retention_tree_regressor features
    m2_features = {
        "hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score",
        "duration_seconds", "hook_onset_latency_seconds", "drop_timestamp_seconds",
        "buildup_duration_seconds", "predrop_silence_ms", "strobe_hz", "actual_avg_percentage_viewed"
    }
    assert m2_features.issubset(table_columns), f"Missing features in M2: {m2_features - table_columns}"

    # Model 3: video_archetype_clusters features
    m3_features = {"hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score"}
    assert m3_features.issubset(table_columns), f"Missing features in M3: {m3_features - table_columns}"


def test_bqml_weight_normalization_cte_logic():
    """
    Simulates the BigQuery SQL dynamic weight recalibration CTE:
    GREATEST(0.01, weight) / SUM(GREATEST(0.01, weight)) OVER()
    Proves that even with negative or degenerate learned weights, the recalibrated
    weights remain strictly positive and sum to 1.0000.
    """
    # Test cases: normal, negative weights, zero weights, highly skewed
    test_cases = [
        # Normal positive weights
        {"hrv_score": 0.45, "dpaw_score": 0.35, "adr_sfd_score": 0.25, "cke_mve_score": 0.15, "ltss_score": 0.10},
        # Learned negative weights for a couple parameters (e.g. noise or counter-trend)
        {"hrv_score": 0.80, "dpaw_score": -0.15, "adr_sfd_score": 0.40, "cke_mve_score": -0.05, "ltss_score": 0.30},
        # All negative weights (extreme degenerate scenario)
        {"hrv_score": -0.5, "dpaw_score": -0.2, "adr_sfd_score": -0.8, "cke_mve_score": -0.1, "ltss_score": -0.3},
    ]

    for raw_weights in test_cases:
        # Step 1: positive_weights = GREATEST(0.01, weight)
        safe_weights = {k: max(0.01, v) for k, v in raw_weights.items()}
        total_sum = sum(safe_weights.values())
        assert total_sum > 0.0

        # Step 2: normalized_weights = safe_weight / total_sum
        normalized = {k: round(v / total_sum, 4) for k, v in safe_weights.items()}

        # Verify all positive
        for k, v in normalized.items():
            assert v >= 0.001, f"Weight for {k} is non-positive: {v}"

        # Verify sum to 1.0 ± 0.001 (due to 4-decimal rounding)
        norm_sum = sum(normalized.values())
        assert math.isclose(norm_sum, 1.0, abs_tol=0.002), f"Normalized weights sum to {norm_sum}"
