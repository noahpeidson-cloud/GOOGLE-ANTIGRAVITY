-- ============================================================================
-- Google Antigravity EDM Media Pipeline: BigQuery Relational Schemas
-- Module: media_pipeline.bqml
-- Dataset: media_pipeline
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Main Table: video_grades (and video_grading_records)
-- Stores PySpark Video Grading Extractions & Post-Publishing Performance Telemetry
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `media_pipeline.video_grades` (
    -- Identification & Media Storage
    video_id STRING NOT NULL,
    gcs_uri STRING NOT NULL,
    raw_file_name STRING,
    file_size_bytes INT64,
    duration_seconds FLOAT64 NOT NULL,
    aspect_ratio STRING NOT NULL,
    resolution STRING,
    fps FLOAT64,
    status STRING NOT NULL, -- 'GRADED', 'FAILED_DLQ', 'PENDING'
    error_message STRING,

    -- 5 Core Viral Parameter Scores (0.0 to 100.0)
    hrv_score FLOAT64 NOT NULL,       -- Hook Retention Velocity (0-3s kinetic pull)
    dpaw_score FLOAT64 NOT NULL,      -- Drop Pacing & Anticipation Window
    adr_sfd_score FLOAT64 NOT NULL,   -- Audio Dynamic Range & Spectral Flux Delta
    cke_mve_score FLOAT64 NOT NULL,   -- Crowd Kinetic Energy & Motion Vector Entropy
    ltss_score FLOAT64 NOT NULL,      -- Lighting Transition & Strobe Synchronicity

    -- Composite Scoring & Categorical Verdict
    evpi_composite FLOAT64 NOT NULL,  -- Expected Viral Potential Index (0.0 to 100.0)
    trending_verdict STRING NOT NULL, -- 'VIRAL_TIER_1', 'HIGH_POTENTIAL', 'MODERATE', 'LOW_REACH'

    -- Temporal Granular Features (Microsecond/Millisecond Precision)
    hook_onset_latency_seconds FLOAT64,
    drop_timestamp_seconds FLOAT64,
    buildup_duration_seconds FLOAT64,
    predrop_silence_ms FLOAT64,
    strobe_hz FLOAT64,
    recommended_trim_start_sec FLOAT64,
    recommended_trim_end_sec FLOAT64,
    peak_drop_timestamp_sec FLOAT64,

    -- Categorization & Metadata
    subgenre STRING,
    suggested_hashtags ARRAY<STRING>,
    grading_rationale STRING,
    graded_at TIMESTAMP NOT NULL,
    model_version STRING,

    -- Downstream Post-Publishing Telemetry (Sinked from YouTube Shorts / TikTok / Instagram)
    actual_vvsa_rate FLOAT64,             -- Viewed vs. Swiped Away percentage (e.g. 0.84 = 84%)
    actual_avg_percentage_viewed FLOAT64, -- Average Percentage Viewed (e.g. 1.25 = 125% loop)
    actual_share_count INT64,             -- Total shares / forwards
    actual_completion_rate FLOAT64,       -- Fraction of viewers completing 100% of video
    actual_viral_status INT64             -- Binary label: 1 if viral (>=100k views in 48h), else 0
)
PARTITION BY DATE(graded_at)
CLUSTER BY subgenre, status, trending_verdict;

-- Schema compatibility view / alias for video_grading_records
CREATE TABLE IF NOT EXISTS `media_pipeline.video_grading_records` (
    video_id STRING NOT NULL,
    gcs_uri STRING NOT NULL,
    raw_file_name STRING,
    file_size_bytes INT64,
    duration_seconds FLOAT64,
    resolution STRING,
    fps FLOAT64,
    status STRING NOT NULL,
    error_message STRING,
    hook_strength FLOAT64,
    audio_drop_sync FLOAT64,
    crowd_energy FLOAT64,
    visual_dynamism FLOAT64,
    retention_pacing FLOAT64,
    composite_trending_score FLOAT64,
    recommended_trim_start_sec FLOAT64,
    recommended_trim_end_sec FLOAT64,
    peak_drop_timestamp_sec FLOAT64,
    subgenre STRING,
    suggested_hashtags ARRAY<STRING>,
    grading_rationale STRING,
    graded_at TIMESTAMP NOT NULL,
    model_version STRING
)
PARTITION BY DATE(graded_at)
CLUSTER BY subgenre, status;


-- ----------------------------------------------------------------------------
-- 2. Post-Performance Telemetry Table
-- Stores platform-specific engagement and retention signals ingested post-publish
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `media_pipeline.post_performance_metrics` (
    metric_id STRING NOT NULL,
    video_id STRING NOT NULL,
    platform STRING NOT NULL, -- 'YOUTUBE_SHORTS', 'TIKTOK', 'INSTAGRAM_REELS'
    published_at TIMESTAMP NOT NULL,
    metrics_as_of TIMESTAMP NOT NULL,
    actual_views INT64,
    actual_likes INT64,
    actual_shares INT64,
    actual_comments INT64,
    actual_watch_time_seconds FLOAT64,
    actual_average_retention_rate FLOAT64,
    actual_avg_percentage_viewed FLOAT64,
    actual_vvsa_rate FLOAT64,
    viral_target_score FLOAT64 NOT NULL, -- Continuous normalized retention target (0-100)
    is_viral INT64                       -- 1 = Viral Hit, 0 = Standard
)
PARTITION BY DATE(published_at)
CLUSTER BY platform, video_id;


-- ----------------------------------------------------------------------------
-- 3. Dynamic Model Parameter Weights Registry
-- Stores versioned empirical parameter weights learned via BQML loop
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `media_pipeline.model_parameter_weights` (
    version_id STRING NOT NULL,
    trained_at TIMESTAMP NOT NULL,
    weight_hrv FLOAT64 NOT NULL,
    weight_dpaw FLOAT64 NOT NULL,
    weight_adr_sfd FLOAT64 NOT NULL,
    weight_cke_mve FLOAT64 NOT NULL,
    weight_ltss FLOAT64 NOT NULL,
    model_r2_score FLOAT64 NOT NULL,
    rmse FLOAT64,
    training_sample_count INT64,
    is_active BOOLEAN NOT NULL
)
PARTITION BY DATE(trained_at)
CLUSTER BY is_active, version_id;
