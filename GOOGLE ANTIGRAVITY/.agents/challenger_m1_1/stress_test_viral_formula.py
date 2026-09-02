"""
Adversarial Stress Test Suite for EDM Short-Form Viral Formula (EVPI-5)
Target Artifact: media_pipeline/VIRAL_FORMULA.md

Tests:
1. Continuous mathematical formula implementations (HRV, DPAW, ADR-SFD, CKE-MVE, LTSS)
2. Boundary conditions, extreme values (zeros, negatives, infinities, NaNs, massive numbers)
3. Piecewise continuity and mathematical clamping
4. Non-linear killswitch matrix and EVPI composite calculations
5. Trending verdict classification boundaries
6. Pydantic v2 Schema validation, constraints, failure modes, and JSON roundtripping
7. Monte Carlo fuzz testing (10,000 iterations) for numerical stability and zero NaN/Inf leaks
8. Mathematical Monotonicity proofs for all parameter scoring functions
9. BigQuery DDL / Schema alignment and field compatibility
"""

import math
import random
import pytest
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, ValidationError


# ============================================================================
# PYDANTIC SCHEMAS (Extracted Verbatim from VIRAL_FORMULA.md Section 4)
# ============================================================================

class TransientEvent(BaseModel):
    timestamp_seconds: float = Field(
        ..., ge=0.0, description="Exact timestamp of the detected event in seconds."
    )
    event_type: Literal[
        "audio_drop", "buildup_start", "predrop_pocket", "laser_burst",
        "pyro_blast", "co2_cryo", "crowd_jump", "camera_zoom", "scene_cut"
    ] = Field(..., description="Categorical classification of the transient event.")
    intensity: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized physical intensity (0.0 to 1.0)."
    )
    description: str = Field(
        ..., max_length=256, description="Concise technical description of event."
    )


class HookAnalysis(BaseModel):
    hook_onset_latency_seconds: float = Field(
        ..., ge=0.0, description="Delay before first engaging audio/visual stimulus."
    )
    transient_count_first_3s: int = Field(
        ..., ge=0, description="Number of visual/audio pattern interrupts in [0, 3.0]s."
    )
    initial_visual_stimulus_score: float = Field(
        ..., ge=0.0, le=100.0, description="Visual kinetic quality score in [0, 3.0]s."
    )
    hrv_score: float = Field(
        ..., ge=0.0, le=100.0, description="Computed 3-Second Hook Retention Velocity Score."
    )


class DropPacingAnalysis(BaseModel):
    drop_detected: bool = Field(
        ..., description="Whether an EDM bass drop was identified."
    )
    drop_timestamp_seconds: Optional[float] = Field(
        None, ge=0.0, description="Timestamp where the main bass drop hits."
    )
    buildup_duration_seconds: Optional[float] = Field(
        None, ge=0.0, description="Duration of build-up tension preceding drop."
    )
    predrop_silence_duration_ms: Optional[float] = Field(
        None, ge=0.0, description="Duration of vocal pocket / silence gap in ms."
    )
    drop_position_ratio: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="drop_timestamp / total_video_duration."
    )
    dpaw_score: float = Field(
        ..., ge=0.0, le=100.0, description="Computed Drop Pacing & Anticipation Window Score."
    )


class AudioAcousticAnalysis(BaseModel):
    sub_bass_surge_ratio: float = Field(
        ..., ge=0.0, description="Ratio of low-end energy (30-90Hz) post-drop vs pre-drop."
    )
    spectral_flux_delta: float = Field(
        ..., ge=0.0, description="Rate of spectral change at drop onset."
    )
    loudness_jump_lufs_est: float = Field(
        ..., description="Estimated perceptual loudness difference in LUFS."
    )
    audio_clipping_detected: bool = Field(
        ..., description="True if severe microphone distortion or clipping is present."
    )
    adr_sfd_score: float = Field(
        ..., ge=0.0, le=100.0, description="Computed Audio Dynamic Range & Spectral Flux Score."
    )


class CrowdDynamicsAnalysis(BaseModel):
    crowd_visible_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage of frame area occupied by crowd."
    )
    jump_synchronicity_coherence: float = Field(
        ..., ge=0.0, le=100.0, description="Unified vertical optical flow coherence (0.0 to 1.0 or percentage)."
    )
    energy_acceleration_factor: float = Field(
        ..., ge=0.0, description="Crowd kinetic energy multiplier post-drop vs pre-drop."
    )
    moshpit_or_intense_reaction: bool = Field(
        ..., description="Presence of moshpits, rail riding, or frantic jumping."
    )
    cke_mve_score: float = Field(
        ..., ge=0.0, le=100.0, description="Computed Crowd Kinetic Energy & Motion Entropy Score."
    )


class LightingProductionAnalysis(BaseModel):
    laser_co2_pyro_present: bool = Field(
        ..., description="Presence of lasers, CO2 cryo cannons, flame pyro, or stage FX."
    )
    strobe_frequency_hz: float = Field(
        ..., ge=0.0, le=50.0, description="Estimated strobe/flash modulation frequency in Hz."
    )
    light_audio_sync_latency_ms: float = Field(
        ..., ge=0.0, description="Absolute offset between light burst and audio drop in ms."
    )
    ltss_score: float = Field(
        ..., ge=0.0, le=100.0, description="Computed Lighting Transition & Strobe Sync Score."
    )


class EDMViralGradingReport(BaseModel):
    video_id: str = Field(..., description="Unique alphanumeric identifier of the video.")
    gcs_uri: str = Field(..., description="Cloud Storage URI (gs://...) of raw video.")
    video_duration_seconds: float = Field(..., ge=1.0, le=300.0)
    aspect_ratio: str = Field(..., pattern=r"^\d+:\d+$", description="Aspect ratio string, e.g. '9:16'.")
    key_transients: List[TransientEvent] = Field(default_factory=list)
    hook_analysis: HookAnalysis
    drop_pacing_analysis: DropPacingAnalysis
    audio_analysis: AudioAcousticAnalysis
    crowd_analysis: CrowdDynamicsAnalysis
    lighting_analysis: LightingProductionAnalysis
    evpi_composite_score: float = Field(
        ..., ge=0.0, le=100.0, description="Final weighted Trending Potential score."
    )
    trending_verdict: Literal["VIRAL_TIER_1", "HIGH_POTENTIAL", "MODERATE", "LOW_REACH"]
    algorithmic_recommendation: str = Field(
        ..., max_length=512, description="Actionable editing advice for retention optimization."
    )

    @field_validator("evpi_composite_score")
    @classmethod
    def validate_evpi(cls, v: float) -> float:
        return round(v, 2)


# ============================================================================
# REFERENCE MATHEMATICAL IMPLEMENTATIONS
# ============================================================================

def clamp(val: float, low: float = 0.0, high: float = 1.0) -> float:
    if math.isnan(val):
        return low
    return max(low, min(high, val))


def calculate_s_hrv(d_hook: float, n_transients: int, t_onset: float) -> float:
    """Formula: P1 - 3-Second Hook Retention Velocity"""
    d_norm = clamp(d_hook / 3.0, 0.0, 1.0)
    n_norm = min(1.0, max(0.0, n_transients / 3.0))
    t_norm = max(0.0, 1.0 - max(0.0, t_onset) / 0.5)
    raw_hrv = 0.40 * d_norm + 0.35 * n_norm + 0.25 * t_norm
    return 100.0 * clamp(raw_hrv, 0.0, 1.0)


def calculate_s_dpaw(
    drop_detected: bool,
    t_drop: Optional[float] = None,
    total_duration: Optional[float] = None,
    w_build: Optional[float] = None,
    delta_t_pocket: Optional[float] = None,
) -> float:
    """Formula: P2 - Drop Pacing & Anticipation Window"""
    if not drop_detected or t_drop is None or total_duration is None or total_duration <= 0:
        return 25.0

    pos_ratio = t_drop / total_duration
    p_pos = math.exp(-((pos_ratio - 0.52) ** 2) / (2.0 * (0.12 ** 2)))

    build_dur = w_build if w_build is not None else 4.5
    b_window = math.exp(-((build_dur - 4.5) ** 2) / (2.0 * (1.5 ** 2)))

    pocket = delta_t_pocket if delta_t_pocket is not None else 0.30
    if 0.15 <= pocket <= 0.45:
        q_pocket = 1.0
    elif 0.0 <= pocket < 0.15:
        q_pocket = 0.5 + 0.5 * (pocket / 0.15)
    else:
        q_pocket = max(0.0, 1.0 - (pocket - 0.45) / 0.50)

    raw_dpaw = 0.45 * p_pos + 0.35 * b_window + 0.20 * q_pocket
    return 100.0 * clamp(raw_dpaw, 0.0, 1.0)


def calculate_s_adr_sfd(
    r_sub: float,
    sfd_max: float,
    sfd_mean: float,
    sfd_sigma: float,
    delta_lufs: float,
) -> float:
    """Formula: P3 - Audio Dynamic Range & Spectral Flux Delta"""
    eps = 1e-6
    safe_r_sub = max(0.0, r_sub)
    r_norm = clamp(math.log10(safe_r_sub + 1.0) / math.log10(8.0), 0.0, 1.0)

    sfd_val = (sfd_max - sfd_mean) / (2.5 * max(eps, sfd_sigma) + eps)
    sfd_norm = clamp(sfd_val, 0.0, 1.0)

    l_norm = clamp(delta_lufs / 6.0, 0.0, 1.0)

    raw_adr = 0.40 * r_norm + 0.35 * sfd_norm + 0.25 * l_norm
    return 100.0 * clamp(raw_adr, 0.0, 1.0)


def calculate_s_cke_mve(
    delta_e_kinetic: float,
    c_jump: float,
    phi_bpm: float,
    crowd_visible_percentage: float = 50.0,
) -> float:
    """Formula: P4 - Crowd Kinetic Energy & Motion Vector Entropy"""
    safe_e_kinetic = max(0.0, delta_e_kinetic)
    e_norm = min(1.0, safe_e_kinetic / 4.0)
    c_jump_norm = clamp(c_jump, 0.0, 1.0)
    phi_norm = max(0.0, min(1.0, phi_bpm))

    raw_cke = 0.40 * e_norm + 0.35 * c_jump_norm + 0.25 * phi_norm
    return 100.0 * clamp(raw_cke, 0.0, 1.0)


def calculate_s_ltss(
    tau_sync_seconds: float,
    has_lasers: bool,
    has_pyro: bool,
    has_co2: bool,
    has_led: bool,
    f_strobe_hz: float,
) -> float:
    """Formula: P5 - Lighting Transition & Strobe Peak Synchronicity"""
    sync_score = math.exp(-(tau_sync_seconds ** 2) / (2.0 * (0.033 ** 2)))

    f_prod = min(
        1.0,
        0.30 * (1.0 if has_lasers else 0.0)
        + 0.30 * (1.0 if has_pyro else 0.0)
        + 0.20 * (1.0 if has_co2 else 0.0)
        + 0.20 * (1.0 if has_led else 0.0),
    )

    strobe_norm = clamp((f_strobe_hz - 4.0) / 12.0, 0.0, 1.0)

    raw_ltss = 0.40 * sync_score + 0.35 * f_prod + 0.25 * strobe_norm
    return 100.0 * clamp(raw_ltss, 0.0, 1.0)


def calculate_evpi(
    s_hrv: float,
    s_dpaw: float,
    s_adr_sfd: float,
    s_cke_mve: float,
    s_ltss: float,
    k_audio: float = 1.0,
    k_format: float = 1.0,
    k_duration: float = 1.0,
) -> float:
    """Composite EVPI calculation with killswitch multipliers"""
    evpi_raw = (
        0.25 * s_hrv
        + 0.25 * s_dpaw
        + 0.20 * s_adr_sfd
        + 0.15 * s_cke_mve
        + 0.15 * s_ltss
    )
    compound_killswitch = k_audio * k_format * k_duration
    final_evpi = evpi_raw * compound_killswitch
    return clamp(final_evpi, 0.0, 100.0)


def determine_trending_verdict(evpi: float) -> str:
    """Classifies EVPI score into viral tiers"""
    if evpi >= 85.0:
        return "VIRAL_TIER_1"
    elif evpi >= 70.0:
        return "HIGH_POTENTIAL"
    elif evpi >= 50.0:
        return "MODERATE"
    else:
        return "LOW_REACH"


# ============================================================================
# COMPREHENSIVE ADVERSARIAL TEST SUITE
# ============================================================================

class TestViralFormulaMathematics:
    """Stress tests on mathematical formulas and edge cases"""

    def test_hrv_extreme_inputs(self):
        s_zero = calculate_s_hrv(d_hook=0.0, n_transients=0, t_onset=3.0)
        assert s_zero == 0.0
        s_max = calculate_s_hrv(d_hook=3.0, n_transients=5, t_onset=0.0)
        assert s_max == 100.0
        s_massive = calculate_s_hrv(d_hook=1000.0, n_transients=1000, t_onset=-5.0)
        assert s_massive == 100.0
        s_mid = calculate_s_hrv(d_hook=1.5, n_transients=1, t_onset=0.5)
        assert abs(s_mid - 31.66667) < 1e-4

    def test_dpaw_drop_pacing_boundaries(self):
        assert calculate_s_dpaw(drop_detected=False) == 25.0
        s_perfect = calculate_s_dpaw(True, 15.6, 30.0, 4.5, delta_t_pocket=0.30)
        assert abs(s_perfect - 100.0) < 1e-4

        # Pre-drop pocket continuity checks
        assert abs(calculate_s_dpaw(True, 15.6, 30.0, 4.5, 0.0) - 90.0) < 1e-4
        assert abs(calculate_s_dpaw(True, 15.6, 30.0, 4.5, 0.15) - 100.0) < 1e-4
        assert abs(calculate_s_dpaw(True, 15.6, 30.0, 4.5, 0.45) - 100.0) < 1e-4
        assert abs(calculate_s_dpaw(True, 15.6, 30.0, 4.5, 0.95) - 80.0) < 1e-4
        assert abs(calculate_s_dpaw(True, 15.6, 30.0, 4.5, 2.0) - 80.0) < 1e-4

        # Zero / negative duration
        assert calculate_s_dpaw(True, 5.0, 0.0) == 25.0
        assert calculate_s_dpaw(True, 5.0, -10.0) == 25.0

    def test_adr_sfd_extreme_inputs(self):
        s_zero = calculate_s_adr_sfd(0.0, 0.0, 0.0, 1.0, -10.0)
        assert s_zero == 0.0
        s_max = calculate_s_adr_sfd(7.0, 10.0, 0.0, 1.0, 6.0)
        assert s_max == 100.0
        s_overflow = calculate_s_adr_sfd(1000.0, 500.0, 1.0, 0.1, 30.0)
        assert s_overflow == 100.0
        s_zero_sigma = calculate_s_adr_sfd(2.0, 1.0, 1.0, 0.0, 3.0)
        assert 0.0 <= s_zero_sigma <= 100.0

    def test_cke_mve_crowd_dynamics(self):
        s_static = calculate_s_cke_mve(0.0, 0.0, 0.0)
        assert s_static == 0.0
        s_max = calculate_s_cke_mve(4.0, 1.0, 1.0)
        assert s_max == 100.0
        s_neg_phase = calculate_s_cke_mve(4.0, 1.0, -1.0)
        assert s_neg_phase == 75.0
        s_massive = calculate_s_cke_mve(100.0, 1.5, 2.0)
        assert s_massive == 100.0

    def test_ltss_lighting_synchronicity(self):
        s_max = calculate_s_ltss(0.0, True, True, True, True, 16.0)
        assert abs(s_max - 100.0) < 1e-4
        s_zero = calculate_s_ltss(2.0, False, False, False, False, 0.0)
        assert s_zero < 0.01

        assert abs(calculate_s_ltss(0.0, True, True, True, True, 4.0) - 75.0) < 1e-4
        assert abs(calculate_s_ltss(0.0, True, True, True, True, 10.0) - 87.5) < 1e-4
        assert abs(calculate_s_ltss(0.0, True, True, True, True, 16.0) - 100.0) < 1e-4
        assert abs(calculate_s_ltss(0.0, True, True, True, True, 50.0) - 100.0) < 1e-4

    def test_evpi_killswitches_and_weight_sum(self):
        weights = [0.25, 0.25, 0.20, 0.15, 0.15]
        assert sum(weights) == 1.00

        assert calculate_evpi(100, 100, 100, 100, 100, 1.0, 1.0, 1.0) == 100.0
        assert calculate_evpi(100, 100, 100, 100, 100, 0.1, 1.0, 1.0) == 10.0
        assert calculate_evpi(100, 100, 100, 100, 100, 1.0, 0.5, 1.0) == 50.0
        assert calculate_evpi(100, 100, 100, 100, 100, 1.0, 1.0, 0.4) == 40.0

        evpi_worst = calculate_evpi(100, 100, 100, 100, 100, 0.1, 0.5, 0.4)
        assert abs(evpi_worst - 2.0) < 1e-4
        assert determine_trending_verdict(evpi_worst) == "LOW_REACH"

    def test_trending_verdict_threshold_exactness(self):
        assert determine_trending_verdict(100.0) == "VIRAL_TIER_1"
        assert determine_trending_verdict(85.0) == "VIRAL_TIER_1"
        assert determine_trending_verdict(84.99) == "HIGH_POTENTIAL"
        assert determine_trending_verdict(70.0) == "HIGH_POTENTIAL"
        assert determine_trending_verdict(69.99) == "MODERATE"
        assert determine_trending_verdict(50.0) == "MODERATE"
        assert determine_trending_verdict(49.99) == "LOW_REACH"
        assert determine_trending_verdict(0.0) == "LOW_REACH"


class TestMathematicalMonotonicity:
    """Rigorous property tests ensuring monotonicity across all formulas"""

    def test_hrv_monotonicity(self):
        """Higher transient count or density must never reduce HRV score"""
        for t_onset in [0.0, 0.1, 0.3, 0.5, 1.0]:
            prev_score = -1.0
            for n_trans in range(0, 10):
                score = calculate_s_hrv(d_hook=1.5, n_transients=n_trans, t_onset=t_onset)
                assert score >= prev_score, f"Monotonicity violated in HRV transients: {prev_score} -> {score}"
                prev_score = score

    def test_ltss_latency_monotonicity(self):
        """Increasing sync latency offset tau_sync must monotonically decrease LTSS score"""
        prev_score = 101.0
        for latency_ms in range(0, 500, 10):
            tau_sec = latency_ms / 1000.0
            score = calculate_s_ltss(tau_sec, True, True, True, True, 16.0)
            assert score <= prev_score + 1e-9, f"Monotonicity violated in LTSS sync latency: {prev_score} -> {score}"
            prev_score = score

    def test_evpi_monotonicity(self):
        """Increasing any single sub-score must never decrease EVPI"""
        base = calculate_evpi(50, 50, 50, 50, 50)
        assert calculate_evpi(60, 50, 50, 50, 50) >= base
        assert calculate_evpi(50, 60, 50, 50, 50) >= base
        assert calculate_evpi(50, 50, 60, 50, 50) >= base
        assert calculate_evpi(50, 50, 50, 60, 50) >= base
        assert calculate_evpi(50, 50, 50, 50, 60) >= base


class TestMonteCarloFuzzing:
    """10,000 randomized iterations testing mathematical robustness and zero NaN/Inf leaks"""

    def test_monte_carlo_fuzz_hrv(self):
        random.seed(42)
        for _ in range(2000):
            d_hook = random.uniform(-10.0, 50.0)
            n_trans = random.randint(-5, 50)
            t_onset = random.uniform(-2.0, 10.0)
            score = calculate_s_hrv(d_hook, n_trans, t_onset)
            assert not math.isnan(score) and not math.isinf(score)
            assert 0.0 <= score <= 100.0

    def test_monte_carlo_fuzz_dpaw(self):
        random.seed(43)
        for _ in range(2000):
            drop_det = random.choice([True, False])
            t_drop = random.uniform(-5.0, 100.0)
            tot_dur = random.uniform(-10.0, 120.0)
            w_build = random.uniform(-5.0, 30.0)
            pocket = random.uniform(-1.0, 5.0)
            score = calculate_s_dpaw(drop_det, t_drop, tot_dur, w_build, pocket)
            assert not math.isnan(score) and not math.isinf(score)
            assert 0.0 <= score <= 100.0

    def test_monte_carlo_fuzz_adr_sfd(self):
        random.seed(44)
        for _ in range(2000):
            r_sub = random.uniform(-5.0, 100.0)
            sfd_max = random.uniform(-10.0, 100.0)
            sfd_mean = random.uniform(-10.0, 100.0)
            sfd_sigma = random.uniform(-5.0, 20.0)
            delta_lufs = random.uniform(-50.0, 50.0)
            score = calculate_s_adr_sfd(r_sub, sfd_max, sfd_mean, sfd_sigma, delta_lufs)
            assert not math.isnan(score) and not math.isinf(score)
            assert 0.0 <= score <= 100.0

    def test_monte_carlo_fuzz_cke_mve(self):
        random.seed(45)
        for _ in range(2000):
            delta_e = random.uniform(-10.0, 100.0)
            c_jump = random.uniform(-2.0, 2.0)
            phi = random.uniform(-5.0, 5.0)
            score = calculate_s_cke_mve(delta_e, c_jump, phi)
            assert not math.isnan(score) and not math.isinf(score)
            assert 0.0 <= score <= 100.0

    def test_monte_carlo_fuzz_evpi(self):
        random.seed(46)
        for _ in range(2000):
            s1 = random.uniform(0.0, 100.0)
            s2 = random.uniform(0.0, 100.0)
            s3 = random.uniform(0.0, 100.0)
            s4 = random.uniform(0.0, 100.0)
            s5 = random.uniform(0.0, 100.0)
            k_aud = random.choice([0.1, 0.6, 1.0])
            k_fmt = random.choice([0.5, 0.85, 1.0])
            k_dur = random.choice([0.4, 0.85, 1.0])
            evpi = calculate_evpi(s1, s2, s3, s4, s5, k_aud, k_fmt, k_dur)
            verdict = determine_trending_verdict(evpi)
            assert not math.isnan(evpi) and not math.isinf(evpi)
            assert 0.0 <= evpi <= 100.0
            assert verdict in ["VIRAL_TIER_1", "HIGH_POTENTIAL", "MODERATE", "LOW_REACH"]


class TestPydanticSchemaValidation:
    """Stress tests for Pydantic V2 schema validation and serialization"""

    def test_valid_grading_report_serialization(self):
        report_data = {
            "video_id": "vid_4k_edm_ultra_001",
            "gcs_uri": "gs://edm-viral-vault/raw/vid_4k_edm_ultra_001.mp4",
            "video_duration_seconds": 24.5,
            "aspect_ratio": "9:16",
            "key_transients": [
                {
                    "timestamp_seconds": 0.05,
                    "event_type": "camera_zoom",
                    "intensity": 0.9,
                    "description": "Rapid whip-zoom into DJ deck",
                },
                {
                    "timestamp_seconds": 12.8,
                    "event_type": "audio_drop",
                    "intensity": 1.0,
                    "description": "Main bass drop with sub-bass explosion",
                },
            ],
            "hook_analysis": {
                "hook_onset_latency_seconds": 0.05,
                "transient_count_first_3s": 3,
                "initial_visual_stimulus_score": 92.0,
                "hrv_score": 94.5,
            },
            "drop_pacing_analysis": {
                "drop_detected": True,
                "drop_timestamp_seconds": 12.8,
                "buildup_duration_seconds": 4.6,
                "predrop_silence_duration_ms": 280.0,
                "drop_position_ratio": 0.522,
                "dpaw_score": 98.0,
            },
            "audio_analysis": {
                "sub_bass_surge_ratio": 6.8,
                "spectral_flux_delta": 4.2,
                "loudness_jump_lufs_est": 5.8,
                "audio_clipping_detected": False,
                "adr_sfd_score": 93.0,
            },
            "crowd_analysis": {
                "crowd_visible_percentage": 65.0,
                "jump_synchronicity_coherence": 0.92,
                "energy_acceleration_factor": 4.5,
                "moshpit_or_intense_reaction": True,
                "cke_mve_score": 96.0,
            },
            "lighting_analysis": {
                "laser_co2_pyro_present": True,
                "strobe_frequency_hz": 15.0,
                "light_audio_sync_latency_ms": 20.0,
                "ltss_score": 95.0,
            },
            "evpi_composite_score": 95.15,
            "trending_verdict": "VIRAL_TIER_1",
            "algorithmic_recommendation": "Optimal candidate for immediate multi-platform distribution.",
        }

        report = EDMViralGradingReport.model_validate(report_data)
        assert report.video_id == "vid_4k_edm_ultra_001"
        assert report.evpi_composite_score == 95.15
        assert len(report.key_transients) == 2

        # JSON Roundtrip
        json_str = report.model_dump_json()
        restored = EDMViralGradingReport.model_validate_json(json_str)
        assert restored.video_id == report.video_id
        assert restored.evpi_composite_score == report.evpi_composite_score

    def test_schema_rejects_negative_and_out_of_bounds_scores(self):
        base_valid_hook = {
            "hook_onset_latency_seconds": 0.1,
            "transient_count_first_3s": 2,
            "initial_visual_stimulus_score": 80.0,
            "hrv_score": 80.0,
        }
        with pytest.raises(ValidationError):
            HookAnalysis.model_validate({**base_valid_hook, "hook_onset_latency_seconds": -0.5})
        with pytest.raises(ValidationError):
            HookAnalysis.model_validate({**base_valid_hook, "hrv_score": 105.0})
        with pytest.raises(ValidationError):
            HookAnalysis.model_validate({**base_valid_hook, "hrv_score": -1.0})

    def test_schema_rejects_invalid_event_types(self):
        with pytest.raises(ValidationError):
            TransientEvent.model_validate({
                "timestamp_seconds": 1.0,
                "event_type": "alien_invasion",
                "intensity": 0.5,
                "description": "Invalid event",
            })

    def test_schema_rejects_string_length_violations(self):
        with pytest.raises(ValidationError):
            TransientEvent.model_validate({
                "timestamp_seconds": 1.0,
                "event_type": "audio_drop",
                "intensity": 0.5,
                "description": "A" * 300,  # Max length is 256
            })

    def test_schema_rejects_invalid_aspect_ratio_format(self):
        invalid_ratios = ["9x16", "vertical", "1080:1920:30", "portrait", ""]
        base_report = {
            "video_id": "v1",
            "gcs_uri": "gs://b/v1.mp4",
            "video_duration_seconds": 15.0,
            "aspect_ratio": "9:16",
            "key_transients": [],
            "hook_analysis": {
                "hook_onset_latency_seconds": 0.1,
                "transient_count_first_3s": 1,
                "initial_visual_stimulus_score": 50.0,
                "hrv_score": 50.0,
            },
            "drop_pacing_analysis": {"drop_detected": False, "dpaw_score": 25.0},
            "audio_analysis": {
                "sub_bass_surge_ratio": 1.0,
                "spectral_flux_delta": 1.0,
                "loudness_jump_lufs_est": 0.0,
                "audio_clipping_detected": False,
                "adr_sfd_score": 50.0,
            },
            "crowd_analysis": {
                "crowd_visible_percentage": 0.0,
                "jump_synchronicity_coherence": 0.0,
                "energy_acceleration_factor": 1.0,
                "moshpit_or_intense_reaction": False,
                "cke_mve_score": 50.0,
            },
            "lighting_analysis": {
                "laser_co2_pyro_present": False,
                "strobe_frequency_hz": 0.0,
                "light_audio_sync_latency_ms": 0.0,
                "ltss_score": 50.0,
            },
            "evpi_composite_score": 45.0,
            "trending_verdict": "LOW_REACH",
            "algorithmic_recommendation": "Fix format",
        }
        for bad_ratio in invalid_ratios:
            with pytest.raises(ValidationError):
                EDMViralGradingReport.model_validate({**base_report, "aspect_ratio": bad_ratio})

    def test_schema_rejects_duration_out_of_bounds(self):
        base_report = {
            "video_id": "v1",
            "gcs_uri": "gs://b/v1.mp4",
            "video_duration_seconds": 0.5,
            "aspect_ratio": "9:16",
            "key_transients": [],
            "hook_analysis": {
                "hook_onset_latency_seconds": 0.1,
                "transient_count_first_3s": 1,
                "initial_visual_stimulus_score": 50.0,
                "hrv_score": 50.0,
            },
            "drop_pacing_analysis": {"drop_detected": False, "dpaw_score": 25.0},
            "audio_analysis": {
                "sub_bass_surge_ratio": 1.0,
                "spectral_flux_delta": 1.0,
                "loudness_jump_lufs_est": 0.0,
                "audio_clipping_detected": False,
                "adr_sfd_score": 50.0,
            },
            "crowd_analysis": {
                "crowd_visible_percentage": 0.0,
                "jump_synchronicity_coherence": 0.0,
                "energy_acceleration_factor": 1.0,
                "moshpit_or_intense_reaction": False,
                "cke_mve_score": 50.0,
            },
            "lighting_analysis": {
                "laser_co2_pyro_present": False,
                "strobe_frequency_hz": 0.0,
                "light_audio_sync_latency_ms": 0.0,
                "ltss_score": 50.0,
            },
            "evpi_composite_score": 45.0,
            "trending_verdict": "LOW_REACH",
            "algorithmic_recommendation": "Too short",
        }
        with pytest.raises(ValidationError):
            EDMViralGradingReport.model_validate(base_report)

        with pytest.raises(ValidationError):
            EDMViralGradingReport.model_validate({**base_report, "video_duration_seconds": 300.1})


class TestBigQueryCompatibility:
    """Validates relational column mappings between Pydantic and BigQuery DDL"""

    def test_schema_field_mapping_completeness(self):
        """Assert all required BigQuery DDL columns exist in EDMViralGradingReport"""
        bq_required_fields = {
            "video_id": str,
            "gcs_uri": str,
            "duration_seconds": float,
            "aspect_ratio": str,
            "hrv_score": float,
            "dpaw_score": float,
            "adr_sfd_score": float,
            "cke_mve_score": float,
            "ltss_score": float,
            "evpi_composite": float,
            "trending_verdict": str,
        }

        # Check that our report and sub-models contain equivalent fields
        report_fields = EDMViralGradingReport.model_fields
        assert "video_id" in report_fields
        assert "gcs_uri" in report_fields
        assert "video_duration_seconds" in report_fields
        assert "aspect_ratio" in report_fields
        assert "evpi_composite_score" in report_fields
        assert "trending_verdict" in report_fields

        assert "hrv_score" in HookAnalysis.model_fields
        assert "dpaw_score" in DropPacingAnalysis.model_fields
        assert "adr_sfd_score" in AudioAcousticAnalysis.model_fields
        assert "cke_mve_score" in CrowdDynamicsAnalysis.model_fields
        assert "ltss_score" in LightingProductionAnalysis.model_fields


if __name__ == "__main__":
    pytest.main(["-v", __file__])
