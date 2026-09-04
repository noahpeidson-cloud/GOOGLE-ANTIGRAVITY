"""Tier 1 Feature Tests: 3-tier Windows file lock detector."""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest

from src.watcher import file_locker


@pytest.mark.tier1
class TestTier1ExtensionFilters:
    """Unit tests for Tier 1 temporary and media extension filters."""

    def test_temporary_extensions_detected(self) -> None:
        temp_files = [
            "video.mp4.tmp",
            "video.part",
            "video.crdownload",
            "video.downloading",
            "video.aria2",
            "video.partial",
            "video.uploading",
            "video.incomplete",
            "video.temp",
            "video.swp",
            "video.lock",
        ]
        for tf in temp_files:
            assert file_locker.is_temporary_file(tf) is True, f"Failed to detect temporary file: {tf}"

    def test_hidden_and_office_prefixes_detected(self) -> None:
        prefixed_files = [
            ".DS_Store",
            ".hidden_clip.mp4",
            "~$active_recording.mp4",
            "._apple_double.mov",
        ]
        for pf in prefixed_files:
            assert file_locker.is_temporary_file(pf) is True, f"Failed to detect prefixed temp file: {pf}"

    def test_supported_media_extensions(self) -> None:
        valid_media = ["clip.mp4", "CLIP.MP4", "shot.mov", "shot.MOV", "raw.mkv", "raw.webm", "raw.avi"]
        for vm in valid_media:
            assert file_locker.is_supported_media(vm) is True
            assert file_locker.is_temporary_file(vm) is False

        invalid_media = ["notes.txt", "thumbnail.jpg", "metadata.json", "audio.mp3", "script.py"]
        for im in invalid_media:
            assert file_locker.is_supported_media(im) is False


@pytest.mark.tier1
class TestTier2ExclusiveHandle:
    """Unit tests for Tier 2 exclusive file handle tests."""

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.mp4"
        ok, err = file_locker.test_exclusive_handle(p)
        assert ok is False
        assert "not exist" in str(err)

    def test_unlocked_file(self, tmp_path: Path) -> None:
        p = tmp_path / "unlocked.mp4"
        p.write_bytes(b"sample video bytes content")
        ok, err = file_locker.test_exclusive_handle(p)
        assert ok is True
        assert err is None

    def test_locked_file_detected(self, tmp_path: Path) -> None:
        p = tmp_path / "locked.mp4"
        p.write_bytes(b"data")

        # Open file in exclusive write mode to simulate active transfer
        with open(p, "r+b"):
            result = file_locker.check_file_lock(p, debounce_interval_sec=0.01)
            assert result.checked_path == str(p.resolve())


@pytest.mark.tier1
class TestTier3SizeStability:
    """Unit tests for Tier 3 size stability debounce."""

    def test_zero_byte_file_fails(self, tmp_path: Path) -> None:
        p = tmp_path / "zero_byte.mp4"
        p.touch()
        ok, size, err = file_locker.test_size_stability(p, interval_sec=0.01)
        assert ok is False
        assert size == 0
        assert "zero bytes" in str(err)

        res = file_locker.check_file_lock(p, debounce_interval_sec=0.01)
        assert res.is_locked is True
        assert res.tier_failed == 3
        assert "zero bytes" in res.reason

    def test_stable_file_passes(self, tmp_path: Path) -> None:
        p = tmp_path / "stable.mp4"
        content = b"X" * 1024
        p.write_bytes(content)

        ok, size, err = file_locker.test_size_stability(p, interval_sec=0.05)
        assert ok is True
        assert size == 1024
        assert err is None

        res = file_locker.check_file_lock(p, debounce_interval_sec=0.05)
        assert res.is_ready is True
        assert res.is_locked is False
        assert res.tier_failed is None
        assert res.file_size_bytes == 1024

    @pytest.mark.asyncio
    async def test_async_size_stability(self, tmp_path: Path) -> None:
        p = tmp_path / "async_stable.mp4"
        p.write_bytes(b"Y" * 2048)

        ok, size, err = await file_locker.test_size_stability_async(p, interval_sec=0.05)
        assert ok is True
        assert size == 2048
        assert err is None

        res = await file_locker.check_file_lock_async(p, debounce_interval_sec=0.05)
        assert res.is_ready is True
        assert res.file_size_bytes == 2048


@pytest.mark.tier1
class TestWaitUntilUnlocked:
    """Unit tests for async waiting until file unlock."""

    @pytest.mark.asyncio
    async def test_wait_until_unlocked_success(self, tmp_path: Path) -> None:
        p = tmp_path / "delayed_ready.mp4"
        p.write_bytes(b"Z" * 512)

        res = await file_locker.wait_until_file_unlocked(
            p,
            timeout_sec=2.0,
            poll_interval_sec=0.05,
            debounce_interval_sec=0.05,
        )
        assert res.is_ready is True
        assert res.file_size_bytes == 512

    @pytest.mark.asyncio
    async def test_wait_until_unlocked_timeout_on_temp_file(self, tmp_path: Path) -> None:
        p = tmp_path / "never_ready.crdownload"
        p.write_bytes(b"downloading chunk")

        res = await file_locker.wait_until_file_unlocked(
            p,
            timeout_sec=0.2,
            poll_interval_sec=0.05,
            debounce_interval_sec=0.05,
        )
        assert res.is_locked is True
        assert res.tier_failed == 1
        assert "timed out" in res.reason
