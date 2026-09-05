import asyncio
import logging

from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.hooks import policy
from google.antigravity.triggers import TriggerContext, every

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_git_status(ctx: TriggerContext):
    """Periodic task to check git status and initiate review."""
    logger.info("TRIGGER: Initiating scheduled git review and maintenance.")
    # Push a message to the agent to start its review process
    await ctx.send("Perform a full automated git review. Check 'git status', review any unstaged or uncommitted changes. If there are valid changes that pass rules, commit them. Do not push.")

# We create a trigger that runs every hour (3600 seconds)
# For testing purposes, you could change this to run more frequently.
git_schedule_trigger = every(3600, check_git_status)

# Custom policy to strictly allow 'git' commands but deny other shell commands
def is_git_command(args):
    cmd = args.get("CommandLine", "")
    return cmd.strip().startswith("git ")

policies = [
    # Allow git commands
    policy.allow("run_command", when=is_git_command, name="allow_git"),
    # Default behavior denies all other run_command
    policy.confirm_run_command(),
]

auditor_agent = types.SubagentConfig(
    name="strict_auditor",
    description="An adversarial code reviewer that critiques diffs against global rules before they are committed.",
    capabilities=types.SubagentCapabilities(
        agent_behavior=types.AgentBehavior.AUTONOMOUS,
        # The auditor only needs to read files and diffs, no write access
        enabled_tools=[
            types.BuiltinTools.VIEW_FILE,
            types.BuiltinTools.RUN_COMMAND,
        ]
    )
)

config = LocalAgentConfig(
    model="gemini-3.1-pro",
    retry_config=types.RetryConfig.benchmark(),
    system_instructions=(
        "You are the autonomous Git Orchestrator. Industry best practices dictate you operate via PR-Based Governance and the Checker Pattern. "
        "When triggered:\n"
        "1. Context Assembly: Read GEMINI.md to load current global rules.\n"
        "2. Branching: If changes exist, create a new branch (e.g. 'agent-review/<date>'). Do not commit to the main working branch.\n"
        "3. Checker Pattern: You MUST invoke the 'strict_auditor' subagent to review the `git diff` output and verify it complies with R52-R57 and other workspace rules.\n"
        "4. Execution: Only if the auditor approves, commit the changes to the new branch with a conventional commit message.\n"
        "5. HITL: Do not push. Stop and notify the human developer that a branch is ready for Pull Request review."
    ),
    capabilities=types.CapabilitiesConfig(
        agent_behavior=types.AgentBehavior.AUTONOMOUS,
        enable_subagents=True,
        allowed_subagents=["strict_auditor"],
    ),
    subagents=[auditor_agent],
    policies=policies,
    triggers=[git_schedule_trigger],
)

async def main():
    logger.info("Starting Automated Git Review Agent...")
    async with Agent(config):
        # Keep the agent alive to process the triggers
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
