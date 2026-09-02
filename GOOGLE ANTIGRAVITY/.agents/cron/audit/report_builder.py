"""Daily Human-In-The-Loop (HITL) Markdown Report Builder.

Generates structured, interactive daily reports adhering to the 6 mandatory sections:
1. Executive Summary & Health Telemetry
2. Red-Team Scrutiny Verdicts
3. Proposed Optimizations (HITL Checkboxes)
4. Historical Failure Lifelines & Drift Analytics
5. ProTeGi Textual Gradients for Self-Improvement
6. Manual Remediation Command Guide (Strictly non-destructive manual commands)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from models import (
    AnomalyRecord,
    DetectorType,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)


class DailyReportBuilder:
    """Builder class that compiles the daily human-in-the-loop health & optimization report."""

    def build_daily_report(
        self,
        session_id: str,
        scan_time: Union[datetime, str, int, float],
        anomalies: List[Union[AnomalyRecord, Dict[str, Any]]],
        gradients: List[Union[str, Dict[str, Any]]],
        audit_results: List[RedTeamAuditResult],
        historical_drift: Optional[Dict[str, Any]] = None,
        duration_ms: float = 0.0,
        entropy: float = 0.0,
    ) -> str:
        """Constructs the complete 6-section Daily Health & Optimization Markdown Report."""
        # Format scan timestamp
        if isinstance(scan_time, datetime):
            formatted_time = scan_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            header_date = scan_time.strftime("%Y-%m-%d")
        elif isinstance(scan_time, (int, float)):
            dt = datetime.fromtimestamp(scan_time, timezone.utc)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            header_date = dt.strftime("%Y-%m-%d")
        else:
            formatted_time = str(scan_time)
            header_date = str(scan_time)

        drift = historical_drift or {}

        # Normalize anomalies
        records: List[AnomalyRecord] = []
        for a in anomalies:
            if isinstance(a, AnomalyRecord):
                records.append(a)
            elif isinstance(a, dict):
                records.append(AnomalyRecord.from_dict(a))

        # Normalize gradients
        grad_strings: List[str] = []
        for g in gradients:
            if isinstance(g, str):
                grad_strings.append(g)
            elif isinstance(g, dict):
                grad_strings.append(str(g.get("gradient_text", g.get("text", ""))))

        # Compute cluster breakdowns
        detector_counts: Dict[str, int] = {}
        severity_counts: Dict[str, int] = {}
        for rec in records:
            d_name = rec.detector_type.value if isinstance(rec.detector_type, DetectorType) else str(rec.detector_type)
            s_name = rec.severity.value if isinstance(rec.severity, Severity) else str(rec.severity)
            detector_counts[d_name] = detector_counts.get(d_name, 0) + 1
            severity_counts[s_name] = severity_counts.get(s_name, 0) + 1

        # Verdict counts
        approved_count = sum(1 for r in audit_results if r.verdict == RedTeamVerdict.APPROVED)
        challenged_count = sum(1 for r in audit_results if r.verdict == RedTeamVerdict.CHALLENGED)
        rejected_count = sum(1 for r in audit_results if r.verdict == RedTeamVerdict.REJECTED)

        sections: List[str] = []

        # =====================================================================
        # Report Header
        # =====================================================================
        sections.append(f"# Daily System Health & Optimization Report — {formatted_time}")
        sections.append("")

        # =====================================================================
        # Section 1: Executive Summary & Health Telemetry
        # =====================================================================
        sections.append("## 1. Executive Summary & Health Telemetry")
        sections.append(f"- **Session ID**: `{session_id}`")
        sections.append(f"- **Scan Timestamp**: {formatted_time}")
        sections.append(f"- **Scan Duration**: `{duration_ms:.2f} ms`")
        sections.append(f"- **Total Anomalies Detected**: `{len(records)}`")
        sections.append(f"- **Semantic Entropy Score**: `{entropy:.4f}`")
        sections.append("")
        sections.append("### Cluster & Anomaly Breakdown")
        if records:
            sections.append("| Category / Detector | Anomalies Count | Severity Distribution |")
            sections.append("|---|---|---|")
            for det, cnt in sorted(detector_counts.items()):
                sevs = [f"{s}: {sum(1 for r in records if (r.detector_type.value if isinstance(r.detector_type, DetectorType) else str(r.detector_type)) == det and (r.severity.value if isinstance(r.severity, Severity) else str(r.severity)) == s)}" for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"] if any((r.detector_type.value if isinstance(r.detector_type, DetectorType) else str(r.detector_type)) == det and (r.severity.value if isinstance(r.severity, Severity) else str(r.severity)) == s for r in records)]
                sections.append(f"| `{det}` | {cnt} | {', '.join(sevs)} |")
        else:
            sections.append("*All telemetry metrics nominal. Zero anomalies detected in current workspace.*")
        sections.append("")

        # =====================================================================
        # Section 2: Red-Team Scrutiny Verdicts
        # =====================================================================
        sections.append("## 2. Red-Team Scrutiny Verdicts")
        sections.append(
            f"**Summary**: Approved: `{approved_count}` | Challenged: `{challenged_count}` | Rejected: `{rejected_count}`"
        )
        sections.append("")
        if audit_results:
            sections.append("| # | Detector | Target | Severity | Red-Team Verdict | Confidence | Rationale / Critique | Recommended Action |")
            sections.append("|---|---|---|---|---|---|---|---|")
            for idx, res in enumerate(audit_results, 1):
                rec = res.anomaly
                det = rec.detector_type.value if isinstance(rec.detector_type, DetectorType) else str(rec.detector_type) if rec else "GENERAL"
                target = rec.target_path if rec else "N/A"
                sev = rec.severity.value if isinstance(rec.severity, Severity) else str(rec.severity) if rec else "LOW"
                verdict_str = res.verdict.value if isinstance(res.verdict, RedTeamVerdict) else str(res.verdict)
                conf_str = f"{res.confidence * 100:.0f}%"
                rationale = (res.rationale or res.reason or "").replace("|", "\\|")
                rec_action = (res.recommended_action or res.counter_proposal or "").replace("|", "\\|")
                sections.append(f"| {idx} | `{det}` | `{target}` | {sev} | **{verdict_str}** | {conf_str} | {rationale} | {rec_action} |")
        else:
            sections.append("*No anomalies required red-team scrutiny.*")
        sections.append("")

        # =====================================================================
        # Section 3: Proposed Optimizations (HITL Checkboxes)
        # =====================================================================
        sections.append("## 3. Proposed Optimizations (HITL Checkboxes)")
        sections.append("Select items below to authorize manual remediation actions:")
        sections.append("")
        if audit_results:
            for idx, res in enumerate(audit_results, 1):
                rec = res.anomaly
                target = rec.target_path if rec else "N/A"
                action = res.recommended_action or res.counter_proposal or "Inspect anomaly"
                if res.verdict == RedTeamVerdict.APPROVED:
                    sections.append(f"- [ ] [HITL-APPROVED] Safe Optimization: {action} (Target: `{target}`)")
                elif res.verdict == RedTeamVerdict.CHALLENGED:
                    sections.append(f"- [ ] [HITL-APPROVED] Manual Review Required: {action} (Target: `{target}`)")
                elif res.verdict == RedTeamVerdict.REJECTED:
                    sections.append(f"- [x] [REJECTED BY RED-TEAM] Blocked Action: {action} (Target: `{target}` — Reason: {res.rationale})")
        else:
            sections.append("- [ ] [HITL-APPROVED] Workspace in optimal health. Zero remediation actions required.")
        sections.append("")

        # =====================================================================
        # Section 4: Historical Failure Lifelines & Drift Analytics
        # =====================================================================
        sections.append("## 4. Historical Failure Lifelines & Drift Analytics")
        sections.append("Active surveillance of the 5 August 23/24 failure lifelines:")
        sections.append("")
        sections.append("1. **Ghost Daemons** (`GHOST_DAEMONS_WINERROR_10048`): Next.js/Uvicorn socket collisions on ports 3000/8000/8501.")
        sections.append("2. **Context Rot** (`CONTEXT_ROT_PLANNING_ARTIFACTS`): Planning artifacts older than 24 hours diluting LLM context.")
        sections.append("3. **Ecosystem Pollution** (`ECOSYSTEM_POLLUTION_DISABLED_PLUGINS`): `.disabled` plugin directories and cross-track leaks.")
        sections.append("4. **Secret Zero** (`SECRET_ZERO_PLACEHOLDER_KEYS`): Placeholder tokens (`your_token_here`) in `.env` files.")
        sections.append("5. **Prompt Fatigue** (`PROMPT_FATIGUE_MANIFEST_BLOAT`): Hardcoded procedural rules bloating `GEMINI.md` (>100 lines).")
        sections.append("")
        sections.append("### 7-Day Trend & Historical Drift Metrics")
        total_sess = drift.get("total_sessions", 1)
        total_anom = drift.get("total_anomalies", len(records))
        avg_dur = drift.get("average_duration_ms", duration_ms)
        avg_ent = drift.get("average_entropy_score", entropy)
        drift_status = "DRIFT DETECTED — Action Recommended" if drift.get("drift_detected", len(records) > 0) else "STABLE BASELINE"

        sections.append(f"- **Total Recorded Sessions**: `{total_sess}`")
        sections.append(f"- **Total Cumulative Anomalies**: `{total_anom}`")
        sections.append(f"- **Historical Average Duration**: `{avg_dur:.2f} ms`")
        sections.append(f"- **Historical Average Entropy**: `{avg_ent:.4f}`")
        sections.append(f"- **Drift Posture**: `{drift_status}`")
        sections.append("")

        # =====================================================================
        # Section 5: ProTeGi Textual Gradients for Self-Improvement
        # =====================================================================
        sections.append("## 5. ProTeGi Textual Gradients for Self-Improvement")
        sections.append("Calculated textual gradients for automatic prompt and heuristic optimization:")
        sections.append("")
        if grad_strings:
            for g in grad_strings:
                sections.append(f"- {g}")
        else:
            sections.append("- No heuristic refinement gradients generated for this session (entropy stable).")
        sections.append("")

        # =====================================================================
        # Section 6: Manual Remediation Command Guide
        # =====================================================================
        sections.append("## 6. Manual Remediation Command Guide")
        sections.append("Run the following read-only / non-destructive manual commands in PowerShell or bash to address approved items:")
        sections.append("")
        sections.append("```powershell")
        sections.append("# 1. Ghost Daemons — Inspect active port listeners without killing processes")
        sections.append("Get-NetTCPConnection -LocalPort 3000,8000,8501 -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, OwningProcess, State")
        sections.append("netstat -ano | findstr /R \":3000 :8000 :8501\"")
        sections.append("")
        sections.append("# 2. Context Rot — Safe manual archival of stale planning artifacts (>48h)")
        sections.append("Move-Item -Path \".agents/worker_*/progress.md\" -Destination \".agents/archive/\" -WhatIf")
        sections.append("")
        sections.append("# 3. Ecosystem Pollution — Isolate unused .disabled plugins to quarantine")
        sections.append("Move-Item -Path \"plugins/*.disabled\" -Destination \".quarantine/\" -WhatIf")
        sections.append("")
        sections.append("# 4. Secret Zero — Locate placeholder tokens in local environment files")
        sections.append("Select-String -Path \".env*\" -Pattern \"your_token_here|YOUR_API_KEY\"")
        sections.append("")
        sections.append("# 5. Prompt Fatigue — Verify GEMINI.md line count and rule depth")
        sections.append("(Get-Content GEMINI.md).Count")
        sections.append("```")
        sections.append("")

        return "\n".join(sections)
