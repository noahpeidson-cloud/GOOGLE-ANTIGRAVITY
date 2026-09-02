"""Unit tests for Milestone 3 ML Clustering, Embeddings, Semantic Entropy, and ProTeGi Gradients."""

import time
import numpy as np
import pytest

from config import DEFAULT_K_CLUSTERS
from models import AnomalyRecord, DetectorType, Severity
from ml.embeddings import (
    DETECTOR_CATEGORY_MAP,
    SEVERITY_WEIGHTS,
    vectorize_anomalies,
    vectorize_anomaly,
)
from ml.clustering import compute_semantic_entropy, kmeans_cluster
from ml.protegi import CONVERGENCE_MESSAGE, generate_textual_gradients
from ml import (
    compute_semantic_entropy as exported_entropy,
    generate_textual_gradients as exported_gradients,
    kmeans_cluster as exported_kmeans,
    vectorize_anomalies as exported_vecs,
    vectorize_anomaly as exported_vec,
)


def test_ml_module_exports() -> None:
    """Verifies that all 5 ML module functions are exported from ml package."""
    assert callable(exported_vec)
    assert callable(exported_vecs)
    assert callable(exported_kmeans)
    assert callable(exported_entropy)
    assert callable(exported_gradients)


def test_vectorize_anomaly_severity_weights() -> None:
    """Verifies Feature 0 severity weights for all severity levels."""
    for sev, expected_val in [
        (Severity.LOW, 0.25),
        (Severity.MEDIUM, 0.50),
        (Severity.HIGH, 0.75),
        (Severity.CRITICAL, 1.00),
    ]:
        rec = AnomalyRecord(
            detector_type=DetectorType.GHOST_DAEMONS,
            target_path="127.0.0.1:3000",
            severity=sev,
            description="Test anomaly",
        )
        vec = vectorize_anomaly(rec)
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (5,)
        assert np.isclose(vec[0], expected_val)


def test_vectorize_anomaly_detector_categories() -> None:
    """Verifies Feature 1 detector category mappings for all 5 detectors."""
    for det, expected_val in [
        (DetectorType.GHOST_DAEMONS, 0.00),
        (DetectorType.CONTEXT_ROT, 0.25),
        (DetectorType.ECOSYSTEM_POLLUTION, 0.50),
        (DetectorType.SECRET_ZERO, 0.75),
        (DetectorType.PROMPT_FATIGUE, 1.00),
    ]:
        rec = AnomalyRecord(
            detector_type=det,
            target_path="test/path",
            severity=Severity.LOW,
            description="Test category",
        )
        vec = vectorize_anomaly(rec)
        assert np.isclose(vec[1], expected_val)


def test_vectorize_anomaly_age_normalization() -> None:
    """Verifies Feature 2 age normalization with bounds [0.0, 1.0]."""
    # 0 hours
    rec_0h = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path="plan.md",
        severity=Severity.MEDIUM,
        description="Stale plan",
        raw_details={"age_hours": 0.0},
    )
    assert np.isclose(vectorize_anomaly(rec_0h)[2], 0.0)

    # 84 hours (half of 168h)
    rec_84h = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path="plan.md",
        severity=Severity.MEDIUM,
        description="Stale plan",
        raw_details={"age_hours": 84.0},
    )
    assert np.isclose(vectorize_anomaly(rec_84h)[2], 0.5)

    # 168 hours (1 week max)
    rec_168h = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path="plan.md",
        severity=Severity.MEDIUM,
        description="Stale plan",
        raw_details={"age_hours": 168.0},
    )
    assert np.isclose(vectorize_anomaly(rec_168h)[2], 1.0)

    # Over 168 hours -> clamped to 1.0
    rec_500h = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path="plan.md",
        severity=Severity.MEDIUM,
        description="Stale plan",
        raw_details={"age_hours": 500.0},
    )
    assert np.isclose(vectorize_anomaly(rec_500h)[2], 1.0)

    # Timestamp-based age calculation with current_time
    cur_t = 1000000.0
    past_t = cur_t - (84.0 * 3600.0)
    rec_ts = AnomalyRecord(
        detector_type=DetectorType.CONTEXT_ROT,
        target_path="plan.md",
        severity=Severity.MEDIUM,
        description="Stale plan",
        timestamp=int(past_t),
    )
    assert np.isclose(vectorize_anomaly(rec_ts, current_time=cur_t)[2], 0.5)


def test_vectorize_anomaly_footprint_normalization() -> None:
    """Verifies Feature 3 token footprint normalization with bounds [0.0, 1.0]."""
    # 0 tokens
    rec_0 = AnomalyRecord(
        detector_type=DetectorType.PROMPT_FATIGUE,
        target_path="GEMINI.md",
        severity=Severity.MEDIUM,
        description="",
        raw_details={"token_count": 0},
    )
    assert np.isclose(vectorize_anomaly(rec_0)[3], 0.0)

    # 5,000 tokens (half of 10,000)
    rec_5k = AnomalyRecord(
        detector_type=DetectorType.PROMPT_FATIGUE,
        target_path="GEMINI.md",
        severity=Severity.MEDIUM,
        description="Manifest bloat",
        raw_details={"token_count": 5000},
    )
    assert np.isclose(vectorize_anomaly(rec_5k)[3], 0.5)

    # 10,000 tokens (max)
    rec_10k = AnomalyRecord(
        detector_type=DetectorType.PROMPT_FATIGUE,
        target_path="GEMINI.md",
        severity=Severity.MEDIUM,
        description="Manifest bloat",
        raw_details={"token_count": 10000},
    )
    assert np.isclose(vectorize_anomaly(rec_10k)[3], 1.0)

    # 50,000 tokens -> clamped to 1.0
    rec_50k = AnomalyRecord(
        detector_type=DetectorType.PROMPT_FATIGUE,
        target_path="GEMINI.md",
        severity=Severity.MEDIUM,
        description="Manifest bloat",
        raw_details={"token_count": 50000},
    )
    assert np.isclose(vectorize_anomaly(rec_50k)[3], 1.0)

    # File size / bytes in raw_details
    rec_bytes = AnomalyRecord(
        detector_type=DetectorType.ECOSYSTEM_POLLUTION,
        target_path="asset.mp4",
        severity=Severity.HIGH,
        description="Leak",
        raw_details={"file_size": 2500},
    )
    assert np.isclose(vectorize_anomaly(rec_bytes)[3], 0.25)


def test_vectorize_anomaly_confidence_and_dict_support() -> None:
    """Verifies Feature 4 confidence score and dictionary input support."""
    dict_anomaly = {
        "detector_type": "SECRET_ZERO",
        "severity": "CRITICAL",
        "target_path": ".env",
        "description": "Placeholder token found",
        "raw_details": {"line_no": 12, "token_count": 2500},
        "confidence": 0.85,
    }
    vec = vectorize_anomaly(dict_anomaly)
    assert vec.shape == (5,)
    assert np.isclose(vec[0], 1.00)  # CRITICAL
    assert np.isclose(vec[1], 0.75)  # SECRET_ZERO
    assert np.isclose(vec[3], 0.25)  # 2500 / 10000
    assert np.isclose(vec[4], 0.85)  # confidence


def test_vectorize_anomalies_empty_and_batch() -> None:
    """Verifies vectorize_anomalies on empty lists and multi-element batches."""
    # Empty list
    empty_res = vectorize_anomalies([])
    assert isinstance(empty_res, np.ndarray)
    assert empty_res.shape == (0, 5)

    # Batch of 5 anomalies
    records = [
        AnomalyRecord(DetectorType.GHOST_DAEMONS, "127.0.0.1:3000", Severity.CRITICAL, "Socket collision"),
        AnomalyRecord(DetectorType.CONTEXT_ROT, "plan.md", Severity.MEDIUM, "Stale file", {"age_hours": 48.0}),
        AnomalyRecord(DetectorType.ECOSYSTEM_POLLUTION, "plugin.disabled", Severity.HIGH, "Disabled plugin"),
        AnomalyRecord(DetectorType.SECRET_ZERO, ".env", Severity.CRITICAL, "Secret zero", {"token_count": 1000}),
        AnomalyRecord(DetectorType.PROMPT_FATIGUE, "GEMINI.md", Severity.MEDIUM, "Prompt fatigue", {"token_count": 8000}),
    ]
    mat = vectorize_anomalies(records)
    assert mat.shape == (5, 5)
    assert np.all(mat >= 0.0)
    assert np.all(mat <= 1.0)


def test_kmeans_clustering_convergence_and_reproducibility() -> None:
    """Verifies K-Means converges to K=3 clusters deterministically with fixed random_state."""
    # Create 3 distinct clusters of 20 points each in [0, 1]^5
    rng = np.random.RandomState(42)
    c1 = rng.normal(loc=0.15, scale=0.03, size=(20, 5))
    c2 = rng.normal(loc=0.50, scale=0.03, size=(20, 5))
    c3 = rng.normal(loc=0.85, scale=0.03, size=(20, 5))
    X = np.clip(np.vstack([c1, c2, c3]), 0.0, 1.0)

    labels1, centroids1, inertia1 = kmeans_cluster(X, k=3, random_state=42)
    labels2, centroids2, inertia2 = kmeans_cluster(X, k=3, random_state=42)

    assert labels1.shape == (60,)
    assert centroids1.shape == (3, 5)
    assert inertia1 >= 0.0
    assert np.array_equal(labels1, labels2)
    assert np.allclose(centroids1, centroids2)
    assert np.isclose(inertia1, inertia2)
    assert len(np.unique(labels1)) == 3


def test_kmeans_clustering_execution_speed_benchmark() -> None:
    """Verifies K-Means executes in < 5.0ms on 100 sample points."""
    rng = np.random.RandomState(123)
    X = rng.uniform(0.0, 1.0, size=(100, 5))

    # Warm-up run
    kmeans_cluster(X, k=3, random_state=42)

    # Benchmark run
    start_time = time.perf_counter()
    iterations = 20
    for _ in range(iterations):
        kmeans_cluster(X, k=3, random_state=42)
    elapsed_total_ms = (time.perf_counter() - start_time) * 1000.0
    avg_elapsed_ms = elapsed_total_ms / iterations

    # Must execute in < 5.0ms per run (typically < 1.0ms)
    assert avg_elapsed_ms < 5.0, f"K-Means execution took {avg_elapsed_ms:.2f}ms (exceeds 5.0ms requirement)"


def test_kmeans_boundary_cases_n0_n1_n2() -> None:
    """Verifies edge cases N=0, N=1, N=2 (N < K) and identical points."""
    # N = 0
    X0 = np.empty((0, 5))
    labels0, centroids0, inertia0 = kmeans_cluster(X0, k=3)
    assert labels0.shape == (0,)
    assert centroids0.shape == (3, 5)
    assert inertia0 == 0.0

    # N = 1
    X1 = np.array([[0.5, 0.5, 0.5, 0.5, 0.5]])
    labels1, centroids1, inertia1 = kmeans_cluster(X1, k=3)
    assert labels1.shape == (1,)
    assert centroids1.shape == (3, 5)
    assert inertia1 == 0.0

    # N = 2 (N < K=3)
    X2 = np.array([
        [0.1, 0.2, 0.3, 0.4, 0.5],
        [0.9, 0.8, 0.7, 0.6, 0.5],
    ])
    labels2, centroids2, inertia2 = kmeans_cluster(X2, k=3)
    assert labels2.shape == (2,)
    assert centroids2.shape == (3, 5)
    assert labels2[0] != labels2[1]
    assert inertia2 == 0.0

    # 30 Identical points
    X_ident = np.full((30, 5), 0.7)
    labels_id, centroids_id, inertia_id = kmeans_cluster(X_ident, k=3)
    assert labels_id.shape == (30,)
    assert np.isclose(inertia_id, 0.0)


def test_kmeans_stress_1000_samples() -> None:
    """Stress tests K-Means clustering on 1,000 anomaly vectors."""
    rng = np.random.RandomState(999)
    X_large = rng.uniform(0.0, 1.0, size=(1000, 5))

    start_time = time.perf_counter()
    labels, centroids, inertia = kmeans_cluster(X_large, k=3, max_iter=50, random_state=42)
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    assert labels.shape == (1000,)
    assert centroids.shape == (3, 5)
    assert inertia > 0.0
    assert not np.isnan(inertia)
    assert duration_ms < 50.0  # Vectorized execution easily under 50ms for 1k samples


def test_semantic_entropy_calculation() -> None:
    """Verifies semantic entropy dispersion calculation for various cluster dispersions."""
    # N = 0
    assert compute_semantic_entropy(np.empty((0, 5)), np.zeros(0, dtype=int), np.zeros((3, 5))) == 0.0

    # N = 1
    assert compute_semantic_entropy(np.array([[0.5, 0.5, 0.5, 0.5, 0.5]]), np.zeros(1, dtype=int), np.zeros((3, 5))) == 0.0

    # Extremely tight clusters -> entropy close to 0.0
    rng = np.random.RandomState(42)
    tight_c1 = rng.normal(loc=0.2, scale=0.001, size=(20, 5))
    tight_c2 = rng.normal(loc=0.8, scale=0.001, size=(20, 5))
    X_tight = np.clip(np.vstack([tight_c1, tight_c2]), 0.0, 1.0)
    labels_tight, centroids_tight, _ = kmeans_cluster(X_tight, k=2)
    entropy_tight = compute_semantic_entropy(X_tight, labels_tight, centroids_tight)
    assert 0.0 <= entropy_tight < 0.05

    # Widely dispersed points -> higher entropy
    X_dispersed = rng.uniform(0.0, 1.0, size=(50, 5))
    labels_disp, centroids_disp, _ = kmeans_cluster(X_dispersed, k=3)
    entropy_disp = compute_semantic_entropy(X_dispersed, labels_disp, centroids_disp)
    assert 0.10 <= entropy_disp <= 1.0


def test_protegi_textual_gradients_convergence() -> None:
    """Verifies that 0 entropy or empty anomaly lists produce the default convergence message."""
    msg_empty = generate_textual_gradients([], np.zeros(0, dtype=int), np.zeros((3, 5)), entropy=0.0)
    assert msg_empty == [CONVERGENCE_MESSAGE]

    dummy_anom = [AnomalyRecord(DetectorType.GHOST_DAEMONS, "127.0.0.1:3000", Severity.LOW, "Test")]
    msg_zero_entropy = generate_textual_gradients(dummy_anom, np.zeros(1, dtype=int), np.zeros((3, 5)), entropy=0.0)
    assert msg_zero_entropy == [CONVERGENCE_MESSAGE]


def test_protegi_textual_gradients_generation() -> None:
    """Verifies ProTeGi generates targeted actionable gradients for all detector categories and high entropy."""
    records = [
        AnomalyRecord(DetectorType.GHOST_DAEMONS, "127.0.0.1:3000", Severity.CRITICAL, "Port 3000 occupied"),
        AnomalyRecord(DetectorType.CONTEXT_ROT, "old_plan.md", Severity.MEDIUM, "Planning file >24h", {"age_hours": 72.0}),
        AnomalyRecord(DetectorType.ECOSYSTEM_POLLUTION, "bad.disabled", Severity.HIGH, "Disabled plugin dir"),
        AnomalyRecord(DetectorType.SECRET_ZERO, ".env", Severity.CRITICAL, "Placeholder sk-***", {"token_count": 100}),
        AnomalyRecord(DetectorType.PROMPT_FATIGUE, "GEMINI.md", Severity.MEDIUM, "150 lines bloat", {"token_count": 8000}),
    ]
    X = vectorize_anomalies(records)
    labels, centroids, _ = kmeans_cluster(X, k=3, random_state=42)
    entropy = compute_semantic_entropy(X, labels, centroids)

    gradients = generate_textual_gradients(records, labels, centroids, entropy=max(0.25, entropy))

    assert len(gradients) >= 5
    joined_text = " ".join(gradients)
    assert "GHOST_DAEMONS" in joined_text
    assert "CONTEXT_ROT" in joined_text
    assert "ECOSYSTEM_POLLUTION" in joined_text
    assert "SECRET_ZERO" in joined_text
    assert "PROMPT_FATIGUE" in joined_text
    assert "ProTeGi Meta-Gradient" in joined_text


def test_protegi_individual_detector_gradients() -> None:
    """Verifies each detector category individually yields its specialized ProTeGi gradient."""
    categories = [
        (DetectorType.GHOST_DAEMONS, "GHOST_DAEMONS"),
        (DetectorType.CONTEXT_ROT, "CONTEXT_ROT"),
        (DetectorType.ECOSYSTEM_POLLUTION, "ECOSYSTEM_POLLUTION"),
        (DetectorType.SECRET_ZERO, "SECRET_ZERO"),
        (DetectorType.PROMPT_FATIGUE, "PROMPT_FATIGUE"),
    ]
    for det_type, det_name in categories:
        anom = [AnomalyRecord(det_type, "target", Severity.HIGH, "Description", {"token_count": 100})]
        X = vectorize_anomalies(anom)
        labels, centroids, _ = kmeans_cluster(X, k=1)
        grads = generate_textual_gradients(anom, labels, centroids, entropy=0.10)
        assert any(det_name in g for g in grads)
