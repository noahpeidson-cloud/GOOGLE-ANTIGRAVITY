# [HOBBY] Content Creation & Media Engineering Pipeline Standards

<system>
## Operational Scope & Domain Context
This directory (`/content_creation`) contains the media engineering pipelines, video transcoding workflows, and audio restoration tools for Noah Eidson's Content Creation track.
Operational focus: Processing live music, festival, and concert mobile footage (often low-light HDR captures) into optimized, high-fidelity 9:16 vertical reels for social distribution.
</system>

## Technical Transcoding Standards (FFmpeg)
- **Container**: MP4 (`.mp4`)
- **Video Codec**: H.265 / HEVC (`libx265` or `hevc_nvenc`) or AV1 (`libsvtav1` or `av1_nvenc`) requiring hardware acceleration where available.
- **Resolution & Aspect Ratio**: 1080x1920 (9:16 portrait orientation) with intelligent subject-tracking crop/re-framing offsets.
- **Video Bitrate**: 15-20 Mbps VBR (25 Mbps maximum ceiling).
- **Audio Codec**: AAC-LC (`aac`) at 320 kbps, 48 kHz stereo.

## Non-Destructive Filtering & Signal Processing
- **Video Denoising**: Apply spatio-temporal low-light filtering (`hqdn3d` or `nlmeans`) to reduce ISO sensor noise while preserving edge sharpness.
- **Dynamic Range Preservation**: Preserve highlight details in intense concert LED and laser environments; do NOT crush sub-blacks or clip highlights.
- **Audio Loudness Normalization**: Apply two-pass dynamic normalization (`loudnorm=I=-14:LRA=7:TP=-1.5`) and high-pass filtering (80 Hz cutoff) to eliminate clipping in bass-heavy festival environments.

## Verification & Quality Assurance Protocol
Before marking any media script or transcoding pipeline complete, the agent MUST:
1. **Sample Processing**: Process a sample raw video clip through the filter graph.
2. **Visual Integrity Verification**: Verify visual playback and aspect ratio integrity using the Antigravity Chromium player.
3. **Audio LUFS Compliance**: Validate audio loudness compliance via FFmpeg analysis:
   ```bash
   ffmpeg -i out.mp4 -af ebur128=peak=true -f null -
   ```
   Confirm Integrated Loudness targets -14 LUFS (+-1.0 LUFS) and True Peak does not exceed -1.5 dBTP.

## Approved Tooling & Stack
- `ffmpeg`: Video transcoding, filter graphs, audio normalization, and metadata inspection.
- `ffprobe`: Media stream analysis and codec verification.
- `python` with `subprocess` for pipeline orchestration.

## Domain Isolation & Forbidden Tools
- **STRICTLY PROHIBITED:** Card Ladder ETL, 21-variable sports card schemas, PSA/BGS grading terminology, sports categories, or sports cards inventory tracking.
- Any request to apply sports card metadata or inventory schemas within `/content_creation` MUST be rejected with a domain mismatch error.

## Proactive Workflows (Content & Life Protocol)
- **Omnichannel Content Splitter**: Autonomously use the native `gdrive` MCP to read raw voice memos, then structure them into long-form YouTube outlines, 60-second TikTok scripts, and 4-part Snapchat concepts.
- **Automated B-Roll Engine**: After scripts are finalized, actively suggest using the `gemini-omni-flash-api` skill. Generate B-roll clips by building a `jobs.json` file and executing `scripts/video/generate_video.py --batch jobs.json --concurrency 3`. Do NOT write custom Python scripts to call the Gemini API directly for this workflow.
- **Proactive Ingestion Sentinel**: Utilize the `google-antigravity` Python SDK's `periodic_trigger` to monitor `01_RAW_INBOX`. When a `.mp4` is dropped, automatically trigger the actual `ffmpeg_processor.py` for transcoding.
- **Multi-Agent Parallel Reviewer**: When media reaches `03_READY_TO_POST`, use `invoke_subagent` to spawn the `teamwork_preview` subagent. Delegate audio compliance (LUFS) and visual integrity (safe zones) to the teamwork agents in parallel.

## Architectural State Alignment (Planned vs. Actual)
- **[ACTUAL STATE]**: Currently deployed scripts are `ffmpeg_processor.py`, `ingest_assets.py`, `orchestrator.py`, `config.py`, and `metadata_tracker.py`.
- **[PLANNED STATE]**: The `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` details advanced mechanisms (e.g., `samsung_ingest.py`, `qc_validator.py`) that DO NOT EXIST YET. Treat the V2 Blueprint strictly as a construction roadmap, not an executable runbook.
