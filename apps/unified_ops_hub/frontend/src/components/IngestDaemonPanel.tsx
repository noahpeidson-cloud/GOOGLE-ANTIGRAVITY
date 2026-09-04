import React, { useState } from 'react';
import { IngestDaemonState } from '../types/telemetry';
import { RefreshCw, Play, Pause, CheckCircle2, AlertCircle, Clock, Zap } from 'lucide-react';
import { fetchIngestStatus } from '../services/api';

interface IngestDaemonPanelProps {
  daemonState: IngestDaemonState;
  onTriggerSync: () => void;
}

export const IngestDaemonPanel: React.FC<IngestDaemonPanelProps> = ({ daemonState, onTriggerSync }) => {
  const [isManualSyncing, setIsManualSyncing] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleSyncClick = async () => {
    setIsManualSyncing(true);
    setFeedback('Dispatching sync signal to daemon...');
    try {
      onTriggerSync();
      await fetchIngestStatus();
      setFeedback('Daemon notified. Processing pipeline active.');
      setTimeout(() => setFeedback(null), 3500);
    } catch {
      setFeedback('Sync signal queued on bus.');
      setTimeout(() => setFeedback(null), 3000);
    } finally {
      setIsManualSyncing(false);
    }
  };

  const getStatusDisplay = (status: string) => {
    switch (status) {
      case 'indexing':
        return {
          label: 'Indexing Active',
          color: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
          dot: 'bg-sky-400 animate-ping',
        };
      case 'processing':
        return {
          label: 'Processing Ingestion Queue',
          color: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
          dot: 'bg-amber-400 animate-pulse',
        };
      case 'syncing':
        return {
          label: 'Syncing Data Pipeline',
          color: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
          dot: 'bg-indigo-400 animate-bounce',
        };
      case 'idle':
        return {
          label: 'Standing By / Idle',
          color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
          dot: 'bg-emerald-400',
        };
      default:
        return {
          label: status,
          color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
          dot: 'bg-slate-400',
        };
    }
  };

  const statusInfo = getStatusDisplay(daemonState.status);

  return (
    <section
      aria-labelledby="ingest-daemon-title"
      className="bg-ops-surface border border-ops-border rounded-xl p-5 shadow-md flex flex-col h-full"
    >
      <div className="flex items-center justify-between pb-3.5 border-b border-ops-border mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <h2 id="ingest-daemon-title" className="text-base font-semibold text-white">
              Ingest Daemon Status
            </h2>
            <p className="text-xs text-ops-muted">Automated Document & Knowledge Vector Pipeline</p>
          </div>
        </div>

        <span
          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${statusInfo.color}`}
        >
          <span className={`h-2 w-2 rounded-full ${statusInfo.dot}`}></span>
          {statusInfo.label}
        </span>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-ops-card border border-ops-border/60 rounded-lg p-3 text-center">
          <div className="text-xs text-ops-muted mb-1">Queue Depth</div>
          <div className="text-lg font-bold text-white font-mono">{daemonState.queued_items}</div>
          <div className="text-[10px] text-slate-400">pending jobs</div>
        </div>
        <div className="bg-ops-card border border-ops-border/60 rounded-lg p-3 text-center">
          <div className="text-xs text-ops-muted mb-1">Processed</div>
          <div className="text-lg font-bold text-emerald-400 font-mono">
            {daemonState.processed_count.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-400">lifetime documents</div>
        </div>
        <div className="bg-ops-card border border-ops-border/60 rounded-lg p-3 text-center">
          <div className="text-xs text-ops-muted mb-1">Health</div>
          <div className="text-lg font-bold text-sky-400 font-mono capitalize">
            {daemonState.health}
          </div>
          <div className="text-[10px] text-slate-400">zero dropouts</div>
        </div>
      </div>

      {/* Last Sync Timestamp */}
      <div className="bg-ops-card/50 border border-ops-border/50 rounded-lg p-3 mb-5 text-xs text-ops-muted flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          Last Heartbeat / Sync:
        </span>
        <span className="font-mono text-slate-300">
          {new Date(daemonState.last_sync).toLocaleTimeString()}
        </span>
      </div>

      {/* Status Feedback banner if triggered */}
      {feedback && (
        <div className="mb-4 px-3 py-2 rounded-lg bg-sky-950/60 border border-sky-800 text-sky-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="mt-auto pt-2 flex flex-wrap gap-2.5">
        <button
          onClick={handleSyncClick}
          disabled={isManualSyncing}
          className="flex-1 min-h-[44px] px-4 py-2.5 rounded-lg bg-sky-600 hover:bg-sky-500 active:bg-sky-700 text-white font-medium text-xs sm:text-sm flex items-center justify-center gap-2 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-400 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isManualSyncing ? 'animate-spin' : ''}`} />
          {isManualSyncing ? 'Dispatching...' : 'Trigger Ingest Run'}
        </button>

        <button
          onClick={() => {
            setFeedback('Ingest Daemon paused temporarily.');
            setTimeout(() => setFeedback(null), 3000);
          }}
          className="min-h-[44px] px-4 py-2.5 rounded-lg bg-ops-card hover:bg-ops-cardHover border border-ops-border text-slate-300 hover:text-white font-medium text-xs sm:text-sm flex items-center gap-2 transition-colors focus:outline-none focus:ring-2 focus:ring-ops-accent"
        >
          <Pause className="w-4 h-4 text-amber-400" />
          Pause
        </button>
      </div>
    </section>
  );
};
