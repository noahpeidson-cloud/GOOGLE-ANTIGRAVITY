"""
Offline ML & Heuristic Light Level Analyzer for S26 Camera Exposure Control.
Strict 100% Offline execution, vectorized Rec.709 integer luminance, and 4-zone ROI slicing.
"""
from typing import Dict, Optional, Tuple
import time
import numpy as np

from .config import DetectorConfig
from .metrics import (
    FrameMetrics,
    ZoneMetrics,
    compute_16bin_histogram,
    compute_percentiles,
    compute_clipping_ratios,
)


def fast_extract_luminance_rgb(frame_rgb: np.ndarray) -> np.ndarray:
    """
    Vectorized Rec.709 integer bit-shift luminance calculation:
    Y = (54*R + 183*G + 19*B) >> 8
    
    Operates in <0.2ms on 160x90 RGB preview frames.
    Input: (H, W, 3) uint8 or (H, W) grayscale uint8 array.
    Output: (H, W) uint8 luminance plane.
    """
    if frame_rgb.ndim == 2:
        return frame_rgb.astype(np.uint8, copy=False)
    
    if frame_rgb.ndim != 3 or frame_rgb.shape[2] < 3:
        raise ValueError(f"Expected 3-channel RGB image (H, W, 3), got shape {frame_rgb.shape}")
    
    r = frame_rgb[:, :, 0].astype(np.uint32)
    g = frame_rgb[:, :, 1].astype(np.uint32)
    b = frame_rgb[:, :, 2].astype(np.uint32)
    
    # Rec.709 integer approximation (54 + 183 + 19 = 256)
    y = (54 * r + 183 * g + 19 * b) >> 8
    return y.astype(np.uint8)


def fast_extract_luminance_yuv(
    y_plane: np.ndarray,
    height: int = 90,
    width: int = 160,
    stride: Optional[int] = None
) -> np.ndarray:
    """
    Zero-copy / slice Y-plane extractor from Camera2 YUV_420_888 / NV21 preview buffer.
    """
    if stride is None or stride == width:
        if y_plane.ndim == 2 and y_plane.shape == (height, width):
            return y_plane.astype(np.uint8, copy=False)
        return y_plane.ravel()[:height * width].reshape((height, width)).astype(np.uint8, copy=False)
    
    # Strided row slicing
    plane_2d = y_plane.ravel()[:height * stride].reshape((height, stride))
    return plane_2d[:, :width].astype(np.uint8, copy=False)


def slice_zones(
    y_plane: np.ndarray,
    config: Optional[DetectorConfig] = None
) -> Dict[str, np.ndarray]:
    """
    Slices the luminance plane into 4 concert semantic Regions of Interest (ROIs):
    1. 'ceiling': Top zone (overhead lasers, trusses, moving heads)
    2. 'stage_center': Center zone (DJ booth, LED backdrop, artist keylight)
    3. 'stage_flanks': Left & Right flanks around the stage
    4. 'crowd_floor': Bottom zone (crowd silhouettes, phones, floor ambient)
    """
    if y_plane.ndim != 2:
        raise ValueError(f"Expected 2D luminance array, got shape {y_plane.shape}")
    
    cfg = config or DetectorConfig()
    h, w = y_plane.shape
    
    y_ceil_cut = max(1, int(round(h * cfg.ceiling_y_ratio)))
    y_stage_bot = max(y_ceil_cut + 1, int(round(h * cfg.stage_y_bot_ratio)))
    x_stage_left = max(1, int(round(w * cfg.stage_x_left_ratio)))
    x_stage_right = min(w - 1, int(round(w * cfg.stage_x_right_ratio)))
    
    # 1. Ceiling (top portion, full width)
    ceiling = y_plane[:y_ceil_cut, :]
    
    # 2. Stage Center (middle vertical band, central horizontal window)
    stage_center = y_plane[y_ceil_cut:y_stage_bot, x_stage_left:x_stage_right]
    
    # 3. Stage Flanks (middle vertical band, left and right outer columns)
    flank_left = y_plane[y_ceil_cut:y_stage_bot, :x_stage_left]
    flank_right = y_plane[y_ceil_cut:y_stage_bot, x_stage_right:]
    if flank_left.size > 0 and flank_right.size > 0:
        stage_flanks = np.concatenate([flank_left.ravel(), flank_right.ravel()])
    elif flank_left.size > 0:
        stage_flanks = flank_left.ravel()
    else:
        stage_flanks = flank_right.ravel()
    
    # 4. Crowd & Floor (bottom portion, full width)
    crowd_floor = y_plane[y_stage_bot:, :]
    
    return {
        "ceiling": ceiling,
        "stage_center": stage_center,
        "stage_flanks": stage_flanks,
        "crowd_floor": crowd_floor,
    }


class LightDetectorEngine:
    """
    High-performance, 100% offline light level and scene heuristic analyzer.
    Executes in <1ms on 160x90 preview frames.
    """
    def __init__(self, config: Optional[DetectorConfig] = None) -> None:
        self.config = config or DetectorConfig()
        
        # Temporal Ring Buffers
        self.history_size = self.config.history_size
        self.history_y_mean = np.zeros(self.history_size, dtype=np.float32)
        self.history_timestamps_ns = np.zeros(self.history_size, dtype=np.int64)
        self.head = 0
        self.frame_count = 0
        
        # Velocity State
        self.last_mean_luma: Optional[float] = None
        self.last_timestamp_ns: Optional[int] = None
        
    def reset(self) -> None:
        """Resets all temporal history buffers and state tracking."""
        self.history_y_mean.fill(0.0)
        self.history_timestamps_ns.fill(0)
        self.head = 0
        self.frame_count = 0
        self.last_mean_luma = None
        self.last_timestamp_ns = None

    def analyze_frame_rgb(
        self,
        frame_rgb: np.ndarray,
        timestamp_ns: Optional[int] = None
    ) -> FrameMetrics:
        """
        Ingests RGB frame (e.g. 90x160x3 uint8), converts to Rec.709 luma,
        and computes complete statistical and zonal metrics.
        """
        y_plane = fast_extract_luminance_rgb(frame_rgb)
        return self.analyze_luma_frame(y_plane, timestamp_ns=timestamp_ns)

    def analyze_luma_frame(
        self,
        y_plane: np.ndarray,
        timestamp_ns: Optional[int] = None
    ) -> FrameMetrics:
        """
        Direct analysis of 2D uint8 luminance plane.
        """
        if timestamp_ns is None:
            timestamp_ns = time.perf_counter_ns()
            
        if y_plane.ndim != 2:
            raise ValueError(f"Expected 2D grayscale array, got shape {y_plane.shape}")
            
        num_pixels = y_plane.size
        if num_pixels == 0:
            raise ValueError("Cannot analyze empty luminance plane")
            
        # 1. Global Statistical Metrics
        mean_luma = float(np.mean(y_plane))
        percentiles = compute_percentiles(y_plane, (10.0, 50.0, 90.0, 99.0))
        p10 = percentiles["p10"]
        p50 = percentiles["p50"]
        p90 = percentiles["p90"]
        p99 = percentiles["p99"]
        
        c_high, c_dark = compute_clipping_ratios(
            y_plane,
            c_high_threshold=self.config.c_high_threshold,
            c_dark_threshold=self.config.c_dark_threshold
        )
        
        # 2. 4-Zone Spatial ROI Slicing
        zones = slice_zones(y_plane, self.config)
        zone_lumas: Dict[str, float] = {}
        for zone_name in ("ceiling", "stage_center", "stage_flanks", "crowd_floor"):
            arr = zones[zone_name]
            zone_lumas[zone_name] = float(np.mean(arr)) if arr.size > 0 else 0.0
            
        # 3. 16-Bin Micro Histogram
        hist16 = compute_16bin_histogram(y_plane)
        hist_tuple = tuple(hist16.tolist())
        
        # 4. Temporal Velocity Calculation
        if self.last_timestamp_ns is not None and timestamp_ns > self.last_timestamp_ns and self.last_mean_luma is not None:
            dt_sec = (timestamp_ns - self.last_timestamp_ns) * 1e-9
            luma_velocity = (mean_luma - self.last_mean_luma) / dt_sec if dt_sec > 0.0 else 0.0
        else:
            luma_velocity = 0.0
            
        # Update Ring Buffer
        self.history_y_mean[self.head] = mean_luma
        self.history_timestamps_ns[self.head] = timestamp_ns
        self.head = (self.head + 1) % self.history_size
        self.frame_count += 1
        self.last_mean_luma = mean_luma
        self.last_timestamp_ns = timestamp_ns
        
        return FrameMetrics(
            timestamp_ns=timestamp_ns,
            mean_luma=mean_luma,
            p10=p10,
            p50=p50,
            p90=p90,
            p99=p99,
            c_high=c_high,
            c_dark=c_dark,
            zone_lumas=zone_lumas,
            luma_velocity=luma_velocity,
            histogram_16bin=hist_tuple,
        )

    def get_detailed_zone_metrics(self, y_plane: np.ndarray) -> Dict[str, ZoneMetrics]:
        """
        Computes detailed statistical breakdown for each of the 4 spatial zones.
        """
        zones = slice_zones(y_plane, self.config)
        result: Dict[str, ZoneMetrics] = {}
        for name, arr in zones.items():
            if arr.size == 0:
                result[name] = ZoneMetrics(
                    name=name,
                    mean_luma=0.0,
                    p10=0.0,
                    p50=0.0,
                    p90=0.0,
                    p99=0.0,
                    c_high=0.0,
                    c_dark=0.0,
                    pixel_count=0
                )
                continue
                
            mean_l = float(np.mean(arr))
            pcts = compute_percentiles(arr, (10.0, 50.0, 90.0, 99.0))
            c_h, c_d = compute_clipping_ratios(
                arr,
                c_high_threshold=self.config.c_high_threshold,
                c_dark_threshold=self.config.c_dark_threshold
            )
            result[name] = ZoneMetrics(
                name=name,
                mean_luma=mean_l,
                p10=pcts["p10"],
                p50=pcts["p50"],
                p90=pcts["p90"],
                p99=pcts["p99"],
                c_high=c_h,
                c_dark=c_d,
                pixel_count=int(arr.size)
            )
        return result

    def get_spatial_contrast_ratio(self, zone_lumas: Optional[Dict[str, float]] = None) -> float:
        """
        Ratio of ceiling energy to stage center energy.
        CR_CS = (mean_ceiling + 1.0) / (mean_stage_center + 1.0)
        High values (>3.5) indicate overhead laser/strobe barrage while artist is dark.
        """
        if zone_lumas is None:
            return 1.0
        ceil = zone_lumas.get("ceiling", 0.0)
        stage = zone_lumas.get("stage_center", 0.0)
        return (ceil + 1.0) / (stage + 1.0)

    def get_stage_prominence_ratio(self, zone_lumas: Optional[Dict[str, float]] = None) -> float:
        """
        Ratio of stage center energy to crowd floor energy.
        PR_stage = (mean_stage_center + 1.0) / (mean_crowd_floor + 1.0)
        High values (>5.0) indicate tight artist spotlight.
        """
        if zone_lumas is None:
            return 1.0
        stage = zone_lumas.get("stage_center", 0.0)
        crowd = zone_lumas.get("crowd_floor", 0.0)
        return (stage + 1.0) / (crowd + 1.0)
