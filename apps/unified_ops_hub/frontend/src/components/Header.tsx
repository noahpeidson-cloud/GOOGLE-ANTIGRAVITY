import React, { useState, useEffect } from 'react';
import { ConnectionStatus } from '../hooks/useTelemetryWebSocket';
import { Activity, Radio, RefreshCw, Server, ShieldCheck, Zap } from 'lucide-react';
import { checkServerHealth } from '../services/api';

interface HeaderProps {
  connectionStatus: ConnectionStatus;
  connectedClients: number;
}

export const Header: React.FC<HeaderProps> = ({ connectionStatus, connectedClients }) => {
  const [serverOnline, setServerOnline] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const checkStatus = async () => {
    setIsRefreshing(true);
    try {
      const res = await checkServerHealth();
      setServerOnline(res.status === 'online');
    } catch {
      setServerOnline(false);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const getStatusBadge = () => {
    switch (connectionStatus) {
      case 'connected':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-950/70 border border-emerald-600/40 text-emerald-400">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            WS Connected ({connectedClients} peer{connectedClients === 1 ? '' : 's'})
          </span>
        );
      case 'connecting':
      case 'reconnecting':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-950/70 border border-amber-600/40 text-amber-400">
            <Radio className="w-3.5 h-3.5 animate-pulse" />
            {connectionStatus === 'connecting' ? 'Connecting Bus...' : 'Reconnecting...'}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-rose-950/70 border border-rose-600/40 text-rose-400">
            <span className="h-2 w-2 rounded-full bg-rose-500"></span>
            Bus Offline
          </span>
        );
    }
  };

  return (
    <header className="border-b border-ops-border bg-ops-surface/80 backdrop-blur-md sticky top-0 z-40 px-4 sm:px-6 py-3.5">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Brand & Title */}
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-sky-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-sky-500/20 text-white font-bold">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-white">Unified Ops Hub</h1>
              <span className="px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider rounded bg-sky-950 text-sky-400 border border-sky-800/60">
                v1.0-headless
              </span>
            </div>
            <p className="text-xs text-ops-muted">System Telemetry & Cognitive Runtime Console</p>
          </div>
        </div>

        {/* Right Status Indicators & Actions */}
        <div className="flex items-center flex-wrap gap-2.5 sm:gap-3">
          {/* FastAPI Server Health */}
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-ops-card border border-ops-border text-slate-300">
            <Server className="w-3.5 h-3.5 text-slate-400" />
            <span>FastAPI:</span>
            {serverOnline ? (
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" /> online
              </span>
            ) : (
              <span className="text-rose-400 font-semibold">offline</span>
            )}
          </div>

          {/* WebSocket Status */}
          {getStatusBadge()}

          {/* Refresh Action */}
          <button
            onClick={checkStatus}
            disabled={isRefreshing}
            aria-label="Refresh Server Status"
            className="min-h-[40px] min-w-[40px] p-2 rounded-lg bg-ops-card hover:bg-ops-cardHover border border-ops-border text-slate-300 hover:text-white transition-colors duration-150 flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-ops-accent"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-ops-accent' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
};
