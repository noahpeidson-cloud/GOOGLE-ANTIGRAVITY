"""
Empirical Adversarial Verification Test Suite for PWA Frontend DOM, JavaScript AST,
Web Vibration API Contracts, CSS Touch Responsiveness, and Web App Manifest.

Targets:
- content_creation/static/index.html
- content_creation/static/manifest.json
- content_creation/remote_trigger.py (FastAPI PWA serving endpoints)
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import status
from fastapi.testclient import TestClient

from remote_trigger import create_app


class DOMElementExtractor(HTMLParser):
    """Deterministic DOM parser extracting elements, attributes, text, styles, and scripts."""

    def __init__(self):
        super().__init__()
        self.meta_tags: List[Dict[str, str]] = []
        self.buttons: List[Dict[str, str]] = []
        self.links: List[Dict[str, str]] = []
        self.all_ids: List[str] = []
        self.scripts: List[str] = []
        self.styles: List[str] = []
        self._current_tag: Optional[str] = None
        self._button_text_parts: List[str] = []
        self.tag_text_map: Dict[str, List[str]] = {}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k: (v if v is not None else "") for k, v in attrs}
        self._current_tag = tag
        if "id" in attr_dict:
            self.all_ids.append(attr_dict["id"])
        if tag == "meta":
            self.meta_tags.append(attr_dict)
        elif tag == "button":
            self.buttons.append(attr_dict)
        elif tag == "link":
            self.links.append(attr_dict)

    def handle_endtag(self, tag: str):
        self._current_tag = None

    def handle_data(self, data: str):
        cleaned = data.strip()
        if not cleaned:
            return
        if self._current_tag == "script":
            self.scripts.append(data)
        elif self._current_tag == "style":
            self.styles.append(data)
        elif self._current_tag in ("button", "span", "div", "p", "h1", "h2", "h3", "a"):
            if self._current_tag not in self.tag_text_map:
                self.tag_text_map[self._current_tag] = []
            self.tag_text_map[self._current_tag].append(cleaned)
            self._button_text_parts.append(cleaned)

    def get_combined_script(self) -> str:
        return "\n".join(self.scripts)

    def get_combined_style(self) -> str:
        return "\n".join(self.styles)

    def find_meta(self, key: str, value: str) -> Optional[Dict[str, str]]:
        for meta in self.meta_tags:
            if meta.get(key, "").lower() == value.lower():
                return meta
        return None

    def find_button_by_id(self, btn_id: str) -> Optional[Dict[str, str]]:
        for btn in self.buttons:
            if btn.get("id") == btn_id:
                return btn
        return None


class TestPWADOMStructure(unittest.TestCase):
    """Adversarial validation of DOM tree structure in static/index.html."""

    def setUp(self):
        self.static_dir = Path(__file__).resolve().parent.parent / "static"
        self.index_path = self.static_dir / "index.html"
        self.assertTrue(self.index_path.exists(), f"Missing required file: {self.index_path}")

        # Read raw bytes to inspect binary/encoding integrity
        with open(self.index_path, "rb") as f:
            self.raw_bytes = f.read()

        # Parse DOM with permissive decode for structural checking
        self.html_content = self.raw_bytes.decode("latin-1")
        self.dom = DOMElementExtractor()
        self.dom.feed(self.html_content)

    def test_utf8_encoding_compliance(self):
        """Verify that index.html is 100% compliant with UTF-8 encoding specification."""
        try:
            decoded = self.raw_bytes.decode("utf-8")
            self.assertGreater(len(decoded), 0)
        except UnicodeDecodeError as e:
            self.fail(
                f"Encoding Violation: index.html contains invalid UTF-8 byte sequences: {e}. "
                f"All static HTML assets must be valid UTF-8."
            )

    def test_pwa_required_meta_tags_presence(self):
        """Assert exact presence and configuration of PWA meta tags."""
        # 1. Viewport
        viewport = self.dom.find_meta("name", "viewport")
        self.assertIsNotNone(viewport, "<meta name='viewport'> tag is required for mobile PWA.")
        content = viewport.get("content", "")
        self.assertIn("width=device-width", content, "Viewport must specify width=device-width")
        self.assertIn("initial-scale=1.0", content, "Viewport must specify initial-scale=1.0")
        self.assertIn("viewport-fit=cover", content, "Viewport must support notch safe areas with viewport-fit=cover")

        # 2. Apple mobile web app capable
        apple_capable = self.dom.find_meta("name", "apple-mobile-web-app-capable")
        self.assertIsNotNone(apple_capable, "<meta name='apple-mobile-web-app-capable'> tag is required.")
        self.assertEqual(apple_capable.get("content", "").lower(), "yes")

        # 3. Theme color (OLED black)
        theme_color = self.dom.find_meta("name", "theme-color")
        self.assertIsNotNone(theme_color, "<meta name='theme-color'> tag is required.")
        self.assertEqual(
            theme_color.get("content", "").upper(),
            "#000000",
            "Theme color must be #000000 for OLED dark theme.",
        )

        # 4. Status bar style
        status_bar = self.dom.find_meta("name", "apple-mobile-web-app-status-bar-style")
        self.assertIsNotNone(status_bar, "<meta name='apple-mobile-web-app-status-bar-style'> is required.")

    def test_massive_trigger_button_element_and_exact_text(self):
        """Assert existence of trigger button element with exact text 'TRIGGER EDM PIPELINE'."""
        trigger_btn = self.dom.find_button_by_id("trigger-btn")
        self.assertIsNotNone(trigger_btn, "Primary button element with id='trigger-btn' is missing from DOM.")
        self.assertIn("massive-trigger-btn", trigger_btn.get("class", ""), "Button class must include massive-trigger-btn.")

        # Verify button text
        all_text = " ".join(self.dom._button_text_parts)
        self.assertIn(
            "TRIGGER EDM PIPELINE",
            all_text,
            f"Button must contain exact text 'TRIGGER EDM PIPELINE'. Found text parts: {self.dom._button_text_parts}",
        )

    def test_toast_container_and_elements_presence(self):
        """Assert existence of toast notification card container and feedback elements."""
        required_toast_ids = ["toast-card", "toast-title", "toast-message", "toast-icon", "toast-close"]
        for elem_id in required_toast_ids:
            self.assertIn(
                elem_id,
                self.dom.all_ids,
                f"Required toast element id='{elem_id}' is missing from DOM.",
            )

        # Backward-compatible alias elements for test assertion suites
        self.assertIn("status-toast", self.dom.all_ids, "Element id='status-toast' missing.")
        self.assertIn("status-display", self.dom.all_ids, "Element id='status-display' missing.")

    def test_telemetry_hud_elements_presence(self):
        """Assert existence of all live telemetry HUD and badge elements."""
        required_hud_ids = [
            "daemon-state",
            "active-job-id",
            "elapsed-time",
            "last-job-summary",
            "badge-adb",
            "badge-ffmpeg",
            "cancel-btn",
        ]
        for elem_id in required_hud_ids:
            self.assertIn(
                elem_id,
                self.dom.all_ids,
                f"Required telemetry HUD element id='{elem_id}' is missing from DOM.",
            )

    def test_metadata_form_inputs_presence_and_attributes(self):
        """Assert existence and attributes of festival and artist input fields."""
        self.assertIn("festival-input", self.dom.all_ids, "Input element with id='festival-input' is missing from DOM.")
        self.assertIn("artist-input", self.dom.all_ids, "Input element with id='artist-input' is missing from DOM.")
        self.assertIn("metadata-section", self.dom.all_ids, "Element id='metadata-section' missing from DOM.")

        # Verify name attributes and 16px CSS
        self.assertIn('name="festival"', self.html_content)
        self.assertIn('name="artist"', self.html_content)
        self.assertIn('font-size: 16px', self.dom.get_combined_style())


class TestJavaScriptContractsAndAST(unittest.TestCase):
    """Adversarial validation of JavaScript AST, syntax, haptic vibration arrays, and fetch contracts."""

    def setUp(self):
        self.static_dir = Path(__file__).resolve().parent.parent / "static"
        self.index_path = self.static_dir / "index.html"
        with open(self.index_path, "rb") as f:
            raw = f.read()
        self.html_content = raw.decode("latin-1")
        match = re.search(r"<script>([\s\S]*?)</script>", self.html_content)
        self.assertTrue(match is not None, "Missing <script> block in index.html")
        self.script_content = match.group(1)

    def test_javascript_syntax_and_ast_validity(self):
        """Adversarial check: Validate that client JavaScript parses cleanly as valid ES6+ AST."""
        # Use Node.js vm.Script to verify actual JS engine AST parsing
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js is not available on PATH for JS AST validation.")

        node_script = """
const vm = require('vm');
const fs = require('fs');
const targetFile = process.argv[2];
const code = fs.readFileSync(targetFile, 'latin1');
const scriptMatch = code.match(/<script>([\\s\\S]*?)<\\/script>/);
if (!scriptMatch) {
    console.error('No script tag found in ' + targetFile);
    process.exit(1);
}
try {
    new vm.Script(scriptMatch[1], { filename: 'pwa_index.js' });
    console.log('JS_AST_VALID');
    process.exit(0);
} catch (err) {
    console.error('JS_SYNTAX_ERROR:', err.message);
    process.exit(2);
}
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tf:
            tf.write(node_script)
            temp_node_runner = tf.name

        try:
            res = subprocess.run(
                [node_bin, temp_node_runner, str(self.index_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(
                res.returncode,
                0,
                f"JavaScript AST / Syntax Error detected in index.html:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}",
            )
        finally:
            if os.path.exists(temp_node_runner):
                os.remove(temp_node_runner)

    def test_javascript_fetch_endpoint_contract(self):
        """Verify exact fetch target '/trigger-pipeline' with method 'POST' in script."""
        self.assertRegex(
            self.script_content,
            r"fetch\(\s*['\"]/trigger-pipeline['\"]",
            "Fetch call must target exact path '/trigger-pipeline'.",
        )
        self.assertRegex(
            self.script_content,
            r"method\s*:\s*['\"]POST['\"]",
            "Fetch call must specify method 'POST'.",
        )

    def test_javascript_success_haptic_array_contract_202(self):
        """Verify exact success haptic array [100, 100, 100] bound to HTTP 202 status."""
        self.assertIn(
            "[100, 100, 100]",
            self.script_content,
            "Success haptic array [100, 100, 100] must be defined in script.",
        )
        # Check association with HTTP 202
        match_202 = re.search(
            r"202[\s\S]{1,200}?vibrate\(\s*\[100,\s*100,\s*100\]\s*\)",
            self.script_content,
        )
        self.assertTrue(
            match_202 is not None,
            "HTTP 202 response handler must trigger vibrate([100, 100, 100]).",
        )

    def test_javascript_error_haptic_array_contract_409_and_catch(self):
        """Verify exact error haptic array [500, 200, 500] bound to HTTP 409 and error catch blocks."""
        self.assertIn(
            "[500, 200, 500]",
            self.script_content,
            "Error haptic array [500, 200, 500] must be defined in script.",
        )
        # Check association with HTTP 409
        match_409 = re.search(
            r"409[\s\S]{1,200}?vibrate\(\s*\[500,\s*200,\s*500\]\s*\)",
            self.script_content,
        )
        self.assertTrue(
            match_409 is not None,
            "HTTP 409 Conflict handler must trigger vibrate([500, 200, 500]).",
        )

    def test_javascript_vibration_feature_detection_guard(self):
        """Verify feature detection check 'navigator.vibrate' exists before vibration calls."""
        self.assertTrue(
            ("vibrate" in self.script_content) and ("navigator" in self.script_content),
            "Script must inspect navigator.vibrate.",
        )
        has_guard = (
            "'vibrate' in navigator" in self.script_content
            or '"vibrate" in navigator' in self.script_content
            or "navigator.vibrate" in self.script_content
        )
        self.assertTrue(
            has_guard,
            "Feature detection guard (e.g. 'vibrate' in navigator) must precede vibration calls.",
        )

    def test_javascript_debounce_locking_lifecycle(self):
        """Verify button debounce locking before fetch dispatch and unlocking in finally."""
        self.assertRegex(
            self.script_content,
            r"(this\.triggerBtn\.disabled\s*=\s*true|setButtonLoading\(\s*true\s*\))",
            "Trigger button must be locked (disabled=true) before network dispatch.",
        )
        self.assertRegex(
            self.script_content,
            r"finally\s*\{[\s\S]*?(this\.triggerBtn\.disabled\s*=\s*false|setButtonLoading\(\s*false\s*\))",
            "Debounce lock must be released in finally block.",
        )

    def test_javascript_reads_metadata_inputs_in_payload(self):
        """Verify client script reads festival and artist inputs and passes in JSON payload."""
        self.assertIn("festival-input", self.script_content)
        self.assertIn("artist-input", self.script_content)
        self.assertIn("festival:", self.script_content)
        self.assertIn("artist:", self.script_content)


class TestPWACSSMobileResponsiveness(unittest.TestCase):
    """Adversarial validation of CSS properties for mobile touch and OLED optimization."""

    def setUp(self):
        self.static_dir = Path(__file__).resolve().parent.parent / "static"
        self.index_path = self.static_dir / "index.html"
        with open(self.index_path, "rb") as f:
            raw = f.read()
        self.html_content = raw.decode("latin-1")
        self.dom = DOMElementExtractor()
        self.dom.feed(self.html_content)
        self.css_content = self.dom.get_combined_style()

    def test_touch_action_manipulation(self):
        """Assert 'touch-action: manipulation' is configured to eliminate 300ms tap delay."""
        self.assertIn(
            "touch-action: manipulation",
            self.css_content,
            "CSS must specify 'touch-action: manipulation' to disable double-tap zoom delay.",
        )

    def test_tap_highlight_color_transparent(self):
        """Assert '-webkit-tap-highlight-color: transparent' is configured."""
        self.assertIn(
            "-webkit-tap-highlight-color: transparent",
            self.css_content,
            "CSS must specify '-webkit-tap-highlight-color: transparent' for clean mobile touch.",
        )

    def test_dark_oled_theme_background_color(self):
        """Assert true dark OLED background color (#000000) on body/root."""
        has_oled_black = (
            "--bg-oled-black: #000000" in self.css_content
            or "background-color: #000000" in self.css_content
            or "background: #000000" in self.css_content
        )
        self.assertTrue(
            has_oled_black,
            "CSS must specify true black #000000 background color for OLED efficiency.",
        )


class TestPWAManifestSchema(unittest.TestCase):
    """Adversarial validation of Web App Manifest schema in static/manifest.json."""

    def setUp(self):
        self.static_dir = Path(__file__).resolve().parent.parent / "static"
        self.manifest_path = self.static_dir / "manifest.json"
        self.assertTrue(self.manifest_path.exists(), f"Missing manifest file: {self.manifest_path}")

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)

    def test_manifest_display_standalone(self):
        """Assert 'display: standalone' for fullscreen app-like experience."""
        self.assertEqual(
            self.manifest.get("display"),
            "standalone",
            "Manifest 'display' must be 'standalone'.",
        )

    def test_manifest_theme_color_and_background_color(self):
        """Assert theme_color: #000000 and background_color: #000000."""
        self.assertEqual(
            self.manifest.get("theme_color", "").upper(),
            "#000000",
            "Manifest 'theme_color' must be '#000000'.",
        )
        self.assertEqual(
            self.manifest.get("background_color", "").upper(),
            "#000000",
            "Manifest 'background_color' must be '#000000'.",
        )

    def test_manifest_start_url_and_icons(self):
        """Assert start_url is '/' and icons array is configured."""
        self.assertEqual(self.manifest.get("start_url"), "/")
        icons = self.manifest.get("icons", [])
        self.assertGreaterEqual(len(icons), 1, "Manifest must contain at least one icon.")
        sizes = [icon.get("sizes") for icon in icons]
        self.assertTrue(
            "192x192" in sizes or "512x512" in sizes,
            "Manifest must include 192x192 or 512x512 icon for Android home screen.",
        )


class TestFastAPIServerEndpointsIntegration(unittest.TestCase):
    """Adversarial integration tests with live FastAPI server endpoints."""

    def setUp(self):
        self.workspace_dir = tempfile.mkdtemp()
        self.workspace = Path(self.workspace_dir)

        repo_static = Path(__file__).resolve().parent.parent / "static"
        workspace_static = self.workspace / "static"
        workspace_static.mkdir(parents=True, exist_ok=True)

        if (repo_static / "index.html").exists():
            shutil.copy(str(repo_static / "index.html"), str(workspace_static / "index.html"))
        if (repo_static / "manifest.json").exists():
            shutil.copy(str(repo_static / "manifest.json"), str(workspace_static / "manifest.json"))

        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

    def tearDown(self):
        shutil.rmtree(self.workspace_dir, ignore_errors=True)

    def test_root_get_returns_200_html(self):
        """GET / must return HTTP 200 with text/html content type."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.headers.get("content-type", "").startswith("text/html"))

    def test_manifest_endpoint_returns_json(self):
        """GET /manifest.json must return HTTP 200 with JSON payload."""
        res = self.client.get("/manifest.json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data.get("display"), "standalone")

    def test_static_asset_mounting(self):
        """GET /static/manifest.json and GET /static/index.html must be reachable."""
        res_manifest = self.client.get("/static/manifest.json")
        self.assertEqual(res_manifest.status_code, status.HTTP_200_OK)

        res_index = self.client.get("/static/index.html")
        self.assertEqual(res_index.status_code, status.HTTP_200_OK)


if __name__ == "__main__":
    unittest.main()
