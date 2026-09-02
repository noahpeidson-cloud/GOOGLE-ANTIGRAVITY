import subprocess
import os
import shutil
import imageio_ffmpeg

def test():
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    print("Using ffmpeg:", exe)

    def run_render(crop_ratio: str, text: str):
        safe_text = text.replace('\\', '\\\\').replace("'", "\\'").replace(':', '\\:').replace('%', '\\%')
        if crop_ratio == "9:16":
            vf = "crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':x='(iw-ow)/2':y='(ih-oh)/2',scale=1080:1920"
        elif crop_ratio == "16:9":
            vf = "crop=w='min(iw,ih*16/9)':h='min(ih,iw*9/16)':x='(iw-ow)/2':y='(ih-oh)/2',scale=1920:1080"
        else:
            vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

        if safe_text:
            vf += f",drawtext=text='{safe_text}':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=h-text_h-100:box=1:boxcolor=black@0.6:boxborderw=8"

        out_name = f"test_{crop_ratio.replace(':', '_')}.mp4"
        cmd = [
            exe,
            "-f", "lavfi", "-i", "testsrc=duration=2:size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
            "-ss", "0.5",
            "-t", "1.0",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-y", out_name
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("FFMPEG ERROR:", res.stderr)
            raise RuntimeError(f"FFmpeg failed with return code {res.returncode}")
        
        size = os.path.getsize(out_name)
        print(f"Success for {crop_ratio}: file={out_name}, size={size} bytes")
        os.remove(out_name)

    run_render("9:16", "Hype Drop 9:16 - Ultra Festival")
    run_render("16:9", "Cinematic Cut 16:9 - 4K Master")
    run_render("original", "Raw POV - Original")
    print("ALL PROTOTYPE TESTS PASSED!")

if __name__ == "__main__":
    test()
