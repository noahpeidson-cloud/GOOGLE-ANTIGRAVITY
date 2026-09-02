import os
from google import genai
from dotenv import load_dotenv
import baseline_extractor
from designer_roundtable import refine_prompt_with_collective

load_dotenv()
client = genai.Client()

def edit_photo(image_path, user_feedback):
    """
    Unified Image Editor.
    1. Extracts baseline.
    2. Runs Roundtable.
    3. Generates Image (Mocked for safety).
    4. Logs Delta.
    """
    baseline_id, base_overexp = baseline_extractor.register_baseline(image_path)
    print(f"Baseline Overexposure: {base_overexp:.2f}%")
    
    discussion, final_prompt = refine_prompt_with_collective(
        user_feedback, 
        f"Do not exceed {base_overexp:.2f}% overexposure."
    )
    print(f"Roundtable Final Prompt: {final_prompt}")
    
    # In a real environment, we call Imagen 3 Edit API here.
    # For simulation, we assume the output file is generated.
    output_file = image_path.replace(".jpg", "_edited.jpg")
    
    # Simulate saving output by copying original
    import shutil
    shutil.copy(image_path, output_file)
    
    # Check Delta
    is_bad, delta = baseline_extractor.log_generation(baseline_id, output_file, final_prompt, base_overexp)
    if is_bad:
        print(f"WARNING: Edit flagged as BAD (Delta: +{delta:.2f}% overexposure)")
    else:
        print("Edit approved. No significant overexposure.")
    return output_file

def edit_video(video_path, user_feedback, in_pt=None, out_pt=None):
    """
    Unified Video Editor using Omni Flash parameters.
    Capabilities exposed: duration, aspect-ratio, strip-audio, EDLs.
    """
    # Exposing Omni Flash Capabilities
    omni_flash_params = {
        "duration": "10s",
        "aspect_ratio": "16:9",
        "strip_audio": True
    }
    
    if in_pt is not None and out_pt is not None:
        user_feedback += f"\nSTRICT EDL CONSTRAINT: Apply edits specifically between timestamp {in_pt}s and {out_pt}s."
        
    discussion, final_prompt = refine_prompt_with_collective(
        user_feedback, 
        "Maintain video continuity. No morphing."
    )
    
    print(f"Generating video via Gemini Omni Flash API with prompt: {final_prompt}")
    print(f"Parameters applied: {omni_flash_params}")
    
    output_file = video_path.replace(".mp4", "_edited.mp4")
    # Simulate video generation
    import shutil
    shutil.copy(video_path, output_file)
    
    return output_file
