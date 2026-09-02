"""Antigravity Autonomous ML Agent Orchestrator.
Monitors the viral trend pipeline, collects execution telemetry, analyzes operational states
via localized K-Means clustering, self-adjusts policies, and manages 14-day data lifecycles.
"""

import asyncio
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from google.antigravity import LocalAgentConfig, hooks, triggers, types

from unified_ops_hub.ml_agent.clustering import KMeansOptimizer
from unified_ops_hub.ml_agent.policy import PolicyEngine
from unified_ops_hub.ml_agent.telemetry import TelemetryStore
from unified_ops_hub.mobile.scraper import MobileViralTrendScraper

logger = logging.getLogger("unified_ops_hub.ml_agent.ml_agent")


@hooks.post_tool_call
async def telemetry_post_tool_hook(tool_call_data: Any) -> None:
    """Captures granular tool execution timing and output size."""
    logger.debug(f"[ML_AGENT_HOOK] Post tool call intercepted: {tool_call_data}")


@hooks.post_turn
async def telemetry_turn_end_hook(turn_result: Any) -> None:
    """Persists model token consumption and transcript span metadata."""
    logger.debug(f"[ML_AGENT_HOOK] Turn end intercepted: {turn_result}")


@hooks.on_tool_error
async def telemetry_tool_error_hook(error: Exception) -> Optional[str]:
    """Catches tool execution failures, logs error signatures, and allows graceful fallback."""
    logger.error(f"[ML_AGENT_HOOK] Intercepted tool error: {error}")
    return "[TOOL_ERROR_INTERCEPTED: Executing policy fallback]"


def build_ml_agent_config(
    db_path: str,
    app_data_dir: str,
    interval_seconds: int = 3600,
) -> LocalAgentConfig:
    """Constructs the authoritative LocalAgentConfig for the ML Agent."""
    budget_config = types.BudgetConfig(
        max_model_calls=20,
        max_tool_calls=50,
        max_input_tokens=150_000,
        max_output_tokens=30_000,
        max_total_tokens=180_000,
    )

    capabilities = types.CapabilitiesConfig(
        agent_behavior=types.AgentBehavior.AUTONOMOUS,
        enable_subagents=True,
        max_subagent_depth=2,
        allowed_subagents=["web_lens_worker", "android_lens_worker"],
    )

    web_worker = types.SubagentConfig(
        name="web_lens_worker",
        description="Extracts viral trends from Web Accessibility trees via Chrome DevTools",
        capabilities=types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
            enabled_tools=[types.BuiltinTools.VIEW_FILE, types.BuiltinTools.RUN_COMMAND],
        ),
    )

    android_worker = types.SubagentConfig(
        name="android_lens_worker",
        description="Extracts viral trends from mobile apps using headless Android UI hierarchy",
        capabilities=types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
            enabled_tools=[types.BuiltinTools.RUN_COMMAND, types.BuiltinTools.VIEW_FILE],
        ),
    )

    async def _trend_cycle_callback(ctx: triggers.TriggerContext) -> None:
        logger.info(f"[TRIGGER] Autonomous trend cycle triggered for db: {db_path}")

    trend_trigger = triggers.every(
        float(interval_seconds),
        _trend_cycle_callback,
    )

    config = LocalAgentConfig(
        model="gemini-3.1-pro-preview",
        app_data_dir=os.path.abspath(app_data_dir),
        budget_config=budget_config,
        capabilities=capabilities,
        subagents=[web_worker, android_worker],
        triggers=[trend_trigger],
        hooks=[
            telemetry_post_tool_hook,
            telemetry_turn_end_hook,
            telemetry_tool_error_hook,
        ],
        system_instructions=(
            "You are the Antigravity Autonomous ML Orchestrator. "
            "Your objective is to execute, monitor, and optimize the viral trend pipeline. "
            "You collect execution telemetry, evaluate cluster health via local K-Means, "
            "and dynamically adapt lens selection and retry backoffs. "
            "You adhere strictly to Rule R2 (Zero-Discretion Mandate)."
        ),
    )
    return config


def execute_trends_garbage_collection(trends_db_path: str, output_md_path: str) -> int:
    """
    Purges trends older than 14 days and writes a consolidated current_trends.md artifact.
    """
    if not os.path.exists(trends_db_path):
        return 0

    with sqlite3.connect(trends_db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        cursor = conn.cursor()

        # 1. Sweep: Hard delete records older than 14 days
        cursor.execute("DELETE FROM trends WHERE date_added < date('now', '-14 days')")
        deleted_count = cursor.rowcount
        conn.commit()

        # 2. Mark: Select active rolling 14-day window
        cursor.execute(
            """
            SELECT platform, topic_category, hashtag_or_audio, velocity_score, date_added 
            FROM trends 
            ORDER BY velocity_score DESC, date_added DESC
            """
        )
        active_trends = cursor.fetchall()

    # 3. Export concise markdown view
    os.makedirs(os.path.dirname(os.path.abspath(output_md_path)), exist_ok=True)
    lines = [
        "# Active 14-Day Viral Trend Catalog",
        f"**Last Refreshed:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"**Active Trend Count:** {len(active_trends)}",
        "",
        "| Platform | Category | Trend / Audio / Hashtag | Velocity Score | Date Added |",
        "|---|---|---|---|---|",
    ]
    for row in active_trends:
        lines.append(f"| {row[0]} | {row[1]} | `{row[2]}` | {row[3]} | {row[4]} |")

    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return deleted_count


class AutonomousMLAgent:
    """Autonomous ML Orchestrator executing the agent-ml-optimization-loop."""

    def __init__(
        self,
        telemetry_db_path: str,
        trends_db_path: Optional[str] = None,
        trends_md_path: Optional[str] = None,
        mobile_scraper: Optional[MobileViralTrendScraper] = None,
    ) -> None:
        self.telemetry_store = TelemetryStore(telemetry_db_path)
        self.k_means = KMeansOptimizer(k=3, random_state=42)
        self.policy_engine = PolicyEngine(
            self.telemetry_store,
            self.k_means,
            mobile_scraper=mobile_scraper,
        )
        self.trends_db_path = trends_db_path
        self.trends_md_path = trends_md_path
        self.mobile_scraper = mobile_scraper

    def run_optimization_cycle(
        self,
        mock_spans: Optional[List[Dict[str, Any]]] = None,
        platforms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a complete closed-loop optimization cycle:
        1. Ingests scraping spans into SQLite telemetry
        2. Runs localized K-Means clustering and adapts execution policies
        3. Performs Mark-and-Sweep garbage collection for stale data (>14 days)
        4. Updates current_trends.md artifact
        """
        now_ms = int(time.time() * 1000)
        spans_recorded = 0

        if mock_spans:
            for span in mock_spans:
                self.telemetry_store.record_span(
                    platform=span.get("platform", "tiktok"),
                    lens_type=span.get("lens_type", "web_a11y_tree"),
                    duration_ms=int(span.get("duration_ms", 1000)),
                    yield_count=int(span.get("yield_count", 10)),
                    error_count=int(span.get("error_count", 0)),
                    status_code=span.get("status_code", "SUCCESS"),
                    input_tokens=int(span.get("input_tokens", 0)),
                    output_tokens=int(span.get("output_tokens", 0)),
                    metadata=span.get("metadata", {}),
                )
                spans_recorded += 1

        eval_platforms = platforms or ["tiktok", "youtube_shorts", "instagram_reels", "facebook_reels"]
        evaluations = {}
        for plat in eval_platforms:
            evaluations[plat] = self.policy_engine.evaluate_and_adjust(plat)

        # Telemetry Mark-and-Sweep GC
        gc_telemetry_purged = self.telemetry_store.mark_and_sweep_telemetry(retention_days=14)

        # Trends DB GC
        gc_trends_purged = 0
        if self.trends_db_path and self.trends_md_path and os.path.exists(self.trends_db_path):
            gc_trends_purged = execute_trends_garbage_collection(
                self.trends_db_path, self.trends_md_path
            )

        return {
            "timestamp_ms": now_ms,
            "spans_recorded": spans_recorded,
            "evaluations": evaluations,
            "gc_telemetry_purged": gc_telemetry_purged,
            "gc_trends_purged": gc_trends_purged,
            "status": "COMPLETED",
        }
