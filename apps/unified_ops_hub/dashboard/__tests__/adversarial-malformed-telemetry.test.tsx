import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as api from '@/lib/api';
import { SystemHealthHeader } from '@/components/SystemHealthHeader';
import { SportsCardWidget } from '@/components/SportsCardWidget';
import { MediaIngestionWidget } from '@/components/MediaIngestionWidget';
import { MLAgentWidget } from '@/components/MLAgentWidget';
import { DLQCenter } from '@/components/DLQCenter';
import CommandCenterDashboard from '@/app/page';

describe('Adversarial Malformed Telemetry & Component Crash Resistance Suite', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('1. SystemHealthHeader with Malformed Telemetry', () => {
    it('renders safely when getSystemHealth returns DEGRADED status and unexpected values', async () => {
      vi.spyOn(api, 'getSystemHealth').mockResolvedValue({
        status: 'DEGRADED',
        version: '0.9.0-rc1',
        uptime_seconds: 120.4,
        ports: {
          '8000': { port: 8000, status: 'DEGRADED', service: 'gateway' },
        },
        dlq_stats: { total: 5, quarantined: 2, replaying: 1, resolved: 2, poison_pill: 0 },
        services: { gateway: 'DEGRADED' },
      });

      render(<SystemHealthHeader />);

      await waitFor(() => {
        expect(screen.getByText('SYSTEM DEGRADED')).toBeInTheDocument();
        expect(screen.getByText(/Uptime: 120s/i)).toBeInTheDocument();
      });
    });

    it('recovers gracefully when getSystemHealth throws an unhandled rejection', async () => {
      vi.spyOn(api, 'getSystemHealth').mockRejectedValue(new Error('Fatal Gateway Socket Drop'));
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      render(<SystemHealthHeader />);

      // Component should remain mounted with default/initial state without crashing the tree
      expect(screen.getByText('Unified Ops Hub')).toBeInTheDocument();
      consoleSpy.mockRestore();
    });
  });

  describe('2. SportsCardWidget with Boundary & Edge Inputs', () => {
    it('renders with zero investment and zero cards without division by zero errors', async () => {
      vi.spyOn(api, 'getSportsPortfolio').mockResolvedValue({ total: 0, cards: [] });
      vi.spyOn(api, 'getSportsStats').mockResolvedValue({
        total_cards: 0,
        total_investment: 0,
        total_estimated_value: 0,
      });

      render(<SportsCardWidget />);

      await waitFor(() => {
        expect(screen.getAllByText('$0.00').length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText('+0.0%')).toBeInTheDocument();
      });
    });

    it('handles card capture with special characters, large numbers, and boundary values', async () => {
      const captureSpy = vi.spyOn(api, 'captureSportsCard').mockResolvedValue({
        id: 'CARD_SPECIAL_01',
        player: '<script>alert("xss")</script> Kobe Bryant',
        year: '1996',
        set_name: 'Topps Chrome Refractor #138',
        card_number: '138',
        category: 'Basketball',
        condition: 'BGS 10 Pristine',
        investment: 50000.0,
        estimated_value: 125000.0,
        ai_status: 'CLEARED',
        captured_at: Date.now(),
      });

      render(<SportsCardWidget />);

      // Open Modal
      const addBtn = screen.getByText('Add New Card');
      fireEvent.click(addBtn);

      const playerInput = screen.getByPlaceholderText(/Player Name/i);
      const setInput = screen.getByPlaceholderText(/Set Name/i);
      const valInput = screen.getByPlaceholderText(/Est. Value/i);

      fireEvent.change(playerInput, { target: { value: '<script>alert("xss")</script> Kobe Bryant' } });
      fireEvent.change(setInput, { target: { value: 'Topps Chrome Refractor #138' } });
      fireEvent.change(valInput, { target: { value: '125000' } });

      const submitBtn = screen.getByText('Save & Clear AI Status');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(captureSpy).toHaveBeenCalled();
      });
    });

    it('handles CardLadder sync trigger without crashing', async () => {
      render(<SportsCardWidget />);
      const syncBtn = screen.getByText(/Sync CardLadder/i);

      fireEvent.click(syncBtn);
      expect(screen.getByText(/Syncing\.\.\./i)).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText(/Sync CardLadder/i)).toBeInTheDocument();
      }, { timeout: 2000 });
    });
  });

  describe('3. MediaIngestionWidget with Boundary Scores & Aspect Ratios', () => {
    it('handles boundary score calculations (0s and 100s)', async () => {
      render(<MediaIngestionWidget />);

      const recalcBtn = screen.getByRole('button', { name: /Recalculate EVPI/i });
      fireEvent.click(recalcBtn);

      await waitFor(() => {
        expect(screen.getByText(/EVPI Score:/i)).toBeInTheDocument();
      });

      // Switch to landscape 16:9
      const landscapeRadio = screen.getByLabelText(/16:9 \(Landscape -50% EVPI\)/i);
      fireEvent.click(landscapeRadio);

      fireEvent.click(recalcBtn);
      await waitFor(() => {
        expect(screen.getByText(/EVPI Score:/i)).toBeInTheDocument();
      });
    });
  });

  describe('4. MLAgentWidget with Inverted Telemetry & Failover', () => {
    it('renders with 100% failover cluster without UI distortion', async () => {
      vi.spyOn(api, 'getMLTelemetry').mockResolvedValue({
        platform: 'tiktok',
        active_lens: 'web_a11y_tree',
        poll_interval_sec: 1800,
        retry_backoff_base_sec: 8.0,
        clusters: {
          c0_healthy: 0,
          c1_throttled: 0,
          c2_failover: 100,
        },
        entropy: 0.89,
        trending_sounds: [],
      });

      render(<MLAgentWidget />);

      await waitFor(() => {
        expect(screen.getByText('100%')).toBeInTheDocument();
        expect(screen.getAllByText('0%').length).toBe(2);
        expect(screen.getByText(/Lens: web_a11y_tree/i)).toBeInTheDocument();
      });
    });

    it('handles lens failover button click with animated feedback', async () => {
      vi.spyOn(api, 'triggerLensFailover').mockResolvedValue({
        success: true,
        active_lens: 'web_a11y_tree',
        reason: 'Manual failover trigger',
      });

      render(<MLAgentWidget />);

      const lensBtn = screen.getByRole('button', { name: /Lens:/i });
      fireEvent.click(lensBtn);

      await waitFor(() => {
        expect(screen.getByText(/Lens failover executed: Swapped to web_a11y_tree/i)).toBeInTheDocument();
      });
    });
  });

  describe('5. DLQCenter with Empty & Corrupted Incidents', () => {
    it('handles empty DLQ state gracefully', async () => {
      vi.spyOn(api, 'getDLQIncidents').mockResolvedValue({ incidents: [], count: 0 });
      vi.spyOn(api, 'getDLQStats').mockResolvedValue({
        total: 0,
        quarantined: 0,
        replaying: 0,
        resolved: 0,
        poison_pill: 0,
        categories: {},
      });

      render(<DLQCenter />);

      await waitFor(() => {
        expect(screen.getByText('Dead Letter Queue & Incident Isolation Center')).toBeInTheDocument();
      });
    });

    it('handles simulate crash trigger and reflects notification', async () => {
      vi.spyOn(api, 'simulateCrash').mockResolvedValue({
        incident_id: 'INC_TEST_CRASH_99',
        status: 'QUARANTINED',
      });

      render(<DLQCenter />);

      const crashBtn = screen.getByRole('button', { name: /Simulate Crash/i });
      fireEvent.click(crashBtn);

      await waitFor(() => {
        expect(screen.getByText(/Simulated ML crash caught safely by DLQ Resiliency Guard/i)).toBeInTheDocument();
      });
    });

    it('handles purge resolved records action', async () => {
      vi.spyOn(api, 'purgeResolvedDLQ').mockResolvedValue({ deleted_count: 5 });

      render(<DLQCenter />);

      const purgeBtn = screen.getByRole('button', { name: /Purge Resolved/i });
      fireEvent.click(purgeBtn);

      await waitFor(() => {
        expect(screen.getByText(/Purged 5 resolved records from DLQ\./i)).toBeInTheDocument();
      });
    });
  });

  describe('6. CommandCenterDashboard Full Navigation & Tab Switching Stress', () => {
    it('switches between all navigation tabs seamlessly without unhandled DOM exceptions', async () => {
      render(<CommandCenterDashboard />);

      // 1. Overview Matrix (Default)
      expect(screen.getByText('Sports Card Ecosystem Hub')).toBeInTheDocument();
      expect(screen.getByText('Media Ingestion & PySpark Grading Pipeline')).toBeInTheDocument();
      expect(screen.getByText('ML Agent & Viral Trends Optimizer')).toBeInTheDocument();
      expect(screen.getByText('Dead Letter Queue & Incident Isolation Center')).toBeInTheDocument();

      // 2. Switch to Sports Cards Tab
      const sportsTab = screen.getByRole('button', { name: /Sports Cards/i });
      fireEvent.click(sportsTab);
      expect(screen.getByText('Sports Card Ecosystem Hub')).toBeInTheDocument();
      expect(screen.queryByText('Media Ingestion & PySpark Grading Pipeline')).toBeNull();

      // 3. Switch to Media & PySpark Tab
      const mediaTab = screen.getByRole('button', { name: /Media & PySpark/i });
      fireEvent.click(mediaTab);
      expect(screen.getByText('Media Ingestion & PySpark Grading Pipeline')).toBeInTheDocument();
      expect(screen.queryByText('Sports Card Ecosystem Hub')).toBeNull();

      // 4. Switch to ML Agent Tab
      const mlTab = screen.getByRole('button', { name: /ML Agent & Trends/i });
      fireEvent.click(mlTab);
      expect(screen.getByText('ML Agent & Viral Trends Optimizer')).toBeInTheDocument();

      // 5. Switch to DLQ Tab
      const dlqTab = screen.getByRole('button', { name: /DLQ Isolation/i });
      fireEvent.click(dlqTab);
      expect(screen.getByText('Dead Letter Queue & Incident Isolation Center')).toBeInTheDocument();

      // 6. Return to Overview
      const overviewTab = screen.getByRole('button', { name: /Overview Matrix/i });
      fireEvent.click(overviewTab);
      expect(screen.getByText('Sports Card Ecosystem Hub')).toBeInTheDocument();
      expect(screen.getByText('Real-Time Pipeline Event Stream (SSE Terminal)')).toBeInTheDocument();
    });
  });
});
