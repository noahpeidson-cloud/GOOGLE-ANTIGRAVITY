"""
Unit test suite for ResearchValidationAgent.
Verifies categorical assignment, anti-canon empirical gates, and skill distillation.
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path
from infrastructure.research_validation_agent import ResearchValidationAgent

@pytest.fixture
def temp_agent():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_research_agent.db")
    agent = ResearchValidationAgent(db_path=db_path)
    # Redirect research dirs to tmp
    agent.research_dir = Path(tmp_dir) / "research"
    agent.sources_dir = agent.research_dir / "sources"
    agent._init_environment()
    yield agent
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

def test_categorize_source(temp_agent):
    agent = temp_agent
    assert agent.categorize_source("Building an Agent Harness in 2026") == "harness_architecture"
    assert agent.categorize_source("Context Engineering: KV Cache & Prefix Caching") == "context_engineering"
    assert agent.categorize_source("Using Git with coding agents - Simon Willison") == "dual_ide_git"
    assert agent.categorize_source("SWE-bench Verified Leaderboard 2026") == "benchmarking_evals"
    assert agent.categorize_source("8K APV Ingestion Guide & EBU R128 Audio") == "media_engineering"
    assert agent.categorize_source("Antigravity SDK Custom Skills & MCP") == "antigravity_internals"

def test_empirical_gate_pass(temp_agent):
    agent = temp_agent
    passing_code = "import sys\nsys.exit(0)\n"
    res = agent.run_empirical_gate(
        concept_name="sqlite_wal_mode_test",
        hypothesis="SQLite WAL mode provides concurrent read-write access without locks",
        domain_track="platform",
        test_script_content=passing_code
    )
    assert res["passed"] is True
    assert res["score"] == 10.0
    assert res["status"] == "VALIDATED"

    # Verify recorded in memory hub
    records = agent.memory_hub.query(topic="sqlite_wal_mode_test")
    assert len(records) == 1
    assert "VALIDATED" in records[0].finding_summary

def test_empirical_gate_fail(temp_agent):
    agent = temp_agent
    failing_code = "raise RuntimeError('Speculative daemon connection failed')\n"
    res = agent.run_empirical_gate(
        concept_name="mock_vector_daemon",
        hypothesis="Local Ollama daemon must be running for agent context",
        domain_track="platform",
        test_script_content=failing_code
    )
    assert res["passed"] is False
    assert res["status"] == "REJECTED"

    # Verify contradiction recorded
    records = agent.memory_hub.query(topic="mock_vector_daemon")
    assert len(records) == 1
    assert "CONTRADICTION" in records[0].finding_summary

def test_distill_to_skill(temp_agent):
    agent = temp_agent
    skill_path = agent.distill_to_skill(
        skill_name="test-validation-workflow",
        description="A verified research workflow for testing purposes.",
        overview="Tests the automated skill distillation pipeline.",
        workflow_steps=[
            {"title": "Inspect Raw Source", "instruction": "Check source metadata."},
            {"title": "Run Test Assertion", "instruction": "Execute loud pytest gate."}
        ],
        example_invocations=["Run the test validation workflow"]
    )
    assert skill_path.exists()
    content = skill_path.read_text(encoding="utf-8")
    assert "name: test-validation-workflow" in content
    assert "## Workflow" in content
    assert "TODO" not in content

    # Cleanup generated test skill
    shutil.rmtree(skill_path.parent, ignore_errors=True)

def test_empirical_gate_audit_hash(temp_agent):
    agent = temp_agent
    passing_code = "print('Audit verified')\n"
    res = agent.run_empirical_gate(
        concept_name="audit_hash_test",
        hypothesis="Audit hash must be deterministic SHA-256 string",
        domain_track="platform",
        test_script_content=passing_code
    )
    assert res["passed"] is True
    assert "audit_hash" in res
    assert len(res["audit_hash"]) == 64  # Valid SHA-256 hexdigest length

    # Verify metadata in memory hub includes audit_hash
    records = agent.memory_hub.query(topic="audit_hash_test")
    assert len(records) == 1
    import json
    meta = json.loads(records[0].metadata_json)
    assert meta.get("audit_hash") == res["audit_hash"]

def test_session_checkpoint_and_restore(temp_agent):
    agent = temp_agent
    session_name = "deepmind_research_session_001"
    state_payload = {
        "active_category": "harness_architecture",
        "verified_concepts": ["dual_loop_control", "kiro_crew_persistence"],
        "pending_hypotheses": ["speculative_caching"],
        "step_index": 42
    }

    ckpt = agent.checkpoint_research_session(
        session_name=session_name,
        domain_track="platform",
        state_payload=state_payload,
        token_budget_used=12500
    )
    assert "checkpoint_id" in ckpt
    assert "checkpoint_hash" in ckpt
    assert len(ckpt["checkpoint_hash"]) == 64

    # Restore session
    restored = agent.restore_research_session(session_name)
    assert restored is not None
    assert restored["session_name"] == session_name
    assert restored["domain_track"] == "platform"
    assert restored["token_budget_used"] == 12500
    assert restored["state"]["active_category"] == "harness_architecture"
    assert restored["state"]["step_index"] == 42
    assert restored["checkpoint_hash"] == ckpt["checkpoint_hash"]

def test_checkpoint_list(temp_agent):
    agent = temp_agent
    agent.checkpoint_research_session("session_a", "platform", {"v": 1})
    agent.checkpoint_research_session("session_b", "sports_cards", {"v": 2})

    all_ckpts = agent.memory_hub.list_checkpoints()
    assert len(all_ckpts) == 2

    filtered_ckpts = agent.memory_hub.list_checkpoints(session_name="session_a")
    assert len(filtered_ckpts) == 1
    assert filtered_ckpts[0]["session_name"] == "session_a"

