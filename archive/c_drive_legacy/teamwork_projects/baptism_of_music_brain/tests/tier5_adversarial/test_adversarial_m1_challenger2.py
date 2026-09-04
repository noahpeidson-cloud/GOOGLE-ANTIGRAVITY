"""Tier 5 Adversarial Stress Tests: Challenger 2 Milestone 1 Audit.

Adversarially stress-tests:
1. src/renderer/probe.py:
   - Corrupt video files, random bytes, truncated headers
   - Missing streams (audio-only, video-only, zero streams)
   - Non-media files (text, json, binary garbage, empty, non-existent, directories)
   - Fractional frame rates, boundary frame rates, and corrupted rate strings
   - Missing or None-valued keys in ffprobe metadata dictionaries
2. src/models/schemas.py:
   - Extreme EDL values (negative timestamps, inverted in/out, zero duration)
   - Out-of-bound color grading values (contrast, brightness, saturation, gammas)
   - Out-of-bound audio mastering values (LUFS, peak limit, gain dB)
   - Extreme speed and volume multipliers
   - Non-even or non-positive target resolutions
   - Out-of-bound target FPS and progress percentage
3. src/models/state_machine.py:
   - Exhaustive 361-combination FSM transition matrix verification
   - Illegal jumps across lifecycle stages
   - Terminal state immutability (DELIVERED and COMPLETED cannot transition)
   - Error message and timestamp mutation safety
"""

from __future__ import annotations

import itertools
import json
import os
from pathlib import Path
import subprocess
import time
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
from src.renderer.probe import (
    CorruptMediaError,
    FFprobeError,
    FFprobeExecutionError,
    FFprobeNotFoundError,
    MediaFileNotFoundError,
    _parse_ffprobe_json,
    async_probe_media,
    parse_fractional_rate,
    probe_media,
)
from tests.test_infra.media_generator import (
    generate_procedural_video,
    generate_silent_video,
)


# ============================================================================
# 1. ADVERSARIAL PROBE TESTS (src/renderer/probe.py)
# ============================================================================

@pytest.mark.tier5
class TestAdversarialProbeCorruptAndNonMedia:
    """Stress-test probe.py against corrupted inputs, malformed containers, and non-media files."""

    def test_probe_random_binary_garbage_file(self, tmp_path: Path) -> None:
        """Probe must reject files containing random pseudo-random binary data."""
        bad_file = tmp_path / "corrupt_garbage.mp4"
        bad_file.write_bytes(os.urandom(65536))

        with pytest.raises(CorruptMediaError) as excinfo:
            probe_media(bad_file)
        assert bad_file.name in str(excinfo.value) or "FFprobe failed" in str(excinfo.value)

    def test_probe_truncated_mp4_header(self, tmp_path: Path) -> None:
        """Probe must reject files with valid initial ftyp magic but truncated payload."""
        truncated_file = tmp_path / "truncated_header.mp4"
        # Standard MP4 ftyp box header (32 bytes) cut short
        ftyp_header = b"\x00\x00\x00\x1c\x66\x74\x79\x70\x69\x73\x6f\x6d\x00\x00\x02\x00\x69\x73\x6f\x6d\x69\x73\x6f\x32\x61\x76\x63\x31\x6d\x70\x34\x31"
        truncated_file.write_bytes(ftyp_header)

        with pytest.raises(CorruptMediaError):
            probe_media(truncated_file)

    def test_probe_plain_text_disguised_as_mp4(self, tmp_path: Path) -> None:
        """Probe must reject ASCII text files even if renamed to .mp4."""
        txt_file = tmp_path / "fake_video.mp4"
        txt_file.write_text("THIS IS NOT A VALID VIDEO CONTAINER FORMAT AT ALL\n" * 50, encoding="utf-8")

        with pytest.raises(CorruptMediaError):
            probe_media(txt_file)

    def test_probe_json_file_disguised_as_mov(self, tmp_path: Path) -> None:
        """Probe must reject JSON documents disguised as media files."""
        json_file = tmp_path / "manifest.mov"
        json_file.write_text(json.dumps({"streams": [], "format": {"filename": "test"}}), encoding="utf-8")

        with pytest.raises(CorruptMediaError):
            probe_media(json_file)

    def test_probe_directory_path_raises_error(self, tmp_path: Path) -> None:
        """Probe must raise error if passed a directory instead of a media file."""
        sub_dir = tmp_path / "fake_media_folder.mp4"
        sub_dir.mkdir()

        with pytest.raises((FFprobeError, CorruptMediaError, FFprobeExecutionError)):
            probe_media(sub_dir)

    def test_probe_zero_byte_empty_file(self, tmp_path: Path) -> None:
        """Probe must explicitly raise CorruptMediaError on 0-byte files."""
        empty_file = tmp_path / "empty_stream.mp4"
        empty_file.touch()

        with pytest.raises(CorruptMediaError) as excinfo:
            probe_media(empty_file)
        assert "0 bytes" in str(excinfo.value)

    def test_probe_nonexistent_file(self, tmp_path: Path) -> None:
        """Probe must raise MediaFileNotFoundError when file does not exist."""
        ghost = tmp_path / "nonexistent_subfolder" / "ghost.mp4"
        with pytest.raises(MediaFileNotFoundError):
            probe_media(ghost)

    def test_probe_video_only_silent_media(self, tmp_path: Path) -> None:
        """Probe must correctly parse video-only silent files (has_audio=False, primary_audio=None)."""
        silent_path = tmp_path / "silent_test.mp4"
        generate_silent_video(silent_path, duration_sec=1.0)

        result = probe_media(silent_path)
        assert result.has_video is True
        assert result.has_audio is False
        assert result.primary_video is not None
        assert result.primary_audio is None
        assert result.width == 1920
        assert result.height == 1080
        assert result.fps == pytest.approx(30.0, abs=0.05)

    def test_parse_fractional_rate_standard_and_corrupt_strings(self) -> None:
        """Test parse_fractional_rate with valid, invalid, and boundary rate strings."""
        assert parse_fractional_rate("30/1") == 30.0
        assert parse_fractional_rate("60/1") == 60.0
        assert parse_fractional_rate("0/0", default=30.0) == 30.0
        assert parse_fractional_rate("100/0", default=30.0) == 30.0
        assert parse_fractional_rate("0", default=25.0) == 25.0
        assert parse_fractional_rate("N/A", default=24.0) == 24.0
        assert parse_fractional_rate(None, default=60.0) == 60.0
        assert parse_fractional_rate("", default=30.0) == 30.0
        assert parse_fractional_rate("   ", default=30.0) == 30.0
        assert parse_fractional_rate("invalid/fraction/string", default=30.0) == 30.0
        assert parse_fractional_rate("NaN", default=30.0) == 30.0
        assert parse_fractional_rate("-60.0", default=30.0) == 30.0
        assert parse_fractional_rate("59.94", default=30.0) == 59.94
        assert parse_fractional_rate("24000/1001") == pytest.approx(23.976, abs=0.001)

    def test_parse_ffprobe_json_with_zero_streams(self, tmp_path: Path) -> None:
        """Container with 0 streams (raw container or metadata-only) must produce valid MediaProbeResult."""
        dummy_file = tmp_path / "empty_container.mp4"
        dummy_file.write_bytes(b"dummy")

        raw_data = {
            "streams": [],
            "format": {
                "format_name": "mp4",
                "duration": "5.0",
                "size": "5000",
                "bit_rate": "8000",
            },
        }
        result = _parse_ffprobe_json(raw_data, dummy_file)
        assert result.has_video is False
        assert result.has_audio is False
        assert result.duration_sec == 5.0
        assert result.size_bytes == 5000
        assert result.bitrate == 8000
        assert result.primary_video is None
        assert result.primary_audio is None
        assert result.width == 0
        assert result.height == 0
        assert result.fps == 0.0


# ============================================================================
# 2. ADVERSARIAL SCHEMAS & EDL TESTS (src/models/schemas.py)
# ============================================================================

@pytest.mark.tier5
class TestAdversarialEDLAndSchemas:
    """Stress-test schemas.py against out-of-bounds, negative, inverted, and malformed parameters."""

    # --- ClipSegment Boundaries ---

    def test_clip_segment_negative_source_in_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ClipSegment(source_in_sec=-0.001, source_out_sec=2.0)
        assert "source_in_sec" in str(exc.value)

    def test_clip_segment_negative_source_out_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=-5.0, source_out_sec=-1.0)

    def test_clip_segment_inverted_in_out_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ClipSegment(source_in_sec=10.0, source_out_sec=5.0)
        assert "strictly greater" in str(exc.value)

    def test_clip_segment_equal_in_out_zero_duration_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ClipSegment(source_in_sec=3.1415, source_out_sec=3.1415)
        assert "strictly greater" in str(exc.value)

    def test_clip_segment_negative_timeline_in_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, timeline_in_sec=-1.0)
        assert "timeline_in_sec" in str(exc.value)

    def test_clip_segment_zero_or_negative_speed_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, speed_multiplier=0.0)
        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, speed_multiplier=-2.0)

    def test_clip_segment_excessive_speed_multiplier_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, speed_multiplier=10.01)
        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, speed_multiplier=100.0)

    def test_clip_segment_volume_multiplier_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, volume_multiplier=-0.01)
        with pytest.raises(ValidationError):
            ClipSegment(source_in_sec=0.0, source_out_sec=2.0, volume_multiplier=5.01)

    # --- ColorGradeSettings Boundaries ---

    @pytest.mark.parametrize("invalid_contrast", [-0.01, -1.0, 3.01, 10.0])
    def test_color_grade_invalid_contrast_rejected(self, invalid_contrast: float) -> None:
        with pytest.raises(ValidationError):
            ColorGradeSettings(contrast=invalid_contrast)

    @pytest.mark.parametrize("invalid_brightness", [-1.01, -2.0, 1.01, 5.0])
    def test_color_grade_invalid_brightness_rejected(self, invalid_brightness: float) -> None:
        with pytest.raises(ValidationError):
            ColorGradeSettings(brightness=invalid_brightness)

    @pytest.mark.parametrize("invalid_saturation", [-0.01, -5.0, 3.01, 100.0])
    def test_color_grade_invalid_saturation_rejected(self, invalid_saturation: float) -> None:
        with pytest.raises(ValidationError):
            ColorGradeSettings(saturation=invalid_saturation)

    @pytest.mark.parametrize("invalid_gamma", [0.09, 0.0, -1.0, 10.01, 50.0])
    def test_color_grade_invalid_gamma_rejected(self, invalid_gamma: float) -> None:
        with pytest.raises(ValidationError):
            ColorGradeSettings(gamma=invalid_gamma)

    @pytest.mark.parametrize("invalid_channel_gamma", [0.09, -1.0, 10.01])
    def test_color_grade_invalid_channel_gamma_rejected(self, invalid_channel_gamma: float) -> None:
        with pytest.raises(ValidationError):
            ColorGradeSettings(gamma_r=invalid_channel_gamma)
        with pytest.raises(ValidationError):
            ColorGradeSettings(gamma_g=invalid_channel_gamma)
        with pytest.raises(ValidationError):
            ColorGradeSettings(gamma_b=invalid_channel_gamma)

    # --- AudioMasteringSettings Boundaries ---

    @pytest.mark.parametrize("invalid_lufs", [-70.1, -100.0, -4.9, 0.0, 10.0])
    def test_audio_mastering_invalid_lufs_rejected(self, invalid_lufs: float) -> None:
        with pytest.raises(ValidationError):
            AudioMasteringSettings(target_lufs=invalid_lufs)

    @pytest.mark.parametrize("invalid_peak", [-20.1, -30.0, 0.1, 1.0, 10.0])
    def test_audio_mastering_invalid_peak_limit_rejected(self, invalid_peak: float) -> None:
        with pytest.raises(ValidationError):
            AudioMasteringSettings(peak_limit_db=invalid_peak)

    @pytest.mark.parametrize("invalid_gain", [-30.1, -50.0, 30.1, 100.0])
    def test_audio_mastering_invalid_gain_db_rejected(self, invalid_gain: float) -> None:
        with pytest.raises(ValidationError):
            AudioMasteringSettings(gain_db=invalid_gain)

    # --- EditDecisionList Boundaries ---

    @pytest.mark.parametrize("odd_res", [(1921, 1080), (1920, 1081), (1921, 1081), (1080, 1919)])
    def test_edl_odd_resolution_rejected(self, odd_res: tuple[int, int]) -> None:
        with pytest.raises(ValidationError) as exc:
            EditDecisionList(
                job_id="job_odd",
                source_video_path="source.mp4",
                target_resolution=odd_res,
            )
        assert "even" in str(exc.value)

    @pytest.mark.parametrize("zero_or_neg_res", [(0, 1080), (1920, 0), (-1920, 1080), (1920, -1080)])
    def test_edl_zero_or_negative_resolution_rejected(self, zero_or_neg_res: tuple[int, int]) -> None:
        with pytest.raises(ValidationError) as exc:
            EditDecisionList(
                job_id="job_zero_res",
                source_video_path="source.mp4",
                target_resolution=zero_or_neg_res,
            )
        assert "positive integers" in str(exc.value)

    @pytest.mark.parametrize("invalid_fps", [0.0, -1.0, -29.97, 240.1, 1000.0])
    def test_edl_invalid_fps_rejected(self, invalid_fps: float) -> None:
        with pytest.raises(ValidationError):
            EditDecisionList(
                job_id="job_invalid_fps",
                source_video_path="source.mp4",
                target_fps=invalid_fps,
            )

    # --- VideoJob Progress Boundaries ---

    @pytest.mark.parametrize("invalid_progress", [-1.0, -0.01, 100.01, 150.0])
    def test_video_job_invalid_progress_rejected(self, invalid_progress: float) -> None:
        with pytest.raises(ValidationError):
            VideoJob(
                source_filepath="ingest/clip.mp4",
                progress_percent=invalid_progress,
            )


# ============================================================================
# 3. ADVERSARIAL FSM STATE MACHINE TESTS (src/models/state_machine.py)
# ============================================================================

@pytest.mark.tier5
class TestAdversarialFSMStateMachine:
    """Exhaustive adversarial validation of JobStatus finite state machine."""

    def test_all_status_pairs_exhaustively(self) -> None:
        """Verify all 19x19 = 361 permutations strictly follow ALLOWED_TRANSITIONS."""
        all_statuses = list(JobStatus)
        assert len(all_statuses) == 19

        for current, target in itertools.product(all_statuses, all_statuses):
            expected_allowed = (current == target) or (target in ALLOWED_TRANSITIONS.get(current, set()))
            actual_can_transition = can_transition(current, target)

            assert actual_can_transition == expected_allowed, (
                f"FSM mismatch for transition {current.value} -> {target.value}: "
                f"expected {expected_allowed}, got {actual_can_transition}"
            )

            if not expected_allowed:
                with pytest.raises(InvalidStateTransitionError) as excinfo:
                    validate_transition(current, target, job_id="adversarial_test_job")
                assert current.value in str(excinfo.value)
                assert target.value in str(excinfo.value)
                assert "adversarial_test_job" in str(excinfo.value)

    def test_terminal_states_cannot_transition_to_any_other_state(self) -> None:
        """DELIVERED and COMPLETED are strictly terminal; no transitions out allowed."""
        for terminal_state in (JobStatus.DELIVERED, JobStatus.COMPLETED):
            for other_state in JobStatus:
                if other_state == terminal_state:
                    assert can_transition(terminal_state, other_state) is True
                else:
                    assert can_transition(terminal_state, other_state) is False
                    with pytest.raises(InvalidStateTransitionError):
                        validate_transition(terminal_state, other_state)

    def test_illegal_lifecycle_jumps_rejected(self) -> None:
        """Ensure arbitrary state skips (e.g. DETECTED -> RENDERING) fail loudly."""
        illegal_jumps = [
            (JobStatus.PENDING, JobStatus.RENDERING),
            (JobStatus.PENDING, JobStatus.DELIVERING),
            (JobStatus.PENDING, JobStatus.DELIVERED),
            (JobStatus.PENDING, JobStatus.COMPLETED),
            (JobStatus.DETECTED, JobStatus.APPROVED),
            (JobStatus.DETECTED, JobStatus.RENDERING),
            (JobStatus.DETECTED, JobStatus.DELIVERED),
            (JobStatus.INGESTING, JobStatus.PROBING),
            (JobStatus.INGESTING, JobStatus.RENDERING),
            (JobStatus.INGESTED, JobStatus.APPROVED),
            (JobStatus.INGESTED, JobStatus.RENDERING),
            (JobStatus.PROBING, JobStatus.APPROVED),
            (JobStatus.PROBING, JobStatus.RENDERING),
            (JobStatus.PROBED, JobStatus.RENDERING),
            (JobStatus.PROBED, JobStatus.DELIVERED),
            (JobStatus.RENDERING, JobStatus.AWAITING_OVERRIDE),
            (JobStatus.RENDERING, JobStatus.PROBING),
            (JobStatus.DELIVERING, JobStatus.PROBING),
            (JobStatus.DELIVERING, JobStatus.RENDERING),
        ]
        for src, dst in illegal_jumps:
            assert can_transition(src, dst) is False
            with pytest.raises(InvalidStateTransitionError):
                validate_transition(src, dst)

    def test_transition_job_updates_timestamp_and_error(self) -> None:
        """transition_job must update status, updated_at timestamp, and optional error message."""
        job = VideoJob(source_filepath="ingest/video.mp4", status=JobStatus.DETECTED)
        t_before = job.updated_at

        # Valid transition with error message
        job = transition_job(job, JobStatus.FAILED, error_message="Disk full error")
        assert job.status == JobStatus.FAILED
        assert job.error_message == "Disk full error"
        assert job.updated_at >= t_before

    def test_transition_job_preserves_state_on_invalid_transition(self) -> None:
        """When an invalid transition is rejected, job state must remain intact (no side-effects)."""
        job = VideoJob(source_filepath="ingest/video.mp4", status=JobStatus.DETECTED)
        original_status = job.status
        original_updated_at = job.updated_at

        with pytest.raises(InvalidStateTransitionError):
            transition_job(job, JobStatus.DELIVERED)

        assert job.status == original_status
        assert job.updated_at == original_updated_at
        assert job.error_message is None
