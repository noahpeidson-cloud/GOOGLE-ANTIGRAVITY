# Code Review Request — Antigravity Gemini -> Claude Code

**Requested by:** Antigravity Gemini (Conversation `e7927e32`)
**Date:** 2026-09-03T18:10 MST
**Branch:** `feat/c-drive-guardrail`
**Commit:** `a1ef458a`
**Review scope:** `HEAD~1..HEAD` (single commit, 2 source files + 1 skill file)

---

## Changed Files

| File | Type | Change Summary |
|---|---|---|
| `.agents/skills/skill-router/SKILL.md` | Skill | Full rewrite — NL triggers, context fingerprint, Rule Risk column, killed concepts |
| `infrastructure/curated_memory.py` | Python | Added `skill_telemetry` DDL + `record_skill_execution()` + `get_skill_confidence()` |
| `infrastructure/benchmark_harness.py` | Python | Added telemetry write inside `benchmark_skills()` skill loop |

---

## Implementation Plan

### Phase 1 — skill-router/SKILL.md
- Moved NL trigger phrases into YAML description field. Rationale: per agy-customizations/SKILL.md lines 85-87, only name and description are injected into context before a skill is loaded.
- Context fingerprint (3 fields, ~150 tokens) replaces a proposed SQLite+git probe (1,500 tokens/call).
- R14 ask_question modal gated to ambiguous >=2-candidate results only.
- Rule Risk annotation column added to routing table.
- Ghost Backend checkpoint added to Fullstack Dashboard pipeline.
- Permanent kill notice for DAG Pipeline Contracts and Context-Hydrated Skills (failed adversarial review).

### Phase 2 — infrastructure/curated_memory.py
- New SQLite table skill_telemetry: id, skill_name, invocation_ts, success (0/1), latency_ms, executor.
- record_skill_execution(): Hard-rejects executor not in {"benchmark_harness"} with ValueError + R2 citation.
- get_skill_confidence(): Bayesian Laplace-smoothed rate. Cold-start (<10 samples): seed_score/10.0 prior or 0.5 neutral floor.

### Phase 3 — infrastructure/benchmark_harness.py
- benchmark_skills() calls hub.record_skill_execution(executor="benchmark_harness") after scoring each skill.
- Wrapped in try/except: telemetry write failure must not break benchmark scoring.

---

## Pre-Review Verification

Tests:     python -m pytest tests/test_research_validation_agent.py -> 7/7 PASS
Benchmark: python -m infrastructure.benchmark_harness -> 10.0/10.0 [HEALTHY]
Commit:    a1ef458a on feat/c-drive-guardrail

---

## Specific Concerns for Reviewer

1. R2 enforcement gap — record_skill_execution() rejects at runtime via ValueError. Can _get_connection() be reached directly without going through this method? Should the trust boundary be at the DB layer (trigger) rather than Python method?

2. Bayesian cold-start seeding — get_skill_confidence(seed_score=X) accepts caller-provided float. Benchmark harness writes telemetry but does not call get_skill_confidence(). Who seeds the initial prior on a fresh clone? Is there a missing integration?

3. Silent telemetry failure — bare except Exception: pass in benchmark_harness.py. If D: drive is not mounted, all telemetry silently fails. Should this at minimum log a WARN rather than fully silence?

4. skill-router SKILL.md — [!WARNING] GitHub alert syntax at bottom. Verify it renders in the Antigravity skill viewer and is not treated as a literal code block.

---

## Review Protocol

Per .claude/agents/code-reviewer.md:
- Run git_log_or_diff on HEAD~1..HEAD to get the live diff.
- Open full files for any hunk where control flow or error handling changed.
- Use git_blame if any suspicious line needs age attribution.
- Call ReportFindings once with verified findings, most severe first.

Do not merge to main until findings are addressed.
