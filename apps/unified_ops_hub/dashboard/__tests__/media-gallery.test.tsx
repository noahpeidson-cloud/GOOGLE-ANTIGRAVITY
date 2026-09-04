import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MediaGallery } from '@/components/MediaGallery';

describe('MediaGallery', () => {
  it('renders catalog albums and media, and triggers grade selected', async () => {
    render(<MediaGallery />);

    // Wait for the mock catalog to load
    await waitFor(() => {
      expect(screen.getByText('Ultra Miami 2026 Mainstage')).toBeInTheDocument();
    });

    // Check if album details are rendered
    expect(screen.getByText('4K 60FPS multi-cam raw captures from Mainstage Day 1')).toBeInTheDocument();
    expect(screen.getByText('clip_ultra_drop_4k_01.mp4')).toBeInTheDocument();

    // Check if Grade Selected button is disabled initially
    const gradeBtn = screen.getByRole('button', { name: /Grade Selected/i });
    expect(gradeBtn).toBeDisabled();

    // Click the video card to select it
    const mediaCard = screen.getByText('clip_ultra_drop_4k_01.mp4').closest('div.group');
    if (mediaCard) {
      fireEvent.click(mediaCard);
    }

    // Now Grade Selected should be enabled
    expect(gradeBtn).not.toBeDisabled();
    expect(gradeBtn).toHaveTextContent('Grade Selected (1)');

    // Click Grade Selected
    fireEvent.click(gradeBtn);

    // Wait for success message
    await waitFor(() => {
      expect(screen.getByText('Successfully queued 1 items for grading.')).toBeInTheDocument();
    });
  });
});
