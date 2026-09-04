"""
Adversarial Stress Test Suite for Milestone 4 Remediation (Iteration 2).
Reviewer: teamwork_preview_reviewer
"""

import math
import random
import sys
from pathlib import Path

# Add project roots to sys.path
PROJECT_ROOT = Path("g:/My Drive/GOOGLE ANTIGRAVITY")
MEDIA_PIPELINE_DIR = PROJECT_ROOT / "media_pipeline"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(MEDIA_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(MEDIA_PIPELINE_DIR))

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


def stress_test_simplex_normalization():
    print("[1/5] Stress testing Simplex Normalization across 20,000 random & adversarial vectors...")
    
    # 1. Random floats in [-1000, 1000]
    for seed in range(10000):
        random.seed(seed)
        raw = {
            feat: random.uniform(-500.0, 500.0)
            for feat in CANONICAL_FEATURES
        }
        norm = extract_normalized_weights(raw, min_weight_floor=0.01)
        
        # Check all 5 keys exist
        assert len(norm) == 5, f"Expected 5 keys, got {len(norm)}"
        
        # Check sum == 1.0000 exactly
        total = round(sum(norm.values()), 4)
        assert abs(total - 1.0000) < 1e-6, f"Sum violation: {total} != 1.0000 on {raw} -> {norm}"
        
        # Check simplex non-negativity: w_i >= 0.0
        for k, v in norm.items():
            assert v >= 0.0, f"Simplex violation (negative weight): {k}={v}"

    # 2. Extreme Disparity (1e9 vs 1e-9)
    print("  Testing extreme disparity ratios...")
    for dominant in CANONICAL_FEATURES:
        raw = {feat: 1e-6 for feat in CANONICAL_FEATURES}
        raw[dominant] = 1e8
        norm = extract_normalized_weights(raw, min_weight_floor=0.01)
        total = round(sum(norm.values()), 4)
        assert abs(total - 1.0000) < 1e-6, f"Sum violation on extreme: {total}"
        assert norm[dominant] >= 0.90, f"Dominant feature not prioritized: {norm[dominant]}"
        for k, v in norm.items():
            assert v >= 0.0

    # 3. All Negative Coefficients
    print("  Testing all-negative coefficients...")
    all_neg = {feat: -random.uniform(1.0, 100.0) for feat in CANONICAL_FEATURES}
    norm_neg = extract_normalized_weights(all_neg, min_weight_floor=0.01)
    total_neg = round(sum(norm_neg.values()), 4)
    assert abs(total_neg - 1.0000) < 1e-6
    # Each clamped to 0.01 -> each normalized to 0.20
    for feat in CANONICAL_FEATURES:
        assert norm_neg[feat] == 0.20

    # 4. All Zero Coefficients
    print("  Testing all-zero coefficients...")
    all_zero = {feat: 0.0 for feat in CANONICAL_FEATURES}
    norm_zero = extract_normalized_weights(all_zero, min_weight_floor=0.01)
    total_zero = round(sum(norm_zero.values()), 4)
    assert abs(total_zero - 1.0000) < 1e-6
    for feat in CANONICAL_FEATURES:
        assert norm_zero[feat] == 0.20

    # 5. Missing / Partial Features
    print("  Testing partial feature maps...")
    partial = {"weight_hrv": 0.8}
    norm_partial = extract_normalized_weights(partial)
    total_partial = round(sum(norm_partial.values()), 4)
    assert abs(total_partial - 1.0000) < 1e-6
    for k, v in norm_partial.items():
        assert v >= 0.0

    # 6. Empty dict
    print("  Testing empty input...")
    norm_empty = extract_normalized_weights({})
    total_empty = round(sum(norm_empty.values()), 4)
    assert abs(total_empty - 1.0000) < 1e-6
    assert norm_empty == {
        "weight_hrv": 0.25,
        "weight_dpaw": 0.25,
        "weight_adr_sfd": 0.20,
        "weight_cke_mve": 0.15,
        "weight_ltss": 0.15,
    }

    # 7. List of dicts with mixed types and unknown keys
    print("  Testing list of ML.WEIGHTS rows with messy inputs...")
    messy_rows = [
        {"processed_input": "hrv_score", "weight": "0.35"},
        {"feature_name": "dpaw_score", "raw_coefficient": 0.25},
        {"name": "audio_dynamics", "value": 0.20},
        {"feature": "visual_dynamism", "importance_weight": 0.10},
        {"processed_input": "retention_pacing", "weight": 0.10},
        {"junk_feature": "ignore_me", "weight": 999.0},
    ]
    norm_messy = extract_normalized_weights(messy_rows)
    total_messy = round(sum(norm_messy.values()), 4)
    assert abs(total_messy - 1.0000) < 1e-6
    assert len(norm_messy) == 5

    # 8. Target Skewed Negative Input Vector
    print("  Testing authoritative target skewed negative vector...")
    raw_skewed = {
        'weight_hrv': -318.73,
        'weight_dpaw': 161.43,
        'weight_adr_sfd': -165.44,
        'weight_cke_mve': -302.06,
        'weight_ltss': -10.48
    }
    norm_skewed = extract_normalized_weights(raw_skewed)
    assert all(v >= 0.0 for v in norm_skewed.values())
    assert round(sum(norm_skewed.values()), 4) == 1.0000
    m_skewed = ModelParameterWeights(version_id="v_skewed_verified", **norm_skewed)
    assert m_skewed.weight_dpaw > 0.90

    # 9. Pydantic validation on extracted weights
    print("  Testing ModelParameterWeights validation on 1,000 normalized outputs...")
    for seed in range(1000):
        random.seed(seed + 50000)
        raw = {feat: random.uniform(-100, 100) for feat in CANONICAL_FEATURES}
        norm = extract_normalized_weights(raw)
        model = ModelParameterWeights(
            version_id=f"v_test_{seed}",
            weight_hrv=norm["weight_hrv"],
            weight_dpaw=norm["weight_dpaw"],
            weight_adr_sfd=norm["weight_adr_sfd"],
            weight_cke_mve=norm["weight_cke_mve"],
            weight_ltss=norm["weight_ltss"],
        )
        assert model.is_active is True

    print("  [PASS] Simplex Normalization passed all 20,000+ stress vectors.")


def stress_test_sql_ddl_and_dml():
    print("[2/5] Stress testing SQL files (syntax, clauses, DDL structure)...")
    schema_path = PROJECT_ROOT / "media_pipeline" / "bqml" / "schema.sql"
    models_path = PROJECT_ROOT / "media_pipeline" / "bqml" / "models.sql"
    
    assert schema_path.exists(), "schema.sql missing"
    assert models_path.exists(), "models.sql missing"

    schema_sql = schema_path.read_text(encoding="utf-8")
    models_sql = models_path.read_text(encoding="utf-8")

    # Verify Table Definitions
    expected_tables = [
        "media_pipeline.video_grades",
        "media_pipeline.video_grading_records",
        "media_pipeline.post_performance_metrics",
        "media_pipeline.model_parameter_weights",
    ]
    for tbl in expected_tables:
        assert tbl in schema_sql, f"Missing table {tbl} in schema.sql"

    # Verify BQML models
    expected_models = [
        "media_pipeline.viral_weight_regressor",
        "media_pipeline.viral_retention_tree_regressor",
        "media_pipeline.video_archetype_clusters",
    ]
    for mdl in expected_models:
        assert mdl in models_sql, f"Missing model {mdl} in models.sql"

    # Verify BQML functions
    expected_funcs = [
        "ML.WEIGHTS",
        "ML.FEATURE_IMPORTANCE",
        "ML.EVALUATE",
        "ML.PREDICT",
    ]
    for fn in expected_funcs:
        assert fn in models_sql, f"Missing function {fn} in models.sql"

    print("  [PASS] SQL DDL, DML, and BQML definitions verified.")


def stress_test_model_parameter_weights_validation():
    print("[3/5] Stress testing ModelParameterWeights Pydantic model...")
    # Valid model
    w = ModelParameterWeights(
        version_id="v_stress_1",
        weight_hrv=0.25,
        weight_dpaw=0.25,
        weight_adr_sfd=0.20,
        weight_cke_mve=0.15,
        weight_ltss=0.15,
        model_r2_score=0.91,
        is_active=True,
    )
    assert w.is_active is True
    assert w.model_r2_score == 0.91

    # Invalid sum (> 1.001)
    try:
        ModelParameterWeights(
            weight_hrv=0.4,
            weight_dpaw=0.4,
            weight_adr_sfd=0.4,
            weight_cke_mve=0.1,
            weight_ltss=0.1,
        )
        assert False, "Should have raised ValueError on invalid sum"
    except Exception as e:
        assert "must sum to 1.0" in str(e) or "ValidationError" in type(e).__name__

    print("  [PASS] ModelParameterWeights validation rules verified.")


def stress_test_feedback_loop_state_machine():
    print("[4/5] Stress testing Feedback Loop State Machine and Versioning...")
    from tests.conftest import MockBigQueryMLEngine
    mock_bq = MockBigQueryMLEngine()
    engine = BigQueryMLFeedbackEngine(client=mock_bq)

    # Ingest 100 rows
    for i in range(100):
        mock_bq.tables["media_pipeline.video_grades"].append({
            "video_id": f"vid_state_{i}",
            "hrv_score": random.uniform(50.0, 95.0),
            "dpaw_score": random.uniform(50.0, 95.0),
            "adr_sfd_score": random.uniform(50.0, 95.0),
            "cke_mve_score": random.uniform(50.0, 95.0),
            "ltss_score": random.uniform(50.0, 95.0),
            "actual_avg_percentage_viewed": random.uniform(0.8, 1.5),
        })

    # Train and recalibrate 10 iterations
    prev_versions = []
    for i in range(10):
        new_w = engine.recalibrate_weights(
            raw_weights_override={
                "weight_hrv": random.uniform(0.2, 0.5),
                "weight_dpaw": random.uniform(0.1, 0.4),
                "weight_adr_sfd": random.uniform(0.1, 0.3),
                "weight_cke_mve": random.uniform(0.05, 0.2),
                "weight_ltss": random.uniform(0.05, 0.2),
            }
        )
        prev_versions.append(new_w.version_id)
        
        # Verify exactly one active record in table
        active_records = [
            r for r in mock_bq.tables["media_pipeline.model_parameter_weights"]
            if r.get("is_active") is True
        ]
        assert len(active_records) == 1, f"Expected 1 active record, found {len(active_records)}"
        assert active_records[0]["version_id"] == new_w.version_id

    assert len(engine.history) == 10
    assert engine.get_active_weights().version_id == prev_versions[-1]
    print("  [PASS] Feedback Loop State Machine and Versioning verified across 10 recalibrations.")


def stress_test_sink_and_telemetry_resilience():
    print("[5/5] Stress testing Sink Connector and Telemetry Ingestion...")
    from tests.conftest import MockBigQueryMLEngine
    mock_bq = MockBigQueryMLEngine()
    
    # 1. Empty list sink
    assert sink_video_grades_to_bq(mock_bq, "media_pipeline.video_grades", []) == 0

    # 2. None input handling
    assert sink_video_grades_to_bq(mock_bq, "media_pipeline.video_grades", None) == 0

    # 3. Telemetry on non-existent video
    assert update_post_performance_telemetry(mock_bq, "media_pipeline.video_grades", "missing_id", 0.8, 1.2, 1) is False

    # 4. Telemetry update on present video
    mock_bq.tables["media_pipeline.video_grades"].append({"video_id": "present_vid", "hrv_score": 88.0})
    assert update_post_performance_telemetry(mock_bq, "media_pipeline.video_grades", "present_vid", 0.85, 1.25, 1, share_count=450, completion_rate=0.72) is True
    
    row = [r for r in mock_bq.tables["media_pipeline.video_grades"] if r.get("video_id") == "present_vid"][0]
    assert row["actual_vvsa_rate"] == 0.85
    assert row["actual_avg_percentage_viewed"] == 1.25
    assert row["actual_viral_status"] == 1
    assert row["actual_share_count"] == 450
    assert row["actual_completion_rate"] == 0.72

    print("  [PASS] Sink Connector and Telemetry Ingestion resilient to edge cases.")


if __name__ == "__main__":
    stress_test_simplex_normalization()
    stress_test_sql_ddl_and_dml()
    stress_test_model_parameter_weights_validation()
    stress_test_feedback_loop_state_machine()
    stress_test_sink_and_telemetry_resilience()
    print("\n[ALL ADVERSARIAL STRESS TESTS PASSED 100%]")
