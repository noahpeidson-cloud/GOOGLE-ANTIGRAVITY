"""Pytest configuration and global fixtures for Viral Trend Pipeline integration tests."""

import socket
from typing import Generator
import pytest

from viral_trend_pipeline.models import NetworkBlockError
from viral_trend_pipeline.extractors.chrome_devtools import ChromeDevToolsExtractor
from viral_trend_pipeline.extractors.android_cli import AndroidCLIExtractor
from viral_trend_pipeline.storage.database import SQLiteTrendStore
from viral_trend_pipeline.storage.garbage_collector import GarbageCollector
from tests.fixtures.chrome_fixtures import (
    get_tiktok_a11y_snapshot,
    get_youtube_a11y_snapshot,
)
from tests.fixtures.android_fixtures import (
    get_instagram_reels_layout_json,
    get_instagram_reels_layout_data,
)


@pytest.fixture(autouse=True)
def block_network_sockets(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Enforce 100% deterministic offline execution by barring socket.socket.connect.
    Any unmocked network request attempting a socket connection will immediately fail with NetworkBlockError.
    """
    def guarded_connect(*args, **kwargs):
        raise NetworkBlockError(
            "CRITICAL: Real network socket connection blocked during integration test! "
            "All extractions must use deterministic mock fixtures."
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    yield


@pytest.fixture
def chrome_extractor() -> ChromeDevToolsExtractor:
    """Fixture providing a configured ChromeDevToolsExtractor instance."""
    return ChromeDevToolsExtractor(default_anchor_date="2026-08-22")


@pytest.fixture
def android_extractor() -> AndroidCLIExtractor:
    """Fixture providing a configured AndroidCLIExtractor instance."""
    return AndroidCLIExtractor(default_anchor_date="2026-08-22")


@pytest.fixture
def tiktok_a11y_raw() -> str:
    """Fixture returning raw TikTok Creative Center a11y tree snapshot text."""
    return get_tiktok_a11y_snapshot()


@pytest.fixture
def youtube_a11y_raw() -> str:
    """Fixture returning raw YouTube Trending a11y tree snapshot text."""
    return get_youtube_a11y_snapshot()


@pytest.fixture
def instagram_layout_raw() -> str:
    """Fixture returning raw Instagram Reels layout JSON string."""
    return get_instagram_reels_layout_json()


@pytest.fixture
def instagram_layout_data() -> list:
    """Fixture returning parsed Instagram Reels layout data list."""
    return get_instagram_reels_layout_data()


@pytest.fixture
def trend_store() -> Generator[SQLiteTrendStore, None, None]:
    """Fixture providing a clean in-memory SQLiteTrendStore instance."""
    store = SQLiteTrendStore(":memory:")
    yield store
    store.close()


@pytest.fixture
def temp_trend_store(tmp_path) -> Generator[SQLiteTrendStore, None, None]:
    """Fixture providing a file-backed SQLiteTrendStore instance in tmp_path."""
    db_file = str(tmp_path / "trends.db")
    store = SQLiteTrendStore(db_file)
    yield store
    store.close()


@pytest.fixture
def garbage_collector(trend_store: SQLiteTrendStore) -> GarbageCollector:
    """Fixture providing GarbageCollector bound to in-memory trend_store."""
    return GarbageCollector(trend_store)


@pytest.fixture
def seeded_store_30_days(trend_store: SQLiteTrendStore) -> SQLiteTrendStore:
    """Fixture providing trend_store pre-seeded with 60 records across 30 days anchored at 2026-08-22."""
    trend_store.seed_30_day_trends(anchor_date="2026-08-22", records_per_day=2, total_days=30)
    return trend_store
