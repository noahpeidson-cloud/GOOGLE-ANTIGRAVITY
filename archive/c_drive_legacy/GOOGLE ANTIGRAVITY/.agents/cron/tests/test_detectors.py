"""Comprehensive unit and integration tests for all 5 anomaly detectors and HealthScanner."""

import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import List
import pytest

CRON_DIR = Path(__file__).resolve().parent.parent
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from config import (
    CONTEXT_ROT_THRESHOLD_HOURS,
    PROMPT_FATIGUE_MAX_LINES,
    WHITELISTED_FILENAMES,
)
from conftest import FileSystemSnapshot
from detectors.base import BaseDetector
from detectors.context_rot import ContextRotDetector
from detectors.ecosystem_pollution import EcosystemPollutionDetector
from detectors.ghost_daemons import GhostDaemonsDetector
from detectors.prompt_fatigue import PromptFatigueDetector
from detectors.secret_zero import SecretZeroDetector, mask_token
from models import AnomalyRecord, DetectorType, Severity
from scanner import HealthScanner


# ---------------------------------------------------------------------------
# 1. Base Detector Tests
# ---------------------------------------------------------------------------

def test_base_detector_contract() -> None:
    """Verifies that BaseDetector enforces the scan interface."""
    with pytest.raises(TypeError):
        # Cannot instantiate abstract class directly
        BaseDetector()  # type: ignore

    class CustomDetector(BaseDetector):
        detector_type = DetectorType.GHOST_DAEMONS

        def scan(self, workspace_root: str) -> List[AnomalyRecord]:
            return []

    det = CustomDetector()
    assert det.scan("/tmp") == []
    assert det.detector_type == DetectorType.GHOST_DAEMONS


# ---------------------------------------------------------------------------
# 2. GhostDaemonsDetector Tests
# ---------------------------------------------------------------------------

def test_ghost_daemons_clean_ports() -> None:
    """Verifies that probing inactive ports returns zero anomalies."""
    # Use unassigned high ephemeral ports
    detector = GhostDaemonsDetector(monitored_ports=[59123, 59124], probe_timeout_s=0.1)
    anomalies = detector.scan(workspace_root=".")
    assert len(anomalies) == 0


def test_ghost_daemons_occupied_port_detection() -> None:
    """Verifies that active listening ports are detected as GHOST_DAEMONS anomalies."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Bind to loopback on an ephemeral port
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    bound_port = server_sock.getsockname()[1]

    try:
        detector = GhostDaemonsDetector(monitored_ports=[bound_port], probe_timeout_s=0.2)
        anomalies = detector.scan(workspace_root=".")
        assert len(anomalies) == 1
        record = anomalies[0]
        assert record.detector_type == DetectorType.GHOST_DAEMONS
        assert record.severity == Severity.CRITICAL
        assert f"127.0.0.1:{bound_port}" in record.target_path
        assert "10048" in record.description or "occupied" in record.description
        assert record.raw_details["errno"] == 10048
        assert record.raw_details["port"] == bound_port
    finally:
        server_sock.close()


def test_ghost_daemons_probe_port_direct() -> None:
    """Verifies direct probe_port method."""
    detector = GhostDaemonsDetector(probe_timeout_s=0.1)
    assert detector.probe_port(59999) is False


# ---------------------------------------------------------------------------
# 3. ContextRotDetector Tests
# ---------------------------------------------------------------------------

def test_context_rot_stale_files_detected(tmp_path: Path) -> None:
    """Verifies that planning artifacts older than 24 hours are detected."""
    ws = tmp_path / "ws"
    ws.mkdir()

    # Create stale planning files (>24 hours old)
    old_time = time.time() - (48 * 3600)  # 48 hours ago
    stale_files = [
        "architecture_proposal_v1.md",
        "system_blueprint.md",
        "feature_ideas.md",
        "dev_scratchpad.md",
        "migration_plan.md",
        "worker_progress.md",
        "execution_context.md",
    ]

    for fname in stale_files:
        fpath = ws / fname
        fpath.write_text(f"# Stale artifact: {fname}", encoding="utf-8")
        os.utime(str(fpath), (old_time, old_time))

    detector = ContextRotDetector(threshold_hours=24.0)
    anomalies = detector.scan(str(ws))

    assert len(anomalies) == len(stale_files)
    for rec in anomalies:
        assert rec.detector_type == DetectorType.CONTEXT_ROT
        assert rec.severity == Severity.MEDIUM
        assert rec.raw_details["age_hours"] >= 47.0


def test_context_rot_fresh_files_ignored(tmp_path: Path) -> None:
    """Verifies that fresh planning artifacts (<24 hours old) are ignored."""
    ws = tmp_path / "ws"
    ws.mkdir()

    fresh_plan = ws / "current_plan.md"
    fresh_plan.write_text("# Active Plan", encoding="utf-8")

    detector = ContextRotDetector(threshold_hours=24.0)
    anomalies = detector.scan(str(ws))
    assert len(anomalies) == 0


def test_context_rot_whitelisted_files_protected(tmp_path: Path) -> None:
    """Verifies that whitelisted manifest files are NEVER flagged, even if 100 hours old."""
    ws = tmp_path / "ws"
    ws.mkdir()

    old_time = time.time() - (100 * 3600)  # 100 hours ago
    for wl in WHITELISTED_FILENAMES:
        fpath = ws / wl
        fpath.write_text(f"# Whitelisted manifest {wl}", encoding="utf-8")
        os.utime(str(fpath), (old_time, old_time))

    detector = ContextRotDetector(threshold_hours=24.0)
    anomalies = detector.scan(str(ws))
    assert len(anomalies) == 0, f"Whitelisted files were falsely flagged: {anomalies}"


def test_context_rot_non_planning_files_ignored(tmp_path: Path) -> None:
    """Verifies that non-planning files (e.g. .py, .txt, .json) are ignored by context rot detector."""
    ws = tmp_path / "ws"
    ws.mkdir()

    old_time = time.time() - (100 * 3600)
    (ws / "main.py").write_text("print('hello')", encoding="utf-8")
    os.utime(str(ws / "main.py"), (old_time, old_time))
    (ws / "data.csv").write_text("a,b,c\n1,2,3", encoding="utf-8")
    os.utime(str(ws / "data.csv"), (old_time, old_time))

    detector = ContextRotDetector(threshold_hours=24.0)
    anomalies = detector.scan(str(ws))
    assert len(anomalies) == 0


# ---------------------------------------------------------------------------
# 4. EcosystemPollutionDetector Tests
# ---------------------------------------------------------------------------

def test_ecosystem_pollution_disabled_directories_and_files(tmp_path: Path) -> None:
    """Verifies detection of .disabled plugins and components."""
    ws = tmp_path / "ws"
    plugins_dir = ws / ".gemini" / "config" / "plugins"
    plugins_dir.mkdir(parents=True)

    disabled_dir = plugins_dir / "bigquery_sql.disabled"
    disabled_dir.mkdir()
    (disabled_dir / "SKILL.md").write_text("# Disabled skill", encoding="utf-8")

    disabled_file = ws / "legacy_module.disabled"
    disabled_file.write_text("disabled component", encoding="utf-8")

    detector = EcosystemPollutionDetector()
    anomalies = detector.scan(str(ws))

    assert len(anomalies) == 2
    paths = [a.target_path for a in anomalies]
    assert any("bigquery_sql.disabled" in p for p in paths)
    assert any("legacy_module.disabled" in p for p in paths)
    assert all(a.severity == Severity.HIGH for a in anomalies)


def test_ecosystem_pollution_cross_track_leaks(tmp_path: Path) -> None:
    """Verifies detection of domain cross-track leaks between sports_cards and content_creation."""
    ws = tmp_path / "ws"
    sports_track = ws / "sports_cards"
    sports_track.mkdir(parents=True)
    content_track = ws / "content_creation"
    content_track.mkdir(parents=True)

    # 1. Media video file leaked into sports_cards
    video_leak = sports_track / "unrelated_vlog.mp4"
    video_leak.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    # 2. Sports cards data leaked into content_creation
    card_leak = content_track / "card_ladder_export.csv"
    card_leak.write_text("card_id,psa_grade,price\n1,10,500.0", encoding="utf-8")

    detector = EcosystemPollutionDetector()
    anomalies = detector.scan(str(ws))

    assert len(anomalies) == 2
    assert any(a.detector_type == DetectorType.ECOSYSTEM_POLLUTION for a in anomalies)
    assert any("sports_cards" in a.target_path for a in anomalies)
    assert any("content_creation" in a.target_path for a in anomalies)


def test_ecosystem_pollution_clean_workspace(tmp_path: Path) -> None:
    """Verifies zero anomalies on a clean organized workspace."""
    ws = tmp_path / "ws"
    (ws / "sports_cards").mkdir(parents=True)
    (ws / "sports_cards" / "etl.py").write_text("print('card ladder')", encoding="utf-8")
    (ws / "content_creation").mkdir(parents=True)
    (ws / "content_creation" / "render.py").write_text("print('video render')", encoding="utf-8")

    detector = EcosystemPollutionDetector()
    anomalies = detector.scan(str(ws))
    assert len(anomalies) == 0


# ---------------------------------------------------------------------------
# 5. SecretZeroDetector Tests
# ---------------------------------------------------------------------------

def test_secret_zero_masks_token_utility() -> None:
    """Verifies token masking logic."""
    assert mask_token("abc") == "****"
    assert mask_token("your_token_here") == "yo***re"
    assert mask_token("YOUR_API_KEY_HERE") == "YO***RE"


def test_secret_zero_finds_placeholder_tokens(tmp_path: Path) -> None:
    """Verifies detection of placeholder tokens across environment and configuration files."""
    ws = tmp_path / "ws"
    ws.mkdir()

    # 1. .env file
    env_file = ws / ".env"
    env_file.write_text("API_SECRET=your_token_here\nPORT=3000\n", encoding="utf-8")

    # 2. config.json
    cfg_file = ws / "config.json"
    cfg_file.write_text('{\n  "service_key": "YOUR_API_KEY_HERE"\n}', encoding="utf-8")

    # 3. settings.yaml
    yaml_file = ws / "settings.yaml"
    yaml_file.write_text("auth:\n  token: INSERT_API_KEY_HERE\n", encoding="utf-8")

    detector = SecretZeroDetector()
    anomalies = detector.scan(str(ws))

    assert len(anomalies) == 3
    for a in anomalies:
        assert a.detector_type == DetectorType.SECRET_ZERO
        assert a.severity == Severity.CRITICAL
        # CRITICAL INTEGRITY CHECK: Plaintext placeholder must be masked in description
        assert "your_token_here" not in a.description
        assert "YOUR_API_KEY_HERE" not in a.description
        assert "INSERT_API_KEY_HERE" not in a.description
        assert "***" in a.description


def test_secret_zero_clean_workspace(tmp_path: Path) -> None:
    """Verifies clean config files with valid production format or non-template values pass cleanly."""
    ws = tmp_path / "ws"
    ws.mkdir()

    (ws / ".env").write_text("PORT=8080\nDEBUG=false\n", encoding="utf-8")
    (ws / "config.json").write_text('{"db": "production.db"}', encoding="utf-8")

    detector = SecretZeroDetector()
    anomalies = detector.scan(str(ws))
    assert len(anomalies) == 0


# ---------------------------------------------------------------------------
# 6. PromptFatigueDetector Tests
# ---------------------------------------------------------------------------

def test_prompt_fatigue_bloated_manifest(tmp_path: Path) -> None:
    """Verifies that GEMINI.md manifests exceeding max_lines (100) are flagged."""
    ws = tmp_path / "ws"
    ws.mkdir()

    manifest = ws / "GEMINI.md"
    lines = [f"# Directive Section {i}\nRule description {i}" for i in range(70)]
    manifest.write_text("\n".join(lines), encoding="utf-8")  # 140 lines

    detector = PromptFatigueDetector(max_lines=100)
    anomalies = detector.scan(str(ws))

    assert len(anomalies) >= 1
    rec = anomalies[0]
    assert rec.detector_type == DetectorType.PROMPT_FATIGUE
    assert rec.raw_details["line_count"] > 100
    assert rec.raw_details["max_lines"] == 100
    assert "token_count" in rec.raw_details


def test_prompt_fatigue_duplicate_sections(tmp_path: Path) -> None:
    """Verifies detection of duplicate markdown rule sections in GEMINI.md."""
    ws = tmp_path / "ws"
    ws.mkdir()

    manifest = ws / "GEMINI.md"
    content = """# Antigravity Global Steering
## R1. Workflow Distillation
Description of R1.

## R2. The Zero-Discretion Mandate
Description of R2.

## R1. Workflow Distillation
Duplicate copy of R1.
"""
    manifest.write_text(content, encoding="utf-8")

    detector = PromptFatigueDetector(max_lines=100)
    anomalies = detector.scan(str(ws))

    assert len(anomalies) >= 1
    dup_rec = [a for a in anomalies if "Duplicate" in a.description][0]
    assert dup_rec.severity == Severity.HIGH
    assert "R1. Workflow Distillation" in dup_rec.description or "r1. workflow distillation" in dup_rec.description.lower()


def test_prompt_fatigue_clean_manifest(tmp_path: Path) -> None:
    """Verifies that a concise, unique GEMINI.md passes cleanly."""
    ws = tmp_path / "ws"
    ws.mkdir()

    manifest = ws / "GEMINI.md"
    content = """# Antigravity Global Steering
## R1. Protocol
Clean description.
"""
    manifest.write_text(content, encoding="utf-8")

    detector = PromptFatigueDetector(max_lines=100)
    anomalies = detector.scan(str(ws))
    assert len(anomalies) == 0


def test_prompt_fatigue_missing_manifest(tmp_path: Path) -> None:
    """Verifies that a missing GEMINI.md returns empty list gracefully."""
    ws = tmp_path / "ws"
    ws.mkdir()

    detector = PromptFatigueDetector()
    anomalies = detector.scan(str(ws))
    assert len(anomalies) == 0


# ---------------------------------------------------------------------------
# 7. HealthScanner Orchestration Tests
# ---------------------------------------------------------------------------

def test_health_scanner_orchestration(tmp_path: Path) -> None:
    """Verifies HealthScanner coordinates all 5 detectors on a complete mock environment."""
    ws = tmp_path / "mock_workspace"
    ws.mkdir()

    # 1. Stale planning file
    old_time = time.time() - (48 * 3600)
    stale_file = ws / "old_plan.md"
    stale_file.write_text("# Old plan", encoding="utf-8")
    os.utime(str(stale_file), (old_time, old_time))

    # 2. Disabled plugin
    (ws / "plugins").mkdir()
    (ws / "plugins" / "bad.disabled").mkdir()

    # 3. Secret zero token
    (ws / ".env").write_text("KEY=your_token_here\n", encoding="utf-8")

    # 4. Bloated GEMINI.md
    manifest_lines = [f"Line {i}" for i in range(120)]
    (ws / "GEMINI.md").write_text("\n".join(manifest_lines), encoding="utf-8")

    scanner = HealthScanner()
    anomalies = scanner.scan_workspace(str(ws))

    assert len(anomalies) >= 4
    detected_types = {a.detector_type for a in anomalies}
    assert DetectorType.CONTEXT_ROT in detected_types
    assert DetectorType.ECOSYSTEM_POLLUTION in detected_types
    assert DetectorType.SECRET_ZERO in detected_types
    assert DetectorType.PROMPT_FATIGUE in detected_types

    duration_ms = scanner.get_last_duration_ms()
    assert duration_ms > 0.0


def test_health_scanner_exception_isolation(tmp_path: Path) -> None:
    """Verifies that an exception in one detector does not crash the overall scan."""
    class FaultyDetector(BaseDetector):
        detector_type = DetectorType.GHOST_DAEMONS

        def scan(self, workspace_root: str) -> List[AnomalyRecord]:
            raise RuntimeError("Catastrophic network socket error")

    class WorkingDetector(BaseDetector):
        detector_type = DetectorType.CONTEXT_ROT

        def scan(self, workspace_root: str) -> List[AnomalyRecord]:
            return [
                AnomalyRecord(
                    detector_type=DetectorType.CONTEXT_ROT,
                    target_path="plan.md",
                    severity=Severity.LOW,
                    description="Test finding",
                    raw_details={},
                )
            ]

    scanner = HealthScanner(detectors=[FaultyDetector(), WorkingDetector()])
    anomalies = scanner.scan_workspace(str(tmp_path))

    # WorkingDetector results should still be returned
    assert len(anomalies) == 1
    assert anomalies[0].detector_type == DetectorType.CONTEXT_ROT


# ---------------------------------------------------------------------------
# 8. Cryptographic Read-Only FileSystemSnapshot Verification
# ---------------------------------------------------------------------------

def test_detectors_and_scanner_strictly_read_only(tmp_path: Path) -> None:
    """Loud Assertion: Takes FileSystemSnapshot before full scan and asserts 0 modifications."""
    ws = tmp_path / "read_only_ws"
    ws.mkdir()

    # Create various mock files
    (ws / "GEMINI.md").write_text("# Manifest\n", encoding="utf-8")
    (ws / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    (ws / ".env").write_text("TOKEN=your_token_here\n", encoding="utf-8")
    (ws / "proposal_old.md").write_text("# Proposal\n", encoding="utf-8")

    # Take initial cryptographic snapshot
    snapshot = FileSystemSnapshot(str(ws))

    # Run full HealthScanner
    scanner = HealthScanner()
    anomalies = scanner.scan_workspace(str(ws))

    assert len(anomalies) > 0

    # Assert 100% untouched
    snapshot.assert_untouched()
