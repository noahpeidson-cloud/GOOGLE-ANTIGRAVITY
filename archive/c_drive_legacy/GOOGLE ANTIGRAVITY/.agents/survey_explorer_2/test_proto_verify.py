import os
import tempfile
import shutil
import subprocess
import pytest
from fastapi.testclient import TestClient
import imageio_ffmpeg

# We can prototype the test logic to ensure zero-discretion verification
def test_prototype_verification():
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    assert os.path.isfile(exe), "FFmpeg binary must exist"
    
    # Run a test render
    temp_dir = tempfile.mkdtemp(prefix="test_renderer_proto_")
    try:
        src = os.path.join(temp_dir, "raw_sample.mp4")
        dst = os.path.join(temp_dir, "render_output.mp4")
        
        # Generate 4s test file
        subprocess.run([
            exe, "-f", "lavfi", "-i", "testsrc=duration=4:size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
            "-c:v", "libx264", "-c:a", "aac", "-y", src
        ], check=True, capture_output=True)
        
        assert os.path.exists(src)
        assert os.path.getsize(src) > 0
        
        # Test render cmd
        vf = "crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':x='(iw-ow)/2':y='(ih-oh)/2',scale=1080:1920,drawtext=text='PROTOTYPE TEST':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=h-text_h-100:box=1:boxcolor=black@0.6:boxborderw=8"
        cmd = [
            exe, "-y",
            "-ss", "1.0",
            "-t", "2.0",
            "-i", src,
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            dst
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"FFmpeg render failed: {res.stderr}"
        assert os.path.exists(dst)
        assert os.path.getsize(dst) > 0
        
        # Probe dst
        probe_res = subprocess.run([exe, "-i", dst, "-hide_banner"], capture_output=True, text=True)
        assert "1080x1920" in probe_res.stderr, "Output should be 1080x1920"
        print("Prototype test verified successfully: 1080x1920 output confirmed!")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_prototype_verification()
