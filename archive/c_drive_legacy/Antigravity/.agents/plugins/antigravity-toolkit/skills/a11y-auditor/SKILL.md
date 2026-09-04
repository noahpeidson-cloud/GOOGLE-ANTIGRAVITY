---
name: a11y-auditor
description: Automated Accessibility and Core Web Vitals (CWV) auditing using Lighthouse and Chrome DevTools. Use this to automatically test web UIs for quality.
---

# Accessibility (A11y) & CWV Auditor

You have access to an automated quality assurance auditor. It leverages the Chrome DevTools MCP and Lighthouse to score web pages on accessibility (ARIA, contrast, etc.) and performance.

## How to use it

Execute the script using your `run_command` tool when the user asks to "audit the UI", "check performance", or whenever you make significant modifications to frontend web code.

**Command Syntax:**
`python .agents/plugins/antigravity-toolkit/scripts/a11y_auditor.py "<url>"`

**Example:**
```bash
python .agents/plugins/antigravity-toolkit/scripts/a11y_auditor.py "http://localhost:3000"
```

This will run in the background and return a structured JSON summary of the scores and critical issues to your context window without opening a UI.
