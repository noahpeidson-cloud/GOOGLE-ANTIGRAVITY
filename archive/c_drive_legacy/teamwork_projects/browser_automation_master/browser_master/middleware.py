"""
browser_master.middleware
=========================
Resilient error-handling hooks and telemetry middleware for browser automation.
Catches DOM errors, stale UIDs, and timeout exceptions to guide self-healing interaction loops.
"""

import logging
from typing import Any, Optional, Set
from google.antigravity.hooks import hooks

logger = logging.getLogger("browser_master.middleware")

# Keywords in tool error messages that signal DOM detachment, missing nodes, or stale UIDs
DOM_ERROR_KEYWORDS: Set[str] = {
    "uid",
    "not found",
    "element not found",
    "no element matching",
    "could not find element",
    "stale",
    "selector",
    "timeout",
    "no node",
    "target closed",
    "detached",
    "cannot find context",
    "invalid node id",
}


class ElementNotFoundRecoveryHook(hooks.OnToolErrorHook):
    """
    Lifecycle hook that intercepts tool execution failures in Chrome DevTools MCP.
    When a subagent attempts an action with a stale, expired, or missing element UID,
    this hook intercepts the exception and injects actionable recovery instructions
    forcing a fresh `take_snapshot` call rather than failing the session.
    """

    def __init__(self, max_retries: int = 3):
        super().__init__()
        self.max_retries = max_retries

    async def run(self, context: hooks.HookContext, data: Any) -> Optional[str]:
        """
        Processes tool execution errors and returns recovery guidance when DOM errors occur.

        Args:
            context: The HookContext containing execution metadata.
            data: The exception or error payload produced by the failed tool call.

        Returns:
            A string containing recovery guidance for DOM errors, or None to retain default handling.
        """
        error_msg = str(data)
        tool_name = getattr(context, "tool_name", "unknown_tool")
        
        logger.warning(
            f"[BrowserMiddleware] Intercepted tool error in '{tool_name}': {error_msg}"
        )

        error_lower = error_msg.lower()
        is_dom_error = any(keyword in error_lower for keyword in DOM_ERROR_KEYWORDS)

        if is_dom_error:
            recovery_prompt = (
                f"[RECOVERY PROTOCOL ACTIVATED] The browser action '{tool_name}' encountered a DOM error: '{error_msg}'.\n"
                "The target element was not found, the element UID has expired, or the DOM structure mutated.\n"
                "MANDATORY RECOVERY STEPS:\n"
                "1. DO NOT retry using the previous element UID.\n"
                "2. Call 'take_snapshot' immediately to capture a fresh accessibility snapshot of the current DOM.\n"
                "3. Locate the updated element UID in the fresh snapshot.\n"
                "4. Re-execute the interaction ('click', 'fill', 'evaluate_script') with the confirmed UID."
            )
            logger.info(
                f"[BrowserMiddleware] Injected self-healing recovery prompt for tool '{tool_name}'."
            )
            return recovery_prompt

        # For non-DOM errors (e.g. system network crashes), pass through
        return None


class BrowserAuditTraceHook(hooks.PostToolCallHook):
    """
    Telemetry and audit hook that logs tool execution lifecycle events.
    Enables forensic debugging and observability of browser automation workflows.
    """

    async def run(self, context: hooks.HookContext, data: Any) -> None:
        """
        Logs successful or completed tool executions.
        """
        tool_name = getattr(context, "tool_name", "unknown_tool")
        logger.debug(
            f"[BrowserAuditTrace] Tool '{tool_name}' executed successfully. Context state: {getattr(context, 'state', None)}"
        )
