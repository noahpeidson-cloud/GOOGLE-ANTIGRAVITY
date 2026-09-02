"""Antigravity Media Studio - MediaEditor & AI Cut Generation Engine.
Handles 720p H.264 Faststart proxy downscaling via FFmpeg subprocess, in-memory PCM
audio DSP peak detection, and 3-cut JSON metadata compilation (hype_drop, cinematic, raw_pov).
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np


class MediaEditor:
    """Core Media Studio editor for AI proxy generation and cut metadata synthesis."""

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        proxies_dir: Optional[Union[str, Path]] = None,
    ):
        """Initializes the MediaEditor with dynamic FFmpeg binary resolution.

        Args:
            ffmpeg_path: Optional explicit path to ffmpeg binary.
            proxies_dir: Optional default directory to store generated proxy files.
        """
        self.ffmpeg_bin = self._resolve_ffmpeg(ffmpeg_path)
        self.proxies_dir = Path(proxies_dir).resolve() if proxies_dir else None

    @classmethod
    def _resolve_ffmpeg(cls, custom_path: Optional[str] = None) -> str:
        """Resolves the FFmpeg binary using a 5-tier fallback cascade.

        Args:
            custom_path: Optional explicit path to verify.

        Returns:
            str: Resolved absolute or executable path to FFmpeg.

        Raises:
            FileNotFoundError: If no valid FFmpeg executable can be found.
        """
        # 1. Custom explicit path passed to constructor
        if custom_path:
            if Path(custom_path).is_file() or shutil.which(custom_path):
                return str(custom_path)
            raise FileNotFoundError(f"Specified FFmpeg executable does not exist: {custom_path}")

        # 2. Environment variables
        for env_var in ("FFMPEG_BINARY", "FFMPEG_PATH", "IMAGEIO_FFMPEG_EXE"):
            val = os.environ.get(env_var)
            if val and (Path(val).is_file() or shutil.which(val)):
                return str(val)

        # 3. imageio_ffmpeg dynamic detection
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and Path(exe).is_file():
                return str(exe)
        except (ImportError, Exception):
            pass

        # 4. PATH lookup
        which_exe = shutil.which("ffmpeg")
        if which_exe:
            return str(which_exe)

        # 5. Fallback failure
        raise FileNotFoundError(
            "FFmpeg binary not found. Ensure ffmpeg is in your system PATH "
            "or install imageio-ffmpeg (`pip install imageio-ffmpeg`)."
        )

    def probe_media(self, source_file: Union[str, Path]) -> Dict[str, Any]:
        """Probes media metadata (duration, width, height, audio presence) via FFmpeg stderr.

        Args:
            source_file: Path to source video file.

        Returns:
            Dict[str, Any]: Extracted metadata properties.

        Raises:
            FileNotFoundError: If source_file does not exist.
        """
        source = Path(source_file).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Source media file does not exist: {source_file}")

        cmd = [self.ffmpeg_bin, "-i", str(source)]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        stderr = res.stderr

        # Duration parsing: Duration: 00:00:10.00
        duration = 0.0
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
        if dur_match:
            hours, minutes, seconds = dur_match.groups()
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

        # Resolution parsing: Video: h264 ..., 1920x1080 ...
        width, height = 1920, 1080
        res_match = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", stderr)
        if res_match:
            width, height = map(int, res_match.groups())

        # Audio stream detection
        has_audio = bool(re.search(r"Stream #.*?: Audio:", stderr))

        return {
            "duration": round(duration, 2),
            "width": width,
            "height": height,
            "has_audio": has_audio,
        }

    def get_video_info(self, source_file: Union[str, Path]) -> Dict[str, Any]:
        """Alias for probe_media."""
        return self.probe_media(source_file)

    def get_video_duration(self, source_file: Union[str, Path]) -> float:
        """Extracts media duration in seconds.

        Args:
            source_file: Path to video file.

        Returns:
            float: Video duration in seconds.
        """
        info = self.probe_media(source_file)
        return float(info["duration"])

    def generate_proxy(
        self,
        source_file: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        target_height: int = 720,
        crf: int = 23,
        preset: str = "fast",
        proxy_dir: str = "proxies",
    ) -> str:
        """Generates a 720p H.264 Faststart proxy video for web playback.

        Args:
            source_file: Path to raw input video.
            output_path: Optional explicit output destination.
            target_height: Vertical resolution in pixels (default: 720).
            crf: Constant Rate Factor (default: 23).
            preset: Encoding speed preset (default: 'fast').
            proxy_dir: Default output directory if output_path is None.

        Returns:
            str: Path to generated proxy file.

        Raises:
            FileNotFoundError: If source_file or FFmpeg binary does not exist.
            RuntimeError: If FFmpeg fails or creates an empty output.
        """
        source = Path(source_file).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Input video file not found: {source_file}")

        if output_path is None:
            pdir = self.proxies_dir or Path(proxy_dir)
            pdir.mkdir(parents=True, exist_ok=True)
            target_out = pdir / f"{source.stem}_proxy.mp4"
        else:
            target_out = Path(output_path)
            target_out.parent.mkdir(parents=True, exist_ok=True)

        info = self.probe_media(source_file)

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(source),
            "-vf", f"scale=-2:{target_height}",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
        ]

        if info["has_audio"]:
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.extend(["-an"])

        cmd.extend(["-movflags", "+faststart", str(target_out)])

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"FFmpeg binary not found at '{self.ffmpeg_bin}': {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Subprocess execution error during proxy generation: {exc}") from exc

        if res.returncode != 0:
            raise RuntimeError(
                f"FFmpeg proxy generation failed with exit code {res.returncode}.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Error Output:\n{res.stderr}"
            )

        if not target_out.exists() or target_out.stat().st_size == 0:
            raise RuntimeError(f"Proxy generation produced an empty or missing output file at: {target_out}")

        return str(target_out)

    def extract_pcm_audio(
        self,
        source_file: Union[str, Path],
        sample_rate: int = 22050,
    ) -> bytes:
        """Extracts mono 16-bit PCM audio directly into RAM via FFmpeg stdout pipe.

        Args:
            source_file: Path to video file.
            sample_rate: Target sample rate in Hz (default: 22050).

        Returns:
            bytes: Raw signed 16-bit PCM stream, or b"" if no audio exists.

        Raises:
            FileNotFoundError: If source_file does not exist.
        """
        source = Path(source_file).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Source media file not found: {source_file}")

        cmd = [
            self.ffmpeg_bin,
            "-v", "error",
            "-i", str(source),
            "-vn",
            "-ac", "1",
            "-ar", str(sample_rate),
            "-f", "s16le",
            "-",
        ]

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        if res.returncode != 0 or len(res.stdout) == 0:
            return b""

        return res.stdout

    def detect_audio_peak(
        self,
        source_file: Union[str, Path],
        target_duration: float = 15.0,
        window_duration_sec: Optional[float] = None,
        frame_duration_ms: float = 50.0,
        sample_rate: int = 22050,
    ) -> Tuple[float, float]:
        """Detects loudest audio peak window using vectorized RMS energy sliding sum.

        Args:
            source_file: Path to source media file.
            target_duration: Target window duration in seconds (default: 15.0s).
            window_duration_sec: Optional alias for target_duration.
            frame_duration_ms: Frame length for RMS calculation in ms (default: 50.0ms).
            sample_rate: Audio resampling frequency in Hz (default: 22050).

        Returns:
            Tuple[float, float]: (in_point, out_point) in seconds.

        Raises:
            FileNotFoundError: If source_file does not exist.
        """
        if window_duration_sec is not None:
            target_duration = window_duration_sec

        info = self.probe_media(source_file)
        duration = float(info["duration"])

        if duration <= 0.0:
            return 0.0, 0.0

        effective_window = min(target_duration, duration)

        if not info["has_audio"]:
            return 0.0, round(effective_window, 2)

        pcm_bytes = self.extract_pcm_audio(source_file, sample_rate=sample_rate)
        if not pcm_bytes:
            return 0.0, round(effective_window, 2)

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        if len(samples) == 0 or np.max(np.abs(samples)) < 1e-3:
            # Pure silence or empty samples fallback
            return 0.0, round(effective_window, 2)

        frame_size = int(sample_rate * (frame_duration_ms / 1000.0))
        if frame_size <= 0:
            frame_size = 1

        n_frames = len(samples) // frame_size
        if n_frames == 0:
            return 0.0, round(effective_window, 2)

        framed = samples[: n_frames * frame_size].reshape((n_frames, frame_size))
        frame_rms = np.sqrt(np.mean(framed ** 2, axis=1) + 1e-9)

        # Check for near-total silence
        if np.max(frame_rms) < 1.0:
            return 0.0, round(effective_window, 2)

        k = max(1, int(round(effective_window / (frame_size / sample_rate))))
        if n_frames <= k or duration <= target_duration:
            return 0.0, round(duration, 2)

        # O(N) Sliding window cumulative sum
        cumsum = np.cumsum(np.insert(frame_rms, 0, 0.0))
        window_sums = cumsum[k:] - cumsum[:-k]
        best_idx = int(np.argmax(window_sums))

        in_point = round(best_idx * (frame_size / sample_rate), 2)
        out_point = round(in_point + effective_window, 2)

        # Clamp within video boundaries
        if out_point > duration:
            out_point = round(duration, 2)
            in_point = max(0.0, round(out_point - effective_window, 2))

        return in_point, out_point

    def generate_cuts_metadata(
        self,
        source_file: Union[str, Path],
        duration: float,
        in_point: float,
        out_point: float,
    ) -> Dict[str, Any]:
        """Compiles the 3-cut JSON dictionary adhering to PROJECT.md interface contract.

        Args:
            source_file: Path to source video.
            duration: Video duration in seconds.
            in_point: Start timestamp for hype_drop cut.
            out_point: End timestamp for hype_drop cut.

        Returns:
            Dict[str, Any]: Dictionary containing 'hype_drop', 'cinematic', and 'raw_pov'.
        """
        dur_rounded = round(float(duration), 2)
        return {
            "hype_drop": {
                "in_point": round(float(in_point), 2),
                "out_point": round(float(out_point), 2),
                "crop_ratio": "9:16",
                "label": "Hype Drop (Audio Peak)",
                "target_resolution": "1080x1920",
            },
            "cinematic": {
                "in_point": 0.0,
                "out_point": dur_rounded,
                "crop_ratio": "16:9",
                "label": "Cinematic (16:9)",
                "target_resolution": "1920x1080",
            },
            "raw_pov": {
                "in_point": 0.0,
                "out_point": dur_rounded,
                "crop_ratio": "original",
                "label": "Raw POV (Original)",
                "target_resolution": "original",
            },
        }

    def generate_cuts(
        self,
        source_file: Union[str, Path],
        duration: Optional[float] = None,
        window_duration_sec: float = 15.0,
    ) -> Dict[str, Any]:
        """Computes audio peak timestamps and generates the 3-cut metadata dictionary.

        Args:
            source_file: Path to source media file.
            duration: Optional pre-probed duration in seconds.
            window_duration_sec: Window length for hype_drop peak.

        Returns:
            Dict[str, Any]: 3-cut dictionary.
        """
        if duration is None:
            duration = self.get_video_duration(source_file)

        in_point, out_point = self.detect_audio_peak(
            source_file,
            target_duration=window_duration_sec,
        )

        return self.generate_cuts_metadata(
            source_file=source_file,
            duration=duration,
            in_point=in_point,
            out_point=out_point,
        )

    def generate_proxy_and_cuts(
        self,
        source_file: Union[str, Path],
        proxy_dir: str = "proxies",
        target_height: int = 720,
        window_duration_sec: float = 15.0,
    ) -> Dict[str, Any]:
        """End-to-end pipeline: Generates 720p proxy and compiles 3-cut metadata payload.

        Args:
            source_file: Path to source video file.
            proxy_dir: Destination folder for proxies.
            target_height: Height in pixels for proxy video.
            window_duration_sec: Window length for audio peak hype_drop.

        Returns:
            Dict[str, Any]: Complete payload matching PROJECT.md interface contract.
        """
        source = Path(source_file).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Source media file does not exist: {source_file}")

        duration = self.get_video_duration(source_file)
        proxy_path = self.generate_proxy(
            source_file=source_file,
            proxy_dir=proxy_dir,
            target_height=target_height,
        )

        cuts = self.generate_cuts(
            source_file=source_file,
            duration=duration,
            window_duration_sec=window_duration_sec,
        )

        return {
            "source_file": str(source_file),
            "proxy_file": str(proxy_path),
            "duration": round(duration, 2),
            "cuts": cuts,
        }
