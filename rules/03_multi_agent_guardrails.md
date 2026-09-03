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
