"""
Unit and benchmark tests for Milestone 1: Offline ML Light Level Analyzer & Heuristics.
"""
import time
import socket
import pytest
import numpy as np

from s26_controller import (
    LightDetectorEngine,
    DetectorConfig,
    FrameMetrics,
    ZoneMetrics,
    fast_extract_luminance_rgb,
    fast_extract_luminance_yuv,
    compute_16bin_histogram,
    compute_percentiles,
    compute_clipping_ratios,
    slice_zones,
)


class TestRec709LuminanceExtraction:
    def test_rec709_pure_colors(self):
        # Red: (54 * 255) >> 8 = 53
        red = np.zeros((10, 10, 3), dtype=np.uint8)
        red[:, :, 0] = 255
        y_red = fast_extract_luminance_rgb(red)
        assert np.all(y_red == 53)

        # Green: (183 * 255) >> 8 = 182
        green = np.zeros((10, 10, 3), dtype=np.uint8)
        green[:, :, 1] = 255
        y_green = fast_extract_luminance_rgb(green)
        assert np.all(y_green == 182)

        # Blue: (19 * 255) >> 8 = 18
        blue = np.zeros((10, 10, 3), dtype=np.uint8)
        blue[:, :, 2] = 255
        y_blue = fast_extract_luminance_rgb(blue)
        assert np.all(y_blue == 18)

        # White: (54 + 183 + 19) * 255 >> 8 = 256 * 255 >> 8 = 255
        white = np.full((10, 10, 3), 255, dtype=np.uint8)
        y_white = fast_extract_luminance_rgb(white)
        assert np.all(y_white == 255)

        # Black: 0
        black = np.zeros((10, 10, 3), dtype=np.uint8)
        y_black = fast_extract_luminance_rgb(black)
        assert np.all(y_black == 0)

    def test_rec709_grayscale_passthrough(self):
        gray = np.full((90, 160), 100, dtype=np.uint8)
        y = fast_extract_luminance_rgb(gray)
        assert np.all(y == 100)

    def test_rec709_invalid_input(self):
        with pytest.raises(ValueError):
            fast_extract_luminance_rgb(np.zeros((10, 10, 2), dtype=np.uint8))


class TestYUVExtraction:
    def test_yuv_plane_contiguous(self):
        buf = np.arange(90 * 160, dtype=np.uint8)
        y = fast_extract_luminance_yuv(buf, height=90, width=160)
        assert y.shape == (90, 160)
        assert y[0, 0] == 0
        assert y[89, 159] == 14399 % 256

    def test_yuv_plane_strided(self):
        # 160 width with 192 stride (e.g. 32 byte row padding)
        stride = 192
        buf = np.zeros((90, stride), dtype=np.uint8)
        buf[:, :160] = 77
        buf[:, 160:] = 255  # padding
        y = fast_extract_luminance_yuv(buf, height=90, width=160, stride=stride)
        assert y.shape == (90, 160)
        assert np.all(y == 77)


class TestSpatialROISlicing:
    def test_4zone_geometry_and_pixel_counts(self):
        y_plane = np.zeros((90, 160), dtype=np.uint8)
        zones = slice_zones(y_plane)

        assert set(zones.keys()) == {"ceiling", "stage_center", "stage_flanks", "crowd_floor"}
        # Ceiling: 27 x 160 = 4320
        assert zones["ceiling"].shape == (27, 160)
        assert zones["ceiling"].size == 4320

        # Stage Center: 36 x 96 = 3456
        assert zones["stage_center"].shape == (36, 96)
        assert zones["stage_center"].size == 3456

        # Stage Flanks: 36 x 64 = 2304 (32 left + 32 right)
        assert zones["stage_flanks"].size == 2304

        # Crowd Floor: 27 x 160 = 4320
        assert zones["crowd_floor"].shape == (27, 160)
        assert zones["crowd_floor"].size == 4320

        # Total coverage
        total_zone_pixels = (
            zones["ceiling"].size
            + zones["stage_center"].size
            + zones["stage_flanks"].size
            + zones["crowd_floor"].size
        )
        assert total_zone_pixels == 90 * 160

    def test_zone_spatial_isolation(self):
        # 1. Only ceiling bright
        frame_ceil = np.zeros((90, 160), dtype=np.uint8)
        frame_ceil[:27, :] = 200
        z_ceil = slice_zones(frame_ceil)
        assert np.all(z_ceil["ceiling"] == 200)
        assert np.all(z_ceil["stage_center"] == 0)
        assert np.all(z_ceil["stage_flanks"] == 0)
        assert np.all(z_ceil["crowd_floor"] == 0)

        # 2. Only stage center bright
        frame_stage = np.zeros((90, 160), dtype=np.uint8)
        frame_stage[27:63, 32:128] = 220
        z_stage = slice_zones(frame_stage)
        assert np.all(z_stage["ceiling"] == 0)
        assert np.all(z_stage["stage_center"] == 220)
        assert np.all(z_stage["stage_flanks"] == 0)
        assert np.all(z_stage["crowd_floor"] == 0)

        # 3. Only crowd bright
        frame_crowd = np.zeros((90, 160), dtype=np.uint8)
        frame_crowd[63:, :] = 180
        z_crowd = slice_zones(frame_crowd)
        assert np.all(z_crowd["ceiling"] == 0)
        assert np.all(z_crowd["stage_center"] == 0)
        assert np.all(z_crowd["stage_flanks"] == 0)
        assert np.all(z_crowd["crowd_floor"] == 180)


class TestStatisticalMetrics:
    def test_16bin_micro_histogram(self):
        # Create array with known values in distinct bins
        # 0 -> bin 0, 16 -> bin 1, 32 -> bin 2, 240 -> bin 15
        arr = np.array([0, 16, 32, 240, 255], dtype=np.uint8)
        hist = compute_16bin_histogram(arr)
        assert len(hist) == 16
        assert np.isclose(np.sum(hist), 1.0)
        assert np.isclose(hist[0], 0.2)
        assert np.isclose(hist[1], 0.2)
        assert np.isclose(hist[2], 0.2)
        assert np.isclose(hist[15], 0.4)  # 240 and 255 are in bin 15

    def test_percentile_calculations(self):
        # Range 0 to 99
        arr = np.arange(100, dtype=np.uint8)
        pcts = compute_percentiles(arr, (10, 50, 90, 99))
        assert np.isclose(pcts["p10"], 9.9, atol=1.0)
        assert np.isclose(pcts["p50"], 49.5, atol=1.0)
        assert np.isclose(pcts["p90"], 89.1, atol=1.0)
        assert np.isclose(pcts["p99"], 98.01, atol=1.0)

    def test_clipping_ratios(self):
        arr = np.array([0, 5, 10, 50, 100, 245, 250, 255, 255, 255], dtype=np.uint8)
        c_high, c_dark = compute_clipping_ratios(arr, c_high_threshold=245, c_dark_threshold=10)
        # dark: 0, 5, 10 -> 3/10 = 0.3
        assert np.isclose(c_dark, 0.3)
        # high: 245, 250, 255, 255, 255 -> 5/10 = 0.5
        assert np.isclose(c_high, 0.5)


class TestLightDetectorEngine:
    def test_blackout_frame(self, blackout_frame_rgb):
        engine = LightDetectorEngine()
        metrics = engine.analyze_frame_rgb(blackout_frame_rgb, timestamp_ns=1_000_000_000)

        assert isinstance(metrics, FrameMetrics)
        assert metrics.mean_luma == 0.0
        assert metrics.p10 == 0.0
        assert metrics.p50 == 0.0
        assert metrics.p90 == 0.0
        assert metrics.p99 == 0.0
        assert metrics.c_dark == 1.0
        assert metrics.c_high == 0.0
        assert all(v == 0.0 for v in metrics.zone_lumas.values())
        assert len(metrics.histogram_16bin) == 16
        assert metrics.histogram_16bin[0] == 1.0

    def test_floodlight_frame(self, floodlight_frame_rgb):
        engine = LightDetectorEngine()
        metrics = engine.analyze_frame_rgb(floodlight_frame_rgb, timestamp_ns=1_000_000_000)

        assert metrics.mean_luma == 250.0
        assert metrics.p10 == 250.0
        assert metrics.p99 == 250.0
        assert metrics.c_high == 1.0
        assert metrics.c_dark == 0.0
        assert all(v == 250.0 for v in metrics.zone_lumas.values())

    def test_laser_spot_frame(self, laser_spot_frame_rgb):
        engine = LightDetectorEngine()
        metrics = engine.analyze_frame_rgb(laser_spot_frame_rgb, timestamp_ns=1_000_000_000)

        # Ceiling should be significantly brighter than crowd
        assert metrics.zone_lumas["ceiling"] > metrics.zone_lumas["crowd_floor"]
        assert metrics.p99 == 255.0
        assert metrics.c_high > 0.0
        cr = engine.get_spatial_contrast_ratio(metrics.zone_lumas)
        assert cr > 3.0

    def test_stage_spotlight_frame(self, stage_spotlight_frame_rgb):
        engine = LightDetectorEngine()
        metrics = engine.analyze_frame_rgb(stage_spotlight_frame_rgb, timestamp_ns=1_000_000_000)

        assert metrics.zone_lumas["stage_center"] > metrics.zone_lumas["crowd_floor"]
        pr = engine.get_stage_prominence_ratio(metrics.zone_lumas)
        assert pr > 5.0

    def test_temporal_velocity(self):
        engine = LightDetectorEngine()
        t0 = 1_000_000_000  # 1.0s
        t1 = 1_100_000_000  # 1.1s (dt = 0.1s)

        f0 = np.full((90, 160, 3), 50, dtype=np.uint8)
        f1 = np.full((90, 160, 3), 110, dtype=np.uint8)

        m0 = engine.analyze_frame_rgb(f0, timestamp_ns=t0)
        assert m0.luma_velocity == 0.0

        m1 = engine.analyze_frame_rgb(f1, timestamp_ns=t1)
        # delta luma = 110 - 50 = 60, dt = 0.1s -> velocity = 600.0 units/sec
        assert np.isclose(m1.luma_velocity, 600.0, atol=1.0)

    def test_detailed_zone_metrics(self, laser_spot_frame_rgb):
        engine = LightDetectorEngine()
        y_plane = fast_extract_luminance_rgb(laser_spot_frame_rgb)
        detailed = engine.get_detailed_zone_metrics(y_plane)

        assert set(detailed.keys()) == {"ceiling", "stage_center", "stage_flanks", "crowd_floor"}
        assert isinstance(detailed["ceiling"], ZoneMetrics)
        assert detailed["ceiling"].pixel_count == 4320
        assert detailed["ceiling"].p99 == 255.0
        assert detailed["crowd_floor"].p99 == 5.0

    def test_reset_functionality(self):
        engine = LightDetectorEngine()
        f = np.full((90, 160, 3), 100, dtype=np.uint8)
        engine.analyze_frame_rgb(f, timestamp_ns=1_000_000_000)
        assert engine.frame_count == 1
        assert engine.last_mean_luma == 100.0

        engine.reset()
        assert engine.frame_count == 0
        assert engine.last_mean_luma is None
        assert engine.last_timestamp_ns is None


class TestOfflineZeroNetworkContract:
    def test_zero_network_calls_during_detection(self, monkeypatch):
        # Guard: monkeypatch socket to disallow any outbound network connection
        def forbidden_socket(*args, **kwargs):
            raise AssertionError("Network socket creation attempted during offline light detection!")

        monkeypatch.setattr(socket, "socket", forbidden_socket)

        engine = LightDetectorEngine()
        for _ in range(50):
            dummy = np.random.randint(0, 256, (90, 160, 3), dtype=np.uint8)
            metrics = engine.analyze_frame_rgb(dummy)
            assert isinstance(metrics, FrameMetrics)


class TestLatencyBenchmark:
    def test_benchmark_sub_millisecond_execution(self):
        engine = LightDetectorEngine()
        frame = np.random.randint(0, 256, (90, 160, 3), dtype=np.uint8)

        # Warm-up (100 frames)
        for _ in range(100):
            engine.analyze_frame_rgb(frame)

        # Timed benchmark run (500 frames)
        num_frames = 500
        durations = []

        for i in range(num_frames):
            start = time.perf_counter_ns()
            engine.analyze_frame_rgb(frame, timestamp_ns=start)
            end = time.perf_counter_ns()
            durations.append((end - start) / 1e6)  # ms

        mean_ms = float(np.mean(durations))
        p99_ms = float(np.percentile(durations, 99))
        max_ms = float(np.max(durations))

        print(f"\nBenchmark Latency: Mean={mean_ms:.3f}ms, P99={p99_ms:.3f}ms, Max={max_ms:.3f}ms")

        # Strict requirement: Mean < 1.0ms on 160x90 frames, Max < 5.0ms
        assert mean_ms < 1.0, f"Expected mean latency < 1.0ms, got {mean_ms:.3f}ms"
        assert max_ms < 5.0, f"Expected max latency < 5.0ms, got {max_ms:.3f}ms"
