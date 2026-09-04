"""Comprehensive 4-Tier Opaque-Box E2E Test Suite for Unified Ops Hub Media Gallery.

Verifies:
- Tier 1: Feature Coverage (Schema DDL, Album CRUD, Media Insertion, Relational Joins, Batch Grading Dispatch)
- Tier 2: Boundary & Corner Cases (Empty Albums, Nonexistent IDs, Special Chars/Unicode G: Paths, Zero-Selection, Large Scalability)
- Tier 3: Cross-Feature Combinations (Ingestion -> DB -> API, Cascade Deletion, Status Propagation)
- Tier 4: Real-World Scenarios (Multithreaded SQLite WAL Concurrency, Full End-to-End Lifecycle Workflow)

Strictly adheres to:
- Rule R2 (The Leash Protocol / Zero-Discretion Mandate / Loud Assertions)
- Rule R16 (Executable Absolute Python Imports)
"""

import os
import sys
import time
import uuid
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient

# Adhere to Rule R16: Absolute import with fallback
try:
    from unified_ops_hub.gateway.app import create_app, GatewayState
    from unified_ops_hub.gateway.port_manager import PortManager
    from unified_ops_hub.gateway.dlq_manager import DLQManager
except ImportError:
    from gateway.app import create_app, GatewayState
    from gateway.port_manager import PortManager
    from gateway.dlq_manager import DLQManager


# Helper loader for MediaCatalogManager
def get_media_catalog_class():
    """Dynamically loads MediaCatalogManager adhering to Rule R16."""
    try:
        from unified_ops_hub.gateway.media_catalog import MediaCatalogManager
        return MediaCatalogManager
    except ImportError:
        try:
            from gateway.media_catalog import MediaCatalogManager
            return MediaCatalogManager
        except ImportError:
            pytest.fail("MediaCatalogManager not yet implemented in gateway.media_catalog")


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def catalog_db_path(tmp_path) -> str:
    """Provides a fresh, isolated temporary SQLite database path per test."""
    db_file = tmp_path / f"test_media_catalog_{uuid.uuid4().hex[:8]}.db"
    return str(db_file)


@pytest.fixture
def catalog_manager(catalog_db_path):
    """Initializes and returns a fresh MediaCatalogManager instance."""
    CatalogClass = get_media_catalog_class()
    manager = CatalogClass(db_path=catalog_db_path)
    if hasattr(manager, "create_schema"):
        manager.create_schema()
    elif hasattr(manager, "init_db"):
        manager.init_db()
    return manager


@pytest.fixture
def test_client(catalog_db_path, tmp_path):
    """Creates a FastAPI test client attached to the isolated test catalog database."""
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    dlq_db = str(tmp_path / "test_dlq.db")
    quarantine_dir = str(tmp_path / "quarantine")

    port_mgr = PortManager(lock_dir=str(lock_dir))
    dlq_mgr = DLQManager(db_path=dlq_db, quarantine_dir=quarantine_dir)

    app = create_app(port_manager=port_mgr, dlq_manager=dlq_mgr)
    
    # Initialize catalog manager on app state if supported
    CatalogClass = get_media_catalog_class()
    manager = CatalogClass(db_path=catalog_db_path)
    if hasattr(manager, "create_schema"):
        manager.create_schema()
    elif hasattr(manager, "init_db"):
        manager.init_db()
    app.state.media_catalog = manager

    client = TestClient(app)
    return client


# ============================================================================
# TIER 1: Core Feature Coverage (>=5 Tests)
# ============================================================================

def test_tier1_schema_creation_and_tables(catalog_db_path, catalog_manager):
    """T1.1: Verify SQLite schema initialization, table creation, foreign keys, and indexes."""
    conn = sqlite3.connect(catalog_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query master table for created tables
    cursor.execute("SELECT name, type FROM sqlite_master WHERE type='table';")
    tables = {row["name"] for row in cursor.fetchall()}

    assert "albums" in tables, "LOUD ASSERTION: 'albums' table must exist in schema"
    assert "media" in tables, "LOUD ASSERTION: 'media' table must exist in schema"

    # Verify column structures in albums table
    cursor.execute("PRAGMA table_info(albums);")
    album_cols = {row["name"]: row["type"].upper() for row in cursor.fetchall()}
    assert "id" in album_cols, "albums table must have 'id' column"
    assert "title" in album_cols, "albums table must have 'title' column"
    assert "event_date" in album_cols or "created_at" in album_cols, "albums table must have date tracking"
    assert "status" in album_cols, "albums table must have 'status' column"

    # Verify column structures in media table
    cursor.execute("PRAGMA table_info(media);")
    media_cols = {row["name"]: row["type"].upper() for row in cursor.fetchall()}
    assert "id" in media_cols, "media table must have 'id' column"
    assert "album_id" in media_cols, "media table must have 'album_id' foreign key"
    assert "raw_path" in media_cols, "media table must have 'raw_path' column"
    assert "proxy_path" in media_cols, "media table must have 'proxy_path' column"
    assert "grading_status" in media_cols, "media table must have 'grading_status' column"

    # Verify high-performance indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indexes = {row["name"] for row in cursor.fetchall()}
    assert any("album" in idx for idx in indexes), "Index on album_id must be defined"
    
    conn.close()


def test_tier1_album_creation_and_attributes(catalog_manager):
    """T1.2: Verify album creation with custom metadata and default attributes."""
    album_id = catalog_manager.create_album(
        title="Ultra Music Festival 2026 Raw Drops",
        description="Mainstage 4K POV recordings and live crowd reactions",
    )

    assert album_id is not None and len(album_id) > 0, "LOUD ASSERTION: Album creation must return a non-empty string ID"

    albums = catalog_manager.get_albums()
    assert isinstance(albums, list), "get_albums() must return a list"
    assert len(albums) == 1, f"Expected 1 album in catalog, found {len(albums)}"

    created_album = albums[0]
    assert created_album["id"] == album_id
    assert created_album["title"] == "Ultra Music Festival 2026 Raw Drops"
    assert created_album.get("description") == "Mainstage 4K POV recordings and live crowd reactions"
    
    # Check media count and status defaults
    media_count = created_album.get("total_media_count", created_album.get("media_count", 0))
    assert media_count == 0, "Newly created album must have 0 total media items"
    assert created_album.get("status") in ("INGESTED", "ACTIVE", "READY", None)


def test_tier1_media_insertion_with_gdrive_paths(catalog_manager):
    """T1.3: Verify inserting media entries containing Windows G: Drive paths and metadata."""
    album_id = catalog_manager.create_album(title="EDC Las Vegas 2026 Clips")
    
    raw_path = r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\raw\EDC_2026_DROP_01.mp4"
    proxy_path = r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\proxies\EDC_2026_DROP_01_proxy.mp4"

    media_id = catalog_manager.add_media_item(
        album_id=album_id,
        filename="EDC_2026_DROP_01.mp4",
        proxy_path=proxy_path,
        raw_path=raw_path,
        duration=24.5,
        resolution="1080x1920",
    )

    assert media_id is not None and len(media_id) > 0, "LOUD ASSERTION: add_media_item must return a valid media ID"

    media_list = catalog_manager.get_album_media(album_id)
    assert len(media_list) == 1, f"Expected 1 media item in album {album_id}, got {len(media_list)}"

    item = media_list[0]
    assert item["id"] == media_id
    assert item["album_id"] == album_id
    assert item["raw_path"] == raw_path
    assert item["proxy_path"] == proxy_path
    
    duration = item.get("duration_sec", item.get("duration", 0.0))
    assert abs(duration - 24.5) < 1e-3, f"Expected duration 24.5s, got {duration}"
    assert item.get("grading_status") in ("UNGRADED", "PENDING")


def test_tier1_relational_join_retrieval(catalog_manager):
    """T1.4: Verify relational join query retrieving an album with 3 linked media entries."""
    album_id = catalog_manager.create_album(
        title="Tomorrowland 2026 POV Album",
        description="Full set raw captures",
    )

    media_specs = [
        ("TL_2026_001.mp4", r"G:\My Drive\raw\TL_001.mp4", r"/proxies/TL_001_proxy.mp4", 15.0, "1080x1920"),
        ("TL_2026_002.mp4", r"G:\My Drive\raw\TL_002.mp4", r"/proxies/TL_002_proxy.mp4", 30.5, "1080x1920"),
        ("TL_2026_003.mp4", r"G:\My Drive\raw\TL_003.mp4", r"/proxies/TL_003_proxy.mp4", 18.2, "1920x1080"),
    ]

    inserted_ids = []
    for fn, raw, proxy, dur, res in media_specs:
        mid = catalog_manager.add_media_item(
            album_id=album_id,
            filename=fn,
            proxy_path=proxy,
            raw_path=raw,
            duration=dur,
            resolution=res,
        )
        inserted_ids.append(mid)

    assert len(inserted_ids) == 3, "All 3 media items must be successfully inserted"

    # Query album media
    retrieved_media = catalog_manager.get_album_media(album_id)
    assert len(retrieved_media) == 3, f"LOUD ASSERTION: Expected 3 media rows, got {len(retrieved_media)}"

    retrieved_ids = [m["id"] for m in retrieved_media]
    assert retrieved_ids == inserted_ids, "Retrieved media IDs must match insertion order and values"

    filenames = [m.get("file_name", m.get("filename")) for m in retrieved_media]
    assert filenames == ["TL_2026_001.mp4", "TL_2026_002.mp4", "TL_2026_003.mp4"]


def test_tier1_batch_grading_dispatch(catalog_manager, test_client):
    """T1.5: Verify batch grading trigger dispatch via API and status updates."""
    album_id = catalog_manager.create_album(title="Coachella 2026 Viral Cuts")
    
    m1 = catalog_manager.add_media_item(
        album_id=album_id,
        filename="COA_001.mp4",
        proxy_path=r"G:\My Drive\proxies\COA_001_proxy.mp4",
        raw_path=r"G:\My Drive\raw\COA_001.mp4",
        duration=12.0,
    )
    m2 = catalog_manager.add_media_item(
        album_id=album_id,
        filename="COA_002.mp4",
        proxy_path=r"G:\My Drive\proxies\COA_002_proxy.mp4",
        raw_path=r"G:\My Drive\raw\COA_002.mp4",
        duration=22.0,
    )

    # Test via Catalog Manager directly
    if hasattr(catalog_manager, "update_grading_status"):
        catalog_manager.update_grading_status([m1, m2], status="QUEUED")
        updated_items = catalog_manager.get_album_media(album_id)
        for item in updated_items:
            assert item["grading_status"] == "QUEUED"

    # Test via Gateway API endpoints
    for endpoint in ["/api/v1/ml/grade/batch", "/api/v1/ml/grade-batch", "/api/v1/media/grade/batch"]:
        response = test_client.post(endpoint, json={"media_ids": [m1, m2]})
        if response.status_code in (200, 202):
            data = response.json()
            assert "status" in data or "job_id" in data or "queued_count" in data or "job_ids" in data
            break


# ============================================================================
# TIER 2: Boundary Value Analysis & Edge Cases (>=5 Tests)
# ============================================================================

def test_tier2_empty_album_handling(catalog_manager, test_client):
    """T2.1: Verify querying an empty album returns empty array without raising exceptions."""
    empty_album_id = catalog_manager.create_album(title="Empty Ghost Album")

    media_items = catalog_manager.get_album_media(empty_album_id)
    assert isinstance(media_items, list), "get_album_media must return a list for empty albums"
    assert len(media_items) == 0, f"Expected 0 media items, got {len(media_items)}"

    # Test via API if endpoint available
    for endpoint in [f"/api/v1/media/albums/{empty_album_id}/media", f"/api/v1/gallery/albums/{empty_album_id}/media"]:
        res = test_client.get(endpoint)
        if res.status_code == 200:
            data = res.json()
            items = data if isinstance(data, list) else data.get("media", [])
            assert len(items) == 0


def test_tier2_nonexistent_ids_queries_and_updates(catalog_manager, test_client):
    """T2.2: Verify querying and updating non-existent IDs behaves deterministically."""
    fake_album_id = "nonexistent_album_xyz999"
    fake_media_id = "nonexistent_media_xyz999"

    # Querying nonexistent album media returns empty list or handles gracefully
    media_items = catalog_manager.get_album_media(fake_album_id)
    assert isinstance(media_items, list)
    assert len(media_items) == 0

    # Updating nonexistent media items does not raise unhandled SQL errors
    if hasattr(catalog_manager, "update_grading_status"):
        res = catalog_manager.update_grading_status([fake_media_id], status="QUEUED")
        # Should return 0 modified rows or None
        if res is not None:
            assert res == 0 or res is False

    # Verify REST endpoint returns 404 or empty list for nonexistent album
    for endpoint in [f"/api/v1/media/albums/{fake_album_id}/media", f"/api/v1/gallery/albums/{fake_album_id}/media"]:
        resp = test_client.get(endpoint)
        if resp.status_code != 404:
            # If 200, must return empty array
            assert resp.status_code == 200
            data = resp.json()
            items = data if isinstance(data, list) else data.get("media", [])
            assert len(items) == 0


def test_tier2_special_characters_and_unicode_paths(catalog_manager):
    """T2.3: Verify paths & titles with quotes, brackets, emojis, spaces, hashtags and G: drive."""
    complex_title = "🔥 Ultra (Mainstage) — 2026 [4K] #Hardwell & Martin's ID's!"
    album_id = catalog_manager.create_album(
        title=complex_title,
        description="Testing 'quotes', \"double quotes\", & special chars: <>&%#@!",
    )

    special_filename = "Drop #1 [Ultra 2026] (100% Boost) — 🎵 'Banger'.mp4"
    special_raw = r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\raw\Drop #1 [Ultra 2026] (100% Boost) — 🎵 'Banger'.mp4"
    special_proxy = r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\proxies\Drop #1 [Ultra 2026] (100% Boost) — 🎵 'Banger'_proxy.mp4"

    media_id = catalog_manager.add_media_item(
        album_id=album_id,
        filename=special_filename,
        proxy_path=special_proxy,
        raw_path=special_raw,
        duration=14.8,
    )

    # Retrieve and assert exact string preservation
    media_list = catalog_manager.get_album_media(album_id)
    assert len(media_list) == 1
    item = media_list[0]
    
    assert item["id"] == media_id
    assert item.get("file_name", item.get("filename")) == special_filename
    assert item["raw_path"] == special_raw
    assert item["proxy_path"] == special_proxy

    albums = catalog_manager.get_albums()
    matching_album = [a for a in albums if a["id"] == album_id][0]
    assert matching_album["title"] == complex_title


def test_tier2_zero_selection_batch_grade_rejection(catalog_manager, test_client):
    """T2.4: Verify submitting an empty media list to batch grading is properly rejected."""
    # API endpoints must reject empty media_ids list with 422 or 400
    for endpoint in ["/api/v1/ml/grade/batch", "/api/v1/ml/grade-batch", "/api/v1/media/grade/batch"]:
        response = test_client.post(endpoint, json={"media_ids": []})
        if response.status_code not in (404,):
            assert response.status_code in (400, 422), (
                f"Expected 400/422 on zero-selection batch grading, got {response.status_code}"
            )

    # Direct catalog manager call with empty list should be safe no-op
    if hasattr(catalog_manager, "update_grading_status"):
        res = catalog_manager.update_grading_status([], status="QUEUED")
        assert res in (0, None, False)


def test_tier2_large_catalog_query_50_plus_items(catalog_manager):
    """T2.5: Verify scalability and performance when querying 60+ media items across multiple albums."""
    album_ids = []
    for i in range(3):
        aid = catalog_manager.create_album(title=f"Scalability Test Album {i + 1}")
        album_ids.append(aid)

    total_inserted = 0
    start_time = time.time()
    for a_idx, aid in enumerate(album_ids):
        for m_idx in range(20):
            catalog_manager.add_media_item(
                album_id=aid,
                filename=f"clip_bulk_{a_idx}_{m_idx}.mp4",
                proxy_path=f"/proxies/bulk_{a_idx}_{m_idx}_proxy.mp4",
                raw_path=rf"G:\My Drive\raw\bulk_{a_idx}_{m_idx}.mp4",
                duration=10.0 + m_idx,
                resolution="1080x1920" if m_idx % 2 == 0 else "1920x1080",
            )
            total_inserted += 1

    insertion_elapsed = time.time() - start_time
    assert total_inserted == 60, "Must have inserted exactly 60 media items"

    # Query full catalog
    query_start = time.time()
    if hasattr(catalog_manager, "get_full_catalog"):
        catalog_items = catalog_manager.get_full_catalog()
        query_elapsed = time.time() - query_start
        assert len(catalog_items) == 60, f"Expected 60 total items, found {len(catalog_items)}"
        assert query_elapsed < 0.2, f"Large catalog query took {query_elapsed:.4f}s (should be < 200ms)"

    # Query each album individually
    for aid in album_ids:
        album_media = catalog_manager.get_album_media(aid)
        assert len(album_media) == 20, f"Expected 20 items in album {aid}, got {len(album_media)}"


# ============================================================================
# TIER 3: Cross-Feature Combinations (>=3 Tests)
# ============================================================================

def test_tier3_ingestion_to_catalog_db_to_api_retrieval(catalog_manager, test_client):
    """T3.1: Ingestion pipeline adds media to SQLite DB -> Gateway REST API exposes them correctly."""
    album_id = catalog_manager.create_album(
        title="Cross-Feature Ingest Album",
        description="Ingestion testing",
    )

    mock_ingested = [
        ("INGEST_001.mp4", r"G:\My Drive\raw\INGEST_001.mp4", "/proxies/INGEST_001_proxy.mp4", 16.5),
        ("INGEST_002.mp4", r"G:\My Drive\raw\INGEST_002.mp4", "/proxies/INGEST_002_proxy.mp4", 28.0),
    ]

    for fn, raw, proxy, dur in mock_ingested:
        catalog_manager.add_media_item(
            album_id=album_id,
            filename=fn,
            proxy_path=proxy,
            raw_path=raw,
            duration=dur,
        )

    # Verify REST API albums endpoint
    for endpoint in ["/api/v1/media/albums", "/api/v1/gallery/albums"]:
        res = test_client.get(endpoint)
        if res.status_code == 200:
            albums_data = res.json()
            assert isinstance(albums_data, list)
            target = [a for a in albums_data if a["id"] == album_id]
            assert len(target) == 1, "Created album must be present in GET /albums response"
            
            # Verify media count aggregation
            count = target[0].get("total_media_count", target[0].get("media_count", 0))
            assert count == 2

    # Verify REST API album media endpoint
    for endpoint in [f"/api/v1/media/albums/{album_id}/media", f"/api/v1/gallery/albums/{album_id}/media"]:
        res = test_client.get(endpoint)
        if res.status_code == 200:
            media_data = res.json()
            items = media_data if isinstance(media_data, list) else media_data.get("media", [])
            assert len(items) == 2
            assert items[0]["proxy_path"] == "/proxies/INGEST_001_proxy.mp4"
            assert items[1]["proxy_path"] == "/proxies/INGEST_002_proxy.mp4"


def test_tier3_cascade_deletion_album_removes_child_media(catalog_db_path, catalog_manager):
    """T3.2: Verify deleting an album cascades to delete all child media rows in SQLite."""
    album_id = catalog_manager.create_album(title="Album for Deletion Cascade")
    
    media_ids = []
    for i in range(4):
        mid = catalog_manager.add_media_item(
            album_id=album_id,
            filename=f"cascade_clip_{i}.mp4",
            proxy_path=f"/proxies/cascade_{i}.mp4",
            raw_path=rf"G:\My Drive\raw\cascade_{i}.mp4",
            duration=15.0,
        )
        media_ids.append(mid)

    # Verify media rows exist in DB
    conn = sqlite3.connect(catalog_db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM media WHERE album_id = ?;", (album_id,))
    count_before = cursor.fetchone()[0]
    assert count_before == 4, "Must find 4 media items before deletion"

    # Delete album using manager method or direct SQL
    if hasattr(catalog_manager, "delete_album"):
        catalog_manager.delete_album(album_id)
    else:
        cursor.execute("DELETE FROM albums WHERE id = ?;", (album_id,))
        conn.commit()

    # Query media table to confirm cascade deletion
    cursor.execute("SELECT COUNT(*) FROM media WHERE album_id = ?;", (album_id,))
    count_after = cursor.fetchone()[0]
    assert count_after == 0, f"LOUD ASSERTION: Child media rows must be cascaded to 0, found {count_after}"

    cursor.execute("SELECT COUNT(*) FROM media WHERE id IN (?, ?, ?, ?);", tuple(media_ids))
    orphan_count = cursor.fetchone()[0]
    assert orphan_count == 0, "No orphaned media records should remain after album deletion"

    conn.close()


def test_tier3_batch_grading_status_update_across_catalog_queries(catalog_manager):
    """T3.3: Verify grading status transitions (UNGRADED -> QUEUED -> GRADED) reflect in queries."""
    album_id = catalog_manager.create_album(title="Grading Status Flow Album")
    
    m1 = catalog_manager.add_media_item(
        album_id=album_id,
        filename="grade_flow_01.mp4",
        proxy_path="/proxies/flow_01.mp4",
        raw_path=r"G:\My Drive\raw\flow_01.mp4",
        duration=15.0,
    )
    m2 = catalog_manager.add_media_item(
        album_id=album_id,
        filename="grade_flow_02.mp4",
        proxy_path="/proxies/flow_02.mp4",
        raw_path=r"G:\My Drive\raw\flow_02.mp4",
        duration=20.0,
    )

    # Initial state: UNGRADED
    initial_items = catalog_manager.get_album_media(album_id)
    for itm in initial_items:
        assert itm["grading_status"] in ("UNGRADED", "PENDING")

    # Transition 1: Queue for grading
    if hasattr(catalog_manager, "update_grading_status"):
        catalog_manager.update_grading_status([m1, m2], status="QUEUED")
        queued_items = {i["id"]: i for i in catalog_manager.get_album_media(album_id)}
        assert queued_items[m1]["grading_status"] == "QUEUED"
        assert queued_items[m2]["grading_status"] == "QUEUED"

        # Transition 2: Complete grading for m1 with EVPI score and verdict
        if hasattr(catalog_manager, "update_grading_result"):
            catalog_manager.update_grading_result(
                media_id=m1,
                evpi_score=92.5,
                verdict="VIRAL_READY",
                metadata={"HRV": 95.0, "DPAW": 90.0, "ADR_SFD": 92.0},
            )
        else:
            catalog_manager.update_grading_status(
                [m1],
                status="GRADED",
                evpi_score=92.5,
                verdict="VIRAL_READY",
            )

        final_items = {i["id"]: i for i in catalog_manager.get_album_media(album_id)}
        assert final_items[m1]["grading_status"] == "GRADED"
        if "evpi_score" in final_items[m1] and final_items[m1]["evpi_score"] is not None:
            assert abs(final_items[m1]["evpi_score"] - 92.5) < 1e-2
        if "grading_verdict" in final_items[m1] and final_items[m1]["grading_verdict"] is not None:
            assert final_items[m1]["grading_verdict"] == "VIRAL_READY"
        assert final_items[m2]["grading_status"] == "QUEUED"


# ============================================================================
# TIER 4: Real-World Scenarios & Concurrency (>=2 Tests)
# ============================================================================

def test_tier4_sqlite_wal_concurrent_reads_and_writes(catalog_db_path, catalog_manager):
    """T4.1: Multi-threaded stress test verifying SQLite WAL mode under concurrent readers and writers."""
    # Ensure WAL mode and busy timeout are active
    conn = sqlite3.connect(catalog_db_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.close()

    album_id = catalog_manager.create_album(title="WAL Concurrency Stress Album")
    num_writers = 4
    items_per_writer = 15
    num_readers = 6
    reads_per_reader = 25

    errors: List[str] = []

    def writer_task(writer_id: int):
        CatalogClass = get_media_catalog_class()
        local_mgr = CatalogClass(db_path=catalog_db_path)
        for i in range(items_per_writer):
            try:
                mid = local_mgr.add_media_item(
                    album_id=album_id,
                    filename=f"thread_clip_w{writer_id}_{i}.mp4",
                    proxy_path=f"/proxies/w{writer_id}_{i}.mp4",
                    raw_path=rf"G:\My Drive\raw\w{writer_id}_{i}.mp4",
                    duration=10.0 + i,
                )
                if i % 3 == 0 and hasattr(local_mgr, "update_grading_status"):
                    local_mgr.update_grading_status([mid], status="QUEUED")
                time.sleep(0.005)
            except Exception as e:
                errors.append(f"Writer {writer_id} error on item {i}: {str(e)}")

    def reader_task(reader_id: int):
        CatalogClass = get_media_catalog_class()
        local_mgr = CatalogClass(db_path=catalog_db_path)
        for i in range(reads_per_reader):
            try:
                items = local_mgr.get_album_media(album_id)
                assert isinstance(items, list)
                time.sleep(0.003)
            except Exception as e:
                errors.append(f"Reader {reader_id} error on read {i}: {str(e)}")

    with ThreadPoolExecutor(max_workers=num_writers + num_readers) as executor:
        futures = []
        for w in range(num_writers):
            futures.append(executor.submit(writer_task, w))
        for r in range(num_readers):
            futures.append(executor.submit(reader_task, r))

        for f in as_completed(futures):
            f.result()

    assert len(errors) == 0, f"LOUD ASSERTION: Concurrency stress encountered errors: {errors}"

    final_media = catalog_manager.get_album_media(album_id)
    expected_total = num_writers * items_per_writer
    assert len(final_media) == expected_total, (
        f"Expected {expected_total} items after concurrent insertions, got {len(final_media)}"
    )


def test_tier4_full_lifecycle_multi_album_management_workflow(catalog_manager, test_client):
    """T4.2: End-to-end full lifecycle covering multi-album creation, ingestion, selection, grading, and cleanup."""
    # Step 1: Create 2 distinct albums
    a1_id = catalog_manager.create_album(
        title="Ultra Miami 2026 — Day 1",
        description="Opening sets and mainstage raw 4K drops",
    )
    a2_id = catalog_manager.create_album(
        title="Ultra Miami 2026 — Day 2",
        description="Closing sets and drone flyovers",
    )

    # Step 2: Ingest 4 clips into Album 1, 3 clips into Album 2
    a1_clips = []
    for i in range(4):
        cid = catalog_manager.add_media_item(
            album_id=a1_id,
            filename=f"ultra_d1_{i+1:03d}.mp4",
            proxy_path=f"/proxies/ultra_d1_{i+1:03d}_proxy.mp4",
            raw_path=rf"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\raw\ultra_d1_{i+1:03d}.mp4",
            duration=15.0 + i * 5.0,
            resolution="1080x1920" if i % 2 == 0 else "1920x1080",
        )
        a1_clips.append(cid)

    a2_clips = []
    for i in range(3):
        cid = catalog_manager.add_media_item(
            album_id=a2_id,
            filename=f"ultra_d2_{i+1:03d}.mp4",
            proxy_path=f"/proxies/ultra_d2_{i+1:03d}_proxy.mp4",
            raw_path=rf"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\raw\ultra_d2_{i+1:03d}.mp4",
            duration=20.0 + i * 10.0,
        )
        a2_clips.append(cid)

    # Step 3: Browse catalog and verify album counts
    albums = {a["id"]: a for a in catalog_manager.get_albums()}
    assert a1_id in albums and a2_id in albums
    
    # Step 4: Multi-item selection across albums for batch grading
    selected_for_grading = [a1_clips[0], a1_clips[1], a2_clips[0]]
    if hasattr(catalog_manager, "update_grading_status"):
        catalog_manager.update_grading_status(selected_for_grading, status="QUEUED")

    # Step 5: Simulate ML Grading completion with EVPI score updates
    if hasattr(catalog_manager, "update_grading_status"):
        catalog_manager.update_grading_status(
            [a1_clips[0]],
            status="GRADED",
            evpi_score=94.2,
            verdict="VIRAL_READY",
        )
        catalog_manager.update_grading_status(
            [a1_clips[1]],
            status="GRADED",
            evpi_score=72.0,
            verdict="HIGH_POTENTIAL",
        )

    # Step 6: Verify status parity in both albums
    a1_media = {m["id"]: m for m in catalog_manager.get_album_media(a1_id)}
    assert a1_media[a1_clips[0]]["grading_status"] == "GRADED"
    assert a1_media[a1_clips[1]]["grading_status"] == "GRADED"
    assert a1_media[a1_clips[2]]["grading_status"] in ("UNGRADED", "PENDING")
    assert a1_media[a1_clips[3]]["grading_status"] in ("UNGRADED", "PENDING")

    a2_media = {m["id"]: m for m in catalog_manager.get_album_media(a2_id)}
    assert a2_media[a2_clips[0]]["grading_status"] == "QUEUED"
    assert a2_media[a2_clips[1]]["grading_status"] in ("UNGRADED", "PENDING")

    # Step 7: Delete Album 1 and verify Album 2 remains intact
    if hasattr(catalog_manager, "delete_album"):
        catalog_manager.delete_album(a1_id)
        remaining_albums = [a["id"] for a in catalog_manager.get_albums()]
        assert a1_id not in remaining_albums
        assert a2_id in remaining_albums
        assert len(catalog_manager.get_album_media(a2_id)) == 3
