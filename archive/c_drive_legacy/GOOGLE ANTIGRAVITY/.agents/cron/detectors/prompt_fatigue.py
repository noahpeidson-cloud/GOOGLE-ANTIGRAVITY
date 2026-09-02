"""Prompt Fatigue Anomaly Detector: Inspects GEMINI.md for rule bloat (>100 lines) and duplicate directives."""

import os
import re
import time
from typing import Dict, List, Optional, Set, Tuple

try:
    from ..config import PROMPT_FATIGUE_MAX_LINES
    from ..models import AnomalyRecord, DetectorType, Severity
    from .base import BaseDetector
except (ImportError, ValueError):
    from config import PROMPT_FATIGUE_MAX_LINES
    from detectors.base import BaseDetector
    from models import AnomalyRecord, DetectorType, Severity


HEADER_REGEX = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
RULE_TAG_REGEX = re.compile(r"<RULE\[([^\]]+)\]>", re.IGNORECASE)


def estimate_token_count(text: str) -> int:
    """Provides a deterministic estimate of token count (~4 characters per token average)."""
    if not text:
        return 0
    # Average 4 chars per token + word-based heuristic
    char_estimate = len(text) / 4.0
    word_estimate = len(text.split()) * 1.3
    return int((char_estimate + word_estimate) / 2.0)


class PromptFatigueDetector(BaseDetector):
    """Detects prompt fatigue and token bloat in GEMINI.md system manifests.

    Flags manifests exceeding 100 lines and identifies duplicate rule sections.
    """

    detector_type = DetectorType.PROMPT_FATIGUE

    def __init__(
        self,
        max_lines: int = PROMPT_FATIGUE_MAX_LINES,
        manifest_filename: str = "GEMINI.md",
    ) -> None:
        super().__init__(DetectorType.PROMPT_FATIGUE)
        self.max_lines = max_lines
        self.manifest_filename = manifest_filename

    def _find_manifest_file(self, workspace_root: str) -> Optional[str]:
        """Locates the GEMINI.md manifest file in workspace root or subdirectories."""
        root_path = os.path.join(workspace_root, self.manifest_filename)
        if os.path.isfile(root_path):
            return root_path

        for r, _, files in os.walk(workspace_root):
            for f in files:
                if f.upper() == self.manifest_filename.upper():
                    return os.path.join(r, f)
        return None

    def _extract_duplicate_sections(self, content: str) -> List[str]:
        """Extracts markdown headers and rule identifiers to detect duplicate sections."""
        seen_headers: Dict[str, int] = {}
        duplicates: List[str] = []

        # Check Markdown headers
        for match in HEADER_REGEX.finditer(content):
            header_text = match.group(2).strip().lower()
            seen_headers[header_text] = seen_headers.get(header_text, 0) + 1
            if seen_headers[header_text] == 2:
                duplicates.append(match.group(2).strip())

        # Check rule tags
        seen_tags: Dict[str, int] = {}
        for match in RULE_TAG_REGEX.finditer(content):
            tag_text = match.group(1).strip()
            seen_tags[tag_text] = seen_tags.get(tag_text, 0) + 1
            if seen_tags[tag_text] == 2 and tag_text not in duplicates:
                duplicates.append(f"<RULE[{tag_text}]>")

        return duplicates

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Scans workspace for GEMINI.md prompt fatigue and duplicate rules."""
        anomalies: List[AnomalyRecord] = []
        if not os.path.exists(workspace_root):
            return anomalies

        manifest_path = self._find_manifest_file(workspace_root)
        if not manifest_path:
            return anomalies

        try:
            with open(manifest_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return anomalies

        lines = content.splitlines()
        line_count = len(lines)
        token_count = estimate_token_count(content)
        duplicates = self._extract_duplicate_sections(content)
        current_ts = int(time.time())
        rel_path = os.path.relpath(manifest_path, workspace_root).replace("\\", "/")

        # Check line count threshold
        if line_count > self.max_lines:
            severity = Severity.HIGH if line_count > (self.max_lines * 1.5) else Severity.MEDIUM
            anomalies.append(
                AnomalyRecord(
                    detector_type=DetectorType.PROMPT_FATIGUE,
                    target_path=rel_path,
                    severity=severity,
                    description=(
                        f"Manifest rule bloat: {self.manifest_filename} has {line_count} lines "
                        f"(exceeds {self.max_lines} line threshold, ~{token_count} tokens)"
                    ),
                    raw_details={
                        "manifest_file": rel_path,
                        "line_count": line_count,
                        "max_lines": self.max_lines,
                        "token_count": token_count,
                        "duplicate_sections": duplicates,
                    },
                    is_historical=False,
                    timestamp=current_ts,
                    confidence=1.0,
                )
            )

        # Check duplicate rule sections separately if found
        if duplicates:
            anomalies.append(
                AnomalyRecord(
                    detector_type=DetectorType.PROMPT_FATIGUE,
                    target_path=rel_path,
                    severity=Severity.HIGH,
                    description=(
                        f"Duplicate rule sections detected in {self.manifest_filename}: {', '.join(duplicates)}"
                    ),
                    raw_details={
                        "manifest_file": rel_path,
                        "duplicate_sections": duplicates,
                        "duplicate_count": len(duplicates),
                    },
                    is_historical=False,
                    timestamp=current_ts,
                    confidence=1.0,
                )
            )

        return anomalies
