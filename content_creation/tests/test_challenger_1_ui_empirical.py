"""
test_challenger_1_ui_empirical.py - Empirical Challenge & Stress Test Suite
Challenger 1: DOM Stress, Safe Zone Geometry, Audio Policy Guardrails & Static Sync
Master Dashboard UI Overhaul (Milestone Challenge)
"""

import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple
import unittest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


class DOMExtractor(HTMLParser):
    """Deterministic, strict HTML parser extracting all tags, IDs, attributes, scripts, styles, SVGs."""

    def __init__(self):
        super().__init__()
        self.all_ids: List[str] = []
        self.elements_by_id: Dict[str, Dict[str, Any]] = {}
        self.elements_by_tag: Dict[str, List[Dict[str, Any]]] = {}
        self.scripts: List[str] = []
        self.styles: List[str] = []
        self.meta_tags: List[Dict[str, str]] = []
        self.link_tags: List[Dict[str, str]] = []
        self.svg_elements: List[Dict[str, Any]] = []
        self.rect_elements: List[Dict[str, Any]] = []
        self._current_tag: Optional[str] = None
        self._tag_stack: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k: (v if v is not None else "") for k, v in attrs}
        self._current_tag = tag
        self._tag_stack.append(tag)

        elem_entry = {"tag": tag, "attrs": attr_dict}

        if "id" in attr_dict:
            elem_id = attr_dict["id"]
            self.all_ids.append(elem_id)
            self.elements_by_id[elem_id] = elem_entry

        if tag not in self.elements_by_tag:
            self.elements_by_tag[tag] = []
        self.elements_by_tag[tag].append(elem_entry)

        if tag == "meta":
            self.meta_tags.append(attr_dict)
        elif tag == "link":
            self.link_tags.append(attr_dict)
        elif tag == "svg":
            self.svg_elements.append(elem_entry)
        elif tag == "rect":
            self.rect_elements.append(elem_entry)

    def handle_endtag(self, tag: str):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        self._current_tag = self._tag_stack[-1] if self._tag_stack else None

    def handle_data(self, data: str):
        if not data.strip():
            return
        if self._current_tag == "script":
            self.scripts.append(data)
        elif self._current_tag == "style":
            self.styles.append(data)

    def get_combined_script(self) -> str:
        return "\n".join(self.scripts)

    def get_combined_style(self) -> str:
        return "\n".join(self.styles)


class TestChallenger1DOMAndParityEmpirical(unittest.TestCase):
    """Empirical adversarial verification of DOM IDs, HUD safe zones, guardrails, and file sync."""

    def setUp(self):
        self.root_index = WORKSPACE_ROOT / "index.html"
        self.static_index = WORKSPACE_ROOT / "static" / "index.html"
        self.sw_js = WORKSPACE_ROOT / "static" / "sw.js"
        self.manifest_json = WORKSPACE_ROOT / "static" / "manifest.json"

        self.assertTrue(self.root_index.exists(), f"Missing {self.root_index}")
        self.assertTrue(self.static_index.exists(), f"Missing {self.static_index}")

        self.root_bytes = self.root_index.read_bytes()
        self.static_bytes = self.static_index.read_bytes()

        self.root_text = self.root_index.read_text(encoding="utf-8")
        self.static_text = self.static_index.read_text(encoding="utf-8")

        self.dom = DOMExtractor()
        self.dom.feed(self.root_text)

        self.static_dom = DOMExtractor()
        self.static_dom.feed(self.static_text)

    # ------------------------------------------------------------------------
    # CHALLENGE TASK 1: DOM ELEMENT ID AUDIT (40+ IDS)
    # ------------------------------------------------------------------------
    def test_challenge_task_1_legacy_and_new_dom_ids_inventory(self):
        """Empirically audit presence and tag correctness of all 40+ legacy and modern DOM IDs."""
        mandatory_dom_id_spec = {
            # Video Player & Transport Controls
            "proxy-video": "video",
            "video-time-display": ["span", "div", "p"],
            "video-resolution-badge": ["span", "div", "p"],
            "buffering-status": ["span", "div", "p"],
            "play-pause-btn": "button",
            "step-back-btn": "button",
            "step-fwd-btn": "button",
            "jump-drop-btn": "button",
            "clip-selector": ["select", "div"],
            # Timeline & Scrubber Multi-Track Elements
            "timeline-section": ["div", "section"],
            "timeline-ruler": ["div", "section"],
            "timeline-scrubber": ["div", "section"],
            "start-trim-handle": ["div", "span"],
            "end-trim-handle": ["div", "span"],
            "drop-highlight-region": ["div", "span"],
            "timeline-playhead": ["div", "span"],
            "start-time-display": ["span", "div", "p"],
            "end-time-display": ["span", "div", "p"],
            "duration-display": ["span", "div", "p"],
            "track-v1": ["div", "section"],
            "v1-clip-name": ["span", "div"],
            "track-a1": ["div", "section"],
            "waveform-canvas": "canvas",
            # Handoff & Triggers
            "approve-render-btn": "button",
            "approve-btn-label": ["span", "div"],
            "trigger-btn": "button",
            "btn-label": ["span", "div"],
            "btn-spinner": ["div", "span"],
            # Toast & Feedback Card
            "toast-container": "div",
            "toast-card": "div",
            "toast-title": ["div", "span", "h1", "h2", "h3", "h4", "p"],
            "toast-message": ["div", "span", "p"],
            "toast-icon": ["div", "span", "i", "svg"],
            "toast-close": ["button", "div", "span"],
            # Backward Compatibility Aliases
            "status-toast": ["div", "section"],
            "status-display": ["div", "span", "p"],
            # Telemetry & Badges
            "health-badges": "div",
            "badge-adb": ["div", "span"],
            "badge-ffmpeg": ["div", "span"],
            "badge-server": ["div", "span"],
            "status-card": "div",
            "daemon-state": ["span", "div", "p"],
            "active-job-id": ["strong", "span", "div", "p"],
            "elapsed-time": ["strong", "span", "div", "p"],
            "last-job-summary": ["strong", "div", "span", "p"],
            "cancel-btn": "button",
            "refresh-status-btn": "button",
            # Inspector Metadata Inputs & Controls
            "metadata-section": ["section", "div", "form"],
            "festival-input": "input",
            "artist-input": "input",
            "inspector-track": "input",
            "inspector-bpm": "input",
            "inspector-genre": "select",
            "inspector-brand": "select",
            "inspector-tier": "select",
            "ts-drop-start": "input",
            "ts-drop-end": "input",
            "ts-drop-duration": ["span", "div"],
            # Navigation & View Transitions
            "nav-trigger-tab": ["button", "a", "div"],
            "nav-review-tab": ["button", "a", "div"],
            "view-trigger": ["div", "section", "main"],
            "view-review": ["div", "section", "main"],
            # Left Sidebar Bins & Queue
            "project-selector": "select",
            "refresh-assets-btn": "button",
            "asset-bins-list": "div",
            "queue-count-badge": ["span", "div"],
            "render-queue-list": "div",
            # Omnichannel Safe Zone HUD & Guardrails
            "hud-overlay-container": ["div", "section"],
            "yt-safe-mask": "mask",
            "tiktok-safe-mask": "mask",
            "hud-guide-youtube": "g",
            "hud-guide-tiktok": "g",
            "content-id-guardrail-banner": ["div", "section", "aside"],
            "guardrail-duration-val": ["span", "div", "b", "strong"],
            "clamp-59s-btn": "button",
            "ghost-link-badge": ["div", "span", "badge"],
            "ghost-link-toggle": "input",
        }

        self.assertGreaterEqual(len(self.dom.all_ids), 40, f"Expected >= 40 DOM IDs, found {len(self.dom.all_ids)}")
        self.assertEqual(len(self.dom.all_ids), 78, f"Expected exactly 78 DOM IDs, found {len(self.dom.all_ids)}")

        missing_ids = []
        mismatched_tags = []

        for expected_id, expected_tags in mandatory_dom_id_spec.items():
            if expected_id not in self.dom.elements_by_id:
                missing_ids.append(expected_id)
            else:
                actual_tag = self.dom.elements_by_id[expected_id]["tag"]
                if isinstance(expected_tags, list):
                    if actual_tag not in expected_tags:
                        mismatched_tags.append((expected_id, actual_tag, expected_tags))
                else:
                    if actual_tag != expected_tags:
                        mismatched_tags.append((expected_id, actual_tag, expected_tags))

        self.assertEqual(missing_ids, [], f"Missing required DOM element IDs: {missing_ids}")
        self.assertEqual(mismatched_tags, [], f"Mismatched tag types for DOM IDs: {mismatched_tags}")

    def test_dom_id_uniqueness(self):
        """Empirically verify that every element ID in index.html is 100% unique (no duplicates)."""
        seen: Set[str] = set()
        duplicates: List[str] = []
        for eid in self.dom.all_ids:
            if eid in seen:
                duplicates.append(eid)
            seen.add(eid)
        self.assertEqual(duplicates, [], f"Duplicate DOM element IDs found: {duplicates}")

    # ------------------------------------------------------------------------
    # CHALLENGE TASK 2: SVG HUD SAFE ZONE GEOMETRY AUDIT
    # ------------------------------------------------------------------------
    def test_challenge_task_2_safe_zone_geometry_youtube_shorts(self):
        """Empirically verify YouTube Shorts Safe Zone geometry (900x1270 px) in SVG overlay."""
        self.assertIn("hud-guide-youtube", self.dom.elements_by_id)
        self.assertIn("yt-safe-mask", self.dom.elements_by_id)

        yt_rects = [
            r for r in self.dom.rect_elements
            if ("yt-rect" in r["attrs"].get("class", "")) or (r["attrs"].get("width") == "900" and r["attrs"].get("height") == "1270")
        ]
        self.assertGreaterEqual(len(yt_rects), 1, "Must contain YouTube Shorts safe area rect (900x1270)")

        for r in yt_rects:
            width = float(r["attrs"].get("width", 0))
            height = float(r["attrs"].get("height", 0))
            x = float(r["attrs"].get("x", 0))
            y = float(r["attrs"].get("y", 0))

            self.assertEqual(width, 900.0, f"YouTube Shorts safe zone width must be 900, got {width}")
            self.assertEqual(height, 1270.0, f"YouTube Shorts safe zone height must be 1270, got {height}")
            self.assertEqual(x, 50.0, f"YouTube Shorts safe zone x coordinate must be 50, got {x}")
            self.assertEqual(y, 180.0, f"YouTube Shorts safe zone y coordinate must be 180, got {y}")

    def test_challenge_task_2_safe_zone_geometry_tiktok(self):
        """Empirically verify TikTok Safe Zone geometry (920x1310 px) in SVG overlay."""
        self.assertIn("hud-guide-tiktok", self.dom.elements_by_id)
        self.assertIn("tiktok-safe-mask", self.dom.elements_by_id)

        tt_rects = [
            r for r in self.dom.rect_elements
            if ("tiktok-rect" in r["attrs"].get("class", "")) or (r["attrs"].get("width") == "920" and r["attrs"].get("height") == "1310")
        ]
        self.assertGreaterEqual(len(tt_rects), 1, "Must contain TikTok safe area rect (920x1310)")

        for r in tt_rects:
            width = float(r["attrs"].get("width", 0))
            height = float(r["attrs"].get("height", 0))
            x = float(r["attrs"].get("x", 0))
            y = float(r["attrs"].get("y", 0))

            self.assertEqual(width, 920.0, f"TikTok safe zone width must be 920, got {width}")
            self.assertEqual(height, 1310.0, f"TikTok safe zone height must be 1310, got {height}")
            self.assertEqual(x, 50.0, f"TikTok safe zone x coordinate must be 50, got {x}")
            self.assertEqual(y, 140.0, f"TikTok safe zone y coordinate must be 140, got {y}")

    def test_challenge_task_2_svg_canvas_viewbox_and_aspect_ratio(self):
        """Verify SVG viewBox is 1080x1920 (9:16 vertical canvas) with HUD elements."""
        svg_elements = self.dom.elements_by_tag.get("svg", [])
        self.assertGreaterEqual(len(svg_elements), 1, "Must contain HUD SVG overlay element")
        hud_svg = svg_elements[0]
        viewbox = hud_svg["attrs"].get("viewbox", "") or hud_svg["attrs"].get("viewBox", "")
        self.assertIn("0 0 1080 1920", viewbox, f"SVG viewBox must be '0 0 1080 1920', got {viewbox}")
        self.assertEqual(hud_svg["attrs"].get("preserveaspectratio", "") or hud_svg["attrs"].get("preserveAspectRatio", ""), "none")

    # ------------------------------------------------------------------------
    # CHALLENGE TASK 3: AUDIO POLICY GUARDRAILS (59.00s WARNING & GHOST-LINK)
    # ------------------------------------------------------------------------
    def test_challenge_task_3_content_id_warning_banner_and_clamp_btn(self):
        """Empirically verify 59.00s YouTube Content ID warning toast / amber banner & clamp button."""
        self.assertIn("content-id-guardrail-banner", self.dom.elements_by_id)
        self.assertIn("guardrail-duration-val", self.dom.elements_by_id)
        self.assertIn("clamp-59s-btn", self.dom.elements_by_id)

        clamp_btn = self.dom.elements_by_id["clamp-59s-btn"]
        self.assertEqual(clamp_btn["tag"], "button")

        script = self.dom.get_combined_script()
        self.assertIn("59.00", script)
        self.assertRegex(script, r"(>|>=)\s*59(\.0+)?")
        self.assertIn("content-id-guardrail-banner", script)
        self.assertIn("clamp-59s-btn", script)

        styles = self.dom.get_combined_style()
        self.assertIn("pulse-amber-glow", styles)
        self.assertIn(".guardrail-warning", styles)

    def test_challenge_task_3_tiktok_ghost_linking_badge(self):
        """Empirically verify TikTok Ghost-Linking Audio badge #ghost-link-badge presence and styling."""
        self.assertIn("ghost-link-badge", self.dom.elements_by_id)
        self.assertIn("ghost-link-toggle", self.dom.elements_by_id)

        styles = self.dom.get_combined_style()
        self.assertIn(".ghost-link-badge", styles)
        self.assertIn(".ghost-status-pill", styles)

        script = self.dom.get_combined_script()
        self.assertIn("ghost-link-badge", script)

    # ------------------------------------------------------------------------
    # CHALLENGE TASK 4: STATIC FILE SYNCHRONIZATION
    # ------------------------------------------------------------------------
    def test_challenge_task_4_root_and_static_html_exact_byte_sync(self):
        """Empirically verify exact byte-for-byte synchronization between root index.html and static/index.html."""
        root_sha256 = hashlib.sha256(self.root_bytes).hexdigest()
        static_sha256 = hashlib.sha256(self.static_bytes).hexdigest()

        self.assertEqual(
            root_sha256,
            static_sha256,
            f"SHA256 mismatch between index.html ({root_sha256}) and static/index.html ({static_sha256})",
        )
        self.assertEqual(
            self.root_bytes,
            self.static_bytes,
            "root index.html and static/index.html must be byte-for-byte identical.",
        )

    # ------------------------------------------------------------------------
    # CHALLENGE TASK 5: PWA STANDARDS, MANIFEST, AND JAVASCRIPT AST
    # ------------------------------------------------------------------------
    def test_pwa_manifest_and_meta_tags(self):
        """Verify PWA manifest link, theme color, and viewport settings."""
        viewport_metas = [m for m in self.dom.meta_tags if m.get("name") == "viewport"]
        self.assertEqual(len(viewport_metas), 1)
        vp_content = viewport_metas[0].get("content", "")
        self.assertIn("width=device-width", vp_content)
        self.assertIn("viewport-fit=cover", vp_content)

        theme_metas = [m for m in self.dom.meta_tags if m.get("name") == "theme-color"]
        self.assertEqual(len(theme_metas), 1)
        self.assertEqual(theme_metas[0].get("content", "").upper(), "#000000")

        manifest_links = [l for l in self.dom.link_tags if l.get("rel") == "manifest"]
        self.assertEqual(len(manifest_links), 1)
        self.assertEqual(manifest_links[0].get("href"), "/manifest.json")

    def test_javascript_ast_syntax_via_node_if_available(self):
        """Verify client JavaScript syntax via Node.js vm.Script."""
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js not installed on system.")

        node_script = """
const vm = require('vm');
const fs = require('fs');
const code = fs.readFileSync(process.argv[2], 'utf8');
const scriptMatch = code.match(/<script>([\\s\\S]*?)<\\/script>/);
if (!scriptMatch) {
    console.error('No script tag found');
    process.exit(1);
}
try {
    new vm.Script(scriptMatch[1], { filename: 'dashboard.js' });
    console.log('JS_PARSED_CLEANLY');
    process.exit(0);
} catch (err) {
    console.error('JS_SYNTAX_ERROR:', err.message);
    process.exit(2);
}
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tf:
            tf.write(node_script)
            runner = tf.name

        try:
            res = subprocess.run([node_bin, runner, str(self.root_index)], capture_output=True, text=True, timeout=10)
            self.assertEqual(res.returncode, 0, f"JavaScript parsing error:\n{res.stderr}")
        finally:
            if os.path.exists(runner):
                os.remove(runner)

    def test_css_grid_layout_structure(self):
        """Verify CSS Grid layout areas, columns, and Slate Dark tokens."""
        styles = self.dom.get_combined_style()
        self.assertIn("grid-template-areas", styles)
        self.assertRegex(styles, r'["\']topbar\s+topbar\s+topbar["\']')
        self.assertRegex(styles, r'["\']sidebar\s+workspace\s+inspector["\']')
        self.assertRegex(styles, r'["\']footer\s+footer\s+footer["\']')

        self.assertIn("--color-bg-base: #0B0F19", styles)
        self.assertIn("--color-bg-elevated: #1A2234", styles)
        self.assertIn("--color-border-subtle: #2D3748", styles)
        self.assertIn("--color-text-primary: #E2E8F0", styles)
        self.assertIn("--color-accent-blue: #3B82F6", styles)

    def test_fastapi_endpoints_wiring_in_javascript(self):
        """Verify all 6 required FastAPI endpoints are referenced in client JavaScript."""
        script = self.dom.get_combined_script()
        required_endpoints = [
            "/trigger-pipeline",
            "/approve-render",
            "/proxies",
            "/status",
            "/cancel",
            "/health",
        ]
        for ep in required_endpoints:
            self.assertIn(ep, script, f"Missing endpoint reference '{ep}' in JavaScript")


if __name__ == "__main__":
    unittest.main(verbosity=2)
