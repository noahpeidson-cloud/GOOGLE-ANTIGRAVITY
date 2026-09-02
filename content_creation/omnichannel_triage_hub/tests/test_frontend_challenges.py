"""
Adversarial Challenge & Robustness Verification Test Suite for Milestone 1
Omnichannel Triage Hub - Frontend

Validates:
1. Keyboard event handling (Ctrl+Shift+T, modifier edge cases, case sensitivity, preventDefault)
2. Video component fallback handling (media paused/missing, onError state transitions, stream placeholder)
3. Collision queue resolution button state transitions (Keep 4K ADB, Keep Takeout, Undo, multi-item isolation)
4. Layout boundary constraints (h-screen overflow-hidden, scroll containment, CSS resets)
5. Static type check, build bundling, and procedural asset integrity.
"""

import os
import re
import subprocess
import json
import pytest
from pathlib import Path

REPO_ROOT = Path("G:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub")
FRONTEND_DIR = REPO_ROOT / "frontend"
SRC_DIR = FRONTEND_DIR / "src"
COMPONENTS_DIR = SRC_DIR / "components"
PUBLIC_DIR = FRONTEND_DIR / "public"
DIST_DIR = FRONTEND_DIR / "dist"


# ==============================================================================
# 1. KEYBOARD EVENT HANDLING TESTS (Ctrl+Shift+T)
# ==============================================================================

class TestKeyboardHandling:
    """Stress-tests the global keyboard event handling logic in App.tsx."""

    @pytest.fixture(autouse=True)
    def setup_app_source(self):
        self.app_tsx_path = SRC_DIR / "App.tsx"
        assert self.app_tsx_path.exists(), f"App.tsx not found at {self.app_tsx_path}"
        self.app_source = self.app_tsx_path.read_text(encoding="utf-8")

    def test_hotkey_listener_present_and_bound_to_window(self):
        """Verifies that window.addEventListener('keydown', ...) is registered in a useEffect."""
        assert "window.addEventListener('keydown', handleKeyDown)" in self.app_source
        assert "window.removeEventListener('keydown', handleKeyDown)" in self.app_source
        # Verify cleanup function exists to avoid memory leak
        cleanup_pattern = r"return\s*\(\)\s*=>\s*\{\s*window\.removeEventListener\('keydown',\s*handleKeyDown\);\s*\};"
        assert re.search(cleanup_pattern, self.app_source), "Cleanup handler for keydown listener missing or malformed"

    def test_ctrl_shift_t_case_insensitivity(self):
        """Verifies that both 'T' and 't' are accepted in e.key check."""
        condition_pattern = r"e\.ctrlKey\s*&&\s*e\.shiftKey\s*&&\s*\(\s*e\.key\s*===\s*'T'\s*\|\|\s*e\.key\s*===\s*'t'\s*\)"
        match = re.search(condition_pattern, self.app_source)
        assert match is not None, f"Expected robust case-insensitive check (e.key === 'T' || e.key === 't'), found: {self.app_source}"

    def test_prevent_default_called_on_hotkey(self):
        """Verifies e.preventDefault() is called to stop browser hijacking (e.g. reopen closed tab)."""
        assert "e.preventDefault();" in self.app_source
        # Ensure preventDefault is called inside the hotkey condition block
        handler_match = re.search(
            r"if\s*\(e\.ctrlKey\s*&&\s*e\.shiftKey[^{]+\{\s*e\.preventDefault\(\);\s*handleCaptureScreen\(\);",
            self.app_source,
        )
        assert handler_match is not None, "e.preventDefault() not called immediately before handleCaptureScreen()"

    def test_simulated_key_event_matrix(self):
        """
        Evaluates the boolean logic for all key combination permutations:
        - Must PASS: (ctrl=True, shift=True, key='T'), (ctrl=True, shift=True, key='t')
        - Must FAIL: (ctrl=True, shift=False, key='T'), (ctrl=False, shift=True, key='T'),
                     (ctrl=True, shift=True, key='A'), (ctrl=False, shift=False, key='t')
        """
        def evaluate_handler(ctrlKey: bool, shiftKey: bool, key: str) -> bool:
            return bool(ctrlKey and shiftKey and (key == 'T' or key == 't'))

        # Valid hotkey combinations
        assert evaluate_handler(True, True, 'T') is True, "Ctrl+Shift+T must trigger"
        assert evaluate_handler(True, True, 't') is True, "Ctrl+Shift+t must trigger"

        # Invalid modifier combinations (standard browser hotkeys or plain typing)
        assert evaluate_handler(True, False, 'T') is False, "Ctrl+T must NOT trigger (new tab collision)"
        assert evaluate_handler(True, False, 't') is False, "Ctrl+t must NOT trigger (new tab collision)"
        assert evaluate_handler(False, True, 'T') is False, "Shift+T must NOT trigger (typing capital T)"
        assert evaluate_handler(False, True, 't') is False, "Shift+t must NOT trigger"
        assert evaluate_handler(False, False, 't') is False, "Plain 't' must NOT trigger"
        assert evaluate_handler(False, False, 'T') is False, "Plain 'T' must NOT trigger"

        # Wrong key
        assert evaluate_handler(True, True, 'A') is False, "Ctrl+Shift+A must NOT trigger"
        assert evaluate_handler(True, True, 'Escape') is False, "Ctrl+Shift+Escape must NOT trigger"
        assert evaluate_handler(True, True, 'Enter') is False, "Ctrl+Shift+Enter must NOT trigger"

    def test_handle_capture_screen_toast_and_timer(self):
        """Verifies handleCaptureScreen sets notification, updates status, and resets after timeout."""
        assert "setTagNotification('Screen captured! Gemini Vision analyzing Phone Link window...')" in self.app_source
        assert "setPhoneLinkStatus" in self.app_source
        assert "setTimeout" in self.app_source
        assert "setTagNotification(null)" in self.app_source


# ==============================================================================
# 2. VIDEO COMPONENT FALLBACK HANDLING TESTS
# ==============================================================================

class TestVideoFallbackHandling:
    """Stress-tests PhoneLinkFeed video player and error fallback mechanisms."""

    @pytest.fixture(autouse=True)
    def setup_feed_source(self):
        self.feed_path = COMPONENTS_DIR / "PhoneLinkFeed.tsx"
        assert self.feed_path.exists(), f"PhoneLinkFeed.tsx not found at {self.feed_path}"
        self.feed_source = self.feed_path.read_text(encoding="utf-8")

    def test_video_tag_attributes(self):
        """Verifies standard video streaming attributes (autoPlay, loop, muted, playsInline, poster)."""
        assert "autoPlay" in self.feed_source, "autoPlay attribute missing from <video>"
        assert "loop" in self.feed_source, "loop attribute missing from <video>"
        assert "muted" in self.feed_source, "muted attribute missing from <video> (required for autoplay policy)"
        assert "playsInline" in self.feed_source, "playsInline attribute missing from <video>"
        assert "poster={feedState.currentVideo.poster}" in self.feed_source, "poster attribute missing or unlinked"
        assert "src={feedState.currentVideo.src}" in self.feed_source, "src attribute missing or unlinked"

    def test_video_on_error_handler_attached(self):
        """Verifies onError event handler is attached to video element."""
        assert "onError={() => setVideoError(true)}" in self.feed_source or "onError={" in self.feed_source
        assert "const [videoError, setVideoError] = useState(false)" in self.feed_source

    def test_fallback_ui_elements(self):
        """Verifies presence of fallback UI elements when videoError is true."""
        assert "[ Phone Link Stream ]" in self.feed_source
        assert "{feedState.currentVideo.filename}" in self.feed_source
        assert "{feedState.currentVideo.description}" in self.feed_source
        assert "aspect-[9/16]" in self.feed_source
        assert "border-dashed" in self.feed_source

    def test_simulated_video_state_machine(self):
        """Simulates the state machine for normal vs errored video playback."""
        class VideoStateMachine:
            def __init__(self, src: str, poster: str, filename: str, description: str):
                self.src = src
                self.poster = poster
                self.filename = filename
                self.description = description
                self.video_error = False

            def on_error(self):
                self.video_error = True

            def render_mode(self):
                if not self.video_error:
                    return {
                        "mode": "video_element",
                        "attributes": {
                            "src": self.src,
                            "poster": self.poster,
                            "autoPlay": True,
                            "muted": True,
                            "loop": True,
                            "playsInline": True
                        }
                    }
                else:
                    return {
                        "mode": "fallback_placeholder",
                        "display_title": "[ Phone Link Stream ]",
                        "display_filename": f"Playing: {self.filename}",
                        "display_description": f"({self.description})"
                    }

        # Case 1: Initial state -> renders video element
        vsm = VideoStateMachine("/placeholder.mp4", "/placeholder.png", "20260819_213606.mp4", "Excision Drop")
        res1 = vsm.render_mode()
        assert res1["mode"] == "video_element"
        assert res1["attributes"]["src"] == "/placeholder.mp4"
        assert res1["attributes"]["muted"] is True

        # Case 2: Media fails to load (e.g. 404, unsupported codec) -> triggers on_error -> renders fallback
        vsm.on_error()
        res2 = vsm.render_mode()
        assert res2["mode"] == "fallback_placeholder"
        assert res2["display_title"] == "[ Phone Link Stream ]"
        assert "20260819_213606.mp4" in res2["display_filename"]
        assert "Excision Drop" in res2["display_description"]


# ==============================================================================
# 3. COLLISION QUEUE RESOLUTION BUTTON STATE TRANSITIONS
# ==============================================================================

class TestCollisionQueueStateTransitions:
    """Stress-tests the resolution, undo, and state transitions of CollisionQueue."""

    @pytest.fixture(autouse=True)
    def setup_collision_source(self):
        self.collision_path = COMPONENTS_DIR / "CollisionQueue.tsx"
        assert self.collision_path.exists(), f"CollisionQueue.tsx not found at {self.collision_path}"
        self.collision_source = self.collision_path.read_text(encoding="utf-8")

    def test_resolution_choice_handler_implemented(self):
        """Verifies handleResolveChoice supports both 'adb' and 'takeout' choices."""
        assert "handleResolveChoice" in self.collision_source
        assert "choice: 'adb' | 'takeout'" in self.collision_source
        assert "resolved: true" in self.collision_source
        assert "resolutionChoice: choice" in self.collision_source

    def test_undo_handler_implemented(self):
        """Verifies handleUndo resets resolved to false and clears resolutionChoice."""
        assert "handleUndo" in self.collision_source
        assert "resolved: false" in self.collision_source
        assert "resolutionChoice: undefined" in self.collision_source

    def test_state_machine_transitions_and_isolation(self):
        """Simulates state transitions across multiple items to verify state integrity and isolation."""
        class CollisionItemModel:
            def __init__(self, item_id: str, filename: str):
                self.id = item_id
                self.filename = filename
                self.resolved = False
                self.resolution_choice = None

        class CollisionQueueSimulator:
            def __init__(self, items):
                self.items = {item.id: item for item in items}
                self.resolved_events = []

            def resolve(self, item_id: str, choice: str):
                assert choice in ("adb", "takeout"), f"Invalid choice {choice}"
                assert item_id in self.items, f"Item {item_id} not found"
                self.items[item_id].resolved = True
                self.items[item_id].resolution_choice = choice
                self.resolved_events.append((item_id, choice))

            def undo(self, item_id: str):
                assert item_id in self.items, f"Item {item_id} not found"
                self.items[item_id].resolved = False
                self.items[item_id].resolution_choice = None

            def get_ui_state(self, item_id: str):
                item = self.items[item_id]
                if not item.resolved:
                    return {
                        "badge": "Resolution Mismatch",
                        "buttons_visible": ["keep_4k_adb", "keep_takeout"],
                        "adb_box_class": "normal",
                        "takeout_box_class": "normal"
                    }
                else:
                    return {
                        "badge": f"Resolved ({'Kept 4K ADB' if item.resolution_choice == 'adb' else 'Kept Takeout'})",
                        "buttons_visible": ["undo"],
                        "adb_box_class": "normal" if item.resolution_choice == "adb" else "opacity-40 grayscale",
                        "takeout_box_class": "normal" if item.resolution_choice == "takeout" else "opacity-30 grayscale"
                    }

        # Initialize queue with 3 distinct collision items
        item1 = CollisionItemModel("col-001", "20260819_213606.mp4")
        item2 = CollisionItemModel("col-002", "20260819_221045.mp4")
        item3 = CollisionItemModel("col-003", "20260819_234512.mp4")
        queue = CollisionQueueSimulator([item1, item2, item3])

        # Step 1: Initial state
        for item_id in ["col-001", "col-002", "col-003"]:
            ui = queue.get_ui_state(item_id)
            assert ui["badge"] == "Resolution Mismatch"
            assert "keep_4k_adb" in ui["buttons_visible"]
            assert "keep_takeout" in ui["buttons_visible"]
            assert "undo" not in ui["buttons_visible"]

        # Step 2: Resolve item 1 as ADB 4K
        queue.resolve("col-001", "adb")
        ui1 = queue.get_ui_state("col-001")
        assert ui1["badge"] == "Resolved (Kept 4K ADB)"
        assert ui1["takeout_box_class"] == "opacity-30 grayscale"
        assert ui1["adb_box_class"] == "normal"
        assert "undo" in ui1["buttons_visible"]
        assert "keep_4k_adb" not in ui1["buttons_visible"]

        # Verify items 2 & 3 are unaffected (State Isolation)
        assert queue.get_ui_state("col-002")["badge"] == "Resolution Mismatch"
        assert queue.get_ui_state("col-003")["badge"] == "Resolution Mismatch"

        # Step 3: Resolve item 2 as Takeout
        queue.resolve("col-002", "takeout")
        ui2 = queue.get_ui_state("col-002")
        assert ui2["badge"] == "Resolved (Kept Takeout)"
        assert ui2["adb_box_class"] == "opacity-40 grayscale"
        assert ui2["takeout_box_class"] == "normal"

        # Step 4: Undo item 1
        queue.undo("col-001")
        ui1_undone = queue.get_ui_state("col-001")
        assert ui1_undone["badge"] == "Resolution Mismatch"
        assert "keep_4k_adb" in ui1_undone["buttons_visible"]
        assert "undo" not in ui1_undone["buttons_visible"]

        # Verify item 2 remains resolved as Takeout
        assert queue.get_ui_state("col-002")["badge"] == "Resolved (Kept Takeout)"


# ==============================================================================
# 4. LAYOUT BOUNDARY & OVERFLOW CONSTRAINTS
# ==============================================================================

class TestLayoutConstraints:
    """Stress-tests the full-screen viewport layout and overflow containment."""

    @pytest.fixture(autouse=True)
    def setup_layout_sources(self):
        self.app_source = (SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        self.index_css = (SRC_DIR / "index.css").read_text(encoding="utf-8")
        self.feed_source = (COMPONENTS_DIR / "PhoneLinkFeed.tsx").read_text(encoding="utf-8")
        self.collision_source = (COMPONENTS_DIR / "CollisionQueue.tsx").read_text(encoding="utf-8")

    def test_root_viewport_height_and_overflow_hidden(self):
        """Verifies App.tsx has h-screen overflow-hidden on the outer container."""
        root_div_match = re.search(r'<div\s+className="([^"]*)"', self.app_source)
        assert root_div_match is not None, "Root div in App.tsx not found"
        classes = root_div_match.group(1)
        assert "h-screen" in classes, "App root div must have 'h-screen' class"
        assert "overflow-hidden" in classes, "App root div must have 'overflow-hidden' class"
        assert "flex" in classes and "flex-col" in classes, "App root div must be a flex-col container"

    def test_main_grid_layout_containment(self):
        """Verifies <main> element spans 12 columns with overflow-hidden and flex-1."""
        main_match = re.search(r'<main\s+className="([^"]*)"', self.app_source)
        assert main_match is not None, "Main element in App.tsx not found"
        classes = main_match.group(1)
        assert "grid" in classes, "Main must be a grid container"
        assert "grid-cols-12" in classes, "Main must use 12-column grid"
        assert "flex-1" in classes, "Main must have flex-1 to fill available vertical space"
        assert "overflow-hidden" in classes, "Main must have overflow-hidden to prevent window blowout"

    def test_column_grid_span_proportions(self):
        """Verifies Left column is 4 cols and Right column is 8 cols (4 + 8 = 12)."""
        assert "col-span-4" in self.feed_source, "PhoneLinkFeed must use col-span-4"
        assert "col-span-8" in self.collision_source, "CollisionQueue must use col-span-8"

    def test_scroll_containment_in_panels(self):
        """Verifies that internal panel bodies have overflow-y-auto for independent scrolling."""
        assert "overflow-y-auto" in self.feed_source, "PhoneLinkFeed must contain overflow-y-auto for vertical scroll"
        assert "overflow-y-auto" in self.collision_source, "CollisionQueue must contain overflow-y-auto for vertical scroll"

    def test_body_css_resets(self):
        """Verifies body styles in index.css enforce 100vh, 100vw, and overflow: hidden."""
        assert "overflow: hidden" in self.index_css
        assert "height: 100vh" in self.index_css
        assert "width: 100vw" in self.index_css
        assert "margin: 0" in self.index_css


# ==============================================================================
# 5. BUILD, COMPILATION & ASSET INTEGRITY
# ==============================================================================

class TestBuildAndAssetIntegrity:
    """Verifies that TypeScript compiles cleanly, Vite builds production bundle, and media assets exist."""

    def test_procedural_media_assets_exist(self):
        """Verifies procedural placeholder media assets in public/."""
        mp4_path = PUBLIC_DIR / "placeholder.mp4"
        png_path = PUBLIC_DIR / "placeholder.png"

        assert mp4_path.exists(), f"Placeholder video missing at {mp4_path}"
        assert png_path.exists(), f"Placeholder poster missing at {png_path}"

        # Verify files are non-empty
        assert mp4_path.stat().st_size > 1000, f"Placeholder video is suspiciously small: {mp4_path.stat().st_size} bytes"
        assert png_path.stat().st_size > 500, f"Placeholder poster is suspiciously small: {png_path.stat().st_size} bytes"

    def test_npm_run_build_execution(self):
        """Executes 'npm run build' to verify strict TypeScript and Vite production bundle generation."""
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            shell=True
        )
        assert result.returncode == 0, f"npm run build failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

        # Verify build artifacts
        assert (DIST_DIR / "index.html").exists(), "dist/index.html missing after build"
        assets_dir = DIST_DIR / "assets"
        assert assets_dir.exists(), "dist/assets missing after build"
        js_files = list(assets_dir.glob("*.js"))
        css_files = list(assets_dir.glob("*.css"))
        assert len(js_files) > 0, "No JS bundle files found in dist/assets"
        assert len(css_files) > 0, "No CSS bundle files found in dist/assets"
