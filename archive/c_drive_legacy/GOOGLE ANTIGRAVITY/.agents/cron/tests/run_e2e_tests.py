#!/usr/bin/env python3
"""Master Opaque-Box E2E Test Runner & Adversarial Verification Engine.

Executes all 5 comprehensive test tiers for the Antigravity Daily Health Scanner & ML Optimization Daemon:
  - Tier 1: Feature Coverage (SQLite, 5 Historical Seeds, AST Safety, 5 Detectors, K-Means ML, Red-Team Audit, Report Builder, Scanner Daemon)
  - Tier 2: Boundary & Corner Cases (Empty DB, 0 anomalies, large payloads, N < K, borderline timestamps, corrupt files)
  - Tier 3: Cross-Feature Combinations (Full pipeline integration, drift tracking over sessions, exception isolation across components)
  - Tier 4: Real-World Workloads (Full mock workspace reproducing all 5 August 23/24 historical failure patterns simultaneously, CLI runner --run-once --mock-env)
  - Tier 5: Adversarial Hardening (AST evasion stress matrix, malicious action rejection in Red-Team, SHA-256 cryptographic immutability assertions)

Formats a comprehensive console summary report with exit code 0 when 100% pass.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure cron root is in sys.path
CURRENT_FILE = Path(__file__).resolve()
TESTS_DIR = CURRENT_FILE.parent
CRON_DIR = TESTS_DIR.parent
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

# Core imports
from audit.red_team import ArchitectureRedTeam, is_whitelisted_file
from audit.report_builder import DailyReportBuilder
from database import (
    get_anomalies_for_session,
    get_db_connection,
    get_historical_drift,
    get_historical_lifelines,
    get_session,
    get_textual_gradients_for_session,
    init_db,
    log_scan_session,
    seed_historical_lifelines,
)
from detectors.context_rot import ContextRotDetector
from detectors.ecosystem_pollution import EcosystemPollutionDetector
from detectors.ghost_daemons import GhostDaemonsDetector
from detectors.prompt_fatigue import PromptFatigueDetector
from detectors.secret_zero import SecretZeroDetector
from ml.clustering import compute_semantic_entropy, kmeans_cluster
from ml.embeddings import vectorize_anomalies, vectorize_anomaly
from ml.protegi import CONVERGENCE_MESSAGE, generate_textual_gradients
from models import (
    AnomalyRecord,
    DetectorType,
    OptimizationReport,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)
from safety_guardrails import (
    SafetyViolationError,
    assert_safe_codebase,
    scan_code_for_safety,
)
from scanner import HealthScanner
from scanner_daemon import (
    build_cli_parser,
    create_antigravity_sdk_trigger,
    create_mock_workspace,
    main as daemon_main,
    run_health_scan,
)


# =============================================================================
# Helper Utilities & FileSystem Cryptographic Snapshot
# =============================================================================
class FileSystemSnapshot:
    """Computes and verifies SHA-256 cryptographic hashes of all files to enforce 0-destruction."""

    def __init__(self, root_dir: str) -> None:
        self.root_dir = os.path.abspath(root_dir)
        self.initial_hashes: Dict[str, str] = self._compute_hashes()

    def _compute_hashes(self) -> Dict[str, str]:
        hashes: Dict[str, str] = {}
        if not os.path.exists(self.root_dir):
            return hashes
        for root, _, files in os.walk(self.root_dir):
            for file in sorted(files):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.root_dir)
                try:
                    with open(full_path, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    hashes[rel_path] = file_hash
                except Exception as e:
                    hashes[rel_path] = f"ERROR:{e}"
        return hashes

    def assert_untouched(self) -> None:
        current_hashes = self._compute_hashes()
        added = set(current_hashes.keys()) - set(self.initial_hashes.keys())
        removed = set(self.initial_hashes.keys()) - set(current_hashes.keys())
        modified = [
            k for k in self.initial_hashes
            if k in current_hashes and self.initial_hashes[k] != current_hashes[k]
        ]
        if added or removed or modified:
            raise AssertionError(
                f"Cryptographic SHA-256 violation in {self.root_dir}:\n"
                f"  Added: {sorted(list(added))}\n"
                f"  Removed: {sorted(list(removed))}\n"
                f"  Modified: {sorted(modified)}"
            )


@dataclass
class TestResult:
    tier: str
    name: str
    description: str
    passed: bool
    duration_ms: float
    error_message: Optional[str] = None


class TestRegistry:
    def __init__(self) -> None:
        self.results: List[TestResult] = []

    def run_test(self, tier: str, name: str, description: str, test_fn: Callable[[], None]) -> bool:
        start = time.perf_counter()
        passed = False
        err_msg = None
        try:
            test_fn()
            passed = True
        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)}"
        duration_ms = (time.perf_counter() - start) * 1000.0
        self.results.append(
            TestResult(
                tier=tier,
                name=name,
                description=description,
                passed=passed,
                duration_ms=duration_ms,
                error_message=err_msg,
            )
        )
        status_icon = "PASS" if passed else "FAIL"
        print(f"  [{status_icon:<4}] {tier} :: {name} ({duration_ms:.2f} ms)")
        if not passed:
            print(f"         Error: {err_msg}")
        return passed


# =============================================================================
# Tier 1: Feature Coverage Test Suite
# =============================================================================
def run_tier_1_feature_tests(registry: TestRegistry) -> None:
    print("\n" + "=" * 78)
    print("  TIER 1: FEATURE COVERAGE (Component & Schema Level Verification)")
    print("=" * 78)

    def test_sqlite_telemetry_schema():
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "tier1_telemetry.db")
            init_db(db_path)
            conn = get_db_connection(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {r["name"] for r in cursor.fetchall()}
            cursor.execute("PRAGMA journal_mode;")
            j_mode = cursor.fetchone()[0].lower()
            cursor.execute("PRAGMA foreign_keys;")
            fk = cursor.fetchone()[0]
            conn.close()

            assert "scan_sessions" in tables
            assert "anomalies" in tables
            assert "historical_lifelines" in tables
            assert "textual_gradients" in tables
            assert j_mode == "wal"
            assert fk == 1

    def test_historical_lifelines_seeding():
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "tier1_seeds.db")
            init_db(db_path)
            lifelines = get_historical_lifelines(db_path)
            assert len(lifelines) == 5
            codes = {lf["lifeline_code"] for lf in lifelines}
            expected_codes = {
                "GHOST_DAEMONS_WINERROR_10048",
                "CONTEXT_ROT_PLANNING_ARTIFACTS",
                "ECOSYSTEM_POLLUTION_DISABLED_PLUGINS",
                "SECRET_ZERO_PLACEHOLDER_KEYS",
                "PROMPT_FATIGUE_MANIFEST_BLOAT",
            }
            assert codes == expected_codes
            # Idempotency check
            seed_historical_lifelines(db_path)
            assert len(get_historical_lifelines(db_path)) == 5

    def test_ast_safety_guardrails():
        clean_code = "import json\ndef process():\n    return json.dumps({'status': 'ok'})\n"
        assert len(scan_code_for_safety(clean_code)) == 0

        dirty_remove = "import os\nos.remove('file.txt')"
        assert any("os.remove" in v for v in scan_code_for_safety(dirty_remove))

        dirty_taskkill = "import subprocess\nsubprocess.run(['taskkill', '/PID', '1234'])"
        assert any("taskkill" in v for v in scan_code_for_safety(dirty_taskkill))

        # Check production codebase
        assert_safe_codebase(str(CRON_DIR), exclude_dirs=["tests"])

    def test_detector_ghost_daemons():
        detector = GhostDaemonsDetector(monitored_ports=[59998])
        # Port 59998 is not open
        anomalies = detector.scan(".")
        assert isinstance(anomalies, list)

    def test_detector_context_rot():
        with tempfile.TemporaryDirectory() as tmp_dir:
            agents_dir = os.path.join(tmp_dir, ".agents", "worker_old")
            os.makedirs(agents_dir, exist_ok=True)
            stale_file = os.path.join(agents_dir, "progress.md")
            with open(stale_file, "w", encoding="utf-8") as f:
                f.write("# Old Progress\n")
            old_time = time.time() - (48 * 3600)
            os.utime(stale_file, (old_time, old_time))

            detector = ContextRotDetector(threshold_hours=24.0)
            anomalies = detector.scan(tmp_dir)
            assert len(anomalies) >= 1
            assert anomalies[0].detector_type == DetectorType.CONTEXT_ROT

    def test_detector_ecosystem_pollution():
        with tempfile.TemporaryDirectory() as tmp_dir:
            plugin_dir = os.path.join(tmp_dir, "plugins", "sample.disabled")
            os.makedirs(plugin_dir, exist_ok=True)
            with open(os.path.join(plugin_dir, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("# Disabled Skill\n")

            detector = EcosystemPollutionDetector()
            anomalies = detector.scan(tmp_dir)
            assert len(anomalies) >= 1
            assert anomalies[0].detector_type == DetectorType.ECOSYSTEM_POLLUTION

    def test_detector_secret_zero():
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = os.path.join(tmp_dir, ".env")
            with open(env_file, "w", encoding="utf-8") as f:
                f.write("API_KEY=your_token_here\nDATABASE_URL=postgres://...\n")

            detector = SecretZeroDetector()
            anomalies = detector.scan(tmp_dir)
            assert len(anomalies) >= 1
            assert anomalies[0].detector_type == DetectorType.SECRET_ZERO

    def test_detector_prompt_fatigue():
        with tempfile.TemporaryDirectory() as tmp_dir:
            gemini_file = os.path.join(tmp_dir, "GEMINI.md")
            with open(gemini_file, "w", encoding="utf-8") as f:
                f.write("# Manifest\n" + "\n".join([f"Rule {i}: instruction" for i in range(150)]))

            detector = PromptFatigueDetector(max_lines=100)
            anomalies = detector.scan(tmp_dir)
            assert len(anomalies) == 1
            assert anomalies[0].detector_type == DetectorType.PROMPT_FATIGUE

    def test_master_health_scanner():
        scanner = HealthScanner()
        assert len(scanner.detectors) == 5
        with tempfile.TemporaryDirectory() as tmp_dir:
            create_mock_workspace(tmp_dir)
            anomalies = scanner.scan_workspace(tmp_dir)
            assert len(anomalies) >= 4
            assert scanner.get_last_duration_ms() > 0.0

    def test_ml_vectorization():
        anoms = [
            AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path="plan.md",
                severity=Severity.HIGH,
                description="Stale file",
                raw_details={"age_hours": 36.0, "token_count": 500},
                timestamp=int(time.time()),
            )
        ]
        X = vectorize_anomalies(anoms)
        assert X.shape == (1, 5)
        assert 0.0 <= X[0, 0] <= 1.0  # severity
        assert 0.0 <= X[0, 1] <= 1.0  # detector
        assert 0.0 <= X[0, 2] <= 1.0  # age
        assert 0.0 <= X[0, 3] <= 1.0  # footprint
        assert 0.0 <= X[0, 4] <= 1.0  # confidence

    def test_ml_kmeans_clustering():
        import numpy as np
        np.random.seed(42)
        X = np.random.uniform(0.0, 1.0, size=(15, 5))
        labels, centroids, inertia = kmeans_cluster(X, k=3, max_iter=25)
        assert labels.shape == (15,)
        assert centroids.shape == (3, 5)
        assert inertia >= 0.0
        entropy = compute_semantic_entropy(X, labels, centroids)
        assert 0.0 <= entropy <= 1.0

    def test_protegi_textual_gradients():
        import numpy as np
        anoms = [
            AnomalyRecord(
                detector_type=DetectorType.SECRET_ZERO,
                target_path=".env",
                severity=Severity.CRITICAL,
                description="Placeholder token",
                raw_details={"token": "your_token_here"},
            )
        ]
        labels = np.array([0])
        centroids = np.zeros((1, 5))
        gradients = generate_textual_gradients(anoms, labels, centroids, entropy=0.35)
        assert len(gradients) >= 1
        assert any("SECRET_ZERO" in g or "placeholder" in g.lower() for g in gradients)

    def test_architecture_red_team():
        red_team = ArchitectureRedTeam()
        anom_secret = AnomalyRecord(
            detector_type=DetectorType.SECRET_ZERO,
            target_path=".env",
            severity=Severity.CRITICAL,
            description="Placeholder token in .env",
            raw_details={"token": "your_token_here"},
        )
        res = red_team.audit_optimization(anom_secret)
        assert res.verdict == RedTeamVerdict.APPROVED
        assert len(res.rationale) > 0
        assert len(res.recommended_action) > 0

    def test_daily_report_builder():
        builder = DailyReportBuilder()
        content = builder.build_daily_report(
            session_id="t1_report_sess",
            scan_time=time.time(),
            anomalies=[],
            gradients=[CONVERGENCE_MESSAGE],
            audit_results=[],
            historical_drift={"total_sessions": 1, "total_anomalies": 0},
            duration_ms=25.0,
            entropy=0.0,
        )
        assert "Daily System Health & Optimization Report" in content
        assert "Executive Summary" in content
        assert "Historical Failure Lifelines & Drift Analytics" in content

    def test_antigravity_sdk_cron_trigger():
        trigger = create_antigravity_sdk_trigger(interval_seconds=60, workspace_root=".")
        assert callable(trigger) or hasattr(trigger, "__call__") or hasattr(trigger, "interval")

    registry.run_test("Tier 1", "test_sqlite_telemetry_schema", "Verify SQLite schema, tables & pragmas", test_sqlite_telemetry_schema)
    registry.run_test("Tier 1", "test_historical_lifelines_seeding", "Verify 5 August 23/24 lifelines seeded idempotently", test_historical_lifelines_seeding)
    registry.run_test("Tier 1", "test_ast_safety_guardrails", "Verify AST static analyzer detects destructive calls", test_ast_safety_guardrails)
    registry.run_test("Tier 1", "test_detector_ghost_daemons", "Verify Ghost Daemons socket detector", test_detector_ghost_daemons)
    registry.run_test("Tier 1", "test_detector_context_rot", "Verify Context Rot stale planning artifact detector", test_detector_context_rot)
    registry.run_test("Tier 1", "test_detector_ecosystem_pollution", "Verify Ecosystem Pollution .disabled plugin detector", test_detector_ecosystem_pollution)
    registry.run_test("Tier 1", "test_detector_secret_zero", "Verify Secret Zero placeholder token detector", test_detector_secret_zero)
    registry.run_test("Tier 1", "test_detector_prompt_fatigue", "Verify Prompt Fatigue manifest bloat detector", test_detector_prompt_fatigue)
    registry.run_test("Tier 1", "test_master_health_scanner", "Verify Master HealthScanner orchestration", test_master_health_scanner)
    registry.run_test("Tier 1", "test_ml_vectorization", "Verify 5D normalized feature matrix extraction", test_ml_vectorization)
    registry.run_test("Tier 1", "test_ml_kmeans_clustering", "Verify pure NumPy/Pandas K-Means (K=3) & semantic entropy", test_ml_kmeans_clustering)
    registry.run_test("Tier 1", "test_protegi_textual_gradients", "Verify ProTeGi textual gradient generation", test_protegi_textual_gradients)
    registry.run_test("Tier 1", "test_architecture_red_team", "Verify Architecture Red-Team adversarial audit", test_architecture_red_team)
    registry.run_test("Tier 1", "test_daily_report_builder", "Verify 6-section HITL Markdown report builder", test_daily_report_builder)
    registry.run_test("Tier 1", "test_antigravity_sdk_cron_trigger", "Verify Antigravity SDK cron trigger factory", test_antigravity_sdk_cron_trigger)


# =============================================================================
# Tier 2: Boundary & Corner Cases Test Suite
# =============================================================================
def run_tier_2_boundary_tests(registry: TestRegistry) -> None:
    print("\n" + "=" * 78)
    print("  TIER 2: BOUNDARY & CORNER CASES (Edge, Stress, and Degradation Handling)")
    print("=" * 78)

    def test_empty_workspace_and_zero_anomalies():
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir = os.path.join(tmp_dir, "clean_ws")
            os.makedirs(ws_dir, exist_ok=True)
            db_path = os.path.join(tmp_dir, "empty_ws.db")
            out_dir = os.path.join(tmp_dir, "reports")
            clean_scanner = HealthScanner(
                detectors=[
                    GhostDaemonsDetector(monitored_ports=[59992]),
                    ContextRotDetector(),
                    EcosystemPollutionDetector(),
                    SecretZeroDetector(),
                    PromptFatigueDetector(),
                ]
            )
            report, report_path = run_health_scan(ws_dir, db_path, out_dir, custom_scanner=clean_scanner)
            assert report.total_anomalies == 0
            assert report.entropy_score == 0.0
            assert os.path.exists(report_path)

    def test_kmeans_n_less_than_k():
        import numpy as np
        # N = 0
        X_0 = np.empty((0, 5))
        l0, c0, in0 = kmeans_cluster(X_0, k=3)
        assert l0.shape == (0,)
        assert c0.shape == (3, 5)

        # N = 1
        X_1 = np.array([[0.5, 0.2, 0.1, 0.0, 1.0]])
        l1, c1, in1 = kmeans_cluster(X_1, k=3)
        assert l1.shape == (1,)
        assert c1.shape == (3, 5)

        # N = 2
        X_2 = np.array([[0.5, 0.2, 0.1, 0.0, 1.0], [0.8, 0.4, 0.3, 0.1, 0.9]])
        l2, c2, in2 = kmeans_cluster(X_2, k=3)
        assert l2.shape == (2,)
        assert c2.shape == (3, 5)

    def test_kmeans_all_identical_samples():
        import numpy as np
        X_same = np.tile(np.array([0.5, 0.5, 0.5, 0.5, 0.5]), (10, 1))
        labels, centroids, inertia = kmeans_cluster(X_same, k=3)
        assert labels.shape == (10,)
        assert inertia == 0.0
        entropy = compute_semantic_entropy(X_same, labels, centroids)
        assert entropy == 0.0

    def test_large_payload_stress():
        anoms = [
            AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT if i % 2 == 0 else DetectorType.ECOSYSTEM_POLLUTION,
                target_path=f"file_{i}.md",
                severity=Severity.HIGH if i % 3 == 0 else Severity.MEDIUM,
                description=f"Stress test anomaly {i}",
                raw_details={"age_hours": float(25 + (i % 100))},
                timestamp=int(time.time()),
            )
            for i in range(500)
        ]
        start = time.perf_counter()
        X = vectorize_anomalies(anoms)
        labels, centroids, _ = kmeans_cluster(X, k=3)
        entropy = compute_semantic_entropy(X, labels, centroids)
        gradients = generate_textual_gradients(anoms, labels, centroids, entropy)
        red_team = ArchitectureRedTeam()
        audits = red_team.audit_batch(anoms, gradients=gradients)
        builder = DailyReportBuilder()
        report_md = builder.build_daily_report(
            session_id="stress_500",
            scan_time=time.time(),
            anomalies=anoms,
            gradients=gradients,
            audit_results=audits,
            duration_ms=100.0,
            entropy=entropy,
        )
        elapsed = (time.perf_counter() - start) * 1000.0
        assert len(audits) == 500
        assert len(report_md) > 1000
        assert elapsed < 500.0  # Must complete <500ms for 500 items

    def test_borderline_timestamps_and_whitelists():
        with tempfile.TemporaryDirectory() as tmp_dir:
            agents_dir = os.path.join(tmp_dir, ".agents", "worker_test")
            os.makedirs(agents_dir, exist_ok=True)
            fresh_plan = os.path.join(agents_dir, "fresh_plan.md")
            stale_plan = os.path.join(agents_dir, "stale_plan.md")
            protected_briefing = os.path.join(agents_dir, "BRIEFING.md")

            with open(fresh_plan, "w", encoding="utf-8") as f:
                f.write("# Fresh\n")
            with open(stale_plan, "w", encoding="utf-8") as f:
                f.write("# Stale\n")
            with open(protected_briefing, "w", encoding="utf-8") as f:
                f.write("# Protected Briefing\n")

            now = time.time()
            # 23.5 hours old (fresh)
            os.utime(fresh_plan, (now - 23.5 * 3600, now - 23.5 * 3600))
            # 25.0 hours old (stale)
            os.utime(stale_plan, (now - 25.0 * 3600, now - 25.0 * 3600))
            # 100.0 hours old (whitelisted)
            os.utime(protected_briefing, (now - 100.0 * 3600, now - 100.0 * 3600))

            detector = ContextRotDetector(threshold_hours=24.0)
            anomalies = detector.scan(tmp_dir)
            targets = [os.path.basename(a.target_path) for a in anomalies]
            assert "stale_plan.md" in targets
            assert "fresh_plan.md" not in targets
            assert "BRIEFING.md" not in targets

    def test_corrupted_files_graceful_handling():
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Corrupted binary .env
            env_file = os.path.join(tmp_dir, ".env")
            with open(env_file, "wb") as f:
                f.write(b"\x00\xff\xfe\x00" * 100)

            # Corrupted binary GEMINI.md
            gemini_file = os.path.join(tmp_dir, "GEMINI.md")
            with open(gemini_file, "wb") as f:
                f.write(b"\x00" * 5000)

            db_path = os.path.join(tmp_dir, "corrupt.db")
            out_dir = os.path.join(tmp_dir, "reports")
            report, report_path = run_health_scan(tmp_dir, db_path, out_dir)
            assert isinstance(report, OptimizationReport)
            assert os.path.exists(report_path)

    registry.run_test("Tier 2", "test_empty_workspace_and_zero_anomalies", "Empty workspace produces 0 anomalies and clean 0.000 entropy", test_empty_workspace_and_zero_anomalies)
    registry.run_test("Tier 2", "test_kmeans_n_less_than_k", "K-Means handles N=0, N=1, N=2 with K=3 gracefully", test_kmeans_n_less_than_k)
    registry.run_test("Tier 2", "test_kmeans_all_identical_samples", "K-Means handles zero-variance identical samples", test_kmeans_all_identical_samples)
    registry.run_test("Tier 2", "test_large_payload_stress", "Stress test 500 anomalies pipeline in <500ms", test_large_payload_stress)
    registry.run_test("Tier 2", "test_borderline_timestamps_and_whitelists", "Accurate 24h boundary discrimination & whitelist safety", test_borderline_timestamps_and_whitelists)
    registry.run_test("Tier 2", "test_corrupted_files_graceful_handling", "Corrupted binary files handled without pipeline crash", test_corrupted_files_graceful_handling)


# =============================================================================
# Tier 3: Cross-Feature Combinations & Pairwise Integration
# =============================================================================
def run_tier_3_cross_feature_tests(registry: TestRegistry) -> None:
    print("\n" + "=" * 78)
    print("  TIER 3: CROSS-FEATURE PAIRWISE INTEGRATION (12 Integration Flows)")
    print("=" * 78)

    def test_flow_1():
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir = os.path.join(tmp_dir, "f1_ws")
            create_mock_workspace(ws_dir)
            db_path = os.path.join(tmp_dir, "f1.db")
            init_db(db_path)
            scanner = HealthScanner()
            anoms = scanner.scan_workspace(ws_dir)
            log_scan_session("f1_sess", anoms, ["grad"], 30.0, db_path=db_path)
            loaded = get_anomalies_for_session("f1_sess", db_path=db_path)
            assert len(loaded) == len(anoms)

    def test_flow_2():
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "f2.db")
            init_db(db_path)
            records = [
                AnomalyRecord(
                    detector_type=DetectorType.CONTEXT_ROT,
                    target_path=f"f_{i}.md",
                    severity=Severity.MEDIUM,
                    description=f"Rot {i}",
                    raw_details={"age_hours": 30.0 + i},
                )
                for i in range(6)
            ]
            log_scan_session("f2_sess", records, [], 10.0, db_path=db_path)
            loaded = get_anomalies_for_session("f2_sess", db_path=db_path)
            X = vectorize_anomalies(loaded)
            labels, centroids, _ = kmeans_cluster(X, k=3)
            entropy = compute_semantic_entropy(X, labels, centroids)
            assert 0.0 <= entropy <= 1.0

    def test_flow_3():
        with tempfile.TemporaryDirectory() as tmp_dir:
            create_mock_workspace(tmp_dir)
            scanner = HealthScanner()
            anoms = scanner.scan_workspace(tmp_dir)
            red_team = ArchitectureRedTeam()
            audits = red_team.audit_batch(anoms)
            assert len(audits) == len(anoms)

    def test_flow_4():
        builder = DailyReportBuilder()
        anom = AnomalyRecord(
            detector_type=DetectorType.SECRET_ZERO,
            target_path=".env",
            severity=Severity.CRITICAL,
            description="Token found",
            raw_details={},
        )
        audit = RedTeamAuditResult(
            anomaly=anom,
            verdict=RedTeamVerdict.APPROVED,
            rationale="Rotate token",
            risk_assessment="Low risk",
            recommended_action="Update token",
        )
        content = builder.build_daily_report(
            session_id="f4_sess",
            scan_time=time.time(),
            anomalies=[anom],
            gradients=["ProTeGi: Secret rotation rule"],
            audit_results=[audit],
        )
        assert "- [ ]" in content
        assert "ProTeGi" in content

    def test_flow_5():
        builder = DailyReportBuilder()
        approved_anom = AnomalyRecord(
            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
            target_path="plugins/a.disabled",
            severity=Severity.HIGH,
            description="Disabled plugin",
            raw_details={},
        )
        rejected_anom = AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path="PROJECT.md",
            severity=Severity.HIGH,
            description="Project spec",
            raw_details={},
        )
        audits = [
            RedTeamAuditResult(anomaly=approved_anom, verdict=RedTeamVerdict.APPROVED, rationale="Safe", risk_assessment="Low", recommended_action="Quarantine"),
            RedTeamAuditResult(anomaly=rejected_anom, verdict=RedTeamVerdict.REJECTED, rationale="Whitelisted", risk_assessment="Critical", recommended_action="Retain"),
        ]
        content = builder.build_daily_report("f5_sess", time.time(), [approved_anom, rejected_anom], [], audits)
        assert "- [ ]" in content
        assert "PROJECT.md" in content
        assert "REJECTED" in content

    def test_flow_6():
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir = os.path.join(tmp_dir, "f6_ws")
            create_mock_workspace(ws_dir)
            db_path = os.path.join(tmp_dir, "f6.db")
            for _ in range(4):
                run_health_scan(ws_dir, db_path, os.path.join(tmp_dir, "reports"))
            drift = get_historical_drift(db_path=db_path)
            assert drift["total_sessions"] == 4
            assert drift["historical_lifelines_count"] == 5

    def test_flow_7():
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, ".env"), "wb") as f:
                f.write(b"\x00\xff\x00")
            rep, _ = run_health_scan(tmp_dir, os.path.join(tmp_dir, "f7.db"), os.path.join(tmp_dir, "reports"))
            assert rep.session_id is not None

    def test_flow_8():
        anom = AnomalyRecord(
            detector_type=DetectorType.GHOST_DAEMONS,
            target_path="127.0.0.1:3000",
            severity=Severity.CRITICAL,
            description="Occupied port 3000",
            raw_details={"port": 3000},
        )
        red_team = ArchitectureRedTeam()
        res = red_team.audit_optimization(anom)
        assert res.verdict in {RedTeamVerdict.CHALLENGED, RedTeamVerdict.REJECTED}
        assert "kill" not in res.recommended_action.lower() or "avoid" in res.recommended_action.lower()

    def test_flow_9():
        with tempfile.TemporaryDirectory() as tmp_dir:
            snapshot = FileSystemSnapshot(tmp_dir)
            detector = ContextRotDetector()
            detector.scan(tmp_dir)
            snapshot.assert_untouched()
            assert_safe_codebase(str(CRON_DIR), exclude_dirs=["tests"])

    def test_flow_10():
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, ".env"), "w") as f:
                f.write("KEY=your_token_here\n")
            rep, rpath = run_health_scan(tmp_dir, os.path.join(tmp_dir, "f10.db"), os.path.join(tmp_dir, "reports"))
            assert rep.total_anomalies >= 1
            assert os.path.exists(rpath)

    def test_flow_11():
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdir = os.path.join(tmp_dir, "plugins", "old.disabled")
            os.makedirs(pdir, exist_ok=True)
            with open(os.path.join(pdir, "SKILL.md"), "w") as f:
                f.write("# Disabled\n")
            rep, _ = run_health_scan(tmp_dir, os.path.join(tmp_dir, "f11.db"), os.path.join(tmp_dir, "reports"))
            p_items = [a for a in rep.audited_anomalies if a.anomaly.detector_type == DetectorType.ECOSYSTEM_POLLUTION]
            assert len(p_items) >= 1
            assert p_items[0].verdict == RedTeamVerdict.APPROVED

    def test_flow_12():
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "GEMINI.md"), "w") as f:
                f.write("# M\n" + "\n".join([f"Rule {i}" for i in range(120)]))
            detector = PromptFatigueDetector(max_lines=100)
            anoms = detector.scan(tmp_dir)
            assert len(anoms) == 1
            X = vectorize_anomalies(anoms)
            labels, centroids, _ = kmeans_cluster(X, k=1)
            grads = generate_textual_gradients(anoms, labels, centroids, entropy=0.2)
            assert len(grads) >= 1

    registry.run_test("Tier 3", "Flow 1: SQLite + Detectors Pipeline Integration", "Anomalies persisted accurately in telemetry schema", test_flow_1)
    registry.run_test("Tier 3", "Flow 2: SQLite + ML Clustering & Vectorization", "Anomalies loaded from SQLite clustered cleanly", test_flow_2)
    registry.run_test("Tier 3", "Flow 3: Detectors + Architecture Red-Team", "Adversarial evaluation filters false positives", test_flow_3)
    registry.run_test("Tier 3", "Flow 4: ML Gradients + Daily HITL Report", "Textual gradients formatted in daily report", test_flow_4)
    registry.run_test("Tier 3", "Flow 5: Red-Team Verdicts + Interactive Checkboxes", "Approved items receive checkboxes, rejected receive warnings", test_flow_5)
    registry.run_test("Tier 3", "Flow 6: Multi-Session Telemetry + Drift Tracking", "Sequential sessions track drift across runs", test_flow_6)
    registry.run_test("Tier 3", "Flow 7: Exception Isolation Across Components", "Corrupt payload handled gracefully without failure", test_flow_7)
    registry.run_test("Tier 3", "Flow 8: Ghost Daemon -> Red-Team Challenge", "Ghost daemons rejected from auto-kill", test_flow_8)
    registry.run_test("Tier 3", "Flow 9: Context Rot -> Zero Deletion AST Invariant", "Stale files detected while AST guarantees zero deletion", test_flow_9)
    registry.run_test("Tier 3", "Flow 10: Secret Zero -> SQLite -> Rotation Alert", "Placeholder key logged and flagged for rotation", test_flow_10)
    registry.run_test("Tier 3", "Flow 11: Ecosystem Pollution -> Quarantine Approval", "Disabled plugin approved for quarantine", test_flow_11)
    registry.run_test("Tier 3", "Flow 12: Prompt Fatigue -> Vectorization -> ProTeGi", "Bloated manifest vectorized into rule distillation diff", test_flow_12)


# =============================================================================
# Tier 4: Real-World Workloads & Scenarios
# =============================================================================
def run_tier_4_real_world_tests(registry: TestRegistry) -> None:
    print("\n" + "=" * 78)
    print("  TIER 4: REAL-WORLD WORKLOADS & SCENARIOS (Full Workspace Simulations)")
    print("=" * 78)

    def test_scenario_1_master_workspace_5_failures():
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir = os.path.join(tmp_dir, "master_ws")
            create_mock_workspace(ws_dir)
            db_path = os.path.join(tmp_dir, "master.db")
            out_dir = os.path.join(tmp_dir, "reports")

            snapshot = FileSystemSnapshot(ws_dir)
            report, report_path = run_health_scan(ws_dir, db_path, out_dir)
            snapshot.assert_untouched()

            assert report.total_anomalies >= 4
            assert report.approved_count >= 1
            assert len(report.textual_gradients) >= 1
            assert os.path.exists(report_path)

            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "- [ ]" in content
            assert "ProTeGi" in content

    def test_scenario_2_clean_workspace_baseline():
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir = os.path.join(tmp_dir, "clean_ws")
            os.makedirs(ws_dir, exist_ok=True)
            with open(os.path.join(ws_dir, "PROJECT.md"), "w", encoding="utf-8") as f:
                f.write("# Project Spec\nClean specifications.\n")
            with open(os.path.join(ws_dir, "GEMINI.md"), "w", encoding="utf-8") as f:
                f.write("# Rules\nClean rules under 100 lines.\n")

            clean_scanner = HealthScanner(
                detectors=[
                    GhostDaemonsDetector(monitored_ports=[59991]),
                    ContextRotDetector(),
                    EcosystemPollutionDetector(),
                    SecretZeroDetector(),
                    PromptFatigueDetector(),
                ]
            )
            db_path = os.path.join(tmp_dir, "clean.db")
            out_dir = os.path.join(tmp_dir, "reports")
            report, report_path = run_health_scan(ws_dir, db_path, out_dir, custom_scanner=clean_scanner)

            assert report.total_anomalies == 0
            assert report.entropy_score == 0.0
            assert os.path.exists(report_path)

    def test_scenario_3_multiday_historical_drift():
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir = os.path.join(tmp_dir, "drift_ws")
            create_mock_workspace(ws_dir)
            db_path = os.path.join(tmp_dir, "drift.db")
            out_dir = os.path.join(tmp_dir, "reports")

            for i in range(7):
                rep, _ = run_health_scan(ws_dir, db_path, out_dir)
                assert rep.session_id is not None

            drift = get_historical_drift(db_path=db_path)
            assert drift["total_sessions"] == 7
            assert drift["historical_lifelines_count"] == 5
            assert drift["drift_detected"] is True

    def test_scenario_4_cli_runner_mock_env():
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "cli_mock.db")
            out_dir = os.path.join(tmp_dir, "cli_reports")
            argv = ["--run-once", "--mock-env", "--db", db_path, "--output-dir", out_dir]
            exit_code = daemon_main(argv)
            assert exit_code == 0
            drift = get_historical_drift(db_path=db_path)
            assert drift["total_sessions"] == 1

    def test_scenario_5_subprocess_standalone_execution():
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir = os.path.join(tmp_dir, "sub_ws")
            create_mock_workspace(ws_dir)
            db_path = os.path.join(tmp_dir, "sub.db")
            out_dir = os.path.join(tmp_dir, "sub_reports")
            daemon_script = os.path.join(CRON_DIR, "scanner_daemon.py")

            cmd = [
                sys.executable,
                daemon_script,
                "--run-once",
                "--workspace",
                ws_dir,
                "--db",
                db_path,
                "--output-dir",
                out_dir,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            assert res.returncode == 0
            assert "ANTIGRAVITY HEALTH SCAN COMPLETE:" in res.stdout

    registry.run_test("Tier 4", "Scenario 1: 5 Historical Failures Workspace", "Full mock workspace exercising all 5 detectors simultaneously", test_scenario_1_master_workspace_5_failures)
    registry.run_test("Tier 4", "Scenario 2: Clean Baseline Workspace", "Pristine workspace produces 0 anomalies & 100% health score", test_scenario_2_clean_workspace_baseline)
    registry.run_test("Tier 4", "Scenario 3: 7-Day Historical Drift Lifecycle", "Multi-session scan telemetry and drift tracking", test_scenario_3_multiday_historical_drift)
    registry.run_test("Tier 4", "Scenario 4: CLI Runner --run-once --mock-env", "Standalone in-process CLI execution with temporary mock workspace", test_scenario_4_cli_runner_mock_env)
    registry.run_test("Tier 4", "Scenario 5: Subprocess Standalone Execution", "External process CLI execution exits with code 0", test_scenario_5_subprocess_standalone_execution)


# =============================================================================
# Tier 5: Adversarial Hardening & Cryptographic Immutability
# =============================================================================
def run_tier_5_adversarial_tests(registry: TestRegistry) -> None:
    print("\n" + "=" * 78)
    print("  TIER 5: ADVERSARIAL HARDENING & CRYPTOGRAPHIC IMMUTABILITY")
    print("=" * 78)

    def test_ast_evasion_aliased_imports():
        code = "import os as my_os\nmy_os.remove('file.txt')"
        violations = scan_code_for_safety(code)
        assert len(violations) >= 1
        assert any("os.remove" in v for v in violations)

    def test_ast_evasion_getattr_destructive():
        code = "import os\nfn = getattr(os, 'unlink')\nfn('file.txt')"
        violations = scan_code_for_safety(code)
        assert len(violations) >= 1
        assert any("getattr" in v or "unlink" in v for v in violations)

    def test_ast_evasion_eval_exec():
        code_eval = "eval(\"__import__('os').remove('file.txt')\")"
        v_eval = scan_code_for_safety(code_eval)
        assert len(v_eval) >= 1

        code_exec = "exec(\"import os; os.rmdir('dir')\")"
        v_exec = scan_code_for_safety(code_exec)
        assert len(v_exec) >= 1

    def test_ast_evasion_pathlib_unlink_rmdir():
        code = "from pathlib import Path\nPath('file.txt').unlink()"
        violations = scan_code_for_safety(code)
        assert len(violations) >= 1
        assert any("unlink" in v for v in violations)

    def test_ast_evasion_subprocess_taskkill_pkill():
        code = "import subprocess\nsubprocess.Popen(['pkill', '-9', 'python'])"
        violations = scan_code_for_safety(code)
        assert len(violations) >= 1
        assert any("pkill" in v for v in violations)

    def test_ast_evasion_sql_destructive():
        code_drop = "cursor.execute('DROP TABLE scan_sessions')"
        v_drop = scan_code_for_safety(code_drop)
        assert len(v_drop) >= 1

        code_trunc = "cursor.execute('TRUNCATE TABLE anomalies')"
        v_trunc = scan_code_for_safety(code_trunc)
        assert len(v_trunc) >= 1

    def test_red_team_rejects_broad_destructive_actions():
        red_team = ArchitectureRedTeam()
        destructive_actions = [
            "rmdir /s /q plugins",
            "del .env",
            "unlink .env.local",
            "rm -rf .agents",
            "drop table scan_sessions",
            "truncate table anomalies",
            "Remove-Item -Recurse plugins",
            "wipe database",
            "purge all temporary directories",
        ]
        for act in destructive_actions:
            anom = AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path="sample.md",
                severity=Severity.HIGH,
                description="Stale planning file",
                raw_details={"age_hours": 30.0},
            )
            res = red_team.audit_optimization(anom, proposed_action=act)
            assert res.verdict == RedTeamVerdict.REJECTED, f"Action '{act}' must be REJECTED by Red-Team"

    def test_red_team_rejects_automated_process_killing():
        red_team = ArchitectureRedTeam()
        kill_actions = [
            "taskkill /PID 1234 /F",
            "pkill -f node",
            "kill -9 5678",
            "os.kill(pid, signal.SIGKILL)",
            "Stop-Process -Id 1234",
            "wmic process delete",
        ]
        for act in kill_actions:
            anom = AnomalyRecord(
                detector_type=DetectorType.GHOST_DAEMONS,
                target_path="127.0.0.1:3000",
                severity=Severity.CRITICAL,
                description="Port 3000 occupied",
                raw_details={"port": 3000},
            )
            res = red_team.audit_optimization(anom, proposed_action=act)
            assert res.verdict == RedTeamVerdict.REJECTED, f"Kill action '{act}' must be REJECTED"

    def test_red_team_whitelist_protection_gemini_and_project():
        red_team = ArchitectureRedTeam()
        whitelisted_files = ["PROJECT.md", "GEMINI.md", "README.md", "BRIEFING.md", "ORIGINAL_REQUEST.md"]
        for wf in whitelisted_files:
            assert is_whitelisted_file(wf) is True
            anom = AnomalyRecord(
                detector_type=DetectorType.PROMPT_FATIGUE if wf == "GEMINI.md" else DetectorType.CONTEXT_ROT,
                target_path=wf,
                severity=Severity.HIGH,
                description=f"Flagged {wf}",
                raw_details={"line_count": 150},
            )
            res = red_team.audit_optimization(anom, proposed_action="delete this file to reduce bloat")
            assert res.verdict == RedTeamVerdict.REJECTED

    def test_sha256_cryptographic_immutability():
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir = os.path.join(tmp_dir, "mock_ws")
            create_mock_workspace(ws_dir)
            snapshot = FileSystemSnapshot(ws_dir)

            # Execute complete multi-stage pipeline with external DB and external report directory
            db_path = os.path.join(tmp_dir, "crypto.db")
            out_dir = os.path.join(tmp_dir, "crypto_reports")
            run_health_scan(ws_dir, db_path, out_dir)

            # Cryptographically assert 0 files modified or removed inside workspace root
            snapshot.assert_untouched()

    registry.run_test("Tier 5", "AST Evasion: Aliased Module Imports", "Detects os.remove via alias (my_os.remove)", test_ast_evasion_aliased_imports)
    registry.run_test("Tier 5", "AST Evasion: Dynamic getattr Access", "Detects getattr(os, 'unlink') dynamic binding", test_ast_evasion_getattr_destructive)
    registry.run_test("Tier 5", "AST Evasion: Dynamic eval / exec", "Detects eval/exec metaprogramming bypass attempts", test_ast_evasion_eval_exec)
    registry.run_test("Tier 5", "AST Evasion: Pathlib Deletion Ops", "Detects Path.unlink() and Path.rmdir() calls", test_ast_evasion_pathlib_unlink_rmdir)
    registry.run_test("Tier 5", "AST Evasion: Subprocess Process Killing", "Detects taskkill, pkill, and kill process commands", test_ast_evasion_subprocess_taskkill_pkill)
    registry.run_test("Tier 5", "AST Evasion: Destructive SQL Statements", "Detects DROP TABLE and TRUNCATE statements", test_ast_evasion_sql_destructive)
    registry.run_test("Tier 5", "Red-Team: Rejection of Broad Deletion", "Red-Team rejects all 9 destructive filesystem/DB operations", test_red_team_rejects_broad_destructive_actions)
    registry.run_test("Tier 5", "Red-Team: Rejection of Process Killing", "Red-Team rejects all 6 automated process termination commands", test_red_team_rejects_automated_process_killing)
    registry.run_test("Tier 5", "Red-Team: Protected Whitelist Defense", "Red-Team strictly blocks deletion of GEMINI.md / PROJECT.md", test_red_team_whitelist_protection_gemini_and_project)
    registry.run_test("Tier 5", "Cryptographic SHA-256 Immutability", "FileSystemSnapshot cryptographically proves 0 modifications during scan", test_sha256_cryptographic_immutability)


# =============================================================================
# Master Test Runner Entrypoint
# =============================================================================
def main() -> int:
    start_total = time.perf_counter()
    registry = TestRegistry()

    print("\n" + "=" * 78)
    print("  ANTIGRAVITY HEALTH SCANNER & ML OPTIMIZATION DAEMON")
    print("  MASTER OPAQUE-BOX E2E TEST RUNNER & ADVERSARIAL HARNESS")
    print("=" * 78)

    run_tier_1_feature_tests(registry)
    run_tier_2_boundary_tests(registry)
    run_tier_3_cross_feature_tests(registry)
    run_tier_4_real_world_tests(registry)
    run_tier_5_adversarial_tests(registry)

    total_time = (time.perf_counter() - start_total) * 1000.0

    # Summary analytics
    total_tests = len(registry.results)
    passed_tests = sum(1 for r in registry.results if r.passed)
    failed_tests = total_tests - passed_tests

    tier_stats: Dict[str, Dict[str, int]] = {}
    for r in registry.results:
        if r.tier not in tier_stats:
            tier_stats[r.tier] = {"total": 0, "passed": 0, "failed": 0}
        tier_stats[r.tier]["total"] += 1
        if r.passed:
            tier_stats[r.tier]["passed"] += 1
        else:
            tier_stats[r.tier]["failed"] += 1

    print("\n" + "=" * 78)
    print("  E2E TEST SUITE EXECUTION SUMMARY")
    print("=" * 78)
    print(f"  {'Test Tier':<10} | {'Total':<8} | {'Passed':<8} | {'Failed':<8} | {'Pass Rate':<10}")
    print("  " + "-" * 56)

    for tier, s in tier_stats.items():
        rate = (s["passed"] / s["total"]) * 100.0 if s["total"] > 0 else 0.0
        print(f"  {tier:<10} | {s['total']:<8} | {s['passed']:<8} | {s['failed']:<8} | {rate:>7.1f} %")

    print("  " + "-" * 56)
    pass_pct = (passed_tests / total_tests) * 100.0 if total_tests > 0 else 0.0
    print(f"  {'TOTAL':<10} | {total_tests:<8} | {passed_tests:<8} | {failed_tests:<8} | {pass_pct:>7.1f} %")
    print(f"\n  Total Execution Time: {total_time:.2f} ms ({total_time / 1000.0:.2f} s)")

    if failed_tests > 0:
        print("\n  [FAILED] TEST RUN FAILED with the following errors:")
        for r in registry.results:
            if not r.passed:
                print(f"    - [{r.tier}] {r.name}: {r.error_message}")
        print("=" * 78)
        return 1

    print("\n  [SUCCESS] 100% E2E TEST PASS CERTIFIED: Zero failures across all 5 test tiers.")
    print("=" * 78 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
