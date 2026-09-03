---
name: ffmpeg-audio-mastering
description: Specialized media DSP skill for FFmpeg transcoding, EBU R128 two-pass audio loudness normalization (-14 LUFS), 80Hz high-pass filtering, NVENC hardware encoding, and web proxy generation.
license: Complete terms in LICENSE.txt
---

# FFmpeg & Audio Mastering Engine

## Overview
This skill provides the exact commands, filter graphs, and audio normalization mathematics required to master concert and festival audio and render broadcast-standard 1080x1920 9:16 vertical video.

## Target Output Standards
- **Loudness Standards**: EBU R128 / ITU-R BS.1770-4
  - **Integrated Loudness ($I$)**: `-14.0 LUFS` ($\pm 1.0\text{ LUFS}$)
  - **Loudness Range ($LRA$)**: `7.0 LU`
  - **True Peak ($TP$)**: `\le -1.5\text{ dBTP}`
- **Audio Encoding**: AAC-LC (`aac`) at `320 kbps`, `48,000 Hz` Stereo.
- **Low-End Filtering**: High-pass filter at `80 Hz` (`highpass=f=80`) to eliminate sub-bass festival stage clipping.
- **Video Master Target**: `1080x1920` (9:16 portrait), H.265 / HEVC (`hevc_nvenc`) with 18 Mbps VBR, 60fps.

---

## The Two-Pass Audio Normalization Workflow

### Pass 1: Loudness Analysis (No Output File)
Execute analysis to measure the source clip's audio characteristics:
```bash
ffmpeg -i input.mp4 -af "highpass=f=80,loudnorm=I=-14:LRA=7:TP=-1.5:print_format=json" -f null -
```
Extract the JSON block from stderr:
```json
{
  "input_i": "-22.34",
  "input_tp": "-0.21",
  "input_lra": "11.20",
  "input_thresh": "-33.10",
  "target_offset": "0.15"
}
```

### Pass 2: Hardware-Accelerated Render
Feed measured values into Pass 2 to achieve linear normalization without dynamic pump/breathing artifacts:
```bash
ffmpeg -y -i input.mp4 \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" \
  -c:v hevc_nvenc -preset p6 -tune hq -rc vbr -b:v 18M -maxrate 25M -bufsize 30M \
  -af "highpass=f=80,loudnorm=I=-14:LRA=7:TP=-1.5:measured_I=-22.34:measured_LRA=11.20:measured_TP=-0.21:measured_thresh=-33.10:offset=0.15:linear=true" \
  -c:a aac -b:a 320k -ar 48000 output_master.mp4
```

---

## Fast Web Proxy Generation (8K APV Optimized)
Because 8K APV is a visually lossless intra-frame codec without native NVDEC hardware silicon support (on RTX 3080 Ti), the CPU *must* decode the massive frames. To prevent CPU starvation, we must immediately offload encoding to the GPU (`h264_nvenc`).

```bash
ffmpeg -y -i input.apv \
  -vf "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280" \
  -c:v h264_nvenc -preset p4 -tune hq -cq 28 \
  -c:a aac -b:a 128k -ar 48000 \
  02_PROXIES/proxy_preview.mp4
```

---

## Procedural Test Media Generation (R21 Compliance)
When developing or testing pipelines without physical video on disk, procedurally generate a valid 9:16 test clip:
```bash
ffmpeg -y -f lavfi -i testsrc=duration=5:size=1080x1920:rate=60 \
  -f lavfi -i sine=frequency=440:duration=5 \
  -c:v libx264 -c:a aac -b:a 192k \
  public/procedural_test.mp4
```

---

## Audio Verification Command
Verify rendered compliance deterministically:
```bash
ffmpeg -i output_master.mp4 -af ebur128=peak=true -f null - 2>&1 | findstr /i "Integrated True"
```

## Natural Language Invocations
- *"Normalize audio to -14 LUFS for this video"*
- *"Transcode to 9:16 vertical with NVENC hardware acceleration"*
- *"Fix bass distortion and highpass at 80Hz"*
- *"Generate a lightweight web proxy for this 4K clip"*
