'use client';

import React, { useEffect, useState } from 'react';
import { CatalogAlbum, CatalogMedia, getCatalog, gradeSelectedMedia } from '@/lib/api';
import { Image as ImageIcon, Loader2, Play, CheckSquare, Square, CheckCircle2 } from 'lucide-react';

export function MediaGallery() {
  const [catalog, setCatalog] = useState<CatalogAlbum[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isGrading, setIsGrading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchCatalog();
  }, []);

  const fetchCatalog = async () => {
    setLoading(true);
    try {
      const data = await getCatalog();
      setCatalog(data);
    } catch (error) {
      console.error('Failed to fetch catalog:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSelect = (mediaId: string) => {
    const next = new Set(selectedIds);
    if (next.has(mediaId)) {
      next.delete(mediaId);
    } else {
      next.add(mediaId);
    }
    setSelectedIds(next);
  };

  const handleGradeSelected = async () => {
    if (selectedIds.size === 0) return;
    setIsGrading(true);
    setStatusMessage(null);
    try {
      const mediaIds = Array.from(selectedIds);
      await gradeSelectedMedia(mediaIds);
      setStatusMessage(`Successfully queued ${mediaIds.length} items for grading.`);
      // Refresh catalog after a short delay
      setTimeout(fetchCatalog, 1500);
      setSelectedIds(new Set());
    } catch (err) {
      console.error('Failed to grade selected media:', err);
      setStatusMessage('Error queuing grading job.');
    } finally {
      setIsGrading(false);
      setTimeout(() => setStatusMessage(null), 4000);
    }
  };

  if (loading) {
    return (
      <div className="glass-panel rounded-2xl p-6 border border-zinc-800/80 bg-zinc-900/40 flex items-center justify-center min-h-[300px]">
        <div className="flex flex-col items-center text-zinc-500 gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
          <span className="text-sm font-medium">Loading Media Catalog...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-2xl p-6 border border-zinc-800/80 bg-zinc-900/40 relative overflow-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <ImageIcon className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Media Catalog & Gallery
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-950/80 text-purple-300 border border-purple-800/50">
                Track 2 Active
              </span>
            </h2>
            <p className="text-xs text-zinc-400">View albums and dispatch assets to the grading pipeline.</p>
          </div>
        </div>

        <button
          onClick={handleGradeSelected}
          disabled={selectedIds.size === 0 || isGrading}
          className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition flex items-center gap-1.5 self-start sm:self-auto ${
            selectedIds.size === 0
              ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
              : 'bg-purple-600 hover:bg-purple-500 text-white'
          }`}
        >
          {isGrading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          Grade Selected ({selectedIds.size})
        </button>
      </div>

      {statusMessage && (
        <div className="mt-4 p-2.5 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Gallery Content */}
      <div className="mt-6 space-y-8">
        {catalog.length === 0 ? (
          <div className="text-center py-12 text-zinc-500 text-sm">No albums found in catalog.</div>
        ) : (
          catalog.map((album) => (
            <div key={album.id} className="space-y-4">
              <div className="flex items-end justify-between border-b border-zinc-800 pb-2">
                <div>
                  <h3 className="text-sm font-bold text-zinc-200">{album.title}</h3>
                  {album.description && <p className="text-xs text-zinc-500 mt-1">{album.description}</p>}
                </div>
                <div className="text-xs text-zinc-500 font-mono">{album.media_count} items</div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                {album.media && album.media.length > 0 ? (
                  album.media.map((item) => (
                    <MediaCard
                      key={item.id}
                      item={item}
                      isSelected={selectedIds.has(item.id)}
                      onToggle={() => handleToggleSelect(item.id)}
                    />
                  ))
                ) : (
                  <div className="col-span-full py-4 text-xs text-zinc-600 italic">No media items in this album.</div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function MediaCard({ item, isSelected, onToggle }: { item: CatalogMedia; isSelected: boolean; onToggle: () => void }) {
  return (
    <div
      onClick={onToggle}
      className={`group relative aspect-[9/16] bg-zinc-950 rounded-xl overflow-hidden cursor-pointer border transition-colors ${
        isSelected ? 'border-purple-500 shadow-[0_0_15px_rgba(168,85,247,0.2)]' : 'border-zinc-800 hover:border-zinc-700'
      }`}
    >
      {/* Selection Checkbox (Top Left) */}
      <div className="absolute top-2 left-2 z-20 drop-shadow-md">
        {isSelected ? (
          <CheckSquare className="w-5 h-5 text-purple-400 bg-black/50 rounded" />
        ) : (
          <Square className="w-5 h-5 text-zinc-400 bg-black/30 rounded opacity-0 group-hover:opacity-100 transition-opacity" />
        )}
      </div>

      {/* Badges (Top Right) */}
      <div className="absolute top-2 right-2 z-20 flex flex-col items-end gap-1">
        <span
          className={`text-[9px] font-bold px-1.5 py-0.5 rounded shadow-sm ${
            item.grading_status === 'GRADED'
              ? 'bg-emerald-500/80 text-emerald-50'
              : item.grading_status === 'QUEUED'
              ? 'bg-amber-500/80 text-amber-50'
              : 'bg-zinc-800/80 text-zinc-300'
          }`}
        >
          {item.grading_status}
        </span>
        {item.grading_verdict && (
          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded shadow-sm bg-purple-600/80 text-purple-50">
            {item.grading_verdict}
          </span>
        )}
      </div>

      {/* Image Preview / Placeholder */}
      <div className="absolute inset-0 z-0">
        {item.proxy_url ? (
          <video
            src={`${process.env.NEXT_PUBLIC_GATEWAY_URL || 'http://127.0.0.1:8000'}${item.proxy_url}`}
            className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity"
            muted
            loop
            playsInline
            onMouseEnter={(e) => (e.target as HTMLVideoElement).play().catch(() => {})}
            onMouseLeave={(e) => {
              const v = e.target as HTMLVideoElement;
              v.pause();
              v.currentTime = 0;
            }}
          />
        ) : (
          <div className="w-full h-full bg-zinc-900 flex items-center justify-center">
            <ImageIcon className="w-8 h-8 text-zinc-800" />
          </div>
        )}
      </div>

      {/* Bottom Gradient & Info */}
      <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent pt-12 pb-3 px-3 z-10 pointer-events-none">
        <p className="text-xs font-semibold text-white truncate drop-shadow-sm">{item.filename}</p>
        <div className="flex items-center justify-between mt-1">
          <span className="text-[10px] text-zinc-400 font-mono">{item.resolution}</span>
          <span className="text-[10px] text-zinc-400 font-mono">{item.duration.toFixed(1)}s</span>
        </div>
      </div>
      
      {/* Selected Overlay */}
      {isSelected && (
        <div className="absolute inset-0 bg-purple-500/10 z-10 pointer-events-none"></div>
      )}
    </div>
  );
}
