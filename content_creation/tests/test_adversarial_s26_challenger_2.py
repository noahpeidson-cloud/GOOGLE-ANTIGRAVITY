"""
test_adversarial_s26_challenger_2.py - Dedicated Adversarial Stress Harness for Challenger 2

Comprehensive empirical challenge suite verifying:
1. SOP Completeness: Mathematical shutter speed, ISO range, Kelvin locks, mic attenuation, laser safety, shooting duration.
2. Blueprint Completeness: Phase 0, Mechanism 0 (samsung_ingest.py), updated topologies, 6-phase lifecycle, retention of all core parameters.
3. Orchestrator CLI Execution: Live execution of `orchestrator.py --help`, `orchestrator.py adb-ingest --help`, `orchestrator.py pipeline --help`, plus all subcommands and parser verification.
4. End-to-End Simulated Pipeline: Full lifecycle execution with `--from-device` flag (dry-run and mocked device pull).
5. Adversarial Edge Cases: Broken ADB states, hash mismatch retries, partition boundaries, safe-zone violations, device selection logic.
"""

from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Ensure content_creation module directory is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_DIR = SCRIPT_DIR.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from config import (
    ADB_DEFAULT_TIMEOUT_SECONDS,
    ADB_EXPERT_RAW_PATH,
    ADB_MIN_FREE_DISK_HEADROOM_BYTES,
    ADB_SUPPORTED_EXTENSIONS,
    AUDIO_CEILING_TRUE_PEAK,
    AUDIO_LUFS_TOLERANCE,
    AUDIO_TARGET_LUFS,
    AUDIO_TARGET_TRUE_PEAK,
    AssetStatus,
    BrandType,
    ContentIDStatus,
    DEFAULT_ANDROID_CAMERA_PATH,
    DenoiseMode,
    EventTier,
    FOLDER_TIERS,
    LoudnormMode,
    MAX_FOLDER_ITEMS,
    ProductionPreset,
    ReframeMode,
    SAMSUNG_MODEL_PREFIXES,
    ToneMapMode,
    VIDEO_CANVAS_HEIGHT,
    VIDEO_CANVAS_WIDTH,
    VIDEO_DURATION_MAX_SECONDS,
)
from ffmpeg_processor import (
    FFmpegMasterProcessor,
    FilterGraphBuilder,
    LoudnessStats,
    TranscodeConfig,
)
from ingest_assets import (
    AssetIngestionRouter,
    DirectoryHealthGuard,
    FilenameNormalizer,
    StreamProbeData,
    calculate_sha256,
)
from metadata_tracker import (
    BoundingBox,
    CommentSpamFilter,
    MediaManifestDB,
    SEOCaptionGenerator,
    SafeZoneAuditor,
)
from orchestrator import (
    QCReport,
    build_parser,
    run_master_pipeline,
    verify_media_file,
)
from samsung_ingest import (
    ADBClient,
    ADBDeviceInfo,
    ADBDeviceManager,
    ADBError,
    ADBIngestionLedger,
    ADBIngestionSummary,
    ADBNotFoundError,
    ADBPullResult,
    DeviceSelectionError,
    DeviceUnauthorizedError,
    InsufficientStorageError,
    NoDeviceConnectedError,
    RemoteDirectoryNotFoundError,
    RemoteMediaAsset,
    SamsungADBIngestor,
    SamsungIngestEngine,
    TransferIntegrityError,
    find_adb_binary,
)


class TestSOPCompleteness(unittest.TestCase):
    """Adversarial validation of samsung_s26_concert_sop.md completeness and rigor."""

    def setUp(self):
        self.sop_path = MODULE_DIR / "samsung_s26_concert_sop.md"
        self.assertTrue(self.sop_path.is_file(), f"SOP document missing at {self.sop_path}")
        self.sop_text = self.sop_path.read_text(encoding="utf-8")

    def test_sop_length_and_identity(self):
        """Asserts SOP is comprehensive (>25KB) with proper identification headers."""
        self.assertGreater(len(self.sop_text), 25000)
        self.assertIn("SOP-S26U-CONCERT-001", self.sop_text)
        self.assertIn("Samsung Galaxy S26 Ultra", self.sop_text)
        self.assertIn("ISOCELL 200MP", self.sop_text)

    def test_sop_shutter_speed_math_and_pwm_mitigation(self):
        """Asserts presence of exact shutter speed math, 180-degree rule, and PWM roll fixes."""
        self.assertIn("Target Shutter Speed", self.sop_text)
        self.assertIn("Framerate", self.sop_text)
        self.assertIn("1/120", self.sop_text)
        self.assertIn("1/60", self.sop_text)
        self.assertIn("1/240", self.sop_text)
        # Regional AC mains sync (60Hz vs 50Hz)
        self.assertIn("60", self.sop_text)
        self.assertIn("50", self.sop_text)
        self.assertIn("1/100", self.sop_text)
        self.assertIn("rolling shutter", self.sop_text.lower())
        self.assertIn("split-frame", self.sop_text.lower())

    def test_sop_iso_range_and_auto_iso_failure(self):
        """Asserts presence of ISO range (100-400 festival standard, 800 ceiling) and auto-ISO failure mode."""
        self.assertIn("ISO 100", self.sop_text)
        self.assertIn("400", self.sop_text)
        self.assertIn("800", self.sop_text)
        self.assertIn("Auto-Exposure Failure Mode", self.sop_text)
        self.assertIn("Smart-ISO Pro", self.sop_text)
        self.assertIn("Dual Slope Gain", self.sop_text)

    def test_sop_kelvin_locks_and_awb_failure(self):
        """Asserts Kelvin locks (5000K-5200K daylight/laser, 4000K-4500K club, 5600K daylight)."""
        self.assertIn("5000", self.sop_text)
        self.assertIn("5200", self.sop_text)
        self.assertIn("4000", self.sop_text)
        self.assertIn("5600", self.sop_text)
        self.assertIn("Auto White Balance (AWB) Failure", self.sop_text)

    def test_sop_mic_attenuation_and_acoustic_spl(self):
        """Asserts mic attenuation (-8 dB default, -6 to -10 dB range, rear mic, zoom-in mic OFF, 110-125 dB SPL)."""
        self.assertIn("-8 dB", self.sop_text)
        self.assertIn("-6", self.sop_text)
        self.assertIn("-10", self.sop_text)
        self.assertIn("Rear", self.sop_text)
        self.assertIn("Omni", self.sop_text)
        self.assertIn("Zoom-in Mic", self.sop_text)
        self.assertIn("STRICTLY OFF", self.sop_text)
        self.assertIn("110", self.sop_text)
        self.assertIn("125", self.sop_text)
        self.assertIn("-12", self.sop_text)
        self.assertIn("-6 dBFS", self.sop_text)

    def test_sop_laser_safety_protocol(self):
        """Asserts laser radiation safety protocol (>30° off-axis, scatter capture, Class 3B/4)."""
        self.assertIn("Laser Radiation", self.sop_text)
        self.assertIn("Class 3B", self.sop_text)
        self.assertIn("Class 4", self.sop_text)
        self.assertIn(">30", self.sop_text)
        self.assertIn("off-axis", self.sop_text.lower())
        self.assertIn("aperture", self.sop_text.lower())
        self.assertIn("photodiode", self.sop_text.lower())
        self.assertIn("silicon", self.sop_text.lower())

    def test_sop_shooting_duration_and_lead_in(self):
        """Asserts shooting duration limits (<55s hard ceiling, 16-30s target, 4s pre-drop lead-in)."""
        self.assertIn("4.0", self.sop_text)
        self.assertIn("16.0", self.sop_text)
        self.assertIn("30.0", self.sop_text)
        self.assertIn("55.0", self.sop_text)
        self.assertIn("59.0", self.sop_text)
        self.assertIn("Content ID", self.sop_text)

    def test_sop_sensor_architecture_and_binning(self):
        """Asserts sensor specs (200MP ISOCELL, 16-in-1 Tetra²pixel binning to 12.5MP, 2.4µm super-pixels)."""
        self.assertIn("200 Megapixels", self.sop_text)
        self.assertIn("16-in-1 Tetra²pixel", self.sop_text)
        self.assertIn("12.5MP", self.sop_text)
        self.assertIn("2.4", self.sop_text)
        self.assertIn("HDR10+", self.sop_text)
        self.assertIn("HEVC", self.sop_text)


class TestBlueprintCompleteness(unittest.TestCase):
    """Adversarial validation of V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md completeness."""

    def setUp(self):
        self.bp_path = MODULE_DIR / "V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md"
        self.assertTrue(self.bp_path.is_file(), f"Blueprint missing at {self.bp_path}")
        self.bp_text = self.bp_path.read_text(encoding="utf-8")

    def test_blueprint_header_and_scale(self):
        """Asserts Blueprint document size (>75KB) and master header structure."""
        self.assertGreater(len(self.bp_text), 75000)
        self.assertIn("V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT", self.bp_text)
        self.assertIn("Autonomous AI Master Mind Edition", self.bp_text)

    def test_blueprint_mechanism_0_presence(self):
        """Asserts Mechanism 0 (samsung_ingest.py) is explicitly documented with python interface."""
        self.assertIn("Mechanism 0: Samsung Galaxy S26 Ultra ADB Hardware Ingestion Bridge", self.bp_text)
        self.assertIn("samsung_ingest.py", self.bp_text)
        self.assertIn("SamsungADBIngestor", self.bp_text)
        self.assertIn("ADBPullResult", self.bp_text)
        self.assertIn("RemoteMediaAsset", self.bp_text)
        self.assertIn("ADBDeviceInfo", self.bp_text)
        self.assertIn("SM-S948", self.bp_text)

    def test_blueprint_updated_system_topologies(self):
        """Asserts presence of updated system topologies including hardware layer and Phase 0."""
        self.assertIn("AI AGENT MASTER MIND ORCHESTRATOR", self.bp_text)
        self.assertIn("Phase 0: Physical Device Capture & Automated Hardware Ingestion", self.bp_text)
        self.assertIn("01_RAW_INBOX", self.bp_text)
        self.assertIn("02_IN_PROGRESS", self.bp_text)
        self.assertIn("03_READY_TO_POST", self.bp_text)
        self.assertIn("04_ARCHIVE", self.bp_text)

    def test_blueprint_6_phase_lifecycle(self):
        """Asserts full 6-phase lifecycle from Phase 0 to Phase 5."""
        self.assertIn("6-Phase Agent Orchestration Lifecycle", self.bp_text)
        self.assertIn("[Phase 0: Physical Device Capture & Automated Hardware Ingestion]", self.bp_text)
        self.assertIn("[Phase 1: Ingestion & Trigger]", self.bp_text)
        self.assertIn("[Phase 2: Deep Analysis & Classification]", self.bp_text)
        self.assertIn("[Phase 3: Automated Transcoding & Assembly]", self.bp_text)
        self.assertIn("[Phase 4: Automated Verification & QC]", self.bp_text)
        self.assertIn("[Phase 5: Distribution Packaging & Metadata Staging]", self.bp_text)

    def test_blueprint_core_technical_parameters_retained(self):
        """Asserts retention of all critical broadcast and platform parameters."""
        # Audio Loudness
        self.assertIn("-14.0", self.bp_text)
        self.assertIn("-1.5", self.bp_text)
        # Safe Zones
        self.assertIn("900", self.bp_text)
        self.assertIn("1270", self.bp_text)
        # Duration ceiling
        self.assertIn("59.00", self.bp_text)
        # Partition rule
        self.assertIn("50", self.bp_text)
        # Dimensions
        self.assertIn("1080", self.bp_text)
        self.assertIn("1920", self.bp_text)

    def test_blueprint_adb_edge_cases_documented(self):
        """Asserts Section 8 contains explicit ADB troubleshooting edge cases."""
        self.assertIn("ADB Device Unauthorized", self.bp_text)
        self.assertIn("ADB Binary Not Found in PATH", self.bp_text)
        self.assertIn("Physical Connection Lost Mid-Transfer", self.bp_text)
        self.assertIn("Host Storage Exhaustion", self.bp_text)
        self.assertIn("Folder Partition Overflow During Bulk Pull", self.bp_text)


class TestOrchestratorCLISubprocessAndParsing(unittest.TestCase):
    """Adversarially tests CLI command invocation, help dispatching, and argument parsing."""

    def setUp(self):
        self.python_exe = sys.executable
        self.orchestrator_script = MODULE_DIR / "orchestrator.py"
        self.parser = build_parser()

    def run_cli(self, args: list) -> subprocess.CompletedProcess:
        cmd = [self.python_exe, str(self.orchestrator_script)] + args
        return subprocess.run(
            cmd,
            cwd=str(MODULE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )

    def test_orchestrator_main_help_execution(self):
        """Executes orchestrator.py --help in a live subprocess."""
        proc = self.run_cli(["--help"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Master AI Media Orchestrator", proc.stdout)
        self.assertIn("adb-ingest", proc.stdout)
        self.assertIn("pipeline", proc.stdout)
        self.assertIn("ingest", proc.stdout)
        self.assertIn("process", proc.stdout)

    def test_orchestrator_adb_ingest_help_execution(self):
        """Executes orchestrator.py adb-ingest --help in a live subprocess."""
        proc = self.run_cli(["adb-ingest", "--help"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--device", proc.stdout)
        self.assertIn("--adb-path", proc.stdout)
        self.assertIn("--remote-dir", proc.stdout)
        self.assertIn("--recent", proc.stdout)
        self.assertIn("--date", proc.stdout)
        self.assertIn("--auto-route", proc.stdout)
        self.assertIn("--inbox-only", proc.stdout)
        self.assertIn("--include-raw-dng", proc.stdout)
        self.assertIn("--force", proc.stdout)
        self.assertIn("--dry-run", proc.stdout)
        self.assertIn("--list-devices", proc.stdout)

    def test_orchestrator_pipeline_help_execution(self):
        """Executes orchestrator.py pipeline --help in a live subprocess."""
        proc = self.run_cli(["pipeline", "--help"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--from-device", proc.stdout)
        self.assertIn("--device", proc.stdout)
        self.assertIn("--adb-path", proc.stdout)
        self.assertIn("--event", proc.stdout)
        self.assertIn("--artist", proc.stdout)
        self.assertIn("--track", proc.stdout)
        self.assertIn("--brand", proc.stdout)
        self.assertIn("--tier", proc.stdout)
        self.assertIn("--dry-run", proc.stdout)

    def test_orchestrator_all_subcommands_help_execution(self):
        """Executes --help on all remaining subcommands."""
        for sub in ["ingest", "process", "inspect", "generate-seo", "audit-safezone", "verify"]:
            proc = self.run_cli([sub, "--help"])
            self.assertEqual(proc.returncode, 0, f"Failed help on subcommand: {sub}")

    def test_orchestrator_subcommand_parser_validation(self):
        """Tests argument parsing and validation across all subcommands."""
        # 1. adb-ingest
        args_adb = self.parser.parse_args([
            "adb-ingest", "--event", "UltraMiami", "--artist", "MartinGarrix", "--recent", "5", "--dry-run"
        ])
        self.assertEqual(args_adb.subcommand, "adb-ingest")
        self.assertEqual(args_adb.event, "UltraMiami")
        self.assertEqual(args_adb.artist, "MartinGarrix")
        self.assertEqual(args_adb.recent, 5)
        self.assertTrue(args_adb.dry_run)

        # 2. pipeline with --from-device
        args_pipe = self.parser.parse_args([
            "pipeline", "--from-device", "--event", "Tomorrowland", "--artist", "Hardwell", "--dry-run"
        ])
        self.assertEqual(args_pipe.subcommand, "pipeline")
        self.assertTrue(args_pipe.from_device)
        self.assertEqual(args_pipe.event, "Tomorrowland")
        self.assertEqual(args_pipe.artist, "Hardwell")
        self.assertTrue(args_pipe.dry_run)

        # 3. generate-seo
        args_seo = self.parser.parse_args([
            "generate-seo", "--artist", "SubFocus", "--track", "Desire", "--event", "EDC"
        ])
        self.assertEqual(args_seo.subcommand, "generate-seo")
        self.assertEqual(args_seo.artist, "SubFocus")

        # 4. audit-safezone
        args_safe = self.parser.parse_args([
            "audit-safezone", "--box", "100", "200", "300", "400"
        ])
        self.assertEqual(args_safe.subcommand, "audit-safezone")
        self.assertEqual(args_safe.box, [100, 200, 300, 400])


class TestEndToEndPipelineSimulatedExecution(unittest.TestCase):
    """Adversarially tests end-to-end simulated pipeline with --from-device and local files."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        for tier_dir in FOLDER_TIERS.values():
            (self.workspace / tier_dir).mkdir(parents=True, exist_ok=True)
        self.db_path = self.workspace / "media_manifest.sqlite"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_pipeline_dry_run_with_from_device(self):
        """Tests pipeline execution simulating --from-device in dry-run mode."""
        # Create a dummy simulated inbox file
        sim_file = self.workspace / FOLDER_TIERS["INBOX"] / "simulated_take.mp4"
        sim_file.write_bytes(b"Simulated MP4 video bytes for testing")

        # Execute run_master_pipeline directly
        result = run_master_pipeline(
            input_file=sim_file,
            workspace_root=self.workspace,
            event="EDCLasVegas",
            artist="SubFocus",
            track="Desire",
            genre="dnb",
            brand=BrandType.LASER_BAPTISM,
            tier=EventTier.PILLAR_A,
            reframe_mode=ReframeMode.CENTER_CROP,
            dry_run=True,
            db_path=self.db_path,
        )

        self.assertEqual(result["status"], AssetStatus.READY_TO_POST.value)
        self.assertIn("SubFocus", result["seo_package"]["yt_title"])
        self.assertTrue(result["qc_report"]["passed"])

    @patch("samsung_ingest.find_adb_binary")
    @patch("samsung_ingest.ADBClient.run_cmd")
    @patch("samsung_ingest.ADBClient.pull_file_atomic")
    def test_pipeline_with_mocked_adb_device_pull(self, mock_pull, mock_run, mock_find_adb):
        """Tests pipeline pulling directly from a mocked Samsung S26 Ultra ADB device."""
        mock_find_adb.return_value = Path("C:/fake/adb.exe")

        def dynamic_mock_run(args, **kwargs):
            cmd_str = " ".join(str(a) for a in args)
            if "devices" in cmd_str:
                return subprocess.CompletedProcess(
                    args=args, returncode=0,
                    stdout="List of devices attached\nR5CX10ABCD device product:e3q model:SM-S948U device:e3q\n",
                    stderr=""
                )
            elif "EXISTS" in cmd_str or "[ -d" in cmd_str:
                return subprocess.CompletedProcess(
                    args=args, returncode=0,
                    stdout="EXISTS\n",
                    stderr=""
                )
            elif "stat" in cmd_str:
                return subprocess.CompletedProcess(
                    args=args, returncode=0,
                    stdout="104857600 1755813600 /sdcard/DCIM/Camera/20260822_010000.mp4\n",
                    stderr=""
                )
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        mock_run.side_effect = dynamic_mock_run

        def side_effect_pull_atomic(remote_path, local_destination, expected_size_bytes, serial=None, max_retries=3):
            Path(local_destination).write_bytes(b"Simulated 4K HDR raw concert video bytes from S26 Ultra")
            return (True, 1.25, "abcdef1234567890")

        mock_pull.side_effect = side_effect_pull_atomic

        ingestor = SamsungADBIngestor(workspace_root=self.workspace, adb_path="mock_adb")
        summary = ingestor.ingest_batch(
            event_name="EDCOrlando",
            artist_name="JohnSummit",
            track_name="WhereYouAre",
            recent_limit=1,
            auto_route=False,
            inbox_only=True,
            dry_run=False,
        )

        self.assertEqual(summary.total_pulled, 1)
        pulled_file = Path(summary.pulled_results[0].local_path)
        self.assertTrue(pulled_file.is_file())

        # Now run the rest of the master pipeline on this pulled file in dry-run mode
        res = run_master_pipeline(
            input_file=pulled_file,
            workspace_root=self.workspace,
            event="EDCOrlando",
            artist="JohnSummit",
            track="WhereYouAre",
            genre="house",
            brand=BrandType.LASER_BAPTISM,
            tier=EventTier.PILLAR_A,
            dry_run=True,
            db_path=self.db_path,
        )

        self.assertEqual(res["status"], AssetStatus.READY_TO_POST.value)
        self.assertIn("JohnSummit", res["seo_package"]["yt_title"])
        self.assertTrue(res["qc_report"]["passed"])


class TestAdversarialEdgeCasesAndResilience(unittest.TestCase):
    """Adversarial stress testing of edge cases across ADB, Partitioning, and Safe Zones."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        for tier_dir in FOLDER_TIERS.values():
            (self.workspace / tier_dir).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_safezone_boundary_violations(self):
        """Tests that text overlays outside the 900x1270 safe zone are flagged."""
        # Clean compliant bounding box (centered)
        good_box = BoundingBox(x=100, y=250, width=800, height=200)
        report_good = SafeZoneAuditor.audit_bounding_box(good_box)
        self.assertTrue(report_good.is_compliant)
        self.assertEqual(len(report_good.yt_violations), 0)

        # Violating bottom right action buttons
        bad_box = BoundingBox(x=950, y=1400, width=120, height=200)
        report_bad = SafeZoneAuditor.audit_bounding_box(bad_box)
        self.assertFalse(report_bad.is_compliant)
        self.assertGreater(len(report_bad.yt_violations) + len(report_bad.tiktok_violations), 0)

    def test_directory_health_guard_50_item_partitioning(self):
        """Tests that DirectoryHealthGuard cleanly creates Batch02 when Batch01 hits 50 items."""
        guard = DirectoryHealthGuard(max_items=50)
        base_folder = self.workspace / FOLDER_TIERS["INBOX"]

        # Batch 1 folder
        batch_folder = guard.get_healthy_subfolder(base_folder, "EDC2026")
        self.assertTrue(str(batch_folder).endswith("EDC2026") or str(batch_folder).endswith("EDC2026_Batch01"))

        # Create 50 dummy files in that folder
        for i in range(50):
            (batch_folder / f"clip_{i:03d}.mp4").write_bytes(b"dummy")

        # Request next subfolder -> Must partition to Batch02
        next_folder = guard.get_healthy_subfolder(base_folder, "EDC2026")
        self.assertNotEqual(batch_folder, next_folder)
        self.assertTrue(str(next_folder).endswith("Batch02"))

    @patch("samsung_ingest.find_adb_binary")
    @patch("samsung_ingest.ADBClient.run_cmd")
    def test_unauthorized_adb_device_handling(self, mock_run, mock_find_adb):
        """Tests clean error reporting when connected ADB device is in unauthorized state."""
        mock_find_adb.return_value = Path("C:/fake/adb.exe")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="List of devices attached\nR5CX10ABCD unauthorized\n",
            stderr=""
        )
        ingestor = SamsungADBIngestor(workspace_root=self.workspace, adb_path="mock_adb")
        with self.assertRaises(DeviceUnauthorizedError):
            ingestor.ingest_batch(
                event_name="EDC",
                artist_name="Artist",
                track_name="ID",
                dry_run=False,
            )

    @patch("samsung_ingest.find_adb_binary")
    @patch("samsung_ingest.ADBClient.run_cmd")
    def test_device_selection_prioritizes_s26_ultra(self, mock_run, mock_find_adb):
        """Tests that device manager prioritizes S26 Ultra over other connected devices."""
        mock_find_adb.return_value = Path("C:/fake/adb.exe")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=(
                "List of devices attached\n"
                "DEVICE_PIXEL device product:cheetah model:Pixel_7_Pro device:cheetah\n"
                "DEVICE_S26 device product:e3q model:SM-S948U device:e3q\n"
            ),
            stderr=""
        )
        client = ADBClient(adb_path="mock_adb")
        active = client.select_active_device()
        self.assertEqual(active.serial, "DEVICE_S26")
        self.assertTrue(active.is_s26_ultra)


if __name__ == "__main__":
    unittest.main()
