"""
Configuration models and parameters for S26 AI Camera Controller light detection.
"""
from pydantic import BaseModel, Field


class ZoneROI(BaseModel):
    name: str
    y_min: float = Field(default=0.0, ge=0.0, le=1.0)
    y_max: float = Field(default=1.0, ge=0.0, le=1.0)
    x_min: float = Field(default=0.0, ge=0.0, le=1.0)
    x_max: float = Field(default=1.0, ge=0.0, le=1.0)


class DetectorConfig(BaseModel):
    target_width: int = Field(default=160, gt=0)
    target_height: int = Field(default=90, gt=0)
    c_high_threshold: int = Field(default=245, ge=0, le=255)
    c_dark_threshold: int = Field(default=10, ge=0, le=255)
    fps: float = Field(default=60.0, gt=0.0)
    history_size: int = Field(default=64, ge=8)

    # 4-Zone Spatial ROI relative boundary ratios
    ceiling_y_ratio: float = Field(default=0.30, ge=0.0, le=1.0)
    stage_y_top_ratio: float = Field(default=0.30, ge=0.0, le=1.0)
    stage_y_bot_ratio: float = Field(default=0.70, ge=0.0, le=1.0)
    stage_x_left_ratio: float = Field(default=0.20, ge=0.0, le=1.0)
    stage_x_right_ratio: float = Field(default=0.80, ge=0.0, le=1.0)
    crowd_y_ratio: float = Field(default=0.70, ge=0.0, le=1.0)

    zero_network_enforced: bool = True
