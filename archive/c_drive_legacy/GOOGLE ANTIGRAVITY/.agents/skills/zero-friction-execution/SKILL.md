---
name: zero-friction-execution
description: >-
  Strict guardrail forbidding agents from asking the user to manually execute terminal commands. Mandates the use of background daemons for local servers.
---

# Zero-Friction Execution Protocol

## 1. No Manual Terminal Handoffs
The agent is **strictly forbidden** from providing instructions like "Open a terminal and run "npm run dev"" or "Run this python script in your terminal." 

## 2. Autonomous Daemon Hosting
Whenever a task requires running a local development server (e.g., Next.js, React, Vite), a Python background listener, or any long-running process:
*   The agent MUST use its run_command tool with the IsDaemon=true flag to host the process in the background.
*   The agent MUST handle all dependency installations (e.g., creating a venv or running npm install) silently in the background before launching the daemon.
*   The agent should simply provide the user with the localhost URL to click, fully abstracting the terminal away.
