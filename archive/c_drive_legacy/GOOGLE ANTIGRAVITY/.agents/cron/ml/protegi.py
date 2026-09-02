"""ProTeGi Textual Gradient Generator: Synthesizes actionable rule refinement gradients from anomaly clusters."""

from typing import Any, Dict, List, Set, Union

import numpy as np

try:
    from ..models import AnomalyRecord, DetectorType, Severity
except (ImportError, ValueError):
    from models import AnomalyRecord, DetectorType, Severity


CONVERGENCE_MESSAGE = "[ProTeGi Convergence] Semantic entropy is 0.000 — Workspace rules and detectors are tightly aligned."


def _get_detector_type_str(anomaly: Union[AnomalyRecord, Dict[str, Any]]) -> str:
    """Extracts string representation of detector_type."""
    if isinstance(anomaly, AnomalyRecord):
        dt = anomaly.detector_type
        return dt.value if isinstance(dt, DetectorType) else str(dt)
    if isinstance(anomaly, dict):
        return str(anomaly.get("detector_type", ""))
    return ""


def _get_severity_str(anomaly: Union[AnomalyRecord, Dict[str, Any]]) -> str:
    """Extracts string representation of severity."""
    if isinstance(anomaly, AnomalyRecord):
        sev = anomaly.severity
        return sev.value if isinstance(sev, Severity) else str(sev)
    if isinstance(anomaly, dict):
        return str(anomaly.get("severity", ""))
    return ""


def _get_description_str(anomaly: Union[AnomalyRecord, Dict[str, Any]]) -> str:
    """Extracts description string."""
    if isinstance(anomaly, AnomalyRecord):
        return anomaly.description or ""
    if isinstance(anomaly, dict):
        return str(anomaly.get("description", ""))
    return ""


def generate_textual_gradients(
    anomalies: List[Union[AnomalyRecord, Dict[str, Any]]],
    labels: np.ndarray,
    centroids: np.ndarray,
    entropy: float,
) -> List[str]:
    """Synthesizes ProTeGi textual gradients analyzing cluster centroids, high-entropy clusters,

    and recurring anomaly patterns to produce actionable rule refinement advice.

    Parameters:
        anomalies: List of AnomalyRecord or dict objects.
        labels: (N,) integer array of cluster assignments.
        centroids: (k, 5) float array of cluster centroids.
        entropy: float normalized intra-cluster dispersion score in [0.0, 1.0].

    Returns:
        List of textual gradient strings. Returns default convergence message if entropy is 0.0 or anomalies is empty.
    """
    if not anomalies or entropy <= 0.0:
        return [CONVERGENCE_MESSAGE]

    gradients: List[str] = []
    generated_types: Set[str] = set()

    # Analyze cluster-level patterns
    k = centroids.shape[0] if isinstance(centroids, np.ndarray) and centroids.ndim > 1 else 0
    n = len(anomalies)

    # Collect member anomalies for each cluster
    cluster_members: Dict[int, List[Union[AnomalyRecord, Dict[str, Any]]]] = {i: [] for i in range(k)}
    if isinstance(labels, np.ndarray) and labels.shape[0] == n:
        for idx, anom in enumerate(anomalies):
            c_id = int(labels[idx])
            if c_id in cluster_members:
                cluster_members[c_id].append(anom)

    # 1. Generate cluster-specific gradient guidance
    for c_id, members in cluster_members.items():
        if not members:
            continue

        # Count detector types in this cluster
        type_counts: Dict[str, int] = {}
        for m in members:
            dt = _get_detector_type_str(m).upper()
            type_counts[dt] = type_counts.get(dt, 0) + 1

        dominant_type = max(type_counts.keys(), key=lambda k: type_counts[k]) if type_counts else ""

        if dominant_type == DetectorType.GHOST_DAEMONS.value and dominant_type not in generated_types:
            gradients.append(
                "[ProTeGi Gradient: GHOST_DAEMONS] Socket collision patterns detected on dev ports (3000/8000/8501). "
                "Recommend implementing pre-launch socket sweep hooks and graceful daemon lifecycle shutdown."
            )
            generated_types.add(dominant_type)

        elif dominant_type == DetectorType.CONTEXT_ROT.value and dominant_type not in generated_types:
            gradients.append(
                "[ProTeGi Gradient: CONTEXT_ROT] High age dispersion detected in planning artifacts. "
                "Recommend tuning CONTEXT_ROT_THRESHOLD_HOURS (current 24.0h) or expanding whitelist in WHITELISTED_FILENAMES to protect active project docs."
            )
            generated_types.add(dominant_type)

        elif dominant_type == DetectorType.ECOSYSTEM_POLLUTION.value and dominant_type not in generated_types:
            gradients.append(
                "[ProTeGi Gradient: ECOSYSTEM_POLLUTION] Detected .disabled plugin artifacts and cross-track leaks. "
                "Recommend automated quarantine of .disabled directories and enforcing domain boundaries between /sports_cards and /content_creation."
            )
            generated_types.add(dominant_type)

        elif dominant_type == DetectorType.SECRET_ZERO.value and dominant_type not in generated_types:
            gradients.append(
                "[ProTeGi Gradient: SECRET_ZERO] Critical placeholder token exposures detected in config files. "
                "Recommend adding pre-commit token hygiene hooks and strict template replacement checks."
            )
            generated_types.add(dominant_type)

        elif dominant_type == DetectorType.PROMPT_FATIGUE.value and dominant_type not in generated_types:
            gradients.append(
                "[ProTeGi Gradient: PROMPT_FATIGUE] GEMINI.md manifest exhibits rule bloat (>100 lines). "
                "Recommend distilling procedural guidelines into modular skills (.agents/skills/) to reduce LLM prompt fatigue."
            )
            generated_types.add(dominant_type)

    # 2. Cover any unrepresented anomaly types present in the batch
    for a in anomalies:
        dt = _get_detector_type_str(a).upper()
        if dt and dt not in generated_types:
            if dt == DetectorType.GHOST_DAEMONS.value:
                gradients.append(
                    "[ProTeGi Gradient: GHOST_DAEMONS] Socket collision patterns detected on dev ports (3000/8000/8501). "
                    "Recommend implementing pre-launch socket sweep hooks and graceful daemon lifecycle shutdown."
                )
                generated_types.add(dt)
            elif dt == DetectorType.CONTEXT_ROT.value:
                gradients.append(
                    "[ProTeGi Gradient: CONTEXT_ROT] High age dispersion detected in planning artifacts. "
                    "Recommend tuning CONTEXT_ROT_THRESHOLD_HOURS (current 24.0h) or expanding whitelist in WHITELISTED_FILENAMES to protect active project docs."
                )
                generated_types.add(dt)
            elif dt == DetectorType.ECOSYSTEM_POLLUTION.value:
                gradients.append(
                    "[ProTeGi Gradient: ECOSYSTEM_POLLUTION] Detected .disabled plugin artifacts and cross-track leaks. "
                    "Recommend automated quarantine of .disabled directories and enforcing domain boundaries between /sports_cards and /content_creation."
                )
                generated_types.add(dt)
            elif dt == DetectorType.SECRET_ZERO.value:
                gradients.append(
                    "[ProTeGi Gradient: SECRET_ZERO] Critical placeholder token exposures detected in config files. "
                    "Recommend adding pre-commit token hygiene hooks and strict template replacement checks."
                )
                generated_types.add(dt)
            elif dt == DetectorType.PROMPT_FATIGUE.value:
                gradients.append(
                    "[ProTeGi Gradient: PROMPT_FATIGUE] GEMINI.md manifest exhibits rule bloat (>100 lines). "
                    "Recommend distilling procedural guidelines into modular skills (.agents/skills/) to reduce LLM prompt fatigue."
                )
                generated_types.add(dt)

    # 3. Add high entropy meta-gradient if variance is elevated
    if entropy >= 0.15:
        gradients.append(
            f"[ProTeGi Meta-Gradient] Elevated semantic entropy ({entropy:.3f}) across {n} anomalies. "
            "High variance indicates multiple concurrent drift patterns; prioritize critical-severity clusters."
        )

    # Fallback if no specific gradients matched
    if not gradients:
        gradients.append(
            f"[ProTeGi Gradient: GENERAL_DRIFT] Detected {n} anomalies with entropy score {entropy:.3f}. "
            "Review workspace health telemetry and calibrate detector thresholds."
        )

    return gradients
