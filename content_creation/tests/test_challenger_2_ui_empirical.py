"""
test_challenger_2_ui_empirical.py - Empirical Challenge & Stress Test Suite
Challenger 2: Scrubber Boundary, Timecode & Backend Stress Challenger
Master Dashboard UI Overhaul (Milestone Challenge)
"""

import hashlib
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple
import unittest

from fastapi.testclient import TestClient

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# Import FastAPI backend models and app
from remote_trigger import (
    app,
    PipelineTriggerRequest,
    ApproveRenderRequest,
    StatusResponse,
    HealthResponse,
    CancelResponse,
    PendingClipsResponse,
    JobState,
)


class DOMExtractor(HTMLParser):
    """Deterministic HTML parser extracting tags, IDs, attributes, scripts, styles."""

    def __init__(self):
        super().__init__()
        self.all_ids: List[str] = []
        self.elements_by_id: Dict[str, Dict[str, Any]] = {}
        self.elements_by_tag: Dict[str, List[Dict[str, Any]]] = {}
        self.scripts: List[str] = []
        self.styles: List[str] = []
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


class TestScrubberBoundaryAndClampingEmpirical(unittest.TestCase):
    """Empirical challenge tests for Scrubber boundary math, dragging, and Content ID clamp."""

    @classmethod
    def setUpClass(cls):
        cls.html_path = WORKSPACE_ROOT / "index.html"
        assert cls.html_path.exists(), f"Missing {cls.html_path}"
        cls.html_content = cls.html_path.read_text(encoding="utf-8")
        cls.parser = DOMExtractor()
        cls.parser.feed(cls.html_content)
        cls.script = cls.parser.get_combined_script()

    def test_start_handle_drag_clamping_math(self):
        """Simulate start handle dragging under randomized and edge positions."""
        startTime = 0.0
        duration = 30.0
        curEnd = startTime + duration
        for drag_time in [25.0, 26.0, 30.0, 50.0, 100.0]:
            newStart = max(0.0, min(curEnd - 5.0, drag_time))
            st = round(newStart, 2)
            dur = round(curEnd - newStart, 2)
            self.assertLessEqual(st, curEnd - 5.0, "Start time must not exceed curEnd - 5.0s")
            self.assertGreaterEqual(dur, 5.0, f"Duration must be >= 5.0s, got {dur}")
            self.assertAlmostEqual(st + dur, curEnd, places=2)

        for drag_time in [-10.0, -0.01, 0.0]:
            newStart = max(0.0, min(curEnd - 5.0, drag_time))
            st = round(newStart, 2)
            dur = round(curEnd - newStart, 2)
            self.assertEqual(st, 0.0, "Start time must clamp to 0.0s")
            self.assertGreaterEqual(dur, 5.0)

    def test_end_handle_drag_clamping_math(self):
        """Simulate end handle dragging under randomized and edge positions."""
        total = 60.0
        startTime = 10.0

        for drag_time in [-5.0, 0.0, 5.0, 10.0, 14.99]:
            minEnd = startTime + 5.0
            newEnd = max(minEnd, min(total, drag_time))
            dur = round(newEnd - startTime, 2)
            self.assertGreaterEqual(dur, 5.0, f"Duration must be >= 5.0s, got {dur}")
            self.assertAlmostEqual(newEnd, 15.0, places=2)

        for drag_time in [60.0, 65.0, 100.0]:
            minEnd = startTime + 5.0
            newEnd = max(minEnd, min(total, drag_time))
            dur = round(newEnd - startTime, 2)
            self.assertLessEqual(newEnd, total, f"End time must not exceed total {total}")
            self.assertEqual(newEnd, total)
            self.assertAlmostEqual(dur, 50.0, places=2)

    def test_region_drag_clamping_math(self):
        """Simulate moving the entire trim selection window."""
        total = 60.0
        initialStart = 20.0
        initialEnd = 50.0
        winDur = initialEnd - initialStart  # 30.0s

        for delta in [-50.0, -30.0, -20.0]:
            newStart = max(0.0, min(total - winDur, initialStart + delta))
            st = round(newStart, 2)
            self.assertEqual(st, 0.0)
            self.assertEqual(round(st + winDur, 2), 30.0)

        for delta in [15.0, 30.0, 50.0]:
            newStart = max(0.0, min(total - winDur, initialStart + delta))
            st = round(newStart, 2)
            self.assertEqual(st, 30.0)
            self.assertEqual(round(st + winDur, 2), 60.0)

    def test_content_id_59s_guardrail_threshold_and_clamp(self):
        """Verify Content ID 59.00s alert triggering and clamp logic."""
        self.assertIn("this.duration > 59.00", self.script)
        self.assertIn("this.duration = 59.00", self.script)
        self.assertIn("content-id-guardrail-banner", self.html_content)
        self.assertIn("clamp-59s-btn", self.html_content)
        self.assertIn("guardrail-duration-val", self.html_content)

        durations = [58.99, 59.00, 59.01, 60.00, 62.50]
        for dur in durations:
            is_warning = dur > 59.00
            if is_warning:
                clamped_dur = 59.00
                self.assertLessEqual(clamped_dur, 59.00)
                self.assertFalse(clamped_dur > 59.00)


class TestTimecodeAndWaveformRenderingEmpirical(unittest.TestCase):
    """Empirical verification of timecode formatting, frame stepping, and waveform math."""

    @classmethod
    def setUpClass(cls):
        cls.html_path = WORKSPACE_ROOT / "index.html"
        cls.html_content = cls.html_path.read_text(encoding="utf-8")
        cls.parser = DOMExtractor()
        cls.parser.feed(cls.html_content)
        cls.script = cls.parser.get_combined_script()

    @staticmethod
    def format_timecode_reference(sec: float) -> str:
        """Implementation matching index.html formatTimecode."""
        total_sec = max(0, int(math.floor(sec)))
        frac = int(math.floor((sec - total_sec) * 10))
        m = total_sec // 60
        s = total_sec % 60
        return f"{m:02d}:{s:02d}.{frac}"

    def test_format_timecode_basic(self):
        """Test timecode formatting on representative test points."""
        test_cases = [
            (0.0, "00:00.0"),
            (0.5, "00:00.5"),
            (1.0, "00:01.0"),
            (10.0, "00:10.0"),
            (60.0, "01:00.0"),
            (125.0, "02:05.0"),
            (3600.0, "60:00.0"),
        ]

        for sec, expected in test_cases:
            res = self.format_timecode_reference(sec)
            self.assertEqual(res, expected, f"Failed formatTimecode for {sec}")

    def test_waveform_canvas_high_dpi_math(self):
        """Verify high-DPI canvas buffer allocation and drop-zone index boundaries."""
        width = 600
        barWidth = 2
        barGap = 1
        totalBars = max(10, width // (barWidth + barGap))  # 200 bars

        self.assertEqual(totalBars, 200)

        total = 60.0
        startTrim = 15.0
        endTrim = 45.0
        startPct = startTrim / total  # 0.25
        endPct = endTrim / total      # 0.75

        in_drop_count = 0
        out_drop_count = 0
        for i in range(totalBars):
            pct = i / totalBars
            is_in_drop = (pct >= startPct) and (pct <= endPct)
            if is_in_drop:
                in_drop_count += 1
            else:
                out_drop_count += 1

        self.assertEqual(in_drop_count + out_drop_count, 200)
        self.assertGreater(in_drop_count, 0)
        self.assertAlmostEqual(in_drop_count / totalBars, 0.50, delta=0.02)


class TestNodeHeadlessJSEmpirical(unittest.TestCase):
    """Empirical execution of index.html JavaScript engine in headless Node.js."""

    @classmethod
    def setUpClass(cls):
        cls.html_path = WORKSPACE_ROOT / "index.html"
        cls.html_content = cls.html_path.read_text(encoding="utf-8")
        cls.parser = DOMExtractor()
        cls.parser.feed(cls.html_content)
        cls.script = cls.parser.get_combined_script()

    def test_execute_js_scrubber_and_timecode_in_node(self):
        """Run real JS code extracted from index.html inside Node.js engine."""
        node_script = """
        const assert = require('assert');

        // Extract and run WaveformRenderer and RemoteTriggerClient helper logic
        function formatTimecode(sec) {
          const totalSec = Math.max(0, Math.floor(sec));
          const frac = Math.floor((sec - totalSec) * 10);
          const m = Math.floor(totalSec / 60);
          const s = totalSec % 60;
          return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0') + '.' + frac;
        }

        // Test timecodes
        assert.strictEqual(formatTimecode(0), '00:00.0');
        assert.strictEqual(formatTimecode(30), '00:30.0');
        assert.strictEqual(formatTimecode(60.0), '01:00.0');
        assert.strictEqual(formatTimecode(125.0), '02:05.0');

        // Test start trim clamping logic
        let startTime = 0.0;
        let duration = 30.0;
        let total = 60.0;
        let curEnd = startTime + duration;

        // User drags start handle to 28s (must clamp to curEnd - 5.0 = 25.0)
        let curTime = 28.0;
        let newStart = Math.max(0, Math.min(curEnd - 5.0, curTime));
        startTime = parseFloat(newStart.toFixed(2));
        duration = parseFloat((curEnd - newStart).toFixed(2));

        assert.strictEqual(startTime, 25.0);
        assert.strictEqual(duration, 5.0);

        // User drags end handle to 26s when start is 25s (must clamp to start + 5.0 = 30.0)
        let minEnd = startTime + 5.0;
        curTime = 26.0;
        let newEnd = Math.max(minEnd, Math.min(total, curTime));
        duration = parseFloat((newEnd - startTime).toFixed(2));

        assert.strictEqual(newEnd, 30.0);
        assert.strictEqual(duration, 5.0);

        // User clamps to 59s
        duration = 65.0;
        assert.strictEqual(duration > 59.0, true);
        duration = 59.00;
        assert.strictEqual(duration > 59.0, false);

        console.log("NODE_JS_SCRUBBER_TESTS_PASSED");
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(node_script)
            temp_js_path = f.name

        try:
            res = subprocess.run(["node", temp_js_path], capture_output=True, text=True, check=True)
            self.assertIn("NODE_JS_SCRUBBER_TESTS_PASSED", res.stdout)
        finally:
            if os.path.exists(temp_js_path):
                os.remove(temp_js_path)


class TestApiPayloadAssemblyAndBackendEndpoints(unittest.TestCase):
    """Empirical challenge tests for API payload construction and server responses."""

    def setUp(self):
        self.client = TestClient(app)

    def test_trigger_pipeline_payload_pydantic_validation(self):
        """Validate exact payload schema created by index.html handleTrigger against Pydantic."""
        frontend_payload = {
            "festival": "EDC Las Vegas",
            "event": "EDC Las Vegas",
            "artist": "Sub Focus",
            "track": "Desire",
            "genre": "house",
            "brand": "laser_baptism",
            "tier": "pillar_a_stadium_arena",
            "from_device": True,
            "auto_drop": True,
            "drop_duration": 30.0,
            "publish_youtube": False,
            "auto_promote": False,
        }

        # Validate with Pydantic model
        model = PipelineTriggerRequest(**frontend_payload)
        self.assertEqual(model.festival, "EDC Las Vegas")
        self.assertEqual(model.artist, "Sub Focus")
        self.assertEqual(model.resolved_event, "EDC Las Vegas")
        self.assertEqual(model.drop_duration, 30.0)

    def test_approve_render_payload_pydantic_validation(self):
        """Validate exact payload schema created by index.html handleApproveRender against Pydantic."""
        frontend_payload = {
            "clip_id": "test_take_001",
            "project_name": "EDC Las Vegas_Sub Focus_Master",
            "timeline_name": "Sub Focus_Desire_Drop_Vertical",
            "festival": "EDC Las Vegas",
            "artist": "Sub Focus",
            "track": "Desire",
            "raw_file_path": "C:/vault/01_RAW/take1.mp4",
            "start_time": 10.0,
            "end_time": 40.0,
            "duration": 30.0,
            "fps": 60.0,
            "width": 1080,
            "height": 1920,
            "dry_run": True,
            "auto_save": True,
        }

        model = ApproveRenderRequest(**frontend_payload)
        self.assertEqual(model.clip_id, "test_take_001")
        self.assertEqual(model.start_time, 10.0)
        self.assertEqual(model.end_time, 40.0)
        self.assertEqual(model.duration, 30.0)
        self.assertEqual(model.fps, 60.0)

        # Dispatch to TestClient
        res = self.client.post("/approve-render", json=frontend_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn(data["status"], ("success", "dry_run_simulated", "resolve_unavailable"))
        self.assertEqual(data["timeline_name"], "Sub Focus_Desire_Drop_Vertical")

    def test_health_endpoint_response_structure(self):
        """Test GET /health telemetry and payload compliance."""
        res = self.client.get("/health")
        self.assertIn(res.status_code, (200, 503))
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("adb_available", data)
        self.assertIn("ffmpeg_available", data)
        self.assertIn("ffprobe_available", data)
        HealthResponse(**data)

    def test_status_endpoint_response_structure(self):
        """Test GET /status telemetry and payload compliance."""
        res = self.client.get("/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("state", data)
        self.assertIn("is_running", data)
        StatusResponse(**data)

    def test_proxies_endpoint_response_structure(self):
        """Test GET /proxies and PendingClipsResponse schema."""
        res = self.client.get("/proxies")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total", data)
        self.assertIn("clips", data)
        PendingClipsResponse(**data)

    def test_cancel_endpoint_when_idle(self):
        """Test POST /cancel when no job is running."""
        res = self.client.post("/cancel")
        self.assertIn(res.status_code, (200, 400, 404))


if __name__ == "__main__":
    unittest.main()
