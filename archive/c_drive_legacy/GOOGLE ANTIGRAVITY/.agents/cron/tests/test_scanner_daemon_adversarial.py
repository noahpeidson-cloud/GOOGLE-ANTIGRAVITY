"""Adversarial stress-test suite for Antigravity Scanner Daemon CLI and Daemon Orchestration.

Tests:
- CLI argument fuzzing, invalid flags, missing parameters, --help
- Concurrent multi-process and multi-threaded daemon invocations under SQLite WAL mode
- Rapid sequential scans and multi-session drift analytics aggregation
- Non-existent, empty, deeply nested, unicode, and special-character workspaces
- Cryptographic SHA-256 workspace immutability (0-destruction guarantee)
- Daemon KeyboardInterrupt simulation and SDK trigger execution (both SDK trigger and fallback)
- K-Means cluster count boundary conditions (k=1, k=5, k=10 with varying anomaly counts)
"""

import asyncio
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, List
import pytest

CRON_DIR = Path(__file__).resolve().parent.parent
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

from audit.red_team import ArchitectureRedTeam
from config import DEFAULT_DB_PATH, DEFAULT_K_CLUSTERS
from database import (
    get_anomalies_for_session,
    get_historical_drift,
    get_historical_lifelines,
    get_session,
    get_textual_gradients_for_session,
    init_db,
)
from detectors.context_rot import ContextRotDetector
from detectors.ecosystem_pollution import EcosystemPollutionDetector
from detectors.ghost_daemons import GhostDaemonsDetector
from detectors.prompt_fatigue import PromptFatigueDetector
from detectors.secret_zero import SecretZeroDetector
from fixtures.mock_workspace_factory import MockDaemonListener, create_mock_workspace
from models import (
    AnomalyRecord,
    DetectorType,
    OptimizationReport,
    RedTeamAuditResult,
    RedTeamVerdict,
    Severity,
)
from scanner import HealthScanner
from scanner_daemon import (
    build_cli_parser,
    create_antigravity_sdk_trigger,
    main,
    run_health_scan,
)
from tests.conftest import FileSystemSnapshot


def create_isolated_scanner(ephemeral_ports: List[int] = (59971, 59972)) -> HealthScanner:
    """Helper creating a HealthScanner with inactive ephemeral ports to prevent host port bleeding."""
    return HealthScanner(
        detectors=[
            GhostDaemonsDetector(monitored_ports=list(ephemeral_ports)),
            ContextRotDetector(),
            EcosystemPollutionDetector(),
            SecretZeroDetector(),
            PromptFatigueDetector(),
        ]
    )


# =============================================================================
# 1. CLI Argument Fuzzing & Stress Tests
# =============================================================================
def test_cli_fuzzing_unknown_flags(tmp_path: Path) -> None:
    """Stress-test CLI with unknown/prohibited flags, expecting argparse exit code 2."""
    daemon_script = CRON_DIR / "scanner_daemon.py"
    invalid_flag_combos = [
        ["--invalid-flag"],
        ["--destroy-everything"],
        ["--force-kill"],
        ["--drop-db"],
        ["--rm", "-rf"],
        ["--workspace"],  # missing required argument value
        ["--interval", "not_an_int"],
        ["--k-clusters", "invalid_cluster_val"],
    ]

    for combo in invalid_flag_combos:
        cmd = [sys.executable, str(daemon_script)] + combo
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert res.returncode == 2, f"Expected returncode 2 for invalid args {combo}, got {res.returncode}"
        assert "error:" in res.stderr.lower() or "usage:" in res.stderr.lower()


def test_cli_help_flag() -> None:
    """Verifies that --help and -h cleanly exit with code 0 and describe daemon flags."""
    daemon_script = CRON_DIR / "scanner_daemon.py"
    for help_flag in ["--help", "-h"]:
        cmd = [sys.executable, str(daemon_script), help_flag]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert res.returncode == 0
        assert "Antigravity Daily Health Scanner" in res.stdout
        assert "--run-once" in res.stdout
        assert "--workspace" in res.stdout
        assert "--db" in res.stdout
        assert "--output-dir" in res.stdout
        assert "--mock-env" in res.stdout


def test_cli_mock_env_standalone_execution(tmp_path: Path) -> None:
    """Tests executing --run-once with --mock-env flag via CLI."""
    daemon_script = CRON_DIR / "scanner_daemon.py"
    db_path = tmp_path / "mock_cli.db"
    out_dir = tmp_path / "mock_cli_reports"

    cmd = [
        sys.executable,
        str(daemon_script),
        "--run-once",
        "--mock-env",
        "--db",
        str(db_path),
        "--output-dir",
        str(out_dir),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "Created mock workspace environment at:" in res.stderr or "Created mock workspace environment at:" in res.stdout
    assert "ANTIGRAVITY HEALTH SCAN COMPLETE:" in res.stdout
    assert "Total Anomalies Detected :" in res.stdout

    created_reports = list(out_dir.glob("daily_health_report_*.md"))
    assert len(created_reports) == 1
    assert created_reports[0].stat().st_size > 500


# =============================================================================
# 2. Concurrency & Multi-Process / Multi-Threaded Stress Tests
# =============================================================================
def test_concurrent_multithreaded_scans_same_database(tmp_path: Path) -> None:
    """Stress-test: 10 parallel threads executing run_health_scan concurrently against ONE SQLite DB."""
    ws_dir = tmp_path / "shared_workspace"
    db_path = tmp_path / "shared_concurrency.db"
    out_dir = tmp_path / "shared_reports"

    create_mock_workspace(str(ws_dir))
    init_db(str(db_path))

    num_threads = 10
    reports = []
    errors = []

    def _worker(thread_idx: int):
        try:
            rep, path = run_health_scan(
                workspace_root=str(ws_dir),
                db_path=str(db_path),
                output_dir=str(out_dir),
                session_id=f"concurrent_thread_scan_{thread_idx}_{int(time.time()*1000)}",
            )
            return rep, path
        except Exception as e:
            return None, str(e)

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(_worker, i) for i in range(num_threads)]
        for f in as_completed(futures):
            rep, path_or_err = f.result()
            if rep is not None:
                reports.append(rep)
            else:
                errors.append(path_or_err)

    assert len(errors) == 0, f"Encountered thread errors: {errors}"
    assert len(reports) == num_threads

    # Verify that all 10 sessions are present in the SQLite database
    drift = get_historical_drift(db_path=str(db_path))
    assert drift["total_sessions"] == num_threads
    assert drift["historical_lifelines_count"] == 5

    # Verify report files were generated
    created_reports = list(out_dir.glob("daily_health_report_*.md"))
    assert len(created_reports) >= 1


def test_concurrent_multiprocess_cli_execution(tmp_path: Path) -> None:
    """Stress-test: 4 parallel subprocesses executing scanner_daemon.py against ONE SQLite DB."""
    ws_dir = tmp_path / "proc_workspace"
    db_path = tmp_path / "proc_concurrency.db"
    out_dir = tmp_path / "proc_reports"

    create_mock_workspace(str(ws_dir))
    daemon_script = CRON_DIR / "scanner_daemon.py"

    num_procs = 4
    commands = [
        [
            sys.executable,
            str(daemon_script),
            "--run-once",
            "--workspace",
            str(ws_dir),
            "--db",
            str(db_path),
            "--output-dir",
            str(out_dir),
        ]
        for _ in range(num_procs)
    ]

    procs = [
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for cmd in commands
    ]

    for p in procs:
        stdout, stderr = p.communicate()
        assert p.returncode == 0, f"Subprocess failed with code {p.returncode}: {stderr}"
        assert "ANTIGRAVITY HEALTH SCAN COMPLETE:" in stdout

    drift = get_historical_drift(db_path=str(db_path))
    assert drift["total_sessions"] == num_procs
    assert drift["historical_lifelines_count"] == 5


# =============================================================================
# 3. Multi-Session Drift & Sequential Telemetry Stress Tests
# =============================================================================
def test_rapid_sequential_drift_accumulation_20_sessions(tmp_path: Path) -> None:
    """Stress-test: 20 sequential scans testing cumulative drift metrics and database integrity."""
    ws_dir = tmp_path / "drift_seq_workspace"
    db_path = tmp_path / "drift_seq.db"
    out_dir = tmp_path / "drift_seq_reports"

    create_mock_workspace(str(ws_dir))
    init_db(str(db_path))

    total_sessions_to_run = 20
    accumulated_anomalies = 0

    for i in range(total_sessions_to_run):
        rep, _ = run_health_scan(
            workspace_root=str(ws_dir),
            db_path=str(db_path),
            output_dir=str(out_dir),
            session_id=f"seq_scan_{i:03d}",
        )
        assert rep.session_id == f"seq_scan_{i:03d}"
        assert rep.total_anomalies > 0
        accumulated_anomalies += rep.total_anomalies

    drift = get_historical_drift(db_path=str(db_path))
    assert drift["total_sessions"] == total_sessions_to_run
    assert drift["total_anomalies"] == accumulated_anomalies
    assert drift["historical_lifelines_count"] == 5
    assert drift["average_duration_ms"] > 0.0
    assert 0.0 <= drift["average_entropy_score"] <= 1.0
    assert drift["drift_detected"] is True
    assert len(drift["detector_distribution"]) > 0


def test_drift_transition_empty_to_populated_to_empty(tmp_path: Path) -> None:
    """Tests drift analytics when workspace transitions: Empty -> Populated -> Empty."""
    ws_dir = tmp_path / "dynamic_ws"
    ws_dir.mkdir(parents=True)
    db_path = tmp_path / "dynamic.db"
    out_dir = tmp_path / "dynamic_reports"

    isolated_scanner = create_isolated_scanner()

    # Scan 1: Empty workspace (0 anomalies)
    rep1, _ = run_health_scan(
        workspace_root=str(ws_dir),
        db_path=str(db_path),
        output_dir=str(out_dir),
        session_id="dynamic_01_empty",
        custom_scanner=isolated_scanner,
    )
    assert rep1.total_anomalies == 0

    # Populate workspace with mock fixtures
    create_mock_workspace(str(ws_dir))

    # Scan 2: Populated workspace (N anomalies)
    rep2, _ = run_health_scan(
        workspace_root=str(ws_dir),
        db_path=str(db_path),
        output_dir=str(out_dir),
        session_id="dynamic_02_populated",
        custom_scanner=isolated_scanner,
    )
    assert rep2.total_anomalies > 0

    # Clean workspace again
    shutil.rmtree(str(ws_dir))
    ws_dir.mkdir(parents=True)

    # Scan 3: Empty workspace again (0 anomalies)
    rep3, _ = run_health_scan(
        workspace_root=str(ws_dir),
        db_path=str(db_path),
        output_dir=str(out_dir),
        session_id="dynamic_03_empty_again",
        custom_scanner=isolated_scanner,
    )
    assert rep3.total_anomalies == 0

    drift = get_historical_drift(db_path=str(db_path))
    assert drift["total_sessions"] == 3
    assert drift["total_anomalies"] == rep2.total_anomalies


# =============================================================================
# 4. Non-Existent, Deeply-Nested, & Unicode Path Stress Tests
# =============================================================================
def test_non_existent_workspace_directory_graceful_handling(tmp_path: Path) -> None:
    """Tests scan against a non-existent directory path; must complete cleanly without crash."""
    non_existent = tmp_path / "does_not_exist_folder_9999"
    db_path = tmp_path / "non_existent.db"
    out_dir = tmp_path / "non_existent_reports"

    isolated_scanner = create_isolated_scanner()

    report, report_path = run_health_scan(
        workspace_root=str(non_existent),
        db_path=str(db_path),
        output_dir=str(out_dir),
        custom_scanner=isolated_scanner,
    )

    assert isinstance(report, OptimizationReport)
    assert report.total_anomalies == 0
    assert report.entropy_score == 0.0
    assert os.path.exists(report_path)


def test_deeply_nested_workspace_directory_scan(tmp_path: Path) -> None:
    """Tests scanning a directory structure 15 levels deep with files at the leaf."""
    ws_dir = tmp_path / "deep_ws"
    current = ws_dir
    for depth in range(15):
        current = current / f"level_{depth:02d}"
    current.mkdir(parents=True)

    # Place a secret zero anomaly at the deepest level
    (current / ".env").write_text("API_KEY=your_token_here\n", encoding="utf-8")

    db_path = tmp_path / "deep.db"
    out_dir = tmp_path / "deep_reports"

    snapshot = FileSystemSnapshot(str(ws_dir))

    report, report_path = run_health_scan(
        workspace_root=str(ws_dir),
        db_path=str(db_path),
        output_dir=str(out_dir),
    )

    assert report.total_anomalies >= 1
    # Verify cryptographic immutability
    snapshot.assert_untouched()


def test_unicode_and_special_characters_in_workspace_paths(tmp_path: Path) -> None:
    """Tests workspace directory containing unicode characters, emojis, brackets, and spaces."""
    ws_dir = tmp_path / "🚀 Workspace (测试) [2026] #1"
    ws_dir.mkdir(parents=True)

    create_mock_workspace(str(ws_dir))
    db_path = tmp_path / "unicode.db"
    out_dir = tmp_path / "unicode_reports"

    snapshot = FileSystemSnapshot(str(ws_dir))

    report, report_path = run_health_scan(
        workspace_root=str(ws_dir),
        db_path=str(db_path),
        output_dir=str(out_dir),
    )

    assert report.total_anomalies > 0
    assert os.path.exists(report_path)
    snapshot.assert_untouched()


# =============================================================================
# 5. K-Means Clustering Boundary Conditions in Daemon
# =============================================================================
def test_kmeans_cluster_count_boundary_conditions(tmp_path: Path) -> None:
    """Tests running daemon with k_clusters=1, k_clusters=5, k_clusters=10."""
    ws_dir = tmp_path / "kmeans_ws"
    db_path = tmp_path / "kmeans.db"
    out_dir = tmp_path / "kmeans_reports"

    create_mock_workspace(str(ws_dir))

    for k in [1, 5, 10]:
        rep, _ = run_health_scan(
            workspace_root=str(ws_dir),
            db_path=str(db_path),
            output_dir=str(out_dir),
            k_clusters=k,
            session_id=f"kmeans_k_{k}",
        )
        assert rep.total_anomalies > 0
        assert 0.0 <= rep.entropy_score <= 1.0
        assert len(rep.textual_gradients) > 0


# =============================================================================
# 6. Daemon KeyboardInterrupt and SDK Trigger Async / Fallback Stress
# =============================================================================
def test_daemon_loop_keyboard_interrupt_clean_exit(tmp_path: Path, monkeypatch) -> None:
    """Verifies that KeyboardInterrupt in daemon loop mode is handled cleanly and exits with code 0."""
    ws_dir = tmp_path / "daemon_loop_ws"
    db_path = tmp_path / "daemon_loop.db"
    out_dir = tmp_path / "daemon_loop_reports"

    create_mock_workspace(str(ws_dir))

    # Monkeypatch time.sleep to raise KeyboardInterrupt after 1st iteration
    call_count = 0

    def mock_sleep(seconds):
        nonlocal call_count
        call_count += 1
        raise KeyboardInterrupt()

    import scanner_daemon
    monkeypatch.setattr(scanner_daemon.time, "sleep", mock_sleep)

    argv = [
        "--workspace",
        str(ws_dir),
        "--db",
        str(db_path),
        "--output-dir",
        str(out_dir),
        "--interval",
        "1",
    ]

    exit_code = main(argv)
    assert exit_code == 0
    assert call_count == 1

    # Verify scan session was successfully executed and persisted before exit
    sess = get_historical_drift(db_path=str(db_path))
    assert sess["total_sessions"] == 1


class MockTriggerContext:
    """Mock TriggerContext for Google Antigravity SDK cron handler."""

    def __init__(self):
        self.sent_messages: List[str] = []

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)


def test_antigravity_sdk_trigger_async_invocation(tmp_path: Path) -> None:
    """Tests invoking the SDK cron handler asynchronously with a TriggerContext."""
    ws_dir = tmp_path / "sdk_trigger_ws"
    db_path = tmp_path / "sdk_trigger.db"
    out_dir = tmp_path / "sdk_trigger_reports"

    create_mock_workspace(str(ws_dir))

    trigger = create_antigravity_sdk_trigger(
        interval_seconds=0.01,
        workspace_root=str(ws_dir),
        db_path=str(db_path),
        output_dir=str(out_dir),
    )

    assert callable(trigger)
    mock_ctx = MockTriggerContext()

    async def _run_one_tick():
        try:
            await asyncio.wait_for(trigger(mock_ctx), timeout=0.2)
        except asyncio.TimeoutError:
            pass

    asyncio.run(_run_one_tick())

    # Verify report was created in SQLite DB and message was sent
    drift = get_historical_drift(db_path=str(db_path))
    assert drift["total_sessions"] >= 1
    assert len(mock_ctx.sent_messages) >= 1
    assert "Antigravity Daily Health Scan Complete:" in mock_ctx.sent_messages[0]

    created_reports = list(out_dir.glob("daily_health_report_*.md"))
    assert len(created_reports) >= 1


def test_antigravity_sdk_fallback_standalone_mode(tmp_path: Path, monkeypatch) -> None:
    """Tests create_antigravity_sdk_trigger fallback path when google.antigravity is not installed."""
    ws_dir = tmp_path / "fallback_mock_ws"
    db_path = tmp_path / "fallback_mock.db"
    out_dir = tmp_path / "fallback_mock_reports"

    create_mock_workspace(str(ws_dir))

    # Temporarily hide google.antigravity
    orig_modules = sys.modules.copy()
    for k in list(sys.modules.keys()):
        if k.startswith("google.antigravity"):
            del sys.modules[k]

    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name.startswith("google.antigravity"):
            raise ImportError("Mock missing google.antigravity")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    trigger = create_antigravity_sdk_trigger(
        interval_seconds=86400,
        workspace_root=str(ws_dir),
        db_path=str(db_path),
        output_dir=str(out_dir),
    )

    assert callable(trigger)
    rep, report_path = trigger()

    assert isinstance(rep, OptimizationReport)
    assert rep.total_anomalies > 0
    assert os.path.exists(report_path)
