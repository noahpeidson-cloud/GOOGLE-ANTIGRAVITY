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

## R38. VS Code Deprecation & GitKraken Swarm Lane Architecture
- **Context:** Multi-agent development lifecycle across GitKraken, terminal CLI agents, and Antigravity IDE.
- **Mandate:** VS Code is completely deprecated and removed from active workflows. Agents MUST adhere to single-writer domain lane boundaries:
  1. **Claude Code (Git / GitKraken):** Owns all git mutations (index, commits, branches, merges, worktrees). Must NOT touch `.claude/` or application source directly.
  2. **Claude Code (Terminal CLI SWE):** Fast autonomous feature scaffolding on `feat/*` branches. Leaves verifiable commit metadata (`Co-Authored-By: Claude Sonnet 5`, `Claude-Session` URLs).
  3. **Claude Code Reviewer (`.claude/agents/code-reviewer.md`):** Pre-merge audit gate inspecting diffs and git graph via GitKraken MCP tools.
  4. **Antigravity IDE Gemini (Platform Architect):** Owns application code in domain tracks, long-term context, CuratedMemoryHub (SQLite WAL), research validation funnels, daemon telemetry, and benchmark verification.
- **Actionable Execution:** Never cross lanes. If a task requires changes in another lane, hand off via `send_message` or GitKraken PR — do not reach across.

## R39. Git Ownership & Branch Discipline
- **Context:** Any agent (Claude Code, Antigravity IDE harness, or other) with git write access to this repository.
- **Mandate:** Claude Code is the sole integrator of `main`. Other agents MUST work on their own `feat/*` (or similarly namespaced) branches and hand off via pull request — never commit or push directly to `main`.
- **Actionable Execution:** Enforced locally via `.githooks/pre-commit` (wired through `core.hooksPath`) which blocks direct commits to `main`. When GitHub CLI (`gh`) is authenticated, server-side branch protection provides redundant enforcement. Treat direct-to-`main` writes as critical lane violations.

## R40. Split-Brain Workspace Isolation & Anti-Reset Mandate
- **Context:** Concurrent operations involving multiple IDEs (Antigravity IDE, VS Code, Claude Code) or autonomous subagents.
- **Mandate:** Agents are STRICTLY FORBIDDEN from executing `git reset --hard`, `git checkout .`, or switching branches directly on the primary workspace root (`D:\GOOGLE ANTIGRAVITY`).
- **Actionable Execution:**
  1. Any experimental branch switching or subagent workspace isolation MUST use dedicated git worktrees (`git worktree add ../.worktrees/<branch-name>`).
  2. **Durability before handoff.** No agent may end a turn or delegate with unflushed work. How that obligation is discharged depends on the lane:
     - **The git-owning lane** stages and commits new code files and rules before ending a turn.
     - **Every other lane** writes all content to disk with a native file tool (never held in context alone), then issues an explicit handoff to the git-owning lane naming the exact paths it created or modified.

     A non-git lane MUST NOT run `git add`, `git commit`, or any other git write to satisfy this rule; doing so is an R38 lane violation, not compliance with R40. Unflushed context is the wipeout risk R40 exists to prevent — an uncommitted file on disk survives a branch update in another worktree; a file that exists only in an agent's context does not.

     *Amended from the original single-clause form, which bound every agent to a git action only one lane can legally take — every non-git lane was structurally forced to violate either this clause or R38 on any turn that created a file. See commit acf69674 for the trigger (the proposal file was removed after merge, per R49).*

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

## R43. Inter-Session Peer Agent Messaging & State Synchronization
- **Context:** Concurrent coordination between multiple top-level sessions or subagents.
- **Mandate:** Agents MUST communicate with peer agents exclusively via the `send_message` tool using the peer's conversation ID. Never output peer agent responses into the user-facing chat text.
- **Handoff Contract:** Synchronization messages MUST transmit:
  1. Active git branch name and latest commit SHA.
  2. Canonical filesystem boundaries (`D:\GOOGLE ANTIGRAVITY`, `D:\AI_Platform`).
  3. Active daemon ports and interfaces (e.g. FastAPI on 8000, Vite on 5173).
  4. Reproducible test and benchmark commands (`pytest`, `benchmark_harness`).

## R44. Anti-Destructive Live Directory Deletion Guardrail (Agent Suicide Prevention)
- **Context:** Cleaning disk caches or migrating active application data directories on `C:\`.
- **Mandate:** Agents are STRICTLY FORBIDDEN from deleting, replacing with NTFS junctions (`mklink /J`), or wiping runtime directories (`C:\Users\<user>\.gemini\antigravity`, active IDE profiles, or running session logs) while tools, agents, or IDE processes are executing.
- **Actionable Execution:** 
  1. Deleting active brain directories tears open file descriptors and causes catastrophic session crashes.
  2. Storage migration MUST use native environment variable redirection (`$env:ANTIGRAVITY_APP_DATA`, `--extensions-dir`) prior to process launch.
  3. Cleanups of C: drive directories must be executed only when processes are completely terminated.

## R45. Monolithic Canonical Workspace & Anti-In-Tree Split Mandate
- **Context:** Restructuring repository architecture or separating domain concerns.
- **Mandate:** Agents are STRICTLY FORBIDDEN from creating nested `.git` repositories, in-tree project splits (e.g. `Antigravity_OS`, `Antigravity_Media`), or internal directory junctions inside the canonical root (`D:\GOOGLE ANTIGRAVITY`).
- **Actionable Execution:** 
  1. Maintain `D:\GOOGLE ANTIGRAVITY` as the sole canonical repository root.
  2. Domain isolation MUST use established top-level track directories (`/apps`, `/content_creation`, `/sports_cards`, `/travel_and_life`).
  3. Experimental branches must use external git worktrees (`git worktree add ../.worktrees/<name>`), never internal sub-repos.

## R46. "Measure, Do Not Recall" Ground Truth Guardrail
- **Context:** Cross-agent handoffs, status assessments, branch assertions, and defect reports.
- **Mandate:** Agents MUST NOT accept another agent's chat transcripts or self-reported status as physical ground truth.
- **Actionable Execution:** 
  1. Always re-measure the physical disk state via tools (`git status`, `find_by_name`, `view_file`) before making architectural assertions or edits.
  2. Every bug or defect report must state the concrete trigger and reproducible state (`input/state -> wrong output/crash`). Speculative or purely stylistic critiques are prohibited.


## R47. The Triad Cognitive Pipeline (Model Orchestration)
- **Context:** Designing multi-stage autonomous workflows or research validation loops.
- **Mandate:** Agents MUST NOT route complex multi-stage tasks to a single monolithic model. Workflows MUST be decomposed to leverage specific model cognitive strengths:
  1. **The Harvester (Gemini Flash):** High-speed, large-context extraction and fluff-filtering (Disk offloading only).
  2. **The Scientist (Gemini Pro):** Deep logical reasoning, feasibility testing, and deterministic Red Phase Pytest gates.
  3. **The Architect (Claude Opus):** Terminal-triggered execution (claude -p) for top-tier software engineering, idiomatic repository integration, and SKILL.md authorship.
- **Actionable Execution:** Use define_subagent and run_command (for claude) to orchestrate these handoffs. Never rely on Flash to write production code, and never waste Opus compute on raw data parsing.


## R48. Claude Code CLI Boundary Traversal
- **Context:** Delegating implementation tasks to Claude Code via the terminal that require reading external contexts (e.g., blueprints, dossiers, or scratch files located in D:\AI_Platform).
- **Mandate:** Agents MUST NOT assume Claude Code can autonomously break out of its D:\GOOGLE ANTIGRAVITY sandbox to read external files. By default, Claude Code will hard-block reads to sibling or parent directories.
- **Actionable Execution:** When triggering Claude Code to process an external file, the invoking agent MUST grant explicit boundary access using the `--add-dir` flag, and MUST pass the prompt with `-p` / `--print` (there is no `-m` option; `--model` selects a model, not a prompt).
  - *Example:* `claude --add-dir "D:\AI_Platform\scratch\claims" -p "Implement the blueprint at D:\AI_Platform\scratch\claims\file.md"`
  - *Alternative:* pipe the file in and let the sandbox stay closed — `cat "D:\AI_Platform\scratch\claims\file.md" | claude -p "Implement this blueprint."` — which needs no `--add-dir` because no read crosses the boundary. This is the safer default, not merely equivalent: `--add-dir` widens the sandbox for the whole session, while piping grants nothing.
  - Verify before relying on either form: `claude --help` is the source of truth for flags on this machine.
  - *Amended: the original examples used `-m`, which does not exist as a Claude Code CLI flag. See commit acf69674 for the trigger (the proposal file was removed after merge, per R49).*

## R49. Rule Amendment & Number Ownership Protocol
- **Context:** Correcting, narrowing, or superseding a rule that is already numbered and in force — as opposed to contributing a new one, which `rules/proposed/README.md` already covers.
- **Mandate:** Agents are STRICTLY FORBIDDEN from editing a numbered rule's text in place to change its meaning, from reusing a number that is already in force for a different mandate, and from renumbering or deleting another agent's rule. A rule number is a permanent, single-meaning identifier: every citation of a number across sessions, skills, and commit messages must resolve to one mandate.
- **Actionable Execution:**
  1. Write an amendment file in `rules/proposed/` named `R<number>_<slug>.md` with frontmatter `type: amendment` and `amends: R<number>`. State the defect, the concrete trigger that exposed it, and the exact replacement text.
  2. A new rule uses frontmatter `type: new` and `proposal: R<number>`, where the number is free per this file.
  3. The git-owning session merges the amendment into the canonical numbered file, preserving the number. Superseded text is replaced, not deleted silently — the amendment file in `rules/proposed/` (or its git history once merged) is the record.
  4. Never renumber a rule to resolve a collision in someone else's file. Record the collision in `.githooks/rule-collisions.allow` and open an amendment against the file you own.
