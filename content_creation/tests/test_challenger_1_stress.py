"""
test_challenger_1_stress.py - Adversarial Stress Test Harness by Challenger 1
Track 2: Content Creation Pipeline (Milestone 3 EDM Content Strategy Upgrade)

Comprehensive White-Box and Black-Box Stress Testing:
1. Multi-peak energy contours (global vs local maxima, subtle deltas, flat-tops, micro-spikes).
2. Non-standard sample rates (8k-192k), unusual durations, odd sample counts, DC/silence/extremes.
3. YouTube publisher polling with flaky networks, backoff, multi-claims, timeout limits, malformed payloads.
4. Manual override parameter fuzzing (negative, extreme, float precision, boundary conditions).
"""

from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audio_dsp import (
    AudioDropDetector,
    AudioDSPError,
    AudioExtractionError,
    DropWindowResult,
    detect_optimal_drop,
    generate_synthetic_edm_signal,
)
from config import (
    AssetStatus,
    ContentIDStatus,
    VIDEO_DURATION_MAX_SECONDS,
)
from metadata_tracker import MediaManifestDB
from youtube_publisher import (
    AuditTimeoutError,
    ContentIDBlockError,
    VideoAuditStatus,
    YouTubeAuthError,
    YouTubeAuthManager,
    YouTubePublisher,
    YouTubePublishError,
    YouTubePublishResult,
    YouTubeUploadError,
    YouTubeVideoMetadata,
    build_parser,
)


class TestAudioDSPAdversarialContours(unittest.TestCase):
    """Stress testing RMS energy contour calculation and sliding window argmax."""

    def setUp(self):
        self.sample_rate = 22050
        self.detector = AudioDropDetector(target_duration_sec=30.0, sample_rate=self.sample_rate)

    def test_multi_peak_global_vs_local_maxima(self):
        """Construct 4 peaks; verify argmax cumsum selects global apex peak at 100s."""
        total_duration = 180.0
        n_samples = int(total_duration * self.sample_rate)
        t = np.linspace(0, total_duration, n_samples, endpoint=False)
        audio = np.full(n_samples, 0.02, dtype=np.float32)

        # Peak 1 (Local): 10s-40s (30s duration), amp=0.50
        mask1 = (t >= 10.0) & (t < 40.0)
        audio[mask1] = 0.50 * np.sin(2 * np.pi * 100 * t[mask1])

        # Peak 2 (Local): 50s-80s (30s duration), amp=0.75
        mask2 = (t >= 50.0) & (t < 80.0)
        audio[mask2] = 0.75 * np.sin(2 * np.pi * 150 * t[mask2])

        # Peak 3 (Global Apex): 100s-130s (30s duration), amp=0.98
        mask3 = (t >= 100.0) & (t < 130.0)
        audio[mask3] = 0.98 * np.sin(2 * np.pi * 60 * t[mask3])

        # Peak 4 (Local): 140s-170s (30s duration), amp=0.60
        mask4 = (t >= 140.0) & (t < 170.0)
        audio[mask4] = 0.60 * np.sin(2 * np.pi * 200 * t[mask4])

        result = self.detector.detect_optimal_drop(audio)

        self.assertAlmostEqual(result.start_time_sec, 100.0, delta=0.1)
        self.assertEqual(result.duration_sec, 30.0)
        self.assertAlmostEqual(result.end_time_sec, 130.0, delta=0.1)
        self.assertGreater(result.max_rms_energy, 0.65)

    def test_subtle_delta_peak_resolution(self):
        """Two 30s peaks differing by only 0.005 amplitude: verify true winner is chosen."""
        total_duration = 120.0
        n_samples = int(total_duration * self.sample_rate)
        t = np.linspace(0, total_duration, n_samples, endpoint=False)
        audio = np.zeros(n_samples, dtype=np.float32)

        # Peak 1 at 15s-45s: 0.895 amp
        m1 = (t >= 15.0) & (t < 45.0)
        audio[m1] = 0.895 * np.sin(2 * np.pi * 80 * t[m1])

        # Peak 2 at 65s-95s: 0.900 amp (higher energy)
        m2 = (t >= 65.0) & (t < 95.0)
        audio[m2] = 0.900 * np.sin(2 * np.pi * 80 * t[m2])

        result = self.detector.detect_optimal_drop(audio)
        self.assertAlmostEqual(result.start_time_sec, 65.0, delta=0.1)

    def test_flat_top_energy_contour(self):
        """Long 60s flat-top plateau (20s to 80s): verify window starts within plateau without boundary violation."""
        total_duration = 100.0
        n_samples = int(total_duration * self.sample_rate)
        t = np.linspace(0, total_duration, n_samples, endpoint=False)
        audio = np.full(n_samples, 0.05, dtype=np.float32)

        plateau_mask = (t >= 20.0) & (t < 80.0)
        audio[plateau_mask] = 0.85 * np.sin(2 * np.pi * 100 * t[plateau_mask])

        result = self.detector.detect_optimal_drop(audio)
        # Any start between 20.0 and 50.0 is valid for a 30s window on a 60s plateau
        self.assertGreaterEqual(result.start_time_sec, 19.9)
        self.assertLessEqual(result.start_time_sec, 50.1)
        self.assertAlmostEqual(result.duration_sec, 30.0)
        self.assertLessEqual(result.end_time_sec, 80.1)

    def test_rapid_micro_spikes_vs_sustained_drop(self):
        """Short 2s ultra-high spike vs sustained 30s drop: 30s cumsum must choose sustained drop."""
        total_duration = 100.0
        n_samples = int(total_duration * self.sample_rate)
        t = np.linspace(0, total_duration, n_samples, endpoint=False)
        audio = np.full(n_samples, 0.01, dtype=np.float32)

        # 2s spike at 10s (amp 1.0)
        spike_mask = (t >= 10.0) & (t < 12.0)
        audio[spike_mask] = 1.0 * np.sin(2 * np.pi * 500 * t[spike_mask])

        # 30s sustained drop at 50s (amp 0.70)
        drop_mask = (t >= 50.0) & (t < 80.0)
        audio[drop_mask] = 0.70 * np.sin(2 * np.pi * 60 * t[drop_mask])

        result = self.detector.detect_optimal_drop(audio)
        # Sustained drop contains ~10x total integrated RMS energy of the short 2s spike
        self.assertAlmostEqual(result.start_time_sec, 50.0, delta=0.1)

    def test_dc_offset_and_inverted_phases(self):
        """Verify RMS energy properly calculates with DC offset and negative phases."""
        total_duration = 60.0
        n_samples = int(total_duration * self.sample_rate)
        t = np.linspace(0, total_duration, n_samples, endpoint=False)
        audio = np.zeros(n_samples, dtype=np.float32)

        # Drop with negative offset and inverted sine at 20s-50s
        drop_mask = (t >= 20.0) & (t < 50.0)
        audio[drop_mask] = -0.80 * np.sin(2 * np.pi * 60 * t[drop_mask])

        result = self.detector.detect_optimal_drop(audio)
        self.assertAlmostEqual(result.start_time_sec, 20.0, delta=0.1)
        self.assertGreater(result.max_rms_energy, 0.5)


class TestAudioDSPAdversarialRatesAndDurations(unittest.TestCase):
    """Stress testing sample rates, durations, odd lengths, and edge audio buffers."""

    def test_non_standard_sample_rates(self):
        """Test across diverse sample rates: 8k, 11025, 16k, 32k, 44.1k, 48k, 88.2k, 96k, 192k."""
        rates = [8000, 11025, 16000, 32000, 44100, 48000, 88200, 96000, 192000]
        for sr in rates:
            with self.subTest(sample_rate=sr):
                detector = AudioDropDetector(target_duration_sec=30.0, sample_rate=sr)
                total_duration = 75.0
                drop_start = 25.0
                drop_dur = 30.0
                n_samples = int(total_duration * sr)
                t = np.linspace(0, total_duration, n_samples, endpoint=False)
                audio = np.full(n_samples, 0.05, dtype=np.float32)
                drop_m = (t >= drop_start) & (t < drop_start + drop_dur)
                audio[drop_m] = 0.90 * np.sin(2 * np.pi * 60 * t[drop_m])

                result = detector.detect_optimal_drop(audio)
                self.assertAlmostEqual(result.start_time_sec, 25.0, delta=0.15)
                self.assertEqual(result.duration_sec, 30.0)
                self.assertAlmostEqual(result.end_time_sec, 55.0, delta=0.15)

    def test_ultra_short_durations_sub_frame(self):
        """Test durations shorter than 1 analysis frame (< 2048 samples)."""
        sr = 22050
        detector = AudioDropDetector(target_duration_sec=30.0, sample_rate=sr)

        # 512 samples (~0.023 seconds, smaller than frame_length 2048)
        audio = (0.5 * np.sin(np.linspace(0, 10, 512))).astype(np.float32)
        result = detector.detect_optimal_drop(audio)

        self.assertEqual(result.detection_method, "short_audio_fallback")
        self.assertEqual(result.start_time_sec, 0.0)
        self.assertAlmostEqual(result.duration_sec, 512 / sr, places=3)
        self.assertAlmostEqual(result.end_time_sec, 512 / sr, places=3)

    def test_odd_sample_counts(self):
        """Verify non-standard prime sample count does not throw stride or padding errors."""
        sr = 22050
        detector = AudioDropDetector(target_duration_sec=30.0, sample_rate=sr)
        prime_samples = 133337  # ~6.046 seconds
        audio = (0.7 * np.sin(np.linspace(0, 500, prime_samples))).astype(np.float32)

        result = detector.detect_optimal_drop(audio)
        self.assertEqual(result.detection_method, "short_audio_fallback")
        self.assertAlmostEqual(result.duration_sec, prime_samples / sr, places=3)

    def test_exact_target_duration_boundary(self):
        """Audio exactly equal to target duration (30.0s): window must be [0.0, 30.0]."""
        sr = 22050
        detector = AudioDropDetector(target_duration_sec=30.0, sample_rate=sr)
        n_samples = int(30.0 * sr)
        audio = (0.8 * np.sin(np.linspace(0, 300, n_samples))).astype(np.float32)

        result = detector.detect_optimal_drop(audio)
        self.assertAlmostEqual(result.start_time_sec, 0.0, delta=0.05)
        self.assertEqual(result.duration_sec, 30.0)
        self.assertAlmostEqual(result.end_time_sec, 30.0, delta=0.05)

    def test_audio_with_nans_or_infs_in_fallback(self):
        """Audio buffer containing NaNs or Infs: calculate_rms_energy handles without crashing."""
        sr = 22050
        detector = AudioDropDetector(target_duration_sec=30.0, sample_rate=sr)
        audio = np.zeros(sr * 10, dtype=np.float32)
        audio[1000] = np.nan
        audio[2000] = np.inf

        # Force pure NumPy engine
        with patch("audio_dsp.HAS_LIBROSA", False):
            rms, method = detector.calculate_rms_energy(audio)
            self.assertIsInstance(rms, np.ndarray)
            self.assertEqual(method, "numpy_fallback")


class TestYouTubePublisherAdversarialPolling(unittest.TestCase):
    """Stress testing YouTube publisher polling loop, API errors, timeouts, and claim statuses."""

    def test_polling_api_error_returns_failed_without_crash(self):
        """API returns 500/503/429 errors during polling."""
        mock_service = MagicMock()
        mock_req = MagicMock()
        mock_req.execute.side_effect = Exception("HTTP 503 Backend service overloaded")
        mock_service.videos().list.return_value = mock_req

        publisher = YouTubePublisher(service=mock_service)
        result = publisher.poll_content_id_status("vid_err_503")

        self.assertEqual(result.content_id_status, "FAILED")
        self.assertIn("503 Backend service overloaded", result.error_message)
        self.assertFalse(result.is_blocked)
        self.assertEqual(result.final_privacy, "unlisted")

    def test_polling_empty_items_then_timeout(self):
        """API returns empty items list (e.g. indexing delay) until timeout expires."""
        mock_service = MagicMock()
        mock_req = MagicMock()
        mock_req.execute.return_value = {"items": []}
        mock_service.videos().list.return_value = mock_req

        publisher = YouTubePublisher(service=mock_service)
        # Advance time to trigger timeout immediately
        with patch("time.time", side_effect=[0.0, 0.0, 50.0, 50.0]):
            with patch("time.sleep", return_value=None):
                result = publisher.poll_content_id_status("vid_missing", timeout_sec=10.0)

        self.assertEqual(result.content_id_status, "TIMED_OUT")
        self.assertIn("not found after 10.0s", result.error_message)
        self.assertEqual(result.final_privacy, "unlisted")

    def test_polling_malformed_item_missing_status_or_processing(self):
        """API returns item missing status or processingDetails sub-dictionaries."""
        mock_service = MagicMock()
        mock_req = MagicMock()
        # Item with empty dicts
        mock_req.execute.return_value = {"items": [{}]}
        mock_service.videos().list.return_value = mock_req

        publisher = YouTubePublisher(service=mock_service)
        with patch("time.time", side_effect=[0.0, 0.0, 100.0, 100.0]):
            with patch("time.sleep", return_value=None):
                result = publisher.poll_content_id_status("vid_malformed", timeout_sec=5.0)

        self.assertEqual(result.content_id_status, "TIMED_OUT")
        self.assertFalse(result.is_blocked)

    def test_polling_multiple_non_blocking_content_id_claims(self):
        """Standard content claim (licensedContent=True) without rejection allows promotion."""
        mock_service = MagicMock()
        mock_req = MagicMock()
        mock_req.execute.return_value = {
            "items": [{
                "id": "vid_claim_ok",
                "status": {"uploadStatus": "processed", "privacyStatus": "unlisted"},
                "processingDetails": {"processingStatus": "succeeded"},
                "contentDetails": {"licensedContent": True},
            }]
        }
        mock_service.videos().list.return_value = mock_req

        publisher = YouTubePublisher(service=mock_service)
        result = publisher.poll_content_id_status("vid_claim_ok")

        self.assertEqual(result.content_id_status, "UNLISTED_CLEARED")
        self.assertFalse(result.is_blocked)
        self.assertTrue(result.is_cleared)

    def test_polling_explicit_copyright_rejection_blocks_promotion(self):
        """Explicit rejection with rejectionReason='copyright' blocks immediately."""
        mock_service = MagicMock()
        mock_req = MagicMock()
        mock_req.execute.return_value = {
            "items": [{
                "id": "vid_blocked_strike",
                "status": {
                    "uploadStatus": "rejected",
                    "rejectionReason": "copyright",
                    "privacyStatus": "unlisted",
                },
                "processingDetails": {"processingStatus": "terminated"},
            }]
        }
        mock_service.videos().list.return_value = mock_req

        publisher = YouTubePublisher(service=mock_service)
        result = publisher.poll_content_id_status("vid_blocked_strike")

        self.assertEqual(result.content_id_status, "BLOCKED")
        self.assertTrue(result.is_blocked)
        self.assertEqual(result.rejection_reason, "copyright")

    def test_publish_workflow_timeout_prevents_public_promotion(self):
        """When Content ID audit times out, publish_workflow MUST keep video unlisted."""
        mock_service = MagicMock()

        # Mock Insert
        mock_insert = MagicMock()
        mock_insert.next_chunk.return_value = (None, {"id": "vid_timeout_123"})
        mock_service.videos().insert.return_value = mock_insert

        # Mock Polling timeout (processing never completes)
        mock_list = MagicMock()
        mock_list.execute.return_value = {
            "items": [{
                "id": "vid_timeout_123",
                "status": {"uploadStatus": "uploaded", "privacyStatus": "unlisted"},
                "processingDetails": {"processingStatus": "processing"},
            }]
        }
        mock_service.videos().list.return_value = mock_list

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_f:
            tmp_video = Path(tmp_f.name)
            tmp_video.write_bytes(b"dummy mp4 content")

        try:
            publisher = YouTubePublisher(service=mock_service)
            with patch("time.time", side_effect=[0.0, 0.0, 10.0, 10.0, 10.0]):
                with patch("time.sleep", return_value=None):
                    result = publisher.publish_workflow(
                        video_path=tmp_video,
                        title="Timeout Test",
                        description="Timeout Desc",
                        auto_promote=True,
                        poll_timeout_sec=5.0,
                    )

            self.assertEqual(result.content_id_status, "TIMED_OUT")
            self.assertEqual(result.final_privacy, "unlisted")
            self.assertFalse(result.is_blocked)
            mock_service.videos().update.assert_not_called()
        finally:
            if tmp_video.exists():
                tmp_video.unlink()



class TestManualOverrideParameterFuzzing(unittest.TestCase):
    """Fuzz testing manual override CLI parameters and boundary conditions."""

    def setUp(self):
        self.detector = AudioDropDetector(target_duration_sec=30.0)

    def test_manual_override_with_bogus_media_path(self):
        """Manual override bypasses file checking completely."""
        bogus_paths = [
            "",
            "   ",
            "/definitely/does/not/exist/clip.mp4",
            "C:\\NonExistentDirectory\\video.mp4",
            None,
        ]
        for path in bogus_paths:
            with self.subTest(path=path):
                res = self.detector.detect_optimal_drop(
                    media_path=path,
                    manual_start_time=12.5,
                    manual_duration=20.0,
                )
                self.assertTrue(res.is_manual_override)
                self.assertEqual(res.detection_method, "manual_cli_override")
                self.assertEqual(res.start_time_sec, 12.5)
                self.assertEqual(res.duration_sec, 20.0)
                self.assertEqual(res.end_time_sec, 32.5)

    def test_manual_override_floating_point_precision_rounding(self):
        """Verify high-precision floating point parameters are cleanly rounded to 3 decimal places."""
        res = self.detector.detect_optimal_drop(
            media_path="dummy.mp4",
            manual_start_time=14.123456789,
            manual_duration=25.987654321,
        )
        self.assertEqual(res.start_time_sec, 14.123)
        self.assertEqual(res.duration_sec, 25.988)
        self.assertEqual(res.end_time_sec, 40.111)

    def test_manual_override_duration_capped_at_59_seconds(self):
        """Verify duration >= 60.0s is capped to VIDEO_DURATION_MAX_SECONDS (59.0s)."""
        durations = [59.0, 59.5, 60.0, 90.0, 3600.0]
        for dur in durations:
            with self.subTest(duration=dur):
                res = self.detector.detect_optimal_drop(
                    media_path="dummy.mp4",
                    manual_start_time=5.0,
                    manual_duration=dur,
                )
                self.assertLessEqual(res.duration_sec, float(VIDEO_DURATION_MAX_SECONDS))
                self.assertEqual(res.duration_sec, 59.0)
                self.assertEqual(res.end_time_sec, 64.0)

    def test_audio_dsp_sliding_window_argmax_tie_breaker(self):
        """When two windows have identical energy, verify first window is chosen stably."""
        sr = 22050
        detector = AudioDropDetector(target_duration_sec=30.0, sample_rate=sr)
        total_duration = 100.0
        n_samples = int(total_duration * sr)
        t = np.linspace(0, total_duration, n_samples, endpoint=False)
        audio = np.zeros(n_samples, dtype=np.float32)

        # Identical Peak A at 10s-40s
        mA = (t >= 10.0) & (t < 40.0)
        audio[mA] = 0.80 * np.sin(2 * np.pi * 100 * t[mA])

        # Identical Peak B at 50s-80s
        mB = (t >= 50.0) & (t < 80.0)
        audio[mB] = 0.80 * np.sin(2 * np.pi * 100 * t[mB])

        res = detector.detect_optimal_drop(audio)
        # Argmax on identical sums chooses first occurrence
        self.assertAlmostEqual(res.start_time_sec, 10.0, delta=0.1)

    def test_audio_dsp_window_boundary_clamping(self):
        """Target duration 45.0s on a 50.0s track: window must start at <= 5.0s and end <= 50.0s."""
        sr = 22050
        detector = AudioDropDetector(target_duration_sec=45.0, sample_rate=sr)
        total_duration = 50.0
        n_samples = int(total_duration * sr)
        t = np.linspace(0, total_duration, n_samples, endpoint=False)
        audio = (0.75 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)

        res = detector.detect_optimal_drop(audio)
        self.assertLessEqual(res.start_time_sec, 5.0)
        self.assertEqual(res.duration_sec, 45.0)
        self.assertLessEqual(res.end_time_sec, 50.0)

    def test_audio_dsp_clipping_and_extreme_amplitudes(self):
        """Square wave / clipped signal at extreme amplitude 10.0 does not overflow."""
        sr = 22050
        detector = AudioDropDetector(target_duration_sec=30.0, sample_rate=sr)
        total_duration = 60.0
        n_samples = int(total_duration * sr)
        t = np.linspace(0, total_duration, n_samples, endpoint=False)
        # Extreme square wave
        audio = np.where(np.sin(2 * np.pi * 100 * t) > 0, 10.0, -10.0).astype(np.float32)

        res = detector.detect_optimal_drop(audio)
        self.assertIsInstance(res, DropWindowResult)
        self.assertEqual(res.duration_sec, 30.0)
        self.assertGreater(res.max_rms_energy, 9.0)

    def test_youtube_publisher_auth_refresh_failure_raises_youtube_auth_error(self):
        """When OAuth token refresh fails with exception, YouTubeAuthError is raised."""
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "invalid_refresh_token"
        mock_creds.refresh.side_effect = Exception("Token has been expired or revoked.")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_f:
            tmp_token = Path(tmp_f.name)
            tmp_token.write_text('{"refresh_token": "revoked"}', encoding="utf-8")

        try:
            with patch("youtube_publisher.Credentials") as mock_creds_cls:
                mock_creds_cls.from_authorized_user_file.return_value = mock_creds
                with self.assertRaises(YouTubeAuthError):
                    YouTubeAuthManager.resolve_credentials(
                        token_path=tmp_token,
                        client_secrets_path="/nonexistent/secret.json",
                    )
        finally:
            if tmp_token.exists():
                tmp_token.unlink()

    def test_youtube_publisher_sqlite_manifest_sync_new_asset(self):
        """Syncing an asset that is not yet in the SQLite DB creates a new asset record cleanly."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_f:
            tmp_db_path = Path(tmp_f.name)

        try:
            pub_res = YouTubePublishResult(
                video_id="brand_new_yt_vid",
                final_privacy="public",
                content_id_status="UNLISTED_CLEARED",
                is_blocked=False,
                published_url="https://youtu.be/brand_new_yt_vid",
            )
            YouTubePublisher.sync_manifest_db(
                db_path=tmp_db_path,
                asset_id="20260822_Autonomous_New",
                publish_result=pub_res,
            )

            db = MediaManifestDB(db_path=tmp_db_path)
            asset = db.get_asset("20260822_Autonomous_New")
            self.assertIsNotNone(asset)
            self.assertEqual(asset["current_status"], "POSTED")
            self.assertEqual(asset["youtube_content_id_status"], "UNLISTED_CLEARED")
            self.assertEqual(asset["metadata"]["youtube_video_id"], "brand_new_yt_vid")
        finally:
            if tmp_db_path.exists():
                tmp_db_path.unlink()


if __name__ == "__main__":
    unittest.main()