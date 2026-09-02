# Original User Request

## Initial Request — 2026-08-27T10:00:22Z

<USER_REQUEST>
A local desktop machine learning Video Editing Brain and Renderer (Python/FastAPI) that intercepts raw video from an existing ingest bridge. It features a Gemini Omni ML feedback loop for autonomous edit decisions, executing them via desktop-class FFmpeg to guarantee visually lossless quality, before pushing to a delivery folder.

Working directory: `~/teamwork_projects/baptism_of_music_brain`
Integrity mode: `development`

## Verification Resources
The user has an existing ingestion bridge and will provide a local `ingest` folder containing a high-fidelity reference video (4K) to act as the ground-truth benchmark for rendering tests.

## Requirements

### R1. The ML Brain (FastAPI + Gemini Omni)
A Python service that monitors a local `ingest` directory. When a raw video arrives, it must trigger a Gemini Omni ML grading loop to generate an Edit Decision List (EDL) (e.g., trims, cuts, color adjustments) based on trends. It must also expose an endpoint/interface for full manual user overrides before rendering.

### R2. The High-Fidelity Renderer (Desktop FFmpeg)
The system must parse the AI's decisions and execute the physical video edits using local desktop-class `ffmpeg`. To balance the "0% loss" requirement against storage limits, the pipeline must use visually lossless encoding profiles (e.g., high-bitrate `libx264 -crf 17` or `hevc_nvenc`) to maximize quality without the catastrophic file bloat of uncompressed rendering.

### R3. The Delivery Pipeline
Once the FFmpeg render completes, the finalized video must be exported to a designated `delivery` directory, formatted and ready for the user's existing bridge to sync back to their Samsung Gallery for publishing.

## Acceptance Criteria

### 1. Programmatic Encoding Verification
- [ ] An automated test script must execute `ffprobe` on the final output video to programmatically assert that the output codec, high bitrate, and resolution constraints mathematically match the "visually lossless" configuration targets.

### 2. End-to-End File Pipeline Execution
- [ ] An integration test must physically drop a sample video into the `ingest` folder and assert that the FastAPI brain successfully detects it, generates a mock ML edit decision, renders the output via FFmpeg, and deposits the final video into the `delivery` directory.
</USER_REQUEST>
<ADDITIONAL_METADATA>
The current local time is: 2026-08-27T03:00:22-07:00.
</ADDITIONAL_METADATA>
