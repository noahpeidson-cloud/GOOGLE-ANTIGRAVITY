import pandas as pd
from google.cloud import bigquery
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")

PROJECT_ID = "local-catfish-470915-r8"
DATASET_ID = "antigravity_telemetry"

def main():
    client = bigquery.Client(project=PROJECT_ID)

    # 1. K-Means Clustering on anomalies
    cluster_query = f"""
    CREATE OR REPLACE MODEL `{PROJECT_ID}.{DATASET_ID}.anomaly_clustering_model`
    OPTIONS(model_type='kmeans', num_clusters=3, standardize_features=TRUE) AS
    SELECT
      detector_type,
      severity,
      confidence
    FROM `{PROJECT_ID}.{DATASET_ID}.anomalies`
    """
    logging.info("Training K-Means Clustering Model...")
    try:
        client.query(cluster_query).result()
        logging.info("K-Means Model Trained.")
    except Exception as e:
        logging.error(f"Error: {e}")

    # Evaluate the clustering model
    eval_query = f"""
    SELECT * FROM ML.EVALUATE(MODEL `{PROJECT_ID}.{DATASET_ID}.anomaly_clustering_model`)
    """
    try:
        eval_df = client.query(eval_query).to_dataframe()
        logging.info("Clustering Evaluation:")
        print(eval_df.to_string())
    except Exception as e:
        logging.error(f"Error: {e}")

    # Inspect Clusters
    centroid_query = f"""
    SELECT * FROM ML.CENTROIDS(MODEL `{PROJECT_ID}.{DATASET_ID}.anomaly_clustering_model`)
    """
    try:
        centroid_df = client.query(centroid_query).to_dataframe()
        logging.info("Clustering Centroids:")
        print(centroid_df.to_string())
    except Exception as e:
        logging.error(f"Error: {e}")
        
    # 2. Time-Series Anomaly Detection using ARIMA_PLUS
    # First, let's create a time series of anomalies count per minute or hour
    # We will use scan_sessions duration_ms and anomalies count
    ts_query = f"""
    CREATE OR REPLACE MODEL `{PROJECT_ID}.{DATASET_ID}.anomaly_timeseries_model`
    OPTIONS(model_type='ARIMA_PLUS',
            time_series_timestamp_col='timestamp_bucket',
            time_series_data_col='anomaly_count',
            auto_arima=TRUE) AS
    SELECT
      TIMESTAMP_TRUNC(TIMESTAMP_MILLIS(timestamp), HOUR) as timestamp_bucket,
      COUNT(id) as anomaly_count
    FROM `{PROJECT_ID}.{DATASET_ID}.anomalies`
    GROUP BY timestamp_bucket
    """
    logging.info("Training ARIMA_PLUS Anomaly Detection Model...")
    try:
        client.query(ts_query).result()
        logging.info("ARIMA_PLUS Model Trained.")
    except Exception as e:
        logging.error(f"Error: {e}")

    # Detect anomalies
    detect_query = f"""
    SELECT * FROM ML.DETECT_ANOMALIES(
        MODEL `{PROJECT_ID}.{DATASET_ID}.anomaly_timeseries_model`,
        STRUCT(0.95 AS anomaly_prob_threshold)
    )
    """
    try:
        detect_df = client.query(detect_query).to_dataframe()
        logging.info("Time-Series Anomalies Detected:")
        print(detect_df.to_string())
    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    main()
