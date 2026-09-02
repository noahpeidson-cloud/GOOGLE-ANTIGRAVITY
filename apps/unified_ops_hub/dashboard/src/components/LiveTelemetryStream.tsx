'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Terminal, Trash2, Radio } from 'lucide-react';

interface LiveTelemetryStreamProps {
  streamUrl?: string;
}

export function LiveTelemetryStream({ streamUrl = '/api/v1/events/stream' }: LiveTelemetryStreamProps) {
  const [logs, setLogs] = useState<string[]>([
    '[19:14:00] [GATEWAY] Dynamic port manager initialized. Bound 8000 (PRIMARY).',
    '[19:14:02] [MEDIA_DAEMON] Ingestion Watcher active on 192.168.1.150:5555.',
    '[19:14:05] [SPORTS_CARDS] Card Ladder ETL loop online. 1,420 records synchronized.',
    '[19:14:09] [ML_AGENT] Scraped 25 TikTok sounds. K-Means distribution: C0:78%, C1:15%, C2:7%.',
    '[19:14:12] [DLQ_GUARD] Incident quarantine active. 0 active collisions.',
  ]);
  const [isActive, setIsActive] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Listen to contentvisibilityautostatechange per modern-web-guidance
    const handleStateChange = (event: any) => {
      if (event.skipped) {
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
        setIsActive(false);
      } else {
        connectStream();
        setIsActive(true);
      }
    };

    const connectStream = () => {
      if (typeof window === 'undefined' || !(window as any).EventSource) return;
      if (eventSourceRef.current) return;
      try {
        const es = new EventSource(streamUrl);
        es.onmessage = (event) => {
          setLogs((prev) => [...prev.slice(-99), `[${new Date().toLocaleTimeString()}] ${event.data}`]);
        };
        es.onerror = () => {
          es.close();
          eventSourceRef.current = null;
        };
        eventSourceRef.current = es;
      } catch {
        // Fallback for mock environment
      }
    };

    connectStream();

    el.addEventListener('contentvisibilityautostatechange', handleStateChange);
    return () => {
      el.removeEventListener('contentvisibilityautostatechange', handleStateChange);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [streamUrl]);

  const handleClear = () => {
    setLogs([]);
  };

  return (
    <div
      ref={containerRef}
      className="glass-panel rounded-2xl p-4 border border-zinc-800/80 bg-zinc-950/80 content-visibility-auto"
    >
      <div className="flex items-center justify-between pb-3 border-b border-zinc-800/80">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-zinc-400" />
          <h3 className="text-xs font-bold text-zinc-200 uppercase tracking-wider">
            Real-Time Pipeline Event Stream (SSE Terminal)
          </h3>
          <span className="flex items-center gap-1.5 ml-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isActive ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-600'
              }`}
            />
            <span className="text-[10px] font-mono text-zinc-400">{isActive ? 'LIVE STREAM' : 'PAUSED'}</span>
          </span>
        </div>
        <button
          onClick={handleClear}
          className="text-xs text-zinc-500 hover:text-zinc-300 transition flex items-center gap-1"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Clear
        </button>
      </div>

      <div className="mt-3 h-36 overflow-y-auto font-mono text-[11px] text-zinc-400 space-y-1 select-text">
        {logs.length === 0 ? (
          <div className="text-zinc-600 italic">No event logs in buffer.</div>
        ) : (
          logs.map((log, idx) => (
            <div key={idx} className="leading-tight hover:text-zinc-200 transition">
              {log}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
