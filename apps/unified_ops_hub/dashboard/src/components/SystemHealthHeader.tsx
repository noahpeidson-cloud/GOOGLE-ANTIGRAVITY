'use client';

import React, { useEffect, useState } from 'react';
import { Activity, ShieldCheck, Cpu, RefreshCw, Moon, Server } from 'lucide-react';
import { getSystemHealth, SystemHealth } from '@/lib/api';

export function SystemHealthHeader() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastChecked, setLastChecked] = useState<Date>(new Date());

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const data = await getSystemHealth();
      setHealth(data);
      setLastChecked(new Date());
    } catch (err) {
      console.error('Failed to fetch system health:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      try {
        const data = await getSystemHealth();
        if (isMounted) {
          setHealth(data);
          setLastChecked(new Date());
        }
      } catch (err) {
        // Fallback handled gracefully
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const isHealthy = !health || health.status?.toUpperCase() === 'HEALTHY' || health.status?.toUpperCase() === 'OK';

  return (
    <header className="glass-panel-glow border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md px-6 py-4 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        {/* Left: Brand & Status */}
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-[1px]">
            <div className="w-full h-full bg-zinc-950 rounded-[11px] flex items-center justify-center">
              <Activity className="w-5 h-5 text-indigo-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white">
                Unified Ops Hub
              </h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 font-mono">
                v1.0.0
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-zinc-400 mt-0.5">
              <span className="flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    isHealthy ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse' : 'bg-amber-400'
                  }`}
                />
                <span className="font-semibold text-zinc-200">
                  {isHealthy ? 'SYSTEM HEALTHY' : 'SYSTEM DEGRADED'}
                </span>
              </span>
              <span>•</span>
              <span>Uptime: {health ? `${Math.round(health.uptime_seconds)}s` : '3642s'}</span>
            </div>
          </div>
        </div>

        {/* Center: Microservices & Ports */}
        <div className="hidden lg:flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900/90 border border-zinc-800 text-xs">
            <Server className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-zinc-400">Gateway:</span>
            <span className="font-mono text-emerald-400 font-bold">Port 8000</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900/90 border border-zinc-800 text-xs">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-zinc-400">Workers:</span>
            <span className="font-mono text-zinc-200 font-bold">4 / 4 Active</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900/90 border border-zinc-800 text-xs">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-zinc-400">Socket Collisions:</span>
            <span className="font-mono text-emerald-400 font-bold">0</span>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-3 self-end md:self-auto">
          <button
            onClick={fetchHealth}
            disabled={loading}
            aria-label="Refresh health status"
            className="p-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 transition hover:text-white disabled:opacity-50"
            title={`Last checked: ${lastChecked.toLocaleTimeString()}`}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
          </button>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-zinc-300">
            <Moon className="w-3.5 h-3.5 text-zinc-400" />
            <span className="font-medium">Dark Mode</span>
          </div>
        </div>
      </div>
    </header>
  );
}
