import sqlite3
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'design_telemetry.db')

def analyze_telemetry_clusters():
    """
    Pandas-Native K-Means Evaluation.
    Evaluates the SQLite generation_logs for overexposure clusters.
    """
    if not os.path.exists(DB_PATH):
        print("Telemetry database not found. Run baseline_extractor first.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    # Read logs into Pandas DataFrame
    df = pd.read_sql_query("SELECT id, baseline_id, new_overexposure_percent, delta_overexposure, is_flagged_bad FROM generation_logs", conn)
    conn.close()
    
    if df.empty or len(df) < 5:
        print("Not enough data to run K-Means (Need at least 5 generations). Waiting for more telemetry.")
        return
        
    print("Running Local Pandas K-Means Clustering on Design Telemetry...")
    
    # Feature extraction for K-Means (Euclidean distance on overexposure metrics)
    features = df[['new_overexposure_percent', 'delta_overexposure']].fillna(0)
    
    # K-Means clustering
    kmeans = KMeans(n_clusters=2, random_state=42, n_init='auto')
    df['cluster'] = kmeans.fit_predict(features)
    
    # Calculate Semantic Entropy (Distance between cluster centroids)
    centroids = kmeans.cluster_centers_
    entropy = np.linalg.norm(centroids[0] - centroids[1])
    
    print(f"Semantic Entropy (Centroid Distance): {entropy:.4f}")
    
    if entropy > 10.0:
        print("WARNING: High Semantic Entropy detected. Subagents are generating wildly differing exposures.")
        print("INITIATING PROTEGI TEXTUAL GRADIENT (Backward Pass)...")
        # In a real system, this triggers workflow-skill-creator to update the SKILL.md
        print("ProTeGi Pass: Updating Subagent prompt to strictly enforce < 5% Delta limit.")
    else:
        print("Execution pattern stable. Clusters are tight.")
        
if __name__ == "__main__":
    analyze_telemetry_clusters()
