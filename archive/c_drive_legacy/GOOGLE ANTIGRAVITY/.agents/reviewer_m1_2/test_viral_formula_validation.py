"""
Independent Reviewer Validation & Stress-Test Suite for Milestone 1 (VIRAL_FORMULA.md)
Location: .agents/reviewer_m1_2/test_viral_formula_validation.py
"""

import sys
import json
import math
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, ValidationError

# ============================================================================
# 1. Pydantic Models as specified in VIRAL_FORMULA.md
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
        ..., ge=0.0, le=1.0, description="Unified vertical optical flow coherence (0.0 to 1.0)."
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
# 2. Mathematical Reference Functions (Directly from Formula equations)
# ============================================================================

def clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, val))

def calc_hrv_score(d_hook: float, n_transients: int, t_onset: float) -> float:
    d_norm = d_hook / 3.0
    t_norm = clamp(n_transients / 3.0, 0.0, 1.0)
    onset_score = max(0.0, 1.0 - (t_onset / 0.5))
    raw = 0.40 * d_norm + 0.35 * t_norm + 0.25 * onset_score
    return 100.0 * clamp(raw, 0.0, 1.0)

def calc_dpaw_score(duration: float, t_drop: Optional[float], w_build: Optional[float], delta_t_pocket: Optional[float]) -> float:
    if t_drop is None or duration <= 0:
        return 25.0
    pos_ratio = t_drop / duration
    p_pos = math.exp(-((pos_ratio - 0.52) ** 2) / (2 * (0.12 ** 2)))
    
    w = w_build if w_build is not None else 4.5
    b_win = math.exp(-((w - 4.5) ** 2) / (2 * (1.5 ** 2)))
    
    dt = delta_t_pocket if delta_t_pocket is not None else 0.25
    if 0.15 <= dt <= 0.45:
        q_pocket = 1.0
    elif 0.0 <= dt < 0.15:
        q_pocket = 0.5 + 0.5 * (dt / 0.15)
    else:
        q_pocket = max(0.0, 1.0 - (dt - 0.45) / 0.50)
        
    raw = 0.45 * p_pos + 0.35 * b_win + 0.20 * q_pocket
    return 100.0 * clamp(raw, 0.0, 1.0)

def calc_evpi_composite(hrv: float, dpaw: float, adr: float, cke: float, ltss: float,
                        audio_clean: str = "clean", aspect_ratio: str = "9:16", duration: float = 20.0) -> float:
    raw = 0.25 * hrv + 0.25 * dpaw + 0.20 * adr + 0.15 * cke + 0.15 * ltss
    
    if audio_clean == "clean":
        k_aud = 1.0
    elif audio_clean == "moderate_clip":
        k_aud = 0.6
    else:
        k_aud = 0.1
        
    if aspect_ratio in ["9:16", "vertical"]:
        k_fmt = 1.0
    elif aspect_ratio in ["1:1", "square"]:
        k_fmt = 0.85
    else:
        k_fmt = 0.50
        
    if 12.0 <= duration <= 38.0:
        k_dur = 1.0
    elif (8.0 <= duration < 12.0) or (38.0 < duration <= 60.0):
        k_dur = 0.85
    else:
        k_dur = 0.40
        
    return clamp(raw * k_aud * k_fmt * k_dur, 0.0, 100.0)


# ============================================================================
# 3. Test Runner
# ============================================================================

def run_tests():
    print("=== STARTING INDEPENDENT VIRAL FORMULA VALIDATION ===")
    
    # --- TEST 1: Golden Valid Payload ---
    golden_dict = {
        "video_id": "edm_ultra_2026_001",
        "gcs_uri": "gs://antigravity-media/raw/edm_ultra_2026_001.mp4",
        "video_duration_seconds": 24.5,
        "aspect_ratio": "9:16",
        "key_transients": [
            {
                "timestamp_seconds": 0.05,
                "event_type": "camera_zoom",
                "intensity": 0.9,
                "description": "Rapid whip pan into stage visual"
            },
            {
                "timestamp_seconds": 8.0,
                "event_type": "buildup_start",
                "intensity": 0.85,
                "description": "Snare roll acceleration and riser sweep"
            },
            {
                "timestamp_seconds": 12.5,
                "event_type": "predrop_pocket",
                "intensity": 0.95,
                "description": "Clean 250ms vocal sample silence pocket"
            },
            {
                "timestamp_seconds": 12.75,
                "event_type": "audio_drop",
                "intensity": 1.0,
                "description": "Sub-bass drop explosion and CO2 cryo jets"
            }
        ],
        "hook_analysis": {
            "hook_onset_latency_seconds": 0.04,
            "transient_count_first_3s": 3,
            "initial_visual_stimulus_score": 95.0,
            "hrv_score": 94.5
        },
        "drop_pacing_analysis": {
            "drop_detected": True,
            "drop_timestamp_seconds": 12.75,
            "buildup_duration_seconds": 4.75,
            "predrop_silence_duration_ms": 250.0,
            "drop_position_ratio": 0.52,
            "dpaw_score": 96.0
        },
        "audio_analysis": {
            "sub_bass_surge_ratio": 7.2,
            "spectral_flux_delta": 4.8,
            "loudness_jump_lufs_est": 6.5,
            "audio_clipping_detected": False,
            "adr_sfd_score": 92.0
        },
        "crowd_analysis": {
            "crowd_visible_percentage": 65.0,
            "jump_synchronicity_coherence": 0.88,
            "energy_acceleration_factor": 4.2,
            "moshpit_or_intense_reaction": True,
            "cke_mve_score": 89.0
        },
        "lighting_analysis": {
            "laser_co2_pyro_present": True,
            "strobe_frequency_hz": 16.0,
            "light_audio_sync_latency_ms": 15.0,
            "ltss_score": 95.0
        },
        "evpi_composite_score": 93.62,
        "trending_verdict": "VIRAL_TIER_1",
        "algorithmic_recommendation": "Optimal drop timing, frame-perfect laser sync, and high crowd jump coherence. Ready for syndication."
    }

    report = EDMViralGradingReport.model_validate(golden_dict)
    assert report.video_id == "edm_ultra_2026_001"
    json_str = report.model_dump_json()
    reloaded = EDMViralGradingReport.model_validate_json(json_str)
    assert reloaded.evpi_composite_score == 93.62
    print("[PASS] Test 1: Golden payload validation and JSON round-trip successful.")

    # --- TEST 2: Boundary & Edge Values ---
    min_dict = dict(golden_dict)
    min_dict.update({
        "video_duration_seconds": 1.0,
        "hook_analysis": {
            "hook_onset_latency_seconds": 0.0,
            "transient_count_first_3s": 0,
            "initial_visual_stimulus_score": 0.0,
            "hrv_score": 0.0
        },
        "drop_pacing_analysis": {
            "drop_detected": False,
            "drop_timestamp_seconds": None,
            "buildup_duration_seconds": None,
            "predrop_silence_duration_ms": None,
            "drop_position_ratio": None,
            "dpaw_score": 25.0
        },
        "audio_analysis": {
            "sub_bass_surge_ratio": 0.0,
            "spectral_flux_delta": 0.0,
            "loudness_jump_lufs_est": -12.0,
            "audio_clipping_detected": True,
            "adr_sfd_score": 0.0
        },
        "crowd_analysis": {
            "crowd_visible_percentage": 0.0,
            "jump_synchronicity_coherence": 0.0,
            "energy_acceleration_factor": 0.0,
            "moshpit_or_intense_reaction": False,
            "cke_mve_score": 0.0
        },
        "lighting_analysis": {
            "laser_co2_pyro_present": False,
            "strobe_frequency_hz": 0.0,
            "light_audio_sync_latency_ms": 500.0,
            "ltss_score": 0.0
        },
        "evpi_composite_score": 2.50,
        "trending_verdict": "LOW_REACH"
    })
    min_report = EDMViralGradingReport.model_validate(min_dict)
    assert min_report.drop_pacing_analysis.drop_detected is False
    assert min_report.drop_pacing_analysis.drop_timestamp_seconds is None
    print("[PASS] Test 2: Minimum boundary payload and nullable fields validation passed.")

    # --- TEST 3: Negative / Invalid Cases Stress Test ---
    invalid_cases = [
        ("Negative duration", {**golden_dict, "video_duration_seconds": -5.0}),
        ("Duration > 300s", {**golden_dict, "video_duration_seconds": 350.0}),
        ("Invalid aspect ratio format", {**golden_dict, "aspect_ratio": "vertical_9_16"}),
        ("Invalid trending verdict", {**golden_dict, "trending_verdict": "SUPER_VIRAL"}),
        ("EVPI score > 100", {**golden_dict, "evpi_composite_score": 105.0}),
        ("Negative HRV score", {**golden_dict, "hook_analysis": {**golden_dict["hook_analysis"], "hrv_score": -1.0}}),
        ("Invalid transient event type", {**golden_dict, "key_transients": [{
            "timestamp_seconds": 1.0, "event_type": "alien_invasion", "intensity": 0.5, "description": "Invalid"
        }]})
    ]

    for label, bad_payload in invalid_cases:
        try:
            EDMViralGradingReport.model_validate(bad_payload)
            print(f"FAILED: Expected validation error for case: {label}")
            sys.exit(1)
        except ValidationError:
            pass # Expected
    print(f"[PASS] Test 3: All {len(invalid_cases)} negative stress test cases rejected cleanly by Pydantic.")

    # --- TEST 4: Mathematical Formulation Sanity Checks ---
    # HRV test:
    hrv_perfect = calc_hrv_score(d_hook=3.0, n_transients=3, t_onset=0.0)
    assert abs(hrv_perfect - 100.0) < 1e-5, f"Expected 100.0, got {hrv_perfect}"
    hrv_zero = calc_hrv_score(d_hook=0.0, n_transients=0, t_onset=2.0)
    assert abs(hrv_zero - 0.0) < 1e-5, f"Expected 0.0, got {hrv_zero}"

    # DPAW test:
    dpaw_perfect = calc_dpaw_score(duration=20.0, t_drop=10.4, w_build=4.5, delta_t_pocket=0.25)
    assert dpaw_perfect > 95.0, f"Expected >95, got {dpaw_perfect}"
    dpaw_nodrop = calc_dpaw_score(duration=20.0, t_drop=None, w_build=None, delta_t_pocket=None)
    assert abs(dpaw_nodrop - 25.0) < 1e-5, f"Expected 25.0 for no-drop, got {dpaw_nodrop}"

    # EVPI test & Killswitches:
    evpi_clean = calc_evpi_composite(95.0, 95.0, 95.0, 95.0, 95.0, audio_clean="clean", aspect_ratio="9:16", duration=20.0)
    assert abs(evpi_clean - 95.0) < 1e-5, f"Expected 95.0, got {evpi_clean}"
    
    # Audio ruined killswitch (0.1x)
    evpi_ruined_aud = calc_evpi_composite(95.0, 95.0, 95.0, 95.0, 95.0, audio_clean="ruined", aspect_ratio="9:16", duration=20.0)
    assert abs(evpi_ruined_aud - 9.5) < 1e-5, f"Expected 9.5, got {evpi_ruined_aud}"
    
    # Horizontal format killswitch (0.5x)
    evpi_horizontal = calc_evpi_composite(95.0, 95.0, 95.0, 95.0, 95.0, audio_clean="clean", aspect_ratio="16:9", duration=20.0)
    assert abs(evpi_horizontal - 47.5) < 1e-5, f"Expected 47.5, got {evpi_horizontal}"

    print("[PASS] Test 4: Mathematical formulas, Gaussian curves, and non-linear killswitches verified.")
    print("=== ALL INDEPENDENT TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_tests()
