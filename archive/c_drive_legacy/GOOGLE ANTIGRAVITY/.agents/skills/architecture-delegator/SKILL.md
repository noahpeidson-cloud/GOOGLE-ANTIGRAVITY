---
name: architecture-delegator
description: >-
  A strict orchestration protocol that forces the agent to resolve all technical ambiguities from rough briefs via interactive multiple-choice, compile a finalized architectural prompt, and delegate execution to the teamwork-langgraph-orchestrator multi-agent team. Halts execution entirely on failure.
---

# Architecture Delegator

## Overview
Turns the AI agent into a strict project orchestrator. Rather than attempting to guess or hallucinate code from a vague user request, the agent is forced to interview the user, lock in exact architectural boundaries, and deploy a specialized multi-agent engineering team to do the actual building and auditing.

## Dependencies
- **lbert-einstein-deep-think**: Mandatory protocol for resolving ambiguities, interrogating the user, and forcing external falsifiability.
- **	eamwork-langgraph-orchestrator**: Mandatory multi-agent delegation system (Claude Fable 5 master node) for writing the codebase.

## Workflow

### 1. Phase 1: Ambiguity Resolution (Einstein Protocol)
- Read the user's initial idea, technical brief, or scratchpad document.
- You **MUST** trigger the native /grill-me command logic under the Einstein Protocol.
- You **MUST** use the sk_question tool to present structured, multiple-choice questions one at a time. Walk down the decision tree until all major technical uncertainties (tech stack, infrastructure, API constraints) are resolved.

### 2. Phase 2: Prompt Compilation
- Once the interview is complete, write a prompt_draft.md artifact.
- The artifact must clearly define the Requirements (R1, R2, etc.) and Objective Acceptance Criteria based on the user's answers.

### 3. Phase 3: Autonomous Delegation
- Present the prompt_draft.md to the user.
- Upon user approval, extract the exact text of the prompt and pass it to the 	eamwork-langgraph-orchestrator skill to construct the DAG.

### 4. Phase 4: Independent Audit & Strict Halt Rule
- Allow the LangGraph orchestrator and its Red Team Auditor to run.
- **CRITICAL FAILURE PROTOCOL**: If the teamwork subagent fails, errors out, or if the Victory Auditor rejects the codebase, you must **fail loudly and halt execution**. You are explicitly barred from attempting to write hallucinated fallback code or bypass the auditor. Report the failure directly to the user.
