"""
cli.py - Rich Command-Line Interface for S26 AI Camera Controller

Provides interactive commands for:
- Simulating EDM concert scenarios (Scenarios A through E)
- Benchmarking detector, state machine, and daemon compute latencies
- Running the live real-time controller daemon against ADB or Mock device
- Inspecting display profiles, coordinate maps, and Pro Video presets
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import List, Optional

import numpy as np

from s26_controller import __version__
from s26_controller.core.coordinates import (
    CameraParameter,
    CoordinateNormalizer,
    DisplayProfile,
    DisplayResolution,
    SamsungS26CoordinateMap,
)
from s26_controller.core.dispatcher import (
    AccessibilityGestureDispatcher,
    BaseDispatcher,
    CameraPreset,
    LightingRegime,
    MockDispatcher,
    PersistentADBDispatcher,
    TaskerIntentDispatcher,
)
from s26_controller.core.state_machine import DEFAULT_CAMERA_PRESETS
from s26_controller.daemon import DaemonStepResult, S26CameraControllerDaemon
from s26_controller.simulation.light_simulator import (
    ConcertLightSimulator,
    ConcertScenario,
)
from s26_controller.simulation.mock_device import MockAndroidDevice, MockDeviceDispatcher


def _create_dispatcher(
    dispatcher_type: str,
    display_profile: DisplayProfile,
    serial: Optional[str] = None,
    dry_run: bool = False,
) -> BaseDispatcher:
    """Factory creating the requested dispatcher backend."""
    dtype = dispatcher_type.lower()
    if dtype == "adb":
        return PersistentADBDispatcher(
            serial=serial,
            dry_run=dry_run,
            display_profile=display_profile,
        )
    elif dtype == "tasker":
        return TaskerIntentDispatcher(
            serial=serial,
            dry_run=dry_run,
            display_profile=display_profile,
        )
    elif dtype == "accessibility":
        return AccessibilityGestureDispatcher(display_profile=display_profile)
    elif dtype == "shizuku":
        from s26_controller.core.dispatcher import ShizukuDispatcher
        return ShizukuDispatcher(display_profile=display_profile)
    elif dtype == "mock_device":
        device = MockAndroidDevice(display_profile=display_profile)
        return MockDeviceDispatcher(device)
    else:
        return MockDispatcher(display_profile=display_profile)


def _resolve_profile(resolution_str: str) -> DisplayProfile:
    """Parses resolution parameter into DisplayProfile."""
    res = resolution_str.lower().strip()
    if res in ("wqhd", "wqhd+", "3120x1440"):
        return DisplayProfile.get_default_s26_ultra_wqhd(is_landscape=True)
    elif res in ("fhd", "fhd+", "2340x1080"):
        return DisplayProfile.get_default_s26_ultra_fhd(is_landscape=True)
    elif "x" in res:
        parts = res.split("x")
        try:
            w, h = int(parts[0]), int(parts[1])
            return DisplayProfile.from_resolution(w, h)
        except Exception:
            pass
    return DisplayProfile.get_default_s26_ultra_wqhd()


def cmd_simulate(args: argparse.Namespace) -> int:
    """Executes synthetic concert simulation scenario and prints telemetry."""
    print("=" * 80)
    print(f"  S26 AI Camera Controller — Concert Simulation Engine (v{__version__})")
    print("=" * 80)

    profile = _resolve_profile(args.resolution)
    dispatcher = _create_dispatcher(args.dispatcher, profile, serial=args.serial, dry_run=args.dry_run)

    daemon = S26CameraControllerDaemon(dispatcher=dispatcher)
    simulator = ConcertLightSimulator(fps=args.fps)

    scenarios_to_run: List[ConcertScenario] = []
    if args.scenario.lower() == "all":
        scenarios_to_run = [
            ConcertScenario.SCENARIO_A_BLACKOUT_DROP,
            ConcertScenario.SCENARIO_B_LASER_ASSAULT,
            ConcertScenario.SCENARIO_C_STROBE_TRAIN,
            ConcertScenario.SCENARIO_D_PYRO_FLOOD,
            ConcertScenario.SCENARIO_E_FULL_CONCERT_SET,
        ]
    else:
        # Match scenario name
        matched = False
        for s in ConcertScenario:
            if args.scenario.lower() in s.value.lower():
                scenarios_to_run.append(s)
                matched = True
                break
        if not matched:
            print(f"Error: Unknown scenario '{args.scenario}'. Available: {[s.value for s in ConcertScenario]}")
            return 1

    for scen in scenarios_to_run:
        print(f"\n[RUNNING SCENARIO] {scen.value} (FPS: {args.fps}, Duration: {args.duration or 'Auto'}s)")
        print("-" * 80)

        daemon.reset()
        frames = simulator.generate_scenario_frames(scen, duration_sec=args.duration, as_rgb=True)

        results: List[DaemonStepResult] = []
        for idx, (frame, t_ns) in enumerate(frames):
            res = daemon.step(frame, timestamp_ns=t_ns)
            results.append(res)
            if res.triggered and args.verbose:
                print(f"  [Frame {idx:04d} @ {t_ns*1e-9:.2f}s] TRIGGERED -> {res.regime.value} | {res.reason} | Preset: ISO {res.preset.iso} {res.preset.shutter_speed}")

        telemetry = daemon.get_telemetry()
        print(f"\n  [SCENARIO SUMMARY: {scen.value}]")
        print(f"  - Total Frames Processed: {telemetry.total_frames_processed}")
        print(f"  - Total Slider Dispatches: {telemetry.total_dispatches}")
        print(f"  - Final Lighting Regime:   {telemetry.current_regime.value}")
        print(f"  - Mean Compute Latency:    {telemetry.mean_compute_latency_ms:.3f} ms")
        print(f"  - P95 Compute Latency:     {telemetry.p95_compute_latency_ms:.3f} ms")
        print(f"  - P99 Compute Latency:     {telemetry.p99_compute_latency_ms:.3f} ms")

        if telemetry.transitions:
            print("\n  [REGIME TRANSITIONS]")
            print(f"  {'#':<3} | {'Frame':<6} | {'Time (s)':<8} | {'From Regime':<15} | {'To Regime':<15} | {'Preset (ISO/Shutter)':<22} | {'Reason'}")
            print("  " + "-" * 105)
            for tr in telemetry.transitions:
                preset_str = f"ISO {tr.preset.iso} @ {tr.preset.shutter_speed}" if tr.preset else "None"
                print(f"  {tr.transition_index:<3} | {tr.frame_index:<6} | {tr.timestamp_ns*1e-9:<8.2f} | {tr.from_regime.value:<15} | {tr.to_regime.value:<15} | {preset_str:<22} | {tr.reason}")

    print("\n" + "=" * 80)
    print("  Simulation Complete. All scenarios executed successfully.")
    print("=" * 80)
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Runs a high-throughput execution benchmark to verify sub-millisecond compute latency."""
    print("=" * 80)
    print(f"  S26 AI Camera Controller — Sub-Millisecond Benchmark (v{__version__})")
    print("=" * 80)

    num_frames = int(args.frames)
    fps = float(args.fps)
    print(f"Running benchmark across {num_frames:,} frames at simulated {fps:.0f} FPS...\n")

    profile = _resolve_profile(args.resolution)
    dispatcher = MockDispatcher(display_profile=profile)
    daemon = S26CameraControllerDaemon(dispatcher=dispatcher)
    simulator = ConcertLightSimulator(fps=fps)

    # Generate test set
    scenarios = [
        ConcertScenario.SCENARIO_A_BLACKOUT_DROP,
        ConcertScenario.SCENARIO_B_LASER_ASSAULT,
        ConcertScenario.SCENARIO_C_STROBE_TRAIN,
        ConcertScenario.SCENARIO_D_PYRO_FLOOD,
    ]

    all_frames: List[Tuple[np.ndarray, int]] = []
    frames_per_scen = max(10, num_frames // len(scenarios))
    for scen in scenarios:
        frames = simulator.generate_scenario_frames(scen, duration_sec=frames_per_scen / fps, as_rgb=True)
        all_frames.extend(frames)

    all_frames = all_frames[:num_frames]

    # Warmup
    warmup_frames = simulator.generate_scenario_frames(ConcertScenario.SCENARIO_E_FULL_CONCERT_SET, duration_sec=1.0, as_rgb=True)
    for f, t in warmup_frames:
        daemon.step(f, t)
    daemon.reset()

    # Benchmark loop
    t_start = time.perf_counter_ns()
    for f, t in all_frames:
        daemon.step(f, t)
    total_time_ns = time.perf_counter_ns() - t_start

    total_time_sec = total_time_ns * 1e-9
    fps_throughput = len(all_frames) / total_time_sec
    telemetry = daemon.get_telemetry()

    print(f"Benchmark Results ({len(all_frames):,} frames processed):")
    print(f"  - Total Elapsed Wall Time: {total_time_sec * 1000.0:.2f} ms")
    print(f"  - Throughput:              {fps_throughput:,.1f} frames/sec ({fps_throughput / 60.0:.1f}x real-time 60fps)")
    print(f"  - Mean Compute Latency:    {telemetry.mean_compute_latency_ms:.3f} ms")
    print(f"  - Min Compute Latency:     {telemetry.min_compute_latency_ms:.3f} ms")
    print(f"  - P50 (Median) Latency:    {telemetry.p50_compute_latency_ms:.3f} ms")
    print(f"  - P95 Latency:             {telemetry.p95_compute_latency_ms:.3f} ms")
    print(f"  - P99 Latency:             {telemetry.p99_compute_latency_ms:.3f} ms")
    print(f"  - Max Compute Latency:     {telemetry.max_compute_latency_ms:.3f} ms")

    # Contract Verification
    passed = telemetry.p99_compute_latency_ms < 1.0
    status_str = "PASSED (<1.0 ms contract)" if passed else "FAILED (exceeded 1.0 ms contract)"
    print(f"\n  [PERFORMANCE GATE]: {status_str}")

    if args.json_output:
        data = {
            "num_frames": len(all_frames),
            "fps_throughput": fps_throughput,
            "mean_ms": telemetry.mean_compute_latency_ms,
            "p50_ms": telemetry.p50_compute_latency_ms,
            "p95_ms": telemetry.p95_compute_latency_ms,
            "p99_ms": telemetry.p99_compute_latency_ms,
            "max_ms": telemetry.max_compute_latency_ms,
            "contract_passed": passed,
        }
        print("\nJSON Output:\n" + json.dumps(data, indent=2))

    return 0 if passed else 1


def cmd_run_daemon(args: argparse.Namespace) -> int:
    """Runs the live controller daemon loop against ADB device or mock source."""
    print("=" * 80)
    print(f"  S26 AI Camera Controller — Live Controller Daemon (v{__version__})")
    print("=" * 80)

    profile = _resolve_profile(args.resolution)
    dispatcher = _create_dispatcher(args.dispatcher, profile, serial=args.serial, dry_run=args.dry_run)
    daemon = S26CameraControllerDaemon(dispatcher=dispatcher)

    # Attach frame source
    simulator = ConcertLightSimulator(fps=args.fps)
    stream = simulator.stream_scenario(
        scenario=ConcertScenario.SCENARIO_E_FULL_CONCERT_SET,
        duration_sec=args.duration or 15.0,
        as_rgb=True,
        real_time=True,
    )

    print(f"Starting controller daemon loop [Dispatcher: {args.dispatcher}, FPS: {args.fps}]...")
    print("Press Ctrl+C to stop.\n")

    def _on_regime(from_reg, to_reg, preset):
        preset_str = f"ISO {preset.iso} @ {preset.shutter_speed}" if preset else ""
        print(f"  [*] REGIME SHIFT: {from_reg.value} -> {to_reg.value} | Dispatching: {preset_str}")

    daemon.on_regime_change = _on_regime

    try:
        daemon.process_stream(stream, fps=args.fps, real_time=True)
    except KeyboardInterrupt:
        print("\nStopping daemon...")
    finally:
        daemon.close()

    telemetry = daemon.get_telemetry()
    print("\nDaemon Stopped. Summary:")
    print(f"  Frames Processed: {telemetry.total_frames_processed}")
    print(f"  Dispatches:       {telemetry.total_dispatches}")
    print(f"  P99 Latency:      {telemetry.p99_compute_latency_ms:.3f} ms")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Displays display profiles, default presets, and UI coordinate mappings."""
    print("=" * 80)
    print(f"  S26 AI Camera Controller — System Information & UI Map (v{__version__})")
    print("=" * 80)

    print("\n[PRO VIDEO CAMERA PRESETS PER REGIME]")
    print(f"  {'Lighting Regime':<16} | {'Target ISO':<12} | {'Target Shutter':<15} | {'Description'}")
    print("  " + "-" * 80)
    for regime, preset in DEFAULT_CAMERA_PRESETS.items():
        print(f"  {regime.value:<16} | ISO {preset.iso:<8} | {preset.shutter_speed:<15} | {preset.reason}")

    print("\n[SAMSUNG S26 ULTRA DISPLAY PROFILES]")
    wqhd = DisplayProfile.get_default_s26_ultra_wqhd()
    fhd = DisplayProfile.get_default_s26_ultra_fhd()
    print(f"  - Native WQHD+ (Landscape): {wqhd.width} x {wqhd.height} pixels (500 ppi)")
    print(f"  - Standard FHD+ (Landscape): {fhd.width} x {fhd.height} pixels (375 ppi)")

    print("\n[PRO TOOLBAR RIBBON TOUCH TARGETS (WQHD+ Screen Coordinates)]")
    normalizer = CoordinateNormalizer(wqhd)
    for param in CameraParameter:
        if param in SamsungS26CoordinateMap.RIBBON_BUTTONS:
            norm_x, norm_y = SamsungS26CoordinateMap.RIBBON_BUTTONS[param]
            px_x, px_y = normalizer.to_screen_pixels(norm_x, norm_y)
            print(f"  - {param.value:<14}: Screen ({px_x:>4}px, {px_y:>4}px) [Norm: ({norm_x:.3f}, {norm_y:.3f})]")

    print("\n[ISO SLIDER TICKS (WQHD+ Screen Coordinates)]")
    for iso_key, (norm_x, norm_y) in SamsungS26CoordinateMap.ISO_SLIDER_TICKS.items():
        px_x, px_y = normalizer.to_screen_pixels(norm_x, norm_y)
        print(f"  - ISO {iso_key:<6}: Screen ({px_x:>4}px, {px_y:>4}px) [Norm: ({norm_x:.3f}, {norm_y:.3f})]")

    print("\n[SHUTTER SLIDER TICKS (WQHD+ Screen Coordinates)]")
    for speed_key, (norm_x, norm_y) in SamsungS26CoordinateMap.SHUTTER_SLIDER_TICKS.items():
        px_x, px_y = normalizer.to_screen_pixels(norm_x, norm_y)
        print(f"  - Shutter {speed_key:<8}: Screen ({px_x:>4}px, {px_y:>4}px) [Norm: ({norm_x:.3f}, {norm_y:.3f})]")

    print("\n" + "=" * 80)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Constructs the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="s26-controller",
        description="S26 AI Camera Controller: Real-Time EDM Concert Exposure Automation",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # simulate
    p_sim = subparsers.add_parser("simulate", help="Run synthetic EDM concert lighting simulation")
    p_sim.add_argument("--scenario", "-s", default="all", help="Scenario name (ScenarioA_BlackoutDrop, ScenarioB_LaserAssault, etc.) or 'all'")
    p_sim.add_argument("--fps", type=float, default=60.0, help="Simulation frame rate (default: 60.0)")
    p_sim.add_argument("--duration", "-d", type=float, default=None, help="Scenario duration in seconds (optional)")
    p_sim.add_argument("--dispatcher", default="mock", choices=["mock", "adb", "tasker", "accessibility", "shizuku", "mock_device"], help="Dispatcher backend")
    p_sim.add_argument("--resolution", default="wqhd", help="Target display resolution (wqhd, fhd, or WxH)")
    p_sim.add_argument("--serial", default=None, help="ADB device serial")
    p_sim.add_argument("--dry-run", action="store_true", help="Dry run mode for ADB / Tasker commands")
    p_sim.add_argument("--verbose", "-v", action="store_true", help="Print verbose step-by-step triggers")

    # benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run latency & throughput performance benchmark")
    p_bench.add_argument("--frames", "-n", type=int, default=1000, help="Number of benchmark frames (default: 1000)")
    p_bench.add_argument("--fps", type=float, default=60.0, help="Simulated frame rate")
    p_bench.add_argument("--resolution", default="wqhd", help="Target display resolution")
    p_bench.add_argument("--json-output", action="store_true", help="Output machine-readable JSON metrics")

    # run-daemon
    p_daemon = subparsers.add_parser("run-daemon", help="Run the live controller daemon loop")
    p_daemon.add_argument("--dispatcher", default="mock", choices=["mock", "adb", "tasker", "accessibility", "shizuku", "mock_device"], help="Dispatcher backend")
    p_daemon.add_argument("--fps", type=float, default=60.0, help="Capture/processing frame rate")
    p_daemon.add_argument("--duration", type=float, default=15.0, help="Duration to run daemon in seconds")
    p_daemon.add_argument("--resolution", default="wqhd", help="Target display resolution")
    p_daemon.add_argument("--serial", default=None, help="ADB device serial")
    p_daemon.add_argument("--dry-run", action="store_true", help="Dry run mode for ADB commands")

    # info
    subparsers.add_parser("info", help="Display S26 Ultra coordinate maps and Pro Video presets")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "simulate":
        return cmd_simulate(args)
    elif args.command == "benchmark":
        return cmd_benchmark(args)
    elif args.command == "run-daemon":
        return cmd_run_daemon(args)
    elif args.command == "info":
        return cmd_info(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
