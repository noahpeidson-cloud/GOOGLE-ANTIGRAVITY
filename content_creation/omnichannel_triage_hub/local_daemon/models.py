"""
Pydantic schemas and models for the FastAPI Local Daemon Bridge.
Strict adherence to Rule R16 (Absolute imports only).
"""

from typing import List, Optional, Literal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, model_validator


class PulledFileInfo(BaseModel):
    """Information about a single pulled or simulated media file."""
    filename: str = Field(..., description="File name")
    local_path: str = Field(..., description="Absolute or relative local file path")
    size_bytes: int = Field(..., description="Size of file in bytes")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of transfer"
    )
    is_mock: bool = Field(default=False, description="Whether file was procedurally generated")


class AdbPullRequest(BaseModel):
    """Request payload for triggering an ADB pull operation."""
    device_id: Optional[str] = Field(default=None, description="Optional target device serial")
    source_path: Optional[str] = Field(default=None, description="Source path on Android device")
    device_path: Optional[str] = Field(default=None, description="Alias for source_path")
    destination_path: Optional[str] = Field(default=None, description="Local destination directory")
    local_dest: Optional[str] = Field(default=None, description="Alias for destination_path")
    file_pattern: str = Field(default="*.mp4", description="File pattern glob (e.g. *.mp4)")
    limit: int = Field(default=10, ge=1, le=100, description="Max files to pull")
    mock: bool = Field(default=False, description="Force simulated mock pull")
    run_in_background: bool = Field(default=False, description="Execute in background task")

    @property
    def resolved_source_path(self) -> str:
        """Returns resolved source path from source_path or device_path, with default."""
        return self.source_path or self.device_path or "/sdcard/DCIM/Camera"

    @property
    def resolved_destination_path(self) -> str:
        """Returns resolved destination path from destination_path or local_dest, with default."""
        return self.destination_path or self.local_dest or "./staging/videos"


class AdbPullResponse(BaseModel):
    """Response payload for ADB pull operation."""
    success: bool = Field(default=True, description="Whether operation succeeded")
    status: Literal["success", "mock_success", "error", "in_progress"] = Field(
        default="success", description="Status code"
    )
    message: str = Field(default="ADB pull completed successfully", description="Status message")
    device_id: Optional[str] = Field(default=None, description="Device serial used")
    bytes_transferred: int = Field(default=0, description="Bytes transferred in this operation")
    total_bytes: int = Field(default=0, description="Total storage bytes or batch total bytes")
    file_path: Optional[str] = Field(default=None, description="Primary or first pulled file path")
    pulled_files: List[PulledFileInfo] = Field(default_factory=list, description="List of pulled files")
    total_count: int = Field(default=0, description="Total count of pulled files")
    duration_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    duration_seconds: float = Field(default=0.0, description="Execution duration in seconds")
    task_id: Optional[str] = Field(default=None, description="Background task identifier")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class CaptureScreenRequest(BaseModel):
    """Request payload for capturing screen from Android device or mock."""
    device_id: Optional[str] = Field(default=None, description="Optional target device serial")
    format: str = Field(default="png", description="Image format: png, jpeg, base64, file, both")
    mock: bool = Field(default=False, description="Force mock procedural screenshot")
    save_dir: Optional[str] = Field(default="./staging/screenshots", description="Directory to save image")
    save_to_file: bool = Field(default=False, description="Whether to write image file to disk")


class CaptureScreenResponse(BaseModel):
    """Response payload for screen capture operation."""
    success: bool = Field(default=True, description="Whether operation succeeded")
    status: Literal["success", "mock_success", "error"] = Field(
        default="success", description="Status string"
    )
    message: str = Field(default="Screen captured successfully", description="Status message")
    image_base64: Optional[str] = Field(
        default=None, description="Base64 Data URI (e.g. data:image/png;base64,...)"
    )
    raw_base64: Optional[str] = Field(
        default=None, description="Raw Base64 string without data URI prefix"
    )
    file_path: Optional[str] = Field(default=None, description="Local file path if saved")
    width: int = Field(default=540, description="Image width in pixels")
    height: int = Field(default=960, description="Image height in pixels")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of capture"
    )
    device_id: Optional[str] = Field(default=None, description="Device serial used")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class DeviceInfo(BaseModel):
    """Information on an attached Android device."""
    serial: str = Field(..., description="Device serial number")
    state: str = Field(default="device", description="Device state (e.g. device, unauthorized, offline)")
    model: Optional[str] = Field(default=None, description="Device model if available")
    product: Optional[str] = Field(default=None, description="Product code if available")


class DevicesResponse(BaseModel):
    """List of connected Android devices."""
    devices: List[DeviceInfo] = Field(default_factory=list, description="Connected device list")
    count: int = Field(default=0, description="Number of connected devices")


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(default="ok", description="Daemon status")
    adb_connected: bool = Field(default=False, description="Whether at least one ADB device is online")
    device_count: int = Field(default=0, description="Count of active devices")
    devices: List[str] = Field(default_factory=list, description="List of connected device serials")
    adb_version: Optional[str] = Field(default=None, description="Detected ADB version")
    mock_available: bool = Field(default=True, description="Whether mock fallback engine is active")
    uptime_seconds: float = Field(default=0.0, description="Daemon uptime in seconds")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Current server ISO timestamp"
    )


class StagingFile(BaseModel):
    """Metadata for a file stored in staging."""
    filename: str = Field(..., description="File name")
    path: str = Field(..., description="File path")
    size_bytes: int = Field(..., description="File size in bytes")
    modified_at: str = Field(..., description="Last modified ISO timestamp")
    media_type: str = Field(..., description="MIME media type or extension")


class StagingInventoryResponse(BaseModel):
    """Inventory of staged files."""
    files: List[StagingFile] = Field(default_factory=list, description="Staged files")
    total_size_bytes: int = Field(default=0, description="Total size in bytes")
    count: int = Field(default=0, description="Total number of files")
