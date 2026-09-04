---
name: zero-friction-model-routing
description: Implementation patterns for zero-stall model fallbacks and bounded API retries using isolated quota buckets. Use when building ML pipelines or agents that hit 429 rate limits.
---

# Zero-Friction Model Routing

Whenever designing a pipeline or agent that utilizes the Gemini API on free-tier limits, you MUST implement this Zero-Friction Fallback mechanism. NEVER use `time.sleep()` to wait out a 429 Quota Exceeded error. Waiting blocks background daemons.

## The Strategy
Google Gemini API models utilize **isolated quota buckets** per model endpoint. This means that if `gemini-3.7-flash` hits a limit, `gemini-3.6-flash` and others are completely unaffected.

## Implementation 1: Raw Google GenAI SDK
When working with standard scripts (e.g., `google-genai` directly):

```python
from google import genai

client = genai.Client()

def robust_generation(prompt):
    # Dynamic Tiered Cascade
    fallback_models = [
        'gemini-3.7-flash', 
        'gemini-3.6-flash',
        'gemini-3.5-flash',
        'gemini-3.5-flash-lite',
        'gemini-2.5-pro'
    ]
    
    for model_id in fallback_models:
        try:
            interaction = client.interactions.create(
                model=model_id,
                input=prompt
            )
            return interaction.output_text
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                print(f"Limit Hit on {model_id}. Immediately falling back...")
                continue # Try the next model, zero stall!
            else:
                raise e
```

## Implementation 2: Google Antigravity SDK
When writing agents using the Antigravity SDK, do not write custom fallback loops. Instead, utilize the built-in `RetryConfig.benchmark()` to autonomously manage unbounded background retries against quota buckets.

```python
from google.antigravity import LocalAgentConfig, Agent, types

config = LocalAgentConfig(
    model="gemini-3.7-flash",
    retry_config=types.RetryConfig.benchmark() # Automatically handles 429/503 quotas
)

async with Agent(config) as agent:
    response = await agent.chat("Execute task.")
```
