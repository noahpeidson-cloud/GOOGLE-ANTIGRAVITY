import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Unified Ops Hub component crashed:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 rounded-xl bg-rose-950/30 border border-rose-800 text-rose-200">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
            <h3 className="font-semibold text-sm">
              {this.props.fallbackTitle || 'Component Error'}
            </h3>
          </div>
          <p className="text-xs text-rose-300 mb-4 leading-relaxed">
            {this.state.error?.message || 'An unexpected rendering error occurred in this module.'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false })}
            className="min-h-[44px] px-3 py-1.5 rounded-lg bg-rose-800 hover:bg-rose-700 text-white text-xs font-medium flex items-center gap-2"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Retry Component
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
