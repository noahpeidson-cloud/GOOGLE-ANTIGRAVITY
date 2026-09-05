"""
End-to-end integration test validating full extraction of all 61 sources + 1 note.
Adheres to R2 Zero-Discretion Mandate with uncompromising loud assertions.
"""

import json
import subprocess
import sys
from pathlib import Path
import pytest

from schemas import NotebookExtractionPayload


@pytest.mark.live
def test_extractor_full_61_sources_e2e(tmp_path, target_notebook_id):
    """
    Execute full extraction of notebook 4b52cc67-9f81-4e85-a024-5f06756991ab:
    - Runs extractor CLI with concurrency 4 and full item list.
    - Asserts exactly 61 sources and 1 note extracted.
    - Validates that every source has non-empty text, correct char_count, and status='success'.
    - Validates complete JSON payload against NotebookExtractionPayload schema.
    """
    output_file = tmp_path / "full_extraction_61_items.json"
    extractor_script = Path(__file__).parent.parent / "extractor.py"

    cmd = [
        sys.executable,
        str(extractor_script),
        "--notebook-id", target_notebook_id,
        "--output", str(output_file),
        "--concurrency", "4",
        "--transport", "mcp",  # MCP transport runs in ~57s vs >210s direct
    ]

    print(f"\n[E2E] Launching full 61-source extraction...")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minute timeout to absorb network fluctuations
    )

    assert result.returncode == 0, (
        f"LOUD FAILURE: Full extraction CLI failed with code {result.returncode}.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    assert output_file.exists(), f"LOUD FAILURE: Output JSON file missing: {output_file}"
    file_size_bytes = output_file.stat().st_size
    assert file_size_bytes > 500_000, (
        f"LOUD FAILURE: Extracted JSON file size ({file_size_bytes} bytes) is suspiciously small "
        f"for 61 full documents!"
    )

    # Read and parse file
    with open(output_file, "r", encoding="utf-8") as f:
        raw_json = json.load(f)

    payload = NotebookExtractionPayload.model_validate(raw_json)

    # 1. Metadata Verification
    assert payload.metadata.id == target_notebook_id, "LOUD FAILURE: metadata.id mismatch"
    assert payload.metadata.title == "Dual-Loop Control and Agentic Orchestration in Cognitive Architectures", (
        f"LOUD FAILURE: Notebook title mismatch: {payload.metadata.title}"
    )
    assert payload.metadata.source_count == 61, "LOUD FAILURE: metadata.source_count != 61"

    # 2. Provenance Verification
    assert payload.provenance.is_dry_run is False, "LOUD FAILURE: is_dry_run should be False"
    assert payload.provenance.limit_applied is None, "LOUD FAILURE: limit_applied should be None"
    assert payload.provenance.total_sources == 61, "LOUD FAILURE: total_sources in provenance != 61"
    assert payload.provenance.total_notes == 1, "LOUD FAILURE: total_notes in provenance != 1"

    # 3. Source Count & Integrity Verification
    assert len(payload.sources) == 61, (
        f"LOUD FAILURE: Expected exactly 61 extracted sources, got {len(payload.sources)}"
    )

    failed_sources = []
    empty_content_sources = []
    total_characters = 0

    for i, src in enumerate(payload.sources, 1):
        if src.status != "success":
            failed_sources.append(f"#{i} {src.id} ({src.title}): {src.error}")
        if not src.content or len(src.content.strip()) == 0:
            empty_content_sources.append(f"#{i} {src.id} ({src.title})")
        else:
            total_characters += len(src.content)
            assert src.char_count == len(src.content), (
                f"LOUD FAILURE: Source #{i} char_count mismatch ({src.char_count} != {len(src.content)})"
            )

    assert len(failed_sources) == 0, (
        f"LOUD FAILURE: {len(failed_sources)} sources failed extraction:\n" + "\n".join(failed_sources[:10])
    )
    assert len(empty_content_sources) == 0, (
        f"LOUD FAILURE: {len(empty_content_sources)} sources returned empty content:\n" + "\n".join(empty_content_sources[:10])
    )
    assert total_characters > 500_000, (
        f"LOUD FAILURE: Total extracted text length ({total_characters} chars) is below expected 500k chars."
    )

    # 4. Known Source Boundaries Check
    source_titles = [s.title for s in payload.sources]
    first_title = source_titles[0]
    last_title = source_titles[-1]
    assert "11 Top Open-Source LLMs for 2026" in first_title, (
        f"LOUD FAILURE: Expected first source to be Open-Source LLMs, got: {first_title}"
    )
    assert "What is an AI Agent Harness?" in last_title, (
        f"LOUD FAILURE: Expected last source to be AI Agent Harness, got: {last_title}"
    )

    # 5. Note Verification
    assert len(payload.notes) == 1, f"LOUD FAILURE: Expected exactly 1 note, got {len(payload.notes)}"
    note = payload.notes[0]
    assert note.id == "eff2cf19-844e-4af7-aad8-601d7d0fbf13", f"LOUD FAILURE: note id mismatch: {note.id}"
    assert note.title == "The Multi-Model Orchestration and AI Handoff Framework", (
        f"LOUD FAILURE: Note title mismatch: {note.title}"
    )
    assert len(note.content) >= 3000, (
        f"LOUD FAILURE: Note content length ({len(note.content)} chars) unexpectedly short"
    )

    print(f"\n[E2E SUCCESS] Successfully verified all 61 sources ({total_characters:,} characters) and 1 note!")
