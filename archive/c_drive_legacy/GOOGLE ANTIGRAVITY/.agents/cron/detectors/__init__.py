"""Modular Read-Only Anomaly Detectors for Antigravity Daily Health Scanner."""

try:
    from .base import BaseDetector
    from .context_rot import ContextRotDetector
    from .ecosystem_pollution import EcosystemPollutionDetector
    from .ghost_daemons import GhostDaemonsDetector
    from .prompt_fatigue import PromptFatigueDetector
    from .secret_zero import SecretZeroDetector
except ImportError:
    from detectors.base import BaseDetector
    from detectors.context_rot import ContextRotDetector
    from detectors.ecosystem_pollution import EcosystemPollutionDetector
    from detectors.ghost_daemons import GhostDaemonsDetector
    from detectors.prompt_fatigue import PromptFatigueDetector
    from detectors.secret_zero import SecretZeroDetector

__all__ = [
    "BaseDetector",
    "GhostDaemonsDetector",
    "ContextRotDetector",
    "EcosystemPollutionDetector",
    "SecretZeroDetector",
    "PromptFatigueDetector",
]
