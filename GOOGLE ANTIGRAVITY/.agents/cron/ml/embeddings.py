"""Feature vectorization converting AnomalyRecord instances into normalized NumPy feature matrices."""

import time
from typing import Any, Dict, List, Union

import numpy as np

try:
    from ..models import AnomalyRecord, DetectorType, Severity
except (ImportError, ValueError):
    from models import AnomalyRecord, DetectorType, Severity


# Feature 0: Severity weights
SEVERITY_WEIGHTS: Dict[str, float] = {
    Severity.LOW.value: 0.25,
    Severity.MEDIUM.value: 0.50,
    Severity.HIGH.value: 0.75,
    Severity.CRITICAL.value: 1.00,
    "LOW": 0.25,
    "MEDIUM": 0.50,
    "HIGH": 0.75,
    "CRITICAL": 1.00,
}

# Feature 1: Detector category normalized values
DETECTOR_CATEGORY_MAP: Dict[str, float] = {
    DetectorType.GHOST_DAEMONS.value: 0.00,
    DetectorType.CONTEXT_ROT.value: 0.25,
    DetectorType.ECOSYSTEM_POLLUTION.value: 0.50,
    DetectorType.SECRET_ZERO.value: 0.75,
    DetectorType.PROMPT_FATIGUE.value: 1.00,
    "GHOST_DAEMONS": 0.00,
    "CONTEXT_ROT": 0.25,
    "ECOSYSTEM_POLLUTION": 0.50,
    "SECRET_ZERO": 0.75,
    "PROMPT_FATIGUE": 1.00,
}

# Normalization constants
MAX_AGE_HOURS: float = 168.0  # 1 week = 7 * 24h
MAX_FOOTPRINT: float = 10000.0


def _extract_field(obj: Union[AnomalyRecord, Dict[str, Any]], field_name: str, default: Any = None) -> Any:
    """Safely extracts a field from an AnomalyRecord or dict."""
    if isinstance(obj, AnomalyRecord):
        return getattr(obj, field_name, default)
    if isinstance(obj, dict):
        return obj.get(field_name, default)
    return default


def _extract_raw_details(obj: Union[AnomalyRecord, Dict[str, Any]]) -> Dict[str, Any]:
    """Safely extracts raw_details dict from an AnomalyRecord or dict."""
    if isinstance(obj, AnomalyRecord):
        return obj.raw_details if isinstance(obj.raw_details, dict) else {}
    if isinstance(obj, dict):
        details = obj.get("raw_details", {})
        return details if isinstance(details, dict) else {}
    return {}


def vectorize_anomaly(anomaly: Union[AnomalyRecord, Dict[str, Any]], current_time: float = 0.0) -> np.ndarray:
    """Vectorizes a single AnomalyRecord or dict into a 1D float array of shape (5,) in [0.0, 1.0].

    Features:
    0: Severity weight (LOW: 0.25, MEDIUM: 0.50, HIGH: 0.75, CRITICAL: 1.00)
    1: Detector category (GHOST_DAEMONS: 0.0, CONTEXT_ROT: 0.25, ECOSYSTEM_POLLUTION: 0.50,
                           SECRET_ZERO: 0.75, PROMPT_FATIGUE: 1.00)
    2: Age in hours normalized: min(1.0, age_hours / 168.0)
    3: Token footprint / file size normalized: min(1.0, footprint / 10000.0)
    4: Confidence float score in [0.0, 1.0] (default 1.0)
    """
    # 0. Severity
    raw_sev = _extract_field(anomaly, "severity", Severity.LOW)
    if isinstance(raw_sev, Severity):
        sev_key = raw_sev.value
    else:
        sev_key = str(raw_sev).upper()
    f0_severity = SEVERITY_WEIGHTS.get(sev_key, 0.25)

    # 1. Detector category
    raw_det = _extract_field(anomaly, "detector_type", DetectorType.GHOST_DAEMONS)
    if isinstance(raw_det, DetectorType):
        det_key = raw_det.value
    else:
        det_key = str(raw_det).upper()
    f1_category = DETECTOR_CATEGORY_MAP.get(det_key, 0.0)

    # 2. Age in hours
    raw_details = _extract_raw_details(anomaly)
    age_hours = 0.0
    if "age_hours" in raw_details:
        try:
            age_hours = float(raw_details["age_hours"])
        except (ValueError, TypeError):
            age_hours = 0.0
    elif "mtime" in raw_details:
        ref_time = current_time if current_time > 0 else time.time()
        try:
            age_hours = max(0.0, (ref_time - float(raw_details["mtime"])) / 3600.0)
        except (ValueError, TypeError):
            age_hours = 0.0
    else:
        ts = _extract_field(anomaly, "timestamp", 0)
        if ts and ts > 0:
            ref_time = current_time if current_time > 0 else time.time()
            try:
                age_hours = max(0.0, (ref_time - float(ts)) / 3600.0)
            except (ValueError, TypeError):
                age_hours = 0.0

    f2_age = float(min(1.0, max(0.0, age_hours / MAX_AGE_HOURS)))

    # 3. Token footprint / size
    footprint = 0.0
    for key in ("token_count", "footprint", "file_size", "bytes", "line_count"):
        if key in raw_details and raw_details[key] is not None:
            try:
                footprint = float(raw_details[key])
                break
            except (ValueError, TypeError):
                continue

    if footprint <= 0.0:
        desc = _extract_field(anomaly, "description", "")
        if desc:
            footprint = float(len(str(desc)))

    f3_footprint = float(min(1.0, max(0.0, footprint / MAX_FOOTPRINT)))

    # 4. Confidence
    raw_conf = _extract_field(anomaly, "confidence", 1.0)
    try:
        conf_val = float(raw_conf)
    except (ValueError, TypeError):
        conf_val = 1.0
    f4_confidence = float(min(1.0, max(0.0, conf_val)))

    return np.array([f0_severity, f1_category, f2_age, f3_footprint, f4_confidence], dtype=np.float64)


def vectorize_anomalies(
    anomalies: List[Union[AnomalyRecord, Dict[str, Any]]],
    current_time: float = 0.0,
) -> np.ndarray:
    """Vectorizes a list of AnomalyRecord or dict objects into an (N, 5) float array in [0.0, 1.0].

    Returns (0, 5) array when anomalies is empty.
    """
    if not anomalies:
        return np.empty((0, 5), dtype=np.float64)

    vectors = [vectorize_anomaly(a, current_time=current_time) for a in anomalies]
    return np.vstack(vectors).astype(np.float64)
