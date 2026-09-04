"""
Independent Verification & Adversarial Stress-Test Script for Milestone 1: VIRAL_FORMULA.md
Reviewer: teamwork_preview_reviewer
"""

import sys
import json
import math
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, ValidationError

# ============================================================================
# 1. Pydantic Schema Definition (Extracted verbatim from VIRAL_FORMULA.md)
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
# 2. Mathematical Functions Reference Implementation
# ============================================================================

def clamp(val: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, val))

def compute_hrv(d_hook: float, n_transients: int, t_onset: float) -> float:
    hrv_raw = 0.40 * (d_hook / 3.0) + 0.35 * min(1.0, n_transients / 3.0) + 0.25 * max(0.0, 1.0 - t_onset / 0.5)
    return 100.0 * clamp(hrv_raw, 0.0, 1.0)

def compute_dpaw(drop_present: bool, t_drop: Optional[float], total_dur: float, w_build: Optional[float], delta_t_pocket: Optional[float]) -> float:
    if not drop_present or t_drop is None or w_build is None or delta_t_pocket is None:
        return 25.0
    p_pos = math.exp(-((t_drop / total_dur - 0.52) ** 2) / (2 * (0.12 ** 2)))
    b_window = math.exp(-((w_build - 4.5) ** 2) / (2 * (1.5 ** 2)))
    if 0.15 <= delta_t_pocket <= 0.45:
        q_pocket = 1.0
    elif 0.0 <= delta_t_pocket < 0.15:
        q_pocket = 0.5 + 0.5 * (delta_t_pocket / 0.15)
    else:
        q_pocket = max(0.0, 1.0 - (delta_t_pocket - 0.45) / 0.50)
    raw = 0.45 * p_pos + 0.35 * b_window + 0.20 * q_pocket
    return 100.0 * clamp(raw, 0.0, 1.0)

def compute_adr_sfd(r_sub: float, sfd_val: float, sfd_mean: float, sfd_sigma: float, delta_lufs: float) -> float:
    r_norm = clamp(math.log10(r_sub + 1.0) / math.log10(8.0), 0.0, 1.0)
    sfd_norm = clamp((sfd_val - sfd_mean) / (2.5 * sfd_sigma + 1e-6), 0.0, 1.0)
    l_norm = clamp(delta_lufs / 6.0, 0.0, 1.0)
    raw = 0.40 * r_norm + 0.35 * sfd_norm + 0.25 * l_norm
    return 100.0 * clamp(raw, 0.0, 1.0)

def compute_cke_mve(delta_e_kinetic: float, c_jump: float, phi_bpm: float) -> float:
    raw = 0.40 * min(1.0, delta_e_kinetic / 4.0) + 0.35 * clamp(c_jump, 0.0, 1.0) + 0.25 * max(0.0, phi_bpm)
    return 100.0 * clamp(raw, 0.0, 1.0)

def compute_ltss(tau_sync_sec: float, f_prod: float, f_strobe: float) -> float:
    sync_score = math.exp(-(tau_sync_sec ** 2) / (2 * (0.033 ** 2)))
    strobe_norm = clamp((f_strobe - 4.0) / 12.0, 0.0, 1.0)
    raw = 0.40 * sync_score + 0.35 * clamp(f_prod, 0.0, 1.0) + 0.25 * strobe_norm
    return 100.0 * clamp(raw, 0.0, 1.0)

def compute_evpi(s_hrv: float, s_dpaw: float, s_adr: float, s_cke: float, s_ltss: float,
                 k_audio: float = 1.0, k_format: float = 1.0, k_dur: float = 1.0) -> float:
    raw = 0.25 * s_hrv + 0.25 * s_dpaw + 0.20 * s_adr + 0.15 * s_cke + 0.15 * s_ltss
    return round(clamp(raw * k_audio * k_format * k_dur, 0.0, 100.0), 2)


# ============================================================================
# 3. Test Cases Execution
# ============================================================================

def run_tests():
    print("--- 1. Testing Pydantic Schema Parsing & Validation ---")
    valid_payload = {
        "video_id": "edm_ultra_2026_001",
        "gcs_uri": "gs://edm-raw-media-prod/ultra2026/mainstage_drop_4k.mp4",
        "video_duration_seconds": 24.5,
        "aspect_ratio": "9:16",
        "key_transients": [
            {
                "timestamp_seconds": 0.05,
                "event_type": "camera_zoom",
                "intensity": 0.9,
                "description": "Snap zoom onto DJ riser"
            },
            {
                "timestamp_seconds": 12.2,
                "event_type": "audio_drop",
                "intensity": 1.0,
                "description": "Main sub-bass drop impact"
            },
            {
                "timestamp_seconds": 12.23,
                "event_type": "laser_burst",
                "intensity": 1.0,
                "description": "RGB laser sweep synchronised with drop"
            }
        ],
        "hook_analysis": {
            "hook_onset_latency_seconds": 0.04,
            "transient_count_first_3s": 3,
            "initial_visual_stimulus_score": 95.0,
            "hrv_score": 96.5
        },
        "drop_pacing_analysis": {
            "drop_detected": True,
            "drop_timestamp_seconds": 12.2,
            "buildup_duration_seconds": 4.6,
            "predrop_silence_duration_ms": 250.0,
            "drop_position_ratio": 0.498,
            "dpaw_score": 94.2
        },
        "audio_analysis": {
            "sub_bass_surge_ratio": 6.8,
            "spectral_flux_delta": 4.2,
            "loudness_jump_lufs_est": 6.5,
            "audio_clipping_detected": False,
            "adr_sfd_score": 95.0
        },
        "crowd_analysis": {
            "crowd_visible_percentage": 65.0,
            "jump_synchronicity_coherence": 0.92,
            "energy_acceleration_factor": 4.5,
            "moshpit_or_intense_reaction": True,
            "cke_mve_score": 93.8
        },
        "lighting_analysis": {
            "laser_co2_pyro_present": True,
            "strobe_frequency_hz": 16.0,
            "light_audio_sync_latency_ms": 30.0,
            "ltss_score": 96.0
        },
        "evpi_composite_score": 95.21,
        "trending_verdict": "VIRAL_TIER_1",
        "algorithmic_recommendation": "Optimal viral candidate. Retain 9:16 vertical crop and publish immediately to YouTube Shorts."
    }

    report = EDMViralGradingReport.model_validate(valid_payload)
    json_out = report.model_dump_json(indent=2)
    print("[PASS] Successfully validated and dumped EDMViralGradingReport (JSON len: %d bytes)" % len(json_out))

    # Test Validation Bounds & Errors
    print("\n--- 2. Testing Boundary Rejections (Pydantic Constraints) ---")
    
    # Negative duration rejected
    try:
        EDMViralGradingReport.model_validate({**valid_payload, "video_duration_seconds": -5.0})
        assert False, "Should have raised ValidationError for negative duration"
    except ValidationError:
        print("[PASS] Negative duration correctly rejected")

    # Invalid Aspect ratio rejected
    try:
        EDMViralGradingReport.model_validate({**valid_payload, "aspect_ratio": "invalid_ratio"})
        assert False, "Should have raised ValidationError for aspect_ratio pattern"
    except ValidationError:
        print("[PASS] Invalid aspect_ratio pattern correctly rejected")

    # Score > 100 rejected
    try:
        EDMViralGradingReport.model_validate({**valid_payload, "evpi_composite_score": 105.0})
        assert False, "Should have raised ValidationError for evpi_composite_score > 100"
    except ValidationError:
        print("[PASS] EVPI > 100.0 correctly rejected")

    # Invalid event_type rejected
    try:
        bad_payload = json.loads(json.dumps(valid_payload))
        bad_payload["key_transients"][0]["event_type"] = "unsupported_event_type"
        EDMViralGradingReport.model_validate(bad_payload)
        assert False, "Should have raised ValidationError for bad event_type"
    except ValidationError:
        print("[PASS] Invalid event_type Literal correctly rejected")

    # Invalid trending_verdict rejected
    try:
        EDMViralGradingReport.model_validate({**valid_payload, "trending_verdict": "SUPER_VIRAL"})
        assert False, "Should have raised ValidationError for bad trending_verdict"
    except ValidationError:
        print("[PASS] Invalid trending_verdict Literal correctly rejected")

    print("\n--- 3. Testing Mathematical Scoring Bounds & Consistency ---")
    # Test HRV extremes
    hrv_max = compute_hrv(3.0, 5, 0.0)
    hrv_min = compute_hrv(0.0, 0, 5.0)
    assert abs(hrv_max - 100.0) < 1e-3, f"Expected 100.0 got {hrv_max}"
    assert abs(hrv_min - 0.0) < 1e-3, f"Expected 0.0 got {hrv_min}"
    print(f"[PASS] HRV bounds verified: min={hrv_min}, max={hrv_max}")

    # Test DPAW extremes & optimal
    dpaw_opt = compute_dpaw(True, 13.0, 25.0, 4.5, 0.30)
    dpaw_no_drop = compute_dpaw(False, None, 25.0, None, None)
    assert dpaw_opt > 99.0, f"Expected >99.0 for perfect DPAW, got {dpaw_opt}"
    assert abs(dpaw_no_drop - 25.0) < 1e-3, f"Expected 25.0 for no-drop baseline, got {dpaw_no_drop}"
    print(f"[PASS] DPAW bounds verified: no_drop={dpaw_no_drop}, perfect={dpaw_opt:.2f}")

    # Test ADR-SFD extremes
    adr_max = compute_adr_sfd(10.0, 5.0, 1.0, 1.0, 8.0)
    adr_min = compute_adr_sfd(0.0, 0.0, 5.0, 1.0, -10.0)
    assert abs(adr_max - 100.0) < 1e-3, f"Expected 100.0 got {adr_max}"
    assert abs(adr_min - 0.0) < 1e-3, f"Expected 0.0 got {adr_min}"
    print(f"[PASS] ADR-SFD bounds verified: min={adr_min}, max={adr_max}")

    # Test CKE-MVE extremes
    cke_max = compute_cke_mve(5.0, 1.0, 1.0)
    cke_min = compute_cke_mve(0.0, 0.0, -0.5)
    assert abs(cke_max - 100.0) < 1e-3, f"Expected 100.0 got {cke_max}"
    assert abs(cke_min - 0.0) < 1e-3, f"Expected 0.0 got {cke_min}"
    print(f"[PASS] CKE-MVE bounds verified: min={cke_min}, max={cke_max}")

    # Test LTSS extremes
    ltss_max = compute_ltss(0.0, 1.0, 16.0)
    ltss_min = compute_ltss(1.0, 0.0, 0.0)
    assert abs(ltss_max - 100.0) < 1e-3, f"Expected 100.0 got {ltss_max}"
    assert ltss_min < 0.1, f"Expected <0.1 got {ltss_min}"
    print(f"[PASS] LTSS bounds verified: min={ltss_min:.4f}, max={ltss_max}")

    # Test EVPI composite calculation & Killswitches
    evpi_clean = compute_evpi(100, 100, 100, 100, 100, k_audio=1.0, k_format=1.0, k_dur=1.0)
    evpi_ruined_audio = compute_evpi(100, 100, 100, 100, 100, k_audio=0.1, k_format=1.0, k_dur=1.0)
    evpi_horiz = compute_evpi(100, 100, 100, 100, 100, k_audio=1.0, k_format=0.5, k_dur=1.0)
    evpi_short = compute_evpi(100, 100, 100, 100, 100, k_audio=1.0, k_format=1.0, k_dur=0.40)
    assert evpi_clean == 100.0
    assert evpi_ruined_audio == 10.0
    assert evpi_horiz == 50.0
    assert evpi_short == 40.0
    print(f"[PASS] EVPI composite & killswitches verified: clean={evpi_clean}, clipped_audio={evpi_ruined_audio}, horizontal={evpi_horiz}, too_short={evpi_short}")

    # Verify realistic payload composite match
    computed_evpi = compute_evpi(96.5, 94.2, 95.0, 93.8, 96.0)
    print(f"[PASS] Realistic sample EVPI calculated: {computed_evpi}")
    assert computed_evpi == 95.14 or computed_evpi == 95.15, f"Discrepancy in sample EVPI: {computed_evpi}"

    # Update valid_payload with exact computed evpi
    valid_payload["evpi_composite_score"] = computed_evpi
    report_updated = EDMViralGradingReport.model_validate(valid_payload)
    assert report_updated.evpi_composite_score == computed_evpi
    print("[PASS] EDMViralGradingReport with exactly matched EVPI validated successfully")

    print("\n--- 4. Adversarial Edge Cases & Stress Testing ---")
    
    # Stress Case 1: All zeroes input
    s1_hrv = compute_hrv(0.0, 0, 100.0)
    s1_dpaw = compute_dpaw(True, 0.0, 10.0, 0.0, 10.0)
    s1_adr = compute_adr_sfd(0.0, 0.0, 10.0, 1.0, -50.0)
    s1_cke = compute_cke_mve(0.0, 0.0, -1.0)
    s1_ltss = compute_ltss(10.0, 0.0, 0.0)
    s1_evpi = compute_evpi(s1_hrv, s1_dpaw, s1_adr, s1_cke, s1_ltss, k_audio=0.1, k_format=0.5, k_dur=0.4)
    print(f"[PASS] Stress Case 1 (Minimums & worst killswitches): EVPI={s1_evpi}")
    assert 0.0 <= s1_evpi <= 100.0

    # Stress Case 2: Maximum overflow inputs (inputs far exceeding normal ranges)
    s2_hrv = compute_hrv(999.0, 999, 0.0)
    s2_dpaw = compute_dpaw(True, 13.0, 25.0, 4.5, 0.30)
    s2_adr = compute_adr_sfd(1e6, 1e6, 0.0, 1.0, 500.0)
    s2_cke = compute_cke_mve(1e6, 1.0, 5.0)
    s2_ltss = compute_ltss(0.0, 1.0, 100.0)
    s2_evpi = compute_evpi(s2_hrv, s2_dpaw, s2_adr, s2_cke, s2_ltss, k_audio=1.0, k_format=1.0, k_dur=1.0)
    print(f"[PASS] Stress Case 2 (Extreme Maximums & Clamping): EVPI={s2_evpi}")
    assert s2_evpi == 100.0

    # Stress Case 3: Pydantic Schema with No-Drop scenario (null values in optional fields)
    no_drop_payload = json.loads(json.dumps(valid_payload))
    no_drop_payload["drop_pacing_analysis"] = {
        "drop_detected": False,
        "drop_timestamp_seconds": None,
        "buildup_duration_seconds": None,
        "predrop_silence_duration_ms": None,
        "drop_position_ratio": None,
        "dpaw_score": 25.0
    }
    no_drop_evpi = compute_evpi(96.5, 25.0, 95.0, 93.8, 96.0)
    no_drop_payload["evpi_composite_score"] = no_drop_evpi
    no_drop_payload["trending_verdict"] = "HIGH_POTENTIAL" if no_drop_evpi >= 70.0 else "MODERATE"
    no_drop_report = EDMViralGradingReport.model_validate(no_drop_payload)
    print(f"[PASS] Stress Case 3 (No-drop scenario validation): EVPI={no_drop_evpi}, Verdict={no_drop_report.trending_verdict}")

    # Stress Case 4: Weight sum conservation
    w_sum = 0.25 + 0.25 + 0.20 + 0.15 + 0.15
    assert abs(w_sum - 1.0) < 1e-9, f"Weights sum must equal 1.0, got {w_sum}"
    print(f"[PASS] Parameter weights conservation: sum={w_sum:.2f}")

    print("\nALL VERIFICATIONS AND ADVERSARIAL STRESS TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
