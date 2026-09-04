---
name: protegi-leash-enforcer
description: Operationalizes Automatic Prompt Optimization (APO) and ProTeGi textual gradients as a pre-flight adversarial loop to choke AI discretion and prevent hallucinations.
---

# ProteGi Leash Enforcer

This skill forces the agent into a continuous adversarial alignment loop BEFORE executing highly complex or deeply ambiguous tasks. It serves as the physical enforcement mechanism for Rule R2 (The Zero-Discretion Mandate).

## Core Philosophy
If an LLM encounters an underspecified prompt, its default behavior is to use "discretion" (guessing). This skill uses mathematical entropy and Automatic Prompt Optimization (APO) / Textual Gradients to detect that guessing and violently tighten the constraints until the prompt is perfectly rigid.

## Workflow: The Adversarial Alignment Loop

When an agent is faced with an ambiguous architectural task and lacks deterministic tests, it MUST invoke this protocol.

### Step 1: Beam Search Expansion (The Entropy Check)
Instead of proceeding with the first plan it thinks of, the agent MUST generate multiple distinct prompt branches (A, B, C) to explore the solution space.
*   **Branch A:** The naive/standard approach.
*   **Branch B:** An approach optimizing for zero external dependencies.
*   **Branch C:** An approach optimizing for maximum programmatic verifiability via ContextCov static checks.

### Step 2: Discretion Detection (Bandit Pruning)
The agent must act as a meta-judge and evaluate the semantic distance between the branches. If the branches diverge wildly in architecture, tech stack, or assumptions, the initial prompt was too loose. The agent is exercising too much discretion.
Using a conceptual multi-armed bandit algorithm, the agent immediately prunes branches that rely on hallucinated or unverifiable steps, concentrating constraints onto the single most deterministic branch.

### Step 3: The ProTeGi Backward Pass (Textual Gradient)
If High Entropy is detected, the agent MUST NOT ask the user a generic "What should I do?" question. It must execute a Textual Gradient update:
1.  **Critique:** The agent writes a harsh critique identifying the exact missing parameters that allowed the branches to diverge so wildly.
2.  **Gradient Update:** The agent rewrites the original task prompt, physically injecting strict guardrails that invalidate the ambiguous branches.
3.  **Halt & Grill:** The agent halts execution and invokes `/grill-me` with the updated, hardened prompt to force the user to lock in the final variables.

### Step 4: The TDAD Orthogonal Handoff (Trustless Execution)
Once the constraints are tightened, the agent is forbidden from executing the code itself.
1.  The agent MUST delegate the finalized, hardened prompt to a fresh subagent (via `invoke_subagent` or `/teamwork-preview`).
2.  **The "Red" Phase Mandate:** The primary agent transitions into an Adversarial Auditor. It MUST enforce Test-Driven Agentic Development (TDAD). The auditor explicitly commands the subagent to write a failing test suite using "Loud Assertions" (zero shared state) and prove it fails *before* any implementation code is written. 
3.  If the subagent violates the Red Phase or fails the tests, the Auditor generates a new textual gradient critique and forces a re-run.

## Common Mistakes
- **Self-Certification:** An agent writing the code and then evaluating its own code. *The builder can never be the judge.*
- **Asking open-ended questions:** When applying the Textual Gradient, do not ask the user "What should I do?" Ask them multiple-choice questions derived directly from the mathematical divergence of the plans.
