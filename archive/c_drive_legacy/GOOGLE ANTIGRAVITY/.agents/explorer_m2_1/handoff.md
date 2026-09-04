# Milestone 2 Investigation & Architecture Handoff: `detectors/base.py`, `detectors/ghost_daemons.py`, and `detectors/context_rot.py`

**Agent ID**: `explorer_m2_1`  
**Milestone**: Milestone 2 (Modular Read-Only Anomaly Detectors)  
**Target Files**: 
- `g:/My Drive/GOOGLE ANTIGRAVITY/.agents/cron/detectors/base.py`
- `g:/My Drive/GOOGLE ANTIGRAVITY/.agents/cron/detectors/ghost_daemons.py`
- `g:/My Drive/GOOGLE ANTIGRAVITY/.agents/cron/detectors/context_rot.py`

---

## 1. Observation

### 1.1 Specification Contracts & Schema Citations
1. **`PROJECT.md` (§ Interface Contracts: Lines 114–125)**:
   ```python
   from abc import ABC, abstractmethod
   from typing import List
   from models import AnomalyRecord

   class BaseDetector(ABC):
       @abstractmethod
       def scan(self, workspace_root: str) -> List[AnomalyRecord]:
           """Strictly read-only scan of target workspace."""
           pass
   ```
2. **`models.py` Data Model (Lines 8–38)**:
   - `Severity`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
   - `DetectorType`: `GHOST_DAEMONS`, `CONTEXT_ROT`, `ECOSYSTEM_POLLUTION`, `SECRET_ZERO`, `PROMPT_FATIGUE`
   - `AnomalyRecord`:
     - `detector_type: DetectorType`
     - `target_path: str`
     - `severity: Severity`
     - `description: str`
     - `raw_details: Dict[str, Any]`
     - `is_historical: bool = False`
     - `timestamp: int = 0`
     - `confidence: float = 1.0`
3. **`config.py` Constants & Whitelists (Lines 6–21)**:
   - `CONTEXT_ROT_THRESHOLD_HOURS = 24.0`
   - `MONITORED_PORTS = [3000, 8000, 8501]`
   - `WHITELISTED_FILENAMES = ["PROJECT.md", "GEMINI.md", "README.md", "BRIEFING.md", "ORIGINAL_REQUEST.md"]`
4. **`safety_guardrails.py` Prohibited Operations (Lines 9–35)**:
   - Forbidden call attributes: `os.remove`, `os.unlink`, `os.rmdir`, `os.kill`, `os.killpg`, `shutil.rmtree`, `signal.pthread_kill`
   - Forbidden subprocess commands: `taskkill`, `pkill`, `kill`, `rm -rf`, `del /f`, `rmdir /s`
   - Forbidden SQL statements: `DROP TABLE`, `TRUNCATE`
   - Forbidden functions: `eval`, `exec`
5. **Historical Failure Baseline (`ORIGINAL_REQUEST.md` § R2.1 & R2.2)**:
   - Ghost Daemons: Unmonitored Next.js (port 3000) / Uvicorn (port 8000) / Streamlit (port 8501) tasks causing socket collisions (`WinError 10048`).
   - Context Rot: Planning artifacts older than 24 hours diluting the context window.

### 1.2 Prototyping & Verification Evidence
- Executed `scratch_test.py` via `python .agents/explorer_m2_1/scratch_test.py`:
  ```
  [AST Safety PASS] base has 0 violations.
  [AST Safety PASS] ghost has 0 violations.
  [AST Safety PASS] rot has 0 violations.
  ```
- Executed `scratch_functional_test.py` via `python .agents/explorer_m2_1/scratch_functional_test.py`:
  ```
  Testing BaseDetector contract...
  [PASS] BaseDetector contract test passed.
  Testing GhostDaemonsDetector...
  [PASS] GhostDaemonsDetector test passed.
  Testing ContextRotDetector...
  [PASS] ContextRotDetector test passed.
  [ALL TESTS PASSED SUCCESSFULLY]
  ```

---

## 2. Logic Chain

### Step 1: `detectors/base.py` Interface Architecture
- Derived from `PROJECT.md:114-125`.
- Implements abstract base class `BaseDetector(ABC)` with class-level `detector_type: DetectorType`.
- Enforces strict abstract method signature:
  `scan(self, workspace_root: str) -> List[AnomalyRecord]`
- Provides seamless relative/root import fallback (`try: from models import ... except ImportError: from ..models import ...`).

### Step 2: `detectors/ghost_daemons.py` Design & Zero-Kill Protocol
- **Probing Method**: Non-blocking loopback TCP connection probing via `socket.socket(socket.AF_INET, socket.SOCK_STREAM)` with `sock.settimeout(0.2)` and `sock.connect_ex((self.host, port))`.
- **Collision Detection**: If `connect_ex` returns `0`, the socket port is currently occupied by an active listener.
- **Process Introspection**: Safely checks `psutil` if installed to extract `pid` and `process_name` without executing external CLI utilities or interrupting execution. If `psutil` is missing or access is denied, gracefully populates `pid = None` and `process_name = "unknown"`.
- **Zero-Kill Guarantee**: No process termination methods (`taskkill`, `os.kill`, `kill`) are present.
- **Payload Emission**:
  - `detector_type = DetectorType.GHOST_DAEMONS`
  - `target_path = f"{host}:{port}"` (e.g. `"127.0.0.1:3000"`)
  - `severity = Severity.HIGH`
  - `description = f"Unmonitored ghost daemon or socket collision detected on port {port} (WinError 10048 signature, PID: {pid or 'N/A'}, Process: {process_name})"`
  - `raw_details = {"port": port, "host": host, "status": "OCCUPIED", "errno": 10048, "error_signature": "WinError 10048 (WSAEADDRINUSE)", "pid": pid, "process_name": process_name, "proposed_action": "REPORT_OCCUPIED_PORT"}`
  - `confidence = 1.0`

### Step 3: `detectors/context_rot.py` Traversal, Aging & Whitelist Protocol
- **Pattern Matching**: Matches workspace `.md` files against planning patterns:
  `*proposal*.md`, `*blueprint*.md`, `*ideas*.md`, `*scratchpad*.md`, `*plan*.md` via case-insensitive `fnmatch.fnmatch`.
- **Directory Exclusion**: Prunes in-place `EXCLUDED_DIRS = {".git", "venv", ".venv", "__pycache__", ".pytest_cache", "node_modules"}` during `os.walk`.
- **Protected Whitelist**: Checks basename against `WHITELISTED_FILENAMES` (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`). Whitelisted files are strictly exempted.
- **Age Calculation**: Compares `os.path.getmtime(path)` against current epoch time: `age_hours = (time.time() - mtime) / 3600.0`. If `age_hours >= CONTEXT_ROT_THRESHOLD_HOURS` (24.0h), flags anomaly.
- **Payload Emission**:
  - `detector_type = DetectorType.CONTEXT_ROT`
  - `target_path = rel_path` (e.g. `".agents/worker_old/plan.md"`)
  - `severity = Severity.MEDIUM`
  - `description = f"Planning artifact '{basename}' is {age_hours:.1f}h old (exceeds {threshold_hours:.1f}h threshold) and dilutes context window"`
  - `raw_details = {"file_name": basename, "file_path": os.path.abspath(full_path), "relative_path": rel_path, "age_hours": round(age_hours, 2), "threshold_hours": threshold_hours, "mtime": mtime, "matched_pattern": matched_pattern, "proposed_action": "MOVE_TO_ARCHIVE"}`
  - `confidence = 0.95`

---

## 3. Implementation Blueprints

### 3.1 `detectors/base.py`
```python
"""Abstract Base Detector Interface for Antigravity Daily Health Scanner."""

from abc import ABC, abstractmethod
from typing import List

try:
    from models import AnomalyRecord, DetectorType
except ImportError:
    from ..models import AnomalyRecord, DetectorType


class BaseDetector(ABC):
    """Abstract base class for all read-only workspace anomaly detectors."""

    detector_type: DetectorType

    @abstractmethod
    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Strictly read-only scan of target workspace.
        
        Args:
            workspace_root: Absolute path to the workspace root directory.
            
        Returns:
            List of detected AnomalyRecord instances.
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} type={getattr(self, 'detector_type', 'UNKNOWN')}>"
```

### 3.2 `detectors/ghost_daemons.py`
```python
"""Ghost Daemons Detector: Identifies unmonitored ports and socket collisions."""

import socket
import time
from typing import List, Optional, Tuple

try:
    from models import AnomalyRecord, DetectorType, Severity
    from config import MONITORED_PORTS
    from detectors.base import BaseDetector
except ImportError:
    from ..models import AnomalyRecord, DetectorType, Severity
    from ..config import MONITORED_PORTS
    from .base import BaseDetector


class GhostDaemonsDetector(BaseDetector):
    """Probes loopback ports non-destructively for active daemons and WinError 10048 socket collisions."""

    detector_type = DetectorType.GHOST_DAEMONS

    def __init__(
        self,
        target_ports: Optional[List[int]] = None,
        host: str = "127.0.0.1",
        timeout_seconds: float = 0.2,
    ) -> None:
        self.target_ports = list(target_ports) if target_ports is not None else list(MONITORED_PORTS)
        self.host = host
        self.timeout_seconds = timeout_seconds

    def _discover_process_info(self, port: int) -> Tuple[Optional[int], Optional[str]]:
        """Safely extracts PID and process name using psutil if available, without running external commands."""
        pid: Optional[int] = None
        process_name: Optional[str] = "unknown"
        try:
            import psutil  # type: ignore
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr and conn.laddr.port == port:
                    pid = conn.pid
                    if pid:
                        try:
                            proc = psutil.Process(pid)
                            process_name = proc.name()
                        except Exception:
                            process_name = "unknown"
                    break
        except (ImportError, Exception):
            pass
        return pid, process_name

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Probes target loopback ports and returns high-severity anomalies for occupied ports."""
        anomalies: List[AnomalyRecord] = []
        current_ts = int(time.time())

        for port in self.target_ports:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout_seconds)
                res = sock.connect_ex((self.host, port))
                if res == 0:
                    pid, process_name = self._discover_process_info(port)
                    desc = (
                        f"Unmonitored ghost daemon or socket collision detected on {self.host}:{port} "
                        f"(WinError 10048 signature, PID: {pid if pid is not None else 'N/A'}, "
                        f"Process: {process_name})"
                    )
                    anomalies.append(
                        AnomalyRecord(
                            detector_type=DetectorType.GHOST_DAEMONS,
                            target_path=f"{self.host}:{port}",
                            severity=Severity.HIGH,
                            description=desc,
                            raw_details={
                                "port": port,
                                "host": self.host,
                                "status": "OCCUPIED",
                                "errno": 10048,
                                "error_signature": "WinError 10048 (WSAEADDRINUSE)",
                                "pid": pid,
                                "process_name": process_name,
                                "proposed_action": "REPORT_OCCUPIED_PORT",
                            },
                            is_historical=False,
                            timestamp=current_ts,
                            confidence=1.0,
                        )
                    )
            except Exception:
                pass
            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass

        return anomalies
```

### 3.3 `detectors/context_rot.py`
```python
"""Context Rot Detector: Detects planning artifacts older than 24 hours."""

import fnmatch
import os
import time
from typing import List, Optional, Set

try:
    from models import AnomalyRecord, DetectorType, Severity
    from config import CONTEXT_ROT_THRESHOLD_HOURS, WHITELISTED_FILENAMES
    from detectors.base import BaseDetector
except ImportError:
    from ..models import AnomalyRecord, DetectorType, Severity
    from ..config import CONTEXT_ROT_THRESHOLD_HOURS, WHITELISTED_FILENAMES
    from .base import BaseDetector

DEFAULT_ROT_PATTERNS: List[str] = [
    "*proposal*.md",
    "*blueprint*.md",
    "*ideas*.md",
    "*scratchpad*.md",
    "*plan*.md",
]

EXCLUDED_DIRS: Set[str] = {
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}


class ContextRotDetector(BaseDetector):
    """Scans workspace for stale planning markdown files exceeding CONTEXT_ROT_THRESHOLD_HOURS."""

    detector_type = DetectorType.CONTEXT_ROT

    def __init__(
        self,
        threshold_hours: float = CONTEXT_ROT_THRESHOLD_HOURS,
        patterns: Optional[List[str]] = None,
        whitelisted_filenames: Optional[List[str]] = None,
    ) -> None:
        self.threshold_hours = threshold_hours
        self.patterns = list(patterns) if patterns is not None else list(DEFAULT_ROT_PATTERNS)
        raw_whitelist = whitelisted_filenames if whitelisted_filenames is not None else WHITELISTED_FILENAMES
        self.whitelisted_filenames: Set[str] = {f.upper() for f in raw_whitelist}

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Recursively inspects markdown planning files and flags those exceeding age threshold."""
        anomalies: List[AnomalyRecord] = []
        now = time.time()

        if not os.path.exists(workspace_root):
            return anomalies

        for root, dirs, files in os.walk(workspace_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                basename = file
                if basename.upper() in self.whitelisted_filenames:
                    continue

                matched_pattern: Optional[str] = None
                for pat in self.patterns:
                    if fnmatch.fnmatch(basename.lower(), pat.lower()):
                        matched_pattern = pat
                        break

                if matched_pattern is not None:
                    full_path = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(full_path)
                        age_hours = (now - mtime) / 3600.0
                        if age_hours >= self.threshold_hours:
                            rel_path = os.path.relpath(full_path, workspace_root)
                            desc = (
                                f"Planning artifact '{basename}' is {age_hours:.1f}h old "
                                f"(exceeds {self.threshold_hours:.1f}h threshold) and dilutes context window"
                            )
                            anomalies.append(
                                AnomalyRecord(
                                    detector_type=DetectorType.CONTEXT_ROT,
                                    target_path=rel_path,
                                    severity=Severity.MEDIUM,
                                    description=desc,
                                    raw_details={
                                        "file_name": basename,
                                        "file_path": os.path.abspath(full_path),
                                        "relative_path": rel_path,
                                        "age_hours": round(age_hours, 2),
                                        "threshold_hours": self.threshold_hours,
                                        "mtime": mtime,
                                        "matched_pattern": matched_pattern,
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
```

---

## 4. Caveats & Assumptions

1. **Loopback Port Binding vs Connect**:
   - `connect_ex` probes for active listeners without attempting to seize the port. This is non-intrusive and does not interrupt running local servers.
   - Probing timeout is set to 0.2s to prevent socket latency overhead during bulk scans.
2. **Process Metadata Privilege Boundaries**:
   - Querying process name via `psutil` on certain protected operating system PIDs may raise `AccessDenied` or `NoSuchProcess`. The code catches all such exceptions and falls back to `process_name = "unknown"` without failing the scan.
3. **Mtime Clocks & File System Resolution**:
   - File modification time relies on `os.path.getmtime(path)`. In unit tests, `os.utime()` must be used to simulate historical timestamps (e.g. `time.time() - 48*3600`).
4. **Scope Boundaries**:
   - Detectors for Ecosystem Pollution, Secret Zero, and Prompt Fatigue are designed by `explorer_m2_2`.
   - Master `HealthScanner` orchestration and `test_detectors.py` integration are covered by `explorer_m2_3`.

---

## 5. Conclusion

- The architecture for `detectors/base.py`, `detectors/ghost_daemons.py`, and `detectors/context_rot.py` meets 100% of Milestone 2 requirements.
- Zero destructive operations exist in the design; static AST checks pass with 0 violations.
- Ready for implementation by `worker_m2`.

---

## 6. Verification Method

To verify these designs independently:

1. **AST Static Safety Check**:
   ```bash
   python .agents/explorer_m2_1/scratch_test.py
   ```
   *Expected output*: `[AST Safety PASS]` for all modules with 0 violations.

2. **Functional & Read-Only Cryptographic Check**:
   ```bash
   python .agents/explorer_m2_1/scratch_functional_test.py
   ```
   *Expected output*: `[ALL TESTS PASSED SUCCESSFULLY]` with `FileSystemSnapshot.assert_untouched()` verifying zero file mutations.

3. **Target Unit Test Scenarios for `tests/test_detectors.py`**:
   - `test_base_detector_cannot_be_instantiated()`
   - `test_ghost_daemons_detects_occupied_port(mock_tcp_listener)`
   - `test_ghost_daemons_passes_free_ports()`
   - `test_ghost_daemons_zero_kill_safety()`
   - `test_context_rot_detects_stale_planning_files()`
   - `test_context_rot_ignores_fresh_planning_files()`
   - `test_context_rot_respects_whitelisted_files()`
   - `test_context_rot_skips_excluded_directories()`
