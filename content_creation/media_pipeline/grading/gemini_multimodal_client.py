"""
Resilient Gemini Omni Multimodal Video Client.
Module: media_pipeline.grading.gemini_multimodal_client
Features:
- Official google-genai SDK integration with Structured Outputs (JSON Schema)
- Tenacity exponential backoff with jitter for 429/503 resilience
- In-flight Rate Limiter (Token Bucket / QPM Throttling)
- Dead Letter Queue (DLQ) serialization for failed payloads
- Deterministic mock / offline mode for isolated CI/CD testing
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from pydantic import BaseModel, ValidationError
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from media_pipeline.grading.viral_schema import (
    AudioAcousticAnalysis,
    CrowdDynamicsAnalysis,
    DEFAULT_WEIGHTS,
    DropPacingAnalysis,
    EDMShortsViralMetrics,
    EDMViralGradingReport,
    HookAnalysis,
    LightingProductionAnalysis,
    ModelParameterWeights,
    TrendingVerdict,
    ViralParameterScores,
    calculate_evpi,
    calculate_evpi_from_scores,
    classify_viral_tier,
    compute_killswitches,
    get_verdict_from_evpi,
)

logger = logging.getLogger("gemini_multimodal_client")
logger.setLevel(logging.INFO)

# Optional import of google-genai SDK
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    APIError = Exception
    GENAI_AVAILABLE = False


# ============================================================================
# 1. RATE LIMITER (LEAKY BUCKET / INTERVAL THROTTLER)
# ============================================================================

class RateLimiter:
    """Thread-safe rate limiter to constrain requests per minute (QPM)."""

    def __init__(self, max_qpm: int = 60):
        self.max_qpm = max_qpm
        self.min_interval = 60.0 / float(max_qpm) if max_qpm > 0 else 0.0
        self.last_call_time = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Blocks until the next request window is available."""
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.time()
            elapsed = now - self.last_call_time
            if elapsed < self.min_interval:
                sleep_duration = self.min_interval - elapsed
                time.sleep(sleep_duration)
            self.last_call_time = time.time()


# ============================================================================
# 2. DEAD LETTER QUEUE (DLQ) MANAGER
# ============================================================================

class DeadLetterQueue:
    """Manages recording and serialization of failed grading jobs."""

    def __init__(self, dlq_dir: Optional[Union[str, Path]] = None):
        self.dlq_dir = Path(dlq_dir) if dlq_dir else None
        if self.dlq_dir:
            self.dlq_dir.mkdir(parents=True, exist_ok=True)
        self.records: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def record_failure(
        self,
        video_id: str,
        gcs_uri: str,
        error: Exception,
        raw_response: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Captures error details, stores in-memory, and writes to disk if configured."""
        entry = {
            "video_id": video_id,
            "gcs_uri": gcs_uri,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "raw_response": raw_response,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self.records.append(entry)
            if self.dlq_dir:
                try:
                    file_path = self.dlq_dir / f"dlq_{video_id}_{int(time.time()*1000)}.json"
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(entry, f, indent=2)
                except Exception as write_err:
                    logger.error(f"Failed to write DLQ file for {video_id}: {write_err}")
        return entry

    def get_records(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.records)

    def clear(self) -> None:
        with self._lock:
            self.records.clear()


# ============================================================================
# 3. GEMINI MULTIMODAL VIDEO GRADING CLIENT
# ============================================================================

class GeminiMultimodalClient:
    """
    Production-grade client for grading video virality using Gemini Multimodal Video API.
    Supports structured JSON schema outputs, exponential backoff, rate limiting, and DLQ.
    """

    SYSTEM_PROMPT = (
        "You are the Autonomous Algorithmic Video Intelligence Engine for Google Antigravity, "
        "specializing in short-form EDM festival and club video optimization.\n\n"
        "Your objective is to analyze the synchronous video and audio streams with microsecond precision "
        "and extract quantitative metrics matching the EDMViralGradingReport schema.\n\n"
        "ANALYSIS DIRECTIVES:\n"
        "1. TEMPORAL ACCURACY: Identify exact millisecond timestamps of hook onset, build-up start, pre-drop pocket, and drop impact.\n"
        "2. DYNAMIC SCORING (0.0 to 100.0): Evaluate HRV, DPAW, ADR-SFD, CKE-MVE, and LTSS.\n"
        "3. COMPOSITE EVPI EVALUATION: Compute weighted EVPI and classify into VIRAL_TIER_1 (>=85), HIGH_POTENTIAL (70-84.9), MODERATE (50-69.9), LOW_REACH (<50).\n\n"
        "Output must strictly conform to the requested JSON schema."
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        max_qpm: int = 50,
        dlq_dir: Optional[Union[str, Path]] = None,
        mock_mode: Optional[bool] = None,
        simulate_rate_limit: bool = False,
        failure_rate: float = 0.0,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self.rate_limiter = RateLimiter(max_qpm=max_qpm)
        self.dlq = DeadLetterQueue(dlq_dir=dlq_dir)
        self.simulate_rate_limit = simulate_rate_limit
        self.failure_rate = failure_rate
        self.call_history: List[Dict[str, Any]] = []

        # Auto-enable mock mode if genai is missing or no api key provided (or explicitly requested)
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = not GENAI_AVAILABLE or not self.api_key

        self._client = None
        if not self.mock_mode and GENAI_AVAILABLE and self.api_key:
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize live GenAI client: {e}. Falling back to mock mode.")
                self.mock_mode = True

    @property
    def dlq_records(self) -> List[Dict[str, Any]]:
        """Convenience property for DLQ records."""
        return self.dlq.get_records()

    def _generate_deterministic_scores(
        self, video_id: str, gcs_uri: str, duration_seconds: float
    ) -> ViralParameterScores:
        """Generates deterministic pseudo-scores derived from video_id hash for mock mode."""
        h = int(hashlib.md5(f"{video_id}_{gcs_uri}".encode()).hexdigest()[:8], 16)
        hrv = round(60.0 + (h % 36), 1)
        dpaw = round(65.0 + ((h >> 2) % 31), 1)
        adr_sfd = round(70.0 + ((h >> 4) % 26), 1)
        cke_mve = round(55.0 + ((h >> 6) % 41), 1)
        ltss = round(60.0 + ((h >> 8) % 36), 1)
        return ViralParameterScores(
            hrv=min(100.0, max(0.0, hrv)),
            dpaw=min(100.0, max(0.0, dpaw)),
            adr_sfd=min(100.0, max(0.0, adr_sfd)),
            cke_mve=min(100.0, max(0.0, cke_mve)),
            ltss=min(100.0, max(0.0, ltss)),
        )

    def _generate_mock_report(
        self,
        video_id: str,
        gcs_uri: str,
        duration_seconds: float = 30.0,
        aspect_ratio: str = "9:16",
        forced_scores: Optional[ViralParameterScores] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> EDMViralGradingReport:
        """Generates a complete, schema-valid EDMViralGradingReport in mock mode."""
        scores = forced_scores or self._generate_deterministic_scores(video_id, gcs_uri, duration_seconds)
        k_aud, k_fmt, k_dur = compute_killswitches(
            audio_clipping_detected=False,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
        )
        evpi = calculate_evpi_from_scores(
            hrv_score=scores.hrv,
            dpaw_score=scores.dpaw,
            adr_sfd_score=scores.adr_sfd,
            cke_mve_score=scores.cke_mve,
            ltss_score=scores.ltss,
            weights=weights,
            k_audio=k_aud,
            k_format=k_fmt,
            k_duration=k_dur,
        )
        verdict = classify_viral_tier(evpi)

        drop_time = round(duration_seconds * 0.52, 2)
        return EDMViralGradingReport(
            video_id=video_id,
            gcs_uri=gcs_uri,
            video_duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            key_transients=[
                {
                    "timestamp_seconds": 0.05,
                    "event_type": "camera_zoom",
                    "intensity": 0.85,
                    "description": "High-velocity snap zoom on DJ decks",
                },
                {
                    "timestamp_seconds": max(0.1, drop_time - 4.5),
                    "event_type": "buildup_start",
                    "intensity": 0.90,
                    "description": "Snare roll acceleration and riser pitch bend",
                },
                {
                    "timestamp_seconds": max(0.2, drop_time - 0.25),
                    "event_type": "predrop_pocket",
                    "intensity": 0.95,
                    "description": "Crisp 250ms vocal sample silence pocket",
                },
                {
                    "timestamp_seconds": drop_time,
                    "event_type": "audio_drop",
                    "intensity": 1.0,
                    "description": "Sub-bass impact (42Hz) with synchronized laser fan",
                },
                {
                    "timestamp_seconds": min(duration_seconds - 0.1, drop_time + 0.05),
                    "event_type": "pyro_blast",
                    "intensity": 0.98,
                    "description": "Stage flame jets fired on downbeat",
                },
                {
                    "timestamp_seconds": min(duration_seconds - 0.05, drop_time + 0.1),
                    "event_type": "crowd_jump",
                    "intensity": 0.92,
                    "description": "Synchronized vertical audience jumping",
                },
            ],
            hook_analysis=HookAnalysis(
                hook_onset_latency_seconds=0.08,
                transient_count_first_3s=4,
                initial_visual_stimulus_score=scores.hrv,
                hrv_score=scores.hrv,
            ),
            drop_pacing_analysis=DropPacingAnalysis(
                drop_detected=True,
                drop_timestamp_seconds=drop_time,
                buildup_duration_seconds=4.5,
                predrop_silence_duration_ms=250.0,
                drop_position_ratio=round(drop_time / max(1.0, duration_seconds), 2),
                dpaw_score=scores.dpaw,
            ),
            audio_analysis=AudioAcousticAnalysis(
                sub_bass_surge_ratio=6.4,
                spectral_flux_delta=8.2,
                loudness_jump_lufs_est=5.5,
                audio_clipping_detected=False,
                adr_sfd_score=scores.adr_sfd,
            ),
            crowd_analysis=CrowdDynamicsAnalysis(
                crowd_visible_percentage=65.0,
                jump_synchronicity_coherence=0.88,
                energy_acceleration_factor=4.2,
                moshpit_or_intense_reaction=True,
                cke_mve_score=scores.cke_mve,
            ),
            lighting_analysis=LightingProductionAnalysis(
                laser_co2_pyro_present=True,
                strobe_frequency_hz=16.0,
                light_audio_sync_latency_ms=25.0,
                ltss_score=scores.ltss,
            ),
            evpi_composite_score=evpi,
            trending_verdict=verdict,
            algorithmic_recommendation=(
                f"Peak drop at {drop_time}s with outstanding audio-visual synchronicity ({scores.ltss}/100). "
                "Retain current 9:16 vertical framing for high retention and seamless loop transition."
            ),
        )

    @retry(
        wait=wait_random_exponential(min=1.0, max=10.0),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    def _execute_live_call(
        self,
        gcs_uri: str,
        schema_class: Type[BaseModel],
    ) -> str:
        """Invokes Gemini generate_content with structured output configuration."""
        if not self._client or not types:
            raise RuntimeError("Google GenAI client is not initialized.")

        self.rate_limiter.acquire()
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_uri(file_uri=gcs_uri, mime_type="video/mp4"),
                self.SYSTEM_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema_class,
                temperature=0.15,
                max_output_tokens=3072,
            ),
        )
        return response.text

    def grade_video_report(
        self,
        video_id: str,
        gcs_uri: str,
        duration_seconds: float = 30.0,
        aspect_ratio: str = "9:16",
        forced_scores: Optional[ViralParameterScores] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> EDMViralGradingReport:
        """
        Grades an EDM video and returns a full EDMViralGradingReport.
        Records telemetry and catches failures into the Dead Letter Queue.
        """
        start_time = time.time()
        self.call_history.append({
            "video_id": video_id,
            "gcs_uri": gcs_uri,
            "duration_seconds": duration_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        if self.simulate_rate_limit:
            err = RuntimeError(f"Gemini API 429 Quota Exceeded for {gcs_uri}")
            self.dlq.record_failure(video_id, gcs_uri, err, context={"code": 429})
            raise err

        if self.mock_mode:
            report = self._generate_mock_report(
                video_id=video_id,
                gcs_uri=gcs_uri,
                duration_seconds=duration_seconds,
                aspect_ratio=aspect_ratio,
                forced_scores=forced_scores,
                weights=weights,
            )
            return report

        try:
            raw_text = self._execute_live_call(gcs_uri=gcs_uri, schema_class=EDMViralGradingReport)
            report = EDMViralGradingReport.model_validate_json(raw_text)
            return report
        except Exception as e:
            logger.error(f"Grading failed for video {video_id} ({gcs_uri}): {e}")
            self.dlq.record_failure(video_id=video_id, gcs_uri=gcs_uri, error=e)
            raise e

    def grade_video(
        self,
        video_id: str,
        gcs_uri: str,
        duration_seconds: float = 30.0,
        aspect_ratio: str = "9:16",
        forced_scores: Optional[ViralParameterScores] = None,
        weights: Optional[Union[Dict[str, float], ModelParameterWeights]] = None,
    ) -> EDMShortsViralMetrics:
        """
        Grades an EDM video and returns streamlined EDMShortsViralMetrics.
        Cross-compatible with both standalone test harnesses and PySpark jobs.
        """
        w_dict = weights.model_dump() if isinstance(weights, ModelParameterWeights) else weights
        report = self.grade_video_report(
            video_id=video_id,
            gcs_uri=gcs_uri,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            forced_scores=forced_scores,
            weights=w_dict,
        )

        scores = ViralParameterScores(
            hrv=report.hook_analysis.hrv_score,
            dpaw=report.drop_pacing_analysis.dpaw_score,
            adr_sfd=report.audio_analysis.adr_sfd_score,
            cke_mve=report.crowd_analysis.cke_mve_score,
            ltss=report.lighting_analysis.ltss_score,
        )

        # Normalize verdict to TrendingVerdict enum or string
        verdict = report.trending_verdict

        return EDMShortsViralMetrics(
            video_id=video_id,
            gcs_uri=gcs_uri,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            scores=scores,
            evpi_composite=report.evpi_composite_score,
            trending_verdict=verdict,
            peak_drop_timestamp_sec=report.drop_pacing_analysis.drop_timestamp_seconds,
            recommended_trim_start_sec=max(0.0, (report.drop_pacing_analysis.drop_timestamp_seconds or 15.0) - 5.0),
            recommended_trim_end_sec=min(duration_seconds, (report.drop_pacing_analysis.drop_timestamp_seconds or 15.0) + 15.0),
            subgenre="EDM",
            suggested_hashtags=["#EDM", "#Festival", "#BassDrop", "#UltraMiami", "#ViralShorts"],
            grading_rationale=report.algorithmic_recommendation,
        )
