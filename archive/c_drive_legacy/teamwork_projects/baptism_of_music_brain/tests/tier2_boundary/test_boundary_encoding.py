"""Tier 2 Boundary Tests: Encoding Engine Edge Cases and Media Irregularities."""

from __future__ import annotations

from pathlib import Path
import pytest

from tests.test_infra.media_generator import generate_odd_dimension_video, generate_silent_video
from tests.test_infra.ffprobe_validator import (
    assert_resolution_match,
    assert_visually_lossless,
    probe_media_file,
)


@pytest.mark.tier2
@pytest.mark.media
def test_boundary_odd_dimension_video_probing(odd_dimension_clip: Path):
    """Verify probe engine accurately measures odd/unpadded spatial dimensions (1921x1081)."""
    meta = probe_media_file(odd_dimension_clip)
    assert_resolution_match(meta, 1921, 1081)


@pytest.mark.tier2
@pytest.mark.media
def test_boundary_silent_video_probing(procedural_silent_clip: Path):
    """Verify video without audio stream is correctly parsed without throwing errors."""
    meta = probe_media_file(procedural_silent_clip)
    assert len(meta["video_streams"]) == 1
    assert len(meta["audio_streams"]) == 0
    assert meta["audio"] == {}


@pytest.mark.tier2
def test_boundary_corrupted_file_handling(corrupt_media_file: Path):
    """Verify probing a corrupted media file raises RuntimeError or ValueError."""
    with pytest.raises((RuntimeError, ValueError)):
        probe_media_file(corrupt_media_file)


@pytest.mark.tier2
def test_boundary_zero_byte_media_file(tmp_path: Path):
    """Verify 0-byte media file is detected and raises appropriate error."""
    zero_file = tmp_path / "zero_media.mp4"
    zero_file.touch()
    with pytest.raises((RuntimeError, ValueError)):
        probe_media_file(zero_file)


@pytest.mark.tier2
@pytest.mark.media
def test_boundary_high_entropy_noise_clip(procedural_noise_clip: Path):
    """Verify high-entropy noise footage encodes cleanly with video stream intact."""
    meta = probe_media_file(procedural_noise_clip)
    assert meta["video"]["width"] == 1280
    assert meta["video"]["height"] == 720
    assert meta["video"]["codec"] == "h264"


@pytest.mark.tier2
@pytest.mark.media
def test_boundary_fractional_frame_rate_23976(tmp_path: Path):
    """Verify 23.976 (24000/1001) cinema frame rate is handled with precision."""
    from tests.test_infra.media_generator import generate_procedural_video
    clip = tmp_path / "cinema_23976.mp4"
    generate_procedural_video(clip, duration_sec=1.0, fps=23.976)
    meta = probe_media_file(clip)
    assert abs(meta["video"]["fps"] - 23.976) <= 0.05


@pytest.mark.tier2
@pytest.mark.media
def test_boundary_fractional_frame_rate_5994(tmp_path: Path):
    """Verify 59.94 (60000/1001) broadcast frame rate is handled with precision."""
    from tests.test_infra.media_generator import generate_procedural_video
    clip = tmp_path / "broadcast_5994.mp4"
    generate_procedural_video(clip, duration_sec=1.0, fps=59.94)
    meta = probe_media_file(clip)
    assert abs(meta["video"]["fps"] - 59.94) <= 0.05


@pytest.mark.tier2
@pytest.mark.media
def test_boundary_high_frame_rate_120fps(tmp_path: Path):
    """Verify 120fps high frame rate clip generation and probing."""
    from tests.test_infra.media_generator import generate_procedural_video
    clip = tmp_path / "hfr_120fps.mp4"
    generate_procedural_video(clip, duration_sec=0.5, fps=120.0)
    meta = probe_media_file(clip)
    assert abs(meta["video"]["fps"] - 120.0) <= 0.1


@pytest.mark.tier2
@pytest.mark.media
def test_boundary_odd_vertical_dimension(tmp_path: Path):
    """Verify odd vertical resolution (e.g. 1081x1921)."""
    from tests.test_infra.media_generator import generate_procedural_video
    clip = tmp_path / "odd_vert.mp4"
    generate_procedural_video(clip, duration_sec=0.5, resolution=(1081, 1921), fps=30.0, pattern="color", pix_fmt="yuv444p")
    meta = probe_media_file(clip)
    assert_resolution_match(meta, 1081, 1921)


@pytest.mark.tier2
def test_boundary_nonexistent_media_path():
    """Verify probe on missing path raises FileNotFoundError."""
    with pytest.raises((FileNotFoundError, RuntimeError)):
        probe_media_file("path/does/not/exist/footage.mp4")
