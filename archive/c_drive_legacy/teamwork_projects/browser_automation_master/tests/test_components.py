"""Unit tests for browser_automation_master package."""
import asyncio
import os
import unittest
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


class DummyContext(hooks.HookContext):
    def __init__(self, tool_name: str = "click"):
        self.tool_name = tool_name


class TestBrowserMasterComponents(unittest.TestCase):
    def test_npx_resolution(self):
        npx_bin = get_npx_executable()
        self.assertTrue(bool(npx_bin))
        if os.name == "nt":
            self.assertTrue("npx" in npx_bin.lower())

    def test_mcp_config(self):
        mcp = create_chrome_devtools_mcp(headless=True)
        self.assertEqual(mcp.name, "chrome_devtools")
        self.assertIn("--headless", mcp.args)
        self.assertIn("chrome-devtools-mcp@latest", mcp.args)
        for tool in BROWSER_AUTOMATION_TOOLS:
            self.assertIn(tool, mcp.enabled_tools)

    def test_subagent_configs(self):
        worker = create_browser_worker_config()
        self.assertEqual(worker.name, "browser_worker")
        self.assertIn("navigate_page", worker.tools)
        self.assertIn("take_snapshot", worker.tools
        )
        extractor = create_extractor_config()
        self.assertEqual(extractor.name, "dom_extractor")
        self.assertIn("evaluate_script", extractor.tools)

    def test_master_agent_config(self):
        config = create_master_agent_config(headless=True)
        self.assertEqual(len(config.mcp_servers), 1)
        self.assertEqual(len(config.subagents), 2)
        self.assertTrue(config.capabilities.enable_subagents)
        self.assertIn("browser_worker", config.capabilities.allowed_subagents)
        self.assertIn("dom_extractor", config.capabilities.allowed_subagents)

    def test_error_recovery_hook(self):
        async def run_hook():
            hook = ElementNotFoundRecoveryHook()
            ctx = DummyContext("click")
            
            # Element not found
            res = await hook.run(ctx, Exception("Element with uid 'foo' not found"))
            self.assertIsNotNone(res)
            self.assertIn("take_snapshot", res)
            
            # Unrelated error
            unrelated = await hook.run(ctx, Exception("Disk full"))
            self.assertIsNone(unrelated)

        asyncio.run(run_hook())


if __name__ == "__main__":
    unittest.main()
