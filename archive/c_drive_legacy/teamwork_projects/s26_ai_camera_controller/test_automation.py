#!/usr/bin/env python3
"""
test_automation.py - Standalone Acceptance Verification Script for S26 AI Camera Controller

Acceptance Criteria:
1. Simulates sudden lighting deviations (Laser Strike, Blackout Drop, Strobe Lock) and verifies
   corresponding Pro Video UI screen tap intents are dispatched in strictly < 500ms.
2. Verifies 100% offline on-device execution with device in Airplane Mode (0 cloud APIs, 0 network activity).
3. Validates resolution-aware coordinate calculation for Samsung Galaxy S26 Ultra (WQHD+ & FHD+).
4. Prints detailed diagnostic telemetry and exits with return code 0 on complete pass.

Usage:
    python test_automation.py
    python test_automation.py --scenario laser --resolution wqhd --verbose
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

# Ensure s26_ai_camera_controller package root is on PYTHONPATH
_PKG_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from s26_controller.core.config import DetectorConfig
from s26_controller.core.coordinates import (
    CameraParameter,
    CoordinateNormalizer,
    DisplayProfile,
    DisplayResolution,
    SamsungS26CoordinateMap,
)
from s26_controller.core.detector import LightDetectorEngine
from s26_controller.core.dispatcher import (
    BaseDispatcher,
    CameraPreset,
    DispatchResult,
    LightingRegime,
    MockDispatcher,
)
from s26_controller.core.state_machine import ConcertStateMachine, StateMachineConfig
from s26_controller.daemon import DaemonStepResult, S26CameraControllerDaemon
from s26_controller.simulation.light_simulator import (
    ConcertLightSimulator,
    ConcertScenario,
)
from s26_controller.simulation.mock_device import (
    MockAndroidDevice,
    MockDeviceDispatcher,
)


class AcceptanceTestRunner:
    """
    Automated Acceptance Test Harness executing verification suites for S26 AI Camera Controller.
    """

    def __init__(self, verbose: bool = False, display_res: str = "wqhd") -> None:
        self.verbose = verbose
        if display_res.lower() in ("fhd", "fhd+"):
            self.profile = DisplayProfile.get_default_s26_ultra_fhd()
        else:
            self.profile = DisplayProfile.get_default_s26_ultra_wqhd()

        self.passed_checks = 0
        self.total_checks = 0
        self.test_results: List[Dict[str, Any]] = []

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def _record_result(self, name: str, passed: bool, details: str, latency_ms: Optional[float] = None) -> None:
        self.total_checks += 1
        if passed:
            self.passed_checks += 1
        self.test_results.append({
            "name": name,
            "passed": passed,
            "details": details,
            "latency_ms": latency_ms,
        })
        status_str = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
        lat_str = f" ({latency_ms:.2f} ms)" if latency_ms is not None else ""
        print(f"  {status_str} {name}{lat_str}: {details}")

    def run_all(self) -> bool:
        """Executes all acceptance test suites."""
        print("=" * 80)
        print("S26 AI CAMERA CONTROLLER - ACCEPTANCE VERIFICATION HARNESS")
        print(f"Target Device: Samsung Galaxy S26 Ultra | Display: {self.profile.resolution_type.value} ({self.profile.width}x{self.profile.height})")
        print("=" * 80)

        # Suite 1: Offline Airplane Mode Isolation Verification
        print("\n[SUITE 1] Verifying Offline Isolation & Airplane Mode Compliance...")
        self.verify_offline_airplane_mode()

        # Suite 2: Sudden Laser Strike Light Spike (<500ms Trigger & Dispatch)
        print("\n[SUITE 2] Verifying Sudden Laser Strike Reaction & Tap Dispatch (<500ms)...")
        self.verify_laser_strike_reaction()

        # Suite 3: Sudden Blackout Drop (<500ms Trigger & Dispatch)
        print("\n[SUITE 3] Verifying Sudden Blackout Drop Reaction & Tap Dispatch (<500ms)...")
        self.verify_blackout_drop_reaction()

        # Suite 4: Strobe Lock Anti-Hunting Verification
        print("\n[SUITE 4] Verifying 14Hz Strobe Lock & Anti-Hunting Freeze...")
        self.verify_strobe_lock_freeze()

        # Suite 5: Resolution-Aware Screen Tap Coordinates
        print("\n[SUITE 5] Verifying Resolution-Aware Touch Coordinate Mapping...")
        self.verify_coordinate_mapping()

        # Suite 6: Sub-Millisecond Decision Latency Benchmark (<1.0ms contract)
        print("\n[SUITE 6] Verifying Decision Latency Benchmark (<1.0ms compute budget)...")
        self.verify_decision_compute_benchmark()

        # Summary
        print("\n" + "=" * 80)
        print(f"ACCEPTANCE RESULTS: {self.passed_checks}/{self.total_checks} CHECKS PASSED")
        print("=" * 80)

        all_passed = (self.passed_checks == self.total_checks and self.total_checks > 0)
        if all_passed:
            print("\033[92m>>> ALL ACCEPTANCE REQUIREMENTS MET SUCCESSFULLY (Exit Code 0) <<<\033[0m\n")
        else:
            print("\033[91m>>> ACCEPTANCE FAILURES DETECTED! <<<\033[0m\n")

        return all_passed

    def verify_offline_airplane_mode(self) -> None:
        """Verifies zero cloud dependencies and Airplane Mode operation."""
        mock_device = MockAndroidDevice(display_profile=self.profile, airplane_mode=True)
        dispatcher = MockDeviceDispatcher(mock_device)
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

        # Confirm initial state
        assert mock_device.is_airplane_mode is True
        assert mock_device.state.network_requests_count == 0

        # Feed 30 frames through daemon
        sim = ConcertLightSimulator(fps=60.0, seed=101)
        frames = sim.generate_scenario_frames(ConcertScenario.SCENARIO_A_BLACKOUT_DROP, duration_sec=0.5)

        for frame, ts_ns in frames:
            res = daemon.step(frame, timestamp_ns=ts_ns)
            assert res is not None

        # Verify device remained strictly isolated
        try:
            mock_device.assert_airplane_mode_compliance()
            self._record_result(
                "Offline Airplane Mode Isolation",
                True,
                "Device executed 100% offline in Airplane Mode with 0 network calls",
            )
        except AssertionError as e:
            self._record_result("Offline Airplane Mode Isolation", False, str(e))
        finally:
            daemon.close()

    def verify_laser_strike_reaction(self) -> None:
        """
        Simulates an intense sudden laser strike spike and verifies screen tap intent
        dispatch within the strict <500ms latency budget.
        """
        mock_device = MockAndroidDevice(
            display_profile=self.profile,
            simulate_touch_latency_ms=0.0,
            initial_iso=640,
            initial_shutter="1/60",
        )
        dispatcher = MockDeviceDispatcher(mock_device)
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

        # 1. Establish baseline ambient state (10 frames of normal ambient lighting)
        ambient_frame = np.full((90, 160, 3), 45, dtype=np.uint8)
        t_base = time.perf_counter_ns()
        for i in range(10):
            ts = t_base + int(i * (1e9 / 60.0))
            daemon.step(ambient_frame, timestamp_ns=ts)

        assert daemon.current_regime == LightingRegime.NORMAL
        assert mock_device.current_iso == 640

        # 2. Inject sudden extreme laser spike (P99=255, collimated beams in stage center & ceiling)
        laser_frame = np.full((90, 160, 3), 35, dtype=np.uint8)
        laser_frame[0:27, 40:120, :] = 255
        laser_frame[27:63, 60:100, :] = 255

        t_spike_start = time.perf_counter()
        t_spike_ns = time.perf_counter_ns()

        # Step daemon with laser frame
        step_res = daemon.step(laser_frame, timestamp_ns=t_spike_ns)
        t_spike_end = time.perf_counter()

        elapsed_ms = (t_spike_end - t_spike_start) * 1000.0

        # Verify trigger and latency
        regime = step_res.regime
        preset = step_res.preset
        dispatched = step_res.dispatch_result is not None and step_res.dispatch_result.success

        # Assertions
        passed_regime = (regime == LightingRegime.LASER_SPIKE)
        passed_preset = (preset is not None and preset.iso <= 200)
        passed_latency = (elapsed_ms < 500.0)
        passed_device_state = (mock_device.current_iso <= 200)

        all_ok = passed_regime and passed_preset and passed_latency and passed_device_state and dispatched

        detail_msg = (
            f"Laser spike detected -> Regime: {regime.value}, Target ISO: {preset.iso if preset else 'None'}, "
            f"Target Shutter: {preset.shutter_speed if preset else 'None'}, "
            f"Mock Device ISO: {mock_device.current_iso}"
        )
        self._record_result(
            "Laser Strike Reaction & Dispatch",
            all_ok,
            detail_msg,
            latency_ms=elapsed_ms,
        )
        assert elapsed_ms < 500.0, f"Trigger latency {elapsed_ms:.2f}ms exceeded 500ms threshold!"
        daemon.close()

    def verify_blackout_drop_reaction(self) -> None:
        """
        Simulates sudden stage blackout drop and asserts reactive trigger and tap intent
        dispatch within <500ms.
        """
        mock_device = MockAndroidDevice(
            display_profile=self.profile,
            initial_iso=640,
            initial_shutter="1/60",
        )
        dispatcher = MockDeviceDispatcher(mock_device)
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

        # Baseline frames
        normal_frame = np.full((90, 160, 3), 60, dtype=np.uint8)
        for i in range(10):
            daemon.step(normal_frame)

        # Blackout frame (luma < 5)
        blackout_frame = np.full((90, 160, 3), 3, dtype=np.uint8)

        t0 = time.perf_counter()
        # Feed 3 blackout frames (to satisfy 2-frame persistence window)
        step_res = None
        for _ in range(3):
            step_res = daemon.step(blackout_frame)

        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000.0

        assert step_res is not None
        passed_regime = (daemon.current_regime == LightingRegime.BLACKOUT)
        passed_iso = (mock_device.current_iso == 200)  # Locked to ISO 200 for noise suppression
        passed_lat = (elapsed_ms < 500.0)

        all_ok = passed_regime and passed_iso and passed_lat
        detail_msg = (
            f"Blackout detected -> Regime: {daemon.current_regime.value}, "
            f"Device ISO clamped to {mock_device.current_iso} (noise lock), Device Shutter: {mock_device.current_shutter}"
        )
        self._record_result(
            "Blackout Drop Reaction & Dispatch",
            all_ok,
            detail_msg,
            latency_ms=elapsed_ms,
        )
        assert elapsed_ms < 500.0, f"Blackout trigger latency {elapsed_ms:.2f}ms exceeded 500ms!"
        daemon.close()

    def verify_strobe_lock_freeze(self) -> None:
        """
        Simulates 14Hz Xenon strobe burst and asserts Strobe Lock anti-hunting freeze.
        """
        mock_device = MockAndroidDevice(display_profile=self.profile)
        dispatcher = MockDeviceDispatcher(mock_device)
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

        # Generate 2.5s of Scenario C (Phase 1: 0..1.0s baseline, Phase 2: 1.0..4.0s 14Hz Strobe Train)
        sim = ConcertLightSimulator(fps=60.0, seed=777)
        strobe_frames = sim.generate_scenario_frames(
            ConcertScenario.SCENARIO_C_STROBE_TRAIN,
            duration_sec=2.5,
        )

        strobe_lock_entered = False
        dispatches_during_strobe = 0

        for frame, ts_ns in strobe_frames:
            res = daemon.step(frame, timestamp_ns=ts_ns)
            if res.regime == LightingRegime.STROBE_LOCK:
                strobe_lock_entered = True
            if strobe_lock_entered and res.triggered:
                dispatches_during_strobe += 1

        # While locked, slider adjustments should be frozen (anti-hunting)
        passed = strobe_lock_entered and (dispatches_during_strobe <= 1)
        detail_msg = (
            f"14Hz Strobe train recognized -> STROBE_LOCK engaged: {strobe_lock_entered}, "
            f"Slider Hunting Dispatches suppressed: {dispatches_during_strobe}"
        )
        self._record_result("Strobe Lock Anti-Hunting Freeze", passed, detail_msg)
        daemon.close()

    def verify_coordinate_mapping(self) -> None:
        """
        Verifies resolution-aware coordinate calculation for WQHD+ (3120x1440) and FHD+ (2340x1080).
        """
        norm_wqhd = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_wqhd())
        norm_fhd = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_fhd())

        # Check ISO ribbon button in WQHD+ and FHD+
        wqhd_x, wqhd_y = norm_wqhd.get_ribbon_button_pixels(CameraParameter.ISO)
        fhd_x, fhd_y = norm_fhd.get_ribbon_button_pixels(CameraParameter.ISO)

        assert wqhd_x == 686 and wqhd_y == 1267, f"WQHD ISO Ribbon mismatch: ({wqhd_x}, {wqhd_y})"
        assert fhd_x == 515 and fhd_y == 950, f"FHD ISO Ribbon mismatch: ({fhd_x}, {fhd_y})"

        # Check ISO 100 slider tick coordinate in WQHD+ and FHD+
        tick_wqhd_x, tick_wqhd_y = norm_wqhd.get_iso_tick_pixels(100)
        tick_fhd_x, tick_fhd_y = norm_fhd.get_iso_tick_pixels(100)

        assert (tick_wqhd_x, tick_wqhd_y) == (874, 1037), f"ISO 100 tick mismatch: ({tick_wqhd_x}, {tick_wqhd_y})"
        assert (tick_fhd_x, tick_fhd_y) == (655, 778), f"ISO 100 FHD tick mismatch: ({tick_fhd_x}, {tick_fhd_y})"

        detail_msg = (
            f"WQHD+ ISO Button ({wqhd_x}, {wqhd_y}), FHD+ ISO Button ({fhd_x}, {fhd_y}), "
            f"ISO 100 Tick ({tick_wqhd_x}, {tick_wqhd_y})"
        )
        self._record_result("Resolution-Aware Coordinate Geometry", True, detail_msg)

    def verify_decision_compute_benchmark(self) -> None:
        """
        Runs 300 synthetic frames and benchmarks detector + state machine decision latency.
        Asserts P99 < 1.0ms.
        """
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
        sim = ConcertLightSimulator(fps=60.0, seed=42)
        frames = sim.generate_scenario_frames(ConcertScenario.SCENARIO_E_FULL_CONCERT_SET, duration_sec=5.0)

        for frame, ts in frames:
            daemon.step(frame, timestamp_ns=ts)

        telemetry = daemon.get_telemetry()
        p99 = telemetry.p99_compute_latency_ms
        p50 = telemetry.p50_compute_latency_ms
        mean = telemetry.mean_compute_latency_ms

        passed = p99 < 1.0
        detail_msg = f"Mean: {mean:.3f}ms | P50: {p50:.3f}ms | P99: {p99:.3f}ms (Contract Budget: <1.0ms)"
        self._record_result("Decision Compute Latency Benchmark", passed, detail_msg, latency_ms=p99)
        assert p99 < 1.0, f"P99 latency {p99:.3f}ms exceeded 1.0ms contract!"
        daemon.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="S26 AI Camera Controller - Standalone Acceptance Verification Script",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable detailed debug diagnostic logging",
    )
    parser.add_argument(
        "--resolution", "-r",
        type=str,
        default="wqhd",
        choices=["wqhd", "fhd"],
        help="Target Samsung Galaxy S26 Ultra display resolution (default: wqhd)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = AcceptanceTestRunner(verbose=args.verbose, display_res=args.resolution)
    success = runner.run_all()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
