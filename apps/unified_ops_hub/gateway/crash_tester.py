"""Programmatic Crash-Test Suite & CLI Chaos Runner.
Simulates real-world backend component failures (socket collisions, corrupted payloads,
simulated ML grading crashes) to verify daemon uptime and Dead Letter Queue isolation.
"""

import sys
import time
import socket
import logging
import argparse
from typing import Optional, Dict, Any, List
from fastapi.testclient import TestClient

from unified_ops_hub.gateway.port_manager import PortManager
from unified_ops_hub.gateway.dlq_manager import DLQManager, ErrorCategory, IncidentStatus
from unified_ops_hub.gateway.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("unified_ops_hub.crash_tester")


class CrashTester:
    """Programmatic verification suite simulating failure modes against the Gateway."""

    def __init__(
        self,
        app=None,
        client: Optional[TestClient] = None,
        port_manager: Optional[PortManager] = None,
        dlq_manager: Optional[DLQManager] = None,
    ) -> None:
        self.port_manager = port_manager or PortManager()
        self.dlq_manager = dlq_manager or DLQManager()
        self.app = app or create_app(port_manager=self.port_manager, dlq_manager=self.dlq_manager)
        self.client = client if client is not None else TestClient(self.app, raise_server_exceptions=False)

    def test_socket_collision_resilience(self) -> Dict[str, Any]:
        """Scenario 1: Simulates port collision and validates dynamic sequential rebinding."""
        test_name = "Socket Collision Resilience"
        logger.info("Executing Scenario: %s", test_name)
        
        # 1. Occupy a real TCP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        occupied_port = sock.getsockname()[1]

        try:
            # 2. Verify PortManager detects collision
            in_use = self.port_manager.is_port_in_use(occupied_port)
            if not in_use:
                return {"name": test_name, "passed": False, "error": f"Port {occupied_port} was not detected as in use."}

            # 3. Request port allocation starting at occupied_port
            fallback_port = self.port_manager.find_available_port(preferred_port=occupied_port, max_attempts=20)
            if fallback_port <= occupied_port or self.port_manager.is_port_in_use(fallback_port):
                return {
                    "name": test_name,
                    "passed": False,
                    "error": f"Fallback port {fallback_port} invalid or in use.",
                }

            return {
                "name": test_name,
                "passed": True,
                "details": f"Successfully detected collision on {occupied_port} and allocated fallback {fallback_port}.",
            }
        finally:
            sock.close()

    def test_corrupted_payload_quarantine(self) -> Dict[str, Any]:
        """Scenario 2: Sends malformed payload, verifies HTTP 422 and DLQ quarantine."""
        test_name = "Corrupted Payload Quarantine"
        logger.info("Executing Scenario: %s", test_name)
        
        # Missing required player name (min_length=1)
        corrupted_payload = {"player": "", "investment": "not_a_float"}
        resp = self.client.post("/api/v1/sports/capture", json=corrupted_payload)
        
        if resp.status_code != 422:
            return {
                "name": test_name,
                "passed": False,
                "error": f"Expected HTTP 422, received {resp.status_code}",
            }
            
        data = resp.json()
        incident_id = data.get("incident_id")
        if not incident_id:
            return {"name": test_name, "passed": False, "error": "No incident_id returned in 422 response."}

        # Inspect DLQ
        incident = self.dlq_manager.get_incident(incident_id)
        if not incident:
            return {"name": test_name, "passed": False, "error": f"Incident {incident_id} not found in DLQ database."}

        if incident.error_category != ErrorCategory.CORRUPTED_PAYLOAD:
            return {
                "name": test_name,
                "passed": False,
                "error": f"Expected category CORRUPTED_PAYLOAD, got {incident.error_category}",
            }

        return {
            "name": test_name,
            "passed": True,
            "details": f"Corrupted payload quarantined with DLQ ID {incident_id}.",
        }

    def test_ml_grading_crash_simulation(self) -> Dict[str, Any]:
        """Scenario 3: Triggers simulated PySpark/Gemini ML crash, verifies 500 + DLQ isolation and daemon uptime."""
        test_name = "ML Grading Crash Simulation"
        logger.info("Executing Scenario: %s", test_name)
        
        resp = self.client.post("/api/v1/simulate-crash", json={"error_type": "MLGradingCrash", "trigger": True})
        if resp.status_code != 500:
            return {
                "name": test_name,
                "passed": False,
                "error": f"Expected HTTP 500, received {resp.status_code}",
            }

        data = resp.json()
        incident_id = data.get("incident_id")
        if not incident_id:
            return {"name": test_name, "passed": False, "error": "No incident_id in 500 error response."}

        incident = self.dlq_manager.get_incident(incident_id)
        if not incident:
            return {"name": test_name, "passed": False, "error": f"Incident {incident_id} was not persisted in DLQ."}

        # Verify server remains healthy
        health = self.client.get("/api/v1/health")
        if health.status_code != 200 or health.json()["status"] != "HEALTHY":
            return {
                "name": test_name,
                "passed": False,
                "error": "Gateway daemon failed health check after simulated crash.",
            }

        return {
            "name": test_name,
            "passed": True,
            "details": f"ML crash safely caught, recorded in DLQ ({incident_id}), daemon remains healthy.",
        }

    def test_daemon_alive_under_chaos(self) -> Dict[str, Any]:
        """Scenario 4: Fires high-frequency chaos requests, asserts zero daemon downtime."""
        test_name = "Daemon Uptime Under Chaos"
        logger.info("Executing Scenario: %s", test_name)
        
        total_requests = 30
        failed_health_checks = 0

        for i in range(total_requests):
            if i % 3 == 0:
                # Trigger crash
                self.client.post("/api/v1/simulate-crash", json={"error_type": "DivisionByZero", "trigger": True})
            elif i % 3 == 1:
                # Corrupt payload
                self.client.post("/api/v1/sports/capture", json={"bad_field": 123})
            else:
                # Normal grade
                self.client.post(
                    "/api/v1/ml/grade",
                    json={"video_id": f"v_{i}", "scores": {"HRV": 90.0}, "aspect_ratio": "9:16"},
                )

            # Assert health check after each chaotic request
            h_resp = self.client.get("/api/v1/health")
            if h_resp.status_code != 200 or h_resp.json()["status"] != "HEALTHY":
                failed_health_checks += 1

        if failed_health_checks > 0:
            return {
                "name": test_name,
                "passed": False,
                "error": f"{failed_health_checks}/{total_requests} health probes failed during chaos run.",
            }

        return {
            "name": test_name,
            "passed": True,
            "details": f"All {total_requests} chaotic request cycles handled with 100% daemon availability.",
        }

    def run_all_tests(self) -> Dict[str, Any]:
        """Executes all crash-test scenarios and produces structured summary report."""
        test_methods = [
            self.test_socket_collision_resilience,
            self.test_corrupted_payload_quarantine,
            self.test_ml_grading_crash_simulation,
            self.test_daemon_alive_under_chaos,
        ]

        results: List[Dict[str, Any]] = []
        passed_count = 0

        for test_fn in test_methods:
            try:
                res = test_fn()
            except Exception as exc:
                res = {
                    "name": test_fn.__name__,
                    "passed": False,
                    "error": f"Unhandled exception in crash test: {str(exc)}",
                }
            results.append(res)
            if res.get("passed"):
                passed_count += 1

        all_passed = passed_count == len(test_methods)
        summary = {
            "total_tests": len(test_methods),
            "passed_tests": passed_count,
            "failed_tests": len(test_methods) - passed_count,
        }

        return {
            "all_passed": all_passed,
            "summary": summary,
            "results": results,
        }


def main():
    parser = argparse.ArgumentParser(description="Unified Ops Hub Gateway Crash-Tester CLI")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose log output")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 70)
    print(" UNIFIED OPS HUB - PROGRAMMATIC CRASH & RESILIENCY TEST RUNNER")
    print("=" * 70)

    tester = CrashTester()
    report = tester.run_all_tests()

    for idx, r in enumerate(report["results"], 1):
        status_str = "[PASS]" if r["passed"] else "[FAIL]"
        print(f"{idx}. {status_str} {r['name']}")
        if r["passed"]:
            print(f"   Detail: {r.get('details', '')}")
        else:
            print(f"   Error:  {r.get('error', '')}")

    print("-" * 70)
    print(f"Summary: {report['summary']['passed_tests']}/{report['summary']['total_tests']} tests passed.")
    print("=" * 70)

    if not report["all_passed"]:
        sys.exit(1)
    print("All crash scenarios certified resilient.")
    sys.exit(0)


if __name__ == "__main__":
    main()
