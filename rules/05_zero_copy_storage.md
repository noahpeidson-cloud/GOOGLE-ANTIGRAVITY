---
title: "Storage & File System Guardrails"
category: "storage"
enforcement: "strict"
---

# Storage & File System Guardrails

## R-STORE-01. Canonical Path Integrity & D: Drive Exclusivity
- **Canonical Root:** `D:\GOOGLE ANTIGRAVITY` and `D:\AI_Platform`.
- **Mandate:** Agents MUST NEVER reference or generate paths to legacy cloud-synced folders (`G:\My Drive\GOOGLE ANTIGRAVITY`, `C:\Users\noahp\OneDrive\...`).
- **Storage Isolation:** All AI model caches, vector stores, ephemeral scratch files, and datasets MUST live strictly on `D:`. The `C:` drive is reserved strictly for Noah's operating system.
- **Actionable Execution:** Always import and use `from infrastructure.workspace_context import WORKSPACE_ROOT`.

## R-STORE-02. Non-Destructive Raw Archiving
- **Context:** Media pipeline directory lifecycle (`01_RAW/`, `01_RAW_INBOX/`, `04_ARCHIVE/`).
- **Mandate:** Raw source files are STRICTLY IMMUTABLE. Agents MUST NEVER overwrite original source files. Output all processed assets to dedicated sibling directories (`02_PROXIES/`, `03_READY_TO_POST/`, `renders/`).
- **Destructive File Operation Prohibition:** Any file deletions or migrations MUST preserve an explicit backup in `.archive/` before modification. Hard-deletions without archiving are FORBIDDEN.
