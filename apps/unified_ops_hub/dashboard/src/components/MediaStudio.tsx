'use client';

import React, { useState, useRef } from 'react';
import {
  Film,
  Sparkles,
  Scissors,
  Play,
  Pause,
  Download,
  RefreshCw,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Video,
  Type,
} from 'lucide-react';
import {
  renderMediaVideo,
  RenderRequest,
  MediaRenderResult,
} from '@/lib/api';

export interface MediaStudioProps {
  initialSourceFile?: string;
  initialProxyUrl?: string;
  initialDuration?: number;
}

export type CutPresetKey = 'hype_drop' | 'cinematic' | 'raw_pov' | 'custom';

export function MediaStudio({
  initialSourceFile = 'clip_ultra_drop_4k_01.mp4',
  initialProxyUrl = '/proxies/sample_clip_proxy.mp4',
  initialDuration = 30.0,
}: MediaStudioProps) {
  const [sourceFile] = useState(initialSourceFile);
  const [proxyUrl] = useState(initialProxyUrl);
  const [totalDuration] = useState(initialDuration);

  // Cut preset and trimming state
  const [activePreset, setActivePreset] = useState<CutPresetKey>('hype_drop');
  const [cropRatio, setCropRatio] = useState<'9:16' | '16:9' | 'original'>('9:16');
  const [inPoint, setInPoint] = useState<number>(5.0);
  const [outPoint, setOutPoint] = useState<number>(15.0);
  const [textOverlay, setTextOverlay] = useState<string>('🔥 INSANE DROP');

  // Video playback state
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(5.0);

  // AI Google Flow State (Deep Think)
  const [subject, setSubject] = useState<string>('');
  const [scene, setScene] = useState<string>('');
  const [style, setStyle] = useState<string>('');
  const [use5Experts, setUse5Experts] = useState<boolean>(true);

  // Render & API state
  const [isRendering, setIsRendering] = useState(false);
  const [renderResult, setRenderResult] = useState<MediaRenderResult | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  // Presets definition
  const presets: Record<
    'hype_drop' | 'cinematic' | 'raw_pov',
    {
      in_point: number;
      out_point: number;
      crop_ratio: '9:16' | '16:9' | 'original';
      label: string;
      description: string;
      icon: React.ComponentType<{ className?: string }>;
    }
  > = {
    hype_drop: {
      in_point: 5.0,
      out_point: 15.0,
      crop_ratio: '9:16',
      label: 'Hype Drop (9:16)',
      description: 'Loudest Audio Peak (10.0s)',
      icon: Sparkles,
    },
    cinematic: {
      in_point: 0.0,
      out_point: totalDuration,
      crop_ratio: '16:9',
      label: 'Cinematic (16:9)',
      description: `Full Widescreen (${totalDuration.toFixed(1)}s)`,
      icon: Film,
    },
    raw_pov: {
      in_point: 0.0,
      out_point: totalDuration,
      crop_ratio: 'original',
      label: 'Raw POV (Original)',
      description: `Native Aspect (${totalDuration.toFixed(1)}s)`,
      icon: Video,
    },
  };

  const applyPreset = (key: 'hype_drop' | 'cinematic' | 'raw_pov') => {
    const p = presets[key];
    setActivePreset(key);
    setCropRatio(p.crop_ratio);
    setInPoint(p.in_point);
    setOutPoint(p.out_point);

    if (videoRef.current) {
      videoRef.current.currentTime = p.in_point;
      setCurrentTime(p.in_point);
    }
  };

  const handleInPointChange = (val: number) => {
    const clamped = Math.max(0, Math.min(val, outPoint - 0.5));
    setInPoint(clamped);
    setActivePreset('custom');
    if (videoRef.current) {
      videoRef.current.currentTime = clamped;
      setCurrentTime(clamped);
    }
  };

  const handleOutPointChange = (val: number) => {
    const clamped = Math.min(totalDuration, Math.max(val, inPoint + 0.5));
    setOutPoint(clamped);
    setActivePreset('custom');
    if (videoRef.current) {
      videoRef.current.currentTime = clamped;
      setCurrentTime(clamped);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const curr = videoRef.current.currentTime;
      setCurrentTime(curr);
      // Loop or stop if reaching outPoint
      if (curr >= outPoint) {
        videoRef.current.currentTime = inPoint;
        setCurrentTime(inPoint);
      }
    }
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
        setIsPlaying(false);
      } else {
        if (currentTime < inPoint || currentTime >= outPoint) {
          videoRef.current.currentTime = inPoint;
        }
        videoRef.current.play().catch(() => {});
        setIsPlaying(true);
      }
    }
  };

  const handleRenderAndPublish = async () => {
    setIsRendering(true);
    setRenderError(null);
    setRenderResult(null);

    const payload: RenderRequest = {
      source_file: sourceFile,
      in_point: inPoint,
      out_point: outPoint,
      crop_ratio: cropRatio,
      text_overlay: textOverlay.trim() ? textOverlay.trim() : undefined,
      sync: true,
      subject,
      scene,
      style,
      use_5_experts: use5Experts
    } as any; // Type override since we are dynamically extending the payload

    try {
      const res = await renderMediaVideo(payload);
      setRenderResult(res);
    } catch (err: any) {
      setRenderError(err?.message || 'FFmpeg render request failed.');
    } finally {
      setIsRendering(false);
    }
  };

  const selectedDuration = Math.max(0, outPoint - inPoint);

  return (
    <div className="glass-panel rounded-2xl p-6 border border-zinc-800/80 bg-zinc-900/40 relative overflow-hidden space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
            <Scissors className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Media Studio & Asset Producer
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-950/80 text-blue-300 border border-blue-800/50">
                Google Flow (5-Experts)
              </span>
            </h2>
            <p className="text-xs text-zinc-400">
              Interactive Video Scrubbing paired with Deep Think Prompt Engineering
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400 font-mono hidden sm:inline">
            Source: <span className="text-zinc-200">{sourceFile}</span>
          </span>
        </div>
      </div>

      {/* Main Editing Layout: Video Player + Tools */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Video Player & Overlay Preview (7 cols) */}
        <div className="lg:col-span-7 flex flex-col items-center justify-center p-4 rounded-xl bg-zinc-950/80 border border-zinc-800 space-y-4 min-h-[380px]">
          <div
            className={`relative rounded-xl overflow-hidden bg-black flex items-center justify-center shadow-2xl border border-zinc-800/60 transition-all ${
              cropRatio === '9:16'
                ? 'w-full max-w-[260px] aspect-[9/16]'
                : cropRatio === '16:9'
                ? 'w-full max-w-[480px] aspect-video'
                : 'w-full max-w-[440px] aspect-video'
            }`}
          >
            {/* HTML5 Video Element */}
            <video
              ref={videoRef}
              src={proxyUrl}
              onTimeUpdate={handleTimeUpdate}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              playsInline
              className="w-full h-full object-cover"
              data-testid="media-studio-video"
            />

            {/* Instagram-Style Text Overlay Stamp Preview */}
            {textOverlay.trim() && (
              <div
                data-testid="text-overlay-preview"
                className="absolute bottom-6 inset-x-4 flex justify-center pointer-events-none"
              >
                <div className="px-3.5 py-1.5 rounded-lg bg-black/75 backdrop-blur-sm border border-white/20 text-white font-extrabold text-xs sm:text-sm tracking-wider uppercase shadow-xl text-center">
                  {textOverlay}
                </div>
              </div>
            )}

            {/* Play/Pause Overlay Button */}
            <button
              type="button"
              onClick={togglePlay}
              aria-label={isPlaying ? 'Pause video' : 'Play video'}
              className="absolute inset-0 m-auto w-12 h-12 rounded-full bg-black/50 hover:bg-black/70 border border-white/30 text-white flex items-center justify-center transition opacity-80 hover:opacity-100 hover:scale-105 cursor-pointer"
            >
              {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
            </button>

            {/* Aspect Ratio Badge */}
            <div className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded bg-black/60 border border-zinc-700 text-[10px] font-mono text-zinc-300 uppercase">
              {cropRatio}
            </div>
          </div>

          {/* Player Controls Bar */}
          <div className="w-full max-w-md flex items-center justify-between text-xs text-zinc-400 px-2 pt-1 font-mono">
            <span data-testid="current-time-display">
              {currentTime.toFixed(1)}s / {totalDuration.toFixed(1)}s
            </span>
            <span className="text-violet-400 font-semibold">
              Trim Range: [{inPoint.toFixed(1)}s - {outPoint.toFixed(1)}s]
            </span>
          </div>
        </div>

        {/* Right Column: AI Cuts, Trim Sliders, Text Overlay, Render Button (5 cols) */}
        <div className="lg:col-span-5 space-y-5">
          {/* 1. Base AI Cut Presets */}
          <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800 space-y-3">
            <label className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-violet-400" />
              AI Cut Presets
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {(['hype_drop', 'cinematic', 'raw_pov'] as const).map((key) => {
                const p = presets[key];
                const Icon = p.icon;
                const isSelected = activePreset === key;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => applyPreset(key)}
                    className={`p-3 rounded-xl border text-left flex flex-col justify-between transition cursor-pointer ${
                      isSelected
                        ? 'bg-violet-950/70 border-violet-500/80 text-white shadow-sm ring-1 ring-violet-500/50'
                        : 'bg-zinc-900/50 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
                    }`}
                    data-testid={`preset-btn-${key}`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <Icon className={`w-4 h-4 ${isSelected ? 'text-violet-300' : 'text-zinc-400'}`} />
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800/80 text-zinc-300">
                        {p.crop_ratio}
                      </span>
                    </div>
                    <div className="text-xs font-bold leading-tight">{p.label}</div>
                    <div className="text-[10px] text-zinc-400 mt-1 leading-tight">{p.description}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 2. Dual-Handle In/Out Point Trimming */}
          <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-violet-400" />
                Precision Trim Controls
              </label>
              <span className="text-xs font-mono font-bold text-emerald-400">
                Duration: {selectedDuration.toFixed(1)}s
              </span>
            </div>

            {/* In-Point Slider */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-zinc-400">
                <span>In-Point (Start):</span>
                <span className="font-mono text-zinc-200 font-bold" data-testid="in-point-value">
                  {inPoint.toFixed(1)}s
                </span>
              </div>
              <input
                type="range"
                min="0"
                max={Math.max(0, totalDuration - 0.5)}
                step="0.1"
                value={inPoint}
                onChange={(e) => handleInPointChange(parseFloat(e.target.value))}
                className="w-full accent-violet-500 bg-zinc-800 cursor-pointer"
                data-testid="in-point-slider"
                aria-label="In-point trim slider"
              />
            </div>

            {/* Out-Point Slider */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-zinc-400">
                <span>Out-Point (End):</span>
                <span className="font-mono text-zinc-200 font-bold" data-testid="out-point-value">
                  {outPoint.toFixed(1)}s
                </span>
              </div>
              <input
                type="range"
                min="0.5"
                max={totalDuration}
                step="0.1"
                value={outPoint}
                onChange={(e) => handleOutPointChange(parseFloat(e.target.value))}
                className="w-full accent-violet-500 bg-zinc-800 cursor-pointer"
                data-testid="out-point-slider"
                aria-label="Out-point trim slider"
              />
            </div>
          </div>

          {/* 3. Google Flow (Deep Think Generation) */}
          <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                Google Flow (Deep Think)
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={use5Experts}
                  onChange={(e) => setUse5Experts(e.target.checked)}
                  className="accent-blue-500 rounded cursor-pointer"
                />
                <span className="text-[10px] font-mono font-bold text-blue-400 uppercase">5-Expert Consensus</span>
              </label>
            </div>
            
            <div className="space-y-2">
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Subject (e.g., DJ on main stage)"
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-zinc-900 border border-zinc-700 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition"
              />
              <input
                type="text"
                value={scene}
                onChange={(e) => setScene(e.target.value)}
                placeholder="Scene (e.g., Ultra Miami at night)"
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-zinc-900 border border-zinc-700 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition"
              />
              <input
                type="text"
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                placeholder="Style (e.g., Cinematic, high contrast)"
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-zinc-900 border border-zinc-700 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition"
              />
            </div>
          </div>

          {/* 4. Instagram-Style Text Overlay Field */}
          <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800 space-y-2.5">
            <label
              htmlFor="text-overlay-input"
              className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center gap-1.5"
            >
              <Type className="w-3.5 h-3.5 text-violet-400" />
              Text Overlay (DrawText)
            </label>
            <input
              id="text-overlay-input"
              type="text"
              value={textOverlay}
              onChange={(e) => setTextOverlay(e.target.value)}
              placeholder="e.g. 🔥 INSANE DROP | Ultra 2026"
              className="w-full px-3.5 py-2 text-xs rounded-xl bg-zinc-900 border border-zinc-700 text-white placeholder-zinc-500 focus:outline-none focus:border-violet-500 transition"
              data-testid="text-overlay-input"
            />
            <div className="flex flex-wrap gap-1.5 pt-1">
              {['🔥 INSANE DROP', '⚡ ULTRA MIAMI 2026', '🎧 LIVE POV', '🚨 UNRELEASED ID'].map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => setTextOverlay(tag)}
                  className="text-[10px] px-2 py-0.5 rounded-md bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 border border-zinc-700/60 transition cursor-pointer"
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          {/* 5. Render & Publish Action Button */}
          <div className="space-y-3 pt-1">
            <button
              type="button"
              onClick={handleRenderAndPublish}
              disabled={isRendering || inPoint >= outPoint}
              className={`w-full py-3 px-4 rounded-xl text-xs font-extrabold flex items-center justify-center gap-2 transition shadow-lg cursor-pointer ${
                isRendering
                  ? 'bg-zinc-800 text-zinc-400 cursor-not-allowed border border-zinc-700'
                  : 'bg-violet-600 hover:bg-violet-500 text-white border border-violet-400/40 hover:shadow-violet-600/30'
              }`}
              data-testid="render-publish-button"
            >
              {isRendering ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-violet-300" />
                  <span>Rendering 4K Master via FFmpeg...</span>
                </>
              ) : (
                <>
                  <Film className="w-4 h-4" />
                  <span>Render & Publish ({cropRatio} • {selectedDuration.toFixed(1)}s)</span>
                </>
              )}
            </button>

            {/* Error Message Container */}
            {renderError && (
              <div
                className="p-3 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs flex items-center gap-2"
                data-testid="render-error-container"
              >
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{renderError}</span>
              </div>
            )}

            {/* Success Result Container */}
            {renderResult && (
              <div
                className="p-4 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-xs space-y-2.5"
                data-testid="render-success-container"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-bold text-emerald-300">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Render Complete!</span>
                  </div>
                  <span className="text-[10px] font-mono bg-emerald-900/60 px-2 py-0.5 rounded border border-emerald-700/50">
                    {renderResult.job_id}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] text-zinc-300 font-mono pt-1">
                  <div>Ratio: <span className="text-white">{renderResult.crop_ratio}</span></div>
                  <div>Duration: <span className="text-white">{renderResult.duration}s</span></div>
                  <div className="col-span-2 truncate">File: <span className="text-emerald-300">{renderResult.output_file || renderResult.output_url}</span></div>
                </div>

                {renderResult.output_url && (
                  <div className="pt-2 flex items-center gap-2">
                    <a
                      href={renderResult.output_url}
                      download
                      className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition"
                      data-testid="download-rendered-mp4"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download Rendered MP4
                    </a>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
