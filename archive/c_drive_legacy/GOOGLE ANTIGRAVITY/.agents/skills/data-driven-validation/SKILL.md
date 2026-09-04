---
name: data-driven-validation
description: >-
  Executes a targeted, exhaustive deep research workflow using the Gemini Deep Research agent to validate, enhance, or reject architectural designs and ideas using hard data. Use when the user proposes a new architecture and needs objective validation.
---

# Data-Driven Validation

## Overview
This skill leverages the Gemini Interactions API and the `deep-research-max-preview-04-2026` background agent to perform exhaustive web research on a proposed topic, design, or architecture. It outputs a definitive, data-backed markdown report that either validates, enhances, or rejects the proposal.

## Dependencies
- `gemini-interactions-api`: Used to spawn the background research agent.
- `managing-python-dependencies`: The utility script must be run using `uv`.

## Quick Start
```bash
uv run .agents/skills/data-driven-validation/scripts/validate_design.py research --topic "Migrating our backend from REST to GraphQL" --output validation.md
```

## Utility Scripts

### `research`
Dispatches a background research agent to analyze a specific topic.

**Arguments:**
- `--topic` (required): The design, idea, or problem to research.
- `--output` (required): The file path where the markdown report will be saved.

**Example:**
```bash
uv run .agents/skills/data-driven-validation/scripts/validate_design.py research --topic "Using SQLite for high-concurrency web apps" --output /tmp/sqlite_research.md
```

## Common Mistakes
- **Forgetting `--output`:** The script forces file output to prevent massive context window bloat from the exhaustive research report.
- **Not waiting for completion:** The research agent runs in the background, but the python script actively polls it until completion. Do not interrupt the script.
