export interface IngestDaemonState {
  status: 'idle' | 'processing' | 'indexing' | 'syncing' | 'offline';
  last_sync: string;
  queued_items: number;
  processed_count: number;
  health: string;
}

export interface VectorHubStats {
  status: string;
  total_vectors: number;
  dimension: number;
  avg_query_latency_ms: number;
  index_integrity: number;
}

export interface SystemStats {
  cpu_usage_pct: number;
  memory_usage_mb: number;
  uptime_seconds: number;
}

export interface TelemetryState {
  ingest_daemon: IngestDaemonState;
  vector_hub: VectorHubStats;
  system: SystemStats;
}

export interface VectorDocMatch {
  id: string;
  title: string;
  snippet: string;
  score: number;
  collection: string;
  indexed_at: string;
}

export interface VectorSearchResponse {
  query: string;
  total_matches: number;
  results: VectorDocMatch[];
}

export interface WebSocketEventMessage {
  event: string;
  timestamp: string;
  data?: any;
  connected_clients?: number;
}
