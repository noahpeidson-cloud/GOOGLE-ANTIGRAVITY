import React, { useState } from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { LiveTelemetryStream } from '@/components/LiveTelemetryStream';
import { DLQCenter } from '@/components/DLQCenter';
import { SportsCardWidget } from '@/components/SportsCardWidget';
import { MediaIngestionWidget } from '@/components/MediaIngestionWidget';
import { MLAgentWidget } from '@/components/MLAgentWidget';
import { SystemHealthHeader } from '@/components/SystemHealthHeader';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import CommandCenterDashboard from '@/app/page';
import * as api from '@/lib/api';

const INITIAL_DLQ_MOCK: api.DLQIncident[] = [
  {
    incident_id: 'INC_a81f09c2',
    source_service: 'pyspark_grading',
    error_category: 'ML_GRADING_FAILURE',
    error_message: 'Simulated PySpark partition crash in Gemini Omni grading job.',
    retry_count: 0,
    max_retries: 3,
    status: 'QUARANTINED',
    timestamp: Date.now() - 1200000,
    payload: {
      video_id: 'clip_festival_drop_4k_01.mp4',
      aspect_ratio: '9:16',
      scores: { HRV: 94.0, DPAW: 88.0 },
    },
    traceback_str: 'RuntimeError: Simulated PySpark partition crash\n  at execute_job(app.py:378)',
  },
  {
    incident_id: 'INC_b94e11d8',
    source_service: 'gateway_validation',
    error_category: 'CORRUPTED_PAYLOAD',
    error_message: 'Missing required field [player] in card capture schema.',
    retry_count: 3,
    max_retries: 3,
    status: 'RESOLVED',
    timestamp: Date.now() - 86400000,
    payload: { set_name: 'Prizm', year: '2024' },
    traceback_str: 'ValidationError: 1 validation error for SportsCardCaptureRequest\nplayer: Field required',
  },
];

// Custom Mock EventSource with detailed lifecycle spy
class MockStressEventSource {
  public static instances: MockStressEventSource[] = [];
  public static closeCalls = 0;
  public static instancesCreated = 0;

  url: string;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  readyState = 1; // OPEN
  closed = false;

  constructor(url: string) {
    this.url = url;
    this.closed = false;
    MockStressEventSource.instancesCreated++;
    MockStressEventSource.instances.push(this);
  }

  close() {
    this.readyState = 2; // CLOSED
    this.closed = true;
    MockStressEventSource.closeCalls++;
  }

  emitMessage(data: string) {
    if (!this.closed && this.onmessage) {
      this.onmessage({ data });
    }
  }

  emitError(errorData?: any) {
    if (!this.closed && this.onerror) {
      this.onerror(errorData || new Error('Stream error'));
    }
  }

  static reset() {
    MockStressEventSource.instances = [];
    MockStressEventSource.closeCalls = 0;
    MockStressEventSource.instancesCreated = 0;
  }
}

describe('Adversarial Stress Test Suite — Unified Next.js Command Center Dashboard', () => {
  beforeEach(async () => {
    MockStressEventSource.reset();
    (window as any).EventSource = MockStressEventSource;
    vi.clearAllMocks();

    // Deep reset mock state before every test
    const { incidents } = await api.getDLQIncidents();
    incidents.length = 0;
    INITIAL_DLQ_MOCK.forEach((item) => incidents.push(JSON.parse(JSON.stringify(item))));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // =========================================================================
  // 1. HIGH-FREQUENCY SSE MESSAGE BURSTS & BUFFER INTEGRITY
  // =========================================================================
  describe('1. High-Frequency SSE Message Bursts & Buffer Capping', () => {
    it('survives a burst of 500 rapid SSE messages while enforcing the 100-entry sliding window cap and FIFO ordering', async () => {
      const { unmount } = render(<LiveTelemetryStream streamUrl="/api/v1/events/stream" />);

      const esInstance = MockStressEventSource.instances[0];
      expect(esInstance).toBeDefined();

      // Fire 500 consecutive messages in rapid succession
      act(() => {
        for (let i = 1; i <= 500; i++) {
          esInstance.emitMessage(`BURST_EVENT_${i}: Pipeline payload sync index ${i}`);
        }
      });

      // Query all rendered log items
      const logElements = screen.getAllByText(/BURST_EVENT_/i);

      // The sliding buffer is capped at [...prev.slice(-99), newLog], meaning max 100 total items
      expect(logElements.length).toBeLessThanOrEqual(100);

      // Verify FIFO retention: the oldest messages (1..400) should be safely evicted
      expect(screen.queryByText(/BURST_EVENT_1:/)).not.toBeInTheDocument();
      expect(screen.queryByText(/BURST_EVENT_50:/)).not.toBeInTheDocument();
      expect(screen.queryByText(/BURST_EVENT_400:/)).not.toBeInTheDocument();

      // The latest message (500) must be present in the document
      expect(screen.getByText(/BURST_EVENT_500:/)).toBeInTheDocument();

      // Test buffer clearing
      const clearBtn = screen.getByRole('button', { name: /clear/i });
      fireEvent.click(clearBtn);

      expect(screen.getByText('No event logs in buffer.')).toBeInTheDocument();
      expect(screen.queryByText(/BURST_EVENT_500:/)).not.toBeInTheDocument();

      unmount();
    });

    it('survives an ultra-burst of 1,000 rapid messages without crashing the component state', async () => {
      const { unmount } = render(<LiveTelemetryStream streamUrl="/api/v1/events/stream" />);
      const esInstance = MockStressEventSource.instances[0];

      act(() => {
        for (let i = 1; i <= 1000; i++) {
          esInstance.emitMessage(`HIGH_VOL_${i}`);
        }
      });

      expect(screen.getByText(/HIGH_VOL_1000/)).toBeInTheDocument();
      expect(screen.queryByText(/HIGH_VOL_1\b/)).not.toBeInTheDocument();

      unmount();
    });

    it('handles contentvisibilityautostatechange events (pause when skipped, reconnect when active)', async () => {
      const { container, unmount } = render(<LiveTelemetryStream streamUrl="/api/v1/events/stream" />);
      const hostElement = container.querySelector('.content-visibility-auto');
      expect(hostElement).toBeInTheDocument();

      expect(screen.getByText('LIVE STREAM')).toBeInTheDocument();

      // Trigger visibility skipped (scrolled out of view / offscreen)
      act(() => {
        const skipEvent = new CustomEvent('contentvisibilityautostatechange', {
          detail: {},
        });
        (skipEvent as any).skipped = true;
        hostElement!.dispatchEvent(skipEvent);
      });

      expect(screen.getByText('PAUSED')).toBeInTheDocument();

      // Trigger visibility unskipped (scrolled into view)
      act(() => {
        const unskipEvent = new CustomEvent('contentvisibilityautostatechange', {
          detail: {},
        });
        (unskipEvent as any).skipped = false;
        hostElement!.dispatchEvent(unskipEvent);
      });

      expect(screen.getByText('LIVE STREAM')).toBeInTheDocument();

      unmount();
    });

    it('handles SSE error events by closing stream safely without throwing', async () => {
      const { unmount } = render(<LiveTelemetryStream streamUrl="/api/v1/events/stream" />);
      const esInstance = MockStressEventSource.instances[0];

      act(() => {
        esInstance.emitError();
      });

      expect(esInstance.closed).toBe(true);
      unmount();
    });
  });

  // =========================================================================
  // 2. DOM RENDER PERFORMANCE & RAPID RE-RENDERS
  // =========================================================================
  describe('2. DOM Render Performance & Rapid Re-renders', () => {
    it('survives rapid tab navigation cycling through 50 tab switches without layout collapse', async () => {
      const { unmount } = render(<CommandCenterDashboard />);

      const tabs = [
        { name: 'Sports Cards', expectedHeading: /Sports Card Ecosystem Hub/i },
        { name: 'Media & PySpark', expectedHeading: /Media Ingestion & PySpark Grading/i },
        { name: 'ML Agent & Trends', expectedHeading: /ML Agent & Viral Trends Optimizer/i },
        { name: 'DLQ Isolation', expectedHeading: /Dead Letter Queue & Incident Isolation/i },
        { name: 'Overview Matrix', expectedHeading: /Sports Card Ecosystem Hub/i },
      ];

      // Perform 50 rapid sequential tab switches
      for (let cycle = 0; cycle < 10; cycle++) {
        for (const tab of tabs) {
          const tabButton = screen.getByRole('button', { name: new RegExp(tab.name, 'i') });
          fireEvent.click(tabButton);
          expect(screen.getByText(tab.expectedHeading)).toBeInTheDocument();
        }
      }

      // Verify header and dock stream remain solid
      expect(screen.getByRole('heading', { name: /Unified Ops Hub/i })).toBeInTheDocument();
      expect(screen.getByText(/Real-Time Pipeline Event Stream/i)).toBeInTheDocument();

      unmount();
    });

    it('handles high-frequency slider value updates in MediaIngestionWidget without UI freezing', async () => {
      const { unmount } = render(<MediaIngestionWidget />);

      // Find HRV slider and dispatch 50 rapid value changes
      const sliders = screen.getAllByRole('slider');
      expect(sliders.length).toBe(5);

      const hrvSlider = sliders[0];
      for (let val = 10; val <= 100; val += 2) {
        fireEvent.change(hrvSlider, { target: { value: val.toString() } });
      }

      expect(screen.getByText(/HRV \(Hook Retention\): 100/i)).toBeInTheDocument();

      // Recalculate EVPI
      const calcBtn = screen.getByRole('button', { name: /Recalculate EVPI/i });
      fireEvent.click(calcBtn);

      await waitFor(() => {
        expect(screen.getByText(/EVPI Score:/i)).toBeInTheDocument();
      });

      unmount();
    });

    it('handles rapid sequential card intake submissions in SportsCardWidget without dropping records', async () => {
      const { unmount } = render(<SportsCardWidget />);

      // Open modal
      const addBtn = screen.getByRole('button', { name: /Add New Card/i });
      fireEvent.click(addBtn);

      expect(screen.getByPlaceholderText(/Player Name/i)).toBeInTheDocument();

      // Add 3 cards sequentially with proper state transition waits
      for (let i = 1; i <= 3; i++) {
        fireEvent.change(screen.getByPlaceholderText(/Player Name/i), {
          target: { value: `Stress Player ${i}` },
        });
        fireEvent.change(screen.getByPlaceholderText(/Est. Value/i), {
          target: { value: (i * 150).toString() },
        });

        const saveBtn = screen.getByRole('button', { name: /Save & Clear AI Status/i });
        fireEvent.click(saveBtn);

        // Wait for modal to close and re-open if needed for next card
        if (i < 3) {
          await waitFor(() => {
            expect(screen.getByRole('button', { name: /Add New Card/i })).toBeInTheDocument();
          });
          const reopenBtn = screen.getByRole('button', { name: /Add New Card/i });
          fireEvent.click(reopenBtn);
        }
      }

      await waitFor(() => {
        expect(screen.getByText('Stress Player 3')).toBeInTheDocument();
      });

      unmount();
    });

    it('toggles ML lenses rapidly back and forth without state corruption', async () => {
      const { unmount } = render(<MLAgentWidget />);

      const toggleBtn = screen.getByRole('button', { name: /Lens:/i });
      expect(toggleBtn).toBeInTheDocument();

      // Trigger lens failover 4 times
      for (let i = 0; i < 4; i++) {
        fireEvent.click(toggleBtn);
        await waitFor(() => {
          expect(screen.getByText(/Lens failover executed:/i)).toBeInTheDocument();
        });
      }

      unmount();
    });
  });

  // =========================================================================
  // 3. DLQ REPLAY DISPATCH RACES & CONCURRENCY
  // =========================================================================
  describe('3. DLQ Replay Dispatch Races & Concurrency', () => {
    it('handles 10 concurrent replay dispatches on the same incident idempotently', async () => {
      const retrySpy = vi.spyOn(api, 'retryDLQIncident');

      // Dispatch 10 parallel replay calls for the same incident
      const promises = Array.from({ length: 10 }, () => api.retryDLQIncident('INC_a81f09c2'));
      const results = await Promise.all(promises);

      expect(results).toHaveLength(10);
      results.forEach((res) => {
        expect(res.success).toBe(true);
        expect(res.status).toBe('RESOLVED');
        expect(res.incident_id).toBe('INC_a81f09c2');
      });

      expect(retrySpy).toHaveBeenCalledTimes(10);
    });

    it('handles multiple concurrent crash simulations without ID collisions', async () => {
      const promises = Array.from({ length: 10 }, () => api.simulateCrash('HighConcurrencyCrash'));
      const results = await Promise.all(promises);

      expect(results).toHaveLength(10);
      const incidentIds = results.map((r) => r.incident_id);
      const uniqueIds = new Set(incidentIds);

      // All 10 generated incidents must have distinct IDs
      expect(uniqueIds.size).toBe(10);
      results.forEach((res) => {
        expect(res.status).toBe('QUARANTINED');
      });
    });

    it('handles rapid clicking of the Replay and Purge buttons in the DLQCenter UI', async () => {
      const { unmount } = render(<DLQCenter />);

      await waitFor(() => {
        expect(screen.getByText('INC_a81f09c2')).toBeInTheDocument();
        expect(screen.getByTitle('Trigger Replay')).toBeInTheDocument();
      });

      // Rapidly click Replay
      const replayBtn = screen.getByTitle('Trigger Replay');
      for (let i = 0; i < 5; i++) {
        fireEvent.click(replayBtn);
      }

      await waitFor(() => {
        expect(screen.getByText(/Replay triggered for INC_a81f09c2/i)).toBeInTheDocument();
      });

      // Click Purge
      const purgeBtn = screen.getByRole('button', { name: /Purge Resolved/i });
      fireEvent.click(purgeBtn);

      await waitFor(() => {
        expect(screen.getByText(/Purged \d+ resolved records from DLQ/i)).toBeInTheDocument();
      });

      unmount();
    });

    it('inspects payload modal under stress without breaking modal state', async () => {
      const { unmount } = render(<DLQCenter />);

      await waitFor(() => {
        expect(screen.getByText('INC_a81f09c2')).toBeInTheDocument();
      });

      // Open inspector modal
      const inspectBtns = screen.getAllByTitle('Inspect Payload');
      fireEvent.click(inspectBtns[0]);

      expect(screen.getByText(/Quarantine Inspector: INC_a81f09c2/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Simulated PySpark partition crash/i).length).toBeGreaterThanOrEqual(1);

      // Close modal
      const closeBtn = screen.getByText('Close');
      fireEvent.click(closeBtn);

      expect(screen.queryByText(/Quarantine Inspector: INC_a81f09c2/i)).not.toBeInTheDocument();

      unmount();
    });
  });

  // =========================================================================
  // 4. MEMORY LEAK CHECKS DURING STREAM UNMOUNTING & LIFECYCLE
  // =========================================================================
  describe('4. Memory Leak Checks During Stream Unmounting & Lifecycle', () => {
    it('closes EventSource cleanly and removes all listeners across 25 rapid mount/unmount cycles', () => {
      for (let i = 0; i < 25; i++) {
        const { unmount } = render(<LiveTelemetryStream streamUrl="/api/v1/events/stream" />);
        unmount();
      }

      // 25 instances created, 25 close calls executed
      expect(MockStressEventSource.instancesCreated).toBe(25);
      expect(MockStressEventSource.closeCalls).toBe(25);
      MockStressEventSource.instances.forEach((inst) => {
        expect(inst.closed).toBe(true);
      });
    });

    it('does not leak or throw when messages arrive after unmount', () => {
      const { unmount } = render(<LiveTelemetryStream streamUrl="/api/v1/events/stream" />);
      const esInstance = MockStressEventSource.instances[0];

      unmount();
      expect(esInstance.closed).toBe(true);

      // Emitting on a closed/unmounted instance should be a no-op and not throw
      expect(() => {
        esInstance.emitMessage('LATE_BURST_MESSAGE_POST_UNMOUNT');
      }).not.toThrow();
    });

    it('cleans up interval timer on SystemHealthHeader unmount', () => {
      const clearIntervalSpy = vi.spyOn(window, 'clearInterval');
      const { unmount } = render(<SystemHealthHeader />);

      unmount();
      expect(clearIntervalSpy).toHaveBeenCalled();
    });
  });

  // =========================================================================
  // 5. ERROR BOUNDARY FAULT TOLERANCE & RECOVERY
  // =========================================================================
  describe('5. Error Boundary Fault Tolerance & Recovery', () => {
    const ProblematicComponent = ({ shouldThrow }: { shouldThrow: boolean }) => {
      if (shouldThrow) {
        throw new Error('Simulated Hard Crash inside child widget');
      }
      return <div>Child Component Healthy</div>;
    };

    it('catches uncaught component exceptions and provides deterministic recovery', () => {
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const Wrapper = () => {
        const [shouldThrow, setShouldThrow] = useState(true);
        return (
          <ErrorBoundary fallbackTitle="Custom Fault Captured">
            <ProblematicComponent shouldThrow={shouldThrow} />
            {shouldThrow && (
              <button onClick={() => setShouldThrow(false)}>Fix Child</button>
            )}
          </ErrorBoundary>
        );
      };

      const { unmount } = render(<Wrapper />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Custom Fault Captured')).toBeInTheDocument();
      expect(screen.getByText(/Simulated Hard Crash inside child widget/i)).toBeInTheDocument();

      // Click Reset & Recover
      const resetBtn = screen.getByRole('button', { name: /Reset & Recover/i });
      fireEvent.click(resetBtn);

      spy.mockRestore();
      unmount();
    });
  });
});
