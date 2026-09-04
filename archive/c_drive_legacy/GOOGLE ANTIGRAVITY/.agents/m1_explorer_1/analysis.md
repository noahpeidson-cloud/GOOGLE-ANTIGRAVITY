# Analysis & Implementation Blueprint: MediaEditor Proxy Engine

**Specialist**: M1 Explorer 1 (Proxy Engine Specialist)  
**Target Module**: `unified_ops_hub/ml_agent/editor.py` (`MediaEditor`)  
**Package Integration**: `unified_ops_hub/ml_agent/__init__.py`  
**Milestone**: M1 (AI Proxy & Cut Generator)  
**Date**: 2026-08-25  

---

## 1. Executive Summary & Scope

In the Unified Ops Hub Media Studio architecture, raw ingested video files (which may be 4K 60fps, 10-bit HDR, HEVC, or multi-gigabyte files) cannot be smoothly scrubbed, manipulated, or previewed directly inside an HTML5 web browser without significant latency and high resource consumption. 

The `MediaEditor` class in `unified_ops_hub/ml_agent/editor.py` serves as the core media preprocessing engine responsible for:
1. **Generating 720p H.264 Faststart Proxy Videos** (`.mp4`) optimized for zero-buffering browser playback and dual-handle trim slider scrubbing in `MediaStudio.tsx`.
2. **Dynamic FFmpeg Binary Discovery & Resolution** across virtual environments, OS PATHs, environment variables, and `imageio_ffmpeg`.
3. **Resilient Subprocess Execution** with loud error handling (`FileNotFoundError`, `RuntimeError`), preventing silent failures.
4. **Exporting `MediaEditor`** in `unified_ops_hub/ml_agent/__init__.py` adhering strictly to **Rule R16 (Executable Python Import Guardrail — Absolute Imports Only)**.

---

## 2. Requirements Traceability

| Requirement | Description | Implementation Mechanism |
|-------------|-------------|--------------------------|
| **R1.1 (Proxy Generation)** | Subprocess FFmpeg downscaling to 720p H.264 MP4 | `subprocess.run` calling resolved `ffmpeg` with `-vf scale=-2:720`, `-c:v libx264`, `-preset fast`, `-pix_fmt yuv420p` |
| **R1.2 (Web Optimization)** | Faststart moov atom header relocation | `-movflags +faststart` flag ensuring instant scrubbing before full download |
| **R1.3 (Binary Resolution)** | Automatic multi-tier binary resolution | Fallback chain: Explicit param $\to$ `FFMPEG_BINARY`/`FFMPEG_PATH` env vars $\to$ `imageio_ffmpeg.get_ffmpeg_exe()` $\to$ `shutil.which("ffmpeg")` $\to$ system `"ffmpeg"` |
| **R2 (Leash / Loud Assertions)** | Deterministic error handling and test verification | Explicit `FileNotFoundError` for missing source or binary; explicit `RuntimeError` with stderr on non-zero exit code or zero-byte output |
| **R16 (Absolute Imports)** | No relative imports | `from unified_ops_hub.ml_agent.editor import MediaEditor` across all entrypoints and modules |

---

## 3. FFmpeg Binary Path Resolution Engine

### 3.1 Precedence Hierarchy
To guarantee zero-friction execution across development machines, CI environments, and containerized deployments, `MediaEditor._resolve_ffmpeg()` implements a 5-tier fallback cascade:

```
[1. Constructor Argument: ffmpeg_path]
               │ (if None / unset)
               ▼
[2. Environment Variables: FFMPEG_BINARY / FFMPEG_PATH]
               │ (if unset)
               ▼
[3. imageio_ffmpeg.get_ffmpeg_exe()]
               │ (if ImportError / failure)
               ▼
[4. shutil.which("ffmpeg")]
               │ (if None)
               ▼
[5. System Fallback: "ffmpeg"]
```

### 3.2 Resolution Algorithm & Validation Logic
```python
import os
import shutil
from pathlib import Path
from typing import Optional

def resolve_ffmpeg_binary(custom_path: Optional[str] = None) -> str:
    # 1. Custom explicit path passed to constructor
    if custom_path:
        if Path(custom_path).is_file() or shutil.which(custom_path):
            return str(custom_path)
        raise FileNotFoundError(f"Specified FFmpeg executable does not exist: {custom_path}")

    # 2. Environment variables
    for env_key in ("FFMPEG_BINARY", "FFMPEG_PATH", "IMAGEIO_FFMPEG_EXE"):
        env_val = os.environ.get(env_key)
        if env_val and (Path(env_val).is_file() or shutil.which(env_val)):
            return str(env_val)

    # 3. imageio_ffmpeg dynamic detection
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return str(exe)
    except (ImportError, Exception):
        pass

    # 4. PATH lookup
    path_exe = shutil.which("ffmpeg")
    if path_exe:
        return str(path_exe)

    # 5. Default fallback or error
    raise FileNotFoundError(
        "FFmpeg binary could not be found. Ensure ffmpeg is in your system PATH "
        "or install imageio-ffmpeg (`pip install imageio-ffmpeg`)."
    )
```

---

## 4. 720p Proxy Downscaling & Encoding Pipeline

### 4.1 Filter Graph & Resolution Scaling
The filter configuration must ensure standard 720p vertical dimension while preserving aspect ratio, while also ensuring that both width and height are **even integers** (divisible by 2). Standard YUV420p chroma subsampling fails in `libx264` if width or height is odd.

- **Primary Filter**: `-vf "scale=-2:720"`
  - `-2` instructs FFmpeg to calculate the width automatically to maintain the original aspect ratio, rounding to the nearest multiple of 2.
  - `720` fixes the output height to 720 pixels.
  - **Behaviors**:
    - **16:9 Landscape 4K (3840x2160)** $\to$ $1280 \times 720$
    - **16:9 Landscape 1080p (1920x1080)** $\to$ $1280 \times 720$
    - **9:16 Portrait (1080x1920)** $\to$ $406 \times 720$
    - **1:1 Square (1080x1080)** $\to$ $720 \times 720$

- **Conditional Box Scaling Alternative**:
  `-vf "scale='min(1280,iw)':-2"` or `scale=-2:'min(720,ih)'` (can be passed via `scale_filter` parameter).

- **Pixel Format**: `-pix_fmt yuv420p`
  - High-end smartphones (iPhone ProRes / HDR 10-bit) and modern cameras output `yuv422p10le` or `yuv420p10le`.
  - Browsers (Chrome/Safari/Firefox) cannot decode 10-bit H.264 in standard HTML5 `<video>` tags without stutter or black screens.
  - Explicitly forcing `-pix_fmt yuv420p` normalizes the chroma planes to 8-bit 4:2:0.

### 4.2 Encoding Parameters & Performance Profile

| Flag | Parameter | Rationale |
|------|-----------|-----------|
| `-y` | Overwrite | Overwrite target file without prompt in automated pipelines |
| `-i` | `<source_file>` | Source video file path |
| `-vf` | `scale=-2:720` | Aspect-preserving 720p downscaling with even pixel alignment |
| `-c:v` | `libx264` | Broadest HTML5 browser decoding compatibility |
| `-preset` | `fast` | High encoding throughput with minimal CPU overhead |
| `-crf` | `23` | Visually lossless compression profile for proxy preview |
| `-pix_fmt` | `yuv420p` | Standard 8-bit YUV format supported across all modern web browsers |
| `-c:a` | `aac` | Re-encodes audio to standard AAC format (preventing playback failure from 5.1 AC3 or raw PCM source audio) |
| `-b:a` | `128k` | High quality stereo audio bitrate |
| `-movflags` | `+faststart` | Moves the `moov` atom header from the end to the beginning of the MP4 container for instant HTTP byte-range scrubbing |

---

## 5. Subprocess Execution & Error Handling Blueprint

### 5.1 Invocation Protocol
```python
def generate_proxy(
    self,
    source_file: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    target_height: int = 720,
) -> Path:
    source = Path(source_file).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Input video file not found: {source}")

    if output_path is None:
        proxies_dir = self.proxies_dir or source.parent / "proxies"
        output_path = proxies_dir / f"{source.stem}_proxy_720p.mp4"
    else:
        output_path = Path(output_path).resolve()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        self.ffmpeg_bin,
        "-y",
        "-i", str(source),
        "-vf", f"scale=-2:{target_height}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"FFmpeg binary not found or not executable at '{self.ffmpeg_bin}': {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Subprocess execution error during proxy generation: {exc}") from exc

    if res.returncode != 0:
        raise RuntimeError(
            f"FFmpeg proxy generation failed with exit code {res.returncode}.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Error Output:\n{res.stderr}"
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Proxy generation produced an empty or missing output file at: {output_path}")

    return output_path
```

---

## 6. Complete Blueprint for `unified_ops_hub/ml_agent/editor.py`

Below is the exact code specification for `unified_ops_hub/ml_agent/editor.py` including both the Proxy Engine and the Audio DSP Cut Generator:

```python
"""Antigravity Media Studio - MediaEditor & AI Cut Generation Engine.
Handles 720p proxy generation via FFmpeg subprocess, in-memory audio extraction,
and DSP-based loud-peak audio detection for automated edit cuts.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


class MediaEditor:
    """Core Media Studio editor for AI proxy generation and cut metadata synthesis."""

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        proxies_dir: Optional[Union[str, Path]] = None,
    ):
        """Initializes the MediaEditor with FFmpeg binary resolution.
        
        Args:
            ffmpeg_path: Optional explicit path to ffmpeg binary.
            proxies_dir: Optional directory to store generated proxy files.
        """
        self.ffmpeg_bin = self._resolve_ffmpeg(ffmpeg_path)
        self.proxies_dir = Path(proxies_dir).resolve() if proxies_dir else None

    @classmethod
    def _resolve_ffmpeg(cls, custom_path: Optional[str] = None) -> str:
        """Resolves the FFmpeg binary using a 5-tier fallback cascade."""
        if custom_path:
            if Path(custom_path).is_file() or shutil.which(custom_path):
                return str(custom_path)
            raise FileNotFoundError(f"Specified FFmpeg executable does not exist: {custom_path}")

        for env_var in ("FFMPEG_BINARY", "FFMPEG_PATH", "IMAGEIO_FFMPEG_EXE"):
            val = os.environ.get(env_var)
            if val and (Path(val).is_file() or shutil.which(val)):
                return str(val)

        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and Path(exe).is_file():
                return str(exe)
        except (ImportError, Exception):
            pass

        which_exe = shutil.which("ffmpeg")
        if which_exe:
            return str(which_exe)

        raise FileNotFoundError(
            "FFmpeg binary not found. Install imageio-ffmpeg (`pip install imageio-ffmpeg`) "
            "or add ffmpeg to PATH."
        )

    def get_video_duration(self, source_file: Union[str, Path]) -> float:
        """Extracts media duration in seconds via FFmpeg stderr inspection."""
        source = Path(source_file).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source}")

        cmd = [self.ffmpeg_bin, "-i", str(source)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
        if not match:
            # Fallback duration or error if completely unreadable
            raise RuntimeError(f"Could not parse media duration from FFmpeg output:\n{res.stderr}")

        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    def generate_proxy(
        self,
        source_file: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        target_height: int = 720,
    ) -> Path:
        """Generates a 720p H.264 Faststart proxy video for web playback."""
        source = Path(source_file).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Input video file not found: {source}")

        if output_path is None:
            proxies_dir = self.proxies_dir or (source.parent / "proxies")
            output_path = proxies_dir / f"{source.stem}_proxy_720p.mp4"
        else:
            output_path = Path(output_path).resolve()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(source),
            "-vf", f"scale=-2:{target_height}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"FFmpeg binary not found at '{self.ffmpeg_bin}': {exc}") from exc

        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg proxy generation failed with code {res.returncode}:\n{res.stderr}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"FFmpeg produced an empty or missing proxy file: {output_path}")

        return output_path

    def extract_audio_pcm(
        self,
        source_file: Union[str, Path],
        sample_rate: int = 44100,
    ) -> np.ndarray:
        """Extracts mono 16-bit PCM audio samples directly into memory as a numpy array."""
        source = Path(source_file).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source}")

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(source),
            "-vn",
            "-ac", "1",
            "-ar", str(sample_rate),
            "-f", "s16le",
            "-",
        ]

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if res.returncode != 0:
            # If no audio track or extraction fails, return silent array
            return np.zeros(0, dtype=np.int16)

        pcm_data = np.frombuffer(res.stdout, dtype=np.int16)
        return pcm_data

    def detect_hype_drop_in_out(
        self,
        audio_pcm: np.ndarray,
        duration: float,
        target_window_sec: float = 15.0,
        sample_rate: int = 44100,
    ) -> Tuple[float, float]:
        """Detects the loudest audio peak window using sliding RMS energy argmax."""
        if duration <= 0:
            return (0.0, 0.0)

        window_duration = min(target_window_sec, duration)
        if len(audio_pcm) == 0:
            # Silence / no audio fallback: center window or start at 0
            in_pt = max(0.0, (duration - window_duration) / 2.0)
            return (round(in_pt, 2), round(in_pt + window_duration, 2))

        # Downsample RMS calculation using 100ms frames
        frame_size = int(sample_rate * 0.1)
        if frame_size <= 0:
            frame_size = 1

        n_frames = len(audio_pcm) // frame_size
        if n_frames == 0:
            return (0.0, round(window_duration, 2))

        audio_trimmed = audio_pcm[: n_frames * frame_size].astype(np.float32)
        frames = audio_trimmed.reshape(n_frames, frame_size)
        rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-9)

        # Sliding window over RMS frames
        frames_per_window = max(1, int((window_duration / 0.1)))
        if len(rms) <= frames_per_window:
            return (0.0, round(window_duration, 2))

        window_energies = np.convolve(rms, np.ones(frames_per_window), mode="valid")
        best_frame_idx = int(np.argmax(window_energies))
        in_point = best_frame_idx * 0.1
        out_point = in_point + window_duration

        # Clamp within video duration
        if out_point > duration:
            out_point = duration
            in_point = max(0.0, duration - window_duration)

        return (round(in_point, 2), round(out_point, 2))

    def process_video(
        self,
        source_file: Union[str, Path],
        output_proxy_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Runs full proxy generation and 3-cut metadata synthesis."""
        source = Path(source_file).resolve()
        duration = self.get_video_duration(source)
        proxy_path = self.generate_proxy(source, output_proxy_path)

        pcm = self.extract_audio_pcm(source)
        hype_in, hype_out = self.detect_hype_drop_in_out(pcm, duration, target_window_sec=15.0)

        metadata = {
            "source_file": str(source),
            "proxy_file": str(proxy_path),
            "duration": round(duration, 2),
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
                    "out_point": round(duration, 2),
                    "crop_ratio": "16:9",
                    "label": "Cinematic (16:9)",
                    "target_resolution": "1920x1080",
                },
                "raw_pov": {
                    "in_point": 0.0,
                    "out_point": round(duration, 2),
                    "crop_ratio": "original",
                    "label": "Raw POV (Original)",
                    "target_resolution": "original",
                },
            },
        }
        return metadata
```

---

## 7. Module Exports & R16 Compliance

### 7.1 Updates to `unified_ops_hub/ml_agent/__init__.py`
```python
"""Antigravity ML Agent & Autonomy Optimization Loop Module.
Provides SQLite WAL telemetry tracking, sub-5ms localized K-Means clustering,
closed-loop execution policy adaptation, and autonomous trend pipeline orchestration.
"""

from unified_ops_hub.ml_agent.telemetry import TelemetryStore
from unified_ops_hub.ml_agent.clustering import KMeansOptimizer
from unified_ops_hub.ml_agent.policy import PolicyEngine
from unified_ops_hub.ml_agent.ml_agent import (
    AutonomousMLAgent,
    build_ml_agent_config,
    execute_trends_garbage_collection,
)
from unified_ops_hub.ml_agent.editor import MediaEditor

__all__ = [
    "TelemetryStore",
    "KMeansOptimizer",
    "PolicyEngine",
    "AutonomousMLAgent",
    "build_ml_agent_config",
    "execute_trends_garbage_collection",
    "MediaEditor",
]
```

---

## 8. Test-Driven Verification Plan (`tests/test_media_editor.py`)

In accordance with Rule R2 (The Leash Protocol / Loud Assertions), the test suite will enforce the following invariants:

1. **`test_media_editor_ffmpeg_resolution_fallback`**:
   - Verify explicit custom path resolves correctly.
   - Verify `FFMPEG_BINARY` environment variable override works.
   - Verify `imageio_ffmpeg` fallback works.
   - Loudly assert `FileNotFoundError` when an invalid path is passed.

2. **`test_media_editor_generate_proxy_loud_assertions`**:
   - Synthesize a 3-second 1080p test video with audio via FFmpeg `testsrc` and `sine` filter.
   - Execute `editor.generate_proxy(source_video, proxy_path)`.
   - Assert `proxy_path.exists()` and `proxy_path.stat().st_size > 0`.
   - Inspect proxy metadata via FFmpeg stderr:
     - Height must equal 720.
     - Pixel format must equal `yuv420p`.
     - Codec must be `h264`.

3. **`test_media_editor_non_existent_source_raises`**:
   - Assert `FileNotFoundError` is raised when non-existent source path is provided.

4. **`test_media_editor_process_video_contract`**:
   - Assert full JSON structure matches `PROJECT.md` contract schema (`source_file`, `proxy_file`, `duration`, `cuts` dictionary with `hype_drop`, `cinematic`, `raw_pov`).
   - Validate `hype_drop` has `crop_ratio == "9:16"` and `in_point < out_point <= duration`.
