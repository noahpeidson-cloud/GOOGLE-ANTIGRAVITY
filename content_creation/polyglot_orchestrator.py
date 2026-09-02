import sys
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

# Fix stdout encoding for Windows console (emojis/unicode)
sys.stdout.reconfigure(encoding='utf-8')

# The Antigravity SDK
from google.antigravity import Agent, LocalAgentConfig, types

# Load API keys for the Polyglot Models (OpenAI, Anthropic, Google)
workspace_root = Path(__file__).parent
load_dotenv(workspace_root / ".env")

def enforce_api_keys():
    """R26 Guardrail: Ensure polyglot keys exist to prevent runtime auth crashes."""
    required = ["GEMINI_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"R26 Violation: Missing required API keys in .env: {missing}")
    
    # Optional but highly recommended for the Polyglot architecture
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        print("[WARNING] Neither OPENAI_API_KEY nor ANTHROPIC_API_KEY found. Polyglot routing will fallback to Gemini.")

# Define the Polyglot Subagents
editor_agent = types.SubagentConfig(
    name="editor_agent",
    description="The Editor. Focuses on code logic, timeline mathematics, and precise Python integration for DaVinci Resolve.",
    model="anthropic/claude-5-sonnet-20260220",
    capabilities=types.SubagentCapabilities(
        enabled_tools=[types.BuiltinTools.RUN_COMMAND],
        agent_behavior=types.AgentBehavior.AUTONOMOUS,
    ),
)

publisher_agent = types.SubagentConfig(
    name="publisher_agent",
    description="The Publisher. Executes high-speed tool calls to the YouTube API, Snapchat Spotlight, TikTok, and Facebook Pages.",
    model="gemini-3.7-flash",
    capabilities=types.SubagentCapabilities(
        agent_behavior=types.AgentBehavior.AUTONOMOUS,
    ),
)

async def run_polyglot_pipeline(concept: str, asset_id: str = "default_asset"):
    enforce_api_keys()
    
    # The Root Router
    config = LocalAgentConfig(
        model="gemini-3.7-flash", # High speed root router
        retry_config=types.RetryConfig.benchmark(), # R27: Tiered Model Cascade
        system_instructions=types.TemplatedSystemInstructions(
            identity="You are the Omnichannel Polyglot Router. You delegate tasks to the most capable model based on the domain. Editor (Code/Math), Publisher (Tool Calling)."
        ),
        subagents=[editor_agent, publisher_agent],
        capabilities=types.CapabilitiesConfig(
            enable_subagents=True,
            max_subagent_depth=2,
            allowed_subagents=["editor_agent", "publisher_agent"],
        ),
    )
    
    try:
        async with Agent(config) as agent:
            print(f"Starting Polyglot Media Pipeline for asset {asset_id}...")
            response = await agent.chat(f"Execute this pipeline concept using the optimal agents: {concept}")
            final_report = await response.text()
            print("\n\n=== PIPELINE REPORT ===")
            print(final_report)
            
            # Output the draft state for the Human-in-the-Loop UI
            import json
            with open("draft_state.json", "w", encoding="utf-8") as f:
                json.dump({
                    "concept": concept,
                    "status": "AWAITING_HUMAN_COMMIT",
                    "ai_summary": final_report[:200] + "..."
                }, f, indent=4)
            print("-> Generated draft_state.json for Human-in-the-Loop Review.")
    except Exception as e:
        print(f"[ERROR] Agent Pipeline failed for asset {asset_id}: {e}")
        print(f"[QUARANTINE] Implementing Aggressive Cascade. Quarantining asset {asset_id} and proceeding.")
        import sqlite3
        try:
            conn = sqlite3.connect("media_manifest.sqlite")
            cursor = conn.cursor()
            cursor.execute("UPDATE assets SET status = 'QUARANTINED' WHERE asset_id = ?", (asset_id,))
            conn.commit()
            conn.close()
        except Exception as db_err:
            print(f"[ERROR] Failed to update sqlite for quarantine: {db_err}")
        return False
    return True

if __name__ == "__main__":
    asyncio.run(run_polyglot_pipeline("Process the EDC Summit 2026 raw footage into a viral 9:16 Short.", "test_asset_001"))
