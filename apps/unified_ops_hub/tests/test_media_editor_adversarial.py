"""Adversarial DSP and Media Stress Test Suite for MediaEditor.
Independently written by M1 Challenger 1 (Adversarial DSP & Media Verifier).
Tests multi-burst waveforms, micro/macro durations, odd resolutions, faststart atom order, and contract invariants.
"""

import os
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pytest

from ml_agent.editor import MediaEditor


@pytest.fixture(scope="module")
def editor() -> MediaEditor:
    """Provides an initialized MediaEditor instance."""
    return MediaEditor()


def parse_mp4_box_atoms(file_path: Path) -> List[Tuple[str, int, int]]:
    """Parses top-level MP4 container boxes to verify atom layout (e.g. faststart).

    Returns:
        List of (box_type, byte_offset, box_size) tuples.
    """
    atoms = []
    with open(file_path, "rb") as f:
        data = f.read()
    offset = 0
    while offset + 8 <= len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        box_type = data[offset + 4 : offset + 8].decode("latin1", errors="replace")
        atoms.append((box_type, offset, size))
        if size == 0:
            break
        if size == 1:
            size = struct.unpack(">Q", data[offset + 8 : offset + 16])[0]
        offset += size
    return atoms


# ==============================================================================
# 1. Multi-Burst Audio Waveforms & Energy Argmax Stress Tests
# ==============================================================================

def test_adversarial_multiburst_audio_energy_argmax(editor: MediaEditor):
    """Stress tests 3 distinct audio bursts with different amplitudes and frequencies.

    Layout (40s total):
    - Burst 1: t=4..7s (3s) @ 0.25 amp (1000Hz) - local peak
    - Burst 2: t=18..23s (5s) @ 0.95 amp (500Hz)  - GLOBAL MAX
    - Burst 3: t=32..35s (3s) @ 0.55 amp (2000Hz) - local peak
    - Background: 0.001 amp noise

    Verification:
    detect_audio_peak with 15.0s window must strictly contain the global maximum [18..23s].
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "multiburst.mp4"
        audio_filter = (
            "if(between(t\\,4\\,7)\\, 0.25*sin(2*PI*1000*t)\\, "
            "if(between(t\\,18\\,23)\\, 0.95*sin(2*PI*500*t)\\, "
            "if(between(t\\,32\\,35)\\, 0.55*sin(2*PI*2000*t)\\, "
            "0.001*sin(2*PI*100*t))))"
        )
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=40:size=320x240:rate=10",
            "-f", "lavfi", "-i", f"aevalsrc={audio_filter}:d=40:s=22050",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        in_pt, out_pt = editor.detect_audio_peak(src, target_duration=15.0)
        assert in_pt <= 18.0, f"Expected in_point <= 18.0, got {in_pt}"
        assert out_pt >= 23.0, f"Expected out_point >= 23.0, got {out_pt}"
        assert round(out_pt - in_pt, 2) == 15.0


def test_adversarial_competing_bursts_energy_integration(editor: MediaEditor):
    """Stress tests integrated RMS energy over time vs narrow transient spike.

    Layout (35s total):
    - Spike: t=4.0..4.3s (0.3s) @ 1.0 amp spike
    - Sustained: t=16.0..24.0s (8.0s) @ 0.85 amp continuous energy

    Verification:
    A 15s window sliding sum will integrate significantly more total RMS energy
    over the 8s sustained block than the 0.3s spike.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "energy_integration.mp4"
        audio_filter = (
            "if(between(t\\,4\\,4.3)\\, 1.0*sin(2*PI*1000*t)\\, "
            "if(between(t\\,16\\,24)\\, 0.85*sin(2*PI*440*t)\\, "
            "0.001*sin(2*PI*100*t)))"
        )
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=35:size=320x240:rate=10",
            "-f", "lavfi", "-i", f"aevalsrc={audio_filter}:d=35:s=22050",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        in_pt, out_pt = editor.detect_audio_peak(src, target_duration=15.0)
        assert in_pt <= 16.0, f"Expected in_point <= 16.0, got {in_pt}"
        assert out_pt >= 24.0, f"Expected out_point >= 24.0, got {out_pt}"


def test_adversarial_stereo_channel_asymmetry(editor: MediaEditor):
    """Stress tests mono downmixing from asymmetric stereo channels.

    Channel 0 (Left): Pure silence
    Channel 1 (Right): Loud 0.9 amp burst at t=10..14s
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "stereo_asym.mp4"
        audio_filter = (
            "0|if(between(t\\,10\\,14)\\, 0.9*sin(2*PI*600*t)\\, 0.001)"
        )
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=25:size=320x240:rate=10",
            "-f", "lavfi", "-i", f"aevalsrc={audio_filter}:d=25:s=22050:c=stereo",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        in_pt, out_pt = editor.detect_audio_peak(src, target_duration=15.0)
        assert in_pt <= 10.0, f"Expected in_point <= 10.0, got {in_pt}"
        assert out_pt >= 14.0, f"Expected out_point >= 14.0, got {out_pt}"


# ==============================================================================
# 2. Micro and Macro Video Duration Stress Tests
# ==============================================================================

def test_adversarial_micro_clip_0_3s(editor: MediaEditor):
    """Stress tests micro video clip of 0.3s duration (sub-second edge case)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "micro_0_3s.mp4"
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=0.3:size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        info = editor.probe_media(src)
        assert info["duration"] <= 0.4
        assert info["duration"] >= 0.2

        in_pt, out_pt = editor.detect_audio_peak(src, target_duration=15.0)
        assert in_pt == 0.0
        assert out_pt <= 0.4

        proxy_path = editor.generate_proxy(src, proxy_dir=tmpdir)
        assert Path(proxy_path).is_file()
        assert Path(proxy_path).stat().st_size > 0

        cuts = editor.generate_cuts(src, duration=info["duration"])
        for cut_name in ("hype_drop", "cinematic", "raw_pov"):
            assert cuts[cut_name]["in_point"] == 0.0
            assert cuts[cut_name]["out_point"] <= 0.4


def test_adversarial_micro_clip_1_2s(editor: MediaEditor):
    """Stress tests 1.2s short clip duration clamping."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "micro_1_2s.mp4"
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1.2:size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1.2",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        dur = editor.get_video_duration(src)
        assert 1.1 <= dur <= 1.3
        in_pt, out_pt = editor.detect_audio_peak(src, target_duration=15.0)
        assert in_pt == 0.0
        assert out_pt == round(dur, 2)


def test_adversarial_macro_clip_65s_duration_and_peak(editor: MediaEditor):
    """Stress tests 65s long video duration regex parsing (> 1 minute) and peak localization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "macro_65s.mp4"
        audio_filter = (
            "if(between(t\\,48\\,53)\\, 0.95*sin(2*PI*440*t)\\, 0.005*sin(2*PI*220*t))"
        )
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=65:size=320x240:rate=10",
            "-f", "lavfi", "-i", f"aevalsrc={audio_filter}:d=65:s=22050",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        dur = editor.get_video_duration(src)
        assert 64.9 <= dur <= 65.1

        in_pt, out_pt = editor.detect_audio_peak(src, target_duration=15.0)
        assert in_pt <= 48.0, f"Expected in_pt <= 48.0, got {in_pt}"
        assert out_pt >= 53.0, f"Expected out_pt >= 53.0, got {out_pt}"
        assert round(out_pt - in_pt, 2) == 15.0

        cuts = editor.generate_cuts(src, duration=dur)
        assert cuts["cinematic"]["out_point"] == round(dur, 2)
        assert cuts["raw_pov"]["out_point"] == round(dur, 2)


# ==============================================================================
# 3. Unusual Resolutions & Aspect Ratios Stress Tests
# ==============================================================================

def test_adversarial_unusual_resolution_odd_721x1281(editor: MediaEditor):
    """Stress tests odd pixel dimensions (721x1281) with scale=-2:720 H.264 proxy generator."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "odd_721x1281.mp4"
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=721x1281:rate=10",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv444p",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        info = editor.probe_media(src)
        assert info["width"] == 721
        assert info["height"] == 1281

        proxy = editor.generate_proxy(src, proxy_dir=tmpdir)
        proxy_info = editor.probe_media(proxy)

        # Height MUST be exactly 720, and width must be even integer
        assert proxy_info["height"] == 720
        assert proxy_info["width"] % 2 == 0
        assert 400 <= proxy_info["width"] <= 410


def test_adversarial_resolution_4k_uhd_3840x2160(editor: MediaEditor):
    """Stress tests 4K UHD 16:9 input (3840x2160) scaling to 1280x720."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "uhd_4k.mp4"
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=3840x2160:rate=10",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        info = editor.probe_media(src)
        assert info["width"] == 3840
        assert info["height"] == 2160

        proxy = editor.generate_proxy(src, proxy_dir=tmpdir)
        proxy_info = editor.probe_media(proxy)
        assert proxy_info["width"] == 1280
        assert proxy_info["height"] == 720


def test_adversarial_resolution_vertical_9_16_1080x1920(editor: MediaEditor):
    """Stress tests full HD vertical 9:16 video (1080x1920)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "vertical_9_16.mp4"
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=1080x1920:rate=10",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        info = editor.probe_media(src)
        assert info["width"] == 1080
        assert info["height"] == 1920

        proxy = editor.generate_proxy(src, proxy_dir=tmpdir)
        proxy_info = editor.probe_media(proxy)
        assert proxy_info["height"] == 720
        assert proxy_info["width"] in (404, 406)


def test_adversarial_resolution_ultrawide_21_9_2560x1080(editor: MediaEditor):
    """Stress tests 21:9 ultrawide video (2560x1080)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "ultrawide_21_9.mp4"
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=2560x1080:rate=10",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        info = editor.probe_media(src)
        assert info["width"] == 2560
        assert info["height"] == 1080

        proxy = editor.generate_proxy(src, proxy_dir=tmpdir)
        proxy_info = editor.probe_media(proxy)
        assert proxy_info["height"] == 720
        assert proxy_info["width"] in (1706, 1708)


# ==============================================================================
# 4. Proxy Faststart Flag & Playability Verification
# ==============================================================================

def test_adversarial_proxy_faststart_atom_structure(editor: MediaEditor):
    """Empirically verifies the MP4 binary atom header order for web streaming (+faststart).

    In a faststart-enabled MP4, the `moov` atom (metadata) MUST precede the `mdat` atom (media data).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "stream_test.mp4"
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        proxy_path = Path(editor.generate_proxy(src, proxy_dir=tmpdir))
        atoms = parse_mp4_box_atoms(proxy_path)
        box_types = [a[0] for a in atoms]

        assert "moov" in box_types, f"Missing 'moov' atom in proxy MP4: {box_types}"
        assert "mdat" in box_types, f"Missing 'mdat' atom in proxy MP4: {box_types}"

        moov_idx = box_types.index("moov")
        mdat_idx = box_types.index("mdat")

        assert moov_idx < mdat_idx, (
            f"Faststart violation: 'moov' atom at index {moov_idx} appears AFTER 'mdat' atom at index {mdat_idx}! "
            f"Atoms: {atoms}"
        )


def test_adversarial_proxy_playability_and_codec(editor: MediaEditor):
    """Verifies proxy conforms to H.264 baseline/high profile and YUV420P for universal browser playback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "browser_playable.mp4"
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        proxy_path = editor.generate_proxy(src, proxy_dir=tmpdir)

        # Inspect proxy codec details via FFmpeg stderr
        probe_cmd = [editor.ffmpeg_bin, "-i", str(proxy_path)]
        res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stderr = res.stderr

        assert "Video: h264" in stderr, f"Proxy not encoded in H.264: {stderr}"
        assert "yuv420p" in stderr, f"Proxy pixel format not yuv420p: {stderr}"
        assert "Audio: aac" in stderr, f"Proxy audio not aac: {stderr}"


# ==============================================================================
# 5. Interface Contract & Robustness Invariants
# ==============================================================================

def test_adversarial_cuts_json_contract_conformance(editor: MediaEditor):
    """Validates full JSON metadata compliance with PROJECT.md Interface Contracts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "contract_sample.mp4"
        cmd = [
            editor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=20:size=1920x1080:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=20",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        payload = editor.generate_proxy_and_cuts(src, proxy_dir=tmpdir)

        # Verify top-level contract keys
        for key in ("source_file", "proxy_file", "duration", "cuts"):
            assert key in payload, f"Missing top-level contract key: {key}"

        assert isinstance(payload["duration"], (float, int))
        assert payload["duration"] == 20.0

        cuts = payload["cuts"]
        for cut_name in ("hype_drop", "cinematic", "raw_pov"):
            assert cut_name in cuts, f"Missing cut definition: {cut_name}"
            cut = cuts[cut_name]
            for required_prop in ("in_point", "out_point", "crop_ratio", "label", "target_resolution"):
                assert required_prop in cut, f"Cut '{cut_name}' missing property '{required_prop}'"
            assert isinstance(cut["in_point"], (float, int))
            assert isinstance(cut["out_point"], (float, int))
            assert cut["in_point"] <= cut["out_point"]

        assert cuts["hype_drop"]["crop_ratio"] == "9:16"
        assert cuts["hype_drop"]["target_resolution"] == "1080x1920"

        assert cuts["cinematic"]["crop_ratio"] == "16:9"
        assert cuts["cinematic"]["target_resolution"] == "1920x1080"

        assert cuts["raw_pov"]["crop_ratio"] == "original"
        assert cuts["raw_pov"]["target_resolution"] == "original"


def test_adversarial_nonexistent_and_corrupt_files(editor: MediaEditor):
    """Verifies clean error handling on missing or corrupted input files."""
    with pytest.raises(FileNotFoundError):
        editor.probe_media("non_existent_video_12345.mp4")

    with pytest.raises(FileNotFoundError):
        editor.generate_proxy("non_existent_video_12345.mp4")

    with pytest.raises(FileNotFoundError):
        editor.detect_audio_peak("non_existent_video_12345.mp4")

    with tempfile.TemporaryDirectory() as tmpdir:
        corrupt_file = Path(tmpdir) / "corrupt.mp4"
        corrupt_file.write_bytes(b"NOT_AN_MP4_FILE_CORRUPTED_BYTES_1234567890")

        with pytest.raises((RuntimeError, Exception)):
            editor.generate_proxy(corrupt_file, proxy_dir=tmpdir)