"""
Tests for CuratedMemoryHub and NOOA memory model.
Zero-discretion tests with loud assertions.
"""

import os
import shutil
import tempfile
import pytest
from infrastructure.curated_memory import CuratedMemoryHub, MemoryRecord

@pytest.fixture
def temp_memory_hub():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_memory.db")
    hub = CuratedMemoryHub(db_path)
    yield hub
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

def test_initialization_and_schema(temp_memory_hub):
    hub = temp_memory_hub
    assert os.path.exists(hub.db_path)
    with hub._get_connection() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal_mode.lower() == "wal"
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        assert "curated_memory" in tables

def test_record_and_query(temp_memory_hub):
    hub = temp_memory_hub
    rec_id = hub.record(
        topic="sqlite_storage",
        finding_summary="All databases must live on D: drive.",
        domain_track="platform",
        importance_score=10,
        evidence_source="rules/05_zero_copy_storage.md",
        metadata={"drive": "D:"}
    )
    assert rec_id is not None
    assert len(rec_id) > 0

    record = hub.get_record(rec_id)
    assert record is not None
    assert record.topic == "sqlite_storage"
    assert record.importance_score == 10
    assert record.status == "active"

    results = hub.query(topic="sqlite")
    assert len(results) == 1
    assert results[0].id == rec_id

def test_relationship_and_supersede(temp_memory_hub):
    hub = temp_memory_hub
    old_id = hub.record(
        topic="audio_dsp",
        finding_summary="Audio normalized to -16 LUFS.",
        importance_score=5
    )
    new_id = hub.record(
        topic="audio_dsp",
        finding_summary="Audio normalized to -14 LUFS per EBU R128.",
        importance_score=9,
        relationship_type="replaces",
        related_id=old_id
    )

    old_rec = hub.get_record(old_id)
    new_rec = hub.get_record(new_id)

    assert old_rec.status == "superseded"
    assert new_rec.status == "active"
    assert new_rec.related_id == old_id

def test_pruning_and_dossier(temp_memory_hub):
    hub = temp_memory_hub
    r1 = hub.record(
        topic="card_schema",
        finding_summary="21-variable schema integrity.",
        domain_track="sports_cards",
        importance_score=8
    )
    hub.record(
        topic="ffmpeg_filters",
        finding_summary="80Hz high-pass filter.",
        domain_track="content_creation",
        importance_score=7
    )

    cards_dossier = hub.get_dossier("sports_cards")
    assert "21-variable schema integrity" in cards_dossier
    assert "80Hz high-pass filter" not in cards_dossier

    hub.deprecate(r1)
    dep_rec = hub.get_record(r1)
    assert dep_rec.status == "deprecated"
    assert "21-variable" not in hub.get_dossier("sports_cards")
