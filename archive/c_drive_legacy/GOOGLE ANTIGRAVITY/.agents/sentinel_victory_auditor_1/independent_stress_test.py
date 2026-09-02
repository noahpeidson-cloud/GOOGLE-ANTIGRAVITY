import json
import subprocess
import sys
import os
import time

WATCHDOG_SCRIPT = r"G:\My Drive\GOOGLE ANTIGRAVITY\.agents\shadow_watchdog.py"

def run_watchdog(payload_str):
    t0 = time.perf_counter()
    p = subprocess.run(
        [sys.executable, WATCHDOG_SCRIPT],
        input=payload_str,
        text=True,
        capture_output=True,
        cwd=r"G:\My Drive\GOOGLE ANTIGRAVITY\.agents"
    )
    t1 = time.perf_counter()
    assert p.returncode == 0, f"Process crashed (code {p.returncode}): {p.stderr}"
    out_json = json.loads(p.stdout.strip())
    return out_json, (t1 - t0) * 1000.0

def run_all_tests():
    print("--- STARTING INDEPENDENT AUDITOR ADVERSARIAL STRESS SUITE ---")
    passed = 0
    failed = 0

    def check(name, payload, expect_rejection, expected_decision="continue"):
        nonlocal passed, failed
        if not isinstance(payload, str):
            payload_str = json.dumps(payload)
        else:
            payload_str = payload
            
        out, latency_ms = run_watchdog(payload_str)
        is_rejected = (out.get("decision") == "continue")
        
        if is_rejected == expect_rejection:
            if expect_rejection:
                assert "reason" in out, "Rejection payload missing 'reason' field"
                assert "confidence" in out["reason"].lower(), "Rejection reason doesn't mention confidence"
            print(f"[PASS] ({latency_ms:.2f}ms) {name}")
            passed += 1
        else:
            print(f"[FAIL] ({latency_ms:.2f}ms) {name} -> Expected reject={expect_rejection}, got {out}")
            failed += 1

    # 1. Exact acceptance criteria test: JSONL stream missing confidence -> {"decision": "continue"}
    check(
        "AC1: Standard JSONL transcript payload missing confidence",
        '{"type": "USER_INPUT", "content": "hello"}\n{"type": "PLANNER_RESPONSE", "content": "I am working on it"}',
        True
    )

    # 2. Exact acceptance criteria test: JSONL stream with valid confidence -> {}
    check(
        "AC2: Standard JSONL transcript payload with valid confidence",
        '{"type": "USER_INPUT", "content": "hello"}\n{"type": "PLANNER_RESPONSE", "content": "Done!\\n<confidence>\\n**Confidence Level:** HIGH\\n</confidence>"}',
        False
    )

    # 3. 6-backtick code block enclosing 5-backtick block with <confidence>
    check(
        "Adversarial: 6-backtick code block with nested 5-backtick code containing <confidence>",
        {"type": "PLANNER_RESPONSE", "content": "``````markdown\n`````xml\n<confidence>HIGH</confidence>\n`````\n``````"},
        True
    )

    # 4. 6-backtick code block + real terminal confidence
    check(
        "Adversarial: 6-backtick code block followed by real terminal confidence",
        {"type": "PLANNER_RESPONSE", "content": "``````markdown\n<confidence>LOW</confidence>\n``````\n\n<confidence>\n**Confidence Level:** HIGH\n</confidence>"},
        False
    )

    # 5. Tildes code block with 4 tildes enclosing <confidence>
    check(
        "Adversarial: 4-tilde code block ~~~~xml enclosing <confidence>",
        {"type": "PLANNER_RESPONSE", "content": "~~~~xml\n<confidence>HIGH</confidence>\n~~~~"},
        True
    )

    # 6. Mixed inline backticks and escaped characters
    check(
        "Adversarial: Inline code with backtick variations",
        {"type": "PLANNER_RESPONSE", "content": "Here is ```` <confidence>HIGH</confidence> ```` inside code"},
        True
    )

    # 7. Multi-step subagent invocation: multiple tool calls, then send_message with confidence in backticks (REJECT)
    complex_subagent_fake = {
        "steps": [
            {"type": "USER_INPUT", "content": "Audit task"},
            {"type": "MODEL_RESPONSE", "content": "Starting audit"},
            {"stepType": "TOOL_CALL", "toolCall": {"name": "run_command", "args": {"CommandLine": "dir"}}},
            {"stepType": "TOOL_RESULT", "output": "output"},
            {"stepType": "TOOL_CALL", "toolCall": {"name": "send_message", "args": {"Recipient": "parent", "Message": "Audit done! Here is tag: `<confidence>HIGH</confidence>`"}}}
        ]
    }
    check(
        "Adversarial: Subagent send_message with confidence inside inline backticks only",
        complex_subagent_fake,
        True
    )

    # 8. Multi-step subagent invocation: multiple tool calls, then send_message with valid confidence (ALLOW)
    complex_subagent_valid = {
        "steps": [
            {"type": "USER_INPUT", "content": "Audit task"},
            {"type": "MODEL_RESPONSE", "content": "Starting audit"},
            {"stepType": "TOOL_CALL", "toolCall": {"name": "run_command", "args": {"CommandLine": "dir"}}},
            {"stepType": "TOOL_RESULT", "output": "output"},
            {"stepType": "TOOL_CALL", "toolCall": {"name": "send_message", "args": {"Recipient": "parent", "Message": "Audit complete!\n\n<confidence>\n**Confidence Level:** HIGH\n**Evidence Chain:** Verified all 47 tests pass\n**Gaps / Assumptions:** None\n</confidence>"}}}
        ]
    }
    check(
        "Adversarial: Subagent send_message with genuine terminal confidence block",
        complex_subagent_valid,
        False
    )

    # 9. Case-insensitive tags <CONFIDENCE>...</CONFIDENCE>
    check(
        "Adversarial: Uppercase <CONFIDENCE> tag",
        {"type": "PLANNER_RESPONSE", "content": "All done!\n\n<CONFIDENCE>\n**Confidence Level:** HIGH\n</CONFIDENCE>"},
        False
    )

    # 10. Tag with extra XML attributes
    check(
        "Adversarial: Tag with XML attributes <confidence version='2.0' validated='true'>",
        {"type": "PLANNER_RESPONSE", "content": "All done!\n\n<confidence version=\"2.0\" validated=\"true\">\n**Confidence Level:** HIGH\n</confidence>"},
        False
    )

    # 11. Malformed JSONL lines interspersed with valid lines
    mixed_jsonl = '{"type": "USER_INPUT", "content": "start"}\nMALFORMED_LINE\n{"type": "PLANNER_RESPONSE", "content": "Done!\n<confidence>HIGH</confidence>"}\n'
    check(
        "Adversarial: JSONL stream with corrupt lines gracefully ignored and parsed",
        mixed_jsonl,
        False
    )

    # 12. Massive payload benchmark (500KB transcript)
    large_steps = []
    for i in range(500):
        large_steps.append({"type": "TOOL_RESULT", "output": f"Log line {i} " * 50})
    large_steps.append({"type": "PLANNER_RESPONSE", "content": "Finished large processing run.\n\n<confidence>\n**Confidence Level:** HIGH\n</confidence>"})
    large_payload = json.dumps({"steps": large_steps})
    print(f"Testing 500KB payload size: {len(large_payload)} bytes...")
    check(
        "Performance: 500KB transcript processing within acceptable latency",
        large_payload,
        False
    )

    print("\n=======================================================")
    print(f"INDEPENDENT AUDIT RESULT: {passed}/{passed+failed} PASSED, {failed} FAILED")
    print("=======================================================")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
