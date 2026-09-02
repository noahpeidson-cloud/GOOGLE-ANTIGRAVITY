"""Secret Zero Anomaly Detector: Scans environment and config files for placeholder tokens with token masking."""

import fnmatch
import os
import re
import time
from typing import List, Optional, Set

try:
    from ..config import BLACKLIST_TOKEN_PATTERNS
    from ..models import AnomalyRecord, DetectorType, Severity
    from .base import BaseDetector
except (ImportError, ValueError):
    from config import BLACKLIST_TOKEN_PATTERNS
    from detectors.base import BaseDetector
    from models import AnomalyRecord, DetectorType, Severity


CONFIG_FILE_PATTERNS: List[str] = [
    ".env",
    ".env.*",
    "*.json",
    "*.yaml",
    "*.yml",
    "*.toml",
    "*.ini",
    "*.cfg",
]


def mask_token(token: str) -> str:
    """Masks a token string so that secret/placeholder values are never leaked in plain text."""
    clean = token.strip()
    if len(clean) <= 4:
        return "****"
    return f"{clean[:2]}***{clean[-2:]}"


class SecretZeroDetector(BaseDetector):
    """Detects unresolved placeholder tokens and leaked template credentials in configuration files.

    Strictly masks all tokens in descriptions and raw details to prevent leakage in telemetry and reports.
    """

    detector_type = DetectorType.SECRET_ZERO

    def __init__(
        self,
        token_patterns: Optional[List[str]] = None,
        config_patterns: Optional[List[str]] = None,
        ignored_dirs: Optional[Set[str]] = None,
    ) -> None:
        super().__init__(DetectorType.SECRET_ZERO)
        raw_patterns = token_patterns or BLACKLIST_TOKEN_PATTERNS
        self.compiled_patterns = [
            (pat, re.compile(pat, re.IGNORECASE)) for pat in raw_patterns
        ]
        self.config_patterns = list(config_patterns or CONFIG_FILE_PATTERNS)
        self.ignored_dirs = ignored_dirs or {
            ".git",
            "node_modules",
            "venv",
            ".venv",
            "__pycache__",
            ".pytest_cache",
        }

    def _is_config_file(self, filename: str) -> bool:
        """Checks if a file matches standard environment or configuration file patterns."""
        fn_lower = filename.lower()
        return any(fnmatch.fnmatch(fn_lower, pat.lower()) for pat in self.config_patterns)

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Scans workspace configuration and environment files for placeholder tokens."""
        anomalies: List[AnomalyRecord] = []
        if not os.path.exists(workspace_root):
            return anomalies

        current_ts = int(time.time())

        for root, dirs, files in os.walk(workspace_root):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]

            for file in files:
                if self._is_config_file(file):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, workspace_root).replace("\\", "/")

                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                    except Exception:
                        continue

                    for line_idx, line_content in enumerate(lines, start=1):
                        for pattern_str, regex in self.compiled_patterns:
                            match = regex.search(line_content)
                            if match:
                                matched_val = match.group(0)
                                masked = mask_token(matched_val)
                                record = AnomalyRecord(
                                    detector_type=DetectorType.SECRET_ZERO,
                                    target_path=rel_path,
                                    severity=Severity.CRITICAL,
                                    description=(
                                        f"Unresolved placeholder token '{masked}' found in {rel_path}:{line_idx}"
                                    ),
                                    raw_details={
                                        "file": rel_path,
                                        "line_no": line_idx,
                                        "matched_pattern": pattern_str,
                                        "masked_token": masked,
                                    },
                                    is_historical=False,
                                    timestamp=current_ts,
                                    confidence=1.0,
                                )
                                anomalies.append(record)
                                # Break pattern loop on first match per line to avoid duplicate line reporting
                                break

        return anomalies
