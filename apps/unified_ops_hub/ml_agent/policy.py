"""Closed-Loop Self-Adjusting Execution Policy Engine.
Analyzes K-Means cluster distributions across scraping telemetry and dynamically adjusts
polling intervals, retry backoff bases, and lens failovers to Android CLI automation.
"""

import logging
import time
from typing import Any, Dict, Optional

import numpy as np

from unified_ops_hub.ml_agent.clustering import KMeansOptimizer
from unified_ops_hub.ml_agent.telemetry import TelemetryStore

logger = logging.getLogger("unified_ops_hub.ml_agent.policy")


class PolicyEngine:
    """Evaluates telemetry cluster distributions and mutates operational parameters."""

    def __init__(
        self,
        telemetry_store: TelemetryStore,
        k_means: Optional[KMeansOptimizer] = None,
        mobile_scraper: Optional[Any] = None,
    ) -> None:
        self.store = telemetry_store
        self.k_means = k_means or KMeansOptimizer(k=3, random_state=42)
        self.mobile_scraper = mobile_scraper

    def evaluate_and_adjust(self, platform: str, recent_window_size: int = 10) -> Dict[str, Any]:
        """
        Evaluates recent scraping spans for a platform and adapts execution policy dials.
        """
        df = self.store.get_recent_spans(platform=platform, limit=50)
        if len(df) < 3:
            return {
                "action": "NO_OP",
                "platform": platform,
                "reason": "Insufficient telemetry spans",
            }

        labels, centroids, counts = self.k_means.fit_predict(df)

        # Update cluster labels in database
        span_ids = df["span_id"].tolist()
        span_cluster_map = dict(zip(span_ids, [int(lbl) for lbl in labels]))
        self.store.update_cluster_labels(span_cluster_map)

        current_policy = self.store.get_policy(platform)
        if not current_policy:
            return {
                "action": "NO_OP",
                "platform": platform,
                "reason": f"No policy record found for platform '{platform}'",
            }

        current_lens = current_policy.get("active_lens", "web_a11y_tree")
        current_interval = int(current_policy.get("poll_interval_sec", 3600))
        current_backoff = float(current_policy.get("retry_backoff_base_sec", 2.0))

        # Recent window of spans (newest spans are at the beginning since sorted DESC by timestamp_ms)
        recent_labels = labels[:recent_window_size]
        total_recent = len(recent_labels)
        if total_recent == 0:
            return {"action": "NO_OP", "platform": platform, "reason": "Empty recent window"}

        c0_rate = float(np.mean(recent_labels == 0))
        c1_rate = float(np.mean(recent_labels == 1))
        c2_rate = float(np.mean(recent_labels == 2))

        # 1. Critical Failure / DOM Drift (Cluster 2 dominance >= 35%)
        if c2_rate >= 0.35:
            new_lens = "android_ui_dump" if current_lens == "web_a11y_tree" else "web_a11y_tree"
            new_interval = max(current_interval, 7200)
            new_backoff = min(current_backoff * 1.5, 10.0)
            reason = f"Cluster 2 (DOM Drift/Zero Yield) detected ({c2_rate:.1%}). Switching lens to {new_lens}."
            self.store.update_policy(
                platform=platform,
                active_lens=new_lens,
                poll_interval_sec=new_interval,
                retry_backoff_base_sec=new_backoff,
                reason=reason,
            )
            return {
                "action": "LENS_SWAP",
                "platform": platform,
                "new_lens": new_lens,
                "new_interval": new_interval,
                "new_backoff": new_backoff,
                "c2_rate": c2_rate,
                "reason": reason,
            }

        # 2. Rate Limiting / Latency Degradation (Cluster 1 dominance >= 40%)
        elif c1_rate >= 0.40:
            new_interval = min(int(current_interval * 1.5), 28800)  # Max 8 hours
            new_backoff = min(round(current_backoff * 2.0, 2), 10.0)
            reason = f"Cluster 1 (Rate Limit/Lag) detected ({c1_rate:.1%}). Throttling cadence."
            self.store.update_policy(
                platform=platform,
                active_lens=current_lens,
                poll_interval_sec=new_interval,
                retry_backoff_base_sec=new_backoff,
                reason=reason,
            )
            return {
                "action": "THROTTLE",
                "platform": platform,
                "new_interval": new_interval,
                "new_backoff": new_backoff,
                "c1_rate": c1_rate,
                "reason": reason,
            }

        # 3. Healthy Recovery (Cluster 0 dominance >= 75% with elevated dials)
        elif c0_rate >= 0.75 and (current_interval > 3600 or current_backoff > 2.0):
            new_interval = max(int(current_interval * 0.8), 3600)
            new_backoff = max(round(current_backoff * 0.8, 1), 2.0)
            reason = f"Cluster 0 (Healthy) sustained ({c0_rate:.1%}). Restoring baseline cadence."
            self.store.update_policy(
                platform=platform,
                active_lens=current_lens,
                poll_interval_sec=new_interval,
                retry_backoff_base_sec=new_backoff,
                reason=reason,
            )
            return {
                "action": "RECOVER",
                "platform": platform,
                "new_interval": new_interval,
                "new_backoff": new_backoff,
                "c0_rate": c0_rate,
                "reason": reason,
            }

        return {
            "action": "MAINTAIN",
            "platform": platform,
            "c0_rate": c0_rate,
            "c1_rate": c1_rate,
            "c2_rate": c2_rate,
            "reason": "System operating within acceptable entropy bounds",
        }

    def trigger_mobile_failover(self, platform: str, scraper: Optional[Any] = None) -> Dict[str, Any]:
        """
        Directly executes lens failover to Android CLI mobile scraping and updates policy.
        """
        active_scraper = scraper or self.mobile_scraper
        current_policy = self.store.get_policy(platform)
        current_interval = int(current_policy.get("poll_interval_sec", 3600)) if current_policy else 3600
        current_backoff = float(current_policy.get("retry_backoff_base_sec", 2.0)) if current_policy else 2.0

        new_lens = "android_ui_dump"
        reason = "Automated lens failover to Android CLI mobile scraping triggered."

        self.store.update_policy(
            platform=platform,
            active_lens=new_lens,
            poll_interval_sec=max(current_interval, 3600),
            retry_backoff_base_sec=max(current_backoff, 2.5),
            reason=reason,
        )

        logger.info(f"[POLICY_FAILOVER] Platform '{platform}' transitioned to {new_lens}.")
        return {
            "success": True,
            "platform": platform,
            "active_lens": new_lens,
            "timestamp": int(time.time() * 1000),
            "reason": reason,
        }
