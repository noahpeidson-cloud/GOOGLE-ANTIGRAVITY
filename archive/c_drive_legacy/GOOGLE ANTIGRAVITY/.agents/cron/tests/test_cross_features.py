"""Tier 3: Pairwise Cross-Feature Integration Suite (12 Integration Flows).

Exercises interactions and contracts between adjacent subsystems:
1. SQLite Telemetry + Detectors Pipeline Integration
2. SQLite Telemetry + ML Clustering & Vectorization Pipeline
3. Detectors + Architecture Red-Team Auditor Filtering
4. ML Textual Gradients + Daily HITL Report Builder
5. Red-Team Audit Results + Interactive Checkboxes Contract
6. Multi-Session Telemetry + Historical Drift Evolution
7. Exception Isolation Across Pipeline Components
8. Ghost Daemon Collision -> Red-Team Challenge -> Diagnostic Report
9. Context Rot Detection -> Zero Deletion AST Invariant
10. Secret Zero Placeholder -> SQLite Persistence -> Rotation Guidance
11. Ecosystem Pollution -> Red-Team Quarantine Guidance -> Report
12. Prompt Fatigue Bloat -> ML Feature Vectorization -> ProTeGi Refinement
"""

import os
import sqlite3
import time
from pathlib import Path
from typing import List

import pytest

try:
    from conftest import FileSystemSnapshot
except ImportError:
    try:
        from .conftest import FileSystemSnapshot
    except ImportError:
        import importlib.util
        conftest_path = Path(__file__).parent / "conftest.py"
        spec = importlib.util.spec_from_file_location("conftest_module", conftest_path)
        conftest_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conftest_module)
        FileSystemSnapshot = conftest_module.FileSystemSnapshot

from audit.red_team import ArchitectureRedTeam
from audit.report_builder import DailyReportBuilder
from database import (
    get_anomalies_for_session,
    get_historical_drift,
    get_historical_lifelines,
    get_session,
    get_textual_gradients_for_session,
    init_db,
    log_scan_session,
)
from detectors.context_rot import ContextRotDetector
from detectors.ecosystem_pollution import EcosystemPollutionDetector
from detectors.ghost_daemons import GhostDaemonsDetector
from detectors.prompt_fatigue import PromptFatigueDetector
from detectors.secret_zero import SecretZeroDetector
from ml.clustering import compute_semantic_entropy, kmeans_cluster
from ml.embeddings import vectorize_anomalies, vectorize_anomaly
from ml.protegi import CONVERGENCE_MESSAGE, generate_textual_gradients
from models import (
    AnomalyRecord,
    DetectorType,
    OptimizationReport,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)
from safety_guardrails import assert_safe_codebase
from scanner import HealthScanner
from scanner_daemon import create_mock_workspace, run_health_scan


# =============================================================================
# Flow 1: SQLite Telemetry + Detectors Pipeline Integration
# =============================================================================
def test_flow_1_sqlite_and_detectors_pipeline(tmp_path: Path) -> None:
    """Verifies that all detector anomalies flow smoothly into SQLite telemetry schema."""
    ws_dir = tmp_path / "flow1_ws"
    create_mock_workspace(str(ws_dir))
    db_path = str(tmp_path / "flow1.db")
    init_db(db_path)

    scanner = HealthScanner()
    anomalies = scanner.scan_workspace(str(ws_dir))
    assert len(anomalies) >= 4, "Detectors must produce anomaly records from mock workspace"

    session_id = "flow1-test-session-001"
    log_scan_session(
        session_id=session_id,
        anomalies=anomalies,
        gradients=["ProTeGi: optimize context window"],
        duration_ms=45.2,
        db_path=db_path,
    )

    persisted_sess = get_session(session_id, db_path=db_path)
    assert persisted_sess is not None
    assert persisted_sess["total_anomalies"] == len(anomalies)

    persisted_anomalies = get_anomalies_for_session(session_id, db_path=db_path)
    assert len(persisted_anomalies) == len(anomalies)

    detector_types_found = {a.detector_type.value for a in persisted_anomalies}
    assert DetectorType.CONTEXT_ROT.value in detector_types_found
    assert DetectorType.ECOSYSTEM_POLLUTION.value in detector_types_found
    assert DetectorType.SECRET_ZERO.value in detector_types_found
    assert DetectorType.PROMPT_FATIGUE.value in detector_types_found


# =============================================================================
# Flow 2: SQLite Telemetry + ML Clustering & Vectorization Pipeline
# =============================================================================
def test_flow_2_sqlite_ml_clustering_integration(tmp_path: Path) -> None:
    """Verifies anomaly records from SQLite are vectorized, clustered, and produce gradients."""
    db_path = str(tmp_path / "flow2.db")
    init_db(db_path)

    # Seed multiple sessions of anomaly data
    records = [
        AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path=f"file_{i}.md",
            severity=Severity.HIGH if i % 2 == 0 else Severity.MEDIUM,
            description=f"Stale planning file {i}",
            raw_details={"age_hours": 30.0 + i},
            timestamp=1756000000 + i * 100,
        )
        for i in range(12)
    ]
    log_scan_session("flow2-sess", records, [], 10.0, db_path=db_path)

    loaded_anomalies = get_anomalies_for_session("flow2-sess", db_path=db_path)
    assert len(loaded_anomalies) == 12

    matrix = vectorize_anomalies(loaded_anomalies)
    assert matrix.shape[0] == 12
    assert matrix.shape[1] == 5

    labels, centroids, inertia = kmeans_cluster(matrix, k=3, max_iter=20)
    assert labels.shape[0] == 12
    assert centroids.shape == (3, 5)

    entropy = compute_semantic_entropy(matrix, labels, centroids)
    assert 0.0 <= entropy <= 1.0

    gradients = generate_textual_gradients(loaded_anomalies, labels, centroids, entropy)
    assert len(gradients) >= 1
    assert any("CONTEXT_ROT" in g or "ProTeGi" in g for g in gradients)


# =============================================================================
# Flow 3: Detectors + Architecture Red-Team Auditor Filtering
# =============================================================================
def test_flow_3_detectors_red_team_auditor_filtering(tmp_path: Path) -> None:
    """Verifies detector outputs undergo adversarial audit and receive calibrated verdicts."""
    ws_dir = tmp_path / "flow3_ws"
    create_mock_workspace(str(ws_dir))

    # Add a whitelisted file that looks stale to test challenge / rejection
    agents_dir = ws_dir / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    stale_briefing = agents_dir / "BRIEFING.md"
    stale_briefing.write_text("# 🔒 My Identity\nImmutable briefing\n", encoding="utf-8")
    stale_ts = time.time() - (48 * 3600)
    os.utime(str(stale_briefing), (stale_ts, stale_ts))

    scanner = HealthScanner()
    anomalies = scanner.scan_workspace(str(ws_dir))

    red_team = ArchitectureRedTeam()
    audit_results = red_team.audit_batch(anomalies)

    assert len(audit_results) == len(anomalies)
    verdicts = {r.verdict for r in audit_results}
    assert RedTeamVerdict.APPROVED in verdicts or RedTeamVerdict.CHALLENGED in verdicts or RedTeamVerdict.REJECTED in verdicts

    # All audit results must have non-empty rationale and action
    for r in audit_results:
        assert len(r.rationale) > 0
        assert len(r.recommended_action) > 0
        assert len(r.risk_assessment) > 0


# =============================================================================
# Flow 4: ML Textual Gradients + Daily HITL Report Builder
# =============================================================================
def test_flow_4_ml_gradients_and_report_builder(tmp_path: Path) -> None:
    """Verifies that ML textual gradients and entropy scores render accurately in HITL Markdown."""
    sample_audits = [
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path=".agents/scratch_48h.md",
                severity=Severity.HIGH,
                description="Stale planning scratchpad",
                raw_details={"age_hours": 48.0},
            ),
            verdict=RedTeamVerdict.APPROVED,
            rationale="Scratchpad is unreferenced and past 24h retention window",
            risk_assessment="Low risk",
            recommended_action="Archive scratchpad to .agents/archive/",
        ),
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.GHOST_DAEMONS,
                target_path="127.0.0.1:3000",
                severity=Severity.CRITICAL,
                description="Port 3000 occupied",
                raw_details={"port": 3000},
            ),
            verdict=RedTeamVerdict.CHALLENGED,
            rationale="Automated taskkill forbidden under Rule R3",
            risk_assessment="High risk of aborting active server",
            recommended_action="Run `netstat -ano | findstr :3000` for diagnosis",
        ),
    ]

    gradients = [
        "ProTeGi Textual Gradient [Cluster 0]: Context window bloat detected from unindexed scratchpads.",
        "ProTeGi Textual Gradient [Cluster 1]: Ghost daemon socket collision patterns observed.",
    ]

    drift_stats = {
        "total_sessions": 4,
        "total_anomalies": 18,
        "historical_lifelines_count": 5,
        "drift_detected": True,
        "average_duration_ms": 24.5,
    }

    builder = DailyReportBuilder()
    report_content = builder.build_daily_report(
        session_id="flow4-session",
        scan_time=time.time(),
        anomalies=[a.anomaly for a in sample_audits],
        gradients=gradients,
        audit_results=sample_audits,
        historical_drift=drift_stats,
        duration_ms=52.3,
        entropy=0.4821,
    )

    assert "Daily System Health & Optimization Report" in report_content
    assert "0.4821" in report_content
    assert "ProTeGi Textual Gradient" in report_content
    assert "Historical Failure Lifelines & Drift Analytics" in report_content
    assert "- [ ]" in report_content, "Interactive checkboxes must be present for HITL approval"


# =============================================================================
# Flow 5: Red-Team Audit Results + Interactive Checkboxes Contract
# =============================================================================
def test_flow_5_red_team_audit_and_checkboxes_contract(tmp_path: Path) -> None:
    """Verifies that APPROVED items receive checkboxes, while CHALLENGED/REJECTED receive diagnostic warnings."""
    results = [
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                target_path="plugins/old.disabled",
                severity=Severity.HIGH,
                description="Disabled plugin folder",
                raw_details={},
            ),
            verdict=RedTeamVerdict.APPROVED,
            rationale="Unused disabled plugin directory confirmed",
            risk_assessment="Zero risk",
            recommended_action="Quarantine directory",
        ),
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path="PROJECT.md",
                severity=Severity.MEDIUM,
                description="Project spec file",
                raw_details={},
            ),
            verdict=RedTeamVerdict.REJECTED,
            rationale="PROJECT.md is the permanent workspace contract",
            risk_assessment="Severe risk of project spec loss",
            recommended_action="Retain permanently",
        ),
    ]

    builder = DailyReportBuilder()
    content = builder.build_daily_report(
        session_id="flow5-sess",
        scan_time=time.time(),
        anomalies=[a.anomaly for a in results],
        gradients=[],
        audit_results=results,
        historical_drift={},
        duration_ms=15.0,
        entropy=0.1,
    )

    # Checkbox for APPROVED item
    assert "- [ ]" in content
    assert "plugins/old.disabled" in content
    # REJECTED item in challenged/rejected section
    assert "PROJECT.md" in content
    assert "REJECTED" in content


# =============================================================================
# Flow 6: Multi-Session Telemetry + Historical Drift Evolution
# =============================================================================
def test_flow_6_multisession_telemetry_and_drift_evolution(tmp_path: Path) -> None:
    """Verifies sequential scan sessions accumulate telemetry and compute accurate drift evolution."""
    ws_dir = tmp_path / "flow6_ws"
    create_mock_workspace(str(ws_dir))
    db_path = str(tmp_path / "flow6_telemetry.db")
    out_dir = str(tmp_path / "flow6_reports")

    session_ids = []
    for i in range(5):
        rep, _ = run_health_scan(str(ws_dir), db_path, out_dir)
        session_ids.append(rep.session_id)

    assert len(set(session_ids)) == 5

    drift = get_historical_drift(db_path=db_path)
    assert drift["total_sessions"] == 5
    assert drift["historical_lifelines_count"] == 5
    assert drift["total_anomalies"] > 0
    assert drift["average_duration_ms"] > 0.0

    lifelines = get_historical_lifelines(db_path=db_path)
    assert len(lifelines) == 5


# =============================================================================
# Flow 7: Exception Isolation Across Pipeline Components
# =============================================================================
def test_flow_7_exception_isolation_across_components(tmp_path: Path) -> None:
    """Verifies that malformed or edge-case inputs do not crash the end-to-end scanner pipeline."""
    ws_dir = tmp_path / "flow7_corrupt_ws"
    ws_dir.mkdir()
    db_path = str(tmp_path / "flow7.db")
    out_dir = str(tmp_path / "flow7_reports")

    # Create unreadable or binary-filled files
    (ws_dir / ".env").write_bytes(b"\x00\xff\xfe\x00\xaa\xbb\xcc\xdd")
    (ws_dir / "GEMINI.md").write_bytes(b"\x00" * 5000)
    (ws_dir / "unusual_file.unknown").write_text("random binary simulation", encoding="utf-8")

    rep, report_path = run_health_scan(str(ws_dir), db_path, out_dir)
    assert isinstance(rep, OptimizationReport)
    assert os.path.exists(report_path)
    assert rep.session_id is not None


# =============================================================================
# Flow 8: Ghost Daemon Collision -> Red-Team Challenge -> Diagnostic Report
# =============================================================================
def test_flow_8_ghost_daemon_socket_collision_to_report(tmp_path: Path) -> None:
    """Verifies ghost daemon port detections trigger Red-Team challenges and non-destructive diagnostic guidance."""
    detector = GhostDaemonsDetector(monitored_ports=[8000])

    # Inject mock occupied anomaly
    anom = AnomalyRecord(
        detector_type=DetectorType.GHOST_DAEMONS,
        target_path="127.0.0.1:8000",
        severity=Severity.CRITICAL,
        description="Ghost daemon detected: port 8000 is occupied / unmonitored",
        raw_details={"port": 8000, "status": "OCCUPIED", "errno": 10048},
    )

    red_team = ArchitectureRedTeam()
    audit_results = red_team.audit_batch([anom])
    assert len(audit_results) == 1
    result = audit_results[0]
    assert result.verdict in {RedTeamVerdict.CHALLENGED, RedTeamVerdict.REJECTED}
    assert "kill" not in result.recommended_action.lower() or "avoid" in result.recommended_action.lower()

    builder = DailyReportBuilder()
    content = builder.build_daily_report(
        session_id="flow8-sess",
        scan_time=time.time(),
        anomalies=[anom],
        gradients=[],
        audit_results=audit_results,
        historical_drift={},
        duration_ms=12.0,
        entropy=0.25,
    )
    assert "Ghost Daemon" in content or "GHOST_DAEMONS" in content
    assert "8000" in content


# =============================================================================
# Flow 9: Context Rot Detection -> Zero Deletion AST Invariant
# =============================================================================
def test_flow_9_context_rot_to_ast_guardrails(tmp_path: Path) -> None:
    """Verifies context rot detector finds stale files while AST analyzer proves code is strictly non-destructive."""
    ws_dir = tmp_path / "flow9_ws"
    ws_dir.mkdir()
    agents_dir = ws_dir / ".agents" / "stale_run"
    agents_dir.mkdir(parents=True)
    stale_file = agents_dir / "old_plan.md"
    stale_file.write_text("# Old Plan\nOld content\n", encoding="utf-8")
    old_time = time.time() - (72 * 3600)
    os.utime(str(stale_file), (old_time, old_time))

    snapshot = FileSystemSnapshot(str(ws_dir))

    detector = ContextRotDetector(threshold_hours=24.0)
    anomalies = detector.scan(str(ws_dir))
    assert len(anomalies) >= 1

    # Verify file was NOT modified or deleted
    snapshot.assert_untouched()

    # Codebase safety check
    cron_dir = Path(__file__).resolve().parent.parent
    assert_safe_codebase(str(cron_dir), exclude_dirs=["tests"])


# =============================================================================
# Flow 10: Secret Zero Placeholder -> SQLite Persistence -> Rotation Guidance
# =============================================================================
def test_flow_10_secret_zero_placeholder_to_sqlite_and_report(tmp_path: Path) -> None:
    """Verifies placeholder tokens in .env files are logged to SQLite and highlighted in daily report."""
    ws_dir = tmp_path / "flow10_ws"
    ws_dir.mkdir()
    env_file = ws_dir / ".env"
    env_file.write_text("DATABASE_URL=postgres://...\nAPI_KEY=your_token_here\n", encoding="utf-8")

    db_path = str(tmp_path / "flow10.db")
    out_dir = str(tmp_path / "flow10_reports")

    rep, report_path = run_health_scan(str(ws_dir), db_path, out_dir)
    assert rep.total_anomalies >= 1

    secret_anomalies = [
        a for a in rep.audited_anomalies
        if a.anomaly and a.anomaly.detector_type == DetectorType.SECRET_ZERO
    ]
    assert len(secret_anomalies) >= 1
    assert secret_anomalies[0].verdict == RedTeamVerdict.APPROVED

    with open(report_path, "r", encoding="utf-8") as f:
        report_text = f.read()
    assert "your_token_here" in report_text or "SECRET_ZERO" in report_text or "Secret Zero" in report_text


# =============================================================================
# Flow 11: Ecosystem Pollution -> Red-Team Quarantine Guidance -> Report
# =============================================================================
def test_flow_11_ecosystem_pollution_to_red_team_approval(tmp_path: Path) -> None:
    """Verifies .disabled plugin directories are detected, approved for quarantine, and presented to user."""
    ws_dir = tmp_path / "flow11_ws"
    ws_dir.mkdir()
    plugins_dir = ws_dir / "plugins"
    (plugins_dir / "bigquery_ai.disabled").mkdir(parents=True)
    (plugins_dir / "bigquery_ai.disabled" / "SKILL.md").write_text("# Disabled skill\n", encoding="utf-8")

    db_path = str(tmp_path / "flow11.db")
    out_dir = str(tmp_path / "flow11_reports")

    rep, report_path = run_health_scan(str(ws_dir), db_path, out_dir)
    pollution_items = [
        a for a in rep.audited_anomalies
        if a.anomaly and a.anomaly.detector_type == DetectorType.ECOSYSTEM_POLLUTION
    ]
    assert len(pollution_items) >= 1
    assert pollution_items[0].verdict == RedTeamVerdict.APPROVED
    assert "quarantine" in pollution_items[0].recommended_action.lower() or "archive" in pollution_items[0].recommended_action.lower()


# =============================================================================
# Flow 12: Prompt Fatigue Bloat -> ML Feature Vectorization -> ProTeGi Refinement
# =============================================================================
def test_flow_12_prompt_fatigue_to_ml_vectorization(tmp_path: Path) -> None:
    """Verifies oversized GEMINI.md is vectorized, clustered, and triggers ProTeGi rule distillation diffs."""
    ws_dir = tmp_path / "flow12_ws"
    ws_dir.mkdir()
    gemini_file = ws_dir / "GEMINI.md"
    lines = ["# Manifest\n"] + [f"Rule {i}: Do something specific and verbose\n" for i in range(160)]
    gemini_file.write_text("".join(lines), encoding="utf-8")

    detector = PromptFatigueDetector(max_lines=100)
    anomalies = detector.scan(str(ws_dir))
    assert len(anomalies) == 1
    anom = anomalies[0]
    assert anom.detector_type == DetectorType.PROMPT_FATIGUE

    # Run vectorization & clustering
    feat_matrix = vectorize_anomalies([anom])
    assert feat_matrix.shape == (1, 5)

    labels, centroids, inertia = kmeans_cluster(feat_matrix, k=1, max_iter=10)
    assert labels.shape == (1,)

    entropy = compute_semantic_entropy(feat_matrix, labels, centroids)
    assert 0.0 <= entropy <= 1.0

    gradients = generate_textual_gradients([anom], labels, centroids, entropy=0.2)
    assert len(gradients) >= 1
    assert "PROMPT_FATIGUE" in gradients[0] or "GEMINI.md" in gradients[0] or "Manifest" in gradients[0] or "distill" in gradients[0].lower()
