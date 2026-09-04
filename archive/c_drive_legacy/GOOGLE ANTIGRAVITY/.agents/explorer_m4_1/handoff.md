# Milestone 4 Handoff Report: Architecture Red-Team Auditor Design

## 1. Observation

### 1.1 Direct Codebase & Data Model Observations
- **Data Model Contract (`models.py:23-100`)**:
  `RedTeamVerdict` enum is defined with 3 variants: `APPROVED = "APPROVED"`, `CHALLENGED = "CHALLENGED"`, `REJECTED = "REJECTED"`.
  `RedTeamAuditResult` dataclass has fields `anomaly: AnomalyRecord`, `verdict: RedTeamVerdict`, `rationale: str`, `risk_assessment: str`, `recommended_action: str`, plus serialization methods `to_dict()` and `from_dict()`.
- **Whitelists & Configuration (`config.py:15-36`)**:
  `WHITELISTED_FILENAMES` includes `["PROJECT.md", "GEMINI.md", "README.md", "BRIEFING.md", "ORIGINAL_REQUEST.md"]`. `MONITORED_PORTS = [3000, 8000, 8501]`. `CONTEXT_ROT_THRESHOLD_HOURS = 24.0`. `PROMPT_FATIGUE_MAX_LINES = 100`.
- **Static AST Safety Guardrails (`safety_guardrails.py:1-312`)**:
  Enforces zero destructive operations across `.agents/cron`. Specifically bars `os.remove`, `os.unlink`, `shutil.rmtree`, `os.kill`, `subprocess` calls with `taskkill`/`pkill`/`kill`/`rm -rf`, `DROP`/`TRUNCATE` SQL, and `eval`/`exec`.
- **Detectors & ML Outputs (`detectors/`, `ml/`)**:
  Detectors generate `AnomalyRecord` instances. All 73 existing unit tests across M1, M2, and M3 pass cleanly in 2.46s (`python -m pytest -v`).
- **Scratch Prototype Execution (`.agents/explorer_m4_1/scratch_red_team.py`)**:
  Evaluated all 8 test cases against `ArchitectureRedTeam` prototype. Execution output:
  `ALL 8 SCRATCH TEST CASES PASSED SUCCESSFULLY!`
  AST Safety Verification output: `Violations: []` (0 static AST violations).

---

## 2. Logic Chain

1. **Adversarial Triad Decomposition**:
   - Upstream anomaly detectors are rule-based heuristics that may produce false alarms or propose naive actions (e.g., flagging whitelisted manifests as stale context, proposing process kills for active dev servers, or attempting to wipe `.env` files).
   - In accordance with Skill `architecture-red-team` and `accidental-data-loss-prevention`, the daemon must subject every detected anomaly to three distinct adversarial lenses before HITL presentation:
     1. **Perspective 1: False Positive Filter**: Checks if target matches whitelisted manifests (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`, `DISPATCH.md`), documentation templates (`.env.example`, `.env.template`), or test fixture directories (`fixtures/`, `tests/`, `mock_workspace/`). If true -> emits `RedTeamVerdict.REJECTED`.
     2. **Perspective 2: Data Loss Risk**: Checks if acting on the anomaly risks accidental deletion of unstaged work, notes, or configuration. In adherence to `accidental-data-loss-prevention`, autonomous deletion is strictly prohibited. For `CONTEXT_ROT`, borderline age (24.0h - 36.0h) triggers `RedTeamVerdict.CHALLENGED`, while verified stale files (>36h) trigger `RedTeamVerdict.APPROVED` with non-destructive L2 context paging recommendation (`.archive/`). For `SECRET_ZERO`, active `.env` files trigger `APPROVED` with manual interactive token replacement instructions (zero file deletion).
     3. **Perspective 3: System Integrity**: Checks if proposed optimization risks system stability, background daemon crashes, or manifest degradation. For `GHOST_DAEMONS`, occupied ports (3000, 8000, 8501) trigger `RedTeamVerdict.CHALLENGED` because automated `taskkill` could crash active user frontend/backend servers or corrupt SQLite state. For `PROMPT_FATIGUE`, `GEMINI.md` > 100 lines triggers `CHALLENGED` with counter-proposal to distill procedural rules into skills (`.agents/skills/<name>/SKILL.md`), protecting core `<system>` directives from truncation. Duplicate rule sections trigger `APPROVED` for clean deduplication.

2. **Arbitration & Verdict Synthesis**:
   - The evaluation pipeline executes:
     `Perspective 1 (False Positive)` -> if REJECTED, return immediately.
     `Perspective 3 (System Integrity)` -> if CHALLENGED, return with system risk explanation and counter-proposal.
     `Perspective 2 (Data Loss Risk)` -> if CHALLENGED, return with data loss warning and L2 archive counter-proposal; if APPROVED, return with safe non-destructive action.
     If System Integrity produced APPROVED (e.g. duplicate section deduplication), return APPROVED.
     Fallback for unclassified anomalies: defaults safely to `CHALLENGED`.
   - Error isolation ensures that an unexpected exception during single-anomaly evaluation returns a safe fallback `CHALLENGED` result, preventing daemon crashes.

3. **Data Model Compatibility**:
   - Enhancing `models.py:RedTeamAuditResult` with `@property def reason` (aliasing `rationale`), `@property def counter_proposal` (aliasing `recommended_action`), and optional `confidence: float = 1.0` satisfies all prompt interface requirements while retaining 100% backward compatibility with existing tests and `OptimizationReport`.

---

## 3. Caveats

- **Operating System PID Probing**: While `ArchitectureRedTeam` challenges ghost daemon alerts and recommends manual inspection, it strictly avoids issuing terminal commands or subprocess task calls, complying with AST safety guardrails.
- **Cross-Track Domain Leaks**: Cross-track keyword detection in code files (e.g., `ffmpeg` in `sports_cards`) is conservatively challenged because some multi-modal workflows may intentionally bridge domains. The Red Team delegates final classification to human review.
- **Whitelist Scope**: The protected manifest list includes standard Antigravity project files. If new permanent workspace manifests are added, they should be appended to `PROTECTED_MANIFESTS`.

---

## 4. Conclusion & Implementation Blueprint

### 4.1 File Inventory for Milestone 4 (Red Team)
Target Directory: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron`

| Target File | Action | Description |
|---|---|---|
| `cron/audit/__init__.py` | CREATE | Package initialization exporting `ArchitectureRedTeam`. |
| `cron/audit/red_team.py` | CREATE | Complete `ArchitectureRedTeam` implementation with 3 adversarial perspectives and arbitration. |
| `cron/models.py` | ENHANCE | Backward-compatible enhancements to `RedTeamAuditResult` (`confidence`, `counter_proposal`, `reason` property). |
| `cron/tests/test_red_team_audit.py` | CREATE | Comprehensive unit test suite covering all 8 adversarial scenarios, batch operations, and AST safety. |

---

### 4.2 Drop-In Blueprint: `cron/audit/__init__.py`

```python
"""Antigravity Audit and Red-Team Package."""

try:
    from .red_team import ArchitectureRedTeam
except ImportError:
    from audit.red_team import ArchitectureRedTeam

__all__ = ["ArchitectureRedTeam"]
```

---

### 4.3 Drop-In Blueprint: `cron/audit/red_team.py`

```python
"""Architecture Red-Team Auditor: Adversarial scrutiny of health anomalies and optimizations."""

import fnmatch
import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    from ..config import (
        CONTEXT_ROT_THRESHOLD_HOURS,
        MONITORED_PORTS,
        PROMPT_FATIGUE_MAX_LINES,
        WHITELISTED_FILENAMES,
    )
    from ..models import (
        AnomalyRecord,
        DetectorType,
        RedTeamAuditResult,
        RedTeamVerdict,
        Severity,
    )
except (ImportError, ValueError):
    from config import (
        CONTEXT_ROT_THRESHOLD_HOURS,
        MONITORED_PORTS,
        PROMPT_FATIGUE_MAX_LINES,
        WHITELISTED_FILENAMES,
    )
    from models import (
        AnomalyRecord,
        DetectorType,
        RedTeamAuditResult,
        RedTeamVerdict,
        Severity,
    )

logger = logging.getLogger(__name__)

# Extended whitelisted permanent project manifests
PROTECTED_MANIFESTS: Set[str] = {
    "PROJECT.MD",
    "GEMINI.MD",
    "README.MD",
    "BRIEFING.MD",
    "ORIGINAL_REQUEST.MD",
    "BRIEFING_ARCHIVE.MD",
    "DISPATCH.MD",
    "GATE_STATUS.MD",
    "TASK.MD",
    "TEST_READY.MD",
}

# Template and documentation config patterns
TEMPLATE_CONFIG_PATTERNS: List[str] = [
    "*.example",
    "*.example.*",
    "*.template",
    "*.template.*",
    "*.sample",
    "*.sample.*",
    ".env.example",
    ".env.template",
    ".env.sample",
    "sample.env",
    "example.env",
    "*.mock.*",
]

# Test and fixture path substrings to exclude from production alerts
FIXTURE_PATH_SUBSTRINGS: List[str] = [
    "fixtures/",
    "tests/",
    "mock_workspace/",
    "test_fixtures/",
]


class ArchitectureRedTeam:
    """Adversarial Architecture Red-Team auditor for Antigravity health scans.

    Scrutinizes every detected anomaly and proposed optimization through three adversarial perspectives:
    1. System Integrity (daemon stability, port collisions, cross-track isolation, manifest rule integrity)
    2. Data Loss Risk (accidental-data-loss-prevention, L2 context paging vs deletion, uncommitted state)
    3. False Positive Filter (project manifests, example templates, test fixtures)

    Emits structured RedTeamAuditResult instances with 3-tiered verdicts: APPROVED, CHALLENGED, REJECTED.
    """

    def __init__(
        self,
        whitelisted_manifests: Optional[Set[str]] = None,
        template_patterns: Optional[List[str]] = None,
        borderline_staleness_hours: float = 36.0,
        monitored_ports: Optional[List[int]] = None,
    ) -> None:
        self.whitelisted_manifests = set(whitelisted_manifests or PROTECTED_MANIFESTS)
        self.template_patterns = list(template_patterns or TEMPLATE_CONFIG_PATTERNS)
        self.borderline_staleness_hours = borderline_staleness_hours
        self.monitored_ports = list(monitored_ports or MONITORED_PORTS)

    def _is_protected_manifest(self, target_path: str) -> bool:
        """Checks if target path is a whitelisted permanent project manifest."""
        normalized = target_path.replace("\\", "/")
        filename = os.path.basename(normalized).upper()
        if filename in self.whitelisted_manifests:
            return True
        return any(filename == m.upper() for m in self.whitelisted_manifests)

    def _is_template_or_fixture(self, target_path: str) -> bool:
        """Checks if target path is an example/template file or inside a test fixture."""
        normalized = target_path.replace("\\", "/").lower()
        filename = os.path.basename(normalized)

        # Check fixture substrings
        if any(fix in normalized for fix in FIXTURE_PATH_SUBSTRINGS):
            return True

        # Check template glob patterns
        return any(fnmatch.fnmatch(filename, pat.lower()) for pat in self.template_patterns)

    def _evaluate_false_positive(
        self, anomaly: AnomalyRecord, workspace_root: Optional[str] = None
    ) -> Tuple[bool, Optional[RedTeamVerdict], str, float]:
        """Perspective 1: False Positive Filter.

        Returns: (is_false_positive, verdict_override, rationale, confidence)
        """
        det_type = anomaly.detector_type
        target = anomaly.target_path

        # 1. Protected Manifests Check
        if self._is_protected_manifest(target):
            if det_type in (DetectorType.CONTEXT_ROT, DetectorType.ECOSYSTEM_POLLUTION):
                return (
                    True,
                    RedTeamVerdict.REJECTED,
                    f"Target '{target}' is a protected permanent workspace manifest ({os.path.basename(target)}). "
                    "Manifests are exempt from context rot and ecosystem pollution flagging.",
                    1.0,
                )

        # 2. Template / Sample / Fixture Check for Secret Zero
        if det_type == DetectorType.SECRET_ZERO:
            if self._is_template_or_fixture(target):
                return (
                    True,
                    RedTeamVerdict.REJECTED,
                    f"Target '{target}' is a documentation template or test fixture. "
                    "Placeholder tokens in template/example files are intentional and do not constitute a credential leak.",
                    0.95,
                )

        # 3. Test Fixtures in general
        if any(fix in target.replace("\\", "/").lower() for fix in FIXTURE_PATH_SUBSTRINGS):
            if not anomaly.is_historical:
                return (
                    True,
                    RedTeamVerdict.REJECTED,
                    f"Target '{target}' is located within test fixtures/suites. "
                    "Test assets are intentionally mocked and excluded from production health alerts.",
                    0.95,
                )

        return (False, None, "", 0.0)

    def _evaluate_data_loss_risk(
        self, anomaly: AnomalyRecord, workspace_root: Optional[str] = None
    ) -> Tuple[bool, Optional[RedTeamVerdict], str, str, str, float]:
        """Perspective 2: Data Loss Risk (accidental-data-loss-prevention).

        Returns: (has_data_loss_risk, verdict_override, rationale, risk_assessment, recommended_action, confidence)
        """
        det_type = anomaly.detector_type
        target = anomaly.target_path
        details = anomaly.raw_details or {}

        # 1. Context Rot Data Loss Scrutiny
        if det_type == DetectorType.CONTEXT_ROT:
            age_hours = float(details.get("age_hours", 0.0))
            if age_hours == 0.0 and anomaly.timestamp > 0:
                # Estimate age from timestamp if not present in details
                age_hours = max(0.0, (1756000000 - anomaly.timestamp) / 3600.0)

            # Borderline Staleness (e.g. 24.0h - 36.0h)
            if CONTEXT_ROT_THRESHOLD_HOURS < age_hours <= self.borderline_staleness_hours:
                return (
                    True,
                    RedTeamVerdict.CHALLENGED,
                    f"Planning artifact '{target}' is {age_hours:.1f}h old (borderline staleness, threshold {CONTEXT_ROT_THRESHOLD_HOURS:.1f}h). "
                    "The document may still contain active in-flight reasoning or uncommitted architecture notes.",
                    "Medium data loss risk: premature relocation may disrupt active subagent context.",
                    f"Prompt developer for explicit HITL approval before archiving '{target}' to .archive/ directory. Do not delete.",
                    0.80,
                )
            else:
                # Verified Stale (> 36h): Approve L2 archiving (Zero automated deletion)
                return (
                    False,
                    RedTeamVerdict.APPROVED,
                    f"Planning artifact '{target}' is {age_hours:.1f}h old and diluting context window. "
                    "Automated deletion is strictly forbidden under accidental-data-loss-prevention.",
                    "Low data loss risk when utilizing non-destructive L2 context paging (.archive/) with HITL approval.",
                    f"Propose moving '{target}' to '.archive/{os.path.basename(target)}' (L2 context paging) upon HITL confirmation. Zero automated deletion.",
                    0.95,
                )

        # 2. Ecosystem Pollution Data Loss Scrutiny
        if det_type == DetectorType.ECOSYSTEM_POLLUTION:
            p_type = details.get("pollution_type", "")
            if p_type == "DISABLED_PLUGIN" or ".disabled" in target:
                return (
                    False,
                    RedTeamVerdict.APPROVED,
                    f"Unused disabled plugin '{target}' identified. Autonomous deletion is prohibited.",
                    "Low data loss risk under non-destructive quarantine.",
                    f"Propose moving '{target}' to '.archive/disabled_plugins/' upon HITL approval. Zero automated deletion.",
                    0.95,
                )
            elif p_type == "CROSS_TRACK_LEAK" or "cross-track" in anomaly.description.lower():
                return (
                    True,
                    RedTeamVerdict.CHALLENGED,
                    f"Cross-track keyword/file match in '{target}'. File may represent an intentional multi-domain integration (e.g. video processing in sports cards).",
                    "Medium risk of breaking multi-track domain logic or losing application code if moved blindly.",
                    f"Prompt developer to review and confirm domain categorization for '{target}' before any file relocation.",
                    0.85,
                )

        # 3. Secret Zero Data Loss Scrutiny
        if det_type == DetectorType.SECRET_ZERO:
            return (
                False,
                RedTeamVerdict.APPROVED,
                f"Unresolved placeholder token detected in active configuration file '{target}'. "
                "Deleting or wiping configuration is strictly prohibited.",
                "High operational/authentication risk if left unaddressed; zero data loss risk via interactive prompt.",
                f"Prompt developer to manually replace placeholder token in '{target}' with active credentials (HITL manual update).",
                1.0,
            )

        return (False, None, "", "", "", 0.0)

    def _evaluate_system_integrity(
        self, anomaly: AnomalyRecord, workspace_root: Optional[str] = None
    ) -> Tuple[bool, Optional[RedTeamVerdict], str, str, str, float]:
        """Perspective 3: System Integrity (stability, daemon safety, manifest integrity).

        Returns: (has_integrity_issue, verdict_override, rationale, risk_assessment, recommended_action, confidence)
        """
        det_type = anomaly.detector_type
        target = anomaly.target_path
        details = anomaly.raw_details or {}

        # 1. Ghost Daemons / Port Collisions
        if det_type == DetectorType.GHOST_DAEMONS:
            port = details.get("port", 0)
            return (
                True,
                RedTeamVerdict.CHALLENGED,
                f"Port {port} is occupied on loopback interface. "
                "Automated process termination (`taskkill`, `kill`) is strictly prohibited by AST guardrails and risks killing active user development servers (Next.js/FastAPI).",
                "High system integrity risk: blind process termination may crash active user session or corrupt SQLite state.",
                f"Inspect PID and verify process command line. If confirmed orphaned, prompt developer for manual graceful termination (SIGTERM). Zero automated taskkill.",
                0.90,
            )

        # 2. Prompt Fatigue Manifest Integrity
        if det_type == DetectorType.PROMPT_FATIGUE:
            line_count = details.get("line_count", 0)
            duplicates = details.get("duplicate_sections", [])
            if duplicates:
                return (
                    False,
                    RedTeamVerdict.APPROVED,
                    f"Duplicate rule sections ({', '.join(duplicates)}) in '{target}' create redundant token consumption.",
                    "Low system integrity risk; deduplication improves context efficiency without altering directives.",
                    f"Prompt developer to deduplicate redundant rule sections in '{target}'.",
                    0.95,
                )
            elif line_count > PROMPT_FATIGUE_MAX_LINES:
                return (
                    True,
                    RedTeamVerdict.CHALLENGED,
                    f"System manifest '{target}' has {line_count} lines (exceeds {PROMPT_FATIGUE_MAX_LINES} line threshold). "
                    "Direct truncation would destroy core operating directives (<system>, <workspace_manifest>, R1-R3).",
                    "High system integrity risk: truncating manifest causes prompt fatigue degradation and lost directives.",
                    f"Distill procedural guidelines into reusable modular skills (.agents/skills/<name>/SKILL.md) using workflow-skill-creator; preserve immutable manifest directives.",
                    0.90,
                )

        return (False, None, "", "", "", 0.0)

    def audit_anomaly(
        self,
        anomaly: Union[AnomalyRecord, Dict[str, Any]],
        workspace_root: Optional[str] = None,
    ) -> RedTeamAuditResult:
        """Audits a single anomaly through all 3 adversarial perspectives.

        Arbitrates findings to produce a definitive RedTeamAuditResult.
        """
        # Ensure AnomalyRecord instance
        if isinstance(anomaly, dict):
            record = AnomalyRecord.from_dict(anomaly)
        elif isinstance(anomaly, AnomalyRecord):
            record = anomaly
        else:
            raise TypeError(f"Expected AnomalyRecord or dict, got {type(anomaly)}")

        try:
            # 1. Perspective 1: False Positive Filter
            is_fp, fp_verdict, fp_rationale, fp_conf = self._evaluate_false_positive(record, workspace_root)
            if is_fp and fp_verdict == RedTeamVerdict.REJECTED:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.REJECTED,
                    rationale=fp_rationale,
                    risk_assessment="Zero risk: target item is a legitimate project manifest, template, or test fixture.",
                    recommended_action="Dismiss finding. Retain asset in place. No action required.",
                    confidence=fp_conf,
                    counter_proposal="Retain asset in place.",
                )

            # 2. Perspective 3: System Integrity Scrutiny
            has_sys_risk, sys_verdict, sys_rationale, sys_risk, sys_action, sys_conf = self._evaluate_system_integrity(record, workspace_root)
            if sys_verdict == RedTeamVerdict.CHALLENGED:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.CHALLENGED,
                    rationale=sys_rationale,
                    risk_assessment=sys_risk,
                    recommended_action=sys_action,
                    confidence=sys_conf,
                    counter_proposal=sys_action,
                )

            # 3. Perspective 2: Data Loss Risk Scrutiny
            has_dl_risk, dl_verdict, dl_rationale, dl_risk, dl_action, dl_conf = self._evaluate_data_loss_risk(record, workspace_root)
            if dl_verdict == RedTeamVerdict.CHALLENGED:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.CHALLENGED,
                    rationale=dl_rationale,
                    risk_assessment=dl_risk,
                    recommended_action=dl_action,
                    confidence=dl_conf,
                    counter_proposal=dl_action,
                )
            elif dl_verdict == RedTeamVerdict.APPROVED:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.APPROVED,
                    rationale=dl_rationale,
                    risk_assessment=dl_risk,
                    recommended_action=dl_action,
                    confidence=dl_conf,
                    counter_proposal=dl_action,
                )

            # Check if System Integrity had an APPROVED recommendation (e.g. duplicate sections)
            if sys_verdict == RedTeamVerdict.APPROVED:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.APPROVED,
                    rationale=sys_rationale,
                    risk_assessment=sys_risk,
                    recommended_action=sys_action,
                    confidence=sys_conf,
                    counter_proposal=sys_action,
                )

            # Default Fallback for unclassified anomalies
            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.CHALLENGED,
                rationale=f"Anomaly in '{record.target_path}' requires manual HITL review.",
                risk_assessment="Uncertain risk profile; requires human assessment.",
                recommended_action=f"Review anomaly details for '{record.target_path}' before taking any action.",
                confidence=0.70,
                counter_proposal=f"Review anomaly details for '{record.target_path}'.",
            )

        except Exception as e:
            logger.warning(
                "ArchitectureRedTeam encountered an isolated exception while auditing anomaly on '%s': %s",
                getattr(record, "target_path", "unknown"),
                e,
                exc_info=True,
            )
            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.CHALLENGED,
                rationale=f"Red Team evaluation encountered an isolated exception: {e}",
                risk_assessment="Audit evaluation error; defaulting to CHALLENGED to prevent unintended actions.",
                recommended_action=f"Manually inspect '{getattr(record, 'target_path', 'unknown')}'.",
                confidence=0.50,
                counter_proposal=f"Manually inspect '{getattr(record, 'target_path', 'unknown')}'.",
            )

    def audit_batch(
        self,
        anomalies: List[Union[AnomalyRecord, Dict[str, Any]]],
        workspace_root: Optional[str] = None,
    ) -> List[RedTeamAuditResult]:
        """Audits a batch of anomalies through the adversarial red team.

        Returns a list of RedTeamAuditResult instances corresponding to each input anomaly.
        """
        if not anomalies:
            return []
        return [self.audit_anomaly(a, workspace_root=workspace_root) for a in anomalies]
```

---

### 4.4 Drop-In Blueprint: `cron/models.py` Enhancement

```python
# In cron/models.py, enhance RedTeamAuditResult:
@dataclass
class RedTeamAuditResult:
    anomaly: AnomalyRecord
    verdict: RedTeamVerdict
    rationale: str
    risk_assessment: str
    recommended_action: str
    confidence: float = 1.0
    counter_proposal: Optional[str] = None

    @property
    def reason(self) -> str:
        return self.rationale

    @reason.setter
    def reason(self, value: str) -> None:
        self.rationale = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly": self.anomaly.to_dict() if isinstance(self.anomaly, AnomalyRecord) else self.anomaly,
            "verdict": self.verdict.value if isinstance(self.verdict, RedTeamVerdict) else str(self.verdict),
            "rationale": self.rationale,
            "risk_assessment": self.risk_assessment,
            "recommended_action": self.recommended_action,
            "confidence": self.confidence,
            "counter_proposal": self.counter_proposal or self.recommended_action,
            "reason": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedTeamAuditResult":
        raw_verdict = data.get("verdict")
        verdict = RedTeamVerdict(raw_verdict) if isinstance(raw_verdict, str) else raw_verdict
        anomaly_data = data.get("anomaly", {})
        anomaly = AnomalyRecord.from_dict(anomaly_data) if isinstance(anomaly_data, dict) else anomaly_data
        rationale = data.get("rationale") or data.get("reason", "")
        rec_action = data.get("recommended_action") or data.get("counter_proposal", "")
        return cls(
            anomaly=anomaly,
            verdict=verdict,
            rationale=rationale,
            risk_assessment=data.get("risk_assessment", ""),
            recommended_action=rec_action,
            confidence=float(data.get("confidence", 1.0)),
            counter_proposal=data.get("counter_proposal"),
        )
```

---

### 4.5 Drop-In Blueprint: `cron/tests/test_red_team_audit.py`

```python
"""Unit tests for Milestone 4 Architecture Red-Team Auditor."""

import pytest

from models import AnomalyRecord, DetectorType, RedTeamAuditResult, RedTeamVerdict, Severity
from audit.red_team import ArchitectureRedTeam
from audit import ArchitectureRedTeam as ExportedRedTeam
import safety_guardrails


def test_red_team_package_exports() -> None:
    """Verifies that ArchitectureRedTeam is exported from audit package."""
    assert ExportedRedTeam is ArchitectureRedTeam


def test_whitelisted_manifest_context_rot_rejected() -> None:
    """Verifies Perspective 1: Whitelisted manifest files flagged as context rot are REJECTED."""
    red_team = ArchitectureRedTeam()
    for manifest_name in ["PROJECT.md", "GEMINI.md", "README.md", "BRIEFING.md", "ORIGINAL_REQUEST.md"]:
        rec = AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path=manifest_name,
            severity=Severity.MEDIUM,
            description=f"Planning artifact {manifest_name} > 24h old",
            raw_details={"age_hours": 30.0},
        )
        res = red_team.audit_anomaly(rec)
        assert res.verdict == RedTeamVerdict.REJECTED
        assert "protected permanent workspace manifest" in res.rationale
        assert res.confidence >= 0.95


def test_template_and_fixture_secret_zero_rejected() -> None:
    """Verifies Perspective 1: Placeholder tokens in template files or test fixtures are REJECTED."""
    red_team = ArchitectureRedTeam()
    for tpl_path in [".env.example", ".env.template", "config.sample.json", "fixtures/mock_workspace/.env"]:
        rec = AnomalyRecord(
            detector_type=DetectorType.SECRET_ZERO,
            target_path=tpl_path,
            severity=Severity.CRITICAL,
            description="Placeholder token found",
            raw_details={"token": "your_token_here"},
        )
        res = red_team.audit_anomaly(rec)
        assert res.verdict == RedTeamVerdict.REJECTED
        assert "template" in res.rationale.lower() or "fixture" in res.rationale.lower()


def test_ghost_daemon_port_collision_challenged() -> None:
    """Verifies Perspective 3: Ghost daemon alerts on active dev ports are CHALLENGED to prevent auto-kill."""
    red_team = ArchitectureRedTeam()
    rec = AnomalyRecord(
        detector_type=DetectorType.GHOST_DAEMONS,
        target_path="127.0.0.1:3000",
        severity=Severity.CRITICAL,
        description="Port 3000 occupied (WinError 10048)",
        raw_details={"port": 3000, "host": "127.0.0.1"},
    )
    res = red_team.audit_anomaly(rec)
    assert res.verdict == RedTeamVerdict.CHALLENGED
    assert "taskkill" in res.recommended_action.lower() or "sigterm" in res.recommended_action.lower()
    assert "system integrity" in res.risk_assessment.lower()


def test_borderline_context_rot_challenged() -> None:
    """Verifies Perspective 2: Planning files with borderline age (24-36h) are CHALLENGED."""
    red_team = ArchitectureRedTeam()
    rec = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path="scratchpad.md",
        severity=Severity.MEDIUM,
        description="Planning file is 25.0h old",
        raw_details={"age_hours": 25.0},
    )
    res = red_team.audit_anomaly(rec)
    assert res.verdict == RedTeamVerdict.CHALLENGED
    assert "borderline" in res.rationale.lower()


def test_verified_stale_planning_file_approved_with_l2_archive() -> None:
    """Verifies Perspective 2: Stale planning files (>36h) are APPROVED with non-destructive L2 archive."""
    red_team = ArchitectureRedTeam()
    rec = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path=".agents/worker_1/proposal.md",
        severity=Severity.MEDIUM,
        description="Planning file is 72.0h old",
        raw_details={"age_hours": 72.0},
    )
    res = red_team.audit_anomaly(rec)
    assert res.verdict == RedTeamVerdict.APPROVED
    assert ".archive" in res.recommended_action
    assert "zero automated deletion" in res.recommended_action.lower()


def test_real_env_secret_zero_approved_with_manual_update() -> None:
    """Verifies Perspective 2: Active .env with placeholder token is APPROVED with manual update prompt."""
    red_team = ArchitectureRedTeam()
    rec = AnomalyRecord(
        detector_type=DetectorType.SECRET_ZERO,
        target_path=".env",
        severity=Severity.CRITICAL,
        description="Placeholder token 'sk-***' found",
        raw_details={"masked_token": "sk-***"},
    )
    res = red_team.audit_anomaly(rec)
    assert res.verdict == RedTeamVerdict.APPROVED
    assert "replace" in res.recommended_action.lower()


def test_manifest_prompt_fatigue_challenged_with_skill_distillation() -> None:
    """Verifies Perspective 3: GEMINI.md line bloat is CHALLENGED with skill distillation counter-proposal."""
    red_team = ArchitectureRedTeam()
    rec = AnomalyRecord(
        detector_type=DetectorType.PROMPT_FATIGUE,
        target_path="GEMINI.md",
        severity=Severity.MEDIUM,
        description="Manifest rule bloat: 180 lines",
        raw_details={"line_count": 180, "max_lines": 100},
    )
    res = red_team.audit_anomaly(rec)
    assert res.verdict == RedTeamVerdict.CHALLENGED
    assert "skill" in res.recommended_action.lower()


def test_manifest_duplicate_sections_approved() -> None:
    """Verifies Perspective 3: Duplicate manifest sections are APPROVED for deduplication."""
    red_team = ArchitectureRedTeam()
    rec = AnomalyRecord(
        detector_type=DetectorType.PROMPT_FATIGUE,
        target_path="GEMINI.md",
        severity=Severity.HIGH,
        description="Duplicate rule sections found",
        raw_details={"duplicate_sections": ["<RULE[R1]>"]},
    )
    res = red_team.audit_anomaly(rec)
    assert res.verdict == RedTeamVerdict.APPROVED
    assert "deduplicate" in res.recommended_action.lower()


def test_audit_batch_and_empty_handling() -> None:
    """Verifies batch auditing on empty and multi-element lists."""
    red_team = ArchitectureRedTeam()
    assert red_team.audit_batch([]) == []

    records = [
        AnomalyRecord(DetectorType.CONTEXT_ROT, "PROJECT.md", Severity.MEDIUM, "Stale", {"age_hours": 30.0}),
        AnomalyRecord(DetectorType.SECRET_ZERO, ".env", Severity.CRITICAL, "Token", {"token": "sk-***"}),
    ]
    results = red_team.audit_batch(records)
    assert len(results) == 2
    assert results[0].verdict == RedTeamVerdict.REJECTED
    assert results[1].verdict == RedTeamVerdict.APPROVED


def test_red_team_ast_safety_guarantee() -> None:
    """Verifies that audit/red_team.py contains zero destructive operations."""
    import audit.red_team as rt_module
    violations = safety_guardrails.scan_file_for_safety(rt_module.__file__)
    assert violations == [], f"AST safety violations detected: {violations}"
```

---

## 5. Verification Method

To independently verify this design and its implementation:

1. **Unit & Integration Test Execution**:
   Run the pytest test suite in the target directory:
   ```powershell
   python -m pytest tests/test_red_team_audit.py -v
   ```
   **Expected Result**: All test cases pass with 0 failures.

2. **Full Workspace Regression Test**:
   Execute the full test suite across all milestones:
   ```powershell
   python -m pytest -v
   ```
   **Expected Result**: All 73+ unit and integration tests pass cleanly in < 3.0s.

3. **Static AST Safety Guarantee**:
   Run the AST safety verifier on the codebase:
   ```powershell
   python -c "import safety_guardrails; safety_guardrails.assert_safe_codebase('.')"
   ```
   **Expected Result**: Exits with 0 violations and code 0.

4. **Invalidation Conditions**:
   The design is invalidated if:
   - Any destructive operation (`os.remove`, `os.unlink`, `shutil.rmtree`, `os.kill`, `taskkill`) is present.
   - `PROJECT.md` or `GEMINI.md` is approved for deletion or truncation.
   - `.env.example` is flagged as an active secret leak.
   - An anomaly evaluation raises an unhandled exception that halts the daemon.
