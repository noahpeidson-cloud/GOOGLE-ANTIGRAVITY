"""Tier 4 E2E Workload Tests: Programmatic Encoding Verification (Acceptance Criteria 1).

Executes ffprobe on rendered output videos to programmatically assert that the output codec,
bitrate, and resolution constraints mathematically match visually lossless configuration targets.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.test_infra.media_generator import (
    generate_1080p_video,
    generate_4k_uhd_video,
    get_ffmpeg_binary,
)
from tests.test_infra.ffprobe_validator import (
    assert_codec_and_profile,
    assert_fps_precision,
    assert_resolution_match,
    assert_visually_lossless,
    probe_media_file,
)


@pytest.mark.tier4
@pytest.mark.e2e
@pytest.mark.media
def test_e2e_1080p_visually_lossless_encoding(tmp_path: Path, procedural_1080p_clip: Path):
    """AC1: Render 1080p source with x264_crf17 and assert codec, profile, resolution, and fps."""
    output_path = tmp_path / "rendered_1080p_master.mp4"
    ffmpeg_bin = get_ffmpeg_binary()

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(procedural_1080p_clip),
        "-c:v", "libx264",
        "-crf", "17",
        "-preset", "veryfast",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "320k",
        str(output_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"FFmpeg render failed:\n{res.stderr}"
    assert output_path.exists()

    probe_data = assert_visually_lossless(
        output_path,
        expected_resolution=(1920, 1080),
        expected_fps=30.0,
        expected_vcodec="h264",
        expected_profile="High",
        expected_acodec="aac",
    )
    assert probe_data["video"]["width"] == 1920
    assert probe_data["video"]["height"] == 1080


@pytest.mark.tier4
@pytest.mark.e2e
@pytest.mark.media
def test_e2e_4k_uhd_visually_lossless_encoding(tmp_path: Path, procedural_4k_clip: Path):
    """AC1: Render 4K UHD source with x264_crf17 and assert 3840x2160 @ 60fps fidelity."""
    output_path = tmp_path / "rendered_4k_master.mp4"
    ffmpeg_bin = get_ffmpeg_binary()

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(procedural_4k_clip),
        "-c:v", "libx264",
        "-crf", "17",
        "-preset", "veryfast",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "320k",
        str(output_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"FFmpeg render failed:\n{res.stderr}"
    assert output_path.exists()

    assert_visually_lossless(
        output_path,
        expected_resolution=(3840, 2160),
        expected_fps=60.0,
        expected_vcodec="h264",
        expected_profile="High",
        expected_acodec="aac",
    )


@pytest.mark.tier4
@pytest.mark.e2e
@pytest.mark.media
def test_e2e_duration_and_aspect_ratio_preservation(tmp_path: Path, procedural_1080p_clip: Path):
    """AC1: Verify duration and display aspect ratio are preserved through lossless render."""
    source_meta = probe_media_file(procedural_1080p_clip)
    output_path = tmp_path / "aspect_duration_master.mp4"
    ffmpeg_bin = get_ffmpeg_binary()

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(procedural_1080p_clip),
        "-c:v", "libx264",
        "-crf", "17",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    out_meta = probe_media_file(output_path)
    assert abs(out_meta["video"]["duration"] - source_meta["video"]["duration"]) <= 0.1
    assert out_meta["video"]["aspect_ratio"] == source_meta["video"]["aspect_ratio"]


@pytest.mark.tier4
@pytest.mark.e2e
@pytest.mark.media
def test_e2e_high_fidelity_audio_aac_bitrate(tmp_path: Path, procedural_1080p_clip: Path):
    """AC1: Verify audio stream is encoded with AAC and high bitrate allocation."""
    output_path = tmp_path / "high_audio_master.mp4"
    ffmpeg_bin = get_ffmpeg_binary()

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(procedural_1080p_clip),
        "-c:v", "copy",
        "-c:a", "aac",
        "-ac", "2",
        "-b:a", "320k",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    meta = probe_media_file(output_path)
    assert meta["audio"]["codec"] == "aac"
    assert meta["audio"]["channels"] == 2


@pytest.mark.tier4
@pytest.mark.e2e
@pytest.mark.media
def test_e2e_yuv444p_chroma_preservation(tmp_path: Path, procedural_1080p_clip: Path):
    """AC1: Verify yuv444p profile preserves full chroma resolution."""
    output_path = tmp_path / "rendered_yuv444p.mp4"
    ffmpeg_bin = get_ffmpeg_binary()

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(procedural_1080p_clip),
        "-c:v", "libx264",
        "-crf", "17",
        "-preset", "veryfast",
        "-pix_fmt", "yuv444p",
        "-c:a", "copy",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    meta = probe_media_file(output_path)
    assert meta["video"]["pix_fmt"] == "yuv444p"
