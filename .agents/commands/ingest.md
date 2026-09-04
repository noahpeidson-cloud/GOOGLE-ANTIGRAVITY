# /ingest — Ingest Media

Trigger the media ingestion pipeline for new content in the `content_creation/` directory.

## Instructions
1. Invoke the `media-engineer` subagent
2. Run ADB pull or file discovery as appropriate
3. Trigger the FFmpeg proxy generator via the `media-pipeline-ingestor` hook
