import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MediaIngestionWidget } from '@/components/MediaIngestionWidget';

describe('MediaIngestionWidget', () => {
  it('renders ADB Wi-Fi live status, PySpark 5-score viral radar, and triggers pipeline run', async () => {
    render(<MediaIngestionWidget />);

    // Ingestion status
    expect(screen.getByText(/192.168.1.150/i)).toBeInTheDocument();
    expect(screen.getByText('LOCKED / ACTIVE')).toBeInTheDocument();
    expect(screen.getByText('12 Clips (4K HDR)')).toBeInTheDocument();

    // 5-Score radar labels
    expect(screen.getByText(/HRV \(Hook Retention\)/i)).toBeInTheDocument();
    expect(screen.getByText(/DPAW \(Dynamic Pacing\)/i)).toBeInTheDocument();
    expect(screen.getByText(/ADR_SFD \(Speech Freq\)/i)).toBeInTheDocument();
    expect(screen.getByText(/CKE_MVE \(Visual Entropy\)/i)).toBeInTheDocument();
    expect(screen.getByText(/LTSS \(Shareability\)/i)).toBeInTheDocument();

    // EVPI Score & Verdict
    expect(screen.getByText('VIRAL_READY')).toBeInTheDocument();

    // Trigger pipeline run
    const triggerBtn = screen.getByText('Trigger Pipeline Run');
    fireEvent.click(triggerBtn);
    expect(screen.getByText(/Triggering ADB Wi-Fi 01_RAW Ingestion/i)).toBeInTheDocument();
  });
});
