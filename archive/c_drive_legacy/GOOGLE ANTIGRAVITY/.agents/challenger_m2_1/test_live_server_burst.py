"""
test_live_server_burst.py - Live TCP Socket Multi-Threaded Stress Test
Runs an actual uvicorn server on a live localhost socket and sends 50 concurrent OS-thread requests.
"""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import requests


def get_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def main():
    port = get_free_port()
    test_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    workspace = Path(test_dir.name)

    # Create dummy orchestrator.py in workspace that runs for 1.5 seconds
    orch_script = workspace / "orchestrator.py"
    with open(orch_script, "w", encoding="utf-8") as f:
        f.write(
            "import sys, time\n"
            "print('[ORCH] Starting long pipeline job...')\n"
            "sys.stdout.flush()\n"
            "time.sleep(1.5)\n"
            "print('[ORCH] Finished successfully.')\n"
        )

    # Launch live remote_trigger server on 127.0.0.1:port with DEVNULL pipes
    server_cmd = [
        sys.executable,
        "-u",
        "remote_trigger.py",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--workspace",
        str(workspace),
    ]

    server_proc = subprocess.Popen(
        server_cmd,
        cwd=str(Path(__file__).resolve().parents[2] / "content_creation"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    base_url = f"http://127.0.0.1:{port}"

    # Wait for server to become responsive
    healthy = False
    for _ in range(30):
        try:
            r = requests.get(f"{base_url}/health", timeout=1)
            if r.status_code in (200, 503):
                healthy = True
                break
        except Exception:
            time.sleep(0.1)

    if not healthy:
        server_proc.kill()
        try:
            test_dir.cleanup()
        except Exception:
            pass
        raise RuntimeError("Server failed to start within timeout")

    try:
        # 1. Health check
        h_res = requests.get(f"{base_url}/health")
        print(f"[LIVE SERVER] Health: status={h_res.status_code}")

        # 2. 50 Concurrent OS Threads hitting /trigger-pipeline simultaneously
        print("[LIVE SERVER] Launching 50 concurrent OS threads over real TCP sockets...")
        num_threads = 50

        def post_job(i):
            t0 = time.perf_counter()
            r = requests.post(f"{base_url}/trigger-pipeline", json={"event": f"LiveBurst_{i}"}, timeout=10)
            t1 = time.perf_counter()
            return r.status_code, r.json(), (t1 - t0)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(post_job, i) for i in range(num_threads)]
            results = [f.result() for f in futures]

        status_codes = [r[0] for r in results]
        latencies_ms = [r[2] * 1000.0 for r in results]

        accepted_count = status_codes.count(202)
        conflict_count = status_codes.count(409)

        print(f"[LIVE SERVER] Results: 202 Accepted = {accepted_count}, 409 Conflict = {conflict_count}")
        print(f"[LIVE SERVER] Latencies (ms): min={min(latencies_ms):.2f}, max={max(latencies_ms):.2f}, avg={sum(latencies_ms)/len(latencies_ms):.2f}")

        assert accepted_count == 1, f"Expected 1 accepted, got {accepted_count}"
        assert conflict_count == num_threads - 1, f"Expected {num_threads - 1} conflicts, got {conflict_count}"

        winning_job = [r[1] for r in results if r[0] == 202][0]
        winning_job_id = winning_job["job_id"]

        for r in results:
            if r[0] == 409:
                assert r[1]["status"] == "conflict"
                assert r[1]["current_job_id"] == winning_job_id

        # 3. Status check while running
        st = requests.get(f"{base_url}/status").json()
        print(f"[LIVE SERVER] Status while running: state={st['state']}, is_running={st['is_running']}, current_job_id={st['current_job_id']}")
        assert st["is_running"] is True
        assert st["current_job_id"] == winning_job_id

        # 4. Cancel the active job
        print(f"[LIVE SERVER] Cancelling active job {winning_job_id}...")
        c_res = requests.post(f"{base_url}/cancel")
        print(f"[LIVE SERVER] Cancel response: {c_res.status_code}, {c_res.json()}")
        assert c_res.status_code == 200
        assert c_res.json()["status"] == "cancelled"
        assert c_res.json()["job_id"] == winning_job_id

        # 5. Verify status after cancellation
        time.sleep(0.3)
        st2 = requests.get(f"{base_url}/status").json()
        print(f"[LIVE SERVER] Status after cancel: state={st2['state']}, is_running={st2['is_running']}, last_job_state={st2['last_job']['state']}")
        assert st2["is_running"] is False
        assert st2["state"] == "idle"
        assert st2["last_job"]["state"] == "cancelled"

        # 6. Verify immediately triggering a new job works after cancellation
        r_new = requests.post(f"{base_url}/trigger-pipeline", json={"event": "AfterCancelJob"})
        assert r_new.status_code == 202
        new_job_id = r_new.json()["job_id"]
        print(f"[LIVE SERVER] Successfully launched new job after cancel: {new_job_id}")

        # Cancel the second job as well
        requests.post(f"{base_url}/cancel")

        # 7. Check logs retrieval
        logs_res = requests.get(f"{base_url}/logs?tail=10").json()
        print(f"[LIVE SERVER] Logs retrieved ({logs_res['total_lines']} lines)")

        print("\n[LIVE SERVER] ALL LIVE TCP ADVERSARIAL ASSERTIONS PASSED PERFECTLY!")

    finally:
        server_proc.kill()
        try:
            test_dir.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    main()
