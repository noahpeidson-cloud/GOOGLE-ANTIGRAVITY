import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import CommandCenterDashboard from '@/app/page';

describe('Command Center Master Layout Integration', () => {
  it('renders master command center with header, navigation, and system status indicator', async () => {
    render(<CommandCenterDashboard />);

    // Header & Status
    expect(screen.getByText('Unified Ops Hub')).toBeInTheDocument();
    expect(screen.getByText('SYSTEM HEALTHY')).toBeInTheDocument();
    expect(screen.getByText('Port 8000')).toBeInTheDocument();

    // Navigation Tabs
    expect(screen.getByText('Overview Matrix')).toBeInTheDocument();
    expect(screen.getByText('Sports Cards')).toBeInTheDocument();
    expect(screen.getByText('Media & PySpark')).toBeInTheDocument();
    expect(screen.getByText('Media Studio')).toBeInTheDocument();
    expect(screen.getByText('ML Agent & Trends')).toBeInTheDocument();
    expect(screen.getByText('DLQ Isolation')).toBeInTheDocument();

    // All 4 Subsystem Widgets in Overview
    expect(screen.getByText('Sports Card Ecosystem Hub')).toBeInTheDocument();
    expect(screen.getByText('Media Ingestion & PySpark Grading Pipeline')).toBeInTheDocument();
    expect(screen.getByText('ML Agent & Viral Trends Optimizer')).toBeInTheDocument();
    expect(screen.getByText('Dead Letter Queue & Incident Isolation Center')).toBeInTheDocument();

    // Live Telemetry Stream
    expect(screen.getByText('Real-Time Pipeline Event Stream (SSE Terminal)')).toBeInTheDocument();
  });
});
