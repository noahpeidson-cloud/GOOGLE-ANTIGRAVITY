"""Independent Forensic Integrity Audit Script for Milestone 5."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CRON_DIR = Path("g:/My Drive/GOOGLE ANTIGRAVITY/.agents/cron").resolve()
sys.path.insert(0, str(CRON_DIR))

from audit.red_team import ArchitectureRedTeam
from audit.report_builder import DailyReportBuilder
from database import (
    get_anomalies_for_session,
    get_historical_drift,
    get_historical_lifelines,
    get_session,
    get_textual_gradients_for_session,
    init_db,
)
from fixtures.mock_workspace_factory import MockDaemonListener, create_mock_workspace
from ml.clustering import compute_semantic_entropy, kmeans_cluster
from ml.embeddings import vectorize_anomalies
from ml.protegi import generate_textual_gradients
from models import (
    AnomalyRecord,
    DetectorType,
    OptimizationReport,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)
from safety_guardrails import assert_safe_codebase, scan_file_for_safety
from scanner import HealthScanner
from scanner_daemon import (
    build_cli_parser,
    create_antigravity_sdk_trigger,
    main,
    run_health_scan,
)


def compute_dir_sha256(directory: str) -> dict:
    """Computes SHA-256 hashes of all files in a directory."""
    hashes = {}
    for root, _, files in os.walk(directory):
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, directory).replace("\\", "/")
            with open(p, "rb") as fh:
                hashes[rel] = hashlib.sha256(fh.read()).hexdigest()
    return hashes


def test_audit_safety_and_ast() -> None:
    print("[CHECK 1] Verifying 0 destructive calls across all production files via AST...")
    assert_safe_codebase(str(CRON_DIR), exclude_dirs=["tests", "__pycache__"])
    print("  -> AST safety check PASSED with 0 violations.")


def test_audit_mock_workspace_generation() -> None:
    print("[CHECK 2] Verifying authentic mock workspace factory (all 5 patterns)...")
    with tempfile.TemporaryDirectory() as td:
        ws = Path(create_mock_workspace(td))

        # 1. Ghost Daemons
        p3000 = ws / ".daemons" / "ghost_server_3000.pid"
        p8000 = ws / ".daemons" / "ghost_server_8000.pid"
        assert p3000.exists() and "3000" in p3000.read_text()
        assert p8000.exists() and "8000" in p8000.read_text()

        # 2. Context Rot
        stale_prop = ws / "docs" / "stale_architecture_proposal.md"
        assert stale_prop.exists()
        age_hours = (time.time() - stale_prop.stat().st_mtime) / 3600.0
        assert age_hours >= 70.0
        assert (ws / "PROJECT.md").exists()
        assert (ws / "GEMINI.md").exists()

        # 3. Ecosystem Pollution
        assert (ws / ".gemini" / "config" / "plugins" / "mock_plugin.disabled" / "SKILL.md").exists()
        assert (ws / "content_creation" / "sports_cards" / "card_ladder_model.py").exists()

        # 4. Secret Zero
        assert (ws / ".env").exists()
        assert "your_token_here" in (ws / ".env").read_text()

        # 5. Prompt Fatigue
        gemini_txt = (ws / "GEMINI.md").read_text()
        lines = gemini_txt.splitlines()
        assert len(lines) > 100
        assert gemini_txt.count("## R1. Workflow Distillation Directive") >= 2

    print("  -> Mock workspace factory PASSED with authentic patterns.")


def test_audit_9_step_pipeline() -> None:
    print("[CHECK 3] Verifying authentic 9-step dataflow orchestration in run_health_scan()...")
    with tempfile.TemporaryDirectory() as td:
        ws_dir = os.path.join(td, "ws")
        db_path = os.path.join(td, "telemetry.db")
        out_dir = os.path.join(td, "reports")
        create_mock_workspace(ws_dir)

        # Snapshot before
        pre_hashes = compute_dir_sha256(ws_dir)

        report, report_path = run_health_scan(
            workspace_root=ws_dir,
            db_path=db_path,
            output_dir=out_dir,
            k_clusters=3,
        )

        # Snapshot after
        post_hashes = compute_dir_sha256(ws_dir)
        assert pre_hashes == post_hashes, "Workspace was mutated during scan!"

        # Verify Report Object Contract
        assert isinstance(report, OptimizationReport)
        assert report.total_anomalies > 0
        assert len(report.audited_anomalies) == report.total_anomalies
        assert len(report.textual_gradients) > 0
        assert report.entropy_score > 0.0

        # Verify DB Persistence
        sess = get_session(report.session_id, db_path=db_path)
        assert sess is not None
        assert sess["total_anomalies"] == report.total_anomalies

        anoms = get_anomalies_for_session(report.session_id, db_path=db_path)
        assert len(anoms) == report.total_anomalies

        grads = get_textual_gradients_for_session(report.session_id, db_path=db_path)
        assert len(grads) == len(report.textual_gradients)

        lifelines = get_historical_lifelines(db_path=db_path)
        assert len(lifelines) == 5

        # Verify Report File Content
        assert os.path.exists(report_path)
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "## 1. Executive Summary & Health Telemetry" in content
        assert "## 2. Red-Team Scrutiny Verdicts" in content
        assert "## 3. Proposed Optimizations (HITL Checkboxes)" in content
        assert "## 4. Historical Failure Lifelines & Drift Analytics" in content
        assert "## 5. ProTeGi Textual Gradients for Self-Improvement" in content
        assert "## 6. Manual Remediation Command Guide" in content

    print("  -> 9-step dataflow orchestration PASSED.")


def test_audit_cli_standalone() -> None:
    print("[CHECK 4] Verifying standalone CLI subprocess execution (--run-once --mock-env)...")
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "cli.db")
        out_dir = os.path.join(td, "cli_reports")

        cmd = [
            sys.executable,
            str(CRON_DIR / "scanner_daemon.py"),
            "--run-once",
            "--mock-env",
            "--db",
            db_path,
            "--output-dir",
            out_dir,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"CLI exited with {res.returncode}: {res.stderr}"
        assert "ANTIGRAVITY HEALTH SCAN COMPLETE:" in res.stdout
        assert "Total Anomalies Detected :" in res.stdout
        assert "Red-Team Approved" in res.stdout
        assert "Red-Team Challenged" in res.stdout

        reports = list(Path(out_dir).glob("daily_health_report_*.md"))
        assert len(reports) == 1
        assert reports[0].stat().st_size > 500

    print("  -> Standalone CLI subprocess execution PASSED.")


def test_audit_adversarial_clean_and_stress() -> None:
    print("[CHECK 5] Stress-testing edge cases: clean workspace, large anomaly batches, K variations...")
    with tempfile.TemporaryDirectory() as td:
        # Clean workspace
        clean_ws = os.path.join(td, "clean_ws")
        os.makedirs(clean_ws)
        with open(os.path.join(clean_ws, "PROJECT.md"), "w") as f:
            f.write("# Spec\n")
        with open(os.path.join(clean_ws, "GEMINI.md"), "w") as f:
            f.write("# Rules\n## R1. Test\nOk.\n")

        db_path = os.path.join(td, "clean.db")
        out_dir = os.path.join(td, "clean_reports")

        rep, rep_path = run_health_scan(
            workspace_root=clean_ws,
            db_path=db_path,
            output_dir=out_dir,
            custom_scanner=HealthScanner(detectors=[]),
        )
        assert rep.total_anomalies == 0
        assert rep.entropy_score == 0.0
        assert os.path.exists(rep_path)

        # Test K variations
        from fixtures.mock_workspace_factory import create_mock_workspace
        ws_m = os.path.join(td, "ws_m")
        create_mock_workspace(ws_m)
        for k in [1, 2, 4, 5]:
            r_k, _ = run_health_scan(
                workspace_root=ws_m,
                db_path=os.path.join(td, f"k_{k}.db"),
                output_dir=os.path.join(td, f"out_{k}"),
                k_clusters=k,
            )
            assert r_k.total_anomalies > 0
            assert isinstance(r_k.entropy_score, float)

    print("  -> Adversarial edge-case tests PASSED.")


if __name__ == "__main__":
    test_audit_safety_and_ast()
    test_audit_mock_workspace_generation()
    test_audit_9_step_pipeline()
    test_audit_cli_standalone()
    test_audit_adversarial_clean_and_stress()
    print("\n=======================================================")
    print("ALL FORENSIC VERIFICATION CHECKS PASSED: VERDICT = CLEAN")
    print("=======================================================")
