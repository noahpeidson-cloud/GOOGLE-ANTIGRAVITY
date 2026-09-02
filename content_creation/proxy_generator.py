import os
import sqlite3
import subprocess
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.resolve()
DB_PATH = WORKSPACE_ROOT / "media_manifest.sqlite"
PROXIES_DIR = WORKSPACE_ROOT / "02_PROXIES"

def ensure_proxy_column(conn):
    """Ensure the proxy_path column exists in the database."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(asset_manifest)")
    columns = [row[1] for row in cursor.fetchall()]
    if "proxy_path" not in columns:
        cursor.execute("ALTER TABLE asset_manifest ADD COLUMN proxy_path TEXT")
        conn.commit()

def process_video_proxy(asset):
    """Worker function to generate a proxy for a single asset."""
    asset_id = asset["asset_id"]
    source_path = Path(asset["raw_path"])
    brand = asset["brand"] or "Unknown"
    tier = asset["tier"] or "Tiers"
    
    proxy_dest_dir = PROXIES_DIR / brand / tier
    proxy_dest_dir.mkdir(parents=True, exist_ok=True)
    
    proxy_filename = source_path.stem + "_proxy.mp4"
    proxy_path = proxy_dest_dir / proxy_filename
    
    print(f"[FFMPEG] Generating proxy for {source_path.name}...")
    
    # FFmpeg command: 720p, H.264, fast preset, reasonable bitrate for web viewing
    ffmpeg_exe = r"C:\Users\noahp\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
    cmd = [
        ffmpeg_exe, "-y", "-i", str(source_path),
        "-vf", "scale=-2:720", 
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(proxy_path)
    ]
    
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        print(f"[SUCCESS] Proxy generated: {proxy_path}")
        return (asset_id, str(proxy_path), None)
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode('utf-8', errors='ignore')
        return (asset_id, None, f"FFmpeg error: {err}")
    except FileNotFoundError:
        return (asset_id, None, "FFmpeg binary not found on PATH.")

def generate_proxies():
    """Finds all raw files without a proxy and generates them in parallel."""
    if not DB_PATH.exists():
        print("[ERROR] media_manifest.sqlite not found.")
        return

    PROXIES_DIR.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_proxy_column(conn)
        
        cursor = conn.cursor()
        cursor.execute(
            "SELECT asset_id, source_file_name, raw_path, brand, tier "
            "FROM asset_manifest WHERE raw_path IS NOT NULL AND proxy_path IS NULL"
        )
        assets = [dict(row) for row in cursor.fetchall()]

    if not assets:
        print("[INFO] No new assets require proxy generation.")
        return

    print(f"[INFO] Found {len(assets)} assets requiring proxies. Starting parallel generation...")

    from concurrent.futures import ProcessPoolExecutor, as_completed
    import multiprocessing
    
    # Use max_workers = core count, but cap it to avoid killing disk I/O on large batches
    max_workers = min(multiprocessing.cpu_count(), 8)
    print(f"[INFO] Running FFmpeg across {max_workers} parallel workers...")

    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_video_proxy, asset): asset for asset in assets}
        
        for future in as_completed(futures):
            results.append(future.result())

    # Update the database with the results sequentially to avoid SQLite locking
    with sqlite3.connect(str(DB_PATH)) as conn:
        cur = conn.cursor()
        for asset_id, proxy_path, error in results:
            if proxy_path:
                cur.execute(
                    "UPDATE asset_manifest SET proxy_path = ? WHERE asset_id = ?",
                    (proxy_path, asset_id)
                )
            elif error:
                print(f"[ERROR] Proxy generation failed for asset ID {asset_id}:\n{error}")
        conn.commit()

if __name__ == "__main__":
    generate_proxies()
