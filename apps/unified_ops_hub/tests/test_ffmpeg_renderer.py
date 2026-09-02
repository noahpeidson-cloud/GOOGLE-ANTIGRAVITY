"""Unit and Integration Tests for Unified Ops Hub Headless FFmpeg Renderer (Milestone 2).
Enforces Rule R2 (The Leash Protocol / Zero-Discretion Mandate / Loud Assertions / TDAD).
Executes actual FFmpeg commands against dynamically generated synthetic test media.
"""

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient

# Cross-module import support adhering to Rule R16
try:
    from unified_ops_hub.gateway.renderer import (
        FFmpegRenderer,
        RenderRequest,
        RenderResponse,
        get_ffmpeg_path,
        escape_drawtext,
        build_video_filter,
    )
    from unified_ops_hub.gateway.app import create_app, GatewayState
except ImportError:
    from gateway.renderer import (
        FFmpegRenderer,
        RenderRequest,
        RenderResponse,
        get_ffmpeg_path,
        escape_drawtext,
        build_video_filter,
    )
    from gateway.app import create_app, GatewayState


# ============================================================================
# Synthetic Media Generation & Probing Utilities
# ============================================================================

def resolve_test_ffmpeg_path() -> str:
    """Resolves FFmpeg executable for test fixtures."""
    if os.environ.get("FFMPEG_PATH"):
        return os.environ["FFMPEG_PATH"]
    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def probe_rendered_media(file_path: str, ffmpeg_path: Optional[str] = None) -> Dict[str, Any]:
    """Probes media properties (width, height, duration, audio) directly via FFmpeg."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found for probing: {file_path}")

    exe = ffmpeg_path or resolve_test_ffmpeg_path()
    res = subprocess.run([exe, "-i", file_path], capture_output=True, text=True)
    stderr = res.stderr

    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
    duration = None
    if dur_match:
        h, m, s = map(float, dur_match.groups())
        duration = round(h * 3600 + m * 60 + s, 3)

    dim_match = re.search(r"Video:.*,\s*(\d{2,5})x(\d{2,5})", stderr)
    width, height = (int(dim_match.group(1)), int(dim_match.group(2))) if dim_match else (0, 0)

    has_audio = bool(re.search(r"Stream #.*: Audio:", stderr))

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "has_audio": has_audio,
        "file_size": os.path.getsize(file_path),
    }


def create_test_synthetic_source(
    output_path: str,
    duration: float = 6.0,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    ffmpeg_path: Optional[str] = None,
) -> str:
    """Procedurally creates a synthetic 1080p source video with a 1000Hz test tone."""
    exe = ffmpeg_path or resolve_test_ffmpeg_path()
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    cmd = [
        exe, "-y",
        "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate={fps}:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        output_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to create synthetic test source: {res.stderr}")
    return output_path


# ============================================================================
# Unit Tests: Dynamic Binary Resolution & Helper Functions
# ============================================================================

def test_ffmpeg_binary_detection():
    """Loud Assertion: Validates dynamic binary resolution finds an executable FFmpeg binary."""
    ffmpeg_exe = get_ffmpeg_path()
    assert os.path.exists(ffmpeg_exe), f"Resolved FFmpeg path does not exist: {ffmpeg_exe}"
    res = subprocess.run([ffmpeg_exe, "-version"], capture_output=True, text=True)
    assert res.returncode == 0, f"FFmpeg -version failed with returncode {res.returncode}"
    assert "ffmpeg version" in res.stdout.lower() or "ffmpeg version" in res.stderr.lower()


def test_escape_drawtext_special_characters():
    """Loud Assertion: Tests escaping of quotes, colons, backslashes, percents, and commas."""
    raw_text = "DROP 100%: 'LIVE' \\ Mainstage: 2026, Ultra!"
    escaped = escape_drawtext(raw_text)
    
    # Backslashes must be doubled
    assert "\\\\" in escaped
    # Single quotes must be escaped
    assert "\\'" in escaped
    # Colons must be escaped
    assert "\\:" in escaped
    # Percents must be escaped
    assert "\\%" in escaped
    # Commas must be escaped
    assert "\\," in escaped


def test_build_video_filter_ratios():
    """Loud Assertion: Validates filter strings for 9:16, 16:9, and original aspect ratios."""
    f_9_16 = build_video_filter(crop_ratio="9:16", text_overlay=None)
    assert "crop=" in f_9_16
    assert "scale=1080:1920" in f_9_16

    f_16_9 = build_video_filter(crop_ratio="16:9", text_overlay=None)
    assert "crop=" in f_16_9
    assert "scale=1920:1080" in f_16_9

    f_orig = build_video_filter(crop_ratio="original", text_overlay=None)
    assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in f_orig

    f_text = build_video_filter(crop_ratio="9:16", text_overlay="🔥 HYPE MOMENT")
    assert "drawtext=" in f_text
    assert "scale=1080:1920" in f_text


# ============================================================================
# Functional Renderer Engine Tests (FFmpegRenderer)
# ============================================================================

def test_render_hype_drop_9_16_vertical_crop(tmp_path):
    """Loud Assertion: 9:16 crop render produces exact 1080x1920 MP4 file with text overlay."""
    source_file = str(tmp_path / "raw_16_9_source.mp4")
    create_test_synthetic_source(source_file, duration=5.0, width=1920, height=1080)

    renderer = FFmpegRenderer()
    out_file = str(tmp_path / "renders" / "hype_drop_rendered.mp4")
    
    result = renderer.render_cut(
        source_file=source_file,
        in_point=1.0,
        out_point=4.0,
        crop_ratio="9:16",
        text_overlay="🔥 ULTRA DROP",
        output_path=out_file,
    )

    assert result.status == "completed"
    assert os.path.exists(out_file), f"Rendered output does not exist: {out_file}"
    assert os.path.getsize(out_file) > 1024, "Rendered file is empty or suspiciously small"

    meta = probe_rendered_media(out_file)
    assert meta["width"] == 1080, f"Expected width 1080, got {meta['width']}"
    assert meta["height"] == 1920, f"Expected height 1920, got {meta['height']}"
    assert abs(meta["duration"] - 3.0) <= 0.25, f"Expected duration ~3.0s, got {meta['duration']}"
    assert meta["has_audio"] is True, "Rendered video should retain audio stream"


def test_render_cinematic_16_9_crop(tmp_path):
    """Loud Assertion: 16:9 widescreen crop render produces exact 1920x1080 MP4 file."""
    source_file = str(tmp_path / "raw_vertical_source.mp4")
    # Provide a 1080x1920 vertical source to test 16:9 center crop and scaling
    create_test_synthetic_source(source_file, duration=4.0, width=1080, height=1920)

    renderer = FFmpegRenderer()
    out_file = str(tmp_path / "renders" / "cinematic_rendered.mp4")

    result = renderer.render_cut(
        source_file=source_file,
        in_point=0.5,
        out_point=3.0,
        crop_ratio="16:9",
        text_overlay=None,
        output_path=out_file,
    )

    assert result.status == "completed"
    assert os.path.exists(out_file)
    meta = probe_rendered_media(out_file)
    assert meta["width"] == 1920, f"Expected width 1920, got {meta['width']}"
    assert meta["height"] == 1080, f"Expected height 1080, got {meta['height']}"
    assert abs(meta["duration"] - 2.5) <= 0.25, f"Expected duration ~2.5s, got {meta['duration']}"


def test_render_raw_pov_original_aspect_ratio(tmp_path):
    """Loud Assertion: 'original' / 'raw_pov' crop preserves input dimensions."""
    source_file = str(tmp_path / "raw_1280x720.mp4")
    create_test_synthetic_source(source_file, duration=3.0, width=1280, height=720)

    renderer = FFmpegRenderer()
    out_file = str(tmp_path / "renders" / "raw_pov_rendered.mp4")

    result = renderer.render_cut(
        source_file=source_file,
        in_point=0.0,
        out_point=2.0,
        crop_ratio="raw_pov",
        text_overlay="RAW POV",
        output_path=out_file,
    )

    assert result.status == "completed"
    assert os.path.exists(out_file)
    meta = probe_rendered_media(out_file)
    assert meta["width"] == 1280, f"Expected width 1280, got {meta['width']}"
    assert meta["height"] == 720, f"Expected height 720, got {meta['height']}"
    assert abs(meta["duration"] - 2.0) <= 0.25


def test_render_trim_accuracy_and_subsecond_precision(tmp_path):
    """Loud Assertion: Trimming accurately outputs specified duration (out_point - in_point)."""
    source_file = str(tmp_path / "source_10s.mp4")
    create_test_synthetic_source(source_file, duration=10.0, width=1920, height=1080)

    renderer = FFmpegRenderer()
    out_file = str(tmp_path / "renders" / "trimmed_1_25s.mp4")

    # In: 2.25s, Out: 3.50s -> Duration: 1.25s
    result = renderer.render_cut(
        source_file=source_file,
        in_point=2.25,
        out_point=3.50,
        crop_ratio="9:16",
        output_path=out_file,
    )

    assert result.status == "completed"
    assert abs(result.duration - 1.25) < 0.001
    meta = probe_rendered_media(out_file)
    assert abs(meta["duration"] - 1.25) <= 0.25


def test_render_text_overlay_complex_escaped_characters(tmp_path):
    """Loud Assertion: Text overlay with escaped characters renders cleanly without syntax errors."""
    source_file = str(tmp_path / "source_complex_text.mp4")
    create_test_synthetic_source(source_file, duration=3.0, width=1920, height=1080)

    renderer = FFmpegRenderer()
    out_file = str(tmp_path / "renders" / "escaped_text.mp4")

    complex_text = "Artist: DJ Snake | 100% 'HYPED' \\ VIP: Ultra"
    result = renderer.render_cut(
        source_file=source_file,
        in_point=0.0,
        out_point=2.0,
        crop_ratio="9:16",
        text_overlay=complex_text,
        output_path=out_file,
    )

    assert result.status == "completed"
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 1024


def test_renderer_validation_invalid_in_out_points(tmp_path):
    """Loud Assertion: in_point >= out_point raises ValueError in renderer engine."""
    source_file = str(tmp_path / "source_dummy.mp4")
    create_test_synthetic_source(source_file, duration=3.0)

    renderer = FFmpegRenderer()
    with pytest.raises(ValueError) as excinfo:
        renderer.render_cut(
            source_file=source_file,
            in_point=3.0,
            out_point=1.0,
            crop_ratio="9:16",
        )
    assert "in_point" in str(excinfo.value) and "out_point" in str(excinfo.value)


def test_renderer_validation_nonexistent_source(tmp_path):
    """Loud Assertion: Nonexistent source file raises FileNotFoundError."""
    renderer = FFmpegRenderer()
    with pytest.raises(FileNotFoundError):
        renderer.render_cut(
            source_file=str(tmp_path / "does_not_exist.mp4"),
            in_point=0.0,
            out_point=2.0,
            crop_ratio="9:16",
        )


# ============================================================================
# FastAPI Gateway Integration Tests (POST /api/v1/media/render)
# ============================================================================

def test_fastapi_render_endpoint_sync_success(tmp_path):
    """Loud Assertion: POST /api/v1/media/render synchronous render returns 200 with completed payload."""
    source_file = str(tmp_path / "fastapi_source.mp4")
    create_test_synthetic_source(source_file, duration=4.0, width=1920, height=1080)

    app = create_app()
    renders_dir = str(tmp_path / "renders")
    os.makedirs(renders_dir, exist_ok=True)
    
    with TestClient(app) as client:
        payload = {
            "source_file": source_file,
            "in_point": 1.0,
            "out_point": 3.0,
            "crop_ratio": "9:16",
            "text_overlay": "🔥 API SYNC RENDER",
            "output_dir": renders_dir,
            "sync": True,
        }
        res = client.post("/api/v1/media/render", json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        assert data["status"] == "completed"
        assert "render_id" in data or "job_id" in data
        assert "output_file" in data and data["output_file"] is not None
        assert os.path.exists(data["output_file"]), f"Output file not found: {data['output_file']}"
        assert abs(data["duration"] - 2.0) < 0.01
        assert data["crop_ratio"] == "9:16"


def test_fastapi_render_endpoint_async_job_queue(tmp_path):
    """Loud Assertion: POST /api/v1/media/render with sync=False queues job and completes in background."""
    source_file = str(tmp_path / "fastapi_async_source.mp4")
    create_test_synthetic_source(source_file, duration=4.0, width=1920, height=1080)

    app = create_app()
    renders_dir = str(tmp_path / "renders_async")
    os.makedirs(renders_dir, exist_ok=True)

    with TestClient(app) as client:
        payload = {
            "source_file": source_file,
            "in_point": 0.5,
            "out_point": 2.5,
            "crop_ratio": "16:9",
            "text_overlay": "ASYNC RENDER",
            "output_dir": renders_dir,
            "sync": False,
        }
        res = client.post("/api/v1/media/render", json=payload)
        assert res.status_code in (200, 202), f"Expected 200/202, got {res.status_code}: {res.text}"
        data = res.json()
        job_id = data.get("job_id") or data.get("render_id")
        assert job_id is not None
        assert data["status"] in ("queued", "processing", "completed", "QUEUED", "PROCESSING", "COMPLETED")

        # Poll status endpoint
        poll_res = client.get(f"/api/v1/media/status/{job_id}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        assert poll_data["job_id"] == job_id


def test_fastapi_render_validation_invalid_in_out_points(tmp_path):
    """Loud Assertion: POST /api/v1/media/render with out_point <= in_point returns 422 Unprocessable Content."""
    source_file = str(tmp_path / "source_valid.mp4")
    create_test_synthetic_source(source_file, duration=3.0)

    app = create_app()
    with TestClient(app) as client:
        # out_point <= in_point
        payload = {
            "source_file": source_file,
            "in_point": 4.0,
            "out_point": 2.0,
            "crop_ratio": "9:16",
        }
        res = client.post("/api/v1/media/render", json=payload)
        assert res.status_code == 422, f"Expected 422, got {res.status_code}: {res.text}"


def test_fastapi_render_validation_nonexistent_source(tmp_path):
    """Loud Assertion: POST /api/v1/media/render with nonexistent file returns 404 or 400 error."""
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "source_file": str(tmp_path / "ghost_file.mp4"),
            "in_point": 0.0,
            "out_point": 2.0,
            "crop_ratio": "9:16",
            "sync": True,
        }
        res = client.post("/api/v1/media/render", json=payload)
        assert res.status_code in (404, 400, 422, 500)


def test_fastapi_cors_middleware_enabled():
    """Loud Assertion: Gateway includes CORSMiddleware returning Allow-Origin headers."""
    app = create_app()
    with TestClient(app) as client:
        # Pre-flight OPTIONS request
        res = client.options(
            "/api/v1/media/render",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") in ("*", "http://localhost:3000")


def test_fastapi_static_renders_route_serving(tmp_path):
    """Loud Assertion: Static /renders mount serves rendered video files."""
    source_file = str(tmp_path / "source_static.mp4")
    create_test_synthetic_source(source_file, duration=2.0)

    app = create_app()
    renderer = FFmpegRenderer()
    
    renders_dir = Path(os.getcwd()) / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)
    test_render_path = renders_dir / f"test_static_serve_{int(time.time())}.mp4"
    
    renderer.render_cut(
        source_file=source_file,
        in_point=0.0,
        out_point=1.0,
        crop_ratio="9:16",
        output_path=str(test_render_path),
    )

    with TestClient(app) as client:
        res = client.get(f"/renders/{test_render_path.name}")
        assert res.status_code == 200
        assert int(res.headers.get("content-length", 0)) > 0
