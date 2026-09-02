---
name: agent-ml-optimization-loop
description: "Implements a localized CI/CD machine learning feedback loop for subagents using Antigravity SDK lifecycle hooks, SQLite3 telemetry, Pandas K-Means clustering, and ProTeGi textual gradients."
---

# Localized Agent ML Optimization Loop

## Core Philosophy
Subagents must not operate blindly. Execution metrics must be captured, analyzed via localized Machine Learning, and autonomously corrected when drift occurs, strictly adhering to the 'No Hallucinated Tooling' workspace mandate.

## Implementation Protocol

### 1. The Localized Telemetry Hook
When orchestrating subagents, inject the `@hooks.on_turn_end` decorator to capture metrics into a local SQLite database, enforcing Directory-Scoped Isolation.

```python
from google.antigravity import hooks
import sqlite3
import time

@hooks.on_turn_end
def capture_telemetry(context, turn_result):
    conn = sqlite3.connect('telemetry_spans.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS telemetry
                      (agent_id TEXT, domain_track TEXT, input_tokens INT, output_tokens INT, error_count INT, timestamp INT, transcript TEXT)''')
    
    cursor.execute("INSERT INTO telemetry VALUES (?, ?, ?, ?, ?, ?, ?)", 
                   (context.agent_id, context.workspace.name, turn_result.usage.input_tokens, 
                    turn_result.usage.output_tokens, len([e for e in turn_result.errors]), 
                    int(time.time() * 1000), turn_result.transcript))
    conn.commit()
    conn.close()
```

### 2. Pandas-Native K-Means Evaluation (The Judge)
Do NOT use BigQuery ML. Use local `pandas` and `numpy` to identify poor execution patterns:
1.  **Vector Embeddings:** Generate N=5 response variations and extract local embeddings.
2.  **Semantic Clustering:** Calculate Euclidean distances using `numpy` and `pandas` DataFrames.
3.  **Hallucination Detection:** If semantic entropy (distance between centroids) is high, execution halts. This process must execute in < 5ms locally.

### 3. Autonomous Correction (ProTeGi Textual Gradients)
When the Pandas cluster identifies semantic entropy:
1.  The Meta-Agent executes a ProTeGi "backward pass" to critique the flawed trajectory.
2.  The Meta-Agent invokes the `workflow-skill-creator`.
3.  The Meta-Agent applies the textual gradient, rewriting the subagent's `SKILL.md` to patch the behavioral drift.
4.  If the failure stems from missing structural context, the Meta-Agent MUST trigger the `/grill-me` protocol per Rule R2.
