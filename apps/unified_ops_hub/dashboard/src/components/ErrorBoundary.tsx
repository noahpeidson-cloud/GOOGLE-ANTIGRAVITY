'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertOctagon, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary] Uncaught component error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          className="glass-panel p-6 rounded-2xl border border-rose-500/30 bg-rose-950/20 text-rose-200 my-4 shadow-xl"
        >
          <div className="flex items-center gap-3">
            <div className="p-3 bg-rose-500/20 rounded-xl text-rose-400">
              <AlertOctagon className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold tracking-tight text-white">
                {this.props.fallbackTitle || 'Component Execution Failure'}
              </h3>
              <p className="text-sm text-rose-300 mt-1">
                {this.state.error?.message || 'An unexpected rendering error occurred. Safe fallback engaged.'}
              </p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-rose-500/20 flex justify-end">
            <button
              onClick={this.handleReset}
              className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-sm font-medium transition flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Reset & Recover
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
