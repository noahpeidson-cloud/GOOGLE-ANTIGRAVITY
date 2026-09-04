---
name: browser-e2e
description: Automated UI testing and browser interaction without context bloat. Use this whenever the user wants to test a web UI, verify a frontend feature, or run End-to-End browser tests.
---

# Browser E2E Subagent

You have access to an autonomous Browser Subagent that can navigate web pages, interact with the DOM, and verify UI functionality using Chrome DevTools via MCP. 

Because interacting with the browser DOM directly in this main session would flood your context window with massive HTML snapshots, you **MUST** delegate all UI testing tasks to this subagent script.

## How to use it

Execute the script using your `run_command` tool. Provide the objective and the starting URL as arguments.

**Command Syntax:**
`python .agents/plugins/antigravity-toolkit/scripts/browser_agent.py "<objective>" "<url>"`

**Example:**
If the user asks you to "test if the new login form works", you should run:
```bash
python .agents/plugins/antigravity-toolkit/scripts/browser_agent.py "Fill out the login form with test@example.com / password123 and verify it redirects to the dashboard" "http://localhost:3000/login"
```

The script will handle all the complex Chrome DevTools orchestration (navigate -> wait -> snapshot -> interact) in a separate context and return a clean, concise summary of the results to you.
