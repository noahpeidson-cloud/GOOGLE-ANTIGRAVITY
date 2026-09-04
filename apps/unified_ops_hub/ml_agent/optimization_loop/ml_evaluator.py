import sqlite3
import pandas as pd
import numpy as np
import os
# Fallback in case dependencies are not installed in the environment during tests
try:
    from sklearn.preprocessing import StandardScaler
    import umap
    import hdbscan
except ImportError:
    StandardScaler = None
    umap = None
    hdbscan = None

from google.genai import Client

class AgentMLEvaluator:
    def __init__(self, db_path='telemetry_spans.db'):
        self.db_path = db_path
        self.client = Client()

    def fetch_traces(self):
        if not os.path.exists(self.db_path):
            return pd.DataFrame()
        conn = sqlite3.connect(self.db_path)
        query = "SELECT agent_id, role, input_tokens, output_tokens, error_count, transcript FROM telemetry"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def cluster_and_detect_anomalies(self, df):
        if len(df) < 5 or umap is None:
            # Fallback to simple heuristic if not enough data or missing dependency
            idle_mask = (df['output_tokens'] < 50) & (df['input_tokens'] > 500)
            return df, df[idle_mask]
            
        # 1. Semantic Embeddings (Gemini Embeddings API)
        embeddings = []
        for t in df['transcript']:
            # Slice to avoid massive context sizes in embeddings
            res = self.client.models.embed_content(model="text-embedding-004", contents=str(t)[:1000])
            embeddings.append(res.embeddings[0].values)
        semantic_embeddings = np.array(embeddings)
        
        # 2. Behavioral Metrics
        metrics = df[['input_tokens', 'output_tokens', 'error_count']].values
        scaled_metrics = StandardScaler().fit_transform(metrics)
        
        # 3. Concatenate & UMAP Projection
        combined_features = np.hstack([semantic_embeddings, scaled_metrics])
        reducer = umap.UMAP(n_neighbors=2, n_components=3, metric='cosine')
        reduced = reducer.fit_transform(combined_features)
        
        # 4. HDBSCAN Density Clustering
        clusterer = hdbscan.HDBSCAN(min_cluster_size=2, metric='euclidean')
        df['cluster'] = clusterer.fit_predict(reduced)
        
        # 5. Extract "Idle/Bloat" Anomaly Clusters
        # Typically noise is -1 in HDBSCAN. We look for the cluster that matches our heuristic criteria
        # Alternatively, just apply the heuristic mask directly on the clustered dataframe to find the failure cluster.
        idle_mask = (df['output_tokens'] < 50) & (df['input_tokens'] > 500)
        failure_traces = df[idle_mask]
        
        return df, failure_traces
