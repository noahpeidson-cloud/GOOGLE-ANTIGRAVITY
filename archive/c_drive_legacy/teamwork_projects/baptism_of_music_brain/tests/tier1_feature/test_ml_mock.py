"""Tier 1 Feature Tests: Deterministic Mock ML Grading Engine & Gemini Omni Provider."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.ml_brain.base import BaseMLProvider, MLAuthenticationError, MLGradingError
from src.ml_brain.gemini_provider import GeminiOmniProvider
from src.ml_brain.mock_provider import MockMLProvider
from src.models.schemas import EditDecisionList, JobMetadata, JobStatus, MediaProbeResult


@pytest.fixture
def mock_ml_provider():
    return MockMLProvider()


@pytest.fixture
def dummy_job():
    return JobMetadata(
        job_id="job_mock_test_001",
        source_filepath="ingest/sample_raw.mp4",
        status=JobStatus.INGESTED,
    )


@pytest.fixture
def sample_probe_data():
    return {
        "width": 1920,
        "height": 1080,
        "duration": 5.0,
        "fps": 30.0,
        "vcodec": "h264",
        "acodec": "aac",
    }


@pytest.mark.tier1
def test_ml_mock_generates_valid_edl(mock_ml_provider, dummy_job, sample_probe_data):
    """Verify mock provider generates a schema-compliant EditDecisionList."""
    edl = mock_ml_provider.grade_video(dummy_job, sample_probe_data)
    assert isinstance(edl, EditDecisionList)
    assert edl.job_id == dummy_job.job_id
    assert len(edl.segments) >= 1
    assert edl.target_resolution == (1920, 1080)


@pytest.mark.tier1
def test_ml_mock_segments_within_source_duration(mock_ml_provider, dummy_job, sample_probe_data):
    """Verify all generated cut segments are strictly bounded within the source duration."""
    edl = mock_ml_provider.grade_video(dummy_job, sample_probe_data)
    duration = sample_probe_data["duration"]
    for seg in edl.segments:
        assert 0.0 <= seg.source_in_sec < seg.source_out_sec <= duration, (
            f"Segment {seg.clip_id} bounds [{seg.source_in_sec}, {seg.source_out_sec}] exceed duration {duration}"
        )


@pytest.mark.tier1
def test_ml_mock_color_grade_defaults(mock_ml_provider, dummy_job, sample_probe_data):
    """Verify generated color grading parameters are within normalized bounds."""
    edl = mock_ml_provider.grade_video(dummy_job, sample_probe_data)
    cg = edl.color_grade
    assert 0.0 <= cg.contrast <= 3.0
    assert -1.0 <= cg.brightness <= 1.0
    assert 0.0 <= cg.saturation <= 3.0
    assert 0.1 <= cg.gamma <= 10.0


@pytest.mark.tier1
def test_ml_mock_audio_mastering_defaults(mock_ml_provider, dummy_job, sample_probe_data):
    """Verify generated audio mastering applies loudness normalization to -14 LUFS."""
    edl = mock_ml_provider.grade_video(dummy_job, sample_probe_data)
    am = edl.audio_mastering
    assert am.normalize_lufs is True
    assert am.target_lufs == -14.0
    assert am.peak_limit_db == -1.5


@pytest.mark.tier1
def test_ml_mock_deterministic_reproducibility(mock_ml_provider, dummy_job, sample_probe_data):
    """Verify mock provider produces bit-for-bit identical EDLs for identical inputs."""
    edl1 = mock_ml_provider.grade_video(dummy_job, sample_probe_data)
    edl2 = mock_ml_provider.grade_video(dummy_job, sample_probe_data)
    assert edl1.model_dump() == edl2.model_dump(), "Mock ML provider must be strictly deterministic"


@pytest.mark.tier1
def test_ml_mock_handles_variable_durations(mock_ml_provider, dummy_job):
    """Verify mock provider scales cuts appropriately for short vs long source clips."""
    for dur in [0.8, 1.5, 4.0, 10.0, 60.0]:
        probe_info = {"width": 1920, "height": 1080, "duration": dur, "fps": 30.0}
        edl = mock_ml_provider.grade_video(dummy_job, probe_info)
        assert len(edl.segments) >= 1
        assert edl.segments[-1].source_out_sec <= dur


@pytest.mark.tier1
def test_ml_mock_preserves_target_frame_rate(mock_ml_provider, dummy_job):
    """Verify mock provider preserves source frame rate (e.g. 60fps) in target EDL."""
    probe_info = {"width": 3840, "height": 2160, "duration": 5.0, "fps": 60.0}
    edl = mock_ml_provider.grade_video(dummy_job, probe_info)
    assert edl.target_fps == 60.0


@pytest.mark.tier1
def test_ml_mock_prompt_responsiveness(mock_ml_provider, dummy_job, sample_probe_data):
    """Verify creative prompts steer color grading parameters in mock provider."""
    edl_cyberpunk = mock_ml_provider.grade_video(dummy_job, sample_probe_data, user_prompt="Cyberpunk neon style")
    assert edl_cyberpunk.color_grade.saturation > 1.3
    assert edl_cyberpunk.color_grade.contrast > 1.2

    edl_dark = mock_ml_provider.grade_video(dummy_job, sample_probe_data, user_prompt="Moody dark aesthetic")
    assert edl_dark.color_grade.brightness < 0.0


@pytest.mark.tier1
@pytest.mark.asyncio
async def test_ml_mock_async_execution(mock_ml_provider, dummy_job, sample_probe_data):
    """Verify async grade_video_async produces valid EDL."""
    edl = await mock_ml_provider.grade_video_async(dummy_job, sample_probe_data)
    assert isinstance(edl, EditDecisionList)
    assert edl.job_id == dummy_job.job_id


@pytest.mark.tier1
def test_gemini_provider_fallback_when_unauthenticated(dummy_job, sample_probe_data):
    """Verify GeminiOmniProvider gracefully falls back to mock provider when no API key is provided."""
    provider = GeminiOmniProvider(api_key=None, fallback_to_mock=True)
    edl = provider.grade_video(dummy_job, sample_probe_data)
    assert isinstance(edl, EditDecisionList)
    assert edl.job_id == dummy_job.job_id


@pytest.mark.tier1
def test_gemini_provider_r27_503_retry():
    """Verify Rule R27: GeminiOmniProvider retries on 503 UNAVAILABLE errors with exponential backoff."""
    provider = GeminiOmniProvider(
        api_key="fake_test_key",
        max_retries=3,
        initial_backoff_sec=0.01,
        backoff_multiplier=1.5,
    )

    mock_client = MagicMock()
    # First 2 calls fail with 503, 3rd call succeeds
    mock_response = MagicMock()
    mock_response.text = (
        '{"segments": [{"clip_id": "seg_1", "source_in_sec": 0.0, "source_out_sec": 2.0, "timeline_in_sec": 0.0}],'
        ' "color_grade": {"contrast": 1.2, "saturation": 1.3},'
        ' "audio_mastering": {"normalize_lufs": true, "target_lufs": -14.0}}'
    )
    mock_client.models.generate_content.side_effect = [
        Exception("503 Server Unavailable: temporary overload"),
        Exception("UNAVAILABLE: Service temporarily unavailable"),
        mock_response,
    ]
    provider._client = mock_client

    job = JobMetadata(job_id="job_r27_test", source_filepath="video.mp4", status=JobStatus.INGESTED)
    edl = provider.grade_video(job, {"width": 1920, "height": 1080, "duration": 5.0})

    assert isinstance(edl, EditDecisionList)
    assert mock_client.models.generate_content.call_count == 3
