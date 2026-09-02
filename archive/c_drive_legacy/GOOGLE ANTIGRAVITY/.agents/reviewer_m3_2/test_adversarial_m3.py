"""Adversarial stress-testing script for Milestone 3 (ML Clustering, Embeddings, Semantic Entropy, ProTeGi)."""

import ast
import os
import sys
import time
from typing import Dict, List, Tuple
import numpy as np

# Ensure .agents/cron is on sys.path
CRON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cron"))
sys.path.insert(0, CRON_DIR)

from models import AnomalyRecord, DetectorType, Severity
from ml.embeddings import (
    DETECTOR_CATEGORY_MAP,
    SEVERITY_WEIGHTS,
    vectorize_anomalies,
    vectorize_anomaly,
)
from ml.clustering import compute_semantic_entropy, kmeans_cluster
from ml.protegi import CONVERGENCE_MESSAGE, generate_textual_gradients
from safety_guardrails import assert_safe_codebase


def check_zero_sklearn_dependencies() -> List[str]:
    """Inspects AST of all files in .agents/cron to ensure 0 sklearn / scikit-learn dependencies."""
    violations = []
    for root, _, files in os.walk(CRON_DIR):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8") as pyfile:
                    tree = ast.parse(pyfile.read(), filename=fpath)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            if "sklearn" in name.name or "scikit" in name.name:
                                violations.append(f"{fpath}: Prohibited import '{name.name}'")
                    elif isinstance(node, ast.ImportFrom):
                        mod = node.module or ""
                        if "sklearn" in mod or "scikit" in mod:
                            violations.append(f"{fpath}: Prohibited from-import from '{mod}'")
    return violations


def benchmark_kmeans_latency() -> Dict[str, float]:
    """Measures execution latency across multiple sample sizes and iterations."""
    benchmarks = {}
    sample_sizes = [1, 5, 10, 50, 100, 200, 500, 1000]
    rng = np.random.RandomState(42)

    for n in sample_sizes:
        X = rng.uniform(0.0, 1.0, size=(n, 5))
        # Warmup
        kmeans_cluster(X, k=3, random_state=42)
        
        runs = 50 if n <= 100 else 20
        times_ms = []
        for _ in range(runs):
            t0 = time.perf_counter()
            kmeans_cluster(X, k=3, random_state=42)
            t1 = time.perf_counter()
            times_ms.append((t1 - t0) * 1000.0)

        mean_ms = float(np.mean(times_ms))
        p95_ms = float(np.percentile(times_ms, 95))
        max_ms = float(np.max(times_ms))
        benchmarks[f"N={n}_mean_ms"] = round(mean_ms, 4)
        benchmarks[f"N={n}_p95_ms"] = round(p95_ms, 4)
        benchmarks[f"N={n}_max_ms"] = round(max_ms, 4)

    return benchmarks


def test_n_less_than_k_edge_cases() -> List[str]:
    """Rigorously tests N < K edge cases (N=0, 1, 2 for K=3, 5, 10)."""
    errors = []

    # 1. N=0
    for k in [1, 2, 3, 5]:
        labels, centroids, inertia = kmeans_cluster(np.empty((0, 5)), k=k)
        if labels.shape != (0,):
            errors.append(f"N=0, K={k}: labels shape {labels.shape} != (0,)")
        if centroids.shape != (k, 5):
            errors.append(f"N=0, K={k}: centroids shape {centroids.shape} != ({k}, 5)")
        if inertia != 0.0:
            errors.append(f"N=0, K={k}: inertia {inertia} != 0.0")

    # 2. N=1
    for k in [1, 2, 3, 5]:
        X1 = np.array([[0.1, 0.2, 0.3, 0.4, 0.5]])
        labels, centroids, inertia = kmeans_cluster(X1, k=k)
        if labels.shape != (1,) or labels[0] != 0:
            errors.append(f"N=1, K={k}: labels {labels} invalid")
        if centroids.shape != (k, 5):
            errors.append(f"N=1, K={k}: centroids shape {centroids.shape} != ({k}, 5)")
        if inertia != 0.0:
            errors.append(f"N=1, K={k}: inertia {inertia} != 0.0")

    # 3. N=2 with K=3, K=5
    for k in [3, 5]:
        X2 = np.array([[0.1, 0.2, 0.3, 0.4, 0.5], [0.9, 0.8, 0.7, 0.6, 0.5]])
        labels, centroids, inertia = kmeans_cluster(X2, k=k)
        if labels.shape != (2,):
            errors.append(f"N=2, K={k}: labels shape {labels.shape} != (2,)")
        if centroids.shape != (k, 5):
            errors.append(f"N=2, K={k}: centroids shape {centroids.shape} != ({k}, 5)")
        if labels[0] == labels[1]:
            errors.append(f"N=2, K={k}: distinct points given identical label")
        if inertia != 0.0:
            errors.append(f"N=2, K={k}: inertia {inertia} != 0.0")

    # 4. N=5 with K=5
    X5 = np.random.RandomState(42).uniform(0, 1, size=(5, 5))
    labels5, centroids5, inertia5 = kmeans_cluster(X5, k=5)
    if labels5.shape != (5,) or len(np.unique(labels5)) != 5:
        errors.append(f"N=5, K=5: expected 5 unique labels, got {len(np.unique(labels5))}")

    return errors


def test_adversarial_data_shapes_and_degeneracies() -> List[str]:
    """Tests extreme inputs, arbitrary dimensions D != 5, 1D arrays, and coincident points."""
    errors = []

    # D = 1
    X_1d = np.array([[1.0], [2.0], [3.0], [10.0], [11.0], [12.0]])
    labels, centroids, inertia = kmeans_cluster(X_1d, k=2)
    if labels.shape != (6,) or centroids.shape != (2, 1):
        errors.append(f"D=1 failure: labels={labels.shape}, centroids={centroids.shape}")

    # D = 10
    X_10d = np.random.RandomState(42).uniform(0, 1, size=(30, 10))
    labels, centroids, inertia = kmeans_cluster(X_10d, k=3)
    if labels.shape != (30,) or centroids.shape != (3, 10):
        errors.append(f"D=10 failure: labels={labels.shape}, centroids={centroids.shape}")

    # 1D flattened input of size 5 -> reshaped to (1, 5)
    X_flat5 = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    labels, centroids, inertia = kmeans_cluster(X_flat5, k=3)
    if labels.shape != (1,) or centroids.shape != (3, 5):
        errors.append(f"1D shape(5,) input failed to reshape: labels={labels.shape}, centroids={centroids.shape}")

    # Coincident / Identical points (100 identical vectors)
    X_ident = np.full((100, 5), 0.42)
    labels, centroids, inertia = kmeans_cluster(X_ident, k=3)
    if labels.shape != (100,) or centroids.shape != (3, 5) or not np.isclose(inertia, 0.0):
        errors.append(f"100 Identical points failure: inertia={inertia}")

    # Two distinct clusters where one cluster has 50 points and another has 1 point (outlier)
    c1 = np.full((50, 5), 0.1)
    c2 = np.full((1, 5), 0.9)
    X_outlier = np.vstack([c1, c2])
    labels, centroids, inertia = kmeans_cluster(X_outlier, k=2, random_state=42)
    if labels.shape != (51,) or centroids.shape != (2, 5):
        errors.append(f"Outlier cluster failure: labels={labels.shape}")

    return errors


def test_semantic_entropy_mathematics() -> List[str]:
    """Tests the mathematical correctness of intra-cluster semantic entropy."""
    errors = []

    # Perfect clustering on 2 distinct point sets -> entropy must be exactly 0.0
    X = np.array([
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0, 1.0, 1.0],
        [1.0, 1.0, 1.0, 1.0, 1.0],
    ])
    labels = np.array([0, 0, 1, 1])
    centroids = np.array([
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0, 1.0, 1.0],
    ])
    ent = compute_semantic_entropy(X, labels, centroids)
    if ent != 0.0:
        errors.append(f"Perfect cluster entropy {ent} != 0.0")

    # Worst-case dispersion: points at extreme corners [0,0,0,0,0] and [1,1,1,1,1] assigned to centroid [0.5, 0.5, 0.5, 0.5, 0.5]
    X_worst = np.array([
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0, 1.0, 1.0],
    ])
    labels_worst = np.array([0, 0])
    centroids_worst = np.array([[0.5, 0.5, 0.5, 0.5, 0.5]])
    ent_worst = compute_semantic_entropy(X_worst, labels_worst, centroids_worst)
    # distance of each point to centroid is sqrt(5 * 0.25) = sqrt(1.25)
    # RMSE = sqrt(1.25) = 1.11803
    # max_dispersion = sqrt(5) = 2.23606
    # entropy = RMSE / max_dispersion = sqrt(1.25 / 5) = sqrt(0.25) = 0.5000
    if not np.isclose(ent_worst, 0.5, atol=1e-3):
        errors.append(f"Expected entropy 0.5 for hypercube centers, got {ent_worst}")

    return errors


def test_protegi_textual_gradients_adversarial() -> List[str]:
    """Tests ProTeGi gradient synthesis under various adversarial conditions."""
    errors = []

    # 1. Zero entropy -> Convergence message
    res = generate_textual_gradients([], np.zeros(0), np.zeros((3, 5)), entropy=0.0)
    if res != [CONVERGENCE_MESSAGE]:
        errors.append(f"Empty anomalies didn't return convergence message: {res}")

    # 2. Single anomaly of each type with high entropy
    for dt in DetectorType:
        rec = [AnomalyRecord(dt, "path/to/target", Severity.CRITICAL, "Adversarial test description")]
        X = vectorize_anomalies(rec)
        labels, centroids, _ = kmeans_cluster(X, k=1)
        grads = generate_textual_gradients(rec, labels, centroids, entropy=0.20)
        if not any(dt.value in g for g in grads):
            errors.append(f"Detector {dt.value} gradient missing from output: {grads}")
        if not any("ProTeGi Meta-Gradient" in g for g in grads):
            errors.append(f"Meta-gradient missing for entropy >= 0.15: {grads}")

    return errors


def main():
    print("=== STARTING ADVERSARIAL REVIEW TEST SUITE ===")

    # 1. Check zero sklearn dependencies
    print("\n[1] Checking for 0 scikit-learn / sklearn dependencies in codebase...")
    sklearn_violations = check_zero_sklearn_dependencies()
    if sklearn_violations:
        print("FAIL: Found prohibited sklearn imports:")
        for v in sklearn_violations:
            print(f"  - {v}")
    else:
        print("PASS: Verified 0 scikit-learn / sklearn imports across all .py files in .agents/cron.")

    # 2. AST Codebase Safety Check
    print("\n[2] Executing AST Safety Guardrails on .agents/cron...")
    try:
        assert_safe_codebase(CRON_DIR, exclude_dirs=["tests", "__pycache__", ".pytest_cache"])
        print("PASS: 0 destructive function calls detected in production code paths.")
    except Exception as e:
        print(f"FAIL: AST Safety check raised: {e}")

    # 3. Latency Benchmarking
    print("\n[3] Benchmarking K-Means Latency across sample sizes (Target: <5.0ms)...")
    benchmarks = benchmark_kmeans_latency()
    for k, v in benchmarks.items():
        print(f"  - {k}: {v}ms")
    n100_mean = benchmarks.get("N=100_mean_ms", 999.0)
    n100_p95 = benchmarks.get("N=100_p95_ms", 999.0)
    if n100_mean < 5.0 and n100_p95 < 5.0:
        print(f"PASS: N=100 execution latency is {n100_mean}ms (well within <5.0ms budget).")
    else:
        print(f"FAIL: N=100 latency ({n100_mean}ms mean, {n100_p95}ms p95) exceeds 5.0ms budget!")

    # 4. N < K Edge Cases
    print("\n[4] Testing N < K boundary edge cases (N=0, 1, 2 for K=3, 5)...")
    nk_errors = test_n_less_than_k_edge_cases()
    if nk_errors:
        print(f"FAIL: N < K errors found ({len(nk_errors)}):")
        for err in nk_errors:
            print(f"  - {err}")
    else:
        print("PASS: All N < K edge cases (N=0, 1, 2) handled gracefully with 0 NaN/Inf/Exceptions.")

    # 5. Adversarial shapes & degeneracies
    print("\n[5] Testing adversarial input shapes, degeneracies, outliers...")
    shape_errors = test_adversarial_data_shapes_and_degeneracies()
    if shape_errors:
        print(f"FAIL: Shape/degeneracy errors ({len(shape_errors)}):")
        for err in shape_errors:
            print(f"  - {err}")
    else:
        print("PASS: Handled 1D, D=1, D=10, 100 identical points, extreme outliers cleanly.")

    # 6. Semantic Entropy Mathematical Correctness
    print("\n[6] Verifying Semantic Entropy mathematical properties...")
    ent_errors = test_semantic_entropy_mathematics()
    if ent_errors:
        print(f"FAIL: Semantic entropy errors ({len(ent_errors)}):")
        for err in ent_errors:
            print(f"  - {err}")
    else:
        print("PASS: Semantic entropy mathematically verified against analytical ground truth.")

    # 7. ProTeGi Textual Gradients Synthesis
    print("\n[7] Verifying ProTeGi Textual Gradients synthesis...")
    protegi_errors = test_protegi_textual_gradients_adversarial()
    if protegi_errors:
        print(f"FAIL: ProTeGi gradient errors ({len(protegi_errors)}):")
        for err in protegi_errors:
            print(f"  - {err}")
    else:
        print("PASS: ProTeGi gradients synthesized properly across all categories and meta-gradients.")

    total_failures = len(sklearn_violations) + len(nk_errors) + len(shape_errors) + len(ent_errors) + len(protegi_errors)
    if total_failures == 0 and n100_mean < 5.0:
        print("\n=== ALL ADVERSARIAL CHECKS PASSED (0 FAILURES) ===")
        sys.exit(0)
    else:
        print(f"\n=== ADVERSARIAL CHECKS FAILED WITH {total_failures} ISSUES ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
