import os
import sys
import json
import requests
from google.cloud import storage
import datetime
from dotenv import load_dotenv

# R26: The Background Daemon Auth Guardrail
# Must explicitly load .env file to prevent runtime auth crashes
load_dotenv()

def deploy_to_social(manifest_path: str):
    """
    Deploys media to social channels using the Postiz API via a GCS Signed URL pull-handoff.
    """
    POSTIZ_API_KEY = os.getenv("POSTIZ_API_KEY")
    GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "antigravity-media-staging")
    
    if not POSTIZ_API_KEY:
        print("[!] FATAL: POSTIZ_API_KEY is missing from .env", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Reading deployment manifest: {manifest_path}")
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
        
    deployments = manifest.get("deployments", [])
    if not deployments and "platforms" in manifest:
        # Adapt from social_manifest.json schema
        platforms = manifest["platforms"]
        base_dir = os.path.dirname(manifest_path)
        if "facebook_page" in platforms:
            fb = platforms["facebook_page"]
            if "feed_path" in fb:
                deployments.append({
                    "local_path": os.path.join(base_dir, fb["feed_path"]),
                    "platform": "facebook",
                    "caption": fb.get("post_copy", "New Content!")
                })
        if "youtube" in platforms:
            yt = platforms["youtube"]
            if "video_target_id" in yt:
                # Assuming video_target_id is a local path for now, or thumbnail
                path = yt.get("thumbnail_path", yt["video_target_id"])
                deployments.append({
                    "local_path": os.path.join(base_dir, path) if not os.path.isabs(path) else path,
                    "platform": "youtube",
                    "caption": "New YouTube Upload"
                })

    # 1. GCS Upload & Signed URL Generation
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
    except Exception as e:
        print(f"[!] FATAL: Google Cloud Storage Auth Failed. Check Application Default Credentials. Error: {e}", file=sys.stderr)
        sys.exit(1)

    for item in deployments:
        local_file_path = item.get("local_path")
        platform = item.get("platform")
        
        if not os.path.exists(local_file_path):
            print(f"[!] Warning: File not found: {local_file_path}. Skipping.")
            continue
            
        filename = os.path.basename(local_file_path)
        gcs_blob_name = f"social_deployments/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        blob = bucket.blob(gcs_blob_name)
        
        print(f"[*] Uploading {filename} to GCS bucket '{GCS_BUCKET_NAME}'...")
        blob.upload_from_filename(local_file_path)
        
        # Generate a 1-hour secure download link
        print(f"[*] Generating Signed URL...")
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=1),
            method="GET"
        )
        
        # 2. Aggregator Pull Handoff (Postiz)
        print(f"[*] Instructing Postiz to pull media from GCS...")
        headers = {"Authorization": f"Bearer {POSTIZ_API_KEY}"}
        
        upload_res = requests.post(
            "https://api.postiz.com/public/v1/upload-from-url",
            headers=headers,
            json={"url": signed_url}
        )
        
        if not upload_res.ok:
            print(f"[!] FATAL: Postiz Upload Failed: {upload_res.text}", file=sys.stderr)
            sys.exit(1)
            
        media_id = upload_res.json()["id"]
        media_path = upload_res.json()["path"]
        print(f"[*] Postiz Media ID acquired: {media_id}")
        
        # 3. Publish to specific channel
        integration_id_env_var = f"POSTIZ_{platform.upper()}_INTEGRATION_ID"
        integration_id = os.getenv(integration_id_env_var)
        
        if not integration_id:
            print(f"[!] Warning: Integration ID for {platform} not found in .env ({integration_id_env_var}). Skipping publish.", file=sys.stderr)
            continue
            
        payload = {
            "type": "schedule" if item.get("scheduled_time") else "publish",
            "posts": [
                {
                    "integration": { "id": integration_id },
                    "value": [{"content": item.get("caption", "New Content!"), "image": [{"id": media_id, "path": media_path}]}],
                    "settings": {
                        "__type": platform.lower()
                    }
                }
            ]
        }
        
        print(f"[*] Dispatching publish request to Postiz for {platform}...")
        publish_res = requests.post("https://api.postiz.com/public/v1/posts", headers=headers, json=payload)
        
        if publish_res.ok:
            print(f"[+] Successfully deployed {filename} to {platform}!")
        else:
            print(f"[!] Failed to deploy to {platform}: {publish_res.text}", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python deploy_social.py <manifest.json>")
        sys.exit(1)
    
    deploy_to_social(sys.argv[1])
