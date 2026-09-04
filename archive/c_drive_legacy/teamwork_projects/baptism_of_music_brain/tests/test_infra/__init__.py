"""Test infrastructure and assertion engines for baptism_of_music_brain."""

from tests.test_infra.media_generator import (
    get_ffmpeg_binary,
    get_ffprobe_binary,
    generate_procedural_video,
    generate_4k_uhd_video,
    generate_1080p_video,
    generate_vertical_video,
    generate_noise_video,
    generate_smpte_bars_video,
    generate_silent_video,
    generate_corrupt_video,
    generate_odd_dimension_video,
)
from tests.test_infra.ffprobe_validator import (
    probe_media_file,
    assert_visually_lossless,
    assert_resolution_match,
    assert_fps_precision,
    assert_codec_and_profile,
    assert_duration,
)

__all__ = [
    "get_ffmpeg_binary",
    "get_ffprobe_binary",
    "generate_procedural_video",
    "generate_4k_uhd_video",
    "generate_1080p_video",
    "generate_vertical_video",
    "generate_noise_video",
    "generate_smpte_bars_video",
    "generate_silent_video",
    "generate_corrupt_video",
    "generate_odd_dimension_video",
    "probe_media_file",
    "assert_visually_lossless",
    "assert_resolution_match",
    "assert_fps_precision",
    "assert_codec_and_profile",
    "assert_duration",
]
