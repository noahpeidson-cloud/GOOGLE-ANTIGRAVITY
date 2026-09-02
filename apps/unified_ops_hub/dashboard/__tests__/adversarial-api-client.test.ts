import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getSystemHealth,
  getPortStatus,
  getSportsPortfolio,
  getSportsStats,
  captureSportsCard,
  getMediaHealth,
  getMediaProxies,
  triggerMediaJob,
  gradeVideo,
  getMLTelemetry,
  triggerLensFailover,
  getDLQIncidents,
  getDLQStats,
  retryDLQIncident,
  purgeResolvedDLQ,
  simulateCrash,
} from '@/lib/api';

describe('Adversarial API Client Stress Test Suite', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  describe('1. Network Failure & Offline Resilience', () => {
    beforeEach(() => {
      global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch (Network Unreachable)'));
    });

    it('getSystemHealth falls back to deterministic healthy state upon network failure', async () => {
      const health = await getSystemHealth();
      expect(health).toBeDefined();
      expect(health.status).toBe('HEALTHY');
      expect(health.version).toBe('1.0.0');
      expect(health.ports['8000']).toBeDefined();
      expect(health.services.dlq_gateway).toBe('ACTIVE');
    });

    it('getPortStatus falls back to default ports upon network failure', async () => {
      const ports = await getPortStatus();
      expect(ports).toBeDefined();
      expect(ports['8000'].port).toBe(8000);
      expect(ports['8001'].port).toBe(8001);
    });

    it('getSportsPortfolio and getSportsStats fallback smoothly upon network failure', async () => {
      const portfolio = await getSportsPortfolio();
      expect(portfolio.total).toBeGreaterThan(0);
      expect(portfolio.cards.length).toBeGreaterThan(0);

      const stats = await getSportsStats();
      expect(stats.total_cards).toBeGreaterThan(0);
      expect(stats.total_investment).toBeGreaterThan(0);
    });

    it('captureSportsCard inserts locally into mock state on network failure', async () => {
      const card = await captureSportsCard({
        player: 'Anthony Edwards',
        set_name: 'Select Courtside',
        year: '2020',
        investment: 800,
        estimated_value: 1400,
      });
      expect(card.id).toMatch(/^CARD_/);
      expect(card.player).toBe('Anthony Edwards');
      expect(card.ai_status).toBe('CLEARED');
    });

    it('getMediaHealth and getMediaProxies fallback upon network failure', async () => {
      const mediaHealth = await getMediaHealth();
      expect(mediaHealth.status).toBe('READY');
      expect(mediaHealth.active_jobs).toBe(2);

      const proxies = await getMediaProxies();
      expect(proxies.proxies.length).toBe(3);
    });

    it('triggerMediaJob creates queued job fallback upon network failure', async () => {
      const job = await triggerMediaJob('TEST_CLIP.mp4', 'vertical_reframes', 'HIGH');
      expect(job.job_id).toMatch(/^job_/);
      expect(job.status).toBe('QUEUED');
      expect(job.clip_name).toBe('TEST_CLIP.mp4');
    });

    it('getMLTelemetry and triggerLensFailover fallback smoothly upon network failure', async () => {
      const ml = await getMLTelemetry();
      expect(ml.platform).toBe('tiktok');
      expect(ml.clusters.c0_healthy).toBe(78);

      const failover = await triggerLensFailover('tiktok');
      expect(failover.success).toBe(true);
      expect(failover.active_lens).toBeDefined();
    });

    it('getDLQIncidents, getDLQStats, retryDLQIncident, purgeResolvedDLQ fallback gracefully', async () => {
      const incidents = await getDLQIncidents();
      expect(incidents.count).toBeGreaterThanOrEqual(1);

      const stats = await getDLQStats();
      expect(stats.quarantined).toBeGreaterThanOrEqual(1);

      const retry = await retryDLQIncident('INC_a81f09c2');
      expect(retry.success).toBe(true);

      const purge = await purgeResolvedDLQ();
      expect(purge.deleted_count).toBeGreaterThanOrEqual(0);
    });

    it('simulateCrash generates quarantined incident fallback upon network failure', async () => {
      const crash = await simulateCrash('SimulatedFailure');
      expect(crash.error).toBe('INTERNAL_SERVER_ERROR');
      expect(crash.status).toBe('QUARANTINED');
      expect(crash.incident_id).toMatch(/^INC_/);
    });
  });

  describe('2. HTTP Error Status Code Resilience (500, 502, 404, 422)', () => {
    it('handles HTTP 500 Internal Server Error by returning fallback', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: async () => ({ error: 'Database connection failed' }),
      } as Response);

      const health = await getSystemHealth();
      expect(health.status).toBe('HEALTHY');

      const stats = await getSportsStats();
      expect(stats.total_cards).toBeGreaterThan(0);
    });

    it('handles HTTP 502 Bad Gateway by returning fallback', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        statusText: 'Bad Gateway',
      } as Response);

      const ml = await getMLTelemetry();
      expect(ml.platform).toBe('tiktok');
    });

    it('handles HTTP 404 Not Found by returning fallback', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      } as Response);

      const incidents = await getDLQIncidents();
      expect(incidents.incidents).toBeDefined();
    });
  });

  describe('3. Corrupted & Malformed Server Payload Resilience', () => {
    it('handles invalid JSON syntax from server without unhandled rejection', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => {
          throw new SyntaxError('Unexpected token < in JSON at position 0');
        },
      } as unknown as Response);

      const health = await getSystemHealth();
      expect(health.status).toBe('HEALTHY');

      const portfolio = await getSportsPortfolio();
      expect(portfolio.cards).toBeDefined();
    });

    it('handles null JSON response from server', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => null,
      } as unknown as Response);

      const health = await getSystemHealth();
      expect(health).toBeDefined();
      expect(health.status).toBe('HEALTHY');
    });

    it('handles partially empty object response from server for getSystemHealth', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          status: 'ok',
          uptime_seconds: 'corrupted_string_uptime', // invalid type
          ports: {}, // empty
        }),
      } as unknown as Response);

      const health = await getSystemHealth();
      expect(health.status).toBe('OK');
      expect(typeof health.uptime_seconds).toBe('number'); // coerced/defaulted
      expect(health.ports['8000']).toBeDefined(); // defaulted from mock state
    });
  });

  describe('4. PySpark Video Grading Weight & Killswitch Edge Cases', () => {
    it('defaults missing score keys to 50 without crashing', async () => {
      // Pass completely empty scores object
      const result = await gradeVideo('clip_empty_scores.mp4', {} as any, '9:16');
      expect(result.video_id).toBe('clip_empty_scores.mp4');
      // 50 * (0.25 + 0.25 + 0.20 + 0.15 + 0.15) = 50.0
      expect(result.evpi).toBe(50);
      expect(result.verdict).toBe('MODERATE_REACH');
    });

    it('caps EVPI at 49.9 when HRV is below 40 even if all other metrics are 100', async () => {
      const result = await gradeVideo('clip_low_hrv.mp4', {
        HRV: 39.9,
        DPAW: 100,
        ADR_SFD: 100,
        CKE_MVE: 100,
        LTSS: 100,
      }, '9:16');
      expect(result.evpi).toBeLessThanOrEqual(49.9);
      expect(result.verdict).toBe('LOW_REACH');
    });

    it('applies 50% penalty on 16:9 landscape aspect ratio', async () => {
      const portrait = await gradeVideo('clip.mp4', { HRV: 100, DPAW: 100, ADR_SFD: 100, CKE_MVE: 100, LTSS: 100 }, '9:16');
      const landscape = await gradeVideo('clip.mp4', { HRV: 100, DPAW: 100, ADR_SFD: 100, CKE_MVE: 100, LTSS: 100 }, '16:9');

      expect(portrait.evpi).toBe(100);
      expect(portrait.verdict).toBe('VIRAL_READY');
      expect(landscape.evpi).toBe(50);
      expect(landscape.verdict).toBe('MODERATE_REACH');
    });

    it('handles unknown aspect ratios without breaking evaluation', async () => {
      const result = await gradeVideo('clip.mp4', { HRV: 80, DPAW: 80, ADR_SFD: 80, CKE_MVE: 80, LTSS: 80 }, '1:1');
      expect(result.evpi).toBe(80);
      expect(result.verdict).toBe('HIGH_POTENTIAL');
    });
  });

  describe('5. DLQ Filtering & Mutation Stress Testing', () => {
    it('filters DLQ incidents by status and category', async () => {
      const quarantined = await getDLQIncidents({ status: 'QUARANTINED' });
      quarantined.incidents.forEach((inc) => {
        expect(inc.status).toBe('QUARANTINED');
      });

      const nonExistent = await getDLQIncidents({ status: 'NON_EXISTENT_STATUS' });
      expect(nonExistent.incidents.length).toBe(0);
      expect(nonExistent.count).toBe(0);
    });

    it('handles retry for unknown incident ID safely', async () => {
      const res = await retryDLQIncident('UNKNOWN_INCIDENT_ID');
      expect(res.success).toBe(true);
      expect(res.incident_id).toBe('UNKNOWN_INCIDENT_ID');
    });
  });
});
