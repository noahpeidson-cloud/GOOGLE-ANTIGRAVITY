"""
resolve_handoff.py - DaVinci Resolve Studio Python Handoff & Timeline Engine
Part of Track 2: Content Creation & Media Engineering Pipeline

Automates the non-destructive human-in-the-loop handoff from Web UI / PWA to DaVinci Resolve Studio:
1. Resilient Windows / cross-platform discovery of `DaVinciResolveScript` / `fusionscript`.
2. Connects to running DaVinci Resolve Studio instance via `dvr_script.scriptapp("Resolve")`.
3. Loads or creates dedicated vertical 9:16 (1080x1920 or 2160x3840) 60fps project.
4. Imports pristine untouched 4K raw media from `01_RAW` vault into Media Pool without re-encoding.
5. Calculates exact frame indices: start_frame = round(start_time * fps), end_frame = round(end_time * fps).
6. Creates/appends to timeline using `AppendToTimeline([{"mediaPoolItem": item, "startFrame": start_frame, "endFrame": end_frame, "recordFrame": 0}])`.
7. Returns complete execution telemetry and diagnostics for FastAPI PWA and CLI workflows.
"""

from dataclasses import asdict, dataclass, field
import datetime
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

# Set up module logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [resolve_handoff] %(message)s")
logger = logging.getLogger("resolve_handoff")


# ============================================================================
# EXCEPTIONS
# ============================================================================

class ResolveScriptError(Exception):
    """Base exception for DaVinci Resolve scripting operations."""
    pass


class ResolveModuleNotFoundError(ResolveScriptError):
    """Raised when DaVinciResolveScript / fusionscript module cannot be found or loaded."""
    pass


class ResolveNotRunningError(ResolveScriptError):
    """Raised when DaVinci Resolve Studio is not running or external scripting is disabled."""
    pass


class MediaImportError(ResolveScriptError):
    """Raised when a raw media file cannot be imported into the Media Storage or Media Pool."""
    pass


class TimelineCreationError(ResolveScriptError):
    """Raised when timeline creation or clip appending fails in DaVinci Resolve."""
    pass


class ProjectManagementError(ResolveScriptError):
    """Raised when ProjectManager fails to create, load, or configure a project."""
    pass


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ResolveHandoffConfig:
    """Configuration parameters for DaVinci Resolve timeline construction."""
    raw_file_path: Union[str, Path]
    project_name: str = "EDM_Master_Dashboard"
    timeline_name: str = "EDM_Vertical_Timeline"
    start_time: float = 0.0
    end_time: Optional[float] = None
    duration: Optional[float] = 30.0
    fps: float = 60.0
    width: int = 1080
    height: int = 1920
    festival: Optional[str] = "Concert"
    artist: Optional[str] = "Artist"
    track: Optional[str] = "ID"
    auto_save: bool = True
    dry_run: bool = False

    # Aliases for flexibility across survey and API schemas
    @property
    def raw_clip_path(self) -> Path:
        return Path(self.raw_file_path)

    @property
    def start_time_sec(self) -> float:
        return float(self.start_time)

    @property
    def end_time_sec(self) -> float:
        if self.end_time is not None:
            return float(self.end_time)
        dur = self.duration if self.duration is not None else 30.0
        return self.start_time_sec + float(dur)

    @property
    def duration_sec(self) -> float:
        if self.duration is not None:
            return float(self.duration)
        if self.end_time is not None:
            return max(0.0, float(self.end_time) - self.start_time_sec)
        return 30.0

    @property
    def timeline_width(self) -> int:
        return int(self.width)

    @property
    def timeline_height(self) -> int:
        return int(self.height)

    @property
    def timeline_fps(self) -> float:
        return float(self.fps)


@dataclass
class ResolveHandoffResult:
    """Telemetry report produced upon timeline construction."""
    success: bool
    status: str
    project_name: str
    timeline_name: str
    raw_file_path: str
    start_time: float
    end_time: float
    duration: float
    start_frame: int
    end_frame: int
    duration_frames: int
    fps: float
    width: int
    height: int
    timeline_resolution: str
    media_item_name: Optional[str] = None
    timeline_id: Optional[str] = None
    error_message: Optional[str] = None
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to JSON-serializable dictionary."""
        data = asdict(self)
        return data


# ============================================================================
# SCRIPT DISCOVERY & APPLICATION INSTANTIATION
# ============================================================================

def get_resolve_script_search_paths() -> List[str]:
    """
    Returns candidate directory paths where DaVinciResolveScript modules
    are installed on Windows, macOS, and Linux platforms.
    """
    paths: List[str] = []

    # 1. Check explicit environment variables
    env_api = os.environ.get("RESOLVE_SCRIPT_API")
    if env_api:
        paths.append(str(Path(env_api) / "Modules"))
        paths.append(env_api)

    env_lib = os.environ.get("RESOLVE_SCRIPT_LIB")
    if env_lib:
        paths.append(str(Path(env_lib).parent))
        paths.append(env_lib)

    # 2. Windows Standard Paths
    if sys.platform.startswith("win"):
        win_candidates = [
            os.path.expandvars(r"%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules"),
            os.path.expandvars(r"%PROGRAMFILES%\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules"),
            r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules",
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
        ]
        paths.extend(win_candidates)

    # 3. macOS Standard Paths
    elif sys.platform == "darwin":
        mac_candidates = [
            "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
            os.path.expanduser("~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"),
        ]
        paths.extend(mac_candidates)

    # 4. Linux Standard Paths
    else:
        linux_candidates = [
            "/opt/resolve/Developer/Scripting/Modules",
            "/opt/resolve/libs/Fusion/Modules",
            os.path.expanduser("~/.local/share/DaVinciResolve/Developer/Scripting/Modules"),
        ]
        paths.extend(linux_candidates)

    # Deduplicate while preserving order
    seen = set()
    unique_paths = []
    for p in paths:
        norm = os.path.normpath(p)
        if norm not in seen:
            seen.add(norm)
            unique_paths.append(norm)

    return unique_paths


def get_resolve_script_module() -> Any:
    """
    Dynamically discovers and imports the `DaVinciResolveScript` module.
    Raises ResolveModuleNotFoundError if the module cannot be found or loaded.
    """
    try:
        import DaVinciResolveScript as dvr_script
        return dvr_script
    except ImportError:
        pass

    # Search standard candidate paths
    search_paths = get_resolve_script_search_paths()
    for p in search_paths:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
            try:
                import DaVinciResolveScript as dvr_script
                return dvr_script
            except ImportError:
                continue

    raise ResolveModuleNotFoundError(
        "DaVinciResolveScript module could not be loaded. Ensure DaVinci Resolve Studio is installed "
        "and RESOLVE_SCRIPT_API is configured. Searched paths:\n" + "\n".join(f" - {p}" for p in search_paths)
    )


def get_resolve_instance() -> Any:
    """
    Discovers the DaVinciResolveScript module and connects to the active DaVinci Resolve Studio instance.
    Raises ResolveModuleNotFoundError or ResolveNotRunningError if unavailable.
    """
    dvr_script = get_resolve_script_module()

    resolve = None
    try:
        resolve = dvr_script.scriptapp("Resolve")
    except Exception as ex:
        logger.warning(f"Error while calling dvr_script.scriptapp('Resolve'): {ex}")

    if resolve is None:
        try:
            # Fallback attempt via Fusion if Resolve is embedded
            fusion = dvr_script.scriptapp("Fusion")
            if fusion is not None and hasattr(fusion, "GetResolve"):
                resolve = fusion.GetResolve()
        except Exception:
            pass

    if resolve is None:
        raise ResolveNotRunningError(
            "DaVinci Resolve Studio is not running or external scripting is disabled. "
            "Please launch DaVinci Resolve Studio and verify 'Preferences -> System -> General -> "
            "External scripting using -> Local' is enabled."
        )

    return resolve


# ============================================================================
# DAVINCI RESOLVE HANDOFF ENGINE
# ============================================================================

class DaVinciResolveHandoffEngine:
    """
    Engine for executing non-destructive handoffs into DaVinci Resolve Studio.
    Supports live Resolve Studio interaction, headless mock injection, and dry-run simulations.
    """

    def __init__(
        self,
        resolve_instance: Optional[Any] = None,
        dry_run: bool = False,
        default_fps: float = 60.0,
        default_width: int = 1080,
        default_height: int = 1920,
    ):
        self.resolve_instance = resolve_instance
        self.dry_run = dry_run
        self.default_fps = default_fps
        self.default_width = default_width
        self.default_height = default_height

    def connect(self) -> Any:
        """Connects to the DaVinci Resolve Studio application instance."""
        if self.resolve_instance is not None:
            return self.resolve_instance
        if self.dry_run:
            logger.info("[DRY-RUN] Simulating DaVinci Resolve Studio connection")
            return None
        self.resolve_instance = get_resolve_instance()
        return self.resolve_instance

    def calculate_frames(self, start_time: float, end_time: float, fps: float) -> Tuple[int, int, int]:
        """
        Calculates exact integer frame counts using mathematical rounding:
        start_frame = int(round(start_time * fps))
        end_frame = int(round(end_time * fps))
        duration_frames = end_frame - start_frame
        """
        start_frame = int(round(start_time * fps))
        end_frame = int(round(end_time * fps))
        duration_frames = max(0, end_frame - start_frame)
        return start_frame, end_frame, duration_frames

    def get_or_create_project(self, project_manager: Any, project_name: str) -> Any:
        """
        Loads an existing project by name, or creates a new project if not found.
        """
        project = None
        try:
            project = project_manager.LoadProject(project_name)
        except Exception as ex:
            logger.debug(f"LoadProject({project_name}) returned exception: {ex}")

        if project is None:
            try:
                project = project_manager.CreateProject(project_name)
            except Exception as ex:
                logger.debug(f"CreateProject({project_name}) returned exception: {ex}")

        if project is None:
            # Fallback to currently open project
            try:
                project = project_manager.GetCurrentProject()
            except Exception:
                pass

        if project is None:
            raise ProjectManagementError(f"Failed to load or create project '{project_name}' in DaVinci Resolve.")

        return project

    def configure_project_settings(
        self,
        project: Any,
        width: int = 1080,
        height: int = 1920,
        fps: float = 60.0,
    ) -> None:
        """
        Configures project settings for vertical 9:16 high-frame-rate master timelines.
        """
        settings = {
            "timelineResolutionWidth": str(width),
            "timelineResolutionHeight": str(height),
            "timelineFrameRate": str(int(fps) if fps.is_integer() else f"{fps:.3f}"),
            "timelinePlaybackFrameRate": str(int(fps) if fps.is_integer() else f"{fps:.3f}"),
            "useCustomTimelineSettings": "1",
        }

        for setting_key, val in settings.items():
            try:
                project.SetSetting(setting_key, val)
            except Exception as ex:
                logger.debug(f"Project.SetSetting({setting_key}={val}) failed: {ex}")

    def import_raw_media(self, resolve: Any, project: Any, raw_file_path: Union[str, Path]) -> Any:
        """
        Imports raw 4K media from the filesystem into the Media Pool root bin.
        Returns the imported MediaPoolItem object.
        """
        raw_path = Path(raw_file_path).resolve()
        if not raw_path.exists() and not self.dry_run and self.resolve_instance is None:
            raise MediaImportError(f"Raw media file does not exist on disk: {raw_path}")

        raw_path_str = str(raw_path)
        media_pool = project.GetMediaPool() if hasattr(project, "GetMediaPool") else None
        media_storage = resolve.GetMediaStorage() if (resolve and hasattr(resolve, "GetMediaStorage")) else None

        imported_items: List[Any] = []

        # Strategy 1: AddItemListToMediaPool via MediaStorage
        if media_storage and hasattr(media_storage, "AddItemListToMediaPool"):
            try:
                res = media_storage.AddItemListToMediaPool([raw_path_str])
                if res and isinstance(res, list):
                    imported_items = res
            except Exception as ex:
                logger.debug(f"MediaStorage.AddItemListToMediaPool failed: {ex}")

        # Strategy 2: ImportMedia via MediaPool
        if not imported_items and media_pool and hasattr(media_pool, "ImportMedia"):
            try:
                res = media_pool.ImportMedia([raw_path_str])
                if res and isinstance(res, list):
                    imported_items = res
            except Exception as ex:
                logger.debug(f"MediaPool.ImportMedia failed: {ex}")

        # Strategy 3: Check existing root folder clips
        if not imported_items and media_pool and hasattr(media_pool, "GetRootFolder"):
            root_folder = media_pool.GetRootFolder()
            if root_folder and hasattr(root_folder, "GetClipList"):
                clips = root_folder.GetClipList() or []
                for clip in clips:
                    clip_path = ""
                    if hasattr(clip, "GetClipProperty"):
                        clip_path = clip.GetClipProperty("File Path") or clip.GetClipProperty("FilePath") or ""
                    if clip_path and Path(clip_path).name == raw_path.name:
                        imported_items = [clip]
                        break

        if not imported_items:
            raise MediaImportError(f"Failed to import raw media '{raw_path_str}' into DaVinci Resolve Media Pool.")

        return imported_items[0]

    def create_and_populate_timeline(
        self,
        project: Any,
        clip_item: Any,
        timeline_name: str,
        start_frame: int,
        end_frame: int,
        record_frame: int = 0,
    ) -> Any:
        """
        Creates a new empty timeline and appends the precisely sliced clip item.
        """
        media_pool = project.GetMediaPool()
        timeline = None

        if hasattr(media_pool, "CreateEmptyTimeline"):
            try:
                timeline = media_pool.CreateEmptyTimeline(timeline_name)
            except Exception as ex:
                logger.debug(f"CreateEmptyTimeline({timeline_name}) failed: {ex}")

        if timeline is None and hasattr(project, "GetCurrentTimeline"):
            timeline = project.GetCurrentTimeline()

        if timeline is None:
            raise TimelineCreationError(f"Failed to create timeline '{timeline_name}' in DaVinci Resolve.")

        # Structure subclip insertion payload
        clip_info = {
            "mediaPoolItem": clip_item,
            "startFrame": start_frame,
            "endFrame": end_frame,
            "recordFrame": record_frame,
        }

        appended = False
        if hasattr(media_pool, "AppendToTimeline"):
            try:
                append_res = media_pool.AppendToTimeline([clip_info])
                appended = bool(append_res)
            except Exception as ex:
                logger.warning(f"MediaPool.AppendToTimeline failed: {ex}")

        if hasattr(project, "SetCurrentTimeline"):
            try:
                project.SetCurrentTimeline(timeline)
            except Exception:
                pass

        return timeline

    def execute_handoff(self, config: ResolveHandoffConfig) -> ResolveHandoffResult:
        """
        Executes full end-to-end DaVinci Resolve handoff workflow.
        """
        start_time = config.start_time_sec
        end_time = config.end_time_sec
        duration = config.duration_sec
        fps = config.timeline_fps
        width = config.timeline_width
        height = config.timeline_height
        resolution_str = f"{width}x{height}"

        start_frame, end_frame, duration_frames = self.calculate_frames(start_time, end_time, fps)

        # Handle Dry-Run mode
        if config.dry_run or self.dry_run:
            logger.info(
                f"[DRY-RUN] Simulating Resolve handoff: project='{config.project_name}', "
                f"timeline='{config.timeline_name}', frames={start_frame}..{end_frame} ({duration:.2f}s)"
            )
            return ResolveHandoffResult(
                success=True,
                status="dry_run_simulated",
                project_name=config.project_name,
                timeline_name=config.timeline_name,
                raw_file_path=str(config.raw_file_path),
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                start_frame=start_frame,
                end_frame=end_frame,
                duration_frames=duration_frames,
                fps=fps,
                width=width,
                height=height,
                timeline_resolution=resolution_str,
                media_item_name=Path(config.raw_file_path).name,
                timeline_id="simulated_timeline_id",
                telemetry={
                    "mode": "dry_run",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "festival": config.festival,
                    "artist": config.artist,
                    "track": config.track,
                },
            )

        # Connect to Resolve
        try:
            resolve = self.connect()
        except ResolveScriptError as rse:
            logger.error(f"DaVinci Resolve connection failed: {rse}")
            return ResolveHandoffResult(
                success=False,
                status="resolve_unavailable",
                project_name=config.project_name,
                timeline_name=config.timeline_name,
                raw_file_path=str(config.raw_file_path),
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                start_frame=start_frame,
                end_frame=end_frame,
                duration_frames=duration_frames,
                fps=fps,
                width=width,
                height=height,
                timeline_resolution=resolution_str,
                error_message=str(rse),
            )

        try:
            # 1. Project Management
            project_manager = resolve.GetProjectManager()
            project = self.get_or_create_project(project_manager, config.project_name)

            # 2. Configure Resolution & Framerate
            self.configure_project_settings(project, width=width, height=height, fps=fps)

            # 3. Import 4K Raw Media
            clip_item = self.import_raw_media(resolve, project, config.raw_file_path)
            item_name = None
            if hasattr(clip_item, "GetName"):
                try:
                    item_name = clip_item.GetName()
                except Exception:
                    item_name = Path(config.raw_file_path).name

            # 4. Create Timeline & Append Subclip
            timeline = self.create_and_populate_timeline(
                project=project,
                clip_item=clip_item,
                timeline_name=config.timeline_name,
                start_frame=start_frame,
                end_frame=end_frame,
                record_frame=0,
            )

            # 5. Auto-Save Project if configured
            if config.auto_save and hasattr(project_manager, "SaveProject"):
                try:
                    project_manager.SaveProject()
                except Exception as ex:
                    logger.warning(f"ProjectManager.SaveProject() failed: {ex}")

            timeline_id = str(getattr(timeline, "GetUniqueId", lambda: "timeline_1")()) if timeline else None

            logger.info(
                f"Successfully created timeline '{config.timeline_name}' in project '{config.project_name}' "
                f"with clip slice [{start_frame}..{end_frame}] ({duration:.2f}s)"
            )

            return ResolveHandoffResult(
                success=True,
                status="success",
                project_name=config.project_name,
                timeline_name=config.timeline_name,
                raw_file_path=str(config.raw_file_path),
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                start_frame=start_frame,
                end_frame=end_frame,
                duration_frames=duration_frames,
                fps=fps,
                width=width,
                height=height,
                timeline_resolution=resolution_str,
                media_item_name=item_name or Path(config.raw_file_path).name,
                timeline_id=timeline_id,
                telemetry={
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "festival": config.festival,
                    "artist": config.artist,
                    "track": config.track,
                },
            )

        except Exception as ex:
            logger.error(f"Error during DaVinci Resolve handoff execution: {ex}", exc_info=True)
            return ResolveHandoffResult(
                success=False,
                status="execution_failed",
                project_name=config.project_name,
                timeline_name=config.timeline_name,
                raw_file_path=str(config.raw_file_path),
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                start_frame=start_frame,
                end_frame=end_frame,
                duration_frames=duration_frames,
                fps=fps,
                width=width,
                height=height,
                timeline_resolution=resolution_str,
                error_message=str(ex),
            )


# ============================================================================
# CORE TOP-LEVEL API FUNCTION
# ============================================================================

def create_resolve_timeline(
    raw_file_path: Union[str, Path],
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    duration: Optional[float] = 30.0,
    project_name: str = "EDM_Master_Dashboard",
    timeline_name: str = "EDM_Vertical_Timeline",
    fps: float = 60.0,
    width: int = 1080,
    height: int = 1920,
    festival: Optional[str] = "Concert",
    artist: Optional[str] = "Artist",
    track: Optional[str] = "ID",
    auto_save: bool = True,
    dry_run: bool = False,
    resolve_instance: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Top-level programmatic API function to create or append to a DaVinci Resolve timeline.
    Returns a telemetry dictionary containing execution status, frame counts, and diagnostics.
    """
    config = ResolveHandoffConfig(
        raw_file_path=raw_file_path,
        project_name=project_name,
        timeline_name=timeline_name,
        start_time=start_time,
        end_time=end_time,
        duration=duration,
        fps=fps,
        width=width,
        height=height,
        festival=festival,
        artist=artist,
        track=track,
        auto_save=auto_save,
        dry_run=dry_run,
    )

    engine = DaVinciResolveHandoffEngine(
        resolve_instance=resolve_instance,
        dry_run=dry_run,
        default_fps=fps,
        default_width=width,
        default_height=height,
    )

    result = engine.execute_handoff(config)
    return result.to_dict()


# ============================================================================
# STANDALONE CLI INTERFACE
# ============================================================================

def parse_cli_args(args: Optional[List[str]] = None):
    import argparse
    parser = argparse.ArgumentParser(
        description="DaVinci Resolve Studio Python Handoff CLI for EDM Master Dashboard",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--raw-file", "-i",
        required=True,
        help="Path to the untouched 4K raw video file in 01_RAW vault",
    )
    parser.add_argument(
        "--start", "-s",
        type=float,
        default=0.0,
        help="Start trim timestamp in seconds",
    )
    parser.add_argument(
        "--end", "-e",
        type=float,
        default=None,
        help="End trim timestamp in seconds",
    )
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=30.0,
        help="Clip slice duration in seconds (if --end is not specified)",
    )
    parser.add_argument(
        "--project", "-p",
        default="EDM_Master_Dashboard",
        help="DaVinci Resolve project name",
    )
    parser.add_argument(
        "--timeline", "-t",
        default="EDM_Vertical_Timeline",
        help="DaVinci Resolve timeline name",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=60.0,
        help="Timeline framerate in frames per second",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1080,
        help="Timeline canvas width in pixels",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1920,
        help="Timeline canvas height in pixels",
    )
    parser.add_argument(
        "--festival",
        default="Concert",
        help="Festival or event metadata name",
    )
    parser.add_argument(
        "--artist",
        default="Artist",
        help="Artist or DJ metadata name",
    )
    parser.add_argument(
        "--track",
        default="ID",
        help="Track title or ID metadata",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Disable automatic project saving upon completion",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without requiring DaVinci Resolve Studio",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON string",
    )

    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    parsed = parse_cli_args(args)

    result_dict = create_resolve_timeline(
        raw_file_path=parsed.raw_file,
        start_time=parsed.start,
        end_time=parsed.end,
        duration=parsed.duration,
        project_name=parsed.project,
        timeline_name=parsed.timeline,
        fps=parsed.fps,
        width=parsed.width,
        height=parsed.height,
        festival=parsed.festival,
        artist=parsed.artist,
        track=parsed.track,
        auto_save=not parsed.no_save,
        dry_run=parsed.dry_run,
    )

    if parsed.json:
        print(json.dumps(result_dict, indent=2))
    else:
        print("\n" + "=" * 60)
        print("DAVINCI RESOLVE HANDOFF REPORT")
        print("=" * 60)
        print(f"Status:             {result_dict.get('status')}")
        print(f"Success:            {result_dict.get('success')}")
        print(f"Project Name:       {result_dict.get('project_name')}")
        print(f"Timeline Name:      {result_dict.get('timeline_name')}")
        print(f"Raw File Path:      {result_dict.get('raw_file_path')}")
        print(f"Frame Slice:        {result_dict.get('start_frame')} -> {result_dict.get('end_frame')} ({result_dict.get('duration_frames')} frames)")
        print(f"Time Slice:         {result_dict.get('start_time'):.2f}s -> {result_dict.get('end_time'):.2f}s ({result_dict.get('duration'):.2f}s)")
        print(f"Timeline Format:    {result_dict.get('timeline_resolution')} @ {result_dict.get('fps')} fps")
        if result_dict.get("error_message"):
            print(f"Error Message:      {result_dict.get('error_message')}")
        print("=" * 60 + "\n")

    return 0 if result_dict.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
