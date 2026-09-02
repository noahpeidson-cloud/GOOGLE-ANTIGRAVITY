# Handoff Report: Milestone 5 — Test Suite Design for `tests/test_scanner_daemon.py`

## 1. Observation
Across the project workspace at `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron`, the underlying subsystem components have been analyzed:

1. **Modular Health Scanner (`scanner.py:27-82`)**:
   - `HealthScanner.__init__(detectors=None)` initializes 5 default detectors: `GhostDaemonsDetector`, `ContextRotDetector`, `EcosystemPollutionDetector`, `SecretZeroDetector`, `PromptFatigueDetector`.
   - `HealthScanner.scan_workspace(workspace_root: str) -> List[AnomalyRecord]` executes sequential read-only scans, isolates detector exceptions (`scanner.py:71-77`), and records duration in `_last_duration_ms` accessed via `get_last_duration_ms()`.

2. **SQLite Telemetry & Historical Lifelines (`database.py:78-430`)**:
   - `init_db(db_path)` enables WAL mode, foreign keys, 5000ms busy timeout, and auto-seeds the 5 historical lifelines:
     - `GHOST_DAEMONS_WINERROR_10048` (`CRITICAL`, ports 3000/8000/8501)
     - `CONTEXT_ROT_PLANNING_ARTIFACTS` (`MEDIUM`, >24h planning artifacts)
     - `ECOSYSTEM_POLLUTION_DISABLED_PLUGINS` (`HIGH`, `.disabled` directories)
     - `SECRET_ZERO_PLACEHOLDER_KEYS` (`CRITICAL`, `your_token_here` in `.env`)
     - `PROMPT_FATIGUE_MANIFEST_BLOAT` (`MEDIUM`, `GEMINI.md` > 100 lines)
   - `log_scan_session(session_id, anomalies, gradients, duration_ms, db_path, entropy_score)` atomically logs session metadata, anomalies, and textual gradients within a transaction.
   - `get_historical_drift(db_path)` aggregates `total_sessions`, `total_anomalies`, `average_duration_ms`, `average_entropy_score`, `detector_distribution`, `severity_distribution`, and `drift_detected`.

3. **NumPy ML Clustering & ProTeGi Textual Gradients (`ml/`)**:
   - `ml.embeddings.vectorize_anomalies(anomalies) -> np.ndarray` vectorizes anomalies into a normalized 5-dimensional feature matrix `[severity, detector_type, age_normalized, footprint_normalized, confidence]`.
   - `ml.clustering.kmeans_cluster(X, k=3, random_state=42) -> (labels, centroids, inertia)` performs localized $K=3$ clustering in <2ms without scikit-learn.
   - `ml.clustering.compute_semantic_entropy(X, labels, centroids) -> float` calculates intra-cluster dispersion score in `[0.0, 1.0]`.
   - `ml.protegi.generate_textual_gradients(anomalies, labels, centroids, entropy) -> List[str]` produces actionable rule refinement guidance.

4. **Architecture Red-Team Scrutiny & HITL Report Builder (`audit/`)**:
   - `ArchitectureRedTeam.audit_batch(anomalies, gradients)` evaluates findings across System Integrity, Data Loss Risk, and False Positive Filtering, emitting `RedTeamVerdict.APPROVED`, `CHALLENGED`, or `REJECTED`.
   - `DailyReportBuilder.build_daily_report(...) -> str` builds a 6-section Markdown report featuring interactive HITL checkboxes (`- [ ] [HITL-APPROVED]`), executive telemetry, red-team critiques, 5 historical lifelines, ProTeGi gradients, and non-destructive manual commands.

5. **Shared Pytest Infrastructure (`tests/conftest.py:19-61`)**:
   - `FileSystemSnapshot(root_dir)` computes SHA-256 hashes of all files in a directory tree.
   - `snapshot.assert_untouched()` raises `AssertionError` if any file is added, removed, or modified.
   - Fixtures available: `isolated_workspace`, `mock_db`, `sample_anomalies`.

6. **Static AST Safety Guardrails (`safety_guardrails.py:86-312`)**:
   - Static AST analyzer guarantees 0-destruction (`os.remove`, `shutil.rmtree`, `taskkill`, `kill`, `rm -rf`, `DROP`, `TRUNCATE`).

---

## 2. Logic Chain

1. **Integration Test Scope & Target Design**:
   - To thoroughly validate `scanner_daemon.py` without coupling tests to external networks or OS state, `tests/test_scanner_daemon.py` must test the entire top-level orchestration lifecycle:
     ```
     Target Workspace -> HealthScanner -> 5 Anomaly Detectors -> Feature Vectorization -> NumPy K-Means ($K=3$)
     -> Semantic Entropy -> ProTeGi Gradients -> Architecture Red-Team Scrutiny -> SQLite Persistence -> Daily HITL Report
     ```

2. **Mock Workspace Factory**:
   - A dedicated pytest fixture/helper `mock_workspace_with_all_anomalies(ws_path, bound_port)` deterministically generates all 5 anomaly types:
     - `127.0.0.1:<port>`: Socket listener or loopback port binding (Ghost Daemons)
     - `.agents/worker_stale/progress.md`: 50h old planning artifact (Context Rot)
     - `plugins/unused_feature.disabled/` and `sports_cards/preview.mp4`: `.disabled` directory & cross-track leak (Ecosystem Pollution)
     - `.env`: `API_SECRET=your_token_here` (Secret Zero)
     - `GEMINI.md`: 130 lines with duplicate section tags (Prompt Fatigue)

3. **End-to-End Execution Verification**:
   - `test_e2e_daemon_mock_workspace()` tests full pipeline execution:
     - Asserts `OptimizationReport` returned contains $\ge 5$ anomalies spanning all 5 `DetectorType` enums.
     - Asserts $K=3$ clustering assigns valid cluster labels and calculates entropy $\in [0.0, 1.0]$.
     - Asserts Red-Team generates audit results for every anomaly with zero destructive approvals.
     - Asserts SQLite database contains `scan_sessions`, `anomalies`, `textual_gradients`, and the 5 seeded `historical_lifelines`.
     - Asserts the output Markdown report contains all 6 mandatory sections and interactive checkboxes (`- [ ] [HITL-APPROVED]`).

4. **CLI Invocations**:
   - `test_cli_run_once`: Tests standalone CLI execution via `main(["--once", "--workspace", ..., "--db-path", ..., "--output-report", ...])` returning exit code `0`.
   - `test_cli_custom_workspace`: Verifies `--workspace` targets the specified directory.
   - `test_cli_custom_db_and_output`: Verifies custom database and markdown report paths in nested subdirectories are created and populated.

5. **Multi-Session Drift & Idempotency**:
   - `test_daemon_idempotency_and_drift_tracking`: Running the daemon twice against the same workspace:
     - Verifies session count increments (`total_sessions == 2`).
     - Verifies `historical_lifelines` remains exactly 5 records (idempotent seeding).
     - Verifies drift metrics in SQLite and in Section 4 of the report reflect the cumulative 2-session history.

6. **0-Destruction Cryptographic Invariance**:
   - `test_daemon_zero_destruction_cryptographic_snapshot`: Takes `FileSystemSnapshot` of the target workspace before running the daemon and verifies `snapshot.assert_untouched()` after completion.

---

## 3. Caveats

1. **Ghost Daemon Port Binding**: In restricted CI/Windows environments, binding port 3000 may encounter permission or existing socket issues. The test fixture uses ephemeral loopback binding (`server_sock.bind(("127.0.0.1", 0))`) or mocks `GhostDaemonsDetector(monitored_ports=[bound_port])` to ensure 100% deterministic test execution without socket collisions.
2. **Path Separators**: Workspace paths and target paths in anomaly descriptions must normalize Windows backslashes (`\`) to forward slashes (`/`) for cross-platform consistency.
3. **Database Concurrency & Temp Files**: All tests should use temporary directories (`tmp_path`) for databases and output markdown reports to prevent cross-test contamination.
4. **Read-Only Discipline**: All test fixtures and daemon operations must write outputs (`*.db`, `*.md`) to designated output paths outside the scanned target directory, preserving workspace immutability.

---

## 4. Conclusion: Complete Drop-In Blueprint for `tests/test_scanner_daemon.py`

Below is the complete, drop-in implementation blueprint for `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_scanner_daemon.py`:

```python
"""Integration and CLI test suite for Antigravity Daily Health Scanner & ML Optimization Daemon (`scanner_daemon.py`).

Milestone 5 Test Suite covering:
1. End-to-End full scan cycle against mock workspace (all 5 anomaly types, K=3 clustering, ProTeGi gradients, Red-Team audit, SQLite persistence, 6-section HITL report).
2. CLI execution tests (--once, --workspace, --db-path, --output-report).
3. Multi-session drift tracking and database idempotency.
4. Cryptographic SHA-256 FileSystemSnapshot 0-destruction verification.
5. Error isolation, clean workspace handling, and boundary conditions.
"""

import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Tuple
import pytest

# Ensure .agents/cron is in sys.path
CRON_DIR = Path(__file__).resolve().parent.parent
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

from audit.red_team import ArchitectureRedTeam
from audit.report_builder import DailyReportBuilder
from config import (
    CONTEXT_ROT_THRESHOLD_HOURS,
    DEFAULT_DB_PATH,
    DEFAULT_K_CLUSTERS,
    MONITORED_PORTS,
    PROMPT_FATIGUE_MAX_LINES,
    WHITELISTED_FILENAMES,
)
from database import (
    get_anomalies_for_session,
    get_historical_drift,
    get_historical_lifelines,
    get_session,
    get_textual_gradients_for_session,
    init_db,
)
from detectors.ghost_daemons import GhostDaemonsDetector
from models import (
    AnomalyRecord,
    DetectorType,
    OptimizationReport,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)
from scanner import HealthScanner
from scanner_daemon import HealthScanDaemon, main, run_scan_cycle
from tests.conftest import FileSystemSnapshot


# =============================================================================
# Mock Workspace Fixtures
# =============================================================================

@pytest.fixture
def mock_ghost_daemon_socket() -> Generator[Tuple[socket.socket, int], None, None]:
    """Binds an ephemeral TCP socket on loopback to simulate an unmonitored ghost daemon."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    bound_port = server_sock.getsockname()[1]
    try:
        yield server_sock, bound_port
    finally:
        server_sock.close()


@pytest.fixture
def populated_mock_workspace(
    tmp_path: Path, mock_ghost_daemon_socket: Tuple[socket.socket, int]
) -> Tuple[Path, int]:
    """Constructs a deterministic mock workspace containing all 5 anomaly types."""
    _, bound_port = mock_ghost_daemon_socket
    ws = tmp_path / "mock_antigravity_workspace"
    ws.mkdir(parents=True, exist_ok=True)

    # 1. Anomaly: Context Rot (>24h planning artifact)
    agents_dir = ws / ".agents" / "worker_stale"
    agents_dir.mkdir(parents=True, exist_ok=True)
    stale_file = agents_dir / "progress.md"
    stale_file.write_text("# Worker 1 Progress\n- Task 1: Stale in-flight work", encoding="utf-8")
    stale_mtime = time.time() - (52.0 * 3600.0)  # 52 hours old (>48h for red-team approval)
    os.utime(str(stale_file), (stale_mtime, stale_mtime))

    # 2. Anomaly: Ecosystem Pollution (.disabled plugin + cross-track leak)
    plugins_dir = ws / "plugins" / "gcp_spark.disabled"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / "SKILL.md").write_text("# Spark Skill\nDisabled plugin.", encoding="utf-8")

    sports_track = ws / "sports_cards"
    sports_track.mkdir(parents=True, exist_ok=True)
    (sports_track / "unrelated_video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")

    # 3. Anomaly: Secret Zero (Unresolved placeholder token in .env)
    env_file = ws / ".env"
    env_file.write_text(
        "PORT=3000\nAPI_KEY=your_token_here\nDATABASE_URL=postgres://user:YOUR_API_KEY_HERE@localhost:5432/db\n",
        encoding="utf-8",
    )

    # 4. Anomaly: Prompt Fatigue (GEMINI.md > 100 lines + duplicate rule section)
    gemini_file = ws / "GEMINI.md"
    manifest_lines = [
        "# Antigravity Global Steering & Workspace Manifest",
        "<system>",
        "## Permanent System Instructions",
        "</system>",
        "## R1. Workflow Distillation Directive",
        "Distill workflows into permanent skills.",
        "## R2. The Zero-Discretion Mandate",
        "Trustless execution protocol.",
        "## R1. Workflow Distillation Directive",  # Duplicate section
        "Duplicate rule text.",
    ]
    for i in range(120):
        manifest_lines.append(f"## Procedural Directive {i}\nDetailed steering directive line {i}.")
    gemini_file.write_text("\n".join(manifest_lines), encoding="utf-8")

    # 5. Whitelisted Valid Files (Must NOT be flagged as context rot or deleted)
    (ws / "PROJECT.md").write_text("# Project Specification\nSystem spec.", encoding="utf-8")
    (ws / "README.md").write_text("# Readme\nProject overview.", encoding="utf-8")

    return ws, bound_port


# =============================================================================
# 1. End-to-End Integration Tests
# =============================================================================

def test_e2e_daemon_mock_workspace_full_pipeline(
    tmp_path: Path, populated_mock_workspace: Tuple[Path, int]
) -> None:
    """1. End-to-End test verifying the complete daemon execution against a mock workspace.

    Asserts:
    - All 5 anomaly types are detected.
    - K-Means clusters anomalies ($K=3$) and calculates semantic entropy in [0.0, 1.0].
    - ProTeGi generates actionable textual gradients.
    - Architecture Red-Team scrutinizes anomalies with 3-tier verdicts.
    - Findings and telemetry are persisted to SQLite (sessions, anomalies, gradients, lifelines).
    - Daily HITL Markdown report is generated with all 6 mandatory sections and interactive checkboxes.
    """
    ws_path, bound_port = populated_mock_workspace
    db_path = str(tmp_path / "telemetry_e2e.db")
    report_path = str(tmp_path / "reports" / "daily_health_report.md")

    # Create custom detectors list using the bound ephemeral port for GhostDaemonsDetector
    custom_detectors = [
        GhostDaemonsDetector(monitored_ports=[bound_port], probe_timeout_s=0.2),
    ]

    report = run_scan_cycle(
        workspace_root=str(ws_path),
        db_path=db_path,
        report_path=report_path,
        k_clusters=3,
        custom_detectors=custom_detectors,
    )

    # 1.1 Assert Anomaly Detection across all 5 types
    assert isinstance(report, OptimizationReport)
    assert report.total_anomalies >= 5
    assert report.duration_ms > 0.0

    detected_types = {
        res.anomaly.detector_type for res in report.audited_anomalies if res.anomaly
    }
    assert DetectorType.GHOST_DAEMONS in detected_types
    assert DetectorType.CONTEXT_ROT in detected_types
    assert DetectorType.ECOSYSTEM_POLLUTION in detected_types
    assert DetectorType.SECRET_ZERO in detected_types
    assert DetectorType.PROMPT_FATIGUE in detected_types

    # 1.2 Assert ML Clustering & Textual Gradients
    assert 0.0 <= report.entropy_score <= 1.0
    assert len(report.textual_gradients) >= 3
    joined_gradients = " ".join(report.textual_gradients)
    assert any(
        dt.value in joined_gradients
        for dt in [DetectorType.GHOST_DAEMONS, DetectorType.CONTEXT_ROT, DetectorType.SECRET_ZERO]
    )

    # 1.3 Assert Red-Team Scrutiny
    assert len(report.audited_anomalies) == report.total_anomalies
    verdicts = {res.verdict for res in report.audited_anomalies}
    assert RedTeamVerdict.APPROVED in verdicts or RedTeamVerdict.CHALLENGED in verdicts
    assert report.approved_count + report.challenged_count <= report.total_anomalies

    # 1.4 Assert SQLite Persistence
    session_row = get_session(report.session_id, db_path)
    assert session_row is not None
    assert session_row["session_id"] == report.session_id
    assert session_row["total_anomalies"] == report.total_anomalies
    assert session_row["duration_ms"] == report.duration_ms

    stored_anomalies = get_anomalies_for_session(report.session_id, db_path)
    assert len(stored_anomalies) == report.total_anomalies

    stored_gradients = get_textual_gradients_for_session(report.session_id, db_path)
    assert len(stored_gradients) == len(report.textual_gradients)

    lifelines = get_historical_lifelines(db_path)
    assert len(lifelines) == 5

    # 1.5 Assert Daily Markdown Report File Output
    assert os.path.exists(report_path)
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()

    assert "# Daily System Health & Optimization Report" in report_content
    assert "## 1. Executive Summary & Health Telemetry" in report_content
    assert "## 2. Red-Team Scrutiny Verdicts" in report_content
    assert "## 3. Proposed Optimizations (HITL Checkboxes)" in report_content
    assert "## 4. Historical Failure Lifelines & Drift Analytics" in report_content
    assert "## 5. ProTeGi Textual Gradients for Self-Improvement" in report_content
    assert "## 6. Manual Remediation Command Guide" in report_content
    assert "- [ ] [HITL-APPROVED]" in report_content
    assert report.session_id in report_content


# =============================================================================
# 2. CLI Execution Tests
# =============================================================================

def test_cli_run_once(tmp_path: Path, populated_mock_workspace: Tuple[Path, int]) -> None:
    """2. Tests standalone CLI execution with --once flag returning exit code 0."""
    ws_path, bound_port = populated_mock_workspace
    db_path = str(tmp_path / "cli_test.db")
    report_path = str(tmp_path / "cli_report.md")

    argv = [
        "--workspace", str(ws_path),
        "--db-path", db_path,
        "--output-report", report_path,
        "--once",
    ]

    exit_code = main(argv)
    assert exit_code == 0
    assert os.path.exists(db_path)
    assert os.path.exists(report_path)


def test_cli_custom_workspace(tmp_path: Path) -> None:
    """3. Tests CLI execution against a custom clean workspace vs populated workspace."""
    clean_ws = tmp_path / "clean_workspace"
    clean_ws.mkdir()
    (clean_ws / "README.md").write_text("# Clean Workspace", encoding="utf-8")

    db_path = str(tmp_path / "clean_test.db")
    report_path = str(tmp_path / "clean_report.md")

    argv = [
        "--workspace", str(clean_ws),
        "--db-path", db_path,
        "--output-report", report_path,
        "--once",
    ]

    exit_code = main(argv)
    assert exit_code == 0

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Total Anomalies Detected**: `0`" in content or "All telemetry metrics nominal" in content


def test_cli_custom_db_and_output(tmp_path: Path, populated_mock_workspace: Tuple[Path, int]) -> None:
    """4. Tests CLI with nested custom output paths for DB and Markdown report."""
    ws_path, _ = populated_mock_workspace
    custom_db = str(tmp_path / "custom" / "nested" / "telemetry_custom.db")
    custom_report = str(tmp_path / "custom" / "nested" / "reports" / "report_custom.md")

    argv = [
        "--workspace", str(ws_path),
        "--db-path", custom_db,
        "--output-report", custom_report,
        "--once",
    ]

    exit_code = main(argv)
    assert exit_code == 0
    assert os.path.exists(custom_db)
    assert os.path.exists(custom_report)


# =============================================================================
# 3. Idempotency & Historical Drift Tests
# =============================================================================

def test_daemon_idempotency_and_drift_tracking(
    tmp_path: Path, populated_mock_workspace: Tuple[Path, int]
) -> None:
    """5. Tests running the daemon multiple times against the same workspace.

    Asserts:
    - Scan sessions increment (session 1 -> session 2).
    - Historical lifelines remain exactly 5 (idempotent seeding without duplicates).
    - Historical drift analytics calculate multi-session trends accurately.
    """
    ws_path, bound_port = populated_mock_workspace
    db_path = str(tmp_path / "telemetry_drift.db")
    report_path_1 = str(tmp_path / "report_cycle_1.md")
    report_path_2 = str(tmp_path / "report_cycle_2.md")

    custom_detectors = [
        GhostDaemonsDetector(monitored_ports=[bound_port], probe_timeout_s=0.2),
    ]

    # First cycle
    rep1 = run_scan_cycle(
        workspace_root=str(ws_path),
        db_path=db_path,
        report_path=report_path_1,
        custom_detectors=custom_detectors,
    )
    drift1 = get_historical_drift(db_path)
    assert drift1["total_sessions"] == 1
    assert drift1["total_anomalies"] == rep1.total_anomalies

    # Second cycle
    rep2 = run_scan_cycle(
        workspace_root=str(ws_path),
        db_path=db_path,
        report_path=report_path_2,
        custom_detectors=custom_detectors,
    )
    assert rep1.session_id != rep2.session_id

    drift2 = get_historical_drift(db_path)
    assert drift2["total_sessions"] == 2
    assert drift2["total_anomalies"] == rep1.total_anomalies + rep2.total_anomalies
    assert drift2["drift_detected"] is True

    # Verify 5 historical lifelines were NOT duplicated
    lifelines = get_historical_lifelines(db_path)
    assert len(lifelines) == 5

    # Verify second report includes 2 total recorded sessions in Section 4
    with open(report_path_2, "r", encoding="utf-8") as f:
        content2 = f.read()
    assert "Total Recorded Sessions**: `2`" in content2


# =============================================================================
# 4. 0-Destruction Cryptographic SHA-256 Snapshot Test
# =============================================================================

def test_daemon_zero_destruction_cryptographic_snapshot(
    tmp_path: Path, populated_mock_workspace: Tuple[Path, int]
) -> None:
    """6. Cryptographically verifies that daemon execution never modifies target workspace files.

    Takes a SHA-256 hash of all files before execution and asserts snapshot.assert_untouched()
    after full daemon execution.
    """
    ws_path, bound_port = populated_mock_workspace
    db_path = str(tmp_path / "telemetry_snapshot.db")
    report_path = str(tmp_path / "report_snapshot.md")

    # Take cryptographic snapshot of target workspace
    snapshot = FileSystemSnapshot(str(ws_path))

    custom_detectors = [
        GhostDaemonsDetector(monitored_ports=[bound_port], probe_timeout_s=0.2),
    ]

    # Run full scan cycle
    report = run_scan_cycle(
        workspace_root=str(ws_path),
        db_path=db_path,
        report_path=report_path,
        custom_detectors=custom_detectors,
    )
    assert report.total_anomalies > 0

    # Cryptographically verify zero files were added, deleted, or altered
    snapshot.assert_untouched()


# =============================================================================
# 5. Resilience, Error Isolation & Boundary Tests
# =============================================================================

def test_daemon_handles_empty_or_clean_workspace(tmp_path: Path) -> None:
    """7. Tests daemon execution on a sterile empty workspace."""
    empty_ws = tmp_path / "empty_workspace"
    empty_ws.mkdir()
    db_path = str(tmp_path / "empty.db")
    report_path = str(tmp_path / "empty_report.md")

    report = run_scan_cycle(
        workspace_root=str(empty_ws),
        db_path=db_path,
        report_path=report_path,
    )

    assert report.total_anomalies == 0
    assert report.approved_count == 0
    assert report.challenged_count == 0
    assert len(report.textual_gradients) >= 1
    assert "Convergence" in report.textual_gradients[0]

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "All telemetry metrics nominal" in content


def test_daemon_detector_exception_resilience(tmp_path: Path) -> None:
    """8. Tests daemon resilience when a custom detector raises an unhandled exception."""
    ws = tmp_path / "resilient_ws"
    ws.mkdir()
    (ws / ".env").write_text("TOKEN=your_token_here\n", encoding="utf-8")

    class CrashingDetector(GhostDaemonsDetector):
        def scan(self, workspace_root: str) -> List[AnomalyRecord]:
            raise ConnectionResetError("Simulated unhandled network crash")

    db_path = str(tmp_path / "resilient.db")
    report_path = str(tmp_path / "resilient_report.md")

    # Scanner should catch exception in CrashingDetector and still detect SecretZero
    report = run_scan_cycle(
        workspace_root=str(ws),
        db_path=db_path,
        report_path=report_path,
        custom_detectors=[CrashingDetector()],
    )

    assert report.total_anomalies >= 1
    assert any(a.anomaly and a.anomaly.detector_type == DetectorType.SECRET_ZERO for a in report.audited_anomalies)
    assert os.path.exists(report_path)
```

---

## 5. Verification Method

To independently verify this specification and blueprint:

### 5.1 Verification Commands
```powershell
# 1. Verify AST Safety across the entire .agents/cron codebase
pytest "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_safety_ast.py" -v

# 2. Verify all underlying module unit and integration tests
pytest "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_database.py" -v
pytest "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_detectors.py" -v
pytest "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_ml_clustering.py" -v
pytest "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_red_team_and_report.py" -v

# 3. Once scanner_daemon.py and test_scanner_daemon.py are created:
pytest "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_scanner_daemon.py" -v
```

### 5.2 Invalidation Conditions
This design would be invalidated if:
1. `scanner_daemon.py` fails to expose `run_scan_cycle(...)` or `main(argv)`.
2. Any detector in `HealthScanner` modifies files in `workspace_root`, causing `snapshot.assert_untouched()` to fail.
3. Historical failure lifelines are duplicated upon multiple scan cycles instead of remaining strictly 5 records.
4. The generated Daily Markdown report omits any of the 6 mandatory sections or lacks interactive `- [ ] [HITL-APPROVED]` checkboxes.
