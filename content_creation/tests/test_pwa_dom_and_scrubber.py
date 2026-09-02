"""
tests/test_pwa_dom_and_scrubber.py - Comprehensive Adversarial Test Suite
for Milestone M2: Modern PWA Web UI, 720p Proxy Video Player, Timeline Scrubber,
View Transitions API, and Service Worker.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple
import unittest
from html.parser import HTMLParser

from fastapi import status
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from remote_trigger import create_app


class FullDOMParser(HTMLParser):
    """Deep DOM structure parser extracting elements, attributes, text, styles, links, and scripts."""

    def __init__(self):
        super().__init__()
        self.elements_by_id: Dict[str, Dict[str, str]] = {}
        self.all_ids: List[str] = []
        self.meta_tags: List[Dict[str, str]] = []
        self.link_tags: List[Dict[str, str]] = []
        self.button_tags: List[Dict[str, str]] = []
        self.video_tags: List[Dict[str, str]] = []
        self.input_tags: List[Dict[str, str]] = []
        self.scripts: List[str] = []
        self.styles: List[str] = []
        self._current_tag: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k: (v if v is not None else "") for k, v in attrs}
        self._current_tag = tag

        if "id" in attr_dict:
            elem_id = attr_dict["id"]
            self.all_ids.append(elem_id)
            self.elements_by_id[elem_id] = {"tag": tag, **attr_dict}

        if tag == "meta":
            self.meta_tags.append(attr_dict)
        elif tag == "link":
            self.link_tags.append(attr_dict)
        elif tag == "button":
            self.button_tags.append(attr_dict)
        elif tag == "video":
            self.video_tags.append(attr_dict)
        elif tag == "input":
            self.input_tags.append(attr_dict)

    def handle_endtag(self, tag: str):
        self._current_tag = None

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


class TestPWADOMAndScrubberStructure(unittest.TestCase):
    """Validates DOM structure and elements in static/index.html and root index.html."""

    def setUp(self):
        self.static_dir = Path(__file__).resolve().parent.parent / "static"
        self.index_path = self.static_dir / "index.html"
        self.root_index_path = Path(__file__).resolve().parent.parent / "index.html"
        self.sw_path = self.static_dir / "sw.js"
        self.manifest_path = self.static_dir / "manifest.json"

        self.assertTrue(self.index_path.exists(), f"Missing {self.index_path}")
        self.assertTrue(self.root_index_path.exists(), f"Missing {self.root_index_path}")
        self.assertTrue(self.sw_path.exists(), f"Missing {self.sw_path}")
        self.assertTrue(self.manifest_path.exists(), f"Missing {self.manifest_path}")

        with open(self.index_path, "r", encoding="utf-8") as f:
            self.html_content = f.read()

        self.dom = FullDOMParser()
        self.dom.feed(self.html_content)
        self.script_code = self.dom.get_combined_script()
        self.style_code = self.dom.get_combined_style()

    def test_pwa_head_links_and_meta_tags(self):
        """Assert all required PWA manifest, icon, apple-touch-icon, and theme-color tags."""
        # 1. Manifest link
        manifest_links = [l for l in self.dom.link_tags if l.get("rel") == "manifest"]
        self.assertGreaterEqual(len(manifest_links), 1, "Must have <link rel='manifest'>")
        self.assertIn("/manifest.json", manifest_links[0].get("href", ""))

        # 2. Favicon / App icons
        icon_links = [l for l in self.dom.link_tags if "icon" in l.get("rel", "")]
        self.assertGreaterEqual(len(icon_links), 2, "Must declare icon and apple-touch-icon links")
        icon_hrefs = [l.get("href", "") for l in icon_links]
        self.assertTrue(any("icon-192.png" in h for h in icon_hrefs), "Must reference 192px icon")

        # 3. Theme color #000000
        theme_metas = [m for m in self.dom.meta_tags if m.get("name") == "theme-color"]
        self.assertEqual(len(theme_metas), 1)
        self.assertEqual(theme_metas[0].get("content", "").upper(), "#000000")

    def test_720p_proxy_video_player_elements(self):
        """Assert existence and attributes of the 720p proxy video player."""
        self.assertIn("proxy-video", self.dom.all_ids, "Element <video id='proxy-video'> must exist")
        video_info = self.dom.elements_by_id["proxy-video"]
        self.assertEqual(video_info["tag"], "video")

        # Check HUD and control elements
        required_player_ids = [
            "video-time-display",
            "buffering-status",
            "play-pause-btn",
            "step-back-btn",
            "step-fwd-btn",
            "jump-drop-btn",
            "clip-selector",
        ]
        for elem_id in required_player_ids:
            self.assertIn(elem_id, self.dom.all_ids, f"Required video player element id='{elem_id}' missing")

    def test_interactive_timeline_scrubber_elements(self):
        """Assert existence of timeline scrubber, trim handles, drop highlight, and timecodes."""
        required_scrubber_ids = [
            "timeline-scrubber",
            "start-trim-handle",
            "end-trim-handle",
            "drop-highlight-region",
            "timeline-playhead",
            "start-time-display",
            "end-time-display",
            "duration-display",
            "approve-render-btn",
        ]
        for elem_id in required_scrubber_ids:
            self.assertIn(elem_id, self.dom.all_ids, f"Required scrubber element id='{elem_id}' missing")

        # Verify timeline scrubber has slider ARIA role
        scrubber_info = self.dom.elements_by_id["timeline-scrubber"]
        self.assertEqual(scrubber_info.get("role"), "slider")

    def test_view_transition_navigation_panels(self):
        """Assert existence of tab buttons and panel views for progressive view transitions."""
        required_nav_ids = [
            "nav-trigger-tab",
            "nav-review-tab",
            "view-trigger",
            "view-review",
        ]
        for elem_id in required_nav_ids:
            self.assertIn(elem_id, self.dom.all_ids, f"Required navigation element id='{elem_id}' missing")

    def test_view_transitions_css_and_reduced_motion(self):
        """Assert CSS view transition animations and prefers-reduced-motion media query."""
        self.assertIn("::view-transition-old", self.style_code)
        self.assertIn("::view-transition-new", self.style_code)
        self.assertIn("prefers-reduced-motion: reduce", self.style_code)
        self.assertIn("backdrop-filter: blur(12px)", self.style_code)

    def test_javascript_view_transitions_implementation(self):
        """Assert View Transitions API check and progressive fallback in client script."""
        self.assertIn("document.startViewTransition", self.script_code)
        self.assertIn("!document.startViewTransition", self.script_code)

    def test_javascript_service_worker_registration(self):
        """Assert service worker registration with navigator.serviceWorker guard."""
        self.assertIn("'serviceWorker' in navigator", self.script_code)
        self.assertIn("navigator.serviceWorker.register", self.script_code)
        self.assertIn("/static/sw.js", self.script_code)

    def test_approve_render_fetch_dispatch_contract(self):
        """Assert /approve-render endpoint dispatch with full metadata payload."""
        self.assertIn("/approve-render", self.script_code)
        self.assertIn("clip_id", self.script_code)
        self.assertIn("start_time", self.script_code)
        self.assertIn("duration", self.script_code)
        self.assertIn("end_time", self.script_code)
        self.assertIn("raw_file_path", self.script_code)

    def test_root_and_static_html_exact_sync(self):
        """Assert content_creation/index.html is synchronized with static/index.html."""
        with open(self.root_index_path, "r", encoding="utf-8") as f:
            root_content = f.read()
        self.assertEqual(
            self.html_content.strip(),
            root_content.strip(),
            "static/index.html and root index.html must be identical in content.",
        )


class TestServiceWorkerImplementation(unittest.TestCase):
    """Validates service worker syntax, event listeners, and caching strategies in static/sw.js."""

    def setUp(self):
        self.sw_path = Path(__file__).resolve().parent.parent / "static" / "sw.js"
        self.assertTrue(self.sw_path.exists(), f"Missing {self.sw_path}")
        with open(self.sw_path, "r", encoding="utf-8") as f:
            self.sw_code = f.read()

    def test_service_worker_js_ast_validity(self):
        """Validates that sw.js is syntactically valid JavaScript via Node.js vm.Script."""
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js not found on PATH.")

        node_script = """
const vm = require('vm');
const fs = require('fs');
const targetFile = process.argv[2];
const code = fs.readFileSync(targetFile, 'utf8');
try {
    new vm.Script(code, { filename: 'sw.js' });
    console.log('SW_JS_VALID');
    process.exit(0);
} catch (err) {
    console.error('SW_SYNTAX_ERROR:', err.message);
    process.exit(1);
}
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tf:
            tf.write(node_script)
            runner = tf.name

        try:
            res = subprocess.run([node_bin, runner, str(self.sw_path)], capture_output=True, text=True, timeout=10)
            self.assertEqual(res.returncode, 0, f"sw.js syntax error:\n{res.stderr}")
        finally:
            if os.path.exists(runner):
                os.remove(runner)

    def test_service_worker_event_handlers_and_strategies(self):
        """Assert install, activate, and fetch event handlers and caching strategy separation."""
        self.assertIn("addEventListener('install'", self.sw_code)
        self.assertIn("addEventListener('activate'", self.sw_code)
        self.assertIn("addEventListener('fetch'", self.sw_code)

        # Cache-first for static assets
        self.assertIn("caches.match", self.sw_code)
        self.assertIn("caches.open", self.sw_code)

        # Network-first for dynamic API routes
        self.assertIn("/api/", self.sw_code)
        self.assertIn("/proxies/", self.sw_code)
        self.assertIn("/trigger-pipeline", self.sw_code)
        self.assertIn("/approve-render", self.sw_code)


class TestPWARestEndpointsIntegration(unittest.TestCase):
    """Validates FastAPI server responses for PWA HTML, SW, Proxies, and DaVinci Handoff."""

    def setUp(self):
        self.workspace_dir = tempfile.mkdtemp()
        self.workspace = Path(self.workspace_dir)

        repo_static = Path(__file__).resolve().parent.parent / "static"
        workspace_static = self.workspace / "static"
        workspace_static.mkdir(parents=True, exist_ok=True)

        for filename in ["index.html", "manifest.json", "sw.js"]:
            if (repo_static / filename).exists():
                shutil.copy(str(repo_static / filename), str(workspace_static / filename))

        # Create simulated raw and proxy folders
        raw_dir = self.workspace / "01_RAW" / "EDCLV" / "SubFocus"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / "20260822_EDCLV_SubFocus_V1_4k.mp4"
        raw_file.write_bytes(b"\x00" * 4096)

        proxy_dir = self.workspace / "02_AWAITING_REVIEW" / "EDCLV" / "SubFocus"
        proxy_dir.mkdir(parents=True, exist_ok=True)
        proxy_file = proxy_dir / "20260822_EDCLV_SubFocus_V1_proxy.mp4"
        proxy_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2048)

        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

    def tearDown(self):
        shutil.rmtree(self.workspace_dir, ignore_errors=True)

    def test_service_worker_served_via_static(self):
        """GET /static/sw.js must return HTTP 200 with javascript media type."""
        res = self.client.get("/static/sw.js")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("javascript", res.headers.get("content-type", ""))

    def test_proxies_catalog_endpoint(self):
        """GET /proxies must return list of discovered takes with proxy URLs."""
        res = self.client.get("/proxies")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("clips", data)
        self.assertGreaterEqual(data["total"], 1)
        first_clip = data["clips"][0]
        self.assertIn("clip_id", first_clip)
        self.assertIn("/proxies/", first_clip["proxy_url"])

    def test_proxy_video_streaming_endpoint(self):
        """GET /proxies/{clip_id}/video must support HTTP 200 and HTTP 206 Partial Content."""
        catalog_res = self.client.get("/proxies")
        clip_id = catalog_res.json()["clips"][0]["clip_id"]

        # Full file request
        res = self.client.get(f"/proxies/{clip_id}/video")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.headers.get("accept-ranges"), "bytes")

        # Range request (HTTP 206)
        range_res = self.client.get(f"/proxies/{clip_id}/video", headers={"Range": "bytes=0-100"})
        self.assertEqual(range_res.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertIn("bytes 0-100/", range_res.headers.get("content-range", ""))

    def test_approve_render_endpoint(self):
        """POST /approve-render must accept user trim coordinates and trigger handoff."""
        catalog_res = self.client.get("/proxies")
        first_clip = catalog_res.json()["clips"][0]

        payload = {
            "clip_id": first_clip["clip_id"],
            "project_name": "EDCLV_SubFocus_Drop",
            "festival": "EDCLV",
            "artist": "SubFocus",
            "raw_file_path": first_clip["raw_path"],
            "start_time": 45.0,
            "end_time": 75.0,
            "duration": 30.0,
            "dry_run": True,
        }
        res = self.client.post("/approve-render", json=payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn(data["status"], ("success", "dry_run_simulated"))
        self.assertEqual(data["start_time"], 45.0)
        self.assertEqual(data["duration"], 30.0)


if __name__ == "__main__":
    unittest.main()
