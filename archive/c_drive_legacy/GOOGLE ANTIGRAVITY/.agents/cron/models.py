"""Data models and enums for Antigravity Daily Health Scanner & ML Daemon."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DetectorType(str, Enum):
    GHOST_DAEMONS = "GHOST_DAEMONS"
    CONTEXT_ROT = "CONTEXT_ROT"
    ECOSYSTEM_POLLUTION = "ECOSYSTEM_POLLUTION"
    SECRET_ZERO = "SECRET_ZERO"
    PROMPT_FATIGUE = "PROMPT_FATIGUE"


class RedTeamVerdict(str, Enum):
    APPROVED = "APPROVED"
    CHALLENGED = "CHALLENGED"
    REJECTED = "REJECTED"


@dataclass
class AnomalyRecord:
    detector_type: DetectorType
    target_path: str
    severity: Severity
    description: str
    raw_details: Dict[str, Any] = field(default_factory=dict)
    is_historical: bool = False
    timestamp: int = 0
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detector_type": self.detector_type.value if isinstance(self.detector_type, DetectorType) else str(self.detector_type),
            "target_path": self.target_path,
            "severity": self.severity.value if isinstance(self.severity, Severity) else str(self.severity),
            "description": self.description,
            "raw_details": dict(self.raw_details) if self.raw_details is not None else {},
            "is_historical": self.is_historical,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnomalyRecord":
        raw_type = data.get("detector_type")
        det_type = DetectorType(raw_type) if isinstance(raw_type, str) else raw_type
        raw_sev = data.get("severity")
        sev = Severity(raw_sev) if isinstance(raw_sev, str) else raw_sev
        return cls(
            detector_type=det_type,
            target_path=data.get("target_path", ""),
            severity=sev,
            description=data.get("description", ""),
            raw_details=data.get("raw_details", {}) if isinstance(data.get("raw_details"), dict) else {},
            is_historical=bool(data.get("is_historical", False)),
            timestamp=int(data.get("timestamp", 0)),
            confidence=float(data.get("confidence", 1.0)),
        )


@dataclass
class RedTeamAuditResult:
    anomaly: Optional[AnomalyRecord] = None
    verdict: RedTeamVerdict = RedTeamVerdict.CHALLENGED
    rationale: str = ""
    risk_assessment: str = ""
    recommended_action: str = ""
    confidence: float = 1.0
    reason: Optional[str] = None
    counter_proposal: Optional[str] = None

    def __post_init__(self) -> None:
        if self.reason is not None and not self.rationale:
            self.rationale = self.reason
        elif self.rationale and self.reason is None:
            self.reason = self.rationale

        if self.counter_proposal is not None and not self.recommended_action:
            self.recommended_action = self.counter_proposal
        elif self.recommended_action and self.counter_proposal is None:
            self.counter_proposal = self.recommended_action

        if isinstance(self.verdict, str):
            self.verdict = RedTeamVerdict(self.verdict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly": self.anomaly.to_dict() if isinstance(self.anomaly, AnomalyRecord) else (self.anomaly or {}),
            "verdict": self.verdict.value if isinstance(self.verdict, RedTeamVerdict) else str(self.verdict),
            "rationale": self.rationale,
            "risk_assessment": self.risk_assessment,
            "recommended_action": self.recommended_action,
            "confidence": self.confidence,
            "reason": self.reason or self.rationale,
            "counter_proposal": self.counter_proposal or self.recommended_action,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedTeamAuditResult":
        raw_verdict = data.get("verdict")
        verdict = RedTeamVerdict(raw_verdict) if isinstance(raw_verdict, str) else (raw_verdict or RedTeamVerdict.CHALLENGED)
        anomaly_data = data.get("anomaly", {})
        anomaly = AnomalyRecord.from_dict(anomaly_data) if isinstance(anomaly_data, dict) and anomaly_data else (anomaly_data if isinstance(anomaly_data, AnomalyRecord) else None)
        rationale = data.get("rationale") or data.get("reason", "")
        recommended = data.get("recommended_action") or data.get("counter_proposal", "")
        return cls(
            anomaly=anomaly,
            verdict=verdict,
            rationale=rationale,
            risk_assessment=data.get("risk_assessment", ""),
            recommended_action=recommended,
            confidence=float(data.get("confidence", 1.0)),
            reason=rationale,
            counter_proposal=recommended,
        )



@dataclass
class OptimizationReport:
    session_id: str
    timestamp: int
    duration_ms: float
    total_anomalies: int
    approved_count: int
    challenged_count: int
    audited_anomalies: List[RedTeamAuditResult] = field(default_factory=list)
    textual_gradients: List[str] = field(default_factory=list)
    entropy_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "total_anomalies": self.total_anomalies,
            "approved_count": self.approved_count,
            "challenged_count": self.challenged_count,
            "audited_anomalies": [
                a.to_dict() if isinstance(a, RedTeamAuditResult) else a
                for a in self.audited_anomalies
            ],
            "textual_gradients": list(self.textual_gradients),
            "entropy_score": self.entropy_score,
        }
