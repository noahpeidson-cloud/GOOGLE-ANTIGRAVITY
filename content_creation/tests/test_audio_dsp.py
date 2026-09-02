"""
test_audio_dsp.py - Comprehensive Unit Tests for Audio DSP & Drop Detection Engine
Part of Track 2: Content Creation Pipeline
"""

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import wave

import numpy as np

from audio_dsp import (
    AudioDropDetector,
    AudioDSPError,
    AudioExtractionError,
    DropAnalysisResult,
    DropWindowResult,
    detect_optimal_drop,
    generate_synthetic_edm_signal,
    run_auto_drop_detection,
)


class TestAudioDropDetector(unittest.TestCase):
    """Unit test suite for AudioDropDetector and RMS energy calculations."""

    def setUp(self):
        self.sample_rate = 22050
        self.hop_length = 512
        self.frame_length = 2048
        self.target_duration = 30.0
        self.detector = AudioDropDetector(
            target_duration_sec=self.target_duration,
            sample_rate=self.sample_rate,
            hop_length=self.hop_length,
            frame_length=self.frame_length,
        )

    # ========================================================================
    # 1. SYNTHETIC AUDIO & SLIDING WINDOW ARGMAX TESTS
    # ========================================================================

    def test_synthetic_signal_exact_drop_localization(self):
        """Verify O(N) cumsum argmax accurately locates the exact 30s drop window."""
        total_duration = 90.0
        drop_start = 30.0
        drop_duration = 30.0

        # Generate 90s signal: [0-30s quiet (0.05)] -> [30-60s loud (0.90)] -> [60-90s quiet (0.05)]
        audio_array = generate_synthetic_edm_signal(
            total_duration_sec=total_duration,
            drop_start_sec=drop_start,
            drop_duration_sec=drop_duration,
            sample_rate=self.sample_rate,
            quiet_amplitude=0.05,
            drop_amplitude=0.90,
        )

        result = self.detector.detect_optimal_drop(audio_array)

        self.assertIsInstance(result, DropWindowResult)
        self.assertFalse(result.is_manual_override)
        # Expected start is ~30.0s within 1 frame margin of error (0.025s)
        self.assertAlmostEqual(result.start_time_sec, 30.0, delta=0.05)
        self.assertEqual(result.duration_sec, 30.0)
        self.assertAlmostEqual(result.end_time_sec, 60.0, delta=0.05)
        self.assertGreater(result.max_rms_energy, 0.4)
        self.assertIn(result.detection_method, ["librosa", "numpy_fallback"])

    def test_synthetic_signal_offset_drop_localization(self):
        """Verify drop detection with an offset drop window (e.g. 45.0s to 75.0s in 120s track)."""
        total_duration = 120.0
        drop_start = 45.0
        drop_duration = 30.0

        audio_array = generate_synthetic_edm_signal(
            total_duration_sec=total_duration,
            drop_start_sec=drop_start,
            drop_duration_sec=drop_duration,
            sample_rate=self.sample_rate,
            quiet_amplitude=0.02,
            drop_amplitude=0.85,
        )

        result = self.detector.detect_optimal_drop(audio_array)

        self.assertAlmostEqual(result.start_time_sec, 45.0, delta=0.05)
        self.assertEqual(result.duration_sec, 30.0)
        self.assertAlmostEqual(result.end_time_sec, 75.0, delta=0.05)

    def test_multi_peak_argmax_selection(self):
        """Verify detector selects the primary (highest energy) peak over a secondary minor build peak."""
        total_duration = 120.0
        t = np.linspace(0, total_duration, int(total_duration * self.sample_rate), endpoint=False)
        audio = np.full_like(t, 0.05)

        # Minor build at 10s-40s (amplitude 0.40)
        minor_mask = (t >= 10.0) & (t < 40.0)
        audio[minor_mask] = 0.40 * np.sin(2 * np.pi * 300 * t[minor_mask])

        # Main Apex Drop at 70s-100s (amplitude 0.95)
        major_mask = (t >= 70.0) & (t < 100.0)
        audio[major_mask] = 0.95 * np.sin(2 * np.pi * 60 * t[major_mask])

        result = self.detector.detect_optimal_drop(audio)

        # Must locate main drop starting at ~70.0s
        self.assertAlmostEqual(result.start_time_sec, 70.0, delta=0.05)
        self.assertEqual(result.duration_sec, 30.0)
        self.assertAlmostEqual(result.end_time_sec, 100.0, delta=0.05)

    def test_custom_target_duration_window(self):
        """Verify custom target window lengths (e.g. 15.0s and 45.0s) work accurately."""
        audio_15s_detector = AudioDropDetector(target_duration_sec=15.0, sample_rate=self.sample_rate)
        audio_array = generate_synthetic_edm_signal(
            total_duration_sec=60.0,
            drop_start_sec=25.0,
            drop_duration_sec=15.0,
            sample_rate=self.sample_rate,
            drop_amplitude=0.90,
        )

        res15 = audio_15s_detector.detect_optimal_drop(audio_array)
        self.assertAlmostEqual(res15.start_time_sec, 25.0, delta=0.05)
        self.assertEqual(res15.duration_sec, 15.0)
        self.assertAlmostEqual(res15.end_time_sec, 40.0, delta=0.05)

    # ========================================================================
    # 2. MANUAL OVERRIDE PRIORITY TESTS
    # ========================================================================

    def test_manual_override_priority_bypasses_audio_extraction(self):
        """Verify manual override immediately returns DropWindowResult without touching disk or audio extraction."""
        # Non-existent file path should NOT raise FileNotFoundError when manual override is provided
        fake_path = "/non/existent/path/to/never_opened_concert_clip.mp4"

        result = self.detector.detect_optimal_drop(
            media_path=fake_path,
            manual_start_time=15.5,
            manual_duration=30.0,
        )

        self.assertTrue(result.is_manual_override)
        self.assertEqual(result.detection_method, "manual_cli_override")
        self.assertEqual(result.start_time_sec, 15.5)
        self.assertEqual(result.duration_sec, 30.0)
        self.assertEqual(result.end_time_sec, 45.5)
        self.assertEqual(result.max_rms_energy, 1.0)

    def test_manual_override_default_duration_fallback(self):
        """Verify manual override uses default target duration when manual_duration is None."""
        result = self.detector.detect_optimal_drop(
            media_path=np.array([1.0, 2.0]),
            manual_start_time=42.0,
            manual_duration=None,
        )

        self.assertTrue(result.is_manual_override)
        self.assertEqual(result.start_time_sec, 42.0)
        self.assertEqual(result.duration_sec, 30.0)
        self.assertEqual(result.end_time_sec, 72.0)

    def test_manual_override_clamps_to_max_allowed_duration(self):
        """Verify manual override duration is clamped to VIDEO_DURATION_MAX_SECONDS (59.0s)."""
        result = self.detector.detect_optimal_drop(
            media_path="any_file.mp4",
            manual_start_time=10.0,
            manual_duration=90.0,  # Exceeds 59.0s
        )

        self.assertTrue(result.is_manual_override)
        self.assertEqual(result.start_time_sec, 10.0)
        self.assertEqual(result.duration_sec, 59.0)
        self.assertEqual(result.end_time_sec, 69.0)

    # ========================================================================
    # 3. EDGE CASE TESTS: SHORT AUDIO, SILENT AUDIO, EMPTY STREAM
    # ========================================================================

    def test_short_audio_fallback(self):
        """Verify audio shorter than target duration returns [0.0, total_duration]."""
        short_duration = 14.5
        t = np.linspace(0, short_duration, int(short_duration * self.sample_rate), endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

        result = self.detector.detect_optimal_drop(audio)

        self.assertFalse(result.is_manual_override)
        self.assertEqual(result.detection_method, "short_audio_fallback")
        self.assertEqual(result.start_time_sec, 0.0)
        self.assertAlmostEqual(result.duration_sec, 14.5, places=2)
        self.assertAlmostEqual(result.end_time_sec, 14.5, places=2)
        self.assertGreater(result.max_rms_energy, 0.1)

    def test_silent_audio_fallback(self):
        """Verify silent audio (RMS < 1e-4) returns default [0.0, target_duration] with silent fallback method."""
        silent_duration = 45.0
        audio = np.zeros(int(silent_duration * self.sample_rate), dtype=np.float32)

        result = self.detector.detect_optimal_drop(audio)

        self.assertFalse(result.is_manual_override)
        self.assertEqual(result.detection_method, "silent_audio_fallback")
        self.assertEqual(result.start_time_sec, 0.0)
        self.assertEqual(result.duration_sec, 30.0)
        self.assertEqual(result.end_time_sec, 30.0)
        self.assertEqual(result.max_rms_energy, 0.0)

    def test_near_silent_audio_under_threshold(self):
        """Verify audio with microscopic noise (< 1e-5) is treated as silent fallback."""
        audio = np.full(int(40.0 * self.sample_rate), 1e-6, dtype=np.float32)

        result = self.detector.detect_optimal_drop(audio)

        self.assertEqual(result.detection_method, "silent_audio_fallback")
        self.assertEqual(result.start_time_sec, 0.0)

    def test_empty_audio_buffer_fallback(self):
        """Verify empty audio buffer (no audio stream) returns graceful fallback."""
        empty_audio = np.array([], dtype=np.float32)

        result = self.detector.detect_optimal_drop(empty_audio)

        self.assertFalse(result.is_manual_override)
        self.assertEqual(result.detection_method, "no_audio_stream")
        self.assertEqual(result.start_time_sec, 0.0)
        self.assertEqual(result.duration_sec, 30.0)
        self.assertEqual(result.max_rms_energy, 0.0)

    # ========================================================================
    # 4. RMS CALCULATION & ENGINE PARITY TESTS
    # ========================================================================

    def test_numpy_fallback_rms_calculation(self):
        """Verify vectorized pure NumPy RMS calculation produces correct mathematical output."""
        # 1-second sine wave at 440 Hz with peak amplitude 1.0 (Theoretical RMS = 1/sqrt(2) ≈ 0.7071)
        t = np.linspace(0, 1.0, self.sample_rate, endpoint=False)
        sine_wave = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        rms_curve, method = self.detector.calculate_rms_energy(sine_wave)

        self.assertIsInstance(rms_curve, np.ndarray)
        self.assertGreater(len(rms_curve), 0)
        # Center frames of continuous sine should be very close to 0.7071
        center_rms = rms_curve[len(rms_curve) // 2]
        self.assertAlmostEqual(float(center_rms), 0.7071, places=2)

    def test_mock_librosa_vs_numpy_fallback_parity(self):
        """Verify that when librosa is available, calculate_rms_energy calls librosa and matches NumPy."""
        t = np.linspace(0, 2.0, self.sample_rate * 2, endpoint=False)
        audio = (0.8 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)

        # Force pure NumPy engine
        with patch("audio_dsp.HAS_LIBROSA", False):
            np_rms, np_method = self.detector.calculate_rms_energy(audio)
            self.assertEqual(np_method, "numpy_fallback")

        # Mock librosa feature extraction
        mock_librosa = MagicMock()
        mock_librosa.feature.rms.return_value = np.array([np_rms])

        with patch("audio_dsp.HAS_LIBROSA", True), patch("audio_dsp.librosa", mock_librosa):
            lib_rms, lib_method = self.detector.calculate_rms_energy(audio)
            self.assertEqual(lib_method, "librosa")
            np.testing.assert_allclose(lib_rms, np_rms, rtol=1e-4, atol=1e-4)

    def test_librosa_failure_gracefully_falls_back_to_numpy(self):
        """Verify that if librosa throws an exception during calculation, it falls back to NumPy."""
        audio = np.ones(self.sample_rate, dtype=np.float32)
        mock_librosa = MagicMock()
        mock_librosa.feature.rms.side_effect = RuntimeError("Librosa internal backend failure")

        with patch("audio_dsp.HAS_LIBROSA", True), patch("audio_dsp.librosa", mock_librosa):
            rms, method = self.detector.calculate_rms_energy(audio)
            self.assertEqual(method, "numpy_fallback")
            self.assertGreater(len(rms), 0)

    # ========================================================================
    # 5. AUDIO EXTRACTION & FILE DECODING TESTS
    # ========================================================================

    def test_extract_audio_from_wav_file(self):
        """Verify in-memory created WAV file is extracted accurately by extract_audio_buffer."""
        duration_sec = 2.0
        t = np.linspace(0, duration_sec, int(self.sample_rate * duration_sec), endpoint=False)
        synth_samples = (0.75 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_path = Path(tmp_wav.name)

        try:
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(synth_samples.tobytes())

            extracted_pcm = self.detector.extract_audio_buffer(tmp_path)

            self.assertIsInstance(extracted_pcm, np.ndarray)
            self.assertEqual(len(extracted_pcm), len(synth_samples))
            self.assertAlmostEqual(float(np.max(extracted_pcm)), 0.75, places=2)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_extract_audio_stereo_downmix(self):
        """Verify stereo WAV files are automatically downmixed to mono."""
        duration_sec = 1.0
        n_samples = int(self.sample_rate * duration_sec)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False)
        left = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        right = (0.5 * np.sin(2 * np.pi * 880 * t) * 32767).astype(np.int16)
        stereo_interleaved = np.column_stack((left, right)).flatten()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_path = Path(tmp_wav.name)

        try:
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(stereo_interleaved.tobytes())

            extracted_mono = self.detector.extract_audio_buffer(tmp_path)

            self.assertEqual(len(extracted_mono), n_samples)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_extract_audio_resampling(self):
        """Verify WAV file with 44100 Hz sample rate is resampled to target 22050 Hz."""
        input_sr = 44100
        duration_sec = 1.0
        t = np.linspace(0, duration_sec, int(input_sr * duration_sec), endpoint=False)
        synth_samples = (0.8 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_path = Path(tmp_wav.name)

        try:
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(input_sr)
                wf.writeframes(synth_samples.tobytes())

            extracted_pcm = self.detector.extract_audio_buffer(tmp_path)

            self.assertAlmostEqual(len(extracted_pcm), self.sample_rate, delta=5)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_extract_audio_ffmpeg_pipe_mock(self):
        """Verify FFmpeg subprocess extraction pipe correctly parses raw s16le PCM bytes."""
        duration_sec = 2.0
        n_samples = int(self.sample_rate * duration_sec)
        synth_int16 = (0.6 * np.sin(np.linspace(0, 100, n_samples)) * 32767).astype(np.int16)
        raw_pcm_bytes = synth_int16.tobytes()

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = raw_pcm_bytes
        mock_proc.stderr = b""

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_mp4:
            tmp_path = Path(tmp_mp4.name)

        try:
            with patch("subprocess.run", return_value=mock_proc), \
                 patch.object(self.detector, "_ffmpeg_bin", Path("ffmpeg")):
                pcm = self.detector.extract_audio_buffer(tmp_path)

                self.assertEqual(len(pcm), n_samples)
                self.assertAlmostEqual(float(np.max(pcm)), 0.6, places=2)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_extract_audio_non_existent_file_raises_file_not_found(self):
        """Verify extracting from a non-existent file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self.detector.extract_audio_buffer("/path/to/completely_missing_audio.wav")

    def test_extract_audio_corrupted_ffmpeg_failure_raises_audio_extraction_error(self):
        """Verify FFmpeg failure on corrupted file raises AudioExtractionError."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = b""
        mock_proc.stderr = b"Invalid data found when processing input"

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_mp4:
            tmp_path = Path(tmp_mp4.name)

        try:
            with patch("subprocess.run", return_value=mock_proc), \
                 patch.object(self.detector, "_ffmpeg_bin", Path("ffmpeg")):
                with self.assertRaises(AudioExtractionError) as ctx:
                    self.detector.extract_audio_buffer(tmp_path)
                self.assertIn("FFmpeg extraction failed", str(ctx.exception))
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_extract_audio_soundfile_fallback_mock(self):
        """Verify soundfile fallback works when sf is present and ffmpeg is absent."""
        mock_sf = MagicMock()
        mock_sf.read.return_value = (np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32), 22050)

        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            with patch("audio_dsp.HAS_SOUNDFILE", True), \
                 patch("audio_dsp.sf", mock_sf), \
                 patch.object(self.detector, "_ffmpeg_bin", None), \
                 patch("audio_dsp.find_binary", return_value=None):
                pcm = self.detector.extract_audio_buffer(tmp_path)
                self.assertEqual(len(pcm), 4)
                self.assertAlmostEqual(float(pcm[0]), 0.1)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_extract_audio_unsupported_format_raises_error_when_no_ffmpeg(self):
        """Verify unsupported format with no ffmpeg binary raises AudioExtractionError."""
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            with patch("audio_dsp.HAS_SOUNDFILE", False), \
                 patch.object(self.detector, "_ffmpeg_bin", None), \
                 patch("audio_dsp.find_binary", return_value=None):
                with self.assertRaises(AudioExtractionError):
                    self.detector.extract_audio_buffer(tmp_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    # ========================================================================
    # 6. FUNCTIONAL CONVENIENCE INTERFACE & ALIAS TESTS
    # ========================================================================

    def test_functional_wrapper_detect_optimal_drop(self):
        """Verify the module-level detect_optimal_drop convenience function."""
        audio_array = generate_synthetic_edm_signal(
            total_duration_sec=60.0,
            drop_start_sec=20.0,
            drop_duration_sec=30.0,
            sample_rate=self.sample_rate,
        )

        res = detect_optimal_drop(
            media_path=audio_array,
            target_duration_sec=30.0,
            sample_rate=self.sample_rate,
        )

        self.assertIsInstance(res, DropWindowResult)
        self.assertAlmostEqual(res.start_time_sec, 20.0, delta=0.05)
        self.assertEqual(res.duration_sec, 30.0)

    def test_alias_drop_analysis_result_compatibility(self):
        """Verify DropAnalysisResult is compatible with DropWindowResult."""
        self.assertIs(DropAnalysisResult, DropWindowResult)

    def test_dataclass_fields_immutability(self):
        """Verify DropWindowResult dataclass structure and immutability."""
        res = DropWindowResult(
            start_time_sec=10.0,
            duration_sec=30.0,
            end_time_sec=40.0,
            max_rms_energy=0.95,
            is_manual_override=False,
            detection_method="librosa",
        )
        self.assertEqual(res.start_time_sec, 10.0)
        self.assertEqual(res.duration_sec, 30.0)
        self.assertEqual(res.end_time_sec, 40.0)
        self.assertEqual(res.max_rms_energy, 0.95)
        self.assertFalse(res.is_manual_override)
        self.assertEqual(res.detection_method, "librosa")

        with self.assertRaises(Exception):
            # dataclass is frozen
            res.start_time_sec = 20.0

    # ========================================================================
    # 7. DIRECT .WAV FILE DROP DETECTION & RUN_AUTO_DROP_DETECTION TESTS
    # ========================================================================

    def test_detect_optimal_drop_direct_wav_file(self):
        """Verify AudioDropDetector processes a real .wav file on disk directly with wave decoding."""
        total_duration = 90.0
        drop_start = 30.0
        drop_duration = 30.0

        audio_array = generate_synthetic_edm_signal(
            total_duration_sec=total_duration,
            drop_start_sec=drop_start,
            drop_duration_sec=drop_duration,
            sample_rate=self.sample_rate,
            quiet_amplitude=0.05,
            drop_amplitude=0.90,
        )
        synth_int16 = (audio_array * 32767).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_path = Path(tmp_wav.name)

        try:
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(synth_int16.tobytes())

            result = self.detector.detect_optimal_drop(tmp_path)

            self.assertIsInstance(result, DropWindowResult)
            self.assertFalse(result.is_manual_override)
            self.assertAlmostEqual(result.start_time_sec, 30.0, delta=0.05)
            self.assertEqual(result.duration_sec, 30.0)
            self.assertAlmostEqual(result.end_time_sec, 60.0, delta=0.05)
            self.assertGreater(result.max_rms_energy, 0.4)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_run_auto_drop_detection_direct_wav_file(self):
        """Verify run_auto_drop_detection top-level helper executes on .wav file path."""
        total_duration = 60.0
        drop_start = 20.0
        drop_duration = 30.0

        audio_array = generate_synthetic_edm_signal(
            total_duration_sec=total_duration,
            drop_start_sec=drop_start,
            drop_duration_sec=drop_duration,
            sample_rate=self.sample_rate,
            quiet_amplitude=0.02,
            drop_amplitude=0.88,
        )
        synth_int16 = (audio_array * 32767).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_path = Path(tmp_wav.name)

        try:
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(synth_int16.tobytes())

            res = run_auto_drop_detection(
                audio_wav_path=tmp_path,
                target_duration_sec=30.0,
                sample_rate=self.sample_rate,
            )

            self.assertIsInstance(res, DropWindowResult)
            self.assertFalse(res.is_manual_override)
            self.assertAlmostEqual(res.start_time_sec, 20.0, delta=0.05)
            self.assertEqual(res.duration_sec, 30.0)
            self.assertAlmostEqual(res.end_time_sec, 50.0, delta=0.05)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_run_auto_drop_detection_manual_override_priority(self):
        """Verify run_auto_drop_detection honors manual CLI overrides immediately."""
        res = run_auto_drop_detection(
            audio_wav_path="/non_existent_fake_path/clip.wav",
            target_duration_sec=30.0,
            manual_start_time=18.5,
            manual_duration=22.0,
        )

        self.assertTrue(res.is_manual_override)
        self.assertEqual(res.detection_method, "manual_cli_override")
        self.assertEqual(res.start_time_sec, 18.5)
        self.assertEqual(res.duration_sec, 22.0)
        self.assertEqual(res.end_time_sec, 40.5)

    def test_direct_wav_vs_synthetic_array_parity(self):
        """Verify numerical parity between direct .wav file analysis and array analysis."""
        total_duration = 75.0
        drop_start = 25.0
        drop_duration = 30.0

        audio_array = generate_synthetic_edm_signal(
            total_duration_sec=total_duration,
            drop_start_sec=drop_start,
            drop_duration_sec=drop_duration,
            sample_rate=self.sample_rate,
            quiet_amplitude=0.04,
            drop_amplitude=0.85,
        )
        synth_int16 = (audio_array * 32767).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_path = Path(tmp_wav.name)

        try:
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(synth_int16.tobytes())

            array_res = self.detector.detect_optimal_drop(audio_array)
            wav_res = self.detector.detect_optimal_drop(tmp_path)

            self.assertAlmostEqual(array_res.start_time_sec, wav_res.start_time_sec, delta=0.01)
            self.assertEqual(array_res.duration_sec, wav_res.duration_sec)
            self.assertAlmostEqual(array_res.end_time_sec, wav_res.end_time_sec, delta=0.01)
            self.assertAlmostEqual(array_res.max_rms_energy, wav_res.max_rms_energy, delta=0.01)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()
