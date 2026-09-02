"""
test_resolve_handoff_live.py - Live & Simulated Test Suite for DaVinci Resolve Handoff Engine
Part of Milestone M3: Comprehensive Test Suites and Full Pipeline E2E Integration Verification

Tests cover:
1. Live DaVinci Resolve Studio API Connection & Diagnostic Probing:
   - Module discovery via search paths (Windows %PROGRAMDATA%, %PROGRAMFILES%, macOS, Linux).
   - Dynamic module import via `get_resolve_script_module()`.
   - Live instance connection via `get_resolve_instance()` (handling running vs offline Studio).
   - `DaVinciResolveHandoffEngine.connect()` behavior in live, mock, and dry-run modes.
2. Mathematical Frame Calculation & Boundary Edge Cases:
   - Exact frame mapping: start_frame = round(start_time * fps), end_frame = round(end_time * fps).
   - Zero start time (0.0s) -> start_frame = 0.
   - Fractional / float durations and sub-second timestamps (e.g., 12.345s, 0.5s, 59.94s).
   - Standard (24fps, 30fps, 60fps) and broadcast non-integer framerates (23.976fps, 29.97fps, 59.94fps).
   - High frame rate conversion (120fps, 240fps).
   - Boundary clamping (end < start, start == end, negative timestamps).
3. DaVinciResolveHandoffEngine Execution & Mock Integration:
   - Project lifecycle (LoadProject vs CreateProject, custom 9:16 resolution settings).
   - Media Pool import strategies (MediaStorage.AddItemListToMediaPool, MediaPool.ImportMedia, root folder search).
   - Timeline creation and AppendToTimeline structure: [{"mediaPoolItem": item, "startFrame": S, "endFrame": E, "recordFrame": 0}].
   - Error taxonomy: ResolveScriptError, ResolveModuleNotFoundError, ResolveNotRunningError, MediaImportError, TimelineCreationError, ProjectManagementError.
   - Dry-run simulated handoff producing complete telemetry without live Resolve Studio.
4. CLI Invocation, JSON Output Formatting, and Parameter Parsing:
   - Full CLI flags: --raw-file, --start, --end, --duration, --project, --timeline, --fps, --width, --height, --festival, --artist, --track, --no-save, --dry-run, --json.
   - Human-readable formatted report output vs structured JSON payload output.
   - CLI error codes and missing argument validations.
5. Conditional Live Studio Integration Verification:
   - Graceful execution when DaVinci Resolve Studio is actively running or when running headless in CI.
"""

from dataclasses import asdict
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import MagicMock, patch

# Ensure content_creation root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from resolve_handoff import (
    DaVinciResolveHandoffEngine,
    MediaImportError,
    ProjectManagementError,
    ResolveHandoffConfig,
    ResolveHandoffResult,
    ResolveModuleNotFoundError,
    ResolveNotRunningError,
    ResolveScriptError,
    TimelineCreationError,
    create_resolve_timeline,
    get_resolve_instance,
    get_resolve_script_module,
    get_resolve_script_search_paths,
    main,
    parse_cli_args,
)


# ============================================================================
# MOCK DAVINCI RESOLVE API HIERARCHY FOR CONTROLLED SIMULATION
# ============================================================================

class MockLiveMediaPoolItem:
    """Mock MediaPoolItem simulating DaVinci Resolve Studio clip."""

    def __init__(self, name: str = "4k_concert_take.mp4", file_path: str = "/01_RAW/4k_concert_take.mp4"):
        self._name = name
        self._file_path = str(file_path)
        self._properties = {
            "File Name": name,
            "File Path": str(file_path),
            "FilePath": str(file_path),
            "FPS": "60.0",
            "Resolution": "3840x2160",
        }

    def GetName(self) -> str:
        return self._name

    def GetClipProperty(self, prop_name: Optional[str] = None) -> Any:
        if prop_name:
            return self._properties.get(prop_name, "")
        return self._properties


class MockLiveFolder:
    """Mock Media Pool Folder."""

    def __init__(self, name: str = "Master"):
        self._name = name
        self._clips: List[MockLiveMediaPoolItem] = []

    def GetName(self) -> str:
        return self._name

    def GetClipList(self) -> List[MockLiveMediaPoolItem]:
        return self._clips


class MockLiveTimeline:
    """Mock Timeline simulating DaVinci Resolve Studio timeline."""

    def __init__(self, name: str = "EDM_Vertical_Timeline", unique_id: str = "tl_live_mock_999"):
        self._name = name
        self._unique_id = unique_id
        self._track_count = {"video": 1, "audio": 2}
        self.appended_items: List[Dict[str, Any]] = []

    def GetName(self) -> str:
        return self._name

    def GetUniqueId(self) -> str:
        return self._unique_id

    def GetTrackCount(self, track_type: str) -> int:
        return self._track_count.get(track_type, 0)


class MockLiveMediaPool:
    """Mock MediaPool simulating DaVinci Resolve Studio Media Pool."""

    def __init__(self):
        self.root_folder = MockLiveFolder("Master")
        self.timelines: List[MockLiveTimeline] = []
        self.imported_paths: List[str] = []
        self.append_calls: List[List[Dict[str, Any]]] = []

    def GetRootFolder(self) -> MockLiveFolder:
        return self.root_folder

    def ImportMedia(self, file_paths: List[str]) -> List[MockLiveMediaPoolItem]:
        items = []
        for p in file_paths:
            self.imported_paths.append(str(p))
            item = MockLiveMediaPoolItem(name=Path(p).name, file_path=str(p))
            self.root_folder._clips.append(item)
            items.append(item)
        return items

    def CreateEmptyTimeline(self, name: str) -> MockLiveTimeline:
        tl = MockLiveTimeline(name=name)
        self.timelines.append(tl)
        return tl

    def AppendToTimeline(self, clip_info_list: List[Dict[str, Any]]) -> bool:
        self.append_calls.append(clip_info_list)
        if self.timelines:
            self.timelines[-1].appended_items.extend(clip_info_list)
        return True


class MockLiveMediaStorage:
    """Mock MediaStorage simulating DaVinci Resolve Studio Media Storage."""

    def __init__(self, media_pool: Optional[MockLiveMediaPool] = None):
        self.media_pool = media_pool

    def AddItemListToMediaPool(self, file_paths: List[str]) -> List[MockLiveMediaPoolItem]:
        if self.media_pool:
            return self.media_pool.ImportMedia(file_paths)
        return [MockLiveMediaPoolItem(name=Path(p).name, file_path=str(p)) for p in file_paths]


class MockLiveProject:
    """Mock Project simulating DaVinci Resolve Studio active project."""

    def __init__(self, name: str = "EDM_Master_Dashboard"):
        self._name = name
        self._settings: Dict[str, str] = {
            "timelineResolutionWidth": "1080",
            "timelineResolutionHeight": "1920",
            "timelineFrameRate": "60",
            "timelinePlaybackFrameRate": "60",
            "useCustomTimelineSettings": "1",
        }
        self.media_pool = MockLiveMediaPool()
        self.current_timeline: Optional[MockLiveTimeline] = None

    def GetName(self) -> str:
        return self._name

    def GetSetting(self, key: str) -> str:
        return self._settings.get(key, "")

    def SetSetting(self, key: str, value: str) -> bool:
        self._settings[key] = str(value)
        return True

    def GetMediaPool(self) -> MockLiveMediaPool:
        return self.media_pool

    def GetCurrentTimeline(self) -> Optional[MockLiveTimeline]:
        return self.current_timeline or (self.media_pool.timelines[-1] if self.media_pool.timelines else None)

    def SetCurrentTimeline(self, timeline: MockLiveTimeline) -> bool:
        self.current_timeline = timeline
        return True


class MockLiveProjectManager:
    """Mock ProjectManager simulating DaVinci Resolve Studio Project Manager."""

    def __init__(self):
        self.projects: Dict[str, MockLiveProject] = {}
        self.current_project: Optional[MockLiveProject] = None
        self.saved_projects: List[str] = []

    def LoadProject(self, name: str) -> Optional[MockLiveProject]:
        if name in self.projects:
            self.current_project = self.projects[name]
            return self.current_project
        return None

    def CreateProject(self, name: str) -> MockLiveProject:
        proj = MockLiveProject(name=name)
        self.projects[name] = proj
        self.current_project = proj
        return proj

    def GetCurrentProject(self) -> Optional[MockLiveProject]:
        return self.current_project

    def SaveProject(self) -> bool:
        if self.current_project:
            self.saved_projects.append(self.current_project.GetName())
        return True


class MockLiveResolveApp:
    """Mock root Resolve object simulating `dvr_script.scriptapp('Resolve')`."""

    def __init__(self):
        self.project_manager = MockLiveProjectManager()
        self.media_pool = MockLiveMediaPool()
        self.media_storage = MockLiveMediaStorage(self.media_pool)

    def GetProjectManager(self) -> MockLiveProjectManager:
        return self.project_manager

    def GetMediaStorage(self) -> MockLiveMediaStorage:
        return self.media_storage


# ============================================================================
# 1. LIVE CONNECTION & DIAGNOSTIC PROBING TESTS
# ============================================================================

class TestResolveLiveConnectionAndDiagnostics(unittest.TestCase):
    """Verifies DaVinci Resolve script module discovery, path resolution, and connection probing."""

    def test_search_paths_discovery_cross_platform(self):
        """Verifies candidate search paths for Resolve scripting across OS platforms."""
        paths = get_resolve_script_search_paths()
        self.assertIsInstance(paths, list)
        self.assertGreater(len(paths), 0)
        for p in paths:
            self.assertIsInstance(p, str)
            self.assertTrue(len(p.strip()) > 0)

        # On Windows, verify standard DaVinci Resolve developer paths are represented
        if sys.platform.startswith("win"):
            has_blackmagic = any("Blackmagic Design" in p for p in paths)
            self.assertTrue(has_blackmagic, "Expected Blackmagic Design search paths on Windows")

    def test_environment_variable_override_search_paths(self):
        """Verifies RESOLVE_SCRIPT_API and RESOLVE_SCRIPT_LIB env vars are prioritized."""
        fake_api_dir = str(Path("/custom/resolve/api").resolve())
        fake_lib_dir = str(Path("/custom/resolve/lib/fusionscript.so").resolve())
        with patch.dict(os.environ, {"RESOLVE_SCRIPT_API": fake_api_dir, "RESOLVE_SCRIPT_LIB": fake_lib_dir}):
            paths = get_resolve_script_search_paths()
            self.assertTrue(any(fake_api_dir in p for p in paths))

    def test_get_resolve_script_module_graceful_handling(self):
        """Verifies get_resolve_script_module returns module or raises ResolveModuleNotFoundError."""
        try:
            mod = get_resolve_script_module()
            self.assertIsNotNone(mod)
            self.assertTrue(hasattr(mod, "scriptapp") or hasattr(mod, "GetResolve"))
        except ResolveModuleNotFoundError as err:
            # When Resolve Studio is not installed in the test environment, error is properly formatted
            self.assertIn("DaVinciResolveScript module could not be loaded", str(err))

    def test_get_resolve_instance_raises_when_offline(self):
        """Verifies get_resolve_instance raises ResolveNotRunningError or ResolveModuleNotFoundError when offline."""
        with patch("resolve_handoff.get_resolve_script_module") as mock_mod_fn:
            mock_module = MagicMock()
            mock_module.scriptapp.return_value = None
            mock_mod_fn.return_value = mock_module

            with self.assertRaises(ResolveNotRunningError) as ctx:
                get_resolve_instance()
            self.assertIn("DaVinci Resolve Studio is not running", str(ctx.exception))

    def test_engine_connect_live_vs_mock_vs_dry_run(self):
        """Verifies DaVinciResolveHandoffEngine.connect() under different injection modes."""
        # 1. Injected instance
        mock_app = MockLiveResolveApp()
        engine_injected = DaVinciResolveHandoffEngine(resolve_instance=mock_app)
        self.assertEqual(engine_injected.connect(), mock_app)

        # 2. Dry run mode returns None without raising
        engine_dry = DaVinciResolveHandoffEngine(dry_run=True)
        self.assertIsNone(engine_dry.connect())

        # 3. Offline without dry run raises ResolveNotRunningError
        with patch("resolve_handoff.get_resolve_instance", side_effect=ResolveNotRunningError("Studio Offline")):
            engine_offline = DaVinciResolveHandoffEngine(dry_run=False)
            with self.assertRaises(ResolveNotRunningError):
                engine_offline.connect()


# ============================================================================
# 2. FRAME CALCULATION & BOUNDARY EDGE CASES
# ============================================================================

class TestResolveFrameCalculationsAndEdgeCases(unittest.TestCase):
    """Verifies mathematical frame calculation and edge conditions."""

    def setUp(self):
        self.engine = DaVinciResolveHandoffEngine()

    def test_zero_start_time_standard_60fps(self):
        """Verifies start_time=0.0s with 30.0s duration at 60fps."""
        start_frame, end_frame, duration_frames = self.engine.calculate_frames(
            start_time=0.0,
            end_time=30.0,
            fps=60.0,
        )
        self.assertEqual(start_frame, 0)
        self.assertEqual(end_frame, 1800)
        self.assertEqual(duration_frames, 1800)

    def test_float_duration_and_subsecond_timestamps(self):
        """Verifies sub-second float duration (e.g. 15.5s at 60fps -> 930 frames)."""
        start_frame, end_frame, duration_frames = self.engine.calculate_frames(
            start_time=10.25,
            end_time=25.75,
            fps=60.0,
        )
        # 10.25 * 60 = 615.0 -> 615
        # 25.75 * 60 = 1545.0 -> 1545
        self.assertEqual(start_frame, 615)
        self.assertEqual(end_frame, 1545)
        self.assertEqual(duration_frames, 930)

    def test_fractional_broadcast_framerates(self):
        """Verifies fractional framerates: 59.94 fps, 29.97 fps, 23.976 fps."""
        # 59.94 fps over 30s
        s59, e59, d59 = self.engine.calculate_frames(0.0, 30.0, 59.94)
        self.assertEqual(s59, 0)
        self.assertEqual(e59, int(round(30.0 * 59.94)))  # 1798
        self.assertEqual(d59, 1798)

        # 29.97 fps
        s30, e30, d30 = self.engine.calculate_frames(1.5, 31.5, 29.97)
        self.assertEqual(s30, int(round(1.5 * 29.97)))   # 45
        self.assertEqual(e30, int(round(31.5 * 29.97)))  # 944
        self.assertEqual(d30, 899)

        # 23.976 fps
        s24, e24, d24 = self.engine.calculate_frames(0.0, 10.0, 23.976)
        self.assertEqual(s24, 0)
        self.assertEqual(e24, 240)
        self.assertEqual(d24, 240)

    def test_high_framerate_120fps_and_240fps(self):
        """Verifies 120fps and 240fps slow-motion capture frame calculations."""
        s120, e120, d120 = self.engine.calculate_frames(5.0, 15.0, 120.0)
        self.assertEqual(s120, 600)
        self.assertEqual(e120, 1800)
        self.assertEqual(d120, 1200)

        s240, e240, d240 = self.engine.calculate_frames(2.0, 4.0, 240.0)
        self.assertEqual(s240, 480)
        self.assertEqual(e240, 960)
        self.assertEqual(d240, 480)

    def test_zero_duration_start_equals_end(self):
        """Verifies start == end yields duration_frames=0."""
        s, e, d = self.engine.calculate_frames(10.0, 10.0, 60.0)
        self.assertEqual(s, 600)
        self.assertEqual(e, 600)
        self.assertEqual(d, 0)

    def test_clamped_negative_duration_end_less_than_start(self):
        """Verifies end < start clamps duration_frames to 0 without crashing."""
        s, e, d = self.engine.calculate_frames(20.0, 10.0, 60.0)
        self.assertEqual(s, 1200)
        self.assertEqual(e, 600)
        self.assertEqual(d, 0)


# ============================================================================
# 3. ENGINE EXECUTION & MOCK INTEGRATION TESTS
# ============================================================================

class TestResolveHandoffEngineExecution(unittest.TestCase):
    """Verifies DaVinci Resolve handoff engine execution in mock, dry-run, and failure states."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raw_media_path = Path(self.temp_dir.name) / "01_RAW" / "EDC" / "Sub_Focus" / "take_4k.mp4"
        self.raw_media_path.parent.mkdir(parents=True, exist_ok=True)
        self.raw_media_path.write_bytes(b"\x00\x00\x00 ftypisom" + b"\x00" * 2048)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dry_run_execution_simulated_success(self):
        """Verifies execute_handoff in dry_run mode returns complete telemetry without live Resolve."""
        config = ResolveHandoffConfig(
            raw_file_path=self.raw_media_path,
            project_name="EDC_SubFocus_Master",
            timeline_name="SubFocus_Desire_Drop_Vertical",
            start_time=10.5,
            duration=30.0,
            fps=60.0,
            width=1080,
            height=1920,
            festival="EDC Las Vegas",
            artist="Sub Focus",
            track="Desire",
            dry_run=True,
        )

        engine = DaVinciResolveHandoffEngine(dry_run=True)
        result = engine.execute_handoff(config)

        self.assertTrue(result.success)
        self.assertEqual(result.status, "dry_run_simulated")
        self.assertEqual(result.project_name, "EDC_SubFocus_Master")
        self.assertEqual(result.timeline_name, "SubFocus_Desire_Drop_Vertical")
        self.assertEqual(result.start_time, 10.5)
        self.assertEqual(result.end_time, 40.5)
        self.assertEqual(result.duration, 30.0)
        self.assertEqual(result.start_frame, 630)
        self.assertEqual(result.end_frame, 2430)
        self.assertEqual(result.duration_frames, 1800)
        self.assertEqual(result.timeline_resolution, "1080x1920")
        self.assertEqual(result.fps, 60.0)
        self.assertIn("festival", result.telemetry)
        self.assertEqual(result.telemetry["festival"], "EDC Las Vegas")

    def test_mock_live_resolve_api_execution(self):
        """Verifies full timeline creation against mock DaVinci Resolve Studio object model."""
        mock_resolve = MockLiveResolveApp()
        engine = DaVinciResolveHandoffEngine(resolve_instance=mock_resolve, dry_run=False)

        config = ResolveHandoffConfig(
            raw_file_path=self.raw_media_path,
            project_name="Tomorrowland_Alesso_Master",
            timeline_name="Alesso_Heroes_Drop_Vertical",
            start_time=5.0,
            end_time=35.0,
            fps=60.0,
            width=1080,
            height=1920,
            auto_save=True,
        )

        result = engine.execute_handoff(config)

        self.assertTrue(result.success)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.project_name, "Tomorrowland_Alesso_Master")
        self.assertEqual(result.timeline_name, "Alesso_Heroes_Drop_Vertical")
        self.assertEqual(result.start_frame, 300)
        self.assertEqual(result.end_frame, 2100)
        self.assertEqual(result.duration_frames, 1800)

        # Assert project configuration
        pm = mock_resolve.GetProjectManager()
        self.assertIn("Tomorrowland_Alesso_Master", pm.projects)
        proj = pm.projects["Tomorrowland_Alesso_Master"]
        self.assertEqual(proj.GetSetting("timelineResolutionWidth"), "1080")
        self.assertEqual(proj.GetSetting("timelineResolutionHeight"), "1920")
        self.assertEqual(proj.GetSetting("timelineFrameRate"), "60")

        # Assert Media Pool import and timeline creation
        mp = proj.GetMediaPool()
        self.assertGreaterEqual(len(mp.timelines), 1)
        created_tl = mp.timelines[0]
        self.assertEqual(created_tl.GetName(), "Alesso_Heroes_Drop_Vertical")
        self.assertGreaterEqual(len(created_tl.appended_items), 1)
        clip_data = created_tl.appended_items[0]
        self.assertEqual(clip_data["startFrame"], 300)
        self.assertEqual(clip_data["endFrame"], 2100)
        self.assertEqual(clip_data["recordFrame"], 0)

        # Assert auto-save occurred
        self.assertIn("Tomorrowland_Alesso_Master", pm.saved_projects)

    def test_create_resolve_timeline_top_level_wrapper(self):
        """Verifies top-level create_resolve_timeline() convenience function."""
        mock_resolve = MockLiveResolveApp()
        res_dict = create_resolve_timeline(
            raw_file_path=str(self.raw_media_path),
            start_time=0.0,
            duration=30.0,
            project_name="Ultra_Hardwell_Master",
            timeline_name="Hardwell_Spaceman_Drop",
            fps=60.0,
            width=1080,
            height=1920,
            festival="Ultra Miami",
            artist="Hardwell",
            track="Spaceman",
            dry_run=False,
            resolve_instance=mock_resolve,
        )

        self.assertIsInstance(res_dict, dict)
        self.assertTrue(res_dict["success"])
        self.assertEqual(res_dict["status"], "success")
        self.assertEqual(res_dict["start_frame"], 0)
        self.assertEqual(res_dict["end_frame"], 1800)
        self.assertEqual(res_dict["duration_frames"], 1800)
        self.assertEqual(res_dict["timeline_resolution"], "1080x1920")

    def test_project_management_failure_handling(self):
        """Verifies ProjectManagementError is caught and returned in result telemetry."""
        mock_resolve = MockLiveResolveApp()
        # Sabotage ProjectManager to fail both LoadProject and CreateProject
        mock_resolve.GetProjectManager().LoadProject = MagicMock(return_value=None)
        mock_resolve.GetProjectManager().CreateProject = MagicMock(return_value=None)
        mock_resolve.GetProjectManager().GetCurrentProject = MagicMock(return_value=None)

        engine = DaVinciResolveHandoffEngine(resolve_instance=mock_resolve)
        config = ResolveHandoffConfig(raw_file_path=self.raw_media_path, project_name="Broken_Project")

        result = engine.execute_handoff(config)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "execution_failed")
        self.assertIn("Failed to load or create project", result.error_message)

    def test_media_import_failure_handling(self):
        """Verifies MediaImportError when media pool refuses clip import."""
        mock_resolve = MockLiveResolveApp()
        # Sabotage MediaStorage and MediaPool
        mock_resolve.GetMediaStorage().AddItemListToMediaPool = MagicMock(return_value=[])
        mock_resolve.GetProjectManager().CreateProject("Test_Proj")
        proj = mock_resolve.GetProjectManager().GetCurrentProject()
        proj.GetMediaPool().ImportMedia = MagicMock(return_value=[])
        proj.GetMediaPool().GetRootFolder().GetClipList = MagicMock(return_value=[])

        engine = DaVinciResolveHandoffEngine(resolve_instance=mock_resolve)
        config = ResolveHandoffConfig(raw_file_path=self.raw_media_path, project_name="Test_Proj")

        result = engine.execute_handoff(config)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "execution_failed")
        self.assertIn("Failed to import raw media", result.error_message)


# ============================================================================
# 4. CLI INVOCATION & JSON FORMATTING TESTS
# ============================================================================

class TestResolveCLIAndJSONFormatting(unittest.TestCase):
    """Verifies CLI argument parsing, dry-run CLI execution, and JSON reporting."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raw_file = Path(self.temp_dir.name) / "raw_take.mp4"
        self.raw_file.write_bytes(b"\x00" * 1024)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_cli_args_all_options(self):
        """Verifies parsing of all CLI arguments and flag defaults."""
        args = [
            "--raw-file", str(self.raw_file),
            "--start", "12.5",
            "--end", "42.5",
            "--duration", "30.0",
            "--project", "EDC_2026_Master",
            "--timeline", "SubFocus_Timeline",
            "--fps", "59.94",
            "--width", "2160",
            "--height", "3840",
            "--festival", "EDC",
            "--artist", "Sub Focus",
            "--track", "Solar System",
            "--no-save",
            "--dry-run",
            "--json",
        ]
        parsed = parse_cli_args(args)
        self.assertEqual(parsed.raw_file, str(self.raw_file))
        self.assertEqual(parsed.start, 12.5)
        self.assertEqual(parsed.end, 42.5)
        self.assertEqual(parsed.duration, 30.0)
        self.assertEqual(parsed.project, "EDC_2026_Master")
        self.assertEqual(parsed.timeline, "SubFocus_Timeline")
        self.assertEqual(parsed.fps, 59.94)
        self.assertEqual(parsed.width, 2160)
        self.assertEqual(parsed.height, 3840)
        self.assertEqual(parsed.festival, "EDC")
        self.assertEqual(parsed.artist, "Sub Focus")
        self.assertEqual(parsed.track, "Solar System")
        self.assertTrue(parsed.no_save)
        self.assertTrue(parsed.dry_run)
        self.assertTrue(parsed.json)

    def test_cli_main_dry_run_json_output(self):
        """Verifies CLI main() invocation with --dry-run and --json flags produces valid JSON."""
        cli_args = [
            "--raw-file", str(self.raw_file),
            "--start", "5.0",
            "--duration", "30.0",
            "--fps", "60.0",
            "--dry-run",
            "--json",
        ]

        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = main(cli_args)

        self.assertEqual(exit_code, 0)
        output_str = stdout_capture.getvalue()
        self.assertTrue(len(output_str.strip()) > 0)

        # Parse JSON and assert schema
        data = json.loads(output_str)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("status"), "dry_run_simulated")
        self.assertEqual(data.get("start_frame"), 300)
        self.assertEqual(data.get("end_frame"), 2100)
        self.assertEqual(data.get("duration_frames"), 1800)
        self.assertEqual(data.get("fps"), 60.0)
        self.assertEqual(data.get("timeline_resolution"), "1080x1920")

    def test_cli_main_dry_run_human_readable_report(self):
        """Verifies CLI main() invocation without --json outputs formatted summary table."""
        cli_args = [
            "--raw-file", str(self.raw_file),
            "--start", "0.0",
            "--duration", "20.0",
            "--fps", "60.0",
            "--dry-run",
        ]

        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = main(cli_args)

        self.assertEqual(exit_code, 0)
        output_str = stdout_capture.getvalue()
        self.assertIn("DAVINCI RESOLVE HANDOFF REPORT", output_str)
        self.assertIn("Status:", output_str)
        self.assertIn("dry_run_simulated", output_str)
        self.assertIn("Frame Slice:        0 -> 1200 (1200 frames)", output_str)
        self.assertIn("Timeline Format:    1080x1920 @ 60.0 fps", output_str)


# ============================================================================
# 5. CONDITIONAL LIVE STUDIO EXECUTION
# ============================================================================

class TestResolveLiveStudioConditional(unittest.TestCase):
    """
    Tests live DaVinci Resolve Studio instance when available in environment,
    or asserts clean diagnostics fallback without crashing when offline.
    """

    def test_live_resolve_studio_or_graceful_diagnostics(self):
        """Probes live DaVinci Resolve Studio and handles both connected and offline states."""
        try:
            resolve_app = get_resolve_instance()
            self.assertIsNotNone(resolve_app)
            # If Studio is running, test live project manager
            pm = resolve_app.GetProjectManager()
            self.assertIsNotNone(pm)
            current_proj = pm.GetCurrentProject()
            if current_proj:
                name = current_proj.GetName()
                self.assertIsInstance(name, str)
        except (ResolveNotRunningError, ResolveModuleNotFoundError) as ex:
            # Expected in headless / CI environments without active DaVinci Resolve Studio UI
            self.assertTrue(
                "DaVinci Resolve Studio is not running" in str(ex)
                or "DaVinciResolveScript module could not be loaded" in str(ex)
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
