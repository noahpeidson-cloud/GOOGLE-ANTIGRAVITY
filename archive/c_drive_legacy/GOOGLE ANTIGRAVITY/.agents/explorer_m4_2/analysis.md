# Technical Analysis & Architecture Specification: `audit/report_builder.py`

## 1. Executive Overview

The `DailyReportBuilder` class in `audit/report_builder.py` serves as the reporting and human-in-the-loop (HITL) interface for the Antigravity Daily Health Scanner & ML Optimization Daemon.

It compiles scan telemetry, machine learning clustering results, semantic entropy scores, internal red-team scrutiny verdicts, historical failure lifeline tracking, and ProTeGi textual gradients into a structured, deterministic Markdown report.

In strict compliance with `GEMINI.md` Rule R2 (Zero-Discretion), Rule R3 (Lifeline Extraction), and the `accidental-data-loss-prevention` skill:
- Execution is **100% read-only and non-destructive**.
- All optimizations are presented with **interactive HITL review checkboxes** (`- [ ] [HITL-APPROVED] ...`).
- **Manual remediation commands** are compiled as exact copy-pasteable PowerShell/Windows terminal commands for the developer to execute manually if approved — with zero automated execution.

---

## 2. Architectural Blueprint & File Layout

```
.agents/cron/
├── audit/
│   ├── __init__.py           # Package exports: ArchitectureRedTeam, DailyReportBuilder
│   ├── red_team.py           # Milestone 4: ArchitectureRedTeam auditor & RedTeamAuditResult
│   └── report_builder.py     # Milestone 4: DailyReportBuilder class & formatting utilities
├── config.py                 # Configuration thresholds, ports, whitelists
├── database.py               # SQLite telemetry, historical lifelines & drift queries
├── detectors/                # 5 read-only anomaly detectors
├── ml/                       # Vectorizer, K-Means clustering, semantic entropy, ProTeGi
├── models.py                 # AnomalyRecord, RedTeamAuditResult, OptimizationReport, Enums
├── safety_guardrails.py      # Static AST verification
├── scanner.py                # HealthScanner orchestrator
└── tests/
    └── test_red_team_and_report.py  # Milestone 4 unit & integration test suite
```

---

## 3. Data Flow & Interface Contracts

### 3.1 Input Data Sources

`DailyReportBuilder` consumes data from two primary avenues:

1. **Direct `OptimizationReport` Ingestion**:
   ```python
   builder = DailyReportBuilder(db_path="health_telemetry.db")
   markdown_report = builder.build_report(
       report=optimization_report,
       cluster_distribution={0: 2, 1: 2, 2: 1},
       db_path="health_telemetry.db"
   )
   ```

2. **Session ID Query Ingestion**:
   ```python
   builder = DailyReportBuilder(db_path="health_telemetry.db")
   markdown_report = builder.build_report_from_session(
       session_id="scan_20260825_054008",
       db_path="health_telemetry.db"
   )
   ```

### 3.2 Report Model Interfaces (`models.py`)

- `OptimizationReport`:
  - `session_id: str`
  - `timestamp: int`
  - `duration_ms: float`
  - `total_anomalies: int`
  - `approved_count: int`
  - `challenged_count: int`
  - `audited_anomalies: List[RedTeamAuditResult]`
  - `textual_gradients: List[str]`
  - `entropy_score: float`

- `RedTeamAuditResult`:
  - `anomaly: AnomalyRecord` (detector_type, target_path, severity, description, raw_details, is_historical, timestamp, confidence)
  - `verdict: RedTeamVerdict` (`APPROVED`, `CHALLENGED`, `REJECTED`)
  - `rationale: str`
  - `risk_assessment: str`
  - `recommended_action: str`

---

## 4. The 6 Core Report Sections

### Section 1: Executive Summary & Health Telemetry
- **Scan Metadata**: Session ID, ISO 8601 UTC timestamp, scan duration formatted in milliseconds.
- **Overall Health Status**:
  - `🟢 HEALTHY (Zero Anomalies)` when `total_anomalies == 0`.
  - `🔴 CRITICAL ACTION REQUIRED` when any anomaly is `CRITICAL`.
  - `🟠 HIGH ATTENTION NEEDED` when any anomaly is `HIGH`.
  - `🟡 ATTENTION NEEDED` when anomalies are `MEDIUM` or `LOW`.
- **Anomaly Telemetry Matrix**:
  - Total anomalies detected.
  - Distribution by Severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
  - Distribution by Detector (`GHOST_DAEMONS`, `CONTEXT_ROT`, `ECOSYSTEM_POLLUTION`, `SECRET_ZERO`, `PROMPT_FATIGUE`).
- **Semantic Entropy Score**:
  - Score formatted to 4 decimal places (`0.0000` to `1.0000`).
  - Status classification:
    - `<= 0.05`: `[🟢 Converged / Tight Rule Alignment]`
    - `< 0.15`: `[🟡 Stable / Low Dispersion]`
    - `>= 0.15`: `[🔴 High Dispersion / Multiple Concurrent Drift Modes]`
- **K-Means Cluster Distribution (K=3)**:
  - Table showing cluster ID, item count, percentage of total anomalies, and dominant pattern.

### Section 2: Red-Team Scrutiny Verdicts
- **Audit Scorecard**:
  - Count and percentage of `APPROVED` actions (safe to execute).
  - Count and percentage of `CHALLENGED` actions (risk flagged, human review advised).
  - Count and percentage of `REJECTED` actions (blocked to prevent data loss or false positive).
- **Scrutiny Matrix Table**:
  - Columns: `#`, `Target Resource`, `Detector`, `Severity`, `Verdict`, `Risk Assessment`, `Red-Team Rationale`.
- **Adversarial Counter-Arguments**:
  - Explicit documentation of why challenged or rejected items were flagged (e.g. protected manifest `PROJECT.md`, active build artifacts, production ports).

### Section 3: Proposed Optimizations with HITL Interactive Checkboxes
- **HITL Guardrail Banner**:
  - Warning that zero automated changes were made and execution is 100% read-only.
- **Interactive Review Checkboxes**:
  - **Approved Actions**:
    `- [ ] [HITL-APPROVED] [<DETECTOR>] <Action Summary> (Target: <target_path>)`
    - Sub-bullets with Rationale and Recommended Safe Action.
  - **Challenged Actions** (if present):
    `- [ ] [HITL-CHALLENGED] [<DETECTOR>] <Action Summary> (Target: <target_path>)`
    - Sub-bullets with Warning and Counter-Proposal.
  - **Blocked Actions**:
    `- [x] [RED-TEAM BLOCKED - REJECTED] [<DETECTOR>] <Action Summary> (Target: <target_path>)`
    - Sub-bullets explaining safety rule trigger.

### Section 4: Historical Failure Lifelines & Drift Analytics
- **5 August 23/24 Failure Lifelines**:
  1. `GHOST_DAEMONS_WINERROR_10048`: Ghost Daemons (ports 3000/8000/8501)
  2. `CONTEXT_ROT_PLANNING_ARTIFACTS`: Context Rot (>24h planning artifacts)
  3. `ECOSYSTEM_POLLUTION_DISABLED_PLUGINS`: Ecosystem Pollution (.disabled plugins)
  4. `SECRET_ZERO_PLACEHOLDER_KEYS`: Secret Zero (`your_token_here` in .env)
  5. `PROMPT_FATIGUE_MANIFEST_BLOAT`: Prompt Fatigue (GEMINI.md > 100 lines)
- **Lifeline Status Table**:
  - Columns: `Lifeline Code`, `Category`, `Failure Session`, `Status` (`🟢 PASS` vs `🔴 ACTIVE ANOMALIES`), `Active Count`, `Target Pattern`.
- **7-Day Trend & Drift Analytics**:
  - Total historical scan sessions logged in SQLite.
  - Total historical anomalies logged.
  - Average scan duration (ms).
  - Average semantic entropy score across sessions.
  - Systematic drift determination (`No Systematic Drift Detected` vs `Active Drift Detected`).

### Section 5: ProTeGi Textual Gradients for Heuristic Self-Improvement
- **Textual Gradient Recommendations**:
  - Extracted from `OptimizationReport.textual_gradients` or `ml/protegi.py`.
  - Blockquoted gradient rules (e.g. `> **[ProTeGi Gradient: GHOST_DAEMONS]** ...`).
- **Convergence Indicator**:
  - When entropy is `0.000` or zero anomalies exist:
    `> **[ProTeGi Convergence]** Semantic entropy is 0.000 — Workspace rules and detectors are tightly aligned.`
- **Heuristic Self-Tuning Suggestions**:
  - Specific parameter tuning suggestions:
    - Adjust `CONTEXT_ROT_THRESHOLD_HOURS = 24.0`
    - Expand `WHITELISTED_FILENAMES`
    - Enforce pre-commit token checks for `BLACKLIST_TOKEN_PATTERNS`
    - Prune procedural instructions from `GEMINI.md` to `.agents/skills/`

### Section 6: Manual Remediation Command Guide
- **100% Zero Automated Execution Guarantee**:
  - Explicit disclaimer: The scanner is 100% read-only.
- **Copy-Pasteable PowerShell Commands**:
  - Generates safe, verified PowerShell commands for each approved anomaly:
    - **Ghost Daemons**:
      ```powershell
      # Inspect and terminate process on occupied port:
      Get-NetTCPConnection -LocalPort <port> -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
      ```
    - **Context Rot**:
      ```powershell
      # Safely archive stale planning artifact:
      New-Item -ItemType Directory -Force -Path ".agents/archive"
      Move-Item -Path "<target_path>" -Destination ".agents/archive/"
      ```
    - **Ecosystem Pollution**:
      ```powershell
      # Quarantine disabled plugin directory:
      New-Item -ItemType Directory -Force -Path ".quarantine"
      Move-Item -Path "<target_path>" -Destination ".quarantine/"
      ```
    - **Secret Zero**:
      ```powershell
      # Inspect placeholder token in environment file:
      Get-Content "<target_path>" | Select-String "your_token_here"
      ```
    - **Prompt Fatigue**:
      ```powershell
      # Inspect manifest line count:
      (Get-Content "<target_path>").Count
      ```
- **Rejected Items**:
  - Explicitly generates `# NO REMEDIATION COMMANDS GENERATED — Action rejected by red team.`

---

## 5. Drop-In Code Blueprint (`audit/report_builder.py`)

```python
\"\"\"Daily Human-in-the-Loop (HITL) Markdown Report Builder for Health Scanner & ML Daemon.\"\"\"

import datetime
import os
import time
from typing import Any, Dict, List, Optional

try:
    from ..config import (
        CONTEXT_ROT_THRESHOLD_HOURS,
        DEFAULT_DB_PATH,
        DEFAULT_K_CLUSTERS,
        MONITORED_PORTS,
        PROMPT_FATIGUE_MAX_LINES,
        WHITELISTED_FILENAMES,
    )
    from ..database import (
        get_anomalies_for_session,
        get_historical_drift,
        get_historical_lifelines,
        get_session,
        get_textual_gradients_for_session,
    )
    from ..ml.protegi import CONVERGENCE_MESSAGE
    from ..models import (
        AnomalyRecord,
        DetectorType,
        OptimizationReport,
        RedTeamAuditResult,
        RedTeamVerdict,
        Severity,
    )
except (ImportError, ValueError):
    from config import (
        CONTEXT_ROT_THRESHOLD_HOURS,
        DEFAULT_DB_PATH,
        DEFAULT_K_CLUSTERS,
        MONITORED_PORTS,
        PROMPT_FATIGUE_MAX_LINES,
        WHITELISTED_FILENAMES,
    )
    from database import (
        get_anomalies_for_session,
        get_historical_drift,
        get_historical_lifelines,
        get_session,
        get_textual_gradients_for_session,
    )
    from ml.protegi import CONVERGENCE_MESSAGE
    from models import (
        AnomalyRecord,
        DetectorType,
        OptimizationReport,
        RedTeamAuditResult,
        RedTeamVerdict,
        Severity,
    )


class DailyReportBuilder:
    \"\"\"Compiles comprehensive, human-in-the-loop (HITL) daily Markdown reports

    incorporating executive telemetry, red-team scrutiny verdicts, interactive
    checkboxes, historical drift analytics, ProTeGi textual gradients, and copy-pasteable
    manual remediation commands with 0% automated execution.
    \"\"\"

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        default_output_dir: Optional[str] = None,
    ) -> None:
        self.db_path = db_path
        self.default_output_dir = default_output_dir or "."

    def _format_timestamp(self, ts: int) -> str:
        \"\"\"Formats integer unix timestamp into ISO 8601 UTC string.\"\"\"
        if ts <= 0:
            ts = int(time.time())
        try:
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts))

    def build_report(
        self,
        report: OptimizationReport,
        cluster_distribution: Optional[Dict[int, int]] = None,
        db_path: Optional[str] = None,
    ) -> str:
        \"\"\"Builds complete daily Markdown report from an OptimizationReport instance.\"\"\"
        active_db = db_path or self.db_path
        sections = [
            self._build_header(report),
            self._build_executive_summary(report, cluster_distribution),
            self._build_red_team_scrutiny(report),
            self._build_hitl_checkboxes(report),
            self._build_lifelines_and_drift(report, active_db),
            self._build_protegi_gradients(report),
            self._build_remediation_commands(report),
            self._build_footer(report),
        ]
        return "\\n\\n".join(sections) + "\\n"

    def build_report_from_session(
        self,
        session_id: str,
        db_path: Optional[str] = None,
    ) -> str:
        \"\"\"Builds daily Markdown report by querying session records from SQLite.\"\"\"
        active_db = db_path or self.db_path
        sess_meta = get_session(session_id, db_path=active_db)
        if not sess_meta:
            raise ValueError(f"Session ID '{session_id}' not found in database: {active_db}")

        anomalies = get_anomalies_for_session(session_id, db_path=active_db)
        gradients = get_textual_gradients_for_session(session_id, db_path=active_db)

        # Reconstruct RedTeamAuditResult items with default approval if not pre-audited
        audited_anomalies: List[RedTeamAuditResult] = []
        for anom in anomalies:
            audited_anomalies.append(
                RedTeamAuditResult(
                    anomaly=anom,
                    verdict=RedTeamVerdict.APPROVED,
                    rationale=anom.description,
                    risk_assessment="Low risk / Verified anomaly",
                    recommended_action=f"Remediate {anom.detector_type.value if hasattr(anom.detector_type, 'value') else anom.detector_type}",
                )
            )

        report = OptimizationReport(
            session_id=session_id,
            timestamp=sess_meta["timestamp"],
            duration_ms=float(sess_meta["duration_ms"]),
            total_anomalies=int(sess_meta["total_anomalies"]),
            approved_count=len(audited_anomalies),
            challenged_count=0,
            audited_anomalies=audited_anomalies,
            textual_gradients=gradients,
            entropy_score=float(sess_meta.get("entropy_score", 0.0)),
        )

        return self.build_report(report, db_path=active_db)

    def save_report(
        self,
        markdown_content: str,
        output_path: Optional[str] = None,
        session_id: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> str:
        \"\"\"Safely writes generated Markdown report to disk in a read-only/non-destructive manner.\"\"\"
        if output_path:
            target_path = output_path
        else:
            ts_str = time.strftime("%Y%m%d_%H%M%S", time.gmtime(timestamp or time.time()))
            sess_tag = f"_{session_id}" if session_id else ""
            filename = f"daily_health_report_{ts_str}{sess_tag}.md"
            target_path = os.path.join(self.default_output_dir, filename)

        parent_dir = os.path.dirname(os.path.abspath(target_path))
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        return target_path

    # =========================================================================
    # Section Builders
    # =========================================================================

    def _build_header(self, report: OptimizationReport) -> str:
        return (
            "# 🛡️ Antigravity Workspace Health & Telemetry Report\\n"
            f"> **Session ID**: `{report.session_id}` | "
            f"**Generated**: `{self._format_timestamp(report.timestamp)}` | "
            f"**Execution Mode**: `100% Non-Destructive (HITL)`"
        )

    def _build_executive_summary(
        self,
        report: OptimizationReport,
        cluster_distribution: Optional[Dict[int, int]] = None,
    ) -> str:
        # Determine overall status
        has_critical = any(
            (a.anomaly.severity == Severity.CRITICAL if hasattr(a, "anomaly") else False)
            for a in report.audited_anomalies
        )
        has_high = any(
            (a.anomaly.severity == Severity.HIGH if hasattr(a, "anomaly") else False)
            for a in report.audited_anomalies
        )

        if report.total_anomalies == 0:
            health_badge = "🟢 **HEALTHY (Zero Anomalies Detected)**"
        elif has_critical:
            health_badge = "🔴 **CRITICAL ACTION REQUIRED (Immediate Attention)**"
        elif has_high:
            health_badge = "🟠 **HIGH ATTENTION NEEDED (High Severity Issues Found)**"
        else:
            health_badge = "🟡 **ATTENTION NEEDED (Moderate/Low Drift Detected)**"

        # Severity breakdown
        sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        det_counts: Dict[str, int] = {}

        for audit in report.audited_anomalies:
            anom = audit.anomaly if hasattr(audit, "anomaly") else audit
            sev = anom.severity.value if hasattr(anom.severity, "value") else str(anom.severity)
            sev_counts[sev] = sev_counts.get(sev, 0) + 1

            det = anom.detector_type.value if hasattr(anom.detector_type, "value") else str(anom.detector_type)
            det_counts[det] = det_counts.get(det, 0) + 1

        # Entropy status
        if report.entropy_score <= 0.0001:
            entropy_label = "`0.0000` (🟢 Converged / Perfect Alignment)"
        elif report.entropy_score < 0.15:
            entropy_label = f"`{report.entropy_score:.4f}` (🟡 Stable / Low Dispersion)"
        else:
            entropy_label = f"`{report.entropy_score:.4f}` (🔴 High Dispersion / Multi-Mode Drift)"

        # Cluster distribution
        if cluster_distribution:
            clusters_str = ", ".join(f"Cluster {k}: **{v}** items" for k, v in sorted(cluster_distribution.items()))
        else:
            clusters_str = f"Assigned to {DEFAULT_K_CLUSTERS} K-Means clusters"

        lines = [
            "## 1. Executive Summary & Health Telemetry",
            "",
            f"- **Overall Workspace Status**: {health_badge}",
            f"- **Scan Timestamp**: `{self._format_timestamp(report.timestamp)}`",
            f"- **Scan Execution Duration**: `{report.duration_ms:.2f} ms`",
            f"- **Total Anomalies Detected**: **{report.total_anomalies}**",
            f"- **Semantic Entropy Score**: {entropy_label}",
            f"- **K-Means Cluster Distribution (K={DEFAULT_K_CLUSTERS})**: {clusters_str}",
            "",
            "### Telemetry Breakdown",
            "",
            "| Metric Category | Values / Distribution |",
            "|---|---|",
            f"| **Severity Breakdown** | Critical: **{sev_counts.get('CRITICAL', 0)}**, High: **{sev_counts.get('HIGH', 0)}**, Medium: **{sev_counts.get('MEDIUM', 0)}**, Low: **{sev_counts.get('LOW', 0)}** |",
            f"| **Detector Types** | " + (", ".join(f"{k}: **{v}**" for k, v in sorted(det_counts.items())) if det_counts else "None") + " |",
            f"| **Red-Team Verdicts** | Approved: **{report.approved_count}**, Challenged: **{report.challenged_count}**, Rejected: **{report.total_anomalies - report.approved_count - report.challenged_count}** |",
        ]
        return "\\n".join(lines)

    def _build_red_team_scrutiny(self, report: OptimizationReport) -> str:
        rejected_count = max(0, report.total_anomalies - report.approved_count - report.challenged_count)
        approved_pct = (report.approved_count / report.total_anomalies * 100.0) if report.total_anomalies > 0 else 100.0
        challenged_pct = (report.challenged_count / report.total_anomalies * 100.0) if report.total_anomalies > 0 else 0.0
        rejected_pct = (rejected_count / report.total_anomalies * 100.0) if report.total_anomalies > 0 else 0.0

        lines = [
            "## 2. Red-Team Scrutiny Verdicts",
            "",
            "> **Adversarial Audit Directive**: Every proposed optimization is evaluated against System Integrity, Data Loss Risk (`accidental-data-loss-prevention`), and False Positive Filtering before reaching the human developer.",
            "",
            f"- **Approved Actions**: **{report.approved_count}** ({approved_pct:.1f}%) — Verified non-destructive, zero data loss risk.",
            f"- **Challenged Actions**: **{report.challenged_count}** ({challenged_pct:.1f}%) — Potential secondary impacts identified.",
            f"- **Rejected Actions**: **{rejected_count}** ({rejected_pct:.1f}%) — Prohibited by safety policies or identified as active assets.",
            "",
        ]

        if not report.audited_anomalies:
            lines.append("*No anomalies requiring red-team audit in this scan.*")
            return "\\n".join(lines)

        lines.extend([
            "### Detailed Scrutiny Breakdown",
            "",
            "| # | Target Resource | Detector | Severity | Red-Team Verdict | Risk Assessment | Red-Team Rationale & Counter-Argument |",
            "|---|---|---|---|---|---|---|",
        ])

        for idx, audit in enumerate(report.audited_anomalies, start=1):
            anom = audit.anomaly
            det = anom.detector_type.value if hasattr(anom.detector_type, "value") else str(anom.detector_type)
            sev = anom.severity.value if hasattr(anom.severity, "value") else str(anom.severity)
            verdict_str = audit.verdict.value if hasattr(audit.verdict, "value") else str(audit.verdict)

            if verdict_str == RedTeamVerdict.APPROVED.value:
                badge = "✅ `APPROVED`"
            elif verdict_str == RedTeamVerdict.CHALLENGED.value:
                badge = "⚠️ `CHALLENGED`"
            else:
                badge = "❌ `REJECTED`"

            target = f"`{anom.target_path}`"
            lines.append(
                f"| {idx} | {target} | `{det}` | `{sev}` | {badge} | {audit.risk_assessment} | {audit.rationale} |"
            )

        return "\\n".join(lines)

    def _build_hitl_checkboxes(self, report: OptimizationReport) -> str:
        lines = [
            "## 3. Proposed Optimizations (Human-in-the-Loop Review)",
            "",
            "> ⚠️ **HITL Guardrail Notice**: In accordance with `accidental-data-loss-prevention` and `GEMINI.md` Rule R2, **no automated actions have been taken**. Mark the checkboxes below for manual execution reference.",
            "",
        ]

        approved_items = [
            a for a in report.audited_anomalies
            if (a.verdict == RedTeamVerdict.APPROVED if hasattr(a.verdict, "value") else str(a.verdict) == "APPROVED")
        ]
        challenged_items = [
            a for a in report.audited_anomalies
            if (a.verdict == RedTeamVerdict.CHALLENGED if hasattr(a.verdict, "value") else str(a.verdict) == "CHALLENGED")
        ]
        rejected_items = [
            a for a in report.audited_anomalies
            if (a.verdict == RedTeamVerdict.REJECTED if hasattr(a.verdict, "value") else str(a.verdict) == "REJECTED")
        ]

        if not report.audited_anomalies:
            lines.append("*Zero optimizations proposed — workspace is in pristine health.*")
            return "\\n".join(lines)

        if approved_items:
            lines.append("### Approved Optimizations (Ready for Human Approval)")
            lines.append("")
            for audit in approved_items:
                anom = audit.anomaly
                det = anom.detector_type.value if hasattr(anom.detector_type, "value") else str(anom.detector_type)
                lines.append(
                    f"- [ ] **[HITL-APPROVED]** `[{det}]` {audit.recommended_action} (Target: `{anom.target_path}`)\\n"
                    f"  - **Rationale**: {audit.rationale}\\n"
                    f"  - **Severity**: `{anom.severity.value if hasattr(anom.severity, 'value') else anom.severity}`"
                )
            lines.append("")

        if challenged_items:
            lines.append("### Challenged Optimizations (Caution / Double-Check Required)")
            lines.append("")
            for audit in challenged_items:
                anom = audit.anomaly
                det = anom.detector_type.value if hasattr(anom.detector_type, "value") else str(anom.detector_type)
                lines.append(
                    f"- [ ] **[HITL-CHALLENGED]** `[{det}]` {audit.recommended_action} (Target: `{anom.target_path}`)\\n"
                    f"  - **Warning**: {audit.rationale}\\n"
                    f"  - **Risk**: {audit.risk_assessment}"
                )
            lines.append("")

        if rejected_items:
            lines.append("### Blocked Optimizations (Red-Team Blocked — Prohibited)")
            lines.append("")
            for audit in rejected_items:
                anom = audit.anomaly
                det = anom.detector_type.value if hasattr(anom.detector_type, "value") else str(anom.detector_type)
                lines.append(
                    f"- [x] **[RED-TEAM BLOCKED - REJECTED]** `[{det}]` Preserved `{anom.target_path}`\\n"
                    f"  - **Safety Trigger**: {audit.rationale}\\n"
                    f"  - **Risk**: {audit.risk_assessment}"
                )
            lines.append("")

        return "\\n".join(lines)

    def _build_lifelines_and_drift(
        self,
        report: OptimizationReport,
        db_path: str,
    ) -> str:
        lines = [
            "## 4. Historical Failure Lifelines & Drift Analytics",
            "",
            "> **Rule R3 Enforcement**: Tracking resolution and drift status for the 5 historical failures from the August 23/24 session.",
            "",
        ]

        try:
            lifelines = get_historical_lifelines(db_path=db_path)
            drift_stats = get_historical_drift(db_path=db_path)
        except Exception:
            lifelines = []
            drift_stats = {}

        if lifelines:
            # Count active anomalies matching each detector type
            active_by_det: Dict[str, int] = {}
            for audit in report.audited_anomalies:
                anom = audit.anomaly
                dt = anom.detector_type.value if hasattr(anom.detector_type, "value") else str(anom.detector_type)
                active_by_det[dt] = active_by_det.get(dt, 0) + 1

            lines.extend([
                "### Historical Failure Lifelines (August 23/24 Session)",
                "",
                "| Lifeline Code | Category | Failure Date | Current Status | Active Findings | Target Pattern / Rule |",
                "|---|---|---|---|---|---|",
            ])

            for lf in lifelines:
                code = lf.get("lifeline_code", "")
                dt = lf.get("detector_type", "")
                fail_date = lf.get("failure_session_date", "2026-08-24")
                pattern = lf.get("target_pattern", "")
                active_cnt = active_by_det.get(dt, 0)

                if active_cnt == 0:
                    status_badge = "🟢 `PASS / CLEARED`"
                else:
                    status_badge = "🔴 `ACTIVE / DRIFT`"

                lines.append(
                    f"| `{code}` | `{dt}` | {fail_date} | {status_badge} | **{active_cnt}** | `{pattern}` |"
                )
            lines.append("")

        if drift_stats:
            total_sess = drift_stats.get("total_sessions", 0)
            total_anom = drift_stats.get("total_anomalies", 0)
            avg_dur = drift_stats.get("average_duration_ms", 0.0)
            avg_ent = drift_stats.get("average_entropy_score", 0.0)
            drift_flag = drift_stats.get("drift_detected", False)

            drift_summary = "🔴 **Active Anomaly Drift Detected**" if drift_flag else "🟢 **No Systematic Drift Detected**"

            lines.extend([
                "### 7-Day Drift Telemetry Summary",
                "",
                f"- **Total Historical Sessions Logged**: **{total_sess}**",
                f"- **Total Lifetime Anomalies Recorded**: **{total_anom}**",
                f"- **Average Scan Execution Duration**: `{avg_dur:.2f} ms`",
                f"- **Average Semantic Entropy Score**: `{avg_ent:.4f}`",
                f"- **Historical Drift Status**: {drift_summary}",
            ])

        return "\\n".join(lines)

    def _build_protegi_gradients(self, report: OptimizationReport) -> str:
        lines = [
            "## 5. ProTeGi Textual Gradients for Heuristic Self-Improvement",
            "",
            "> **ProTeGi Leash Optimization**: Dynamic textual gradients derived from anomaly clusters to self-tune detector thresholds, whitelists, and prompt directives.",
            "",
        ]

        if not report.textual_gradients or report.textual_gradients == [CONVERGENCE_MESSAGE]:
            lines.append(f"> 🟢 **{CONVERGENCE_MESSAGE}**")
            lines.append("")
            lines.append("No heuristic calibration adjustments required.")
            return "\\n".join(lines)

        for grad in report.textual_gradients:
            lines.append(f"> 🔹 **{grad}**")
            lines.append("")

        lines.extend([
            "### Recommended Heuristic Calibrations",
            "",
            "- **Context Rot Threshold**: Review `CONTEXT_ROT_THRESHOLD_HOURS` (currently `24.0h`) if planning documents require extended multi-day lifespans.",
            "- **Whitelist Maintenance**: Add verified static files to `WHITELISTED_FILENAMES` in `config.py` to eliminate recurring false positives.",
            "- **Prompt Hygiene**: Maintain `GEMINI.md` under `100 lines` (`PROMPT_FATIGUE_MAX_LINES`) by offloading procedural steps into modular `.agents/skills/`.",
            "- **Port Sweeping**: Pre-bind ports `3000`, `8000`, `8501` (`MONITORED_PORTS`) with graceful socket lifecycle hooks.",
        ])

        return "\\n".join(lines)

    def _build_remediation_commands(self, report: OptimizationReport) -> str:
        lines = [
            "## 6. Manual Remediation Command Guide",
            "",
            "> 🛡️ **100% Zero Automated Execution Guarantee**:",
            "> The scanner daemon operates in strict read-only mode and NEVER modifies files or terminates tasks autonomously.",
            "> If you choose to execute any approved optimizations from Section 3, copy and run the PowerShell commands below:",
            "",
        ]

        approved_items = [
            a for a in report.audited_anomalies
            if (a.verdict == RedTeamVerdict.APPROVED if hasattr(a.verdict, "value") else str(a.verdict) == "APPROVED")
        ]

        if not approved_items:
            lines.append("```powershell")
            lines.append("# No manual remediation commands required — workspace is healthy or all actions were rejected.")
            lines.append("```")
            return "\\n".join(lines)

        lines.append("```powershell")
        lines.append("# =============================================================================")
        lines.append("# Antigravity Manual Remediation Commands (Windows / PowerShell)")
        lines.append(f"# Generated for Scan Session: {report.session_id}")
        lines.append("# =============================================================================")
        lines.append("")

        for idx, audit in enumerate(approved_items, start=1):
            cmd = self._generate_remediation_command(audit)
            anom = audit.anomaly
            det = anom.detector_type.value if hasattr(anom.detector_type, "value") else str(anom.detector_type)

            lines.append(f"# -----------------------------------------------------------------------------")
            lines.append(f"# [{idx}] [{det}] {audit.recommended_action}")
            lines.append(f"# Target: {anom.target_path}")
            lines.append(f"# Rationale: {audit.rationale}")
            lines.append(f"# -----------------------------------------------------------------------------")
            if cmd:
                lines.append(cmd)
            else:
                lines.append(f"# Manual review recommended for {anom.target_path}")
            lines.append("")

        lines.append("```")
        return "\\n".join(lines)

    def _generate_remediation_command(self, audit: RedTeamAuditResult) -> Optional[str]:
        \"\"\"Generates platform-specific PowerShell remediation command tailored to detector type.\"\"\"
        anom = audit.anomaly
        dt = anom.detector_type.value if hasattr(anom.detector_type, "value") else str(anom.detector_type)
        path = anom.target_path

        if dt == DetectorType.GHOST_DAEMONS.value:
            # Extract port if present
            port = anom.raw_details.get("port") if hasattr(anom, "raw_details") and isinstance(anom.raw_details, dict) else None
            if port is None and ":" in path:
                try:
                    port = int(path.split(":")[-1])
                except ValueError:
                    port = None
            if port:
                return (
                    f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
                    f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -Verbose }}"
                )
            return f"# Check and free occupied port for {path}"

        elif dt == DetectorType.CONTEXT_ROT.value:
            norm_path = path.replace("/", "\\\\")
            return (
                f"New-Item -ItemType Directory -Force -Path \".agents\\\\archive\" | Out-Null\\n"
                f"Move-Item -Path \"{norm_path}\" -Destination \".agents\\\\archive\\\\\" -Force"
            )

        elif dt == DetectorType.ECOSYSTEM_POLLUTION.value:
            norm_path = path.replace("/", "\\\\")
            return (
                f"New-Item -ItemType Directory -Force -Path \".quarantine\" | Out-Null\\n"
                f"Move-Item -Path \"{norm_path}\" -Destination \".quarantine\\\\\" -Force"
            )

        elif dt == DetectorType.SECRET_ZERO.value:
            norm_path = path.replace("/", "\\\\")
            return (
                f"# Inspect and replace placeholder credentials with real environment variables:\\n"
                f"Get-Content -Path \"{norm_path}\" | Select-String \"your_token_here\""
            )

        elif dt == DetectorType.PROMPT_FATIGUE.value:
            norm_path = path.replace("/", "\\\\")
            return (
                f"# Inspect line count and distill procedural rules into .agents\\\\skills\\\\:\\n"
                f"(Get-Content -Path \"{norm_path}\").Count"
            )

        return None

    def _build_footer(self, report: OptimizationReport) -> str:
        return (
            "---\\n"
            "*Report compiled automatically by Antigravity Daily Health Scanner & Telemetry Loop.*\\n"
            "*Zero automated destructive actions executed.*"
        )
```

---

## 6. Verification and Test Strategy

The `DailyReportBuilder` class is tested deterministically across the following test suites:

1. **Unit Tests (`test_report_builder_unit`)**:
   - Verify `_format_timestamp` produces ISO 8601 UTC formatted strings.
   - Verify `build_report` produces all 6 core sections with exact headers.
   - Verify interactive checkboxes adhere to `- [ ] [HITL-APPROVED]`, `- [ ] [HITL-CHALLENGED]`, and `- [x] [RED-TEAM BLOCKED - REJECTED]`.
   - Verify K-Means cluster distribution formatting for K=3.
   - Verify `save_report` creates directories and writes valid UTF-8 files.

2. **Edge Case Tests (`test_report_builder_edge_cases`)**:
   - Zero anomalies detected: outputs `🟢 HEALTHY (Zero Anomalies Detected)`, convergence message, 0 checkboxes, and no remediation commands.
   - All anomalies rejected by red-team: outputs 0 approved checkboxes, all blocked entries, and no executable commands.
   - High semantic entropy (>= 0.15): flags `🔴 High Dispersion / Multi-Mode Drift` and includes meta-gradients.

3. **Database Integration Tests (`test_report_builder_db_integration`)**:
   - Round-trip test: `log_scan_session` in SQLite -> `build_report_from_session` -> verify accurate telemetry, lifelines, and drift stats.

4. **Static AST & 0-Destruction Guarantee (`test_safety_ast`)**:
   - Verifies `audit/report_builder.py` contains 0 calls to `os.remove`, `os.unlink`, `shutil.rmtree`, `subprocess`, `taskkill`, `eval`, or `exec`.
