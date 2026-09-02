---
name: architecture-red-team
description: >-
  Forces the agent to bring in diverse opinions and rigorously audit architectural decisions before execution. Triggered when the user proposes a major pivot or asks "is this the right approach".
---

# Architecture Red Team Protocol

## Overview
This skill actively fights confirmation bias and "yes-man" behavior. When designing a system, the agent must never blindly agree with the user's first idea or its own first idea.

## Workflow Steps

### 1. The Halt
When a new architecture is proposed, halt execution. Do not write code.

### 2. The Adversarial Research
Invoke the `browser` subagent to actively search for "opposing viewpoints", "trade-offs", and "flaws" regarding the proposed architecture on StackOverflow, Reddit, and engineering blogs.
**CRITICAL:** The research must be solely data-backed and thoroughly credited. The subagent must cite specific sources (e.g., StackOverflow, specific subreddits, GitHub issues, or engineering blog posts).

### 3. The Matrix Presentation
Present the user with a streamlined, multi-perspective review:
- **The Original Idea:** Pros and Cons.
- **The Red Team Attack:** The hidden flaws, security risks, or scalability issues discovered during research (MUST include cited sources).
- **The Industry Standard Alternative:** What other developers do in this exact scenario (MUST include cited sources).

### 4. The Omnichannel Alignment Check
The agent MUST explicitly cross-reference the winning architecture against the user's Global Directives (e.g., the "Omnichannel Content & Life Protocol" in `GEMINI.md`). 
The agent must explain exactly how the architecture serves the overarching goal of a "Centralized Autonomous Brain" and how it scales across the user's disparate tracks (Sports Cards, Content Creation, Travel, Apps). If the architecture creates isolated technical debt that doesn't serve the broader ecosystem, the agent must flag it.

### 5. Executive Decision
Wait for the user to review the diverse opinions and make an informed executive decision before proceeding to code generation.
