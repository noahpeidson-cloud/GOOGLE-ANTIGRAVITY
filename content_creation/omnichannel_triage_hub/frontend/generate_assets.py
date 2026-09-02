import subprocess
import os
import imageio_ffmpeg

def generate_placeholder_assets():
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    out_dir = os.path.join(os.path.dirname(__file__), "public")
    os.makedirs(out_dir, exist_ok=True)
    
    mp4_path = os.path.join(out_dir, "placeholder.mp4")
    png_path = os.path.join(out_dir, "placeholder.png")

    print(f"Using FFmpeg: {ffmpeg_exe}")
    print(f"Target directory: {out_dir}")

    # Generate 9:16 MP4 (540x960, 3 seconds, 30 fps, H.264 yuv420p)
    # Using lavfi testsrc and drawbox/drawtext or mandelbrot/gradients
    # Simple, high-compatibility filter chain:
    # color background + test pattern
    vf_chain = (
        "color=c=0x0B0F17:s=540x960:d=3.0[bg];"
        "nullsrc=s=460x820:d=3.0[sub];"
        "[sub]format=rgba,drawbox=x=0:y=0:w=460:h=820:color=0x3B82F6@0.4:t=fill,"
        "drawbox=x=20:y=20:w=420:h=780:color=0x1E293B@0.8:t=fill[card];"
        "[bg][card]overlay=x=40:y=70:shortest=1"
    )

    cmd_video = [
        ffmpeg_exe,
        "-y",
        "-f", "lavfi",
        "-i", vf_chain,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-t", "3.0",
        mp4_path
    ]

    print("Executing video generation...")
    result_video = subprocess.run(cmd_video, capture_output=True, text=True)
    if result_video.returncode != 0:
        print(f"Video generation error:\n{result_video.stderr}")
        # Fallback to simple color filter if complex filter fails
        cmd_fallback = [
            ffmpeg_exe,
            "-y",
            "-f", "lavfi",
            "-i", "color=c=0x18181b:s=540x960:d=3.0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-t", "3.0",
            mp4_path
        ]
        res_fb = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if res_fb.returncode != 0:
            raise RuntimeError(f"FFmpeg fallback failed: {res_fb.stderr}")
    
    print(f"Generated {mp4_path} (size: {os.path.getsize(mp4_path)} bytes)")

    # Extract first frame as poster PNG
    cmd_png = [
        ffmpeg_exe,
        "-y",
        "-i", mp4_path,
        "-ss", "00:00:00.100",
        "-vframes", "1",
        png_path
    ]
    print("Extracting poster frame...")
    result_png = subprocess.run(cmd_png, capture_output=True, text=True)
    if result_png.returncode != 0:
        print(f"PNG extraction error:\n{result_png.stderr}")
    else:
        print(f"Generated {png_path} (size: {os.path.getsize(png_path)} bytes)")

if __name__ == "__main__":
    generate_placeholder_assets()
