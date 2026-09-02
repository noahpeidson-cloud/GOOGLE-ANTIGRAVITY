import os
import re

ROOT_DIR = r"G:\My Drive\GOOGLE ANTIGRAVITY"
TARGET_FOLDERS = [
    "apps", "brain_link", "content_creation", "local_daemon", "media_pipeline",
    "omnichannel_triage_hub", "photos_triage_project", "quick_share_ai_loop",
    "sports_cards", "tests", "travel_and_life", "unified_ops_hub", "workspace_database"
]

EXCLUDE_PARTS = {"node_modules", ".git", ".venv", "venv", ".archive", "archive", ".pytest_cache", "dist", "build", "__pycache__"}
EXCLUDE_EXTS = {".png", ".jpg", ".jpeg", ".mp4", ".tsbuildinfo", ".db", ".sqlite", ".sqlite3", ".pyc", ".log", ".gif", ".ico", ".pdf"}

PATTERNS = [
    re.compile(r"dataconnect", re.IGNORECASE),
    re.compile(r"video_tags", re.IGNORECASE),
    re.compile(r"VideoTag", re.IGNORECASE),
    re.compile(r"omnichannel[-_]service", re.IGNORECASE),
    re.compile(r"omnichannel[-_]connector", re.IGNORECASE),
    re.compile(r"omnichannel[-_]db", re.IGNORECASE),
    re.compile(r"omnichannel[-_]postgres", re.IGNORECASE),
    re.compile(r"ListVideoTags", re.IGNORECASE),
    re.compile(r"GetVideoTag", re.IGNORECASE),
    re.compile(r"CreateVideoTag", re.IGNORECASE),
]

def scan():
    # Scan root files first
    print("--- Scanning Root Files ---")
    for file in os.listdir(ROOT_DIR):
        full_path = os.path.join(ROOT_DIR, file)
        if os.path.isfile(full_path):
            ext = os.path.splitext(file)[1].lower()
            if ext in EXCLUDE_EXTS:
                continue
            scan_file(full_path, file)

    for folder in TARGET_FOLDERS:
        folder_path = os.path.join(ROOT_DIR, folder)
        if not os.path.exists(folder_path):
            continue
        print(f"--- Scanning Folder: {folder} ---")
        for root, dirs, files in os.walk(folder_path):
            # filter dirs
            dirs[:] = [d for d in dirs if d not in EXCLUDE_PARTS and not d.startswith(".pytest")]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in EXCLUDE_EXTS:
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ROOT_DIR)
                scan_file(full_path, rel_path)

def scan_file(filepath, rel_path):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            matches = []
            for i, line in enumerate(f, 1):
                for p in PATTERNS:
                    if p.search(line):
                        matches.append((i, line.strip()))
                        break
            if matches:
                print(f"\n[MATCH] {rel_path} ({len(matches)} matches)")
                for line_num, line in matches[:8]:
                    print(f"  L{line_num}: {line[:120]}")
                if len(matches) > 8:
                    print(f"  ... +{len(matches)-8} more")
    except Exception as e:
        pass

if __name__ == "__main__":
    scan()
