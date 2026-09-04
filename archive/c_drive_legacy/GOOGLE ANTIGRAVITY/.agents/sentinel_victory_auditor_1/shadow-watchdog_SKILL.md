---
name: shadow-watchdog
description: "Implements an orthogonal monitoring agent to catch rule drift, and a Generational Mark-and-Sweep garbage collector to maintain context purity without data loss."
---

# The Shadow Watchdog

## Core Philosophy
The main agent's working memory degrades over time. The Shadow Watchdog runs an isolated, stateless `flash_lite` model that intercepts the main agent's payload, grading it strictly against `GEMINI.md` rules. It also enforces zero-data-loss context health via Generational Mark-and-Sweep.

## Implementation Protocol

### 1. Interception Layer
Implement the following Antigravity SDK hook in the primary execution script.

```python
from google.antigravity import hooks, exceptions
from google.antigravity.agents import Agent, LocalAgentConfig

shadow_config = LocalAgentConfig(model="flash_lite", system_instruction="You are a strict compliance auditor...")
shadow_agent = Agent(config=shadow_config)

@hooks.on_turn_end
def enforce_shadow_compliance(context, turn_result):
    # Inspect main agent's output
    pending_output = turn_result.transcript
    
    # Query Shadow Agent (Latency: ~0.5s)
    audit_result = shadow_agent.run(f"Does this output contain the mandatory <confidence> block and avoid fluff? Output: {pending_output}")
    
    # Block and Rewrite
    if "VIOLATION" in audit_result.text:
        raise exceptions.AgentInterceptError(
            message=f"SHADOW INTERCEPT: Rule violation detected. Fix immediately: {audit_result.text}",
            allow_retry=True
        )
```

### 2. Generational Mark-and-Sweep (Context Health)
Do NOT use recursive summarization. It destroys critical schemas (e.g., -14 LUFS, 21-variable).
1. **Immutable Marking:** In the `@hooks.on_pre_turn` cycle, explicitly flag the `GEMINI.md` system instructions and the current track's localized manifests as immutable.
2. **Continuous Sweeping:** Every 3 conversational turns, execute a lightweight sweep that discards the oldest non-essential `USER_INPUT` and `MODEL` spans.
3. **Heuristic:** Keep immediate follow-up context intact. Mathematically depreciate isolated, older tangents without ever touching the marked structural data.
