"""
adversarial_suite.py - Comprehensive Empirical Challenger Stress Test Suite for remote_trigger.py
Part of Milestone 2 Verification by Challenger 1.
"""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure content_creation is in sys.path
workspace_dir = Path(__file__).resolve().parents[2] / "content_creation"
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

import httpx
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


class MockControllableProcess:
    """Mock process providing asynchronous stream piping and controlled delay."""

    def __init__(self, exit_code: int = 0, delay: float = 0.0, stdout_lines=None, stderr_lines=None):
        self.returncode = exit_code
        self.delay = delay
        self._terminated = False
        self._killed = False
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()

        lines_out = stdout_lines or [b"[STAGE 1] Ingesting...\n", b"[STAGE 2] Complete\n"]
        for line in lines_out:
            self.stdout.feed_data(line)
        self.stdout.feed_eof()

        lines_err = stderr_lines or []
        for line in lines_err:
            self.stderr.feed_data(line)
        self.stderr.feed_eof()

    async def wait(self):
        if self.delay > 0 and not self._terminated and not self._killed:
            await asyncio.sleep(self.delay)
        return self.returncode

    def terminate(self):
        self._terminated = True
        self.returncode = -15

    def kill(self):
        self._killed = True
        self.returncode = -9


class TestAdversarialFastAPISuite(unittest.IsolatedAsyncioTestCase):
    """Hermetic async adversarial test suite executing against FastAPI ASGI endpoints."""

    async def asyncSetUp(self):
        self.test_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.workspace = Path(self.test_dir.name)
        self.app = create_app(workspace_root=self.workspace)
        self.manager: PipelineJobManager = self.app.state.job_manager
        self.transport = httpx.ASGITransport(app=self.app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        try:
            self.test_dir.cleanup()
        except Exception:
            pass

    # ------------------------------------------------------------------------
    # 1. CONCURRENCY & MUTEX BURST STRESS TESTS
    # ------------------------------------------------------------------------
    async def test_burst_concurrency_single_winner_and_all_conflicts(self):
        """Send 50 simultaneous trigger requests to verify atomic single-job mutex locking."""
        mock_proc = MockControllableProcess(delay=1.0)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            num_requests = 50

            async def send_req(i):
                t0 = time.perf_counter()
                res = await self.client.post("/trigger-pipeline", json={
                    "event": f"BurstFestival_{i}",
                    "artist": "Adversary",
                    "dry_run": True,
                })
                t1 = time.perf_counter()
                return res.status_code, res.json(), (t1 - t0)

            tasks = [send_req(i) for i in range(num_requests)]
            results = await asyncio.gather(*tasks)

            status_codes = [r[0] for r in results]
            latencies_ms = [r[2] * 1000.0 for r in results]

            accepted_count = status_codes.count(202)
            conflict_count = status_codes.count(409)

            print(f"\n[STRESS TEST] Concurrency 50 burst: Accepted={accepted_count}, Conflict={conflict_count}")
            print(f"[STRESS TEST] Latency stats: min={min(latencies_ms):.2f}ms, max={max(latencies_ms):.2f}ms, avg={(sum(latencies_ms)/len(latencies_ms)):.2f}ms")

            self.assertEqual(accepted_count, 1, f"Expected exactly 1 request to win 202, got {accepted_count}")
            self.assertEqual(conflict_count, num_requests - 1, f"Expected {num_requests - 1} requests to get 409, got {conflict_count}")

            # Verify that all 409 responses reference the winning job ID
            winning_res = [r[1] for r in results if r[0] == 202][0]
            winning_job_id = winning_res["job_id"]

            for r in results:
                if r[0] == 409:
                    self.assertEqual(r[1]["status"], "conflict")
                    self.assertEqual(r[1]["current_job_id"], winning_job_id)

    async def test_sequential_rapid_handoff(self):
        """Verify that sequential jobs can be triggered one after another as soon as previous finishes."""
        for i in range(10):
            mock_proc = MockControllableProcess(exit_code=0, delay=0.005)
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                res = await self.client.post("/trigger-pipeline", json={"event": f"Sequential_{i}"})
                self.assertEqual(res.status_code, 202)

                # Poll until job finishes
                for _ in range(50):
                    await asyncio.sleep(0.01)
                    if not self.manager.is_running:
                        break

                status_res = await self.client.get("/status")
                self.assertEqual(status_res.status_code, 200)
                self.assertFalse(status_res.json()["is_running"])

        self.assertEqual(self.manager.total_jobs_run, 10)
        self.assertEqual(len(self.manager._job_history), 10)

    # ------------------------------------------------------------------------
    # 2. LATENCY BENCHMARKING (<50ms)
    # ------------------------------------------------------------------------
    async def test_response_time_under_50ms_across_trials(self):
        """Verify that /trigger-pipeline returns in <50ms even when subprocess takes 5 seconds."""
        latencies = []
        trials = 30

        for i in range(trials):
            td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
            ws = Path(td.name)
            app = create_app(workspace_root=ws)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
                mock_proc = MockControllableProcess(delay=5.0)

                with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                    t0 = time.perf_counter()
                    res = await test_client.post("/trigger-pipeline", json={"event": f"LatencyTrial_{i}"})
                    t1 = time.perf_counter()

                    elapsed_ms = (t1 - t0) * 1000.0
                    latencies.append(elapsed_ms)
                    self.assertEqual(res.status_code, 202)
                    self.assertLess(elapsed_ms, 50.0, f"Trial {i} took {elapsed_ms:.2f}ms which exceeds 50ms ceiling")
            try:
                td.cleanup()
            except Exception:
                pass

        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[-1]
        print(f"\n[LATENCY BENCHMARK] 30 Trials: min={latencies[0]:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, max={p99:.2f}ms")
        self.assertLess(p95, 30.0, f"p95 latency was {p95:.2f}ms")

    # ------------------------------------------------------------------------
    # 3. MALFORMED JSON & SCHEMA BOUNDARY FUZZING (HTTP 422)
    # ------------------------------------------------------------------------
    async def test_malformed_json_syntax(self):
        """Malformed JSON syntax must return 422 Unprocessable Entity."""
        res = await self.client.post(
            "/trigger-pipeline",
            content="{invalid_json: 'missing_quotes'",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(res.status_code, 422)

    async def test_drop_duration_boundary_constraints(self):
        """drop_duration has constraints ge=5.0, le=59.0."""
        res_low = await self.client.post("/trigger-pipeline", json={"drop_duration": 4.9})
        self.assertEqual(res_low.status_code, 422)

        res_high = await self.client.post("/trigger-pipeline", json={"drop_duration": 59.1})
        self.assertEqual(res_high.status_code, 422)

    async def test_duration_boundary_constraints(self):
        """duration has constraints ge=5.0, le=59.0."""
        res_low = await self.client.post("/trigger-pipeline", json={"duration": 3.0})
        self.assertEqual(res_low.status_code, 422)

        res_high = await self.client.post("/trigger-pipeline", json={"duration": 60.0})
        self.assertEqual(res_high.status_code, 422)

    async def test_start_time_negative_constraint(self):
        """start_time has constraint ge=0.0."""
        res = await self.client.post("/trigger-pipeline", json={"start_time": -1.0})
        self.assertEqual(res.status_code, 422)

    async def test_poll_timeout_boundary_constraint(self):
        """poll_timeout has constraint ge=10.0."""
        res = await self.client.post("/trigger-pipeline", json={"publish_youtube": True, "poll_timeout": 5.0})
        self.assertEqual(res.status_code, 422)

    async def test_type_mismatch_fuzzing(self):
        """Invalid types passed for bools/floats must return 422."""
        res1 = await self.client.post("/trigger-pipeline", json={"auto_drop": {"nested": "dict"}})
        self.assertEqual(res1.status_code, 422)

        res2 = await self.client.post("/trigger-pipeline", json={"drop_duration": "not_a_number"})
        self.assertEqual(res2.status_code, 422)

        res3 = await self.client.post("/trigger-pipeline", json={"event": [1, 2, 3]})
        self.assertEqual(res3.status_code, 422)

    # ------------------------------------------------------------------------
    # 4. SUBPROCESS CANCELLATION & RECOVERY
    # ------------------------------------------------------------------------
    async def test_cancel_active_job_and_immediate_reactivation(self):
        """Verify cancellation cleanly terminates active job and allows immediate subsequent job."""
        mock_proc = MockControllableProcess(delay=10.0)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # 1. Trigger job
            res1 = await self.client.post("/trigger-pipeline", json={"event": "JobToCancel"})
            self.assertEqual(res1.status_code, 202)
            job1_id = res1.json()["job_id"]

            # Give background task a microtick to spawn process
            await asyncio.sleep(0.01)

            # Verify running
            status_before = (await self.client.get("/status")).json()
            self.assertTrue(status_before["is_running"])
            self.assertEqual(status_before["current_job_id"], job1_id)

            # 2. Cancel job
            res_cancel = await self.client.post("/cancel")
            self.assertEqual(res_cancel.status_code, 200)
            cancel_data = res_cancel.json()
            self.assertEqual(cancel_data["status"], "cancelled")
            self.assertEqual(cancel_data["job_id"], job1_id)
            self.assertTrue(cancel_data["terminated"])
            self.assertTrue(mock_proc._terminated)

            # Verify status is now idle and cancelled
            status_after = (await self.client.get("/status")).json()
            self.assertFalse(status_after["is_running"])
            self.assertIsNone(status_after["current_job_id"])
            self.assertEqual(status_after["last_job"]["state"], "cancelled")

            # 3. Immediately trigger a second job to prove lock is released
            mock_proc2 = MockControllableProcess(exit_code=0, delay=0.01)
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc2):
                res2 = await self.client.post("/trigger-pipeline", json={"event": "ReplacementJob"})
                self.assertEqual(res2.status_code, 202)
                job2_id = res2.json()["job_id"]
                self.assertNotEqual(job1_id, job2_id)

    async def test_cancel_when_idle_returns_400(self):
        """Calling /cancel when idle must return 400 Bad Request."""
        res = await self.client.post("/cancel")
        self.assertEqual(res.status_code, 400)
        self.assertIn("No active pipeline job", res.json()["detail"])

    # ------------------------------------------------------------------------
    # 5. LOG BUFFER OVERFLOW & TAIL TRUNCATION
    # ------------------------------------------------------------------------
    async def test_log_buffer_overflow_and_max_capacity(self):
        """Inject 10,000 log entries into buffer (max capacity 2,000) and verify bounded memory."""
        total_injected = 10000
        for i in range(total_injected):
            self.manager._add_log(LogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                level="INFO" if i % 10 != 0 else "ERROR",
                message=f"Log sequence payload line #{i}",
                job_id=f"job_{i % 5}",
            ))

        # 1. Verify buffer size is strictly clamped to maxlen (2000)
        self.assertEqual(len(self.manager._log_buffer), 2000)

        # 2. Verify the oldest retained entry is line #8000
        first_retained = self.manager._log_buffer[0]
        self.assertIn("Log sequence payload line #8000", first_retained.message)
        last_retained = self.manager._log_buffer[-1]
        self.assertIn("Log sequence payload line #9999", last_retained.message)

        # 3. Test GET /logs?tail=50 returns exact latest 50 lines
        res_50 = await self.client.get("/logs?tail=50")
        self.assertEqual(res_50.status_code, 200)
        data_50 = res_50.json()
        self.assertEqual(data_50["total_lines"], 50)
        self.assertEqual(len(data_50["entries"]), 50)
        self.assertIn("Log sequence payload line #9999", data_50["logs"][-1])
        self.assertIn("Log sequence payload line #9950", data_50["logs"][0])

        # 4. Test GET /logs?tail=5000 requests more than buffer; should cap at 2000
        res_all = await self.client.get("/logs?tail=5000")
        self.assertEqual(res_all.status_code, 200)
        data_all = res_all.json()
        self.assertEqual(data_all["total_lines"], 2000)

        # 5. Test job_id filter on wrapped ring buffer
        res_job1 = await self.client.get("/logs?job_id=job_1&tail=100")
        self.assertEqual(res_job1.status_code, 200)
        data_job1 = res_job1.json()
        self.assertTrue(all(e["job_id"] == "job_1" for e in data_job1["entries"]))

    # ------------------------------------------------------------------------
    # 6. SUBPROCESS FAILURE & STDERR STREAMING
    # ------------------------------------------------------------------------
    async def test_subprocess_crash_with_stderr_capture(self):
        """Process exits non-zero; verify stderr captured with [STDERR] prefix and telemetry updated."""
        mock_proc = MockControllableProcess(
            exit_code=127,
            stdout_lines=[b"Starting pipeline\n"],
            stderr_lines=[b"FFmpeg crashed with SIGSEGV\n", b"Fatal memory allocation error\n"]
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            res = await self.client.post("/trigger-pipeline", json={"event": "CrashEvent"})
            self.assertEqual(res.status_code, 202)
            job_id = res.json()["job_id"]

            await asyncio.sleep(0.05)

            job = self.manager.find_job(job_id)
            self.assertIsNotNone(job)
            self.assertEqual(job.state, JobState.FAILED)
            self.assertEqual(job.exit_code, 127)
            self.assertIn("non-zero exit code: 127", job.error_summary)

            logs = (await self.client.get(f"/logs?job_id={job_id}")).json()
            stderr_logs = [l for l in logs["logs"] if "[STDERR]" in l]
            self.assertEqual(len(stderr_logs), 2)
            self.assertIn("FFmpeg crashed with SIGSEGV", stderr_logs[0])

    async def test_subprocess_creation_exception_gracefully_handled(self):
        """If create_subprocess_exec throws FileNotFoundError/OSError, lock is released and state = FAILED."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("No such binary")):
            res = await self.client.post("/trigger-pipeline", json={"event": "MissingBinaryEvent"})
            self.assertEqual(res.status_code, 202)
            job_id = res.json()["job_id"]

            await asyncio.sleep(0.05)

            job = self.manager.find_job(job_id)
            self.assertIsNotNone(job)
            self.assertEqual(job.state, JobState.FAILED)
            self.assertIn("No such binary", job.error_summary)

            status_res = (await self.client.get("/status")).json()
            self.assertFalse(status_res["is_running"])
            self.assertIsNone(status_res["current_job_id"])

    # ------------------------------------------------------------------------
    # 7. HEALTH, TELEMETRY & ALIASES
    # ------------------------------------------------------------------------
    async def test_health_states(self):
        """Verify health checks: healthy, degraded (no adb), unhealthy (no ffmpeg/ffprobe)."""
        with patch("remote_trigger.find_binary", return_value=Path("/bin/mock")), \
             patch("remote_trigger.find_adb_binary", return_value=Path("/bin/adb")):
            r = await self.client.get("/health")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["status"], "healthy")

        with patch("remote_trigger.find_binary", return_value=Path("/bin/mock")), \
             patch("remote_trigger.find_adb_binary", return_value=None):
            r = await self.client.get("/health")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["status"], "degraded")

        with patch("remote_trigger.find_binary", return_value=None), \
             patch("remote_trigger.find_adb_binary", return_value=None):
            r = await self.client.get("/health")
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.json()["status"], "unhealthy")

    async def test_specific_job_status_404(self):
        """Querying nonexistent job must return 404."""
        r = await self.client.get("/status/job_invalid_id")
        self.assertEqual(r.status_code, 404)
        self.assertIn("not found", r.json()["detail"].lower())

    def test_schema_aliases(self):
        """Verify backward compatibility aliases."""
        self.assertIs(PipelineTriggerResponse, TriggerResponse)
        self.assertIs(PipelineConflictResponse, ConflictResponse)
        self.assertIs(JobDetail, JobTelemetry)
        self.assertIs(JobStatusResponse, StatusResponse)
        self.assertIs(CancelJobResponse, CancelResponse)


if __name__ == "__main__":
    unittest.main(verbosity=2)
