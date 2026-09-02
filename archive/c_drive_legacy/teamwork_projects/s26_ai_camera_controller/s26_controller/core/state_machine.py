"""
state_machine.py - Reactive Event Trigger Engine & Concert State Machine

Implements event-driven lighting regime state machine for live EDM concerts:
- Regimes: NORMAL, BLACKOUT, LASER_SPIKE, FLOOD_PYRO, STROBE_LOCK
- Dual-threshold hysteresis (Blackout Y_mean < 8.0 / >= 25.0; Laser P99 >= 250 / <= 200)
- 350ms minimum dwell window for standard transitions to prevent transient noise triggers
- Emergency single-frame bypass for critical laser arrays (P99 >= 250 & c_high >= 0.08)
- Debounce governor & rate limiter (maximum 2.0 Hz actuation rate / 500ms cooldown)
- Dynamic CameraPreset generation for Pro Video exposure automation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from s26_controller.core.metrics import FrameMetrics
from s26_controller.core.dispatcher import LightingRegime, CameraPreset
from s26_controller.core.strobe_filter import StrobeFilter, StrobeMetrics


@dataclass
class StateMachineConfig:
    """Configuration parameters and hysteresis boundaries for ConcertStateMachine."""
    # Timing & Debounce parameters
    dwell_time_ms: float = 350.0          # Minimum dwell before standard regime change
    cooldown_ms: float = 500.0            # Minimum interval between dispatches (2.0 Hz max)
    min_persistence_frames: int = 2       # Consecutive frames required for standard transition

    # Blackout regime thresholds
    blackout_enter_luma: float = 8.0
    blackout_enter_cdark: float = 0.85
    blackout_exit_luma: float = 25.0
    blackout_exit_cdark: float = 0.50

    # Laser spike regime thresholds
    laser_enter_p99: float = 250.0
    laser_enter_chigh: float = 0.04
    laser_stage_p99: float = 252.0
    laser_stage_chigh: float = 0.03
    laser_exit_p99: float = 200.0
    laser_exit_chigh: float = 0.01

    # Emergency single-frame laser bypass thresholds
    emergency_laser_p99: float = 250.0
    emergency_laser_chigh: float = 0.08
    emergency_ceiling_p99: float = 254.0
    emergency_ceiling_chigh: float = 0.08

    # Full Arena Flood / Pyro thresholds
    flood_enter_luma: float = 195.0
    flood_enter_chigh: float = 0.40
    flood_exit_luma: float = 140.0

    # Strobe filter settings
    strobe_holdoff_ms: float = 400.0
    strobe_min_freq_hz: float = 6.0
    strobe_max_freq_hz: float = 25.0


# Default Pro Video camera presets per lighting regime
DEFAULT_CAMERA_PRESETS: Dict[LightingRegime, CameraPreset] = {
    LightingRegime.NORMAL: CameraPreset(
        iso=400,
        shutter_speed="1/60",
        regime=LightingRegime.NORMAL,
        reason="Normal balanced stage exposure",
    ),
    LightingRegime.BLACKOUT: CameraPreset(
        iso=200,
        shutter_speed="1/60",
        regime=LightingRegime.BLACKOUT,
        reason="Pre-drop blackout lock (noise suppression)",
    ),
    LightingRegime.LASER_SPIKE: CameraPreset(
        iso=100,
        shutter_speed="1/250",
        regime=LightingRegime.LASER_SPIKE,
        reason="Laser burst protection clamp",
    ),
    LightingRegime.FLOOD_PYRO: CameraPreset(
        iso=100,
        shutter_speed="1/125",
        regime=LightingRegime.FLOOD_PYRO,
        reason="Full arena pyro/flood washout clamp",
    ),
    LightingRegime.STROBE_LOCK: CameraPreset(
        iso=400,
        shutter_speed="1/60",
        regime=LightingRegime.STROBE_LOCK,
        reason="Strobe lock active (AE frozen)",
    ),
}


class ConcertStateMachine:
    """
    Reactive event trigger state machine with dual-threshold hysteresis,
    350ms dwell window, 2.0 Hz rate limiting, emergency single-frame laser bypass,
    and strobe lock anti-hunting integration.
    """

    def __init__(
        self,
        config: Optional[StateMachineConfig] = None,
        strobe_filter: Optional[StrobeFilter] = None,
        presets: Optional[Dict[LightingRegime, CameraPreset]] = None,
        initial_regime: LightingRegime = LightingRegime.NORMAL,
    ) -> None:
        self.config = config or StateMachineConfig()
        self.presets = dict(presets or DEFAULT_CAMERA_PRESETS)

        self.strobe_filter = strobe_filter or StrobeFilter(
            min_frequency_hz=self.config.strobe_min_freq_hz,
            max_frequency_hz=self.config.strobe_max_freq_hz,
            cessation_holdoff_ms=self.config.strobe_holdoff_ms,
        )

        # State tracking
        self.current_regime: LightingRegime = initial_regime
        self.last_regime_change_timestamp_ns: int = 0
        self.last_dispatch_timestamp_ns: int = 0
        self.total_frames_processed: int = 0
        self.total_dispatches: int = 0

        # Persistence counters for standard transitions
        self.blackout_persist_count: int = 0
        self.laser_persist_count: int = 0
        self.flood_persist_count: int = 0

    @property
    def current_state(self) -> LightingRegime:
        """Alias for current_regime."""
        return self.current_regime

    def reset(self) -> None:
        """Resets state machine, persistence counters, and strobe filter."""
        self.current_regime = LightingRegime.NORMAL
        self.last_regime_change_timestamp_ns = 0
        self.last_dispatch_timestamp_ns = 0
        self.total_frames_processed = 0
        self.total_dispatches = 0
        self.blackout_persist_count = 0
        self.laser_persist_count = 0
        self.flood_persist_count = 0
        self.strobe_filter.reset()

    def get_preset_for_regime(self, regime: LightingRegime) -> Optional[CameraPreset]:
        """Returns the configured CameraPreset for the given regime."""
        return self.presets.get(regime)

    def get_active_preset(self) -> Optional[CameraPreset]:
        """Returns the CameraPreset for the currently active regime."""
        return self.presets.get(self.current_regime)

    def _check_flood_candidate(self, metrics: FrameMetrics) -> bool:
        """Checks if scene illumination matches full arena pyro or flood washout."""
        return (
            metrics.mean_luma >= self.config.flood_enter_luma
            and metrics.c_high >= self.config.flood_enter_chigh
        )

    def _check_emergency_laser(self, metrics: FrameMetrics) -> bool:
        """
        Determines whether the frame contains a critical direct laser array strike
        requiring immediate single-frame emergency exposure clamp.
        """
        if metrics.mean_luma >= self.config.flood_enter_luma:
            return False

        # Global sensor saturation
        if metrics.p99 >= self.config.emergency_laser_p99 and metrics.c_high >= self.config.emergency_laser_chigh:
            return True

        # Ceiling zone specific blast
        ceiling_luma = metrics.zone_lumas.get("ceiling", 0.0)
        if ceiling_luma >= 220.0 and metrics.c_high >= self.config.emergency_ceiling_chigh:
            return True

        return False

    def _check_laser_candidate(self, metrics: FrameMetrics) -> bool:
        """Checks standard laser spike candidate conditions across global and zonal metrics."""
        if metrics.mean_luma >= self.config.flood_enter_luma:
            return False

        # Global laser threshold
        if metrics.p99 >= self.config.laser_enter_p99 and metrics.c_high >= self.config.laser_enter_chigh:
            return True

        # Ceiling zone laser array
        ceiling_luma = metrics.zone_lumas.get("ceiling", 0.0)
        if ceiling_luma >= 220.0 and metrics.c_high >= 0.03:
            return True

        # Stage laser blast
        stage_luma = metrics.zone_lumas.get("stage_center", 0.0)
        if stage_luma >= self.config.laser_stage_p99 and metrics.c_high >= self.config.laser_stage_chigh:
            return True

        return False

    def _check_blackout_candidate(self, metrics: FrameMetrics) -> bool:
        """Checks if scene illumination matches pitch-black pre-drop tension."""
        return (
            metrics.mean_luma < self.config.blackout_enter_luma
            and metrics.c_dark >= self.config.blackout_enter_cdark
        )

    def process_frame(self, metrics: FrameMetrics) -> Tuple[bool, Optional[CameraPreset], str]:
        """
        Processes a telemetry frame through the state machine.

        Returns:
            Tuple[bool, Optional[CameraPreset], str]:
                - bool: True if an action intent was triggered to dispatch to camera controls.
                - Optional[CameraPreset]: Target CameraPreset to apply (or None if not triggered / frozen).
                - str: Human-readable diagnostic reason string.
        """
        now_ns = int(metrics.timestamp_ns)
        self.total_frames_processed += 1

        # 1. Strobe Filter update
        strobe_res = self.strobe_filter.process(metrics)

        # 2. Candidate checks (Flood > Laser > Blackout)
        is_flood = self._check_flood_candidate(metrics)
        is_emergency_laser = self._check_emergency_laser(metrics)
        is_laser = self._check_laser_candidate(metrics)
        is_blackout = self._check_blackout_candidate(metrics)

        # 3. Persistence Counter Updates
        if is_flood:
            self.flood_persist_count += 1
        else:
            self.flood_persist_count = 0

        if is_laser or is_emergency_laser:
            self.laser_persist_count += 1
        else:
            self.laser_persist_count = 0

        if is_blackout:
            self.blackout_persist_count += 1
        else:
            self.blackout_persist_count = 0

        # 4. Determine Proposed Regime
        current = self.current_regime
        proposed = current

        if strobe_res.is_strobe:
            # Active strobe pulse train forces STROBE_LOCK
            proposed = LightingRegime.STROBE_LOCK
        elif current == LightingRegime.STROBE_LOCK:
            # Strobe has ceased past the holdoff window -> determine current baseline
            if is_flood and self.flood_persist_count >= self.config.min_persistence_frames:
                proposed = LightingRegime.FLOOD_PYRO
            elif is_laser and self.laser_persist_count >= self.config.min_persistence_frames:
                proposed = LightingRegime.LASER_SPIKE
            elif is_blackout and self.blackout_persist_count >= self.config.min_persistence_frames:
                proposed = LightingRegime.BLACKOUT
            else:
                proposed = LightingRegime.NORMAL

        elif current == LightingRegime.NORMAL:
            if is_flood and self.flood_persist_count >= self.config.min_persistence_frames:
                proposed = LightingRegime.FLOOD_PYRO
            elif is_emergency_laser or self.laser_persist_count >= self.config.min_persistence_frames:
                proposed = LightingRegime.LASER_SPIKE
            elif self.blackout_persist_count >= self.config.min_persistence_frames:
                proposed = LightingRegime.BLACKOUT
            else:
                proposed = LightingRegime.NORMAL

        elif current == LightingRegime.BLACKOUT:
            # Flood or Laser take absolute priority over blackout
            if is_flood and self.flood_persist_count >= self.config.min_persistence_frames:
                proposed = LightingRegime.FLOOD_PYRO
            elif is_emergency_laser or self.laser_persist_count >= self.config.min_persistence_frames:
                proposed = LightingRegime.LASER_SPIKE
            elif is_laser or is_flood:
                # Accumulating persistence for laser or flood, hold in blackout
                proposed = LightingRegime.BLACKOUT
            elif metrics.mean_luma >= self.config.blackout_exit_luma or metrics.c_dark < self.config.blackout_exit_cdark:
                # Blackout exit hysteresis met
                proposed = LightingRegime.NORMAL
            else:
                proposed = LightingRegime.BLACKOUT

        elif current == LightingRegime.LASER_SPIKE:
            if is_flood and self.flood_persist_count >= self.config.min_persistence_frames:
                proposed = LightingRegime.FLOOD_PYRO
            elif metrics.p99 <= self.config.laser_exit_p99 and metrics.c_high <= self.config.laser_exit_chigh:
                proposed = LightingRegime.NORMAL
            else:
                proposed = LightingRegime.LASER_SPIKE

        elif current == LightingRegime.FLOOD_PYRO:
            if metrics.mean_luma <= self.config.flood_exit_luma:
                proposed = LightingRegime.NORMAL
            else:
                proposed = LightingRegime.FLOOD_PYRO

        # 5. Evaluate Timing, Dwell, and Debounce
        time_since_regime_change_ms = (
            (now_ns - self.last_regime_change_timestamp_ns) * 1e-6
            if self.last_regime_change_timestamp_ns > 0
            else float("inf")
        )
        time_since_last_dispatch_ms = (
            (now_ns - self.last_dispatch_timestamp_ns) * 1e-6
            if self.last_dispatch_timestamp_ns > 0
            else float("inf")
        )

        dwell_ok = time_since_regime_change_ms >= self.config.dwell_time_ms
        cooldown_ok = time_since_last_dispatch_ms >= self.config.cooldown_ms

        # 6. Dispatch Decision Logic
        # Case 1: Entering or continuing STROBE_LOCK
        if proposed == LightingRegime.STROBE_LOCK:
            if current != LightingRegime.STROBE_LOCK:
                self.current_regime = LightingRegime.STROBE_LOCK
                self.last_regime_change_timestamp_ns = now_ns
                return (
                    False,
                    None,
                    f"Strobe pulse train detected ({strobe_res.frequency_hz:.1f} Hz) - Exposure frozen",
                )
            return (
                False,
                None,
                f"Strobe lock active ({strobe_res.frequency_hz:.1f} Hz) - AE adjustment suppressed",
            )

        # Case 2: Regime Transition Requested
        if proposed != current:
            # Special Case: Emergency Single-Frame Laser Bypass
            if proposed == LightingRegime.LASER_SPIKE and is_emergency_laser:
                self.current_regime = proposed
                self.last_regime_change_timestamp_ns = now_ns
                self.last_dispatch_timestamp_ns = now_ns
                self.total_dispatches += 1
                preset = self.get_preset_for_regime(proposed)
                return (
                    True,
                    preset,
                    f"EMERGENCY single-frame laser bypass triggered: {preset.reason if preset else 'Laser Protection'}",
                )

            # Exiting STROBE_LOCK or Standard Transition: Enforce dwell & rate limit
            is_strobe_exit = (current == LightingRegime.STROBE_LOCK)
            if (dwell_ok or is_strobe_exit) and (cooldown_ok or is_strobe_exit):
                self.current_regime = proposed
                self.last_regime_change_timestamp_ns = now_ns
                self.last_dispatch_timestamp_ns = now_ns
                self.total_dispatches += 1
                preset = self.get_preset_for_regime(proposed)
                return (
                    True,
                    preset,
                    f"State transitioned from {current.value} to {proposed.value}: {preset.reason if preset else ''}",
                )
            else:
                reason_blocked = []
                if not dwell_ok:
                    reason_blocked.append(f"dwell window ({time_since_regime_change_ms:.0f}ms < {self.config.dwell_time_ms}ms)")
                if not cooldown_ok:
                    reason_blocked.append(f"cooldown ({time_since_last_dispatch_ms:.0f}ms < {self.config.cooldown_ms}ms)")
                return (
                    False,
                    None,
                    f"Transition to {proposed.value} deferred by {', '.join(reason_blocked)}",
                )

        # Case 3: Steady State
        return False, None, f"Steady state in {current.value}"
