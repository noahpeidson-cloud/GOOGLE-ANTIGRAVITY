import React, { useState, useEffect, useRef } from 'react';
import { Radio, Zap, CheckCircle2 } from 'lucide-react';
import { PhoneLinkFeedState } from '../types';
import { VideoTagsPanel } from './VideoTagsPanel';
import { VideoTag } from '../lib/dataconnect';

interface PhoneLinkFeedProps {
  feedState?: PhoneLinkFeedState;
  onTriggerAdbPull?: () => void;
  onCaptureScreen?: () => void;
  onSelectVideoTag?: (tag: VideoTag) => void;
  isPulling?: boolean;
}

export const PhoneLinkFeed: React.FC<PhoneLinkFeedProps> = ({
  feedState = {
    active: true,
    currentVideo: {
      filename: '20260819_213606.mp4',
      description: 'Excision Drop',
      src: '/placeholder.mp4',
      poster: '/placeholder.png',
    },
    visionResult: {
      entity: 'Excision',
      attribute: 'Lasers, Bass Drop',
      action: 'ADB Pull Triggered',
    },
  },
  onTriggerAdbPull,
  onCaptureScreen,
  onSelectVideoTag,
  isPulling = false,
}) => {
  const [videoError, setVideoError] = useState(false);
  const [pullSuccess, setPullSuccess] = useState(false);
  const [selectedTag, setSelectedTag] = useState<VideoTag | null>(null);
  const pullTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (pullTimerRef.current) {
        clearTimeout(pullTimerRef.current);
      }
    };
  }, []);

  const handleSelectTag = (tag: VideoTag) => {
    setSelectedTag(tag);
    if (onSelectVideoTag) {
      onSelectVideoTag(tag);
    }
  };

  const handlePullClick = () => {
    if (onTriggerAdbPull) {
      onTriggerAdbPull();
    } else {
      if (pullTimerRef.current) {
        clearTimeout(pullTimerRef.current);
      }
      setPullSuccess(true);
      pullTimerRef.current = setTimeout(() => setPullSuccess(false), 3000);
    }
  };

  return (
    <section
      role="region"
      aria-labelledby="phone-link-feed-heading"
      className="col-span-4 flex flex-col bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-sm overflow-hidden relative"
    >
      {/* Panel Header */}
      <div className="p-5 border-b border-[var(--border)] bg-black/20">
        <h2 id="phone-link-feed-heading" className="font-bold text-xl flex items-center justify-between text-[var(--foreground)]">
          <span>Phone Link Feed</span>
          <span className="text-[10px] bg-[var(--primary)] text-white px-2 py-1 rounded uppercase tracking-wide font-mono font-semibold shadow">
            Ctrl+Shift+T to Tag
          </span>
        </h2>
        <p className="text-sm text-[var(--muted-foreground)] mt-2 leading-relaxed">
          The daemon is watching your Windows Phone Link window. When you scroll through Samsung Gallery on your PC and hit the hotkey, Gemini Vision analyzes the screen to auto-tag the exact video you're viewing.
        </p>
      </div>

      {/* Panel Body */}
      <div className="flex-1 p-5 overflow-y-auto bg-black/40 space-y-4">
        {/* Stream Frame */}
        <div className="border border-[var(--primary)] rounded-xl overflow-hidden relative shadow-lg">
          {/* Live Badge */}
          <div className="absolute top-2 right-2 bg-red-500 text-white text-xs px-2 py-1 rounded font-bold uppercase tracking-wider shadow-lg flex items-center z-10 pointer-events-none">
            <div className="w-2 h-2 bg-white rounded-full animate-ping mr-2" aria-hidden="true" />
            Live Capture
          </div>

          {/* 9:16 Aspect Phone Canvas */}
          <div className="aspect-[9/16] bg-gray-900 w-full flex flex-col items-center justify-center p-4 relative">
            {!videoError ? (
              <video
                src={feedState.currentVideo.src}
                poster={feedState.currentVideo.poster}
                width={540}
                height={960}
                autoPlay
                loop
                muted
                playsInline
                aria-label="Phone Link live video preview stream"
                onError={() => setVideoError(true)}
                className="w-full h-full object-cover rounded-lg border border-gray-800"
              />
            ) : (
              <div className="w-full h-full bg-gray-800 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-700 p-4">
                <div className="text-gray-400 text-center text-sm px-4">
                  <Radio className="w-8 h-8 mx-auto mb-2 text-blue-400 animate-pulse" aria-hidden="true" />
                  <span className="font-semibold text-gray-300">[ Phone Link Stream ]</span>
                  <br />
                  <span className="text-xs text-gray-400 mt-2 block font-mono">
                    Playing: {feedState.currentVideo.filename}
                  </span>
                  <span className="text-xs text-blue-400 mt-1 block">
                    ({feedState.currentVideo.description})
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Gemini Vision Result Card */}
        <div className="bg-[var(--background)] border border-[var(--border)] rounded-lg p-4 shadow-sm" role="region" aria-label="Gemini Vision analysis result">
          <h3 className="text-sm font-bold text-[var(--primary)] mb-2 flex items-center justify-between">
            <span>Gemini Vision Result</span>
            <span className="text-[10px] text-green-400 font-mono bg-green-500/10 px-2 py-0.5 rounded border border-green-500/20">
              Verified
            </span>
          </h3>
          <ul className="text-sm space-y-2">
            <li className="flex justify-between items-center py-0.5 border-b border-white/5">
              <span className="text-[var(--muted-foreground)]">Entity (L2)</span>
              <strong className="text-[var(--foreground)]">{feedState.visionResult.entity}</strong>
            </li>
            <li className="flex justify-between items-center py-0.5 border-b border-white/5">
              <span className="text-[var(--muted-foreground)]">Attribute (L3)</span>
              <strong className="text-[var(--foreground)]">{feedState.visionResult.attribute}</strong>
            </li>
            <li className="flex justify-between items-center py-0.5">
              <span className="text-[var(--muted-foreground)]">Action</span>
              <span className="text-green-500 font-semibold flex items-center space-x-1">
                <CheckCircle2 className="w-3.5 h-3.5 inline mr-1" aria-hidden="true" />
                {feedState.visionResult.action}
              </span>
            </li>
          </ul>
        </div>

        {/* Firebase Data Connect PostgreSQL Video Tags Panel */}
        <VideoTagsPanel
          selectedTagId={selectedTag?.id}
          onSelectTag={handleSelectTag}
        />

        {/* Action Controls */}
        <div className="pt-2 flex flex-col space-y-2">
          <button
            onClick={handlePullClick}
            disabled={isPulling}
            aria-label={isPulling ? 'Pulling media files from ADB...' : 'Trigger ADB Pull from connected device'}
            className="w-full min-h-[48px] bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800/50 text-white py-2.5 px-4 rounded-lg font-bold text-sm shadow-md transition-all flex items-center justify-center space-x-2 cursor-pointer focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
          >
            <Zap className={`w-4 h-4 ${isPulling ? 'animate-spin' : ''}`} aria-hidden="true" />
            <span>{isPulling ? 'Pulling from ADB...' : pullSuccess ? 'ADB Pull Triggered!' : 'Trigger ADB Pull'}</span>
          </button>

          {onCaptureScreen && (
            <button
              onClick={onCaptureScreen}
              aria-label="Simulate screen capture using Gemini Vision with hotkey Ctrl+Shift+T"
              className="w-full min-h-[48px] bg-gray-800 hover:bg-gray-700 text-gray-200 py-2.5 px-4 rounded-lg text-xs font-semibold transition-all border border-gray-700 flex items-center justify-center cursor-pointer focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
            >
              Simulate Screen Capture (Ctrl+Shift+T)
            </button>
          )}
        </div>
      </div>
    </section>
  );
};

export default PhoneLinkFeed;
