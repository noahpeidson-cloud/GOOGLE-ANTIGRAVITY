'use client';

import React, { useState } from 'react';
import { LayoutDashboard, CreditCard, Film, Scissors, Bot, ShieldAlert, Layers } from 'lucide-react';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { SystemHealthHeader } from '@/components/SystemHealthHeader';
import { SportsCardWidget } from '@/components/SportsCardWidget';
import { MediaIngestionWidget } from '@/components/MediaIngestionWidget';
import { MediaStudio } from '@/components/MediaStudio';
import { MediaGallery } from '@/components/MediaGallery';
import { MLAgentWidget } from '@/components/MLAgentWidget';
import { DLQCenter } from '@/components/DLQCenter';
import { LiveTelemetryStream } from '@/components/LiveTelemetryStream';

type TabType = 'overview' | 'sports' | 'media' | 'studio' | 'ml' | 'dlq';

export default function CommandCenterDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col">
      {/* 1. Master System Health Header */}
      <ErrorBoundary fallbackTitle="Header Service Interrupted">
        <SystemHealthHeader />
      </ErrorBoundary>

      {/* 2. Navigation Tabs */}
      <nav aria-label="Dashboard views" className="border-b border-zinc-800/80 bg-zinc-900/30 px-6 py-2">
        <div className="max-w-7xl mx-auto flex items-center gap-2 overflow-x-auto">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition ${
              activeTab === 'overview'
                ? 'bg-zinc-800 text-white shadow-sm border border-zinc-700/60'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            Overview Matrix
          </button>

          <button
            onClick={() => setActiveTab('sports')}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition ${
              activeTab === 'sports'
                ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-700/50'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            <CreditCard className="w-3.5 h-3.5 text-emerald-400" />
            Sports Cards
          </button>

          <button
            onClick={() => setActiveTab('media')}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition ${
              activeTab === 'media'
                ? 'bg-purple-950/60 text-purple-300 border border-purple-700/50'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            <Film className="w-3.5 h-3.5 text-purple-400" />
            Media & PySpark
          </button>

          <button
            onClick={() => setActiveTab('studio')}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition ${
              activeTab === 'studio'
                ? 'bg-violet-950/60 text-violet-300 border border-violet-700/50'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            <Scissors className="w-3.5 h-3.5 text-violet-400" />
            Media Studio
          </button>

          <button
            onClick={() => setActiveTab('ml')}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition ${
              activeTab === 'ml'
                ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-700/50'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            <Bot className="w-3.5 h-3.5 text-cyan-400" />
            ML Agent & Trends
          </button>

          <button
            onClick={() => setActiveTab('dlq')}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition ${
              activeTab === 'dlq'
                ? 'bg-rose-950/60 text-rose-300 border border-rose-700/50'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
            DLQ Isolation
          </button>
        </div>
      </nav>

      {/* 3. Main Workspace Grid */}
      <main className="max-w-7xl mx-auto px-6 py-6 flex-1 w-full space-y-6">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ErrorBoundary fallbackTitle="Sports Card Ecosystem Service Error">
              <SportsCardWidget />
            </ErrorBoundary>

            <ErrorBoundary fallbackTitle="Media Ingestion & Grading Pipeline Error">
              <MediaIngestionWidget />
            </ErrorBoundary>

            <ErrorBoundary fallbackTitle="ML Agent & Viral Trends Error">
              <MLAgentWidget />
            </ErrorBoundary>

            <ErrorBoundary fallbackTitle="DLQ & Incident Isolation Error">
              <DLQCenter />
            </ErrorBoundary>
          </div>
        )}

        {activeTab === 'sports' && (
          <ErrorBoundary fallbackTitle="Sports Card Ecosystem Service Error">
            <SportsCardWidget />
          </ErrorBoundary>
        )}

        {activeTab === 'media' && (
          <div className="space-y-6">
            <ErrorBoundary fallbackTitle="Media Gallery Error">
              <MediaGallery />
            </ErrorBoundary>
            <ErrorBoundary fallbackTitle="Media Ingestion & Grading Pipeline Error">
              <MediaIngestionWidget />
            </ErrorBoundary>
            <ErrorBoundary fallbackTitle="Media Studio Web Editor Error">
              <MediaStudio />
            </ErrorBoundary>
          </div>
        )}

        {activeTab === 'studio' && (
          <ErrorBoundary fallbackTitle="Media Studio Web Editor Error">
            <MediaStudio />
          </ErrorBoundary>
        )}

        {activeTab === 'ml' && (
          <ErrorBoundary fallbackTitle="ML Agent & Viral Trends Error">
            <MLAgentWidget />
          </ErrorBoundary>
        )}

        {activeTab === 'dlq' && (
          <ErrorBoundary fallbackTitle="DLQ & Incident Isolation Error">
            <DLQCenter />
          </ErrorBoundary>
        )}

        {/* 4. Docked Live Telemetry Stream */}
        <div className="pt-2">
          <ErrorBoundary fallbackTitle="Event Stream Telemetry Error">
            <LiveTelemetryStream />
          </ErrorBoundary>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800/80 bg-zinc-950 py-4 px-6 text-center text-xs text-zinc-500">
        Google Antigravity Unified Ops Hub • Autonomous Execution & Resilient Microservices Framework
      </footer>
    </div>
  );
}
