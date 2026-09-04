import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from metadata_tracker import MediaManifestDB
from config import AssetStatus

try:
    from google import genai
    from google.genai import types
    from google.cloud import storage
except ImportError:
    print("[ERROR] Required packages not installed. Run: pip install google-genai google-cloud-storage")
    sys.exit(1)

# Pydantic schema for structured output from Gemini
class TrimAnalysis(BaseModel):
    is_action_found: bool = Field(description="True if an exciting highlight was found.")
    start_time: float = Field(description="Start time of the highlight in seconds.")
    duration: float = Field(description="Duration of the highlight in seconds.")
    clip_type: str = Field(description="Classification of the clip, e.g., 'A-Roll', 'B-Roll', 'Action'")
    reasoning: str = Field(description="Brief explanation of why this segment was chosen.")


def main():
    workspace_root = Path(__file__).parent.resolve()
    load_dotenv(workspace_root / ".env")

    client = genai.Client(vertexai=True, project="local-catfish-470915-r8", location="us-central1")
    gcs_client = storage.Client(project="local-catfish-470915-r8")
    bucket_name = "video-ingestion-raw-noahp"
    bucket = gcs_client.bucket(bucket_name)

    db_path = workspace_root / "media_manifest.sqlite"
    db = MediaManifestDB(db_path=db_path)

    assets = db.list_assets(status=AssetStatus.AWAITING_REVIEW)
    if not assets:
        print("[INFO] No assets found in AWAITING_REVIEW state.")
        return

    print(f"[INFO] Found {len(assets)} assets awaiting review. Starting Gemini analysis...")

    for asset in assets:
        asset_id = asset["asset_id"]
        proxy_path_str = asset.get("proxy_path")

        if not proxy_path_str:
            print(f"[WARN] No proxy_path found for {asset_id}. Skipping.")
            continue

        proxy_path = Path(proxy_path_str)
        if not proxy_path.exists():
            print(f"[WARN] Proxy file does not exist: {proxy_path}. Skipping.")
            continue
            
        metadata = asset.get("metadata", {})
        if "start_time" in metadata and "duration" in metadata:
            print(f"[INFO] Asset {asset_id} already has trim metadata. Skipping.")
            continue

        print(f"\n[INFO] Uploading proxy video for {asset_id} to GCS bucket '{bucket_name}'...")
        
        try:
            gcs_blob_name = f"gemini_temp/{asset_id}_{proxy_path.name}"
            blob = bucket.blob(gcs_blob_name)
            blob.upload_from_filename(str(proxy_path))
            
            gcs_uri = f"gs://{bucket_name}/{gcs_blob_name}"
            print(f"[INFO] Uploaded to {gcs_uri}. Analyzing highlights...")
            
            prompt = (
                "You are an expert video editor specializing in short-form content. "
                "Analyze this proxy video and find the most engaging and exciting segment "
                "(e.g., a massive beat drop, incredible laser sequence, or peak crowd energy). "
                "The segment should be roughly 10 seconds long. "
                "Return the exact start time and duration in seconds."
            )

            video_part = types.Part.from_uri(file_uri=gcs_uri, mime_type="video/mp4")

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[video_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TrimAnalysis,
                    temperature=0.2
                )
            )

            # Parse response
            analysis = json.loads(response.text)
            print(f"[INFO] Analysis for {asset_id} complete!")
            print(f"       Start Time: {analysis['start_time']}s")
            print(f"       Duration: {analysis['duration']}s")
            print(f"       Reasoning: {analysis['reasoning']}")
            
            # Update database metadata
            metadata["start_time"] = analysis["start_time"]
            metadata["duration"] = analysis["duration"]
            metadata["clip_type"] = analysis["clip_type"]
            metadata["gemini_reasoning"] = analysis["reasoning"]

            with db._db_connection() as conn:
                conn.execute(
                    "UPDATE asset_manifest SET metadata_json = ? WHERE asset_id = ?",
                    (json.dumps(metadata), asset_id)
                )
                conn.commit()

            print(f"[INFO] Saved AI metadata for {asset_id}. (Still in AWAITING_REVIEW for visual confirmation)")

        except Exception as e:
            print(f"[ERROR] Failed processing {asset_id}: {e}")

if __name__ == "__main__":
    main()
