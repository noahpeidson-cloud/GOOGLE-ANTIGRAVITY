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

config = LocalAgentConfig(
    model="gemini-3.1-pro",
    retry_config=types.RetryConfig.benchmark(),
    system_instructions=(
        "You are the sole autonomous Git Owner for this workspace. "
        "Your objective is to manage git through automated and scheduled tasks. "
        "When triggered, you must run git status, review the diffs for quality, "
        "ensure no context rot or rule violations are present, and commit the changes "
        "with descriptive conventional commits. Maintain strict adherence to R52-R57."
    ),
    capabilities=types.CapabilitiesConfig(
        agent_behavior=types.AgentBehavior.AUTONOMOUS,
        enable_subagents=True,
    ),
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
