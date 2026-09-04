import os
from deep_scan import analyze_python_file

workspace_root = r"g:\My Drive\GOOGLE ANTIGRAVITY"
cc_dir = os.path.join(workspace_root, "content_creation")

for f in sorted(os.listdir(cc_dir)):
    full = os.path.join(cc_dir, f)
    if os.path.isfile(full) and f.endswith(".py"):
        info = analyze_python_file(full)
        print("="*60)
        print(f"FILE: {info['file']}")
        if info['ports']: print(f"  PORTS: {info['ports']}")
        if info['routes']: print(f"  ROUTES: {info['routes']}")
        if info['db_paths']: print(f"  DB PATHS: {info['db_paths']}")
        if info['subprocesses']: print(f"  SUBPROCESS: {info['subprocesses']}")
        print(f"  FLAGS: FastAPI={info['has_fastapi']}, Streamlit={info['has_streamlit']}, Uvicorn={info['has_uvicorn']}, ADB={info['has_adb']}, FFmpeg={info['has_ffmpeg']}")
