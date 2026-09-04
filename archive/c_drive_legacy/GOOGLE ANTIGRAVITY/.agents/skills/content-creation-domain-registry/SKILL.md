---
name: content-creation-domain-registry
description: Unified SOP registry for Media Ingestion, ML Grading, and EDM Video processing pipelines. Replaces standalone fragmented SOPs.
---

# Content Creation Domain Registry

This unified registry contains the Standard Operating Procedures (SOPs) for the entire media and video creation pipeline.

## Table of Contents
1. [Media Ingestion Pipeline (Quick Share Push)](#media-ingestion-pipeline)
2. [Media ML Grading Engine (R27 Guardrails)](#media-ml-grading-engine)
3. [EDM Master Mind Pipeline](#edm-master-mind-pipeline)
4. [Headless Automation (Edge Playbook)](#headless-automation)

---

## 1. Media Ingestion Pipeline (Quick Share Push) <a name="media-ingestion-pipeline"></a>

### Overview
This pipeline securely transfers raw, uncompressed 4K video files from an Android device to a local Windows machine via Samsung Quick Share, bypassing cloud compression and the instability of ADB Wi-Fi polling.
**Location:** `g:\My Drive\GOOGLE ANTIGRAVITY\quick_share_ai_loop`

### Step-by-Step Boot Sequence

#### 1. Directory Setup & Intercept
The python `watchdog` daemon monitors the exact directory Samsung Quick Share utilizes on Windows.
- **Target Dir:** `C:\Users\noahp\Downloads\Quick Share`

#### 2. The File Lock Invariant (Race Condition Prevention)
Quick Share writes massive 4K files in chunks, triggering multiple `on_created` and `on_modified` events.
**Mandate:** Agents MUST NOT rely on file size stability (`st_size`) to determine if a transfer is complete. You MUST execute an explicit OS file lock check (e.g., attempting an exclusive `r+` open or `os.rename(file, file)`). If it throws a `PermissionError`, the transfer is still active.

#### 3. Verification
- Watch the `quick_share_hijack.py` console for `Quick Share Intercept: New video detected`.
- A 720p proxy is generated locally via FFmpeg to save bandwidth before uploading to Gemini API for tagging.

---

## 2. Media ML Grading Engine (R27 Guardrails) <a name="media-ml-grading-engine"></a>

### Overview
This pipeline executes multimodal inference on video proxies using `gemini-3.1-pro-preview` (per the Grounded Model Mandate). 

### Bulk Upload Queueing Guardrail (R27 Extension)
When dumping 30+ 4K videos at once via Quick Share, executing concurrent GenAI API calls will trigger massive `429 RESOURCE_EXHAUSTED` quotas.
**Mandate:** Agents MUST explicitly catch `429 RESOURCE_EXHAUSTED` (alongside `503 UNAVAILABLE`) in an exponential backoff loop.
**Mandate:** For bulk workflows, agents MUST implement a local queue (e.g., SQLite, Celery, or ThreadPoolExecutor with `max_workers=2`) to throttle concurrent Gemini API calls. Do not allow 40 unbound threads to slam the API simultaneously.

### BigQuery ML Feedback Loop
Once tagged, metadata is sunk to Firebase Data Connect (PostgreSQL) for the React frontend, and BigQuery ML for Simplex Normalization to refine the viral weighting algorithms dynamically over time.

---

## 3. EDM Master Mind Pipeline <a name="edm-master-mind-pipeline"></a>

### Overview
This skill orchestrates the entire workflow from the Samsung S26 Ultra to DaVinci Resolve. It acts as the user's Assistant Editor.

### Workflow Steps
#### 1. Ingestion (Zero-Touch)
- Handled by Quick Share Push pipeline.
#### 2. Proxy Generation (FFmpeg)
- For every 4K HDR H.265 file, immediately generate a lightweight 720p proxy and a `.wav` file. Move 4K raw files to `01_RAW/`.
#### 3. PWA Web Dashboard
- Serve `static/index.html` via FastAPI or React/Vite.
- The UI displays the 720p proxy and allows the user to manually adjust the AI-detected trim points.
#### 4. DaVinci Resolve Handoff
- Upon Web UI approval, use the DaVinci Resolve Python API to create a new project.
- Import the 4K raw files, slice them precisely based on the Web UI timestamps, and place them on the timeline.

---

## 4. Headless Automation (Edge Playbook) <a name="headless-automation"></a>

### Overview
When writing browser automation scripts or deploying the `browser` subagent on Windows, natively launching `chrome.exe` with `--remote-debugging-port` often crashes instantly due to existing instances locking the profile.

### The `cmd.exe` Edge Mandate
**Mandate:** To securely spin up a detached background browser for DevTools or Lighthouse audits, agents MUST use Microsoft Edge wrapped in a `cmd.exe` call with a temporary user data directory:
```powershell
cmd.exe /c "msedge.exe --headless=new --remote-debugging-port=9222 --user-data-dir=C:\Users\noahp\AppData\Local\Temp\EdgeTest"
```
This avoids PowerShell execution policy hangs and guarantees an isolated WebSocket binding for `mcp_chrome_devtools`.
