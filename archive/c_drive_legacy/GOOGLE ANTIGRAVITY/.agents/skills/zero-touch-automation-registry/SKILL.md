---
name: zero-touch-automation-registry
description: Unified SOP registry for Zero-Touch Firebase and Mobile (ADB) Provisioning. Replaces standalone fragmented SOPs.
---

# Zero-Touch Automation Registry

This unified registry contains the Standard Operating Procedures (SOPs) for zero-touch cloud and mobile provisioning.

## Table of Contents
1. [Zero-Touch Firebase Provisioning](#zero-touch-firebase-provisioning)
2. [Zero-Touch Mobile Provisioning (The "No-UI" Playbook)](#zero-touch-mobile-provisioning)

---

## 1. Zero-Touch Firebase Provisioning <a name="zero-touch-firebase-provisioning"></a>

### Objective
Never ask the user to manually click buttons in the Google Cloud or Firebase web consoles if a CLI alternative exists. 
Leverage gcloud and firebase-tools to provision backend architecture dynamically.

### 1. Database Provisioning
When a new Firebase project is created, Firestore is **not** enabled by default. 
Instead of asking the user to visit the console, run:
`gcloud firestore databases create --location=nam5 --type=firestore-native --project=<PROJECT_ID>`

### 2. Service Account Key Generation
When a backend Python daemon needs a Service Account JSON key:
Do NOT ask the user to manually click Generate New Private Key in the browser.
Instead, run:
`gcloud iam service-accounts keys create credentials.json --iam-account=<ACCOUNT_EMAIL> --project=<PROJECT_ID>`

### 3. Application Default Credentials (ADC)
Whenever possible, prioritize relying on the user's local ADC for local Python scripts instead of generating JSON files:
`gcloud auth application-default login`
This ensures zero API keys are left lingering in the local filesystem.

---

## 2. Zero-Touch Mobile Provisioning (The "No-UI" Playbook) <a name="zero-touch-mobile-provisioning"></a>

This skill enforces Rule R10.2 (The "No-UI" Reverse Engineering Mandate). When provisioning an Android device, configuring a third-party app (like Shizuku), or bypassing the Termux sandbox over ADB, the agent is strictly forbidden from asking the user to manually tap the screen. 

Instead, the agent MUST exhaust the following 4-tier automation hierarchy to bypass the UI entirely.

### Tier 1: Direct Dalvik / Binary Execution (Preferred)
Many Android apps rely on underlying binaries, shell scripts, or compiled payloads to do the actual work. You can execute these directly over `adb shell`.

#### Extracting and Executing Hidden Payloads
1. Find the exact path of the installed APK:
   ```bash
   adb shell pm path com.example.app
   ```
2. Execute the underlying binary/service directly. 
   *(Example: Bypassing the Shizuku "Start" UI button by directly starting its server payload):*
   ```bash
   adb shell /data/app/~~.../moe.shizuku.privileged.api-.../lib/arm64/libshizuku.so
   ```

#### Manually Generating Classpath Loaders (`app_process`)
If an app requires exporting a wrapper script (e.g., Shizuku's `rish`), DO NOT ask the user to tap "Export". Write the `app_process` loader directly to a shared directory.
```bash
adb shell "echo '#!/system/bin/sh' > /sdcard/loader.sh"
adb shell "echo 'app_process -Djava.class.path=/data/app/.../base.apk /system/bin com.example.MainClass \"\$@\"' >> /sdcard/loader.sh"
```

### Tier 2: Android Intents (`am start` / `am broadcast`)
If the action is exposed via an Android Intent, broadcast it directly over ADB to bypass the UI.
```bash
# Example: Triggering a Tasker profile
adb shell am broadcast -a net.dinglisch.android.tasker.ACTION_TASK -e task_name "MyTask"
```

### Tier 3: UI Automator (Blind Tapping)
If the app relies on internal UI state and cannot be bypassed via binaries/intents, use `uiautomator` to dump the layout, parse the XML for the bounds of the target button (e.g., `text="Pair"`), and tap it mathematically.
```bash
# Dump UI
adb shell uiautomator dump /data/local/tmp/window_dump.xml
adb shell cat /data/local/tmp/window_dump.xml

# Calculate center of bounds="[x1,y1][x2,y2]" and tap
adb shell input tap <x> <y>
```

### Tier 4: Keystroke Injection (Last Resort for Sandboxed Apps)
When injecting commands into a strict sandbox (like Termux) where standard `adb shell` drops you into the wrong unprivileged environment (`/system/bin/sh` instead of `usr/bin/bash`), hijack the UI via keystroke injection.

1. **Inject Files to Shared Storage (instead of typing huge commands):**
   ```bash
   adb push <local_repo> /sdcard/<repo_name>
   ```
2. **Force Launch the Sandbox App:**
   ```bash
   adb shell monkey -p com.termux 1
   ```
3. **Inject the Run Command:**
   Use `input text` (replace spaces with `%s` and symbols with hex codes like `%24` for `$`) and `keyevent 66` (ENTER).
   ```bash
   # Execute a single command to pull the script from shared storage
   adb shell input text "cp%s/sdcard/loader.sh%s%24PREFIX/bin/loader"
   adb shell input keyevent 66
   ```

### Constraints
- Never ask the user to tap "Allow" on standard permission prompts. Use `adb shell pm grant <package> <permission>`.
- Always replace spaces with `%s` in `adb shell input text` strings, or ADB will parse them as separate arguments.

### Known Environment Traps & Fixes

#### 1. The Samsung Auto Blocker Timeout
On Samsung One UI 6.0+, Auto Blocker will secretly turn itself back on and kill ADB connections after a timeout. Before deploying prolonged ADB sessions, you MUST kill the auto-enablement timer:
```bash
adb shell settings put global rampart_auto_enabled_switch_enabled 0
```

#### 2. Cryptographic Signature Collisions
If `adb install` fails with `INSTALL_FAILED_VERIFICATION_FAILURE` or `INSTALL_FAILED_UPDATE_INCOMPATIBLE`, you are mixing APKs with different cryptographic signatures (e.g., F-Droid vs Google Play vs GitHub Releases). 
- Do not blindly uninstall the user's existing app (which wipes their data). 
- Either match the distribution source or abandon the companion app deployment.
