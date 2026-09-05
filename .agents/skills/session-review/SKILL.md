---
name: session-review
description: >-
  Use this skill to autonomously review and grade past agent sessions (conversations) for context rot, drift, and lessons learned. Trigger this when the user asks to "review a session", "grade my thinking", or evaluate a specific conversation ID.
---

# Session Review and Grading Workflow

This skill equips the main agent to review past conversations and grade the AI's performance, specifically looking for context rot, drift, and structural failures, ultimately outputting "lessons learned" and new rules.

## Step 1: Locate the Target Transcript

Because session transcripts are stored globally outside the workspace, you must use the `find_by_name` tool.
1. Search within the directory: `C:\Users\noahp\.gemini\antigravity\brain` (or `<appDataDir>\brain\`).
2. Look for the directory matching the target Conversation ID.
3. Identify the `transcript.jsonl` file within that conversation's `.system_generated\logs` folder.

## Step 2: Configure the Evaluator Subagent

Do NOT process the massive transcript directly in your own context window. You must configure and spawn a specialized subagent to do the heavy lifting.

1. Define a `SubagentConfig` named `session_evaluator`.
2. **Restrict Tools:** In `capabilities.enabled_tools`, you MUST ONLY enable `types.BuiltinTools.VIEW_FILE`. Do not give it access to web search or command execution to minimize token footprint.
3. **Set Autonomous Behavior:** In `capabilities`, set `agent_behavior=types.AgentBehavior.AUTONOMOUS`.
4. **System Instruction:** Instruct the subagent to read the provided `transcript.jsonl` file path, analyze the AI's decision-making process, and summarize the core failures and required architectural rules to prevent them in the future.
5. **Grading Rubric:** Specifically instruct the subagent to grade the transcript for the following failure modes:
    *   **Positional Bias (Context Rot):** Did the agent ignore early constraints or instructions as the context grew?
    *   **Looping:** Did the agent repeatedly try the same failed solution or code change more than twice?
    *   **Prompt/Goal Drift:** Did the agent silently change the core objective without explicit user permission?
    *   **Tool Hallucination:** Did the agent attempt to use tools that do not exist or were not provided in its configuration?
    *   **OS/Shell Syntax Hallucination:** Did the agent attempt to run Unix commands (e.g., `grep`, `cat`, `ls`) in a Windows PowerShell environment instead of prioritizing the native API tools (`grep_search`, `view_file`, `list_dir`)?
    *   **Workspace Boundary Violation:** Did the agent execute broad, unbounded drive scans (e.g., `C:\`, `D:\`) rather than anchoring its searches strictly within the active workspace root?

## Step 3: Execute and Synthesize

1. Invoke the subagent, passing it the exact path to the `transcript.jsonl` file.
2. Wait for the subagent to complete its autonomous analysis.
3. Once the subagent returns its findings, synthesize the "lessons learned".
4. If the findings warrant a permanent change in behavior, propose adding a new rule to the `GEMINI.md` file using the standard Antigravity rules format.
