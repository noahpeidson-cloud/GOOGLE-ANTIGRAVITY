---
name: grill-me
description: >-
  Interactive multiple-choice interrogation protocol. Triggers whenever a technical architecture, framework, data schema, or user requirement is underspecified. Halts speculative execution and asks 3-5 structured multiple-choice questions to establish unambiguous technical boundaries.
---

# Ambiguity Circuit Breaker: `/grill-me` Interrogation Protocol

## Overview
The `/grill-me` skill is the primary ambiguity circuit breaker for the Antigravity AI Harness. When an agent receives an underspecified or ambiguous request (e.g., *"build an app"*, *"process my data"*, *"optimize this workflow"*), it is **mechanically barred** from generating speculative code or assuming technical stacks. Instead, it must trip this circuit breaker, halt execution, and interrogate the user with structured, multiple-choice questions.

## Invocation Triggers
Activate this skill immediately when ANY of the following conditions are met:
1. **Underspecified Architecture**: The request asks to create software, dashboards, or scripts without specifying the tech stack (e.g., Streamlit vs. React, SQLite vs. CSV).
2. **Missing Input/Output Contracts**: Target file paths, input schemas, or expected output formats are not provided.
3. **Unclear Functional Scope**: Core requirements, business logic boundaries, or error-handling policies are ambiguous.
4. **Vague Performance / Constraint Targets**: Scaling requirements, latency limits, or execution environments are unspecified.

## The Halting Rule (Zero Speculation)
- **STRICT PROHIBITION**: Do NOT write code, create project files, or install dependencies while in an ambiguous state.
- **HALT IMMEDIATELY**: Suspend task execution until the user selects options or clarifies requirements.

## Protocol Execution & Output Format
When `/grill-me` is triggered, the agent MUST format its response strictly using the following structure:

```markdown
<grill_me>
# Technical Requirement Clarification (/grill-me)

To ensure an exact implementation without assumptions, please choose from the options below:

### 1. [Primary Architectural / Framework Decision]
- **A)** [Option 1 Description]
- **B)** [Option 2 Description] [Recommended]
- **C)** [Option 3 Description]
- **D)** Custom / Other (Please specify)

### 2. [Data Storage & Persistence Strategy]
- **A)** [Option 1 Description] [Recommended]
- **B)** [Option 2 Description]
- **C)** [Option 3 Description]
- **D)** Custom / Other (Please specify)

### 3. [Scope & Integration Boundaries]
- **A)** [Option 1 Description]
- **B)** [Option 2 Description] [Recommended]
- **C)** [Option 3 Description]
- **D)** Custom / Other (Please specify)

---
*Reply with your choices (e.g., "1B, 2A, 3B") or provide custom instructions to proceed.*
</grill_me>

<confidence>
**Confidence Level:** LOW
**Evidence Chain:**
- Prompt requested: "[Verbatim user prompt]"
- Critical architectural decisions (framework, data schema, scope) are underspecified.
**Gaps / Assumptions:** Undefined technology stack and input/output contracts.
</confidence>
```

## Step-by-Step Runbook
1. **Detect Ambiguity**: Analyze incoming prompt. If technical stack, schema, or scope is underspecified, halt execution immediately.
2. **Decompose Requirements**: Formulate 3 to 5 targeted questions covering:
   - Architecture & Tech Stack (e.g., Streamlit vs React, CLI vs Web UI)
   - Data Ingestion & Storage (e.g., SQLite vs CSV vs In-Memory)
   - Scope Boundaries & Error Handling (e.g., Minimal MVP vs Full Feature Set)
3. **Provide Recommended Defaults**: Mark the most sensible, production-aligned choice with `[Recommended]`.
4. **Append Terminal Confidence Block**: Anchor `<confidence>` at the very bottom with level `LOW` or `MEDIUM` and cite specific gaps.
5. **Await User Clarification**: Resume execution only after user response resolves ambiguity.

## Anti-Patterns & Prohibitions
- ❌ **Speculative Implementation**: Writing `app.py` or scaffolding directories before asking questions.
- ❌ **Open-Ended Interrogation**: Asking vague, unstructured questions like *"What do you want to build?"* instead of structured multiple-choice options.
- ❌ **Missing Confidence Block**: Omitting the terminal `<confidence>` block.
