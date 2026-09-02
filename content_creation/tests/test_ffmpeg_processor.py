"""
test_ffmpeg_processor.py - Unit tests for FFmpeg filtergraph construction and loudnorm parsing.
"""

from pathlib import Path
import tempfile
import unittest

from config import (
    DenoiseMode,
    LoudnormMode,
    ProductionPreset,
    ReframeMode,
    ToneMapMode,
)
from ffmpeg_processor import (
    FilterGraphBuilder,
    LoudnessStats,
    ProxyGenerationResult,
    TranscodeConfig,
    FFmpegMasterProcessor,
    parse_loudnorm_pass1_output,
)


class TestFFmpegProcessor(unittest.TestCase):
    """Verifies filtergraph generator logic, loudnorm parsers, and command assemblers."""

    def test_center_crop_video_filter(self):
        v_filter = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.OFF,
            denoise=DenoiseMode.OFF,
        )
        self.assertIn("crop=w=ih*9/16:h=ih:x=(iw-ow)/2:y=0", v_filter)
        self.assertIn("scale=1080:1920:flags=lanczos", v_filter)

    def test_blur_pad_video_filter(self):
        v_filter = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.BLUR_PAD,
            tone_map=ToneMapMode.OFF,
            denoise=DenoiseMode.OFF,
        )
        self.assertIn("boxblur=luma_radius=25", v_filter)
        self.assertIn("overlay=(W-w)/2:(H-h)/2", v_filter)

    def test_hdr_tonemap_filter(self):
        v_filter = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.AUTO,
            is_hdr=True,
            denoise=DenoiseMode.OFF,
        )
        self.assertIn("tonemap=mobius:desat=0.5", v_filter)
        self.assertIn("zscale=p=bt709:t=bt709:m=bt709:r=tv", v_filter)

    def test_denoise_filter(self):
        v_filter = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            tone_map=ToneMapMode.OFF,
            denoise=DenoiseMode.ON,
        )
        self.assertIn("hqdn3d=luma_spatial=4.0:chroma_spatial=3.0:luma_tmp=6.0:chroma_tmp=4.5", v_filter)

    def test_safe_zone_text_overlay_filter(self):
        v_filter = FilterGraphBuilder.build_video_filter(
            reframe_mode=ReframeMode.CENTER_CROP,
            track_title="Where You Are",
            artist_name="John Summit",
        )
        self.assertIn("drawtext=text='JOHN SUMMIT - Where You Are'", v_filter)
        self.assertIn("y=350", v_filter)  # Validated in universal safe zone

    def test_audio_filter_two_pass(self):
        stats = LoudnessStats(
            input_i=-21.4,
            input_tp=-0.2,
            input_lra=11.2,
            input_thresh=-32.5,
            target_offset=0.6,
        )
        a_filter = FilterGraphBuilder.build_audio_filter(
            loudnorm_stats=stats,
            highpass_hz=40,
            duration_sec=30.0,
            apply_loop_crossfade=True,
            loudnorm_mode=LoudnormMode.TWO_PASS,
        )
        self.assertIn("highpass=f=40:poles=2", a_filter)
        self.assertIn("loudnorm=I=-14.0:LRA=7.0:TP=-1.5:measured_I=-21.40", a_filter)
        self.assertIn("measured_LRA=11.20:measured_TP=-0.20:measured_thresh=-32.50:offset=0.60:linear=true", a_filter)
        self.assertIn("afade=t=in:ss=0:d=0.030", a_filter)
        self.assertIn("afade=t=out:st=29.970:d=0.030", a_filter)

    def test_parse_loudnorm_stderr_json(self):
        sample_stderr = """
        [Parsed_loudnorm_1 @ 0000021b38f84700] 
        {
            "input_i" : "-21.40",
            "input_tp" : "-0.20",
            "input_lra" : "11.20",
            "input_thresh" : "-32.50",
            "output_i" : "-14.02",
            "output_tp" : "-1.50",
            "output_lra" : "6.80",
            "output_thresh" : "-24.50",
            "normalization_type" : "dynamic",
            "target_offset" : "+0.60"
        }
        """
        stats = parse_loudnorm_pass1_output(sample_stderr)
        self.assertIsNotNone(stats)
        self.assertAlmostEqual(stats.input_i, -21.4)
        self.assertAlmostEqual(stats.input_tp, -0.2)
        self.assertAlmostEqual(stats.input_lra, 11.2)
        self.assertAlmostEqual(stats.input_thresh, -32.5)
        self.assertAlmostEqual(stats.target_offset, 0.6)

    def test_dry_run_transcode_command_assembly(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"dummy video data")
            tf_p = Path(tf.name)

        out_p = tf_p.parent / "test_out.mp4"

        try:
            cfg = TranscodeConfig(
                input_path=tf_p,
                output_path=out_p,
                preset=ProductionPreset.FAST_TRACK,
                reframe_mode=ReframeMode.CENTER_CROP,
                duration_sec=75.0,  # Should be clamped to <= 59.0s
                max_duration_sec=59.0,
                dry_run=True,
            )
            processor = FFmpegMasterProcessor()
            res = processor.transcode(cfg)
            self.assertTrue(res.success)
            self.assertEqual(res.duration_sec, 59.0)  # Clamped!
            self.assertIn("-t", res.ffmpeg_command)
            self.assertIn("59.0", res.ffmpeg_command)
            self.assertIn("-movflags", res.ffmpeg_command)
            self.assertIn("+faststart", res.ffmpeg_command)
        finally:
            tf_p.unlink(missing_ok=True)
            out_p.unlink(missing_ok=True)

    def test_generate_proxy_video_command(self):
        processor = FFmpegMasterProcessor()
        src = Path("01_RAW/UltraMiami/MartinGarrix/20260822_UltraMiami_MartinGarrix_Animals_V1_4k.mp4")
        dest = Path("02_AWAITING_REVIEW/UltraMiami/MartinGarrix/proxy_20260822_UltraMiami_MartinGarrix_Animals_V1_720p.mp4")
        cmd = processor.generate_proxy_video(src, dest, target_resolution=720, bitrate_kbps=2500, dry_run=True)

        self.assertIn("-i", cmd)
        self.assertIn("-vf", cmd)
        vf_idx = cmd.index("-vf")
        self.assertIn("scale='if(gt(ih,iw),720,-2)':'if(gt(ih,iw),-2,720)'", cmd[vf_idx + 1])
        self.assertIn("-preset", cmd)
        self.assertIn("fast", cmd)
        self.assertIn("-b:v", cmd)
        self.assertIn("2500k", cmd)
        self.assertIn("-movflags", cmd)
        self.assertIn("+faststart", cmd)

    def test_extract_wav_audio_command(self):
        processor = FFmpegMasterProcessor()
        src = Path("01_RAW/UltraMiami/MartinGarrix/20260822_UltraMiami_MartinGarrix_Animals_V1_4k.mp4")
        dest = Path("02_AWAITING_REVIEW/UltraMiami/MartinGarrix/20260822_UltraMiami_MartinGarrix_Animals_V1.wav")
        cmd = processor.extract_wav_audio(src, dest, sample_rate=22050, audio_codec="pcm_s16le", dry_run=True)

        self.assertIn("-vn", cmd)
        self.assertIn("-c:a", cmd)
        self.assertIn("pcm_s16le", cmd)
        self.assertIn("-ar", cmd)
        self.assertIn("22050", cmd)
        self.assertIn("-ac", cmd)
        self.assertIn("1", cmd)
        self.assertIn("-f", cmd)
        self.assertIn("wav", cmd)

    def test_generate_proxy_and_wav(self):
        processor = FFmpegMasterProcessor()
        src = Path("01_RAW/UltraMiami/MartinGarrix/20260822_UltraMiami_MartinGarrix_Animals_V1_4k.mp4")
        proxy_dest = Path("02_AWAITING_REVIEW/UltraMiami/MartinGarrix/proxy_20260822_UltraMiami_MartinGarrix_Animals_V1_720p.mp4")
        wav_dest = Path("02_AWAITING_REVIEW/UltraMiami/MartinGarrix/20260822_UltraMiami_MartinGarrix_Animals_V1.wav")

        res = processor.generate_proxy_and_wav(src, proxy_dest, wav_dest, dry_run=True)
        self.assertIsInstance(res, ProxyGenerationResult)
        self.assertTrue(res.success)
        self.assertTrue(res.proxy_video_path.endswith("proxy_20260822_UltraMiami_MartinGarrix_Animals_V1_720p.mp4"))
        self.assertTrue(res.audio_wav_path.endswith("20260822_UltraMiami_MartinGarrix_Animals_V1.wav"))
        self.assertIn("-b:v", res.proxy_ffmpeg_cmd)
        self.assertIn("-vn", res.wav_ffmpeg_cmd)

    def test_trim_proxy_video_command(self):
        processor = FFmpegMasterProcessor()
        src = Path("02_AWAITING_REVIEW/UltraMiami/MartinGarrix/proxy_20260822_UltraMiami_MartinGarrix_Animals_V1_720p.mp4")
        dest = Path("02_AWAITING_REVIEW/UltraMiami/MartinGarrix/20260822_UltraMiami_MartinGarrix_Animals_V1_drop_30s.mp4")
        cmd = processor.trim_proxy_video(src, dest, start_time=15.5, duration=30.0, dry_run=True)

        self.assertIn("-ss", cmd)
        self.assertIn("15.5", cmd)
        self.assertIn("-t", cmd)
        self.assertIn("30.0", cmd)
        self.assertIn("-c", cmd)
        self.assertIn("copy", cmd)
        self.assertIn("-movflags", cmd)
        self.assertIn("+faststart", cmd)


if __name__ == "__main__":
    unittest.main()
