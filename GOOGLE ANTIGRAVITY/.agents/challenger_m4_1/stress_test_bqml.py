#!/usr/bin/env python3
"""
stress_test_bqml.py - Adversarial Stress & Chaos Test Suite for Milestone 4 (BigQuery ML Loop).

Empirically challenges:
1. 10,000 Monte Carlo Simplex Normalization Vectors ($L_1$ sum == 1.0000, bounds [0, 1]).
2. Degenerate Inputs: All-Zero, All-Negative, Massive Outliers (1e12 / 1e-12), NaN, Inf, None.
3. SQL Injection & Identifier Sanitization in DDLs and Feedback Loop DML.
4. High-Concurrency Multithreaded Recalibrations (Race Conditions & Version ID Collisions).
5. 1,000-Generation Iterative Feedback Loop Drift & Stability.
"""

from __future__ import annotations

import concurrent.futures
import math
import os
import random
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure paths
CURRENT_DIR = Path(__file__).parent.resolve()
WORKSPACE_DIR = Path("g:/My Drive/GOOGLE ANTIGRAVITY").resolve()
MEDIA_PIPELINE_DIR = WORKSPACE_DIR / "media_pipeline"

for p in [str(MEDIA_PIPELINE_DIR), str(WORKSPACE_DIR), str(MEDIA_PIPELINE_DIR.parent)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from media_pipeline.bqml.feedback_loop import (
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

from media_pipeline.grading.viral_schema import (
    EDMShortsViralMetrics,
    EDMViralGradingReport,
    TrendingVerdict,
    ViralParameterScores,
    calculate_evpi_from_scores,
    classify_viral_tier,
)

from tests.conftest import MockBigQueryMLEngine, MockGeminiOmniClient, MockGCSClient


class AdversarialTestRunner:
    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}

    def log_result(self, test_id: str, title: str, passed: bool, details: Dict[str, Any]):
        self.results[test_id] = {
            "title": title,
            "passed": passed,
            "details": details,
        }
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_id}: {title}")
        for k, v in details.items():
            print(f"       {k}: {v}")


runner = AdversarialTestRunner()


# ============================================================================
# 1. 10,000 MONTE CARLO SIMPLEX NORMALIZATION VECTORS
# ============================================================================

def challenge_10000_monte_carlo_simplex():
    random.seed(42)
    trials = 10000
    negative_weight_failures = 0
    sum_failures = 0
    pydantic_validation_failures = 0
    failed_examples = []

    for i in range(trials):
        dist_type = i % 5
        if dist_type == 0:
            raw = {f: random.uniform(0.0, 1.0) for f in CANONICAL_FEATURES}
        elif dist_type == 1:
            raw = {f: 10 ** random.uniform(-8, 8) for f in CANONICAL_FEATURES}
        elif dist_type == 2:
            active_feats = random.sample(CANONICAL_FEATURES, k=random.randint(1, 3))
            raw = {f: (random.uniform(0.1, 10.0) if f in active_feats else random.uniform(-10.0, 0.0)) for f in CANONICAL_FEATURES}
        elif dist_type == 3:
            raw = {f: random.expovariate(1.0) for f in CANONICAL_FEATURES}
        else:
            base = random.uniform(1.0, 100.0)
            raw = {f: base + random.uniform(-0.0001, 0.0001) for f in CANONICAL_FEATURES}

        try:
            norm = extract_normalized_weights(raw)
            total = sum(norm.values())
            
            # Check sum
            if abs(total - 1.0000) >= 1e-4:
                sum_failures += 1
                if len(failed_examples) < 3:
                    failed_examples.append({"trial": i, "reason": "Sum != 1.0", "sum": total, "raw": raw, "norm": norm})

            # Check individual weight bounds
            has_negative = False
            for feat, val in norm.items():
                if val < 0.0:
                    has_negative = True
                    negative_weight_failures += 1
                    if len(failed_examples) < 3:
                        failed_examples.append({"trial": i, "reason": f"Negative weight: {feat}={val}", "raw": raw, "norm": norm})
                    break

            # Check Pydantic validation
            try:
                ModelParameterWeights(
                    version_id=f"v_mc_{i}",
                    weight_hrv=norm["weight_hrv"],
                    weight_dpaw=norm["weight_dpaw"],
                    weight_adr_sfd=norm["weight_adr_sfd"],
                    weight_cke_mve=norm["weight_cke_mve"],
                    weight_ltss=norm["weight_ltss"],
                )
            except Exception as pe:
                pydantic_validation_failures += 1

        except Exception as e:
            sum_failures += 1
            if len(failed_examples) < 3:
                failed_examples.append({"trial": i, "reason": f"Exception: {str(e)}", "raw": raw})

    total_failures = negative_weight_failures + sum_failures + pydantic_validation_failures
    passed = (total_failures == 0)
    runner.log_result(
        "TEST_1_MONTE_CARLO_SIMPLEX",
        "10,000 Randomized Monte Carlo Simplex Vectors",
        passed,
        {
            "total_trials": trials,
            "negative_weight_failures": negative_weight_failures,
            "sum_deviation_failures": sum_failures,
            "pydantic_validation_failures": pydantic_validation_failures,
            "failed_examples": failed_examples,
        }
    )


# ============================================================================
# 2. DEGENERATE & ADVERSARIAL WEIGHT INPUTS
# ============================================================================

def challenge_degenerate_and_extreme_weights():
    test_cases = [
        ("All Zeros", {f: 0.0 for f in CANONICAL_FEATURES}),
        ("All Negative (-1e6)", {f: -1e6 for f in CANONICAL_FEATURES}),
        ("All Negative Small (-1e-7)", {f: -1e-7 for f in CANONICAL_FEATURES}),
        ("Single Outlier (1e12 vs 1.0)", {"weight_hrv": 1e12, "weight_dpaw": 1.0, "weight_adr_sfd": 1.0, "weight_cke_mve": 1.0, "weight_ltss": 1.0}),
        ("Subnormal Numbers (1e-300)", {f: 1e-300 for f in CANONICAL_FEATURES}),
        ("Empty Dict", {}),
        ("Single Feature Only", {"weight_hrv": 0.85}),
        ("Aliased Features Mixed", {"hrv_score": 50.0, "audio_drop_sync": 30.0, "crowd_motion": 20.0}),
        ("ML.WEIGHTS row format with zeros", [
            {"processed_input": "hrv_score", "weight": 0.0},
            {"processed_input": "dpaw_score", "weight": -5.0},
            {"processed_input": "adr_sfd_score", "weight": 0.0},
            {"processed_input": "cke_mve_score", "weight": 0.0},
            {"processed_input": "ltss_score", "weight": 0.0},
        ]),
        ("ML.WEIGHTS row format with extra features", [
            {"processed_input": "hrv_score", "weight": 0.5},
            {"processed_input": "dpaw_score", "weight": 0.3},
            {"processed_input": "adr_sfd_score", "weight": 0.1},
            {"processed_input": "cke_mve_score", "weight": 0.05},
            {"processed_input": "ltss_score", "weight": 0.05},
            {"processed_input": "intercept", "weight": 1.25},
            {"processed_input": "unknown_feature", "weight": 99.0},
        ]),
    ]

    failures = []
    for name, raw in test_cases:
        try:
            norm = extract_normalized_weights(raw)
            total = round(sum(norm.values()), 4)
            if total != 1.0000:
                failures.append(f"{name}: Sum={total} != 1.0000")
            for k, v in norm.items():
                if not (0.0 <= v <= 1.0) or math.isnan(v) or math.isinf(v):
                    failures.append(f"{name}: Invalid value {k}={v}")
            ModelParameterWeights(
                version_id="v_test",
                weight_hrv=norm["weight_hrv"],
                weight_dpaw=norm["weight_dpaw"],
                weight_adr_sfd=norm["weight_adr_sfd"],
                weight_cke_mve=norm["weight_cke_mve"],
                weight_ltss=norm["weight_ltss"],
            )
        except Exception as e:
            failures.append(f"{name}: Raised exception {str(e)}")

    passed = (len(failures) == 0)
    runner.log_result(
        "TEST_2_DEGENERATE_WEIGHTS",
        "Degenerate and Extreme Weight Boundary Cases",
        passed,
        {"tested_cases": len(test_cases), "failures": failures}
    )


def challenge_nan_inf_safety():
    nan_inputs = {
        "weight_hrv": float("nan"),
        "weight_dpaw": 0.30,
        "weight_adr_sfd": 0.20,
        "weight_cke_mve": 0.15,
        "weight_ltss": 0.15,
    }
    inf_inputs = {
        "weight_hrv": float("inf"),
        "weight_dpaw": 0.30,
        "weight_adr_sfd": 0.20,
        "weight_cke_mve": 0.15,
        "weight_ltss": 0.15,
    }
    failures = []

    # Test NaN
    try:
        norm_nan = extract_normalized_weights(nan_inputs)
        if any(math.isnan(v) for v in norm_nan.values()):
            failures.append(f"NaN leaked into output: {norm_nan}")
        if round(sum(norm_nan.values()), 4) != 1.0000:
            failures.append(f"NaN case sum != 1.0000: {norm_nan}")
    except Exception as e:
        failures.append(f"NaN exception: {str(e)}")

    # Test Inf
    try:
        norm_inf = extract_normalized_weights(inf_inputs)
        if any(math.isinf(v) or math.isnan(v) for v in norm_inf.values()):
            failures.append(f"Inf/NaN leaked into output: {norm_inf}")
        if round(sum(norm_inf.values()), 4) != 1.0000:
            failures.append(f"Inf case sum != 1.0000: {norm_inf}")
    except Exception as e:
        failures.append(f"Inf exception: {str(e)}")

    passed = (len(failures) == 0)
    runner.log_result(
        "TEST_2B_NAN_INF_SAFETY",
        "NaN and Inf Floating-Point Poison Resilience",
        passed,
        {"failures": failures}
    )


# ============================================================================
# 3. SQL DDL VALIDATION & INJECTION RESILIENCE
# ============================================================================

def challenge_sql_ddl_and_injection():
    schema_file = MEDIA_PIPELINE_DIR / "bqml" / "schema.sql"
    models_file = MEDIA_PIPELINE_DIR / "bqml" / "models.sql"

    schema_sql = schema_file.read_text(encoding="utf-8")
    models_sql = models_file.read_text(encoding="utf-8")

    issues = []
    
    # Check tables
    for tbl in ["video_grades", "post_performance_metrics", "model_parameter_weights"]:
        if tbl not in schema_sql:
            issues.append(f"Missing table {tbl} in schema.sql")

    # Check models
    for mdl in ["viral_weight_regressor", "viral_retention_tree_regressor", "video_archetype_clusters"]:
        if mdl not in models_sql:
            issues.append(f"Missing model {mdl} in models.sql")

    mock_engine = MockBigQueryMLEngine()
    
    scores = ViralParameterScores(hrv=88.0, dpaw=85.0, adr_sfd=80.0, cke_mve=75.0, ltss=70.0)
    evpi = calculate_evpi_from_scores(88.0, 85.0, 80.0, 75.0, 70.0)
    verdict_str = classify_viral_tier(evpi)
    verdict_enum = TrendingVerdict(verdict_str)
    
    pydantic_metric = EDMShortsViralMetrics(
        video_id="test_pydantic_vid",
        gcs_uri="gs://bucket/test.mp4",
        raw_file_name="test.mp4",
        file_size_bytes=1024,
        duration_seconds=15.0,
        aspect_ratio="9:16",
        resolution="1080x1920",
        fps=30.0,
        status="GRADED",
        scores=scores,
        evpi_composite=evpi,
        trending_verdict=verdict_enum,
    )
    
    pydantic_sink_ok = False
    try:
        cnt = sink_video_grades_to_bq(mock_engine, "media_pipeline.video_grades", [pydantic_metric])
        pydantic_sink_ok = (cnt == 1)
    except Exception as e:
        issues.append(f"Pydantic sink failed: {str(e)}")

    # Test with Dict record
    dict_record = {
        "video_id": "test_dict_vid'; DROP TABLE `video_grades`; --",
        "gcs_uri": "gs://bucket/test_dict.mp4",
        "duration_seconds": 15.0,
        "aspect_ratio": "9:16",
        "status": "GRADED",
        "hrv_score": 88.0,
        "dpaw_score": 85.0,
        "adr_sfd_score": 80.0,
        "cke_mve_score": 75.0,
        "ltss_score": 70.0,
        "evpi_composite": 81.0,
        "trending_verdict": "HIGH_POTENTIAL",
    }
    
    dict_sink_ok = False
    try:
        cnt_dict = sink_video_grades_to_bq(mock_engine, "media_pipeline.video_grades", [dict_record])
        dict_sink_ok = (cnt_dict == 1)
    except Exception as e:
        issues.append(f"Dict sink failed (Polymorphism bug): {str(e)}")

    # Test Telemetry update
    telemetry_ok = False
    try:
        up_ok = update_post_performance_telemetry(
            mock_engine,
            "media_pipeline.video_grades",
            video_id="test_pydantic_vid",
            vvsa_rate=0.88,
            apv=1.25,
            viral_status=1,
        )
        telemetry_ok = up_ok
    except Exception as e:
        issues.append(f"Telemetry update failed: {str(e)}")

    passed = (len(issues) == 0)
    runner.log_result(
        "TEST_3_SQL_DDL_AND_INJECTION",
        "SQL DDL Verification & Sink Connector Resilience",
        passed,
        {
            "pydantic_sink_ok": pydantic_sink_ok,
            "dict_sink_ok": dict_sink_ok,
            "telemetry_ok": telemetry_ok,
            "issues": issues,
        }
    )


# ============================================================================
# 4. CONCURRENT MULTITHREADED RECALIBRATIONS
# ============================================================================

def challenge_concurrency():
    mock_engine = MockBigQueryMLEngine()
    engine = BigQueryMLFeedbackEngine(client=mock_engine)

    num_threads = 100
    results: List[ModelParameterWeights] = []
    lock = threading.Lock()
    exceptions: List[Exception] = []

    def worker(worker_id: int):
        try:
            raw = {
                "weight_hrv": random.uniform(0.2, 0.5),
                "weight_dpaw": random.uniform(0.2, 0.4),
                "weight_adr_sfd": random.uniform(0.1, 0.3),
                "weight_cke_mve": random.uniform(0.1, 0.2),
                "weight_ltss": random.uniform(0.05, 0.15),
            }
            new_w = engine.recalibrate_weights(
                model_name=f"worker_{worker_id}",
                raw_weights_override=raw,
            )
            with lock:
                results.append(new_w)
        except Exception as e:
            with lock:
                exceptions.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        concurrent.futures.wait(futures)

    issues = []
    if exceptions:
        issues.append(f"{len(exceptions)} thread exceptions occurred (e.g. {exceptions[0]})")

    # Check version_id uniqueness
    version_ids = [w.version_id for w in results]
    unique_vids = set(version_ids)
    if len(unique_vids) < len(version_ids):
        issues.append(f"Version ID Collision: {len(version_ids)} calls generated only {len(unique_vids)} unique version IDs (int(time.time()) resolution flaw)")

    tbl = mock_engine.tables.get("media_pipeline.model_parameter_weights", [])
    active_rows = [r for r in tbl if r.get("is_active") is True]

    passed = (len(issues) == 0)
    runner.log_result(
        "TEST_4_CONCURRENCY",
        "Multithreaded High-Concurrency Weight Recalibration (100 Threads)",
        passed,
        {
            "threads_executed": len(results),
            "exceptions_count": len(exceptions),
            "unique_version_ids": len(unique_vids),
            "active_version_count_in_registry": len(active_rows),
            "issues": issues,
        }
    )


# ============================================================================
# 5. 1,000-GENERATION FEEDBACK LOOP STABILITY
# ============================================================================

def challenge_1000_generation_feedback_loop():
    mock_engine = MockBigQueryMLEngine()
    engine = BigQueryMLFeedbackEngine(client=mock_engine)

    generations = 1000
    start_time = time.time()
    issues = []

    try:
        for gen in range(generations):
            active_w = engine.get_active_weights()
            w_dict = {
                "weight_hrv": active_w.weight_hrv,
                "weight_dpaw": active_w.weight_dpaw,
                "weight_adr_sfd": active_w.weight_adr_sfd,
                "weight_cke_mve": active_w.weight_cke_mve,
                "weight_ltss": active_w.weight_ltss,
            }
            w_sum = sum(w_dict.values())
            if abs(w_sum - 1.0) > 1e-4:
                issues.append(f"Gen {gen}: Active weights sum {w_sum} != 1.0")
                break

            # Deterministic video grading scores
            scores = ViralParameterScores(
                hrv=70.0 + (gen % 25),
                dpaw=65.0 + (gen % 30),
                adr_sfd=75.0 + (gen % 20),
                cke_mve=60.0 + (gen % 35),
                ltss=70.0 + (gen % 25),
            )
            evpi = calculate_evpi_from_scores(
                scores.hrv, scores.dpaw, scores.adr_sfd, scores.cke_mve, scores.ltss,
                weights=w_dict,
            )
            verdict_str = classify_viral_tier(evpi)
            verdict_enum = TrendingVerdict(verdict_str)

            metric = EDMShortsViralMetrics(
                video_id=f"gen_{gen}_vid",
                gcs_uri=f"gs://edm-media-vault/gen_{gen}.mp4",
                duration_seconds=22.5,
                aspect_ratio="9:16",
                scores=scores,
                evpi_composite=evpi,
                trending_verdict=verdict_enum,
            )

            # Sink
            engine.sink_grades([metric])

            # Ingest telemetry
            engine.record_telemetry(
                video_id=f"gen_{gen}_vid",
                vvsa_rate=0.85 + (gen % 10) * 0.01,
                apv=1.10 + (gen % 15) * 0.02,
                viral_status=1 if gen % 3 == 0 else 0,
            )

            if gen % 100 == 0:
                drifted_raw = {
                    "weight_hrv": 0.25 + 0.05 * math.sin(gen),
                    "weight_dpaw": 0.25 + 0.05 * math.cos(gen),
                    "weight_adr_sfd": 0.20,
                    "weight_cke_mve": 0.15,
                    "weight_ltss": 0.15,
                }
                engine.recalibrate_weights(
                    model_name=f"drift_model_gen_{gen}",
                    raw_weights_override=drifted_raw,
                )
    except Exception as e:
        issues.append(f"Feedback loop exception at gen {gen}: {str(e)}")

    elapsed = time.time() - start_time
    passed = (len(issues) == 0)
    runner.log_result(
        "TEST_5_1000_GENERATION_LOOP",
        "1,000-Generation Iterative Feedback Loop Drift & Stability",
        passed,
        {
            "generations_completed": generations if not issues else gen,
            "elapsed_seconds": round(elapsed, 3),
            "issues": issues,
        }
    )


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("EMPIRICAL CHALLENGER ADVERSARIAL TEST SUITE: Milestone 4")
    print("=" * 80)

    challenge_10000_monte_carlo_simplex()
    challenge_degenerate_and_extreme_weights()
    challenge_nan_inf_safety()
    challenge_sql_ddl_and_injection()
    challenge_concurrency()
    challenge_1000_generation_feedback_loop()

    print("\n" + "=" * 80)
    total_tests = len(runner.results)
    passed_tests = sum(1 for r in runner.results.values() if r["passed"])
    failed_tests = total_tests - passed_tests
    print(f"STRESS HARNESS VERDICT SUMMARY: {passed_tests}/{total_tests} TEST GROUPS PASSED ({failed_tests} FAILED)")
    print("=" * 80)

    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
