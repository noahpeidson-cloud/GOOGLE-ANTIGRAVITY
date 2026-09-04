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

Match the existing rule shape so a merge is a copy, not a rewrite:

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

Next free number is **R48**. Check `rules/03_multi_agent_guardrails.md` before
claiming one; R02, R22, R38–R43 and R47 are taken. If two agents race for a number,
the merging session reassigns — do not renumber another agent's proposal in place.
