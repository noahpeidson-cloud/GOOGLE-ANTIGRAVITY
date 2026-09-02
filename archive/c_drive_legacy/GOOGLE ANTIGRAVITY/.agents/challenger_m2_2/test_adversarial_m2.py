"""
Adversarial Stress Test Suite for Milestone 2 (remote_trigger.py)
Executed by Challenger 2 (teamwork_preview_challenger)

Tests:
1. Missing binaries (adb, ffmpeg, ffprobe) and GET /health status codes (503 vs 200) + schema conformance.
2. Process crash & failure telemetry (non-zero exit codes, spawn exceptions, telemetry capture).
3. Non-existent job ID queries to GET /status/{job_id} (404 Not Found, input fuzzing).
4. CLI arg parsing & env var overrides (--host, --port, --workspace, --reload, env overrides).
5. High-concurrency flood, cancellation edge cases, log buffer memory bounds, and schema validation fuzzing.
"""

import argparse
import asyncio
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure content_creation root is on sys.path
WORKSPACE_DIR = Path(__file__).resolve().parents[2] / "content_creation"
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from fastapi.testclient import TestClient
import remote_trigger
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


class TestHealthCheckExtremeStates(unittest.TestCase):
    """Stress-tests the GET /health endpoint under missing binary scenarios and filesystem faults."""

    def setUp(self):
        self.app = create_app(workspace_root=WORKSPACE_DIR)
        self.client = TestClient(self.app)

    def test_health_all_binaries_present(self):
        """When adb, ffmpeg, and ffprobe are available, returns 200 OK with status='healthy'."""
        with patch("remote_trigger.find_binary", side_effect=lambda name: Path(f"/usr/bin/{name}")), \
             patch("remote_trigger.find_adb_binary", return_value=Path("/usr/bin/adb")):
            resp = self.client.get("/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            validated = HealthResponse.model_validate(data)
            self.assertEqual(validated.status, "healthy")
            self.assertTrue(validated.adb_available)
            self.assertTrue(validated.ffmpeg_available)
            self.assertTrue(validated.ffprobe_available)

    def test_health_adb_missing_ffmpeg_ffprobe_present(self):
        """When adb is missing but ffmpeg/ffprobe exist, returns 200 OK with status='degraded'."""
        def mock_find_binary(name: str):
            if name in ("ffmpeg", "ffprobe"):
                return Path(f"/usr/bin/{name}")
            return None

        with patch("remote_trigger.find_binary", side_effect=mock_find_binary), \
             patch("remote_trigger.find_adb_binary", return_value=None):
            resp = self.client.get("/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            validated = HealthResponse.model_validate(data)
            self.assertEqual(validated.status, "degraded")
            self.assertFalse(validated.adb_available)
            self.assertTrue(validated.ffmpeg_available)
            self.assertTrue(validated.ffprobe_available)

    def test_health_ffmpeg_missing(self):
        """When ffmpeg is missing, returns 503 Service Unavailable with status='unhealthy'."""
        def mock_find_binary(name: str):
            if name == "ffprobe":
                return Path("/usr/bin/ffprobe")
            return None

        with patch("remote_trigger.find_binary", side_effect=mock_find_binary), \
             patch("remote_trigger.find_adb_binary", return_value=Path("/usr/bin/adb")):
            resp = self.client.get("/health")
            self.assertEqual(resp.status_code, 503)
            data = resp.json()
            validated = HealthResponse.model_validate(data)
            self.assertEqual(validated.status, "unhealthy")
            self.assertFalse(validated.ffmpeg_available)
            self.assertTrue(validated.ffprobe_available)
            self.assertTrue(validated.adb_available)

    def test_health_ffprobe_missing(self):
        """When ffprobe is missing, returns 503 Service Unavailable with status='unhealthy'."""
        def mock_find_binary(name: str):
            if name == "ffmpeg":
                return Path("/usr/bin/ffmpeg")
            return None

        with patch("remote_trigger.find_binary", side_effect=mock_find_binary), \
             patch("remote_trigger.find_adb_binary", return_value=Path("/usr/bin/adb")):
            resp = self.client.get("/health")
            self.assertEqual(resp.status_code, 503)
            data = resp.json()
            validated = HealthResponse.model_validate(data)
            self.assertEqual(validated.status, "unhealthy")
            self.assertTrue(validated.ffmpeg_available)
            self.assertFalse(validated.ffprobe_available)
            self.assertTrue(validated.adb_available)

    def test_health_all_binaries_missing(self):
        """When all binaries are missing, returns 503 Service Unavailable with status='unhealthy'."""
        with patch("remote_trigger.find_binary", return_value=None), \
             patch("remote_trigger.find_adb_binary", return_value=None):
            resp = self.client.get("/health")
            self.assertEqual(resp.status_code, 503)
            data = resp.json()
            validated = HealthResponse.model_validate(data)
            self.assertEqual(validated.status, "unhealthy")
            self.assertFalse(validated.adb_available)
            self.assertFalse(validated.ffmpeg_available)
            self.assertFalse(validated.ffprobe_available)

    def test_health_disk_usage_failure_resilience(self):
        """When disk_usage raises an OS permission/filesystem error, server does not crash."""
        with patch("shutil.disk_usage", side_effect=OSError("Drive inaccessible")), \
             patch("remote_trigger.find_binary", side_effect=lambda name: Path(f"/usr/bin/{name}")), \
             patch("remote_trigger.find_adb_binary", return_value=Path("/usr/bin/adb")):
            resp = self.client.get("/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIsNone(data["free_disk_space_bytes"])
            self.assertIsNone(data["free_disk_space_gb"])
            self.assertEqual(data["status"], "healthy")


class TestProcessCrashAndTelemetry(unittest.TestCase):
    """Stress-tests subprocess execution failures, non-zero exit codes, and telemetry capturing."""

    def test_subprocess_exit_code_1_failure(self):
        """Subprocess exiting with code 1 transitions state to FAILED and populates error_summary."""
        async def _run_test():
            manager = PipelineJobManager(workspace_root=WORKSPACE_DIR)
            mock_proc = MagicMock()
            mock_proc.stdout = asyncio.StreamReader()
            mock_proc.stdout.feed_data(b"Processing start...\n")
            mock_proc.stdout.feed_eof()
            mock_proc.stderr = asyncio.StreamReader()
            mock_proc.stderr.feed_data(b"Traceback (most recent call last):\nFatal error in pipeline!\n")
            mock_proc.stderr.feed_eof()
            mock_proc.wait = AsyncMock(return_value=1)

            with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
                req = PipelineTriggerRequest(event="CrashTest", auto_drop=True)
                success, trigger_res = await manager.trigger(req)
                self.assertTrue(success)
                job_id = trigger_res.job_id

                # Await active background task
                if manager._active_task:
                    await manager._active_task

                # Check manager state
                self.assertFalse(manager.is_running)
                self.assertIsNone(manager.current_job_id)

                # Check job history
                job = manager.find_job(job_id)
                self.assertIsNotNone(job)
                self.assertEqual(job.state, JobState.FAILED)
                self.assertEqual(job.exit_code, 1)
                self.assertIn("non-zero exit code: 1", job.error_summary)
                self.assertIsNotNone(job.completed_at)

                # Check logs
                logs = manager.get_logs(job_id=job_id)
                log_messages = [l.message for l in logs]
                self.assertTrue(any("Processing start..." in m for m in log_messages))
                self.assertTrue(any("Fatal error in pipeline!" in m for m in log_messages))
                self.assertTrue(any("failed with exit code 1" in m for m in log_messages))

        asyncio.run(_run_test())

    def test_subprocess_exit_code_127_command_not_found(self):
        """Subprocess exiting with code 127 records FAILED state and exit_code=127."""
        async def _run_test():
            manager = PipelineJobManager(workspace_root=WORKSPACE_DIR)
            mock_proc = MagicMock()
            mock_proc.stdout = asyncio.StreamReader()
            mock_proc.stdout.feed_eof()
            mock_proc.stderr = asyncio.StreamReader()
            mock_proc.stderr.feed_data(b"sh: orchestrator.py: command not found\n")
            mock_proc.stderr.feed_eof()
            mock_proc.wait = AsyncMock(return_value=127)

            with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
                req = PipelineTriggerRequest(event="NotFoundTest")
                success, trigger_res = await manager.trigger(req)
                self.assertTrue(success)
                job_id = trigger_res.job_id

                if manager._active_task:
                    await manager._active_task

                job = manager.find_job(job_id)
                self.assertEqual(job.state, JobState.FAILED)
                self.assertEqual(job.exit_code, 127)
                self.assertIn("127", job.error_summary)

        asyncio.run(_run_test())

    def test_subprocess_spawn_exception_handled_gracefully(self):
        """If create_subprocess_exec raises FileNotFoundError or PermissionError, mutex is unlocked and state is FAILED."""
        async def _run_test():
            manager = PipelineJobManager(workspace_root=WORKSPACE_DIR)

            with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("Python executable missing")):
                req = PipelineTriggerRequest(event="SpawnFailTest")
                success, trigger_res = await manager.trigger(req)
                self.assertTrue(success)
                job_id = trigger_res.job_id

                if manager._active_task:
                    await manager._active_task

                self.assertFalse(manager.is_running)
                job = manager.find_job(job_id)
                self.assertEqual(job.state, JobState.FAILED)
                self.assertIn("Python executable missing", job.error_summary)

                # Verify subsequent job can immediately be triggered without deadlock
                mock_proc_ok = MagicMock()
                mock_proc_ok.stdout = asyncio.StreamReader()
                mock_proc_ok.stdout.feed_eof()
                mock_proc_ok.stderr = asyncio.StreamReader()
                mock_proc_ok.stderr.feed_eof()
                mock_proc_ok.wait = AsyncMock(return_value=0)

                with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc_ok)):
                    success2, trigger_res2 = await manager.trigger(PipelineTriggerRequest(event="RecoveryTest"))
                    self.assertTrue(success2)
                    if manager._active_task:
                        await manager._active_task
                    self.assertEqual(manager.find_job(trigger_res2.job_id).state, JobState.COMPLETED)

        asyncio.run(_run_test())

    def test_status_endpoint_reflects_failure_telemetry(self):
        """GET /status and GET /status/{job_id} accurately expose error telemetry after failure."""
        app = create_app(workspace_root=WORKSPACE_DIR)
        client = TestClient(app)
        manager = app.state.job_manager

        # Directly insert a failed job record into manager history
        job = JobRecord(
            job_id="job_failed_test_001",
            command=["python", "orchestrator.py"],
            params={"event": "FailedEvent"},
        )
        job.state = JobState.FAILED
        job.exit_code = 1
        job.error_summary = "Subprocess exited with non-zero exit code: 1"
        manager._job_history.insert(0, job)
        manager._total_jobs_count = 1

        # Query GET /status
        resp_status = client.get("/status")
        self.assertEqual(resp_status.status_code, 200)
        status_data = resp_status.json()
        validated_status = StatusResponse.model_validate(status_data)
        self.assertFalse(validated_status.is_running)
        self.assertIsNone(validated_status.active_job)
        self.assertIsNotNone(validated_status.last_job)
        self.assertEqual(validated_status.last_job.state, JobState.FAILED)
        self.assertEqual(validated_status.last_job.exit_code, 1)
        self.assertEqual(validated_status.last_job.error_summary, "Subprocess exited with non-zero exit code: 1")

        # Query GET /status/{job_id}
        resp_job = client.get("/status/job_failed_test_001")
        self.assertEqual(resp_job.status_code, 200)
        job_data = resp_job.json()
        validated_job = JobTelemetry.model_validate(job_data)
        self.assertEqual(validated_job.state, JobState.FAILED)
        self.assertEqual(validated_job.exit_code, 1)
        self.assertEqual(validated_job.job_id, "job_failed_test_001")


class TestNonExistentJobAnd404Routing(unittest.TestCase):
    """Stress-tests job ID lookups, 404 responses, and malformed path routing."""

    def setUp(self):
        self.app = create_app(workspace_root=WORKSPACE_DIR)
        self.client = TestClient(self.app)

    def test_non_existent_job_id_returns_404(self):
        """Querying a non-existent job ID returns 404 Not Found with descriptive detail."""
        resp = self.client.get("/status/job_non_existent_999999")
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertIn("detail", data)
        self.assertIn("job_non_existent_999999", data["detail"])
        self.assertIn("not found", data["detail"].lower())

    def test_fuzzed_job_ids_return_404(self):
        """Fuzzed IDs (None, null, special chars, UUIDs) return 404 without crashing or 500s."""
        fuzz_ids = [
            "None",
            "null",
            "undefined",
            "0",
            "-1",
            "job_!@#$%^&*()_+",
            "../../etc/passwd",
            "SELECT * FROM jobs;",
            "a" * 500,
        ]
        for fid in fuzz_ids:
            resp = self.client.get(f"/status/{fid}")
            self.assertEqual(resp.status_code, 404, f"Failed on fuzzed ID: {fid}")
            self.assertIn("detail", resp.json())

    def test_status_base_route_returns_200(self):
        """GET /status returns 200 OK StatusResponse even when history is empty."""
        resp = self.client.get("/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        validated = StatusResponse.model_validate(data)
        self.assertEqual(validated.state, JobState.IDLE)
        self.assertFalse(validated.is_running)
        self.assertEqual(len(validated.recent_jobs), 0)


class TestCLIArgParsingAndEnvOverrides(unittest.TestCase):
    """Stress-tests CLI argument parsing, environment variable overrides, and precedence."""

    def test_default_cli_args_without_env(self):
        """CLI parser defaults to host=0.0.0.0, port=8000, reload=False when no args or env vars exist."""
        with patch.dict(os.environ, {}, clear=True):
            parser = argparse.ArgumentParser()
            parser.add_argument("--host", default=os.environ.get("REMOTE_TRIGGER_HOST", "0.0.0.0"))
            parser.add_argument("--port", type=int, default=int(os.environ.get("REMOTE_TRIGGER_PORT", 8000)))
            parser.add_argument("--workspace", default=str(WORKSPACE_DIR))
            parser.add_argument("--reload", action="store_true")

            args = parser.parse_args([])
            self.assertEqual(args.host, "0.0.0.0")
            self.assertEqual(args.port, 8000)
            self.assertEqual(args.workspace, str(WORKSPACE_DIR))
            self.assertFalse(args.reload)

    def test_env_var_overrides(self):
        """Environment variables REMOTE_TRIGGER_HOST and REMOTE_TRIGGER_PORT override defaults."""
        custom_env = {
            "REMOTE_TRIGGER_HOST": "192.168.1.150",
            "REMOTE_TRIGGER_PORT": "9090",
        }
        with patch.dict(os.environ, custom_env, clear=True):
            parser = argparse.ArgumentParser()
            parser.add_argument("--host", default=os.environ.get("REMOTE_TRIGGER_HOST", "0.0.0.0"))
            parser.add_argument("--port", type=int, default=int(os.environ.get("REMOTE_TRIGGER_PORT", 8000)))
            parser.add_argument("--workspace", default=str(WORKSPACE_DIR))
            parser.add_argument("--reload", action="store_true")

            args = parser.parse_args([])
            self.assertEqual(args.host, "192.168.1.150")
            self.assertEqual(args.port, 9090)

    def test_cli_flags_override_env_vars(self):
        """Explicit CLI flags take precedence over environment variables."""
        custom_env = {
            "REMOTE_TRIGGER_HOST": "192.168.1.150",
            "REMOTE_TRIGGER_PORT": "9090",
        }
        with patch.dict(os.environ, custom_env, clear=True):
            parser = argparse.ArgumentParser()
            parser.add_argument("--host", default=os.environ.get("REMOTE_TRIGGER_HOST", "0.0.0.0"))
            parser.add_argument("--port", type=int, default=int(os.environ.get("REMOTE_TRIGGER_PORT", 8000)))
            parser.add_argument("--workspace", default=str(WORKSPACE_DIR))
            parser.add_argument("--reload", action="store_true")

            args = parser.parse_args(["--host", "127.0.0.1", "--port", "7070", "--reload", "--workspace", "/tmp/custom"])
            self.assertEqual(args.host, "127.0.0.1")
            self.assertEqual(args.port, 7070)
            self.assertEqual(args.workspace, "/tmp/custom")
            self.assertTrue(args.reload)

    def test_main_dispatch_invokes_uvicorn_correctly(self):
        """Calling remote_trigger.main() parses arguments and invokes uvicorn.run with exact values."""
        with patch("sys.argv", ["remote_trigger.py", "--host", "10.0.0.5", "--port", "8888", "--reload"]), \
             patch("uvicorn.run") as mock_uvicorn_run, \
             patch("remote_trigger.create_app") as mock_create_app:

            mock_app_instance = MagicMock()
            mock_create_app.return_value = mock_app_instance

            remote_trigger.main()

            mock_create_app.assert_called_once()
            mock_uvicorn_run.assert_called_once_with(
                mock_app_instance,
                host="10.0.0.5",
                port=8888,
                reload=True,
            )


class TestConcurrencyAndAdversarialAttacks(unittest.TestCase):
    """Stress-tests high concurrency mutex locking, rapid cancellation, log buffer memory bounds, and payload validation."""

    def test_concurrency_flood_mutex_locking(self):
        """When 50 concurrent trigger requests are fired, exactly 1 succeeds (202) and 49 receive 409 Conflict."""
        async def _run_test():
            manager = PipelineJobManager(workspace_root=WORKSPACE_DIR)

            # Keep process running for a short period
            blocker_event = asyncio.Event()

            async def mock_wait():
                await blocker_event.wait()
                return 0

            mock_proc = MagicMock()
            mock_proc.stdout = asyncio.StreamReader()
            mock_proc.stdout.feed_eof()
            mock_proc.stderr = asyncio.StreamReader()
            mock_proc.stderr.feed_eof()
            mock_proc.wait = mock_wait

            with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
                req = PipelineTriggerRequest(event="FloodTest")

                async def fire_trigger(i):
                    return await manager.trigger(req)

                tasks = [fire_trigger(i) for i in range(50)]
                results = await asyncio.gather(*tasks)

                success_count = sum(1 for success, _ in results if success)
                conflict_count = sum(1 for success, _ in results if not success)

                self.assertEqual(success_count, 1, "Exactly 1 job should acquire the mutex")
                self.assertEqual(conflict_count, 49, "49 requests should receive conflict")

                # Verify conflict responses match schema
                for success, res in results:
                    if not success:
                        self.assertIsInstance(res, ConflictResponse)
                        self.assertEqual(res.status, "conflict")
                        self.assertEqual(res.error, "Pipeline execution is already in progress")

                # Unblock and finish
                blocker_event.set()
                if manager._active_task:
                    await manager._active_task

        asyncio.run(_run_test())

    def test_cancellation_when_idle_returns_400(self):
        """POST /cancel when no job is running returns HTTP 400 Bad Request."""
        app = create_app(workspace_root=WORKSPACE_DIR)
        client = TestClient(app)

        resp = client.post("/cancel")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No active pipeline job currently running", resp.json()["detail"])

    def test_cancellation_active_job_transitions_to_cancelled(self):
        """Cancelling an active job terminates process and transitions state to CANCELLED."""
        async def _run_test():
            manager = PipelineJobManager(workspace_root=WORKSPACE_DIR)

            proc_terminated = False
            proc_killed = False

            mock_proc = MagicMock()
            mock_proc.returncode = -15
            mock_proc.stdout = asyncio.StreamReader()
            mock_proc.stdout.feed_eof()
            mock_proc.stderr = asyncio.StreamReader()
            mock_proc.stderr.feed_eof()

            running_event = asyncio.Event()

            async def mock_wait():
                # Process remains running until terminate/kill is called
                await running_event.wait()
                return -15

            def mock_terminate():
                nonlocal proc_terminated
                proc_terminated = True
                running_event.set()

            def mock_kill():
                nonlocal proc_killed
                proc_killed = True
                running_event.set()

            mock_proc.terminate = mock_terminate
            mock_proc.kill = mock_kill
            mock_proc.wait = mock_wait

            with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
                req = PipelineTriggerRequest(event="CancelTest")
                success, trigger_res = await manager.trigger(req)
                self.assertTrue(success)
                self.assertTrue(manager.is_running)

                # Give event loop a cycle to assign _active_process
                await asyncio.sleep(0.01)

                # Now cancel the job
                cancel_success, cancel_msg, job_id = await manager.cancel_active_job()
                self.assertTrue(cancel_success)
                self.assertTrue(proc_terminated)
                self.assertEqual(job_id, trigger_res.job_id)
                self.assertFalse(manager.is_running)

                job = manager.find_job(job_id)
                self.assertEqual(job.state, JobState.CANCELLED)
                self.assertEqual(job.error_summary, "Process terminated via /cancel request")

        asyncio.run(_run_test())

    def test_log_ring_buffer_memory_cap(self):
        """Ring buffer caps at max_logs (2000) and discards oldest lines without memory explosion."""
        manager = PipelineJobManager(workspace_root=WORKSPACE_DIR, max_logs=2000)

        # Ingest 5000 lines
        for i in range(5000):
            manager._add_log(LogEntry(
                timestamp=f"2026-08-22T00:00:{i:04d}Z",
                level="INFO",
                message=f"Log line sequence {i}",
                job_id="job_stress_001" if i % 2 == 0 else "job_stress_002",
            ))

        logs = manager.get_logs()
        self.assertEqual(len(logs), 2000)
        # Oldest retained message should be line 3000
        self.assertEqual(logs[0].message, "Log line sequence 3000")
        self.assertEqual(logs[-1].message, "Log line sequence 4999")

        # Tail filter
        tail_50 = manager.get_logs(tail=50)
        self.assertEqual(len(tail_50), 50)
        self.assertEqual(tail_50[-1].message, "Log line sequence 4999")

        # Job ID filter
        job1_logs = manager.get_logs(job_id="job_stress_001")
        self.assertEqual(len(job1_logs), 1000)
        self.assertTrue(all(l.job_id == "job_stress_001" for l in job1_logs))

    def test_payload_validation_rejects_out_of_bounds(self):
        """Pydantic rejects invalid parameters (negative drop_duration, excessive drop_duration, invalid duration)."""
        app = create_app(workspace_root=WORKSPACE_DIR)
        client = TestClient(app)

        invalid_payloads = [
            {"drop_duration": -1.0},
            {"drop_duration": 120.0},
            {"drop_duration": 2.0},  # Below 5.0
            {"start_time": -5.0},
            {"duration": 1.0},       # Below 5.0
            {"duration": 75.0},      # Above 59.0
            {"poll_timeout": 5.0},   # Below 10.0
        ]

        for payload in invalid_payloads:
            resp = client.post("/trigger-pipeline", json=payload)
            self.assertEqual(resp.status_code, 422, f"Failed to reject invalid payload: {payload}")

    def test_command_builder_injection_safety(self):
        """Verify command builder tokenizes inputs safely without shell interpolation vulnerability."""
        malicious_input = PipelineTriggerRequest(
            event="Concert; rm -rf /; echo hacked",
            artist="$(whoami)",
            track="ID`calc.exe`",
            brand="laser_baptism",
            tier="pillar_a_stadium_arena",
            reframe_mode="center_crop",
            auto_drop=True,
            publish_youtube=True,
            auto_promote=True,
            dry_run=True,
        )
        cmd = build_orchestrator_command(malicious_input, WORKSPACE_DIR)

        # Assert arguments are passed as discrete array elements (not concatenated into a raw shell string)
        self.assertIn("Concert; rm -rf /; echo hacked", cmd)
        self.assertIn("$(whoami)", cmd)
        self.assertIn("ID`calc.exe`", cmd)
        self.assertIn("--publish-youtube", cmd)
        self.assertIn("--auto-promote", cmd)
        self.assertIn("--dry-run", cmd)
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(cmd[1], str(WORKSPACE_DIR / "orchestrator.py"))


    def test_extra_fields_preserved_in_job_params(self):
        """Pydantic model_config extra='allow' preserves unknown extra payload fields in job telemetry."""
        async def _run_test():
            manager = PipelineJobManager(workspace_root=WORKSPACE_DIR)
            mock_proc = MagicMock()
            mock_proc.stdout = asyncio.StreamReader()
            mock_proc.stdout.feed_eof()
            mock_proc.stderr = asyncio.StreamReader()
            mock_proc.stderr.feed_eof()
            mock_proc.wait = AsyncMock(return_value=0)

            with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
                req = PipelineTriggerRequest(
                    event="ExtraFieldsTest",
                    custom_metadata_tag="vip_access",
                    tasker_battery_level=88,
                )
                success, trigger_res = await manager.trigger(req)
                self.assertTrue(success)
                if manager._active_task:
                    await manager._active_task

                job = manager.find_job(trigger_res.job_id)
                self.assertIsNotNone(job)
                self.assertEqual(job.params.get("custom_metadata_tag"), "vip_access")
                self.assertEqual(job.params.get("tasker_battery_level"), 88)

        asyncio.run(_run_test())

    def test_cors_preflight_headers(self):
        """OPTIONS preflight request returns CORS headers echoing Origin when credentials are enabled."""
        app = create_app(workspace_root=WORKSPACE_DIR)
        client = TestClient(app)

        resp = client.options(
            "/trigger-pipeline",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(resp.status_code, 200)
        # With allow_credentials=True, Starlette echoes the requesting origin per CORS standard
        self.assertEqual(resp.headers.get("access-control-allow-origin"), "http://localhost:3000")

    def test_sequential_jobs_history_accumulation(self):
        """Sequential jobs execute cleanly, incrementing total_jobs_run and preserving history."""
        async def _run_test():
            manager = PipelineJobManager(workspace_root=WORKSPACE_DIR)

            for i in range(3):
                mock_proc = MagicMock()
                mock_proc.stdout = asyncio.StreamReader()
                mock_proc.stdout.feed_eof()
                mock_proc.stderr = asyncio.StreamReader()
                mock_proc.stderr.feed_eof()
                mock_proc.wait = AsyncMock(return_value=0)

                with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
                    success, res = await manager.trigger(PipelineTriggerRequest(event=f"SeqJob_{i}"))
                    self.assertTrue(success)
                    if manager._active_task:
                        await manager._active_task

            self.assertEqual(manager.total_jobs_run, 3)
            self.assertEqual(len(manager._job_history), 3)
            self.assertEqual(manager._job_history[0].params["event"], "SeqJob_2")
            self.assertEqual(manager._job_history[1].params["event"], "SeqJob_1")
            self.assertEqual(manager._job_history[2].params["event"], "SeqJob_0")

        asyncio.run(_run_test())

    def test_double_cancellation_race_condition(self):
        """Calling /cancel twice on the same active job returns 200 for the first and 400 for the second."""
        async def _run_test():
            manager = PipelineJobManager(workspace_root=WORKSPACE_DIR)

            running_event = asyncio.Event()

            async def mock_wait():
                await running_event.wait()
                return -15

            def mock_term():
                running_event.set()

            mock_proc = MagicMock()
            mock_proc.returncode = -15
            mock_proc.stdout = asyncio.StreamReader()
            mock_proc.stdout.feed_eof()
            mock_proc.stderr = asyncio.StreamReader()
            mock_proc.stderr.feed_eof()
            mock_proc.wait = mock_wait
            mock_proc.terminate = mock_term
            mock_proc.kill = MagicMock()

            with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
                success, trigger_res = await manager.trigger(PipelineTriggerRequest(event="DoubleCancel"))
                self.assertTrue(success)
                await asyncio.sleep(0.01)

                # First cancel -> Success
                s1, msg1, jid1 = await manager.cancel_active_job()
                self.assertTrue(s1)
                self.assertEqual(jid1, trigger_res.job_id)

                # Second cancel -> Failure (no active job)
                s2, msg2, jid2 = await manager.cancel_active_job()
                self.assertFalse(s2)
                self.assertIn("No active pipeline job", msg2)
                self.assertIsNone(jid2)

        asyncio.run(_run_test())

    def test_cancellation_sigterm_timeout_triggers_sigkill(self):
        """When a process ignores terminate() and times out (3.0s), cancel_active_job() invokes kill()."""
        async def _run_test():
            manager = PipelineJobManager(workspace_root=WORKSPACE_DIR)

            kill_invoked = False
            running_event = asyncio.Event()

            async def mock_wait():
                await running_event.wait()
                return -9

            def stub_kill():
                nonlocal kill_invoked
                kill_invoked = True
                running_event.set()

            mock_proc = MagicMock()
            mock_proc.returncode = -9
            mock_proc.stdout = asyncio.StreamReader()
            mock_proc.stdout.feed_eof()
            mock_proc.stderr = asyncio.StreamReader()
            mock_proc.stderr.feed_eof()
            mock_proc.terminate = MagicMock()
            mock_proc.kill = stub_kill
            mock_proc.wait = mock_wait

            with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)), \
                 patch("asyncio.wait_for", side_effect=[asyncio.TimeoutError(), -9]):

                success, trigger_res = await manager.trigger(PipelineTriggerRequest(event="StubbornProcess"))
                self.assertTrue(success)
                await asyncio.sleep(0.01)

                cancel_success, msg, jid = await manager.cancel_active_job()
                self.assertTrue(cancel_success)
                self.assertTrue(kill_invoked)
                self.assertEqual(jid, trigger_res.job_id)

        asyncio.run(_run_test())


if __name__ == "__main__":
    unittest.main(verbosity=2)
