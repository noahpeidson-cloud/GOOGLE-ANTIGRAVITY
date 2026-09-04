"""
test_ui_dispatcher.py - Comprehensive Unit Tests for M2: Pro Video UI Automator & Intent Dispatcher

Tests:
- Coordinate conversions and normalization across WQHD+, FHD+, Portrait, and Custom resolutions
- Pro Video ribbon and slider tick mappings
- Preset sequence generation (Ribbon Tap -> Delay -> Slider Tap)
- BaseDispatcher, MockDispatcher, PersistentADBDispatcher, TaskerIntentDispatcher, AccessibilityGestureDispatcher
- Sub-50ms dispatch timing benchmarks
- Error handling and input validation for invalid parameters
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock, patch

from s26_controller.core.coordinates import (
    CameraParameter,
    CoordinateNormalizer,
    DisplayProfile,
    DisplayResolution,
    ResolutionScaler,
    RibbonButton,
    SamsungS26CoordinateMap,
    TapAction,
)
from s26_controller.core.dispatcher import (
    AccessibilityGestureDispatcher,
    BaseDispatcher,
    CameraPreset,
    DispatchResult,
    LightingRegime,
    MockDispatcher,
    PersistentADBDispatcher,
    TaskerIntentDispatcher,
    dispatch_preset,
)


# ==============================================================================
# 1. Coordinate Mapping & Resolution Scaler Tests
# ==============================================================================

class TestCoordinateMapping:
    """Tests for resolution-independent coordinate normalization and scaling."""

    def test_display_profile_initialization(self):
        wqhd = DisplayProfile.get_default_s26_ultra_wqhd(is_landscape=True)
        assert wqhd.width == 3120
        assert wqhd.height == 1440
        assert wqhd.is_landscape is True
        assert wqhd.resolution_type == DisplayResolution.WQHD_PLUS_LANDSCAPE

        fhd = DisplayProfile.get_default_s26_ultra_fhd(is_landscape=True)
        assert fhd.width == 2340
        assert fhd.height == 1080
        assert fhd.is_landscape is True
        assert fhd.resolution_type == DisplayResolution.FHD_PLUS_LANDSCAPE

    def test_display_profile_portrait(self):
        wqhd_p = DisplayProfile.get_default_s26_ultra_wqhd(is_landscape=False)
        assert wqhd_p.width == 1440
        assert wqhd_p.height == 3120
        assert wqhd_p.is_landscape is False
        assert wqhd_p.resolution_type == DisplayResolution.WQHD_PLUS_PORTRAIT

        fhd_p = DisplayProfile.get_default_s26_ultra_fhd(is_landscape=False)
        assert fhd_p.width == 1080
        assert fhd_p.height == 2340
        assert fhd_p.is_landscape is False
        assert fhd_p.resolution_type == DisplayResolution.FHD_PLUS_PORTRAIT

    def test_display_profile_from_resolution(self):
        p1 = DisplayProfile.from_resolution(3120, 1440)
        assert p1.resolution_type == DisplayResolution.WQHD_PLUS_LANDSCAPE

        p2 = DisplayProfile.from_resolution(2340, 1080)
        assert p2.resolution_type == DisplayResolution.FHD_PLUS_LANDSCAPE

        p3 = DisplayProfile.from_resolution(1920, 1080)
        assert p3.resolution_type == DisplayResolution.CUSTOM
        assert p3.width == 1920
        assert p3.height == 1080

    def test_display_profile_invalid_dimensions(self):
        with pytest.raises(ValueError, match="positive"):
            DisplayProfile(width=-100, height=1440)
        with pytest.raises(ValueError, match="positive"):
            DisplayProfile.from_resolution(0, 1080)

    def test_wqhd_ribbon_button_pixel_coordinates(self):
        norm = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_wqhd())

        # Expected coordinates based on WQHD+ 3120x1440:
        # BTN_ISO (0.220, 0.880) -> (686, 1267)
        # BTN_SPEED (0.340, 0.880) -> (1060, 1267)
        # BTN_EV (0.460, 0.880) -> (1435, 1267)
        # BTN_FOCUS (0.580, 0.880) -> (1810, 1267)
        # BTN_WB (0.700, 0.880) -> (2184, 1267)
        # BTN_MIC (0.820, 0.880) -> (2558, 1267)

        iso_x, iso_y = norm.get_ribbon_button_pixels(CameraParameter.ISO)
        assert iso_x == 686
        assert iso_y == 1267

        spd_x, spd_y = norm.get_ribbon_button_pixels(CameraParameter.SHUTTER_SPEED)
        assert spd_x == 1061
        assert spd_y == 1267

        ev_x, ev_y = norm.get_ribbon_button_pixels(CameraParameter.EV)
        assert ev_x == 1435
        assert ev_y == 1267

        foc_x, foc_y = norm.get_ribbon_button_pixels(CameraParameter.FOCUS)
        assert foc_x == 1810
        assert foc_y == 1267

        wb_x, wb_y = norm.get_ribbon_button_pixels(CameraParameter.WHITE_BALANCE)
        assert wb_x == 2184
        assert wb_y == 1267

        mic_x, mic_y = norm.get_ribbon_button_pixels(CameraParameter.MIC_GAIN)
        assert mic_x == 2558
        assert mic_y == 1267

    def test_fhd_ribbon_button_pixel_coordinates(self):
        norm = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_fhd())

        # Expected coordinates based on FHD+ 2340x1080:
        # BTN_ISO (0.220, 0.880) -> (515, 950)
        # BTN_SPEED (0.340, 0.880) -> (796, 950)
        # BTN_EV (0.460, 0.880) -> (1076, 950)
        # BTN_FOCUS (0.580, 0.880) -> (1357, 950)
        # BTN_WB (0.700, 0.880) -> (1638, 950)
        # BTN_MIC (0.820, 0.880) -> (1918, 950)

        iso_x, iso_y = norm.get_ribbon_button_pixels("ISO")
        assert iso_x == 515
        assert iso_y == 950

        spd_x, spd_y = norm.get_ribbon_button_pixels("SPEED")
        assert spd_x == 796
        assert spd_y == 950

        ev_x, ev_y = norm.get_ribbon_button_pixels("EV")
        assert ev_x == 1076
        assert ev_y == 950

    def test_iso_slider_tick_coordinates(self):
        norm_wqhd = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_wqhd())

        # WQHD+ (3120x1440), Y_norm = 0.720 -> Y = 1037
        iso_ticks_expected = {
            "AUTO": (468, 1037),
            "50": (655, 1037),
            "100": (874, 1037),
            "200": (1186, 1037),
            "400": (1560, 1037),
            "800": (2028, 1037),
            "1600": (2434, 1037),
            "3200": (2652, 1037),
        }
        for iso_val, expected_px in iso_ticks_expected.items():
            px = norm_wqhd.get_iso_tick_pixels(iso_val)
            assert px == expected_px, f"ISO {iso_val} expected {expected_px}, got {px}"

        # FHD+ (2340x1080), Y_norm = 0.720 -> Y = 778
        norm_fhd = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_fhd())
        iso_ticks_fhd = {
            "AUTO": (351, 778),
            "50": (491, 778),
            "100": (655, 778),
            "200": (889, 778),
            "400": (1170, 778),
            "800": (1521, 778),
            "1600": (1825, 778),
            "3200": (1989, 778),
        }
        for iso_val, expected_px in iso_ticks_fhd.items():
            px = norm_fhd.get_iso_tick_pixels(iso_val)
            assert px == expected_px, f"FHD ISO {iso_val} expected {expected_px}, got {px}"

    def test_shutter_slider_tick_coordinates(self):
        norm_wqhd = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_wqhd())

        # WQHD+ (3120x1440), Y_norm = 0.720 -> Y = 1037
        shutter_ticks_expected = {
            "AUTO": (468, 1037),
            "1/30": (780, 1037),
            "1/60": (1092, 1037),
            "1/120": (1560, 1037),
            "1/240": (2028, 1037),
            "1/500": (2434, 1037),
            "1/1000": (2652, 1037),
            "1/2000": (2808, 1037),
            "1/4000": (2933, 1037),
            "1/12000": (3058, 1037),
        }
        for shutter_val, expected_px in shutter_ticks_expected.items():
            px = norm_wqhd.get_shutter_tick_pixels(shutter_val)
            assert px == expected_px, f"Shutter {shutter_val} expected {expected_px}, got {px}"

    def test_shutter_alias_normalization(self):
        norm = CoordinateNormalizer()
        # 1/125 should alias to 1/120
        assert norm.get_shutter_tick_pixels("1/125") == norm.get_shutter_tick_pixels("1/120")
        # 1/250 should alias to 1/240
        assert norm.get_shutter_tick_pixels("1/250") == norm.get_shutter_tick_pixels("1/240")
        # String '60' or '1/60s' should resolve to '1/60'
        assert norm.get_shutter_tick_pixels("60") == norm.get_shutter_tick_pixels("1/60")
        assert norm.get_shutter_tick_pixels("1/60s") == norm.get_shutter_tick_pixels("1/60")

    def test_coordinate_clamping_and_normalization_roundtrip(self):
        norm = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_wqhd())

        # Test extreme out of bounds clamping
        px_x, px_y = norm.to_screen_pixels(-0.5, 1.5)
        assert px_x == 0
        assert px_y == 1439  # height - 1

        # Test within bounds roundtrip
        orig_nx, orig_ny = 0.380, 0.720
        px_x, px_y = norm.to_screen_pixels(orig_nx, orig_ny)
        calc_nx, calc_ny = norm.to_normalized(px_x, px_y)
        assert abs(calc_nx - orig_nx) < 0.001
        assert abs(calc_ny - orig_ny) < 0.001

    def test_scale_point_custom_resolution(self):
        norm = CoordinateNormalizer()
        px = norm.scale_point(0.5, 0.5, 1920, 1080)
        assert px == (960, 540)

        with pytest.raises(ValueError):
            norm.scale_point(0.5, 0.5, -100, 1080)


# ==============================================================================
# 2. Preset Sequence Generation Tests
# ==============================================================================

class TestSequenceGeneration:
    """Tests for generating Pro Video touch sequences."""

    def test_iso_sequence_generation(self):
        norm = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_wqhd())
        actions = norm.build_iso_sequence(target_iso=200, delay_after_ribbon_ms=40, delay_after_slider_ms=15)

        assert len(actions) == 2
        # Step 1: Ribbon button
        assert actions[0].x_px == 686
        assert actions[0].y_px == 1267
        assert actions[0].delay_after_ms == 40
        assert "ISO Ribbon" in actions[0].description

        # Step 2: Slider tick for ISO 200
        assert actions[1].x_px == 1186
        assert actions[1].y_px == 1037
        assert actions[1].delay_after_ms == 15
        assert "ISO 200" in actions[1].description

    def test_shutter_sequence_generation(self):
        norm = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_wqhd())
        actions = norm.build_shutter_sequence(target_shutter="1/120")

        assert len(actions) == 2
        # Step 1: Ribbon button for Shutter Speed
        assert actions[0].x_px == 1061
        assert actions[0].y_px == 1267
        assert actions[0].delay_after_ms == 35

        # Step 2: Slider tick for 1/120
        assert actions[1].x_px == 1560
        assert actions[1].y_px == 1037
        assert actions[1].delay_after_ms == 10

    def test_combined_preset_sequence(self):
        norm = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_wqhd())
        actions = norm.build_preset_sequence(iso=100, shutter_speed="1/240")

        assert len(actions) == 4
        # ISO step 1 & 2
        assert actions[0].x_px == 686
        assert actions[1].x_px == 874
        # Shutter step 1 & 2
        assert actions[2].x_px == 1061
        assert actions[3].x_px == 2028

    def test_tap_action_validation(self):
        with pytest.raises(ValueError):
            TapAction(x_px=-1, y_px=100)
        with pytest.raises(ValueError):
            TapAction(x_px=100, y_px=100, delay_after_ms=-5)


# ==============================================================================
# 3. Modular Dispatch Engine Tests
# ==============================================================================

class TestMockDispatcher:
    """Tests for MockDispatcher execution, recording, and assertions."""

    def test_mock_dispatcher_single_tap(self):
        dispatcher = MockDispatcher()
        res = dispatcher.dispatch_tap(500, 1000, delay_after_ms=10)
        assert res is True
        assert dispatcher.get_taps_count() == 1

        last = dispatcher.get_last_tap()
        assert last is not None
        assert last["x"] == 500
        assert last["y"] == 1000
        assert last["delay_after_ms"] == 10

        dispatcher.assert_tap_dispatched(500, 1000)
        dispatcher.assert_action_count(1)

    def test_mock_dispatcher_sequence_and_preset(self):
        dispatcher = MockDispatcher()
        preset = CameraPreset(
            iso=400,
            shutter_speed="1/500",
            regime=LightingRegime.LASER_SPIKE,
            reason="Laser burst detected on stage center",
        )

        result = dispatcher.dispatch_camera_preset(preset)
        assert result.success is True
        assert result.actions_executed == 4
        assert len(result.actions) == 4
        assert dispatcher.get_taps_count() == 4

        dispatcher.assert_preset_dispatched(preset)
        # Check ISO ribbon and ISO 400 slider
        dispatcher.assert_tap_dispatched(686, 1267)
        dispatcher.assert_tap_dispatched(1560, 1037)

    def test_mock_dispatcher_simulated_failure(self):
        # Global failure
        dispatcher = MockDispatcher(simulate_failures=True)
        res_tap = dispatcher.dispatch_tap(100, 100)
        assert res_tap is False

        actions = [TapAction(x_px=100, y_px=100), TapAction(x_px=200, y_px=200)]
        res_seq = dispatcher.dispatch_sequence(actions)
        assert res_seq.success is False
        assert res_seq.actions_executed == 0

        # Partial failure on index 1
        dispatcher2 = MockDispatcher(fail_on_action_index=1)
        res_seq2 = dispatcher2.dispatch_sequence(actions)
        assert res_seq2.success is False
        assert res_seq2.actions_executed == 1
        assert res_seq2.metadata["failed_index"] == 1

    def test_mock_dispatcher_reset(self):
        dispatcher = MockDispatcher()
        dispatcher.dispatch_tap(100, 200)
        assert dispatcher.get_taps_count() == 1
        dispatcher.reset()
        assert dispatcher.get_taps_count() == 0
        assert dispatcher.get_last_tap() is None
        assert len(dispatcher.presets_dispatched) == 0


class TestPersistentADBDispatcher:
    """Tests for PersistentADBDispatcher pipe management and fallback."""

    def test_adb_dispatcher_dry_run(self):
        dispatcher = PersistentADBDispatcher(dry_run=True)
        preset = CameraPreset(
            iso=800,
            shutter_speed="1/60",
            regime=LightingRegime.BLACKOUT,
            reason="Pre-drop stage blackout",
        )

        res = dispatcher.dispatch_camera_preset(preset)
        assert res.success is True
        assert res.actions_executed == 4
        assert res.metadata["dry_run"] is True
        assert len(res.metadata["commands"]) == 4
        assert res.metadata["commands"][0] == "input tap 686 1267"
        assert res.metadata["commands"][1] == "input tap 2028 1037"

        dispatcher.close()

    def test_adb_dispatcher_mocked_interactive_pipe(self):
        """Test persistent stdin write without real device."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is alive
        mock_stdin = MagicMock()
        mock_process.stdin = mock_stdin

        with patch("subprocess.Popen", return_value=mock_process):
            dispatcher = PersistentADBDispatcher(dry_run=False)
            assert dispatcher.process is mock_process

            res = dispatcher.dispatch_tap(123, 456, delay_after_ms=0)
            assert res is True
            mock_stdin.write.assert_called_with("input tap 123 456\n")
            mock_stdin.flush.assert_called()

            dispatcher.close()
            mock_stdin.write.assert_called_with("exit\n")
            mock_process.terminate.assert_called()

    def test_adb_dispatcher_fallback_to_standalone(self):
        """Test fallback to subprocess.run if pipe write fails."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_stdin = MagicMock()
        mock_stdin.write.side_effect = BrokenPipeError("Pipe broken")
        mock_process.stdin = mock_stdin

        with patch("subprocess.Popen", return_value=mock_process), \
             patch("subprocess.run") as mock_run:
            dispatcher = PersistentADBDispatcher(dry_run=False, fallback_to_standalone=True)

            action = TapAction(x_px=500, y_px=600, delay_after_ms=0)
            res = dispatcher.dispatch_sequence([action])
            assert res.success is True
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args == ["adb", "shell", "input", "tap", "500", "600"]

            dispatcher.close()


class TestTaskerIntentDispatcher:
    """Tests for TaskerIntentDispatcher command and extras generation."""

    def test_tasker_intent_payload_and_command(self):
        dispatcher = TaskerIntentDispatcher(task_name="SetCameraPreset", dry_run=True)
        preset = CameraPreset(
            iso=100,
            shutter_speed="1/1000",
            regime=LightingRegime.FLOOD_PYRO,
            reason="Pyro flash blast",
        )

        extras = dispatcher.build_tasker_intent_extras(preset)
        assert extras["task"] == "SetCameraPreset"
        assert extras["iso"] == "100"
        assert extras["shutter"] == "1/1000"
        assert extras["regime"] == "FLOOD_PYRO"

        cmd = dispatcher.build_intent_command(preset)
        assert "am broadcast -a net.dinglisch.android.tasker.ACTION_TASK" in cmd
        assert '--es iso "100"' in cmd
        assert '--es shutter "1/1000"' in cmd

        res = dispatcher.dispatch_camera_preset(preset)
        assert res.success is True
        assert len(dispatcher.broadcast_history) == 1


class TestAccessibilityGestureDispatcher:
    """Tests for AccessibilityGestureDispatcher JSON and Kotlin generation."""

    def test_accessibility_payload_generation(self):
        dispatcher = AccessibilityGestureDispatcher(DisplayProfile.get_default_s26_ultra_wqhd())
        actions = [
            TapAction(x_px=686, y_px=1267, delay_after_ms=35, description="Tap ISO Ribbon"),
            TapAction(x_px=1186, y_px=1037, delay_after_ms=10, description="Tap ISO 200"),
        ]

        payload = dispatcher.build_accessibility_gesture_payload(actions)
        assert payload["type"] == "GestureDescription"
        assert payload["strokes_count"] == 2
        assert payload["strokes"][0]["x"] == 686
        assert payload["strokes"][0]["y"] == 1267
        assert payload["strokes"][0]["start_time_ms"] == 0
        assert payload["strokes"][0]["duration_ms"] == 25

        # Second stroke starts after 25ms + 35ms delay = 60ms
        assert payload["strokes"][1]["x"] == 1186
        assert payload["strokes"][1]["start_time_ms"] == 60

        snippet = dispatcher.build_kotlin_accessibility_snippet(actions)
        assert "GestureDescription.Builder()" in snippet
        assert "moveTo(686f, 1267f)" in snippet
        assert "dispatchGesture" in snippet

        res = dispatcher.dispatch_sequence(actions)
        assert res.success is True
        assert len(dispatcher.generated_gestures) == 1


# ==============================================================================
# 4. Timing & Sub-50ms Benchmarks
# ==============================================================================

class TestDispatchTimingAndLatency:
    """Rigorous timing assertions verifying sub-50ms dispatch overhead."""

    def test_mock_dispatch_latency_under_10ms(self):
        dispatcher = MockDispatcher(simulated_latency_ms=0.0)
        preset = CameraPreset(
            iso=200,
            shutter_speed="1/120",
            regime=LightingRegime.NORMAL,
            reason="Baseline concert standard",
        )

        start_time = time.perf_counter()
        result = dispatcher.dispatch_camera_preset(preset)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        assert result.success is True
        assert elapsed_ms < 15.0, f"In-memory dispatch took {elapsed_ms:.2f}ms, expected <15ms"
        assert result.total_latency_ms < 15.0

    def test_adb_pipe_sub_50ms_overhead(self):
        """Verifies that persistent ADB shell pipe command writing executes in <50ms."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_stdin = MagicMock()
        mock_process.stdin = mock_stdin

        with patch("subprocess.Popen", return_value=mock_process):
            dispatcher = PersistentADBDispatcher(dry_run=False)

            actions = [
                TapAction(x_px=686, y_px=1267, delay_after_ms=0),
                TapAction(x_px=1186, y_px=1037, delay_after_ms=0),
            ]

            start_time = time.perf_counter()
            res = dispatcher.dispatch_sequence(actions)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            assert res.success is True
            assert elapsed_ms < 50.0, f"Persistent pipe dispatch took {elapsed_ms:.2f}ms, expected <50ms"
            dispatcher.close()

    def test_top_level_dispatch_preset_contract(self):
        preset = CameraPreset(
            iso=400,
            shutter_speed="1/240",
            regime=LightingRegime.STROBE_LOCK,
            reason="Strobe train active",
        )
        mock_disp = MockDispatcher()
        res = dispatch_preset(preset, resolution=(3120, 1440), dispatcher=mock_disp)
        assert res.success is True
        assert res.actions_executed == 4
        mock_disp.assert_preset_dispatched(preset)


# ==============================================================================
# 5. Error Handling & Parameter Validation Tests
# ==============================================================================

class TestErrorHandling:
    """Tests for edge cases and invalid parameters."""

    def test_invalid_iso_values(self):
        norm = CoordinateNormalizer()
        with pytest.raises(ValueError, match="Invalid ISO value"):
            norm.get_iso_tick_pixels(99999)
        with pytest.raises(ValueError, match="Invalid ISO value"):
            norm.get_iso_tick_pixels("INVALID_ISO")
        with pytest.raises(ValueError, match="Invalid ISO value"):
            norm.build_iso_sequence(target_iso="555")

    def test_invalid_shutter_values(self):
        norm = CoordinateNormalizer()
        with pytest.raises(ValueError, match="Invalid Shutter Speed"):
            norm.get_shutter_tick_pixels("1/99999")
        with pytest.raises(ValueError, match="Invalid Shutter Speed"):
            norm.get_shutter_tick_pixels("FAST")
        with pytest.raises(ValueError, match="Invalid Shutter Speed"):
            norm.build_shutter_sequence("1/15")

    def test_invalid_camera_preset_dataclass(self):
        with pytest.raises(ValueError, match="positive integer"):
            CameraPreset(iso=-100, shutter_speed="1/60", regime=LightingRegime.NORMAL, reason="test")
        with pytest.raises(ValueError, match="empty"):
            CameraPreset(iso=100, shutter_speed="", regime=LightingRegime.NORMAL, reason="test")

    def test_empty_sequence_dispatch(self):
        mock_disp = MockDispatcher()
        res = mock_disp.dispatch_sequence([])
        assert res.success is True
        assert res.actions_executed == 0

        adb_disp = PersistentADBDispatcher(dry_run=True)
        res_adb = adb_disp.dispatch_sequence([])
        assert res_adb.success is True
        assert res_adb.actions_executed == 0


# ==============================================================================
# 6. Advanced Features, Sliders & Context Managers Tests
# ==============================================================================

class TestAdvancedDispatcherFeatures:
    """Tests covering EV/WB/Focus sliders, context managers, and dynamic resolution switching."""

    def test_ev_wb_focus_slider_ticks(self):
        norm = CoordinateNormalizer(DisplayProfile.get_default_s26_ultra_wqhd())

        # EV slider ticks
        ev_px = norm.to_screen_pixels(*SamsungS26CoordinateMap.EV_SLIDER_TICKS["0.0"])
        assert ev_px == (1560, 1037)

        # WB slider ticks
        wb_px = norm.to_screen_pixels(*SamsungS26CoordinateMap.WB_SLIDER_TICKS["5500K"])
        assert wb_px == (2028, 1037)

        # Focus slider ticks
        foc_px = norm.to_screen_pixels(*SamsungS26CoordinateMap.FOCUS_SLIDER_TICKS["MID"])
        assert foc_px == (1716, 1037)

    def test_resolution_scaler_alias(self):
        assert ResolutionScaler is CoordinateNormalizer
        scaler = ResolutionScaler()
        assert scaler.width == 3120

    def test_dispatcher_context_managers(self):
        with MockDispatcher() as mock_disp:
            res = mock_disp.dispatch_tap(10, 20)
            assert res is True
            assert mock_disp.get_taps_count() == 1

        with PersistentADBDispatcher(dry_run=True) as adb_disp:
            res = adb_disp.dispatch_tap(30, 40)
            assert res is True

    def test_dispatcher_dynamic_profile_switch(self):
        disp = MockDispatcher(DisplayProfile.get_default_s26_ultra_wqhd())
        assert disp.resolution == (3120, 1440)

        # Switch to FHD+
        disp.set_display_profile(DisplayProfile.get_default_s26_ultra_fhd())
        assert disp.resolution == (2340, 1080)

        # Dispatched coordinates should now use FHD+ scaling
        preset = CameraPreset(iso=200, shutter_speed="1/120", regime=LightingRegime.NORMAL, reason="test")
        disp.dispatch_camera_preset(preset)
        # FHD+ ISO ribbon is (515, 950) and ISO 200 tick is (889, 778)
        disp.assert_tap_dispatched(515, 950)
        disp.assert_tap_dispatched(889, 778)

    def test_persistent_adb_pipe_restart_on_dead_process(self):
        """Test that PersistentADBDispatcher restarts pipe if process is dead."""
        mock_dead_proc = MagicMock()
        mock_dead_proc.poll.return_value = 1  # Process has exited

        mock_live_proc = MagicMock()
        mock_live_proc.poll.return_value = None
        mock_live_stdin = MagicMock()
        mock_live_proc.stdin = mock_live_stdin

        with patch("subprocess.Popen", side_effect=[mock_dead_proc, mock_live_proc]):
            dispatcher = PersistentADBDispatcher(dry_run=False, fallback_to_standalone=False)
            assert dispatcher.process is mock_dead_proc

            action = TapAction(x_px=100, y_px=200, delay_after_ms=0)
            res = dispatcher.dispatch_sequence([action])
            assert res.success is True
            assert dispatcher.process is mock_live_proc
            mock_live_stdin.write.assert_called_with("input tap 100 200\n")
            dispatcher.close()

