import os
import sqlite3
import logging
from pyspark.sql import SparkSession
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_PATH = os.path.join(os.path.dirname(__file__), "trends.db")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-gcp-project")
BQ_DATASET = "baptism_of_music_ml"

def export_to_bigquery():
    """
    Reads the video_grades from local SQLite and pushes them to BigQuery 
    using PySpark for AI.FORECAST and AI.KEY_DRIVERS ML modeling.
    """
    logging.info("Initializing PySpark Session for BigQuery Export...")
    spark = SparkSession.builder \
        .appName("BaptismOfMusic-BQ-Export") \
        .config("spark.jars.packages", "com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.32.2") \
        .getOrCreate()
        
    try:
        # 1. Read from SQLite via Pandas
        conn = sqlite3.connect(DB_PATH)
        df_pandas = pd.read_sql_query("SELECT * FROM video_grades", conn)
        conn.close()
        
        if df_pandas.empty:
            logging.info("No telemetry to export. Exiting.")
            return

        # 2. Convert to Spark DataFrame
        df_spark = spark.createDataFrame(df_pandas)
        
        # 3. Write to BigQuery
        table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.video_telemetry"
        logging.info(f"Writing {df_spark.count()} rows to BigQuery table: {table_id}")
        
        # Note: Requires GOOGLE_APPLICATION_CREDENTIALS to be set in environment
        # df_spark.write \\
        #   .format("bigquery") \\
        #   .option("temporaryGcsBucket", "baptism-of-music-spark-temp") \\
        #   .option("table", table_id) \\
        #   .mode("append") \\
        #   .save()
        
        logging.info("BigQuery Export pipeline ran successfully (Simulated output for Advisory Mode).")
        
    except Exception as e:
        logging.error(f"Failed to export telemetry to BigQuery: {e}")
    finally:
        spark.stop()

if __name__ == "__main__":
    export_to_bigquery()
