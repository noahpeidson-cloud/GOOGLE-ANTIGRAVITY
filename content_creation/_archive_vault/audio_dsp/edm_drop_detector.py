"""
---
Name: EDM Drop Detector & Signal Telemetry Engine
Context Mapping: Originally developed in `content_creation/audio_dsp.py` for Track 2 (EDM Short-Form Media Engineering) to detect peak energy musical drops in concert footage for automated 30s rough-cut creation.
Strengths:
  - In-memory streaming audio extraction (`ffmpeg -vn -ac 1 -ar 22050 -f s16le -` piped directly to NumPy float32) completely eliminates disk I/O bottlenecks.
  - Pure NumPy centered sliding-window RMS calculation using `np.lib.stride_tricks.as_strided` perfectly replicates Librosa centered feature extraction with zero third-party C-extension dependencies.
  - O(N) cumulative sum prefix-array argmax (`np.cumsum`) finds the global maximum energy 30-second window in <1 millisecond across hours of footage.
  - Immediate CLI manual timestamp override hierarchy bypasses extraction and DSP math when explicit human cuts are specified.
  - Graceful edge-case fallbacks for missing audio streams, silent recordings, and media shorter than target duration.
  - Self-contained synthetic EDM signal generator with sub-bass (60Hz) and harmonic (120Hz) synthesis for deterministic test execution.
Weaknesses:
  - Broad-band RMS energy measures total signal amplitude rather than frequency-isolated low-end drop transients; loud crowd noise or white noise risers can occasionally skew window selection without multiband bandpass filtering.
  - Originally tightly coupled to external `config.py` constants and fragile filesystem paths in legacy pipeline daemons.
Implementation Instructions:
  - Import `AudioDropDetector` or `detect_optimal_drop` directly from this module.
  - Pass a video path, audio path, or pre-extracted NumPy array to `detect_optimal_drop()`.
  - Check `result.start_time_sec`, `result.duration_sec`, and `result.detection_method`.
  - Use `generate_synthetic_edm_signal()` for zero-dependency testing and calibration.
---
"""

from dataclasses import dataclass
import io
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
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

logger = logging.getLogger("edm_drop_detector")

# Default DSP parameters
DEFAULT_SAMPLE_RATE: int = 22050
DEFAULT_HOP_LENGTH: int = 512
DEFAULT_FRAME_LENGTH: int = 2048
DEFAULT_TARGET_DURATION_SEC: float = 30.0
VIDEO_DURATION_MAX_SECONDS: float = 59.0
SILENCE_RMS_THRESHOLD: float = 1e-4


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time_sec": self.start_time_sec,
            "duration_sec": self.duration_sec,
            "end_time_sec": self.end_time_sec,
            "max_rms_energy": self.max_rms_energy,
            "is_manual_override": self.is_manual_override,
            "detection_method": self.detection_method,
        }


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
# UTILITY HELPERS
# ============================================================================

def find_binary(
    binary_name: str,
    custom_path: Optional[Union[str, Path]] = None,
    env_var: Optional[str] = None,
) -> Optional[Path]:
    """
    Locates an executable binary across custom paths, environment variables,
    system PATH, and standard Windows install locations.
    """
    if custom_path:
        cp = Path(custom_path)
        if cp.is_file() and os.access(cp, os.X_OK):
            return cp

    if env_var and os.environ.get(env_var):
        ep = Path(os.environ[env_var])
        if ep.is_file() and os.access(ep, os.X_OK):
            return ep

    which_path = shutil.which(binary_name)
    if which_path:
        return Path(which_path)

    # Standard Windows search candidates
    if sys.platform == "win32":
        candidates = [
            Path(r"C:\ffmpeg\bin") / f"{binary_name}.exe",
            Path(r"C:\Program Files\ffmpeg\bin") / f"{binary_name}.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / f"{binary_name}.exe",
        ]
        for c in candidates:
            if c.is_file() and os.access(c, os.X_OK):
                return c

    return None


# ============================================================================
# SYNTHETIC AUDIO GENERATOR (FOR TESTS & CALIBRATION)
# ============================================================================

def generate_synthetic_edm_signal(
    total_duration_sec: float = 90.0,
    drop_start_sec: float = 30.0,
    drop_duration_sec: float = 30.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
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
    Supports pure NumPy strided-window RMS calculation and immediate CLI override bypass.
    """

    def __init__(
        self,
        target_duration_sec: float = DEFAULT_TARGET_DURATION_SEC,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        hop_length: int = DEFAULT_HOP_LENGTH,
        frame_length: int = DEFAULT_FRAME_LENGTH,
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
        Pipes raw PCM s16le stream directly from FFmpeg stdout to NumPy array in memory,
        with native WAV parsing fallback.
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
        Computes frame RMS energy curve using Librosa (if available) or
        vectorized zero-dependency pure NumPy fallback via np.lib.stride_tricks.as_strided.
        Returns tuple of (rms_array, detection_method_name).
        """
        if len(y) == 0:
            return np.array([], dtype=np.float32), "numpy_fallback"

        # Engine 1: Librosa (when available)
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

        # Edge Case 3: Silent Audio (max RMS < SILENCE_RMS_THRESHOLD)
        if max_energy < SILENCE_RMS_THRESHOLD:
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


# ============================================================================
# CONVENIENCE FUNCTIONAL INTERFACE
# ============================================================================

def detect_optimal_drop(
    media_path: Union[str, Path, np.ndarray],
    manual_start_time: Optional[float] = None,
    manual_duration: Optional[float] = None,
    target_duration_sec: float = DEFAULT_TARGET_DURATION_SEC,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    hop_length: int = DEFAULT_HOP_LENGTH,
    frame_length: int = DEFAULT_FRAME_LENGTH,
    custom_ffmpeg_path: Optional[str] = None,
) -> DropWindowResult:
    """Convenience functional wrapper around AudioDropDetector.detect_optimal_drop."""
    detector = AudioDropDetector(
        target_duration_sec=target_duration_sec,
        sample_rate=sample_rate,
        hop_length=hop_length,
        frame_length=frame_length,
        custom_ffmpeg_path=custom_ffmpeg_path,
    )
    return detector.detect_optimal_drop(
        media_path=media_path,
        manual_start_time=manual_start_time,
        manual_duration=manual_duration,
    )


# ============================================================================
# CLI ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EDM Drop Detector & Audio Signal Telemetry")
    parser.add_argument("media_file", nargs="?", default=None, help="Path to video or audio container file")
    parser.add_argument("--target-duration", type=float, default=30.0, help="Target drop cut duration in seconds (default: 30.0)")
    parser.add_argument("--manual-start", type=float, default=None, help="Manual start timestamp override in seconds")
    parser.add_argument("--manual-duration", type=float, default=None, help="Manual duration override in seconds")
    parser.add_argument("--test-synthetic", action="store_true", help="Run automated self-test against synthetic EDM signal")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    if args.test_synthetic:
        print("[TEST] Generating 90s synthetic EDM signal with drop at 30.0s...")
        sig = generate_synthetic_edm_signal(total_duration_sec=90.0, drop_start_sec=30.0, drop_duration_sec=30.0)
        detector = AudioDropDetector(target_duration_sec=30.0)
        res = detector.detect_optimal_drop(sig)
        print(f"[TEST] Result: start={res.start_time_sec}s, dur={res.duration_sec}s, method={res.detection_method}, peak_rms={res.max_rms_energy}")
        diff = abs(res.start_time_sec - 30.0)
        if diff < 1.0:
            print(f"[PASS] Synthetic drop localized within {diff:.3f}s of ground truth!")
            sys.exit(0)
        else:
            print(f"[FAIL] Localization error {diff:.3f}s exceeds tolerance!")
            sys.exit(1)

    if not args.media_file:
        parser.print_help()
        sys.exit(1)

    res = detect_optimal_drop(
        args.media_file,
        manual_start_time=args.manual_start,
        manual_duration=args.manual_duration,
        target_duration_sec=args.target_duration,
    )

    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
    else:
        print(f"Drop Window: {res.start_time_sec:.3f}s -> {res.end_time_sec:.3f}s ({res.duration_sec:.3f}s)")
        print(f"Peak RMS Energy: {res.max_rms_energy:.6f}")
        print(f"Detection Method: {res.detection_method}")
        print(f"Manual Override: {res.is_manual_override}")
