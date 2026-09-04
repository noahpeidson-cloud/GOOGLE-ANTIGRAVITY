---
title: "Multi-Agent & Dual-IDE Guardrails"
category: "agentic"
enforcement: "strict"
---

# Multi-Agent & Dual-IDE Guardrails

## R02. Zero-Discretion Empirical Verification
- **Context:** Every code modification, test pass assertion, or infrastructure state change.
- **Mandate:** Agents MUST NOT claim success or pass assertions without executing real tests, inspecting real process outputs, or verifying network responses.
- **Actionable Execution:** Execute test runners via the terminal, verify zero exit codes, and output `<confidence>X/10</confidence>`.

## R22. Direct Tool File Modification Guardrail
- **Context:** Creating or modifying files across the repository.
- **Mandate:** Agents are STRICTLY FORBIDDEN from using shell interpolation (`cat << EOF`, `echo > file`, `sed`) to author code files.
- **Actionable Execution:** Use native editor/agent file modification tools.

## R38. Dual-IDE State Synchronization Guardrail
- **Context:** Concurrent operations between VS Code and Antigravity IDE.
- **Mandate:** Agents must prevent file-lock contention and ensure atomic reads on shared SQLite databases and JSON manifests (`command_bridge.json`, `feature_list.json`).
- **Actionable Execution:** Always close file handles and check lock statuses before starting long-running background tasks.

## R39. Git Ownership & Branch Discipline
- **Context:** Any agent (Claude Code, Antigravity IDE harness, or other) with git write access to this repository.
- **Mandate:** Claude Code is the sole integrator of `main`. Other agents MUST work on their own `feat/*` (or similarly namespaced) branches and hand off via pull request — never commit or push directly to `main`.
- **Actionable Execution:** GitHub branch protection on `main` enforces this server-side (required PRs, no direct pushes). This rule is documentation of that policy, not the enforcement mechanism — do not rely on an agent reading and following this text alone. If branch protection is ever absent, treat direct-to-`main` writes as the R38 file-lock-contention failure mode and stop.
