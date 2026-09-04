import asyncio
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

content_dir = Path(r"G:\My Drive\GOOGLE ANTIGRAVITY\content_creation").resolve()
sys.path.insert(0, str(content_dir))

from fastapi.testclient import TestClient
from remote_trigger import create_app, PipelineJobManager, JobState, JobRecord
from samsung_ingest import extract_ip_address, ADBMDNSDiscovery, parse_service_properties

class TestAdversarialVictoryStress(unittest.TestCase):
    def setUp(self):
        self.app = create_app(workspace_root=content_dir)
        self.client = TestClient(self.app)

    @patch("remote_trigger.PipelineJobManager._run_subprocess", new_callable=AsyncMock)
    def test_concurrency_mutex_lock(self, mock_subproc):
        """Stress test simultaneous requests to trigger-pipeline."""
        manager = self.app.state.job_manager
        # Simulate active job in RUNNING state with valid datetime
        mock_job = JobRecord(
            job_id="job_test_123",
            command=["python", "orchestrator.py"],
            params={},
        )
        mock_job.state = JobState.RUNNING
        mock_job.started_at = datetime.now(timezone.utc)
        manager._active_job = mock_job

        payload = {
            "event": "AdversarialConcert",
            "artist": "TestDJ",
            "track": "StressTest",
            "dry_run": True,
        }
        res = self.client.post("/trigger-pipeline", json=payload)
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["status"], "conflict")

    def test_mdns_malformed_byte_arrays(self):
        """Verify extract_ip_address handles corrupted, partial, or huge byte sequences."""
        class CorruptedInfo:
            addresses = [b"\x00\x01", b"\xff\xff\xff\xff\xff\xff", "not-bytes", None, b""]
            address = None
            def parsed_addresses(self):
                raise RuntimeError("DNS parser crashed")
        
        ip = extract_ip_address(CorruptedInfo())
        self.assertIsNone(ip)

    def test_mdns_zeroconf_missing_fallback(self):
        """Verify discovery handles absence of zeroconf gracefully."""
        discovery = ADBMDNSDiscovery(timeout_sec=0.01)
        with patch("samsung_ingest.Zeroconf", None), patch.dict(sys.modules, {"zeroconf": None}):
            services = discovery.discover_services()
            self.assertEqual(services, [])

    def test_tasker_pydantic_schema_strictness(self):
        """Test that invalid request payloads return 422 Unprocessable Entity."""
        res = self.client.post("/trigger-pipeline", json={"drop_duration": 1000.0}) # exceeds ge=5.0, le=59.0
        self.assertEqual(res.status_code, 422)

if __name__ == "__main__":
    unittest.main()
