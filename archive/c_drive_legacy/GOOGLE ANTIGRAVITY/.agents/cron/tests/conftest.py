"""Shared pytest fixtures and FileSystemSnapshot SHA256 integrity verifier."""

import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, List
import pytest

# Ensure the parent .agents/cron directory is on sys.path
CRON_DIR = Path(__file__).resolve().parent.parent
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

from database import init_db
from models import AnomalyRecord, DetectorType, Severity


class FileSystemSnapshot:
    """Computes and verifies SHA256 hashes of all files in a directory tree to enforce read-only safety."""

    def __init__(self, root_dir: str) -> None:
        self.root_dir = os.path.abspath(root_dir)
        self.initial_hashes: Dict[str, str] = self._compute_hashes()

    def _compute_hashes(self) -> Dict[str, str]:
        hashes: Dict[str, str] = {}
        if not os.path.exists(self.root_dir):
            return hashes

        for root, _, files in os.walk(self.root_dir):
            for file in sorted(files):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.root_dir)
                try:
                    with open(full_path, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    hashes[rel_path] = file_hash
                except Exception as e:
                    hashes[rel_path] = f"ERROR:{e}"
        return hashes

    def assert_untouched(self) -> None:
        """Asserts that zero files have been added, deleted, or modified since initialization."""
        current_hashes = self._compute_hashes()
        added = set(current_hashes.keys()) - set(self.initial_hashes.keys())
        removed = set(self.initial_hashes.keys()) - set(current_hashes.keys())
        modified = [
            k for k in self.initial_hashes
            if k in current_hashes and self.initial_hashes[k] != current_hashes[k]
        ]

        if added or removed or modified:
            msg = (
                f"FileSystem modification violation in {self.root_dir}:\n"
                f"  Added files: {sorted(list(added))}\n"
                f"  Removed files: {sorted(list(removed))}\n"
                f"  Modified files: {sorted(modified)}"
            )
            raise AssertionError(msg)


@pytest.fixture
def isolated_workspace(tmp_path: Path) -> Path:
    """Provides a sterile, isolated workspace directory."""
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


@pytest.fixture
def mock_db(tmp_path: Path) -> str:
    """Initializes and returns the path to a temporary SQLite telemetry database."""
    db_file = tmp_path / "test_telemetry.db"
    db_path = str(db_file)
    init_db(db_path)
    return db_path


@pytest.fixture
def sample_anomalies() -> List[AnomalyRecord]:
    """Returns a representative list of AnomalyRecord instances across all 5 detector types."""
    return [
        AnomalyRecord(
            detector_type=DetectorType.GHOST_DAEMONS,
            target_path="127.0.0.1:3000",
            severity=Severity.CRITICAL,
            description="Socket collision detected on port 3000 (WinError 10048)",
            raw_details={"port": 3000, "status": "OCCUPIED", "errno": 10048},
            is_historical=False,
            timestamp=1756000000,
            confidence=1.0,
        ),
        AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path=".agents/worker_old/progress.md",
            severity=Severity.MEDIUM,
            description="Planning artifact older than 48.5 hours diluting context window",
            raw_details={"age_hours": 48.5, "threshold_hours": 24.0},
            is_historical=False,
            timestamp=1756000000,
            confidence=0.95,
        ),
        AnomalyRecord(
            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
            target_path="plugins/gcp_spark.disabled",
            severity=Severity.HIGH,
            description="Unused .disabled plugin directory detected polluting workspace",
            raw_details={"is_disabled": True, "extension": ".disabled"},
            is_historical=False,
            timestamp=1756000000,
            confidence=1.0,
        ),
        AnomalyRecord(
            detector_type=DetectorType.SECRET_ZERO,
            target_path=".env",
            severity=Severity.CRITICAL,
            description="Unresolved placeholder token 'your_token_here' found in environment file",
            raw_details={"token": "your_token_here", "line": 4},
            is_historical=False,
            timestamp=1756000000,
            confidence=1.0,
        ),
        AnomalyRecord(
            detector_type=DetectorType.PROMPT_FATIGUE,
            target_path="GEMINI.md",
            severity=Severity.MEDIUM,
            description="Manifest rule bloat: GEMINI.md has 179 lines (exceeds 100 line limit)",
            raw_details={"line_count": 179, "max_lines": 100},
            is_historical=False,
            timestamp=1756000000,
            confidence=1.0,
        ),
    ]
