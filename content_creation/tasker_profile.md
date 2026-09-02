# Samsung Galaxy S26 Ultra Tasker Profile & Zero-Touch Remote Trigger Specification

> **Document Type:** Mobile Hardware Integration Specification & Tasker Automation Runbook  
> **Document ID:** `TASKER-PROFILE-S26-ULTRA-001`  
> **Target Device:** Samsung Galaxy S26 Ultra (`SM-S948U` / `SM-S948B` / `SM-S9480`)  
> **Operating System:** Samsung One UI 7.0 / Android 15 & Android 16  
> **Target Framework:** Tasker v6.3.13+ (Android Automation Engine)  
> **Target Server Daemon:** FastAPI Zero-Touch Server (`remote_trigger.py` on Workstation Port 8000)  
> **Author:** Antigravity AI Media Engineering & Mobile Automation Track  
> **Date:** 2026-08-22  

---

## 1. Executive Overview

This document provides the authoritative specification for integrating the **Samsung Galaxy S26 Ultra** hardware into the autonomous AI EDM Content Creation Master Mind pipeline via **Android Tasker**. 

By deploying this Tasker profile, a videographer or creator at a live concert or music festival can tap a **1x1 Home Screen Widget** or swipe down the **One UI 7 Quick Settings Tile** to instantly dispatch a non-blocking `HTTP POST /trigger-pipeline` request to the local/remote workstation. 

### Key Integration Highlights:
1. **<50ms Tactile Feedback:** Dispatches headless HTTP request and immediately delivers dual-pulse haptic feedback upon receiving `HTTP 202 Accepted`.
2. **Zero In-Field Interruption:** Can be triggered directly from the lock screen or inside the Samsung Pro Video viewfinder without terminating camera recording or losing focus.
3. **Fail-Safe Branching:** Traps network drops, server timeouts, and pipeline mutex locks (`HTTP 409 Conflict`), providing distinct heavy warning vibrations and toast diagnostics.
4. **Knox Power Whitelisting:** Configures One UI 7 power management to prevent Android Doze from suspending background HTTP dispatches.

---

## 2. Complete Valid Tasker XML Configuration Blocks

### 2.1 Complete Importable Tasker Task XML (`Trigger_EDM_Pipeline.tsk.xml`)

Save the following XML code block as `Trigger_EDM_Pipeline.tsk.xml` on device storage (`/sdcard/Tasker/tasks/`) and import via Tasker UI:

```xml
<TaskerData sr="" dvi="1" tv="6.3.13">
	<Task sr="task1" ve="2">
		<cdate>1755840000000</cdate>
		<edate>1755840000000</edate>
		<id>1</id>
		<nme>Trigger_EDM_Pipeline</nme>
		<pri>100</pri>
		<Action sr="act0" ve="7">
			<code>547</code>
			<Str sr="arg0" ve="3">%EDM_SERVER_IP</Str>
			<Str sr="arg1" ve="3">192.168.1.100</Str>
			<Int sr="arg2" val="0"/>
			<Int sr="arg3" val="0"/>
			<Int sr="arg4" val="0"/>
			<Int sr="arg5" val="3"/>
			<Int sr="arg6" val="0"/>
			<ConditionList sr="arg7">
				<bool0>0</bool0>
				<Condition sr="c0">
					<lhs>%EDM_SERVER_IP</lhs>
					<op>12</op>
					<rhs></rhs>
				</Condition>
			</ConditionList>
		</Action>
		<Action sr="act1" ve="7">
			<code>547</code>
			<Str sr="arg0" ve="3">%EDM_SERVER_PORT</Str>
			<Str sr="arg1" ve="3">8000</Str>
			<Int sr="arg2" val="0"/>
			<Int sr="arg3" val="0"/>
			<Int sr="arg4" val="0"/>
			<Int sr="arg5" val="3"/>
			<Int sr="arg6" val="0"/>
			<ConditionList sr="arg7">
				<bool0>0</bool0>
				<Condition sr="c0">
					<lhs>%EDM_SERVER_PORT</lhs>
					<op>12</op>
					<rhs></rhs>
				</Condition>
			</ConditionList>
		</Action>
		<Action sr="act2" ve="7">
			<code>339</code>
			<Int sr="arg0" val="1"/>
			<Str sr="arg1" ve="3">http://%EDM_SERVER_IP:%EDM_SERVER_PORT/trigger-pipeline</Str>
			<Str sr="arg2" ve="3">Content-Type:application/json&#10;Accept:application/json</Str>
			<Str sr="arg3" ve="3"/>
			<Str sr="arg4" ve="3">{"source": "s26_ultra", "from_device": true, "auto_drop": true, "event": "LiveConcert", "artist": "AutoArtist", "brand": "laser_baptism"}</Str>
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
		<Action sr="act3" ve="7">
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
		<Action sr="act4" ve="7">
			<code>130</code>
			<Str sr="arg0" ve="3">0,100,100,100</Str>
			<Int sr="arg1" val="0"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
		</Action>
		<Action sr="act5" ve="7">
			<code>548</code>
			<Str sr="arg0" ve="3">🚀 EDM Pipeline Triggered (HTTP 202 Accepted)&#10;Processing S26 Ultra takes...</Str>
			<Int sr="arg1" val="1"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
			<ConditionList sr="arg4"/>
		</Action>
		<Action sr="act6" ve="7">
			<code>523</code>
			<Str sr="arg0" ve="3">EDM Master Pipeline</Str>
			<Str sr="arg1" ve="3">Ingestion &amp; Drop Detection Active (%http_data)</Str>
			<Str sr="arg10" ve="3"/>
			<Int sr="arg11" val="0"/>
			<Str sr="arg2" ve="3">mw_av_videocam</Str>
			<Int sr="arg3" val="0"/>
			<Int sr="arg4" val="0"/>
			<Int sr="arg5" val="4"/>
			<Int sr="arg6" val="0"/>
			<Int sr="arg7" val="0"/>
			<Int sr="arg8" val="0"/>
			<Str sr="arg9" ve="3"/>
		</Action>
		<Action sr="act7" ve="7">
			<code>43</code>
		</Action>
		<Action sr="act8" ve="7">
			<code>130</code>
			<Str sr="arg0" ve="3">0,500,200,500</Str>
			<Int sr="arg1" val="0"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
		</Action>
		<Action sr="act9" ve="7">
			<code>548</code>
			<Str sr="arg0" ve="3">❌ Trigger Failed! Code: %http_response_code&#10;Error: %http_error</Str>
			<Int sr="arg1" val="1"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
			<ConditionList sr="arg4"/>
		</Action>
		<Action sr="act10" ve="7">
			<code>38</code>
		</Action>
		<Img sr="icn" ve="2">
			<nme>mw_action_offline_bolt</nme>
		</Img>
	</Task>
</TaskerData>
```

---

### 2.2 Complete Importable Tasker Project XML (`EDM_Automation.prj.xml`)

Save the following XML code block as `EDM_Automation.prj.xml` on device storage (`/sdcard/Tasker/projects/`) to import the full project bundle into Tasker:

```xml
<TaskerData sr="" dvi="1" tv="6.3.13">
	<Project sr="proj0" ve="2">
		<cdate>1755840000000</cdate>
		<edate>1755840000000</edate>
		<id>EDM_Remote_Automation</id>
		<name>EDM Automation</name>
		<pids></pids>
		<tids>1</tids>
		<Img sr="icon" ve="2">
			<nme>mw_action_offline_bolt</nme>
		</Img>
	</Project>
	<Task sr="task1" ve="2">
		<cdate>1755840000000</cdate>
		<edate>1755840000000</edate>
		<id>1</id>
		<nme>Trigger_EDM_Pipeline</nme>
		<pri>100</pri>
		<Action sr="act0" ve="7">
			<code>547</code>
			<Str sr="arg0" ve="3">%EDM_SERVER_IP</Str>
			<Str sr="arg1" ve="3">192.168.1.100</Str>
			<Int sr="arg2" val="0"/>
			<Int sr="arg3" val="0"/>
			<Int sr="arg4" val="0"/>
			<Int sr="arg5" val="3"/>
			<Int sr="arg6" val="0"/>
			<ConditionList sr="arg7">
				<bool0>0</bool0>
				<Condition sr="c0">
					<lhs>%EDM_SERVER_IP</lhs>
					<op>12</op>
					<rhs></rhs>
				</Condition>
			</ConditionList>
		</Action>
		<Action sr="act1" ve="7">
			<code>547</code>
			<Str sr="arg0" ve="3">%EDM_SERVER_PORT</Str>
			<Str sr="arg1" ve="3">8000</Str>
			<Int sr="arg2" val="0"/>
			<Int sr="arg3" val="0"/>
			<Int sr="arg4" val="0"/>
			<Int sr="arg5" val="3"/>
			<Int sr="arg6" val="0"/>
			<ConditionList sr="arg7">
				<bool0>0</bool0>
				<Condition sr="c0">
					<lhs>%EDM_SERVER_PORT</lhs>
					<op>12</op>
					<rhs></rhs>
				</Condition>
			</ConditionList>
		</Action>
		<Action sr="act2" ve="7">
			<code>339</code>
			<Int sr="arg0" val="1"/>
			<Str sr="arg1" ve="3">http://%EDM_SERVER_IP:%EDM_SERVER_PORT/trigger-pipeline</Str>
			<Str sr="arg2" ve="3">Content-Type:application/json&#10;Accept:application/json</Str>
			<Str sr="arg3" ve="3"/>
			<Str sr="arg4" ve="3">{"source": "s26_ultra", "from_device": true, "auto_drop": true, "event": "LiveConcert", "artist": "AutoArtist", "brand": "laser_baptism"}</Str>
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
		<Action sr="act3" ve="7">
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
		<Action sr="act4" ve="7">
			<code>130</code>
			<Str sr="arg0" ve="3">0,100,100,100</Str>
			<Int sr="arg1" val="0"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
		</Action>
		<Action sr="act5" ve="7">
			<code>548</code>
			<Str sr="arg0" ve="3">🚀 EDM Pipeline Triggered (HTTP 202 Accepted)&#10;Processing S26 Ultra takes...</Str>
			<Int sr="arg1" val="1"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
			<ConditionList sr="arg4"/>
		</Action>
		<Action sr="act6" ve="7">
			<code>523</code>
			<Str sr="arg0" ve="3">EDM Master Pipeline</Str>
			<Str sr="arg1" ve="3">Ingestion &amp; Drop Detection Active (%http_data)</Str>
			<Str sr="arg10" ve="3"/>
			<Int sr="arg11" val="0"/>
			<Str sr="arg2" ve="3">mw_av_videocam</Str>
			<Int sr="arg3" val="0"/>
			<Int sr="arg4" val="0"/>
			<Int sr="arg5" val="4"/>
			<Int sr="arg6" val="0"/>
			<Int sr="arg7" val="0"/>
			<Int sr="arg8" val="0"/>
			<Str sr="arg9" ve="3"/>
		</Action>
		<Action sr="act7" ve="7">
			<code>43</code>
		</Action>
		<Action sr="act8" ve="7">
			<code>130</code>
			<Str sr="arg0" ve="3">0,500,200,500</Str>
			<Int sr="arg1" val="0"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
		</Action>
		<Action sr="act9" ve="7">
			<code>548</code>
			<Str sr="arg0" ve="3">❌ Trigger Failed! Code: %http_response_code&#10;Error: %http_error</Str>
			<Int sr="arg1" val="1"/>
			<Int sr="arg2" val="0"/>
			<Str sr="arg3" ve="3"/>
			<ConditionList sr="arg4"/>
		</Action>
		<Action sr="act10" ve="7">
			<code>38</code>
		</Action>
		<Img sr="icn" ve="2">
			<nme>mw_action_offline_bolt</nme>
		</Img>
	</Task>
</TaskerData>
```

---

## 3. Action Code & Argument Mapping Matrix

The Tasker action sequence is structured as follows:

| Action # | Action Code | Action Name | Parameter Values | Technical Purpose |
|---|---|---|---|---|
| **Act 0** | `547` | Variable Set | `%EDM_SERVER_IP = 192.168.1.100` (If `%EDM_SERVER_IP !Set`) | Defines fallback LAN IP for host workstation. |
| **Act 1** | `547` | Variable Set | `%EDM_SERVER_PORT = 8000` (If `%EDM_SERVER_PORT !Set`) | Defines fallback port for FastAPI daemon. |
| **Act 2** | `339` | HTTP Request | Method: `POST` (`arg0=1`), URL: `http://%EDM_SERVER_IP:%EDM_SERVER_PORT/trigger-pipeline`, Headers: `Content-Type:application/json\nAccept:application/json`, Body: `{"source": "s26_ultra", "from_device": true, "auto_drop": true, "event": "LiveConcert", "artist": "AutoArtist", "brand": "laser_baptism"}`, Timeout: `30` (`arg7=30`), Trust Cert: `1` (`arg8=1`), Continue Task After Error: `1` (`arg11=1`) | Headless HTTP client dispatching JSON trigger to FastAPI endpoint. |
| **Act 3** | `37` | If | `%http_response_code eq 202` | Evaluates HTTP status code for accepted execution. |
| **Act 4** | `130` | Vibrate Pattern | Pattern: `0,100,100,100` | Dual-pulse tactile vibration confirming server acceptance. |
| **Act 5** | `548` | Flash HUD | Text: `🚀 EDM Pipeline Triggered (HTTP 202 Accepted)\nProcessing S26 Ultra takes...` | On-screen toast HUD with active job confirmation. |
| **Act 6** | `523` | Notify | Title: `EDM Master Pipeline`, Text: `Ingestion & Drop Detection Active (%http_data)`, Icon: `mw_av_videocam`, Priority: `4` | Persistent Android notification drawer entry. |
| **Act 7** | `43` | Else | *(none)* | Error branch execution if HTTP != 202 or timeout. |
| **Act 8** | `130` | Vibrate Pattern | Pattern: `0,500,200,500` | Heavy warning vibration alerting operator of failure. |
| **Act 9** | `548` | Flash HUD | Text: `❌ Trigger Failed! Code: %http_response_code\nError: %http_error` | Diagnostic toast displaying response code and error. |
| **Act 10** | `38` | End If | *(none)* | Closes conditional execution block. |

---

## 4. FastAPI REST Endpoint Parameter Matching (`remote_trigger.py`)

The Tasker action payload precisely targets the `PipelineTriggerRequest` Pydantic model exposed by `remote_trigger.py`:

### HTTP Request Schema
- **Endpoint:** `POST /trigger-pipeline`
- **Full URL:** `http://<SERVER_IP>:<PORT>/trigger-pipeline`
- **Request Headers:**
  ```http
  Content-Type: application/json
  Accept: application/json
  ```
- **JSON Request Body:**
  ```json
  {
    "event": "LiveConcert",
    "artist": "AutoArtist",
    "track": "ID",
    "genre": "house",
    "brand": "laser_baptism",
    "tier": "pillar_a_stadium_arena",
    "from_device": true,
    "auto_drop": true,
    "drop_duration": 30.0,
    "reframe_mode": "center_crop",
    "publish_youtube": false,
    "auto_promote": false,
    "dry_run": false
  }
  ```

### HTTP Response Handling
- **HTTP 202 Accepted (<50ms):**
  ```json
  {
    "status": "accepted",
    "job_id": "job_20260822_073000_123456",
    "message": "Pipeline job accepted and launched in background",
    "command": ["python", "orchestrator.py", "pipeline", "--from-device", "--auto-drop"],
    "started_at": "2026-08-22T07:30:00.123456Z"
  }
  ```
  *Tasker Response:* Triggers **Success Branch** (Double haptic pulse `0,100,100,100` + HUD Flash + Notification).
- **HTTP 409 Conflict (Pipeline Busy):**
  ```json
  {
    "status": "conflict",
    "error": "Pipeline execution is already in progress",
    "current_job_id": "job_20260822_072800_654321"
  }
  ```
  *Tasker Response:* Triggers **Error Branch** (Heavy haptic pulse `0,500,200,500` + Toast: `❌ Trigger Failed! Code: 409`).
- **HTTP Connection Timeout / Unreachable Host:**
  *Tasker Response:* Action Code 339 populates `%http_error` (e.g. `Connection refused` or `timeout`) and executes **Error Branch**.

---

## 5. Samsung Galaxy S26 Ultra One UI 7 Step-by-Step Setup Guide

### 5.1 Manual Task Creation in Tasker UI
1. **Launch Tasker:** Open Tasker on your Samsung S26 Ultra.
2. **Create Task:**
   - Tap the **Tasks** tab -> Tap **`+`** (Bottom-right FAB).
   - Enter name: `Trigger_EDM_Pipeline` -> Tap checkmark.
3. **Add IP Fallback Variable (Action 0):**
   - Tap **`+`** -> Select **Variables** -> **Variable Set**.
   - **Name:** `%EDM_SERVER_IP` | **To:** `192.168.1.100` (Workstation LAN IP).
   - Tap **`If`** -> Condition: `%EDM_SERVER_IP` `Is Not Set` (`!Set`).
   - Tap Back.
4. **Add Port Fallback Variable (Action 1):**
   - Tap **`+`** -> Select **Variables** -> **Variable Set**.
   - **Name:** `%EDM_SERVER_PORT` | **To:** `8000`.
   - Tap **`If`** -> Condition: `%EDM_SERVER_PORT` `Is Not Set` (`!Set`).
   - Tap Back.
5. **Add HTTP Request (Action 2):**
   - Tap **`+`** -> Select **Net** -> **HTTP Request** (Code 339).
   - **Method:** `POST`
   - **URL:** `http://%EDM_SERVER_IP:%EDM_SERVER_PORT/trigger-pipeline`
   - **Headers:** `Content-Type:application/json`
   - **Body:** `{"source": "s26_ultra", "from_device": true, "auto_drop": true, "event": "LiveConcert", "artist": "AutoArtist", "brand": "laser_baptism"}`
   - **Timeout (Seconds):** `30`
   - **Trust Any Certificate:** Check `[ON]`
   - **Automatically Follow Redirects:** Check `[ON]`
   - **Continue Task After Error:** Check `[ON]` *(Crucial for error trapping)*.
   - Tap Back.
6. **Add Success Condition (Action 3):**
   - Tap **`+`** -> Select **Task** -> **If** (Code 37).
   - Condition: `%http_response_code` `Equals` (`eq`) `202`.
   - Tap Back.
7. **Add Success Haptic Vibration (Action 4):**
   - Tap **`+`** -> Select **Alert** -> **Vibrate Pattern** (Code 130).
   - **Pattern:** `0,100,100,100`
   - Tap Back.
8. **Add Success Flash Toast (Action 5):**
   - Tap **`+`** -> Select **Alert** -> **Flash** (Code 548).
   - **Text:** `🚀 EDM Pipeline Triggered (HTTP 202 Accepted)\nProcessing S26 Ultra takes...`
   - **Long:** Check `[ON]`.
   - Tap Back.
9. **Add Success Notification (Action 6):**
   - Tap **`+`** -> Select **Alert** -> **Notify** (Code 523).
   - **Title:** `EDM Master Pipeline`
   - **Text:** `Ingestion & Drop Detection Active (%http_data)`
   - **Icon:** Tap icon selector -> Choose `mw_av_videocam`.
   - **Priority:** `4` (High).
   - Tap Back.
10. **Add Else Condition (Action 7):**
    - Tap **`+`** -> Select **Task** -> **Else** (Code 43).
    - Tap Back.
11. **Add Failure Haptic Vibration (Action 8):**
    - Tap **`+`** -> Select **Alert** -> **Vibrate Pattern** (Code 130).
    - **Pattern:** `0,500,200,500`
    - Tap Back.
12. **Add Failure Flash Toast (Action 9):**
    - Tap **`+`** -> Select **Alert** -> **Flash** (Code 548).
    - **Text:** `❌ Trigger Failed! Code: %http_response_code\nError: %http_error`
    - **Long:** Check `[ON]`.
    - Tap Back.
13. **Add End If (Action 10):**
    - Tap **`+`** -> Select **Task** -> **End If** (Code 38).
    - Tap Back.
14. **Set Task Icon & Save:**
    - Tap the bottom-right icon grid -> Select `mw_action_offline_bolt`.
    - Tap Back to exit Tasker and commit changes.

---

## 6. Samsung One UI 7 1x1 Home Screen Widget Configuration

1. **Enter Launcher Edit Mode:** Long-press any empty area on your S26 Ultra home screen wallpaper.
2. **Open Widget Catalog:** Tap the **Widgets** icon at the bottom tray.
3. **Select Tasker Widget:** Scroll alphabetically to **Tasker** -> Select **Task Shortcut (1x1)** (or **Task 1x1**).
4. **Place Widget:** Drag and drop the 1x1 widget onto your home screen grid (recommended: place immediately to the right of the Samsung Pro Video / Camera icon).
5. **Bind Task:** When Tasker's Task Selection menu appears, tap **`Trigger_EDM_Pipeline`**.
6. **Set Label & Verify:** Ensure label displays `⚡ Ingest Take` (or `EDM Pipeline`).
7. **One-Tap Operation:** Tap the icon once after filming a concert drop. The phone will pulse twice and launch the pipeline in background.

---

## 7. Samsung One UI 7 Quick Settings (QS) Tile Configuration

1. **Assign Quick Settings Slot in Tasker:**
   - In Tasker, tap the 3-dots Menu (top-right) -> **Preferences**.
   - Select the **Action** tab -> Scroll down to **Quick Settings Tasks**.
   - In **Tile 1**, select `Trigger_EDM_Pipeline`.
   - Set Title: `EDM Ingest` | Subtitle: `Zero-Touch Trigger`.
   - Tap Back to save preferences.
2. **Add Tile to One UI 7 Quick Panel:**
   - Swipe down **twice** from the top of the S26 Ultra screen to expand the full Quick Settings shade.
   - Tap the **Pencil / Edit** icon in the top header -> Select **Full Edit**.
   - In the lower "Available buttons" tray, locate **Tasker - Tile 1 (`EDM Ingest`)**.
   - Drag and drop the tile into the primary top row of your active Quick Settings grid (adjacent to Wi-Fi and Flashlight).
   - Tap **Done**.
3. **In-Field Viewfinder Operation:**
   - While filming in the Samsung Camera / Pro Video app, swipe down the notification shade and tap `EDM Ingest`.
   - Ingestion is triggered over Wi-Fi 7 without terminating the camera app or leaving the festival rail.

---

## 8. Knox Battery & Power Optimization Whitelist Runbook

To prevent Samsung One UI 7 / Android 15/16 battery savers from sleeping Tasker during multi-hour concerts:

1. **Unrestricted Battery Mode:**
   - Open **Settings** -> **Apps** -> **Tasker**.
   - Tap **Battery** -> Change setting from "Optimized" to **Unrestricted**.
2. **Never Sleeping Apps Whitelist:**
   - Open **Settings** -> **Battery** -> **Background usage limits**.
   - Tap **Never sleeping apps** -> Tap **`+`** (Add) -> Check **Tasker** -> Tap **Add**.
3. **Background Mobile Data & Data Saver Exemption:**
   - Open **Settings** -> **Apps** -> **Tasker** -> **Mobile Data**.
   - Enable **Allow background data usage** and **Allow data usage while Data saver is on**.
4. **Persistent Monitoring Service:**
   - In Tasker -> **Preferences** -> **Monitor** -> Verify **Run In Foreground** is enabled (maintains continuous background socket readiness).

---

## 9. Verification & Testing Playbook

### 9.1 Local Simulation Test
1. Start the FastAPI server on workstation:
   ```bash
   python content_creation/remote_trigger.py --host 0.0.0.0 --port 8000 --dry-run
   ```
2. Test endpoint using curl or Python:
   ```bash
   curl -X POST http://localhost:8000/trigger-pipeline \
     -H "Content-Type: application/json" \
     -d "{\"event\": \"TestSet\", \"artist\": \"TestDJ\", \"auto_drop\": true, \"dry_run\": true}"
   ```
   *Expected Output:* `HTTP 202 Accepted` with JSON containing `job_id`.
3. Tap the Tasker 1x1 widget on the S26 Ultra.
4. Verify double-pulse haptic vibration occurs on phone and workstation console logs display `[POST /trigger-pipeline] Accepted job`.

### 9.2 Conflict Test (Concurrency Mutex)
1. Trigger a live long-running transcode job.
2. Tap the Tasker widget again while the first job is running.
3. Verify the phone delivers the heavy error haptic buzz (`0,500,200,500`) and displays toast `❌ Trigger Failed! Code: 409`.
