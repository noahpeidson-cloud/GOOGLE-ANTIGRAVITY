"""Tests for Architecture Red Team Scrutiny Engine (PROJECT.md contract)."""

from tests.test_red_team_and_report import (
    test_red_team_audit_batch,
    test_red_team_context_rot_borderline_staleness_challenged,
    test_red_team_context_rot_fresh_file_rejected,
    test_red_team_context_rot_stale_scratchpad_approval,
    test_red_team_context_rot_whitelisted_file_rejection,
    test_red_team_ecosystem_pollution_audits,
    test_red_team_ghost_daemons_challenges_safe_diagnostics,
    test_red_team_prompt_fatigue_audits,
    test_red_team_rejects_automated_process_killing,
    test_red_team_secret_zero_audits,
    test_whitelisted_file_detection,
)

__all__ = [
    "test_whitelisted_file_detection",
    "test_red_team_rejects_automated_process_killing",
    "test_red_team_ghost_daemons_challenges_safe_diagnostics",
    "test_red_team_context_rot_whitelisted_file_rejection",
    "test_red_team_context_rot_stale_scratchpad_approval",
    "test_red_team_context_rot_borderline_staleness_challenged",
    "test_red_team_context_rot_fresh_file_rejected",
    "test_red_team_ecosystem_pollution_audits",
    "test_red_team_secret_zero_audits",
    "test_red_team_prompt_fatigue_audits",
    "test_red_team_audit_batch",
]
