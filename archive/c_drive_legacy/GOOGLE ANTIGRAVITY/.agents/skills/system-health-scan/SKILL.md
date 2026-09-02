---
name: system-health-scan
description: >-
  Executes a rigorous, data-driven system health scan on the Antigravity workspace to eradicate context bloat, detect dead code, and validate environment variables.
---

# System Health Scan Protocol

## Overview
This skill formally audits the workspace to prevent LLM Context Rot, technical debt, and token desynchronization.

> [!CAUTION]
> **MANDATORY HUMAN-IN-THE-LOOP (HITL):**
> The agent executing this scan is strictly restricted to **READ-ONLY** auditing. Under no circumstances may the agent delete files, move artifacts, or modify code autonomously. The agent must compile its findings into a report and STOP, explicitly waiting for the user to grant final approval before executing any destructive or structural changes.

## Core Directives (Data-Driven Constraints)
1. **L1/L2 Context Paging (Artifact Sweep):** 
   Identify all stale planning artifacts (e.g., `.md` files with 'proposal', 'ideas', or 'blueprint' in the name) older than 24 hours. The agent must propose moving them to a `.archive` folder (L2 cache) rather than allowing them to rot in the primary context window.
2. **Dead Code Detection:**
   Run static analysis to find orphaned `.py` files. **Crucial:** Automated deletion is strictly prohibited due to framework-aware false positives. The agent must halt and present an Architectural Nudge containing the exact diffs for human approval.
3. **Secret Zero Eradication (.env & Tokens):**
   Audit `.env` and `*.pickle` files. If a placeholder (e.g., `your_token_here`) is found, or an OAuth scope mismatch is detected, violently halt execution and prompt the user to intervene.
4. **The Watchdog Cap:**
   If this scan is run by a background subagent, it is mechanically barred at a hard maximum of 3 iterations to prevent infinite looping.
5. **Ecosystem Integrity (Plugin & Ontology Audit):**
   Search the active workspace and `.gemini/config/plugins` for `.disabled` directories that may be silently polluting the crawler's context. **CRITICAL GUARDRAIL:** Do NOT propose deleting `.disabled` skills. Instead, flag them in the report and ask the user if they should be explicitly enabled (by stripping the `.disabled` suffix) to assist with future builds, or left ignored.
6. **Daemon & Background Task Audit:**
   Use the `manage_task` (list) command to audit all running background daemons. Identify orphaned UI servers, WebSockets, or background agents. Propose killing any task that is no longer actively tied to a running process to prevent port collisions (e.g., `WinError 10048`).
