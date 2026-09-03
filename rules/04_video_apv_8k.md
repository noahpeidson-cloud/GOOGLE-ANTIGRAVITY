---
title: "8K APV Video Processing Standards"
category: "media"
enforcement: "strict"
---

# 8K APV Video Processing Standards & Guardrails

## R-APV-01. Zero-Copy Media Staging Mandate
- **Context:** Moving or staging massive Samsung Galaxy S26 Ultra 8K APV (422-10 HQ) raw media across pipeline folders.
- **Mandate:** Agents are STRICTLY FORBIDDEN from using standard file copy or byte duplication on primary storage.
- **Actionable Execution:** You MUST use Windows NTFS Hardlinks (`os.link` in Python) to stage media instantaneously without I/O degradation or duplicate storage consumption.

## R-APV-02. Dual-Tier Proxy Pipeline
- **Context:** Processing 8K 60fps / 10-bit APV captures for previewing and editing.
- **Mandate:** Agents must generate optimized proxies immediately upon ingestion:
  - **Tier 1 (Web Dashboard Preview):** 720p H.264 (`libx264`, crf 23, AAC-LC 128kbps) for zero-latency browser streaming.
  - **Tier 2 (DaVinci Resolve NLE):** 1080p ProRes 422 Proxy / DNxHR LB for seamless 60fps real-time scrubbing.
- **Actionable Execution:** Trigger `content_creation/proxy_generator.py` or execute NVENC-accelerated FFmpeg commands.

## R-APV-03. Hardware-Accelerated NVENC Encoding
- **Context:** Transcoding, proxy generation, or final delivery renders.
- **Mandate:** Agents MUST prioritize NVIDIA NVENC hardware encoders (`hevc_nvenc`, `h264_nvenc`) with CUDA acceleration.
- **Actionable Execution:** Use `-c:v hevc_nvenc -preset p5 -tune hq -rc vbr -cq 19 -pix_fmt p010le` for 10-bit HDR exports.

## R-APV-04. EBU R128 Audio Loudness Normalization & DSP Chain
- **Context:** Mastering concert, festival, and live event audio tracks for short-form social delivery.
- **Mandate:** All final audio streams MUST strictly comply with social platform broadcast standards:
  - **Integrated Loudness Target ($I$):** $-14.0\text{ LUFS} \ (\pm 1.0\text{ LUFS})$
  - **Loudness Range ($\text{LRA}$):** $\le 7.0\text{ LU}$
  - **True Peak Target ($\text{TP}$):** $\le -1.5\text{ dBTP}$
  - **High-Pass Filter:** $80\text{ Hz}$ cutoff (`highpass=f=80`) to eliminate sub-bass stage rumble.
  - **Format:** AAC-LC, 320 kbps, 48 kHz stereo.
- **Actionable Execution:** Execute two-pass FFmpeg `loudnorm` filter with measured integrated, true peak, and LRA parameters.
