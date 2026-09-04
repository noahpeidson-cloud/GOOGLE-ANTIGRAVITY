"""
test_worker_m2_verification.py - Comprehensive Independent Programmatic Verification Suite for remote_trigger.py
"""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure content_creation is in Python path
workspace_dir = Path(__file__).resolve().parents[2] / "content_creation"
sys.path.insert(0, str(workspace_dir))

from fastapi.testclient import TestClient
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


class MockAsyncProcess:
    """Mock process providing simulated asynchronous pipes for testing."""
    def __init__(self, exit_code: int = 0, stdout_lines: list = None, stderr_lines: list = None, delay: float = 0.0):
        self.returncode = exit_code
        self._delay = delay
        self._terminated = False
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        for line in (stdout_lines or [b"[PIPELINE] Ingesting take...\n", b"[COMPLETE] Master exported\n"]):
            self.stdout.feed_data(line)
        self.stdout.feed_eof()
        for line in (stderr_lines or []):
            self.stderr.feed_data(line)
        self.stderr.feed_eof()

    async def wait(self):
        if self._delay > 0 and not self._terminated:
            try:
                await asyncio.sleep(self._delay)
            except asyncio.CancelledError:
                pass
        return self.returncode

    def terminate(self):
        self._terminated = True
        self.returncode = -15

    def kill(self):
        self._terminated = True
        self.returncode = -9


class TestRemoteTriggerServer(unittest.TestCase):
    """Hermetic unit and integration tests for remote_trigger.py."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.test_dir.name)
        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)
        self.manager: PipelineJobManager = self.app.state.job_manager

    def tearDown(self):
        self.test_dir.cleanup()

    def test_command_builder_defaults(self):
        req = PipelineTriggerRequest(
            event="Tomorrowland",
            artist="Hardwell",
            track="Spaceman",
            genre="bigroom",
            brand="laser_baptism",
            tier="pillar_a_stadium_arena",
            from_device=True,
            device_serial="RFCT123456",
            auto_drop=True,
            drop_duration=28.5,
            publish_youtube=True,
            auto_promote=True,
            poll_timeout=150.0,
            dry_run=True,
        )
        cmd = build_orchestrator_command(req, self.workspace)
        self.assertIn("orchestrator.py", cmd[1])
        self.assertIn("pipeline", cmd)
        self.assertIn("--event", cmd)
        self.assertIn("Tomorrowland", cmd)
        self.assertIn("--artist", cmd)
        self.assertIn("Hardwell", cmd)
        self.assertIn("--track", cmd)
        self.assertIn("Spaceman", cmd)
        self.assertIn("--from-device", cmd)
        self.assertIn("--device", cmd)
        self.assertIn("RFCT123456", cmd)
        self.assertIn("--auto-drop", cmd)
        self.assertIn("--drop-duration", cmd)
        self.assertIn("28.5", cmd)
        self.assertIn("--publish-youtube", cmd)
        self.assertIn("--auto-promote", cmd)
        self.assertIn("--poll-timeout", cmd)
        self.assertIn("150.0", cmd)
        self.assertIn("--dry-run", cmd)

    def test_command_builder_input_file_and_manual_overrides(self):
        req = PipelineTriggerRequest(
            event="Ultra",
            artist="Martin Garrix",
            track="Animals",
            from_device=False,
            input_file="custom_raw.mp4",
            auto_drop=False,
            start_time=12.5,
            duration=35.0,
            reframe_mode="blur_pad",
            publish_youtube=True,
            auto_promote=False,
            client_secrets="secrets.json",
            token_path="token.json",
        )
        cmd = build_orchestrator_command(req, self.workspace)
        self.assertNotIn("--from-device", cmd)
        self.assertIn("--input", cmd)
        self.assertIn("custom_raw.mp4", cmd)
        self.assertNotIn("--auto-drop", cmd)
        self.assertIn("--start-time", cmd)
        self.assertIn("12.5", cmd)
        self.assertIn("--duration", cmd)
        self.assertIn("35.0", cmd)
        self.assertIn("--reframe-mode", cmd)
        self.assertIn("blur_pad", cmd)
        self.assertIn("--client-secrets", cmd)
        self.assertIn("secrets.json", cmd)
        self.assertIn("--token-path", cmd)
        self.assertIn("token.json", cmd)

    def test_health_endpoint_healthy(self):
        with patch("remote_trigger.find_binary", return_value=Path("/usr/bin/mock")), \
             patch("remote_trigger.find_adb_binary", return_value=Path("/usr/bin/adb")):
            res = self.client.get("/health")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "healthy")
            self.assertTrue(data["adb_available"])
            self.assertTrue(data["ffmpeg_available"])
            self.assertTrue(data["ffprobe_available"])
            self.assertFalse(data["is_pipeline_running"])
            self.assertIn("workspace_root", data)
            self.assertIn("timestamp", data)

    def test_health_endpoint_degraded_missing_adb(self):
        with patch("remote_trigger.find_binary", return_value=Path("/usr/bin/mock")), \
             patch("remote_trigger.find_adb_binary", return_value=None):
            res = self.client.get("/health")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "degraded")
            self.assertFalse(data["adb_available"])
            self.assertTrue(data["ffmpeg_available"])
            self.assertTrue(data["ffprobe_available"])

    def test_health_endpoint_unhealthy_missing_critical(self):
        with patch("remote_trigger.find_binary", return_value=None), \
             patch("remote_trigger.find_adb_binary", return_value=None):
            res = self.client.get("/health")
            self.assertEqual(res.status_code, 503)
            data = res.json()
            self.assertEqual(data["status"], "unhealthy")
            self.assertFalse(data["ffmpeg_available"])
            self.assertFalse(data["ffprobe_available"])

    def test_trigger_pipeline_success_202(self):
        mock_proc = MockAsyncProcess(
            exit_code=0,
            stdout_lines=[b"[PHASE 1] Pulling take\n", b"[PHASE 2] Transcoding\n"],
            stderr_lines=[b"[FFMPEG] Processing frame 100\n"]
        )
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            res = self.client.post("/trigger-pipeline", json={
                "event": "EDC",
                "artist": "John Summit",
                "dry_run": True,
            })
            self.assertEqual(res.status_code, 202)
            data = res.json()
            self.assertEqual(data["status"], "accepted")
            self.assertTrue(data["job_id"].startswith("job_"))
            self.assertIn("pipeline", data["command"])
            self.assertIn("John Summit", data["command"])
            self.assertIn("started_at", data)

    def test_trigger_pipeline_failed_exit_code(self):
        mock_proc = MockAsyncProcess(
            exit_code=1,
            stdout_lines=[b"[ERROR] Audio processing failed\n"],
            stderr_lines=[b"[STDERR] Librosa failed\n"]
        )
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            res = self.client.post("/trigger-pipeline", json={
                "event": "Lost Lands",
                "artist": "Excision",
            })
            self.assertEqual(res.status_code, 202)
            job_id = res.json()["job_id"]

            # Wait briefly for async subprocess task to finish in background
            time.sleep(0.05)

            job = self.manager.find_job(job_id)
            self.assertIsNotNone(job)
            self.assertEqual(job.state, JobState.FAILED)
            self.assertEqual(job.exit_code, 1)
            self.assertIn("non-zero exit code: 1", job.error_summary)

    def test_trigger_pipeline_mutex_409_conflict(self):
        now = datetime.now(timezone.utc)
        active_job = JobRecord(job_id="job_active_123", command=["cmd"], params={})
        active_job.state = JobState.RUNNING
        active_job.started_at = now
        self.manager._active_job = active_job

        res = self.client.post("/trigger-pipeline", json={"event": "Coachella"})
        self.assertEqual(res.status_code, 409)
        data = res.json()
        self.assertEqual(data["status"], "conflict")
        self.assertEqual(data["current_job_id"], "job_active_123")
        self.assertIn("Pipeline execution is already in progress", data["error"])

    def test_status_endpoint_idle_and_historical(self):
        res = self.client.get("/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["state"], "idle")
        self.assertFalse(data["is_running"])
        self.assertIsNone(data["current_job_id"])
        self.assertEqual(data["total_jobs_run"], 0)

        # Add a finished job to history
        job = JobRecord(job_id="job_hist_1", command=["cmd"], params={"artist": "Alesso"})
        job.state = JobState.COMPLETED
        job.started_at = datetime.now(timezone.utc)
        job.completed_at = datetime.now(timezone.utc)
        job.exit_code = 0
        self.manager._job_history.append(job)
        self.manager._total_jobs_count = 1

        res2 = self.client.get("/status")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["total_jobs_run"], 1)
        self.assertEqual(len(data2["recent_jobs"]), 1)
        self.assertEqual(data2["recent_jobs"][0]["job_id"], "job_hist_1")
        self.assertEqual(data2["recent_jobs"][0]["state"], "completed")

    def test_status_specific_job_found_and_not_found(self):
        job = JobRecord(job_id="job_specific_999", command=["cmd"], params={})
        job.state = JobState.COMPLETED
        job.started_at = datetime.now(timezone.utc)
        self.manager._job_history.append(job)

        res = self.client.get("/status/job_specific_999")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["job_id"], "job_specific_999")

        res_404 = self.client.get("/status/job_nonexistent")
        self.assertEqual(res_404.status_code, 404)
        self.assertIn("not found", res_404.json()["detail"].lower())

    def test_logs_endpoint_filtering(self):
        self.manager._add_log(LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level="INFO",
            message="Line 1 for job A",
            job_id="job_A",
        ))
        self.manager._add_log(LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level="INFO",
            message="Line 2 for job B",
            job_id="job_B",
        ))
        self.manager._add_log(LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level="ERROR",
            message="Line 3 for job A",
            job_id="job_A",
        ))

        # Get all logs with tail=2
        res = self.client.get("/logs?tail=2")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_lines"], 2)
        self.assertIn("Line 2 for job B", data["logs"][0])
        self.assertIn("Line 3 for job A", data["logs"][1])

        # Filter by job_id
        res_job = self.client.get("/logs?job_id=job_A")
        self.assertEqual(res_job.status_code, 200)
        data_job = res_job.json()
        self.assertEqual(data_job["total_lines"], 2)
        self.assertEqual(data_job["job_id"], "job_A")
        self.assertTrue(all("job A" in msg for msg in data_job["logs"]))

    def test_cancel_endpoint_no_active_job_400(self):
        res = self.client.post("/cancel")
        self.assertEqual(res.status_code, 400)
        self.assertIn("No active pipeline job", res.json()["detail"])

    def test_cancel_endpoint_active_job_success(self):
        mock_proc = MockAsyncProcess(exit_code=0, delay=1.0)
        job = JobRecord(job_id="job_to_cancel", command=["test"], params={})
        job.state = JobState.RUNNING
        job.started_at = datetime.now(timezone.utc)

        self.manager._active_job = job
        self.manager._active_process = mock_proc

        res = self.client.post("/cancel")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "cancelled")
        self.assertEqual(data["job_id"], "job_to_cancel")
        self.assertTrue(data["terminated"])
        self.assertEqual(job.state, JobState.CANCELLED)

    def test_backward_compatibility_aliases(self):
        self.assertIs(PipelineTriggerResponse, TriggerResponse)
        self.assertIs(PipelineConflictResponse, ConflictResponse)
        self.assertIs(JobDetail, JobTelemetry)
        self.assertIs(JobStatusResponse, StatusResponse)
        self.assertIs(CancelJobResponse, CancelResponse)


if __name__ == "__main__":
    unittest.main()
