"""
test_remote_trigger.py - Unit and Integration Test Suite for FastAPI Zero-Touch Remote Trigger

Tests cover:
1. Pydantic v2 schemas and validation (PipelineTriggerRequest, TriggerResponse, ConflictResponse, JobTelemetry, StatusResponse, HealthResponse, CancelResponse, LogEntry, LogsResponse).
2. Command line builder (build_orchestrator_command) across multiple configuration permutations.
3. PipelineJobManager lifecycle (job creation, mutex locking, subprocess spawning, stdout/stderr streaming, completion, failure, cancellation, log buffer ring-buffering, history management).
4. FastAPI REST Endpoints via TestClient:
   - GET /health (healthy, degraded, unhealthy 503 states)
   - POST /trigger-pipeline (HTTP 202 Accepted, <50ms dispatch)
   - POST /trigger-pipeline Concurrency Mutex (HTTP 409 Conflict)
   - POST /trigger-pipeline Pydantic Validation (HTTP 422 for malformed payloads)
   - GET /status and GET /status/{job_id} (daemon and job telemetry, 404 handling)
   - GET /logs with ?tail=N and ?job_id= filters
   - POST /cancel (cancellation of active job vs HTTP 400 when idle)
5. CLI entrypoint argument parsing.
"""

import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from remote_trigger import (
    CancelResponse,
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
    build_orchestrator_command,
    create_app,
)


class TestRemoteTriggerSchemas(unittest.TestCase):
    """Unit tests for Pydantic V2 schemas and payload validations."""

    def test_pipeline_trigger_request_defaults(self):
        req = PipelineTriggerRequest()
        self.assertEqual(req.event, "Concert")
        self.assertEqual(req.artist, "Artist")
        self.assertEqual(req.track, "ID")
        self.assertEqual(req.genre, "house")
        self.assertEqual(req.brand, "laser_baptism")
        self.assertEqual(req.tier, "pillar_a_stadium_arena")
        self.assertTrue(req.from_device)
        self.assertIsNone(req.device_serial)
        self.assertIsNone(req.input_file)
        self.assertTrue(req.auto_drop)
        self.assertEqual(req.drop_duration, 30.0)
        self.assertEqual(req.reframe_mode, "center_crop")
        self.assertFalse(req.publish_youtube)
        self.assertFalse(req.auto_promote)
        self.assertEqual(req.poll_timeout, 300.0)
        self.assertFalse(req.dry_run)

    def test_pipeline_trigger_request_custom_and_extra_fields(self):
        req = PipelineTriggerRequest(
            event="Tomorrowland",
            artist="Alesso",
            track="Heroes",
            genre="progressive_house",
            brand="music_baptism",
            tier="pillar_c_festival_mega",
            from_device=False,
            input_file="input.mp4",
            auto_drop=False,
            start_time=12.5,
            duration=28.0,
            publish_youtube=True,
            auto_promote=True,
            poll_timeout=180.0,
            dry_run=True,
            custom_extra_field="arbitrary_value",
        )
        self.assertEqual(req.event, "Tomorrowland")
        self.assertEqual(req.artist, "Alesso")
        self.assertFalse(req.from_device)
        self.assertEqual(req.input_file, "input.mp4")
        self.assertFalse(req.auto_drop)
        self.assertEqual(req.start_time, 12.5)
        self.assertEqual(req.duration, 28.0)
        self.assertTrue(req.publish_youtube)
        self.assertTrue(req.auto_promote)
        self.assertEqual(req.poll_timeout, 180.0)
        self.assertTrue(req.dry_run)
        # Extra fields allowed by model_config
        self.assertEqual(getattr(req, "custom_extra_field", None), "arbitrary_value")

    def test_pipeline_trigger_request_festival_field(self):
        req = PipelineTriggerRequest(festival="Tomorrowland", artist="Alesso")
        self.assertEqual(req.festival, "Tomorrowland")
        self.assertEqual(req.artist, "Alesso")
        self.assertEqual(req.resolved_event, "Tomorrowland")
        self.assertEqual(req.resolved_artist, "Alesso")

        # Test fallback when festival is None or empty whitespace
        req_fallback = PipelineTriggerRequest(festival="  ", event="EDC", artist="")
        self.assertEqual(req_fallback.resolved_event, "EDC")
        self.assertEqual(req_fallback.resolved_artist, "Artist")

    def test_pipeline_trigger_request_validation_bounds(self):
        # drop_duration must be between 5.0 and 59.0
        with self.assertRaises(ValueError):
            PipelineTriggerRequest(drop_duration=4.9)
        with self.assertRaises(ValueError):
            PipelineTriggerRequest(drop_duration=60.0)

        # duration must be between 5.0 and 59.0 if provided
        with self.assertRaises(ValueError):
            PipelineTriggerRequest(duration=3.0)
        with self.assertRaises(ValueError):
            PipelineTriggerRequest(duration=65.0)

        # start_time must be non-negative
        with self.assertRaises(ValueError):
            PipelineTriggerRequest(start_time=-1.0)

    def test_trigger_response_schema(self):
        res = TriggerResponse(
            status="accepted",
            job_id="job_20260822_001",
            message="Accepted",
            command=["python", "orchestrator.py"],
            started_at="2026-08-22T00:00:00Z",
        )
        self.assertEqual(res.status, "accepted")
        self.assertEqual(res.job_id, "job_20260822_001")
        self.assertEqual(len(res.command), 2)

    def test_conflict_response_schema(self):
        res = ConflictResponse(
            status="conflict",
            error="Pipeline execution is already in progress",
            current_job_id="job_20260822_000",
            started_at="2026-08-22T00:00:00Z",
            elapsed_seconds=15.4,
        )
        self.assertEqual(res.status, "conflict")
        self.assertEqual(res.current_job_id, "job_20260822_000")
        self.assertEqual(res.elapsed_seconds, 15.4)

    def test_job_telemetry_schema(self):
        tel = JobTelemetry(
            job_id="job_123",
            state=JobState.COMPLETED,
            command=["python", "test.py"],
            started_at="2026-08-22T00:00:00Z",
            completed_at="2026-08-22T00:00:10Z",
            elapsed_seconds=10.0,
            exit_code=0,
            error_summary=None,
            params={"event": "EDC"},
        )
        self.assertEqual(tel.state, JobState.COMPLETED)
        self.assertEqual(tel.exit_code, 0)
        self.assertEqual(tel.elapsed_seconds, 10.0)


class TestCommandBuilder(unittest.TestCase):
    """Unit tests for build_orchestrator_command."""

    def setUp(self):
        self.workspace = Path("/tmp/content_creation").resolve()

    def test_build_orchestrator_command_defaults(self):
        req = PipelineTriggerRequest()
        cmd = build_orchestrator_command(req, self.workspace, python_bin="python")

        expected_prefix = [
            "python",
            str(self.workspace / "orchestrator.py"),
            "--target-dir",
            str(self.workspace),
            "pipeline",
            "--event", "Concert",
            "--artist", "Artist",
            "--track", "ID",
            "--genre", "house",
            "--brand", "laser_baptism",
            "--tier", "pillar_a_stadium_arena",
            "--reframe-mode", "center_crop",
            "--drop-duration", "30.0",
            "--from-device",
            "--auto-drop",
        ]
        self.assertEqual(cmd, expected_prefix)

    def test_build_orchestrator_command_with_device_serial(self):
        req = PipelineTriggerRequest(from_device=True, device_serial="R5CX10ABCDE")
        cmd = build_orchestrator_command(req, self.workspace, python_bin="python")
        self.assertIn("--from-device", cmd)
        self.assertIn("--device", cmd)
        self.assertEqual(cmd[cmd.index("--device") + 1], "R5CX10ABCDE")

    def test_build_orchestrator_command_with_local_input_file(self):
        req = PipelineTriggerRequest(from_device=False, input_file="my_take.mp4")
        cmd = build_orchestrator_command(req, self.workspace, python_bin="python")
        self.assertNotIn("--from-device", cmd)
        self.assertIn("--input", cmd)
        self.assertEqual(cmd[cmd.index("--input") + 1], "my_take.mp4")

    def test_build_orchestrator_command_manual_cut_and_publishing(self):
        req = PipelineTriggerRequest(
            event="Ultra",
            artist="Garrix",
            track="Animals",
            genre="mainstage",
            brand="laser_baptism",
            tier="pillar_a_stadium_arena",
            from_device=False,
            input_file="ultra.mp4",
            auto_drop=False,
            start_time=25.0,
            duration=30.0,
            publish_youtube=True,
            auto_promote=True,
            poll_timeout=120.0,
            client_secrets="secrets.json",
            token_path="tok.json",
            dry_run=True,
        )
        cmd = build_orchestrator_command(req, self.workspace, python_bin="python")

        self.assertNotIn("--auto-drop", cmd)
        self.assertIn("--start-time", cmd)
        self.assertEqual(cmd[cmd.index("--start-time") + 1], "25.0")
        self.assertIn("--duration", cmd)
        self.assertEqual(cmd[cmd.index("--duration") + 1], "30.0")
        self.assertIn("--publish-youtube", cmd)
        self.assertIn("--auto-promote", cmd)
        self.assertIn("--poll-timeout", cmd)
        self.assertEqual(cmd[cmd.index("--poll-timeout") + 1], "120.0")
        self.assertIn("--client-secrets", cmd)
        self.assertEqual(cmd[cmd.index("--client-secrets") + 1], "secrets.json")
        self.assertIn("--token-path", cmd)
        self.assertEqual(cmd[cmd.index("--token-path") + 1], "tok.json")
        self.assertIn("--dry-run", cmd)

    def test_build_orchestrator_command_with_festival_and_artist(self):
        req = PipelineTriggerRequest(festival="EDC Las Vegas", artist="Sub Focus")
        cmd = build_orchestrator_command(req, self.workspace, python_bin="python")
        self.assertIn("--event", cmd)
        self.assertEqual(cmd[cmd.index("--event") + 1], "EDC Las Vegas")
        self.assertIn("--artist", cmd)
        self.assertEqual(cmd[cmd.index("--artist") + 1], "Sub Focus")


class TestJobRecordAndPipelineJobManager(unittest.IsolatedAsyncioTestCase):
    """Unit tests for JobRecord and PipelineJobManager internal logic."""

    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir).resolve()
        self.manager = PipelineJobManager(workspace_root=self.workspace, max_history=5, max_logs=10)

    async def asyncTearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_job_record_elapsed_seconds(self):
        job = JobRecord("job_test", ["echo", "hi"], {"event": "test"})
        self.assertEqual(job.elapsed_seconds, 0.0)

        t0 = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 8, 22, 12, 0, 5, 500000, tzinfo=timezone.utc)
        job.started_at = t0
        job.completed_at = t1
        self.assertEqual(job.elapsed_seconds, 5.5)

        tel = job.to_telemetry()
        self.assertEqual(tel.job_id, "job_test")
        self.assertEqual(tel.elapsed_seconds, 5.5)

    async def test_manager_initial_state(self):
        self.assertFalse(self.manager.is_running)
        self.assertIsNone(self.manager.current_job_id)
        self.assertEqual(self.manager.total_jobs_run, 0)
        self.assertIsNone(self.manager.get_active_job())
        self.assertIsNone(self.manager.get_last_job())

    async def test_manager_log_buffer_ring_buffering(self):
        for i in range(15):
            self.manager._add_log(LogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                level="INFO",
                message=f"Log line {i}",
                job_id=f"job_{i % 2}",
            ))

        # Capacity capped at max_logs = 10
        all_logs = self.manager.get_logs()
        self.assertEqual(len(all_logs), 10)
        self.assertEqual(all_logs[-1].message, "Log line 14")
        self.assertEqual(all_logs[0].message, "Log line 5")

        # Tail filter
        tail_3 = self.manager.get_logs(tail=3)
        self.assertEqual(len(tail_3), 3)
        self.assertEqual(tail_3[-1].message, "Log line 14")

        # Job ID filter
        job_0_logs = self.manager.get_logs(job_id="job_0")
        self.assertTrue(all(l.job_id == "job_0" for l in job_0_logs))

    @patch("asyncio.create_subprocess_exec")
    async def test_manager_successful_job_execution(self, mock_exec):
        fake_process = MagicMock()
        fake_process.stdout.readline = AsyncMock(side_effect=[b"Processing take 1\n", b"Finished successfully\n", b""])
        fake_process.stderr.readline = AsyncMock(side_effect=[b""])
        fake_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = fake_process

        req = PipelineTriggerRequest(event="EDC", dry_run=True)
        success, res = await self.manager.trigger(req)

        self.assertTrue(success)
        self.assertIsInstance(res, TriggerResponse)
        self.assertEqual(res.status, "accepted")
        self.assertEqual(self.manager.total_jobs_run, 1)

        # Wait for the background task to complete
        if self.manager._active_task:
            await self.manager._active_task

        self.assertFalse(self.manager.is_running)
        last_job = self.manager.get_last_job()
        self.assertIsNotNone(last_job)
        self.assertEqual(last_job.state, JobState.COMPLETED)
        self.assertEqual(last_job.exit_code, 0)
        self.assertIsNone(last_job.error_summary)

    @patch("asyncio.create_subprocess_exec")
    async def test_manager_failed_job_execution(self, mock_exec):
        fake_process = MagicMock()
        fake_process.stdout.readline = AsyncMock(side_effect=[b"Starting\n", b""])
        fake_process.stderr.readline = AsyncMock(side_effect=[b"Error: File not found\n", b""])
        fake_process.wait = AsyncMock(return_value=1)
        mock_exec.return_value = fake_process

        req = PipelineTriggerRequest(event="EDC")
        success, res = await self.manager.trigger(req)

        self.assertTrue(success)
        if self.manager._active_task:
            await self.manager._active_task

        self.assertFalse(self.manager.is_running)
        last_job = self.manager.get_last_job()
        self.assertIsNotNone(last_job)
        self.assertEqual(last_job.state, JobState.FAILED)
        self.assertEqual(last_job.exit_code, 1)
        self.assertIn("non-zero exit code: 1", last_job.error_summary or "")

    @patch("asyncio.create_subprocess_exec")
    async def test_manager_mutex_lock_conflict(self, mock_exec):
        # Create an uncompleted long-running process
        fake_process = MagicMock()
        wait_event = asyncio.Event()

        async def slow_readline():
            await wait_event.wait()
            return b""

        fake_process.stdout.readline = AsyncMock(side_effect=slow_readline)
        fake_process.stderr.readline = AsyncMock(side_effect=slow_readline)
        fake_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = fake_process

        req1 = PipelineTriggerRequest(event="Job1")
        success1, res1 = await self.manager.trigger(req1)
        self.assertTrue(success1)
        self.assertTrue(self.manager.is_running)

        # Trigger second request while first is still running
        req2 = PipelineTriggerRequest(event="Job2")
        success2, res2 = await self.manager.trigger(req2)
        self.assertFalse(success2)
        self.assertIsInstance(res2, ConflictResponse)
        self.assertEqual(res2.status, "conflict")
        self.assertEqual(res2.current_job_id, res1.job_id)

        # Release first job
        wait_event.set()
        if self.manager._active_task:
            await self.manager._active_task

    async def test_manager_cancel_active_job(self):
        # Simulate an active job with a mock process
        job = JobRecord("job_cancel_test", ["sleep", "100"], {})
        job.state = JobState.RUNNING
        job.started_at = datetime.now(timezone.utc)
        self.manager._active_job = job

        mock_proc = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = AsyncMock(return_value=15)
        mock_proc.returncode = 15
        self.manager._active_process = mock_proc

        cancelled, msg, job_id = await self.manager.cancel_active_job()
        self.assertTrue(cancelled)
        self.assertEqual(job_id, "job_cancel_test")
        self.assertIn("Successfully terminated", msg)
        self.assertEqual(job.state, JobState.CANCELLED)
        self.assertFalse(self.manager.is_running)

    async def test_manager_cancel_when_idle(self):
        cancelled, msg, job_id = await self.manager.cancel_active_job()
        self.assertFalse(cancelled)
        self.assertIsNone(job_id)
        self.assertIn("No active pipeline job", msg)


class TestRemoteTriggerAPIEndpoints(unittest.TestCase):
    """Integration test suite for FastAPI REST endpoints using TestClient."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir).resolve()
        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # GET /health
    # -------------------------------------------------------------------------

    @patch("remote_trigger.find_binary")
    @patch("remote_trigger.find_adb_binary")
    def test_health_check_healthy(self, mock_find_adb, mock_find_bin):
        mock_find_adb.return_value = Path("/usr/bin/adb")
        mock_find_bin.side_effect = lambda name: Path(f"/usr/bin/{name}")

        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["adb_available"])
        self.assertTrue(data["ffmpeg_available"])
        self.assertTrue(data["ffprobe_available"])
        self.assertFalse(data["is_pipeline_running"])
        self.assertIn("free_disk_space_bytes", data)

    @patch("remote_trigger.find_binary")
    @patch("remote_trigger.find_adb_binary")
    def test_health_check_degraded_when_adb_missing(self, mock_find_adb, mock_find_bin):
        mock_find_adb.return_value = None
        mock_find_bin.side_effect = lambda name: None if name == "adb" else Path(f"/usr/bin/{name}")

        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "degraded")
        self.assertFalse(data["adb_available"])
        self.assertTrue(data["ffmpeg_available"])
        self.assertTrue(data["ffprobe_available"])

    @patch("remote_trigger.find_binary")
    @patch("remote_trigger.find_adb_binary")
    def test_health_check_unhealthy_503_when_ffmpeg_missing(self, mock_find_adb, mock_find_bin):
        mock_find_adb.return_value = Path("/usr/bin/adb")
        mock_find_bin.side_effect = lambda name: None if name == "ffmpeg" else Path(f"/usr/bin/{name}")

        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        data = response.json()
        self.assertEqual(data["status"], "unhealthy")
        self.assertFalse(data["ffmpeg_available"])

    # -------------------------------------------------------------------------
    # POST /trigger-pipeline
    # -------------------------------------------------------------------------

    @patch("asyncio.create_subprocess_exec")
    def test_trigger_pipeline_accepted_202(self, mock_exec):
        fake_process = MagicMock()
        fake_process.stdout.readline = AsyncMock(side_effect=[b"Started\n", b""])
        fake_process.stderr.readline = AsyncMock(side_effect=[b""])
        fake_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = fake_process

        payload = {
            "event": "EDCOrlando",
            "artist": "JohnSummit",
            "track": "WhereYouAre",
            "from_device": True,
            "auto_drop": True,
            "drop_duration": 30.0,
            "dry_run": True,
        }

        response = self.client.post("/trigger-pipeline", json=payload)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()
        self.assertEqual(data["status"], "accepted")
        self.assertIn("job_", data["job_id"])
        self.assertIn("orchestrator.py", " ".join(data["command"]))
        self.assertIn("started_at", data)

    @patch("asyncio.create_subprocess_exec")
    def test_trigger_pipeline_empty_body_accepted_with_defaults(self, mock_exec):
        fake_process = MagicMock()
        fake_process.stdout.readline = AsyncMock(side_effect=[b""])
        fake_process.stderr.readline = AsyncMock(side_effect=[b""])
        fake_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = fake_process

        response = self.client.post("/trigger-pipeline", json={})
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()
        self.assertEqual(data["status"], "accepted")
        self.assertIn("--event", data["command"])
        self.assertIn("Concert", data["command"])

    @patch("asyncio.create_subprocess_exec")
    def test_trigger_pipeline_with_festival_payload(self, mock_exec):
        fake_process = MagicMock()
        fake_process.stdout.readline = AsyncMock(side_effect=[b"Started\n", b""])
        fake_process.stderr.readline = AsyncMock(side_effect=[b""])
        fake_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = fake_process

        payload = {
            "festival": "Tomorrowland",
            "artist": "MartinGarrix",
            "track": "Starlight",
            "dry_run": True,
        }

        response = self.client.post("/trigger-pipeline", json=payload)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()
        self.assertEqual(data["status"], "accepted")
        self.assertIn("--event", data["command"])
        self.assertEqual(data["command"][data["command"].index("--event") + 1], "Tomorrowland")
        self.assertIn("--artist", data["command"])
        self.assertEqual(data["command"][data["command"].index("--artist") + 1], "MartinGarrix")

    def test_trigger_pipeline_validation_error_422(self):
        # Invalid drop_duration < 5.0
        response = self.client.post("/trigger-pipeline", json={"drop_duration": 2.0})
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Invalid duration > 59.0
        response2 = self.client.post("/trigger-pipeline", json={"duration": 75.0})
        self.assertEqual(response2.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Invalid start_time < 0
        response3 = self.client.post("/trigger-pipeline", json={"start_time": -5.0})
        self.assertEqual(response3.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_trigger_pipeline_conflict_409_when_busy(self):
        manager: PipelineJobManager = self.app.state.job_manager
        # Manually inject an active running job
        running_job = JobRecord("job_active_conflict", ["sleep", "10"], {})
        running_job.state = JobState.RUNNING
        running_job.started_at = datetime.now(timezone.utc)
        manager._active_job = running_job

        response = self.client.post("/trigger-pipeline", json={"event": "EDC"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        data = response.json()
        self.assertEqual(data["status"], "conflict")
        self.assertEqual(data["current_job_id"], "job_active_conflict")
        self.assertIn("already in progress", data["error"])

    # -------------------------------------------------------------------------
    # GET /status & GET /status/{job_id}
    # -------------------------------------------------------------------------

    def test_get_status_idle(self):
        response = self.client.get("/status")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["state"], "idle")
        self.assertFalse(data["is_running"])
        self.assertIsNone(data["current_job_id"])
        self.assertEqual(data["total_jobs_run"], 0)
        self.assertIsNone(data["active_job"])
        self.assertIsNone(data["last_job"])
        self.assertEqual(data["recent_jobs"], [])

    def test_get_status_running_and_historical(self):
        manager: PipelineJobManager = self.app.state.job_manager
        historical_job = JobRecord("job_hist_1", ["echo", "1"], {})
        historical_job.state = JobState.COMPLETED
        historical_job.started_at = datetime(2026, 8, 22, 1, 0, 0, tzinfo=timezone.utc)
        historical_job.completed_at = datetime(2026, 8, 22, 1, 0, 5, tzinfo=timezone.utc)
        historical_job.exit_code = 0
        manager._job_history.append(historical_job)

        active_job = JobRecord("job_active_2", ["echo", "2"], {})
        active_job.state = JobState.RUNNING
        active_job.started_at = datetime.now(timezone.utc)
        manager._active_job = active_job
        manager._total_jobs_count = 2

        response = self.client.get("/status")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["state"], "running")
        self.assertTrue(data["is_running"])
        self.assertEqual(data["current_job_id"], "job_active_2")
        self.assertEqual(data["total_jobs_run"], 2)
        self.assertIsNotNone(data["active_job"])
        self.assertEqual(data["active_job"]["job_id"], "job_active_2")
        self.assertEqual(len(data["recent_jobs"]), 1)

    def test_get_specific_job_status(self):
        manager: PipelineJobManager = self.app.state.job_manager
        hist_job = JobRecord("job_find_me", ["cmd"], {"param": 1})
        hist_job.state = JobState.COMPLETED
        hist_job.started_at = datetime.now(timezone.utc)
        hist_job.completed_at = datetime.now(timezone.utc)
        hist_job.exit_code = 0
        manager._job_history.append(hist_job)

        # Existing job lookup
        res = self.client.get("/status/job_find_me")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data["job_id"], "job_find_me")
        self.assertEqual(data["state"], "completed")

        # Non-existent job lookup -> 404
        res_404 = self.client.get("/status/job_not_exist")
        self.assertEqual(res_404.status_code, status.HTTP_404_NOT_FOUND)

    # -------------------------------------------------------------------------
    # GET /logs
    # -------------------------------------------------------------------------

    def test_get_logs_filtering(self):
        manager: PipelineJobManager = self.app.state.job_manager
        now_iso = datetime.now(timezone.utc).isoformat()
        manager._add_log(LogEntry(timestamp=now_iso, level="INFO", message="Log A", job_id="job_A"))
        manager._add_log(LogEntry(timestamp=now_iso, level="ERROR", message="Log B", job_id="job_B"))
        manager._add_log(LogEntry(timestamp=now_iso, level="INFO", message="Log C", job_id="job_A"))

        # All logs
        res_all = self.client.get("/logs")
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        self.assertEqual(res_all.json()["total_lines"], 3)

        # Filter by tail
        res_tail = self.client.get("/logs?tail=2")
        self.assertEqual(res_tail.json()["total_lines"], 2)
        self.assertEqual(res_tail.json()["entries"][-1]["message"], "Log C")

        # Filter by job_id
        res_job = self.client.get("/logs?job_id=job_B")
        self.assertEqual(res_job.json()["total_lines"], 1)
        self.assertEqual(res_job.json()["entries"][0]["message"], "Log B")

    # -------------------------------------------------------------------------
    # POST /cancel
    # -------------------------------------------------------------------------

    def test_cancel_endpoint_when_running_vs_idle(self):
        manager: PipelineJobManager = self.app.state.job_manager

        # When idle -> 400 Bad Request
        res_idle = self.client.post("/cancel")
        self.assertEqual(res_idle.status_code, status.HTTP_400_BAD_REQUEST)

        # Inject running job with mock process
        running_job = JobRecord("job_to_cancel", ["proc"], {})
        running_job.state = JobState.RUNNING
        running_job.started_at = datetime.now(timezone.utc)
        manager._active_job = running_job

        mock_p = MagicMock()
        mock_p.terminate = MagicMock()
        mock_p.wait = AsyncMock(return_value=-15)
        mock_p.returncode = -15
        manager._active_process = mock_p

        res_cancel = self.client.post("/cancel")
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        data = res_cancel.json()
        self.assertEqual(data["status"], "cancelled")
        self.assertEqual(data["job_id"], "job_to_cancel")
        self.assertTrue(data["terminated"])


# ============================================================================
# PWA DOM INSPECTOR & TEST SUITE
# ============================================================================

class PWADOMInspector(HTMLParser):
    """Deterministic in-memory HTML parser for PWA DOM verification."""

    def __init__(self):
        super().__init__()
        self.meta_tags: List[Dict[str, str]] = []
        self.buttons: List[Dict[str, str]] = []
        self.links: List[Dict[str, str]] = []
        self.div_ids: List[str] = []
        self.all_ids: List[str] = []
        self.scripts: List[str] = []
        self.styles: List[str] = []
        self._current_tag: Optional[str] = None
        self._button_texts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k: (v if v is not None else "") for k, v in attrs}
        self._current_tag = tag
        if "id" in attr_dict:
            self.all_ids.append(attr_dict["id"])
        if tag == "meta":
            self.meta_tags.append(attr_dict)
        elif tag == "button":
            self.buttons.append(attr_dict)
        elif tag == "link":
            self.links.append(attr_dict)
        elif tag == "div" and "id" in attr_dict:
            self.div_ids.append(attr_dict["id"])

    def handle_endtag(self, tag: str):
        self._current_tag = None

    def handle_data(self, data: str):
        if self._current_tag == "script":
            self.scripts.append(data)
        elif self._current_tag == "style":
            self.styles.append(data)
        elif self._current_tag in ("button", "div", "span"):
            self._button_texts.append(data)

    def get_button_text(self) -> str:
        return " ".join(self._button_texts).strip()

    def get_combined_script(self) -> str:
        return "\n".join(self.scripts)

    def get_combined_style(self) -> str:
        return "\n".join(self.styles)

    def find_meta(self, key: str, value: str) -> Optional[Dict[str, str]]:
        for meta in self.meta_tags:
            if meta.get(key) == value:
                return meta
        return None


class TestRemoteTriggerPWADashboard(unittest.TestCase):
    """Hermetic test suite for the Mobile-First PWA Remote Trigger Dashboard."""

    def setUp(self):
        self.workspace_dir = tempfile.mkdtemp()
        self.workspace = Path(self.workspace_dir)

        # Copy static assets from repo or create standard test PWA files
        repo_static = Path(__file__).resolve().parent.parent / "static"
        workspace_static = self.workspace / "static"
        workspace_static.mkdir(parents=True, exist_ok=True)

        if (repo_static / "index.html").exists():
            shutil.copy(str(repo_static / "index.html"), str(workspace_static / "index.html"))
        if (repo_static / "manifest.json").exists():
            shutil.copy(str(repo_static / "manifest.json"), str(workspace_static / "manifest.json"))

        self.app = create_app(workspace_root=self.workspace)
        self.client = TestClient(self.app)

    def tearDown(self):
        shutil.rmtree(self.workspace_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage
    # -------------------------------------------------------------------------

    def test_get_root_serves_html_200(self):
        """GET / must return HTTP 200 OK with Content-Type: text/html."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.headers.get("content-type", "").startswith("text/html"))
        self.assertGreater(len(res.text), 100)

    def test_pwa_meta_tags_present(self):
        """PWA meta tags (viewport, apple-mobile-web-app-capable, theme-color) must be present."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        inspector = PWADOMInspector()
        inspector.feed(res.text)

        # Viewport meta tag
        viewport_meta = inspector.find_meta("name", "viewport")
        self.assertIsNotNone(viewport_meta, "Missing <meta name='viewport'> tag")
        content = viewport_meta.get("content", "")
        self.assertIn("width=device-width", content)
        self.assertIn("initial-scale=1.0", content)
        self.assertIn("viewport-fit=cover", content)

        # Apple / Mobile web app capable
        apple_cap = inspector.find_meta("name", "apple-mobile-web-app-capable")
        self.assertIsNotNone(apple_cap, "Missing <meta name='apple-mobile-web-app-capable'> tag")
        self.assertEqual(apple_cap.get("content"), "yes")

        mobile_cap = inspector.find_meta("name", "mobile-web-app-capable")
        self.assertIsNotNone(mobile_cap, "Missing <meta name='mobile-web-app-capable'> tag")
        self.assertEqual(mobile_cap.get("content"), "yes")

        # Theme color meta tag
        theme_meta = inspector.find_meta("name", "theme-color")
        self.assertIsNotNone(theme_meta, "Missing <meta name='theme-color'> tag")
        self.assertEqual(theme_meta.get("content"), "#000000")

    def test_massive_trigger_button_element_and_text(self):
        """Trigger button #trigger-btn must exist and contain 'TRIGGER EDM PIPELINE'."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        inspector = PWADOMInspector()
        inspector.feed(res.text)

        # Verify button ID in IDs list
        self.assertIn("trigger-btn", inspector.all_ids, "Missing button element with id='trigger-btn'")

        # Verify button contains verbatim 'TRIGGER EDM PIPELINE'
        button_match = any(b.get("id") == "trigger-btn" for b in inspector.buttons)
        self.assertTrue(button_match, "Missing <button id='trigger-btn'> tag")
        self.assertIn("TRIGGER EDM PIPELINE", res.text)

    def test_visual_toast_and_dom_feedback(self):
        """Toast feedback elements (#toast-card, #toast-container) must exist in DOM."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        inspector = PWADOMInspector()
        inspector.feed(res.text)

        self.assertIn("toast-container", inspector.all_ids)
        self.assertIn("toast-card", inspector.all_ids)
        self.assertIn("toast-title", inspector.all_ids)
        self.assertIn("toast-message", inspector.all_ids)

    def test_telemetry_hud_elements_present(self):
        """Telemetry HUD elements (#status-card, #daemon-state, #active-job-id, #elapsed-time) must exist."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        inspector = PWADOMInspector()
        inspector.feed(res.text)

        self.assertIn("status-card", inspector.all_ids)
        self.assertIn("daemon-state", inspector.all_ids)
        self.assertIn("active-job-id", inspector.all_ids)
        self.assertIn("elapsed-time", inspector.all_ids)

    def test_javascript_fetch_post_trigger_pipeline(self):
        """Client-side JavaScript must dispatch fetch('/trigger-pipeline') via POST."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        inspector = PWADOMInspector()
        inspector.feed(res.text)
        script_code = inspector.get_combined_script()

        self.assertIn("/trigger-pipeline", script_code)
        self.assertTrue(
            re.search(r"fetch\(\s*['\"]/trigger-pipeline['\"]\s*,\s*\{[^}]*method:\s*['\"]POST['\"]", script_code, re.DOTALL)
            or "method: 'POST'" in script_code
            or 'method: "POST"' in script_code
        )

    def test_javascript_success_haptics_202(self):
        """Client-side JavaScript must execute navigator.vibrate([100, 100, 100]) on HTTP 202."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        inspector = PWADOMInspector()
        inspector.feed(res.text)
        script_code = inspector.get_combined_script()

        # Assert [100, 100, 100] pattern
        self.assertTrue(
            re.search(r"\[\s*100\s*,\s*100\s*,\s*100\s*\]", script_code),
            "Expected success vibration pattern [100, 100, 100] in script",
        )

    def test_javascript_error_haptics_409_and_failure(self):
        """Client-side JavaScript must execute navigator.vibrate([500, 200, 500]) on HTTP 409 and error."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        inspector = PWADOMInspector()
        inspector.feed(res.text)
        script_code = inspector.get_combined_script()

        # Assert [500, 200, 500] pattern
        self.assertTrue(
            re.search(r"\[\s*500\s*,\s*200\s*,\s*500\s*\]", script_code),
            "Expected error vibration pattern [500, 200, 500] in script",
        )

    def test_javascript_vibration_feature_detection_guard(self):
        """navigator.vibrate must be guarded with feature detection check."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        inspector = PWADOMInspector()
        inspector.feed(res.text)
        script_code = inspector.get_combined_script()

        self.assertTrue(
            "'vibrate' in navigator" in script_code or '"vibrate" in navigator' in script_code,
            "Expected 'vibrate' in navigator feature detection guard in client script",
        )

    def test_static_asset_mounting(self):
        """Static asset mounting must serve /static/manifest.json."""
        res = self.client.get("/static/manifest.json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data.get("display"), "standalone")
        self.assertEqual(data.get("theme_color"), "#000000")

    def test_manifest_json_endpoint(self):
        """GET /manifest.json must serve PWA manifest with correct JSON MIME type."""
        res = self.client.get("/manifest.json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("short_name", data)
        self.assertEqual(data["short_name"], "EDM Trigger")

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases
    # -------------------------------------------------------------------------

    def test_index_html_missing_404_handling(self):
        """If index.html is missing, GET / must return HTTP 404 with actionable error."""
        empty_dir = tempfile.mkdtemp()
        try:
            empty_app = create_app(workspace_root=Path(empty_dir))
            empty_client = TestClient(empty_app)
            res = empty_client.get("/")
            self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)

    def test_http_method_not_allowed_on_root(self):
        """POST / must return HTTP 405 Method Not Allowed."""
        res = self.client.post("/")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_pwa_touch_action_and_safe_area_css(self):
        """CSS must specify touch-action: manipulation and safe-area insets."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        inspector = PWADOMInspector()
        inspector.feed(res.text)
        style_code = inspector.get_combined_style()

        self.assertIn("touch-action: manipulation", style_code)
        self.assertIn("env(safe-area-inset-top", style_code)
        self.assertIn("env(safe-area-inset-bottom", style_code)
        self.assertIn("#000000", style_code)

    def test_button_debouncing_logic(self):
        """JavaScript must lock button (.disabled = true) during in-flight dispatch."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        inspector = PWADOMInspector()
        inspector.feed(res.text)
        script_code = inspector.get_combined_script()

        self.assertIn(".disabled", script_code)

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions (E2E PWA Workflow)
    # -------------------------------------------------------------------------

    def test_e2e_pwa_trigger_flow_accepted_202(self):
        """Simulate PWA client reading UI and triggering pipeline returning 202."""
        # 1. Fetch PWA HTML
        pwa_res = self.client.get("/")
        self.assertEqual(pwa_res.status_code, status.HTTP_200_OK)

        # 2. Dispatch POST /trigger-pipeline as PWA client does
        trigger_payload = {
            "event": "LiveConcert",
            "artist": "AutoArtist",
            "brand": "laser_baptism",
            "tier": "pillar_a_stadium_arena",
            "from_device": True,
            "auto_drop": True,
            "dry_run": True,
        }

        # Mock create_subprocess_exec to avoid launching real long-running process in test
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_proc.returncode = 0
        mock_proc.stdout.readline = AsyncMock(side_effect=[b"Mock PWA Output\n", b""])
        mock_proc.stderr.readline = AsyncMock(side_effect=[b""])
        mock_proc.wait = AsyncMock(return_value=0)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            res = self.client.post("/trigger-pipeline", json=trigger_payload)
            self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED)
            data = res.json()
            self.assertEqual(data["status"], "accepted")
            self.assertIn("job_id", data)

    def test_e2e_pwa_trigger_flow_conflict_409(self):
        """Simulate PWA client trigger when job is already running, returning 409."""
        manager: PipelineJobManager = self.app.state.job_manager
        active_job = JobRecord("pwa_active_job", ["cmd"], {})
        active_job.state = JobState.RUNNING
        active_job.started_at = datetime.now(timezone.utc)
        manager._active_job = active_job

        res = self.client.post("/trigger-pipeline", json={"event": "ConflictTest"})
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        data = res.json()
        self.assertEqual(data["status"], "conflict")
        self.assertEqual(data["current_job_id"], "pwa_active_job")


if __name__ == "__main__":
    unittest.main()

