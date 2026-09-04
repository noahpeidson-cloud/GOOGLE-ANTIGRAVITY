import os
import re
import json

workspace_root = r"g:\My Drive\GOOGLE ANTIGRAVITY"
target_dirs = ["content_creation", "media_pipeline", "sports_cards", "apps", "tests"]
exclude_dirs = {".agents", ".pytest_cache", "archive", "venv", "__pycache__", "node_modules"}

findings = []

# Also include root py files
root_files = [os.path.join(workspace_root, f) for f in os.listdir(workspace_root) if f.endswith(".py") and os.path.isfile(os.path.join(workspace_root, f))]

for td in target_dirs:
    dir_path = os.path.join(workspace_root, td)
    if not os.path.exists(dir_path):
        continue
    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
        if any(ex in root.split(os.sep) for ex in exclude_dirs):
            continue
        for f in files:
            if f.endswith(".py") or f.endswith(".json") or f.endswith(".yaml") or f.endswith(".sh") or f.endswith(".bat"):
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as file:
                        content = file.read()
                        ports = re.findall(r"(?:port\s*[:=]\s*(\d{2,5})|localhost:(\d{2,5})|127\.0\.0\.1:(\d{2,5})|--port\s+(\d{2,5})|--server\.port\s+(\d{2,5}))", content, re.IGNORECASE)
                        flattened_ports = set()
                        for p_tuple in ports:
                            for p in p_tuple:
                                if p: flattened_ports.add(int(p))
                        fastapi = "FastAPI" in content or "APIRouter" in content
                        uvicorn = "uvicorn" in content
                        streamlit = "streamlit" in content or "st." in content
                        sqlite = "sqlite3" in content or ".db" in content
                        bigquery = "bigquery" in content or "BigQuery" in content or "bq" in content
                        adb = "adb" in content or "ADB" in content
                        spark = "spark" in content or "Spark" in content or "PySpark" in content
                        ffmpeg = "ffmpeg" in content or "FFmpeg" in content
                        
                        if flattened_ports or fastapi or uvicorn or streamlit or sqlite or bigquery or adb or spark:
                            findings.append({
                                "file": os.path.relpath(path, workspace_root),
                                "ports": sorted(list(flattened_ports)),
                                "fastapi": fastapi,
                                "uvicorn": uvicorn,
                                "streamlit": streamlit,
                                "sqlite": sqlite,
                                "bigquery": bigquery,
                                "adb": adb,
                                "spark": spark,
                                "ffmpeg": ffmpeg,
                                "lines": len(content.splitlines())
                            })
                except Exception as e:
                    pass

for path in root_files:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as file:
            content = file.read()
            ports = re.findall(r"(?:port\s*[:=]\s*(\d{2,5})|localhost:(\d{2,5})|127\.0\.0\.1:(\d{2,5})|--port\s+(\d{2,5})|--server\.port\s+(\d{2,5}))", content, re.IGNORECASE)
            flattened_ports = set()
            for p_tuple in ports:
                for p in p_tuple:
                    if p: flattened_ports.add(int(p))
            fastapi = "FastAPI" in content or "APIRouter" in content
            uvicorn = "uvicorn" in content
            streamlit = "streamlit" in content or "st." in content
            sqlite = "sqlite3" in content or ".db" in content
            bigquery = "bigquery" in content or "BigQuery" in content or "bq" in content
            adb = "adb" in content or "ADB" in content
            spark = "spark" in content or "Spark" in content or "PySpark" in content
            ffmpeg = "ffmpeg" in content or "FFmpeg" in content
            
            findings.append({
                "file": os.path.relpath(path, workspace_root),
                "ports": sorted(list(flattened_ports)),
                "fastapi": fastapi,
                "uvicorn": uvicorn,
                "streamlit": streamlit,
                "sqlite": sqlite,
                "bigquery": bigquery,
                "adb": adb,
                "spark": spark,
                "ffmpeg": ffmpeg,
                "lines": len(content.splitlines())
            })
    except Exception as e:
        pass

print(json.dumps(findings, indent=2))
