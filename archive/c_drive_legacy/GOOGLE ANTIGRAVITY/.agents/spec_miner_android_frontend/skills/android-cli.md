# Android CLI Specialist Skill Reference
Source: C:\Users\noahp\.gemini\config\plugins\android-cli-plugin\skills\SKILL.md

The Android CLI provides tools for SDK management, project creation, emulator control, UI layout dumps, screenshots, and visual annotations.

### Key Commands:
- `android info <field>`: Environment info (SDK, connected devices).
- `android emulator start|stop|list|create|remove`: Virtual device management.
- `android layout [-d] [-p] [-o=file] [--device=serial]`: Returns JSON layout tree of app. `--diff` returns modified elements.
- `android screen capture -o <file>`: PNG screenshot of device.
- `android screen capture --annotate -o <file>`: Annotated PNG screenshot with numbered bounding boxes.
- `android screen resolve --screen <file> --string "<label>"`: Converts labeled annotation to screen coordinates (X, Y).
- `android install [--use-delta-install] [--device=serial] --apks=<paths>`: Fast delta install of APKs.
- `android run [--debug] [--activity=name] [--device=serial] --apks=<paths>`: Launch app on device.
- `adb shell input tap <x> <y>`: Direct touch simulation.
- `adb shell input swipe <x1> <y1> <x2> <y2> <duration_ms>`: Direct swipe / scroll simulation.
- `adb shell input text "<escaped_text>"`: Keystroke injection.
