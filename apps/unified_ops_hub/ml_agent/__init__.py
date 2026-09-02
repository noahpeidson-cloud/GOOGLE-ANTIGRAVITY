"""Antigravity ML Agent & Autonomy Optimization Loop Module.
Provides SQLite WAL telemetry tracking, sub-5ms localized K-Means clustering,
closed-loop execution policy adaptation, and autonomous trend pipeline orchestration.
"""

from unified_ops_hub.ml_agent.telemetry import TelemetryStore
from unified_ops_hub.ml_agent.clustering import KMeansOptimizer
from unified_ops_hub.ml_agent.policy import PolicyEngine
from unified_ops_hub.ml_agent.ml_agent import (
    AutonomousMLAgent,
    build_ml_agent_config,
    execute_trends_garbage_collection,
)
from unified_ops_hub.ml_agent.editor import MediaEditor

__all__ = [
    "TelemetryStore",
    "KMeansOptimizer",
    "PolicyEngine",
    "AutonomousMLAgent",
    "build_ml_agent_config",
    "execute_trends_garbage_collection",
    "MediaEditor",
]

