"""
test_concert_scenarios.py - End-to-End EDM Concert Scenario & Daemon Simulation Tests

Validates full pipeline behavior across realistic concert dynamics:
- Scenario A: Blackout Drop (Pre-drop blackout -> bass drop laser ignition)
- Scenario B: Laser Assault (Collimated ceiling/stage laser bursts, P99=255)
- Scenario C: Strobe Train (10-18Hz Xenon/LED strobe pulse bursts, anti-hunting freeze)
- Scenario D: Pyro Flood (Full stage blinding floodlight wash Y >= 200)
- Scenario E: Full Concert Set (Multi-phase Sunbar set timeline)
- Sub-Millisecond Compute Latency Benchmark (<1.0ms contract)
- Mock Device Pro Video UI State Machine & Airplane Mode Verification
- CLI Entrypoint execution
"""

import sys
import numpy as np
import pytest

from s26_controller.core.coordinates import (
    CameraParameter,
    DisplayProfile,
    DisplayResolution,
    SamsungS26CoordinateMap,
)
from s26_controller.core.dispatcher import (
    BaseDispatcher,
    CameraPreset,
    LightingRegime,
    MockDispatcher,
)
from s26_controller.core.metrics import FrameMetrics
from s26_controller.daemon import (
    DaemonStepResult,
    DaemonTelemetry,
    S26CameraControllerDaemon,
)
from s26_controller.cli import main as cli_main
from s26_controller.simulation.light_simulator import (
    ConcertLightSimulator,
    ConcertScenario,
    generate_blackout_drop_scenario,
    generate_full_concert_set_scenario,
    generate_laser_assault_scenario,
    generate_pyro_flood_scenario,
    generate_scenario_frames,
    generate_strobe_train_scenario,
)
from s26_controller.simulation.mock_device import (
    MockAndroidDevice,
    MockDeviceDispatcher,
)


class TestLightSimulator:
    """Tests for ConcertLightSimulator frame generation and geometry."""

    def test_simulator_initialization(self):
        sim = ConcertLightSimulator(fps=60.0, width=160, height=90, seed=123)
        assert sim.fps == 60.0
        assert sim.width == 160
        assert sim.height == 90
        assert sim.y_ceil_cut == 27
        assert sim.y_stage_bot == 63
        assert sim.x_stage_left == 32
        assert sim.x_stage_right == 128

    def test_render_rgb_and_luma_shapes(self):
        sim = ConcertLightSimulator()
        luma = sim.render_luma_frame(ConcertScenario.SCENARIO_A_BLACKOUT_DROP, t_sec=0.5)
        assert luma.shape == (90, 160)
        assert luma.dtype == np.uint8

        rgb = sim.render_rgb_frame(ConcertScenario.SCENARIO_A_BLACKOUT_DROP, t_sec=0.5)
        assert rgb.shape == (90, 160, 3)
        assert rgb.dtype == np.uint8

    def test_all_preset_scenarios_generate_valid_frames(self):
        sim = ConcertLightSimulator()
        for scenario in ConcertScenario:
            if scenario == ConcertScenario.CUSTOM:
                continue
            frames = sim.generate_scenario_frames(scenario, duration_sec=1.0, as_rgb=True)
            assert len(frames) == 60
            f0, t0 = frames[0]
            assert f0.shape == (90, 160, 3)
            assert f0.dtype == np.uint8
            assert t0 > 0

    def test_stream_scenario_generator(self):
        sim = ConcertLightSimulator(fps=60.0)
        stream = sim.stream_scenario(ConcertScenario.SCENARIO_B_LASER_ASSAULT, duration_sec=0.5, as_rgb=False)
        collected = list(stream)
        assert len(collected) == 30
        for i in range(len(collected) - 1):
            assert collected[i + 1][1] > collected[i][1]  # Monotonic timestamps

    def test_seed_reproducibility(self):
        sim1 = ConcertLightSimulator(seed=999)
        sim2 = ConcertLightSimulator(seed=999)
        f1 = sim1.render_rgb_frame(ConcertScenario.SCENARIO_E_FULL_CONCERT_SET, t_sec=6.0)
        f2 = sim2.render_rgb_frame(ConcertScenario.SCENARIO_E_FULL_CONCERT_SET, t_sec=6.0)
        np.testing.assert_array_equal(f1, f2)


class TestScenarioABlackoutDrop:
    """
    Tier 4 Test: Scenario A — Pre-Drop Stage Blackout followed by Bass Drop Ignition.
    Timeline:
    - 0.0s - 1.5s: Ambient club baseline -> NORMAL regime
    - 1.5s - 3.5s: Pitch-black pre-drop blackout -> transitions to BLACKOUT (ISO 250)
    - 3.5s - 5.5s: Bass drop laser hit -> transitions to LASER_SPIKE (ISO 100, 1/250s)
    - 5.5s - 7.0s: Mainstage visuals -> recovers to NORMAL
    """

    def test_scenario_a_pipeline_execution(self):
        dispatcher = MockDispatcher()
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)
        simulator = ConcertLightSimulator(fps=60.0, seed=42)

        frames = simulator.generate_scenario_frames(
            ConcertScenario.SCENARIO_A_BLACKOUT_DROP,
            duration_sec=7.0,
            as_rgb=True,
        )
        assert len(frames) == 420

        results = [daemon.step(frame, timestamp_ns=t_ns) for frame, t_ns in frames]

        # Extract regimes by time
        regimes = [r.regime for r in results]

        # 1. Baseline ambient (0.0s - 1.2s): should be NORMAL
        baseline_slice = regimes[10:70]
        assert all(reg == LightingRegime.NORMAL for reg in baseline_slice), f"Expected NORMAL in baseline, got {set(baseline_slice)}"

        # 2. Blackout window (2.0s - 3.2s, frames 120 - 192): must transition to BLACKOUT
        blackout_slice = regimes[130:190]
        assert any(reg == LightingRegime.BLACKOUT for reg in blackout_slice)

        # Verify blackout preset was dispatched
        blackout_dispatches = [
            r for r in results if r.triggered and r.preset and r.preset.regime == LightingRegime.BLACKOUT
        ]
        assert len(blackout_dispatches) >= 1
        assert blackout_dispatches[0].preset.iso in (200, 250)
        assert blackout_dispatches[0].preset.shutter_speed == "1/60"

        # 3. Bass drop lasers (4.0s - 5.0s, frames 240 - 300): must transition to LASER_SPIKE
        drop_slice = regimes[250:300]
        assert any(reg == LightingRegime.LASER_SPIKE for reg in drop_slice)

        laser_dispatches = [
            r for r in results if r.triggered and r.preset and r.preset.regime == LightingRegime.LASER_SPIKE
        ]
        assert len(laser_dispatches) >= 1
        assert laser_dispatches[0].preset.iso == 100

        # Verify dispatcher received presets
        assert any(p.regime == LightingRegime.BLACKOUT for p in dispatcher.presets_dispatched)
        assert any(p.regime == LightingRegime.LASER_SPIKE for p in dispatcher.presets_dispatched)


class TestScenarioBLaserAssault:
    """
    Tier 4 Test: Scenario B — Laser Beam Sweeps & High Intensity Bursts.
    Timeline:
    - 0.0s - 1.0s: Dark stage baseline (Y ~ 30) -> NORMAL regime
    - 1.0s - 4.0s: Intense collimated laser array (P99=255 in ceiling/stage, crowd dark)
    - 4.0s - 5.5s: Return to balanced stage -> NORMAL
    """

    def test_scenario_b_laser_detection_and_clamp(self):
        dispatcher = MockDispatcher()
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)
        simulator = ConcertLightSimulator(fps=60.0, seed=42)

        frames = simulator.generate_scenario_frames(
            ConcertScenario.SCENARIO_B_LASER_ASSAULT,
            duration_sec=5.5,
            as_rgb=True,
        )

        results = [daemon.step(frame, timestamp_ns=t_ns) for frame, t_ns in frames]

        # Laser assault window (1.5s - 3.5s, frames 90 - 210)
        laser_frames = results[90:210]
        laser_regimes = [r.regime for r in laser_frames]
        assert LightingRegime.LASER_SPIKE in laser_regimes

        # Verify laser preset was dispatched
        laser_dispatches = [
            r for r in results if r.triggered and r.preset and r.preset.regime == LightingRegime.LASER_SPIKE
        ]
        assert len(laser_dispatches) >= 1
        assert laser_dispatches[0].preset.iso == 100
        assert laser_dispatches[0].preset.shutter_speed in ("1/240", "1/250", "1/500")

        # Verify crowd darkness did not prevent laser trigger
        laser_metrics = [r.metrics for r in laser_frames if r.regime == LightingRegime.LASER_SPIKE]
        assert any(m.zone_lumas.get("ceiling", 0) > 100 for m in laser_metrics)

        # Verify recovery to NORMAL after laser turns off
        end_frames = results[300:]
        assert any(r.regime == LightingRegime.NORMAL for r in end_frames)


class TestScenarioCStrobeTrain:
    """
    Tier 4 Test: Scenario C — 10-18Hz Strobe Train Anti-Hunting & Exposure Freeze.
    Timeline:
    - 0.0s - 1.0s: Ambient baseline -> NORMAL regime
    - 1.0s - 4.0s: 14 Hz Strobe train -> STROBE_LOCK engaged, zero UI slider chattering
    - 4.0s - 5.5s: Cooldown -> recovers to NORMAL
    """

    def test_scenario_c_strobe_lock_and_zero_hunting(self):
        dispatcher = MockDispatcher()
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)
        simulator = ConcertLightSimulator(fps=60.0, seed=42)

        frames = simulator.generate_scenario_frames(
            ConcertScenario.SCENARIO_C_STROBE_TRAIN,
            duration_sec=5.5,
            as_rgb=True,
        )

        results = [daemon.step(frame, timestamp_ns=t_ns) for frame, t_ns in frames]

        # Strobe active window: 1.5s - 3.8s (frames 90 - 228)
        strobe_results = results[90:228]

        # Strobe lock must engage
        strobe_regimes = [r.regime for r in strobe_results]
        assert LightingRegime.STROBE_LOCK in strobe_regimes

        # Anti-hunting invariant: while STROBE_LOCK is active, ZERO UI adjustments are dispatched
        dispatches_during_lock = [
            r for r in strobe_results if r.triggered and r.regime == LightingRegime.STROBE_LOCK
        ]
        assert len(dispatches_during_lock) == 0, (
            f"Exposure hunting violation! Dispatched {len(dispatches_during_lock)} times during strobe lock!"
        )

        # After strobe cessation (4.5s - 5.5s), daemon must recover to NORMAL
        recovery_results = results[270:]
        assert any(r.regime == LightingRegime.NORMAL for r in recovery_results)


class TestScenarioDPyroFlood:
    """
    Tier 4 Test: Scenario D — Full Arena Pyro Floodlight Wash (Y >= 200).
    Timeline:
    - 0.0s - 1.0s: Baseline stage -> NORMAL
    - 1.0s - 3.0s: Full arena pyro wash (Y >= 210, C_high >= 0.50) -> FLOOD_PYRO (ISO 100, 1/125s)
    - 3.0s - 5.0s: Cooldown wash -> returns to NORMAL
    """

    def test_scenario_d_pyro_flood_and_recovery(self):
        dispatcher = MockDispatcher()
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)
        simulator = ConcertLightSimulator(fps=60.0, seed=42)

        frames = simulator.generate_scenario_frames(
            ConcertScenario.SCENARIO_D_PYRO_FLOOD,
            duration_sec=5.0,
            as_rgb=True,
        )

        results = [daemon.step(frame, timestamp_ns=t_ns) for frame, t_ns in frames]

        # Flood window (1.2s - 2.8s, frames 72 - 168)
        flood_results = results[72:168]
        flood_regimes = [r.regime for r in flood_results]
        assert LightingRegime.FLOOD_PYRO in flood_regimes

        # Verify flood preset was dispatched
        flood_dispatches = [
            r for r in results if r.triggered and r.preset and r.preset.regime == LightingRegime.FLOOD_PYRO
        ]
        assert len(flood_dispatches) >= 1
        assert flood_dispatches[0].preset.iso == 100
        assert flood_dispatches[0].preset.shutter_speed in ("1/120", "1/125")

        # Verify exit after flood cools down
        cooldown_results = results[240:]
        assert any(r.regime == LightingRegime.NORMAL for r in cooldown_results)


class TestScenarioEFullConcertSet:
    """
    Tier 4 Test: Scenario E — 15-Second Multi-Phase Live EDM Set Timeline.
    Verifies full transitions:
    Warmup -> Breakdown -> Blackout -> Drop Lasers -> Strobe Train -> Pyro Flood -> Stable Mainstage
    """

    def test_full_concert_set_multi_phase_execution(self):
        dispatcher = MockDispatcher()
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)
        simulator = ConcertLightSimulator(fps=60.0, seed=42)

        frames = simulator.generate_scenario_frames(
            ConcertScenario.SCENARIO_E_FULL_CONCERT_SET,
            duration_sec=15.0,
            as_rgb=True,
        )
        assert len(frames) == 900

        results = [daemon.step(frame, timestamp_ns=t_ns) for frame, t_ns in frames]

        telemetry = daemon.get_telemetry()
        assert telemetry.total_frames_processed == 900

        # Regimes visited throughout set
        visited_regimes = {tr.to_regime for tr in telemetry.transitions}
        assert LightingRegime.BLACKOUT in visited_regimes or any(r.regime == LightingRegime.BLACKOUT for r in results)
        assert LightingRegime.LASER_SPIKE in visited_regimes or any(r.regime == LightingRegime.LASER_SPIKE for r in results)
        assert any(r.regime == LightingRegime.STROBE_LOCK for r in results)
        assert LightingRegime.FLOOD_PYRO in visited_regimes or any(r.regime == LightingRegime.FLOOD_PYRO for r in results)

        # Rate limiter constraint: maximum ~15-20 dispatches across 15 seconds (no chattering)
        assert telemetry.total_dispatches <= 20, f"Excessive dispatches ({telemetry.total_dispatches}); possible chattering!"


class TestDaemonLatencyBenchmark:
    """
    Latency & Performance Benchmark:
    Verifies that LightDetectorEngine + ConcertStateMachine compute latency is strictly <1.0ms per frame.
    """

    def test_benchmark_sub_millisecond_compute_latency(self):
        dispatcher = MockDispatcher()
        daemon = S26CameraControllerDaemon(dispatcher=dispatcher)
        simulator = ConcertLightSimulator(fps=60.0, seed=42)

        # 600 frames of mixed scenarios (10 seconds)
        frames = simulator.generate_scenario_frames(
            ConcertScenario.SCENARIO_E_FULL_CONCERT_SET,
            duration_sec=10.0,
            as_rgb=True,
        )

        # Warmup loop for steady-state JIT execution
        for frame, t_ns in frames[:30]:
            daemon.step(frame, timestamp_ns=t_ns)
        daemon.reset()

        for frame, t_ns in frames:
            daemon.step(frame, timestamp_ns=t_ns)

        telemetry = daemon.get_telemetry()

        # Assert performance guarantees
        assert telemetry.total_frames_processed == len(frames)
        assert telemetry.mean_compute_latency_ms < 0.80, f"Mean compute latency {telemetry.mean_compute_latency_ms:.3f}ms exceeded 0.80ms"
        assert telemetry.p99_compute_latency_ms < 1.00, f"P99 compute latency {telemetry.p99_compute_latency_ms:.3f}ms exceeded 1.00ms"

        # Assert contract helper
        daemon.assert_performance_contract(max_p99_compute_latency_ms=1.0)


class TestMockDeviceIntegration:
    """
    Tests MockAndroidDevice emulation of Samsung Camera Pro Video Mode:
    - Verifies Pro Video UI state tracking on tap injection
    - Verifies Tasker broadcast intent parsing
    - Verifies Airplane mode offline compliance
    """

    def test_mock_device_pro_video_slider_actuation(self):
        device = MockAndroidDevice()
        dispatcher = MockDeviceDispatcher(device)

        assert device.current_iso == 640
        assert device.current_shutter == "1/60"

        # Dispatch ISO 100 preset
        preset_laser = CameraPreset(
            iso=100,
            shutter_speed="1/250",
            regime=LightingRegime.LASER_SPIKE,
            reason="Laser clamp",
        )
        res = dispatcher.dispatch_camera_preset(preset_laser)
        assert res.success is True

        # Device internal state should now reflect ISO 100 and Shutter 1/240 or 1/250
        device.assert_iso_equals(100)
        assert device.current_shutter in ("1/240", "1/250")

    def test_mock_device_shell_command_execution(self):
        device = MockAndroidDevice()

        # 1. Tap ISO button (norm: 0.22, 0.88 -> WQHD: 686, 1267)
        res1 = device.execute_shell_command("input tap 686 1267")
        assert res1 == "OK"
        assert device.state.active_ribbon == CameraParameter.ISO
        assert device.state.slider_open is True

        # 2. Tap ISO 250 tick (norm ~0.44 -> px ~ 1373, 1037) or ISO 200 tick (1186, 1037)
        res2 = device.execute_shell_command("input tap 1186 1037")
        assert res2 == "OK"
        device.assert_iso_equals(200)

        # 3. Tasker broadcast command
        cmd_tasker = 'am broadcast -a net.dinglisch.android.tasker.ACTION_TASK --es task "SetCameraPreset" --es iso "400" --es shutter "1/120"'
        res3 = device.execute_shell_command(cmd_tasker)
        assert "Broadcast completed" in res3
        device.assert_iso_equals(400)
        device.assert_shutter_equals("1/120")

    def test_mock_device_airplane_mode_offline_guarantee(self):
        device = MockAndroidDevice(airplane_mode=True)
        device.assert_airplane_mode_compliance()


class TestCLISubcommands:
    """Tests for the s26-controller CLI entrypoints."""

    def test_cli_info(self, capsys):
        code = cli_main(["info"])
        assert code == 0
        captured = capsys.readouterr()
        assert "S26 AI Camera Controller" in captured.out
        assert "PRO VIDEO CAMERA PRESETS" in captured.out

    def test_cli_benchmark(self, capsys):
        code = cli_main(["benchmark", "--frames", "200", "--fps", "60"])
        assert code == 0
        captured = capsys.readouterr()
        assert "Benchmark Results" in captured.out
        assert "PASSED (<1.0 ms contract)" in captured.out

    def test_cli_simulate_single_scenario(self, capsys):
        code = cli_main(["simulate", "--scenario", "ScenarioA_BlackoutDrop", "--duration", "2.0", "--fps", "60"])
        assert code == 0
        captured = capsys.readouterr()
        assert "SCENARIO SUMMARY" in captured.out
