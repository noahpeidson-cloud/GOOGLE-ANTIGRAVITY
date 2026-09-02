# Phase 3 Media Suite Survey & Architecture Analysis: Backend Gateway & FFmpeg Renderer

**Author**: Survey Explorer 2 (Backend Gateway & FFmpeg Renderer)  
**Target Project**: `g:/My Drive/GOOGLE ANTIGRAVITY/unified_ops_hub`  
**Date**: 2026-08-26  
**Status**: Investigation Complete & Verified

---

## 1. Executive Summary

This survey provides the complete architectural blueprint and execution plan for implementing the **Headless FFmpeg Renderer** (`gateway/renderer.py`), integrating it into the **Unified Ops Hub FastAPI Gateway** (`gateway/app.py`), and verifying it with **TDAD Loud Assertions** (`tests/test_ffmpeg_renderer.py`).

All FFmpeg commands and filter expressions have been empirically tested and verified using the environment's bundled FFmpeg v7.1 engine.

---

## 2. Existing Codebase Audit (`gateway/app.py` & Related Modules)

### 2.1 Gateway Architecture & Lifespan
- **File**: `unified_ops_hub/gateway/app.py`
- **Application Factory**: `create_app(port_manager: Optional[PortManager] = None, dlq_manager: Optional[DLQManager] = None) -> FastAPI`
- **State Management**: `GatewayState` class stores in-memory state (`cards_staging`, `media_jobs`, `model_weights`, `feedback_records`, `clusters`, `trending_sounds`). Attached to `app.state.gateway_state`.
- **Managers**:
  - `PortManager` handles socket conflict detection, dynamic port allocation, and lockfile lifecycle management.
  - `DLQManager` handles thread-safe SQLite WAL persistence, error categorization (`ErrorCategory`), and payload quarantine.

### 2.2 Existing Media Router
- `create_media_router(app_state: GatewayState) -> APIRouter`:
  - `GET /api/v1/media/health`: Returns service health and active jobs count.
  - `POST /api/v1/media/trigger`: Accepts `VideoTriggerRequest(clip_name, mode, priority)` and enqueues a job into `app_state.media_jobs`.
  - `GET /api/v1/media/status/{job_id}`: Returns status for a given `job_id`.
  - `GET /api/v1/media/proxies`: Returns mock list of 720p proxies.

### 2.3 Identified Architecture Gaps in `gateway/app.py`
1. **Missing CORS Middleware**:
   - The React / Next.js dashboard runs on port 3000 (or dynamic port) while the FastAPI gateway runs on port 8000 (or dynamic port).
   - In `create_app()`, `CORSMiddleware` is currently absent, causing browser-originated fetch requests from `MediaStudio.tsx` to fail with CORS policy violations.
   - **Resolution**: Add `CORSMiddleware` with `allow_origins=["*"]`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.
2. **Missing Static File Serving for Media**:
   - The HTML5 video player in `MediaStudio.tsx` needs to stream both 720p proxies and rendered MP4 files from disk.
   - **Resolution**: Mount `StaticFiles(directory=renders_dir)` at `/renders` and `StaticFiles(directory=proxies_dir)` at `/proxies` (or provide streaming endpoint `/api/v1/media/stream/{file_type}/{filename}`).
3. **Missing Headless Video Renderer Integration**:
   - Currently, there is no `POST /api/v1/media/render` endpoint or `gateway/renderer.py` module.

---

## 3. Architecture Design: `gateway/renderer.py`

### 3.1 Module Structure & Responsibilities
`gateway/renderer.py` must be a self-contained, high-performance module adhering strictly to Rule R16 (absolute imports):

```
unified_ops_hub/gateway/renderer.py
├── 1. Binary Locator & Environment Resolver (get_ffmpeg_path)
├── 2. Pydantic Request / Response Data Models (RenderRequest, RenderResponse)
├── 3. Filtergraph Builder & Escaper (build_video_filter, escape_drawtext)
├── 4. FFmpeg Command Compiler (build_ffmpeg_render_command)
└── 5. FFmpegRenderer Engine Class (sync & async execution, status tracking, DLQ hooks)
```

### 3.2 Binary Locator Strategy
On Windows / Developer workstation environments, FFmpeg may reside in system PATH or within python package caches (`imageio_ffmpeg`):
```python
import os
import shutil
import logging

logger = logging.getLogger("unified_ops_hub.renderer")

def get_ffmpeg_path() -> str:
    """Locates a valid FFmpeg binary from environment, PATH, or imageio-ffmpeg."""
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    
    path_bin = shutil.which("ffmpeg")
    if path_bin and os.path.isfile(path_bin):
        return path_bin
        
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except ImportError:
        pass
        
    raise FileNotFoundError(
        "FFmpeg binary not found. Please install ffmpeg or imageio-ffmpeg, "
        "or set the FFMPEG_PATH environment variable."
    )
```

### 3.3 Pydantic Data Models
```python
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CropRatio(str, Enum):
    RATIO_9_16 = "9:16"
    RATIO_16_9 = "16:9"
    ORIGINAL = "original"

class RenderRequest(BaseModel):
    source_file: str = Field(..., description="Absolute path or project-relative filename of input raw video")
    in_point: float = Field(..., ge=0.0, description="Start timestamp in seconds")
    out_point: float = Field(..., gt=0.0, description="End timestamp in seconds (must be > in_point)")
    crop_ratio: str = Field(default="9:16", description="Target aspect ratio: '9:16', '16:9', or 'original'")
    text_overlay: Optional[str] = Field(default=None, description="Optional text overlay to stamp onto the video")
    output_dir: Optional[str] = Field(default=None, description="Custom output directory (defaults to hub renders/)")
    output_filename: Optional[str] = Field(default=None, description="Custom output filename (.mp4)")
    sync: bool = Field(default=True, description="Synchronous execution (True) or background job (False)")

class RenderResponse(BaseModel):
    job_id: str
    status: str = Field(..., description="COMPLETED, QUEUED, PROCESSING, or FAILED")
    source_file: str
    output_file: Optional[str] = None
    output_url: Optional[str] = None
    in_point: float
    out_point: float
    duration: float
    crop_ratio: str
    text_overlay: Optional[str] = None
    error: Optional[str] = None
    ffmpeg_command: Optional[List[str]] = None
    created_at: float
    completed_at: Optional[float] = None
```

---

## 4. Exact FFmpeg Command & Filtergraph Formulation

### 4.1 Input Trimming & Frame-Accurate Seeking
To achieve sub-second frame-accurate cuts without audio-video desync:
- Trimming parameters: `-ss <in_point>` and `-t <duration>` where `duration = out_point - in_point`.
- For frame accuracy with complex filtergraphs, placing `-ss` and `-t` before the input or using input seeking + filtergraph decoding guarantees synchronization.

### 4.2 Aspect Ratio Cropping & Scaling Formulation
H.264 (`libx264`) requires even dimensions (divisible by 2). The filter pipelines ensure standard output resolutions:

1. **Vertical 9:16 (TikTok / Instagram Reels / Shorts)**:
   - Target Dimension: `1080x1920` (or `2160x3840` for 4K vertical)
   - Filter Expression:
     ```
     crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':x='(iw-ow)/2':y='(ih-oh)/2',scale=1080:1920
     ```
   - Behavior: Automatically centers and crops horizontal 16:9 or non-standard inputs into exact 9:16, then scales to standard 1080x1920.

2. **Cinematic 16:9 (YouTube / Standard Widescreen)**:
   - Target Dimension: `1920x1080` (or `3840x2160` for 4K master)
   - Filter Expression:
     ```
     crop=w='min(iw,ih*16/9)':h='min(ih,iw*9/16)':x='(iw-ow)/2':y='(ih-oh)/2',scale=1920:1080
     ```
   - Behavior: Crops vertically oversized inputs or preserves full 16:9 master frame.

3. **Raw POV / Original Aspect Ratio**:
   - Filter Expression:
     ```
     scale=trunc(iw/2)*2:trunc(ih/2)*2
     ```
   - Behavior: Preserves the source aspect ratio while enforcing even pixel dimensions required by `libx264`.

### 4.3 Text Overlay Escaping (`drawtext` filter)
In FFmpeg filtergraphs, special characters (`:`, `'`, `\`, `%`, `,`) must be escaped to prevent filter parsing errors:
```python
def escape_drawtext(text: str) -> str:
    """Escapes special characters in text strings for FFmpeg drawtext filter."""
    if not text:
        return ""
    # Order matters: backslash first
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("%", "\\%")
    escaped = escaped.replace(",", "\\,")
    return escaped
```

- Drawtext filter snippet:
  ```
  drawtext=text='{safe_text}':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=h-text_h-100:box=1:boxcolor=black@0.6:boxborderw=8
  ```
  - `x=(w-text_w)/2`: Centers text horizontally.
  - `y=h-text_h-100`: Positions text 100 pixels above the bottom boundary.
  - `box=1:boxcolor=black@0.6:boxborderw=8`: Adds a semi-transparent black background box with padding for high contrast against any video background.

### 4.4 Full FFmpeg Command Formulation
```python
cmd = [
    ffmpeg_bin,
    "-y",                         # Overwrite output file
    "-ss", f"{in_point:.3f}",     # In point (seek)
    "-t", f"{duration:.3f}",      # Segment duration
    "-i", resolved_source_path,   # Input file
    "-vf", full_filter_chain,     # Video filtergraph (crop + scale + drawtext)
    "-c:v", "libx264",            # H.264 video codec
    "-preset", "fast",            # Fast encoding preset
    "-pix_fmt", "yuv420p",        # Broadest player compatibility
    "-c:a", "aac",                # AAC audio codec
    "-b:a", "192k",               # Audio bitrate
    output_filepath               # Target output .mp4
]
```

---

## 5. API Design & Gateway Integration (`gateway/app.py`)

### 5.1 Route Definition in `create_media_router`
```python
@router.post("/render", response_model=RenderResponse, status_code=status.HTTP_200_OK)
async def render_media_endpoint(
    req: RenderRequest,
    background_tasks: BackgroundTasks,
    request: Request
):
    if req.in_point >= req.out_point:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"in_point ({req.in_point}) must be strictly less than out_point ({req.out_point})"
        )

    renderer: FFmpegRenderer = getattr(request.app.state, "renderer", None)
    if renderer is None:
        renderer = FFmpegRenderer()
        request.app.state.renderer = renderer

    if req.sync:
        # Synchronous render (awaited in worker thread)
        result = await asyncio.to_thread(renderer.render_sync, req)
        app_state.media_jobs[result.job_id] = result.model_dump()
        
        if result.status == "FAILED":
            dlq_mgr: DLQManager = request.app.state.dlq_manager
            dlq_mgr.record_failure(
                source_service="media_renderer",
                error_category=ErrorCategory.UNHANDLED_EXCEPTION,
                error_message=f"Render job {result.job_id} failed: {result.error}",
                payload=req.model_dump(),
            )
            raise HTTPException(status_code=500, detail=f"Render execution failed: {result.error}")
            
        return result
    else:
        # Async background job
        job_id = f"render_{uuid.uuid4().hex[:8]}"
        initial_job = RenderResponse(
            job_id=job_id,
            status="QUEUED",
            source_file=req.source_file,
            in_point=req.in_point,
            out_point=req.out_point,
            duration=round(req.out_point - req.in_point, 3),
            crop_ratio=req.crop_ratio,
            text_overlay=req.text_overlay,
            created_at=time.time(),
        )
        app_state.media_jobs[job_id] = initial_job.model_dump()
        background_tasks.add_task(renderer.execute_background_render, req, job_id, app_state)
        return initial_job
```

### 5.2 Companion Endpoints
- `GET /api/v1/media/renders`: Returns list of all completed/cached renders.
- `GET /api/v1/media/status/{job_id}`: Polling endpoint for frontend async render progress.

---

## 6. TDAD Test Suite Blueprint (`tests/test_ffmpeg_renderer.py`)

Following Rule R2 (Zero-Discretion Mandate / Loud Assertions), `test_ffmpeg_renderer.py` must execute isolated, deterministic tests with zero shared state:

| Test Case | Description | Loud Assertions |
|---|---|---|
| `test_ffmpeg_binary_detection` | Verifies `get_ffmpeg_path()` finds valid binary | Executable exists, running `-version` returns code 0. |
| `test_render_hype_drop_9_16_sync` | Renders 9:16 vertical cut with overlay | Status is `COMPLETED`, output file exists > 10KB, probed dimensions are exactly `1080x1920`, duration matches trimmed range. |
| `test_render_cinematic_16_9_sync` | Renders 16:9 widescreen cut | Status is `COMPLETED`, output file exists > 10KB, probed dimensions are `1920x1080`. |
| `test_render_raw_pov_original` | Renders original aspect ratio cut | Status is `COMPLETED`, dimensions match source (with even pixel adjustment). |
| `test_text_overlay_special_chars` | Renders text with colons, quotes, percents | Return code 0, no filtergraph parse errors, output file valid. |
| `test_render_invalid_timestamp_validation` | `in_point >= out_point` | FastAPI endpoint returns `422 Unprocessable Content`. |
| `test_render_missing_source_file` | Non-existent source file | Returns error status or 404/500, recorded in DLQ. |
| `test_render_async_background_execution` | Submits async render job (`sync=False`) | Returns `200/202` with `QUEUED`, background task finishes, status transitions to `COMPLETED`. |
| `test_cors_headers_present` | Pre-flight OPTIONS & GET / POST requests | Response contains `access-control-allow-origin: *`. |

---

## 7. Implementation Roadmap & Checklist

1. **Step 1**: Implement `unified_ops_hub/gateway/renderer.py` with binary resolver, models, filter builder, and `FFmpegRenderer` engine.
2. **Step 2**: Update `unified_ops_hub/gateway/app.py`:
   - Import `FFmpegRenderer`, `RenderRequest`, `RenderResponse` from `gateway.renderer`.
   - Add `CORSMiddleware`.
   - Mount `/renders` static files directory.
   - Update `create_media_router` with `POST /render` and `GET /renders`.
3. **Step 3**: Create test suite `unified_ops_hub/tests/test_ffmpeg_renderer.py` with 9+ loud assertion test cases.
4. **Step 4**: Execute `python -m pytest tests/test_ffmpeg_renderer.py` to achieve 100% test pass rate.
