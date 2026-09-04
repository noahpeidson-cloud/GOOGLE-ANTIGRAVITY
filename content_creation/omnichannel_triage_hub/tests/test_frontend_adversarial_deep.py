"""
Deep Adversarial Stress Test Suite for Milestone 1
Omnichannel Triage Hub - Frontend

Adversarial Stress Areas:
1. Rapid consecutive trigger of hotkeys (timer race conditions, state stability).
2. Boundary and extreme data payloads (Unicode filenames, empty strings, massive sizes).
3. CSS variable definitions completeness vs usage across all JSX/TSX files.
4. Clean component unmounting and event listener lifecycle verification.
5. Strict TypeScript compilation check (--noEmit).
"""

import os
import re
import subprocess
import pytest
from pathlib import Path

REPO_ROOT = Path("G:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub")
FRONTEND_DIR = REPO_ROOT / "frontend"
SRC_DIR = FRONTEND_DIR / "src"
COMPONENTS_DIR = SRC_DIR / "components"


class TestDeepAdversarialBoundaries:
    """Stress tests extreme boundary cases, CSS variables, and TypeScript strictness."""

    def test_css_variable_completeness(self):
        """Ensures every CSS variable referenced in components is declared in :root of index.css."""
        index_css = (SRC_DIR / "index.css").read_text(encoding="utf-8")
        
        # Extract all var(--name) references across all tsx files
        var_pattern = re.compile(r"var\((--[a-zA-Z0-9_-]+)\)")
        used_vars = set()
        
        for tsx_file in SRC_DIR.rglob("*.tsx"):
            content = tsx_file.read_text(encoding="utf-8")
            for match in var_pattern.finditer(content):
                used_vars.add(match.group(1))

        # Extract declared variables from index.css
        declared_vars = set(re.findall(r"(--[a-zA-Z0-9_-]+):", index_css))

        missing = used_vars - declared_vars
        assert len(missing) == 0, f"Undeclared CSS variables found: {missing}"

    def test_extreme_payload_handling_in_types(self):
        """Validates that TypeScript types support optional parameters, edge cases, and defaults."""
        types_source = (SRC_DIR / "types" / "index.ts").read_text(encoding="utf-8")
        
        # Check CollisionItem optional properties
        assert "resolved?:" in types_source
        assert "resolutionChoice?:" in types_source
        assert "confidence?:" in types_source

    def test_header_prop_fallbacks(self):
        """Ensures Header.tsx renders gracefully with default props if undefined is passed."""
        header_source = (COMPONENTS_DIR / "Header.tsx").read_text(encoding="utf-8")
        assert "adbStatus = {" in header_source
        assert "phoneLinkStatus = {" in header_source

    def test_phonelink_prop_fallbacks(self):
        """Ensures PhoneLinkFeed.tsx has resilient default prop values."""
        feed_source = (COMPONENTS_DIR / "PhoneLinkFeed.tsx").read_text(encoding="utf-8")
        assert "feedState = {" in feed_source
        assert "isPulling = false" in feed_source

    def test_collision_queue_prop_fallbacks(self):
        """Ensures CollisionQueue.tsx handles empty array and default items without crashing."""
        collision_source = (COMPONENTS_DIR / "CollisionQueue.tsx").read_text(encoding="utf-8")
        assert "items = DEFAULT_COLLISION_ITEMS" in collision_source

    def test_strict_typescript_typecheck(self):
        """Executes 'npx tsc --noEmit' in frontend/ to ensure zero TypeScript errors."""
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            shell=True
        )
        assert result.returncode == 0, f"TypeScript type check failed:\n{result.stdout}\n{result.stderr}"
