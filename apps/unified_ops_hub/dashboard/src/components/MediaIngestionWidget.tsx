'use client';

import React, { useState } from 'react';
import { Film, Wifi, Sparkles, Sliders, CheckCircle2, Play, Layers } from 'lucide-react';
import { gradeVideo, triggerMediaJob, VideoGradeResult } from '@/lib/api';

export function MediaIngestionWidget() {
  const [videoId, setVideoId] = useState('clip_ultra_drop_4k_01.mp4');
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [scores, setScores] = useState({
    HRV: 92.4,
    DPAW: 88.0,
    ADR_SFD: 85.2,
    CKE_MVE: 90.1,
    LTSS: 86.5,
  });
  const [gradeResult, setGradeResult] = useState<VideoGradeResult | null>({
    video_id: 'clip_ultra_drop_4k_01.mp4',
    evpi: 88.74,
    verdict: 'VIRAL_READY',
    scores: { HRV: 92.4, DPAW: 88.0, ADR_SFD: 85.2, CKE_MVE: 90.1, LTSS: 86.5 },
    aspect_ratio: '9:16',
  });
  const [isGrading, setIsGrading] = useState(false);
  const [jobTriggerStatus, setJobTriggerStatus] = useState<string | null>(null);

  const handleRunGrade = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsGrading(true);
    try {
      const res = await gradeVideo(videoId, scores, aspectRatio);
      setGradeResult(res);
    } catch (err) {
      console.error('Grading error:', err);
    } finally {
      setIsGrading(false);
    }
  };

  const handleTriggerIngestion = async () => {
    setJobTriggerStatus('Triggering ADB Wi-Fi 01_RAW Ingestion & FFmpeg Proxy Pipeline...');
    await triggerMediaJob('RAW_CAPTURE_20260825_004.mp4', 'vertical_reframes', 'HIGH');
    setTimeout(() => {
      setJobTriggerStatus('Ingestion Job QUEUED. 01_RAW Inbox synced.');
      setTimeout(() => setJobTriggerStatus(null), 3000);
    }, 800);
  };

  return (
    <div className="glass-panel rounded-2xl p-6 border border-zinc-800/80 bg-zinc-900/40 relative overflow-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <Film className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Media Ingestion & PySpark Grading Pipeline
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-950/80 text-purple-300 border border-purple-800/50">
                Track 2 Active
              </span>
            </h2>
            <p className="text-xs text-zinc-400">ADB Wi-Fi Ingestion, FFmpeg 720p Proxies & DaVinci XML Export</p>
          </div>
        </div>

        <button
          onClick={handleTriggerIngestion}
          className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-purple-600 hover:bg-purple-500 text-white transition flex items-center gap-1.5 self-start sm:self-auto"
        >
          <Play className="w-3.5 h-3.5" />
          Trigger Pipeline Run
        </button>
      </div>

      {jobTriggerStatus && (
        <div className="mt-4 p-2.5 rounded-xl bg-purple-950/60 border border-purple-500/40 text-purple-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-purple-400 shrink-0" />
          <span>{jobTriggerStatus}</span>
        </div>
      )}

      {/* Ingestion & Hardware Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 my-5">
        <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">ADB Wi-Fi Ingest</div>
            <div className="text-sm font-bold text-emerald-400 mt-0.5 flex items-center gap-1.5">
              <Wifi className="w-3.5 h-3.5" /> 192.168.1.150 (5GHz)
            </div>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">ACTIVE</span>
        </div>

        <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">01_RAW Inbox</div>
            <div className="text-sm font-bold text-white mt-0.5">12 Clips (4K HDR)</div>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono">3 Proxies Ready</span>
        </div>

        <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Recording Guard</div>
            <div className="text-sm font-bold text-emerald-400 mt-0.5">LOCKED / ACTIVE</div>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">DaVinci Sync</span>
        </div>
      </div>

      {/* PySpark 5-Score Breakdown & Viral Calculator */}
      <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <h3 className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400" />
            PySpark Gemini-Omni 5-Score Viral Radar
          </h3>
          {gradeResult && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-400">EVPI Score:</span>
              <span className="text-sm font-extrabold font-mono text-emerald-400">{gradeResult.evpi} / 100</span>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                  gradeResult.verdict === 'VIRAL_READY'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-amber-500/20 text-amber-300'
                }`}
              >
                {gradeResult.verdict}
              </span>
            </div>
          )}
        </div>

        {/* Sliders Grid */}
        <form onSubmit={handleRunGrade} className="mt-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
            <div>
              <label className="text-zinc-400 block mb-1">HRV (Hook Retention): {scores.HRV}</label>
              <input
                type="range"
                min="0"
                max="100"
                value={scores.HRV}
                onChange={(e) => setScores({ ...scores, HRV: parseFloat(e.target.value) })}
                className="w-full accent-purple-500 bg-zinc-800"
              />
            </div>
            <div>
              <label className="text-zinc-400 block mb-1">DPAW (Dynamic Pacing): {scores.DPAW}</label>
              <input
                type="range"
                min="0"
                max="100"
                value={scores.DPAW}
                onChange={(e) => setScores({ ...scores, DPAW: parseFloat(e.target.value) })}
                className="w-full accent-purple-500 bg-zinc-800"
              />
            </div>
            <div>
              <label className="text-zinc-400 block mb-1">ADR_SFD (Speech Freq): {scores.ADR_SFD}</label>
              <input
                type="range"
                min="0"
                max="100"
                value={scores.ADR_SFD}
                onChange={(e) => setScores({ ...scores, ADR_SFD: parseFloat(e.target.value) })}
                className="w-full accent-purple-500 bg-zinc-800"
              />
            </div>
            <div>
              <label className="text-zinc-400 block mb-1">CKE_MVE (Visual Entropy): {scores.CKE_MVE}</label>
              <input
                type="range"
                min="0"
                max="100"
                value={scores.CKE_MVE}
                onChange={(e) => setScores({ ...scores, CKE_MVE: parseFloat(e.target.value) })}
                className="w-full accent-purple-500 bg-zinc-800"
              />
            </div>
            <div>
              <label className="text-zinc-400 block mb-1">LTSS (Shareability): {scores.LTSS}</label>
              <input
                type="range"
                min="0"
                max="100"
                value={scores.LTSS}
                onChange={(e) => setScores({ ...scores, LTSS: parseFloat(e.target.value) })}
                className="w-full accent-purple-500 bg-zinc-800"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <div className="flex items-center gap-4 text-xs">
              <span className="text-zinc-400">Aspect Ratio:</span>
              <label className="flex items-center gap-1.5 text-zinc-200 cursor-pointer">
                <input
                  type="radio"
                  name="ratio"
                  value="9:16"
                  checked={aspectRatio === '9:16'}
                  onChange={() => setAspectRatio('9:16')}
                  className="accent-purple-500"
                />
                9:16 (Shorts / Reels)
              </label>
              <label className="flex items-center gap-1.5 text-zinc-200 cursor-pointer">
                <input
                  type="radio"
                  name="ratio"
                  value="16:9"
                  checked={aspectRatio === '16:9'}
                  onChange={() => setAspectRatio('16:9')}
                  className="accent-purple-500"
                />
                16:9 (Landscape -50% EVPI)
              </label>
            </div>

            <button
              type="submit"
              disabled={isGrading}
              className="px-4 py-1.5 text-xs font-bold rounded-lg bg-zinc-800 hover:bg-zinc-700 text-purple-300 border border-purple-500/30 transition flex items-center gap-1.5"
            >
              <Sliders className="w-3.5 h-3.5" />
              {isGrading ? 'Evaluating...' : 'Recalculate EVPI'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
