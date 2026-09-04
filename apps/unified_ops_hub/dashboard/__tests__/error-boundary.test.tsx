import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ErrorBoundary } from '@/components/ErrorBoundary';

const BadComponent = () => {
  throw new Error('Simulated Crash inside widget');
};

const GoodComponent = () => <div>All systems operational</div>;

describe('ErrorBoundary', () => {
  it('catches render crashes and displays recovery UI without taking down application', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary fallbackTitle="Test Widget Failure">
        <BadComponent />
      </ErrorBoundary>
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Test Widget Failure')).toBeInTheDocument();
    expect(screen.getByText('Simulated Crash inside widget')).toBeInTheDocument();
    expect(screen.getByText('Reset & Recover')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('renders children normally when no error occurs', () => {
    render(
      <ErrorBoundary>
        <GoodComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText('All systems operational')).toBeInTheDocument();
  });
});
