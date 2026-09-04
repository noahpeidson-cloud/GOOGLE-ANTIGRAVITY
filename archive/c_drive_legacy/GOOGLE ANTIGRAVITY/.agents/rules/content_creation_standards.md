# [HOBBY] Content Creation & Media Engineering Pipeline

## Operational Mandate
Process live music, festival, and concert mobile footage (often low-light HDR captures) into optimized, high-fidelity 9:16 vertical reels for social distribution.

## Technical Transcoding Standards (FFmpeg)
- **Container**: MP4
- **Video Codec**: H.265 / HEVC or AV1 (require hardware acceleration).
- **Resolution**: 1080x1920 (9:16 portrait) with intelligent subject-tracking offsets.
- **Video Bitrate**: 15–20 Mbps VBR (25 Mbps max).
- **Audio Codec**: AAC-LC at 320 kbps, 48 kHz stereo.

## Non-Destructive Filtering
- **Video Denoising**: Apply spatio-temporal low-light filtering (`hqdn3d` or `nlmeans`).
- **Dynamic Range**: Preserve highlights in intense LED environments; do not crush sub-blacks.
- **Audio Normalization**: Apply two-pass dynamic normalization (`loudnorm=I=-14:LRA=7:TP=-1.5`) and high-pass filtering to eliminate clipping in bass-heavy environments.

## Verification Protocol
Before marking a media script complete, the agent MUST:
1. Process a sample raw video clip.
2. Verify visual integrity using the Antigravity Chromium player.
3. Validate audio LUFS compliance via FFmpeg analysis (`ffmpeg -i out.mp4 -af ebur128=peak=true -f null -`).
