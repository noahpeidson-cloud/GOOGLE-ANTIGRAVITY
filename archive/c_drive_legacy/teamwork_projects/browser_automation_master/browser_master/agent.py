"""
browser_master.agent
====================
Master Agent orchestrator for browser automation using Google Antigravity SDK.
Manages subagent delegation, Chrome DevTools MCP lifecycle, and resilient task execution.
"""

import os
from typing import List, Optional
from google.antigravity import Agent, LocalAgentConfig, types
from browser_master.mcp_config import (
    create_chrome_devtools_mcp,
    configure_mcp_safety_policies,
)
from browser_master.middleware import (
    ElementNotFoundRecoveryHook,
    BrowserAuditTraceHook,
)
from browser_master.subagents.browser_worker import create_browser_worker_config
from browser_master.subagents.extractor import create_extractor_config

MASTER_AGENT_INSTRUCTIONS = """You are the Master Browser Automation Orchestrator.
Your mission is to coordinate complex web workflows by delegating tasks to specialized subagents:
- Delegate navigation, page setup, clicking, and form submissions to `browser_worker`.
- Delegate DOM inspection, JavaScript scraping, and text extraction to `dom_extractor`.

ORCHESTRATION DIRECTIVES:
1. DELEGATION FIRST: Always delegate web interactions to the appropriate subagent (`browser_worker` or `dom_extractor`).
2. RESILIENCE: Enforce the 'navigate -> wait -> snapshot -> interact' workflow.
3. SYNTHESIS: Gather responses and extracted data from subagents, verify correctness, and present a clear, structured final answer.
"""


def create_master_agent_config(
    headless: bool = True,
    system_instructions: Optional[str] = None,
    api_key: Optional[str] = None,
    additional_mcp_args: Optional[List[str]] = None,
    app_data_dir: Optional[str] = None,
) -> LocalAgentConfig:
    """
    Constructs the LocalAgentConfig for the Master Browser Automation Agent.

    Args:
        headless: Whether Chrome DevTools runs in headless mode. Defaults to True.
        system_instructions: Optional custom root instructions for the orchestrator.
        api_key: Optional Gemini API key. If omitted, uses GEMINI_API_KEY from environment.
        additional_mcp_args: Optional list of additional CLI flags passed to chrome-devtools-mcp.
        app_data_dir: Optional application metadata directory.

    Returns:
        LocalAgentConfig fully configured with subagents, MCP servers, hooks, and policies.
    """
    mcp_server = create_chrome_devtools_mcp(
        headless=headless,
        additional_args=additional_mcp_args,
    )
    
    worker_subagent = create_browser_worker_config()
    extractor_subagent = create_extractor_config()
    
    hooks_list = [
        ElementNotFoundRecoveryHook(),
        BrowserAuditTraceHook(),
    ]
    
    policies_list = configure_mcp_safety_policies(mcp_server)

    effective_api_key = api_key or os.environ.get("GEMINI_API_KEY")

    config_kwargs = {
        "system_instructions": system_instructions or MASTER_AGENT_INSTRUCTIONS,
        "mcp_servers": [mcp_server],
        "subagents": [worker_subagent, extractor_subagent],
        "capabilities": types.CapabilitiesConfig(
            enable_subagents=True,
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
            max_subagent_depth=2,
            allowed_subagents=["browser_worker", "dom_extractor"],
        ),
        "hooks": hooks_list,
        "policies": policies_list,
    }

    if effective_api_key:
        config_kwargs["api_key"] = effective_api_key

    if app_data_dir:
        config_kwargs["app_data_dir"] = app_data_dir

    return LocalAgentConfig(**config_kwargs)


class BrowserMaster:
    """
    High-level asynchronous interface for running browser automation workflows.
    Encapsulates the Antigravity Agent lifecycle and Chrome DevTools MCP connection.
    """

    def __init__(
        self,
        headless: bool = True,
        api_key: Optional[str] = None,
        config: Optional[LocalAgentConfig] = None,
    ):
        """
        Initializes the BrowserMaster instance.

        Args:
            headless: Whether to run Chrome in headless mode (default: True).
            api_key: Optional Gemini API key.
            config: Optional pre-constructed LocalAgentConfig.
        """
        self.headless = headless
        self.api_key = api_key
        self.config = config or create_master_agent_config(
            headless=headless,
            api_key=api_key,
        )

    async def execute_task(self, prompt: str) -> str:
        """
        Executes a browser automation prompt through the Master Agent.

        Args:
            prompt: Task instructions (e.g. navigate to URL, extract text, fill form).

        Returns:
            The text response from the Master Agent upon workflow completion.
        """
        async with Agent(config=self.config) as agent:
            response = await agent.chat(prompt)
            return await response.text()

    async def run(self, prompt: str) -> str:
        """Alias for execute_task."""
        return await self.execute_task(prompt)
