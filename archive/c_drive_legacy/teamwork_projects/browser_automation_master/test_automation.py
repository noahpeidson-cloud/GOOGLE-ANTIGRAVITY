"""
test_automation.py
==================
Comprehensive automated verification suite for Browser Automation Master.

Tests include:
1. MCP configuration and cross-platform executable resolution.
2. Resilient Error Recovery Hook unit testing (DOM / Stale UID error interception).
3. Subagent and Master Agent configuration schema validations.
4. End-to-end browser automation execution navigating to https://example.com
   and extracting <h1>Example Domain</h1>.
"""

import asyncio
import logging
import os
import sys
from typing import Any
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

from browser_master import (
    BrowserMaster,
    create_master_agent_config,
    create_chrome_devtools_mcp,
    get_npx_executable,
    BROWSER_AUTOMATION_TOOLS,
    ElementNotFoundRecoveryHook,
    BrowserAuditTraceHook,
    create_browser_worker_config,
    create_extractor_config,
)
from google.antigravity.hooks import hooks

# Configure logging with ASCII-safe formatting
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("test_automation")


class DummyHookContext(hooks.HookContext):
    """Context object for testing lifecycle hooks."""
    def __init__(self, tool_name: str = "click"):
        self.tool_name = tool_name


def test_mcp_configuration():
    """Validates MCP configuration factory and executable resolution."""
    logger.info("--- [TEST 1] Validating MCP Configuration ---")
    
    npx_exe = get_npx_executable()
    logger.info(f"Resolved npx executable: {npx_exe}")
    assert npx_exe, "npx executable must not be empty"

    mcp = create_chrome_devtools_mcp(headless=True)
    assert mcp.name == "chrome_devtools"
    assert mcp.command == npx_exe
    assert "--headless" in mcp.args
    assert "chrome-devtools-mcp@latest" in mcp.args
    assert set(BROWSER_AUTOMATION_TOOLS).issubset(set(mcp.enabled_tools))
    
    logger.info("[PASSED] [TEST 1] MCP configuration matches specification.")


async def test_error_recovery_middleware():
    """Validates that ElementNotFoundRecoveryHook intercepts DOM errors and provides guidance."""
    logger.info("--- [TEST 2] Validating Resilient Error Recovery Hook ---")
    
    hook = ElementNotFoundRecoveryHook(max_retries=3)
    ctx = DummyHookContext(tool_name="click")

    # Test 1: Element not found error
    dom_error = Exception("Error: Element with uid 'node-1234' not found")
    recovery_guidance = await hook.run(ctx, dom_error)
    assert recovery_guidance is not None, "Hook must intercept element-not-found errors"
    assert "RECOVERY PROTOCOL ACTIVATED" in recovery_guidance
    assert "take_snapshot" in recovery_guidance
    logger.info("Intercepted element-not-found error successfully.")

    # Test 2: Stale UID error
    stale_error = Exception("Failed: Stale UID reference in page context")
    recovery_guidance = await hook.run(ctx, stale_error)
    assert recovery_guidance is not None
    assert "take_snapshot" in recovery_guidance
    logger.info("Intercepted stale-UID error successfully.")

    # Test 3: Unrelated error (should NOT be transformed into snapshot recovery)
    generic_error = Exception("NetworkConnectionRefused: Port 9999 closed")
    unrelated_res = await hook.run(ctx, generic_error)
    assert unrelated_res is None, "Non-DOM errors must not trigger snapshot recovery"
    logger.info("Passed through non-DOM error correctly.")

    logger.info("[PASSED] [TEST 2] Error Recovery Middleware functions correctly.")


def test_subagents_and_master_config():
    """Validates subagent definitions and Master Agent configuration."""
    logger.info("--- [TEST 3] Validating Subagents & Agent Config ---")
    
    worker = create_browser_worker_config()
    assert worker.name == "browser_worker"
    assert "navigate_page" in worker.tools
    assert "take_snapshot" in worker.tools
    assert "click" in worker.tools
    logger.info("Verified browser_worker subagent configuration.")

    extractor = create_extractor_config()
    assert extractor.name == "dom_extractor"
    assert "evaluate_script" in extractor.tools
    assert "take_snapshot" in extractor.tools
    logger.info("Verified dom_extractor subagent configuration.")

    config = create_master_agent_config(headless=True)
    assert len(config.mcp_servers) == 1
    assert len(config.subagents) == 2
    assert config.capabilities.enable_subagents is True
    assert "browser_worker" in config.capabilities.allowed_subagents
    assert "dom_extractor" in config.capabilities.allowed_subagents
    assert any(isinstance(h, ElementNotFoundRecoveryHook) for h in config.hooks)
    assert any(isinstance(h, BrowserAuditTraceHook) for h in config.hooks)
    
    logger.info("[PASSED] [TEST 3] Agent and Subagent configurations are valid.")


async def test_example_domain_live_execution():
    """
    End-to-End Verification Test:
    Executes live master agent task against https://example.com and extracts <h1> text.
    """
    logger.info("--- [TEST 4] End-to-End Live Browser Automation Verification ---")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning(
            "[SKIP] GEMINI_API_KEY is not set in environment or .env. "
            "Skipping live LLM invocation test. Set GEMINI_API_KEY to run full end-to-end browser execution."
        )
        return True

    master = BrowserMaster(headless=True)
    prompt = (
        "Perform the following web automation task:\n"
        "1. Delegate to the 'browser_worker' subagent to navigate to 'https://example.com'.\n"
        "2. Wait for the page to load and take a snapshot of the DOM.\n"
        "3. Delegate to the 'dom_extractor' subagent or use evaluate_script to extract the exact text of the main <h1> heading.\n"
        "4. Return the extracted heading text clearly."
    )

    logger.info("Executing task on Master Agent...")
    try:
        result_text = await master.execute_task(prompt)
        logger.info(f"Agent Response:\n{result_text}")
        
        # Verify acceptance criteria
        assert "Example Domain" in result_text, (
            f"Verification Failure: Expected 'Example Domain' in output, but received:\n{result_text}"
        )
        logger.info("[PASSED] [TEST 4] Successfully extracted 'Example Domain' via Master Agent.")
        return True
    except Exception as e:
        logger.error(f"[FAILED] [TEST 4] Live execution encountered an error: {e}", exc_info=True)
        raise


async def run_all_tests():
    """Runs all test cases."""
    logger.info("================================================================")
    logger.info("STARTING BROWSER AUTOMATION MASTER AGENT VERIFICATION SUITE")
    logger.info("================================================================")
    
    test_mcp_configuration()
    await test_error_recovery_middleware()
    test_subagents_and_master_config()
    await test_example_domain_live_execution()
    
    logger.info("================================================================")
    logger.info("[SUCCESS] ALL TESTS COMPLETED SUCCESSFULLY!")
    logger.info("================================================================")


def main():
    try:
        asyncio.run(run_all_tests())
        sys.exit(0)
    except Exception as e:
        logger.critical(f"FATAL: Test verification suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
