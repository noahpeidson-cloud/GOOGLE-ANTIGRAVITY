---
name: teamwork-langgraph-orchestrator
description: The ultimate data-backed multi-agent orchestrator. Replaces naive swarms with a strict Orchestrator-Worker cyclic graph, leveraging heterogeneous model routing, localized ML telemetry, and adversarial validation.
---

# LangGraph Orchestrator Protocol (Master Blueprint)

When the user invokes this skill, you must abandon conversational swarming and execute this strict state-machine workflow integrating SDK execution, ML optimization, and deep-think validation.

## Step 1: Initialize the Heterogeneous Graph (`google-antigravity-sdk`)
You must use the `google-antigravity-sdk` to spawn specific models for specific nodes using invoke_subagent.

**Code Simulation Requirement:**
```python
# The Orchestrator (Claude Fable 5 via Proxy/Native)
# Responsible solely for planning the DAG and reviewing Worker outputs.
orchestrator_config = LocalOpenAIAgentConfig(
    model="claude-fable-5", 
    system_instructions="You are the LangGraph Master Node. Break tasks into exact DAG nodes."
)

# The Workers (Gemini 3.7 Flash)
# Responsible for executing discrete nodes (e.g., 'Scrape docs', 'Write UI component')
worker_config = LocalAgentConfig(
    model="gemini-3.7-flash",
    system_instructions="You are a stateless Worker node. Execute exactly what the Orchestrator commands."
)
```

## Step 2: The Mandatory Validation Loop (`albert-einstein-deep-think`)
Before the Orchestrator can mark a task as "Complete", the graph must loop through an Adversarial Red Team. 
The Red Team MUST execute Phase 2 (Adversarial Web-Grounded Deep Research) and Phase 4 (External Falsifiability) from the `albert-einstein-deep-think` protocol to aggressively attempt to break the Worker's code or architecture before approval.

- Spawn a subagent using a separate model weight (e.g., gemini-3.1-pro or a local 120B OSS model).
- The Red Team attempts to break the Worker's code.
- The Orchestrator reviews the Red Team's report and either approves the node or routes it back to the Worker.

## Step 3: Execution Artifacts
You must explicitly write the DAG status to a `langgraph_state.md` artifact in real-time so the user can observe the Orchestrator-Worker node transitions.

## Step 4: Continuous CI/CD Telemetry (`agent-ml-optimization-loop` & `ml-best-practices`)
Subagents must not operate blindly. You MUST inject the `@hooks.on_turn_end` decorator into the Antigravity SDK graph to capture metrics into a local SQLite database (`agent-ml-optimization-loop`).

Once data is collected, the Orchestrator must apply `ml-best-practices` (Pandas K-Means Clustering, Euclidean distance evaluation) to detect high semantic entropy or hallucination drift across worker nodes, triggering a ProTeGi textual gradient rewrite if the cluster deviates from the baseline.
