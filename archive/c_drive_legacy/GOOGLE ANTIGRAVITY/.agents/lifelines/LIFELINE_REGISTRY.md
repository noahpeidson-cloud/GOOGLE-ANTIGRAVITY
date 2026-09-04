# Antigravity Lifeline Registry

This registry permanently stores all structural failures, root cause analyses (RCAs), and deployed solutions extracted by the Omniscient Auditor (R28).

## Lifeline 001: The Google Drive Bandwidth Trap
**Date Recorded:** August 2026
**Target Session:** IDE Installation Request (`5ba0016f-8b31-4dd8-afeb-56830004e3da`)

### 1. The Finding (Root Cause)
The agent attempted to locate documents in Google Drive by executing the generic `list_resources` command against the `gdrive` MCP server. Because Google Drives can contain tens of thousands of files, this triggered an unpaginated, massive data fetch that saturated the agent's context window and stalled the execution loop indefinitely.

### 2. The Solution
Enforcement of **Rule R34 (The Google Drive MCP Bandwidth Guardrail)**. Agents are strictly forbidden from calling `list_resources` on `gdrive`. They must read the specific schemas (e.g., `search.json`, `listGoogleDocs.json`) inside `C:\Users\noahp\.gemini\antigravity\mcp\gdrive` and exclusively use `call_mcp_tool` with targeted search parameters.

### 3. Active Intervention Status
**[ACTIVE]** The Shadow Watchdog intercepted the target session and injected a cross-session directive via `send_message` to halt the `list_resources` loop and course-correct.

## Lifeline 002: Disconnected Transport & Auth Paradigms
**Date Recorded:** August 2026
**Target Session:** IDE Installation Request (`5ba0016f-8b31-4dd8-afeb-56830004e3da`)

### 1. The Finding (Root Cause)
The target session's execution graph proposed a physically unviable local-to-cloud architecture:
1. It attempted to automate 67GB 8K video ingestion using Google Quick Share, which is fundamentally a UI-driven, manual peer-to-peer protocol that frequently drops connections for power-saving and requires a manual user "Accept" tap.
2. It hallucinated cross-cloud authorization by attempting to use the Windows Microsoft Store CLI (`msstore`) to provision service principals to authenticate a Google Cloud (GCP) data pipeline.

### 2. The Solution
Enforcement of **Rule R35 (The Ingestion Automation Guardrail)** and **Rule R36 (The GCP Authentication Guardrail)** in the global `GEMINI.md` manifest. 
*   Agents must bypass UI-locked edge tools (like Quick Share) for headless operations and use Syncthing, SMB, or direct cloud bucket APIs.
*   Agents must explicitly map authorization flows to their native cloud environment (e.g., GCP ADC / Workload Identity) rather than arbitrarily blending Microsoft Azure packaging CLI tools into Google backend orchestration.

### 3. Active Intervention Status
**[PASSIVE]** The target session correctly invoked its own Red Team Adversarial Subagent, which audited and killed the unviable architecture. No manual intervention was required. The learnings were permanently distilled into R35 and R36.
