"""
tests/test_state_machine.py - Comprehensive Unit & Integration Tests for Milestone 3 (M3)

Tests:
1. StrobeFilter: Periodic pulse detection, frequency estimation (6-25 Hz), zero-crossing velocity analysis,
   autocorrelation peak analysis, sliding window variance tracking, cessation holdoff, reset.
2. ConcertStateMachine:
   - State tracking for all LightingRegimes (NORMAL, BLACKOUT, LASER_SPIKE, FLOOD_PYRO, STROBE_LOCK)
   - Dual-threshold hysteresis for Blackout, Laser Spike, and Flood/Pyro
   - 350ms minimum dwell window for standard transitions
   - Emergency single-frame laser bypass
   - Debounce governor & rate limiter (maximum 2.0 Hz actuation rate / 500ms cooldown)
   - Anti-chatter stability under noisy boundary conditions
   - CameraPreset mapping accuracy and custom preset overrides
   - Matrix transitions between all regimes
   - End-to-end integration with LightDetectorEngine
"""

from __future__ import annotations

import numpy as np
import pytest

from s26_controller.core.dispatcher import LightingRegime, CameraPreset
from s26_controller.core.metrics import FrameMetrics
from s26_controller.core.strobe_filter import StrobeFilter, StrobeMetrics
from s26_controller.core.state_machine import (
    ConcertStateMachine,
    StateMachineConfig,
    DEFAULT_CAMERA_PRESETS,
)
from s26_controller.core.detector import LightDetectorEngine


def make_frame_metrics(
    timestamp_ns: int,
    mean_luma: float = 120.0,
    p10: float = 50.0,
    p50: float = 110.0,
    p90: float = 180.0,
    p99: float = 210.0,
    c_high: float = 0.01,
    c_dark: float = 0.05,
    zone_lumas: dict[str, float] | None = None,
    luma_velocity: float = 0.0,
) -> FrameMetrics:
    """Helper to synthesize FrameMetrics with realistic defaults."""
    if zone_lumas is None:
        zone_lumas = {
            "ceiling": mean_luma,
            "stage_center": mean_luma,
            "stage_flanks": mean_luma,
            "crowd_floor": mean_luma,
        }
    return FrameMetrics(
        timestamp_ns=timestamp_ns,
        mean_luma=mean_luma,
        p10=p10,
        p50=p50,
        p90=p90,
        p99=p99,
        c_high=c_high,
        c_dark=c_dark,
        zone_lumas=zone_lumas,
        luma_velocity=luma_velocity,
    )


def generate_strobe_series(
    frequency_hz: float,
    num_frames: int = 60,
    fps: float = 60.0,
    high_luma: float = 250.0,
    low_luma: float = 15.0,
    start_time_ns: int = 0,
) -> list[FrameMetrics]:
    """Generates a synthetic periodic square-wave strobe frame sequence."""
    dt_ns = int((1.0 / fps) * 1e9)
    metrics_list = []
    period_sec = 1.0 / frequency_hz

    for i in range(num_frames):
        t_sec = i / fps
        phase = (t_sec % period_sec) / period_sec
        is_pulse_high = phase < 0.35
        luma = high_luma if is_pulse_high else low_luma
        p99 = 255.0 if is_pulse_high else 40.0
        c_h = 0.30 if is_pulse_high else 0.0
        c_d = 0.0 if is_pulse_high else 0.80

        m = make_frame_metrics(
            timestamp_ns=start_time_ns + i * dt_ns,
            mean_luma=luma,
            p99=p99,
            c_high=c_h,
            c_dark=c_d,
            zone_lumas={
                "ceiling": luma,
                "stage_center": luma,
                "stage_flanks": luma,
                "crowd_floor": luma * 0.5,
            },
        )
        metrics_list.append(m)

    return metrics_list


# ============================================================================
# 1. StrobeFilter Unit Tests
# ============================================================================

class TestStrobeFilter:
    def test_strobe_filter_initialization(self):
        filter_ = StrobeFilter(min_frequency_hz=6.0, max_frequency_hz=25.0)
        assert filter_.min_frequency_hz == 6.0
        assert filter_.max_frequency_hz == 25.0
        assert filter_.is_active is False
        assert filter_.current_frequency_hz == 0.0

    def test_invalid_strobe_filter_parameters(self):
        with pytest.raises(ValueError):
            StrobeFilter(min_frequency_hz=30.0, max_frequency_hz=10.0)
        with pytest.raises(ValueError):
            StrobeFilter(min_frequency_hz=-5.0, max_frequency_hz=20.0)
        with pytest.raises(ValueError):
            StrobeFilter(window_size=8)

    def test_strobe_detection_8hz(self):
        filter_ = StrobeFilter(fps=60.0)
        frames = generate_strobe_series(frequency_hz=8.0, num_frames=60, fps=60.0)
        for m in frames:
            filter_.process(m)
        assert filter_.is_active is True
        assert 6.5 <= filter_.current_frequency_hz <= 10.0

    def test_strobe_detection_10hz(self):
        filter_ = StrobeFilter(fps=60.0)
        frames = generate_strobe_series(frequency_hz=10.0, num_frames=60, fps=60.0)

        active_detected = False
        detected_freq = 0.0
        for m in frames:
            res = filter_.process(m)
            if res.is_strobe:
                active_detected = True
                detected_freq = res.frequency_hz

        assert active_detected, "10Hz strobe was not detected by StrobeFilter"
        assert 8.0 <= detected_freq <= 12.0, f"Expected ~10Hz, got {detected_freq:.2f}Hz"
        assert filter_.is_active is True

    def test_strobe_detection_15hz(self):
        filter_ = StrobeFilter(fps=60.0)
        frames = generate_strobe_series(frequency_hz=15.0, num_frames=60, fps=60.0)

        active_detected = False
        for m in frames:
            if filter_.is_strobe_train_active(m):
                active_detected = True

        assert active_detected, "15Hz strobe was not detected"
        assert 13.0 <= filter_.current_frequency_hz <= 17.5

    def test_strobe_detection_20hz(self):
        filter_ = StrobeFilter(fps=60.0)
        frames = generate_strobe_series(frequency_hz=20.0, num_frames=60, fps=60.0)

        active_detected = False
        for m in frames:
            if filter_.is_strobe_train_active(m):
                active_detected = True

        assert active_detected, "20Hz strobe was not detected"
        assert 17.0 <= filter_.current_frequency_hz <= 23.0

    def test_strobe_detection_24hz(self):
        filter_ = StrobeFilter(fps=60.0)
        frames = generate_strobe_series(frequency_hz=24.0, num_frames=60, fps=60.0)
        for m in frames:
            filter_.process(m)
        assert filter_.is_active is True
        assert 20.0 <= filter_.current_frequency_hz <= 26.0

    def test_out_of_range_low_frequency_rejection(self):
        # 3 Hz is below the 6-25 Hz strobe range
        filter_ = StrobeFilter(min_frequency_hz=6.0, fps=60.0)
        frames = generate_strobe_series(frequency_hz=3.0, num_frames=60, fps=60.0)
        for m in frames:
            res = filter_.process(m)
        assert filter_.is_active is False

    def test_out_of_range_high_frequency_rejection(self):
        # 35 Hz is above the 25 Hz max frequency range (tested at 120fps to avoid 60fps Nyquist aliasing)
        filter_ = StrobeFilter(max_frequency_hz=25.0, fps=120.0)
        frames = generate_strobe_series(frequency_hz=35.0, num_frames=120, fps=120.0)
        for m in frames:
            res = filter_.process(m)
        assert filter_.is_active is False


    def test_non_strobe_constant_light(self):
        filter_ = StrobeFilter(fps=60.0)
        dt_ns = int((1.0 / 60.0) * 1e9)
        for i in range(60):
            m = make_frame_metrics(timestamp_ns=i * dt_ns, mean_luma=120.0)
            res = filter_.process(m)
            assert res.is_strobe is False
        assert filter_.is_active is False

    def test_non_strobe_slow_ramp(self):
        filter_ = StrobeFilter(fps=60.0)
        dt_ns = int((1.0 / 60.0) * 1e9)
        for i in range(60):
            m = make_frame_metrics(timestamp_ns=i * dt_ns, mean_luma=float(i * 3))
            res = filter_.process(m)
            assert res.is_strobe is False

    def test_non_strobe_low_amplitude_noise(self):
        filter_ = StrobeFilter(fps=60.0, min_amplitude=50.0)
        dt_ns = int((1.0 / 60.0) * 1e9)
        rng = np.random.default_rng(42)
        for i in range(60):
            jitter = float(rng.uniform(-10.0, 10.0))
            m = make_frame_metrics(timestamp_ns=i * dt_ns, mean_luma=100.0 + jitter)
            res = filter_.process(m)
            assert res.is_strobe is False

    def test_cessation_holdoff_window(self):
        filter_ = StrobeFilter(fps=60.0, cessation_holdoff_ms=400.0)
        frames = generate_strobe_series(frequency_hz=10.0, num_frames=40, fps=60.0)
        for m in frames:
            filter_.process(m)

        assert filter_.is_active is True
        last_t = frames[-1].timestamp_ns

        # 200ms after strobe stops (within 400ms holdoff) -> still active
        m_200ms = make_frame_metrics(timestamp_ns=last_t + int(0.200 * 1e9), mean_luma=15.0)
        res_200ms = filter_.process(m_200ms)
        assert res_200ms.is_strobe is True

        # 500ms after strobe stops (> 400ms holdoff) -> becomes inactive
        m_500ms = make_frame_metrics(timestamp_ns=last_t + int(0.500 * 1e9), mean_luma=15.0)
        res_500ms = filter_.process(m_500ms)
        assert res_500ms.is_strobe is False
        assert filter_.is_active is False

    def test_strobe_filter_reset(self):
        filter_ = StrobeFilter(fps=60.0)
        frames = generate_strobe_series(frequency_hz=10.0, num_frames=40, fps=60.0)
        for m in frames:
            filter_.process(m)
        assert filter_.is_active is True

        filter_.reset()
        assert filter_.is_active is False
        assert filter_.current_frequency_hz == 0.0

    def test_autocorrelation_computation(self):
        sig = np.array([250, 250, 10, 10, 250, 250, 10, 10, 250, 250, 10, 10], dtype=np.float32)
        r, peak_val, peak_lag = StrobeFilter.compute_autocorrelation(sig)
        assert len(r) == len(sig)
        assert peak_lag == 4
        assert peak_val > 0.5


# ============================================================================
# 2. ConcertStateMachine Blackout Hysteresis Tests
# ============================================================================

class TestBlackoutHysteresis:
    def test_blackout_entry_requires_persistence(self):
        sm = ConcertStateMachine()
        assert sm.current_regime == LightingRegime.NORMAL

        dt_ns = int((1.0 / 60.0) * 1e9)
        # Frame 1 of blackout: mean_luma < 8.0, c_dark >= 0.85
        m1 = make_frame_metrics(timestamp_ns=1 * dt_ns, mean_luma=3.0, c_dark=0.95)
        triggered1, preset1, reason1 = sm.process_frame(m1)
        assert triggered1 is False
        assert sm.current_regime == LightingRegime.NORMAL
        assert sm.blackout_persist_count == 1

        # Frame 2 of blackout: persistence condition (>=2) met
        m2 = make_frame_metrics(timestamp_ns=2 * dt_ns, mean_luma=3.0, c_dark=0.95)
        triggered2, preset2, reason2 = sm.process_frame(m2)
        assert triggered2 is True
        assert sm.current_regime == LightingRegime.BLACKOUT
        assert preset2 is not None
        assert preset2.iso == 200
        assert preset2.shutter_speed == "1/60"
        assert preset2.regime == LightingRegime.BLACKOUT

    def test_blackout_hysteresis_gap_stability(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # Transition into blackout
        sm.process_frame(make_frame_metrics(timestamp_ns=1 * dt_ns, mean_luma=3.0, c_dark=0.95))
        sm.process_frame(make_frame_metrics(timestamp_ns=2 * dt_ns, mean_luma=3.0, c_dark=0.95))
        assert sm.current_regime == LightingRegime.BLACKOUT

        # Fluctuate inside hysteresis gap (Y_mean in [8.0, 24.0])
        test_lumas = [9.0, 12.0, 15.0, 18.0, 22.0, 24.5]
        for idx, luma in enumerate(test_lumas):
            t = (10 + idx) * dt_ns
            m = make_frame_metrics(timestamp_ns=t, mean_luma=luma, c_dark=0.60)
            trig, preset, reason = sm.process_frame(m)
            assert trig is False, f"Premature trigger at luma {luma}"
            assert sm.current_regime == LightingRegime.BLACKOUT, f"Premature exit at luma {luma}"

        # Exit hysteresis when Y_mean >= 25.0 (after 350ms dwell & 500ms cooldown)
        exit_t_ns = int(0.600 * 1e9)
        m_exit = make_frame_metrics(timestamp_ns=exit_t_ns, mean_luma=30.0, c_dark=0.20)
        trig_exit, preset_exit, reason_exit = sm.process_frame(m_exit)
        assert trig_exit is True
        assert sm.current_regime == LightingRegime.NORMAL
        assert preset_exit is not None
        assert preset_exit.iso == 400

    def test_transient_single_frame_blackout_does_not_trigger(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # Frame 1: Transient dip
        m1 = make_frame_metrics(timestamp_ns=1 * dt_ns, mean_luma=2.0, c_dark=0.99)
        trig1, _, _ = sm.process_frame(m1)
        assert trig1 is False

        # Frame 2: Recovers immediately to normal stage
        m2 = make_frame_metrics(timestamp_ns=2 * dt_ns, mean_luma=120.0, c_dark=0.05)
        trig2, _, _ = sm.process_frame(m2)
        assert trig2 is False
        assert sm.current_regime == LightingRegime.NORMAL
        assert sm.blackout_persist_count == 0


# ============================================================================
# 3. Laser Spike & Emergency Single-Frame Bypass Tests
# ============================================================================

class TestLaserSpikeDetection:
    def test_standard_laser_entry_and_exit_hysteresis(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # Frame 1: Laser candidate (P99 >= 250, c_high >= 0.04, mean_luma < 195.0)
        m1 = make_frame_metrics(
            timestamp_ns=1 * dt_ns,
            mean_luma=50.0,
            p99=252.0,
            c_high=0.05,
            zone_lumas={"ceiling": 230.0, "stage_center": 60.0, "stage_flanks": 40.0, "crowd_floor": 20.0},
        )
        trig1, preset1, _ = sm.process_frame(m1)
        assert trig1 is False
        assert sm.current_regime == LightingRegime.NORMAL

        # Frame 2: Persistence met
        m2 = make_frame_metrics(
            timestamp_ns=2 * dt_ns,
            mean_luma=50.0,
            p99=252.0,
            c_high=0.05,
            zone_lumas={"ceiling": 230.0, "stage_center": 60.0, "stage_flanks": 40.0, "crowd_floor": 20.0},
        )
        trig2, preset2, _ = sm.process_frame(m2)
        assert trig2 is True
        assert sm.current_regime == LightingRegime.LASER_SPIKE
        assert preset2 is not None
        assert preset2.iso == 100
        assert preset2.shutter_speed == "1/250"

        # In Laser Spike: P99 drops to 230 -> Hysteresis keeps state in LASER_SPIKE
        m3 = make_frame_metrics(timestamp_ns=30 * dt_ns, mean_luma=40.0, p99=230.0, c_high=0.02)
        trig3, _, _ = sm.process_frame(m3)
        assert trig3 is False
        assert sm.current_regime == LightingRegime.LASER_SPIKE

        # Laser exit: P99 <= 200 and c_high <= 0.01 after dwell/cooldown
        m_exit = make_frame_metrics(
            timestamp_ns=int(0.600 * 1e9),
            mean_luma=80.0,
            p99=170.0,
            c_high=0.005,
        )
        trig_exit, preset_exit, _ = sm.process_frame(m_exit)
        assert trig_exit is True
        assert sm.current_regime == LightingRegime.NORMAL
        assert preset_exit.iso == 400

    def test_stage_center_laser_detection(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # Stage center blast
        m1 = make_frame_metrics(
            timestamp_ns=1 * dt_ns,
            mean_luma=70.0,
            p99=253.0,
            c_high=0.04,
            zone_lumas={"ceiling": 30.0, "stage_center": 253.0, "stage_flanks": 50.0, "crowd_floor": 20.0},
        )
        m2 = make_frame_metrics(
            timestamp_ns=2 * dt_ns,
            mean_luma=70.0,
            p99=253.0,
            c_high=0.04,
            zone_lumas={"ceiling": 30.0, "stage_center": 253.0, "stage_flanks": 50.0, "crowd_floor": 20.0},
        )
        sm.process_frame(m1)
        trig, preset, _ = sm.process_frame(m2)
        assert trig is True
        assert sm.current_regime == LightingRegime.LASER_SPIKE

    def test_emergency_single_frame_laser_bypass(self):
        sm = ConcertStateMachine()
        # Even on the very first frame, an intense direct laser hit triggers immediately
        m_emergency = make_frame_metrics(
            timestamp_ns=int(0.016 * 1e9),
            mean_luma=80.0,
            p99=255.0,
            c_high=0.15,
        )
        trig, preset, reason = sm.process_frame(m_emergency)
        assert trig is True, "Emergency laser did not bypass single-frame check"
        assert sm.current_regime == LightingRegime.LASER_SPIKE
        assert preset.iso == 100
        assert "EMERGENCY" in reason

    def test_emergency_laser_bypasses_recent_dwell(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # 1. Enter Blackout at t = 33ms
        sm.process_frame(make_frame_metrics(timestamp_ns=1 * dt_ns, mean_luma=2.0, c_dark=0.98))
        sm.process_frame(make_frame_metrics(timestamp_ns=2 * dt_ns, mean_luma=2.0, c_dark=0.98))
        assert sm.current_regime == LightingRegime.BLACKOUT

        # 2. Only 50ms later (dwell window is 350ms), a direct blinding laser strike occurs
        t_blast = int(2 * dt_ns + 0.050 * 1e9)
        m_blast = make_frame_metrics(
            timestamp_ns=t_blast,
            mean_luma=120.0,
            p99=255.0,
            c_high=0.18,
        )
        trig, preset, reason = sm.process_frame(m_blast)
        assert trig is True, "Emergency laser failed to override dwell holdoff"
        assert sm.current_regime == LightingRegime.LASER_SPIKE
        assert preset.iso == 100


# ============================================================================
# 4. Strobe Lock & Anti-Hunting Tests
# ============================================================================

class TestStrobeLockIntegration:
    def test_strobe_train_freezes_exposure(self):
        sm = ConcertStateMachine()
        strobe_frames = generate_strobe_series(frequency_hz=12.0, num_frames=60, fps=60.0)

        dispatched_count = 0
        for m in strobe_frames:
            trig, preset, _ = sm.process_frame(m)
            if trig:
                dispatched_count += 1

        # Once strobe lock is active, exposure is frozen and NO continuous slider movements occur
        assert sm.current_regime == LightingRegime.STROBE_LOCK
        # Dispatches must be at most 1 (the initial entry before filter lock) or 0
        assert dispatched_count <= 1

    def test_strobe_lock_recovery_to_normal(self):
        sm = ConcertStateMachine()
        strobe_frames = generate_strobe_series(frequency_hz=12.0, num_frames=40, fps=60.0)
        for m in strobe_frames:
            sm.process_frame(m)

        assert sm.current_regime == LightingRegime.STROBE_LOCK
        last_t = strobe_frames[-1].timestamp_ns

        # 500ms after strobe stops (> 400ms holdoff), scene is steady normal stage
        post_strobe_t = last_t + int(0.500 * 1e9)
        m_normal = make_frame_metrics(
            timestamp_ns=post_strobe_t,
            mean_luma=120.0,
            p99=190.0,
            c_high=0.01,
            c_dark=0.05,
        )
        trig, preset, reason = sm.process_frame(m_normal)
        assert sm.current_regime == LightingRegime.NORMAL
        assert trig is True
        assert preset.regime == LightingRegime.NORMAL


# ============================================================================
# 5. Debounce Governor & Dwell Timing Tests
# ============================================================================

class TestDebounceAndDwell:
    def test_rate_limiter_suppresses_rapid_triggers(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # 1. Trigger transition to Blackout at t = 0
        sm.process_frame(make_frame_metrics(timestamp_ns=0, mean_luma=2.0, c_dark=0.98))
        trig1, preset1, _ = sm.process_frame(make_frame_metrics(timestamp_ns=dt_ns, mean_luma=2.0, c_dark=0.98))
        assert trig1 is True
        assert sm.current_regime == LightingRegime.BLACKOUT

        # 2. Attempt standard transition at t = 200ms (< 350ms dwell and < 500ms cooldown)
        t_200ms = int(0.200 * 1e9)
        m_200ms_1 = make_frame_metrics(timestamp_ns=t_200ms, mean_luma=120.0, c_dark=0.05)
        m_200ms_2 = make_frame_metrics(timestamp_ns=t_200ms + dt_ns, mean_luma=120.0, c_dark=0.05)
        sm.process_frame(m_200ms_1)
        trig_early, preset_early, reason_early = sm.process_frame(m_200ms_2)
        assert trig_early is False
        assert preset_early is None
        assert "deferred" in reason_early

        # 3. Attempt at t = 600ms (> 350ms dwell and > 500ms cooldown)
        t_600ms = int(0.600 * 1e9)
        m_600ms = make_frame_metrics(timestamp_ns=t_600ms, mean_luma=120.0, c_dark=0.05)
        trig_ok, preset_ok, _ = sm.process_frame(m_600ms)
        assert trig_ok is True
        assert sm.current_regime == LightingRegime.NORMAL
        assert preset_ok.iso == 400

    def test_maximum_actuation_rate_under_2hz(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)
        dispatches = 0

        for frame_idx in range(120):
            t = frame_idx * dt_ns
            is_dark = (frame_idx // 6) % 2 == 0
            luma = 2.0 if is_dark else 150.0
            cd = 0.98 if is_dark else 0.02

            m = make_frame_metrics(timestamp_ns=t, mean_luma=luma, c_dark=cd)
            trig, _, _ = sm.process_frame(m)
            if trig:
                dispatches += 1

        # Over 2.0 seconds with a 500ms cooldown (2.0 Hz cap), max dispatches is <= 4
        assert dispatches <= 4, f"Rate limiter failed: dispatched {dispatches} times in 2.0s"


# ============================================================================
# 6. Anti-Chatter Stability Under Boundary Noise Tests
# ============================================================================

class TestAntiChatterStability:
    def test_boundary_noise_anti_chatter(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # Feed 60 frames fluctuating right around the blackout threshold (7.8 to 8.2)
        rng = np.random.default_rng(123)
        dispatches = 0
        for i in range(60):
            luma = float(rng.uniform(7.8, 8.2))
            cd = 0.86 if luma < 8.0 else 0.80
            m = make_frame_metrics(timestamp_ns=i * dt_ns, mean_luma=luma, c_dark=cd)
            trig, _, _ = sm.process_frame(m)
            if trig:
                dispatches += 1

        # Hysteresis and persistence prevent chatter -> at most 1 dispatch occurred
        assert dispatches <= 1

    def test_laser_boundary_noise_anti_chatter(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # Fluctuating near laser threshold (P99 between 248 and 252)
        rng = np.random.default_rng(456)
        dispatches = 0
        for i in range(60):
            p99 = float(rng.uniform(248.0, 252.0))
            ch = 0.045 if p99 >= 250.0 else 0.035
            m = make_frame_metrics(timestamp_ns=i * dt_ns, mean_luma=60.0, p99=p99, c_high=ch)
            trig, _, _ = sm.process_frame(m)
            if trig:
                dispatches += 1

        assert dispatches <= 1


# ============================================================================
# 7. Full Arena Flood / Pyro Wash Tests
# ============================================================================

class TestFloodPyroWash:
    def test_flood_wash_entry_and_exit(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # Flood Wash: mean_luma >= 195.0, c_high >= 0.40
        m1 = make_frame_metrics(timestamp_ns=1 * dt_ns, mean_luma=210.0, c_high=0.55)
        m2 = make_frame_metrics(timestamp_ns=2 * dt_ns, mean_luma=210.0, c_high=0.55)
        sm.process_frame(m1)
        trig, preset, _ = sm.process_frame(m2)

        assert trig is True
        assert sm.current_regime == LightingRegime.FLOOD_PYRO
        assert preset is not None
        assert preset.iso == 100
        assert preset.shutter_speed == "1/125"

        # Exit flood when mean_luma <= 140.0
        m_exit = make_frame_metrics(
            timestamp_ns=int(0.600 * 1e9),
            mean_luma=110.0,
            c_high=0.05,
        )
        trig_exit, preset_exit, _ = sm.process_frame(m_exit)
        assert trig_exit is True
        assert sm.current_regime == LightingRegime.NORMAL


# ============================================================================
# 8. CameraPreset Mapping & State Machine Config Tests
# ============================================================================

class TestPresetMappingAndConfig:
    def test_default_preset_mapping(self):
        sm = ConcertStateMachine()
        p_norm = sm.get_preset_for_regime(LightingRegime.NORMAL)
        assert p_norm.iso == 400
        assert p_norm.shutter_speed == "1/60"

        p_blackout = sm.get_preset_for_regime(LightingRegime.BLACKOUT)
        assert p_blackout.iso == 200
        assert p_blackout.shutter_speed == "1/60"


        p_laser = sm.get_preset_for_regime(LightingRegime.LASER_SPIKE)
        assert p_laser.iso == 100
        assert p_laser.shutter_speed == "1/250"

        p_flood = sm.get_preset_for_regime(LightingRegime.FLOOD_PYRO)
        assert p_flood.iso == 100
        assert p_flood.shutter_speed == "1/125"

    def test_custom_preset_overrides(self):
        custom_presets = {
            LightingRegime.NORMAL: CameraPreset(iso=400, shutter_speed="1/60", regime=LightingRegime.NORMAL, reason="Custom"),
            LightingRegime.BLACKOUT: CameraPreset(iso=200, shutter_speed="1/60", regime=LightingRegime.BLACKOUT, reason="Custom"),
            LightingRegime.LASER_SPIKE: CameraPreset(iso=50, shutter_speed="1/500", regime=LightingRegime.LASER_SPIKE, reason="Custom"),
            LightingRegime.FLOOD_PYRO: CameraPreset(iso=50, shutter_speed="1/250", regime=LightingRegime.FLOOD_PYRO, reason="Custom"),
            LightingRegime.STROBE_LOCK: CameraPreset(iso=400, shutter_speed="1/60", regime=LightingRegime.STROBE_LOCK, reason="Custom"),
        }
        sm = ConcertStateMachine(presets=custom_presets)
        assert sm.get_preset_for_regime(LightingRegime.LASER_SPIKE).iso == 50
        assert sm.get_preset_for_regime(LightingRegime.LASER_SPIKE).shutter_speed == "1/500"

    def test_state_machine_reset(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)
        sm.process_frame(make_frame_metrics(timestamp_ns=1 * dt_ns, mean_luma=2.0, c_dark=0.98))
        sm.process_frame(make_frame_metrics(timestamp_ns=2 * dt_ns, mean_luma=2.0, c_dark=0.98))
        assert sm.current_regime == LightingRegime.BLACKOUT

        sm.reset()
        assert sm.current_regime == LightingRegime.NORMAL
        assert sm.total_frames_processed == 0
        assert sm.total_dispatches == 0


# ============================================================================
# 9. Regime Cross-Transition Matrix Tests
# ============================================================================

class TestRegimeMatrixTransitions:
    def test_blackout_to_laser_override(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # 1. In blackout
        sm.process_frame(make_frame_metrics(timestamp_ns=1 * dt_ns, mean_luma=2.0, c_dark=0.98))
        sm.process_frame(make_frame_metrics(timestamp_ns=2 * dt_ns, mean_luma=2.0, c_dark=0.98))
        assert sm.current_regime == LightingRegime.BLACKOUT

        # 2. Laser burst cuts through blackout after 550ms cooldown
        t_laser = int(0.600 * 1e9)
        m1 = make_frame_metrics(timestamp_ns=t_laser, mean_luma=40.0, p99=252.0, c_high=0.06)
        m2 = make_frame_metrics(timestamp_ns=t_laser + dt_ns, mean_luma=40.0, p99=252.0, c_high=0.06)
        sm.process_frame(m1)
        trig, preset, _ = sm.process_frame(m2)

        assert trig is True
        assert sm.current_regime == LightingRegime.LASER_SPIKE
        assert preset.iso == 100

    def test_blackout_to_pyro_flood_override(self):
        sm = ConcertStateMachine()
        dt_ns = int((1.0 / 60.0) * 1e9)

        # 1. In blackout
        sm.process_frame(make_frame_metrics(timestamp_ns=1 * dt_ns, mean_luma=2.0, c_dark=0.98))
        sm.process_frame(make_frame_metrics(timestamp_ns=2 * dt_ns, mean_luma=2.0, c_dark=0.98))

        # 2. Pyro explosion after drop (2 consecutive frames for flood persistence)
        t_pyro = int(0.600 * 1e9)
        m_pyro_1 = make_frame_metrics(timestamp_ns=t_pyro, mean_luma=230.0, c_high=0.70)
        m_pyro_2 = make_frame_metrics(timestamp_ns=t_pyro + dt_ns, mean_luma=230.0, c_high=0.70)
        sm.process_frame(m_pyro_1)
        trig, preset, _ = sm.process_frame(m_pyro_2)

        assert trig is True
        assert sm.current_regime == LightingRegime.FLOOD_PYRO
        assert preset.iso == 100



# ============================================================================
# 10. End-to-End Detector -> StateMachine Integration Test
# ============================================================================

class TestDetectorStateMachineIntegration:
    def test_detector_to_state_machine_e2e_blackout(self, blackout_frame_rgb):
        detector = LightDetectorEngine()
        sm = ConcertStateMachine()

        dt_ns = int((1.0 / 60.0) * 1e9)
        m1 = detector.analyze_frame_rgb(blackout_frame_rgb, timestamp_ns=1 * dt_ns)
        trig1, _, _ = sm.process_frame(m1)
        assert trig1 is False

        m2 = detector.analyze_frame_rgb(blackout_frame_rgb, timestamp_ns=2 * dt_ns)
        trig2, preset2, _ = sm.process_frame(m2)
        assert trig2 is True
        assert sm.current_regime == LightingRegime.BLACKOUT
        assert preset2.iso == 200

    def test_detector_to_state_machine_e2e_laser(self, laser_spot_frame_rgb):
        detector = LightDetectorEngine()
        sm = ConcertStateMachine()

        dt_ns = int((1.0 / 60.0) * 1e9)
        m1 = detector.analyze_frame_rgb(laser_spot_frame_rgb, timestamp_ns=1 * dt_ns)
        trig, preset, _ = sm.process_frame(m1)

        assert sm.current_regime == LightingRegime.LASER_SPIKE
        assert trig is True
        assert preset.iso == 100

    def test_detector_to_state_machine_e2e_flood(self, floodlight_frame_rgb):
        detector = LightDetectorEngine()
        sm = ConcertStateMachine()

        dt_ns = int((1.0 / 60.0) * 1e9)
        m1 = detector.analyze_frame_rgb(floodlight_frame_rgb, timestamp_ns=1 * dt_ns)
        sm.process_frame(m1)
        m2 = detector.analyze_frame_rgb(floodlight_frame_rgb, timestamp_ns=2 * dt_ns)
        trig, preset, _ = sm.process_frame(m2)

        assert sm.current_regime == LightingRegime.FLOOD_PYRO
        assert trig is True
        assert preset.iso == 100
        assert preset.shutter_speed == "1/125"
