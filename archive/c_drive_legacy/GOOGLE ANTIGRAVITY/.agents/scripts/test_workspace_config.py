import json
import os

def test_settings_sandbox():
    settings_path = os.path.join(os.path.dirname(__file__), '../../.gemini/settings.json')
    with open(settings_path, 'r') as f:
        settings = json.load(f)
    
    # LOUD ASSERTION: The sandbox must be enabled and network disabled
    assert settings.get("enableTerminalSandbox") is True, "FATAL: Terminal Sandbox is not enabled!"
    assert settings["tools"].get("sandboxNetworkAccess") is False, "FATAL: Network access must be restricted to block prompt injections!"
    print("PASS: Sandbox Configuration Verified.")

def test_hooks_exist():
    # LOUD ASSERTION: Hooks must point to a valid python script
    hooks_path = os.path.join(os.path.dirname(__file__), '../../.agents/hooks.json')
    with open(hooks_path, 'r') as f:
        hooks = json.load(f)
    assert "PreToolUse" in hooks, "FATAL: PreToolUse hook missing!"
    print("PASS: JSON Hook Configured.")

if __name__ == "__main__":
    test_settings_sandbox()
    test_hooks_exist()
