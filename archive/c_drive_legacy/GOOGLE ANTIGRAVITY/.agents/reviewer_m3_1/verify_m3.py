import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path(__file__).resolve().parent.parent.parent
content_creation = repo_root / "content_creation"
tasker_file = content_creation / "tasker_profile.md"
blueprint_file = content_creation / "V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md"
remote_trigger_file = content_creation / "remote_trigger.py"

print("--- 1. Checking tasker_profile.md XML Blocks ---")
tasker_text = tasker_file.read_text(encoding="utf-8")
xmls = re.findall(r"<TaskerData[\s\S]*?</TaskerData>", tasker_text)
print(f"Found {len(xmls)} XML blocks in tasker_profile.md")
assert len(xmls) >= 2, f"Expected >= 2 XML blocks, found {len(xmls)}"

for idx, xml_str in enumerate(xmls):
    root = ET.fromstring(xml_str)
    print(f"\n[XML Block {idx+1}] Root: {root.tag}, Attributes: {root.attrib}")
    task = root.find(".//Task")
    assert task is not None, "Task element missing"
    task_name = task.findtext("nme")
    print(f"Task Name: {task_name}")
    assert task_name == "Trigger_EDM_Pipeline", f"Unexpected task name: {task_name}"

    actions = task.findall("./Action")
    print(f"Total Actions: {len(actions)}")
    assert len(actions) == 11, f"Expected 11 actions, found {len(actions)}"

    # Check Act 0: Set %EDM_SERVER_IP
    act0 = actions[0]
    assert act0.findtext("code") == "547", f"Act 0 code is {act0.findtext('code')}"
    ip_var = act0.find("./Str[@sr='arg0']").text
    ip_val = act0.find("./Str[@sr='arg1']").text
    print(f"Act 0: Variable Set {ip_var} = {ip_val}")
    assert ip_var == "%EDM_SERVER_IP" and ip_val == "192.168.1.100"

    # Check Act 1: Set %EDM_SERVER_PORT
    act1 = actions[1]
    assert act1.findtext("code") == "547", f"Act 1 code is {act1.findtext('code')}"
    port_var = act1.find("./Str[@sr='arg0']").text
    port_val = act1.find("./Str[@sr='arg1']").text
    print(f"Act 1: Variable Set {port_var} = {port_val}")
    assert port_var == "%EDM_SERVER_PORT" and port_val == "8000"

    # Check Act 2: HTTP Request Action 339
    act2 = actions[2]
    assert act2.findtext("code") == "339", f"Act 2 code is {act2.findtext('code')}"
    method_val = act2.find("./Int[@sr='arg0']").attrib.get("val")
    url_val = act2.find("./Str[@sr='arg1']").text
    headers_val = act2.find("./Str[@sr='arg2']").text
    body_val = act2.find("./Str[@sr='arg4']").text
    timeout_val = act2.find("./Int[@sr='arg7']").attrib.get("val")
    trust_cert_val = act2.find("./Int[@sr='arg8']").attrib.get("val")
    continue_err_val = act2.find("./Int[@sr='arg11']").attrib.get("val")

    print(f"Act 2 (HTTP Request 339): Method={method_val}, URL={url_val}, Timeout={timeout_val}, ContinueOnError={continue_err_val}")
    assert method_val == "1", "Expected Method 1 (POST)"
    assert url_val == "http://%EDM_SERVER_IP:%EDM_SERVER_PORT/trigger-pipeline"
    assert "Content-Type:application/json" in headers_val
    assert continue_err_val == "1", "Expected Continue Task After Error == 1"

    parsed_body = json.loads(body_val)
    print(f"Act 2 JSON Body: {parsed_body}")
    assert parsed_body.get("from_device") is True
    assert parsed_body.get("auto_drop") is True
    assert parsed_body.get("source") == "s26_ultra"

    # Check Act 3: If %http_response_code eq 202
    act3 = actions[3]
    assert act3.findtext("code") == "37", f"Act 3 code is {act3.findtext('code')}"
    cond = act3.find(".//Condition")
    lhs = cond.findtext("lhs")
    op = cond.findtext("op")
    rhs = cond.findtext("rhs")
    print(f"Act 3 (If): LHS={lhs}, op={op}, RHS={rhs}")
    assert lhs == "%http_response_code"
    assert op == "0"  # Equals
    assert rhs == "202"

    # Check Act 4: Success Vibrate Pattern 130
    act4 = actions[4]
    assert act4.findtext("code") == "130"
    vibe_pat = act4.find("./Str[@sr='arg0']").text
    print(f"Act 4 (Success Vibrate Pattern): {vibe_pat}")
    assert vibe_pat == "0,100,100,100"

    # Check Act 5: Success Flash 548
    act5 = actions[5]
    assert act5.findtext("code") == "548"
    flash_txt = act5.find("./Str[@sr='arg0']").text
    print(f"Act 5 (Success Flash): {repr(flash_txt[:40])}...")
    assert "HTTP 202 Accepted" in flash_txt

    # Check Act 6: Success Notify 523
    act6 = actions[6]
    assert act6.findtext("code") == "523"
    notify_title = act6.find("./Str[@sr='arg0']").text
    print(f"Act 6 (Success Notify Title): {notify_title}")
    assert notify_title == "EDM Master Pipeline"

    # Check Act 7: Else 43
    act7 = actions[7]
    assert act7.findtext("code") == "43"
    print("Act 7: Else (Code 43)")

    # Check Act 8: Error Vibrate Pattern 130
    act8 = actions[8]
    assert act8.findtext("code") == "130"
    err_vibe = act8.find("./Str[@sr='arg0']").text
    print(f"Act 8 (Error Vibrate Pattern): {err_vibe}")
    assert err_vibe == "0,500,200,500"

    # Check Act 9: Error Flash 548
    act9 = actions[9]
    assert act9.findtext("code") == "548"
    err_flash = act9.find("./Str[@sr='arg0']").text
    print(f"Act 9 (Error Flash): {repr(err_flash[:40])}...")
    assert "%http_response_code" in err_flash

    # Check Act 10: End If 38
    act10 = actions[10]
    assert act10.findtext("code") == "38"
    print("Act 10: End If (Code 38)")

print("\n--- 2. Checking Alignment with remote_trigger.py ---")
sys.path.insert(0, str(content_creation))
from remote_trigger import PipelineTriggerRequest, app

# Test instantiating PipelineTriggerRequest with Tasker body
req = PipelineTriggerRequest(**parsed_body)
print(f"Pydantic validation passed for Tasker body: {req.model_dump()}")
assert req.from_device is True
assert req.auto_drop is True
assert req.event == "LiveConcert"
assert req.artist == "AutoArtist"
assert req.brand == "laser_baptism"

print("\n--- 3. Checking Samsung S26 Ultra One UI 7 Setup Instructions in tasker_profile.md ---")
assert "One UI 7" in tasker_text
assert "1x1 Home Screen Widget" in tasker_text
assert "Quick Settings (QS) Tile" in tasker_text
assert "Knox Battery" in tasker_text
assert "Unrestricted" in tasker_text
assert "Never sleeping apps" in tasker_text
print("All S26 Ultra One UI 7 runbook sections verified present!")

print("\n--- 4. Checking V2 Blueprint Integration ---")
blueprint_text = blueprint_file.read_text(encoding="utf-8")
assert "Mechanism 6: FastAPI Zero-Touch Remote Trigger Server" in blueprint_text
assert "Mechanism 7: Tasker One UI 7 Mobile Fast-Action Client" in blueprint_text
assert "Step 0A (Mobile Trigger)" in blueprint_text
assert "Step 0B (HTTP Dispatch)" in blueprint_text
assert "Step 0C (mDNS Discovery & Connect)" in blueprint_text
assert "Step 0D (Atomic Pull & Ledger)" in blueprint_text
assert "Step 0E (Health Partitioning)" in blueprint_text
assert "Tasker HTTP Timeout / Host Unreachable" in blueprint_text
assert "Concurrent Trigger Overlap (HTTP 409 Conflict)" in blueprint_text
print("All V2 Blueprint integration sections verified present!")

print("\nALL VERIFICATIONS PASSED CLEANLY!")
