"""
test_ingest.py - Unit tests for asset ingestion, filename normalization, and directory health.
"""

from pathlib import Path
import tempfile
import unittest

from config import BrandType, EventTier, MAX_FOLDER_ITEMS
from ingest_assets import (
    AssetIngestionRouter,
    DirectoryHealthGuard,
    FilenameNormalizer,
    StreamProbeData,
    calculate_sha256,
)


class TestIngestAssets(unittest.TestCase):
    """Tests filename parsing, generation, folder capacity guards, and checksums."""

    def test_canonical_filename_parsing(self):
        valid_name = "20260821_EDCOrlando_JohnSummit_WhereYouAre_V1_1080p.mp4"
        parsed = FilenameNormalizer.parse_filename(valid_name)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["date"], "20260821")
        self.assertEqual(parsed["event"], "EDCOrlando")
        self.assertEqual(parsed["artist"], "JohnSummit")
        self.assertEqual(parsed["track"], "WhereYouAre")
        self.assertEqual(parsed["version"], 1)
        self.assertEqual(parsed["resolution"], "1080p")
        self.assertEqual(parsed["ext"], "mp4")

    def test_canonical_filename_parsing_4k(self):
        valid_name = "20260822_Tomorrowland_Garrix_Animals_V2_4k.mov"
        parsed = FilenameNormalizer.parse_filename(valid_name)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["resolution"], "4k")
        self.assertEqual(parsed["ext"], "mov")

    def test_non_canonical_filename_parsing(self):
        invalid_name = "IMG_4920.MOV"
        parsed = FilenameNormalizer.parse_filename(invalid_name)
        self.assertIsNone(parsed)

    def test_canonical_filename_builder(self):
        built = FilenameNormalizer.build_canonical_filename(
            event="EDC Las Vegas",
            artist="sub focus",
            track="Desire",
            resolution="1080p",
            version=1,
            date_str="20260822",
            ext="mp4",
        )
        self.assertEqual(built, "20260822_EdcLasVegas_SubFocus_Desire_V1_1080p.mp4")

    def test_token_sanitization(self):
        self.assertEqual(FilenameNormalizer.sanitize_token("John Summit!"), "JohnSummit")
        self.assertEqual(FilenameNormalizer.sanitize_token("   "), "Unknown")
        self.assertEqual(FilenameNormalizer.sanitize_token("Lost-Lands_2026"), "LostLands2026")

    def test_directory_health_guard_partitioning(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_p = Path(tmp_dir)
            guard = DirectoryHealthGuard(max_items=3)  # Low cap for test

            # Allocate folder under 3 items
            sub_1 = guard.get_healthy_subfolder(base_p, "TestEvent")
            self.assertEqual(sub_1.name, "TestEvent")

            # Fill folder to cap (3 items)
            for i in range(3):
                (sub_1 / f"file_{i}.mp4").write_text("test")

            # Next request should branch to Batch02
            sub_2 = guard.get_healthy_subfolder(base_p, "TestEvent")
            self.assertEqual(sub_2.name, "TestEvent_Batch02")

            # Fill Batch02 to cap
            for i in range(3):
                (sub_2 / f"file_{i}.mp4").write_text("test")

            # Next request should branch to Batch03
            sub_3 = guard.get_healthy_subfolder(base_p, "TestEvent")
            self.assertEqual(sub_3.name, "TestEvent_Batch03")

    def test_sha256_checksum(self):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"EDM Media Engineering Pipeline Test Data")
            tf_path = Path(tf.name)

        try:
            h = calculate_sha256(tf_path)
            self.assertIsInstance(h, str)
            self.assertEqual(len(h), 64)  # 64 hex characters
        finally:
            tf_path.unlink(missing_ok=True)

    def test_stream_probe_data_properties(self):
        data = StreamProbeData(
            file_path="dummy.mp4",
            file_size_bytes=1024,
            duration_seconds=30.0,
            width=1080,
            height=1920,
            aspect_ratio="9:16",
            frame_rate=60.0,
            video_codec="hevc",
            pix_fmt="yuv420p10le",
            color_space="bt2020nc",
            color_transfer="arib-std-b67",
            color_primaries="bt2020",
            is_hdr=True,
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            audio_bitrate_kbps=320,
            sha256_hash="abc",
            creation_time="2026-08-22T00:00:00",
        )
        self.assertEqual(data.resolution_label, "1080p")
        self.assertTrue(data.is_hdr)

    def test_store_raw_asset_directory_structure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir)
            router = AssetIngestionRouter(workspace_root=ws)
            raw_src = ws / "sample_4k_source.mp4"
            raw_src.write_text("sample 4k hdr video payload")

            stored_dest = router.store_raw_asset(
                source_path=raw_src,
                event_name="Ultra Miami",
                artist_name="Martin Garrix",
                canonical_filename="20260822_UltraMiami_MartinGarrix_Animals_V1_4k.mp4",
            )
            expected_dest = ws / "01_RAW" / "UltraMiami" / "MartinGarrix" / "20260822_UltraMiami_MartinGarrix_Animals_V1_4k.mp4"
            self.assertEqual(stored_dest, expected_dest)
            self.assertTrue(stored_dest.is_file())
            self.assertEqual(stored_dest.read_text(), "sample 4k hdr video payload")

    def test_store_raw_asset_token_sanitization(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir)
            router = AssetIngestionRouter(workspace_root=ws)
            raw_src = ws / "test.mp4"
            raw_src.write_text("data")

            stored_dest = router.store_raw_asset(
                source_path=raw_src,
                event_name="EDC Las Vegas 2026!",
                artist_name="Sub Focus / Wilkinson",
                canonical_filename="20260822_EdcLasVegas2026_SubFocusWilkinson_Desire_V1_4k.mp4",
            )
            self.assertEqual(
                stored_dest,
                ws / "01_RAW" / "EdcLasVegas2026" / "SubFocusWilkinson" / "20260822_EdcLasVegas2026_SubFocusWilkinson_Desire_V1_4k.mp4",
            )

    def test_store_raw_asset_immutability(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir)
            router = AssetIngestionRouter(workspace_root=ws)
            raw_src = ws / "untouched_4k.mp4"
            raw_src.write_bytes(b"IMMUTABLE_4K_HDR_MASTER_DATA" * 50)
            initial_hash = calculate_sha256(raw_src)

            stored_dest = router.store_raw_asset(
                source_path=raw_src,
                event_name="Tomorrowland",
                artist_name="Alesso",
                canonical_filename="20260822_Tomorrowland_Alesso_Heroes_V1_4k.mp4",
            )
            stored_hash = calculate_sha256(stored_dest)
            self.assertEqual(initial_hash, stored_hash)

    def test_ingest_asset_includes_raw_storage_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir)
            router = AssetIngestionRouter(workspace_root=ws)
            raw_src = ws / "input.mp4"
            raw_src.write_text("raw footage content")

            res = router.ingest_asset(
                source_path=raw_src,
                event_name="Lost Lands",
                artist_name="Excision",
                track_name="Feel Something",
                dry_run=True,
            )
            self.assertIsNotNone(res.raw_storage_path)
            self.assertIn("01_RAW", res.raw_storage_path)
            self.assertIn("LostLands", res.raw_storage_path)
            self.assertIn("Excision", res.raw_storage_path)


if __name__ == "__main__":
    unittest.main()
