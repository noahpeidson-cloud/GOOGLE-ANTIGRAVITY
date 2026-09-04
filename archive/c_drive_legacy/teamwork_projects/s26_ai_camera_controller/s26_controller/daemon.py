"""
daemon.py - Master Real-Time Camera Controller Daemon & Live Ingestion Pipeline

Links:
[Frame Ingestion (160x90 RGB / YUV)] -> [LightDetectorEngine] -> [ConcertStateMachine] -> [BaseDispatcher]

Guarantees:
- Real-time step() and process_frame() with sub-millisecond compute latency (<1.0ms)
- Thread-safe background execution loop for live video feeds / simulation streams
- Full telemetry logging, regime transition auditing, and performance stats
"""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union
import numpy as np

from s26_controller.core.config import DetectorConfig
from s26_controller.core.detector import LightDetectorEngine
from s26_controller.core.dispatcher import (
    BaseDispatcher,
    CameraPreset,
    DispatchResult,
    LightingRegime,
    MockDispatcher,
)
from s26_controller.core.metrics import FrameMetrics
from s26_controller.core.state_machine import ConcertStateMachine, StateMachineConfig
from s26_controller.simulation.light_simulator import (
    ConcertLightSimulator,
    ConcertScenario,
)


@dataclass
class DaemonStepResult:
    """Telemetry outcome of an individual frame processing step in the daemon loop."""
    frame_index: int
    timestamp_ns: int
    metrics: FrameMetrics
    regime: LightingRegime
    triggered: bool
    preset: Optional[CameraPreset] = None
    reason: str = ""
    dispatch_result: Optional[DispatchResult] = None
    compute_latency_ms: float = 0.0
    total_step_latency_ms: float = 0.0


@dataclass
class RegimeTransitionRecord:
    """Historical audit log entry of a lighting regime change."""
    transition_index: int
    frame_index: int
    timestamp_ns: int
    from_regime: LightingRegime
    to_regime: LightingRegime
    preset: Optional[CameraPreset]
    reason: str
    compute_latency_ms: float


@dataclass
class DaemonTelemetry:
    """Aggregated operational metrics and latency profile of the running daemon."""
    total_frames_processed: int
    total_dispatches: int
    current_regime: LightingRegime
    active_preset: Optional[CameraPreset]
    mean_compute_latency_ms: float
    min_compute_latency_ms: float
    max_compute_latency_ms: float
    p50_compute_latency_ms: float
    p95_compute_latency_ms: float
    p99_compute_latency_ms: float
    transitions: List[RegimeTransitionRecord] = field(default_factory=list)


class S26CameraControllerDaemon:
    """
    High-Performance Real-Time Camera Controller Daemon for Samsung Galaxy S26 Ultra.
    Orchestrates LightDetectorEngine, ConcertStateMachine, and BaseDispatcher.
    """

    def __init__(
        self,
        detector: Optional[LightDetectorEngine] = None,
        state_machine: Optional[ConcertStateMachine] = None,
        dispatcher: Optional[BaseDispatcher] = None,
        detector_config: Optional[DetectorConfig] = None,
        state_machine_config: Optional[StateMachineConfig] = None,
        history_buffer_size: int = 256,
    ) -> None:
        self.detector = detector or LightDetectorEngine(detector_config)
        self.state_machine = state_machine or ConcertStateMachine(state_machine_config)
        self.dispatcher = dispatcher or MockDispatcher()

        self.history_buffer_size = int(history_buffer_size)

        # Threading and lifecycle management
        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Telemetry and state tracking
        self.frame_count: int = 0
        self.dispatch_count: int = 0
        self.last_step_result: Optional[DaemonStepResult] = None
        self.active_preset: Optional[CameraPreset] = self.state_machine.get_active_preset()

        # Latency metric ring buffers (for stats)
        self._compute_latencies: List[float] = []
        self._transitions: List[RegimeTransitionRecord] = []
        self._recent_step_results: List[DaemonStepResult] = []

        # Callback hooks
        self.on_frame: Optional[Callable[[DaemonStepResult], None]] = None
        self.on_regime_change: Optional[Callable[[LightingRegime, LightingRegime, Optional[CameraPreset]], None]] = None
        self.on_preset_dispatched: Optional[Callable[[CameraPreset, DispatchResult], None]] = None

    @property
    def is_running(self) -> bool:
        """Returns True if background daemon loop is active."""
        return self._is_running

    @property
    def current_regime(self) -> LightingRegime:
        """Returns the currently active lighting regime."""
        return self.state_machine.current_regime

    def reset(self) -> None:
        """Resets all internal engines, metrics, and telemetry histories."""
        with self._lock:
            self.detector.reset()
            self.state_machine.reset()
            self.frame_count = 0
            self.dispatch_count = 0
            self.last_step_result = None
            self.active_preset = self.state_machine.get_active_preset()
            self._compute_latencies.clear()
            self._transitions.clear()
            self._recent_step_results.clear()

    def step(
        self,
        frame: np.ndarray,
        timestamp_ns: Optional[int] = None,
    ) -> DaemonStepResult:
        """
        Executes a single synchronous real-time frame processing step:
        1. Analyzes frame luminance & spatial zones (<0.2ms)
        2. Evaluates state machine & hysteresis (<0.1ms)
        3. Dispatches UI adjustment preset if triggered (<35ms on ADB, <0.01ms on Mock)

        Returns DaemonStepResult with complete telemetry and latency accounting.
        """
        t_start = time.perf_counter_ns()
        if timestamp_ns is None:
            timestamp_ns = t_start

        with self._lock:
            self.frame_count += 1
            idx = self.frame_count

            # 1. Detection Stage
            if frame.ndim == 3:
                metrics = self.detector.analyze_frame_rgb(frame, timestamp_ns=timestamp_ns)
            elif frame.ndim == 2:
                metrics = self.detector.analyze_luma_frame(frame, timestamp_ns=timestamp_ns)
            else:
                raise ValueError(f"Invalid frame shape: {frame.shape}, expected 2D (H,W) or 3D (H,W,3)")

            # Track regime prior to state machine evaluation
            prev_regime = self.state_machine.current_regime

            # 2. State Machine & Reactive Hysteresis Stage
            triggered, preset, reason = self.state_machine.process_frame(metrics)

            t_compute_end = time.perf_counter_ns()
            compute_latency_ms = (t_compute_end - t_start) * 1e-6

            # 3. UI Intent Dispatch Stage
            dispatch_res: Optional[DispatchResult] = None
            if triggered and preset is not None:
                dispatch_res = self.dispatcher.dispatch_camera_preset(preset)
                self.dispatch_count += 1
                self.active_preset = preset

                # Transition record
                trans_rec = RegimeTransitionRecord(
                    transition_index=len(self._transitions) + 1,
                    frame_index=idx,
                    timestamp_ns=timestamp_ns,
                    from_regime=prev_regime,
                    to_regime=preset.regime,
                    preset=preset,
                    reason=reason,
                    compute_latency_ms=compute_latency_ms,
                )
                self._transitions.append(trans_rec)

                # Callback triggers
                if self.on_regime_change:
                    try:
                        self.on_regime_change(prev_regime, preset.regime, preset)
                    except Exception:
                        pass

                if self.on_preset_dispatched and dispatch_res:
                    try:
                        self.on_preset_dispatched(preset, dispatch_res)
                    except Exception:
                        pass

            t_step_end = time.perf_counter_ns()
            total_step_latency_ms = (t_step_end - t_start) * 1e-6

            # Record compute latency in buffer
            self._compute_latencies.append(compute_latency_ms)
            if len(self._compute_latencies) > 10000:
                self._compute_latencies.pop(0)

            result = DaemonStepResult(
                frame_index=idx,
                timestamp_ns=timestamp_ns,
                metrics=metrics,
                regime=self.state_machine.current_regime,
                triggered=triggered,
                preset=preset,
                reason=reason,
                dispatch_result=dispatch_res,
                compute_latency_ms=compute_latency_ms,
                total_step_latency_ms=total_step_latency_ms,
            )

            self.last_step_result = result

            # Maintain recent results buffer
            self._recent_step_results.append(result)
            if len(self._recent_step_results) > self.history_buffer_size:
                self._recent_step_results.pop(0)

        # Frame callback outside lock
        if self.on_frame:
            try:
                self.on_frame(result)
            except Exception:
                pass

        return result

    def process_frame(
        self,
        frame: np.ndarray,
        timestamp_ns: Optional[int] = None,
    ) -> DaemonStepResult:
        """Alias for step()."""
        return self.step(frame, timestamp_ns)

    def process_stream(
        self,
        frame_stream: Iterator[Tuple[np.ndarray, int]],
        fps: float = 60.0,
        real_time: bool = False,
    ) -> List[DaemonStepResult]:
        """
        Synchronously processes a stream or generator of frames.
        """
        results: List[DaemonStepResult] = []
        frame_interval_sec = 1.0 / max(1.0, fps)

        for frame, t_ns in frame_stream:
            t0 = time.perf_counter()
            res = self.step(frame, timestamp_ns=t_ns)
            results.append(res)
            if real_time:
                elapsed = time.perf_counter() - t0
                sleep_dur = frame_interval_sec - elapsed
                if sleep_dur > 0:
                    time.sleep(sleep_dur)

        return results

    def process_scenario(
        self,
        scenario: Union[ConcertScenario, str],
        fps: float = 60.0,
        duration_sec: Optional[float] = None,
        as_rgb: bool = True,
        real_time: bool = False,
    ) -> List[DaemonStepResult]:
        """
        Executes a synthetic concert scenario through the controller daemon.
        """
        simulator = ConcertLightSimulator(fps=fps)
        stream = simulator.stream_scenario(
            scenario=scenario,
            duration_sec=duration_sec,
            as_rgb=as_rgb,
            real_time=False,
        )
        return self.process_stream(stream, fps=fps, real_time=real_time)

    def start_background_stream(
        self,
        frame_source_generator: Iterator[Tuple[np.ndarray, int]],
        fps: float = 60.0,
        real_time: bool = True,
    ) -> None:
        """
        Launches the daemon execution loop in a dedicated background worker thread.
        """
        if self._is_running:
            return

        self._stop_event.clear()
        self._is_running = True

        def _worker_loop():
            frame_interval_sec = 1.0 / max(1.0, fps)
            for frame, t_ns in frame_source_generator:
                if self._stop_event.is_set():
                    break
                t0 = time.perf_counter()
                self.step(frame, timestamp_ns=t_ns)
                if real_time:
                    elapsed = time.perf_counter() - t0
                    sleep_dur = frame_interval_sec - elapsed
                    if sleep_dur > 0:
                        time.sleep(sleep_dur)
            self._is_running = False

        self._thread = threading.Thread(target=_worker_loop, daemon=True, name="S26CameraControllerDaemon")
        self._thread.start()

    def stop(self) -> None:
        """Stops background execution loop gracefully."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._is_running = False
        self._thread = None

    def get_telemetry(self) -> DaemonTelemetry:
        """Computes statistical summary and latency percentiles."""
        with self._lock:
            lats = np.array(self._compute_latencies, dtype=np.float32) if self._compute_latencies else np.array([0.0])
            mean_lat = float(np.mean(lats))
            min_lat = float(np.min(lats))
            max_lat = float(np.max(lats))
            p50_lat = float(np.percentile(lats, 50))
            p95_lat = float(np.percentile(lats, 95))
            p99_lat = float(np.percentile(lats, 99))

            return DaemonTelemetry(
                total_frames_processed=self.frame_count,
                total_dispatches=self.dispatch_count,
                current_regime=self.state_machine.current_regime,
                active_preset=self.active_preset,
                mean_compute_latency_ms=mean_lat,
                min_compute_latency_ms=min_lat,
                max_compute_latency_ms=max_lat,
                p50_compute_latency_ms=p50_lat,
                p95_compute_latency_ms=p95_lat,
                p99_compute_latency_ms=p99_lat,
                transitions=list(self._transitions),
            )

    def assert_performance_contract(self, max_p99_compute_latency_ms: float = 1.0) -> None:
        """
        Strictly asserts that the P99 decision latency of the detector + state machine
        is below the required threshold (<1.0ms).
        """
        telemetry = self.get_telemetry()
        assert telemetry.p99_compute_latency_ms < max_p99_compute_latency_ms, (
            f"Performance Contract Breach: P99 compute latency {telemetry.p99_compute_latency_ms:.3f}ms "
            f"exceeds maximum allowed threshold of {max_p99_compute_latency_ms:.3f}ms!"
        )

    def close(self) -> None:
        """Cleans up background threads and dispatches."""
        self.stop()
        if self.dispatcher:
            self.dispatcher.close()

    def __enter__(self) -> S26CameraControllerDaemon:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
