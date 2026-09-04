"""Ecosystem Pollution Anomaly Detector: Identifies .disabled plugins and cross-track domain leaks."""

import os
import re
import time
from typing import List, Optional, Set

try:
    from ..models import AnomalyRecord, DetectorType, Severity
    from .base import BaseDetector
except (ImportError, ValueError):
    from detectors.base import BaseDetector
    from models import AnomalyRecord, DetectorType, Severity


MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv"}
SPORTS_CARD_KEYWORDS = {"card_ladder", "cardladder", "psa_grade", "bgs_grade", "sports_card", "sportscard"}
MEDIA_KEYWORDS = {"ffmpeg", "ffprobe", "video_render", "da_vinci", "premiere", "hdr_video"}


class EcosystemPollutionDetector(BaseDetector):
    """Detects ecosystem pollution across the workspace, including:

    1. Unused .disabled plugin/component directories and files.
    2. Cross-track domain leaks (e.g. media engineering files placed in sports_cards or vice versa).
    """

    detector_type = DetectorType.ECOSYSTEM_POLLUTION

    def __init__(self, ignored_dirs: Optional[Set[str]] = None) -> None:
        super().__init__(DetectorType.ECOSYSTEM_POLLUTION)
        self.ignored_dirs = ignored_dirs or {
            ".git",
            "node_modules",
            "venv",
            ".venv",
            "__pycache__",
            ".pytest_cache",
        }

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Scans workspace for .disabled plugins and cross-track pollution."""
        anomalies: List[AnomalyRecord] = []
        if not os.path.exists(workspace_root):
            return anomalies

        current_ts = int(time.time())

        for root, dirs, files in os.walk(workspace_root):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]

            rel_root = os.path.relpath(root, workspace_root).replace("\\", "/")

            # 1. Check directories for .disabled extension
            for d in list(dirs):
                if d.endswith(".disabled"):
                    full_dir_path = os.path.join(root, d)
                    rel_dir_path = os.path.relpath(full_dir_path, workspace_root).replace("\\", "/")
                    anomalies.append(
                        AnomalyRecord(
                            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                            target_path=rel_dir_path,
                            severity=Severity.HIGH,
                            description=f"Unused disabled plugin/component directory '{d}' polluting workspace",
                            raw_details={
                                "pollution_type": "DISABLED_PLUGIN",
                                "name": d,
                                "path": rel_dir_path,
                                "is_dir": True,
                            },
                            is_historical=False,
                            timestamp=current_ts,
                            confidence=1.0,
                        )
                    )

            # 2. Check files for .disabled extension and cross-track leaks
            for file in files:
                full_file_path = os.path.join(root, file)
                rel_file_path = os.path.relpath(full_file_path, workspace_root).replace("\\", "/")
                file_lower = file.lower()
                _, ext = os.path.splitext(file_lower)

                # 2.1 .disabled files
                if file.endswith(".disabled"):
                    anomalies.append(
                        AnomalyRecord(
                            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                            target_path=rel_file_path,
                            severity=Severity.HIGH,
                            description=f"Unused disabled component file '{file}' polluting workspace",
                            raw_details={
                                "pollution_type": "DISABLED_PLUGIN",
                                "name": file,
                                "path": rel_file_path,
                                "is_dir": False,
                            },
                            is_historical=False,
                            timestamp=current_ts,
                            confidence=1.0,
                        )
                    )
                    continue

                # 2.2 Cross-track leak checks
                # Track 1: sports_cards — should not contain media assets or video engineering scripts
                if "sports_cards" in rel_file_path:
                    if ext in MEDIA_EXTENSIONS:
                        anomalies.append(
                            AnomalyRecord(
                                detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                                target_path=rel_file_path,
                                severity=Severity.MEDIUM,
                                description=(
                                    f"Cross-track leak: Media file '{file}' located in /sports_cards track"
                                ),
                                raw_details={
                                    "pollution_type": "CROSS_TRACK_LEAK",
                                    "track": "sports_cards",
                                    "reason": f"Media file extension '{ext}' in sports_cards",
                                },
                                is_historical=False,
                                timestamp=current_ts,
                                confidence=0.95,
                            )
                        )
                    elif ext in {".py", ".sh", ".ts", ".js"}:
                        try:
                            with open(full_file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read(4096).lower()
                            if any(mk in content for mk in MEDIA_KEYWORDS) and "ffmpeg" in content:
                                anomalies.append(
                                    AnomalyRecord(
                                        detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                                        target_path=rel_file_path,
                                        severity=Severity.MEDIUM,
                                        description=(
                                            f"Cross-track leak: Video engineering logic detected in /sports_cards file '{file}'"
                                        ),
                                        raw_details={
                                            "pollution_type": "CROSS_TRACK_LEAK",
                                            "track": "sports_cards",
                                            "reason": "FFmpeg/video keywords in sports_cards code",
                                        },
                                        is_historical=False,
                                        timestamp=current_ts,
                                        confidence=0.9,
                                    )
                                )
                        except Exception:
                            pass

                # Track 2: content_creation — should not contain sports cards domain data / logic
                elif "content_creation" in rel_file_path:
                    if any(sk in file_lower for sk in SPORTS_CARD_KEYWORDS):
                        anomalies.append(
                            AnomalyRecord(
                                detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                                target_path=rel_file_path,
                                severity=Severity.MEDIUM,
                                description=(
                                    f"Cross-track leak: Sports cards artifact '{file}' located in /content_creation track"
                                ),
                                raw_details={
                                    "pollution_type": "CROSS_TRACK_LEAK",
                                    "track": "content_creation",
                                    "reason": f"Sports card keyword match in content_creation file '{file}'",
                                },
                                is_historical=False,
                                timestamp=current_ts,
                                confidence=0.95,
                            )
                        )

        return anomalies
