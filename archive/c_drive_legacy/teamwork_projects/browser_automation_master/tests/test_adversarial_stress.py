"""
test_adversarial_stress.py
==========================
Adversarial stress-testing suite for Browser Automation Master.
Empirically tests edge cases, failure modes, cross-platform resolution,
and schema invariants against the implementation.
"""

import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock
from typing import Any

from google.antigravity import LocalAgentConfig, types
from google.antigravity.hooks import hooks

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
from browser_master.mcp_config import configure_mcp_safety_policies
from browser_master.middleware import DOM_ERROR_KEYWORDS


class DummyContext(hooks.HookContext):
    """Context object with configurable tool_name and attributes."""
    def __init__(self, tool_name: Any = "click"):
        self.tool_name = tool_name


class EmptyContext(hooks.HookContext):
    """Context object with no tool_name attribute."""
    pass


class TestElementNotFoundRecoveryHookStress(unittest.IsolatedAsyncioTestCase):
    """Adversarial stress testing of ElementNotFoundRecoveryHook."""

    async def asyncSetUp(self):
        self.hook = ElementNotFoundRecoveryHook(max_retries=3)

    async def test_required_dom_error_phrases(self):
        """Verify all mandatory DOM error exceptions trigger recovery prompts."""
        ctx = DummyContext("click")

        mandatory_errors = [
            'Element with uid "123" not found',
            'Stale element reference',
            'Target closed',
            'Timeout waiting for selector',
        ]

        for err_msg in mandatory_errors:
            with self.subTest(error=err_msg):
                res = await self.hook.run(ctx, Exception(err_msg))
                self.assertIsNotNone(res, f"Failed to intercept mandatory DOM error: {err_msg}")
                self.assertIn("[RECOVERY PROTOCOL ACTIVATED]", res)
                self.assertIn("take_snapshot", res)
                self.assertIn("click", res)
                self.assertIn(err_msg, res)

    async def test_case_insensitivity_and_variations(self):
        """Verify case insensitivity across diverse DOM error formulations."""
        ctx = DummyContext("fill")

        error_variations = [
            'ELEMENT WITH UID "123" NOT FOUND',
            'stale ELEMENT REFERENCE IN PAGE CONTEXT',
            'TARGET CLOSED UNEXPECTEDLY',
            'TIMEOUT WAITING FOR SELECTOR "#submit-btn"',
            'No element matching selector .btn-primary',
            'Could not find element with id main-frame',
            'Cannot find context with specified id',
            'Invalid node id provided for interaction',
            'Node is detached from document',
            'No node with given id found',
        ]

        for err_msg in error_variations:
            with self.subTest(error=err_msg):
                res = await self.hook.run(ctx, RuntimeError(err_msg))
                self.assertIsNotNone(res, f"Failed on variation: {err_msg}")
                self.assertIn("take_snapshot", res)
                self.assertIn("fill", res)

    async def test_non_dom_errors_pass_through(self):
        """Verify non-DOM errors return None and do not inject recovery prompts."""
        ctx = DummyContext("navigate_page")

        non_dom_errors = [
            "NetworkConnectionRefused: Port 9999 closed",
            "AuthenticationError: Invalid API Key provided",
            "OutOfMemoryError: Browser process exceeded heap limit",
            "SyntaxError in user script evaluation",
            "PermissionDenied: File system access restricted",
            "RateLimitExceeded: 429 Too Many Requests",
            "Disk full: Cannot write screenshot to disk",
        ]

        for err_msg in non_dom_errors:
            with self.subTest(error=err_msg):
                res = await self.hook.run(ctx, Exception(err_msg))
                self.assertIsNone(res, f"Non-DOM error should return None: {err_msg}")

    async def test_edge_case_contexts(self):
        """Verify hook handles context anomalies gracefully."""
        # 1. Context without tool_name attribute
        empty_ctx = EmptyContext()
        res = await self.hook.run(empty_ctx, Exception('Element with uid "999" not found'))
        self.assertIsNotNone(res)
        self.assertIn("unknown_tool", res)

        # 2. Context with tool_name = None
        none_ctx = DummyContext(tool_name=None)
        res = await self.hook.run(none_ctx, Exception('Element with uid "999" not found'))
        self.assertIsNotNone(res)
        self.assertIn("None", res)

        # 3. Context with non-string tool_name
        int_ctx = DummyContext(tool_name=42)
        res = await self.hook.run(int_ctx, Exception('Element with uid "999" not found'))
        self.assertIsNotNone(res)
        self.assertIn("42", res)

    async def test_non_standard_data_payloads(self):
        """Verify hook handles non-Exception data payloads."""
        ctx = DummyContext("evaluate_script")

        # String error payload
        res = await self.hook.run(ctx, "Error: stale element reference in DOM")
        self.assertIsNotNone(res)
        self.assertIn("take_snapshot", res)

        # Custom object with __str__ containing DOM error
        class CustomErrorObj:
            def __str__(self):
                return "CustomError: Element with uid 'x' not found"

        res = await self.hook.run(ctx, CustomErrorObj())
        self.assertIsNotNone(res)
        self.assertIn("take_snapshot", res)


class TestNpxResolutionCrossPlatform(unittest.TestCase):
    """Adversarial cross-platform simulation of get_npx_executable."""

    def test_windows_resolution_order(self):
        """Verify npx resolution behavior on Windows (os.name == 'nt')."""
        with patch("os.name", "nt"):
            # Case 1: npx.cmd found
            with patch("shutil.which", side_effect=lambda cmd: "C:\\nodejs\\npx.cmd" if cmd == "npx.cmd" else None):
                result = get_npx_executable()
                self.assertEqual(result, "C:\\nodejs\\npx.cmd")

            # Case 2: npx.cmd is None, npx.CMD found
            with patch("shutil.which", side_effect=lambda cmd: "C:\\nodejs\\npx.CMD" if cmd == "npx.CMD" else None):
                result = get_npx_executable()
                self.assertEqual(result, "C:\\nodejs\\npx.CMD")

            # Case 3: npx.cmd and npx.CMD are None, bare npx found
            with patch("shutil.which", side_effect=lambda cmd: "C:\\nodejs\\npx.exe" if cmd == "npx" else None):
                result = get_npx_executable()
                self.assertEqual(result, "C:\\nodejs\\npx.exe")

            # Case 4: No executable found on PATH -> fallback to 'npx.cmd'
            with patch("shutil.which", return_value=None):
                result = get_npx_executable()
                self.assertEqual(result, "npx.cmd")

    def test_posix_resolution_order(self):
        """Verify npx resolution behavior on POSIX (os.name == 'posix')."""
        with patch("os.name", "posix"):
            # Case 1: npx found on PATH
            with patch("shutil.which", side_effect=lambda cmd: "/usr/local/bin/npx" if cmd == "npx" else None):
                result = get_npx_executable()
                self.assertEqual(result, "/usr/local/bin/npx")

            # Case 2: npx not on PATH -> fallback to 'npx'
            with patch("shutil.which", return_value=None):
                result = get_npx_executable()
                self.assertEqual(result, "npx")

    def test_darwin_resolution(self):
        """Verify npx resolution behavior on Darwin / other non-nt systems."""
        with patch("os.name", "darwin"):
            with patch("shutil.which", side_effect=lambda cmd: "/opt/homebrew/bin/npx" if cmd == "npx" else None):
                result = get_npx_executable()
                self.assertEqual(result, "/opt/homebrew/bin/npx")


class TestAgentConfigOverridesAndSchemas(unittest.TestCase):
    """Stress testing of configuration schemas, overrides, and Pydantic validation."""

    def test_default_master_agent_config(self):
        """Verify default master agent configuration structure and invariants."""
        config = create_master_agent_config()
        self.assertIsInstance(config, LocalAgentConfig)
        self.assertEqual(len(config.mcp_servers), 1)
        self.assertEqual(config.mcp_servers[0].name, "chrome_devtools")
        self.assertIn("--headless", config.mcp_servers[0].args)
        self.assertIn("chrome-devtools-mcp@latest", config.mcp_servers[0].args)

        # Capabilities
        self.assertTrue(config.capabilities.enable_subagents)
        self.assertEqual(config.capabilities.agent_behavior, types.AgentBehavior.AUTONOMOUS)
        self.assertEqual(config.capabilities.max_subagent_depth, 2)
        self.assertEqual(set(config.capabilities.allowed_subagents), {"browser_worker", "dom_extractor"})

        # Subagents
        self.assertEqual(len(config.subagents), 2)
        subagent_names = {s.name for s in config.subagents}
        self.assertEqual(subagent_names, {"browser_worker", "dom_extractor"})

        # Hooks and Policies
        self.assertTrue(any(isinstance(h, ElementNotFoundRecoveryHook) for h in config.hooks))
        self.assertTrue(any(isinstance(h, BrowserAuditTraceHook) for h in config.hooks))
        self.assertTrue(len(config.policies) > 0)

    def test_custom_overrides(self):
        """Verify headless=False, custom instructions, api_key, additional args, and app_data_dir."""
        custom_instructions = "Custom Master Instructions - Do Not Deviate"
        custom_key = "test-api-key-12345-override"
        custom_mcp_args = ["--viewport-size=1920,1080", "--user-data-dir=/tmp/profile"]
        custom_data_dir = "C:\\custom\\app_data"

        config = create_master_agent_config(
            headless=False,
            system_instructions=custom_instructions,
            api_key=custom_key,
            additional_mcp_args=custom_mcp_args,
            app_data_dir=custom_data_dir,
        )

        # Headless False check
        self.assertNotIn("--headless", config.mcp_servers[0].args)

        # Additional MCP CLI flags
        self.assertIn("--viewport-size=1920,1080", config.mcp_servers[0].args)
        self.assertIn("--user-data-dir=/tmp/profile", config.mcp_servers[0].args)

        # System instructions
        self.assertEqual(config.system_instructions, custom_instructions)

        # API Key
        self.assertEqual(config.api_key, custom_key)

        # App Data Dir
        self.assertEqual(config.app_data_dir, custom_data_dir)

    def test_subagent_overrides(self):
        """Verify customization of subagent tools and system instructions."""
        custom_worker_tools = ["navigate_page", "click"]
        custom_worker_inst = "Custom Worker Instructions"
        worker = create_browser_worker_config(
            tools=custom_worker_tools,
            system_instructions=custom_worker_inst,
        )
        self.assertEqual(worker.name, "browser_worker")
        self.assertEqual(worker.tools, custom_worker_tools)
        self.assertEqual(worker.system_instructions, custom_worker_inst)
        self.assertEqual(worker.capabilities.agent_behavior, types.AgentBehavior.AUTONOMOUS)

        custom_ext_tools = ["evaluate_script"]
        custom_ext_inst = "Custom Extractor Instructions"
        extractor = create_extractor_config(
            tools=custom_ext_tools,
            system_instructions=custom_ext_inst,
        )
        self.assertEqual(extractor.name, "dom_extractor")
        self.assertEqual(extractor.tools, custom_ext_tools)
        self.assertEqual(extractor.system_instructions, custom_ext_inst)
        self.assertEqual(extractor.capabilities.agent_behavior, types.AgentBehavior.AUTONOMOUS)

    def test_mcp_tools_and_policy_variations(self):
        """Verify custom MCP server enabled tools and safety policy configurations."""
        custom_tools = ["navigate_page", "take_snapshot"]
        mcp = create_chrome_devtools_mcp(headless=True, enabled_tools=custom_tools)
        self.assertEqual(mcp.enabled_tools, custom_tools)

        policies_all = configure_mcp_safety_policies(None)
        self.assertTrue(len(policies_all) >= 1)

        policies_server = configure_mcp_safety_policies(mcp)
        self.assertTrue(len(policies_server) >= 1)

    def test_browser_master_instantiation(self):
        """Verify BrowserMaster wrapper class initialization under various configurations."""
        # Default
        bm1 = BrowserMaster(headless=True)
        self.assertTrue(bm1.headless)
        self.assertIn("--headless", bm1.config.mcp_servers[0].args)

        # Headless False with custom key
        bm2 = BrowserMaster(headless=False, api_key="sk-test-fake")
        self.assertFalse(bm2.headless)
        self.assertEqual(bm2.api_key, "sk-test-fake")
        self.assertNotIn("--headless", bm2.config.mcp_servers[0].args)

        # Pre-constructed config
        custom_cfg = create_master_agent_config(system_instructions="Preconstructed")
        bm3 = BrowserMaster(config=custom_cfg)
        self.assertEqual(bm3.config.system_instructions, "Preconstructed")


class TestBrowserAuditTraceHookStress(unittest.IsolatedAsyncioTestCase):
    """Stress testing of BrowserAuditTraceHook."""

    async def test_trace_hook_execution(self):
        hook = BrowserAuditTraceHook()
        ctx = DummyContext("take_snapshot")
        # Should execute cleanly without throwing
        await hook.run(ctx, {"status": "ok"})

        # Context with missing attributes
        empty_ctx = EmptyContext()
        await hook.run(empty_ctx, None)


if __name__ == "__main__":
    unittest.main()
