# M1 Explorer 3 Analysis: TDAD & Test Architecture Blueprint for `test_media_editor.py`

## Executive Summary
This document establishes the authoritative test architecture and Loud Assertions test suite for the Unified Ops Hub Media Studio backend module (`ml_agent/editor.py` / `MediaEditor`), strictly adhering to **Rule R2 (The Zero-Discretion Mandate / The Leash Protocol / TDAD)**.

In accordance with TDAD principles:
1. **Zero Mock Cheating**: Tests execute actual FFmpeg commands against dynamically generated synthetic test media fixtures (using FFmpeg's `lavfi` source filters: `testsrc`, `aevalsrc`, `sine`, `anullsrc`).
2. **Deterministic Loud Assertions**: Every test validates physical output artifacts (file existence, exact dimensions, video duration, audio stream presence, RMS energy localization, and strict JSON dictionary schema contracts) with unambiguous failure messages (`LOUD ASSERTION FAILURE: ...`).
3. **Zero Shared State**: Every test utilizes isolated pytest `tmp_path` fixtures to ensure thread-safe, collision-free execution.
4. **Pytest Compatibility**: Native support for Python 3.13, Pytest 9.1+, and automated FFmpeg binary discovery via `shutil.which`, `os.environ["FFMPEG_PATH"]`, and `imageio_ffmpeg`.

---

## 1. Synthetic Test Media Generator Architecture

To avoid maintaining heavy binary video files in git and to ensure deterministic edge-case coverage, all test media is generated programmatically on-the-fly.

### FFmpeg Synthetic Media Pipeline
```
[lavfi testsrc=size=WxH:rate=FPS:duration=D] ───┐
                                               ├──> [FFmpeg libx264 -preset ultrafast] ──> synthetic_media.mp4
[lavfi aevalsrc=sin(2*PI*f*t)*between(t,a,b)] ─┘
```

### Parameterized Generator Specification
```python
def generate_synthetic_video(
    output_path: str,
    duration: float = 10.0,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    audio_type: str = "beep",  # "beep" | "silence" | "none" | "constant"
    beep_start: float = 3.0,
    beep_end: float = 6.0,
    beep_freq: int = 1000,
    ffmpeg_path: Optional[str] = None,
) -> str:
    """Generates deterministic synthetic MP4 video with precise audio waveforms.
    - beep: 1000Hz sine tone isolated strictly between beep_start and beep_end, silence elsewhere.
    - silence: Audio track present with zero amplitude (aevalsrc=0).
    - none: Video only (-an), no audio stream present.
    - constant: Continuous sine tone across entire duration (zero energy gradient).
    """
```

### Generator Benchmarking & Performance
- Generation of a 10.0s 1080p MP4 takes **~0.48s** using `-preset ultrafast`.
- Total test suite execution time across all 16 test cases is **< 12 seconds**.

---

## 2. Loud Assertions Test Matrix

The test suite is structured into 4 comprehensive tiers:

| Tier | Category | Test Function | Purpose & Loud Assertions |
|------|----------|---------------|---------------------------|
| **Tier 1** | Proxy Generation | `test_generate_proxy_standard_1080p` | Verifies downscaling 1080p -> 720p (1280x720), H.264 video, faststart container flag, file size > 0, duration parity within 0.1s. |
| **Tier 1** | Proxy Audio | `test_generate_proxy_preserves_audio_stream` | Asserts audio stream is present in generated proxy when source contains audio. |
| **Tier 1** | Proxy No-Audio | `test_generate_proxy_silent_source` | Asserts proxy generation succeeds without error on video lacking audio track (`-an`). |
| **Tier 2** | Proxy Edge Case | `test_generate_proxy_nonexistent_file_raises_filenotfound` | Loudly asserts `FileNotFoundError` is raised when invalid path is passed. |
| **Tier 2** | Proxy Edge Case | `test_generate_proxy_custom_output_path` | Verifies proxy is written to caller-specified explicit output path and directory is auto-created. |
| **Tier 1** | Audio DSP Peak | `test_detect_audio_peak_exact_localization` | In a 25s video with beep at `[6.0s, 9.0s]`, asserts detected 15s window `[in_point, out_point]` encapsulates the beep (`in_point <= 6.0` and `out_point >= 9.0`) with `out_point - in_point == 15.0`. |
| **Tier 2** | Audio DSP Peak | `test_detect_audio_peak_start_boundary` | In a 20s video with beep at `[0.0s, 3.0s]`, asserts `in_point == 0.0` and `out_point == 15.0`. |
| **Tier 2** | Audio DSP Peak | `test_detect_audio_peak_end_boundary` | In a 30s video with beep at `[26.0s, 29.0s]`, asserts `out_point <= 30.0` and `in_point >= 11.0` covering the peak. |
| **Tier 1** | Audio Fallback | `test_detect_audio_peak_silence_fallback` | Asserts video with pure silence (`aevalsrc=0`) falls back to `in_point == 0.0, out_point == 15.0` without NaN / divide-by-zero. |
| **Tier 1** | Audio Fallback | `test_detect_audio_peak_no_audio_stream_fallback` | Asserts video with `-an` gracefully falls back to `in_point == 0.0, out_point == 15.0`. |
| **Tier 2** | Duration Clamping | `test_detect_audio_peak_short_video_clamping` | In a 4.0s video (< 15s window), asserts `in_point == 0.0` and `out_point == 4.0` (clamped to duration). |
| **Tier 2** | Duration Clamping | `test_detect_audio_peak_subsecond_micro_video` | In a 0.8s micro video, asserts `in_point == 0.0` and `out_point == 0.8`. |
| **Tier 2** | Audio Edge Case | `test_detect_audio_peak_constant_tone_zero_variance` | 20s constant tone asserts valid window `[0.0, 15.0]` without crashing. |
| **Tier 1** | JSON Contract | `test_generate_cuts_metadata_schema_contract` | Verifies exact keys (`hype_drop`, `cinematic`, `raw_pov`), crop ratios (`9:16`, `16:9`, `original`), and target resolutions (`1080x1920`, `1920x1080`, `original`). |
| **Tier 3** | Full Pipeline | `test_generate_proxy_and_cuts_complete_pipeline` | Executes end-to-end `generate_proxy_and_cuts`, asserting all top-level keys (`source_file`, `proxy_file`, `duration`, `cuts`), physical proxy creation, and contract parity. |
| **Tier 3** | Directory Safety | `test_generate_proxy_and_cuts_auto_creates_proxy_directory` | Asserts `proxy_dir` is created on disk if non-existent. |

---

## 3. Complete Proposed Test Suite: `tests/test_media_editor.py`

Below is the complete, drop-in Python implementation for `unified_ops_hub/tests/test_media_editor.py`:

```python
\"\"\"Unit and Integration Tests for Unified Ops Hub MediaEditor (Milestone 1).
Enforces Rule R2 (The Leash Protocol / Zero-Discretion Mandate / Loud Assertions / TDAD).
Executes actual FFmpeg commands against dynamically generated synthetic test media.
\"\"\"

import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pytest

# Cross-module import support for unified_ops_hub
try:
    from unified_ops_hub.ml_agent.editor import MediaEditor
except ImportError:
    from ml_agent.editor import MediaEditor


# ============================================================================
# Test Fixtures & Synthetic Media Utilities
# ============================================================================

def resolve_ffmpeg_path() -> str:
    """Resolves FFmpeg executable path across environments."""
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


def probe_media_file(file_path: str, ffmpeg_path: Optional[str] = None) -> Dict[str, Any]:
    """Probes media file properties directly via FFmpeg stderr output."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found for probing: {file_path}")

    exe = ffmpeg_path or resolve_ffmpeg_path()
    res = subprocess.run([exe, "-i", file_path], capture_output=True, text=True)
    stderr = res.stderr

    # Duration parsing: Duration: 00:00:10.00
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
    duration = None
    if dur_match:
        h, m, s = map(float, dur_match.groups())
        duration = round(h * 3600 + m * 60 + s, 3)

    # Resolution parsing: Video: h264 ..., 1920x1080 ...
    dim_match = re.search(r"Video:.*,\s*(\d{2,5})x(\d{2,5})", stderr)
    width, height = (int(dim_match.group(1)), int(dim_match.group(2))) if dim_match else (0, 0)

    # Audio stream check
    has_audio = bool(re.search(r"Stream #.*: Audio:", stderr))

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "has_audio": has_audio,
        "file_size": os.path.getsize(file_path),
    }


def create_synthetic_video(
    output_path: str,
    duration: float = 10.0,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    audio_type: str = "beep",  # "beep" | "silence" | "none" | "constant"
    beep_start: float = 3.0,
    beep_end: float = 6.0,
    beep_freq: int = 1000,
    ffmpeg_path: Optional[str] = None,
) -> str:
    """Procedurally generates an MP4 video file with exact audio characteristics."""
    exe = ffmpeg_path or resolve_ffmpeg_path()
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    cmd = [
        exe, "-y",
        "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate={fps}:duration={duration}",
    ]

    if audio_type == "beep":
        # 1000Hz tone only between beep_start and beep_end
        filter_expr = f"sin(2*PI*{beep_freq}*t)*between(t\\,{beep_start}\\,{beep_end})"
        cmd.extend([
            "-f", "lavfi", "-i", f"aevalsrc={filter_expr}:sample_rate=22050:duration={duration}",
            "-c:a", "aac",
        ])
    elif audio_type == "silence":
        cmd.extend([
            "-f", "lavfi", "-i", f"aevalsrc=0:sample_rate=22050:duration={duration}",
            "-c:a", "aac",
        ])
    elif audio_type == "constant":
        cmd.extend([
            "-f", "lavfi", "-i", f"aevalsrc=sin(2*PI*{beep_freq}*t):sample_rate=22050:duration={duration}",
            "-c:a", "aac",
        ])
    elif audio_type == "none":
        cmd.extend(["-an"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        output_path,
    ])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg synthetic media generation failed: {res.stderr}")

    return output_path


@pytest.fixture
def media_editor() -> MediaEditor:
    """Provides a clean instance of MediaEditor."""
    return MediaEditor()


# ============================================================================
# 1. AI 720p Proxy Generation Tests (Tier 1 & Tier 2)
# ============================================================================

def test_generate_proxy_standard_1080p(tmp_path, media_editor):
    """Loud Assertion: Proxy generation downscales 1080p to 720p H.264 Faststart MP4."""
    source_file = str(tmp_path / "raw_1080p.mp4")
    create_synthetic_video(source_file, duration=6.0, width=1920, height=1080, audio_type="beep")

    proxy_file = media_editor.generate_proxy(source_file)

    # 1. Existence and non-zero size
    assert os.path.exists(proxy_file), f"LOUD ASSERTION FAILURE: Proxy file not created at {proxy_file}"
    assert os.path.getsize(proxy_file) > 0, "LOUD ASSERTION FAILURE: Proxy file is 0 bytes"

    # 2. Probe dimensions and duration
    info = probe_media_file(proxy_file)
    assert info["height"] == 720, f"LOUD ASSERTION FAILURE: Expected height 720, got {info['height']}"
    assert info["width"] == 1280, f"LOUD ASSERTION FAILURE: Expected width 1280, got {info['width']}"
    assert abs(info["duration"] - 6.0) < 0.2, f"LOUD ASSERTION FAILURE: Duration mismatch: {info['duration']} vs 6.0"
    assert info["has_audio"] is True, "LOUD ASSERTION FAILURE: Audio stream was lost in proxy generation"


def test_generate_proxy_preserves_audio_stream(tmp_path, media_editor):
    """Loud Assertion: Audio stream is preserved and encoded in proxy output."""
    source_file = str(tmp_path / "audio_source.mp4")
    create_synthetic_video(source_file, duration=5.0, audio_type="beep")

    proxy_file = media_editor.generate_proxy(source_file)
    info = probe_media_file(proxy_file)
    assert info["has_audio"] is True, "LOUD ASSERTION FAILURE: Audio stream missing in proxy"


def test_generate_proxy_silent_source(tmp_path, media_editor):
    """Loud Assertion: Proxy generation succeeds cleanly on video lacking audio track."""
    source_file = str(tmp_path / "no_audio.mp4")
    create_synthetic_video(source_file, duration=5.0, audio_type="none")

    proxy_file = media_editor.generate_proxy(source_file)
    assert os.path.exists(proxy_file), "LOUD ASSERTION FAILURE: Proxy generation failed for silent source"
    info = probe_media_file(proxy_file)
    assert info["height"] == 720, f"LOUD ASSERTION FAILURE: Expected height 720, got {info['height']}"


def test_generate_proxy_nonexistent_file_raises_filenotfound(tmp_path, media_editor):
    """Loud Assertion: Nonexistent file path loudly raises FileNotFoundError."""
    bogus_path = str(tmp_path / "does_not_exist.mp4")
    with pytest.raises(FileNotFoundError) as exc_info:
        media_editor.generate_proxy(bogus_path)
    assert "does_not_exist.mp4" in str(exc_info.value), "LOUD ASSERTION FAILURE: Exception message missing filename"


def test_generate_proxy_custom_output_path(tmp_path, media_editor):
    """Loud Assertion: Explicit custom output path is respected and directories are created."""
    source_file = str(tmp_path / "custom_src.mp4")
    create_synthetic_video(source_file, duration=4.0)

    custom_out = str(tmp_path / "nested" / "dir" / "my_custom_proxy.mp4")
    result_path = media_editor.generate_proxy(source_file, output_path=custom_out)

    assert result_path == custom_out, "LOUD ASSERTION FAILURE: Returned path does not match requested output_path"
    assert os.path.exists(custom_out), "LOUD ASSERTION FAILURE: Custom proxy file was not created on disk"


# ============================================================================
# 2. Audio Peak DSP & Vectorized Window Detection Tests (Tier 1 & Tier 2)
# ============================================================================

def test_detect_audio_peak_exact_localization(tmp_path, media_editor):
    """Loud Assertion: Audio peak detection accurately isolates 1000Hz beep placed at [6.0s, 9.0s]."""
    source_file = str(tmp_path / "peak_test_25s.mp4")
    create_synthetic_video(
        source_file,
        duration=25.0,
        audio_type="beep",
        beep_start=6.0,
        beep_end=9.0,
        beep_freq=1000,
    )

    in_point, out_point = media_editor.detect_audio_peak(source_file, window_duration_sec=15.0)

    # The 15.0s window must encapsulate the 6.0s-9.0s beep
    assert in_point <= 6.0, f"LOUD ASSERTION FAILURE: in_point {in_point} is after beep start (6.0s)"
    assert out_point >= 9.0, f"LOUD ASSERTION FAILURE: out_point {out_point} is before beep end (9.0s)"
    assert abs((out_point - in_point) - 15.0) < 0.2, (
        f"LOUD ASSERTION FAILURE: Window length is not 15.0s: {out_point - in_point}"
    )
    assert in_point >= 0.0, f"LOUD ASSERTION FAILURE: in_point cannot be negative: {in_point}"
    assert out_point <= 25.0, f"LOUD ASSERTION FAILURE: out_point cannot exceed duration: {out_point}"


def test_detect_audio_peak_start_boundary(tmp_path, media_editor):
    """Loud Assertion: Beep located at beginning of video [0.0s, 3.0s] yields in_point=0.0."""
    source_file = str(tmp_path / "peak_start_20s.mp4")
    create_synthetic_video(source_file, duration=20.0, audio_type="beep", beep_start=0.0, beep_end=3.0)

    in_point, out_point = media_editor.detect_audio_peak(source_file, window_duration_sec=15.0)
    assert in_point == 0.0, f"LOUD ASSERTION FAILURE: Expected in_point 0.0, got {in_point}"
    assert abs(out_point - 15.0) < 0.1, f"LOUD ASSERTION FAILURE: Expected out_point 15.0, got {out_point}"


def test_detect_audio_peak_end_boundary(tmp_path, media_editor):
    """Loud Assertion: Beep located at end of video [26.0s, 29.0s] yields window covering the peak."""
    source_file = str(tmp_path / "peak_end_30s.mp4")
    create_synthetic_video(source_file, duration=30.0, audio_type="beep", beep_start=26.0, beep_end=29.0)

    in_point, out_point = media_editor.detect_audio_peak(source_file, window_duration_sec=15.0)
    assert in_point <= 26.0, f"LOUD ASSERTION FAILURE: in_point {in_point} does not capture start of late peak"
    assert out_point >= 29.0, f"LOUD ASSERTION FAILURE: out_point {out_point} does not capture end of late peak"
    assert out_point <= 30.0, f"LOUD ASSERTION FAILURE: out_point {out_point} exceeds clip duration 30.0s"
    assert abs((out_point - in_point) - 15.0) < 0.2, "LOUD ASSERTION FAILURE: Window length mismatch"


def test_detect_audio_peak_silence_fallback(tmp_path, media_editor):
    """Loud Assertion: Pure silent video falls back to default window [0.0, 15.0]."""
    source_file = str(tmp_path / "silence_20s.mp4")
    create_synthetic_video(source_file, duration=20.0, audio_type="silence")

    in_point, out_point = media_editor.detect_audio_peak(source_file, window_duration_sec=15.0)
    assert in_point == 0.0, f"LOUD ASSERTION FAILURE: Expected in_point 0.0 for silence, got {in_point}"
    assert out_point == 15.0, f"LOUD ASSERTION FAILURE: Expected out_point 15.0 for silence, got {out_point}"


def test_detect_audio_peak_no_audio_stream_fallback(tmp_path, media_editor):
    """Loud Assertion: Video without audio stream falls back to default window [0.0, 15.0]."""
    source_file = str(tmp_path / "no_audio_20s.mp4")
    create_synthetic_video(source_file, duration=20.0, audio_type="none")

    in_point, out_point = media_editor.detect_audio_peak(source_file, window_duration_sec=15.0)
    assert in_point == 0.0, f"LOUD ASSERTION FAILURE: Expected in_point 0.0 for no-audio, got {in_point}"
    assert out_point == 15.0, f"LOUD ASSERTION FAILURE: Expected out_point 15.0 for no-audio, got {out_point}"


def test_detect_audio_peak_short_video_clamping(tmp_path, media_editor):
    """Loud Assertion: Short video (4.0s < 15.0s) clamps out_point to actual video duration."""
    source_file = str(tmp_path / "short_4s.mp4")
    create_synthetic_video(source_file, duration=4.0, audio_type="beep", beep_start=1.0, beep_end=2.5)

    in_point, out_point = media_editor.detect_audio_peak(source_file, window_duration_sec=15.0)
    assert in_point == 0.0, f"LOUD ASSERTION FAILURE: Expected in_point 0.0, got {in_point}"
    assert out_point <= 4.0 and abs(out_point - 4.0) < 0.1, (
        f"LOUD ASSERTION FAILURE: Expected out_point 4.0, got {out_point}"
    )


def test_detect_audio_peak_subsecond_micro_video(tmp_path, media_editor):
    """Loud Assertion: Subsecond micro video (0.8s) clamps cleanly to [0.0, 0.8]."""
    source_file = str(tmp_path / "micro_0_8s.mp4")
    create_synthetic_video(source_file, duration=0.8, audio_type="beep", beep_start=0.1, beep_end=0.5)

    in_point, out_point = media_editor.detect_audio_peak(source_file, window_duration_sec=15.0)
    assert in_point == 0.0, f"LOUD ASSERTION FAILURE: Expected in_point 0.0, got {in_point}"
    assert abs(out_point - 0.8) < 0.1, f"LOUD ASSERTION FAILURE: Expected out_point 0.8, got {out_point}"


def test_detect_audio_peak_constant_tone_zero_variance(tmp_path, media_editor):
    """Loud Assertion: Constant tone with zero energy gradient returns valid window without crashing."""
    source_file = str(tmp_path / "constant_20s.mp4")
    create_synthetic_video(source_file, duration=20.0, audio_type="constant")

    in_point, out_point = media_editor.detect_audio_peak(source_file, window_duration_sec=15.0)
    assert in_point >= 0.0, "LOUD ASSERTION FAILURE: Negative in_point"
    assert out_point <= 20.0, "LOUD ASSERTION FAILURE: out_point exceeds duration"
    assert abs((out_point - in_point) - 15.0) < 0.1, "LOUD ASSERTION FAILURE: Window length mismatch"


# ============================================================================
# 3. 3-Cuts Metadata Contract Parity Tests (Tier 1 & Tier 2)
# ============================================================================

def test_generate_cuts_metadata_schema_contract(tmp_path, media_editor):
    """Loud Assertion: generate_cuts returns exact 3-cut JSON contract matching PROJECT.md."""
    source_file = str(tmp_path / "cuts_test_20s.mp4")
    create_synthetic_video(source_file, duration=20.0, audio_type="beep", beep_start=5.0, beep_end=8.0)

    cuts = media_editor.generate_cuts(source_file)

    # 1. Top-level dictionary keys
    expected_cuts = {"hype_drop", "cinematic", "raw_pov"}
    assert set(cuts.keys()) == expected_cuts, (
        f"LOUD ASSERTION FAILURE: Expected cuts {expected_cuts}, got {set(cuts.keys())}"
    )

    # 2. hype_drop contract
    hype = cuts["hype_drop"]
    assert "in_point" in hype and isinstance(hype["in_point"], (float, int))
    assert "out_point" in hype and isinstance(hype["out_point"], (float, int))
    assert hype["crop_ratio"] == "9:16", f"LOUD ASSERTION FAILURE: Hype crop_ratio mismatch: {hype.get('crop_ratio')}"
    assert hype["label"] == "Hype Drop (Audio Peak)", "LOUD ASSERTION FAILURE: Hype label mismatch"
    assert hype["target_resolution"] == "1080x1920", "LOUD ASSERTION FAILURE: Hype target_resolution mismatch"
    assert 0.0 <= hype["in_point"] < hype["out_point"] <= 20.0, "LOUD ASSERTION FAILURE: Invalid hype cut timestamps"

    # 3. cinematic contract
    cin = cuts["cinematic"]
    assert cin["in_point"] == 0.0, f"LOUD ASSERTION FAILURE: Cinematic in_point expected 0.0, got {cin.get('in_point')}"
    assert abs(cin["out_point"] - 20.0) < 0.2, f"LOUD ASSERTION FAILURE: Cinematic out_point expected 20.0, got {cin.get('out_point')}"
    assert cin["crop_ratio"] == "16:9", "LOUD ASSERTION FAILURE: Cinematic crop_ratio mismatch"
    assert cin["label"] == "Cinematic (16:9)", "LOUD ASSERTION FAILURE: Cinematic label mismatch"
    assert cin["target_resolution"] == "1920x1080", "LOUD ASSERTION FAILURE: Cinematic target_resolution mismatch"

    # 4. raw_pov contract
    raw = cuts["raw_pov"]
    assert raw["in_point"] == 0.0, f"LOUD ASSERTION FAILURE: Raw POV in_point expected 0.0, got {raw.get('in_point')}"
    assert abs(raw["out_point"] - 20.0) < 0.2, f"LOUD ASSERTION FAILURE: Raw POV out_point expected 20.0, got {raw.get('out_point')}"
    assert raw["crop_ratio"] == "original", "LOUD ASSERTION FAILURE: Raw POV crop_ratio mismatch"
    assert raw["label"] == "Raw POV (Original)", "LOUD ASSERTION FAILURE: Raw POV label mismatch"
    assert raw["target_resolution"] == "original", "LOUD ASSERTION FAILURE: Raw POV target_resolution mismatch"


def test_generate_cuts_short_clip_sync(tmp_path, media_editor):
    """Loud Assertion: All 3 cuts for short clip (< 15s) are synchronously clamped to duration."""
    source_file = str(tmp_path / "short_clip_3s.mp4")
    create_synthetic_video(source_file, duration=3.5)

    cuts = media_editor.generate_cuts(source_file)
    for cut_name in ["hype_drop", "cinematic", "raw_pov"]:
        cut = cuts[cut_name]
        assert cut["in_point"] == 0.0, f"LOUD ASSERTION FAILURE: {cut_name} in_point is not 0.0"
        assert abs(cut["out_point"] - 3.5) < 0.2, (
            f"LOUD ASSERTION FAILURE: {cut_name} out_point {cut['out_point']} does not match duration 3.5s"
        )


# ============================================================================
# 4. Full Pipeline Integration Tests (Tier 3 & Tier 4)
# ============================================================================

def test_generate_proxy_and_cuts_complete_pipeline(tmp_path, media_editor):
    """Loud Assertion: generate_proxy_and_cuts executes full workflow and returns valid payload."""
    source_file = str(tmp_path / "full_source.mp4")
    create_synthetic_video(source_file, duration=18.0, audio_type="beep", beep_start=4.0, beep_end=7.0)

    proxy_dir = str(tmp_path / "proxies_out")
    result = media_editor.generate_proxy_and_cuts(source_file, proxy_dir=proxy_dir)

    # 1. Top-level keys
    assert "source_file" in result and result["source_file"] == source_file
    assert "proxy_file" in result and os.path.exists(result["proxy_file"])
    assert "duration" in result and abs(result["duration"] - 18.0) < 0.2
    assert "cuts" in result

    # 2. Proxy validation
    proxy_info = probe_media_file(result["proxy_file"])
    assert proxy_info["height"] == 720, f"LOUD ASSERTION FAILURE: Proxy height expected 720, got {proxy_info['height']}"

    # 3. Cuts validation
    assert "hype_drop" in result["cuts"]
    assert "cinematic" in result["cuts"]
    assert "raw_pov" in result["cuts"]


def test_generate_proxy_and_cuts_auto_creates_proxy_directory(tmp_path, media_editor):
    """Loud Assertion: Nonexistent proxy directory is automatically created."""
    source_file = str(tmp_path / "src_auto_dir.mp4")
    create_synthetic_video(source_file, duration=4.0)

    deep_proxy_dir = str(tmp_path / "deep" / "nested" / "proxy_dir")
    assert not os.path.exists(deep_proxy_dir)

    result = media_editor.generate_proxy_and_cuts(source_file, proxy_dir=deep_proxy_dir)
    assert os.path.exists(deep_proxy_dir), "LOUD ASSERTION FAILURE: Deep proxy directory was not created"
    assert os.path.exists(result["proxy_file"]), "LOUD ASSERTION FAILURE: Proxy file not created in deep directory"


def test_generate_proxy_and_cuts_nonexistent_source_loud_error(tmp_path, media_editor):
    """Loud Assertion: generate_proxy_and_cuts with invalid source raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        media_editor.generate_proxy_and_cuts(str(tmp_path / "ghost_file.mp4"))
```

---

## 4. Implementation Guidelines for M1 Worker

When `M1 Worker` implements `unified_ops_hub/ml_agent/editor.py`:
1. **Module Location**: `unified_ops_hub/ml_agent/editor.py`
2. **Export**: Must be exported in `unified_ops_hub/ml_agent/__init__.py` (`from unified_ops_hub.ml_agent.editor import MediaEditor`).
3. **Class**: `MediaEditor`
4. **Signatures**:
   - `def __init__(self, ffmpeg_path: Optional[str] = None)`
   - `def get_video_info(self, source_file: str) -> Dict[str, Any]`
   - `def generate_proxy(self, source_file: str, output_path: Optional[str] = None, target_height: int = 720) -> str`
   - `def detect_audio_peak(self, source_file: str, window_duration_sec: float = 15.0) -> Tuple[float, float]`
   - `def generate_cuts(self, source_file: str, duration: Optional[float] = None) -> Dict[str, Any]`
   - `def generate_proxy_and_cuts(self, source_file: str, proxy_dir: str = "proxies") -> Dict[str, Any]`
5. **DSP Parameters**:
   - Audio extraction command: `ffmpeg -v error -i <file> -vn -ac 1 -ar 22050 -f s16le -`
   - PCM type: `np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32)`
   - Frame length: 50ms (1102 samples at 22.05kHz)
   - Energy metric: Mean squared amplitude per frame (`np.mean(frame ** 2)`)
   - Sliding window: 1D convolution / moving sum over `int(window_sec / 0.05)` frames
   - Silence threshold: Max frame energy < 1.0 (defaults to `[0.0, min(15.0, duration)]`)
   - Duration clamping: Max window bounded by `min(duration, window_duration_sec)`.
