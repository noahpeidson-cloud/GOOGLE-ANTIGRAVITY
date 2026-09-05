import os
import sys
import time

SRC_PATH = r"d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_orchestrator_5\progress.md"
DEST_PATH = r"C:\Users\noahp\.gemini\antigravity\brain\18970d60-5763-466b-bf68-a5b801718994\task.md"

def mirror_loop():
    last_mtime = None
    last_content = None
    
    os.makedirs(os.path.dirname(DEST_PATH), exist_ok=True)
    
    # Initialize task.md if not present
    if not os.path.exists(DEST_PATH):
        initial_content = """# Task Checklist

## Initialization
- [/] Spawning teamwork_preview_orchestrator_5
- [ ] Surveying legacy media pipeline scripts & dashboards
- [ ] Formulating extraction and vault architecture
- [ ] Extracting high-value logic to _archive_vault with frontmatter
- [ ] Verifying read-only integrity and acceptance criteria
- [ ] Independent Victory Audit
"""
        with open(DEST_PATH, "w", encoding="utf-8") as f:
            f.write(initial_content)
        last_content = initial_content

    while True:
        try:
            if os.path.exists(SRC_PATH):
                mtime = os.path.getmtime(SRC_PATH)
                if mtime != last_mtime:
                    time.sleep(1.0)  # 1.0s debounce
                    with open(SRC_PATH, "r", encoding="utf-8") as f:
                        content = f.read()
                    if content != last_content:
                        with open(DEST_PATH, "w", encoding="utf-8") as f:
                            f.write(content)
                        last_content = content
                        last_mtime = os.path.getmtime(SRC_PATH)
        except Exception as e:
            pass
        time.sleep(1.0)

if __name__ == "__main__":
    mirror_loop()
