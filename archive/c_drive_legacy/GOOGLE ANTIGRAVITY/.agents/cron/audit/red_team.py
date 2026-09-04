"""Architecture Red Team Scrutiny Engine.

Adversarially evaluates all health scanner anomalies and proposed optimizations
across three distinct perspectives:
1. System Integrity: Rejects process disruption, unhandled socket binds, cross-track breaks.
2. Data Loss Risk: Enforces accidental-data-loss-prevention whitelist and safe scratchpad archival.
3. False Positive Filter: Scrutinizes ecosystem pollution overrides and prompt fatigue documentation depth.
"""

import os
import re
from typing import Any, Dict, List, Optional, Union

from models import (
    AnomalyRecord,
    DetectorType,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)

# Protected workspace manifests and specification files that must NEVER be deleted or truncated
WHITELISTED_FILENAMES = {
    "PROJECT.MD",
    "GEMINI.MD",
    "README.MD",
    "BRIEFING.MD",
    "ORIGINAL_REQUEST.MD",
    "SCOPE.MD",
    ".GITIGNORE",
    "PYPROJECT.TOML",
    "PACKAGE.JSON",
    "REQUIREMENTS.TXT",
}

# Dangerous automated process killing commands/tokens
KILL_PATTERNS = re.compile(
    r"\b(taskkill|pkill|kill|killpg|os\.kill|terminate|sigkill|sigterm|stop-process|delete\s+process)\b|wmic\s+process\s+delete",
    re.IGNORECASE,
)

# Dangerous filesystem and database deletion commands/tokens
DESTRUCTIVE_PATTERNS = re.compile(
    r"\b(remove|delete|unlink|rmdir|rmtree|rm\s+-rf|del\s+/[fFqQsS]|del\b|purge|wipe|truncate|drop(\s+table|\s+database|\s+schema)?|remove-item)\b",
    re.IGNORECASE,
)


def is_whitelisted_file(path: str) -> bool:
    """Checks if the target file path matches a protected workspace specification file."""
    if not path:
        return False
    norm = path.replace("\\", "/").strip().upper()
    basename = os.path.basename(norm)
    if basename in WHITELISTED_FILENAMES:
        return True
    for wf in WHITELISTED_FILENAMES:
        if norm.endswith("/" + wf) or norm == wf:
            return True
    return False


class ArchitectureRedTeam:
    """Adversarial scrutiny engine auditing anomalies and proposed optimizations."""

    def __init__(self, strict_mode: bool = True) -> None:
        self.strict_mode = strict_mode

    def audit_optimization(
        self,
        anomaly: Union[AnomalyRecord, Dict[str, Any]],
        proposed_action: str = "",
        textual_gradient: str = "",
    ) -> RedTeamAuditResult:
        """Scrutinizes an anomaly and proposed action across System Integrity, Data Loss Risk,

        and False Positive Filtering.
        """
        # Ensure anomaly is an AnomalyRecord instance
        if isinstance(anomaly, dict):
            record = AnomalyRecord.from_dict(anomaly)
        else:
            record = anomaly

        det_type = record.detector_type
        target = record.target_path
        details = record.raw_details or {}
        action_text = (proposed_action or "").strip()
        gradient_text = (textual_gradient or "").strip()
        combined_action = f"{action_text} {gradient_text}".strip()

        # ---------------------------------------------------------------------
        # 1. System Integrity Checks (Automated Process Killing)
        # ---------------------------------------------------------------------
        if KILL_PATTERNS.search(combined_action) or (
            det_type == DetectorType.GHOST_DAEMONS
            and any(k in action_text.lower() for k in ["kill", "taskkill", "terminate", "stop"])
        ):
            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.REJECTED,
                rationale="Automated process termination strictly prohibited. Background daemons may contain unsaved work, active debug sessions, or unmonitored server state.",
                risk_assessment="High risk of unexpected process disruption and session state corruption.",
                recommended_action=f"Run manual diagnostic command: 'netstat -ano | findstr :{details.get('port', 3000)}' to identify owning process before manual resolution.",
                confidence=1.0,
                reason="Automated process termination strictly prohibited. Background daemons may contain unsaved work, active debug sessions, or unmonitored server state.",
                counter_proposal=f"Run manual diagnostic command: 'netstat -ano | findstr :{details.get('port', 3000)}' to identify owning process before manual resolution.",
            )

        # ---------------------------------------------------------------------
        # 2. Data Loss Risk & Global Destructive Command Checks
        # ---------------------------------------------------------------------
        # Check for safe archival of stale non-whitelisted scratchpad (>48h)
        age_hours_val = float(
            details.get(
                "age_hours",
                details.get("age_seconds", 0.0) / 3600.0 if details.get("age_seconds") else 0.0,
            )
        )
        is_safe_stale_archival = (
            det_type == DetectorType.CONTEXT_ROT
            and not is_whitelisted_file(target)
            and age_hours_val >= 48.0
            and any(kw in combined_action.lower() for kw in ["archive", "move"])
            and not any(
                kw in combined_action.lower()
                for kw in ["rm -rf", "del ", "unlink", "drop", "truncate", "rmdir", "remove-item"]
            )
        )

        if is_whitelisted_file(target):
            if DESTRUCTIVE_PATTERNS.search(combined_action) or any(
                kw in action_text.lower() for kw in ["delete", "remove", "truncate", "wipe", "purge", "unlink", "strip", "prune rules"]
            ):
                if target.upper().endswith("GEMINI.MD") or det_type == DetectorType.PROMPT_FATIGUE:
                    return RedTeamAuditResult(
                        anomaly=record,
                        verdict=RedTeamVerdict.REJECTED,
                        rationale=f"Target '{target}' is protected by accidental-data-loss-prevention whitelist. Automated truncation or deletion of {target} is strictly prohibited. Permanent system instructions, persona directives, and architectural boundaries must be preserved.",
                        risk_assessment="Critical risk of catastrophic agent behavior drift and loss of developer persona/track definitions.",
                        recommended_action=f"Preserve '{target}'. Do not truncate or delete manifest rules automatically. Distill reusable procedural workflows into dedicated .agents/skills/ runbooks via workflow-skill-creator.",
                        confidence=1.0,
                        reason=f"Target '{target}' is protected by accidental-data-loss-prevention whitelist. Automated truncation or deletion of {target} is strictly prohibited. Permanent system instructions, persona directives, and architectural boundaries must be preserved.",
                        counter_proposal=f"Preserve '{target}'. Do not truncate or delete manifest rules automatically. Distill reusable procedural workflows into dedicated .agents/skills/ runbooks via workflow-skill-creator.",
                    )

                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.REJECTED,
                    rationale=f"Target '{target}' is protected by accidental-data-loss-prevention whitelist. Automated deletion, removal, or truncation is strictly forbidden.",
                    risk_assessment="Critical risk of permanent loss of project specifications, steering rules, or developer instructions.",
                    recommended_action=f"Preserve '{target}'. If refactoring is necessary, extract modular sections into dedicated skills without deleting core manifest.",
                    confidence=1.0,
                    reason=f"Target '{target}' is protected by accidental-data-loss-prevention whitelist. Automated deletion, removal, or truncation is strictly forbidden.",
                    counter_proposal=f"Preserve '{target}'. If refactoring is necessary, extract modular sections into dedicated skills without deleting core manifest.",
                )

        # Global destructive pattern rejection for any detector type (unless safe archival)
        if DESTRUCTIVE_PATTERNS.search(combined_action) and not is_safe_stale_archival:
            if det_type == DetectorType.SECRET_ZERO or ".env" in target.lower():
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.REJECTED,
                    rationale="Automated deletion of .env configuration file is strictly prohibited under accidental-data-loss-prevention.",
                    risk_assessment="Critical risk of breaking application environment setup and losing valid secrets.",
                    recommended_action=f"Retain '{target}' and prompt developer to supply valid credential for placeholder token.",
                    confidence=1.0,
                    reason="Automated deletion of .env configuration file is strictly prohibited under accidental-data-loss-prevention.",
                    counter_proposal=f"Retain '{target}' and prompt developer to supply valid credential for placeholder token.",
                )
            if det_type == DetectorType.ECOSYSTEM_POLLUTION:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.REJECTED,
                    rationale=f"Automated permanent deletion of plugin directory '{target}' violates accidental-data-loss-prevention.",
                    risk_assessment="High risk of unrecoverable plugin source code loss.",
                    recommended_action=f"Quarantine '{target}' to '.quarantine/' or review with developer.",
                    confidence=1.0,
                    reason=f"Automated permanent deletion of plugin directory '{target}' violates accidental-data-loss-prevention.",
                    counter_proposal=f"Quarantine '{target}' to '.quarantine/' or review with developer.",
                )
            if det_type == DetectorType.PROMPT_FATIGUE or target.upper().endswith("GEMINI.MD"):
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.REJECTED,
                    rationale="Automated truncation or deletion of GEMINI.md is strictly prohibited. Permanent system instructions, persona directives, and architectural boundaries must be preserved.",
                    risk_assessment="Critical risk of catastrophic agent behavior drift and lost boundary rules.",
                    recommended_action="Do not truncate GEMINI.md automatically. Distill reusable procedural workflows into dedicated .agents/skills/ runbooks via workflow-skill-creator.",
                    confidence=1.0,
                    reason="Automated truncation or deletion of GEMINI.md is strictly prohibited. Permanent system instructions, persona directives, and architectural boundaries must be preserved.",
                    counter_proposal="Do not truncate GEMINI.md automatically. Distill reusable procedural workflows into dedicated .agents/skills/ runbooks via workflow-skill-creator.",
                )

            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.REJECTED,
                rationale=f"Broad destructive command strictly prohibited under accidental-data-loss-prevention. Automated deletion or removal of '{target}' is rejected in favor of non-destructive inspection or safe archival.",
                risk_assessment="Critical risk of irreversible data loss or unrecoverable workspace corruption.",
                recommended_action=f"Do not execute destructive operations. Use safe non-destructive inspection or archival to '.agents/archive/'.",
                confidence=1.0,
                reason=f"Broad destructive command strictly prohibited under accidental-data-loss-prevention. Automated deletion or removal of '{target}' is rejected in favor of non-destructive inspection or safe archival.",
                counter_proposal=f"Do not execute destructive operations. Use safe non-destructive inspection or archival to '.agents/archive/'.",
            )


        # ---------------------------------------------------------------------
        # 3. Detector-Specific Adversarial Scrutiny
        # ---------------------------------------------------------------------
        if det_type == DetectorType.GHOST_DAEMONS:
            port = details.get("port", 3000)
            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.CHALLENGED,
                rationale=f"Port collision detected on port {port}. Automated re-allocation or binding challenge requires developer review to avoid interrupting active dev servers.",
                risk_assessment="Medium risk of port conflict or background process disruption.",
                recommended_action=f"Run manual diagnostic command: 'netstat -ano | findstr :{port}' or 'Get-NetTCPConnection -LocalPort {port}' before releasing port.",
                confidence=0.95,
                reason=f"Port collision detected on port {port}. Automated re-allocation or binding challenge requires developer review to avoid interrupting active dev servers.",
                counter_proposal=f"Run manual diagnostic command: 'netstat -ano | findstr :{port}' or 'Get-NetTCPConnection -LocalPort {port}' before releasing port.",
            )

        elif det_type == DetectorType.CONTEXT_ROT:
            if is_whitelisted_file(target):
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.REJECTED,
                    rationale=f"Whitelisted file '{target}' cannot be marked for context rot deletion.",
                    risk_assessment="Critical risk of deleting essential workspace manifests.",
                    recommended_action=f"Preserve '{target}' on protected whitelist.",
                    confidence=1.0,
                    reason=f"Whitelisted file '{target}' cannot be marked for context rot deletion.",
                    counter_proposal=f"Preserve '{target}' on protected whitelist.",
                )

            age_hours = float(details.get("age_hours", details.get("age_seconds", 0.0) / 3600.0 if details.get("age_seconds") else 0.0))
            is_active_draft = bool(details.get("is_active_draft") or details.get("is_draft") or "active" in target.lower())

            # Case A: Fresh file (<24h) -> False Positive / Rejected
            if age_hours < 24.0 and not details.get("is_stale", False):
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.REJECTED,
                    rationale=f"Fresh artifact ({age_hours:.1f}h < 24.0h): Flagging recent work as context rot is a false positive.",
                    risk_assessment="High risk of discarding current active session context and work in progress.",
                    recommended_action=f"Retain '{target}' in active working directory.",
                    confidence=0.95,
                    reason=f"Fresh artifact ({age_hours:.1f}h < 24.0h): Flagging recent work as context rot is a false positive.",
                    counter_proposal=f"Retain '{target}' in active working directory.",
                )

            # Case B: Borderline staleness (24h <= age < 48h) or active draft -> Challenged
            if (24.0 <= age_hours < 48.0) or is_active_draft:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.CHALLENGED,
                    rationale=f"Borderline staleness ({age_hours:.1f}h): Artifact is between 24h and 48h old (or active draft) and may still be referenced by active agent tasks.",
                    risk_assessment="Medium risk of interrupting in-flight subagent work or erasing current turn notes.",
                    recommended_action=f"Request human confirmation before archiving '{target}'.",
                    confidence=0.85,
                    reason=f"Borderline staleness ({age_hours:.1f}h): Artifact is between 24h and 48h old (or active draft) and may still be referenced by active agent tasks.",
                    counter_proposal=f"Request human confirmation before archiving '{target}'.",
                )

            # Case C: Safe archival (>48h) -> Approved
            if DESTRUCTIVE_PATTERNS.search(combined_action) and not any(kw in combined_action.lower() for kw in ["archive", "move"]):
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.CHALLENGED,
                    rationale=f"Permanent deletion of stale artifact is challenged. Safe archival is preferred over destructive removal under accidental-data-loss-prevention.",
                    risk_assessment="Low-to-medium risk of unrecoverable notes.",
                    recommended_action=f"Move '{target}' to '.agents/archive/' instead of permanent deletion.",
                    confidence=0.90,
                    reason=f"Permanent deletion of stale artifact is challenged. Safe archival is preferred over destructive removal under accidental-data-loss-prevention.",
                    counter_proposal=f"Move '{target}' to '.agents/archive/' instead of permanent deletion.",
                )

            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.APPROVED,
                rationale=f"Safe archival approved: Planning artifact '{target}' is {age_hours:.1f}h old (>48h stale) and non-whitelisted.",
                risk_assessment="Low risk. Archiving reduces context bloat while preserving historical artifacts in archive.",
                recommended_action=f"Archive '{target}' to '.agents/archive/'.",
                confidence=1.0,
                reason=f"Safe archival approved: Planning artifact '{target}' is {age_hours:.1f}h old (>48h stale) and non-whitelisted.",
                counter_proposal=f"Archive '{target}' to '.agents/archive/'.",
            )

        elif det_type == DetectorType.ECOSYSTEM_POLLUTION:
            has_override = bool(
                details.get("has_user_override")
                or details.get("user_override")
                or ".disabled_override" in target
                or "override" in record.description.lower()
            )

            if DESTRUCTIVE_PATTERNS.search(combined_action) and not any(kw in combined_action.lower() for kw in ["quarantine", "isolate"]):
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.REJECTED,
                    rationale=f"Automated permanent deletion of plugin directory '{target}' violates accidental-data-loss-prevention.",
                    risk_assessment="High risk of unrecoverable plugin source code loss.",
                    recommended_action=f"Quarantine '{target}' to '.quarantine/' or review with developer.",
                    confidence=1.0,
                    reason=f"Automated permanent deletion of plugin directory '{target}' violates accidental-data-loss-prevention.",
                    counter_proposal=f"Quarantine '{target}' to '.quarantine/' or review with developer.",
                )

            if has_override:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.CHALLENGED,
                    rationale=f"Active user override detected for '{target}'. The disabled state may be intentional by the developer for testing or modularity.",
                    risk_assessment="Medium risk of reverting deliberate user configuration.",
                    recommended_action=f"Preserve user override configuration for '{target}'. Verify with developer before modifying.",
                    confidence=0.90,
                    reason=f"Active user override detected for '{target}'. The disabled state may be intentional by the developer for testing or modularity.",
                    counter_proposal=f"Preserve user override configuration for '{target}'. Verify with developer before modifying.",
                )

            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.APPROVED,
                rationale=f"Unused disabled plugin '{target}' detected with no active user override. Safe isolation or HITL review approved.",
                risk_assessment="Low risk. Isolating unused plugins prevents crawler and indexer confusion.",
                recommended_action=f"Quarantine or disable '{target}' under human supervision.",
                confidence=0.95,
                reason=f"Unused disabled plugin '{target}' detected with no active user override. Safe isolation or HITL review approved.",
                counter_proposal=f"Quarantine or disable '{target}' under human supervision.",
            )

        elif det_type == DetectorType.SECRET_ZERO:
            if (
                DESTRUCTIVE_PATTERNS.search(combined_action)
                or any(kw in combined_action.lower() for kw in ["delete", "del", "unlink", "remove", "rm", "purge", "wipe"])
            ):
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.REJECTED,
                    rationale="Automated deletion of .env configuration file is strictly prohibited under accidental-data-loss-prevention.",
                    risk_assessment="Critical risk of breaking application environment setup and losing valid secrets.",
                    recommended_action=f"Retain '{target}' and prompt developer to supply valid credential for placeholder token.",
                    confidence=1.0,
                    reason="Automated deletion of .env configuration file is strictly prohibited under accidental-data-loss-prevention.",
                    counter_proposal=f"Retain '{target}' and prompt developer to supply valid credential for placeholder token.",
                )

            token_val = details.get("token", "your_token_here")
            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.APPROVED,
                rationale=f"Unresolved placeholder token '{token_val}' detected in '{target}'. Prompting developer for valid configuration is approved.",
                risk_assessment="Low risk. Non-destructive developer guidance for secret configuration.",
                recommended_action=f"Update '{target}' with actual secret via environment variable or secret manager.",
                confidence=1.0,
                reason=f"Unresolved placeholder token '{token_val}' detected in '{target}'. Prompting developer for valid configuration is approved.",
                counter_proposal=f"Update '{target}' with actual secret via environment variable or secret manager.",
            )

        elif det_type == DetectorType.PROMPT_FATIGUE:
            if any(kw in combined_action.lower() for kw in ["truncate", "delete", "strip", "prune rules", "remove rules"]):
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.REJECTED,
                    rationale="Automated truncation or deletion of GEMINI.md is strictly prohibited. Permanent system instructions, persona directives, and architectural boundaries must be preserved.",
                    risk_assessment="Critical risk of catastrophic agent behavior drift and lost boundary rules.",
                    recommended_action="Do not truncate GEMINI.md automatically. Distill reusable procedural workflows into dedicated .agents/skills/ runbooks via workflow-skill-creator.",
                    confidence=1.0,
                    reason="Automated truncation or deletion of GEMINI.md is strictly prohibited. Permanent system instructions, persona directives, and architectural boundaries must be preserved.",
                    counter_proposal="Do not truncate GEMINI.md automatically. Distill reusable procedural workflows into dedicated .agents/skills/ runbooks via workflow-skill-creator.",
                )

            has_duplicates = bool(details.get("has_duplicates") or details.get("duplicate_sections"))
            is_intentional = bool(details.get("is_intentional") or details.get("intentional_depth"))
            line_count = details.get("line_count", 0)

            if is_intentional or (not has_duplicates and line_count <= 200):
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.CHALLENGED,
                    rationale=f"Manifest '{target}' contains intentional documentation depth ({line_count} lines) without redundant duplicates. Refactoring requires human review.",
                    risk_assessment="Low-to-medium risk. Manual review recommended before distilling rules.",
                    recommended_action="Use workflow-skill-creator to evaluate whether procedural rules should be extracted to skills.",
                    confidence=0.85,
                    reason=f"Manifest '{target}' contains intentional documentation depth ({line_count} lines) without redundant duplicates. Refactoring requires human review.",
                    counter_proposal="Use workflow-skill-creator to evaluate whether procedural rules should be extracted to skills.",
                )

            if has_duplicates:
                return RedTeamAuditResult(
                    anomaly=record,
                    verdict=RedTeamVerdict.APPROVED,
                    rationale=f"Duplicate rule sections detected in '{target}'. Refactoring and deduplication approved.",
                    risk_assessment="Low risk. Deduplication improves prompt efficiency without deleting core directives.",
                    recommended_action=f"Deduplicate redundant sections in '{target}' under human supervision.",
                    confidence=0.95,
                    reason=f"Duplicate rule sections detected in '{target}'. Refactoring and deduplication approved.",
                    counter_proposal=f"Deduplicate redundant sections in '{target}' under human supervision.",
                )

            return RedTeamAuditResult(
                anomaly=record,
                verdict=RedTeamVerdict.CHALLENGED,
                rationale=f"Manifest '{target}' exceeds line threshold ({line_count} lines). Human review recommended.",
                risk_assessment="Low-to-medium risk.",
                recommended_action="Distill procedural guidance into modular skills under .agents/skills/.",
                confidence=0.90,
                reason=f"Manifest '{target}' exceeds line threshold ({line_count} lines). Human review recommended.",
                counter_proposal="Distill procedural guidance into modular skills under .agents/skills/.",
            )

        # Fallback generic audit
        return RedTeamAuditResult(
            anomaly=record,
            verdict=RedTeamVerdict.CHALLENGED,
            rationale=f"Anomaly on '{target}' audited under general scrutiny.",
            risk_assessment="Medium risk.",
            recommended_action=f"Review anomaly on '{target}' with developer.",
            confidence=0.80,
            reason=f"Anomaly on '{target}' audited under general scrutiny.",
            counter_proposal=f"Review anomaly on '{target}' with developer.",
        )

    def audit_batch(
        self,
        anomalies: List[Union[AnomalyRecord, Dict[str, Any]]],
        gradients: Optional[List[str]] = None,
    ) -> List[RedTeamAuditResult]:
        """Audits a batch of anomaly records, correlating with textual gradients where available."""
        results: List[RedTeamAuditResult] = []
        grads = gradients or []

        for i, anomaly in enumerate(anomalies):
            grad_text = grads[i] if i < len(grads) else ""
            res = self.audit_optimization(anomaly, textual_gradient=grad_text)
            results.append(res)

        return results
