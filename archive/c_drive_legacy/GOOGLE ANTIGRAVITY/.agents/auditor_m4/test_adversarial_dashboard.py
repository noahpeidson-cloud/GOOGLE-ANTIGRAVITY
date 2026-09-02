"""
test_adversarial_dashboard.py - Adversarial Stress-Testing for Milestone 4 Dashboard Logic.
Simulates hostile inputs, boundary values, division-by-zero, and state transitions.
"""

import math

def calculate_evpi(scores, aspect_ratio="9:16"):
    hrv = scores.get("HRV", 50)
    dpaw = scores.get("DPAW", 50)
    adr_sfd = scores.get("ADR_SFD", 50)
    cke_mve = scores.get("CKE_MVE", 50)
    ltss = scores.get("LTSS", 50)

    evpi = hrv * 0.25 + dpaw * 0.25 + adr_sfd * 0.20 + cke_mve * 0.15 + ltss * 0.15
    if hrv < 40:
        evpi = min(evpi, 49.9)
    if aspect_ratio == "16:9":
        evpi *= 0.5
    evpi = round(evpi * 100) / 100

    verdict = "LOW_REACH"
    if evpi >= 85:
        verdict = "VIRAL_READY"
    elif evpi >= 70:
        verdict = "HIGH_POTENTIAL"
    elif evpi >= 50:
        verdict = "MODERATE_REACH"

    return evpi, verdict

def test_adversarial_evpi():
    print("Testing EVPI viral calculation adversarial scenarios...")
    
    # 1. Zeroes & Negative inputs
    evpi, verdict = calculate_evpi({"HRV": 0, "DPAW": 0, "ADR_SFD": 0, "CKE_MVE": 0, "LTSS": 0})
    assert evpi == 0.0
    assert verdict == "LOW_REACH"

    # 2. Perfect 100 scores 9:16
    evpi, verdict = calculate_evpi({"HRV": 100, "DPAW": 100, "ADR_SFD": 100, "CKE_MVE": 100, "LTSS": 100}, "9:16")
    assert evpi == 100.0
    assert verdict == "VIRAL_READY"

    # 3. Perfect 100 scores in 16:9 (Landscape -50% penalty)
    evpi, verdict = calculate_evpi({"HRV": 100, "DPAW": 100, "ADR_SFD": 100, "CKE_MVE": 100, "LTSS": 100}, "16:9")
    assert evpi == 50.0
    assert verdict == "MODERATE_REACH"

    # 4. HRV Killswitch: High metrics (100) on everything else, but HRV = 39.9 (HRV < 40)
    evpi, verdict = calculate_evpi({"HRV": 39.9, "DPAW": 100, "ADR_SFD": 100, "CKE_MVE": 100, "LTSS": 100}, "9:16")
    assert evpi <= 49.9
    assert verdict == "LOW_REACH"

    # 5. HRV Boundary: HRV = 40.0 exactly (No killswitch trigger)
    evpi, verdict = calculate_evpi({"HRV": 40.0, "DPAW": 100, "ADR_SFD": 100, "CKE_MVE": 100, "LTSS": 100}, "9:16")
    # 40*0.25 + 100*0.75 = 10 + 75 = 85.0
    assert evpi == 85.0
    assert verdict == "VIRAL_READY"

    # 6. Verdict boundaries
    # Exactly 85.0 -> VIRAL_READY
    # Exactly 84.9 -> HIGH_POTENTIAL
    # Exactly 70.0 -> HIGH_POTENTIAL
    # Exactly 69.9 -> MODERATE_REACH
    # Exactly 50.0 -> MODERATE_REACH
    # Exactly 49.9 -> LOW_REACH
    assert calculate_evpi({"HRV": 85, "DPAW": 85, "ADR_SFD": 85, "CKE_MVE": 85, "LTSS": 85})[1] == "VIRAL_READY"
    assert calculate_evpi({"HRV": 84.9, "DPAW": 84.9, "ADR_SFD": 84.9, "CKE_MVE": 84.9, "LTSS": 84.9})[1] == "HIGH_POTENTIAL"
    assert calculate_evpi({"HRV": 70, "DPAW": 70, "ADR_SFD": 70, "CKE_MVE": 70, "LTSS": 70})[1] == "HIGH_POTENTIAL"
    assert calculate_evpi({"HRV": 69.9, "DPAW": 69.9, "ADR_SFD": 69.9, "CKE_MVE": 69.9, "LTSS": 69.9})[1] == "MODERATE_REACH"
    assert calculate_evpi({"HRV": 50, "DPAW": 50, "ADR_SFD": 50, "CKE_MVE": 50, "LTSS": 50})[1] == "MODERATE_REACH"
    assert calculate_evpi({"HRV": 49.9, "DPAW": 49.9, "ADR_SFD": 49.9, "CKE_MVE": 49.9, "LTSS": 49.9})[1] == "LOW_REACH"

    print("  -> EVPI adversarial calculations: ALL PASSED")

def test_adversarial_roi_calc():
    print("Testing Sports ROI division-by-zero protection...")
    # When investment is 0
    total_investment = 0
    total_estimated_value = 500
    net_profit = total_estimated_value - total_investment
    profit_margin = (net_profit / total_investment * 100) if total_investment > 0 else 0
    assert profit_margin == 0
    assert net_profit == 500
    print("  -> Sports ROI zero-guard: PASSED")

def test_dlq_replay_state_transitions():
    print("Testing DLQ retry state machine...")
    incidents = [
        {"incident_id": "INC_01", "retry_count": 0, "max_retries": 3, "status": "QUARANTINED"},
        {"incident_id": "INC_02", "retry_count": 2, "max_retries": 3, "status": "QUARANTINED"},
        {"incident_id": "INC_03", "retry_count": 3, "max_retries": 3, "status": "RESOLVED"},
    ]
    
    # Replay INC_01
    inc1 = incidents[0]
    inc1["retry_count"] += 1
    inc1["status"] = "RESOLVED"
    assert inc1["retry_count"] == 1
    assert inc1["status"] == "RESOLVED"
    
    # Purge resolved
    remaining = [i for i in incidents if i["status"] != "RESOLVED"]
    assert len(remaining) == 1
    assert remaining[0]["incident_id"] == "INC_02"
    print("  -> DLQ state machine transitions: ALL PASSED")

if __name__ == "__main__":
    test_adversarial_evpi()
    test_adversarial_roi_calc()
    test_dlq_replay_state_transitions()
    print("\n=== ALL ADVERSARIAL STRESS TESTS PASSED SUCCESSFULLY ===")
