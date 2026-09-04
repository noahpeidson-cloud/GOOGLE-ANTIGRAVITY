"""Android CLI and ADB Client Automation Wrapper.
Provides robust lifecycle management, headless layout inspection (JSON & XML),
touch/swipe gestures, keystroke injection (Rule R10.2), and bounded timeout execution.
"""

import os
import re
import json
import subprocess
import logging
from typing import Optional, List, Dict, Any, Callable, Tuple
import xml.etree.ElementTree as ET

from unified_ops_hub.mobile.models import DeviceState

logger = logging.getLogger("unified_ops_hub.mobile.client")


class AndroidAutomationError(Exception):
    """Base exception for Android CLI and ADB automation failures."""
    pass


class DeviceNotFoundError(AndroidAutomationError):
    """Raised when the specified Android device serial is not found."""
    pass


class DeviceOfflineError(AndroidAutomationError):
    """Raised when an attached device is offline, unauthorized, or disconnected."""
    pass


class CommandTimeoutError(AndroidAutomationError):
    """Raised when an ADB or Android CLI command exceeds its execution timeout."""
    pass


class UIAutomatorError(AndroidAutomationError):
    """Raised when uiautomator layout dump fails or window manager is locked."""
    pass


class AndroidClient:
    """Robust client wrapper for Android CLI (`android`) and ADB (`adb`)."""

    def __init__(
        self,
        serial: Optional[str] = None,
        adb_path: str = "adb",
        android_cli_path: str = "android",
        timeout: float = 15.0,
        runner: Optional[Callable[[List[str], Optional[float]], Any]] = None,
    ) -> None:
        self.serial = serial
        self.adb_path = adb_path
        self.android_cli_path = android_cli_path
        self.timeout = timeout
        self._custom_runner = runner
        self._screen_width = 1080
        self._screen_height = 2400

    def _execute(self, cmd: List[str], timeout: Optional[float] = None) -> str:
        """Executes a command through custom test runner or real subprocess with timeout."""
        exec_timeout = timeout or self.timeout
        if self._custom_runner:
            result = self._custom_runner(cmd, timeout=exec_timeout)
            if isinstance(result, bytes):
                return result.decode("utf-8", errors="replace")
            return str(result)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=exec_timeout,
                text=False,
            )
            stdout = proc.stdout.decode("utf-8", errors="replace").strip()
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()

            combined = f"{stdout}\n{stderr}".strip()
            if "error: device not found" in combined.lower() or "device not found" in combined.lower():
                raise DeviceNotFoundError(f"Device '{self.serial}' not found: {combined}")
            if "error: device offline" in combined.lower() or "device offline" in combined.lower() or "device unauthorized" in combined.lower():
                raise DeviceOfflineError(f"Device '{self.serial}' is offline or unauthorized: {combined}")

            if proc.returncode != 0:
                logger.warning("Command %s exited with %d: %s", " ".join(cmd), proc.returncode, combined)

            return stdout

        except subprocess.TimeoutExpired as exc:
            raise CommandTimeoutError(f"Command timed out after {exec_timeout}s: {' '.join(cmd)}") from exc
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Binary '{cmd[0]}' not found on system PATH.") from exc

    def _get_adb_prefix(self) -> List[str]:
        """Builds ADB command prefix with device serial targeting."""
        cmd = [self.adb_path]
        if self.serial:
            cmd.extend(["-s", self.serial])
        return cmd

    def run_adb(self, cmd_args: List[str], timeout: Optional[float] = None) -> str:
        """Runs a targeted ADB command."""
        full_cmd = self._get_adb_prefix() + cmd_args
        return self._execute(full_cmd, timeout=timeout)

    def run_android_cli(self, cmd_args: List[str], timeout: Optional[float] = None) -> str:
        """Runs an Android CLI tool command."""
        full_cmd = [self.android_cli_path] + cmd_args
        return self._execute(full_cmd, timeout=timeout)

    def list_devices(self) -> List[DeviceState]:
        """Discovers attached hardware and virtual devices via ADB / Android CLI."""
        devices: List[DeviceState] = []
        try:
            output = self._execute([self.adb_path, "devices", "-l"], timeout=5.0)
            lines = output.strip().splitlines()
            for line in lines[1:]:  # Skip "List of devices attached"
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    serial = parts[0]
                    state_str = parts[1]
                    model = None
                    product = None
                    for p in parts[2:]:
                        if p.startswith("model:"):
                            model = p.split(":", 1)[1]
                        elif p.startswith("product:"):
                            product = p.split(":", 1)[1]
                    
                    is_emulator = serial.startswith("emulator-") or (product and "sdk" in product.lower())
                    devices.append(
                        DeviceState(
                            serial=serial,
                            status=state_str,
                            model=model,
                            product=product,
                            is_emulator=bool(is_emulator),
                        )
                    )
        except Exception as exc:
            logger.error("Failed to list devices: %s", exc)
        return devices

    def get_device_state(self) -> DeviceState:
        """Inspects current device status, screen dimensions, and foreground app."""
        devices = self.list_devices()
        current = next((d for d in devices if d.serial == self.serial), None)
        if not current:
            current = DeviceState(
                serial=self.serial or "unknown",
                status="device" if self.serial else "disconnected",
            )

        # Query screen resolution: `wm size` -> "Physical size: 1080x2400"
        try:
            wm_out = self.run_adb(["shell", "wm", "size"])
            match = re.search(r'Physical size:\s*(\d+)x(\d+)', wm_out)
            if match:
                self._screen_width = int(match.group(1))
                self._screen_height = int(match.group(2))
                current.screen_width = self._screen_width
                current.screen_height = self._screen_height
        except Exception:
            pass

        current.foreground_package = self.get_foreground_package()
        return current

    def disable_samsung_auto_blocker(self) -> bool:
        """Pre-flight disables Samsung One UI 6.0+ Auto Blocker timeout kill-switch."""
        try:
            self.run_adb([
                "shell", "settings", "put", "global",
                "rampart_auto_enabled_switch_enabled", "0"
            ])
            return True
        except (CommandTimeoutError, DeviceOfflineError, DeviceNotFoundError):
            raise
        except Exception as exc:
            logger.warning("Samsung Auto Blocker setting could not be applied: %s", exc)
            return False

    def launch_app(self, package_name: str, activity_name: Optional[str] = None) -> bool:
        """Launches an application package using monkey or am start."""
        try:
            if activity_name:
                self.run_adb(["shell", "am", "start", "-n", f"{package_name}/{activity_name}"])
            else:
                self.run_adb(["shell", "monkey", "-p", package_name, "1"])
            return True
        except (CommandTimeoutError, DeviceOfflineError, DeviceNotFoundError):
            raise
        except Exception as exc:
            logger.error("Failed to launch app %s: %s", package_name, exc)
            return False

    def open_deep_link(self, uri: str, action: str = "android.intent.action.VIEW") -> bool:
        """Opens a deep link URI directly via Android Intent."""
        try:
            self.run_adb(["shell", "am", "start", "-a", action, "-d", uri])
            return True
        except (CommandTimeoutError, DeviceOfflineError, DeviceNotFoundError):
            raise
        except Exception as exc:
            logger.error("Failed to open deep link %s: %s", uri, exc)
            return False

    def get_foreground_package(self) -> Optional[str]:
        """Detects the currently focused application package name."""
        try:
            out = self.run_adb(["shell", "dumpsys", "window"])
            match = re.search(r'mCurrentFocus=Window\{[^\}]*\s+([^\/\}\s]+)', out)
            if match:
                return match.group(1)
        except (CommandTimeoutError, DeviceOfflineError, DeviceNotFoundError):
            raise
        except Exception:
            pass
        return None

    def get_layout_tree(self, diff_only: bool = False) -> List[Dict[str, Any]]:
        """Retrieves layout elements, attempting `android layout` first with XML fallback."""
        cmd = ["layout"]
        if diff_only:
            cmd.append("--diff")
        if self.serial:
            cmd.append(f"--device={self.serial}")

        try:
            out = self.run_android_cli(cmd)
            parsed = json.loads(out)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

        # Fallback to pure ADB XML hierarchy dump
        return self._fallback_xml_layout_dump()

    def dump_ui_xml(self) -> str:
        """Executes uiautomator dump on the device and returns raw XML content."""
        self.run_adb(["shell", "uiautomator", "dump", "/data/local/tmp/dump.xml"])
        xml_content = self.run_adb(["shell", "cat", "/data/local/tmp/dump.xml"])
        return xml_content

    def _fallback_xml_layout_dump(self) -> List[Dict[str, Any]]:
        """Parses UIAutomator XML dump into normalized layout node dictionaries."""
        xml_content = self.dump_ui_xml()
        nodes: List[Dict[str, Any]] = []

        try:
            root = ET.fromstring(xml_content)
            for idx, elem in enumerate(root.iter("node")):
                bounds_str = elem.attrib.get("bounds", "[0,0][0,0]")
                text = elem.attrib.get("text", "")
                res_id = elem.attrib.get("resource-id", "")
                cls = elem.attrib.get("class", "android.view.View")
                content_desc = elem.attrib.get("content-desc", "")
                clickable = elem.attrib.get("clickable", "false") == "true"

                # Parse center coordinate
                center_str = "[0,0]"
                m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if m:
                    x1, y1, x2, y2 = map(int, m.groups())
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                    center_str = f"[{cx},{cy}]"

                nodes.append({
                    "key": 1048576 + idx,
                    "class": cls,
                    "resourceId": res_id,
                    "text": text,
                    "contentDesc": content_desc,
                    "bounds": bounds_str,
                    "center": center_str,
                    "interactions": ["clickable"] if clickable else [],
                    "state": [],
                    "off-screen": False,
                })
        except Exception as exc:
            logger.warning("XML layout fallback parsing failed: %s", exc)

        return nodes

    def tap_coordinates(self, x: int, y: int) -> bool:
        """Synthesizes a touchscreen click event at the specified pixel coordinates."""
        self.run_adb(["shell", "input", "tap", str(x), str(y)])
        return True

    def tap_element_bounds(self, bounds: str) -> bool:
        """Calculates element center coordinate from bounding box '[x1,y1][x2,y2]' and taps."""
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if not m:
            logger.error("Invalid bounds format: %s", bounds)
            return False
        x1, y1, x2, y2 = map(int, m.groups())
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return self.tap_coordinates(cx, cy)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> bool:
        """Synthesizes a continuous touch drag gesture across screen coordinates."""
        self.run_adb([
            "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(duration_ms)
        ])
        return True

    def swipe_direction(
        self,
        direction: str = "up",
        distance_ratio: float = 0.6,
        duration_ms: int = 500,
    ) -> bool:
        """Executes a directional feed swipe based on device screen dimensions."""
        mid_x = self._screen_width // 2
        mid_y = self._screen_height // 2

        if direction == "up":
            # Drag from bottom to top (moves feed forward)
            start_y = int(self._screen_height * 0.8)
            end_y = int(self._screen_height * (0.8 - distance_ratio))
            return self.swipe(mid_x, start_y, mid_x, end_y, duration_ms=duration_ms)
        elif direction == "down":
            start_y = int(self._screen_height * 0.2)
            end_y = int(self._screen_height * (0.2 + distance_ratio))
            return self.swipe(mid_x, start_y, mid_x, end_y, duration_ms=duration_ms)
        elif direction == "left":
            start_x = int(self._screen_width * 0.8)
            end_x = int(self._screen_width * (0.8 - distance_ratio))
            return self.swipe(start_x, mid_y, end_x, mid_y, duration_ms=duration_ms)
        elif direction == "right":
            start_x = int(self._screen_width * 0.2)
            end_x = int(self._screen_width * (0.2 + distance_ratio))
            return self.swipe(start_x, mid_y, end_x, mid_y, duration_ms=duration_ms)
        else:
            raise ValueError(f"Unsupported swipe direction: {direction}")

    def inject_text(self, text: str) -> bool:
        """Injects text via ADB, replacing spaces with %s and encoding symbols per Rule R10.2."""
        escaped = (
            text.replace(" ", "%s")
            .replace("$", "%24")
            .replace("&", "%26")
            .replace("#", "%23")
        )
        self.run_adb(["shell", "input", "text", escaped])
        return True

    def send_keyevent(self, keycode: int) -> bool:
        """Injects hardware keyevent (e.g. 3=Home, 4=Back, 66=Enter)."""
        self.run_adb(["shell", "input", "keyevent", str(keycode)])
        return True

    def capture_screen(self, output_path: Optional[str] = None) -> bytes:
        """Captures device display directly as a PNG byte stream."""
        if self._custom_runner:
            data = self._custom_runner(["adb", "exec-out", "screencap", "-p"])
            if isinstance(data, str):
                data = data.encode("utf-8")
        else:
            full_cmd = self._get_adb_prefix() + ["exec-out", "screencap", "-p"]
            proc = subprocess.run(full_cmd, capture_output=True, timeout=self.timeout)
            data = proc.stdout

        if output_path and data:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(data)

        return data
