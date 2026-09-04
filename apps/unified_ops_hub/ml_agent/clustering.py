"""Localized K-Means Clustering Engine for Telemetry Spans.
Executes sub-5ms Lloyd's algorithm with K-Means++ initialization and semantic sorting
to classify scraping runs into Healthy (0), Degraded (1), and Failure (2) operational states.
"""

import logging
from typing import Dict, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("unified_ops_hub.ml_agent.clustering")


class KMeansOptimizer:
    """Localized, high-performance K-Means clustering engine using NumPy & Pandas."""

    def __init__(self, k: int = 3, random_state: int = 42, max_iter: int = 15) -> None:
        self.k = k
        self.random_state = random_state
        self.max_iter = max_iter

    def fit_predict(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, Dict[int, int]]:
        """
        Extracts features, normalizes distributions, and executes K-Means clustering.
        Returns:
            - labels: np.ndarray of cluster assignments (0: Healthy, 1: Degraded, 2: Failure)
            - centroids: np.ndarray of shape (k, 3) representing sorted cluster centroids
            - cluster_counts: Dict[int, int] mapping cluster ID to sample count
        """
        n_samples = len(df)
        if n_samples == 0:
            return np.array([], dtype=int), np.zeros((self.k, 3)), {}

        # Cold-start heuristic fallback for sparse samples (N < K)
        if n_samples < self.k:
            labels = np.zeros(n_samples, dtype=int)
            for i in range(n_samples):
                row = df.iloc[i]
                err = float(row.get("error_count", 0))
                yld = float(row.get("yield_count", 0))
                dur = float(row.get("duration_ms", 0))
                if err > 0 and yld == 0:
                    labels[i] = 2  # Failure
                elif err > 0 or dur > 15000 or yld < 5:
                    labels[i] = 1  # Degraded
                else:
                    labels[i] = 0  # Healthy

            counts = {int(k_id): int(v) for k_id, v in pd.Series(labels).value_counts().items()}
            return labels, np.zeros((self.k, 3)), counts

        # Feature Extraction
        duration = df["duration_ms"].values.astype(float) if "duration_ms" in df.columns else np.zeros(n_samples)
        yield_count = df["yield_count"].values.astype(float) if "yield_count" in df.columns else np.zeros(n_samples)
        error_count = df["error_count"].values.astype(float) if "error_count" in df.columns else np.zeros(n_samples)

        duration_sec = np.maximum(duration / 1000.0, 0.1)
        yield_rate = yield_count / duration_sec
        total_ops = np.maximum(1.0, yield_count + error_count)
        error_rate = error_count / total_ops

        # Z-Score Standardization with variance safety guard
        f1 = (duration - np.mean(duration)) / max(float(np.std(duration)), 1e-6)
        f2 = (yield_rate - np.mean(yield_rate)) / max(float(np.std(yield_rate)), 1e-6)
        f3 = (error_rate - np.mean(error_rate)) / max(float(np.std(error_rate)), 1e-6)
        X = np.column_stack([f1, f2, f3])

        # Check for near-zero variance across all features (all points identical or near-identical)
        if np.all(np.abs(X) < 1e-5) or (np.std(duration) < 1e-5 and np.std(yield_rate) < 1e-5 and np.std(error_rate) < 1e-5):
            labels = np.zeros(n_samples, dtype=int)
            for i in range(n_samples):
                err = float(error_count[i])
                yld = float(yield_count[i])
                dur = float(duration[i])
                if err > 0 and yld == 0:
                    labels[i] = 2  # Failure
                elif err > 0 or dur > 15000 or yld < 5:
                    labels[i] = 1  # Degraded
                else:
                    labels[i] = 0  # Healthy

            centroids = np.zeros((self.k, 3))
            counts = {int(k_id): int(v) for k_id, v in pd.Series(labels).value_counts().items()}
            return labels, centroids, counts

        # K-Means++ Initialization
        rng = np.random.RandomState(self.random_state)
        first_idx = rng.choice(n_samples)
        centroids = [X[first_idx]]

        for _ in range(1, self.k):
            distances_sq = np.min([np.sum((X - c) ** 2, axis=1) for c in centroids], axis=0)
            total_dist = np.sum(distances_sq)
            if total_dist < 1e-9:
                # Add random point if all points are equidistant
                next_idx = rng.choice(n_samples)
            else:
                probs = distances_sq / total_dist
                next_idx = rng.choice(n_samples, p=probs)
            centroids.append(X[next_idx])

        centroids = np.array(centroids, dtype=float)

        # Lloyd's Algorithm Iteration
        labels = np.zeros(n_samples, dtype=int)
        for _ in range(self.max_iter):
            # Compute Euclidean distances: (N, K)
            diff = X[:, np.newaxis, :] - centroids[np.newaxis, :, :]
            dist = np.sum(diff ** 2, axis=2)
            new_labels = np.argmin(dist, axis=1)

            if np.array_equal(labels, new_labels):
                break
            labels = new_labels

            # Centroid Updates
            for j in range(self.k):
                members = X[labels == j]
                if len(members) > 0:
                    centroids[j] = np.mean(members, axis=0)
                else:
                    # Reassign empty cluster to the furthest point
                    furthest_idx = np.argmax(np.min(dist, axis=1))
                    centroids[j] = X[furthest_idx]

        # Semantic Ordering:
        # Calculate raw degradation score per cluster:
        # High error rate and high duration increase score; high yield rate decreases score.
        cluster_scores = []
        for j in range(self.k):
            mask = (labels == j)
            if np.any(mask):
                c_err = float(np.mean(error_rate[mask]))
                c_yld = float(np.mean(yield_rate[mask]))
                c_dur = float(np.mean(duration[mask]))
                # Weight error heavily, then negative yield, then duration lag
                score = (c_err * 100.0) - (c_yld * 1.5) + (c_dur / 5000.0)
            else:
                # Normalized centroid score fallback
                score = float(centroids[j, 2] - centroids[j, 1] + 0.3 * centroids[j, 0])
            cluster_scores.append((score, j))

        # Sort ascending: lowest score -> Cluster 0 (Healthy), middle -> Cluster 1 (Degraded), highest -> Cluster 2 (Failure)
        cluster_scores.sort(key=lambda item: item[0])
        remap = {original_idx: new_idx for new_idx, (_, original_idx) in enumerate(cluster_scores)}

        final_labels = np.array([remap[lbl] for lbl in labels], dtype=int)
        final_centroids = np.array([centroids[orig_idx] for _, orig_idx in cluster_scores], dtype=float)

        # Count frequencies
        counts = {int(k_id): int(v) for k_id, v in pd.Series(final_labels).value_counts().items()}
        return final_labels, final_centroids, counts
