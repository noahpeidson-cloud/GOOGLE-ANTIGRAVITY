"""Ghost Daemons Anomaly Detector: Non-destructive socket occupancy and collision probing."""

import socket
import time
from typing import List, Optional

try:
    from ..config import MONITORED_PORTS
    from ..models import AnomalyRecord, DetectorType, Severity
    from .base import BaseDetector
except (ImportError, ValueError):
    from config import MONITORED_PORTS
    from detectors.base import BaseDetector
    from models import AnomalyRecord, DetectorType, Severity


class GhostDaemonsDetector(BaseDetector):
    """Detects unmonitored server processes and socket collisions (WinError 10048) on standard dev ports

    via non-destructive loopback TCP probing. Strictly zero process kills.
    """

    detector_type = DetectorType.GHOST_DAEMONS

    def __init__(
        self,
        monitored_ports: Optional[List[int]] = None,
        host: str = "127.0.0.1",
        probe_timeout_s: float = 0.2,
    ) -> None:
        super().__init__(DetectorType.GHOST_DAEMONS)
        self.monitored_ports = list(monitored_ports or MONITORED_PORTS)
        self.host = host
        self.probe_timeout_s = probe_timeout_s

    def probe_port(self, port: int) -> bool:
        """Probes a specific TCP port on loopback interface non-destructively.

        Returns True if port is occupied (connection accepted), False otherwise.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.probe_timeout_s)
        try:
            res = sock.connect_ex((self.host, port))
            return res == 0
        except Exception:
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Scans configured ports on loopback interface for unmonitored daemon activity.

        Strictly read-only and non-destructive.
        """
        anomalies: List[AnomalyRecord] = []
        current_ts = int(time.time())

        for port in self.monitored_ports:
            is_occupied = self.probe_port(port)
            if is_occupied:
                record = AnomalyRecord(
                    detector_type=DetectorType.GHOST_DAEMONS,
                    target_path=f"{self.host}:{port}",
                    severity=Severity.CRITICAL,
                    description=(
                        f"Ghost daemon detected: port {port} is occupied / unmonitored on {self.host} "
                        "(potential WinError 10048 socket collision)"
                    ),
                    raw_details={
                        "host": self.host,
                        "port": port,
                        "status": "OCCUPIED",
                        "errno": 10048,
                        "signature": "WinError 10048 (WSAEADDRINUSE)",
                    },
                    is_historical=False,
                    timestamp=current_ts,
                    confidence=1.0,
                )
                anomalies.append(record)

        return anomalies
