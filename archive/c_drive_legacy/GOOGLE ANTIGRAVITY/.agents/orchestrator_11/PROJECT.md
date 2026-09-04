# Project: S26 AI Camera Controller (Samsung Galaxy S26 Ultra EDM PoC)

## Architecture
A decoupled on-device camera exposure control system that preserves native Samsung Camera 200MP Tetra²pixel binning and 10-bit HDR10+ Pro Video processing by automating UI sliders (ISO, Shutter Speed) via accessibility/ADB touch dispatch triggered by an offline, real-time light level heuristic analyzer.

```
[Raw Frame / Sensor Ingestion (160x90 Gray/RGB)]
                     │
                     ▼
[Offline ML & Heuristic Detector (Rec.709 Luma, 4-Zone ROI, 16-Bin Hist, Percentiles)]
                     │
                     ▼
[Reactive State Machine (Hysteresis, Strobe Lock 6-25Hz, Laser Spikes, Blackout Drop)]
                     │
                     ▼
[UI Automator & Intent Dispatcher (Resolution-Aware Touch Coordinates, ADB/Accessibility/Tasker)]
                     │
                     ▼
[Samsung Galaxy S26 Ultra Pro Video Mode (ISO / Shutter Sliders Tap Simulation)]
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Integer Rec.709 Luminance Extractor | Vectorized integer bit-shift luma calculation ($Y = (54R+183G+19B)\gg 8$) executing in <0.2ms | M1 | Survey R1 |
| 2 | 4-Zone Spatial ROI Slicing | Stage Center, Ceiling, Flanks, Crowd Floor zonal luminance segmentation | M1 | Survey R1 |
| 3 | 16-Bin Micro-Histogram & Percentiles | Fast $P_{10}, P_{50}, P_{90}, P_{99}$ percentile metrics & saturation counting ($C_{high}, C_{dark}$) | M1 | Survey R1 |
| 4 | Offline Isolation Guarantee | Strict 0-network dependency verification for Airplane Mode compatibility | M1 | Survey R1 |
| 5 | Pro Video Coordinate Model | Normalized float touch coordinate mapping for WQHD+ (3120x1440) and FHD+ (2340x1080) | M2 | Survey R2 |
| 6 | Modular Dispatch Engine | Abstract multi-provider dispatcher supporting Persistent ADB Pipe, Tasker Intent, Accessibility Script, and Mock | M2 | Survey R2 |
| 7 | Sub-50ms Tap Dispatcher | Persistent shell pipe for <35ms touch latency execution on Android | M2 | Survey R2 |
| 8 | Concert State Machine | Event-driven lighting regime state machine (Normal, Blackout, LaserSpike, FloodPyro, StrobeLock) | M3 | Survey R3 |
| 9 | Strobe Lock & Anti-Hunting Filter | Autocorrelation / zero-crossing 6-25Hz strobe train detector that freezes exposure | M3 | Survey R3 |
| 10 | Emergency Laser Bypass & Debounce | Fast single-frame laser bypass with 350ms dwell window and 2.0Hz rate limiter for standard transitions | M3 | Survey R3 |
| 11 | Controller Loop Daemon & CLI | Integrated real-time processing loop linking Ingestion -> Detector -> StateMachine -> Dispatcher | M4 | Survey R1-R3 |
| 12 | Concert Light Simulator | Synthetic scenario generator for Sunbar concert dynamics (Blackout, Laser bursts, Strobe trains, Normal) | M4 | Survey Acceptance |
| 13 | E2E Testing Suite (Tiers 1-4) | Opaque-box requirement tests for offline execution, latency budgets, state transitions, parameter maps | M5 | Survey Acceptance |
| 14 | Latency & Trigger Verification Script | Automated standalone test script (`test_automation.py`) verifying <500ms light spike trigger latency | M5 | Survey Acceptance |
| 15 | Adversarial Hardening (Tier 5) | White-box stress testing against rapid flicker, frame drops, extreme noisy inputs, and boundary conditions | M5 | Survey Acceptance |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Offline ML Light Detector | Vectorized luma, 4-zone ROI, 16-bin histogram, percentile metrics, zero-network offline architecture | none | DONE |
| 2 | M2: Pro Video UI Automator | Resolution-aware coordinate maps (WQHD+/FHD+), multi-provider dispatcher (ADB/Tasker/Mock) | none | DONE |
| 3 | M3: Reactive State Engine | Dual-threshold hysteresis, 6-25Hz strobe lock, emergency laser bypass, debounce rate limiter | M1 | DONE |
| 4 | M4: Integration Daemon & Simulator | Controller daemon, CLI runner, Sunbar concert lighting simulation harness | M1, M2, M3 | DONE |
| 5 | M5: E2E Test Suite & Verification | Tier 1-4 tests, test_automation.py (<500ms latency assertion), Tier 5 adversarial hardening | M4 | DONE |

## Interface Contracts

### M1 Detector ↔ M3 State Machine
```python
@dataclass(frozen=True)
class FrameMetrics:
    timestamp_ns: int
    mean_luma: float          # 0.0 - 255.0
    p10: float
    p50: float
    p90: float
    p99: float
    c_high: float             # Ratio of pixels >= 245
    c_dark: float             # Ratio of pixels <= 10
    zone_lumas: dict[str, float]  # {'ceiling', 'stage_center', 'stage_flanks', 'crowd_floor'}
    luma_velocity: float      # delta luma / delta time
```

### M3 State Machine ↔ M2 UI Automator
```python
class LightingRegime(str, Enum):
    NORMAL = "NORMAL"
    BLACKOUT = "BLACKOUT"
    LASER_SPIKE = "LASER_SPIKE"
    FLOOD_PYRO = "FLOOD_PYRO"
    STROBE_LOCK = "STROBE_LOCK"

@dataclass(frozen=True)
class CameraPreset:
    iso: int                  # e.g. 100, 200, 400, 800
    shutter_speed: str        # e.g. "1/60", "1/125", "1/250", "1/500"
    regime: LightingRegime
    reason: str

# Dispatch contract
def dispatch_preset(preset: CameraPreset, resolution: tuple[int, int]) -> DispatchResult: ...
```

## Code Layout
Target Project Root: `C:\Users\noahp\teamwork_projects\s26_ai_camera_controller`
```
s26_ai_camera_controller/
├── pyproject.toml
├── requirements.txt
├── README.md
├── test_automation.py              # User acceptance script (<500ms trigger verification)
├── s26_controller/
│   ├── __init__.py
│   ├── cli.py                     # CLI entrypoint
│   ├── config.py                  # Presets & coordinate configurations
│   ├── daemon.py                  # Real-time controller daemon
│   ├── core/
│   │   ├── __init__.py
│   │   ├── detector.py            # M1: Vectorized Rec.709 Luma & ROI Analyzer
│   │   ├── metrics.py             # M1: Statistical metrics & percentiles
│   │   ├── coordinates.py         # M2: S26 Ultra Pro Video coordinate mapping
│   │   ├── dispatcher.py          # M2: ADB / Tasker / Mock Touch Dispatcher
│   │   ├── state_machine.py       # M3: Reactive Event Trigger State Machine
│   │   └── strobe_filter.py       # M3: 6-25Hz Strobe Autocorrelation Lock
│   └── simulation/
│       ├── __init__.py
│       ├── light_simulator.py     # M4: EDM Concert Lighting Simulator
│       └── mock_device.py         # M4: Mock ADB / Android Camera Environment
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_detector_offline.py   # Tier 1: Offline ML & Luma metrics
    ├── test_ui_dispatcher.py      # Tier 1: Coordinate mapping & ADB dispatch
    ├── test_state_machine.py      # Tier 2: Hysteresis, strobe lock & anti-chatter
    ├── test_integration_e2e.py    # Tier 3: Full pipeline integration
    ├── test_concert_scenarios.py  # Tier 4: Sunbar concert scenario tests
    ├── test_latency_e2e.py        # Tier 4: <500ms latency verification
    └── test_adversarial_stress.py # Tier 5: Adversarial edge cases & noise
```
