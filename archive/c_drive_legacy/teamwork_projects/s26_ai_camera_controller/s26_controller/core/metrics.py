"""
Statistical metrics, percentile estimators, and data models for light analysis.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple
import numpy as np


@dataclass(frozen=True)
class FrameMetrics:
    """
    Immutable telemetry frame metrics capturing exposure, percentiles, saturation,
    spatial zone luminance, and temporal velocity.
    """
    timestamp_ns: int
    mean_luma: float              # 0.0 - 255.0
    p10: float
    p50: float
    p90: float
    p99: float
    c_high: float                 # Ratio of pixels >= 245 (saturation)
    c_dark: float                 # Ratio of pixels <= 10 (shadow floor)
    zone_lumas: Dict[str, float]  # {'ceiling', 'stage_center', 'stage_flanks', 'crowd_floor'}
    luma_velocity: float          # delta luma / delta time (units/sec)
    histogram_16bin: Tuple[float, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ZoneMetrics:
    """
    Detailed statistical metrics for an individual spatial Region of Interest (ROI).
    """
    name: str
    mean_luma: float
    p10: float
    p50: float
    p90: float
    p99: float
    c_high: float
    c_dark: float
    pixel_count: int


def compute_16bin_histogram(y_plane: np.ndarray) -> np.ndarray:
    """
    Fast bit-shift 16-bin normalized histogram computation.
    Bin index is computed via bit-shift: y >> 4 (bins: 0-15, 16-31, ..., 240-255).
    Returns normalized float32 array of shape (16,) summing to 1.0 (or zeros if empty).
    """
    if y_plane.size == 0:
        return np.zeros(16, dtype=np.float32)
    bins = y_plane >> 4
    hist = np.bincount(bins.ravel(), minlength=16).astype(np.float32)
    return hist / float(y_plane.size)


def compute_percentiles(
    y_plane: np.ndarray,
    percentiles: Tuple[float, ...] = (10.0, 50.0, 90.0, 99.0)
) -> Dict[str, float]:
    """
    Calculates exact statistical percentiles on the luminance plane.
    """
    if y_plane.size == 0:
        return {f"p{int(p)}": 0.0 for p in percentiles}
    
    vals = np.percentile(y_plane, percentiles)
    return {f"p{int(p)}": float(v) for p, v in zip(percentiles, vals)}


def compute_clipping_ratios(
    y_plane: np.ndarray,
    c_high_threshold: int = 245,
    c_dark_threshold: int = 10
) -> Tuple[float, float]:
    """
    Vectorized high saturation (>= c_high_threshold) and dark crushing (<= c_dark_threshold) ratios.
    Returns (c_high, c_dark) in range [0.0, 1.0].
    """
    total = y_plane.size
    if total == 0:
        return 0.0, 0.0
    
    high_count = int(np.count_nonzero(y_plane >= c_high_threshold))
    dark_count = int(np.count_nonzero(y_plane <= c_dark_threshold))
    return high_count / total, dark_count / total
