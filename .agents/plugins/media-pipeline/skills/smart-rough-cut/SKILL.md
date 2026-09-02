---
name: smart-rough-cut
description: >-
  Use this skill when the user wants to initiate the "Smart Rough Cut" workflow for their ingested media, 
  combining the Web Dashboard review with automated DaVinci Resolve timeline creation.
---

# Smart Rough Cut Workflow

This skill dictates the procedure for executing the media pipeline review phase.

## Prerequisites
- The media must have already been ingested via USB (e.g. `samsung_ingest.py`).
- The proxies must have been generated (via `proxy_generator.py`).

## Steps

### 1. Launch the Review Dashboard
Start the local FastAPI review dashboard.
```bash
uvicorn dashboard_backend:app --host 127.0.0.1 --port 8000
```
Provide the user with the localhost URL so they can review their proxies and tag the clips with `APPROVED_FOR_RENDER` (or in/out points).

### 2. Wait for User Completion
Do not proceed until the user explicitly confirms they have finished reviewing and tagging their clips in the web UI.

### 3. Generate the DaVinci Resolve Project
Once the user confirms they are done, execute the integration script to pull the approved clips into DaVinci Resolve.
```bash
python davinci_integration.py --name "Auto Project"
```

### 4. Verification
Inform the user that DaVinci Resolve has been configured. The user should open Resolve to see their Bins and "Rough Cut Auto" timeline assembled.
