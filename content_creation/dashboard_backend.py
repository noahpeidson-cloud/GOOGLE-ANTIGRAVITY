import os
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
import asyncio
import uvicorn

# We must import from local modules
from metadata_tracker import MediaManifestDB
from config import AssetStatus

app = FastAPI(title="AntiGravity Media Review Dashboard")

# Semaphore to limit concurrent NVENC renders to 2
render_semaphore = asyncio.Semaphore(2)

# Enable CORS for the Generative UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_ROOT = Path(__file__).parent.resolve()
DB_PATH = WORKSPACE_ROOT / "media_manifest.sqlite"

app.mount("/static", StaticFiles(directory=WORKSPACE_ROOT / "static"), name="static")


class ApproveRequest(BaseModel):
    start_time: Optional[float] = None
    duration: Optional[float] = None
    clip_type: Optional[str] = "A-Roll"

@app.get("/")
def serve_frontend():
    """Serves the main review dashboard HTML page."""
    html_path = WORKSPACE_ROOT / "dashboard_v2.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Dashboard UI not found.</h1> Please create dashboard_v2.html.", status_code=404)
    return FileResponse(html_path)

@app.get("/api/assets/review")
def list_review_assets():
    """Returns all assets currently in AWAITING_REVIEW state."""
    db = MediaManifestDB(db_path=DB_PATH)
    assets = db.list_assets(status=AssetStatus.AWAITING_REVIEW)
    
    # Also parse metadata_json for convenience
    for a in assets:
        if a.get("metadata_json"):
            try:
                a["metadata"] = json.loads(a["metadata_json"])
            except json.JSONDecodeError:
                a["metadata"] = {}
        else:
            a["metadata"] = {}
            
    return {"assets": assets}

@app.get("/api/media/{project_id}")
def get_media(project_id: str, request: Request):
    """Streams the proxy MP4 file for previewing."""
    db = MediaManifestDB(db_path=DB_PATH)
    asset = db.get_asset(project_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    proxy_path = asset.get("proxy_path")
    if not proxy_path or not Path(proxy_path).exists():
        raise HTTPException(status_code=404, detail="Proxy file not found on disk")
        
    file_size = os.path.getsize(proxy_path)
    range_header = request.headers.get("range")
    
    if range_header:
        byte1, byte2 = 0, None
        try:
            parts = range_header.replace("bytes=", "").split("-")
            byte1 = int(parts[0]) if parts[0] else 0
            byte2 = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        except Exception:
            byte2 = file_size - 1
            
        length = byte2 - byte1 + 1
        
        def file_iterator():
            with open(proxy_path, "rb") as f:
                f.seek(byte1)
                yield f.read(length)
                
        headers = {
            "Content-Range": f"bytes {byte1}-{byte2}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        }
        return StreamingResponse(file_iterator(), status_code=206, headers=headers, media_type="video/mp4")
    
    return FileResponse(proxy_path, media_type="video/mp4")

async def process_render(project_id: str):
    """Background worker that respects the NVENC hardware limit (max 2)."""
    async with render_semaphore:
        print(f"[RENDER QUEUE] Starting master render for project: {project_id}")
        cmd = f"python orchestrator.py render --project-id {project_id} --publish-youtube --auto-promote"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(WORKSPACE_ROOT),
            creationflags=0x08000000
        )
        stdout, stderr = await proc.communicate()
        print(f"[RENDER QUEUE] Finished {project_id} (Code: {proc.returncode})")
        if proc.returncode != 0:
            print(f"[RENDER QUEUE] Error: {stderr.decode()}")

@app.post("/api/assets/approve/{project_id}")
def approve_asset(project_id: str, payload: ApproveRequest, background_tasks: BackgroundTasks):
    """Approves an asset for rendering, updates trim times, and queues the render."""
    db = MediaManifestDB(db_path=DB_PATH)
    asset = db.get_asset(project_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    meta = {}
    if asset.get("metadata_json"):
        try:
            meta = json.loads(asset["metadata_json"])
        except json.JSONDecodeError:
            pass
            
    if payload.start_time is not None:
        meta["start_time"] = payload.start_time
    if payload.duration is not None:
        meta["duration"] = payload.duration
    
    meta["clip_type"] = payload.clip_type
        
        
    with db._db_connection() as conn:
        conn.execute(
            "UPDATE asset_manifest SET current_status = ?, metadata_json = ? WHERE asset_id = ?",
            (AssetStatus.APPROVED_FOR_RENDER.value, json.dumps(meta), project_id)
        )
        conn.commit()
        
    # Enqueue the background render task
    background_tasks.add_task(process_render, project_id)
        
    return {"status": "success", "project_id": project_id, "new_state": AssetStatus.APPROVED_FOR_RENDER.value}

@app.post("/api/assets/reject/{project_id}")
def reject_asset(project_id: str):
    """Rejects an asset by archiving it."""
    db = MediaManifestDB(db_path=DB_PATH)
    asset = db.get_asset(project_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    db.update_status(project_id, AssetStatus.ARCHIVED)
    return {"status": "success", "project_id": project_id, "new_state": AssetStatus.ARCHIVED.value}

class ChatRequest(BaseModel):
    message: str
    project_id: Optional[str] = None

@app.post("/api/chat")
def chat_with_agent(payload: ChatRequest):
    """Processes natural language editing commands via Gemini and executes them."""
    try:
        from google import genai
        import os
        from dotenv import load_dotenv
        
        load_dotenv(WORKSPACE_ROOT / ".env")
        
        if not os.environ.get("GEMINI_API_KEY"):
            return {"status": "error", "response": "GEMINI_API_KEY not found in .env"}
            
        client = genai.Client()
        
        # Pydantic schema for structured output
        from pydantic import Field
        class AgentAction(BaseModel):
            action_type: str = Field(description="One of: 'trim', 'rebuild', 'export', 'unknown'")
            asset_id: Optional[str] = Field(description="The asset ID if applicable")
            start_time: Optional[float] = Field(description="Start time for trim")
            duration: Optional[float] = Field(description="Duration for trim")
            clip_type: Optional[str] = Field(description="A-Roll or B-Roll")
            social_format: Optional[str] = Field(description="If export, 'vertical' for shorts/reels, 'horizontal' otherwise.")
            response_message: str = Field(description="Message to return to the user")

        prompt = (
            f"User request: {payload.message}\n"
            f"Active asset ID (if any): {payload.project_id}\n"
            f"Determine the action required (trim, rebuild, export, or unknown). "
            f"If 'trim', try to extract start_time (seconds) and duration (seconds). "
            f"If 'export', check if they mentioned YouTube Short, Instagram Reel, TikTok, Snapchat Spotlight, or Vertical, and set social_format to 'vertical'. "
            f"Return a conversational 'response_message' acknowledging the action."
        )
                 
        response = client.models.generate_content(
            model='gemini-3.1-pro-preview',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': AgentAction,
            },
        )
        
        action_data = json.loads(response.text)
        action_type = action_data.get("action_type")
        
        from edit_controller import EditController
        controller = EditController()
        
        if action_type == "trim":
            asset_id = action_data.get("asset_id") or payload.project_id
            if asset_id and action_data.get("start_time") is not None and action_data.get("duration") is not None:
                controller.trim_clip(
                    asset_id, 
                    action_data["start_time"], 
                    action_data["duration"], 
                    action_data.get("clip_type", "A-Roll")
                )
        elif action_type == "rebuild":
            controller.rebuild_resolve_timeline()
        elif action_type == "export":
            fmt = action_data.get("social_format", "horizontal")
            controller.export_video("final_export.mp4", social_format=fmt)
            
        return {"status": "success", "response": action_data.get("response_message", "Action processed.")}
        
    except Exception as e:
        return {"status": "error", "response": str(e)}

async def preflight_sensor_tool(filepath: str) -> str:
    """Analyzes a media file to extract physical metrics like beats per minute and average brightness."""
    from preflight_sensor import PreFlightSensor
    result = PreFlightSensor.analyze_media(filepath)
    return json.dumps(result)

@app.post("/api/council_think")
async def council_think(payload: ChatRequest):
    import os
    from dotenv import load_dotenv
    import asyncio
    
    load_dotenv(WORKSPACE_ROOT / ".env")
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in .env")
        
    db = MediaManifestDB(db_path=DB_PATH)
    asset = db.get_asset(payload.project_id) if payload.project_id else None
    proxy_path = asset.get("proxy_path") if asset else "None"
    
    from polyglot_orchestrator import run_polyglot_pipeline
    
    try:
        # Generate the draft state JSON file using the new polyglot architecture
        await run_polyglot_pipeline(payload.message)
        
        # Read the generated draft state to send back to the UI
        import json
        with open("draft_state.json", "r", encoding="utf-8") as f:
            draft_state = json.load(f)
            
        return {"status": "success", "response": draft_state.get("ai_summary", "Processing complete.")}
    except Exception as e:
        import json
        with open("draft_state.json", "w", encoding="utf-8") as f:
            json.dump({
                "concept": payload.message,
                "status": "AWAITING_HUMAN_COMMIT",
                "ai_summary": f"🚨 Polyglot Pipeline Error: {str(e)}\n\nThe Antigravity SDK returned a 503 High Demand error. Please try again."
            }, f, indent=4)
        return {"status": "error", "response": f"Polyglot Pipeline failed: {str(e)}"}

@app.get("/api/draft_state")
async def get_draft_state():
    import json
    draft_path = Path("draft_state.json")
    if not draft_path.exists():
        return {"status": "none"}
    with open(draft_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/commit_render")
async def commit_render():
    import json
    from edit_controller import EditController
    
    draft_path = Path("draft_state.json")
    if not draft_path.exists():
        raise HTTPException(status_code=400, detail="No draft state found.")
        
    with open(draft_path, "r", encoding="utf-8") as f:
        draft_state = json.load(f)
        
    # Update status
    draft_state["status"] = "COMMITTED"
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(draft_state, f, indent=4)
        
    # Trigger Render
    controller = EditController()
    controller.export_video("final_export.mp4", social_format="vertical")
    
    return {"status": "success", "message": "Render committed and triggered successfully."}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9067)
