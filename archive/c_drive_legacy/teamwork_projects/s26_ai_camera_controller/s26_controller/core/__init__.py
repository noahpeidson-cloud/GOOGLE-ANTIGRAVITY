"""
Core algorithms, detectors, coordinates, and dispatchers for S26 AI Camera Controller.
"""
from .config import DetectorConfig, ZoneROI
from .metrics import (
    FrameMetrics,
    ZoneMetrics,
    compute_16bin_histogram,
    compute_percentiles,
    compute_clipping_ratios,
)
from .detector import (
    LightDetectorEngine,
    fast_extract_luminance_rgb,
    fast_extract_luminance_yuv,
    slice_zones,
)
from .coordinates import (
    DisplayProfile,
    DisplayResolution,
    CameraParameter,
    RibbonButton,
    TapAction,
    SamsungS26CoordinateMap,
    CoordinateNormalizer,
    ResolutionScaler,
)
from .dispatcher import (
    LightingRegime,
    CameraPreset,
    DispatchResult,
    BaseDispatcher,
    MockDispatcher,
    PersistentADBDispatcher,
    TaskerIntentDispatcher,
    AccessibilityGestureDispatcher,
    dispatch_preset,
)
from .strobe_filter import StrobeFilter, StrobeMetrics
from .state_machine import (
    ConcertStateMachine,
    StateMachineConfig,
    DEFAULT_CAMERA_PRESETS,
)

__all__ = [
    "DetectorConfig",
    "ZoneROI",
    "FrameMetrics",
    "ZoneMetrics",
    "compute_16bin_histogram",
    "compute_percentiles",
    "compute_clipping_ratios",
    "LightDetectorEngine",
    "fast_extract_luminance_rgb",
    "fast_extract_luminance_yuv",
    "slice_zones",
    "DisplayProfile",
    "DisplayResolution",
    "CameraParameter",
    "RibbonButton",
    "TapAction",
    "SamsungS26CoordinateMap",
    "CoordinateNormalizer",
    "ResolutionScaler",
    "LightingRegime",
    "CameraPreset",
    "DispatchResult",
    "BaseDispatcher",
    "MockDispatcher",
    "PersistentADBDispatcher",
    "TaskerIntentDispatcher",
    "AccessibilityGestureDispatcher",
    "dispatch_preset",
    "StrobeFilter",
    "StrobeMetrics",
    "ConcertStateMachine",
    "StateMachineConfig",
    "DEFAULT_CAMERA_PRESETS",
]

