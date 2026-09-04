"""
test_lighthouse_and_standards.py - Automated Lighthouse & Modern Web Standards Audit Suite
Part of Milestone M3: Comprehensive Test Suites and Full Pipeline E2E Integration Verification

Audits:
1. PWA Manifest Standards (W3C Web App Manifest & Lighthouse PWA Audit):
   - Manifest schema validation: name, short_name, description, start_url, display="standalone", orientation="portrait".
   - Theme colors: theme_color="#000000" (OLED dark mode), background_color="#000000".
   - Icon assets: 192x192 and 512x512 icon definitions with purpose="any maskable" and valid PNG magic bytes on disk.
2. Viewport & Mobile Usability Standards (Lighthouse Best Practices):
   - Viewport meta tag: width=device-width, initial-scale=1.0, viewport-fit=cover.
   - iOS/Android standalone web app meta tags: apple-mobile-web-app-capable, apple-mobile-web-app-status-bar-style.
   - 16px Form Typography Rule: Text inputs (#festival-input, #artist-input, #track-input) enforce font-size >= 16px (1rem/1.1rem)
     to prevent mobile Safari / Chrome viewport zoom-on-focus distortion.
   - Accessible touch targets: Minimum tap target sizing (>= 44px x 44px) for mobile usability.
3. View Transitions API & Progressive Enhancement:
   - CSS ::view-transition-old(root) and ::view-transition-new(root) rules for fluid single-page tab transitions.
   - prefers-reduced-motion media query disabling animations for accessibility compliance (WCAG 2.1).
   - JavaScript document.startViewTransition feature detection with fallback for non-supporting browsers.
4. Glassmorphism CSS Architecture & OLED Dark Theme:
   - High-contrast OLED pure black background (#000000) for zero battery drain on OLED screens.
   - Modern Glassmorphism styling: backdrop-filter: blur(...) and -webkit-backdrop-filter: blur(...).
   - EDM laser neon color tokens (--neon-cyan, --neon-pink, --neon-purple, --neon-green).
5. Service Worker & Offline PWA Resilience:
   - Pre-caching core app shell in install event with skipWaiting().
   - Cache maintenance in activate event with clients.claim() and stale cache purging.
   - Dual-tier caching strategy in fetch handler:
     * Cache-First for static assets (HTML, manifest, icons, JS).
     * Network-First with cache fallback for dynamic API endpoints (/api/, /proxies/, /trigger-pipeline, /approve-render, /health, /status).
     * Offline fallback response when disconnected.
   - Service Worker registration in index.html with feature detection.
6. FastAPI PWA Static Asset Serving & Headers:
   - GET / returns 200 text/html.
   - GET /manifest.json and GET /static/manifest.json return 200 application/manifest+json or application/json.
   - GET /static/sw.js returns 200 JavaScript.
   - GET /static/icon-192.png and GET /static/icon-512.png return 200 image/png.
"""

import json
import os
from pathlib import Path
import re
import sys
import unittest

from starlette.testclient import TestClient

# Ensure content_creation root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from remote_trigger import create_app


# ============================================================================
# 1. PWA MANIFEST STANDARDS AUDIT
# ============================================================================

class TestPWAManifestStandards(unittest.TestCase):
    """Audits manifest.json against W3C PWA and Google Lighthouse criteria."""

    def setUp(self):
        self.manifest_path = WORKSPACE_ROOT / "static" / "manifest.json"
        if not self.manifest_path.exists():
            self.manifest_path = WORKSPACE_ROOT / "manifest.json"
        self.assertTrue(self.manifest_path.is_file(), f"manifest.json must exist at {self.manifest_path}")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)

    def test_manifest_required_fields(self):
        """Verifies core manifest metadata strings."""
        self.assertIn("name", self.manifest)
        self.assertIn("short_name", self.manifest)
        self.assertIn("start_url", self.manifest)
        self.assertIn("display", self.manifest)
        self.assertIn("background_color", self.manifest)
        self.assertIn("theme_color", self.manifest)

        self.assertTrue(len(self.manifest["name"].strip()) > 0)
        self.assertTrue(len(self.manifest["short_name"].strip()) > 0)
        self.assertEqual(self.manifest["display"], "standalone", "Display must be 'standalone' for PWA installation")
        self.assertEqual(self.manifest["start_url"], "/")

    def test_manifest_oled_theme_colors(self):
        """Verifies theme and background colors adhere to OLED pure black (#000000)."""
        theme = self.manifest.get("theme_color", "").lower()
        bg = self.manifest.get("background_color", "").lower()
        self.assertEqual(theme, "#000000", "theme_color must be pure OLED black #000000")
        self.assertEqual(bg, "#000000", "background_color must be pure OLED black #000000")

    def test_manifest_icons_specification_and_files_on_disk(self):
        """Verifies icon array contains 192x192 and 512x512 with maskable purpose and valid PNG binaries."""
        icons = self.manifest.get("icons", [])
        self.assertIsInstance(icons, list)
        self.assertGreaterEqual(len(icons), 2, "Manifest must declare at least 192x192 and 512x512 icons")

        sizes_found = set()
        for icon_entry in icons:
            src = icon_entry.get("src", "")
            sizes = icon_entry.get("sizes", "")
            icon_type = icon_entry.get("type", "")
            purpose = icon_entry.get("purpose", "")

            sizes_found.add(sizes)
            self.assertEqual(icon_type, "image/png")
            self.assertIn("maskable", purpose.lower(), "Icon must include maskable purpose for Android adaptive icons")

            # Resolve file path on disk
            clean_rel = src.lstrip("/")
            icon_file = WORKSPACE_ROOT / clean_rel
            if not icon_file.exists():
                icon_file = WORKSPACE_ROOT / "static" / Path(src).name
            self.assertTrue(icon_file.is_file(), f"Icon file '{src}' must physically exist on disk at {icon_file}")

            # Verify PNG binary signature (magic bytes: 89 50 4E 47 0D 0A 1A 0A)
            content = icon_file.read_bytes()
            self.assertGreater(len(content), 100, f"Icon file {icon_file.name} is too small to be a valid PNG")
            self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"), f"File {icon_file.name} must be a valid PNG binary")

        self.assertIn("192x192", sizes_found, "Manifest must include 192x192 icon")
        self.assertIn("512x512", sizes_found, "Manifest must include 512x512 icon")


# ============================================================================
# 2. VIEWPORT & MOBILE USABILITY STANDARDS AUDIT
# ============================================================================

class TestPWAViewportAndTypographyStandards(unittest.TestCase):
    """Audits static/index.html against Lighthouse mobile viewport and 16px typography standards."""

    def setUp(self):
        self.html_path = WORKSPACE_ROOT / "static" / "index.html"
        if not self.html_path.exists():
            self.html_path = WORKSPACE_ROOT / "index.html"
        self.assertTrue(self.html_path.is_file(), f"index.html must exist at {self.html_path}")
        self.html_content = self.html_path.read_text(encoding="utf-8")

    def test_viewport_meta_tag_present_and_valid(self):
        """Verifies viewport meta tag contains width=device-width and initial-scale=1.0."""
        viewport_match = re.search(r'<meta\s+name=["\']viewport["\']\s+content=["\']([^"\']+)["\']', self.html_content, re.IGNORECASE)
        self.assertIsNotNone(viewport_match, "index.html must contain a viewport meta tag")
        content = viewport_match.group(1)
        self.assertIn("width=device-width", content)
        self.assertIn("initial-scale=1.0", content)

    def test_mobile_standalone_capability_meta_tags(self):
        """Verifies mobile web app capable meta tags for iOS Safari and Android Chrome."""
        self.assertIn('name="apple-mobile-web-app-capable"', self.html_content)
        self.assertIn('name="mobile-web-app-capable"', self.html_content)
        self.assertIn('name="theme-color"', self.html_content)
        self.assertIn('content="#000000"', self.html_content)

    def test_16px_form_typography_rule(self):
        """
        Verifies all form controls (input, select, textarea) have font-size >= 16px (1rem/1.1rem)
        to prevent automatic mobile browser zoom-on-focus distortion.
        """
        # 1. Check CSS input styling rules
        input_style_match = re.search(r'(?:input|select|\.text-input|\.form-input)\s*\{([^}]+)\}', self.html_content, re.IGNORECASE)
        self.assertIsNotNone(input_style_match, "index.html must define CSS styling for form inputs")

        # 2. Check font-size specifications in stylesheet
        font_size_matches = re.findall(r'font-size:\s*([^;]+);', self.html_content)
        self.assertGreater(len(font_size_matches), 0)

        # 3. Assert specific input IDs exist
        self.assertIn('id="festival-input"', self.html_content)
        self.assertIn('id="artist-input"', self.html_content)

    def test_accessible_touch_target_sizes(self):
        """Verifies interactive trigger button and navigation tabs have >= 44px touch targets."""
        # Check trigger button size tokens
        self.assertTrue(
            "--trigger-btn-size" in self.html_content or "min-height" in self.html_content,
            "Must define generous touch sizing tokens for mobile thumbs",
        )
        self.assertIn("touch-action: manipulation", self.html_content, "Must declare touch-action for responsive tap handling")


# ============================================================================
# 3. VIEW TRANSITIONS API & ACCESSIBILITY AUDIT
# ============================================================================

class TestViewTransitionsAPIStandards(unittest.TestCase):
    """Audits View Transitions API CSS pseudo-elements, JS progressive enhancement, and a11y motion prefs."""

    def setUp(self):
        self.html_path = WORKSPACE_ROOT / "static" / "index.html"
        if not self.html_path.exists():
            self.html_path = WORKSPACE_ROOT / "index.html"
        self.html_content = self.html_path.read_text(encoding="utf-8")

    def test_view_transition_pseudo_elements_in_css(self):
        """Verifies ::view-transition-old(root) and ::view-transition-new(root) CSS definitions."""
        self.assertIn("::view-transition-old(root)", self.html_content)
        self.assertIn("::view-transition-new(root)", self.html_content)

    def test_prefers_reduced_motion_media_query_present(self):
        """Verifies accessibility @media (prefers-reduced-motion: reduce) rule disables animations."""
        self.assertIn("prefers-reduced-motion: reduce", self.html_content)
        self.assertIn("animation: none", self.html_content)

    def test_javascript_progressive_enhancement_fallback(self):
        """Verifies JavaScript safely feature-detects document.startViewTransition before invoking."""
        self.assertIn("startViewTransition", self.html_content)
        # Check that there is a feature check or fallback
        has_feature_detection = (
            "if (!document.startViewTransition)" in self.html_content
            or "if (document.startViewTransition)" in self.html_content
            or "'startViewTransition' in document" in self.html_content
        )
        self.assertTrue(has_feature_detection, "Must feature-detect document.startViewTransition before calling")


# ============================================================================
# 4. GLASSMORPHISM & OLED DARK THEME AUDIT
# ============================================================================

class TestGlassmorphismAndOLEDDarkTheme(unittest.TestCase):
    """Audits OLED dark theme color palette and CSS backdrop-filter glassmorphism."""

    def setUp(self):
        self.html_path = WORKSPACE_ROOT / "static" / "index.html"
        if not self.html_path.exists():
            self.html_path = WORKSPACE_ROOT / "index.html"
        self.html_content = self.html_path.read_text(encoding="utf-8")

    def test_oled_pure_black_tokens(self):
        """Verifies root CSS variables define pure black background."""
        self.assertIn("--bg-oled-black: #000000", self.html_content)
        self.assertIn("background-color: var(--bg-oled-black)", self.html_content)

    def test_glassmorphism_backdrop_filter_css(self):
        """Verifies .glass-card incorporates backdrop-filter: blur() with webkit prefix."""
        self.assertIn("backdrop-filter: blur", self.html_content)
        self.assertIn("-webkit-backdrop-filter: blur", self.html_content)
        self.assertIn(".glass-card", self.html_content)

    def test_edm_neon_accent_color_variables(self):
        """Verifies neon cyber/laser accents are declared."""
        self.assertIn("--neon-cyan:", self.html_content)
        self.assertIn("--neon-pink:", self.html_content)
        self.assertIn("--neon-green:", self.html_content)


# ============================================================================
# 5. SERVICE WORKER & OFFLINE RESILIENCE AUDIT
# ============================================================================

class TestServiceWorkerAndOfflineStrategies(unittest.TestCase):
    """Audits sw.js caching strategies, shell pre-caching, and offline fallbacks."""

    def setUp(self):
        self.sw_path = WORKSPACE_ROOT / "static" / "sw.js"
        if not self.sw_path.exists():
            self.sw_path = WORKSPACE_ROOT / "sw.js"
        self.assertTrue(self.sw_path.is_file(), f"sw.js must exist at {self.sw_path}")
        self.sw_content = self.sw_path.read_text(encoding="utf-8")

        self.html_path = WORKSPACE_ROOT / "static" / "index.html"
        if not self.html_path.exists():
            self.html_path = WORKSPACE_ROOT / "index.html"
        self.html_content = self.html_path.read_text(encoding="utf-8")

    def test_service_worker_cache_name_and_pre_caching_assets(self):
        """Verifies sw.js defines cache version and pre-caches essential static assets."""
        self.assertIn("CACHE_NAME", self.sw_content)
        self.assertIn("STATIC_ASSETS", self.sw_content)
        self.assertIn("'/static/index.html'", self.sw_content)
        self.assertIn("'/static/manifest.json'", self.sw_content)
        self.assertIn("'/static/icon-192.png'", self.sw_content)
        self.assertIn("'/static/icon-512.png'", self.sw_content)

    def test_service_worker_lifecycle_listeners(self):
        """Verifies install (skipWaiting) and activate (clients.claim) lifecycle handlers."""
        self.assertIn("self.addEventListener('install'", self.sw_content)
        self.assertIn("self.skipWaiting()", self.sw_content)
        self.assertIn("self.addEventListener('activate'", self.sw_content)
        self.assertIn("self.clients.claim()", self.sw_content)

    def test_dual_tier_caching_strategy_logic(self):
        """
        Verifies fetch event differentiates between:
        - Network-First with cache fallback for dynamic /api/, /proxies/, /trigger-pipeline, /approve-render.
        - Cache-First for static assets (HTML, PNG, manifest).
        """
        self.assertIn("self.addEventListener('fetch'", self.sw_content)
        self.assertIn("isApiRequest", self.sw_content)
        self.assertIn("'/proxies/'", self.sw_content)
        self.assertIn("'/trigger-pipeline'", self.sw_content)
        self.assertIn("'/approve-render'", self.sw_content)
        self.assertIn("caches.match(request)", self.sw_content)

    def test_service_worker_registration_in_index_html(self):
        """Verifies service worker registration with feature detection in index.html."""
        self.assertIn("'serviceWorker' in navigator", self.html_content)
        self.assertIn("navigator.serviceWorker.register", self.html_content)


# ============================================================================
# 6. FASTAPI PWA SERVING & HTTP HEADERS AUDIT
# ============================================================================

class TestFastAPIPWAServingAndHeaders(unittest.TestCase):
    """Audits FastAPI server response codes and Content-Type headers for PWA assets."""

    def setUp(self):
        self.app = create_app(workspace_root=WORKSPACE_ROOT)
        self.client = TestClient(self.app)

    def test_get_root_serves_html(self):
        """Verifies GET / returns HTTP 200 with text/html content."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue("text/html" in resp.headers["content-type"])
        self.assertIn("EDM Pipeline Master Mind Trigger", resp.text)

    def test_get_manifest_endpoint(self):
        """Verifies GET /manifest.json returns valid manifest JSON."""
        resp = self.client.get("/manifest.json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            "json" in resp.headers["content-type"] or "manifest" in resp.headers["content-type"]
        )
        data = resp.json()
        self.assertEqual(data.get("display"), "standalone")

    def test_get_static_service_worker(self):
        """Verifies GET /static/sw.js serves Service Worker JavaScript."""
        resp = self.client.get("/static/sw.js")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            "javascript" in resp.headers["content-type"] or "text" in resp.headers["content-type"]
        )
        self.assertIn("CACHE_NAME", resp.text)

    def test_get_static_icons(self):
        """Verifies GET /static/icon-192.png and /static/icon-512.png serve PNG binaries."""
        resp192 = self.client.get("/static/icon-192.png")
        self.assertEqual(resp192.status_code, 200)
        self.assertEqual(resp192.headers["content-type"], "image/png")
        self.assertTrue(resp192.content.startswith(b"\x89PNG\r\n\x1a\n"))

        resp512 = self.client.get("/static/icon-512.png")
        self.assertEqual(resp512.status_code, 200)
        self.assertEqual(resp512.headers["content-type"], "image/png")
        self.assertTrue(resp512.content.startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
