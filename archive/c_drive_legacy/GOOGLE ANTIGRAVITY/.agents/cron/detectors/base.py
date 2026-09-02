"""Abstract Base Detector interface."""

from abc import ABC, abstractmethod
from typing import List, Optional

try:
    from ..models import AnomalyRecord, DetectorType
except (ImportError, ValueError):
    from models import AnomalyRecord, DetectorType


class BaseDetector(ABC):
    """Abstract base class for all read-only anomaly detectors."""

    detector_type: DetectorType

    def __init__(self, detector_type: Optional[DetectorType] = None) -> None:
        if detector_type is not None:
            self.detector_type = detector_type

    @abstractmethod
    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Strictly read-only scan of target workspace.

        Args:
            workspace_root: Absolute or relative path to the target workspace root directory.

        Returns:
            List of detected AnomalyRecord instances.
        """
        pass
