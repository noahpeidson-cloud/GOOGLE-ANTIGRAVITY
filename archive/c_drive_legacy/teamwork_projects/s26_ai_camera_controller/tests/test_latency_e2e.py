"""
test_latency_e2e.py - Tier 4 Latency Verification & Performance Benchmark Tests

Asserts strict real-time performance and timing budgets for S26 AI Camera Controller:
1. Trigger-to-Dispatch Latency: <500ms contract under both 60fps and 30fps streaming feeds.
2. Sub-Millisecond Decision Compute Latency: P99 < 1.0ms (Detector + State Machine evaluation).
3. High Throughput Execution: >1000 FPS offline processing capability.
4. Dispatcher Execution Latency: <150ms for complete multi-tap preset UI sequences and <10ms for single taps.
"""

from __future__ import annotations

import time
from typing import List, Tuple
import numpy as np
import pytest

from s26_controller.core.coordinates import DisplayProfile
from s26_controller.core.dispatcher import (
    BaseDispatcher,
    CameraPreset,
    DispatchResult,
    LightingRegime,
    MockDispatcher,
    PersistentADBDispatcher,
)
from s26_controller.core.state_machine import ConcertStateMachine
from s26_controller.daemon import DaemonStepResult, S26CameraControllerDaemon
from s26_controller.simulation.light_simulator import (
    ConcertLightSimulator,
    ConcertScenario,
)
from s26_controller.simulation.mock_device import (
    MockAndroidDevice,
    MockDeviceDispatcher,
)


class TestTriggerToDispatchLatency:
    """Tier 4: Trigger-to-dispatch latency verification under 60fps and 30fps streams."""

    def test_laser_spike_latency_60fps(self):
        """Asserts laser spike trigger-to-dispatch latency is strictly <500ms at 60fps."""
        device = MockAndroidDevice(initial_iso=640, initial_shutter="1/60")
        dispatcher = MockDeviceDispatcher(device)
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

        # Baseline ambient frames at 60fps (dt = 16.66ms)
        ambient = np.full((90, 160, 3), 45, dtype=np.uint8)
        t_base = time.perf_counter_ns()
        dt_60_ns = int(round(1e9 / 60.0))

        for i in range(10):
            daemon.step(ambient, timestamp_ns=t_base + i * dt_60_ns)

        # High-intensity laser burst frame
        laser_frame = np.full((90, 160, 3), 30, dtype=np.uint8)
        laser_frame[0:27, 40:120, :] = 255
        laser_frame[27:63, 60:100, :] = 255

        t_start = time.perf_counter()
        step_res = daemon.step(laser_frame, timestamp_ns=t_base + 10 * dt_60_ns)
        t_end = time.perf_counter()

        elapsed_ms = (t_end - t_start) * 1000.0

        assert step_res.triggered is True
        assert step_res.regime == LightingRegime.LASER_SPIKE
        assert device.current_iso == 100
        assert elapsed_ms < 500.0, f"Trigger latency {elapsed_ms:.2f}ms exceeded 500ms threshold!"
        assert elapsed_ms < 150.0, f"Full preset sequence latency {elapsed_ms:.2f}ms exceeded 150ms expected!"
        daemon.close()

    def test_laser_spike_latency_30fps(self):
        """Asserts laser spike trigger-to-dispatch latency is strictly <500ms at 30fps."""
        device = MockAndroidDevice(initial_iso=640, initial_shutter="1/60")
        dispatcher = MockDeviceDispatcher(device)
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

        # Baseline ambient frames at 30fps (dt = 33.33ms)
        ambient = np.full((90, 160, 3), 45, dtype=np.uint8)
        t_base = time.perf_counter_ns()
        dt_30_ns = int(round(1e9 / 30.0))

        for i in range(5):
            daemon.step(ambient, timestamp_ns=t_base + i * dt_30_ns)

        laser_frame = np.full((90, 160, 3), 30, dtype=np.uint8)
        laser_frame[0:27, 40:120, :] = 255
        laser_frame[27:63, 60:100, :] = 255

        t_start = time.perf_counter()
        step_res = daemon.step(laser_frame, timestamp_ns=t_base + 5 * dt_30_ns)
        t_end = time.perf_counter()

        elapsed_ms = (t_end - t_start) * 1000.0

        assert step_res.triggered is True
        assert step_res.regime == LightingRegime.LASER_SPIKE
        assert device.current_iso == 100
        assert elapsed_ms < 500.0, f"30fps trigger latency {elapsed_ms:.2f}ms exceeded 500ms!"
        assert elapsed_ms < 150.0, f"30fps sequence latency {elapsed_ms:.2f}ms exceeded 150ms!"
        daemon.close()

    def test_blackout_drop_latency_60fps(self):
        """Asserts blackout drop trigger latency under 60fps streaming is strictly <500ms."""
        device = MockAndroidDevice(initial_iso=640, initial_shutter="1/60")
        dispatcher = MockDeviceDispatcher(device)
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

        # Ambient baseline
        normal_frame = np.full((90, 160, 3), 55, dtype=np.uint8)
        t_base = time.perf_counter_ns()
        dt_60_ns = int(round(1e9 / 60.0))

        for i in range(10):
            daemon.step(normal_frame, timestamp_ns=t_base + i * dt_60_ns)

        # Blackout frames (3 frames to satisfy 2-frame persistence)
        blackout_frame = np.full((90, 160, 3), 2, dtype=np.uint8)

        t_start = time.perf_counter()
        for j in range(3):
            step_res = daemon.step(blackout_frame, timestamp_ns=t_base + (10 + j) * dt_60_ns)
        t_end = time.perf_counter()

        elapsed_ms = (t_end - t_start) * 1000.0

        assert daemon.current_regime == LightingRegime.BLACKOUT
        assert device.current_iso == 200
        assert elapsed_ms < 500.0, f"Blackout drop latency {elapsed_ms:.2f}ms exceeded 500ms!"
        daemon.close()

    def test_pyro_flood_latency_60fps(self):
        """Asserts pyro flood trigger-to-dispatch latency is strictly <500ms."""
        device = MockAndroidDevice()
        dispatcher = MockDeviceDispatcher(device)
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

        t_base = time.perf_counter_ns()
        dt_60_ns = int(round(1e9 / 60.0))

        for i in range(10):
            daemon.step(np.full((90, 160, 3), 50, dtype=np.uint8), timestamp_ns=t_base + i * dt_60_ns)

        flood_frame = np.full((90, 160, 3), 250, dtype=np.uint8)
        t_start = time.perf_counter()
        for j in range(3):
            step_res = daemon.step(flood_frame, timestamp_ns=t_base + (10 + j) * dt_60_ns)
        t_end = time.perf_counter()

        elapsed_ms = (t_end - t_start) * 1000.0

        assert daemon.current_regime == LightingRegime.FLOOD_PYRO
        assert elapsed_ms < 500.0, f"Flood latency {elapsed_ms:.2f}ms exceeded 500ms!"
        daemon.close()


class TestDecisionComputeBenchmark:
    """Tier 4: Sub-millisecond compute latency benchmarks and throughput verification."""

    def test_p99_compute_latency_under_1ms_contract(self):
        """
        Runs 600 frames through the detector + state machine and asserts:
        - P99 decision compute latency < 1.0ms
        - Mean compute latency < 0.6ms
        """
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
        sim = ConcertLightSimulator(fps=60.0, seed=555)
        frames = sim.generate_scenario_frames(ConcertScenario.SCENARIO_E_FULL_CONCERT_SET, duration_sec=10.0)

        for frame, ts_ns in frames:
            daemon.step(frame, timestamp_ns=ts_ns)

        telemetry = daemon.get_telemetry()
        assert telemetry.total_frames_processed == 600
        assert telemetry.p99_compute_latency_ms < 1.0, (
            f"Contract Breach: P99 compute latency {telemetry.p99_compute_latency_ms:.3f}ms >= 1.0ms"
        )
        assert telemetry.mean_compute_latency_ms < 0.6, (
            f"Mean compute latency {telemetry.mean_compute_latency_ms:.3f}ms exceeded expected 0.6ms"
        )
        daemon.assert_performance_contract(max_p99_compute_latency_ms=1.0)
        daemon.close()

    def test_offline_throughput_exceeds_1000_fps(self):
        """
        Benchmarks batch throughput across 1,000 frames.
        Asserts system processes > 1,000 FPS in offline batch mode.
        """
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
        sim = ConcertLightSimulator(fps=60.0, seed=999)
        test_frames = [
            sim.render_rgb_frame(ConcertScenario.SCENARIO_E_FULL_CONCERT_SET, t_sec=i * 0.016)
            for i in range(1000)
        ]

        t0 = time.perf_counter()
        for f in test_frames:
            daemon.step(f)
        t1 = time.perf_counter()

        total_sec = t1 - t0
        fps_achieved = 1000.0 / total_sec

        assert fps_achieved > 1000.0, (
            f"Throughput {fps_achieved:.1f} FPS is below required 1000.0 FPS target!"
        )
        daemon.close()

    def test_mock_dispatcher_latency_profile(self):
        """Verifies MockDeviceDispatcher executes touch sequences within UI animation timing."""
        device = MockAndroidDevice()
        dispatcher = MockDeviceDispatcher(device)

        preset = CameraPreset(
            iso=100,
            shutter_speed="1/500",
            regime=LightingRegime.LASER_SPIKE,
            reason="Laser burst",
        )

        t0 = time.perf_counter()
        res = dispatcher.dispatch_camera_preset(preset)
        t1 = time.perf_counter()

        elapsed_ms = (t1 - t0) * 1000.0
        assert res.success is True
        # Full preset sequence contains 4 UI actions with 90ms total deliberate inter-tap delays for Android UI animation
        assert elapsed_ms < 150.0, f"Mock dispatch overhead {elapsed_ms:.2f}ms exceeded 150ms!"

    def test_single_tap_raw_dispatcher_overhead(self):
        """Verifies raw single-tap dispatch overhead is <5ms."""
        device = MockAndroidDevice()
        dispatcher = MockDeviceDispatcher(device)

        t0 = time.perf_counter()
        success = dispatcher.dispatch_tap(686, 1267, delay_after_ms=0)
        t1 = time.perf_counter()

        elapsed_ms = (t1 - t0) * 1000.0
        assert success is True
        assert elapsed_ms < 5.0, f"Raw tap overhead {elapsed_ms:.2f}ms exceeded 5.0ms!"
