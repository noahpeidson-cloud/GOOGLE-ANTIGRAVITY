"""Forensic Integrity Verification Script for MediaEditor (Milestone 1).
Executed independently by M1 Forensic Auditor.
"""

import ast
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Add project root and workspace to path
project_root = Path(r"G:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub").resolve()
sys.path.insert(0, str(project_root.parent))
sys.path.insert(0, str(project_root))

from ml_agent.editor import MediaEditor
import numpy as np

def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return res

def test_ast_analysis():
    print("=== CHECK 1: AST Static Analysis & Facade Detection ===")
    editor_path = project_root / "ml_agent" / "editor.py"
    with open(editor_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    
    print(f"Found {len(functions)} functions/methods in editor.py")
    
    facades = []
    for fn in functions:
        # Check if function body is just a pass, return constant, or NotImplementedError
        if len(fn.body) == 1:
            stmt = fn.body[0]
            if isinstance(stmt, ast.Pass):
                facades.append((fn.name, "empty pass"))
            elif isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
                facades.append((fn.name, f"returns constant {stmt.value.value}"))
            elif isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Call) and getattr(stmt.exc.func, 'id', '') == 'NotImplementedError':
                facades.append((fn.name, "raises NotImplementedError"))
        print(f"  [OK] Method '{fn.name}' has {len(fn.body)} AST statements")

    if facades:
        print(f"  [FAIL] Detected facade methods: {facades}")
        return False
    print("  [PASS] No facade implementations or dummy returns detected.")
    return True

def test_genuine_execution():
    print("\n=== CHECK 2: Genuine FFmpeg Execution & DSP Math Trace ===")
    editor = MediaEditor()
    print(f"  Resolved FFmpeg Binary: {editor.ffmpeg_bin}")
    assert os.path.exists(editor.ffmpeg_bin), f"FFmpeg binary missing: {editor.ffmpeg_bin}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Test 1: Generate synthetic 1080p video with audio burst at [8.0s, 12.0s]
        src_1080p = str(tmp_path / "synthetic_1080p.mp4")
        cmd_gen = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=24:duration=20",
            "-f", "lavfi", "-i", "aevalsrc=sin(2*PI*1000*t)*between(t\\,8.0\\,12.0):sample_rate=22050:duration=20",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            src_1080p
        ]
        res = subprocess.run(cmd_gen, capture_output=True, text=True)
        assert res.returncode == 0, f"Synthetic video generation failed: {res.stderr}"
        assert os.path.exists(src_1080p) and os.path.getsize(src_1080p) > 0
        print(f"  [PASS] Generated 1080p synthetic media: {os.path.getsize(src_1080p)} bytes")

        # Test probe_media
        info = editor.probe_media(src_1080p)
        print(f"  [PROBE RESULT] 1080p media: {info}")
        assert info["width"] == 1920 and info["height"] == 1080
        assert abs(info["duration"] - 20.0) < 0.2
        assert info["has_audio"] is True
        print("  [PASS] probe_media accurately measured 1920x1080, 20.0s, has_audio=True")

        # Test 2: Generate 4K video (3840x2160) to verify probe is NOT hardcoded to 1080p
        src_4k = str(tmp_path / "synthetic_4k.mp4")
        cmd_4k = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=size=3840x2160:rate=10:duration=2",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-an",
            src_4k
        ]
        res = subprocess.run(cmd_4k, capture_output=True, text=True)
        assert res.returncode == 0
        info_4k = editor.probe_media(src_4k)
        print(f"  [PROBE RESULT] 4K media: {info_4k}")
        assert info_4k["width"] == 3840 and info_4k["height"] == 2160
        assert info_4k["has_audio"] is False
        print("  [PASS] probe_media dynamic resolution extraction verified (3840x2160 != default 1080p)")

        # Test 3: Generate 9:16 vertical video (1080x1920)
        src_vert = str(tmp_path / "synthetic_vert.mp4")
        cmd_vert = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=10:duration=2",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-an",
            src_vert
        ]
        res = subprocess.run(cmd_vert, capture_output=True, text=True)
        assert res.returncode == 0
        info_vert = editor.probe_media(src_vert)
        print(f"  [PROBE RESULT] Vertical media: {info_vert}")
        assert info_vert["width"] == 1080 and info_vert["height"] == 1920
        print("  [PASS] probe_media vertical resolution extraction verified (1080x1920)")

        # Test 4: PCM Audio extraction & Signal Inspection
        pcm = editor.extract_pcm_audio(src_1080p, sample_rate=22050)
        assert len(pcm) > 0, "PCM audio extraction returned 0 bytes"
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        print(f"  Extracted {len(samples)} PCM audio samples ({len(samples)/22050:.2f}s at 22050Hz)")
        
        # Verify signal energy peak: samples between 8.0s and 12.0s should have massive energy vs silence outside
        idx_8s = int(8.0 * 22050)
        idx_12s = int(12.0 * 22050)
        burst_rms = np.sqrt(np.mean(samples[idx_8s:idx_12s] ** 2))
        outside_rms = np.sqrt(np.mean(samples[:int(7.0 * 22050)] ** 2))
        print(f"  Measured RMS - Burst [8-12s]: {burst_rms:.2f}, Outside [0-7s]: {outside_rms:.4f}")
        assert burst_rms > 1000.0, f"Expected loud audio burst RMS > 1000, got {burst_rms}"
        assert outside_rms < 10.0, f"Expected silence RMS < 10, got {outside_rms}"
        print("  [PASS] In-memory PCM streaming & acoustic energy empirically verified")

        # Test 5: Audio Peak Detection
        in_pt, out_pt = editor.detect_audio_peak(src_1080p, target_duration=15.0)
        print(f"  Detected audio peak window: [{in_pt:.2f}s, {out_pt:.2f}s]")
        assert in_pt <= 8.0, f"in_point {in_pt} is after burst start 8.0s"
        assert out_pt >= 12.0, f"out_point {out_pt} is before burst end 12.0s"
        assert abs((out_pt - in_pt) - 15.0) < 0.2
        print("  [PASS] Peak detection successfully located 15s window encapsulating the burst")

        # Test 6: Multi-peak selection (Loudness discrimination)
        src_multipeak = str(tmp_path / "multipeak.mp4")
        # Quiet tone at [2-4s] (amplitude 0.2) vs Loud tone at [14-17s] (amplitude 1.0)
        cmd_multi = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=size=640x360:rate=10:duration=25",
            "-f", "lavfi", "-i", "aevalsrc=0.2*sin(2*PI*500*t)*between(t\\,2.0\\,4.0)+sin(2*PI*1000*t)*between(t\\,14.0\\,17.0):sample_rate=22050:duration=25",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            src_multipeak
        ]
        res = subprocess.run(cmd_multi, capture_output=True, text=True)
        assert res.returncode == 0
        in_m, out_m = editor.detect_audio_peak(src_multipeak, target_duration=10.0)
        print(f"  Multi-peak detected window: [{in_m:.2f}s, {out_m:.2f}s]")
        # The 10s window must encapsulate the louder peak at [14-17s], NOT the quiet peak at [2-4s]
        assert in_m <= 14.0 and out_m >= 17.0, f"Failed to pick louder peak: got [{in_m}, {out_m}]"
        print("  [PASS] Multi-peak loudness discrimination successfully picked loudest peak")

        # Test 7: Proxy Generation & Faststart Verification
        proxy_out = str(tmp_path / "proxies" / "proxy_test.mp4")
        res_proxy = editor.generate_proxy(src_1080p, output_path=proxy_out, target_height=720)
        assert os.path.exists(res_proxy) and os.path.getsize(res_proxy) > 0
        proxy_info = editor.probe_media(res_proxy)
        print(f"  [PROXY RESULT] info: {proxy_info}, size: {os.path.getsize(res_proxy)} bytes")
        assert proxy_info["height"] == 720 and proxy_info["width"] == 1280
        assert proxy_info["has_audio"] is True
        
        # Check Faststart (+faststart places 'moov' atom before 'mdat' atom near top of file)
        with open(res_proxy, "rb") as f:
            header_bytes = f.read(4096)
            assert b"moov" in header_bytes, "Faststart verification failed: 'moov' atom not in first 4KB"
        print("  [PASS] Faststart (+faststart) atom placement verified in generated proxy binary")

        # Test 8: End-to-end generate_proxy_and_cuts
        cuts_res = editor.generate_proxy_and_cuts(src_1080p, proxy_dir=str(tmp_path / "pdir"))
        print("  [E2E RESULT] Schema validation:")
        print(f"    source_file: {cuts_res['source_file']}")
        print(f"    proxy_file: {cuts_res['proxy_file']}")
        print(f"    duration: {cuts_res['duration']}")
        print(f"    cuts keys: {list(cuts_res['cuts'].keys())}")
        assert set(cuts_res["cuts"].keys()) == {"hype_drop", "cinematic", "raw_pov"}
        assert cuts_res["cuts"]["hype_drop"]["crop_ratio"] == "9:16"
        assert cuts_res["cuts"]["cinematic"]["crop_ratio"] == "16:9"
        assert cuts_res["cuts"]["raw_pov"]["crop_ratio"] == "original"
        print("  [PASS] End-to-end metadata schema strictly conforms to PROJECT.md")

    return True

if __name__ == "__main__":
    t1 = test_ast_analysis()
    t2 = test_genuine_execution()
    print("\n==========================================")
    if t1 and t2:
        print("ALL FORENSIC VERIFICATION CHECKS PASSED: CLEAN")
    else:
        print("FORENSIC VERIFICATION FAILED: INTEGRITY VIOLATION")
