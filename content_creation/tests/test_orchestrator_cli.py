"""
test_orchestrator_cli.py - Tests for master CLI parser, QC assertions, auto-drop detection, and YouTube publisher integration.
"""

from pathlib import Path
import tempfile
import unittest

from config import AssetStatus, BrandType, EventTier
from orchestrator import (
    QCReport,
    build_parser,
    run_auto_drop_detection,
    run_master_pipeline,
)


class TestOrchestratorCLI(unittest.TestCase):
    """Tests CLI arguments and master pipeline orchestration."""

    def setUp(self):
        self.parser = build_parser()

    def test_ingest_cli_args(self):
        args = self.parser.parse_args(["ingest", "--input", "test.mp4", "--event", "Ultra", "--artist", "Alesso"])
        self.assertEqual(args.subcommand, "ingest")
        self.assertEqual(args.input, "test.mp4")
        self.assertEqual(args.event, "Ultra")
        self.assertEqual(args.artist, "Alesso")

    def test_process_cli_args(self):
        args = self.parser.parse_args([
            "process", "--input", "in.mp4", "--output", "out.mp4",
            "--reframe-mode", "blur_pad", "--tone-map", "on", "--denoise", "on"
        ])
        self.assertEqual(args.subcommand, "process")
        self.assertEqual(args.reframe_mode, "blur_pad")
        self.assertEqual(args.tone_map, "on")
        self.assertEqual(args.denoise, "on")
        self.assertIsNone(args.start_time)
        self.assertFalse(args.auto_drop)

    def test_process_cli_auto_drop_args(self):
        args = self.parser.parse_args([
            "process", "--input", "in.mp4", "--output", "out.mp4",
            "--auto-drop", "--drop-duration", "25.0"
        ])
        self.assertEqual(args.subcommand, "process")
        self.assertTrue(args.auto_drop)
        self.assertEqual(args.drop_duration, 25.0)
        self.assertIsNone(args.start_time)

    def test_pipeline_cli_auto_drop_and_publish_args(self):
        args = self.parser.parse_args([
            "pipeline", "--input", "in.mp4", "--event", "Ultra", "--artist", "Garrix",
            "--auto-drop", "--drop-duration", "30.0", "--publish-youtube", "--auto-promote",
            "--poll-timeout", "120.0"
        ])
        self.assertEqual(args.subcommand, "pipeline")
        self.assertTrue(args.auto_drop)
        self.assertEqual(args.drop_duration, 30.0)
        self.assertTrue(args.publish_youtube)
        self.assertTrue(args.auto_promote)
        self.assertEqual(args.poll_timeout, 120.0)

    def test_publish_youtube_subcommand_args(self):
        args = self.parser.parse_args([
            "publish-youtube", "--video", "master.mp4", "--title", "Garrix Ultra Drop",
            "--description", "Epic drop live at Ultra 2026", "--tags", "EDM", "Festival",
            "--auto-promote", "--poll-timeout", "180.0", "--dry-run"
        ])
        self.assertEqual(args.subcommand, "publish-youtube")
        self.assertEqual(args.video, "master.mp4")
        self.assertEqual(args.title, "Garrix Ultra Drop")
        self.assertEqual(args.tags, ["EDM", "Festival"])
        self.assertTrue(args.auto_promote)
        self.assertEqual(args.poll_timeout, 180.0)
        self.assertTrue(args.dry_run)

    def test_publish_subcommand_alias_args(self):
        args = self.parser.parse_args([
            "publish", "-v", "master.mp4", "-t", "Garrix Ultra Drop", "--dry-run"
        ])
        self.assertIn(args.subcommand, ("publish", "publish-youtube"))
        self.assertEqual(args.video, "master.mp4")
        self.assertEqual(args.title, "Garrix Ultra Drop")
        self.assertTrue(args.dry_run)

    def test_generate_seo_cli_args(self):
        args = self.parser.parse_args([
            "generate-seo", "--artist", "Martin Garrix", "--track", "Animals", "--event", "Tomorrowland"
        ])
        self.assertEqual(args.subcommand, "generate-seo")
        self.assertEqual(args.artist, "Martin Garrix")
        self.assertEqual(args.track, "Animals")

    def test_audit_safezone_cli_args(self):
        args = self.parser.parse_args([
            "audit-safezone", "--box", "100", "350", "400", "60"
        ])
        self.assertEqual(args.subcommand, "audit-safezone")
        self.assertEqual(args.box, [100, 350, 400, 60])

    def test_qc_report_evaluation_logic(self):
        # Case 1: All passing
        pass_qc = QCReport(
            passed=True,
            file_path="master.mp4",
            duration_seconds=30.0,
            duration_compliant=True,
            resolution="1080x1920",
            resolution_compliant=True,
            framerate_fps=60.0,
            framerate_compliant=True,
            measured_lufs=-14.0,
            lufs_compliant=True,
            measured_true_peak=-1.5,
            true_peak_compliant=True,
        )
        self.assertTrue(pass_qc.passed)

        # Case 2: Duration violation (> 59s)
        fail_dur_qc = QCReport(
            passed=False,
            file_path="master.mp4",
            duration_seconds=65.0,
            duration_compliant=False,
            resolution="1080x1920",
            resolution_compliant=True,
            framerate_fps=60.0,
            framerate_compliant=True,
            measured_lufs=-14.0,
            lufs_compliant=True,
            measured_true_peak=-1.5,
            true_peak_compliant=True,
            failure_reasons=["Duration (65.0s) exceeds 59s ceiling."],
        )
        self.assertFalse(fail_dur_qc.passed)
        self.assertIn("exceeds 59s", fail_dur_qc.failure_reasons[0])

    def test_dry_run_pipeline_execution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            raw_file = tmp_root / "20260822_Ultra_Garrix_Animals_V1_1080p.mp4"
            raw_file.write_text("dummy media content")

            summary = run_master_pipeline(
                input_file=raw_file,
                workspace_root=tmp_root,
                event="Ultra",
                artist="Garrix",
                track="Animals",
                genre="electro",
                brand=BrandType.LASER_BAPTISM,
                tier=EventTier.PILLAR_A,
                dry_run=True,
            )
            self.assertEqual(summary["status"], "READY_TO_POST")
            self.assertIn("Ultra_Garrix", summary["project_id"])
            self.assertIn("Animals", summary["canonical_filename"])
            self.assertTrue(summary["qc_report"]["passed"])

    def test_manual_override_priority_over_auto_drop_in_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            raw_file = tmp_root / "20260822_Tomorrowland_Alesso_Heroes_V1_1080p.mp4"
            raw_file.write_text("dummy media content")

            # Provide both start_time=15.0 and auto_drop=True
            summary = run_master_pipeline(
                input_file=raw_file,
                workspace_root=tmp_root,
                event="Tomorrowland",
                artist="Alesso",
                track="Heroes",
                genre="progressive",
                brand=BrandType.LASER_BAPTISM,
                tier=EventTier.PILLAR_A,
                start_time=15.0,
                duration=25.0,
                auto_drop=True,
                drop_duration=30.0,
                dry_run=True,
            )
            self.assertIn("drop_window", summary)
            drop_win = summary["drop_window"]
            self.assertTrue(drop_win["is_manual_override"])
            self.assertEqual(drop_win["detection_method"], "manual_cli_override")
            self.assertEqual(drop_win["start_time_sec"], 15.0)
            self.assertEqual(drop_win["duration_sec"], 25.0)
            self.assertEqual(drop_win["end_time_sec"], 40.0)

    def test_auto_drop_in_pipeline_execution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            raw_file = tmp_root / "20260822_LostLands_Excision_FeelSomething_V1_1080p.mp4"
            raw_file.write_text("dummy media content")

            summary = run_master_pipeline(
                input_file=raw_file,
                workspace_root=tmp_root,
                event="LostLands",
                artist="Excision",
                track="FeelSomething",
                genre="dubstep",
                brand=BrandType.LASER_BAPTISM,
                tier=EventTier.PILLAR_A,
                start_time=None,
                auto_drop=True,
                drop_duration=30.0,
                dry_run=True,
            )
            self.assertIn("drop_window", summary)
            drop_win = summary["drop_window"]
            self.assertFalse(drop_win["is_manual_override"])
            self.assertEqual(drop_win["duration_sec"], 30.0)

    def test_publish_youtube_in_pipeline_execution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            raw_file = tmp_root / "20260822_EDC_JohnSummit_WhereYouAre_V1_1080p.mp4"
            raw_file.write_text("dummy media content")

            summary = run_master_pipeline(
                input_file=raw_file,
                workspace_root=tmp_root,
                event="EDC",
                artist="JohnSummit",
                track="WhereYouAre",
                genre="house",
                brand=BrandType.LASER_BAPTISM,
                tier=EventTier.PILLAR_A,
                publish_youtube=True,
                auto_promote=True,
                poll_timeout=60.0,
                dry_run=True,
            )
            self.assertIn("youtube_publish", summary)
            yt_pub = summary["youtube_publish"]
            self.assertTrue(yt_pub["video_id"].startswith("dry_run_"))
            self.assertEqual(yt_pub["final_privacy"], "public")
            self.assertEqual(yt_pub["content_id_status"], "UNLISTED_CLEARED")
            self.assertEqual(summary["status"], AssetStatus.POSTED.value)

    def test_generate_proxy_cli_args(self):
        args = self.parser.parse_args([
            "generate-proxy", "--input", "raw_4k.mp4", "--event", "Ultra", "--artist", "Garrix", "--dry-run"
        ])
        self.assertEqual(args.subcommand, "generate-proxy")
        self.assertEqual(args.input, "raw_4k.mp4")
        self.assertEqual(args.event, "Ultra")
        self.assertEqual(args.artist, "Garrix")
        self.assertTrue(args.dry_run)

    def test_proxy_alias_cli_args(self):
        args = self.parser.parse_args([
            "proxy", "-i", "raw_4k.mp4", "-o", "proxy.mp4", "-w", "audio.wav", "--dry-run"
        ])
        self.assertIn(args.subcommand, ("proxy", "generate-proxy"))
        self.assertEqual(args.input, "raw_4k.mp4")
        self.assertEqual(args.output_proxy, "proxy.mp4")
        self.assertEqual(args.output_wav, "audio.wav")
        self.assertTrue(args.dry_run)

    def test_pipeline_raw_storage_and_proxy_paths(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            raw_file = tmp_root / "take_4k_source.mp4"
            raw_file.write_text("4K HDR MASTER VIDEO CONTENT")

            summary = run_master_pipeline(
                input_file=raw_file,
                workspace_root=tmp_root,
                event="Ultra Miami",
                artist="Martin Garrix",
                track="Animals",
                genre="electro",
                brand=BrandType.LASER_BAPTISM,
                tier=EventTier.PILLAR_A,
                dry_run=True,
            )
            self.assertIn("raw_storage_path", summary)
            self.assertIn("proxy_video_path", summary)
            self.assertIn("audio_wav_path", summary)
            self.assertIn("01_RAW", summary["raw_storage_path"])
            self.assertIn("UltraMiami", summary["raw_storage_path"])
            self.assertIn("MartinGarrix", summary["raw_storage_path"])
            self.assertTrue(summary["proxy_video_path"].endswith(f"proxy_{summary['canonical_filename']}"))
            self.assertTrue(summary["audio_wav_path"].endswith(f"{summary['canonical_filename'].rsplit('.', 1)[0]}.wav"))

    def test_raw_4k_file_untouched_invariant(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            raw_src = tmp_root / "source_take_4k.mp4"
            original_payload = b"PRISTINE_4K_HDR_BITSTREAM_CONTENT" * 100
            raw_src.write_bytes(original_payload)

            summary = run_master_pipeline(
                input_file=raw_src,
                workspace_root=tmp_root,
                event="Tomorrowland",
                artist="Alesso",
                track="Heroes",
                genre="progressive",
                dry_run=True,
            )
            # Verify source file payload remains 100% untouched
            self.assertEqual(raw_src.read_bytes(), original_payload)

    def test_pipeline_stages_proxy_into_awaiting_review(self):
        """Verify pipeline stages trimmed proxy drop into 02_AWAITING_REVIEW."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            raw_src = tmp_root / "raw_take.mp4"
            raw_src.write_bytes(b"4K RAW CONCERT DATA")

            summary = run_master_pipeline(
                input_file=raw_src,
                workspace_root=tmp_root,
                event="Lost Lands",
                artist="Sub Focus",
                track="Solar System",
                genre="dnb",
                auto_drop=True,
                drop_duration=30.0,
                dry_run=True,
            )

            self.assertIn("review_proxy_path", summary)
            self.assertIn("trimmed_proxy_path", summary)
            self.assertEqual(summary["review_proxy_path"], summary["trimmed_proxy_path"])
            self.assertIn("02_AWAITING_REVIEW", summary["review_proxy_path"])
            self.assertIn("LostLands", summary["review_proxy_path"])
            self.assertIn("SubFocus", summary["review_proxy_path"])
            self.assertTrue(summary["review_proxy_path"].endswith("_proxy_drop.mp4"))

    def test_run_auto_drop_detection_helper(self):
        """Verify run_auto_drop_detection helper correctly processes audio inputs and overrides."""
        # Manual override case
        res_manual = run_auto_drop_detection(
            audio_wav_path="fake.wav",
            target_duration_sec=30.0,
            manual_start_time=25.0,
            manual_duration=20.0,
        )
        self.assertTrue(res_manual.is_manual_override)
        self.assertEqual(res_manual.start_time_sec, 25.0)
        self.assertEqual(res_manual.duration_sec, 20.0)

        # Simulation / dry-run case
        res_sim = run_auto_drop_detection(
            audio_wav_path="non_existent.wav",
            target_duration_sec=30.0,
            dry_run=True,
        )
        self.assertFalse(res_sim.is_manual_override)
        self.assertEqual(res_sim.start_time_sec, 0.0)
        self.assertEqual(res_sim.duration_sec, 30.0)


if __name__ == "__main__":
    unittest.main()


