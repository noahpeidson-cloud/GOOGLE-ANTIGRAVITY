---
name: davinci-resolve-automation
description: DaVinci Resolve Studio automation skill. Manages timeline creation, frame-accurate drop alignment, marker insertion, and render queue execution via DaVinci's Python scripting API (fusionscript).
license: Complete terms in LICENSE.txt
---

# DaVinci Resolve Studio Automation

## Overview
This skill automates DaVinci Resolve Studio workflows via its native Python API (`fusionscript`). It enables automated media importing, timeline generation with 9:16 vertical framing, beat-marker placement, and render queue management.

## Environment & API Prerequisites
- DaVinci Resolve Studio must be running with external scripting enabled (`Preferences > System > General > External scripting using: Local`).
- The DaVinci Resolve Python module must be importable:
  ```python
  import sys
  sys.path.append(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules")
  import DaVinciResolveScript as dvr_script
  ```

---

## Standard Automation Workflows

### 1. Initialize Resolve Connection & Project
```python
import DaVinciResolveScript as dvr_script

resolve = dvr_script.scriptapp("Resolve")
if not resolve:
    raise ConnectionError("DaVinci Resolve Studio is not running or scripting is disabled.")

project_manager = resolve.GetProjectManager()
project = project_manager.GetCurrentProject()
media_pool = project.GetMediaPool()
```

### 2. Configure 9:16 Vertical Timeline
```python
# Set timeline settings to 1080x1920 portrait
project.SetSetting("timelineResolutionWidth", "1080")
project.SetSetting("timelineResolutionHeight", "1920")
project.SetSetting("timelineFrameRate", "60")

root_folder = media_pool.GetRootFolder()
clips = root_folder.GetClipList()

# Create timeline from imported clips
timeline = media_pool.CreateTimelineFromClips("EDM_Shorts_Master", clips)
```

### 3. Place Markers at EDM Beat Drops
```python
# Add markers at specific frames for EDM drop visual effects
# Timeline.AddMarker(frameId, color, name, note, duration)
drop_frame = 360  # e.g., 6 seconds at 60fps
timeline.AddMarker(drop_frame, "Cyan", "Main Drop", "Bass drop visual punch-in", 1)
```

### 4. Trigger Render Queue Export
```python
project.SetRenderSettings({
    "SelectAllFrames": True,
    "TargetDir": r"D:\GOOGLE ANTIGRAVITY\content_creation\03_READY_TO_POST",
    "CustomName": "EDM_Reel_Master",
    "FormatWidth": 1080,
    "FormatHeight": 1920
})
project.AddRenderJob()
project.StartRendering()
```

---

## Natural Language Invocations
- *"Import this clip into DaVinci Resolve and create a 9:16 timeline"*
- *"Place markers on the audio drops in Resolve"*
- *"Add the active timeline to the DaVinci render queue and start export"*
- *"Check DaVinci Resolve scripting connection"*
