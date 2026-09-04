# Claude Code — Workspace Contract

This file exists so Claude Code loads the same rulebook the Antigravity/Gemini agent
loads. Without it, Claude sessions start with zero knowledge of `rules/` and re-derive
policy from scratch every session. Keep it short — it is prefix context on every turn.

Per R42, load order is static-to-dynamic: immutable rules first, volatile input last.

## Immutable rules (position 1)

@rules/01_python_runtime.md
@rules/02_cloud_and_db.md
@rules/03_multi_agent_guardrails.md
@rules/04_video_apv_8k.md
@rules/05_zero_copy_storage.md

## Workspace manifest and persona

@GEMINI.md

## Agent lane assignment

Three agents operate on `D:\GOOGLE ANTIGRAVITY` concurrently. Lanes are not advisory —
crossing them is the split-brain failure mode R40 describes.

| Agent | Host | Owns | Must not touch |
|---|---|---|---|
| Claude Code (git) | GitKraken Desktop | All git mutation: index, commits, branches, merges, worktrees | `.claude/`, application source |
| Gemini | Antigravity IDE | Application source in track dirs | `.git/`, `.claude/`, `GEMINI.md`, `rules/` |
| Claude Code (config) | Antigravity IDE terminal | `.claude/`, `CLAUDE.md`, measurement and verification | Any git write |

**One writer per domain.** If a task requires another lane, hand off — do not reach across.
Cross-session handoff uses `SendMessage`; both Claude sessions are peers via `ListAgents`.

## Verification standard

R02 requires empirical verification. In a multi-agent workspace this extends further:

- **Measure, do not recall.** Another agent's status report describes its context, not the
  disk. Re-read the disk before acting on any claim about repo state. This has caught three
  false claims already: a branch reported as `main` that was `feat/c-drive-guardrail`, a
  credential "leak" that was a hook test fixture, and a rules edit attributed to the wrong session.
- State findings with the command that produced them, not with confidence language.

## Known-false rule claims

Rules describe intent; some describe controls that do not yet exist. Verify before relying:

- **R39** states GitHub branch protection enforces `main` server-side. `gh` is not installed
  on this machine and protection was never configured. The only live enforcement is
  `.githooks/pre-commit` (wired via `core.hooksPath`), which fires on commit — it cannot stop
  a push of already-committed content.
- **R42** requires offloading large output to `D:\AI_Platform\scratch`. Create it if absent.

## Repo hazards

- `archive/` holds 1,574 tracked files whose basenames collide with 51 live-tree files
  (`config.py`, `app.py`, `database.py`, `GEMINI.md`, `AGENTS.md`). **Scope every search to the
  live tree**; a grep hit under `archive/` or `.archive/` is stale by default.
- `.git` is ~5.7 GB; three media blobs account for 96% of it. Avoid operations that
  rewrite or re-walk full history unless that is the explicit task.
