"""
Simulation and synthetic concert lighting environment for S26 AI Camera Controller.
"""

from .light_simulator import (
    ConcertScenario,
    ScenarioType,
    ScenarioPhase,
    ConcertLightSimulator,
    generate_scenario_frames,
    generate_blackout_drop_scenario,
    generate_laser_assault_scenario,
    generate_strobe_train_scenario,
    generate_pyro_flood_scenario,
    generate_full_concert_set_scenario,
)
from .mock_device import (
    MockAndroidDevice,
    MockDeviceDispatcher,
    ProVideoCameraState,
    CapturedCommand,
)

__all__ = [
    "ConcertScenario",
    "ScenarioType",
    "ScenarioPhase",
    "ConcertLightSimulator",
    "generate_scenario_frames",
    "generate_blackout_drop_scenario",
    "generate_laser_assault_scenario",
    "generate_strobe_train_scenario",
    "generate_pyro_flood_scenario",
    "generate_full_concert_set_scenario",
    "MockAndroidDevice",
    "MockDeviceDispatcher",
    "ProVideoCameraState",
    "CapturedCommand",
]
