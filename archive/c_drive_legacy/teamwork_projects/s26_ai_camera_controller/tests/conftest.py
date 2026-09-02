"""
Pytest fixtures for offline light detection and synthetic concert lighting generation.
"""
import pytest
import numpy as np


@pytest.fixture
def blackout_frame_rgb():
    """Generates a pitch-black frame (90x160x3) representing pre-drop tension."""
    return np.zeros((90, 160, 3), dtype=np.uint8)


@pytest.fixture
def uniform_gray_frame_rgb():
    """Generates a uniform middle gray frame (90x160x3) with RGB (128, 128, 128)."""
    return np.full((90, 160, 3), 128, dtype=np.uint8)


@pytest.fixture
def laser_spot_frame_rgb():
    """
    Generates a dark club scene with intense collimated laser beams in the ceiling zone.
    Ceiling zone contains high saturation beams (255), while crowd is dark (5).
    """
    frame = np.full((90, 160, 3), 5, dtype=np.uint8)
    # Intense laser line in ceiling (rows 5 to 15, cols 20 to 140)
    frame[5:15, 20:140] = 255
    return frame


@pytest.fixture
def floodlight_frame_rgb():
    """Generates a full arena pyro/floodlight washout scene with high saturation across all zones."""
    return np.full((90, 160, 3), 250, dtype=np.uint8)


@pytest.fixture
def vertical_gradient_frame_rgb():
    """Generates a smooth vertical gradient from top (255) to bottom (0)."""
    h, w = 90, 160
    grad_1d = np.linspace(255, 0, h, dtype=np.uint8)
    grad_2d = np.repeat(grad_1d[:, np.newaxis], w, axis=1)
    return np.stack([grad_2d, grad_2d, grad_2d], axis=2)


@pytest.fixture
def stage_spotlight_frame_rgb():
    """
    Generates an artist spotlight scene: dark ceiling and crowd, bright stage center.
    """
    frame = np.full((90, 160, 3), 10, dtype=np.uint8)
    # Stage center (y: 27 to 63, x: 32 to 128) set to high luminance
    frame[27:63, 32:128] = 220
    return frame
