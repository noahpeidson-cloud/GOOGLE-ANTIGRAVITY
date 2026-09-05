"""
Unit tests for schemas.py adhering to R2 Zero-Discretion Mandate.
Tests Pydantic v2 data models, serialization, and edge cases with loud assertions.
"""

import json
import pytest
from pydantic import ValidationError

from schemas import (
    NotebookMetadata,
    ExtractedSource,
    ExtractedNote,
    ExtractionProvenance,
    NotebookExtractionPayload,
)


@pytest.mark.unit
def test_notebook_metadata_valid():
    """Verify NotebookMetadata instantiation with valid fields."""
    meta = NotebookMetadata(
        id="4b52cc67-9f81-4e85-a024-5f06756991ab",
        title="Dual-Loop Control and Agentic Orchestration in Cognitive Architectures",
        url="https://notebooklm.google.com/notebook/4b52cc67-9f81-4e85-a024-5f06756991ab",
        source_count=61,
        emoji="⚓",
    )
    assert meta.id == "4b52cc67-9f81-4e85-a024-5f06756991ab", f"LOUD FAILURE: id mismatch: {meta.id}"
    assert meta.source_count == 61, f"LOUD FAILURE: source_count mismatch: {meta.source_count}"
    assert meta.emoji == "⚓", f"LOUD FAILURE: emoji mismatch: {meta.emoji}"


@pytest.mark.unit
def test_notebook_metadata_missing_required():
    """Verify ValidationError is raised when required fields are missing."""
    with pytest.raises(ValidationError) as exc_info:
        NotebookMetadata(id="123", title="Missing other fields")  # type: ignore
    errors = exc_info.value.errors()
    missing_fields = {e["loc"][0] for e in errors}
    assert "url" in missing_fields, f"LOUD FAILURE: 'url' should be required: {missing_fields}"
    assert "source_count" in missing_fields, f"LOUD FAILURE: 'source_count' should be required: {missing_fields}"


@pytest.mark.unit
def test_extracted_source_defaults_and_types(sample_valid_source_dict):
    """Verify ExtractedSource defaults and strict field assignments."""
    source = ExtractedSource(**sample_valid_source_dict)
    assert source.id == sample_valid_source_dict["id"], "LOUD FAILURE: id mismatch"
    assert source.char_count == 51151, "LOUD FAILURE: char_count mismatch"
    assert source.status == "success", "LOUD FAILURE: status default mismatch"
    assert source.error is None, "LOUD FAILURE: error should be None"

    # Verify optional content allowed
    source_no_content = ExtractedSource(id="src-1", title="Title Only")
    assert source_no_content.content is None, "LOUD FAILURE: content should default to None"
    assert source_no_content.source_type == "unknown", "LOUD FAILURE: source_type default mismatch"
    assert source_no_content.char_count == 0, "LOUD FAILURE: char_count default should be 0"


@pytest.mark.unit
def test_extracted_source_error_state():
    """Verify ExtractedSource correctly models an extraction failure."""
    source = ExtractedSource(
        id="src-failed",
        title="Failed Article",
        status="failed",
        error="HTTP 429: Too Many Requests",
        content=None,
        char_count=0,
    )
    assert source.status == "failed", f"LOUD FAILURE: status should be 'failed', got {source.status}"
    assert source.error == "HTTP 429: Too Many Requests", f"LOUD FAILURE: error mismatch: {source.error}"
    assert source.content is None, "LOUD FAILURE: content should be None on failure"


@pytest.mark.unit
def test_extracted_note_validation(sample_valid_note_dict):
    """Verify ExtractedNote fields and validation."""
    note = ExtractedNote(**sample_valid_note_dict)
    assert note.id == sample_valid_note_dict["id"], "LOUD FAILURE: note id mismatch"
    assert note.title == sample_valid_note_dict["title"], "LOUD FAILURE: note title mismatch"
    assert len(note.content) > 50, "LOUD FAILURE: note content unexpectedly short"
    assert note.preview is not None, "LOUD FAILURE: note preview should not be None"


@pytest.mark.unit
def test_extraction_provenance_validation():
    """Verify ExtractionProvenance models dry-run vs full run correctly."""
    # Dry run provenance
    dry_prov = ExtractionProvenance(
        transport="mcp",
        total_sources=2,
        total_notes=1,
        is_dry_run=True,
        limit_applied=2,
    )
    assert dry_prov.is_dry_run is True, "LOUD FAILURE: is_dry_run should be True"
    assert dry_prov.limit_applied == 2, f"LOUD FAILURE: limit_applied mismatch: {dry_prov.limit_applied}"
    assert dry_prov.transport == "mcp", "LOUD FAILURE: transport mismatch"
    assert dry_prov.extractor_version == "1.0.0", "LOUD FAILURE: version mismatch"

    # Full run provenance
    full_prov = ExtractionProvenance(
        transport="direct",
        total_sources=61,
        total_notes=1,
        is_dry_run=False,
        limit_applied=None,
    )
    assert full_prov.is_dry_run is False, "LOUD FAILURE: is_dry_run should be False"
    assert full_prov.limit_applied is None, "LOUD FAILURE: limit_applied should be None"


@pytest.mark.unit
def test_notebook_extraction_payload_roundtrip(sample_valid_source_dict, sample_valid_note_dict):
    """Verify full NotebookExtractionPayload JSON serialization and deserialization roundtrip."""
    meta = NotebookMetadata(
        id="4b52cc67-9f81-4e85-a024-5f06756991ab",
        title="Dual-Loop Control and Agentic Orchestration in Cognitive Architectures",
        url="https://notebooklm.google.com/notebook/4b52cc67-9f81-4e85-a024-5f06756991ab",
        source_count=1,
        emoji="⚓",
    )
    src = ExtractedSource(**sample_valid_source_dict)
    note = ExtractedNote(**sample_valid_note_dict)
    prov = ExtractionProvenance(
        transport="mcp",
        total_sources=1,
        total_notes=1,
        is_dry_run=True,
        limit_applied=1,
    )

    payload = NotebookExtractionPayload(
        schema_version="1.0.0",
        metadata=meta,
        sources=[src],
        notes=[note],
        provenance=prov,
    )

    # Serialize to JSON string
    json_str = payload.model_dump_json(indent=2)
    assert isinstance(json_str, str), "LOUD FAILURE: model_dump_json did not return str"

    # Deserialize and assert deep equality
    reconstructed = NotebookExtractionPayload.model_validate_json(json_str)
    assert reconstructed.schema_version == payload.schema_version, "LOUD FAILURE: schema_version mismatch"
    assert reconstructed.metadata.id == payload.metadata.id, "LOUD FAILURE: metadata.id mismatch"
    assert len(reconstructed.sources) == 1, f"LOUD FAILURE: sources count mismatch: {len(reconstructed.sources)}"
    assert reconstructed.sources[0].content == src.content, "LOUD FAILURE: source content mismatch after roundtrip"
    assert len(reconstructed.notes) == 1, f"LOUD FAILURE: notes count mismatch: {len(reconstructed.notes)}"
    assert reconstructed.notes[0].title == note.title, "LOUD FAILURE: note title mismatch after roundtrip"


@pytest.mark.unit
def test_payload_unicode_and_emojis():
    """Verify that unicode characters, emojis, and special quotes serialize without corruption."""
    complex_title = "Architectural Patterns: “Dual-Loop” & Agentic Workflows — 2026 Edition ⚡⚓"
    complex_content = "Special chars: \u2014, \u2019, \u201c, \u201d, \U0001F680, \u4e2d\u6587"
    
    meta = NotebookMetadata(
        id="test-unicode-id",
        title=complex_title,
        url="https://example.com",
        source_count=1,
        emoji="⚓",
    )
    src = ExtractedSource(
        id="src-unicode",
        title=complex_title,
        content=complex_content,
        char_count=len(complex_content),
    )
    payload = NotebookExtractionPayload(
        schema_version="1.0.0",
        metadata=meta,
        sources=[src],
        notes=[],
        provenance=ExtractionProvenance(
            transport="direct",
            total_sources=1,
            total_notes=0,
        ),
    )

    json_str = payload.model_dump_json()
    assert complex_title in json_str, "LOUD FAILURE: complex title corrupted in JSON"
    assert "⚡⚓" in json_str, "LOUD FAILURE: emojis missing in JSON"

    parsed = NotebookExtractionPayload.model_validate_json(json_str)
    assert parsed.sources[0].content == complex_content, "LOUD FAILURE: unicode content mismatch"
