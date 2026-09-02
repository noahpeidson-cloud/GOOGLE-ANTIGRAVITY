import sys
import json

def main():
    payload = sys.stdin.read()
    try:
        data = json.loads(payload)
        tool_call = data.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        
        # Explicitly deny network tools to prevent prompt injection exfiltration
        if tool_name in ["read_url_content", "search_web", "call_mcp_tool"]:
            if "network" in str(tool_call).lower():
                print(json.dumps({"decision": "deny", "reason": "Network egress blocked in Dev Mode."}))
                return

        # Allow local sandbox execution silently
        print(json.dumps({"decision": "allow"}))
    except Exception as e:
        print(json.dumps({"decision": "ask", "reason": "Failed to parse hook payload."}))

if __name__ == "__main__":
    main()
