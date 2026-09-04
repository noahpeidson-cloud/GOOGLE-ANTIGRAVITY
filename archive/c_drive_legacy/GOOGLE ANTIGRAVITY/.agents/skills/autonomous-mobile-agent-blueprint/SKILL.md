---
name: autonomous-mobile-agent-blueprint
description: Master Blueprint for building Agentic Mobile Automation Pipelines. Synthesizes Gemini Interactions API, headless ADB orchestration, and strict pre-flight guardrails.
---

# Autonomous Mobile Agent Blueprint

When the user invokes this skill (or asks to build a mobile automation agent), you MUST adhere to the following 4-stage architectural blueprint. You are strictly forbidden from implementing naive screen-scraping loops or foreground terminal execution.

## Stage 1: The Managed Mobile Agent (`gemini-interactions-api`)
Future python agents MUST use the `gemini-interactions-api` to create a custom sandboxed agent inheriting from `antigravity-preview-05-2026`. 

**Code Simulation Requirement:**
```python
from google import genai
client = genai.Client()

agent = client.agents.create(
    id="mobile-automation-worker",
    base_agent="antigravity-preview-05-2026",
    system_instruction="You are a headless Android automation agent. Use ADB to manipulate the device.",
    base_environment={
        "type": "remote"
    }
)
```

## Stage 2: The 4-Tier Bypass Engine (`zero-touch-automation-registry`)
When orchestrating the device via the `android-cli` (ADB), the agent is STRICTLY FORBIDDEN from relying on visual screen-scraping as a first resort. It MUST execute the 4-tier hierarchy:
1. **Direct Dalvik binary execution** (`adb shell app_process ...`)
2. **Android Intents** (`adb shell am start ...` / `am broadcast`)
3. **`uiautomator` DOM parsing** (dump XML, parse bounds mathematically)
4. **`monkey` keystroke injection**

## Stage 3: The Pre-Flight Guardrails (`albert-einstein-deep-think`)
Before the Agent is permitted to execute, the orchestrator script MUST programmatically verify the environment using adversarial falsifiability.

**Static Guardrail Requirement:**
```python
import subprocess
import sys

def verify_adb():
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
    if len(lines) < 2 or "device" not in lines[1]:
        print("[!] FATAL: No ADB device attached or authorized!", file=sys.stderr)
        sys.exit(1)

verify_adb()
```

## Stage 4: Daemonized Execution (`zero-friction-execution`)
The Python script running this Gemini interactions loop MUST be executed natively by Antigravity via the `run_command` tool with the `IsDaemon=true` flag. 
- You MUST handle `python-dotenv` natively in the script.
- You MUST install dependencies (`pip install google-genai python-dotenv`) before launching.
- You MUST completely abstract the terminal execution away from the user.
