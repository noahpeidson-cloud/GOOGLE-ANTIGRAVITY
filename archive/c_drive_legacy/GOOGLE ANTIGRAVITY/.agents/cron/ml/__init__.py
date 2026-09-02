"""Machine Learning optimization engine for health scanner anomaly clustering and ProTeGi textual gradients."""

from .clustering import compute_semantic_entropy, kmeans_cluster
from .embeddings import vectorize_anomalies, vectorize_anomaly
from .protegi import generate_textual_gradients

__all__ = [
    "vectorize_anomalies",
    "vectorize_anomaly",
    "kmeans_cluster",
    "compute_semantic_entropy",
    "generate_textual_gradients",
]
