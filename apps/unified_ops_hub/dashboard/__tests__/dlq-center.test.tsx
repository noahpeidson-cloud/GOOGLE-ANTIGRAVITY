import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { DLQCenter } from '@/components/DLQCenter';

describe('DLQCenter', () => {
  it('displays quarantined incidents, handles replay triggers, and inspects payload', async () => {
    render(<DLQCenter />);

    await waitFor(() => {
      expect(screen.getByText('INC_a81f09c2')).toBeInTheDocument();
      expect(screen.getByText('ML_GRADING_FAILURE')).toBeInTheDocument();
    });

    // Inspect payload modal
    const inspectBtns = screen.getAllByTitle('Inspect Payload');
    fireEvent.click(inspectBtns[0]);
    expect(screen.getByText(/Quarantine Inspector: INC_a81f09c2/i)).toBeInTheDocument();

    // Close modal
    const closeBtn = screen.getByText('Close');
    fireEvent.click(closeBtn);

    // Replay Trigger
    const replayBtn = screen.getByTitle('Trigger Replay');
    fireEvent.click(replayBtn);
    await waitFor(() => {
      expect(screen.getByText(/Replay triggered for INC_a81f09c2/i)).toBeInTheDocument();
    });
  });
});
