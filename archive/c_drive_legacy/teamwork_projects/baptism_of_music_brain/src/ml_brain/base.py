"""Abstract base classes and common error types for ML Brain video grading providers."""

from __future__ import annotations

import abc
import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from src.models.schemas import (
    EditDecisionList,
    JobMetadata,
    MediaProbeResult,
    VideoJob,
)

logger = logging.getLogger(__name__)


class MLError(Exception):
    """Base exception for all ML Brain errors."""
    pass


class MLAuthenticationError(MLError):
    """Raised when Gemini or external ML API credentials are missing or invalid."""
    pass


class MLRateLimitError(MLError):
    """Raised when external ML API rate limit is exceeded."""
    pass


class MLGradingError(MLError):
    """Raised when ML grading or Edit Decision List synthesis fails."""
    pass


class BaseMLProvider(abc.ABC):
    """
    Abstract interface for video grading and Edit Decision List (EDL) synthesis providers.
    Supports both live multimodal LLMs (e.g. Gemini Omni) and offline deterministic mocks.
    """

    @abc.abstractmethod
    def grade_video(
        self,
        media_input: Union[Path, str, VideoJob, JobMetadata],
        probe_data: Optional[Union[MediaProbeResult, Dict[str, Any]]] = None,
        user_prompt: Optional[str] = None,
    ) -> EditDecisionList:
        """
        Synchronously analyze video visual/audio characteristics and synthesize an EditDecisionList.

        Args:
            media_input: Path to raw video file, or existing VideoJob/JobMetadata instance.
            probe_data: Optional pre-extracted media metadata from FFprobe (MediaProbeResult or dict).
            user_prompt: Optional natural language creative steering instructions from human editor.

        Returns:
            Fully populated, schema-compliant EditDecisionList.
        """
        raise NotImplementedError("grade_video must be implemented by concrete subclass.")

    async def grade_video_async(
        self,
        media_input: Union[Path, str, VideoJob, JobMetadata],
        probe_data: Optional[Union[MediaProbeResult, Dict[str, Any]]] = None,
        user_prompt: Optional[str] = None,
    ) -> EditDecisionList:
        """
        Asynchronously analyze video visual/audio characteristics and synthesize an EditDecisionList.
        Default implementation delegates synchronous `grade_video` to a thread pool.
        """
        return await asyncio.to_thread(self.grade_video, media_input, probe_data, user_prompt)

    def _extract_media_context(
        self,
        media_input: Union[Path, str, VideoJob, JobMetadata],
        probe_data: Optional[Union[MediaProbeResult, Dict[str, Any]]] = None,
    ) -> Tuple[str, str, float, Tuple[int, int], float, Dict[str, Any]]:
        """
        Helper utility extracting normalized media parameters from polymorphic inputs.

        Returns:
            Tuple of:
            - job_id: str
            - source_video_path: str
            - duration_sec: float
            - resolution: Tuple[int, int] (even width, even height)
            - fps: float
            - metadata: Dict[str, Any]
        """
        # 1. Extract job_id and source_video_path
        if hasattr(media_input, "job_id"):
            job_id = str(media_input.job_id)
        else:
            job_id = f"job_{Path(str(media_input)).stem}"

        if hasattr(media_input, "source_filepath"):
            source_video_path = str(media_input.source_filepath)
        else:
            source_video_path = str(Path(str(media_input)).resolve())

        # 2. Extract probe metadata if available
        duration_sec = 30.0
        width = 1920
        height = 1080
        fps = 30.0
        metadata: Dict[str, Any] = {}

        if probe_data is not None:
            if isinstance(probe_data, MediaProbeResult):
                duration_sec = probe_data.duration_sec if probe_data.duration_sec > 0 else 30.0
                if probe_data.primary_video:
                    width = probe_data.primary_video.width or 1920
                    height = probe_data.primary_video.height or 1080
                    fps = probe_data.primary_video.fps if probe_data.primary_video.fps > 0 else 30.0
                metadata = probe_data.raw_json or {}
            elif isinstance(probe_data, dict):
                metadata = probe_data
                duration_sec = float(probe_data.get("duration") or probe_data.get("duration_sec") or 30.0)
                width = int(probe_data.get("width") or 1920)
                height = int(probe_data.get("height") or 1080)
                fps = float(probe_data.get("fps") or probe_data.get("frame_rate") or 30.0)
        elif hasattr(media_input, "probe_metadata") and media_input.probe_metadata:
            meta = media_input.probe_metadata
            metadata = meta
            duration_sec = float(meta.get("duration") or meta.get("duration_sec") or 30.0)
            width = int(meta.get("width") or 1920)
            height = int(meta.get("height") or 1080)
            fps = float(meta.get("fps") or 30.0)

        # Enforce positive values & even dimensions for YUV video
        duration_sec = max(0.1, duration_sec)
        width = max(2, width - (width % 2))
        height = max(2, height - (height % 2))
        fps = max(1.0, fps)

        return job_id, source_video_path, duration_sec, (width, height), fps, metadata
