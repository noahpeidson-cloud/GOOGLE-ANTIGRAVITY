---
name: omnichannel-media-pipeline
description: >-
  End-to-end autonomous media ingestion and distribution pipeline. Orchestrates pulling media from Android devices, processing via DaVinci/Gemini, and publishing via Chrome DevTools.
---

# Omnichannel Media Pipeline

## Overview
This skill orchestrates the end-to-end "Sticky 5" EDM Short-Form workflow. It pulls 4K festival footage from a connected Android device, processes it using DaVinci Resolve and Gemini for frame-accurate algorithmic trimming, updates the local SQLite manifest, and publishes the final render to YouTube Shorts and Snapchat Spotlight.

## Dependencies
This skill relies on the following installed skills:
- **`android-cli`**: For fetching media via `adb pull` from the mobile device.
- **`google-antigravity-sdk` & `antigravity-guide`**: For spawning multi-agent orchestration pipelines.
- **`chrome-devtools`**: For web automation and publishing.
- **`ml-best-practices`**: For analytical review of performance data.
- **`accidental-data-loss-prevention`**: To prevent destructive operations on the `media_manifest.sqlite` database.

## Workflow

### 1. Ingestion (The Android Bridge)
- Use the `android-cli` to connect to the physical device.
- Execute `adb shell ls /sdcard/DCIM/Camera/*.mp4` to locate unprocessed media.
- Run `adb pull` to move the files into your local ingestion directory.
- *Guardrail Check*: Ensure no local data is overwritten during the pull.

### 2. Multi-Agent Orchestration (Processing & Distribution)
Instead of launching a single monolithic agent, we now use the **Adversarial Director** pattern via `multi_agent_orchestrator.py`.
- Run `python d:\GOOGLE ANTIGRAVITY\content_creation\multi_agent_orchestrator.py`
- The Root Agent will automatically spawn three subagents:
  1. **editor_agent**: Runs `davinci_integration.py` to create the edits.
  2. **producer_agent**: Audits the resulting SQLite manifest and logs. If the "Sticky 5" EDM drops are misaligned, this agent fails the pipeline and prevents publishing.
  3. **publisher_agent**: Once the producer approves, this agent initializes `chrome-devtools` to upload and publish the video to YouTube/Snapchat.
- *Guardrail Check*: When updating the `media_manifest.sqlite`, you MUST invoke `accidental-data-loss-prevention` before running any `DROP`, `DELETE`, or `TRUNCATE` SQL commands.

## Common Mistakes
- **Failing to wake the device**: Android Wi-Fi debugging frequently sleeps. You must ping the device before concluding it is offline.
- **Ignoring DaVinci State**: DaVinci Resolve MUST be open with external scripting enabled before step 2 runs, otherwise it will instantly crash.
- **Dropping the DB**: Never clear the SQLite manifest without explicit approval.
