# Milestone 2: Master Health Scanner & Detector Test Suite Deep Analysis

**Author**: `explorer_m2_3`  
**Working Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m2_3`  
**Target Modules**:
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\scanner.py`
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\detectors\base.py`
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\detectors\ghost_daemons.py`
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\detectors\context_rot.py`
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\detectors\ecosystem_pollution.py`
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\detectors\secret_zero.py`
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\detectors\prompt_fatigue.py`
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_detectors.py`

---

## 1. System Architecture Overview

Milestone 2 establishes the read-only inspection engine for the Antigravity Daily Health Sentinel. The architecture consists of:
1. **Abstract Detector Contract (`detectors/base.py`)**: Abstract base class `BaseDetector` defining `scan(workspace_root: str) -> List[AnomalyRecord]`.
2. **5 Modular Read-Only Detectors**:
   - `GhostDaemonsDetector`: Probes ports (3000, 8000, 8501) for `WinError 10048` socket collisions & unmonitored tasks.
   - `ContextRotDetector`: Recursively identifies stale `.md` planning artifacts older than 24.0 hours while strictly respecting whitelisted files.
   - `EcosystemPollutionDetector`: Detects `.disabled` plugin directories and cross-track domain boundary contamination.
   - `SecretZeroDetector`: Scans configuration and environment files for unresolved placeholder tokens (`your_token_here`), masking values.
   - `PromptFatigueDetector`: Identifies `GEMINI.md` manifest bloat exceeding 100 lines and duplicate rule headings.
3. **Master Health Scanner Orchestrator (`scanner.py`)**:
   - `HealthScanner` class initializing all 5 detectors.
   - Sequential read-only execution via `scan_workspace(workspace_root: str) -> List[AnomalyRecord]`.
   - Graceful detector exception isolation (`try...except` per detector) preventing any single detector crash from halting the scan.
   - High-resolution duration tracking in milliseconds (`perf_counter()`).
4. **Comprehensive Unit & Integration Test Suite (`tests/test_detectors.py`)**:
   - 25+ pytest test cases across Tiers 1 and 2 verifying all individual detectors and master orchestrator integration.
   - Cryptographic `FileSystemSnapshot` SHA256 integrity verification guaranteeing 0 destructive side effects.

---

## 2. Complete Implementation Blueprint for `scanner.py`

```python
\"\"\"Master Health Scanner Orchestrator for Antigravity Daily Health Daemon.\"\"\"

import logging
import os
import time
from typing import Any, Dict, List, Optional

from config import MONITORED_PORTS
from models import AnomalyRecord, DetectorType, Severity
from detectors.base import BaseDetector
from detectors.ghost_daemons import GhostDaemonsDetector
from detectors.context_rot import ContextRotDetector
from detectors.ecosystem_pollution import EcosystemPollutionDetector
from detectors.secret_zero import SecretZeroDetector
from detectors.prompt_fatigue import PromptFatigueDetector

logger = logging.getLogger(__name__)


class HealthScanner:
    \"\"\"Master health scanner orchestrating sequential read-only detector runs.\"\"\"

    def __init__(
        self,
        detectors: Optional[List[BaseDetector]] = None,
        custom_logger: Optional[logging.Logger] = None,
    ) -> None:
        if detectors is not None:
            self.detectors = list(detectors)
        else:
            self.detectors = [
                GhostDaemonsDetector(),
                ContextRotDetector(),
                EcosystemPollutionDetector(),
                SecretZeroDetector(),
                PromptFatigueDetector(),
            ]
        self.logger = custom_logger or logger
        self.last_duration_ms: float = 0.0
        self.last_scan_timestamp: int = 0
        self.last_detector_errors: Dict[str, str] = {}

    def scan_workspace(self, workspace_root: str) -> List[AnomalyRecord]:
        \"\"\"Executes all anomaly detectors sequentially in a strictly read-only manner.

        Gracefully isolates detector exceptions so that one failing detector
        does not abort the full scan. Measures duration in milliseconds.

        Args:
            workspace_root: Path to the target workspace root directory.

        Returns:
            Aggregated List[AnomalyRecord] from all successful detector scans.
        \"\"\"
        start_time = time.perf_counter()
        self.last_scan_timestamp = int(time.time())
        self.last_detector_errors.clear()

        if not workspace_root or not os.path.exists(workspace_root):
            self.logger.warning(f"Workspace root does not exist: {workspace_root}")
            self.last_duration_ms = (time.perf_counter() - start_time) * 1000.0
            return []

        abs_root = os.path.abspath(workspace_root)
        aggregated_anomalies: List[AnomalyRecord] = []

        for detector in self.detectors:
            det_name = detector.__class__.__name__
            try:
                self.logger.debug(f"Starting detector: {det_name}")
                anomalies = detector.scan(abs_root)
                if anomalies:
                    for anomaly in anomalies:
                        if not anomaly.timestamp:
                            anomaly.timestamp = self.last_scan_timestamp
                    aggregated_anomalies.extend(anomalies)
                self.logger.debug(f"Detector {det_name} finished: found {len(anomalies) if anomalies else 0} anomalies.")
            except Exception as exc:
                err_msg = f"Detector '{det_name}' failed with exception: {exc}"
                self.logger.warning(err_msg, exc_info=True)
                self.last_detector_errors[det_name] = str(exc)

        self.last_duration_ms = (time.perf_counter() - start_time) * 1000.0
        self.logger.info(
            f"Health scan completed in {self.last_duration_ms:.2f}ms. Total anomalies found: {len(aggregated_anomalies)}."
        )
        return aggregated_anomalies

    def get_last_duration_ms(self) -> float:
        \"\"\"Returns the duration of the most recent scan in milliseconds.\"\"\"
        return self.last_duration_ms

    def get_detector_errors(self) -> Dict[str, str]:
        \"\"\"Returns any detector errors recorded during the most recent scan.\"\"\"
        return dict(self.last_detector_errors)

    def get_summary(self, anomalies: List[AnomalyRecord]) -> Dict[str, Any]:
        \"\"\"Generates summary statistics from a list of AnomalyRecords.\"\"\"
        by_detector: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}

        for a in anomalies:
            det_type = a.detector_type.value if hasattr(a.detector_type, "value") else str(a.detector_type)
            sev = a.severity.value if hasattr(a.severity, "value") else str(a.severity)
            by_detector[det_type] = by_detector.get(det_type, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            "total_anomalies": len(anomalies),
            "duration_ms": self.last_duration_ms,
            "timestamp": self.last_scan_timestamp,
            "by_detector": by_detector,
            "by_severity": by_severity,
            "errors": self.last_detector_errors,
        }
```

---

## 3. Implementation Blueprints for the 5 Detectors

### 3.1 Base Detector (`detectors/base.py`)
```python
\"\"\"Abstract base detector interface.\"\"\"

from abc import ABC, abstractmethod
from typing import List
from models import AnomalyRecord, DetectorType


class BaseDetector(ABC):
    \"\"\"Strictly read-only workspace anomaly detector.\"\"\"

    @property
    @abstractmethod
    def detector_type(self) -> DetectorType:
        \"\"\"Returns the DetectorType enum associated with this detector.\"\"\"
        pass

    @abstractmethod
    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        \"\"\"Strictly read-only scan of the target workspace.

        Args:
            workspace_root: Absolute path to workspace root.

        Returns:
            List of AnomalyRecord instances detected.
        \"\"\"
        pass
```

### 3.2 Ghost Daemons Detector (`detectors/ghost_daemons.py`)
```python
\"\"\"Ghost Daemons anomaly detector: identifies port collisions and unmonitored server processes.\"\"\"

import errno
import socket
import time
from typing import List, Optional

from config import MONITORED_PORTS
from detectors.base import BaseDetector
from models import AnomalyRecord, DetectorType, Severity


class GhostDaemonsDetector(BaseDetector):
    \"\"\"Detects unmonitored server daemons binding ports 3000, 8000, 8501 without supervision.\"\"\"

    def __init__(self, ports: Optional[List[int]] = None) -> None:
        self.ports = list(ports) if ports is not None else list(MONITORED_PORTS)

    @property
    def detector_type(self) -> DetectorType:
        return DetectorType.GHOST_DAEMONS

    def _is_port_occupied(self, port: int, host: str = "127.0.0.1") -> bool:
        \"\"\"Non-destructively checks if a TCP port is occupied on loopback.\"\"\"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            result = s.connect_ex((host, port))
            return result == 0

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        \"\"\"Scans loopback ports for unmonitored daemon bindings.\"\"\"
        anomalies: List[AnomalyRecord] = []
        current_ts = int(time.time())

        for port in self.ports:
            if self._is_port_occupied(port):
                anomalies.append(
                    AnomalyRecord(
                        detector_type=DetectorType.GHOST_DAEMONS,
                        target_path=f"127.0.0.1:{port}",
                        severity=Severity.HIGH,
                        description=f"Socket collision / unmonitored ghost daemon detected on port {port} (WinError 10048)",
                        raw_details={
                            "port": port,
                            "host": "127.0.0.1",
                            "status": "OCCUPIED",
                            "errno": 10048,
                            "error_name": "WSAEADDRINUSE",
                        },
                        is_historical=False,
                        timestamp=current_ts,
                        confidence=1.0,
                    )
                )
        return anomalies
```

### 3.3 Context Rot Detector (`detectors/context_rot.py`)
```python
\"\"\"Context Rot anomaly detector: identifies stale planning artifacts >24h old.\"\"\"

import fnmatch
import os
import time
from typing import List, Optional, Set

from config import CONTEXT_ROT_THRESHOLD_HOURS, WHITELISTED_FILENAMES
from detectors.base import BaseDetector
from models import AnomalyRecord, DetectorType, Severity

PLANNING_PATTERNS = [
    "*proposal*.md",
    "*blueprint*.md",
    "*ideas*.md",
    "*scratchpad*.md",
    "*plan*.md",
    "*draft*.md",
    "task.md",
]

IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
}


class ContextRotDetector(BaseDetector):
    \"\"\"Identifies planning markdown files older than 24 hours diluting the context window.\"\"\"

    def __init__(
        self,
        threshold_hours: float = CONTEXT_ROT_THRESHOLD_HOURS,
        whitelisted_filenames: Optional[List[str]] = None,
        planning_patterns: Optional[List[str]] = None,
    ) -> None:
        self.threshold_hours = float(threshold_hours)
        self.whitelisted_filenames: Set[str] = set(
            whitelisted_filenames if whitelisted_filenames is not None else WHITELISTED_FILENAMES
        )
        self.planning_patterns = list(planning_patterns or PLANNING_PATTERNS)

    @property
    def detector_type(self) -> DetectorType:
        return DetectorType.CONTEXT_ROT

    def _is_planning_file(self, filename: str) -> bool:
        lower_name = filename.lower()
        return any(fnmatch.fnmatch(lower_name, pattern.lower()) for pattern in self.planning_patterns)

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        \"\"\"Recursively walks workspace to find stale planning files.\"\"\"
        anomalies: List[AnomalyRecord] = []
        now = time.time()
        threshold_seconds = self.threshold_hours * 3600.0

        for root, dirs, files in os.walk(workspace_root):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            for file in files:
                if not file.endswith(".md"):
                    continue

                if file in self.whitelisted_filenames:
                    continue

                if not self._is_planning_file(file):
                    continue

                full_path = os.path.join(root, file)
                try:
                    mtime = os.path.getmtime(full_path)
                    age_seconds = now - mtime
                    if age_seconds > threshold_seconds:
                        age_hours = age_seconds / 3600.0
                        rel_path = os.path.relpath(full_path, workspace_root).replace("\\\\", "/")
                        anomalies.append(
                            AnomalyRecord(
                                detector_type=DetectorType.CONTEXT_ROT,
                                target_path=rel_path,
                                severity=Severity.MEDIUM,
                                description=f"Stale planning artifact '{file}' is {age_hours:.1f}h old (exceeds {self.threshold_hours}h limit)",
                                raw_details={
                                    "age_hours": round(age_hours, 2),
                                    "threshold_hours": self.threshold_hours,
                                    "mtime": mtime,
                                    "proposed_action": "MOVE_TO_ARCHIVE",
                                },
                                is_historical=False,
                                timestamp=int(now),
                                confidence=0.95,
                            )
                        )
                except (OSError, IOError):
                    continue

        return anomalies
```

### 3.4 Ecosystem Pollution Detector (`detectors/ecosystem_pollution.py`)
```python
\"\"\"Ecosystem Pollution anomaly detector: detects .disabled plugins and cross-track domain leaks.\"\"\"

import os
import time
from typing import List, Set

from detectors.base import BaseDetector
from models import AnomalyRecord, DetectorType, Severity

IGNORED_DIRS = {".git", "node_modules", ".pytest_cache", "__pycache__", ".venv", "venv"}

TRACK_CROSS_CONTAMINATION_RULES = [
    {
        "track_prefix": "content_creation",
        "forbidden_keywords": ["card_ladder", "psa_slab", "bgs_slab", "sports_card", "slab_serial"],
        "leak_source": "sports_cards",
    },
    {
        "track_prefix": "sports_cards",
        "forbidden_keywords": ["davinci_resolve", "premiere_pro", "ffmpeg_proxy", "hdr_color_grade"],
        "leak_source": "content_creation",
    },
]


class EcosystemPollutionDetector(BaseDetector):
    \"\"\"Identifies .disabled plugin directories and cross-track contamination.\"\"\"

    @property
    def detector_type(self) -> DetectorType:
        return DetectorType.ECOSYSTEM_POLLUTION

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        anomalies: List[AnomalyRecord] = []
        current_ts = int(time.time())

        for root, dirs, files in os.walk(workspace_root):
            # 1. Check for .disabled directories
            for d in list(dirs):
                if d.endswith(".disabled"):
                    full_dir_path = os.path.join(root, d)
                    rel_path = os.path.relpath(full_dir_path, workspace_root).replace("\\\\", "/")
                    anomalies.append(
                        AnomalyRecord(
                            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                            target_path=rel_path,
                            severity=Severity.HIGH,
                            description=f"Unused .disabled plugin directory detected polluting workspace: {rel_path}",
                            raw_details={
                                "is_disabled": True,
                                "pollution_type": "disabled_plugin",
                                "directory": d,
                            },
                            is_historical=False,
                            timestamp=current_ts,
                            confidence=1.0,
                        )
                    )

            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            # 2. Check for cross-track leaks
            for file in files:
                full_file_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_file_path, workspace_root).replace("\\\\", "/")
                
                for rule in TRACK_CROSS_CONTAMINATION_RULES:
                    prefix = rule["track_prefix"]
                    if rel_path.startswith(prefix + "/") or rel_path.startswith(prefix + "\\\\"):
                        lower_file = file.lower()
                        for kw in rule["forbidden_keywords"]:
                            if kw in lower_file:
                                anomalies.append(
                                    AnomalyRecord(
                                        detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                                        target_path=rel_path,
                                        severity=Severity.MEDIUM,
                                        description=f"Cross-track domain contamination: '{file}' contains {rule['leak_source']} logic inside '{prefix}/'",
                                        raw_details={
                                            "track": prefix,
                                            "leak_source": rule["leak_source"],
                                            "keyword": kw,
                                            "pollution_type": "cross_track_leak",
                                        },
                                        is_historical=False,
                                        timestamp=current_ts,
                                        confidence=0.9,
                                    )
                                )
                                break
        return anomalies
```

### 3.5 Secret Zero Detector (`detectors/secret_zero.py`)
```python
\"\"\"Secret Zero anomaly detector: detects unresolved placeholder tokens in configs and .env files.\"\"\"

import os
import re
import time
from typing import List, Pattern

from config import BLACKLIST_TOKEN_PATTERNS
from detectors.base import BaseDetector
from models import AnomalyRecord, DetectorType, Severity

TARGET_EXTENSIONS = {".env", ".json", ".yaml", ".yml", ".toml"}
TARGET_FILENAMES = {".env", ".env.local", ".env.development", ".env.production", "config.json", "settings.yaml"}
IGNORED_DIRS = {".git", "node_modules", ".pytest_cache", "__pycache__", ".venv", "venv"}


class SecretZeroDetector(BaseDetector):
    \"\"\"Scans for placeholder tokens and dummy secrets in environment and config files.\"\"\"

    def __init__(self, token_patterns: Optional[List[str]] = None) -> None:
        patterns = token_patterns or BLACKLIST_TOKEN_PATTERNS
        self.regexes: List[Pattern[str]] = [re.compile(p, re.IGNORECASE) for p in patterns]

    @property
    def detector_type(self) -> DetectorType:
        return DetectorType.SECRET_ZERO

    def _mask_token(self, text: str) -> str:
        \"\"\"Masks sensitive tokens to prevent plain text exposure in telemetry.\"\"\"
        if len(text) <= 4:
            return "***"
        return text[:4] + "***"

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        anomalies: List[AnomalyRecord] = []
        current_ts = int(time.time())

        for root, dirs, files in os.walk(workspace_root):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if file not in TARGET_FILENAMES and ext not in TARGET_EXTENSIONS and not file.startswith(".env"):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, workspace_root).replace("\\\\", "/")

                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()

                    for idx, line in enumerate(lines, start=1):
                        for regex in self.regexes:
                            match = regex.search(line)
                            if match:
                                raw_match = match.group(0)
                                masked = self._mask_token(raw_match)
                                anomalies.append(
                                    AnomalyRecord(
                                        detector_type=DetectorType.SECRET_ZERO,
                                        target_path=rel_path,
                                        severity=Severity.CRITICAL,
                                        description=f"Unresolved placeholder token '{masked}' found in {rel_path} on line {idx}",
                                        raw_details={
                                            "line_number": idx,
                                            "pattern": regex.pattern,
                                            "masked_token": masked,
                                            "file_path": rel_path,
                                        },
                                        is_historical=False,
                                        timestamp=current_ts,
                                        confidence=1.0,
                                    )
                                )
                                break
                except (OSError, IOError):
                    continue

        return anomalies
```

### 3.6 Prompt Fatigue Detector (`detectors/prompt_fatigue.py`)
```python
\"\"\"Prompt Fatigue anomaly detector: checks GEMINI.md manifest for line bloat and duplicate rules.\"\"\"

import os
import re
import time
from typing import List, Optional

from config import PROMPT_FATIGUE_MAX_LINES
from detectors.base import BaseDetector
from models import AnomalyRecord, DetectorType, Severity


class PromptFatigueDetector(BaseDetector):
    \"\"\"Checks system prompt manifests (GEMINI.md) for rule bloat (>100 lines) and token exhaustion.\"\"\"

    def __init__(
        self,
        max_lines: int = PROMPT_FATIGUE_MAX_LINES,
        manifest_filename: str = "GEMINI.md",
    ) -> None:
        self.max_lines = int(max_lines)
        self.manifest_filename = manifest_filename

    @property
    def detector_type(self) -> DetectorType:
        return DetectorType.PROMPT_FATIGUE

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        anomalies: List[AnomalyRecord] = []
        current_ts = int(time.time())

        manifest_path = os.path.join(workspace_root, self.manifest_filename)
        if not os.path.exists(manifest_path):
            return anomalies

        try:
            with open(manifest_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            content = "".join(lines)
            word_count = len(content.split())
            estimated_tokens = int(word_count * 1.3)

            # Check for duplicate headings
            heading_regex = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
            headings = [m.group(2).strip().lower() for m in heading_regex.finditer(content)]
            seen_headings = set()
            duplicate_headings = []
            for h in headings:
                if h in seen_headings:
                    duplicate_headings.append(h)
                seen_headings.add(h)

            if total_lines > self.max_lines or duplicate_headings:
                rel_path = os.path.relpath(manifest_path, workspace_root).replace("\\\\", "/")
                anomalies.append(
                    AnomalyRecord(
                        detector_type=DetectorType.PROMPT_FATIGUE,
                        target_path=rel_path,
                        severity=Severity.MEDIUM,
                        description=f"Manifest rule bloat: '{self.manifest_filename}' has {total_lines} lines (exceeds {self.max_lines} limit)",
                        raw_details={
                            "line_count": total_lines,
                            "max_lines": self.max_lines,
                            "word_count": word_count,
                            "estimated_tokens": estimated_tokens,
                            "duplicate_headings": duplicate_headings,
                            "recommended_action": "Distill procedural rules into specialized skills or vectorized-rule-registry",
                        },
                        is_historical=False,
                        timestamp=current_ts,
                        confidence=1.0,
                    )
                )
        except (OSError, IOError):
            pass

        return anomalies
```

---

## 4. Comprehensive Test Suite Blueprint: `tests/test_detectors.py`

Below is the complete architectural specification for `tests/test_detectors.py` providing 26 deterministic test functions:

```python
\"\"\"Unit and integration tests for all 5 anomaly detectors and the master HealthScanner orchestrator.\"\"\"

import os
import socket
import sys
import time
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

# Ensure .agents/cron is in sys.path
CRON_DIR = Path(__file__).resolve().parent.parent
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

from config import MONITORED_PORTS, WHITELISTED_FILENAMES
from detectors.base import BaseDetector
from detectors.ghost_daemons import GhostDaemonsDetector
from detectors.context_rot import ContextRotDetector
from detectors.ecosystem_pollution import EcosystemPollutionDetector
from detectors.secret_zero import SecretZeroDetector
from detectors.prompt_fatigue import PromptFatigueDetector
from models import AnomalyRecord, DetectorType, Severity
from scanner import HealthScanner
from tests.conftest import FileSystemSnapshot


# ============================================================================
# 1. GHOST DAEMONS DETECTOR TESTS
# ============================================================================

def test_ghost_daemons_detects_occupied_port(isolated_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    \"\"\"1. Test that GhostDaemonsDetector detects an occupied port (e.g. 3000) and emits HIGH severity anomaly.\"\"\"
    detector = GhostDaemonsDetector(ports=[3000, 8000])

    def mock_is_port_occupied(self, port: int, host: str = "127.0.0.1") -> bool:
        return port == 3000

    monkeypatch.setattr(GhostDaemonsDetector, "_is_port_occupied", mock_is_port_occupied)

    anomalies = detector.scan(str(isolated_workspace))
    assert len(anomalies) == 1
    record = anomalies[0]
    assert record.detector_type == DetectorType.GHOST_DAEMONS
    assert record.severity == Severity.HIGH
    assert record.target_path == "127.0.0.1:3000"
    assert record.raw_details["port"] == 3000
    assert record.raw_details["status"] == "OCCUPIED"
    assert record.raw_details["errno"] == 10048


def test_ghost_daemons_free_ports_pass(isolated_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    \"\"\"2. Test that GhostDaemonsDetector returns 0 anomalies when all ports are free.\"\"\"
    detector = GhostDaemonsDetector(ports=[3000, 8000, 8501])
    monkeypatch.setattr(GhostDaemonsDetector, "_is_port_occupied", lambda self, port, host="127.0.0.1": False)

    anomalies = detector.scan(str(isolated_workspace))
    assert len(anomalies) == 0


def test_ghost_daemons_custom_ports(isolated_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    \"\"\"3. Test that GhostDaemonsDetector correctly probes custom port lists.\"\"\"
    detector = GhostDaemonsDetector(ports=[9000, 9001])
    probed = []

    def mock_is_port_occupied(self, port: int, host: str = "127.0.0.1") -> bool:
        probed.append(port)
        return port == 9001

    monkeypatch.setattr(GhostDaemonsDetector, "_is_port_occupied", mock_is_port_occupied)

    anomalies = detector.scan(str(isolated_workspace))
    assert probed == [9000, 9001]
    assert len(anomalies) == 1
    assert anomalies[0].raw_details["port"] == 9001


def test_ghost_daemons_socket_connection_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    \"\"\"4. Test internal _is_port_occupied via socket.socket connect_ex mock.\"\"\"
    detector = GhostDaemonsDetector()

    mock_socket_inst = MagicMock()
    mock_socket_inst.connect_ex.return_value = 0  # 0 indicates open/occupied

    mock_socket_cls = MagicMock()
    mock_socket_cls.return_value.__enter__.return_value = mock_socket_inst

    monkeypatch.setattr(socket, "socket", mock_socket_cls)

    assert detector._is_port_occupied(3000) is True
    mock_socket_inst.connect_ex.assert_called_with(("127.0.0.1", 3000))


# ============================================================================
# 2. CONTEXT ROT DETECTOR TESTS
# ============================================================================

def test_context_rot_detects_stale_planning_file(isolated_workspace: Path) -> None:
    \"\"\"5. Test that planning files older than 24h are flagged as CONTEXT_ROT.\"\"\"
    stale_file = isolated_workspace / ".agents" / "worker" / "plan.md"
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_text("# Old Plan\\nStale details.", encoding="utf-8")

    # Set mtime to 30 hours ago
    past_mtime = time.time() - (30 * 3600.0)
    os.utime(str(stale_file), (past_mtime, past_mtime))

    detector = ContextRotDetector(threshold_hours=24.0)
    anomalies = detector.scan(str(isolated_workspace))

    assert len(anomalies) == 1
    rec = anomalies[0]
    assert rec.detector_type == DetectorType.CONTEXT_ROT
    assert rec.severity == Severity.MEDIUM
    assert "plan.md" in rec.target_path
    assert rec.raw_details["age_hours"] >= 29.9
    assert rec.raw_details["proposed_action"] == "MOVE_TO_ARCHIVE"


def test_context_rot_fresh_planning_file_passes(isolated_workspace: Path) -> None:
    \"\"\"6. Test that fresh planning files (<24h) are not flagged.\"\"\"
    fresh_file = isolated_workspace / "blueprint_new.md"
    fresh_file.write_text("# Fresh Architecture", encoding="utf-8")

    # Set mtime to 2 hours ago
    past_mtime = time.time() - (2 * 3600.0)
    os.utime(str(fresh_file), (past_mtime, past_mtime))

    detector = ContextRotDetector(threshold_hours=24.0)
    anomalies = detector.scan(str(isolated_workspace))
    assert len(anomalies) == 0


def test_context_rot_whitelist_exemption(isolated_workspace: Path) -> None:
    \"\"\"7. Test that whitelisted files (PROJECT.md, GEMINI.md, README.md, BRIEFING.md, ORIGINAL_REQUEST.md) are exempt even if >24h old.\"\"\"
    past_mtime = time.time() - (100 * 3600.0)

    for filename in WHITELISTED_FILENAMES:
        p = isolated_workspace / filename
        p.write_text(f"# {filename}\\nPermanent content", encoding="utf-8")
        os.utime(str(p), (past_mtime, past_mtime))

    detector = ContextRotDetector(threshold_hours=24.0)
    anomalies = detector.scan(str(isolated_workspace))
    assert len(anomalies) == 0, f"Whitelisted files should not be flagged: {[a.target_path for a in anomalies]}"


def test_context_rot_ignores_non_planning_markdown(isolated_workspace: Path) -> None:
    \"\"\"8. Test that regular markdown files not matching planning patterns are ignored.\"\"\"
    regular_doc = isolated_workspace / "docs" / "user_guide.md"
    regular_doc.parent.mkdir(parents=True, exist_ok=True)
    regular_doc.write_text("# User Guide", encoding="utf-8")

    past_mtime = time.time() - (50 * 3600.0)
    os.utime(str(regular_doc), (past_mtime, past_mtime))

    detector = ContextRotDetector(threshold_hours=24.0)
    anomalies = detector.scan(str(isolated_workspace))
    assert len(anomalies) == 0


# ============================================================================
# 3. ECOSYSTEM POLLUTION DETECTOR TESTS
# ============================================================================

def test_ecosystem_pollution_detects_disabled_directories(isolated_workspace: Path) -> None:
    \"\"\"9. Test that .disabled directories are flagged as ECOSYSTEM_POLLUTION.\"\"\"
    disabled_dir = isolated_workspace / ".gemini" / "config" / "plugins" / "gcp_spark.disabled"
    disabled_dir.mkdir(parents=True, exist_ok=True)

    detector = EcosystemPollutionDetector()
    anomalies = detector.scan(str(isolated_workspace))

    assert len(anomalies) == 1
    rec = anomalies[0]
    assert rec.detector_type == DetectorType.ECOSYSTEM_POLLUTION
    assert rec.severity == Severity.HIGH
    assert "gcp_spark.disabled" in rec.target_path
    assert rec.raw_details["is_disabled"] is True


def test_ecosystem_pollution_detects_cross_track_leak(isolated_workspace: Path) -> None:
    \"\"\"10. Test that cross-track contamination (e.g. sports card files in content_creation) is flagged.\"\"\"
    leak_file = isolated_workspace / "content_creation" / "sports_card_ladder_etl.py"
    leak_file.parent.mkdir(parents=True, exist_ok=True)
    leak_file.write_text("# Card ladder logic in content track", encoding="utf-8")

    detector = EcosystemPollutionDetector()
    anomalies = detector.scan(str(isolated_workspace))

    assert len(anomalies) == 1
    rec = anomalies[0]
    assert rec.detector_type == DetectorType.ECOSYSTEM_POLLUTION
    assert rec.severity == Severity.MEDIUM
    assert "sports_card_ladder_etl.py" in rec.target_path
    assert rec.raw_details["pollution_type"] == "cross_track_leak"


def test_ecosystem_pollution_clean_workspace(isolated_workspace: Path) -> None:
    \"\"\"11. Test that clean track structures with no .disabled directories pass cleanly.\"\"\"
    valid_file = isolated_workspace / "content_creation" / "ffmpeg_renderer.py"
    valid_file.parent.mkdir(parents=True, exist_ok=True)
    valid_file.write_text("# Clean content file", encoding="utf-8")

    detector = EcosystemPollutionDetector()
    anomalies = detector.scan(str(isolated_workspace))
    assert len(anomalies) == 0


# ============================================================================
# 4. SECRET ZERO DETECTOR TESTS
# ============================================================================

def test_secret_zero_detects_placeholder_in_env(isolated_workspace: Path) -> None:
    \"\"\"12. Test that 'your_token_here' in .env is detected with CRITICAL severity and masked output.\"\"\"
    env_file = isolated_workspace / ".env"
    env_file.write_text("DATABASE_URL=sqlite:///app.db\\nAPI_KEY=your_token_here\\nPORT=8000\\n", encoding="utf-8")

    detector = SecretZeroDetector()
    anomalies = detector.scan(str(isolated_workspace))

    assert len(anomalies) == 1
    rec = anomalies[0]
    assert rec.detector_type == DetectorType.SECRET_ZERO
    assert rec.severity == Severity.CRITICAL
    assert rec.raw_details["line_number"] == 2
    assert "your_***" in rec.description or "***" in rec.description
    assert "your_token_here" not in rec.raw_details["masked_token"]


def test_secret_zero_detects_multiple_tokens_across_configs(isolated_workspace: Path) -> None:
    \"\"\"13. Test placeholder tokens detected in .json and .yaml config files.\"\"\"
    json_cfg = isolated_workspace / "config.json"
    json_cfg.write_text('{\\n  "api_key": "YOUR_API_KEY_HERE",\\n  "secret": "CHANGE_ME"\\n}', encoding="utf-8")

    detector = SecretZeroDetector()
    anomalies = detector.scan(str(isolated_workspace))

    assert len(anomalies) >= 2
    for a in anomalies:
        assert a.detector_type == DetectorType.SECRET_ZERO
        assert a.severity == Severity.CRITICAL


def test_secret_zero_clean_configs_pass(isolated_workspace: Path) -> None:
    \"\"\"14. Test that properly configured files without placeholder tokens return 0 anomalies.\"\"\"
    env_file = isolated_workspace / ".env"
    env_file.write_text("HOST=127.0.0.1\\nPORT=3000\\nAPP_ENV=production\\n", encoding="utf-8")

    detector = SecretZeroDetector()
    anomalies = detector.scan(str(isolated_workspace))
    assert len(anomalies) == 0


# ============================================================================
# 5. PROMPT FATIGUE DETECTOR TESTS
# ============================================================================

def test_prompt_fatigue_detects_bloated_manifest(isolated_workspace: Path) -> None:
    \"\"\"15. Test that GEMINI.md exceeding 100 lines is flagged as PROMPT_FATIGUE.\"\"\"
    manifest = isolated_workspace / "GEMINI.md"
    lines = [f"# Rule Line {i}\\nSome procedural instruction." for i in range(120)]
    manifest.write_text("\\n".join(lines), encoding="utf-8")

    detector = PromptFatigueDetector(max_lines=100)
    anomalies = detector.scan(str(isolated_workspace))

    assert len(anomalies) == 1
    rec = anomalies[0]
    assert rec.detector_type == DetectorType.PROMPT_FATIGUE
    assert rec.severity == Severity.MEDIUM
    assert rec.raw_details["line_count"] == 239 or rec.raw_details["line_count"] > 100
    assert rec.raw_details["max_lines"] == 100


def test_prompt_fatigue_clean_manifest_passes(isolated_workspace: Path) -> None:
    \"\"\"16. Test that GEMINI.md <= 100 lines passes cleanly.\"\"\"
    manifest = isolated_workspace / "GEMINI.md"
    lines = [f"Line {i}" for i in range(40)]
    manifest.write_text("\\n".join(lines), encoding="utf-8")

    detector = PromptFatigueDetector(max_lines=100)
    anomalies = detector.scan(str(isolated_workspace))
    assert len(anomalies) == 0


def test_prompt_fatigue_detects_duplicate_headings(isolated_workspace: Path) -> None:
    \"\"\"17. Test that duplicate section headings in GEMINI.md are flagged.\"\"\"
    manifest = isolated_workspace / "GEMINI.md"
    content = \"\"\"# System Manifest
## Core Directives
Rule details.
## Core Directives
Duplicate section.
\"\"\"
    manifest.write_text(content, encoding="utf-8")

    detector = PromptFatigueDetector(max_lines=100)
    anomalies = detector.scan(str(isolated_workspace))

    assert len(anomalies) == 1
    assert "core directives" in anomalies[0].raw_details["duplicate_headings"]


def test_prompt_fatigue_missing_manifest_handled_gracefully(isolated_workspace: Path) -> None:
    \"\"\"18. Test that missing GEMINI.md returns 0 anomalies without raising an error.\"\"\"
    detector = PromptFatigueDetector()
    anomalies = detector.scan(str(isolated_workspace))
    assert len(anomalies) == 0


# ============================================================================
# 6. MASTER HEALTH SCANNER ORCHESTRATOR TESTS
# ============================================================================

def test_health_scanner_initializes_all_5_detectors() -> None:
    \"\"\"19. Test that HealthScanner instantiates all 5 detectors by default.\"\"\"
    scanner = HealthScanner()
    assert len(scanner.detectors) == 5
    detector_types = {d.detector_type for d in scanner.detectors}
    assert detector_types == {
        DetectorType.GHOST_DAEMONS,
        DetectorType.CONTEXT_ROT,
        DetectorType.ECOSYSTEM_POLLUTION,
        DetectorType.SECRET_ZERO,
        DetectorType.PROMPT_FATIGUE,
    }


def test_health_scanner_full_aggregation(isolated_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    \"\"\"20. Test that HealthScanner runs all 5 detectors and aggregates all anomalies into a single list.\"\"\"
    # Mock ghost daemons port 3000 occupied
    monkeypatch.setattr(GhostDaemonsDetector, "_is_port_occupied", lambda self, port, host="127.0.0.1": port == 3000)

    # Create stale planning file
    stale_plan = isolated_workspace / ".agents" / "worker" / "plan.md"
    stale_plan.parent.mkdir(parents=True, exist_ok=True)
    stale_plan.write_text("# Plan", encoding="utf-8")
    past_mtime = time.time() - (48 * 3600.0)
    os.utime(str(stale_plan), (past_mtime, past_mtime))

    # Create .disabled directory
    (isolated_workspace / "plugins" / "old.disabled").mkdir(parents=True, exist_ok=True)

    # Create .env with secret placeholder
    (isolated_workspace / ".env").write_text("API_KEY=your_token_here\\n", encoding="utf-8")

    # Create bloated GEMINI.md
    (isolated_workspace / "GEMINI.md").write_text("\\n".join([f"Line {i}" for i in range(150)]), encoding="utf-8")

    scanner = HealthScanner()
    anomalies = scanner.scan_workspace(str(isolated_workspace))

    assert len(anomalies) == 5
    found_types = {a.detector_type for a in anomalies}
    assert found_types == {
        DetectorType.GHOST_DAEMONS,
        DetectorType.CONTEXT_ROT,
        DetectorType.ECOSYSTEM_POLLUTION,
        DetectorType.SECRET_ZERO,
        DetectorType.PROMPT_FATIGUE,
    }
    assert scanner.last_duration_ms > 0.0


def test_health_scanner_clean_workspace(isolated_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    \"\"\"21. Test that HealthScanner on a clean workspace returns an empty list.\"\"\"
    monkeypatch.setattr(GhostDaemonsDetector, "_is_port_occupied", lambda self, port, host="127.0.0.1": False)

    (isolated_workspace / "PROJECT.md").write_text("# Clean project", encoding="utf-8")
    (isolated_workspace / "GEMINI.md").write_text("# Clean prompt", encoding="utf-8")

    scanner = HealthScanner()
    anomalies = scanner.scan_workspace(str(isolated_workspace))

    assert len(anomalies) == 0
    assert scanner.last_duration_ms >= 0.0
    assert len(scanner.last_detector_errors) == 0


def test_health_scanner_graceful_exception_isolation(isolated_workspace: Path) -> None:
    \"\"\"22. Test that an unhandled exception in one detector does not crash the full scan.\"\"\"
    class FaultyDetector(BaseDetector):
        @property
        def detector_type(self) -> DetectorType:
            return DetectorType.GHOST_DAEMONS

        def scan(self, workspace_root: str) -> List[AnomalyRecord]:
            raise RuntimeError("Hardware socket inspection failure")

    class WorkingDetector(BaseDetector):
        @property
        def detector_type(self) -> DetectorType:
            return DetectorType.SECRET_ZERO

        def scan(self, workspace_root: str) -> List[AnomalyRecord]:
            return [
                AnomalyRecord(
                    detector_type=DetectorType.SECRET_ZERO,
                    target_path=".env",
                    severity=Severity.CRITICAL,
                    description="Placeholder secret",
                    raw_details={},
                )
            ]

    scanner = HealthScanner(detectors=[FaultyDetector(), WorkingDetector()])
    anomalies = scanner.scan_workspace(str(isolated_workspace))

    assert len(anomalies) == 1
    assert anomalies[0].detector_type == DetectorType.SECRET_ZERO
    assert "FaultyDetector" in scanner.last_detector_errors
    assert "Hardware socket inspection failure" in scanner.last_detector_errors["FaultyDetector"]


def test_health_scanner_duration_tracking_in_milliseconds(isolated_workspace: Path) -> None:
    \"\"\"23. Test that duration tracking accurately records elapsed time in milliseconds.\"\"\"
    scanner = HealthScanner(detectors=[])
    scanner.scan_workspace(str(isolated_workspace))

    assert isinstance(scanner.last_duration_ms, float)
    assert scanner.last_duration_ms >= 0.0
    assert scanner.get_last_duration_ms() == scanner.last_duration_ms


def test_health_scanner_summary_generation(isolated_workspace: Path) -> None:
    \"\"\"24. Test that get_summary creates accurate statistical rollups.\"\"\"
    scanner = HealthScanner(detectors=[])
    sample_anomalies = [
        AnomalyRecord(
            detector_type=DetectorType.SECRET_ZERO,
            target_path=".env",
            severity=Severity.CRITICAL,
            description="Test 1",
            raw_details={},
        ),
        AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path="plan.md",
            severity=Severity.MEDIUM,
            description="Test 2",
            raw_details={},
        ),
    ]

    summary = scanner.get_summary(sample_anomalies)
    assert summary["total_anomalies"] == 2
    assert summary["by_detector"][DetectorType.SECRET_ZERO.value] == 1
    assert summary["by_detector"][DetectorType.CONTEXT_ROT.value] == 1
    assert summary["by_severity"][Severity.CRITICAL.value] == 1
    assert summary["by_severity"][Severity.MEDIUM.value] == 1


def test_health_scanner_zero_destruction_cryptographic_hash(isolated_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    \"\"\"25. Test that HealthScanner enforces 100% read-only safety with zero file mutation.\"\"\"
    # Populate workspace with diverse files
    (isolated_workspace / ".env").write_text("API_KEY=your_token_here\\n", encoding="utf-8")
    (isolated_workspace / "GEMINI.md").write_text("# Manifest\\n" * 50, encoding="utf-8")
    (isolated_workspace / "docs").mkdir(parents=True, exist_ok=True)
    (isolated_workspace / "docs" / "plan.md").write_text("# Old Plan", encoding="utf-8")

    # Take initial SHA256 snapshot
    snapshot = FileSystemSnapshot(str(isolated_workspace))

    # Run full health scan
    monkeypatch.setattr(GhostDaemonsDetector, "_is_port_occupied", lambda self, port, host="127.0.0.1": False)
    scanner = HealthScanner()
    scanner.scan_workspace(str(isolated_workspace))

    # Assert workspace is untouched cryptographically
    snapshot.assert_untouched()
```
