"""Modular Health Scanner orchestrating all 5 read-only anomaly detectors with error isolation."""

import logging
import time
from typing import List, Optional

try:
    from .detectors.base import BaseDetector
    from .detectors.context_rot import ContextRotDetector
    from .detectors.ecosystem_pollution import EcosystemPollutionDetector
    from .detectors.ghost_daemons import GhostDaemonsDetector
    from .detectors.prompt_fatigue import PromptFatigueDetector
    from .detectors.secret_zero import SecretZeroDetector
    from .models import AnomalyRecord
except (ImportError, ValueError):
    from detectors.base import BaseDetector
    from detectors.context_rot import ContextRotDetector
    from detectors.ecosystem_pollution import EcosystemPollutionDetector
    from detectors.ghost_daemons import GhostDaemonsDetector
    from detectors.prompt_fatigue import PromptFatigueDetector
    from detectors.secret_zero import SecretZeroDetector
    from models import AnomalyRecord

logger = logging.getLogger(__name__)


class HealthScanner:
    """Orchestrates sequential execution of modular anomaly detectors with exception isolation

    and scan duration telemetry.
    """

    def __init__(self, detectors: Optional[List[BaseDetector]] = None) -> None:
        if detectors is not None:
            self.detectors: List[BaseDetector] = list(detectors)
        else:
            self.detectors = [
                GhostDaemonsDetector(),
                ContextRotDetector(),
                EcosystemPollutionDetector(),
                SecretZeroDetector(),
                PromptFatigueDetector(),
            ]
        self._last_duration_ms: float = 0.0

    def get_last_duration_ms(self) -> float:
        """Returns the duration of the most recent workspace scan in milliseconds."""
        return self._last_duration_ms

    def scan_workspace(self, workspace_root: str) -> List[AnomalyRecord]:
        """Executes a strictly read-only health scan across the workspace.

        Isolates individual detector failures so a single failing detector does not halt
        the overall scan.

        Args:
            workspace_root: Absolute or relative path to the workspace root directory.

        Returns:
            Aggregated list of all AnomalyRecord objects detected.
        """
        start_time = time.perf_counter()
        all_anomalies: List[AnomalyRecord] = []

        for detector in self.detectors:
            det_name = detector.__class__.__name__
            try:
                findings = detector.scan(workspace_root)
                if findings:
                    all_anomalies.extend(findings)
            except Exception as e:
                logger.warning(
                    "Detector '%s' encountered an isolated exception during scan: %s",
                    det_name,
                    e,
                    exc_info=True,
                )

        elapsed_seconds = time.perf_counter() - start_time
        self._last_duration_ms = elapsed_seconds * 1000.0
        return all_anomalies
