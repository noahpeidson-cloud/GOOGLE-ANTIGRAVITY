---
title: "Shared Code Review Standard"
category: "agentic"
enforcement: "referenced"
---

# Shared Code Review Standard

Canonical review criteria for this workspace. Two agent systems review code here and
had independently written the same standard twice, in two places, already diverging:

- `.claude/agents/code-reviewer.md` — Claude Code subagent, GitKraken MCP tools
- `.agents/skills/gitkraken-swarm-review/SKILL.md` — Antigravity skill, same MCP server

Both must reference this file rather than restate its contents. Two entry points, one
definition. Adapters carry only what is genuinely tool-specific — how their host invokes
MCP calls, and how findings are returned.

## S1. Establish scope before reading any diff

Never review a bare diff in isolation. Confirm the target branch and working state
first (`git_status`, `git_branch`), and for any hunk touching logic, error handling, or
a security boundary, read the full surrounding file. A hunk without its function's body
is not enough to judge correctness.

## S2. What to flag

1. **Correctness** — logic flaws, off-by-one, unhandled edge cases that will actually
   occur, race conditions, broken error handling, broken imports, type mismatches.
2. **Security** — hardcoded credentials, injection, path traversal, auth/authz gaps,
   unsafe deserialization, SSRF.
3. **Waste** — duplicated logic that already exists in the repo, unbounded quadratic
   loops, N+1 queries, un-indexed queries against growing tables, memory leaks.

## S3. What not to flag

Style preferences, formatting, naming debates, and anything a linter or formatter owns.
Speculative critiques with no concrete trigger are prohibited.

## S4. Verify against disk before reporting

Per R02 and R46, check every candidate finding against the live file — not against the
diff, and not against another agent's report of what the file contains. Confirm a
variable really is unvalidated; confirm a "duplicate" has not already been refactored
away. Only findings that survive this check are reported.

This is not ceremony. Within this workspace, agent self-reports have diverged from disk
repeatedly — a branch reported as `main` that was `feat/c-drive-guardrail`, a credential
"leak" that was a test fixture, a rules edit attributed to the wrong session. Re-read
rather than recall.

## S5. State the trigger, not the pattern

Every finding names a concrete failure path:

```
[input / state]  ->  [wrong output / crash]
```

A finding that cannot be stated in that form is not yet a finding.

## S6. Severity ordering

Report most severe first: security, then correctness, then waste. An empty result is a
valid and useful outcome — do not pad a report to look thorough.
