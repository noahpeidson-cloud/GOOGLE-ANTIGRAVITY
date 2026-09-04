"""BigQuery ML Payload Formatting module (Milestone M3 / R3).

Formats unnested, normalized trend data for BigQuery TimesFM 2.0 (AI.FORECAST)
and Key Driver Analysis (AI.KEY_DRIVERS), implementing strict case preservation,
case-sensitive deduplication, emoji stripping, and schema validation.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Set, Union

from viral_trend_pipeline.models import (
    EMOJI_AND_SPECIAL_PATTERN,
    TrendRecord,
    parse_metric_number,
    parse_velocity_metric,
)


def safe_cast_float(val: Any, default: float = 0.0) -> float:
    """Safe-cast any value to float, handling percentage strings, currency, decimals, or corrupted data."""
    if val is None or isinstance(val, bool):
        return default
    if isinstance(val, (int, float)):
        return float(val)
    parsed = parse_velocity_metric(val)
    if parsed is not None:
        return parsed
    try:
        clean = str(val).replace(",", "").replace("$", "").strip()
        return float(clean)
    except (ValueError, TypeError):
        pass
    parsed_num = parse_metric_number(val)
    if parsed_num is not None:
        return float(parsed_num)
    return default


def safe_cast_int(val: Any, default: int = 0) -> int:
    """Safe-cast any value to integer, handling metric suffixes (K, M, B) or corrupted data."""
    if val is None or isinstance(val, bool):
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    parsed = parse_metric_number(val)
    if parsed is not None:
        return parsed
    try:
        clean = str(val).replace(",", "").replace("$", "").strip()
        return int(float(clean))
    except (ValueError, TypeError):
        return default


def format_iso_timestamp(date_val: Any) -> str:
    """Convert date/timestamp string or datetime to ISO-8601 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)."""
    if isinstance(date_val, datetime):
        if date_val.tzinfo is None:
            date_val = date_val.replace(tzinfo=timezone.utc)
        return date_val.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    s = str(date_val).strip()
    if not s:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    
    if "T" in s:
        if s.endswith("Z"):
            return s
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass

    try:
        dt = datetime.strptime(s[:10], "%Y-%m-%d")
        return dt.strftime("%Y-%m-%dT00:00:00Z")
    except ValueError:
        pass

    return s


class BigQueryPayloadFormatter:
    """Payload formatter and schema validator for BigQuery ML export pipelines."""

    @staticmethod
    def normalize_tag_array(raw_tags: Union[List[Any], str, None]) -> List[str]:
        """Unnests tag arrays, trims whitespace, strips leading '#', cleans emojis,
        deduplicates, and STRICTLY PRESERVES CASE.
        
        Example:
            ['#SportsCards', ' #SportsCards ', '#sportscards', '#CardLadder🔥']
            -> ['SportsCards', 'sportscards', 'CardLadder']
        """
        if raw_tags is None:
            return []

        flat_items: List[str] = []
        
        def _flatten(item: Any) -> None:
            if item is None:
                return
            if isinstance(item, (list, tuple, set)):
                for sub in item:
                    _flatten(sub)
            elif isinstance(item, str):
                s = item.strip()
                if not s:
                    return
                flat_items.append(s)
            else:
                s = str(item).strip()
                if s:
                    flat_items.append(s)

        _flatten(raw_tags)

        seen_tags: Set[str] = set()
        normalized_result: List[str] = []

        for raw_item in flat_items:
            cleaned = raw_item.strip(" \t\n\r\u200b\ufeff\u200e\u200f\u202a\u202c")
            if not cleaned:
                continue

            cleaned = re.sub(r"^#+", "", cleaned)
            cleaned = EMOJI_AND_SPECIAL_PATTERN.sub("", cleaned)
            cleaned = cleaned.strip()
            if not cleaned:
                continue

            match = re.match(r"^([A-Za-z0-9_\-]+)", cleaned)
            tag = match.group(1).rstrip("!?.,:;-") if match else re.sub(r"[^\w\-]", "", cleaned)
            tag = tag.strip()
            if not tag:
                continue

            if tag not in seen_tags:
                seen_tags.add(tag)
                normalized_result.append(tag)

        return normalized_result

    # Aliases
    normalize_tags = normalize_tag_array

    @classmethod
    def build_ai_forecast_payload(
        cls,
        records: List[Union[TrendRecord, Dict[str, Any]]],
        metric_field: str = "velocity_score",
        min_history_points: int = 3,
    ) -> List[Dict[str, Any]]:
        """Formats time-series records matching BigQuery TimesFM 2.0 schema:
        - Columns: tag, date/timestamp, velocity_score
        - Validates minimum 3 historical data points per series identifier (tag).
        - Raises ValueError if any tag series has < 3 data points.
        """
        if not records:
            return []

        parsed_entries: List[Dict[str, Any]] = []
        for r in records:
            if isinstance(r, TrendRecord):
                tag = r.normalized_tag or (cls.normalize_tag_array([r.raw_title])[0] if cls.normalize_tag_array([r.raw_title]) else "UnknownTag")
                date_str = format_iso_timestamp(r.date_added)
                if metric_field == "velocity_score":
                    metric_val = r.velocity_metric if r.velocity_metric is not None else r.engagement_metrics.get("velocity_score", 0.0)
                elif metric_field in r.engagement_metrics:
                    metric_val = r.engagement_metrics[metric_field]
                elif hasattr(r, metric_field):
                    metric_val = getattr(r, metric_field)
                else:
                    metric_val = 0.0
            elif isinstance(r, dict):
                raw_tag = r.get("tag") or r.get("normalized_tag") or r.get("raw_title", "UnknownTag")
                norm_tags = cls.normalize_tag_array([raw_tag])
                tag = norm_tags[0] if norm_tags else str(raw_tag).strip()
                date_val = r.get("date") or r.get("timestamp") or r.get("date_added", "")
                date_str = format_iso_timestamp(date_val)
                metric_val = r.get(metric_field)
                if metric_val is None and "engagement_metrics" in r and isinstance(r["engagement_metrics"], dict):
                    metric_val = r["engagement_metrics"].get(metric_field)
                if metric_val is None and metric_field == "velocity_score":
                    metric_val = r.get("velocity_metric", 0.0)
            else:
                continue

            parsed_entries.append({
                "tag": tag,
                "date": date_str,
                metric_field: safe_cast_float(metric_val),
            })

        series_groups: Dict[str, List[Dict[str, Any]]] = {}
        for entry in parsed_entries:
            t = entry["tag"]
            series_groups.setdefault(t, []).append(entry)

        for tag, items in series_groups.items():
            if len(items) < min_history_points:
                raise ValueError(
                    f"BigQuery AI.FORECAST requires a minimum of {min_history_points} historical data points per time series. "
                    f"Tag series '{tag}' has only {len(items)} point(s)."
                )

        output_payload: List[Dict[str, Any]] = []
        for tag in sorted(series_groups.keys()):
            sorted_items = sorted(series_groups[tag], key=lambda x: x["date"])
            output_payload.extend(sorted_items)

        return output_payload

    # Alias
    format_ai_forecast_payload = build_ai_forecast_payload

    @classmethod
    def build_ai_key_drivers_payload(
        cls,
        records: List[Union[TrendRecord, Dict[str, Any]]],
        viral_threshold: int = 50000,
        dimension_cols: Optional[List[str]] = None,
        metric_col: str = "views",
        interest_label_col: str = "is_viral",
    ) -> List[Dict[str, Any]]:
        """Formats TVF input records for BigQuery AI.KEY_DRIVERS analysis:
        - 1-12 dimension columns (e.g. editing_style, platform, category)
        - Boolean interest label (is_viral = views >= viral_threshold)
        - Numeric metric (views)
        - Raises ValueError on invalid dimension count (<1 or >12).
        """
        if dimension_cols is None:
            dimension_cols = ["editing_style", "platform", "category"]

        if len(dimension_cols) < 1 or len(dimension_cols) > 12:
            raise ValueError(
                f"BigQuery AI.KEY_DRIVERS requires between 1 and 12 dimension columns, got {len(dimension_cols)}."
            )

        if metric_col in dimension_cols:
            raise ValueError(f"metric_col '{metric_col}' cannot be included in dimension_cols.")
        if interest_label_col in dimension_cols:
            raise ValueError(f"interest_label_col '{interest_label_col}' cannot be included in dimension_cols.")

        if not records:
            return []

        payload: List[Dict[str, Any]] = []
        for r in records:
            row: Dict[str, Any] = {}
            if isinstance(r, TrendRecord):
                for col in dimension_cols:
                    if hasattr(r, col):
                        val = getattr(r, col)
                    elif col in r.raw_metadata:
                        val = r.raw_metadata[col]
                    else:
                        val = "unknown"
                    row[col] = str(val) if val is not None else "unknown"

                if metric_col in r.engagement_metrics:
                    m_val = r.engagement_metrics[metric_col]
                elif hasattr(r, metric_col):
                    m_val = getattr(r, metric_col)
                elif metric_col == "views" and r.post_count is not None:
                    m_val = r.post_count
                else:
                    m_val = 0
            elif isinstance(r, dict):
                for col in dimension_cols:
                    val = r.get(col)
                    if val is None and "raw_metadata" in r and isinstance(r["raw_metadata"], dict):
                        val = r["raw_metadata"].get(col)
                    row[col] = str(val) if val is not None else "unknown"

                m_val = r.get(metric_col)
                if m_val is None and "engagement_metrics" in r and isinstance(r["engagement_metrics"], dict):
                    m_val = r["engagement_metrics"].get(metric_col)
                if m_val is None:
                    m_val = 0
            else:
                continue

            metric_int = safe_cast_int(m_val)
            row[interest_label_col] = bool(metric_int >= viral_threshold)
            row[metric_col] = metric_int
            payload.append(row)

        return payload

    # Alias
    format_ai_key_drivers_payload = build_ai_key_drivers_payload

    @staticmethod
    def validate_forecast_schema(
        payload: List[Dict[str, Any]],
        metric_field: str = "velocity_score",
        min_history_points: int = 3,
    ) -> bool:
        """Schema validator checking required fields, types, and series point counts for AI.FORECAST."""
        if not isinstance(payload, list):
            return False
        if not payload:
            return True

        series_counts: Dict[str, int] = {}
        for entry in payload:
            if not isinstance(entry, dict):
                return False
            if "tag" not in entry or not isinstance(entry["tag"], str) or not entry["tag"].strip():
                return False
            if "date" not in entry and "timestamp" not in entry:
                return False
            date_val = entry.get("date") or entry.get("timestamp")
            if not isinstance(date_val, str) or not date_val.strip():
                return False
            if metric_field not in entry:
                return False
            metric_val = entry[metric_field]
            if isinstance(metric_val, bool) or not isinstance(metric_val, (int, float)):
                return False

            series_counts[entry["tag"]] = series_counts.get(entry["tag"], 0) + 1

        for tag, count in series_counts.items():
            if count < min_history_points:
                return False

        return True

    @staticmethod
    def validate_key_drivers_schema(
        payload: List[Dict[str, Any]],
        dimension_cols: Optional[List[str]] = None,
        metric_col: str = "views",
        interest_label_col: str = "is_viral",
    ) -> bool:
        """Schema validator checking dimension columns, boolean label, and numeric metric for AI.KEY_DRIVERS."""
        if dimension_cols is None:
            dimension_cols = ["editing_style", "platform", "category"]

        if not isinstance(payload, list):
            return False
        if len(dimension_cols) < 1 or len(dimension_cols) > 12:
            return False
        if not payload:
            return True

        for row in payload:
            if not isinstance(row, dict):
                return False
            for dim in dimension_cols:
                if dim not in row:
                    return False
                if not isinstance(row[dim], str):
                    return False
            if interest_label_col not in row or not isinstance(row[interest_label_col], bool):
                return False
            if metric_col not in row:
                return False
            metric_val = row[metric_col]
            if isinstance(metric_val, bool) or not isinstance(metric_val, (int, float)):
                return False

        return True
