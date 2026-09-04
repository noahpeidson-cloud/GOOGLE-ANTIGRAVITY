# Handoff: GEMINI.md / rules/ deduplication and the R38-R39 renumber

**From:** config-and-measurement lane (`google-antigravity-8c`)
**To:** the lane that owns `GEMINI.md` and `rules/` — per `CLAUDE.md`'s table that is the
git lane; the Gemini lane is explicitly forbidden both paths.
**Status:** proposal. Nothing in `GEMINI.md` or `rules/` was modified to produce this.
**Produced by:** `/doctor`, 2026-09-03.

## Why this exists

Every Claude session loads `CLAUDE.md`, which `@`-imports `rules/01`–`rules/05` and
`GEMINI.md`. Measured on disk:

| File | Bytes | Est. tokens |
|---|---:|---:|
| `GEMINI.md` | 18,870 | ~4,717 |
| `rules/03_multi_agent_guardrails.md` | 18,032 | ~4,508 |
| `rules/06_code_review_standard.md` | 2,725 | ~681 |
| `CLAUDE.md` | 2,999 | ~749 |
| `rules/04_video_apv_8k.md` | 2,318 | ~579 |
| `rules/01_python_runtime.md` | 2,124 | ~531 |
| `rules/02_cloud_and_db.md` | 1,965 | ~491 |
| `rules/05_zero_copy_storage.md` | 1,279 | ~319 |
| **Total always-loaded** | **50,312** | **~12,578** |

No single file trips the large-memory-file warning (~40,000 chars), so nothing is being
truncated. The cost is simply that ~12.6k tokens are resident before the user types
anything.

## Finding 1 — nine rule numbers appear in both `GEMINI.md` and `rules/`

    R16  R17  R18  R22  R26  R34  R36  R38  R39

Reproduce:

    grep -oE '^#{1,3}[[:space:]]*R[-A-Z]*[0-9]+\.' GEMINI.md rules/*.md | sort -u

Seven of the nine are **true duplicates** — the same mandate stated twice, differing only
in title wording and prose:

| Number | `rules/` | `GEMINI.md` |
|---|---|---|
| R16 | Executable Python Import Guardrail | Executable Python Import Guardrail |
| R17 | BigQuery DDL Guardrail | BigQuery DDL Guardrail |
| R18 | Python Dependency Pre-Flight Guardrail | Python Dependency Pre-Flight Guardrail |
| R22 | Direct Tool File Modification Guardrail | The Markdown Data Loss Prevention Guardrail |
| R26 | Background Daemon Auth Guardrail | The Background Daemon Auth Guardrail |
| R34 | Google Drive MCP Bandwidth Guardrail | The Google Drive MCP Bandwidth Guardrail |
| R36 | GCP Authentication Guardrail | The GCP Authentication Guardrail (MS Store CLI) |

Those seven blocks occupy **5,205 chars (~1,301 est. tokens)** of `GEMINI.md`, loaded on
top of the identical text already arriving from `rules/01` and `rules/02`.

R22 is listed here as a duplicate rather than a collision because both texts forbid the
same thing — authoring files through shell interpolation. `rules/03` states it as a tool
mandate, `GEMINI.md` as a data-loss warning. `.githooks/rule-collisions.allow` classifies
it as "same prohibition, different framing and scope", which is the more careful reading;
if the git lane agrees with that classification, R22 belongs in Finding 2 instead and
should be renumbered rather than deleted.

## Finding 2 — R38 and R39 resolve to unrelated mandates

| Number | `rules/03` | `GEMINI.md` |
|---|---|---|
| R38 | VS Code Deprecation & GitKraken Swarm Lane Architecture | The Fail-Fast API Guardrail (Anti-Mocking) |
| R39 | Git Ownership & Branch Discipline | The Terminal Confidence Block Guardrail |

This is a direct R49 violation: *"A rule number is a permanent, single-meaning identifier:
every citation of a number across sessions, skills, and commit messages must resolve to
one mandate."*

It is not theoretical. Over one evening, this session and the git session used "R39"
throughout to mean branch discipline, while `GEMINI.md`'s R39 is what makes agents append
`<confidence>` blocks. Both mandates are live and both are cited by number.

`.githooks/rule-collisions.allow` already records R2, R22, R38 and R39, with its own note
that this is "debt, not a pardon" and that the fix is a renumber in `GEMINI.md` —
outside the lane that wrote the hook. This handoff is that fix reaching the right lane.

## Proposed changes

### A. Delete the seven duplicated rule blocks from `GEMINI.md`

Remove the `### R16`, `### R17`, `### R18`, `### R26`, `### R34`, `### R36` blocks — and
`### R22` only if the git lane classifies it as duplication rather than collision. Replace
the run with a single pointer so nothing is silently lost:

    > R16, R17, R18, R22, R26, R34 and R36 are defined canonically in `rules/01_python_runtime.md`
    > and `rules/02_cloud_and_db.md`, which `CLAUDE.md` imports. They are not restated here.

Saves ~1,301 est. tokens per session. Reversible from git history.

### B. Renumber `GEMINI.md`'s R38 and R39

`rules/03` holds the numbers. R49 clause 4 says never renumber another agent's rule to
resolve a collision — so `rules/03` keeps R38 and R39, and `GEMINI.md`'s two rules move to
free numbers. Currently free: **R51** and **R52** (`rules/` uses R02, R16–R18, R22, R26,
R34, R36, R38–R50 plus the `R-APV-*` and `R-STORE-*` namespaces; `GEMINI.md` additionally
uses R1–R4, R15, R19–R21, R23–R25, R27, R28, R31, R32, R35, R37).

    GEMINI.md R38 "The Fail-Fast API Guardrail (Anti-Mocking)"        -> R51
    GEMINI.md R39 "The Terminal Confidence Block Guardrail"           -> R52

Then delete the R38 and R39 lines from `.githooks/rule-collisions.allow`, leaving R2 and
R22 (or R2 alone, if A also resolves R22). The lint fails closed on a *new* collision, so
removing a resolved entry is the correct bookkeeping.

**Grep for stale citations before landing this.** `<confidence>` is enforced by a watchdog
and referenced in agent instructions; a renumber that misses a citation makes the rule
uncitable:

    grep -rn --exclude-dir=archive --exclude-dir=.archive --exclude-dir=.git \
      -E '\bR38\b|\bR39\b' . | grep -v '^./rules/03'

### C. Consider moving `GEMINI.md`'s task-triggered rules to skills

Not required, and lower value than A and B. These are narrow, situation-specific rules
sitting in always-loaded context, each relevant only when its trigger occurs:

    R19  Workspace Disconnection Protocol (G: drive unmounted)
    R20  Next.js & Firebase Cache Guardrail
    R21  Procedural Media Generation Mandate
    R24  Tauri IPC Bandwidth Wall Guardrail
    R25  Google Takeout Timezone Deduplication Guardrail
    R27  Zero-Friction Fallback Mandate (429 handling)
    R32  Browser Subagent Google Routing Mandate
    R35  Ingestion Automation Guardrail (Quick Share)

As `.agents/skills/<name>/SKILL.md` files, only each one-line description stays resident.
**Do not move R2, R22, R37, or any "STRICTLY FORBIDDEN" safety rule** — a prohibition that
is only sometimes loaded is worse than one that costs tokens. Estimated saving if all eight
move: roughly 3,000-3,500 chars (~750-875 est. tokens).

## What this handoff does NOT claim

- Token figures are estimates at chars/4, not measured against a tokenizer. `/context` is
  the authoritative live number.
- Duplicate classification is by rule number and title, plus reading both texts. It is not
  a semantic diff; the git lane should confirm each of the seven before deleting it.
- Whether R22 is duplication or collision is a judgment call this lane deliberately did not
  make on someone else's file.
- Nothing here was applied. `GEMINI.md`, `rules/`, and `.githooks/rule-collisions.allow`
  are untouched by this lane.
