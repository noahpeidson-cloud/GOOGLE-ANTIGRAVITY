# Media Pipeline Rules

## R-MEDIA-1: The Zero-Copy Mandate
- **Context:** When manipulating, staging, or moving raw video files (especially massive APV or ProRes formats).
- **Mandate:** Agents are STRICTLY FORBIDDEN from using `shutil.copy2`, `cp`, or any other standard file-copying operations on source media.
- **Actionable Execution:** You MUST use Windows Hardlinks (`os.link` in Python) to safely "copy" files across directories on the same physical volume to prevent I/O thrashing and massive storage duplication.

## R-MEDIA-2: The Fast-Proxy Generation
- **Context:** When a new asset is ingested into `01_RAW` via the media pipeline.
- **Mandate:** The agent MUST ensure a lightweight 720p H.264 proxy is generated for the web dashboard.
- **Actionable Execution:** Ensure the `proxy_generator.py` hook fires, or manually trigger it if running a custom ingest script, so the Web UI can stream the asset without locking up the browser.

## R-MEDIA-3: The Bleeding-Edge Model Mandate
- **Context:** When configuring LLMs, orchestrators, or backend logic for the media pipeline (e.g., in `dashboard_backend.py`).
- **Mandate:** Agents MUST prioritize the absolute newest, highest-tier reasoning model available in reality (e.g., `gemini-3.1-pro`), rather than falling back to older LTS defaults like `2.5-pro` or `flash`.
- **Actionable Execution:** The media editing orchestrator requires zero-shot perfection to parse complex human constraints into DaVinci API JSON. You must verify the latest model release using `search_web` (per R23) and explicitly hardcode the absolute latest Pro tier into the backend SDK configuration.
