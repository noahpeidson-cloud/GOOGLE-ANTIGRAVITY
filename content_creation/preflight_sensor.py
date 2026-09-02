import os
import json
import librosa
import cv2
import numpy as np

class PreFlightSensor:
    @staticmethod
    def analyze_media(filepath: str) -> dict:
        if not os.path.exists(filepath):
            return {"error": f"File not found: {filepath}"}
            
        print(f"[PreFlightSensor] Analyzing {filepath}...")
        
        # Audio Analysis
        temp_wav = filepath + ".temp.wav"
        try:
            import subprocess
            # Extract audio to wav
            subprocess.run(["ffmpeg", "-y", "-i", filepath, "-vn", "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1", temp_wav], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                           
            # Load audio. sr=None keeps original sample rate (we already resampled to 22050)
            y, sr = librosa.load(temp_wav, sr=None)
            
            # Estimate BPM and beat frames
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            
            # Convert beat frames to timestamps (seconds)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            
            # Limit to first 20 beats if there are too many to keep the LLM context clean
            major_beats = [round(float(t), 2) for t in beat_times[:20]]
            
            bpm = round(float(tempo[0] if isinstance(tempo, (list, np.ndarray)) else tempo), 1)
        except Exception as e:
            bpm = 0
            major_beats = []
            print(f"[PreFlightSensor] Audio analysis failed: {e}")
        finally:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except:
                    pass
            
        # Video Analysis
        try:
            cap = cv2.VideoCapture(filepath)
            brightness_sum = 0
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                # Skip frames to speed up analysis (e.g. sample 1 every 10 frames)
                if frame_count % 10 == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    brightness_sum += np.mean(gray)
                
                frame_count += 1
                
                # Limit to 300 frames to avoid long processing for huge videos
                if frame_count >= 300:
                    break
                    
            cap.release()
            
            avg_brightness = 0
            if frame_count > 0:
                sampled_frames = (frame_count - 1) // 10 + 1
                avg_brightness = round(float(brightness_sum / sampled_frames), 1)
                
        except Exception as e:
            avg_brightness = 0
            print(f"[PreFlightSensor] Video analysis failed: {e}")
            
        return {
            "bpm": bpm,
            "major_beats_sec": major_beats,
            "avg_brightness_out_of_255": avg_brightness
        }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(PreFlightSensor.analyze_media(sys.argv[1]), indent=2))
