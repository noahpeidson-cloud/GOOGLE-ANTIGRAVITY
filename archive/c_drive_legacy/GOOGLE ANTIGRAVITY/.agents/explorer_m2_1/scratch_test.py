"""Scratchpad validation script for detector prototypes in explorer_m2_1."""

import os
import sys
from pathlib import Path

# Add cron dir to sys.path
cron_dir = Path(__file__).resolve().parent.parent / "cron"
if str(cron_dir) not in sys.path:
    sys.path.insert(0, str(cron_dir))

from safety_guardrails import scan_code_for_safety

sample_base_code = """
from abc import ABC, abstractmethod
from typing import List
from models import AnomalyRecord, DetectorType

class BaseDetector(ABC):
    detector_type: DetectorType

    @abstractmethod
    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        pass
"""

sample_ghost_code = """
import socket
import time
from typing import List, Optional
from models import AnomalyRecord, DetectorType, Severity
from config import MONITORED_PORTS

class GhostDaemonsDetector:
    def __init__(self, target_ports: Optional[List[int]] = None, host: str = "127.0.0.1"):
        self.target_ports = target_ports or list(MONITORED_PORTS)
        self.host = host

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        anomalies = []
        for port in self.target_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.2)
                res = sock.connect_ex((self.host, port))
                sock.close()
                if res == 0:
                    anomalies.append(
                        AnomalyRecord(
                            detector_type=DetectorType.GHOST_DAEMONS,
                            target_path=f"{self.host}:{port}",
                            severity=Severity.HIGH,
                            description=f"Ghost daemon / port collision detected on port {port} (WinError 10048 signature)",
                            raw_details={
                                "port": port,
                                "host": self.host,
                                "status": "OCCUPIED",
                                "errno": 10048,
                                "error_signature": "WinError 10048 (WSAEADDRINUSE)",
                                "pid": None,
                                "process_name": "unknown",
                                "proposed_action": "REPORT_OCCUPIED_PORT",
                            },
                            is_historical=False,
                            timestamp=int(time.time()),
                            confidence=1.0,
                        )
                    )
            except Exception:
                pass
        return anomalies
"""

sample_context_rot_code = """
import os
import time
import fnmatch
from typing import List, Optional, Set
from models import AnomalyRecord, DetectorType, Severity
from config import CONTEXT_ROT_THRESHOLD_HOURS, WHITELISTED_FILENAMES

DEFAULT_ROT_PATTERNS = [
    "*proposal*.md",
    "*blueprint*.md",
    "*ideas*.md",
    "*scratchpad*.md",
    "*plan*.md",
]

EXCLUDED_DIRS = {".git", "venv", ".venv", "__pycache__", ".pytest_cache", "node_modules"}

class ContextRotDetector:
    def __init__(
        self,
        threshold_hours: float = CONTEXT_ROT_THRESHOLD_HOURS,
        patterns: Optional[List[str]] = None,
        whitelisted_filenames: Optional[List[str]] = None,
    ):
        self.threshold_hours = threshold_hours
        self.patterns = patterns or DEFAULT_ROT_PATTERNS
        self.whitelisted_filenames = {
            f.upper() for f in (whitelisted_filenames or WHITELISTED_FILENAMES)
        }

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        anomalies = []
        now = time.time()
        for root, dirs, files in os.walk(workspace_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                basename = file
                if basename.upper() in self.whitelisted_filenames:
                    continue
                matched_pat = None
                for pat in self.patterns:
                    if fnmatch.fnmatch(basename.lower(), pat.lower()):
                        matched_pat = pat
                        break
                if matched_pat:
                    full_path = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(full_path)
                        age_hours = (now - mtime) / 3600.0
                        if age_hours >= self.threshold_hours:
                            rel_path = os.path.relpath(full_path, workspace_root)
                            anomalies.append(
                                AnomalyRecord(
                                    detector_type=DetectorType.CONTEXT_ROT,
                                    target_path=rel_path,
                                    severity=Severity.MEDIUM,
                                    description=(
                                        f"Stale planning artifact '{basename}' is {age_hours:.1f}h old "
                                        f"(exceeds {self.threshold_hours:.1f}h threshold) and dilutes context window"
                                    ),
                                    raw_details={
                                        "file_name": basename,
                                        "file_path": os.path.abspath(full_path),
                                        "relative_path": rel_path,
                                        "age_hours": round(age_hours, 2),
                                        "threshold_hours": self.threshold_hours,
                                        "mtime": mtime,
                                        "matched_pattern": matched_pat,
                                        "proposed_action": "MOVE_TO_ARCHIVE",
                                    },
                                    is_historical=False,
                                    timestamp=int(now),
                                    confidence=0.95,
                                )
                            )
                    except Exception:
                        pass
        return anomalies
"""

def test_ast_safety():
    for name, code in [("base", sample_base_code), ("ghost", sample_ghost_code), ("rot", sample_context_rot_code)]:
        violations = scan_code_for_safety(code, filename=name)
        assert len(violations) == 0, f"AST Safety violations in {name}: {violations}"
        print(f"[AST Safety PASS] {name} has 0 violations.")

if __name__ == "__main__":
    test_ast_safety()
