#!/usr/bin/env python3
"""
test_adversarial_m4.py - Comprehensive Adversarial Stress Test Suite for Milestone 4 (BigQuery ML Loop).

Covers:
1. Schema consistency & DDL syntax validation across all 3 tables and compatibility views.
2. BQML options, model architectures, and query filter guards (NULL handling, status filtering).
3. Simplex weight normalization stress: negative weights, all zeros, extreme disparities, denormals, floating point precision drift, garbage feature keys, casing/whitespace variations.
4. Multi-version weight lifecycle, consecutive versioning, single-active-version invariant, and historical rollback mechanisms.
5. Ingestion & telemetry updater stress: handling unreleased videos (NULL APV), DLQ failures, corrupted dictionaries, and high-volume batch sinks.
6. Closed-loop ML feedback simulation: telemetry-driven weight adaptation and downstream EVPI re-scoring.
"""

from __future__ import annotations

import copy
import os
import re
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

# Ensure parent directory is in sys.path
CURRENT_DIR = Path(__file__).parent.resolve()
MEDIA_PIPELINE_DIR = CURRENT_DIR.parent.resolve()
if str(MEDIA_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(MEDIA_PIPELINE_DIR))
if str(MEDIA_PIPELINE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(MEDIA_PIPELINE_DIR.parent))

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
    TrendingVerdict,
    ViralParameterScores,
    calculate_evpi,
    get_verdict_from_evpi,
)


# ============================================================================
# ADVERSARIAL TEST HARNESS: Mock BigQuery Engine with Full DDL & Rollback
# ============================================================================

class AdversarialMockBigQueryEngine:
    """
    In-memory mock BigQuery Engine supporting DDL tracking, DML updates,
    multi-version weight history, and historical rollback capabilities.
    """
    def __init__(self):
        self.tables: Dict[str, List[Dict[str, Any]]] = {
            "media_pipeline.video_grades": [],
            "media_pipeline.post_performance_metrics": [],
            "media_pipeline.model_parameter_weights": [
                ModelParameterWeights(
                    version_id="v1.0.0_baseline",
                    weight_hrv=0.25,
                    weight_dpaw=0.25,
                    weight_adr_sfd=0.20,
                    weight_cke_mve=0.15,
                    weight_ltss=0.15,
                    is_active=True,
                ).model_dump()
            ],
        }
        self.models: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def sink_video_grades(self, metrics: List[Any]) -> int:
        with self.lock:
            count = 0
            for m in metrics:
                if hasattr(m, "model_dump"):
                    dump = m.model_dump()
                    if "scores" in dump and isinstance(dump["scores"], dict):
                        dump["hrv_score"] = dump["scores"].get("hrv", 0.0)
                        dump["dpaw_score"] = dump["scores"].get("dpaw", 0.0)
                        dump["adr_sfd_score"] = dump["scores"].get("adr_sfd", 0.0)
                        dump["cke_mve_score"] = dump["scores"].get("cke_mve", 0.0)
                        dump["ltss_score"] = dump["scores"].get("ltss", 0.0)
                    if "trending_verdict" in dump and hasattr(dump["trending_verdict"], "value"):
                        dump["trending_verdict"] = dump["trending_verdict"].value
                    self.tables["media_pipeline.video_grades"].append(dump)
                elif isinstance(m, dict):
                    self.tables["media_pipeline.video_grades"].append(dict(m))
                count += 1
            return count

    def update_post_telemetry(self, video_id: str, vvsa_rate: float, apv: float, viral_status: int) -> bool:
        with self.lock:
            updated = False
            for row in self.tables["media_pipeline.video_grades"]:
                if row.get("video_id") == video_id:
                    row["actual_vvsa_rate"] = vvsa_rate
                    row["actual_avg_percentage_viewed"] = apv
                    row["actual_viral_status"] = viral_status
                    updated = True
            return updated

    def execute_create_model(self, model_name: str, model_type: str, query_sql: str) -> Dict[str, Any]:
        with self.lock:
            # Filter training data based on status = 'GRADED' and APV IS NOT NULL
            graded_records = [
                r for r in self.tables["media_pipeline.video_grades"]
                if r.get("status") == "GRADED" and r.get("actual_avg_percentage_viewed") is not None
            ]
            self.models[model_name] = {
                "model_name": model_name,
                "model_type": model_type,
                "training_rows": len(graded_records),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            return self.models[model_name]

    def register_new_weights(self, weights: ModelParameterWeights) -> None:
        with self.lock:
            for r in self.tables["media_pipeline.model_parameter_weights"]:
                r["is_active"] = False
            self.tables["media_pipeline.model_parameter_weights"].append(weights.model_dump())

    def get_active_weights(self) -> ModelParameterWeights:
        with self.lock:
            active_rows = [r for r in self.tables["media_pipeline.model_parameter_weights"] if r.get("is_active")]
            if active_rows:
                return ModelParameterWeights(**active_rows[-1])
            return ModelParameterWeights(version_id="v_fallback_default")

    def rollback_to_version(self, target_version_id: str) -> bool:
        """Rolls back active status to a specified historical model weight version."""
        with self.lock:
            found = False
            for r in self.tables["media_pipeline.model_parameter_weights"]:
                if r.get("version_id") == target_version_id:
                    found = True
            if not found:
                return False

            for r in self.tables["media_pipeline.model_parameter_weights"]:
                if r.get("version_id") == target_version_id:
                    r["is_active"] = True
                else:
                    r["is_active"] = False
            return True


# ============================================================================
# 1. ADVERSARIAL SCHEMA & DDL VALIDATION TESTS
# ============================================================================

def test_adversarial_schema_sql_ddl_exact_signatures():
    """Validates full BigQuery DDL syntax, partition clauses, and data types in schema.sql."""
    schema_file = CURRENT_DIR / "schema.sql"
    assert schema_file.exists(), f"Missing schema.sql at {schema_file}"
    content = schema_file.read_text(encoding="utf-8")

    # Verify all 3 required tables exist
    tables = [
        "media_pipeline.video_grades",
        "media_pipeline.video_grading_records",
        "media_pipeline.post_performance_metrics",
        "media_pipeline.model_parameter_weights",
    ]
    for tbl in tables:
        assert tbl in content, f"DDL for table {tbl} missing in schema.sql"

    # Verify Partitioning on all tables
    partition_matches = re.findall(r"PARTITION BY\s+DATE\((\w+)\)", content, re.IGNORECASE)
    assert len(partition_matches) >= 3, f"Expected >=3 partitioned tables, found: {partition_matches}"

    # Verify Clustering on all tables
    cluster_matches = re.findall(r"CLUSTER BY\s+([^\;\n]+)", content, re.IGNORECASE)
    assert len(cluster_matches) >= 3, f"Expected >=3 clustered tables, found: {cluster_matches}"

    # Verify video_grades NOT NULL columns
    required_not_null = [
        "video_id", "gcs_uri", "duration_seconds", "aspect_ratio",
        "status", "hrv_score", "dpaw_score", "adr_sfd_score",
        "cke_mve_score", "ltss_score", "evpi_composite", "trending_verdict"
    ]
    for col in required_not_null:
        pattern = rf"{col}\s+[\w<>]+\s+NOT\s+NULL"
        assert re.search(pattern, content, re.IGNORECASE), f"Column {col} missing NOT NULL constraint"


def test_adversarial_models_sql_query_filters_and_syntax():
    """Validates BQML CREATE MODEL statements, hyperparameters, and WHERE clause guards."""
    models_file = CURRENT_DIR / "models.sql"
    assert models_file.exists(), f"Missing models.sql at {models_file}"
    content = models_file.read_text(encoding="utf-8")

    # 1. Linear Regression Model
    assert "viral_weight_regressor" in content
    assert "model_type='LINEAR_REG'" in content
    assert "input_label_cols=['actual_avg_percentage_viewed']" in content
    assert "l1_reg=" in content
    assert "l2_reg=" in content
    assert "standardize_features=TRUE" in content

    # 2. Boosted Tree Regressor
    assert "viral_retention_tree_regressor" in content
    assert "model_type='BOOSTED_TREE_REGRESSOR'" in content
    assert "learn_rate=" in content
    assert "subsample=" in content
    assert "tree_method='HIST'" in content

    # 3. K-Means
    assert "video_archetype_clusters" in content
    assert "model_type='KMEANS'" in content
    assert "num_clusters=4" in content

    # 4. Mandatory WHERE clause filters preventing unreleased/null training
    where_clauses = re.findall(r"WHERE\s+([^;]+)", content, re.IGNORECASE)
    assert len(where_clauses) >= 2, "Expected WHERE clauses in model training queries"
    for wc in where_clauses[:2]:
        assert "actual_avg_percentage_viewed IS NOT NULL" in wc, f"Missing IS NOT NULL filter in: {wc}"
        assert "status = 'GRADED'" in wc, f"Missing status = 'GRADED' filter in: {wc}"

    # 5. Dynamic Recalibration SQL CTE query
    assert "WITH raw_weights AS" in content
    assert "GREATEST(0.01, weight)" in content
    assert "SUM(safe_weight) OVER()" in content
    assert "ROUND(normalized_weight, 4)" in content


# ============================================================================
# 2. ADVERSARIAL SIMPLEX WEIGHT NORMALIZATION TESTS
# ============================================================================

def test_adversarial_normalization_all_negative_coefficients():
    """Tests normalization behavior when all model coefficients are negative."""
    raw_negative = {
        "hrv_score": -0.45,
        "dpaw_score": -0.80,
        "adr_sfd_score": -0.12,
        "cke_mve_score": -0.99,
        "ltss_score": -0.05,
    }
    # With min floor 0.01, all become 0.01 -> total 0.05 -> normalized to equal 0.20
    norm = extract_normalized_weights(raw_negative, min_weight_floor=0.01)
    assert abs(sum(norm.values()) - 1.0000) < 1e-4
    for k in CANONICAL_FEATURES:
        assert norm[k] >= 0.01
        assert abs(norm[k] - 0.20) <= 0.01


def test_adversarial_normalization_all_zero_coefficients():
    """Tests normalization behavior when all coefficients are exactly zero."""
    raw_zeros = {
        "hrv_score": 0.0,
        "dpaw_score": 0.0,
        "adr_sfd_score": 0.0,
        "cke_mve_score": 0.0,
        "ltss_score": 0.0,
    }
    norm = extract_normalized_weights(raw_zeros, min_weight_floor=0.05)
    assert abs(sum(norm.values()) - 1.0000) < 1e-4
    for k in CANONICAL_FEATURES:
        assert norm[k] == 0.20


def test_adversarial_normalization_extreme_single_feature_dominance():
    """Tests normalization when a single feature has massive dominance (1e8 vs 1e-5)."""
    raw_extreme = {
        "weight_hrv": 100_000_000.0,
        "weight_dpaw": 0.0001,
        "weight_adr_sfd": 0.0001,
        "weight_cke_mve": 0.0001,
        "weight_ltss": 0.0001,
    }
    norm = extract_normalized_weights(raw_extreme, min_weight_floor=0.0001)
    assert norm["weight_hrv"] > 0.999
    assert abs(sum(norm.values()) - 1.0000) < 1e-4


def test_adversarial_normalization_missing_keys_and_garbage_injection():
    """Tests resilience against missing canonical features and unexpected injected columns."""
    raw_corrupted = {
        "hrv_score": 0.50,
        "random_garbage_column": 999.9,
        "injected_sql_drop_table": "DROP TABLE video_grades",
        "another_unknown_key": 42.0,
        # dpaw, adr_sfd, cke_mve, ltss are missing!
    }
    norm = extract_normalized_weights(raw_corrupted)
    assert set(norm.keys()) == set(CANONICAL_FEATURES)
    assert abs(sum(norm.values()) - 1.0000) < 1e-4
    # Missing keys fall back to defaults
    assert norm["weight_dpaw"] > 0.0
    assert norm["weight_adr_sfd"] > 0.0


def test_adversarial_normalization_case_and_whitespace_insensitivity():
    """Tests that alias lookup is fully case and whitespace insensitive."""
    raw_messy = {
        "   HRV_SCORE  ": 35.0,
        "dPaW_ScOrE": 25.0,
        "\tAdR_sFd_ScOrE\n": 20.0,
        "  CROWD_MOTION  ": 10.0,
        "  LIGHTING_SYNC  ": 10.0,
    }
    norm = extract_normalized_weights(raw_messy)
    assert norm["weight_hrv"] == 0.35
    assert norm["weight_dpaw"] == 0.25
    assert norm["weight_adr_sfd"] == 0.20
    assert norm["weight_cke_mve"] == 0.10
    assert norm["weight_ltss"] == 0.10
    assert abs(sum(norm.values()) - 1.0000) < 1e-4


def test_adversarial_normalization_floating_point_residual_correction():
    """Tests that residual rounding guarantees exact 1.0000 sum across 1,000 random weights."""
    import random
    random.seed(42)
    for _ in range(1000):
        raw = {
            "hrv": random.uniform(-10.0, 100.0),
            "dpaw": random.uniform(-10.0, 100.0),
            "adr_sfd": random.uniform(-10.0, 100.0),
            "cke_mve": random.uniform(-10.0, 100.0),
            "ltss": random.uniform(-10.0, 100.0),
        }
        norm = extract_normalized_weights(raw)
        total = round(sum(norm.values()), 4)
        assert total == 1.0000, f"Sum failed for {raw}: {total}"


# ============================================================================
# 3. ADVERSARIAL MULTI-VERSION WEIGHT LIFECYCLE & ROLLBACK TESTS
# ============================================================================

def test_adversarial_multi_version_lifecycle_and_single_active_invariant():
    """Validates consecutive model training versions and enforces single-active-version invariant."""
    engine = AdversarialMockBigQueryEngine()

    # Initial state: exactly 1 active version (baseline)
    active_rows = [r for r in engine.tables["media_pipeline.model_parameter_weights"] if r["is_active"]]
    assert len(active_rows) == 1
    assert active_rows[0]["version_id"] == "v1.0.0_baseline"

    # Train 5 consecutive versions
    version_ids = []
    for i in range(1, 6):
        override = {
            "weight_hrv": 0.20 + (i * 0.02),
            "weight_dpaw": 0.25,
            "weight_adr_sfd": 0.20,
            "weight_cke_mve": 0.20 - (i * 0.01),
            "weight_ltss": 0.15 - (i * 0.01),
        }
        w = recalibrate_model_weights(raw_weights_override=override, r2_score_override=0.80 + (i * 0.02))
        w.version_id = f"v_prod_{i}.0.0"
        engine.register_new_weights(w)
        version_ids.append(w.version_id)

        # Invariant check: Exactly one active version
        active_list = [r for r in engine.tables["media_pipeline.model_parameter_weights"] if r["is_active"]]
        assert len(active_list) == 1, f"Invariant violated at step {i}: {len(active_list)} active versions"
        assert active_list[0]["version_id"] == f"v_prod_{i}.0.0"

    # Total versions in history = 1 (baseline) + 5 (trained) = 6
    assert len(engine.tables["media_pipeline.model_parameter_weights"]) == 6


def test_adversarial_historical_weight_rollback():
    """Validates rolling back from a degraded model version (v5) to a known stable version (v2)."""
    engine = AdversarialMockBigQueryEngine()

    # Create historical versions
    v1 = ModelParameterWeights(version_id="v1.0", weight_hrv=0.25, weight_dpaw=0.25, weight_adr_sfd=0.20, weight_cke_mve=0.15, weight_ltss=0.15)
    v2_stable = ModelParameterWeights(version_id="v2.0_stable", weight_hrv=0.35, weight_dpaw=0.25, weight_adr_sfd=0.20, weight_cke_mve=0.10, weight_ltss=0.10)
    v3_degraded = ModelParameterWeights(version_id="v3.0_degraded", weight_hrv=0.10, weight_dpaw=0.10, weight_adr_sfd=0.10, weight_cke_mve=0.35, weight_ltss=0.35)

    engine.register_new_weights(v1)
    engine.register_new_weights(v2_stable)
    engine.register_new_weights(v3_degraded)

    # Currently v3_degraded is active
    current_active = engine.get_active_weights()
    assert current_active.version_id == "v3.0_degraded"

    # Score a video using degraded weights
    scores = ViralParameterScores(hrv=95.0, dpaw=90.0, adr_sfd=85.0, cke_mve=40.0, ltss=40.0)
    evpi_degraded = calculate_evpi(scores, weights=current_active)

    # Execute Rollback to v2.0_stable
    success = engine.rollback_to_version("v2.0_stable")
    assert success is True

    # Verify active version is now v2.0_stable
    restored_active = engine.get_active_weights()
    assert restored_active.version_id == "v2.0_stable"
    assert restored_active.weight_hrv == 0.35

    # Invariant check: Exactly one active version
    active_list = [r for r in engine.tables["media_pipeline.model_parameter_weights"] if r["is_active"]]
    assert len(active_list) == 1
    assert active_list[0]["version_id"] == "v2.0_stable"

    # Re-score video using rolled back weights -> EVPI should be significantly higher due to high HRV weight
    evpi_restored = calculate_evpi(scores, weights=restored_active)
    assert evpi_restored > evpi_degraded, f"Restored EVPI ({evpi_restored}) should exceed degraded ({evpi_degraded})"


def test_adversarial_rollback_nonexistent_version():
    """Validates that attempting to roll back to a nonexistent version fails gracefully."""
    engine = AdversarialMockBigQueryEngine()
    success = engine.rollback_to_version("v999_does_not_exist")
    assert success is False
    # Baseline remains active
    assert engine.get_active_weights().version_id == "v1.0.0_baseline"


# ============================================================================
# 4. ADVERSARIAL SINK & TELEMETRY INGESTION EDGE CASES
# ============================================================================

def test_adversarial_sink_with_null_and_failed_dlq_records():
    """Validates that sink handles mixed status records (GRADED, FAILED_DLQ, PENDING)."""
    engine = AdversarialMockBigQueryEngine()

    raw_records = [
        {
            "video_id": "vid_success_1",
            "gcs_uri": "gs://vault/vid1.mp4",
            "duration_seconds": 24.5,
            "aspect_ratio": "9:16",
            "status": "GRADED",
            "hrv_score": 88.0,
            "dpaw_score": 82.0,
            "adr_sfd_score": 79.0,
            "cke_mve_score": 70.0,
            "ltss_score": 75.0,
            "evpi_composite": 80.2,
            "trending_verdict": "HIGH_POTENTIAL",
        },
        {
            "video_id": "vid_failed_dlq",
            "gcs_uri": "gs://vault/corrupted.mp4",
            "duration_seconds": 15.0,
            "aspect_ratio": "9:16",
            "status": "FAILED_DLQ",
            "error_message": "Audio stream unreadable",
            "hrv_score": 0.0,
            "dpaw_score": 0.0,
            "adr_sfd_score": 0.0,
            "cke_mve_score": 0.0,
            "ltss_score": 0.0,
            "evpi_composite": 0.0,
            "trending_verdict": "LOW_REACH",
        },
        {
            "video_id": "vid_pending",
            "gcs_uri": "gs://vault/pending.mp4",
            "duration_seconds": 30.0,
            "aspect_ratio": "9:16",
            "status": "PENDING",
            "hrv_score": 50.0,
            "dpaw_score": 50.0,
            "adr_sfd_score": 50.0,
            "cke_mve_score": 50.0,
            "ltss_score": 50.0,
            "evpi_composite": 50.0,
            "trending_verdict": "MODERATE",
        },
    ]

    inserted = sink_video_grades_to_bq(engine, "media_pipeline.video_grades", raw_records)
    assert inserted == 3
    assert len(engine.tables["media_pipeline.video_grades"]) == 3

    # Now simulate model training: only GRADED records with non-null APV should be trained
    # Attach telemetry to vid_success_1
    engine.update_post_telemetry("vid_success_1", vvsa_rate=0.85, apv=1.20, viral_status=1)

    model_res = engine.execute_create_model("test_filter_model", "LINEAR_REG", "SELECT *")
    assert model_res["training_rows"] == 1  # Only vid_success_1 qualified


def test_adversarial_telemetry_update_concurrency_stress():
    """Validates thread-safe concurrent telemetry updates across 50 simultaneous threads."""
    engine = AdversarialMockBigQueryEngine()

    # Pre-populate 50 video records
    for i in range(50):
        engine.tables["media_pipeline.video_grades"].append({
            "video_id": f"threaded_vid_{i}",
            "status": "GRADED",
            "hrv_score": 75.0,
            "actual_vvsa_rate": None,
            "actual_avg_percentage_viewed": None,
            "actual_viral_status": 0,
        })

    def worker_update(idx: int):
        engine.update_post_telemetry(
            f"threaded_vid_{idx}",
            vvsa_rate=0.70 + (idx * 0.005),
            apv=1.00 + (idx * 0.01),
            viral_status=1 if idx % 2 == 0 else 0,
        )

    threads = [threading.Thread(target=worker_update, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify all 50 records were correctly updated without corruption or race condition
    for i in range(50):
        row = next(r for r in engine.tables["media_pipeline.video_grades"] if r["video_id"] == f"threaded_vid_{i}")
        assert row["actual_vvsa_rate"] is not None
        assert row["actual_avg_percentage_viewed"] is not None
        assert row["actual_viral_status"] == (1 if i % 2 == 0 else 0)


def test_adversarial_high_volume_batch_sink():
    """Validates memory and execution stability when sinking 5,000 video records."""
    engine = AdversarialMockBigQueryEngine()
    batch = []
    for i in range(5000):
        batch.append({
            "video_id": f"batch_vid_{i}",
            "gcs_uri": f"gs://edm-vault/batch_{i}.mp4",
            "duration_seconds": 25.0,
            "aspect_ratio": "9:16",
            "status": "GRADED",
            "hrv_score": 80.0,
            "dpaw_score": 80.0,
            "adr_sfd_score": 80.0,
            "cke_mve_score": 80.0,
            "ltss_score": 80.0,
            "evpi_composite": 80.0,
            "trending_verdict": "HIGH_POTENTIAL",
        })

    t0 = time.perf_counter()
    inserted = sink_video_grades_to_bq(engine, "media_pipeline.video_grades", batch)
    t1 = time.perf_counter()

    assert inserted == 5000
    assert len(engine.tables["media_pipeline.video_grades"]) == 5000
    assert (t1 - t0) < 2.0, f"Batch sink took too long: {t1 - t0:.2f}s"


# ============================================================================
# 5. ADVERSARIAL CLOSED-LOOP ML FEEDBACK SIMULATION
# ============================================================================

def test_adversarial_closed_loop_feedback_recalibration():
    """
    Simulates complete closed-loop ML optimization:
    1. 10 videos graded with baseline weights.
    2. Telemetry shows strong correlation between HRV/DPAW and actual virality.
    3. Recalibration extracts learned weights, boosting HRV & DPAW.
    4. Re-scoring a high-hook video yields higher EVPI and upgraded verdict.
    """
    engine = AdversarialMockBigQueryEngine()
    feedback = BigQueryMLFeedbackEngine(client=engine, dataset="media_pipeline")

    # 1. Ingest videos
    records = []
    for i in range(10):
        scores = ViralParameterScores(
            hrv=50.0 + (i * 5),
            dpaw=50.0 + (i * 5),
            adr_sfd=60.0,
            cke_mve=60.0,
            ltss=60.0,
        )
        evpi = calculate_evpi(scores)
        verdict = get_verdict_from_evpi(evpi)
        records.append({
            "video_id": f"loop_v_{i}",
            "gcs_uri": f"gs://vault/v_{i}.mp4",
            "duration_seconds": 20.0,
            "aspect_ratio": "9:16",
            "status": "GRADED",
            "hrv_score": scores.hrv,
            "dpaw_score": scores.dpaw,
            "adr_sfd_score": scores.adr_sfd,
            "cke_mve_score": scores.cke_mve,
            "ltss_score": scores.ltss,
            "evpi_composite": evpi,
            "trending_verdict": verdict.value,
        })
    feedback.sink_grades(records)

    # 2. Attach telemetry: High HRV/DPAW strongly correlates with high APV
    for i in range(10):
        apv_val = 0.60 + (i * 0.10)  # 0.60 to 1.50
        viral_flag = 1 if apv_val >= 1.10 else 0
        feedback.record_telemetry(f"loop_v_{i}", vvsa_rate=0.70 + (i * 0.02), apv=apv_val, viral_status=viral_flag)

    # 3. Train Model & Recalibrate with raw weights showing high HRV & DPAW coefficients
    raw_coefficients = {
        "hrv_score": 0.45,
        "dpaw_score": 0.35,
        "adr_sfd_score": 0.10,
        "cke_mve_score": 0.05,
        "ltss_score": 0.05,
    }
    new_weights = feedback.recalibrate_weights(raw_weights_override=raw_coefficients)

    assert new_weights.is_active is True
    assert new_weights.weight_hrv >= 0.40
    assert new_weights.weight_dpaw >= 0.30
    assert abs(new_weights.weight_hrv + new_weights.weight_dpaw + new_weights.weight_adr_sfd + new_weights.weight_cke_mve + new_weights.weight_ltss - 1.0) < 1e-4

    # 4. Score a candidate with high hook (HRV=95, DPAW=90, rest=60)
    candidate_scores = ViralParameterScores(hrv=95.0, dpaw=90.0, adr_sfd=60.0, cke_mve=60.0, ltss=60.0)
    baseline_evpi = calculate_evpi(candidate_scores, weights=ModelParameterWeights(version_id="baseline"))
    recalibrated_evpi = calculate_evpi(candidate_scores, weights=new_weights)

    # Recalibrated EVPI must be strictly greater than baseline EVPI
    assert recalibrated_evpi > baseline_evpi, (
        f"Recalibrated EVPI ({recalibrated_evpi}) did not exceed baseline ({baseline_evpi})"
    )


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_adversarial_test_suite() -> int:
    """Executes all adversarial tests and prints structured results."""
    test_cases = [
        ("ADV-1: Schema SQL DDL Exact Signatures & Constraints", test_adversarial_schema_sql_ddl_exact_signatures),
        ("ADV-2: Models SQL Query Filters, Options & CTE Syntax", test_adversarial_models_sql_query_filters_and_syntax),
        ("ADV-3: Simplex Normalization - All Negative Weights", test_adversarial_normalization_all_negative_coefficients),
        ("ADV-4: Simplex Normalization - All Zero Weights", test_adversarial_normalization_all_zero_coefficients),
        ("ADV-5: Simplex Normalization - Extreme Disparities (1e8 vs 1e-5)", test_adversarial_normalization_extreme_single_feature_dominance),
        ("ADV-6: Simplex Normalization - Missing Keys & Injected Garbage", test_adversarial_normalization_missing_keys_and_garbage_injection),
        ("ADV-7: Simplex Normalization - Case & Whitespace Insensitivity", test_adversarial_normalization_case_and_whitespace_insensitivity),
        ("ADV-8: Simplex Normalization - 1,000 Monte Carlo Precision Sweeps", test_adversarial_normalization_floating_point_residual_correction),
        ("ADV-9: Multi-Version Lifecycle & Single-Active-Version Invariant", test_adversarial_multi_version_lifecycle_and_single_active_invariant),
        ("ADV-10: Historical Model Weight Rollback Verification", test_adversarial_historical_weight_rollback),
        ("ADV-11: Rollback Graceful Failure on Nonexistent Version", test_adversarial_rollback_nonexistent_version),
        ("ADV-12: Sink with NULL and FAILED_DLQ Records & Model Filter Guards", test_adversarial_sink_with_null_and_failed_dlq_records),
        ("ADV-13: Concurrent Telemetry Updates (50 Threads Stress)", test_adversarial_telemetry_update_concurrency_stress),
        ("ADV-14: High Volume Batch Sink (5,000 Records Benchmark)", test_adversarial_high_volume_batch_sink),
        ("ADV-15: Closed-Loop Telemetry Recalibration & Re-Scoring Simulation", test_adversarial_closed_loop_feedback_recalibration),
    ]

    print("\n" + "=" * 80)
    print("   ADVERSARIAL STRESS & INTEGRITY SUITE: MILESTONE 4 (BIGQUERY ML LOOP)")
    print("=" * 80 + "\n")

    passed = 0
    failed = 0

    for name, test_fn in test_cases:
        try:
            test_fn()
            print(f"  [+] PASSED: {name}")
            passed += 1
        except Exception as e:
            print(f"  [-] FAILED: {name} -> {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "-" * 80)
    print(f"Total Adversarial Tests: {passed + failed} | Passed: {passed} | Failed: {failed}")
    print("-" * 80)

    if failed == 0:
        print("\n[SUCCESS] ALL 15 ADVERSARIAL STRESS TESTS PASSED EMPIRICALLY (Exit code 0)\n")
        return 0
    else:
        print(f"\n[FAILURE] {failed} ADVERSARIAL TESTS FAILED (Exit code 1)\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_adversarial_test_suite())
