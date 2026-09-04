import { IngestDaemonState, TelemetryState, VectorSearchResponse } from '../types/telemetry';

const BASE_URL = '';

/**
 * Robust fetch wrapper with timeout and error wrapping
 */
async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), 6000);

  try {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
    clearTimeout(id);

    if (!res.ok) {
      throw new Error(`API Error [${res.status}]: ${res.statusText}`);
    }
    return await res.json();
  } catch (err: any) {
    clearTimeout(id);
    if (err.name === 'AbortError') {
      throw new Error(`Request timed out for endpoint: ${endpoint}`);
    }
    throw err;
  }
}

export async function checkServerHealth(): Promise<{ status: string }> {
  try {
    return await fetchJson<{ status: string }>('/status');
  } catch {
    // Fallback attempt to root
    return await fetchJson<{ status: string }>('/');
  }
}

export async function fetchTelemetrySnapshot(): Promise<{
  status: string;
  timestamp: string;
  telemetry: TelemetryState;
  connected_clients: number;
}> {
  return await fetchJson('/api/telemetry');
}

export async function searchVectorHub(query: string, limit = 6): Promise<VectorSearchResponse> {
  const params = new URLSearchParams();
  if (query) params.append('q', query);
  params.append('limit', limit.toString());
  return await fetchJson(`/api/vector-hub/search?${params.toString()}`);
}

export async function fetchIngestStatus(): Promise<{
  daemon: IngestDaemonState;
  system_load: any;
  status: string;
}> {
  return await fetchJson('/api/ingest/status');
}

export async function publishEvent(event: string, data: Record<string, any> = {}): Promise<{ status: string }> {
  return await fetchJson('/api/events', {
    method: 'POST',
    body: JSON.stringify({ event, data }),
  });
}
