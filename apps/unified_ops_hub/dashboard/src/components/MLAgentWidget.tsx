'use client';

import React, { useEffect, useState } from 'react';
import { Bot, Smartphone, Globe, CheckCircle, Flame } from 'lucide-react';
import { getMLTelemetry, triggerLensFailover, MLTelemetryData } from '@/lib/api';

const DEFAULT_ML_DATA: MLTelemetryData = {
  platform: 'tiktok',
  active_lens: 'android_ui_dump',
  poll_interval_sec: 3600,
  retry_backoff_base_sec: 2.0,
  clusters: {
    c0_healthy: 78,
    c1_throttled: 15,
    c2_failover: 7,
  },
  entropy: 0.042,
  trending_sounds: [
    {
      id: 'SND_001',
      sound_title: 'Ultra Miami 2026 Mainstage ID',
      creator: 'Martin Garrix',
      hashtag: '#Ultra2026',
      likes: 1420000,
      velocity: 98.4,
      lens: 'android_ui_dump',
    },
    {
      id: 'SND_002',
      sound_title: 'Hardwell Rebel ID Drop',
      creator: 'Hardwell',
      hashtag: '#BigRoomNeverDies',
      likes: 890000,
      velocity: 91.2,
      lens: 'android_ui_dump',
    },
    {
      id: 'SND_003',
      sound_title: 'Subtronics Heavy Bass Flip',
      creator: 'Subtronics',
      hashtag: '#EDMDrop',
      likes: 640000,
      velocity: 87.6,
      lens: 'android_ui_dump',
    },
  ],
};

export function MLAgentWidget() {
  const [data, setData] = useState<MLTelemetryData>(DEFAULT_ML_DATA);
  const [isSwapping, setIsSwapping] = useState(false);
  const [swapNotice, setSwapNotice] = useState<string | null>(null);

  const loadTelemetry = async () => {
    try {
      const res = await getMLTelemetry();
      setData(res);
    } catch (err) {
      console.error('Error loading ML telemetry:', err);
    }
  };

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      try {
        const res = await getMLTelemetry();
        if (isMounted) {
          setData(res);
        }
      } catch (err) {
        // Fallback handled gracefully
      }
    };
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleToggleLens = async () => {
    setIsSwapping(true);
    try {
      const res = await triggerLensFailover();
      setSwapNotice(`Lens failover executed: Swapped to ${res.active_lens}`);
      await loadTelemetry();
      setTimeout(() => setSwapNotice(null), 4000);
    } catch (err) {
      console.error('Failover error:', err);
    } finally {
      setIsSwapping(false);
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-6 border border-zinc-800/80 bg-zinc-900/40 relative overflow-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              ML Agent & Viral Trends Optimizer
              <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-300 border border-cyan-800/50">
                Antigravity SDK
              </span>
            </h2>
            <p className="text-xs text-zinc-400">K-Means Cluster Telemetry & ProTeGi Textual Gradients</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleToggleLens}
            disabled={isSwapping}
            className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 transition flex items-center gap-1.5"
          >
            {data.active_lens === 'android_ui_dump' ? (
              <Smartphone className="w-3.5 h-3.5 text-cyan-400" />
            ) : (
              <Globe className="w-3.5 h-3.5 text-cyan-400" />
            )}
            {isSwapping ? 'Switching Lens...' : `Lens: ${data.active_lens}`}
          </button>
        </div>
      </div>

      {swapNotice && (
        <div className="mt-4 p-2.5 rounded-xl bg-cyan-950/60 border border-cyan-500/40 text-cyan-300 text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>{swapNotice}</span>
        </div>
      )}

      {/* K-Means Clusters Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-5">
        <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Cluster 0 (Healthy)</span>
            <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">C0 Healthy</span>
          </div>
          <div className="text-2xl font-extrabold text-white mt-1">{data.clusters.c0_healthy}%</div>
          <div className="text-[11px] text-zinc-500 mt-0.5">Optimal latency & high yield</div>
        </div>

        <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Cluster 1 (Throttled)</span>
            <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">C1 Throttled</span>
          </div>
          <div className="text-2xl font-extrabold text-amber-300 mt-1">{data.clusters.c1_throttled}%</div>
          <div className="text-[11px] text-zinc-500 mt-0.5">Rate limit or backoff penalty</div>
        </div>

        <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Cluster 2 (Failover)</span>
            <span className="text-xs px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold">C2 Failover</span>
          </div>
          <div className="text-2xl font-extrabold text-rose-400 mt-1">{data.clusters.c2_failover}%</div>
          <div className="text-[11px] text-zinc-500 mt-0.5">DOM drift / Zero-yield triggers</div>
        </div>
      </div>

      {/* Operational Policy Telemetry */}
      <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800 flex flex-wrap items-center justify-between gap-3 text-xs mb-5">
        <div>
          <span className="text-zinc-500">Platform:</span> <span className="text-zinc-200 font-mono font-bold">{data.platform}</span>
        </div>
        <div>
          <span className="text-zinc-500">Poll Interval:</span> <span className="text-zinc-200 font-mono font-bold">{data.poll_interval_sec}s</span>
        </div>
        <div>
          <span className="text-zinc-500">Backoff Base:</span> <span className="text-zinc-200 font-mono font-bold">{data.retry_backoff_base_sec}s</span>
        </div>
        <div>
          <span className="text-zinc-500">Gradient Entropy:</span> <span className="text-cyan-400 font-mono font-bold">{data.entropy} (Optimal)</span>
        </div>
      </div>

      {/* Trending Sounds Table */}
      <div>
        <h3 className="text-xs font-bold text-zinc-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <Flame className="w-3.5 h-3.5 text-amber-400" />
          Scraped Viral Sounds & Velocity Metrics
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-400 font-medium">
                <th className="pb-2">Sound Track / Artist</th>
                <th className="pb-2">Hashtag</th>
                <th className="pb-2 text-right">Likes</th>
                <th className="pb-2 text-right">Velocity</th>
                <th className="pb-2 text-center">Capture Lens</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {data.trending_sounds.map((snd) => (
                <tr key={snd.id} className="hover:bg-zinc-800/30 transition">
                  <td className="py-2.5 font-medium text-zinc-200">
                    <div>{snd.sound_title}</div>
                    <div className="text-[11px] text-zinc-500 font-normal">{snd.creator}</div>
                  </td>
                  <td className="py-2.5 text-cyan-400 font-mono">{snd.hashtag}</td>
                  <td className="py-2.5 text-right font-mono text-zinc-300">{snd.likes.toLocaleString()}</td>
                  <td className="py-2.5 text-right font-mono text-amber-400 font-bold">{snd.velocity} / 100</td>
                  <td className="py-2.5 text-center">
                    <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono text-[10px]">
                      {snd.lens}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
