"""
test_remote_trigger_forensic.py - Independent Forensic Audit Test Suite for Milestone 2
Target: content_creation/remote_trigger.py
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
from unittest.mock import MagicMock, patch

import httpx
from httpx import ASGITransport

# Ensure content_creation is in Python path
workspace_dir = Path(__file__).resolve().parents[2] / "content_creation"
sys.path.insert(0, str(workspace_dir))

from remote_trigger import (
    CancelJobResponse,
    CancelResponse,
    ConflictResponse,
    HealthResponse,
    JobDetail,
    JobRecord,
    JobState,
    JobStatusResponse,
    JobTelemetry,
    LogEntry,
    LogsResponse,
    PipelineConflictResponse,
    PipelineJobManager,
    PipelineTriggerRequest,
    PipelineTriggerResponse,
    StatusResponse,
    TriggerResponse,
    build_orchestrator_command,
    create_app,
)


class TestRemoteTriggerForensicAudit(unittest.IsolatedAsyncioTestCase):
    """Forensic integrity verification and stress test suite."""

    async def asyncSetUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.test_dir.name)
        # Create dummy orchestrator.py in temp workspace
        self.dummy_orchestrator = self.workspace / "orchestrator.py"
        with open(self.dummy_orchestrator, "w", encoding="utf-8") as f:
            f.write(
                "import sys, time\n"
                "print('[ORCHESTRATOR] Initialized pipeline', flush=True)\n"
                "if '--error' in sys.argv:\n"
                "    print('[STDERR] Simulating fatal error', file=sys.stderr, flush=True)\n"
                "    sys.exit(1)\n"
                "time.sleep(0.4)\n"
                "print('[ORCHESTRATOR] Completed pipeline successfully', flush=True)\n"
                "sys.exit(0)\n"
            )

        self.app = create_app(workspace_root=self.workspace)
        self.transport = ASGITransport(app=self.app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")
        self.manager: PipelineJobManager = self.app.state.job_manager

    async def asyncTearDown(self):
        await self.client.aclose()
        self.test_dir.cleanup()

    def test_01_command_builder_dynamic_permutations(self):
        """Verifies that command builder is dynamic and does not return static strings."""
        test_cases = [
            ("Creamfields", "Swedish House Mafia", "One", "progressive", "music_baptism", "pillar_b_club"),
            ("Defqon1", "Headhunterz", "Dragonborn", "hardstyle", "laser_baptism", "pillar_c_festival"),
        ]
        for event, artist, track, genre, brand, tier in test_cases:
            req = PipelineTriggerRequest(
                event=event,
                artist=artist,
                track=track,
                genre=genre,
                brand=brand,
                tier=tier,
                drop_duration=25.0,
                from_device=False,
                input_file="input.mp4",
                start_time=10.0,
                duration=40.0,
            )
            cmd = build_orchestrator_command(req, self.workspace)
            self.assertEqual(cmd[0], sys.executable)
            self.assertEqual(cmd[1], str(self.dummy_orchestrator))
            self.assertIn("--event", cmd)
            self.assertEqual(cmd[cmd.index("--event") + 1], event)
            self.assertIn("--artist", cmd)
            self.assertEqual(cmd[cmd.index("--artist") + 1], artist)
            self.assertIn("--track", cmd)
            self.assertEqual(cmd[cmd.index("--track") + 1], track)
            self.assertIn("--genre", cmd)
            self.assertEqual(cmd[cmd.index("--genre") + 1], genre)
            self.assertIn("--brand", cmd)
            self.assertEqual(cmd[cmd.index("--brand") + 1], brand)
            self.assertIn("--tier", cmd)
            self.assertEqual(cmd[cmd.index("--tier") + 1], tier)
            self.assertIn("--input", cmd)
            self.assertEqual(cmd[cmd.index("--input") + 1], "input.mp4")
            self.assertIn("--start-time", cmd)
            self.assertEqual(cmd[cmd.index("--start-time") + 1], "10.0")
            self.assertIn("--duration", cmd)
            self.assertEqual(cmd[cmd.index("--duration") + 1], "40.0")

    async def test_02_pydantic_validation_error_handling(self):
        """Verifies Pydantic field validators reject out-of-range bounds (422 HTTP)."""
        # Duration > 59s
        res1 = await self.client.post("/trigger-pipeline", json={"duration": 75.0})
        self.assertEqual(res1.status_code, 422)

        # Drop duration < 5s
        res2 = await self.client.post("/trigger-pipeline", json={"drop_duration": 2.0})
        self.assertEqual(res2.status_code, 422)

        # Negative start time
        res3 = await self.client.post("/trigger-pipeline", json={"start_time": -1.0})
        self.assertEqual(res3.status_code, 422)

    async def test_03_real_subprocess_execution_non_blocking_and_telemetry(self):
        """Verifies genuine async subprocess execution and real non-blocking behavior."""
        start_time = time.time()
        res = await self.client.post("/trigger-pipeline", json={
            "event": "ForensicFestival",
            "artist": "ForensicArtist",
        })
        elapsed_http = time.time() - start_time

        # HTTP request must return immediately (< 0.200s) with 202 Accepted
        self.assertEqual(res.status_code, 202)
        self.assertLess(elapsed_http, 0.200)

        data = res.json()
        job_id = data["job_id"]
        self.assertTrue(job_id.startswith("job_"))

        # While process is sleeping (0.4s), verify status endpoint shows RUNNING
        res_status = await self.client.get("/status")
        self.assertEqual(res_status.status_code, 200)
        status_data = res_status.json()
        self.assertTrue(status_data["is_running"])
        self.assertEqual(status_data["current_job_id"], job_id)
        self.assertEqual(status_data["state"], "running")

        # Wait for the background subprocess to finish
        await asyncio.sleep(0.6)

        # Verify status endpoint shows completed
        res_status_after = await self.client.get("/status")
        self.assertEqual(res_status_after.status_code, 200)
        status_after = res_status_after.json()
        self.assertFalse(status_after["is_running"])
        self.assertEqual(status_after["state"], "idle")
        self.assertEqual(status_after["total_jobs_run"], 1)
        self.assertIsNotNone(status_after["last_job"])
        self.assertEqual(status_after["last_job"]["state"], "completed")
        self.assertEqual(status_after["last_job"]["exit_code"], 0)

        # Verify logs captured stdout in real-time
        res_logs = await self.client.get(f"/logs?job_id={job_id}")
        self.assertEqual(res_logs.status_code, 200)
        logs_data = res_logs.json()
        log_text = " ".join(logs_data["logs"])
        self.assertIn("[ORCHESTRATOR] Initialized pipeline", log_text)
        self.assertIn("[ORCHESTRATOR] Completed pipeline successfully", log_text)

    async def test_04_mutex_locking_and_concurrency_race_condition(self):
        """Verifies strict mutex locking under rapid concurrent requests."""
        # Trigger first long-running job
        res1 = await self.client.post("/trigger-pipeline", json={"event": "Job1"})
        self.assertEqual(res1.status_code, 202)
        job_id1 = res1.json()["job_id"]

        # Immediate second trigger must return 409 Conflict
        res2 = await self.client.post("/trigger-pipeline", json={"event": "Job2"})
        self.assertEqual(res2.status_code, 409)
        conflict_data = res2.json()
        self.assertEqual(conflict_data["status"], "conflict")
        self.assertEqual(conflict_data["current_job_id"], job_id1)
        self.assertIn("already in progress", conflict_data["error"])

        # Wait for job to finish
        await asyncio.sleep(0.6)

        # Subsequent trigger should now succeed
        res3 = await self.client.post("/trigger-pipeline", json={"event": "Job3"})
        self.assertEqual(res3.status_code, 202)
        await asyncio.sleep(0.6)

    async def test_05_concurrent_fanout_stress_mutex(self):
        """Fires 20 concurrent requests simultaneously to verify only 1 gets 202 and 19 get 409."""
        async def send_trigger(i):
            return await self.client.post("/trigger-pipeline", json={"event": f"Stress_{i}"})

        responses = await asyncio.gather(*[send_trigger(i) for i in range(20)])
        status_codes = [r.status_code for r in responses]

        # Exactly one must be 202, all 19 others must be 409
        self.assertEqual(status_codes.count(202), 1)
        self.assertEqual(status_codes.count(409), 19)

        await asyncio.sleep(0.6)

    async def test_06_cancel_endpoint_real_subprocess_termination(self):
        """Verifies POST /cancel actively terminates the executing background process."""
        res = await self.client.post("/trigger-pipeline", json={"event": "JobToCancel"})
        self.assertEqual(res.status_code, 202)
        job_id = res.json()["job_id"]

        # Immediately send cancel request
        res_cancel = await self.client.post("/cancel")
        self.assertEqual(res_cancel.status_code, 200)
        cancel_data = res_cancel.json()
        self.assertEqual(cancel_data["status"], "cancelled")
        self.assertEqual(cancel_data["job_id"], job_id)
        self.assertTrue(cancel_data["terminated"])

        await asyncio.sleep(0.1)

        # Status must reflect cancelled
        res_status = await self.client.get(f"/status/{job_id}")
        self.assertEqual(res_status.status_code, 200)
        telemetry = res_status.json()
        self.assertEqual(telemetry["state"], "cancelled")
        self.assertTrue(
            "cancel" in telemetry["error_summary"].lower() or "terminate" in telemetry["error_summary"].lower()
        )

    async def test_07_subprocess_failure_exit_code_and_stderr(self):
        """Verifies failed subprocess properly logs stderr and sets state=FAILED."""
        # Overwrite dummy orchestrator to exit with code 1 and emit stderr
        with open(self.dummy_orchestrator, "w", encoding="utf-8") as f:
            f.write(
                "import sys\n"
                "print('[STDERR] Critical failure during audio analysis', file=sys.stderr, flush=True)\n"
                "sys.exit(2)\n"
            )

        res = await self.client.post("/trigger-pipeline", json={"event": "FailTest"})
        self.assertEqual(res.status_code, 202)
        job_id = res.json()["job_id"]

        await asyncio.sleep(0.3)

        res_status = await self.client.get(f"/status/{job_id}")
        self.assertEqual(res_status.status_code, 200)
        data = res_status.json()
        self.assertEqual(data["state"], "failed")
        self.assertEqual(data["exit_code"], 2)
        self.assertIn("non-zero exit code: 2", data["error_summary"])

        res_logs = await self.client.get(f"/logs?job_id={job_id}")
        self.assertEqual(res_logs.status_code, 200)
        logs = res_logs.json()["logs"]
        stderr_entry = [line for line in logs if "Critical failure" in line]
        self.assertTrue(len(stderr_entry) > 0)

    def test_08_ring_buffer_overflow_capping(self):
        """Verifies ring buffer caps total stored log lines at max_logs without memory bloat."""
        manager = PipelineJobManager(workspace_root=self.workspace, max_logs=50)
        for i in range(100):
            manager._add_log(LogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                level="INFO",
                message=f"Log line {i}",
                job_id="job_buffer_test",
            ))

        logs = manager.get_logs()
        self.assertEqual(len(logs), 50)
        self.assertEqual(logs[0].message, "Log line 50")
        self.assertEqual(logs[-1].message, "Log line 99")

    async def test_09_health_endpoint_states(self):
        """Verifies health endpoint accurately reflects binary discovery."""
        with patch("remote_trigger.find_binary", return_value=Path("/bin/mock")), \
             patch("remote_trigger.find_adb_binary", return_value=Path("/bin/adb")):
            res = await self.client.get("/health")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["status"], "healthy")

        with patch("remote_trigger.find_binary", return_value=None), \
             patch("remote_trigger.find_adb_binary", return_value=None):
            res = await self.client.get("/health")
            self.assertEqual(res.status_code, 503)
            self.assertEqual(res.json()["status"], "unhealthy")


if __name__ == "__main__":
    unittest.main()
