#!/usr/bin/env python3
"""
test_bqml_loop.py - Deterministic Verification Test Suite for Milestone 4 (BigQuery ML Loop).
Tests:
1. SQL Schema DDL Syntax & Column Parsing (schema.sql).
2. BigQuery ML Model Definitions & Options Validation (models.sql).
3. Simplex Weight Normalization & Mathematical Floor Bounds (extract_normalized_weights).
4. Automated Dynamic Weight Recalibration & State Lifecycle (recalibrate_model_weights).
5. BigQuery Sink Connector & Post-Performance Telemetry Ingestion.
6. End-to-End Dynamic Feedback Loop with PySpark Grading Engine.

Can be run standalone via `python test_bqml_loop.py` or with `pytest`.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
import pytest

# Ensure parent directory is in sys.path
CURRENT_DIR = Path(__file__).parent.resolve()
MEDIA_PIPELINE_DIR = CURRENT_DIR.parent.resolve()
if str(MEDIA_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(MEDIA_PIPELINE_DIR))
if str(MEDIA_PIPELINE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(MEDIA_PIPELINE_DIR.parent))

try:
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
except ImportError:
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

try:
    from media_pipeline.grading.viral_schema import (
        EDMShortsViralMetrics,
        EDMViralGradingReport,
        TrendingVerdict,
        ViralParameterScores,
        calculate_evpi,
        get_verdict_from_evpi,
    )
except ImportError:
    from tests.conftest import (
        EDMShortsViralMetrics,
        TrendingVerdict,
        ViralParameterScores,
        calculate_evpi,
        get_verdict_from_evpi,
    )

try:
    from tests.conftest import MockBigQueryMLEngine, MockGeminiOmniClient, MockPySparkGradingEngine, MockGCSClient
except ImportError:
    # Minimal fallback mock
    class MockBigQueryMLEngine:
        def __init__(self):
            self.tables = {
                "media_pipeline.video_grades": [],
                "media_pipeline.model_parameter_weights": [
                    ModelParameterWeights(version_id="v1.0.0_baseline").model_dump()
                ],
            }
            self.models = {}

        def sink_video_grades(self, metrics):
            for m in metrics:
                self.tables["media_pipeline.video_grades"].append(m.model_dump() if hasattr(m, "model_dump") else m)
            return len(metrics)

        def update_post_telemetry(self, video_id, vvsa_rate, apv, viral_status):
            for r in self.tables["media_pipeline.video_grades"]:
                if r.get("video_id") == video_id:
                    r["actual_vvsa_rate"] = vvsa_rate
                    r["actual_avg_percentage_viewed"] = apv
                    r["actual_viral_status"] = viral_status
                    return True
            return False

        def execute_create_model(self, model_name, model_type, query_sql):
            self.models[model_name] = {"model_name": model_name, "model_type": model_type, "r2_score": 0.88}
            return self.models[model_name]

        def extract_ml_weights(self, model_name):
            w = extract_normalized_weights({"weight_hrv": 0.30, "weight_dpaw": 0.28, "weight_adr_sfd": 0.18, "weight_cke_mve": 0.12, "weight_ltss": 0.12})
            for r in self.tables["media_pipeline.model_parameter_weights"]:
                r["is_active"] = False
            new_w = ModelParameterWeights(
                version_id=f"v_{model_name}_{int(time.time())}",
                weight_hrv=norm["weight_hrv"],
                weight_dpaw=norm["weight_dpaw"],
                weight_adr_sfd=norm["weight_adr_sfd"],
                weight_cke_mve=norm["weight_cke_mve"],
                weight_ltss=norm["weight_ltss"],
                model_r2_score=0.88,
                is_active=True,
            )
            self.tables["media_pipeline.model_parameter_weights"].append(new_w.model_dump())
            return new_w

        def get_active_weights(self):
            for r in reversed(self.tables["media_pipeline.model_parameter_weights"]):
                if r.get("is_active", True):
                    return ModelParameterWeights(**r)
            return ModelParameterWeights()


# ============================================================================
# 1. SCHEMA DDL TESTS
# ============================================================================

def test_schema_sql_file_exists_and_readable():
    """Validates that schema.sql exists and contains valid CREATE TABLE statements."""
    schema_path = CURRENT_DIR / "schema.sql"
    assert schema_path.exists(), f"schema.sql not found at {schema_path}"
    content = schema_path.read_text(encoding="utf-8")
    assert len(content) > 200
    assert "CREATE TABLE" in content


def test_schema_sql_table_definitions():
    """Validates presence of all 3 required BigQuery tables and their column schemas."""
    schema_path = CURRENT_DIR / "schema.sql"
    content = schema_path.read_text(encoding="utf-8")

    # Check for video_grades / video_grading_records
    assert "media_pipeline.video_grades" in content or "video_grades" in content
    assert "media_pipeline.video_grading_records" in content or "video_grading_records" in content

    # Check for post_performance_metrics
    assert "media_pipeline.post_performance_metrics" in content or "post_performance_metrics" in content

    # Check for model_parameter_weights
    assert "media_pipeline.model_parameter_weights" in content or "model_parameter_weights" in content

    # Check required viral parameter columns
    assert "hrv_score" in content
    assert "dpaw_score" in content
    assert "adr_sfd_score" in content
    assert "cke_mve_score" in content
    assert "ltss_score" in content
    assert "evpi_composite" in content
    assert "trending_verdict" in content

    # Check post-telemetry columns
    assert "actual_vvsa_rate" in content
    assert "actual_avg_percentage_viewed" in content
    assert "actual_viral_status" in content

    # Check Partitioning and Clustering
    assert "PARTITION BY" in content
    assert "CLUSTER BY" in content


# ============================================================================
# 2. BQML MODELS DDL TESTS
# ============================================================================

def test_models_sql_file_exists_and_readable():
    """Validates that models.sql exists and contains BQML CREATE MODEL statements."""
    models_path = CURRENT_DIR / "models.sql"
    assert models_path.exists(), f"models.sql not found at {models_path}"
    content = models_path.read_text(encoding="utf-8")
    assert len(content) > 300
    assert "CREATE OR REPLACE MODEL" in content


def test_models_sql_all_required_architectures():
    """Validates LINEAR_REG, BOOSTED_TREE_REGRESSOR, KMEANS, and ML operations in models.sql."""
    models_path = CURRENT_DIR / "models.sql"
    content = models_path.read_text(encoding="utf-8")

    # 1. Linear Regression
    assert "model_type='LINEAR_REG'" in content
    assert "viral_weight_regressor" in content or "viral_linear_weights_model" in content
    assert "input_label_cols" in content

    # 2. Boosted Tree Regressor
    assert "model_type='BOOSTED_TREE_REGRESSOR'" in content
    assert "viral_retention_tree_regressor" in content or "viral_predictor_boosted_tree" in content
    assert "tree_method='HIST'" in content or "tree_method" in content

    # 3. K-Means
    assert "model_type='KMEANS'" in content
    assert "num_clusters=4" in content or "num_clusters" in content
    assert "video_archetype_clusters" in content

    # 4. Evaluation and Feature Inspection Queries
    assert "ML.EVALUATE" in content
    assert "ML.WEIGHTS" in content
    assert "ML.FEATURE_IMPORTANCE" in content
    assert "ML.PREDICT" in content


# ============================================================================
# 3. WEIGHT NORMALIZATION ALGORITHM TESTS
# ============================================================================

def test_extract_normalized_weights_standard():
    """Validates standard weights normalization strictly summing to 1.0000."""
    raw = {
        "weight_hrv": 0.35,
        "weight_dpaw": 0.25,
        "weight_adr_sfd": 0.20,
        "weight_cke_mve": 0.10,
        "weight_ltss": 0.10,
    }
    norm = extract_normalized_weights(raw)
    assert set(norm.keys()) == set(CANONICAL_FEATURES)
    total = sum(norm.values())
    assert abs(total - 1.0000) < 1e-6
    assert norm["weight_hrv"] == 0.35
    assert norm["weight_dpaw"] == 0.25


def test_extract_normalized_weights_from_ml_weights_rows():
    """Validates parsing list of ML.WEIGHTS query row dictionaries."""
    ml_rows = [
        {"processed_input": "hrv_score", "weight": 0.42},
        {"processed_input": "dpaw_score", "weight": 0.28},
        {"processed_input": "adr_sfd_score", "weight": 0.15},
        {"processed_input": "cke_mve_score", "weight": 0.08},
        {"processed_input": "ltss_score", "weight": 0.07},
    ]
    norm = extract_normalized_weights(ml_rows)
    total = sum(norm.values())
    assert abs(total - 1.0000) < 1e-6
    assert norm["weight_hrv"] > norm["weight_dpaw"] > norm["weight_adr_sfd"]


def test_extract_normalized_weights_handles_negative_and_zero():
    """Validates that negative or zero coefficients are clamped to positive floor."""
    raw = {
        "hrv_score": -0.15,
        "dpaw_score": 0.0,
        "adr_sfd_score": 0.50,
        "cke_mve_score": 0.25,
        "ltss_score": 0.25,
    }
    norm = extract_normalized_weights(raw, min_weight_floor=0.02)
    assert norm["weight_hrv"] >= 0.01
    assert norm["weight_dpaw"] >= 0.01
    total = sum(norm.values())
    assert abs(total - 1.0000) < 1e-6


def test_extract_normalized_weights_with_aliases():
    """Validates legacy column names (hook_strength, audio_drop_sync, etc.) map properly."""
    raw = {
        "hook_strength": 30.0,
        "audio_drop_sync": 25.0,
        "crowd_energy": 20.0,
        "visual_dynamism": 15.0,
        "retention_pacing": 10.0,
    }
    norm = extract_normalized_weights(raw)
    assert norm["weight_hrv"] == 0.30
    assert norm["weight_dpaw"] == 0.25
    assert norm["weight_adr_sfd"] == 0.20
    assert norm["weight_cke_mve"] == 0.15
    assert norm["weight_ltss"] == 0.10
    assert abs(sum(norm.values()) - 1.0000) < 1e-6


def test_extract_normalized_weights_extreme_ratios():
    """Validates normalization with high disparity (one dominant feature)."""
    raw = {
        "weight_hrv": 1000.0,
        "weight_dpaw": 1.0,
        "weight_adr_sfd": 1.0,
        "weight_cke_mve": 1.0,
        "weight_ltss": 1.0,
    }
    norm = extract_normalized_weights(raw)
    assert norm["weight_hrv"] > 0.95
    assert all(norm[k] >= 0.001 for k in CANONICAL_FEATURES)
    assert abs(sum(norm.values()) - 1.0000) < 1e-6


def test_extract_normalized_weights_skewed_negative_vector():
    """Validates normalization with heavily skewed negative weights vector."""
    raw = {
        "weight_hrv": -318.73,
        "weight_dpaw": 161.43,
        "weight_adr_sfd": -165.44,
        "weight_cke_mve": -302.06,
        "weight_ltss": -10.48,
    }
    norm = extract_normalized_weights(raw)
    assert set(norm.keys()) == set(CANONICAL_FEATURES)
    assert all(v >= 0.0 for v in norm.values()), f"Negative weight detected: {norm}"
    total = sum(norm.values())
    assert abs(total - 1.0000) < 1e-6, f"Weights do not sum to 1.0000: {total}"

    # Verify ModelParameterWeights instantiates cleanly without ValidationError
    model_weights = ModelParameterWeights(version_id="v_skewed_test", **norm)
    assert model_weights.version_id == "v_skewed_test"
    assert model_weights.weight_dpaw > 0.90
    assert model_weights.weight_hrv >= 0.0



# ============================================================================
# 4. RECALIBRATION LOOP & ACTIVE WEIGHTS TESTS
# ============================================================================

def test_recalibrate_model_weights_mock_engine():
    """Validates recalibrating weights with mock BigQuery engine."""
    mock_bq = MockBigQueryMLEngine()
    # Add dummy row to allow training
    mock_bq.tables["media_pipeline.video_grades"].append({"video_id": "dummy_1"})
    mock_bq.execute_create_model("viral_weight_regressor", "LINEAR_REG", "SELECT *")

    new_weights = recalibrate_model_weights(client=mock_bq, model_name="viral_weight_regressor")
    assert isinstance(new_weights, ModelParameterWeights)
    assert new_weights.is_active is True
    assert new_weights.version_id.startswith("v_viral_weight_regressor")

    # Verify active weights retrieval
    active = mock_bq.get_active_weights()
    assert active.version_id == new_weights.version_id


def test_recalibrate_model_weights_raw_override():
    """Validates offline recalibration using raw weights override."""
    override = {
        "weight_hrv": 0.40,
        "weight_dpaw": 0.20,
        "weight_adr_sfd": 0.20,
        "weight_cke_mve": 0.10,
        "weight_ltss": 0.10,
    }
    weights = recalibrate_model_weights(raw_weights_override=override, r2_score_override=0.92)
    assert weights.weight_hrv == 0.40
    assert weights.weight_dpaw == 0.20
    assert weights.model_r2_score == 0.92
    assert weights.is_active is True
    assert abs(weights.weight_hrv + weights.weight_dpaw + weights.weight_adr_sfd + weights.weight_cke_mve + weights.weight_ltss - 1.0) < 1e-6


def test_recalibration_deactivates_previous_versions():
    """Validates that older weight versions are deactivated upon recalibration."""
    mock_bq = MockBigQueryMLEngine()
    mock_bq.tables["media_pipeline.video_grades"].append({"video_id": "v1"})
    mock_bq.execute_create_model("m1", "LINEAR_REG", "SELECT *")

    # Baseline is active
    assert mock_bq.tables["media_pipeline.model_parameter_weights"][0]["is_active"] is True

    # Recalibrate 1
    w1 = recalibrate_model_weights(mock_bq, model_name="m1")
    active_rows = [r for r in mock_bq.tables["media_pipeline.model_parameter_weights"] if r["is_active"]]
    assert len(active_rows) == 1
    assert active_rows[0]["version_id"] == w1.version_id

    # Recalibrate 2
    w2 = recalibrate_model_weights(mock_bq, model_name="m1")
    active_rows = [r for r in mock_bq.tables["media_pipeline.model_parameter_weights"] if r["is_active"]]
    assert len(active_rows) == 1
    assert active_rows[0]["version_id"] == w2.version_id


# ============================================================================
# 5. SINK & TELEMETRY INGESTION HELPERS
# ============================================================================

def test_sink_video_grades_to_bq_helper():
    """Validates sink_video_grades_to_bq with Pydantic metrics and dicts."""
    mock_bq = MockBigQueryMLEngine()
    scores = ViralParameterScores(hrv=85.0, dpaw=80.0, adr_sfd=75.0, cke_mve=70.0, ltss=65.0)
    evpi = calculate_evpi(scores)
    verdict = get_verdict_from_evpi(evpi)

    metric = EDMShortsViralMetrics(
        video_id="sink_test_1",
        gcs_uri="gs://edm-media-vault/raw/sink_test_1.mp4",
        duration_seconds=30.0,
        aspect_ratio="9:16",
        scores=scores,
        evpi_composite=evpi,
        trending_verdict=verdict,
    )

    inserted = sink_video_grades_to_bq(mock_bq, "media_pipeline.video_grades", [metric])
    assert inserted == 1
    assert len(mock_bq.tables["media_pipeline.video_grades"]) >= 1

    row = mock_bq.tables["media_pipeline.video_grades"][-1]
    assert row["video_id"] == "sink_test_1"
    assert row["hrv_score"] == 85.0


def test_update_post_performance_telemetry_helper():
    """Validates update_post_performance_telemetry updating retention metrics."""
    mock_bq = MockBigQueryMLEngine()
    mock_bq.tables["media_pipeline.video_grades"].append({
        "video_id": "telemetry_vid",
        "hrv_score": 90.0,
        "actual_vvsa_rate": None,
        "actual_avg_percentage_viewed": None,
    })

    success = update_post_performance_telemetry(
        mock_bq,
        "media_pipeline.video_grades",
        video_id="telemetry_vid",
        vvsa_rate=0.89,
        apv=1.32,
        viral_status=1,
    )
    assert success is True
    row = mock_bq.tables["media_pipeline.video_grades"][-1]
    assert row["actual_vvsa_rate"] == 0.89
    assert row["actual_avg_percentage_viewed"] == 1.32
    assert row["actual_viral_status"] == 1


# ============================================================================
# 6. HIGH-LEVEL FEEDBACK ENGINE END-TO-END WORKFLOW
# ============================================================================

def test_feedback_engine_end_to_end_lifecycle():
    """
    Validates complete end-to-end ML optimization lifecycle:
    1. Video grading results ingested into BigQuery.
    2. Post-publishing engagement telemetry recorded.
    3. Model trained on paired data.
    4. Weight recalibration executed and verified.
    5. Active weights retrieved for downstream PySpark grading.
    """
    mock_bq = MockBigQueryMLEngine()
    engine = BigQueryMLFeedbackEngine(client=mock_bq, dataset="media_pipeline")

    # 1. Ingest 3 video grades
    records = []
    for i in range(3):
        vid = f"loop_vid_{i}"
        scores = ViralParameterScores(
            hrv=70.0 + (i * 10),
            dpaw=75.0 + (i * 5),
            adr_sfd=80.0,
            cke_mve=60.0,
            ltss=65.0,
        )
        evpi = calculate_evpi(scores)
        verdict = get_verdict_from_evpi(evpi)
        m = EDMShortsViralMetrics(
            video_id=vid,
            gcs_uri=f"gs://edm-media-vault/raw/{vid}.mp4",
            duration_seconds=25.0,
            aspect_ratio="9:16",
            scores=scores,
            evpi_composite=evpi,
            trending_verdict=verdict,
        )
        records.append(m)

    sink_count = engine.sink_grades(records)
    assert sink_count == 3

    # 2. Record telemetry
    assert engine.record_telemetry("loop_vid_0", vvsa_rate=0.65, apv=0.85, viral_status=0) is True
    assert engine.record_telemetry("loop_vid_1", vvsa_rate=0.78, apv=1.05, viral_status=0) is True
    assert engine.record_telemetry("loop_vid_2", vvsa_rate=0.92, apv=1.40, viral_status=1) is True

    # 3. Train Model
    train_res = engine.train_model("viral_weight_regressor", "LINEAR_REG")
    assert train_res is not None

    # 4. Recalibrate Weights
    new_weights = engine.recalibrate_weights("viral_weight_regressor")
    assert new_weights.is_active is True
    total = (
        new_weights.weight_hrv +
        new_weights.weight_dpaw +
        new_weights.weight_adr_sfd +
        new_weights.weight_cke_mve +
        new_weights.weight_ltss
    )
    assert abs(total - 1.0000) < 1e-4

    # 5. Fetch Active Weights for Spark Grading
    active = engine.get_active_weights()
    assert active.version_id == new_weights.version_id

    # 6. Re-score a video using newly recalibrated active weights
    test_scores = ViralParameterScores(hrv=95.0, dpaw=90.0, adr_sfd=85.0, cke_mve=70.0, ltss=70.0)
    evpi_recal = calculate_evpi(test_scores, weights=active)
    assert 0.0 <= evpi_recal <= 100.0


# ============================================================================
# MAIN EXECUTION RUNNER
# ============================================================================

def run_all_tests() -> int:
    """Executes all test functions in this module and prints formatted summary."""
    test_functions = [
        ("F12.1: Schema SQL File Existence", test_schema_sql_file_exists_and_readable),
        ("F12.2: Schema Table & Column DDL Structure", test_schema_sql_table_definitions),
        ("F14.1: Models SQL File Existence", test_models_sql_file_exists_and_readable),
        ("F14.2: BQML Model Options & Architectures", test_models_sql_all_required_architectures),
        ("F15.1: Simplex Weight Normalization (Standard)", test_extract_normalized_weights_standard),
        ("F15.2: Simplex Normalization (ML.WEIGHTS list)", test_extract_normalized_weights_from_ml_weights_rows),
        ("F15.3: Simplex Normalization (Negative & Zero Bounds)", test_extract_normalized_weights_handles_negative_and_zero),
        ("F15.4: Simplex Normalization (Legacy Aliases)", test_extract_normalized_weights_with_aliases),
        ("F15.5: Simplex Normalization (Extreme Ratios)", test_extract_normalized_weights_extreme_ratios),
        ("F15.9: Simplex Normalization (Skewed Negative Residual Fix)", test_extract_normalized_weights_skewed_negative_vector),
        ("F15.6: Recalibrate Model Weights via Mock Engine", test_recalibrate_model_weights_mock_engine),
        ("F15.7: Recalibrate Model Weights via Override", test_recalibrate_model_weights_raw_override),
        ("F15.8: Deactivation of Stale Weight Versions", test_recalibration_deactivates_previous_versions),
        ("F13.1: BigQuery Sink Connector Ingestion", test_sink_video_grades_to_bq_helper),
        ("F13.2: Post-Performance Telemetry Updater", test_update_post_performance_telemetry_helper),
        ("F16.1: End-to-End Feedback Engine Lifecycle", test_feedback_engine_end_to_end_lifecycle),
    ]

    print("\n" + "=" * 80)
    print("   BIGQUERY ML OPTIMIZATION LOOP - DETERMINISTIC TEST SUITE")
    print("=" * 80 + "\n")

    passed = 0
    failed = 0

    for name, func in test_functions:
        try:
            func()
            print(f"  [+] PASSED: {name}")
            passed += 1
        except Exception as e:
            print(f"  [-] FAILED: {name} -> {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "-" * 80)
    print(f"Total Tests: {passed + failed} | Passed: {passed} | Failed: {failed}")
    print("-" * 80)

    if failed == 0:
        print("\n[SUCCESS] ALL BIGQUERY ML OPTIMIZATION LOOP TESTS PASSED (Exit code 0)\n")
        return 0
    else:
        print(f"\n[FAILURE] {failed} TESTS FAILED (Exit code 1)\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
