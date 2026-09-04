# Milestone 1 Architecture & Implementation Blueprint: Models, Settings & FFprobe

**Author**: Explorer 1  
**Milestone**: Milestone 1 (Core Models, Ingest & Locking)  
**Target Subsystems**: `config/settings.py`, `src/models/schemas.py`, `src/models/state_machine.py`, `src/renderer/probe.py`  
**Date**: 2026-08-27  

---

## 1. Executive Summary & Design Objectives

This document establishes the technical specification, Pydantic v2 data schemas, state machine transition rules, typed configuration engine, and high-performance FFprobe metadata prober for `baptism_of_music_brain`.

### Key Design Principles:
1. **Pydantic v2 Strictness & Validation**: Full type safety with `@model_validator` and `@field_validator` for video timecodes, aspect ratios, color grading ranges, and audio mastering constraints.
2. **Deterministic State Machine**: Explicit, non-bypassable job lifecycle state transitions with custom exception handling (`InvalidStateTransitionError`).
3. **Robust Media Probing**: Zero-friction FFprobe binary resolution (supporting Windows PATH, `static_ffmpeg`, and explicit configuration) capable of handling zero-audio, multi-stream, fractional frame rates, and corrupt file edge cases.
4. **Environment-Driven Typed Configuration**: Pydantic `pydantic-settings` `BaseSettings` with `BRAIN_` prefix, `.env` support, automatic path resolution, and directory bootstrapping (`ensure_directories`).

---

## 2. Subsystem 1: Configuration & Settings (`config/settings.py`)

### 2.1 Specification
- Class: `AppSettings` inheriting from `pydantic_settings.BaseSettings`
- Configuration: `SettingsConfigDict(env_prefix="BRAIN_", env_file=".env", env_file_encoding="utf-8", extra="ignore")`
- Target Path: `config/settings.py` (with exports in `config/__init__.py`)

### 2.2 Fields & Defaults
| Field Name | Type | Default | Description / Constraints |
|---|---|---|---|
| `app_name` | `str` | `"baptism_of_music_brain"` | Application identifier |
| `app_version` | `str` | `"0.1.0"` | Semantic version |
| `environment` | `str` | `"development"` | `"development"`, `"testing"`, `"production"` |
| `host` | `str` | `"127.0.0.1"` | Server host binding |
| `port` | `int` | `8000` | Server HTTP port (1024-65535) |
| `ingest_dir` | `Path` | `Path("ingest")` | Incoming raw video drops directory |
| `delivery_dir` | `Path` | `Path("delivery")` | Output master renders directory |
| `temp_dir` | `Path` | `Path(".tmp")` | Intermediate staging directory |
| `default_profile` | `str` | `"x264_crf17"` | Default visually lossless encoding profile |
| `gemini_api_key` | `Optional[str]` | `None` | Google Gemini API key (env: `BRAIN_GEMINI_API_KEY` / `GEMINI_API_KEY`) |
| `mock_ml` | `bool` | `False` | Force offline deterministic mock ML engine |
| `ffmpeg_path` | `Optional[str]` | `None` | Custom path to `ffmpeg.exe` |
| `ffprobe_path` | `Optional[str]` | `None` | Custom path to `ffprobe.exe` |
| `lock_poll_interval_sec` | `float` | `0.25` | Polling frequency for Win32 file lock detection |
| `lock_timeout_sec` | `float` | `30.0` | Timeout before flagging incomplete transfer |
| `debounce_delay_sec` | `float` | `1.0` | File size stability debounce threshold |
| `max_concurrent_renders` | `int` | `2` | Max concurrent FFmpeg rendering subprocesses |

### 2.3 Key Methods & Helpers
- `ensure_directories() -> None`: Safely creates `ingest_dir`, `delivery_dir`, and `temp_dir` with `parents=True, exist_ok=True`.
- `resolve_ffmpeg_bin() -> str`: Resolves binary via `ffmpeg_path` -> `static_ffmpeg.add_paths()` -> `shutil.which("ffmpeg")` -> fallback.
- `resolve_ffprobe_bin() -> str`: Resolves binary via `ffprobe_path` -> `static_ffmpeg.add_paths()` -> `shutil.which("ffprobe")` -> fallback.
- `@lru_cache def get_settings() -> AppSettings`: Returns cached application settings singleton.

---

## 3. Subsystem 2: Pydantic v2 Data Models (`src/models/schemas.py`)

### 3.1 Model Hierarchy
```
MediaProbeResult ────────► VideoStreamMetadata / AudioStreamMetadata
                               ▲
EditDecisionList ────────► ClipSegment (list)
                 ────────► ColorGradeSettings
                 ────────► AudioMasteringSettings
                               ▲
VideoJob / JobMetadata ──► JobStatus (Enum)
                       ──► EditDecisionList (Optional)
                       ──► MediaProbeResult (Optional)
```

### 3.2 Schema Specifications

#### A. `JobStatus` (Enum)
```python
class JobStatus(str, Enum):
    PENDING = "PENDING"
    INGESTED = "INGESTED"
    PROBING = "PROBING"
    PROBED = "PROBED"
    GRADING = "GRADING"
    AWAITING_OVERRIDE = "AWAITING_OVERRIDE"
    OVERRIDDEN = "OVERRIDDEN"
    APPROVED = "APPROVED"
    RENDERING = "RENDERING"
    DELIVERING = "DELIVERING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
```

#### B. `ClipSegment` (BaseModel)
- `clip_id: str` (UUID4 prefix or unique string)
- `source_in_sec: float` (ge=0.0)
- `source_out_sec: float` (gt=0.0)
- `timeline_in_sec: float` (ge=0.0, default 0.0)
- `speed_multiplier: float` (gt=0.0, le=10.0, default 1.0)
- `volume_multiplier: float` (ge=0.0, le=5.0, default 1.0)
- `label: Optional[str]`
- **Validators**:
  - `source_out_sec > source_in_sec` (raises ValueError if `source_out_sec <= source_in_sec`)
- **Properties**:
  - `source_duration -> float`: `source_out_sec - source_in_sec`
  - `timeline_duration -> float`: `(source_out_sec - source_in_sec) / speed_multiplier`
  - `timeline_out_sec -> float`: `timeline_in_sec + timeline_duration`

#### C. `ColorGradeSettings` (BaseModel)
- `contrast: float` (default 1.0, range: 0.0 to 3.0)
- `brightness: float` (default 0.0, range: -1.0 to 1.0)
- `saturation: float` (default 1.0, range: 0.0 to 3.0)
- `gamma: float` (default 1.0, range: 0.1 to 10.0)
- `gamma_r: Optional[float]` (range: 0.1 to 10.0)
- `gamma_g: Optional[float]` (range: 0.1 to 10.0)
- `gamma_b: Optional[float]` (range: 0.1 to 10.0)
- **Helper**:
  - `to_ffmpeg_eq_filter() -> str`: Generates `"eq=contrast=...:brightness=...:saturation=...:gamma=..."`

#### D. `AudioMasteringSettings` (BaseModel)
- `normalize_lufs: bool` (default True)
- `target_lufs: float` (default -14.0, range: -70.0 to -5.0)
- `peak_limit_db: float` (default -1.5, range: -20.0 to 0.0)
- `gain_db: float` (default 0.0, range: -30.0 to 30.0)
- `dual_pass: bool` (default False)
- **Helper**:
  - `to_ffmpeg_audio_filter() -> str`: Returns `"loudnorm=I=-14.0:TP=-1.5:LRA=11"` or `f"volume={gain_db}dB"`

#### E. `EditDecisionList` (BaseModel)
- `job_id: str`
- `source_video_path: str`
- `target_resolution: tuple[int, int]` (default: (1920, 1080))
- `target_fps: float` (default: 30.0, gt=0.0, le=240.0)
- `encoding_profile: str` (default: "x264_crf17")
- `segments: list[ClipSegment]` (default: `[]`)
- `color_grade: ColorGradeSettings` (default: `ColorGradeSettings()`)
- `audio_mastering: AudioMasteringSettings` (default: `AudioMasteringSettings()`)
- `manual_override_applied: bool` (default: False)
- `created_at: datetime` (default: UTC now)
- `updated_at: datetime` (default: UTC now)
- **Validators**:
  - Target resolution dimensions must be positive even integers (divisible by 2 for YUV420p).
  - Segments sequence validation: `timeline_in_sec` order and no invalid negative overlaps.
- **Properties**:
  - `total_timeline_duration -> float`: sum of `segment.timeline_duration` for all segments.
  - `segment_count -> int`: `len(segments)`

#### F. `EDLOverridePayload` (BaseModel)
- Partial payload for `PUT /api/v1/jobs/{id}/edl`:
- `segments: Optional[list[ClipSegment]] = None`
- `color_grade: Optional[ColorGradeSettings] = None`
- `audio_mastering: Optional[AudioMasteringSettings] = None`
- `target_resolution: Optional[tuple[int, int]] = None`
- `target_fps: Optional[float] = None`
- `encoding_profile: Optional[str] = None`

#### G. `VideoStreamMetadata` & `AudioStreamMetadata` & `MediaProbeResult`
- `VideoStreamMetadata`: `index: int`, `codec_name: str`, `codec_long_name: Optional[str]`, `profile: Optional[str]`, `width: int`, `height: int`, `aspect_ratio: Optional[str]`, `fps: float`, `pixel_format: str`, `bitrate: Optional[int]`, `duration_sec: Optional[float]`, `nb_frames: Optional[int]`, `color_space: Optional[str]`, `color_transfer: Optional[str]`, `color_primaries: Optional[str]`.
- `AudioStreamMetadata`: `index: int`, `codec_name: str`, `codec_long_name: Optional[str]`, `sample_rate: int`, `channels: int`, `channel_layout: Optional[str]`, `bitrate: Optional[int]`, `duration_sec: Optional[float]`.
- `MediaProbeResult`: `filepath: str`, `format_name: str`, `format_long_name: Optional[str]`, `duration_sec: float`, `size_bytes: int`, `bitrate: Optional[int]`, `video_streams: list[VideoStreamMetadata]`, `audio_streams: list[AudioStreamMetadata]`, `raw_json: Optional[dict[str, Any]]`.
  - Properties: `primary_video`, `primary_audio`, `has_video`, `has_audio`, `width`, `height`, `fps`.

#### H. `VideoJob` & `JobMetadata` (BaseModel)
- `job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))`
- `source_filepath: str`
- `status: JobStatus = JobStatus.PENDING`
- `progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)`
- `active_edl: Optional[EditDecisionList] = None`
- `probe_data: Optional[MediaProbeResult] = None`
- `delivery_filepath: Optional[str] = None`
- `error_message: Optional[str] = None`
- `created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))`
- `updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))`

---

## 4. Subsystem 3: Job State Machine (`src/models/state_machine.py`)

### 4.1 State Transition Graph
```
PENDING ──────► INGESTED ──────► PROBING ──────► PROBED ──────► GRADING
                                                                   │
                                                                   ▼
DELIVERED ◄──── DELIVERING ◄──── RENDERING ◄──── APPROVED ◄──── AWAITING_OVERRIDE
                                                     ▲                 │
                                                     │                 ▼
                                                     └─────────── OVERRIDDEN
```
*(Any non-terminal state may transition to `FAILED` or `CANCELLED`)*

### 4.2 Transition Rules Table
| From State | Allowed Target States | Description |
|---|---|---|
| `PENDING` | `INGESTED`, `FAILED` | Watcher detects file candidate |
| `INGESTED` | `PROBING`, `FAILED`, `CANCELLED` | Win32 lock cleared, prober triggered |
| `PROBING` | `PROBED`, `FAILED` | FFprobe execution in progress |
| `PROBED` | `GRADING`, `FAILED`, `CANCELLED` | Media probed, sent to ML brain |
| `GRADING` | `AWAITING_OVERRIDE`, `APPROVED`, `FAILED` | ML synthesis complete |
| `AWAITING_OVERRIDE` | `OVERRIDDEN`, `APPROVED`, `GRADING`, `CANCELLED`, `FAILED` | User review window |
| `OVERRIDDEN` | `APPROVED`, `AWAITING_OVERRIDE`, `GRADING`, `CANCELLED`, `FAILED` | User applied manual changes |
| `APPROVED` | `RENDERING`, `CANCELLED`, `FAILED` | Enqueued for FFmpeg render |
| `RENDERING` | `DELIVERING`, `FAILED`, `CANCELLED` | FFmpeg rendering in progress |
| `DELIVERING` | `DELIVERED`, `FAILED` | Verification & atomic rename |
| `DELIVERED` | None (Terminal) | Final master published |
| `FAILED` | `PENDING` (Retry), None | Error condition recorded |
| `CANCELLED` | None (Terminal) | Aborted by user |

### 4.3 API & Enforcement
- `InvalidStateTransitionError(Exception)`: Captures `current_status`, `target_status`, `job_id`.
- `can_transition(current: JobStatus, target: JobStatus) -> bool`
- `validate_transition(current: JobStatus, target: JobStatus, job_id: Optional[str] = None) -> None`
- `transition_job(job: VideoJob, target: JobStatus, error_message: Optional[str] = None) -> VideoJob`

---

## 5. Subsystem 4: High-Performance FFprobe Prober (`src/renderer/probe.py`)

### 5.1 Invocation Architecture
- Command:
  `ffprobe -v quiet -print_format json -show_format -show_streams -show_error <input_path>`
- Binary Discovery Pipeline:
  1. Parameter `ffprobe_bin` (if explicitly provided)
  2. `settings.ffprobe_path`
  3. `static_ffmpeg.add_paths()` + `shutil.which("ffprobe")`
  4. Raise `FFprobeNotFoundError` with clear installation/configuration advice.

### 5.2 Fractional Frame Rate Parser
Robustly parses frame rate strings:
- `"30/1"` -> `30.0`
- `"30000/1001"` -> `29.97002997`
- `"60000/1001"` -> `59.94005994`
- `"24000/1001"` -> `23.97602398`
- `"0/0"`, `""`, `None` -> Fallback to `r_frame_rate` or default `30.0`

### 5.3 Exception Hierarchy
- `FFprobeError(Exception)`
  - `FFprobeNotFoundError`
  - `MediaFileNotFoundError` (File does not exist on disk)
  - `CorruptMediaError` (Non-media file, 0-byte file, unreadable container)
  - `FFprobeExecutionError` (Process failed with non-zero exit code or timeout)

### 5.4 Synchronous & Asynchronous Interfaces
- `probe_media(file_path: Union[str, Path], ffprobe_bin: Optional[str] = None, timeout_sec: float = 15.0) -> MediaProbeResult`
- `async_probe_media(file_path: Union[str, Path], ffprobe_bin: Optional[str] = None, timeout_sec: float = 15.0) -> MediaProbeResult`

---

## 6. Implementation Code Signatures & Sign-Off

All module implementations strictly follow absolute imports (`from src.models.schemas import ...`, `from config.settings import ...`) complying with **R16** and Pydantic v2 conventions.
