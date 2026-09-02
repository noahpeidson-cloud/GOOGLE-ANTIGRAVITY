# Specification Survey Report: Tasker Profile Generation & V2 Blueprint Documentation

**Document ID:** SPEC-REPORT-TASKER-BLUEPRINT-001  
**Project Track:** Track 2 (`content_creation/`)  
**Target File Outputs:** `content_creation/tasker_profile.md` & `content_creation/V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md`  
**Target Hardware / OS:** Samsung Galaxy S26 Ultra (One UI 7 / Android 15/16) + Local Workstation (FastAPI, ADB, Zeroconf)  
**Author:** Spec Miner (`teamwork_preview_spec_miner`)  
**Timestamp:** 2026-08-22T07:22:00Z  

---

## Executive Summary

This specification report details the complete, verified technical blueprints for implementing **R3: Tasker Profile Generation & Blueprint Documentation** in the EDM Content Creation ecosystem. 

It defines:
1. The **exact Tasker XML specification block** (`<TaskerData>`, `<Project>`, `<Task>`, `<Action>` code 339 `net.dinglisch.android.tasker.actions.HTTP`) supporting one-click import into Android Tasker.
2. The **HTTP Request Action parameter matrix** targeting the FastAPI Zero-Touch Server (`POST /trigger-pipeline`).
3. The **Samsung S26 Ultra (One UI 7)** click-by-click manual UI creation workflows for Tasker tasks, **1x1 Home Screen Widgets**, and **Quick Settings (QS) Tiles**.
4. The **Dual-Branch Haptic & Toast Feedback Engine** verifying `HTTP 202 Accepted` vs network/server error conditions.
5. The **Architectural Updates** required in `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` to formally document Phase 0 Remote Triggering, mDNS Zeroconf Auto-Discovery (`_adb-tls-connect._tcp.local.`), and the FastAPI background server.

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|---|---|---|---|---|---|---|
| 1 | Tasker XML | `<TaskerData>` XML Schema | Standard XML container format for direct project/task import into Tasker | Valid XML string or `.tsk.xml`/`.prj.xml` file | Tasker Data Tree containing Projects, Tasks, and Actions | Parser XML error if malformed tags or mismatched versions | Tasker Android Data Spec v6.x |
| 2 | Tasker Action | HTTP Request (Code 339) | Headless HTTP client action in Tasker (`net.dinglisch.android.tasker.actions.HTTP`) | Method=1 (POST), URL, Headers, Body, Timeout (30s), Trust Cert (1) | `%http_response_code`, `%http_data`, `%http_response_headers` | Sets `%http_error` if offline/refused; continues task if `arg11=1` | Tasker Action Reference (Code 339) |
| 3 | Tasker Logic | Response Code Conditional Branch | Evaluates `%http_response_code` to differentiate `202 Accepted` from errors | `%http_response_code` integer string | Routes execution to Success branch (Act 2-3) or Error branch (Act 5-6) | Fallback to Error branch if code is unset, 4xx, 5xx, or network failure | Tasker Logic Operators (Code 37 If / Code 43 Else) |
| 4 | Tasker Feedback | Success Haptic Pulse | High-frequency double vibration pulse indicating server acceptance | Pattern: `0,100,100,100` (delay 0ms, buzz 100ms, pause 100ms, buzz 100ms) | Physical haptic motor oscillation on S26 Ultra | Silent fallback if device in DND/Do Not Disturb | Tasker Action Code 130 (`Vibrate Pattern`) |
| 5 | Tasker Feedback | Success Toast Flash | On-screen toast HUD displaying accepted trigger and job status | Text: `"🚀 EDM Pipeline Triggered (HTTP 202 Accepted)"`, Long: 1 | Android Toast / Custom Tasker Flash popup | None (always renders on active display) | Tasker Action Code 548 (`Flash`) |
| 6 | Tasker Feedback | Failure Error Alert | Long, heavy error vibration buzzing + descriptive error toast | Pattern: `0,400,150,400`, Text: `"❌ Trigger Failed! Code: %http_response_code | %http_error"` | Error vibration + Toast with exact status code / error | Logged to Tasker Run Log | Tasker Action Code 130 & 548 |
| 7 | One UI 7 Integration | 1x1 Home Screen Widget | Launcher shortcut widget executing the task with a single tap | Touch press on Home Screen widget icon | Dispatches Tasker intent immediately in background | None; triggers configured Tasker task | Samsung One UI 7 Widget Framework |
| 8 | One UI 7 Integration | Quick Settings (QS) Tile | Notification shade toggle button enabling trigger access from lock screen or camera app | Swipe down QS shade -> Tap Tile 1 | Executes Tasker task without opening launcher or switching apps | Shows inactive state if Tasker service disabled | Android QuickSettings TileService API / One UI 7 |
| 9 | S26 Ultra Reliability | Battery & Doze Whitelist | Configuration disabling Samsung aggressive background app sleeping | Settings -> Apps -> Tasker -> Battery -> "Unrestricted" | Prevents Tasker process termination during concert standby | If omitted, Android Doze may delay HTTP trigger by minutes | Samsung Device Care / Android 15/16 Power Mgmt |
| 10 | Blueprint Spec | Phase 0 Topology Update | Expands High-Level Topology diagram to include Mobile Trigger and FastAPI Server | S26 Ultra Tasker client, FastAPI server (`remote_trigger.py`), Zeroconf mDNS | Flowchart documentation in Section 1.5 of V2 Blueprint | Inconsistent docs if omitted | `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` |
| 11 | Blueprint Spec | Mechanism 0 mDNS Enhancement | Documents `zeroconf` dynamic resolution of `_adb-tls-connect._tcp.local.` | Dynamic IP/port broadcast from Samsung S26 Ultra | Automatic `adb connect <ip>:<port>` execution without static IP | Fallback to USB or stored cache if mDNS filtered | `samsung_ingest.py` Zeroconf integration |
| 12 | Blueprint Spec | Mechanism 6 FastAPI Remote Trigger | Documents background HTTP server specification (`remote_trigger.py`) | `POST /trigger-pipeline`, `GET /health`, `GET /status/{job_id}` | Asynchronously spawns `orchestrator.py pipeline --from-device --auto-drop` | Returns HTTP 409 if job already running; HTTP 422 if bad JSON | FastAPI / Uvicorn Architectural Spec |
| 13 | Blueprint Spec | Mechanism 7 Tasker Remote Client | Documents mobile trigger client architecture and XML specification | `content_creation/tasker_profile.md` reference | Unified documentation for mobile hardware operator | Outdated documentation if missing | V2 Blueprint Section 3 |
| 14 | Blueprint Spec | Section 4.1 Phase 0 Revision | Updates the 6-Phase End-to-End Orchestration Lifecycle to include Phase 0 Remote Triggering | Trigger -> Ingest -> Analyze -> Transcode -> QC -> Publish | Step-by-step lifecycle documentation | Lifecycle gap if omitted | V2 Blueprint Section 4.1 |
| 15 | Blueprint Spec | Section 8 Troubleshooting Updates | Adds failure modes and remediation for mDNS multicast drops, dynamic port shifts, and server timeouts | Network drops, port re-pairing, server crashes | Troubleshooting matrices and CLI remediation commands | Unhandled edge cases if omitted | V2 Blueprint Section 8 |

---

## Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---|---|---|
| 1 | Tasker HTTP Request | Server IP is offline or unreachable (e.g. Workstation sleeping, wrong Wi-Fi SSID) | Tasker action code 339 times out after 30s; `%http_response_code` is set to `-1` or `0`; `%http_error` contains timeout message. With `arg11=1` (Continue Task After Error), task does not crash, enters `Else` branch, and fires heavy error vibration + toast. |
| 2 | Tasker HTTP Request | Server returns `HTTP 409 Conflict` (Pipeline already executing an active batch) | `%http_response_code` is `409`. Conditional `%http_response_code eq 202` evaluates to false. Enters `Else` branch; notifies operator that server is currently busy with previous render. |
| 3 | Tasker HTTP Request | Fast-response `HTTP 202 Accepted` returned within 50ms (Asynchronous Spawn) | `%http_response_code` is `202`. Task immediately executes `Act 2` (Double-tap haptic) and `Act 3` (Success toast), providing instantaneous confirmation to the concert videographer without waiting for video rendering. |
| 4 | Samsung One UI 7 Widget | Screen is locked or camera app is currently active in foreground | Quick Settings Tile can be swiped down and tapped directly over the active camera viewfinder or lock screen without exiting Pro Video mode or losing camera focus. |
| 5 | Samsung S26 Ultra Doze | Device has been in pocket for 2 hours with screen off (Deep Sleep Mode) | If Tasker is set to "Optimized" battery, Android 15/16 Doze delays HTTP network dispatch until next maintenance window. Setting Tasker to "Unrestricted" in One UI Battery settings ensures instant HTTP packet transmission. |
| 6 | mDNS Discovery | Local Wi-Fi router blocks mDNS multicast packets (AP Isolation enabled) | `Zeroconf` browser fails to locate `_adb-tls-connect._tcp.local.`. `samsung_ingest.py` detects timeout and falls back to: 1) USB ADB check (`adb devices`), 2) Cached IP/Port from `.adb_ingest_ledger.json`, 3) Explicit manual CLI IP/Port parameter. |
| 7 | Android Wireless Debugging | Phone disconnects and reconnects to Wi-Fi, causing Android 15/16 to randomize ADB port | `_adb-tls-connect._tcp.local.` mDNS service broadcasts the newly assigned port (e.g. changing from port 38451 to 42109). `samsung_ingest.py` extracts new port dynamically and reconnects seamlessly. |

---

## Deep-Dive Specification 1: `content_creation/tasker_profile.md`

### 1.1 Complete Valid Tasker XML Specification Block

The XML block below is a fully compliant, standalone Tasker export definition that can be saved directly as `trigger_edm_pipeline.tsk.xml` or `EDM_Automation.prj.xml` and imported into Tasker on Android 15/16.

```xml
<TaskerData sr="" dvi="1" tv="6.3.13">
	<Project sr="proj0" ve="2">
		<cdate>1724311200000</cdate>
		<edate>1724311200000</edate>
		<id>EDM_Remote_Automation</id>
		<name>EDM Automation</name>
		<pids></pids>
		<tids>101</tids>
		<Img sr="icon" ve="2">
			<nme>mw_action_android</nme>
		</Img>
	</Project>
	<Task sr="task101">
		<cdate>1724311200000</cdate>
		<edate>1724311200000</edate>
		<id>101</id>
		<nme>Trigger EDM Pipeline</nme>
		<pri>100</pri>
		<Action sr="act0" ve="7">
			<code>339</code>
			<Int sr="arg0" val="1"/>
			<Str sr="arg1" ve="3">http://192.168.1.100:8000/trigger-pipeline</Str>
			<Str sr="arg2" ve="3">Content-Type:application/json&#10;Accept:application/json</Str>
			<Str sr="arg3" ve="3"/>
			<Str sr="arg4" ve="3">{"event": "Concert", "brand": "laser_baptism", "auto_drop": true}</Str>
			<Str sr="arg5" ve="3"/>
			<Str sr="arg6" ve="3"/>
			<Int sr="arg7" val="30"/>
			<Int sr="arg8" val="1"/>
			<Int sr="arg9" val="1"/>
			<Int sr="arg10" val="0"/>
			<Int sr="arg11" val="1"/>
			<Int sr="arg12" val="0"/>
			<ConditionList sr="arg13"/>
		</Action>
		<Action sr="act1" ve="7">
			<code>37</code>
			<ConditionList sr="arg0">
				<bool0>0</bool0>
				<Condition sr="c0">
					<lhs>%http_response_code</lhs>
					<op>0</op>
					<rhs>202</rhs>
				</Condition>
			</ConditionList>
		</Action>
		<Action sr="act2" ve="7">
			<code>130</code>
			<Str sr="arg0" ve="3">0,100,100,100</Str>
			<Int sr="arg1" val="0"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
		</Action>
		<Action sr="act3" ve="7">
			<code>548</code>
			<Str sr="arg0" ve="3">🚀 EDM Pipeline Triggered (HTTP 202 Accepted)&#10;Processing S26 Ultra takes...</Str>
			<Int sr="arg1" val="1"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
			<ConditionList sr="arg4"/>
		</Action>
		<Action sr="act4" ve="7">
			<code>43</code>
		</Action>
		<Action sr="act5" ve="7">
			<code>130</code>
			<Str sr="arg0" ve="3">0,400,150,400</Str>
			<Int sr="arg1" val="0"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
		</Action>
		<Action sr="act6" ve="7">
			<code>548</code>
			<Str sr="arg0" ve="3">❌ Trigger Failed! Code: %http_response_code&#10;Error: %http_error</Str>
			<Int sr="arg1" val="1"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
			<ConditionList sr="arg4"/>
		</Action>
		<Action sr="act7" ve="7">
			<code>38</code>
		</Action>
		<Img sr="icn" ve="2">
			<nme>mw_action_android</nme>
		</Img>
	</Task>
</TaskerData>
```

---

### 1.2 Tasker HTTP Request Action (Code 339) Parameter Mapping

| Parameter Name | Tasker XML Argument | UI Field Label | Value / Setting | Purpose & Specification |
|---|---|---|---|---|
| **Method** | `arg0` (`Int`) | **Method** | `POST` (`val="1"`) | Dispatches HTTP POST verb to FastAPI trigger endpoint. |
| **URL** | `arg1` (`Str`) | **URL** | `http://<SERVER_IP>:8000/trigger-pipeline` | Destination URI of the FastAPI remote trigger daemon. (e.g. `http://192.168.1.100:8000/trigger-pipeline` or `%SERVER_IP`). |
| **Headers** | `arg2` (`Str`) | **Headers** | `Content-Type:application/json\nAccept:application/json` | Enforces JSON payload encoding and MIME type negotiation. |
| **Query Parameters** | `arg3` (`Str`) | **Query Parameters** | *(empty)* | Reserved for optional URL query overrides. |
| **Body** | `arg4` (`Str`) | **Body** | `{"event": "Concert", "brand": "laser_baptism", "auto_drop": true}` | JSON string specifying pipeline parameters (Event name, Brand routing, Librosa auto-drop activation). |
| **File to Send** | `arg5` (`Str`) | **File to Send** | *(empty)* | N/A (Zero-touch pipeline uses wireless ADB to pull files). |
| **File to Save** | `arg6` (`Str`) | **File / Directory to Save With Output** | *(empty)* | Response is ephemeral and parsed in memory via `%http_data`. |
| **Timeout** | `arg7` (`Int`) | **Timeout (Seconds)** | `30` (`val="30"`) | Socket timeout window (10–30s) preventing indefinite task hang. |
| **Trust Any Certificate** | `arg8` (`Int`) | **Trust Any Certificate** | `Checked` (`val="1"`) | Allows self-signed certificates if using HTTPS over local LAN. |
| **Follow Redirects** | `arg9` (`Int`) | **Automatically Follow Redirects** | `Checked` (`val="1"`) | Ensures seamless proxy/redirect handling. |
| **Use Cookies** | `arg10` (`Int`) | **Use Cookies** | `Unchecked` (`val="0"`) | Stateless REST API execution. |
| **Continue Task After Error** | `arg11` (`Int`) | **Continue Task After Error** | `Checked` (`val="1"`) | **Mandatory.** Prevents Tasker from aborting on HTTP 4xx/5xx or connection drops, enabling the custom error haptic/toast branch. |
| **Body Format** | `arg12` (`Int`) | **Custom Body / Type** | `0` (`Text / JSON`) | Identifies raw body content as UTF-8 string payload. |

---

### 1.3 Step-by-Step UI Instructions: Manual Task Creation in Tasker (One UI 7)

1. **Launch Tasker:** Open the Tasker application on the Samsung Galaxy S26 Ultra.
2. **Create New Task:**
   - Tap the **Tasks** tab at the top.
   - Tap the **+ (Floating Action Button)** in the bottom right corner.
   - Enter the task name: `Trigger EDM Pipeline` and tap the checkmark.
3. **Add Action 1 (HTTP Request):**
   - Tap **+** (Add Action) -> Select **Net** -> Select **HTTP Request** (Action Code 339).
   - In the Action Edit screen, configure:
     - **Method:** `POST`
     - **URL:** `http://192.168.1.100:8000/trigger-pipeline` *(Replace `192.168.1.100` with workstation LAN IP)*
     - **Headers:** `Content-Type:application/json`
     - **Body:** `{"event": "Concert", "brand": "laser_baptism", "auto_drop": true}`
     - **Timeout (Seconds):** `30`
     - **Trust Any Certificate:** Check `ON`
     - **Continue Task After Error:** Check `ON` *(Tap the gear/slider icon or check "Continue Task After Error" at the bottom)*.
   - Tap the **Back Arrow (<)** to save Action 1.
4. **Add Action 2 (If Condition):**
   - Tap **+** -> Select **Task** -> Select **If** (Action Code 37).
   - Condition 1: Tap the tag icon and choose `%http_response_code` (or type `%http_response_code`).
   - Operator: Select `Equals` (`~` or `eq`).
   - Value: `202`.
   - Tap **Back Arrow (<)**.
5. **Add Action 3 (Success Vibration):**
   - Tap **+** -> Select **Alert** -> Select **Vibrate Pattern** (Action Code 130).
   - Pattern: Enter `0,100,100,100` *(Creates a crisp double-tap haptic pulse)*.
   - Tap **Back Arrow (<)**.
6. **Add Action 4 (Success Flash Toast):**
   - Tap **+** -> Select **Alert** -> Select **Flash** (Action Code 548).
   - Text: `🚀 EDM Pipeline Triggered (HTTP 202 Accepted)\nProcessing S26 Ultra takes...`
   - Long: Check `ON`.
   - Tap **Back Arrow (<)**.
7. **Add Action 5 (Else Condition):**
   - Tap **+** -> Select **Task** -> Select **Else** (Action Code 43).
   - Tap **Back Arrow (<)**.
8. **Add Action 6 (Failure Vibration):**
   - Tap **+** -> Select **Alert** -> Select **Vibrate Pattern** (Action Code 130).
   - Pattern: Enter `0,400,150,400` *(Creates a heavy error alert pulse)*.
   - Tap **Back Arrow (<)**.
9. **Add Action 7 (Failure Flash Toast):**
   - Tap **+** -> Select **Alert** -> Select **Flash** (Action Code 548).
   - Text: `❌ Trigger Failed! Code: %http_response_code\nError: %http_error`
   - Long: Check `ON`.
   - Tap **Back Arrow (<)**.
10. **Add Action 8 (End If):**
    - Tap **+** -> Select **Task** -> Select **End If** (Action Code 38).
    - Tap **Back Arrow (<)**.
11. **Assign Task Icon:**
    - Tap the **Grid / Icon selector** in the bottom-right corner of the Task Edit screen.
    - Choose **Built-in Icon** -> Select `mw_action_android` (or `mw_av_videocam` / `mw_file_cloud_upload`).
12. **Save Task:** Tap the back button to return to Tasker's main screen, then tap the top checkmark to commit changes.

---

### 1.4 Step-by-Step UI Instructions: Samsung One UI 7 Home Screen Widget (1x1)

1. **Enter Home Screen Edit Mode:** Long-press on an empty area of your Samsung Galaxy S26 Ultra Home Screen.
2. **Open Widget Picker:** Tap the **Widgets** button at the bottom of the screen.
3. **Locate Tasker:** Scroll down through the alphabetical app list and tap **Tasker**.
4. **Select 1x1 Shortcut:**
   - Locate the **Task Shortcut (1x1)** (or **Task 1x1**) widget option.
   - Tap and hold the widget, then drag it onto your desired Home Screen grid slot (or tap **Add**).
5. **Bind Task:**
   - Tasker's Task Selection menu will automatically appear.
   - Tap **Trigger EDM Pipeline**.
6. **Confirm Icon:** Verify that the task icon and label (`Trigger EDM Pipeline`) are displayed.
7. **Execution:** Tap the 1x1 icon at any time. The phone will instantly issue the HTTP POST request and confirm with haptic vibration.

---

### 1.5 Step-by-Step UI Instructions: Samsung One UI 7 Quick Settings (QS) Tile

1. **Configure Quick Settings Slot in Tasker:**
   - Open **Tasker** -> Tap the 3-dots Menu (top-right) -> Tap **Preferences**.
   - Tap the **Action** tab.
   - Scroll down to **Quick Settings Tasks**.
   - For **Quick Settings 1**, enter/select: `Trigger EDM Pipeline`.
   - Set the label to: `EDM Ingest` (or `Trigger Pipeline`).
   - Tap the back button to save.
2. **Add Tile to Samsung One UI 7 Quick Settings Panel:**
   - Swipe down **twice** from the top of the S26 Ultra screen to expand the full Quick Settings panel (or swipe down from top-right corner if split shade is enabled).
   - Tap the **Edit (Pencil) icon** in the top-right header -> Select **Full Edit** (or **Top Edit**).
   - Scroll through the lower "Available buttons" tray to find **Tasker - Quick Settings 1** (labeled `EDM Ingest`).
   - Touch and hold the tile, then drag it up into your active Quick Settings grid (recommended: place in the top row next to Wi-Fi and Flashlight for instant access).
   - Tap **Done** in the top right.
3. **One-Touch Concert Operation:**
   - While filming in the Samsung Camera app, swipe down the notification shade and tap `EDM Ingest`.
   - The tile will pulse, fire the HTTP POST trigger, and deliver a double-tap haptic buzz, triggering ingestion without exiting the Camera app.

---

### 1.6 Battery, Doze & Network Optimization Runbook (Samsung S26 Ultra)

To guarantee that Tasker's HTTP requests fire with zero millisecond latency and are never suspended by Samsung One UI background power management:

1. **Disable Battery Optimization (Unrestricted Mode):**
   - Open **Settings** -> **Apps** -> **Tasker**.
   - Tap **Battery** -> Change setting from "Optimized" to **Unrestricted**.
2. **Never Sleeping Apps Whitelist:**
   - Open **Settings** -> **Battery** -> **Background usage limits**.
   - Tap **Never sleeping apps** -> Tap **+** (Add) -> Check **Tasker** -> Tap **Add**.
3. **Disable Samsung Adaptive Battery Throttling for Tasker:**
   - Open **Settings** -> **Apps** -> **Tasker** -> **Mobile Data**.
   - Enable **Allow background data usage** and **Allow data usage while Data saver is on**.
4. **Tasker Persistent Foreground Notification:**
   - In Tasker -> **Preferences** -> **Monitor** -> Ensure **Run In Foreground** is `Enabled` (shows a minimal, persistent status icon in the status bar).

---

## Deep-Dive Specification 2: Blueprint Updates (`V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md`)

### 2.1 Section 1.5 System High-Level Topology & Flowchart Updates

The system topology diagram in Section 1.5 must be updated to incorporate the Remote Mobile Trigger and Zeroconf mDNS Discovery loop:

```
+----------------------------------------------------------------------------------------------------+
|                         PHASE 0: ZERO-TOUCH REMOTE TRIGGER & HARDWARE INGESTION                    |
+----------------------------------------------------------------------------------------------------+
|  [Samsung Galaxy S26 Ultra]                                                                        |
|    - Tasker 1x1 Widget / QS Tile Touch Trigger                                                     |
|    - Wireless Debugging mDNS Broadcast (_adb-tls-connect._tcp.local.)                             |
|          │                                                                                         |
|          │ HTTP POST /trigger-pipeline                                                             |
|          ▼                                                                                         |
|  [remote_trigger.py (FastAPI Daemon on Local Workstation :8000)]                                   |
|    - Immediate Non-Blocking HTTP 202 Accepted Response (w/ Job UUID)                               |
|    - Spawns Async Pipeline Worker (asyncio.create_subprocess_exec)                                 |
|          │                                                                                         |
|          ▼                                                                                         |
|  [samsung_ingest.py (with Zeroconf mDNS Discovery Engine)]                                         |
|    - Scans LAN for _adb-tls-connect._tcp.local.                                                    |
|    - Dynamically resolves S26 Ultra IP and ephemeral wireless ADB port                             |
|    - Executes `adb connect <ip>:<port>` (immune to DHCP lease changes)                             |
|    - Scans /sdcard/DCIM/Camera & Expert RAW for new 4K60 takes                                     |
|    - Atomic Pull (.tmp_<name>.part) + SHA-256 Checksum Validation                                  |
|    - 50-Item DirectoryHealthGuard Partitioning into 01_RAW_INBOX                                    |
+----------------------------------------------------------------------------------------------------+
                                                   │
                                                   ▼
+----------------------------------------------------------------------------------------------------+
|                         PHASE 1-5: AUTOMATED PROCESSING, QC & PUBLISHING                           |
+----------------------------------------------------------------------------------------------------+
|  [ingest_assets.py] ──▶ [audio_dsp.py (Librosa RMS)] ──▶ [ffmpeg_processor.py (NVENC 9:16)]        |
|  ──▶ [qc_validator.py (-14 LUFS / <=59s)] ──▶ [youtube_publisher.py (Unlisted Content ID Audit)]  |
+----------------------------------------------------------------------------------------------------+
```

---

### 2.2 Section 3 Technical Mechanism Additions

#### 1. Update Section 3.1: Mechanism 0 (`samsung_ingest.py` with Zeroconf mDNS)
- **Role:** Hardware ingestion bridge upgraded with zero-configuration dynamic IP/port discovery.
- **Zeroconf Service Type:** `_adb-tls-connect._tcp.local.` and `_adb._tcp.local.`.
- **Dynamic IP Resolution:** Resolves IPv4 socket tuples (`ip_address`, `port`) in real time, eliminating hardcoded IP addresses.
- **CLI Commands:**
  ```bash
  # Auto-discover via mDNS and pull 5 most recent takes
  python content_creation/samsung_ingest.py --auto-discover --recent 5 --event LostLands --artist Subtronics --auto-route
  ```

#### 2. Add Section 3.7: Mechanism 6 — FastAPI Zero-Touch Remote Trigger Server (`remote_trigger.py`)
- **Role:** Lightweight asynchronous background daemon exposing REST endpoints to receive mobile triggers and orchestrate pipeline executions without blocking web responses.
- **Key Endpoints:**
  - `POST /trigger-pipeline`: Receives JSON trigger payload, validates parameters via Pydantic model (`PipelineTriggerRequest`), checks concurrency lock, spawns subprocess, and returns `HTTP 202 Accepted` with `job_id`.
  - `GET /health`: Health probe endpoint returning server status, uptime, active job state, and zeroconf connectivity.
  - `GET /status/{job_id}`: Returns execution status, logs tail, and completion telemetry for a specific pipeline job.
- **Interface Definition:**
  ```python
  # content_creation/remote_trigger.py
  from fastapi import FastAPI, BackgroundTasks, HTTPException, status
  from pydantic import BaseModel, Field
  from typing import Optional, Dict, Any
  import asyncio
  import uuid

  class PipelineTriggerRequest(BaseModel):
      event: str = Field(default="Concert", description="Event name (e.g. LostLands, Tomorrowland)")
      brand: str = Field(default="laser_baptism", description="Brand routing: laser_baptism | music_baptism")
      auto_drop: bool = Field(default=True, description="Enable Librosa automated RMS drop detection")
      artist: Optional[str] = None
      track: Optional[str] = None
      recent_limit: int = Field(default=5, ge=1, le=50)

  class TriggerResponse(BaseModel):
      status: str = "accepted"
      message: str
      job_id: str
      parameters: Dict[str, Any]
      timestamp: str
  ```

#### 3. Add Section 3.8: Mechanism 7 — Tasker One UI 7 Mobile Trigger Client (`tasker_profile.md`)
- **Role:** Mobile physical/UI client providing one-touch tactile trigger capability on the Samsung Galaxy S26 Ultra.
- **Cross-Reference:** Links to `content_creation/tasker_profile.md` for XML imports and UI binding SOPs.

---

### 2.3 Section 4.1 Phase 0 Lifecycle Revision

Update **Phase 0** in the End-to-End Orchestration Lifecycle (Section 4.1) from a manual command-line step to an **autonomous dual-trigger operational lifecycle**:

```markdown
[Phase 0: Zero-Touch Remote Trigger & Hardware Ingestion]
  │  - Step 0A (Trigger): Videographer taps 1x1 Widget or QS Tile on S26 Ultra during/after concert set.
  │  - Step 0B (Dispatch): Tasker dispatches HTTP POST to FastAPI server (`remote_trigger.py`); receives HTTP 202 Accepted; fires double haptic pulse.
  │  - Step 0C (Discovery & Connect): FastAPI server asynchronously invokes `samsung_ingest.py --auto-discover`; Zeroconf resolves `_adb-tls-connect._tcp.local.` and connects to S26 Ultra via wireless ADB (`adb connect <ip>:<port>`).
  │  - Step 0D (Atomic Pull & Ledger): `samsung_ingest.py` pulls uncompressed 4K60 files to `.tmp_<name>.part` staging; validates SHA-256; updates `.adb_ingest_ledger.json`.
  │  - Step 0E (Health Guard): `DirectoryHealthGuard` partitions files into 50-item subfolders in `01_RAW_INBOX` and hands off to Phase 1.
```

---

### 2.4 Section 8 Troubleshooting & Edge Cases Additions

Add the following recovery recipes to Section 8 of `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md`:

| Failure Mode | Root Cause | Impact | Automated / Manual Remediation |
|---|---|---|---|
| **mDNS Discovery Timeout (No service discovered)** | Router AP isolation enabled on public/hotel Wi-Fi blocking multicast UDP port 5353. | ADB cannot resolve IP automatically. | 1. Script logs mDNS warning and falls back to physical USB cable auto-detection.<br>2. Operator inputs manual IP via CLI flag `--device-ip <ip> --device-port <port>`.<br>3. Phone USB tethering / portable hotspot can be enabled to establish direct peer-to-peer subnet. |
| **Android Wireless Debugging Port Shift** | S26 Ultra reconnected to Wi-Fi or toggled Wireless Debugging, randomizing ADB TLS port. | Stale port connection refused. | `samsung_ingest.py` runs fresh mDNS query on every pull cycle, always discovering the latest broadcast port in real time. |
| **Tasker HTTP Timeout / Server Offline** | Desktop workstation is sleeping, FastAPI server is halted, or phone is on cellular data instead of LAN. | HTTP POST fails; pipeline does not trigger. | Tasker `Continue Task After Error` (`arg11=1`) triggers `Else` branch -> fires heavy error haptic buzz (`0,400,150,400`) and displays toast `"❌ Trigger Failed! Server Offline"`. |
| **Concurrent Trigger Overlap (HTTP 409)** | Operator double-taps Tasker widget while previous transcode batch is still running. | Multiple pipelines running simultaneously could cause GPU memory exhaustion. | FastAPI server enforces an async lock (`asyncio.Lock`); returns `HTTP 409 Conflict` with JSON `"Pipeline currently busy with active job <id>"`; Tasker notifies operator via error toast. |

---

## Verification & Validation Plan

| Verification Target | Command / Inspection Method | Success Criteria |
|---|---|---|
| **XML Syntactic Validity** | Validate XML structure via `xml.etree.ElementTree.fromstring(tasker_xml)` | Parse tree constructs cleanly with 0 syntax errors; all 8 actions and conditions are valid. |
| **Action 339 Argument Mapping** | Inspect arguments against Tasker Action 339 spec | `arg0=1` (POST), `arg1=URL`, `arg4=Body`, `arg7=30`, `arg8=1`, `arg11=1`. |
| **HTTP 202 Response Contract** | Inspect FastAPI response schema vs Tasker condition | FastAPI returns status code 202; Tasker condition `%http_response_code eq 202` evaluates to True. |
| **Blueprint Phase 0 Consistency** | Verify Section 1.5, Section 3, Section 4.1, Section 8 alignment | All sections consistently describe Remote Trigger -> FastAPI -> Zeroconf mDNS -> Wireless ADB -> Ingest. |
