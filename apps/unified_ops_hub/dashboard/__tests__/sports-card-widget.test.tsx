import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SportsCardWidget } from '@/components/SportsCardWidget';

describe('SportsCardWidget', () => {
  it('renders portfolio statistics, active inventory, and handles CSV export and card capture', async () => {
    render(<SportsCardWidget />);

    // Titles & badges
    expect(screen.getByText('Sports Card Ecosystem Hub')).toBeInTheDocument();
    expect(screen.getByText('Track 1 Active')).toBeInTheDocument();

    // Cards list
    await waitFor(() => {
      expect(screen.getByText('Victor Wembanyama')).toBeInTheDocument();
    });

    // CSV Export trigger
    const exportBtn = screen.getByText('CSV Export');
    fireEvent.click(exportBtn);
    expect(screen.getByText(/Exported 1,420 records to BigQuery ML/i)).toBeInTheDocument();

    // Add New Card modal toggle
    const addBtn = screen.getByText('Add New Card');
    fireEvent.click(addBtn);
    expect(screen.getByPlaceholderText(/Player Name/i)).toBeInTheDocument();
  });
});
