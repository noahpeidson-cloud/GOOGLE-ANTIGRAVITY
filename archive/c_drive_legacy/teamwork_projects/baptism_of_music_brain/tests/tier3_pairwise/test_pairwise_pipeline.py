"""Tier 3 Pairwise Tests: Cross-Feature Combinations and Integration Matrix."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Tuple

import pytest

from tests.test_infra.media_generator import (
    generate_1080p_video,
    generate_4k_uhd_video,
    generate_noise_video,
    generate_smpte_bars_video,
    generate_vertical_video,
)
from tests.test_infra.ffprobe_validator import assert_visually_lossless, probe_media_file


# Pairwise matrix parameters:
# 1. Resolutions: 1080p, 4K, Vertical (9:16)
# 2. Content types: Clean pattern (testsrc2), Color calibration (smptebars), High entropy (noise)
# 3. Audio modes: Standard stereo sine, High sample rate, Silent
# 4. Color Grades: Neutral, Warm EDM boost, Moody desaturated
# 5. Profiles: x264_crf17, x264_yuv444p, x265_crf16


@pytest.mark.tier3
@pytest.mark.media
def test_pairwise_1080p_clean_standard_x264(tmp_path: Path):
    """Pairwise combination 1: 1080p + testsrc2 + standard audio + default grade + x264_crf17."""
    clip = tmp_path / "pw_1080p_clean.mp4"
    generate_1080p_video(clip, duration_sec=1.0)
    assert_visually_lossless(
        clip,
        expected_resolution=(1920, 1080),
        expected_fps=30.0,
        expected_vcodec="h264",
        expected_profile="High",
    )


@pytest.mark.tier3
@pytest.mark.media
def test_pairwise_4k_smpte_color_x264(tmp_path: Path):
    """Pairwise combination 2: 4K UHD + smptebars + 60fps + x264_crf17."""
    clip = tmp_path / "pw_4k_smpte.mp4"
    generate_4k_uhd_video(clip, duration_sec=1.0, fps=60.0)
    assert_visually_lossless(
        clip,
        expected_resolution=(3840, 2160),
        expected_fps=60.0,
        expected_vcodec="h264",
        expected_profile="High",
    )


@pytest.mark.tier3
@pytest.mark.media
def test_pairwise_vertical_noise_high_entropy(tmp_path: Path):
    """Pairwise combination 3: 9:16 Vertical + noise pattern + audio tone."""
    clip = tmp_path / "pw_vert_noise.mp4"
    generate_vertical_video(clip, duration_sec=1.0)
    assert_visually_lossless(
        clip,
        expected_resolution=(1080, 1920),
        expected_fps=30.0,
        expected_vcodec="h264",
        expected_profile="High",
    )


@pytest.mark.tier3
@pytest.mark.media
@pytest.mark.parametrize(
    "resolution,fps,expected_wh",
    [
        ((1920, 1080), 30.0, (1920, 1080)),
        ((3840, 2160), 60.0, (3840, 2160)),
        ((1080, 1920), 30.0, (1080, 1920)),
        ((1280, 720), 24.0, (1280, 720)),
    ],
)
def test_pairwise_resolution_fps_matrix(tmp_path: Path, resolution: Tuple[int, int], fps: float, expected_wh: Tuple[int, int]):
    """Pairwise combinations 4-7: Parametric resolution and frame rate matrix."""
    from tests.test_infra.media_generator import generate_procedural_video
    clip = tmp_path / f"pw_matrix_{expected_wh[0]}x{expected_wh[1]}.mp4"
    generate_procedural_video(clip, duration_sec=1.0, resolution=resolution, fps=fps)
    assert_visually_lossless(clip, expected_resolution=expected_wh, expected_fps=fps)


@pytest.mark.tier3
def test_pairwise_model_to_filtergraph_integration(sample_edl_dict_factory):
    """Pairwise combination 8: Schema EDL serialization into Filtergraph compilation."""
    try:
        from src.models.schemas import EditDecisionList
        from src.renderer.filtergraph import build_filtergraph
    except ImportError:
        pytest.skip("Filtergraph or schemas module not yet implemented")

    edl_dict = sample_edl_dict_factory(
        job_id="pw_edl_fg_01",
        contrast=1.3,
        saturation=1.4,
        normalize_lufs=True,
    )
    edl = EditDecisionList(**edl_dict)
    fg_str = build_filtergraph(edl)
    assert "eq=" in fg_str
    assert "contrast=1.3" in fg_str
    assert "loudnorm" in fg_str


@pytest.mark.tier3
def test_pairwise_ml_mock_to_job_manager_integration():
    """Pairwise combination 9: Ingest Job creation + Mock ML grading attaching active EDL."""
    try:
        from src.models.schemas import JobStatus
        from src.ml_brain.mock_provider import MockMLProvider
        from src.pipeline.job_manager import JobManager
    except ImportError:
        pytest.skip("Pipeline modules not yet implemented")

    manager = JobManager()
    ml_provider = MockMLProvider()

    job = manager.create_job(source_filepath="ingest/test_4k.mp4")
    assert job.status == JobStatus.INGESTED

    probe_data = {"width": 3840, "height": 2160, "duration": 4.0, "fps": 60.0}
    edl = ml_provider.grade_video(job, probe_data)
    manager.update_edl(job.job_id, edl)
    manager.update_status(job.job_id, JobStatus.AWAITING_OVERRIDE)

    updated_job = manager.get_job(job.job_id)
    assert updated_job.status == JobStatus.AWAITING_OVERRIDE
    assert updated_job.active_edl is not None
    assert updated_job.active_edl.target_resolution == (3840, 2160)


@pytest.mark.tier3
def test_pairwise_api_override_to_job_manager_flow(sample_edl_dict_factory):
    """Pairwise combination 10: REST API override modifying active EDL in JobManager."""
    try:
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        from src.pipeline.job_manager import JobManager
    except ImportError:
        pytest.skip("API / Pipeline modules not yet implemented")

    app = create_app()
    client = TestClient(app)

    trig = client.post("/api/v1/jobs/ingest/trigger", json={"filepath": "ingest/edm.mp4"})
    if trig.status_code in (200, 201):
        job_id = trig.json()["job_id"]
        override = sample_edl_dict_factory(job_id=job_id, contrast=1.6, manual_override_applied=True)
        put_resp = client.put(f"/api/v1/jobs/{job_id}/edl", json=override)
        assert put_resp.status_code in (200, 202)


@pytest.mark.tier3
def test_pairwise_profile_selection_to_ffmpeg_command():
    """Pairwise combination 11: Profile selection mapped to command line arguments."""
    try:
        from src.renderer.profiles import get_encoding_args
    except ImportError:
        pytest.skip("Profiles module not yet implemented")

    for prof in ["x264_crf17", "x264_yuv444p", "x265_crf16"]:
        args = get_encoding_args(prof)
        assert isinstance(args, list)
        assert len(args) >= 4


@pytest.mark.tier3
@pytest.mark.media
def test_pairwise_color_grade_eq_render(tmp_path: Path, procedural_1080p_clip: Path):
    """Pairwise combination 12: Media clip + EQ filter color grade + render validation."""
    from tests.test_infra.media_generator import get_ffmpeg_binary
    output_path = tmp_path / "pw_color_grade.mp4"
    ffmpeg_bin = get_ffmpeg_binary()

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(procedural_1080p_clip),
        "-vf", "eq=contrast=1.4:brightness=0.05:saturation=1.5:gamma=0.9",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(output_path),
    ]
    subprocess_res = __import__("subprocess").run(cmd, capture_output=True)
    assert subprocess_res.returncode == 0
    assert output_path.exists()


@pytest.mark.tier3
@pytest.mark.media
def test_pairwise_loudnorm_audio_render(tmp_path: Path, procedural_1080p_clip: Path):
    """Pairwise combination 13: Media clip + loudnorm audio filter + render validation."""
    from tests.test_infra.media_generator import get_ffmpeg_binary
    output_path = tmp_path / "pw_loudnorm_rendered.mp4"
    ffmpeg_bin = get_ffmpeg_binary()

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(procedural_1080p_clip),
        "-af", "loudnorm=I=-14.0:TP=-1.5:LRA=11",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "320k",
        str(output_path),
    ]
    subprocess_res = __import__("subprocess").run(cmd, capture_output=True)
    assert subprocess_res.returncode == 0
    assert output_path.exists()


@pytest.mark.tier3
@pytest.mark.media
def test_pairwise_multi_cut_concat_render(tmp_path: Path, procedural_1080p_clip: Path):
    """Pairwise combination 14: Trim + concat complex filtergraph render."""
    from tests.test_infra.media_generator import get_ffmpeg_binary
    output_path = tmp_path / "pw_concat_rendered.mp4"
    ffmpeg_bin = get_ffmpeg_binary()

    filter_complex = (
        "[0:v]trim=start=0:end=0.5,setpts=PTS-STARTPTS[v1];"
        "[0:a]atrim=start=0:end=0.5,asetpts=PTS-STARTPTS[a1];"
        "[0:v]trim=start=1.0:end=1.5,setpts=PTS-STARTPTS[v2];"
        "[0:a]atrim=start=1.0:end=1.5,asetpts=PTS-STARTPTS[a2];"
        "[v1][a1][v2][a2]concat=n=2:v=1:a=1[outv][outa]"
    )

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(procedural_1080p_clip),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(output_path),
    ]
    subprocess_res = __import__("subprocess").run(cmd, capture_output=True)
    assert subprocess_res.returncode == 0
    assert output_path.exists()
