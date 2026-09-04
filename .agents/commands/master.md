# /master — Master Audio

Run EBU R128 two-pass loudness normalization on all proxy audio files.

## Instructions
1. Invoke the `ffmpeg-audio-mastering` skill
2. Target all WAV/MP4 files in `content_creation/proxies/`
3. Normalize to -14 LUFS with 80Hz high-pass filter
