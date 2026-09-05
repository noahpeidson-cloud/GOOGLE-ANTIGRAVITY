"""
Adversarial Empirical Challenge Test Suite for Extracted Notebook Data.
Authored by teamwork_preview_challenger.
Tests live file: extracted_notebook_data.json
"""

import json
import uuid
from pathlib import Path
import pytest
from schemas import NotebookExtractionPayload

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
PAYLOAD_PATH = PROJECT_ROOT / "extracted_notebook_data.json"
EXPECTED_NOTEBOOK_ID = "4b52cc67-9f81-4e85-a024-5f06756991ab"
EXPECTED_NOTEBOOK_TITLE = "Dual-Loop Control and Agentic Orchestration in Cognitive Architectures"
EXPECTED_SOURCE_COUNT = 61
EXPECTED_NOTE_COUNT = 1
EXPECTED_NOTE_ID = "eff2cf19-844e-4af7-aad8-601d7d0fbf13"
EXPECTED_NOTE_TITLE = "The Multi-Model Orchestration and AI Handoff Framework"


@pytest.fixture(scope="module")
def raw_data():
    """Load raw JSON from extracted_notebook_data.json."""
    assert PAYLOAD_PATH.exists(), f"LOUD FAILURE: {PAYLOAD_PATH} does not exist!"
    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def payload(raw_data):
    """Parse payload with Pydantic NotebookExtractionPayload schema."""
    return NotebookExtractionPayload.model_validate(raw_data)


def test_file_integrity_and_size():
    """Verify that the JSON payload file exists and is substantial in size (>1MB)."""
    assert PAYLOAD_PATH.exists(), f"File missing: {PAYLOAD_PATH}"
    size = PAYLOAD_PATH.stat().st_size
    assert size > 1_000_000, f"File size too small: {size} bytes (expected >1MB)"


def test_pydantic_schema_validation(payload):
    """Verify payload validates 100% cleanly against NotebookExtractionPayload."""
    assert isinstance(payload, NotebookExtractionPayload)
    assert payload.schema_version == "1.0.0"


def test_notebook_metadata(payload):
    """Verify notebook metadata fields match target notebook specifications."""
    assert payload.metadata.id == EXPECTED_NOTEBOOK_ID
    assert payload.metadata.title == EXPECTED_NOTEBOOK_TITLE
    assert payload.metadata.source_count == EXPECTED_SOURCE_COUNT
    assert payload.metadata.url.startswith("https://notebooklm.google.com/notebook/")


def test_provenance_audit(payload):
    """Verify execution provenance reflects complete, non-dry-run extraction."""
    prov = payload.provenance
    assert prov.is_dry_run is False
    assert prov.limit_applied is None
    assert prov.total_sources == EXPECTED_SOURCE_COUNT
    assert prov.successful_sources == EXPECTED_SOURCE_COUNT
    assert prov.failed_sources == 0
    assert prov.total_notes == EXPECTED_NOTE_COUNT
    assert prov.transport in ["direct", "mcp"]
    assert prov.duration_seconds is not None and prov.duration_seconds > 0


def test_exact_61_sources(payload):
    """Verify that exactly 61 sources are present in the sources array."""
    assert len(payload.sources) == EXPECTED_SOURCE_COUNT, (
        f"Expected exactly {EXPECTED_SOURCE_COUNT} sources, found {len(payload.sources)}"
    )


def test_exact_1_note(payload):
    """Verify that exactly 1 note is present in the notes array."""
    assert len(payload.notes) == EXPECTED_NOTE_COUNT, (
        f"Expected exactly {EXPECTED_NOTE_COUNT} note, found {len(payload.notes)}"
    )
    note = payload.notes[0]
    assert note.id == EXPECTED_NOTE_ID
    assert note.title == EXPECTED_NOTE_TITLE
    assert len(note.content.strip()) > 1000, "Note content unexpectedly truncated"


def test_100_percent_non_empty_content_sources(payload):
    """Verify that 100% of the 61 sources have non-empty, substantive text content."""
    empty_sources = []
    failed_sources = []
    for idx, src in enumerate(payload.sources, 1):
        if src.status != "success":
            failed_sources.append((idx, src.id, src.title, src.error))
        if not src.content or len(src.content.strip()) == 0:
            empty_sources.append((idx, src.id, src.title))

    assert len(failed_sources) == 0, f"Found failed sources: {failed_sources}"
    assert len(empty_sources) == 0, f"Found empty content sources: {empty_sources}"


def test_100_percent_char_count_matches_actual_string_length(payload):
    """Verify that for 100% of sources, char_count matches actual len(content)."""
    mismatches = []
    for idx, src in enumerate(payload.sources, 1):
        actual_len = len(src.content) if src.content else 0
        if src.char_count != actual_len:
            mismatches.append(
                f"Source #{idx} ({src.id}): char_count={src.char_count} vs len(content)={actual_len}"
            )

    assert len(mismatches) == 0, f"Character count mismatches detected:\n" + "\n".join(mismatches)


def test_source_ids_are_unique_uuids(payload):
    """Verify all 61 source IDs are valid UUIDs and unique with zero collisions."""
    source_ids = [s.id for s in payload.sources]
    assert len(source_ids) == len(set(source_ids)), "Duplicate source IDs detected!"

    for sid in source_ids:
        parsed = uuid.UUID(sid)
        assert str(parsed) == sid, f"Invalid UUID format: {sid}"


def test_boundary_sources_content_and_titles(payload):
    """Verify first, middle, and last sources have expected titles and content signatures."""
    first = payload.sources[0]
    assert "11 Top Open-Source LLMs for 2026" in first.title
    assert "Open-Source LLMs" in first.content
    assert first.char_count > 10_000

    last = payload.sources[-1]
    assert "What is an AI Agent Harness?" in last.title
    assert "Harness" in last.content
    assert last.char_count > 10_000


def test_total_text_volume(payload):
    """Verify aggregate character count across all 61 sources exceeds 500,000 characters."""
    total_chars = sum(len(s.content) for s in payload.sources)
    assert total_chars > 500_000, f"Total text volume ({total_chars}) is below 500,000 chars"
