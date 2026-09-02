import sys
import json
import os
import re

def get_fenced_code_intervals(text):
    """Find character spans of all fenced code blocks (``` or ~~~)."""
    intervals = []
    fence_re = re.compile(r'^[ ]{0,3}(`{3,}|~{3,})(.*)$')
    lines = text.splitlines(keepends=True)
    pos = 0
    in_fence = False
    fence_char = ''
    fence_len = 0
    fence_start = 0
    
    for line in lines:
        line_start = pos
        pos += len(line)
        line_stripped = line.rstrip('\r\n')
        m = fence_re.match(line_stripped)
        if not in_fence:
            if m:
                in_fence = True
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                fence_start = line_start
        else:
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len and not m.group(2).strip():
                intervals.append((fence_start, pos))
                in_fence = False
    if in_fence:
        intervals.append((fence_start, len(text)))
    return intervals

def get_indented_code_intervals(text, fenced_intervals):
    """Find character spans of lines indented by 4+ spaces or tabs (indented code blocks)."""
    intervals = []
    lines = text.splitlines(keepends=True)
    pos = 0
    for line in lines:
        line_start = pos
        pos += len(line)
        if any(fs <= line_start < fe for fs, fe in fenced_intervals):
            continue
        if re.match(r'^(?: {4,}|\t)', line):
            intervals.append((line_start, pos))
    return intervals

def get_inline_code_intervals(text, block_intervals):
    """Find character spans of inline backtick code spans outside block code."""
    intervals = []
    tick_re = re.compile(r'(`+)')
    matches = list(tick_re.finditer(text))
    i = 0
    while i < len(matches):
        m = matches[i]
        start = m.start()
        if any(bs <= start < be for bs, be in block_intervals):
            i += 1
            continue
        tick_seq = m.group(1)
        tick_len = len(tick_seq)
        j = i + 1
        found_close = False
        while j < len(matches):
            m2 = matches[j]
            if any(bs <= m2.start() < be for bs, be in block_intervals):
                j += 1
                continue
            if len(m2.group(1)) == tick_len:
                intervals.append((start, m2.end()))
                i = j + 1
                found_close = True
                break
            j += 1
        if not found_close:
            i += 1
    return intervals

def get_all_code_intervals(text):
    """Get all code intervals (fenced, indented, inline)."""
    fenced = get_fenced_code_intervals(text)
    indented = get_indented_code_intervals(text, fenced)
    block_intervals = fenced + indented
    inline = get_inline_code_intervals(text, block_intervals)
    return block_intervals + inline

def is_inside_code_structure(pos, code_intervals):
    """Check if character index `pos` falls within any code interval."""
    return any(start <= pos < end for start, end in code_intervals)

def is_inside_code_block(pos, text):
    """Check if character index `pos` in `text` is inside a markdown code block (fenced or indented)."""
    fenced = get_fenced_code_intervals(text)
    indented = get_indented_code_intervals(text, fenced)
    return any(start <= pos < end for start, end in (fenced + indented))

def is_inside_inline_code(pos, text):
    """Check if character index `pos` in `text` is inside an inline backtick code span."""
    fenced = get_fenced_code_intervals(text)
    indented = get_indented_code_intervals(text, fenced)
    inline = get_inline_code_intervals(text, fenced + indented)
    return any(start <= pos < end for start, end in inline)

def find_valid_confidence_blocks(text):
    """Find all valid, non-code confidence blocks in text."""
    if not text or not isinstance(text, str):
        return []
        
    code_intervals = get_all_code_intervals(text)
    pattern = re.compile(r'<confidence\b[^>]*>([\s\S]*?)</confidence>', re.IGNORECASE)
    valid_blocks = []
    
    for match in pattern.finditer(text):
        start_pos = match.start()
        end_pos = match.end()
        inner_text = match.group(1).strip()
        
        # Inner text must contain substantive alphanumeric content
        if not inner_text or not re.search(r'[a-zA-Z0-9]', inner_text):
            continue
            
        # Must not be inside any code structure
        if is_inside_code_structure(start_pos, code_intervals):
            continue
            
        valid_blocks.append((match, inner_text, start_pos, end_pos))
        
    return valid_blocks

def has_valid_confidence_block(text):
    """Check if the text contains a complete, non-empty, and terminal <confidence> block."""
    if not text or not isinstance(text, str):
        return False
        
    valid_blocks = find_valid_confidence_blocks(text)
    if not valid_blocks:
        return False
        
    # The last valid block must be terminal
    last_match, inner_text, start_pos, end_pos = valid_blocks[-1]
    
    # Text after </confidence> must not contain substantive alphanumeric characters
    after_text = text[end_pos:].strip()
    if after_text:
        if re.search(r'[a-zA-Z0-9]', after_text):
            return False
            
    return True

def extract_send_message_from_tc(tc):
    """Extract message string from a tool call dictionary if it is a send_message invocation."""
    if not isinstance(tc, dict):
        return ""
    name = str(tc.get("name") or tc.get("functionName") or "").lower()
    fn_obj = tc.get("function")
    if isinstance(fn_obj, dict):
        if not name:
            name = str(fn_obj.get("name") or "").lower()
        args = fn_obj.get("arguments") or fn_obj.get("args") or {}
    else:
        args = tc.get("args") or tc.get("arguments") or tc.get("input") or {}
        
    if "send_message" not in name:
        return ""
        
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            pass
            
    if isinstance(args, dict):
        for k in ("Message", "message", "content", "text", "prompt", "body"):
            val = args.get(k)
            if isinstance(val, str) and val.strip():
                return val
    elif isinstance(args, str) and args.strip():
        return args
    return ""

def extract_send_message_from_step(step):
    """Find and extract send_message content from step tool structures."""
    if not isinstance(step, dict):
        return ""
        
    # Check singular keys
    for k in ("toolCall", "tool_call", "functionCall", "function_call"):
        tc = step.get(k)
        if isinstance(tc, dict):
            res = extract_send_message_from_tc(tc)
            if res:
                return res
                
    # Check plural lists
    for k in ("toolCalls", "tool_calls", "functionCalls", "function_calls"):
        tcs = step.get(k)
        if isinstance(tcs, list):
            for tc in tcs:
                res = extract_send_message_from_tc(tc)
                if res:
                    return res
                    
    # Check parts list (Gemini proto)
    parts = step.get("parts")
    if isinstance(parts, list):
        for p in parts:
            if isinstance(p, dict):
                res = extract_send_message_from_step(p)
                if res:
                    return res
                    
    # Check content list (Anthropic tool_use or list of blocks)
    content = step.get("content")
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict):
                res = extract_send_message_from_tc(c)
                if res:
                    return res

    return ""

def has_send_message_tool_call(step):
    """Check if step contains a send_message tool call."""
    return bool(extract_send_message_from_step(step))

def is_user_step(step):
    """Check if step is explicitly from user."""
    if isinstance(step, str):
        return False
    if not isinstance(step, dict):
        return False
    step_type = str(step.get("type") or step.get("stepType") or step.get("step_type") or "").upper()
    role = str(step.get("role") or "").lower()
    if any(k in step_type for k in ("USER_INPUT", "USER_MESSAGE", "USER")):
        return True
    if role == "user":
        return True
    if "userMessage" in step or "userInput" in step:
        return True
    return False

def is_non_model_step(step):
    """Check if step is explicitly from user, tool result, or system."""
    if not isinstance(step, dict):
        return False
    if is_user_step(step):
        return True

    # If it is a send_message tool call, it represents model output to parent/user
    if has_send_message_tool_call(step):
        return False

    step_type = str(step.get("type") or step.get("stepType") or step.get("step_type") or "").upper()
    role = str(step.get("role") or "").lower()

    if any(k in step_type for k in ("TOOL_RESULT", "SYSTEM", "SESSION_INIT")):
        return True
    if role in ("system", "tool"):
        return True
    if "toolResult" in step or "error_details" in step or "tool_result" in step:
        return True
    if "sessionId" in step and "kind" in step:
        return True

    # Non-messaging tool calls
    if any(k in step_type for k in ("TOOL_CALL", "TOOL_USE")):
        return True
    if "toolCalls" in step or "toolCall" in step or "tool_calls" in step or "tool_call" in step or "functionCall" in step or "function_call" in step:
        if not ("plannerResponse" in step or "modelResponse" in step or "candidates" in step):
            return True

    return False

def is_model_step(step):
    """Determine if a step is from the model/planner rather than user/tool/system."""
    if not isinstance(step, dict):
        return False
    if is_non_model_step(step):
        return False
        
    if has_send_message_tool_call(step):
        return True

    step_type = str(step.get("type") or step.get("stepType") or step.get("step_type") or "").upper()
    role = str(step.get("role") or "").lower()

    if any(k in step_type for k in ("PLANNER_RESPONSE", "MODEL_RESPONSE", "ASSISTANT", "MODEL")):
        return True
    if role in ("model", "assistant"):
        return True
    if any(k in step for k in ("plannerResponse", "modelResponse", "candidates")):
        return True

    text = extract_text_from_step(step)
    return bool(text.strip())

def extract_text_from_step(step):
    """Recursively extract string content from various step, message, and tool formats."""
    if isinstance(step, str):
        return step
    if not isinstance(step, dict):
        return ""
    
    # 1. Send message tool call content
    msg_text = extract_send_message_from_step(step)
    if msg_text:
        return msg_text

    # 2. Direct string fields
    for field in ("text", "response", "output"):
        val = step.get(field)
        if isinstance(val, str) and val.strip():
            return val

    # 3. Content field (can be string, dict, or list of parts)
    content = step.get("content")
    if isinstance(content, str) and content.strip():
        return content
    elif isinstance(content, list):
        parts_text = [extract_text_from_step(c) for c in content]
        joined = "\n".join([p for p in parts_text if p.strip()])
        if joined.strip():
            return joined
    elif isinstance(content, dict):
        res = extract_text_from_step(content)
        if res.strip():
            return res

    # 4. Message field
    msg = step.get("message")
    if isinstance(msg, str) and msg.strip():
        return msg
    elif isinstance(msg, dict):
        res = extract_text_from_step(msg)
        if res.strip():
            return res

    # 5. Parts array (Gemini proto format)
    parts = step.get("parts")
    if isinstance(parts, list):
        extracted_parts = []
        for p in parts:
            if isinstance(p, dict):
                p_text = extract_text_from_step(p)
                if p_text:
                    extracted_parts.append(p_text)
            elif isinstance(p, str) and p.strip():
                extracted_parts.append(p)
        if extracted_parts:
            return "\n".join(extracted_parts)

    # 6. Candidates array (Gemini SDK / API structure)
    candidates = step.get("candidates")
    if isinstance(candidates, list):
        extracted_candidates = []
        for c in candidates:
            c_text = extract_text_from_step(c)
            if c_text:
                extracted_candidates.append(c_text)
        if extracted_candidates:
            return "\n".join(extracted_candidates)

    # 7. Nested object fields (plannerResponse, modelResponse)
    for parent in ("plannerResponse", "modelResponse"):
        nested = step.get(parent)
        if isinstance(nested, dict):
            res = extract_text_from_step(nested)
            if res.strip():
                return res
        elif isinstance(nested, list):
            res_list = [extract_text_from_step(item) for item in nested]
            res_str = "\n".join([r for r in res_list if r.strip()])
            if res_str.strip():
                return res_str

    return ""

def flatten_step_items(items):
    """Recursively flatten arrays, mongo-style $set wrappers, and message containers."""
    flat = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, list):
            flat.extend(flatten_step_items(item))
        elif isinstance(item, dict):
            if "$set" in item and isinstance(item["$set"], dict):
                set_obj = item["$set"]
                for k in ("messages", "steps", "transcript", "history"):
                    if k in set_obj and isinstance(set_obj[k], list):
                        flat.extend(flatten_step_items(set_obj[k]))
            elif "messages" in item and isinstance(item["messages"], list):
                flat.extend(flatten_step_items(item["messages"]))
            elif "steps" in item and isinstance(item["steps"], list):
                flat.extend(flatten_step_items(item["steps"]))
            elif "transcript" in item and isinstance(item["transcript"], list):
                flat.extend(flatten_step_items(item["transcript"]))
            elif "history" in item and isinstance(item["history"], list):
                flat.extend(flatten_step_items(item["history"]))
            else:
                flat.append(item)
        elif isinstance(item, str):
            flat.append(item)
    return flat

def parse_transcript_steps(raw_input):
    """Parse and flatten transcript steps from stdin string (JSON, JSONL, or file reference)."""
    raw_stripped = raw_input.strip()
    if not raw_stripped:
        return []

    # 1. Try parsing as a single JSON entity
    try:
        data = json.loads(raw_stripped)
        if isinstance(data, dict):
            transcript_path = data.get("transcriptPath")
            if transcript_path and os.path.exists(transcript_path):
                file_steps = []
                try:
                    with open(transcript_path, "r", encoding="utf-8") as f:
                        for line in f:
                            l = line.strip()
                            if l:
                                try:
                                    file_steps.append(json.loads(l))
                                except Exception:
                                    pass
                    if file_steps:
                        return flatten_step_items(file_steps)
                except Exception:
                    pass

            return flatten_step_items([data])
        elif isinstance(data, list):
            return flatten_step_items(data)
    except Exception:
        pass

    # 2. Try parsing line by line as JSONL
    line_steps = []
    for line in raw_stripped.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        try:
            parsed_line = json.loads(line_clean)
            line_steps.append(parsed_line)
        except Exception:
            pass

    if line_steps:
        return flatten_step_items(line_steps)

    # 3. Fallback: treat raw text as single response step
    if raw_stripped:
        return [{"type": "PLANNER_RESPONSE", "content": raw_stripped}]

    return []

def run_watchdog():
    try:
        raw_input = sys.stdin.read()
    except Exception:
        print(json.dumps({}))
        return

    if not raw_input or not raw_input.strip():
        print(json.dumps({}))
        return

    steps = parse_transcript_steps(raw_input)
    if not steps:
        print(json.dumps({}))
        return

    # Find the relevant model/planner response for the latest turn
    last_user_idx = -1
    for i, step in enumerate(steps):
        if is_user_step(step):
            last_user_idx = i

    relevant_steps = steps[last_user_idx + 1:] if last_user_idx != -1 else steps

    last_response_text = ""
    for step in relevant_steps:
        if is_model_step(step):
            text = extract_text_from_step(step)
            if text.strip():
                last_response_text = text

    # If there is no response text to evaluate (e.g. only user input or non-messaging tools), allow stop
    if not last_response_text.strip():
        print(json.dumps({}))
        return

    # Enforce R4: <confidence> block must be present and terminal
    if not has_valid_confidence_block(last_response_text):
        print(json.dumps({
            "decision": "continue",
            "reason": "CRITICAL RULE VIOLATION (R4): Your last response to the user was missing the terminal <confidence> block. You are mechanically barred from stopping. Rewrite your response and include the block."
        }))
        return

    # Valid confidence block found, allow stop
    print(json.dumps({}))

if __name__ == "__main__":
    run_watchdog()
