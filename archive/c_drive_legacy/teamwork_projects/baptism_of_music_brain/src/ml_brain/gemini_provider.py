"""Production multimodal Gemini Omni video grading provider with Rule R27 backoff retries."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from config.settings import AppSettings, get_settings
from src.ml_brain.base import (
    BaseMLProvider,
    MLAuthenticationError,
    MLError,
    MLGradingError,
    MLRateLimitError,
)
from src.ml_brain.mock_provider import MockMLProvider
from src.models.schemas import (
    AudioMasteringSettings,
    ClipSegment,
    ColorGradeSettings,
    EditDecisionList,
    JobMetadata,
    MediaProbeResult,
    VideoJob,
)

logger = logging.getLogger(__name__)


class GeminiOmniProvider(BaseMLProvider):
    """
    Multimodal AI video grading provider powered by Google Gemini Omni models via google-genai SDK.
    Features:
    - Rule R27 compliance: Exponential backoff retry loop on 503 (UNAVAILABLE) exceptions.
    - Graceful fallback to MockMLProvider when API key is missing or in offline mode.
    - Schema-structured output generation.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        settings: Optional[AppSettings] = None,
        fallback_to_mock: bool = True,
        max_retries: int = 4,
        initial_backoff_sec: float = 1.0,
        backoff_multiplier: float = 2.0,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key or self.settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self.fallback_to_mock = fallback_to_mock
        self.max_retries = max_retries
        self.initial_backoff_sec = initial_backoff_sec
        self.backoff_multiplier = backoff_multiplier
        self.mock_fallback = MockMLProvider()
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Google GenAI client if credentials and SDK are present."""
        if not self.api_key:
            logger.info("No Gemini API key provided. GeminiOmniProvider running in fallback/mock mode.")
            return

        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini client initialized successfully (model: {self.model_name}).")
        except ImportError:
            logger.warning("google-genai SDK not installed. Falling back to mock ML provider.")
            self._client = None
        except Exception as exc:
            logger.warning(f"Failed to initialize Gemini GenAI client: {exc}. Will fallback to mock.")
            self._client = None

    def grade_video(
        self,
        media_input: Union[Path, str, VideoJob, JobMetadata],
        probe_data: Optional[Union[MediaProbeResult, Dict[str, Any]]] = None,
        user_prompt: Optional[str] = None,
    ) -> EditDecisionList:
        """
        Grade video media using live Gemini model with Rule R27 exponential backoff retry.
        Falls back to MockMLProvider if offline or API key is absent.
        """
        # If client not available or mock mode forced, fallback immediately
        if self._client is None or self.settings.mock_ml:
            return self.mock_fallback.grade_video(media_input, probe_data, user_prompt)

        job_id, source_path, duration_sec, resolution, fps, metadata = self._extract_media_context(
            media_input, probe_data
        )

        try:
            return self._call_gemini_with_retry(
                job_id=job_id,
                source_path=source_path,
                duration_sec=duration_sec,
                resolution=resolution,
                fps=fps,
                metadata=metadata,
                user_prompt=user_prompt,
            )
        except Exception as exc:
            logger.error(f"Gemini grading failed after retries: {exc}")
            if self.fallback_to_mock:
                logger.warning("Falling back to deterministic MockMLProvider.")
                return self.mock_fallback.grade_video(media_input, probe_data, user_prompt)
            raise MLGradingError(f"Gemini grading failed: {exc}") from exc

    def _call_gemini_with_retry(
        self,
        job_id: str,
        source_path: str,
        duration_sec: float,
        resolution: Tuple[int, int],
        fps: float,
        metadata: Dict[str, Any],
        user_prompt: Optional[str] = None,
    ) -> EditDecisionList:
        """
        Execute `client.models.generate_content` with Rule R27 exponential backoff retry on 503 errors.
        """
        prompt = self._construct_grading_prompt(
            job_id=job_id,
            source_path=source_path,
            duration_sec=duration_sec,
            resolution=resolution,
            fps=fps,
            metadata=metadata,
            user_prompt=user_prompt,
        )

        delay = self.initial_backoff_sec
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Invoking Gemini model '{self.model_name}' for job {job_id} (attempt {attempt}/{self.max_retries})...")
                
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )

                if not response or not response.text:
                    raise MLGradingError("Empty response returned by Gemini model.")

                return self._parse_gemini_response(
                    response_text=response.text,
                    job_id=job_id,
                    source_path=source_path,
                    duration_sec=duration_sec,
                    resolution=resolution,
                    fps=fps,
                )

            except Exception as exc:
                last_exception = exc
                err_str = str(exc)

                # Check for 503 UNAVAILABLE or transient server error (Rule R27)
                is_503 = "503" in err_str or "UNAVAILABLE" in err_str.upper() or "RESOURCE_EXHAUSTED" in err_str.upper()
                is_transient = is_503 or "connection" in err_str.lower() or "timeout" in err_str.lower()

                if is_transient and attempt < self.max_retries:
                    logger.warning(
                        f"Rule R27: Gemini API returned 503/transient error on attempt {attempt}: {exc}. "
                        f"Backing off for {delay:.2f}s before retry..."
                    )
                    time.sleep(delay)
                    delay *= self.backoff_multiplier
                    continue

                if "401" in err_str or "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str:
                    raise MLAuthenticationError(f"Gemini API authentication failed: {exc}") from exc

                if not is_transient:
                    raise

        raise MLGradingError(f"Gemini API call exceeded max retries ({self.max_retries}): {last_exception}")

    def _construct_grading_prompt(
        self,
        job_id: str,
        source_path: str,
        duration_sec: float,
        resolution: Tuple[int, int],
        fps: float,
        metadata: Dict[str, Any],
        user_prompt: Optional[str] = None,
    ) -> str:
        """Construct structured prompt enforcing valid JSON output for EditDecisionList."""
        return f"""
You are the Gemini Omni ML Video Editing Brain for the 'baptism_of_music_brain' engine.
Analyze the following media asset parameters and generate a high-impact EDM viral Edit Decision List (EDL).

Asset Parameters:
- Job ID: {job_id}
- Source File: {source_path}
- Duration: {duration_sec:.2f} seconds
- Resolution: {resolution[0]}x{resolution[1]}
- Frame Rate: {fps} fps
- User Creative Prompt: {user_prompt or 'Default EDM High-Energy Viral Cut'}

Output MUST be a single valid JSON object with the following schema:
{{
  "segments": [
    {{
      "clip_id": "seg_1",
      "source_in_sec": 0.0,
      "source_out_sec": 2.5,
      "timeline_in_sec": 0.0,
      "speed_multiplier": 1.0,
      "volume_multiplier": 1.0,
      "label": "hook"
    }}
  ],
  "color_grade": {{
    "contrast": 1.2,
    "brightness": 0.0,
    "saturation": 1.3,
    "gamma": 1.0
  }},
  "audio_mastering": {{
    "normalize_lufs": true,
    "target_lufs": -14.0,
    "peak_limit_db": -1.5,
    "gain_db": 0.0
  }},
  "rationale": "High-energy hook followed by build-up and slow-mo drop."
}}

Rules:
1. Every segment's source_out_sec MUST be strictly greater than source_in_sec and <= {duration_sec:.2f}.
2. Contrast must be 0.0 to 3.0, Brightness -1.0 to 1.0, Saturation 0.0 to 3.0, Gamma 0.1 to 5.0.
3. Return ONLY raw JSON without markdown code fences.
"""

    def _parse_gemini_response(
        self,
        response_text: str,
        job_id: str,
        source_path: str,
        duration_sec: float,
        resolution: Tuple[int, int],
        fps: float,
    ) -> EditDecisionList:
        """Parse Gemini output JSON text into validated EditDecisionList."""
        clean_text = response_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as exc:
            logger.warning(f"Could not parse Gemini JSON directly: {exc}. Extracting bracketed content.")
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(clean_text[start : end + 1])
            else:
                raise MLGradingError(f"Failed to extract valid JSON from Gemini output: {clean_text[:100]}")

        # Parse segments
        raw_segments = data.get("segments", [])
        segments: List[ClipSegment] = []
        for idx, seg_dict in enumerate(raw_segments):
            in_sec = max(0.0, float(seg_dict.get("source_in_sec", 0.0)))
            out_sec = min(duration_sec, float(seg_dict.get("source_out_sec", duration_sec)))
            if out_sec <= in_sec:
                out_sec = min(duration_sec, in_sec + 1.0)

            segments.append(
                ClipSegment(
                    clip_id=seg_dict.get("clip_id") or f"seg_{idx+1}",
                    source_in_sec=in_sec,
                    source_out_sec=out_sec,
                    timeline_in_sec=float(seg_dict.get("timeline_in_sec", 0.0)),
                    speed_multiplier=float(seg_dict.get("speed_multiplier", 1.0)),
                    volume_multiplier=float(seg_dict.get("volume_multiplier", 1.0)),
                    label=seg_dict.get("label"),
                )
            )

        if not segments:
            segments = self.mock_fallback._synthesize_segments(duration_sec, 42)

        # Parse color grade
        cg_dict = data.get("color_grade", {})
        color_grade = ColorGradeSettings(
            contrast=float(cg_dict.get("contrast", 1.15)),
            brightness=float(cg_dict.get("brightness", 0.0)),
            saturation=float(cg_dict.get("saturation", 1.25)),
            gamma=float(cg_dict.get("gamma", 1.0)),
        )

        # Parse audio mastering
        am_dict = data.get("audio_mastering", {})
        audio_mastering = AudioMasteringSettings(
            normalize_lufs=bool(am_dict.get("normalize_lufs", True)),
            target_lufs=float(am_dict.get("target_lufs", -14.0)),
            peak_limit_db=float(am_dict.get("peak_limit_db", -1.5)),
            gain_db=float(am_dict.get("gain_db", 0.0)),
        )

        now = datetime.now(timezone.utc)
        return EditDecisionList(
            job_id=job_id,
            source_video_path=source_path,
            target_resolution=resolution,
            target_fps=fps,
            encoding_profile="x264_crf17",
            segments=segments,
            color_grade=color_grade,
            audio_mastering=audio_mastering,
            manual_override_applied=False,
            created_at=now,
            updated_at=now,
        )
