"""Comprehensive Integration and End-to-End Test Suite for Antigravity Scanner Daemon."""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List
import pytest

CRON_DIR = Path(__file__).resolve().parent.parent
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

from audit.red_team import ArchitectureRedTeam
from config import DEFAULT_DB_PATH, DEFAULT_K_CLUSTERS
from database import (
    get_anomalies_for_session,
    get_historical_drift,
    get_historical_lifelines,
    get_session,
    get_textual_gradients_for_session,
    init_db,
)
from fixtures.mock_workspace_factory import MockDaemonListener, create_mock_workspace
from models import (
    AnomalyRecord,
    DetectorType,
    OptimizationReport,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)
from scanner import HealthScanner
from scanner_daemon import (
    build_cli_parser,
    create_antigravity_sdk_trigger,
    main,
    run_health_scan,
)
from tests.conftest import FileSystemSnapshot


# =============================================================================
# 1. End-to-End Pipeline Integration Tests
# =============================================================================
def test_scanner_daemon_e2e_mock_workspace(tmp_path: Path) -> None:
    """Tests the full 9-step non-destructive health scan pipeline against the mock workspace."""
    ws_dir = tmp_path / "workspace"
    db_path = tmp_path / "telemetry.db"
    out_dir = tmp_path / "reports"

    create_mock_workspace(str(ws_dir))

    # Execute 9-step pipeline
    report, report_path = run_health_scan(
        workspace_root=str(ws_dir),
        db_path=str(db_path),
        output_dir=str(out_dir),
        k_clusters=3,
    )

    # 1. Validate OptimizationReport dataclass contract
    assert isinstance(report, OptimizationReport)
    assert report.session_id.startswith("health_scan_")
    assert report.timestamp > 0
    assert report.duration_ms > 0.0
    assert report.total_anomalies > 0
    assert report.approved_count + report.challenged_count <= report.total_anomalies
    assert len(report.audited_anomalies) == report.total_anomalies
    assert len(report.textual_gradients) > 0
    assert 0.0 <= report.entropy_score <= 1.0

    # 2. Validate written Markdown report file
    assert os.path.exists(report_path)
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()

    assert "# Daily System Health & Optimization Report —" in report_content
    assert "## 1. Executive Summary & Health Telemetry" in report_content
    assert "## 2. Red-Team Scrutiny Verdicts" in report_content
    assert "## 3. Proposed Optimizations (HITL Checkboxes)" in report_content
    assert "## 4. Historical Failure Lifelines & Drift Analytics" in report_content
    assert "## 5. ProTeGi Textual Gradients for Self-Improvement" in report_content
    assert "## 6. Manual Remediation Command Guide" in report_content
    assert report.session_id in report_content

    # 3. Validate SQLite persistence and data integrity
    sess = get_session(report.session_id, db_path=str(db_path))
    assert sess is not None
    assert sess["session_id"] == report.session_id
    assert sess["total_anomalies"] == report.total_anomalies

    anomalies = get_anomalies_for_session(report.session_id, db_path=str(db_path))
    assert len(anomalies) == report.total_anomalies

    gradients = get_textual_gradients_for_session(report.session_id, db_path=str(db_path))
    assert len(gradients) == len(report.textual_gradients)

    # 4. Validate 5 Historical Lifelines auto-seeding
    lifelines = get_historical_lifelines(db_path=str(db_path))
    assert len(lifelines) == 5
    codes = {lf["lifeline_code"] for lf in lifelines}
    assert "GHOST_DAEMONS_WINERROR_10048" in codes
    assert "CONTEXT_ROT_PLANNING_ARTIFACTS" in codes
    assert "ECOSYSTEM_POLLUTION_DISABLED_PLUGINS" in codes
    assert "SECRET_ZERO_PLACEHOLDER_KEYS" in codes
    assert "PROMPT_FATIGUE_MANIFEST_BLOAT" in codes


# =============================================================================
# 2. CLI Execution Tests (--run-once, arguments, exit code 0)
# =============================================================================
def test_cli_main_run_once(tmp_path: Path) -> None:
    """Tests invoking main() directly with CLI arguments."""
    ws_dir = tmp_path / "cli_workspace"
    db_path = tmp_path / "cli_telemetry.db"
    out_dir = tmp_path / "cli_reports"

    create_mock_workspace(str(ws_dir))

    argv = [
        "--run-once",
        "--workspace",
        str(ws_dir),
        "--db",
        str(db_path),
        "--output-dir",
        str(out_dir),
    ]

    exit_code = main(argv)
    assert exit_code == 0

    # Verify report created in out_dir
    created_reports = list(out_dir.glob("daily_health_report_*.md"))
    assert len(created_reports) == 1
    assert created_reports[0].stat().st_size > 500


def test_cli_subprocess_execution(tmp_path: Path) -> None:
    """Tests executing scanner_daemon.py as a standalone external Python subprocess."""
    ws_dir = tmp_path / "subp_workspace"
    db_path = tmp_path / "subp_telemetry.db"
    out_dir = tmp_path / "subp_reports"

    create_mock_workspace(str(ws_dir))

    daemon_script = CRON_DIR / "scanner_daemon.py"

    cmd = [
        sys.executable,
        str(daemon_script),
        "--run-once",
        "--workspace",
        str(ws_dir),
        "--db",
        str(db_path),
        "--output-dir",
        str(out_dir),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "ANTIGRAVITY HEALTH SCAN COMPLETE:" in result.stdout
    assert "Total Anomalies Detected" in result.stdout

    created_reports = list(out_dir.glob("daily_health_report_*.md"))
    assert len(created_reports) == 1


def test_cli_parser_defaults_and_options() -> None:
    """Tests CLI argument parser configurations and flag combinations."""
    parser = build_cli_parser()
    args = parser.parse_args(["--run-once", "--interval", "120", "--k-clusters", "4"])
    assert args.run_once is True
    assert args.interval == 120
    assert args.k_clusters == 4
    assert args.mock_env is False


# =============================================================================
# 3. Idempotency & Drift Analytics Across Multiple Sessions
# =============================================================================
def test_idempotency_and_drift_tracking_across_sessions(tmp_path: Path) -> None:
    """Tests multiple consecutive scan sessions, drift metrics aggregation, and seeding idempotency."""
    ws_dir = tmp_path / "drift_workspace"
    db_path = tmp_path / "drift_telemetry.db"
    out_dir = tmp_path / "drift_reports"

    create_mock_workspace(str(ws_dir))

    # Session 1
    rep1, _ = run_health_scan(str(ws_dir), str(db_path), str(out_dir))
    # Session 2
    rep2, _ = run_health_scan(str(ws_dir), str(db_path), str(out_dir))
    # Session 3
    rep3, _ = run_health_scan(str(ws_dir), str(db_path), str(out_dir))

    assert rep1.session_id != rep2.session_id != rep3.session_id

    # Check drift statistics
    drift = get_historical_drift(db_path=str(db_path))
    assert drift["total_sessions"] == 3
    assert drift["total_anomalies"] == rep1.total_anomalies + rep2.total_anomalies + rep3.total_anomalies
    assert drift["historical_lifelines_count"] == 5
    assert drift["drift_detected"] is True
    assert drift["average_duration_ms"] > 0.0

    # Ensure historical failure lifelines remained exactly 5 (idempotent seeding)
    lifelines = get_historical_lifelines(db_path=str(db_path))
    assert len(lifelines) == 5


# =============================================================================
# 4. Cryptographic SHA-256 0-Destruction FileSystemSnapshot Verification
# =============================================================================
def test_0_destruction_cryptographic_snapshot_untouched(tmp_path: Path) -> None:
    """Loud Assertion: Takes SHA-256 snapshot before scan and cryptographically proves 0 modifications."""
    ws_dir = tmp_path / "protected_workspace"
    db_path = tmp_path / "external_telemetry.db"
    out_dir = tmp_path / "external_reports"

    create_mock_workspace(str(ws_dir))

    # Cryptographic snapshot of workspace before scan
    snapshot = FileSystemSnapshot(str(ws_dir))

    # Run full health scan
    report, report_path = run_health_scan(
        workspace_root=str(ws_dir),
        db_path=str(db_path),
        output_dir=str(out_dir),
    )

    assert report.total_anomalies > 0

    # Assert workspace is 100% byte-for-byte untouched
    snapshot.assert_untouched()


# =============================================================================
# 5. Ghost Daemon Active Socket Listener Integration Test
# =============================================================================
def test_ghost_daemon_active_socket_detection(tmp_path: Path) -> None:
    """Tests that active ghost daemon listener is detected during scan."""
    ws_dir = tmp_path / "daemon_workspace"
    db_path = tmp_path / "daemon_telemetry.db"
    out_dir = tmp_path / "daemon_reports"

    create_mock_workspace(str(ws_dir))

    # Start loopback listener
    with MockDaemonListener(port=3000) as listener:
        bound_port = listener.port
        # Configure scanner with listener port
        scanner = HealthScanner()
        # Find GhostDaemonsDetector and ensure bound_port is in monitored_ports
        for d in scanner.detectors:
            if isinstance(d, type(d)) and d.__class__.__name__ == "GhostDaemonsDetector":
                if bound_port not in d.monitored_ports:
                    d.monitored_ports.append(bound_port)

        report, _ = run_health_scan(
            workspace_root=str(ws_dir),
            db_path=str(db_path),
            output_dir=str(out_dir),
            custom_scanner=scanner,
        )

        ghost_anomalies = [
            a for a in report.audited_anomalies
            if a.anomaly and a.anomaly.detector_type == DetectorType.GHOST_DAEMONS
        ]
        assert len(ghost_anomalies) >= 1
        assert ghost_anomalies[0].verdict in {RedTeamVerdict.CHALLENGED, RedTeamVerdict.REJECTED}


# =============================================================================
# 6. Clean Workspace & SDK Trigger Tests
# =============================================================================
def test_clean_workspace_nominal_scan(tmp_path: Path) -> None:
    """Tests scan against a nominal clean workspace with 0 anomalies."""
    ws_dir = tmp_path / "clean_workspace"
    ws_dir.mkdir(parents=True)
    (ws_dir / "PROJECT.md").write_text("# Project Spec\n", encoding="utf-8")
    (ws_dir / "GEMINI.md").write_text("# Steering\n## R1. Protocol\nClean rules.\n", encoding="utf-8")

    db_path = tmp_path / "clean.db"
    out_dir = tmp_path / "clean_reports"

    # Use clean scanner with inactive ephemeral ports
    from detectors.ghost_daemons import GhostDaemonsDetector
    from detectors.context_rot import ContextRotDetector
    from detectors.ecosystem_pollution import EcosystemPollutionDetector
    from detectors.secret_zero import SecretZeroDetector
    from detectors.prompt_fatigue import PromptFatigueDetector

    clean_scanner = HealthScanner(
        detectors=[
            GhostDaemonsDetector(monitored_ports=[59981, 59982]),
            ContextRotDetector(),
            EcosystemPollutionDetector(),
            SecretZeroDetector(),
            PromptFatigueDetector(),
        ]
    )

    report, report_path = run_health_scan(
        workspace_root=str(ws_dir),
        db_path=str(db_path),
        output_dir=str(out_dir),
        custom_scanner=clean_scanner,
    )

    assert report.total_anomalies == 0
    assert report.entropy_score == 0.0
    assert os.path.exists(report_path)


def test_antigravity_sdk_trigger_creation(tmp_path: Path) -> None:
    """Tests SDK trigger factory function creates callable or trigger object."""
    ws_dir = tmp_path / "trigger_ws"
    ws_dir.mkdir()
    trigger = create_antigravity_sdk_trigger(
        interval_seconds=60,
        workspace_root=str(ws_dir),
        db_path=str(tmp_path / "trigger.db"),
    )
    assert trigger is not None
    assert callable(trigger) or hasattr(trigger, "interval") or hasattr(trigger, "__call__")


# =============================================================================
# 7. Red-Team Hardening & Mock Workspace Fixture Unit Tests
# =============================================================================
def test_red_team_hardened_destructive_patterns() -> None:
    """Verifies that hardened ArchitectureRedTeam rejects all broad destructive and kill patterns."""
    red_team = ArchitectureRedTeam()

    destructive_cmds = [
        "rmdir /s /q plugins",
        "del .env",
        "unlink .env.local",
        "rm -rf .agents",
        "drop table scan_sessions",
        "truncate table anomalies",
        "Remove-Item -Recurse plugins",
        "wipe database",
        "purge all temporary directories",
    ]

    for cmd in destructive_cmds:
        anom = AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path="some_file.md",
            severity=Severity.HIGH,
            description="Stale planning file",
            raw_details={"age_hours": 30.0},
        )
        res = red_team.audit_optimization(anom, proposed_action=cmd)
        assert res.verdict == RedTeamVerdict.REJECTED, f"Command '{cmd}' must be strictly REJECTED"
        assert res.confidence == 1.0

    # Test expanded kill patterns
    kill_cmds = [
        "wmic process delete",
        "Stop-Process -Id 1234",
        "delete process on port 3000",
        "pkill -9 nextjs",
        "sigkill python",
    ]

    for k_cmd in kill_cmds:
        ghost_anom = AnomalyRecord(
            detector_type=DetectorType.GHOST_DAEMONS,
            target_path="127.0.0.1:3000",
            severity=Severity.CRITICAL,
            description="Port 3000 occupied",
            raw_details={"port": 3000},
        )
        k_res = red_team.audit_optimization(ghost_anom, proposed_action=k_cmd)
        assert k_res.verdict == RedTeamVerdict.REJECTED, f"Kill command '{k_cmd}' must be strictly REJECTED"
        assert "strictly prohibited" in k_res.rationale

    # Test SECRET_ZERO destructive actions
    sec_anom = AnomalyRecord(
        detector_type=DetectorType.SECRET_ZERO,
        target_path=".env",
        severity=Severity.CRITICAL,
        description="Placeholder token in .env",
        raw_details={"token": "your_token_here"},
    )
    for sec_cmd in ["del .env", "unlink .env", "delete .env", "Remove-Item .env"]:
        s_res = red_team.audit_optimization(sec_anom, proposed_action=sec_cmd)
        assert s_res.verdict == RedTeamVerdict.REJECTED
        assert "strictly prohibited" in s_res.rationale


def test_mock_workspace_factory_all_five_patterns(tmp_path: Path) -> None:
    """Verifies that create_mock_workspace establishes all 5 historical failure patterns."""
    ws = Path(create_mock_workspace(str(tmp_path / "factory_ws")))

    # 1. Ghost Daemons
    assert (ws / ".daemons" / "ghost_server_3000.pid").exists()
    assert (ws / ".daemons" / "ghost_server_8000.pid").exists()

    # 2. Context Rot & Whitelisted Manifests
    stale_proposal = ws / "docs" / "stale_architecture_proposal.md"
    assert stale_proposal.exists()
    age_hours = (time.time() - stale_proposal.stat().st_mtime) / 3600.0
    assert age_hours >= 70.0  # ~72 hours old
    assert (ws / "PROJECT.md").exists()
    assert (ws / "GEMINI.md").exists()
    assert (ws / "README.md").exists()
    assert (ws / "BRIEFING.md").exists()

    # 3. Ecosystem Pollution
    assert (ws / ".gemini" / "config" / "plugins" / "mock_plugin.disabled" / "SKILL.md").exists()
    assert (ws / "content_creation" / "sports_cards" / "card_ladder_model.py").exists()
    assert (ws / "content_creation" / "card_ladder_export.py").exists()

    # 4. Secret Zero
    assert (ws / ".env").exists()
    assert (ws / ".env.example").exists()
    assert (ws / ".env.local").exists()
    env_content = (ws / ".env").read_text(encoding="utf-8")
    assert "your_token_here" in env_content

    # 5. Prompt Fatigue
    gemini_content = (ws / "GEMINI.md").read_text(encoding="utf-8")
    gemini_lines = gemini_content.splitlines()
    assert len(gemini_lines) > 100
    assert gemini_content.count("## R1. Workflow Distillation Directive") >= 2

