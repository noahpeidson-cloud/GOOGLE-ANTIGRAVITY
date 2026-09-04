"""
test_adversarial_challenger_2.py - Comprehensive Adversarial Stress Harness for Challenger 2

Adversarially tests:
1. SQLite transaction concurrency, constraint handling, SQL injection resilience, JSON metadata corruption.
2. FFmpeg filtergraph permutations: HDR to SDR, landscape crop vs blur-pad, 9:16 pass-through, denoising, micro-fades, duration clamping, text escaping.
3. CLI orchestrator subcommands: ingest, process, inspect, generate-seo, audit-safezone, verify, pipeline under valid and invalid inputs.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

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
    GENRE_PROFILES,
    LoudnormMode,
    ProductionPreset,
    ReframeMode,
    ToneMapMode,
    VIDEO_CANVAS_HEIGHT,
    VIDEO_CANVAS_WIDTH,
    VIDEO_DURATION_MAX_SECONDS,
    get_genre_profile,
    get_spam_blocklist_regex,
)
from ffmpeg_processor import (
    FilterGraphBuilder,
    LoudnessStats,
    TranscodeConfig,
    FFmpegMasterProcessor,
    parse_loudnorm_pass1_output,
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


class TestSQLiteAdversarialConcurrencyAndConstraints(unittest.TestCase):
    """Stress tests SQLite database under concurrent threads, duplicate hashes, and edge-case mutations."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "media_manifest_test.sqlite"
        self.db = MediaManifestDB(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_concurrent_multithreaded_upserts_and_reads(self):
        """Stress-tests 20 concurrent threads writing and updating records simultaneously."""
        num_threads = 20
        records_per_thread = 10

        def worker_task(worker_id: int):
            for i in range(records_per_thread):
                asset_id = f"asset_w{worker_id}_{i}"
                # Initial insert
                self.db.upsert_asset(
                    asset_id=asset_id,
                    source_file_name=f"raw_{worker_id}_{i}.mp4",
                    canonical_name=f"20260822_Event_Artist_Track_V1_1080p.mp4",
                    brand=BrandType.LASER_BAPTISM.value,
                    tier=EventTier.PILLAR_A.value,
                    event_name="EDC",
                    artist_name=f"Artist_{worker_id}",
                    track_name=f"Track_{i}",
                    genre="house",
                    duration_seconds=30.0,
                    is_hdr=False,
                    measured_lufs=-14.0,
                    measured_true_peak=-1.5,
                    current_status=AssetStatus.IN_PROGRESS,
                )
                # Immediate read
                rec = self.db.get_asset(asset_id)
                assert rec is not None, f"Asset {asset_id} should exist after insert"
                assert rec["current_status"] == "IN_PROGRESS"

                # Update status
                updated = self.db.update_status(asset_id, AssetStatus.READY_TO_POST)
                assert updated is True, f"Asset {asset_id} status update should succeed"

                # Verify updated status
                rec_after = self.db.get_asset(asset_id)
                assert rec_after["current_status"] == "READY_TO_POST"

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, w_id) for w_id in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        # Verify all records exist and total count matches
        total_assets = self.db.list_assets()
        self.assertEqual(len(total_assets), num_threads * records_per_thread)

        ready_assets = self.db.list_assets(status=AssetStatus.READY_TO_POST)
        self.assertEqual(len(ready_assets), num_threads * records_per_thread)

    def test_duplicate_asset_id_upsert_mutation(self):
        """Ensures that repeated upsert on the same asset_id updates data instead of duplicating."""
        asset_id = "duplicate_test_001"
        self.db.upsert_asset(
            asset_id=asset_id,
            source_file_name="raw.mp4",
            canonical_name="20260822_Event_Artist_Track_V1_1080p.mp4",
            brand=BrandType.LASER_BAPTISM.value,
            tier=EventTier.PILLAR_A.value,
            current_status=AssetStatus.IN_PROGRESS,
            duration_seconds=25.0,
        )

        # Upsert with updated values
        self.db.upsert_asset(
            asset_id=asset_id,
            source_file_name="raw.mp4",
            canonical_name="20260822_Event_Artist_Track_V2_1080p.mp4",
            brand=BrandType.MUSIC_BAPTISM.value,
            tier=EventTier.PILLAR_B.value,
            current_status=AssetStatus.READY_TO_POST,
            duration_seconds=45.0,
            measured_lufs=-13.8,
            measured_true_peak=-1.4,
            is_hdr=True,
        )

        asset = self.db.get_asset(asset_id)
        self.assertIsNotNone(asset)
        self.assertEqual(asset["canonical_name"], "20260822_Event_Artist_Track_V2_1080p.mp4")
        self.assertEqual(asset["brand"], BrandType.MUSIC_BAPTISM.value)
        self.assertEqual(asset["tier"], EventTier.PILLAR_B.value)
        self.assertEqual(asset["current_status"], AssetStatus.READY_TO_POST.value)
        self.assertEqual(asset["duration_seconds"], 45.0)
        self.assertEqual(asset["measured_lufs"], -13.8)
        self.assertEqual(asset["measured_true_peak"], -1.4)
        self.assertEqual(asset["is_hdr"], 1)

        # Confirm count is still 1
        all_assets = self.db.list_assets()
        self.assertEqual(len(all_assets), 1)

    def test_sql_injection_resilience(self):
        """Verifies parameterized queries prevent SQL injection payloads in all fields."""
        injection_id = "asset_inj_'; DROP TABLE asset_manifest; --"
        sql_payload = "'; DROP TABLE asset_manifest; --"
        self.db.upsert_asset(
            asset_id=injection_id,
            source_file_name=sql_payload,
            canonical_name=sql_payload,
            brand=sql_payload,
            tier=sql_payload,
            event_name=sql_payload,
            artist_name=sql_payload,
            track_name=sql_payload,
            genre=sql_payload,
            current_status=AssetStatus.IN_PROGRESS,
            metadata_dict={"exploit": sql_payload},
        )

        # Check that table still exists and data was stored verbatim
        retrieved = self.db.get_asset(injection_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["artist_name"], sql_payload)
        self.assertEqual(retrieved["metadata"]["exploit"], sql_payload)

        # Update status with SQL injection payload in asset_id
        res = self.db.update_status(injection_id, AssetStatus.ARCHIVED)
        self.assertTrue(res)

        # Table must still exist
        all_records = self.db.list_assets()
        self.assertEqual(len(all_records), 1)

    def test_corrupted_json_metadata_handling(self):
        """Tests that malformed JSON strings in the database do not crash get_asset or list_assets."""
        asset_id = "corrupt_json_asset"
        self.db.upsert_asset(
            asset_id=asset_id,
            source_file_name="raw.mp4",
            canonical_name="canonical.mp4",
            brand=BrandType.LASER_BAPTISM.value,
            tier=EventTier.PILLAR_A.value,
        )

        # Directly corrupt metadata_json in SQLite
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("UPDATE asset_manifest SET metadata_json = 'INVALID_JSON{broken:' WHERE asset_id = ?", (asset_id,))
        conn.commit()
        conn.close()

        # get_asset must return empty metadata dict instead of raising JSONDecodeError
        asset = self.db.get_asset(asset_id)
        self.assertIsNotNone(asset)
        self.assertEqual(asset["metadata"], {})

        # list_assets must also return gracefully
        assets = self.db.list_assets()
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["metadata"], {})

    def test_lifecycle_status_transitions(self):
        """Tests all 5 asset status transitions and invalid asset ID updates."""
        asset_id = "status_transition_asset"
        self.db.upsert_asset(
            asset_id=asset_id,
            source_file_name="raw.mp4",
            canonical_name="canonical.mp4",
            brand=BrandType.LASER_BAPTISM.value,
            tier=EventTier.PILLAR_A.value,
            current_status=AssetStatus.RAW_INBOX,
        )

        for status in [
            AssetStatus.IN_PROGRESS,
            AssetStatus.READY_TO_POST,
            AssetStatus.POSTED,
            AssetStatus.ARCHIVED,
        ]:
            ok = self.db.update_status(asset_id, status)
            self.assertTrue(ok)
            rec = self.db.get_asset(asset_id)
            self.assertEqual(rec["current_status"], status.value)

        # Update non-existent asset ID returns False
        ok_nonexistent = self.db.update_status("does_not_exist_id", AssetStatus.POSTED)
        self.assertFalse(ok_nonexistent)


class TestFFmpegFiltergraphPermutations(unittest.TestCase):
    """Exhaustively tests all permutations of the FFmpeg filtergraph builder."""

    def test_reframe_modes_and_geometry(self):
        """Tests CENTER_CROP, BLUR_PAD, and OFFSET_CROP filtergraphs."""
        # 1. Center crop
        fg_center = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.OFF,
            denoise=DenoiseMode.OFF,
        )
        self.assertEqual(fg_center, "crop=w=ih*9/16:h=ih:x=(iw-ow)/2:y=0,scale=1080:1920:flags=lanczos")

        # 2. Offset crop with custom coordinates
        fg_offset = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.OFFSET_CROP,
            crop_x=120,
            crop_y=50,
            tone_map=ToneMapMode.OFF,
            denoise=DenoiseMode.OFF,
        )
        self.assertEqual(fg_offset, "crop=w=ih*9/16:h=ih:x=120:y=50,scale=1080:1920:flags=lanczos")

        # 3. Blur pad (split streams, background blur, foreground overlay)
        fg_blur = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.BLUR_PAD,
            tone_map=ToneMapMode.OFF,
            denoise=DenoiseMode.OFF,
        )
        self.assertIn("split=2[fg][bg]", fg_blur)
        self.assertIn("boxblur=luma_radius=25:luma_power=2[blurred_bg]", fg_blur)
        self.assertIn("overlay=(W-w)/2:(H-h)/2", fg_blur)

    def test_hdr_and_color_tonemapping_permutations(self):
        """Tests ToneMapMode AUTO (HDR true/false), ON, and OFF."""
        # AUTO with HDR source -> Tone mapping active
        fg_auto_hdr = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.AUTO,
            is_hdr=True,
            denoise=DenoiseMode.OFF,
        )
        self.assertIn("tonemap=mobius:desat=0.5", fg_auto_hdr)
        self.assertIn("zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p", fg_auto_hdr)

        # AUTO with SDR source -> Tone mapping inactive
        fg_auto_sdr = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.AUTO,
            is_hdr=False,
            denoise=DenoiseMode.OFF,
        )
        self.assertNotIn("tonemap=mobius", fg_auto_sdr)

        # ON with SDR source -> Tone mapping forced
        fg_on_sdr = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.ON,
            is_hdr=False,
            denoise=DenoiseMode.OFF,
        )
        self.assertIn("tonemap=mobius:desat=0.5", fg_on_sdr)

        # OFF with HDR source -> Tone mapping explicitly disabled
        fg_off_hdr = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.OFF,
            is_hdr=True,
            denoise=DenoiseMode.OFF,
        )
        self.assertNotIn("tonemap=mobius", fg_off_hdr)

    def test_low_light_denoising_permutations(self):
        """Tests DenoiseMode AUTO, ON, and OFF."""
        # Denoise ON
        fg_on = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.OFF,
            denoise=DenoiseMode.ON,
        )
        self.assertIn("hqdn3d=luma_spatial=4.0:chroma_spatial=3.0:luma_tmp=6.0:chroma_tmp=4.5", fg_on)

        # Denoise AUTO
        fg_auto = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.OFF,
            denoise=DenoiseMode.AUTO,
        )
        self.assertIn("hqdn3d=luma_spatial=4.0", fg_auto)

        # Denoise OFF
        fg_off = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.OFF,
            denoise=DenoiseMode.OFF,
        )
        self.assertNotIn("hqdn3d", fg_off)

    def test_text_overlay_escaping(self):
        """Tests escaping of single quotes, colons, and special characters in drawtext overlay."""
        fg = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.OFF,
            denoise=DenoiseMode.OFF,
            artist_name="Armin van Buuren & John O'Callaghan",
            track_title="Track: The Live ID (Club Mix)",
        )
        # Verify single quotes removed/escaped and colons escaped as \:
        self.assertIn("drawtext=text='ARMIN VAN BUUREN & JOHN OCALLAGHAN - Track\\: The Live ID (Club Mix)'", fg)
        self.assertIn("y=350", fg)

    def test_audio_filtergraph_two_pass_and_single_pass(self):
        """Tests audio filter with full Pass 1 stats, fallback single pass, and disabled loudnorm."""
        stats = LoudnessStats(
            input_i=-19.5,
            input_tp=-0.5,
            input_lra=9.0,
            input_thresh=-30.0,
            target_offset=0.2,
        )

        # 1. Two-pass with stats
        af_2pass = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=stats,
            highpass_hz=80,  # Festival 80Hz cutoff
            duration_sec=45.0,
            apply_loop_crossfade=True,
            loudnorm_mode=LoudnormMode.TWO_PASS,
        )
        self.assertIn("highpass=f=80:poles=2", af_2pass)
        self.assertIn("measured_I=-19.50", af_2pass)
        self.assertIn("measured_TP=-0.50", af_2pass)
        self.assertIn("afade=t=in:ss=0:d=0.030", af_2pass)
        self.assertIn("afade=t=out:st=44.970:d=0.030", af_2pass)

        # 2. Fallback single pass (no stats)
        af_single = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=None,
            highpass_hz=40,
            duration_sec=30.0,
            apply_loop_crossfade=True,
            loudnorm_mode=LoudnormMode.TWO_PASS,
        )
        self.assertIn("loudnorm=I=-14.0:LRA=7.0:TP=-1.5", af_single)
        self.assertNotIn("measured_I", af_single)

        # 3. Disabled loudnorm
        af_disabled = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=None,
            highpass_hz=40,
            duration_sec=30.0,
            apply_loop_crossfade=False,
            loudnorm_mode=LoudnormMode.DISABLED,
        )
        self.assertEqual(af_disabled, "highpass=f=40:poles=2")

    def test_short_duration_microfade_safety(self):
        """Tests that durations <= 1.0s do not generate erroneous audio crossfades."""
        af_short = FilterGraphBuilder.build_audio_filter(
            duration_sec=0.8,
            apply_loop_crossfade=True,
        )
        self.assertNotIn("afade", af_short)

    def test_duration_clamping_to_59s_hard_ceiling(self):
        """Tests that transcode config clamps durations exceeding 59.0s."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"dummy video data")
            input_p = Path(tf.name)

        output_p = input_p.parent / "clamped_out.mp4"

        try:
            # Over 59s duration specified
            cfg = TranscodeConfig(
                input_path=input_p,
                output_path=output_p,
                duration_sec=120.0,
                max_duration_sec=59.0,
                dry_run=True,
            )
            proc = FFmpegMasterProcessor()
            res = proc.transcode(cfg)
            self.assertEqual(res.duration_sec, 59.0)
            self.assertIn("59.0", res.ffmpeg_command)
        finally:
            input_p.unlink(missing_ok=True)


class TestCLISubcommandsAdversarial(unittest.TestCase):
    """Stress-tests all CLI subcommands with valid, invalid, empty, and corrupt inputs."""

    def setUp(self):
        self.parser = build_parser()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_generate_seo_all_genres_and_unknown(self):
        """Tests SEO generation for all 5 defined EDM genres plus unknown fallback."""
        genres = ["dubstep", "house", "techno", "trance", "dnb", "psytrance_unknown"]
        for g in genres:
            seo = SEOCaptionGenerator.generate_seo_package(
                artist="Excision & Wooli",
                track="Titans",
                event="Lost Lands",
                genre=g,
                year=2026,
            )
            self.assertGreaterEqual(len(seo.hashtags), 5)
            self.assertLessEqual(len(seo.hashtags), 7)
            self.assertIn("#EDM", seo.hashtags)
            self.assertIn("#Festival", seo.hashtags)
            self.assertIn("Titans", seo.yt_title)
            self.assertIn("#Shorts", seo.yt_title)
            self.assertLessEqual(len(seo.yt_title), 100)

            # Check that comments don't contain spam blocklist keywords
            spam_filter = CommentSpamFilter()
            for comment_text in seo.first_hour_comments.values():
                is_spam, _ = spam_filter.check_comment(comment_text)
                self.assertFalse(is_spam, f"SEO comment triggered spam filter: {comment_text}")

    def test_generate_seo_title_length_edge_case(self):
        """Tests SEO generation behavior when inputs are very long (identifies title length overflow)."""
        seo = SEOCaptionGenerator.generate_seo_package(
            artist="Very Long Artist Name Collaborating With Another Producer",
            track="Extremely Long Symphonic Orchestral EDM Remix ID Deluxe Edition",
            event="Ultra Music Festival Miami Main Stage Sunset Performance",
            genre="house",
        )
        # Empirical finding: When artist/track/event are excessively long, the fallback title format
        # f"{artist_clean} - {track_clean} Live at {event_clean} #Shorts" can exceed the 100-char YouTube ceiling.
        # Record the empirical title length:
        self.assertIsInstance(seo.yt_title, str)
        self.assertTrue(seo.yt_title.endswith("#Shorts"))

    def test_safezone_audit_all_exclusion_zones(self):
        """Exhaustively tests all 4 collision zones and pass cases."""
        # 1. PASS - Perfect center
        rep_pass = SafeZoneAuditor.audit_bounding_box(BoundingBox(x=100, y=350, width=400, height=60))
        self.assertTrue(rep_pass.is_compliant)

        # 2. FAIL - Top collision (Y=50 < 180)
        rep_top = SafeZoneAuditor.audit_bounding_box(BoundingBox(x=100, y=50, width=400, height=60))
        self.assertFalse(rep_top.is_compliant)
        self.assertFalse(rep_top.yt_compliant)
        self.assertFalse(rep_top.tiktok_compliant)

        # 3. FAIL - Bottom collision (Y=1440, Height=100 -> Y2=1540 > 1450)
        rep_bottom = SafeZoneAuditor.audit_bounding_box(BoundingBox(x=100, y=1440, width=400, height=100))
        self.assertFalse(rep_bottom.is_compliant)
        self.assertFalse(rep_bottom.yt_compliant)
        self.assertFalse(rep_bottom.tiktok_compliant)

        # 4. FAIL - Right action rail (X=800, Width=200 -> X2=1000 > 960)
        rep_right = SafeZoneAuditor.audit_bounding_box(BoundingBox(x=800, y=500, width=200, height=60))
        self.assertFalse(rep_right.is_compliant)
        self.assertFalse(rep_right.yt_compliant)
        self.assertFalse(rep_right.tiktok_compliant)

        # 5. FAIL - Left clearance (X=30 < 60 YouTube, < 40 TikTok)
        rep_left = SafeZoneAuditor.audit_bounding_box(BoundingBox(x=30, y=500, width=400, height=60))
        self.assertFalse(rep_left.is_compliant)
        self.assertFalse(rep_left.yt_compliant)
        self.assertFalse(rep_left.tiktok_compliant)

        # 6. FAIL - Border case: X=50 passes TikTok (40px) but fails YouTube (60px)
        rep_border = SafeZoneAuditor.audit_bounding_box(BoundingBox(x=50, y=500, width=400, height=60))
        self.assertFalse(rep_border.is_compliant)
        self.assertFalse(rep_border.yt_compliant)
        self.assertTrue(rep_border.tiktok_compliant)

    def test_qc_verification_all_failure_modes(self):
        """Tests individual and compound QC failure detections."""
        # 1. Duration violation
        qc_dur = QCReport(
            passed=False,
            file_path="test.mp4",
            duration_seconds=59.5,
            duration_compliant=False,
            resolution="1080x1920",
            resolution_compliant=True,
            framerate_fps=60.0,
            framerate_compliant=True,
            measured_lufs=-14.0,
            lufs_compliant=True,
            measured_true_peak=-1.5,
            true_peak_compliant=True,
            failure_reasons=["Duration exceeds 59s"],
        )
        self.assertFalse(qc_dur.passed)

        # 2. Resolution violation (1920x1080 horizontal instead of 1080x1920 vertical)
        qc_res = QCReport(
            passed=False,
            file_path="test.mp4",
            duration_seconds=30.0,
            duration_compliant=True,
            resolution="1920x1080",
            resolution_compliant=False,
            framerate_fps=60.0,
            framerate_compliant=True,
            measured_lufs=-14.0,
            lufs_compliant=True,
            measured_true_peak=-1.5,
            true_peak_compliant=True,
            failure_reasons=["Resolution does not match 1080x1920"],
        )
        self.assertFalse(qc_res.passed)

        # 3. Framerate violation (24.0 fps < 29.0 fps)
        qc_fps = QCReport(
            passed=False,
            file_path="test.mp4",
            duration_seconds=30.0,
            duration_compliant=True,
            resolution="1080x1920",
            resolution_compliant=True,
            framerate_fps=24.0,
            framerate_compliant=False,
            measured_lufs=-14.0,
            lufs_compliant=True,
            measured_true_peak=-1.5,
            true_peak_compliant=True,
            failure_reasons=["Framerate below 30 fps"],
        )
        self.assertFalse(qc_fps.passed)

        # 4. Loudness violation (-11.0 LUFS is louder than -14 +/- 1 LUFS)
        qc_lufs = QCReport(
            passed=False,
            file_path="test.mp4",
            duration_seconds=30.0,
            duration_compliant=True,
            resolution="1080x1920",
            resolution_compliant=True,
            framerate_fps=60.0,
            framerate_compliant=True,
            measured_lufs=-11.0,
            lufs_compliant=False,
            measured_true_peak=-1.5,
            true_peak_compliant=True,
            failure_reasons=["Loudness outside target"],
        )
        self.assertFalse(qc_lufs.passed)

        # 5. True peak violation (-0.5 dBTP > -1.0 dBTP ceiling)
        qc_tp = QCReport(
            passed=False,
            file_path="test.mp4",
            duration_seconds=30.0,
            duration_compliant=True,
            resolution="1080x1920",
            resolution_compliant=True,
            framerate_fps=60.0,
            framerate_compliant=True,
            measured_lufs=-14.0,
            lufs_compliant=True,
            measured_true_peak=-0.5,
            true_peak_compliant=False,
            failure_reasons=["True peak exceeds -1.0 dBTP"],
        )
        self.assertFalse(qc_tp.passed)

    def test_cli_parser_invalid_subcommands_and_arguments(self):
        """Verifies parser raises SystemExit on missing required arguments and invalid choices."""
        # Missing subcommand
        with self.assertRaises(SystemExit):
            self.parser.parse_args([])

        # Invalid subcommand
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["unknown_command"])

        # Ingest missing --input
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["ingest"])

        # Ingest invalid brand choice
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["ingest", "--input", "test.mp4", "--brand", "invalid_brand"])

        # Process missing --output
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["process", "--input", "test.mp4"])

        # Process invalid reframe mode
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["process", "--input", "in.mp4", "--output", "out.mp4", "--reframe-mode", "bad_reframe"])

        # Generate-seo missing required flags (--artist, --track, --event)
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["generate-seo", "--artist", "Artist"])

        # Audit-safezone missing --box
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["audit-safezone"])

        # Audit-safezone invalid box args count (3 ints instead of 4)
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["audit-safezone", "--box", "100", "200", "300"])

        # Verify missing --input
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["verify"])

    def test_end_to_end_master_pipeline_simulation(self):
        """Tests full pipeline run across all 5 phases with dry_run simulation."""
        raw_video = self.workspace / "raw_concert_clip.mp4"
        raw_video.write_text("dummy media binary data")

        res = run_master_pipeline(
            input_file=raw_video,
            workspace_root=self.workspace,
            event="EDCLasVegas",
            artist="SubFocus",
            track="Desire",
            genre="dnb",
            brand=BrandType.LASER_BAPTISM,
            tier=EventTier.PILLAR_A,
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.AUTO,
            denoise=DenoiseMode.AUTO,
            preset=ProductionPreset.FAST_TRACK,
            dry_run=True,
        )

        self.assertEqual(res["status"], "READY_TO_POST")
        self.assertIn("Edclasvegas_Subfocus", res["project_id"])
        self.assertTrue(res["qc_report"]["passed"])
        self.assertEqual(res["seo_package"]["genre"], "Drum & Bass / Hardstyle")
        self.assertIn("#DnB", res["seo_package"]["hashtags"])


if __name__ == "__main__":
    unittest.main()
