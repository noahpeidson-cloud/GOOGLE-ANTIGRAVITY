-- ============================================================================
-- Google Antigravity EDM Media Pipeline: BigQuery ML Model Definitions
-- Module: media_pipeline.bqml
-- Dataset: media_pipeline
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Linear Regression Model for Empirical Parameter Weight Extraction (ML.WEIGHTS)
-- Uses L1/L2 regularization and standardized features to isolate linear contribution
-- of each viral parameter to actual average percentage viewed (APV).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE MODEL `media_pipeline.viral_weight_regressor`
OPTIONS(
    model_type='LINEAR_REG',
    input_label_cols=['actual_avg_percentage_viewed'],
    l1_reg=0.01,
    l2_reg=0.01,
    standardize_features=TRUE,
    max_iterations=50,
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
    status = 'GRADED'
    AND actual_avg_percentage_viewed IS NOT NULL;


-- ----------------------------------------------------------------------------
-- 2. Gradient Boosted Tree Regressor for Nonlinear Virality Prediction
-- Captures complex interactions between temporal features, drop pacing, audio dynamics,
-- and audience response curves.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE MODEL `media_pipeline.viral_retention_tree_regressor`
OPTIONS(
    model_type='BOOSTED_TREE_REGRESSOR',
    input_label_cols=['actual_avg_percentage_viewed'],
    max_iterations=50,
    learn_rate=0.1,
    subsample=0.85,
    tree_method='HIST'
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
    status = 'GRADED'
    AND actual_avg_percentage_viewed IS NOT NULL;


-- ----------------------------------------------------------------------------
-- 3. K-Means Clustering for Video Archetype Categorization
-- Partitions video catalog into 4 distinct stylistic archetypes:
-- Cluster 0: Peak-Time Drop Explosion (High Bass / Strobes / Jump)
-- Cluster 1: Atmospheric Vocal Riser (High Hook / Melodic Build)
-- Cluster 2: Fast-Paced Rhythmic Groove (High Pacing / Continuous Cut)
-- Cluster 3: Underground Bass Heavy (High Sub-Bass / Mosh Energy)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE MODEL `media_pipeline.video_archetype_clusters`
OPTIONS(
    model_type='KMEANS',
    num_clusters=4,
    standardize_features=TRUE,
    max_iterations=20
) AS
SELECT
    hrv_score,
    dpaw_score,
    adr_sfd_score,
    cke_mve_score,
    ltss_score
FROM
    `media_pipeline.video_grades`
WHERE
    status = 'GRADED';


-- ----------------------------------------------------------------------------
-- 4. Model Evaluation Queries (ML.EVALUATE)
-- ----------------------------------------------------------------------------

-- Evaluate Linear Weights Regressor
SELECT
    *
FROM
    ML.EVALUATE(
        MODEL `media_pipeline.viral_weight_regressor`,
        (
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
                status = 'GRADED'
                AND actual_avg_percentage_viewed IS NOT NULL
        )
    );

-- Evaluate Boosted Tree Regressor
SELECT
    *
FROM
    ML.EVALUATE(
        MODEL `media_pipeline.viral_retention_tree_regressor`,
        (
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
                status = 'GRADED'
                AND actual_avg_percentage_viewed IS NOT NULL
        )
    );

-- Evaluate K-Means Clustering Silhouette Score & Davies-Bouldin Index
SELECT
    *
FROM
    ML.EVALUATE(
        MODEL `media_pipeline.video_archetype_clusters`
    );


-- ----------------------------------------------------------------------------
-- 5. Feature Weights & Feature Importance Extraction Queries
-- ----------------------------------------------------------------------------

-- Extract Raw Linear Coefficients
SELECT
    processed_input AS feature_name,
    weight AS raw_coefficient
FROM
    ML.WEIGHTS(MODEL `media_pipeline.viral_weight_regressor`)
WHERE
    processed_input IN ('hrv_score', 'dpaw_score', 'adr_sfd_score', 'cke_mve_score', 'ltss_score');

-- Extract Boosted Tree Feature Importance
SELECT
    feature,
    importance_weight,
    importance_gain,
    importance_cover
FROM
    ML.FEATURE_IMPORTANCE(MODEL `media_pipeline.viral_retention_tree_regressor`);


-- ----------------------------------------------------------------------------
-- 6. Automated Dynamic Recalibration SQL Query (Simplex Normalization)
-- Normalizes positive coefficients such that sum(weight_i) == 1.0000
-- ----------------------------------------------------------------------------
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


-- ----------------------------------------------------------------------------
-- 7. Batch Inference / Prediction Queries (ML.PREDICT)
-- ----------------------------------------------------------------------------

-- Predict Predicted Retention for New Video Grades
SELECT
    video_id,
    gcs_uri,
    evpi_composite,
    predicted_actual_avg_percentage_viewed AS predicted_apv
FROM
    ML.PREDICT(
        MODEL `media_pipeline.viral_retention_tree_regressor`,
        (
            SELECT
                video_id,
                gcs_uri,
                evpi_composite,
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
                strobe_hz
            FROM
                `media_pipeline.video_grades`
            WHERE
                status = 'GRADED'
        )
    );

-- Assign Stylistic Archetype Cluster to Video Grades
SELECT
    video_id,
    CENTROID_ID AS archetype_cluster_id,
    NEAREST_CENTROIDS_DISTANCE[OFFSET(0)].distance AS cluster_distance
FROM
    ML.PREDICT(
        MODEL `media_pipeline.video_archetype_clusters`,
        (
            SELECT
                video_id,
                hrv_score,
                dpaw_score,
                adr_sfd_score,
                cke_mve_score,
                ltss_score
            FROM
                `media_pipeline.video_grades`
            WHERE
                status = 'GRADED'
        )
    );
