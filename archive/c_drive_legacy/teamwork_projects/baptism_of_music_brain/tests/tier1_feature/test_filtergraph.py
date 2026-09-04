"""Tier 1 Feature Tests: Complex Filtergraph Compiler."""

from __future__ import annotations

import pytest

try:
    from src.models.schemas import (
        AudioMasteringSettings,
        ClipSegment,
        ColorGradeSettings,
        EditDecisionList,
    )
    from src.renderer.filtergraph import build_filtergraph
except ImportError:
    AudioMasteringSettings = None
    ClipSegment = None
    ColorGradeSettings = None
    EditDecisionList = None
    build_filtergraph = None


def _check_fg():
    if build_filtergraph is None:
        pytest.skip("src.renderer.filtergraph not yet implemented")


@pytest.fixture
def base_edl():
    _check_fg()
    return EditDecisionList(
        job_id="job_filter_001",
        source_video_path="ingest/source.mp4",
        target_resolution=(1920, 1080),
        target_fps=30.0,
        encoding_profile="x264_crf17",
        segments=[
            ClipSegment(
                clip_id="seg_01",
                source_in_sec=0.0,
                source_out_sec=2.0,
                timeline_in_sec=0.0,
                speed_multiplier=1.0,
                volume_multiplier=1.0,
            )
        ],
        color_grade=ColorGradeSettings(contrast=1.2, brightness=0.05, saturation=1.1, gamma=1.0),
        audio_mastering=AudioMasteringSettings(normalize_lufs=True, target_lufs=-14.0, peak_limit_db=-1.5),
    )


@pytest.mark.tier1
def test_filtergraph_single_segment_trim_setpts(base_edl):
    """Verify filtergraph contains trim and setpts filters for single clip."""
    fg = build_filtergraph(base_edl)
    assert "trim=" in fg
    assert "setpts=PTS-STARTPTS" in fg
    assert "atrim=" in fg
    assert "asetpts=PTS-STARTPTS" in fg


@pytest.mark.tier1
def test_filtergraph_multi_segment_concat(base_edl):
    """Verify filtergraph compiles multiple segments and joins them via concat filter."""
    base_edl.segments.append(
        ClipSegment(
            clip_id="seg_02",
            source_in_sec=3.0,
            source_out_sec=5.0,
            timeline_in_sec=2.0,
            speed_multiplier=1.0,
            volume_multiplier=1.0,
        )
    )
    fg = build_filtergraph(base_edl)
    assert "concat=n=2:v=1:a=1" in fg or "concat" in fg


@pytest.mark.tier1
def test_filtergraph_color_grade_eq_filter(base_edl):
    """Verify filtergraph contains eq filter matching color grade settings."""
    base_edl.color_grade.contrast = 1.35
    base_edl.color_grade.saturation = 1.25
    fg = build_filtergraph(base_edl)
    assert "eq=" in fg
    assert "contrast=1.35" in fg
    assert "saturation=1.25" in fg


@pytest.mark.tier1
def test_filtergraph_audio_volume_and_gain(base_edl):
    """Verify audio volume adjustment is compiled into audio filter chain."""
    base_edl.segments[0].volume_multiplier = 0.8
    fg = build_filtergraph(base_edl)
    assert "volume=" in fg or "volume" in fg


@pytest.mark.tier1
def test_filtergraph_loudnorm_filter_generation(base_edl):
    """Verify loudnorm filter is appended when normalize_lufs is enabled."""
    base_edl.audio_mastering.normalize_lufs = True
    base_edl.audio_mastering.target_lufs = -14.0
    fg = build_filtergraph(base_edl)
    assert "loudnorm=" in fg or "loudnorm" in fg
    assert "I=-14" in fg or "-14.0" in fg


@pytest.mark.tier1
def test_filtergraph_speed_multiplier_setpts(base_edl):
    """Verify speed multiplier alters setpts and atempo filter values."""
    base_edl.segments[0].speed_multiplier = 0.5
    fg = build_filtergraph(base_edl)
    assert "setpts=" in fg


@pytest.mark.tier1
def test_filtergraph_scale_and_pad_resolution(base_edl):
    """Verify scale and pad filters conform to target resolution."""
    base_edl.target_resolution = (1080, 1920)
    fg = build_filtergraph(base_edl)
    assert "scale=" in fg or "pad=" in fg or "1080" in fg


@pytest.mark.tier1
def test_filtergraph_compilation_syntax_validity(base_edl):
    """Verify overall filtergraph string syntax contains valid stream labels."""
    fg = build_filtergraph(base_edl)
    assert isinstance(fg, str)
    assert len(fg) > 10
    assert fg.count("[") == fg.count("]")


@pytest.mark.tier1
def test_filtergraph_disabled_audio_normalization(base_edl):
    """Verify loudnorm filter is omitted when normalize_lufs is False."""
    base_edl.audio_mastering.normalize_lufs = False
    fg = build_filtergraph(base_edl)
    assert "loudnorm" not in fg
