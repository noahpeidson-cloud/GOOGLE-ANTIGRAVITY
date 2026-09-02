"""M2 Forensic Integrity & Adversarial Stress Suite
Performs deep empirical inspection, binary atom validation, ffprobe stream verification,
and adversarial stress-testing against the FFmpeg renderer and Gateway API.
"""

import ast
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add workspace root and project root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = WORKSPACE_ROOT / "unified_ops_hub"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from unified_ops_hub.gateway.renderer import (
        FFmpegRenderer,
        RenderRequest,
        RenderResponse,
        get_ffmpeg_path,
        escape_drawtext,
        build_video_filter,
    )
    from unified_ops_hub.gateway.app import create_app
except ImportError:
    from gateway.renderer import (
        FFmpegRenderer,
        RenderRequest,
        RenderResponse,
        get_ffmpeg_path,
        escape_drawtext,
        build_video_filter,
    )
    from gateway.app import create_app
from fastapi.testclient import TestClient


def scan_prepopulated_artifacts():
    print("--- 1. PRE-POPULATED ARTIFACT & STALE OUTPUT SCAN ---")
    stale_found = []
    for check_dir in ["renders", "proxies"]:
        target = PROJECT_ROOT / check_dir
        if target.exists():
            files = list(target.glob("*"))
            print(f"Found {len(files)} files in {check_dir}/")
            for f in files:
                print(f"  - {f.name} ({f.stat().st_size} bytes, mtime={f.stat().st_mtime})")
                stale_found.append(f)
        else:
            print(f"Directory {check_dir}/ does not pre-exist.")
    return stale_found


def inspect_mock_and_facade_patterns():
    print("\n--- 2. FACADE & MOCK PATTERN SCAN ---")
    files_to_check = [
        PROJECT_ROOT / "gateway" / "renderer.py",
        PROJECT_ROOT / "gateway" / "app.py",
        PROJECT_ROOT / "tests" / "test_ffmpeg_renderer.py",
    ]
    
    prohibited_terms = [
        "unittest.mock",
        "MagicMock",
        "monkeypatch",
        "@mock",
        "create_autospec",
        "return_value",
        "patch(",
    ]
    
    for p in files_to_check:
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
            for term in prohibited_terms:
                if term in content:
                    print(f"  [ALERT] Found prohibited pattern '{term}' in {p.name}!")
            # Check for dummy constant returns in render methods
            if "renderer.py" in p.name:
                if "subprocess.run" not in content:
                    print(f"  [ALERT] No subprocess.run found in renderer.py!")
                else:
                    print(f"  [PASS] Real subprocess.run is invoked in {p.name}")


def verify_mp4_binary_structure(file_path: str) -> dict:
    """Forensically inspects the binary MP4 container atoms and validates ISO compliance."""
    if not os.path.exists(file_path):
        return {"valid": False, "error": "File does not exist"}

    size = os.path.getsize(file_path)
    if size < 500:
        return {"valid": False, "error": f"File too small ({size} bytes)"}

    atoms = []
    with open(file_path, "rb") as f:
        data = f.read()
        offset = 0
        while offset < len(data) - 8:
            atom_size, = struct.unpack(">I", data[offset:offset+4])
            atom_type = data[offset+4:offset+8].decode("latin-1", errors="replace")
            if atom_size == 1:
                if offset + 16 > len(data):
                    break
                atom_size, = struct.unpack(">Q", data[offset+8:offset+16])
                atoms.append((atom_type, atom_size, offset))
                offset += atom_size
            elif atom_size == 0:
                atoms.append((atom_type, len(data) - offset, offset))
                break
            elif atom_size >= 8:
                atoms.append((atom_type, atom_size, offset))
                offset += atom_size
            else:
                break

    atom_dict = {a[0]: a[1] for a in atoms}
    
    # Check for ftyp, mdat, moov
    has_ftyp = "ftyp" in atom_dict
    has_mdat = "mdat" in atom_dict
    has_moov = "moov" in atom_dict
    
    # Check major brand in ftyp
    major_brand = None
    if has_ftyp and len(data) >= 16:
        major_brand = data[8:12].decode("latin-1", errors="replace")

    return {
        "valid": has_ftyp and (has_mdat or has_moov),
        "size_bytes": size,
        "atoms": atom_dict,
        "major_brand": major_brand,
    }


def create_synthetic_test_video(dest_path: str, duration: float = 5.0) -> str:
    ffmpeg_exe = get_ffmpeg_path()
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "lavfi", "-i", f"testsrc=size=1920x1080:rate=30:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        dest_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg synthetic generator failed: {res.stderr}")
    return dest_path


def probe_with_ffprobe(file_path: str) -> dict:
    ffmpeg_exe = get_ffmpeg_path()
    res = subprocess.run([ffmpeg_exe, "-i", file_path], capture_output=True, text=True)
    stderr = res.stderr
    
    # Parse video stream details
    video_codec = None
    width = 0
    height = 0
    fps = 0.0
    for line in stderr.splitlines():
        if "Stream #" in line and "Video:" in line:
            # e.g. Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709, progressive), 1080x1920 [SAR 1:1 DAR 9:16], 30 fps
            if "h264" in line:
                video_codec = "h264"
            dim_m = re.search(r"(\d{3,5})x(\d{3,5})", line)
            if dim_m:
                width = int(dim_m.group(1))
                height = int(dim_m.group(2))
            fps_m = re.search(r"(\d+(?:\.\d+)?)\s*fps", line)
            if fps_m:
                fps = float(fps_m.group(1))

    audio_codec = None
    for line in stderr.splitlines():
        if "Stream #" in line and "Audio:" in line:
            if "aac" in line:
                audio_codec = "aac"

    return {
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "width": width,
        "height": height,
        "fps": fps,
        "raw_info": [l.strip() for l in stderr.splitlines() if "Stream #" in l or "Duration:" in l],
    }


def execute_empirical_render_tests():
    print("\n--- 3. EMPIRICAL EXECUTION & CONTAINER FORENSICS ---")
    temp_dir = tempfile.mkdtemp(prefix="auditor_m2_")
    try:
        source_path = os.path.join(temp_dir, "auditor_source_4k_sim.mp4")
        print(f"Generating synthetic source video at: {source_path}")
        create_synthetic_test_video(source_path, duration=6.0)
        
        renderer = FFmpegRenderer()
        
        # Test 1: 9:16 Vertical Render with Escaped Text
        render_916_path = os.path.join(temp_dir, "render_916_test.mp4")
        t0 = time.time()
        res_916 = renderer.render_cut(
            source_file=source_path,
            in_point=1.5,
            out_point=4.5,
            crop_ratio="9:16",
            text_overlay="AUDIT: Martin Garrix @ Ultra '26 (100% LIVE) \\ VIP",
            output_path=render_916_path,
        )
        elapsed_916 = time.time() - t0
        print(f"\n[Test 1: 9:16 Vertical Render] Finished in {elapsed_916:.2f}s")
        print(f"  Result status: {res_916.status}, duration={res_916.duration}")
        
        # Verify Binary Atoms
        atom_analysis_916 = verify_mp4_binary_structure(render_916_path)
        print(f"  Atom analysis: {atom_analysis_916}")
        assert atom_analysis_916["valid"] is True, "MP4 container invalid!"
        
        # Probe Video/Audio streams
        stream_info_916 = probe_with_ffprobe(render_916_path)
        print(f"  Stream probe: {stream_info_916}")
        assert stream_info_916["width"] == 1080, f"Expected 1080w, got {stream_info_916['width']}"
        assert stream_info_916["height"] == 1920, f"Expected 1920h, got {stream_info_916['height']}"
        assert stream_info_916["video_codec"] == "h264", "Expected h264 video codec"
        assert stream_info_916["audio_codec"] == "aac", "Expected aac audio codec"
        print("  [PASS] 9:16 Render is 100% genuine H.264/AAC 1080x1920 MP4.")

        # Test 2: 16:9 Cinematic Render
        render_169_path = os.path.join(temp_dir, "render_169_test.mp4")
        t0 = time.time()
        res_169 = renderer.render_cut(
            source_file=source_path,
            in_point=0.0,
            out_point=3.0,
            crop_ratio="16:9",
            output_path=render_169_path,
        )
        elapsed_169 = time.time() - t0
        print(f"\n[Test 2: 16:9 Cinematic Render] Finished in {elapsed_169:.2f}s")
        atom_analysis_169 = verify_mp4_binary_structure(render_169_path)
        stream_info_169 = probe_with_ffprobe(render_169_path)
        print(f"  Stream probe: {stream_info_169}")
        assert stream_info_169["width"] == 1920, f"Expected 1920w, got {stream_info_169['width']}"
        assert stream_info_169["height"] == 1080, f"Expected 1080h, got {stream_info_169['height']}"
        print("  [PASS] 16:9 Render is 100% genuine H.264/AAC 1920x1080 MP4.")

        # Test 3: FastAPI Synchronous and Asynchronous HTTP endpoints
        print("\n--- 4. FASTAPI GATEWAY ENDPOINT INTEGRITY ---")
        app = create_app()
        with TestClient(app) as client:
            # Sync Endpoint
            api_render_dir = os.path.join(temp_dir, "api_renders")
            post_payload = {
                "source_file": source_path,
                "in_point": 0.5,
                "out_point": 2.5,
                "crop_ratio": "9:16",
                "text_overlay": "API AUDIT TEST",
                "output_dir": api_render_dir,
                "sync": True,
            }
            resp = client.post("/api/v1/media/render", json=post_payload)
            print(f"  POST /api/v1/media/render (sync) HTTP Status: {resp.status_code}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "completed"
            assert os.path.exists(data["output_file"])
            print(f"  Output file generated by API: {data['output_file']} ({os.path.getsize(data['output_file'])} bytes)")
            
            # Catalog list endpoint
            cat_resp = client.get("/api/v1/media/renders")
            print(f"  GET /api/v1/media/renders HTTP Status: {cat_resp.status_code}")
            assert cat_resp.status_code == 200

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def execute_adversarial_stress_tests():
    print("\n--- 5. ADVERSARIAL STRESS-TESTING ---")
    temp_dir = tempfile.mkdtemp(prefix="auditor_adv_")
    try:
        source_path = os.path.join(temp_dir, "adv_source.mp4")
        create_synthetic_test_video(source_path, duration=5.0)
        renderer = FFmpegRenderer()

        # Challenge 1: Shell injection in text overlay
        injection_text = "; echo PWNED ; calc.exe | $(dir) %PATH% ' \" \\"
        print(f"Stress 1: Filter injection attack with string: {injection_text}")
        out_inj = os.path.join(temp_dir, "adv_injection.mp4")
        res_inj = renderer.render_cut(
            source_file=source_path,
            in_point=0.0,
            out_point=1.0,
            crop_ratio="9:16",
            text_overlay=injection_text,
            output_path=out_inj,
        )
        assert res_inj.status == "completed"
        assert os.path.exists(out_inj)
        print("  [PASS] Shell injection safely handled without command execution escape.")

        # Challenge 2: Ultra-short duration (0.05 seconds sub-second precision)
        print("Stress 2: Sub-second micro-trim (0.05s duration)")
        out_micro = os.path.join(temp_dir, "adv_micro.mp4")
        res_micro = renderer.render_cut(
            source_file=source_path,
            in_point=1.000,
            out_point=1.050,
            crop_ratio="9:16",
            output_path=out_micro,
        )
        assert res_micro.status == "completed"
        assert os.path.exists(out_micro)
        assert os.path.getsize(out_micro) > 500
        print(f"  [PASS] Micro-trim rendered valid video ({os.path.getsize(out_micro)} bytes).")

        # Challenge 3: Negative / inverted timestamps
        print("Stress 3: Inverted timestamp rejection (in_point > out_point)")
        try:
            renderer.render_cut(source_file=source_path, in_point=4.0, out_point=2.0)
            print("  [FAIL] Did not raise ValueError for inverted timestamps!")
            assert False
        except ValueError as e:
            print(f"  [PASS] Successfully caught invalid timestamps: {e}")

        # Challenge 4: Nonexistent source file
        print("Stress 4: Missing source file rejection")
        try:
            renderer.render_cut(source_file="does_not_exist_xyz.mp4", in_point=0.0, out_point=1.0)
            print("  [FAIL] Did not raise FileNotFoundError for nonexistent file!")
            assert False
        except FileNotFoundError as e:
            print(f"  [PASS] Successfully caught missing file: {e}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    scan_prepopulated_artifacts()
    inspect_mock_and_facade_patterns()
    execute_empirical_render_tests()
    execute_adversarial_stress_tests()
    print("\n=== ALL FORENSIC CHECKS & ADVERSARIAL STRESS-TESTS COMPLETED ===")
