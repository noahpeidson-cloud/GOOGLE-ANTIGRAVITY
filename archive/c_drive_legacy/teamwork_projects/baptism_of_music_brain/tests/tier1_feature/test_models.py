"""Tier 1 Feature Tests: Pydantic v2 schemas and FSM state machine validation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from src.models.schemas import (
    AudioMasteringSettings,
    AudioStreamMetadata,
    ClipSegment,
    ColorGradeSettings,
    EditDecisionList,
    EDLOverridePayload,
    JobMetadata,
    JobStatus,
    MediaProbeResult,
    VideoJob,
    VideoStreamMetadata,
)
from src.models.state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidStateTransitionError,
    can_transition,
    transition_job,
    validate_transition,
)


@pytest.mark.tier1
class TestClipSegment:
    """Unit tests for ClipSegment model."""

    def test_valid_clip_segment(self) -> None:
        seg = ClipSegment(
            source_in_sec=1.5,
            source_out_sec=5.5,
            timeline_in_sec=0.0,
            speed_multiplier=2.0,
            volume_multiplier=0.8,
            label="intro_hook",
        )
        assert seg.source_duration == pytest.approx(4.0)
        assert seg.timeline_duration == pytest.approx(2.0)
        assert seg.timeline_out_sec == pytest.approx(2.0)
        assert seg.label == "intro_hook"

    def test_invalid_bounds_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            # source_out_sec <= source_in_sec
            ClipSegment(source_in_sec=5.0, source_out_sec=5.0)

        with pytest.raises(ValidationError):
            # source_out_sec < source_in_sec
            ClipSegment(source_in_sec=10.0, source_out_sec=5.0)

        with pytest.raises(ValidationError):
            # negative source_in_sec
            ClipSegment(source_in_sec=-1.0, source_out_sec=5.0)

    def test_speed_and_volume_multiplier_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, speed_multiplier=0.0)

        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, speed_multiplier=15.0)

        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, volume_multiplier=-0.1)

        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, volume_multiplier=10.0)


@pytest.mark.tier1
class TestColorGradeSettings:
    """Unit tests for ColorGradeSettings model."""

    def test_default_values(self) -> None:
        cg = ColorGradeSettings()
        assert cg.contrast == 1.0
        assert cg.brightness == 0.0
        assert cg.saturation == 1.0
        assert cg.gamma == 1.0
        assert cg.gamma_r is None
        assert cg.to_ffmpeg_eq_filter() == "eq=contrast=1.000:brightness=0.000:saturation=1.000:gamma=1.000"

    def test_custom_values_and_channel_gamma(self) -> None:
        cg = ColorGradeSettings(
            contrast=1.2,
            brightness=0.05,
            saturation=1.5,
            gamma=1.1,
            gamma_r=1.05,
            gamma_g=1.0,
            gamma_b=0.95,
        )
        eq_str = cg.to_ffmpeg_eq_filter()
        assert "contrast=1.200" in eq_str
        assert "gamma_r=1.050" in eq_str
        assert "gamma_b=0.950" in eq_str

    def test_bounds_validation(self) -> None:
        with pytest.raises(ValidationError):
            ColorGradeSettings(contrast=4.0)

        with pytest.raises(ValidationError):
            ColorGradeSettings(brightness=-1.5)

        with pytest.raises(ValidationError):
            ColorGradeSettings(gamma=0.05)


@pytest.mark.tier1
class TestAudioMasteringSettings:
    """Unit tests for AudioMasteringSettings model."""

    def test_default_values(self) -> None:
        ams = AudioMasteringSettings()
        assert ams.normalize_lufs is True
        assert ams.target_lufs == -14.0
        assert ams.peak_limit_db == -1.5
        assert ams.gain_db == 0.0
        assert ams.to_ffmpeg_audio_filter() == "loudnorm=I=-14.0:TP=-1.5:LRA=11"

    def test_gain_and_disabled_normalization(self) -> None:
        ams = AudioMasteringSettings(normalize_lufs=False, gain_db=3.5)
        assert ams.to_ffmpeg_audio_filter() == "volume=3.5dB"

        ams_passthrough = AudioMasteringSettings(normalize_lufs=False, gain_db=0.0)
        assert ams_passthrough.to_ffmpeg_audio_filter() == "anull"

    def test_bounds_validation(self) -> None:
        with pytest.raises(ValidationError):
            AudioMasteringSettings(target_lufs=-80.0)

        with pytest.raises(ValidationError):
            AudioMasteringSettings(peak_limit_db=1.0)

        with pytest.raises(ValidationError):
            AudioMasteringSettings(gain_db=50.0)


@pytest.mark.tier1
class TestEditDecisionList:
    """Unit tests for EditDecisionList model."""

    def test_edl_creation_and_timeline_duration(self) -> None:
        seg1 = ClipSegment(clip_id="seg1", source_in_sec=0.0, source_out_sec=2.0, timeline_in_sec=0.0)
        seg2 = ClipSegment(clip_id="seg2", source_in_sec=5.0, source_out_sec=9.0, timeline_in_sec=2.0, speed_multiplier=2.0)

        edl = EditDecisionList(
            job_id="job_123",
            source_video_path="ingest/clip.mp4",
            target_resolution=(1920, 1080),
            target_fps=60.0,
            segments=[seg1, seg2],
        )

        assert edl.segment_count == 2
        # seg1: 2.0s, seg2: (9-5)/2 = 2.0s -> total = 4.0s
        assert edl.total_timeline_duration == pytest.approx(4.0)

    def test_resolution_even_dimension_validation(self) -> None:
        # Valid even dimensions
        edl = EditDecisionList(
            job_id="job_even",
            source_video_path="ingest/clip.mp4",
            target_resolution=(1080, 1920),
        )
        assert edl.target_resolution == (1080, 1920)

        # Invalid odd dimension (width odd)
        with pytest.raises(ValidationError) as excinfo:
            EditDecisionList(
                job_id="job_odd",
                source_video_path="ingest/clip.mp4",
                target_resolution=(1921, 1080),
            )
        assert "even" in str(excinfo.value)

        # Invalid negative dimension
        with pytest.raises(ValidationError):
            EditDecisionList(
                job_id="job_neg",
                source_video_path="ingest/clip.mp4",
                target_resolution=(-1920, 1080),
            )

    def test_json_serialization_roundtrip(self) -> None:
        edl = EditDecisionList(
            job_id="job_json",
            source_video_path="ingest/clip.mp4",
            target_resolution=(3840, 2160),
            segments=[
                ClipSegment(source_in_sec=0.0, source_out_sec=3.0, label="drop"),
            ],
            color_grade=ColorGradeSettings(contrast=1.1, saturation=1.2),
            audio_mastering=AudioMasteringSettings(target_lufs=-12.0),
        )
        json_data = edl.model_dump_json()
        edl_reconstructed = EditDecisionList.model_validate_json(json_data)
        assert edl_reconstructed.job_id == edl.job_id
        assert edl_reconstructed.target_resolution == (3840, 2160)
        assert edl_reconstructed.segment_count == 1
        assert edl_reconstructed.color_grade.contrast == 1.1


@pytest.mark.tier1
class TestMediaProbeResult:
    """Unit tests for probe result models."""

    def test_probe_result_properties(self) -> None:
        v_stream = VideoStreamMetadata(
            index=0,
            codec_name="h264",
            profile="High",
            width=1920,
            height=1080,
            fps=29.97,
            pixel_format="yuv420p",
            bitrate=25000000,
        )
        a_stream = AudioStreamMetadata(
            index=1,
            codec_name="aac",
            sample_rate=48000,
            channels=2,
            bitrate=320000,
        )
        probe = MediaProbeResult(
            filepath="ingest/sample.mp4",
            format_name="mov,mp4,m4a,3gp,3g2,mj2",
            duration_sec=10.5,
            size_bytes=32000000,
            video_streams=[v_stream],
            audio_streams=[a_stream],
        )

        assert probe.has_video is True
        assert probe.has_audio is True
        assert probe.width == 1920
        assert probe.height == 1080
        assert probe.fps == 29.97
        assert probe.primary_video.codec_name == "h264"
        assert probe.primary_audio.sample_rate == 48000


@pytest.mark.tier1
class TestJobStateMachine:
    """Unit tests for FSM transitions and validation."""

    def test_allowed_lifecycle_transitions(self) -> None:
        job = VideoJob(source_filepath="ingest/video.mp4", status=JobStatus.DETECTED)
        assert job.filename == "video.mp4"

        # DETECTED -> INGESTING -> INGESTED -> PROBING -> PROBED -> ML_GRADING -> AWAITING_OVERRIDE -> APPROVED -> RENDERING -> DELIVERING -> DELIVERED
        transitions = [
            JobStatus.INGESTING,
            JobStatus.INGESTED,
            JobStatus.PROBING,
            JobStatus.PROBED,
            JobStatus.ML_GRADING,
            JobStatus.AWAITING_OVERRIDE,
            JobStatus.APPROVED,
            JobStatus.RENDERING,
            JobStatus.DELIVERING,
            JobStatus.DELIVERED,
        ]
        for next_status in transitions:
            assert can_transition(job.status, next_status) is True
            job = transition_job(job, next_status)
            assert job.status == next_status

    def test_override_workflow_transitions(self) -> None:
        job = VideoJob(source_filepath="ingest/video.mp4", status=JobStatus.AWAITING_OVERRIDE)
        # AWAITING_OVERRIDE -> OVERRIDE_APPLIED -> APPROVED
        assert can_transition(job.status, JobStatus.OVERRIDE_APPLIED) is True
        job = transition_job(job, JobStatus.OVERRIDE_APPLIED)
        assert job.status == JobStatus.OVERRIDE_APPLIED

        assert can_transition(job.status, JobStatus.APPROVED) is True
        job = transition_job(job, JobStatus.APPROVED)
        assert job.status == JobStatus.APPROVED

    def test_invalid_transitions_raise_error(self) -> None:
        job = VideoJob(source_filepath="ingest/video.mp4", status=JobStatus.DELIVERED)

        # Terminal DELIVERED cannot transition anywhere
        with pytest.raises(InvalidStateTransitionError):
            validate_transition(JobStatus.DELIVERED, JobStatus.ML_GRADING)

        with pytest.raises(InvalidStateTransitionError):
            validate_transition(JobStatus.PENDING, JobStatus.DELIVERED)

        with pytest.raises(InvalidStateTransitionError):
            validate_transition(JobStatus.PROBING, JobStatus.RENDERING)

    def test_failure_and_cancellation_transitions(self) -> None:
        # Non-terminal states can transition to FAILED and CANCELLED
        for status in (JobStatus.DETECTED, JobStatus.INGESTED, JobStatus.PROBING, JobStatus.RENDERING):
            assert can_transition(status, JobStatus.FAILED) is True
            assert can_transition(status, JobStatus.CANCELLED) is True
