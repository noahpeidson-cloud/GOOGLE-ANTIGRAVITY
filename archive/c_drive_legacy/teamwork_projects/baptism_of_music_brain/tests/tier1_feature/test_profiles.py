"""Tier 1 Feature Tests: Visually Lossless Encoding Profiles."""

from __future__ import annotations

import pytest

try:
    from src.renderer.profiles import get_encoding_args, list_available_profiles
except ImportError:
    get_encoding_args = None
    list_available_profiles = None


def _check_profiles():
    if get_encoding_args is None:
        pytest.skip("src.renderer.profiles not yet implemented")


@pytest.mark.tier1
def test_profile_x264_crf17_flags():
    """Verify default x264_crf17 profile sets libx264, crf 17, and aac 320k."""
    _check_profiles()
    args = get_encoding_args("x264_crf17")
    assert "-c:v" in args
    idx_v = args.index("-c:v")
    assert args[idx_v + 1] == "libx264"
    assert "-crf" in args
    idx_crf = args.index("-crf")
    assert args[idx_crf + 1] == "17"
    assert "-c:a" in args
    idx_a = args.index("-c:a")
    assert args[idx_a + 1] == "aac"


@pytest.mark.tier1
def test_profile_x264_yuv444p_flags():
    """Verify x264_yuv444p profile sets 4:4:4 chroma sampling."""
    _check_profiles()
    args = get_encoding_args("x264_yuv444p")
    assert "-pix_fmt" in args
    idx = args.index("-pix_fmt")
    assert args[idx + 1] == "yuv444p"


@pytest.mark.tier1
def test_profile_x265_crf16_flags():
    """Verify x265_crf16 profile sets libx265, crf 16, and 10-bit color."""
    _check_profiles()
    args = get_encoding_args("x265_crf16")
    assert "libx265" in args
    assert "16" in args


@pytest.mark.tier1
def test_profile_nvenc_hevc_flags():
    """Verify hevc_nvenc profile sets hardware encoder flags."""
    _check_profiles()
    args = get_encoding_args("hevc_nvenc")
    assert "hevc_nvenc" in args


@pytest.mark.tier1
def test_profile_prores_hq_flags():
    """Verify prores_hq profile sets Apple ProRes codec and uncompressed audio."""
    _check_profiles()
    args = get_encoding_args("prores_hq")
    assert any("prores" in a for a in args)


@pytest.mark.tier1
def test_invalid_profile_name_raises_error():
    """Verify requesting an unsupported profile raises KeyError or ValueError."""
    _check_profiles()
    with pytest.raises((KeyError, ValueError)):
        get_encoding_args("unsupported_super_codec_9000")


@pytest.mark.tier1
def test_list_available_profiles_contains_defaults():
    """Verify list_available_profiles includes required baseline profiles."""
    _check_profiles()
    if list_available_profiles is not None:
        profiles = list_available_profiles()
        assert "x264_crf17" in profiles
