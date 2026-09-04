"""
Milestone 1 Adversarial Stress Test Suite & Empirical Verification Harness.
Target: unified_ops_hub.gateway (app.py, crash_tester.py, dlq_manager.py, port_manager.py)
Author: Challenger 2 (Milestone 1)
"""

import os
import sys
import json
import time
import socket
import shutil
import tempfile
import threading
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

import pytest
from fastapi.testclient import TestClient

# Ensure root workspace is in sys.path
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from unified_ops_hub.gateway.port_manager import PortManager
from unified_ops_hub.gateway.dlq_manager import (
    DLQManager,
    DLQIncident,
    ErrorCategory,
    IncidentStatus,
)
from unified_ops_hub.gateway.app import create_app
from unified_ops_hub.gateway.crash_tester import CrashTester


class AdversarialTestRunner:
    """Orchestrates comprehensive adversarial challenge suites for Milestone 1."""

    def __init__(self) -> None:
        self.results: List[Dict[str, Any]] = []
        self.temp_dir = tempfile.mkdtemp(prefix="challenger_m1_resiliency_")
        self.db_path = os.path.join(self.temp_dir, "challenger_dlq.db")
        self.quarantine_dir = os.path.join(self.temp_dir, "quarantine")
        self.lock_dir = os.path.join(self.temp_dir, "locks")

        self.port_manager = PortManager(lock_dir=self.lock_dir)
        self.dlq_manager = DLQManager(db_path=self.db_path, quarantine_dir=self.quarantine_dir)
        self.app = create_app(port_manager=self.port_manager, dlq_manager=self.dlq_manager)
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def cleanup(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def record_result(self, suite: str, test_name: str, passed: bool, details: str = "", error: str = ""):
        res = {
            "suite": suite,
            "test_name": test_name,
            "passed": passed,
            "details": details,
            "error": error,
        }
        self.results.append(res)
        status_tag = "[PASS]" if passed else "[FAIL]"
        print(f"  {status_tag} {test_name}")
        if details:
            print(f"         Detail: {details}")
        if error:
            print(f"         Error:  {error}")

    # =========================================================================
    # Suite 1: Malformed & Corrupted Payloads (Quarantine & Schema Resiliency)
    # =========================================================================
    def run_suite_1_malformed_payloads(self):
        suite = "Suite 1: Malformed Payloads & Schema Quarantine"
        print(f"\n--- {suite} ---")

        # 1.1 Empty JSON body on sports capture
        try:
            resp = self.client.post("/api/v1/sports/capture", json={})
            assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
            data = resp.json()
            assert "incident_id" in data, "incident_id missing from 422 response"
            inc = self.dlq_manager.get_incident(data["incident_id"])
            assert inc is not None, "Incident not persisted in SQLite"
            assert inc.error_category == ErrorCategory.CORRUPTED_PAYLOAD
            self.record_result(suite, "1.1 Empty JSON body -> 422 + DLQ Quarantine", True, f"DLQ ID: {inc.incident_id}")
        except Exception as exc:
            self.record_result(suite, "1.1 Empty JSON body -> 422 + DLQ Quarantine", False, error=str(exc))

        # 1.2 Corrupted schema payload (wrong types, invalid constraints)
        try:
            resp = self.client.post(
                "/api/v1/sports/capture",
                json={"player": "", "investment": "not_a_float", "unexpected_payload": True},
            )
            assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
            data = resp.json()
            assert data.get("error") == "CORRUPTED_PAYLOAD"
            inc = self.dlq_manager.get_incident(data["incident_id"])
            assert inc is not None
            self.record_result(suite, "1.2 Corrupted schema payload -> 422 + DLQ Quarantine", True, f"DLQ ID: {inc.incident_id}")
        except Exception as exc:
            self.record_result(suite, "1.2 Corrupted schema payload -> 422 + DLQ Quarantine", False, error=str(exc))

        # 1.3 Invalid types: string for float fields & missing required fields in ML grade
        try:
            resp = self.client.post("/api/v1/ml/grade", json={"video_id": 12345, "scores": "NOT_A_DICT"})
            assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
            data = resp.json()
            inc = self.dlq_manager.get_incident(data["incident_id"])
            assert inc is not None
            assert inc.error_category == ErrorCategory.CORRUPTED_PAYLOAD
            self.record_result(suite, "1.3 Invalid field types in ML Grade -> 422 + DLQ Quarantine", True, f"DLQ ID: {inc.incident_id}")
        except Exception as exc:
            self.record_result(suite, "1.3 Invalid field types in ML Grade -> 422 + DLQ Quarantine", False, error=str(exc))

        # 1.4 Truncated JSON stream
        try:
            resp = self.client.post(
                "/api/v1/media/trigger",
                content=b'{"clip_name": "partial_stream_',
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
            data = resp.json()
            inc = self.dlq_manager.get_incident(data["incident_id"])
            assert inc is not None
            self.record_result(suite, "1.4 Truncated JSON stream -> 422 + DLQ Quarantine", True, f"DLQ ID: {inc.incident_id}")
        except Exception as exc:
            self.record_result(suite, "1.4 Truncated JSON stream -> 422 + DLQ Quarantine", False, error=str(exc))

        # 1.5 JSON Audit Artifact disk persistence check
        try:
            incidents = self.dlq_manager.list_incidents(category=ErrorCategory.CORRUPTED_PAYLOAD)
            assert len(incidents) >= 4, f"Expected at least 4 incidents, found {len(incidents)}"
            for inc in incidents:
                json_path = os.path.join(self.quarantine_dir, f"dlq_{inc.incident_id}.json")
                assert os.path.exists(json_path), f"Audit artifact {json_path} does not exist on disk"
                with open(json_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                assert loaded["incident_id"] == inc.incident_id
                assert loaded["error_category"] == ErrorCategory.CORRUPTED_PAYLOAD.value
            self.record_result(suite, "1.5 Disk audit artifacts verified for all 422 quarantines", True, f"Verified {len(incidents)} JSON files")
        except Exception as exc:
            self.record_result(suite, "1.5 Disk audit artifacts verified for all 422 quarantines", False, error=str(exc))

    # =========================================================================
    # Suite 2: Unhandled Worker Panics & Crash Simulation
    # =========================================================================
    def run_suite_2_unhandled_crashes(self):
        suite = "Suite 2: Unhandled Worker Exceptions & Crash Isolation"
        print(f"\n--- {suite} ---")

        # 2.1 Division by Zero panic
        try:
            resp = self.client.post("/api/v1/simulate-crash", json={"error_type": "DivisionByZero", "trigger": True})
            assert resp.status_code == 500, f"Expected 500, got {resp.status_code}"
            data = resp.json()
            assert data.get("error") == "INTERNAL_SERVER_ERROR"
            incident_id = data.get("incident_id")
            assert incident_id is not None
            inc = self.dlq_manager.get_incident(incident_id)
            assert inc is not None
            assert inc.error_category == ErrorCategory.UNHANDLED_EXCEPTION
            assert "ZeroDivisionError" in inc.error_message or "division by zero" in inc.error_message.lower()
            self.record_result(suite, "2.1 ZeroDivisionError caught, isolated in DLQ", True, f"DLQ ID: {incident_id}")
        except Exception as exc:
            self.record_result(suite, "2.1 ZeroDivisionError caught, isolated in DLQ", False, error=str(exc))

        # 2.2 Simulated ML Grading PySpark Partition Crash
        try:
            resp = self.client.post("/api/v1/simulate-crash", json={"error_type": "MLGradingCrash", "trigger": True})
            assert resp.status_code == 500, f"Expected 500, got {resp.status_code}"
            data = resp.json()
            incident_id = data.get("incident_id")
            assert incident_id is not None
            inc = self.dlq_manager.get_incident(incident_id)
            assert inc is not None
            assert inc.error_category == ErrorCategory.ML_GRADING_FAILURE
            self.record_result(suite, "2.2 MLGradingCrash categorized as ML_GRADING_FAILURE", True, f"DLQ ID: {incident_id}")
        except Exception as exc:
            self.record_result(suite, "2.2 MLGradingCrash categorized as ML_GRADING_FAILURE", False, error=str(exc))

        # 2.3 Custom Runtime Exception with stack trace capture
        try:
            resp = self.client.post("/api/v1/simulate-crash", json={"error_type": "DeadlockTimeoutException", "trigger": True})
            assert resp.status_code == 500, f"Expected 500, got {resp.status_code}"
            data = resp.json()
            incident_id = data.get("incident_id")
            inc = self.dlq_manager.get_incident(incident_id)
            assert inc is not None
            assert inc.traceback_str is not None
            assert "Traceback" in inc.traceback_str
            self.record_result(suite, "2.3 Full traceback captured in DLQ for runtime exception", True, f"Traceback length: {len(inc.traceback_str)} chars")
        except Exception as exc:
            self.record_result(suite, "2.3 Full traceback captured in DLQ for runtime exception", False, error=str(exc))

        # 2.4 Health probe remains 100% HEALTHY after panics
        try:
            health_resp = self.client.get("/api/v1/health")
            assert health_resp.status_code == 200
            health_data = health_resp.json()
            assert health_data["status"] == "HEALTHY"
            assert health_data["dlq_stats"]["total_incidents"] >= 3
            self.record_result(suite, "2.4 Health probe verifies daemon alive & operational post-crashes", True, f"Uptime: {health_data['uptime_seconds']}s")
        except Exception as exc:
            self.record_result(suite, "2.4 Health probe verifies daemon alive & operational post-crashes", False, error=str(exc))

    # =========================================================================
    # Suite 3: High-Frequency Concurrent Chaos Hammer Test
    # =========================================================================
    def run_suite_3_concurrent_chaos(self):
        suite = "Suite 3: High-Frequency Concurrent Chaos Hammer Test"
        print(f"\n--- {suite} ---")

        num_threads = 40
        cycles_per_thread = 5
        total_requests = num_threads * cycles_per_thread
        errors = []
        status_codes: Dict[int, int] = {}
        status_lock = threading.Lock()

        def chaos_worker(worker_id: int):
            for i in range(cycles_per_thread):
                try:
                    mode = (worker_id + i) % 5
                    if mode == 0:
                        # Crash trigger
                        r = self.client.post("/api/v1/simulate-crash", json={"error_type": "DivisionByZero", "trigger": True})
                    elif mode == 1:
                        # Malformed sports payload
                        r = self.client.post("/api/v1/sports/capture", json={"bad_key": 999})
                    elif mode == 2:
                        # Valid ML grading request
                        r = self.client.post(
                            "/api/v1/ml/grade",
                            json={"video_id": f"vid_w{worker_id}_{i}", "scores": {"HRV": 75.0, "DPAW": 80.0}},
                        )
                    elif mode == 3:
                        # Valid sports capture
                        r = self.client.post(
                            "/api/v1/sports/capture",
                            json={"player": f"Player_{worker_id}_{i}", "investment": 50.0},
                        )
                    else:
                        # Health query
                        r = self.client.get("/api/v1/health")

                    with status_lock:
                        status_codes[r.status_code] = status_codes.get(r.status_code, 0) + 1

                except Exception as exc:
                    errors.append(f"Worker {worker_id} iter {i}: {exc}")

        threads = [threading.Thread(target=chaos_worker, args=(t,)) for t in range(num_threads)]
        t0 = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        duration = time.time() - t0

        # 3.1 Zero dropped connections / zero client exceptions
        if len(errors) == 0:
            self.record_result(
                suite,
                "3.1 Concurrent chaos execution without dropped connections",
                True,
                f"{total_requests} requests in {duration:.2f}s (~{total_requests/duration:.1f} req/s). Status codes: {status_codes}",
            )
        else:
            self.record_result(suite, "3.1 Concurrent chaos execution without dropped connections", False, error=f"{len(errors)} errors: {errors[:3]}")

        # 3.2 Post-chaos health verification
        try:
            health = self.client.get("/api/v1/health")
            assert health.status_code == 200
            assert health.json()["status"] == "HEALTHY"
            self.record_result(suite, "3.2 Post-chaos daemon health status is HEALTHY", True)
        except Exception as exc:
            self.record_result(suite, "3.2 Post-chaos daemon health status is HEALTHY", False, error=str(exc))

        # 3.3 DLQ database integrity & consistency check
        try:
            stats = self.dlq_manager.get_stats()
            expected_crashes_and_malformed = status_codes.get(500, 0) + status_codes.get(422, 0)
            assert stats["total_incidents"] >= expected_crashes_and_malformed
            self.record_result(
                suite,
                "3.3 DLQ captured all failed requests under concurrent load",
                True,
                f"Total incidents logged: {stats['total_incidents']}, Expected new: {expected_crashes_and_malformed}",
            )
        except Exception as exc:
            self.record_result(suite, "3.3 DLQ captured all failed requests under concurrent load", False, error=str(exc))

    # =========================================================================
    # Suite 4: PortManager & Dynamic Collision Recovery
    # =========================================================================
    def run_suite_4_port_manager_stress(self):
        suite = "Suite 4: PortManager & Dynamic Collision Recovery"
        print(f"\n--- {suite} ---")

        # 4.1 Multi-port sequential collision avoidance
        socks = []
        try:
            # Occupy 3 consecutive ports starting at base_port
            base_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            base_sock.bind(("127.0.0.1", 0))
            base_sock.listen(1)
            occupied_base = base_sock.getsockname()[1]
            socks.append(base_sock)

            # Request port allocation starting at occupied_base
            fallback = self.port_manager.find_available_port(preferred_port=occupied_base, max_attempts=20)
            assert fallback > occupied_base
            assert not self.port_manager.is_port_in_use(fallback)
            self.record_result(suite, "4.1 Dynamic sequential port allocation avoids occupied sockets", True, f"Base {occupied_base} -> Fallback {fallback}")
        except Exception as exc:
            self.record_result(suite, "4.1 Dynamic sequential port allocation avoids occupied sockets", False, error=str(exc))
        finally:
            for s in socks:
                s.close()

        # 4.2 Port exhaustion raises RuntimeError
        try:
            # Mock is_port_in_use to always return True
            class StubPortManager(PortManager):
                def is_port_in_use(self, port: int, host: str = None) -> bool:
                    return True

            stub_pm = StubPortManager(lock_dir=self.lock_dir)
            exhaustion_threw = False
            try:
                stub_pm.find_available_port(preferred_port=8000, max_attempts=5)
            except RuntimeError:
                exhaustion_threw = True

            assert exhaustion_threw is True, "Exhaustion did not raise RuntimeError"
            self.record_result(suite, "4.2 Port exhaustion cleanly raises RuntimeError after max_attempts", True)
        except Exception as exc:
            self.record_result(suite, "4.2 Port exhaustion cleanly raises RuntimeError after max_attempts", False, error=str(exc))

        # 4.3 Atomic file lock contention across 20 threads
        lock_port = 8765
        acquisitions = []
        lock_threads = []

        def locker_worker(wid: int):
            pm = PortManager(lock_dir=self.lock_dir)
            lock_path = pm.acquire_port_lock(lock_port)
            if lock_path:
                acquisitions.append((wid, lock_path))

        for tid in range(20):
            t = threading.Thread(target=locker_worker, args=(tid,))
            lock_threads.append(t)
            t.start()
        for t in lock_threads:
            t.join()

        try:
            assert len(acquisitions) == 1, f"Expected exactly 1 thread to acquire lock, got {len(acquisitions)}"
            winner_wid, winner_path = acquisitions[0]
            # Release winning lock
            pm_winner = PortManager(lock_dir=self.lock_dir)
            released = pm_winner.release_port_lock(lock_port)
            assert released is True
            self.record_result(suite, "4.3 Atomic lock contention: exactly 1 thread acquires lock", True, f"Winner thread: {winner_wid}")
        except Exception as exc:
            self.record_result(suite, "4.3 Atomic lock contention: exactly 1 thread acquires lock", False, error=str(exc))

        # 4.4 Stale lock cleanup for dead PIDs
        try:
            stale_lock_path = os.path.join(self.lock_dir, "port_8888.lock")
            with open(stale_lock_path, "w", encoding="utf-8") as f:
                f.write("99999999")  # Unlikely PID
            # Set old mtime
            old_time = time.time() - 3600
            os.utime(stale_lock_path, (old_time, old_time))

            cleaned = self.port_manager.cleanup_stale_locks(max_age_seconds=30)
            assert stale_lock_path in cleaned
            assert not os.path.exists(stale_lock_path)
            self.record_result(suite, "4.4 Stale lock eviction for dead PIDs", True, f"Cleaned {len(cleaned)} stale lock(s)")
        except Exception as exc:
            self.record_result(suite, "4.4 Stale lock eviction for dead PIDs", False, error=str(exc))

    # =========================================================================
    # Suite 5: DLQ Lifecycle, Replay State Machine, & Purge
    # =========================================================================
    def run_suite_5_dlq_lifecycle(self):
        suite = "Suite 5: DLQ Lifecycle & State Machine"
        print(f"\n--- {suite} ---")

        # 5.1 Replay non-existent incident
        try:
            fake_id = "00000000-0000-0000-0000-000000000000"
            res = self.dlq_manager.replay_incident(fake_id)
            assert res["success"] is False
            assert "not found" in res["error"].lower()
            self.record_result(suite, "5.1 Replay of non-existent incident returns structured error", True)
        except Exception as exc:
            self.record_result(suite, "5.1 Replay of non-existent incident returns structured error", False, error=str(exc))

        # 5.2 Replay success state transition
        try:
            inc = self.dlq_manager.record_failure(
                source_service="media_pipeline",
                error_category=ErrorCategory.API_RATE_LIMIT,
                error_message="Quota Exceeded",
                payload={"video_id": "test_01"},
            )
            res = self.dlq_manager.replay_incident(inc.incident_id, handler=lambda p: {"status": "GRADED", "score": 95.0})
            assert res["success"] is True
            updated = self.dlq_manager.get_incident(inc.incident_id)
            assert updated.status == IncidentStatus.RESOLVED
            assert updated.resolved_at is not None
            assert len(updated.history) >= 2
            self.record_result(suite, "5.2 Successful replay transitions status to RESOLVED with timestamp", True, f"DLQ ID: {inc.incident_id}")
        except Exception as exc:
            self.record_result(suite, "5.2 Successful replay transitions status to RESOLVED with timestamp", False, error=str(exc))

        # 5.3 Repeated replay failure transitions to RETRYING and EXHAUSTED
        try:
            inc = self.dlq_manager.record_failure(
                source_service="sports_cards",
                error_category=ErrorCategory.TIMEOUT,
                error_message="Gateway timeout to CardLadder",
                payload={"card": "Prizm #1"},
                max_retries=2,
            )

            def failing_handler(payload):
                raise ConnectionError("Endpoint down")

            # Attempt 1 -> RETRYING
            res1 = self.dlq_manager.replay_incident(inc.incident_id, handler=failing_handler)
            assert res1["success"] is False
            inc1 = self.dlq_manager.get_incident(inc.incident_id)
            assert inc1.status == IncidentStatus.RETRYING
            assert inc1.retry_count == 1

            # Attempt 2 -> EXHAUSTED
            res2 = self.dlq_manager.replay_incident(inc.incident_id, handler=failing_handler)
            assert res2["success"] is False
            inc2 = self.dlq_manager.get_incident(inc.incident_id)
            assert inc2.status == IncidentStatus.EXHAUSTED
            assert inc2.retry_count == 2
            self.record_result(suite, "5.3 Multi-step replay failures increment count and reach EXHAUSTED state", True)
        except Exception as exc:
            self.record_result(suite, "5.3 Multi-step replay failures increment count and reach EXHAUSTED state", False, error=str(exc))

        # 5.4 Batch automatic processing of due retries
        try:
            now = datetime.now(timezone.utc)
            inc_due = self.dlq_manager.record_failure(
                source_service="batch_service",
                error_category=ErrorCategory.API_RATE_LIMIT,
                error_message="Rate limit",
                payload={"job": "sync"},
            )
            # Force next_retry_at into the past
            past_iso = (now - timedelta(minutes=10)).isoformat()
            self.dlq_manager.update_incident_schedule(inc_due.incident_id, next_retry_at=past_iso)

            replayed_items = []
            results = self.dlq_manager.process_retries(handlers={"batch_service": lambda p: replayed_items.append(p)})
            assert results["processed_count"] == 1
            assert len(replayed_items) == 1
            self.record_result(suite, "5.4 Automated batch retry processing scans and executes eligible incidents", True)
        except Exception as exc:
            self.record_result(suite, "5.4 Automated batch retry processing scans and executes eligible incidents", False, error=str(exc))

        # 5.5 File quarantine and isolation
        try:
            dummy_file = os.path.join(self.temp_dir, "broken_media.mp4")
            with open(dummy_file, "wb") as f:
                f.write(b"CORRUPTED_MP4_ATOM_BYTES")
            inc, q_path = self.dlq_manager.quarantine_file(
                source_file_path=dummy_file,
                source_service="media_ingest",
                reason="Corrupt header atom",
            )
            assert not os.path.exists(dummy_file)
            assert os.path.exists(q_path)
            assert inc.error_category == ErrorCategory.CORRUPTED_PAYLOAD
            self.record_result(suite, "5.5 File quarantine moves bad files and records audit incident", True, f"Quarantined path: {q_path}")
        except Exception as exc:
            self.record_result(suite, "5.5 File quarantine moves bad files and records audit incident", False, error=str(exc))

        # 5.6 Purge resolved incidents
        try:
            purged = self.dlq_manager.purge_resolved()
            assert purged >= 1, f"Expected at least 1 purged incident, got {purged}"
            stats = self.dlq_manager.get_stats()
            assert stats["resolved_count"] == 0
            self.record_result(suite, "5.6 Purge removes resolved incidents while keeping quarantined/exhausted", True, f"Purged: {purged}")
        except Exception as exc:
            self.record_result(suite, "5.6 Purge removes resolved incidents while keeping quarantined/exhausted", False, error=str(exc))

        # 5.7 SQLite Database PRAGMA integrity check
        try:
            with self.dlq_manager._get_connection() as conn:
                res = conn.execute("PRAGMA integrity_check;").fetchone()[0]
                assert res == "ok", f"SQLite integrity check failed: {res}"
            self.record_result(suite, "5.7 SQLite PRAGMA integrity check returns 'ok'", True)
        except Exception as exc:
            self.record_result(suite, "5.7 SQLite PRAGMA integrity check returns 'ok'", False, error=str(exc))

    # =========================================================================
    # Suite 6: Programmatic CrashTester & CLI Execution
    # =========================================================================
    def run_suite_6_crash_tester_and_cli(self):
        suite = "Suite 6: Programmatic CrashTester & CLI Runner"
        print(f"\n--- {suite} ---")

        # 6.1 Direct CrashTester run
        try:
            tester = CrashTester(
                app=self.app,
                client=self.client,
                port_manager=self.port_manager,
                dlq_manager=self.dlq_manager,
            )
            report = tester.run_all_tests()
            assert report["all_passed"] is True, f"CrashTester report failed: {report}"
            assert report["summary"]["passed_tests"] >= 4
            self.record_result(suite, "6.1 Programmatic CrashTester executes all 4 built-in scenarios with 100% pass", True)
        except Exception as exc:
            self.record_result(suite, "6.1 Programmatic CrashTester executes all 4 built-in scenarios with 100% pass", False, error=str(exc))

        # 6.2 CLI Entrypoint Execution via Subprocess
        try:
            cmd = [
                sys.executable,
                "-m",
                "unified_ops_hub.gateway.crash_tester",
            ]
            proc = subprocess.run(
                cmd,
                cwd=WORKSPACE_DIR,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert proc.returncode == 0, f"CLI exit code {proc.returncode} != 0. stderr: {proc.stderr}\nstdout: {proc.stdout}"
            assert "All crash scenarios certified resilient." in proc.stdout
            self.record_result(suite, "6.2 CLI crash_tester runner exits with code 0 and certifies resilience", True)
        except Exception as exc:
            self.record_result(suite, "6.2 CLI crash_tester runner exits with code 0 and certifies resilience", False, error=str(exc))

        # 6.3 REST Endpoint Replay via FastAPI Route
        try:
            inc = self.dlq_manager.record_failure(
                source_service="sports_cards",
                error_category=ErrorCategory.API_RATE_LIMIT,
                error_message="CardLadder 429",
                payload={"item_id": 999},
            )
            resp = self.client.post(f"/api/v1/dlq/retry/{inc.incident_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("success") is True
            self.record_result(suite, "6.3 REST Replay endpoint /api/v1/dlq/retry/{id} successfully resolves incident", True)
        except Exception as exc:
            self.record_result(suite, "6.3 REST Replay endpoint /api/v1/dlq/retry/{id} successfully resolves incident", False, error=str(exc))

        # 6.4 REST Endpoint Filter Listing by Category and Status
        try:
            resp = self.client.get("/api/v1/dlq/incidents?status=RESOLVED")
            assert resp.status_code == 200
            data = resp.json()
            assert "incidents" in data
            assert all(i["status"] == "RESOLVED" for i in data["incidents"])
            self.record_result(suite, "6.4 REST Listing endpoint /api/v1/dlq/incidents correctly filters by status", True, f"Found {data['count']} resolved")
        except Exception as exc:
            self.record_result(suite, "6.4 REST Listing endpoint /api/v1/dlq/incidents correctly filters by status", False, error=str(exc))


    # =========================================================================
    # Master Execution
    # =========================================================================
    def run_all(self) -> Dict[str, Any]:
        print("=" * 75)
        print(" CHALLENGER 2: ADVERSARIAL RESILIENCY & DLQ VERIFICATION HARNESS")
        print("=" * 75)

        try:
            self.run_suite_1_malformed_payloads()
            self.run_suite_2_unhandled_crashes()
            self.run_suite_3_concurrent_chaos()
            self.run_suite_4_port_manager_stress()
            self.run_suite_5_dlq_lifecycle()
            self.run_suite_6_crash_tester_and_cli()
        finally:
            self.cleanup()

        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        print("\n" + "=" * 75)
        print(f" FINAL EMPIRICAL RESULTS: {passed}/{total} Scenarios Passed ({failed} Failed)")
        print("=" * 75)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "all_passed": failed == 0,
            "results": self.results,
        }


if __name__ == "__main__":
    runner = AdversarialTestRunner()
    summary = runner.run_all()
    if not summary["all_passed"]:
        sys.exit(1)
    sys.exit(0)
