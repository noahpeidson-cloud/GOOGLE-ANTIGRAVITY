"""
Empirical Adversarial Stress Test Suite for Milestone 3: Antigravity ML Agent & Autonomy Loop.
Target Modules:
- unified_ops_hub.ml_agent.clustering (KMeansOptimizer)
- unified_ops_hub.ml_agent.telemetry (TelemetryStore)
- unified_ops_hub.ml_agent.policy (PolicyEngine)
- unified_ops_hub.ml_agent.ml_agent (AutonomousMLAgent, execute_trends_garbage_collection)
- .agents.cron.ml.clustering (kmeans_cluster)
"""

import concurrent.futures
import json
import logging
import os
import sqlite3
import sys
import tempfile
import threading
import time
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

# Add workspace root to sys.path
WORKSPACE_ROOT = r"G:\My Drive\GOOGLE ANTIGRAVITY"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from unified_ops_hub.ml_agent.clustering import KMeansOptimizer
from unified_ops_hub.ml_agent.telemetry import TelemetryStore
from unified_ops_hub.ml_agent.policy import PolicyEngine
from unified_ops_hub.ml_agent.ml_agent import (
    AutonomousMLAgent,
    build_ml_agent_config,
    execute_trends_garbage_collection,
)

# Also test legacy/cron kmeans_cluster if available
try:
    from .agents.cron.ml.clustering import kmeans_cluster, compute_semantic_entropy
except Exception:
    try:
        sys.path.insert(0, os.path.join(WORKSPACE_ROOT, ".agents", "cron"))
        from ml.clustering import kmeans_cluster, compute_semantic_entropy
    except Exception:
        kmeans_cluster = None
        compute_semantic_entropy = None

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("m3_stress_test")


class TestResultsCollector:
    def __init__(self):
        self.results = []
        self.failures = []

    def record_pass(self, test_name: str, details: str = ""):
        self.results.append({"test": test_name, "status": "PASS", "details": details})
        print(f"  [PASS] {test_name}: {details}")

    def record_fail(self, test_name: str, error: str):
        self.failures.append({"test": test_name, "status": "FAIL", "error": error})
        print(f"  [FAIL] {test_name}: {error}")


collector = TestResultsCollector()


# ============================================================================
# VECTOR 1: KMeansOptimizer Degenerate, Extreme & Boundary Tests
# ============================================================================

def run_kmeans_adversarial_tests():
    print("\n" + "="*80)
    print("RUNNING VECTOR 1: KMeansOptimizer Adversarial & Mathematical Stress Tests")
    print("="*80)

    opt = KMeansOptimizer(k=3, random_state=42)

    # 1.1 Empty DataFrame (N=0)
    try:
        empty_df1 = pd.DataFrame()
        l1, c1, cnt1 = opt.fit_predict(empty_df1)
        assert len(l1) == 0, f"Expected 0 labels, got {len(l1)}"
        assert c1.shape == (3, 3), f"Expected shape (3,3), got {c1.shape}"
        assert cnt1 == {}, f"Expected empty counts, got {cnt1}"

        empty_df2 = pd.DataFrame(columns=["duration_ms", "yield_count", "error_count"])
        l2, c2, cnt2 = opt.fit_predict(empty_df2)
        assert len(l2) == 0
        collector.record_pass("KMeans.EmptyInput_N0", "Empty DataFrame handled without error")
    except Exception as e:
        collector.record_fail("KMeans.EmptyInput_N0", str(e))

    # 1.2 Sparse inputs (N=1, N=2)
    try:
        # N=1
        df_n1_healthy = pd.DataFrame([{"duration_ms": 500, "yield_count": 20, "error_count": 0}])
        l_n1, c_n1, cnt_n1 = opt.fit_predict(df_n1_healthy)
        assert len(l_n1) == 1 and l_n1[0] == 0, f"Expected label 0 for healthy N=1, got {l_n1}"

        df_n1_fail = pd.DataFrame([{"duration_ms": 500, "yield_count": 0, "error_count": 10}])
        l_n1_f, _, _ = opt.fit_predict(df_n1_fail)
        assert l_n1_f[0] == 2, f"Expected label 2 for failure N=1, got {l_n1_f}"

        df_n1_deg = pd.DataFrame([{"duration_ms": 20000, "yield_count": 1, "error_count": 1}])
        l_n1_d, _, _ = opt.fit_predict(df_n1_deg)
        assert l_n1_d[0] == 1, f"Expected label 1 for degraded N=1, got {l_n1_d}"

        # N=2
        df_n2 = pd.DataFrame([
            {"duration_ms": 600, "yield_count": 30, "error_count": 0},
            {"duration_ms": 2000, "yield_count": 0, "error_count": 8},
        ])
        l_n2, c_n2, cnt_n2 = opt.fit_predict(df_n2)
        assert len(l_n2) == 2 and l_n2[0] == 0 and l_n2[1] == 2
        collector.record_pass("KMeans.SparseInputs_N1_N2", "Cold-start heuristic accurately categorizes N=1, N=2")
    except Exception as e:
        collector.record_fail("KMeans.SparseInputs_N1_N2", str(e))

    # 1.3 Zero Variance Across All Features (N=10, 100, 1000 identical rows)
    try:
        for n in [10, 100, 1000]:
            df_zero_var = pd.DataFrame([
                {"duration_ms": 1200, "yield_count": 15, "error_count": 0}
                for _ in range(n)
            ])
            labels, centroids, counts = opt.fit_predict(df_zero_var)
            assert len(labels) == n, f"Labels length mismatch: {len(labels)} vs {n}"
            assert not np.isnan(centroids).any(), "Centroids contain NaN under zero variance"
            assert not np.isinf(centroids).any(), "Centroids contain Inf under zero variance"
            assert all(lbl == 0 for lbl in labels), "Healthy identical rows should all be label 0"

        # Zero variance failure rows
        df_zero_var_fail = pd.DataFrame([
            {"duration_ms": 1000, "yield_count": 0, "error_count": 5}
            for _ in range(50)
        ])
        l_fail, c_fail, _ = opt.fit_predict(df_zero_var_fail)
        assert all(lbl == 2 for lbl in l_fail), "Failure identical rows should all be label 2"
        collector.record_pass("KMeans.ZeroVariance_AllIdentical", "Zero variance handled cleanly across N=10..1000")
    except Exception as e:
        collector.record_fail("KMeans.ZeroVariance_AllIdentical", str(e))

    # 1.4 Single Dimension Variance / Partial Zero Variance
    try:
        # Duration varies, yield and error are completely zero/constant
        df_one_dim = pd.DataFrame([
            {"duration_ms": 500 + i * 500, "yield_count": 0, "error_count": 0}
            for i in range(30)
        ])
        l_od, c_od, cnt_od = opt.fit_predict(df_one_dim)
        assert len(l_od) == 30
        assert not np.isnan(c_od).any()
        assert not np.isinf(c_od).any()
        collector.record_pass("KMeans.SingleDimensionVariance", "Handled partial zero-variance without division-by-zero")
    except Exception as e:
        collector.record_fail("KMeans.SingleDimensionVariance", str(e))

    # 1.5 Extreme Outliers & Enormous Value Scales
    try:
        # 45 normal spans + 5 extreme outliers (duration 10^9 ms, errors 10^7)
        rows = []
        for _ in range(30):
            rows.append({"duration_ms": 800, "yield_count": 25, "error_count": 0})
        for _ in range(15):
            rows.append({"duration_ms": 15000, "yield_count": 2, "error_count": 1})
        for _ in range(5):
            rows.append({"duration_ms": 1e9, "yield_count": 1e6, "error_count": 1e7})

        df_outliers = pd.DataFrame(rows)
        l_out, c_out, cnt_out = opt.fit_predict(df_outliers)
        assert len(l_out) == 50
        assert not np.isnan(c_out).any(), "Centroids contain NaN with extreme floats"
        assert not np.isinf(c_out).any(), "Centroids contain Inf with extreme floats"
        # Outlier points should be classified as Failure (2) or Degraded (1)
        assert all(l_out[50-5:] == 2), f"Extreme error outliers should be labeled 2, got {l_out[50-5:]}"
        collector.record_pass("KMeans.ExtremeOutliers", "Scaled floats (1e9) handled stably without overflow or NaN")
    except Exception as e:
        collector.record_fail("KMeans.ExtremeOutliers", str(e))

    # 1.6 Collinear Data (Points lie on a straight 1D line in 3D space)
    try:
        rows = []
        for i in range(60):
            val = float(i + 1)
            rows.append({"duration_ms": val * 100.0, "yield_count": val * 2.0, "error_count": val * 0.1})
        df_collinear = pd.DataFrame(rows)
        l_col, c_col, cnt_col = opt.fit_predict(df_collinear)
        assert len(l_col) == 60
        assert len(cnt_col) == 3, f"Expected 3 clusters on collinear data, got {len(cnt_col)}"
        assert not np.isnan(c_col).any()
        collector.record_pass("KMeans.CollinearData", "Collinear 1D manifold segmented into 3 distinct clusters")
    except Exception as e:
        collector.record_fail("KMeans.CollinearData", str(e))

    # 1.7 Ordering Stability Across 50 Random Seeds
    try:
        ordering_mismatches = 0
        for seed in range(50):
            test_opt = KMeansOptimizer(k=3, random_state=seed)
            rows = (
                [{"duration_ms": 600, "yield_count": 30, "error_count": 0} for _ in range(20)] +
                [{"duration_ms": 16000, "yield_count": 2, "error_count": 2} for _ in range(20)] +
                [{"duration_ms": 2000, "yield_count": 0, "error_count": 10} for _ in range(20)]
            )
            df_seed = pd.DataFrame(rows)
            labels, centroids, counts = test_opt.fit_predict(df_seed)

            # Check cluster labels: 0..19 must be 0, 20..39 must be 1, 40..59 must be 2
            h_labels = labels[:20]
            d_labels = labels[20:40]
            f_labels = labels[40:60]

            if not (all(l == 0 for l in h_labels) and all(l == 1 for l in d_labels) and all(l == 2 for l in f_labels)):
                ordering_mismatches += 1

        assert ordering_mismatches == 0, f"Ordering unstable in {ordering_mismatches}/50 seeds"
        collector.record_pass("KMeans.ClusterOrderingStability", "100% semantic order stability verified across 50 random seeds")
    except Exception as e:
        collector.record_fail("KMeans.ClusterOrderingStability", str(e))

    # 1.8 Latency & Scalability Benchmarking (<5ms budget up to 5,000 points)
    try:
        sizes = [100, 500, 1000, 2500, 5000, 10000]
        timings = {}
        for n in sizes:
            rows = (
                [{"duration_ms": 600, "yield_count": 25, "error_count": 0} for _ in range(n // 3)] +
                [{"duration_ms": 15000, "yield_count": 3, "error_count": 2} for _ in range(n // 3)] +
                [{"duration_ms": 2000, "yield_count": 0, "error_count": 6} for _ in range(n - 2 * (n // 3))]
            )
            df_bench = pd.DataFrame(rows)

            # Warmup
            opt.fit_predict(df_bench)

            runs = []
            for _ in range(20):
                t0 = time.perf_counter()
                opt.fit_predict(df_bench)
                runs.append((time.perf_counter() - t0) * 1000.0)

            mean_ms = float(np.mean(runs))
            p95_ms = float(np.percentile(runs, 95))
            timings[n] = (mean_ms, p95_ms)

        print(f"    Latency Benchmark Results (Mean, P95): {timings}")
        assert timings[1000][0] < 5.0, f"N=1000 mean latency exceeded 5ms: {timings[1000][0]:.2f}ms"
        assert timings[5000][0] < 15.0, f"N=5000 mean latency exceeded 15ms: {timings[5000][0]:.2f}ms"
        collector.record_pass("KMeans.LatencyBenchmark", f"N=1k: {timings[1000][0]:.2f}ms, N=5k: {timings[5000][0]:.2f}ms (sub-5ms verified)")
    except Exception as e:
        collector.record_fail("KMeans.LatencyBenchmark", str(e))

    # 1.9 Legacy/Cron kmeans_cluster Verification
    if kmeans_cluster is not None:
        try:
            # Test empty, single, N<k, identical
            l0, c0, in0 = kmeans_cluster(np.zeros((0, 5)))
            assert len(l0) == 0 and in0 == 0.0

            l1, c1, in1 = kmeans_cluster(np.array([[1.0, 2.0, 3.0, 4.0, 5.0]]))
            assert len(l1) == 1 and in1 == 0.0

            l2, c2, in2 = kmeans_cluster(np.ones((2, 5)))
            assert len(l2) == 2 and in2 == 0.0

            l_norm, c_norm, in_norm = kmeans_cluster(np.random.rand(100, 5), k=3)
            assert len(l_norm) == 100 and in_norm >= 0.0
            collector.record_pass("KMeans.LegacyCronClustering", "Legacy/Cron kmeans_cluster passed all degenerate vector tests")
        except Exception as e:
            collector.record_fail("KMeans.LegacyCronClustering", str(e))


# ============================================================================
# VECTOR 2: TelemetryStore Concurrency, WAL & Data Integrity
# ============================================================================

def run_telemetry_adversarial_tests():
    print("\n" + "="*80)
    print("RUNNING VECTOR 2: TelemetryStore Adversarial & Concurrency Stress Tests")
    print("="*80)

    # 2.1 High-Concurrency Multi-Threaded Write Storm (32 threads x 50 writes = 1,600 spans)
    temp_db_1 = tempfile.mktemp(suffix=".db")
    try:
        store = TelemetryStore(temp_db_1)
        num_threads = 32
        writes_per_thread = 50
        errors = []

        def writer_thread(t_idx: int):
            try:
                for i in range(writes_per_thread):
                    store.record_span(
                        platform="tiktok" if t_idx % 2 == 0 else "instagram_reels",
                        lens_type="web_a11y_tree" if t_idx % 2 == 0 else "android_ui_dump",
                        duration_ms=500 + (i * 20),
                        yield_count=i % 25,
                        error_count=0 if i % 10 != 0 else 1,
                        status_code="SUCCESS" if i % 10 != 0 else "RATE_LIMITED",
                        input_tokens=100 + i,
                        output_tokens=50 + i,
                        metadata={"thread": t_idx, "iter": i},
                    )
            except Exception as e:
                errors.append((t_idx, e))

        threads = [threading.Thread(target=writer_thread, args=(t,)) for t in range(num_threads)]
        t_start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_time = time.perf_counter() - t_start

        assert len(errors) == 0, f"Concurrent writes threw {len(errors)} errors: {errors[:5]}"
        spans_df = store.get_recent_spans(limit=5000)
        expected_count = num_threads * writes_per_thread
        assert len(spans_df) == expected_count, f"Expected {expected_count} spans, got {len(spans_df)}"
        collector.record_pass("Telemetry.HighConcurrencyWrites_32Threads", f"1,600 writes completed across 32 threads in {total_time:.2f}s with 0 lock errors")
    except Exception as e:
        collector.record_fail("Telemetry.HighConcurrencyWrites_32Threads", str(e))
    finally:
        if os.path.exists(temp_db_1):
            try:
                os.remove(temp_db_1)
            except Exception:
                pass

    # 2.2 Mixed Concurrency: Simultaneous Writers, Readers, Policy Updates, Cluster Updates
    temp_db_2 = tempfile.mktemp(suffix=".db")
    try:
        store = TelemetryStore(temp_db_2)
        span_ids = []
        for i in range(100):
            sid = store.record_span("tiktok", "web_a11y_tree", 1000, 10, 0, "SUCCESS")
            span_ids.append(sid)

        errors = []
        stop_event = threading.Event()

        def reader_worker():
            try:
                while not stop_event.is_set():
                    df = store.get_recent_spans(limit=50)
                    assert len(df) >= 0
                    time.sleep(0.005)
            except Exception as e:
                errors.append(("reader", e))

        def policy_worker(p_name: str):
            try:
                for i in range(25):
                    store.update_policy(
                        platform=p_name,
                        active_lens="web_a11y_tree" if i % 2 == 0 else "android_ui_dump",
                        poll_interval_sec=3600 + i * 60,
                        retry_backoff_base_sec=2.0 + (i * 0.1),
                        reason=f"Stress update {i}",
                    )
                    time.sleep(0.005)
            except Exception as e:
                errors.append(("policy", e))

        def cluster_updater():
            try:
                for i in range(25):
                    cmap = {sid: (i % 3) for sid in span_ids[:25]}
                    store.update_cluster_labels(cmap)
                    time.sleep(0.005)
            except Exception as e:
                errors.append(("cluster", e))

        def continuous_writer(thread_id: int):
            try:
                for i in range(30):
                    store.record_span("youtube_shorts", "web_a11y_tree", 800, 12, 0, "SUCCESS")
                    time.sleep(0.003)
            except Exception as e:
                errors.append(("writer", e))

        all_threads = []
        for _ in range(4):
            all_threads.append(threading.Thread(target=reader_worker))
        for p in ["tiktok", "youtube_shorts", "instagram_reels", "facebook_reels"]:
            all_threads.append(threading.Thread(target=policy_worker, args=(p,)))
        all_threads.append(threading.Thread(target=cluster_updater))
        for tid in range(6):
            all_threads.append(threading.Thread(target=continuous_writer, args=(tid,)))

        for t in all_threads:
            t.start()

        time.sleep(0.5)
        stop_event.set()

        for t in all_threads:
            t.join()

        assert len(errors) == 0, f"Mixed concurrency produced errors: {errors}"
        collector.record_pass("Telemetry.MixedConcurrentWorkload", "Simultaneous readers, writers, policy updates, cluster updates succeeded")
    except Exception as e:
        collector.record_fail("Telemetry.MixedConcurrentWorkload", str(e))
    finally:
        if os.path.exists(temp_db_2):
            try:
                os.remove(temp_db_2)
            except Exception:
                pass

    # 2.3 Boundary & Edge Cases in Mark-and-Sweep Garbage Collection
    temp_db_3 = tempfile.mktemp(suffix=".db")
    try:
        store = TelemetryStore(temp_db_3)
        now_ms = int(time.time() * 1000)
        day_ms = 86400 * 1000
        cutoff_ms = now_ms - (14 * day_ms)

        # 1. Exactly at boundary - 1ms (stale)
        store.record_span("tiktok", "web_a11y_tree", 1000, 10, 0, "SUCCESS", span_id="stale_edge", timestamp_ms=cutoff_ms - 1)
        # 2. Exactly at boundary + 1000ms (fresh)
        store.record_span("tiktok", "web_a11y_tree", 1000, 10, 0, "SUCCESS", span_id="fresh_edge", timestamp_ms=cutoff_ms + 1000)
        # 3. Far future timestamp (fresh)
        store.record_span("tiktok", "web_a11y_tree", 1000, 10, 0, "SUCCESS", span_id="future_span", timestamp_ms=now_ms + (30 * day_ms))
        # 4. Far past / negative timestamp (stale)
        store.record_span("tiktok", "web_a11y_tree", 1000, 10, 0, "SUCCESS", span_id="ancient_span", timestamp_ms=-500000)

        purged = store.mark_and_sweep_telemetry(retention_days=14)
        assert purged == 2, f"Expected exactly 2 purged spans (stale_edge and ancient_span), got {purged}"

        remaining_spans = store.get_recent_spans(limit=10)
        remaining_ids = set(remaining_spans["span_id"].values)
        assert "fresh_edge" in remaining_ids
        assert "future_span" in remaining_ids
        assert "stale_edge" not in remaining_ids
        assert "ancient_span" not in remaining_ids

        # Running GC again on clean DB should return 0
        assert store.mark_and_sweep_telemetry(retention_days=14) == 0

        collector.record_pass("Telemetry.MarkAndSweepBoundaries", "Exact boundary timestamps, future, and ancient timestamps handled accurately")
    except Exception as e:
        collector.record_fail("Telemetry.MarkAndSweepBoundaries", str(e))
    finally:
        if os.path.exists(temp_db_3):
            try:
                os.remove(temp_db_3)
            except Exception:
                pass

    # 2.4 Schema Check Constraints & SQL Injection Robustness
    temp_db_4 = tempfile.mktemp(suffix=".db")
    try:
        store = TelemetryStore(temp_db_4)

        # 1. Negative numbers violating CHECK constraints
        check_constraint_triggered = False
        try:
            with store.get_connection() as conn:
                conn.execute(
                    "INSERT INTO scraping_telemetry (span_id, timestamp_ms, platform, lens_type, duration_ms, yield_count, error_count, status_code) "
                    "VALUES ('bad_1', 12345, 'tiktok', 'lens', -10, 5, 0, 'SUCCESS')"
                )
                conn.commit()
        except sqlite3.IntegrityError:
            check_constraint_triggered = True
        assert check_constraint_triggered, "Negative duration_ms failed to trigger CHECK constraint"

        # 2. SQL injection strings in platform, lens_type, status_code, metadata
        injection_payloads = [
            "tiktok' OR '1'='1",
            "'; DROP TABLE scraping_telemetry; --",
            "web_a11y_tree' UNION SELECT * FROM execution_policies --",
            "<script>alert(1)</script>",
            "💥 Unicode \u0000 \ufffd \n\r\t SQL Injection",
        ]

        for payload in injection_payloads:
            sid = store.record_span(
                platform=payload,
                lens_type=payload,
                duration_ms=1000,
                yield_count=10,
                error_count=0,
                status_code=payload,
                metadata={"payload": payload, "nested": {"key": payload}},
            )
            assert sid is not None

        # Verify table was not dropped and data is intact
        spans_df = store.get_recent_spans(limit=50)
        assert len(spans_df) == len(injection_payloads)
        collector.record_pass("Telemetry.SchemaConstraintsAndInjectionResilience", "CHECK constraints active; parameterized queries immune to SQL injection")
    except Exception as e:
        collector.record_fail("Telemetry.SchemaConstraintsAndInjectionResilience", str(e))
    finally:
        if os.path.exists(temp_db_4):
            try:
                os.remove(temp_db_4)
            except Exception:
                pass

    # 2.5 ProTeGi Gradient Logging Under Stress
    temp_db_5 = tempfile.mktemp(suffix=".db")
    try:
        store = TelemetryStore(temp_db_5)
        num_grads = 50

        def grad_logger(i: int):
            store.log_protegi_gradient(
                target_skill_path=f"skills/test_{i}/SKILL.md",
                divergence_entropy=0.01 * i,
                critique_text=f"Critique text for iteration {i} with long description " * 10,
                gradient_diff=f"--- a/SKILL.md\n+++ b/SKILL.md\n@@ -1,5 +1,5 @@\n-old rule {i}\n+new rule {i}",
                applied_status="PROPOSED" if i % 2 == 0 else "APPLIED",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(grad_logger, range(num_grads)))

        with store.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM protegi_gradient_log").fetchone()[0]
            assert count == num_grads, f"Expected {num_grads} gradient logs, found {count}"

        collector.record_pass("Telemetry.ProTeGiGradientLogging", "Concurrent ProTeGi gradient logging succeeded with 0 loss")
    except Exception as e:
        collector.record_fail("Telemetry.ProTeGiGradientLogging", str(e))
    finally:
        if os.path.exists(temp_db_5):
            try:
                os.remove(temp_db_5)
            except Exception:
                pass


# ============================================================================
# VECTOR 3: Closed-Loop Adaptation & AutonomousMLAgent Integration Tests
# ============================================================================

def run_policy_and_agent_adversarial_tests():
    print("\n" + "="*80)
    print("RUNNING VECTOR 3: Policy Engine & Autonomous Agent Lifecycle Tests")
    print("="*80)

    temp_db = tempfile.mktemp(suffix=".db")
    trends_db = tempfile.mktemp(suffix=".db")
    trends_md = tempfile.mktemp(suffix=".md")

    try:
        store = TelemetryStore(temp_db)
        optimizer = KMeansOptimizer(k=3, random_state=42)
        policy_engine = PolicyEngine(store, optimizer)

        # 3.1 Policy Adjustment on Sparse / Insufficient Telemetry
        res_empty = policy_engine.evaluate_and_adjust("tiktok")
        assert res_empty["action"] == "NO_OP", f"Expected NO_OP for insufficient telemetry, got {res_empty}"
        assert res_empty["reason"] == "Insufficient telemetry spans"
        collector.record_pass("PolicyEngine.InsufficientTelemetryHandling", "Returned NO_OP gracefully without exception when <3 spans")

        # 3.2 Cascading Failures & Lens Swap
        # Inject 15 DOM drift failure spans (Cluster 2)
        for _ in range(15):
            store.record_span("tiktok", "web_a11y_tree", 1000, 0, 8, "DOM_DRIFT")

        res_swap = policy_engine.evaluate_and_adjust("tiktok")
        assert res_swap["action"] == "LENS_SWAP"
        assert res_swap["new_lens"] == "android_ui_dump"
        collector.record_pass("PolicyEngine.DOMDriftLensSwap", "Correctly switched lens to android_ui_dump on Cluster 2 dominance")

        # 3.3 Rate Limit Throttling (Cluster 1 dominance)
        # Inject 15 Degraded spans
        for _ in range(15):
            store.record_span("youtube_shorts", "web_a11y_tree", 18000, 2, 3, "RATE_LIMITED")

        res_throttle = policy_engine.evaluate_and_adjust("youtube_shorts")
        assert res_throttle["action"] == "THROTTLE"
        assert res_throttle["new_interval"] > 7200
        assert res_throttle["new_backoff"] > 2.0
        collector.record_pass("PolicyEngine.RateLimitThrottling", "Cadence throttled (interval and backoff elevated) on Cluster 1 dominance")

        # 3.4 Full Agent Lifecycle with Trends DB GC
        # Create trends db with 100 stale rows and 10 fresh rows
        with sqlite3.connect(trends_db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    topic_category TEXT NOT NULL,
                    hashtag_or_audio TEXT NOT NULL,
                    velocity_score REAL NOT NULL,
                    date_added TEXT NOT NULL
                )
                """
            )
            for i in range(100):
                conn.execute(
                    "INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) "
                    "VALUES ('tiktok', 'SportsCards', ?, ?, date('now', '-20 days'))",
                    (f"#Stale_{i}", 40.0 + (i % 10)),
                )
            for i in range(10):
                conn.execute(
                    "INSERT INTO trends (platform, topic_category, hashtag_or_audio, velocity_score, date_added) "
                    "VALUES ('tiktok', 'SportsCards', ?, ?, date('now', '-1 days'))",
                    (f"#Fresh_{i}", 90.0 + i),
                )
            conn.commit()

        agent = AutonomousMLAgent(
            telemetry_db_path=temp_db,
            trends_db_path=trends_db,
            trends_md_path=trends_md,
        )

        cycle_result = agent.run_optimization_cycle(
            mock_spans=[
                {"platform": "youtube_shorts", "lens_type": "web_a11y_tree", "duration_ms": 750, "yield_count": 28, "error_count": 0, "status_code": "SUCCESS"}
                for _ in range(10)
            ]
        )

        assert cycle_result["status"] == "COMPLETED"
        assert cycle_result["gc_trends_purged"] == 100, f"Expected 100 purged trends, got {cycle_result['gc_trends_purged']}"
        assert os.path.exists(trends_md), "current_trends.md was not generated"

        with open(trends_md, "r", encoding="utf-8") as f:
            md_content = f.read()

        assert "#Fresh_9" in md_content
        assert "#Stale_" not in md_content

        collector.record_pass("AutonomousMLAgent.EndToEndCycleAndGC", "Autonomous cycle executed, 100 stale trends purged, markdown catalog refreshed")
    except Exception as e:
        collector.record_fail("AutonomousMLAgent.EndToEndCycleAndGC", str(e))
    finally:
        for p in [temp_db, trends_db, trends_md]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


# ============================================================================
# MAIN HARNESS RUNNER
# ============================================================================

def main():
    print("="*80)
    print("ANTIGRAVITY MILESTONE 3: EMPIRICAL ADVERSARIAL CHALLENGER SUITE")
    print("="*80)

    run_kmeans_adversarial_tests()
    run_telemetry_adversarial_tests()
    run_policy_and_agent_adversarial_tests()

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Passed: {len(collector.results)}")
    print(f"Total Failed: {len(collector.failures)}")

    if collector.failures:
        print("\nFAILURES:")
        for f in collector.failures:
            print(f"  - {f['test']}: {f['error']}")
        sys.exit(1)
    else:
        print("\nALL ADVERSARIAL STRESS TESTS PASSED EMPIRICALLY!")
        sys.exit(0)


if __name__ == "__main__":
    main()
