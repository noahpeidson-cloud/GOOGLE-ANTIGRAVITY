"""Pydantic v2 data schemas for Edit Decision Lists (EDL), media metadata, and job state."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from pydantic import BaseModel, Field, field_validator, model_validator


class JobStatus(str, Enum):
    """Lifecycle status states for a VideoJob."""
    PENDING = "PENDING"
    DETECTED = "DETECTED"
    INGESTING = "INGESTING"
    INGESTED = "INGESTED"
    PROBING = "PROBING"
    PROBED = "PROBED"
    ANALYZING = "ANALYZING"
    GRADING = "GRADING"
    ML_GRADING = "ML_GRADING"
    AWAITING_OVERRIDE = "AWAITING_OVERRIDE"
    OVERRIDDEN = "OVERRIDDEN"
    OVERRIDE_APPLIED = "OVERRIDE_APPLIED"
    APPROVED = "APPROVED"
    RENDERING = "RENDERING"
    DELIVERING = "DELIVERING"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ClipSegment(BaseModel):
    """Specification for an individual video clip segment within an EDL."""
    clip_id: str = Field(default_factory=lambda: f"seg_{uuid.uuid4().hex[:8]}")
    source_in_sec: float = Field(ge=0.0, description="Start timestamp in source video (seconds)")
    source_out_sec: float = Field(gt=0.0, description="End timestamp in source video (seconds)")
    timeline_in_sec: float = Field(default=0.0, ge=0.0, description="Placement timestamp on master timeline (seconds)")
    speed_multiplier: float = Field(default=1.0, gt=0.0, le=10.0, description="Playback speed multiplier")
    volume_multiplier: float = Field(default=1.0, ge=0.0, le=5.0, description="Segment volume scale factor")
    label: Optional[str] = Field(default=None, description="Descriptive semantic tag (e.g., 'drop', 'buildup')")

    @model_validator(mode="after")
    def validate_segment_bounds(self) -> "ClipSegment":
        if self.source_out_sec <= self.source_in_sec:
            raise ValueError(
                f"source_out_sec ({self.source_out_sec}) must be strictly greater than source_in_sec ({self.source_in_sec})"
            )
        return self

    @property
    def source_duration(self) -> float:
        """Original duration in source media."""
        return self.source_out_sec - self.source_in_sec

    @property
    def timeline_duration(self) -> float:
        """Effective duration on master timeline after speed adjustment."""
        return (self.source_out_sec - self.source_in_sec) / self.speed_multiplier

    @property
    def timeline_out_sec(self) -> float:
        """End timestamp on master timeline."""
        return self.timeline_in_sec + self.timeline_duration


class ColorGradeSettings(BaseModel):
    """Color correction and grading parameters compiled into FFmpeg eq / LUT filters."""
    contrast: float = Field(default=1.0, ge=0.0, le=3.0, description="Contrast multiplier (0.0 to 3.0)")
    brightness: float = Field(default=0.0, ge=-1.0, le=1.0, description="Brightness adjustment (-1.0 to 1.0)")
    saturation: float = Field(default=1.0, ge=0.0, le=3.0, description="Color saturation multiplier (0.0 to 3.0)")
    gamma: float = Field(default=1.0, ge=0.1, le=10.0, description="Global gamma balance (0.1 to 10.0)")
    gamma_r: Optional[float] = Field(default=None, ge=0.1, le=10.0, description="Red channel gamma")
    gamma_g: Optional[float] = Field(default=None, ge=0.1, le=10.0, description="Green channel gamma")
    gamma_b: Optional[float] = Field(default=None, ge=0.1, le=10.0, description="Blue channel gamma")

    def to_ffmpeg_eq_filter(self) -> str:
        """Compile color grade parameters into FFmpeg eq filter string."""
        parts = [
            f"contrast={self.contrast:.3f}",
            f"brightness={self.brightness:.3f}",
            f"saturation={self.saturation:.3f}",
            f"gamma={self.gamma:.3f}",
        ]
        if self.gamma_r is not None:
            parts.append(f"gamma_r={self.gamma_r:.3f}")
        if self.gamma_g is not None:
            parts.append(f"gamma_g={self.gamma_g:.3f}")
        if self.gamma_b is not None:
            parts.append(f"gamma_b={self.gamma_b:.3f}")
        return f"eq={':'.join(parts)}"


class AudioMasteringSettings(BaseModel):
    """Audio mastering parameters compiled into FFmpeg loudnorm / volume filters."""
    normalize_lufs: bool = Field(default=True, description="Enable EBU R128 loudness normalization")
    target_lufs: float = Field(default=-14.0, ge=-70.0, le=-5.0, description="Target integrated loudness in LUFS")
    peak_limit_db: float = Field(default=-1.5, ge=-20.0, le=0.0, description="Maximum true peak limit in dBFS")
    gain_db: float = Field(default=0.0, ge=-30.0, le=30.0, description="Manual post-gain trim in dB")
    dual_pass: bool = Field(default=False, description="Use dual-pass loudnorm analysis")

    def to_ffmpeg_audio_filter(self) -> str:
        """Compile audio mastering settings into an FFmpeg audio filter string."""
        filters: List[str] = []
        if self.normalize_lufs:
            filters.append(f"loudnorm=I={self.target_lufs:.1f}:TP={self.peak_limit_db:.1f}:LRA=11")
        if self.gain_db != 0.0:
            filters.append(f"volume={self.gain_db:.1f}dB")
        return ",".join(filters) if filters else "anull"


class EditDecisionList(BaseModel):
    """Complete Edit Decision List specifying cuts, trims, color grade, audio, and render targets."""
    job_id: str = Field(description="Associated VideoJob identifier")
    source_video_path: str = Field(description="Absolute or relative path to raw source video file")
    target_resolution: Tuple[int, int] = Field(default=(1920, 1080), description="(width, height) in pixels")
    target_fps: float = Field(default=30.0, gt=0.0, le=240.0, description="Target timeline frame rate")
    encoding_profile: str = Field(default="x264_crf17", description="Visual lossless encoder profile")
    segments: List[ClipSegment] = Field(default_factory=list, description="Ordered list of timeline segments")
    color_grade: ColorGradeSettings = Field(default_factory=ColorGradeSettings, description="Color grade settings")
    audio_mastering: AudioMasteringSettings = Field(default_factory=AudioMasteringSettings, description="Audio mastering")
    manual_override_applied: bool = Field(default=False, description="Flag set True if editor modified ML EDL")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("target_resolution")
    @classmethod
    def validate_resolution(cls, v: Tuple[int, int]) -> Tuple[int, int]:
        width, height = v
        if width <= 0 or height <= 0:
            raise ValueError(f"Resolution dimensions must be positive integers: got ({width}, {height})")
        if width % 2 != 0 or height % 2 != 0:
            raise ValueError(f"Resolution dimensions must be even for YUV420p video: got ({width}, {height})")
        return v

    @property
    def total_timeline_duration(self) -> float:
        """Calculate total continuous duration of the timeline across all segments."""
        return sum(seg.timeline_duration for seg in self.segments)

    @property
    def segment_count(self) -> int:
        """Total number of cut segments."""
        return len(self.segments)


class EDLOverridePayload(BaseModel):
    """Payload for partial or full EDL user overrides via API."""
    segments: Optional[List[ClipSegment]] = None
    color_grade: Optional[ColorGradeSettings] = None
    audio_mastering: Optional[AudioMasteringSettings] = None
    target_resolution: Optional[Tuple[int, int]] = None
    target_fps: Optional[float] = None
    encoding_profile: Optional[str] = None


class VideoStreamMetadata(BaseModel):
    """Metadata for an individual video stream extracted by FFprobe."""
    index: int = 0
    codec_name: str
    codec_long_name: Optional[str] = None
    profile: Optional[str] = None
    width: int
    height: int
    aspect_ratio: Optional[str] = None
    fps: float
    pixel_format: str
    bitrate: Optional[int] = None
    duration_sec: Optional[float] = None
    nb_frames: Optional[int] = None
    color_space: Optional[str] = None
    color_transfer: Optional[str] = None
    color_primaries: Optional[str] = None


class AudioStreamMetadata(BaseModel):
    """Metadata for an individual audio stream extracted by FFprobe."""
    index: int = 0
    codec_name: str
    codec_long_name: Optional[str] = None
    sample_rate: int
    channels: int
    channel_layout: Optional[str] = None
    bitrate: Optional[int] = None
    duration_sec: Optional[float] = None


class MediaProbeResult(BaseModel):
    """Parsed and normalized result of FFprobe execution."""
    filepath: str
    format_name: str
    format_long_name: Optional[str] = None
    duration_sec: float = 0.0
    size_bytes: int = 0
    bitrate: Optional[int] = None
    video_streams: List[VideoStreamMetadata] = Field(default_factory=list)
    audio_streams: List[AudioStreamMetadata] = Field(default_factory=list)
    raw_json: Optional[Dict[str, Any]] = None

    @property
    def has_video(self) -> bool:
        return len(self.video_streams) > 0

    @property
    def has_audio(self) -> bool:
        return len(self.audio_streams) > 0

    @property
    def primary_video(self) -> Optional[VideoStreamMetadata]:
        return self.video_streams[0] if self.video_streams else None

    @property
    def primary_audio(self) -> Optional[AudioStreamMetadata]:
        return self.audio_streams[0] if self.audio_streams else None

    @property
    def width(self) -> int:
        return self.primary_video.width if self.primary_video else 0

    @property
    def height(self) -> int:
        return self.primary_video.height if self.primary_video else 0

    @property
    def fps(self) -> float:
        return self.primary_video.fps if self.primary_video else 0.0


class VideoJob(BaseModel):
    """Complete in-memory model representing a video processing job in the brain pipeline."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_filepath: str
    filename: Optional[str] = None
    file_size_bytes: int = 0
    status: JobStatus = JobStatus.DETECTED
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    active_edl: Optional[EditDecisionList] = None
    probe_data: Optional[MediaProbeResult] = None
    probe_metadata: Optional[Dict[str, Any]] = None
    delivery_filepath: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def populate_filename(self) -> "VideoJob":
        if not self.filename and self.source_filepath:
            self.filename = Path(self.source_filepath).name
        return self


# JobMetadata is an alias/representation of VideoJob for lightweight metadata responses
JobMetadata = VideoJob
