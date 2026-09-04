import React, { useState, useEffect } from 'react';
import { VectorDocMatch } from '../types/telemetry';
import { searchVectorHub } from '../services/api';
import { Search, Database, Copy, Check, Sparkles, AlertCircle, FileText } from 'lucide-react';

export const VectorHubPanel: React.FC = () => {
  const [query, setQuery] = useState<string>('');
  const [results, setResults] = useState<VectorDocMatch[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const performSearch = async (searchTerm: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await searchVectorHub(searchTerm);
      setResults(data.results || []);
    } catch (err: any) {
      setError('Unable to fetch vector results. Showing cached index state.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    performSearch('');
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    performSearch(query);
  };

  const handleCopy = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getScoreBadge = (score: number) => {
    const pct = Math.round(score * 100);
    if (score >= 0.9) {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-emerald-950/70 border border-emerald-600/40 text-emerald-400">
          {pct}% match
        </span>
      );
    }
    if (score >= 0.8) {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-sky-950/70 border border-sky-600/40 text-sky-400">
          {pct}% match
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-amber-950/70 border border-amber-600/40 text-amber-400">
        {pct}% match
      </span>
    );
  };

  const quickTags = ['telemetry', 'protocols', 'proxy', 'media', 'failover'];

  return (
    <section
      aria-labelledby="vector-hub-title"
      className="bg-ops-surface border border-ops-border rounded-xl p-5 shadow-md flex flex-col h-full"
    >
      <div className="flex items-center justify-between pb-3.5 border-b border-ops-border mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-violet-500/10 text-violet-400 border border-violet-500/20">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <h2 id="vector-hub-title" className="text-base font-semibold text-white">
              Vector Hub Semantic Search
            </h2>
            <p className="text-xs text-ops-muted">Cosine Embedding Query & Vector Knowledge Store</p>
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400">
          <Sparkles className="w-3.5 h-3.5 text-violet-400" />
          <span>1536-dim Embedding</span>
        </div>
      </div>

      {/* Search Input Form */}
      <form onSubmit={handleSearchSubmit} className="mb-4">
        <label htmlFor="vector-search-input" className="sr-only">
          Search Vector Store
        </label>
        <div className="relative flex items-center">
          <Search className="absolute left-3.5 w-4 h-4 text-ops-muted pointer-events-none" />
          <input
            id="vector-search-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search operational memory, protocols, ffmpeg cuts..."
            className="w-full pl-10 pr-24 py-2.5 rounded-lg bg-ops-card border border-ops-border text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-ops-accent focus:border-transparent transition-all"
          />
          <button
            type="submit"
            disabled={isLoading}
            className="absolute right-1.5 min-h-[36px] px-3.5 py-1.5 rounded-md bg-ops-accent hover:bg-ops-accentHover text-slate-900 font-semibold text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-white"
          >
            {isLoading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </form>

      {/* Preset Tags */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className="text-xs text-ops-muted">Suggested:</span>
        {quickTags.map((tag) => (
          <button
            key={tag}
            type="button"
            onClick={() => {
              setQuery(tag);
              performSearch(tag);
            }}
            className="text-xs px-2.5 py-1 rounded-md bg-ops-card hover:bg-ops-cardHover border border-ops-border text-slate-300 hover:text-white transition-colors"
          >
            #{tag}
          </button>
        ))}
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-3 p-3 rounded-lg bg-amber-950/40 border border-amber-800 text-amber-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Search Results List */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-3 max-h-[380px]">
        {results.length === 0 && !isLoading && (
          <div className="text-center py-8 text-ops-muted text-xs">
            No matching documents found. Try querying another term.
          </div>
        )}

        {results.map((doc) => (
          <div
            key={doc.id}
            className="p-3.5 rounded-lg bg-ops-card hover:bg-ops-cardHover border border-ops-border transition-colors group"
          >
            <div className="flex items-start justify-between gap-2 mb-1.5">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-sky-400 shrink-0" />
                <h3 className="text-sm font-medium text-slate-100 group-hover:text-sky-300 transition-colors">
                  {doc.title}
                </h3>
              </div>
              {getScoreBadge(doc.score)}
            </div>

            <p className="text-xs text-slate-300 mb-2 leading-relaxed">{doc.snippet}</p>

            <div className="flex items-center justify-between text-[11px] text-ops-muted pt-2 border-t border-ops-border/40">
              <div className="flex items-center gap-2">
                <span className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 font-mono text-slate-300">
                  {doc.collection}
                </span>
                <span className="font-mono text-slate-400">{doc.id}</span>
              </div>

              <button
                type="button"
                onClick={() => handleCopy(doc.id)}
                aria-label={`Copy document ID ${doc.id}`}
                className="flex items-center gap-1 text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-slate-800 transition-colors"
              >
                {copiedId === doc.id ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy ID</span>
                  </>
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
