## 2026-08-22T11:00:33Z
Upgrade the EDM Content Strategy architecture to implement a "Human-in-the-Loop" editing workflow, metadata tagging in the Web UI, and an FFmpeg proxy generation system to prevent processing bottlenecks.

Integrity mode: benchmark

Requirements:
R1. Web UI Metadata Forms:
Modify `static/index.html` (served by `remote_trigger.py`) to include text input fields for "Festival Name" and "Artist Name" above the main Trigger button. Update the frontend `fetch()` logic to pass these fields in the JSON payload to `POST /trigger-pipeline`.

R2. Proxy Generation & Storage Structure:
Update `orchestrator.py` to organize ingested files logically based on the new metadata. Upon ingestion, the orchestrator MUST use `ffmpeg` to generate a lightweight 720p proxy video (`.mp4`) and extract a `.wav` file for every 4K video. The original 4K HDR files must be stored safely and untouched in a `01_RAW/[Festival]/[Artist]` directory structure.

R3. Human-in-the-Loop "Awaiting Review" Gate:
Modify the Librosa drop-detection logic in `orchestrator.py`. It must now run its analysis exclusively on the lightweight `.wav` file. Instead of exporting a final 4K video, the script must trim the *proxy* video based on the drop-detection timestamps and save it to a new `02_AWAITING_REVIEW` directory. The AI must NOT touch or edit the 4K files.

Acceptance Criteria:
- The `index.html` form correctly captures and transmits metadata to the FastAPI backend.
- The orchestrator successfully executes `ffmpeg` to generate proxies and `.wav` files upon receiving the payload.
- The orchestrator successfully trims the proxy video and deposits it into `02_AWAITING_REVIEW`, leaving the 4K file untouched in `01_RAW`.
