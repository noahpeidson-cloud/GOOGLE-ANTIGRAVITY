import os
import time
import sqlite3
import json

DB_FILE = r"g:\My Drive\GOOGLE ANTIGRAVITY\content_creation\editing_booth\booth_telemetry.db"
FLAG_FILE = r"g:\My Drive\GOOGLE ANTIGRAVITY\content_creation\editing_booth\REVIEW_REQUESTED.flag"
ARTIFACT_PATH = r"C:\Users\noahp\.gemini\antigravity\brain\f339feef-ff8b-48c4-bdcf-bf629367824f\Validation_Report.md"

def calculate_ml_deltas():
    if not os.path.exists(DB_FILE):
        return
        
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM edits ORDER BY timestamp DESC LIMIT 5")
        rows = c.fetchall()
        
        report = "# ML Optimization Delta Report\n\n"
        for row in rows:
            # row: id, filename, in, out, tags, notes, ai_in, ai_out, ts
            fname = row[1]
            in_pt = row[2] or 0
            ai_in = row[6] or 0
            delta = in_pt - ai_in
            report += f"- **{fname}**: User shifted IN point by `{delta:.3f}s`. Tags: {row[4]}\n"
            
        with open(ARTIFACT_PATH, 'w') as f:
            f.write(report)
            
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

print("Booth Watchdog Started. Monitoring SQLite for deltas and review requests...")

while True:
    calculate_ml_deltas()
    
    # Check for Agent Review Request
    if os.path.exists(FLAG_FILE):
        with open(FLAG_FILE, 'r') as f:
            data = json.load(f)
        
        print(f"\n[ALERT] AGENT_REVIEW_REQUESTED for file: {data.get('filename')}")
        print("Please review the Validation_Report.md and discuss styling with the user.")
        
        os.remove(FLAG_FILE)
        
    time.sleep(2)
