import os
import json
import time
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
import imageio_ffmpeg

load_dotenv()

def generate_proxy(video_path: str) -> str:
    """Generates a low-bitrate 720p proxy using the local FFmpeg binary."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    video_path_obj = Path(video_path)
    proxy_dir = video_path_obj.parent / "temp_proxy"
    proxy_dir.mkdir(exist_ok=True)
    
    proxy_path = proxy_dir / f"{video_path_obj.stem}_proxy.mp4"
    
    # Generate 720p 30fps proxy, overriding if exists
    print(f"Generating FFmpeg proxy for {video_path_obj.name}...")
    subprocess.run([
        ffmpeg_exe, "-y", "-i", video_path, 
        "-vf", "scale=-2:720", "-r", "30",
        "-b:v", "1M", "-b:a", "128k", 
        str(proxy_path)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    return str(proxy_path)

def tag_video(video_path: str) -> dict:
    """Generates a proxy, uploads it, and tags it using gemini-3.1-pro-preview."""
    client = genai.Client()
    
    # 1. Generate Proxy
    proxy_path = generate_proxy(video_path)
    
    print(f"Uploading proxy {proxy_path} to Gemini...")
    uploaded_file = client.files.upload(file=proxy_path)
    
    # Wait for processing
    print("Waiting for video processing...")
    while True:
        file_info = client.files.get(name=uploaded_file.name)
        if file_info.state.name == "ACTIVE":
            break
        elif file_info.state.name == "FAILED":
            raise Exception("Video processing failed.")
        time.sleep(5)
        
    print("Video processed. Running tag extraction...")
    
    prompt = """
    Analyze this video and output a JSON object adhering to this 4-layer taxonomy:
    1. domain: The high-level category (e.g., 'EDM', 'Sports Cards', 'Travel').
    2. entity: The specific subject (e.g., 'Excision', 'Zeds Dead').
    3. viral_features: Array of strings detailing trending hooks (e.g., ['Heavy_Lasers', 'Bass_Drop_0:15', 'Crowd_Pan']).
    4. technical: Object with quality metrics (e.g., {'lighting': 'dark', 'audio_clipping': true}).
    
    Return ONLY raw JSON.
    """
    
    # Exponential backoff loop for 503 errors
    max_retries = 5
    base_delay = 5
    response_text = ""
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.1-pro-preview',
                contents=[
                    uploaded_file,
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            response_text = response.text
            break
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e).upper() or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e).upper():
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    print(f"503 Service Unavailable. Retrying in {sleep_time} seconds (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(sleep_time)
                else:
                    client.files.delete(name=uploaded_file.name)
                    raise Exception(f"Failed after {max_retries} retries due to 503 overload.") from e
            else:
                client.files.delete(name=uploaded_file.name)
                os.remove(proxy_path)
                raise e
                
    # Clean up the file from Google's servers and local proxy
    client.files.delete(name=uploaded_file.name)
    os.remove(proxy_path)
    
    return json.loads(response_text)

if __name__ == "__main__":
    # Test script if executed directly
    print("Gemini Tagger Ready.")
