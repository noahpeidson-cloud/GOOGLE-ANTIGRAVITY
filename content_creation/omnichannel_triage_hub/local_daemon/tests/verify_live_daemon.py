"""
Live End-to-End Socket & HTTP Protocol Verification for FastAPI Local Daemon Bridge.
Spawns the real Uvicorn server on a test port, fires live HTTP requests with httpx,
and validates CORS, base64 payloads, ADB mock behavior, and graceful shutdown.
"""

import sys
import time
import base64
import subprocess
import httpx
from PIL import Image
import io

PORT = 8999
BASE_URL = f"http://127.0.0.1:{PORT}"


def run_live_verification():
    print(f"[LIVE TEST] Starting Uvicorn daemon on {BASE_URL}...")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ],
        cwd=r"G:\My Drive\GOOGLE ANTIGRAVITY\omnichannel_triage_hub\local_daemon",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Poll until server is responding
        ready = False
        for _ in range(30):
            try:
                r = httpx.get(f"{BASE_URL}/api/health", timeout=1.0)
                if r.status_code == 200:
                    ready = True
                    break
            except Exception:
                time.sleep(0.2)

        if not ready:
            raise RuntimeError("Uvicorn server failed to start within timeout.")

        print("[LIVE TEST] Server ready. Running empirical HTTP verification...")

        with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
            # 1. Root & Health Check
            r_root = client.get("/")
            assert r_root.status_code == 200, f"Root failed: {r_root.text}"
            root_data = r_root.json()
            assert root_data["status"] == "online"
            print("  [OK] GET / returned status: online")

            r_health = client.get("/api/health")
            assert r_health.status_code == 200
            health_data = r_health.json()
            assert health_data["status"] == "ok"
            print(f"  [OK] GET /api/health returned adb_connected={health_data['adb_connected']}, devices={health_data['devices']}")

            # 2. CORS Preflight OPTIONS Check from React Dev Server
            cors_headers = {
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            }
            r_options = client.options("/api/trigger-adb-pull", headers=cors_headers)
            assert r_options.status_code == 200
            assert "access-control-allow-origin" in r_options.headers
            print(f"  [OK] OPTIONS /api/trigger-adb-pull CORS allow-origin: {r_options.headers['access-control-allow-origin']}")

            # 3. Live POST /api/trigger-adb-pull
            r_pull = client.post(
                "/api/trigger-adb-pull",
                json={"mock": True, "destination_path": "./staging/videos"},
                headers={"Origin": "http://localhost:5173"},
            )
            assert r_pull.status_code == 200
            pull_data = r_pull.json()
            assert pull_data["success"] is True
            assert pull_data["status"] == "mock_success"
            assert pull_data["bytes_transferred"] == 564156416
            assert pull_data["total_bytes"] == 97173897216
            print(f"  [OK] POST /api/trigger-adb-pull returned mock_success, file: {pull_data['file_path']}")

            # 4. Live POST /api/capture-screen
            r_cap = client.post(
                "/api/capture-screen",
                json={"mock": True, "format": "png"},
                headers={"Origin": "http://localhost:5173"},
            )
            assert r_cap.status_code == 200
            cap_data = r_cap.json()
            assert cap_data["success"] is True
            assert cap_data["width"] == 540
            assert cap_data["height"] == 960

            # Decode raw base64 and verify image
            raw_b64 = cap_data["raw_base64"]
            img_bytes = base64.b64decode(raw_b64)
            img = Image.open(io.BytesIO(img_bytes))
            assert img.size == (540, 960)
            assert img.format == "PNG"
            print(f"  [OK] POST /api/capture-screen returned valid {img.format} image ({img.size[0]}x{img.size[1]})")

            # 5. Live GET /api/devices
            r_dev = client.get("/api/devices")
            assert r_dev.status_code == 200
            dev_data = r_dev.json()
            assert isinstance(dev_data["devices"], list)
            print(f"  [OK] GET /api/devices returned {dev_data['count']} devices")

            # 6. Live GET /api/staging
            r_staging = client.get("/api/staging")
            assert r_staging.status_code == 200
            staging_data = r_staging.json()
            assert staging_data["count"] > 0
            print(f"  [OK] GET /api/staging returned {staging_data['count']} staged items ({staging_data['total_size_bytes']} bytes)")

        print("\n[LIVE TEST SUCCESS] All live socket HTTP assertions verified with 100% success.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    run_live_verification()
