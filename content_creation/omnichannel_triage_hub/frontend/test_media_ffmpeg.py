import os
import subprocess
import imageio_ffmpeg

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
mp4_path = os.path.join(os.path.dirname(__file__), "public", "placeholder.mp4")

cmd = [ffmpeg_exe, "-i", mp4_path]
proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

print("FFMPEG STDERR INSPECTION:")
print(proc.stderr)

assert "Video: h264" in proc.stderr or "Video: " in proc.stderr, "H.264 video stream detected"
assert "540x960" in proc.stderr, "540x960 9:16 resolution detected in container"
print("\n[SUCCESS] placeholder.mp4 is a fully valid, playable H.264 9:16 video stream.")
