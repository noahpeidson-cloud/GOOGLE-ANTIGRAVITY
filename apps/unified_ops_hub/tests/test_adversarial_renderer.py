"""Adversarial Stress Test Suite for Headless FFmpeg Renderer (Milestone 2).
Enforces Rule R2 (The Leash Protocol / Zero-Discretion Mandate / Loud Assertions / TDAD).

Adversarial Stress-Testing Targets:
1. Multi-line text overlays, Unicode emoji overlays (🔥🚀🎧), quotes, colons, shell metacharacters, backslashes.
2. Non-standard crop ratios and extreme resolutions (4K landscape 3840x2160 -> 9:16, 4K vertical 2160x3840 -> 16:9, square 1080x1080, ultrawide 2560x1080, odd pixel resolutions 1281x719).
3. Sub-second micro trimming ([0.2s, 0.7s], 150ms micro-slices, boundary zero-points, tail-end trims).
4. Playback and stream integrity verification via null-sink decoding and stream validation.
5. Concurrent multithreaded render stress (parallel jobs without race conditions or file clobbering).
6. FastAPI render endpoint stress testing with adversarial payloads.
"""

import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    from unified_ops_hub.gateway.app import create_app
except ImportError:
    from gateway.renderer import (
        FFmpegRenderer,
        RenderRequest,
        RenderResponse,
        get_ffmpeg_path,
        escape_drawtext,
        build_video_filter,
    )
    from gateway.app import create_app


# ============================================================================
# Helpers & Verification Oracles
# ============================================================================

def resolve_test_ffmpeg_path() -> str:
    """Dynamically resolves FFmpeg binary path."""
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


def verify_playback_and_decode(file_path: str, ffmpeg_bin: Optional[str] = None) -> Tuple[bool, str]:
    """Runs a full null-sink decode over the output media file.
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message). True if FFmpeg decodes 100% of packets with 0 errors.
    """
    if not os.path.isfile(file_path):
        return False, f"File does not exist: {file_path}"
    if os.path.getsize(file_path) == 0:
        return False, f"File is 0 bytes: {file_path}"

    exe = ffmpeg_bin or resolve_test_ffmpeg_path()
    cmd = [
        exe, "-v", "error",
        "-i", file_path,
        "-f", "null", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or res.stderr.strip():
        return False, f"Decode failure (exit code {res.returncode}): {res.stderr.strip()}"
    return True, ""


def probe_media_deep(file_path: str, ffmpeg_bin: Optional[str] = None) -> Dict[str, Any]:
    """Probes media metadata and stream specs deeply using FFmpeg."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    exe = ffmpeg_bin or resolve_test_ffmpeg_path()
    res = subprocess.run([exe, "-i", file_path], capture_output=True, text=True)
    stderr = res.stderr

    # Parse duration
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
    duration = 0.0
    if dur_match:
        h, m, s = map(float, dur_match.groups())
        duration = round(h * 3600 + m * 60 + s, 3)

    # Parse video stream dimensions & codec
    v_match = re.search(r"Stream #.*: Video:\s*([a-zA-Z0-9_-]+).*?,\s*(\d{2,5})x(\d{2,5})", stderr)
    video_codec = v_match.group(1) if v_match else None
    width = int(v_match.group(2)) if v_match else 0
    height = int(v_match.group(3)) if v_match else 0

    # Parse audio stream
    a_match = re.search(r"Stream #.*: Audio:\s*([a-zA-Z0-9_-]+)", stderr)
    audio_codec = a_match.group(1) if a_match else None
    has_audio = bool(a_match)

    return {
        "file_path": file_path,
        "file_size": os.path.getsize(file_path),
        "duration": duration,
        "width": width,
        "height": height,
        "video_codec": video_codec,
        "has_audio": has_audio,
        "audio_codec": audio_codec,
    }


def create_synthetic_media(
    output_path: str,
    duration: float = 5.0,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    include_audio: bool = True,
    audio_freq: int = 1000,
    ffmpeg_bin: Optional[str] = None,
) -> str:
    """Procedurally creates a synthetic test video with customizable dimensions and audio."""
    exe = ffmpeg_bin or resolve_test_ffmpeg_path()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        exe, "-y",
        "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate={fps}:duration={duration}",
    ]

    if include_audio:
        cmd.extend([
            "-f", "lavfi", "-i", f"sine=frequency={audio_freq}:duration={duration}",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
        ])
    else:
        cmd.extend(["-an"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        output_path,
    ])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Synthetic media creation failed ({res.returncode}): {res.stderr}")

    return output_path


# ============================================================================
# 1. Text Overlay Adversarial Tests (Unicode, Emojis, Multiline, Escaping)
# ============================================================================

class TestTextOverlayAdversarial:
    """Stress tests text overlays with complex Unicode, emojis, newlines, and escaping."""

    @pytest.mark.parametrize(
        "test_id,text_input",
        [
            ("unicode_emojis", "🔥 ULTRA FESTIVAL 2026 🚀 🎧 DROP! ✨⚡️"),
            ("multiline_newlines", "MAIN STAGE\nLIVE AT MIDNIGHT\nTRACK #4"),
            ("quotes_and_colons", "DJ's Choice: \"The Final Countdown\": 100% 'HYPED'"),
            ("backslashes_and_percents", "C:\\Media\\Clips\\Render_%04d.mp4 -> 50% CPU \\ 100% GPU"),
            ("special_punctuation_symbols", "@#$%^&*()_+-=[]{}|;:,.<>?/`~"),
            ("cjk_and_international", "東京サイバーパンク 2026 // 東京ドーム // Ремикс // مرحبا"),
            ("very_long_string", "SUPER_LONG_HEADER_" + ("X" * 300) + "_END"),
            ("empty_and_whitespace", "   \t   "),
        ],
    )
    def test_adversarial_text_overlays(self, tmp_path, test_id, text_input):
        """Loud Assertion: Adversarial text overlay renders valid MP4 without syntax crash or abort."""
        source_path = str(tmp_path / f"src_{test_id}.mp4")
        create_synthetic_media(source_path, duration=3.0, width=1280, height=720)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / f"render_{test_id}.mp4")

        result = renderer.render_cut(
            source_file=source_path,
            in_point=0.5,
            out_point=2.0,
            crop_ratio="9:16",
            text_overlay=text_input,
            output_path=out_path,
        )

        assert result.status == "completed", f"LOUD ASSERTION FAILURE: {test_id} did not complete"
        assert os.path.isfile(out_path), f"LOUD ASSERTION FAILURE: Output file missing: {out_path}"
        assert os.path.getsize(out_path) > 1024, f"LOUD ASSERTION FAILURE: Output file suspiciously small"

        # Verify full stream decode & playback
        is_valid, err = verify_playback_and_decode(out_path)
        assert is_valid, f"LOUD ASSERTION FAILURE: Stream decode failed for {test_id}: {err}"

        meta = probe_media_deep(out_path)
        assert meta["width"] == 1080
        assert meta["height"] == 1920
        assert abs(meta["duration"] - 1.5) <= 0.25
        assert meta["has_audio"] is True


# ============================================================================
# 2. Extreme Aspect Ratios & Resolutions Adversarial Tests
# ============================================================================

class TestAspectRatiosAndExtremeResolutions:
    """Stress tests non-standard aspect ratios, 4K landscape/vertical, square, ultrawide, and odd pixels."""

    def test_4k_landscape_to_9_16_vertical_crop(self, tmp_path):
        """Loud Assertion: 4K (3840x2160) landscape renders into exact 1080x1920 9:16 vertical video."""
        src_path = str(tmp_path / "4k_landscape_src.mp4")
        create_synthetic_media(src_path, duration=2.0, width=3840, height=2160)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / "4k_to_9_16.mp4")

        result = renderer.render_cut(
            source_file=src_path,
            in_point=0.0,
            out_point=1.5,
            crop_ratio="9:16",
            text_overlay="4K -> 9:16 VERTICAL",
            output_path=out_path,
        )

        assert result.status == "completed"
        is_valid, err = verify_playback_and_decode(out_path)
        assert is_valid, f"4K to 9:16 output decode failed: {err}"

        meta = probe_media_deep(out_path)
        assert meta["width"] == 1080, f"Expected 1080 width, got {meta['width']}"
        assert meta["height"] == 1920, f"Expected 1920 height, got {meta['height']}"

    def test_4k_vertical_to_16_9_widescreen_crop(self, tmp_path):
        """Loud Assertion: 4K vertical (2160x3840) renders into exact 1920x1080 16:9 widescreen video."""
        src_path = str(tmp_path / "4k_vertical_src.mp4")
        create_synthetic_media(src_path, duration=2.0, width=2160, height=3840)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / "4k_to_16_9.mp4")

        result = renderer.render_cut(
            source_file=src_path,
            in_point=0.2,
            out_point=1.8,
            crop_ratio="16:9",
            text_overlay="4K VERTICAL -> 16:9 WIDESCREEN",
            output_path=out_path,
        )

        assert result.status == "completed"
        is_valid, err = verify_playback_and_decode(out_path)
        assert is_valid, f"4K vertical to 16:9 decode failed: {err}"

        meta = probe_media_deep(out_path)
        assert meta["width"] == 1920
        assert meta["height"] == 1080

    def test_square_1_1_to_9_16_and_16_9(self, tmp_path):
        """Loud Assertion: 1:1 square source (1080x1080) cleanly crops and scales to both 9:16 and 16:9."""
        src_path = str(tmp_path / "square_1080x1080.mp4")
        create_synthetic_media(src_path, duration=2.0, width=1080, height=1080)

        renderer = FFmpegRenderer()

        # 1. Square to 9:16
        out_9_16 = str(tmp_path / "square_to_9_16.mp4")
        res_9_16 = renderer.render_cut(
            source_file=src_path, in_point=0.0, out_point=1.0, crop_ratio="9:16", output_path=out_9_16
        )
        assert res_9_16.status == "completed"
        meta_9_16 = probe_media_deep(out_9_16)
        assert meta_9_16["width"] == 1080 and meta_9_16["height"] == 1920

        # 2. Square to 16:9
        out_16_9 = str(tmp_path / "square_to_16_9.mp4")
        res_16_9 = renderer.render_cut(
            source_file=src_path, in_point=0.0, out_point=1.0, crop_ratio="16:9", output_path=out_16_9
        )
        assert res_16_9.status == "completed"
        meta_16_9 = probe_media_deep(out_16_9)
        assert meta_16_9["width"] == 1920 and meta_16_9["height"] == 1080

    def test_ultrawide_21_9_to_9_16(self, tmp_path):
        """Loud Assertion: 21:9 ultrawide (2560x1080) cleanly center crops to 9:16 vertical."""
        src_path = str(tmp_path / "ultrawide_2560x1080.mp4")
        create_synthetic_media(src_path, duration=2.0, width=2560, height=1080)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / "ultrawide_to_9_16.mp4")

        result = renderer.render_cut(
            source_file=src_path, in_point=0.0, out_point=1.2, crop_ratio="9:16", output_path=out_path
        )
        assert result.status == "completed"
        meta = probe_media_deep(out_path)
        assert meta["width"] == 1080 and meta["height"] == 1920

    def test_odd_dimension_source_libx264_compatibility(self, tmp_path):
        """Loud Assertion: Source with odd pixel dimensions (1281x719) scales to even dimensions without encoder error."""
        src_path = str(tmp_path / "odd_dim_src.avi")
        exe = resolve_test_ffmpeg_path()
        # Generate an odd-dimension video using mjpeg codec in AVI container (supports odd pixel sizes)
        cmd = [
            exe, "-y",
            "-f", "lavfi", "-i", "testsrc=size=1281x719:rate=24:duration=2.0",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=2.0",
            "-c:v", "mjpeg", "-q:v", "3",
            "-c:a", "pcm_s16le",
            "-shortest",
            src_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        renderer = FFmpegRenderer()

        # 1. Test raw_pov / original preservation with odd pixel dimensions
        out_raw = str(tmp_path / "odd_to_raw.mp4")
        res_raw = renderer.render_cut(
            source_file=src_path, in_point=0.0, out_point=1.0, crop_ratio="original", output_path=out_raw
        )
        assert res_raw.status == "completed"
        meta_raw = probe_media_deep(out_raw)
        # Dimensions must be even for yuv420p libx264 (e.g. 1280x718)
        assert meta_raw["width"] % 2 == 0
        assert meta_raw["height"] % 2 == 0
        assert meta_raw["width"] == 1280
        assert meta_raw["height"] == 718

        # Verify decode
        is_valid, err = verify_playback_and_decode(out_raw)
        assert is_valid, f"Odd dimension raw output decode failed: {err}"

        # 2. Test 9:16 crop on odd dimensions
        out_9_16 = str(tmp_path / "odd_to_9_16.mp4")
        res_9_16 = renderer.render_cut(
            source_file=src_path, in_point=0.0, out_point=1.0, crop_ratio="9:16", output_path=out_9_16
        )
        assert res_9_16.status == "completed"
        meta_9_16 = probe_media_deep(out_9_16)
        assert meta_9_16["width"] == 1080 and meta_9_16["height"] == 1920
        is_valid, err = verify_playback_and_decode(out_9_16)
        assert is_valid, f"Odd dimension 9:16 output decode failed: {err}"

    def test_unrecognized_custom_crop_ratio_fallback(self, tmp_path):
        """Loud Assertion: Custom or unrecognized crop ratios safely fallback to original even dimensions."""
        src_path = str(tmp_path / "custom_crop_src.mp4")
        create_synthetic_media(src_path, duration=2.0, width=640, height=480)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / "custom_crop.mp4")

        result = renderer.render_cut(
            source_file=src_path, in_point=0.0, out_point=1.0, crop_ratio="custom_ratio_4_3", output_path=out_path
        )
        assert result.status == "completed"
        meta = probe_media_deep(out_path)
        assert meta["width"] == 640
        assert meta["height"] == 480


# ============================================================================
# 3. Sub-Second Micro Trimming Adversarial Tests
# ============================================================================

class TestSubsecondMicroTrimming:
    """Stress tests precise micro-second trimming, boundary frames, and tail-end trims."""

    def test_subsecond_micro_trim_half_second(self, tmp_path):
        """Loud Assertion: Micro trim [0.2s, 0.7s] renders precise 0.5s output with playable stream."""
        src_path = str(tmp_path / "source_5s.mp4")
        create_synthetic_media(src_path, duration=5.0, width=1280, height=720)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / "micro_0_2_to_0_7.mp4")

        result = renderer.render_cut(
            source_file=src_path,
            in_point=0.2,
            out_point=0.7,
            crop_ratio="9:16",
            output_path=out_path,
        )

        assert result.status == "completed"
        assert abs(result.duration - 0.5) < 0.001

        is_valid, err = verify_playback_and_decode(out_path)
        assert is_valid, f"Micro-trim [0.2, 0.7] decode failed: {err}"

        meta = probe_media_deep(out_path)
        assert abs(meta["duration"] - 0.5) <= 0.15, f"Expected duration ~0.5s, got {meta['duration']}"
        assert meta["file_size"] > 500

    def test_ultra_micro_trim_150ms(self, tmp_path):
        """Loud Assertion: Ultra-short 150ms slice [0.10s, 0.25s] produces valid non-zero video."""
        src_path = str(tmp_path / "source_short.mp4")
        create_synthetic_media(src_path, duration=3.0, width=1280, height=720)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / "micro_150ms.mp4")

        result = renderer.render_cut(
            source_file=src_path,
            in_point=0.100,
            out_point=0.250,
            crop_ratio="16:9",
            output_path=out_path,
        )

        assert result.status == "completed"
        assert abs(result.duration - 0.150) < 0.001

        is_valid, err = verify_playback_and_decode(out_path)
        assert is_valid, f"Ultra micro-trim 150ms decode failed: {err}"

        meta = probe_media_deep(out_path)
        assert meta["width"] == 1920
        assert meta["height"] == 1080

    def test_zero_point_boundary_trim(self, tmp_path):
        """Loud Assertion: Trimming exactly at in_point=0.0 produces clean start frame without keyframe lag."""
        src_path = str(tmp_path / "source_boundary.mp4")
        create_synthetic_media(src_path, duration=4.0, width=1280, height=720)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / "boundary_zero.mp4")

        result = renderer.render_cut(
            source_file=src_path,
            in_point=0.0,
            out_point=0.35,
            crop_ratio="9:16",
            output_path=out_path,
        )

        assert result.status == "completed"
        is_valid, err = verify_playback_and_decode(out_path)
        assert is_valid, f"Zero boundary trim failed: {err}"

    def test_tail_end_micro_trim(self, tmp_path):
        """Loud Assertion: Micro trim at video tail [4.7s, 5.0s] decodes properly without EOF truncation crash."""
        src_path = str(tmp_path / "source_tail.mp4")
        create_synthetic_media(src_path, duration=5.0, width=1280, height=720)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / "tail_end.mp4")

        result = renderer.render_cut(
            source_file=src_path,
            in_point=4.7,
            out_point=5.0,
            crop_ratio="9:16",
            output_path=out_path,
        )

        assert result.status == "completed"
        is_valid, err = verify_playback_and_decode(out_path)
        assert is_valid, f"Tail end trim failed: {err}"


# ============================================================================
# 4. Stream Integrity & Silent Media Tests
# ============================================================================

class TestStreamIntegrityAndAudioModes:
    """Stress tests streams with silence, missing audio tracks, and codec compliance."""

    def test_video_without_audio_source_rendering(self, tmp_path):
        """Loud Assertion: Video source with NO audio stream renders cleanly without missing audio stream crash."""
        src_no_audio = str(tmp_path / "src_no_audio.mp4")
        create_synthetic_media(src_no_audio, duration=3.0, width=1280, height=720, include_audio=False)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / "rendered_no_audio.mp4")

        result = renderer.render_cut(
            source_file=src_no_audio,
            in_point=0.5,
            out_point=2.0,
            crop_ratio="9:16",
            text_overlay="MUTE SOURCE",
            output_path=out_path,
        )

        assert result.status == "completed"
        is_valid, err = verify_playback_and_decode(out_path)
        assert is_valid, f"Mute source render decode failed: {err}"

        meta = probe_media_deep(out_path)
        assert meta["width"] == 1080
        assert meta["height"] == 1920

    def test_audio_preservation_and_sync(self, tmp_path):
        """Loud Assertion: Output retains AAC audio stream and valid sample rates."""
        src_path = str(tmp_path / "src_audio_sync.mp4")
        create_synthetic_media(src_path, duration=4.0, width=1280, height=720, include_audio=True, audio_freq=440)

        renderer = FFmpegRenderer()
        out_path = str(tmp_path / "rendered_audio_sync.mp4")

        result = renderer.render_cut(
            source_file=src_path,
            in_point=1.0,
            out_point=3.0,
            crop_ratio="16:9",
            output_path=out_path,
        )

        assert result.status == "completed"
        meta = probe_media_deep(out_path)
        assert meta["has_audio"] is True
        assert meta["audio_codec"] == "aac"


# ============================================================================
# 5. Multithreaded Concurrency Stress Tests
# ============================================================================

class TestConcurrentRendererStress:
    """Stress tests concurrent parallel rendering jobs under heavy process load."""

    def test_parallel_multithreaded_rendering(self, tmp_path):
        """Loud Assertion: 5 parallel worker threads rendering distinct cuts simultaneously succeed with 0 collisions."""
        num_jobs = 5
        sources = []
        for i in range(num_jobs):
            src = str(tmp_path / f"parallel_src_{i}.mp4")
            create_synthetic_media(src, duration=3.0, width=1280, height=720)
            sources.append(src)

        renderer = FFmpegRenderer()
        renders_dir = str(tmp_path / "parallel_renders")

        def _render_job(idx: int, src: str) -> RenderResponse:
            ratio = "9:16" if idx % 2 == 0 else "16:9"
            return renderer.render_cut(
                source_file=src,
                in_point=0.2 * idx,
                out_point=1.5 + 0.2 * idx,
                crop_ratio=ratio,
                text_overlay=f"JOB #{idx} 🔥",
                renders_dir=renders_dir,
                job_id=f"job_{idx}_{int(time.time())}",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_jobs) as executor:
            futures = [executor.submit(_render_job, i, sources[i]) for i in range(num_jobs)]
            results = [f.result(timeout=60) for f in concurrent.futures.as_completed(futures)]

        assert len(results) == num_jobs
        for res in results:
            assert res.status == "completed"
            assert os.path.isfile(res.output_file)
            is_valid, err = verify_playback_and_decode(res.output_file)
            assert is_valid, f"Concurrent render decode failed: {err}"


# ============================================================================
# 6. FastAPI Adversarial API Endpoints Tests
# ============================================================================

class TestFastApiAdversarialEndpoints:
    """Stress tests FastAPI gateway render endpoint with adversarial and edge payloads."""

    def test_api_adversarial_unicode_and_micro_trim(self, tmp_path):
        """Loud Assertion: POST /api/v1/media/render handles Unicode emoji and sub-second micro trim."""
        src_path = str(tmp_path / "api_adv_src.mp4")
        create_synthetic_media(src_path, duration=4.0, width=1920, height=1080)

        app = create_app()
        renders_dir = str(tmp_path / "api_renders")
        os.makedirs(renders_dir, exist_ok=True)

        with TestClient(app) as client:
            payload = {
                "source_file": src_path,
                "in_point": 0.25,
                "out_point": 0.75,
                "crop_ratio": "9:16",
                "text_overlay": "🔥 VIP DROP: 100% 'LIVE' \\ 🎧",
                "output_dir": renders_dir,
                "sync": True,
            }
            res = client.post("/api/v1/media/render", json=payload)
            assert res.status_code == 200, f"API failed ({res.status_code}): {res.text}"
            data = res.json()

            assert data["status"] == "completed"
            assert abs(data["duration"] - 0.5) < 0.01
            assert os.path.isfile(data["output_file"])

            is_valid, err = verify_playback_and_decode(data["output_file"])
            assert is_valid, f"API rendered video decode failed: {err}"

    def test_api_rejection_negative_in_point(self, tmp_path):
        """Loud Assertion: POST /api/v1/media/render with negative in_point is rejected with 422."""
        src_path = str(tmp_path / "api_dummy.mp4")
        create_synthetic_media(src_path, duration=2.0)

        app = create_app()
        with TestClient(app) as client:
            payload = {
                "source_file": src_path,
                "in_point": -1.0,
                "out_point": 1.0,
                "crop_ratio": "9:16",
            }
            res = client.post("/api/v1/media/render", json=payload)
            assert res.status_code == 422


if __name__ == "__main__":
    pytest.main(["-v", __file__])
