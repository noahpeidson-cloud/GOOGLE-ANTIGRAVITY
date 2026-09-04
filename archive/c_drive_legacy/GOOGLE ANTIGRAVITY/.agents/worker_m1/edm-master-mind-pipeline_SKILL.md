---
name: edm-master-mind-pipeline
description: >-
  Executes the ultimate zero-touch EDM video pipeline. Orchestrates ADB Wi-Fi ingestion, FastAPI PWA dashboard serving, FFmpeg proxy generation, and DaVinci Resolve Python API timeline construction.
---

# EDM Master Mind Pipeline

## Overview
This skill orchestrates the entire workflow from the Samsung S26 Ultra to DaVinci Resolve. It acts as the user's Assistant Editor.

## Dependencies
- `android-cli` (For ADB ingestion management)
- `modern-web-guidance` (For building PWA Web UI dashboards)

## Workflow Steps

### 1. Ingestion (Zero-Touch)
- Execute `adb pull` exclusively targeting `/sdcard/DCIM/EDM_Drops`.
- Do not download files that already exist in the local manifest.

### 2. Proxy Generation (FFmpeg)
- For every 4K HDR H.265 file, immediately generate a lightweight 720p proxy and a `.wav` file.
- Move 4K raw files to `01_RAW/`.

### 3. PWA Web Dashboard
- Serve `static/index.html` via FastAPI. 
- Use modern View Transitions and Glassmorphism.
- The UI displays the 720p proxy and allows the user to manually adjust the AI-detected trim points.

### 4. DaVinci Resolve Handoff
- Upon Web UI approval, use the DaVinci Resolve Python API to create a new project.
- Import the 4K raw files, slice them precisely based on the Web UI timestamps, and place them on the timeline.
- Await the user to open Resolve for final color grading.
