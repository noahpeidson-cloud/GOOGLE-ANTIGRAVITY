"""
strobe_filter.py - 6-25Hz Strobe Autocorrelation Lock & Anti-Hunting Filter

Provides periodic pulse detection, sliding window variance tracking, zero-crossing
derivative analysis, and normalized autocorrelation for high-frequency strobe trains
(6-25 Hz) in live EDM concert lighting. Freezes exposure controls during strobe bursts
to prevent camera Auto-Exposure (AE) hunting and slider oscillation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

from s26_controller.core.metrics import FrameMetrics


@dataclass(frozen=True)
class StrobeMetrics:
    """Telemetry and diagnostic metrics produced by the strobe filter."""
    is_strobe: bool
    frequency_hz: float
    amplitude: float
    variance: float
    zero_crossings: int
    autocorrelation_peak: float
    dominant_period_frames: int


class StrobeFilter:
    """
    Sliding window periodic pulse detector and frequency estimator.
    Analyzes temporal luminance oscillations using zero-crossings of velocity
    and normalized autocorrelation across a rolling frame buffer.
    """

    def __init__(
        self,
        min_frequency_hz: float = 6.0,
        max_frequency_hz: float = 25.0,
        min_amplitude: float = 50.0,
        min_variance: float = 150.0,
        min_zero_crossings: int = 4,
        min_autocorrelation_peak: float = 0.35,
        window_size: int = 64,
        cessation_holdoff_ms: float = 400.0,
        fps: float = 60.0,
    ) -> None:
        if min_frequency_hz <= 0 or max_frequency_hz <= min_frequency_hz:
            raise ValueError(f"Invalid frequency range: ({min_frequency_hz}, {max_frequency_hz})")
        if window_size < 16:
            raise ValueError(f"window_size must be >= 16, got {window_size}")

        self.min_frequency_hz = float(min_frequency_hz)
        self.max_frequency_hz = float(max_frequency_hz)
        self.min_amplitude = float(min_amplitude)
        self.min_variance = float(min_variance)
        self.min_zero_crossings = int(min_zero_crossings)
        self.min_autocorrelation_peak = float(min_autocorrelation_peak)
        self.window_size = int(window_size)
        self.cessation_holdoff_sec = float(cessation_holdoff_ms) / 1000.0
        self.fps = float(fps)

        # Ring Buffers for sliding window analysis
        self._history_luma = np.zeros(self.window_size, dtype=np.float32)
        self._history_timestamps_ns = np.zeros(self.window_size, dtype=np.int64)
        self._head: int = 0
        self._total_frames: int = 0

        # State tracking
        self._strobe_active: bool = False
        self._last_pulse_timestamp_ns: int = 0
        self._current_frequency_hz: float = 0.0
        self._last_metrics: Optional[StrobeMetrics] = None

    @property
    def is_active(self) -> bool:
        """Returns True if strobe lock is currently engaged."""
        return self._strobe_active

    @property
    def current_frequency_hz(self) -> float:
        """Returns the most recently estimated strobe frequency in Hz (0.0 if inactive)."""
        return self._current_frequency_hz

    def reset(self) -> None:
        """Resets all sliding window history and state tracking."""
        self._history_luma.fill(0.0)
        self._history_timestamps_ns.fill(0)
        self._head = 0
        self._total_frames = 0
        self._strobe_active = False
        self._last_pulse_timestamp_ns = 0
        self._current_frequency_hz = 0.0
        self._last_metrics = None

    @staticmethod
    def compute_autocorrelation(signal: np.ndarray) -> Tuple[np.ndarray, float, int]:
        """
        Computes normalized zero-mean autocorrelation for 1D signal.
        Returns: (r_norm, peak_value, peak_lag)
        """
        n = len(signal)
        if n < 4:
            return np.array([1.0], dtype=np.float32), 0.0, 0

        mean = float(np.mean(signal))
        centered = signal - mean
        variance = float(np.sum(centered ** 2))

        if variance < 1e-6:
            return np.zeros(n, dtype=np.float32), 0.0, 0

        # Compute autocorrelation for positive lags
        r = np.correlate(centered, centered, mode="full")[n - 1:]
        r_norm = r / variance

        # Look for dominant periodic peak in lag range [2, n // 2]
        min_lag = 2
        max_lag = max(min_lag + 1, n // 2)
        if max_lag > min_lag:
            search_window = r_norm[min_lag:max_lag]
            if len(search_window) > 0:
                best_rel_lag = int(np.argmax(search_window))
                peak_lag = min_lag + best_rel_lag
                peak_val = float(r_norm[peak_lag])
                return r_norm, peak_val, peak_lag

        return r_norm, 0.0, 0

    def process(self, metrics: FrameMetrics) -> StrobeMetrics:
        """
        Ingests the latest frame metrics, updates sliding window buffers,
        evaluates periodic strobe properties, and returns StrobeMetrics.
        """
        luma = float(metrics.mean_luma)
        timestamp_ns = int(metrics.timestamp_ns)
        now_sec = timestamp_ns * 1e-9

        # Store in ring buffer
        self._history_luma[self._head] = luma
        self._history_timestamps_ns[self._head] = timestamp_ns
        self._head = (self._head + 1) % self.window_size
        self._total_frames += 1

        # Insufficient history for statistical frequency estimation
        if self._total_frames < 8:
            result = StrobeMetrics(
                is_strobe=self._strobe_active,
                frequency_hz=self._current_frequency_hz,
                amplitude=0.0,
                variance=0.0,
                zero_crossings=0,
                autocorrelation_peak=0.0,
                dominant_period_frames=0,
            )
            self._last_metrics = result
            return result

        # Extract ordered chronological window
        effective_len = min(self._total_frames, self.window_size)
        all_indices = [(self._head - effective_len + i) % self.window_size for i in range(effective_len)]

        # Filter to recent window within the last 600ms
        max_lookback_ns = int(0.600 * 1e9)
        recent_indices = [
            idx for idx in all_indices
            if (timestamp_ns - self._history_timestamps_ns[idx]) <= max_lookback_ns
        ]

        if len(recent_indices) < 8:
            if self._strobe_active and self._last_pulse_timestamp_ns > 0:
                time_since_pulse = now_sec - (self._last_pulse_timestamp_ns * 1e-9)
                if time_since_pulse <= self.cessation_holdoff_sec:
                    self._strobe_active = True
                else:
                    self._strobe_active = False
                    self._current_frequency_hz = 0.0
            else:
                self._strobe_active = False
                self._current_frequency_hz = 0.0

            result = StrobeMetrics(
                is_strobe=self._strobe_active,
                frequency_hz=self._current_frequency_hz,
                amplitude=0.0,
                variance=0.0,
                zero_crossings=0,
                autocorrelation_peak=0.0,
                dominant_period_frames=0,
            )
            self._last_metrics = result
            return result

        sample_luma = self._history_luma[recent_indices]
        sample_times = self._history_timestamps_ns[recent_indices]

        # 1. Amplitude & Variance
        min_luma = float(np.min(sample_luma))
        max_luma = float(np.max(sample_luma))
        amplitude = max_luma - min_luma
        variance = float(np.var(sample_luma))

        # 2. Time delta and effective sample rate across the window
        dt_ns = sample_times[-1] - sample_times[0]
        if dt_ns > 0:
            dt_sec = dt_ns * 1e-9
            effective_fps = (len(recent_indices) - 1) / dt_sec
        else:
            dt_sec = (len(recent_indices) - 1) / self.fps
            effective_fps = self.fps
        dt_sec = max(dt_sec, 0.01)

        # 3. First derivative velocity and zero crossings (with noise deadband filtering)
        diffs = np.diff(sample_luma)
        significant_diffs = diffs[np.abs(diffs) >= 4.0]
        if len(significant_diffs) > 1:
            zero_crossings = int(len(np.where(np.diff(np.signbit(significant_diffs)))[0]))
        else:
            zero_crossings = 0

        # Frequency estimate from zero crossings: (crossings / 2) / duration_seconds
        freq_zero_crossings = (zero_crossings / 2.0) / dt_sec

        # 4. Autocorrelation & Peak Period
        _, autocorr_peak, dominant_lag = self.compute_autocorrelation(sample_luma)
        freq_autocorr = (effective_fps / dominant_lag) if dominant_lag > 0 else 0.0

        # Tolerance for discrete sampling / float precision (e.g. 5.99999Hz at 60fps)
        f_tol = 0.15
        min_f = self.min_frequency_hz - f_tol
        max_f = self.max_frequency_hz + f_tol

        # Choose best frequency estimate and evaluate bounds
        if freq_zero_crossings > (self.max_frequency_hz + 1.0):
            estimated_freq = freq_zero_crossings
            freq_ok = False
        elif min_f <= freq_autocorr <= max_f and autocorr_peak >= self.min_autocorrelation_peak:
            # Strong in-band autocorrelation peak: prioritize autocorrelation when zero-crossing is near or underestimated
            if self.min_frequency_hz <= freq_zero_crossings <= self.max_frequency_hz:
                if abs(freq_autocorr - freq_zero_crossings) < 3.0:
                    estimated_freq = freq_autocorr
                else:
                    estimated_freq = freq_zero_crossings
            else:
                # freq_zero_crossings was underestimated due to square-wave plateaus (e.g. 5.14Hz for 6.0Hz strobe)
                estimated_freq = freq_autocorr
            freq_ok = True
        elif self.min_frequency_hz <= freq_zero_crossings <= self.max_frequency_hz:
            estimated_freq = freq_zero_crossings
            freq_ok = True
        else:
            estimated_freq = freq_zero_crossings if freq_zero_crossings > 0 else freq_autocorr
            freq_ok = min_f <= estimated_freq <= max_f

        # 5. Strobe Criteria Evaluation
        amplitude_ok = amplitude >= self.min_amplitude
        variance_ok = variance >= self.min_variance
        required_crossings = max(3, min(self.min_zero_crossings, len(recent_indices) // 4))
        crossings_ok = zero_crossings >= required_crossings

        pulse_detected = (
            amplitude_ok
            and variance_ok
            and freq_ok
            and (crossings_ok or autocorr_peak >= self.min_autocorrelation_peak)
        )

        is_pulse_peak = luma >= (min_luma + 0.35 * amplitude) and luma >= 60.0

        if pulse_detected:
            if is_pulse_peak or not self._strobe_active:
                self._last_pulse_timestamp_ns = timestamp_ns
            self._strobe_active = True
            self._current_frequency_hz = estimated_freq
        elif self._strobe_active:
            # Check cessation holdoff window
            if self._last_pulse_timestamp_ns > 0:
                time_since_pulse = now_sec - (self._last_pulse_timestamp_ns * 1e-9)
                if time_since_pulse <= self.cessation_holdoff_sec:
                    self._strobe_active = True
                else:
                    self._strobe_active = False
                    self._current_frequency_hz = 0.0
            else:
                self._strobe_active = False
                self._current_frequency_hz = 0.0
        else:
            self._strobe_active = False
            self._current_frequency_hz = 0.0

        result = StrobeMetrics(
            is_strobe=self._strobe_active,
            frequency_hz=self._current_frequency_hz,
            amplitude=amplitude,
            variance=variance,
            zero_crossings=zero_crossings,
            autocorrelation_peak=autocorr_peak,
            dominant_period_frames=dominant_lag,
        )
        self._last_metrics = result
        return result

    def is_strobe_train_active(self, metrics: FrameMetrics) -> bool:
        """
        Evaluates frame metrics and returns True if an active 6-25Hz strobe train
        is ongoing (or within the cessation holdoff window).
        """
        res = self.process(metrics)
        return res.is_strobe

    def get_frequency(self) -> float:
        """Returns the current strobe frequency in Hz."""
        return self._current_frequency_hz
