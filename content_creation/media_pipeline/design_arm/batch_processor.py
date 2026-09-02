import os
import glob
from unified_editor import edit_photo, edit_video
from artifact_generator import create_social_artifacts
from pandas_optimizer import analyze_telemetry_clusters
import shutil

RAW_CAMERA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "raw_ingest", "Camera"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "outputs"))

def process_media_edit(filename, tags, notes, in_pt=None, out_pt=None, bbox=None):
    """
    The Self-Contained execution loop triggered by the Editing Booth.
    1. Receives specific file and tags from Booth UI.
    2. Runs Unified Editor (Roundtable -> Baseline -> Generation)
    3. Crops Artifacts
    4. Runs Pandas K-Means Optimizer on Telemetry
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Construct raw path based on the booth's file string, assuming it's in raw_ingest
    media_path = os.path.join(RAW_CAMERA_DIR, filename)
    if not os.path.exists(media_path):
        print(f"File not found for processing: {media_path}")
        return
        
    feedback = f"User Notes: {notes} | Stylistic Tags: {tags}"
    if bbox:
        feedback += f" | Bounding Box: {bbox}"
    if in_pt is not None and out_pt is not None:
        feedback += f" | Trim EDL: {in_pt}s to {out_pt}s"
        
    print(f"\n--- Processing {filename} with feedback: {feedback} ---")
    
    if filename.lower().endswith('.jpg') or filename.lower().endswith('.png'):
        edited = edit_photo(media_path, feedback)
        
        final_path = os.path.join(OUTPUT_DIR, os.path.basename(edited))
        if os.path.exists(edited):
            shutil.move(edited, final_path)
            create_social_artifacts(final_path)
            
    elif filename.lower().endswith('.mp4'):
        edited = edit_video(media_path, feedback, in_pt, out_pt)
        
        final_path = os.path.join(OUTPUT_DIR, os.path.basename(edited))
        if os.path.exists(edited):
            shutil.move(edited, final_path)
            
    print("\n--- Running Pandas Telemetry Optimizer ---")
    analyze_telemetry_clusters()
    
    print("\n--- Processing Complete ---")
    print(f"Artifacts saved to {OUTPUT_DIR}")
