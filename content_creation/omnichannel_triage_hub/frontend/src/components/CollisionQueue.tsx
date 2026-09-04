import React, { useState } from 'react';
import { AlertTriangle, CheckCircle, Trash2, Undo2 } from 'lucide-react';
import { CollisionItem } from '../types';

interface CollisionQueueProps {
  items?: CollisionItem[];
  onResolve?: (id: string, choice: 'adb' | 'takeout') => void;
}

const DEFAULT_COLLISION_ITEMS: CollisionItem[] = [
  {
    id: 'col-20260819-213606',
    filename: '20260819_213606.mp4',
    timestamp: 'Aug 19, 2026 • 9:36 PM EST',
    conflictType: 'Resolution Mismatch',
    adbSource: {
      title: 'Local ADB Pull',
      resolution: '4K',
      resolutionSubtext: '2160p',
      sourcePath: 'Source: /sdcard/DCIM/Camera',
      size: '538 MB',
      badgeColor: 'green',
    },
    takeoutSource: {
      title: 'Takeout Cloud',
      resolution: '1080p',
      resolutionSubtext: 'Compressed',
      sourcePath: 'Source: Takeout/Google Photos',
      size: '42 MB',
      badgeColor: 'red',
    },
    resolved: false,
  },
];

export const CollisionQueue: React.FC<CollisionQueueProps> = ({
  items = DEFAULT_COLLISION_ITEMS,
  onResolve,
}) => {
  const [collisionList, setCollisionList] = useState<CollisionItem[]>(items);

  const handleResolveChoice = (id: string, choice: 'adb' | 'takeout') => {
    setCollisionList((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, resolved: true, resolutionChoice: choice }
          : item
      )
    );
    if (onResolve) {
      onResolve(id, choice);
    }
  };

  const handleUndo = (id: string) => {
    setCollisionList((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, resolved: false, resolutionChoice: undefined }
          : item
      )
    );
  };

  return (
    <section
      role="region"
      aria-labelledby="collision-queue-heading"
      className="col-span-8 flex flex-col space-y-8 overflow-hidden"
    >
      {/* Deduplication Arena */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 shadow-sm flex flex-col flex-1 overflow-hidden">
        <div className="mb-6">
          <h2 id="collision-queue-heading" className="font-bold text-xl mb-2 text-[var(--foreground)]">
            Collision Resolution Queue
          </h2>
          <p className="text-sm text-[var(--muted-foreground)]">
            <strong className="text-[var(--foreground)]">Why are you seeing this?</strong> The script found photos in your Samsung pull and Google Takeout that share the exact same UTC-adjusted timestamp (within 2 seconds). You must decide which version to keep.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto space-y-6 pr-4">
          {collisionList.map((item) => (
            <div
              key={item.id}
              className={`border border-[var(--border)] rounded-xl p-5 bg-[var(--background)] transition-all ${
                item.resolved ? 'opacity-60 bg-zinc-900/50' : ''
              }`}
            >
              {/* Item Top Bar */}
              <div className="flex justify-between items-center mb-4 border-b border-[var(--border)] pb-4">
                <div>
                  <h3 className="font-mono text-sm bg-gray-800 text-gray-200 px-2 py-1 rounded inline-block">
                    {item.filename}
                  </h3>
                  <span className="text-xs text-[var(--muted-foreground)] ml-2">
                    Taken: {item.timestamp}
                  </span>
                </div>
                {item.resolved ? (
                  <div
                    role="status"
                    aria-label={`Collision resolved for ${item.filename}`}
                    className="flex items-center text-xs text-green-400 font-bold bg-green-500/10 px-3 py-1 rounded-full border border-green-500/20"
                  >
                    <CheckCircle className="w-4 h-4 mr-1 text-green-400" aria-hidden="true" />
                    Resolved ({item.resolutionChoice === 'adb' ? 'Kept 4K ADB' : 'Kept Takeout'})
                  </div>
                ) : (
                  <div
                    role="status"
                    aria-label={`Collision conflict: ${item.conflictType}`}
                    className="flex items-center text-xs text-amber-500 font-bold bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20"
                  >
                    <AlertTriangle className="w-4 h-4 mr-1" aria-hidden="true" />
                    {item.conflictType}
                  </div>
                )}
              </div>

              {/* Side-by-side comparison grid */}
              <div className="grid grid-cols-2 gap-6 mb-4">
                {/* Left side: Samsung ADB */}
                <div
                  className={`border-2 border-green-500/40 rounded-lg p-4 bg-green-900/10 relative transition-all ${
                    item.resolved && item.resolutionChoice !== 'adb'
                      ? 'opacity-40 grayscale'
                      : ''
                  }`}
                >
                  <div className="absolute -top-3 left-4 bg-green-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded shadow">
                    {item.adbSource.title}
                  </div>
                  <div className="flex justify-between items-end">
                    <div>
                      <span className="block text-2xl font-black text-green-400 mb-1">
                        {item.adbSource.resolution}{' '}
                        <span className="text-sm font-normal text-green-500/70">
                          {item.adbSource.resolutionSubtext}
                        </span>
                      </span>
                      <span className="text-xs text-gray-400">
                        {item.adbSource.sourcePath}
                      </span>
                    </div>
                    <span className="text-xl font-bold text-gray-200">
                      {item.adbSource.size}
                    </span>
                  </div>
                </div>

                {/* Right side: Google Takeout */}
                <div
                  className={`border-2 border-red-500/40 rounded-lg p-4 bg-red-900/10 relative transition-opacity ${
                    item.resolved && item.resolutionChoice !== 'takeout'
                      ? 'opacity-30 grayscale'
                      : 'opacity-75 hover:opacity-100'
                  }`}
                >
                  <div className="absolute -top-3 left-4 bg-red-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded shadow">
                    {item.takeoutSource.title}
                  </div>
                  <div className="flex justify-between items-end">
                    <div>
                      <span className="block text-2xl font-black text-red-400 mb-1">
                        {item.takeoutSource.resolution}{' '}
                        <span className="text-sm font-normal text-red-500/70">
                          {item.takeoutSource.resolutionSubtext}
                        </span>
                      </span>
                      <span className="text-xs text-gray-400">
                        {item.takeoutSource.sourcePath}
                      </span>
                    </div>
                    <span className="text-xl font-bold text-gray-200">
                      {item.takeoutSource.size}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex space-x-3 mt-5">
                {!item.resolved ? (
                  <>
                    <button
                      onClick={() => handleResolveChoice(item.id, 'adb')}
                      aria-label={`Keep 4K ADB version for ${item.filename} and auto-trash Takeout copy`}
                      className="flex-1 min-h-[48px] bg-green-600 hover:bg-green-500 text-white py-3 px-4 rounded-lg font-bold shadow-lg transition-all transform hover:scale-[1.02] flex items-center justify-center space-x-2 cursor-pointer focus-visible:ring-2 focus-visible:ring-green-400 focus-visible:outline-none"
                    >
                      <CheckCircle className="w-5 h-5" aria-hidden="true" />
                      <span>Keep 4K ADB Version (Auto-Trash Takeout)</span>
                    </button>
                    <button
                      onClick={() => handleResolveChoice(item.id, 'takeout')}
                      aria-label={`Keep compressed Takeout copy for ${item.filename} instead`}
                      className="px-4 py-3 min-h-[48px] min-w-[48px] bg-gray-800 hover:bg-red-900/40 text-gray-400 hover:text-red-300 rounded-lg text-xs font-semibold border border-gray-700 transition-all flex items-center justify-center space-x-1.5 cursor-pointer focus-visible:ring-2 focus-visible:ring-red-400 focus-visible:outline-none"
                      title="Keep compressed Takeout copy instead"
                    >
                      <Trash2 className="w-4 h-4" aria-hidden="true" />
                      <span>Keep Takeout</span>
                    </button>
                  </>
                ) : (
                  <div className="flex-1 min-h-[48px] flex items-center justify-between bg-zinc-800/80 px-4 py-2.5 rounded-lg border border-zinc-700">
                    <span className="text-sm text-green-400 font-medium">
                      ✓ Collision resolved. Trash job queued for discarded copy.
                    </span>
                    <button
                      onClick={() => handleUndo(item.id)}
                      aria-label={`Undo collision resolution for ${item.filename}`}
                      className="min-h-[48px] min-w-[48px] px-3 py-2 text-xs text-gray-400 hover:text-white flex items-center justify-center space-x-1 underline cursor-pointer focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none rounded"
                    >
                      <Undo2 className="w-3.5 h-3.5" aria-hidden="true" />
                      <span>Undo</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default CollisionQueue;
