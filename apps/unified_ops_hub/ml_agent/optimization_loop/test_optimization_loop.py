import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import os
os.environ["GEMINI_API_KEY"] = "mock_key"
import sqlite3

# Import components
from hook_telemetry import capture_telemetry
from ml_evaluator import AgentMLEvaluator
from protegi_optimizer import ProtegiOptimizer

@pytest.fixture
def mock_db_path(tmp_path):
    db_file = tmp_path / "test_telemetry.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS telemetry (
        agent_id TEXT, role TEXT, input_tokens INT, output_tokens INT, 
        error_count INT, timestamp INT, transcript TEXT
    )''')
    
    # Insert 21 mock idle subagents (High input tokens, very few output tokens, no tools used)
    for i in range(21):
        cursor.execute(
            "INSERT INTO telemetry VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (f"subagent_{i}", "idle_worker", 800, 10, 0, 1600000000, "['User: Run', 'Agent: OK, I will run.']")
        )
    # Insert 5 successful subagents
    for i in range(5):
        cursor.execute(
            "INSERT INTO telemetry VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (f"subagent_success_{i}", "active_worker", 800, 450, 0, 1600000000, "['User: Run', 'Agent: Done', 'ToolCall']")
        )
        
    conn.commit()
    conn.close()
    return db_file

def test_telemetry_fetch(mock_db_path):
    evaluator = AgentMLEvaluator(db_path=mock_db_path)
    df = evaluator.fetch_traces()
    assert len(df) == 26
    
def test_ml_evaluator_anomaly_detection(mock_db_path):
    evaluator = AgentMLEvaluator(db_path=mock_db_path)
    df = evaluator.fetch_traces()
    
    # We patch out the umap/hdbscan if we just want to test the heuristic fallback
    # or let the heuristic fallback run if we didn't mock it.
    df, failure_traces = evaluator.cluster_and_detect_anomalies(df)
    
    # It should isolate the 21 idle traces
    assert len(failure_traces) == 21
    assert all(failure_traces['output_tokens'] < 50)

@patch('protegi_optimizer.Client')
def test_protegi_optimizer(mock_client_class):
    mock_client = mock_client_class.return_value
    mock_client.models.generate_content.return_value.text = "PROMPT_GRADIENT: Explicitly forbid idling."
    
    optimizer = ProtegiOptimizer()
    optimizer.client = mock_client
    
    gradient = optimizer.compute_textual_gradient("Initial prompt", ["Trace1"])
    assert "Explicitly forbid idling" in gradient
