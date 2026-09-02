import os
import sys
import time
import sqlite3

# Add design_arm to path so we can import the batch processor
sys.path.append(os.path.join(os.path.dirname(__file__), "media_pipeline", "design_arm"))
from batch_processor import process_media_edit

DB_FILE = r"g:\My Drive\GOOGLE ANTIGRAVITY\content_creation\editing_booth\booth_telemetry.db"
STATE_FILE = r"g:\My Drive\GOOGLE ANTIGRAVITY\daemon_state.txt"

def get_last_processed_id():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return int(f.read().strip())
    return 0

def set_last_processed_id(last_id):
    with open(STATE_FILE, 'w') as f:
        f.write(str(last_id))

def run_headless_daemon():
    print("Self-Contained Headless Orchestrator Started.")
    print("Monitoring Editing Booth SQLite for new UI edits...")
    print("Any new manual edits will automatically trigger the Omni Flash ML Generation Arm.")
    
    while True:
        if not os.path.exists(DB_FILE):
            time.sleep(5)
            continue
            
        last_id = get_last_processed_id()
        
        try:
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("SELECT id, filename, tags, notes, in_point, out_point, bounding_box FROM edits WHERE id > ? ORDER BY id ASC", (last_id,))
                rows = c.fetchall()
                
                for row in rows:
                    edit_id = row[0]
                    filename = row[1]
                    tags = row[2]
                    notes = row[3]
                    in_pt = row[4]
                    out_pt = row[5]
                    bbox = row[6]
                    
                    print(f"\n[DAEMON] Detected new UI edit (ID: {edit_id}) for {filename}")
                    print(f"[DAEMON] Handing off to ML Design Arm Pipeline...")
                    
                    try:
                        # Pass the edit straight to the ML generator!
                        process_media_edit(filename, tags, notes, in_pt, out_pt, bbox)
                    except Exception as e:
                        print(f"Error processing {filename}: {e}")
                        
                    set_last_processed_id(edit_id)
                    
        except sqlite3.OperationalError:
            pass
            
        time.sleep(3) # Poll every 3 seconds

if __name__ == "__main__":
    run_headless_daemon()
