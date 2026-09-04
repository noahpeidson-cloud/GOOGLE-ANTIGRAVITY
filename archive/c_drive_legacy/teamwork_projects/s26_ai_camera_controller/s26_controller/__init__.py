"""
S26 AI Camera Controller package.
"""
__version__ = "0.1.0"

from .core.config import DetectorConfig, ZoneROI
from .core.metrics import (
    FrameMetrics,
    ZoneMetrics,
    compute_16bin_histogram,
    compute_percentiles,
    compute_clipping_ratios,
)
from .core.detector import (
    LightDetectorEngine,
    fast_extract_luminance_rgb,
    fast_extract_luminance_yuv,
    slice_zones,
)
from .core.coordinates import (
    DisplayProfile,
    DisplayResolution,
    CameraParameter,
    RibbonButton,
    TapAction,
    SamsungS26CoordinateMap,
    CoordinateNormalizer,
    ResolutionScaler,
)
from .core.dispatcher import (
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
from .core.strobe_filter import StrobeFilter, StrobeMetrics
from .core.state_machine import (
    ConcertStateMachine,
    StateMachineConfig,
    DEFAULT_CAMERA_PRESETS,
)
from .daemon import (
    S26CameraControllerDaemon,
    DaemonStepResult,
    DaemonTelemetry,
    RegimeTransitionRecord,
)
from .simulation import (
    ConcertScenario,
    ScenarioType,
    ScenarioPhase,
    ConcertLightSimulator,
    MockAndroidDevice,
    MockDeviceDispatcher,
    ProVideoCameraState,
    CapturedCommand,
    generate_scenario_frames,
    generate_blackout_drop_scenario,
    generate_laser_assault_scenario,
    generate_strobe_train_scenario,
    generate_pyro_flood_scenario,
    generate_full_concert_set_scenario,
)

__all__ = [
    "__version__",
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
    "S26CameraControllerDaemon",
    "DaemonStepResult",
    "DaemonTelemetry",
    "RegimeTransitionRecord",
    "ConcertScenario",
    "ScenarioType",
    "ScenarioPhase",
    "ConcertLightSimulator",
    "MockAndroidDevice",
    "MockDeviceDispatcher",
    "ProVideoCameraState",
    "CapturedCommand",
    "generate_scenario_frames",
    "generate_blackout_drop_scenario",
    "generate_laser_assault_scenario",
    "generate_strobe_train_scenario",
    "generate_pyro_flood_scenario",
    "generate_full_concert_set_scenario",
]
