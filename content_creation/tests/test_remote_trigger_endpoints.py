"""
test_remote_trigger_endpoints.py - Unit & Integration Test Suite for Pending Clips, Proxy Streaming & Resolve Endpoints
Part of Milestone M1 / Track 2: Content Creation & Media Engineering Pipeline

Tests cover:
1. Pydantic schemas:
   - PendingClipItem, PendingClipsResponse, ApproveRenderRequest, ApproveRenderResponse.
2. GET /api/clips/pending and aliases (/proxies, /api/proxies):
   - Scans 01_RAW, 02_AWAITING_REVIEW, 02_IN_PROGRESS, 01_RAW_INBOX.
   - Extracts festival, artist, raw_path, proxy_path, wav_path, AI drop window.
3. GET /proxies/{clip_id}/video and aliases (/api/proxy/{clip_id}/video):
   - Full content retrieval (HTTP 200) with Accept-Ranges and Content-Length.
   - Byte-range request (HTTP 206 Partial Content): e.g. "Range: bytes=0-1023", "Range: bytes=1000-", "Range: bytes=-500".
   - Content-Range header verification ("bytes 0-1023/10000").
   - Out-of-bounds range request handling (HTTP 416 Range Not Satisfiable).
   - Missing clip ID error handling (HTTP 404 Not Found).
4. POST /approve-render and aliases (/api/resolve/handoff, /api/approve-render):
   - Approved trim points dispatch to DaVinci Resolve engine (with dry-run and mock resolution).
   - Exact mathematical frame verification in response payload.
   - Input payload validation errors (HTTP 422 Unprocessable Entity).
   - Missing raw video error handling (HTTP 404 Not Found).
"""

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from remote_trigger import (
    ApproveRenderRequest,
    ApproveRenderResponse,
    PendingClipItem,
    PendingClipsResponse,
    create_app,
    discover_pending_clips,
    find_proxy_file,
    stream_video_range,
)


class TestRemoteTriggerNewSchemas(unittest.TestCase):
    """Verifies Pydantic v2 schemas and validation behavior for new review/handoff models."""

    def test_pending_clip_item_defaults(self):
        item = PendingClipItem(
            clip_id="take_001",
            canonical_filename="20260822_EDC_Subtronics_V1_4k.mp4",
            raw_path="01_RAW/EDC/Subtronics/20260822_EDC_Subtronics_V1_4k.mp4",
            festival="EDC Las Vegas",
            artist="Subtronics",
        )
        self.assertEqual(item.clip_id, "take_001")
        self.assertEqual(item.festival, "EDC Las Vegas")
        self.assertEqual(item.artist, "Subtronics")
        self.assertEqual(item.duration_seconds, 30.0)
        self.assertEqual(item.status, "awaiting_review")

    def test_pending_clips_response_serialization(self):
        item = PendingClipItem(
            clip_id="take_001",
            canonical_filename="take1.mp4",
            raw_path="01_RAW/take1.mp4",
        )
        resp = PendingClipsResponse(total=1, clips=[item])
        data = resp.model_dump()
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["clips"]), 1)
        self.assertEqual(data["clips"][0]["clip_id"], "take_001")

    def test_approve_render_request_validation(self):
        req = ApproveRenderRequest(
            clip_id="take_001",
            raw_file_path="01_RAW/EDC/Subfocus/raw.mp4",
            start_time=12.45,
            end_time=42.45,
            duration=30.0,
            fps=60.0,
            festival="EDC",
            artist="Sub Focus",
        )
        self.assertEqual(req.resolved_raw_path, "01_RAW/EDC/Subfocus/raw.mp4")
        self.assertEqual(req.start_time, 12.45)
        self.assertEqual(req.end_time, 42.45)
        self.assertEqual(req.fps, 60.0)

    def test_approve_render_request_alias_raw_clip_path(self):
        req = ApproveRenderRequest(
            raw_clip_path="01_RAW/EDC/Subfocus/raw.mp4",
            start_time=10.0,
        )
        self.assertEqual(req.resolved_raw_path, "01_RAW/EDC/Subfocus/raw.mp4")


class TestPendingClipsDiscoveryEndpoint(unittest.TestCase):
    """Verifies directory scanning and GET /api/clips/pending endpoint."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

        # Create standard directory tiers
        self.raw_dir = self.workspace / "01_RAW" / "EDC_Las_Vegas" / "Sub_Focus"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.review_dir = self.workspace / "02_AWAITING_REVIEW" / "EDC_Las_Vegas" / "Sub_Focus"
        self.review_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy raw, proxy, and wav files
        self.raw_file = self.raw_dir / "20260822_Edclasvegas_Subfocus_Desire_V1_4k.mp4"
        self.raw_file.write_bytes(b"\x00" * 2048)

        self.proxy_file = self.review_dir / "20260822_Edclasvegas_Subfocus_Desire_V1_proxy_drop.mp4"
        self.proxy_file.write_bytes(b"\x00" * 1024)

        self.wav_file = self.raw_dir / "20260822_Edclasvegas_Subfocus_Desire_V1_audio.wav"
        self.wav_file.write_bytes(b"\x00" * 512)

        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_discover_pending_clips_helper(self):
        clips = discover_pending_clips(self.workspace)
        self.assertGreaterEqual(len(clips), 1)

        clip = clips[0]
        self.assertEqual(clip.festival, "EDC_Las_Vegas")
        self.assertEqual(clip.artist, "Sub_Focus")
        self.assertIsNotNone(clip.proxy_url)
        self.assertIsNotNone(clip.wav_url)

    def test_get_pending_clips_api_route(self):
        response = self.client.get("/api/clips/pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIn("total", data)
        self.assertIn("clips", data)
        self.assertGreaterEqual(data["total"], 1)

        clip = data["clips"][0]
        self.assertEqual(clip["festival"], "EDC_Las_Vegas")
        self.assertEqual(clip["artist"], "Sub_Focus")
        self.assertIn("proxies", clip["proxy_url"])

    def test_proxies_alias_routes(self):
        resp1 = self.client.get("/proxies")
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        resp2 = self.client.get("/api/proxies")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)


class TestProxyVideoStreamingEndpoint(unittest.TestCase):
    """Verifies HTTP 206 Partial Content video streaming and seeking for HTML5 player."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

        # Create dummy 720p proxy video with known byte patterns
        self.proxy_dir = self.workspace / "02_AWAITING_REVIEW"
        self.proxy_dir.mkdir(parents=True, exist_ok=True)

        self.clip_id = "test_drop_take"
        self.video_file = self.proxy_dir / f"{self.clip_id}_proxy.mp4"
        # 10,000 bytes with byte values modulo 256
        self.file_content = bytes([i % 256 for i in range(10000)])
        self.video_file.write_bytes(self.file_content)

        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_video_full_content_no_range(self):
        response = self.client.get(f"/proxies/{self.clip_id}/video")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Accept-Ranges"), "bytes")
        self.assertEqual(response.headers.get("Content-Length"), "10000")
        self.assertEqual(len(response.content), 10000)
        self.assertEqual(response.content, self.file_content)

    def test_get_video_byte_range_first_1024_bytes(self):
        headers = {"Range": "bytes=0-1023"}
        response = self.client.get(f"/proxies/{self.clip_id}/video", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(response.headers.get("Content-Range"), "bytes 0-1023/10000")
        self.assertEqual(response.headers.get("Content-Length"), "1024")
        self.assertEqual(response.headers.get("Accept-Ranges"), "bytes")
        self.assertEqual(len(response.content), 1024)
        self.assertEqual(response.content, self.file_content[0:1024])

    def test_get_video_byte_range_mid_stream(self):
        headers = {"Range": "bytes=2000-4999"}
        response = self.client.get(f"/proxies/{self.clip_id}/video", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(response.headers.get("Content-Range"), "bytes 2000-4999/10000")
        self.assertEqual(response.headers.get("Content-Length"), "3000")
        self.assertEqual(response.content, self.file_content[2000:5000])

    def test_get_video_byte_range_open_ended(self):
        headers = {"Range": "bytes=8000-"}
        response = self.client.get(f"/proxies/{self.clip_id}/video", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(response.headers.get("Content-Range"), "bytes 8000-9999/10000")
        self.assertEqual(response.headers.get("Content-Length"), "2000")
        self.assertEqual(response.content, self.file_content[8000:10000])

    def test_get_video_byte_range_suffix(self):
        headers = {"Range": "bytes=-500"}
        response = self.client.get(f"/proxies/{self.clip_id}/video", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(response.headers.get("Content-Range"), "bytes 9500-9999/10000")
        self.assertEqual(response.headers.get("Content-Length"), "500")
        self.assertEqual(response.content, self.file_content[9500:10000])

    def test_get_video_invalid_range_416(self):
        headers = {"Range": "bytes=25000-30000"}
        response = self.client.get(f"/proxies/{self.clip_id}/video", headers=headers)
        self.assertEqual(response.status_code, 416)
        self.assertEqual(response.headers.get("Content-Range"), "bytes */10000")

    def test_get_video_missing_clip_404(self):
        response = self.client.get("/proxies/totally_missing_clip_id_9999/video")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_proxy_video_alias_routes(self):
        resp1 = self.client.get(f"/api/proxy/{self.clip_id}/video", headers={"Range": "bytes=0-99"})
        self.assertEqual(resp1.status_code, status.HTTP_206_PARTIAL_CONTENT)

        resp2 = self.client.get(f"/api/proxies/{self.clip_id}/video", headers={"Range": "bytes=0-99"})
        self.assertEqual(resp2.status_code, status.HTTP_206_PARTIAL_CONTENT)


class TestApproveRenderEndpoint(unittest.TestCase):
    """Verifies POST /approve-render endpoint dispatch and telemetry."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

        # Setup raw directory and dummy video
        self.raw_dir = self.workspace / "01_RAW" / "Ultra" / "Hardwell"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.raw_file = self.raw_dir / "20260822_Ultra_Hardwell_Spaceman_V1_4k.mp4"
        self.raw_file.write_bytes(b"\x00" * 4096)

        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_approve_render_dry_run_success(self):
        payload = {
            "clip_id": "20260822_Ultra_Hardwell_Spaceman_V1",
            "raw_file_path": str(self.raw_file),
            "start_time": 15.0,
            "end_time": 45.0,
            "duration": 30.0,
            "fps": 60.0,
            "festival": "Ultra Miami",
            "artist": "Hardwell",
            "track": "Spaceman",
            "dry_run": True,
        }

        response = self.client.post("/approve-render", json=payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["status"], "dry_run_simulated")
        self.assertEqual(data["start_frame"], 900)
        self.assertEqual(data["end_frame"], 2700)
        self.assertEqual(data["duration_frames"], 1800)
        self.assertEqual(data["timeline_resolution"], "1080x1920")
        self.assertEqual(data["fps"], 60.0)
        self.assertIn("job_id", data)

    def test_approve_render_alias_route(self):
        payload = {
            "raw_file_path": str(self.raw_file),
            "start_time": 10.0,
            "duration": 30.0,
            "dry_run": True,
        }
        response = self.client.post("/api/resolve/handoff", json=payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "dry_run_simulated")
        self.assertEqual(data["start_frame"], 600)
        self.assertEqual(data["end_frame"], 2400)

    def test_approve_render_validation_error_negative_start(self):
        payload = {
            "raw_file_path": str(self.raw_file),
            "start_time": -10.0,  # Negative start time
            "duration": 30.0,
        }
        response = self.client.post("/approve-render", json=payload)
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_approve_render_missing_raw_file_404(self):
        payload = {
            "raw_file_path": "01_RAW/totally_non_existent_file.mp4",
            "start_time": 10.0,
            "duration": 30.0,
            "dry_run": False,
        }
        response = self.client.post("/approve-render", json=payload)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
