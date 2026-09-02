# -*- coding: utf-8 -*-
import pathlib

target_file = pathlib.Path('G:/My Drive/GOOGLE ANTIGRAVITY/content_creation/V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md')
target_file.parent.mkdir(parents=True, exist_ok=True)

with open(target_file, 'w', encoding='utf-8') as out:
    # ----------------------------------------------------
    # BLOCK 1: FRONTMATTER & TABLE OF CONTENTS
    # ----------------------------------------------------
    out.write(r"""---
document_id: V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT
title: "Master Operational Blueprint for EDM Short-Form Content Strategy V2: Autonomous AI Master Mind Edition"
version: "2.0.0"
architecture: "Autonomous AI Master Mind Orchestration"
target_platforms: ["YouTube Shorts", "TikTok", "Instagram Reels"]
brands: ["@LaserBaptismLive", "@MusicBaptismLive"]
spec_version: "2026.1"
last_updated: "2026-08-22"
author: "Antigravity AI Media Engineering & Orchestration Architecture"
---

# Master Operational Blueprint for EDM Short-Form Content Strategy (V2 Consolidated Master Blueprint)

> **Document Type:** Master Architectural Specification & Operational Execution Runbook  
> **Target Directory:** `content_creation/` (Track 2: Media Engineering & Audio/Video Pipeline Automation)  
> **Autonomous Agent Role:** Central "Master Mind" Execution Engine  
> **Hardware Target:** NVIDIA NVENC / Intel QSV Hardware Transcode Acceleration, Librosa Audio DSP, Model Context Protocol (MCP) Drive Bridge

---

## Table of Contents
1. [Executive Architecture Manifest & System Vision](#1-executive-architecture-manifest--system-vision)
   - 1.1 [The Paradigm Shift: From Fragmented Manual Editing to AI Master Mind Orchestration](#11-the-paradigm-shift-from-fragmented-manual-editing-to-ai-master-mind-orchestration)
   - 1.2 [Master Brand Identity Matrix: Laser Baptism vs. Music Baptism](#12-master-brand-identity-matrix-laser-baptism-vs-music-baptism)
   - 1.3 [Three-Tier Content Pillar Classification](#13-three-tier-content-pillar-classification)
   - 1.4 [Dual-Brand Routing Logic & Automated Visual Classification](#14-dual-brand-routing-logic--automated-visual-classification)
   - 1.5 [System High-Level Topology & Flowchart Diagram](#15-system-high-level-topology--flowchart-diagram)
2. [Comprehensive Technical Guardrails & Parameter Matrix](#2-comprehensive-technical-guardrails--parameter-matrix)
   - 2.1 [Video Engineering & Transcoding Standards](#21-video-engineering--transcoding-standards)
   - 2.2 [Visual Safe Zones & Geometry Specifications](#22-visual-safe-zones--geometry-specifications)
   - 2.3 [Audio Engineering, Mastering & Loudness Matrix](#23-audio-engineering-mastering--loudness-matrix)
   - 2.4 [Pacing, Duration & Genre BPM Pacing Formulas](#24-pacing-duration--genre-bpm-pacing-formulas)
   - 2.5 [Platform Copyright & Content ID Policy Enforcement](#25-platform-copyright--content-id-policy-enforcement)
3. [Concrete Agent-Executable Technical Mechanisms](#3-concrete-agent-executable-technical-mechanisms)
   - 3.1 [Mechanism 1: MCP Asset Ingestion & Routing Engine (`ingest_watcher.py`)](#31-mechanism-1-mcp-asset-ingestion--routing-engine-ingest_watcherpy)
   - 3.2 [Mechanism 2: Librosa & FFmpeg Audio DSP Analyzer (`audio_dsp.py`)](#32-mechanism-2-librosa--ffmpeg-audio-dsp-analyzer-audio_dsppy)
   - 3.3 [Mechanism 3: FFmpeg Hardware-Accelerated Master Transcoder (`video_transcoder.py`)](#33-mechanism-3-ffmpeg-hardware-accelerated-master-transcoder-video_transcoderpy)
   - 3.4 [Mechanism 4: Headless Automated Quality Control (QC) Validator (`qc_validator.py`)](#34-mechanism-4-headless-automated-quality-control-qc-validator-qc_validatorpy)
   - 3.5 [Automation of Manual GUI Editing Tasks](#35-automation-of-manual-gui-editing-tasks)
4. [Operational Execution Pipelines & Dual-Track SOPs](#4-operational-execution-pipelines--dual-track-sops)
   - 4.1 [End-to-End 5-Phase Agent Orchestration Lifecycle](#41-end-to-end-5-phase-agent-orchestration-lifecycle)
   - 4.2 [Track A: High-Fidelity "North Star" Pipeline (Multi-Model Automated Stack)](#42-track-a-high-fidelity-north-star-pipeline-multi-model-automated-stack)
   - 4.3 [Track B: 15-Minute Fast-Track Pipeline (High-Velocity SOP)](#43-track-b-15-minute-fast-track-pipeline-high-velocity-sop)
   - 4.4 [Automated Competitive Intelligence & Trend Tracker](#44-automated-competitive-intelligence--trend-tracker)
   - 4.5 [Pre-Production Storyboarding & Web Publishing](#45-pre-production-storyboarding--web-publishing)
5. [Platform-Specific Configuration & Distribution Playbooks](#5-platform-specific-configuration--distribution-playbooks)
   - 5.1 [YouTube Shorts Platform Configuration Matrix & Unlisted SOP](#51-youtube-shorts-platform-configuration-matrix--unlisted-sop)
   - 5.2 [TikTok Platform Configuration & High-Quality Upload Protocol](#52-tiktok-platform-configuration--high-quality-upload-protocol)
   - 5.3 [TikTok Ghost-Linking Audio Synchronization](#53-tiktok-ghost-linking-audio-synchronization)
   - 5.4 [Caption SEO & 5–7 Hashtag Taxonomy](#54-caption-seo--57-hashtag-taxonomy)
   - 5.5 [Universal 17-Keyword Spam & Phishing Comment Blocklist](#55-universal-17-keyword-spam--phishing-comment-blocklist)
   - 5.6 [First-Hour Community Engagement Velocity Playbook](#56-first-hour-community-engagement-velocity-playbook)
   - 5.7 [Daily Publishing Timing & Multi-Timezone Cadence](#57-daily-publishing-timing--multi-timezone-cadence)
6. [Hybrid Storage & Asset Lifecycle Architecture](#6-hybrid-storage--asset-lifecycle-architecture)
   - 6.1 [4-Folder Hybrid Drive Taxonomy](#61-4-folder-hybrid-drive-taxonomy)
   - 6.2 [Standardized File Naming Convention](#62-standardized-file-naming-convention)
   - 6.3 [50-Item Folder Health & Auto-Partitioning Overflow Rule](#63-50-item-folder-health--auto-partitioning-overflow-rule)
   - 6.4 [Asset Promotion & Quarantine Workflow](#64-asset-promotion--quarantine-workflow)
7. [Future Content Concepts & Creative Formats](#7-future-content-concepts--creative-formats)
   - 7.1 [The 8 Core Creative Concepts](#71-the-8-core-creative-concepts)
8. [Troubleshooting, Edge Cases & Failure Recovery Playbook](#8-troubleshooting-edge-cases--failure-recovery-playbook)
   - 8.1 [Exhaustive Edge Cases & Concrete Remediation Matrix](#81-exhaustive-edge-cases--concrete-remediation-matrix)
9. [Agent Validation Matrix & System Context Injection](#9-agent-validation-matrix--system-context-injection)
   - 9.1 [System Context Prompt for EDM Short-Form Automation Assistant](#91-system-context-prompt-for-edm-short-form-automation-assistant)
   - 9.2 [Robust Gemini AI Studio / Gemini Advanced Adversarial Validation Audit Prompt](#92-robust-gemini-ai-studio--gemini-advanced-adversarial-validation-audit-prompt)
""")

    # ----------------------------------------------------
    # BLOCK 2: SECTION 1 (EXECUTIVE ARCHITECTURE)
    # ----------------------------------------------------
    out.write(r"""
---

## 1. Executive Architecture Manifest & System Vision

### 1.1 The Paradigm Shift: From Fragmented Manual Editing to AI Master Mind Orchestration

The initial V1 short-form operational framework was fragmented across disparate standalone graphical user interfaces (GUIs)—requiring human operators to manually transfer files across storage directories, adjust spectral de-noising in iZotope RX, tune dynamic limiters in FabFilter Pro-L2, queue GPU upscales in Topaz Video AI, keyframe subject tracking in DaVinci Resolve or CapCut Pro, and manually fill out metadata and setting forms in YouTube Studio and TikTok. This manual workflow introduced severe digital friction, inconsistent audio mastering tolerances, frequent copyright duration oversights, and throughput limitations.

In **V2**, the entire ecosystem is consolidated into an **Autonomous AI Agent "Master Mind" Architecture**. The AI Agent acts as the central execution engine, replacing human GUI friction with programmatic, headless, reproducible pipelines. Operating directly within `content_creation/`, the agent:
1. **Listens and Ingests:** Monitors incoming raw concert recordings across cloud and local drop zones via the Model Context Protocol (MCP) Google Drive bridge and local filesystem event watchers.
2. **Performs Signal Telemetry & Audio DSP:** Executes headless audio analysis (transient onsets, RMS energy curves, BPM tempo estimation, and spectral clarity) using Python (`librosa`, `scipy`) and metadata extraction via `ffprobe`.
3. **Constructs Dynamic Filtergraphs:** Generates parameterized FFmpeg hardware-accelerated filtergraphs for smart 9:16 vertical re-framing, spatio-temporal low-light denoising (`hqdn3d`), dynamic range preservation, safe-zone kinetic text overlays, 40Hz/80Hz high-pass filtering, and two-pass EBU R128 loudness normalization.
4. **Enforces Strict Automated QC:** Validates every rendered master against rigorous mathematical criteria (aspect ratio, CFR framerate, duration $\le 59.00$s, $-14\text{ LUFS} \pm 1.0\text{ LUFS}$, $\le -1.5\text{ dBTP}$) before permitting promotion to publishing tiers.
5. **Packages Omnichannel Payloads:** Compiles platform-ready payloads containing keyword-optimized captions, 5–7 hashtag taxonomies, first-hour engagement hooks, and ghost-linking sync instructions.

```
+----------------------------------------------------------------------------------------------------+
|                                  AI AGENT MASTER MIND ORCHESTRATOR                                 |
+----------------------------------------------------------------------------------------------------+
|  [Ingestion & Routing]         [Signal Analysis & DSP]          [Hardware Transcoder]              |
|  - MCP Google Drive Bridge     - Librosa Transient Detection    - FFmpeg NVENC/AV1 Pipeline        |
|  - EXIF/XMP Metadata Parser    - RMS Energy Drop Locator (>0.8) - Spatio-Temporal Denoise (hqdn3d) |
|  - 4-Folder Hybrid Router      - Two-Pass EBU R128 Loudnorm     - 9:16 Safe-Zone Smart Reframe     |
+----------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                               AUTOMATED VERIFICATION & QC COMPLIANCE                               |
|  - Strict 59.0s Duration Ceiling (Content ID Guardrail)  - 1080x1920 @ 60fps CFR Assertion         |
|  - Integrated Loudness: -14.0 LUFS (+-1.0 LUFS)         - True Peak: <= -1.5 dBTP Verification     |
|  - Universal Safe Zone Boundary Enforcement              - Signed Machine-Readable qc_report.json   |
+----------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                OMNICHANNEL DISTRIBUTION & STAGING                                  |
|  - YouTube Shorts: Unlisted Pre-Flight Staging Payload & 17-Keyword Moderation Blocklist           |
|  - TikTok: 1-3% Ghost-Linking Audio Sync & High-Quality Ingestion Config                           |
|  - SEO Caption Generator, 5-7 Hashtag Taxonomy, First-Hour Community Velocity Playbook             |
+----------------------------------------------------------------------------------------------------+
```

---

### 1.2 Master Brand Identity Matrix: Laser Baptism vs. Music Baptism

To comprehensively capture electronic dance music culture while preserving distinct audience expectations and algorithmic clustering, the media empire operates under two complementary brand umbrellas:

| Brand Dimension | Laser Baptism (`@LaserBaptismLive`) | Music Baptism (`@MusicBaptismLive`) |
| :--- | :--- | :--- |
| **Core Resonance** | High-energy visual spectacle, laser synchronization, and massive stage production. | Total acoustic immersion, emotional transcendence, and raw musical authenticity. |
| **Genre Scope** | Visual-centric high-energy electronic: Stadium House, Mainstage EDM, Heavy Dubstep, Tearout, Peak-Time Techno, Hardstyle. | Multi-genre artistic freedom: Tech House, Deep House, Melodic Techno, Progressive Trance, Liquid & Neurofunk DnB, Future Bass, Live Vocal Sets. |
| **Atmospheric Scope** | Stadium arenas, festival mainstages, mega-structure laser canopies, high-end nightclub lighting grids. | Underground warehouse raves, intimate club booths, sunrise open-air day parties, sunset beach stages, acoustic live sessions. |
| **Official Handles** | `@LaserBaptismLive`, `@LaserBaptismClips` | `@MusicBaptism`, `@MusicBaptismLive` |
| **Visual Iconography** | Neon laser beam piercing a high-contrast synthesizer waveform on a deep black field (`#000000`). | Intimate DJ deck POV, glowing mixer LED meters, vinyl/fader close-ups, warm analog lighting. |
| **Audience Hook** | "Look at this insane production and explosive drop!" | "Listen to this incredible unreleased ID and emotional transition." |

---

### 1.3 Three-Tier Content Pillar Classification

All raw footage and finished assets are categorized into a 3-tier pillar structure for automated cataloging, indexing, and playlist routing:

*   **Pillar A: Big Artist Stadium & Arena Shows**
    *   *Scope & Artists:* Major headliner one-off stadium and arena tours (e.g., Skrillex, Martin Garrix, Charlotte de Witte, Excision, John Summit, Subtronics, Tiësto, Swedish House Mafia).
    *   *Genres:* Mainstage House, Heavy Bass, Stadium Techno, Peak-Time Electro.
    *   *Editing Focus:* Arena-scale pyrotechnics, laser arrays, massive drop impacts, and iconic vocal choruses.
    *   *Primary Brand Routing:* `@LaserBaptismLive`
*   **Pillar B: Up-and-Coming Artist Spotlights**
    *   *Scope & Artists:* Rising talent, intimate nightclub residencies, underground warehouse raves, boiler-room style sets.
    *   *Genres:* Tech House, Underground Techno, Deep Minimal, Bassline, UK Garage, Jungle.
    *   *Editing Focus:* DJ hand movements, mixer knob adjustments, raw crowd intimacy, and prominent on-screen Track ID overlays.
    *   *Primary Brand Routing:* `#LaserBaptismID` / `@MusicBaptismLive`
*   **Pillar C: Festival Mega-Clips**
    *   *Scope & Festivals:* Multi-stage electronic music festivals (EDC Las Vegas/Orlando, Tomorrowland Belgium, Ultra Music Festival Miami, Lost Lands, Movement Detroit, Electric Forest).
    *   *Genres:* All EDM genres represented across multi-stage festival environments.
    *   *Editing Focus:* Giant stage panoramas, drone-style sweeps, firework/laser apexes, massive rail-riding crowd reactions, and multi-angle festival energy.
    *   *Primary Brand Routing:* `Laser Baptism Festival Clips` / `@LaserBaptismLive`

---

### 1.4 Dual-Brand Routing Logic & Automated Visual Classification

The AI Master Mind evaluates raw video files at ingestion and automatically assigns brand routing based on computer vision heuristics and audio frequency analysis:

```
                      [Raw Video Ingested]
                               │
                               ▼
        ┌───────────────────────────────────────────────┐
        │       Extract Video Luma Histogram & Audio     │
        │ - Peak Luma Standard Deviation (Strobe/Laser) │
        │ - High-Frequency Transient Energy Density     │
        │ - Dominant BPM & Subgenre Spectral Profile    │
        └───────────────────────────────────────────────┘
                               │
              Is Strobe/Laser Peak Luma > Threshold
               AND Genre in [Dubstep, Mainstage, Hardstyle]?
                               │
                ├─── YES ────────────────────────── NO ───┐
                ▼                                         ▼
    [Route: @LaserBaptismLive]               [Route: @MusicBaptismLive]
    - Laser & Strobe Focus                   - Deck POV & Acoustic Focus
    - High-Energy Visual Pacing              - Groove & Vocal Pacing
    - Neon High-Contrast Color Grade         - Warm Organic Color Grade
```

---

### 1.5 System High-Level Topology & Flowchart Diagram

```
[01_RAW_INBOX] ──▶ [ingest_watcher.py] ──▶ [02_IN_PROGRESS/{project_id}/]
                         │
                         ▼
                 [audio_dsp.py] ──────────┐
                 - Librosa Drop Locator   │
                 - EBU R128 First-Pass    │
                 - High-Pass Filter Spec  │
                         │                │
                         ▼                ▼
               [video_transcoder.py] ◀────┘
               - 9:16 Center Crop & Re-frame
               - Low-Light Spatio-Temporal Denoise
               - Safe-Zone Kinetic Text Overlay
               - Two-Pass Audio Loudnorm (-14 LUFS)
               - Seamless 30ms Loop Crossfade
                         │
                         ▼
                [qc_validator.py]
               - ffprobe Stream Verification
               - Duration <= 59.0s Guardrail
               - Loudness: -14 LUFS / <= -1.5 dBTP
               - Safe Zone Geometry Assertion
                         │
        ┌────────────────┴────────────────┐
        ▼ [PASS]                          ▼ [FAIL]
[03_READY_TO_POST]               [02_IN_PROGRESS/Quarantine]
- Signed qc_report.json          - Diagnostic Error Log
- distribution_package.json      - Circuit Breaker Trigger
```
""")

    # ----------------------------------------------------
    # BLOCK 3: SECTION 2 (TECHNICAL GUARDRAILS)
    # ----------------------------------------------------
    out.write(r"""
---

## 2. Comprehensive Technical Guardrails & Parameter Matrix

### 2.1 Video Engineering & Transcoding Standards

All video files processed by the ecosystem must strictly adhere to the following master video engineering specifications:

| Parameter | Social Export Preset (Default) | High-Fidelity Master / Archive | 4K Upscale Target (Optional) |
| :--- | :--- | :--- | :--- |
| **Canvas Resolution** | $1080 \times 1920$ pixels | $1080 \times 1920$ pixels | $2160 \times 3840$ pixels |
| **Aspect Ratio** | 9:16 (Vertical Portrait) | 9:16 (Vertical Portrait) | 9:16 (Vertical Portrait) |
| **Frame Rate** | 60.0 fps CFR (Constant Frame Rate) | 60.0 fps CFR (Constant Frame Rate) | 60.0 fps CFR |
| **Frame Rate Fallback** | 30.0 fps CFR (if source <45 fps) | 30.0 fps CFR | 30.0 fps CFR |
| **Variable Frame Rate (VFR)** | **STRICTLY PROHIBITED** | **STRICTLY PROHIBITED** | **STRICTLY PROHIBITED** |
| **Video Codec** | H.264 (`libx264` / `h264_nvenc`) | H.265 / HEVC (`hevc_nvenc` / `libx265`) or AV1 (`av1_nvenc` / `libsvtav1`) | H.265 / HEVC (`hevc_nvenc`) |
| **Pixel Format** | `yuv420p` (8-bit SDR) | `yuv420p` (8-bit SDR) or `yuv420p10le` | `yuv420p` |
| **Target Video Bitrate** | 10.0–12.0 Mbps VBR (8.0–12.0 Mbps range) | 15.0–20.0 Mbps VBR | 30.0–40.0 Mbps VBR |
| **Max Bitrate Ceiling** | 15.0 Mbps | 25.0 Mbps | 50.0 Mbps |
| **Container** | MP4 (`.mp4`) with `+faststart` flag | MP4 (`.mp4`) with `+faststart` flag | MP4 (`.mp4`) |
| **Spatio-Temporal Denoising** | `hqdn3d=4:3:6:4.5` | `hqdn3d=4:3:6:4.5` or `nlmeans` | Topaz Video AI (Nyx / Proteus) |
| **HDR-to-SDR Tone-Mapping** | BT.709 Color Matrix (`zscale` / `tonemap`) | BT.709 Color Matrix | BT.709 Color Matrix |

*Crucial Technical Rules:*
1. **No VFR:** Variable Frame Rate video causes progressive audio/video desynchronization when uploaded to platform ingestion transcoders. All pipelines must normalize frame rates to Constant Frame Rate (`fps=fps=60`).
2. **Faststart Flag:** MP4 files must be rendered with `-movflags +faststart` to place the `moov` atom at the beginning of the file, enabling instant streaming playback.
3. **Sensor Noise vs. Laser Detail:** Low-light spatio-temporal filtering (`hqdn3d`) must be calibrated to smooth high-ISO sensor grain without softening laser beam edges or stage geometry.

---

### 2.2 Visual Safe Zones & Geometry Specifications

Platform user interfaces (UI) overlay headers, search bars, channel handles, interaction icons, sound marquees, and system navigation bars directly over the video canvas. All critical action (laser apex, DJ face, mixer decks, kinetic Track ID text) must be strictly confined to the **Universal Safe Zone**.

```
+---------------------------------------------------------------------------------------+
|                                1080 x 1920 MASTER CANVAS                              |
|                                                                                       |
|  [ Top Exclusion Zone: Y 0 - 180 px (YouTube) / Y 0 - 160 px (TikTok) ]               |
|  ...................................................................................  |
|  |                                                                                 |  |
|  |                                                                                 |  |
|  |                     UNIVERSAL SAFE CANVAS BOX                                   |  |
|  |                     - YouTube: 900 x 1160 px (X: 60-960, Y: 180-1450)           |  |
|  |                     - TikTok:  920 x 1250 px (X: 40-960, Y: 160-1470)           |  |
|  |                                                                                 |  |
|  |   [ Center all laser apex, DJ faces, build-up text, and Track ID overlays ]     |  |
|  |                                                                                 |  |
|  |                                                                                 |  |
|  ...................................................................................  |
|  [ Bottom Exclusion Zone: Y 1450 - 1920 px (YouTube) / Y 1470 - 1920 px (TikTok) ]    |
|  [ Right Rail Exclusion: X 960 - 1080 px (Action Icons on both platforms) ]           |
+---------------------------------------------------------------------------------------+
```

#### Safe Zone Boundary Coordinates Table

| Surface / Platform | Dimension / Coordinate Window | Purpose & Notes |
| :--- | :--- | :--- |
| **Master Video Canvas** | $1080 \times 1920\text{ px}$ | Vertical 9:16 aspect ratio canvas. |
| **YouTube Shorts Top Exclusion** | $Y = 0\text{ to }180\text{ px}$ | Search header, back button, camera icon, sound selector. |
| **YouTube Shorts Bottom Exclusion** | $Y = 1450\text{ to }1920\text{ px}$ | Channel avatar, `@handle`, subscribe button, title text, sound marquee. |
| **YouTube Shorts Right Rail Exclusion** | $X = 960\text{ to }1080\text{ px}$ | Like, Dislike, Comment count, Share, Remix icons. |
| **YouTube Shorts Universal Safe Box** | **$900 \times 1160\text{ px}$** ($X: 60-960, Y: 180-1450$) | **Primary action, DJ faces, Track ID, and lyrics.** |
| **TikTok Top Exclusion** | $Y = 0\text{ to }160\text{ px}$ | Following/For You tabs, Live indicator, Search icon. |
| **TikTok Bottom Exclusion** | $Y = 1470\text{ to }1920\text{ px}$ | Username, caption, translation tags, sound title, navigation bar. |
| **TikTok Right Rail Exclusion** | $X = 960\text{ to }1080\text{ px}$ | Profile follow button, Like heart, Comment, Bookmark, Share stack. |
| **TikTok Left Margin Clearance** | $X = 0\text{ to }40\text{ px}$ | Left margin padding clearance for clean visual framing. |
| **TikTok Safe Area Box** | **$920 \times 1250\text{ px}$** ($X: 40-960, Y: 160-1470$) | **Vertically centered safe area for TikTok UI.** |
| **YouTube Channel Banner Canvas** | $2048 \times 1152\text{ px}$ (16:9, max 6 MB) | Full banner canvas for TV displays. |
| **YouTube Channel Banner Safe Area** | **$1235 \times 338\text{ px}$** (Centered) | **Cross-device display box visible on mobile, desktop, and TV.** |
| **YouTube Profile Picture** | Min $98 \times 98\text{ px}$ (max 4 MB PNG/GIF) | Rendered circular; scaled to $32 \times 32\text{ px}$ on mobile Shorts feed. |
| **YouTube Desktop Watermark** | $150 \times 150\text{ px}$ square (max 1 MB) | Fixed lower-right corner on desktop horizontal player. |

---

### 2.3 Audio Engineering, Mastering & Loudness Matrix

Live concert audio suffers from extreme acoustic pressure (often exceeding 115 dB SPL), sub-bass acoustic distortion, microphone capsule clipping, and screaming crowd noise. All audio streams must undergo broadcast-grade DSP filtering and loudness normalization:

| Audio Engineering Metric | Target Specification | Enforcement Mechanism & Filter Parameters |
| :--- | :--- | :--- |
| **Integrated Loudness ($I$)** | **$-14.0\text{ LUFS}$** ($\pm 1.0\text{ LUFS}$) | Two-Pass EBU R128: `loudnorm=I=-14:LRA=7:TP=-1.5` |
| **Loudness Range ($LRA$)** | **$7.0\text{ LRA}$** | Preserves transient dynamic punch in drops while taming build-ups. |
| **True Peak Ceiling ($TP$)** | **$\le -1.5\text{ dBTP}$** (Master) / **$\le -1.0\text{ dBTP}$** (SOP) | Prevents inter-sample clipping during platform lossy transcoding. |
| **High-Pass Cutoff (Low-Cut)** | **$40\text{ Hz}$** (Studio/DAW) / **$80\text{ Hz}$** (Live Festival) | `highpass=f=40` or `highpass=f=80` (removes non-audible speaker-destroying sub-rumble). |
| **Audio Codec & Bitrate** | **AAC-LC** at **$320\text{ kbps}$**, $48\text{ kHz}$ Stereo | `-c:a aac -b:a 320k -ar 48000 -ac 2` |
| **Hybrid Audio Mixing Ratio** | **$70\%\text{ Studio Master} / 30\%\text{ Live Crowd}$** | Phase-aligned blend providing pristine music with live venue atmosphere. |
| **Waveform Phase Alignment** | Microsecond accuracy ($\Delta t < 0.5\text{ms}$) | Cross-correlation alignment preventing acoustic comb filtering. |
| **TikTok Ghost-Linking Volume** | **$1\% - 3\%\text{ Added} / 100\%\text{ Original}$** | Added official sound at 1–3%, Remastered live master at 100%. |
| **Seamless Loop Micro-Fade** | **$30\text{ ms}$** linear crossfade | `acrossfade=d=0.03:c1=tri:c2=tri` on exact 4-bar or 8-bar boundaries. |

---

### 2.4 Pacing, Duration & Genre BPM Pacing Formulas

#### Duration Guardrails & Retention Rules
*   **Optimal Duration Window:** Strictly **$15.0\text{ to }45.0\text{ seconds}$**.
*   **Absolute Hard Ceiling:** **$\le 59.00\text{ seconds}$** (Enforced mechanically to prevent YouTube Content ID Global Blocks).
*   **The 15-Minute Fast-Track Structural Blueprint:**
    *   **Phase 1 (The Hook & Build-up):** Exactly **$4.0\text{ seconds}$** of rising tension.
    *   **Phase 2 (The Drop Payoff):** **$12.0\text{ to }16.0\text{ seconds}$** of explosive visual and audio drop impact.
    *   **Total Runtime:** **$16.0\text{ to }20.0\text{ seconds}$** for maximum loop completion and audience retention rate ($>120\%$).

#### Genre-Specific BPM & Pacing Matrix

| Genre Family | Typical BPM Range | Hook Window & Edit Trigger | Visual Focus & Cutting Style |
| :--- | :--- | :--- | :--- |
| **Bass Music / Dubstep / Trap** | 140–150 BPM | Cut starts **1.5s before the drop** on the final vocal/riser build; hard cut precisely on bass drop hit and pyro ignition. | Kinetic zoom snaps, rail-riding crowd reactions, violent headbanging, high-contrast strobe flashes. |
| **House / Tech House / Techno** | 124–130 BPM | Rolling 4/4 groove; cut into vocal hook or groove; loop precisely on a **4-bar or 8-bar measure** for infinite replay. | Hypnotic laser sweeps, warehouse club lighting, DJ deck POV, hand and fader movements. |
| **Trance / Melodic / Future Bass** | 138–145 BPM | Emotional vocal climax and synth buildup leading into bright, expansive melodic drop. | Wide festival stage sweeps, massive laser canopies, emotional crowd singing moments. |
| **Drum & Bass / Hardstyle** | 150–175+ BPM | Rapid cuts synchronized to double-time kick drums, snare rolls, or reverse-bass triplets. | High-speed strobe effects, kinetic flash cuts, fast-paced crowd energy. |

---

### 2.5 Platform Copyright & Content ID Policy Enforcement

Managing intellectual property rights is critical when distributing live concert recordings containing copyrighted musical compositions and sound recordings.

```
                          [Video Rendered]
                                 │
                   Is Duration <= 59.00 Seconds?
                                 │
                 ├─── YES ─────────────── NO ───┐
                 ▼                              ▼
    [Standard Content ID Claim]         [AUTOMATIC GLOBAL BLOCK]
    - Video remains LIVE worldwide      - Video blocked in all countries
    - Ad revenue shared with label      - Channel reach demoted
    - 0 Copyright Strikes               - Severe algorithmic penalty
    - Channel standing clean            - AUTOMATICALLY REJECTED BY QC
```

#### Copyright Enforcement Matrix

| Enforcement Type | Trigger Condition in EDM Content | Channel Impact | Monetization Status | Automated Mitigation Workflow |
| :--- | :--- | :--- | :--- | :--- |
| **In-App Shorts Audio** | Licensing official audio via in-app YouTube Shorts sound library ($\le 60\text{s}$). | Fully compliant; 0 strikes; positive algorithmic discovery. | Monetized via Shorts Creator Pool revenue share. | Used when adding studio track over pure visual concert footage. |
| **Standard Content ID Claim** | Live concert audio recognized in raw venue recordings ($\le 59.00\text{s}$). | No copyright strikes; video remains **LIVE globally**. | Ad revenue redirected to artist/record label. | **Standard Operating Procedure.** Keep all clips strictly $\le 59.00\text{s}$. |
| **Global Block (61–180s)** | Content ID match on vertical video between 61 and 180 seconds. | **Video blocked worldwide**; suppresses channel distribution. | Unmonetized; hidden from public feeds. | **Strict QC Duration Ceiling:** Never export or publish vertical clips $>59.00\text{s}$. Stage all uploads as **Unlisted** for 30–60 min hold. |
| **DMCA Takedown Notice** | Direct legal takedown by artist management (e.g., stolen unreleased studio leaks). | **1 Copyright Strike** (3 strikes in 90 days = permanent channel termination). | Video removed immediately by YouTube legal. | Strictly avoid publishing stolen studio audio leaks or prohibited exclusive festival sets. |
""")

    # ----------------------------------------------------
    # BLOCK 4: SECTION 3 (CONCRETE AGENT-EXECUTABLE MECHANISMS)
    # ----------------------------------------------------
    out.write(r"""
---

## 3. Concrete Agent-Executable Technical Mechanisms

To eliminate human manual editing bottlenecks, the AI Master Mind executes four concrete, headless technical mechanisms implemented in Python and FFmpeg:

### 3.1 Mechanism 1: MCP Asset Ingestion & Routing Engine (`ingest_watcher.py`)

*   **Role:** Autonomous intake, stream telemetry probing, metadata extraction, filename standardization, and isolated workspace provisioning.
*   **Integration:** Communicates with Google Drive via Model Context Protocol (`gdrive`) or local filesystem event watchers (`watchdog`).

#### Python Interface Definition
```python
# content_creation/scripts/ingest_watcher.py
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from pathlib import Path
import subprocess
import json
import datetime

@dataclass
class RawAssetMetadata:
    source_path: str
    event_name: str
    artist: str
    track_name: str
    version: int
    resolution: str
    duration_sec: float
    fps: float
    has_audio: bool
    creation_timestamp: str

@dataclass
class IngestionManifest:
    project_id: str
    raw_asset: RawAssetMetadata
    staged_path: str
    workspace_dir: str
    brand_assignment: str  # "LaserBaptism" | "MusicBaptism"
    genre: str             # "Dubstep" | "House" | "Techno" | "Trance" | "DnB"

class AssetIngestionPipeline:
    def __init__(self, inbox_dir: Path, workspace_root: Path):
        self.inbox_dir = inbox_dir
        self.workspace_root = workspace_root

    def scan_inbox(self) -> List[Path]:
        '''Discovers pending raw video files (.mp4, .mov) in 01_RAW_INBOX.'''
        pass

    def probe_file(self, file_path: Path) -> RawAssetMetadata:
        '''Executes ffprobe to extract stream telemetry and container metadata.'''
        pass

    def standardize_filename(self, metadata: RawAssetMetadata) -> str:
        '''Generates YYYYMMDD_[Event]_[Artist]_[TrackName]_V[#]_[Res].mp4.'''
        pass

    def provision_project_workspace(self, file_path: Path, metadata: RawAssetMetadata) -> IngestionManifest:
        '''Creates 02_IN_PROGRESS/{project_id} and moves raw file into staging.'''
        pass
```

#### JSON Schema (`ingestion_manifest.json`)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "IngestionManifest",
  "type": "object",
  "properties": {
    "project_id": {"type": "string"},
    "brand_assignment": {"type": "string", "enum": ["LaserBaptism", "MusicBaptism"]},
    "genre": {"type": "string", "enum": ["Dubstep", "House", "Techno", "Trance", "DnB", "Hardstyle"]},
    "source_file": {"type": "string"},
    "staged_file": {"type": "string"},
    "target_aspect_ratio": {"type": "string", "default": "9:16"},
    "target_resolution": {"type": "string", "default": "1080x1920"},
    "duration_sec": {"type": "number"},
    "fps": {"type": "number"}
  },
  "required": ["project_id", "brand_assignment", "genre", "source_file", "staged_file", "duration_sec", "fps"]
}
```

#### CLI Execution Command
```bash
python content_creation/scripts/ingest_watcher.py \
  --inbox "G:/My Drive/GOOGLE ANTIGRAVITY/content_creation/01_RAW_INBOX" \
  --workspace "G:/My Drive/GOOGLE ANTIGRAVITY/content_creation/02_IN_PROGRESS" \
  --auto-route
```

---

### 3.2 Mechanism 2: Librosa & FFmpeg Audio DSP Analyzer (`audio_dsp.py`)

*   **Role:** Audio stream extraction, RMS energy envelope calculation, drop detection, genre-specific hook extraction, high-pass filter calculation, and two-pass EBU R128 loudness analysis.

#### Python Interface Definition
```python
# content_creation/scripts/audio_dsp.py
from dataclasses import dataclass
from typing import Dict, Any, Tuple
from pathlib import Path
import json

@dataclass
class DropSegment:
    build_start_sec: float
    drop_hit_sec: float
    payoff_end_sec: float
    total_duration_sec: float
    estimated_bpm: float

@dataclass
class LoudnessStats:
    integrated_lufs: float
    loudness_range: float
    true_peak_dbtp: float
    threshold: float
    offset: float

class AudioDSPAnalyzer:
    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

    def detect_drop_segment(self, audio_file: Path, genre: str) -> DropSegment:
        '''
        Uses librosa to compute onset envelope and RMS energy.
        Applies genre-specific pacing:
        - Dubstep/Bass: Start 1.5s before drop peak.
        - House/Techno: Start on 4-bar vocal/groove, trim on 8-bar loop.
        - Trance: Start on vocal riser into laser climax.
        - DnB: Fast transient sync.
        Clamps total duration to 15.0 - 45.0s (strictly <= 59.0s).
        '''
        pass

    def analyze_ebur128_first_pass(self, audio_file: Path) -> LoudnessStats:
        '''
        Executes FFmpeg ebur128 first pass:
        ffmpeg -i input.wav -af loudnorm=I=-14:LRA=7:TP=-1.5:print_format=json -f null -
        Parses JSON output for measured_I, measured_LRA, measured_TP, measured_thresh, offset.
        '''
        pass

    def build_audio_filter_graph(self, stats: LoudnessStats, highpass_hz: int = 40) -> str:
        '''
        Constructs FFmpeg audio filter string:
        highpass=f={highpass_hz},loudnorm=I=-14:LRA=7:TP=-1.5:measured_I={stats.integrated_lufs}:measured_LRA={stats.loudness_range}:measured_TP={stats.true_peak_dbtp}:measured_thresh={stats.threshold}:offset={stats.offset}:linear=true,alimiter=limit=-1.5dB:attack=5:release=50
        '''
        pass
```

#### CLI Execution Command
```bash
python content_creation/scripts/audio_dsp.py \
  --input "G:/My Drive/GOOGLE ANTIGRAVITY/content_creation/02_IN_PROGRESS/PRJ_001/raw_audio.wav" \
  --genre "Dubstep" \
  --highpass 40 \
  --output-json "G:/My Drive/GOOGLE ANTIGRAVITY/content_creation/02_IN_PROGRESS/PRJ_001/audio_dsp_manifest.json"
```

---

### 3.3 Mechanism 3: FFmpeg Hardware-Accelerated Master Transcoder (`video_transcoder.py`)

*   **Role:** Constructs complex FFmpeg filtergraphs for 9:16 vertical center-cropping, spatio-temporal low-light denoising (`hqdn3d`), HDR-to-SDR tone-mapping, dynamic safe-zone kinetic text overlays, two-pass audio normalization, and 30ms seamless loop crossfades.

#### Python Interface Definition
```python
# content_creation/scripts/video_transcoder.py
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

@dataclass
class SafeZoneConfig:
    canvas_w: int = 1080
    canvas_h: int = 1920
    yt_safe_w: int = 900
    yt_safe_h: int = 1160
    tiktok_safe_w: int = 920
    tiktok_safe_h: int = 1250

@dataclass
class TranscodeConfig:
    input_video: Path
    input_audio: Optional[Path]
    output_path: Path
    start_time_sec: float
    duration_sec: float
    track_id_text: str
    artist_text: str
    event_text: str
    denoise_enabled: bool = True
    hardware_accel: str = "nvenc"  # "nvenc" | "qsv" | "cpu"
    target_bitrate_kbps: int = 12000

class FFmpegMasterTranscoder:
    def __init__(self, safe_zones: SafeZoneConfig = SafeZoneConfig()):
        self.safe_zones = safe_zones

    def construct_video_filter(self, config: TranscodeConfig) -> str:
        '''
        Builds video filter graph:
        1. Crop to 9:16: crop=w=ih*(9/16):h=ih:x=(iw-ow)/2:y=0,scale=1080:1920
        2. Denoise: hqdn3d=4:3:6:4.5
        3. Dynamic Text Overlay in Safe Zone (Y: 300 to 500 px):
           drawtext=text='{config.artist_text} - {config.track_id_text}':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.6:boxborderw=10:x=(w-text_w)/2:y=350
        '''
        pass

    def execute_transcode(self, config: TranscodeConfig, audio_filter: str) -> bool:
        '''Executes FFmpeg subprocess with NVENC/QSV hardware acceleration.'''
        pass
```

#### Concrete Production FFmpeg CLI Commands

**1. NVIDIA NVENC Hardware-Accelerated Transcode (Master Production):**
```bash
ffmpeg -y -ss 00:00:14.500 -t 00:00:19.500 -i raw_input.mp4 \
  -filter_complex "[0:v]crop=w=ih*(9/16):h=ih:x=(iw-ow)/2:y=0,scale=1080:1920:flags=lanczos,hqdn3d=4:3:6:4.5,drawtext=text='John Summit - Where You Are':fontcolor=white:fontsize=46:box=1:boxcolor=black@0.6:boxborderw=12:x=(w-text_w)/2:y=340[v];[0:a]highpass=f=40,loudnorm=I=-14:LRA=7:TP=-1.5:measured_I=-18.2:measured_LRA=8.5:measured_TP=-0.4:measured_thresh=-28.5:offset=0.2:linear=true,alimiter=limit=-1.5dB:attack=5:release=50[a]" \
  -map "[v]" -map "[a]" \
  -c:v hevc_nvenc -preset p6 -tune hq -b:v 14M -maxrate 20M -bufsize 28M -r 60 \
  -c:a aac -b:a 320k -ar 48000 -movflags +faststart \
  output_master.mp4
```

**2. CPU Fallback Transcode (libx264):**
```bash
ffmpeg -y -ss 00:00:14.500 -t 00:00:19.500 -i raw_input.mp4 \
  -filter_complex "[0:v]crop=w=ih*(9/16):h=ih:x=(iw-ow)/2:y=0,scale=1080:1920,hqdn3d=4:3:6:4.5,drawtext=text='Excision - Feel Something':fontcolor=white:fontsize=46:box=1:boxcolor=black@0.6:boxborderw=12:x=(w-text_w)/2:y=340[v];[0:a]highpass=f=80,loudnorm=I=-14:LRA=7:TP=-1.5:measured_I=-16.5:measured_LRA=6.2:measured_TP=-0.1:measured_thresh=-26.8:offset=-0.5:linear=true[a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -preset slow -crf 18 -r 60 \
  -c:a aac -b:a 320k -ar 48000 -movflags +faststart \
  output_master.mp4
```

**3. Seamless 30ms Audio Crossfade for Endless Loop Replay:**
```bash
ffmpeg -y -i clip.mp4 \
  -filter_complex "[0:a]asplit=2[a1][a2];[a1]atrim=start=0:end=19.470[a_main];[a2]atrim=start=19.470:end=19.500[a_tail];[a_tail][a_main]acrossfade=d=0.03:c1=tri:c2=tri[a_out]" \
  -map 0:v -map "[a_out]" -c:v copy -c:a aac -b:a 320k loop_master.mp4
```

---

### 3.4 Mechanism 4: Headless Automated Quality Control (QC) Validator (`qc_validator.py`)

*   **Role:** Mathematical validation of rendered files against platform constraints before promotion from `02_IN_PROGRESS` to `03_READY_TO_POST`.
*   **Rules:** Duration $\le 59.00$s, Resolution $== 1080\times 1920$, Framerate $== 60.0$ fps CFR, $-15.0\text{ LUFS} \le \text{Integrated Loudness} \le -13.0\text{ LUFS}$, $\text{True Peak} \le -1.5\text{ dBTP}$.

#### Python Interface Definition
```python
# content_creation/scripts/qc_validator.py
from dataclasses import dataclass
from typing import Dict, Any, List
from pathlib import Path
import json

@dataclass
class QCReport:
    file_path: str
    passed: bool
    duration_sec: float
    duration_compliant: bool      # <= 59.0s
    resolution: str
    resolution_compliant: bool    # 1080x1920
    framerate_fps: float
    framerate_compliant: bool     # 60.0 fps CFR
    integrated_lufs: float
    lufs_compliant: bool          # -14.0 +/- 1.0 LUFS
    true_peak_dbtp: float
    peak_compliant: bool          # <= -1.5 dBTP
    failure_reasons: List[str]

class AutomatedQCVerifier:
    def __init__(self, max_duration: float = 59.0, target_lufs: float = -14.0, max_peak: float = -1.5):
        self.max_duration = max_duration
        self.target_lufs = target_lufs
        self.max_peak = max_peak

    def inspect_streams(self, file_path: Path) -> Dict[str, Any]:
        '''Runs ffprobe -show_format -show_streams -print_format json.'''
        pass

    def inspect_audio_ebur128(self, file_path: Path) -> Dict[str, float]:
        '''Runs ffmpeg -i file -af ebur128=peak=true -f null - and parses output.'''
        pass

    def evaluate_compliance(self, file_path: Path) -> QCReport:
        '''Evaluates all criteria and generates formal signed QC report.'''
        pass
```

#### JSON Schema (`qc_report.json`)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "QCReport",
  "type": "object",
  "properties": {
    "file_path": {"type": "string"},
    "passed": {"type": "boolean"},
    "metrics": {
      "type": "object",
      "properties": {
        "duration_sec": {"type": "number"},
        "resolution": {"type": "string"},
        "framerate_fps": {"type": "number"},
        "integrated_lufs": {"type": "number"},
        "true_peak_dbtp": {"type": "number"}
      },
      "required": ["duration_sec", "resolution", "framerate_fps", "integrated_lufs", "true_peak_dbtp"]
    },
    "compliance": {
      "type": "object",
      "properties": {
        "duration_compliant": {"type": "boolean"},
        "resolution_compliant": {"type": "boolean"},
        "framerate_compliant": {"type": "boolean"},
        "lufs_compliant": {"type": "boolean"},
        "peak_compliant": {"type": "boolean"}
      },
      "required": ["duration_compliant", "resolution_compliant", "framerate_compliant", "lufs_compliant", "peak_compliant"]
    },
    "failure_reasons": {
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": ["file_path", "passed", "metrics", "compliance", "failure_reasons"]
}
```

#### CLI Execution Command
```bash
python content_creation/scripts/qc_validator.py \
  --input "G:/My Drive/GOOGLE ANTIGRAVITY/content_creation/02_IN_PROGRESS/PRJ_001/output_master.mp4" \
  --promote-dir "G:/My Drive/GOOGLE ANTIGRAVITY/content_creation/03_READY_TO_POST"
```

---

### 3.5 Automation of Manual GUI Editing Tasks

The table below demonstrates how every legacy manual GUI editing task across DaVinci Resolve, CapCut Pro, iZotope RX, FabFilter Pro-L2, Topaz Video AI, and platform settings is transformed into an autonomous agent pipeline:

| Original Production Step | Legacy Manual GUI Tool | Manual Bottleneck | Autonomous AI Agent Pipeline | Automated Implementation |
| :--- | :--- | :--- | :--- | :--- |
| **Drop Detection & Scrubbing** | Audacity / Ableton / Manual Playhead Scrub | Listening through 20 minutes of footage to find drop impact. | `AudioDSPAnalyzer` (`audio_dsp.py`) | Librosa calculates RMS energy envelope; flags timestamps where $\text{RMS} > 0.8$; auto-extracts 4s build + 16s drop. |
| **Audio Stem Separation** | Demucs GUI / Manual Vocal Isolation | Manual export of individual stems. | Headless `demucs` CLI | Automated extraction of `'Other'` stem (synths, drums, bass) separating music from crowd screams. |
| **Sub-Bass Cleanup** | iZotope RX High-Pass Plugin | Opening DAW, inserting plugin, rendering offline WAV. | FFmpeg `highpass=f=40` or `f=80` | Programmatic DSP filter integrated directly into transcode filtergraph. |
| **Audio De-Clipping** | iZotope RX De-Clip Module | Adjusting threshold sliders by hand. | Automated EBU R128 First Pass + Limiter | Soft peak limiting (`alimiter=limit=-1.5dB`) and two-pass dynamic loudness normalization. |
| **Audio Loudness Normalization** | FabFilter Pro-L2 (Dynamic Mode) | Manual visual metering and ceiling adjustment. | FFmpeg `loudnorm` filter | Two-pass normalization targeting exactly $-14.0\text{ LUFS} \pm 1.0\text{ LUFS}$ and $\le -1.5\text{ dBTP}$. |
| **Low-Light Sensor Denoising** | Topaz Video AI (Nyx / Proteus GUI) | Heavy GPU render queue, manual slider tuning. | FFmpeg `hqdn3d=4:3:6:4.5` / NVENC | High-speed hardware-accelerated spatio-temporal filter preserving laser beam sharpness. |
| **Vertical Re-framing (9:16)** | DaVinci Resolve Smart Reframe | Keyframing subject tracking manually in timeline. | Parameterized FFmpeg `crop` | Smart center-crop `crop=w=ih*(9/16):h=ih:x=(iw-ow)/2:y=0` with optional face/laser offset variables. |
| **Kinetic Text & Track ID** | CapCut Pro Text Animations | Dragging text boxes, typing track names, adjusting shadow. | FFmpeg `drawtext` Filter | Programmatic font rendering inside safe zone ($Y: 340\text{px}$) with automatic bounding box and drop shadow. |
| **Seamless Infinite Loop** | Manual timeline slicing & crossfade | Trimming bar boundaries by eye. | FFmpeg `acrossfade` Filter | Beat-matched $30\text{ms}$ micro-fade crossfade across exact 4-bar or 8-bar measures. |
| **File Renaming & Routing** | Windows File Explorer drag-and-drop | Manual file renaming and folder sorting. | `AssetIngestionPipeline` | Auto-naming `YYYYMMDD_[Event]_[Artist]_[TrackName]_V[#]_[Res].mp4` and routing across 4 tiers. |
| **Directory Capacity Health** | Manual folder item count check | Folders exceeding 50 items causing sync lag. | Directory Partition Guardrail | Checks child count; auto-creates overflow partitions (`01_RAW_INBOX/Part_02/`) at 50 items. |
| **Copyright Duration Check** | Checking video duration in properties | Accidental upload of 62s clip causing Global Block. | `AutomatedQCVerifier` Hard Ceiling | Rejects any render $>59.00\text{s}$; halts pipeline before upload. |
| **YouTube Upload Staging** | Filling forms in studio.youtube.com | Typing tags, description, unlisted toggle manually. | Staged `distribution_package.json` | Programmatic packaging with SEO description, rights disclaimer, and scheduled unlisted hold. |
| **TikTok Ghost-Linking Setup** | Searching sound and sliding volume in app | Adjusting volume sliders manually on phone. | Staged Ghost-Linking Manifest | Generates exact sound ID, timing offset, and $1-3\%$ volume execution instructions. |
""")

    # ----------------------------------------------------
    # BLOCK 5: SECTION 4 (OPERATIONAL EXECUTION PIPELINES)
    # ----------------------------------------------------
    out.write(r"""
---

## 4. Operational Execution Pipelines & Dual-Track SOPs

### 4.1 End-to-End 5-Phase Agent Orchestration Lifecycle

The complete lifecycle operates through five deterministic phases:

```
[Phase 1: Ingestion & Trigger]
  │  - Raw file dropped into 01_RAW_INBOX
  │  - ffprobe stream inspection (telemetry, duration, codec, audio)
  │  - Standardized filename assigned
  │  - Workspace provisioned in 02_IN_PROGRESS/{project_id}/
  ▼
[Phase 2: Deep Analysis & Classification]
  │  - Audio extracted to temporary WAV
  │  - Librosa computes RMS energy curve & identifies peak drop timestamp
  │  - Dual-brand routing evaluated (@LaserBaptismLive vs @MusicBaptismLive)
  │  - Genre pacing template selected (Dubstep, House, Trance, DnB)
  ▼
[Phase 3: Automated Transcoding & Assembly]
  │  - Video filtergraph constructed (9:16 crop, safe zone, hqdn3d denoise, drawtext)
  │  - Audio DSP filtergraph constructed (highpass 40/80Hz, two-pass loudnorm -14 LUFS)
  │  - 30ms seamless loop crossfade applied
  │  - Hardware-accelerated transcode executed (NVENC/AV1 60fps CFR 12-15 Mbps)
  ▼
[Phase 4: Automated Verification & QC]
  │  - ffprobe validates 1080x1920, 60fps CFR, <=59.0s duration
  │  - FFmpeg ebur128 validates -14 LUFS (+-1.0) and <= -1.5 dBTP True Peak
  │  - Pass -> Move master to 03_READY_TO_POST/ with signed qc_report.json
  │  - Fail -> Move to Quarantine with failure diagnostic report
  ▼
[Phase 5: Distribution Packaging & Metadata Staging]
  │  - Generate YouTube Shorts unlisted payload (SEO title, description, tags)
  │  - Generate TikTok payload (caption, 5-7 hashtags, ghost-linking instructions)
  │  - Generate First-Hour engagement hooks (bounty, 1-10 rating, artist tag)
  │  - Output finalized distribution_package.json
```

---

### 4.2 Track A: High-Fidelity "North Star" Pipeline (Multi-Model Automated Stack)

Designed for marquee festival drops, arena spectacles, and official press captures where maximum fidelity is paramount:

$$\text{Raw Clip} \xrightarrow{\text{Librosa RMS}>0.8} \text{Demucs 'Other'} \xrightarrow{\text{FFmpeg HPF 40Hz + De-clip}} \text{Two-Pass Loudnorm (-14 LUFS / -1.5dBTP)} \xrightarrow{\text{Topaz/NVENC Denoise}} \text{9:16 Safe Reframe}$$

1.  **Drop & Onset Isolation:** Librosa identifies the highest-energy drop window ($4.0\text{s}$ build $+ 16.0\text{s}$ payoff).
2.  **Stem Separation:** Demucs isolates the musical backing from screaming crowd bleed.
3.  **Acoustic DSP Cleanup:** High-pass filter ($40\text{ Hz}$) removes sub-audible stage rumble; soft peak limiting prevents inter-sample clipping.
4.  **Audio Mastering:** Two-pass loudness normalization locks integrated loudness to $-14.0\text{ LUFS} \pm 1.0\text{ LUFS}$ with True Peak $\le -1.5\text{ dBTP}$.
5.  **Visual Denoising & Re-framing:** Spatio-temporal filtering (`hqdn3d`) cleans high-ISO grain; 9:16 vertical crop locks onto primary laser apex.
6.  **Master Export:** 1080x1920, H.265 / HEVC, 60fps CFR, 15–20 Mbps VBR, AAC 320kbps.

---

### 4.3 Track B: 15-Minute Fast-Track Pipeline (High-Velocity SOP)

Designed for rapid daily publishing and high-frequency touring coverage:

1.  **Ingest & Scrub:** Auto-clip $4.0\text{s}$ build-up $+ 12.0\text{ to }16.0\text{s}$ drop payoff ($16.0\text{ to }20.0\text{s}$ total).
2.  **Audio Clean & Normalization:** Apply $40\text{ Hz}$ low-cut and one-pass/two-pass normalization to $-14\text{ LUFS}$.
3.  **Vertical Framing:** Auto-crop to 9:16 centered on stage action within the $900\times 1160\text{ px}$ safe zone.
4.  **Track ID Overlay:** Render kinetic font overlay with drop shadow in upper safe zone ($Y: 340\text{px}$).
5.  **Infinite Loop Crossfade:** Apply $30\text{ms}$ micro-fade audio crossfade over 4-bar or 8-bar loop.
6.  **Fast Export:** 1080x1920, H.264, 60fps CFR, 10–12 Mbps, AAC 320kbps.

---

### 4.4 Automated Competitive Intelligence & Trend Tracker

*   **Scraper Integration:** Lightweight background workers monitor YouTube Shorts and TikTok electronic music hashtags (`#EDM`, `#Dubstep`, `#TechHouse`, `#EDMTok`).
*   **Trend Metrics Parsed:** View velocity (views per hour in first 24h), sound reuse count, comment sentiment, and trending Track IDs.
*   **Weekly Action Summary:** Synthesizes algorithmic priorities into a structured JSON briefing:
    *   *Top 3 High-Velocity Subgenres* (e.g., Fast Tech House at 128 BPM, Heavy Tearout Dubstep).
    *   *Top 5 Trending Sounds* for TikTok Ghost-Linking.
    *   *Optimal Visual Editing Hooks* (e.g., rail-riding crowd zoom vs. laser canopy pan).

---

### 4.5 Pre-Production Storyboarding & Web Publishing

*   **Google Flow & Tempo Mapping:** Prior to attending festival events, the agent ingests DJ set history and track tempo databases to generate venue shot lists (e.g., expected drop at minute 14:30, 145 BPM, pyro cue).
*   **Blogger API v3 Publishing:** Automatically drafts search-indexed companion web articles featuring vertical video embeds, track release history, artist bio, and contextual links to Spotify/1001Tracklists.
""")
    # ----------------------------------------------------
    # BLOCK 6: SECTION 5 (PLATFORM CONFIGURATION & PLAYBOOKS)
    # ----------------------------------------------------
    out.write(r"""
---

## 5. Platform-Specific Configuration & Distribution Playbooks

### 5.1 YouTube Shorts Platform Configuration Matrix & Unlisted SOP

#### YouTube Studio Configuration Matrix (studio.youtube.com)

| UI Settings Tab | Configuration Parameter | Value / Setting | EDM Strategic Purpose |
| :--- | :--- | :--- | :--- |
| **General** | Currency | `USD - US Dollar` | Standardizes monetization metrics in YouTube Analytics. |
| **Channel** | Basic Info > Country | `United States` (or operational country) | Ensures correct regional algorithmic indexing. |
| **Channel** | Basic Info > Keywords | `Laser Baptism, EDM Shorts, Festival Clips, Live DJ Sets, Dubstep Drops, Tech House, Techno Raves, Trance Music, Drum and Bass, EDC, Tomorrowland, Ultra, Rising DJs, Concert POV` | Trains recommendation engine to place clips in electronic music feeds. |
| **Channel** | Advanced Settings > Audience | **"No, set this channel as not made for kids."** | **Mandatory.** Nightlife/concert content; prevents disabling of comments and monetization. |
| **Channel** | Feature Eligibility | `Intermediate & Advanced Features: ENABLED` | Unlocks custom thumbnails, longer uploads, and increased daily Shorts posting limits. |
| **Upload Defaults** | Basic Info > Description | Standard Description Template with Rights Disclaimer & Socials. | Guarantees baseline SEO metadata and intellectual property attribution. |
| **Upload Defaults** | Basic Info > Visibility | **Unlisted** | **Critical Copyright Safeguard.** Allows 30–60 min hold for Content ID scan. |
| **Upload Defaults** | Advanced > Category | **Music** | Routes clips into YouTube's music discovery algorithm. |
| **Upload Defaults** | Advanced > License | **Standard YouTube License** | Protects original camera recordings. |
| **Upload Defaults** | Advanced > Comments | **"Hold potentially inappropriate comments for review"** | Intercepts spam bots, fake ticket sellers, and phishing URLs. |
| **Community** | Automated Filters > Blocked Words | 17-Keyword Blocklist (see Section 5.5) | Automatically quarantines scam links and spam comments. |
| **Community** | Automated Filters > Block Links | **CHECKED (`true`)** | Intercepts all raw URLs and Telegram links in comments. |

#### YouTube Shorts 7-Step Publishing SOP
1.  **Export:** Render master 1080x1920 MP4 file (60fps CFR, duration $\le 59.00\text{s}$, $-14\text{ LUFS}$).
2.  **Upload:** Upload to YouTube Studio and set visibility to **Unlisted**.
3.  **Metadata:** Insert SEO Title, Description Template, and baseline hashtags (`#Shorts #EDM #LaserBaptism #LiveMusic`).
4.  **Pre-Flight Hold:** Wait **30 to 60 minutes** for HD/VP09 transcode and automated Content ID scan to complete.
5.  **Restrictions Audit:** Inspect the "Restrictions" column in YouTube Studio. Confirm status is "None" or "Copyright" (Standard Claim - no strikes, not blocked).
6.  **Launch:** Switch visibility from Unlisted to **Public** (or set scheduled release).
7.  **Velocity Stimulation:** Post and pin the First-Hour Engagement Comment immediately.

---

### 5.2 TikTok Platform Configuration & High-Quality Upload Protocol

*   **Account Type:** **Personal Account or Creator Account** (**STRICTLY NEVER Business Account**). Business accounts face severe music licensing locks that block access to commercial trending tracks.
*   **Allow High-Quality Uploads Toggle:**
    *   *Mandatory Action:* Must be toggled **ON** for *every single post*.
    *   *Navigation:* On final posting screen $\to$ tap **More options** $\to$ toggle **"Allow High-Quality Uploads" = ON**.
*   **Compression Bypass:** Render video at 12–15 Mbps VBR 60fps CFR MP4 to prevent server-side compression degradation.

---

### 5.3 TikTok Ghost-Linking Audio Synchronization

Allows videos to index on official trending sound discovery pages while delivering pristine, remastered live concert audio:

```
Step 1: Upload video containing remastered live concert audio (-14 LUFS, clean bass).
Step 2: Tap "Add sound" at top of edit screen; search and select official studio track.
Step 3: Tap "Volume" controls at bottom right.
Step 4: Slide "Added Sound Volume" down to 1% - 3% (never 0% to prevent indexing drops).
Step 5: Maintain "Original Sound Volume" at 100%.
Outcome: Video indexes on official song page while audience hears live concert atmosphere.
```

---

### 5.4 Caption SEO & 5–7 Hashtag Taxonomy

#### Keyword-Frontloaded Caption Template
> `[Artist Name] dropping [Track ID / Title] live at [Festival Name] [Year] 🤯 [Stage Name] was electric. #EDM #[Genre] #[Festival] #[Artist] #LiveMusic #EDMTok #Shorts`

*Example:*  
> `John Summit dropping Where You Are live at EDC Orlando 2026 🤯 Circuit Grounds was electric. #EDM #TechHouse #EDCOrlando #JohnSummit #LiveMusic #EDMTok #Shorts`

#### The 5–7 Hashtag Formula Rules
*   **2 Broad EDM Hashtags:** `#EDM`, `#Festival` (or `#LiveMusic`, `#Rave`)
*   **2 Sub-Genre Hashtags:** `#TechHouse`, `#Dubstep` (or `#Techno`, `#Trance`, `#DnB`)
*   **2 Entity / Event Hashtags:** `#[ArtistName]`, `#[FestivalName2026]`
*   **1 Community / Intent Hashtag:** `#EDMTok` (or `#UnreleasedID`, `#LaserBaptism`)

---

### 5.5 Universal 17-Keyword Spam & Phishing Comment Blocklist

To prevent ticket scammers, crypto bots, and phishing rings from polluting comment sections, copy and paste this exact comma-separated string into YouTube Studio **Blocked words** and TikTok comment filters:

```text
t.me/, whatsapp, crypto, investment, check bio, full set link, telegram, drop your track, promo on, dm to promote, click here, ticket sale, buy tickets, leak, scam, dm me, free download
```

*Ensure the **"Block links"** checkbox is enabled in YouTube Studio Community settings.*

---

### 5.6 First-Hour Community Engagement Velocity Playbook

Drop and pin one of the following structured engagement prompts immediately after publishing:

*   **Hook 1: The Track ID Crowdsource Bounty (High Comment Volume)**
    > *"This unreleased track blew our minds. Crowdsourcing the ID—who knows who produced this? 👇"*
*   **Hook 2: The Binary 1-to-10 Drop Rating Prompt (Frictionless Interaction)**
    > *"Laser and bass drop rating: 1 to 10? Drop your rating below! 🔥👇"*
*   **Hook 3: Direct Artist & Label Tagging (Industry Repost Hook)**
    > *"Filmed live at [Event]. @[ArtistHandle] dropped this at 3 AM. When is this master finally dropping?! 🔊"*

---

### 5.7 Daily Publishing Timing & Multi-Timezone Cadence

To capture peak audience scrolling windows across both European and North American time zones, publish twice daily:
*   **Post 1 (Morning Peak):** **10:00 AM EST (15:00 UTC)** — Captures European evening/transit browsing and US morning commuter traffic.
*   **Post 2 (Evening Peak):** **6:00 PM EST (23:00 UTC)** — Captures North American peak evening couch-scrolling and pre-weekend festival hype.
""")

    # ----------------------------------------------------
    # BLOCK 7: SECTION 6 (HYBRID STORAGE ARCHITECTURE)
    # ----------------------------------------------------
    out.write(r"""
---

## 6. Hybrid Storage & Asset Lifecycle Architecture

### 6.1 4-Folder Hybrid Drive Taxonomy

The workspace utilizes a unified 4-folder lifecycle architecture balancing high-end multi-tier rigor with rapid file access:

```
📁 content_creation/
├── 📂 01_RAW_INBOX (Color: Red)        # Unprocessed mobile captures organized by Event
├── 📂 02_IN_PROGRESS (Color: Orange)    # Active project workspaces, stems, intermediate renders
├── 📂 03_READY_TO_POST (Color: Green)   # Verified master MP4s with signed QC reports
└── 📂 04_ARCHIVE (Color: Gray)          # Cold compressed backups of raw assets and timelines
```

---

### 6.2 Standardized File Naming Convention

All files moving through the pipeline must strictly obey the standardized naming syntax:

$$\mathbf{YYYYMMDD\_[Event]\_[Artist]\_[TrackName-or-ID]\_V[\#]\_[Resolution].mp4}$$

*Examples:*
*   `20260821_EDCOrlando_JohnSummit_WhereYouAre_V1_1080p.mp4`
*   `20260822_LostLands_Excision_FeelSomething_V2_1080p.mp4`
*   `20260823_ClubSpace_CharlotteDeWitte_UnreleasedID_V1_1080p.mp4`

---

### 6.3 50-Item Folder Health & Auto-Partitioning Overflow Rule

*   **The Nesting Rule:** No subfolder within `01_RAW_INBOX`, `02_IN_PROGRESS`, or `03_READY_TO_POST` shall exceed **50 items**.
*   **Reasoning:** Prevents Google Drive API synchronization timeouts, IDE metadata scraping latency, and human visual browsing fatigue.
*   **Auto-Partitioning:** When item count reaches 50, the agent automatically creates a numbered overflow partition (e.g., `01_RAW_INBOX/EDC_Orlando_2026_Part02/`).

---

### 6.4 Asset Promotion & Quarantine Workflow

```
[01_RAW_INBOX] ──▶ Ingestion & Analysis ──▶ [02_IN_PROGRESS/{project_id}/]
                                                        │
                                            Automated Transcode
                                                        │
                                                        ▼
                                                [qc_validator.py]
                                                        │
                                        ┌───────────────┴───────────────┐
                                        ▼ [PASS]                        ▼ [FAIL]
                             [03_READY_TO_POST]           [02_IN_PROGRESS/Quarantine/]
                             - Master MP4                 - Diagnostic Failure Log
                             - signed qc_report.json      - Raw Intermediates Kept
                             - distribution_package.json  - Circuit Breaker Tripped
```
""")

    # ----------------------------------------------------
    # BLOCK 8: SECTION 7 (FUTURE CONTENT CONCEPTS)
    # ----------------------------------------------------
    out.write(r"""
---

## 7. Future Content Concepts & Creative Formats

To sustain long-term audience growth and prevent format fatigue over 90-day cycles, the AI Master Mind executes 8 specialized content formats:

1.  **ID Hunter Series:** Weekly top-3 countdown spotlighting the most sought-after unreleased IDs identified in live sets, complete with on-screen sleuthing notes and producer clues.
2.  **Laser Canopy ASMR:** Pure audiovisual immersion featuring synchronized stadium laser arrays and binaural spatial audio remastering with zero voiceover or invasive text.
3.  **Multi-Angle Switch:** Dynamic split-screen or rapid cut alternating between DJ booth mixer POV and front-row rail-riding crowd reactions on every beat drop.
4.  **BPM Acceleration Drop:** Dramatic tempo ramp beginning at 128 BPM tech house and accelerating dynamically into a 150+ BPM Hardstyle or 174 BPM Drum & Bass drop.
5.  **Interactive Track ID Bounty:** Mystery track clips posted with a structured community bounty prompt, rewarding the first commenter who accurately identifies the unreleased track and timestamp.
6.  **Festival Audio Remastering Hub:** Salvaging famous, historical, low-quality mobile concert clips from past years and restoring them using Demucs stem isolation and phase-aligned hybrid mastering.
7.  **1001Tracklists Webhook:** Automated API integration triggering immediate video clipping when a "Most Wanted" festival ID is officially identified or tracklisted.
8.  **Live Soundboard Hybrid Fader:** On-screen animated mixer fader visually sliding between "Board Feed" (100% clean studio) and "Crowd Mic" (100% crowd reverb), illustrating the power of the 70/30 hybrid mix.
""")

    # ----------------------------------------------------
    # BLOCK 9: SECTION 8 (TROUBLESHOOTING & EDGE CASES)
    # ----------------------------------------------------
    out.write(r"""
---

## 8. Troubleshooting, Edge Cases & Failure Recovery Playbook

### 8.1 Exhaustive Edge Cases & Concrete Remediation Matrix

| # | Edge Case / Failure Mode | Root Cause | Immediate Remediation | Automated Agent Prevention Rule |
| :--- | :--- | :--- | :--- | :--- |
| 1 | **Video Duration = 61.5s (YouTube Shorts)** | Extended outro causes video to exceed 60s with active Content ID match. | **Global Block:** YouTube blocks video worldwide. | `AutomatedQCVerifier` enforces hard duration cap: $\text{Duration} \le 59.00\text{s}$. Rejects render automatically if $>59.00\text{s}$. |
| 2 | **Commercial Audio Muted on TikTok** | Original sound containing commercial track exceeds 60 seconds. | **Audio Muted:** TikTok mutes entire video audio track. | Clamp all TikTok video renders to $15.0 - 45.0\text{s}$; enforce Ghost-Linking protocol. |
| 3 | **Ghost-Linking Fails to Index on TikTok** | Added commercial sound volume was set to 0%. | Sound discovery page fails to link video. | Maintain Added Sound Volume at strictly **$1\% \text{ to } 3\%$**; never set to 0%. |
| 4 | **Text / DJ Face Blocked by UI (YouTube)** | Critical text placed at $Y = 1600\text{px}$ (bottom 470px). | Obscured by channel title, handle, and sound marquee. | Restrict all text overlays to Universal Safe Zone ($Y: 180 - 1450\text{px}$, optimal text anchor at $Y: 340\text{px}$). |
| 5 | **Action Blocked by Right Rail (TikTok)** | Kinetic action placed at $X = 1000\text{px}$ (right 120px). | Obscured by profile avatar, Like heart, and Comment icons. | Restrict all action to Safe Area Box ($X: 40 - 960\text{px}$). |
| 6 | **115 dB Festival Bass Distortion** | Phone microphone diaphragm overloaded by stage subwoofers. | Acoustic rumble and inter-sample digital clipping. | Apply $40\text{ Hz}$ / $80\text{ Hz}$ high-pass filter + iZotope RX De-Clip + soft limiter to $-1.5\text{ dBTP}$. |
| 7 | **Severe Low-Light Sensor Noise** | Mobile camera sensor ISO spiked to 6400 in dark warehouse. | Heavy chroma/luma grain ("festival haze"). | Apply FFmpeg spatio-temporal filter (`hqdn3d=4:3:6:4.5`) or Topaz Nyx model before final transcode. |
| 8 | **TikTok Business Account Licensing Block** | Account mistakenly registered as Business. | Commercial music catalog blocked by TikTok licensing. | Account policy mandate: Set account strictly to **Personal or Creator**. |
| 9 | **Direct Upload to Public Triggers Block** | Video made public before Content ID processing finishes. | Video launches in low-res 360p and triggers instant block. | **Unlisted Pre-Flight Hold:** Stage as Unlisted for 30–60 min before setting Public. |
| 10 | **Spam Comments & Scam Ticket Phishing** | Bot rings posting Telegram links (`t.me/...`). | Phishing links mislead community. | 17-Keyword Blocklist in Studio + "Block links" checkbox intercepts URLs automatically. |
| 11 | **Loop Rhythmic Stutter** | Video trimmed on non-bar boundary (e.g., 3.5 bars). | Cadence breaks on replay, destroying hypnotic retention. | Cut on exact 4-bar or 8-bar boundaries with a $30\text{ms}$ micro-crossfade. |
| 12 | **Subfolder Exceeds 50 Items** | Uploading 100 clips into a single folder. | Google Drive sync timeouts and IDE indexing lag. | Auto-partition into sub-folders (`/Event_Part01/`, `/Event_Part02/`) at 50 items. |
| 13 | **Strobe Bitrate Starvation / Macroblocking** | High-speed stage strobes overwhelm encoder bitrate. | Heavy pixelation and blocky artifacts. | Use 12–15 Mbps VBR (up to 20 Mbps maxrate) with 60fps CFR encoding. |
| 14 | **Hybrid Audio Comb Filtering** | Studio WAV and live crowd mic misaligned by 15ms. | Acoustic phase cancellation and hollow flanging. | Cross-correlate audio waveforms to $\Delta t < 0.5\text{ms}$ before blending $70/30$. |
""")

    # ----------------------------------------------------
    # BLOCK 10: SECTION 9 (AGENT VALIDATION MATRIX)
    # ----------------------------------------------------
    out.write(r"""
---

## 9. Agent Validation Matrix & System Context Injection

### 9.1 System Context Prompt for EDM Short-Form Automation Assistant

```markdown
System Prompt for EDM Short-Form Automation Assistant:
You are the master co-pilot for the @LaserBaptism and @MusicBaptism short-form media brands. Your job is to generate on-brand captions, title structures, video editing guides, and metadata tags based on our Master Operational Blueprint.

Ensure you adhere to these core guardrails in every response:
1. Brand Boundaries:
   - "Laser Baptism" focuses on heavy stadium visuals, massive laser displays, club POVs, and unreleased IDs.
   - "Music Baptism" focuses on deep acoustic immersion, emotional vocal climaxes, and diverse dance subgenres.
2. Technical Guardrails:
   - Video length must be kept strictly under 60 seconds (target: 15–45 seconds) to avoid global Content ID blocks.
   - All visual highlights, texts, and DJ faces must reside within the 900x1160 px universal safe zone for YouTube and 920x1250 px for TikTok.
3. Audio Rule:
   - We use Phase-Aligned Hybrid Audio (mixing 70% studio track audio with 30% live crowd reverb). On TikTok, always use the Ghost-Linking Method (official track at 1-3% volume, remastered live venue sound at 100%).
```

---

### 9.2 Robust Gemini AI Studio / Gemini Advanced Adversarial Validation Audit Prompt

```markdown
You are a highly critical, elite technical architect and digital media lawyer specializing in vertical video distribution algorithms, copyright mechanics (YouTube Content ID and TikTok Sound Match), and automated AI infrastructure.

Your objective is to stress-test and validate a proposed "EDM Short-Form Content Creation Ecosystem" before it is finalized into production. Perform an exhaustive, adversarial validation. Do not take the easy path, and do not accept surface-level answers. If a technical tool integration has API limitations, rate boundaries, or operational risks, flag it. If a copyright bypass technique carries algorithmic penalties or platform policy risks, dissect it.

Analyze the proposed setup across the following four technical vectors, citing actual platform documentation, developer APIs, and industry case studies:

### Vector 1: The Spark Orchestration Engine & MCP Ingestion
- Validate the real-world execution of a Model Context Protocol (MCP) bridge connecting mobile phone video uploads directly to Google Drive/Cloud Storage. What are the best open-source MCP servers or custom Python pipelines to achieve this seamlessly?
- Assess the reliability of using Python scripts to extract raw mobile video EXIF/XMP metadata (timestamps, GPS coordinates, and camera/exposure profiles) to auto-sort footage. Does Google Drive API allow for instant automated trigger-based sorting based on these parameters without causing sync latency?
- Critique the "GPT Workspace" automation in Google Sheets fed by automated scrapers. What are the practical API limits when scraping YouTube Shorts and TikTok metrics (view counts, trending audio) without triggering bot-detection blocks? Propose a robust, lightweight scraping alternative (e.g., utilizing third-party API aggregators or scrapers).

### Vector 2: Google Flow & Blogger Publishing Automation
- Analyze Google Flow's current integration capabilities with media pipelines. How viable is it to automate visual storyboards and shot lists directly from music track tempos or artist histories?
- Stress-test the Blogger Editor automated posting workflow via Blogger API v3. What are the formatting limitations when inserting vertical video previews, search indexing structures, and rich contextual links dynamically?

### Vector 3: The Multi-Model Production Stack
- Verify the feasibility of the Librosa (RMS energy threshold >0.8) and Demucs python pipeline for automated drop detection and audio stem separation. Will processing typical crowded, distorted festival audio through Demucs yield clean music stems, or will the crowd noise bleed corrupt the separation?
- Evaluate the iZotope RX Spectral Repair and FabFilter Pro-L2 audio mastering chain. Are there open-source, CLI-based or Python-based audio processing libraries (like Pedals, Pydub, or FFmpeg filters) that can replicate this high-fidelity mastering chain programmatically to remove the need for manual DAW work?
- Assess Topaz Video AI (using Nyx or Proteus models) for processing concert footage. What are the hardware/render time bottlenecks for upscaling 1080p high-ISO mobile footage to 4K? Is a 4K upscaled file practically beneficial for YouTube Shorts/TikTok's compression algorithms, or does it get compressed back down, making the render overhead wasteful?

### Vector 4: Copyright Architecture, Platform Policies & Safe Zones
- Deconstruct the "Ghost-Linking" Protocol on TikTok (sliding added commercial sound to 1% while keeping original high-fidelity live venue audio at 100%). Does the TikTok algorithm detect this volume mitigation and issue silent shadowbans or algorithmic reach suppression for "original sound" abuse?
- Critique the 59-second Content ID threshold rule for YouTube Shorts. Detail the exact distinction between standard Content ID claims (revenue sharing/label claims) and DMCA takedowns (strikes) when publishing unreleased IDs or festival bootlegs. What is the precise risk of receiving a manual takedown strike from a artist's management team even if the clip is kept under 60 seconds?
- Review the proposed safe zone pixel configurations (YouTube Shorts universal safe zone: 900x1160 px on a 1080x1920 canvas; TikTok safe area box: 920x1250 px). Are these coordinates perfectly optimized for modern (2026) mobile interfaces, or do they conflict with newer UI overlays (like the YouTube Shorts "Remix" button position or TikTok's extended interactive caption fields)?

Provide a highly structured, objective audit report. Identify "Critical Risks", "Operational Bottlenecks", and "Optimized Alternatives". Do not make up facts; if a tool cannot do something, tell me directly and offer a proven workaround.
```
""")

print("Master Blueprint successfully generated!")


