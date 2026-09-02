from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
import datetime
from workers.media_worker import process_media_workflow

app = FastAPI(title="Antigravity Control Plane - Celery Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class JobPayload(BaseModel):
    task_type: str
    target_file: str
    parameters: dict

@app.post("/api/jobs/media")
async def submit_media_job(job: JobPayload):
    job_id = str(uuid.uuid4())
    
    if job.task_type == "TASK_MEDIA_WORKFLOW":
        # Offload heavy lifting to Celery/Redis
        process_media_workflow.delay(job_id, job.target_file, job.parameters)
    elif job.task_type == "TASK_VIDEO_TRIM":
        # Default behavior just routing to media workflow for now
        process_media_workflow.delay(job_id, job.target_file, job.parameters)
    else:
        # Other job types can be handled here or by other celery tasks
        pass
        
    return {"status": "success", "job_id": job_id, "message": "Job successfully dispatched to Celery worker."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
