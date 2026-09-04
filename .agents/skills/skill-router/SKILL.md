---
name: skill-router
description: >-
  Master Natural Language Skill & Agent Router. Intelligently maps user requests,
  intent phrases, and multi-step pipeline goals directly to the exact skills,
  custom agents, and tool chains across the workspace. Trigger phrases: "Router,",
  "route this to", "which skill should I use", "what agent handles", "dispatch to",
  "skill router", "map this request". Activates context-aware fingerprint evaluation
  to resolve ambiguous multi-domain requests before loading any skill body.
license: Complete terms in LICENSE.txt
---

# Master Natural Language Skill Router

## Overview
This routing engine maps natural language user queries and workflow intents to the optimal domain skills and custom agents in Antigravity. It eliminates guesswork and prevents loading bloated, unnecessary context.

---

## Context Fingerprint (Pre-Routing Evaluation)

Before consulting the routing table, perform a lightweight context evaluation (~150 tokens):

1. **Active track** — What directory is the conversation focused on? (`/content_creation`, `/sports_cards`, `/apps`, `/infrastructure`)
2. **Last 3 user intent tokens** — What are the dominant nouns/verbs? (e.g., "video render proxy", "card valuation CSV", "memory benchmark")
3. **Open file extension** — Any `.py`, `.tsx`, `.sql`, `.resolve` file recently referenced?

**Disambiguation rule**: Only invoke the R14 `ask_question` modal when the fingerprint produces **≥2 candidate skills with equal confidence**. Single-match results route immediately without a modal. This prevents friction on unambiguous requests.

---

## Intent Routing Decision Table

| User Natural Language Query / Keywords | Target Skill(s) | Assigned Custom Agent | Target Directory | ⚠️ Rule Risk |
| :--- | :--- | :--- | :--- | :--- |
| *"Process video"*, *"render reel"*, *"transcode clip"*, *"festival footage"*, *"export 9:16 master"* | `omnichannel-media-pipeline` | `media-engineer` | `/content_creation` | — |
| *"Normalize audio"*, *"-14 LUFS"*, *"fix bass distortion"*, *"highpass filter"*, *"generate proxy"*, *"NVENC transcode"* | `ffmpeg-audio-mastering` | `media-engineer` | `/content_creation` | — |
| *"DaVinci Resolve"*, *"create timeline"*, *"add cut markers"*, *"render queue export"*, *"Resolve script"* | `davinci-resolve-automation` | `media-engineer` | `/content_creation` | — |
| *"Split this memo"*, *"write scripts"*, *"TikTok script"*, *"YouTube Shorts outline"*, *"content package"* | `omnichannel-content-splitter` | `media-engineer` | `/content_creation` | — |
| *"Card valuation"*, *"Card Ladder CSV"*, *"sports cards inventory"*, *"PSA/BGS grading"*, *"raw card checklist"* | `card-valuation-hub` | `sports-analyst` | `/sports_cards` | — |
| *"Build UI"*, *"dashboard design"*, *"Streamlit app"*, *"React component"*, *"style dashboard"*, *"fix layout"* | `frontend-design`, `building-data-apps` | `app-builder` | `/apps` | R1 Ghost Backend — verify backend exists before any POST route |
| *"Audit security"*, *"check CORS"*, *"token validation"*, *"SQL injection check"*, *"data loss review"* | `security-auditor` (agent), `accidental-data-loss-prevention` | `security-auditor` | All tracks | — |
| *"Performance review"*, *"fix LCP"*, *"slow database query"*, *"SQLite WAL index"*, *"DOM memory leak"* | `performance-auditor` (agent) | `performance-auditor` | All tracks | — |
| *"Stress test"*, *"adversarial edge cases"*, *"fuzz test"*, *"break this code"*, *"write loud test suite"* | `challenger-qa` (agent) | `challenger-qa` | All tracks | — |
| *"Ask me questions first"*, *"grill me"*, *"clarify requirements before building"*, *"plan feature"* | `grill-me` | `architect` | Workspace root | — |
| *"Validate research"*, *"test AI concept"*, *"evaluate paper"*, *"notebook review"*, *"feasibility gate"* | `curated-memory`, `workflow-skill-creator` | `research-validation-triad` | `/infrastructure` | — |
| *"GitKraken audit"*, *"review PR"*, *"diff audit"*, *"branch review"*, *"swarm review"* | `gitkraken-swarm-review` | `code-reviewer` | Workspace root | — |
| *"Benchmark"*, *"effectiveness score"*, *"ecosystem health"*, *"run harness"*, *"skill telemetry"* | `curated-memory` | `research-validation-triad` | `/infrastructure` | R2 — benchmark harness is sole writer for telemetry; executor must not self-certify |

---

## Multi-Step Composite Pipelines

### 1. The Full Concert-to-Social Workflow
- **Trigger**: *"I just dropped new concert footage in the inbox, turn it into short-form content."*
- **Execution Chain**:
  1. `omnichannel-media-pipeline` (Inspect file, verify hash, load into `01_RAW_INBOX/`).
  2. `ffmpeg-audio-mastering` (Analyze audio, apply 80Hz high-pass, normalize to -14 LUFS, render NVENC 1080x1920 9:16 + 720p web proxy).
  3. `omnichannel-content-splitter` (Generate synchronized YouTube Shorts, TikTok, and Snapchat caption copy).
  4. Move master to `03_READY_TO_POST/` with sidecar metadata JSON.

### 2. The Fullstack Dashboard Feature Pipeline
- **Trigger**: *"Build a new real-time queue monitor dashboard for our media pipeline."*
- **Execution Chain**:
  1. `frontend-design` (Establish Dark Cybernetic Cockpit tokens: Obsidian ground `#080A0E`, Cyan accent `#00F0FF`, tabular metrics).
  2. `app-builder` (Implement React / Streamlit frontend with zero detached DOM nodes and virtualized list).
  3. ⚠️ **Ghost Backend Checkpoint** (R1): Verify FastAPI/Flask backend is running before any POST route is wired.
  4. `performance-auditor` (Verify sub-2.0s LCP).
  5. `security-auditor` (Verify loopback-only binding and sanitized endpoints).

### 3. The Research Validation & Memory Pipeline
- **Trigger**: *"Validate this AI concept and record the findings into curated memory."*
- **Execution Chain**:
  1. `curated-memory` (Query active dossier for domain track to avoid re-researching known facts).
  2. `research-validation-triad` (Run empirical gate: hypothesis → test → SHA-256 signed result).
  3. CuratedMemoryHub `.record()` (Write validated finding with importance score ≥ 7, `relationship_type="replaces"` for superseded records).
  4. `benchmark_harness` (Benchmark harness writes telemetry result — executor must not self-write).

---

## How to Invoke via Natural Language

When prompting in Antigravity or Copilot, you can speak naturally:
- *"Router, process the incoming video take and generate web proxies."*
- *"Router, create a full release package from this voice note."*
- *"Router, audit our local daemon security and database query performance."*
- *"Router, which skill handles DaVinci Resolve timeline creation?"*
- *"Route this to the right agent — I need to validate an AI research concept."*
- *"Dispatch this card checklist to the correct pipeline."*

---

## Killed Concepts (Permanently Closed)

> [!WARNING]
> The following architectural proposals were **adversarially reviewed and killed** on 2026-09-03. Do not re-implement without a new platform capability to support them.
>
> - **DAG Pipeline Contracts** (`consumes`/`produces` frontmatter keys): Custom frontmatter is not surfaced at routing time per the Antigravity progressive disclosure model. Prose pipeline chains above are the correct solution.
> - **Context-Hydrated Dynamic Skills**: Introduces a prompt injection attack surface via raw SQLite value injection into system prompts. No viable safe implementation path exists.
| *"Isolate agent"*, *"worktree setup"*, *"prevent index lock"*, *"split brain"*, *"concurrent coding"* | git-worktree-isolation | rchitect | /infrastructure |
