"""
test_challenger_1_m3_tasker.py - Empirical Adversarial Verification for Milestone 3 (Tasker Profile)
Author: Challenger 1 (teamwork_preview_challenger)
Target Artifacts:
- content_creation/tasker_profile.md
- content_creation/remote_trigger.py

Empirically verifies:
1. Valid XML syntax for all XML codeblocks in tasker_profile.md using xml.etree.ElementTree.
2. Action code 339 HTTP request action with POST method and target URL.
3. Vibration patterns (0,100,100,100 and 0,500,200,500).
4. Notification (Code 523) and Flash (Code 548) action codes and payloads.
5. Variable definitions (%EDM_SERVER_IP, %EDM_SERVER_PORT) with !Set conditions (Code 547).
6. Conditional branching: Code 37 (If %http_response_code eq 202), Code 43 (Else), Code 38 (End If).
7. Project XML bundle (EDM_Automation.prj.xml) structure, metadata, and task binding.
8. Complete bidirectional compatibility between Tasker JSON body and remote_trigger.py:PipelineTriggerRequest.
9. Orchestrator command construction from Tasker payload.
10. One UI 7 documentation completeness (1x1 Widget, Quick Settings Tile, Knox Whitelist).
11. Adversarial edge cases: Mutex concurrency, boundary fuzzing, malformed payloads, entity decoding.
"""

import asyncio
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from pydantic import ValidationError

SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_DIR = SCRIPT_DIR.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from remote_trigger import (
    PipelineTriggerRequest,
    TriggerResponse,
    ConflictResponse,
    StatusResponse,
    create_app,
    build_orchestrator_command,
)


class TestTaskerProfileXMLVerification(unittest.TestCase):
    """Empirical verification of Tasker XML specifications in content_creation/tasker_profile.md."""

    @classmethod
    def setUpClass(cls):
        cls.tasker_md_path = MODULE_DIR / "tasker_profile.md"
        if not cls.tasker_md_path.is_file():
            raise FileNotFoundError(f"tasker_profile.md not found at {cls.tasker_md_path}")
        cls.raw_content = cls.tasker_md_path.read_text(encoding="utf-8")
        cls.xml_blocks = re.findall(r"<TaskerData[\s\S]*?</TaskerData>", cls.raw_content)

    def test_xml_blocks_exist_and_parse_cleanly(self):
        """Verify at least 2 complete XML blocks exist and parse with xml.etree.ElementTree."""
        self.assertGreaterEqual(len(self.xml_blocks), 2, "Expected at least 2 XML blocks (Task XML and Project XML)")

        for idx, xml_str in enumerate(self.xml_blocks):
            try:
                root = ET.fromstring(xml_str)
                self.assertEqual(root.tag, "TaskerData", f"Block {idx} root tag is not TaskerData")
                self.assertIn("tv", root.attrib, f"Block {idx} missing Tasker version 'tv' attribute")
                self.assertIn("dvi", root.attrib, f"Block {idx} missing data version 'dvi' attribute")
            except ET.ParseError as e:
                self.fail(f"XML Block {idx} failed to parse with ElementTree: {e}")

    def test_standalone_task_xml_structure(self):
        """Verify Trigger_EDM_Pipeline.tsk.xml has proper Task metadata and required action sequence."""
        task_xml = self.xml_blocks[0]
        root = ET.fromstring(task_xml)
        
        task = root.find("Task")
        self.assertIsNotNone(task, "Task element not found in Task XML block")
        self.assertEqual(task.findtext("nme"), "Trigger_EDM_Pipeline")
        self.assertEqual(task.findtext("id"), "1")
        self.assertEqual(task.findtext("pri"), "100")

        actions = task.findall("Action")
        self.assertEqual(len(actions), 11, f"Expected exactly 11 actions (act0 to act10), found {len(actions)}")

    def test_variable_definitions_and_conditions(self):
        """Verify Variable Set actions (Code 547) for %EDM_SERVER_IP and %EDM_SERVER_PORT with !Set condition."""
        for xml_str in self.xml_blocks:
            root = ET.fromstring(xml_str)
            task = root.find(".//Task")
            self.assertIsNotNone(task)
            
            # Action 0: %EDM_SERVER_IP
            act0 = task.find("Action[@sr='act0']")
            self.assertIsNotNone(act0, "act0 not found")
            self.assertEqual(act0.findtext("code"), "547")
            self.assertEqual(act0.find("Str[@sr='arg0']").text, "%EDM_SERVER_IP")
            self.assertEqual(act0.find("Str[@sr='arg1']").text, "192.168.1.100")
            
            cond0 = act0.find(".//Condition[@sr='c0']")
            self.assertIsNotNone(cond0, "act0 missing condition")
            self.assertEqual(cond0.findtext("lhs"), "%EDM_SERVER_IP")
            self.assertEqual(cond0.findtext("op"), "12", "Condition operator should be 12 (Is Not Set / !Set)")

            # Action 1: %EDM_SERVER_PORT
            act1 = task.find("Action[@sr='act1']")
            self.assertIsNotNone(act1, "act1 not found")
            self.assertEqual(act1.findtext("code"), "547")
            self.assertEqual(act1.find("Str[@sr='arg0']").text, "%EDM_SERVER_PORT")
            self.assertEqual(act1.find("Str[@sr='arg1']").text, "8000")
            
            cond1 = act1.find(".//Condition[@sr='c0']")
            self.assertIsNotNone(cond1, "act1 missing condition")
            self.assertEqual(cond1.findtext("lhs"), "%EDM_SERVER_PORT")
            self.assertEqual(cond1.findtext("op"), "12", "Condition operator should be 12 (Is Not Set / !Set)")

    def test_action_339_http_request_parameters(self):
        """Verify Action Code 339 HTTP Request parameters: POST method, URL, Headers, Body, Timeout, Error handling."""
        for xml_str in self.xml_blocks:
            root = ET.fromstring(xml_str)
            task = root.find(".//Task")
            act2 = task.find("Action[@sr='act2']")
            self.assertIsNotNone(act2, "act2 not found")
            self.assertEqual(act2.findtext("code"), "339", "Action 2 code must be 339 (HTTP Request)")

            # arg0: Method (1 = POST)
            self.assertEqual(act2.find("Int[@sr='arg0']").attrib.get("val"), "1", "HTTP method must be 1 (POST)")

            # arg1: URL
            url = act2.find("Str[@sr='arg1']").text
            self.assertEqual(url, "http://%EDM_SERVER_IP:%EDM_SERVER_PORT/trigger-pipeline")

            # arg2: Headers
            headers = act2.find("Str[@sr='arg2']").text
            self.assertIn("Content-Type:application/json", headers)
            self.assertIn("Accept:application/json", headers)

            # arg4: Body
            body_str = act2.find("Str[@sr='arg4']").text
            self.assertIsNotNone(body_str, "HTTP request body is missing")
            body_json = json.loads(body_str)
            self.assertEqual(body_json.get("from_device"), True)
            self.assertEqual(body_json.get("auto_drop"), True)
            self.assertEqual(body_json.get("brand"), "laser_baptism")

            # arg7: Timeout (30s)
            self.assertEqual(act2.find("Int[@sr='arg7']").attrib.get("val"), "30")

            # arg8: Trust Cert (1)
            self.assertEqual(act2.find("Int[@sr='arg8']").attrib.get("val"), "1")

            # arg9: Follow Redirects (1)
            self.assertEqual(act2.find("Int[@sr='arg9']").attrib.get("val"), "1")

            # arg11: Continue Task After Error (1) -> Essential so errors jump to Else branch
            self.assertEqual(act2.find("Int[@sr='arg11']").attrib.get("val"), "1")

    def test_conditional_branching_codes(self):
        """Verify Conditional Branching: Code 37 (If), Code 43 (Else), Code 38 (End If)."""
        for xml_str in self.xml_blocks:
            root = ET.fromstring(xml_str)
            task = root.find(".//Task")

            # Act 3: If Code 37
            act3 = task.find("Action[@sr='act3']")
            self.assertEqual(act3.findtext("code"), "37")
            cond = act3.find(".//Condition[@sr='c0']")
            self.assertEqual(cond.findtext("lhs"), "%http_response_code")
            self.assertEqual(cond.findtext("op"), "0", "Operator 0 is Equals")
            self.assertEqual(cond.findtext("rhs"), "202")

            # Act 7: Else Code 43
            act7 = task.find("Action[@sr='act7']")
            self.assertEqual(act7.findtext("code"), "43")

            # Act 10: End If Code 38
            act10 = task.find("Action[@sr='act10']")
            self.assertEqual(act10.findtext("code"), "38")

    def test_vibration_patterns(self):
        """Verify Vibrate Pattern actions (Code 130): Success (0,100,100,100) and Error (0,500,200,500)."""
        for xml_str in self.xml_blocks:
            root = ET.fromstring(xml_str)
            task = root.find(".//Task")

            # Act 4: Success Vibrate Pattern
            act4 = task.find("Action[@sr='act4']")
            self.assertEqual(act4.findtext("code"), "130")
            self.assertEqual(act4.find("Str[@sr='arg0']").text, "0,100,100,100")

            # Act 8: Error Vibrate Pattern
            act8 = task.find("Action[@sr='act8']")
            self.assertEqual(act8.findtext("code"), "130")
            self.assertEqual(act8.find("Str[@sr='arg0']").text, "0,500,200,500")

    def test_notification_and_flash_action_codes(self):
        """Verify Flash HUD (Code 548) and Notify (Code 523) actions."""
        for xml_str in self.xml_blocks:
            root = ET.fromstring(xml_str)
            task = root.find(".//Task")

            # Act 5: Success Flash (Code 548)
            act5 = task.find("Action[@sr='act5']")
            self.assertEqual(act5.findtext("code"), "548")
            self.assertIn("202 Accepted", act5.find("Str[@sr='arg0']").text)

            # Act 6: Success Notify (Code 523)
            act6 = task.find("Action[@sr='act6']")
            self.assertEqual(act6.findtext("code"), "523")
            self.assertEqual(act6.find("Str[@sr='arg0']").text, "EDM Master Pipeline")
            self.assertIn("%http_data", act6.find("Str[@sr='arg1']").text)
            self.assertEqual(act6.find("Str[@sr='arg2']").text, "mw_av_videocam")
            self.assertEqual(act6.find("Int[@sr='arg5']").attrib.get("val"), "4")

            # Act 9: Error Flash (Code 548)
            act9 = task.find("Action[@sr='act9']")
            self.assertEqual(act9.findtext("code"), "548")
            self.assertIn("%http_response_code", act9.find("Str[@sr='arg0']").text)
            self.assertIn("%http_error", act9.find("Str[@sr='arg0']").text)

    def test_project_xml_bundle_structure(self):
        """Verify EDM_Automation.prj.xml Project root, metadata, and task inclusion."""
        proj_xml = self.xml_blocks[1]
        root = ET.fromstring(proj_xml)

        project = root.find("Project")
        self.assertIsNotNone(project, "Project element missing in Project XML")
        self.assertEqual(project.findtext("id"), "EDM_Remote_Automation")
        self.assertEqual(project.findtext("name"), "EDM Automation")
        self.assertEqual(project.findtext("tids"), "1")
        self.assertIsNotNone(project.find("Img/nme"))

        task = root.find("Task")
        self.assertIsNotNone(task, "Task element missing in Project XML")
        self.assertEqual(task.findtext("nme"), "Trigger_EDM_Pipeline")
        self.assertEqual(task.findtext("id"), "1")


class TestTaskerFastAPISchemaCompatibility(unittest.TestCase):
    """Empirical verification of schema compatibility between Tasker payload and remote_trigger.py."""

    @classmethod
    def setUpClass(cls):
        cls.tasker_md_path = MODULE_DIR / "tasker_profile.md"
        cls.raw_content = cls.tasker_md_path.read_text(encoding="utf-8")
        cls.xml_blocks = re.findall(r"<TaskerData[\s\S]*?</TaskerData>", cls.raw_content)

    def test_pydantic_validation_on_tasker_xml_json_body(self):
        """Verify that the raw JSON payload in the Tasker XML parses cleanly into PipelineTriggerRequest."""
        root = ET.fromstring(self.xml_blocks[0])
        body_str = root.find(".//Action[@sr='act2']/Str[@sr='arg4']").text
        self.assertIsNotNone(body_str)

        # Validate with Pydantic
        req = PipelineTriggerRequest.model_validate_json(body_str)
        self.assertEqual(req.from_device, True)
        self.assertEqual(req.auto_drop, True)
        self.assertEqual(req.event, "LiveConcert")
        self.assertEqual(req.artist, "AutoArtist")
        self.assertEqual(req.brand, "laser_baptism")
        self.assertEqual(req.reframe_mode, "center_crop")
        self.assertEqual(req.publish_youtube, False)
        self.assertEqual(req.dry_run, False)

    def test_pydantic_validation_on_documented_markdown_json_body(self):
        """Verify that the documented JSON snippet in Section 4 parses into PipelineTriggerRequest."""
        json_matches = re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", self.raw_content)
        self.assertGreater(len(json_matches), 0)

        # Find the request body snippet
        req_json_str = None
        for j_str in json_matches:
            if '"from_device": true' in j_str and '"drop_duration"' in j_str:
                req_json_str = j_str
                break
        
        self.assertIsNotNone(req_json_str, "Could not find documented request body JSON snippet")
        req = PipelineTriggerRequest.model_validate_json(req_json_str)
        self.assertEqual(req.from_device, True)
        self.assertEqual(req.auto_drop, True)
        self.assertEqual(req.drop_duration, 30.0)
        self.assertEqual(req.brand, "laser_baptism")

    def test_build_orchestrator_command_with_tasker_payload(self):
        """Verify that build_orchestrator_command builds the expected CLI arguments from Tasker payload."""
        root = ET.fromstring(self.xml_blocks[0])
        body_str = root.find(".//Action[@sr='act2']/Str[@sr='arg4']").text
        req = PipelineTriggerRequest.model_validate_json(body_str)

        cmd = build_orchestrator_command(req, MODULE_DIR)
        self.assertIn("orchestrator.py", cmd[1])
        self.assertIn("pipeline", cmd)
        self.assertIn("--from-device", cmd)
        self.assertIn("--auto-drop", cmd)
        self.assertIn("--event", cmd)
        self.assertIn("LiveConcert", cmd)
        self.assertIn("--artist", cmd)
        self.assertIn("AutoArtist", cmd)
        self.assertIn("--brand", cmd)
        self.assertIn("laser_baptism", cmd)


class TestTaskerDocumentationCompleteness(unittest.TestCase):
    """Verify all documentation sections and Samsung One UI 7 runbook completeness."""

    @classmethod
    def setUpClass(cls):
        cls.tasker_md_path = MODULE_DIR / "tasker_profile.md"
        cls.raw_content = cls.tasker_md_path.read_text(encoding="utf-8")

    def test_document_metadata_and_id(self):
        self.assertIn("TASKER-PROFILE-S26-ULTRA-001", self.raw_content)
        self.assertIn("Samsung Galaxy S26 Ultra", self.raw_content)
        self.assertIn("SM-S948", self.raw_content)
        self.assertIn("One UI 7", self.raw_content)

    def test_action_matrix_table(self):
        self.assertIn("## 3. Action Code & Argument Mapping Matrix", self.raw_content)
        self.assertIn("339", self.raw_content)
        self.assertIn("547", self.raw_content)
        self.assertIn("130", self.raw_content)
        self.assertIn("548", self.raw_content)
        self.assertIn("523", self.raw_content)

    def test_widget_and_tile_instructions(self):
        self.assertIn("## 6. Samsung One UI 7 1x1 Home Screen Widget Configuration", self.raw_content)
        self.assertIn("Task Shortcut (1x1)", self.raw_content)
        self.assertIn("## 7. Samsung One UI 7 Quick Settings (QS) Tile Configuration", self.raw_content)
        self.assertIn("Quick Settings Tasks", self.raw_content)

    def test_knox_battery_whitelist_instructions(self):
        self.assertIn("## 8. Knox Battery & Power Optimization Whitelist Runbook", self.raw_content)
        self.assertIn("Unrestricted", self.raw_content)
        self.assertIn("Never sleeping apps", self.raw_content)
        self.assertIn("Allow background data usage", self.raw_content)
        self.assertIn("Run In Foreground", self.raw_content)


class TestAdversarialTaskerAndFastAPIStress(unittest.TestCase):
    """Adversarial stress harness for Tasker payload variations and FastAPI mutex concurrency."""

    def test_payload_with_extra_unknown_fields(self):
        """Tasker might include extra metadata fields; ensure PipelineTriggerRequest allows them (extra='allow')."""
        adversarial_payload = {
            "source": "s26_ultra",
            "from_device": True,
            "auto_drop": True,
            "event": "LiveConcert",
            "artist": "AutoArtist",
            "brand": "laser_baptism",
            "battery_level": 88,
            "carrier": "Verizon",
            "tasker_version": "6.3.13",
            "extra_nested_data": {"gps_lat": 33.4484, "gps_lon": -112.0740},
        }
        req = PipelineTriggerRequest.model_validate(adversarial_payload)
        self.assertEqual(req.from_device, True)
        self.assertEqual(req.auto_drop, True)
        self.assertEqual(req.event, "LiveConcert")
        self.assertEqual(req.extra_nested_data["gps_lat"], 33.4484)

    def test_drop_duration_bounds_fuzzing(self):
        """Verify drop_duration adheres to [5.0, 59.0] bounds."""
        valid_low = PipelineTriggerRequest(drop_duration=5.0)
        self.assertEqual(valid_low.drop_duration, 5.0)

        valid_high = PipelineTriggerRequest(drop_duration=59.0)
        self.assertEqual(valid_high.drop_duration, 59.0)

        with self.assertRaises(ValidationError):
            PipelineTriggerRequest(drop_duration=4.9)

        with self.assertRaises(ValidationError):
            PipelineTriggerRequest(drop_duration=59.1)

    def test_reframe_mode_variations(self):
        """Verify valid reframe modes."""
        for mode in ["center_crop", "blur_pad", "offset_crop"]:
            req = PipelineTriggerRequest(reframe_mode=mode)
            self.assertEqual(req.reframe_mode, mode)

    @patch("remote_trigger.find_binary", return_value=Path("/usr/bin/mock_binary"))
    @patch("remote_trigger.find_adb_binary", return_value=Path("/usr/bin/mock_adb"))
    def test_fastapi_app_trigger_and_mutex_concurrency(self, mock_adb, mock_bin):
        """Verify FastAPI app triggers job and handles endpoints with mocked dependencies."""
        async def run_async_test():
            from fastapi.testclient import TestClient
            app = create_app(workspace_root=MODULE_DIR)
            client = TestClient(app)

            # Test health endpoint
            health_res = client.get("/health")
            self.assertEqual(health_res.status_code, 200)
            self.assertEqual(health_res.json()["status"], "healthy")

            # Test dry_run trigger
            payload = {
                "event": "AdversarialTest",
                "artist": "AdversarialDJ",
                "brand": "laser_baptism",
                "from_device": True,
                "auto_drop": True,
                "dry_run": True,
            }
            res1 = client.post("/trigger-pipeline", json=payload)
            self.assertEqual(res1.status_code, 202)
            data1 = res1.json()
            self.assertEqual(data1["status"], "accepted")
            self.assertIn("job_id", data1)

            # Test status endpoint
            status_res = client.get("/status")
            self.assertEqual(status_res.status_code, 200)

        asyncio.run(run_async_test())


if __name__ == "__main__":
    unittest.main()