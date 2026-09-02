"""Comprehensive unit and integration tests for Architecture Red Team and Daily HITL Report Builder."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List
import pytest

from audit.red_team import ArchitectureRedTeam, is_whitelisted_file
from audit.report_builder import DailyReportBuilder
from database import get_historical_drift, init_db, log_scan_session
from models import (
    AnomalyRecord,
    DetectorType,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)
from tests.conftest import FileSystemSnapshot


# =============================================================================
# 1. Unit Tests: Whitelist Verification & Basic Filtering
# =============================================================================
def test_whitelisted_file_detection() -> None:
    """Test that all critical workspace manifests are accurately identified as whitelisted."""
    assert is_whitelisted_file("PROJECT.md") is True
    assert is_whitelisted_file("g:/workspace/PROJECT.md") is True
    assert is_whitelisted_file("GEMINI.md") is True
    assert is_whitelisted_file(".agents/worker_1/BRIEFING.md") is True
    assert is_whitelisted_file("ORIGINAL_REQUEST.md") is True
    assert is_whitelisted_file("README.md") is True
    assert is_whitelisted_file("pyproject.toml") is True
    assert is_whitelisted_file("package.json") is True
    assert is_whitelisted_file(".gitignore") is True

    # Non-whitelisted scratchpads
    assert is_whitelisted_file(".agents/worker_1/progress.md") is False
    assert is_whitelisted_file("scratchpad.md") is False
    assert is_whitelisted_file("temp_notes.txt") is False
    assert is_whitelisted_file("plugins/foo.disabled") is False


# =============================================================================
# 2. Unit Tests: Red-Team Scrutiny Across All 5 Detector Types
# =============================================================================
def test_red_team_rejects_automated_process_killing() -> None:
    """Test that ArchitectureRedTeam strictly REJECTS any automated taskkill / process termination."""
    red_team = ArchitectureRedTeam()

    # Ghost daemons anomaly with proposed automated kill
    anomaly = AnomalyRecord(
        detector_type=DetectorType.GHOST_DAEMONS,
        target_path="127.0.0.1:3000",
        severity=Severity.CRITICAL,
        description="Port collision on 3000 (WinError 10048)",
        raw_details={"port": 3000, "errno": 10048},
    )

    # 1. Explicit taskkill command
    result1 = red_team.audit_optimization(anomaly, proposed_action="taskkill /F /PID 1234")
    assert result1.verdict == RedTeamVerdict.REJECTED
    assert "strictly prohibited" in result1.rationale
    assert result1.confidence == 1.0

    # 2. os.kill / terminate
    result2 = red_team.audit_optimization(anomaly, proposed_action="terminate process on port 3000 via os.kill")
    assert result2.verdict == RedTeamVerdict.REJECTED

    # 3. kill -9
    result3 = red_team.audit_optimization(anomaly, proposed_action="kill -9 $(lsof -t -i:3000)")
    assert result3.verdict == RedTeamVerdict.REJECTED


def test_red_team_ghost_daemons_challenges_safe_diagnostics() -> None:
    """Test that ArchitectureRedTeam CHALLENGES ghost daemon port conflicts for manual review."""
    red_team = ArchitectureRedTeam()
    anomaly = AnomalyRecord(
        detector_type=DetectorType.GHOST_DAEMONS,
        target_path="127.0.0.1:8000",
        severity=Severity.CRITICAL,
        description="Port collision on 8000 (WinError 10048)",
        raw_details={"port": 8000, "errno": 10048},
    )

    result = red_team.audit_optimization(anomaly, proposed_action="Inspect active port bindings on 8000")
    assert result.verdict == RedTeamVerdict.CHALLENGED
    assert "8000" in result.recommended_action
    assert result.confidence >= 0.90


def test_red_team_context_rot_whitelisted_file_rejection() -> None:
    """Test that ArchitectureRedTeam strictly REJECTS deleting or removing whitelisted files."""
    red_team = ArchitectureRedTeam()

    whitelisted_targets = [
        "PROJECT.md",
        "GEMINI.md",
        "README.md",
        ".agents/worker_1/BRIEFING.md",
        "ORIGINAL_REQUEST.md",
    ]

    for target in whitelisted_targets:
        anomaly = AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path=target,
            severity=Severity.HIGH,
            description=f"Planning file {target} flagged for cleanup",
            raw_details={"age_hours": 72.0},
        )
        result = red_team.audit_optimization(anomaly, proposed_action=f"delete {target}")
        assert result.verdict == RedTeamVerdict.REJECTED, f"Must reject deleting {target}"
        assert "whitelist" in result.rationale.lower()


def test_red_team_context_rot_stale_scratchpad_approval() -> None:
    """Test that ArchitectureRedTeam APPROVES safe archival of stale scratchpads (>48h)."""
    red_team = ArchitectureRedTeam()
    anomaly = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path=".agents/worker_old/progress.md",
        severity=Severity.MEDIUM,
        description="Planning artifact older than 52.0h",
        raw_details={"age_hours": 52.0, "is_stale": True},
    )

    result = red_team.audit_optimization(anomaly, proposed_action="Archive to .agents/archive/")
    assert result.verdict == RedTeamVerdict.APPROVED
    assert "Safe archival approved" in result.rationale
    assert result.confidence == 1.0


def test_red_team_context_rot_borderline_staleness_challenged() -> None:
    """Test that ArchitectureRedTeam CHALLENGES borderline staleness (24h <= age < 48h) or active drafts."""
    red_team = ArchitectureRedTeam()

    # Case 1: 30 hours old
    anomaly1 = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path=".agents/worker_2/plan.md",
        severity=Severity.MEDIUM,
        description="Planning artifact 30.0 hours old",
        raw_details={"age_hours": 30.0},
    )
    res1 = red_team.audit_optimization(anomaly1)
    assert res1.verdict == RedTeamVerdict.CHALLENGED
    assert "Borderline staleness" in res1.rationale

    # Case 2: Active draft flag
    anomaly2 = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path="scratchpad.md",
        severity=Severity.LOW,
        description="Scratchpad draft",
        raw_details={"age_hours": 60.0, "is_active_draft": True},
    )
    res2 = red_team.audit_optimization(anomaly2)
    assert res2.verdict == RedTeamVerdict.CHALLENGED


def test_red_team_context_rot_fresh_file_rejected() -> None:
    """Test that ArchitectureRedTeam REJECTS false positive context rot on fresh files (<24h)."""
    red_team = ArchitectureRedTeam()
    anomaly = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path=".agents/worker_current/progress.md",
        severity=Severity.LOW,
        description="Progress file 3.5 hours old",
        raw_details={"age_hours": 3.5},
    )
    res = red_team.audit_optimization(anomaly, proposed_action="archive progress.md")
    assert res.verdict == RedTeamVerdict.REJECTED
    assert "Fresh artifact" in res.rationale


def test_red_team_ecosystem_pollution_audits() -> None:
    """Test ArchitectureRedTeam handles ecosystem pollution, user overrides, and destructive actions."""
    red_team = ArchitectureRedTeam()

    # 1. Clean unused disabled plugin -> APPROVED
    anomaly_clean = AnomalyRecord(
        detector_type=DetectorType.ECOSYSTEM_POLLUTION,
        target_path="plugins/gcp_spark.disabled",
        severity=Severity.HIGH,
        description="Unused .disabled plugin directory detected",
        raw_details={"is_disabled": True, "has_user_override": False},
    )
    res_clean = red_team.audit_optimization(anomaly_clean, proposed_action="Quarantine disabled plugin")
    assert res_clean.verdict == RedTeamVerdict.APPROVED
    assert res_clean.confidence >= 0.90

    # 2. Active user override -> CHALLENGED
    anomaly_override = AnomalyRecord(
        detector_type=DetectorType.ECOSYSTEM_POLLUTION,
        target_path="plugins/custom_tool.disabled",
        severity=Severity.MEDIUM,
        description="Plugin with active user override",
        raw_details={"is_disabled": True, "has_user_override": True},
    )
    res_override = red_team.audit_optimization(anomaly_override)
    assert res_override.verdict == RedTeamVerdict.CHALLENGED
    assert "Active user override detected" in res_override.rationale

    # 3. Destructive deletion -> REJECTED
    res_destructive = red_team.audit_optimization(anomaly_clean, proposed_action="rm -rf plugins/gcp_spark.disabled")
    assert res_destructive.verdict == RedTeamVerdict.REJECTED
    assert "permanent deletion" in res_destructive.rationale.lower()


def test_red_team_secret_zero_audits() -> None:
    """Test ArchitectureRedTeam approves non-destructive secret alerts and rejects deleting .env."""
    red_team = ArchitectureRedTeam()

    anomaly = AnomalyRecord(
        detector_type=DetectorType.SECRET_ZERO,
        target_path=".env",
        severity=Severity.CRITICAL,
        description="Placeholder token your_token_here in .env",
        raw_details={"token": "your_token_here", "line": 4},
    )

    # 1. Normal guidance -> APPROVED
    res_ok = red_team.audit_optimization(anomaly, proposed_action="Notify developer to configure valid API key")
    assert res_ok.verdict == RedTeamVerdict.APPROVED
    assert "your_token_here" in res_ok.rationale

    # 2. Attempt to delete .env -> REJECTED
    res_del = red_team.audit_optimization(anomaly, proposed_action="delete .env file")
    assert res_del.verdict == RedTeamVerdict.REJECTED


def test_red_team_prompt_fatigue_audits() -> None:
    """Test ArchitectureRedTeam scrutinizes GEMINI.md line bloat vs intentional documentation depth."""
    red_team = ArchitectureRedTeam()

    # 1. Truncating / deleting GEMINI.md -> REJECTED
    anomaly = AnomalyRecord(
        detector_type=DetectorType.PROMPT_FATIGUE,
        target_path="GEMINI.md",
        severity=Severity.MEDIUM,
        description="Manifest rule bloat: 179 lines",
        raw_details={"line_count": 179, "has_duplicates": False},
    )
    res_del = red_team.audit_optimization(anomaly, proposed_action="strip and delete rules from GEMINI.md")
    assert res_del.verdict == RedTeamVerdict.REJECTED
    assert "Automated truncation or deletion of GEMINI.md is strictly prohibited" in res_del.rationale

    # 2. Intentional documentation depth without duplicates -> CHALLENGED
    res_depth = red_team.audit_optimization(anomaly, proposed_action="Review rules with developer")
    assert res_depth.verdict == RedTeamVerdict.CHALLENGED
    assert "intentional documentation depth" in res_depth.rationale.lower()

    # 3. Redundant duplicate sections -> APPROVED for deduplication
    anomaly_dup = AnomalyRecord(
        detector_type=DetectorType.PROMPT_FATIGUE,
        target_path="GEMINI.md",
        severity=Severity.MEDIUM,
        description="Duplicate rule sections in GEMINI.md",
        raw_details={"line_count": 150, "has_duplicates": True},
    )
    res_dup = red_team.audit_optimization(anomaly_dup)
    assert res_dup.verdict == RedTeamVerdict.APPROVED
    assert "Duplicate rule sections detected" in res_dup.rationale


def test_red_team_audit_batch(sample_anomalies: List[AnomalyRecord]) -> None:
    """Test ArchitectureRedTeam.audit_batch processes all 5 anomalies with textual gradients."""
    red_team = ArchitectureRedTeam()
    gradients = [
        "Rule refinement: probe ports before launch",
        "Rule refinement: exclude BRIEFING.md from rot scan",
        "Rule refinement: isolate disabled plugins",
        "Rule refinement: alert on placeholder secrets",
        "Rule refinement: distill skills from GEMINI.md",
    ]

    results = red_team.audit_batch(sample_anomalies, gradients=gradients)
    assert len(results) == len(sample_anomalies)

    for res in results:
        assert isinstance(res, RedTeamAuditResult)
        assert res.verdict in {RedTeamVerdict.APPROVED, RedTeamVerdict.CHALLENGED, RedTeamVerdict.REJECTED}
        assert len(res.rationale) > 0
        assert len(res.recommended_action) > 0
        assert 0.0 <= res.confidence <= 1.0


# =============================================================================
# 3. Unit & Integration Tests: DailyReportBuilder
# =============================================================================
def test_daily_report_builder_sections_and_content(sample_anomalies: List[AnomalyRecord]) -> None:
    """Test DailyReportBuilder generates all 6 mandatory sections with accurate telemetry & checkboxes."""
    red_team = ArchitectureRedTeam()
    builder = DailyReportBuilder()

    gradients = [
        "Rule refinement: probe ports before launch",
        "Rule refinement: exclude BRIEFING.md from rot scan",
    ]
    audit_results = red_team.audit_batch(sample_anomalies, gradients=gradients)

    drift_data = {
        "total_sessions": 3,
        "total_anomalies": 12,
        "average_duration_ms": 42.5,
        "average_entropy_score": 0.65,
        "drift_detected": True,
    }

    scan_time = datetime(2026, 8, 25, 6, 0, 0, tzinfo=timezone.utc)
    session_id = "session-report-test-100"

    report = builder.build_daily_report(
        session_id=session_id,
        scan_time=scan_time,
        anomalies=sample_anomalies,
        gradients=gradients,
        audit_results=audit_results,
        historical_drift=drift_data,
        duration_ms=55.4,
        entropy=0.72,
    )

    # 1. Verify Top Header
    assert "# Daily System Health & Optimization Report — 2026-08-25 06:00:00 UTC" in report

    # 2. Verify 6 Mandatory Section Headers
    assert "## 1. Executive Summary & Health Telemetry" in report
    assert "## 2. Red-Team Scrutiny Verdicts" in report
    assert "## 3. Proposed Optimizations (HITL Checkboxes)" in report
    assert "## 4. Historical Failure Lifelines & Drift Analytics" in report
    assert "## 5. ProTeGi Textual Gradients for Self-Improvement" in report
    assert "## 6. Manual Remediation Command Guide" in report

    # 3. Verify Telemetry in Section 1
    assert f"`{session_id}`" in report
    assert "55.40 ms" in report
    assert "0.7200" in report
    assert "`GHOST_DAEMONS`" in report
    assert "`CONTEXT_ROT`" in report

    # 4. Verify Red-Team Critique Table in Section 2
    assert "| Category / Detector | Anomalies Count | Severity Distribution |" in report
    assert "| # | Detector | Target | Severity | Red-Team Verdict | Confidence | Rationale / Critique | Recommended Action |" in report

    # 5. Verify HITL Interactive Checkboxes in Section 3
    assert "- [ ] [HITL-APPROVED]" in report

    # 6. Verify 5 Historical Failure Lifelines in Section 4
    assert "Ghost Daemons" in report
    assert "Context Rot" in report
    assert "Ecosystem Pollution" in report
    assert "Secret Zero" in report
    assert "Prompt Fatigue" in report
    assert "DRIFT DETECTED" in report

    # 7. Verify Gradients in Section 5
    assert "Rule refinement: probe ports before launch" in report

    # 8. Verify Manual Command Guide in Section 6
    assert "Get-NetTCPConnection" in report
    assert "netstat -ano" in report
    assert "Select-String" in report


def test_daily_report_builder_clean_workspace() -> None:
    """Test DailyReportBuilder formats a clean report when 0 anomalies are detected."""
    builder = DailyReportBuilder()

    report = builder.build_daily_report(
        session_id="session-clean-001",
        scan_time="2026-08-25 07:00:00 UTC",
        anomalies=[],
        gradients=[],
        audit_results=[],
        historical_drift={"total_sessions": 1, "total_anomalies": 0, "drift_detected": False},
        duration_ms=10.0,
        entropy=0.0,
    )

    assert "## 1. Executive Summary & Health Telemetry" in report
    assert "All telemetry metrics nominal" in report
    assert "Approved: `0` | Challenged: `0` | Rejected: `0`" in report
    assert "Zero remediation actions required" in report
    assert "STABLE BASELINE" in report


# =============================================================================
# 4. Cryptographic SHA-256 FileSystemSnapshot Read-Only Immutability Test
# =============================================================================
def test_report_building_and_red_team_is_strictly_read_only(
    tmp_path: Path, sample_anomalies: List[AnomalyRecord]
) -> None:
    """Cryptographically verifies that ArchitectureRedTeam and DailyReportBuilder do not modify files."""
    # Create mock directory structure
    ws = tmp_path / "mock_workspace"
    ws.mkdir(parents=True)
    (ws / "PROJECT.md").write_text("# Project Spec\n", encoding="utf-8")
    (ws / "GEMINI.md").write_text("# Global Manifest\n", encoding="utf-8")
    (ws / ".env").write_text("API_KEY=your_token_here\n", encoding="utf-8")
    (ws / "stale_plan.md").write_text("Old plan notes\n", encoding="utf-8")

    # Take initial SHA256 snapshot
    snapshot = FileSystemSnapshot(str(ws))

    # Run red-team and report builder operations repeatedly
    red_team = ArchitectureRedTeam()
    builder = DailyReportBuilder()

    audit_results = red_team.audit_batch(sample_anomalies)
    report = builder.build_daily_report(
        session_id="snapshot-test-session",
        scan_time=datetime.now(timezone.utc),
        anomalies=sample_anomalies,
        gradients=["gradient 1"],
        audit_results=audit_results,
        historical_drift={},
        duration_ms=25.0,
        entropy=0.5,
    )

    assert len(report) > 500

    # Cryptographic proof that not a single byte was added, deleted, or altered
    snapshot.assert_untouched()


# =============================================================================
# 5. Integration Tests: End-to-End Pipeline Serialization & Boundary Cases
# =============================================================================
def test_red_team_audit_result_serialization_and_aliases() -> None:
    """Test RedTeamAuditResult dataclass serialization, to_dict, from_dict, and reason/counter_proposal aliases."""
    anomaly = AnomalyRecord(
        detector_type=DetectorType.SECRET_ZERO,
        target_path=".env.local",
        severity=Severity.HIGH,
        description="Placeholder key in local env",
        raw_details={"token": "YOUR_KEY_HERE"},
    )
    result = RedTeamAuditResult(
        anomaly=anomaly,
        verdict=RedTeamVerdict.APPROVED,
        rationale="Safe notification",
        risk_assessment="Low risk",
        recommended_action="Set local secret",
        confidence=0.98,
    )

    # Property / alias verification
    assert result.reason == "Safe notification"
    assert result.counter_proposal == "Set local secret"

    # Serialization
    d = result.to_dict()
    assert d["verdict"] == "APPROVED"
    assert d["confidence"] == 0.98
    assert d["reason"] == "Safe notification"

    # Deserialization
    reconstructed = RedTeamAuditResult.from_dict(d)
    assert reconstructed.verdict == RedTeamVerdict.APPROVED
    assert reconstructed.confidence == 0.98
    assert reconstructed.rationale == "Safe notification"


def test_red_team_audit_empty_batch() -> None:
    """Test ArchitectureRedTeam handles empty lists gracefully."""
    red_team = ArchitectureRedTeam()
    results = red_team.audit_batch([])
    assert results == []


def test_daily_report_builder_timestamp_formats(sample_anomalies: List[AnomalyRecord]) -> None:
    """Test DailyReportBuilder handles float/int timestamps and datetime objects."""
    red_team = ArchitectureRedTeam()
    builder = DailyReportBuilder()
    audit_results = red_team.audit_batch(sample_anomalies[:2])

    # Float timestamp
    rep_float = builder.build_daily_report(
        session_id="ts-float-test",
        scan_time=1756000000.0,
        anomalies=sample_anomalies[:2],
        gradients=["gradient 1"],
        audit_results=audit_results,
    )
    assert "ts-float-test" in rep_float
    assert "UTC" in rep_float

    # String timestamp
    rep_str = builder.build_daily_report(
        session_id="ts-str-test",
        scan_time="2026-08-25 12:34:56 UTC",
        anomalies=sample_anomalies[:2],
        gradients=[],
        audit_results=audit_results,
    )
    assert "2026-08-25 12:34:56 UTC" in rep_str

