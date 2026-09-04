import React, { useState } from 'react';
import { WebSocketEventMessage } from '../types/telemetry';
import { Activity, Terminal, Trash2, Radio } from 'lucide-react';

interface EventFeedPanelProps {
  eventLog: WebSocketEventMessage[];
  onClear: () => void;
}

export const EventFeedPanel: React.FC<EventFeedPanelProps> = ({ eventLog, onClear }) => {
  const [filter, setFilter] = useState<string>('all');

  const filteredEvents = eventLog.filter((evt) => {
    if (filter === 'all') return true;
    return evt.event.toLowerCase().includes(filter.toLowerCase());
  });

  return (
    <section
      aria-labelledby="telemetry-bus-title"
      className="bg-ops-surface border border-ops-border rounded-xl p-5 shadow-md flex flex-col h-full"
    >
      <div className="flex items-center justify-between pb-3.5 border-b border-ops-border mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
            <Radio className="w-5 h-5" />
          </div>
          <div>
            <h2 id="telemetry-bus-title" className="text-base font-semibold text-white">
              WebSocket Telemetry Stream
            </h2>
            <p className="text-xs text-ops-muted">Multiplexed Real-time Event Bus</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label="Filter events"
            className="text-xs bg-ops-card border border-ops-border rounded-md px-2 py-1 text-slate-300 focus:outline-none focus:ring-1 focus:ring-ops-accent"
          >
            <option value="all">All Events</option>
            <option value="telemetry">Telemetry Only</option>
            <option value="sync">Sync Events</option>
          </select>

          <button
            type="button"
            onClick={onClear}
            aria-label="Clear Event Feed"
            className="p-1.5 rounded-md bg-ops-card hover:bg-ops-cardHover border border-ops-border text-slate-400 hover:text-white transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Event Stream Container */}
      <div className="flex-1 overflow-y-auto space-y-2 max-h-[380px] font-mono text-xs pr-1">
        {filteredEvents.length === 0 ? (
          <div className="text-center py-8 text-ops-muted text-xs">
            Listening for live telemetry frames on /ws...
          </div>
        ) : (
          filteredEvents.map((evt, idx) => (
            <div
              key={idx}
              className="p-2.5 rounded bg-ops-card/80 border border-ops-border/60 hover:border-ops-border transition-colors flex items-start gap-2.5"
            >
              <Terminal className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <span className="font-semibold text-sky-300 uppercase tracking-wide">
                    {evt.event}
                  </span>
                  <span className="text-slate-500">
                    {new Date(evt.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="text-slate-300 text-[11px] truncate">
                  {evt.data ? JSON.stringify(evt.data) : 'No payload'}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
};
