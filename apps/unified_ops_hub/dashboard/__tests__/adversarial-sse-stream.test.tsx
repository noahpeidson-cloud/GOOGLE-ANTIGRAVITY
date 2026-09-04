import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { LiveTelemetryStream } from '@/components/LiveTelemetryStream';

class MockEventSource {
  public url: string;
  public onmessage: ((event: MessageEvent) => void) | null = null;
  public onerror: ((event: Event) => void) | null = null;
  public readyState: number = 1;
  public closed: boolean = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  static instances: MockEventSource[] = [];
  static reset() {
    MockEventSource.instances = [];
  }

  close() {
    this.closed = true;
    this.readyState = 2;
  }

  emitMessage(data: string) {
    if (this.onmessage && !this.closed) {
      this.onmessage(new MessageEvent('message', { data }));
    }
  }

  emitError() {
    if (this.onerror && !this.closed) {
      this.onerror(new Event('error'));
    }
  }
}

describe('Adversarial SSE Stream & LiveTelemetryStream Stress Tests', () => {
  const originalEventSource = global.EventSource;

  beforeEach(() => {
    MockEventSource.reset();
    (global as any).EventSource = MockEventSource;
  });

  afterEach(() => {
    (global as any).EventSource = originalEventSource;
    vi.restoreAllMocks();
  });

  it('renders default initialized buffer when offline or stream pending', () => {
    render(<LiveTelemetryStream />);
    expect(screen.getByText('Real-Time Pipeline Event Stream (SSE Terminal)')).toBeInTheDocument();
    expect(screen.getByText(/Dynamic port manager initialized/i)).toBeInTheDocument();
    expect(screen.getByText(/Card Ladder ETL loop online/i)).toBeInTheDocument();
    expect(screen.getByText('LIVE STREAM')).toBeInTheDocument();
  });

  it('handles incoming SSE messages and appends them to terminal buffer', () => {
    render(<LiveTelemetryStream streamUrl="/api/v1/test/stream" />);
    expect(MockEventSource.instances.length).toBe(1);

    const es = MockEventSource.instances[0];
    act(() => {
      es.emitMessage('[ADVERSARIAL_STREAM] Ingestion batch #9921 completed successfully.');
    });

    expect(screen.getByText(/\[ADVERSARIAL_STREAM\] Ingestion batch #9921 completed successfully\./i)).toBeInTheDocument();
  });

  it('bounds log buffer strictly to 100 items when flooded with >100 SSE bursts', () => {
    const { container } = render(<LiveTelemetryStream streamUrl="/api/v1/burst" />);
    const es = MockEventSource.instances[0];

    act(() => {
      for (let i = 1; i <= 150; i++) {
        es.emitMessage(`BURST_EVENT_${i}`);
      }
    });

    // Check that BURST_EVENT_150 is present
    expect(screen.getByText(/BURST_EVENT_150/i)).toBeInTheDocument();
    // Check that BURST_EVENT_1 was evicted (since max buffer is 100)
    expect(screen.queryByText(/BURST_EVENT_1$/i)).toBeNull();

    // Verify total rendered log elements in terminal does not exceed 100
    const logItems = container.querySelectorAll('.font-mono.space-y-1 > div');
    expect(logItems.length).toBeLessThanOrEqual(100);
  });

  it('clears log buffer on user Clear click and shows empty state', () => {
    render(<LiveTelemetryStream />);
    const clearBtn = screen.getByRole('button', { name: /Clear/i });

    fireEvent.click(clearBtn);

    expect(screen.getByText('No event logs in buffer.')).toBeInTheDocument();
    expect(screen.queryByText(/Dynamic port manager initialized/i)).toBeNull();
  });

  it('handles stream connection error and closes EventSource safely', () => {
    render(<LiveTelemetryStream />);
    const es = MockEventSource.instances[0];
    expect(es.closed).toBe(false);

    act(() => {
      es.emitError();
    });

    expect(es.closed).toBe(true);
  });

  it('reacts to contentvisibilityautostatechange event per modern-web-guidance (skipped=true pauses, skipped=false resumes)', () => {
    const { container } = render(<LiveTelemetryStream />);
    const panel = container.querySelector('.content-visibility-auto');
    expect(panel).not.toBeNull();

    const es1 = MockEventSource.instances[0];
    expect(es1.closed).toBe(false);

    // Simulate off-screen skip (tab/scroll away)
    act(() => {
      panel?.dispatchEvent(new CustomEvent('contentvisibilityautostatechange', { detail: { skipped: true } }));
      // also dispatch with event.skipped directly
      const skipEvent = new Event('contentvisibilityautostatechange') as any;
      skipEvent.skipped = true;
      panel?.dispatchEvent(skipEvent);
    });

    expect(es1.closed).toBe(true);
    expect(screen.getByText('PAUSED')).toBeInTheDocument();

    // Simulate scrolling back into viewport (skipped = false)
    act(() => {
      const resumeEvent = new Event('contentvisibilityautostatechange') as any;
      resumeEvent.skipped = false;
      panel?.dispatchEvent(resumeEvent);
    });

    expect(screen.getByText('LIVE STREAM')).toBeInTheDocument();
    expect(MockEventSource.instances.length).toBe(2);
  });

  it('operates safely when EventSource is not supported (undefined)', () => {
    (global as any).EventSource = undefined;
    expect(() => {
      render(<LiveTelemetryStream />);
    }).not.toThrow();
    expect(screen.getByText('Real-Time Pipeline Event Stream (SSE Terminal)')).toBeInTheDocument();
  });
});
