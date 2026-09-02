"""
mock_device.py - Simulated Android Device & Samsung Camera Pro Video Mode

Provides a realistic in-memory Android mobile device simulation for Samsung Galaxy S26 Ultra:
- Emulates Samsung Pro Video Mode UI state machine (ISO/Shutter ribbons and sliders)
- Captures and interprets ADB shell touch inputs (`input tap X Y`, `input swipe`)
- Captures and parses Tasker broadcast intents (`am broadcast`)
- Ingests and streams synthetic preview frames from LightSimulator
- Enforces strict Airplane Mode offline isolation verification
"""

from dataclasses import dataclass, field
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from s26_controller.core.coordinates import (
    CameraParameter,
    CoordinateNormalizer,
    DisplayProfile,
    DisplayResolution,
    SamsungS26CoordinateMap,
    TapAction,
)
from s26_controller.core.dispatcher import (
    BaseDispatcher,
    CameraPreset,
    DispatchResult,
    LightingRegime,
)
from s26_controller.simulation.light_simulator import ConcertLightSimulator, ConcertScenario


@dataclass
class CapturedCommand:
    """Telemetry record for an executed ADB shell command or touch intent."""
    raw_command: str
    command_type: str  # "tap", "swipe", "broadcast", "shell"
    timestamp_ns: int
    params: Dict[str, Any] = field(default_factory=dict)
    applied_state_change: Optional[str] = None


@dataclass
class ProVideoCameraState:
    """Current exposure and UI state of the simulated Samsung Camera app."""
    iso: int = 640
    shutter_speed: str = "1/60"
    ev: str = "0.0"
    white_balance: str = "AUTO"
    focus: str = "AUTO"
    active_ribbon: Optional[CameraParameter] = None
    slider_open: bool = False
    slider_type: Optional[CameraParameter] = None
    is_recording: bool = True
    airplane_mode: bool = True
    network_requests_count: int = 0


class MockAndroidDevice:
    """
    Mock Android Device environment emulating a physical Samsung Galaxy S26 Ultra.
    Tracks Pro Video UI touch coordinates, slider positions, and verifies Airplane mode isolation.
    """

    def __init__(
        self,
        display_profile: Optional[DisplayProfile] = None,
        simulate_touch_latency_ms: float = 0.0,
        airplane_mode: bool = True,
        initial_iso: int = 640,
        initial_shutter: str = "1/60",
    ) -> None:
        self.profile = display_profile or DisplayProfile.get_default_s26_ultra_wqhd()
        self.normalizer = CoordinateNormalizer(self.profile)
        self.simulate_touch_latency_ms = float(simulate_touch_latency_ms)

        self.state = ProVideoCameraState(
            iso=initial_iso,
            shutter_speed=initial_shutter,
            airplane_mode=airplane_mode,
        )

        # Telemetry histories
        self.captured_commands: List[CapturedCommand] = []
        self.captured_taps: List[Tuple[int, int, int]] = []  # (x, y, timestamp_ns)
        self.state_history: List[Dict[str, Any]] = []

        # Optional attached frame stream
        self._simulator: Optional[ConcertLightSimulator] = None
        self._frame_generator: Optional[Any] = None

    @property
    def current_iso(self) -> int:
        return self.state.iso

    @property
    def current_shutter(self) -> str:
        return self.state.shutter_speed

    @property
    def is_airplane_mode(self) -> bool:
        return self.state.airplane_mode

    def reset(self) -> None:
        """Resets device state, telemetry, and command history."""
        self.state = ProVideoCameraState(
            iso=640,
            shutter_speed="1/60",
            airplane_mode=True,
        )
        self.captured_commands.clear()
        self.captured_taps.clear()
        self.state_history.clear()
        self._frame_generator = None

    def attach_simulator_scenario(
        self,
        scenario: Union[ConcertScenario, str] = ConcertScenario.SCENARIO_A_BLACKOUT_DROP,
        fps: float = 60.0,
        as_rgb: bool = True,
    ) -> None:
        """Attaches a ConcertLightSimulator scenario as the preview frame source."""
        self._simulator = ConcertLightSimulator(fps=fps)
        self._frame_generator = self._simulator.stream_scenario(scenario, as_rgb=as_rgb)

    def get_next_preview_frame(self) -> Tuple[np.ndarray, int]:
        """Fetches the next simulated camera preview frame from the attached stream."""
        if self._frame_generator is not None:
            try:
                return next(self._frame_generator)
            except StopIteration:
                pass

        # Fallback default 160x90 ambient frame
        now_ns = time.perf_counter_ns()
        default_frame = np.full((90, 160, 3), 45, dtype=np.uint8)
        return default_frame, now_ns

    def _find_matching_ribbon_button(self, x: int, y: int, tolerance_px: int = 120) -> Optional[CameraParameter]:
        """Checks if a tap falls within touch tolerance of a Pro parameter ribbon button."""
        for param, (norm_x, norm_y) in SamsungS26CoordinateMap.RIBBON_BUTTONS.items():
            bx, by = self.normalizer.to_screen_pixels(norm_x, norm_y)
            dist = math.hypot(x - bx, y - by)
            if dist <= tolerance_px:
                return param
        return None

    def _find_matching_iso_tick(self, x: int, y: int, tolerance_px: int = 120) -> Optional[str]:
        """Checks if a tap falls within touch tolerance of an ISO slider tick."""
        for iso_key, (norm_x, norm_y) in SamsungS26CoordinateMap.ISO_SLIDER_TICKS.items():
            tx, ty = self.normalizer.to_screen_pixels(norm_x, norm_y)
            dist = math.hypot(x - tx, y - ty)
            if dist <= tolerance_px:
                return iso_key
        return None

    def _find_matching_shutter_tick(self, x: int, y: int, tolerance_px: int = 120) -> Optional[str]:
        """Checks if a tap falls within touch tolerance of a Shutter speed slider tick."""
        for speed_key, (norm_x, norm_y) in SamsungS26CoordinateMap.SHUTTER_SLIDER_TICKS.items():
            tx, ty = self.normalizer.to_screen_pixels(norm_x, norm_y)
            dist = math.hypot(x - tx, y - ty)
            if dist <= tolerance_px:
                return speed_key
        return None

    def inject_touch_tap(self, x: int, y: int) -> Dict[str, Any]:
        """
        Simulates a physical screen tap at physical pixel coordinates (x, y) on the S26 Ultra.
        Updates Pro Video UI state accordingly.
        """
        now_ns = time.perf_counter_ns()
        self.captured_taps.append((x, y, now_ns))

        if self.simulate_touch_latency_ms > 0:
            time.sleep(self.simulate_touch_latency_ms / 1000.0)

        applied_change = None

        # Check 1: Did tap hit a ribbon button?
        ribbon_btn = self._find_matching_ribbon_button(x, y)
        if ribbon_btn is not None:
            self.state.active_ribbon = ribbon_btn
            self.state.slider_open = True
            self.state.slider_type = ribbon_btn
            applied_change = f"Opened {ribbon_btn.value} slider ribbon"

        # Check 2: If Shutter slider is open
        elif self.state.slider_type == CameraParameter.SHUTTER_SPEED:
            shutter_tick = self._find_matching_shutter_tick(x, y)
            if shutter_tick is not None:
                self.state.shutter_speed = shutter_tick
                applied_change = f"Set Shutter to {shutter_tick}"

        # Check 3: If ISO slider is open
        elif self.state.slider_type == CameraParameter.ISO:
            iso_tick = self._find_matching_iso_tick(x, y)
            if iso_tick is not None:
                if iso_tick == "AUTO":
                    applied_change = f"Set ISO to AUTO"
                else:
                    self.state.iso = int(iso_tick)
                    applied_change = f"Set ISO to {iso_tick}"

        # Check 4: Tap along slider track area when no specific slider was explicitly recorded
        elif y > self.profile.height * 0.65 and y < self.profile.height * 0.80:
            iso_tick = self._find_matching_iso_tick(x, y)
            shutter_tick = self._find_matching_shutter_tick(x, y)
            if iso_tick is not None:
                if iso_tick == "AUTO":
                    applied_change = f"Set ISO to AUTO"
                else:
                    self.state.iso = int(iso_tick)
                    applied_change = f"Set ISO to {iso_tick}"
            elif shutter_tick is not None:
                self.state.shutter_speed = shutter_tick
                applied_change = f"Set Shutter to {shutter_tick}"

        self.state_history.append({
            "timestamp_ns": now_ns,
            "iso": self.state.iso,
            "shutter": self.state.shutter_speed,
            "active_ribbon": self.state.active_ribbon.value if self.state.active_ribbon else None,
            "slider_open": self.state.slider_open,
            "applied_change": applied_change,
        })

        return {
            "success": True,
            "x": x,
            "y": y,
            "applied_change": applied_change,
            "current_iso": self.state.iso,
            "current_shutter": self.state.shutter_speed,
        }

    def execute_shell_command(self, cmd_str: str) -> str:
        """
        Interprets an ADB shell command string (e.g. 'input tap 686 1267' or 'am broadcast ...')
        and executes the corresponding simulated action.
        """
        now_ns = time.perf_counter_ns()
        clean_cmd = cmd_str.strip()

        # 1. Parse 'input tap X Y'
        tap_match = re.match(r"^input\s+tap\s+(\d+)\s+(\d+)$", clean_cmd, re.IGNORECASE)
        if tap_match:
            x_px = int(tap_match.group(1))
            y_px = int(tap_match.group(2))
            res = self.inject_touch_tap(x_px, y_px)
            self.captured_commands.append(
                CapturedCommand(
                    raw_command=clean_cmd,
                    command_type="tap",
                    timestamp_ns=now_ns,
                    params={"x": x_px, "y": y_px},
                    applied_state_change=res["applied_change"],
                )
            )
            return "OK"

        # 2. Parse 'am broadcast -a net.dinglisch.android.tasker.ACTION_TASK ...'
        if "am broadcast" in clean_cmd:
            extras: Dict[str, str] = {}
            for match in re.finditer(r'--es\s+([^\s]+)\s+"([^"]*)"', clean_cmd):
                extras[match.group(1)] = match.group(2)
            if not extras:
                # Unquoted fallback
                for match in re.finditer(r"--es\s+([^\s]+)\s+([^\s]+)", clean_cmd):
                    extras[match.group(1)] = match.group(2)

            applied_change = self._apply_tasker_extras(extras)
            self.captured_commands.append(
                CapturedCommand(
                    raw_command=clean_cmd,
                    command_type="broadcast",
                    timestamp_ns=now_ns,
                    params=extras,
                    applied_state_change=applied_change,
                )
            )
            return "Broadcast completed: result=0"

        # 3. Generic shell command
        self.captured_commands.append(
            CapturedCommand(
                raw_command=clean_cmd,
                command_type="shell",
                timestamp_ns=now_ns,
                params={},
                applied_state_change=None,
            )
        )
        return "OK"

    def _apply_tasker_extras(self, extras: Dict[str, str]) -> str:
        """Applies parameters received via Tasker broadcast extras."""
        changes = []
        if "iso" in extras:
            try:
                self.state.iso = int(extras["iso"])
                changes.append(f"ISO -> {self.state.iso}")
            except ValueError:
                pass
        if "shutter" in extras:
            self.state.shutter_speed = extras["shutter"]
            changes.append(f"Shutter -> {self.state.shutter_speed}")

        desc = ", ".join(changes) if changes else "No parameter change"
        self.state_history.append({
            "timestamp_ns": time.perf_counter_ns(),
            "iso": self.state.iso,
            "shutter": self.state.shutter_speed,
            "applied_change": f"Tasker Intent: {desc}",
        })
        return desc

    def assert_airplane_mode_compliance(self) -> None:
        """Asserts that Airplane mode was active and zero outbound network calls were attempted."""
        assert self.state.airplane_mode is True, "Device Airplane mode was disabled!"
        assert self.state.network_requests_count == 0, (
            f"Integrity Violation: {self.state.network_requests_count} network requests attempted in Airplane mode!"
        )

    def assert_iso_equals(self, expected_iso: int) -> None:
        """Asserts that the camera current ISO matches the expected setting."""
        assert self.state.iso == expected_iso, f"Expected ISO {expected_iso}, but camera is at ISO {self.state.iso}"

    def assert_shutter_equals(self, expected_shutter: str) -> None:
        """Asserts that the camera current Shutter speed matches the expected setting."""
        assert self.state.shutter_speed == expected_shutter, (
            f"Expected Shutter {expected_shutter}, but camera is at {self.state.shutter_speed}"
        )


class MockDeviceDispatcher(BaseDispatcher):
    """
    Dispatcher implementation that routes touch taps and presets directly into a MockAndroidDevice instance.
    """

    def __init__(self, device: MockAndroidDevice) -> None:
        super().__init__(device.profile)
        self.device = device

    def dispatch_tap(self, x: int, y: int, delay_after_ms: int = 0) -> bool:
        self.device.inject_touch_tap(x, y)
        if delay_after_ms > 0:
            time.sleep(delay_after_ms / 1000.0)
        return True

    def dispatch_sequence(self, actions: List[TapAction]) -> DispatchResult:
        start_ns = time.perf_counter_ns()
        for act in actions:
            self.device.inject_touch_tap(act.x_px, act.y_px)
            if act.delay_after_ms > 0:
                time.sleep(act.delay_after_ms / 1000.0)

        total_latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        return DispatchResult(
            success=True,
            actions_executed=len(actions),
            actions=actions,
            total_latency_ms=total_latency_ms,
            metadata={"mock_device": True, "device_iso": self.device.current_iso, "device_shutter": self.device.current_shutter},
        )
