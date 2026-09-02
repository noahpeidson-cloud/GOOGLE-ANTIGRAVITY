"""Pure NumPy/Pandas K-Means clustering and semantic entropy analysis with zero external ML dependencies."""

from typing import Tuple

import numpy as np


def kmeans_cluster(
    X: np.ndarray,
    k: int = 3,
    max_iter: int = 50,
    tol: float = 1e-4,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Performs fast vectorized K-Means clustering (K=3) in pure NumPy with zero scikit-learn dependency.

    Parameters:
        X: (N, D) float numpy array of feature vectors.
        k: Number of clusters (default: 3).
        max_iter: Maximum EM iterations (default: 50).
        tol: Convergence tolerance for centroid movement (default: 1e-4).
        random_state: Seed for reproducible centroid initialization.

    Returns:
        labels: (N,) integer numpy array of cluster assignments.
        centroids: (k, D) float numpy array of cluster centers.
        inertia: float sum of squared distances to closest cluster centroid.
    """
    if not isinstance(X, np.ndarray):
        X = np.asarray(X, dtype=np.float64)
    else:
        X = X.astype(np.float64, copy=False)

    if X.ndim == 1:
        X = X.reshape(-1, 5 if X.size == 5 else 1)

    n_samples, n_features = X.shape

    # Edge Case 1: Empty input (N=0)
    if n_samples == 0:
        labels = np.zeros(0, dtype=np.int64)
        centroids = np.zeros((k, n_features if n_features > 0 else 5), dtype=np.float64)
        return labels, centroids, 0.0

    # Edge Case 2: Single sample (N=1)
    if n_samples == 1:
        labels = np.zeros(1, dtype=np.int64)
        centroids = np.repeat(X, k, axis=0)
        return labels, centroids, 0.0

    # Edge Case 3: N < k samples (e.g. N=2, k=3)
    if n_samples < k:
        labels = np.arange(n_samples, dtype=np.int64)
        # Pad centroids with the first sample to keep (k, D) shape
        padding = np.repeat(X[:1], k - n_samples, axis=0)
        centroids = np.vstack([X, padding])
        return labels, centroids, 0.0

    # Edge Case 4: All samples are identical
    if np.all(np.isclose(X, X[0])):
        labels = np.zeros(n_samples, dtype=np.int64)
        centroids = np.repeat(X[:1], k, axis=0)
        return labels, centroids, 0.0

    # Deterministic K-Means++ Initialization
    rng = np.random.RandomState(random_state)
    centroids = np.empty((k, n_features), dtype=np.float64)

    # 1. Pick first centroid randomly with seed
    initial_idx = int(rng.randint(0, n_samples))
    centroids[0] = X[initial_idx]

    # 2. Pick remaining centroids using distance weighting (K-Means++)
    for c_idx in range(1, k):
        # Distance from each point to existing centroids: shape (N, c_idx)
        diff = X[:, None, :] - centroids[None, :c_idx, :]
        dist_sq = np.min(np.sum(diff ** 2, axis=-1), axis=-1)  # shape (N,)
        dist_sum = np.sum(dist_sq)
        if dist_sum > 1e-12:
            probs = dist_sq / dist_sum
            next_idx = int(rng.choice(n_samples, p=probs))
        else:
            next_idx = int(rng.choice(n_samples))
        centroids[c_idx] = X[next_idx]

    # Iterative Lloyd's Algorithm with Vectorized Broadcasting
    labels = np.zeros(n_samples, dtype=np.int64)

    for _ in range(max_iter):
        # Compute squared Euclidean distances: (N, 1, D) - (1, k, D) -> (N, k)
        diff = X[:, None, :] - centroids[None, :, :]
        dist_sq = np.sum(diff ** 2, axis=-1)

        new_labels = np.argmin(dist_sq, axis=-1)
        min_dists = np.min(dist_sq, axis=-1)

        # Centroid update
        new_centroids = np.empty_like(centroids)
        for j in range(k):
            mask = (new_labels == j)
            if np.any(mask):
                new_centroids[j] = np.mean(X[mask], axis=0)
            else:
                # Handle empty cluster: re-seed at sample with largest min distance
                furthest_idx = int(np.argmax(min_dists))
                new_centroids[j] = X[furthest_idx]

        # Check convergence
        centroid_shift = np.linalg.norm(new_centroids - centroids)
        centroids = new_centroids
        if centroid_shift < tol or np.array_equal(new_labels, labels):
            labels = new_labels
            break
        labels = new_labels

    # Compute final inertia (sum of squared distances to closest centroid)
    final_diff = X[:, None, :] - centroids[None, :, :]
    final_dist_sq = np.sum(final_diff ** 2, axis=-1)
    inertia = float(np.sum(np.min(final_dist_sq, axis=-1)))

    return labels, centroids, inertia


def compute_semantic_entropy(
    X: np.ndarray,
    labels: np.ndarray,
    centroids: np.ndarray,
) -> float:
    """Calculates intra-cluster variance / normalized dispersion in [0.0, 1.0].

    Parameters:
        X: (N, D) float array of feature vectors.
        labels: (N,) integer array of cluster assignments.
        centroids: (k, D) float array of cluster centroids.

    Returns:
        entropy: float in [0.0, 1.0] representing normalized intra-cluster dispersion.
                 0.0 indicates perfect tight clustering or empty input.
                 1.0 indicates maximum possible dispersion.
    """
    if not isinstance(X, np.ndarray):
        X = np.asarray(X, dtype=np.float64)

    if X.size == 0 or X.shape[0] <= 1:
        return 0.0

    n_samples, n_features = X.shape

    if labels.shape[0] != n_samples or centroids.shape[0] == 0:
        return 0.0

    # Ensure labels are within centroid bounds
    valid_labels = np.clip(labels, 0, centroids.shape[0] - 1)
    assigned_centroids = centroids[valid_labels]

    # Calculate squared Euclidean distances from each point to its assigned centroid
    squared_dists = np.sum((X - assigned_centroids) ** 2, axis=-1)

    # Root Mean Square Error (RMSE) across all points
    rmse = np.sqrt(np.mean(squared_dists))

    # In [0.0, 1.0]^D space, max distance from center is sqrt(D)
    max_dispersion = np.sqrt(float(n_features if n_features > 0 else 5))

    # Normalized intra-cluster dispersion
    entropy = float(min(1.0, max(0.0, rmse / max_dispersion)))
    return round(entropy, 4)
