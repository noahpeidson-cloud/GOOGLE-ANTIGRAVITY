"""
test_tasker_profile.py - Test Suite for Samsung S26 Ultra Tasker Profile XML & Schema Consistency

Tests cover:
1. File presence and structural completeness of tasker_profile.md.
2. XML parsing and schema validation of Trigger_EDM_Pipeline.tsk.xml:
   - Root <TaskerData> schema (dvi, tv="6.3.13").
   - <Task> attributes and action sequence (Actions 0 to 10).
   - Action 547: Fallback variable initializations for %EDM_SERVER_IP and %EDM_SERVER_PORT.
   - Action 339: HTTP Request POST to /trigger-pipeline with Content-Type and Accept headers.
   - Action 37 & 43: Status code branching on %http_response_code eq 202.
   - Action 130: Vibration pattern definitions (0,100,100,100 success vs 0,500,200,500 error).
   - Action 548: HUD Flash feedback for success and failure branches.
   - Action 523: Persistent notification HUD.
3. XML parsing and schema validation of EDM_Automation.prj.xml:
   - <Project> bundle structure and task references (tids="1").
4. Schema parity between Tasker Action 339 JSON payload and remote_trigger.PipelineTriggerRequest Pydantic model.
"""

import json
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from remote_trigger import PipelineTriggerRequest, TriggerResponse, ConflictResponse


class TestTaskerProfileDocument(unittest.TestCase):
    """Structural assertions for tasker_profile.md."""

    def setUp(self):
        self.doc_path = Path(__file__).resolve().parent.parent / "tasker_profile.md"
        self.assertTrue(self.doc_path.is_file(), f"tasker_profile.md not found at {self.doc_path}")
        self.content = self.doc_path.read_text(encoding="utf-8")

    def test_document_size_and_core_sections(self):
        self.assertGreater(len(self.content), 5000)
        self.assertIn("TASKER-PROFILE-S26-ULTRA-001", self.content)
        self.assertIn("Samsung Galaxy S26 Ultra", self.content)
        self.assertIn("Trigger_EDM_Pipeline.tsk.xml", self.content)
        self.assertIn("EDM_Automation.prj.xml", self.content)
        self.assertIn("Action Code & Argument Mapping Matrix", self.content)
        self.assertIn("FastAPI REST Endpoint Parameter Matching", self.content)
        self.assertIn("One UI 7 Step-by-Step Setup Guide", self.content)

    def test_haptic_patterns_documented(self):
        self.assertIn("0,100,100,100", self.content)
        self.assertIn("0,500,200,500", self.content)

    def test_http_endpoint_documented(self):
        self.assertIn("/trigger-pipeline", self.content)
        self.assertIn("HTTP 202 Accepted", self.content)
        self.assertIn("HTTP 409 Conflict", self.content)


class TestTaskerTaskXMLValidity(unittest.TestCase):
    """Validation of the importable Task XML block (Trigger_EDM_Pipeline.tsk.xml)."""

    def setUp(self):
        self.doc_path = Path(__file__).resolve().parent.parent / "tasker_profile.md"
        self.content = self.doc_path.read_text(encoding="utf-8")

        # Extract XML code blocks
        xml_blocks = re.findall(r"```xml\s*(<TaskerData[\s\S]*?</TaskerData>)\s*```", self.content)
        self.assertGreaterEqual(len(xml_blocks), 2, "Failed to extract both Tasker XML blocks from tasker_profile.md")

        # First XML block is the Task XML
        self.task_xml_text = xml_blocks[0]
        self.root = ET.fromstring(self.task_xml_text)

    def test_tasker_data_root_attributes(self):
        self.assertEqual(self.root.tag, "TaskerData")
        self.assertEqual(self.root.attrib.get("dvi"), "1")
        self.assertEqual(self.root.attrib.get("tv"), "6.3.13")

    def test_task_element_attributes(self):
        task = self.root.find("Task")
        self.assertIsNotNone(task, "<Task> element missing from XML")
        self.assertEqual(task.find("nme").text, "Trigger_EDM_Pipeline")
        self.assertEqual(task.find("pri").text, "100")
        self.assertEqual(task.find("id").text, "1")

    def test_action_sequence_codes(self):
        task = self.root.find("Task")
        actions = task.findall("Action")
        self.assertEqual(len(actions), 11, "Expected exactly 11 Tasker action nodes (act0 through act10)")

        # Verify action codes
        codes = [act.find("code").text for act in actions]
        expected_codes = [
            "547",  # act0: Variable Set %EDM_SERVER_IP
            "547",  # act1: Variable Set %EDM_SERVER_PORT
            "339",  # act2: HTTP Request POST /trigger-pipeline
            "37",   # act3: If %http_response_code eq 202
            "130",  # act4: Vibrate Pattern (success)
            "548",  # act5: Flash HUD (success)
            "523",  # act6: Notify (success HUD)
            "43",   # act7: Else
            "130",  # act8: Vibrate Pattern (error)
            "548",  # act9: Flash HUD (error)
            "38",   # act10: End If
        ]
        self.assertEqual(codes, expected_codes)

    def test_action_0_and_1_variable_set(self):
        task = self.root.find("Task")
        act0 = task.findall("Action")[0]
        self.assertEqual(act0.find("Str[@sr='arg0']").text, "%EDM_SERVER_IP")
        self.assertEqual(act0.find("Str[@sr='arg1']").text, "192.168.1.100")

        act1 = task.findall("Action")[1]
        self.assertEqual(act1.find("Str[@sr='arg0']").text, "%EDM_SERVER_PORT")
        self.assertEqual(act1.find("Str[@sr='arg1']").text, "8000")

    def test_action_2_http_request_details(self):
        task = self.root.find("Task")
        act2 = task.findall("Action")[2]

        # Method: 1 = POST
        self.assertEqual(act2.find("Int[@sr='arg0']").attrib.get("val"), "1")

        # URL
        url = act2.find("Str[@sr='arg1']").text
        self.assertEqual(url, "http://%EDM_SERVER_IP:%EDM_SERVER_PORT/trigger-pipeline")

        # Headers
        headers = act2.find("Str[@sr='arg2']").text
        self.assertIn("Content-Type:application/json", headers)
        self.assertIn("Accept:application/json", headers)

        # Body JSON
        body = act2.find("Str[@sr='arg4']").text
        self.assertIsNotNone(body)
        payload = json.loads(body)
        self.assertTrue(payload.get("from_device"))
        self.assertTrue(payload.get("auto_drop"))
        self.assertEqual(payload.get("brand"), "laser_baptism")

        # Schema validation against remote_trigger.PipelineTriggerRequest
        req_model = PipelineTriggerRequest(**payload)
        self.assertTrue(req_model.from_device)
        self.assertTrue(req_model.auto_drop)
        self.assertEqual(req_model.brand, "laser_baptism")

        # Timeout, Trust Cert, Continue Task After Error
        self.assertEqual(act2.find("Int[@sr='arg7']").attrib.get("val"), "30")
        self.assertEqual(act2.find("Int[@sr='arg8']").attrib.get("val"), "1")
        self.assertEqual(act2.find("Int[@sr='arg11']").attrib.get("val"), "1")

    def test_action_3_if_condition_status_code(self):
        task = self.root.find("Task")
        act3 = task.findall("Action")[3]
        condition = act3.find("ConditionList/Condition")
        self.assertEqual(condition.find("lhs").text, "%http_response_code")
        self.assertEqual(condition.find("op").text, "0")  # 0 = eq
        self.assertEqual(condition.find("rhs").text, "202")

    def test_action_4_and_8_vibrate_patterns(self):
        task = self.root.find("Task")
        # Success vibration
        act4 = task.findall("Action")[4]
        self.assertEqual(act4.find("Str[@sr='arg0']").text, "0,100,100,100")

        # Error vibration
        act8 = task.findall("Action")[8]
        self.assertEqual(act8.find("Str[@sr='arg0']").text, "0,500,200,500")

    def test_action_5_and_9_flash_toasts(self):
        task = self.root.find("Task")
        # Success toast
        act5 = task.findall("Action")[5]
        self.assertIn("202 Accepted", act5.find("Str[@sr='arg0']").text)

        # Error toast
        act9 = task.findall("Action")[9]
        self.assertIn("Trigger Failed", act9.find("Str[@sr='arg0']").text)


class TestTaskerProjectXMLValidity(unittest.TestCase):
    """Validation of the importable Project XML block (EDM_Automation.prj.xml)."""

    def setUp(self):
        self.doc_path = Path(__file__).resolve().parent.parent / "tasker_profile.md"
        self.content = self.doc_path.read_text(encoding="utf-8")

        xml_blocks = re.findall(r"```xml\s*(<TaskerData[\s\S]*?</TaskerData>)\s*```", self.content)
        self.assertGreaterEqual(len(xml_blocks), 2)

        # Second XML block is the Project XML
        self.prj_xml_text = xml_blocks[1]
        self.root = ET.fromstring(self.prj_xml_text)

    def test_project_element_attributes(self):
        prj = self.root.find("Project")
        self.assertIsNotNone(prj, "<Project> element missing from Project XML")
        self.assertEqual(prj.find("id").text, "EDM_Remote_Automation")
        self.assertEqual(prj.find("name").text, "EDM Automation")
        self.assertEqual(prj.find("tids").text, "1")

    def test_project_contains_trigger_task(self):
        task = self.root.find("Task")
        self.assertIsNotNone(task, "<Task> element missing from Project bundle")
        self.assertEqual(task.find("nme").text, "Trigger_EDM_Pipeline")
        self.assertEqual(task.find("id").text, "1")
        self.assertEqual(len(task.findall("Action")), 11)


class TestTaskerSchemaParity(unittest.TestCase):
    """Validates contract compatibility between Tasker payload and FastAPI server."""

    def test_tasker_payload_deserialization_and_command_construction(self):
        tasker_payload = {
            "source": "s26_ultra",
            "from_device": True,
            "auto_drop": True,
            "event": "LiveConcert",
            "artist": "AutoArtist",
            "brand": "laser_baptism",
        }

        # Validate with Pydantic
        req = PipelineTriggerRequest(**tasker_payload)
        self.assertEqual(req.event, "LiveConcert")
        self.assertEqual(req.artist, "AutoArtist")
        self.assertTrue(req.from_device)
        self.assertTrue(req.auto_drop)

        # Verify response structure compatibility
        res = TriggerResponse(
            status="accepted",
            job_id="job_20260822_123456_abcdef",
            message="Pipeline job accepted and launched in background",
            command=["python", "orchestrator.py", "pipeline"],
            started_at="2026-08-22T12:34:56Z",
        )
        self.assertEqual(res.status, "accepted")

        # Verify conflict structure compatibility
        conflict = ConflictResponse(
            status="conflict",
            error="Pipeline execution is already in progress",
            current_job_id="job_active_123",
        )
        self.assertEqual(conflict.status, "conflict")


if __name__ == "__main__":
    unittest.main()
