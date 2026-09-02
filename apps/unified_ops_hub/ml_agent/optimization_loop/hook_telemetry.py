import sqlite3
import time
import json

# Fallback in case hooks.on_turn_end doesn't exist natively or isn't mocked
try:
    from google.antigravity import hooks
    decorator = hooks.on_turn_end
except (ImportError, AttributeError):
    decorator = lambda f: f

@decorator
def capture_telemetry(context, turn_result):
    # Ensure the directory exists or path is absolute in production
    conn = sqlite3.connect('telemetry_spans.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS telemetry (
        agent_id TEXT, 
        role TEXT, 
        input_tokens INT, 
        output_tokens INT, 
        error_count INT, 
        timestamp INT, 
        transcript TEXT
    )''')
    
    # Calculate telemetry metrics
    errors = len(list(turn_result.errors)) if turn_result.errors else 0
    transcript_str = json.dumps([str(m) for m in turn_result.transcript]) if turn_result.transcript else ""
    
    # Safe fallback for context properties depending on SDK version
    agent_id = getattr(context, 'agent_id', 'unknown_agent')
    behavior = getattr(context, 'agent_behavior', None)
    role = getattr(behavior, 'role', 'default_role') if behavior else 'default_role'
    
    cursor.execute(
        "INSERT INTO telemetry VALUES (?, ?, ?, ?, ?, ?, ?)", 
        (agent_id, role, 
         turn_result.usage.input_tokens, turn_result.usage.output_tokens, 
         errors, int(time.time() * 1000), transcript_str)
    )
    conn.commit()
    conn.close()
