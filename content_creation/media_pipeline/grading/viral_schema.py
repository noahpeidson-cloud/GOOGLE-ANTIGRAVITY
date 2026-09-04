"""
Strict Pydantic V2 Models for Multimodal EDM Video Viral Grading.
Module: media_pipeline.grading.viral_schema
Authoritative Specification: VIRAL_FORMULA.md (EVPI-5)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ============================================================================
# 1. ENUMS & CONSTANTS
# ============================================================================

class TrendingVerdict(str, Enum):
    """Categorical classification of short-form viral potential."""
    VIRAL_TIER_1 = "VIRAL_TIER_1"      # EVPI >= 85.0
    HIGH_POTENTIAL = "HIGH_POTENTIAL"  # 70.0 <= EVPI < 85.0
    MODERATE = "MODERATE"              # 50.0 <= EVPI < 70.0
    LOW_REACH = "LOW_REACH"            # EVPI < 50.0

    # Aliases for backward/conftest compatibility
    VIRAL = "VIRAL_TIER_1"
    AVERAGE = "MODERATE"
    LOW = "LOW_REACH"


DEFAULT_WEIGHTS: Dict[str, float] = {
    "weight_hrv": 0.25,
    "weight_dpaw": 0.25,
    "weight_adr_sfd": 0.20,
    "weight_cke_mve": 0.15,
    "weight_ltss": 0.15,
}


# ============================================================================
# 2. MATHEMATICAL FORMULATION & KILLSWITCH HELPER FUNCTIONS
# ============================================================================

def compute_killswitches(
    audio_clipping_detected: bool,
    aspect_ratio: str,
    duration_seconds: float,
) -> Tuple[float, float, float]:
    """
    Computes non-linear algorithmic killswitch multipliers per VIRAL_FORMULA.md Section 3.2.
    
    Returns:
        (k_audio, k_format, k_duration)
    """
    # 1. Audio Integrity Killswitch (K_audio)
    if audio_clipping_detected:
        k_audio = 0.1
    else:
        k_audio = 1.0

    # 2. Aspect Ratio & Framing Killswitch (K_format)
    clean_ratio = aspect_ratio.strip()
    if clean_ratio in ("9:16", "9/16"):
        k_format = 1.0
    elif clean_ratio in ("1:1", "1/1", "4:5"):
        k_format = 0.85
    elif clean_ratio in ("16:9", "16/9"):
        k_format = 0.50
    else:
        k_format = 0.50

    # 3. Runtime Bounds Killswitch (K_duration)
    if 12.0 <= duration_seconds <= 38.0:
        k_duration = 1.0
    elif (8.0 <= duration_seconds < 12.0) or (38.0 < duration_seconds <= 60.0):
        k_duration = 0.85
    else:
        k_duration = 0.40

    return (k_audio, k_format, k_duration)


def classify_viral_tier(evpi_score: float) -> str:
    """Classifies EVPI score into TrendingVerdict string per VIRAL_FORMULA.md Section 3.3."""
    if evpi_score >= 85.0:
        return TrendingVerdict.VIRAL_TIER_1.value
    elif evpi_score >= 70.0:
        return TrendingVerdict.HIGH_POTENTIAL.value
    elif evpi_score >= 50.0:
        return TrendingVerdict.MODERATE.value
    else:
        return TrendingVerdict.LOW_REACH.value


def calculate_evpi_from_scores(
    hrv_score: float,
    dpaw_score: float,
    adr_sfd_score: float,
    cke_mve_score: float,
    ltss_score: float,
    weights: Optional[Dict[str, float]] = None,
    k_audio: float = 1.0,
    k_format: float = 1.0,
    k_duration: float = 1.0,
) -> float:
    """
    Calculates composite Expected Viral Potential Index (EVPI) per VIRAL_FORMULA.md Section 3.1.
    EVPI_raw = sum(w_i * S_i)
    EVPI = Clamp[0.0, 100.0](EVPI_raw * K_audio * K_format * K_duration)
    """
    w = weights or DEFAULT_WEIGHTS
    w_hrv = w.get("weight_hrv", w.get("hook_strength", 0.25))
    w_dpaw = w.get("weight_dpaw", w.get("audio_drop_sync", 0.25))
    w_adr = w.get("weight_adr_sfd", w.get("crowd_energy", 0.20))
    w_cke = w.get("weight_cke_mve", w.get("visual_dynamism", 0.15))
    w_ltss = w.get("weight_ltss", w.get("retention_pacing", 0.15))

    evpi_raw = (
        hrv_score * w_hrv +
        dpaw_score * w_dpaw +
        adr_sfd_score * w_adr +
        cke_mve_score * w_cke +
        ltss_score * w_ltss
    )
    multiplier = k_audio * k_format * k_duration
    composite = max(0.0, min(100.0, evpi_raw * multiplier))
    return round(float(composite), 2)


# ============================================================================
# 3. GRANULAR SUB-ANALYSIS PYDANTIC V2 SCHEMAS
# ============================================================================

class TransientEvent(BaseModel):
    """Temporal marker of a key audio-visual transient event."""
    model_config = ConfigDict(validate_assignment=True)

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
    """Parameter 1: 3-Second Hook Retention Velocity (HRV) Analysis."""
    model_config = ConfigDict(validate_assignment=True)

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
    """Parameter 2: Drop Pacing & Anticipation Window (DPAW) Analysis."""
    model_config = ConfigDict(validate_assignment=True)

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
    """Parameter 3: Audio Dynamic Range & Spectral Flux Delta (ADR-SFD) Analysis."""
    model_config = ConfigDict(validate_assignment=True)

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
    """Parameter 4: Crowd Kinetic Energy & Motion Vector Entropy (CKE-MVE) Analysis."""
    model_config = ConfigDict(validate_assignment=True)

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
    """Parameter 5: Lighting Transition & Strobe Peak Synchronicity (LTSS) Analysis."""
    model_config = ConfigDict(validate_assignment=True)

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


# ============================================================================
# 4. COMPREHENSIVE GRADING REPORT SCHEMA (VIRAL_FORMULA.md SECTION 4)
# ============================================================================

class EDMViralGradingReport(BaseModel):
    """Comprehensive Multimodal EDM Video Viral Grading Report."""
    model_config = ConfigDict(validate_assignment=True)

    video_id: str = Field(..., min_length=1, description="Unique alphanumeric identifier of the video.")
    gcs_uri: str = Field(
        ...,
        pattern=r"^gs://[a-zA-Z0-9_\.\-]+/.+\.mp4$",
        description="Cloud Storage URI (gs://...) of raw video."
    )
    video_duration_seconds: float = Field(
        ..., ge=1.0, le=300.0, description="Total video runtime in seconds."
    )
    aspect_ratio: str = Field(
        "9:16",
        pattern=r"^\d+:\d+$",
        description="Aspect ratio string, e.g. '9:16'."
    )
    key_transients: List[TransientEvent] = Field(
        default_factory=list,
        description="Chronological sequence of detected audiovisual transients."
    )
    hook_analysis: HookAnalysis
    drop_pacing_analysis: DropPacingAnalysis
    audio_analysis: AudioAcousticAnalysis
    crowd_analysis: CrowdDynamicsAnalysis
    lighting_analysis: LightingProductionAnalysis
    evpi_composite_score: float = Field(
        ..., ge=0.0, le=100.0, description="Final weighted Trending Potential score."
    )
    trending_verdict: Literal["VIRAL_TIER_1", "HIGH_POTENTIAL", "MODERATE", "LOW_REACH"] = Field(
        ..., description="Categorical viral tier classification."
    )
    algorithmic_recommendation: str = Field(
        ..., max_length=512, description="Actionable editing advice for retention optimization."
    )

    @field_validator("evpi_composite_score")
    @classmethod
    def validate_evpi(cls, v: float) -> float:
        return round(v, 2)


# ============================================================================
# 5. STREAMLINED METRICS & SCORING COMPATIBILITY SCHEMAS
# ============================================================================

class ViralParameterScores(BaseModel):
    """5 Core EDM Short-Form Viral Parameters (0.0 to 100.0)."""
    model_config = ConfigDict(validate_assignment=True)

    hrv: float = Field(..., ge=0.0, le=100.0, description="Hook Retention Velocity (0-3s energy curve)")
    dpaw: float = Field(..., ge=0.0, le=100.0, description="Drop Payoff Audio Waveform (RMS & spectral punch)")
    adr_sfd: float = Field(..., ge=0.0, le=100.0, description="Audio Drop Rate & Spectral Flux Density")
    cke_mve: float = Field(..., ge=0.0, le=100.0, description="Crowd Kinetic Energy & Motion Vector Entropy")
    ltss: float = Field(..., ge=0.0, le=100.0, description="Lighting Transition & Strobe Synchronization")


class ModelParameterWeights(BaseModel):
    """Dynamic parameter weights learned via BQML loop. Must sum to 1.0 ± 0.001."""
    model_config = ConfigDict(validate_assignment=True)

    version_id: str = "v1.0.0"
    weight_hrv: float = Field(0.25, ge=0.0, le=1.0)
    weight_dpaw: float = Field(0.25, ge=0.0, le=1.0)
    weight_adr_sfd: float = Field(0.20, ge=0.0, le=1.0)
    weight_cke_mve: float = Field(0.15, ge=0.0, le=1.0)
    weight_ltss: float = Field(0.15, ge=0.0, le=1.0)
    trained_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model_r2_score: float = Field(0.85, ge=0.0, le=1.0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_sum_to_one(self) -> ModelParameterWeights:
        total = self.weight_hrv + self.weight_dpaw + self.weight_adr_sfd + self.weight_cke_mve + self.weight_ltss
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Parameter weights must sum to 1.0 (got {total:.4f})")
        return self


def calculate_evpi(
    scores: ViralParameterScores,
    weights: Optional[ModelParameterWeights] = None
) -> float:
    """Calculates composite Expected Viral Potential Index (EVPI) from ViralParameterScores."""
    w = weights or ModelParameterWeights()
    evpi = (
        scores.hrv * w.weight_hrv +
        scores.dpaw * w.weight_dpaw +
        scores.adr_sfd * w.weight_adr_sfd +
        scores.cke_mve * w.weight_cke_mve +
        scores.ltss * w.weight_ltss
    )
    return round(float(evpi), 2)


def get_verdict_from_evpi(evpi: float) -> TrendingVerdict:
    """Classifies EVPI score into TrendingVerdict enum."""
    if evpi >= 85.0:
        return TrendingVerdict.VIRAL_TIER_1
    elif evpi >= 70.0:
        return TrendingVerdict.HIGH_POTENTIAL
    elif evpi >= 50.0:
        return TrendingVerdict.MODERATE
    else:
        return TrendingVerdict.LOW_REACH


class EDMShortsViralMetrics(BaseModel):
    """
    Direct structured metrics schema for Gemini Video Grading and Spark batch processing.
    """
    model_config = ConfigDict(validate_assignment=True)

    video_id: str = Field(..., min_length=1, description="Unique video identifier.")
    gcs_uri: str = Field(
        ...,
        pattern=r"^gs://[a-zA-Z0-9_\.\-]+/.+\.mp4$",
        description="GCS URI pointing to raw video file."
    )
    duration_seconds: float = Field(..., gt=0.0, le=60.0, description="Video duration in seconds.")
    aspect_ratio: str = Field("9:16", pattern=r"^(9:16|16:9|1:1|4:5)$", description="Aspect ratio.")
    scores: ViralParameterScores = Field(..., description="5 Core Viral Parameter Scores.")
    evpi_composite: float = Field(..., ge=0.0, le=100.0, description="Computed EVPI composite score.")
    trending_verdict: Union[TrendingVerdict, str] = Field(..., description="Viral tier verdict.")
    
    # Granular timestamps & recommendations
    peak_drop_timestamp_sec: Optional[float] = Field(None, ge=0.0)
    recommended_trim_start_sec: Optional[float] = Field(None, ge=0.0)
    recommended_trim_end_sec: Optional[float] = Field(None, ge=0.0)
    subgenre: Optional[str] = Field("EDM", description="Detected EDM subgenre.")
    suggested_hashtags: List[str] = Field(default_factory=list, description="Platform hashtags.")
    grading_rationale: Optional[str] = Field(None, description="Detailed grading explanation.")
    graded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("suggested_hashtags")
    @classmethod
    def validate_hashtags(cls, v: List[str]) -> List[str]:
        return [t if t.startswith("#") else f"#{t}" for t in v][:10]

    @model_validator(mode="after")
    def validate_evpi_and_verdict(self) -> EDMShortsViralMetrics:
        expected_verdict = get_verdict_from_evpi(self.evpi_composite)
        # Check verdict match (allowing string or enum)
        v_str = self.trending_verdict.value if isinstance(self.trending_verdict, TrendingVerdict) else str(self.trending_verdict)
        e_str = expected_verdict.value
        # Allow legacy mappings VIRAL <-> VIRAL_TIER_1, AVERAGE <-> MODERATE, LOW <-> LOW_REACH
        mapping = {
            "VIRAL": "VIRAL_TIER_1",
            "VIRAL_TIER_1": "VIRAL_TIER_1",
            "HIGH_POTENTIAL": "HIGH_POTENTIAL",
            "AVERAGE": "MODERATE",
            "MODERATE": "MODERATE",
            "LOW": "LOW_REACH",
            "LOW_REACH": "LOW_REACH",
        }
        if mapping.get(v_str) != mapping.get(e_str):
            raise ValueError(f"Verdict {v_str} does not match expected {e_str} for EVPI {self.evpi_composite}")
        return self
