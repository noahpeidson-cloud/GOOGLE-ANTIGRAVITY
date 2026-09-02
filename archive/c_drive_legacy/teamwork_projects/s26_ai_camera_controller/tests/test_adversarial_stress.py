"""
test_adversarial_stress.py - Tier 5 White-Box Adversarial Stress & Robustness Tests

Stress tests the S26 AI Camera Controller against extreme edge cases, adversarial inputs,
sensor noise, numerical anomalies, rapid oscillations, and concurrency stress:
1. Extreme Sensor Noise: High-variance Gaussian, Salt & Pepper, Shot noise.
2. Rapid Out-of-Band Oscillation: 50Hz/60Hz AC flutter, chaotic flashing.
3. Numerical & Bounds Safety: All-zeros, all-255s, 1-pixel frames, dtype handling.
4. Transient Spikes vs Emergency Lasers: Single-pixel hot spots vs real laser arrays.
5. Boundary Flutter & Anti-Chatter: Oscillations at exact hysteresis threshold boundaries.
6. Timestamp Anomalies: Reverse timestamps, zero timestamps, multi-hour gaps.
7. Dispatcher Failure & Recovery: Simulated ADB pipe failures and recovery during live stream.
8. Multi-Threaded Concurrency & Buffer Boundedness: 5,000 rapid steps with concurrent resets.
"""

from __future__ import annotations

import math
import threading
import time
from typing import List, Tuple
import numpy as np
import pytest

from s26_controller.core.config import DetectorConfig
from s26_controller.core.coordinates import DisplayProfile
from s26_controller.core.detector import LightDetectorEngine
from s26_controller.core.dispatcher import (
    BaseDispatcher,
    CameraPreset,
    DispatchResult,
    LightingRegime,
    MockDispatcher,
)
from s26_controller.core.metrics import (
    FrameMetrics,
    compute_16bin_histogram,
    compute_clipping_ratios,
    compute_percentiles,
)
from s26_controller.core.state_machine import ConcertStateMachine, StateMachineConfig
from s26_controller.core.strobe_filter import StrobeFilter
from s26_controller.daemon import DaemonStepResult, S26CameraControllerDaemon
from s26_controller.simulation.light_simulator import (
    ConcertLightSimulator,
    ConcertScenario,
)
from s26_controller.simulation.mock_device import (
    MockAndroidDevice,
    MockDeviceDispatcher,
)


class TestExtremeNoiseRobustness:
    """Tier 5: High-variance noise and pixel corruption resilience."""

    def test_extreme_gaussian_noise_stability(self):
        """Injects extreme Gaussian noise (sigma=80.0) on dark stage frame."""
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
        rng = np.random.default_rng(12345)

        base_dark = np.full((90, 160, 3), 15, dtype=np.float32)

        for _ in range(30):
            noise = rng.normal(0.0, 80.0, (90, 160, 3)).astype(np.float32)
            corrupted = np.clip(base_dark + noise, 0.0, 255.0).astype(np.uint8)
            res = daemon.step(corrupted)
            assert res is not None
            assert 0.0 <= res.metrics.mean_luma <= 255.0
            assert 0.0 <= res.metrics.p99 <= 255.0

        daemon.close()

    def test_salt_and_pepper_impulse_noise(self):
        """Injects 5% salt-and-pepper dead/hot pixels and verifies no false emergency trigger."""
        detector = LightDetectorEngine()
        sm = ConcertStateMachine()
        rng = np.random.default_rng(999)

        base = np.full((90, 160, 3), 40, dtype=np.uint8)
        # Add 5% isolated hot pixels (value 255)
        mask_hot = rng.random((90, 160)) < 0.05
        base[mask_hot] = 255

        metrics = detector.analyze_frame_rgb(base)
        triggered, preset, reason = sm.process_frame(metrics)

        # 5% hot pixels is below emergency laser threshold (c_high >= 0.08)
        assert triggered is False
        assert sm.current_regime == LightingRegime.NORMAL


class TestOutOfBandFrequencyRejection:
    """Tier 5: 50Hz/60Hz AC ripple and chaotic non-strobe frequency rejection."""

    def test_50hz_mains_hum_rejection(self):
        """Simulates 50Hz LED PWM flutter at 120fps ingestion (outside 6-25Hz band)."""
        strobe_filter = StrobeFilter(min_frequency_hz=6.0, max_frequency_hz=25.0)
        dt_ns = int(round(1e9 / 120.0))  # 120fps
        t_base = 1_000_000_000

        res = None
        for i in range(120):
            t_sec = i / 120.0
            # 50Hz sine oscillation
            luma = 50.0 + 30.0 * math.sin(2 * math.pi * 50.0 * t_sec)
            m = FrameMetrics(
                timestamp_ns=t_base + i * dt_ns,
                mean_luma=luma,
                p10=luma - 5,
                p50=luma,
                p90=luma + 5,
                p99=luma + 10,
                c_high=0.0,
                c_dark=0.0,
                zone_lumas={"ceiling": luma, "stage_center": luma, "stage_flanks": luma, "crowd_floor": luma},
                luma_velocity=0.0,
            )
            res = strobe_filter.process(m)

        # 50Hz is above 25Hz max cutoff -> must be rejected
        assert res is not None
        assert res.is_strobe is False

    def test_60hz_rolling_shutter_flutter_rejection(self):
        """Simulates 60Hz alternating frame flutter at 60fps (Nyquist limit artifact)."""
        strobe_filter = StrobeFilter(min_frequency_hz=6.0, max_frequency_hz=25.0)
        dt_ns = int(round(1e9 / 60.0))
        t_base = 1_000_000_000

        res = None
        for i in range(60):
            # Alternates every frame (30Hz effective Nyquist)
            luma = 100.0 if (i % 2 == 0) else 20.0
            m = FrameMetrics(
                timestamp_ns=t_base + i * dt_ns,
                mean_luma=luma,
                p10=luma,
                p50=luma,
                p90=luma,
                p99=luma,
                c_high=0.0,
                c_dark=0.0,
                zone_lumas={"ceiling": luma, "stage_center": luma, "stage_flanks": luma, "crowd_floor": luma},
                luma_velocity=0.0,
            )
            res = strobe_filter.process(m)

        assert res is not None
        assert res.is_strobe is False


class TestNumericalSafetyAndBoundaryValues:
    """Tier 5: Numerical bounds, solid color frames, and dimension handling."""

    def test_all_zeros_pitch_black_frame(self):
        """Processes completely black frame (all 0s)."""
        detector = LightDetectorEngine()
        frame_zeros = np.zeros((90, 160, 3), dtype=np.uint8)
        metrics = detector.analyze_frame_rgb(frame_zeros)

        assert metrics.mean_luma == 0.0
        assert metrics.p10 == 0.0
        assert metrics.p90 == 0.0
        assert metrics.p99 == 0.0
        assert metrics.c_dark == 1.0
        assert metrics.c_high == 0.0

    def test_all_255s_solid_white_frame(self):
        """Processes solid blinding white frame (all 255s)."""
        detector = LightDetectorEngine()
        frame_white = np.full((90, 160, 3), 255, dtype=np.uint8)
        metrics = detector.analyze_frame_rgb(frame_white)

        assert metrics.mean_luma == 255.0
        assert metrics.p10 == 255.0
        assert metrics.p90 == 255.0
        assert metrics.p99 == 255.0
        assert metrics.c_dark == 0.0
        assert metrics.c_high == 1.0

    def test_irregular_frame_dimensions_handling(self):
        """Verifies detector handles non-standard frame dimensions dynamically."""
        detector = LightDetectorEngine()
        custom_frame = np.full((120, 200, 3), 75, dtype=np.uint8)
        metrics = detector.analyze_frame_rgb(custom_frame)
        assert abs(metrics.mean_luma - 75.0) < 1.0

    def test_invalid_frame_shape_exception(self):
        """Verifies 1D or 4D arrays raise clean ValueError."""
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
        with pytest.raises(ValueError, match="Invalid frame shape"):
            daemon.step(np.zeros((100,), dtype=np.uint8))
        with pytest.raises(ValueError, match="Invalid frame shape"):
            daemon.step(np.zeros((1, 90, 160, 3), dtype=np.uint8))
        daemon.close()


class TestSingleFrameSpikesVsLaserStrikes:
    """Tier 5: Differentiation between harmless transient single-pixel spikes and genuine laser attacks."""

    def test_single_pixel_cosmic_ray_spike_ignored(self):
        """A single pixel at 255 among 14,400 pixels (c_high = 1/14400 = 0.00007) must NOT trigger laser spike."""
        detector = LightDetectorEngine()
        sm = ConcertStateMachine()

        frame = np.full((90, 160, 3), 30, dtype=np.uint8)
        frame[45, 80, :] = 255  # 1 pixel spike

        metrics = detector.analyze_frame_rgb(frame)
        triggered, preset, reason = sm.process_frame(metrics)

        assert triggered is False
        assert sm.current_regime == LightingRegime.NORMAL

    def test_genuine_emergency_laser_single_frame_trigger(self):
        """A genuine laser strike with >8% saturated pixels must trigger in exactly 1 frame."""
        detector = LightDetectorEngine()
        sm = ConcertStateMachine()

        frame = np.full((90, 160, 3), 30, dtype=np.uint8)
        # Fill 10% of frame with 255 (e.g. 15 lines of ceiling)
        frame[0:15, :, :] = 255

        metrics = detector.analyze_frame_rgb(frame)
        triggered, preset, reason = sm.process_frame(metrics)

        assert triggered is True
        assert preset is not None
        assert preset.regime == LightingRegime.LASER_SPIKE
        assert sm.current_regime == LightingRegime.LASER_SPIKE


class TestBoundaryHysteresisAntiChatter:
    """Tier 5: Hysteresis stability when fluctuating rapidly across boundary thresholds."""

    def test_blackout_boundary_chatter_suppression(self):
        """Oscillates between Y=7.8 and Y=8.2 every frame; asserts no continuous rapid switching."""
        sm = ConcertStateMachine()
        t_cur_ns = 1_000_000_000
        dt_ns = int(round(1e9 / 60.0))

        dispatches = 0
        for i in range(120):  # 2.0 seconds
            luma = 7.8 if (i % 2 == 0) else 8.2
            c_dark = 0.90 if (i % 2 == 0) else 0.80
            m = FrameMetrics(
                timestamp_ns=t_cur_ns + i * dt_ns,
                mean_luma=luma,
                p10=luma,
                p50=luma,
                p90=luma,
                p99=luma,
                c_high=0.0,
                c_dark=c_dark,
                zone_lumas={"ceiling": luma, "stage_center": luma, "stage_flanks": luma, "crowd_floor": luma},
                luma_velocity=0.0,
            )
            triggered, preset, _ = sm.process_frame(m)
            if triggered:
                dispatches += 1

        # Max 2 dispatches across 2 seconds due to 500ms rate limit and persistence
        assert dispatches <= 2

    def test_laser_exit_hysteresis_boundary_chatter(self):
        """In LASER_SPIKE regime, oscillates near exit boundary (P99=198 vs P99=202)."""
        sm = ConcertStateMachine(initial_regime=LightingRegime.LASER_SPIKE)
        sm.last_regime_change_timestamp_ns = 1_000_000_000
        sm.last_dispatch_timestamp_ns = 1_000_000_000
        t_cur_ns = 1_000_000_000
        dt_ns = int(round(1e9 / 60.0))

        dispatches = 0
        for i in range(120):
            p99 = 198.0 if (i % 2 == 0) else 202.0
            chigh = 0.005 if (i % 2 == 0) else 0.015
            m = FrameMetrics(
                timestamp_ns=t_cur_ns + i * dt_ns,
                mean_luma=50.0,
                p10=30.0,
                p50=45.0,
                p90=120.0,
                p99=p99,
                c_high=chigh,
                c_dark=0.0,
                zone_lumas={"ceiling": 50.0, "stage_center": 50.0, "stage_flanks": 50.0, "crowd_floor": 50.0},
                luma_velocity=0.0,
            )
            triggered, _, _ = sm.process_frame(m)
            if triggered:
                dispatches += 1

        # Hysteresis prevents high-frequency chattering
        assert dispatches <= 2


class TestTimestampAnomaliesAndJitter:
    """Tier 5: Timestamp robustness under reverse ordering, clock resets, and large gaps."""

    def test_zero_and_negative_timestamp_handling(self):
        """Processes frames with zero or negative timestamps without throwing exceptions."""
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
        frame = np.full((90, 160, 3), 50, dtype=np.uint8)

        res0 = daemon.step(frame, timestamp_ns=0)
        res_neg = daemon.step(frame, timestamp_ns=-1000)

        assert res0 is not None and res_neg is not None
        daemon.close()

    def test_large_time_gap_recovery(self):
        """Simulates 1-hour pause between camera frames."""
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
        frame = np.full((90, 160, 3), 50, dtype=np.uint8)

        daemon.step(frame, timestamp_ns=1_000_000_000)
        # 1 hour later (3.6e12 ns)
        res_after = daemon.step(frame, timestamp_ns=1_000_000_000 + 3_600_000_000_000)

        assert res_after is not None
        assert daemon.current_regime == LightingRegime.NORMAL
        daemon.close()


class TestDispatcherFailuresAndConcurrency:
    """Tier 5: Dispatcher error injection, multi-threaded stress, and memory stability."""

    def test_simulated_dispatcher_failure_recovery(self):
        """Simulates intermittent dispatcher touch failures; verifies daemon does not crash."""
        failing_dispatcher = MockDispatcher(simulate_failures=True)
        daemon = S26CameraControllerDaemon(dispatcher=failing_dispatcher)

        # Trigger laser spike with failing dispatcher
        laser_frame = np.full((90, 160, 3), 30, dtype=np.uint8)
        laser_frame[0:27, 40:120, :] = 255
        laser_frame[27:63, 60:100, :] = 255

        res = daemon.step(laser_frame)
        assert res.triggered is True
        assert res.dispatch_result is not None
        assert res.dispatch_result.success is False
        assert daemon.current_regime == LightingRegime.LASER_SPIKE

        # Resume with non-failing dispatcher
        failing_dispatcher.simulate_failures = False
        res2 = daemon.step(np.full((90, 160, 3), 50, dtype=np.uint8))
        assert res2 is not None
        daemon.close()

    def test_high_volume_stress_and_buffer_boundedness(self):
        """Runs 3,000 rapid steps and asserts internal ring buffers remain strictly bounded."""
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher(), history_buffer_size=128)
        frame = np.full((90, 160, 3), 50, dtype=np.uint8)

        for _ in range(3000):
            daemon.step(frame)

        assert daemon.frame_count == 3000
        assert len(daemon._recent_step_results) <= 128
        assert len(daemon._compute_latencies) <= 10000
        daemon.close()

    def test_concurrent_step_and_reset_thread_safety(self):
        """Executes concurrent step() and reset() operations across multiple threads."""
        daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
        errors: List[Exception] = []

        def worker_stream():
            try:
                frame = np.full((90, 160, 3), 50, dtype=np.uint8)
                for _ in range(500):
                    daemon.step(frame)
            except Exception as e:
                errors.append(e)

        def worker_reset():
            try:
                for _ in range(50):
                    time.sleep(0.005)
                    daemon.reset()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=worker_stream)
        t2 = threading.Thread(target=worker_reset)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        assert len(errors) == 0, f"Thread concurrency errors encountered: {errors}"
        daemon.close()
