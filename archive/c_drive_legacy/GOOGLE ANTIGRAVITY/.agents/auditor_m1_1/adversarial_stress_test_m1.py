"""
Adversarial Stress Test Suite for Milestone 1: VIRAL_FORMULA.md
Tests extreme mathematical boundaries, singularity stability (epsilon checks),
adversarial input configurations, and Pydantic validation edge cases.
"""

import sys
import math
import numpy as np
from pydantic import ValidationError
from forensic_verify_m1 import (
    calc_p1_hrv, calc_p2_dpaw, calc_p3_adr_sfd, calc_p4_cke_mve, calc_p5_ltss,
    calc_composite_evpi, EDMViralGradingReport, TransientEvent
)

def run_adversarial_stress_tests():
    print("\n" + "="*80)
    print("RUNNING ADVERSARIAL STRESS TESTS ON VIRAL FORMULA MATHEMATICS")
    print("="*80)
    
    passed_count = 0
    total_count = 0

    # ------------------------------------------------------------------------
    # Test 1: P1 (HRV) Extreme Value Stress & Monotonicity
    # ------------------------------------------------------------------------
    total_count += 1
    try:
        # Test extreme large inputs
        s_inf = calc_p1_hrv(d_hook=1e6, n_transients=10000, t_onset=0.0)
        assert s_inf == 100.0, f"Expected 100.0, got {s_inf}"
        
        # Test extreme late onset
        s_late = calc_p1_hrv(d_hook=0.0, n_transients=0, t_onset=100.0)
        assert s_late == 0.0, f"Expected 0.0, got {s_late}"
        
        # Monotonicity test over t_onset
        onsets = np.linspace(0.0, 2.0, 50)
        scores = [calc_p1_hrv(1.5, 2, t) for t in onsets]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i+1], "HRV score must be monotonically decreasing with onset latency"
            
        print("[PASS] Test 1: P1 (HRV) Extreme Value & Monotonicity verified.")
        passed_count += 1
    except Exception as e:
        print(f"[FAIL] Test 1: P1 (HRV) failed: {e}")

    # ------------------------------------------------------------------------
    # Test 2: P2 (DPAW) Piecewise Continuity & Singularity Resistance
    # ------------------------------------------------------------------------
    total_count += 1
    try:
        # Test piecewise continuity at delta_t_pocket boundaries (0.15s and 0.45s)
        eps = 1e-6
        # at 0.15s
        q_left_15 = calc_p2_dpaw(13.0, 25.0, 4.5, 0.15 - eps)
        q_right_15 = calc_p2_dpaw(13.0, 25.0, 4.5, 0.15 + eps)
        assert abs(q_left_15 - q_right_15) < 1e-3, f"Discontinuity at 0.15s: {q_left_15} vs {q_right_15}"
        
        # at 0.45s
        q_left_45 = calc_p2_dpaw(13.0, 25.0, 4.5, 0.45 - eps)
        q_right_45 = calc_p2_dpaw(13.0, 25.0, 4.5, 0.45 + eps)
        assert abs(q_left_45 - q_right_45) < 1e-3, f"Discontinuity at 0.45s: {q_left_45} vs {q_right_45}"
        
        # Test extreme build times (e.g. 100s build or 0.01s build)
        s_long_build = calc_p2_dpaw(13.0, 25.0, 100.0, 0.25)
        assert 0.0 <= s_long_build <= 100.0
        assert not math.isnan(s_long_build)
        
        print("[PASS] Test 2: P2 (DPAW) Piecewise Continuity & Boundary Safety verified.")
        passed_count += 1
    except Exception as e:
        print(f"[FAIL] Test 2: P2 (DPAW) failed: {e}")

    # ------------------------------------------------------------------------
    # Test 3: P3 (ADR-SFD) Sub-Bass Log-Scale & Negative Dynamics Resistance
    # ------------------------------------------------------------------------
    total_count += 1
    try:
        # Test negative loudness jump (drop quieter than build)
        s_quieter = calc_p3_adr_sfd(r_sub=0.0, sfd_val=0.0, delta_lufs=-12.0)
        assert s_quieter == 0.0, f"Expected 0.0 for quiet drop, got {s_quieter}"
        
        # Test massive sub-bass surge (10,000x)
        s_mega_sub = calc_p3_adr_sfd(r_sub=10000.0, sfd_val=1.0, delta_lufs=15.0)
        assert s_mega_sub == 100.0, f"Expected clamped 100.0, got {s_mega_sub}"
        
        print("[PASS] Test 3: P3 (ADR-SFD) Logarithmic Stability & Negative LUFS Handling verified.")
        passed_count += 1
    except Exception as e:
        print(f"[FAIL] Test 3: P3 (ADR-SFD) failed: {e}")

    # ------------------------------------------------------------------------
    # Test 4: P4 (CKE-MVE) Zero Motion / Anti-Phase Robustness
    # ------------------------------------------------------------------------
    total_count += 1
    try:
        # Zero motion in crowd (epsilon division test)
        s_static_crowd = calc_p4_cke_mve(delta_e_kinetic=0.0, c_jump=0.0, phi_bpm=-1.0)
        assert s_static_crowd == 0.0, f"Expected 0.0 for static crowd, got {s_static_crowd}"
        
        # Complete anti-phase (phi_bpm = -0.99)
        s_antiphase = calc_p4_cke_mve(delta_e_kinetic=4.0, c_jump=1.0, phi_bpm=-0.99)
        # 0.40 * 1.0 + 0.35 * 1.0 + 0.25 * 0.0 = 0.75 * 100 = 75.0
        assert abs(s_antiphase - 75.0) < 1e-5, f"Expected 75.0 for antiphase, got {s_antiphase}"
        
        print("[PASS] Test 4: P4 (CKE-MVE) Zero Motion & Anti-Phase Robustness verified.")
        passed_count += 1
    except Exception as e:
        print(f"[FAIL] Test 4: P4 (CKE-MVE) failed: {e}")

    # ------------------------------------------------------------------------
    # Test 5: P5 (LTSS) Sub-Frame Gaussian Decay Precision
    # ------------------------------------------------------------------------
    total_count += 1
    try:
        # Verify 33ms sigma Gaussian:
        # at tau = 0ms: score component = 1.0
        # at tau = 33ms: score component = exp(-0.5) ~= 0.60653
        # at tau = 66ms (2 frames): score component = exp(-2.0) ~= 0.13533
        # at tau = 150ms: score component = exp(-10.3) ~= 0.00003
        s_0ms = calc_p5_ltss(tau_sync_sec=0.0, f_prod=0.0, f_strobe_hz=4.0)
        s_33ms = calc_p5_ltss(tau_sync_sec=0.033, f_prod=0.0, f_strobe_hz=4.0)
        s_66ms = calc_p5_ltss(tau_sync_sec=0.066, f_prod=0.0, f_strobe_hz=4.0)
        
        assert abs(s_0ms - 40.0) < 1e-3
        assert abs(s_33ms - 40.0 * math.exp(-0.5)) < 1e-3
        assert abs(s_66ms - 40.0 * math.exp(-2.0)) < 1e-3
        
        print("[PASS] Test 5: P5 (LTSS) Sub-Frame 33ms Gaussian Decay Precision verified.")
        passed_count += 1
    except Exception as e:
        print(f"[FAIL] Test 5: P5 (LTSS) failed: {e}")

    # ------------------------------------------------------------------------
    # Test 6: Composite EVPI Compound Killswitch Suppression
    # ------------------------------------------------------------------------
    total_count += 1
    try:
        # All 3 killswitches tripped to worst level:
        # K_audio = 0.1, K_format = 0.5, K_dur = 0.4
        # Compound multiplier = 0.1 * 0.5 * 0.4 = 0.02
        # Raw score = 100.0 -> EVPI = 2.0
        evpi_worst = calc_composite_evpi(100, 100, 100, 100, 100, k_audio=0.1, k_format=0.5, k_duration=0.4)
        assert abs(evpi_worst - 2.0) < 1e-5, f"Expected 2.0, got {evpi_worst}"
        
        print("[PASS] Test 6: Composite EVPI Compound Killswitch Suppression verified.")
        passed_count += 1
    except Exception as e:
        print(f"[FAIL] Test 6: Composite EVPI failed: {e}")

    # ------------------------------------------------------------------------
    # Test 7: Pydantic Schema Adversarial Boundary Injections
    # ------------------------------------------------------------------------
    total_count += 1
    try:
        # Attempt to inject invalid transient event types
        try:
            TransientEvent(
                timestamp_seconds=1.0,
                event_type="fireworks_explosion", # Not in Literal
                intensity=0.8,
                description="Fireworks"
            )
            assert False, "Failed to reject invalid event_type literal"
        except ValidationError:
            pass

        # Attempt to inject negative intensity
        try:
            TransientEvent(
                timestamp_seconds=1.0,
                event_type="audio_drop",
                intensity=-0.5, # ge=0.0 violated
                description="Drop"
            )
            assert False, "Failed to reject negative intensity"
        except ValidationError:
            pass

        print("[PASS] Test 7: Pydantic Schema Adversarial Boundary Injections successfully rejected.")
        passed_count += 1
    except Exception as e:
        print(f"[FAIL] Test 7: Pydantic Schema failed: {e}")

    print("\n" + "="*80)
    print(f"ADVERSARIAL STRESS TEST SUMMARY: {passed_count}/{total_count} PASSED")
    print("="*80)
    return passed_count == total_count

if __name__ == "__main__":
    success = run_adversarial_stress_tests()
    sys.exit(0 if success else 1)
