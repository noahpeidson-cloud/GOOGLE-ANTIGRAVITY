"""Antigravity Daily Health Scanner & ML Optimization Daemon.

Orchestrates the 9-step non-destructive health scan, SQLite telemetry persistence,
NumPy/Pandas K-Means clustering, ProTeGi textual gradient synthesis, Architecture Red-Team
adversarial auditing, and daily HITL Markdown report generation.

Supports Google Antigravity SDK cron integration and standalone CLI execution (--run-once).
"""

import argparse
import logging
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Ensure module directory is on sys.path for direct CLI execution
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from .audit.red_team import ArchitectureRedTeam
    from .audit.report_builder import DailyReportBuilder
    from .config import DEFAULT_DB_PATH, DEFAULT_K_CLUSTERS
    from .database import get_historical_drift, init_db, log_scan_session
    from .fixtures.mock_workspace_factory import create_mock_workspace
    from .ml.clustering import compute_semantic_entropy, kmeans_cluster
    from .ml.embeddings import vectorize_anomalies
    from .ml.protegi import generate_textual_gradients
    from .models import (
        AnomalyRecord,
        OptimizationReport,
        RedTeamAuditResult,
        RedTeamVerdict,
        Severity,
    )
    from .scanner import HealthScanner
except (ImportError, ValueError):
    from audit.red_team import ArchitectureRedTeam
    from audit.report_builder import DailyReportBuilder
    from config import DEFAULT_DB_PATH, DEFAULT_K_CLUSTERS
    from database import get_historical_drift, init_db, log_scan_session
    from fixtures.mock_workspace_factory import create_mock_workspace
    from ml.clustering import compute_semantic_entropy, kmeans_cluster
    from ml.embeddings import vectorize_anomalies
    from ml.protegi import generate_textual_gradients
    from models import (
        AnomalyRecord,
        OptimizationReport,
        RedTeamAuditResult,
        RedTeamVerdict,
        Severity,
    )
    from scanner import HealthScanner

logger = logging.getLogger("scanner_daemon")


def run_health_scan(
    workspace_root: str = ".",
    db_path: str = DEFAULT_DB_PATH,
    output_dir: Optional[str] = None,
    k_clusters: int = DEFAULT_K_CLUSTERS,
    session_id: Optional[str] = None,
    custom_scanner: Optional[HealthScanner] = None,
) -> Tuple[OptimizationReport, str]:
    """Executes the full 9-step non-destructive health scan and optimization pipeline.

    1. init_db(db_path): Ensures WAL mode, telemetry schema, and 5 historical seeds.
    2. HealthScanner.scan_workspace(workspace_root): Executes 5 read-only detectors.
    3. vectorize_anomalies(anomalies): Converts findings into (N, 5) normalized array.
    4. kmeans_cluster(X, k=3) & compute_semantic_entropy(X, labels, centroids).
    5. generate_textual_gradients(anomalies, labels, centroids, entropy).
    6. ArchitectureRedTeam.audit_batch(anomalies, gradients): Scrutinizes false positives.
    7. log_scan_session(...): Persists session, anomalies, and gradients to SQLite.
    8. get_historical_drift(...) & DailyReportBuilder.build_daily_report(...).
    9. Saves daily report to .agents/reports/ and returns OptimizationReport.

    Args:
        workspace_root: Target workspace root directory to scan.
        db_path: Path to SQLite telemetry database.
        output_dir: Directory where daily report markdown file will be written.
        k_clusters: Number of K-Means clusters (default: 3).
        session_id: Optional unique identifier for the scan session.
        custom_scanner: Optional pre-configured HealthScanner instance.

    Returns:
        Tuple of (OptimizationReport, report_file_path).
    """
    scan_start_perf = time.perf_counter()
    scan_timestamp = int(time.time())
    scan_dt = datetime.fromtimestamp(scan_timestamp, timezone.utc)

    if not session_id:
        session_id = f"health_scan_{scan_dt.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    abs_workspace = os.path.abspath(workspace_root)
    abs_db = os.path.abspath(db_path)

    # -------------------------------------------------------------------------
    # Step 1: Initialize Database & Seed 5 Historical Failure Lifelines
    # -------------------------------------------------------------------------
    init_db(abs_db)

    # -------------------------------------------------------------------------
    # Step 2: Execute Modular Read-Only Health Scanner
    # -------------------------------------------------------------------------
    scanner = custom_scanner or HealthScanner()
    anomalies: List[AnomalyRecord] = scanner.scan_workspace(abs_workspace)
    scan_duration_ms = scanner.get_last_duration_ms()
    if scan_duration_ms <= 0.0:
        scan_duration_ms = (time.perf_counter() - scan_start_perf) * 1000.0

    # -------------------------------------------------------------------------
    # Step 3: Feature Vectorization
    # -------------------------------------------------------------------------
    X = vectorize_anomalies(anomalies, current_time=float(scan_timestamp))

    # -------------------------------------------------------------------------
    # Step 4: Localized NumPy/Pandas K-Means Clustering & Semantic Entropy
    # -------------------------------------------------------------------------
    labels, centroids, _ = kmeans_cluster(X, k=k_clusters)
    entropy = compute_semantic_entropy(X, labels, centroids)

    # -------------------------------------------------------------------------
    # Step 5: ProTeGi Textual Gradient Synthesis
    # -------------------------------------------------------------------------
    gradients = generate_textual_gradients(anomalies, labels, centroids, entropy)

    # -------------------------------------------------------------------------
    # Step 6: Architecture Red-Team Adversarial Audit
    # -------------------------------------------------------------------------
    red_team = ArchitectureRedTeam()
    audit_results: List[RedTeamAuditResult] = red_team.audit_batch(
        anomalies, gradients=gradients
    )

    # -------------------------------------------------------------------------
    # Step 7: Atomic SQLite Telemetry Logging
    # -------------------------------------------------------------------------
    log_scan_session(
        session_id=session_id,
        anomalies=anomalies,
        gradients=gradients,
        duration_ms=scan_duration_ms,
        db_path=abs_db,
        entropy_score=entropy,
        timestamp=scan_timestamp,
    )

    # -------------------------------------------------------------------------
    # Step 8: Historical Drift Analytics & Daily HITL Report Compilation
    # -------------------------------------------------------------------------
    drift = get_historical_drift(db_path=abs_db)
    builder = DailyReportBuilder()
    report_md = builder.build_daily_report(
        session_id=session_id,
        scan_time=scan_dt,
        anomalies=anomalies,
        gradients=gradients,
        audit_results=audit_results,
        historical_drift=drift,
        duration_ms=scan_duration_ms,
        entropy=entropy,
    )

    # -------------------------------------------------------------------------
    # Step 9: Save Daily Report & Construct OptimizationReport Contract
    # -------------------------------------------------------------------------
    target_out_dir = output_dir or os.path.join(abs_workspace, ".agents", "reports")
    target_out_dir = os.path.abspath(target_out_dir)
    os.makedirs(target_out_dir, exist_ok=True)

    report_filename = f"daily_health_report_{scan_dt.strftime('%Y%m%d_%H%M%S')}.md"
    report_path = os.path.join(target_out_dir, report_filename)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    approved_count = sum(
        1 for r in audit_results if r.verdict == RedTeamVerdict.APPROVED
    )
    challenged_count = sum(
        1 for r in audit_results if r.verdict == RedTeamVerdict.CHALLENGED
    )

    optimization_report = OptimizationReport(
        session_id=session_id,
        timestamp=scan_timestamp,
        duration_ms=scan_duration_ms,
        total_anomalies=len(anomalies),
        approved_count=approved_count,
        challenged_count=challenged_count,
        audited_anomalies=audit_results,
        textual_gradients=gradients,
        entropy_score=entropy,
    )

    return optimization_report, report_path


# =============================================================================
# Google Antigravity SDK Trigger & Cron Integration
# =============================================================================
def create_antigravity_sdk_trigger(
    interval_seconds: int = 86400,
    workspace_root: str = ".",
    db_path: str = DEFAULT_DB_PATH,
    output_dir: Optional[str] = None,
) -> Any:
    """Creates a periodic trigger compatible with the Google Antigravity SDK (triggers.every).

    Falls back gracefully if the SDK is not installed in the local environment.
    """
    try:
        from google.antigravity.triggers import TriggerContext, every  # type: ignore

        async def _sdk_cron_handler(ctx: Any) -> None:
            logger.info("Antigravity SDK Trigger: Executing daily health scan...")
            report, report_file = run_health_scan(
                workspace_root=workspace_root,
                db_path=db_path,
                output_dir=output_dir,
            )
            msg = (
                f"Antigravity Daily Health Scan Complete: Session {report.session_id}\n"
                f"- Anomalies: {report.total_anomalies} (Approved: {report.approved_count}, Challenged: {report.challenged_count})\n"
                f"- Semantic Entropy: {report.entropy_score:.4f}\n"
                f"- Report saved to: {report_file}"
            )
            if hasattr(ctx, "send"):
                await ctx.send(msg)
            logger.info(msg)

        return every(interval_seconds, _sdk_cron_handler)
    except ImportError:
        logger.info(
            "google-antigravity SDK not installed; returning standalone trigger wrapper."
        )

        def _fallback_trigger() -> Tuple[OptimizationReport, str]:
            return run_health_scan(
                workspace_root=workspace_root,
                db_path=db_path,
                output_dir=output_dir,
            )

        return _fallback_trigger


# =============================================================================
# CLI Entrypoint & Standalone Runner
# =============================================================================
def build_cli_parser() -> argparse.ArgumentParser:
    """Constructs the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Antigravity Daily Health Scanner & ML Optimization Daemon",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--run-once",
        "--once",
        action="store_true",
        dest="run_once",
        help="Execute a single health scan and exit immediately with code 0.",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=".",
        help="Path to workspace root directory to inspect.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help="Path to SQLite telemetry database.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to write daily health markdown reports (defaults to <workspace>/.agents/reports).",
    )
    parser.add_argument(
        "--interval",
        "--interval-seconds",
        type=int,
        default=86400,
        dest="interval",
        help="Daemon interval in seconds for continuous cron mode (default: 86400 = 24h).",
    )
    parser.add_argument(
        "--k-clusters",
        type=int,
        default=DEFAULT_K_CLUSTERS,
        help="Number of clusters for K-Means anomaly grouping.",
    )
    parser.add_argument(
        "--mock-env",
        action="store_true",
        help="Create and scan a temporary mock workspace reproducing all 5 historical failure patterns.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI runner entrypoint."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )

    parser = build_cli_parser()
    args = parser.parse_args(argv)

    temp_mock_dir = None
    target_workspace = args.workspace

    try:
        if args.mock_env:
            temp_mock_dir = tempfile.TemporaryDirectory()
            target_workspace = create_mock_workspace(temp_mock_dir.name)
            logger.info("Created mock workspace environment at: %s", target_workspace)

        if args.run_once:
            logger.info("Executing standalone single-run health scan...")
            report, report_file = run_health_scan(
                workspace_root=target_workspace,
                db_path=args.db,
                output_dir=args.output_dir,
                k_clusters=args.k_clusters,
            )
            print("=" * 72)
            print(f"ANTIGRAVITY HEALTH SCAN COMPLETE: {report.session_id}")
            print(f"- Total Anomalies Detected : {report.total_anomalies}")
            print(f"- Red-Team Approved        : {report.approved_count}")
            print(f"- Red-Team Challenged      : {report.challenged_count}")
            print(f"- Semantic Entropy Score   : {report.entropy_score:.4f}")
            print(f"- Scan Duration            : {report.duration_ms:.2f} ms")
            print(f"- Report Path              : {report_file}")
            print("=" * 72)
            return 0

        # Continuous daemon loop mode
        logger.info(
            "Starting continuous health daemon (interval: %d seconds)...",
            args.interval,
        )
        try:
            while True:
                report, report_file = run_health_scan(
                    workspace_root=target_workspace,
                    db_path=args.db,
                    output_dir=args.output_dir,
                    k_clusters=args.k_clusters,
                )
                logger.info(
                    "Completed scan session %s: %d anomalies recorded. Next scan in %d seconds.",
                    report.session_id,
                    report.total_anomalies,
                    args.interval,
                )
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Daemon interrupted by user signal. Exiting cleanly.")
            return 0

    finally:
        if temp_mock_dir is not None:
            temp_mock_dir.cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(main())
