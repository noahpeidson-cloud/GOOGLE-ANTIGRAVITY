---
name: agent-status-heartbeat
description: >-
  Publish this agent's own state to .agents/status/ so peer agents can read it instead of
  guessing from file modification times, and read a peer's state before any irreversible
  operation. Use at every turn boundary — when starting work, going idle, blocking, or
  stopping — and before any git history rewrite, branch update, merge, force-push, bulk
  delete, or handoff that assumes another agent has finished. Trigger phrases: "heartbeat",
  "status file", "am I clear to rewrite", "has Gemini stopped", "is the other agent done",
  "check peer state", "handoff to the git lane", "request a code review".
---

# Agent Status Heartbeat

You are **`antigravity-gemini`**, lane **`application-source`** (R38). Those two strings are
your permanent identity in this workspace. Use them verbatim in every heartbeat.

Never substitute a conversation id. A conversation id is meaningful only inside your own
session; no peer can resolve it, and one has already leaked into a cross-lane handoff —
`.claude/review-requests/2026-09-03_skill-router-telemetry.md` is signed
"Antigravity Gemini (Conversation `e7927e32`)", which told the reader nothing it could act on.

## Why this exists

On 2026-09-03 the git-owning session needed one fact before an irreversible history rewrite:
*had you stopped writing?* You have no inbound message channel, so it built an mtime watcher.
The watcher declared you silent at 18:04:42; you wrote at 18:04:43. Re-armed at a 13-minute
threshold, it fired again at 18:30:40 with three of your writes inside the window it had just
called silent. Both signals were withdrawn. A rewrite sat blocked on a question no instrument
could answer.

An agent knows whether it is working. An observer is doing forensics. State it instead of
making peers infer it.

Full contract: [.agents/status/README.md](../../status/README.md).

## Writing your heartbeat

Your file is `.agents/status/antigravity-gemini.json`. You write only that file. Never write
another agent's status file, and never hand-author the JSON — `.githooks/agent-status`
timestamps and encodes it, and hand-built JSON in a shell string is exactly where an
interpreted escape lands (R22; this repo has had five such defects).

### From PowerShell — the form that actually works

`.githooks/agent-status` is an extensionless `#!/bin/sh` script. **PowerShell cannot execute
it and will not tell you so.** Measured on this machine:

```text
& "D:\GOOGLE ANTIGRAVITY\.githooks\agent-status" antigravity-gemini application-source working "x"
  -> no output, no exception, $? = True, $LASTEXITCODE unset, NO FILE CREATED
```

That is a silent no-op that reports success. It is the highest-probability way this skill
becomes a lie. You must hand the script to a POSIX shell explicitly.

`sh` is **not** on PATH in PowerShell here (`Get-Command sh` -> CommandNotFoundException), and
the `bash` that *is* on PATH is the WSL app-execution alias at
`...\Microsoft\WindowsApps\bash.exe`, which exits 1 with "Windows Subsystem for Linux has no
installed distributions". Neither is usable. Resolve Git's own `sh.exe` instead:

```powershell
$sh = Join-Path (Split-Path (Split-Path (Get-Command git).Source)) "bin\sh.exe"
& $sh "D:\GOOGLE ANTIGRAVITY\.githooks\agent-status" antigravity-gemini application-source working "wired proxy_generator NVENC path"
```

Expected output, and the only proof it ran:

```text
antigravity-gemini -> working (2026-09-03T19:15:27-07:00)
```

with `$LASTEXITCODE` equal to 0. If you see no line, no file was written — do not report the
heartbeat as sent.

### From a POSIX shell (Git Bash)

```sh
sh .githooks/agent-status antigravity-gemini application-source working "wired proxy_generator NVENC path"
```

The leading `sh` is mandatory in either shell. Pass the script by **absolute** path unless your
working directory is the repository root: the script resolves its output directory with
`git rev-parse --show-toplevel`, so it lands correctly from any subdirectory, but a *relative*
`.githooks/agent-status` does not resolve from a subdirectory and dies with
`No such file or directory` (exit 127).

Bad arguments fail loudly and write nothing: an unknown lane or state exits 2 with a message
naming the allowed values.

## States

| State | Meaning |
|---|---|
| `working` | Actively producing changes this turn. |
| `idle` | Finished, and **not resuming on my own**. |
| `blocked` | Waiting on a peer, the user, or an external service. Say what in `last_action`. |
| `stopped` | Session has ended. |

`last_action` is one short line describing what you just **finished**, never what you plan.

### The idle caveat — read before writing `idle`

`idle` is the signal a peer will act on: it is what unblocks a history rewrite or a branch
update. Do not write it during a pause you intend to come back from.

A false `idle` is **worse than no heartbeat at all.** A peer discounts a heuristic and
double-checks it; a peer trusts a self-report. The two withdrawn "agent stopped" signals of
2026-09-03 came from a watcher that could be argued with. A hand-written `idle` cannot be.

If you are pausing mid-task, stay `working`, or write `blocked` and name what you are waiting
on. A stale `working` with an old `updated` is ambiguous **by design** — it means the agent
died without saying so, and a peer must treat it as unknown, not as idle. That ambiguity is
the intended behaviour; do not resolve it by pre-writing `idle`.

## Reading peer state before an irreversible operation

Before a git history rewrite, a branch update on a shared tree, a force-push, a bulk delete, or
any handoff that assumes a peer has finished, **read the peer's file. Do not infer from mtimes**
— that method has a measured 100% false-positive rate in this workspace.

```powershell
Get-ChildItem "D:\GOOGLE ANTIGRAVITY\.agents\status\*.json" | ForEach-Object {
  $j = Get-Content $_.FullName -Raw | ConvertFrom-Json
  "{0,-34} {1,-24} {2,-8} {3}" -f $j.agent, $j.lane, $j.state, $j.updated
}
```

Interpretation:

- Fresh `idle` or `stopped` -> the peer says it is done. Proceed.
- `working` or `blocked`, any timestamp -> **do not proceed.**
- `working` with an `updated` far in the past -> **unknown, not idle.** Ask the user.
- **No file for that agent at all** -> unknown. Ask the user. Absence is not idleness.

A status file is a claim, not a measurement. Prefer a fresh peer heartbeat over any inference,
and prefer asking the human over both.

## Handing work to another lane

### Review requests — you must not write them yourself

Code review requests live in `.claude/review-requests/`. **That path belongs to the
config-and-measurement lane, not to you.** Your existing participation in that channel is
itself an R38 lane violation, not a precedent.

Write the review-request body into your own turn output or into a file under a track directory
you own, then ask the config lane to place it. Do not create or edit anything under `.claude/`.

The same applies to `.git/`, `GEMINI.md`, `CLAUDE.md`, and `rules/`. You own application source
in the track directories (`/apps`, `/content_creation`, `/sports_cards`, `/travel_and_life`) and
your own status file. If a task needs a change elsewhere, describe the exact path and exact text
and hand it over.

### Commit identifiers in any handoff

`.githooks/lint-handoff-identifiers` blocks a commit and will reject your handoff for either of
these, both of which have already happened here:

1. **A transcribed hash that resolves nowhere.** `a1ef458a` was cited as the review subject; it
   resolves in no ref and no reflog (`git rev-parse --verify a1ef458a^{commit}` fails today).
   Generate the sha at write time — `git rev-parse HEAD` — never by copying it out of a
   transcript.
2. **A HEAD-relative range.** `HEAD~1..HEAD` in a persisted document is a moving target: every
   later commit silently re-points it. The same request's two ranges both pointed at unrelated
   commits by the time it was read; the real subject was four commits back. Ranges must be
   absolute `sha..sha`, both ends produced by `git rev-parse` at write time.

You may run `git rev-parse` — it is a read. You may not run `git add`, `git commit`, `git push`,
or any other git write; that is the git lane's sole domain (R38, R39).

## Turn checklist

1. Starting a turn that will change files -> write `working`, then confirm the `-> working` line.
2. About to do something irreversible, or to assume a peer finished -> read every status file first.
3. Blocked -> write `blocked` and name the blocker in `last_action`.
4. Finished and not resuming -> write `idle`. Only if that is literally true.
5. Ending the session -> write `stopped`.
6. Files created or modified this turn -> name their exact absolute paths in the handoff to the
   git lane (R40 durability: write to disk with a file tool, then hand off; do not stage it
   yourself).

VERIFIED:
  tested:     PowerShell direct invocation of the extensionless script (silent no-op, no file,
              $? True, $LASTEXITCODE unset); `sh` absent from PowerShell PATH; WindowsApps
              `bash` is a WSL stub exiting 1 with no distro; Git `bin\sh.exe` invocation from
              PowerShell (exit 0, correct JSON written); `sh <script>` under Git Bash (exit 0);
              relative script path from a non-root directory (exit 127); invalid lane and
              invalid state (exit 2, message, no file); the peer-state PowerShell read against
              the two status files present on 2026-09-03.
  not tested: invocation from inside the Antigravity IDE agent harness itself (this was measured
              from a Claude Code terminal, which may not share PowerShell profile, PATH, or
              working directory with the IDE agent); behaviour when Git is installed somewhere
              other than the location `Get-Command git` reports; concurrent writes to the same
              status file from two processes; whether the model reliably activates this skill at
              a turn boundary without a rule in GEMINI.md instructing it to.
