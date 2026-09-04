"""Mark-and-Sweep Garbage Collection engine and markdown view generator."""

from datetime import datetime, timezone
import os
from typing import Optional, Dict, Any, List

from viral_trend_pipeline.models import get_default_date, TrendRecord
from viral_trend_pipeline.storage.database import SQLiteTrendStore


class GarbageCollector:
    """Executes rolling window mark-and-sweep garbage collection on SQLiteTrendStore."""

    def __init__(self, store: SQLiteTrendStore):
        self.store = store

    def sweep(self, anchor_date: Optional[str] = None, cutoff_days: int = 14) -> Dict[str, int]:
        """Purge trend records strictly older than cutoff_days relative to anchor_date.
        Query executed: DELETE FROM trends WHERE date_added < date(:anchor_date, '-' || :cutoff_days || ' days')

        Returns:
            Dict with keys: purged_count, retained_count, pre_count, post_count
        """
        anchor = get_default_date(anchor_date)
        pre_count = self.store.get_total_count()

        query = "DELETE FROM trends WHERE date_added < date(?, '-' || ? || ' days')"
        with self.store.connection:
            cursor = self.store.connection.execute(query, (anchor, cutoff_days))
            purged_count = cursor.rowcount

        post_count = self.store.get_total_count()
        retained_count = post_count

        return {
            "purged_count": purged_count,
            "retained_count": retained_count,
            "pre_count": pre_count,
            "post_count": post_count,
        }

    def generate_current_trends_view(
        self,
        anchor_date: Optional[str] = None,
        cutoff_days: int = 14,
        output_path: Optional[str] = None,
    ) -> str:
        """Compile the active rolling window records into a structured markdown document.
        Optionally writes to output_path if provided.
        """
        anchor = get_default_date(anchor_date)
        records = self.store.get_records_in_window(anchor_date=anchor, window_days=cutoff_days)

        # Calculate earliest active window date
        with self.store.connection:
            cursor = self.store.connection.execute(
                "SELECT date(?, '-' || ? || ' days')", (anchor, cutoff_days)
            )
            row = cursor.fetchone()
            earliest_date = row[0] if row else "N/A"

        lines: List[str] = []
        lines.append("# Active Viral Trends (Rolling 14-Day Window)")
        lines.append("")
        lines.append(f"**Anchor Date:** `{anchor}`  ")
        lines.append(f"**Window Range:** `{earliest_date}` to `{anchor}` ({cutoff_days} days)  ")
        lines.append(f"**Active Records Count:** `{len(records)}`  ")
        lines.append("")

        if not records:
            lines.append("_No active trends found in current window._")
            lines.append("")
            content = "\n".join(lines)
            if output_path:
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)
            return content

        # Group by platform and category
        grouped: Dict[str, Dict[str, List[TrendRecord]]] = {}
        for r in records:
            grouped.setdefault(r.platform, {}).setdefault(r.category, []).append(r)

        for platform in sorted(grouped.keys()):
            for category in sorted(grouped[platform].keys()):
                group_records = grouped[platform][category]
                lines.append(f"## Platform: {platform.capitalize()} | Category: `{category}`")
                lines.append("")
                lines.append("| Tag | Date Added | Velocity | Rank | Post Count | Editing Style | Views |")
                lines.append("|---|---|---|---|---|---|---|")
                for r in group_records:
                    tag_str = f"#{r.normalized_tag}"
                    date_str = r.date_added
                    vel_str = f"{r.velocity_metric}%" if r.velocity_metric is not None else "--"
                    rank_str = str(r.rank) if r.rank is not None else "--"
                    post_str = f"{r.post_count:,}" if r.post_count is not None else "--"
                    style_str = r.editing_style or "--"
                    views = r.engagement_metrics.get("views")
                    views_str = f"{views:,}" if isinstance(views, (int, float)) else "--"
                    lines.append(f"| `{tag_str}` | {date_str} | {vel_str} | {rank_str} | {post_str} | {style_str} | {views_str} |")
                lines.append("")

        content = "\n".join(lines)
        if output_path:
            out_dir = os.path.dirname(os.path.abspath(output_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

        return content
