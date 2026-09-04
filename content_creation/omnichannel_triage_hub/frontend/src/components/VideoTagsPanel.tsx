import React, { useState } from 'react';
import {
  Database,
  RefreshCw,
  Tag,
  Film,
  Sparkles,
  CheckCircle,
  Plus,
  Server,
  Cloud,
} from 'lucide-react';
import { useVideoTags, VideoTag, CreateVideoTagVariables } from '../lib/dataconnect';

interface VideoTagsPanelProps {
  onSelectTag?: (tag: VideoTag) => void;
  selectedTagId?: string | null;
}

export const VideoTagsPanel: React.FC<VideoTagsPanelProps> = ({
  onSelectTag,
  selectedTagId,
}) => {
  const { tags, loading, error, isOfflineFallback, refetch, addTag } = useVideoTags();
  const [isAdding, setIsAdding] = useState(false);
  const [newEntity, setNewEntity] = useState('');
  const [newDomain, setNewDomain] = useState('EDM_FESTIVALS');
  const [newFilename, setNewFilename] = useState('');
  const [newFeature, setNewFeature] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCreateTag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFilename || !newEntity) return;

    setIsSubmitting(true);
    const newTagVars: CreateVideoTagVariables = {
      filename: newFilename.endsWith('.mp4') ? newFilename : `${newFilename}.mp4`,
      filepath: `/sdcard/DCIM/Camera/${newFilename}`,
      domain: newDomain,
      entity: newEntity,
      viralFeatures: {
        visualHooks: newFeature ? [newFeature] : ['Auto-Analyzed Hook'],
        energyLevel: 'High',
      },
      technical: {
        resolution: '3840x2160',
        fps: 60,
        codec: 'h264',
        audioClipping: false,
      },
    };

    await addTag(newTagVars);
    setNewFilename('');
    setNewEntity('');
    setNewFeature('');
    setIsAdding(false);
    setIsSubmitting(false);
  };

  return (
    <div
      role="region"
      aria-label="Firebase Data Connect Video Tags"
      className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4 flex flex-col space-y-3"
    >
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-3">
        <div className="flex items-center space-x-2">
          <Database className="w-4 h-4 text-blue-400" aria-hidden="true" />
          <h3 className="font-bold text-sm text-[var(--foreground)]">
            Firebase Data Connect
          </h3>
          <span
            role="status"
            aria-label={isOfflineFallback ? 'Status: Local Fallback' : 'Status: PostgreSQL Cloud SQL Connected'}
            className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/20 font-mono flex items-center"
          >
            {isOfflineFallback ? (
              <>
                <Server className="w-3 h-3 mr-1 text-amber-400" aria-hidden="true" />
                Local / Fallback
              </>
            ) : (
              <>
                <Cloud className="w-3 h-3 mr-1 text-green-400" aria-hidden="true" />
                PostgreSQL • Cloud SQL
              </>
            )}
          </span>
        </div>

        <div className="flex items-center space-x-1">
          <button
            onClick={() => refetch()}
            disabled={loading}
            aria-label="Refetch GraphQL video tags from Data Connect"
            title="Refetch GraphQL video tags"
            className="min-h-[48px] min-w-[48px] p-2 rounded-md hover:bg-white/10 text-gray-400 hover:text-white transition-colors cursor-pointer flex items-center justify-center focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} aria-hidden="true" />
          </button>
          <button
            onClick={() => setIsAdding(!isAdding)}
            aria-label={isAdding ? 'Close tag video form' : 'Open tag video form'}
            className="min-h-[48px] text-xs bg-blue-600/80 hover:bg-blue-600 text-white px-3 py-2 rounded-md flex items-center space-x-1.5 font-medium transition-all cursor-pointer focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
          >
            <Plus className="w-4 h-4" aria-hidden="true" />
            <span>Tag Video</span>
          </button>
        </div>
      </div>

      {/* Error alert if any */}
      {error && !isOfflineFallback && (
        <div role="alert" className="bg-red-500/10 border border-red-500/20 rounded p-2 text-xs text-red-400">
          Data Connect query error: {error.message}
        </div>
      )}

      {/* New Tag Form */}
      {isAdding && (
        <form
          onSubmit={handleCreateTag}
          aria-label="Add new video tag form"
          className="bg-black/30 border border-blue-500/30 rounded-lg p-3 space-y-2 text-xs"
        >
          <div className="font-semibold text-blue-300 flex items-center space-x-1">
            <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Create Data Connect Video Tag (GraphQL Mutation)</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="tag-filename" className="block text-gray-400 mb-1 font-medium">
                Filename
              </label>
              <input
                id="tag-filename"
                type="text"
                placeholder="20260822_120000.mp4"
                value={newFilename}
                onChange={(e) => setNewFilename(e.target.value)}
                required
                aria-required="true"
                className="w-full min-h-[48px] bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-400"
              />
            </div>
            <div>
              <label htmlFor="tag-domain" className="block text-gray-400 mb-1 font-medium">
                Domain
              </label>
              <select
                id="tag-domain"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                className="w-full min-h-[48px] bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                <option value="EDM_FESTIVALS">EDM_FESTIVALS</option>
                <option value="SPORTS_CARDS">SPORTS_CARDS</option>
                <option value="TRAVEL_AND_LIFE">TRAVEL_AND_LIFE</option>
              </select>
            </div>
          </div>
          <div>
            <label htmlFor="tag-entity" className="block text-gray-400 mb-1 font-medium">
              Entity / Subject
            </label>
            <input
              id="tag-entity"
              type="text"
              placeholder="e.g. Illenium (Ascend 2026)"
              value={newEntity}
              onChange={(e) => setNewEntity(e.target.value)}
              required
              aria-required="true"
              className="w-full min-h-[48px] bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-400"
            />
          </div>
          <div>
            <label htmlFor="tag-feature" className="block text-gray-400 mb-1 font-medium">
              Viral Feature
            </label>
            <input
              id="tag-feature"
              type="text"
              placeholder="e.g. Pyro Drop, Triple Laser Array"
              value={newFeature}
              onChange={(e) => setNewFeature(e.target.value)}
              className="w-full min-h-[48px] bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-400"
            />
          </div>
          <div className="flex justify-end space-x-2 pt-1">
            <button
              type="button"
              onClick={() => setIsAdding(false)}
              aria-label="Cancel creating video tag"
              className="min-h-[48px] px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-gray-300 rounded cursor-pointer focus-visible:ring-2 focus-visible:ring-zinc-400 focus-visible:outline-none"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              aria-label="Save video tag to Data Connect"
              className="min-h-[48px] px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-medium disabled:opacity-50 cursor-pointer focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
            >
              {isSubmitting ? 'Syncing...' : 'Save Tag'}
            </button>
          </div>
        </form>
      )}

      {/* Video Tags List */}
      <div

        aria-label="Available video tags"
        className="space-y-2 max-h-56 overflow-y-auto pr-1"
      >
        {tags.length === 0 ? (
          <div className="text-center py-4 text-xs text-gray-500">
            No video tags found in Data Connect database.
          </div>
        ) : (
          tags.map((tag) => {
            const isSelected = selectedTagId === tag.id;
            const features = Array.isArray(tag.viralFeatures)
              ? tag.viralFeatures
              : typeof tag.viralFeatures === 'object' && tag.viralFeatures !== null && 'visualHooks' in tag.viralFeatures
              ? (tag.viralFeatures as { visualHooks: string[] }).visualHooks
              : [];

            return (
              <div
                key={tag.id}
                role="button"
                tabIndex={0}
                aria-pressed={isSelected}
                aria-label={`Select tag for ${tag.filename} (${tag.entity})`}
                onClick={() => onSelectTag && onSelectTag(tag)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    if (onSelectTag) onSelectTag(tag);
                  }
                }}
                className={`min-h-[48px] p-3 rounded-lg border transition-all cursor-pointer focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none ${
                  isSelected
                    ? 'border-blue-500 bg-blue-950/30'
                    : 'border-white/5 bg-black/20 hover:border-white/20 hover:bg-white/5'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Film className="w-4 h-4 text-blue-400 flex-shrink-0" aria-hidden="true" />
                    <span className="font-mono text-xs font-semibold text-gray-200 truncate max-w-[150px]">
                      {tag.filename}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                    {tag.domain}
                  </span>
                </div>

                <div className="mt-1 flex items-center justify-between text-xs">
                  <span className="text-gray-300 font-medium">{tag.entity}</span>
                  <span className="text-[10px] text-green-400 flex items-center">
                    <CheckCircle className="w-3 h-3 mr-1 inline" aria-hidden="true" />
                    PostgreSQL
                  </span>
                </div>

                {features.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {features.map((feat, idx) => (
                      <span
                        key={idx}
                        className="text-[9px] bg-purple-500/10 text-purple-300 border border-purple-500/20 px-1.5 py-0.5 rounded-full flex items-center"
                      >
                        <Tag className="w-2.5 h-2.5 mr-0.5 inline" aria-hidden="true" />
                        {String(feat)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default VideoTagsPanel;
