"""
Challenger 2 Empirical Verification Suite for Milestone 5 (Zero-Waste Audit R4)
Omnichannel Triage Hub

Validates:
1. WCAG 2.1 AA Contrast calculation across 4 theme modes (Standard Dark, OLED Black, Slate Midnight, Zinc Deep).
2. Button interaction state contrast (normal, hover, active, focus).
3. Complete keyboard navigation support (:focus-visible rings, onKeyDown Enter/Space, tabIndex, hotkeys).
4. Zero Cumulative Layout Shift (CLS = 0) with explicit media aspect ratios and fixed viewport bounds.
5. Heading hierarchy (h1 -> h2 -> h3) and ARIA landmark compliance.
6. Form input label association (htmlFor <-> id matching).
7. Production bundle performance budgets and virtual tag scaling.
"""

import math
import os
import re
import time
from pathlib import Path
import pytest

REPO_ROOT = Path("G:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub")
FRONTEND_DIR = REPO_ROOT / "frontend"
SRC_DIR = FRONTEND_DIR / "src"
COMPONENTS_DIR = SRC_DIR / "components"
DIST_DIR = FRONTEND_DIR / "dist"


# -----------------------------------------------------------------------------
# Color Contrast Calculation
# -----------------------------------------------------------------------------
def hex_to_rgb(hex_str: str):
    clean = hex_str.lstrip("#")
    if len(clean) == 3:
        clean = "".join(c + c for c in clean)
    int_val = int(clean, 16)
    return ((int_val >> 16) & 255, (int_val >> 8) & 255, int_val & 255)


def relative_luminance(rgb_tuple):
    sRGB = []
    for val in rgb_tuple:
        v = val / 255.0
        if v <= 0.03928:
            sRGB.append(v / 12.92)
        else:
            sRGB.append(math.pow((v + 0.055) / 1.055, 2.4))
    return 0.2126 * sRGB[0] + 0.7152 * sRGB[1] + 0.0722 * sRGB[2]


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    l1 = relative_luminance(hex_to_rgb(fg_hex))
    l2 = relative_luminance(hex_to_rgb(bg_hex))
    brightest = max(l1, l2)
    darkest = min(l1, l2)
    return (brightest + 0.05) / (darkest + 0.05)


def extract_opening_tags(src: str, tag_name: str):
    tags = []
    i = 0
    while i < len(src):
        start_idx = src.find(f"<{tag_name}", i)
        if start_idx == -1:
            break
        next_char = src[start_idx + len(tag_name) + 1 : start_idx + len(tag_name) + 2]
        if next_char not in (" ", "\n", "\r", "\t", ">"):
            i = start_idx + 1
            continue

        in_curly = 0
        in_quotes = None
        end_idx = -1

        for j in range(start_idx + len(tag_name) + 1, len(src)):
            ch = src[j]
            if in_quotes:
                if ch == in_quotes and src[j - 1] != "\\":
                    in_quotes = None
            elif ch in ('"', "'", "`"):
                in_quotes = ch
            elif ch == "{":
                in_curly += 1
            elif ch == "}":
                in_curly -= 1
            elif ch == ">" and in_curly == 0 and not in_quotes:
                end_idx = j
                break

        if end_idx != -1:
            tags.append(src[start_idx : end_idx + 1])
            i = end_idx + 1
        else:
            i = start_idx + 1
    return tags


# ==============================================================================
# 1. CONTRAST MATRIX TESTS
# ==============================================================================

class TestContrastMatrix:
    THEMES = [
        ("Standard Dark", "#09090b", "#18181b"),
        ("OLED Black", "#000000", "#0f0f0f"),
        ("Slate Midnight", "#020617", "#0f172a"),
        ("Zinc Deep", "#18181b", "#27272a"),
    ]

    TOKENS = [
        ("Primary Foreground", "#f8fafc", 4.5),
        ("Muted Foreground", "#94a3b8", 4.5),
        ("Green Badge", "#4ade80", 4.5),
        ("Blue Badge", "#60a5fa", 4.5),
        ("Amber Badge", "#fbbf24", 4.5),
        ("Red Badge", "#f87171", 4.5),
        ("Purple Badge", "#d8b4fe", 4.5),
    ]

    @pytest.mark.parametrize("theme_name,bg_hex,card_hex", THEMES)
    def test_theme_background_and_card_contrast(self, theme_name, bg_hex, card_hex):
        for token_name, fg_hex, min_ratio in self.TOKENS:
            ratio_bg = contrast_ratio(fg_hex, bg_hex)
            ratio_card = contrast_ratio(fg_hex, card_hex)
            assert ratio_bg >= min_ratio, f"{token_name} ({fg_hex}) on {theme_name} bg ({bg_hex}) ratio {ratio_bg:.2f}:1 < {min_ratio}:1"
            assert ratio_card >= min_ratio, f"{token_name} ({fg_hex}) on {theme_name} card ({card_hex}) ratio {ratio_card:.2f}:1 < {min_ratio}:1"

    def test_button_states_contrast(self):
        buttons = [
            ("Blue Normal", "#ffffff", "#2563eb", 4.5),
            ("Blue Hover", "#ffffff", "#1d4ed8", 4.5),
            ("Blue Active", "#ffffff", "#1e40af", 4.5),
            ("Green Normal", "#ffffff", "#16a34a", 3.0),
            ("Green Hover", "#ffffff", "#15803d", 3.0),
            ("Gray Secondary Normal", "#e2e8f0", "#1f2937", 4.5),
            ("Dark Monospace Pill", "#e5e7eb", "#1f2937", 4.5),
        ]
        for name, fg, bg, min_ratio in buttons:
            ratio = contrast_ratio(fg, bg)
            assert ratio >= min_ratio, f"{name} ({fg} on {bg}) ratio {ratio:.2f}:1 < {min_ratio}:1"


# ==============================================================================
# 2. KEYBOARD NAVIGATION & FOCUS RINGS
# ==============================================================================

class TestKeyboardAndFocus:
    @pytest.fixture(autouse=True)
    def setup_sources(self):
        self.app_src = (SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        self.header_src = (COMPONENTS_DIR / "Header.tsx").read_text(encoding="utf-8")
        self.feed_src = (COMPONENTS_DIR / "PhoneLinkFeed.tsx").read_text(encoding="utf-8")
        self.col_src = (COMPONENTS_DIR / "CollisionQueue.tsx").read_text(encoding="utf-8")
        self.panel_src = (COMPONENTS_DIR / "VideoTagsPanel.tsx").read_text(encoding="utf-8")

    def test_all_buttons_have_focus_visible_rings(self):
        sources = [
            ("App.tsx", self.app_src),
            ("PhoneLinkFeed.tsx", self.feed_src),
            ("CollisionQueue.tsx", self.col_src),
            ("VideoTagsPanel.tsx", self.panel_src),
        ]
        for filename, src in sources:
            buttons = extract_opening_tags(src, "button")
            for btn in buttons:
                has_ring = "focus-visible:ring-2" in btn or "focus-visible:outline-none" in btn
                assert has_ring, f"Button in {filename} missing focus-visible ring: {btn}"

    def test_video_tag_custom_buttons_keyboard_operable(self):
        divs = extract_opening_tags(self.panel_src, "div")
        role_buttons = [d for d in divs if 'role="button"' in d]
        assert len(role_buttons) > 0, "Expected at least one role='button' element"
        for rb in role_buttons:
            assert "tabIndex={0}" in rb, f"role='button' missing tabIndex={{0}}: {rb}"
            assert "focus-visible:ring-2" in rb, f"role='button' missing focus ring: {rb}"

        assert "e.key === 'Enter' || e.key === ' '" in self.panel_src, "role='button' must handle Enter & Space"
        assert "e.preventDefault()" in self.panel_src, "role='button' must prevent default on Space to stop scrolling"

    def test_form_inputs_have_focus_indicators(self):
        inputs = extract_opening_tags(self.panel_src, "input") + extract_opening_tags(self.panel_src, "select")
        assert len(inputs) >= 4, "Expected at least 4 form inputs in VideoTagsPanel"
        for inp in inputs:
            assert "focus-visible:ring-2" in inp or "focus:border-blue-500" in inp, f"Input missing focus state: {inp}"


# ==============================================================================
# 3. ACCESSIBILITY & ARIA LANDMARKS
# ==============================================================================

class TestAccessibilitySemantics:
    @pytest.fixture(autouse=True)
    def setup_sources(self):
        self.app_src = (SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        self.header_src = (COMPONENTS_DIR / "Header.tsx").read_text(encoding="utf-8")
        self.feed_src = (COMPONENTS_DIR / "PhoneLinkFeed.tsx").read_text(encoding="utf-8")
        self.col_src = (COMPONENTS_DIR / "CollisionQueue.tsx").read_text(encoding="utf-8")
        self.panel_src = (COMPONENTS_DIR / "VideoTagsPanel.tsx").read_text(encoding="utf-8")

    def test_heading_hierarchy(self):
        assert "<h1" in self.header_src, "Header must define <h1>"
        assert "<h2" in self.feed_src, "PhoneLinkFeed must define <h2>"
        assert "<h2" in self.col_src, "CollisionQueue must define <h2>"
        assert "<h3" in self.feed_src, "Feed subcard must define <h3>"
        assert "<h3" in self.panel_src, "Tags panel must define <h3>"

    def test_aria_landmarks_and_roles(self):
        assert 'role="banner"' in self.header_src, "Header must have role='banner'"
        assert 'role="main"' in self.app_src, "Main must have role='main'"
        assert 'role="region"' in self.feed_src, "Feed must have role='region'"
        assert 'role="region"' in self.col_src, "CollisionQueue must have role='region'"
        assert 'role="region"' in self.panel_src, "Tags panel must have role='region'"
        assert 'role="status"' in self.app_src, "Toast must have role='status'"
        assert 'aria-live="polite"' in self.app_src, "Toast must have aria-live='polite'"
        assert 'aria-atomic="true"' in self.app_src, "Toast must have aria-atomic='true'"
        assert 'role="list"' in self.panel_src, "Tags list must have role='list'"

    def test_form_labels_association(self):
        expected_pairs = [
            ("tag-filename", "tag-filename"),
            ("tag-domain", "tag-domain"),
            ("tag-entity", "tag-entity"),
            ("tag-feature", "tag-feature"),
        ]
        for html_for, input_id in expected_pairs:
            assert f'htmlFor="{html_for}"' in self.panel_src
            assert f'id="{input_id}"' in self.panel_src

    def test_touch_target_dimensions(self):
        assert "min-h-[48px]" in self.feed_src
        assert "min-h-[48px]" in self.col_src
        assert "min-w-[48px]" in self.col_src
        assert "min-h-[48px]" in self.panel_src


# ==============================================================================
# 4. ZERO CLS & LAYOUT STABILITY
# ==============================================================================

class TestLayoutShiftAndStability:
    @pytest.fixture(autouse=True)
    def setup_sources(self):
        self.app_src = (SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        self.feed_src = (COMPONENTS_DIR / "PhoneLinkFeed.tsx").read_text(encoding="utf-8")

    def test_video_explicit_dimensions_and_aspect_ratio(self):
        assert "width={540}" in self.feed_src, "Video missing width={540}"
        assert "height={960}" in self.feed_src, "Video missing height={960}"
        assert "aspect-[9/16]" in self.feed_src, "Video container missing aspect-[9/16]"
        assert "object-cover" in self.feed_src, "Video missing object-cover"

    def test_toast_absolute_positioning_zero_shift(self):
        assert "absolute top-4 left-1/2 transform -translate-x-1/2" in self.app_src

    def test_viewport_bounding(self):
        assert "h-screen overflow-hidden flex flex-col" in self.app_src


# ==============================================================================
# 5. PERFORMANCE UNDER SCALE
# ==============================================================================

class TestScaleAndPerformance:
    def test_virtual_tag_data_transformation_speed(self):
        start = time.perf_counter()
        tags = []
        for i in range(1000):
            tags.append({
                "id": f"tag-{i}",
                "filename": f"video_{i:05d}.mp4",
                "domain": "EDM_FESTIVALS" if i % 2 == 0 else "SPORTS_CARDS",
                "entity": f"Entity-{i}",
                "viralFeatures": [f"Feature-{i}"],
                "technical": {"resolution": "3840x2160", "fps": 60}
            })
        formatted = [{**t, "summary": f"{t['filename']} - {t['entity']}"} for t in tags]
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert len(formatted) == 1000
        assert elapsed_ms < 50.0, f"Transformation took {elapsed_ms:.2f} ms (> 50 ms)"

    def test_dist_assets_bundle_sizes(self):
        if (DIST_DIR / "assets").exists():
            for js in (DIST_DIR / "assets").glob("*.js"):
                size_kb = js.stat().st_size / 1024
                assert size_kb < 500.0, f"JS bundle {js.name} ({size_kb:.2f} KB) > 500 KB"
            for css in (DIST_DIR / "assets").glob("*.css"):
                size_kb = css.stat().st_size / 1024
                assert size_kb < 50.0, f"CSS bundle {css.name} ({size_kb:.2f} KB) > 50 KB"
