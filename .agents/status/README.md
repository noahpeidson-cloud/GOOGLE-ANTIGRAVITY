# Agent Status Heartbeats

## The failure this replaces

On 2026-09-03 the git-owning session needed one fact before running an irreversible
history rewrite: *has the Antigravity/Gemini agent stopped writing?* Gemini has no
inbound message channel, so the terminal session tried to infer the answer from file
modification times.

It built a watcher. The watcher fired "no writes for 180 seconds" at 18:04:42, and
Gemini wrote at 18:04:43 — one second later. It was re-armed at a 13-minute threshold,
above Gemini's observed 8m34s maximum pause. It fired again at 18:30:40, with three
writes inside the window it declared silent (18:30:14, 18:30:29, 18:30:38).

Both signals were withdrawn. The cause was never identified. Meanwhile a rewrite sat
blocked on a question no instrument could answer, and the only reliable resolution was
to ask the human.

**Inferring another agent's state from its filesystem exhaust does not work.** An agent
knows whether it is working; an observer is doing forensics. This directory exists so
agents state it instead.

## The contract

Each agent owns exactly one file: `.agents/status/<agent-name>.json`. You write only
your own. Never write another agent's file, and never infer a peer's state from mtimes
when its status file exists.

```json
{
  "agent":       "google-antigravity-8c",
  "host":        "Antigravity IDE terminal",
  "lane":        "config-and-measurement",
  "state":       "working",
  "last_action": "reviewed 2d780d02, reported 7 findings",
  "updated":     "2026-09-03T18:40:12-07:00"
}
```

| Field | Meaning |
|---|---|
| `agent` | Stable identity. For Claude Code sessions, the name `ListAgents` reports. |
| `host` | Which application this agent runs inside. |
| `lane` | Per R38. One of `git`, `application-source`, `config-and-measurement`. |
| `state` | `working`, `idle`, `blocked`, `stopped`. |
| `last_action` | One short line. What you just finished, not what you plan. |
| `updated` | ISO 8601 with offset. |

### When to write

At turn boundaries — when you start work, when you go idle, when you block, and before
you stop. Not on every tool call; this is a heartbeat, not a log.

`idle` means *finished and not resuming on my own*. It is the signal another agent may
act on. Do not write `idle` during a pause you intend to come back from — that is the
exact false-positive the watcher produced, and writing it by hand makes it worse, not
better, because a peer will trust a self-report more than a heuristic.

`stopped` means the session has ended. A stale `working` file with an old `updated`
timestamp is ambiguous by design: it means the agent died without saying so, and a peer
should treat it as unknown rather than idle.

## Writing it

Use `.githooks/agent-status`, which timestamps and formats correctly:

    .githooks/agent-status <agent> <lane> <state> "<last action>"

Hand-authoring the JSON is allowed but discouraged — R22 applies, and a heartbeat
written with shell interpolation is exactly where an escape gets interpreted.

## What this does not solve

A status file is a claim, not a measurement. An agent that stops writing without
updating its file leaves a stale `working` entry. That failure is at least *visible* —
a timestamp that has not advanced is legible, whereas an mtime heuristic silently
reports the wrong answer with full confidence.

Before an irreversible operation, prefer a fresh `idle` heartbeat over any inference,
and prefer asking the human over both.
