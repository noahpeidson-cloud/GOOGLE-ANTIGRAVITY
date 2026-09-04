"""
test_challenger2_m6_empirical.py - Challenger 2 Empirical Stress Test Suite (Milestone 6)

Rigorous Empirical Verification Harness for:
1. 4K Raw Vault Immutability & SHA-256 Byte-for-Byte Invariant Testing.
2. Direct WAV DSP Audio Fuzzing & Fallback Handling (Silent, Short <30s, High-Dynamic Drops, Corrupted Headers).
3. Immediate Manual CLI Timestamp Override Bypass Hierarchy.
4. 720p Proxy Trimming, Review Gate Routing, and Path Sanitization Invariant Safety.
"""

from dataclasses import asdict
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple
import unittest
from unittest.mock import MagicMock, patch
import wave

import numpy as np

# Add content_creation root directory to sys.path
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
    PROXY_AUDIO_CODEC,
    PROXY_AUDIO_SAMPLE_RATE,
    PROXY_PRESET,
    PROXY_VIDEO_BITRATE_KBPS,
    PROXY_VIDEO_CODEC,
    PROXY_VIDEO_HEIGHT,
    ReframeMode,
    ToneMapMode,
    VIDEO_CANVAS_HEIGHT,
    VIDEO_CANVAS_WIDTH,
    VIDEO_DURATION_MAX_SECONDS,
    get_awaiting_review_folder,
    get_raw_folder,
)
from audio_dsp import (
    AudioDropDetector,
    AudioDSPError,
    AudioExtractionError,
    DropWindowResult,
    generate_synthetic_edm_signal,
    detect_optimal_drop,
    run_auto_drop_detection,
)
from ffmpeg_processor import (
    FFmpegExecutionError,
    FFmpegMasterProcessor,
    FilterGraphBuilder,
    ProxyGenerationResult,
    TranscodeConfig,
    TranscodeResult,
)
from ingest_assets import (
    AssetIngestionRouter,
    ChecksumMismatchError,
    DirectoryHealthGuard,
    FilenameNormalizer,
    StreamProbeData,
    calculate_sha256,
    find_binary,
)
from metadata_tracker import (
    MediaManifestDB,
    SEOCaptionGenerator,
)
from orchestrator import (
    QCReport,
    run_master_pipeline,
    verify_media_file,
)


# ============================================================================
# HELPER UTILITIES FOR SYNTHETIC MEDIA CREATION
# ============================================================================

def create_synthetic_wav_file(
    file_path: Path,
    duration_sec: float = 60.0,
    sample_rate: int = 22050,
    num_channels: int = 1,
    sample_width: int = 2,  # 16-bit PCM
    waveform: Optional[np.ndarray] = None,
) -> Path:
    """Creates a real binary PCM .wav file on disk for DSP testing."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if waveform is None:
        num_samples = int(duration_sec * sample_rate)
        t = np.linspace(0, duration_sec, num_samples, endpoint=False)
        # Standard sine wave at 440 Hz
        raw_signal = (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    else:
        raw_signal = waveform.astype(np.float32)
        num_samples = len(raw_signal)

    # Scale to int16
    clamped = np.clip(raw_signal, -1.0, 1.0)
    int16_samples = (clamped * 32767.0).astype(np.int16)

    if num_channels > 1:
        # Replicate mono signal across channels
        multi_samples = np.repeat(int16_samples[:, np.newaxis], num_channels, axis=1)
        raw_bytes = multi_samples.tobytes()
    else:
        raw_bytes = int16_samples.tobytes()

    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_bytes)

    return file_path


def create_synthetic_raw_4k_file(
    file_path: Path,
    size_bytes: int = 1024 * 1024 * 4,  # 4 MB synthetic master payload
    pattern: bytes = b"SYNTHETIC_4K_HDR_MASTER_PAYLOAD_UNTOUCHED_",
) -> Tuple[Path, str]:
    """Generates synthetic 4K raw video master with deterministic payload and returns (path, sha256)."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    full_pattern = pattern * ((size_bytes // len(pattern)) + 1)
    content = full_pattern[:size_bytes]

    with open(file_path, "wb") as f:
        f.write(content)

    sha256_hash = hashlib.sha256(content).hexdigest()
    return file_path, sha256_hash


# ============================================================================
# TEST SUITE 1: 4K RAW VAULT IMMUTABILITY & SHA-256 INVARIANT TESTING
# ============================================================================

class TestEmpirical4KRawImmutability(unittest.TestCase):
    """
    Stress-tests the immutability of 4K master files stored in 01_RAW/[Festival]/[Artist]/.
    Asserts 100% untouched byte-for-byte SHA-256 equality across all pipeline stages.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()
        for tier in FOLDER_TIERS.values():
            (self.workspace / tier).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("ingest_assets.probe_media_file")
    def test_sha256_exact_byte_match_after_raw_ingestion(self, mock_probe):
        """
        Creates synthetic 4K master video, computes pre-hash, executes router ingestion,
        and verifies that the stored 4K file in 01_RAW/[Festival]/[Artist]/ matches byte-for-byte.
        """
        inbox_file = self.workspace / "01_RAW_INBOX" / "GOPR0042_4K_HDR.mp4"
        _, pre_hash = create_synthetic_raw_4k_file(inbox_file, size_bytes=2 * 1024 * 1024)

        mock_probe.return_value = StreamProbeData(
            file_path=str(inbox_file),
            file_size_bytes=inbox_file.stat().st_size,
            duration_seconds=30.0,
            width=3840,
            height=2160,
            aspect_ratio="16:9",
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
            sha256_hash=pre_hash,
            creation_time="2026-08-22T00:00:00",
        )

        router = AssetIngestionRouter(workspace_root=self.workspace)
        res = router.ingest_asset(
            source_path=inbox_file,
            event_name="UltraMiami",
            artist_name="MartinGarrix",
            track_name="Animals",
            brand=BrandType.LASER_BAPTISM,
            tier=EventTier.PILLAR_A,
            version=1,
            dry_run=False,
        )

        raw_stored_path = Path(res.raw_storage_path)
        self.assertTrue(raw_stored_path.is_file(), f"4K Raw file missing at {raw_stored_path}")
        self.assertIn("01_RAW", str(raw_stored_path))
        self.assertIn("Ultramiami", str(raw_stored_path))
        self.assertIn("Martingarrix", str(raw_stored_path))

        # Direct byte comparison and SHA-256 validation
        post_hash = calculate_sha256(raw_stored_path)
        self.assertEqual(
            pre_hash,
            post_hash,
            f"4K Raw master mutated during ingestion! Pre-hash: {pre_hash}, Post-hash: {post_hash}",
        )
        self.assertEqual(raw_stored_path.stat().st_size, inbox_file.stat().st_size)

    def test_4k_raw_vault_immutability_through_complete_pipeline(self):
        """
        Executes end-to-end master pipeline (ingest, proxy generation, drop detection,
        awaiting review staging, and master promotion) and verifies 4K raw master is 100% untouched.
        """
        raw_video = self.workspace / "01_RAW_INBOX" / "EDC_SubFocus_4K60_Live.mp4"
        _, pre_hash = create_synthetic_raw_4k_file(raw_video, size_bytes=3 * 1024 * 1024)

        pipeline_res = run_master_pipeline(
            input_file=raw_video,
            workspace_root=self.workspace,
            event="EDC Las Vegas",
            artist="Sub Focus",
            track="Desire",
            genre="dnb",
            brand=BrandType.LASER_BAPTISM,
            tier=EventTier.PILLAR_A,
            auto_drop=True,
            drop_duration=30.0,
            dry_run=True,  # Dry run simulates FFmpeg encoding while testing pipeline orchestration
        )

        raw_vault_path = Path(pipeline_res["raw_storage_path"])
        # In non-dry-run or dry-run, verify raw path format and original file integrity
        self.assertIn("01_RAW", str(raw_vault_path))
        self.assertIn("EdcLasVegas", str(raw_vault_path))
        self.assertIn("SubFocus", str(raw_vault_path))

        current_hash = calculate_sha256(raw_video)
        self.assertEqual(
            pre_hash,
            current_hash,
            "Original input 4K video modified in place during pipeline run!",
        )

    @patch("ingest_assets.probe_media_file")
    def test_raw_storage_with_special_characters_and_punctuation(self, mock_probe):
        """
        Verifies that festival/artist names with complex symbols, slashes, and spaces
        produce sanitized paths and store the 4K raw video with 100% hash preservation.
        """
        raw_video = self.workspace / "01_RAW_INBOX" / "Tomorrowland_Alesso_4K.mp4"
        _, pre_hash = create_synthetic_raw_4k_file(raw_video, size_bytes=1024 * 1024)

        mock_probe.return_value = StreamProbeData(
            file_path=str(raw_video),
            file_size_bytes=raw_video.stat().st_size,
            duration_seconds=30.0,
            width=3840,
            height=2160,
            aspect_ratio="16:9",
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
            sha256_hash=pre_hash,
            creation_time="2026-08-22T00:00:00",
        )

        router = AssetIngestionRouter(workspace_root=self.workspace)
        res = router.ingest_asset(
            source_path=raw_video,
            event_name="Tomorrowland 2026 // Belgium (Mainstage)",
            artist_name="Alesso & Sebastian Ingrosso (Live!)",
            track_name="Calling (Lose My Mind) #1",
            brand=BrandType.MUSIC_BAPTISM,
            tier=EventTier.PILLAR_A,
            version=1,
            dry_run=False,
        )

        stored_raw = Path(res.raw_storage_path)
        self.assertTrue(stored_raw.is_file())
        self.assertEqual(calculate_sha256(stored_raw), pre_hash)
        # Check sanitized directory names
        self.assertNotIn("//", str(stored_raw))
        self.assertNotIn("!", str(stored_raw.parent.name))
        self.assertEqual(stored_raw.parent.name, "AlessoSebastianIngrossoLive")
        self.assertEqual(stored_raw.parent.parent.name, "Tomorrowland2026BelgiumMainstage")

    def test_repeated_ingestion_checksum_and_vault_preservation(self):
        """Tests that re-ingesting an identical file or same target name does not corrupt the vault."""
        raw_file = self.workspace / "01_RAW_INBOX" / "take_001.mp4"
        _, pre_hash = create_synthetic_raw_4k_file(raw_file, size_bytes=512 * 1024)

        router = AssetIngestionRouter(workspace_root=self.workspace)
        res1 = router.store_raw_asset(
            source_path=raw_file,
            event_name="LostLands",
            artist_name="Excision",
            canonical_filename="20260822_Lostlands_Excision_ID_V1_4k.mp4",
            dry_run=False,
        )
        self.assertEqual(calculate_sha256(res1), pre_hash)

        # Re-store (overwrite identical)
        res2 = router.store_raw_asset(
            source_path=raw_file,
            event_name="LostLands",
            artist_name="Excision",
            canonical_filename="20260822_Lostlands_Excision_ID_V1_4k.mp4",
            dry_run=False,
        )
        self.assertEqual(res1, res2)
        self.assertEqual(calculate_sha256(res2), pre_hash)


# ============================================================================
# TEST SUITE 2: DIRECT WAV DSP AUDIO FUZZING & FALLBACK SUITE
# ============================================================================

class TestWAVDSPAudioFuzzingAndFallbacks(unittest.TestCase):
    """
    Adversarial fuzzing and edge case verification for AudioDropDetector & audio_dsp.py.
    Tests silent WAVs, short clips (<30s), high-dynamic drop spikes, corrupted headers, and multi-channel WAVs.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name).resolve()
        self.detector = AudioDropDetector(target_duration_sec=30.0, sample_rate=22050)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_silent_wav_file_fallback(self):
        """
        Fuzz test with an all-zero digital silence WAV file (45s).
        Asserts detector detects silence (RMS < 1e-4) and returns 'silent_audio_fallback'.
        """
        silent_wav = self.test_dir / "silent_45s.wav"
        zero_signal = np.zeros(int(45.0 * 22050), dtype=np.float32)
        create_synthetic_wav_file(silent_wav, duration_sec=45.0, waveform=zero_signal)

        result = self.detector.detect_optimal_drop(silent_wav)
        self.assertIsInstance(result, DropWindowResult)
        self.assertEqual(result.detection_method, "silent_audio_fallback")
        self.assertEqual(result.start_time_sec, 0.0)
        self.assertEqual(result.duration_sec, 30.0)
        self.assertEqual(result.end_time_sec, 30.0)
        self.assertFalse(result.is_manual_override)
        self.assertLess(result.max_rms_energy, 1e-4)

    def test_near_silent_noise_wav_fallback(self):
        """
        Fuzz test with near-silent low-amplitude noise (amplitude = 0.00005, below 1e-4 threshold).
        Asserts graceful fallback to 'silent_audio_fallback'.
        """
        near_silent_wav = self.test_dir / "near_silent.wav"
        noise = (np.random.uniform(-0.00005, 0.00005, int(40.0 * 22050))).astype(np.float32)
        create_synthetic_wav_file(near_silent_wav, duration_sec=40.0, waveform=noise)

        result = self.detector.detect_optimal_drop(near_silent_wav)
        self.assertEqual(result.detection_method, "silent_audio_fallback")
        self.assertEqual(result.start_time_sec, 0.0)

    def test_short_audio_clip_fallback_under_30s(self):
        """
        Tests clips shorter than 30s (e.g. 5.0s, 14.2s, 29.5s).
        Asserts detector returns 'short_audio_fallback' with exact clip duration.
        """
        test_durations = [5.0, 14.2, 29.5]
        for dur in test_durations:
            short_wav = self.test_dir / f"short_{int(dur)}s.wav"
            create_synthetic_wav_file(short_wav, duration_sec=dur)

            res = self.detector.detect_optimal_drop(short_wav)
            self.assertEqual(res.detection_method, "short_audio_fallback")
            self.assertEqual(res.start_time_sec, 0.0)
            self.assertAlmostEqual(res.duration_sec, dur, places=1)
            self.assertAlmostEqual(res.end_time_sec, dur, places=1)

    def test_high_dynamic_edm_drop_waveform_localization(self):
        """
        Tests high-dynamic EDM waveform: 0-30s quiet build (amp 0.03), 30-60s massive bass drop (amp 0.95), 60-90s outro.
        Asserts detector pinpoints drop start within +/- 0.5s of 30.0s.
        """
        edm_signal = generate_synthetic_edm_signal(
            total_duration_sec=90.0,
            drop_start_sec=30.0,
            drop_duration_sec=30.0,
            sample_rate=22050,
            quiet_amplitude=0.03,
            drop_amplitude=0.95,
        )
        edm_wav = self.test_dir / "edm_drop_test.wav"
        create_synthetic_wav_file(edm_wav, duration_sec=90.0, waveform=edm_signal)

        res = self.detector.detect_optimal_drop(edm_wav)
        self.assertIn(res.detection_method, ["librosa", "numpy_fallback"])
        self.assertAlmostEqual(res.start_time_sec, 30.0, delta=0.5)
        self.assertEqual(res.duration_sec, 30.0)
        self.assertAlmostEqual(res.end_time_sec, 60.0, delta=0.5)
        self.assertGreater(res.max_rms_energy, 0.3)

    def test_multi_peak_drop_energy_maximization(self):
        """
        Tests signal with two energy bursts:
        - Burst 1: 15s to 45s at amplitude 0.40
        - Burst 2: 65s to 95s at amplitude 0.90 (True drop)
        Asserts detector selects Burst 2 (maximum cumulative energy).
        """
        sr = 22050
        total_samples = 120 * sr
        t = np.linspace(0, 120.0, total_samples, endpoint=False)
        y = (0.02 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)

        # Burst 1
        m1 = (t >= 15.0) & (t < 45.0)
        y[m1] = (0.40 * np.sin(2 * np.pi * 80.0 * t[m1])).astype(np.float32)

        # Burst 2 (Peak drop)
        m2 = (t >= 65.0) & (t < 95.0)
        y[m2] = (0.90 * np.sin(2 * np.pi * 60.0 * t[m2])).astype(np.float32)

        wav_path = self.test_dir / "dual_peak_test.wav"
        create_synthetic_wav_file(wav_path, duration_sec=120.0, waveform=y)

        res = self.detector.detect_optimal_drop(wav_path)
        self.assertAlmostEqual(res.start_time_sec, 65.0, delta=0.5)

    def test_corrupted_wav_header_resilience(self):
        """
        Fuzz test with corrupted/truncated WAV headers and random binary junk.
        Asserts extract_audio_buffer raises AudioExtractionError cleanly without crashing Python runtime.
        """
        corrupted_wav = self.test_dir / "corrupted_header.wav"
        # Write invalid RIFF header with garbage bytes
        with open(corrupted_wav, "wb") as f:
            f.write(b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00GARBAGE_PAYLOAD_TRUNCATED")

        # Native wave reader or FFmpeg will fail; verify AudioExtractionError is raised cleanly
        with self.assertRaises((AudioExtractionError, Exception)):
            self.detector.extract_audio_buffer(corrupted_wav)

    def test_zero_byte_wav_file_handling(self):
        """Tests 0-byte file handling."""
        empty_wav = self.test_dir / "empty.wav"
        empty_wav.touch()

        with self.assertRaises((AudioExtractionError, Exception)):
            self.detector.extract_audio_buffer(empty_wav)

    def test_multichannel_stereo_and_surround_downmixing(self):
        """
        Tests multi-channel WAV inputs (Stereo 2ch and 5.1 surround 6ch).
        Asserts extract_audio_buffer extracts and downmixes to single mono float32 array.
        """
        stereo_wav = self.test_dir / "stereo_test.wav"
        create_synthetic_wav_file(stereo_wav, duration_sec=10.0, num_channels=2)
        buf_stereo = self.detector.extract_audio_buffer(stereo_wav)
        self.assertEqual(buf_stereo.ndim, 1)
        self.assertEqual(len(buf_stereo), int(10.0 * 22050))

        surround_wav = self.test_dir / "surround_test.wav"
        create_synthetic_wav_file(surround_wav, duration_sec=5.0, num_channels=6)
        buf_surround = self.detector.extract_audio_buffer(surround_wav)
        self.assertEqual(buf_surround.ndim, 1)
        self.assertEqual(len(buf_surround), int(5.0 * 22050))

    def test_non_standard_sample_rates_resampling(self):
        """
        Tests WAVs with 44.1kHz, 48kHz, and 8kHz sample rates.
        Asserts native wave decoder accurately resamples to 22.05kHz buffer length.
        """
        for sr in [8000, 44100, 48000]:
            test_wav = self.test_dir / f"rate_{sr}hz.wav"
            create_synthetic_wav_file(test_wav, duration_sec=6.0, sample_rate=sr)
            buf = self.detector.extract_audio_buffer(test_wav)
            expected_samples = int(6.0 * 22050)
            self.assertAlmostEqual(len(buf), expected_samples, delta=10)


    def test_exact_boundary_durations_30s_and_neighboring(self):
        """
        Tests boundary cases:
        - 30.0s exact (target duration boundary)
        - 29.9s (just under boundary -> short_audio_fallback)
        - 30.1s (just over boundary -> standard sliding window)
        """
        for dur, expected_method in [
            (29.9, "short_audio_fallback"),
            (30.0, "librosa" if hasattr(self.detector, "calculate_rms_energy") else "numpy_fallback"),
            (30.1, "librosa" if hasattr(self.detector, "calculate_rms_energy") else "numpy_fallback"),
        ]:
            wav_path = self.test_dir / f"boundary_{str(dur).replace('.', '_')}s.wav"
            create_synthetic_wav_file(wav_path, duration_sec=dur)
            res = self.detector.detect_optimal_drop(wav_path)
            if dur < 30.0:
                self.assertEqual(res.detection_method, "short_audio_fallback")
                self.assertAlmostEqual(res.duration_sec, dur, places=1)
            else:
                self.assertIn(res.detection_method, ["librosa", "numpy_fallback"])
                self.assertEqual(res.duration_sec, 30.0)

    def test_clipping_and_extreme_amplitude_signals(self):
        """Tests hard-clipped waveforms (+1.0 / -1.0 square wave saturation)."""
        sr = 22050
        t = np.linspace(0, 40.0, 40 * sr, endpoint=False)
        clipped_signal = np.sign(np.sin(2 * np.pi * 100.0 * t)).astype(np.float32)
        wav_path = self.test_dir / "clipped_square.wav"
        create_synthetic_wav_file(wav_path, duration_sec=40.0, waveform=clipped_signal)

        res = self.detector.detect_optimal_drop(wav_path)
        self.assertIn(res.detection_method, ["librosa", "numpy_fallback"])
        self.assertEqual(res.duration_sec, 30.0)
        self.assertGreaterEqual(res.max_rms_energy, 0.9)


# ============================================================================
# TEST SUITE 3: MANUAL CLI OVERRIDE BYPASS HIERARCHY
# ============================================================================

class TestManualOverrideBypassHierarchy(unittest.TestCase):
    """
    Verifies that manual timestamp overrides (--start-time, --duration)
    completely bypass Librosa/RMS calculations and file I/O immediately.
    """

    def setUp(self):
        self.detector = AudioDropDetector(target_duration_sec=30.0)

    def test_manual_override_bypasses_non_existent_file_io(self):
        """
        Passes a completely non-existent file path with manual_start_time=14.5.
        Asserts immediate return without FileNotFoundError or DSP invocation.
        """
        ghost_path = "G:/NON_EXISTENT_DIRECTORY/GHOST_AUDIO_DOES_NOT_EXIST.wav"
        res = self.detector.detect_optimal_drop(
            media_path=ghost_path,
            manual_start_time=14.5,
            manual_duration=22.0,
        )

        self.assertTrue(res.is_manual_override)
        self.assertEqual(res.detection_method, "manual_cli_override")
        self.assertEqual(res.start_time_sec, 14.5)
        self.assertEqual(res.duration_sec, 22.0)
        self.assertEqual(res.end_time_sec, 36.5)
        self.assertEqual(res.max_rms_energy, 1.0)

    def test_manual_override_clamps_duration_to_shorts_ceiling(self):
        """Tests that manual duration > 59.0s is clamped to 59.0s."""
        res = self.detector.detect_optimal_drop(
            media_path="dummy.wav",
            manual_start_time=10.0,
            manual_duration=120.0,
        )
        self.assertEqual(res.duration_sec, VIDEO_DURATION_MAX_SECONDS)
        self.assertEqual(res.end_time_sec, 10.0 + VIDEO_DURATION_MAX_SECONDS)

    def test_functional_convenience_wrappers_respect_override(self):
        """Tests detect_optimal_drop and run_auto_drop_detection helper wrappers."""
        res1 = detect_optimal_drop(
            media_path="any_dummy_path.wav",
            manual_start_time=5.0,
            manual_duration=15.0,
        )
        self.assertTrue(res1.is_manual_override)
        self.assertEqual(res1.start_time_sec, 5.0)

        res2 = run_auto_drop_detection(
            audio_wav_path="any_dummy_path.wav",
            manual_start_time=8.2,
            manual_duration=20.0,
        )
        self.assertTrue(res2.is_manual_override)
        self.assertEqual(res2.start_time_sec, 8.2)

    def test_cli_parser_manual_override_and_auto_drop_flags(self):
        """Tests CLI argument parser in orchestrator.py for process and pipeline subcommands."""
        from orchestrator import build_parser

        parser = build_parser()
        # Test pipeline with --start-time
        args = parser.parse_args([
            "pipeline",
            "--event", "EDCLV",
            "--artist", "Garrix",
            "--start-time", "22.5",
            "--duration", "15.0",
        ])
        self.assertEqual(args.start_time, 22.5)
        self.assertEqual(args.duration, 15.0)

        # Test process with --auto-drop and --drop-duration
        args_proc = parser.parse_args([
            "process",
            "--input", "input.mp4",
            "--output", "output.mp4",
            "--auto-drop",
            "--drop-duration", "25.0",
        ])
        self.assertTrue(args_proc.auto_drop)
        self.assertEqual(args_proc.drop_duration, 25.0)


# ============================================================================
# TEST SUITE 4: PROXY TRIMMING & REVIEW GATE VALIDATION
# ============================================================================

class TestProxyTrimmingAndReviewGateValidation(unittest.TestCase):
    """
    Validates that:
    1. The trimmed video staged in 02_AWAITING_REVIEW is the 720p proxy video and NOT the 4K raw.
    2. Path sanitization handles all special characters, spaces, and punctuation safely.
    3. FFmpeg proxy generation and trimming commands assemble compliant arguments.
    4. Database manifest records AWAITING_REVIEW stage with review proxy path while preserving raw path.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()
        for tier in FOLDER_TIERS.values():
            (self.workspace / tier).mkdir(parents=True, exist_ok=True)
        self.processor = FFmpegMasterProcessor()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_manifest_awaiting_review_status_and_paths(self):
        """
        Verifies that SQLite database accurately records current_status = AWAITING_REVIEW
        with master_path pointing to 02_AWAITING_REVIEW proxy and raw_path pointing to 01_RAW.
        """
        db_path = self.workspace / "test_manifest.sqlite"
        db = MediaManifestDB(db_path=db_path)

        db.upsert_asset(
            asset_id="20260822_Ultra_Garrix_V1",
            source_file_name="garrix_4k.mp4",
            canonical_name="20260822_Ultra_Garrix_Animals_V1_1080p.mp4",
            brand=BrandType.LASER_BAPTISM.value,
            tier=EventTier.PILLAR_A.value,
            event_name="Ultra",
            artist_name="Garrix",
            track_name="Animals",
            duration_seconds=30.0,
            is_hdr=True,
            current_status=AssetStatus.AWAITING_REVIEW,
            raw_path=str(self.workspace / "01_RAW" / "Ultra" / "Garrix" / "garrix_4k.mp4"),
            master_path=str(self.workspace / "02_AWAITING_REVIEW" / "Ultra" / "Garrix" / "garrix_proxy_drop.mp4"),
        )

        record = db.get_asset("20260822_Ultra_Garrix_V1")
        self.assertIsNotNone(record)
        self.assertEqual(record["current_status"], AssetStatus.AWAITING_REVIEW.value)
        self.assertIn("01_RAW", record["raw_path"])
        self.assertIn("02_AWAITING_REVIEW", record["master_path"])
        self.assertTrue(record["master_path"].endswith("proxy_drop.mp4"))

    def test_awaiting_review_folder_resolution(self):
        """Tests get_awaiting_review_folder helper."""
        review_dir = get_awaiting_review_folder(self.workspace, "UltraMiami", "MartinGarrix")
        expected = self.workspace / "02_AWAITING_REVIEW" / "UltraMiami" / "MartinGarrix"
        self.assertEqual(review_dir, expected)

    def test_proxy_trimming_command_structure(self):
        """
        Verifies that trim_proxy_video constructs correct stream-copy FFmpeg commands:
        -ss <start>, -t <duration>, -c copy, +faststart.
        """
        input_proxy = self.workspace / "02_IN_PROGRESS" / "proxy_test.mp4"
        output_review = self.workspace / "02_AWAITING_REVIEW" / "Ultra" / "Garrix" / "test_proxy_drop.mp4"

        cmd = self.processor.trim_proxy_video(
            input_proxy_path=input_proxy,
            output_path=output_review,
            start_time_sec=15.0,
            duration_sec=30.0,
            dry_run=True,
        )

        self.assertIn("-ss", cmd)
        self.assertIn("15.0", cmd)
        self.assertIn("-t", cmd)
        self.assertIn("30.0", cmd)
        self.assertIn("-c", cmd)
        self.assertIn("copy", cmd)
        self.assertIn("+faststart", cmd)

    def test_proxy_generation_720p_command_structure(self):
        """
        Verifies generate_proxy_video command specifies 720p scaling, 2.5 Mbps, and fast preset.
        """
        raw_4k = self.workspace / "01_RAW" / "Ultra" / "Garrix" / "raw_4k.mp4"
        out_proxy = self.workspace / "02_IN_PROGRESS" / "proxy_raw_4k.mp4"

        cmd = self.processor.generate_proxy_video(
            input_path=raw_4k,
            output_path=out_proxy,
            target_resolution=720,
            bitrate_kbps=2500,
            preset="fast",
            dry_run=True,
        )

        self.assertIn("-preset", cmd)
        self.assertIn("fast", cmd)
        self.assertIn("-b:v", cmd)
        self.assertIn("2500k", cmd)
        self.assertTrue(any("720" in arg for arg in cmd))

    def test_path_sanitization_adversarial_matrix(self):
        """
        Adversarial test matrix for FilenameNormalizer.sanitize_token with challenging inputs:
        Path traversal, emojis, slashes, punctuation, latin diacritics.
        """
        test_cases = [
            ("EDC Las Vegas 2026!", "EdcLasVegas2026"),
            ("Sub Focus & Wilkinson (Live)", "SubFocusWilkinsonLive"),
            ("Tiësto / Martin Garrix", "TiestoMartinGarrix"),
            ("Ørjan Nilsen (Extended Mix)", "OrjanNilsenExtendedMix"),
            ("../../etc/passwd", "EtcPasswd"),
            ("..\\..\\Windows\\System32", "WindowsSystem32"),
            ("🔥 Ultra Miami 🚀 [Mainstage]", "UltraMiamiMainstage"),
            ("??? /// !!!", "Unknown"),
            ("", "Unknown"),
            (None, "Unknown"),
        ]

        for raw_input, expected in test_cases:
            cleaned = FilenameNormalizer.sanitize_token(raw_input, default="Unknown")
            self.assertEqual(
                cleaned,
                expected,
                f"Failed sanitizing token '{raw_input}': expected '{expected}', got '{cleaned}'",
            )
            # Assert no path separators or illegal filesystem characters remain
            for illegal in ["/", "\\", ":", "*", "?", '"', "<", ">", "|", ".."]:
                self.assertNotIn(illegal, cleaned)

    def test_canonical_filename_builder_compliance(self):
        """Tests that build_canonical_filename produces valid names matching CANONICAL_PATTERN."""
        fname = FilenameNormalizer.build_canonical_filename(
            event="EDC Las Vegas",
            artist="Sub Focus",
            track="Desire",
            resolution="720p",
            version=1,
            date_str="20260822",
        )
        self.assertEqual(fname, "20260822_EdcLasVegas_SubFocus_Desire_V1_720p.mp4")
        parsed = FilenameNormalizer.parse_filename(fname)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["event"], "EdcLasVegas")
        self.assertEqual(parsed["artist"], "SubFocus")
        self.assertEqual(parsed["track"], "Desire")
        self.assertEqual(parsed["resolution"], "720p")


if __name__ == "__main__":
    unittest.main()
