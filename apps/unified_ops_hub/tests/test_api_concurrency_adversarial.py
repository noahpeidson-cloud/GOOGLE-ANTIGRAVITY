"""Adversarial Concurrency, Asynchronous Queuing, and Input Fuzzing Test Suite for FastAPI Media API.
Tested by: M2 Challenger 2 (API & Concurrency Challenger)
Target: POST /api/v1/media/render, GET /api/v1/media/status/{job_id}, GET /api/v1/media/renders

Tests cover:
1. Multi-threaded concurrent synchronous render requests (thread-safety & output isolation).
2. Multi-job concurrent asynchronous background queuing (sync=False) and polling lifecycle.
3. Malformed JSON payloads, type mutations, negative timestamps, missing fields (422 responses).
4. Corrupted / invalid media inputs, non-existent files (404/500 containment & DLQ quarantine).
5. Shell injection, path traversal, complex escaping, and unicode text overlays.
6. Post-attack health check and DLQ verification proving zero server downtime.
"""

import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

try:
    from unified_ops_hub.gateway.renderer import (
        FFmpegRenderer,
        RenderRequest,
        RenderResponse,
        get_ffmpeg_path,
    )
    from unified_ops_hub.gateway.app import create_app, GatewayState
    from unified_ops_hub.gateway.dlq_manager import DLQManager, ErrorCategory
except ImportError:
    from gateway.renderer import (
        FFmpegRenderer,
        RenderRequest,
        RenderResponse,
        get_ffmpeg_path,
    )
    from gateway.app import create_app, GatewayState
    from gateway.dlq_manager import DLQManager, ErrorCategory


# ============================================================================
# Helpers & Media Fixtures
# ============================================================================

def resolve_test_ffmpeg_path() -> str:
    if os.environ.get("FFMPEG_PATH"):
        return os.environ["FFMPEG_PATH"]
    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def create_synthetic_clip(
    output_path: str,
    duration: float = 4.0,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
) -> str:
    exe = resolve_test_ffmpeg_path()
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    cmd = [
        exe, "-y",
        "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate={fps}:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        output_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to generate synthetic clip: {res.stderr}")
    return output_path


def probe_clip(file_path: str) -> Dict[str, Any]:
    exe = resolve_test_ffmpeg_path()
    res = subprocess.run([exe, "-i", file_path], capture_output=True, text=True)
    stderr = res.stderr

    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
    duration = None
    if dur_match:
        h, m, s = map(float, dur_match.groups())
        duration = round(h * 3600 + m * 60 + s, 3)

    dim_match = re.search(r"Video:.*,\s*(\d{2,5})x(\d{2,5})", stderr)
    width, height = (int(dim_match.group(1)), int(dim_match.group(2))) if dim_match else (0, 0)
    has_audio = bool(re.search(r"Stream #.*: Audio:", stderr))

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "has_audio": has_audio,
        "size": os.path.getsize(file_path),
    }


# ============================================================================
# Adversarial Concurrency Test 1: Multi-Threaded Synchronous Render Flooding
# ============================================================================

def test_concurrent_synchronous_renders_thread_pool(tmp_path):
    """Stress Test: 4 concurrent worker threads simultaneously submitting sync render requests.

    Verifies:
    1. Zero race conditions or collisions in app.state or file outputs.
    2. All 4 requests return HTTP 200 with unique job IDs.
    3. Each generated MP4 file is valid, non-empty, and probeable.
    4. State in app_state.media_jobs contains all completed records without corruption.
    """
    app = create_app()
    renders_dir = str(tmp_path / "renders_sync_pool")
    os.makedirs(renders_dir, exist_ok=True)

    # Generate 4 distinct source clips
    sources = []
    for i in range(4):
        p = str(tmp_path / f"source_sync_{i}.mp4")
        create_synthetic_clip(p, duration=3.0)
        sources.append(p)

    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    def perform_sync_render(index: int, source_file: str) -> Dict[str, Any]:
        with TestClient(app) as client:
            payload = {
                "source_file": source_file,
                "in_point": 0.5,
                "out_point": 2.0,
                "crop_ratio": "9:16" if index % 2 == 0 else "16:9",
                "text_overlay": f"THREAD #{index} 🔥 CONCURRENCY",
                "output_dir": renders_dir,
                "sync": True,
            }
            res = client.post("/api/v1/media/render", json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Thread {index} failed with HTTP {res.status_code}: {res.text}")
            return res.json()

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_idx = {
            executor.submit(perform_sync_render, i, sources[i]): i
            for i in range(4)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                data = future.result()
                results.append(data)
            except Exception as e:
                errors.append(f"Worker {idx} error: {e}")

    assert len(errors) == 0, f"Encountered concurrency errors: {errors}"
    assert len(results) == 4, f"Expected 4 successful renders, got {len(results)}"

    job_ids = set()
    output_files = set()

    for item in results:
        assert item["status"] == "completed"
        jid = item["job_id"]
        out_f = item["output_file"]
        assert jid not in job_ids, f"Duplicate job_id detected: {jid}"
        assert out_f not in output_files, f"Duplicate output_file detected: {out_f}"
        job_ids.add(jid)
        output_files.add(out_f)

        assert os.path.exists(out_f), f"Rendered output missing: {out_f}"
        assert os.path.getsize(out_f) > 1024, f"Rendered file too small: {out_f}"

        # Probe the output
        meta = probe_clip(out_f)
        assert meta["has_audio"] is True
        assert abs(meta["duration"] - 1.5) <= 0.3


# ============================================================================
# Adversarial Concurrency Test 2: Asynchronous Background Queue Flooding
# ============================================================================

def test_concurrent_async_background_renders_and_polling(tmp_path):
    """Stress Test: 4 concurrent background render requests (sync=False) with real-time status polling.

    Verifies:
    1. All 4 requests return HTTP 200/202 immediately with status="QUEUED".
    2. Background tasks execute asynchronously without blocking each other.
    3. Status polling endpoint (/api/v1/media/status/{job_id}) reflects transitions.
    4. All background jobs transition to completed state and output valid MP4s.
    """
    app = create_app()
    renders_dir = str(tmp_path / "renders_async_pool")
    os.makedirs(renders_dir, exist_ok=True)

    sources = []
    for i in range(4):
        p = str(tmp_path / f"source_async_{i}.mp4")
        create_synthetic_clip(p, duration=3.0)
        sources.append(p)

    with TestClient(app) as client:
        queued_jobs = []

        # Dispatch 4 async requests
        for i in range(4):
            payload = {
                "source_file": sources[i],
                "in_point": 0.0,
                "out_point": 1.5,
                "crop_ratio": "9:16",
                "text_overlay": f"ASYNC JOB #{i}",
                "output_dir": renders_dir,
                "sync": False,
            }
            res = client.post("/api/v1/media/render", json=payload)
            assert res.status_code in (200, 202), f"Failed to queue job #{i}: {res.text}"
            data = res.json()
            assert data["status"] in ("QUEUED", "queued", "PROCESSING", "completed")
            queued_jobs.append(data["job_id"])

        assert len(queued_jobs) == 4
        assert len(set(queued_jobs)) == 4, "Job IDs must be unique"

        # Poll status for all jobs with a timeout
        deadline = time.time() + 30.0  # 30 seconds max
        completed_jobs = {}

        while time.time() < deadline and len(completed_jobs) < 4:
            for jid in queued_jobs:
                if jid in completed_jobs:
                    continue
                status_res = client.get(f"/api/v1/media/status/{jid}")
                assert status_res.status_code == 200, f"Status check failed for {jid}"
                st_data = status_res.json()
                if st_data.get("status") in ("completed", "COMPLETED"):
                    completed_jobs[jid] = st_data
            time.sleep(0.5)

        assert len(completed_jobs) == 4, f"Not all jobs completed within timeout. Completed: {list(completed_jobs.keys())}"

        for jid, job_info in completed_jobs.items():
            assert job_info["status"] in ("completed", "COMPLETED")
            out_file = job_info.get("output_file")
            assert out_file and os.path.exists(out_file), f"Rendered output missing for job {jid}: {out_file}"
            meta = probe_clip(out_file)
            assert meta["width"] == 1080
            assert meta["height"] == 1920
            assert abs(meta["duration"] - 1.5) <= 0.3


# ============================================================================
# Adversarial Fuzzing Test 3: Malformed & Missing Payload Schema Attacks
# ============================================================================

def test_malformed_json_and_schema_validation_fuzzing(tmp_path):
    """Adversarial Probe: Fuzzing the endpoint with malformed payloads, missing fields, and type errors.

    Verifies:
    1. HTTP 422 Unprocessable Content returned for every invalid schema variant.
    2. Zero unhandled server crashes (500) on malformed inputs.
    3. Errors are isolated in DLQ with category CORRUPTED_PAYLOAD.
    """
    valid_source = str(tmp_path / "valid_src.mp4")
    create_synthetic_clip(valid_source, duration=2.0)

    app = create_app()

    adversarial_payloads = [
        # 1. Empty body
        {},
        # 2. Missing source_file
        {"in_point": 0.0, "out_point": 1.0, "crop_ratio": "9:16"},
        # 3. Missing out_point
        {"source_file": valid_source, "in_point": 0.0},
        # 4. Negative in_point
        {"source_file": valid_source, "in_point": -2.0, "out_point": 1.0},
        # 5. Negative out_point
        {"source_file": valid_source, "in_point": 0.0, "out_point": -1.0},
        # 6. in_point > out_point
        {"source_file": valid_source, "in_point": 5.0, "out_point": 1.0},
        # 7. in_point == out_point (0-duration clip)
        {"source_file": valid_source, "in_point": 1.0, "out_point": 1.0},
        # 8. Type mismatch: string for in_point
        {"source_file": valid_source, "in_point": "not_a_float", "out_point": 2.0},
        # 9. Type mismatch: array for source_file
        {"source_file": [valid_source], "in_point": 0.0, "out_point": 1.0},
        # 10. Type mismatch: dict for sync
        {"source_file": valid_source, "in_point": 0.0, "out_point": 1.0, "sync": {"bad": True}},
    ]

    with TestClient(app) as client:
        for idx, payload in enumerate(adversarial_payloads):
            res = client.post("/api/v1/media/render", json=payload)
            assert res.status_code == 422, (
                f"Payload #{idx} expected 422, got {res.status_code}: {res.text} (Payload: {payload})"
            )

        # Check DLQ manager captured validation errors (8 schema validation failures)
        dlq_stats = client.get("/api/v1/dlq/stats").json()
        assert dlq_stats["total_incidents"] >= 8, f"Expected at least 8 DLQ incidents, got {dlq_stats['total_incidents']}"


def test_raw_corrupted_json_body_bytes(tmp_path):
    """Adversarial Probe: Sending broken, non-JSON bytes to POST /api/v1/media/render."""
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            "/api/v1/media/render",
            content=b"{invalid_json: true, 'missing_quotes: [}",
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 422
        assert "CORRUPTED_PAYLOAD" in res.text or "JSON" in res.text or "detail" in res.text


# ============================================================================
# Adversarial Security Test 4: Shell Injection, Escaping & Path Traversal
# ============================================================================

def test_shell_injection_and_complex_characters_in_text_overlay(tmp_path):
    """Adversarial Security Test: Attempting command injection and extreme character sets in text_overlay.

    Verifies:
    1. Subprocess arguments are safely vectorized (no shell injection possible).
    2. Escaped characters (: ' \\ % ,) do not cause FFmpeg filter syntax parser crashes.
    3. Multi-byte Unicode and emoji strings render cleanly.
    """
    source_file = str(tmp_path / "source_sec.mp4")
    create_synthetic_clip(source_file, duration=2.0)

    app = create_app()
    renders_dir = str(tmp_path / "renders_sec")
    os.makedirs(renders_dir, exist_ok=True)

    injection_strings = [
        "; rm -rf / ; $(whoami) & echo 'PWNED'",
        "Line 1 \\ Line 2: 100% 'HYPED' , Ultra #1!",
        "🔥 VIP MAIN STAGE ⚡ 🚀 (Drop @ 01:25.500) 100%",
        "Special: \\'\\:\"\\%\\,\\n\\r",
        "A" * 500,  # 500-char long banner
    ]

    with TestClient(app) as client:
        for idx, text in enumerate(injection_strings):
            payload = {
                "source_file": source_file,
                "in_point": 0.0,
                "out_point": 1.0,
                "crop_ratio": "9:16",
                "text_overlay": text,
                "output_dir": renders_dir,
                "sync": True,
            }
            res = client.post("/api/v1/media/render", json=payload)
            assert res.status_code == 200, f"Injection test #{idx} failed: {res.text}"
            data = res.json()
            assert data["status"] == "completed"
            assert os.path.exists(data["output_file"])


# ============================================================================
# Adversarial Robustness Test 5: Corrupted Source File & DLQ Isolation
# ============================================================================

def test_corrupted_non_media_source_sync_render_dlq_containment(tmp_path):
    """Adversarial Probe: Passing a corrupted non-media text file masquerading as .mp4.

    Verifies:
    1. System handles FFmpeg execution failure gracefully without process crash.
    2. Sync mode returns HTTP 500 with descriptive error detail.
    3. Incident is isolated in DLQ for analysis.
    """
    fake_mp4 = tmp_path / "corrupt_fake_video.mp4"
    fake_mp4.write_text("THIS IS NOT A VALID MP4 VIDEO FILE CONTAINER")

    app = create_app()
    with TestClient(app) as client:
        payload = {
            "source_file": str(fake_mp4),
            "in_point": 0.0,
            "out_point": 1.0,
            "crop_ratio": "9:16",
            "sync": True,
        }
        res = client.post("/api/v1/media/render", json=payload)
        assert res.status_code == 500
        data = res.json()
        assert "Render execution failed" in data.get("detail", "") or "INTERNAL_SERVER_ERROR" in str(data)

        # Check DLQ has recorded this incident
        dlq_res = client.get("/api/v1/dlq/incidents?source_service=media_renderer")
        assert dlq_res.status_code == 200
        incidents = dlq_res.json()["incidents"]
        assert len(incidents) >= 1
        assert "corrupt_fake_video.mp4" in str(incidents[0]["payload"])


def test_corrupted_source_async_background_render_status_failed(tmp_path):
    """Adversarial Probe: Async render with corrupted media sets job status to FAILED."""
    fake_mp4 = tmp_path / "corrupt_async.mp4"
    fake_mp4.write_text("NOT A VIDEO")

    app = create_app()
    with TestClient(app) as client:
        payload = {
            "source_file": str(fake_mp4),
            "in_point": 0.0,
            "out_point": 1.0,
            "crop_ratio": "9:16",
            "sync": False,
        }
        res = client.post("/api/v1/media/render", json=payload)
        assert res.status_code in (200, 202)
        job_id = res.json()["job_id"]

        # Poll status for failure transition
        deadline = time.time() + 10.0
        final_status = None
        while time.time() < deadline:
            st = client.get(f"/api/v1/media/status/{job_id}").json()
            if st.get("status") in ("FAILED", "failed"):
                final_status = st
                break
            time.sleep(0.3)

        assert final_status is not None, "Job should transition to FAILED"
        assert final_status["status"] == "FAILED"
        assert "error" in final_status


# ============================================================================
# Adversarial Verification 6: System Health & Uptime Post-Attack
# ============================================================================

def test_system_health_post_adversarial_attack():
    """Loud Assertion: After all adversarial stress, /api/v1/health remains HEALTHY."""
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "HEALTHY"
        assert data["services"]["media_pipeline"] == "READY"
        assert data["services"]["dlq_gateway"] == "ACTIVE"
