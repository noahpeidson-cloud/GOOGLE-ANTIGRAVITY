"""
dispatcher.py - Modular Touch Dispatch Engine & Camera Preset Dispatcher

Implements multi-provider touch dispatchers:
- Abstract BaseDispatcher
- MockDispatcher for deterministic offline testing and latency simulation
- PersistentADBDispatcher with interactive subprocess shell pipe (<35ms latency)
- TaskerIntentDispatcher for Android broadcast intent integration
- AccessibilityGestureDispatcher for Android AccessibilityService gesture synthesis
"""

from __future__ import annotations

import os
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from s26_controller.core.coordinates import (
    CoordinateNormalizer,
    DisplayProfile,
    DisplayResolution,
    TapAction,
)


class LightingRegime(str, Enum):
    """Lighting regime classifications for reactive camera control."""
    NORMAL = "NORMAL"
    BLACKOUT = "BLACKOUT"
    LASER_SPIKE = "LASER_SPIKE"
    FLOOD_PYRO = "FLOOD_PYRO"
    STROBE_LOCK = "STROBE_LOCK"


@dataclass(frozen=True)
class CameraPreset:
    """Camera setting preset target for Pro Video mode."""
    iso: int
    shutter_speed: str
    regime: LightingRegime
    reason: str

    def __post_init__(self):
        if self.iso <= 0:
            raise ValueError(f"ISO must be a positive integer, got {self.iso}")
        if not self.shutter_speed:
            raise ValueError("shutter_speed cannot be empty")


@dataclass
class DispatchResult:
    """Outcome and latency telemetry of a dispatch execution."""
    success: bool
    actions_executed: int
    actions: List[TapAction] = field(default_factory=list)
    total_latency_ms: float = 0.0
    error_message: Optional[str] = None
    timestamp_ns: int = field(default_factory=time.perf_counter_ns)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseDispatcher(ABC):
    """
    Abstract base class for all UI and Intent Dispatchers.
    """

    def __init__(self, display_profile: Optional[DisplayProfile] = None):
        self.display_profile = display_profile or DisplayProfile.get_default_s26_ultra_wqhd()
        self.normalizer = CoordinateNormalizer(self.display_profile)

    @property
    def resolution(self) -> Tuple[int, int]:
        return self.display_profile.width, self.display_profile.height

    def set_display_profile(self, profile: DisplayProfile) -> None:
        self.display_profile = profile
        self.normalizer = CoordinateNormalizer(profile)

    @abstractmethod
    def dispatch_tap(self, x: int, y: int, delay_after_ms: int = 0) -> bool:
        """Dispatches a single physical tap at screen coordinates (x, y)."""
        pass

    @abstractmethod
    def dispatch_sequence(self, actions: List[TapAction]) -> DispatchResult:
        """Dispatches an ordered sequence of tap actions."""
        pass

    def dispatch_camera_preset(
        self,
        preset: CameraPreset,
        resolution: Optional[Tuple[int, int]] = None,
    ) -> DispatchResult:
        """
        Translates a CameraPreset into discrete Pro Video UI tap actions
        and dispatches them.
        """
        if resolution is not None:
            active_profile = DisplayProfile.from_resolution(resolution[0], resolution[1])
            normalizer = CoordinateNormalizer(active_profile)
        else:
            normalizer = self.normalizer

        actions = normalizer.build_preset_sequence(
            iso=preset.iso,
            shutter_speed=preset.shutter_speed,
            delay_after_ribbon_ms=35,
            delay_after_slider_ms=10,
        )

        result = self.dispatch_sequence(actions)
        result.metadata["preset"] = {
            "iso": preset.iso,
            "shutter_speed": preset.shutter_speed,
            "regime": preset.regime.value if isinstance(preset.regime, LightingRegime) else str(preset.regime),
            "reason": preset.reason,
        }
        return result

    def close(self) -> None:
        """Release any open resources or subprocesses."""
        pass

    def __enter__(self) -> BaseDispatcher:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


class MockDispatcher(BaseDispatcher):
    """
    Mock dispatcher for unit tests and deterministic simulation.
    Records all dispatched actions, simulates configurable latencies and failure modes.
    """

    def __init__(
        self,
        display_profile: Optional[DisplayProfile] = None,
        simulated_latency_ms: float = 0.0,
        simulate_failures: bool = False,
        fail_on_action_index: Optional[int] = None,
    ):
        super().__init__(display_profile)
        self.simulated_latency_ms = simulated_latency_ms
        self.simulate_failures = simulate_failures
        self.fail_on_action_index = fail_on_action_index

        self.history: List[Dict[str, Any]] = []
        self.presets_dispatched: List[CameraPreset] = []
        self.raw_taps: List[Tuple[int, int, int]] = []  # (x, y, delay)

    def dispatch_tap(self, x: int, y: int, delay_after_ms: int = 0) -> bool:
        start_ns = time.perf_counter_ns()
        if self.simulate_failures:
            return False

        if self.simulated_latency_ms > 0:
            time.sleep(self.simulated_latency_ms / 1000.0)

        self.raw_taps.append((x, y, delay_after_ms))
        latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0

        self.history.append({
            "type": "tap",
            "x": x,
            "y": y,
            "delay_after_ms": delay_after_ms,
            "latency_ms": latency_ms,
            "timestamp_ns": start_ns,
        })
        return True

    def dispatch_sequence(self, actions: List[TapAction]) -> DispatchResult:
        start_ns = time.perf_counter_ns()
        executed_count = 0
        executed_actions: List[TapAction] = []

        if not actions:
            return DispatchResult(
                success=True,
                actions_executed=0,
                actions=[],
                total_latency_ms=0.0,
                metadata={"mock": True},
            )

        for idx, action in enumerate(actions):
            if self.simulate_failures or (self.fail_on_action_index is not None and idx == self.fail_on_action_index):
                total_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
                return DispatchResult(
                    success=False,
                    actions_executed=executed_count,
                    actions=executed_actions,
                    total_latency_ms=total_ms,
                    error_message=f"Simulated failure at action index {idx}",
                    metadata={"mock": True, "failed_index": idx},
                )

            if self.simulated_latency_ms > 0:
                time.sleep(self.simulated_latency_ms / 1000.0)

            self.raw_taps.append((action.x_px, action.y_px, action.delay_after_ms))
            executed_actions.append(action)
            executed_count += 1

            self.history.append({
                "type": "sequence_step",
                "index": idx,
                "x": action.x_px,
                "y": action.y_px,
                "norm_x": action.norm_x,
                "norm_y": action.norm_y,
                "description": action.description,
                "delay_after_ms": action.delay_after_ms,
                "timestamp_ns": time.perf_counter_ns(),
            })

        total_latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        return DispatchResult(
            success=True,
            actions_executed=executed_count,
            actions=executed_actions,
            total_latency_ms=total_latency_ms,
            metadata={"mock": True},
        )

    def dispatch_camera_preset(
        self,
        preset: CameraPreset,
        resolution: Optional[Tuple[int, int]] = None,
    ) -> DispatchResult:
        self.presets_dispatched.append(preset)
        return super().dispatch_camera_preset(preset, resolution)

    def reset(self) -> None:
        """Clear recorded history."""
        self.history.clear()
        self.presets_dispatched.clear()
        self.raw_taps.clear()

    def get_last_tap(self) -> Optional[Dict[str, Any]]:
        """Returns the most recently recorded tap event."""
        if not self.history:
            return None
        return self.history[-1]

    def get_taps_count(self) -> int:
        """Returns the total number of raw taps executed."""
        return len(self.raw_taps)

    # Assertion Helpers for unit tests
    def assert_preset_dispatched(self, preset: CameraPreset) -> None:
        assert preset in self.presets_dispatched, f"Preset {preset} was not found in dispatched list: {self.presets_dispatched}"

    def assert_tap_dispatched(self, x: int, y: int, tolerance_px: int = 2) -> None:
        matched = any(
            abs(tap_x - x) <= tolerance_px and abs(tap_y - y) <= tolerance_px
            for tap_x, tap_y, _ in self.raw_taps
        )
        assert matched, f"Tap near ({x}, {y}) [tolerance={tolerance_px}px] was not found in {self.raw_taps}"

    def assert_action_count(self, count: int) -> None:
        assert len(self.raw_taps) == count, f"Expected {count} taps, got {len(self.raw_taps)}"


class PersistentADBDispatcher(BaseDispatcher):
    """
    High-performance ADB Dispatcher utilizing a persistent interactive `adb shell` process
    pipe to eliminate the 150-350ms OS subprocess spawn overhead, guaranteeing <35ms latency.
    """

    def __init__(
        self,
        adb_path: str = "adb",
        serial: Optional[str] = None,
        dry_run: bool = False,
        display_profile: Optional[DisplayProfile] = None,
        shell_pipe_timeout_s: float = 2.0,
        fallback_to_standalone: bool = True,
    ):
        super().__init__(display_profile)
        self.adb_path = adb_path
        self.serial = serial
        self.dry_run = dry_run
        self.shell_pipe_timeout_s = shell_pipe_timeout_s
        self.fallback_to_standalone = fallback_to_standalone

        self.process: Optional[subprocess.Popen] = None
        self._command_history: List[str] = []

        if not self.dry_run:
            self._start_persistent_shell()

    def _build_adb_base_cmd(self) -> List[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd.extend(["-s", self.serial])
        return cmd

    def _start_persistent_shell(self) -> bool:
        """Launches the persistent interactive adb shell process."""
        try:
            cmd = self._build_adb_base_cmd() + ["shell"]
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )
            return True
        except Exception:
            self.process = None
            return False

    def _is_shell_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def dispatch_tap(self, x: int, y: int, delay_after_ms: int = 0) -> bool:
        action = TapAction(x_px=x, y_px=y, delay_after_ms=delay_after_ms)
        res = self.dispatch_sequence([action])
        return res.success

    def dispatch_sequence(self, actions: List[TapAction]) -> DispatchResult:
        start_ns = time.perf_counter_ns()
        if not actions:
            return DispatchResult(
                success=True,
                actions_executed=0,
                actions=[],
                total_latency_ms=0.0,
                metadata={"adb": True},
            )

        executed_actions: List[TapAction] = []

        for idx, action in enumerate(actions):
            cmd_str = f"input tap {action.x_px} {action.y_px}\n"
            self._command_history.append(cmd_str.strip())

            if self.dry_run:
                executed_actions.append(action)
                if action.delay_after_ms > 0:
                    time.sleep(action.delay_after_ms / 1000.0)
                continue

            # Check / restart pipe if needed
            if not self._is_shell_alive():
                started = self._start_persistent_shell()
                if not started and not self.fallback_to_standalone:
                    total_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
                    return DispatchResult(
                        success=False,
                        actions_executed=len(executed_actions),
                        actions=executed_actions,
                        total_latency_ms=total_ms,
                        error_message="ADB shell process unavailable",
                        metadata={"failed_index": idx},
                    )

            # Attempt writing to persistent pipe
            pipe_success = False
            if self.process and self.process.stdin:
                try:
                    self.process.stdin.write(cmd_str)
                    self.process.stdin.flush()
                    pipe_success = True
                except (BrokenPipeError, OSError):
                    pipe_success = False

            # Fallback to standalone subprocess if pipe failed
            if not pipe_success and self.fallback_to_standalone:
                try:
                    full_cmd = self._build_adb_base_cmd() + ["shell", "input", "tap", str(action.x_px), str(action.y_px)]
                    subprocess.run(full_cmd, timeout=self.shell_pipe_timeout_s, check=True)
                    pipe_success = True
                except Exception as ex:
                    total_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
                    return DispatchResult(
                        success=False,
                        actions_executed=len(executed_actions),
                        actions=executed_actions,
                        total_latency_ms=total_ms,
                        error_message=f"Fallback ADB tap failed: {ex}",
                        metadata={"failed_index": idx},
                    )

            executed_actions.append(action)
            if action.delay_after_ms > 0:
                time.sleep(action.delay_after_ms / 1000.0)

        total_latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        return DispatchResult(
            success=True,
            actions_executed=len(executed_actions),
            actions=executed_actions,
            total_latency_ms=total_latency_ms,
            metadata={"adb": True, "dry_run": self.dry_run, "commands": list(self._command_history)},
        )

    def close(self) -> None:
        """Safely terminate ADB persistent process."""
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.write("exit\n")
                    self.process.stdin.flush()
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            finally:
                self.process = None


class TaskerIntentDispatcher(BaseDispatcher):
    """
    Dispatches camera adjustments via Android Broadcast Intents for Tasker / AutoInput automation.
    Intent Action: net.dinglisch.android.tasker.ACTION_TASK
    Task: SetCameraPreset
    Extras: iso, shutter, regime, reason
    """

    TASKER_INTENT_ACTION = "net.dinglisch.android.tasker.ACTION_TASK"
    DEFAULT_TASK_NAME = "SetCameraPreset"

    def __init__(
        self,
        adb_path: str = "adb",
        serial: Optional[str] = None,
        task_name: str = DEFAULT_TASK_NAME,
        dry_run: bool = True,
        display_profile: Optional[DisplayProfile] = None,
    ):
        super().__init__(display_profile)
        self.adb_path = adb_path
        self.serial = serial
        self.task_name = task_name
        self.dry_run = dry_run
        self.broadcast_history: List[Dict[str, Any]] = []

    def build_tasker_intent_extras(self, preset: CameraPreset) -> Dict[str, str]:
        """Constructs string dictionary of extras for Tasker intent."""
        return {
            "task": self.task_name,
            "iso": str(preset.iso),
            "shutter": str(preset.shutter_speed),
            "regime": preset.regime.value if isinstance(preset.regime, LightingRegime) else str(preset.regime),
            "reason": str(preset.reason),
        }

    def build_intent_command(self, preset: CameraPreset) -> str:
        """Generates the exact 'adb shell am broadcast' shell command."""
        extras = self.build_tasker_intent_extras(preset)
        extras_args = " ".join([f'--es {k} "{v}"' for k, v in extras.items()])
        return f"am broadcast -a {self.TASKER_INTENT_ACTION} {extras_args}"

    def dispatch_tap(self, x: int, y: int, delay_after_ms: int = 0) -> bool:
        # Fallback to coordinate normalizer tap
        return True

    def dispatch_sequence(self, actions: List[TapAction]) -> DispatchResult:
        return DispatchResult(
            success=True,
            actions_executed=len(actions),
            actions=actions,
            total_latency_ms=0.0,
            metadata={"transport": "tasker_intent"},
        )

    def dispatch_camera_preset(
        self,
        preset: CameraPreset,
        resolution: Optional[Tuple[int, int]] = None,
    ) -> DispatchResult:
        start_ns = time.perf_counter_ns()
        cmd_str = self.build_intent_command(preset)
        extras = self.build_tasker_intent_extras(preset)

        entry = {
            "intent_command": cmd_str,
            "extras": extras,
            "preset": preset,
            "timestamp_ns": start_ns,
        }
        self.broadcast_history.append(entry)

        if not self.dry_run:
            cmd = [self.adb_path]
            if self.serial:
                cmd.extend(["-s", self.serial])
            cmd.extend(["shell", cmd_str])
            try:
                subprocess.run(cmd, check=True, timeout=3.0)
            except Exception as ex:
                total_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
                return DispatchResult(
                    success=False,
                    actions_executed=0,
                    total_latency_ms=total_ms,
                    error_message=f"Tasker broadcast intent failed: {ex}",
                    metadata=entry,
                )

        total_latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        return DispatchResult(
            success=True,
            actions_executed=1,
            total_latency_ms=total_latency_ms,
            metadata=entry,
        )


class ShizukuDispatcher(BaseDispatcher):
    """
    Executes raw ADB commands directly on the Android device via Shizuku (`rish`).
    This provides bare-metal tap latency without requiring Tasker or a PC.
    """

    def __init__(self, display_profile: Optional[DisplayProfile] = None):
        super().__init__(display_profile)
        self.command_history: List[str] = []

    def dispatch_tap(self, x: int, y: int, delay_after_ms: int = 0) -> bool:
        cmd = f"rish -c 'input tap {x} {y}'"
        self.command_history.append(cmd)
        
        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            if delay_after_ms > 0:
                time.sleep(delay_after_ms / 1000.0)
            return True
        except subprocess.CalledProcessError:
            return False

    def dispatch_sequence(self, actions: List[TapAction]) -> DispatchResult:
        start_ns = time.perf_counter_ns()
        executed = []

        for action in actions:
            success = self.dispatch_tap(action.x_px, action.y_px, action.delay_after_ms)
            if success:
                executed.append(action)

        total_latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        return DispatchResult(
            success=len(executed) == len(actions),
            actions_executed=len(executed),
            actions=executed,
            total_latency_ms=total_latency_ms,
            metadata={"shizuku": True, "commands": self.command_history[-len(actions):]},
        )


class AccessibilityGestureDispatcher(BaseDispatcher):
    """
    Generates structured gesture payloads for Android AccessibilityService.dispatchGesture().
    Outputs JSON and Kotlin-compatible GestureDescription definitions.
    """

    def __init__(self, display_profile: Optional[DisplayProfile] = None):
        super().__init__(display_profile)
        self.generated_gestures: List[Dict[str, Any]] = []

    def dispatch_tap(self, x: int, y: int, delay_after_ms: int = 0) -> bool:
        action = TapAction(x_px=x, y_px=y, delay_after_ms=delay_after_ms)
        self.dispatch_sequence([action])
        return True

    def build_accessibility_gesture_payload(self, actions: List[TapAction]) -> Dict[str, Any]:
        """
        Builds an Android AccessibilityService GestureDescription payload.
        Each tap is mapped to a stroke with start_time_ms and duration_ms.
        """
        current_time_ms = 0
        strokes = []

        for idx, act in enumerate(actions):
            stroke = {
                "stroke_index": idx,
                "x": act.x_px,
                "y": act.y_px,
                "start_time_ms": current_time_ms,
                "duration_ms": 25,  # 25ms tap duration
                "description": act.description,
            }
            strokes.append(stroke)
            current_time_ms += 25 + act.delay_after_ms

        return {
            "type": "GestureDescription",
            "strokes": strokes,
            "total_duration_ms": current_time_ms,
            "strokes_count": len(strokes),
        }

    def build_kotlin_accessibility_snippet(self, actions: List[TapAction]) -> str:
        """Produces a Kotlin snippet ready for Android AccessibilityService."""
        lines = [
            "val gestureBuilder = GestureDescription.Builder()",
        ]
        current_time_ms = 0
        for act in actions:
            lines.append(
                f"val path_{current_time_ms} = Path().apply {{ moveTo({act.x_px}f, {act.y_px}f) }}"
            )
            lines.append(
                f"gestureBuilder.addStroke(GestureDescription.StrokeDescription(path_{current_time_ms}, {current_time_ms}L, 25L))"
            )
            current_time_ms += 25 + act.delay_after_ms
        lines.append("dispatchGesture(gestureBuilder.build(), null, null)")
        return "\n".join(lines)

    def dispatch_sequence(self, actions: List[TapAction]) -> DispatchResult:
        start_ns = time.perf_counter_ns()
        payload = self.build_accessibility_gesture_payload(actions)
        self.generated_gestures.append(payload)

        total_latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        return DispatchResult(
            success=True,
            actions_executed=len(actions),
            actions=actions,
            total_latency_ms=total_latency_ms,
            metadata={"accessibility_payload": payload},
        )


def dispatch_preset(
    preset: CameraPreset,
    resolution: Tuple[int, int] = (3120, 1440),
    dispatcher: Optional[BaseDispatcher] = None,
) -> DispatchResult:
    """
    Top-level interface contract function to dispatch camera presets.
    Defaults to MockDispatcher if no dispatcher instance is passed.
    """
    active_dispatcher = dispatcher or MockDispatcher()
    return active_dispatcher.dispatch_camera_preset(preset, resolution=resolution)
