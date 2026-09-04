"""
browser_master.subagents.browser_worker
=======================================
Autonomous browser worker subagent responsible for web page navigation,
accessibility tree inspection, and UI element interactions.
"""

from typing import List, Optional
from google.antigravity import types

BROWSER_WORKER_INSTRUCTIONS = """You are the specialized Browser Worker subagent for web automation.
Your responsibility is to navigate web pages, inspect accessibility DOM snapshots, and execute precise UI interactions (clicks, form inputs, keyboard events).

STRICT OPERATING INVARIANTS:
1. RESILIENT INTERACTION CYCLE:
   Always follow the strict 4-step execution flow:
   a) NAVIGATE: Use `navigate_page` or `new_page` to open target URLs.
   b) WAIT: Use `wait_for` to ensure critical text, elements, or loading states are settled.
   c) SNAPSHOT: Use `take_snapshot` to capture the current accessibility tree and obtain valid element `uid`s.
   d) INTERACT: Use element `uid`s strictly from the latest snapshot for `click`, `fill`, `fill_form`, `hover`, or `drag`.

2. ACCESSIBILITY UIDS:
   - NEVER guess or fabricate element `uid`s.
   - Element UIDs are transient and become invalid upon DOM updates or navigation.
   - Always verify the element exists in your latest snapshot before triggering an interaction.

3. ERROR RECOVERY:
   - If any tool fails with an "element not found" or "stale UID" error, immediately invoke `take_snapshot` to capture a fresh DOM tree and locate the new UID.
"""

WORKER_DEFAULT_TOOLS: List[str] = [
    "navigate_page",
    "wait_for",
    "take_snapshot",
    "click",
    "fill",
    "fill_form",
    "take_screenshot",
    "list_pages",
    "select_page",
    "new_page",
    "close_page",
]


def create_browser_worker_config(
    tools: Optional[List[str]] = None,
    system_instructions: Optional[str] = None,
) -> types.SubagentConfig:
    """
    Constructs the SubagentConfig for the Browser Worker subagent.

    Args:
        tools: Optional list of MCP tools exposed to the worker. Defaults to WORKER_DEFAULT_TOOLS.
        system_instructions: Optional override for system instructions.

    Returns:
        types.SubagentConfig instance.
    """
    return types.SubagentConfig(
        name="browser_worker",
        description="Specialized subagent for web page navigation, accessibility snapshot inspection, and DOM interaction.",
        system_instructions=system_instructions or BROWSER_WORKER_INSTRUCTIONS,
        tools=tools if tools is not None else WORKER_DEFAULT_TOOLS,
        capabilities=types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
        ),
    )
