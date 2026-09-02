# Milestone 5 Architecture & Implementation Blueprint: `scanner_daemon.py`

## 1. Observation

Direct investigation of the codebase and project specifications revealed the following baseline and interface contracts:

1. **Safety AST Requirements (`safety_guardrails.py:9-79`)**:
   `SafetyASTVisitor` strictly forbids functions such as `os.remove`, `os.unlink`, `os.rmdir`, `shutil.rmtree`, `os.kill`, `subprocess.run` with `taskkill`/`pkill`/`kill`/`rm -rf`, `DROP TABLE`, `TRUNCATE TABLE`, `eval`, `exec`, `importlib.import_module`, and any `.unlink()` / `.rmdir()` calls on paths.
   All filesystem writes must be strictly non-destructive (e.g., `os.makedirs(output_dir, exist_ok=True)` and `with open(report_path, "w", encoding="utf-8") as f: f.write(...)`).

2. **Data Contracts (`models.py:29-155`)**:
   - `AnomalyRecord`: attributes `detector_type` (`DetectorType`), `target_path` (`str`), `severity` (`Severity`), `description` (`str`), `raw_details` (`Dict[str, Any]`), `is_historical` (`bool`), `timestamp` (`int`), `confidence` (`float`).
   - `RedTeamAuditResult`: attributes `anomaly` (`Optional[AnomalyRecord]`), `verdict` (`RedTeamVerdict`: `APPROVED`, `CHALLENGED`, `REJECTED`), `rationale` (`str`), `risk_assessment` (`str`), `recommended_action` (`str`), `confidence` (`float`).
   - `OptimizationReport`: attributes `session_id` (`str`), `timestamp` (`int`), `duration_ms` (`float`), `total_anomalies` (`int`), `approved_count` (`int`), `challenged_count` (`int`), `audited_anomalies` (`List[RedTeamAuditResult]`), `textual_gradients` (`List[str]`), `entropy_score` (`float`).

3. **Database Module (`database.py:78-430`)**:
   - `init_db(db_path: str = DEFAULT_DB_PATH) -> None`: Configures WAL mode, busy timeout 5000ms, creates `scan_sessions`, `anomalies`, `historical_lifelines`, `textual_gradients`, and seeds 5 historical failure lifelines.
   - `log_scan_session(session_id: str, anomalies: list, gradients: list, duration_ms: float, db_path: str, entropy_score: float, timestamp: Optional[int]) -> None`: Logs scan session atomically.
   - `get_historical_drift(db_path: str) -> Dict[str, Any]`: Computes session count, anomaly count, detector distributions, average duration, and historical match counts.

4. **Modular Health Scanner (`scanner.py:27-82`)**:
   - `HealthScanner(detectors=None)`: Instantiates the 5 detectors (`GhostDaemonsDetector`, `ContextRotDetector`, `EcosystemPollutionDetector`, `SecretZeroDetector`, `PromptFatigueDetector`).
   - `scan_workspace(workspace_root: str) -> List[AnomalyRecord]`: Executes read-only scan across all 5 detectors with isolated exception handling.
   - `get_last_duration_ms() -> float`: Returns duration in milliseconds.

5. **ML Vectorization, Clustering & Gradients (`ml/`)**:
   - `embeddings.vectorize_anomalies(anomalies, current_time) -> np.ndarray`: Returns $(N, 5)$ normalized float64 matrix in $[0.0, 1.0]$. Returns $(0, 5)$ if $N=0$.
   - `clustering.kmeans_cluster(X, k=3, max_iter=50, tol=1e-4, random_state=42) -> Tuple[np.ndarray, np.ndarray, float]`: Pure NumPy $K=3$ clustering returning `labels` $(N,)$, `centroids` $(k, 5)$, `inertia`.
   - `clustering.compute_semantic_entropy(X, labels, centroids) -> float`: Calculates normalized intra-cluster dispersion score in $[0.0, 1.0]$.
   - `protegi.generate_textual_gradients(anomalies, labels, centroids, entropy) -> List[str]`: Generates ProTeGi textual gradients for prompt and rule refinement.

6. **Architecture Red-Team & Daily Report Builder (`audit/`)**:
   - `red_team.ArchitectureRedTeam(strict_mode=True)`: `audit_batch(anomalies, gradients) -> List[RedTeamAuditResult]`.
   - `report_builder.DailyReportBuilder()`: `build_daily_report(session_id, scan_time, anomalies, gradients, audit_results, historical_drift, duration_ms, entropy) -> str`.

7. **Google Antigravity SDK Triggers (`google-antigravity-sdk/SKILL.md`)**:
   - SDK periodic triggers use `from google.antigravity.triggers import every, TriggerContext`.
   - Standalone CLI execution must not crash if `google.antigravity` is not installed; it must provide graceful fallback.

8. **Current Test Suite**:
   Running `python -m pytest ".agents/cron/tests"` collected and passed 117 tests across all M1-M4 components in 3.14s with 0 errors.

---

## 2. Logic Chain

1. **Pipeline Composition**:
   The `scanner_daemon.py` module must unify Milestones 1 through 4 into a deterministic, non-destructive 9-step orchestration pipeline:
   - **Step 1 (`init_db`)**: Ensure database tables and the 5 historical failure lifelines exist before scanning begins.
   - **Step 2 (`HealthScanner.scan_workspace`)**: Run read-only scan against the target workspace to gather `anomalies`.
   - **Step 3 (`vectorize_anomalies`)**: Normalize anomaly properties into numerical $(N, 5)$ feature vectors.
   - **Step 4 (`kmeans_cluster` + `compute_semantic_entropy`)**: Cluster vectors ($K=3$) and calculate intra-cluster variance.
   - **Step 5 (`generate_textual_gradients`)**: Formulate actionable rule refinement text for recurring clusters.
   - **Step 6 (`ArchitectureRedTeam.audit_batch`)**: Adversarially evaluate all proposed optimizations, classifying into `APPROVED`, `CHALLENGED`, or `REJECTED`.
   - **Step 7 (`log_scan_session`)**: Atomically record the session telemetry, anomalies, and textual gradients in SQLite.
   - **Step 8 (`get_historical_drift` + `DailyReportBuilder.build_daily_report`)**: Extract 7-day trend metrics and compile the 6-section HITL Markdown report.
   - **Step 9 (Save & Return)**: Save the report to `.agents/reports/daily_health_report_YYYYMMDD_HHMMSS.md` and construct `OptimizationReport`.

2. **Dual-Mode Execution (SDK Cron vs Standalone CLI)**:
   - When running under Antigravity Agent Runtime:
     - `create_antigravity_trigger(interval_seconds=86400)` returns an `every(...)` trigger callback.
     - `@app.cron("0 0 * * *")` or `register_cron(app)` hooks into scheduler frameworks.
   - When running via standalone CLI (`python .agents/cron/scanner_daemon.py --run-once`):
     - Uses standard `argparse` to parse `--run-once`, `--workspace`, `--db`, `--output-dir`, `--interval`, `--max-iterations`, `--mock-env`, and `--json`.
     - In daemon mode (without `--run-once`), executes periodic iterations using `time.sleep`, with clean signal handling (`SIGINT`, `SIGTERM`).
     - Returns exit code `0` on successful completion.

3. **AST Safety Compliance**:
   - Zero destructive operations are used anywhere in `scanner_daemon.py`.
   - Only non-destructive file operations (`os.makedirs(..., exist_ok=True)` and writing report markdown) are performed.

---

## 3. Caveats

1. **Google Antigravity SDK Dependency**:
   The `google.antigravity` package may not be installed in all test environments. The daemon must catch `ImportError` and log an informative warning while remaining 100% operational in standalone CLI mode.
2. **Path Portability**:
   Paths in Windows (`G:\My Drive\...`) vs POSIX require normalized handling (`pathlib.Path` or `os.path.normpath`). Output directories should default to `.agents/reports` relative to workspace root or current directory.
3. **Port Scanning Privileges**:
   Ghost Daemons detector probes TCP ports non-destructively; no administrator privileges are required.

---

## 4. Conclusion & Drop-in Implementation Blueprint

### Blueprint A: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\scanner_daemon.py`

```python
"""Antigravity Daily Health Scanner & ML Optimization Daemon (Milestone 5).

Integrates:
1. Google Antigravity SDK cron registration (@app.cron / triggers.every).
2. Resilient standalone CLI runner (python .agents/cron/scanner_daemon.py --run-once ...).
3. 9-step non-destructive orchestration pipeline (M1-M4 components).
"""

import argparse
import datetime
import logging
import os
import signal
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Ensure package directory is on sys.path for direct CLI invocation
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from config import DEFAULT_DB_PATH
    from database import (
        get_historical_drift,
        init_db,
        log_scan_session,
    )
    from models import (
        AnomalyRecord,
        DetectorType,
        OptimizationReport,
        RedTeamAuditResult,
        RedTeamVerdict,
        Severity,
    )
    from scanner import HealthScanner
    from ml.embeddings import vectorize_anomalies
    from ml.clustering import compute_semantic_entropy, kmeans_cluster
    from ml.protegi import generate_textual_gradients
    from audit.red_team import ArchitectureRedTeam
    from audit.report_builder import DailyReportBuilder
except (ImportError, ValueError):
    from .config import DEFAULT_DB_PATH
    from .database import (
        get_historical_drift,
        init_db,
        log_scan_session,
    )
    from .models import (
        AnomalyRecord,
        DetectorType,
        OptimizationReport,
        RedTeamAuditResult,
        RedTeamVerdict,
        Severity,
    )
    from .scanner import HealthScanner
    from .ml.embeddings import vectorize_anomalies
    from .ml.clustering import compute_semantic_entropy, kmeans_cluster
    from .ml.protegi import generate_textual_gradients
    from .audit.red_team import ArchitectureRedTeam
    from .audit.report_builder import DailyReportBuilder

# Configure module logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scanner_daemon")


# =============================================================================
# 9-Step Non-Destructive Orchestration Pipeline
# =============================================================================

def run_health_scan_pipeline(
    workspace_root: str = ".",
    db_path: str = DEFAULT_DB_PATH,
    output_dir: str = ".agents/reports",
    session_id: Optional[str] = None,
    scanner: Optional[HealthScanner] = None,
    red_team: Optional[ArchitectureRedTeam] = None,
    report_builder: Optional[DailyReportBuilder] = None,
    current_time: Optional[float] = None,
) -> Tuple[OptimizationReport, str]:
    """Executes the complete 9-step non-destructive health scan and ML optimization pipeline.

    Steps:
    1. init_db(db_path) (ensures WAL mode, tables, 5 historical failure seeds).
    2. HealthScanner.scan_workspace(workspace_root) (executes 5 anomaly detectors).
    3. vectorize_anomalies(anomalies) (converts anomalies to (N, 5) float array).
    4. kmeans_cluster(X, k=3) and compute_semantic_entropy(X, labels, centroids).
    5. generate_textual_gradients(anomalies, labels, centroids, entropy).
    6. ArchitectureRedTeam.audit_batch(anomalies, gradients).
    7. log_scan_session(db_path, session_id, scan_time, duration_ms, anomalies, entropy, ...).
    8. get_historical_drift(db_path) and DailyReportBuilder.build_daily_report(...).
    9. Saves report to .agents/reports/daily_health_report_YYYYMMDD_HHMMSS.md and returns OptimizationReport.

    Args:
        workspace_root: Path to workspace root to scan.
        db_path: Path to SQLite telemetry database.
        output_dir: Directory where daily HITL markdown reports will be written.
        session_id: Optional custom session identifier.
        scanner: Optional pre-configured HealthScanner instance.
        red_team: Optional pre-configured ArchitectureRedTeam instance.
        report_builder: Optional pre-configured DailyReportBuilder instance.
        current_time: Optional unix timestamp for deterministic testing.

    Returns:
        Tuple of (OptimizationReport, report_file_path).
    """
    scan_start_perf = time.perf_counter()
    scan_ts = current_time if current_time is not None else time.time()
    dt_now = datetime.datetime.fromtimestamp(scan_ts, datetime.timezone.utc)
    ts_str = dt_now.strftime("%Y%m%d_%H%M%S")

    if not session_id:
        rand_suffix = uuid.uuid4().hex[:8]
        session_id = f"session_{ts_str}_{rand_suffix}"

    logger.info("Starting Health Scan Session '%s' for workspace '%s'", session_id, workspace_root)

    # -------------------------------------------------------------------------
    # Step 1: Initialize Database & Seed Historical Lifelines
    # -------------------------------------------------------------------------
    logger.debug("[Step 1/9] Initializing database at %s", db_path)
    init_db(db_path)

    # -------------------------------------------------------------------------
    # Step 2: Modular Health Scanner Execution
    # -------------------------------------------------------------------------
    logger.debug("[Step 2/9] Executing 5 read-only anomaly detectors...")
    active_scanner = scanner if scanner is not None else HealthScanner()
    anomalies: List[AnomalyRecord] = active_scanner.scan_workspace(workspace_root)
    logger.info("[Step 2/9] Detected %d anomalies in workspace", len(anomalies))

    # -------------------------------------------------------------------------
    # Step 3: Feature Vectorization
    # -------------------------------------------------------------------------
    logger.debug("[Step 3/9] Vectorizing %d anomalies into (N, 5) feature matrix...", len(anomalies))
    X = vectorize_anomalies(anomalies, current_time=scan_ts)

    # -------------------------------------------------------------------------
    # Step 4: K-Means Clustering & Semantic Entropy Analysis
    # -------------------------------------------------------------------------
    logger.debug("[Step 4/9] Performing K-Means clustering (K=3) and semantic entropy calculation...")
    labels, centroids, inertia = kmeans_cluster(X, k=3, random_state=42)
    entropy = compute_semantic_entropy(X, labels, centroids)
    logger.info("[Step 4/9] ML Clustering complete (Inertia: %.4f, Semantic Entropy: %.4f)", inertia, entropy)

    # -------------------------------------------------------------------------
    # Step 5: ProTeGi Textual Gradient Generation
    # -------------------------------------------------------------------------
    logger.debug("[Step 5/9] Synthesizing ProTeGi textual gradients...")
    gradients = generate_textual_gradients(anomalies, labels, centroids, entropy)
    logger.info("[Step 5/9] Generated %d textual gradient directives", len(gradients))

    # -------------------------------------------------------------------------
    # Step 6: Architecture Red-Team Adversarial Audit
    # -------------------------------------------------------------------------
    logger.debug("[Step 6/9] Red-Team auditing %d anomalies and proposed gradients...", len(anomalies))
    active_red_team = red_team if red_team is not None else ArchitectureRedTeam(strict_mode=True)
    audit_results: List[RedTeamAuditResult] = active_red_team.audit_batch(anomalies, gradients=gradients)

    approved_count = sum(1 for a in audit_results if a.verdict == RedTeamVerdict.APPROVED)
    challenged_count = sum(1 for a in audit_results if a.verdict == RedTeamVerdict.CHALLENGED)
    rejected_count = sum(1 for a in audit_results if a.verdict == RedTeamVerdict.REJECTED)
    logger.info(
        "[Step 6/9] Red-Team Scrutiny Verdicts: Approved=%d, Challenged=%d, Rejected=%d",
        approved_count,
        challenged_count,
        rejected_count,
    )

    # Calculate overall duration
    elapsed_seconds = time.perf_counter() - scan_start_perf
    duration_ms = elapsed_seconds * 1000.0

    # -------------------------------------------------------------------------
    # Step 7: Atomic SQLite Telemetry Logging
    # -------------------------------------------------------------------------
    logger.debug("[Step 7/9] Logging scan session telemetry to database...")
    log_scan_session(
        session_id=session_id,
        anomalies=anomalies,
        gradients=gradients,
        duration_ms=duration_ms,
        db_path=db_path,
        entropy_score=entropy,
        timestamp=int(scan_ts),
    )

    # -------------------------------------------------------------------------
    # Step 8: Historical Drift Analytics & Daily Report Building
    # -------------------------------------------------------------------------
    logger.debug("[Step 8/9] Compiling historical drift analytics and Daily HITL report...")
    historical_drift = get_historical_drift(db_path=db_path)
    active_report_builder = report_builder if report_builder is not None else DailyReportBuilder()

    report_markdown = active_report_builder.build_daily_report(
        session_id=session_id,
        scan_time=scan_ts,
        anomalies=anomalies,
        gradients=gradients,
        audit_results=audit_results,
        historical_drift=historical_drift,
        duration_ms=duration_ms,
        entropy=entropy,
    )

    # -------------------------------------------------------------------------
    # Step 9: Save Daily Markdown Report & Return OptimizationReport
    # -------------------------------------------------------------------------
    out_path = Path(output_dir)
    os.makedirs(out_path, exist_ok=True)
    report_filename = f"daily_health_report_{ts_str}.md"
    report_filepath = str(out_path / report_filename)

    with open(report_filepath, "w", encoding="utf-8") as f:
        f.write(report_markdown)

    logger.info("[Step 9/9] Daily HITL Report saved to %s", report_filepath)

    opt_report = OptimizationReport(
        session_id=session_id,
        timestamp=int(scan_ts),
        duration_ms=duration_ms,
        total_anomalies=len(anomalies),
        approved_count=approved_count,
        challenged_count=challenged_count,
        audited_anomalies=audit_results,
        textual_gradients=gradients,
        entropy_score=entropy,
    )

    return opt_report, report_filepath


# =============================================================================
# Google Antigravity SDK Trigger & Cron Integration
# =============================================================================

def create_antigravity_trigger(
    interval_seconds: int = 86400,
    workspace_root: str = ".",
    db_path: str = DEFAULT_DB_PATH,
    output_dir: str = ".agents/reports",
) -> Optional[Any]:
    """Creates a Google Antigravity SDK `triggers.every` periodic trigger callback.

    Returns None if google.antigravity SDK is not installed in the environment.
    """
    try:
        from google.antigravity.triggers import TriggerContext, every
    except ImportError:
        logger.warning(
            "google.antigravity SDK is not installed; Antigravity trigger creation skipped."
        )
        return None

    async def _health_scan_trigger_cb(ctx: TriggerContext) -> None:
        logger.info("[Antigravity Cron] Executing scheduled daily health scan trigger...")
        report, report_path = run_health_scan_pipeline(
            workspace_root=workspace_root,
            db_path=db_path,
            output_dir=output_dir,
        )
        msg = (
            f"[Daily Health Scan] Completed session {report.session_id}: "
            f"{report.total_anomalies} anomalies detected ({report.approved_count} approved, "
            f"{report.challenged_count} challenged). Report: {report_path}"
        )
        logger.info("[Antigravity Cron] %s", msg)
        if hasattr(ctx, "send") and callable(ctx.send):
            await ctx.send(msg)

    return every(interval_seconds, _health_scan_trigger_cb)


def register_cron(
    app: Any,
    cron_expression: str = "0 0 * * *",
    workspace_root: str = ".",
    db_path: str = DEFAULT_DB_PATH,
    output_dir: str = ".agents/reports",
) -> Optional[Callable[..., Any]]:
    """Registers the daily health scan pipeline with an Antigravity App or custom cron scheduler."""
    if hasattr(app, "cron") and callable(app.cron):
        @app.cron(cron_expression)
        def _scheduled_cron_job() -> OptimizationReport:
            logger.info("[App Cron] Firing scheduled cron scan for '%s'", workspace_root)
            report, _ = run_health_scan_pipeline(
                workspace_root=workspace_root,
                db_path=db_path,
                output_dir=output_dir,
            )
            return report

        return _scheduled_cron_job
    logger.warning("Target app does not expose a callable .cron decorator.")
    return None


# =============================================================================
# Standalone CLI Runner & Daemon Loop
# =============================================================================

class ScannerDaemonRunner:
    """Manages the lifecycle of continuous or one-shot health scanner daemon execution."""

    def __init__(
        self,
        workspace_root: str = ".",
        db_path: str = DEFAULT_DB_PATH,
        output_dir: str = ".agents/reports",
        interval_seconds: int = 86400,
        max_iterations: Optional[int] = None,
    ) -> None:
        self.workspace_root = workspace_root
        self.db_path = db_path
        self.output_dir = output_dir
        self.interval_seconds = interval_seconds
        self.max_iterations = max_iterations
        self.is_running = False

    def run_once(self) -> Tuple[OptimizationReport, str]:
        """Executes a single scan session and returns the report."""
        return run_health_scan_pipeline(
            workspace_root=self.workspace_root,
            db_path=self.db_path,
            output_dir=self.output_dir,
        )

    def run_loop(self) -> None:
        """Executes the continuous daemon loop, handling signals and graceful shutdown."""
        self.is_running = True

        def _handle_signal(signum: int, frame: Any) -> None:
            logger.info("Received termination signal (%d). Shutting down scanner daemon...", signum)
            self.is_running = False

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        iteration = 0
        logger.info(
            "Scanner Daemon started. Interval: %d seconds. Output: %s",
            self.interval_seconds,
            self.output_dir,
        )

        while self.is_running:
            iteration += 1
            logger.info("Daemon Iteration #%d starting...", iteration)
            try:
                report, report_path = self.run_once()
                logger.info(
                    "Daemon Iteration #%d complete. Session: %s. Report: %s",
                    iteration,
                    report.session_id,
                    report_path,
                )
            except Exception as e:
                logger.error("Daemon encountered an error during scan iteration #%d: %s", iteration, e, exc_info=True)

            if self.max_iterations is not None and iteration >= self.max_iterations:
                logger.info("Reached maximum iterations (%d). Exiting loop.", self.max_iterations)
                break

            if not self.is_running:
                break

            # Sleep in 1-second chunks to respond quickly to shutdown signals
            sleep_remaining = self.interval_seconds
            while sleep_remaining > 0 and self.is_running:
                chunk = min(1.0, sleep_remaining)
                time.sleep(chunk)
                sleep_remaining -= chunk

        logger.info("Scanner Daemon shutdown complete.")


def build_cli_parser() -> argparse.ArgumentParser:
    """Constructs the command-line argument parser for the scanner daemon."""
    parser = argparse.ArgumentParser(
        prog="scanner_daemon",
        description="Antigravity Daily Health Scanner & ML Optimization Daemon.",
    )
    parser.add_argument(
        "--run-once",
        "--once",
        dest="run_once",
        action="store_true",
        help="Execute a single health scan pass and exit immediately with code 0.",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        dest="workspace",
        type=str,
        default=".",
        help="Path to workspace root directory to scan (default: current directory).",
    )
    parser.add_argument(
        "--db",
        "--db-path",
        dest="db_path",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite telemetry database (default: '{DEFAULT_DB_PATH}').",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        type=str,
        default=".agents/reports",
        help="Directory to save daily HITL markdown reports (default: '.agents/reports').",
    )
    parser.add_argument(
        "-i",
        "--interval",
        dest="interval",
        type=int,
        default=86400,
        help="Daemon loop interval in seconds between scans (default: 86400 / 24 hours).",
    )
    parser.add_argument(
        "-n",
        "--max-iterations",
        dest="max_iterations",
        type=int,
        default=None,
        help="Maximum iterations for daemon loop before exiting (useful for testing).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print OptimizationReport as JSON to stdout after scan completion.",
    )
    return parser


def main(args_list: Optional[List[str]] = None) -> int:
    """CLI entrypoint."""
    parser = build_cli_parser()
    parsed = parser.parse_args(args_list)

    if parsed.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    runner = ScannerDaemonRunner(
        workspace_root=parsed.workspace,
        db_path=parsed.db_path,
        output_dir=parsed.output_dir,
        interval_seconds=parsed.interval,
        max_iterations=parsed.max_iterations,
    )

    if parsed.run_once:
        report, report_path = runner.run_once()
        if parsed.json_output:
            import json
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(f"Health Scan complete. Session ID: {report.session_id}")
            print(f"Total Anomalies: {report.total_anomalies} (Approved: {report.approved_count}, Challenged: {report.challenged_count})")
            print(f"Report written to: {report_path}")
        return 0

    runner.run_loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

### Blueprint B: Deterministic Mock Workspace Fixture Generator (`fixtures/mock_workspace`)

To verify all 5 anomaly failure patterns deterministically offline:
- `fixtures/mock_workspace/conftest_fixture.py` creates:
  1. `127.0.0.1:3000` Ghost Daemon simulated socket listener.
  2. `.agents/worker_stale/progress.md` with mtime set to $T - 72\text{h}$ (Context Rot).
  3. `plugins/data_agent.disabled/` directory (Ecosystem Pollution).
  4. `.env` file containing `OPENAI_API_KEY="your_token_here"` (Secret Zero).
  5. `GEMINI.md` with 150 lines exceeding threshold (Prompt Fatigue).

---

### Blueprint C: Unit & Integration Tests (`tests/test_e2e_daemon.py`)

A comprehensive test suite covering:
1. `test_run_health_scan_pipeline_empty`: Tests pipeline against clean empty workspace (entropy 0.0, 0 anomalies, report generated, DB seeded).
2. `test_run_health_scan_pipeline_mock_workspace`: Tests 9 steps against all 5 failure modes; verifies anomalies, clustering, ProTeGi gradients, Red-Team audit verdicts, SQLite persistence, and Markdown report output.
3. `test_cli_runner_run_once`: Tests `main(["--run-once", ...])` exits code 0.
4. `test_cli_runner_json_flag`: Tests `--json` output format.
5. `test_antigravity_sdk_trigger_registration`: Tests `create_antigravity_trigger` and `register_cron` callbacks without errors.
6. `test_daemon_loop_max_iterations`: Tests `ScannerDaemonRunner.run_loop()` terminates cleanly at `max_iterations`.
7. `test_safety_ast_daemon`: Tests `safety_guardrails.scan_file_for_safety` passes with 0 violations on `scanner_daemon.py`.

---

## 5. Verification Method

To independently verify the implementation:

1. **Static AST Safety Check**:
   ```powershell
   python -c "from safety_guardrails import assert_safe_codebase; assert_safe_codebase('.agents/cron')"
   ```
   *Expected result*: Exits cleanly with zero safety violations.

2. **Standalone CLI Runner Verification**:
   ```powershell
   python .agents/cron/scanner_daemon.py --run-once --workspace "." --db "test_telemetry.db" --output-dir ".agents/reports"
   ```
   *Expected result*: Exits code 0, creates `.agents/reports/daily_health_report_*.md`, and initializes `test_telemetry.db`.

3. **Full Pytest Suite**:
   ```powershell
   python -m pytest ".agents/cron/tests" -v
   ```
   *Expected result*: All unit, detector, ML, audit, safety AST, and E2E daemon tests pass with 100% success rate.
