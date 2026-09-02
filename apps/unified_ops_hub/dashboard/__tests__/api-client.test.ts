import { describe, it, expect } from 'vitest';
import {
  getSystemHealth,
  getPortStatus,
  getSportsPortfolio,
  getSportsStats,
  captureSportsCard,
  gradeVideo,
  renderMediaVideo,
  listMediaRenders,
  getMLTelemetry,
  triggerLensFailover,
  getDLQIncidents,
  getDLQStats,
  retryDLQIncident,
  purgeResolvedDLQ,
} from '@/lib/api';

describe('API Client Layer', () => {
  it('returns valid system health data in offline/test mode', async () => {
    const health = await getSystemHealth();
    expect(health.status.toUpperCase()).toBe('HEALTHY');
    expect(health.ports).toBeDefined();
    expect(health.services).toBeDefined();
  });

  it('handles sports card capture and statistics calculation', async () => {
    const portBefore = await getSportsPortfolio();
    const newCard = await captureSportsCard({
      player: 'Caitlin Clark',
      year: '2024',
      set_name: 'Prizm WNBA',
      investment: 500,
      estimated_value: 950,
    });
    expect(newCard.player).toBe('Caitlin Clark');
    expect(newCard.ai_status).toBe('CLEARED');

    const portAfter = await getSportsPortfolio();
    expect(portAfter.cards.length).toBeGreaterThanOrEqual(portBefore.cards.length);
  });

  it('grades videos with PySpark weights and killswitch penalization', async () => {
    // Normal 9:16 high score
    const highGrade = await gradeVideo('v1', { HRV: 90, DPAW: 90, ADR_SFD: 90, CKE_MVE: 90, LTSS: 90 }, '9:16');
    expect(highGrade.evpi).toBe(90);
    expect(highGrade.verdict).toBe('VIRAL_READY');

    // Low HRV killswitch (<40 caps at 49.9)
    const lowHrvGrade = await gradeVideo('v2', { HRV: 30, DPAW: 90, ADR_SFD: 90, CKE_MVE: 90, LTSS: 90 }, '9:16');
    expect(lowHrvGrade.evpi).toBeLessThanOrEqual(49.9);

    // 16:9 penalty (50% reduction)
    const landscapeGrade = await gradeVideo('v3', { HRV: 90, DPAW: 90, ADR_SFD: 90, CKE_MVE: 90, LTSS: 90 }, '16:9');
    expect(landscapeGrade.evpi).toBe(45);
  });

  it('handles ML telemetry, lens failover, and DLQ incident operations', async () => {
    const ml = await getMLTelemetry();
    expect(ml.clusters.c0_healthy).toBe(78);

    const failover = await triggerLensFailover('tiktok');
    expect(failover.success).toBe(true);

    const dlq = await getDLQIncidents();
    expect(dlq.count).toBeGreaterThan(0);

    const retry = await retryDLQIncident('INC_a81f09c2');
    expect(retry.success).toBe(true);

    const purge = await purgeResolvedDLQ();
    expect(purge.deleted_count).toBeGreaterThanOrEqual(0);
  });

  it('handles headless media render trigger and render catalog listing', async () => {
    const renderRes = await renderMediaVideo({
      source_file: 'clip_ultra_drop_4k_01.mp4',
      in_point: 5.0,
      out_point: 15.0,
      crop_ratio: '9:16',
      text_overlay: '🔥 HYPE DROP',
      sync: true,
    });
    expect(renderRes.status).toBe('completed');
    expect(renderRes.job_id).toBeDefined();
    expect(renderRes.duration).toBe(10.0);
    expect(renderRes.crop_ratio).toBe('9:16');
    expect(renderRes.text_overlay).toBe('🔥 HYPE DROP');

    const renders = await listMediaRenders();
    expect(renders.total).toBeGreaterThanOrEqual(1);
    expect(renders.renders.length).toBeGreaterThanOrEqual(1);
  });
});

