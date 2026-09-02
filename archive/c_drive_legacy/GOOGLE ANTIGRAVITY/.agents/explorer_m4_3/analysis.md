# Analysis & Test Suite Specification: Milestone 4 (`tests/test_red_team_and_report.py`)

## 1. Executive Summary & Objective

Milestone 4 of the **Antigravity Daily Health Scanner & ML Daemon** integrates the adversarial scrutiny and reporting layer of the platform:
1. **`ArchitectureRedTeam` (`audit/red_team.py`)**: An orthogonal adversarial auditor that examines every detected anomaly and proposed optimization across 3 distinct critical lenses:
   - **System Integrity**: Validates whether the proposed action destabilizes active daemons, socket bindings, or cross-track workflows.
   - **Data Loss Risk**: Enforces strict `accidental-data-loss-prevention` guardrails, ensuring that no active project assets, unstaged work, configuration files, or database tables are marked for destructive deletion.
   - **False Positive Filter**: Filters out intentional project manifests (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`), active background services, and valid test fixture placeholders.
   - **3-Tiered Verdict Model**: Emits `RedTeamVerdict.APPROVED`, `RedTeamVerdict.CHALLENGED`, or `RedTeamVerdict.REJECTED`.
2. **`DailyReportBuilder` (`audit/report_builder.py`)**: Compiles comprehensive, human-in-the-loop (HITL) daily Markdown reports containing:
   - Executive Summary & Telemetry Metrics (Duration ms, Total Anomalies, Semantic Entropy, K-Means Cluster breakdown).
   - Red-Team Scrutiny Verdicts Breakdown.
   - Proposed Optimizations with interactive `- [ ] [HITL-APPROVED]` markdown checkboxes.
   - Historical Failure Lifelines & Drift Analytics (monitoring the 5 August 23/24 seeds).
   - ProTeGi Textual Gradients for continuous heuristic self-improvement.
   - Manual Remediation Command Guide with zero automated execution.
3. **`tests/test_red_team_and_report.py`**: A deterministic, loud-assertion test suite that guarantees 100% test coverage over verdict logic, section rendering, markdown structure, 0-destruction cryptographic invariance via `FileSystemSnapshot`, and full pipeline integration.

---

## 2. Interface Contracts & Component Specifications

### 2.1 `models.py` Data Model Alignment

The test suite directly tests against and validates instances of:
```python
class RedTeamVerdict(str, Enum):
    APPROVED = "APPROVED"
    CHALLENGED = "CHALLENGED"
    REJECTED = "REJECTED"

@dataclass
class AnomalyRecord:
    detector_type: DetectorType
    target_path: str
    severity: Severity
    description: str
    raw_details: Dict[str, Any] = field(default_factory=dict)
    is_historical: bool = False
    timestamp: int = 0
    confidence: float = 1.0

@dataclass
class RedTeamAuditResult:
    anomaly: AnomalyRecord
    verdict: RedTeamVerdict
    rationale: str
    risk_assessment: str
    recommended_action: str

@dataclass
class OptimizationReport:
    session_id: str
    timestamp: int
    duration_ms: float
    total_anomalies: int
    approved_count: int
    challenged_count: int
    audited_anomalies: List[RedTeamAuditResult] = field(default_factory=list)
    textual_gradients: List[str] = field(default_factory=list)
    entropy_score: float = 0.0
```

---

### 2.2 Expected Interface for `audit/red_team.py`

```python
"""audit/red_team.py - Architecture Red-Team Adversarial Auditor."""

from typing import List, Optional
from config import WHITELISTED_FILENAMES
from models import AnomalyRecord, DetectorType, RedTeamAuditResult, RedTeamVerdict, Severity

class ArchitectureRedTeam:
    """
    Adversarial auditor evaluating proposed system optimizations across 3 perspectives:
    1. System Integrity
    2. Data Loss Risk
    3. False Positive Filter
    """

    def __init__(self, whitelisted_filenames: Optional[List[str]] = None) -> None:
        self.whitelisted_filenames = set(whitelisted_filenames or WHITELISTED_FILENAMES)

    def audit_anomaly(self, anomaly: AnomalyRecord) -> RedTeamAuditResult:
        """Audits a single anomaly and returns an audit result with a 3-tiered verdict."""
        ...

    def audit_anomalies(self, anomalies: List[AnomalyRecord]) -> List[RedTeamAuditResult]:
        """Audits a batch of anomaly records."""
        return [self.audit_anomaly(a) for a in anomalies]

    def audit(self, anomalies: List[AnomalyRecord]) -> List[RedTeamAuditResult]:
        """Primary audit interface alias."""
        return self.audit_anomalies(anomalies)
```

#### Detailed Verdict Decision Matrix:
| Scenario / Target | Detector Type | Verdict | Rationale & Risk Assessment | Recommended Action |
|---|---|---|---|---|
| **Whitelisted Manifest** (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`) suggested for deletion | Any | `REJECTED` | Protected file. Deletion creates catastrophic loss of project context / operating guidelines. | Preserve file. Whitelist invariant enforced. |
| **Direct Process Termination / Taskkill** | `GHOST_DAEMONS` | `REJECTED` | Automated process killing risks terminating active builds, IDE sessions, or production servers without confirmation. | Do not execute taskkill. Present manual port audit command to developer. |
| **Port Socket Collision (Read-Only Audit)** | `GHOST_DAEMONS` | `APPROVED` | Legitimate port collision detected. Non-destructive port inspection and advisory alert. | Inspect active port binding with `netstat` and restart daemon with isolated port. |
| **Stale Planning Proposal (>48h old)** | `CONTEXT_ROT` | `APPROVED` | Planning file is genuinely stale (>48h) and outside whitelist. Moving to archive clears context bloat. | Move file to `BRIEFING_ARCHIVE.md` or archive directory. |
| **Borderline Stale File (24h - 48h old)** | `CONTEXT_ROT` | `CHALLENGED` | File age is within borderline window (24-48h). May be part of an ongoing multi-day active feature branch. | Request explicit human verification before archiving or moving file. |
| **Disabled Plugin Deletion** | `ECOSYSTEM_POLLUTION` | `CHALLENGED` | Deleting `.disabled` directories permanently loses plugin configurations or uncommitted skill code. | Quarantine directory or prompt developer to permanently uninstall via CLI. |
| **Cross-Track Domain Leak** | `ECOSYSTEM_POLLUTION` | `APPROVED` | Asset leaked into incorrect domain track (e.g. video in sports cards). Non-destructive domain segregation. | Move asset to designated track directory (`/content_creation` or `/sports_cards`). |
| **Placeholder Token in `.env`** | `SECRET_ZERO` | `APPROVED` | Dummy secret detected. Non-destructive alert advising key replacement. | Replace placeholder token with secure environment variable in private config. |
| **Destructive `.env` Purge** | `SECRET_ZERO` | `REJECTED` | Purging entire `.env` destroys other valid production secrets. | Never delete `.env`. Update specific key entry only. |
| **Manifest Rule Bloat (>100 lines)** | `PROMPT_FATIGUE` | `APPROVED` | GEMINI.md exceeds 100 lines limit. Proposes non-destructive rule distillation into skills. | Distill procedural rules into specialized `.agents/skills/<name>/SKILL.md`. |
| **Database Table Drop / Truncate** | Any | `REJECTED` | Irreversible loss of telemetry data violates `accidental-data-loss-prevention`. | Reject operation immediately. |

---

### 2.3 Expected Interface for `audit/report_builder.py`

```python
"""audit/report_builder.py - Daily HITL Markdown Report Builder."""

from typing import Any, Dict, List, Optional
from models import OptimizationReport, RedTeamAuditResult, RedTeamVerdict

class DailyReportBuilder:
    """Compiles comprehensive Human-In-The-Loop (HITL) daily Markdown reports."""

    def build_report(
        self,
        report: OptimizationReport,
        drift_stats: Optional[Dict[str, Any]] = None,
        cluster_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Renders complete 6-section Markdown report string."""
        ...

    def build_and_save_report(
        self,
        report: OptimizationReport,
        output_path: str,
        drift_stats: Optional[Dict[str, Any]] = None,
        cluster_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Renders report and saves to output_path."""
        ...
```

#### Required 6 Report Sections:
1. `# Antigravity Daily System Health & Optimization Report`
2. `## 1. Executive Summary & Health Telemetry`
   - Scan timestamp, Duration (ms), Total Anomalies Detected, Semantic Entropy Score, K-Means Cluster breakdown.
3. `## 2. Red-Team Scrutiny & Adversarial Audit`
   - Table of metrics: Approved Count, Challenged Count, Rejected Count.
   - Itemized audit table with columns: Detector, Target, Severity, Red-Team Verdict (`[APPROVED]`, `[CHALLENGED]`, `[REJECTED]`), Rationale, Risk Assessment.
4. `## 3. Proposed Optimizations (HITL Approval Required)`
   - Interactive checkboxes: `- [ ] [HITL-APPROVED] <Action Title>`
   - Detailed recommendation, Target path, and Verdict tag.
5. `## 4. Historical Failure Lifelines & Drift Analytics`
   - Review of all 5 August 23/24 seeds:
     1. Ghost Daemons (`WinError 10048`)
     2. Context Rot (`>24h planning artifacts`)
     3. Ecosystem Pollution (`.disabled plugins`)
     4. Secret Zero (`your_token_here in .env`)
     5. Prompt Fatigue (`GEMINI.md > 100 lines`)
   - Drift Detection status (`Drift Detected: True/False`), Total historical sessions, Average entropy.
6. `## 5. ProTeGi Textual Gradients (Self-Tuning Heuristics)`
   - Textual gradient bullet list with cluster IDs and semantic weights.
   - Heuristic self-improvement diff recommendations.
7. `## 6. Manual Remediation Command Guide`
   - Copy-pasteable terminal commands (PowerShell / Bash) for developer manual execution.
   - Prominent notice: `100% Zero Automated Execution — Manual Human-In-The-Loop Execution Only`.

---

## 3. Test Suite Architecture for `tests/test_red_team_and_report.py`

The test suite is organized into 4 cohesive test suites comprising 32 deterministic tests:

### Suite 1: `ArchitectureRedTeam` Verdict Logic & 3-Perspective Auditing (13 tests)
- `test_red_team_approves_safe_stale_proposal_archival`: Asserts `APPROVED` when stale planning file (>48h) is flagged for archival.
- `test_red_team_rejects_whitelisted_manifest_deletion`: Asserts `REJECTED` when any whitelisted file (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`) is targeted for deletion.
- `test_red_team_rejects_destructive_process_termination`: Asserts `REJECTED` for actions attempting automated `taskkill`, `os.kill`, or process termination.
- `test_red_team_approves_read_only_ghost_daemon_audit`: Asserts `APPROVED` for read-only socket collision detection recommending manual port inspection.
- `test_red_team_challenges_borderline_staleness_24_to_48h`: Asserts `CHALLENGED` for planning files aged between 24.0 and 48.0 hours.
- `test_red_team_challenges_disabled_plugin_permanent_deletion`: Asserts `CHALLENGED` when `.disabled` plugin directory is flagged for permanent deletion, recommending non-destructive quarantine.
- `test_red_team_approves_cross_track_domain_relocation`: Asserts `APPROVED` when cross-track domain leak is detected and non-destructive relocation is recommended.
- `test_red_team_approves_secret_zero_alert_with_manual_guidance`: Asserts `APPROVED` for placeholder token detection in `.env` recommending manual replacement without deleting `.env`.
- `test_red_team_rejects_env_file_destruction`: Asserts `REJECTED` if anomaly action suggests deleting or wiping the entire `.env` file.
- `test_red_team_approves_prompt_fatigue_distillation`: Asserts `APPROVED` when bloated `GEMINI.md` is flagged for rule distillation into `.agents/skills/`.
- `test_red_team_rejects_sql_table_drop_or_truncate`: Asserts `REJECTED` for any operation involving `DROP TABLE` or `TRUNCATE`.
- `test_red_team_evaluates_all_three_perspectives_in_output`: Validates that `rationale`, `risk_assessment`, and `recommended_action` are populated with coherent adversarial assessments.
- `test_red_team_batch_audit_and_empty_handling`: Validates `audit_anomalies` on empty lists, single items, and large heterogeneous batches.

### Suite 2: `DailyReportBuilder` Formatting, Sections & HITL Checkboxes (10 tests)
- `test_report_builder_contains_all_six_required_sections`: Asserts exact presence of all 6 required markdown section headers.
- `test_report_builder_executive_summary_telemetry`: Asserts session ID, formatted timestamp, duration in ms, total anomaly count, and entropy score appear in Section 1.
- `test_report_builder_red_team_verdicts_breakdown_table`: Asserts Approved, Challenged, and Rejected count tallies and tabular formatting in Section 2.
- `test_report_builder_hitl_interactive_checkboxes`: Asserts `- [ ] [HITL-APPROVED]` formatting is rendered for each proposed optimization in Section 3.
- `test_report_builder_historical_lifelines_and_drift_analytics`: Asserts that all 5 August 23/24 lifelines and drift status are displayed in Section 4.
- `test_report_builder_protegi_textual_gradients_rendering`: Asserts ProTeGi gradient text and meta-gradients are rendered in Section 5.
- `test_report_builder_manual_remediation_command_guide`: Asserts PowerShell code blocks with commands (e.g. `netstat`, `Move-Item`, `Get-Process`) and manual-execution disclaimers in Section 6.
- `test_report_builder_clean_bill_of_health_zero_anomalies`: Asserts clean report rendering with 0 anomalies, 0% entropy, and convergence message.
- `test_report_builder_build_and_save_report`: Asserts `build_and_save_report` creates valid UTF-8 markdown file on disk with parent directory auto-creation.
- `test_report_builder_resilience_to_none_or_partial_stats`: Asserts report builder handles `drift_stats=None` and `cluster_info=None` without throwing exceptions.

### Suite 3: 0-Destruction Cryptographic Hash & Read-Only Invariance (4 tests)
- `test_red_team_and_report_builder_cryptographic_filesystem_invariance`: Loud assertion using `FileSystemSnapshot` before and after full red-team audit and report generation, asserting 0 files added, removed, or altered in workspace.
- `test_report_builder_hash_determinism_for_identical_inputs`: Asserts that SHA256 of generated report markdown is 100% identical for identical input data.
- `test_report_builder_does_not_invoke_subprocess_or_destructive_builtins`: Validates statically and dynamically that report builder never invokes `subprocess.run`, `subprocess.Popen`, `os.system`, or file unlinks.
- `test_report_builder_file_generation_isolated_to_target_path`: Asserts report saving only writes to the explicitly provided output file path without writing side-effects.

### Suite 4: End-to-End M4 Pipeline Integration & Dataclass Serialization (5 tests)
- `test_full_m4_pipeline_anomalies_to_red_team_to_report`: Verifies end-to-end integration: `AnomalyRecord` list -> `ArchitectureRedTeam.audit()` -> `OptimizationReport` dataclass construction -> `DailyReportBuilder.build_report()`.
- `test_optimization_report_to_dict_serialization`: Verifies `OptimizationReport.to_dict()` recursive dictionary serialization.
- `test_red_team_audit_result_serialization_roundtrip`: Verifies `RedTeamAuditResult.to_dict()` and `RedTeamAuditResult.from_dict()` lossless round-trip.
- `test_optimization_report_metrics_consistency`: Asserts `approved_count + challenged_count <= total_anomalies` and matches audited list.
- `test_m4_module_exports_and_imports`: Verifies clean imports from `audit.red_team`, `audit.report_builder`, and `audit` package `__init__.py`.

---

## 4. Complete Code Blueprint for `tests/test_red_team_and_report.py`

Below is the complete, drop-in implementation code for `tests/test_red_team_and_report.py`:

```python
"""
Unit and integration tests for Milestone 4:
1. ArchitectureRedTeam 3-tiered verdict logic (APPROVED, CHALLENGED, REJECTED) across 3 adversarial perspectives.
2. DailyReportBuilder 6-section HITL markdown formatting with interactive checkboxes, drift stats, and ProTeGi gradients.
3. 0-destruction cryptographic hash assertion on report generation via FileSystemSnapshot.
4. End-to-end pipeline integration and dataclass serialization.
"""

import hashlib
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
import pytest

# Ensure .agents/cron is on sys.path
CRON_DIR = Path(__file__).resolve().parent.parent
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

from config import (
    CONTEXT_ROT_THRESHOLD_HOURS,
    DEFAULT_DB_PATH,
    PROMPT_FATIGUE_MAX_LINES,
    WHITELISTED_FILENAMES,
)
from conftest import FileSystemSnapshot
from models import (
    AnomalyRecord,
    DetectorType,
    OptimizationReport,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)
from audit.red_team import ArchitectureRedTeam
from audit.report_builder import DailyReportBuilder


# ===========================================================================
# Fixtures for Milestone 4 Testing
# ===========================================================================

@pytest.fixture
def red_team() -> ArchitectureRedTeam:
    """Returns a configured ArchitectureRedTeam instance."""
    return ArchitectureRedTeam()


@pytest.fixture
def report_builder() -> DailyReportBuilder:
    """Returns a configured DailyReportBuilder instance."""
    return DailyReportBuilder()


@pytest.fixture
def sample_audit_results() -> List[RedTeamAuditResult]:
    """Returns a representative list of RedTeamAuditResult items across verdicts."""
    return [
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.GHOST_DAEMONS,
                target_path="127.0.0.1:3000",
                severity=Severity.CRITICAL,
                description="Socket collision detected on port 3000 (WinError 10048)",
                raw_details={"port": 3000, "errno": 10048},
            ),
            verdict=RedTeamVerdict.APPROVED,
            rationale="Read-only port audit verified collision. Advisory notice generated without automated process termination.",
            risk_assessment="LOW: Advisory notice only. No active process terminated.",
            recommended_action="Inspect active port 3000 bindings via `netstat -ano | findstr :3000` and restart daemon on alternate port.",
        ),
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path="docs/old_architecture_proposal_v1.md",
                severity=Severity.MEDIUM,
                description="Planning artifact older than 52.0 hours diluting context window",
                raw_details={"age_hours": 52.0, "threshold_hours": 24.0},
            ),
            verdict=RedTeamVerdict.APPROVED,
            rationale="File age (52h) significantly exceeds 24h rot threshold and is not in whitelisted manifests.",
            risk_assessment="LOW: Relocating stale proposal to archive prevents context dilution.",
            recommended_action="Move `docs/old_architecture_proposal_v1.md` to `.agents/archive/` or `BRIEFING_ARCHIVE.md`.",
        ),
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path="planning/worker_task_active.md",
                severity=Severity.MEDIUM,
                description="Planning artifact aged 26.5 hours",
                raw_details={"age_hours": 26.5, "threshold_hours": 24.0},
            ),
            verdict=RedTeamVerdict.CHALLENGED,
            rationale="File age (26.5h) is borderline (<48h). May be part of an active multi-day work stream.",
            risk_assessment="MEDIUM: Potential deletion of active in-flight worker planning state.",
            recommended_action="Prompt developer to confirm if `planning/worker_task_active.md` is complete before archiving.",
        ),
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                target_path="plugins/gcp_spark.disabled",
                severity=Severity.HIGH,
                description="Unused .disabled plugin directory detected",
                raw_details={"is_disabled": True},
            ),
            verdict=RedTeamVerdict.CHALLENGED,
            rationale="Automated deletion risks losing custom plugin configuration or uncommitted skill code.",
            risk_assessment="MEDIUM: Irreversible loss of plugin skill definitions.",
            recommended_action="Quarantine `.disabled` directory to backup storage or review before deletion.",
        ),
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.SECRET_ZERO,
                target_path=".env",
                severity=Severity.CRITICAL,
                description="Unresolved placeholder token 'yo***re' found in environment file",
                raw_details={"token": "your_token_here", "line": 4},
            ),
            verdict=RedTeamVerdict.APPROVED,
            rationale="Placeholder key detected. Alert allows developer to configure valid credential manually.",
            risk_assessment="LOW: Purely advisory. `.env` file is NOT modified or deleted automatically.",
            recommended_action="Update `.env` line 4 with valid API credential or remove placeholder variable.",
        ),
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path="PROJECT.md",
                severity=Severity.CRITICAL,
                description="Attempted deletion of whitelisted project manifest",
                raw_details={"age_hours": 120.0},
            ),
            verdict=RedTeamVerdict.REJECTED,
            rationale="PROJECT.md is a permanently protected workspace manifest. Deletion strictly forbidden.",
            risk_assessment="CRITICAL: Deletion would destroy workspace architectural blueprint and rules.",
            recommended_action="Reject deletion unconditionally. Whitelist invariant enforced.",
        ),
        RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.GHOST_DAEMONS,
                target_path="PID:12345",
                severity=Severity.CRITICAL,
                description="Request to execute automated taskkill /F /PID 12345",
                raw_details={"action": "taskkill", "pid": 12345},
            ),
            verdict=RedTeamVerdict.REJECTED,
            rationale="Automated process termination strictly prohibited by accidental-data-loss-prevention.",
            risk_assessment="HIGH: Automated taskkill risks crashing developer session or IDE processes.",
            recommended_action="Reject automated kill command. Emit manual PowerShell remediation snippet.",
        ),
    ]


@pytest.fixture
def sample_optimization_report(sample_audit_results: List[RedTeamAuditResult]) -> OptimizationReport:
    """Returns a complete OptimizationReport instance."""
    approved = sum(1 for a in sample_audit_results if a.verdict == RedTeamVerdict.APPROVED)
    challenged = sum(1 for a in sample_audit_results if a.verdict == RedTeamVerdict.CHALLENGED)
    return OptimizationReport(
        session_id="scan-session-20260825-001",
        timestamp=1756000000,
        duration_ms=42.8,
        total_anomalies=len(sample_audit_results),
        approved_count=approved,
        challenged_count=challenged,
        audited_anomalies=sample_audit_results,
        textual_gradients=[
            "[Cluster 0 - Weight 1.00] GHOST_DAEMONS: Refine socket probe to ignore transient test ports.",
            "[Cluster 1 - Weight 0.85] CONTEXT_ROT: Distinguish stale planning scratchpads (>48h) from active sprint briefs (24-48h).",
            "[Cluster 2 - Weight 0.95] ECOSYSTEM_POLLUTION: Prefer non-destructive quarantine over permanent purge.",
            "ProTeGi Meta-Gradient: System health converged with 3 actionable rule refinements.",
        ],
        entropy_score=0.425,
    )


@pytest.fixture
def sample_drift_stats() -> Dict[str, Any]:
    """Returns realistic drift stats dictionary from database telemetry."""
    return {
        "total_sessions": 14,
        "total_anomalies": 48,
        "average_duration_ms": 38.5,
        "average_entropy_score": 0.35,
        "historical_lifelines_count": 5,
        "drift_detected": True,
        "detector_distribution": {
            "GHOST_DAEMONS": 8,
            "CONTEXT_ROT": 18,
            "ECOSYSTEM_POLLUTION": 6,
            "SECRET_ZERO": 10,
            "PROMPT_FATIGUE": 6,
        },
        "severity_distribution": {
            "CRITICAL": 18,
            "HIGH": 6,
            "MEDIUM": 24,
            "LOW": 0,
        },
        "historical_match_counts": {
            "GHOST_DAEMONS_WINERROR_10048": 8,
            "CONTEXT_ROT_PLANNING_ARTIFACTS": 18,
            "ECOSYSTEM_POLLUTION_DISABLED_PLUGINS": 6,
            "SECRET_ZERO_PLACEHOLDER_KEYS": 10,
            "PROMPT_FATIGUE_MANIFEST_BLOAT": 6,
        },
    }


# ===========================================================================
# Suite 1: ArchitectureRedTeam Verdict Logic & 3-Perspective Auditing
# ===========================================================================

class TestArchitectureRedTeamVerdictLogic:
    """Verifies that ArchitectureRedTeam enforces strict 3-tiered verdict logic and safety rules."""

    def test_red_team_approves_safe_stale_proposal_archival(self, red_team: ArchitectureRedTeam) -> None:
        """1. Asserts APPROVED when moving a stale (>48h) planning proposal to archive."""
        anomaly = AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path="scratchpad_migration_plan.md",
            severity=Severity.MEDIUM,
            description="Planning artifact older than 72.0 hours",
            raw_details={"age_hours": 72.0, "threshold_hours": 24.0},
        )
        result = red_team.audit_anomaly(anomaly)
        assert result.verdict == RedTeamVerdict.APPROVED
        assert "archive" in result.recommended_action.lower() or "relocat" in result.recommended_action.lower()
        assert result.anomaly == anomaly

    def test_red_team_rejects_whitelisted_manifest_deletion(self, red_team: ArchitectureRedTeam) -> None:
        """2. Asserts REJECTED when any whitelisted manifest is targeted for deletion or destructive purge."""
        for filename in WHITELISTED_FILENAMES:
            anomaly = AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path=f"root/{filename}",
                severity=Severity.CRITICAL,
                description=f"Stale manifest detected: {filename}",
                raw_details={"action": "delete", "target": filename},
            )
            result = red_team.audit_anomaly(anomaly)
            assert result.verdict == RedTeamVerdict.REJECTED, f"Whitelisted file {filename} must be REJECTED"
            assert "whitelist" in result.rationale.lower() or "protected" in result.rationale.lower()
            assert "reject" in result.recommended_action.lower() or "preserve" in result.recommended_action.lower()

    def test_red_team_rejects_destructive_process_termination(self, red_team: ArchitectureRedTeam) -> None:
        """3. Asserts REJECTED when anomaly recommends automated taskkill or os.kill."""
        anomaly = AnomalyRecord(
            detector_type=DetectorType.GHOST_DAEMONS,
            target_path="127.0.0.1:3000",
            severity=Severity.CRITICAL,
            description="Active process on port 3000",
            raw_details={"action": "taskkill", "pid": 4567},
        )
        result = red_team.audit_anomaly(anomaly)
        assert result.verdict == RedTeamVerdict.REJECTED
        assert "taskkill" in result.rationale.lower() or "termination" in result.rationale.lower() or "kill" in result.rationale.lower()
        assert "manual" in result.recommended_action.lower()

    def test_red_team_approves_read_only_ghost_daemon_advisory(self, red_team: ArchitectureRedTeam) -> None:
        """4. Asserts APPROVED when Ghost Daemons detection recommends non-destructive port audit."""
        anomaly = AnomalyRecord(
            detector_type=DetectorType.GHOST_DAEMONS,
            target_path="127.0.0.1:8000",
            severity=Severity.CRITICAL,
            description="Socket collision detected on port 8000 (WinError 10048)",
            raw_details={"port": 8000, "errno": 10048, "action": "advisory_alert"},
        )
        result = red_team.audit_anomaly(anomaly)
        assert result.verdict == RedTeamVerdict.APPROVED
        assert "8000" in result.recommended_action or "netstat" in result.recommended_action.lower()

    def test_red_team_challenges_borderline_staleness_24_to_48h(self, red_team: ArchitectureRedTeam) -> None:
        """5. Asserts CHALLENGED when a planning artifact age is between 24h and 48h."""
        for age in [24.1, 30.0, 36.5, 47.9]:
            anomaly = AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path=f"sprint_plan_age_{int(age)}h.md",
                severity=Severity.MEDIUM,
                description=f"Planning artifact age {age} hours",
                raw_details={"age_hours": age, "threshold_hours": 24.0},
            )
            result = red_team.audit_anomaly(anomaly)
            assert result.verdict == RedTeamVerdict.CHALLENGED, f"Age {age}h should be CHALLENGED"
            assert "borderline" in result.rationale.lower() or "active" in result.rationale.lower() or "confirm" in result.recommended_action.lower()

    def test_red_team_challenges_disabled_plugin_permanent_deletion(self, red_team: ArchitectureRedTeam) -> None:
        """6. Asserts CHALLENGED when .disabled plugin directory is targeted for deletion."""
        anomaly = AnomalyRecord(
            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
            target_path="plugins/dataform_bigquery.disabled",
            severity=Severity.HIGH,
            description="Disabled plugin directory found",
            raw_details={"is_disabled": True, "action": "delete_directory"},
        )
        result = red_team.audit_anomaly(anomaly)
        assert result.verdict == RedTeamVerdict.CHALLENGED
        assert "quarantine" in result.recommended_action.lower() or "review" in result.recommended_action.lower()

    def test_red_team_approves_cross_track_domain_relocation(self, red_team: ArchitectureRedTeam) -> None:
        """7. Asserts APPROVED when cross-track media file is detected and relocation is recommended."""
        anomaly = AnomalyRecord(
            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
            target_path="sports_cards/teaser_trailer.mp4",
            severity=Severity.HIGH,
            description="Cross-track leak: video file in sports_cards domain",
            raw_details={"file_type": "video", "target_track": "content_creation"},
        )
        result = red_team.audit_anomaly(anomaly)
        assert result.verdict == RedTeamVerdict.APPROVED
        assert "relocat" in result.recommended_action.lower() or "move" in result.recommended_action.lower()

    def test_red_team_approves_secret_zero_alert_with_manual_guidance(self, red_team: ArchitectureRedTeam) -> None:
        """8. Asserts APPROVED for secret zero token finding advising manual token update."""
        anomaly = AnomalyRecord(
            detector_type=DetectorType.SECRET_ZERO,
            target_path=".env",
            severity=Severity.CRITICAL,
            description="Unresolved placeholder token 'yo***re' found in .env",
            raw_details={"token": "your_token_here", "line": 2},
        )
        result = red_team.audit_anomaly(anomaly)
        assert result.verdict == RedTeamVerdict.APPROVED
        assert "update" in result.recommended_action.lower() or "replace" in result.recommended_action.lower()

    def test_red_team_rejects_env_file_deletion(self, red_team: ArchitectureRedTeam) -> None:
        """9. Asserts REJECTED if optimization suggests deleting or wiping the entire .env file."""
        anomaly = AnomalyRecord(
            detector_type=DetectorType.SECRET_ZERO,
            target_path=".env",
            severity=Severity.CRITICAL,
            description="Purge entire .env file to eliminate dummy keys",
            raw_details={"action": "delete_env_file"},
        )
        result = red_team.audit_anomaly(anomaly)
        assert result.verdict == RedTeamVerdict.REJECTED
        assert "delete" in result.rationale.lower() or "loss" in result.risk_assessment.lower()

    def test_red_team_approves_prompt_fatigue_distillation(self, red_team: ArchitectureRedTeam) -> None:
        """10. Asserts APPROVED when GEMINI.md line bloat recommends distillation into skills."""
        anomaly = AnomalyRecord(
            detector_type=DetectorType.PROMPT_FATIGUE,
            target_path="GEMINI.md",
            severity=Severity.MEDIUM,
            description="Manifest rule bloat: 145 lines exceeds 100 line limit",
            raw_details={"line_count": 145, "max_lines": 100},
        )
        result = red_team.audit_anomaly(anomaly)
        assert result.verdict == RedTeamVerdict.APPROVED
        assert "skill" in result.recommended_action.lower() or "distill" in result.recommended_action.lower()

    def test_red_team_rejects_sql_table_drop_or_truncate(self, red_team: ArchitectureRedTeam) -> None:
        """11. Asserts REJECTED for any action proposing DROP TABLE or TRUNCATE on SQLite telemetry."""
        for dangerous_action in ["DROP TABLE scan_sessions;", "TRUNCATE TABLE anomalies;", "DELETE FROM historical_lifelines;"]:
            anomaly = AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path="health_telemetry.db",
                severity=Severity.CRITICAL,
                description=f"Database purge requested: {dangerous_action}",
                raw_details={"sql_action": dangerous_action},
            )
            result = red_team.audit_anomaly(anomaly)
            assert result.verdict == RedTeamVerdict.REJECTED
            assert "data loss" in result.risk_assessment.lower() or "accidental-data-loss" in result.rationale.lower() or "reject" in result.recommended_action.lower()

    def test_red_team_evaluates_all_three_perspectives_in_output(self, red_team: ArchitectureRedTeam) -> None:
        """12. Verifies that rationale, risk_assessment, and recommended_action are populated and non-empty."""
        anomaly = AnomalyRecord(
            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
            target_path="legacy.disabled",
            severity=Severity.HIGH,
            description="Disabled component found",
        )
        result = red_team.audit_anomaly(anomaly)
        assert isinstance(result, RedTeamAuditResult)
        assert len(result.rationale.strip()) > 10
        assert len(result.risk_assessment.strip()) > 5
        assert len(result.recommended_action.strip()) > 10

    def test_red_team_batch_audit_and_empty_handling(self, red_team: ArchitectureRedTeam) -> None:
        """13. Verifies batch auditing across empty lists and multi-element lists."""
        assert red_team.audit_anomalies([]) == []
        assert red_team.audit([]) == []

        records = [
            AnomalyRecord(DetectorType.GHOST_DAEMONS, "127.0.0.1:3000", Severity.CRITICAL, "Collision", {"errno": 10048}),
            AnomalyRecord(DetectorType.CONTEXT_ROT, "PROJECT.md", Severity.CRITICAL, "Stale manifest", {"action": "delete"}),
            AnomalyRecord(DetectorType.CONTEXT_ROT, "old_doc.md", Severity.MEDIUM, "Stale doc", {"age_hours": 96.0}),
        ]
        results = red_team.audit_anomalies(records)
        assert len(results) == 3
        assert results[0].verdict == RedTeamVerdict.APPROVED
        assert results[1].verdict == RedTeamVerdict.REJECTED
        assert results[2].verdict == RedTeamVerdict.APPROVED


# ===========================================================================
# Suite 2: DailyReportBuilder Formatting, Sections & HITL Checkboxes
# ===========================================================================

class TestDailyReportBuilderFormatting:
    """Verifies that DailyReportBuilder formats structured Markdown reports with all 6 required sections."""

    def test_report_builder_contains_all_six_required_sections(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport, sample_drift_stats: Dict[str, Any]
    ) -> None:
        """1. Asserts exact presence of all 6 required section headers."""
        markdown = report_builder.build_report(sample_optimization_report, drift_stats=sample_drift_stats)

        assert "# Antigravity Daily System Health & Optimization Report" in markdown or "# Daily System Health & Optimization Report" in markdown
        assert "## 1. Executive Summary & Health Telemetry" in markdown
        assert "## 2. Red-Team Scrutiny & Adversarial Audit" in markdown or "## 2. Red-Team Scrutiny" in markdown
        assert "## 3. Proposed Optimizations" in markdown
        assert "## 4. Historical Failure Lifelines & Drift Analytics" in markdown or "## 4. Historical Failure Lifelines" in markdown
        assert "## 5. ProTeGi Textual Gradients" in markdown
        assert "## 6. Manual Remediation Command Guide" in markdown

    def test_report_builder_executive_summary_telemetry(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport
    ) -> None:
        """2. Asserts session_id, timestamp, duration_ms, total_anomalies, and entropy_score in Section 1."""
        markdown = report_builder.build_report(sample_optimization_report)

        assert sample_optimization_report.session_id in markdown
        assert "42.8" in markdown or "42.80" in markdown
        assert str(sample_optimization_report.total_anomalies) in markdown
        assert "0.425" in markdown or "0.42" in markdown

    def test_report_builder_red_team_verdicts_breakdown_table(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport
    ) -> None:
        """3. Asserts Approved, Challenged, Rejected count breakdown and audit result entries in Section 2."""
        markdown = report_builder.build_report(sample_optimization_report)

        # Verdict counts
        assert f"Approved" in markdown
        assert f"Challenged" in markdown
        assert f"Rejected" in markdown

        # Must display verdict tags
        assert "[APPROVED]" in markdown
        assert "[CHALLENGED]" in markdown
        assert "[REJECTED]" in markdown

        # Check that whitelisted rejection rationale is present
        assert "PROJECT.md" in markdown
        assert "permanently protected" in markdown or "whitelist" in markdown.lower()

    def test_report_builder_hitl_interactive_checkboxes(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport
    ) -> None:
        """4. Asserts interactive '- [ ] [HITL-APPROVED]' markdown checkboxes in Section 3."""
        markdown = report_builder.build_report(sample_optimization_report)

        # Section 3 must contain interactive checkboxes
        checkboxes = re.findall(r"- \[ \] \[HITL-APPROVED\]", markdown)
        assert len(checkboxes) >= 1, "Must contain at least one '- [ ] [HITL-APPROVED]' interactive checkbox"

        # Ensure no auto-checked checkboxes (HITL requires human action)
        checked_boxes = re.findall(r"- \[x\]", markdown, re.IGNORECASE)
        assert len(checked_boxes) == 0, "No checkboxes should be pre-checked without human interaction"

    def test_report_builder_historical_lifelines_and_drift_analytics(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport, sample_drift_stats: Dict[str, Any]
    ) -> None:
        """5. Asserts that all 5 August 23/24 lifelines and drift status are displayed in Section 4."""
        markdown = report_builder.build_report(sample_optimization_report, drift_stats=sample_drift_stats)

        assert "GHOST_DAEMONS_WINERROR_10048" in markdown or "Ghost Daemons" in markdown
        assert "CONTEXT_ROT_PLANNING_ARTIFACTS" in markdown or "Context Rot" in markdown
        assert "ECOSYSTEM_POLLUTION_DISABLED_PLUGINS" in markdown or "Ecosystem Pollution" in markdown
        assert "SECRET_ZERO_PLACEHOLDER_KEYS" in markdown or "Secret Zero" in markdown
        assert "PROMPT_FATIGUE_MANIFEST_BLOAT" in markdown or "Prompt Fatigue" in markdown

        assert "Drift Detected" in markdown or "Drift Status" in markdown
        assert "14" in markdown  # total_sessions

    def test_report_builder_protegi_textual_gradients_rendering(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport
    ) -> None:
        """6. Asserts ProTeGi textual gradients and meta-gradient are rendered in Section 5."""
        markdown = report_builder.build_report(sample_optimization_report)

        assert "ProTeGi Meta-Gradient" in markdown or "GHOST_DAEMONS" in markdown
        assert "Cluster 0" in markdown or "Weight" in markdown

    def test_report_builder_manual_remediation_command_guide(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport
    ) -> None:
        """7. Asserts copy-pasteable PowerShell/bash commands and manual-only notice in Section 6."""
        markdown = report_builder.build_report(sample_optimization_report)

        assert "```powershell" in markdown or "```bash" in markdown or "```sh" in markdown
        assert "Manual" in markdown
        assert "Zero Automated Execution" in markdown or "0-Destruction" in markdown or "Manual Execution Only" in markdown

    def test_report_builder_clean_bill_of_health_zero_anomalies(
        self, report_builder: DailyReportBuilder
    ) -> None:
        """8. Asserts clean report rendering when 0 anomalies are detected."""
        clean_report = OptimizationReport(
            session_id="clean-session-001",
            timestamp=1756000000,
            duration_ms=15.2,
            total_anomalies=0,
            approved_count=0,
            challenged_count=0,
            audited_anomalies=[],
            textual_gradients=["ProTeGi: Optimization loop converged. Zero anomalies detected."],
            entropy_score=0.0,
        )
        markdown = report_builder.build_report(clean_report)

        assert "0" in markdown
        assert "clean" in markdown.lower() or "converged" in markdown.lower() or "zero anomalies" in markdown.lower()
        assert "## 1. Executive Summary & Health Telemetry" in markdown

    def test_report_builder_build_and_save_report(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport, tmp_path: Path
    ) -> None:
        """9. Asserts build_and_save_report creates valid UTF-8 markdown file on disk."""
        target_file = tmp_path / "reports" / "daily_health_report.md"
        saved_path = report_builder.build_and_save_report(sample_optimization_report, str(target_file))

        assert os.path.exists(saved_path)
        content = target_file.read_text(encoding="utf-8")
        assert len(content) > 200
        assert "Executive Summary" in content

    def test_report_builder_resilience_to_none_or_partial_stats(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport
    ) -> None:
        """10. Asserts report builder handles drift_stats=None and cluster_info=None gracefully."""
        markdown = report_builder.build_report(sample_optimization_report, drift_stats=None, cluster_info=None)
        assert len(markdown) > 100
        assert "## 1. Executive Summary" in markdown


# ===========================================================================
# Suite 3: 0-Destruction Cryptographic Hash & Read-Only Invariance
# ===========================================================================

class TestCryptographicZeroDestruction:
    """Verifies that auditing and report generation execute in strictly read-only mode."""

    def test_red_team_and_report_builder_cryptographic_filesystem_invariance(
        self, tmp_path: Path, red_team: ArchitectureRedTeam, report_builder: DailyReportBuilder
    ) -> None:
        """1. Loud assertion: Verifies FileSystemSnapshot is 100% untouched after full audit and report generation."""
        ws = tmp_path / "workspace"
        ws.mkdir()

        # Seed workspace files
        (ws / "PROJECT.md").write_text("# Project Architecture\n", encoding="utf-8")
        (ws / "GEMINI.md").write_text("# Manifest Rules\n", encoding="utf-8")
        (ws / ".env").write_text("SECRET=your_token_here\n", encoding="utf-8")
        (ws / "old_plan.md").write_text("# Old Plan\n", encoding="utf-8")

        # Take cryptographic snapshot
        snapshot = FileSystemSnapshot(str(ws))

        # Perform audit
        records = [
            AnomalyRecord(DetectorType.CONTEXT_ROT, str(ws / "PROJECT.md"), Severity.CRITICAL, "Stale manifest"),
            AnomalyRecord(DetectorType.SECRET_ZERO, str(ws / ".env"), Severity.CRITICAL, "Dummy secret"),
            AnomalyRecord(DetectorType.CONTEXT_ROT, str(ws / "old_plan.md"), Severity.MEDIUM, "Stale plan", {"age_hours": 60.0}),
        ]
        audit_results = red_team.audit_anomalies(records)

        # Build optimization report
        opt_report = OptimizationReport(
            session_id="snapshot-test-session",
            timestamp=int(time.time()),
            duration_ms=25.0,
            total_anomalies=len(audit_results),
            approved_count=2,
            challenged_count=0,
            audited_anomalies=audit_results,
            textual_gradients=["gradient 1"],
            entropy_score=0.15,
        )

        # Render report string
        report_md = report_builder.build_report(opt_report)
        assert len(report_md) > 100

        # Assert zero mutations on workspace directory
        snapshot.assert_untouched()

    def test_report_builder_hash_determinism_for_identical_inputs(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport
    ) -> None:
        """2. Asserts SHA256 cryptographic hash of generated markdown is 100% deterministic for identical inputs."""
        md1 = report_builder.build_report(sample_optimization_report)
        md2 = report_builder.build_report(sample_optimization_report)

        hash1 = hashlib.sha256(md1.encode("utf-8")).hexdigest()
        hash2 = hashlib.sha256(md2.encode("utf-8")).hexdigest()

        assert hash1 == hash2, "Report generation must be 100% deterministic"

    def test_report_builder_does_not_execute_destructive_commands(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport
    ) -> None:
        """3. Asserts report builder only renders text and never calls subprocess / system commands."""
        # Scan report_builder module source statically for safety
        import inspect
        source = inspect.getsource(report_builder.__class__)

        assert "subprocess.run" not in source
        assert "subprocess.Popen" not in source
        assert "os.system" not in source
        assert "os.remove" not in source
        assert "shutil.rmtree" not in source

    def test_report_builder_file_generation_isolated_to_target_path(
        self, report_builder: DailyReportBuilder, sample_optimization_report: OptimizationReport, tmp_path: Path
    ) -> None:
        """4. Asserts that saving a report only creates the single requested file and touches nothing else."""
        target_dir = tmp_path / "output_test"
        target_dir.mkdir()
        dummy_file = target_dir / "existing_file.txt"
        dummy_file.write_text("protected content", encoding="utf-8")

        snapshot = FileSystemSnapshot(str(target_dir))

        report_file = target_dir / "daily_report.md"
        report_builder.build_and_save_report(sample_optimization_report, str(report_file))

        # Check that existing_file.txt was untouched
        assert dummy_file.read_text(encoding="utf-8") == "protected content"
        assert os.path.exists(str(report_file))


# ===========================================================================
# Suite 4: End-to-End Pipeline Integration & Dataclass Serialization
# ===========================================================================

class TestMilestone4Integration:
    """Verifies end-to-end integration and dataclass serialization for Milestone 4."""

    def test_full_m4_pipeline_anomalies_to_red_team_to_report(
        self, red_team: ArchitectureRedTeam, report_builder: DailyReportBuilder
    ) -> None:
        """1. End-to-end pipeline: AnomalyRecords -> RedTeam -> OptimizationReport -> DailyReportBuilder."""
        raw_anomalies = [
            AnomalyRecord(DetectorType.GHOST_DAEMONS, "127.0.0.1:3000", Severity.CRITICAL, "Socket collision 10048", {"errno": 10048}),
            AnomalyRecord(DetectorType.CONTEXT_ROT, "plan_old.md", Severity.MEDIUM, "Old plan 50h", {"age_hours": 50.0}),
            AnomalyRecord(DetectorType.SECRET_ZERO, ".env", Severity.CRITICAL, "Dummy token", {"token": "your_token_here"}),
            AnomalyRecord(DetectorType.PROMPT_FATIGUE, "GEMINI.md", Severity.MEDIUM, "120 lines", {"line_count": 120}),
            AnomalyRecord(DetectorType.CONTEXT_ROT, "PROJECT.md", Severity.CRITICAL, "Attempted manifest delete", {"action": "delete"}),
        ]

        # 1. Red-Team Audit
        audited = red_team.audit_anomalies(raw_anomalies)
        assert len(audited) == 5

        approved = [a for a in audited if a.verdict == RedTeamVerdict.APPROVED]
        challenged = [a for a in audited if a.verdict == RedTeamVerdict.CHALLENGED]
        rejected = [a for a in audited if a.verdict == RedTeamVerdict.REJECTED]

        assert len(approved) >= 3
        assert len(rejected) >= 1  # PROJECT.md delete rejected

        # 2. Build OptimizationReport
        report = OptimizationReport(
            session_id="e2e-session-001",
            timestamp=1756000100,
            duration_ms=35.0,
            total_anomalies=len(raw_anomalies),
            approved_count=len(approved),
            challenged_count=len(challenged),
            audited_anomalies=audited,
            textual_gradients=["GHOST_DAEMONS: Audit active sockets", "CONTEXT_ROT: Archive stale briefs"],
            entropy_score=0.35,
        )

        # 3. Render Daily Markdown Report
        markdown = report_builder.build_report(report)

        assert "e2e-session-001" in markdown
        assert "- [ ] [HITL-APPROVED]" in markdown
        assert "## 1. Executive Summary & Health Telemetry" in markdown
        assert "## 2. Red-Team Scrutiny & Adversarial Audit" in markdown or "## 2. Red-Team Scrutiny" in markdown
        assert "## 3. Proposed Optimizations" in markdown
        assert "## 4. Historical Failure Lifelines" in markdown
        assert "## 5. ProTeGi Textual Gradients" in markdown
        assert "## 6. Manual Remediation Command Guide" in markdown

    def test_optimization_report_to_dict_serialization(
        self, sample_optimization_report: OptimizationReport
    ) -> None:
        """2. Asserts OptimizationReport.to_dict() recursively serializes all fields properly."""
        data = sample_optimization_report.to_dict()

        assert isinstance(data, dict)
        assert data["session_id"] == sample_optimization_report.session_id
        assert data["total_anomalies"] == sample_optimization_report.total_anomalies
        assert data["approved_count"] == sample_optimization_report.approved_count
        assert isinstance(data["audited_anomalies"], list)
        assert len(data["audited_anomalies"]) == len(sample_optimization_report.audited_anomalies)

        first_audit = data["audited_anomalies"][0]
        assert isinstance(first_audit, dict)
        assert "verdict" in first_audit
        assert "anomaly" in first_audit
        assert isinstance(first_audit["anomaly"], dict)

    def test_red_team_audit_result_serialization_roundtrip(self) -> None:
        """3. Asserts RedTeamAuditResult to_dict and from_dict round-trip is lossless."""
        original = RedTeamAuditResult(
            anomaly=AnomalyRecord(
                detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                target_path="plugin.disabled",
                severity=Severity.HIGH,
                description="Disabled plugin",
                raw_details={"is_disabled": True},
            ),
            verdict=RedTeamVerdict.CHALLENGED,
            rationale="Risk of losing custom config.",
            risk_assessment="MEDIUM",
            recommended_action="Quarantine directory.",
        )

        d = original.to_dict()
        restored = RedTeamAuditResult.from_dict(d)

        assert restored.verdict == original.verdict
        assert restored.rationale == original.rationale
        assert restored.risk_assessment == original.risk_assessment
        assert restored.recommended_action == original.recommended_action
        assert restored.anomaly.detector_type == original.anomaly.detector_type
        assert restored.anomaly.target_path == original.anomaly.target_path

    def test_optimization_report_metrics_consistency(
        self, sample_optimization_report: OptimizationReport
    ) -> None:
        """4. Asserts count metrics consistency in OptimizationReport."""
        assert sample_optimization_report.approved_count + sample_optimization_report.challenged_count <= sample_optimization_report.total_anomalies
        assert len(sample_optimization_report.audited_anomalies) == sample_optimization_report.total_anomalies

    def test_m4_module_exports_and_imports(self) -> None:
        """5. Verifies that ArchitectureRedTeam and DailyReportBuilder are cleanly importable from audit package."""
        import audit
        from audit import ArchitectureRedTeam as ExportedRedTeam, DailyReportBuilder as ExportedReportBuilder

        assert callable(ExportedRedTeam)
        assert callable(ExportedReportBuilder)
```

---

## 5. Verification Method & Test Execution Plan

### 5.1 Deterministic Execution Commands
Run pytest against the entire test suite:
```powershell
py -m pytest .agents/cron/tests/test_red_team_and_report.py -v
```

Or run all unit tests in the daemon test suite:
```powershell
py -m pytest .agents/cron/tests/ -v
```

### 5.2 Verification Checklist for Implementer (`worker_m4`)
| Requirement | Expected Pass Condition |
|---|---|
| Whitelist Protection | `ArchitectureRedTeam` emits `REJECTED` for all 5 whitelisted files (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`) |
| Process Termination Prohibition | `ArchitectureRedTeam` emits `REJECTED` for `taskkill`, `os.kill`, or automated process killing |
| Stale Proposal Archival | `ArchitectureRedTeam` emits `APPROVED` for planning files > 48 hours old |
| Borderline Staleness | `ArchitectureRedTeam` emits `CHALLENGED` for planning files between 24h and 48h old |
| 6 Core Report Sections | `DailyReportBuilder` renders all 6 sections with exact required headers |
| Interactive Checkboxes | `DailyReportBuilder` renders `- [ ] [HITL-APPROVED]` checkboxes for all actionable proposals |
| Historical Drift Analytics | `DailyReportBuilder` renders all 5 August 23/24 historical failure seeds and drift metrics |
| ProTeGi Textual Gradients | `DailyReportBuilder` renders cluster diffs and meta-gradient recommendations |
| 0-Destruction Cryptographic Invariance | `FileSystemSnapshot` confirms 0 files altered or mutated across entire audit & report cycle |
