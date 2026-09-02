import os
import time
import subprocess
import threading
import firebase_admin
from firebase_admin import credentials, firestore

# Use the local Service Account JSON key you provided
cred = credentials.Certificate('credentials.json')
# Initialize with the user's project
firebase_admin.initialize_app(cred)
db = firestore.client()

def stream_logs(doc_ref, process: subprocess.Popen):
    """Reads stdout from the process and streams it to Firestore."""
    for line in iter(process.stdout.readline, b''):
        decoded_line = line.decode('utf-8').strip()
        print(f"[DAEMON_LOG] {decoded_line}")
        doc_ref.collection("logs").add({
            "timestamp": time.time(),
            "message": decoded_line
        })

    process.stdout.close()
    process.wait()
    doc_ref.update({"status": "completed"})

def handle_command(doc_snapshot, changes, read_time):
    for change in changes:
        if change.type.name == 'ADDED':
            cmd_data = change.document.to_dict()
            if cmd_data.get('status') == 'pending':
                action = cmd_data.get('action')
                print(f"[*] Received new command: {action}")
                
                # Mark as processing
                change.document.reference.update({"status": "processing"})
                
                if action == "trigger_edm_pipeline":
                    print("Executing EDM Master Mind Pipeline...")
                    change.document.reference.update({"status": "completed"})

if __name__ == '__main__':
    print("AGY Daemon starting... Connected to 'noahs-ai-bussin'.")
    commands_ref = db.collection('commands')
    commands_watch = commands_ref.on_snapshot(handle_command)
    
    while True:
        time.sleep(1)
