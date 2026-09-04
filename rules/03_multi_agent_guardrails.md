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

## R40. Split-Brain Workspace Isolation & Anti-Reset Mandate
- **Context:** Concurrent operations involving multiple IDEs (Antigravity IDE, VS Code, Claude Code) or autonomous subagents.
- **Mandate:** Agents are STRICTLY FORBIDDEN from executing `git reset --hard`, `git checkout .`, or switching branches directly on the primary workspace root (`D:\GOOGLE ANTIGRAVITY`).
- **Actionable Execution:** 
  1. Any experimental branch switching or subagent workspace isolation MUST use dedicated git worktrees (`git worktree add ../.worktrees/<branch-name>`).
  2. Before ending a turn or delegating to another agent, all new code files and rules MUST be staged and committed to git to prevent silent wipeouts during external branch updates.

## R41. NOOA Curated Memory & Anti-Raw-Embedding Standard
- **Context:** Long-term cross-session knowledge retention and retrieval.
- **Mandate:** Agents are STRICTLY FORBIDDEN from running background vector daemons (e.g. Ollama `nomic-embed-text`) or embedding uncurated conversation transcripts into prompt context.
- **Actionable Execution:** All cross-session durable memory MUST route through `CuratedMemoryHub` on `D:\AI_Platform\telemetry\vector_memory\vector_memory.db`. Store structured records containing: `domain_track`, `topic`, `finding_summary`, `importance_score` (1-10), and relational status (`replaces`).

## R42. Prompt Prefix Caching Order & Large Output Disk Offloading
- **Context:** System prompt construction, tool executions, and KV prompt cache optimization.
- **Mandate:** Agents MUST maintain static-to-dynamic prefix ordering to maximize prompt caching efficiency and eliminate recency bias:
  1. Immutable System Rules & Guardrails (`rules/`)
  2. Tool Schemas & Custom MCP Interfaces
  3. Curated Memory Dossiers (`hub.get_dossier(<track>)`)
  4. Truncated Rolling History
  5. Volatile User Input
- **Large Output Offloading:** All intermediate tool stdout > 50 lines MUST be offloaded to disk on `D:\AI_Platform\scratch\` and referenced by URI rather than passed raw into prompt context.
