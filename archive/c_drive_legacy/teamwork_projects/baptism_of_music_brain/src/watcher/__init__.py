"""Watcher package for directory monitoring and file locking detection."""

from src.watcher.file_locker import (
    DEFAULT_MEDIA_EXTENSIONS,
    DEFAULT_TEMP_EXTENSIONS,
    LockCheckResult,
    check_file_lock,
    check_file_lock_async,
    is_file_locked,
    is_supported_media,
    is_temporary_file,
    test_exclusive_handle,
    test_size_stability,
    test_size_stability_async,
    wait_until_file_unlocked,
    wait_until_unlocked,
)
from src.watcher.ingest_watcher import IngestWatcher

__all__ = [
    "DEFAULT_MEDIA_EXTENSIONS",
    "DEFAULT_TEMP_EXTENSIONS",
    "LockCheckResult",
    "is_temporary_file",
    "is_supported_media",
    "test_exclusive_handle",
    "test_size_stability",
    "test_size_stability_async",
    "check_file_lock",
    "check_file_lock_async",
    "wait_until_file_unlocked",
    "is_file_locked",
    "wait_until_unlocked",
    "IngestWatcher",
]
