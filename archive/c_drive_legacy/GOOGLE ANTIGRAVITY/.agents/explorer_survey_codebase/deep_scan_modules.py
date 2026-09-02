import os
import re
import json

workspace_root = r"g:\My Drive\GOOGLE ANTIGRAVITY"
from deep_scan import analyze_python_file

for mod in ["content_creation", "media_pipeline", "apps"]:
    print(f"\n=================== MODULE: {mod} ===================")
    base = os.path.join(workspace_root, mod)
    if not os.path.exists(base):
        print(f"Directory {base} does not exist")
        continue
    for root, dirs, files in os.walk(base):
        if any(x in root for x in [".agents", ".pytest_cache", "archive", "venv", "__pycache__", "node_modules"]):
            continue
        for f in files:
            if f.endswith(".py"):
                full = os.path.join(root, f)
                info = analyze_python_file(full)
                # Print everything in these modules
                print(f"\nFILE: {info['file']}")
                if info['ports']: print(f"  PORTS: {info['ports']}")
                if info['routes']: print(f"  ROUTES ({len(info['routes'])}): {info['routes']}")
                if info['db_paths']: print(f"  DB PATHS: {info['db_paths']}")
                if info['subprocesses']: print(f"  SUBPROCESS: {info['subprocesses']}")
                print(f"  FLAGS: FastAPI={info['has_fastapi']}, Streamlit={info['has_streamlit']}, Uvicorn={info['has_uvicorn']}, Spark={info['has_spark']}, ADB={info['has_adb']}, FFmpeg={info['has_ffmpeg']}, GCS={info['has_gcs']}, Gemini={info['has_gemini']}")
