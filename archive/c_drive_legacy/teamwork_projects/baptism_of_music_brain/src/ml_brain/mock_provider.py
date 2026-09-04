"""Deterministic offline Mock ML Brain video grading provider."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.ml_brain.base import BaseMLProvider
from src.models.schemas import (
    AudioMasteringSettings,
    ClipSegment,
    ColorGradeSettings,
    EditDecisionList,
    JobMetadata,
    MediaProbeResult,
    VideoJob,
)


class MockMLProvider(BaseMLProvider):
    """
    Deterministic offline ML Brain provider.
    Synthesizes valid EditDecisionLists derived mathematically from media metadata,
    source duration, and deterministic hashing for repeatable test pipelines and CI/CD.
    """

    def __init__(
        self,
        default_contrast: float = 1.15,
        default_brightness: float = 0.0,
        default_saturation: float = 1.25,
        default_gamma: float = 1.0,
        default_target_lufs: float = -14.0,
        default_peak_limit_db: float = -1.5,
    ) -> None:
        self.default_contrast = default_contrast
        self.default_brightness = default_brightness
        self.default_saturation = default_saturation
        self.default_gamma = default_gamma
        self.default_target_lufs = default_target_lufs
        self.default_peak_limit_db = default_peak_limit_db

    def grade_video(
        self,
        media_input: Union[Path, str, VideoJob, JobMetadata],
        probe_data: Optional[Union[MediaProbeResult, Dict[str, Any]]] = None,
        user_prompt: Optional[str] = None,
    ) -> EditDecisionList:
        """
        Synthesize a deterministic EditDecisionList based on media properties and optional user prompt.
        """
        job_id, source_path, duration_sec, resolution, fps, metadata = self._extract_media_context(
            media_input, probe_data
        )

        # Compute deterministic seed hash
        hash_seed_str = f"{job_id}_{source_path}_{duration_sec:.4f}_{fps:.2f}_{user_prompt or ''}"
        hash_digest = hashlib.sha256(hash_seed_str.encode("utf-8")).hexdigest()
        seed_val = int(hash_digest[:8], 16)

        # 1. Synthesize timeline segments based on duration
        segments = self._synthesize_segments(duration_sec, seed_val)

        # 2. Synthesize color grade (with prompt responsiveness)
        color_grade = self._synthesize_color_grade(user_prompt, seed_val)

        # 3. Synthesize audio mastering
        audio_mastering = AudioMasteringSettings(
            normalize_lufs=True,
            target_lufs=self.default_target_lufs,
            peak_limit_db=self.default_peak_limit_db,
            gain_db=0.0,
            dual_pass=False,
        )

        # 4. Assemble complete EDL with fixed/stable created_at timestamp for determinism
        # If seed is identical, created_at is derived from fixed epoch or stable seed
        created_dt = datetime.fromtimestamp(1700000000 + (seed_val % 1000000), tz=timezone.utc)

        edl = EditDecisionList(
            job_id=job_id,
            source_video_path=source_path,
            target_resolution=resolution,
            target_fps=fps,
            encoding_profile="x264_crf17",
            segments=segments,
            color_grade=color_grade,
            audio_mastering=audio_mastering,
            manual_override_applied=False,
            created_at=created_dt,
            updated_at=created_dt,
        )

        return edl

    def _synthesize_segments(self, duration_sec: float, seed: int) -> List[ClipSegment]:
        """Synthesize cut segments bounded strictly within [0, duration_sec]."""
        segments: List[ClipSegment] = []

        if duration_sec <= 2.0:
            # Ultra-short clip: single full hook segment
            segments.append(
                ClipSegment(
                    clip_id="seg_hook",
                    source_in_sec=0.0,
                    source_out_sec=duration_sec,
                    timeline_in_sec=0.0,
                    speed_multiplier=1.0,
                    volume_multiplier=1.0,
                    label="hook",
                )
            )
        elif duration_sec <= 6.0:
            # Short clip: 2 segments (hook + drop)
            cut_point = round(duration_sec * 0.4, 3)
            segments.append(
                ClipSegment(
                    clip_id="seg_hook",
                    source_in_sec=0.0,
                    source_out_sec=cut_point,
                    timeline_in_sec=0.0,
                    speed_multiplier=1.0,
                    volume_multiplier=1.0,
                    label="hook",
                )
            )
            segments.append(
                ClipSegment(
                    clip_id="seg_drop",
                    source_in_sec=cut_point,
                    source_out_sec=duration_sec,
                    timeline_in_sec=cut_point,
                    speed_multiplier=1.0,
                    volume_multiplier=1.0,
                    label="drop",
                )
            )
        else:
            # Standard duration (e.g. 10s - 60s): 3 segments (Hook, Buildup, Drop Explosion)
            hook_end = min(3.0, round(duration_sec * 0.15, 3))
            drop_time = round(duration_sec * 0.52, 3)
            buildup_start = max(hook_end, round(drop_time - 3.5, 3))
            drop_end = min(duration_sec, round(drop_time + 6.0, 3))

            # Segment 1: High-energy hook
            seg1_dur = hook_end
            segments.append(
                ClipSegment(
                    clip_id="seg_hook",
                    source_in_sec=0.0,
                    source_out_sec=hook_end,
                    timeline_in_sec=0.0,
                    speed_multiplier=1.0,
                    volume_multiplier=1.0,
                    label="hook",
                )
            )

            # Segment 2: Tension buildup
            seg2_source_dur = drop_time - buildup_start
            speed2 = 1.25
            seg2_timeline_dur = seg2_source_dur / speed2
            segments.append(
                ClipSegment(
                    clip_id="seg_buildup",
                    source_in_sec=buildup_start,
                    source_out_sec=drop_time,
                    timeline_in_sec=round(seg1_dur, 3),
                    speed_multiplier=speed2,
                    volume_multiplier=1.0,
                    label="buildup",
                )
            )

            # Segment 3: Drop explosion impact
            speed3 = 0.5 if (drop_end - drop_time) >= 1.0 else 1.0
            segments.append(
                ClipSegment(
                    clip_id="seg_drop",
                    source_in_sec=drop_time,
                    source_out_sec=drop_end,
                    timeline_in_sec=round(seg1_dur + seg2_timeline_dur, 3),
                    speed_multiplier=speed3,
                    volume_multiplier=1.0,
                    label="drop_impact",
                )
            )

        # Final sanity assertion ensuring zero violation of bounds
        for seg in segments:
            if seg.source_out_sec > duration_sec:
                seg.source_out_sec = duration_sec

        return segments

    def _synthesize_color_grade(self, user_prompt: Optional[str], seed: int) -> ColorGradeSettings:
        """Synthesize color grade parameters with optional prompt keyword detection."""
        contrast = self.default_contrast
        brightness = self.default_brightness
        saturation = self.default_saturation
        gamma = self.default_gamma

        if user_prompt:
            prompt_lower = user_prompt.lower()
            if "cyberpunk" in prompt_lower or "neon" in prompt_lower:
                contrast = 1.30
                saturation = 1.45
                gamma = 1.05
            elif "teal" in prompt_lower or "orange" in prompt_lower:
                contrast = 1.25
                saturation = 1.35
                gamma = 1.0
            elif "contrast" in prompt_lower:
                contrast = 1.40
            elif "bright" in prompt_lower:
                brightness = 0.05
            elif "dark" in prompt_lower or "moody" in prompt_lower:
                brightness = -0.05
                contrast = 1.25

        return ColorGradeSettings(
            contrast=contrast,
            brightness=brightness,
            saturation=saturation,
            gamma=gamma,
        )
