---
document_id: 04_production_and_editing_pipelines
title: "Multi-Model Production & Editing Pipelines"
category: "Production Pipelines"
version: "1.0"
platforms: ["DaVinci Resolve", "CapCut Pro", "Premiere Pro"]
last_updated: "2026-08-21"
---

# Doc 4: Multi-Model Production & Editing Pipelines

This document details your physical editing workflows. To balance visual mastery with extreme speed, we establish a **Dual-Track Production Pipeline**. Creators or editors can select the high-fidelity stack for marquee, high-impact festival drops, or the 15-minute fast-track stack for daily, high-frequency posting.

---

## 1. Track A: The High-Fidelity "North Star" Pipeline [9, 10]

This multi-model AI pipeline is designed to eliminate "festival haze" and phone audio distortion, delivering polished, studio-quality vertical concert captures [7, 13].

```
Raw Clip ──▶ [Librosa/Demucs] ──▶ [iZotope RX] ──▶ [FabFilter Pro-L2] ──▶ [Topaz Video AI] ──▶ [DaVinci Resolve]
```

### Stage 1: Ingestion & Drop Detection [10]
*   **Tool:** Librosa & Demucs Python Library [10].
*   **Settings/Parameters:** RMS energy threshold `>0.8` to automatically flag peak musical drops [10]. Set Demucs stem separation for the `'Other'` stem (isolating the electronic music feed from crowd noises) [10].

### Stage 2: Audio DSP & Noise Cleanup [10]
*   **Tool:** iZotope RX [10].
*   **Settings/Parameters:** Spectral Repair [10]. Apply high-pass filter to remove low-end rumble below `40Hz` [10]. Apply De-clip to salvage overloaded phone recordings [10].

### Stage 3: Audio Mastering [10]
*   **Tool:** FabFilter Pro-L2 [10].
*   **Settings/Parameters:** Set True Peak Limiting to `-1.0dB` to prevent digital clipping [10]. Set style to **Dynamic Mode** to preserve the punch and transient response of the kick and bass [10].

### Stage 4: Video Restoration & Upscaling [10]
*   **Tool:** Topaz Video AI [10].
*   **Settings/Parameters:** Apply **Nyx** (for noisy, high-ISO low-light concert footage) or **Proteus** (Fine Tune for stage details) [10]. Execute a **2x Upscale to 4K** to force higher-bitrate ingestion on platform servers [10].

### Stage 5: Assembly & Smart Reframe [10]
*   **Tool:** DaVinci Resolve [10].
*   **Settings/Parameters:** Open a `1080x1920` vertical project [10]. Use **Smart Reframe** (Face/Action tracking) to automatically lock the center crop onto the DJ decks or primary laser array [8, 10].

---

## 2. Track B: The 15-Minute Fast-Track SOP [17, 18]

When time is limited, this streamlined two-tool setup replaces standalone DAWs and scripts, transforming raw phone footage into high-impact vertical clips with minimal friction [16, 17].

### Tool Setup [17, 18]
*   **Primary Video Editor:** CapCut Pro or Premiere Pro (utilizes Auto-Reframing and Beat Transient detection) [17].
*   **Primary Audio Enhancer:** AI-driven 1-Knob De-Noise, 40 Hz Low-Cut, and automated normalization to `-14 LUFS` [18].

### The Step-by-Step SOP [18]

1.  **Ingest & Scrub:** Identify a sequence featuring exactly **4 seconds of build-up** followed by **12–16 seconds of drop payoff** [18].
2.  **Audio Clean & Bass Tame:** Apply the 1-click AI cleanup, set the 40 Hz low-cut filter, and normalize to secure True Peak headroom [18].
3.  **Vertical Framing:** Reframe the video to a `9:16` vertical aspect ratio, verifying all critical visual action stays within the **900x1160 px Safe Zone** [18].
4.  **Track ID Overlay:** Apply a dynamic kinetic text template (using drop shadows for readability) to display the Track ID [17, 18].
5.  **Infinite Loop:** Create an 8-bar audio crossfade utilizing a **30ms micro-fade** at the edit point to ensure a seamless loop [18].
6.  **Export:** Use the target export presets [18].

---

## 3. Unified Master Export Preset [18, 23, 49]

Regardless of which production track is utilized, all final exports must meet these technical publishing targets to prevent platform compression degradation:

*   **Format/Codec:** H.264 (MP4 container) [23, 49]
*   **Resolution:** 1080 x 1920 (Vertical 9:16 Aspect Ratio) [23, 49]
*   **Frame Rate:** 60fps Constant Frame Rate (CFR) [23, 49]
*   **Audio Codec:** AAC at 320kbps stereo [49]
*   **Target Bitrate:** 10–12 Mbps (absolute range: 8–12 Mbps) [18, 23]

---

## 4. Multi-Genre Editing & Visual Pacing [37]

Different EDM subgenres require distinct visual cutting speeds and focal points to maintain on-screen energy [36].

### Bass Music / Dubstep / Trap (140–150 BPM) [37]
*   **Hook Strategy:** Start **1.5 seconds before the drop**, capturing the final riser build, and cut precisely as the bass drop hits and pyrotechnics trigger [37].
*   **Visual Focus:** Kinetic zoom edits [7], high-contrast rail-riding crowd reactions, headbanging, and intense stage lighting flashes [37].

### House / Tech House / Techno (124–130 BPM) [37]
*   **Hook Strategy:** Utilize continuous 4/4 beat structures [37]. Cut into a rolling groove or vocal hook, trimming the video precisely on a **4-bar or 8-bar measure** to create an endless loop [37].
*   **Visual Focus:** Hypnotic laser sweeps, warehouse club lighting, and DJ deck hand movements [37].

### Trance / Melodic Dubstep / Future Bass (138–145 BPM) [37]
*   **Hook Strategy:** Focus on emotional vocal climaxes and synth buildups leading into bright laser shows [37].
*   **Visual Focus:** Wide festival stage shots showing massive laser light canopies and crowd singing moments [37].

### Drum & Bass / Hardstyle (150–175+ BPM) [37]
*   **Hook Strategy:** Rapid cuts synced to fast kick drums or double-time rhythms to maintain visual pacing [37].
*   **Visual Focus:** High-speed strobe effects, light flashes, and fast-paced crowd energy [37].
