import os
import sys
import sqlite3
from pathlib import Path
from typing import List, Optional

# Constants
RESOLVE_SCRIPT_API_WINDOWS = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules"
RESOLVE_SCRIPT_API_MAC = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"

def get_resolve():
    """Initializes and returns the DaVinci Resolve object."""
    try:
        import DaVinciResolveScript as dvr_script
    except ImportError:
        # Try injecting path
        if sys.platform.startswith("win"):
            expected_path = RESOLVE_SCRIPT_API_WINDOWS
        elif sys.platform.startswith("darwin"):
            expected_path = RESOLVE_SCRIPT_API_MAC
        else:
            expected_path = "/opt/resolve/Developer/Scripting/Modules"
            
        if expected_path not in sys.path:
            sys.path.append(expected_path)
            
        try:
            import DaVinciResolveScript as dvr_script
        except ImportError:
            raise RuntimeError(
                "DaVinciResolveScript could not be found. Ensure DaVinci Resolve Studio is installed "
                "and external scripting is enabled (Preferences -> System -> General -> External scripting using: Local)."
            )

    resolve = dvr_script.scriptapp("Resolve")
    if resolve is None:
        raise RuntimeError("Could not connect to DaVinci Resolve. Is it running?")
        
    return resolve

class ResolvePipeline:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.resolve = get_resolve()
        self.project_manager = self.resolve.GetProjectManager()
        
    def _get_or_create_project(self, project_name: str):
        project = self.project_manager.LoadProject(project_name)
        if not project:
            print(f"[INFO] Creating new project: {project_name}")
            project = self.project_manager.CreateProject(project_name)
        return project

    def get_assets_from_db(self, project_id: Optional[str] = None) -> List[dict]:
        """Fetch files from the SQLite manifest."""
        import json
        assets = []
        if not self.db_path.exists():
            print("[WARNING] media_manifest.sqlite not found.")
            return assets
            
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if project_id:
                    cursor.execute(
                        "SELECT source_file_name, raw_path, brand, tier, metadata_json "
                        "FROM asset_manifest WHERE project_id = ? AND raw_path IS NOT NULL", 
                        (project_id,)
                    )
                else:
                    cursor.execute(
                        "SELECT source_file_name, raw_path, brand, tier, metadata_json "
                        "FROM asset_manifest WHERE raw_path IS NOT NULL"
                    )
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    # Parse metadata
                    meta = {}
                    if row_dict.get("metadata_json"):
                        try:
                            meta = json.loads(row_dict["metadata_json"])
                        except json.JSONDecodeError:
                            pass
                    row_dict["parsed_meta"] = meta
                    assets.append(row_dict)
        except Exception as e:
            print(f"[ERROR] DB Error: {e}")
            
        return assets

    def build_project(self, project_name: str, project_id: Optional[str] = None, framerate: int = 24, timeline_name: str = "Rough Cut Auto"):
        """Creates a project, imports assets, organizes into bins, and creates a rough cut timeline."""
        project = self._get_or_create_project(project_name)
        if not project:
            raise RuntimeError("Failed to create or load project.")
            
        # Set project settings
        project.SetSetting("timelineFrameRate", str(framerate))
        
        media_pool = project.GetMediaPool()
        root_folder = media_pool.GetRootFolder()
        
        assets = self.get_assets_from_db(project_id)
        if not assets:
            print("[INFO] No assets found in DB for this project.")
            return
            
        print(f"[INFO] Importing {len(assets)} assets into Resolve...")
        
        # Organize by Brand/Tier AND Clip Type (A-Roll vs B-Roll)
        bin_map = {}
        
        a_roll_clips = []
        b_roll_clips = []
        
        for asset in assets:
            brand = asset.get("brand") or "Unknown"
            tier = asset.get("tier") or "Tiers"
            
            # Determine A-Roll or B-Roll from parsed metadata
            clip_type = asset.get("parsed_meta", {}).get("clip_type", "A-Roll")
            
            bin_key = f"{brand}_{tier}_{clip_type}"
            
            if bin_key not in bin_map:
                new_bin = media_pool.AddSubFolder(root_folder, bin_key)
                bin_map[bin_key] = new_bin
                
            # Import file
            file_path = asset.get("raw_path")
            if file_path and os.path.exists(file_path):
                media_pool.SetCurrentFolder(bin_map[bin_key])
                imported_clips = media_pool.ImportMedia([file_path])
                
                if imported_clips:
                    clip = imported_clips[0]
                    
                    # Convert AI trim points (seconds) to frames
                    meta = asset.get("parsed_meta", {})
                    start_time = float(meta.get("start_time", 0))
                    duration = float(meta.get("duration", 0))
                    
                    if duration > 0:
                        clip_entry = {
                            "mediaPoolItem": clip,
                            "startFrame": int(start_time * framerate),
                            "endFrame": int((start_time + duration) * framerate)
                        }
                    else:
                        clip_entry = clip
                        
                    if clip_type == "A-Roll":
                        a_roll_clips.append(clip_entry)
                    else:
                        b_roll_clips.append(clip_entry)
        
        # Create rough cut timeline
        print(f"[INFO] Creating rough cut timeline '{timeline_name}' with A-Roll/B-Roll Separation...")
        
        if a_roll_clips or b_roll_clips:
            media_pool.CreateEmptyTimeline(timeline_name)
            timeline = project.GetCurrentTimeline()
            
            if a_roll_clips:
                print(f"[INFO] Appending {len(a_roll_clips)} A-Roll clips...")
                media_pool.AppendToTimeline(a_roll_clips)
                
            if b_roll_clips:
                print(f"[INFO] Appending {len(b_roll_clips)} B-Roll clips...")
                # Note: A simple AppendToTimeline will put B-Roll at the end of Track 1.
                # A more complex dict mapping is needed for precise Track 2 layering, 
                # but separating them in the bins and timeline order is a huge first step.
                media_pool.AppendToTimeline(b_roll_clips)
            
        print("[SUCCESS] DaVinci Resolve project setup complete!")

    def export_video(self, export_path: str, format: str = "mp4", preset: str = "H.264 Master", social_format: str = "horizontal"):
        """Automates the final rendering process."""
        project = self.resolve.GetProjectManager().GetCurrentProject()
        if not project:
            raise RuntimeError("No active project in DaVinci Resolve.")
            
        timeline = project.GetCurrentTimeline()
        if not timeline:
            print("[ERROR] No timeline found to export.")
            return

        # Ensure highest quality lossless setup by disabling proxies/optimized media on export
        project.SetSetting("perfProxyMediaOn", "0")
        project.SetSetting("perfOptimizedMediaOn", "0")

        # Handle Social Media Formatting
        width = 1920
        height = 1080
        
        if social_format == "vertical":
            print("[INFO] Formatting for Social Media (9:16 Vertical)...")
            width = 1080
            height = 1920
            # We must use custom settings on the timeline to allow vertical resolutions
            timeline.SetSetting("useCustomSettings", "1")
            timeline.SetSetting("timelineResolutionWidth", str(width))
            timeline.SetSetting("timelineResolutionHeight", str(height))
            # Set mismatch behavior to "Scale Full with Crop" so concert footage fills the vertical frame
            project.SetSetting("videoMonitorScaling", "crop") 
            timeline.SetSetting("timelineMismatchResolution", "ScaleToFill")

        print(f"[INFO] Configuring render job for {export_path}...")
        project.LoadRenderPreset(preset)
        
        target_dir = os.path.dirname(export_path)
        custom_name = os.path.basename(export_path).split('.')[0]
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        project.SetRenderSettings({
            "TargetDir": target_dir,
            "CustomName": custom_name,
            "FormatWidth": width,
            "FormatHeight": height,
            "PixelAspectRatio": "square"
        })
        
        job_id = project.AddRenderJob()
        if job_id:
            print(f"[INFO] Starting highest quality render at {width}x{height}...")
            project.StartRendering([job_id])
            print("[SUCCESS] Rendering started successfully.")
        else:
            print("[ERROR] Failed to add render job.")

    def rebuild_timeline(self, project_name: str, base_timeline_name: str = "Rough Cut Auto", project_id: Optional[str] = None):
        """Timeline Versioning: Creates a new incremented timeline instead of deleting old ones."""
        project = self.resolve.GetProjectManager().GetCurrentProject()
        if not project or project.GetName() != project_name:
            project = self._get_or_create_project(project_name)
            
        # Determine the next version number
        timeline_count = project.GetTimelineCount()
        highest_version = 0
        for i in range(1, timeline_count + 1):
            tl = project.GetTimelineByIndex(i)
            if tl:
                name = tl.GetName()
                if name.startswith(base_timeline_name):
                    # Expecting format "Rough Cut Auto vX"
                    parts = name.split(" v")
                    if len(parts) == 2 and parts[1].isdigit():
                        version = int(parts[1])
                        if version > highest_version:
                            highest_version = version
                    elif name == base_timeline_name and highest_version == 0:
                        highest_version = 1
                        
        next_version = highest_version + 1
        new_timeline_name = f"{base_timeline_name} v{next_version}"
        
        print(f"[INFO] Generating new versioned timeline: {new_timeline_name}...")
        
        # Build project handles creating the timeline and appending the clips safely
        self.build_project(project_name, project_id, timeline_name=new_timeline_name)


if __name__ == "__main__":
    # Test script locally
    import argparse
    parser = argparse.ArgumentParser(description="DaVinci Resolve Pipeline Setup")
    parser.add_argument("--db", type=str, default="media_manifest.sqlite", help="Path to SQLite manifest")
    parser.add_argument("--name", type=str, default="Auto Project", help="DaVinci Project Name")
    parser.add_argument("--project-id", type=str, default=None, help="Optional DB Project ID to filter by")
    args = parser.parse_args()
    
    pipeline = ResolvePipeline(Path(args.db).resolve())
    pipeline.build_project(project_name=args.name, project_id=args.project_id)
