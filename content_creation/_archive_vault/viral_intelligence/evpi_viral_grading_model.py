"""
Name: EVPI Viral Potential Index Video Grading Engine
Context Mapping: Extracted from `media_pipeline/grading/viral_schema.py`, `VIRAL_FORMULA.md`, and `gemini_multimodal_client.py`.
Strengths: Objective, continuous 0-100 scoring model grounded in empirical short-form platform metrics (VVSA, APV, loop retention). Separates feature extraction into 5 orthogonal dimensions. Employs non-linear killswitch dampeners so severe defects (clipping audio, safe zone collisions, duration mismatch) instantly collapse the score without masking. Validated against Pydantic V2 schemas for Gemini Multimodal structured output.
Weaknesses: In the legacy pipeline, the grading engine was entangled with PySpark cluster scripts and an unmaintained BigQuery feedback loop that attempted simplex weight updates on unseeded tables.
Implementation Instructions: Import `evpi_viral_grading_model` as a standalone evaluator. Instantiate `ViralScoreReport` from multimodal LLM structured responses or direct telemetry, compute killswitches via `compute_killswitches()`, and evaluate composite EVPI via `calculate_evpi()`.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from enum import Enum
import json
import math
import sys
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ============================================================================
# 1. ENUMS & CONSTANTS
# ============================================================================

class TrendingVerdict(str, Enum):
    """Categorical classification of short-form viral potential based on EVPI score."""
    VIRAL_TIER_1 = "VIRAL_TIER_1"      # EVPI >= 85.0 (Broad algorithmic distribution, 100k - 10M+ views)
    HIGH_POTENTIAL = "HIGH_POTENTIAL"  # 70.0 <= EVPI < 85.0 (Niche affinity breakout, 10k - 100k views)
    MODERATE = "MODERATE"              # 50.0 <= EVPI < 70.0 (Average reach, 1k - 10k views, requires hook tightening)
    LOW_REACH = "LOW_REACH"            # EVPI < 50.0 (Dead-end impressions, <1k views, reject or archive)

    # Aliases for backward compatibility
    VIRAL = "VIRAL_TIER_1"
    AVERAGE = "MODERATE"
    LOW = "LOW_REACH"


# Authoritative 5-Parameter EVPI Formulation Weights:
# Hook (H: 0.30), Retention (R: 0.25), Visual Engagement (V: 0.20),
# Audio-Visual Coherence (A: 0.15), Narrative Pacing (P: 0.10)
# Sum = 0.30 + 0.25 + 0.20 + 0.15 + 0.10 = 1.00
DEFAULT_EVPI_WEIGHTS: Dict[str, float] = {
    "weight_hook": 0.30,
    "weight_retention": 0.25,
    "weight_visual": 0.20,
    "weight_coherence": 0.15,
    "weight_pacing": 0.10,
}

# Optimal duration bounds in seconds
OPTIMAL_DURATION_MIN = 12.0
OPTIMAL_DURATION_MAX = 38.0
ACCEPTABLE_DURATION_MIN = 8.0
ACCEPTABLE_DURATION_MAX = 60.0


# ============================================================================
# 2. MATHEMATICAL FORMULATION & NON-LINEAR KILLSWITCHES
# ============================================================================

def compute_killswitches(
    audio_clipping_detected: bool,
    aspect_ratio: str,
    duration_seconds: float,
    safe_zone_violation: bool = False,
) -> Tuple[float, float, float]:
    """
    Computes non-linear algorithmic killswitch dampeners per EVPI-5 specifications.
    
    Killswitches enforce hard penalties: if audio clips or the format is unoptimized,
    even a high raw score is crushed.

    Parameters:
        audio_clipping_detected (bool): True if severe mic distortion or digital clipping occurs.
        aspect_ratio (str): Aspect ratio string, e.g. "9:16", "1:1", "16:9".
        duration_seconds (float): Total runtime in seconds.
        safe_zone_violation (bool): True if critical text/focal point collides with platform UI chrome.

    Returns:
        Tuple[float, float, float]: (k_audio, k_format, k_duration)
    """
    # 1. Audio Clipping Killswitch (K_audio)
    # Severe microphone clipping or distortion collapses audio-first platforms (TikTok/Shorts)
    if audio_clipping_detected:
        k_audio = 0.10
    else:
        k_audio = 1.00

    # 2. Safe-Zone & Aspect Ratio Killswitch (K_format)
    clean_ratio = aspect_ratio.strip().replace("/", ":")
    if safe_zone_violation:
        # UI safe-zone collisions cover subtitles or key action
        k_format = 0.50
    elif clean_ratio == "9:16":
        k_format = 1.00
    elif clean_ratio in ("1:1", "4:5"):
        k_format = 0.85
    elif clean_ratio == "16:9":
        k_format = 0.50
    else:
        k_format = 0.50

    # 3. Duration Bounds Killswitch (K_duration)
    # Optimal short-form retention envelope is 12s - 38s
    if OPTIMAL_DURATION_MIN <= duration_seconds <= OPTIMAL_DURATION_MAX:
        k_duration = 1.00
    elif (ACCEPTABLE_DURATION_MIN <= duration_seconds < OPTIMAL_DURATION_MIN) or (
        OPTIMAL_DURATION_MAX < duration_seconds <= ACCEPTABLE_DURATION_MAX
    ):
        k_duration = 0.85
    else:
        # Videos <8s fail to establish emotional payoff; >60s cannot qualify as Shorts/Reels
        k_duration = 0.40

    return (k_audio, k_format, k_duration)


def calculate_evpi(
    hook_score: float,
    retention_score: float,
    visual_score: float,
    coherence_score: float,
    pacing_score: float,
    weights: Optional[Dict[str, float]] = None,
    k_audio: float = 1.00,
    k_format: float = 1.00,
    k_duration: float = 1.00,
) -> Tuple[float, float]:
    """
    Calculates composite Expected Viral Potential Index (EVPI).
    
    Formula:
      EVPI_raw = (0.30 * H) + (0.25 * R) + (0.20 * V) + (0.15 * A) + (0.10 * P)
      Multiplier = K_audio * K_format * K_duration
      EVPI_composite = Clamp[0.0, 100.0](EVPI_raw * Multiplier)

    Returns:
        Tuple[float, float]: (evpi_raw, evpi_composite)
    """
    w = weights or DEFAULT_EVPI_WEIGHTS
    w_h = w.get("weight_hook", 0.30)
    w_r = w.get("weight_retention", 0.25)
    w_v = w.get("weight_visual", 0.20)
    w_a = w.get("weight_coherence", 0.15)
    w_p = w.get("weight_pacing", 0.10)

    # Validate weight sum
    total_w = w_h + w_r + w_v + w_a + w_p
    if abs(total_w - 1.0) > 0.001:
        # Normalize weights if custom
        w_h, w_r, w_v, w_a, w_p = [val / total_w for val in (w_h, w_r, w_v, w_a, w_p)]

    evpi_raw = (
        hook_score * w_h +
        retention_score * w_r +
        visual_score * w_v +
        coherence_score * w_a +
        pacing_score * w_p
    )
    evpi_raw = max(0.0, min(100.0, evpi_raw))

    multiplier = k_audio * k_format * k_duration
    composite = max(0.0, min(100.0, evpi_raw * multiplier))
    return (round(float(evpi_raw), 2), round(float(composite), 2))


def classify_verdict(evpi_score: float) -> TrendingVerdict:
    """Classifies EVPI score into TrendingVerdict enum."""
    if evpi_score >= 85.0:
        return TrendingVerdict.VIRAL_TIER_1
    elif evpi_score >= 70.0:
        return TrendingVerdict.HIGH_POTENTIAL
    elif evpi_score >= 50.0:
        return TrendingVerdict.MODERATE
    else:
        return TrendingVerdict.LOW_REACH


# ============================================================================
# 3. STRICT PYDANTIC V2 SCHEMAS FOR GEMINI MULTIMODAL EVALUATION
# ============================================================================

class HookMetrics(BaseModel):
    """Granular metrics for Parameter 1: Hook Velocity (0-3s window)."""
    model_config = ConfigDict(validate_assignment=True)

    hook_onset_latency_seconds: float = Field(
        ..., ge=0.0, description="Delay before the first engaging audio/visual stimulus (target: <0.15s)."
    )
    visual_pattern_interrupt_count: int = Field(
        ..., ge=0, description="Count of cuts, zooms, on-screen text, or flash transitions in [0, 3.0s]."
    )
    audio_presence_detected: bool = Field(
        True, description="True if punchy audio begins within first 0.2s of playback."
    )
    stop_rate_prediction: float = Field(
        ..., ge=0.0, le=100.0, description="Estimated Viewed vs Swiped Away percentage (VVSA target: >=75%)."
    )
    hook_score: float = Field(
        ..., ge=0.0, le=100.0, description="Normalized Hook score (0.0 to 100.0)."
    )


class RetentionMetrics(BaseModel):
    """Granular metrics for Parameter 2: Retention Curve & Drop Dynamics."""
    model_config = ConfigDict(validate_assignment=True)

    drop_detected: bool = Field(
        ..., description="True if an identifiable bass drop or energetic payoff exists."
    )
    drop_timestamp_seconds: Optional[float] = Field(
        None, ge=0.0, description="Exact timestamp where the main drop hits."
    )
    buildup_duration_seconds: Optional[float] = Field(
        None, ge=0.0, description="Duration of tension build-up preceding drop (target: 3.5s - 6.5s)."
    )
    predrop_silence_duration_ms: Optional[float] = Field(
        None, ge=0.0, description="Duration of vocal pocket or silence gap in ms (target: 150ms - 450ms)."
    )
    loop_transition_seamless: bool = Field(
        False, description="True if the ending audio/video seamlessly transitions back to the start frame."
    )
    retention_score: float = Field(
        ..., ge=0.0, le=100.0, description="Normalized Retention score (0.0 to 100.0)."
    )


class FixRecommendation(BaseModel):
    """Concrete, actionable editorial intervention to raise EVPI score."""
    model_config = ConfigDict(validate_assignment=True)

    category: Literal["hook", "pacing", "audio", "visual", "safe_zone", "format", "loop"] = Field(
        ..., description="Domain category requiring remediation."
    )
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        ..., description="Priority ranking of the recommendation."
    )
    timestamp_range: Optional[Tuple[float, float]] = Field(
        None, description="Start and end timestamp (seconds) where fix applies."
    )
    issue_description: str = Field(
        ..., min_length=5, max_length=256, description="Clear description of the observed defect."
    )
    actionable_fix: str = Field(
        ..., min_length=5, max_length=512, description="Exact instructions for editor or automated tool to resolve."
    )
    expected_evpi_lift: float = Field(
        ..., ge=0.0, le=50.0, description="Projected EVPI score improvement if fix is implemented."
    )


class ViralScoreReport(BaseModel):
    """
    Comprehensive multimodal video evaluation report adhering to strict EVPI-5 standards.
    Compatible with Gemini structured JSON output generation.
    """
    model_config = ConfigDict(validate_assignment=True)

    video_id: str = Field(..., min_length=1, description="Unique identifier or filename of the video asset.")
    duration_seconds: float = Field(..., ge=1.0, le=300.0, description="Total video runtime in seconds.")
    aspect_ratio: str = Field("9:16", pattern=r"^\d+:\d+$", description="Aspect ratio (e.g., '9:16', '16:9').")
    
    # 5 Core Parameters (0.0 - 100.0)
    hook_metrics: HookMetrics = Field(..., description="Parameter 1 (Weight: 0.30): Hook Retention Velocity.")
    retention_metrics: RetentionMetrics = Field(..., description="Parameter 2 (Weight: 0.25): Drop Pacing & Loop.")
    visual_engagement_score: float = Field(
        ..., ge=0.0, le=100.0, description="Parameter 3 (Weight: 0.20): Lighting, laser density, and visual kinetics."
    )
    audiovisual_coherence_score: float = Field(
        ..., ge=0.0, le=100.0, description="Parameter 4 (Weight: 0.15): Beat alignment and transient synchronization."
    )
    narrative_pacing_score: float = Field(
        ..., ge=0.0, le=100.0, description="Parameter 5 (Weight: 0.10): Micro-tension structure and story curve."
    )

    # Killswitch Flags
    audio_clipping_detected: bool = Field(
        False, description="True if severe clipping or microphone distortion is present."
    )
    safe_zone_violation: bool = Field(
        False, description="True if essential overlays collide with platform UI elements."
    )

    # Calculated Outputs
    evpi_raw: float = Field(
        ..., ge=0.0, le=100.0, description="Unweighted composite score before killswitch application."
    )
    killswitch_multiplier: float = Field(
        ..., ge=0.0, le=1.0, description="Total product of K_audio * K_format * K_duration."
    )
    evpi_composite: float = Field(
        ..., ge=0.0, le=100.0, description="Final weighted and damped EVPI score (0.0 to 100.0)."
    )
    trending_verdict: Literal["VIRAL_TIER_1", "HIGH_POTENTIAL", "MODERATE", "LOW_REACH"] = Field(
        ..., description="Categorical viral potential tier."
    )

    # Recommendations
    recommendations: List[FixRecommendation] = Field(
        default_factory=list, description="Actionable editing steps to optimize performance."
    )
    evaluated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of evaluation."
    )

    @field_validator("evpi_raw", "evpi_composite")
    @classmethod
    def round_scores(cls, v: float) -> float:
        return round(float(v), 2)

    @model_validator(mode="after")
    def validate_and_compute_evpi(self) -> ViralScoreReport:
        """Validates consistency between sub-scores, killswitches, and final verdict."""
        # Calculate expected killswitches
        k_a, k_f, k_d = compute_killswitches(
            audio_clipping_detected=self.audio_clipping_detected,
            aspect_ratio=self.aspect_ratio,
            duration_seconds=self.duration_seconds,
            safe_zone_violation=self.safe_zone_violation,
        )
        expected_mult = round(k_a * k_f * k_d, 4)

        # Calculate expected raw EVPI
        expected_raw, expected_comp = calculate_evpi(
            hook_score=self.hook_metrics.hook_score,
            retention_score=self.retention_metrics.retention_score,
            visual_score=self.visual_engagement_score,
            coherence_score=self.audiovisual_coherence_score,
            pacing_score=self.narrative_pacing_score,
            k_audio=k_a,
            k_format=k_f,
            k_duration=k_d,
        )

        # Allow slight floating point tolerance (0.5), otherwise enforce calculated value
        if abs(self.evpi_raw - expected_raw) > 0.5:
            self.evpi_raw = expected_raw
        if abs(self.killswitch_multiplier - expected_mult) > 0.01:
            self.killswitch_multiplier = expected_mult
        if abs(self.evpi_composite - expected_comp) > 0.5:
            self.evpi_composite = expected_comp

        expected_verdict = classify_verdict(self.evpi_composite).value
        if self.trending_verdict != expected_verdict:
            self.trending_verdict = expected_verdict

        return self


# ============================================================================
# 4. CONVENIENCE BUILDER & EVALUATOR API
# ============================================================================

def evaluate_video_metrics(
    video_id: str,
    duration_seconds: float,
    hook_score: float,
    retention_score: float,
    visual_score: float,
    coherence_score: float,
    pacing_score: float,
    aspect_ratio: str = "9:16",
    audio_clipping_detected: bool = False,
    safe_zone_violation: bool = False,
    hook_onset_latency: float = 0.1,
    pattern_interrupts: int = 3,
    drop_detected: bool = True,
    drop_timestamp: Optional[float] = None,
    buildup_duration: Optional[float] = None,
    predrop_silence_ms: Optional[float] = None,
    loop_seamless: bool = False,
    recommendations: Optional[List[FixRecommendation]] = None,
) -> ViralScoreReport:
    """
    Programmatic factory method to evaluate metrics and return a fully validated ViralScoreReport.
    """
    k_a, k_f, k_d = compute_killswitches(
        audio_clipping_detected=audio_clipping_detected,
        aspect_ratio=aspect_ratio,
        duration_seconds=duration_seconds,
        safe_zone_violation=safe_zone_violation,
    )
    evpi_raw, evpi_comp = calculate_evpi(
        hook_score=hook_score,
        retention_score=retention_score,
        visual_score=visual_score,
        coherence_score=coherence_score,
        pacing_score=pacing_score,
        k_audio=k_a,
        k_format=k_f,
        k_duration=k_d,
    )
    verdict = classify_verdict(evpi_comp)

    hook = HookMetrics(
        hook_onset_latency_seconds=hook_onset_latency,
        visual_pattern_interrupt_count=pattern_interrupts,
        audio_presence_detected=hook_onset_latency <= 0.2,
        stop_rate_prediction=hook_score * 0.9,
        hook_score=hook_score,
    )
    retention = RetentionMetrics(
        drop_detected=drop_detected,
        drop_timestamp_seconds=drop_timestamp,
        buildup_duration_seconds=buildup_duration,
        predrop_silence_duration_ms=predrop_silence_ms,
        loop_transition_seamless=loop_seamless,
        retention_score=retention_score,
    )

    return ViralScoreReport(
        video_id=video_id,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        hook_metrics=hook,
        retention_metrics=retention,
        visual_engagement_score=visual_score,
        audiovisual_coherence_score=coherence_score,
        narrative_pacing_score=pacing_score,
        audio_clipping_detected=audio_clipping_detected,
        safe_zone_violation=safe_zone_violation,
        evpi_raw=evpi_raw,
        killswitch_multiplier=round(k_a * k_f * k_d, 4),
        evpi_composite=evpi_comp,
        trending_verdict=verdict.value,
        recommendations=recommendations or [],
    )


# ============================================================================
# 5. CLI ENTRYPOINT
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="EVPI-5 Viral Grading Model & Killswitch Evaluation Engine"
    )
    parser.add_argument("--video-id", default="sample_clip_01", help="Video asset identifier.")
    parser.add_argument("--duration", type=float, default=24.5, help="Duration in seconds.")
    parser.add_argument("--aspect-ratio", default="9:16", help="Aspect ratio, e.g. 9:16, 16:9.")
    parser.add_argument("--hook", type=float, default=85.0, help="Hook score (0-100).")
    parser.add_argument("--retention", type=float, default=80.0, help="Retention score (0-100).")
    parser.add_argument("--visual", type=float, default=78.0, help="Visual engagement score (0-100).")
    parser.add_argument("--coherence", type=float, default=82.0, help="Audiovisual coherence score (0-100).")
    parser.add_argument("--pacing", type=float, default=75.0, help="Narrative pacing score (0-100).")
    parser.add_argument("--audio-clipping", action="store_true", help="Flag severe audio clipping/distortion.")
    parser.add_argument("--safe-zone-violation", action="store_true", help="Flag platform UI safe zone collision.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format.")

    args = parser.parse_args()

    report = evaluate_video_metrics(
        video_id=args.video_id,
        duration_seconds=args.duration,
        hook_score=args.hook,
        retention_score=args.retention,
        visual_score=args.visual,
        coherence_score=args.coherence,
        pacing_score=args.pacing,
        aspect_ratio=args.aspect_ratio,
        audio_clipping_detected=args.audio_clipping,
        safe_zone_violation=args.safe_zone_violation,
    )

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print("=" * 70)
        print("EVPI-5 VIRAL POTENTIAL GRADING REPORT")
        print("=" * 70)
        print(f"Asset ID: {report.video_id} | Duration: {report.duration_seconds}s | Aspect Ratio: {report.aspect_ratio}")
        print(f"Hook (H, w=0.30): {report.hook_metrics.hook_score:.1f}")
        print(f"Retention (R, w=0.25): {report.retention_metrics.retention_score:.1f}")
        print(f"Visual Engagement (V, w=0.20): {report.visual_engagement_score:.1f}")
        print(f"Audio-Visual Coherence (A, w=0.15): {report.audiovisual_coherence_score:.1f}")
        print(f"Narrative Pacing (P, w=0.10): {report.narrative_pacing_score:.1f}")
        print("-" * 70)
        print(f"Raw EVPI: {report.evpi_raw:.2f} / 100.00")
        print(f"Killswitch Multiplier: {report.killswitch_multiplier:.4f} "
              f"(Audio: {'0.10 [CLIP]' if report.audio_clipping_detected else '1.0'}, "
              f"Format/SafeZone: {'0.50 [VIOLATION]' if report.safe_zone_violation else '1.0'})")
        print(f"Final EVPI Composite: {report.evpi_composite:.2f} / 100.00")
        print(f"Trending Verdict: {report.trending_verdict}")
        print("=" * 70)


if __name__ == "__main__":
    main()
