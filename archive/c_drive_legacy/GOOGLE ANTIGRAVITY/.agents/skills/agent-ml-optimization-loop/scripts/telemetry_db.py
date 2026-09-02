import sqlite3
import time
import os

def init_telemetry_db():
    """
    Initializes the SQLite database used by the agent-ml-optimization-loop.
    This database tracks token spans, error counts, and semantic drift.
    """
    db_path = 'telemetry_spans.db'
    
    # Ensure directory exists if we eventually move this to a specific path
    # os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS telemetry
                      (agent_id TEXT, domain_track TEXT, input_tokens INT, 
                       output_tokens INT, error_count INT, timestamp INT, transcript TEXT)''')
    conn.commit()
    return conn

def log_telemetry_span(conn, agent_id, domain, in_tokens, out_tokens, errors, transcript):
    """
    Logs a single execution span for future ML clustering.
    """
    cursor = conn.cursor()
    cursor.execute("INSERT INTO telemetry VALUES (?, ?, ?, ?, ?, ?, ?)", 
                   (agent_id, domain, in_tokens, out_tokens, errors, 
                    int(time.time() * 1000), transcript))
    conn.commit()

if __name__ == '__main__':
    # Initialize the database immediately on run
    print("Initializing Agent ML Optimization Loop Telemetry DB...")
    conn = init_telemetry_db()
    print("Telemetry database created/verified successfully.")
    conn.close()
