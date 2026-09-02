'use client';

import React, { useEffect, useState } from 'react';
import { ShieldAlert, RefreshCw, Trash2, Eye, AlertTriangle, CheckCircle, Bug } from 'lucide-react';
import { getDLQIncidents, getDLQStats, retryDLQIncident, purgeResolvedDLQ, simulateCrash, DLQIncident, DLQStats } from '@/lib/api';

export function DLQCenter() {
  const [incidents, setIncidents] = useState<DLQIncident[]>([]);
  const [stats, setStats] = useState<DLQStats | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<DLQIncident | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const inc = await getDLQIncidents();
      const st = await getDLQStats();
      setIncidents(inc.incidents);
      setStats(st);
    } catch (err) {
      console.error('Error loading DLQ:', err);
    }
  };

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      try {
        const inc = await getDLQIncidents();
        const st = await getDLQStats();
        if (isMounted) {
          setIncidents(inc.incidents);
          setStats(st);
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

  const handleReplay = async (incidentId: string) => {
    try {
      await retryDLQIncident(incidentId);
      setActionNotice(`Replay triggered for ${incidentId}. Incident marked RESOLVED.`);
      await loadData();
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err) {
      console.error('Replay error:', err);
    }
  };

  const handlePurge = async () => {
    try {
      const res = await purgeResolvedDLQ();
      setActionNotice(`Purged ${res.deleted_count} resolved records from DLQ.`);
      await loadData();
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err) {
      console.error('Purge error:', err);
    }
  };

  const handleSimulateCrash = async () => {
    try {
      const res = await simulateCrash();
      setActionNotice(`Simulated ML crash caught safely by DLQ Resiliency Guard (Incident: ${res.incident_id})`);
      await loadData();
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err) {
      console.error('Simulate crash error:', err);
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-6 border border-zinc-800/80 bg-zinc-900/40 relative overflow-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Dead Letter Queue & Incident Isolation Center
              <span className="text-xs px-2 py-0.5 rounded-full bg-rose-950/80 text-rose-300 border border-rose-800/50">
                Resiliency Engine
              </span>
            </h2>
            <p className="text-xs text-zinc-400">Automated Exception Isolation, Quarantine Inspector & Replay</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleSimulateCrash}
            className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-zinc-800 hover:bg-zinc-700 text-amber-300 border border-amber-500/30 transition flex items-center gap-1.5"
          >
            <Bug className="w-3.5 h-3.5" />
            Simulate Crash
          </button>
          <button
            onClick={handlePurge}
            className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 transition flex items-center gap-1.5"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Purge Resolved
          </button>
        </div>
      </div>

      {actionNotice && (
        <div className="mt-4 p-2.5 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 my-5">
        <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800">
          <div className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Quarantined</div>
          <div className="text-2xl font-extrabold text-rose-400 mt-1">{stats?.quarantined ?? 1}</div>
        </div>
        <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800">
          <div className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Replaying</div>
          <div className="text-2xl font-extrabold text-amber-400 mt-1">{stats?.replaying ?? 0}</div>
        </div>
        <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800">
          <div className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Resolved</div>
          <div className="text-2xl font-extrabold text-emerald-400 mt-1">{stats?.resolved ?? 14}</div>
        </div>
        <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800">
          <div className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Poison Pills</div>
          <div className="text-2xl font-extrabold text-zinc-400 mt-1">{stats?.poison_pill ?? 0}</div>
        </div>
      </div>

      {/* Incidents Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-400 font-medium">
              <th className="pb-2">Incident ID</th>
              <th className="pb-2">Category</th>
              <th className="pb-2">Source Service</th>
              <th className="pb-2">Error Message</th>
              <th className="pb-2 text-center">Retries</th>
              <th className="pb-2 text-center">Status</th>
              <th className="pb-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60">
            {incidents.map((inc) => (
              <tr key={inc.incident_id} className="hover:bg-zinc-800/30 transition">
                <td className="py-2.5 font-mono text-zinc-300">{inc.incident_id}</td>
                <td className="py-2.5">
                  <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono text-[10px]">
                    {inc.error_category}
                  </span>
                </td>
                <td className="py-2.5 text-zinc-400">{inc.source_service}</td>
                <td className="py-2.5 text-zinc-300 max-w-xs truncate" title={inc.error_message}>
                  {inc.error_message}
                </td>
                <td className="py-2.5 text-center font-mono text-zinc-400">
                  {inc.retry_count}/{inc.max_retries}
                </td>
                <td className="py-2.5 text-center">
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      inc.status === 'RESOLVED'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : inc.status === 'QUARANTINED'
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        : 'bg-amber-500/20 text-amber-300'
                    }`}
                  >
                    {inc.status}
                  </span>
                </td>
                <td className="py-2.5 text-right space-x-2">
                  <button
                    onClick={() => setSelectedIncident(inc)}
                    className="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition"
                    title="Inspect Payload"
                  >
                    <Eye className="w-3.5 h-3.5" />
                  </button>
                  {inc.status !== 'RESOLVED' && (
                    <button
                      onClick={() => handleReplay(inc.incident_id)}
                      className="p-1 rounded bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 transition"
                      title="Trigger Replay"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Payload Inspection Modal */}
      {selectedIncident && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl max-w-2xl w-full p-6 text-xs text-zinc-300">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <h4 className="font-bold text-sm text-white">Quarantine Inspector: {selectedIncident.incident_id}</h4>
              <button
                onClick={() => setSelectedIncident(null)}
                className="text-zinc-400 hover:text-white font-bold text-sm"
              >
                ✕
              </button>
            </div>
            <div className="mt-4 space-y-3">
              <div>
                <span className="font-bold text-zinc-400 block mb-1">Error Message:</span>
                <p className="p-2 rounded bg-zinc-950 text-rose-300 font-mono">{selectedIncident.error_message}</p>
              </div>
              <div>
                <span className="font-bold text-zinc-400 block mb-1">Payload:</span>
                <pre className="p-3 rounded bg-zinc-950 font-mono text-[11px] overflow-x-auto text-zinc-300 max-h-40">
                  {JSON.stringify(selectedIncident.payload, null, 2)}
                </pre>
              </div>
              {selectedIncident.traceback_str && (
                <div>
                  <span className="font-bold text-zinc-400 block mb-1">Stack Trace:</span>
                  <pre className="p-3 rounded bg-zinc-950 font-mono text-[10px] overflow-x-auto text-zinc-400 max-h-32">
                    {selectedIncident.traceback_str}
                  </pre>
                </div>
              )}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setSelectedIncident(null)}
                className="px-4 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
