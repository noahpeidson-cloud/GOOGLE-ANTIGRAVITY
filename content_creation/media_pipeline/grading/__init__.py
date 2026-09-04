"""
EDM Mastermind Media Pipeline: Video Grading Engine.
Package: media_pipeline.grading
"""

try:
    from .viral_schema import (
        AudioAcousticAnalysis,
        CrowdDynamicsAnalysis,
        DEFAULT_WEIGHTS,
        DropPacingAnalysis,
        EDMShortsViralMetrics,
        EDMViralGradingReport,
        HookAnalysis,
        LightingProductionAnalysis,
        ModelParameterWeights,
        TransientEvent,
        TrendingVerdict,
        ViralParameterScores,
        calculate_evpi,
        calculate_evpi_from_scores,
        classify_viral_tier,
        compute_killswitches,
        get_verdict_from_evpi,
    )
    from .gemini_multimodal_client import (
        DeadLetterQueue,
        GeminiMultimodalClient,
        RateLimiter,
    )
except (ImportError, ValueError):
    from media_pipeline.grading.viral_schema import (
        AudioAcousticAnalysis,
        CrowdDynamicsAnalysis,
        DEFAULT_WEIGHTS,
        DropPacingAnalysis,
        EDMShortsViralMetrics,
        EDMViralGradingReport,
        HookAnalysis,
        LightingProductionAnalysis,
        ModelParameterWeights,
        TransientEvent,
        TrendingVerdict,
        ViralParameterScores,
        calculate_evpi,
        calculate_evpi_from_scores,
        classify_viral_tier,
        compute_killswitches,
        get_verdict_from_evpi,
    )
    from media_pipeline.grading.gemini_multimodal_client import (
        DeadLetterQueue,
        GeminiMultimodalClient,
        RateLimiter,
    )

__all__ = [
    "AudioAcousticAnalysis",
    "CrowdDynamicsAnalysis",
    "DEFAULT_WEIGHTS",
    "DeadLetterQueue",
    "DropPacingAnalysis",
    "EDMShortsViralMetrics",
    "EDMViralGradingReport",
    "GeminiMultimodalClient",
    "HookAnalysis",
    "LightingProductionAnalysis",
    "ModelParameterWeights",
    "RateLimiter",
    "TransientEvent",
    "TrendingVerdict",
    "ViralParameterScores",
    "calculate_evpi",
    "calculate_evpi_from_scores",
    "classify_viral_tier",
    "compute_killswitches",
    "get_verdict_from_evpi",
]
