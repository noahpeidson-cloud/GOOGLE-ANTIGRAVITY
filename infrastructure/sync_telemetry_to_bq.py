import sqlite3
import pandas as pd
from google.cloud import bigquery
from google.api_core.exceptions import NotFound
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PROJECT_ID = "local-catfish-470915-r8"
DATASET_ID = "antigravity_telemetry"
DB_PATH = "health_telemetry.db"

TABLES = [
    "scan_sessions",
    "anomalies",
    "historical_lifelines",
    "textual_gradients"
]

def ensure_dataset(client: bigquery.Client, dataset_id: str):
    dataset_ref = client.dataset(dataset_id)
    try:
        client.get_dataset(dataset_ref)
        logging.info(f"Dataset {dataset_id} already exists.")
    except NotFound:
        logging.info(f"Dataset {dataset_id} not found. Creating...")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset, timeout=30)
        logging.info(f"Created dataset {dataset_id}.")

def main():
    logging.info(f"Starting telemetry sync to BigQuery dataset: {DATASET_ID}")
    try:
        client = bigquery.Client(project=PROJECT_ID)
    except Exception as e:
        logging.error(f"Failed to initialize BigQuery client: {e}")
        sys.exit(1)

    ensure_dataset(client, DATASET_ID)

    try:
        conn = sqlite3.connect(DB_PATH)
    except Exception as e:
        logging.error(f"Failed to connect to SQLite DB {DB_PATH}: {e}")
        sys.exit(1)

    for table in TABLES:
        try:
            logging.info(f"Extracting table: {table}")
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            if df.empty:
                logging.info(f"Table {table} is empty. Skipping.")
                continue

            destination_table = f"{PROJECT_ID}.{DATASET_ID}.{table}"
            logging.info(f"Pushing {len(df)} rows to {destination_table}...")
            
            import pandas_gbq
            pandas_gbq.to_gbq(
                df,
                destination_table=destination_table,
                project_id=PROJECT_ID,
                if_exists="replace", # Overwrite for the initial sync
            )
            logging.info(f"Successfully synced table: {table}")
        except Exception as e:
            logging.error(f"Error processing table {table}: {e}")

    conn.close()
    logging.info("Telemetry sync complete.")

if __name__ == "__main__":
    main()
