---
name: social-deployment-agent
description: "Deploys generated image assets (Facebook Covers, YouTube Thumbnails) securely using ADB and YouTube APIs, executing headlessly via Antigravity SDK and exporting telemetry to SQLite."
---

# Social Deployment Agent

## Purpose
This skill codifies the autonomous deployment phase of the Music Baptism pipeline. Because headless browser automation for Facebook is easily detected and banned, this workflow uses the `android` CLI (ADB) to physically push and simulate posting on an Android emulator.

## Execution Requirements
1. **Dependencies**: Requires `google-antigravity` and `adb` to be in the PATH.
2. **Assets Location**: All resized final assets MUST be located in `g:\My Drive\GOOGLE ANTIGRAVITY\content_creation\baptism_working_order\staged_assets\`.
3. **Metadata**: A valid `social_manifest.json` must be present.
4. **Telemetry**: The agent MUST run via the Antigravity Python SDK and use the `@hooks.on_turn_end` decorator to log success to `booth_telemetry.db`. This satisfies the `agent-ml-optimization-loop` requirement.

## Usage
To execute the deployment, run the python daemon:
```powershell
python "g:\My Drive\GOOGLE ANTIGRAVITY\deployment_agent.py"
```

## Anti-Ban Architecture
- **Facebook**: Deploys via ADB push to the SD card, triggering the `android.intent.action.SEND` intent targeting `com.facebook.katana`.
- **YouTube**: Deploys via standard Google API Python client (requires valid `token.json`).
