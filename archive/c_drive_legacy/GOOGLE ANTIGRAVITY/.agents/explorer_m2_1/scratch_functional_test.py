"""Functional and edge-case verification for BaseDetector, GhostDaemonsDetector, and ContextRotDetector."""

import os
import sys
import time
import socket
import fnmatch
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Set

# Add cron dir to sys.path
cron_dir = Path(__file__).resolve().parent.parent / "cron"
if str(cron_dir) not in sys.path:
    sys.path.insert(0, str(cron_dir))

from tests.conftest import FileSystemSnapshot
from models import AnomalyRecord, DetectorType, Severity
from config import CONTEXT_ROT_THRESHOLD_HOURS, WHITELISTED_FILENAMES, MONITORED_PORTS


class BaseDetector(ABC):
    """Abstract base class for all read-only anomaly detectors."""

    detector_type: DetectorType

    @abstractmethod
    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Strictly read-only scan of target workspace."""
        pass


class GhostDaemonsDetector(BaseDetector):
    """Detects unmonitored background tasks and socket collisions on target ports."""

    detector_type = DetectorType.GHOST_DAEMONS

    def __init__(
        self,
        target_ports: Optional[List[int]] = None,
        host: str = "127.0.0.1",
        timeout_seconds: float = 0.2,
    ):
        self.target_ports = target_ports or list(MONITORED_PORTS)
        self.host = host
        self.timeout_seconds = timeout_seconds

    def _discover_process_info(self, port: int) -> tuple[Optional[int], Optional[str]]:
        """Safely discovers PID and process name for an occupied port without executing destructive commands."""
        pid = None
        process_name = "unknown"
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
        """Scans loopback ports non-destructively for active listeners / collisions."""
        anomalies: List[AnomalyRecord] = []
        for port in self.target_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout_seconds)
                res = sock.connect_ex((self.host, port))
                sock.close()
                if res == 0:
                    pid, process_name = self._discover_process_info(port)
                    desc = (
                        f"Unmonitored ghost daemon or socket collision detected on port {port} "
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
                            timestamp=int(time.time()),
                            confidence=1.0,
                        )
                    )
            except Exception:
                pass
        return anomalies


DEFAULT_ROT_PATTERNS = [
    "*proposal*.md",
    "*blueprint*.md",
    "*ideas*.md",
    "*scratchpad*.md",
    "*plan*.md",
]

EXCLUDED_DIRS = {".git", "venv", ".venv", "__pycache__", ".pytest_cache", "node_modules"}


class ContextRotDetector(BaseDetector):
    """Detects stale planning artifacts (>24h old) diluting workspace context."""

    detector_type = DetectorType.CONTEXT_ROT

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
        """Recursively scans workspace for stale planning markdown artifacts."""
        anomalies: List[AnomalyRecord] = []
        now = time.time()

        if not os.path.exists(workspace_root):
            return anomalies

        for root, dirs, files in os.walk(workspace_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                basename = file
                # Check whitelist protection
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


def test_base_detector_contract():
    print("Testing BaseDetector contract...")
    try:
        b = BaseDetector()
        assert False, "Should not be able to instantiate abstract BaseDetector"
    except TypeError:
        pass

    class DummyDetector(BaseDetector):
        detector_type = DetectorType.GHOST_DAEMONS
        def scan(self, workspace_root: str):
            return []

    d = DummyDetector()
    assert isinstance(d, BaseDetector)
    assert d.scan("dummy") == []
    print("[PASS] BaseDetector contract test passed.")


def test_ghost_daemons_detector():
    print("Testing GhostDaemonsDetector...")
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    free_port = port + 100
    detector = GhostDaemonsDetector(target_ports=[port, free_port], host="127.0.0.1")
    
    anomalies = detector.scan("mock_ws")
    
    server_sock.close()

    assert len(anomalies) == 1, f"Expected 1 anomaly for occupied port, got {len(anomalies)}"
    anom = anomalies[0]
    assert anom.detector_type == DetectorType.GHOST_DAEMONS
    assert anom.severity == Severity.HIGH
    assert anom.target_path == f"127.0.0.1:{port}"
    assert anom.raw_details["port"] == port
    assert anom.raw_details["status"] == "OCCUPIED"
    assert anom.raw_details["errno"] == 10048
    assert anom.raw_details["proposed_action"] == "REPORT_OCCUPIED_PORT"
    print("[PASS] GhostDaemonsDetector test passed.")


def test_context_rot_detector(tmp_path: Path):
    print("Testing ContextRotDetector...")
    ws = tmp_path / "mock_workspace"
    ws.mkdir(parents=True, exist_ok=True)

    # 1. Stale planning artifact (> 24h old)
    stale_plan = ws / "migration_plan.md"
    stale_plan.write_text("# Old Plan", encoding="utf-8")
    old_time = time.time() - (48 * 3600)  # 48 hours ago
    os.utime(str(stale_plan), (old_time, old_time))

    # 2. Fresh planning artifact (< 24h old)
    fresh_plan = ws / "new_blueprint.md"
    fresh_plan.write_text("# Fresh Blueprint", encoding="utf-8")
    fresh_time = time.time() - (2 * 3600)  # 2 hours ago
    os.utime(str(fresh_plan), (fresh_time, fresh_time))

    # 3. Whitelisted file that matches pattern or is old (e.g. PROJECT.md, GEMINI.md)
    whitelisted_proj = ws / "PROJECT.md"
    whitelisted_proj.write_text("# Project Spec", encoding="utf-8")
    os.utime(str(whitelisted_proj), (old_time, old_time))

    whitelisted_gemini = ws / "GEMINI.md"
    whitelisted_gemini.write_text("# Gemini Manifest", encoding="utf-8")
    os.utime(str(whitelisted_gemini), (old_time, old_time))

    whitelisted_briefing = ws / "BRIEFING.md"
    whitelisted_briefing.write_text("# Briefing", encoding="utf-8")
    os.utime(str(whitelisted_briefing), (old_time, old_time))

    # 4. Stale ideas file in nested subdirectory
    nested_dir = ws / "subdir" / "ideas"
    nested_dir.mkdir(parents=True, exist_ok=True)
    nested_stale = nested_dir / "draft_ideas_v1.md"
    nested_stale.write_text("# Draft Ideas", encoding="utf-8")
    os.utime(str(nested_stale), (old_time, old_time))

    # 5. Non-planning markdown file that is stale (e.g. general documentation)
    stale_docs = ws / "changelog.md"
    stale_docs.write_text("# Changelog", encoding="utf-8")
    os.utime(str(stale_docs), (old_time, old_time))

    # Snapshot to ensure read-only
    snapshot = FileSystemSnapshot(str(ws))

    detector = ContextRotDetector(threshold_hours=24.0)
    anomalies = detector.scan(str(ws))

    # Assert filesystem untouched
    snapshot.assert_untouched()

    # We expect exactly 2 anomalies: migration_plan.md and draft_ideas_v1.md
    assert len(anomalies) == 2, f"Expected 2 anomalies, found {len(anomalies)}: {[a.target_path for a in anomalies]}"
    
    target_paths = {a.target_path.replace("\\", "/") for a in anomalies}
    assert "migration_plan.md" in target_paths
    assert "subdir/ideas/draft_ideas_v1.md" in target_paths

    for anom in anomalies:
        assert anom.detector_type == DetectorType.CONTEXT_ROT
        assert anom.severity == Severity.MEDIUM
        assert anom.raw_details["age_hours"] >= 24.0
        assert anom.raw_details["proposed_action"] == "MOVE_TO_ARCHIVE"
        assert anom.confidence == 0.95

    print("[PASS] ContextRotDetector test passed.")


if __name__ == "__main__":
    test_base_detector_contract()
    test_ghost_daemons_detector()
    
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_context_rot_detector(Path(td))
    print("[ALL TESTS PASSED SUCCESSFULLY]")
