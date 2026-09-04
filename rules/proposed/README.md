# Proposed Rules — the append-only path into `rules/`

## Why this directory exists

`rules/` was previously declared immutable to every agent. That contract broke the
first time an agent had a legitimate rule to contribute: the Antigravity/Gemini agent
authored R47 (Triad Cognitive Pipeline) and, with no sanctioned path available, had to
edit the canonical file to add it. The rule it added was sound. The contract was not.

A ban with no alternative does not protect a file — it just guarantees the ban gets
broken by whoever has something worth adding. This directory is the alternative.

## The path

1. **Any agent may write here, freely, at any time.** No permission needed, no lane
   restriction. Name the file `R<number>_<short_slug>.md`.
2. **The git-owning session reviews and merges** the proposal into the numbered rule
   set in `rules/`. That session is the sole writer to canonical `rules/*.md`.
3. **Nothing here is in force.** A rule takes effect only once merged into a numbered
   file. Agents must not cite a `proposed/` rule as binding.

## Format

Every file here starts with frontmatter declaring which number it touches. This is
not decoration — `.githooks/lint-rule-collisions` reads it and blocks the commit if
the number is wrong.

A new rule:

```yaml
---
proposal: R49
type: new
status: proposed
---
```

An amendment to a rule already in force (see R49):

```yaml
---
amends: R40
type: amendment
status: proposed
---
```

The hook checks three things: a `type: new` number must still be free in `rules/`,
a `type: amendment` number must already exist there, and the filename's leading
`R<number>` must agree with the frontmatter. Two proposals claiming one number is
also blocked.

Then match the existing rule shape so a merge is a copy, not a rewrite:

```markdown
## R<number>. <Title>
- **Context:** when this applies
- **Mandate:** what agents MUST or MUST NOT do
- **Actionable Execution:** the concrete steps, commands, or paths
```

State the enforcement honestly. If a rule has no hook, deny-rule, or CI check behind
it, say so in the proposal — R39 already demonstrates the failure mode of a rule whose
text asserts an enforcement that does not exist.

## Numbering

**Always read `rules/03_multi_agent_guardrails.md` for the current highest number before
claiming one — do not trust a number written here.** As of this writing R02, R22 and
R38–R48 are taken, but that list went stale within an hour of being written: R44–R48
were all added while this file sat unchanged. If two agents race for the same number,
the merging session reassigns — do not renumber another agent's proposal in place.

That instruction has already failed in practice, which is why it is now backed by a
hook. `GEMINI.md` and `rules/03_multi_agent_guardrails.md` each define an R38 and an
R39, and the pairs are unrelated mandates. Those four numbers (R2, R22, R38, R39) are
recorded in `.githooks/rule-collisions.allow` so the lint can block the next one
instead of drowning in the existing ones.
