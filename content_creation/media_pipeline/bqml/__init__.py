"""
EDM Mastermind Media Pipeline: BigQuery ML Optimization Loop.
Package: media_pipeline.bqml
"""

try:
    from .feedback_loop import (
        BigQueryMLFeedbackEngine,
        CANONICAL_FEATURES,
        DEFAULT_WEIGHTS,
        FEATURE_ALIASES,
        ModelParameterWeights,
        extract_normalized_weights,
        recalibrate_model_weights,
        sink_video_grades_to_bq,
        update_post_performance_telemetry,
    )
except (ImportError, ValueError):
    from bqml.feedback_loop import (
        BigQueryMLFeedbackEngine,
        CANONICAL_FEATURES,
        DEFAULT_WEIGHTS,
        FEATURE_ALIASES,
        ModelParameterWeights,
        extract_normalized_weights,
        recalibrate_model_weights,
        sink_video_grades_to_bq,
        update_post_performance_telemetry,
    )

__all__ = [
    "BigQueryMLFeedbackEngine",
    "CANONICAL_FEATURES",
    "DEFAULT_WEIGHTS",
    "FEATURE_ALIASES",
    "ModelParameterWeights",
    "extract_normalized_weights",
    "recalibrate_model_weights",
    "sink_video_grades_to_bq",
    "update_post_performance_telemetry",
]
