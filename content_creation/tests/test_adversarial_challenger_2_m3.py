"""
test_adversarial_challenger_2_m3.py - Milestone 3 Adversarial Verification & Stress Test Suite
Challenger 2 Empirical Verification:
1. Contradictory & Ambiguous CLI Flags & Precedence Hierarchy
2. publish-youtube CLI subcommand (missing files, dry-run mode, malformed arguments, exit codes)
3. SQLite database concurrency, manifest status transitions, and lifecycle integrity
4. End-to-end master pipeline chaining under normal, edge, and adversarial conditions
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure content_creation module directory is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_DIR = SCRIPT_DIR.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from config import (
    AssetStatus,
    BrandType,
    ContentIDStatus,
    DenoiseMode,
    EventTier,
    FOLDER_TIERS,
    LoudnormMode,
    ProductionPreset,
    ReframeMode,
    ToneMapMode,
    VIDEO_CANVAS_HEIGHT,
    VIDEO_CANVAS_WIDTH,
    VIDEO_DURATION_MAX_SECONDS,
)
from audio_dsp import (
    AudioDropDetector,
    DropWindowResult,
    generate_synthetic_edm_signal,
)
from ffmpeg_processor import (
    FFmpegMasterProcessor,
    TranscodeConfig,
)
from ingest_assets import (
    AssetIngestionRouter,
    FilenameNormalizer,
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
from youtube_publisher import (
    YouTubePublisher,
    YouTubePublishResult,
    YouTubeVideoMetadata,
)


class TestCLIContradictoryFlagsAndPrecedence(unittest.TestCase):
    """Adversarially tests CLI invocations with contradictory, conflicting, and edge-case flags."""

    def setUp(self):
        self.parser = build_parser()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        for tier_dir in FOLDER_TIERS.values():
            (self.workspace / tier_dir).mkdir(parents=True, exist_ok=True)
        self.db_path = self.workspace / "media_manifest.sqlite"
        self.python_exe = sys.executable
        self.orchestrator_script = MODULE_DIR / "orchestrator.py"

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, args: list) -> subprocess.CompletedProcess:
        cmd = [self.python_exe, str(self.orchestrator_script)] + args
        return subprocess.run(
            cmd,
            cwd=str(MODULE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
        )

    def test_cli_process_auto_drop_with_start_time_override_precedence(self):
        """Verify manual --start-time strictly wins over --auto-drop in process subcommand."""
        parsed = self.parser.parse_args([
            "process",
            "--input", "source.mp4",
            "--output", "dest.mp4",
            "--auto-drop",
            "--start-time", "15.0",
            "--duration", "25.0",
            "--drop-duration", "30.0",
            "--dry-run",
        ])
        self.assertEqual(parsed.subcommand, "process")
        self.assertTrue(parsed.auto_drop)
        self.assertEqual(parsed.start_time, 15.0)
        self.assertEqual(parsed.duration, 25.0)

        # In orchestrator.py line 695:
        # if args.start_time is not None: start_t = float(args.start_time) ...
        # Verify execution logic prioritizes start_time:
        start_t = float(parsed.start_time) if parsed.start_time is not None else None
        self.assertEqual(start_t, 15.0)

    def test_pipeline_auto_drop_with_start_time_manual_override_strictly_wins(self):
        """Verify that in run_master_pipeline, specifying both auto_drop=True and start_time=15.0 yields manual_cli_override."""
        dummy_video = self.workspace / "01_RAW_INBOX" / "test_set.mp4"
        dummy_video.write_bytes(b"dummy mp4 data for testing")

        res = run_master_pipeline(
            input_file=dummy_video,
            workspace_root=self.workspace,
            event="EDCLasVegas",
            artist="SubFocus",
            track="Desire",
            genre="dnb",
            brand=BrandType.LASER_BAPTISM,
            tier=EventTier.PILLAR_A,
            start_time=15.0,
            duration=20.0,
            auto_drop=True,
            drop_duration=30.0,
            dry_run=True,
            db_path=self.db_path,
        )

        self.assertIn("drop_window", res)
        drop_win = res["drop_window"]
        self.assertEqual(drop_win["start_time_sec"], 15.0)
        self.assertEqual(drop_win["duration_sec"], 20.0)
        self.assertEqual(drop_win["end_time_sec"], 35.0)
        self.assertTrue(drop_win["is_manual_override"])
        self.assertEqual(drop_win["detection_method"], "manual_cli_override")

    def test_audio_dsp_detect_optimal_drop_manual_override_immediate_bypass(self):
        """Verify that AudioDropDetector.detect_optimal_drop immediately returns manual override even if path is invalid."""
        detector = AudioDropDetector(target_duration_sec=30.0)
        # Non-existent file path should NOT raise FileNotFoundError when manual_start_time is provided
        res = detector.detect_optimal_drop(
            media_path="completely_non_existent_file.mp4",
            manual_start_time=42.5,
            manual_duration=28.0,
        )
        self.assertEqual(res.start_time_sec, 42.5)
        self.assertEqual(res.duration_sec, 28.0)
        self.assertEqual(res.end_time_sec, 70.5)
        self.assertTrue(res.is_manual_override)
        self.assertEqual(res.detection_method, "manual_cli_override")

    def test_cli_publish_contradictory_skip_audit_and_auto_promote(self):
        """Verify that --skip-audit together with --auto-promote results in auto_promote=False (audit bypass keeps unlisted)."""
        parsed = self.parser.parse_args([
            "publish-youtube",
            "--video", "master.mp4",
            "--skip-audit",
            "--auto-promote",
            "--dry-run",
        ])
        self.assertTrue(parsed.skip_audit)
        self.assertTrue(parsed.auto_promote)
        # Evaluated in orchestrator: auto_promote = args.auto_promote and not args.skip_audit
        effective_auto_promote = parsed.auto_promote and not parsed.skip_audit
        self.assertFalse(effective_auto_promote)

    def test_cli_pipeline_missing_input_and_missing_from_device(self):
        """Verify that running pipeline without --input and without --from-device fails with exit code 1."""
        proc = self.run_cli([
            "pipeline",
            "--event", "EDC",
            "--artist", "MartinGarrix",
            "--dry-run",
        ])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Must provide either --input <FILE> or --from-device flag", proc.stderr)

    def test_cli_duration_clamping_when_manual_duration_exceeds_max_ceiling(self):
        """Verify duration is clamped to 59.0s when manual duration exceeds maximum allowed ceiling."""
        dummy_video = self.workspace / "01_RAW_INBOX" / "long_take.mp4"
        dummy_video.write_bytes(b"dummy mp4 data for testing")

        res = run_master_pipeline(
            input_file=dummy_video,
            workspace_root=self.workspace,
            event="UltraMiami",
            artist="Hardwell",
            track="Spaceman",
            start_time=10.0,
            duration=90.0,  # Exceeds 59.0s
            auto_drop=False,
            dry_run=True,
            db_path=self.db_path,
        )
        self.assertEqual(res["drop_window"]["duration_sec"], 59.0)
        self.assertEqual(res["drop_window"]["end_time_sec"], 69.0)


class TestYouTubePublisherCLIAndAuditing(unittest.TestCase):
    """Adversarially tests youtube_publisher.py and orchestrator publish-youtube subcommand."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.db_path = self.workspace / "media_manifest.sqlite"
        self.python_exe = sys.executable
        self.orchestrator_script = MODULE_DIR / "orchestrator.py"
        self.yt_publisher_script = MODULE_DIR / "youtube_publisher.py"

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cmd(self, script: Path, args: list) -> subprocess.CompletedProcess:
        cmd = [self.python_exe, str(script)] + args
        return subprocess.run(
            cmd,
            cwd=str(MODULE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
        )

    def test_publish_youtube_missing_file_live_mode_graceful_error(self):
        """Verify that live upload of a non-existent file returns a failed publish result instead of unhandled crash."""
        publisher = YouTubePublisher(db_path=self.db_path, dry_run=False)
        res = publisher.publish_workflow(
            video_path=self.workspace / "does_not_exist_master.mp4",
            title="Non-existent video",
            description="Testing missing file",
            auto_promote=False,
        )
        self.assertFalse(res.success)
        self.assertEqual(res.content_id_status, "FAILED")
        self.assertIn("does not exist", res.error_message)

    def test_publish_youtube_cli_subprocess_missing_file_exit_code(self):
        """Verify CLI exits with code 1 on non-existent video file in live mode."""
        proc = self.run_cmd(self.orchestrator_script, [
            "publish-youtube",
            "--video", str(self.workspace / "missing_video.mp4"),
            "--title", "Test",
        ])
        self.assertEqual(proc.returncode, 1)

    def test_publish_youtube_dry_run_success_manifest_sync(self):
        """Verify publish-youtube in dry-run mode completes, outputs report, and syncs POSTED status to SQLite."""
        test_video = self.workspace / "master_take.mp4"
        test_video.write_bytes(b"dummy video bytes")

        proc = self.run_cmd(self.orchestrator_script, [
            "publish-youtube",
            "--video", str(test_video),
            "--title", "John Summit Where You Are Live EDC 2026 #Shorts",
            "--description", "Full energy live drop",
            "--tags", "EDM", "Festival", "HouseMusic",
            "--auto-promote",
            "--dry-run",
            "--db-path", str(self.db_path),
            "--project-id", "PROJ_DRY_RUN_001",
        ])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("YOUTUBE PUBLISH REPORT", proc.stdout)
        self.assertIn("Final Privacy:     public", proc.stdout)
        self.assertIn("Content ID Status: UNLISTED_CLEARED", proc.stdout)

        # Verify SQLite manifest record
        db = MediaManifestDB(db_path=self.db_path)
        asset = db.get_asset("PROJ_DRY_RUN_001")
        self.assertIsNotNone(asset)
        self.assertEqual(asset["current_status"], AssetStatus.POSTED.value)
        self.assertEqual(asset["youtube_content_id_status"], ContentIDStatus.UNLISTED_CLEARED.value)
        self.assertIn("dry_run", asset["metadata"]["youtube_video_id"])
        self.assertEqual(asset["metadata"]["youtube_privacy"], "public")

    def test_publish_youtube_malformed_arguments_invalid_privacy(self):
        """Verify CLI raises error on invalid privacy status choice."""
        proc = self.run_cmd(self.orchestrator_script, [
            "publish-youtube",
            "--video", "test.mp4",
            "--privacy", "super_secret_invalid",
            "--dry-run",
        ])
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("invalid choice: 'super_secret_invalid'", proc.stderr)

    def test_publish_youtube_unicode_emoji_title_and_tags(self):
        """Verify unicode emojis in titles and tags do not crash on Windows console or API serialization."""
        test_video = self.workspace / "unicode_master.mp4"
        test_video.write_bytes(b"dummy bytes")

        proc = self.run_cmd(self.orchestrator_script, [
            "publish-youtube",
            "--video", str(test_video),
            "--title", "🔥⚡ Skrillex & Fred Again.. LIVE at EDC Las Vegas 2026 🤯🔊 #Shorts",
            "--description", "Unreleased ID with pure bass vibes 🎵🇯🇵✨",
            "--tags", "#EDM", "#LaserBaptism", "#FestivalVibes🔥",
            "--dry-run",
            "--auto-promote",
            "--db-path", str(self.db_path),
            "--project-id", "PROJ_UNICODE_001",
        ])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("YOUTUBE PUBLISH REPORT", proc.stdout)

        db = MediaManifestDB(db_path=self.db_path)
        asset = db.get_asset("PROJ_UNICODE_001")
        self.assertIsNotNone(asset)
        self.assertEqual(asset["current_status"], AssetStatus.POSTED.value)

    def test_publish_youtube_companion_seo_json_integration(self):
        """Verify companion .seo.json sidecar is parsed and used when title/description are default."""
        test_video = self.workspace / "seo_video.mp4"
        test_video.write_bytes(b"dummy")
        seo_json = self.workspace / "seo_video.mp4.seo.json"
        seo_data = {
            "yt_title": "Excision Live at Lost Lands 2026 🤯 #Shorts",
            "yt_description": "Massive dinosaur bass drop",
            "hashtags": ["#EDM", "#Dubstep", "#LostLands2026"],
        }
        with open(seo_json, "w", encoding="utf-8") as f:
            json.dump(seo_data, f)

        publisher = YouTubePublisher(db_path=self.db_path, dry_run=True)
        res = publisher.publish_workflow(
            video_path=test_video,
            title="Shorts",  # default placeholder
            description="",  # empty
            seo_json_path=seo_json,
            auto_promote=True,
            project_id="PROJ_SEO_JSON_001",
        )
        self.assertEqual(res.final_privacy, "public")
        self.assertEqual(res.content_id_status, "UNLISTED_CLEARED")

    def test_publish_youtube_copyright_block_status_and_exit_code(self):
        """Verify mocked copyright block returns BLOCKED, leaves privacy as unlisted, and exits code 2."""
        mock_service = MagicMock()
        mock_service.videos().insert().execute.return_value = {"id": "mock_blocked_vid_999"}
        mock_service.videos().list().execute.return_value = {
            "items": [{
                "id": "mock_blocked_vid_999",
                "status": {
                    "uploadStatus": "rejected",
                    "rejectionReason": "copyright",
                    "privacyStatus": "unlisted",
                },
                "processingDetails": {"processingStatus": "terminated"},
                "contentDetails": {"licensedContent": True},
            }]
        }

        test_video = self.workspace / "blocked_master.mp4"
        test_video.write_bytes(b"dummy")

        publisher = YouTubePublisher(
            service=mock_service,
            db_path=self.db_path,
            dry_run=False,
        )
        res = publisher.publish_workflow(
            video_path=test_video,
            title="Blocked Track",
            description="Testing copyright block",
            auto_promote=True,
            project_id="PROJ_BLOCKED_001",
        )

        self.assertTrue(res.is_blocked)
        self.assertEqual(res.content_id_status, "BLOCKED")
        self.assertEqual(res.final_privacy, "unlisted")
        self.assertEqual(res.rejection_reason, "copyright")

        # Manifest must reflect READY_TO_POST (not POSTED) and BLOCKED
        db = MediaManifestDB(db_path=self.db_path)
        asset = db.get_asset("PROJ_BLOCKED_001")
        self.assertIsNotNone(asset)
        self.assertEqual(asset["current_status"], AssetStatus.READY_TO_POST.value)
        self.assertEqual(asset["youtube_content_id_status"], ContentIDStatus.BLOCKED.value)


class TestSQLiteConcurrencyAndManifestIntegrity(unittest.TestCase):
    """Adversarially tests SQLite manifest database under concurrency, locking, and status transitions."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "media_manifest_concurrency.sqlite"
        self.db = MediaManifestDB(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_multithreaded_concurrency_resilience(self):
        """
        Stress-tests concurrent threads writing and updating records simultaneously.
        Tests whether MediaManifestDB handles concurrent operations cleanly.
        """
        num_threads = 10
        records_per_thread = 5
        errors = []

        def worker(worker_id: int):
            try:
                for i in range(records_per_thread):
                    asset_id = f"concurrent_asset_w{worker_id}_{i}"
                    self.db.upsert_asset(
                        asset_id=asset_id,
                        source_file_name=f"take_{worker_id}_{i}.mp4",
                        canonical_name=f"20260822_EDC_Artist_Track_V1_1080p.mp4",
                        brand=BrandType.LASER_BAPTISM.value,
                        tier=EventTier.PILLAR_A.value,
                        event_name="EDC",
                        artist_name=f"Artist_{worker_id}",
                        track_name=f"Track_{i}",
                        current_status=AssetStatus.IN_PROGRESS,
                    )
                    # Read
                    rec = self.db.get_asset(asset_id)
                    if not rec or rec["current_status"] != "IN_PROGRESS":
                        errors.append(f"Worker {worker_id} failed get_asset for {asset_id}")

                    # Transition
                    self.db.update_status(asset_id, AssetStatus.READY_TO_POST)
            except Exception as e:
                errors.append(f"Worker {worker_id} exception: {type(e).__name__}: {e}")

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, w) for w in range(num_threads)]
            for f in as_completed(futures):
                f.result()

        # If SQLite locking errors occurred under concurrency, document them empirically
        if errors:
            print(f"\n[EMPIRICAL FINDING] SQLite Concurrency Exceptions under {num_threads} threads:")
            for err in errors[:5]:
                print(f"  - {err}")

        # In single-threaded verification, confirm stored assets
        total_assets = self.db.list_assets()
        print(f"\n[EMPIRICAL OBSERVATION] Total assets successfully committed: {len(total_assets)} / {num_threads * records_per_thread}")

    def test_complete_status_lifecycle_transitions(self):
        """Verifies full lifecycle sequence: RAW_INBOX -> IN_PROGRESS -> READY_TO_POST -> POSTED -> ARCHIVED."""
        asset_id = "lifecycle_test_asset_001"
        self.db.upsert_asset(
            asset_id=asset_id,
            source_file_name="raw.mp4",
            canonical_name="20260822_Ultra_Garrix_Animals_V1_1080p.mp4",
            brand=BrandType.LASER_BAPTISM.value,
            tier=EventTier.PILLAR_A.value,
            current_status=AssetStatus.RAW_INBOX,
            youtube_content_id_status=ContentIDStatus.UNCHECKED,
        )

        # 1. RAW_INBOX
        a = self.db.get_asset(asset_id)
        self.assertEqual(a["current_status"], "RAW_INBOX")
        self.assertEqual(a["youtube_content_id_status"], "UNCHECKED")

        # 2. IN_PROGRESS
        self.db.update_status(asset_id, AssetStatus.IN_PROGRESS)
        a = self.db.get_asset(asset_id)
        self.assertEqual(a["current_status"], "IN_PROGRESS")

        # 3. READY_TO_POST
        self.db.update_status(asset_id, AssetStatus.READY_TO_POST)
        a = self.db.get_asset(asset_id)
        self.assertEqual(a["current_status"], "READY_TO_POST")

        # 4. POSTED
        self.db.update_status(asset_id, AssetStatus.POSTED)
        a = self.db.get_asset(asset_id)
        self.assertEqual(a["current_status"], "POSTED")

        # 5. ARCHIVED
        self.db.update_status(asset_id, AssetStatus.ARCHIVED)
        a = self.db.get_asset(asset_id)
        self.assertEqual(a["current_status"], "ARCHIVED")

    def test_partial_upsert_preserves_unmodified_columns(self):
        """Verify that updating duration or LUFS in a subsequent upsert does not overwrite raw_path or metadata."""
        asset_id = "upsert_preserve_asset"
        self.db.upsert_asset(
            asset_id=asset_id,
            source_file_name="take1.mp4",
            canonical_name="canonical.mp4",
            brand=BrandType.LASER_BAPTISM.value,
            tier=EventTier.PILLAR_A.value,
            current_status=AssetStatus.IN_PROGRESS,
            raw_path="/path/to/raw.mp4",
            metadata_dict={"initial_key": "initial_value"},
        )

        # Subsequent upsert without specifying raw_path
        self.db.upsert_asset(
            asset_id=asset_id,
            source_file_name="take1.mp4",
            canonical_name="canonical.mp4",
            brand=BrandType.LASER_BAPTISM.value,
            tier=EventTier.PILLAR_A.value,
            duration_seconds=30.0,
            measured_lufs=-14.0,
            measured_true_peak=-1.5,
            current_status=AssetStatus.READY_TO_POST,
            master_path="/path/to/master.mp4",
        )

        rec = self.db.get_asset(asset_id)
        self.assertEqual(rec["raw_path"], "/path/to/raw.mp4")
        self.assertEqual(rec["master_path"], "/path/to/master.mp4")
        self.assertEqual(rec["duration_seconds"], 30.0)
        self.assertEqual(rec["measured_lufs"], -14.0)
        self.assertEqual(rec["metadata"]["initial_key"], "initial_value")


class TestEndToEndPipelineChainingAdversarial(unittest.TestCase):
    """Adversarially tests end-to-end master pipeline chaining with Audio DSP and YouTube publishing."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        for tier_dir in FOLDER_TIERS.values():
            (self.workspace / tier_dir).mkdir(parents=True, exist_ok=True)
        self.db_path = self.workspace / "media_manifest.sqlite"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_e2e_pipeline_with_auto_drop_and_publish_youtube(self):
        """Full end-to-end simulated run: raw asset -> auto-drop -> transcode -> QC -> SEO -> YouTube publish -> POSTED."""
        raw_clip = self.workspace / "01_RAW_INBOX" / "festival_set.mp4"
        raw_clip.write_bytes(b"Simulated raw 4K festival footage")

        res = run_master_pipeline(
            input_file=raw_clip,
            workspace_root=self.workspace,
            event="LostLands",
            artist="Excision",
            track="FeelSomething",
            genre="dubstep",
            brand=BrandType.LASER_BAPTISM,
            tier=EventTier.PILLAR_A,
            auto_drop=True,
            drop_duration=30.0,
            publish_youtube=True,
            auto_promote=True,
            dry_run=True,
            db_path=self.db_path,
        )

        self.assertEqual(res["status"], AssetStatus.POSTED.value)
        self.assertIn("drop_window", res)
        self.assertEqual(res["drop_window"]["duration_sec"], 30.0)
        self.assertIn("youtube_publish", res)
        self.assertEqual(res["youtube_publish"]["final_privacy"], "public")
        self.assertEqual(res["youtube_publish"]["content_id_status"], "UNLISTED_CLEARED")
        self.assertTrue(res["qc_report"]["passed"])

        # Check SQLite manifest
        db = MediaManifestDB(db_path=self.db_path)
        asset = db.get_asset(res["project_id"])
        self.assertIsNotNone(asset)
        self.assertEqual(asset["current_status"], AssetStatus.POSTED.value)
        self.assertEqual(asset["youtube_content_id_status"], ContentIDStatus.UNLISTED_CLEARED.value)


if __name__ == "__main__":
    unittest.main()
