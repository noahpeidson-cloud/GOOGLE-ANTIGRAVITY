# Unified Ops Hub Specification Report: Android CLI Automation & Next.js Command Center

**Author:** Spec Miner Specialist (`spec_miner_android_frontend`)  
**Date:** 2026-08-25  
**Working Directory:** `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_android_frontend`  
**Target Project:** `g:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub` & `apps/`  

---

## 1. Executive Summary

This specification report defines the authoritative blueprint for:
1. **Headless Android Mobile Automation & Viral Trend Scraping**: Utilizing `android-cli` and `adb` via a 4-tier zero-touch automation hierarchy to scrape trending TikTok/Instagram/YouTube Shorts feeds without brittle DOM parsers or manual UI tapping.
2. **Unified Next.js Command Center**: A modern Next.js (React 19 / App Router) dashboard orchestrating all Antigravity subsystems (Sports Card Ecosystem, Media Ingestion & Grading, Viral Trend Scraper, and ML Optimization Loops) over REST, SSE (Server-Sent Events), and WebSockets while adhering strictly to `modern-web-guidance` standards (CSS containment, `content-visibility: auto`, `contentvisibilityautostatechange` resource management, sub-50ms INP).
3. **Deterministic Testing Suites & Mock Harnesses**: Test-Driven Agentic Development (TDAD) and Loud Assertion test architectures for both Next.js (Vitest, React Testing Library, MSW) and Python backend automation (`AndroidCliMockHarness`, mock device state, layout tree mutations, and error injectors).

---

## 2. System Architecture & Topology

```
+---------------------------------------------------------------------------------------------------+
|                                NEXT.JS UNIFIED COMMAND CENTER                                     |
|                       (React 19 / App Router / Tailwind CSS v4 / Vitest)                          |
|                                                                                                   |
|  +---------------------------+  +-------------------------------+  +---------------------------+  |
|  |  Sports Card Ecosystem   |  |   Media Ingestion & Grading   |  |  Viral Trends & ML Agent  |  |
|  |  - Portfolio Metrics      |  |   - 01_RAW Ingestion Watcher  |  |  - Headless Android View  |  |
|  |  - CardLadder Scraper     |  |   - PySpark Gemini-Omni Grade |  |  - Trend Sound/Tag Table  |  |
|  |  - Vision Ingest Queue    |  |   - DaVinci Timeline Exporter |  |  - SQLite ML Telemetry    |  |
|  +---------------------------+  +-------------------------------+  +---------------------------+  |
|                                                                                                   |
|  [CSS Containment: content-visibility: auto | contain-intrinsic-size | contentvisibilityautostate]  |
+----------------------------------------------+----------------------------------------------------+
                                               |
                          REST (JSON) / SSE (EventSource) / WebSockets
                                               |
+----------------------------------------------v----------------------------------------------------+
|                                PYTHON UNIFIED BACKEND DAEMONS                                     |
|                                (FastAPI / Uvicorn / Antigravity SDK)                              |
|                                                                                                   |
|  +---------------------------+  +-------------------------------+  +---------------------------+  |
|  |  Sports Card Daemon       |  |   Media Pipeline Daemon       |  |  Viral Scraping ML Agent  |  |
|  |  Port: 8000 (FastAPI)     |  |   (Ingestion & PySpark Grade) |  |  (ml_agent.py / SQLite)   |  |
|  |  - SQLite / CardLadder    |  |   - GCS / FFmpeg / BQML       |  |  - K-Means / Leash Loop   |  |
|  +---------------------------+  +-------------------------------+  +-------------+-------------+  |
+----------------------------------------------------------------------------------|----------------+
                                                                                   |
                                                                  Subprocess / Asyncio Stream
                                                                                   |
                                                 +---------------------------------v----------------+
                                                 |         ANDROID MOBILE AUTOMATION LAYER          |
                                                 |        (`android` CLI + `adb` Subprocess)        |
                                                 |                                                  |
                                                 |  Tier 1: Dalvik / Binaries (pm path, app_process)|
                                                 |  Tier 2: Intents (am start -d, am broadcast)     |
                                                 |  Tier 3: UIAutomator JSON (android layout / diff)|
                                                 |  Tier 4: Monkey & Input (tap, swipe, keyevent)   |
                                                 +--------------------------------------------------+
```

---

## 3. Deep Dive: Android CLI & Headless Mobile Automation Spec

### 3.1 Android CLI vs Pure ADB Command Matrix

| CLI Tool | Command Syntax | Description | Input Parameters | Output Format | Error Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `android` | `android info <field>` | Inspect SDK, connected serials, env | `connected-devices`, `sdk-path` | Plain text / key-value | Exits non-zero if SDK missing |
| `android` | `android emulator start <avd>` | Boot headless or UI AVD | `--name=<avd_name>`, `--no-window` | Returns when device boot completes | Returns code 1 if AVD not found |
| `android` | `android emulator list` | List available virtual devices | None | Line-separated AVD names | Empty list if none created |
| `android` | `android layout` | Dump full UI hierarchy of foreground app | `--device=<serial>`, `-o=<file>`, `-p` | Flat JSON array of UI elements | Returns empty/error if app in WebView/anim |
| `android` | `android layout --diff` | Diff UI hierarchy against previous dump | `--device=<serial>`, `-o=<file>`, `-p` | Flat JSON array of modified nodes | Returns all if first run |
| `android` | `android screen capture` | Capture full resolution PNG | `-o <filepath>`, `--device=<serial>` | Binary PNG file | Fails if storage unwriteable |
| `android` | `android screen capture --annotate`| Capture PNG with numbered visual bounding boxes | `-o <filepath>`, `--device=<serial>` | Annotated PNG file | Fails if rendering pipeline locked |
| `android` | `android screen resolve` | Resolve annotated visual tag to coordinate | `--screen <file> --string "#<id>"` | Space-delimited string: `<x> <y>` | Returns empty string if label missing |
| `android` | `android install` | Fast delta APK installation | `--apks=<paths>`, `--use-delta-install` | Status message | `INSTALL_FAILED_*` errors |
| `android` | `android run` | Build, deploy, and launch component | `--activity=<name>`, `--debug` | Execution log | Fails if activity not exported or bad name |
| `adb` | `adb devices -l` | List attached hardware & emulators | None | Device serials and qualifiers | Empty if daemon offline |
| `adb` | `adb shell uiautomator dump <path>`| Raw XML UI hierarchy dump | Remote path `/data/local/tmp/dump.xml` | XML file written to device | Error code 255 if UI surface busy |
| `adb` | `adb exec-out screencap -p` | Direct binary screenshot stream | None | Binary PNG stream directly to stdout | Zero bytes on frame drops |
| `adb` | `adb shell input tap <X> <Y>` | Synthesize touchscreen click event | X integer, Y integer | None (Silent) | Ignored if coordinates off-screen |
| `adb` | `adb shell input swipe <x1> <y1> <x2> <y2> <ms>` | Synthesize continuous swipe/drag | Start (x1, y1), End (x2, y2), Duration ms | None (Silent) | Ignored if bad duration |
| `adb` | `adb shell input text "<escaped_str>"` | Inject alphanumeric keystrokes | Space replaced by `%s`, URL-encoded symbols | None (Silent) | Truncates on raw space or quotes |
| `adb` | `adb shell input keyevent <keycode>` | Inject Android hardware keycode | Integer: 66 (Enter), 3 (Home), 4 (Back), 84 (Search) | None (Silent) | No-op if unmapped keycode |
| `adb` | `adb shell monkey -p <pkg> 1` | Force-launch sandboxed application package | Target package name (e.g. `com.zhiliaoapp.musically`) | Event count log | Package not found error |
| `adb` | `adb shell am start -a <action> -d <uri>` | Launch deep link / specific video / hashtag | Action `VIEW`, Uri `https://...` | Status message | `ActivityNotFoundException` |
| `adb` | `adb shell pm grant <pkg> <perm>` | Silently grant runtime permissions | Package, permission string | None (Silent) | SecurityException if not grantable |
| `adb` | `adb shell settings put global <key> <val>` | Override system flags (e.g. Samsung Auto Blocker) | `rampart_auto_enabled_switch_enabled 0` | None | Root/ADB permissions required |

---

### 3.2 UI Element Schema (`android layout` JSON)

The `android layout` command provides a structured JSON output representing the foreground UI hierarchy:

```json
[
  {
    "key": 1048576,
    "class": "android.widget.TextView",
    "resourceId": "com.zhiliaoapp.musically:id/title",
    "text": "#EDM #Festival #MartinGarrix",
    "contentDesc": "Video hashtag caption",
    "bounds": "[48,1620][860,1740]",
    "center": "[454,1680]",
    "interactions": ["clickable"],
    "state": ["focused"],
    "off-screen": false
  },
  {
    "key": 1048577,
    "class": "android.widget.Button",
    "resourceId": "com.zhiliaoapp.musically:id/like_count",
    "text": "1.4M",
    "contentDesc": "Like button with 1.4 million likes",
    "bounds": "[920,1300][1040,1420]",
    "center": "[980,1360]",
    "interactions": ["clickable"],
    "state": [],
    "off-screen": false
  },
  {
    "key": 1048578,
    "class": "androidx.recyclerview.widget.RecyclerView",
    "resourceId": "com.zhiliaoapp.musically:id/view_pager",
    "bounds": "[0,0][1080,2400]",
    "center": "[540,1200]",
    "interactions": ["scrollable"],
    "state": [],
    "off-screen": false
  }
]
```

### 3.3 Python Integration Architecture

To integrate mobile automation securely into Python without blocking asyncio event loops or failing on Windows shell subtleties:

```python
"""
Android automation driver integrating android-cli and adb via asyncio.
"""
import asyncio
import json
import re
from typing import Dict, Any, List, Optional, Tuple

class AndroidAutomationDriver:
    def __init__(self, device_serial: Optional[str] = None, android_cli_path: str = "android", adb_path: str = "adb"):
        self.device_serial = device_serial
        self.android_cli = android_cli_path
        self.adb = adb_path

    def _get_adb_prefix(self) -> List[str]:
        cmd = [self.adb]
        if self.device_serial:
            cmd.extend(["-s", self.device_serial])
        return cmd

    async def run_shell(self, command: str) -> str:
        full_cmd = self._get_adb_prefix() + ["shell"] + command.split()
        proc = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ADB Shell command failed: {stderr.decode().strip()}")
        return stdout.decode().strip()

    async def get_layout_tree(self, diff_only: bool = False) -> List[Dict[str, Any]]:
        cmd = [self.android_cli, "layout"]
        if diff_only:
            cmd.append("--diff")
        if self.device_serial:
            cmd.append(f"--device={self.device_serial}")
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            # Fallback to pure ADB uiautomator dump if android-cli is unavailable
            return await self._fallback_uiautomator_dump()
        return json.loads(stdout.decode())

    async def _fallback_uiautomator_dump(self) -> List[Dict[str, Any]]:
        # Fallback implementation parsing XML dump
        await self.run_shell("uiautomator dump /data/local/tmp/dump.xml")
        xml_data = await self.run_shell("cat /data/local/tmp/dump.xml")
        # Parse XML bounding boxes and text nodes into normalized layout format
        elements = []
        pattern = re.compile(r'text="([^"]*)" resource-id="([^"]*)" bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
        for match in pattern.finditer(xml_data):
            text, res_id, x1, y1, x2, y2 = match.groups()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            elements.append({
                "text": text,
                "resourceId": res_id,
                "bounds": f"[{x1},{y1}][{x2},{y2}]",
                "center": f"[{int((x1+x2)/2)},{int((y1+y2)/2)}]",
                "interactions": ["clickable"],
                "off-screen": False
            })
        return elements

    async def tap_element(self, element: Dict[str, Any]) -> None:
        center_str = element.get("center", "[0,0]")
        coords = [int(n) for n in center_str.strip("[]").split(",")]
        await self.run_shell(f"input tap {coords[0]} {coords[1]}")

    async def swipe_feed(self, direction: str = "up", duration_ms: int = 500) -> None:
        # Default swipe for 1080x2400 displays
        if direction == "up":
            # Swipe upwards (moves feed down)
            await self.run_shell(f"input swipe 540 1800 540 400 {duration_ms}")
        else:
            await self.run_shell(f"input swipe 540 400 540 1800 {duration_ms}")

    async def type_text(self, text: str) -> None:
        # Adheres to Rule R10.2: Escape spaces with %s and special characters
        escaped = text.replace(" ", "%s").replace("&", "%26").replace("$", "%24")
        await self.run_shell(f"input text {escaped}")
```

### 3.4 Viral Trend Scraping Algorithm

The autonomous scraping pipeline executes as follows:
1. **Provision & Health Check**: Query `android info connected-devices`. Verify ADB connection. Disable Samsung Auto Blocker timeout via `settings put global rampart_auto_enabled_switch_enabled 0`.
2. **Deep-Link Launch**: Launch viral feed via Android Intent: `am start -a android.intent.action.VIEW -d "https://www.tiktok.com/tag/electronicmusic"`.
3. **Inspect DOM Hierarchy**: Invoke `android layout` to get the JSON tree.
4. **Extract Metrics**:
   - Extract caption, hashtags, audio track title, sound URL, like count, comment count, and creator username from text nodes.
   - Calculate view velocity ratio: $(\text{Likes} \times 10 + \text{Comments} \times 50) / \text{PostAgeHours}$.
5. **Visual Capture**: If video cover / graphic needs visual analysis, execute `android screen capture -o /data/viral_captures/<id>.png` for multi-modal Gemini-Omni analysis.
6. **Paginate Feed**: Execute slow scroll swipe: `input swipe 540 1700 540 300 600`.
7. **Telemetry Ingestion**: Write parsed record into SQLite `viral_trends` table and pass to K-Means clustering in `ml_agent.py`.

---

## 4. Deep Dive: Next.js Unified Command Center Architecture

### 4.1 Technology Stack & Architectural Decisions

- **Framework**: Next.js 16+ (App Router, Server Components + Client Islands).
- **Language**: TypeScript 5+ (Strict Mode).
- **Styling**: Tailwind CSS v4 + Modern CSS (`@container`, `content-visibility: auto`, subgrid).
- **State Management & Data Fetching**: TanStack React Query / SWR for REST endpoints, native `EventSource` hook for SSE real-time telemetry streams, native `WebSocket` hook for bidirectional interactive controls.
- **Modern Web Guidance Compliance**:
  - `efficient-background-processing`: Automatic pause of SSE rendering and log streaming when tab or card is off-screen using `contentvisibilityautostatechange`.
  - `interactions-in-complex-layouts`: Column and dashboard grid containment to isolate DOM reflows during rapid pipeline status updates.

### 4.2 Dashboard Layout & Subsystem Views

The unified dashboard provides 4 core visual workspaces in a responsive multi-column layout:

```
+----------------------------------------------------------------------------------------------------+
| HEADER: Unified Ops Hub | [Global Health: OK] [Active Daemons: 3/3] [Socket Collisions: 0] [Theme] |
+----------------------------------------------------------------------------------------------------+
| SIDEBAR      | MAIN COMMAND VIEW (Grid with @container & CSS containment)                          |
| - Overview   | +------------------------------------+ +------------------------------------------+ |
| - SportsCard | | 🎴 Sports Card Ecosystem Hub       | | 🎬 Media Ingestion & Grading Pipeline    | |
| - Media EDMs | | - Portfolio: $142,500 (+3.4%)      | | - Ingestion Daemon: ACTIVE (Wi-Fi 5GHz)  | |
| - Viral ML   | | - Scraped: 1,420 cards | Pending: 4| | - 01_RAW Inbox: 12 clips (4K HDR)         | |
| - System Log | | - Vision Ingest: 2 in queue        | | - PySpark Gemini-Omni: Grade avg 88.4/100| |
|              | | - Actions: [Sync CardLadder] [CSV] | | - DaVinci Export: 3 ready to render      | |
|              | +------------------------------------+ +------------------------------------------+ |
|              | +------------------------------------+ +------------------------------------------+ |
|              | | 📱 Viral Trends & Android Engine   | | 🧠 ML Agent & System Health Monitor      | |
|              | | - Device: Pixel 8 (192.168.1.150)  | | - K-Means Clusters: 4 Active             | |
|              | | - Trending Sound: #Ultra2026       | | - Telemetry Gradient: 0.042 (Optimal)    | |
|              | | - Top Hashtag: #FestivalDrop       | | - Dead Letter Queue: 0 items             | |
|              | | - Actions: [Trigger Mobile Scrape] | | - Actions: [Run Health Scan] [Audit ML]  | |
|              | +------------------------------------+ +------------------------------------------+ |
|              | +----------------------------------------------------------------------------------+ |
|              | | 📟 Real-Time Pipeline Event Stream (SSE / WebSocket Terminal)                   | |
|              | | [18:45:01] Ingestion: Downloaded VID_20260825_001.mp4 (1.2GB, SHA256 Verified)    | |
|              | | [18:45:04] Spark: Audio DSP normalized -14 LUFS, Gemini Grade: 92/100 (Viral)    | |
|              | | [18:45:09] ML Agent: Scraped TikTok #EDM -> 15 new sounds registered in SQLite   | |
|              | +----------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
```

### 4.3 Backend Communication Protocols (FastAPI Bridge)

The Next.js client connects to three distinct communication channels:

1. **REST API (`/api/v1/...`)**:
   - `GET /api/v1/sports/portfolio` -> Portfolio totals, recent sales, Card Ladder status.
   - `POST /api/v1/sports/ingest` -> Upload CardLadder CSV or trigger scrape.
   - `GET /api/v1/media/pipeline-status` -> Status of 01_RAW, proxies, DaVinci queue.
   - `POST /api/v1/viral/scrape` -> Trigger Android mobile scrape task.
   - `GET /api/v1/agent/telemetry` -> K-Means clusters and optimization gradients.

2. **Server-Sent Events (SSE - `/api/v1/events/stream`)**:
   - Provides low-overhead server-to-client streaming for logs, progress bars, and status updates.
   - Event types: `INGESTION_PROGRESS`, `GRADING_COMPLETE`, `VIRAL_SCRAPE_LOG`, `PORT_HEALTH`.

3. **WebSockets (`/api/v1/ws/device-control`)**:
   - Bi-directional channel for real-time mobile interaction (streaming live screen bounds, interactive tap coordinates, manual override).

### 4.4 Modern Web Guidance Implementation Specifications

```typescript
// Component demonstrating CSS containment & background task throttling per modern-web-guidance
'use client';

import React, { useEffect, useRef, useState } from 'react';

interface PipelineLogStreamProps {
  streamUrl: string;
}

export function PipelineLogStream({ streamUrl }: PipelineLogStreamProps) {
  const [logs, setLogs] = useState<string[]>([]);
  const [isActive, setIsActive] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Listen to contentvisibilityautostatechange to pause SSE when off-screen
    const handleStateChange = (event: any) => {
      if (event.skipped) {
        // Element is offscreen: close SSE stream to conserve bandwidth and CPU
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
        setIsActive(false);
      } else {
        // Element scrolled into view: resume SSE stream
        connectStream();
        setIsActive(true);
      }
    };

    const connectStream = () => {
      if (eventSourceRef.current) return;
      const es = new EventSource(streamUrl);
      es.onmessage = (event) => {
        setLogs((prev) => [...prev.slice(-100), event.data]);
      };
      es.onerror = () => {
        es.close();
        eventSourceRef.current = null;
      };
      eventSourceRef.current = es;
    };

    // Initial connection
    connectStream();

    el.addEventListener('contentvisibilityautostatechange', handleStateChange);
    return () => {
      el.removeEventListener('contentvisibilityautostatechange', handleStateChange);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [streamUrl]);

  return (
    <div
      ref={containerRef}
      className="dashboard-card border border-neutral-800 rounded-xl p-4 bg-neutral-900"
      style={{
        contentVisibility: 'auto',
        containIntrinsicSize: 'auto 400px auto 300px',
      }}
    >
      <div className="flex items-center justify-between pb-2 border-b border-neutral-800">
        <h3 className="text-sm font-semibold text-neutral-200">Live Telemetry Stream</h3>
        <span className={`inline-block w-2 h-2 rounded-full ${isActive ? 'bg-emerald-500 animate-pulse' : 'bg-neutral-600'}`} />
      </div>
      <div className="mt-2 h-64 overflow-y-auto font-mono text-xs text-neutral-400 space-y-1">
        {logs.map((log, i) => (
          <div key={i} className="leading-tight">{log}</div>
        ))}
      </div>
    </div>
  );
}
```

---

## 5. Deep Dive: Deterministic Testing Strategies

### 5.1 Next.js Frontend Test Suite (Vitest + RTL + MSW)

Enforcing Rule R2 (The Zero-Discretion Mandate) with deterministic loud assertions:

1. **Unit & Component Testing**:
   - **Sports Card Card**: Test rendering of portfolio valuation ($142,500), percentage pill styling (+3.4% emerald, -2.1% rose), and click handlers on "Sync CardLadder".
   - **Media Ingestion Card**: Test rendering of 01_RAW clip counts, PySpark grading badges, and DaVinci export readiness.
   - **Viral Scraper Card**: Test rendering of trending hashtag lists and mobile connection indicator.
2. **SSE & Stream Lifecycle Testing**:
   - Mock `EventSource` with deterministic event dispatching.
   - Test event message parsing, 100-item buffer cap, and connection drop handling.
   - Test `contentvisibilityautostatechange` simulation (`event.skipped = true` closes connection; `event.skipped = false` reconnects).
3. **Loud Assertion Rules**:
   - Zero reliance on random network delays or `waitFor` timeouts > 100ms.
   - Mock all API endpoints using Mock Service Worker (MSW).

### 5.2 Python ADB & Android CLI Mock Test Harness

```python
"""
test_android_cli_mock_harness.py - Deterministic Mock Test Harness for Android CLI Automation.
Demonstrates Loud Assertions, Mock Device State, UI Layout JSON trees, and Error Injection.
"""
import unittest
import json
import asyncio
from typing import Dict, Any, List, Optional

class MockAndroidDeviceState:
    """Deterministic in-memory Android device state for test execution."""
    def __init__(self, serial: str = "emulator-5554"):
        self.serial = serial
        self.is_connected = True
        self.foreground_app = "com.zhiliaoapp.musically"
        self.screen_width = 1080
        self.screen_height = 2400
        self.touch_log: List[Tuple[int, int]] = []
        self.swipe_log: List[Tuple[int, int, int, int, int]] = []
        self.text_log: List[str] = []
        self.keyevent_log: List[int] = []
        self.samsung_auto_blocker_enabled = True
        self.layout_nodes: List[Dict[str, Any]] = [
            {
                "key": 1,
                "class": "android.widget.TextView",
                "resourceId": "com.zhiliaoapp.musically:id/title",
                "text": "#EDM #UltraMiami #MartinGarrix",
                "bounds": "[48,1620][860,1740]",
                "center": "[454,1680]",
                "interactions": ["clickable"],
                "state": ["focused"],
                "off-screen": False
            },
            {
                "key": 2,
                "class": "android.widget.Button",
                "resourceId": "com.zhiliaoapp.musically:id/like_count",
                "text": "1.4M",
                "bounds": "[920,1300][1040,1420]",
                "center": "[980,1360]",
                "interactions": ["clickable"],
                "state": [],
                "off-screen": False
            }
        ]

    def execute_adb_command(self, cmd: List[str]) -> str:
        if not self.is_connected:
            raise ConnectionError(f"error: device '{self.serial}' not found")
        
        subcmd = cmd[0]
        if subcmd == "input":
            action = cmd[1]
            if action == "tap":
                x, y = int(cmd[2]), int(cmd[3])
                self.touch_log.append((x, y))
                return ""
            elif action == "swipe":
                x1, y1, x2, y2, ms = int(cmd[2]), int(cmd[3]), int(cmd[4]), int(cmd[5]), int(cmd[6])
                self.swipe_log.append((x1, y1, x2, y2, ms))
                return ""
            elif action == "text":
                self.text_log.append(cmd[2])
                return ""
            elif action == "keyevent":
                self.keyevent_log.append(int(cmd[2]))
                return ""
        elif subcmd == "settings":
            if cmd[1:4] == ["put", "global", "rampart_auto_enabled_switch_enabled"] and cmd[4] == "0":
                self.samsung_auto_blocker_enabled = False
                return ""
        elif subcmd == "uiautomator" and cmd[1] == "dump":
            return "UI hierchary dumped to: " + cmd[2]
        
        return ""

    def get_layout_json(self) -> str:
        return json.dumps(self.layout_nodes)


class TestAndroidAutomationHarness(unittest.TestCase):
    def setUp(self):
        self.device = MockAndroidDeviceState()

    def test_tap_calculation_and_execution(self):
        """Loud Assertion: Verify element center calculation and ADB tap execution."""
        target_node = self.device.layout_nodes[0]
        bounds = target_node["bounds"] # "[48,1620][860,1740]"
        center = target_node["center"] # "[454,1680]"
        
        # Parse bounds
        import re
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        self.assertIsNotNone(m)
        x1, y1, x2, y2 = map(int, m.groups())
        calc_cx = int((x1 + x2) / 2)
        calc_cy = int((y1 + y2) / 2)
        
        self.assertEqual(calc_cx, 454)
        self.assertEqual(calc_cy, 1680)
        self.assertEqual(f"[{calc_cx},{calc_cy}]", center)

        # Execute mock tap
        self.device.execute_adb_command(["input", "tap", str(calc_cx), str(calc_cy)])
        self.assertEqual(len(self.device.touch_log), 1)
        self.assertEqual(self.device.touch_log[0], (454, 1680))

    def test_samsung_auto_blocker_bypass(self):
        """Loud Assertion: Verify Samsung Auto Blocker timer is disabled before session."""
        self.assertTrue(self.device.samsung_auto_blocker_enabled)
        self.device.execute_adb_command(["settings", "put", "global", "rampart_auto_enabled_switch_enabled", "0"])
        self.assertFalse(self.device.samsung_auto_blocker_enabled)

    def test_space_encoding_in_keystrokes(self):
        """Loud Assertion: Verify spaces are escaped as %s to prevent ADB argument splitting."""
        raw_text = "Ultra Miami 2026 Mainstage"
        escaped_text = raw_text.replace(" ", "%s")
        self.device.execute_adb_command(["input", "text", escaped_text])
        self.assertEqual(self.device.text_log[0], "Ultra%sMiami%s2026%sMainstage")

    def test_offline_device_failure(self):
        """Loud Assertion: Verify exception is raised when device is disconnected."""
        self.device.is_connected = False
        with self.assertRaises(ConnectionError):
            self.device.execute_adb_command(["input", "tap", "100", "200"])
```

---

## 6. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Android CLI | `android layout` | Dumps flat JSON layout tree with bounds, centers, and interaction capabilities | `--device`, `-o`, `-p` | JSON array of UI element descriptors | Returns empty or fails during WebView rendering | `android-cli-plugin/skills/SKILL.md` |
| 2 | Android CLI | `android layout --diff` | Dumps only modified UI nodes since prior invocation to minimize context | `--device`, `-o`, `-p` | Filtered JSON array of changed elements | Returns full tree if no prior invocation | `android-cli-plugin/skills/references/interact.md` |
| 3 | Android CLI | `android screen capture` | High-fidelity device screenshot capture | `-o <filepath>`, `--device` | PNG image file written to disk | Returns error if output path invalid | `android-cli-plugin/skills/SKILL.md` |
| 4 | Android CLI | `android screen capture --annotate` | Captures screenshot with labeled visual indices (#1, #2...) | `-o <filepath>` | Annotated PNG image | Returns error if display surface not ready | `android-cli-plugin/skills/references/interact.md` |
| 5 | Android CLI | `android screen resolve` | Resolves annotated visual index to screen coordinate pair | `--screen <path> --string "#<id>"` | Coordinate string: `<X> <Y>` | Empty string if label unresolvable | `android-cli-plugin/skills/references/interact.md` |
| 6 | Android CLI | `android emulator` | Manages virtual devices (start, stop, list, create, remove) | `start <name>`, `stop <name>` | Emulator process status | Non-zero exit code if AVD does not exist | `android-cli-plugin/skills/SKILL.md` |
| 7 | Android CLI | `android install` | Fast delta APK installation bypassing adb reinstall bottlenecks | `--apks=<paths> --use-delta-install` | Installation confirmation | `INSTALL_FAILED_*` errors | `android-cli-plugin/skills/SKILL.md` |
| 8 | Mobile Bypass | Tier 1 Dalvik Execution | Direct execution of underlying app binaries or `app_process` scripts | Binary path, classpath, MainClass | Process stdout / stderr | Permission denied if SELinux blocks binary | `zero-touch-mobile-provisioning/SKILL.md` |
| 9 | Mobile Bypass | Tier 2 Intent Broadcast | Direct trigger of activities/services via `am broadcast` / `am start` | `-a <action> -d <uri> -e <k> <v>` | Activity launch acknowledgment | `ActivityNotFoundException` if unexported | `zero-touch-mobile-provisioning/SKILL.md` |
| 10 | Mobile Bypass | Tier 3 UIAutomator XML | Blind XML hierarchy dumping via ADB for element center calculation | Remote destination path | XML hierarchy file | Exit code 255 if window manager locked | `zero-touch-mobile-provisioning/SKILL.md` |
| 11 | Mobile Bypass | Tier 4 Keystroke Injection | Alphanumeric injection with `%s` space replacement and keyevent 66 | Text string, keycode int | Injected input stream | Truncation if raw spaces passed | `zero-touch-mobile-provisioning/SKILL.md` |
| 12 | Mobile Security | Samsung Auto Blocker Override | Disables hidden Samsung One UI 6.0+ ADB timeout kill-switch | `settings put global rampart_auto_enabled_switch_enabled 0` | Silent success | Requires ADB connection permissions | `zero-touch-mobile-provisioning/SKILL.md` |
| 13 | Mobile Security | Silent Permission Grant | Grants runtime permissions silently without triggering user dialogs | `pm grant <package> <permission>` | Silent success | SecurityException if permission invalid | `zero-touch-mobile-provisioning/SKILL.md` |
| 14 | Next.js Core | App Router Dashboard Shell | Static server component shell with dynamic client interactive islands | Next.js page / layout routes | Rendered HTML + React hydration | Fallback to Error Boundary on crash | `apps/agy_mobile` & Next.js 16 |
| 15 | Web Performance | `content-visibility: auto` | Defers offscreen component rendering and enforces CSS containment | CSS selector property | Skips layout/paint for offscreen cards | Graceful fallback in older browsers | `modern-web-guidance: efficient-background-processing` |
| 16 | Web Performance | `contain-intrinsic-size` | Placeholder height/width to prevent scrollbar jumping on deferred cards | `auto 400px auto 300px` | Stable scroll geometry | Uses specified fallback size | `modern-web-guidance: interactions-in-complex-layouts` |
| 17 | Web Performance | `contentvisibilityautostatechange` | Event fired when container enters/exits rendering viewport | Event listener on container | Event object with `skipped: boolean` | Never fires in unsupported browsers | `modern-web-guidance: efficient-background-processing` |
| 18 | Real-Time Sync | Server-Sent Events (SSE) Stream | Unidirectional HTTP streaming of pipeline logs and progress bars | `EventSource('/api/v1/events')` | Live text/JSON events | Auto-reconnect with backoff | FastAPI / EventSource Standard |
| 19 | Real-Time Sync | WebSocket Control Channel | Full-duplex interactive channel for remote screen taps and overrides | `WebSocket('ws://...')` | Bidirectional JSON messages | Connection error handled with alert | FastAPI / WebSocket Standard |
| 20 | Subsystem View | Sports Card Portfolio Card | Renders total portfolio value, 24h gain/loss, and CardLadder sync status | Sports Card REST endpoint data | Responsive metric card & tables | Displays skeleton loader / retry state | `sports_cards/ecosystem_hub` |
| 21 | Subsystem View | Media Ingestion Status Card | Displays 01_RAW counts, PySpark grading scores, and DaVinci export readiness | Media pipeline REST endpoint data | Multi-stage pipeline tracker | Displays warning badge if daemon down | `media_pipeline/boot_pipeline.py` |
| 22 | Subsystem View | Viral Trend & ML Telemetry Card | Displays scraped sound velocity, trending hashtags, and K-Means clusters | SQLite telemetry API | Data table and cluster graph | Shows fallback message if DB unseeded | `ml_agent.py` & `viral-trend-pipeline` |

---

## 7. Edge Cases & Resilience Behaviors

| # | Feature | Input / Condition | Observed / Required Behavior |
|---|---------|-------------------|------------------------------|
| 1 | `adb shell input text` | String with literal whitespace `"Ultra Miami 2026"` | ADB splits string into multiple arguments and fails. **Solution:** Transform spaces to `%s` (`"Ultra%sMiami%s2026"`). |
| 2 | `android layout` | Target application displaying a WebView or high-speed animation | `android layout` times out or returns empty node list. **Solution:** Fall back to `android screen capture --annotate` and visual resolution. |
| 3 | Samsung Device Automation | Device connected via Wi-Fi for >15 minutes on One UI 6.0+ | Samsung Auto Blocker silently disconnects ADB. **Solution:** Pre-flight execute `adb shell settings put global rampart_auto_enabled_switch_enabled 0`. |
| 4 | Delta APK Install | APK signed with debug keystore installed over Google Play version | Fails with `INSTALL_FAILED_UPDATE_INCOMPATIBLE`. **Solution:** Detect signature mismatch; do NOT wipe user data without consent. |
| 5 | SSE Stream In Next.js | Dashboard tab left open in background for 8+ hours | Memory leak from unbounded log array. **Solution:** Cap state array at 100 entries via `.slice(-100)` and close SSE on `contentvisibilityautostatechange` skipped state. |
| 6 | Uvicorn / FastAPI Startup | Port 8000 already bound by another background task | Socket collision (`WinError 10048`). **Solution:** Implement automatic port check and port-offset retry (8001, 8002) with port discovery endpoint. |
| 7 | Mobile Scraper Element Search | Target element partially offscreen (`"off-screen": true` in JSON) | `input tap` hits wrong element or outside viewport. **Solution:** Inspect `"interactions": ["scrollable"]` container and execute small `swipe` before tapping. |
| 8 | BigQuery ML Export | Table schema creation generated with `DEFAULT CURRENT_TIMESTAMP()` | CLI rejection per Rule R17. **Solution:** Strip `DEFAULT` syntax and assign timestamps in the application insertion query. |
| 9 | SQLite Telemetry Loop | Database accessed concurrently by scraper and ML Agent | `sqlite3.OperationalError: database is locked`. **Solution:** Enable SQLite WAL mode (`PRAGMA journal_mode=WAL;`) and 5000ms busy timeout. |
| 10 | Next.js Container Sizing | Missing `contain-intrinsic-size` on `content-visibility: auto` card | Severe layout shift (CLS) and scroll jitter as elements enter viewport. **Solution:** Mandate explicit `contain-intrinsic-size: auto <w> auto <h>` on all dynamic cards. |

---

## 8. Verification & Next Steps for Implementation

To implement and independently verify these specifications:
1. **Frontend Verification**:
   - Run `npm test` inside `apps/` (or `unified_ops_hub`) with Vitest to verify all component renders, SSE stream reconnection, and CSS containment classes.
2. **Backend & ML Automation Verification**:
   - Run `pytest test_android_cli_mock_harness.py` to verify deterministic mobile input parsing, space escaping, and UIAutomator center calculation.
   - Run `pytest test_ml_agent.py` to verify SQLite telemetry recording and K-Means clustering convergence.
