import time
import os
import shutil

source = r"C:\Users\noahp\.gemini\antigravity\brain\80ee3a51-58d5-4ef6-941e-f866ec0ad7d3\progress.md"
target = r"C:\Users\noahp\.gemini\antigravity\brain\03e850e0-303c-44ee-aa25-0cc709bfba8b\task.md"

print(f"Starting Real-Time Transparency Watchdog...")
print(f"Monitoring: {source}")
print(f"Mirroring to: {target}")

last_mtime = 0

while True:
    if os.path.exists(source):
        current_mtime = os.path.getmtime(source)
        if current_mtime > last_mtime:
            try:
                shutil.copy2(source, target)
                print("Mirrored progress update.")
                last_mtime = current_mtime
            except Exception as e:
                print(f"Copy failed: {e}")
    time.sleep(1.0)
