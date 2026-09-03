---
title: "Python Runtime & Execution Guardrails"
category: "runtime"
enforcement: "strict"
---

# Python Runtime & Execution Guardrails

## R16. Executable Python Import Guardrail
- **Context:** When generating Python scripts that act as entrypoints, daemons, or CLI tools intended to be executed directly via `python script.py`.
- **Mandate:** Agents are STRICTLY FORBIDDEN from using relative imports (e.g., `from .module import foo`).
- **Actionable Execution:** You MUST use absolute imports (e.g., `from infrastructure.workspace_context import WORKSPACE_ROOT`) to prevent `ImportError: attempted relative import with no known parent package`.

## R18. Python Dependency Pre-Flight Guardrail
- **Context:** When generating or executing Python applications (such as FastAPI daemons, Streamlit dashboards, or background workers) that rely on external libraries.
- **Mandate:** Agents are STRICTLY FORBIDDEN from blindly executing scripts without ensuring runtime dependencies are installed.
- **Actionable Execution:** Before executing any script, ensure requirements are defined in `requirements.txt` and verified in the active environment.

## R26. Background Daemon Auth Guardrail
- **Context:** When spawning long-running Python background processes or daemons that require API access (such as Google GenAI / Gemini API).
- **Mandate:** Agents are STRICTLY FORBIDDEN from assuming background processes inherit IDE-internal proxy authorization.
- **Actionable Execution:** Background scripts must import `load_dotenv` from `python-dotenv` and read `GEMINI_API_KEY` directly from the root `.env` or system environment.
