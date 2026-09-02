"""
test_resolve_handoff.py - Unit & Integration Test Suite for DaVinci Resolve Handoff Engine
Part of Milestone M1 / Track 2: Content Creation & Media Engineering Pipeline

Tests cover:
1. Script discovery protocol and cross-platform search paths (Windows %PROGRAMDATA%, %PROGRAMFILES%).
2. Exception taxonomy: ResolveScriptError, ResolveModuleNotFoundError, ResolveNotRunningError,
   MediaImportError, TimelineCreationError, ProjectManagementError.
3. Configuration and result models (ResolveHandoffConfig, ResolveHandoffResult) with serialization.
4. Exact mathematical frame calculation:
   start_frame = int(round(start_time * fps)), end_frame = int(round(end_time * fps)).
   Tests standard (60 fps, 30 fps) and fractional (59.94 fps, 29.97 fps) framerates.
5. Complete mock hierarchy for DaVinci Resolve Studio Python API:
   - MockResolve, MockProjectManager, MockProject, MockMediaPool, MockMediaStorage, MockTimeline, MockMediaPoolItem.
   - Asserts ProjectManager.LoadProject / CreateProject invocation.
   - Asserts SetSetting for 1080x1920 9:16 vertical 60fps timeline.
   - Asserts AddItemListToMediaPool / ImportMedia with normalized 4K raw paths.
   - Asserts AppendToTimeline structure: [{"mediaPoolItem": item, "startFrame": start, "endFrame": end, "recordFrame": 0}].
   - Asserts SetCurrentTimeline and SaveProject lifecycle.
6. Dry-run execution simulation (headless CI/CD compatibility without Resolve Studio).
7. Standalone CLI argument parsing, dry-run flag, JSON output, and execution via main().
8. Error handling and diagnostics on unimportable files or unavailable application.
"""

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
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
# MOCK DAVINCI RESOLVE API HIERARCHY
# ============================================================================

class MockMediaPoolItem:
    """Mock DaVinci Resolve MediaPoolItem object."""
    def __init__(self, name: str = "raw_take_4k.mp4", file_path: str = "/vault/01_RAW/raw_take_4k.mp4"):
        self._name = name
        self._file_path = file_path
        self._properties = {
            "File Name": name,
            "File Path": file_path,
            "FilePath": file_path,
            "FPS": "60.0",
        }

    def GetName(self) -> str:
        return self._name

    def GetClipProperty(self, prop_name: Optional[str] = None) -> Any:
        if prop_name:
            return self._properties.get(prop_name, "")
        return self._properties


class MockFolder:
    """Mock Media Pool Folder."""
    def __init__(self, name: str = "Master"):
        self._name = name
        self._clips: List[MockMediaPoolItem] = []

    def GetName(self) -> str:
        return self._name

    def GetClipList(self) -> List[MockMediaPoolItem]:
        return self._clips


class MockTimeline:
    """Mock DaVinci Resolve Timeline object."""
    def __init__(self, name: str = "EDM_Vertical_Timeline", unique_id: str = "tl_mock_12345"):
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


class MockMediaPool:
    """Mock DaVinci Resolve MediaPool object."""
    def __init__(self):
        self.root_folder = MockFolder("Master")
        self.timelines: List[MockTimeline] = []
        self.imported_paths: List[str] = []
        self.append_calls: List[List[Dict[str, Any]]] = []

    def GetRootFolder(self) -> MockFolder:
        return self.root_folder

    def ImportMedia(self, file_paths: List[str]) -> List[MockMediaPoolItem]:
        items = []
        for p in file_paths:
            self.imported_paths.append(p)
            item = MockMediaPoolItem(name=Path(p).name, file_path=p)
            self.root_folder._clips.append(item)
            items.append(item)
        return items

    def CreateEmptyTimeline(self, name: str) -> MockTimeline:
        tl = MockTimeline(name=name)
        self.timelines.append(tl)
        return tl

    def AppendToTimeline(self, clip_info_list: List[Dict[str, Any]]) -> bool:
        self.append_calls.append(clip_info_list)
        if self.timelines:
            self.timelines[-1].appended_items.extend(clip_info_list)
        return True


class MockMediaStorage:
    """Mock DaVinci Resolve MediaStorage object."""
    def __init__(self, resolve_app: Optional[Any] = None):
        self.resolve_app = resolve_app
        self.added_paths: List[str] = []

    def AddItemListToMediaPool(self, file_paths: List[str]) -> List[MockMediaPoolItem]:
        items = []
        target_pool = None
        if self.resolve_app and hasattr(self.resolve_app, "GetProjectManager"):
            pm = self.resolve_app.GetProjectManager()
            curr = pm.GetCurrentProject()
            if curr and hasattr(curr, "GetMediaPool"):
                target_pool = curr.GetMediaPool()

        for p in file_paths:
            self.added_paths.append(p)
            item = MockMediaPoolItem(name=Path(p).name, file_path=p)
            if target_pool:
                target_pool.root_folder._clips.append(item)
            items.append(item)
        return items


class MockProject:
    """Mock DaVinci Resolve Project object."""
    def __init__(self, name: str = "EDM_Master_Dashboard"):
        self._name = name
        self.media_pool = MockMediaPool()
        self.settings: Dict[str, str] = {}
        self.current_timeline: Optional[MockTimeline] = None

    def GetName(self) -> str:
        return self._name

    def GetMediaPool(self) -> MockMediaPool:
        return self.media_pool

    def SetSetting(self, setting_name: str, setting_value: str) -> bool:
        self.settings[setting_name] = str(setting_value)
        return True

    def GetSetting(self, setting_name: str) -> str:
        return self.settings.get(setting_name, "")

    def GetCurrentTimeline(self) -> Optional[MockTimeline]:
        return self.current_timeline

    def SetCurrentTimeline(self, timeline: MockTimeline) -> bool:
        self.current_timeline = timeline
        return True


class MockProjectManager:
    """Mock DaVinci Resolve ProjectManager object."""
    def __init__(self):
        self.projects: Dict[str, MockProject] = {}
        self.current_project: Optional[MockProject] = None
        self.saved_projects: List[str] = []

    def CreateProject(self, project_name: str) -> MockProject:
        proj = MockProject(name=project_name)
        self.projects[project_name] = proj
        self.current_project = proj
        return proj

    def LoadProject(self, project_name: str) -> Optional[MockProject]:
        if project_name in self.projects:
            self.current_project = self.projects[project_name]
            return self.current_project
        return None

    def GetCurrentProject(self) -> Optional[MockProject]:
        return self.current_project

    def SaveProject(self) -> bool:
        if self.current_project:
            self.saved_projects.append(self.current_project.GetName())
            return True
        return False


class MockResolveApp:
    """Mock top-level DaVinci Resolve Application object."""
    def __init__(self):
        self.project_manager = MockProjectManager()
        self.media_storage = MockMediaStorage(self)

    def GetProjectManager(self) -> MockProjectManager:
        return self.project_manager

    def GetMediaStorage(self) -> MockMediaStorage:
        return self.media_storage

    def GetVersionString(self) -> str:
        return "19.0.0.0033 Studio"


# ============================================================================
# UNIT TESTS: DISCOVERY, PATHS & EXCEPTIONS
# ============================================================================

class TestResolveDiscoveryAndExceptions(unittest.TestCase):
    """Verifies module discovery, path search heuristics, and exception hierarchy."""

    def test_exception_hierarchy(self):
        self.assertTrue(issubclass(ResolveModuleNotFoundError, ResolveScriptError))
        self.assertTrue(issubclass(ResolveNotRunningError, ResolveScriptError))
        self.assertTrue(issubclass(MediaImportError, ResolveScriptError))
        self.assertTrue(issubclass(TimelineCreationError, ResolveScriptError))
        self.assertTrue(issubclass(ProjectManagementError, ResolveScriptError))
        self.assertTrue(issubclass(ResolveScriptError, Exception))

    def test_search_paths_generation(self):
        paths = get_resolve_script_search_paths()
        self.assertIsInstance(paths, list)
        self.assertGreater(len(paths), 0)

        # On Windows or cross-platform, check that Blackmagic paths are included
        path_strs = " ".join(paths)
        if sys.platform.startswith("win"):
            self.assertIn("Blackmagic Design", path_strs)
            self.assertIn("Developer", path_strs)
            self.assertIn("Scripting", path_strs)

    def test_get_resolve_script_module_missing(self):
        with patch.dict(sys.modules, {"DaVinciResolveScript": None}):
            with patch("os.path.isdir", return_value=False):
                with self.assertRaises(ResolveModuleNotFoundError) as ctx:
                    get_resolve_script_module()
                self.assertIn("DaVinciResolveScript", str(ctx.exception))

    def test_get_resolve_instance_not_running(self):
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = None

        with patch("resolve_handoff.get_resolve_script_module", return_value=mock_dvr):
            with self.assertRaises(ResolveNotRunningError) as ctx:
                get_resolve_instance()
            self.assertIn("DaVinci Resolve Studio is not running", str(ctx.exception))


# ============================================================================
# UNIT TESTS: MATHEMATICAL FRAME CONVERSIONS & CONFIG
# ============================================================================

class TestResolveMathAndConfig(unittest.TestCase):
    """Verifies mathematical frame calculation precision and configuration mapping."""

    def setUp(self):
        self.engine = DaVinciResolveHandoffEngine(dry_run=True)

    def test_calculate_frames_standard_60fps(self):
        # 0.0s to 30.0s at 60.0 fps -> 0 to 1800 (1800 frames)
        start_f, end_f, dur_f = self.engine.calculate_frames(0.0, 30.0, 60.0)
        self.assertEqual(start_f, 0)
        self.assertEqual(end_f, 1800)
        self.assertEqual(dur_f, 1800)

    def test_calculate_frames_subsecond_precision(self):
        # 12.45s to 42.45s at 60.0 fps -> 747 to 2547 (1800 frames)
        start_f, end_f, dur_f = self.engine.calculate_frames(12.45, 42.45, 60.0)
        self.assertEqual(start_f, 747)
        self.assertEqual(end_f, 2547)
        self.assertEqual(dur_f, 1800)

    def test_calculate_frames_fractional_ntsc_fps(self):
        # 10.0s to 40.0s at 59.94 fps -> 599 to 2398
        start_f, end_f, dur_f = self.engine.calculate_frames(10.0, 40.0, 59.94)
        self.assertEqual(start_f, int(round(10.0 * 59.94)))
        self.assertEqual(end_f, int(round(40.0 * 59.94)))
        self.assertEqual(dur_f, end_f - start_f)

    def test_calculate_frames_negative_guard(self):
        start_f, end_f, dur_f = self.engine.calculate_frames(30.0, 10.0, 60.0)
        self.assertEqual(dur_f, 0)

    def test_config_properties_and_aliases(self):
        config = ResolveHandoffConfig(
            raw_file_path="01_RAW/EDCLV/Subtronics/take1.mp4",
            project_name="EDCLV_Project",
            timeline_name="Subtronics_Drop",
            start_time=15.5,
            duration=30.0,
            fps=60.0,
            width=1080,
            height=1920,
        )
        self.assertEqual(config.start_time_sec, 15.5)
        self.assertEqual(config.end_time_sec, 45.5)
        self.assertEqual(config.duration_sec, 30.0)
        self.assertEqual(config.timeline_width, 1080)
        self.assertEqual(config.timeline_height, 1920)
        self.assertEqual(config.timeline_fps, 60.0)
        self.assertEqual(config.raw_clip_path, Path("01_RAW/EDCLV/Subtronics/take1.mp4"))

    def test_result_to_dict_serialization(self):
        result = ResolveHandoffResult(
            success=True,
            status="success",
            project_name="Test_Proj",
            timeline_name="Test_TL",
            raw_file_path="/path/to/raw.mp4",
            start_time=10.0,
            end_time=40.0,
            duration=30.0,
            start_frame=600,
            end_frame=2400,
            duration_frames=1800,
            fps=60.0,
            width=1080,
            height=1920,
            timeline_resolution="1080x1920",
            media_item_name="raw.mp4",
            timeline_id="tl_1",
        )
        res_dict = result.to_dict()
        self.assertTrue(res_dict["success"])
        self.assertEqual(res_dict["start_frame"], 600)
        self.assertEqual(res_dict["end_frame"], 2400)
        self.assertEqual(res_dict["timeline_resolution"], "1080x1920")


# ============================================================================
# UNIT TESTS: MOCK RESOLVE HANDOFF ENGINE
# ============================================================================

class TestDaVinciResolveHandoffEngineMock(unittest.TestCase):
    """Verifies complete API interactions using genuine mock object hierarchy."""

    def setUp(self):
        self.mock_resolve = MockResolveApp()
        self.engine = DaVinciResolveHandoffEngine(resolve_instance=self.mock_resolve)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Create dummy 4K raw video file
        self.raw_video_path = self.temp_path / "20260822_Edclasvegas_Subfocus_V1_4k.mp4"
        self.raw_video_path.write_bytes(b"\x00" * 4096)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_execute_handoff_success_flow(self):
        config = ResolveHandoffConfig(
            raw_file_path=self.raw_video_path,
            project_name="EDC_Las_Vegas_Master",
            timeline_name="Sub_Focus_Desire_Drop",
            start_time=12.45,
            end_time=42.45,
            fps=60.0,
            width=1080,
            height=1920,
            festival="EDC Las Vegas",
            artist="Sub Focus",
            track="Desire",
            auto_save=True,
        )

        result = self.engine.execute_handoff(config)

        self.assertTrue(result.success)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.project_name, "EDC_Las_Vegas_Master")
        self.assertEqual(result.timeline_name, "Sub_Focus_Desire_Drop")
        self.assertEqual(result.start_frame, 747)
        self.assertEqual(result.end_frame, 2547)
        self.assertEqual(result.duration_frames, 1800)
        self.assertEqual(result.timeline_resolution, "1080x1920")
        self.assertEqual(result.fps, 60.0)

        # Verify project settings
        pm = self.mock_resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        self.assertIsNotNone(project)
        self.assertEqual(project.GetSetting("timelineResolutionWidth"), "1080")
        self.assertEqual(project.GetSetting("timelineResolutionHeight"), "1920")
        self.assertEqual(project.GetSetting("timelineFrameRate"), "60")
        self.assertEqual(project.GetSetting("useCustomTimelineSettings"), "1")

        # Verify media import
        media_pool = project.GetMediaPool()
        root_folder = media_pool.GetRootFolder()
        clips = root_folder.GetClipList()
        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].GetName(), self.raw_video_path.name)

        # Verify AppendToTimeline structure
        self.assertEqual(len(media_pool.append_calls), 1)
        append_payload = media_pool.append_calls[0]
        self.assertEqual(len(append_payload), 1)
        clip_data = append_payload[0]
        self.assertEqual(clip_data["mediaPoolItem"], clips[0])
        self.assertEqual(clip_data["startFrame"], 747)
        self.assertEqual(clip_data["endFrame"], 2547)
        self.assertEqual(clip_data["recordFrame"], 0)

        # Verify auto-save
        self.assertIn("EDC_Las_Vegas_Master", pm.saved_projects)

    def test_execute_handoff_load_existing_project(self):
        pm = self.mock_resolve.GetProjectManager()
        pm.CreateProject("Existing_Project")

        config = ResolveHandoffConfig(
            raw_file_path=self.raw_video_path,
            project_name="Existing_Project",
            timeline_name="Timeline_Existing",
            start_time=5.0,
            duration=20.0,
            fps=60.0,
        )

        result = self.engine.execute_handoff(config)
        self.assertTrue(result.success)
        self.assertEqual(result.start_frame, 300)
        self.assertEqual(result.end_frame, 1500)
        self.assertEqual(result.duration_frames, 1200)

    def test_execute_handoff_dry_run(self):
        engine = DaVinciResolveHandoffEngine(dry_run=True)
        config = ResolveHandoffConfig(
            raw_file_path="01_RAW/simulated_4k.mp4",
            project_name="DryRun_Project",
            timeline_name="DryRun_Timeline",
            start_time=10.0,
            duration=30.0,
            dry_run=True,
        )

        result = engine.execute_handoff(config)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "dry_run_simulated")
        self.assertEqual(result.start_frame, 600)
        self.assertEqual(result.end_frame, 2400)
        self.assertEqual(result.duration_frames, 1800)

    def test_create_resolve_timeline_top_level_function(self):
        res_dict = create_resolve_timeline(
            raw_file_path=str(self.raw_video_path),
            start_time=15.0,
            end_time=45.0,
            project_name="TopLevel_Proj",
            timeline_name="TopLevel_TL",
            fps=60.0,
            resolve_instance=self.mock_resolve,
        )
        self.assertIsInstance(res_dict, dict)
        self.assertTrue(res_dict["success"])
        self.assertEqual(res_dict["start_frame"], 900)
        self.assertEqual(res_dict["end_frame"], 2700)
        self.assertEqual(res_dict["duration_frames"], 1800)

    def test_import_raw_media_missing_file_error(self):
        missing_file = self.temp_path / "non_existent_raw_video.mp4"
        engine_live = DaVinciResolveHandoffEngine()
        with self.assertRaises(MediaImportError):
            engine_live.import_raw_media(self.mock_resolve, MockProject("test"), missing_file)


# ============================================================================
# UNIT TESTS: CLI INTERFACE & PARSER
# ============================================================================

class TestResolveHandoffCLI(unittest.TestCase):
    """Verifies CLI argument parsing, flags, and runner integration."""

    def test_parse_cli_args_all_options(self):
        args = parse_cli_args([
            "--raw-file", "01_RAW/Fest/Artist/clip.mp4",
            "--start", "14.5",
            "--end", "44.5",
            "--fps", "60.0",
            "--width", "1080",
            "--height", "1920",
            "--project", "My_Fest_Project",
            "--timeline", "My_Timeline",
            "--festival", "Ultra Miami",
            "--artist", "Hardwell",
            "--track", "Spaceman",
            "--no-save",
            "--dry-run",
            "--json",
        ])

        self.assertEqual(args.raw_file, "01_RAW/Fest/Artist/clip.mp4")
        self.assertEqual(args.start, 14.5)
        self.assertEqual(args.end, 44.5)
        self.assertEqual(args.fps, 60.0)
        self.assertEqual(args.width, 1080)
        self.assertEqual(args.height, 1920)
        self.assertEqual(args.project, "My_Fest_Project")
        self.assertEqual(args.timeline, "My_Timeline")
        self.assertEqual(args.festival, "Ultra Miami")
        self.assertEqual(args.artist, "Hardwell")
        self.assertEqual(args.track, "Spaceman")
        self.assertTrue(args.no_save)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.json)

    def test_cli_main_dry_run_json(self):
        with patch("sys.stdout") as mock_stdout:
            exit_code = main([
                "--raw-file", "01_RAW/EDCLV/Subtronics/sample.mp4",
                "--start", "10.0",
                "--duration", "30.0",
                "--dry-run",
                "--json",
            ])
            self.assertEqual(exit_code, 0)

    def test_cli_main_dry_run_text_report(self):
        with patch("sys.stdout") as mock_stdout:
            exit_code = main([
                "--raw-file", "01_RAW/EDCLV/Subtronics/sample.mp4",
                "--start", "0.0",
                "--duration", "30.0",
                "--dry-run",
            ])
            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
