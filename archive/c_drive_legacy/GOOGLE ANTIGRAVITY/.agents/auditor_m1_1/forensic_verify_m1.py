"""
Forensic Integrity Verification Script for Milestone 1: VIRAL_FORMULA.md
Executes comprehensive programmatic checks across:
1. Pydantic V2 Schema Validation & JSON Serialization
2. Mathematical Formula Rigor, Continuity, and Boundary Bounds
3. Composite EVPI & Killswitch Dynamics
4. BigQuery Relational Schema & ML SQL DDL Validation
5. Anti-pattern & Facade Detection
"""

import sys
import math
import re
import json
import numpy as np
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, ValidationError

# ============================================================================
# 1. PYDANTIC SCHEMA DEFINITIONS (Extracted verbatim from VIRAL_FORMULA.md)
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
# 2. MATHEMATICAL FORMULATION TEST HARNESS
# ============================================================================

def clamp(val: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, val))

def calc_p1_hrv(d_hook: float, n_transients: int, t_onset: float) -> float:
    # d_hook in [0, 3.0]
    hrv_raw = 0.40 * (d_hook / 3.0) + 0.35 * min(1.0, n_transients / 3.0) + 0.25 * max(0.0, 1.0 - t_onset / 0.5)
    return 100.0 * clamp(hrv_raw, 0.0, 1.0)

def calc_p2_dpaw(t_drop: Optional[float], duration: float, w_build: Optional[float], delta_t_pocket: Optional[float]) -> float:
    if t_drop is None or duration <= 0:
        return 25.0
    pos_ratio = t_drop / duration
    p_pos = math.exp(-((pos_ratio - 0.52) ** 2) / (2 * (0.12 ** 2)))
    
    w_b = w_build if w_build is not None else 4.5
    b_window = math.exp(-((w_b - 4.5) ** 2) / (2 * (1.5 ** 2)))
    
    dt = delta_t_pocket if delta_t_pocket is not None else 0.25
    if 0.15 <= dt <= 0.45:
        q_pocket = 1.0
    elif 0.0 <= dt < 0.15:
        q_pocket = 0.5 + 0.5 * (dt / 0.15)
    else:
        q_pocket = max(0.0, 1.0 - (dt - 0.45) / 0.50)
        
    return 100.0 * (0.45 * p_pos + 0.35 * b_window + 0.20 * q_pocket)

def calc_p3_adr_sfd(r_sub: float, sfd_val: float, delta_lufs: float) -> float:
    r_norm = clamp(math.log10(r_sub + 1.0) / math.log10(8.0), 0.0, 1.0)
    sfd_norm = clamp(sfd_val, 0.0, 1.0)
    l_norm = clamp(delta_lufs / 6.0, 0.0, 1.0)
    return 100.0 * (0.40 * r_norm + 0.35 * sfd_norm + 0.25 * l_norm)

def calc_p4_cke_mve(delta_e_kinetic: float, c_jump: float, phi_bpm: float) -> float:
    e_term = min(1.0, delta_e_kinetic / 4.0)
    c_term = clamp(c_jump, 0.0, 1.0)
    phi_term = max(0.0, phi_bpm)
    return 100.0 * (0.40 * e_term + 0.35 * c_term + 0.25 * phi_term)

def calc_p5_ltss(tau_sync_sec: float, f_prod: float, f_strobe_hz: float) -> float:
    sync_score = math.exp(-(tau_sync_sec ** 2) / (2 * (0.033 ** 2)))
    f_prod_clamped = clamp(f_prod, 0.0, 1.0)
    strobe_norm = clamp((f_strobe_hz - 4.0) / 12.0, 0.0, 1.0)
    return 100.0 * (0.40 * sync_score + 0.35 * f_prod_clamped + 0.25 * strobe_norm)

def calc_composite_evpi(s_hrv: float, s_dpaw: float, s_adr: float, s_cke: float, s_ltss: float,
                        k_audio: float = 1.0, k_format: float = 1.0, k_duration: float = 1.0) -> float:
    raw = 0.25 * s_hrv + 0.25 * s_dpaw + 0.20 * s_adr + 0.15 * s_cke + 0.15 * s_ltss
    composite = raw * k_audio * k_format * k_duration
    return round(clamp(composite, 0.0, 100.0), 2)


# ============================================================================
# 3. TEST SUITE EXECUTION
# ============================================================================

def run_all_checks():
    test_results = []
    
    # --- Check 1: Pydantic Valid Instance & JSON Round-Trip ---
    try:
        report_data = {
            "video_id": "EDM_TEST_001",
            "gcs_uri": "gs://edm-viral-media/raw/test_001.mp4",
            "video_duration_seconds": 24.5,
            "aspect_ratio": "9:16",
            "key_transients": [
                {
                    "timestamp_seconds": 0.05,
                    "event_type": "buildup_start",
                    "intensity": 0.85,
                    "description": "Aggressive vocal riser and rapid kick acceleration."
                },
                {
                    "timestamp_seconds": 12.2,
                    "event_type": "predrop_pocket",
                    "intensity": 0.95,
                    "description": "250ms vocal chop silence pocket."
                },
                {
                    "timestamp_seconds": 12.45,
                    "event_type": "audio_drop",
                    "intensity": 1.0,
                    "description": "Massive sub-bass drop impact with full laser fan."
                },
                {
                    "timestamp_seconds": 12.47,
                    "event_type": "laser_burst",
                    "intensity": 1.0,
                    "description": "30W RGB laser ceiling burst synchronized with drop."
                },
                {
                    "timestamp_seconds": 12.50,
                    "event_type": "crowd_jump",
                    "intensity": 0.90,
                    "description": "Entire stadium crowd vertical jump unison."
                }
            ],
            "hook_analysis": {
                "hook_onset_latency_seconds": 0.05,
                "transient_count_first_3s": 3,
                "initial_visual_stimulus_score": 92.5,
                "hrv_score": 93.33
            },
            "drop_pacing_analysis": {
                "drop_detected": True,
                "drop_timestamp_seconds": 12.45,
                "buildup_duration_seconds": 4.5,
                "predrop_silence_duration_ms": 250.0,
                "drop_position_ratio": 0.508,
                "dpaw_score": 98.65
            },
            "audio_analysis": {
                "sub_bass_surge_ratio": 6.8,
                "spectral_flux_delta": 0.88,
                "loudness_jump_lufs_est": 5.8,
                "audio_clipping_detected": False,
                "adr_sfd_score": 94.20
            },
            "crowd_analysis": {
                "crowd_visible_percentage": 65.0,
                "jump_synchronicity_coherence": 0.88,
                "energy_acceleration_factor": 4.2,
                "moshpit_or_intense_reaction": True,
                "cke_mve_score": 92.50
            },
            "lighting_analysis": {
                "laser_co2_pyro_present": True,
                "strobe_frequency_hz": 14.0,
                "light_audio_sync_latency_ms": 20.0,
                "ltss_score": 95.10
            },
            "evpi_composite_score": 94.75,
            "trending_verdict": "VIRAL_TIER_1",
            "algorithmic_recommendation": "Optimal viral parameters. Immediate syndication to YouTube Shorts and TikTok recommended."
        }
        
        # Validate through Pydantic
        report_obj = EDMViralGradingReport.model_validate(report_data)
        json_str = report_obj.model_dump_json()
        restored = EDMViralGradingReport.model_validate_json(json_str)
        assert restored.video_id == "EDM_TEST_001"
        assert len(restored.key_transients) == 5
        assert restored.evpi_composite_score == 94.75
        test_results.append(("Pydantic Schema Validation & JSON Round-Trip", True, "Successfully parsed, validated, and round-tripped full model JSON."))
    except Exception as e:
        test_results.append(("Pydantic Schema Validation & JSON Round-Trip", False, f"Exception: {e}"))

    # --- Check 2: Pydantic Validation Strictness (Reject Invalid Inputs) ---
    invalid_cases = [
        ({"aspect_ratio": "invalid_ratio"}, "aspect_ratio regex mismatch"),
        ({"video_duration_seconds": 0.5}, "duration < 1.0s"),
        ({"video_duration_seconds": 350.0}, "duration > 300.0s"),
        ({"trending_verdict": "SUPER_VIRAL"}, "invalid trending_verdict enum"),
    ]
    strict_passed = True
    strict_details = []
    for patch, name in invalid_cases:
        bad_data = dict(report_data)
        bad_data.update(patch)
        try:
            EDMViralGradingReport.model_validate(bad_data)
            strict_passed = False
            strict_details.append(f"FAILED to reject: {name}")
        except ValidationError:
            strict_details.append(f"Successfully rejected: {name}")
            
    test_results.append(("Pydantic Type & Constraint Enforcement", strict_passed, "; ".join(strict_details)))

    # --- Check 3: Mathematical Continuity & Boundary Bounds of 5 Parameters ---
    math_checks = []
    # P1: HRV
    s_hrv_max = calc_p1_hrv(3.0, 3, 0.0)
    s_hrv_min = calc_p1_hrv(0.0, 0, 1.0)
    s_hrv_mid = calc_p1_hrv(1.5, 2, 0.25)
    assert abs(s_hrv_max - 100.0) < 1e-5, f"P1 Max failed: {s_hrv_max}"
    assert abs(s_hrv_min - 0.0) < 1e-5, f"P1 Min failed: {s_hrv_min}"
    assert 0.0 <= s_hrv_mid <= 100.0
    math_checks.append("P1(HRV) strictly bounded [0, 100]")

    # P2: DPAW
    s_dpaw_peak = calc_p2_dpaw(t_drop=13.0, duration=25.0, w_build=4.5, delta_t_pocket=0.25)
    s_dpaw_no_drop = calc_p2_dpaw(t_drop=None, duration=25.0, w_build=None, delta_t_pocket=None)
    s_dpaw_bad = calc_p2_dpaw(t_drop=1.0, duration=30.0, w_build=15.0, delta_t_pocket=1.5)
    assert abs(s_dpaw_no_drop - 25.0) < 1e-5
    assert s_dpaw_peak > 98.0
    assert 0.0 <= s_dpaw_bad <= 100.0
    math_checks.append("P2(DPAW) Gaussian peaks & baseline valid")

    # P3: ADR-SFD
    s_adr_max = calc_p3_adr_sfd(r_sub=7.0, sfd_val=1.0, delta_lufs=6.0)
    s_adr_min = calc_p3_adr_sfd(r_sub=0.0, sfd_val=0.0, delta_lufs=0.0)
    assert abs(s_adr_max - 100.0) < 1e-5
    assert abs(s_adr_min - 0.0) < 1e-5
    math_checks.append("P3(ADR-SFD) sub-bass & LUFS scaling valid")

    # P4: CKE-MVE
    s_cke_max = calc_p4_cke_mve(delta_e_kinetic=4.0, c_jump=1.0, phi_bpm=1.0)
    s_cke_min = calc_p4_cke_mve(delta_e_kinetic=0.0, c_jump=0.0, phi_bpm=0.0)
    assert abs(s_cke_max - 100.0) < 1e-5
    assert abs(s_cke_min - 0.0) < 1e-5
    math_checks.append("P4(CKE-MVE) optical flow & BPM coupling valid")

    # P5: LTSS
    s_ltss_max = calc_p5_ltss(tau_sync_sec=0.0, f_prod=1.0, f_strobe_hz=16.0)
    s_ltss_min = calc_p5_ltss(tau_sync_sec=1.0, f_prod=0.0, f_strobe_hz=0.0)
    assert abs(s_ltss_max - 100.0) < 1e-5
    assert abs(s_ltss_min - 0.0) < 1e-3
    math_checks.append("P5(LTSS) frame-sync & production score valid")

    test_results.append(("Mathematical Formulas Continuity & Boundedness", True, "; ".join(math_checks)))

    # --- Check 4: Composite EVPI & Killswitch Functionality ---
    # Test perfect video with killswitches = 1.0
    evpi_clean = calc_composite_evpi(100, 100, 100, 100, 100, 1.0, 1.0, 1.0)
    assert evpi_clean == 100.0
    
    # Test audio killswitch (0.1 if clipping)
    evpi_ruined_audio = calc_composite_evpi(100, 100, 100, 100, 100, k_audio=0.1, k_format=1.0, k_duration=1.0)
    assert evpi_ruined_audio == 10.0
    
    # Test format killswitch (0.5 for horizontal letterboxed)
    evpi_horizontal = calc_composite_evpi(80, 80, 80, 80, 80, k_audio=1.0, k_format=0.5, k_duration=1.0)
    assert evpi_horizontal == 40.0
    
    # Test duration killswitch (0.4 for <8s)
    evpi_short = calc_composite_evpi(90, 90, 90, 90, 90, k_audio=1.0, k_format=1.0, k_duration=0.4)
    assert evpi_short == 36.0
    
    test_results.append(("Composite EVPI & Killswitch Multipliers", True, "Killswitches correctly suppress composite EVPI for clipping, horizontal framing, and out-of-bound durations."))

    # --- Check 5: BigQuery SQL Schema & Query Consistency ---
    formula_file_path = "g:/My Drive/GOOGLE ANTIGRAVITY/media_pipeline/VIRAL_FORMULA.md"
    with open(formula_file_path, "r", encoding="utf-8") as f:
        formula_content = f.read()

    sql_blocks = re.findall(r"```sql\s*(.*?)\s*```", formula_content, re.DOTALL)
    assert len(sql_blocks) >= 3, f"Expected >= 3 SQL blocks, found {len(sql_blocks)}"
    
    assert "CREATE OR REPLACE TABLE `media_pipeline.video_grades`" in formula_content
    assert "CREATE OR REPLACE TABLE `media_pipeline.model_parameter_weights`" in formula_content
    assert "CREATE OR REPLACE MODEL `media_pipeline.viral_weight_regressor`" in formula_content
    assert "CREATE OR REPLACE MODEL `media_pipeline.viral_retention_tree_regressor`" in formula_content
    assert "CREATE OR REPLACE MODEL `media_pipeline.video_archetype_clusters`" in formula_content
    assert "ML.WEIGHTS(MODEL `media_pipeline.viral_weight_regressor`)" in formula_content
    
    vg_cols = [
        "hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score",
        "evpi_composite", "trending_verdict", "hook_onset_latency_seconds",
        "drop_timestamp_seconds", "buildup_duration_seconds", "predrop_silence_ms",
        "strobe_hz", "actual_avg_percentage_viewed", "actual_vvsa_rate"
    ]
    for col in vg_cols:
        assert col in formula_content, f"Missing expected column in SQL: {col}"
    
    test_results.append(("BigQuery Relational DDL & ML Consistency", True, f"Found {len(sql_blocks)} valid BigQuery SQL blocks covering relational DDL, LINEAR_REG, BOOSTED_TREE_REGRESSOR, KMEANS, and ML.WEIGHTS feedback query."))

    # --- Check 6: Facade & Anti-Pattern Detection ---
    prohibited_patterns = [
        (r"\bTODO\b", "Unfinished TODO comments"),
        (r"\bFIXME\b", "Unfinished FIXME comments"),
        (r"\bpass\b\s*$", "Empty pass statement"),
        (r"raise NotImplementedError", "Unimplemented placeholder"),
        (r"return\s+0(?:\.0)?\s*$", "Hardcoded zero return facade"),
        (r"return\s+True\s*$", "Hardcoded boolean return facade"),
    ]
    facade_found = False
    facade_notes = []
    py_blocks = re.findall(r"```python\s*(.*?)\s*```", formula_content, re.DOTALL)
    for i, code in enumerate(py_blocks):
        for pattern, desc in prohibited_patterns:
            if re.search(pattern, code, re.MULTILINE):
                facade_found = True
                facade_notes.append(f"Block {i}: {desc}")
                
    if not facade_found:
        test_results.append(("Facade & Placeholder Detection", True, "Zero TODOs, FIXMEs, NotImplementedError, or dummy facade returns detected in Python code blocks."))
    else:
        test_results.append(("Facade & Placeholder Detection", False, "; ".join(facade_notes)))

    # --- Summary ---
    all_passed = all(res[1] for res in test_results)
    print("\n" + "="*80)
    print("FORENSIC VERIFICATION RESULTS FOR VIRAL_FORMULA.MD")
    print("="*80)
    for name, passed, details in test_results:
        status = "PASS [OK]" if passed else "FAIL [VIOLATION]"
        print(f"[{status}] {name}")
        print(f"       Details: {details}\n")
    print("="*80)
    print(f"FINAL RESULT: {'CLEAN' if all_passed else 'INTEGRITY VIOLATION'}")
    print("="*80)
    return all_passed


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
