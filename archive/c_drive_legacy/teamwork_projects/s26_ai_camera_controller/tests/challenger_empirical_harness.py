import sys
import time
import math
import numpy as np

from s26_controller.core.config import DetectorConfig
from s26_controller.core.coordinates import (
    DisplayProfile,
    DisplayResolution,
    CoordinateNormalizer,
    SamsungS26CoordinateMap,
    CameraParameter,
)
from s26_controller.core.detector import LightDetectorEngine
from s26_controller.core.dispatcher import (
    BaseDispatcher,
    CameraPreset,
    DispatchResult,
    LightingRegime,
    MockDispatcher,
    dispatch_preset,
)
from s26_controller.core.metrics import FrameMetrics
from s26_controller.core.state_machine import ConcertStateMachine, StateMachineConfig
from s26_controller.core.strobe_filter import StrobeFilter
from s26_controller.daemon import S26CameraControllerDaemon
from s26_controller.simulation.light_simulator import ConcertLightSimulator, ConcertScenario

def run_empirical_challenge():
    print(= * 80)
    print(CHALLENGER 2: ADVERSARIAL & EMPIRICAL STRESS TEST BATTERY)
    print(= * 80)
    
    passed_tests = 0
    total_tests = 0
    
    # -------------------------------------------------------------------------
    # TEST 1: Strobe Lock Dynamic Frequency Sweep (4Hz - 30Hz)
    # -------------------------------------------------------------------------
    print(\n[TEST 1] Dynamic Strobe Frequency Sweep (4.0Hz to 30.0Hz)...)
    freqs = [4.0, 5.0, 5.5, 6.0, 7.5, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 25.0, 26.0, 30.0]
    strobe_lock_results = {}
    
    for f in freqs:
        total_tests += 1
        sf = StrobeFilter(min_frequency_hz=6.0, max_frequency_hz=25.0, fps=60.0)
        dt_ns = int(round(1e9 / 60.0))
        t_base = 1_000_000_000
        
        # Generate 1.5 seconds of strobe signal at 60fps (90 frames)
        # Strobe: periodic high-intensity flash (luma=220) on dark base (luma=15)
        # Period in frames = 60 / f
        period_frames = 60.0 / f
        detected_strobe = False
        
        for i in range(90):
            # Phase calculation
            phase = (i % period_frames) / period_frames
            # Flash pulse on top 20% of cycle
            is_flash = phase < 0.25 or (period_frames <= 3 and i % int(round(period_frames)) == 0)
            luma = 220.0 if is_flash else 15.0
            
            m = FrameMetrics(
                timestamp_ns=t_base + i * dt_ns,
                mean_luma=luma,
                p10=15.0,
                p50=15.0 if not is_flash else 220.0,
                p90=220.0 if is_flash else 15.0,
                p99=220.0 if is_flash else 15.0,
                c_high=0.05 if is_flash else 0.0,
                c_dark=0.0 if is_flash else 0.85,
                zone_lumas={ceiling: luma, stage_center: luma, stage_flanks: luma, crowd_floor: luma},
                luma_velocity=0.0,
            )
            res = sf.process(m)
            if res.is_strobe:
                detected_strobe = True
                
        expected_strobe = (6.0 <= f <= 25.0)
        strobe_lock_results[f] = (detected_strobe, expected_strobe)
        
        if detected_strobe == expected_strobe:
            print(f [PASS] Strobe {f:4.1f} Hz -> Detected={detected_strobe}, Expected={expected_strobe})
            passed_tests += 1
        else:
            print(f [FAIL] Strobe {f:4.1f} Hz -> Detected={detected_strobe}, Expected={expected_strobe})

    # -------------------------------------------------------------------------
    # TEST 2: Slider Chatter Prevention During Prolonged Strobe (14Hz & 20Hz)
    # -------------------------------------------------------------------------
    print(\n[TEST 2] Slider Chatter Prevention Under Prolonged Strobe Trains...)
    for strobe_freq in [10.0, 14.0, 20.0]:
        total_tests += 1
        mock = MockDispatcher()
        daemon = S26CameraControllerDaemon(dispatcher=mock)
        dt_ns = int(round(1e9 / 60.0))
        t_base = 1_000_000_000
        
        # Run 5 seconds (300 frames) of strobe train
        period_frames = 60.0 / strobe_freq
        for i in range(300):
            phase = (i % period_frames) / period_frames
            is_flash = phase < 0.25
            luma = 220 if is_flash else 20
            frame = np.full((90, 160, 3), luma, dtype=np.uint8)
            daemon.step(frame, timestamp_ns=t_base + i * dt_ns)
            
        dispatches = mock.get_taps_count()
        regime = daemon.current_regime
        # During strobe lock, AE should freeze -> dispatches should be 0 (no slider chatter)
        if dispatches == 0 and regime == LightingRegime.STROBE_LOCK:
            print(f [PASS] {strobe_freq:.0f}Hz Strobe Train: 300 frames -> 0 dispatches (Dispatches={dispatches}, Regime={regime.value}))
            passed_tests += 1
        else:
            print(f [FAIL] {strobe_freq:.0f}Hz Strobe Train: Dispatches={dispatches} (expected 0), Regime={regime.value})

    # -------------------------------------------------------------------------
    # TEST 3: Rapid Boundary Noise & Hysteresis Anti-Chatter
    # -------------------------------------------------------------------------
    print(\n[TEST 3] Rapid Boundary Noise & Hysteresis Anti-Chatter...)
    
    # 3a: Blackout Entry/Exit Boundary Noise (Luma fluctuating between 7.5 and 8.5)
    total_tests += 1
    mock = MockDispatcher()
    daemon = S26CameraControllerDaemon(dispatcher=mock)
    dt_ns = int(round(1e9 / 60.0))
    t_base = 1_000_000_000
    
    for i in range(600):  # 10.0 seconds
        luma = 7.5 if (i % 2 == 0) else 8.5
        frame = np.full((90, 160, 3), int(luma), dtype=np.uint8)
        daemon.step(frame, timestamp_ns=t_base + i * dt_ns)
        
    dispatches_3a = len(daemon._transitions)
    if dispatches_3a <= 3:
        print(f [PASS] Blackout boundary noise (10s): Dispatches={dispatches_3a} (Threshold <= 3))
        passed_tests += 1
    else:
        print(f [FAIL] Blackout boundary noise: Dispatches={dispatches_3a} (Expected <= 3))

    # 3b: Laser Enter/Exit Boundary Noise (P99 fluctuating between 248 and 252)
    total_tests += 1
    sm = ConcertStateMachine()
    t_cur = 1_000_000_000
    laser_trans = 0
    for i in range(600):
        is_high = (i % 2 == 0)
        p99 = 252.0 if is_high else 248.0
        chigh = 0.045 if is_high else 0.035
        m = FrameMetrics(
            timestamp_ns=t_cur + i * dt_ns,
            mean_luma=50.0,
            p10=20.0,
            p50=40.0,
            p90=120.0,
            p99=p99,
            c_high=chigh,
            c_dark=0.0,
            zone_lumas={ceiling: 50.0, stage_center: 50.0, stage_flanks: 50.0, crowd_floor: 50.0},
            luma_velocity=0.0,
        )
        trig, preset, _ = sm.process_frame(m)
        if trig:
            laser_trans += 1
            
    if laser_trans <= 3:
        print(f [PASS] Laser boundary noise (10s): Dispatches={laser_trans} (Threshold <= 3))
        passed_tests += 1
    else:
        print(f [FAIL] Laser boundary noise: Dispatches={laser_trans} (Expected <= 3))

    # -------------------------------------------------------------------------
    # TEST 4: Emergency Laser Array Single-Frame Bypass
    # -------------------------------------------------------------------------
    print(\n[TEST 4] Emergency Laser Array Single-Frame Bypass...)
    
    # 4a: Emergency bypass during steady Normal
    total_tests += 1
    sm = ConcertStateMachine()
    # Feed normal frames
    for i in range(10):
        m = FrameMetrics(
            timestamp_ns=t_base + i * dt_ns,
            mean_luma=50.0, p10=20.0, p50=40.0, p90=70.0, p99=100.0,
            c_high=0.0, c_dark=0.0,
            zone_lumas={ceiling: 50.0, stage_center: 50.0, stage_flanks: 50.0, crowd_floor: 50.0},
            luma_velocity=0.0,
        )
        sm.process_frame(m)
        
    # Now feed EXACTLY 1 emergency laser frame (c_high = 0.10, p99 = 255.0)
    m_emerg = FrameMetrics(
        timestamp_ns=t_base + 10 * dt_ns,
        mean_luma=120.0, p10=20.0, p50=60.0, p90=255.0, p99=255.0,
        c_high=0.10, c_dark=0.0,
        zone_lumas={ceiling: 240.0, stage_center: 80.0, stage_flanks: 50.0, crowd_floor: 40.0},
        luma_velocity=0.0,
    )
    trig, preset, reason = sm.process_frame(m_emerg)
    if trig and preset and preset.regime == LightingRegime.LASER_SPIKE and EMERGENCY in reason:
        print(f [PASS] Emergency Laser Single-Frame Trigger: Triggered={trig}, Preset={preset.regime.value}, Reason={reason})
        passed_tests += 1
    else:
        print(f [FAIL] Emergency Laser Single-Frame Trigger: Triggered={trig}, Reason={reason})

    # 4b: Emergency bypass instantly overrides Blackout regime & 350ms dwell window
    total_tests += 1
    sm = ConcertStateMachine()
    # Enter blackout
    for i in range(5):
        m = FrameMetrics(
            timestamp_ns=t_base + i * dt_ns,
            mean_luma=4.0, p10=0.0, p50=2.0, p90=6.0, p99=8.0,
            c_high=0.0, c_dark=0.95,
            zone_lumas={ceiling: 4.0, stage_center: 4.0, stage_flanks: 4.0, crowd_floor: 4.0},
            luma_velocity=0.0,
        )
        sm.process_frame(m)
    assert sm.current_regime == LightingRegime.BLACKOUT
    
    # Immediately fire emergency laser (0ms after blackout transition)
    m_emerg_blackout = FrameMetrics(
        timestamp_ns=t_base + 5 * dt_ns + 10_000_000, # +10ms
        mean_luma=110.0, p10=0.0, p50=40.0, p90=255.0, p99=255.0,
        c_high=0.12, c_dark=0.40,
        zone_lumas={ceiling: 250.0, stage_center: 70.0, stage_flanks: 30.0, crowd_floor: 20.0},
        luma_velocity=0.0,
    )
    trig, preset, reason = sm.process_frame(m_emerg_blackout)
    if trig and sm.current_regime == LightingRegime.LASER_SPIKE:
        print(f [PASS] Emergency Laser Overrides Blackout & Dwell: Triggered={trig}, Regime={sm.current_regime.value})
        passed_tests += 1
    else:
        print(f [FAIL] Emergency Laser Overrides Blackout: Triggered={trig}, Regime={sm.current_regime.value})

    # -------------------------------------------------------------------------
    # TEST 5: Comprehensive Resolution Matrix & Bounds Violation Audit
    # -------------------------------------------------------------------------
    print(\n[TEST 5] Resolution Matrix Scaling & Boundary Bounds Invariance Audit...)
    test_resolutions = [
        (3120, 1440),  # S26 Ultra WQHD+ Landscape
        (2340, 1080),  # S26 Ultra FHD+ Landscape
        (1600, 720),   # HD+ Landscape
        (3840, 2160),  # 4K UHD
        (1920, 1080),  # Full HD 16:9
        (3440, 1440),  # Ultrawide 21:9
        (2560, 1080),  # Ultrawide FHD
        (1080, 1080),  # 1:1 Square
        (1440, 3120),  # WQHD+ Portrait
        (1080, 2340),  # FHD+ Portrait
        (1080, 1920),  # 1080p Portrait
        (720, 1600),   # HD+ Portrait
        (100, 100),    # Ultra-low res
        (10, 10),      # Extreme thumbnail
        (1, 1),        # 1x1 Degenerate
        (8000, 4500),  # Ultra 8K
    ]
    
    bounds_violations = 0
    monotonic_violations = 0
    total_checks = 0
    
    for w, h in test_resolutions:
        prof = DisplayProfile.from_resolution(w, h)
        normalizer = CoordinateNormalizer(prof)
        
        # Test ribbon buttons
        for param in CameraParameter:
            total_checks += 1
            px_x, px_y = normalizer.get_ribbon_button_pixels(param)
            if not (0 <= px_x < w and 0 <= px_y < h):
                bounds_violations += 1
                print(f [VIOLATION] Resolution {w}x{h} Ribbon {param.value} -> ({px_x}, {px_y}) Out of bounds!)
                
        # Test ISO slider ticks & monotonicity
        iso_ticks = [50, 100, 200, 250, 400, 640, 800, 1600, 3200]
        prev_x = -1
        for iso_val in iso_ticks:
            total_checks += 1
            px_x, px_y = normalizer.get_iso_tick_pixels(iso_val)
            if not (0 <= px_x < w and 0 <= px_y < h):
                bounds_violations += 1
                print(f [VIOLATION] Resolution {w}x{h} ISO {iso_val} -> ({px_x}, {px_y}) Out of bounds!)
            if px_x <= prev_x and w > 10:
                monotonic_violations += 1
            prev_x = px_x
            
        # Test Shutter slider ticks
        shutter_ticks = [1/30, 1/60, 1/120, 1/240, 1/500, 1/1000, 1/2000, 1/4000, 1/12000]
        for shut_val in shutter_ticks:
            total_checks += 1
            px_x, px_y = normalizer.get_shutter_tick_pixels(shut_val)
            if not (0 <= px_x < w and 0 <= px_y < h):
                bounds_violations += 1
                print(f [VIOLATION] Resolution {w}x{h} Shutter {shut_val} -> ({px_x}, {px_y}) Out of bounds!)

    total_tests += 1
    if bounds_violations == 0:
        print(f [PASS] Resolution Matrix Bounds Check: {total_checks} coordinates tested across {len(test_resolutions)} display profiles -> 0 violations.)
        passed_tests += 1
    else:
        print(f [FAIL] Resolution Matrix Bounds Check: {bounds_violations} violations found!)

    # -------------------------------------------------------------------------
    # TEST 6: Sub-Millisecond Decision Compute Latency Benchmark
    # -------------------------------------------------------------------------
    print(\n[TEST 6] Decision Compute Latency Benchmark (1,000 frames)...)
    total_tests += 1
    daemon = S26CameraControllerDaemon(dispatcher=MockDispatcher())
    sim = ConcertLightSimulator(fps=60.0, seed=777)
    
    # Generate 1,000 frames from diverse scenarios
    frames = []
    for sc in [ConcertScenario.SCENARIO_A_NORMAL_STAGE, ConcertScenario.SCENARIO_B_LASER_ASSAULT, ConcertScenario.SCENARIO_C_STROBE_ASSAULT, ConcertScenario.SCENARIO_D_PRE_DROP_BLACKOUT]:
        frames.extend(sim.generate_scenario_frames(sc, duration_sec=4.0)) # ~240 frames each
        
    frames = frames[:1000]
    
    # Warmup
    for f, ts in frames[:50]:
        daemon.step(f, timestamp_ns=ts)
    daemon.reset()
    
    # Timed run
    for f, ts in frames:
        daemon.step(f, timestamp_ns=ts)
        
    telemetry = daemon.get_telemetry()
    print(f Mean Compute Latency: {telemetry.mean_compute_latency_ms:.4f} ms)
    print(f P50 Compute Latency: {telemetry.p50_compute_latency_ms:.4f} ms)
    print(f P95 Compute Latency: {telemetry.p95_compute_latency_ms:.4f} ms)
    print(f P99 Compute Latency: {telemetry.p99_compute_latency_ms:.4f} ms)
    print(f Max Compute Latency: {telemetry.max_compute_latency_ms:.4f} ms)
    
    if telemetry.p99_compute_latency_ms < 1.0:
        print(f [PASS] P99 Compute Latency < 1.0ms ({telemetry.p99_compute_latency_ms:.3f}ms < 1.0ms))
        passed_tests += 1
    else:
        print(f [FAIL] P99 Compute Latency >= 1.0ms ({telemetry.p99_compute_latency_ms:.3f}ms))
        
    daemon.close()

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print(\n + = * 80)
    print(fCHALLENGER 2 EMPIRICAL SUMMARY: {passed_tests}/{total_tests} ASSERTIONS PASSED)
    print(= * 80)
    if passed_tests == total_tests:
        print(>>> VERDICT: EMPIRICAL APPROVAL CONFIRMED <<<)
        return 0
    else:
        print(>>> VERDICT: EMPIRICAL REJECTION CONFIRMED <<<)
        return 1

if __name__ == __main__:
    sys.exit(run_empirical_challenge())
