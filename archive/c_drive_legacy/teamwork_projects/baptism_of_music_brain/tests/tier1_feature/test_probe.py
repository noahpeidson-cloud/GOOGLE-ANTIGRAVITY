"""Tier 1 Feature Tests: FFprobe media stream prober and parser."""

from __future__ import annotations

from pathlib import Path
import pytest

from src.renderer.probe import (
    CorruptMediaError,
    FFprobeError,
    FFprobeExecutionError,
    FFprobeNotFoundError,
    MediaFileNotFoundError,
    async_probe_media,
    parse_fractional_rate,
    probe_media,
)


@pytest.mark.tier1
@pytest.mark.media
class TestProbeMediaSuccess:
    """Unit tests for successful media probing across various procedural video formats."""

    def test_probe_1080p_clip(self, procedural_1080p_clip: Path) -> None:
        result = probe_media(procedural_1080p_clip)

        assert result.width == 1920
        assert result.height == 1080
        assert result.fps == pytest.approx(30.0, abs=0.05)
        assert result.has_video is True
        assert result.has_audio is True
        assert result.primary_video.codec_name in ("h264", "libx264")
        assert result.primary_audio.codec_name == "aac"
        assert result.primary_audio.sample_rate == 48000
        assert result.duration_sec > 0.0

    def test_probe_4k_clip(self, procedural_4k_clip: Path) -> None:
        result = probe_media(procedural_4k_clip)

        assert result.width == 3840
        assert result.height == 2160
        assert result.fps == pytest.approx(60.0, abs=0.05)
        assert result.has_video is True
        assert result.has_audio is True

    def test_probe_vertical_clip(self, procedural_vertical_clip: Path) -> None:
        result = probe_media(procedural_vertical_clip)

        assert result.width == 1080
        assert result.height == 1920
        assert result.fps == pytest.approx(30.0, abs=0.05)

    def test_probe_silent_clip(self, procedural_silent_clip: Path) -> None:
        result = probe_media(procedural_silent_clip)

        assert result.has_video is True
        assert result.has_audio is False
        assert len(result.audio_streams) == 0
        assert result.primary_audio is None

    @pytest.mark.asyncio
    async def test_async_probe_media(self, procedural_1080p_clip: Path) -> None:
        result = await async_probe_media(procedural_1080p_clip)

        assert result.width == 1920
        assert result.height == 1080
        assert result.has_video is True


@pytest.mark.tier1
class TestProbeErrorHandling:
    """Unit tests for probe error handling and edge cases."""

    def test_nonexistent_file_raises_not_found(self, tmp_path: Path) -> None:
        missing = tmp_path / "ghost_video.mp4"
        with pytest.raises(MediaFileNotFoundError):
            probe_media(missing)

    def test_zero_byte_file_raises_corrupt(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.mp4"
        empty.touch()
        with pytest.raises(CorruptMediaError) as excinfo:
            probe_media(empty)
        assert "0 bytes" in str(excinfo.value)

    def test_corrupt_file_raises_corrupt(self, corrupt_media_file: Path) -> None:
        with pytest.raises(CorruptMediaError):
            probe_media(corrupt_media_file)

    def test_invalid_ffprobe_bin_raises_error(self, procedural_1080p_clip: Path) -> None:
        with pytest.raises(FFprobeNotFoundError):
            probe_media(procedural_1080p_clip, ffprobe_bin="nonexistent_ffprobe_bin_path_12345")

    def test_parse_fractional_rate_edge_cases(self) -> None:
        assert parse_fractional_rate("30/1") == 30.0
        assert parse_fractional_rate("30000/1001") == pytest.approx(29.97003, abs=0.001)
        assert parse_fractional_rate("60000/1001") == pytest.approx(59.94006, abs=0.001)
        assert parse_fractional_rate("24000/1001") == pytest.approx(23.97602, abs=0.001)
        assert parse_fractional_rate("0/0", default=30.0) == 30.0
        assert parse_fractional_rate("N/A", default=25.0) == 25.0
        assert parse_fractional_rate(None, default=30.0) == 30.0
        assert parse_fractional_rate("", default=30.0) == 30.0
        assert parse_fractional_rate("invalid", default=30.0) == 30.0
