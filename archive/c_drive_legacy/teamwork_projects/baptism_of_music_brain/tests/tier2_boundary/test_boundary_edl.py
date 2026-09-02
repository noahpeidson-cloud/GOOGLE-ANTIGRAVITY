"""Tier 2 Boundary Tests: EDL and Cut Decision Edge Cases."""

from __future__ import annotations

import pytest

try:
    from pydantic import ValidationError
    from src.models.schemas import (
        AudioMasteringSettings,
        ClipSegment,
        ColorGradeSettings,
        EditDecisionList,
    )
except ImportError:
    ValidationError = Exception
    AudioMasteringSettings = None
    ClipSegment = None
    ColorGradeSettings = None
    EditDecisionList = None


def _check_schemas():
    if EditDecisionList is None:
        pytest.skip("src.models.schemas not yet implemented")


@pytest.mark.tier2
def test_boundary_zero_duration_trim_rejected():
    """Verify segment where source_in == source_out is rejected or flagged."""
    _check_schemas()
    with pytest.raises(ValidationError):
        ClipSegment(
            clip_id="zero_len",
            source_in_sec=2.0,
            source_out_sec=2.0,
            timeline_in_sec=0.0,
        )


@pytest.mark.tier2
def test_boundary_inverted_trim_rejected():
    """Verify segment where source_out < source_in is rejected."""
    _check_schemas()
    with pytest.raises(ValidationError):
        ClipSegment(
            clip_id="inverted",
            source_in_sec=5.0,
            source_out_sec=2.0,
            timeline_in_sec=0.0,
        )


@pytest.mark.tier2
def test_boundary_sub_frame_micro_duration_segment():
    """Verify sub-frame precision (e.g. 1 frame @ 60fps = 0.0166s) is supported."""
    _check_schemas()
    seg = ClipSegment(
        clip_id="micro_flash",
        source_in_sec=1.0,
        source_out_sec=1.016667,
        timeline_in_sec=0.0,
    )
    assert seg.source_out_sec > seg.source_in_sec


@pytest.mark.tier2
def test_boundary_hundred_segment_complex_edl():
    """Verify EDL can assemble and validate 100+ rapid EDM micro-cuts."""
    _check_schemas()
    segments = [
        ClipSegment(
            clip_id=f"cut_{i:03d}",
            source_in_sec=i * 0.1,
            source_out_sec=(i * 0.1) + 0.08,
            timeline_in_sec=i * 0.08,
            speed_multiplier=1.0,
        )
        for i in range(100)
    ]
    edl = EditDecisionList(
        job_id="job_edm_100_cuts",
        source_video_path="ingest/edm_drop.mp4",
        target_resolution=(1920, 1080),
        target_fps=60.0,
        encoding_profile="x264_crf17",
        segments=segments,
        color_grade=ColorGradeSettings(),
        audio_mastering=AudioMasteringSettings(),
    )
    assert len(edl.segments) == 100
    assert edl.segments[-1].clip_id == "cut_099"


@pytest.mark.tier2
def test_boundary_color_grade_extreme_limits():
    """Verify color grade parameters accept valid boundary minimums and maximums."""
    _check_schemas()
    min_grade = ColorGradeSettings(contrast=0.0, brightness=-1.0, saturation=0.0, gamma=0.1)
    assert min_grade.contrast == 0.0
    assert min_grade.brightness == -1.0
    assert min_grade.saturation == 0.0
    assert min_grade.gamma == 0.1

    max_grade = ColorGradeSettings(contrast=3.0, brightness=1.0, saturation=3.0, gamma=10.0)
    assert max_grade.contrast == 3.0
    assert max_grade.brightness == 1.0
    assert max_grade.saturation == 3.0
    assert max_grade.gamma == 10.0


@pytest.mark.tier2
def test_boundary_audio_mastering_extreme_gain():
    """Verify audio mastering handles boundary gain adjustments and rejects out-of-bounds gain."""
    _check_schemas()
    # Boundary valid gain (-30.0 dB to 30.0 dB)
    mute_audio = AudioMasteringSettings(normalize_lufs=False, gain_db=-30.0)
    assert mute_audio.gain_db == -30.0

    boost_audio = AudioMasteringSettings(normalize_lufs=True, target_lufs=-70.0, peak_limit_db=0.0)
    assert boost_audio.target_lufs == -70.0

    # Beyond -30.0 dB or 30.0 dB boundary
    with pytest.raises(ValidationError):
        AudioMasteringSettings(gain_db=-35.0)

    with pytest.raises(ValidationError):
        AudioMasteringSettings(gain_db=35.0)


@pytest.mark.tier2
def test_boundary_speed_multiplier_limits():
    """Verify speed multiplier boundaries (slow-mo and hyperlapse limits)."""
    _check_schemas()
    slow_mo = ClipSegment(
        clip_id="slow",
        source_in_sec=0.0,
        source_out_sec=1.0,
        timeline_in_sec=0.0,
        speed_multiplier=0.1,
    )
    assert slow_mo.speed_multiplier == 0.1

    hyper = ClipSegment(
        clip_id="hyper",
        source_in_sec=0.0,
        source_out_sec=10.0,
        timeline_in_sec=0.0,
        speed_multiplier=10.0,
    )
    assert hyper.speed_multiplier == 10.0

    # Beyond 10.0 max speed multiplier
    with pytest.raises(ValidationError):
        ClipSegment(
            clip_id="too_fast",
            source_in_sec=0.0,
            source_out_sec=10.0,
            timeline_in_sec=0.0,
            speed_multiplier=15.0,
        )


@pytest.mark.tier2
def test_boundary_odd_dimensions_yuv420p_rejected():
    """Verify odd resolution dimensions (e.g. 1921x1081) are rejected for YUV420p video."""
    _check_schemas()
    with pytest.raises(ValidationError):
        EditDecisionList(
            job_id="odd_res_job",
            source_video_path="ingest/source.mp4",
            target_resolution=(1921, 1081),
            target_fps=30.0,
            encoding_profile="x264_crf17",
            segments=[],
            color_grade=ColorGradeSettings(),
            audio_mastering=AudioMasteringSettings(),
        )


@pytest.mark.tier2
def test_boundary_target_fps_validation():
    """Verify target_fps must be positive number."""
    _check_schemas()
    with pytest.raises(ValidationError):
        EditDecisionList(
            job_id="invalid_fps",
            source_video_path="ingest/source.mp4",
            target_resolution=(1920, 1080),
            target_fps=-30.0,
            segments=[
                ClipSegment(clip_id="s1", source_in_sec=0.0, source_out_sec=1.0, timeline_in_sec=0.0)
            ],
            color_grade=ColorGradeSettings(),
            audio_mastering=AudioMasteringSettings(),
        )


@pytest.mark.tier2
def test_boundary_target_resolution_validation():
    """Verify target_resolution tuple must contain positive integers."""
    _check_schemas()
    with pytest.raises(ValidationError):
        EditDecisionList(
            job_id="invalid_res",
            source_video_path="ingest/source.mp4",
            target_resolution=(-1920, 1080),
            target_fps=30.0,
            segments=[
                ClipSegment(clip_id="s1", source_in_sec=0.0, source_out_sec=1.0, timeline_in_sec=0.0)
            ],
            color_grade=ColorGradeSettings(),
            audio_mastering=AudioMasteringSettings(),
        )
