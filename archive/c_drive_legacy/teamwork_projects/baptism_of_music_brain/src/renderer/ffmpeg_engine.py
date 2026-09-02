"""Desktop FFmpeg High-Fidelity Lossless Video Rendering Engine & Atomic Delivery Pipeline.

Executes Edit Decision Lists (EDLs) using local desktop-class FFmpeg subprocesses,
streaming real-time progress to callbacks, asserting mathematical stream integrity via ffprobe,
and atomically delivering finalized masters to the delivery repository.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from config.settings import AppSettings, get_settings
from src.models.schemas import EditDecisionList, MediaProbeResult
from src.renderer.filtergraph import compile_filtergraph
from src.renderer.probe import FFprobeError, async_probe_media, probe_media
from src.renderer.profiles import get_encoding_args, get_profile, resolve_profile_with_fallback

logger = logging.getLogger(__name__)


class FFmpegError(Exception):
    """Base exception for FFmpeg engine errors."""
    pass


class FFmpegNotFoundError(FFmpegError):
    """Raised when FFmpeg binary is missing on disk."""
    pass


class FFmpegExecutionError(FFmpegError):
    """Raised when FFmpeg process exits with a non-zero code or fails during render."""
    pass


class RenderVerificationError(FFmpegError):
    """Raised when post-render ffprobe verification fails."""
    pass


def parse_time_to_seconds(time_str: str) -> float:
    """Parse FFmpeg time format 'HH:MM:SS.MICRO' into total seconds."""
    time_str = time_str.strip()
    if not time_str or time_str == "N/A":
        return 0.0

    try:
        parts = time_str.split(":")
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        else:
            return float(time_str)
    except Exception:
        return 0.0


class FFmpegRenderer:
    """
    High-fidelity video rendering engine executing compiled filtergraphs
    with real-time progress parsing and atomic delivery.
    """

    def __init__(
        self,
        settings: Optional[AppSettings] = None,
        delivery_dir: Optional[Union[str, Path]] = None,
        temp_dir: Optional[Union[str, Path]] = None,
        ffmpeg_bin: Optional[str] = None,
        ffprobe_bin: Optional[str] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.delivery_dir = Path(delivery_dir).resolve() if delivery_dir else self.settings.delivery_dir
        self.temp_dir = Path(temp_dir).resolve() if temp_dir else self.settings.temp_dir
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create delivery and temp directories if they do not exist."""
        self.delivery_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_ffmpeg_binary(self) -> str:
        """Resolve valid ffmpeg binary path or raise FFmpegNotFoundError."""
        if self.ffmpeg_bin and os.path.exists(self.ffmpeg_bin):
            return str(Path(self.ffmpeg_bin).resolve())

        try:
            return self.settings.resolve_ffmpeg_bin()
        except Exception as exc:
            raise FFmpegNotFoundError(f"Failed to locate ffmpeg binary: {exc}") from exc

    def _resolve_ffprobe_binary(self) -> str:
        """Resolve valid ffprobe binary path or raise FFmpegNotFoundError."""
        if self.ffprobe_bin and os.path.exists(self.ffprobe_bin):
            return str(Path(self.ffprobe_bin).resolve())

        try:
            return self.settings.resolve_ffprobe_bin()
        except Exception as exc:
            raise FFmpegNotFoundError(f"Failed to locate ffprobe binary: {exc}") from exc

    def build_ffmpeg_command(
        self,
        edl: EditDecisionList,
        output_temp_path: Path,
    ) -> Tuple[List[str], Any]:
        """Compile EDL into complete FFmpeg execution command arguments."""
        bin_path = self._resolve_ffmpeg_binary()
        compilation = compile_filtergraph(edl)

        cmd = [
            bin_path,
            "-y",
            "-hide_banner",
        ]

        # Add all input files
        for src_file in compilation.input_files:
            cmd.extend(["-i", str(Path(src_file).resolve())])

        # Filter complex
        cmd.extend(["-filter_complex", compilation.filter_complex_str])

        # Stream mappings
        cmd.extend(["-map", compilation.map_video_label])
        cmd.extend(["-map", compilation.map_audio_label])

        # Profile Encoding Flags
        encoding_profile = edl.encoding_profile or self.settings.default_profile
        encoding_args = get_encoding_args(
            encoding_profile,
            fallback_to_software=True,
            ffmpeg_bin=bin_path,
        )
        cmd.extend(encoding_args)

        # Output timeline framerate
        if edl.target_fps > 0:
            cmd.extend(["-r", str(round(edl.target_fps, 3))])

        # Progress reporting over stdout pipe
        cmd.extend(["-progress", "pipe:1"])

        # Output file destination
        cmd.append(str(output_temp_path.resolve()))

        return cmd, compilation

    def render_edl(
        self,
        edl: EditDecisionList,
        progress_callback: Optional[Callable[[float], None]] = None,
        output_filename: Optional[str] = None,
    ) -> str:
        """
        Synchronously render an EDL with atomic staging and post-render ffprobe verification.
        Returns the absolute string path to the delivered master video.
        """
        self._ensure_dirs()
        profile = resolve_profile_with_fallback(edl.encoding_profile or self.settings.default_profile)
        ext = profile.container_extension

        final_name = output_filename or f"{edl.job_id}_master{ext}"
        final_delivery_path = self.delivery_dir / final_name
        staging_temp_path = self.delivery_dir / f".tmp_{edl.job_id}_{final_name}"

        cmd, compilation = self.build_ffmpeg_command(edl, staging_temp_path)
        total_duration = max(0.1, edl.total_timeline_duration)

        logger.info(f"Starting synchronous FFmpeg render for job {edl.job_id} -> {staging_temp_path.name}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        stderr_lines: List[str] = []

        def drain_stderr():
            try:
                if process.stderr:
                    for err_line in process.stderr:
                        stderr_lines.append(err_line)
            except Exception:
                pass

        stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
        stderr_thread.start()

        try:
            # Parse stdout progress line by line while stderr is drained concurrently
            if process.stdout:
                for raw_line in process.stdout:
                    line = raw_line.strip()
                    if "=" in line:
                        key, val = line.split("=", 1)
                        if key in ("out_time_ms", "out_time_us"):
                            try:
                                us_val = float(val)
                                cur_sec = us_val / 1_000_000.0 if key == "out_time_us" else us_val / 1000.0
                                pct = min(99.0, max(0.0, (cur_sec / total_duration) * 100.0))
                                if progress_callback:
                                    progress_callback(round(pct, 1))
                            except Exception:
                                pass
                        elif key == "out_time":
                            cur_sec = parse_time_to_seconds(val)
                            pct = min(99.0, max(0.0, (cur_sec / total_duration) * 100.0))
                            if progress_callback:
                                progress_callback(round(pct, 1))
                        elif key == "progress" and val == "end":
                            if progress_callback:
                                progress_callback(100.0)

            process.wait()
            stderr_thread.join(timeout=3.0)

        except Exception as exc:
            process.kill()
            if staging_temp_path.exists():
                staging_temp_path.unlink(missing_ok=True)
            raise FFmpegExecutionError(f"FFmpeg rendering crashed: {exc}") from exc

        if process.returncode != 0:
            err_msg = "".join(stderr_lines).strip()
            if staging_temp_path.exists():
                staging_temp_path.unlink(missing_ok=True)
            raise FFmpegExecutionError(
                f"FFmpeg execution failed (code {process.returncode}): {err_msg}"
            )

        # Verification & Atomic Move
        if not staging_temp_path.exists() or staging_temp_path.stat().st_size == 0:
            if staging_temp_path.exists():
                staging_temp_path.unlink(missing_ok=True)
            raise FFmpegExecutionError("FFmpeg reported success but output staging file is missing or 0 bytes.")

        try:
            # Probe verification
            probe_result = probe_media(staging_temp_path, ffprobe_bin=self.ffprobe_bin)
            if not probe_result.has_video:
                raise RenderVerificationError("Rendered master video missing valid video stream.")
        except Exception as probe_err:
            if staging_temp_path.exists():
                staging_temp_path.unlink(missing_ok=True)
            raise RenderVerificationError(f"Post-render verification failed: {probe_err}") from probe_err

        # Atomic Delivery Move
        try:
            if final_delivery_path.exists():
                final_delivery_path.unlink(missing_ok=True)
            os.replace(str(staging_temp_path), str(final_delivery_path))
        except Exception as move_err:
            raise FFmpegExecutionError(f"Atomic delivery move failed: {move_err}") from move_err

        if progress_callback:
            progress_callback(100.0)

        logger.info(f"Rendered master successfully delivered to {final_delivery_path}")
        return str(final_delivery_path.resolve())

    async def async_render_edl(
        self,
        edl: EditDecisionList,
        progress_callback: Optional[Callable[[float], None]] = None,
        output_filename: Optional[str] = None,
    ) -> str:
        """
        Asynchronously render an EDL with non-blocking stdout/stderr reading,
        real-time progress updates, and atomic delivery.
        """
        self._ensure_dirs()
        profile = resolve_profile_with_fallback(edl.encoding_profile or self.settings.default_profile)
        ext = profile.container_extension

        final_name = output_filename or f"{edl.job_id}_master{ext}"
        final_delivery_path = self.delivery_dir / final_name
        staging_temp_path = self.delivery_dir / f".tmp_{edl.job_id}_{final_name}"

        cmd, compilation = self.build_ffmpeg_command(edl, staging_temp_path)
        total_duration = max(0.1, edl.total_timeline_duration)

        logger.info(f"Starting async FFmpeg render for job {edl.job_id} -> {staging_temp_path.name}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stderr_accumulator: List[str] = []

        async def read_stdout_progress():
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    if key in ("out_time_ms", "out_time_us"):
                        try:
                            us_val = float(val)
                            cur_sec = us_val / 1_000_000.0 if key == "out_time_us" else us_val / 1000.0
                            pct = min(99.0, max(0.0, (cur_sec / total_duration) * 100.0))
                            if progress_callback:
                                progress_callback(round(pct, 1))
                        except Exception:
                            pass
                    elif key == "out_time":
                        cur_sec = parse_time_to_seconds(val)
                        pct = min(99.0, max(0.0, (cur_sec / total_duration) * 100.0))
                        if progress_callback:
                            progress_callback(round(pct, 1))
                    elif key == "progress" and val == "end":
                        if progress_callback:
                            progress_callback(100.0)

        async def read_stderr_log():
            while True:
                line_bytes = await process.stderr.readline()
                if not line_bytes:
                    break
                stderr_accumulator.append(line_bytes.decode("utf-8", errors="replace"))

        try:
            await asyncio.gather(read_stdout_progress(), read_stderr_log())
            returncode = await process.wait()
        except Exception as exc:
            try:
                process.kill()
            except Exception:
                pass
            if staging_temp_path.exists():
                staging_temp_path.unlink(missing_ok=True)
            raise FFmpegExecutionError(f"Async FFmpeg execution crashed: {exc}") from exc

        if returncode != 0:
            err_msg = "".join(stderr_accumulator).strip()
            if staging_temp_path.exists():
                staging_temp_path.unlink(missing_ok=True)
            raise FFmpegExecutionError(
                f"FFmpeg execution failed with returncode {returncode}: {err_msg}"
            )

        # Verification & Atomic Move
        if not staging_temp_path.exists() or staging_temp_path.stat().st_size == 0:
            if staging_temp_path.exists():
                staging_temp_path.unlink(missing_ok=True)
            raise FFmpegExecutionError("FFmpeg reported success but output staging file is missing or 0 bytes.")

        try:
            probe_result = await async_probe_media(staging_temp_path, ffprobe_bin=self.ffprobe_bin)
            if not probe_result.has_video:
                raise RenderVerificationError("Rendered master video missing valid video stream.")
        except Exception as probe_err:
            if staging_temp_path.exists():
                staging_temp_path.unlink(missing_ok=True)
            raise RenderVerificationError(f"Post-render async verification failed: {probe_err}") from probe_err

        # Atomic Delivery Move
        try:
            if final_delivery_path.exists():
                final_delivery_path.unlink(missing_ok=True)
            os.replace(str(staging_temp_path), str(final_delivery_path))
        except Exception as move_err:
            raise FFmpegExecutionError(f"Atomic delivery move failed: {move_err}") from move_err

        if progress_callback:
            progress_callback(100.0)

        logger.info(f"Async render successfully delivered to {final_delivery_path}")
        return str(final_delivery_path.resolve())
