"""
coordinates.py - Samsung Galaxy S26 Ultra Pro Video Coordinate Mapping Engine

Provides resolution-independent normalized touch coordinate models, resolution scalers
(WQHD+, FHD+, Custom), and tap sequence generators for Samsung Pro Video controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union


class DisplayResolution(str, Enum):
    """Supported display resolutions for Samsung Galaxy S26 Ultra."""
    WQHD_PLUS_LANDSCAPE = "WQHD_PLUS_LANDSCAPE"  # 3120 x 1440
    FHD_PLUS_LANDSCAPE = "FHD_PLUS_LANDSCAPE"    # 2340 x 1080
    WQHD_PLUS_PORTRAIT = "WQHD_PLUS_PORTRAIT"    # 1440 x 3120
    FHD_PLUS_PORTRAIT = "FHD_PLUS_PORTRAIT"      # 1080 x 2340
    CUSTOM = "CUSTOM"


class CameraParameter(str, Enum):
    """Pro Video parameter buttons available on the toolbar ribbon."""
    ISO = "ISO"
    SHUTTER_SPEED = "SPEED"
    EV = "EV"
    FOCUS = "FOCUS"
    WHITE_BALANCE = "WB"
    MIC_GAIN = "MIC"
    LENS = "LENS"


# Alias for readability
RibbonButton = CameraParameter


@dataclass(frozen=True)
class DisplayProfile:
    """Display geometry and orientation configuration."""
    width: int
    height: int
    resolution_type: DisplayResolution = DisplayResolution.WQHD_PLUS_LANDSCAPE
    is_landscape: bool = True

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"Display dimensions must be positive, got {self.width}x{self.height}")

    @classmethod
    def get_default_s26_ultra_wqhd(cls, is_landscape: bool = True) -> DisplayProfile:
        """S26 Ultra native WQHD+ profile (3120x1440 landscape or 1440x3120 portrait)."""
        if is_landscape:
            return cls(
                width=3120,
                height=1440,
                resolution_type=DisplayResolution.WQHD_PLUS_LANDSCAPE,
                is_landscape=True,
            )
        return cls(
            width=1440,
            height=3120,
            resolution_type=DisplayResolution.WQHD_PLUS_PORTRAIT,
            is_landscape=False,
        )

    @classmethod
    def get_default_s26_ultra_fhd(cls, is_landscape: bool = True) -> DisplayProfile:
        """S26 Ultra standard FHD+ profile (2340x1080 landscape or 1080x2340 portrait)."""
        if is_landscape:
            return cls(
                width=2340,
                height=1080,
                resolution_type=DisplayResolution.FHD_PLUS_LANDSCAPE,
                is_landscape=True,
            )
        return cls(
            width=1080,
            height=2340,
            resolution_type=DisplayResolution.FHD_PLUS_PORTRAIT,
            is_landscape=False,
        )

    @classmethod
    def from_resolution(cls, width: int, height: int) -> DisplayProfile:
        """Automatically resolve profile from arbitrary dimensions."""
        if width <= 0 or height <= 0:
            raise ValueError(f"Width and height must be positive integers, got ({width}, {height})")

        is_landscape = width >= height
        if (width, height) == (3120, 1440):
            res_type = DisplayResolution.WQHD_PLUS_LANDSCAPE
        elif (width, height) == (2340, 1080):
            res_type = DisplayResolution.FHD_PLUS_LANDSCAPE
        elif (width, height) == (1440, 3120):
            res_type = DisplayResolution.WQHD_PLUS_PORTRAIT
        elif (width, height) == (1080, 2340):
            res_type = DisplayResolution.FHD_PLUS_PORTRAIT
        else:
            res_type = DisplayResolution.CUSTOM

        return cls(
            width=width,
            height=height,
            resolution_type=res_type,
            is_landscape=is_landscape,
        )


@dataclass(frozen=True)
class TapAction:
    """Represents a single screen touch event."""
    x_px: int
    y_px: int
    norm_x: float = 0.0
    norm_y: float = 0.0
    delay_after_ms: int = 35
    description: str = ""

    def __post_init__(self):
        if self.x_px < 0 or self.y_px < 0:
            raise ValueError(f"Screen coordinates must be non-negative, got ({self.x_px}, {self.y_px})")
        if self.delay_after_ms < 0:
            raise ValueError(f"Delay must be non-negative, got {self.delay_after_ms}")


class SamsungS26CoordinateMap:
    """
    Normalized coordinate definitions [0.0, 1.0] for Samsung Galaxy S26 Ultra Pro Video mode.
    Top-Left is (0.0, 0.0), Bottom-Right is (1.0, 1.0).
    """

    # Pro Toolbar parameter buttons across ribbon (Landscape Y_norm = 0.880)
    RIBBON_BUTTONS: Dict[CameraParameter, Tuple[float, float]] = {
        CameraParameter.ISO: (0.220, 0.880),
        CameraParameter.SHUTTER_SPEED: (0.340, 0.880),
        CameraParameter.EV: (0.460, 0.880),
        CameraParameter.FOCUS: (0.580, 0.880),
        CameraParameter.WHITE_BALANCE: (0.700, 0.880),
        CameraParameter.MIC_GAIN: (0.820, 0.880),
        CameraParameter.LENS: (0.900, 0.880),
    }

    # ISO Slider discrete values (Landscape Y_norm = 0.720)
    ISO_SLIDER_TICKS: Dict[str, Tuple[float, float]] = {
        "AUTO": (0.150, 0.720),
        "50": (0.210, 0.720),
        "100": (0.280, 0.720),
        "200": (0.380, 0.720),
        "250": (0.420, 0.720),
        "400": (0.500, 0.720),
        "640": (0.580, 0.720),
        "800": (0.650, 0.720),
        "1600": (0.780, 0.720),
        "3200": (0.850, 0.720),
    }

    # Shutter Speed Slider discrete values (Landscape Y_norm = 0.720)
    SHUTTER_SLIDER_TICKS: Dict[str, Tuple[float, float]] = {
        "AUTO": (0.150, 0.720),
        "1/30": (0.250, 0.720),
        "1/60": (0.350, 0.720),
        "1/120": (0.500, 0.720),
        "1/125": (0.500, 0.720),  # Alias for 1/120
        "1/240": (0.650, 0.720),
        "1/250": (0.650, 0.720),  # Alias for 1/240
        "1/500": (0.780, 0.720),
        "1/1000": (0.850, 0.720),
        "1/2000": (0.900, 0.720),
        "1/4000": (0.940, 0.720),
        "1/12000": (0.980, 0.720),
    }

    # EV Slider discrete ticks
    EV_SLIDER_TICKS: Dict[str, Tuple[float, float]] = {
        "-2.0": (0.200, 0.720),
        "-1.0": (0.350, 0.720),
        "0.0": (0.500, 0.720),
        "+1.0": (0.650, 0.720),
        "+2.0": (0.800, 0.720),
    }

    # White Balance Slider discrete ticks
    WB_SLIDER_TICKS: Dict[str, Tuple[float, float]] = {
        "AUTO": (0.150, 0.720),
        "2300K": (0.250, 0.720),
        "3200K": (0.380, 0.720),
        "4000K": (0.500, 0.720),
        "5500K": (0.650, 0.720),
        "6500K": (0.780, 0.720),
        "10000K": (0.880, 0.720),
    }

    # Focus Slider discrete ticks
    FOCUS_SLIDER_TICKS: Dict[str, Tuple[float, float]] = {
        "AUTO": (0.150, 0.720),
        "MACRO": (0.300, 0.720),
        "MID": (0.550, 0.720),
        "INFINITY": (0.850, 0.720),
    }


class CoordinateNormalizer:
    """
    Transforms normalized [0.0, 1.0] coordinates to physical device pixels
    and synthesizes multi-step touch tap sequences for Pro Video UI controls.
    """

    def __init__(self, display_profile: Optional[DisplayProfile] = None):
        self.profile = display_profile or DisplayProfile.get_default_s26_ultra_wqhd()

    @property
    def width(self) -> int:
        return self.profile.width

    @property
    def height(self) -> int:
        return self.profile.height

    def to_screen_pixels(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """
        Converts normalized (norm_x, norm_y) [0.0, 1.0] to physical integer pixel coordinates (px_x, px_y),
        clamped strictly to screen boundaries [0, width-1] and [0, height-1].
        """
        if not (0.0 <= norm_x <= 1.0 and 0.0 <= norm_y <= 1.0):
            # Clamping normalized input into valid range
            norm_x = max(0.0, min(1.0, float(norm_x)))
            norm_y = max(0.0, min(1.0, float(norm_y)))

        px_x = int(round(norm_x * self.profile.width))
        px_y = int(round(norm_y * self.profile.height))

        # Clamp to physical screen dimensions
        px_x = max(0, min(self.profile.width - 1, px_x))
        px_y = max(0, min(self.profile.height - 1, px_y))
        return px_x, px_y

    def to_normalized(self, px_x: int, px_y: int) -> Tuple[float, float]:
        """Converts screen pixel coordinates back to normalized [0.0, 1.0] space."""
        norm_x = max(0.0, min(1.0, px_x / max(1, self.profile.width)))
        norm_y = max(0.0, min(1.0, px_y / max(1, self.profile.height)))
        return round(norm_x, 6), round(norm_y, 6)

    def scale_point(self, norm_x: float, norm_y: float, target_width: int, target_height: int) -> Tuple[int, int]:
        """Scales a normalized point directly to target resolution dimensions."""
        if target_width <= 0 or target_height <= 0:
            raise ValueError(f"Target dimensions must be positive, got ({target_width}, {target_height})")
        clamped_x = max(0.0, min(1.0, float(norm_x)))
        clamped_y = max(0.0, min(1.0, float(norm_y)))
        px_x = int(round(clamped_x * target_width))
        px_y = int(round(clamped_y * target_height))
        px_x = max(0, min(target_width - 1, px_x))
        px_y = max(0, min(target_height - 1, px_y))
        return px_x, px_y

    @staticmethod
    def _normalize_parameter_key(param: Union[CameraParameter, str]) -> CameraParameter:
        """Resolves various string representations to canonical CameraParameter enum."""
        if isinstance(param, CameraParameter):
            return param

        clean = str(param).strip().upper().replace("BTN_", "").replace(" ", "_")
        aliases = {
            "ISO": CameraParameter.ISO,
            "SPEED": CameraParameter.SHUTTER_SPEED,
            "SHUTTER": CameraParameter.SHUTTER_SPEED,
            "SHUTTER_SPEED": CameraParameter.SHUTTER_SPEED,
            "EV": CameraParameter.EV,
            "EXPOSURE": CameraParameter.EV,
            "FOCUS": CameraParameter.FOCUS,
            "WB": CameraParameter.WHITE_BALANCE,
            "WHITE_BALANCE": CameraParameter.WHITE_BALANCE,
            "MIC": CameraParameter.MIC_GAIN,
            "MIC_GAIN": CameraParameter.MIC_GAIN,
            "LENS": CameraParameter.LENS,
        }
        if clean in aliases:
            return aliases[clean]
        raise ValueError(f"Unknown camera parameter: {param}")

    @staticmethod
    def _normalize_iso_key(iso: Union[int, str]) -> str:
        """Normalizes ISO input (e.g. 100, '100', 'ISO 100', 'iso100') to canonical key."""
        clean = str(iso).strip().upper().replace("ISO", "").replace(" ", "")
        if clean in SamsungS26CoordinateMap.ISO_SLIDER_TICKS:
            return clean
        if clean == "" or clean == "AUTO":
            return "AUTO"
        raise ValueError(
            f"Invalid ISO value: {iso}. Allowed values: {list(SamsungS26CoordinateMap.ISO_SLIDER_TICKS.keys())}"
        )

    @staticmethod
    def _normalize_shutter_key(shutter: Union[str, float, int]) -> str:
        """Normalizes Shutter Speed input (e.g. '1/60', '60', '1/120s', '1/250') to canonical key."""
        clean = str(shutter).strip().lower().replace("s", "").replace("sec", "").strip()
        
        # Direct lookup
        if clean in SamsungS26CoordinateMap.SHUTTER_SLIDER_TICKS:
            return clean
        if clean.upper() == "AUTO":
            return "AUTO"

        # Handle '1/60' vs '60' or other forms
        if not clean.startswith("1/"):
            with_prefix = f"1/{clean}"
            if with_prefix in SamsungS26CoordinateMap.SHUTTER_SLIDER_TICKS:
                return with_prefix

        # Match close common values
        if clean in ("1/125", "125"):
            return "1/120"
        if clean in ("1/250", "250"):
            return "1/240"

        raise ValueError(
            f"Invalid Shutter Speed: {shutter}. Allowed values: {list(SamsungS26CoordinateMap.SHUTTER_SLIDER_TICKS.keys())}"
        )

    def get_ribbon_button_normalized(self, button: Union[CameraParameter, str]) -> Tuple[float, float]:
        """Returns normalized (x, y) coordinates for a ribbon button."""
        param = self._normalize_parameter_key(button)
        return SamsungS26CoordinateMap.RIBBON_BUTTONS[param]

    def get_ribbon_button_pixels(self, button: Union[CameraParameter, str]) -> Tuple[int, int]:
        """Returns screen pixel (x, y) coordinates for a ribbon button."""
        norm_x, norm_y = self.get_ribbon_button_normalized(button)
        return self.to_screen_pixels(norm_x, norm_y)

    def get_iso_tick_normalized(self, iso: Union[int, str]) -> Tuple[float, float]:
        """Returns normalized (x, y) coordinates for an ISO slider tick."""
        key = self._normalize_iso_key(iso)
        return SamsungS26CoordinateMap.ISO_SLIDER_TICKS[key]

    def get_iso_tick_pixels(self, iso: Union[int, str]) -> Tuple[int, int]:
        """Returns screen pixel (x, y) coordinates for an ISO slider tick."""
        norm_x, norm_y = self.get_iso_tick_normalized(iso)
        return self.to_screen_pixels(norm_x, norm_y)

    def get_shutter_tick_normalized(self, shutter: Union[str, float, int]) -> Tuple[float, float]:
        """Returns normalized (x, y) coordinates for a Shutter Speed slider tick."""
        key = self._normalize_shutter_key(shutter)
        return SamsungS26CoordinateMap.SHUTTER_SLIDER_TICKS[key]

    def get_shutter_tick_pixels(self, shutter: Union[str, float, int]) -> Tuple[int, int]:
        """Returns screen pixel (x, y) coordinates for a Shutter Speed slider tick."""
        norm_x, norm_y = self.get_shutter_tick_normalized(shutter)
        return self.to_screen_pixels(norm_x, norm_y)

    def build_iso_sequence(
        self,
        target_iso: Union[int, str],
        delay_after_ribbon_ms: int = 35,
        delay_after_slider_ms: int = 10,
    ) -> List[TapAction]:
        """
        Builds a 2-step tap sequence:
        1. Tap ISO Ribbon button (expands slider)
        2. Wait delay_after_ribbon_ms
        3. Tap Target ISO tick position
        """
        btn_norm_x, btn_norm_y = self.get_ribbon_button_normalized(CameraParameter.ISO)
        btn_px_x, btn_px_y = self.to_screen_pixels(btn_norm_x, btn_norm_y)

        val_key = self._normalize_iso_key(target_iso)
        val_norm_x, val_norm_y = self.get_iso_tick_normalized(val_key)
        val_px_x, val_px_y = self.to_screen_pixels(val_norm_x, val_norm_y)

        return [
            TapAction(
                x_px=btn_px_x,
                y_px=btn_px_y,
                norm_x=btn_norm_x,
                norm_y=btn_norm_y,
                delay_after_ms=delay_after_ribbon_ms,
                description="Tap ISO Ribbon Button",
            ),
            TapAction(
                x_px=val_px_x,
                y_px=val_px_y,
                norm_x=val_norm_x,
                norm_y=val_norm_y,
                delay_after_ms=delay_after_slider_ms,
                description=f"Tap ISO {val_key} Slider Tick",
            ),
        ]

    def build_shutter_sequence(
        self,
        target_shutter: Union[str, float, int],
        delay_after_ribbon_ms: int = 35,
        delay_after_slider_ms: int = 10,
    ) -> List[TapAction]:
        """
        Builds a 2-step tap sequence:
        1. Tap Shutter Speed Ribbon button (expands slider)
        2. Wait delay_after_ribbon_ms
        3. Tap Target Shutter Speed tick position
        """
        btn_norm_x, btn_norm_y = self.get_ribbon_button_normalized(CameraParameter.SHUTTER_SPEED)
        btn_px_x, btn_px_y = self.to_screen_pixels(btn_norm_x, btn_norm_y)

        val_key = self._normalize_shutter_key(target_shutter)
        val_norm_x, val_norm_y = self.get_shutter_tick_normalized(val_key)
        val_px_x, val_px_y = self.to_screen_pixels(val_norm_x, val_norm_y)

        return [
            TapAction(
                x_px=btn_px_x,
                y_px=btn_px_y,
                norm_x=btn_norm_x,
                norm_y=btn_norm_y,
                delay_after_ms=delay_after_ribbon_ms,
                description="Tap Shutter Speed Ribbon Button",
            ),
            TapAction(
                x_px=val_px_x,
                y_px=val_px_y,
                norm_x=val_norm_x,
                norm_y=val_norm_y,
                delay_after_ms=delay_after_slider_ms,
                description=f"Tap Shutter {val_key} Slider Tick",
            ),
        ]

    def build_preset_sequence(
        self,
        iso: Optional[Union[int, str]] = None,
        shutter_speed: Optional[Union[str, float, int]] = None,
        delay_after_ribbon_ms: int = 35,
        delay_after_slider_ms: int = 10,
    ) -> List[TapAction]:
        """
        Builds combined tap sequence for full exposure preset adjustment.
        Dispatches ISO adjustment followed by Shutter speed adjustment (if specified).
        """
        actions: List[TapAction] = []
        if iso is not None:
            actions.extend(
                self.build_iso_sequence(
                    target_iso=iso,
                    delay_after_ribbon_ms=delay_after_ribbon_ms,
                    delay_after_slider_ms=delay_after_slider_ms,
                )
            )
        if shutter_speed is not None:
            actions.extend(
                self.build_shutter_sequence(
                    target_shutter=shutter_speed,
                    delay_after_ribbon_ms=delay_after_ribbon_ms,
                    delay_after_slider_ms=delay_after_slider_ms,
                )
            )
        return actions


# Resolution Scaler alias for backward compatibility and explicit scaling semantics
ResolutionScaler = CoordinateNormalizer
