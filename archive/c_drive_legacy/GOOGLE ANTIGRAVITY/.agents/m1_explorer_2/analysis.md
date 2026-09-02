# Technical Analysis & Blueprint: Audio Peak DSP & 3-Cut Generation

**Author**: M1 Explorer 2 (Audio Peak & 3-Cut DSP Specialist)  
**Target Module**: `unified_ops_hub/ml_agent/editor.py`  
**Related Requirements**: R1 (ORIGINAL_REQUEST.md §1), `PROJECT.md` §1-§2  
**Date**: 2026-08-25T22:08:50-07:00  

---

## 1. Executive Summary & Architectural Overview

The Media Studio requires an autonomous backend video analysis pipeline that processes raw video assets, generates lightweight 720p H.264 proxy files for browser rendering, and calculates 3 distinct editing cuts (`hype_drop`, `cinematic`, and `raw_pov`) formatted according to a deterministic JSON schema.

This analysis provides the complete mathematical, algorithmic, and software blueprint for the **Audio Peak DSP Engine** and **3-Cut Metadata Generator** to be implemented in `unified_ops_hub/ml_agent/editor.py` (`MediaEditor`).

### Architectural Pipeline
```
[Raw Video Source]
        │
        ├── 1. FFmpeg Metadata Probe (Duration, Dimensions, Audio Presence)
        │
        ├── 2. FFmpeg Video Scale -> 720p Faststart MP4 Proxy (to `proxies/`)
        │
        └── 3. FFmpeg Audio Pipe -> In-Memory PCM Stream (s16le, 22.05 kHz, mono)
                     │
                     ▼
             [NumPy DSP Vectorizer]
                     │
                     ├── Frame into 50ms RMS Energy Chunks
                     ├── Vectorized Cumulative Sum Sliding Window (15.0s)
                     └── Argmax Peak Timestamp Locator -> [in_point, out_point]
                     │
                     ▼
             [3-Cut Metadata Compiler]
                     ├── hype_drop: [in_point, out_point], 9:16 crop, 1080x1920
                     ├── cinematic: [0.0, duration], 16:9 crop, 1920x1080
                     └── raw_pov:   [0.0, duration], original AR, original res
```

---

## 2. In-Memory PCM Streaming via FFmpeg Pipe

### FFmpeg Command Specification
Audio extraction is performed entirely in RAM using a standard OS pipe to eliminate temporary disk I/O, file descriptor leaks, and multi-tenant disk collisions:

```bash
ffmpeg -v error -i "<input_file>" -vn -ac 1 -ar 22050 -f s16le -
```

### Parameter Breakdown
| Parameter | Purpose | Rationale |
|---|---|---|
| `-v error` | Log verbosity | Suppresses informational banners/headers; outputs only errors to `stderr`. |
| `-i "<input_file>"` | Input video | Supports arbitrary media containers (`.mp4`, `.mov`, `.mkv`, `.avi`, `.m4v`). |
| `-vn` | Disable video stream | Prevents video decoding overhead; streams audio exclusively. |
| `-ac 1` | Downmix to mono | Combines multi-channel stereo/surround into a single scalar waveform. |
| `-ar 22050` | Resample to 22.05 kHz | Nyquist limit 11.025 kHz captures all human speech, music drops, and transient energy while reducing buffer size by 50% compared to 44.1 kHz. |
| `-f s16le` | Raw PCM format | Signed 16-bit little-endian integer PCM, 2 bytes per sample. |
| `-` | Stdout stream destination | Emits raw byte stream directly to standard output pipe. |

### Subprocess Pipe Execution Mechanics
```python
def extract_pcm_audio(self, source_file: str, sample_rate: int = 22050) -> bytes:
    """Extracts raw mono s16le PCM audio directly into memory via FFmpeg stdout pipe.
    
    Returns:
        bytes: Raw signed 16-bit PCM buffer, or b"" if no audio track exists.
    """
    if not os.path.exists(source_file):
        raise FileNotFoundError(f"Source media file not found: {source_file}")
        
    cmd = [
        self.ffmpeg_bin,
        "-v", "error",
        "-i", source_file,
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "s16le",
        "-",
    ]
    
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    
    # Return empty buffer if no audio stream exists or decoding failed
    if result.returncode != 0 or len(result.stdout) == 0:
        return b""
        
    return result.stdout
```

---

## 3. Vectorized NumPy Audio DSP & Peak Window Detection

### 3.1 Unpacking & Framing
Given sample rate $f_s = 22050 \text{ Hz}$ and frame length $\Delta t = 50\text{ ms} = 0.050\text{ s}$:
- Samples per frame $N_f = \lfloor f_s \cdot \Delta t \rfloor = \lfloor 22050 \cdot 0.050 \rfloor = 1102$ samples.
- Total samples $N = \frac{\text{len}(\text{raw\_pcm})}{2}$.
- Frame count $M = \lfloor N / N_f \rfloor$.

Vectorized decoding:
```python
samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
trimmed_samples = samples[:M * N_f]
framed = trimmed_samples.reshape((M, N_f))
```

### 3.2 RMS Energy Calculation
For each frame $m \in [0, M-1]$:
$$\text{RMS}[m] = \sqrt{ \frac{1}{N_f} \sum_{i=0}^{N_f - 1} \text{framed}[m, i]^2 + \epsilon }$$
Vectorized in NumPy:
```python
frame_rms = np.sqrt(np.mean(framed ** 2, axis=1) + 1e-9)
```

### 3.3 Fast $O(N)$ Moving Window Sum via Cumulative Sums
To find the continuous window of duration $W = 15.0\text{ s}$ with the highest cumulative energy:
- Window length in frames: $k = \max(1, \text{round}(W / \Delta t)) = 300\text{ frames}$.
- Cumulative sum array: $C[0] = 0, \quad C[j] = \sum_{i=0}^{j-1} \text{RMS}[i]$.
- Window sum for starting frame $j$: $S[j] = C[j + k] - C[j]$.
- Optimal frame index: $j^* = \arg\max_{j} S[j]$.

Vectorized implementation:
```python
cumsum = np.cumsum(np.insert(frame_rms, 0, 0.0))
window_sums = cumsum[k:] - cumsum[:-k]
best_idx = int(np.argmax(window_sums))

in_point = round(best_idx * (N_f / sample_rate), 2)
out_point = round(in_point + effective_window_duration, 2)
```

---

## 4. Edge Case Fallback Matrix & Clamping Policies

| Edge Case Scenario | Condition | Behavior / Clamping Rule | Output `(in_point, out_point)` |
|---|---|---|---|
| **No Audio Track** | Video file has zero audio streams (`len(raw_pcm) == 0` or FFmpeg exit != 0) | Graceful fallback without exception. Window defaults to start of clip. | `(0.0, min(15.0, total_duration))` |
| **Total Silence** | Audio track exists but all samples $\approx 0$ (`np.max(np.abs(samples)) < 1e-3`) | Graceful fallback. Avoids NaN or arbitrary argmax behavior. | `(0.0, min(15.0, total_duration))` |
| **Short Clip (< 15s)** | Total duration $T < 15.0\text{ s}$ (e.g. $T = 4.5\text{ s}$) | Window size clamped to total clip duration: $W_{\text{eff}} = \min(15.0, T)$. | `(0.0, round(total_duration, 2))` |
| **Boundary Clamping** | Peak window exceeds end of clip ($in\_point + 15.0 > T$) | Clamp $out\_point = T$, adjust $in\_point = \max(0.0, T - 15.0)$. | `(max(0.0, T - 15.0), T)` |
| **Sub-50ms / Micro Video** | Total frames $M == 0$ | Direct fallback to full duration. | `(0.0, round(total_duration, 2))` |
| **Missing Source File** | `not os.path.exists(source_file)` | Loud assertion failure: raise standard exception. | `raises FileNotFoundError` |

---

## 5. 3-Cut Metadata JSON Schema Generation

The output schema must strictly adhere to the contract defined in `PROJECT.md § Interface Contracts`:

```json
{
  "source_file": "data/sample_video.mp4",
  "proxy_file": "proxies/sample_video_proxy.mp4",
  "duration": 30.0,
  "cuts": {
    "hype_drop": {
      "in_point": 12.65,
      "out_point": 27.65,
      "crop_ratio": "9:16",
      "label": "Hype Drop (Audio Peak)",
      "target_resolution": "1080x1920"
    },
    "cinematic": {
      "in_point": 0.0,
      "out_point": 30.0,
      "crop_ratio": "16:9",
      "label": "Cinematic (16:9)",
      "target_resolution": "1920x1080"
    },
    "raw_pov": {
      "in_point": 0.0,
      "out_point": 30.0,
      "crop_ratio": "original",
      "label": "Raw POV (Original)",
      "target_resolution": "original"
    }
  }
}
```

### Field Definitions
- `source_file` (`str`): File path of the ingested raw video.
- `proxy_file` (`str`): Relative or absolute path of the generated 720p faststart proxy MP4.
- `duration` (`float`): Total duration of source video rounded to 2 decimal places.
- `cuts.hype_drop`:
  - `in_point`: Sub-second timestamp marking the start of the loudest 15s audio peak.
  - `out_point`: Sub-second timestamp marking the end of the peak window ($in\_point + 15.0$).
  - `crop_ratio`: `"9:16"` (vertical short-form video crop).
  - `label`: `"Hype Drop (Audio Peak)"`.
  - `target_resolution`: `"1080x1920"`.
- `cuts.cinematic`:
  - `in_point`: `0.0`.
  - `out_point`: `round(duration, 2)`.
  - `crop_ratio`: `"16:9"` (horizontal widescreen crop).
  - `label`: `"Cinematic (16:9)"`.
  - `target_resolution`: `"1920x1080"`.
- `cuts.raw_pov`:
  - `in_point`: `0.0`.
  - `out_point`: `round(duration, 2)`.
  - `crop_ratio`: `"original"` (preserves native aspect ratio).
  - `label`: `"Raw POV (Original)"`.
  - `target_resolution`: `"original"`.

---

## 6. Complete Implementation Blueprint for `ml_agent/editor.py`

Below is the exact, complete implementation blueprint for `unified_ops_hub/ml_agent/editor.py`:

```python
"""Antigravity Media Studio - AI Proxy & Cut Generator.
Provides FFmpeg 720p proxy downscaling, in-memory PCM audio DSP peak detection,
and 3-cut metadata compilation (hype_drop, cinematic, raw_pov).
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

import numpy as np


class MediaEditor:
    """Automated media processor for proxy transcoding and audio peak cut generation."""

    def __init__(self, ffmpeg_bin: Optional[str] = None):
        """Initializes MediaEditor with resolved FFmpeg binary path."""
        self.ffmpeg_bin = self._resolve_ffmpeg(ffmpeg_bin)

    @staticmethod
    def _resolve_ffmpeg(custom_bin: Optional[str] = None) -> str:
        """Resolves FFmpeg executable path across environment, PATH, and imageio-ffmpeg."""
        if custom_bin and os.path.isfile(custom_bin):
            return custom_bin

        env_bin = os.environ.get("FFMPEG_BINARY") or os.environ.get("FFMPEG_PATH")
        if env_bin and os.path.isfile(env_bin):
            return env_bin

        which_bin = shutil.which("ffmpeg")
        if which_bin:
            return which_bin

        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, Exception):
            pass

        return "ffmpeg"

    def probe_media(self, source_file: str) -> Dict[str, Any]:
        """Extracts media metadata (duration, resolution, audio presence) using FFmpeg probe.
        
        Args:
            source_file: Path to video file.
            
        Returns:
            Dict containing 'duration' (float), 'width' (int), 'height' (int), 'has_audio' (bool).
        """
        if not os.path.exists(source_file):
            raise FileNotFoundError(f"Source media file does not exist: {source_file}")

        cmd = [self.ffmpeg_bin, "-i", source_file]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        stderr = result.stderr

        # Extract duration
        duration = 0.0
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
        if dur_match:
            hours, minutes, seconds = dur_match.groups()
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

        # Extract resolution
        width, height = 1920, 1080
        res_match = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", stderr)
        if res_match:
            width, height = map(int, res_match.groups())

        # Check audio presence
        has_audio = bool(re.search(r"Stream #.*?: Audio:", stderr))

        return {
            "duration": round(duration, 2),
            "width": width,
            "height": height,
            "has_audio": has_audio,
        }

    def extract_pcm_audio(self, source_file: str, sample_rate: int = 22050) -> bytes:
        """Streams audio track directly into memory as mono s16le PCM via FFmpeg pipe.
        
        Args:
            source_file: Path to video file.
            sample_rate: Audio sampling rate in Hz (default: 22050).
            
        Returns:
            bytes: In-memory raw PCM buffer, or b"" if no audio stream.
        """
        if not os.path.exists(source_file):
            raise FileNotFoundError(f"Source media file does not exist: {source_file}")

        cmd = [
            self.ffmpeg_bin,
            "-v", "error",
            "-i", source_file,
            "-vn",
            "-ac", "1",
            "-ar", str(sample_rate),
            "-f", "s16le",
            "-",
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        if result.returncode != 0 or len(result.stdout) == 0:
            return b""

        return result.stdout

    def detect_audio_peak_window(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 22050,
        total_duration: float = 0.0,
        window_duration: float = 15.0,
        frame_ms: float = 50.0,
    ) -> Tuple[float, float]:
        """Locates the start and end timestamp of the highest-energy audio window.
        
        Args:
            pcm_bytes: Raw signed 16-bit mono PCM bytes.
            sample_rate: Sampling rate of PCM audio.
            total_duration: Total video duration in seconds.
            window_duration: Target duration for peak window (default: 15.0s).
            frame_ms: Duration of RMS analysis frame in milliseconds (default: 50.0ms).
            
        Returns:
            Tuple[float, float]: (in_point, out_point) in seconds.
        """
        effective_window = min(window_duration, max(0.0, total_duration))
        if not pcm_bytes or total_duration <= 0.0:
            return 0.0, round(effective_window, 2)

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        if len(samples) == 0:
            return 0.0, round(effective_window, 2)

        # Fallback for total silence
        if np.max(np.abs(samples)) < 1e-3:
            return 0.0, round(effective_window, 2)

        frame_size = int(sample_rate * (frame_ms / 1000.0))
        if frame_size <= 0:
            return 0.0, round(effective_window, 2)

        n_frames = len(samples) // frame_size
        if n_frames == 0:
            return 0.0, round(effective_window, 2)

        # Vectorized RMS per frame
        framed = samples[: n_frames * frame_size].reshape((n_frames, frame_size))
        rms = np.sqrt(np.mean(framed ** 2, axis=1) + 1e-9)

        # Window size in frames
        k = max(1, int(round(effective_window / (frame_size / sample_rate))))
        if n_frames <= k or total_duration <= window_duration:
            return 0.0, round(total_duration, 2)

        # O(N) Sliding Window Energy Sum
        cumsum = np.cumsum(np.insert(rms, 0, 0.0))
        window_sums = cumsum[k:] - cumsum[:-k]
        best_idx = int(np.argmax(window_sums))

        in_point = round(best_idx * (frame_size / sample_rate), 2)
        out_point = round(in_point + effective_window, 2)

        # Clamp to clip boundaries
        if out_point > total_duration:
            out_point = round(total_duration, 2)
            in_point = max(0.0, round(out_point - effective_window, 2))

        return in_point, out_point

    def generate_proxy(
        self,
        source_file: str,
        proxy_dir: str = "proxies",
        target_height: int = 720,
    ) -> str:
        """Transcodes source video into a lightweight 720p faststart MP4 proxy.
        
        Args:
            source_file: Path to raw source video.
            proxy_dir: Output directory for proxies.
            target_height: Vertical resolution (default: 720).
            
        Returns:
            str: Path to generated proxy file.
        """
        if not os.path.exists(source_file):
            raise FileNotFoundError(f"Source media file does not exist: {source_file}")

        os.makedirs(proxy_dir, exist_ok=True)
        stem = Path(source_file).stem
        proxy_path = os.path.join(proxy_dir, f"{stem}_proxy.mp4")

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", source_file,
            "-vf", f"scale=-2:{target_height}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            proxy_path,
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if result.returncode != 0 or not os.path.exists(proxy_path):
            raise RuntimeError(f"FFmpeg proxy generation failed: {result.stderr}")

        return proxy_path

    def generate_proxy_and_cuts(
        self,
        source_file: str,
        proxy_dir: str = "proxies",
        window_duration: float = 15.0,
    ) -> Dict[str, Any]:
        """Main entry point: Generates 720p proxy and compiles 3-cut JSON metadata.
        
        Args:
            source_file: Path to raw source video.
            proxy_dir: Output directory for proxies.
            window_duration: Duration of hype_drop audio peak cut (default: 15.0s).
            
        Returns:
            Dict matching PROJECT.md interface contract.
        """
        if not os.path.exists(source_file):
            raise FileNotFoundError(f"Source media file does not exist: {source_file}")

        metadata = self.probe_media(source_file)
        duration = metadata["duration"]

        # Generate 720p proxy
        proxy_file = self.generate_proxy(source_file, proxy_dir=proxy_dir)

        # Perform Audio DSP peak detection
        if metadata["has_audio"]:
            pcm_bytes = self.extract_pcm_audio(source_file)
            hype_in, hype_out = self.detect_audio_peak_window(
                pcm_bytes=pcm_bytes,
                total_duration=duration,
                window_duration=window_duration,
            )
        else:
            hype_in = 0.0
            hype_out = round(min(window_duration, duration), 2)

        cuts_payload = {
            "source_file": source_file,
            "proxy_file": proxy_file,
            "duration": duration,
            "cuts": {
                "hype_drop": {
                    "in_point": hype_in,
                    "out_point": hype_out,
                    "crop_ratio": "9:16",
                    "label": "Hype Drop (Audio Peak)",
                    "target_resolution": "1080x1920",
                },
                "cinematic": {
                    "in_point": 0.0,
                    "out_point": duration,
                    "crop_ratio": "16:9",
                    "label": "Cinematic (16:9)",
                    "target_resolution": "1920x1080",
                },
                "raw_pov": {
                    "in_point": 0.0,
                    "out_point": duration,
                    "crop_ratio": "original",
                    "label": "Raw POV (Original)",
                    "target_resolution": "original",
                },
            },
        }

        return cuts_payload
```

---

## 7. Module Exports and Rule Compliance

### Export in `unified_ops_hub/ml_agent/__init__.py`
Update `ml_agent/__init__.py` to export `MediaEditor`:
```python
from unified_ops_hub.ml_agent.editor import MediaEditor

__all__ = [
    ...,
    "MediaEditor",
]
```

### Rule R16 Compliance (Absolute Imports)
Any test scripts, entrypoints, and worker implementations MUST import `MediaEditor` using absolute project root package imports:
```python
from unified_ops_hub.ml_agent.editor import MediaEditor
```
No relative imports (e.g. `from .editor import MediaEditor`) are allowed in top-level test files or standalone runners.

### Rule R18 Compliance (Python Dependencies)
The Audio Peak DSP pipeline relies only on standard Python libraries (`subprocess`, `os`, `re`, `shutil`, `pathlib`) and `numpy` + `imageio-ffmpeg`, which are pre-verified on the target Python 3.13 runtime.
