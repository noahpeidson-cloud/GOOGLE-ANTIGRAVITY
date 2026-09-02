"""Application settings and environment configuration for baptism_of_music_brain."""

from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Optional, Set

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Typed application settings managed via pydantic-settings and environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="BRAIN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application Info
    app_name: str = Field(default="baptism_of_music_brain", description="Application identifier")
    app_version: str = Field(default="0.1.0", description="Application semantic version")
    environment: str = Field(default="development", description="Runtime environment: development, testing, production")
    host: str = Field(default="127.0.0.1", description="FastAPI server host binding")
    port: int = Field(default=8000, ge=1024, le=65535, description="FastAPI server HTTP port")

    # Directory Paths
    ingest_dir: Path = Field(default=Path("ingest"), description="Incoming raw video drop directory")
    delivery_dir: Path = Field(default=Path("delivery"), description="Final master renders export directory")
    temp_dir: Path = Field(default=Path(".tmp"), description="Intermediate staging and temp directory")

    # Encoding & Rendering Profiles
    default_profile: str = Field(default="x264_crf17", description="Default visually lossless encoding profile")
    max_concurrent_renders: int = Field(default=2, ge=1, le=16, description="Max concurrent FFmpeg rendering subprocesses")

    # ML Brain & External APIs
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API Key")
    mock_ml: bool = Field(default=False, description="Force offline deterministic mock ML engine")

    # FFmpeg / FFprobe Explicit Binary Paths
    ffmpeg_path: Optional[str] = Field(default=None, description="Explicit path to ffmpeg executable")
    ffprobe_path: Optional[str] = Field(default=None, description="Explicit path to ffprobe executable")

    # Ingestion & Windows File Lock Parameters
    lock_poll_interval_sec: float = Field(default=0.25, ge=0.01, description="Polling frequency for Win32 lock detection")
    lock_timeout_sec: float = Field(default=30.0, ge=1.0, description="Timeout in seconds before failing lock wait")
    debounce_delay_sec: float = Field(default=1.0, ge=0.01, description="File size stability debounce interval")
    enable_polling_fallback: bool = Field(default=True, description="Enable periodic background directory polling")
    polling_fallback_interval_sec: float = Field(default=5.0, ge=0.5, description="Polling interval for fallback directory scan")

    # Extension Whitelists
    allowed_media_extensions: Set[str] = Field(
        default_factory=lambda: {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".ts", ".flv", ".wmv"}
    )
    temp_extensions: Set[str] = Field(
        default_factory=lambda: {
            ".tmp", ".part", ".crdownload", ".downloading",
            ".aria2", ".partial", ".uploading", ".incomplete",
            ".temp", ".swp", ".lock"
        }
    )

    def ensure_directories(self) -> None:
        """Ensure ingest, delivery, and temp directories exist on disk."""
        self.ingest_dir.mkdir(parents=True, exist_ok=True)
        self.delivery_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def resolve_ffmpeg_bin(self) -> str:
        """Resolve the path to the FFmpeg executable."""
        # 1. Explicit path from settings
        if self.ffmpeg_path and os.path.exists(self.ffmpeg_path):
            return str(Path(self.ffmpeg_path).resolve())

        # 2. static_ffmpeg discovery
        try:
            import static_ffmpeg
            ffmpeg_path, _ = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
            if os.path.exists(ffmpeg_path):
                return str(Path(ffmpeg_path).resolve())
        except Exception:
            pass

        # 3. imageio_ffmpeg discovery
        try:
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            if os.path.exists(ffmpeg_path):
                return str(Path(ffmpeg_path).resolve())
        except Exception:
            pass

        # 4. System PATH
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg and os.path.exists(system_ffmpeg):
            return str(Path(system_ffmpeg).resolve())

        # 5. Windows standard candidate locations
        win_candidates = [
            r"C:\Program Files\Logitech\LogiTune\resources\ffmpeg\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\CapCut\Apps\9.3.0.3970\ffmpeg.exe"),
        ]
        for candidate in win_candidates:
            if os.path.exists(candidate):
                return str(Path(candidate).resolve())

        raise RuntimeError("FFmpeg executable could not be resolved from static_ffmpeg, imageio_ffmpeg, or PATH.")

    def resolve_ffprobe_bin(self) -> str:
        """Resolve the path to the FFprobe executable."""
        # 1. Explicit path from settings
        if self.ffprobe_path and os.path.exists(self.ffprobe_path):
            return str(Path(self.ffprobe_path).resolve())

        # 2. static_ffmpeg discovery
        try:
            import static_ffmpeg
            _, ffprobe_path = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
            if os.path.exists(ffprobe_path):
                return str(Path(ffprobe_path).resolve())
        except Exception:
            pass

        # 3. System PATH
        system_ffprobe = shutil.which("ffprobe")
        if system_ffprobe and os.path.exists(system_ffprobe):
            return str(Path(system_ffprobe).resolve())

        # 4. Sibling of FFmpeg binary
        try:
            ffmpeg_bin = self.resolve_ffmpeg_bin()
            candidate_sibling = Path(ffmpeg_bin).parent / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
            if candidate_sibling.exists():
                return str(candidate_sibling.resolve())
        except Exception:
            pass

        raise RuntimeError("FFprobe executable could not be resolved from static_ffmpeg or PATH.")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached AppSettings singleton."""
    return AppSettings()
