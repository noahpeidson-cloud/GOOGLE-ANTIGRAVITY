import os
import sqlite3
import json
from pathlib import Path
from typing import Optional

from davinci_integration import ResolvePipeline
from metadata_tracker import MediaManifestDB
from config import AssetStatus

WORKSPACE_ROOT = Path(__file__).parent.resolve()
DB_PATH = WORKSPACE_ROOT / "media_manifest.sqlite"

class EditController:
    """
    An Agent-Driven NLE controller that updates the database and triggers 
    DaVinci Resolve 'Destructive Rebuild' actions.
    """
    def __init__(self):
        self.db = MediaManifestDB(db_path=DB_PATH)
        
    def trim_clip(self, project_id: str, start_time: float, duration: float, clip_type: str = "A-Roll"):
        """Trims a clip by updating its metadata in the database."""
        asset = self.db.get_asset(project_id)
        if not asset:
            print(f"[ERROR] Asset {project_id} not found.")
            return False
            
        meta = {}
        if asset.get("metadata_json"):
            try:
                meta = json.loads(asset["metadata_json"])
            except json.JSONDecodeError:
                pass
                
        meta["start_time"] = start_time
        meta["duration"] = duration
        meta["clip_type"] = clip_type
        
        with self.db._db_connection() as conn:
            conn.execute(
                "UPDATE asset_manifest SET metadata_json = ? WHERE asset_id = ?",
                (json.dumps(meta), project_id)
            )
            conn.commit()
            
        print(f"[INFO] Trimmed clip {project_id}: start={start_time}, duration={duration}, type={clip_type}")
        return True
        
    def rebuild_resolve_timeline(self, project_name: str = "Auto Project", timeline_name: str = "Rough Cut Auto", project_id: Optional[str] = None):
        """Triggers DaVinci Resolve to delete and rebuild the timeline with new trims."""
        print(f"[INFO] Triggering DaVinci Destructive Rebuild for {timeline_name}...")
        pipeline = ResolvePipeline(DB_PATH)
        pipeline.rebuild_timeline(project_name=project_name, timeline_name=timeline_name, project_id=project_id)
        print("[SUCCESS] Timeline rebuilt.")
        
    def export_video(self, export_filename: str, social_format: str = "horizontal"):
        """Triggers DaVinci Resolve to render the final video."""
        export_path = str(WORKSPACE_ROOT / "exports" / export_filename)
        print(f"[INFO] Triggering DaVinci Export to {export_path} with format {social_format}...")
        pipeline = ResolvePipeline(DB_PATH)
        pipeline.export_video(export_path, social_format=social_format)
        print("[SUCCESS] Export triggered.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Agent Edit Controller")
    parser.add_argument("--action", type=str, required=True, choices=["trim", "rebuild", "export"])
    parser.add_argument("--id", type=str, help="Asset ID for trim")
    parser.add_argument("--start", type=float, help="Start time for trim")
    parser.add_argument("--duration", type=float, help="Duration for trim")
    parser.add_argument("--type", type=str, default="A-Roll", help="Clip type")
    parser.add_argument("--filename", type=str, default="final_export.mp4", help="Export filename")
    parser.add_argument("--project-id", type=str, help="Project ID for rebuild")
    parser.add_argument("--social-format", type=str, default="horizontal", help="Target social media format (vertical/horizontal)")
    
    args = parser.parse_args()
    
    controller = EditController()
    if args.action == "trim":
        if args.id and args.start is not None and args.duration is not None:
            controller.trim_clip(args.id, args.start, args.duration, args.type)
        else:
            print("[ERROR] Missing arguments for trim.")
    elif args.action == "rebuild":
        controller.rebuild_resolve_timeline(project_id=args.project_id)
    elif args.action == "export":
        controller.export_video(args.filename, args.social_format)
