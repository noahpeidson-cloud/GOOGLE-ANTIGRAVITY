import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React, { useState } from 'react';
import { ErrorBoundary } from '@/components/ErrorBoundary';

const FaultyWidget = ({ shouldThrow = true }: { shouldThrow?: boolean }) => {
  if (shouldThrow) {
    throw new Error('Fatal: Null pointer exception in WebAssembly Video Transcoder');
  }
  return <div data-testid="recovered-content">Widget Recovered and Running Normally</div>;
};

const HealthySiblingWidget = () => (
  <div data-testid="healthy-sibling">Sibling Widget: Database ETL Pipeline Active</div>
);

const FlakyWidget = () => {
  const [fail, setFail] = useState(true);
  if (fail) {
    return (
      <div>
        <button onClick={() => setFail(false)}>Fix Internal State</button>
        {(() => {
          throw new Error('Flaky component runtime crash');
        })()}
      </div>
    );
  }
  return <div data-testid="fixed-widget">Flaky Widget Restored</div>;
};

describe('Adversarial ErrorBoundary Recovery & Crash Isolation Suite', () => {
  it('isolates crashing component and prevents entire dashboard DOM tree failure', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <div className="dashboard-grid">
        <ErrorBoundary fallbackTitle="Media Pipeline Crashed">
          <FaultyWidget shouldThrow={true} />
        </ErrorBoundary>

        <ErrorBoundary fallbackTitle="Database Service Crashed">
          <HealthySiblingWidget />
        </ErrorBoundary>
      </div>
    );

    // Faulty widget is replaced by isolated ErrorBoundary fallback
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Media Pipeline Crashed')).toBeInTheDocument();
    expect(screen.getByText(/Fatal: Null pointer exception in WebAssembly Video Transcoder/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reset & Recover/i })).toBeInTheDocument();

    // Sibling widget remains completely mounted and functional in the DOM tree
    expect(screen.getByTestId('healthy-sibling')).toBeInTheDocument();
    expect(screen.getByText(/Sibling Widget: Database ETL Pipeline Active/i)).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('handles recovery cycle when user clicks Reset & Recover', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    let throwError = true;
    const StatefulFaulty = () => {
      if (throwError) {
        throw new Error('Temporary API timeout crash');
      }
      return <div data-testid="restored-view">Restored After Recovery Click</div>;
    };

    const { rerender } = render(
      <ErrorBoundary fallbackTitle="Temporary Service Drop">
        <StatefulFaulty />
      </ErrorBoundary>
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Temporary Service Drop')).toBeInTheDocument();

    // Now fix the underlying condition
    throwError = false;

    // User clicks Reset & Recover
    const resetBtn = screen.getByRole('button', { name: /Reset & Recover/i });
    fireEvent.click(resetBtn);

    // Component is recovered
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByTestId('restored-view')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('renders fallback with default title when fallbackTitle prop is omitted', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <FaultyWidget shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Component Execution Failure')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reset & Recover/i })).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('supports multiple independent error boundaries in parallel', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <div>
        <ErrorBoundary fallbackTitle="Widget 1 Error">
          <FaultyWidget shouldThrow={true} />
        </ErrorBoundary>
        <ErrorBoundary fallbackTitle="Widget 2 Error">
          <FaultyWidget shouldThrow={true} />
        </ErrorBoundary>
      </div>
    );

    const alerts = screen.getAllByRole('alert');
    expect(alerts.length).toBe(2);
    expect(screen.getByText('Widget 1 Error')).toBeInTheDocument();
    expect(screen.getByText('Widget 2 Error')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
