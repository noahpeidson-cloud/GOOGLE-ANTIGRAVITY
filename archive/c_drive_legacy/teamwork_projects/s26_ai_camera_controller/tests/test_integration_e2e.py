"""
test_integration_e2e.py - Tier 3 Full Pipeline End-to-End Integration Tests

Validates complete integration across all subsystem layers:
[Raw Frame / Sensor Ingestion]
           │
           ▼
[LightDetectorEngine (Rec.709 Luma, 4-Zone ROI, 16-Bin Hist, Percentiles)]
           │
           ▼
[ConcertStateMachine (Hysteresis, Dwell, Laser Bypass, 6-25Hz Strobe Lock)]
           │
           ▼
[CoordinateNormalizer / Intent Dispatcher (WQHD+ / FHD+ / ADB / Tasker / Mock)]
           │
           ▼
[MockAndroidDevice (Samsung S26 Ultra Pro Video State & Airplane Mode)]
"""

from __future__ import annotations

import threading
import time
from typing import List, Tuple
import numpy as np
import pytest

from s26_controller.core.config import DetectorConfig, ZoneROI
from s26_controller.core.coordinates import (
    CameraParameter,
    CoordinateNormalizer,
    DisplayProfile,
    DisplayResolution,
    ResolutionScaler,
    RibbonButton,
    SamsungS26CoordinateMap,
    TapAction,
)
from s26_controller.core.detector import LightDetectorEngine
from s26_controller.core.dispatcher import (
    AccessibilityGestureDispatcher,
    BaseDispatcher,
    CameraPreset,
    DispatchResult,
    LightingRegime,
    MockDispatcher,
    PersistentADBDispatcher,
    TaskerIntentDispatcher,
    dispatch_preset,
)
from s26_controller.core.metrics import FrameMetrics
from s26_controller.core.state_machine import (
    DEFAULT_CAMERA_PRESETS,
    ConcertStateMachine,
    StateMachineConfig,
)
from s26_controller.core.strobe_filter import StrobeFilter
from s26_controller.daemon import (
    DaemonStepResult,
    DaemonTelemetry,
    RegimeTransitionRecord,
    S26CameraControllerDaemon,
)
from s26_controller.simulation.light_simulator import (
    ConcertLightSimulator,
    ConcertScenario,
    generate_blackout_drop_scenario,
    generate_full_concert_set_scenario,
    generate_laser_assault_scenario,
    generate_pyro_flood_scenario,
    generate_strobe_train_scenario,
)
from s26_controller.simulation.mock_device import (
    CapturedCommand,
    MockAndroidDevice,
    MockDeviceDispatcher,
    ProVideoCameraState,
)


class TestFullPipelineIntegration:
    """Tier 3: Full end-to-end integration across Detector -> State Machine -> Dispatcher -> Device."""

    def test_detector_to_mock_device_direct_pipeline(self):
        """Tests complete frame-to-tap intent flow through mock device."""
        device = MockAndroidDevice(initial_iso=640, initial_shutter="1/60")
        dispatcher = MockDeviceDispatcher(device)
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

        # Feed normal ambient frames
        ambient = np.full((90, 160, 3), 50, dtype=np.uint8)
        for _ in range(5):
            res = daemon.step(ambient)
            assert res.regime == LightingRegime.NORMAL

        assert device.current_iso == 640

        # Inject high-intensity laser strike
        laser_frame = np.full((90, 160, 3), 30, dtype=np.uint8)
        laser_frame[0:27, 40:120, :] = 255
        laser_frame[27:63, 60:100, :] = 255

        res_laser = daemon.step(laser_frame)
        assert res_laser.triggered is True
        assert res_laser.regime == LightingRegime.LASER_SPIKE
        assert res_laser.preset.iso == 100
        assert res_laser.preset.shutter_speed in ("1/250", "1/240")

        # Mock device should have updated its state based on simulated screen taps
        assert device.current_iso == 100
        assert device.state.slider_open is True
        assert len(device.captured_taps) >= 2
        daemon.close()

    def test_resolution_aware_pipeline_fhd_vs_wqhd(self):
        """Verifies pipeline correctly targets both WQHD+ (3120x1440) and FHD+ (2340x1080) screens."""
        # WQHD+ Setup
        wqhd_profile = DisplayProfile.get_default_s26_ultra_wqhd()
        wqhd_device = MockAndroidDevice(display_profile=wqhd_profile)
        wqhd_daemon = S26CameraControllerDaemon(dispatcher=MockDeviceDispatcher(wqhd_device))

        # FHD+ Setup
        fhd_profile = DisplayProfile.get_default_s26_ultra_fhd()
        fhd_device = MockAndroidDevice(display_profile=fhd_profile)
        fhd_daemon = S26CameraControllerDaemon(dispatcher=MockDeviceDispatcher(fhd_device))

        laser_frame = np.full((90, 160, 3), 30, dtype=np.uint8)
        laser_frame[0:27, 40:120, :] = 255
        laser_frame[27:63, 60:100, :] = 255

        # Execute step on both
        wqhd_res = wqhd_daemon.step(laser_frame)
        fhd_res = fhd_daemon.step(laser_frame)

        assert wqhd_res.triggered and fhd_res.triggered
        assert wqhd_device.current_iso == 100
        assert fhd_device.current_iso == 100

        # Verify physical tap coordinates differed according to resolution scaling
        wqhd_taps = wqhd_device.captured_taps
        fhd_taps = fhd_device.captured_taps

        # Ribbon tap X: WQHD (686) vs FHD (515)
        assert wqhd_taps[0][0] == 686
        assert fhd_taps[0][0] == 515

        # Ribbon tap Y: WQHD (1267) vs FHD (950)
        assert wqhd_taps[0][1] == 1267
        assert fhd_taps[0][1] == 950

        # Slider tap X: WQHD (874) vs FHD (655)
        assert wqhd_taps[1][0] == 874
        assert fhd_taps[1][0] == 655

        wqhd_daemon.close()
        fhd_daemon.close()

    def test_complete_regime_cycle_integration(self):
        """
        Drives the pipeline through a complete cycle with monotonic simulated timestamps:
        NORMAL -> BLACKOUT -> LASER_SPIKE -> FLOOD_PYRO -> STROBE_LOCK -> NORMAL
        """
        device = MockAndroidDevice()
        daemon = S26CameraControllerDaemon(dispatcher=MockDeviceDispatcher(device))

        t_cur_ns = 1_000_000_000  # Start at 1.0s
        dt_ns = int(round((1.0 / 60.0) * 1e9))  # 16.66ms per frame

        # 1. NORMAL baseline (20 frames, ~330ms)
        for _ in range(20):
            daemon.step(np.full((90, 160, 3), 50, dtype=np.uint8), timestamp_ns=t_cur_ns)
            t_cur_ns += dt_ns
        assert daemon.current_regime == LightingRegime.NORMAL

        # 2. BLACKOUT (25 frames of pitch black, ~400ms > dwell)
        for _ in range(25):
            daemon.step(np.full((90, 160, 3), 2, dtype=np.uint8), timestamp_ns=t_cur_ns)
            t_cur_ns += dt_ns
        assert daemon.current_regime == LightingRegime.BLACKOUT
        assert device.current_iso == 200

        # 3. Emergency LASER_SPIKE override (immediate 1-frame trigger)
        laser_f = np.full((90, 160, 3), 20, dtype=np.uint8)
        laser_f[0:27, 40:120, :] = 255
        laser_f[27:63, 60:100, :] = 255
        daemon.step(laser_f, timestamp_ns=t_cur_ns)
        t_cur_ns += dt_ns
        assert daemon.current_regime == LightingRegime.LASER_SPIKE
        assert device.current_iso == 100

        # Advance beyond dwell window (40 frames, ~660ms > 500ms cooldown)
        for _ in range(40):
            daemon.step(np.full((90, 160, 3), 60, dtype=np.uint8), timestamp_ns=t_cur_ns)
            t_cur_ns += dt_ns
        assert daemon.current_regime == LightingRegime.NORMAL

        # 4. Full arena FLOOD_PYRO (Y >= 245, C_high >= 0.40 for 25 frames, ~400ms > dwell)
        flood_f = np.full((90, 160, 3), 250, dtype=np.uint8)
        for _ in range(25):
            daemon.step(flood_f, timestamp_ns=t_cur_ns)
            t_cur_ns += dt_ns
        assert daemon.current_regime == LightingRegime.FLOOD_PYRO
        assert device.current_shutter in ("1/120", "1/125")

        # 5. Strobe Lock via synthetic train
        # Return to normal for 40 frames
        for _ in range(40):
            daemon.step(np.full((90, 160, 3), 50, dtype=np.uint8), timestamp_ns=t_cur_ns)
            t_cur_ns += dt_ns

        sim = ConcertLightSimulator(fps=60.0, seed=123)
        strobe_frames = sim.generate_scenario_frames(ConcertScenario.SCENARIO_C_STROBE_TRAIN, duration_sec=2.5)
        strobe_detected = False
        for f, ts in strobe_frames:
            r = daemon.step(f, timestamp_ns=ts)
            if r.regime == LightingRegime.STROBE_LOCK:
                strobe_detected = True

        assert strobe_detected is True
        daemon.close()

    def test_callback_hooks_integration(self):
        """Tests that on_frame, on_regime_change, and on_preset_dispatched triggers fire correctly."""
        frame_events: List[DaemonStepResult] = []
        regime_events: List[Tuple[LightingRegime, LightingRegime, Optional[CameraPreset]]] = []
        dispatch_events: List[Tuple[CameraPreset, DispatchResult]] = []

        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
        daemon.on_frame = lambda res: frame_events.append(res)
        daemon.on_regime_change = lambda prev, curr, preset: regime_events.append((prev, curr, preset))
        daemon.on_preset_dispatched = lambda preset, res: dispatch_events.append((preset, res))

        # Baseline frame
        daemon.step(np.full((90, 160, 3), 50, dtype=np.uint8))
        assert len(frame_events) == 1

        # Laser spike
        laser = np.full((90, 160, 3), 30, dtype=np.uint8)
        laser[0:27, 40:120, :] = 255
        laser[27:63, 60:100, :] = 255
        daemon.step(laser)

        assert len(frame_events) == 2
        assert len(regime_events) >= 1
        assert regime_events[0][0] == LightingRegime.NORMAL
        assert regime_events[0][1] == LightingRegime.LASER_SPIKE
        assert len(dispatch_events) >= 1
        assert dispatch_events[0][0].regime == LightingRegime.LASER_SPIKE
        daemon.close()

    def test_background_worker_thread_lifecycle(self):
        """Tests launching and stopping daemon background worker loop with streaming frames."""
        device = MockAndroidDevice()
        dispatcher = MockDeviceDispatcher(device)
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

        sim = ConcertLightSimulator(fps=60.0)
        stream = sim.stream_scenario(ConcertScenario.SCENARIO_A_BLACKOUT_DROP, duration_sec=1.5, real_time=False)

        assert daemon.is_running is False
        daemon.start_background_stream(stream, fps=60.0, real_time=False)
        time.sleep(0.1)

        # Wait for completion or stop
        daemon.stop()
        assert daemon.is_running is False
        assert daemon.frame_count > 0
        daemon.close()

    def test_multi_channel_frame_formats(self):
        """Verifies daemon accepts 3D RGB, 2D Grayscale, and performs bit-shift Rec.709 calculations identically."""
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())

        rgb_frame = np.full((90, 160, 3), 100, dtype=np.uint8)
        gray_frame = np.full((90, 160), 100, dtype=np.uint8)

        res_rgb = daemon.step(rgb_frame)
        res_gray = daemon.step(gray_frame)

        assert abs(res_rgb.metrics.mean_luma - 100.0) < 1.0
        assert abs(res_gray.metrics.mean_luma - 100.0) < 1.0
        daemon.close()

    def test_telemetry_and_transition_records_audit(self):
        """Verifies full telemetry history tracking and transition audit logging."""
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
        sim = ConcertLightSimulator(fps=60.0, seed=42)
        frames = sim.generate_scenario_frames(ConcertScenario.SCENARIO_B_LASER_ASSAULT, duration_sec=2.0)

        for f, ts in frames:
            daemon.step(f, timestamp_ns=ts)

        telemetry = daemon.get_telemetry()
        assert telemetry.total_frames_processed == 120
        assert len(telemetry.transitions) >= 1
        assert telemetry.p99_compute_latency_ms < 1.0
        assert telemetry.mean_compute_latency_ms > 0.0

        first_trans = telemetry.transitions[0]
        assert isinstance(first_trans, RegimeTransitionRecord)
        assert first_trans.to_regime == LightingRegime.LASER_SPIKE
        assert first_trans.preset is not None
        daemon.close()
