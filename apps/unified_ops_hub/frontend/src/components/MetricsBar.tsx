import React from 'react';
import { TelemetryState } from '../types/telemetry';
import { Cpu, HardDrive, Database, Clock, Layers, Shield } from 'lucide-react';

interface MetricsBarProps {
  telemetry: TelemetryState;
}

export const MetricsBar: React.FC<MetricsBarProps> = ({ telemetry }) => {
  const { system, vector_hub, ingest_daemon } = telemetry;

  const getCpuColor = (pct: number) => {
    if (pct < 40) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
    if (pct < 75) return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
    return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
  };

  const getDaemonBadge = (status: string) => {
    switch (status) {
      case 'processing':
      case 'indexing':
      case 'syncing':
        return 'text-sky-400 bg-sky-500/10 border-sky-500/30';
      case 'idle':
        return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
      default:
        return 'text-slate-400 bg-slate-500/10 border-slate-500/30';
    }
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {/* Metric 1: CPU Usage */}
      <div className="bg-ops-surface border border-ops-border rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
        <div className="flex items-center justify-between text-ops-muted text-xs mb-1.5">
          <span className="font-medium flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-ops-accent" /> CPU Load
          </span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${getCpuColor(system.cpu_usage_pct)}`}>
            {system.cpu_usage_pct}%
          </span>
        </div>
        <div className="text-xl font-bold text-slate-100 font-mono">
          {system.cpu_usage_pct}
          <span className="text-xs text-ops-muted ml-0.5 font-normal">%</span>
        </div>
        <div className="w-full bg-slate-800/80 rounded-full h-1.5 mt-2 overflow-hidden">
          <div
            className="bg-ops-accent h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(system.cpu_usage_pct, 100)}%` }}
          />
        </div>
      </div>

      {/* Metric 2: Memory Allocated */}
      <div className="bg-ops-surface border border-ops-border rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
        <div className="flex items-center justify-between text-ops-muted text-xs mb-1.5">
          <span className="font-medium flex items-center gap-1.5">
            <HardDrive className="w-3.5 h-3.5 text-sky-400" /> Host RAM
          </span>
        </div>
        <div className="text-xl font-bold text-slate-100 font-mono">
          {system.memory_usage_mb}
          <span className="text-xs text-ops-muted ml-1 font-normal">MB</span>
        </div>
        <div className="text-[11px] text-ops-muted mt-1 flex items-center justify-between">
          <span>Active Heap</span>
          <span className="text-emerald-400 font-mono">Nominal</span>
        </div>
      </div>

      {/* Metric 3: Daemon State */}
      <div className="bg-ops-surface border border-ops-border rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
        <div className="flex items-center justify-between text-ops-muted text-xs mb-1.5">
          <span className="font-medium flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-indigo-400" /> Daemon State
          </span>
        </div>
        <div>
          <span
            className={`inline-block px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider border ${getDaemonBadge(
              ingest_daemon.status
            )}`}
          >
            {ingest_daemon.status}
          </span>
        </div>
        <div className="text-[11px] text-ops-muted mt-1 truncate">
          Queue: <span className="font-mono text-slate-200">{ingest_daemon.queued_items}</span> items
        </div>
      </div>

      {/* Metric 4: Vector Hub Indexed Total */}
      <div className="bg-ops-surface border border-ops-border rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
        <div className="flex items-center justify-between text-ops-muted text-xs mb-1.5">
          <span className="font-medium flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-violet-400" /> Vectors
          </span>
        </div>
        <div className="text-xl font-bold text-slate-100 font-mono">
          {vector_hub.total_vectors.toLocaleString()}
        </div>
        <div className="text-[11px] text-ops-muted mt-1">
          Dim: <span className="font-mono text-slate-200">{vector_hub.dimension}d</span>
        </div>
      </div>

      {/* Metric 5: Vector Query Latency */}
      <div className="bg-ops-surface border border-ops-border rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
        <div className="flex items-center justify-between text-ops-muted text-xs mb-1.5">
          <span className="font-medium flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-emerald-400" /> Query Latency
          </span>
        </div>
        <div className="text-xl font-bold text-slate-100 font-mono">
          {vector_hub.avg_query_latency_ms}
          <span className="text-xs text-ops-muted ml-1 font-normal">ms</span>
        </div>
        <div className="text-[11px] text-emerald-400 mt-1 font-medium">Sub-20ms SLA</div>
      </div>

      {/* Metric 6: Index Integrity */}
      <div className="bg-ops-surface border border-ops-border rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
        <div className="flex items-center justify-between text-ops-muted text-xs mb-1.5">
          <span className="font-medium flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-teal-400" /> Integrity
          </span>
        </div>
        <div className="text-xl font-bold text-slate-100 font-mono">
          {(vector_hub.index_integrity * 100).toFixed(0)}
          <span className="text-xs text-ops-muted ml-0.5 font-normal">%</span>
        </div>
        <div className="text-[11px] text-ops-muted mt-1">HNSW Graph OK</div>
      </div>
    </div>
  );
};
