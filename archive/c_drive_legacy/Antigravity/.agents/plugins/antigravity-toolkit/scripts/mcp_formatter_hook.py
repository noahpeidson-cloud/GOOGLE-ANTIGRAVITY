import sys
import json
import re

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data:
            print(json.dumps({"decision": "allow"}))
            return
            
        payload = json.loads(input_data)
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})
        
        target_file = args.get("TargetFile", "")
        if "mcp_config.json" not in target_file:
            print(json.dumps({"decision": "allow"}))
            return

        # Check CodeContent (for write_to_file) or ReplacementContent (for replace_file_content)
        content = args.get("CodeContent", args.get("ReplacementContent", ""))
        
        if not content:
            print(json.dumps({"decision": "allow"}))
            return
            
        # Very basic check: are there literal escaped quotes inside an args array in the JSON?
        # e.g., "\"@toolbox-sdk/server@>=1.1.0\""
        if '"\\"' in content or '\\""' in content:
            # We deny it, enforcing the rule
            print(json.dumps({
                "decision": "deny",
                "reason": "MCP Configuration Formatting Rule Violation: Package names in the args array must not contain literal escaped double quotes. Do not double-quote strings."
            }))
            return

        print(json.dumps({"decision": "allow"}))

    except Exception as e:
        # Fail open
        print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
