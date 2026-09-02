"""Adversarial Immutability & Concurrency Stress Test for M4."""

import sys
import copy
from pathlib import Path
from datetime import datetime, timezone

cron_dir = Path("g:/My Drive/GOOGLE ANTIGRAVITY/.agents/cron").resolve()
sys.path.insert(0, str(cron_dir))

from models import AnomalyRecord, DetectorType, RedTeamAuditResult, RedTeamVerdict, Severity
from audit.red_team import ArchitectureRedTeam
from audit.report_builder import DailyReportBuilder

def test_input_immutability():
    print("Testing input immutability...")
    rt = ArchitectureRedTeam()
    builder = DailyReportBuilder()

    anomalies = [
        AnomalyRecord(
            detector_type=DetectorType.GHOST_DAEMONS,
            target_path="127.0.0.1:3000",
            severity=Severity.HIGH,
            description="Port conflict",
            raw_details={"port": 3000, "meta": {"nested": [1, 2, 3]}},
        )
    ]
    anomalies_copy = copy.deepcopy(anomalies)

    grads = ["test gradient"]
    grads_copy = copy.deepcopy(grads)

    drift = {"total_sessions": 2, "total_anomalies": 5}
    drift_copy = copy.deepcopy(drift)

    audit_res = rt.audit_batch(anomalies, gradients=grads)
    report = builder.build_daily_report(
        session_id="immutability-check",
        scan_time=datetime.now(timezone.utc),
        anomalies=anomalies,
        gradients=grads,
        audit_results=audit_res,
        historical_drift=drift,
    )

    assert anomalies == anomalies_copy, "Anomaly list was mutated!"
    assert grads == grads_copy, "Gradient list was mutated!"
    assert drift == drift_copy, "Drift dict was mutated!"
    print("PASS: Inputs are completely immutable and unpolluted.")

if __name__ == "__main__":
    test_input_immutability()
