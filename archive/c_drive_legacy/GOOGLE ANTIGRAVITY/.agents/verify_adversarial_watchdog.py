import json
import subprocess
import sys
import os
import tempfile

def run_watchdog_stdin(payload_str, cwd=r"G:\My Drive\GOOGLE ANTIGRAVITY\.agents"):
    p = subprocess.run(
        [sys.executable, "shadow_watchdog.py"],
        input=payload_str,
        text=True,
        capture_output=True,
        cwd=cwd
    )
    assert p.returncode == 0, f"Process crashed with exit code {p.returncode}: {p.stderr}"
    try:
        return json.loads(p.stdout.strip())
    except Exception as e:
        raise AssertionError(f"Failed to parse JSON output: {p.stdout!r}") from e

def main():
    test_cases = []
    
    # 1. Missing confidence tag entirely
    test_cases.append((
        "Missing confidence tag",
        {"type": "PLANNER_RESPONSE", "content": "I have completed the task."},
        True # True = expect rejection (continue)
    ))

    # 2. Valid terminal confidence block
    test_cases.append((
        "Valid terminal confidence block",
        {"type": "PLANNER_RESPONSE", "content": "I finished the task.\n\n<confidence>\n**Confidence Level:** HIGH\n**Evidence Chain:** Verified\n**Gaps / Assumptions:** None\n</confidence>"},
        False # False = expect allow ({})
    ))

    # 3. Confidence inside 3-backtick code block only
    test_cases.append((
        "Confidence inside 3-backtick code block only",
        {"type": "PLANNER_RESPONSE", "content": "Example:\n```xml\n<confidence>\nHIGH\n</confidence>\n```"},
        True
    ))

    # 4. Confidence inside 4-backtick code block with nested 3-backticks
    test_cases.append((
        "Confidence inside 4-backtick code block with nested 3-backticks",
        {"type": "PLANNER_RESPONSE", "content": "Example:\n````xml\n```\n<confidence>\nHIGH\n</confidence>\n````"},
        True
    ))

    # 5. Confidence inside tilde code block (~~~xml)
    test_cases.append((
        "Confidence inside tilde code block",
        {"type": "PLANNER_RESPONSE", "content": "Example:\n~~~xml\n<confidence>\nHIGH\n</confidence>\n~~~"},
        True
    ))

    # 6. Confidence inside 4-space indented code block
    test_cases.append((
        "Confidence inside 4-space indented code block",
        {"type": "PLANNER_RESPONSE", "content": "Here is an example format:\n\n    <confidence>\n    HIGH\n    </confidence>"},
        True
    ))

    # 7. Confidence inside tab-indented code block
    test_cases.append((
        "Confidence inside tab-indented code block",
        {"type": "PLANNER_RESPONSE", "content": "Here is an example format:\n\n\t<confidence>\n\tHIGH\n\t</confidence>"},
        True
    ))

    # 8. Confidence inside single-backtick inline code
    test_cases.append((
        "Confidence inside single-backtick inline code",
        {"type": "PLANNER_RESPONSE", "content": "Check `<confidence>HIGH</confidence>` tag"},
        True
    ))

    # 9. Confidence inside double-backtick inline code
    test_cases.append((
        "Confidence inside double-backtick inline code",
        {"type": "PLANNER_RESPONSE", "content": "Check `` <confidence>HIGH</confidence> `` tag"},
        True
    ))

    # 10. Code block example earlier + valid terminal confidence block at end
    test_cases.append((
        "Code block example + valid terminal confidence",
        {"type": "PLANNER_RESPONSE", "content": "Here is how it works:\n```xml\n<confidence>LOW</confidence>\n```\n\nAll tasks complete.\n\n<confidence>\n**Confidence Level:** HIGH\n**Evidence Chain:** Ran tests\n**Gaps / Assumptions:** None\n</confidence>"},
        False
    ))

    # 11. Indented code example + valid terminal confidence
    test_cases.append((
        "Indented code example + valid terminal confidence",
        {"type": "PLANNER_RESPONSE", "content": "Here is how it works:\n\n    <confidence>LOW</confidence>\n\nAll tasks complete.\n\n<confidence>\n**Confidence Level:** HIGH\n**Evidence Chain:** Ran tests\n**Gaps / Assumptions:** None\n</confidence>"},
        False
    ))

    # 12. Trailing alphanumeric text after confidence block
    test_cases.append((
        "Trailing alphanumeric text after confidence block",
        {"type": "PLANNER_RESPONSE", "content": "<confidence>HIGH</confidence>\nHere is some trailing commentary."},
        True
    ))

    # 13. Trailing text ending in </confidence>
    test_cases.append((
        "Trailing text ending in </confidence>",
        {"type": "PLANNER_RESPONSE", "content": "<confidence>HIGH</confidence>\nSome trailing text that mentions </confidence>"},
        True
    ))

    # 14. Trailing markdown horizontal rule
    test_cases.append((
        "Trailing markdown horizontal rule after confidence",
        {"type": "PLANNER_RESPONSE", "content": "Done!\n\n<confidence>\nHIGH\n</confidence>\n\n---"},
        False
    ))

    # 15. Trailing whitespace / newlines
    test_cases.append((
        "Trailing whitespace / newlines",
        {"type": "PLANNER_RESPONSE", "content": "Done!\n\n<confidence>\nHIGH\n</confidence>\n\n   \n"},
        False
    ))

    # 16. Empty confidence tag
    test_cases.append((
        "Empty confidence tag",
        {"type": "PLANNER_RESPONSE", "content": "Done!\n\n<confidence></confidence>"},
        True
    ))

    # 17. Whitespace-only confidence tag
    test_cases.append((
        "Whitespace-only confidence tag",
        {"type": "PLANNER_RESPONSE", "content": "Done!\n\n<confidence>   \n\t  </confidence>"},
        True
    ))

    # 18. Inverted tags
    test_cases.append((
        "Inverted tags",
        {"type": "PLANNER_RESPONSE", "content": "Done!\n\n</confidence>HIGH<confidence>"},
        True
    ))

    # 19. Unclosed confidence tag
    test_cases.append((
        "Unclosed confidence tag",
        {"type": "PLANNER_RESPONSE", "content": "Done!\n\n<confidence>HIGH"},
        True
    ))

    # 20. Confidence tag with attributes (<confidence level="HIGH">)
    test_cases.append((
        "Confidence tag with attributes",
        {"type": "PLANNER_RESPONSE", "content": "Done!\n\n<confidence level=\"HIGH\">\n**Confidence Level:** HIGH\n</confidence>"},
        False
    ))

    # 21. JSONL missing confidence
    test_cases.append((
        "JSONL missing confidence",
        '{"type": "USER_INPUT", "content": "run tests"}\n{"type": "PLANNER_RESPONSE", "content": "running tests now"}',
        True
    ))

    # 22. JSONL valid confidence
    test_cases.append((
        "JSONL valid confidence",
        '{"type": "USER_INPUT", "content": "run tests"}\n{"type": "PLANNER_RESPONSE", "content": "tests passed\n<confidence>HIGH</confidence>"}',
        False
    ))

    # 23. Proto parts text missing confidence
    test_cases.append((
        "Proto parts text missing confidence",
        {"role": "model", "parts": [{"text": "Hello without confidence"}]},
        True
    ))

    # 24. Proto parts text valid confidence
    test_cases.append((
        "Proto parts text valid confidence",
        {"role": "model", "parts": [{"text": "Hello\n<confidence>HIGH</confidence>"}]},
        False
    ))

    # 25. Proto parts functionCall send_message missing confidence
    test_cases.append((
        "Proto parts functionCall send_message missing confidence",
        {"parts": [{"functionCall": {"name": "send_message", "args": {"Message": "Done without confidence"}}}]},
        True
    ))

    # 26. Proto parts functionCall send_message valid confidence
    test_cases.append((
        "Proto parts functionCall send_message valid confidence",
        {"parts": [{"functionCall": {"name": "send_message", "args": {"Message": "Done\n<confidence>HIGH</confidence>"}}}]},
        False
    ))

    # 27. Candidates structure missing confidence
    test_cases.append((
        "Candidates structure missing confidence",
        {"candidates": [{"content": {"parts": [{"text": "Response text"}]}}]},
        True
    ))

    # 28. Candidates structure valid confidence
    test_cases.append((
        "Candidates structure valid confidence",
        {"candidates": [{"content": {"parts": [{"text": "Response text\n<confidence>HIGH</confidence>"}]}}]},
        False
    ))

    # 29. Singular toolCall send_message with stepType TOOL_CALL missing confidence
    test_cases.append((
        "Singular toolCall send_message with stepType TOOL_CALL missing confidence",
        {"stepType": "TOOL_CALL", "toolCall": {"name": "send_message", "args": {"Message": "Report without confidence"}}},
        True
    ))

    # 30. Singular toolCall send_message with stepType TOOL_CALL valid confidence
    test_cases.append((
        "Singular toolCall send_message with stepType TOOL_CALL valid confidence",
        {"stepType": "TOOL_CALL", "toolCall": {"name": "send_message", "args": {"Message": "Report\n<confidence>HIGH</confidence>"}}},
        False
    ))

    # 31. Plural toolCalls array send_message missing confidence
    test_cases.append((
        "Plural toolCalls array send_message missing confidence",
        {"stepType": "TOOL_CALL", "toolCalls": [{"name": "send_message", "args": {"Message": "Report without confidence"}}]},
        True
    ))

    # 32. Plural toolCalls array send_message valid confidence
    test_cases.append((
        "Plural toolCalls array send_message valid confidence",
        {"stepType": "TOOL_CALL", "toolCalls": [{"name": "send_message", "args": {"Message": "Report\n<confidence>HIGH</confidence>"}}]},
        False
    ))

    # 33. Snake_case tool_calls array (OpenAI format) missing confidence
    test_cases.append((
        "Snake_case tool_calls array missing confidence",
        {"tool_calls": [{"type": "function", "function": {"name": "send_message", "arguments": json.dumps({"Message": "Report without confidence"})}}]},
        True
    ))

    # 34. Snake_case tool_calls array (OpenAI format) valid confidence
    test_cases.append((
        "Snake_case tool_calls array valid confidence",
        {"tool_calls": [{"type": "function", "function": {"name": "send_message", "arguments": json.dumps({"Message": "Report\n<confidence>HIGH</confidence>"})}}]},
        False
    ))

    # 35. Anthropic content tool_use send_message missing confidence
    test_cases.append((
        "Anthropic content tool_use send_message missing confidence",
        {"role": "assistant", "content": [{"type": "tool_use", "name": "send_message", "input": {"Message": "Anthropic report without confidence"}}]},
        True
    ))

    # 36. Anthropic content tool_use send_message valid confidence
    test_cases.append((
        "Anthropic content tool_use send_message valid confidence",
        {"role": "assistant", "content": [{"type": "tool_use", "name": "send_message", "input": {"Message": "Anthropic report\n<confidence>HIGH</confidence>"}}]},
        False
    ))

    # 37. Non-model tool calls only in turn
    test_cases.append((
        "Non-model tool calls only in turn",
        {"stepType": "TOOL_CALL", "toolCall": {"name": "run_command", "args": {"CommandLine": "dir"}}},
        False
    ))

    # 38. Multi-step turn: intermediate model step with confidence, followed by send_message WITHOUT confidence
    test_cases.append((
        "Multi-step turn: intermediate confidence overridden by send_message without confidence",
        {"steps": [
            {"type": "USER_MESSAGE", "content": "Start task"},
            {"type": "MODEL_RESPONSE", "content": "I am working on it.\n<confidence>HIGH</confidence>"},
            {"stepType": "TOOL_CALL", "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}},
            {"stepType": "TOOL_RESULT", "output": "file1 file2"},
            {"stepType": "TOOL_CALL", "toolCalls": [{"name": "send_message", "args": {"Message": "Final report missing confidence"}}]}
        ]},
        True
    ))

    # 39. Multi-step turn: intermediate tool calls followed by send_message WITH confidence
    test_cases.append((
        "Multi-step turn: intermediate tool calls followed by send_message WITH confidence",
        {"steps": [
            {"type": "USER_MESSAGE", "content": "Start task"},
            {"type": "MODEL_RESPONSE", "content": "I am working on it."},
            {"stepType": "TOOL_CALL", "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}},
            {"stepType": "TOOL_RESULT", "output": "file1 file2"},
            {"stepType": "TOOL_CALL", "toolCalls": [{"name": "send_message", "args": {"Message": "Final report\n<confidence>HIGH</confidence>"}}]}
        ]},
        False
    ))

    # 40. User-only input on stdin
    test_cases.append((
        "User-only input on stdin",
        {"type": "USER_INPUT", "content": "Hello agent"},
        False
    ))

    # 41. Empty stdin
    test_cases.append((
        "Empty stdin",
        "",
        False
    ))

    # 42. Multi-turn conversation: previous turn lacked confidence, current turn has confidence
    test_cases.append((
        "Multi-turn: previous turn lacked confidence, current turn has confidence",
        {"steps": [
            {"type": "USER_INPUT", "content": "First turn"},
            {"type": "PLANNER_RESPONSE", "content": "No confidence in turn 1"},
            {"type": "USER_INPUT", "content": "Second turn"},
            {"type": "PLANNER_RESPONSE", "content": "Turn 2 done\n<confidence>HIGH</confidence>"}
        ]},
        False
    ))

    # 43. Multi-turn conversation: previous turn had confidence, current turn lacks confidence
    test_cases.append((
        "Multi-turn: previous turn had confidence, current turn lacks confidence",
        {"steps": [
            {"type": "USER_INPUT", "content": "First turn"},
            {"type": "PLANNER_RESPONSE", "content": "Turn 1\n<confidence>HIGH</confidence>"},
            {"type": "USER_INPUT", "content": "Second turn"},
            {"type": "PLANNER_RESPONSE", "content": "Turn 2 missing confidence"}
        ]},
        True
    ))

    # 44. Session $set.messages container missing confidence
    test_cases.append((
        "Session $set.messages container missing confidence",
        {"$set": {"messages": [{"type": "user", "content": [{"text": "Hello"}]}, {"type": "model", "content": [{"text": "Response without confidence"}]}]}},
        True
    ))

    # 45. Session $set.messages container valid confidence
    test_cases.append((
        "Session $set.messages container valid confidence",
        {"$set": {"messages": [{"type": "user", "content": [{"text": "Hello"}]}, {"type": "model", "content": [{"text": "Response\n<confidence>HIGH</confidence>"}]}]}},
        False
    ))

    passed = 0
    failed = 0

    for i, (name, payload, expect_reject) in enumerate(test_cases, 1):
        if isinstance(payload, str):
            payload_str = payload
        else:
            payload_str = json.dumps(payload)
            
        out = run_watchdog_stdin(payload_str)
        is_reject = out.get("decision") == "continue"
        
        if is_reject == expect_reject:
            print(f"[{i}/{len(test_cases)}] PASS: {name}")
            passed += 1
        else:
            print(f"[{i}/{len(test_cases)}] FAIL: {name} (Expected reject={expect_reject}, got {out})")
            failed += 1

    # 46 & 47: Test transcriptPath handling
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tf_valid:
        tf_valid.write(json.dumps({"type": "USER_INPUT", "content": "Go"}) + "\n")
        tf_valid.write(json.dumps({"type": "MODEL_RESPONSE", "content": "Done!\n<confidence>HIGH</confidence>"}) + "\n")
        valid_path = tf_valid.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tf_invalid:
        tf_invalid.write(json.dumps({"type": "USER_INPUT", "content": "Go"}) + "\n")
        tf_invalid.write(json.dumps({"type": "MODEL_RESPONSE", "content": "Done without confidence"}) + "\n")
        invalid_path = tf_invalid.name

    try:
        # Valid transcriptPath
        out_v = run_watchdog_stdin(json.dumps({"transcriptPath": valid_path, "terminationReason": "model_stop"}))
        if out_v == {}:
            print(f"[{len(test_cases)+1}] PASS: transcriptPath with valid confidence")
            passed += 1
        else:
            print(f"[{len(test_cases)+1}] FAIL: transcriptPath with valid confidence (got {out_v})")
            failed += 1

        # Invalid transcriptPath
        out_iv = run_watchdog_stdin(json.dumps({"transcriptPath": invalid_path, "terminationReason": "model_stop"}))
        if out_iv.get("decision") == "continue":
            print(f"[{len(test_cases)+2}] PASS: transcriptPath missing confidence rejects")
            passed += 1
        else:
            print(f"[{len(test_cases)+2}] FAIL: transcriptPath missing confidence rejects (got {out_iv})")
            failed += 1
    finally:
        if os.path.exists(valid_path):
            os.remove(valid_path)
        if os.path.exists(invalid_path):
            os.remove(invalid_path)

    total = passed + failed
    print(f"\n==========================================")
    print(f"SUMMARY: {passed}/{total} PASSED, {failed} FAILED")
    print(f"==========================================")

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
