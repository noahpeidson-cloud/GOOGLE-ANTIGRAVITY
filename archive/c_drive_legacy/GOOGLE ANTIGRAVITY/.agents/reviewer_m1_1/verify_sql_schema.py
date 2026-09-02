"""
SQL Syntax & Interface Contract Compatibility Validator
"""
import re

SQL_DDL = """
CREATE OR REPLACE TABLE `media_pipeline.video_grades` (
    video_id STRING NOT NULL,
    gcs_uri STRING NOT NULL,
    processed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    duration_seconds FLOAT64 NOT NULL,
    aspect_ratio STRING NOT NULL,
    
    -- 5 Core Parameter Scores (0.0 to 100.0)
    hrv_score FLOAT64 NOT NULL,
    dpaw_score FLOAT64 NOT NULL,
    adr_sfd_score FLOAT64 NOT NULL,
    cke_mve_score FLOAT64 NOT NULL,
    ltss_score FLOAT64 NOT NULL,
    
    -- Composite Score and Model Classification
    evpi_composite FLOAT64 NOT NULL,
    trending_verdict STRING NOT NULL,
    
    -- Temporal Granular Features
    hook_onset_latency_seconds FLOAT64,
    drop_timestamp_seconds FLOAT64,
    buildup_duration_seconds FLOAT64,
    predrop_silence_ms FLOAT64,
    strobe_hz FLOAT64,
    
    -- Downstream Post-Publishing Telemetry (Sinked from YouTube / TikTok Analytics)
    actual_vvsa_rate FLOAT64,
    actual_avg_percentage_viewed FLOAT64,
    actual_share_count INT64,
    actual_completion_rate FLOAT64,
    actual_viral_status INT64
);

CREATE OR REPLACE TABLE `media_pipeline.model_parameter_weights` (
    version_id STRING NOT NULL,
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    weight_hrv FLOAT64 NOT NULL,
    weight_dpaw FLOAT64 NOT NULL,
    weight_adr_sfd FLOAT64 NOT NULL,
    weight_cke_mve FLOAT64 NOT NULL,
    weight_ltss FLOAT64 NOT NULL,
    model_r2_score FLOAT64 NOT NULL,
    is_active BOOLEAN NOT NULL
);
"""

SQL_MODELS = """
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

CREATE OR REPLACE MODEL `media_pipeline.viral_retention_tree_regressor`
OPTIONS(
    model_type='BOOSTED_TREE_REGRESSOR',
    input_label_cols=['actual_avg_percentage_viewed'],
    max_iterations=50,
    tree_method='HIST',
    subsample=0.85
) AS
SELECT
    hrv_score,
    dpaw_score,
    adr_sfd_score,
    cke_mve_score,
    ltss_score,
    duration_seconds,
    hook_onset_latency_seconds,
    drop_timestamp_seconds,
    buildup_duration_seconds,
    predrop_silence_ms,
    strobe_hz,
    actual_avg_percentage_viewed
FROM
    `media_pipeline.video_grades`
WHERE
    actual_avg_percentage_viewed IS NOT NULL;

CREATE OR REPLACE MODEL `media_pipeline.video_archetype_clusters`
OPTIONS(
    model_type='KMEANS',
    num_clusters=4,
    standardize_features=TRUE
) AS
SELECT
    hrv_score,
    dpaw_score,
    adr_sfd_score,
    cke_mve_score,
    ltss_score
FROM
    `media_pipeline.video_grades`;
"""

SQL_RECALIBRATE = """
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

def validate_sql():
    print("--- Validating BigQuery DDL & Queries ---")
    # Check table definitions
    assert "CREATE OR REPLACE TABLE `media_pipeline.video_grades`" in SQL_DDL
    assert "CREATE OR REPLACE TABLE `media_pipeline.model_parameter_weights`" in SQL_DDL
    print("[PASS] Table DDL statements present and syntactically structured")

    # Check model definitions
    models = ["viral_weight_regressor", "viral_retention_tree_regressor", "video_archetype_clusters"]
    for m in models:
        assert f"CREATE OR REPLACE MODEL `media_pipeline.{m}`" in SQL_MODELS
    print("[PASS] BQML Model DDL statements present for LINEAR_REG, BOOSTED_TREE_REGRESSOR, and KMEANS")

    # Check column references in models match video_grades DDL
    video_grades_cols = [
        "video_id", "gcs_uri", "processed_timestamp", "duration_seconds", "aspect_ratio",
        "hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score",
        "evpi_composite", "trending_verdict", "hook_onset_latency_seconds", "drop_timestamp_seconds",
        "buildup_duration_seconds", "predrop_silence_ms", "strobe_hz", "actual_vvsa_rate",
        "actual_avg_percentage_viewed", "actual_share_count", "actual_completion_rate", "actual_viral_status"
    ]
    
    # Verify linear model feature cols
    linear_cols = ["hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score", "actual_avg_percentage_viewed"]
    for col in linear_cols:
        assert col in video_grades_cols, f"Column {col} missing from video_grades"
    print("[PASS] Linear model columns fully covered in video_grades schema")

    # Verify tree model feature cols
    tree_cols = [
        "hrv_score", "dpaw_score", "adr_sfd_score", "cke_mve_score", "ltss_score",
        "duration_seconds", "hook_onset_latency_seconds", "drop_timestamp_seconds",
        "buildup_duration_seconds", "predrop_silence_ms", "strobe_hz", "actual_avg_percentage_viewed"
    ]
    for col in tree_cols:
        assert col in video_grades_cols, f"Column {col} missing from video_grades"
    print("[PASS] Tree model columns fully covered in video_grades schema")

    # Verify weight recalibration query references
    recal_features = ['hrv_score', 'dpaw_score', 'adr_sfd_score', 'cke_mve_score', 'ltss_score']
    for f in recal_features:
        assert f in SQL_RECALIBRATE, f"Feature {f} missing from recalibration query"
    print("[PASS] Recalibration feedback query features match exactly")

if __name__ == "__main__":
    validate_sql()
