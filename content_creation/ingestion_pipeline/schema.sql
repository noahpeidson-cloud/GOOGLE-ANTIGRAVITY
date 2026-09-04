CREATE TABLE video_metadata (
    video_id STRING NOT NULL,
    filename STRING NOT NULL,
    resolution STRING,
    ingestion_timestamp TIMESTAMP NOT NULL,
    status STRING
);
