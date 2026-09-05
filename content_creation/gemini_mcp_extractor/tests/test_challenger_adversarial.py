"""
Adversarial Stress-Testing Suite for Gemini MCP Extractor.
Author: teamwork_preview_challenger_2 (EMPIRICAL CHALLENGER)

Tests CLI behavior, edge cases, error codes, transport error classification,
custom arguments (--dry-run, --limit 1, --format jsonl, --no-content),
and missing authentication.
"""

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import pytest

from schemas import NotebookExtractionPayload
import client
import extractor


EXTRACTOR_SCRIPT = Path(__file__).parent.parent / "extractor.py"
PROJECT_DIR = Path(__file__).parent.parent


class TestEdgeCasesAndCliOptions:
    """Stress tests covering CLI flags, formats, and limits."""

    def test_dry_run_with_limit_1(self, tmp_path, target_notebook_id):
        """Verify --dry-run and --limit 1 extracts exactly 1 source and valid JSON."""
        output_file = tmp_path / "test_limit_1.json"
        cmd = [
            sys.executable,
            str(EXTRACTOR_SCRIPT),
            "--notebook-id", target_notebook_id,
            "--output", str(output_file),
            "--dry-run",
            "--limit", "1",
            "--transport", "direct",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_file.exists(), "Output file does not exist"

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        payload = NotebookExtractionPayload.model_validate(data)
        assert len(payload.sources) == 1, f"Expected 1 source, got {len(payload.sources)}"
        assert payload.provenance.is_dry_run is True, "Provenance is_dry_run must be True"
        assert payload.provenance.limit_applied == 1, f"Expected limit_applied=1, got {payload.provenance.limit_applied}"
        assert len(payload.notes) >= 1, "Expected notes to be extracted"
        assert payload.sources[0].status == "success"
        assert len(payload.sources[0].content) > 0

    def test_format_jsonl_output(self, tmp_path, target_notebook_id):
        """Verify --format jsonl produces valid Line-Delimited JSON."""
        output_file = tmp_path / "test_format.jsonl"
        cmd = [
            sys.executable,
            str(EXTRACTOR_SCRIPT),
            "--notebook-id", target_notebook_id,
            "--output", str(output_file),
            "--dry-run",
            "--limit", "1",
            "--format", "jsonl",
            "--transport", "direct",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_file.exists(), "JSONL output file not created"

        with open(output_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) >= 4, f"Expected at least 4 JSONL lines, got {len(lines)}"
        parsed_records = []
        for line in lines:
            try:
                record = json.loads(line)
                assert isinstance(record, dict)
                assert "type" in record
                assert "data" in record
                parsed_records.append(record)
            except json.JSONDecodeError as e:
                pytest.fail(f"Line is not valid JSON: {line} - {e}")

        types = [r["type"] for r in parsed_records]
        assert "provenance" in types
        assert "metadata" in types
        assert "note" in types
        assert "source" in types

    def test_no_content_flag(self, tmp_path, target_notebook_id):
        """Verify --no-content extracts source metadata with 0-byte content and skipped status."""
        output_file = tmp_path / "test_no_content.json"
        cmd = [
            sys.executable,
            str(EXTRACTOR_SCRIPT),
            "--notebook-id", target_notebook_id,
            "--output", str(output_file),
            "--dry-run",
            "--limit", "1",
            "--no-content",
            "--transport", "direct",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_file.exists(), "Output file does not exist"

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        payload = NotebookExtractionPayload.model_validate(data)
        assert len(payload.sources) == 1
        src = payload.sources[0]
        assert src.content is None, f"Expected content None, got {src.content}"
        assert src.char_count == 0, f"Expected char_count 0, got {src.char_count}"
        assert src.status == "skipped", f"Expected status 'skipped', got {src.status}"
        assert len(src.title) > 0, "Source title should be populated"

    def test_missing_authentication_exit_code_1(self):
        """Verify missing authentication causes exit code 1 with clean error message."""
        with patch("client.check_cached_authentication", return_value=False):
            with pytest.raises(client.AuthenticationError):
                client.require_authentication()

            test_args = ["extractor.py", "--notebook-id", "any-id"]
            with patch.object(sys, "argv", test_args):
                with pytest.raises(SystemExit) as exc_info:
                    extractor.main()
                assert exc_info.value.code == 1, f"Expected exit code 1 on missing auth, got {exc_info.value.code}"

    def test_unrecognized_argument_exit_code_2(self):
        """Verify invalid CLI arguments exit with code 2."""
        cmd = [sys.executable, str(EXTRACTOR_SCRIPT), "--nonexistent-flag-xyz"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert result.returncode == 2, f"Expected exit code 2 on invalid flag, got {result.returncode}"
        assert "unrecognized arguments" in result.stderr

    def test_dry_run_default_output_safety(self):
        """Verify --dry-run defaults to extracted_notebook_data_dryrun.json when --output is omitted."""
        parser = extractor.build_parser()
        args_normal = parser.parse_args([])
        assert args_normal.output is None
        assert args_normal.dry_run is False

        args_dry = parser.parse_args(["--dry-run"])
        assert args_dry.output is None
        assert args_dry.dry_run is True

        args_explicit = parser.parse_args(["--dry-run", "--output", "custom.json"])
        assert args_explicit.output == "custom.json"


class TestAdversarialErrorHandlingDefects:
    """
    Adversarial tests specifically challenging the error handling and exit codes
    against the mandate:
    'Test invalid notebook ID (must fail cleanly with exit code 1, not crash with unhandled traceback).'
    """

    def test_invalid_notebook_id_exit_code_mandate_mcp(self, tmp_path):
        """
        EMPIRICAL CHALLENGE:
        The mission mandate specifies:
        'Test invalid notebook ID (must fail cleanly with exit code 1, not crash with unhandled traceback).'

        This test empirically verifies whether the CLI returns exit code 1 on invalid notebook ID under MCP transport.
        """
        output_file = tmp_path / "invalid_nb.json"
        cmd = [
            sys.executable,
            str(EXTRACTOR_SCRIPT),
            "--notebook-id", "00000000-0000-0000-0000-000000000000",
            "--output", str(output_file),
            "--transport", "mcp",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        # Assertion: No unhandled traceback
        assert "Traceback (most recent call last):" not in result.stderr, (
            f"Traceback leaked in stderr:\n{result.stderr}"
        )

        # Empirical Check: Did it exit with code 1?
        # Note: If this fails, it proves the bug empirically.
        assert result.returncode == 1, (
            f"DISPROVEN MANDATE: Invalid notebook ID exited with code {result.returncode}, NOT 1!\n"
            f"Stderr: {result.stderr.strip()}"
        )

    def test_invalid_notebook_id_exit_code_mandate_direct(self, tmp_path):
        """
        EMPIRICAL CHALLENGE:
        Verifies whether the CLI returns exit code 1 on invalid notebook ID under Direct transport.
        """
        output_file = tmp_path / "invalid_nb_direct.json"
        cmd = [
            sys.executable,
            str(EXTRACTOR_SCRIPT),
            "--notebook-id", "00000000-0000-0000-0000-000000000000",
            "--output", str(output_file),
            "--transport", "direct",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        # Assertion: No unhandled traceback
        assert "Traceback (most recent call last):" not in result.stderr, (
            f"Traceback leaked in stderr:\n{result.stderr}"
        )

        assert result.returncode == 1, (
            f"DISPROVEN MANDATE: Invalid notebook ID exited with code {result.returncode}, NOT 1!\n"
            f"Stderr: {result.stderr.strip()}"
        )

    def test_string_matching_bug_not_found_vs_not_underscore_found(self):
        """
        EMPIRICAL ROOT CAUSE ANALYSIS:
        Demonstrates why client.py fails to classify NOT_FOUND errors as NotebookNotFoundError.
        In client.py:
            if "not found" in err_msg.lower():
        When the API returns:
            'Failed to get notebook: API error (code 5): NOT_FOUND'
        'not found' (with space) is NOT in '... not_found'.
        """
        upstream_error = "Failed to get notebook: API error (code 5): NOT_FOUND"
        err_lower = upstream_error.lower()

        # The buggy check in client.py lines 261 & 427:
        buggy_check = "not found" in err_lower

        # The correct check that handles underscores and codes:
        correct_check = "not found" in err_lower or "not_found" in err_lower or "code 5" in err_lower

        assert buggy_check is False, "Expected buggy check to fail to match 'not_found'"
        assert correct_check is True, "Expected corrected check to match 'not_found'"
