import React from 'react';
import { Header } from './components/Header';
import { MetricsBar } from './components/MetricsBar';
import { IngestDaemonPanel } from './components/IngestDaemonPanel';
import { VectorHubPanel } from './components/VectorHubPanel';
import { EventFeedPanel } from './components/EventFeedPanel';
import { ErrorBoundary } from './components/ErrorBoundary';
import { useTelemetryWebSocket } from './hooks/useTelemetryWebSocket';

export const App: React.FC = () => {
  const {
    telemetry,
    connectionStatus,
    eventLog,
    connectedClients,
    triggerIngestSync,
  } = useTelemetryWebSocket();

  return (
    <div className="min-h-screen bg-ops-bg text-slate-100 flex flex-col font-sans">
      <Header connectionStatus={connectionStatus} connectedClients={connectedClients} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Real-time Telemetry Metrics Bar */}
        <ErrorBoundary fallbackTitle="Telemetry Metrics Stream">
          <MetricsBar telemetry={telemetry} />
        </ErrorBoundary>

        {/* Primary Dashboard Grid: Vector Hub & Ingest Daemon */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Vector Hub Search Placeholder (7 cols) */}
          <div className="lg:col-span-7">
            <ErrorBoundary fallbackTitle="Vector Hub Semantic Search">
              <VectorHubPanel />
            </ErrorBoundary>
          </div>

          {/* Right Column: Ingest Daemon Status (5 cols) */}
          <div className="lg:col-span-5">
            <ErrorBoundary fallbackTitle="Ingest Daemon Panel">
              <IngestDaemonPanel
                daemonState={telemetry.ingest_daemon}
                onTriggerSync={triggerIngestSync}
              />
            </ErrorBoundary>
          </div>
        </div>

        {/* Bottom Section: Real-time Event Feed */}
        <div className="w-full">
          <ErrorBoundary fallbackTitle="Telemetry Event Stream">
            <EventFeedPanel eventLog={eventLog} onClear={() => {}} />
          </ErrorBoundary>
        </div>
      </main>

      {/* Accessible Footer */}
      <footer className="border-t border-ops-border py-4 px-6 text-center text-xs text-ops-muted">
        <p>Unified Ops Hub &bull; Headless Telemetry & Distributed Services Bus &bull; WCAG 2.1 AA Compliant</p>
      </footer>
    </div>
  );
};

export default App;
