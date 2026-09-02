import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SystemHealthHeader } from '@/components/SystemHealthHeader';

describe('SystemHealthHeader', () => {
  it('renders gateway port status, daemon heartbeat, active worker count, and refreshes', async () => {
    render(<SystemHealthHeader />);

    expect(screen.getByText('Unified Ops Hub')).toBeInTheDocument();
    expect(screen.getByText('Gateway:')).toBeInTheDocument();
    expect(screen.getByText('Port 8000')).toBeInTheDocument();
    expect(screen.getByText('4 / 4 Active')).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument(); // 0 Socket collisions
    expect(screen.getByText('SYSTEM HEALTHY')).toBeInTheDocument();

    const refreshBtn = screen.getByLabelText('Refresh health status');
    fireEvent.click(refreshBtn);
    await waitFor(() => {
      expect(screen.getByText('SYSTEM HEALTHY')).toBeInTheDocument();
    });
  });
});
