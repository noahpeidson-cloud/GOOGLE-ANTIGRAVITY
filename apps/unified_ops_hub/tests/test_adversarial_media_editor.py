"""Adversarial Concurrency, Memory Stability & Failure Mode Stress Test Suite for MediaEditor.
Enforces Rule R2 (The Leash Protocol / Zero-Discretion Mandate / Loud Assertions).
Targets:
1. Parallel Multithreaded & Multiprocess Concurrency.
2. Memory consumption bounds and leak detection during DSP audio extraction.
3. Extreme failure modes (0-byte, truncated, corrupted headers, non-media binary garbage).
"""

import concurrent.futures
import gc
import os
import shutil
import subprocess
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Module import with absolute import fallback
try:
    from unified_ops_hub.ml_agent.editor import MediaEditor
except ImportError:
    from ml_agent.editor import MediaEditor


# ============================================================================
# Helpers & Synthetic Media Generators
# ============================================================================

def resolve_ffmpeg_path() -> str:
    """Resolves FFmpeg executable path dynamically."""
    if os.environ.get("FFMPEG_PATH"):
        return os.environ["FFMPEG_PATH"]
    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def create_adversarial_video(
    output_path: str,
    duration: float = 4.0,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
    audio_type: str = "beep",  # "beep" | "silence" | "none" | "constant"
    beep_start: float = 1.0,
    beep_end: float = 2.5,
    beep_freq: int = 1000,
    sample_rate: int = 22050,
) -> str:
    """Fast procedural generation of synthetic media for stress testing."""
    exe = resolve_ffmpeg_path()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        exe, "-y",
        "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate={fps}:duration={duration}",
    ]

    if audio_type == "beep":
        filter_expr = f"sin(2*PI*{beep_freq}*t)*between(t\\,{beep_start}\\,{beep_end})"
        cmd.extend([
            "-f", "lavfi", "-i", f"aevalsrc={filter_expr}:sample_rate={sample_rate}:duration={duration}",
            "-c:a", "aac",
        ])
    elif audio_type == "silence":
        cmd.extend([
            "-f", "lavfi", "-i", f"aevalsrc=0:sample_rate={sample_rate}:duration={duration}",
            "-c:a", "aac",
        ])
    elif audio_type == "constant":
        cmd.extend([
            "-f", "lavfi", "-i", f"aevalsrc=sin(2*PI*{beep_freq}*t):sample_rate={sample_rate}:duration={duration}",
            "-c:a", "aac",
        ])
    elif audio_type == "none":
        cmd.extend(["-an"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        output_path,
    ])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg synthetic media generation failed: {res.stderr}")

    return output_path


def _worker_process_proxy_task(args_tuple):
    """Top-level helper for multiprocessing executor (picklable)."""
    source_file, proxy_dir, target_height = args_tuple
    editor = MediaEditor()
    return editor.generate_proxy_and_cuts(
        source_file=source_file,
        proxy_dir=proxy_dir,
        target_height=target_height,
    )


# ============================================================================
# 1. Concurrency Stress Tests (Multithreading & Multiprocessing)
# ============================================================================

class TestConcurrencyAdversarial:
    """Stress tests concurrent proxy generation and media analysis."""

    def test_multithreaded_parallel_proxy_generation(self, tmp_path):
        """Loud Assertion: 6 worker threads can generate proxies concurrently without deadlocks or collisions."""
        num_workers = 6
        sources = []
        for i in range(num_workers):
            src = str(tmp_path / f"worker_src_{i}.mp4")
            create_adversarial_video(
                src,
                duration=3.0 + i * 0.5,
                width=1920,
                height=1080,
                beep_start=1.0,
                beep_end=2.0 + i * 0.2,
                beep_freq=800 + i * 100,
            )
            sources.append(src)

        editor = MediaEditor()
        proxy_dir = str(tmp_path / "thread_proxies")

        def _task(src_path: str) -> Dict[str, Any]:
            return editor.generate_proxy_and_cuts(src_path, proxy_dir=proxy_dir)

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(_task, src) for src in sources]
            results = [f.result(timeout=60) for f in concurrent.futures.as_completed(futures)]
        elapsed = time.time() - start_time

        assert len(results) == num_workers, (
            f"LOUD ASSERTION FAILURE: Expected {num_workers} results, got {len(results)}"
        )

        # Validate every proxy generated concurrently
        for res in results:
            assert os.path.exists(res["proxy_file"]), (
                f"LOUD ASSERTION FAILURE: Proxy file does not exist: {res['proxy_file']}"
            )
            assert os.path.getsize(res["proxy_file"]) > 1000, (
                f"LOUD ASSERTION FAILURE: Proxy file is suspiciously small: {res['proxy_file']}"
            )
            assert "cuts" in res and "hype_drop" in res["cuts"]
            assert res["cuts"]["hype_drop"]["crop_ratio"] == "9:16"
            assert res["cuts"]["cinematic"]["crop_ratio"] == "16:9"
            assert res["cuts"]["raw_pov"]["crop_ratio"] == "original"

    def test_multiprocess_parallel_proxy_generation(self, tmp_path):
        """Loud Assertion: 4 independent OS processes execute MediaEditor pipelines concurrently."""
        num_procs = 4
        tasks = []
        proxy_dir = str(tmp_path / "proc_proxies")

        for i in range(num_procs):
            src = str(tmp_path / f"proc_src_{i}.mp4")
            create_adversarial_video(src, duration=2.5 + i * 0.5, width=1280, height=720)
            tasks.append((src, proxy_dir, 720))

        with concurrent.futures.ProcessPoolExecutor(max_workers=num_procs) as executor:
            futures = [executor.submit(_worker_process_proxy_task, t) for t in tasks]
            results = [f.result(timeout=60) for f in concurrent.futures.as_completed(futures)]

        assert len(results) == num_procs, (
            f"LOUD ASSERTION FAILURE: Multiprocess executor did not complete all tasks ({len(results)}/{num_procs})"
        )
        for res in results:
            assert os.path.exists(res["proxy_file"]), (
                f"LOUD ASSERTION FAILURE: Multiprocess proxy file missing: {res['proxy_file']}"
            )

    def test_shared_instance_thread_safety_high_contention(self, tmp_path):
        """Loud Assertion: A single shared MediaEditor instance handles 10 concurrent threads probing & analyzing."""
        num_threads = 10
        sources = []
        for i in range(num_threads):
            src = str(tmp_path / f"contention_src_{i}.mp4")
            create_adversarial_video(src, duration=4.0, audio_type="beep", beep_start=1.0, beep_end=2.0)
            sources.append(src)

        shared_editor = MediaEditor()

        def _probe_and_peak(src: str):
            info = shared_editor.probe_media(src)
            in_p, out_p = shared_editor.detect_audio_peak(src, target_duration=2.0)
            cuts = shared_editor.generate_cuts(src, duration=info["duration"], window_duration_sec=2.0)
            return info, in_p, out_p, cuts

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(_probe_and_peak, src) for src in sources]
            for fut in concurrent.futures.as_completed(futures):
                info, in_p, out_p, cuts = fut.result(timeout=30)
                assert info["duration"] > 0, "LOUD ASSERTION FAILURE: Thread contention corrupted duration"
                assert in_p >= 0.0, "LOUD ASSERTION FAILURE: Thread contention produced invalid in_point"
                assert out_p <= info["duration"] + 0.1, "LOUD ASSERTION FAILURE: out_point exceeded duration"
                assert cuts["hype_drop"]["crop_ratio"] == "9:16"


# ============================================================================
# 2. Memory Stability & Large Media Analysis Stress Tests
# ============================================================================

class TestMemoryStabilityAdversarial:
    """Stress tests memory consumption, linear scaling, and leak prevention."""

    def test_memory_bounded_audio_extraction_and_dsp(self, tmp_path):
        """Loud Assertion: Audio analysis on sustained media retains strictly bounded memory (< 30MB overhead)."""
        # Generate a 60-second video with a clear burst at [30s, 35s]
        src_path = str(tmp_path / "sustained_60s.mp4")
        create_adversarial_video(
            src_path,
            duration=60.0,
            width=640,
            height=360,
            audio_type="beep",
            beep_start=30.0,
            beep_end=35.0,
            beep_freq=1200,
        )

        editor = MediaEditor()

        # Start tracing memory allocations
        gc.collect()
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        # Execute peak detection (which internally extracts PCM into memory and runs DSP)
        in_point, out_point = editor.detect_audio_peak(src_path, target_duration=15.0)

        snapshot_during = tracemalloc.take_snapshot()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / (1024 * 1024)

        # Assert peak memory is well under 30 MB (expected ~5-10 MB for 60s of 22.05kHz PCM)
        assert peak_mb < 30.0, (
            f"LOUD ASSERTION FAILURE: Peak memory exceeded threshold: {peak_mb:.2f} MB >= 30.0 MB"
        )

        # Assert DSP accuracy on large file
        assert in_point <= 30.0, f"LOUD ASSERTION FAILURE: Peak in_point {in_point} missed 30s burst"
        assert out_point >= 35.0, f"LOUD ASSERTION FAILURE: Peak out_point {out_point} missed 35s burst"

    def test_zero_memory_leak_across_repeated_dsp_iterations(self, tmp_path):
        """Loud Assertion: 25 sequential audio analysis iterations exhibit zero cumulative memory leak."""
        src_path = str(tmp_path / "loop_src_10s.mp4")
        create_adversarial_video(src_path, duration=10.0, width=640, height=360)

        editor = MediaEditor()
        tracemalloc.start()

        # Warmup
        for _ in range(3):
            editor.detect_audio_peak(src_path)

        gc.collect()
        mem_start, _ = tracemalloc.get_traced_memory()

        # 25 iterations of audio extraction & peak calculation
        for _ in range(25):
            editor.detect_audio_peak(src_path)
            editor.probe_media(src_path)

        gc.collect()
        mem_end, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        heap_growth_kb = (mem_end - mem_start) / 1024
        # Heap growth should be negligible (< 250 KB over 25 runs)
        assert heap_growth_kb < 250.0, (
            f"LOUD ASSERTION FAILURE: Potential memory leak detected. Heap growth: {heap_growth_kb:.2f} KB"
        )

    def test_extreme_dsp_sample_rates_and_fine_frames(self, tmp_path):
        """Loud Assertion: High sample rate (44.1kHz) and micro-frame duration (10ms) execute safely."""
        src_path = str(tmp_path / "high_sr_10s.mp4")
        create_adversarial_video(
            src_path,
            duration=10.0,
            sample_rate=44100,
            audio_type="beep",
            beep_start=4.0,
            beep_end=6.0,
        )

        editor = MediaEditor()
        in_point, out_point = editor.detect_audio_peak(
            src_path,
            target_duration=5.0,
            frame_duration_ms=10.0,
            sample_rate=44100,
        )

        assert in_point <= 4.0, f"LOUD ASSERTION FAILURE: in_point {in_point} > 4.0"
        assert out_point >= 6.0, f"LOUD ASSERTION FAILURE: out_point {out_point} < 6.0"
        assert abs((out_point - in_point) - 5.0) < 0.1, "LOUD ASSERTION FAILURE: Window mismatch"


# ============================================================================
# 3. Extreme Failure Modes & Corrupted Media Hardening
# ============================================================================

class TestFailureModesAdversarial:
    """Stress tests error resilience on corrupted, 0-byte, truncated, and non-media inputs."""

    def test_zero_byte_empty_file_graceful_handling(self, tmp_path):
        """Loud Assertion: 0-byte empty file handles metadata extraction safely and raises RuntimeError on proxy."""
        empty_file = str(tmp_path / "zero_byte.mp4")
        with open(empty_file, "wb") as f:
            pass  # Create 0-byte file

        editor = MediaEditor()

        # 1. Probing empty file returns duration 0.0 and defaults without crashing
        info = editor.probe_media(empty_file)
        assert info["duration"] == 0.0, f"LOUD ASSERTION FAILURE: Expected duration 0.0, got {info['duration']}"
        assert info["has_audio"] is False, "LOUD ASSERTION FAILURE: Expected has_audio False for 0-byte file"

        # 2. Peak detection on empty file returns (0.0, 0.0)
        in_p, out_p = editor.detect_audio_peak(empty_file)
        assert (in_p, out_p) == (0.0, 0.0), (
            f"LOUD ASSERTION FAILURE: Expected (0.0, 0.0), got ({in_p}, {out_p})"
        )

        # 3. Extracting PCM on empty file returns b""
        pcm = editor.extract_pcm_audio(empty_file)
        assert pcm == b"", "LOUD ASSERTION FAILURE: Expected empty PCM bytes for 0-byte file"

        # 4. Proxy generation raises RuntimeError loudly
        with pytest.raises(RuntimeError) as exc_info:
            editor.generate_proxy(empty_file)
        assert "failed" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()

    def test_random_binary_garbage_file(self, tmp_path):
        """Loud Assertion: Non-media binary garbage is handled gracefully without unhandled crashes."""
        garbage_file = str(tmp_path / "corrupt_garbage.mp4")
        with open(garbage_file, "wb") as f:
            f.write(os.urandom(32768))  # 32 KB of random bytes

        editor = MediaEditor()

        # 1. Probing returns 0.0 duration safely
        info = editor.probe_media(garbage_file)
        assert info["duration"] == 0.0
        assert info["has_audio"] is False

        # 2. Audio extraction returns empty bytes
        pcm = editor.extract_pcm_audio(garbage_file)
        assert pcm == b""

        # 3. Peak detection safely falls back to (0.0, 0.0)
        in_p, out_p = editor.detect_audio_peak(garbage_file)
        assert (in_p, out_p) == (0.0, 0.0)

        # 4. Proxy generation fails loudly with RuntimeError
        with pytest.raises(RuntimeError):
            editor.generate_proxy(garbage_file)

    def test_truncated_mp4_file_header_only(self, tmp_path):
        """Loud Assertion: Truncated MP4 (severed stream) fails safely or detects corruption."""
        valid_src = str(tmp_path / "valid_for_truncation.mp4")
        create_adversarial_video(valid_src, duration=5.0)

        raw_bytes = Path(valid_src).read_bytes()
        # Truncate to first 10% of file
        truncated_path = str(tmp_path / "severed_stream.mp4")
        with open(truncated_path, "wb") as f:
            f.write(raw_bytes[: len(raw_bytes) // 10])

        editor = MediaEditor()

        # Audio peak on truncated file should not crash
        in_p, out_p = editor.detect_audio_peak(truncated_path)
        assert isinstance(in_p, (float, int))
        assert isinstance(out_p, (float, int))

        # Proxy generation must raise RuntimeError due to corrupt moov atom / stream EOF
        with pytest.raises(RuntimeError):
            editor.generate_proxy(truncated_path)

    def test_text_and_json_files_disguised_as_video(self, tmp_path):
        """Loud Assertion: Text/JSON files with .mp4 extension are rejected safely."""
        fake_file = str(tmp_path / "fake_media.mp4")
        with open(fake_file, "w", encoding="utf-8") as f:
            f.write('{"status": "error", "message": "this is not a video"}')

        editor = MediaEditor()
        info = editor.probe_media(fake_file)
        assert info["duration"] == 0.0
        assert info["has_audio"] is False

        with pytest.raises(RuntimeError):
            editor.generate_proxy(fake_file)

    def test_directory_passed_as_source_file_raises_filenotfound(self, tmp_path):
        """Loud Assertion: Directory path passed as source_file raises FileNotFoundError."""
        dir_path = str(tmp_path / "a_directory")
        os.makedirs(dir_path, exist_ok=True)

        editor = MediaEditor()
        with pytest.raises(FileNotFoundError):
            editor.probe_media(dir_path)

        with pytest.raises(FileNotFoundError):
            editor.generate_proxy(dir_path)

        with pytest.raises(FileNotFoundError):
            editor.extract_pcm_audio(dir_path)

        with pytest.raises(FileNotFoundError):
            editor.detect_audio_peak(dir_path)

        with pytest.raises(FileNotFoundError):
            editor.generate_proxy_and_cuts(dir_path)

    def test_audio_only_wav_file_behavior(self, tmp_path):
        """Loud Assertion: Audio-only file correctly extracts audio and peak, but fails proxy video scaling."""
        wav_path = str(tmp_path / "audio_only.wav")
        exe = resolve_ffmpeg_path()
        # Generate 6s WAV with 1000Hz tone at [2s, 4s]
        cmd = [
            exe, "-y",
            "-f", "lavfi", "-i", "aevalsrc=sin(2*PI*1000*t)*between(t\\,2.0\\,4.0):sample_rate=22050:duration=6.0",
            "-c:a", "pcm_s16le",
            wav_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        editor = MediaEditor()
        info = editor.probe_media(wav_path)
        assert info["has_audio"] is True
        assert abs(info["duration"] - 6.0) < 0.2

        pcm = editor.extract_pcm_audio(wav_path)
        assert len(pcm) > 0, "LOUD ASSERTION FAILURE: Could not extract PCM from WAV"

        in_p, out_p = editor.detect_audio_peak(wav_path, target_duration=4.0)
        assert in_p <= 2.0, f"LOUD ASSERTION FAILURE: Peak start {in_p} missed 2.0s"
        assert out_p >= 4.0, f"LOUD ASSERTION FAILURE: Peak end {out_p} missed 4.0s"

        # Proxy generation on audio-only file creates a valid faststart audio-mp4 proxy
        proxy_out = editor.generate_proxy(wav_path)
        assert os.path.exists(proxy_out), "LOUD ASSERTION FAILURE: Audio proxy was not generated"
        assert os.path.getsize(proxy_out) > 0, "LOUD ASSERTION FAILURE: Audio proxy is 0 bytes"
        proxy_info = editor.probe_media(proxy_out)
        assert proxy_info["has_audio"] is True, "LOUD ASSERTION FAILURE: Proxy lost audio track"


    def test_ultra_short_micro_clip(self, tmp_path):
        """Loud Assertion: Micro clip (0.05s / single frame) does not cause divide-by-zero or slice crash."""
        micro_file = str(tmp_path / "micro_clip.mp4")
        create_adversarial_video(micro_file, duration=0.05, width=640, height=360)

        editor = MediaEditor()
        info = editor.probe_media(micro_file)
        in_p, out_p = editor.detect_audio_peak(micro_file, target_duration=15.0)

        assert in_p == 0.0, f"LOUD ASSERTION FAILURE: in_p for micro clip must be 0.0, got {in_p}"
        assert out_p <= 0.1, f"LOUD ASSERTION FAILURE: out_p exceeded micro clip duration: {out_p}"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
