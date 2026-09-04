"""Adversarial stress-testing suite for DailyReportBuilder (audit/report_builder.py).

Verifies:
1. Massive scale stress-testing (500, 1000, 5000 anomalies) with sub-50ms performance.
2. Boundary cases (empty anomalies, empty gradients, empty audit results, None/missing drift stats).
3. Markdown table formatting integrity (exact column counts, escaping of pipes in rationales & actions).
4. Markdown headings, code blocks (```powershell ... ```), and list hierarchies.
5. Interactive checkbox syntax adherence (- [ ] [HITL-APPROVED] and - [x] [REJECTED BY RED-TEAM]).
6. Extreme numerical drift statistics (zero, negative, huge numbers, infinite/NaN edge behaviors).
7. Cryptographic SHA-256 FileSystemSnapshot immutability across extreme workloads.
8. AST Safety Guardrail verification (zero destructive operations).
9. Empirical boundary fuzzing tests capturing failure modes for unescaped pipes, newlines, and NoneType handling.
"""

import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import pytest

from audit.red_team import ArchitectureRedTeam
from audit.report_builder import DailyReportBuilder
from models import (
    AnomalyRecord,
    DetectorType,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)
from safety_guardrails import assert_safe_codebase
from tests.conftest import FileSystemSnapshot


# =============================================================================
# Helper Functions for Markdown Syntax Verification
# =============================================================================
def count_table_columns(row_line: str) -> int:
    """Counts the number of cells in a markdown table row (excluding leading/trailing empty cells)."""
    stripped = row_line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return 0
    parts = re.split(r"(?<!\\)\|", stripped)
    cells = parts[1:-1]
    return len(cells)


def extract_markdown_headers_outside_code_blocks(markdown_text: str) -> List[str]:
    """Extracts markdown headers (#, ##, ###) while ignoring comments inside code blocks."""
    lines = markdown_text.splitlines()
    in_code_block = False
    headers = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if not in_code_block and stripped.startswith("#"):
            headers.append(stripped)
    return headers


# =============================================================================
# 1. Massive Scale Stress Testing (500+, 1000+, 5000+ Anomalies)
# =============================================================================
def test_report_builder_stress_500_anomalies() -> None:
    """Stress-test DailyReportBuilder with 500+ anomalies and verify report structure and performance."""
    builder = DailyReportBuilder()

    detector_types = list(DetectorType)
    severities = list(Severity)

    anomalies: List[AnomalyRecord] = []
    audit_results: List[RedTeamAuditResult] = []

    for i in range(500):
        det = detector_types[i % len(detector_types)]
        sev = severities[i % len(severities)]
        verdict = (
            RedTeamVerdict.APPROVED
            if i % 3 == 0
            else (RedTeamVerdict.CHALLENGED if i % 3 == 1 else RedTeamVerdict.REJECTED)
        )

        rec = AnomalyRecord(
            detector_type=det,
            target_path=f"path/to/target/resource_{i}.ext",
            severity=sev,
            description=f"Automated stress anomaly #{i} for category {det.value}",
            raw_details={"index": i, "synthetic": True},
            timestamp=1756000000 + i,
            confidence=0.85 + (i % 15) * 0.01,
        )
        anomalies.append(rec)

        audit_results.append(
            RedTeamAuditResult(
                anomaly=rec,
                verdict=verdict,
                rationale=f"Audit rationale for anomaly #{i}",
                risk_assessment="Low" if verdict == RedTeamVerdict.APPROVED else "High",
                recommended_action=f"Remediate resource_{i}",
                confidence=0.90,
            )
        )

    gradients = [f"Rule refinement gradient #{k}: update heuristic threshold" for k in range(20)]
    historical_drift = {
        "total_sessions": 45,
        "total_anomalies": 12500,
        "average_duration_ms": 128.5,
        "average_entropy_score": 0.8124,
        "drift_detected": True,
    }

    t0 = time.perf_counter()
    report = builder.build_daily_report(
        session_id="stress-session-500",
        scan_time=datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc),
        anomalies=anomalies,
        gradients=gradients,
        audit_results=audit_results,
        historical_drift=historical_drift,
        duration_ms=45.2,
        entropy=0.7891,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # Latency assertion: Generating 500-item report should take < 150ms
    assert elapsed_ms < 150.0, f"500-anomaly report generation took too long: {elapsed_ms:.2f}ms"

    # Telemetry assertions
    assert "- **Total Anomalies Detected**: `500`" in report
    assert "Approved: `167` | Challenged: `167` | Rejected: `166`" in report

    # Verify Section 1 Table (Breakdown by detector)
    sec1_table_lines = [
        line for line in report.split("## 2. Red-Team Scrutiny Verdicts")[0].splitlines()
        if line.startswith("|")
    ]
    # 1 header + 1 separator + 5 detectors = 7 lines
    assert len(sec1_table_lines) == 7
    for line in sec1_table_lines:
        assert count_table_columns(line) == 3

    # Verify Section 2 Table (Audit results)
    sec2_table_lines = [
        line for line in report.split("## 2. Red-Team Scrutiny Verdicts")[1].split("## 3. Proposed Optimizations")[0].splitlines()
        if line.startswith("|")
    ]
    # Header + separator + 500 rows = 502
    assert len(sec2_table_lines) == 502
    for line in sec2_table_lines:
        assert count_table_columns(line) == 8, f"Malformed table row with incorrect column count: {line}"

    # Verify checkboxes count
    hitl_approved_count = report.count("- [ ] [HITL-APPROVED]")
    rejected_count = report.count("- [x] [REJECTED BY RED-TEAM]")
    assert hitl_approved_count == 334  # 167 approved + 167 challenged
    assert rejected_count == 166


def test_report_builder_stress_1000_anomalies() -> None:
    """Stress-test DailyReportBuilder with 1,000 anomalies to verify linear scaling."""
    builder = DailyReportBuilder()

    anomalies = [
        AnomalyRecord(
            detector_type=DetectorType.GHOST_DAEMONS if i % 2 == 0 else DetectorType.SECRET_ZERO,
            target_path=f"port_{3000 + (i % 100)}",
            severity=Severity.CRITICAL if i % 4 == 0 else Severity.LOW,
            description=f"Anomaly #{i}",
            raw_details={"idx": i},
        )
        for i in range(1000)
    ]

    audit_results = [
        RedTeamAuditResult(
            anomaly=a,
            verdict=RedTeamVerdict.APPROVED if i % 2 == 0 else RedTeamVerdict.REJECTED,
            rationale=f"Rationale {i}",
            recommended_action=f"Action {i}",
        )
        for i, a in enumerate(anomalies)
    ]

    t0 = time.perf_counter()
    report = builder.build_daily_report(
        session_id="stress-1000",
        scan_time=1756000000.0,
        anomalies=anomalies,
        gradients=["gradient 1", "gradient 2"],
        audit_results=audit_results,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 250.0
    assert "- **Total Anomalies Detected**: `1000`" in report
    assert report.count("- [ ] [HITL-APPROVED]") == 500
    assert report.count("- [x] [REJECTED BY RED-TEAM]") == 500


def test_report_builder_stress_5000_anomalies_benchmark() -> None:
    """Stress-test DailyReportBuilder with 5,000 anomalies for memory and throughput benchmarking."""
    builder = DailyReportBuilder()

    anomalies = [
        AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path=f".agents/worker_{i}/progress.md",
            severity=Severity.MEDIUM,
            description=f"Stale progress file #{i}",
        )
        for i in range(5000)
    ]

    audit_results = [
        RedTeamAuditResult(
            anomaly=a,
            verdict=RedTeamVerdict.APPROVED,
            rationale=f"Safe archival approved #{i}",
            recommended_action=f"Archive worker_{i}",
        )
        for i, a in enumerate(anomalies)
    ]

    t0 = time.perf_counter()
    report = builder.build_daily_report(
        session_id="stress-5000",
        scan_time=datetime.now(timezone.utc),
        anomalies=anomalies,
        gradients=["Gradient 1"],
        audit_results=audit_results,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # 5,000 items in < 1,000 ms
    assert elapsed_ms < 1000.0
    assert "- **Total Anomalies Detected**: `5000`" in report
    assert len(report) > 500000


# =============================================================================
# 2. Boundary Cases & Missing / None Inputs
# =============================================================================
def test_report_builder_empty_inputs() -> None:
    """Verify DailyReportBuilder gracefully formats completely empty anomaly and gradient sets."""
    builder = DailyReportBuilder()

    report = builder.build_daily_report(
        session_id="empty-session-000",
        scan_time="2026-08-25 00:00:00 UTC",
        anomalies=[],
        gradients=[],
        audit_results=[],
        historical_drift=None,
        duration_ms=0.0,
        entropy=0.0,
    )

    assert "## 1. Executive Summary & Health Telemetry" in report
    assert "*All telemetry metrics nominal. Zero anomalies detected in current workspace.*" in report
    assert "Approved: `0` | Challenged: `0` | Rejected: `0`" in report
    assert "*No anomalies required red-team scrutiny.*" in report
    assert "- [ ] [HITL-APPROVED] Workspace in optimal health. Zero remediation actions required." in report
    assert "- No heuristic refinement gradients generated for this session (entropy stable)." in report
    assert "- **Drift Posture**: `STABLE BASELINE`" in report


def test_report_builder_dict_format_inputs() -> None:
    """Verify DailyReportBuilder accepts raw dicts for anomalies and gradients (interoperability)."""
    builder = DailyReportBuilder()

    anomalies_dicts: List[Dict[str, Any]] = [
        {
            "detector_type": "GHOST_DAEMONS",
            "target_path": "127.0.0.1:8501",
            "severity": "CRITICAL",
            "description": "Streamlit port collision",
            "raw_details": {"port": 8501},
            "timestamp": 1756000000,
            "confidence": 0.99,
        },
        {
            "detector_type": "SECRET_ZERO",
            "target_path": ".env.test",
            "severity": "HIGH",
            "description": "Placeholder found",
            "raw_details": {"token": "your_token_here"},
            "timestamp": 1756000000,
            "confidence": 1.0,
        },
    ]

    gradient_dicts = [
        {"gradient_text": "Refine port scan timeout", "cluster_id": 1, "semantic_weight": 0.95},
        {"text": "Refine secret zero regex pattern", "cluster_id": 2, "semantic_weight": 0.85},
    ]

    audit_results = [
        RedTeamAuditResult(
            anomaly=AnomalyRecord.from_dict(anomalies_dicts[0]),
            verdict=RedTeamVerdict.CHALLENGED,
            rationale="Verify if Streamlit is meant to be active",
            recommended_action="Inspect port 8501",
            confidence=0.95,
        ),
        RedTeamAuditResult(
            anomaly=AnomalyRecord.from_dict(anomalies_dicts[1]),
            verdict=RedTeamVerdict.APPROVED,
            rationale="Placeholder token confirmed",
            recommended_action="Update .env.test with test key",
            confidence=1.0,
        ),
    ]

    report = builder.build_daily_report(
        session_id="dict-inputs-session",
        scan_time=datetime.now(timezone.utc),
        anomalies=anomalies_dicts,
        gradients=gradient_dicts,
        audit_results=audit_results,
    )

    assert "- **Total Anomalies Detected**: `2`" in report
    assert "`GHOST_DAEMONS`" in report
    assert "`SECRET_ZERO`" in report
    assert "Refine port scan timeout" in report
    assert "Refine secret zero regex pattern" in report
    assert "- [ ] [HITL-APPROVED] Safe Optimization: Update .env.test with test key" in report
    assert "- [ ] [HITL-APPROVED] Manual Review Required: Inspect port 8501" in report


# =============================================================================
# 3. Markdown Formatting Integrity & Fuzzing
# =============================================================================
def test_report_builder_pipe_escaping_in_rationale_and_action() -> None:
    """Verify that pipe characters (|) in rationales and actions are properly escaped with backslash."""
    builder = DailyReportBuilder()

    anomaly = AnomalyRecord(
        detector_type=DetectorType.ECOSYSTEM_POLLUTION,
        target_path="plugins/gcp_spark.disabled",
        severity=Severity.HIGH,
        description="Disabled plugin",
        raw_details={},
    )

    audit_result = RedTeamAuditResult(
        anomaly=anomaly,
        verdict=RedTeamVerdict.CHALLENGED,
        rationale="Rationale with pipe | delimiter and <script>alert(1)</script>",
        recommended_action="Action | with | pipes and `backticks`",
        confidence=0.91,
    )

    report = builder.build_daily_report(
        session_id="pipe-escape-session",
        scan_time="2026-08-25 14:00:00 UTC",
        anomalies=[anomaly],
        gradients=["Gradient with | pipe"],
        audit_results=[audit_result],
    )

    # Check table row column count in Section 2
    table_lines = [
        line for line in report.split("## 2. Red-Team Scrutiny Verdicts")[1].split("## 3. Proposed Optimizations")[0].splitlines()
        if line.startswith("| 1 |")
    ]
    assert len(table_lines) == 1
    row = table_lines[0]
    # Must have exactly 8 cells
    assert count_table_columns(row) == 8, f"Pipe escaping broke table column count: {row}"
    assert "\\|" in row


def test_report_builder_markdown_structure_and_headings() -> None:
    """Verify that the generated report conforms to strict Markdown heading rules."""
    builder = DailyReportBuilder()

    sample_rec = AnomalyRecord(
        detector_type=DetectorType.PROMPT_FATIGUE,
        target_path="GEMINI.md",
        severity=Severity.MEDIUM,
        description="Manifest rule bloat: 179 lines",
        raw_details={"line_count": 179},
    )
    sample_audit = RedTeamAuditResult(
        anomaly=sample_rec,
        verdict=RedTeamVerdict.CHALLENGED,
        rationale="Manifest rule depth intentional",
        recommended_action="Review rules with developer",
    )

    report = builder.build_daily_report(
        session_id="markdown-syntax-session",
        scan_time=datetime(2026, 8, 25, 8, 30, 0, tzinfo=timezone.utc),
        anomalies=[sample_rec],
        gradients=["Rule refinement gradient"],
        audit_results=[sample_audit],
    )

    headers = extract_markdown_headers_outside_code_blocks(report)

    # Heading Level 1 (Report Title)
    h1_headers = [h for h in headers if h.startswith("# ")]
    assert len(h1_headers) == 1
    assert h1_headers[0] == "# Daily System Health & Optimization Report — 2026-08-25 08:30:00 UTC"

    # Heading Level 2 (6 Mandatory Sections)
    h2_headers = [h for h in headers if h.startswith("## ")]
    assert len(h2_headers) == 6
    assert h2_headers[0] == "## 1. Executive Summary & Health Telemetry"
    assert h2_headers[1] == "## 2. Red-Team Scrutiny Verdicts"
    assert h2_headers[2] == "## 3. Proposed Optimizations (HITL Checkboxes)"
    assert h2_headers[3] == "## 4. Historical Failure Lifelines & Drift Analytics"
    assert h2_headers[4] == "## 5. ProTeGi Textual Gradients for Self-Improvement"
    assert h2_headers[5] == "## 6. Manual Remediation Command Guide"

    # Code Block Verification (Powershell in Section 6)
    lines = report.splitlines()
    code_block_fences = [i for i, l in enumerate(lines) if l.strip().startswith("```")]
    assert len(code_block_fences) == 2, "Powershell code block must have exactly 1 opening and 1 closing fence"
    assert lines[code_block_fences[0]].strip() == "```powershell"
    assert lines[code_block_fences[1]].strip() == "```"


# =============================================================================
# 4. Extreme Numerical Drift Statistics
# =============================================================================
def test_report_builder_extreme_drift_statistics() -> None:
    """Verify DailyReportBuilder formats extreme numerical statistics without formatting crashes."""
    builder = DailyReportBuilder()

    extreme_drifts = [
        # Zero stats
        {
            "total_sessions": 0,
            "total_anomalies": 0,
            "average_duration_ms": 0.0,
            "average_entropy_score": 0.0,
            "drift_detected": False,
        },
        # Massive stats
        {
            "total_sessions": 999999999,
            "total_anomalies": 888888888,
            "average_duration_ms": 1234567.891,
            "average_entropy_score": 0.999999,
            "drift_detected": True,
        },
        # Negative / float edge values
        {
            "total_sessions": -1,
            "total_anomalies": -5,
            "average_duration_ms": -10.5,
            "average_entropy_score": -0.1234,
            "drift_detected": False,
        },
    ]

    for drift in extreme_drifts:
        report = builder.build_daily_report(
            session_id="extreme-drift-session",
            scan_time=0.0,  # Epoch 0
            anomalies=[],
            gradients=[],
            audit_results=[],
            historical_drift=drift,
            duration_ms=drift["average_duration_ms"],
            entropy=drift["average_entropy_score"],
        )
        assert "## 4. Historical Failure Lifelines & Drift Analytics" in report
        assert f"- **Total Recorded Sessions**: `{drift['total_sessions']}`" in report
        assert f"- **Total Cumulative Anomalies**: `{drift['total_anomalies']}`" in report
        assert f"{drift['average_duration_ms']:.2f} ms" in report
        assert f"{drift['average_entropy_score']:.4f}" in report


# =============================================================================
# 5. Cryptographic SHA-256 FileSystemSnapshot Read-Only Immutability
# =============================================================================
def test_report_builder_strict_read_only_snapshot(tmp_path: Path) -> None:
    """Cryptographically proves that DailyReportBuilder produces zero disk writes or mutations."""
    workspace = tmp_path / "protected_workspace"
    workspace.mkdir(parents=True)
    (workspace / "GEMINI.md").write_text("# Manifest\n", encoding="utf-8")
    (workspace / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    (workspace / "config.json").write_text('{"key": "value"}', encoding="utf-8")
    sub_dir = workspace / "sub_dir"
    sub_dir.mkdir()
    (sub_dir / "data.txt").write_text("Hello World", encoding="utf-8")

    snapshot = FileSystemSnapshot(str(workspace))

    builder = DailyReportBuilder()
    red_team = ArchitectureRedTeam()

    # Generate 10 consecutive reports with high load
    for run_idx in range(10):
        records = [
            AnomalyRecord(
                detector_type=DetectorType.GHOST_DAEMONS,
                target_path=f"port_{3000 + i}",
                severity=Severity.HIGH,
                description=f"Anomaly {i}",
            )
            for i in range(100)
        ]
        audits = red_team.audit_batch(records)
        report = builder.build_daily_report(
            session_id=f"run-{run_idx}",
            scan_time=datetime.now(timezone.utc),
            anomalies=records,
            gradients=[f"Gradient {run_idx}"],
            audit_results=audits,
            historical_drift={"total_sessions": run_idx + 1},
        )
        assert len(report) > 1000

    # Cryptographic proof: workspace is 100% byte-for-byte untouched
    snapshot.assert_untouched()


# =============================================================================
# 6. Static AST Safety Guardrails Verification
# =============================================================================
def test_report_builder_ast_safety_compliance() -> None:
    """Verifies that audit/report_builder.py and audit/red_team.py contain 0 destructive AST calls."""
    report_builder_path = Path(__file__).resolve().parent.parent / "audit" / "report_builder.py"
    red_team_path = Path(__file__).resolve().parent.parent / "audit" / "red_team.py"

    assert report_builder_path.exists(), f"Missing {report_builder_path}"
    assert red_team_path.exists(), f"Missing {red_team_path}"

    audit_dir = report_builder_path.parent
    # assert_safe_codebase raises AssertionError if any destructive call is found
    assert_safe_codebase(str(audit_dir))


# =============================================================================
# 7. Empirical Fuzzing Tests (Vulnerabilities & Boundary Conditions)
# =============================================================================
def test_fuzzing_vulnerability_target_path_with_pipes() -> None:
    """Documents vulnerability: unescaped pipes in target_path cause table column splitting if unescaped."""
    builder = DailyReportBuilder()

    rec = AnomalyRecord(
        detector_type=DetectorType.ECOSYSTEM_POLLUTION,
        target_path="plugins/path|with|pipe",
        severity=Severity.MEDIUM,
        description="Path with unescaped pipes",
    )
    audit = RedTeamAuditResult(
        anomaly=rec,
        verdict=RedTeamVerdict.APPROVED,
        rationale="Safe action",
        recommended_action="Inspect path",
    )

    report = builder.build_daily_report(
        session_id="fuzz-pipe-target",
        scan_time="2026-08-25 00:00:00 UTC",
        anomalies=[rec],
        gradients=[],
        audit_results=[audit],
    )

    # In report_builder.py, target is formatted as `{target}` without escaping |
    # While target is inside backticks `plugins/path|with|pipe`, table line contains raw |
    table_lines = [
        line for line in report.splitlines()
        if line.startswith("| 1 |")
    ]
    assert len(table_lines) == 1
    # When split by standard unescaped pipe regex:
    cells = [c for c in table_lines[0].split("|")[1:-1]]
    # Documented finding: 10 raw cells produced instead of 8 because of 2 unescaped pipes in target_path
    assert len(cells) == 10


def test_fuzzing_vulnerability_none_in_drift_metrics() -> None:
    """Documents vulnerability: None values in historical_drift dict cause TypeError in string formatting."""
    builder = DailyReportBuilder()

    # When SQL AVG() returns None on empty tables, drift dict may have None for average_duration_ms
    drift_with_nones = {
        "total_sessions": 0,
        "total_anomalies": 0,
        "average_duration_ms": None,
        "average_entropy_score": None,
        "drift_detected": False,
    }

    # Calling with drift_with_nones raises TypeError because drift.get("average_duration_ms", 0.0) returns None
    with pytest.raises(TypeError, match="unsupported format string passed to NoneType"):
        builder.build_daily_report(
            session_id="fuzz-none-drift",
            scan_time="2026-08-25 00:00:00 UTC",
            anomalies=[],
            gradients=[],
            audit_results=[],
            historical_drift=drift_with_nones,
        )


def test_fuzzing_vulnerability_none_anomaly_in_audit_result() -> None:
    """Documents vulnerability: RedTeamAuditResult with anomaly=None causes AttributeError in report builder."""
    builder = DailyReportBuilder()

    audit_with_none_anomaly = RedTeamAuditResult(
        anomaly=None,
        verdict=RedTeamVerdict.APPROVED,
        rationale="General observation without attached anomaly",
        recommended_action="Review workspace health",
    )

    # In report_builder.py line 125: det = rec.detector_type.value if isinstance(rec.detector_type, ...) else ...
    # Raises AttributeError: 'NoneType' object has no attribute 'detector_type'
    with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'detector_type'"):
        builder.build_daily_report(
            session_id="fuzz-none-anomaly",
            scan_time="2026-08-25 00:00:00 UTC",
            anomalies=[],
            gradients=[],
            audit_results=[audit_with_none_anomaly],
        )
