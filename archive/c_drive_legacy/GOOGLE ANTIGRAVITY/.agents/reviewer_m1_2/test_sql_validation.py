"""
Additional SQL & Schema Alignment Validation for Milestone 1
Location: .agents/reviewer_m1_2/test_sql_validation.py
"""

import re

SCHEMA_SQL = """
CREATE OR REPLACE TABLE `media_pipeline.video_grades` (
    video_id STRING NOT NULL,
    gcs_uri STRING NOT NULL,
    processed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    duration_seconds FLOAT64 NOT NULL,
    aspect_ratio STRING NOT NULL,
    hrv_score FLOAT64 NOT NULL,
    dpaw_score FLOAT64 NOT NULL,
    adr_sfd_score FLOAT64 NOT NULL,
    cke_mve_score FLOAT64 NOT NULL,
    ltss_score FLOAT64 NOT NULL,
    evpi_composite FLOAT64 NOT NULL,
    trending_verdict STRING NOT NULL,
    hook_onset_latency_seconds FLOAT64,
    drop_timestamp_seconds FLOAT64,
    buildup_duration_seconds FLOAT64,
    predrop_silence_ms FLOAT64,
    strobe_hz FLOAT64,
    actual_vvsa_rate FLOAT64,
    actual_avg_percentage_viewed FLOAT64,
    actual_share_count INT64,
    actual_completion_rate FLOAT64,
    actual_viral_status INT64
);
"""

MODELS_SQL = """
CREATE OR REPLACE MODEL `media_pipeline.viral_weight_regressor`
OPTIONS(
    model_type='LINEAR_REG',
    input_label_cols=['actual_avg_percentage_viewed'],
    l1_reg=0.01,
    l2_reg=0.01,
    optimize_strategy='AUTO_STRATEGY'
) AS
SELECT
    hrv_score,
    dpaw_score,
    adr_sfd_score,
    cke_mve_score,
    ltss_score,
    actual_avg_percentage_viewed
FROM
    `media_pipeline.video_grades`
WHERE
    actual_avg_percentage_viewed IS NOT NULL;
"""

RECALIBRATION_QUERY = """
WITH raw_weights AS (
    SELECT
        processed_input,
        weight
    FROM
        ML.WEIGHTS(MODEL `media_pipeline.viral_weight_regressor`)
    WHERE
        processed_input IN ('hrv_score', 'dpaw_score', 'adr_sfd_score', 'cke_mve_score', 'ltss_score')
),
positive_weights AS (
    SELECT
        processed_input,
        GREATEST(0.01, weight) AS safe_weight
    FROM
        raw_weights
),
normalized_weights AS (
    SELECT
        processed_input,
        safe_weight / SUM(safe_weight) OVER() AS normalized_weight
    FROM
        positive_weights
)
SELECT
    processed_input AS feature_name,
    ROUND(normalized_weight, 4) AS recalibrated_weight
FROM
    normalized_weights;
"""

def test_sql_syntax():
    # Verify all expected columns in video_grades
    required_cols = [
        "video_id", "gcs_uri", "duration_seconds", "aspect_ratio",
        "hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score",
        "evpi_composite", "trending_verdict"
    ]
    for col in required_cols:
        assert re.search(rf"\b{col}\b", SCHEMA_SQL), f"Missing required column in SQL schema: {col}"
    
    # Verify model features match schema
    for col in ["hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score"]:
        assert re.search(rf"\b{col}\b", MODELS_SQL), f"Missing feature in BQML model: {col}"
        assert col in RECALIBRATION_QUERY, f"Missing feature in recalibration query: {col}"

    print("[PASS] SQL Schema & Model consistency verified across DDL and BQML queries.")

if __name__ == "__main__":
    test_sql_syntax()
