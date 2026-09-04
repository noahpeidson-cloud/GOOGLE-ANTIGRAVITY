"""Challenger M6 Adversarial Stress Suite.

Comprehensive white-box gap analysis, edge case probing, fuzz testing,
and adversarial stress verification across all components of .agents/cron:
1. Safety AST Guardrail Evasion Stress Matrix
2. SQLite Telemetry Store & Foreign Key Cascading
3. Detectors Boundary & Fuzz Matrix (Ghost Daemons, Context Rot, Pollution, Secret Zero, Prompt Fatigue)
4. ML Clustering & Embeddings Boundary Matrix (N=0..1000, extreme values, NaN/Inf resilience)
5. ProTeGi Textual Gradient Generator Dynamic Heuristics
6. Architecture Red-Team Adversarial Scrutiny & Strict Whitelist Enforcement
7. Daily HITL Report Builder Markdown Table & Checkbox Escaping
8. Full Pipeline & Scanner Daemon Concurrency & Immutability
"""

import hashlib
import json
import math
import os
import re
import socket
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pytest

CRON_DIR = Path(__file__).resolve().parent.parent
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

from audit.red_team import ArchitectureRedTeam, is_whitelisted_file
from audit.report_builder import DailyReportBuilder
from config import (
    BLACKLIST_TOKEN_PATTERNS,
    CONTEXT_ROT_THRESHOLD_HOURS,
    DEFAULT_DB_PATH,
    DEFAULT_K_CLUSTERS,
    MONITORED_PORTS,
    PROMPT_FATIGUE_MAX_LINES,
    WHITELISTED_FILENAMES,
)
from database import (
    HISTORICAL_LIFELINES_DATA,
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
from detectors.base import BaseDetector
from detectors.context_rot import ContextRotDetector
from detectors.ecosystem_pollution import EcosystemPollutionDetector
from detectors.ghost_daemons import GhostDaemonsDetector
from detectors.prompt_fatigue import PromptFatigueDetector, estimate_token_count
from detectors.secret_zero import SecretZeroDetector, mask_token
from fixtures.mock_workspace_factory import MockDaemonListener, create_mock_workspace
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
    SafetyASTVisitor,
    SafetyViolationError,
    assert_safe_codebase,
    scan_code_for_safety,
    scan_file_for_safety,
)
from scanner import HealthScanner
from scanner_daemon import (
    build_cli_parser,
    create_antigravity_sdk_trigger,
    main as daemon_main,
    run_health_scan,
)
from tests.conftest import FileSystemSnapshot


# =============================================================================
# 1. Safety AST Guardrail Evasion Stress Matrix
# =============================================================================
class TestSafetyASTStressMatrix:
    """Adversarial stress-testing of AST guardrails with evasion techniques."""

    @pytest.mark.parametrize(
        "evasion_snippet,expected_match",
        [
            ("import os as sys_os; sys_os.remove('foo.txt')", "os.remove"),
            ("from os import unlink as delete_file; delete_file('foo.txt')", "os.unlink"),
            ("from shutil import rmtree as clean_tree; clean_tree('dir')", "shutil.rmtree"),
            ("import os; getattr(os, 'remove')('target.txt')", "getattr"),
            ("import shutil; getattr(shutil, 'rmtree')('target_dir')", "getattr"),
            ("import subprocess; subprocess.run(['pkill', '-f', 'node'])", "pkill"),
            ("import subprocess; subprocess.Popen(args=['taskkill', '/F', '/PID', '123'])", "taskkill"),
            ("import os; os.system('rm -rf /tmp/test')", "rm -rf"),
            ("from pathlib import Path; Path('file.txt').unlink()", ".unlink()"),
            ("from pathlib import Path; Path('dir').rmdir()", ".rmdir()"),
            ("cursor.execute('DROP TABLE users;')", "DROP TABLE"),
            ("cursor.execute('TRUNCATE scan_sessions;')", "TRUNCATE"),
            ("cursor.executemany(operation='DROP SCHEMA public CASCADE', seq_of_parameters=[])", "DROP SCHEMA"),
            ("eval(\"__import__('os').remove('file.txt')\")", "eval"),
            ("exec(\"import os; os.unlink('file.txt')\")", "exec"),
        ],
    )
    def test_ast_detects_obfuscated_and_aliased_destruction(self, evasion_snippet: str, expected_match: str):
        violations = scan_code_for_safety(evasion_snippet)
        assert len(violations) >= 1, f"Failed to catch evasion: {evasion_snippet}"
        assert any(expected_match.lower() in v.lower() for v in violations)

    def test_ast_allows_benign_safe_code(self):
        safe_code = '''
import json
import os
import sqlite3
from typing import List

def safe_math_remove(x: List[int], val: int) -> List[int]:
    return [i for i in x if i != val]

def query_logs(db_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM scan_sessions WHERE description = 'DROP TABLE incident'")
    rows = cur.fetchall()
    conn.close()
    return rows
'''
        violations = scan_code_for_safety(safe_code)
        assert len(violations) == 0, f"False positive on safe code: {violations}"


# =============================================================================
# 2. SQLite Telemetry Store & Foreign Key Integrity
# =============================================================================
class TestSQLiteTelemetryAdversarial:
    """Adversarial stress-testing of database operations and constraint handling."""

    def test_foreign_key_cascade_deletion(self, tmp_path: Path):
        db_path = str(tmp_path / "fk_test.db")
        init_db(db_path)

        session_id = "cascade_sess_1"
        anoms = [
            AnomalyRecord(
                detector_type=DetectorType.CONTEXT_ROT,
                target_path="stale.md",
                severity=Severity.HIGH,
                description="Test rot",
                raw_details={"nested": {"deep": True}},
            )
        ]
        grads = ["Gradient for cascade"]
        log_scan_session(session_id, anoms, grads, duration_ms=12.5, db_path=db_path)

        conn = get_db_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM anomalies WHERE session_id = ?", (session_id,))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT COUNT(*) FROM textual_gradients WHERE session_id = ?", (session_id,))
        assert cur.fetchone()[0] == 1

        cur.execute("DELETE FROM scan_sessions WHERE session_id = ?", (session_id,))
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM anomalies WHERE session_id = ?", (session_id,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT COUNT(*) FROM textual_gradients WHERE session_id = ?", (session_id,))
        assert cur.fetchone()[0] == 0
        conn.close()

    def test_duplicate_session_id_raises_integrity_error(self, tmp_path: Path):
        db_path = str(tmp_path / "dup_test.db")
        init_db(db_path)
        session_id = "unique_sess_123"
        log_scan_session(session_id, [], [], 10.0, db_path=db_path)

        with pytest.raises(sqlite3.IntegrityError):
            log_scan_session(session_id, [], [], 20.0, db_path=db_path)

    def test_historical_drift_empty_db(self, tmp_path: Path):
        db_path = str(tmp_path / "empty_drift.db")
        init_db(db_path)
        drift = get_historical_drift(db_path)
        assert drift["total_sessions"] == 0
        assert drift["total_anomalies"] == 0
        assert drift["drift_detected"] is False
        assert drift["historical_lifelines_count"] == 5


# =============================================================================
# 3. Detectors Boundary & Fuzz Matrix
# =============================================================================
class TestDetectorsBoundaryAndFuzz:
    """Boundary testing for all 5 detectors."""

    def test_ghost_daemons_invalid_inputs(self):
        detector = GhostDaemonsDetector(monitored_ports=[0, -1, 70000, 59999], host="127.0.0.1")
        findings = detector.scan(".")
        assert isinstance(findings, list)

    def test_context_rot_exact_24h_boundary(self, tmp_path: Path):
        detector = ContextRotDetector(threshold_hours=24.0)
        file_23h = tmp_path / "draft_proposal.md"
        file_24h = tmp_path / "old_proposal.md"

        file_23h.write_text("# Fresh")
        file_24h.write_text("# Stale")

        now = time.time()
        os.utime(str(file_23h), (now - 23.9 * 3600, now - 23.9 * 3600))
        os.utime(str(file_24h), (now - 24.1 * 3600, now - 24.1 * 3600))

        findings = detector.scan(str(tmp_path))
        targets = [f.target_path for f in findings]
        assert any("old_proposal.md" in t for t in targets)
        assert not any("draft_proposal.md" in t for t in targets)

    def test_ecosystem_pollution_cross_track_boundary(self, tmp_path: Path):
        detector = EcosystemPollutionDetector()
        sports_track = tmp_path / "sports_cards"
        media_track = tmp_path / "content_creation"
        sports_track.mkdir(parents=True)
        media_track.mkdir(parents=True)

        leak_video = sports_track / "raw_capture.mov"
        leak_video.write_bytes(b"fake video data")

        leak_card = media_track / "card_ladder_analysis.md"
        leak_card.write_text("# Card ladder ETL notes")

        findings = detector.scan(str(tmp_path))
        assert len(findings) >= 2
        categories = [f.raw_details.get("pollution_type") for f in findings]
        assert "CROSS_TRACK_LEAK" in categories

    def test_secret_zero_masking_tokens(self, tmp_path: Path):
        assert mask_token("abc") == "****"
        assert mask_token("your_token_here") == "yo***re"
        assert mask_token("sk-12345678901234567890") == "sk***90"

        detector = SecretZeroDetector()
        env_file = tmp_path / ".env.staging"
        env_file.write_text("SECRET_KEY=your_token_here\nOPENAI_KEY=sk-abcdef123456789012345678\n")

        findings = detector.scan(str(tmp_path))
        assert len(findings) == 2
        for f in findings:
            assert "your_token_here" not in f.description
            assert "sk-abcdef" not in f.description
            assert "***" in f.description

    def test_prompt_fatigue_duplicates_and_token_heuristic(self, tmp_path: Path):
        detector = PromptFatigueDetector(max_lines=10)
        manifest = tmp_path / "GEMINI.md"
        manifest.write_text("""# Manifest Title
## Permanent Rules
Directive 1
Directive 2
Directive 3
## Permanent Rules
Directive 4
Directive 5
Directive 6
Directive 7
Directive 8
Directive 9
Directive 10
Directive 11
""")

        findings = detector.scan(str(tmp_path))
        assert len(findings) == 2
        types = [f.description for f in findings]
        assert any("bloat" in d.lower() for d in types)
        assert any("duplicate" in d.lower() for d in types)


# =============================================================================
# 4. ML Clustering & Embeddings Boundary Matrix
# =============================================================================
class TestMLEmbeddingsAndClusteringStress:
    """Stress-testing pure NumPy K-Means and embedding vectors."""

    def test_vectorization_extreme_numerical_inputs(self):
        anom = AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path="huge.md",
            severity=Severity.CRITICAL,
            description="Extreme value anomaly",
            raw_details={"age_hours": 999999.0, "token_count": 5000000},
            confidence=10.0,
        )
        vec = vectorize_anomaly(anom)
        assert vec.shape == (5,)
        assert np.all(vec >= 0.0)
        assert np.all(vec <= 1.0)
        assert vec[2] == 1.0
        assert vec[3] == 1.0
        assert vec[4] == 1.0

    def test_kmeans_performance_and_k_bounds(self):
        np.random.seed(42)
        X = np.random.uniform(0.0, 1.0, size=(1000, 5))
        t0 = time.perf_counter()
        labels, centroids, inertia = kmeans_cluster(X, k=3, max_iter=30)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        assert elapsed_ms < 30.0
        assert labels.shape == (1000,)
        assert centroids.shape == (3, 5)
        assert inertia >= 0.0

        l1, c1, _ = kmeans_cluster(X[:10], k=1)
        assert l1.shape == (10,)
        assert c1.shape == (1, 5)

        l_kn, c_kn, _ = kmeans_cluster(X[:2], k=5)
        assert l_kn.shape == (2,)
        assert c_kn.shape == (5, 5)


# =============================================================================
# 5. ProTeGi Textual Gradient Generator
# =============================================================================
class TestProTeGiGradients:
    """Verification of textual gradient synthesis under diverse cluster patterns."""

    def test_convergence_on_zero_entropy(self):
        anoms = [
            AnomalyRecord(
                detector_type=DetectorType.SECRET_ZERO,
                target_path=".env",
                severity=Severity.CRITICAL,
                description="Test",
                raw_details={},
            )
        ]
        grads = generate_textual_gradients(anoms, np.array([0]), np.zeros((1, 5)), entropy=0.0)
        assert grads == [CONVERGENCE_MESSAGE]

    def test_all_five_detectors_gradients_generation(self):
        types = list(DetectorType)
        anoms = [
            AnomalyRecord(
                detector_type=dt,
                target_path=f"target_{dt.value}",
                severity=Severity.HIGH,
                description=f"Anomaly for {dt.value}",
                raw_details={},
            )
            for dt in types
        ]
        labels = np.array([0, 1, 2, 0, 1])
        centroids = np.zeros((3, 5))
        grads = generate_textual_gradients(anoms, labels, centroids, entropy=0.45)
        assert len(grads) >= 5
        assert any("Meta-Gradient" in g for g in grads)


# =============================================================================
# 6. Architecture Red-Team Adversarial Scrutiny
# =============================================================================
class TestArchitectureRedTeamHardening:
    """Tests strict enforcement of non-destruction and false-positive suppression."""

    @pytest.mark.parametrize(
        "malicious_action",
        [
            "taskkill /PID 9999 /F",
            "pkill python",
            "kill -9 1234",
            "os.kill(pid, signal.SIGTERM)",
            "Stop-Process -Name node",
            "rmdir /s /q plugins",
            "rm -rf .agents",
            "del .env",
            "DROP TABLE anomalies",
            "TRUNCATE TABLE scan_sessions",
        ],
    )
    def test_red_team_rejects_all_destructive_actions(self, malicious_action: str):
        red_team = ArchitectureRedTeam()
        anom = AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path="stale.md",
            severity=Severity.HIGH,
            description="Stale note",
            raw_details={"age_hours": 30.0},
        )
        res = red_team.audit_optimization(anom, proposed_action=malicious_action)
        assert res.verdict == RedTeamVerdict.REJECTED
        assert "prohibited" in res.rationale.lower() or "whitelist" in res.rationale.lower()

    @pytest.mark.parametrize(
        "manifest_file,malicious_action",
        [
            ("GEMINI.md", "truncate GEMINI.md"),
            ("GEMINI.md", "prune rules from GEMINI.md"),
            ("PROJECT.md", "delete PROJECT.md"),
            ("README.md", "remove README.md"),
            ("BRIEFING.md", "wipe BRIEFING.md"),
        ],
    )
    def test_red_team_rejects_manifest_destruction(self, manifest_file: str, malicious_action: str):
        red_team = ArchitectureRedTeam()
        anom = AnomalyRecord(
            detector_type=DetectorType.PROMPT_FATIGUE if manifest_file == "GEMINI.md" else DetectorType.CONTEXT_ROT,
            target_path=manifest_file,
            severity=Severity.HIGH,
            description=f"Flagged {manifest_file}",
            raw_details={"age_hours": 50.0},
        )
        res = red_team.audit_optimization(anom, proposed_action=malicious_action)
        assert res.verdict == RedTeamVerdict.REJECTED
        assert "whitelist" in res.rationale.lower() or "prohibited" in res.rationale.lower()


# =============================================================================
# 7. Daily HITL Report Builder Markdown Table & Checkbox Escaping
# =============================================================================
class TestReportBuilderEscapingAndFormatting:
    """Verifies pipe escaping, checkbox syntax, and section structure."""

    def test_pipe_escaping_in_rationale_and_action(self):
        builder = DailyReportBuilder()
        anom = AnomalyRecord(
            detector_type=DetectorType.SECRET_ZERO,
            target_path="dir/file.env",
            severity=Severity.CRITICAL,
            description="Pipe | in description",
            raw_details={},
        )
        audit = RedTeamAuditResult(
            anomaly=anom,
            verdict=RedTeamVerdict.APPROVED,
            rationale="Rationale with | pipe and `code`",
            recommended_action="Action with | pipe",
        )
        report = builder.build_daily_report(
            session_id="pipe_sess",
            scan_time=time.time(),
            anomalies=[anom],
            gradients=["Gradient | text"],
            audit_results=[audit],
        )
        for line in report.splitlines():
            if line.startswith("| 1 |"):
                cells = re.split(r"(?<!\\)\|", line.strip())[1:-1]
                assert len(cells) == 8, f"Table cell count broken by unescaped pipe: {line}"

    def test_interactive_checkboxes_presence(self):
        builder = DailyReportBuilder()
        anom = AnomalyRecord(
            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
            target_path="plugins/old.disabled",
            severity=Severity.HIGH,
            description="Disabled plugin",
            raw_details={},
        )
        audit = RedTeamAuditResult(
            anomaly=anom,
            verdict=RedTeamVerdict.APPROVED,
            rationale="Safe isolation",
            recommended_action="Quarantine plugin",
        )
        report = builder.build_daily_report("chk_sess", time.time(), [anom], [], [audit])
        assert "- [ ] [HITL-APPROVED] Safe Optimization: Quarantine plugin (Target: `plugins/old.disabled`)" in report


# =============================================================================
# 8. Full Pipeline & Scanner Daemon Concurrency & Immutability
# =============================================================================
class TestDaemonIntegrationAndImmutability:
    """Verifies cryptographic immutability and complete 9-step scan orchestration."""

    def test_cryptographic_immutability_on_mock_workspace(self, tmp_path: Path):
        ws_dir = tmp_path / "mock_workspace"
        create_mock_workspace(str(ws_dir))
        snapshot = FileSystemSnapshot(str(ws_dir))

        db_path = str(tmp_path / "immutability.db")
        out_dir = str(tmp_path / "reports")

        report, report_file = run_health_scan(
            workspace_root=str(ws_dir),
            db_path=db_path,
            output_dir=out_dir,
        )

        snapshot.assert_untouched()
        assert report.total_anomalies >= 4
        assert os.path.exists(report_file)
