"""
Data models and contracts for Antigravity Daily Health Scanner & ML Optimization Daemon.
Pure Python dataclasses with zero external dependencies, full JSON serialization,
and strict typing for SQLite telemetry, anomaly detection, ML clustering, and Red-Team auditing.
"""

from dataclasses import dataclass, field
from enum import Enum
import json
import time
from typing import Any, Dict, List, Optional, Union


class Severity(str, Enum):
    """Anomaly severity classification level."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    def __str__(self) -> str:
        return self.value


class DetectorType(str, Enum):
    """The 5 modular read-only detector types aligned with historical failure lifelines."""
    GHOST_DAEMONS = "GHOST_DAEMONS"
    CONTEXT_ROT = "CONTEXT_ROT"
    ECOSYSTEM_POLLUTION = "ECOSYSTEM_POLLUTION"
    SECRET_ZERO = "SECRET_ZERO"
    PROMPT_FATIGUE = "PROMPT_FATIGUE"

    def __str__(self) -> str:
        return self.value


class RedTeamVerdict(str, Enum):
    """Adversarial Red-Team audit verdicts for proposed optimizations."""
    APPROVED = "APPROVED"
    CHALLENGED = "CHALLENGED"
    REJECTED = "REJECTED"

    def __str__(self) -> str:
        return self.value


@dataclass
class AnomalyRecord:
    """Represents a single detected system health anomaly or seeded historical lifeline."""
    detector_type: DetectorType
    target_path: str
    severity: Severity
    description: str
    raw_details: Dict[str, Any] = field(default_factory=dict)
    is_historical: bool = False
    timestamp: int = field(default_factory=lambda: int(time.time()))
    confidence: float = 1.0

    def __post_init__(self):
        # Type coercion for enum strings
        if isinstance(self.detector_type, str) and not isinstance(self.detector_type, DetectorType):
            self.detector_type = DetectorType(self.detector_type)
        if isinstance(self.severity, str) and not isinstance(self.severity, Severity):
            self.severity = Severity(self.severity)
        if isinstance(self.raw_details, str):
            try:
                self.raw_details = json.loads(self.raw_details)
            except Exception:
                self.raw_details = {"raw": self.raw_details}
        if self.confidence < 0.0:
            self.confidence = 0.0
        elif self.confidence > 1.0:
            self.confidence = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to a JSON-serializable dictionary."""
        return {
            "detector_type": self.detector_type.value if isinstance(self.detector_type, DetectorType) else str(self.detector_type),
            "target_path": str(self.target_path),
            "severity": self.severity.value if isinstance(self.severity, Severity) else str(self.severity),
            "description": str(self.description),
            "raw_details": self.raw_details if isinstance(self.raw_details, dict) else {},
            "is_historical": bool(self.is_historical),
            "timestamp": int(self.timestamp),
            "confidence": float(self.confidence),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnomalyRecord":
        """Reconstruct AnomalyRecord from dictionary data."""
        det_type = data.get("detector_type", DetectorType.CONTEXT_ROT)
        if isinstance(det_type, str):
            det_type = DetectorType(det_type)
        
        sev = data.get("severity", Severity.MEDIUM)
        if isinstance(sev, str):
            sev = Severity(sev)

        raw = data.get("raw_details", {})
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {"raw": raw}

        return cls(
            detector_type=det_type,
            target_path=str(data.get("target_path", "")),
            severity=sev,
            description=str(data.get("description", "")),
            raw_details=raw if isinstance(raw, dict) else {},
            is_historical=bool(data.get("is_historical", False)),
            timestamp=int(data.get("timestamp", int(time.time()))),
            confidence=float(data.get("confidence", 1.0)),
        )


@dataclass
class RedTeamAuditResult:
    """Adversarial evaluation result for a detected anomaly."""
    anomaly: AnomalyRecord
    verdict: RedTeamVerdict
    rationale: str
    risk_assessment: str
    recommended_action: str

    def __post_init__(self):
        if isinstance(self.verdict, str) and not isinstance(self.verdict, RedTeamVerdict):
            self.verdict = RedTeamVerdict(self.verdict)
        if isinstance(self.anomaly, dict):
            self.anomaly = AnomalyRecord.from_dict(self.anomaly)

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit result to dictionary format."""
        return {
            "anomaly": self.anomaly.to_dict(),
            "verdict": self.verdict.value if isinstance(self.verdict, RedTeamVerdict) else str(self.verdict),
            "rationale": str(self.rationale),
            "risk_assessment": str(self.risk_assessment),
            "recommended_action": str(self.recommended_action),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedTeamAuditResult":
        """Reconstruct RedTeamAuditResult from dictionary data."""
        raw_anomaly = data.get("anomaly", {})
        anomaly_obj = AnomalyRecord.from_dict(raw_anomaly) if isinstance(raw_anomaly, dict) else raw_anomaly

        v = data.get("verdict", RedTeamVerdict.APPROVED)
        if isinstance(v, str):
            v = RedTeamVerdict(v)

        return cls(
            anomaly=anomaly_obj,
            verdict=v,
            rationale=str(data.get("rationale", "")),
            risk_assessment=str(data.get("risk_assessment", "")),
            recommended_action=str(data.get("recommended_action", "")),
        )


@dataclass
class OptimizationReport:
    """Structured end-of-run optimization and health report."""
    session_id: str
    timestamp: int = field(default_factory=lambda: int(time.time()))
    duration_ms: float = 0.0
    total_anomalies: int = 0
    approved_count: int = 0
    challenged_count: int = 0
    audited_anomalies: List[RedTeamAuditResult] = field(default_factory=list)
    textual_gradients: List[str] = field(default_factory=list)
    entropy_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary format."""
        return {
            "session_id": str(self.session_id),
            "timestamp": int(self.timestamp),
            "duration_ms": float(self.duration_ms),
            "total_anomalies": int(self.total_anomalies),
            "approved_count": int(self.approved_count),
            "challenged_count": int(self.challenged_count),
            "audited_anomalies": [a.to_dict() for a in self.audited_anomalies],
            "textual_gradients": list(self.textual_gradients),
            "entropy_score": float(self.entropy_score),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OptimizationReport":
        """Reconstruct OptimizationReport from dictionary data."""
        audited_raw = data.get("audited_anomalies", [])
        audited_list = [
            RedTeamAuditResult.from_dict(item) if isinstance(item, dict) else item
            for item in audited_raw
        ]

        return cls(
            session_id=str(data.get("session_id", "")),
            timestamp=int(data.get("timestamp", int(time.time()))),
            duration_ms=float(data.get("duration_ms", 0.0)),
            total_anomalies=int(data.get("total_anomalies", len(audited_list))),
            approved_count=int(data.get("approved_count", sum(1 for a in audited_list if getattr(a, 'verdict', None) == RedTeamVerdict.APPROVED))),
            challenged_count=int(data.get("challenged_count", sum(1 for a in audited_list if getattr(a, 'verdict', None) == RedTeamVerdict.CHALLENGED))),
            audited_anomalies=audited_list,
            textual_gradients=list(data.get("textual_gradients", [])),
            entropy_score=float(data.get("entropy_score", 0.0)),
        )


@dataclass
class HistoricalLifeline:
    """Historical session failure lifeline seed record."""
    lifeline_id: str
    detector_type: DetectorType
    name: str
    failure_pattern: str
    root_cause: str
    remediation_strategy: str
    severity: Severity
    target_path: str = ""
    raw_details: Dict[str, Any] = field(default_factory=dict)

    def to_anomaly_record(self) -> AnomalyRecord:
        """Convert historical lifeline to an AnomalyRecord for seeding."""
        return AnomalyRecord(
            detector_type=self.detector_type,
            target_path=self.target_path or self.name,
            severity=self.severity,
            description=f"[{self.lifeline_id}] {self.name}: {self.failure_pattern}",
            raw_details={
                "lifeline_id": self.lifeline_id,
                "root_cause": self.root_cause,
                "remediation_strategy": self.remediation_strategy,
                **self.raw_details
            },
            is_historical=True,
            confidence=1.0
        )
