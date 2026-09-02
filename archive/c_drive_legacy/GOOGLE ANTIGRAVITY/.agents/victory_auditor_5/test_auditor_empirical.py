import os
import sys
import unittest
import xml.etree.ElementTree as ET
import re
from pathlib import Path

# Add content_creation to sys.path
content_dir = Path(r"G:\My Drive\GOOGLE ANTIGRAVITY\content_creation").resolve()
sys.path.insert(0, str(content_dir))

class TestTaskerXMLAndProfile(unittest.TestCase):
    def test_xml_blocks_in_tasker_profile(self):
        doc_path = content_dir / "tasker_profile.md"
        self.assertTrue(doc_path.exists(), "tasker_profile.md must exist")
        
        content = doc_path.read_text(encoding="utf-8")
        xml_blocks = re.findall(r"```xml\s*(<\?xml.*?\?>)?\s*(<TaskerData.*?</TaskerData>)\s*```", content, re.DOTALL)
        self.assertGreaterEqual(len(xml_blocks), 1, "Must contain at least one TaskerData XML block")
        
        for idx, (header, block) in enumerate(xml_blocks, 1):
            try:
                root = ET.fromstring(block)
                self.assertEqual(root.tag, "TaskerData")
            except ET.ParseError as e:
                self.fail(f"XML Block {idx} failed to parse: {e}")

    def test_tasker_action_339_parameters(self):
        doc_path = content_dir / "tasker_profile.md"
        content = doc_path.read_text(encoding="utf-8")
        
        # Verify Action 339 (HTTP Request), path /trigger-pipeline, Content-Type, and 202 check
        self.assertIn("339", content, "Tasker XML must include Action Code 339 (HTTP Request)")
        self.assertIn("/trigger-pipeline", content, "Must target /trigger-pipeline endpoint")
        self.assertIn("application/json", content, "Must include application/json Content-Type")
        self.assertIn("202", content, "Must evaluate HTTP 202 Accepted status")

class TestMDNSExtractionEmpirical(unittest.TestCase):
    def test_extract_ip_address_variants(self):
        from samsung_ingest import extract_ip_address
        
        class MockInfo1:
            def parsed_addresses(self):
                return ["192.168.1.145"]
        
        class MockInfo2:
            addresses = [b"\xc0\xa8\x01\x91"] # 192.168.1.145
        
        class MockInfo3:
            address = b"\x0a\x00\x00\x02" # 10.0.0.2
            addresses = []
            def parsed_addresses(self):
                return []
                
        self.assertEqual(extract_ip_address(MockInfo1()), "192.168.1.145")
        self.assertEqual(extract_ip_address(MockInfo2()), "192.168.1.145")
        self.assertEqual(extract_ip_address(MockInfo3()), "10.0.0.2")

class TestFastAPIRemoteTriggerEmpirical(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from remote_trigger import create_app
        self.app = create_app(workspace_root=content_dir)
        self.client = TestClient(self.app)

    def test_health_endpoint(self):
        res = self.client.get("/health")
        self.assertIn(res.status_code, [200, 503])
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("free_disk_space_bytes", data)

    def test_status_endpoint(self):
        res = self.client.get("/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("state", data)
        self.assertIn("is_running", data)
        self.assertIn("total_jobs_run", data)

    def test_trigger_pipeline_dry_run(self):
        payload = {
            "event": "EDC Vegas",
            "artist": "Illenium",
            "track": "Starfall",
            "dry_run": True
        }
        res = self.client.post("/trigger-pipeline", json=payload)
        self.assertIn(res.status_code, [202, 409])
        data = res.json()
        self.assertIn("status", data)
        if res.status_code == 202:
            self.assertEqual(data["status"], "accepted")
            self.assertTrue(data["job_id"].startswith("job_"))

if __name__ == "__main__":
    unittest.main()
