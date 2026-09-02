"""
browser_master.mcp_config
=========================
Chrome DevTools MCP server configuration and process management for Google Antigravity SDK.
Handles cross-platform (Windows & POSIX) executable resolution, command arguments,
and tool policy definitions.
"""

import os
import shutil
from typing import List, Optional
from google.antigravity import types
from google.antigravity.hooks import policy

# Core tools required for robust, headless browser automation
BROWSER_AUTOMATION_TOOLS: List[str] = [
    "navigate_page",
    "wait_for",
    "take_snapshot",
    "click",
    "fill",
    "fill_form",
    "evaluate_script",
    "take_screenshot",
    "list_pages",
    "select_page",
    "new_page",
    "close_page",
]


def get_npx_executable() -> str:
    """
    Resolves the platform-specific npx executable path.

    On Windows, direct execution of bare 'npx' can trigger PowerShell script execution
    policy restrictions on 'npx.ps1'. This function resolves 'npx.cmd' or the full path.
    """
    if os.name == "nt":
        # Windows resolution: prefer .cmd wrapper
        return shutil.which("npx.cmd") or shutil.which("npx.CMD") or shutil.which("npx") or "npx.cmd"
    
    # POSIX resolution
    return shutil.which("npx") or "npx"


def create_chrome_devtools_mcp(
    headless: bool = True,
    additional_args: Optional[List[str]] = None,
    enabled_tools: Optional[List[str]] = None,
) -> types.McpStdioServer:
    """
    Instantiates the Chrome DevTools MCP Stdio configuration for Google Antigravity.

    Args:
        headless: If True, launches Chrome in headless mode without UI windows.
        additional_args: Optional list of additional CLI flags passed to chrome-devtools-mcp.
        enabled_tools: Optional custom list of enabled tools. Defaults to BROWSER_AUTOMATION_TOOLS.

    Returns:
        types.McpStdioServer configured for Chrome DevTools.
    """
    npx_bin = get_npx_executable()
    
    args = ["-y", "chrome-devtools-mcp@latest"]
    if headless:
        args.append("--headless")
    
    if additional_args:
        args.extend(additional_args)

    tools = enabled_tools if enabled_tools is not None else BROWSER_AUTOMATION_TOOLS

    return types.McpStdioServer(
        name="chrome_devtools",
        command=npx_bin,
        args=args,
        enabled_tools=tools,
    )


def configure_mcp_safety_policies(mcp_server: Optional[types.McpStdioServer] = None):
    """
    Configures safety policies for the master agent, granting permissions
    to execute browser automation tools.

    Args:
        mcp_server: Optional McpStdioServer instance to grant targeted access to.

    Returns:
        List of policy rules permitting execution.
    """
    if mcp_server is not None:
        return [policy.allow(mcp_server)]
    return [policy.allow_all()]
