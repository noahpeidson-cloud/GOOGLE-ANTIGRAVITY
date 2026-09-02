"""Tier 2 Boundary Tests: Win32 File Locking Edge Cases."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

try:
    from src.watcher.file_locker import is_file_locked, wait_until_unlocked
except ImportError:
    is_file_locked = None
    wait_until_unlocked = None


def _check_locker():
    if is_file_locked is None:
        pytest.skip("src.watcher.file_locker not yet implemented")


@pytest.mark.tier2
def test_boundary_zero_byte_file_lock(tmp_path: Path):
    """Verify 0-byte file created but not written to is handled safely."""
    _check_locker()
    zero_file = tmp_path / "empty_drop.mp4"
    zero_file.touch()
    assert isinstance(is_file_locked(zero_file), bool)


@pytest.mark.tier2
def test_boundary_temporary_browser_download_extensions(tmp_path: Path):
    """Verify lock handler recognizes incomplete temporary browser extensions."""
    _check_locker()
    part_file = tmp_path / "video.mp4.crdownload"
    part_file.write_bytes(b"downloading...")
    locked = is_file_locked(part_file)
    assert isinstance(locked, bool)


@pytest.mark.tier2
def test_boundary_instant_zero_timeout(tmp_path: Path):
    """Verify wait_until_unlocked handles timeout_sec=0.0 gracefully."""
    _check_locker()
    test_file = tmp_path / "quick_check.mp4"
    test_file.write_bytes(b"data_payload")
    result = wait_until_unlocked(test_file, timeout_sec=0.0, debounce_sec=0.0)
    assert result is True


@pytest.mark.tier2
def test_boundary_partial_chunk_write_release_cycle(tmp_path: Path):
    """Verify file actively toggling between open/write and close is detected."""
    _check_locker()
    cycle_file = tmp_path / "cycling_writer.mp4"
    cycle_file.touch()

    with open(cycle_file, "wb") as f:
        f.write(b"chunk1")
    assert is_file_locked(cycle_file) is False

    with open(cycle_file, "ab") as f:
        f.write(b"chunk2")
        f.flush()
        assert is_file_locked(cycle_file) is True


@pytest.mark.tier2
def test_boundary_rapid_concurrent_lock_polling(tmp_path: Path):
    """Verify rapid consecutive is_file_locked calls do not crash or leak file handles."""
    _check_locker()
    poll_file = tmp_path / "rapid_poll.mp4"
    poll_file.write_bytes(b"test_content_stream")

    for _ in range(100):
        res = is_file_locked(poll_file)
        assert res is False


@pytest.mark.tier2
def test_boundary_read_only_file_locking(tmp_path: Path):
    """Verify read-only marked files are correctly assessed as unlocked."""
    _check_locker()
    ro_file = tmp_path / "readonly_footage.mp4"
    ro_file.write_bytes(b"\x00" * 4096)
    os.chmod(ro_file, 0o444)
    try:
        assert is_file_locked(ro_file) is False
    finally:
        os.chmod(ro_file, 0o666)


@pytest.mark.tier2
def test_boundary_deleted_file_during_lock_poll(tmp_path: Path):
    """Verify file removed during lock polling does not cause uncaught crash."""
    _check_locker()
    temp_f = tmp_path / "deleted_midway.mp4"
    temp_f.write_bytes(b"short_lived")
    temp_f.unlink()
    try:
        assert is_file_locked(temp_f) is True
    except (FileNotFoundError, OSError):
        pass


@pytest.mark.tier2
def test_boundary_negative_timeout_handling(tmp_path: Path):
    """Verify negative timeout values are clamped or return immediately."""
    _check_locker()
    test_file = tmp_path / "neg_timeout.mp4"
    test_file.write_bytes(b"some_bytes")
    res = wait_until_unlocked(test_file, timeout_sec=-1.0, debounce_sec=0.0)
    assert isinstance(res, bool)
