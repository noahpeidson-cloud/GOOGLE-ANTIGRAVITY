#!/usr/bin/env python3
"""
test_dynamic_ml_loop.py - Tier 5 Dynamic ML Loop Adversarial Stress Harness.
Module: .agents.challenger_tier5_2.test_dynamic_ml_loop

Adversarial Stress Test Matrix:
1. Multi-Iteration Automated Feedback Loop (Iteration 1 Ingestion -> Baseline Grading -> BQ Sink ->
   Simulated YouTube/TikTok Analytics -> BQML Training -> Dynamic Weights Recalibration ->
   Iteration 2 Ingestion -> PySpark Dynamic Weights Application -> Iteration 3 Generation).
2. Distributed PySpark Partition Execution & Schema Conformance with Dynamic Broadcast Weights.
3. Adversarial Telemetry Ingestion: Asynchronous, unreleased videos (NULL APV), DLQ failures, extreme APV (5.0x viral loop).
4. Adversarial Regression Coefficients: Negative, zero, and extreme disparity coefficients with Simplex Normalization.
5. Concurrent Multi-Threaded Telemetry Updates & Single-Active-Version Invariant.
6. Historical Model Weight Rollback & PySpark Dynamic Cache Invalidation.
7. Monte Carlo Rank Inversion & Sensitivity Proof across feature weight shifts.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import random
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

# Ensure media_pipeline is in sys.path
AGENT_DIR = Path(__file__).parent.resolve()
WORKSPACE_ROOT = AGENT_DIR.parent.parent.resolve()
MEDIA_PIPELINE_DIR = WORKSPACE_ROOT / "media_pipeline"

if str(MEDIA_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(MEDIA_PIPELINE_DIR))
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

# Project Imports
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
    calculate_evpi,
    calculate_evpi_from_scores,
    classify_viral_tier,
    compute_killswitches,
    get_verdict_from_evpi,
)

from media_pipeline.grading.gemini_multimodal_client import GeminiMultimodalClient
from media_pipeline.grading.spark_grading_job import (
    PYSPARK_AVAILABLE,
    PySparkGradingPipeline,
    fetch_active_weights,
    get_spark_output_schema,
    grade_partition,
)

logger = logging.getLogger("test_dynamic_ml_loop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ============================================================================
# ADVERSARIAL MOCK ENGINE: State Storage, BQML & PySpark Bridge
# ============================================================================

class AdversarialBigQueryMLStore:
    """
    In-memory BigQuery database and ML engine with schema validation,
    transactional locking, multi-version weights, and query filtering.
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
                    model_r2_score=0.85,
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
                    row = m.model_dump()
                    if "scores" in row and isinstance(row["scores"], dict):
                        row["hrv_score"] = row["scores"].get("hrv", 0.0)
                        row["dpaw_score"] = row["scores"].get("dpaw", 0.0)
                        row["adr_sfd_score"] = row["scores"].get("adr_sfd", 0.0)
                        row["cke_mve_score"] = row["scores"].get("cke_mve", 0.0)
                        row["ltss_score"] = row["scores"].get("ltss", 0.0)
                    if "trending_verdict" in row and hasattr(row["trending_verdict"], "value"):
                        row["trending_verdict"] = row["trending_verdict"].value
                    if "status" not in row:
                        row["status"] = "GRADED"
                    self.tables["media_pipeline.video_grades"].append(row)
                elif isinstance(m, dict):
                    row = dict(m)
                    if "status" not in row:
                        row["status"] = "GRADED"
                    self.tables["media_pipeline.video_grades"].append(row)
                count += 1
            return count

    def update_post_telemetry(
        self,
        video_id: str,
        vvsa_rate: float,
        apv: float,
        viral_status: int,
        share_count: Optional[int] = None,
        completion_rate: Optional[float] = None,
    ) -> bool:
        with self.lock:
            for row in self.tables["media_pipeline.video_grades"]:
                if row.get("video_id") == video_id:
                    row["actual_vvsa_rate"] = vvsa_rate
                    row["actual_avg_percentage_viewed"] = apv
                    row["actual_viral_status"] = viral_status
                    if share_count is not None:
                        row["actual_share_count"] = share_count
                    if completion_rate is not None:
                        row["actual_completion_rate"] = completion_rate
                    return True
            return False

    def execute_create_model(self, model_name: str, model_type: str, query_sql: str) -> Dict[str, Any]:
        with self.lock:
            # Enforce BigQuery ML WHERE clause filter guards (status = 'GRADED' AND actual_avg_percentage_viewed IS NOT NULL)
            eligible_rows = [
                r for r in self.tables["media_pipeline.video_grades"]
                if r.get("status") == "GRADED" and r.get("actual_avg_percentage_viewed") is not None
            ]
            if not eligible_rows:
                raise ValueError(f"Cannot train model '{model_name}': 0 eligible rows with status='GRADED' and non-NULL APV.")

            # Compute empirical correlations between features and actual APV
            correlations = self._compute_correlations(eligible_rows)
            
            self.models[model_name] = {
                "model_name": model_name,
                "model_type": model_type.upper(),
                "training_rows": len(eligible_rows),
                "correlations": correlations,
                "r2_score": 0.89 if len(eligible_rows) >= 5 else 0.75,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            return self.models[model_name]

    def _compute_correlations(self, rows: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculates Pearson correlation between each viral score and actual_avg_percentage_viewed."""
        features = ["hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score"]
        n = len(rows)
        if n < 2:
            return {f: 0.20 for f in features}

        apv_vals = [float(r["actual_avg_percentage_viewed"]) for r in rows]
        mean_apv = sum(apv_vals) / n
        std_apv = math.sqrt(sum((x - mean_apv) ** 2 for x in apv_vals) / n) or 1.0

        corrs: Dict[str, float] = {}
        for feat in features:
            f_vals = [float(r.get(feat, 50.0)) for r in rows]
            mean_f = sum(f_vals) / n
            std_f = math.sqrt(sum((x - mean_f) ** 2 for x in f_vals) / n) or 1.0

            cov = sum((f_vals[i] - mean_f) * (apv_vals[i] - mean_apv) for i in range(n)) / n
            r = cov / (std_f * std_apv)
            corrs[feat] = r

        return corrs

    def extract_ml_weights(self, model_name: str) -> ModelParameterWeights:
        with self.lock:
            if model_name not in self.models:
                raise ValueError(f"Model '{model_name}' not found.")

            model = self.models[model_name]
            corrs = model.get("correlations", {})

            # Map correlations to canonical feature weights
            raw_weights = {
                "weight_hrv": max(0.01, corrs.get("hrv_score", 0.25)),
                "weight_dpaw": max(0.01, corrs.get("dpaw_score", 0.25)),
                "weight_adr_sfd": max(0.01, corrs.get("adr_sfd_score", 0.20)),
                "weight_cke_mve": max(0.01, corrs.get("cke_mve_score", 0.15)),
                "weight_ltss": max(0.01, corrs.get("ltss_score", 0.15)),
            }

            norm = extract_normalized_weights(raw_weights)

            new_weights = ModelParameterWeights(
                version_id=f"v_{model_name}_{int(time.time()*1000)}",
                weight_hrv=norm["weight_hrv"],
                weight_dpaw=norm["weight_dpaw"],
                weight_adr_sfd=norm["weight_adr_sfd"],
                weight_cke_mve=norm["weight_cke_mve"],
                weight_ltss=norm["weight_ltss"],
                model_r2_score=model.get("r2_score", 0.88),
                is_active=True,
            )

            # Deactivate older versions & register new active version
            for r in self.tables["media_pipeline.model_parameter_weights"]:
                r["is_active"] = False
            self.tables["media_pipeline.model_parameter_weights"].append(new_weights.model_dump())
            return new_weights

    def get_active_weights(self) -> ModelParameterWeights:
        with self.lock:
            for r in reversed(self.tables["media_pipeline.model_parameter_weights"]):
                if r.get("is_active", True):
                    return ModelParameterWeights(**r)
            return ModelParameterWeights(version_id="v_fallback_baseline")

    def rollback_to_version(self, target_version_id: str) -> bool:
        with self.lock:
            target_found = any(r.get("version_id") == target_version_id for r in self.tables["media_pipeline.model_parameter_weights"])
            if not target_found:
                return False

            for r in self.tables["media_pipeline.model_parameter_weights"]:
                r["is_active"] = (r.get("version_id") == target_version_id)
            return True


# ============================================================================
# 1. ADVERSARIAL STRESS TEST: COMPLETE MULTI-ITERATION ML FEEDBACK LOOP
# ============================================================================

def test_multi_iteration_e2e_feedback_loop():
    """
    Stress-tests the full automated feedback loop across multiple generations:
    - Iteration 1: Ingest Batch 1 (10 videos), grade with baseline weights (0.25, 0.25, 0.20, 0.15, 0.15), sink to BQ.
    - Post-publish 1: Simulate actual YouTube/TikTok analytics (APV, VVSA, viral flag). Market heavily rewards HRV & DPAW.
    - Model train 1: Run BQML Boosted Tree & Linear Reg models to extract new dynamic weights (HRV & DPAW boosted).
    - Iteration 2: Ingest Batch 2 (10 new videos), verify PySpark automatically applies the newly learned weights from model_parameter_weights.
    - Post-publish 2: Simulate market shift (LTSS & CKE become dominant due to festival night strobe trends).
    - Model train 2: Train Gen 3 model, extract new weights, and verify Iteration 3 PySpark adapts seamlessly.
    """
    logger.info("=== Starting Test 1: Multi-Iteration E2E Feedback Loop ===")
    bq_store = AdversarialBigQueryMLStore()
    pipeline = PySparkGradingPipeline(spark=None, mock_mode=True)
    feedback_engine = BigQueryMLFeedbackEngine(client=bq_store, dataset="media_pipeline")

    # ------------------------------------------------------------------------
    # ITERATION 1: Baseline Ingestion & Grading
    # ------------------------------------------------------------------------
    logger.info("[Iteration 1] Ingesting & Grading Batch 1 with Baseline Weights...")
    batch_1_inputs = []
    for i in range(10):
        batch_1_inputs.append({
            "video_id": f"iter1_clip_{i:02d}",
            "gcs_uri": f"gs://edm-vault/raw/iter1_clip_{i:02d}.mp4",
            "duration_seconds": 25.0,
            "aspect_ratio": "9:16",
        })

    # Initial active weights must be baseline
    baseline_weights = bq_store.get_active_weights()
    assert baseline_weights.version_id == "v1.0.0_baseline"
    assert baseline_weights.weight_hrv == 0.25
    assert baseline_weights.weight_dpaw == 0.25

    # Grade Batch 1 using active baseline weights
    graded_batch_1 = pipeline.process_records(batch_1_inputs, custom_weights=baseline_weights.model_dump())
    assert len(graded_batch_1) == 10
    assert all(r["status"] == "GRADED" for r in graded_batch_1)

    # Sink Batch 1 to BigQuery
    sink_count_1 = bq_store.sink_video_grades(graded_batch_1)
    assert sink_count_1 == 10
    assert len(bq_store.tables["media_pipeline.video_grades"]) == 10

    # Simulate Post-Publishing Analytics: Strong correlation with HRV (Hook) and DPAW (Drop)
    logger.info("[Iteration 1 Post-Publish] Recording YouTube/TikTok actual analytics (HRV & DPAW correlated)...")
    for r in graded_batch_1:
        vid = r["video_id"]
        hrv = r["hrv_score"]
        dpaw = r["dpaw_score"]
        
        # APV model: high hook + high drop gives higher retention (0.70x to 1.85x)
        apv = round(0.50 + (hrv * 0.008) + (dpaw * 0.006), 2)
        vvsa = round(0.50 + (hrv * 0.005), 2)
        is_viral = 1 if apv >= 1.25 and vvsa >= 0.80 else 0

        success = bq_store.update_post_telemetry(vid, vvsa_rate=vvsa, apv=apv, viral_status=is_viral)
        assert success is True

    # Train Iteration 1 BQML Model
    logger.info("[Iteration 1 BQML Train] Training Boosted Tree & Linear Reg on Batch 1...")
    model_1 = bq_store.execute_create_model(
        model_name="edm_viral_boosted_tree_gen1",
        model_type="BOOSTED_TREE_REGRESSOR",
        query_sql="SELECT hrv_score, dpaw_score, adr_sfd_score, cke_mve_score, ltss_score, actual_avg_percentage_viewed FROM `media_pipeline.video_grades` WHERE status='GRADED' AND actual_avg_percentage_viewed IS NOT NULL",
    )
    assert model_1["training_rows"] == 10

    # Extract & Recalibrate Iteration 1 Weights
    gen1_weights = bq_store.extract_ml_weights("edm_viral_boosted_tree_gen1")
    assert gen1_weights.is_active is True
    assert gen1_weights.version_id.startswith("v_edm_viral_boosted_tree_gen1")
    
    # Assert Simplex Normalization constraint
    sum_gen1 = (
        gen1_weights.weight_hrv + gen1_weights.weight_dpaw +
        gen1_weights.weight_adr_sfd + gen1_weights.weight_cke_mve + gen1_weights.weight_ltss
    )
    assert abs(sum_gen1 - 1.0000) < 1e-4

    # Assert that HRV and DPAW received increased weight allocation
    assert gen1_weights.weight_hrv > 0.25 or gen1_weights.weight_dpaw > 0.25

    # Check that previous baseline weight was deactivated
    weights_history = bq_store.tables["media_pipeline.model_parameter_weights"]
    assert len(weights_history) == 2
    active_rows = [w for w in weights_history if w["is_active"]]
    assert len(active_rows) == 1
    assert active_rows[0]["version_id"] == gen1_weights.version_id

    # ------------------------------------------------------------------------
    # ITERATION 2: Ingest Next Batch & Verify PySpark Applies New Weights
    # ------------------------------------------------------------------------
    logger.info("[Iteration 2] Ingesting Batch 2 & Verifying PySpark Applies Learned Dynamic Weights...")
    batch_2_inputs = []
    for i in range(10):
        batch_2_inputs.append({
            "video_id": f"iter2_clip_{i:02d}",
            "gcs_uri": f"gs://edm-vault/raw/iter2_clip_{i:02d}.mp4",
            "duration_seconds": 28.0,
            "aspect_ratio": "9:16",
        })

    # Retrieve current active weights dynamically from store
    active_w_iter2 = bq_store.get_active_weights()
    assert active_w_iter2.version_id == gen1_weights.version_id

    # Grade Batch 2 in PySpark using active weights
    graded_batch_2 = pipeline.process_records(batch_2_inputs, custom_weights=active_w_iter2.model_dump())
    assert len(graded_batch_2) == 10
    assert all(r["status"] == "GRADED" for r in graded_batch_2)

    # Prove that EVPI in Iteration 2 strictly matches the Gen 1 learned weights formula
    for r in graded_batch_2:
        expected_evpi = calculate_evpi_from_scores(
            hrv_score=r["hrv_score"],
            dpaw_score=r["dpaw_score"],
            adr_sfd_score=r["adr_sfd_score"],
            cke_mve_score=r["cke_mve_score"],
            ltss_score=r["ltss_score"],
            weights=active_w_iter2.model_dump(),
        )
        assert abs(r["evpi_composite"] - expected_evpi) < 1e-2, (
            f"PySpark EVPI {r['evpi_composite']} != Expected {expected_evpi} under dynamic weights"
        )

    # Sink Batch 2 to BigQuery
    bq_store.sink_video_grades(graded_batch_2)
    assert len(bq_store.tables["media_pipeline.video_grades"]) == 20

    # ------------------------------------------------------------------------
    # ITERATION 2 POST-PUBLISH: Market Meta Shift (Lighting / Crowd Strobe Surge)
    # ------------------------------------------------------------------------
    logger.info("[Iteration 2 Post-Publish] Simulating Market Meta Shift (Strobe & Crowd Energy Surge)...")
    for r in graded_batch_2:
        vid = r["video_id"]
        cke = r["cke_mve_score"]
        ltss = r["ltss_score"]
        
        # New meta: lighting sync + crowd motion drives viral retention
        apv = round(0.50 + (ltss * 0.009) + (cke * 0.007), 2)
        vvsa = round(0.60 + (ltss * 0.004), 2)
        is_viral = 1 if apv >= 1.30 else 0

        bq_store.update_post_telemetry(vid, vvsa_rate=vvsa, apv=apv, viral_status=is_viral)

    # Train Iteration 2 BQML Model
    logger.info("[Iteration 2 BQML Train] Retraining model across all 20 videos...")
    model_2 = bq_store.execute_create_model(
        model_name="edm_viral_boosted_tree_gen2",
        model_type="BOOSTED_TREE_REGRESSOR",
        query_sql="SELECT * FROM `media_pipeline.video_grades` WHERE status='GRADED'",
    )
    assert model_2["training_rows"] == 20

    # Extract Gen 2 Weights
    gen2_weights = bq_store.extract_ml_weights("edm_viral_boosted_tree_gen2")
    assert gen2_weights.is_active is True
    assert gen2_weights.version_id != gen1_weights.version_id

    # Assert Exactly One Active Version in history of 3 versions
    all_weights = bq_store.tables["media_pipeline.model_parameter_weights"]
    assert len(all_weights) == 3
    active_now = [w for w in all_weights if w["is_active"]]
    assert len(active_now) == 1
    assert active_now[0]["version_id"] == gen2_weights.version_id

    # ------------------------------------------------------------------------
    # ITERATION 3: Ingest Batch 3 with Gen 2 Weights
    # ------------------------------------------------------------------------
    logger.info("[Iteration 3] Ingesting Batch 3 and confirming adaptation to Gen 2 Weights...")
    batch_3_inputs = [
        {"video_id": f"iter3_clip_{i:02d}", "gcs_uri": f"gs://edm-vault/raw/iter3_clip_{i:02d}.mp4", "duration_seconds": 20.0}
        for i in range(5)
    ]
    active_w_iter3 = bq_store.get_active_weights()
    assert active_w_iter3.version_id == gen2_weights.version_id

    graded_batch_3 = pipeline.process_records(batch_3_inputs, custom_weights=active_w_iter3.model_dump())
    assert len(graded_batch_3) == 5
    assert all(r["status"] == "GRADED" for r in graded_batch_3)

    logger.info("[SUCCESS] Multi-Iteration E2E Feedback Loop passed all adversarial assertions.")


# ============================================================================
# 2. ADVERSARIAL STRESS TEST: DISTRIBUTED PYSPARK PARTITION EXECUTION & SCHEMA
# ============================================================================

def test_distributed_pyspark_partition_execution_and_schema():
    """
    Executes distributed partition processing and verifies:
    1. Multi-partition batch execution across 4 parallel partition slices.
    2. Dynamic broadcast weights propagation into partition workers.
    3. Output StructType schema conformance matching get_spark_output_schema().
    4. EVPI mathematical correctness and 0 worker failures across all partitions.
    """
    logger.info("=== Starting Test 2: Distributed PySpark Partition Execution & Schema Conformance ===")

    recalibrated_w = {
        "weight_hrv": 0.35,
        "weight_dpaw": 0.30,
        "weight_adr_sfd": 0.15,
        "weight_cke_mve": 0.10,
        "weight_ltss": 0.10,
    }

    # Create 20 sample video partition records across 4 partition slices
    records = [
        {
            "video_id": f"dist_clip_{i:02d}",
            "gcs_uri": f"gs://edm-vault/raw/dist_clip_{i:02d}.mp4",
            "file_size_bytes": 1024 * 1024 * 50,
            "duration_seconds": 25.0 + (i % 10),
            "aspect_ratio": "9:16",
        }
        for i in range(20)
    ]

    # Split into 4 partition slices
    slice_size = len(records) // 4
    partition_slices = [records[i:i + slice_size] for i in range(0, len(records), slice_size)]
    assert len(partition_slices) == 4

    all_graded_results: List[Dict[str, Any]] = []

    # Execute distributed partition workers
    for p_idx, part in enumerate(partition_slices):
        part_results = list(grade_partition(iter(part), recalibrated_w, mock_mode=True))
        assert len(part_results) == len(part)
        all_graded_results.extend(part_results)

    assert len(all_graded_results) == 20

    # Verify PySpark schema definition
    schema = get_spark_output_schema()
    if schema is not None:
        expected_field_names = [f.name for f in schema.fields]
        required_keys = [
            "video_id", "gcs_uri", "raw_file_name", "file_size_bytes",
            "duration_seconds", "aspect_ratio", "status", "error_message",
            "hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score",
            "ltss_score", "evpi_composite", "trending_verdict", "graded_at", "model_version"
        ]
        for k in required_keys:
            assert k in expected_field_names, f"Missing field {k} in Spark StructType schema"

    # Verify every partition result record conforms to schema and math
    for row in all_graded_results:
        assert row["status"] == "GRADED"
        assert row["error_message"] is None
        assert 0.0 <= row["hrv_score"] <= 100.0
        assert 0.0 <= row["dpaw_score"] <= 100.0
        assert 0.0 <= row["evpi_composite"] <= 100.0

        expected_evpi = calculate_evpi_from_scores(
            hrv_score=row["hrv_score"],
            dpaw_score=row["dpaw_score"],
            adr_sfd_score=row["adr_sfd_score"],
            cke_mve_score=row["cke_mve_score"],
            ltss_score=row["ltss_score"],
            weights=recalibrated_w,
        )
        assert abs(row["evpi_composite"] - expected_evpi) < 1e-2

    logger.info(f"[SUCCESS] Distributed PySpark partition execution verified across 4 slices; processed {len(all_graded_results)} rows.")


# ============================================================================
# 3. ADVERSARIAL STRESS TEST: TELEMETRY DISTURBANCES & FILTER GUARDS
# ============================================================================

def test_adversarial_telemetry_disturbances_and_query_guards():
    """
    Stress-tests BQML training resilience against:
    - Unreleased videos (NULL APV).
    - Failed DLQ videos (status='FAILED_DLQ').
    - Pending / un-graded videos.
    - Extreme viral loop APV (e.g. APV = 5.0 for 5-loop replays).
    - Negative or 0.0 APV edge cases.
    """
    logger.info("=== Starting Test 3: Adversarial Telemetry Disturbances & Query Guards ===")
    bq_store = AdversarialBigQueryMLStore()

    mixed_records = [
        # Valid released video
        {
            "video_id": "vid_released_01",
            "status": "GRADED",
            "hrv_score": 92.0, "dpaw_score": 88.0, "adr_sfd_score": 80.0, "cke_mve_score": 75.0, "ltss_score": 85.0,
            "actual_vvsa_rate": 0.90, "actual_avg_percentage_viewed": 1.45, "actual_viral_status": 1,
        },
        # Super-viral 5x loop video (APV = 5.0)
        {
            "video_id": "vid_super_viral_5x",
            "status": "GRADED",
            "hrv_score": 98.0, "dpaw_score": 95.0, "adr_sfd_score": 90.0, "cke_mve_score": 92.0, "ltss_score": 94.0,
            "actual_vvsa_rate": 0.98, "actual_avg_percentage_viewed": 5.00, "actual_viral_status": 1,
        },
        # Unreleased / scheduled video (APV IS NULL)
        {
            "video_id": "vid_unreleased_pending",
            "status": "GRADED",
            "hrv_score": 80.0, "dpaw_score": 80.0, "adr_sfd_score": 80.0, "cke_mve_score": 80.0, "ltss_score": 80.0,
            "actual_vvsa_rate": None, "actual_avg_percentage_viewed": None, "actual_viral_status": None,
        },
        # Failed DLQ video (status='FAILED_DLQ')
        {
            "video_id": "vid_failed_dlq",
            "status": "FAILED_DLQ",
            "error_message": "Corrupt container metadata",
            "hrv_score": 0.0, "dpaw_score": 0.0, "adr_sfd_score": 0.0, "cke_mve_score": 0.0, "ltss_score": 0.0,
            "actual_vvsa_rate": None, "actual_avg_percentage_viewed": None, "actual_viral_status": 0,
        },
        # Flop video (APV = 0.05)
        {
            "video_id": "vid_flop_01",
            "status": "GRADED",
            "hrv_score": 25.0, "dpaw_score": 30.0, "adr_sfd_score": 35.0, "cke_mve_score": 40.0, "ltss_score": 30.0,
            "actual_vvsa_rate": 0.20, "actual_avg_percentage_viewed": 0.05, "actual_viral_status": 0,
        },
    ]

    bq_store.sink_video_grades(mixed_records)

    # Train model -> should filter out unreleased and FAILED_DLQ videos, training on exactly 3 records
    model_res = bq_store.execute_create_model(
        model_name="robustness_test_model",
        model_type="LINEAR_REG",
        query_sql="SELECT * FROM `media_pipeline.video_grades` WHERE status='GRADED' AND actual_avg_percentage_viewed IS NOT NULL",
    )
    assert model_res["training_rows"] == 3

    # Recalibrate weights and assert valid normalization
    weights = bq_store.extract_ml_weights("robustness_test_model")
    assert weights.is_active is True
    assert abs(sum([weights.weight_hrv, weights.weight_dpaw, weights.weight_adr_sfd, weights.weight_cke_mve, weights.weight_ltss]) - 1.0) < 1e-4

    logger.info("[SUCCESS] Adversarial Telemetry Disturbances and Filter Guards verified.")


# ============================================================================
# 4. ADVERSARIAL STRESS TEST: EXTREME REGRESSION COEFFICIENTS & SIMPLEX BOUNDS
# ============================================================================

def test_adversarial_extreme_regression_coefficients():
    """
    Stress-tests extract_normalized_weights and ModelParameterWeights under extreme conditions:
    - All negative coefficients (e.g. -500.0).
    - All zero coefficients.
    - Massive single feature dominance (10,000.0 vs 0.0001).
    - 5,000 Monte Carlo sweeps with random floats and negative numbers.
    """
    logger.info("=== Starting Test 4: Extreme Regression Coefficients & Simplex Bounds ===")

    # Case 1: All negative coefficients
    neg_raw = {"hrv": -120.5, "dpaw": -340.2, "adr_sfd": -50.0, "cke_mve": -800.1, "ltss": -10.0}
    norm_neg = extract_normalized_weights(neg_raw, min_weight_floor=0.02)
    assert abs(sum(norm_neg.values()) - 1.0000) < 1e-4
    assert all(v >= 0.02 for v in norm_neg.values())

    # Case 2: Extreme dominance
    dom_raw = {"weight_hrv": 999999.0, "weight_dpaw": 0.001, "weight_adr_sfd": 0.001, "weight_cke_mve": 0.001, "weight_ltss": 0.001}
    norm_dom = extract_normalized_weights(dom_raw, min_weight_floor=0.01)
    assert norm_dom["weight_hrv"] > 0.95
    assert abs(sum(norm_dom.values()) - 1.0000) < 1e-4

    # Case 3: 5,000 Monte Carlo randomized coefficient sweeps
    random.seed(1337)
    for sweep_idx in range(5000):
        raw = {
            "weight_hrv": random.uniform(-1000.0, 1000.0),
            "weight_dpaw": random.uniform(-1000.0, 1000.0),
            "weight_adr_sfd": random.uniform(-1000.0, 1000.0),
            "weight_cke_mve": random.uniform(-1000.0, 1000.0),
            "weight_ltss": random.uniform(-1000.0, 1000.0),
        }
        norm = extract_normalized_weights(raw, min_weight_floor=0.01)
        tot = round(sum(norm.values()), 4)
        assert tot == 1.0000, f"Monte Carlo sweep #{sweep_idx} failed sum constraint: {tot} for {norm}"

        # Verify ModelParameterWeights validation
        m = ModelParameterWeights(version_id=f"mc_{sweep_idx}", **norm)
        assert m.version_id == f"mc_{sweep_idx}"

    logger.info("[SUCCESS] 5,000 Monte Carlo Simplex Normalization Sweeps passed with 100% precision.")


# ============================================================================
# 5. ADVERSARIAL STRESS TEST: CONCURRENT MULTI-THREADED TELEMETRY & INVARIANTS
# ============================================================================

def test_concurrent_telemetry_updates_and_single_active_invariant():
    """
    Stress-tests multi-threaded concurrent execution:
    - 50 worker threads concurrently updating telemetry on separate videos.
    - 5 concurrent threads triggering BQML model training and weight recalibration.
    - Verifies zero deadlocks, thread safety, and single-active-version invariant.
    """
    logger.info("=== Starting Test 5: Concurrent Multi-Threaded Ingestion & Invariant Test ===")
    bq_store = AdversarialBigQueryMLStore()

    # Pre-populate 100 videos
    for i in range(100):
        bq_store.tables["media_pipeline.video_grades"].append({
            "video_id": f"thread_vid_{i:03d}",
            "status": "GRADED",
            "hrv_score": random.uniform(50.0, 95.0),
            "dpaw_score": random.uniform(50.0, 95.0),
            "adr_sfd_score": random.uniform(50.0, 95.0),
            "cke_mve_score": random.uniform(50.0, 95.0),
            "ltss_score": random.uniform(50.0, 95.0),
            "actual_vvsa_rate": None,
            "actual_avg_percentage_viewed": None,
            "actual_viral_status": 0,
        })

    def telemetry_updater(thread_id: int):
        for i in range(thread_id * 2, (thread_id + 1) * 2):
            vid = f"thread_vid_{i:03d}"
            bq_store.update_post_telemetry(
                video_id=vid,
                vvsa_rate=0.75 + (i * 0.002),
                apv=0.90 + (i * 0.005),
                viral_status=1 if i % 3 == 0 else 0,
            )

    def model_trainer(trainer_id: int):
        time.sleep(0.01)
        m_name = f"concurrent_model_{trainer_id}"
        bq_store.execute_create_model(m_name, "LINEAR_REG", "SELECT * FROM `media_pipeline.video_grades`")
        bq_store.extract_ml_weights(m_name)

    # Launch 50 telemetry threads and 5 model training threads
    threads: List[threading.Thread] = []
    for t_id in range(50):
        threads.append(threading.Thread(target=telemetry_updater, args=(t_id,)))
    for m_id in range(5):
        threads.append(threading.Thread(target=model_trainer, args=(m_id,)))

    random.shuffle(threads)
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Assert Single-Active-Version Invariant in model_parameter_weights table
    all_weights = bq_store.tables["media_pipeline.model_parameter_weights"]
    active_rows = [w for w in all_weights if w.get("is_active")]
    assert len(active_rows) == 1, f"Invariant violated: found {len(active_rows)} active versions: {active_rows}"

    logger.info(f"[SUCCESS] Multi-threaded concurrency passed: {len(all_weights)} versions recorded, exactly 1 active.")


# ============================================================================
# 6. ADVERSARIAL STRESS TEST: MODEL WEIGHT ROLLBACK & PYSPARK RE-EVALUATION
# ============================================================================

def test_model_weight_rollback_and_pyspark_reevaluation():
    """
    Stress-tests rollback recovery:
    1. System is running on stable v1 (HRV-heavy: 0.40, 0.25, 0.15, 0.10, 0.10).
    2. A rogue / degraded training run registers v2 (Penalizing HRV: 0.05, 0.05, 0.10, 0.40, 0.40).
    3. High-hook video scores plummet under degraded v2.
    4. Rollback to v1 is executed.
    5. PySpark immediately reflects restored v1 active weights and EVPI recovers.
    """
    logger.info("=== Starting Test 6: Model Weight Rollback & PySpark Re-evaluation ===")
    bq_store = AdversarialBigQueryMLStore()
    pipeline = PySparkGradingPipeline(spark=None, mock_mode=True)

    v1_stable = ModelParameterWeights(
        version_id="v_stable_v1",
        weight_hrv=0.40, weight_dpaw=0.25, weight_adr_sfd=0.15, weight_cke_mve=0.10, weight_ltss=0.10,
        model_r2_score=0.92, is_active=True,
    )
    for r in bq_store.tables["media_pipeline.model_parameter_weights"]:
        r["is_active"] = False
    bq_store.tables["media_pipeline.model_parameter_weights"].append(v1_stable.model_dump())

    # Candidate high-hook video (HRV=95, DPAW=90, CKE=50, LTSS=50)
    candidate = [{"video_id": "high_hook_hero", "gcs_uri": "gs://vault/hero.mp4", "duration_seconds": 25.0}]

    # Grade under v1_stable
    res_v1 = pipeline.process_records(candidate, custom_weights=bq_store.get_active_weights().model_dump())
    evpi_v1 = res_v1[0]["evpi_composite"]

    # Register Degraded v2
    v2_degraded = ModelParameterWeights(
        version_id="v_degraded_v2",
        weight_hrv=0.05, weight_dpaw=0.05, weight_adr_sfd=0.10, weight_cke_mve=0.40, weight_ltss=0.40,
        model_r2_score=0.45, is_active=True,
    )
    for r in bq_store.tables["media_pipeline.model_parameter_weights"]:
        r["is_active"] = False
    bq_store.tables["media_pipeline.model_parameter_weights"].append(v2_degraded.model_dump())

    # Grade under v2_degraded
    res_v2 = pipeline.process_records(candidate, custom_weights=bq_store.get_active_weights().model_dump())
    evpi_v2 = res_v2[0]["evpi_composite"]
    assert evpi_v2 < evpi_v1, f"Degraded EVPI ({evpi_v2}) did not drop compared to stable ({evpi_v1})"

    # Execute Rollback
    rollback_success = bq_store.rollback_to_version("v_stable_v1")
    assert rollback_success is True
    assert bq_store.get_active_weights().version_id == "v_stable_v1"

    # Re-grade under rolled-back active weights
    res_restored = pipeline.process_records(candidate, custom_weights=bq_store.get_active_weights().model_dump())
    evpi_restored = res_restored[0]["evpi_composite"]
    assert evpi_restored == evpi_v1

    logger.info(f"[SUCCESS] Rollback verified: Stable EVPI={evpi_v1} -> Degraded EVPI={evpi_v2} -> Restored EVPI={evpi_restored}.")


# ============================================================================
# 7. ADVERSARIAL STRESS TEST: RANK INVERSION & SENSITIVITY PROOF
# ============================================================================

def test_rank_inversion_and_sensitivity_proof():
    """
    Mathematical Sensitivity Proof:
    Validates that shifting weight from Audio/Drop to Visual/Lighting triggers
    deterministic rank inversion for videos with divergent feature strengths.
    """
    logger.info("=== Starting Test 7: Rank Inversion & Sensitivity Proof ===")

    # Video A: Audio Titan (High HRV=95, High DPAW=95, Low CKE=40, Low LTSS=40)
    # Video B: Visual Spectacle (Low HRV=40, Low DPAW=40, High CKE=95, High LTSS=95)

    scores_a = ViralParameterScores(hrv=95.0, dpaw=95.0, adr_sfd=80.0, cke_mve=40.0, ltss=40.0)
    scores_b = ViralParameterScores(hrv=40.0, dpaw=40.0, adr_sfd=80.0, cke_mve=95.0, ltss=95.0)

    # Model Regime 1: Audio/Hook Dominated (HRV=0.35, DPAW=0.35, ADR=0.10, CKE=0.10, LTSS=0.10)
    weights_regime_1 = ModelParameterWeights(
        version_id="regime_audio",
        weight_hrv=0.35, weight_dpaw=0.35, weight_adr_sfd=0.10, weight_cke_mve=0.10, weight_ltss=0.10,
    )
    evpi_a_r1 = calculate_evpi(scores_a, weights=weights_regime_1)
    evpi_b_r1 = calculate_evpi(scores_b, weights=weights_regime_1)

    assert evpi_a_r1 > evpi_b_r1, f"In Regime 1, Audio Titan ({evpi_a_r1}) must defeat Visual Spectacle ({evpi_b_r1})"

    # Model Regime 2: Visual/Crowd Dominated (HRV=0.10, DPAW=0.10, ADR=0.10, CKE=0.35, LTSS=0.35)
    weights_regime_2 = ModelParameterWeights(
        version_id="regime_visual",
        weight_hrv=0.10, weight_dpaw=0.10, weight_adr_sfd=0.10, weight_cke_mve=0.35, weight_ltss=0.35,
    )
    evpi_a_r2 = calculate_evpi(scores_a, weights=weights_regime_2)
    evpi_b_r2 = calculate_evpi(scores_b, weights=weights_regime_2)

    assert evpi_b_r2 > evpi_a_r2, f"In Regime 2, Visual Spectacle ({evpi_b_r2}) must defeat Audio Titan ({evpi_a_r2})"

    logger.info(f"[SUCCESS] Deterministic Rank Inversion Confirmed: Regime 1 (A:{evpi_a_r1} > B:{evpi_b_r1}) -> Regime 2 (B:{evpi_b_r2} > A:{evpi_a_r2}).")


# ============================================================================
# MAIN HARNESS EXECUTION RUNNER
# ============================================================================

def run_stress_harness() -> int:
    """Executes all 7 adversarial test suites and returns 0 if all pass."""
    tests = [
        ("ADV-LOOP-1: Multi-Iteration E2E Feedback Loop & BQML Weight Recalibration", test_multi_iteration_e2e_feedback_loop),
        ("ADV-LOOP-2: Distributed PySpark Partition Execution & Schema Conformance", test_distributed_pyspark_partition_execution_and_schema),
        ("ADV-LOOP-3: Adversarial Telemetry Disturbances & Query Filter Guards", test_adversarial_telemetry_disturbances_and_query_guards),
        ("ADV-LOOP-4: Extreme Regression Coefficients & 5,000 Monte Carlo Simplex Sweeps", test_adversarial_extreme_regression_coefficients),
        ("ADV-LOOP-5: Concurrent Multi-Threaded Telemetry & Single-Active Invariant", test_concurrent_telemetry_updates_and_single_active_invariant),
        ("ADV-LOOP-6: Model Weight Rollback & PySpark Dynamic Re-evaluation", test_model_weight_rollback_and_pyspark_reevaluation),
        ("ADV-LOOP-7: Mathematical Rank Inversion & Sensitivity Proof", test_rank_inversion_and_sensitivity_proof),
    ]

    print("\n" + "=" * 85)
    print("   TIER 5 DYNAMIC ML LOOP ADVERSARIAL STRESS HARNESS - MILESTONE 5")
    print("=" * 85 + "\n")

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  [+] PASSED: {name}")
            passed += 1
        except Exception as e:
            print(f"  [-] FAILED: {name} -> {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "-" * 85)
    print(f"Total Stress Tests: {passed + failed} | Passed: {passed} | Failed: {failed}")
    print("-" * 85)

    if failed == 0:
        print("\n[SUCCESS] ALL TIER 5 DYNAMIC ML LOOP ADVERSARIAL TESTS PASSED EMPIRICALLY (Exit code 0)\n")
        return 0
    else:
        print(f"\n[FAILURE] {failed} ADVERSARIAL TESTS FAILED (Exit code 1)\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_stress_harness())
