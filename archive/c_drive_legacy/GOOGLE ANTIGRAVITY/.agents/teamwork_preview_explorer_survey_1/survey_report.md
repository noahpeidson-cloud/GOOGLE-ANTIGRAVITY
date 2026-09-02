# Antigravity Workspace Survey & Directory-Scoped Rule Isolation Report

**Author:** teamwork_preview_explorer_survey_1  
**Target:** G:\My Drive\GOOGLE ANTIGRAVITY  
**Date:** 2026-08-21T23:38:30Z  
**Status:** Completed  

---

## 1. Executive Summary

This report delivers a comprehensive forensic survey of the `G:\My Drive\GOOGLE ANTIGRAVITY` workspace, evaluates Antigravity's customization discovery and rule resolution engine, and establishes the architectural specification for **Directory-Scoped Rule Isolation (R1)** and **Root Routing & Anti-Drift Harness**.

### Core Discoveries:
1. **Unscoped Global Rules in Workspace Root:** Currently, `.agents/rules/sports_cards_schema.md` and `.agents/rules/content_creation_standards.md` reside under `.agents/rules/`. In the Antigravity engine, rules in `.agents/rules/` are loaded at the workspace project level. This creates massive cross-track context leakage: 21-variable sports card database schemas and Card Ladder rules pollute media editing sessions, while FFmpeg audio LUFS filters pollute card ingestion ETL sessions.
2. **Missing Subdirectory Trees:** Target production directories `/apps`, `/content_creation`, and `/sports_cards` do not yet exist on disk.
3. **Root `GEMINI.md` Needs Complete Harness Architecture:** The existing root `GEMINI.md` declares Noah Eidson's persona and lists the two hobbies, but lacks directory routing directives, the Ambiguity Circuit Breaker (`/grill-me` protocol), the Workflow Distillation trigger (`workflow-skill-creator`), and the mandatory Confidence Metric ("I Don't Know" policy).
4. **Antigravity Rule Resolution Mechanics:** Antigravity natively resolves `GEMINI.md` hierarchically by traversing from the Current Working Directory (CWD) up to the workspace root. Placing localized `GEMINI.md` files inside `/apps`, `/content_creation`, and `/sports_cards` provides deterministic physical context isolation without token waste.

---

## 2. Complete Workspace Inventory & Topology

### 2.1 File System Map
```
G:\My Drive\GOOGLE ANTIGRAVITY\
├── GEMINI.md                                    [Root Steering Manifest & Persona - 1,232 bytes]
├── credentials.json                             [OAuth / Service Credentials - 432 bytes]
└── .agents/                                     [Agent Coordination & Rule Metadata]
    ├── ORIGINAL_REQUEST.md                      [Task Definition & Requirements - 2,438 bytes]
    ├── rules/
    │   ├── sports_cards_schema.md               [Legacy 21-Variable Schema - 1,994 bytes]
    │   └── content_creation_standards.md        [Legacy FFmpeg Transcoding Standards - 1,254 bytes]
    ├── sentinel/
    │   └── BRIEFING.md                          [Sentinel Safety Monitor State - 1,241 bytes]
    ├── orchestrator_1/
    │   ├── DISPATCH.md                          [Orchestrator Inbound Dispatch - 1,924 bytes]
    │   ├── BRIEFING.md                          [Orchestrator Working Memory & Plan - 3,832 bytes]
    │   └── progress.md                          [Orchestrator Liveness Log - 520 bytes]
    ├── teamwork_preview_explorer_survey_1/      [Survey 1: Workspace & Directory Survey]
    │   ├── DISPATCH.md
    │   ├── BRIEFING.md
    │   ├── progress.md
    │   ├── survey_report.md                     [This Document]
    │   └── handoff.md
    ├── teamwork_preview_explorer_survey_2/      [Survey 2: Mechanisms & Specs Analysis]
    └── teamwork_preview_explorer_survey_3/      [Survey 3: Industry Standards & Adversarial Eval]
```

### 2.2 Target Topology (To Be Implemented)
```
G:\My Drive\GOOGLE ANTIGRAVITY\
├── GEMINI.md                                    [REFACTORED: Global Router, /grill-me, Confidence, Distillation]
├── credentials.json
├── apps/                                        [NEW: General Software & Automation Track]
│   └── GEMINI.md                                [NEW: Streamlit, SQLite, Python App Engineering Rules]
├── content_creation/                            [NEW: Media Engineering Track]
│   └── GEMINI.md                                [NEW: FFmpeg, Denoising, LUFS Normalization, 9:16 Re-framing]
├── sports_cards/                                [NEW: Sports Cards Track]
│   └── GEMINI.md                                [NEW: 21-Variable Ingestion, Relational Keys, Card Ladder ETL]
└── .agents/
    └── [Metadata, team coordination, skills runbooks only]
```

---

## 3. Antigravity Customization & Rule Resolution Mechanics

Based on the official Antigravity customization specification (`agy-customizations` and `antigravity-guide`):

### 3.1 Rule Discovery Hierarchy & Precedence
When an agent inspects, edits, or operates within a directory path (or CWD), the Antigravity engine dynamically constructs the prompt context through hierarchical path walking:

```
[Level 1: Local CWD Rule]       <CWD>/GEMINI.md (Highest priority directory override)
           ↑
[Level 2: Parent Directories]   Walks upward directory by directory towards root
           ↑
[Level 3: Root Workspace Rule]  G:\My Drive\GOOGLE ANTIGRAVITY\GEMINI.md (Global router & harness)
           ↑
[Level 4: Workspace Meta]       .agents/rules/ (Workspace-level declarations)
           ↑
[Level 5: Global Machine]       ~/.gemini/config/ (User-wide configurations)
           ↑
[Level 6: Built-in Defaults]    Antigravity system built-ins
```

### 3.2 Progressive Disclosure & Context Isolation Principle
1. **Physical Isolation:** When an agent is working in `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation`, Antigravity loads:
   - `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\GEMINI.md`
   - `G:\My Drive\GOOGLE ANTIGRAVITY\GEMINI.md`
   It does **not** load `sports_cards/GEMINI.md` or `apps/GEMINI.md`.
2. **Token Efficiency & Context Caching:** Root `GEMINI.md` serves as a stable, static prefix (optimally cached by Gemini Context Caching). Localized `GEMINI.md` files inject domain-specific instructions only when the agent enters that directory scope.
3. **Deduplication:** Antigravity deduplicates rules by resolved canonical file paths.

---

## 4. Cross-Domain Interference Analysis & Risk Assessment

### 4.1 The Contamination Problem
In Noah Eidson's workspace, the two primary hobbies represent completely disparate technical domains:
- **Track 1: Sports Cards** requires strict tabular relational integrity, 21 exact CSV column headers, rigid categorical enumerations (`[Basketball, Baseball, ... Flesh and Blood]`), OCR sold price heuristics, and 500-card batch rollover limits.
- **Track 2: Content Creation** requires signal processing, spatio-temporal video filtering (`hqdn3d`, `nlmeans`), two-pass audio loudness normalization (`loudnorm=I=-14:LRA=7:TP=-1.5`), FFmpeg filter graphs, and vertical 9:16 portrait transcoding.
- **Track 3: Apps** requires clean Python software architecture, Streamlit UI components, SQLite transaction safety, and minimal dependencies.

### 4.2 Failure Modes of Legacy Layout
If rules remain in `.agents/rules/` or are combined in root `GEMINI.md`:
- **Prompt Bloat:** Agents working on a quick video transcoding script waste 2,000+ tokens on sports card categories and Card Ladder IDs.
- **Hallucinatory Transposition:** An LLM writing an automation script for sports cards might attempt to apply FFmpeg audio normalization or video codecs to image parsing routines, or vice-versa.
- **Schema Violations:** Ambiguity over which domain rules apply leads to dropped schema columns or incorrect file naming.

---

## 5. Directory-Scoped Rule Isolation Architecture

### 5.1 Root `GEMINI.md` (Global Router & Harness Manifest)
The root `GEMINI.md` must act as the **Immutable Core Kernel**. It must never contain track-specific schemas or transcode parameters. Instead, it must define:
1. **Core Directives & Developer Persona:** Noah Eidson (Phoenix, MST), Builder-First, direct & concise, omit boilerplate.
2. **Directory-Scoped Routing Protocol (R1):**
   - Directs all sports card work to `/sports_cards/`.
   - Directs all media/video/audio engineering work to `/content_creation/`.
   - Directs all general software, dashboards, and tooling to `/apps/`.
   - Strict prohibition against cross-domain execution or rule mixing.
3. **Ambiguity Circuit Breaker (`/grill-me`) (R2):**
   - Mandatory trigger: If any request lacks technical architecture, explicit data inputs/outputs, or clear acceptance criteria, HALT immediately and output interactive multiple-choice questions.
4. **Workflow Distillation Protocol (R3):**
   - Proactively recommend converting novel multi-step task completions into permanent `.agents/skills/<name>/SKILL.md` using `workflow-skill-creator`.
5. **The Confidence Mechanism ("I Don't Know" Policy) (R4):**
   - Mandatory bottom output block: `<confidence_metric>High | Medium | Low</confidence_metric>`.
   - If confidence is `< High`, explicitly output "I don't know," halt execution, and request clarifying input.
6. **Anti-Drift Guardrails & Whitelisted Tooling:**
   - 3-Attempt Circuit Breaker.
   - Approved tools: `pandas`, `streamlit`, `sqlite3`, `ffmpeg`. No unapproved dependencies.
7. **Industry AI Engineering Standards (Anthropic/OpenAI/Gemini):**
   - Anthropic: Place core constraints at prompt boundary/bottom; use `<system>`, `<scratchpad>`, `<harness>` XML structures.
   - OpenAI: Enforce task decomposition and strict permanent system role separation.
   - Gemini: Optimize for static prompt caching.

### 5.2 Track 1: `G:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\GEMINI.md`
- **Scope:** CSV batch ingestion, Card Ladder ETL, OCR price indexing, secondary market analytics.
- **Directives:**
  - Relational Key Architecture: Parent Image ID (4-digit int, e.g. `8492`, never recycled), Child Card ID (3-digit suffix, e.g. `8492-105`), Tracking Field (`[Parent_Image_ID]-[Child_Card_ID]` in Col 15 `Notes`), File Naming (`CardScan-[YYYYMMDD]-[Parent_Image_ID].jpg`).
  - Strict 21-Variable Ingestion Schema (Columns 1-21 exact order and formats).
  - Exact Category Enumeration (22 permitted categories).
  - 500-Card Batch Rollover Circuit Breaker.
  - Zero-media-pollution isolation.

### 5.3 Track 2: `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\GEMINI.md`
- **Scope:** High-performance media engineering, mobile concert/festival footage, 9:16 vertical re-framing.
- **Directives:**
  - Transcoding Standard: Container MP4, Video Codec H.265/HEVC or AV1 (HW accelerated), Resolution 1080x1920 (9:16), Bitrate 15-20 Mbps VBR (25 Mbps max), Audio AAC-LC 320 kbps, 48 kHz stereo.
  - Non-Destructive Filtering: Spatio-temporal denoising (`hqdn3d`/`nlmeans`), highlight preservation (avoid crushing blacks/blowing highlights), audio normalization (two-pass dynamic `loudnorm=I=-14:LRA=7:TP=-1.5`, high-pass bass cutoff).
  - Verification Protocol: Run sample -> test visual in Chromium -> test audio LUFS with `ffmpeg -i out.mp4 -af ebur128=peak=true -f null -`.
  - Zero-sports-card-pollution isolation.

### 5.4 Track 3: `G:\My Drive\GOOGLE ANTIGRAVITY\apps\GEMINI.md`
- **Scope:** Software engineering, Streamlit web apps, SQLite transactional databases, data tools.
- **Directives:**
  - Architectural Standards: Modular Python, clean function boundaries, type annotations, decoupled UI and logic.
  - Tooling Discipline: Streamlit + SQLite3 + Pandas. No unapproved external dependencies.
  - Resilience & Logging: Comprehensive error catching, structured logging, graceful degradation.
  - Zero-hobby-pollution isolation.

---

## 6. Implementation & Migration Action Plan

To transition the workspace from current state to target isolated state:

| Step | Action | Target Location | Responsible Role |
|------|--------|-----------------|------------------|
| 1 | Create target directory structure | `/apps`, `/content_creation`, `/sports_cards` | Implementation Worker |
| 2 | Author isolated directory rules | `/apps/GEMINI.md`, `/content_creation/GEMINI.md`, `/sports_cards/GEMINI.md` | Implementation Worker |
| 3 | Refactor Root `GEMINI.md` | `G:\My Drive\GOOGLE ANTIGRAVITY\GEMINI.md` | Implementation Worker |
| 4 | Clean up legacy unisolated rules | Archive or remove `.agents/rules/*.md` to prevent global contamination | Implementation Worker |
| 5 | Verify Rule Discovery & Isolation | Forensic Inspection & Verification | Forensic Auditor / Reviewer |
| 6 | Adversarial Evaluation | Execute `/grill-me`, Confidence, and Ambiguity test cases | Adversarial Judge |

---

## 7. Verification Method

Downstream agents and reviewers can independently verify this survey and design using:
1. **File System Verification:**
   ```powershell
   Get-ChildItem -Path "G:\My Drive\GOOGLE ANTIGRAVITY" -Recurse -Depth 2
   ```
2. **Rule Isolation Verification:**
   Ensure each directory contains its own `GEMINI.md` and that root `GEMINI.md` contains strict routing pointers.
3. **Context Leakage Check:**
   Confirm that `sports_cards/GEMINI.md` contains zero references to FFmpeg/LUFS, and `content_creation/GEMINI.md` contains zero references to Card Ladder / 21-variable schemas.

