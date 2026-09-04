# Zero-Touch Mobile Provisioning Skill Reference
Source: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\zero-touch-mobile-provisioning\SKILL.md

Enforces Rule R10.2 (The No-UI Mandate). Eliminates manual screen tapping via a 4-tier automation hierarchy:

### Tier 1: Direct Dalvik / Binary Execution (Preferred)
- `adb shell pm path <package>`
- `adb shell <path_to_binary_or_so>`
- `app_process -Djava.class.path=<apk> /system/bin <MainClass> "$@"`

### Tier 2: Android Intents
- `adb shell am broadcast -a <action> -e <key> <value>`
- `adb shell am start -n <package>/<activity> -d <uri>`

### Tier 3: UI Automator (Blind Tapping & XML Inspection)
- `adb shell uiautomator dump /data/local/tmp/window_dump.xml`
- Parse XML for element `bounds="[x1,y1][x2,y2]"` -> calculate center `(x1+x2)/2, (y1+y2)/2` -> `adb shell input tap <cx> <cy>`.

### Tier 4: Keystroke Injection & Monkey Launch (Sandboxed Apps)
- `adb push <local_file> /sdcard/<path>`
- `adb shell monkey -p <package> 1`
- `adb shell input text "<escaped_text>"` (replace spaces with `%s`, special chars with URL encoding)
- `adb shell input keyevent 66` (Enter / Action)

### Critical Constraints & Fixes:
- Auto-grant permissions: `adb shell pm grant <package> <permission>`
- Samsung Auto Blocker bypass: `adb shell settings put global rampart_auto_enabled_switch_enabled 0`
- Handle signature collisions gracefully.
