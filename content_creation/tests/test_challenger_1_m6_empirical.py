"""
test_challenger_1_m6_empirical.py - Empirical Adversarial Test Suite for Challenger 1 (Milestone 6)

Rigorous empirical challenge and stress-testing for:
1. DOM & Frontend Inspection: static/index.html input fields, IDs, vibration arrays, CSS styling, and edge-case sanitization.
2. FastAPI Remote Trigger Payload Schema & Mutex Concurrency: POST /trigger-pipeline fuzzing, nulls, injections, boundary checks, and HTTP 409 mutex lock enforcement.
3. FFmpeg Proxy & WAV Generator Verification: 720p aspect constraints, 2500k bitrate, fast preset, and 22.05kHz 16-bit PCM WAV extraction.
"""

import asyncio
from datetime import datetime, timezone
import html.parser
import json
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure content_creation root is on sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from fastapi.testclient import TestClient
import config
from config import (
    PROXY_AUDIO_CODEC,
    PROXY_AUDIO_SAMPLE_RATE,
    PROXY_PRESET,
    PROXY_VIDEO_BITRATE_KBPS,
    PROXY_VIDEO_CODEC,
    PROXY_VIDEO_HEIGHT,
)
from ffmpeg_processor import FFmpegMasterProcessor, ProxyGenerationResult
from remote_trigger import (
    ConflictResponse,
    create_app,
    JobRecord,
    JobState,
    PipelineJobManager,
    PipelineTriggerRequest,
    TriggerResponse,
)


class HTMLTagCollector(html.parser.HTMLParser):
    """Parses HTML into a searchable DOM representation for testing."""
    def __init__(self):
        super().__init__()
        self.tags = []
        self.elements_by_id = {}
        self.scripts = []
        self.styles = []
        self._current_tag = None
        self._current_data = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        el_id = attr_dict.get('id')
        elem = {
            'tag': tag,
            'attrs': attr_dict,
            'id': el_id,
            'class': attr_dict.get('class', ''),
            'type': attr_dict.get('type', ''),
            'name': attr_dict.get('name', ''),
        }
        self.tags.append(elem)
        if el_id:
            self.elements_by_id[el_id] = elem
        self._current_tag = tag
        self._current_data = []

    def handle_data(self, data):
        self._current_data.append(data)
        if self._current_tag == 'script':
            self.scripts.append(data)
        elif self._current_tag == 'style':
            self.styles.append(data)

    def handle_endtag(self, tag):
        self._current_tag = None


class TestAdversarialDOMAndFrontend(unittest.TestCase):
    """Task 1: Adversarial DOM & Frontend Inspection."""

    @classmethod
    def setUpClass(cls):
        cls.html_path = WORKSPACE_ROOT / "static" / "index.html"
        if not cls.html_path.exists():
            cls.html_path = WORKSPACE_ROOT / "index.html"
        assert cls.html_path.exists(), f"index.html not found at {cls.html_path}"
        cls.html_content = cls.html_path.read_text(encoding="utf-8")
        cls.parser = HTMLTagCollector()
        cls.parser.feed(cls.html_content)

    def test_dom_input_elements_presence_and_attributes(self):
        """Assert #festival-input and #artist-input exist with correct attributes."""
        # 1. Check festival input
        self.assertIn("festival-input", self.parser.elements_by_id)
        fest_el = self.parser.elements_by_id["festival-input"]
        self.assertEqual(fest_el["tag"], "input")
        self.assertEqual(fest_el["attrs"].get("type"), "text")
        self.assertEqual(fest_el["attrs"].get("name"), "festival")
        self.assertIn("form-input", fest_el["attrs"].get("class", ""))
        self.assertEqual(fest_el["attrs"].get("maxlength"), "100")

        # 2. Check artist input
        self.assertIn("artist-input", self.parser.elements_by_id)
        art_el = self.parser.elements_by_id["artist-input"]
        self.assertEqual(art_el["tag"], "input")
        self.assertEqual(art_el["attrs"].get("type"), "text")
        self.assertEqual(art_el["attrs"].get("name"), "artist")
        self.assertIn("form-input", art_el["attrs"].get("class", ""))
        self.assertEqual(art_el["attrs"].get("maxlength"), "100")

        # 3. Check trigger button
        self.assertIn("trigger-btn", self.parser.elements_by_id)
        trig_el = self.parser.elements_by_id["trigger-btn"]
        self.assertEqual(trig_el["tag"], "button")
        self.assertIn("massive-trigger-btn", trig_el["attrs"].get("class", ""))

        # 4. Check toast card
        self.assertIn("toast-card", self.parser.elements_by_id)
        toast_el = self.parser.elements_by_id["toast-card"]
        self.assertEqual(toast_el["tag"], "div")
        self.assertIn("toast-card", toast_el["attrs"].get("class", ""))

    def test_vibration_arrays_in_client_script(self):
        """Assert vibration haptics [100, 100, 100] and [500, 200, 500] are present."""
        script_blob = "\n".join(self.parser.scripts)
        # Success vibration: [100, 100, 100]
        self.assertRegex(script_blob, r"vibrate\(\s*\[\s*100\s*,\s*100\s*,\s*100\s*\]\s*\)")
        # Warning / error vibration: [500, 200, 500]
        self.assertRegex(script_blob, r"vibrate\(\s*\[\s*500\s*,\s*200\s*,\s*500\s*\]\s*\)")

    def test_css_styling_oled_glassmorphism_and_safe_typography(self):
        """Assert CSS styling rules for OLED dark theme, glassmorphism, and anti-zoom typography."""
        style_blob = "\n".join(self.parser.styles)
        # OLED tokens
        self.assertIn("--bg-oled-black: #000000", style_blob)
        self.assertIn("--neon-cyan: #00ffcc", style_blob)
        self.assertIn("--neon-pink: #ff007f", style_blob)
        # Glassmorphism
        self.assertIn("backdrop-filter: blur", style_blob)
        self.assertIn("-webkit-backdrop-filter: blur", style_blob)
        # Sizing and typography: 16px to prevent auto-zoom on mobile browsers
        self.assertIn("font-size: 16px;", style_blob)
        # View transitions standards
        self.assertIn("::view-transition-old", style_blob)
        self.assertIn("::view-transition-new", style_blob)
        self.assertIn("@media (prefers-reduced-motion: reduce)", style_blob)
        # Trigger button size
        self.assertIn("--trigger-btn-size: clamp(200px, 55vw, 280px)", style_blob)

    def test_frontend_input_sanitization_and_fallback_simulation(self):
        """Adversarial testing of JS input resolution logic."""
        def resolve_js_inputs(festival_val, artist_val):
            fest_trimmed = festival_val.strip() if festival_val else ""
            art_trimmed = artist_val.strip() if artist_val else ""
            final_fest = fest_trimmed or "Concert"
            final_art = art_trimmed or "Artist"
            return {
                "festival": final_fest,
                "event": final_fest,
                "artist": final_art,
                "brand": "laser_baptism",
                "tier": "pillar_a_stadium_arena",
                "from_device": True,
                "auto_drop": True,
                "drop_duration": 30.0,
            }

        # Case A: Empty strings fallback to defaults
        payload_empty = resolve_js_inputs("", "")
        self.assertEqual(payload_empty["festival"], "Concert")
        self.assertEqual(payload_empty["artist"], "Artist")

        # Case B: Whitespace-only strings fallback to defaults
        payload_ws = resolve_js_inputs("   \t  ", "  \n  ")
        self.assertEqual(payload_ws["festival"], "Concert")
        self.assertEqual(payload_ws["artist"], "Artist")

        # Case C: Unicode & Emojis
        payload_emoji = resolve_js_inputs("  EDC 🎪 Las Vegas  ", "  Sub Focus 🎧  ")
        self.assertEqual(payload_emoji["festival"], "EDC 🎪 Las Vegas")
        self.assertEqual(payload_emoji["artist"], "Sub Focus 🎧")

        # Case D: Malicious script tags & special characters
        payload_xss = resolve_js_inputs("<script>alert('xss')</script>", "DJ O'Connor & Sons")
        self.assertEqual(payload_xss["festival"], "<script>alert('xss')</script>")
        self.assertEqual(payload_xss["artist"], "DJ O'Connor & Sons")


class TestAdversarialFastAPIPayloadAndMutex(unittest.TestCase):
    """Task 2: Adversarial FastAPI Payload Testing & Mutex Concurrency Verification."""

    def setUp(self):
        self.app = create_app(workspace_root=WORKSPACE_ROOT)
        self.client = TestClient(self.app)

    def test_trigger_pipeline_empty_and_null_payloads(self):
        """Fuzz POST /trigger-pipeline with empty body, None, and partial nulls."""
        # 1. Empty body {}
        resp = self.client.post("/trigger-pipeline", json={})
        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertEqual(data["status"], "accepted")
        self.assertTrue(data["job_id"].startswith("job_"))
        self.assertIn("--event", data["command"])
        self.assertIn("Concert", data["command"])
        self.assertIn("--artist", data["command"])
        self.assertIn("Artist", data["command"])

        # 2. Null values
        resp_null = self.client.post("/trigger-pipeline", json={"festival": None, "artist": None, "event": None})
        self.assertEqual(resp_null.status_code, 202)
        data_null = resp_null.json()
        self.assertIn("Concert", data_null["command"])
        self.assertIn("Artist", data_null["command"])

    def test_trigger_pipeline_adversarial_injection_payloads(self):
        """Fuzz with shell injection, SQLi, and unicode strings."""
        malicious_inputs = [
            {"festival": "; rm -rf / ;", "artist": "$(whoami)", "track": "ID && calc"},
            {"festival": "Ultra 2026'; DROP TABLE clips;--", "artist": "Marten Hørger"},
            {"festival": "A" * 500, "artist": "B" * 500},  # Long strings
            {"festival": "🔥 Lost Lands 🦖", "artist": "Excision ⚡"},
        ]

        for payload in malicious_inputs:
            resp = self.client.post("/trigger-pipeline", json=payload)
            self.assertEqual(resp.status_code, 202)
            data = resp.json()
            cmd = data["command"]
            # Assert command is safe list (no shell injection concatenation)
            self.assertIsInstance(cmd, list)
            self.assertIn(payload["festival"].strip() if payload.get("festival") else "Concert", cmd)

    def test_trigger_pipeline_pydantic_boundary_validations(self):
        """Assert boundary validations on drop_duration, start_time, duration."""
        # drop_duration ge=5.0, le=59.0
        r1 = self.client.post("/trigger-pipeline", json={"drop_duration": 4.9})
        self.assertEqual(r1.status_code, 422)

        r2 = self.client.post("/trigger-pipeline", json={"drop_duration": 60.0})
        self.assertEqual(r2.status_code, 422)

        r3 = self.client.post("/trigger-pipeline", json={"drop_duration": 30.0})
        self.assertEqual(r3.status_code, 202)

        # start_time ge=0.0
        r4 = self.client.post("/trigger-pipeline", json={"start_time": -1.0})
        self.assertEqual(r4.status_code, 422)

        # duration ge=5.0, le=59.0
        r5 = self.client.post("/trigger-pipeline", json={"duration": 4.0})
        self.assertEqual(r5.status_code, 422)

    def test_mutex_lock_concurrency_and_409_conflict(self):
        """Assert that concurrent execution is blocked with HTTP 409 Conflict."""
        manager = self.app.state.job_manager
        # Simulate active running job
        now_utc = datetime.now(timezone.utc)
        active_job = JobRecord(
            job_id="job_test_active_123",
            command=["python", "orchestrator.py"],
            params={"festival": "EDC"},
        )
        active_job.state = JobState.RUNNING
        active_job.started_at = now_utc
        manager._active_job = active_job

        self.assertTrue(manager.is_running)

        # Attempt to trigger pipeline while running
        resp = self.client.post("/trigger-pipeline", json={"festival": "Ultra"})
        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertEqual(data["status"], "conflict")
        self.assertEqual(data["current_job_id"], "job_test_active_123")
        self.assertIn("already in progress", data["error"])

        # Check status endpoint reflects running state
        status_resp = self.client.get("/status")
        self.assertEqual(status_resp.status_code, 200)
        sdata = status_resp.json()
        self.assertTrue(sdata["is_running"])
        self.assertEqual(sdata["state"], "running")
        self.assertEqual(sdata["current_job_id"], "job_test_active_123")

        # Cancel active job
        cancel_resp = self.client.post("/cancel")
        self.assertEqual(cancel_resp.status_code, 200)
        cdata = cancel_resp.json()
        self.assertEqual(cdata["status"], "cancelled")
        self.assertEqual(cdata["job_id"], "job_test_active_123")

        # Verify lock is now released
        self.assertFalse(manager.is_running)
        next_resp = self.client.post("/trigger-pipeline", json={"festival": "Tomorrowland"})
        self.assertEqual(next_resp.status_code, 202)


class TestAdversarialProxyAndWAVCommands(unittest.TestCase):
    """Task 3: Adversarial Proxy & WAV Command Verification."""

    def setUp(self):
        self.processor = FFmpegMasterProcessor()

    def test_proxy_video_generation_command_specifications(self):
        """Assert generate_proxy_video builds canonical FFmpeg command."""
        in_path = "01_RAW/UltraMiami/MartinGarrix/take_01.mp4"
        out_path = "01_RAW/UltraMiami/MartinGarrix/take_01_proxy.mp4"

        cmd = self.processor.generate_proxy_video(
            input_path=in_path,
            output_path=out_path,
            target_resolution=PROXY_VIDEO_HEIGHT,
            bitrate_kbps=PROXY_VIDEO_BITRATE_KBPS,
            preset=PROXY_PRESET,
            dry_run=True,
        )

        cmd_str = " ".join(cmd)
        # 1. Aspect-aware scaling to 720p
        expected_scale = "scale='if(gt(ih,iw),720,-2)':'if(gt(ih,iw),-2,720)'"
        self.assertIn(expected_scale, cmd_str)

        # 2. Codec and Preset
        self.assertIn("-c:v libx264", cmd_str)
        self.assertIn("-preset fast", cmd_str)

        # 3. Bitrate 2500k
        self.assertIn("-b:v 2500k", cmd_str)
        self.assertIn("-maxrate 3500k", cmd_str)
        self.assertIn("-bufsize 5000k", cmd_str)

        # 4. Pixel Format & Faststart
        self.assertIn("-pix_fmt yuv420p", cmd_str)
        self.assertIn("-movflags +faststart", cmd_str)

    def test_wav_audio_extraction_command_specifications(self):
        """Assert extract_wav_audio builds canonical FFmpeg command."""
        in_path = "01_RAW/UltraMiami/MartinGarrix/take_01.mp4"
        out_path = "01_RAW/UltraMiami/MartinGarrix/take_01_audio.wav"

        cmd = self.processor.extract_wav_audio(
            input_path=in_path,
            output_path=out_path,
            sample_rate=PROXY_AUDIO_SAMPLE_RATE,
            audio_codec=PROXY_AUDIO_CODEC,
            dry_run=True,
        )

        cmd_str = " ".join(cmd)
        # 1. No video
        self.assertIn("-vn", cmd_str)

        # 2. PCM 16-bit
        self.assertIn("-c:a pcm_s16le", cmd_str)

        # 3. 22.05 kHz sample rate
        self.assertIn("-ar 22050", cmd_str)

        # 4. Mono channel
        self.assertIn("-ac 1", cmd_str)

        # 5. Format WAV
        self.assertIn("-f wav", cmd_str)

    def test_generate_proxy_and_wav_orchestration(self):
        """Assert generate_proxy_and_wav returns complete ProxyGenerationResult."""
        in_path = "01_RAW/take.mp4"
        proxy_path = "01_RAW/take_proxy.mp4"
        wav_path = "01_RAW/take_audio.wav"

        result = self.processor.generate_proxy_and_wav(
            input_path=in_path,
            output_proxy_path=proxy_path,
            output_wav_path=wav_path,
            dry_run=True,
        )

        self.assertIsInstance(result, ProxyGenerationResult)
        self.assertTrue(result.success)
        self.assertIn("-vf", " ".join(result.proxy_ffmpeg_cmd))
        self.assertIn("-vn", " ".join(result.wav_ffmpeg_cmd))


if __name__ == "__main__":
    unittest.main(verbosity=2)
