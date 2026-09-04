"""Context Rot Anomaly Detector: Identifies stale planning artifacts older than 24h diluting context."""

import fnmatch
import os
import time
from typing import List, Optional, Set

try:
    from ..config import CONTEXT_ROT_THRESHOLD_HOURS, WHITELISTED_FILENAMES
    from ..models import AnomalyRecord, DetectorType, Severity
    from .base import BaseDetector
except (ImportError, ValueError):
    from config import CONTEXT_ROT_THRESHOLD_HOURS, WHITELISTED_FILENAMES
    from detectors.base import BaseDetector
    from models import AnomalyRecord, DetectorType, Severity


DEFAULT_PLANNING_PATTERNS: List[str] = [
    "*proposal*.md",
    "*blueprint*.md",
    "*ideas*.md",
    "*scratchpad*.md",
    "*plan*.md",
    "*progress*.md",
    "*context*.md",
]


class ContextRotDetector(BaseDetector):
    """Detects stale planning artifacts older than 24 hours that dilute LLM context windows.

    Strictly protects whitelisted manifest files (PROJECT.md, GEMINI.md, README.md, BRIEFING.md, ORIGINAL_REQUEST.md).
    """

    detector_type = DetectorType.CONTEXT_ROT

    def __init__(
        self,
        threshold_hours: float = CONTEXT_ROT_THRESHOLD_HOURS,
        whitelisted_filenames: Optional[List[str]] = None,
        planning_patterns: Optional[List[str]] = None,
        ignored_dirs: Optional[Set[str]] = None,
    ) -> None:
        super().__init__(DetectorType.CONTEXT_ROT)
        self.threshold_hours = threshold_hours
        self.whitelisted_filenames = {
            f.upper() for f in (whitelisted_filenames or WHITELISTED_FILENAMES)
        }
        self.planning_patterns = list(planning_patterns or DEFAULT_PLANNING_PATTERNS)
        self.ignored_dirs = ignored_dirs or {
            ".git",
            "node_modules",
            "venv",
            ".venv",
            "__pycache__",
            ".pytest_cache",
        }

    def _is_planning_file(self, filename: str) -> bool:
        """Checks if a filename matches any of the planning artifact glob patterns."""
        fn_lower = filename.lower()
        return any(fnmatch.fnmatch(fn_lower, pat.lower()) for pat in self.planning_patterns)

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Scans workspace for planning markdown files older than the configured threshold hours."""
        anomalies: List[AnomalyRecord] = []
        if not os.path.exists(workspace_root):
            return anomalies

        current_time = time.time()
        current_ts = int(current_time)

        for root, dirs, files in os.walk(workspace_root):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]

            for file in files:
                file_upper = file.upper()
                # Strict whitelist check
                if file_upper in self.whitelisted_filenames:
                    continue

                if not file.endswith(".md"):
                    continue

                if self._is_planning_file(file):
                    full_path = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(full_path)
                    except OSError:
                        continue

                    age_hours = (current_time - mtime) / 3600.0
                    if age_hours > self.threshold_hours:
                        rel_path = os.path.relpath(full_path, workspace_root).replace("\\", "/")
                        record = AnomalyRecord(
                            detector_type=DetectorType.CONTEXT_ROT,
                            target_path=rel_path,
                            severity=Severity.MEDIUM,
                            description=(
                                f"Planning artifact '{file}' is {age_hours:.1f}h old "
                                f"(exceeds {self.threshold_hours:.1f}h threshold)"
                            ),
                            raw_details={
                                "file_name": file,
                                "age_hours": round(age_hours, 2),
                                "threshold_hours": self.threshold_hours,
                                "mtime": mtime,
                            },
                            is_historical=False,
                            timestamp=current_ts,
                            confidence=min(1.0, max(0.5, age_hours / (self.threshold_hours * 2))),
                        )
                        anomalies.append(record)

        return anomalies
