"""
audio_dsp.py - Audio Signal Telemetry, Librosa RMS Energy & Intelligent Drop Detection
Part of Track 2: Content Creation Pipeline (EDM Short-Form Media Engineering)

Provides:
1. Memory-efficient in-memory audio extraction via FFmpeg streaming pipe or native WAV/soundfile decoders.
2. Dual-Engine RMS Energy calculation:
   - Primary: Librosa RMS feature extraction (`librosa.feature.rms`) when librosa is installed.
   - Fallback: Vectorized zero-dependency pure NumPy frame sliding window calculation.
3. O(N) Cumulative Sum sliding window argmax optimization to locate peak 30s drop energy.
4. Immediate CLI manual timestamp override bypass hierarchy.
5. Resilient edge case handling (short audio, silent audio, missing audio stream, corrupted media).
"""

from dataclasses import dataclass
import io
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional, Tuple, Union
import wave

import numpy as np

# Optional Librosa import with graceful fallback flag
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    librosa = None
    HAS_LIBROSA = False

# Optional soundfile import
try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    sf = None
    HAS_SOUNDFILE = False

from config import (
    DROP_DETECTION_RMS_THRESHOLD,
    FAST_TRACK_BUILDUP_SECONDS,
    VIDEO_DURATION_MAX_SECONDS,
)
from ingest_assets import find_binary

logger = logging.getLogger("audio_dsp")


# ============================================================================
# DATA STRUCTURES & SCHEMAS
# ============================================================================

@dataclass(frozen=True)
class DropWindowResult:
    """Standardized output schema for audio drop detection analysis."""
    start_time_sec: float
    duration_sec: float
    end_time_sec: float
    max_rms_energy: float
    is_manual_override: bool
    detection_method: str  # 'librosa', 'numpy_fallback', 'manual_cli_override', 'short_audio_fallback', 'silent_audio_fallback', 'no_audio_stream'


# Alias for backward-compatibility with Survey specifications
DropAnalysisResult = DropWindowResult


# ============================================================================
# EXCEPTIONS
# ============================================================================

class AudioDSPError(Exception):
    """Base exception for Audio DSP operations."""
    pass


class AudioExtractionError(AudioDSPError):
    """Raised when audio cannot be extracted from a media container."""
    pass


# ============================================================================
# SYNTHETIC AUDIO GENERATOR (FOR TESTS & CALIBRATION)
# ============================================================================

def generate_synthetic_edm_signal(
    total_duration_sec: float = 90.0,
    drop_start_sec: float = 30.0,
    drop_duration_sec: float = 30.0,
    sample_rate: int = 22050,
    quiet_amplitude: float = 0.05,
    drop_amplitude: float = 0.90,
) -> np.ndarray:
    """
    Generates a synthetic EDM audio signal with:
    - 0 to drop_start: Low energy intro/build (quiet_amplitude)
    - drop_start to drop_start+drop_duration: High energy drop with sub-bass + harmonics (drop_amplitude)
    - drop_start+drop_duration to end: Low energy outro (quiet_amplitude)
    """
    total_samples = int(total_duration_sec * sample_rate)
    t = np.linspace(0, total_duration_sec, total_samples, endpoint=False)
    y = np.zeros(total_samples, dtype=np.float32)

    # Intro
    intro_mask = t < drop_start_sec
    if np.any(intro_mask):
        y[intro_mask] = (quiet_amplitude * np.sin(2 * np.pi * 440.0 * t[intro_mask])).astype(np.float32)

    # Drop (Layered 60Hz sub-bass and 120Hz harmonics)
    drop_mask = (t >= drop_start_sec) & (t < (drop_start_sec + drop_duration_sec))
    if np.any(drop_mask):
        t_drop = t[drop_mask]
        drop_wave = (
            (drop_amplitude * 0.70) * np.sin(2 * np.pi * 60.0 * t_drop) +
            (drop_amplitude * 0.30) * np.sin(2 * np.pi * 120.0 * t_drop)
        )
        y[drop_mask] = drop_wave.astype(np.float32)

    # Outro
    outro_mask = t >= (drop_start_sec + drop_duration_sec)
    if np.any(outro_mask):
        y[outro_mask] = (quiet_amplitude * np.sin(2 * np.pi * 440.0 * t[outro_mask])).astype(np.float32)

    return y


# ============================================================================
# AUDIO DROP DETECTOR CLASS
# ============================================================================

class AudioDropDetector:
    """
    Analyzes audio energy contours and identifies the optimal high-energy drop window.
    Supports dual-engine RMS calculation (Librosa & pure NumPy) and immediate CLI override bypass.
    """

    def __init__(
        self,
        target_duration_sec: float = 30.0,
        sample_rate: int = 22050,
        hop_length: int = 512,
        frame_length: int = 2048,
        custom_ffmpeg_path: Optional[str] = None,
    ):
        self.target_duration_sec = float(target_duration_sec)
        self.sample_rate = int(sample_rate)
        self.hop_length = int(hop_length)
        self.frame_length = int(frame_length)
        self.custom_ffmpeg_path = custom_ffmpeg_path
        self._ffmpeg_bin: Optional[Path] = find_binary(
            "ffmpeg", custom_path=custom_ffmpeg_path, env_var="FFMPEG_BINARY"
        )

    def extract_audio_buffer(self, video_or_audio_path: Union[str, Path]) -> np.ndarray:
        """
        Extracts mono float32 PCM audio buffer from media container or audio file.
        Uses in-memory streaming pipe with FFmpeg, or native fallback for WAV/soundfile.
        """
        path_obj = Path(video_or_audio_path).resolve()
        if not path_obj.is_file():
            raise FileNotFoundError(f"Media file not found: {path_obj}")

        # Attempt 1: Native WAV parsing via Python's built-in wave module (fastest, zero subprocess overhead)
        if path_obj.suffix.lower() == ".wav":
            try:
                with wave.open(str(path_obj), "rb") as wf:
                    nchannels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    framerate = wf.getframerate()
                    nframes = wf.getnframes()
                    raw_bytes = wf.readframes(nframes)

                    if sampwidth == 2:
                        pcm = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    elif sampwidth == 1:
                        pcm = (np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                    elif sampwidth == 4:
                        pcm = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
                    else:
                        pcm = None

                    if pcm is not None:
                        if nchannels > 1:
                            pcm = pcm.reshape(-1, nchannels).mean(axis=1)
                        # Linear resample if needed
                        if framerate != self.sample_rate and len(pcm) > 0:
                            target_samples = int(len(pcm) * self.sample_rate / framerate)
                            x_orig = np.linspace(0, 1, len(pcm))
                            x_target = np.linspace(0, 1, target_samples)
                            pcm = np.interp(x_target, x_orig, pcm).astype(np.float32)
                        return pcm.astype(np.float32)
            except Exception as e:
                logger.debug(f"Native wave parsing skipped or failed: {e}")

        # Attempt 2: FFmpeg in-memory streaming pipe
        ffmpeg_bin = self._ffmpeg_bin or find_binary(
            "ffmpeg", custom_path=self.custom_ffmpeg_path, env_var="FFMPEG_BINARY"
        )
        if ffmpeg_bin:
            cmd = [
                str(ffmpeg_bin),
                "-v", "error",
                "-i", str(path_obj),
                "-vn",
                "-ac", "1",
                "-ar", str(self.sample_rate),
                "-f", "s16le",
                "-",
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if proc.returncode != 0:
                    err_msg = proc.stderr.decode("utf-8", errors="ignore").strip()
                    raise AudioExtractionError(
                        f"FFmpeg extraction failed for '{path_obj}': {err_msg}"
                    )

                if len(proc.stdout) == 0:
                    # Video has no audio stream or empty stream
                    return np.array([], dtype=np.float32)

                pcm_data = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
                return pcm_data
            except subprocess.SubprocessError as exc:
                raise AudioExtractionError(f"Subprocess execution error during audio extraction: {exc}")

        # Attempt 3: soundfile fallback if installed
        if HAS_SOUNDFILE and sf is not None:
            try:
                data, sr = sf.read(str(path_obj), always_2d=False)
                if data.ndim > 1:
                    data = data.mean(axis=1)
                if sr != self.sample_rate and len(data) > 0:
                    target_samples = int(len(data) * self.sample_rate / sr)
                    x_orig = np.linspace(0, 1, len(data))
                    x_target = np.linspace(0, 1, target_samples)
                    data = np.interp(x_target, x_orig, data)
                return data.astype(np.float32)
            except Exception as sf_err:
                raise AudioExtractionError(
                    f"soundfile reading failed for '{path_obj}': {sf_err}"
                )

        raise AudioExtractionError(
            f"Could not extract audio from '{path_obj}'. FFmpeg binary not found on PATH or environment, "
            f"and format is not decodable natively."
        )

    def calculate_rms_energy(self, y: np.ndarray) -> Tuple[np.ndarray, str]:
        """
        Computes frame RMS energy curve using Librosa (if available) or vectorized pure NumPy fallback.
        Returns tuple of (rms_array, detection_method_name).
        """
        if len(y) == 0:
            return np.array([], dtype=np.float32), "numpy_fallback"

        # Engine 1: Librosa (when imported)
        if HAS_LIBROSA and librosa is not None:
            try:
                rms_2d = librosa.feature.rms(
                    y=y,
                    frame_length=self.frame_length,
                    hop_length=self.hop_length,
                    center=True,
                    pad_mode="constant",
                )
                return rms_2d[0].astype(np.float32), "librosa"
            except Exception as e:
                logger.warning(f"Librosa RMS feature extraction failed: {e}. Using NumPy fallback.")

        # Engine 2: Pure NumPy Vectorized Fallback (Centered framing matching Librosa specification)
        pad_len = self.frame_length // 2
        padded = np.pad(y, (pad_len, pad_len), mode="constant")
        if len(padded) < self.frame_length:
            padded = np.pad(padded, (0, self.frame_length - len(padded)), mode="constant")

        n_frames = max(1, (len(padded) - self.frame_length) // self.hop_length + 1)
        shape = (n_frames, self.frame_length)
        strides = (padded.strides[0] * self.hop_length, padded.strides[0])
        frames = np.lib.stride_tricks.as_strided(padded, shape=shape, strides=strides)

        rms = np.sqrt(np.mean(frames**2, axis=1)).astype(np.float32)
        return rms, "numpy_fallback"

    # Backward-compatible alias
    compute_rms_envelope = calculate_rms_energy

    def detect_optimal_drop(
        self,
        media_path: Union[str, Path, np.ndarray],
        manual_start_time: Optional[float] = None,
        manual_duration: Optional[float] = None,
    ) -> DropWindowResult:
        """
        Calculates the optimal target-duration window with peak RMS energy ("the drop").
        
        Precedence Hierarchy:
        1. Manual Override: If manual_start_time is specified, IMMEDIATELY returns manual DropWindowResult,
           bypassing audio extraction, file I/O, and DSP calculations entirely.
        2. Automated DSP: Extracts audio, calculates RMS curve, and computes optimal sliding window via O(N) cumsum.
        3. Safe Edge Case Fallbacks:
           - Missing audio stream -> [0.0, target_duration], method='no_audio_stream'
           - Short audio (< target_duration) -> [0.0, total_duration], method='short_audio_fallback'
           - Silent audio (max RMS < 1e-4) -> [0.0, target_duration], method='silent_audio_fallback'
        """
        # ====================================================================
        # LEVEL 1: IMMEDIATE MANUAL CLI OVERRIDE BYPASS
        # ====================================================================
        if manual_start_time is not None:
            dur = manual_duration if manual_duration is not None else self.target_duration_sec
            dur = min(float(dur), float(VIDEO_DURATION_MAX_SECONDS))
            start_t = float(manual_start_time)
            end_t = start_t + dur
            return DropWindowResult(
                start_time_sec=round(start_t, 3),
                duration_sec=round(dur, 3),
                end_time_sec=round(end_t, 3),
                max_rms_energy=1.0,
                is_manual_override=True,
                detection_method="manual_cli_override",
            )

        # ====================================================================
        # LEVEL 2: AUDIO BUFFER ACQUISITION
        # ====================================================================
        if isinstance(media_path, np.ndarray):
            y = media_path.astype(np.float32)
        else:
            y = self.extract_audio_buffer(str(media_path))

        # Edge Case 1: Missing Audio Stream / Empty Audio Buffer
        if len(y) == 0:
            logger.warning("No audio stream or empty audio buffer detected. Returning default window.")
            return DropWindowResult(
                start_time_sec=0.0,
                duration_sec=float(self.target_duration_sec),
                end_time_sec=float(self.target_duration_sec),
                max_rms_energy=0.0,
                is_manual_override=False,
                detection_method="no_audio_stream",
            )

        total_duration_sec = len(y) / self.sample_rate

        # Edge Case 2: Short Audio (< target_duration_sec)
        if total_duration_sec < self.target_duration_sec:
            rms_curve, method = self.calculate_rms_energy(y)
            max_energy = float(np.max(rms_curve)) if len(rms_curve) > 0 else 0.0
            return DropWindowResult(
                start_time_sec=0.0,
                duration_sec=round(float(total_duration_sec), 3),
                end_time_sec=round(float(total_duration_sec), 3),
                max_rms_energy=round(max_energy, 6),
                is_manual_override=False,
                detection_method="short_audio_fallback",
            )

        # Calculate RMS energy curve
        rms_curve, method = self.calculate_rms_energy(y)
        max_energy = float(np.max(rms_curve)) if len(rms_curve) > 0 else 0.0

        # Edge Case 3: Silent Audio (max RMS < 1e-4)
        if max_energy < 1e-4:
            logger.warning("Silent audio detected (RMS < 1e-4). Returning default start offset 0.0s.")
            return DropWindowResult(
                start_time_sec=0.0,
                duration_sec=float(self.target_duration_sec),
                end_time_sec=float(self.target_duration_sec),
                max_rms_energy=round(max_energy, 6),
                is_manual_override=False,
                detection_method="silent_audio_fallback",
            )

        # ====================================================================
        # LEVEL 3: O(N) SLIDING WINDOW ENERGY MAXIMIZATION
        # ====================================================================
        win_frames = int(self.target_duration_sec * self.sample_rate / self.hop_length)
        if win_frames >= len(rms_curve):
            return DropWindowResult(
                start_time_sec=0.0,
                duration_sec=float(self.target_duration_sec),
                end_time_sec=float(self.target_duration_sec),
                max_rms_energy=round(max_energy, 6),
                is_manual_override=False,
                detection_method=method,
            )

        cumsum = np.pad(np.cumsum(rms_curve), (1, 0))
        window_sums = cumsum[win_frames:] - cumsum[:-win_frames]
        best_frame = int(np.argmax(window_sums))

        raw_start_sec = float(best_frame * self.hop_length / self.sample_rate)
        # Clamped to safe range
        max_valid_start = max(0.0, total_duration_sec - self.target_duration_sec)
        final_start_sec = max(0.0, min(raw_start_sec, max_valid_start))
        final_end_sec = final_start_sec + self.target_duration_sec

        # Peak energy within detected window
        window_slice = rms_curve[best_frame : best_frame + win_frames]
        window_peak_energy = float(np.max(window_slice)) if len(window_slice) > 0 else max_energy

        return DropWindowResult(
            start_time_sec=round(final_start_sec, 3),
            duration_sec=round(float(self.target_duration_sec), 3),
            end_time_sec=round(final_end_sec, 3),
            max_rms_energy=round(window_peak_energy, 6),
            is_manual_override=False,
            detection_method=method,
        )

    # Convenience alias
    detect_drop = detect_optimal_drop


# ============================================================================
# CONVENIENCE FUNCTIONAL INTERFACE
# ============================================================================

def detect_optimal_drop(
    media_path: Union[str, Path, np.ndarray],
    manual_start_time: Optional[float] = None,
    manual_duration: Optional[float] = None,
    target_duration_sec: float = 30.0,
    sample_rate: int = 22050,
    hop_length: int = 512,
    custom_ffmpeg_path: Optional[str] = None,
) -> DropWindowResult:
    """Convenience functional wrapper around AudioDropDetector.detect_optimal_drop."""
    detector = AudioDropDetector(
        target_duration_sec=target_duration_sec,
        sample_rate=sample_rate,
        hop_length=hop_length,
        custom_ffmpeg_path=custom_ffmpeg_path,
    )
    return detector.detect_optimal_drop(
        media_path=media_path,
        manual_start_time=manual_start_time,
        manual_duration=manual_duration,
    )


def run_auto_drop_detection(
    audio_wav_path: Union[str, Path, np.ndarray],
    target_duration_sec: float = 30.0,
    manual_start_time: Optional[float] = None,
    manual_duration: Optional[float] = None,
    sample_rate: int = 22050,
    hop_length: int = 512,
    custom_ffmpeg_path: Optional[str] = None,
) -> DropWindowResult:
    """
    Analyzes an uncompressed / extracted .wav audio file (or audio array) directly.
    Bypasses video container parsing and executes native WAV / Librosa / NumPy RMS drop detection.
    """
    return detect_optimal_drop(
        media_path=audio_wav_path,
        manual_start_time=manual_start_time,
        manual_duration=manual_duration,
        target_duration_sec=target_duration_sec,
        sample_rate=sample_rate,
        hop_length=hop_length,
        custom_ffmpeg_path=custom_ffmpeg_path,
    )

