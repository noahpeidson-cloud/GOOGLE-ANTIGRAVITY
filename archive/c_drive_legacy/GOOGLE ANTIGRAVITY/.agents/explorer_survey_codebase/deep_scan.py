import os
import re
import ast

workspace_root = r"g:\My Drive\GOOGLE ANTIGRAVITY"

def analyze_python_file(file_path):
    rel_path = os.path.relpath(file_path, workspace_root)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Find FastAPI routes
    routes = []
    route_matches = re.findall(r'@(?:app|router)\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)["\']', content)
    for method, path in route_matches:
        routes.append(f"{method.upper()} {path}")

    # Find Port references
    ports = re.findall(r'(?:port\s*[:=]\s*(\d{2,5})|localhost:(\d{2,5})|127\.0\.0\.1:(\d{2,5})|--port\s+(\d{2,5})|--server\.port\s+(\d{2,5}))', content, re.IGNORECASE)
    flat_ports = set()
    for p_tuple in ports:
        for p in p_tuple:
            if p: flat_ports.add(int(p))

    # Find SQLite DB paths
    db_paths = re.findall(r'[\'"][^\'"]*\.db[\'"]', content)

    # Find BigQuery dataset/table references
    bq_refs = re.findall(r'[\'"][a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+(?:\.[a-zA-Z0-9_\-]+)?[\'"]', content)

    # Find subprocess / server boot commands
    subprocesses = re.findall(r'subprocess\.(?:Popen|run)\s*\(\s*\[([^\]]+)\]', content)

    return {
        "file": rel_path,
        "routes": routes,
        "ports": sorted(list(flat_ports)),
        "db_paths": list(set(db_paths)),
        "subprocesses": subprocesses,
        "has_fastapi": "FastAPI" in content or "APIRouter" in content,
        "has_streamlit": "streamlit" in content or "st." in content,
        "has_uvicorn": "uvicorn" in content,
        "has_spark": "spark" in content or "pyspark" in content.lower(),
        "has_adb": "adb" in content or "ADB" in content,
        "has_ffmpeg": "ffmpeg" in content or "FFmpeg" in content,
        "has_gcs": "storage.Client" in content or "google.cloud.storage" in content or "gs://" in content,
        "has_gemini": "genai" in content or "gemini" in content.lower(),
    }

dirs_to_scan = ["content_creation", "media_pipeline", "sports_cards", "apps"]
results = []
for d in dirs_to_scan:
    base = os.path.join(workspace_root, d)
    if not os.path.exists(base):
        continue
    for root, dirs, files in os.walk(base):
        if any(x in root for x in [".agents", ".pytest_cache", "archive", "venv", "__pycache__", "node_modules"]):
            continue
        for f in files:
            if f.endswith(".py"):
                full = os.path.join(root, f)
                info = analyze_python_file(full)
                if info["routes"] or info["ports"] or info["has_fastapi"] or info["has_streamlit"] or info["has_uvicorn"] or info["has_spark"] or info["has_adb"] or "boot" in f.lower() or "daemon" in f.lower() or "pipeline" in f.lower() or "ingest" in f.lower() or "api" in f.lower() or "orchestrator" in f.lower():
                    results.append(info)

# Root files
for f in os.listdir(workspace_root):
    full = os.path.join(workspace_root, f)
    if os.path.isfile(full) and f.endswith(".py"):
        results.append(analyze_python_file(full))

for r in results:
    if r["routes"] or r["ports"] or r["has_fastapi"] or r["has_streamlit"] or r["has_uvicorn"]:
        print("="*80)
        print(f"FILE: {r['file']}")
        if r['ports']: print(f"  PORTS: {r['ports']}")
        if r['routes']: print(f"  ROUTES ({len(r['routes'])}): {r['routes']}")
        if r['db_paths']: print(f"  DB PATHS: {r['db_paths']}")
        if r['subprocesses']: print(f"  SUBPROCESS: {r['subprocesses']}")
        print(f"  FLAGS: FastAPI={r['has_fastapi']}, Streamlit={r['has_streamlit']}, Uvicorn={r['has_uvicorn']}, Spark={r['has_spark']}, ADB={r['has_adb']}, FFmpeg={r['has_ffmpeg']}, GCS={r['has_gcs']}, Gemini={r['has_gemini']}")
