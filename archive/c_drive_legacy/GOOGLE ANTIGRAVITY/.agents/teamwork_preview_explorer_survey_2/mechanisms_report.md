# Antigravity AI Harness: Mechanisms and Specifications Report
**Document Version:** 1.0.0  
**Author:** teamwork_preview_explorer_survey_2  
**Date:** 2026-08-21  
**Target System:** Google Antigravity Agent Runtime  
**Workspace:** G:\My Drive\GOOGLE ANTIGRAVITY

---

## Executive Summary

The Antigravity AI Harness is a deterministic, multi-tiered engineering harness designed to eliminate context drift, prevent hallucinations, and guarantee specification-driven execution across complex, multi-domain developer workflows.

Noah maintains two active, concurrent, and equal hobby domains:
1. **Sports Cards:** A structured, strict-taxonomy ecosystem involving Card Ladder ETL pipelines, bulk CSV ingestion, OCR tracking, and a 21-variable schema.
2. **Content Creation:** A high-fidelity media engineering pipeline involving low-light video denoising, audio de-clipping, vertical 9:16 re-framing, and LUFS compliance via FFmpeg.

This report establishes the technical specifications, exact rule formats, trigger conditions, interactive templates, and execution flows for the four core harness mechanisms:
- **R1: Directory-Scoped Rule Isolation** (Localized GEMINI.md hierarchy and root manifest routing).
- **R2: Ambiguity Circuit Breaker (/grill-me protocol)** (Interactive multi-choice interrogation upon underspecification).
- **R3: Workflow Distillation** (Proactive triggering of workflow-skill-creator to produce permanent SKILL.md runbooks).
- **R4: The Confidence Mechanism ("I Don't Know" Policy)** (Mandatory bottom-appended confidence metrics with mechanical halting for non-HIGH confidence).

---

## Technical Alignment with Industry AI Standards

| Standard / Authority | Mechanism Alignment | Implementation in Antigravity |
| :--- | :--- | :--- |
| **Anthropic Standards** | Bottom placement of critical constraints; strict XML tag encapsulation (<system>, <scratchpad>, <confidence>, <grill_me>). | Confidence metrics and circuit breaker constraints placed at the terminal anchor of prompts and system directives; structured XML scratchpads for pre-execution evaluation. |
| **OpenAI Standards** | Task decomposition, multi-step chaining, strict phase-gated execution, and permanent system-role steering. | Clear separation between system manifest (GEMINI.md), execution state machines, and progressive multi-phase interactive workflows (/grill-me and workflow-skill-creator). |
| **Gemini Standards** | Context Caching for immutable steering rules; progressive disclosure of rules and skills to prevent context window pollution. | Root GEMINI.md serves as a cached global manifest; domain schemas reside in localized subdirectory GEMINI.md files discovered on-demand during directory traversal. |

---

## 1. R1: Directory-Scoped Rule Isolation

### 1.1 Problem Statement & Drift Vectors
When multi-domain rules are aggregated into a monolithic root configuration, the agent experiences:
- **Context Bloat:** Unnecessary token consumption on every turn regardless of the active task.
- **Rule Leakage / Cross-Contamination:** Sports card taxonomy rules inadvertently influencing media processing scripts, or video transcoding constraints interfering with data ETL.
- **Attention Degradation:** Reduced adherence to strict validation schemas due to competing instructions.

### 1.2 Antigravity Customization Discovery & Inheritance Architecture
Antigravity discovers rules through upward directory traversal:
1. When an agent opens, edits, or operates within a file in a subdirectory (e.g., G:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\scripts\ingest.py), the runtime walks up from sports_cards/scripts/ to sports_cards/ and loads sports_cards/GEMINI.md.
2. The runtime continues up to G:\My Drive\GOOGLE ANTIGRAVITY\ and loads the root GEMINI.md.
3. Rules are merged with hierarchical precedence: local directory rules take priority for localized actions, while global directives govern general behavior.
4. Rules are deduplicated by canonical file path, ensuring zero redundant token injection.

### 1.3 Target Directory Hierarchy
`	ext
G:\My Drive\GOOGLE ANTIGRAVITY\
├── GEMINI.md                               <-- Global Steering, Router Manifest & Harness Directives
├── sports_cards\
│   ├── GEMINI.md                           <-- Localized Sports Cards Schema & ETL Rules
│   ├── data\
│   │   └── staging\
│   └── scripts\
│       └── ingest_ladder.py
├── content_creation\
│   ├── GEMINI.md                           <-- Localized Media Transcoding & FFmpeg Standards
│   ├── raw\
│   ├── exports\
│   └── scripts\
│       └── transcode_vertical.py
└── apps\
    ├── GEMINI.md                           <-- Localized Application Architecture & Dev Standards
    └── src\
`

### 1.4 Exact Rule Formats & File Specifications

#### A. Root Manifest & Router (G:\My Drive\GOOGLE ANTIGRAVITY\GEMINI.md)
`markdown
# Antigravity Global Steering & Workspace Manifest

## Core Directives & Developer Persona
- **Developer:** Noah Eidson (America/Phoenix, MST)
- **Identity:** Technical builder, automation architect, "Builder-First" mindset.
- **Communication:** Direct, technical, and concise. Omit all boilerplate.

## Hobbies & Active Tracks (Equal & Concurrent)
Noah maintains two SEPARATE, CONCURRENT, and EQUAL tracks:
1. **[HOBBY] Sports Cards:** Highly structured, strict-taxonomy ecosystem involving Card Ladder ETL pipelines, bulk CSV ingestion, and secondary market analytics.
2. **[HOBBY] Content Creation:** High-performance media engineering pipeline involving low-light video denoising, audio de-clipping, and vertical 9:16 re-framing for live music/festivals.

## Workspace Routing & Domain Boundaries
Domain-specific execution MUST take place within the designated directories to inherit localized rules:
- **Sports Cards Work:** Directory sports_cards/ (Governed by sports_cards/GEMINI.md)
- **Content Creation Work:** Directory content_creation/ (Governed by content_creation/GEMINI.md)
- **General Software/Apps:** Directory pps/ (Governed by pps/GEMINI.md)

Agents are STRICTLY FORBIDDEN from mixing domain taxonomies or creating sports card files in content creation directories and vice versa.

## Anti-Drift Guardrails (The Harness)
1. **Spec-Driven Adherence:** Refer to localized GEMINI.md files before executing any Python or pipeline automation.
2. **The 3-Attempt Circuit Breaker:** If an execution fails 3 times consecutively, stop immediately. Generate an error artifact and request review.
3. **Approved Tooling Only:** Stick strictly to pandas, streamlit, sqlite3, and fmpeg. No unapproved external dependencies.
4. **Ambiguity Circuit Breaker (/grill-me):** Trigger interactive interrogation upon any ambiguous requirement.
5. **Confidence Mechanism:** Mandatory bottom confidence metric. If != HIGH, state "I don't know", halt, and request clarification.
`

#### B. Sports Cards Localized Rules (G:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\GEMINI.md)
`markdown
# [HOBBY] Sports Cards Schema & Directives

## Relational Key Architecture (Strict Enforcement)
- **Parent Image ID:** 4-digit integer per physical photo file (e.g., 8492). MUST NEVER BE RECYCLED.
- **Child Card ID:** 3-digit suffix per distinct card (e.g., 8492-105).
- **Tracking Field:** [Parent_Image_ID]-[Child_Card_ID] written to Column 15 (Notes).
- **File Naming:** CardScan-[YYYYMMDD]-[Parent_Image_ID].jpg.

## The 21-Variable Ingestion Schema
You are STRICTLY FORBIDDEN from deviating from this structure or inventing categories:
1. **Date Purchased**: MM/DD/YYYY (Default to today)
2. **Quantity**: 1
3. **Player**: Full athlete/TCG character name
4. **Year**: 4-digit YYYY
5. **Set**: Manufacturer and release line
6. **Variation**: Aggressively guess visual foil/sheen. Leave blank ONLY for verified base cards.
7. **Number**: Printed card number
8. **Category**: MUST match one of: [Basketball, Baseball, Football, Hockey, Soccer, Tennis, Wrestling, Racing, Golf, Boxing, UFC/MMA, Pokemon, Magic, Metazoo, Yugioh, Fortnite, Dragonballz, Entertainment, Swimming, Softball, PopCulture, Flesh and Blood]
9. **Condition**: MUST BE EXACTLY 'Raw' for ungraded. For graded, use syntax without hyphens (e.g., PSA 10, BGS 9.5).
10. **Slab Serial #**: Graded cert number (Blank if Raw)
11. **Investment**:  .00
12. **Estimated Value**: OCR Last Sold price or  .00
13. **Ladder ID**: Blank
14. **Query**: [Year] [Set] [Player] [Variation] [Condition]. Negative exclusions (-BGS -SGC) are FORBIDDEN on 'Raw' cards.
15. **Notes**: [Parent_Image_ID]-[Child_Card_ID]
16. **Tags**: Blank
17. **Date Sold**: Blank
18. **Sold Price**: Blank
19. **Image**: Direct Drive URL
20. **Back Image**: Direct Drive URL or blank
21. **AI Status**: MUST be REVIEW VARIATION, NEEDS REVIEW, or CLEARED. Visually guessed variations MUST be flagged REVIEW VARIATION.

## 500-Card Batch Limit
- Halt processing if staging approaches 500 rows. Trigger batch export and rollover.
`

#### C. Content Creation Localized Rules (G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\GEMINI.md)
`markdown
# [HOBBY] Content Creation & Media Engineering Pipeline

## Operational Mandate
Process live music, festival, and concert mobile footage (often low-light HDR captures) into optimized, high-fidelity 9:16 vertical reels for social distribution.

## Technical Transcoding Standards (FFmpeg)
- **Container**: MP4
- **Video Codec**: H.265 / HEVC or AV1 (require hardware acceleration where available).
- **Resolution**: 1080x1920 (9:16 portrait) with intelligent subject-tracking offsets.
- **Video Bitrate**: 15–20 Mbps VBR (25 Mbps max).
- **Audio Codec**: AAC-LC at 320 kbps, 48 kHz stereo.

## Non-Destructive Filtering
- **Video Denoising**: Apply spatio-temporal low-light filtering (hqdn3d or 
lmeans).
- **Dynamic Range**: Preserve highlights in intense LED environments; do not crush sub-blacks.
- **Audio Normalization**: Apply two-pass dynamic normalization (loudnorm=I=-14:LRA=7:TP=-1.5) and high-pass filtering to eliminate clipping in bass-heavy environments.

## Verification Protocol
Before marking a media script complete, the agent MUST:
1. Process a sample raw video clip.
2. Verify visual integrity using the Antigravity Chromium player.
3. Validate audio LUFS compliance via FFmpeg analysis (fmpeg -i out.mp4 -af ebur128=peak=true -f null -).
`

### 1.5 Execution Flow for Directory-Scoped Isolation
`	ext
User Request Received
       │
       ▼
Determine Target Domain & Path (e.g. sports_cards/ vs content_creation/)
       │
       ├─► Operating in sports_cards/ ──► Runtime loads root GEMINI.md + sports_cards/GEMINI.md
       │                                  (Full 21-variable schema active; media rules isolated)
       │
       ├─► Operating in content_creation/ ─► Runtime loads root GEMINI.md + content_creation/GEMINI.md
       │                                     (FFmpeg transcoding active; card schema isolated)
       │
       └─► Root Operation ─────────────► Runtime loads root GEMINI.md only (Router manifest)
`

---

## 2. R2: Ambiguity Circuit Breaker (/grill-me Protocol)

### 2.1 Problem Statement & Trigger Rationale
When a user prompt lacks essential technical specifications (e.g., "Build an app to manage my cards", "Transcode my videos", "Optimize the database"), an unharnessed LLM makes uncontrolled assumptions, generating code with arbitrary dependencies, unaligned architectures, and phantom schemas.

The /grill-me protocol creates an impenetrable gate: **no implementation code or file modification is permitted until all architectural ambiguities are resolved via interactive multiple-choice interrogation.**

### 2.2 Ambiguity Trigger Predicates
The Ambiguity Circuit Breaker MUST trip whenever ANY of the following conditions are met:
1. **Underspecified Architecture Stack:** Missing frontend framework, storage engine, or deployment target when creating new software.
2. **Missing Ingestion / Schema Contract:** Undefined column formats, missing primary keys, or unstated data sources.
3. **Ambiguous Media Parameters:** Incomplete audio/video bitrate, unknown source aspect ratios, or unstated filter requirements.
4. **Vague Business Logic:** Branching choices with significant performance or data-retention trade-offs.
5. **High-Impact / Destructive Operations:** Batch updates, schema migrations, or file overwrites without explicit scope boundaries.

### 2.3 Execution Flow & State Machine

`	ext
[ Incoming User Prompt ]
          │
          ▼
<scratchpad>
Evaluate Prompt Completeness against Architecture Checklist:
1. Target Directory & Domain identified? (Yes/No)
2. Architecture / Stack defined? (Yes/No)
3. Schema & Data Contracts clear? (Yes/No)
4. Execution constraints / flags specified? (Yes/No)
</scratchpad>
          │
          ├── [ Any "No" Detected ] ──► [ AMBIGUITY CIRCUIT BREAKER TRIPPED ]
          │                                     │
          │                                     ▼
          │                             [ HALT ALL CODE GENERATION ]
          │                                     │
          │                                     ▼
          │                             [ Emit /grill-me Interrogation Form ]
          │                                     │
          │                                     ▼
          │                             [ Await User Multi-Choice Input ]
          │                                     │
          │                                     ▼
          │                             [ Parse Answers & Reset Breaker ]
          │                                     │
          └── [ All "Yes" Verified ] ───────────┴──► [ Proceed to Execution ]
`

### 2.4 Exact /grill-me Interactive Interrogation Template

`markdown
<grill_me>
### ⚠️ AMBIGUITY CIRCUIT BREAKER TRIPPED
**Status:** Execution halted. The request is underspecified. Please resolve the following architectural decisions before code generation proceeds.

#### Question 1: [Core Architectural Decision]
*Context:* [Brief explanation of why this decision is required]
- **[A]** [Option 1: Recommended default / standard approach]
- **[B]** [Option 2: Alternative approach / specific trade-off]
- **[C]** [Option 3: Minimalist / lightweight approach]
- **[D]** Custom / Other (Please specify)

#### Question 2: [Data Storage & Schema Contract]
*Context:* [Brief explanation of data persistence options]
- **[A]** SQLite database with strict typing and foreign key constraints
- **[B]** Flat CSV / Pandas dataframe adhering to the 21-variable schema
- **[C]** In-memory ephemeral processing (no persistence)
- **[D]** Custom / Other (Please specify)

#### Question 3: [Execution Scope & Error Handling]
*Context:* [Operational boundary and failure tolerance]
- **[A]** Fail-fast with rollback on first error
- **[B]** Batch processing with dead-letter queue / error log artifact
- **[C]** Interactive step-by-step confirmation per item
- **[D]** Custom / Other (Please specify)

---
**How to reply:** Reply with your choices (e.g., 1A, 2B, 3A) or provide specific custom overrides.
</grill_me>
`

---

## 3. R3: Workflow Distillation Protocol

### 3.1 Problem Statement & Operational Objective
When an agent completes a complex, multi-step problem-solving sequence (e.g. debugging a subtle FFmpeg color matrix drift, engineering a custom ETL data repair script, or assembling a multi-tool pipeline), the procedure remains transient. 

Workflow Distillation mechanically detects conversational and technical breakthroughs, proactively offering to distill the sequence into a reusable Antigravity skill (SKILL.md) using the workflow-skill-creator engine.

### 3.2 Distillation Trigger Heuristics
The agent MUST evaluate post-task completion against the Distillation Heuristic:
- **Heuristic 1: Complexity Depth:** Task required $\ge 3$ distinct execution steps, subcommands, or non-trivial tool orchestrations.
- **Heuristic 2: Novelty & Custom Logic:** The procedure resolved a novel challenge or combined existing tools in a non-standard pipeline not covered by built-in skills.
- **Heuristic 3: Repeatability Value:** The task represents an operational pattern that will be executed regularly (e.g. monthly Card Ladder re-indexing, festival footage batch transcoding).

### 3.3 Skill Lifecycle Architecture (workflow-skill-creator Integration)

`	ext
[ Novel Task Successfully Completed ]
                  │
                  ▼
[ Distillation Heuristic Evaluation: Complexity >= 3, Novel == True, Reusable == True ]
                  │
                  ▼
[ Proactive Distillation Prompt Emitted to User ]
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
 [ User Declines ]    [ User Approves / Initiates ]
        │                   │
        ▼                   ▼
 [ Turn Complete ]    [ Phase 1: Brainstorming & Scope Discovery (5 Rounds) ]
                            │
                            ▼
                      [ Phase 2: Skill Design & Architecture Plan ]
                            │
                            ▼
                      [ Phase 3: Implementation ]
                            ├─► Generate .agents/skills/<skill_name>/SKILL.md
                            └─► (Optional) Generate CLI tool scripts (uv run compliant)
                            │
                            ▼
                      [ Phase 4: Validation & Runbook Registration ]
`

### 3.4 Proactive Suggestion Template

`markdown
---
### 💡 Workflow Distillation Suggestion
**Completed Procedure:** [Brief description of the novel multi-step workflow just executed]
**Distillation Assessment:** This multi-step process contains repeatable operational patterns suitable for encapsulation.

Would you like to distill this into a permanent Antigravity skill using workflow-skill-creator?
- **Proposed Skill Name:** [suggested-skill-name]
- **Target Location:** .agents/skills/[suggested-skill-name]/SKILL.md
- **Encapsulated Scope:** [List key subcommands, scripts, and validation steps]

*To proceed, reply with **"Distill workflow"** or provide custom naming/scoping parameters.*
---
`

### 3.5 SKILL.md Standard Format (Distilled Output Contract)
Every distilled skill must conform to the Antigravity Skill Specification:
`markdown
---
name: [skill-name]
description: >-
  [Precise description of skill capabilities, trigger conditions, and scope - max 1024 chars]
---

# [Skill Title]

## Overview
[Executive summary of workflow purpose and architecture]

## Dependencies
[Required tools, libraries, or parent skills e.g., ffmpeg, pandas, uv]

## Quick Start
[Minimal executable command or runbook invocation]

## Workflow & Step-by-Step Runbook
1. **Phase 1: Input Validation & Pre-Checks**
2. **Phase 2: Execution & Core Transformation**
3. **Phase 3: Output Verification & Quality Checks**

## Common Pitfalls & Anti-Patterns
- [Pitfall 1 and mitigation]
- [Pitfall 2 and mitigation]
`

---

## 4. R4: The Confidence Mechanism ("I Don't Know" Policy)

### 4.1 Problem Statement & Hallucination Elimination
In the absence of clear facts, missing files, or undefined schemas, standard LLMs attempt to predict the most statistically probable completion. This leads to subtle, high-cost errors (e.g. fabricated CSV headers, hallucinated API arguments, wrong ffmpeg filter flags).

The Confidence Mechanism enforces an absolute epistemic rule: **if confidence is not HIGH, the agent is mechanically barred from speculating, forced to state "I don't know", halt execution, and demand clarification.**

### 4.2 Confidence Metric Rubric

| Confidence Level | Definition & Grounding Requirements | Permitted Action |
| :--- | :--- | :--- |
| **HIGH** | **100% Grounded.** All source files, schemas, APIs, and parameters are directly verified via tools (iew_file, grep_search, un_command). Zero assumptions. Full certainty. | Full execution, implementation, code generation, and artifact delivery permitted. |
| **MEDIUM** | **Partially Grounded.** General pattern is known, but specific file paths, column names, library versions, or environment flags require inference or interpolation. | **FORBIDDEN from generating code.** Must state "I don't know", cite the missing variables, halt, and request confirmation. |
| **LOW** | **Ungrounded / Speculative.** Requirements are missing, conflicting, unverified, or based on uninspected external systems. | **FORBIDDEN from generating code.** Must state "I don't know", cite fundamental gaps, halt, and request input. |

### 4.3 Mandatory Confidence Block Specification (Anthropic Terminal Placement)
In strict accordance with Anthropic AI engineering guidelines, the Confidence Block MUST be positioned at the terminal anchor (the absolute bottom) of EVERY agent output.

#### Format Specification:
`markdown
---
<confidence>
**Confidence Level:** HIGH | MEDIUM | LOW
**Evidence Chain:**
- [Observation / Verification Step 1: e.g. Verified sports_cards/GEMINI.md lines 12-35]
- [Observation / Verification Step 2: e.g. Executed test command with exit code 0]
**Gaps / Assumptions:** [None for HIGH; exact missing evidence for MEDIUM/LOW]
</confidence>
`

### 4.4 Execution Behavior When Confidence is Not HIGH

When the agent evaluates its confidence as MEDIUM or LOW, the output MUST adhere strictly to the Halting Contract:

`markdown
# I don't know.

## Missing Context & Knowledge Gaps
I cannot proceed with code generation or file modifications because the following critical information is unverified or missing:
1. **[Specific Gap 1]**: [e.g., The exact CSV schema for staging file CardScan-20260821-8492.csv has not been inspected.]
2. **[Specific Gap 2]**: [e.g., Audio channel layout (stereo vs 5.1 surround) in source video aw/fest_clip.mp4 is unconfirmed.]

## Required Clarification / Verification
To reach HIGH confidence, please provide:
- [Item 1 or permission to run iew_file / un_command on specific paths]
- [Item 2]

---
<confidence>
**Confidence Level:** LOW
**Evidence Chain:**
- Prompt requested processing of est_clip.mp4
- Video file metadata has not yet been inspected with ffprobe
**Gaps / Assumptions:** Unknown codec, resolution, and audio sample rate
</confidence>
`

---

## 5. Cross-Mechanism Interplay & Lifecycle Matrix

### 5.1 Integrated Agent Execution Sequence

`	ext
                                [ User Prompt Received ]
                                           │
                                           ▼
                 [ Step 1: Spatial Context & Directory Routing (R1) ]
                 - Identify active path (sports_cards/ vs content_creation/)
                 - Load Root GEMINI.md + Localized GEMINI.md
                                           │
                                           ▼
                 [ Step 2: Pre-Execution Grounding Check (R4) ]
                 - Inspect files, schemas, and dependencies via tools
                 - Is ground truth 100% verified?
                        │                         │
                     [ No ]                    [ Yes ]
                        │                         │
                        ▼                         ▼
            [ Emit "I don't know" ]    [ Step 3: Ambiguity Check (R2) ]
            [ & Halt Execution ]       - Is architecture fully specified?
                                              │                │
                                           [ No ]           [ Yes ]
                                              │                │
                                              ▼                ▼
                                      [ Trip Breaker ]   [ Step 4: Execute & Verify ]
                                      [ Emit /grill-me ] - Run build/test commands
                                                         - Validate against schema
                                                               │
                                                               ▼
                                                         [ Step 5: Post-Task Check ]
                                                         - Confidence post-check (R4)
                                                         - Evaluate Distillation (R3)
                                                               │
                                                               ▼
                                                         [ Final Response + Confidence Block ]
`

### 5.2 Failure Mode Mitigation Matrix

| Failure Mode | Unharnessed Agent Behavior | Harnessed Agent Behavior (R1-R4) |
| :--- | :--- | :--- |
| **Vague Prompt ("Build an app")** | Hallucinates an arbitrary React or Express app with random dependencies. | **Trips R2 (/grill-me):** Halts immediately, presents structured multi-choice options for framework, storage, and scope. |
| **Cross-Hobby Rule Contamination** | Uses video transcoding bitrate rules inside a sports card Python parser. | **Isolated by R1:** Subdirectory GEMINI.md rules scope domain directives exclusively to their respective folders. |
| **Missing Schema / API Key** | Generates plausible mock keys, invent fake column names, or assumes default tables. | **Enforced by R4:** Mechanically states "I don't know", halts execution, and requests exact schema/credentials. |
| **Repeated Manual Orchestration** | Re-executes complex multi-step debugging across multiple sessions from scratch. | **Distilled by R3:** Automatically prompts user to convert the novel workflow into a permanent SKILL.md runbook. |

---

## Conclusion & Implementation Readiness

The four mechanisms (R1: Directory-Scoped Rule Isolation, R2: Ambiguity Circuit Breaker, R3: Workflow Distillation, and R4: The Confidence Mechanism) form an interlocking, mathematically sound AI Harness for Antigravity. By anchoring execution in verified evidence, isolating disparate domain contexts, halting at ambiguity, and capturing novel workflows into permanent runbooks, the harness guarantees deterministic, high-rigor engineering output for Noah's workspace.