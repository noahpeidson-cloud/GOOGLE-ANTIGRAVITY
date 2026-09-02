"""Scratch prototype testing ArchitectureRedTeam adversarial audit logic."""

import fnmatch
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure cron is on path
CRON_DIR = Path(__file__).resolve().parent.parent / "cron"
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

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

# Extended whitelisted manifests
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

# Template & sample config patterns
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

# Test & fixture path substrings
FIXTURE_PATH_SUBSTRINGS: List[str] = [
    "fixtures/",
    "tests/",
    "mock_workspace/",
    "test_fixtures/",
]


class ArchitectureRedTeam:
    """Adversarial Architecture Red-Team auditor for Antigravity health scans.

    Scrutinizes every detected anomaly and proposed optimization through three adversarial perspectives:
    1. System Integrity (daemon stability, port collisions, cross-track isolation)
    2. Data Loss Risk (accidental-data-loss-prevention, L2 context paging vs deletion)
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
                )
            elif dl_verdict == RedTeamVerdict.APPROVED:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.APPROVED,
                    rationale=dl_rationale,
                    risk_assessment=dl_risk,
                    recommended_action=dl_action,
                )

            # Check if System Integrity had an APPROVED recommendation (e.g. duplicate sections)
            if sys_verdict == RedTeamVerdict.APPROVED:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.APPROVED,
                    rationale=sys_rationale,
                    risk_assessment=sys_risk,
                    recommended_action=sys_action,
                )

            # Default Fallback for unclassified anomalies
            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.CHALLENGED,
                rationale=f"Anomaly in '{record.target_path}' requires manual HITL review.",
                risk_assessment="Uncertain risk profile; requires human assessment.",
                recommended_action=f"Review anomaly details for '{record.target_path}' before taking any action.",
            )

        except Exception as e:
            # Error isolation
            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.CHALLENGED,
                rationale=f"Red Team evaluation encountered an isolated exception: {e}",
                risk_assessment="Audit evaluation error; defaulting to CHALLENGED to prevent unintended actions.",
                recommended_action=f"Manually inspect '{record.target_path}'.",
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


if __name__ == "__main__":
    red_team = ArchitectureRedTeam()

    # Test Case 1: Whitelisted manifest (PROJECT.md) flagged as Context Rot -> REJECTED
    rec1 = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path="PROJECT.md",
        severity=Severity.MEDIUM,
        description="Planning artifact > 24h old",
        raw_details={"age_hours": 30.0},
    )
    res1 = red_team.audit_anomaly(rec1)
    print("Test 1 (PROJECT.md Context Rot):", res1.verdict, "->", res1.rationale[:60])
    assert res1.verdict == RedTeamVerdict.REJECTED

    # Test Case 2: Template file (.env.example) flagged as Secret Zero -> REJECTED
    rec2 = AnomalyRecord(
        detector_type=DetectorType.SECRET_ZERO,
        target_path=".env.example",
        severity=Severity.CRITICAL,
        description="Placeholder token 'your_token_here' found",
        raw_details={"token": "your_token_here"},
    )
    res2 = red_team.audit_anomaly(rec2)
    print("Test 2 (.env.example Secret Zero):", res2.verdict, "->", res2.rationale[:60])
    assert res2.verdict == RedTeamVerdict.REJECTED

    # Test Case 3: Ghost daemon on port 3000 -> CHALLENGED (no auto-kill)
    rec3 = AnomalyRecord(
        detector_type=DetectorType.GHOST_DAEMONS,
        target_path="127.0.0.1:3000",
        severity=Severity.CRITICAL,
        description="Port 3000 occupied",
        raw_details={"port": 3000},
    )
    res3 = red_team.audit_anomaly(rec3)
    print("Test 3 (Ghost Daemon 3000):", res3.verdict, "->", res3.rationale[:60])
    assert res3.verdict == RedTeamVerdict.CHALLENGED
    assert "taskkill" in res3.recommended_action.lower() or "sigterm" in res3.recommended_action.lower()

    # Test Case 4: Borderline staleness (25.0h) -> CHALLENGED
    rec4 = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path="notes_scratch.md",
        severity=Severity.MEDIUM,
        description="Planning artifact 25.0h old",
        raw_details={"age_hours": 25.0},
    )
    res4 = red_team.audit_anomaly(rec4)
    print("Test 4 (Borderline Staleness 25h):", res4.verdict, "->", res4.rationale[:60])
    assert res4.verdict == RedTeamVerdict.CHALLENGED

    # Test Case 5: Verified stale proposal (72.0h) -> APPROVED (L2 archive)
    rec5 = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path=".agents/old/proposal.md",
        severity=Severity.MEDIUM,
        description="Planning artifact 72.0h old",
        raw_details={"age_hours": 72.0},
    )
    res5 = red_team.audit_anomaly(rec5)
    print("Test 5 (Stale Proposal 72h):", res5.verdict, "->", res5.rationale[:60])
    assert res5.verdict == RedTeamVerdict.APPROVED
    assert ".archive" in res5.recommended_action

    # Test Case 6: Real .env placeholder token -> APPROVED (manual update)
    rec6 = AnomalyRecord(
        detector_type=DetectorType.SECRET_ZERO,
        target_path=".env",
        severity=Severity.CRITICAL,
        description="Placeholder token found",
        raw_details={"token": "sk-***"},
    )
    res6 = red_team.audit_anomaly(rec6)
    print("Test 6 (Real .env Secret Zero):", res6.verdict, "->", res6.rationale[:60])
    assert res6.verdict == RedTeamVerdict.APPROVED

    # Test Case 7: GEMINI.md rule bloat (180 lines) -> CHALLENGED (distill skills)
    rec7 = AnomalyRecord(
        detector_type=DetectorType.PROMPT_FATIGUE,
        target_path="GEMINI.md",
        severity=Severity.MEDIUM,
        description="Manifest rule bloat: 180 lines",
        raw_details={"line_count": 180},
    )
    res7 = red_team.audit_anomaly(rec7)
    print("Test 7 (GEMINI.md Bloat):", res7.verdict, "->", res7.rationale[:60])
    assert res7.verdict == RedTeamVerdict.CHALLENGED
    assert "skill" in res7.recommended_action.lower()

    # Test Case 8: Batch audit on empty list and multi-item list
    batch_res = red_team.audit_batch([rec1, rec2, rec3, rec4, rec5, rec6, rec7])
    assert len(batch_res) == 7
    print("Batch audit length:", len(batch_res))
    empty_batch = red_team.audit_batch([])
    assert empty_batch == []

    print("\nALL 8 SCRATCH TEST CASES PASSED SUCCESSFULLY!")
