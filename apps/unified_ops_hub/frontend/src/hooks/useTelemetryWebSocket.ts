import { useState, useEffect, useRef, useCallback } from 'react';
import { TelemetryState, WebSocketEventMessage } from '../types/telemetry';

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'offline';

const DEFAULT_TELEMETRY: TelemetryState = {
  ingest_daemon: {
    status: 'idle',
    last_sync: new Date().toISOString(),
    queued_items: 0,
    processed_count: 1420,
    health: 'healthy',
  },
  vector_hub: {
    status: 'indexed',
    total_vectors: 85420,
    dimension: 1536,
    avg_query_latency_ms: 11.4,
    index_integrity: 1.0,
  },
  system: {
    cpu_usage_pct: 14.2,
    memory_usage_mb: 428.6,
    uptime_seconds: 3600,
  },
};

export function useTelemetryWebSocket() {
  const [telemetry, setTelemetry] = useState<TelemetryState>(DEFAULT_TELEMETRY);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [eventLog, setEventLog] = useState<WebSocketEventMessage[]>([]);
  const [connectedClients, setConnectedClients] = useState<number>(1);
  const [lastHeartbeat, setLastHeartbeat] = useState<Date>(new Date());

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const isMountedRef = useRef<boolean>(true);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    // Use relative host or direct fallback
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.port === '5173' ? '127.0.0.1:8000' : window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setConnectionStatus('connected');
        setLastHeartbeat(new Date());

        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: 'ping' }));
          }
        }, 10000);
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const message: WebSocketEventMessage = JSON.parse(event.data);
          setLastHeartbeat(new Date());

          if (message.event === 'telemetry_update' && message.data) {
            setTelemetry(message.data);
            if (message.connected_clients !== undefined) {
              setConnectedClients(message.connected_clients);
            }
          } else if (message.event === 'connected' && message.data) {
            setTelemetry(message.data);
          } else if (message.event === 'ingest_sync_triggered' && message.data) {
            setTelemetry(message.data);
          }

          setEventLog((prev) => [message, ...prev.slice(0, 49)]);
        } catch (e) {
          console.warn('Error parsing incoming WebSocket frame:', e);
        }
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;
        setConnectionStatus('reconnecting');
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          if (isMountedRef.current) connect();
        }, 3000);
      };

      ws.onerror = () => {
        if (!isMountedRef.current) return;
        setConnectionStatus('offline');
        ws.close();
      };
    } catch {
      setConnectionStatus('offline');
      reconnectTimeoutRef.current = window.setTimeout(() => {
        if (isMountedRef.current) connect();
      }, 4000);
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const triggerIngestSync = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'trigger_sync' }));
    } else {
      setTelemetry((prev) => ({
        ...prev,
        ingest_daemon: {
          ...prev.ingest_daemon,
          status: 'indexing',
          queued_items: 4,
          last_sync: new Date().toISOString(),
        },
      }));
    }
  }, []);

  const sendCustomBroadcast = useCallback((event: string, data: any = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'broadcast', event, data }));
    }
  }, []);

  return {
    telemetry,
    connectionStatus,
    eventLog,
    connectedClients,
    lastHeartbeat,
    triggerIngestSync,
    sendCustomBroadcast,
  };
}
