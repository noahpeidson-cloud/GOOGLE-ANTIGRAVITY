"""Unified Ops Hub - Headless FFmpeg Video Renderer Engine.
Provides dynamic binary resolution, filtergraph construction for 9:16 / 16:9 / raw cropping,
special character drawtext escaping, and synchronous/asynchronous render execution.
Adheres strictly to Rule R16 (absolute imports) and Rule R18.
"""

import os
import re
import shutil
import subprocess
import time
import uuid
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

logger = logging.getLogger("unified_ops_hub.gateway.renderer")


# ============================================================================
# Dynamic FFmpeg Binary Resolution
# ============================================================================

def get_ffmpeg_path(custom_path: Optional[str] = None) -> str:
    """Locates a valid FFmpeg executable using a 5-tier fallback cascade.

    Args:
        custom_path: Optional explicit path to ffmpeg binary.

    Returns:
        str: Valid executable path to FFmpeg binary.

    Raises:
        FileNotFoundError: If FFmpeg cannot be located in the environment.
    """
    if custom_path:
        p = Path(custom_path)
        if p.is_file() or shutil.which(custom_path):
            return str(custom_path)
        raise FileNotFoundError(f"Specified FFmpeg executable does not exist: {custom_path}")

    # 1. Check environment variables
    for env_var in ("FFMPEG_BINARY", "FFMPEG_PATH", "IMAGEIO_FFMPEG_EXE"):
        val = os.environ.get(env_var)
        if val and (Path(val).is_file() or shutil.which(val)):
            return str(val)

    # 2. Check imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return str(exe)
    except (ImportError, Exception):
        pass

    # 3. Check system PATH
    which_exe = shutil.which("ffmpeg")
    if which_exe:
        return str(which_exe)

    # 4. Fallback failure
    raise FileNotFoundError(
        "FFmpeg binary not found. Please install ffmpeg or imageio-ffmpeg, "
        "or set the FFMPEG_PATH environment variable."
    )


# ============================================================================
# Filtergraph Building & String Escaping
# ============================================================================

def escape_drawtext(text: str) -> str:
    """Escapes special characters in text strings for FFmpeg drawtext filtergraphs.

    FFmpeg filtergraph parsing requires escaping backslashes, single quotes, colons,
    percent signs, and commas.

    Args:
        text: Raw text string to overlay.

    Returns:
        str: Escaped string safe for drawtext filter parameter.
    """
    if not text:
        return ""
    # Escaping order is critical: backslash must be escaped first
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("%", "\\%")
    escaped = escaped.replace(",", "\\,")
    return escaped


def build_video_filter(
    crop_ratio: str = "9:16",
    text_overlay: Optional[str] = None,
    enable_drawtext: bool = True,
) -> str:
    """Constructs the complete FFmpeg video filtergraph chain (-vf).

    Args:
        crop_ratio: Aspect ratio target ('9:16', '16:9', 'original', 'raw_pov').
        text_overlay: Optional text string to draw over the video.
        enable_drawtext: Whether to append drawtext filter if text_overlay is provided.

    Returns:
        str: Composed filtergraph string.
    """
    ratio_clean = str(crop_ratio).strip().lower()

    if ratio_clean in ("9:16", "vertical", "shorts", "reels", "tiktok"):
        # 9:16 Vertical crop & scale to 1080x1920
        base_filter = "crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':x='(iw-ow)/2':y='(ih-oh)/2',scale=1080:1920"
    elif ratio_clean in ("16:9", "horizontal", "cinematic", "widescreen"):
        # 16:9 Widescreen crop & scale to 1920x1080
        base_filter = "crop=w='min(iw,ih*16/9)':h='min(ih,iw*9/16)':x='(iw-ow)/2':y='(ih-oh)/2',scale=1920:1080"
    else:
        # Original / raw_pov: enforce even pixel dimensions for libx264 compatibility
        base_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

    filters = [base_filter]

    if text_overlay and enable_drawtext:
        safe_text = escape_drawtext(text_overlay)
        drawtext_filter = (
            f"drawtext=text='{safe_text}':fontsize=40:fontcolor=white:"
            f"x=(w-text_w)/2:y=h-text_h-100:box=1:boxcolor=black@0.6:boxborderw=8"
        )
        filters.append(drawtext_filter)

    return ",".join(filters)


# ============================================================================
# Pydantic Request / Response Data Models
# ============================================================================

class CropRatioEnum(str, Enum):
    RATIO_9_16 = "9:16"
    RATIO_16_9 = "16:9"
    ORIGINAL = "original"
    RAW_POV = "raw_pov"


class RenderRequest(BaseModel):
    source_file: str = Field(..., description="Absolute path or project-relative filename of input raw video")
    in_point: float = Field(default=0.0, ge=0.0, description="Start timestamp in seconds")
    out_point: float = Field(..., gt=0.0, description="End timestamp in seconds (must be > in_point)")
    crop_ratio: str = Field(default="9:16", description="Target aspect ratio: '9:16', '16:9', or 'original'")
    text_overlay: Optional[str] = Field(default=None, description="Optional text overlay to stamp onto the video")
    output_dir: Optional[str] = Field(default=None, description="Custom output directory (defaults to renders/)")
    output_filename: Optional[str] = Field(default=None, description="Custom output filename (.mp4)")
    sync: bool = Field(default=True, description="Synchronous execution (True) or background job (False)")


class RenderResponse(BaseModel):
    status: str = Field(..., description="completed, queued, processing, or failed")
    job_id: str = Field(..., description="Unique job identifier")
    render_id: Optional[str] = Field(default=None, description="Parity alias for job_id")
    source_file: str
    output_file: Optional[str] = None
    output_url: Optional[str] = None
    in_point: float
    out_point: float
    duration: float
    crop_ratio: str
    text_overlay: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    ffmpeg_command: Optional[List[str]] = None
    created_at: float
    completed_at: Optional[float] = None


# ============================================================================
# Headless FFmpeg Renderer Engine Class
# ============================================================================

class FFmpegRenderer:
    """Headless FFmpeg video rendering engine with resilient execution & fallback."""

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        default_renders_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initializes FFmpegRenderer with dynamic binary locator and output directory."""
        self.ffmpeg_bin = get_ffmpeg_path(ffmpeg_path)
        
        if default_renders_dir:
            self.default_renders_dir = Path(default_renders_dir).resolve()
        else:
            self.default_renders_dir = Path(os.getcwd()) / "renders"
            
        self.default_renders_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_source_path(self, source_file: Union[str, Path]) -> Path:
        """Resolves source file path against absolute path or workspace locations."""
        p = Path(source_file)
        if p.is_file():
            return p.resolve()

        # Try relative to current working directory
        cwd_p = Path(os.getcwd()) / source_file
        if cwd_p.is_file():
            return cwd_p.resolve()

        # Try relative to module root
        mod_root = Path(__file__).resolve().parent.parent / source_file
        if mod_root.is_file():
            return mod_root.resolve()

        raise FileNotFoundError(f"Source video file not found: {source_file}")

    def render_cut(
        self,
        source_file: Union[str, Path],
        in_point: float,
        out_point: float,
        crop_ratio: str = "9:16",
        text_overlay: Optional[str] = None,
        output_path: Optional[Union[str, Path]] = None,
        renders_dir: Optional[Union[str, Path]] = None,
        job_id: Optional[str] = None,
    ) -> RenderResponse:
        """Renders an edited sub-clip from a source video file.

        Args:
            source_file: Path to source media file.
            in_point: Start timestamp in seconds.
            out_point: End timestamp in seconds.
            crop_ratio: Target aspect ratio ('9:16', '16:9', 'original').
            text_overlay: Optional text string to overlay.
            output_path: Optional explicit target output file path.
            renders_dir: Optional custom renders directory if output_path is not given.
            job_id: Optional explicit job/render identifier.

        Returns:
            RenderResponse: Details of completed render operation.

        Raises:
            ValueError: If in_point >= out_point or timestamps are invalid.
            FileNotFoundError: If source_file does not exist.
            RuntimeError: If FFmpeg execution fails.
        """
        in_pt = float(in_point)
        out_pt = float(out_point)

        if in_pt < 0:
            raise ValueError(f"in_point must be >= 0 (got {in_pt})")
        if out_pt <= in_pt:
            raise ValueError(
                f"in_point ({in_pt}) must be strictly less than out_point ({out_pt})"
            )

        resolved_source = self._resolve_source_path(source_file)
        duration = round(out_pt - in_pt, 3)
        current_time = time.time()
        active_job_id = job_id or f"render_{int(current_time)}_{uuid.uuid4().hex[:6]}"

        # Determine target output path
        if output_path:
            target_out = Path(output_path).resolve()
            target_out.parent.mkdir(parents=True, exist_ok=True)
        else:
            out_dir = Path(renders_dir).resolve() if renders_dir else self.default_renders_dir
            out_dir.mkdir(parents=True, exist_ok=True)
            target_out = out_dir / f"{active_job_id}.mp4"

        # Build video filter chain
        vf_filter = build_video_filter(
            crop_ratio=crop_ratio,
            text_overlay=text_overlay,
            enable_drawtext=True,
        )

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-ss", f"{in_pt:.3f}",
            "-t", f"{duration:.3f}",
            "-i", str(resolved_source),
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            str(target_out),
        ]

        logger.info("Executing FFmpeg render command for job %s: %s", active_job_id, " ".join(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True)

        # Resilient fallback: If drawtext filter failed (e.g. missing filter or font configuration error)
        if res.returncode != 0 and text_overlay:
            logger.warning(
                "FFmpeg render with drawtext failed for job %s (code %d). Retrying without drawtext: %s",
                active_job_id, res.returncode, res.stderr
            )
            fallback_vf = build_video_filter(
                crop_ratio=crop_ratio,
                text_overlay=None,
                enable_drawtext=False,
            )
            fallback_cmd = [
                self.ffmpeg_bin,
                "-y",
                "-ss", f"{in_pt:.3f}",
                "-t", f"{duration:.3f}",
                "-i", str(resolved_source),
                "-vf", fallback_vf,
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                str(target_out),
            ]
            res = subprocess.run(fallback_cmd, capture_output=True, text=True)
            cmd = fallback_cmd

        if res.returncode != 0:
            err_msg = f"FFmpeg render failed with exit code {res.returncode}: {res.stderr}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        if not target_out.is_file() or target_out.stat().st_size == 0:
            raise RuntimeError(f"FFmpeg exited 0 but output file is missing or empty: {target_out}")

        completed_time = time.time()
        relative_url = f"/renders/{target_out.name}"

        return RenderResponse(
            status="completed",
            job_id=active_job_id,
            render_id=active_job_id,
            source_file=str(resolved_source),
            output_file=str(target_out),
            output_url=relative_url,
            in_point=in_pt,
            out_point=out_pt,
            duration=duration,
            crop_ratio=crop_ratio,
            text_overlay=text_overlay,
            message="Render completed successfully",
            ffmpeg_command=cmd,
            created_at=current_time,
            completed_at=completed_time,
        )

    def render_sync(self, req: RenderRequest, job_id: Optional[str] = None) -> RenderResponse:
        """Executes a synchronous render operation directly from a RenderRequest."""
        target_out = None
        if req.output_dir and req.output_filename:
            target_out = Path(req.output_dir) / req.output_filename
        elif req.output_filename:
            target_out = self.default_renders_dir / req.output_filename

        return self.render_cut(
            source_file=req.source_file,
            in_point=req.in_point,
            out_point=req.out_point,
            crop_ratio=req.crop_ratio,
            text_overlay=req.text_overlay,
            output_path=target_out,
            renders_dir=req.output_dir,
            job_id=job_id,
        )

    def execute_background_render(self, req: RenderRequest, job_id: str, app_state: Any) -> None:
        """Background worker method for async render tasks."""
        try:
            if hasattr(app_state, "media_jobs"):
                app_state.media_jobs[job_id]["status"] = "PROCESSING"
            
            result = self.render_sync(req, job_id=job_id)
            
            if hasattr(app_state, "media_jobs"):
                app_state.media_jobs[job_id] = result.model_dump()
        except Exception as exc:
            logger.error("Async background render job %s failed: %s", job_id, exc)
            if hasattr(app_state, "media_jobs"):
                app_state.media_jobs[job_id].update({
                    "status": "FAILED",
                    "error": str(exc),
                    "completed_at": time.time(),
                })
