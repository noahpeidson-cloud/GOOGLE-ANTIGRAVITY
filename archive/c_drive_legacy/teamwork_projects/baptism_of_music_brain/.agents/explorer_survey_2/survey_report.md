# Survey & Architectural Design Report: Gemini Omni ML Grading & FastAPI Brain Interface
**Project:** `baptism_of_music_brain`  
**Explorer:** `explorer_survey_2` (ML & API Specialist)  
**Date:** 2026-08-27  
**Status:** COMPLETE & GROUNDED

---

## 1. Executive Summary

The `baptism_of_music_brain` project creates an enterprise-grade, zero-friction autonomous machine learning Video Editing Brain and Renderer. It intercepts raw 4K footage arriving from a local mobile ingestion bridge (e.g. Samsung S26 Ultra via ADB Wi-Fi or local folder sync), analyzes the synchronous audiovisual streams using a **Gemini Omni Multimodal ML feedback loop**, constructs a structured **Edit Decision List (EDL)** (cuts, trims, color grades, audio EQ/normalization, speed ramps, and transitions), exposes a high-performance **FastAPI REST API** for inspection and manual user overrides, executes lossless rendering via desktop-class **FFmpeg**, and exports the finalized master video to a `delivery/` directory.

This report establishes the complete specification for:
1. The **Gemini Omni ML Grading & Autonomous Edit Decision Feedback Loop**.
2. Strict **Pydantic v2 Data Models & JSON Schemas** for the EDL, pipeline state, and job metadata.
3. The **FastAPI REST API Interface**, including endpoints for job querying, manual overrides, one-click approval, and video streaming.
4. The **Offline Deterministic Mock ML Grading Engine** for zero-dependency CI/CD and unit testing.

---

## 2. End-to-End System Architecture

```
[ Ingest Directory (`ingest/`) ]
         │
         ▼ (File Watcher / Lock Detection)
[ FastAPI Brain Service (`brain/`) ]
         │
         ├──► [ Ingestion & Metadata Prober (ffprobe / imageio_ffmpeg) ]
         │
         ├──► [ Gemini Omni Multimodal ML Loop ] ── (or Deterministic Mock Engine in CI)
         │           │
         │           ▼
         │    [ Synthesized Edit Decision List (EDL v1) ]
         │           │
         ├──► [ FastAPI REST API & WebSocket / SSE ] ◄──► [ Web UI / Mobile Client ]
         │           │   - GET /jobs/{id}/edl                  (Manual Overrides: trims,
         │           │   - PUT /jobs/{id}/edl                  color LUT, audio, speed)
         │           │   - POST /jobs/{id}/approve
         │           ▼
         ├──► [ High-Fidelity FFmpeg Renderer ]
         │           │   (Filter Graph Builder: trims, speed ramps, LUT, loudnorm, x264 CRF 17)
         │           ▼
         └──► [ Delivery Directory (`delivery/`) ] ──► [ Bridge to Samsung Gallery ]
```

---

## 3. Gemini Omni ML Grading & Edit Decision Feedback Loop

### 3.1 Analysis Objectives & Input Handling
When a raw 4K video arrives in `ingest/`:
1. **Metadata Probe**: `ffprobe` extracts exact duration, resolution, frame rate, container, video stream bitrate/pixel format, and audio stream channel layout/sample rate.
2. **Multimodal Ingestion**:
   - For fast processing and API limits (where Gemini video uploads are optimized for ≤25MB clips or ≤720p resolution), the pipeline generates a lightweight 720p 30fps proxy video.
   - The video is uploaded to the Google GenAI Files API (`client.files.upload()`) or passed via Cloud Storage / local URI parts.
3. **Multimodal Analysis Directives**:
   - **Hook Retention Velocity (HRV)**: Evaluates kinetic energy in [0.0s - 3.0s]. Detects subject movement, rapid camera zoom, or pattern interrupts.
   - **Drop Pacing & Anticipation Window (DPAW)**: Scans audio waveform and spectral flux to locate EDM build-up risers, pre-drop silence pockets (100–300ms), and bass drop transients.
   - **Audio Dynamic Range & Spectral Flux (ADR-SFD)**: Measures sub-bass punch (30–90Hz), RMS loudness jumps, and detects audio clipping.
   - **Crowd Kinetic Energy & Motion Vector Entropy (CKE-MVE)**: Quantifies crowd movement, jumping coherence, and stage energy.
   - **Lighting Transition & Strobe Peak Synchronicity (LTSS)**: Identifies strobe modulation, laser fans, CO2 cryo jets, and pyro bursts.

### 3.2 Autonomous Edit Decision Generation (EDL Synthesis)
The ML model converts raw multimodal grading into concrete editing instructions:
- **Cuts & Trims**: Slices the source video into structured segments:
  - *Clip 1 (Hook)*: 0.0s to 3.0s — Highest impact intro frame.
  - *Clip 2 (Buildup)*: Tension build-up preceding the drop (e.g. drop - 4.5s to drop).
  - *Clip 3 (Drop Explosion)*: Bass drop impact with slow-motion time remap (e.g. 0.5x speed for 3s).
  - *Clip 4 (Outro/Loop)*: Seamless loop exit back to start.
- **Transitions**: Adds dynamic video transitions (e.g. `FLASH_WHITE` at drop downbeat, `WHIP_RIGHT` between scene changes, `CROSSFADE` for ambient sections).
- **Color Grading & Filters**:
  - Sets tone curve: Brightness, contrast, saturation, gamma.
  - Applies color look: `CONCERT_PUNCH` (vibrant saturated neon with crushed blacks), `TEAL_ORANGE`, `NEON_CYBERPUNK`, or custom `.cube` 3D LUT.
  - Adds unsharp masking (`unsharp=5:5:0.8:5:5:0.4`) and optional subtle vignette.
- **Audio Mastering**:
  - Normalizes audio to streaming standard: Target `-14.0 LUFS`, `-1.0 dBFS` true peak limit.
  - Applies dynamic EQ: `+2.5 dB` boost at 50Hz (sub-bass punch), `+1.5 dB` boost at 10kHz (air/high frequencies).
  - Adds subtle fade-in (0.1s) and fade-out (0.3s) to prevent speaker popping.
- **Speed Ramping (Time Remap)**:
  - Accelerates build-up tension to 1.5x speed.
  - Drops into 0.5x slow-motion on the primary bass drop downbeat using motion-interpolated blending.

### 3.3 Turn-by-Turn Iteration & Re-Grading Prompt
If a user requests re-grading with custom creative constraints (e.g. *"Focus more on the laser show and make the color grade moody cyber-noir"*), the Gemini client passes the previous EDL and interaction history to generate an updated `v2` EDL.

---

## 4. Complete Pydantic v2 Data Models & JSON Schemas

Below is the authoritative, production-ready Pydantic v2 schema architecture:

```python
"""
Pydantic v2 Schemas for Edit Decision Lists, Pipeline State, and Job Metadata.
Module: baptism_of_music_brain.schemas
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ============================================================================
# 1. ENUMS & CONSTANTS
# ============================================================================

class JobStatus(str, enum.Enum):
    PENDING_INGEST = "PENDING_INGEST"
    INGESTING = "INGESTING"
    INGESTED = "INGESTED"
    ANALYZING_ML = "ANALYZING_ML"
    EDL_READY = "EDL_READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    RENDERING = "RENDERING"
    RENDERED = "RENDERED"
    DELIVERING = "DELIVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TransitionType(str, enum.Enum):
    CUT = "CUT"
    CROSSFADE = "CROSSFADE"
    FADE_BLACK = "FADE_BLACK"
    FLASH_WHITE = "FLASH_WHITE"
    WHIP_LEFT = "WHIP_LEFT"
    WHIP_RIGHT = "WHIP_RIGHT"
    ZOOM_IN = "ZOOM_IN"
    GLITCH = "GLITCH"
    DISSOLVE = "DISSOLVE"


class ColorPreset(str, enum.Enum):
    RAW_PASSTHROUGH = "RAW_PASSTHROUGH"
    TEAL_ORANGE = "TEAL_ORANGE"
    NEON_CYBERPUNK = "NEON_CYBERPUNK"
    GOLDEN_HOUR = "GOLDEN_HOUR"
    CONCERT_PUNCH = "CONCERT_PUNCH"
    HIGH_CONTRAST_MONO = "HIGH_CONTRAST_MONO"
    CUSTOM = "CUSTOM"


class SpeedInterpolation(str, enum.Enum):
    NEAREST = "NEAREST"
    BLEND = "BLEND"
    OPTICAL_FLOW_MOTION = "OPTICAL_FLOW_MOTION"


class VideoCodec(str, enum.Enum):
    LIBX264 = "libx264"
    HEVC_NVENC = "hevc_nvenc"
    LIBX265 = "libx265"
    H264_NVENC = "h264_nvenc"
    PRORES = "prores_ks"


class AudioCodec(str, enum.Enum):
    AAC = "aac"
    PCM_S16LE = "pcm_s16le"
    FLAC = "flac"


class AspectRatio(str, enum.Enum):
    RATIO_9_16 = "9:16"
    RATIO_16_9 = "16:9"
    RATIO_1_1 = "1:1"
    RATIO_4_5 = "4:5"


# ============================================================================
# 2. EDL TIMELINE & EFFECT COMPONENTS
# ============================================================================

class ClipSegment(BaseModel):
    """Represents a single cut/trim segment extracted from source video."""
    model_config = ConfigDict(validate_assignment=True)

    clip_id: str = Field(..., description="Unique clip identifier, e.g. 'clip_1'.")
    source_path: str = Field(..., description="Absolute path or URI to source media.")
    source_in_sec: float = Field(..., ge=0.0, description="Start timestamp in source video.")
    source_out_sec: float = Field(..., ge=0.0, description="End timestamp in source video.")
    timeline_in_sec: float = Field(..., ge=0.0, description="Start placement in final timeline.")
    speed_multiplier: float = Field(1.0, gt=0.0, le=8.0, description="Playback speed factor.")
    volume_multiplier: float = Field(1.0, ge=0.0, le=4.0, description="Audio volume multiplier.")
    label: Optional[str] = Field(None, description="Segment semantic label (hook, drop, outro).")

    @property
    def source_duration(self) -> float:
        return max(0.0, self.source_out_sec - self.source_in_sec)

    @property
    def timeline_duration(self) -> float:
        return self.source_duration / self.speed_multiplier

    @model_validator(mode="after")
    def validate_in_out(self) -> ClipSegment:
        if self.source_out_sec <= self.source_in_sec:
            raise ValueError(f"source_out_sec ({self.source_out_sec}) must be greater than source_in_sec ({self.source_in_sec})")
        return self


class TransitionEffect(BaseModel):
    """Defines a visual transition between clips."""
    model_config = ConfigDict(validate_assignment=True)

    transition_id: str = Field(..., description="Unique transition ID.")
    type: TransitionType = Field(default=TransitionType.CROSSFADE)
    from_clip_id: Optional[str] = Field(None, description="Preceding clip ID.")
    to_clip_id: Optional[str] = Field(None, description="Succeeding clip ID.")
    timeline_offset_sec: float = Field(..., ge=0.0, description="Timeline timestamp where transition starts.")
    duration_sec: float = Field(0.3, gt=0.0, le=3.0, description="Transition duration in seconds.")
    easing: Literal["linear", "ease_in_out"] = "ease_in_out"


class ColorGradeSettings(BaseModel):
    """Color correction, LUT application, and visual filtering parameters."""
    model_config = ConfigDict(validate_assignment=True)

    preset: ColorPreset = Field(default=ColorPreset.CONCERT_PUNCH)
    brightness: float = Field(0.0, ge=-1.0, le=1.0, description="Brightness offset.")
    contrast: float = Field(1.15, ge=0.0, le=3.0, description="Contrast multiplier.")
    saturation: float = Field(1.25, ge=0.0, le=3.0, description="Color saturation multiplier.")
    gamma: float = Field(1.0, ge=0.1, le=5.0, description="Gamma correction factor.")
    temperature_kelvin: Optional[int] = Field(None, ge=2000, le=12000, description="White balance temp.")
    lut_file: Optional[str] = Field(None, description="Path to .cube 3D LUT file.")
    lut_strength: float = Field(1.0, ge=0.0, le=1.0, description="LUT opacity blend factor.")
    sharpness: float = Field(0.2, ge=0.0, le=2.0, description="Unsharp mask strength.")
    vignette_strength: float = Field(0.0, ge=0.0, le=1.0, description="Vignette shading intensity.")


class AudioMasteringSettings(BaseModel):
    """Audio EQ, loudness normalization, and mastering parameters."""
    model_config = ConfigDict(validate_assignment=True)

    normalize_lufs: bool = Field(True, description="Enable EBU R128 loudness normalization.")
    target_lufs: float = Field(-14.0, ge=-30.0, le=-6.0, description="Target integrated LUFS.")
    peak_limit_db: float = Field(-1.0, ge=-6.0, le=0.0, description="True peak ceiling in dBFS.")
    sub_bass_boost_db: float = Field(2.5, ge=-12.0, le=12.0, description="Low-end boost at 50Hz in dB.")
    treble_boost_db: float = Field(1.5, ge=-12.0, le=12.0, description="High-frequency boost at 10kHz in dB.")
    fade_in_sec: float = Field(0.1, ge=0.0, le=2.0, description="Audio fade-in duration.")
    fade_out_sec: float = Field(0.3, ge=0.0, le=3.0, description="Audio fade-out duration.")
    sidechain_ducking: bool = Field(False, description="Enable dynamic audio ducking.")


class SpeedRampSegment(BaseModel):
    """Dynamic speed ramping keypoint."""
    model_config = ConfigDict(validate_assignment=True)

    start_sec: float = Field(..., ge=0.0)
    end_sec: float = Field(..., ge=0.0)
    speed_factor: float = Field(0.5, gt=0.0, le=8.0)
    interpolation: SpeedInterpolation = Field(default=SpeedInterpolation.BLEND)

    @model_validator(mode="after")
    def validate_ramp_bounds(self) -> SpeedRampSegment:
        if self.end_sec <= self.start_sec:
            raise ValueError(f"end_sec ({self.end_sec}) must be greater than start_sec ({self.start_sec})")
        return self


class ExportSettings(BaseModel):
    """FFmpeg rendering and encoding configuration."""
    model_config = ConfigDict(validate_assignment=True)

    video_codec: VideoCodec = Field(default=VideoCodec.LIBX264)
    crf: Optional[int] = Field(17, ge=0, le=51, description="Visually lossless CRF value (0=lossless, 17=high fidelity).")
    bitrate_kbps: Optional[int] = Field(None, ge=1000, description="Target video bitrate if CRF not used.")
    preset: str = Field("slow", description="Encoder speed/compression preset (e.g. slow, medium, p4).")
    pixel_format: str = Field("yuv420p", description="Pixel format (yuv420p or yuv420p10le).")
    target_resolution: Optional[str] = Field("1080x1920", pattern=r"^\d+x\d+$", description="Target WxH.")
    target_fps: Optional[float] = Field(60.0, gt=0.0, le=120.0, description="Output frame rate.")
    audio_codec: AudioCodec = Field(default=AudioCodec.AAC)
    audio_bitrate_kbps: int = Field(320, ge=64, le=640, description="Audio bitrate in kbps.")


# ============================================================================
# 3. ROOT EDIT DECISION LIST (EDL) SCHEMA
# ============================================================================

class EditDecisionList(BaseModel):
    """Complete, self-contained Edit Decision List for video assembly and rendering."""
    model_config = ConfigDict(validate_assignment=True)

    edl_id: str = Field(..., description="Unique UUID for this EDL.")
    job_id: str = Field(..., description="Associated parent job ID.")
    version: int = Field(1, ge=1, description="EDL revision number.")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_video_path: str = Field(..., description="Path to source raw video file.")
    source_metadata: Dict[str, Any] = Field(default_factory=dict, description="Probed video/audio metadata.")
    aspect_ratio: AspectRatio = Field(default=AspectRatio.RATIO_9_16)
    clips: List[ClipSegment] = Field(default_factory=list, min_length=1, description="Ordered clip segments.")
    transitions: List[TransitionEffect] = Field(default_factory=list, description="Transitions between clips.")
    color_grade: ColorGradeSettings = Field(default_factory=ColorGradeSettings)
    audio_mastering: AudioMasteringSettings = Field(default_factory=AudioMasteringSettings)
    speed_ramps: List[SpeedRampSegment] = Field(default_factory=list)
    export_settings: ExportSettings = Field(default_factory=ExportSettings)
    ml_rationale: Optional[str] = Field(None, description="Gemini AI reasoning for edit decisions.")
    user_approved: bool = Field(False, description="Whether human has explicitly approved this EDL.")


# ============================================================================
# 4. JOB METADATA & PIPELINE STATE
# ============================================================================

class JobMetadata(BaseModel):
    """Comprehensive state tracking for a video ingestion and rendering lifecycle."""
    model_config = ConfigDict(validate_assignment=True)

    job_id: str = Field(..., description="Unique alphanumeric job identifier.")
    source_filename: str = Field(..., description="Original filename in ingest folder.")
    source_filepath: str = Field(..., description="Absolute path to raw ingest video.")
    file_size_bytes: int = Field(..., ge=0)
    sha256_hash: str = Field(..., description="SHA-256 cryptographic checksum.")
    status: JobStatus = Field(default=JobStatus.PENDING_INGEST)
    current_step: str = Field("Initialized", description="Current human-readable pipeline stage.")
    progress_percent: float = Field(0.0, ge=0.0, le=100.0, description="Overall task completion %.")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = Field(0, ge=0)
    active_edl: Optional[EditDecisionList] = None
    proxy_filepath: Optional[str] = None
    rendered_output_filepath: Optional[str] = None
    delivery_filepath: Optional[str] = None
    render_stats: Optional[Dict[str, Any]] = None
    dlq_record: Optional[Dict[str, Any]] = None


# ============================================================================
# 5. REST API REQUEST & RESPONSE SCHEMAS
# ============================================================================

class EDLOverridePayload(BaseModel):
    """Payload allowing users to partially or completely override EDL decisions."""
    model_config = ConfigDict(validate_assignment=True)

    clips: Optional[List[ClipSegment]] = None
    color_grade: Optional[ColorGradeSettings] = None
    audio_mastering: Optional[AudioMasteringSettings] = None
    transitions: Optional[List[TransitionEffect]] = None
    speed_ramps: Optional[List[SpeedRampSegment]] = None
    export_settings: Optional[ExportSettings] = None
    notes: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request to approve EDL and optionally initiate immediate rendering."""
    model_config = ConfigDict(validate_assignment=True)

    approved: bool = Field(True, description="Approval flag.")
    override_payload: Optional[EDLOverridePayload] = None
    render_immediately: bool = Field(True, description="Immediately queue FFmpeg render job.")


class RegradeRequest(BaseModel):
    """Request to re-run Gemini ML grading with custom feedback instructions."""
    model_config = ConfigDict(validate_assignment=True)

    custom_prompt: Optional[str] = Field(None, max_length=1000, description="Custom steering prompt.")
    target_duration_sec: Optional[float] = Field(None, ge=3.0, le=60.0)
    target_aspect_ratio: Optional[AspectRatio] = None


class JobListResponse(BaseModel):
    """Paginated list of jobs."""
    jobs: List[JobMetadata]
    total: int
    page: int
    limit: int


class SystemHealthResponse(BaseModel):
    """System health check and environmental telemetry."""
    status: Literal["healthy", "degraded", "error"]
    ffmpeg_available: bool
    ffmpeg_version: Optional[str] = None
    ffmpeg_binary_path: Optional[str] = None
    nvenc_hardware_accel: bool = False
    gemini_mode: Literal["live", "mock"] = "mock"
    ingest_directory: str
    delivery_directory: str
    active_jobs_count: int
    disk_free_gb: float
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
```

---

## 5. FastAPI REST API Interface Specification

The FastAPI application provides a comprehensive REST and real-time streaming API to monitor the video pipeline, inspect generated EDLs, apply manual overrides, and trigger desktop-class rendering.

### 5.1 Route Summary Table

| HTTP Method | Route Path | Summary / Action | Request Model | Response Model / Output | Status Code |
|:---|:---|:---|:---|:---|:---|
| `GET` | `/api/v1/health` | System diagnostics & environment health | None | `SystemHealthResponse` | 200 OK |
| `GET` | `/api/v1/jobs` | Query/list all jobs (filtered by status) | Query params (`status`, `limit`, `page`) | `JobListResponse` | 200 OK |
| `GET` | `/api/v1/jobs/{job_id}` | Retrieve single job state and progress | Path `job_id` | `JobMetadata` | 200 OK, 404 |
| `GET` | `/api/v1/jobs/{job_id}/edl` | Get active Edit Decision List | Path `job_id` | `EditDecisionList` | 200 OK, 404 |
| `PUT` | `/api/v1/jobs/{job_id}/edl` | Apply manual user overrides to EDL | Path `job_id`, Body `EDLOverridePayload` | `EditDecisionList` | 200 OK, 400, 404 |
| `POST` | `/api/v1/jobs/{job_id}/approve` | Approve EDL & trigger FFmpeg render | Path `job_id`, Body `ApprovalRequest` | `JobMetadata` | 202 Accepted, 400 |
| `POST` | `/api/v1/jobs/{job_id}/regrade` | Trigger Gemini re-grading with prompt | Path `job_id`, Body `RegradeRequest` | `JobMetadata` | 202 Accepted, 400 |
| `POST` | `/api/v1/jobs/{job_id}/render` | Force re-render with current EDL | Path `job_id` | `JobMetadata` | 202 Accepted, 409 |
| `GET` | `/api/v1/jobs/{job_id}/proxy` | Stream 720p proxy video for scrubbing | Path `job_id` (supports HTTP Range) | `StreamingResponse` (video/mp4) | 200 / 206 Partial |
| `GET` | `/api/v1/jobs/{job_id}/events` | Server-Sent Events (SSE) live progress | Path `job_id` | `text/event-stream` | 200 OK |
| `POST` | `/api/v1/ingest/scan` | Manually trigger filesystem ingest scan | None | `{"scanned_files": int, "new_jobs": int}` | 200 OK |

---

### 5.2 Key Endpoint Specifications & Request Flows

#### 1. System Health Check (`GET /api/v1/health`)
Checks local FFmpeg binary (from `imageio_ffmpeg` or system PATH), checks if NVIDIA NVENC hardware acceleration is present, confirms `ingest/` and `delivery/` directories exist, and reports disk capacity.
```json
{
  "status": "healthy",
  "ffmpeg_available": true,
  "ffmpeg_version": "7.1",
  "ffmpeg_binary_path": "C:\\Users\\noahp\\AppData\\Local\\Packages\\...\\ffmpeg-win-x86_64-v7.1.exe",
  "nvenc_hardware_accel": false,
  "gemini_mode": "mock",
  "ingest_directory": "C:\\Users\\noahp\\teamwork_projects\\baptism_of_music_brain\\ingest",
  "delivery_directory": "C:\\Users\\noahp\\teamwork_projects\\baptism_of_music_brain\\delivery",
  "active_jobs_count": 1,
  "disk_free_gb": 412.5,
  "timestamp": "2026-08-27T10:02:50Z"
}
```

#### 2. Manual User Override Workflow (`PUT /api/v1/jobs/{job_id}/edl`)
Allows the user to adjust start/end timestamps, swap color grading presets (e.g. from `CONCERT_PUNCH` to `NEON_CYBERPUNK`), modify speed ramp factors, or toggle audio loudness normalization before rendering.

**Example Request Payload:**
```json
{
  "clips": [
    {
      "clip_id": "clip_1",
      "source_path": "C:\\Users\\noahp\\...\\raw_drop.mp4",
      "source_in_sec": 2.5,
      "source_out_sec": 5.5,
      "timeline_in_sec": 0.0,
      "speed_multiplier": 1.0,
      "label": "custom_hook"
    },
    {
      "clip_id": "clip_2",
      "source_path": "C:\\Users\\noahp\\...\\raw_drop.mp4",
      "source_in_sec": 14.0,
      "source_out_sec": 22.0,
      "timeline_in_sec": 3.0,
      "speed_multiplier": 0.5,
      "label": "bass_drop_slowmo"
    }
  ],
  "color_grade": {
    "preset": "NEON_CYBERPUNK",
    "contrast": 1.30,
    "saturation": 1.40,
    "sharpness": 0.3
  },
  "audio_mastering": {
    "normalize_lufs": true,
    "target_lufs": -14.0,
    "sub_bass_boost_db": 3.5
  }
}
```

#### 3. One-Click Approval & Render (`POST /api/v1/jobs/{job_id}/approve`)
Once the user confirms the EDL, calling `/approve` sets `job.status = APPROVED`, spawns a background asyncio task to execute FFmpeg rendering, and streams stdout progress percentage to the UI.

#### 4. Video Streaming with HTTP Range Header (`GET /api/v1/jobs/{job_id}/proxy`)
To ensure smooth scrubbing in HTML5 `<video>` players without downloading entire multi-gigabyte 4K files, this endpoint serves the generated 720p proxy with full `HTTP 206 Partial Content` chunked streaming.

---

## 6. Deterministic Mock/Fallback ML Grading Engine

For offline testing, local CI/CD pipelines, and environments without active Gemini API keys or network connectivity, the system includes a **Deterministic Mock ML Grading Engine**.

### 6.1 Deterministic Scoring Mechanism
The mock engine uses a stable hash of the video's identifier or file metadata (MD5 / SHA-256) to deterministically derive realistic EDM viral parameter scores:

```python
import hashlib
from typing import Dict, List, Optional
from baptism_of_music_brain.schemas import (
    AspectRatio,
    AudioMasteringSettings,
    ClipSegment,
    ColorGradeSettings,
    ColorPreset,
    EditDecisionList,
    ExportSettings,
    SpeedInterpolation,
    SpeedRampSegment,
    TransitionEffect,
    TransitionType,
    VideoCodec,
)

class DeterministicMockGradingEngine:
    """
    Offline deterministic grading and EDL synthesis engine.
    Produces repeatable, valid EditDecisionLists without network or GPU access.
    """

    @staticmethod
    def generate_mock_edl(
        job_id: str,
        source_video_path: str,
        duration_seconds: float = 30.0,
        aspect_ratio: AspectRatio = AspectRatio.RATIO_9_16,
    ) -> EditDecisionList:
        # Seed pseudo-random values from job_id hash
        seed = int(hashlib.md5(f"{job_id}_{source_video_path}".encode()).hexdigest()[:8], 16)
        
        # Calculate dynamic timestamps
        hook_end = min(3.0, duration_seconds * 0.15)
        drop_time = round(duration_seconds * 0.52, 2)
        buildup_start = max(hook_end, drop_time - 4.5)
        drop_end = min(duration_seconds, drop_time + 8.0)
        
        # 1. Synthesize sub-clip segments
        clips = [
            ClipSegment(
                clip_id="clip_hook",
                source_path=source_video_path,
                source_in_sec=0.0,
                source_out_sec=hook_end,
                timeline_in_sec=0.0,
                speed_multiplier=1.0,
                volume_multiplier=1.0,
                label="hook",
            ),
            ClipSegment(
                clip_id="clip_buildup",
                source_path=source_video_path,
                source_in_sec=buildup_start,
                source_out_sec=drop_time,
                timeline_in_sec=hook_end,
                speed_multiplier=1.25, # Slight acceleration
                volume_multiplier=1.0,
                label="buildup",
            ),
            ClipSegment(
                clip_id="clip_drop",
                source_path=source_video_path,
                source_in_sec=drop_time,
                source_out_sec=drop_end,
                timeline_in_sec=hook_end + ((drop_time - buildup_start) / 1.25),
                speed_multiplier=0.5, # 2x Slow-motion impact
                volume_multiplier=1.1,
                label="drop_impact",
            ),
        ]
        
        # 2. Synthesize transitions
        transitions = [
            TransitionEffect(
                transition_id="trans_1",
                type=TransitionType.WHIP_RIGHT,
                from_clip_id="clip_hook",
                to_clip_id="clip_buildup",
                timeline_offset_sec=hook_end,
                duration_sec=0.25,
            ),
            TransitionEffect(
                transition_id="trans_2",
                type=TransitionType.FLASH_WHITE,
                from_clip_id="clip_buildup",
                to_clip_id="clip_drop",
                timeline_offset_sec=hook_end + ((drop_time - buildup_start) / 1.25),
                duration_sec=0.15,
            ),
        ]
        
        # 3. Assemble full EDL
        return EditDecisionList(
            edl_id=f"edl_{job_id[:8]}",
            job_id=job_id,
            version=1,
            source_video_path=source_video_path,
            source_metadata={
                "duration_seconds": duration_seconds,
                "aspect_ratio": aspect_ratio.value,
                "simulated": True,
            },
            aspect_ratio=aspect_ratio,
            clips=clips,
            transitions=transitions,
            color_grade=ColorGradeSettings(
                preset=ColorPreset.CONCERT_PUNCH,
                contrast=1.20,
                saturation=1.30,
                sharpness=0.25,
            ),
            audio_mastering=AudioMasteringSettings(
                normalize_lufs=True,
                target_lufs=-14.0,
                sub_bass_boost_db=2.5,
                treble_boost_db=1.5,
            ),
            speed_ramps=[
                SpeedRampSegment(
                    start_sec=drop_time,
                    end_sec=drop_time + 3.0,
                    speed_factor=0.5,
                    interpolation=SpeedInterpolation.BLEND,
                )
            ],
            export_settings=ExportSettings(
                video_codec=VideoCodec.LIBX264,
                crf=17,
                preset="slow",
                pixel_format="yuv420p",
                target_resolution="1080x1920" if aspect_ratio == AspectRatio.RATIO_9_16 else "3840x2160",
                target_fps=60.0,
            ),
            ml_rationale=(
                f"Deterministic ML Grade: Detected peak drop at {drop_time}s. "
                "Synthesized 3-segment retention curve with 0.5x slow-mo on drop impact."
            ),
            user_approved=False,
        )
```

---

## 7. FFmpeg Rendering Pipeline Contract

The FFmpeg rendering engine parses the Pydantic `EditDecisionList` and constructs an optimized, single-pass FFmpeg command using complex filtergraphs (`-filter_complex`):

### 7.1 Complex Filtergraph Assembly
1. **Video Slicing & Speed Ramping**:
   - `[0:v]trim=start=0:end=3,setpts=PTS-STARTPTS[v0];`
   - `[0:v]trim=start=10.5:end=15,setpts=PTS-STARTPTS,setpts=PTS/1.25[v1];`
   - `[0:v]trim=start=15:end=23,setpts=PTS-STARTPTS,setpts=2.0*PTS[v2];`
2. **Concatenation & Transitions**:
   - `[v0][v1][v2]concat=n=3:v=1:a=0[v_concat];`
3. **Color Grading & Sharpening**:
   - `[v_concat]eq=contrast=1.2:saturation=1.3:brightness=0.02,unsharp=5:5:0.8:5:5:0.4[v_graded];`
4. **Framing & Aspect Ratio Scaling**:
   - `[v_graded]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v_out];`
5. **Audio Mastering & EBU R128 Loudness Normalization**:
   - `[0:a]atrim=start=0:end=3,asetpts=PTS-STARTPTS[a0];`
   - `[0:a]atrim=start=10.5:end=15,asetpts=PTS-STARTPTS,atempo=1.25[a1];`
   - `[0:a]atrim=start=15:end=23,asetpts=PTS-STARTPTS,atempo=0.5[a2];`
   - `[a0][a1][a2]concat=n=3:v=0:a=1[a_concat];`
   - `[a_concat]equalizer=f=50:t=q:w=1.0:g=2.5,equalizer=f=10000:t=q:w=1.0:g=1.5,loudnorm=I=-14:TP=-1.0:LRA=11[a_out]`
6. **Lossless Encoding Profile**:
   - `-c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p -c:a aac -b:a 320k`
   - (Or `-c:v hevc_nvenc -cq 18 -preset p7 -pix_fmt yuv420p10le` if NVIDIA GPU is present).

---

## 8. Directory & Implementation Roadmap

```
baptism_of_music_brain/
├── config/
│   └── settings.py              # Environment variables, directory paths, API keys
├── schemas/
│   ├── __init__.py
│   ├── edl.py                   # EditDecisionList, ClipSegment, Transitions, Color/Audio
│   ├── job.py                   # JobMetadata, JobStatus, PipelineState
│   └── api.py                   # Request/Response models for FastAPI routes
├── ml/
│   ├── __init__.py
│   ├── gemini_client.py         # Google GenAI multimodal video analysis client
│   ├── deterministic_mock.py    # Offline mock grading engine
│   └── prompt_templates.py      # Structured system prompts and analysis instructions
├── api/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app factory, CORS, error handlers
│   ├── routes_jobs.py           # Job listing, status, EDL inspection & overrides
│   ├── routes_health.py         # Health checks, FFmpeg diagnostics
│   └── streaming.py             # HTTP Range byte streaming for proxy playback
├── renderer/
│   ├── __init__.py
│   ├── ffmpeg_builder.py        # Translates EDL into FFmpeg filter_complex command
│   ├── render_executor.py       # Asynchronous process runner with stdout progress parser
│   └── probe.py                 # ffprobe wrapper for media metadata extraction
├── watcher/
│   ├── __init__.py
│   └── file_watcher.py          # Watchdog daemon detecting new video arrivals in ingest/
└── tests/
    ├── conftest.py              # Pytest fixtures, test media generators, mock clients
    ├── test_schemas.py          # Validation tests for EDL and Job models
    ├── test_mock_grading.py     # Deterministic ML engine tests
    ├── test_api_routes.py       # FastAPI TestClient endpoint assertions
    └── test_ffmpeg_renderer.py  # FFmpeg command generation & ffprobe assertion
```

---

## 9. Verification & Quality Assurance Strategy

1. **Schema Integrity**:
   - 100% Pydantic validation coverage ensuring negative timestamps, invalid aspect ratios, and mismatched clip durations raise clear `ValidationError` exceptions.
2. **API Endpoint Verification**:
   - `fastapi.testclient.TestClient` test suite asserting 200/202 responses for job creation, EDL overrides, and approval cycles.
3. **FFmpeg Visual Losslessness & Output Assertion**:
   - `ffprobe` programmatic inspection verifying rendered videos match CRF 17 target bitrate (e.g. >20 Mbps for 4K / >8 Mbps for 1080p), 60fps, and -14 LUFS audio.
4. **Offline Determinism**:
   - Full integration test suite executable in <10 seconds without active internet or Google Cloud credentials.
