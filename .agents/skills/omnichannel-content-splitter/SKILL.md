---
name: omnichannel-content-splitter
description: Converts raw voice memos, concert video transcripts, or brain dumps into platform-optimized content packages for YouTube Long-form, YouTube Shorts, TikTok, Instagram Reels, and Snapchat Spotlight.
license: Complete terms in LICENSE.txt
---

# Omnichannel Content & Script Splitter

## Overview
This skill acts as an automated content engine that converts unstructured concepts, concert tracklists, event recaps, or voice memos into tailored multi-platform scripts and publication packages.

## Multi-Platform Output Contracts

### 1. YouTube Long-Form Architecture (8–15 minutes)
- **Hook (0:00–0:45)**: High-stakes visual and narrative teaser.
- **Chapter Breakdown**: 4–6 distinct chapters with timestamp markers and B-roll cues.
- **Visual Callouts**: Specific on-screen text, graphics, and music track references.
- **Call-to-Action (CTA)**: Frictionless subscription or link-in-bio prompt.

### 2. YouTube Shorts / Instagram Reels Package (9:16 Vertical, 30–60s)
- **First 3-Second Visual Hook**: High-energy opening phrase and fast motion cue.
- **Pacing**: Rapid cadence, 120–150 wpm script with sound effect (SFX) cues.
- **On-Screen Captions**: Key phrases highlighted for sound-off viewers.
- **Loop Seam**: Seamlessly connects the final sentence back to the opening hook.

### 3. TikTok Narrative Reel (15–45s)
- **Relatability Angle**: Insider perspective, behind-the-scenes music production insight.
- **Fast Cuts**: Scene transitions every 2–4 seconds.
- **Trending Audio Placement**: Recommended sound style and hashtag taxonomy.

### 4. Snapchat Spotlight / Behind-The-Scenes (4-Part Story)
- **Snap 1**: The immediate moment / raw concert visual.
- **Snap 2**: Quick commentary / technical insight.
- **Snap 3**: Climax / the drop.
- **Snap 4**: Final verdict and link sticker.

## Usage
1. **Provide Source Context**: Supply a raw voice memo transcript, video outline, or markdown scratchpad file.
2. **Specify Output Directory**: Target `content_creation/02_IN_PROGRESS/{project_name}_scripts.md`.
3. **Execute Splitter**: The skill parses key narrative beats and outputs platform-tailored scripts with explicit timings, B-roll callouts, and audio loudness parameters (-14 LUFS).

## Examples
- **Example 1: Festival Breakdown**: Ingest a 5-minute festival voice memo; generate an 8-minute YouTube long-form outline and two 30-second TikTok clips with seamless loop hooks.
- **Example 2: Concert Footage**: Ingest live set recordings; produce timestamped story beats for Snapchat Spotlight and Instagram Reels.