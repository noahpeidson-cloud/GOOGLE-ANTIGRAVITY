---
name: apps-router
description: >
  MANDATORY TRIGGER: Activate this skill anytime the user asks to "build an app", "fix UI", "update the frontend", or mentions "React", "Vite", or "Streamlit". It provides the exact sequence of skills you must chain together to succeed without guessing.
---

# Apps Track Router

When operating in the `/apps` track, you MUST follow this sequence of skills and operations.

## The Optimal App Building Sequence

1. **Modern Standards Check**
   - Before writing ANY HTML, CSS, or React code, you MUST invoke `view_file` on the `modern-web-guidance` skill to ensure you are using current web APIs (like CSS container queries, native dialogs, etc.) and not legacy polyfills.

2. **Automated Auditing**
   - After implementing UI changes, you MUST read the `chrome-devtools` and `a11y-debugging` skills. Use the Chrome DevTools MCP to take an Accessibility Tree snapshot and verify your color contrast, ARIA labels, and tap targets programmatically.

3. **Dependency Enforcement**
   - If a new library is needed, you MUST read the `managing-python-dependencies` skill or ensure you are strictly following Node.js local project standards (no global installs).

By adhering to this routing script, you guarantee that all applications meet modern web and accessibility standards.
