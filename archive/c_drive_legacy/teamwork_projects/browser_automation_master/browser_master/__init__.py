"""
browser_master
==============
A resilient browser automation orchestrator built on the Google Antigravity SDK
and Chrome DevTools MCP.
"""

from browser_master.agent import BrowserMaster, create_master_agent_config
from browser_master.mcp_config import (
    create_chrome_devtools_mcp,
    get_npx_executable,
    configure_mcp_safety_policies,
    BROWSER_AUTOMATION_TOOLS,
)
from browser_master.middleware import (
    ElementNotFoundRecoveryHook,
    BrowserAuditTraceHook,
)
from browser_master.subagents import (
    create_browser_worker_config,
    create_extractor_config,
)

__all__ = [
    "BrowserMaster",
    "create_master_agent_config",
    "create_chrome_devtools_mcp",
    "get_npx_executable",
    "configure_mcp_safety_policies",
    "BROWSER_AUTOMATION_TOOLS",
    "ElementNotFoundRecoveryHook",
    "BrowserAuditTraceHook",
    "create_browser_worker_config",
    "create_extractor_config",
]

__version__ = "1.0.0"
