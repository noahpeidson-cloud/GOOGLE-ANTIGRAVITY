"""
Dry-run integration test for extractor.py adhering to R2 Zero-Discretion Mandate.
Verifies subset extraction (--dry-run, --limit 2), Pydantic validation, and atomic JSON file writing.
"""

import json
import subprocess
import sys
from pathlib import Path
import pytest

from schemas import NotebookExtractionPayload


@pytest.mark.dry_run
@pytest.mark.live
def test_extractor_cli_dry_run(tmp_path, target_notebook_id):
    """
    Verify CLI dry-run execution:
    - Runs extractor.py with --dry-run and --limit 2 against live target notebook.
    - Asserts returncode 0.
    - Asserts output JSON file exists and parses against NotebookExtractionPayload.
    - Asserts exactly 2 sources and 1 note are recorded.
    """
    output_file = tmp_path / "dry_run_output.json"
    extractor_script = Path(__file__).parent.parent / "extractor.py"

    cmd = [
        sys.executable,
        str(extractor_script),
        "--notebook-id", target_notebook_id,
        "--output", str(output_file),
        "--dry-run",
        "--limit", "2",
        "--transport", "direct",  # Or mcp
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"LOUD FAILURE: CLI dry-run exited with code {result.returncode}.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    assert output_file.exists(), f"LOUD FAILURE: Output JSON file was not created: {output_file}"
    assert output_file.stat().st_size > 0, "LOUD FAILURE: Output JSON file is empty (0 bytes)"

    # Read and parse JSON
    with open(output_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Validate against Pydantic schema
    payload = NotebookExtractionPayload.model_validate(raw_data)

    # R2 Loud Assertions on Dry-Run Subsets
    assert payload.metadata.id == target_notebook_id, (
        f"LOUD FAILURE: Expected notebook ID {target_notebook_id}, got {payload.metadata.id}"
    )
    assert payload.provenance.is_dry_run is True, (
        "LOUD FAILURE: Provenance is_dry_run must be True"
    )
    assert payload.provenance.limit_applied == 2, (
        f"LOUD FAILURE: Provenance limit_applied must be 2, got {payload.provenance.limit_applied}"
    )
    assert len(payload.sources) == 2, (
        f"LOUD FAILURE: Dry-run should extract exactly 2 sources, got {len(payload.sources)}"
    )

    # Assert all extracted sources have non-empty content and valid status
    for i, src in enumerate(payload.sources):
        assert src.status == "success", f"LOUD FAILURE: Source #{i} ({src.id}) status is '{src.status}'"
        assert src.content is not None and len(src.content) > 0, (
            f"LOUD FAILURE: Source #{i} '{src.title}' ({src.id}) has empty content!"
        )
        assert src.char_count == len(src.content), (
            f"LOUD FAILURE: Source #{i} char_count mismatch: {src.char_count} != {len(src.content)}"
        )

    # Assert notes extracted
    assert len(payload.notes) == 1, f"LOUD FAILURE: Expected exactly 1 note, got {len(payload.notes)}"
    assert len(payload.notes[0].content) > 1000, "LOUD FAILURE: Note content unexpectedly short"
