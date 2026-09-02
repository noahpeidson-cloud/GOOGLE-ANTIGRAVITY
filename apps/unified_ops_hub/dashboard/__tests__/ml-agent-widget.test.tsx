import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MLAgentWidget } from '@/components/MLAgentWidget';

describe('MLAgentWidget', () => {
  it('displays K-Means cluster status (C0 Healthy, C1 Throttled, C2 Failover) and triggers lens swap', async () => {
    render(<MLAgentWidget />);

    await waitFor(() => {
      expect(screen.getByText('C0 Healthy')).toBeInTheDocument();
      expect(screen.getByText('C1 Throttled')).toBeInTheDocument();
      expect(screen.getByText('C2 Failover')).toBeInTheDocument();
    });

    // Trending sounds table
    expect(screen.getByText('Ultra Miami 2026 Mainstage ID')).toBeInTheDocument();
    expect(screen.getByText('#Ultra2026')).toBeInTheDocument();

    // Lens failover action
    const lensBtn = screen.getByRole('button', { name: /Lens:/i });
    fireEvent.click(lensBtn);
    await waitFor(() => {
      expect(screen.getByText(/Lens failover executed/i)).toBeInTheDocument();
    });
  });
});
