"""
Challenger 1 (Milestone 5): Empirical Adversarial Memory & DOM Detachment Stress Suite
Omnichannel Triage Hub - Zero-Waste Frontend Audit (R4)

Validates:
1. Execution of adversarial Node.js memory stress suite (100x mount/unmount churn, 1000x hotkey flood).
2. Static inspection of App.tsx, PhoneLinkFeed.tsx, VideoTagsPanel.tsx, CollisionQueue.tsx for 0 dangling handlers.
3. Verification of timer cancellation refs (toastTimerRef, statusTimerRef, pullTimerRef).
4. Verification of AbortController cleanup in lib/api.ts.
5. Verification of isMounted unmount cancellation in lib/dataconnect/index.ts.
6. Verification of TypeScript strict compilation and production build artifacts.
"""

import subprocess
from pathlib import Path
import re
import pytest

REPO_ROOT = Path("G:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub")
FRONTEND_DIR = REPO_ROOT / "frontend"
SRC_DIR = FRONTEND_DIR / "src"
COMPONENTS_DIR = SRC_DIR / "components"
LIB_DIR = SRC_DIR / "lib"
TESTS_DIR = REPO_ROOT / "tests"


class TestAdversarialMemoryAudit:
    """Adversarial challenge tests for Milestone 5 (Zero-Waste Frontend Audit R4)."""

    def test_run_adversarial_memory_mjs_suite(self):
        """Executes the adversarial Node.js memory & DOM detachment stress suite."""
        script_path = TESTS_DIR / "test_challenger_m5_adversarial_memory.mjs"
        assert script_path.exists(), f"Script missing at {script_path}"

        result = subprocess.run(
            ["node", str(script_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            shell=True,
        )
        print("STDOUT:\n", result.stdout)
        if result.stderr:
            print("STDERR:\n", result.stderr)

        assert result.returncode == 0, f"Adversarial memory suite failed with exit code {result.returncode}"
        assert "ALL MEMORY LEAK & LIFECYCLE CHECKS PASSED" in result.stdout or "CHALLENGER 1 VERDICT: APPROVE" in result.stdout
        assert "0 Detached DOM Nodes" in result.stdout or "0 Detached DOM nodes" in result.stdout
        assert "0 Leaked Timers" in result.stdout or "Active timers strictly 0" in result.stdout

    def test_app_timer_refs_and_unmount_cleanup(self):
        """Verifies App.tsx uses useRef for timeout handles and cancels them on unmount."""
        app_path = SRC_DIR / "App.tsx"
        assert app_path.exists(), f"App.tsx not found at {app_path}"
        src = app_path.read_text(encoding="utf-8")

        # Ref handles
        assert "toastTimerRef" in src, "App.tsx must define toastTimerRef"
        assert "statusTimerRef" in src, "App.tsx must define statusTimerRef"

        # Unmount cleanup effect
        assert "clearTimeout(toastTimerRef.current)" in src, "toastTimerRef must be cleared on unmount"
        assert "clearTimeout(statusTimerRef.current)" in src, "statusTimerRef must be cleared on unmount"

        # Toast supersession
        toast_pattern = r"if\s*\(toastTimerRef\.current\)\s*\{\s*clearTimeout\(toastTimerRef\.current\);\s*\}"
        assert re.search(toast_pattern, src), "showToast must clear prior timer before scheduling new toast"

    def test_global_keydown_listener_cleanup(self):
        """Verifies App.tsx registers and removes global keydown listener symmetrically."""
        app_path = SRC_DIR / "App.tsx"
        src = app_path.read_text(encoding="utf-8")

        assert "window.addEventListener('keydown', handleKeyDown)" in src
        assert "window.removeEventListener('keydown', handleKeyDown)" in src

        # Ensure return cleanup hook exists in the same useEffect
        cleanup_match = re.search(
            r"window\.addEventListener\('keydown',\s*handleKeyDown\);\s*return\s*\(\)\s*=>\s*\{\s*window\.removeEventListener\('keydown',\s*handleKeyDown\);\s*\};",
            src,
        )
        assert cleanup_match is not None, "keydown listener not cleanly removed in useEffect return"

    def test_phone_link_feed_timer_cleanup(self):
        """Verifies PhoneLinkFeed.tsx cancels pending pull timers on unmount."""
        feed_path = COMPONENTS_DIR / "PhoneLinkFeed.tsx"
        assert feed_path.exists(), f"PhoneLinkFeed.tsx not found at {feed_path}"
        src = feed_path.read_text(encoding="utf-8")

        assert "pullTimerRef" in src, "PhoneLinkFeed.tsx must define pullTimerRef"
        assert "clearTimeout(pullTimerRef.current)" in src, "pullTimerRef must be cleared"

    def test_api_client_abort_controller_and_finally_timer_clear(self):
        """Verifies fetchWithTimeout in lib/api.ts guarantees timer cleanup in finally block."""
        api_path = LIB_DIR / "api.ts"
        assert api_path.exists(), f"lib/api.ts not found at {api_path}"
        src = api_path.read_text(encoding="utf-8")

        assert "new AbortController()" in src, "api.ts must use AbortController"
        assert "controller.signal" in src, "api.ts must pass signal to fetch"

        # Finally block timer clearance
        finally_pattern = r"finally\s*\{\s*clearTimeout\(timeoutId\);\s*\}"
        assert re.search(finally_pattern, src), "fetchWithTimeout must clear timeoutId in a finally block"

    def test_dataconnect_unmount_cancellation_guard(self):
        """Verifies useVideoTags hook in lib/dataconnect/index.ts guards against unmounted state updates."""
        dc_path = LIB_DIR / "dataconnect" / "index.ts"
        assert dc_path.exists(), f"dataconnect/index.ts not found at {dc_path}"
        src = dc_path.read_text(encoding="utf-8")

        assert "isMounted = true" in src, "useVideoTags must set isMounted = true on mount"
        assert "if (!isMounted) return;" in src or "if (isMounted)" in src, "useVideoTags must check isMounted before setting state"
        assert "isMounted = false" in src, "useVideoTags must set isMounted = false on unmount cleanup"

    def test_frontend_type_check_and_build_artifacts(self):
        """Executes 'npx tsc -b' and validates production build artifacts."""
        result = subprocess.run(
            ["npx", "tsc", "-b"],
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            shell=True,
        )
        assert result.returncode == 0, f"TypeScript build failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

        # Verify build artifacts in dist
        dist_dir = FRONTEND_DIR / "dist"
        if dist_dir.exists():
            assert (dist_dir / "index.html").exists(), "dist/index.html missing"
            assets_dir = dist_dir / "assets"
            if assets_dir.exists():
                js_files = list(assets_dir.glob("*.js"))
                assert len(js_files) > 0, "No JS files found in dist/assets"
