"""
test_adversarial_pwa_server_stress.py - Empirical Adversarial Stress Test Suite
for FastAPI PWA Remote Trigger Server (content_creation/remote_trigger.py)

Adversarial Stress Test Vectors:
1. Rapid concurrent GET requests to `/` (50-200 concurrent requests):
   - 100% 200 OK response rate
   - Content-Type: text/html
   - No descriptor leaks / resource degradation over burst cycles
2. Rapid concurrent POST requests to `/trigger-pipeline` (50-100 concurrent requests):
   - Exactly 1 request acquires mutex lock (HTTP 202 Accepted)
   - All concurrent requests receive HTTP 409 Conflict with accurate telemetry
   - Mutex lock consistency and winning job_id validation
3. Missing static file path resilience:
   - Graceful HTTP 404 when index.html / manifest.json is missing
   - Root index.html fallback when static/index.html is absent
   - Server stability without unhandled 500 exceptions
4. Static assets and Manifest MIME type:
   - GET /manifest.json and GET /static/manifest.json serve valid JSON / manifest MIME types
   - Schema validation for required PWA manifest fields
   - Directory traversal rejection on /static/ mounts
5. Cancellation during active job:
   - POST /cancel transitions state to CANCELLED and terminates subprocess
   - Immediate lock re-acquisition for subsequent POST /trigger-pipeline
   - Idle and duplicate cancellation error handling (HTTP 400)
6. High-frequency trigger/cancel stress cycles
7. Telemetry, ring-buffered logs, and health status under concurrent pressure
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from starlette.testclient import TestClient

# Ensure content_creation root is on sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from remote_trigger import (
    ConflictResponse,
    HealthResponse,
    JobRecord,
    JobState,
    JobTelemetry,
    LogEntry,
    LogsResponse,
    PipelineJobManager,
    PipelineTriggerRequest,
    StatusResponse,
    TriggerResponse,
    create_app,
)


class TestAdversarialPWARapidConcurrentGet(unittest.IsolatedAsyncioTestCase):
    """Test 1: Rapid concurrent GET requests to `/` (50+ concurrent requests)."""

    def setUp(self):
        self.app = create_app(workspace_root=WORKSPACE_ROOT)

    async def test_01_concurrent_get_root_50_burst(self):
        """Verify 50 concurrent GET requests to / all return 200 OK with text/html."""
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            tasks = [client.get("/") for _ in range(50)]
            responses = await asyncio.gather(*tasks)

        self.assertEqual(len(responses), 50)
        for resp in responses:
            self.assertEqual(resp.status_code, 200, f"Expected 200 OK, got {resp.status_code}")
            content_type = resp.headers.get("content-type", "")
            self.assertTrue(
                content_type.startswith("text/html"),
                f"Expected Content-Type starting with text/html, got {content_type}",
            )
            body = resp.text
            self.assertIn("EDM Pipeline Master Mind Trigger", body)
            self.assertIn("TRIGGER EDM PIPELINE", body)
            self.assertIn("manifest.json", body)

    async def test_02_concurrent_get_root_100_burst_multi_cycle(self):
        """Verify 100 concurrent GET requests over 3 consecutive cycles (300 requests total) with zero errors."""
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            for cycle in range(3):
                tasks = [client.get("/") for _ in range(100)]
                responses = await asyncio.gather(*tasks)

                self.assertEqual(len(responses), 100, f"Cycle {cycle} returned unexpected count")
                status_codes = [r.status_code for r in responses]
                self.assertTrue(
                    all(c == 200 for c in status_codes),
                    f"Cycle {cycle} had non-200 responses: {set(status_codes)}",
                )
                # Verify body size is non-trivial and consistent
                body_lengths = [len(r.content) for r in responses]
                self.assertEqual(len(set(body_lengths)), 1, "Body lengths varied across responses")
                self.assertGreater(body_lengths[0], 500, "HTML body too short")

    async def test_03_concurrent_get_mixed_endpoints(self):
        """Verify concurrent GET requests mixing /, /health, /status, /manifest.json, /static/manifest.json."""
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            endpoints = ["/", "/health", "/status", "/manifest.json", "/static/manifest.json"] * 20
            # 100 concurrent requests across different endpoints
            tasks = [client.get(ep) for ep in endpoints]
            responses = await asyncio.gather(*tasks)

        self.assertEqual(len(responses), 100)
        for i, resp in enumerate(responses):
            ep = endpoints[i]
            if ep == "/health":
                self.assertIn(resp.status_code, (200, 503), f"/health returned unexpected {resp.status_code}")
            else:
                self.assertEqual(resp.status_code, 200, f"Endpoint {ep} failed with {resp.status_code}")


class TestAdversarialConcurrentTriggerLocking(unittest.IsolatedAsyncioTestCase):
    """Test 2: Rapid concurrent POST requests to `/trigger-pipeline`."""

    def setUp(self):
        self.app = create_app(workspace_root=WORKSPACE_ROOT)
        self.manager: PipelineJobManager = self.app.state.job_manager

    async def test_01_concurrent_post_50_requests_exact_one_202_and_49_409(self):
        """Simulate 50 concurrent requests hitting /trigger-pipeline simultaneously.

        Verify exactly 1 request gets HTTP 202 and exactly 49 get HTTP 409.
        """
        # Patch _run_subprocess to sleep briefly so the job stays active during the burst
        async def slow_mock_subprocess(job: JobRecord):
            try:
                job.state = JobState.RUNNING
                await asyncio.sleep(0.4)
                job.state = JobState.COMPLETED
                job.exit_code = 0
            except asyncio.CancelledError:
                job.state = JobState.CANCELLED
            finally:
                if self.manager._active_job == job:
                    self.manager._active_job = None
                self.manager._job_history.insert(0, job)

        with patch.object(self.manager, "_run_subprocess", side_effect=slow_mock_subprocess):
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                payload = {
                    "event": "AdversarialConcert",
                    "artist": "StressDJ",
                    "track": "ID_Drop",
                    "dry_run": True,
                }
                tasks = [client.post("/trigger-pipeline", json=payload) for _ in range(50)]
                responses = await asyncio.gather(*tasks)

        status_counts = {}
        for r in responses:
            status_counts[r.status_code] = status_counts.get(r.status_code, 0) + 1

        self.assertEqual(status_counts.get(202, 0), 1, f"Expected exactly 1 202 Accepted, got: {status_counts}")
        self.assertEqual(status_counts.get(409, 0), 49, f"Expected exactly 49 409 Conflict, got: {status_counts}")

        # Find the single 202 response
        accepted_resp = next(r for r in responses if r.status_code == 202)
        accepted_data = accepted_resp.json()
        self.assertEqual(accepted_data["status"], "accepted")
        winning_job_id = accepted_data["job_id"]
        self.assertTrue(winning_job_id.startswith("job_"))

        # Verify all 49 conflict responses reference the winning job ID and have accurate telemetry
        conflict_resps = [r for r in responses if r.status_code == 409]
        for c_resp in conflict_resps:
            c_data = c_resp.json()
            self.assertEqual(c_data["status"], "conflict")
            self.assertEqual(c_data["error"], "Pipeline execution is already in progress")
            self.assertEqual(c_data["current_job_id"], winning_job_id)
            self.assertGreaterEqual(c_data.get("elapsed_seconds", 0.0), 0.0)

    async def test_02_concurrent_post_100_requests_high_pressure(self):
        """Stress test 100 concurrent trigger requests under high contention."""
        async def slow_mock_subprocess(job: JobRecord):
            try:
                job.state = JobState.RUNNING
                await asyncio.sleep(0.5)
                job.state = JobState.COMPLETED
                job.exit_code = 0
            except asyncio.CancelledError:
                job.state = JobState.CANCELLED
            finally:
                if self.manager._active_job == job:
                    self.manager._active_job = None
                self.manager._job_history.insert(0, job)

        with patch.object(self.manager, "_run_subprocess", side_effect=slow_mock_subprocess):
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                tasks = [client.post("/trigger-pipeline", json={"dry_run": True}) for _ in range(100)]
                responses = await asyncio.gather(*tasks)

        accepted = [r for r in responses if r.status_code == 202]
        conflicts = [r for r in responses if r.status_code == 409]
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(conflicts), 99)

    async def test_03_invalid_json_payload_concurrency_lock_safety(self):
        """Verify malformed/invalid payloads return 422 Unprocessable Content without corrupting the mutex."""
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Send invalid drop_duration (out of range > 59)
            invalid_payload = {"drop_duration": 120.0}
            resp_invalid = await client.post("/trigger-pipeline", json=invalid_payload)
            self.assertEqual(resp_invalid.status_code, 422)

            # Mutex should still be completely free and ready for valid requests
            valid_payload = {"dry_run": True}
            resp_valid = await client.post("/trigger-pipeline", json=valid_payload)
            self.assertEqual(resp_valid.status_code, 202)


class TestAdversarialMissingStaticPathResilience(unittest.TestCase):
    """Test 3: Missing static file path resilience."""

    def test_01_complete_absence_of_index_html_returns_404_cleanly(self):
        """When static/index.html and root index.html are both missing, server returns 404 without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_root = Path(tmpdir)
            app = create_app(workspace_root=empty_root)
            client = TestClient(app)

            resp = client.get("/")
            self.assertEqual(resp.status_code, 404)
            self.assertIn("index.html not found", resp.json().get("detail", ""))

            # Subsequent requests to health and status endpoints function perfectly
            health_resp = client.get("/health")
            self.assertIn(health_resp.status_code, (200, 503))
            status_resp = client.get("/status")
            self.assertEqual(status_resp.status_code, 200)

    def test_02_fallback_to_root_index_html_when_static_index_is_missing(self):
        """When static/index.html is absent but root index.html exists, server falls back to root index.html."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            root_index = temp_root / "index.html"
            root_index.write_text("<!DOCTYPE html><html><body>Fallback Root PWA</body></html>", encoding="utf-8")

            app = create_app(workspace_root=temp_root)
            client = TestClient(app)

            resp = client.get("/")
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.headers.get("content-type", "").startswith("text/html"))
            self.assertIn("Fallback Root PWA", resp.text)

    def test_03_missing_manifest_returns_404_cleanly(self):
        """When manifest.json is absent, server returns 404 gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            app = create_app(workspace_root=temp_root)
            client = TestClient(app)

            resp = client.get("/manifest.json")
            self.assertEqual(resp.status_code, 404)
            self.assertIn("manifest.json not found", resp.json().get("detail", ""))

    def test_04_missing_static_dir_does_not_crash_app_startup(self):
        """When static/ directory does not exist, app initializes safely and /static/* returns 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            app = create_app(workspace_root=temp_root)
            client = TestClient(app)

            resp = client.get("/static/manifest.json")
            self.assertEqual(resp.status_code, 404)


class TestAdversarialStaticAssetsAndManifestMIME(unittest.TestCase):
    """Test 4: Static assets serving /static/manifest.json and MIME types."""

    def setUp(self):
        self.app = create_app(workspace_root=WORKSPACE_ROOT)
        self.client = TestClient(self.app)

    def test_01_manifest_json_mime_and_schema(self):
        """Verify GET /manifest.json returns 200 with valid MIME type and schema."""
        resp = self.client.get("/manifest.json")
        self.assertEqual(resp.status_code, 200)
        content_type = resp.headers.get("content-type", "")
        self.assertTrue(
            "application/manifest+json" in content_type or "application/json" in content_type,
            f"Expected manifest json content-type, got {content_type}",
        )

        data = resp.json()
        required_fields = ["name", "short_name", "start_url", "display", "theme_color", "background_color", "icons"]
        for field in required_fields:
            self.assertIn(field, data, f"Missing required manifest field: {field}")

        self.assertEqual(data["name"], "EDM Pipeline Master Mind Trigger")
        self.assertEqual(data["short_name"], "EDM Trigger")
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["start_url"], "/")
        self.assertEqual(data["theme_color"], "#000000")
        self.assertEqual(data["background_color"], "#000000")
        self.assertIsInstance(data["icons"], list)
        self.assertGreaterEqual(len(data["icons"]), 2)

    def test_02_static_manifest_json_route(self):
        """Verify GET /static/manifest.json returns 200 with JSON content."""
        resp = self.client.get("/static/manifest.json")
        self.assertEqual(resp.status_code, 200)
        content_type = resp.headers.get("content-type", "")
        self.assertTrue("json" in content_type or "manifest" in content_type, f"Content-Type: {content_type}")
        data = resp.json()
        self.assertEqual(data["short_name"], "EDM Trigger")

    def test_03_static_directory_traversal_protection(self):
        """Verify directory traversal attempts via /static/ are rejected."""
        # Attempt to traverse up out of static directory
        resp1 = self.client.get("/static/../remote_trigger.py")
        self.assertIn(resp1.status_code, (404, 400, 403))

        resp2 = self.client.get("/static/../../config.py")
        self.assertIn(resp2.status_code, (404, 400, 403))

        resp3 = self.client.get("/static/%2e%2e%2fremote_trigger.py")
        self.assertIn(resp3.status_code, (404, 400, 403))

    def test_04_non_existent_static_file_returns_404(self):
        """Verify non-existent static asset returns 404 without leaking stack trace."""
        resp = self.client.get("/static/does_not_exist_file_99999.png")
        self.assertEqual(resp.status_code, 404)


class TestAdversarialCancellationAndLockReacquisition(unittest.IsolatedAsyncioTestCase):
    """Test 5: Verify cancellation during active job (POST /cancel) and lock re-acquisition."""

    def setUp(self):
        self.app = create_app(workspace_root=WORKSPACE_ROOT)
        self.manager: PipelineJobManager = self.app.state.job_manager

    async def test_01_cancel_active_job_and_immediate_lock_reacquisition(self):
        """Start a job, cancel it midway, verify state transitions to CANCELLED, and immediately trigger a new job."""
        cancel_event = asyncio.Event()

        async def cancellable_mock_subprocess(job: JobRecord):
            try:
                job.state = JobState.RUNNING
                # Wait until cancelled or timeout
                await asyncio.sleep(10.0)
                job.state = JobState.COMPLETED
                job.exit_code = 0
            except asyncio.CancelledError:
                job.state = JobState.CANCELLED
                job.completed_at = datetime.now(timezone.utc)
                job.error_summary = "Job execution cancelled by user request"
                cancel_event.set()
                raise
            finally:
                if self.manager._active_job == job:
                    self.manager._active_job = None
                self.manager._job_history.insert(0, job)

        with patch.object(self.manager, "_run_subprocess", side_effect=cancellable_mock_subprocess):
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                # 1. Trigger initial job
                trig_resp = await client.post("/trigger-pipeline", json={"dry_run": True})
                self.assertEqual(trig_resp.status_code, 202)
                job_1_id = trig_resp.json()["job_id"]

                # 2. Verify status reports running
                status_resp1 = await client.get("/status")
                self.assertEqual(status_resp1.status_code, 200)
                self.assertTrue(status_resp1.json()["is_running"])
                self.assertEqual(status_resp1.json()["current_job_id"], job_1_id)

                # 3. Cancel the active job
                cancel_resp = await client.post("/cancel")
                self.assertEqual(cancel_resp.status_code, 200)
                cancel_data = cancel_resp.json()
                self.assertEqual(cancel_data["status"], "cancelled")
                self.assertEqual(cancel_data["job_id"], job_1_id)
                self.assertTrue(cancel_data["terminated"])

                # 4. Verify status reports idle and job_1 is cancelled
                status_resp2 = await client.get("/status")
                self.assertEqual(status_resp2.status_code, 200)
                status_data2 = status_resp2.json()
                self.assertFalse(status_data2["is_running"])
                self.assertIsNone(status_data2["current_job_id"])

                # Verify job_1 telemetry recorded CANCELLED
                job1_status_resp = await client.get(f"/status/{job_1_id}")
                self.assertEqual(job1_status_resp.status_code, 200)
                self.assertEqual(job1_status_resp.json()["state"], "cancelled")

                # 5. Immediately trigger a second job — MUST acquire lock cleanly (no lingering mutex deadlock)
                trig2_resp = await client.post("/trigger-pipeline", json={"event": "Job2", "dry_run": True})
                self.assertEqual(trig2_resp.status_code, 202)
                job_2_id = trig2_resp.json()["job_id"]
                self.assertNotEqual(job_1_id, job_2_id)

                # Cancel job 2 to clean up
                await client.post("/cancel")

    async def test_02_cancel_when_idle_returns_400_bad_request(self):
        """POST /cancel when no job is running must return HTTP 400 Bad Request."""
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/cancel")
            self.assertEqual(resp.status_code, 400)
            self.assertIn("No active pipeline job currently running", resp.json().get("detail", ""))

    async def test_03_duplicate_cancel_call_returns_400(self):
        """Second consecutive POST /cancel call returns HTTP 400 without exception."""
        async def dummy_slow_subprocess(job: JobRecord):
            try:
                job.state = JobState.RUNNING
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                job.state = JobState.CANCELLED
            finally:
                if self.manager._active_job == job:
                    self.manager._active_job = None
                self.manager._job_history.insert(0, job)

        with patch.object(self.manager, "_run_subprocess", side_effect=dummy_slow_subprocess):
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                await client.post("/trigger-pipeline", json={"dry_run": True})

                # First cancel -> 200
                resp1 = await client.post("/cancel")
                self.assertEqual(resp1.status_code, 200)

                # Second cancel -> 400
                resp2 = await client.post("/cancel")
                self.assertEqual(resp2.status_code, 400)


class TestAdversarialHighFrequencyCyclesAndTelemetry(unittest.IsolatedAsyncioTestCase):
    """Test 6 & 7: High-frequency stress cycles, telemetry tracking, and ring buffer capping."""

    def setUp(self):
        self.app = create_app(workspace_root=WORKSPACE_ROOT)
        self.manager: PipelineJobManager = self.app.state.job_manager

    async def test_01_ten_consecutive_trigger_cancel_burst_cycles(self):
        """Execute 10 consecutive trigger -> cancel cycles to verify state machine robustness."""
        async def mock_subproc(job: JobRecord):
            try:
                job.state = JobState.RUNNING
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                job.state = JobState.CANCELLED
            finally:
                if self.manager._active_job == job:
                    self.manager._active_job = None
                self.manager._job_history.insert(0, job)

        with patch.object(self.manager, "_run_subprocess", side_effect=mock_subproc):
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                for i in range(10):
                    trig_resp = await client.post("/trigger-pipeline", json={"event": f"Burst_{i}", "dry_run": True})
                    self.assertEqual(trig_resp.status_code, 202, f"Cycle {i} trigger failed")
                    job_id = trig_resp.json()["job_id"]

                    cancel_resp = await client.post("/cancel")
                    self.assertEqual(cancel_resp.status_code, 200, f"Cycle {i} cancel failed")
                    self.assertEqual(cancel_resp.json()["job_id"], job_id)

                status_resp = await client.get("/status")
                self.assertEqual(status_resp.status_code, 200)
                status_data = status_resp.json()
                self.assertEqual(status_data["total_jobs_run"], 10)
                self.assertFalse(status_data["is_running"])
                self.assertEqual(len(status_data["recent_jobs"]), 10)

    async def test_02_log_buffer_overflow_capping(self):
        """Verify that injecting > max_logs entries caps the buffer strictly without memory unbounded growth."""
        # Inject 2500 log entries into manager
        for i in range(2500):
            self.manager._add_log(LogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                level="INFO",
                message=f"Log message stress index {i}",
                job_id=f"job_{i}",
            ))

        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/logs?tail=3000")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            # Buffer should be capped at max_logs (2000)
            self.assertEqual(data["total_lines"], 2000)
            self.assertIn("2499", data["logs"][-1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
