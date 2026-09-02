"""
light_simulator.py - Realistic EDM Concert Light Dynamics & Scenario Generator

Produces 160x90 preview frames (RGB uint8 or grayscale uint8) simulating authentic
EDM concert lighting dynamics at venues like Sunbar:
- Scenario A: Blackout Drop (ambient -> sudden blackout <5 luma -> bass drop lasers)
- Scenario B: Laser Assault (collimated ceiling/stage laser bursts, P99=255, dark crowd)
- Scenario C: Strobe Train (10-18Hz Xenon/LED strobe pulse bursts)
- Scenario D: Pyro Flood (full stage blinding floodlight wash Y >= 200)
- Scenario E: Full Concert Set (multi-phase Sunbar set timeline)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import time
from typing import Dict, Iterator, List, Optional, Tuple, Union
import numpy as np


class ConcertScenario(str, Enum):
    """Supported synthetic EDM concert scenarios."""
    SCENARIO_A_BLACKOUT_DROP = "ScenarioA_BlackoutDrop"
    SCENARIO_B_LASER_ASSAULT = "ScenarioB_LaserAssault"
    SCENARIO_C_STROBE_TRAIN = "ScenarioC_StrobeTrain"
    SCENARIO_D_PYRO_FLOOD = "ScenarioD_PyroFlood"
    SCENARIO_E_FULL_CONCERT_SET = "ScenarioE_FullConcertSet"
    CUSTOM = "Custom"


# Aliases for convenience
ScenarioType = ConcertScenario


@dataclass
class ScenarioPhase:
    """Represents a discrete lighting phase within a concert timeline."""
    name: str
    start_sec: float
    end_sec: float
    base_luma: float
    ceiling_boost: float = 0.0
    stage_boost: float = 0.0
    crowd_luma: float = 15.0
    laser_active: bool = False
    laser_intensity: float = 0.0
    laser_beam_count: int = 0
    strobe_active: bool = False
    strobe_freq_hz: float = 0.0
    pyro_active: bool = False
    noise_sigma: float = 2.0


class ConcertLightSimulator:
    """
    Realistic 160x90 EDM concert lighting generator and timeline simulator.
    Produces high-fidelity synthetic preview frames modeling spatial lighting zones:
    - Ceiling (top 30%, y: 0..27): Overhead lasers, truss moving heads, blinders
    - Stage Center (middle 40%, y: 27..63, x: 32..128): DJ booth, LED backdrop, keylight
    - Stage Flanks (middle 40%, y: 27..63, x: 0..32, 128..160): Side blinders, side lasers
    - Crowd Floor (bottom 30%, y: 63..90): Crowd silhouettes, phone screens, floor spill
    """

    def __init__(
        self,
        fps: float = 60.0,
        width: int = 160,
        height: int = 90,
        seed: Optional[int] = 42,
    ) -> None:
        self.fps = float(fps)
        self.width = int(width)
        self.height = int(height)
        self.seed = seed
        self._rng = np.random.default_rng(seed)

        # Coordinate grids for fast spatial rendering
        y_coords, x_coords = np.mgrid[0:self.height, 0:self.width]
        self._y_grid = y_coords.astype(np.float32)
        self._x_grid = x_coords.astype(np.float32)

        # Zone boundaries
        self.y_ceil_cut = int(round(self.height * 0.30))
        self.y_stage_bot = int(round(self.height * 0.70))
        self.x_stage_left = int(round(self.width * 0.20))
        self.x_stage_right = int(round(self.width * 0.80))

        # Zone masks
        self._mask_ceiling = self._y_grid < self.y_ceil_cut
        self._mask_stage_center = (
            (self._y_grid >= self.y_ceil_cut)
            & (self._y_grid < self.y_stage_bot)
            & (self._x_grid >= self.x_stage_left)
            & (self._x_grid < self.x_stage_right)
        )
        self._mask_stage_flanks = (
            (self._y_grid >= self.y_ceil_cut)
            & (self._y_grid < self.y_stage_bot)
            & ((self._x_grid < self.x_stage_left) | (self._x_grid >= self.x_stage_right))
        )
        self._mask_crowd = self._y_grid >= self.y_stage_bot

    def reset_seed(self, seed: Optional[int] = None) -> None:
        """Reset the internal RNG seed for deterministic reproducibility."""
        self.seed = seed
        self._rng = np.random.default_rng(seed)

    def _render_laser_beams(
        self,
        frame: np.ndarray,
        t_sec: float,
        intensity: float = 255.0,
        beam_count: int = 4,
    ) -> None:
        """
        Renders sharp, collimated laser beams emanating across the ceiling and stage center.
        """
        for b in range(beam_count):
            # Dynamic smooth angle sweep
            phase_offset = b * (math.pi / max(1, beam_count))
            sweep_angle = math.sin(t_sec * 1.5 + phase_offset) * 0.6
            origin_x = self.width * (0.15 + 0.70 * (b / max(1, beam_count - 1)))
            origin_y = 0.0

            # Distance from point (x, y) to beam line
            dx = self._x_grid - origin_x
            dy = self._y_grid - origin_y
            cos_a = math.cos(sweep_angle + math.pi / 2)
            sin_a = math.sin(sweep_angle + math.pi / 2)
            dist_to_beam = np.abs(dx * cos_a - dy * sin_a)

            # Laser beam profile: core (3.0px width) with exponential falloff
            beam_mask = np.exp(-0.5 * (dist_to_beam / 3.0) ** 2)

            # Laser beam illuminates ceiling and upper stage
            vertical_decay = np.clip(1.0 - (self._y_grid / (self.y_stage_bot * 1.25)), 0.0, 1.0)
            laser_layer = beam_mask * vertical_decay * intensity

            # Add to frame with saturation
            frame[:, :] = np.clip(frame + laser_layer, 0.0, 255.0)

    def _render_stage_backdrop(
        self,
        frame: np.ndarray,
        t_sec: float,
        intensity: float = 60.0,
    ) -> None:
        """Renders LED backdrop visuals and center DJ booth lighting."""
        if intensity <= 0:
            return
        center_x = (self.x_stage_left + self.x_stage_right) / 2.0
        center_y = (self.y_ceil_cut + self.y_stage_bot) / 2.0
        dx = (self._x_grid - center_x) / max(1.0, ((self.x_stage_right - self.x_stage_left) / 2.0))
        dy = (self._y_grid - center_y) / max(1.0, ((self.y_stage_bot - self.y_ceil_cut) / 2.0))
        radial = np.clip(1.0 - (dx ** 2 + dy ** 2), 0.0, 1.0)

        # LED ambient graphic wash
        pulse = 0.95 + 0.05 * math.sin(t_sec * 0.5)
        stage_light = self._mask_stage_center * radial * intensity * pulse
        frame[:, :] = np.clip(frame + stage_light, 0.0, 255.0)

    def render_luma_frame(
        self,
        scenario: Union[ConcertScenario, str],
        t_sec: float,
        frame_idx: int = 0,
    ) -> np.ndarray:
        """
        Renders a single 2D grayscale luminance frame (H, W) uint8 for the given scenario and timestamp.
        """
        scenario_key = ConcertScenario(scenario) if isinstance(scenario, str) else scenario
        phases = self.get_scenario_timeline(scenario_key)

        # Find active phase
        active_phase: Optional[ScenarioPhase] = None
        for p in phases:
            if p.start_sec <= t_sec < p.end_sec:
                active_phase = p
                break
        if active_phase is None:
            active_phase = phases[-1] if phases else ScenarioPhase("Default", 0.0, 10.0, 50.0)

        # 1. Base ambient frame
        frame = np.zeros((self.height, self.width), dtype=np.float32)

        # Apply base zonal lumas
        frame[self._mask_ceiling] = active_phase.base_luma + active_phase.ceiling_boost
        frame[self._mask_stage_center] = active_phase.base_luma + active_phase.stage_boost
        frame[self._mask_stage_flanks] = active_phase.base_luma + (active_phase.stage_boost * 0.5)
        frame[self._mask_crowd] = active_phase.crowd_luma

        # 2. Stage backdrop graphics
        if active_phase.base_luma > 10.0:
            self._render_stage_backdrop(frame, t_sec, intensity=active_phase.stage_boost + 20.0)

        # 3. Pyro / Arena Flood Wash
        if active_phase.pyro_active:
            # Full blinding blast across all zones with slight center hotspot
            frame[:, :] = np.clip(frame + 220.0, 0.0, 255.0)

        # 4. Strobe Trains (Xenon/LED pulse bursts)
        if active_phase.strobe_active and active_phase.strobe_freq_hz > 0:
            period = 1.0 / active_phase.strobe_freq_hz
            phase_in_period = (t_sec - active_phase.start_sec) % period
            duty_cycle = 0.25  # 25% on-time per pulse
            if phase_in_period < (period * duty_cycle):
                # Flash frame: Blinding pulse in ceiling and stage, moderate in crowd
                frame[self._mask_ceiling] = 255.0
                frame[self._mask_stage_center] = 252.0
                frame[self._mask_stage_flanks] = 248.0
                frame[self._mask_crowd] = np.clip(frame[self._mask_crowd] + 160.0, 0.0, 255.0)
            else:
                # Dark frame between pulses
                frame[self._mask_ceiling] = 12.0
                frame[self._mask_stage_center] = 15.0
                frame[self._mask_stage_flanks] = 10.0
                frame[self._mask_crowd] = 5.0

        # 5. Laser Beams & Fan Arrays
        if active_phase.laser_active:
            self._render_laser_beams(
                frame,
                t_sec,
                intensity=active_phase.laser_intensity,
                beam_count=active_phase.laser_beam_count,
            )

        # 6. Sensor noise & subtle crowd phone dots
        if active_phase.noise_sigma > 0:
            noise = self._rng.normal(0.0, active_phase.noise_sigma, (self.height, self.width)).astype(np.float32)
            frame += noise

        # Add phone screen dots in crowd (realistic EDM audience)
        if not active_phase.pyro_active and active_phase.base_luma > 3.0:
            dot_count = 6
            for d in range(dot_count):
                px = int((self.width * 0.1) + ((d * 27 + int(t_sec * 3)) % int(self.width * 0.8)))
                py = int(self.y_stage_bot + 4 + (d * 7) % (self.height - self.y_stage_bot - 8))
                if 0 <= py < self.height and 0 <= px < self.width:
                    frame[py, px] = min(255.0, frame[py, px] + 80.0)

        # Clamp and cast to uint8
        return np.clip(frame, 0.0, 255.0).astype(np.uint8)

    def render_rgb_frame(
        self,
        scenario: Union[ConcertScenario, str],
        t_sec: float,
        frame_idx: int = 0,
    ) -> np.ndarray:
        """
        Renders a 3D RGB frame (H, W, 3) uint8 with authentic concert color palette:
        - Deep Cyan & Electric Blue LED backdrops
        - High-energy 532nm Green and 445nm Blue lasers
        - Warm Xenon white strobes and Amber/Gold pyro washes
        """
        luma = self.render_luma_frame(scenario, t_sec, frame_idx)
        rgb = np.zeros((self.height, self.width, 3), dtype=np.float32)

        luma_f = luma.astype(np.float32)

        # Highlight blend weight (>= 180 transitions to true full white at 245+)
        highlight_weight = np.clip((luma_f - 180.0) / 65.0, 0.0, 1.0)

        r_base = luma_f * 0.85
        g_base = luma_f * 0.95
        b_base = luma_f * 1.10

        rgb[:, :, 0] = (1.0 - highlight_weight) * r_base + highlight_weight * luma_f
        rgb[:, :, 1] = (1.0 - highlight_weight) * g_base + highlight_weight * luma_f
        rgb[:, :, 2] = (1.0 - highlight_weight) * b_base + highlight_weight * luma_f

        # High saturated pixels
        laser_mask = (luma >= 245)
        rgb[laser_mask, 0] = 255.0
        rgb[laser_mask, 1] = 255.0
        rgb[laser_mask, 2] = 255.0

        return np.clip(rgb, 0.0, 255.0).astype(np.uint8)

    def render_frame(
        self,
        scenario: Union[ConcertScenario, str],
        t_sec: float,
        frame_idx: int = 0,
        as_rgb: bool = True,
    ) -> np.ndarray:
        """Renders either RGB (H, W, 3) or Grayscale (H, W) uint8 frame."""
        if as_rgb:
            return self.render_rgb_frame(scenario, t_sec, frame_idx)
        return self.render_luma_frame(scenario, t_sec, frame_idx)

    def generate_scenario_frames(
        self,
        scenario: Union[ConcertScenario, str],
        duration_sec: Optional[float] = None,
        as_rgb: bool = True,
    ) -> List[Tuple[np.ndarray, int]]:
        """
        Generates all frames for a full scenario timeline.
        Returns a list of tuples: (frame_ndarray, timestamp_ns).
        """
        scenario_key = ConcertScenario(scenario) if isinstance(scenario, str) else scenario
        phases = self.get_scenario_timeline(scenario_key)

        total_duration = duration_sec or (phases[-1].end_sec if phases else 5.0)
        total_frames = int(round(total_duration * self.fps))

        dt_ns = int(round((1.0 / self.fps) * 1e9))
        frames: List[Tuple[np.ndarray, int]] = []

        start_time_ns = 1_000_000_000  # Start at 1.0s timestamp base

        for idx in range(total_frames):
            t_sec = idx / self.fps
            timestamp_ns = start_time_ns + idx * dt_ns
            frame = self.render_frame(scenario_key, t_sec, frame_idx=idx, as_rgb=as_rgb)
            frames.append((frame, timestamp_ns))

        return frames

    def stream_scenario(
        self,
        scenario: Union[ConcertScenario, str],
        duration_sec: Optional[float] = None,
        as_rgb: bool = True,
        real_time: bool = False,
    ) -> Iterator[Tuple[np.ndarray, int]]:
        """
        Streams frames one by one as a generator. If real_time=True, sleeps for 1/fps.
        """
        scenario_key = ConcertScenario(scenario) if isinstance(scenario, str) else scenario
        phases = self.get_scenario_timeline(scenario_key)
        total_duration = duration_sec or (phases[-1].end_sec if phases else 5.0)
        total_frames = int(round(total_duration * self.fps))
        dt_ns = int(round((1.0 / self.fps) * 1e9))
        start_time_ns = time.perf_counter_ns()

        for idx in range(total_frames):
            t_sec = idx / self.fps
            timestamp_ns = start_time_ns + idx * dt_ns
            frame = self.render_frame(scenario_key, t_sec, frame_idx=idx, as_rgb=as_rgb)
            yield frame, timestamp_ns
            if real_time:
                time.sleep(1.0 / self.fps)

    @classmethod
    def get_scenario_timeline(cls, scenario: ConcertScenario) -> List[ScenarioPhase]:
        """Returns the discrete lighting phases for the given scenario."""
        if scenario == ConcertScenario.SCENARIO_A_BLACKOUT_DROP:
            return [
                # 0.0s - 1.5s: Balanced club baseline (Y ~ 45-55)
                ScenarioPhase("Baseline Ambient", 0.0, 1.5, base_luma=45.0, stage_boost=25.0, crowd_luma=15.0),
                # 1.5s - 3.5s: Pitch-black pre-drop blackout (Y < 4, C_dark > 0.95)
                ScenarioPhase("Pre-Drop Blackout", 1.5, 3.5, base_luma=2.0, ceiling_boost=0.0, stage_boost=1.0, crowd_luma=1.0),
                # 3.5s - 5.5s: Bass Drop Ignition with Laser Barrage (P99=255)
                ScenarioPhase(
                    "Bass Drop Lasers",
                    3.5,
                    5.5,
                    base_luma=80.0,
                    ceiling_boost=60.0,
                    stage_boost=70.0,
                    laser_active=True,
                    laser_intensity=255.0,
                    laser_beam_count=6,
                ),
                # 5.5s - 7.0s: Mainstage Drop Visuals
                ScenarioPhase("Mainstage Visuals", 5.5, 7.0, base_luma=70.0, stage_boost=40.0, crowd_luma=20.0),
            ]

        elif scenario == ConcertScenario.SCENARIO_B_LASER_ASSAULT:
            return [
                # 0.0s - 1.0s: Dark stage baseline (Y ~ 30)
                ScenarioPhase("Dark Club Baseline", 0.0, 1.0, base_luma=30.0, stage_boost=15.0, crowd_luma=10.0),
                # 1.0s - 4.0s: High intensity laser beam spikes (P99=255, localized ceiling/stage)
                ScenarioPhase(
                    "Laser Assault",
                    1.0,
                    4.0,
                    base_luma=40.0,
                    ceiling_boost=120.0,
                    stage_boost=50.0,
                    crowd_luma=12.0,
                    laser_active=True,
                    laser_intensity=255.0,
                    laser_beam_count=8,
                ),
                # 4.0s - 5.5s: Return to balanced stage
                ScenarioPhase("Balanced Stage Return", 4.0, 5.5, base_luma=50.0, stage_boost=25.0, crowd_luma=18.0),
            ]

        elif scenario == ConcertScenario.SCENARIO_C_STROBE_TRAIN:
            return [
                # 0.0s - 1.0s: Baseline club ambient
                ScenarioPhase("Pre-Strobe Baseline", 0.0, 1.0, base_luma=50.0, stage_boost=20.0, crowd_luma=15.0),
                # 1.0s - 4.0s: 14 Hz High-Energy Strobe Burst Train
                ScenarioPhase(
                    "14Hz Strobe Train",
                    1.0,
                    4.0,
                    base_luma=50.0,
                    strobe_active=True,
                    strobe_freq_hz=14.0,
                ),
                # 4.0s - 5.5s: Post-strobe cooldown
                ScenarioPhase("Post-Strobe Cooldown", 4.0, 5.5, base_luma=50.0, stage_boost=20.0, crowd_luma=15.0),
            ]

        elif scenario == ConcertScenario.SCENARIO_D_PYRO_FLOOD:
            return [
                # 0.0s - 1.0s: Baseline stage
                ScenarioPhase("Pre-Pyro Stage", 0.0, 1.0, base_luma=45.0, stage_boost=20.0, crowd_luma=15.0),
                # 1.0s - 3.0s: Full Arena Pyro Floodlight Wash (Y >= 210, C_high >= 0.50)
                ScenarioPhase("Pyro Flood Wash", 1.0, 3.0, base_luma=220.0, pyro_active=True),
                # 3.0s - 5.0s: Gradual Cooldown Wash
                ScenarioPhase("Cooldown Wash", 3.0, 5.0, base_luma=55.0, stage_boost=30.0, crowd_luma=20.0),
            ]

        elif scenario == ConcertScenario.SCENARIO_E_FULL_CONCERT_SET:
            return [
                # 0.0s - 2.0s: Warmup & Club Ambient
                ScenarioPhase("Warmup Ambient", 0.0, 2.0, base_luma=45.0, stage_boost=20.0, crowd_luma=15.0),
                # 2.0s - 3.5s: Breakdown & Tension Build (Lights Dimming)
                ScenarioPhase("Breakdown Build", 2.0, 3.5, base_luma=20.0, stage_boost=10.0, crowd_luma=8.0),
                # 3.5s - 5.5s: Pitch-Black Pre-Drop Silence (Y < 4)
                ScenarioPhase("Pre-Drop Blackout", 3.5, 5.5, base_luma=2.5, stage_boost=1.0, crowd_luma=1.0),
                # 5.5s - 7.5s: Bass Drop Hit with Laser Cones (P99=255)
                ScenarioPhase(
                    "Drop Laser Barrage",
                    5.5,
                    7.5,
                    base_luma=70.0,
                    ceiling_boost=80.0,
                    stage_boost=60.0,
                    laser_active=True,
                    laser_intensity=255.0,
                    laser_beam_count=6,
                ),
                # 7.5s - 10.0s: 14Hz Climax Strobe Train
                ScenarioPhase(
                    "Climax Strobe Train",
                    7.5,
                    10.0,
                    base_luma=50.0,
                    strobe_active=True,
                    strobe_freq_hz=14.0,
                ),
                # 10.0s - 12.0s: Full Stage Pyro Flood Wash
                ScenarioPhase("Pyro Flood Wash", 10.0, 12.0, base_luma=220.0, pyro_active=True),
                # 12.0s - 15.0s: Mainstage Stable Visuals
                ScenarioPhase("Mainstage Stable", 12.0, 15.0, base_luma=65.0, stage_boost=35.0, crowd_luma=20.0),
            ]

        # Default fallback
        return [ScenarioPhase("Default Steady", 0.0, 10.0, base_luma=50.0)]


# Functional convenience helpers
def generate_scenario_frames(
    scenario: Union[ConcertScenario, str],
    fps: float = 60.0,
    duration_sec: Optional[float] = None,
    as_rgb: bool = True,
    seed: Optional[int] = 42,
) -> List[Tuple[np.ndarray, int]]:
    """Generates frames for any named concert scenario."""
    simulator = ConcertLightSimulator(fps=fps, seed=seed)
    return simulator.generate_scenario_frames(scenario, duration_sec=duration_sec, as_rgb=as_rgb)


def generate_blackout_drop_scenario(fps: float = 60.0, as_rgb: bool = True) -> List[Tuple[np.ndarray, int]]:
    """Helper to generate Scenario A (Blackout Drop)."""
    return generate_scenario_frames(ConcertScenario.SCENARIO_A_BLACKOUT_DROP, fps=fps, as_rgb=as_rgb)


def generate_laser_assault_scenario(fps: float = 60.0, as_rgb: bool = True) -> List[Tuple[np.ndarray, int]]:
    """Helper to generate Scenario B (Laser Assault)."""
    return generate_scenario_frames(ConcertScenario.SCENARIO_B_LASER_ASSAULT, fps=fps, as_rgb=as_rgb)


def generate_strobe_train_scenario(fps: float = 60.0, as_rgb: bool = True) -> List[Tuple[np.ndarray, int]]:
    """Helper to generate Scenario C (Strobe Train)."""
    return generate_scenario_frames(ConcertScenario.SCENARIO_C_STROBE_TRAIN, fps=fps, as_rgb=as_rgb)


def generate_pyro_flood_scenario(fps: float = 60.0, as_rgb: bool = True) -> List[Tuple[np.ndarray, int]]:
    """Helper to generate Scenario D (Pyro Flood)."""
    return generate_scenario_frames(ConcertScenario.SCENARIO_D_PYRO_FLOOD, fps=fps, as_rgb=as_rgb)


def generate_full_concert_set_scenario(fps: float = 60.0, as_rgb: bool = True) -> List[Tuple[np.ndarray, int]]:
    """Helper to generate Scenario E (Full Concert Set)."""
    return generate_scenario_frames(ConcertScenario.SCENARIO_E_FULL_CONCERT_SET, fps=fps, as_rgb=as_rgb)
