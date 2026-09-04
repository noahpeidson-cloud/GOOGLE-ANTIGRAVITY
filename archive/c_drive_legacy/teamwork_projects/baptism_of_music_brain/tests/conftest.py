"""Pytest configuration and shared fixtures for baptism_of_music_brain test suite."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Optional, Tuple

import pytest

from tests.test_infra.media_generator import (
    generate_1080p_video,
    generate_4k_uhd_video,
    generate_corrupt_video,
    generate_noise_video,
    generate_odd_dimension_video,
    generate_silent_video,
    generate_smpte_bars_video,
    generate_vertical_video,
)
from tests.test_infra.ffprobe_validator import probe_media_file


@pytest.fixture(scope="session")
def session_media_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped directory for caching procedurally generated media."""
    media_dir = tmp_path_factory.mktemp("session_media")
    return media_dir


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Dict[str, Path]:
    """Create isolated test workspace containing ingest, delivery, and temp directories."""
    ingest_dir = tmp_path / "ingest"
    delivery_dir = tmp_path / "delivery"
    staging_dir = tmp_path / "staging"

    ingest_dir.mkdir(parents=True, exist_ok=True)
    delivery_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    return {
        "root": tmp_path,
        "ingest": ingest_dir,
        "delivery": delivery_dir,
        "staging": staging_dir,
    }


@pytest.fixture
def procedural_1080p_clip(session_media_dir: Path) -> Path:
    """Fixture providing a verified 1080p Full HD MP4 clip."""
    clip_path = session_media_dir / "bench_1080p.mp4"
    if not clip_path.exists():
        generate_1080p_video(clip_path, duration_sec=2.0)
    return clip_path


@pytest.fixture
def procedural_4k_clip(session_media_dir: Path) -> Path:
    """Fixture providing a verified 4K UHD MP4 clip."""
    clip_path = session_media_dir / "bench_4k_uhd.mp4"
    if not clip_path.exists():
        generate_4k_uhd_video(clip_path, duration_sec=2.0)
    return clip_path


@pytest.fixture
def procedural_vertical_clip(session_media_dir: Path) -> Path:
    """Fixture providing a verified 9:16 vertical video clip (1080x1920)."""
    clip_path = session_media_dir / "bench_vertical.mp4"
    if not clip_path.exists():
        generate_vertical_video(clip_path, duration_sec=2.0)
    return clip_path


@pytest.fixture
def procedural_noise_clip(session_media_dir: Path) -> Path:
    """Fixture providing a high-entropy noise clip."""
    clip_path = session_media_dir / "bench_noise.mp4"
    if not clip_path.exists():
        generate_noise_video(clip_path, duration_sec=1.5)
    return clip_path


@pytest.fixture
def procedural_silent_clip(session_media_dir: Path) -> Path:
    """Fixture providing a clip with no audio stream."""
    clip_path = session_media_dir / "bench_silent.mp4"
    if not clip_path.exists():
        generate_silent_video(clip_path, duration_sec=2.0)
    return clip_path


@pytest.fixture
def procedural_smpte_clip(session_media_dir: Path) -> Path:
    """Fixture providing SMPTE color bars clip."""
    clip_path = session_media_dir / "bench_smpte.mp4"
    if not clip_path.exists():
        generate_smpte_bars_video(clip_path, duration_sec=2.0)
    return clip_path


@pytest.fixture
def corrupt_media_file(tmp_path: Path) -> Path:
    """Fixture providing a corrupted video file."""
    corrupt_path = tmp_path / "corrupt_clip.mp4"
    generate_corrupt_video(corrupt_path)
    return corrupt_path


@pytest.fixture
def odd_dimension_clip(session_media_dir: Path) -> Path:
    """Fixture providing a clip with non-standard odd resolution (1921x1081)."""
    clip_path = session_media_dir / "bench_odd_dim.mp4"
    if not clip_path.exists():
        generate_odd_dimension_video(clip_path, duration_sec=1.0)
    return clip_path


@pytest.fixture
def sample_edl_dict_factory() -> Callable[..., Dict[str, Any]]:
    """Factory fixture for producing schema-compliant EDL dictionaries."""
    def _create(
        job_id: str = "job_test_001",
        source_path: str = "ingest/sample.mp4",
        resolution: Tuple[int, int] = (1920, 1080),
        fps: float = 30.0,
        profile: str = "x264_crf17",
        segments: Optional[list] = None,
        contrast: float = 1.0,
        brightness: float = 0.0,
        saturation: float = 1.0,
        gamma: float = 1.0,
        normalize_lufs: bool = True,
        target_lufs: float = -14.0,
        peak_limit_db: float = -1.5,
        gain_db: float = 0.0,
        manual_override_applied: bool = False,
    ) -> Dict[str, Any]:
        if segments is None:
            segments = [
                {
                    "clip_id": "seg_01",
                    "source_in_sec": 0.0,
                    "source_out_sec": 1.5,
                    "timeline_in_sec": 0.0,
                    "speed_multiplier": 1.0,
                    "volume_multiplier": 1.0,
                    "label": "intro_drop",
                }
            ]
        return {
            "job_id": job_id,
            "source_video_path": source_path,
            "target_resolution": resolution,
            "target_fps": fps,
            "encoding_profile": profile,
            "segments": segments,
            "color_grade": {
                "contrast": contrast,
                "brightness": brightness,
                "saturation": saturation,
                "gamma": gamma,
            },
            "audio_mastering": {
                "normalize_lufs": normalize_lufs,
                "target_lufs": target_lufs,
                "peak_limit_db": peak_limit_db,
                "gain_db": gain_db,
            },
            "manual_override_applied": manual_override_applied,
        }

    return _create
