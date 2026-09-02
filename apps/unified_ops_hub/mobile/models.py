"""Data models for Android CLI Mobile Automation & Viral Trend Scraping.
Pydantic-based schemas for scraped items, device lifecycle states, sessions, and telemetry metrics.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field, model_validator


class ScrapedTrendItem(BaseModel):
    """Structured viral trend item extracted from mobile UI trees."""
    item_id: str = Field(default_factory=lambda: f"trend_{uuid.uuid4().hex[:10]}")
    platform: str = "generic"
    topic: Optional[str] = None
    caption: str = ""
    hashtags: List[str] = Field(default_factory=list)
    sound_title: Optional[str] = None
    sound_url: Optional[str] = None
    author_handle: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    post_age_hours: float = 1.0
    velocity_score: float = 0.0
    scraped_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_bounds: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def compute_velocity(self) -> "ScrapedTrendItem":
        """Calculates viral velocity score: (Likes*10 + Comments*50 + Shares*100) / PostAgeHours."""
        if self.velocity_score == 0.0 and (self.like_count or self.comment_count or self.share_count):
            age = max(self.post_age_hours, 0.1)
            raw_velocity = (
                self.like_count * 10.0
                + self.comment_count * 50.0
                + self.share_count * 100.0
            ) / age
            self.velocity_score = round(raw_velocity, 2)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Serializes model to JSON dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScrapedTrendItem":
        """Reconstitutes model from dictionary."""
        return cls(**data)


class DeviceState(BaseModel):
    """Hardware and connection state for an attached or virtual Android device."""
    serial: str
    status: str = "device"  # "device", "offline", "unauthorized", "disconnected"
    model: Optional[str] = None
    product: Optional[str] = None
    screen_width: int = 1080
    screen_height: int = 2400
    samsung_auto_blocker_disabled: bool = False
    is_emulator: bool = False
    foreground_package: Optional[str] = None
    battery_level: Optional[int] = None

    def is_ready(self) -> bool:
        """Returns True if the device is attached, online, and authorized."""
        return self.status == "device"


class MobileScrapeSession(BaseModel):
    """Lifecycle and progress record for an autonomous mobile scraping session."""
    session_id: str = Field(default_factory=lambda: f"session_{uuid.uuid4().hex[:8]}")
    platform: str = "generic"
    target_query_or_url: str = ""
    start_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = None
    items_scraped: int = 0
    items_quarantined: int = 0
    status: str = "INITIATED"  # "INITIATED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"
    errors: List[str] = Field(default_factory=list)


class ScrapeMetrics(BaseModel):
    """Aggregated telemetry and yield metrics from a scraping execution."""
    session_id: str
    duration_seconds: float = 0.0
    total_frames_dumped: int = 0
    successful_parses: int = 0
    failed_parses: int = 0
    average_frame_latency_ms: float = 0.0
    top_hashtags: List[Tuple[str, int]] = Field(default_factory=list)
    top_sounds: List[Tuple[str, int]] = Field(default_factory=list)

    @property
    def yield_rate(self) -> float:
        """Proportion of dumped frames that yielded valid trend items."""
        total = max(1, self.total_frames_dumped)
        return round(self.successful_parses / total, 3)

    @property
    def failure_rate(self) -> float:
        """Proportion of frames that failed to parse."""
        total = max(1, self.total_frames_dumped)
        return round(self.failed_parses / total, 3)
