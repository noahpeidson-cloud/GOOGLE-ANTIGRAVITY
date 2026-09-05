import os
import sys

# Import the config from the script
import git_review_agent

def run_assertions():
    config = git_review_agent.config
    
    # Assert 1: Model is explicitly 3.1-pro
    assert config.model == "gemini-3.1-pro", f"Expected gemini-3.1-pro, got {config.model}"
    
    # Assert 2: Subagents are enabled and auditor is present
    assert config.capabilities.enable_subagents is True, "Subagents not enabled"
    assert "strict_auditor" in config.capabilities.allowed_subagents, "Auditor not in allowed_subagents"
    assert any(sub.name == "strict_auditor" for sub in config.subagents), "strict_auditor SubagentConfig missing"
    
    # Assert 3: Policies are in place
    # The default policy blocks run_command, we need to ensure there is a policy allowing it
    assert len(config.policies) == 3, f"Expected 3 policies (1 custom, 2 default), got {len(config.policies)}"
    assert config.policies[0].name == "allow_git", "Custom policy 'allow_git' is not the first policy"
    
    # Assert 4: Trigger is set
    assert len(config.triggers) == 1, "Expected exactly 1 trigger"
    
    print("All static configuration assertions passed.")

if __name__ == "__main__":
    run_assertions()
